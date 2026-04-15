
from app.core.config import settings

print(f"API Key present: {bool(settings.gemini_api_key)}")
print(f"API Key length: {len(settings.gemini_api_key)}")
if settings.gemini_api_key:
    print(f"API Key: {settings.gemini_api_key[:5]}...")
else:
    print("API Key is EMPTY")
