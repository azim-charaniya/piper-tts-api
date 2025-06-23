import os
import uuid
import numpy as np
import soundfile as sf
from transformers import AutoModel

# Load model once at import time
repo_id = "ai4bharat/IndicF5"
model = AutoModel.from_pretrained(repo_id, trust_remote_code=True)

def handle_gujarati_request(data, text, format_param):
    # Synthesize audio
    audio = model(text)
    # Normalize if needed
    if hasattr(audio, "dtype") and audio.dtype == np.int16:
        audio = audio.astype(np.float32) / 32768.0

    # Prepare output file path
    out_dir = "audio_cache"
    os.makedirs(out_dir, exist_ok=True)
    file_ext = format_param if format_param in ["wav", "mp3"] else "wav"
    out_path = os.path.join(out_dir, f"gujarati_{uuid.uuid4()}.{file_ext}")

    # Save as WAV or MP3
    sample_rate = model.config.sampling_rate
    if format_param == "wav":
        sf.write(out_path, audio, sample_rate)
    elif format_param == "mp3":
        import io
        from pydub import AudioSegment
        buf = io.BytesIO()
        sf.write(buf, audio, sample_rate, format="WAV")
        buf.seek(0)
        audio_seg = AudioSegment.from_wav(buf)
        audio_seg.export(out_path, format="mp3")
    else:
        sf.write(out_path, audio, sample_rate)

    return out_path
