# app.py
# Refactored implementation of the Text-to-Speech API with Piper TTS and Google Cloud TTS.
# Engine-specific logic is moved into separate handler functions.
# Authentication, input validation, error handling, logging, and caching are preserved.

import io  # For in-memory WAV handling
import logging
import os
import time  # Added for proper cache clearing
import uuid
import wave  # From original code
from pathlib import Path  # Used in the original code for paths

import pydub  # For audio format conversion
from flask import Flask, request, send_file, jsonify
from google.api_core import exceptions as google_exceptions  # For specific Google API errors
# --- Google Cloud TTS Imports ---
from google.cloud import texttospeech

# Assuming this is from the piper-tts library; adjust if needed
try:
    from piper_tts import PiperVoice

    PIPER_AVAILABLE = True
except ImportError:
    # Provide a dummy class or flag availability if piper_tts is not installed
    class PiperVoice:
        @staticmethod
        def load(*args, **kwargs):
            raise NotImplementedError("piper_tts library not found. Cannot use 'piper' engine.")

        def synthesize(self, *args, **kwargs):
            raise NotImplementedError("piper_tts library not found. Cannot use 'piper' engine.")


    PIPER_AVAILABLE = False
    logging.warning("piper_tts library not found. The 'piper' engine will not be available.")

# Configuration settings
APP_PORT = 17100
VOICES_DIR = os.path.join(os.getcwd(), 'voices')
CACHE_DIR = os.path.join(os.getcwd(), 'cache')
os.makedirs(VOICES_DIR, exist_ok=True)
os.makedirs(CACHE_DIR, exist_ok=True)  # Ensure cache dir exists

# Available voices for Piper
AVAILABLE_PIPER_VOICES = {'en_us': os.path.join(VOICES_DIR, 'en_US-ryan-high.onnx'),
                          'en_gb': os.path.join(VOICES_DIR, 'en_GB-cori-high.onnx'),
                          'en_us_female': os.path.join(VOICES_DIR, 'en_US-lessac-high'), }

# Google Cloud TTS Client Initialization
# Authentication: Make sure GOOGLE_APPLICATION_CREDENTIALS environment variable
# is set to the path of your service account key file.
try:
    google_tts_client = texttospeech.TextToSpeechClient()
    GOOGLE_AVAILABLE = True
except Exception as e:
    google_tts_client = None
    GOOGLE_AVAILABLE = False
    logging.error(f"Failed to initialize Google Cloud TTS client: {e}. The 'google' engine will not be available.")

# Flask app setup
app = Flask(__name__)
logging.basicConfig(level=logging.INFO)


def clear_audio_cache():
    """Clearing cache directory when file is older than 1 day."""
    one_day_in_seconds = 86400
    current_time = time.time()
    for filename in os.listdir(CACHE_DIR):
        file_path = os.path.join(CACHE_DIR, filename)
        if os.path.isfile(file_path):
            file_mtime = os.path.getmtime(file_path)
            if (current_time - file_mtime) > one_day_in_seconds:
                try:
                    os.remove(file_path)
                    logging.info(f"Removed old cache file: {filename}")
                except OSError as e:
                    logging.error(f"Error removing cache file {filename}: {e}")


def load_piper_voice(voice_key):
    """Load the PiperVoice model, adapted from [github.com/rhasspy/piper](https://github.com/rhasspy/piper).

    Args:
        voice_key (str): The key of the voice from AVAILABLE_PIPER_VOICES.

    Returns:
        PiperVoice: Loaded voice instance.

    Raises:
        ValueError: If the voice key is invalid or the file is missing.
        NotImplementedError: If piper_tts library is not available.
    """
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
    """Generate audio from text using Piper TTS, adapted from the synthesis logic."""

    logging.info(f"Generating audio with Piper TTS. Voice: {voice_key}, Format: {format}")
    voice_instance = load_piper_voice(voice_key)  # This will raise errors if Piper is not available/configured

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
        raise  # Re-raise the exception for the handler to catch

    audio_file_path = os.path.join(CACHE_DIR, f"{str(uuid.uuid4())}.{format}")
    with open(audio_file_path, 'wb') as audio_file:
        audio_file.write(audio_data)

    logging.info(f"Piper audio generated and saved to {audio_file_path}")

    return audio_file_path


