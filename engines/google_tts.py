# engines/google_tts.py
import logging
import os
import uuid

from google.api_core import exceptions as google_exceptions
from google.cloud import texttospeech

try:
    google_tts_client = texttospeech.TextToSpeechClient()
    GOOGLE_AVAILABLE = True
except Exception as e:
    google_tts_client = None
    GOOGLE_AVAILABLE = False
    logging.error(f"Failed to initialize Google Cloud TTS: {e}")

CACHE_DIR = os.path.join(os.getcwd(), 'cache')
os.makedirs(CACHE_DIR, exist_ok=True)


def generate_audio_google(text, voice_name, format='wav', speaking_rate=1.0, pitch=0.0):
    """Generate audio from text using Google Cloud TTS."""
    if not GOOGLE_AVAILABLE:
        raise NotImplementedError("Google Cloud TTS client is not initialized.")

    logging.info(f"Generating audio with Google TTS. Voice: {voice_name}, Format: {format}")
    synthesis_input = texttospeech.SynthesisInput(text=text)
    lang_code = 'en-US'  # Default
    if voice_name and len(voice_name.split('-')) >= 2:
        lang_code = '-'.join(voice_name.split('-')[:2])

    voice_params = texttospeech.VoiceSelectionParams(language_code=lang_code, name=voice_name)
    audio_encoding = texttospeech.AudioEncoding.LINEAR16 if format == 'wav' else texttospeech.AudioEncoding.MP3
    audio_config = texttospeech.AudioConfig(audio_encoding=audio_encoding, speaking_rate=speaking_rate, pitch=pitch)

    try:
        response = google_tts_client.synthesize_speech(input=synthesis_input, voice=voice_params,
                                                       audio_config=audio_config)
        audio_data = response.audio_content
        audio_file_path = os.path.join(CACHE_DIR, f"{str(uuid.uuid4())}.{format}")
        with open(audio_file_path, 'wb') as audio_file:
            audio_file.write(audio_data)
        logging.info(f"Google audio generated and saved to {audio_file_path}")
        return audio_file_path
    except google_exceptions.GoogleAPIError as e:
        logging.error(f"Google TTS API Error: {e}")
        raise


def handle_google_request(data, text, format_param):
    """Handles logic specific to the Google Cloud TTS engine."""
    if not GOOGLE_AVAILABLE:
        raise NotImplementedError("Google Cloud TTS engine is not available.")

    google_voice_name = data.get('google_voice_name', 'en-US-Standard-A').strip()
    speaking_rate = float(data.get('speaking_rate', 1.0))
    pitch = float(data.get('pitch', 0.0))

    if len(text) > 5000:
        logging.warning(f"Text exceeds 5000 characters for Google TTS.")

    return generate_audio_google(text, google_voice_name, format_param, speaking_rate, pitch)
