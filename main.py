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
        from api.search_service import search_recipe_text
        recipe_text = await search_recipe_text(request.menu_name)
        
        # search_service의 전역 변수에 저장
        search_service.current_recipe = recipe_text
        
        # 서버에서 출력
        print(f"\n[레시피 결과]\n{recipe_text}\n")
        print(f"{'='*60}\n")
        
        return JSONResponse({
            "success": True,
            "recipe_text": recipe_text
        })
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return JSONResponse(
            {"error": str(e)}, 
            status_code=500
        )

# --- 타이머 비동기 함수 ---
async def timer_task(seconds: int, client_ws: WebSocket):
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
                    2. **[중요] 타이머 확인 절차:** - 레시피 단계에 '시간(예: 3분 볶기)'이 포함되어 있다면, **절대로** 바로 타이머 도구를 실행하지 마세요.
                       - 먼저 "3분 동안 볶아주세요. 타이머를 시작할까요?"라고 **사용자에게 물어보세요.**
                       - 사용자가 "응", "그래", "시작해" 등으로 **동의했을 때만** 'start_timer' 도구를 실행하세요.
                    3. 타이머가 돌아가는 동안에는 잡담을 하지 말고 조용히 기다리세요.
                    4. 사용자가 요리 단계 이외의 질문(예: 재료 대체, 팁, 조리 관련 궁금증 등)을 하면 단계 진행을 잠시 멈추고 질문에 대답한 뒤 다시 단계를 계속하세요.
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
                                    
                                    asyncio.create_task(timer_task(seconds, client_ws))

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
    uvicorn.run(app, host="0.0.0.0", port=8000)
