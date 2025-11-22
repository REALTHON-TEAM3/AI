import asyncio
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from api.search_service import search_recipe_text

async def main():
    print("\n" + "="*40)
    print("🧪 레시피 검색 테스트 모드")
    print("="*40)

    # 1. 사용자 입력 받기
    menu = input("👉 검색할 요리 이름을 입력하세요: ")
    
    if not menu.strip():
        print("❌ 메뉴 이름이 입력되지 않았습니다.")
        return

    print(f"\n⏳ '{menu}' 정보를 구글에서 검색 중입니다... (약 3~5초 소요)")

    try:
        # 2. 검색 서비스 호출
        # (타임아웃 에러 등을 확인하기 위해 try-except 사용)
        result = await search_recipe_text(menu)
        
        # 3. 결과 확인
        if not result:
            print("⚠️ 결과가 비어있습니다. (API 키나 할당량을 확인해주세요)")
        else:
            print("\n" + "="*20 + " [검색 결과] " + "="*20)
            print(result)
            print("="*20 + " [끝] " + "="*20 + "\n")
            
    except Exception as e:
        print(f"\n❌ 에러 발생: {e}")
        print("팁: API 키가 올바른지, 인터넷이 연결되어 있는지 확인해보세요.")

if __name__ == "__main__":
    # 윈도우에서 가끔 발생하는 이벤트 루프 에러 방지
    if sys.platform.startswith('win'):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        
    asyncio.run(main())