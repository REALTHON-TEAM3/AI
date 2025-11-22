from fastapi import FastAPI
from pydantic import BaseModel
from openai import OpenAI
import os
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

app = FastAPI()

class Input(BaseModel):
    text: str

@app.post("/process")
def process_text(data: Input):
    text = data.text

    result = client.responses.create(
        model="gpt-4.1",
        input=f"""
        사용자가 이렇게 말했다: "{text}"
        이걸 명령어로 변환해서 출력해라.
        """
    )

    return {
        "original": text,
        "command": result.output_text
    }