# Moved the splitting logic to a separate function, called only for Piper
def generate_audio_by_splitting_piper(text, voice_key, format_param, speaker_id, length_scale, noise_scale, noise_w,
                                      sentence_silence):
    """Splits long text for Piper TTS and combines the resulting audio."""
    if not PIPER_AVAILABLE:
        raise NotImplementedError("piper_tts library is not installed or available to handle splitting.")

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

    if not paragraphs:
        return None  # Should ideally be caught by initial text validation

    logging.info(f"Piper: Splitting text into {len(paragraphs)} chunks.")
    audio_segments = []
    for i, paragraph in enumerate(paragraphs):
        try:
            # Generate WAV chunks for easier merging
            audio_file_path_chunk = generate_audio_piper(paragraph, voice_key, 'wav',
                                                         speaker_id, length_scale, noise_scale, noise_w,
                                                         sentence_silence if i < len(
                                                             paragraphs) - 1 else 0.0)  # Add silence between chunks

            audio_segment = pydub.AudioSegment.from_file(audio_file_path_chunk)
            audio_segments.append(audio_segment)

            try:  # Clean up chunk file immediately
                os.remove(audio_file_path_chunk)
            except OSError as e:
                logging.warning(f"Could not remove temporary Piper chunk file {audio_file_path_chunk}: {e}")

        except Exception as e:
            logging.error(f"Error generating audio for Piper chunk {i + 1}: {e}")
            raise  # Re-raise the exception

    logging.info(f"Piper: Combining {len(audio_segments)} audio segments.")
    combined_audio = pydub.AudioSegment.empty()
    for segment in audio_segments:
        combined_audio += segment

    combined_audio_file_path = os.path.join(CACHE_DIR, f"{str(uuid.uuid4())}.{format_param}")
    combined_audio.export(combined_audio_file_path, format=format_param)

    logging.info(f"Piper combined audio saved to {combined_audio_file_path}")

    return combined_audio_file_path


def generate_audio_google(text, voice_name, format='wav', speaking_rate=1.0, pitch=0.0):
    """Generate audio from text using Google Cloud TTS."""
    if not GOOGLE_AVAILABLE or google_tts_client is None:
        raise NotImplementedError("Google Cloud TTS client is not initialized or credentials are missing.")

    logging.info(f"Generating audio with Google TTS. Voice: {voice_name}, Format: {format}")

    synthesis_input = texttospeech.SynthesisInput(text=text)

    lang_code = 'en-US'  # Default
    if voice_name and len(voice_name.split('-')) >= 2:
        lang_code = '-'.join(voice_name.split('-')[:2])
    logging.info(f"Deduced language code: {lang_code}")

    voice_params = texttospeech.VoiceSelectionParams(
        language_code=lang_code,
        name=voice_name
    )

    audio_encoding = texttospeech.AudioEncoding.LINEAR16  # Default for wav

    if format == 'mp3':
        audio_encoding = texttospeech.AudioEncoding.MP3
    elif format == 'wav':
        audio_encoding = texttospeech.AudioEncoding.LINEAR16
    else:
        raise ValueError(f"Unsupported audio format for Google TTS: {format}. Use 'wav' or 'mp3'.")

    audio_config = texttospeech.AudioConfig(
        audio_encoding=audio_encoding,
        speaking_rate=speaking_rate,
        pitch=pitch,
    )

    try:
        response = google_tts_client.synthesize_speech(
            request={"input": synthesis_input, "voice": voice_params, "audio_config": audio_config}
        )
    except google_exceptions.InvalidArgument as e:
        logging.error(f"Google API Invalid Argument Error: {e}")
        # Wrap Google API errors in a standard Exception type or re-raise
        raise ValueError(f"Google TTS API Error: Invalid argument. {e}") from e
    except google_exceptions.PermissionDenied as e:
        logging.error(f"Google API Permission Denied Error: {e}")
        raise PermissionError(
            f"Google TTS API Error: Permission denied. Check your GOOGLE_APPLICATION_CREDENTIALS.") from e
    except google_exceptions.ResourceExhausted as e:
        logging.error(f"Google API Resource Exhausted (Quota) Error: {e}")
        raise RuntimeError(f"Google TTS API Error: Quota exceeded. Try again later or check your usage limits.") from e
    except google_exceptions.GoogleAPIError as e:
        logging.error(f"General Google API Error: {e}")
        raise RuntimeError(f"Google TTS API Error: {e}") from e
    except Exception as e:
        logging.error(f"Unexpected error during Google TTS API call: {e}")
        raise  # Re-raise unknown errors

    audio_data = response.audio_content

    audio_file_path = os.path.join(CACHE_DIR, f"{str(uuid.uuid4())}.{format}")
    with open(audio_file_path, 'wb') as audio_file:
        audio_file.write(audio_data)

    logging.info(f"Google audio generated and saved to {audio_file_path}")

    return audio_file_path


