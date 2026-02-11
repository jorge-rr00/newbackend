"""Environment variables configuration."""
import os
from dotenv import load_dotenv

load_dotenv()

# Azure OpenAI Configuration
AZURE_OPENAI_KEY = os.getenv("AZURE_OPENAI_KEY") or os.getenv("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")
AZURE_OPENAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4")
AZURE_SEARCH_KEY = os.getenv("AZURE_SEARCH_KEY") or os.getenv("AZURE_SEARCH_API_KEY")
AZURE_SEARCH_ENDPOINT = os.getenv("AZURE_SEARCH_ENDPOINT")
AZURE_SEARCH_INDEX_FINANCIAL = os.getenv("AZURE_SEARCH_INDEX_FINANCIAL")
AZURE_SEARCH_INDEX_LEGAL = os.getenv("AZURE_SEARCH_INDEX_LEGAL")

# Azure Vision OCR (optional fallback)
AZURE_VISION_ENDPOINT = os.getenv("AZURE_VISION_ENDPOINT")
AZURE_VISION_KEY = os.getenv("AZURE_VISION_KEY")

# Azure Speech (TTS)
AZURE_SPEECH_KEY = os.getenv("AZURE_SPEECH_KEY")
AZURE_SPEECH_REGION = os.getenv("AZURE_SPEECH_REGION")
AZURE_SPEECH_VOICE = os.getenv("AZURE_SPEECH_VOICE", "es-ES-AlvaroNeural")

# Database Configuration
DATABASE_URL = os.getenv("DATABASE_URL")
DB_POOL_MAX = int(os.getenv("DB_POOL_MAX", "5"))

# Server Configuration
DEBUG = os.getenv("DEBUG", "False").lower() == "true"
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", 5100))
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "*")
INIT_DB_TOKEN = os.getenv("INIT_DB_TOKEN", "")
