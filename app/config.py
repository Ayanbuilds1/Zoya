import os

from dotenv import load_dotenv


load_dotenv()


# Application settings
APP_NAME = "Zoya"
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")


# Database
DB_PATH = os.getenv("DB_PATH", "zoya.db")


# AI provider settings
PRIMARY_AI_PROVIDER = os.getenv(
    "PRIMARY_AI_PROVIDER",
    "gemini",
).lower()

AI_FALLBACK_PROVIDERS = [
    provider.strip().lower()
    for provider in os.getenv(
        "AI_FALLBACK_PROVIDERS",
        "groq,openrouter",
    ).split(",")
    if provider.strip()
]


# Discord
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")


# AI API keys
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# Optional future providers
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")


# AI models
GROQ_MODEL = os.getenv(
    "GROQ_MODEL",
    "llama-3.3-70b-versatile",
)

OPENROUTER_MODEL = os.getenv(
    "OPENROUTER_MODEL",
    "openrouter/free",
)

OPENAI_MODEL = os.getenv(
    "OPENAI_MODEL",
    "gpt-5",
)

CLAUDE_MODEL = os.getenv(
    "CLAUDE_MODEL",
    "claude-sonnet-4-6",
)


# Safety checks
if not DISCORD_TOKEN:
    raise RuntimeError(
        "DISCORD_TOKEN is missing. "
        "Please add it to the .env file."
    )

if PRIMARY_AI_PROVIDER == "gemini" and not GEMINI_API_KEY:
    raise RuntimeError(
        "GEMINI_API_KEY is missing while Gemini "
        "is the primary AI provider."
    )