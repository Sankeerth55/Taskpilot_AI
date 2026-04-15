
import google.generativeai as genai
from app.core.config import settings
import sys
import os

sys.path.append(os.getcwd())
genai.configure(api_key=settings.gemini_api_key)

target_models = [
    "models/gemini-1.5-flash",
    "models/gemini-1.5-flash-001",
    "models/gemini-1.5-flash-latest",
    "models/gemini-1.5-pro",
    "models/gemini-1.5-pro-001",
    "models/gemini-pro",
    "models/gemini-2.0-flash",
]

print("Checking specific models...")
found = []
for m in genai.list_models():
    if m.name in target_models:
        print(f"✅ Found: {m.name}")
        found.append(m.name)

print("\nModels NOT found from target list:")
for t in target_models:
    if t not in found:
        print(f"❌ Not found: {t}")
