from fastapi import FastAPI
from api.ingredient_service import router as ingredient_router
import logging
import sys

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('app.log', encoding='utf-8')
    ]
)

# 로거 생성
logger = logging.getLogger(__name__)

app = FastAPI()


app.include_router(ingredient_router, prefix="/api")

@app.get("/")
def read_root():
    logger.info("루트 엔드포인트 접근")
    return {"message": "Welcome to the Ingredient API. Go to /docs to see the API documentation."}

# To run this application:
# uvicorn main:app --reload
