# engines/piper_tts.py
import io
import logging
import os
import uuid
import wave
from pathlib import Path

import pydub

# Assuming piper_tts library is installed
try:
    from piper_tts import PiperVoice

    PIPER_AVAILABLE = True
except ImportError:
    class PiperVoice:
        def __init__(*args, **kwargs):
            raise NotImplementedError("piper_tts library not found.")


    PIPER_AVAILABLE = False
    logging.warning("piper_tts library not found. The 'piper' engine will not be available.")

VOICES_DIR = os.path.join(os.getcwd(), 'voices')
CACHE_DIR = os.path.join(os.getcwd(), 'cache')
os.makedirs(VOICES_DIR, exist_ok=True)
os.makedirs(CACHE_DIR, exist_ok=True)

AVAILABLE_PIPER_VOICES = {
    'en_us': os.path.join(VOICES_DIR, 'en_US-ryan-high.onnx'),
    'en_gb': os.path.join(VOICES_DIR, 'en_GB-cori-high.onnx'),
    'en_us_female': os.path.join(VOICES_DIR, 'en_US-lessac-high'),
}


def load_piper_voice(voice_key):
    """Load the PiperVoice model."""
    if not PIPER_AVAILABLE:
        raise NotImplementedError("piper_tts library is not installed or available.")

    if voice_key not in AVAILABLE_PIPER_VOICES:
        raise ValueError(f"Piper voice '{voice_key}' is not available. Choices: {list(AVAILABLE_PIPER_VOICES.keys())}")
    model_path = Path(AVAILABLE_PIPER_VOICES[voice_key])
    config_path = None
    if not model_path.exists():
        raise FileNotFoundError(f"Model file not found for Piper voice '{voice_key}': {model_path}")

    return PiperVoice.load(str(model_path), config_path=config_path, use_cuda=False)


def generate_audio_piper(text, voice_key, format='wav', speaker_id=0, length_scale=None, noise_scale=None, noise_w=None,
                         sentence_silence=0.0):
    """Generate audio from text using Piper TTS."""
    logging.info(f"Generating audio with Piper TTS. Voice: {voice_key}, Format: {format}")
    voice_instance = load_piper_voice(voice_key)

    synthesize_args = {
        "speaker_id": speaker_id,
        "length_scale": length_scale,
        "noise_scale": noise_scale,
        "noise_w": noise_w,
        "sentence_silence": sentence_silence,
    }

    audio_buffer = io.BytesIO()
    try:
        with wave.open(audio_buffer, 'wb') as wav_file:
            voice_instance.synthesize(text, wav_file, **{k: v for k, v in synthesize_args.items() if v is not None})
        audio_buffer.seek(0)
        audio_data = audio_buffer.read()

        if format == 'mp3':
            audio_segment = pydub.AudioSegment.from_wav(io.BytesIO(audio_data))
            audio_buffer = io.BytesIO()
            audio_segment.export(audio_buffer, format='mp3')
            audio_buffer.seek(0)
            audio_data = audio_buffer.read()
    except Exception as e:
        logging.error(f"Error during Piper synthesis or conversion: {e}")
        raise

    audio_file_path = os.path.join(CACHE_DIR, f"{str(uuid.uuid4())}.{format}")
    with open(audio_file_path, 'wb') as audio_file:
        audio_file.write(audio_data)
    logging.info(f"Piper audio generated and saved to {audio_file_path}")
    return audio_file_path


def generate_audio_by_splitting_piper(text, voice_key, format_param, speaker_id, length_scale, noise_scale, noise_w,
                                      sentence_silence):
    """Splits long text for Piper TTS and combines the resulting audio."""
    if not PIPER_AVAILABLE:
        raise NotImplementedError("piper_tts library is not installed or available.")

    logging.info("Piper: Text exceeds limit; splitting into chunks.")
    words = text.split()
    paragraphs = []
    current_paragraph_words = []
    for word in words:
        current_paragraph_words.append(word)
        if len(current_paragraph_words) >= 450 and word.endswith(('.', '!', '?')):
            paragraphs.append(' '.join(current_paragraph_words))
            current_paragraph_words = []
        elif len(current_paragraph_words) >= 500:
            paragraphs.append(' '.join(current_paragraph_words))
            current_paragraph_words = []
    if current_paragraph_words:
        paragraphs.append(' '.join(current_paragraph_words))

    audio_segments = []
    for i, paragraph in enumerate(paragraphs):
        try:
            audio_file_path_chunk = generate_audio_piper(paragraph, voice_key, 'wav', speaker_id, length_scale,
                                                         noise_scale, noise_w,
                                                         sentence_silence if i < len(paragraphs) - 1 else 0.0)
            audio_segment = pydub.AudioSegment.from_file(audio_file_path_chunk)
            audio_segments.append(audio_segment)
            os.remove(audio_file_path_chunk)  # Clean up
        except Exception as e:
            logging.error(f"Error generating audio for Piper chunk {i + 1}: {e}")
            raise

    combined_audio = pydub.AudioSegment.empty()
    for segment in audio_segments:
        combined_audio += segment
    combined_audio_file_path = os.path.join(CACHE_DIR, f"{str(uuid.uuid4())}.{format_param}")
    combined_audio.export(combined_audio_file_path, format=format_param)
    logging.info(f"Piper combined audio saved to {combined_audio_file_path}")
    return combined_audio_file_path


def handle_piper_request(data, text, format_param):
    """Handles logic specific to the Piper TTS engine."""
    voice_key = data.get('voice', 'en_us').strip()
    speaker_id = int(data.get('speaker_id', 0))
    length_scale = float(data.get('length_scale', None)) if data.get('length_scale') else None
    noise_scale = float(data.get('noise_scale', None)) if data.get('noise_scale') else None
    noise_w = float(data.get('noise_w', None)) if data.get('noise_w') else None
    sentence_silence = float(data.get('sentence_silence', 0.0))

    if voice_key not in AVAILABLE_PIPER_VOICES:
        raise ValueError(f"Invalid Piper voice. Available voices: {list(AVAILABLE_PIPER_VOICES.keys())}")

    if len(text.split()) > 500:
        return generate_audio_by_splitting_piper(text, voice_key, format_param, speaker_id, length_scale, noise_scale,
                                                 noise_w, sentence_silence)
    else:
        return generate_audio_piper(text, voice_key, format_param, speaker_id, length_scale, noise_scale, noise_w,
                                    sentence_silence)
