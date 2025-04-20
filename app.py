# app.py
# Updated implementation of the Text-to-Speech API using Piper TTS.
# This version adapts the CLI code from [github.com/rhasspy/piper](https://github.com/rhasspy/piper)
# to integrate with our Flask API, including options for speaker, scales, and more.
# Best practices: Input validation, error handling, logging, and caching are preserved.

import io  # For in-memory WAV handling
import logging
import os
import uuid
import wave  # From original code
from pathlib import Path  # Used in the original code for paths

import pydub  # For audio format conversion
from flask import Flask, request, send_file, jsonify

from piper_tts import PiperVoice  # Assuming this is from the piper-tts library; adjust if needed

# Configuration settings
APP_PORT = 17100
VOICES_DIR = os.path.join(os.getcwd(), 'voices')
CACHE_DIR = os.path.join(os.getcwd(), 'cache')
os.makedirs(VOICES_DIR, exist_ok=True)


# Available voices (as before, from [github.com/rhasspy/piper/blob/master/VOICES.md](https://github.com/rhasspy/piper/blob/master/VOICES.md))
AVAILABLE_VOICES = {'en_us': os.path.join(VOICES_DIR, 'en_US-ryan-high.onnx'),
    'en_gb': os.path.join(VOICES_DIR, 'en_GB-cori-high.onnx'),
    'en_us_female': os.path.join(VOICES_DIR, 'en_US-lessac-high'), }

pipeline = None
app = Flask(__name__)
logging.basicConfig(level=logging.CRITICAL)

def clear_audio_cache():
    """Clearing cache directory when file is older than 1 day."""
    for filename in os.listdir(CACHE_DIR):
        file_path = os.path.join(CACHE_DIR, filename)
        if os.path.isfile(file_path):
            file_age = os.path.getmtime(file_path)
            if (os.path.getmtime(file_path) - file_age) > 86400:  # 1 day in seconds
                os.remove(file_path)


def load_tts_model(voice):
    """Load the PiperVoice model, adapted from [github.com/rhasspy/piper](https://github.com/rhasspy/piper).

    Args:
        voice (str): The key of the voice from AVAILABLE_VOICES.

    Returns:
        PiperVoice: Loaded voice instance.

    Raises:
        ValueError: If the voice is invalid or the file is missing.
    """
    if voice not in AVAILABLE_VOICES:
        raise ValueError(f"Voice '{voice}' is not available. Choices: {list(AVAILABLE_VOICES.keys())}")
    model_path = Path(AVAILABLE_VOICES[voice])  # Use Path from original code
    config_path = None  # You can extend this to pass a config file if needed
    if not model_path.exists():
        raise FileNotFoundError(f"Model file not found: {model_path}")

    return PiperVoice.load(str(model_path), config_path=config_path, use_cuda=False)


def generate_audio(text, voice, format='wav', speaker_id=0, length_scale=None, noise_scale=None, noise_w=None,
                   sentence_silence=0.0):
    """Generate audio from text, adapted from the synthesis logic in [github.com/rhasspy/piper](https://github.com/rhasspy/piper).

    Args:
        text (str): The text to synthesize.
        voice (str): The voice to use.
        format (str): Output format ('wav' or 'mp3', default 'wav').
        speaker_id (int): Speaker ID (default: 0).
        length_scale (float): Phoneme length scale (optional).
        noise_scale (float): Generator noise scale (optional).
        noise_w (float): Phoneme width noise (optional).
        sentence_silence (float): Seconds of silence after each sentence (default: 0.0).

    Returns:
        path: The generated audio as file path.
    """
    try:
        # Print debug information
        logging.info(f"Generating audio with text: {text}, voice: {voice}, format: {format}, ")
        voice_instance = load_tts_model(voice)
        synthesize_args = {"speaker_id": speaker_id, "length_scale": length_scale, "noise_scale": noise_scale,
                           "noise_w": noise_w, "sentence_silence": sentence_silence, }

        # Synthesize audio (adapted from original code to return bytes)
        audio_buffer = io.BytesIO()  # In-memory buffer for WAV
        with wave.open(audio_buffer, 'wb') as wav_file:
            voice_instance.synthesize(text, wav_file, **{k: v for k, v in synthesize_args.items() if v is not None})

        audio_buffer.seek(0)  # Reset buffer position
        audio_data = audio_buffer.read()  # Get WAV bytes

        if format == 'mp3':
            audio_segment = pydub.AudioSegment.from_wav(audio_data)
            audio_data = audio_segment.export(format='mp3').read()  # Convert to MP3 bytes

        # Write to a temporary file using uuid and cache
        audio_file_path = os.path.join(CACHE_DIR, f"{str(uuid.uuid4())}.{format}")
        with open(audio_file_path, 'wb') as audio_file:
            audio_file.write(audio_data)
        audio_file.close()
        # Return the path to the audio file
        logging.info(f"Audio generated and saved to {audio_file_path}")
        del audio_buffer  # Clean up the buffer

        return audio_file_path
    except Exception as e:
        logging.error(f"Error generating audio: {str(e)}")
        raise


