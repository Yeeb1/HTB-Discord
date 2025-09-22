"""Database utilities for HTB Discord service."""

import sqlite3
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List
from contextlib import contextmanager

logger = logging.getLogger(__name__)

class DatabaseManager:
    """Manages SQLite databases for the service."""

    def __init__(self, config):
        self.config = config
        self.db_paths = {
            'machines': config.get('database.machines_db'),
            'challenges': config.get('database.challenges_db'),
            'notices': config.get('database.notices_db'),
            'links': config.get('database.links_db')
        }
        self.initialize_all()

    def initialize_all(self) -> None:
        """Initialize all databases."""
        for db_name in self.db_paths:
            self.initialize_db(db_name)

    def initialize_db(self, db_name: str) -> None:
        """Initialize a specific database with its schema."""
        db_path = self.db_paths.get(db_name)
        if not db_path:
            logger.error(f"No database path configured for {db_name}")
            return

        # Ensure directory exists
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        with self.get_connection(db_name) as conn:
            cursor = conn.cursor()

            if db_name == 'machines':
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS tracked_machines (
                        id INTEGER PRIMARY KEY,
                        name TEXT,
                        os TEXT,
                        difficulty TEXT,
                        release_date TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')

            elif db_name == 'challenges':
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS tracked_challenges (
                        id INTEGER PRIMARY KEY,
                        name TEXT,
                        difficulty TEXT,
                        category TEXT,
                        release_date TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')

            elif db_name == 'notices':
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS sent_notices (
                        id INTEGER PRIMARY KEY,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')

            elif db_name == 'links':
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS links (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        channel_name TEXT,
                        link TEXT,
                        processed INTEGER DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')

            conn.commit()
            logger.debug(f"Initialized database: {db_name}")

    @contextmanager
    def get_connection(self, db_name: str):
        """Get database connection with context manager."""
        db_path = self.db_paths.get(db_name)
        if not db_path:
            raise ValueError(f"Unknown database: {db_name}")

        conn = sqlite3.connect(db_path)
        try:
            yield conn
        finally:
            conn.close()

    # Machine database methods
    def machine_exists(self, machine_id: int) -> bool:
        """Check if machine exists in database."""
        with self.get_connection('machines') as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT 1 FROM tracked_machines WHERE id = ?', (machine_id,))
            return cursor.fetchone() is not None

    def add_machine(self, machine: Dict[str, Any]) -> bool:
        """Add machine to database."""
        try:
            with self.get_connection('machines') as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO tracked_machines (id, name, os, difficulty, release_date)
                    VALUES (?, ?, ?, ?, ?)
                ''', (
                    machine['id'],
                    machine['name'],
                    machine['os'],
                    machine['difficulty_text'],
                    machine['release']
                ))
                conn.commit()
                logger.debug(f"Added machine to database: {machine['name']}")
                return True
        except Exception as e:
            logger.error(f"Failed to add machine to database: {e}")
            return False

    # Challenge database methods
    def challenge_exists(self, challenge_id: int) -> bool:
        """Check if challenge exists in database."""
        with self.get_connection('challenges') as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT 1 FROM tracked_challenges WHERE id = ?', (challenge_id,))
            return cursor.fetchone() is not None

    def add_challenge(self, challenge: Dict[str, Any]) -> bool:
        """Add challenge to database."""
        try:
            with self.get_connection('challenges') as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO tracked_challenges (id, name, difficulty, category, release_date)
                    VALUES (?, ?, ?, ?, ?)
                ''', (
                    challenge['id'],
                    challenge['name'],
                    challenge['difficulty'],
                    challenge['category_name'],
                    challenge['release_date']
                ))
                conn.commit()
                logger.debug(f"Added challenge to database: {challenge['name']}")
                return True
        except Exception as e:
            logger.error(f"Failed to add challenge to database: {e}")
            return False

    # Notice database methods
    def notice_exists(self, notice_id: int) -> bool:
        """Check if notice exists in database."""
        with self.get_connection('notices') as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT 1 FROM sent_notices WHERE id = ?', (notice_id,))
            return cursor.fetchone() is not None

    def add_notice(self, notice_id: int) -> bool:
        """Add notice to database."""
        try:
            with self.get_connection('notices') as conn:
                cursor = conn.cursor()
                cursor.execute('INSERT INTO sent_notices (id) VALUES (?)', (notice_id,))
                conn.commit()
                logger.debug(f"Added notice to database: {notice_id}")
                return True
        except Exception as e:
            logger.error(f"Failed to add notice to database: {e}")
            return False

    # Link database methods
    def save_link(self, channel_name: str, link: str) -> bool:
        """Save link to database if not already present."""
        try:
            with self.get_connection('links') as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT 1 FROM links WHERE link = ?', (link,))
                if not cursor.fetchone():
                    cursor.execute(
                        'INSERT INTO links (channel_name, link) VALUES (?, ?)',
                        (channel_name, link)
                    )
                    conn.commit()
                    logger.debug(f"Saved link to database: {link}")
                    return True
                return False
        except Exception as e:
            logger.error(f"Failed to save link to database: {e}")
            return False

    def get_unprocessed_links(self, limit: int = 10) -> List[tuple]:
        """Get unprocessed links from database."""
        try:
            with self.get_connection('links') as conn:
                cursor = conn.cursor()
                cursor.execute(
                    'SELECT id, channel_name, link FROM links WHERE processed = 0 LIMIT ?',
                    (limit,)
                )
                return cursor.fetchall()
        except Exception as e:
            logger.error(f"Failed to get unprocessed links: {e}")
            return []

    def mark_link_processed(self, link_id: int) -> bool:
        """Mark link as processed."""
        try:
            with self.get_connection('links') as conn:
                cursor = conn.cursor()
                cursor.execute('UPDATE links SET processed = 1 WHERE id = ?', (link_id,))
                conn.commit()
                logger.debug(f"Marked link as processed: {link_id}")
                return True
        except Exception as e:
            logger.error(f"Failed to mark link as processed: {e}")
            return False