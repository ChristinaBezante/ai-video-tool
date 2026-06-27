import os
from huggingface_hub import InferenceClient
from dotenv import load_dotenv

load_dotenv()

whisper_token = os.getenv("HF_TOKEN")

client = InferenceClient(
    provider="fal-ai",
    api_key=whisper_token,
)

def transcribe_audio(audio_path: str):
    output = client.automatic_speech_recognition(
        audio_path,
        model="openai/whisper-large-v3",
        extra_body={
            "return_timestamps": True
        }
    )

    return output