def handle_piper_request(data, text, format_param):
    """Handles logic specific to the Piper TTS engine."""
    voice_key = data.get('voice', 'en_us').strip()
    speaker_id = int(data.get('speaker_id', 0))
    length_scale = float(data.get('length_scale', None)) if data.get('length_scale') is not None else None
    noise_scale = float(data.get('noise_scale', None)) if data.get('noise_scale') is not None else None
    noise_w = float(data.get('noise_w', None)) if data.get('noise_w') is not None else None
    sentence_silence = float(data.get('sentence_silence', 0.0))

    if voice_key not in AVAILABLE_PIPER_VOICES:
        raise ValueError(f"Invalid Piper voice. Available voices: {list(AVAILABLE_PIPER_VOICES.keys())}")

    words = text.split()
    if len(words) > 500:
        logging.info("Text exceeds 500 words for Piper; calling splitting handler.")
        # This function handles its own exceptions and re-raises
        return generate_audio_by_splitting_piper(text, voice_key, format_param, speaker_id, length_scale, noise_scale,
                                                 noise_w, sentence_silence)
    else:
        logging.info("Text within limit for Piper; calling direct synthesis.")
        # This function handles its own exceptions and re-raises
        return generate_audio_piper(text, voice_key, format_param, speaker_id, length_scale, noise_scale, noise_w,
                                    sentence_silence)


def handle_google_request(data, text, format_param):
    """Handles logic specific to the Google Cloud TTS engine."""
    if not GOOGLE_AVAILABLE or google_tts_client is None:
        raise NotImplementedError("Google Cloud TTS engine is not available. Check credentials and initialization.")

    google_voice_name = data.get('google_voice_name', '').strip()
    speaking_rate = float(data.get('speaking_rate', 1.0))
    pitch = float(data.get('pitch', 0.0))

    if not google_voice_name:
        # Consider defaulting or requiring this parameter
        google_voice_name = 'en-US-Standard-A'
        logging.warning(f"'google_voice_name' not provided, using default: {google_voice_name}")
        # raise ValueError("'google_voice_name' is required for Google TTS.")

    # Simple character limit check for Google (adjust based on current Google limits if needed)
    if len(text) > 5000:
        logging.warning(
            f"Text exceeds 5000 characters ({len(text)}) for Google TTS. This might fail or incur higher costs.")
        # No splitting implemented here for Google - let the API handle it or fail.

    # This function handles its own exceptions (including Google API errors) and re-raises
    return generate_audio_google(text, google_voice_name, format_param, speaking_rate, pitch)


