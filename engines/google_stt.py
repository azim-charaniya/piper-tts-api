# engines/google_stt.py
import io
import logging
from google.cloud import speech_v1 as speech

try:
    speech_client = speech.SpeechClient()
    STT_AVAILABLE = True
except Exception as e:
    speech_client = None
    STT_AVAILABLE = False
    logging.error(f"Failed to initialize Google Cloud STT: {e}")

def handle_google_stt_request(audio_file, language_code='en-US', sample_rate_hertz=16000):
    """Handle speech-to-text using Google Cloud STT."""
    if not STT_AVAILABLE:
        raise NotImplementedError("Google Cloud STT is not available. Check credentials.")

    audio_content = audio_file.read()
    audio = speech.RecognitionAudio(content=audio_content)
    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,  # Adjust based on input file
        sample_rate_hertz=sample_rate_hertz,
        language_code=language_code,
    )

    try:
        response = speech_client.recognize(config=config, audio=audio)
        transcription = ' '.join([result.alternatives[0].transcript for result in response.results])
        return transcription
    except Exception as e:
        logging.error(f"STT Error: {e}")
        raise
