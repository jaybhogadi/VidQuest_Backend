import os
from dataclasses import dataclass
from typing import List
from pydantic import BaseModel, Field
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()
# --------- Settings ---------
@dataclass
class Settings:
    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "uploads")
    WHISPER_MODEL: str = os.getenv("WHISPER_MODEL", "base.en")
    WHISPER_DEVICE: str = os.getenv("WHISPER_DEVICE", "cpu")  # "cuda" if GPU
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "auto")  # "auto" | "groq" | "ollama"
    GROQ_MODEL: str = os.getenv("GROQ_MODEL", "llama3-70b-8192")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "llama3")
    ALLOWED_ORIGINS: List[str] = field(
        default_factory=lambda: (
            os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:3000").split(",")
            if os.getenv("ALLOWED_ORIGINS") is not None
            else ["*"]
        )
    )

    def provider(self) -> str:
        if self.LLM_PROVIDER != "auto":
            return self.LLM_PROVIDER
        return "groq" if self.GROQ_API_KEY else "ollama"

settings = Settings()

# Ensure upload directory exists
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)