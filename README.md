# Piper TTS API

A self-hosted Text-to-Speech (TTS) API built using Flask and Piper TTS. This API allows you to generate speech from text, supporting multiple voices and output formats (WAV or MP3). The project is designed for ease of use, with features like caching, input validation, and error handling.

## Overview
- **Repository:** [https://github.com/azim-charaniya/piper-tts-api.git](https://github.com/azim-charaniya/piper-tts-api.git)
- **Technologies:** Python, Flask, Piper TTS, Conda for dependency management, and Docker for containerization.
- **Features:**
    - Supports 3 high-quality voices (e.g., en_us, en_gb, en_us_female).
    - Handles text up to 500 words, splitting longer texts into paragraphs.
    - API endpoint: `/tts` (POST request).
    - Caching for generated audio to improve performance.
    - Runs on port 17100.

## Prerequisites
- **Python 3.9+**: For local development.
- **Conda**: For managing dependencies (install via [anaconda.com](https://www.anaconda.com/products/individual)).
- **Docker and Docker Compose**: For containerized deployment.
- **Dependencies**: Listed in `requirements.txt` and `environment.yml`.

## Installation
1. **Clone the Repository:**
   git clone https://github.com/azim-charaniya/piper-tts-api.git
   cd piper-tts-api

2. **Set Up Dependencies (Local Development):**
- Create and activate a Conda environment:
  ```
  conda env create -f environment.yml  # Creates the environment from environment.yml
  conda activate tts-api-env
  ```
- Install any additional pip dependencies:
  ```
  pip install -r requirements.txt
  ```

3. **Download Voice Models:**
- Place voice models (e.g., `en_US-ryan-high.onnx`) in the `voices/` directory. You can download them from [github.com/rhasspy/piper](https://github.com/rhasspy/piper).

## Running the Application
### Locally
1. Activate the Conda environment:
   conda activate tts-api-env
2. Start the Flask app:
   python app.py

3. Access the API at `http://localhost:17100`.

### Using Docker Compose
1. Build and start the container:


docker-compose up --build

2. Access the API at `http://localhost:17100`.
3. Stop the container:


docker-compose down


## API Documentation
The API uses a POST endpoint at `/tts`. Send a JSON body with the following parameters:

### Request Body (JSON)
```json
{
"text": "Required. Text to synthesize (up to 500 words).",
"voice": "Required. One of: 'en_us', 'en_gb', 'en_us_female'.",
"format": "Optional. 'wav' or 'mp3' (default: 'wav').",
"speaker_id": "Optional. Speaker ID (default: 0).",
"length_scale": "Optional. Phoneme length scale (e.g., 1.0).",
"noise_scale": "Optional. Generator noise scale (e.g., 0.5).",
"noise_w": "Optional. Phoneme width noise (e.g., 0.3).",
"sentence_silence": "Optional. Seconds of silence after sentences (default: 0.0)."
}


Example cURL Requests

Use these to test the API:


    Basic Request:

curl -X POST "http://localhost:17100/tts" \
     -H "Content-Type: application/json" \
     -d '{"text": "Hello, world!", "voice": "en_us"}' \
     -o output.wav


With Additional Parameters:

curl -X POST "http://localhost:17100/tts" \
     -H "Content-Type: application/json" \
     -d '{"text": "This is a test.", "voice": "en_gb", "format": "mp3", "speaker_id": 1}' \
     -o output.mp3

Troubleshooting


    Errors with Voice Models: Ensure files are in the voices/ directory. Check logs for file not found errors.

    Port Conflicts: If port 17100 is in use, change APP_PORT in app.py.

    Conda Issues: If dependencies fail, recreate the environment with conda env update -f environment.yml.

    Docker Problems: Run docker-compose logs for details, or rebuild with docker-compose build --no-cache.


Contributing

Feel free to fork this repository and submit pull requests. For issues, create a new ticket on GitHub.

License

# MIT License. See LICENSE for details.


### Additional Notes
- **Why These Files?** The `docker-compose.yml` simplifies deployment and scaling, while the `README.md` makes your project more accessible and user-friendly, encouraging contributions.
- **Next Steps:** 
  - Commit these files to your GitHub repository.
  - Test the setup locally to ensure everything works as expected.
  - If you need further customizations (e.g., adding more services or environment variables), let me know!

This should wrap up your project setup. If you have any more questions, I'm here to help!