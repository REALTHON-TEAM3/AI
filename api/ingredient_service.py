from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv
import os
import google.genai as genai
import logging
from typing import List
import json
from utils.parse_ingredients import parse_ingredients_from_gemini_response

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
logger.info(f"GEMINI_API_KEY is {'set' if GEMINI_API_KEY else 'not set'}.")

router = APIRouter()

class Ingredient(BaseModel):
    name: str
    quantity: str

class IngredientsResponse(BaseModel):
    ingredients: List[Ingredient]

class FoodRequest(BaseModel):
    food_name: str

class LinkRequest(BaseModel):
    link: str

class LinkResponse(BaseModel):
    ingredients: List[Ingredient]

@router.post("/ingredients/menu", response_model=IngredientsResponse)
async def get_ingredients_by_menu(request: FoodRequest):
    """
    음식 이름을 받아 Gemini API를 사용하여 해당 음식의 재료 목록만 반환합니다.
    """
    if not GEMINI_API_KEY:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY가 설정되지 않았습니다.")

    food_name = request.food_name

    prompt = (
        f"음식 이름 '{food_name}'에 대한 재료 목록을 JSON 형식으로 알려주세요. "
        f"각 재료는 'name'(문자열)과 'quantity'(문자열) 키를 가져야 합니다. "
        f"예시: {{\"ingredients\": [{{\"name\": \"김치\", \"quantity\": \"200g\"}}, "
        f"{{\"name\": \"돼지고기\", \"quantity\": \"100g\"}}]}} "
        f"다른 설명, 마크다운, 코드블록 없이 오직 JSON 객체만 포함해주세요."
    )

    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        logger.debug(f"Calling Gemini API for: {food_name}")
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )
        logger.info(f"Gemini API raw response received.")

        data = parse_ingredients_from_gemini_response(response)

        return data

    except ValueError as ve:
        logger.error(f"Data processing error: {ve}")
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"An unexpected error occurred during Gemini API call: {e}")
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred during Gemini API call: {e}")

@router.post("/ingredients/link", response_model=str)
async def get_ingredients_by_link(request: LinkRequest):
    """
    링크를 받아 Gemini API를 사용하여 해당 음식의 재료 목록만 반환합니다.
    """
    link = request.link

    prompt = (
        f"링크 '{link}'는 항상 유트브 영상 공유 링크이고 이 유튜브 영상 대한 설명을 무조건 텍스트 형식으로 알려주세요. "
        # f"각 재료는 'name'(문자열)과 'quantity'(문자열) 키를 가져야 합니다. "
        # f"예시: {{\"ingredients\": [{{\"name\": \"김치\", \"quantity\": \"200g\"}}, "
        # f"{{\"name\": \"돼지고기\", \"quantity\": \"100g\"}}]}} "
        # f"다른 설명, 마크다운, 코드블록 없이 오직 JSON 객체만 포함해주세요."
    )

    try:   
        client = genai.Client(api_key=GEMINI_API_KEY)
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )
        logger.info(f"Gemini API raw response received.")
        # data = parse_ingredients_from_gemini_response(response)

        return response.text
    except ValueError as ve:
        logger.error(f"Data processing error: {ve}")
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"An unexpected error occurred during Gemini API call: {e}")
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred during Gemini API call: {e}")