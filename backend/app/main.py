from app.config import APP_NAME, ENVIRONMENT, DISCORD_TOKEN
from app.interfaces.discord.bot import start_bot


def main():
    print(f"Starting {APP_NAME}...")
    print(f"Environment: {ENVIRONMENT}")

    start_bot(DISCORD_TOKEN)


if __name__ == "__main__":
    main()