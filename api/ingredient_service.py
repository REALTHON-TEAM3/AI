# ingredients.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List
import google.generativeai as generativeai
import logging, os, json
from dotenv import load_dotenv
from utils.youtube_download import recog_video

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

load_dotenv()

GOOGLE_AI_API = os.getenv("GOOGLE_AI_API")
if not GOOGLE_AI_API:
    logger.error("GOOGLE_AI_API environment variable not found.")
else:
    logger.info("GOOGLE_AI_API key is set.")
    generativeai.configure(api_key=GOOGLE_AI_API)

# 🔹 여기서는 FastAPI 말고 APIRouter 사용
router = APIRouter(
    prefix="/ingredients",
    tags=["ingredients"],
)

# --- Pydantic Models ---
class Ingredient(BaseModel):
    name: str
    quantity: str

class IngredientCategory(BaseModel):
    food_name: str = Field(alias="메뉴명")
    fruits_veggies: List[Ingredient] = Field(default_factory=list, alias="과일/채소")
    meat: List[Ingredient] = Field(default_factory=list, alias="정육")
    rice_noodles: List[Ingredient] = Field(default_factory=list, alias="쌀/면")
    seafood: List[Ingredient] = Field(default_factory=list, alias="수산물")
    sauce: List[Ingredient] = Field(default_factory=list, alias="양념/소스")
    dairy: List[Ingredient] = Field(default_factory=list, alias="우유/유제품")

    class Config:
        validate_by_name = True

class LinkRequest(BaseModel):
    link: str

class FoodRequest(BaseModel):
    food_name: str

class IngredientsResponse(BaseModel):
    ingredients: List[IngredientCategory]

@router.post(
    "/menu",
    response_model=IngredientsResponse,
    response_model_by_alias=True,
)
async def get_ingredients_by_menu(request: FoodRequest):
    """
    사용자가 보낸 메뉴명을 기반으로 Gemini에게 재료 목록을 요청하고,
    IngredientResponse 형식에 맞춰 반환합니다.
    """
    if not GOOGLE_AI_API:
        raise HTTPException(status_code=500, detail="Google AI API key is not configured.")

    try:
        model = generativeai.GenerativeModel("gemini-2.0-flash")
    except Exception as e:
        logger.error(f"Failed to initialize Gemini model: {e}")
        raise HTTPException(status_code=500, detail="Failed to initialize Gemini model.")

    menu_name = request.food_name

    # 🔹 IngredientResponse 형식을 "강하게" 강제하는 프롬프트
    prompt = f"""
    당신은 자취생 요리 재료 추천 도우미입니다.

    사용자가 요리 이름을 주면, 그 요리를 만들기 위한 재료를
    아래 JSON 형식으로만, 추가 설명 없이 반환하세요.

    사용자가 보낸 메뉴명: "{menu_name}"

    반환 형식(JSON 예시):

    {{
      "ingredients": [
        {{
          "메뉴명": "{menu_name}",
          "과일/채소": [{{ "name": "양파", "quantity": "1/2개" }}],
          "정육": [],
          "쌀/면": [],
          "수산물": [],
          "양념/소스": [],
          "우유/유제품": []
        }}
      ]
    }}

    규칙:
    - 반드시 위와 완전히 동일한 key 들만 사용하세요.
      ("ingredients", "메뉴명", "과일/채소", "정육", "쌀/면", "수산물", "양념/소스", "우유/유제품")
    - "ingredients" 값은 하나 이상의 객체를 가진 배열입니다.
    - 각 재료 카테고리 값은 {{ "name": string, "quantity": string }} 형태의 객체 배열입니다.
    - 재료명(name)은 한국어로 작성합니다.
    - 계량 정보가 없으면 quantity 에 "적당량" 또는 "약간"처럼 합리적인 값을 넣습니다.
    - 해당 카테고리에 재료가 없으면 [] (빈 배열) 로 둡니다.
    - "메뉴명" 필드는 반드시 사용자가 보낸 메뉴명("{menu_name}")을 그대로 사용하세요.
    - JSON 이외의 다른 텍스트(설명, 문장, 주석, 마크다운, ``` 등)는 절대 출력하지 마세요.
    """

    generation_config = {"response_mime_type": "application/json"}

    try:
        logger.info(f"Generating ingredients for menu: {menu_name}")
        result = model.generate_content(
            prompt,
            generation_config=generation_config,
        )

        raw_response = result.text or ""
        logger.info("Gemini raw output received for /menu.")
        logger.debug(f"Raw response content: {raw_response}")

        # 혹시라도 ```json ... ``` 형태로 줄 경우 대비
        if raw_response.startswith("```json"):
            raw_response = raw_response.strip()
            if raw_response.endswith("```"):
                raw_response = raw_response[7:-3].strip()

        try:
            data = json.loads(raw_response)
        except json.JSONDecodeError as e:
            logger.error(f"Model output is not valid JSON despite requesting it. Error: {e}")
            logger.error(f"Invalid response content: {raw_response}")
            raise HTTPException(
                status_code=500,
                detail="Gemini에서 유효한 JSON 형식이 반환되지 않았습니다.",
            )

        # 🔹 Pydantic으로 한 번 더 검증해서 IngredientResponse 형식 보장
        try:
            ingredients_response = IngredientsResponse(**data)
        except ValidationError as e:
            logger.error(f"Pydantic validation error for IngredientsResponse: {e}")
            raise HTTPException(
                status_code=500,
                detail="모델 응답이 IngredientResponse 형식과 일치하지 않습니다.",
            )

        return ingredients_response

    except ValueError as ve:
        logger.error(f"Data processing error: {ve}")
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"An unexpected error occurred in /menu: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred: {e}",
        )

@router.post(
    "/link",
    response_model=List[IngredientCategory],
    response_model_by_alias=True,
)
async def get_ingredients_by_link(request: LinkRequest):
    if not GOOGLE_AI_API:
        raise HTTPException(status_code=500, detail="Google AI API key is not configured.")

    try:
        model = generativeai.GenerativeModel("gemini-2.0-flash")
    except Exception as e:
        logger.error(f"Failed to initialize Gemini model: {e}")
        raise HTTPException(status_code=500, detail="Failed to initialize Gemini model.")
        
    link = request.link

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

    generation_config = {"response_mime_type": "application/json"}

    try:
        logger.info(f"Processing link: {link}")
        raw_response = recog_video(prompt, link, model, generation_config)
        logger.info(f"Gemini raw output received.")
        logger.debug(f"Raw response content: {raw_response}")

        if raw_response.startswith("```json") and raw_response.endswith("```"):
            raw_response = raw_response[7:-3].strip()

        try:
            data = json.loads(raw_response)
        except json.JSONDecodeError as e:
            logger.error(f"Model output is not valid JSON despite requesting it. Error: {e}")
            logger.error(f"Invalid response content: {raw_response}")
            raise HTTPException(
                status_code=500,
                detail="Gemini에서 유효한 JSON 형식이 반환되지 않았습니다.",
            )

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
