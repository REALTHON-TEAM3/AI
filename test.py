import sounddevice as sd
from scipy.io.wavfile import write
import soundfile as sf
import io
import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def record_audio(duration=4):
    fs = 44100
    print("🎙 녹음 시작...")
    audio = sd.rec(int(duration * fs), samplerate=fs, channels=1, dtype='int16')
    sd.wait()
    write("input.wav", fs, audio)
    print("🎤 녹음 완료!")
    return "input.wav"

def speech_to_text(path="input.wav"):
    print("📝 Whisper STT 변환 중...")
    with open(path, "rb") as f:
        transcript = client.audio.transcriptions.create(
            model="whisper-1",
            file=f
        )
    return transcript.text

def generate_response(text, system_prompt=None):
    print("🤖 LLM 응답 생성 중...")

    # 시스템 프롬프트 넣고 싶으면 여기에 추가 가능
    input_messages = text if not system_prompt else f"{system_prompt}\n{text}"

    response = client.responses.create(
        model="gpt-4o-mini",
        input=input_messages
    )
    return response.output_text

def text_to_speech(text):
    print("🔊 TTS 변환 중...")
    result = client.audio.speech.create(
        model="gpt-4o-mini-tts",
        voice="alloy",
        input=text
    )

    audio_bytes = result.read()
    audio_buffer = io.BytesIO(audio_bytes)

    data, samplerate = sf.read(audio_buffer, dtype="float32")

    sd.play(data, samplerate)
    sd.wait()

# ================================
#   🔥 Chat Loop (계속 대화)
# ================================
if __name__ == "__main__":
    print("🤖 음성 챗봇 시작!")
    print("Ctrl + C 로 종료할 수 있습니다.\n")

    system_prompt = "당신은 사용자와 자연스럽게 대화하는 친절한 음성 AI입니다."

    while True:
        # 1) 사용자 말하기
        record_audio()

        # 2) 텍스트 변환
        text = speech_to_text()
        print("👤 사용자:", text)

        # 종료 명령
        if text.lower() in ["quit", "bye", "exit", "종료", "끝내자"]:
            print("👋 대화를 종료합니다!")
            break

        # 3) AI 응답 생성
        response = generate_response(text, system_prompt=system_prompt)
        print("🤖 AI:", response)

        # 4) 응답을 음성으로 출력
        text_to_speech(response)

        print("\n--- 다음 메시지를 말하세요 ---\n")
