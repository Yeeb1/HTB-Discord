if __name__ == "__main__":
    import asyncio
    from htb_discord.config import AppConfig
    cfg = AppConfig.from_file("config.yaml")
    asyncio.run(start_http(cfg))