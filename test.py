import sounddevice as sd
from scipy.io.wavfile import write
import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))  # 무료 키 가능

def record_audio():
    fs = 44100  
    duration = 4  # 녹음 길이(초)
    print("🎙 녹음 시작...")
    audio = sd.rec(int(duration * fs), samplerate=fs, channels=1, dtype='int16')
    sd.wait()
    write("input.wav", fs, audio)
    print("🎤 녹음 완료! -> input.wav 저장됨")

def speech_to_text():
    print("📝 Whisper STT 변환 중...")
    with open("input.wav", "rb") as f:
        transcript = client.audio.transcriptions.create(
            model="whisper-1",
            file=f
        )
    return transcript.text

def generate_response(text):
    print("🤖 LLM 응답 생성 중...")
    response = client.responses.create(
        model="gpt-4o-mini",  # 무료로 사용 가능한 경량 LLM
        input=text
    )
    return response.output_text

if __name__ == "__main__":
    record_audio()

    text = speech_to_text()
    print("📝 인식된 문장:", text)

    response = generate_response(text)
    print("🤖 모델 응답:", response)
