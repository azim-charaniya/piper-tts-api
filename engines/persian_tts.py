import os
import uuid
import torch
from transformers import VitsModel, AutoTokenizer
import scipy.io.wavfile
import io
from pydub import AudioSegment


def handle_persian_request(data, text, format_param):
    # Load the VITS model and tokenizer
    model = VitsModel.from_pretrained("SeyedAli/Persian-Speech-synthesis")
    tokenizer = AutoTokenizer.from_pretrained("SeyedAli/Persian-Speech-synthesis")

    # Tokenize input text
    inputs = tokenizer(text, return_tensors="pt")
    # Generate waveform
    with torch.no_grad():
        output = model(**inputs).waveform
    # Prepare output file path
    out_dir = "audio_cache"
    os.makedirs(out_dir, exist_ok=True)
    file_ext = format_param if format_param in ["wav", "mp3"] else "wav"
    out_path = os.path.join(out_dir, f"persian_{uuid.uuid4()}.{file_ext}")

    # Save as WAV or MP3
    wav_data = output.squeeze().cpu().numpy()
    sample_rate = model.config.sampling_rate

    if format_param == "wav":
        scipy.io.wavfile.write(out_path, rate=sample_rate, data=wav_data)
    elif format_param == "mp3":
        # Write to a BytesIO buffer as WAV, then convert to MP3
        buf = io.BytesIO()
        scipy.io.wavfile.write(buf, rate=sample_rate, data=wav_data)
        buf.seek(0)
        audio = AudioSegment.from_wav(buf)
        audio.export(out_path, format="mp3")
    else:
        # Default to WAV if unknown format
        scipy.io.wavfile.write(out_path, rate=sample_rate, data=wav_data)

    return out_path
