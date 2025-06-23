# app.py
import logging
import os
import uuid

from flask import Flask, request, jsonify, send_file

from engines.google_stt import handle_google_stt_request  # New for STT
from engines.google_tts import handle_google_request
# Import engine handlers
from engines.piper_tts import handle_piper_request
from engines.persian_tts import handle_persian_request  # <-- Add this import
from engines.facebook_tts import handle_facebook_request  # <-- Add this import
#from engines.gujarati_tts import handle_gujarati_request  # <-- Add this import
from utils import clear_audio_cache  # Shared utility

# Flask app setup
app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# Configuration
APP_PORT = 17100
debug_mode =  True #os.getenv('FLASK_DEBUG', 'false').lower() == 'true'
logging.info(f"Starting Flask app on port {APP_PORT} with debug={debug_mode}")

# Clear cache on startup
clear_audio_cache()


@app.route('/tts', methods=['POST'])
def tts_endpoint():
    """TTS API Endpoint. Routes to the appropriate TTS engine handler."""
    try:
        data = request.json
        engine = data.get('engine', 'piper').lower()
        text = data.get('text', '').strip()
        format_param = data.get('format', 'wav').lower()

        if not text:
            return jsonify({"error": "Text is required."}), 400
        if format_param not in ['wav', 'mp3']:
            return jsonify({"error": "Invalid format. Use 'wav' or 'mp3'."}), 400

        if engine == 'piper':
            audio_file_path = handle_piper_request(data, text, format_param)
            return send_file(audio_file_path, mimetype=f'audio/{format_param}', as_attachment=True,
                             download_name=f'output_{uuid.uuid4()}.{format_param}')

        elif engine == 'google':
            audio_file_path = handle_google_request(data, text, format_param)
            return send_file(audio_file_path, mimetype=f'audio/{format_param}', as_attachment=True,
                             download_name=f'output_{uuid.uuid4()}.{format_param}')

        elif engine == 'persian':  # New Persian TTS engine
            audio_file_path = handle_persian_request(data, text, format_param)
            return send_file(audio_file_path, mimetype=f'audio/{format_param}', as_attachment=True,
                             download_name=f'output_{uuid.uuid4()}.{format_param}')

        elif engine == 'facebook':  # Facebook TTS engine
            audio_file_path = handle_facebook_request(data, text, format_param)
            return send_file(audio_file_path, mimetype=f'audio/{format_param}', as_attachment=True,
                             download_name=f'output_{uuid.uuid4()}.{format_param}')

      #  elif engine == 'gujarati':  # Gujarati TTS engine
      #      audio_file_path = handle_gujarati_request(data, text, format_param)
      #      return send_file(audio_file_path, mimetype=f'audio/{format_param}', as_attachment=True,
      #                       download_name=f'output_{uuid.uuid4()}.{format_param}')

        else:
            return jsonify({"error": f"Invalid engine '{engine}'. Use 'piper', 'google', 'persian', 'facebook', or 'gujarati'."}), 400

    except Exception as e:
        logging.error(f"Error in TTS endpoint: {e}")
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500


@app.route('/stt', methods=['POST'])
def stt_endpoint():
    """STT API Endpoint. Routes to the Google STT handler."""
    try:
        logging.info("Received STT request.")
        # Get form data
        data = request.form  # Expect form data with audio details
        audio_file = request.files.get('audio')  # Expect an audio file in the request
        language_code = data.get('language_code', 'en-US')  # Default to en-US
        sample_rate_hertz = int(data.get('sample_rate_hertz', 16000))  # Default sample rate

        if not audio_file:
            return jsonify({"error": "Audio file is required."}), 400
        if audio_file.filename.split('.')[-1].lower() not in ['wav', 'mp3']:
            return jsonify({"error": "Unsupported audio format. Use 'wav' or 'mp3'."}), 400

        transcription = handle_google_stt_request(audio_file, language_code, sample_rate_hertz)
        return jsonify({"transcription": transcription}), 200  # Return transcribed text as JSON

    except Exception as e:
        logging.error(f"Error in STT endpoint: {e}")
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=APP_PORT, debug=debug_mode)

