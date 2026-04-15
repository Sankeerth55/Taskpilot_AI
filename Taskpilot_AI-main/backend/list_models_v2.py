
import asyncio
import sys
import os
import google.generativeai as genai
from app.core.config import settings

# Add backend to path
sys.path.append(os.getcwd())

genai.configure(api_key=settings.gemini_api_key)

print("Listing available models...")
try:
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            print(f"Model: {m.name}")
except Exception as e:
    print(f"Error listing models: {e}")
