import os
from dotenv import load_dotenv

load_dotenv()

TARGET_HOST: str = os.environ.get("TARGET_HOST", "8.8.8.8")
TARGET_HOSTS: list[str] = [
    h.strip()
    for h in os.environ.get("TARGET_HOSTS", TARGET_HOST).split(",")
    if h.strip()
]
PING_COUNT: int = int(os.environ.get("PING_COUNT", "10"))
INTERVAL_SECONDS: int = int(os.environ.get("INTERVAL_SECONDS", "60"))
DB_PATH: str = os.environ.get("DB_PATH", "data/MCNet_checker.db")
PORT: int = int(os.environ.get("PORT", "8000"))
HOST: str = os.environ.get("HOST", "127.0.0.1")
