import os
import json
import base64
import asyncio
import websockets
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from dotenv import load_dotenv
import uvicorn
from api.search_service import app as recipe_app  # search_service의 FastAPI app import
from api import search_service  # 전역 변수 접근용
from pydantic import BaseModel
from api.ingredient_service import router as ingredients_router 
load_dotenv()


OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    print("Warning: OPENAI_API_KEY not found in .env file")

app = FastAPI()
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app.include_router(ingredients_router)

# Audio Configuration
SAMPLE_RATE = 24000

@app.get("/")
async def get():
    return FileResponse(os.path.join(BASE_DIR, "index.html"))

@app.get("/check-api")
async def check_api():
    return JSONResponse({"success": True, "message": "API Key Present"})


class RecipeRequest(BaseModel):
    menu_name: str

class YoutubeRequest(BaseModel):
    video_url: str

@app.post("/recipe")
async def get_recipe(request: RecipeRequest):
    """
    레시피를 생성하고 전역 변수에 저장
    """
    try:
        print(f"\n{'='*60}")
        print(f"📝 레시피 요청: {request.menu_name}")
        print(f"{'='*60}")
        
        # search_service의 함수 호출
        from api.search_service import search_recipe_text, estimate_cooking_time
        recipe_text = await search_recipe_text(request.menu_name)
        
        # 예상 시간 계산
        estimated_time = await estimate_cooking_time(recipe_text)
        
        # search_service의 전역 변수에 저장
        search_service.current_recipe = recipe_text
        
        # 서버에서 출력
        print(f"\n[레시피 결과]\n{recipe_text}\n")
        print(f"⏱️ 예상 조리 시간: {estimated_time}분")
        print(f"{'='*60}\n")
        
        return JSONResponse({
            "success": True,
            "estimated_time": estimated_time
        })
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return JSONResponse(
            {"error": str(e)}, 
            status_code=500
        )

@app.post("/youtube-recipe")
async def get_youtube_recipe(request: YoutubeRequest):
    """
    유튜브 URL로 레시피 생성하고 전역 변수에 저장
    """
    try:
        print(f"\n{'='*60}")
        print(f"🎥 유튜브 레시피 요청: {request.video_url}")
        print(f"{'='*60}")
        
        # search_service의 함수 호출
        from api.search_service import search_recipe_video, estimate_cooking_time
        recipe_text = await search_recipe_video(request.video_url)
        
        # 예상 시간 계산
        estimated_time = await estimate_cooking_time(recipe_text)
        
        # search_service의 전역 변수에 저장
        search_service.current_recipe = recipe_text
        
        # 서버에서 출력
        print(f"\n[유튜브 레시피 결과]\n{recipe_text}\n")
        print(f"⏱️ 예상 조리 시간: {estimated_time}분")
        print(f"{'='*60}\n")
        
        return JSONResponse({
            "success": True,
            "estimated_time": estimated_time
        })
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return JSONResponse(
            {"error": str(e)}, 
            status_code=500
        )




# --- 타이머 비동기 함수 ---
async def timer_task(seconds: int, client_ws: WebSocket, openai_ws):
    print(f"[Timer] {seconds}초 타이머 시작")
    try:
        # 1. 화면에 타이머 표시 신호
        await client_ws.send_json({
            "type": "timer_start",
            "seconds": seconds
        })
        
        # 2. 실제 대기
        await asyncio.sleep(seconds)
        
        # 3. 종료 알림
        print("[Timer] 종료! 클라이언트로 알림 전송")
        await client_ws.send_json({
            "type": "timer_done",
            "message": "타이머가 종료되었습니다! 다음 단계로 넘어갈까요?"
        })

        await openai_ws.send(json.dumps({
            "type": "conversation.item.create",
            "item": {
                "type": "message",
                "role": "user",
                "content": [
                    {"type": "input_text", "text": "타이머가 종료되었습니다. 다음 단계로 진행해주세요."}
                ]
            }
        }))

        try:
            await openai_ws.send(json.dumps({
                "type": "response.create",
                "response": {
                    "modalities": ["text", "audio"], # 텍스트와 오디오로 응답
                    "instructions": "타이머 종료를 알리고 다음 단계를 안내해주세요." # (선택) 지시사항 추가 가능
                }
            }))
        except Exception as ws_e:
            print(f"[Timer] OpenAI 메시지 전송 실패 (연결 종료됨?): {ws_e}")
        
    except Exception as e:
        print(f"[Timer] 에러 발생: {e}")

