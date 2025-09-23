from __future__ import annotations
import datetime as dt
from typing import Dict, Any, List, Optional
from aiohttp import web

from htb_discord.database import DatabaseManager  # dein Modul

CRLF = "\r\n"

def _esc(s: Optional[str]) -> str:
    s = s or ""
    return (s.replace("\\", "\\\\")
             .replace(";", r"\;")
             .replace(",", r"\,")
             .replace("\n", r"\n"))

def _fold(line: str, limit: int = 75) -> str:
    if len(line) <= limit:
        return line
    out, first = [], True
    while line:
        chunk, line = line[:limit], line[limit:]
        out.append(chunk if first else " " + chunk)
        first = False
    return CRLF.join(out)

def _fmt_dt_utc(ts: dt.datetime) -> str:
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=dt.timezone.utc)
    ts = ts.astimezone(dt.timezone.utc)
    return ts.strftime("%Y%m%dT%H%M%SZ")

def _vevent(uid: str, start: dt.datetime, end: dt.datetime,
            summary: str, description: str = "", location: str = "", url: str = "") -> str:
    lines = [
        "BEGIN:VEVENT",
        f"UID:{_esc(uid)}",
        f"DTSTAMP:{_fmt_dt_utc(dt.datetime.now(dt.timezone.utc))}",
        f"DTSTART:{_fmt_dt_utc(start)}",
        f"DTEND:{_fmt_dt_utc(end)}",
    ]
    if summary:     lines.append(_fold(f"SUMMARY:{_esc(summary)}"))
    if description: lines.append(_fold(f"DESCRIPTION:{_esc(description)}"))
    if location:    lines.append(_fold(f"LOCATION:{_esc(location)}"))
    if url:         lines.append(_fold(f"URL:{_esc(url)}"))
    lines.append("END:VEVENT")
    return CRLF.join(lines)

def _vcalendar(prodid: str, events_ics: List[str]) -> str:
    head = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        f"PRODID:{_esc(prodid)}",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
    ]
    return CRLF.join(head + events_ics + ["END:VCALENDAR"]) + CRLF

def _parse_iso_utc(s: str) -> Optional[dt.datetime]:
    if not s:
        return None
    try:
        # akzeptiere "YYYY-MM-DD" oder ISO mit Zeit
        if len(s) == 10:
            return dt.datetime.fromisoformat(s).replace(tzinfo=dt.timezone.utc)
        d = dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)
    except Exception:
        return None

async def _collect_events(dbm: DatabaseManager, cfg: Dict[str, Any]) -> List[str]:
    lookback = int(cfg.get("lookback_days", 30))
    lookahead = int(cfg.get("lookahead_days", 120))
    default_minutes = int(cfg.get("default_duration_minutes", 120))
    now = dt.datetime.now(dt.timezone.utc)
    frm = now - dt.timedelta(days=lookback)
    to  = now + dt.timedelta(days=lookahead)

    events_ics: List[str] = []

    # Machines
    with dbm.get_connection('machines') as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, name, os, difficulty, release_date
            FROM tracked_machines
            WHERE release_date IS NOT NULL
        """)
        for (mid, name, os, diff, rel) in cur.fetchall():
            start = _parse_iso_utc(str(rel))
            if not start:
                continue
            if not (frm <= start <= to):
                continue
            end = start + dt.timedelta(minutes=default_minutes)

            summary = f"HTB Machine: {name}"
            desc = f"OS: {os or '-'} | Difficulty: {diff or '-'}"
            uid = f"htb-machine-{mid}@htb-discord"
            url = ""  # optional: Deep-Link, falls vorhanden
            events_ics.append(_vevent(uid, start, end, summary, desc, "", url))

    # Challenges
    with dbm.get_connection('challenges') as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, name, difficulty, category, release_date
            FROM tracked_challenges
            WHERE release_date IS NOT NULL
        """)
        for (cid, name, diff, cat, rel) in cur.fetchall():
            start = _parse_iso_utc(str(rel))
            if not start:
                continue
            if not (frm <= start <= to):
                continue
            end = start + dt.timedelta(minutes=default_minutes)

            summary = f"HTB Challenge: {name}"
            desc = f"Category: {cat or '-'} | Difficulty: {diff or '-'}"
            uid = f"htb-challenge-{cid}@htb-discord"
            url = ""
            events_ics.append(_vevent(uid, start, end, summary, desc, "", url))

    # sortiert zurückgeben (stabil nach DTSTART)
    events_ics.sort()
    return events_ics

def create_app(dbm: DatabaseManager, prodid: str, cfg: Dict[str, Any]) -> web.Application:
    app = web.Application()

    async def handler(_request: web.Request):
        events_ics = await _collect_events(dbm, cfg)
        body = _vcalendar(prodid, events_ics)
        # Basis-Caching (optional)
        headers = {
            "Cache-Control": "public, max-age=300",
        }
        return web.Response(text=body, content_type="text/calendar", charset="utf-8", headers=headers)

    secret = (cfg.get("secret_path") or "").strip().strip("/")
    path = f"/{secret}/calendar.ics" if secret else "/calendar.ics"
    app.router.add_get(path, handler)
    return app