@app.route('/tts', methods=['POST'])
def tts_endpoint():
    """TTS API Endpoint (now using POST). Routes request to appropriate engine handler.

    Request Body (JSON):
        {
            "engine": "Optional. 'piper' or 'google' (default: 'piper').",
            "text": "Required. Text to synthesize (max 500 words for Piper splitting).",
            "format": "Optional. 'wav' or 'mp3' (default: 'wav').",
            // Engine Specific Parameters:
            // If engine is 'piper':
            "voice": "Required for Piper. One of the AVAILABLE_PIPER_VOICES keys.",
            "speaker_id": "Optional. Piper speaker ID (default: 0).",
            "length_scale": "Optional. Piper phoneme length scale.",
            "noise_scale": "Optional. Piper generator noise scale.",
            "noise_w": "Optional. Piper phoneme width noise.",
            "sentence_silence": "Optional. Piper seconds of silence after sentences (default: 0.0).",
            // If engine is 'google':
            "google_voice_name": "Required for Google. A valid Google TTS voice name (e.g., 'en-US-Standard-A').",
            "speaking_rate": "Optional. Google speech rate (default: 1.0).",
            "pitch": "Optional. Google pitch (default: 0.0)."
        }

    Returns:
        Audio file as a downloadable response, or a JSON error.
    """
    # clear_audio_cache() # Consider running this in a background task instead

    try:
        data = request.json

        # --- Common Input Parsing and Validation ---
        engine = data.get('engine', 'piper').lower()
        text = data.get('text', '').strip()
        format_param = data.get('format', 'wav').lower()

        if not text:
            return jsonify({"error": "Text is required."}), 400
        if format_param not in ['wav', 'mp3']:
            return jsonify({"error": "Invalid format. Use 'wav' or 'mp3'."}), 400

        audio_file_path = None
        audio_uuid_file_name = 'output_' + str(uuid.uuid4())

        # --- Route to Engine-Specific Handlers ---
        if engine == 'piper':
            if not PIPER_AVAILABLE:
                return jsonify({"error": "Piper TTS engine is not installed or available."}), 501  # Not Implemented
            try:
                audio_file_path = handle_piper_request(data, text, format_param)
            except (ValueError, FileNotFoundError) as e:
                # Catch Piper-specific validation/config errors
                return jsonify({"error": str(e)}), 400
            except NotImplementedError as e:
                # Catch errors if load_piper_voice failed internally
                return jsonify({"error": str(e)}), 501
            except Exception as e:
                # Catch unexpected Piper generation/conversion errors
                logging.error(f"Error during Piper TTS processing: {e}")
                return jsonify({"error": "Internal server error during Piper TTS generation."}), 500

        elif engine == 'google':
            if not GOOGLE_AVAILABLE or google_tts_client is None:
                return jsonify({
                    "error": "Google Cloud TTS engine is not available. Check server configuration."}), 503  # Service Unavailable
            try:
                audio_file_path = handle_google_request(data, text, format_param)
            except ValueError as e:
                # Catch invalid argument errors from generate_audio_google (e.g. bad format)
                logging.error(f"Google TTS request error: {e}")
                return jsonify({"error": str(e)}), 400
            except PermissionError as e:
                logging.error(f"Google TTS permission error: {e}")
                return jsonify({"error": str(e)}), 403
            except RuntimeError as e:
                # Catch Google API errors (quota, general API issues)
                logging.error(f"Google TTS API runtime error: {e}")
                return jsonify({"error": str(e)}), 500
            except NotImplementedError as e:
                # Catch errors if google client wasn't available internally
                return jsonify({"error": str(e)}), 503
            except Exception as e:
                # Catch unexpected errors during Google processing
                logging.error(f"Unexpected error during Google TTS processing: {e}")
                return jsonify({"error": "Internal server error during Google TTS generation."}), 500

        else:
            # --- Invalid Engine ---
            return jsonify({"error": f"Invalid engine '{engine}'. Use 'piper' or 'google'."}), 400

        # --- Send Response ---
        if audio_file_path and os.path.exists(audio_file_path):
            # Assuming the handler function returned a valid path
            return send_file(audio_file_path, mimetype=f'audio/{format_param}', as_attachment=True,
                             download_name=f'{audio_uuid_file_name}.{format_param}')
        else:
            # This case indicates a logical error in the handler if no exception was raised
            logging.error(f"Engine handler for '{engine}' completed but did not return a valid file path.")
            return jsonify({"error": "Audio generation failed unexpectedly."}), 500

    except Exception as e:
        # Catch any unexpected errors during request parsing or initial validation
        logging.error(f"An unexpected error occurred in tts_endpoint: {e}")
        return jsonify({"error": f"An unexpected server error occurred: {str(e)}"}), 500


if __name__ == '__main__':
    logging.info("Clearing old cache files on startup...")
    clear_audio_cache()  # Clear cache on startup

    debug_mode = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'
    logging.info(f"Starting Flask app on port {APP_PORT} with debug={debug_mode}")
    # Consider running in production with a WSGI server like Gunicorn or uWSGI
    app.run(host='0.0.0.0', port=APP_PORT, debug=debug_mode)
