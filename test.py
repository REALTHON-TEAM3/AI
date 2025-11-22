from dotenv import load_dotenv
import os
from openai import OpenAI

load_dotenv()

client = OpenAI(api_key="OPENAI_API_KEY")  # <- 본인 키 넣기

audio_file_path = "input.wav"  # mp3, m4a 등도 가능

with open(audio_file_path, "rb") as f:
    transcript = client.audio.transcriptions.create(
        model="whisper-1",   # 또는 gpt-4o-mini-transcribe
        file=f,
        # language="ko",     # 한국어라고 명시해도 됨 (선택)
    )

print("인식된 텍스트:")
print(transcript.text)