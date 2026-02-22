import os
import httpx
import logging
from typing import Optional

logger = logging.getLogger(__name__)

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
# Default to a friendly voice ID if not provided
VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM") 

async def synthesize_speech(text: str) -> Optional[bytes]:
    """
    Synthesizes text into speech using ElevenLabs API.
    Returns audio bytes if successful, None otherwise.
    """
    if not ELEVENLABS_API_KEY:
        logger.warning("ELEVENLABS_API_KEY not set. Skipping voice synthesis.")
        return None

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}"
    
    headers = {
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
        "xi-api-key": ELEVENLABS_API_KEY
    }
    
    data = {
        "text": text,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.5
        }
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=data, headers=headers)
            if response.status_code == 200:
                return response.content
            else:
                logger.error(f"ElevenLabs error: {response.status_code} - {response.text}")
                return None
    except Exception as e:
        logger.error(f"Error during voice synthesis: {e}")
        return None
