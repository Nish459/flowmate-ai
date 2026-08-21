#!/usr/bin/env python3
"""Quick connectivity check for the Gemini API. Reads the key from env/.env,
never hardcode it.

Usage:
    python scripts/gemini_smoke_test.py
"""

import sys
from pathlib import Path

from google import genai

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.settings import settings  # noqa: E402


def main() -> None:
    if not settings.gemini_api_key:
        raise SystemExit("GEMINI_API_KEY is not set. Copy .env.example to .env and fill it in.")

    client = genai.Client(api_key=settings.gemini_api_key)
    response = client.models.generate_content(model=settings.gemini_model, contents="Say hello")
    print(response.text)


if __name__ == "__main__":
    main()
