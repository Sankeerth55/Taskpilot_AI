
import asyncio
import sys
import os
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add backend to path
sys.path.append(os.getcwd())

from app.core.config import settings
from app.services.ai.gemini import GeminiProvider

async def test_gemini():
    print(f"Testing Gemini Provider...")
    print(f"API Key from settings: {settings.gemini_api_key[:5]}... (len={len(settings.gemini_api_key)})")
    
    # Use standard provider initialization which now reads from settings
    # Explicitly pass key if needed, or rely on internal logic. 
    # factory.py does: return GeminiProvider(api_key=api_key or None)
    # let's map that here to simulate real usage
    provider = GeminiProvider(api_key=settings.gemini_api_key)

    
    prompt = "Hello, are you working?"
    print(f"Sending prompt: '{prompt}'")
    
    try:
        response = await provider.generate(prompt)
        print(f"Response: '{response}'")
        
        if response:
            print("✅ Gemini API is WORKING")
        else:
            print("❌ Gemini API returned EMPTY string")
            
    except Exception as e:
        print(f"❌ Exception during generation: {e}")

if __name__ == "__main__":
    asyncio.run(test_gemini())
