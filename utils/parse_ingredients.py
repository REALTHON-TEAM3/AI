import json
import logging

logger = logging.getLogger(__name__)

def parse_ingredients_from_gemini_response(response) -> dict:
    """
    Gemini generate_content() 응답에서 JSON을 파싱하여
    {'ingredients': [...]} 딕셔너리를 반환.
    """
    # 1) 응답 텍스트 추출
    #   - SDK 버전에 따라 response.text가 있을 수도 있고
    #   - 없으면 candidates[0].content.parts[0].text 에서 가져옴
    raw_text = None

    # response.text가 있으면 사용
    if hasattr(response, "text") and response.text:
        raw_text = response.text
    else:
        try:
            raw_text = response.candidates[0].content.parts[0].text
        except (AttributeError, IndexError) as e:
            logger.error(f"Gemini 응답에서 텍스트를 찾을 수 없음: {e}")
            raise ValueError("모델 응답에 텍스트가 없습니다.")

    if not raw_text:
        raise ValueError("모델 응답이 비어 있습니다.")

    logger.debug(f"Raw model text: {raw_text}")

    # 2) 코드블록( ``` ... ``` ) 제거
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        # 첫 줄(```json 또는 ```), 마지막 줄(```) 제거
        lines = cleaned.splitlines()
        # 최소 3줄 이상일 때만 안전하게 자르고, 아니면 전체 사용
        if len(lines) >= 3:
            cleaned = "\n".join(lines[1:-1]).strip()

    logger.debug(f"Cleaned JSON text: {cleaned}")

    # 3) JSON 파싱
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as e:
        logger.error(f"JSON 파싱 실패: {e} | text={cleaned}")
        raise ValueError("모델 응답을 JSON으로 파싱하는 데 실패했습니다.")

    # 4) ingredients 키 검증
    if "ingredients" not in data or not isinstance(data["ingredients"], list):
        raise ValueError("모델 응답에 'ingredients' 리스트가 없습니다.")

    return data