@app.route('/tts', methods=['POST'])
def tts_endpoint():
    """TTS API Endpoint (now using POST).

    Request Body (JSON):
        {
            "text": "Required. Text to synthesize (max 500 characters).",
            "voice": "Required. One of the 5 voices.",
            "format": "Optional. 'wav' or 'mp3' (default: 'wav').",
            "speaker_id": "Optional. Speaker ID (default: 0).",
            "length_scale": "Optional. Phoneme length scale.",
            "noise_scale": "Optional. Generator noise scale.",
            "noise_w": "Optional. Phoneme width noise.",
            "sentence_silence": "Optional. Seconds of silence after sentences (default: 0.0).",
        }

    Returns:
        Audio file as a downloadable response, or a JSON error.
    """
    try:
        data = request.json  # Changed to request.json for POST body
        text = data.get('text', '').strip()
        voice = data.get('voice', '').strip()
        format_param = data.get('format', 'wav').lower()
        speaker_id = int(data.get('speaker_id', 0))
        length_scale = float(data.get('length_scale', None)) if data.get('length_scale') is not None else None
        noise_scale = float(data.get('noise_scale', None)) if data.get('noise_scale') is not None else None
        noise_w = float(data.get('noise_w', None)) if data.get('noise_w') is not None else None
        sentence_silence = float(data.get('sentence_silence', 0.0))

        if not text:
            return jsonify({"error": "Text is required."}), 400
        if not voice:
            voice = "en_us"
        if voice not in AVAILABLE_VOICES:
            return jsonify({"error": f"Invalid voice. Available voices: {list(AVAILABLE_VOICES.keys())}"}), 400
        if format_param not in ['wav', 'mp3']:
            return jsonify({"error": "Invalid format. Use 'wav' or 'mp3'."}), 400

        audio_file_path = None

        words = text.split()  # Split by spaces to count words
        if len(words) > 500:
            audio_file_path = generate_audio_by_splitting(format_param, length_scale, noise_scale, noise_w,
                                                          sentence_silence, speaker_id, voice, words)

        else:

            logging.info("Generating audio with parameters:")
            audio_file_path = generate_audio(text, voice, format_param, speaker_id, length_scale, noise_scale, noise_w,
                                             sentence_silence)
            logging.info("Audio generation complete.")
        audio_uuid_file_name = 'output' + str(uuid.uuid4())

        if audio_file_path:
            return send_file(audio_file_path, mimetype=f'audio/{format_param}', as_attachment=True,
                             download_name=f'{audio_uuid_file_name}.{format_param}')
        else:
            return jsonify({"error": "Audio generation failed."}), 500
    except Exception as e:  # Added try-except for JSON parsing errors
        return jsonify({"error": f"Invalid JSON or failed to process: {str(e)}"}), 400  # More specific error handling


def generate_audio_by_splitting(format_param, length_scale, noise_scale, noise_w, sentence_silence, speaker_id,
                                voice, words):
    logging.info("Text exceeds 500 words; splitting into paragraphs.")
    paragraphs = []
    # Split text into paragraphs of 500 words closes to paragraphs end
    current_paragraph = []
    for word in words:
        current_paragraph.append(word)
        if len(current_paragraph) >= 500:
            paragraphs.append(' '.join(current_paragraph))
            current_paragraph = []
    if current_paragraph:
        paragraphs.append(' '.join(current_paragraph))
    # Generate audio for each paragraph
    logging.info(f"Splitting text into {len(paragraphs)} paragraphs.")
    audio_files = []
    for paragraph in paragraphs:
        audio_file_path = generate_audio(paragraph, voice, format_param, speaker_id, length_scale, noise_scale,
                                         noise_w, sentence_silence)
        audio_files.append(audio_file_path)
    # Combine audio files into one
    logging.info(f"Combining {len(audio_files)} audio files.")
    combined_audio = pydub.AudioSegment.empty()
    for audio_file in audio_files:
        audio_segment = pydub.AudioSegment.from_file(audio_file)
        combined_audio += audio_segment
    # Save combined audio
    combined_audio_file_path = os.path.join(CACHE_DIR, f"{str(uuid.uuid4())}.{format_param}")
    combined_audio.export(combined_audio_file_path, format=format_param)
    return combined_audio_file_path


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=APP_PORT, debug=True)