@app.websocket("/ws")
async def websocket_endpoint(client_ws: WebSocket):
    await client_ws.accept()
    print("Client connected")

    url = "wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-10-01"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "OpenAI-Beta": "realtime=v1"
    }

    try:
        async with websockets.connect(url, additional_headers=headers) as openai_ws:
            print("Connected to OpenAI Realtime API")
            
            # --- [핵심 수정 1] 세션 설정: 노이즈 필터링 & 확인 절차 ---
            session_update = {
                "type": "session.update",
                "session": {
                    "modalities": ["audio", "text"],
                    "instructions": """
                    당신은 '보이스 셰프'입니다. 

                    [행동 규칙]
                    1. 레시피를 한 단계씩 친절하게 설명하세요.

                    2. **[타이머 확인 절차]**
                    - 레시피 단계에 '시간(예: 3분 볶기)'이 포함되어 있다면, **절대로 바로 타이머 도구를 실행하지 마세요.**
                    - 먼저 반드시 이렇게 물어보세요:
                        - "3분 동안 볶아주세요. 타이머를 시작할까요?"
                    - 사용자가 "응", "그래", "시작해", "네" 등으로 **명확하게 동의했을 때만** `start_timer` 도구를 실행하세요.

                    3. **[중요: 타이머 작동 중 침묵]**
                    - `start_timer` 도구를 실행한 직후에는 **"네, 3분 타이머를 시작합니다."라고 짧게 말하고 즉시 침묵하세요.**
                    - **절대로** "타이머가 끝날 때까지 기다려주세요" 뒤에 "다음 단계는..."이라며 말을 이어가지 마세요.
                    - 타이머가 돌아가는 동안에는 **사용자가 먼저 말을 걸기 전까지 절대 먼저 말하지 마세요.**
                    - 타이머가 종료되었다는 시스템 메시지를 받으면 그때 비로소 "타이머가 끝났습니다. 다음 단계로 넘어갈까요?"라고 말하세요.

                    4. 사용자가 요리 단계 이외의 질문(재료 대체, 팁, 조리 관련 궁금증 등)을 하면
                    - 단계 진행을 잠시 멈추고 질문에 대답한 뒤
                    - 다시 현재 단계부터 이어서 설명하세요.

                    5. **[중요: "다시" 요청 처리 규칙]**
                    사용자가 다음과 같은 표현을 말하면, 이것은 '반복 요청'입니다:
                    - "다시 말해줘"
                    - "방금 단계 다시 말해줘"
                    - "전 단계 뭐였어?"
                    - "조금 전 설명 다시"
                    - "다시 설명해줘"
                    - "한 번만 더 말해줘"
                    - "방금 거 잘 못 들었어"
                    - 그 밖에 "다시"라는 단어가 포함된 비슷한 문장들

                    이 경우에는 **절대로 다음 단계로 넘어가면 안 됩니다.**
                    - 새로운 단계 번호(예: "이제 2단계입니다", "다음으로", "그 다음에는")를 말하지 마세요.
                    - 오직 '직전 단계'만 다시 설명하세요.
                    - 형식 예:
                        - "방금 단계는 2단계였습니다. 팬에 기름을 두르고 중불에서 양파를 3분간 볶아주는 단계였어요."
                    - 마지막에 꼭 이렇게 물어보세요:
                        - "이 단계를 한 번 더 설명해 드릴까요, 아니면 다음 단계로 넘어갈까요?"

                    6. 사용자가 "처음부터 다시", "처음 단계부터 차근차근 알려줘"라고 말하면:
                    - 1단계부터 순서대로 다시 설명을 시작하세요.
                    - 각 단계 뒤에 항상 이렇게 물어보세요:
                        - "다음 단계로 넘어갈까요, 아니면 이 단계 다시 설명해 드릴까요?"

                    7. 전체 대화에서 가장 중요한 우선순위는:
                    - (1) 사용자의 이해도에 맞춰 설명하는 것
                    - (2) 사용자가 요청한 것을 정확하게 수행하는 것입니다.
                    - 사용자가 "다시", "전 단계" 같은 말을 하면, **새로운 정보를 주거나 다음 단계로 진행하는 것보다 '반복 설명'이 항상 더 우선입니다.**
                    
                    8. **[특정 단계 번호 요청 처리 규칙]**
                    사용자가 다음과 같은 표현을 말하면:
                    - "1단계 알려줘", "2단계가 뭐였지?"
                    - "지금 3단계인데 1단계 다시 말해줘"
                    - "앞 단계(전 단계 말고 그 앞 단계) 뭐였어?"
                    - "처음 두 단계만 알려줘"
                    - "몇 단계까지 있는지 말해줘"

                    아래 기준으로 행동하세요:

                    - 사용자가 특정 '단계 번호'를 언급했다면,
                        → 현재 단계와 상관없이 **요청한 단계 번호만 정확하게 설명**합니다.

                    - 예시:
                        사용자: "지금 4단계지? 근데 2단계 다시 말해줘."
                        보이스셰프: "2단계는 김치를 넣기 전에 돼지고기를 먼저 볶는 과정이었어요. 충분히 익혀주면 풍미가 살아나요."

                    - 단계 번호를 설명한 후에는 반드시 이렇게 물어보세요:
                        - "현재 진행 중인 단계(예: 4단계)로 돌아가서 계속할까요?"
                        - (또는)
                        - "이전에 설명한 단계를 더 듣고 싶으신가요?"

                    - 절대로 단계 번호를 혼동하거나, 잘못된 단계로 넘어가면 안 됩니다.


                    9. **[중간 질문 처리 규칙]**
                        사용자가 요리 과정과 직접 무관한 질문을 하면 (예: 재료 대체, 맛 변형, 불 세기, 위생, 도구 추천 등),
                        
                        1) 현재 단계 진행을 잠시 '정지'하고  
                        2) 질문에 대해 친절하고 정확하게 답변한 뒤  
                        3) 다시 원래 단계로 자연스럽게 돌아옵니다.

                        - 예시:
                            사용자: "이거 삼겹살로 바꿔도 돼?"
                            보이스셰프: 
                                - "네, 삼겹살을 사용해도 괜찮아요. 기름이 조금 더 나와서 더 고소해질 수 있어요."
                                - "그럼 다시 현재 단계로 돌아갈게요. 우리는 지금 3단계를 진행하고 있었어요."

                        4) 질문에 답한 후에는 반드시 이렇게 마무리하세요:
                            - "지금 단계 설명을 계속할까요?"
                            - "이 단계를 다시 설명해드릴까요?"
                            - "다음 단계로 넘어갈까요?"

                    """,
                    "voice": "alloy",
                    "input_audio_format": "pcm16",
                    "output_audio_format": "pcm16",
                    "turn_detection": {
                        "type": "server_vad",
                        # ▼▼▼ [여기를 수정했습니다] ▼▼▼
                        # 0.5 (기본값) -> 0.6 ~ 0.8 (노이즈 무시)
                        # 주변이 시끄러우면 0.7~0.8로 올리세요.
                        "threshold": 0.8,  
                        "prefix_padding_ms": 300,
                        "silence_duration_ms": 500
                    },
                    "tools": [
                        {
                            "type": "function",
                            "name": "start_timer",
                            "description": "Starts a countdown timer. Only execute this AFTER the user explicitly confirms (says 'yes').",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "seconds": {
                                        "type": "integer",
                                        "description": "Duration in seconds"
                                    }
                                },
                                "required": ["seconds"]
                            }
                        }
                    ],
                    "tool_choice": "auto"
                }
            }
            await openai_ws.send(json.dumps(session_update))
            
            # 전역 변수에서 레시피 가져오기
            recipe_text = search_service.current_recipe or """
            [재료] 아직 레시피가 선택되지 않았습니다.
            [조리 단계]
            1. /recipe 엔드포인트로 레시피를 먼저 요청해주세요.
            """
            
            # [디버그] 현재 적용된 레시피 확인
            print(f"\n📢 [WebSocket] 적용된 레시피:\n{recipe_text[:100]}...\n")
            
            recipe_prompt = f""" 
             [레시피]
             {recipe_text}
             
             위 레시피로 요리를 도와줘. 
             - 한 번에 한 단계씩 설명해.
             - 시간이 필요한 단계에서는 **반드시 먼저 "타이머를 시작할까요?"라고 물어봐.**
             - 내가 "응"이라고 하면 그때 타이머를 켜.
             """

            await openai_ws.send(json.dumps({
                "type": "conversation.item.create",
                "item": {
                    "type": "message",
                    "role": "user",
                    "content": [{ "type": "input_text", "text": recipe_prompt }]
                }
            }))

            async def receive_from_client():
                try:
                    while True:
                        data = await client_ws.receive_bytes()
                        b64_audio = base64.b64encode(data).decode('utf-8')
                        event = {
                            "type": "input_audio_buffer.append",
                            "audio": b64_audio
                        }
                        await openai_ws.send(json.dumps(event))
                except (WebSocketDisconnect, websockets.exceptions.ConnectionClosed):
                    print("Client disconnected.")
                except Exception as e:
                    print(f"Client receive error: {e}")

            async def receive_from_openai():
                try:
                    async for message in openai_ws:
                        event = json.loads(message)
                        event_type = event.get("type")
                        
                        if event_type == "response.audio.delta":
                            b64_data = event.get("delta")
                            if b64_data:
                                await client_ws.send_json({"type": "audio", "data": b64_data})
                        
                        elif event_type == "response.audio_transcript.done":
                            transcript = event.get("transcript")
                            await client_ws.send_json({"type": "text", "data": transcript})

                        elif event_type == "response.function_call_arguments.done":
                            call_id = event.get("call_id")
                            name = event.get("name")
                            arguments = event.get("arguments")

                            if name == "start_timer":
                                try:
                                    args = json.loads(arguments)
                                    seconds = args.get("seconds", 0)
                                    
                                    # 타이머 시작 메시지
                                    await client_ws.send_json({
                                        "type": "text", 
                                        "data": f"(타이머 {seconds}초 설정됨)"
                                    })
                                    
                                    asyncio.create_task(timer_task(seconds, client_ws, openai_ws))

                                    func_resp = {
                                        "type": "conversation.item.create",
                                        "item": {
                                            "type": "function_call_output",
                                            "call_id": call_id,
                                            "output": json.dumps({"status": "timer_started"})
                                        }
                                    }
                                    await openai_ws.send(json.dumps(func_resp))
                                    
                                except Exception as e:
                                    print(f"Timer parsing error: {e}")

                        elif event_type == "error":
                            print(f"OpenAI Error: {event}")

                except Exception as e:
                    print(f"OpenAI receive error: {e}")

            await asyncio.gather(receive_from_client(), receive_from_openai())

    except Exception as e:
        print(f"Connection error: {e}")
        await client_ws.close()

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8002)
