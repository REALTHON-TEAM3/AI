from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import google.generativeai as genai
import json
import os
from dotenv import load_dotenv

load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
genai.configure(api_key=GOOGLE_API_KEY)

# 검색 도구 없이 일반 모델 사용 (API 호환성 문제로 인해)
model = genai.GenerativeModel('gemini-2.5-flash')

# FastAPI 애플리케이션 인스턴스 생성 (새로 추가)
app = FastAPI()

# 레시피 저장용 전역 변수 (main.py에서 접근 가능)
current_recipe = None

# Pydantic 모델 정의 (새로 추가)
class MenuRequest(BaseModel):
    menu_name: str

class RecipeResponse(BaseModel):
    ingredients: list[str]
    steps: list[str]
    tips: list[str] = []

# ★ 핵심: FastAPI 데코레이터(@app.post)를 없애고 일반 비동기 함수로 변경
async def search_recipe_text(menu_name: str) -> str:
    """
    레시피를 검색하여 텍스트 형식으로 반환하는 함수
    (test1.py 등에서 직접 호출 가능)
    """
    try:
        # 1. 검색 및 정리를 위한 프롬프트
        prompt = f"""
        다음 요리의 레시피를 구글에서 검색해서 가장 대중적이고 맛있는 방법으로 정리해줘: "{menu_name}"
        
        [조건]
        1. 재료는 정확한 계량(큰술, 컵, g 등)을 포함해서 적어줘.
        2. 조리 순서는 따라하기 쉽게 번호를 매겨서 단계별로 명확히 작성해.
        3. 팁은 포함하지 마.
        
        [출력 포맷]
        반드시 아래와 같은 텍스트 형식으로 출력해:
        
        [재료]
        - 재료1
        - 재료2
        ...
        
        [조리 단계]
        1. 단계1
        2. 단계2
        ...
        """

        # 2. Gemini 호출 (내부적으로 구글 검색 수행됨)
        response = model.generate_content(prompt)
        
        # 3. 응답 텍스트 반환
        return response.text

    except Exception as e:
        return f"❌ 에러 발생: {str(e)}"


# 새로운 /recipe 엔드포인트 (텍스트 형식 반환)
class RecipeTextResponse(BaseModel):
    recipe_text: str

@app.post("/recipe", response_model=RecipeTextResponse)
async def get_recipe(request: MenuRequest):
    """
    레시피를 텍스트 형식으로 반환하는 엔드포인트
    """
    global current_recipe
    
    try:
        recipe_text = await search_recipe_text(request.menu_name)
        
        # 전역 변수에 저장
        current_recipe = recipe_text
        
        # 서버에서 출력 (테스트용)
        print(f"\n[레시피 결과]\n{recipe_text}\n")
        print(f"{'='*60}\n")
        
        return {"recipe_text": recipe_text}
    except Exception as e:
        print(f"❌ Error: {e}")
        raise HTTPException(status_code=500, detail="레시피를 가져오는 중 오류가 발생했습니다.")


