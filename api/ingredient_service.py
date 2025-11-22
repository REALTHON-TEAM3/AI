from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv
import os
import google.generativeai as genai
import logging
from typing import List
import json
from utils.youtube_download import recog_video
from pydantic import Field

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

load_dotenv()

GOOGLE_AI_API = os.getenv("GOOGLE_AI_API")
if not GOOGLE_AI_API:
    logger.error("GOOGLE_AI_API environment variable not found.")
else:
    logger.info("GOOGLE_AI_API key is set.")
    genai.configure(api_key=GOOGLE_AI_API)


router = APIRouter()

# --- Pydantic Models ---
class Ingredient(BaseModel):
    name: str
    quantity: str

class IngredientCategory(BaseModel):
    # Field aliases are used for mapping between the model and the JSON payload
    food_name: str = Field(alias="메뉴명")
    fruits_veggies: List[Ingredient] = Field(default_factory=list, alias="과일/채소")
    meat: List[Ingredient] = Field(default_factory=list, alias="정육")
    rice_noodles: List[Ingredient] = Field(default_factory=list, alias="쌀/면")
    seafood: List[Ingredient] = Field(default_factory=list, alias="수산물")
    sauce: List[Ingredient] = Field(default_factory=list, alias="양념/소스")
    dairy: List[Ingredient] = Field(default_factory=list, alias="우유/유제품")

    class Config:
        populate_by_name = True # Allows creating model instance with alias names

class LinkRequest(BaseModel):
    link: str

# --- API Endpoint ---
@router.post(
    "/ingredients/link",
    response_model=List[IngredientCategory],
    response_model_by_alias=True, # Use aliases in the JSON response
)
async def get_ingredients_by_link(request: LinkRequest):
    """
    Accepts a YouTube link, analyzes the video using Gemini,
    and returns a structured list of ingredients.
    """
    if not GOOGLE_AI_API:
        raise HTTPException(status_code=500, detail="Google AI API key is not configured.")

    try:
        model = genai.GenerativeModel("gemini-2.0-flash")
    except Exception as e:
        logger.error(f"Failed to initialize Gemini model: {e}")
        raise HTTPException(status_code=500, detail="Failed to initialize Gemini model.")
        
    link = request.link

    # Prompt defining the desired JSON structure for the Gemini model
    prompt = """
    주어진 요리 영상을 분석해서 필요한 재료를 아래 JSON 형식으로만, 추가 설명 없이 반환하세요.
    메뉴명은 영상의 핵심 요리 이름으로 채우세요.

    출력 형식 (예시):
    [
      {
        "메뉴명": "사과 파스타",
        "과일/채소": [{ "name": "사과", "quantity": "1/4개" }],
        "정육": [{ "name": "목살", "quantity": "1kg" }],
        "쌀/면": [{ "name": "파스타면", "quantity": "1인분" }],
        "수산물": [],
        "양념/소스": [{ "name": "돈가스소스", "quantity": "3T" }],
        "우유/유제품": []
      }
    ]

    규칙:
    - 반드시 위와 완전히 동일한 key 들만 사용하세요.
      ("메뉴명", "과일/채소", "정육", "쌀/면", "수산물", "양념/소스", "우유/유제품")
    - 각 value 는 { "name": string, "quantity": string } 객체의 배열입니다.
    - 재료명(name)은 한국어로 작성합니다.
    - 계량 정보가 없으면 quantity 에 "적당량" 또는 "약간"처럼 합리적인 값을 넣습니다.
    - 해당 카테고리에 재료가 없으면 [] (빈 배열) 로 둡니다.
    - JSON 이외의 다른 텍스트(설명, 문장, 주석, 마크다운, ``` 등)는 절대 출력하지 마세요.
    """

    # Enforce JSON output from the model
    generation_config = {"response_mime_type": "application/json"}

    try:
        logger.info(f"Processing link: {link}")
        raw_response = recog_video(prompt, link, model, generation_config)
        logger.info(f"Gemini raw output received.")
        logger.debug(f"Raw response content: {raw_response}")

        # Although we requested JSON, strip potential markdown as a safeguard.
        if raw_response.startswith("```json") and raw_response.endswith("```"):
            raw_response = raw_response[7:-3].strip()

        try:
            # Pydantic will automatically parse the JSON string and validate the structure
            data = json.loads(raw_response)
        except json.JSONDecodeError as e:
            logger.error(f"Model output is not valid JSON despite requesting it. Error: {e}")
            logger.error(f"Invalid response content: {raw_response}")
            raise HTTPException(
                status_code=500,
                detail="Gemini에서 유효한 JSON 형식이 반환되지 않았습니다.",
            )

        # The data is returned and FastAPI will validate it against the response_model
        return data
        
    except ValueError as ve:
        logger.error(f"Data processing error: {ve}")
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred: {e}",
        )