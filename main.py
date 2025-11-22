import os
import json
import base64
import asyncio
import websockets
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from dotenv import load_dotenv
import uvicorn


load_dotenv()


OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
   print("Warning: OPENAI_API_KEY not found in .env file")


app = FastAPI()


# Audio Configuration
SAMPLE_RATE = 24000
CHANNELS = 1


html = """
<!DOCTYPE html>
<html>
   <head>
       <title>Voice Chef AI (Realtime)</title>
       <style>
           body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f0f2f5; display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100vh; margin: 0; }
           h1 { color: #333; }
           #status { margin-top: 20px; padding: 10px; border-radius: 5px; background-color: #fff; box-shadow: 0 2px 5px rgba(0,0,0,0.1); font-weight: bold; }
           button { padding: 10px 20px; font-size: 16px; cursor: pointer; background-color: #007bff; color: white; border: none; border-radius: 5px; margin: 10px; transition: background-color 0.3s; }
           button:hover { background-color: #0056b3; }
           button:disabled { background-color: #ccc; cursor: not-allowed; }
           #log { width: 80%; max-width: 600px; height: 300px; overflow-y: scroll; background: white; border: 1px solid #ddd; padding: 10px; margin-top: 20px; border-radius: 5px; font-size: 14px; }
       </style>
   </head>
   <body>
       <h1>⚡ Voice Chef (Realtime API)</h1>
       <div id="controls">
           <button id="startBtn" onclick="startSession()">Start Conversation</button>
           <button id="stopBtn" onclick="stopSession()" disabled>Stop</button>
       </div>
       <div id="status">Ready</div>
       <div id="log"></div>


       <script>
           let ws;
           let audioContext;
           let processor;
           let inputSource;
           let isRecording = false;
          
           // Audio Playback Queue
           let nextStartTime = 0;
           const audioQueue = [];
           let isPlaying = false;


           function log(message) {
               const logDiv = document.getElementById('log');
               const p = document.createElement('p');
               p.textContent = message;
               logDiv.appendChild(p);
               logDiv.scrollTop = logDiv.scrollHeight;
           }


           async function startSession() {
               document.getElementById('startBtn').disabled = true;
               document.getElementById('stopBtn').disabled = false;
               document.getElementById('status').textContent = "Connecting...";


               const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
               ws = new WebSocket(`${protocol}//${window.location.host}/ws`);
               ws.binaryType = 'arraybuffer';


               ws.onopen = async () => {
                   log("Connected to Server");
                   document.getElementById('status').textContent = "Connected. Initializing Audio...";
                   await startAudio();
               };


               ws.onmessage = async (event) => {
                   const data = JSON.parse(event.data);
                  
                   if (data.type === 'audio') {
                       playAudioChunk(data.data);
                   } else if (data.type === 'text') {
                       log("Chef: " + data.data);
                   } else if (data.type === 'error') {
                       log("Error: " + data.data);
                   }
               };


               ws.onclose = () => {
                   log("Connection closed");
                   stopSession();
               };
           }


           async function startAudio() {
               try {
                   // Initialize AudioContext first
                   if (!audioContext) {
                       audioContext = new (window.AudioContext || window.webkitAudioContext)();
                   }
                  
                   // Resume context if suspended (browser policy)
                   if (audioContext.state === 'suspended') {
                       await audioContext.resume();
                   }


                   const stream = await navigator.mediaDevices.getUserMedia({ audio: {
                       channelCount: 1,
                       sampleRate: 24000, // Request 24k from mic if possible
                       echoCancellation: true
                   }});


                   log("Microphone access granted");
                   document.getElementById('status').textContent = "Listening... (Speak now)";


                   // Create source ONLY after context is ready
                   inputSource = audioContext.createMediaStreamSource(stream);
                  
                   processor = audioContext.createScriptProcessor(4096, 1, 1);
                  
                   processor.onaudioprocess = (e) => {
                       if (!ws || ws.readyState !== WebSocket.OPEN) return;
                      
                       const inputData = e.inputBuffer.getChannelData(0);
                      
                       // Downsample/Upsample to 24k if needed, but for now let's just send what we get
                       // Ideally we should resample to 24k if the context is 48k.
                       // For simplicity in this demo, we'll send raw float32 converted to int16.
                       // OpenAI expects 24k PCM16. If we send 48k, it might sound slow/deep.
                       // Let's rely on the getUserMedia constraint for now, or simple decimation if needed.
                      
                       const pcmData = new Int16Array(inputData.length);
                       for (let i = 0; i < inputData.length; i++) {
                           const s = Math.max(-1, Math.min(1, inputData[i]));
                           pcmData[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
                       }
                      
                       ws.send(pcmData.buffer);
                   };


                   inputSource.connect(processor);
                   processor.connect(audioContext.destination);
                  
                   isRecording = true;


               } catch (err) {
                   log("Audio Error: " + err);
                   stopSession();
               }
           }


           function playAudioChunk(base64Data) {
               if (!audioContext) return;
              
               try {
                   const binaryString = window.atob(base64Data);
                   const len = binaryString.length;
                   const bytes = new Uint8Array(len);
                   for (let i = 0; i < len; i++) {
                       bytes[i] = binaryString.charCodeAt(i);
                   }
                   const int16Data = new Int16Array(bytes.buffer);
                   const float32Data = new Float32Array(int16Data.length);
                  
                   for (let i = 0; i < int16Data.length; i++) {
                       float32Data[i] = int16Data[i] / 0x8000;
                   }


                   // OpenAI sends 24000Hz audio
                   const buffer = audioContext.createBuffer(1, float32Data.length, 24000);
                   buffer.getChannelData(0).set(float32Data);


                   const source = audioContext.createBufferSource();
                   source.buffer = buffer;
                   source.connect(audioContext.destination);


                   const currentTime = audioContext.currentTime;
                   if (nextStartTime < currentTime) {
                       nextStartTime = currentTime;
                   }
                   source.start(nextStartTime);
                   nextStartTime += buffer.duration;
                  
                   document.getElementById('status').textContent = "Chef is speaking...";
                  
                   // Reset status after playback (approximate)
                   source.onended = () => {
                        if (audioContext.currentTime >= nextStartTime) {
                            document.getElementById('status').textContent = "Listening...";
                        }
                   };
                  
               } catch (e) {
                   log("Playback Error: " + e);
               }
           }


           function stopSession() {
               document.getElementById('startBtn').disabled = false;
               document.getElementById('stopBtn').disabled = true;
               document.getElementById('status').textContent = "Stopped";
              
               if (processor) {
                   processor.disconnect();
                   processor = null;
               }
               if (inputSource) {
                   inputSource.disconnect();
                   inputSource = null;
               }
               if (audioContext) {
                   audioContext.close();
                   audioContext = null;
               }
               if (ws) {
                   ws.close();
                   ws = null;
               }
               isRecording = false;
           }
       </script>
   </body>
</html>
"""


@app.get("/")
async def get():
   return HTMLResponse(html)


@app.get("/check-api")
async def check_api():
   # Keep this for debugging
   return JSONResponse({"success": True, "message": "API Key Present"})


@app.websocket("/ws")
async def websocket_endpoint(client_ws: WebSocket):
   await client_ws.accept()
   print("Client connected")


   # OpenAI Realtime API URL
   url = "wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-10-01"
   headers = {
       "Authorization": f"Bearer {OPENAI_API_KEY}",
       "OpenAI-Beta": "realtime=v1"
   }


   try:
       async with websockets.connect(url, additional_headers=headers) as openai_ws:
           print("Connected to OpenAI Realtime API")
          
           # Initialize Session
           session_update = {
               "type": "session.update",
               "session": {
                   "modalities": ["audio", "text"],
                   "instructions": "당신은 '보이스 셰프'라는 이름의 활기차고 도움이 되는 요리 보조입니다. 사용자가 요리하는 것을 도와주세요. 한국어로 대답하세요. 말이 너무 길지 않게 간결하고 빠르게 대답하세요.",
                   "voice": "alloy",
                   "input_audio_format": "pcm16",
                   "output_audio_format": "pcm16",
                   "turn_detection": {
                       "type": "server_vad",
                       "threshold": 0.5,
                       "prefix_padding_ms": 300,
                       "silence_duration_ms": 500
                   }
               }
           }
           await openai_ws.send(json.dumps(session_update))
           
           recipe_text = f"""
           [재료]
            - 신김치 2컵 (약 300g)
            - 돼지고기 앞다리살 또는 목살 200g
            - 두부 1/2모
            - 양파 1/2개
            - 대파 1대
            - 다진 마늘 1 큰술
            - 고춧가루 1~1.5 큰술
            - 설탕 1 작은술
            - 국간장 1 큰술
            - 소금, 후추 약간
            - 물 또는 멸치육수 600ml
            - 김치 국물 1/2컵
            - 고추장 1 큰술 (선택)

            [조리 단계]
            1. 김치를 한 입 크기로 썰고, 돼지고기·두부·양파·대파도 각각 손질한다.
            2. 냄비에 기름을 두르고 돼지고기를 볶는다. 70% 익으면 다진 마늘을 넣어 같이 볶는다.
            3. 김치와 김치 국물을 넣고 3~5분 볶아 풍미를 올린다.
            4. 고춧가루, 국간장, 설탕, (선택) 고추장을 넣고 1~2분 더 볶는다.
            5. 물 또는 육수를 600ml 붓고 센 불에서 끓인 후, 약불로 15~20분 끓인다.
            6. 두부를 넣고 5분 끓인 뒤 대파를 넣고 1분 더 끓인다.
            7. 마지막에 소금과 후추로 간을 맞춰 완성한다.
        """
           recipe_prompt = f""" 
            지금부터 아래 레시피에 따라 요리를 진행할 거야.
            당신은 '보이스 셰프'로서 단계별로 천천히, 음성으로 안내해줘.

            [레시피]
            {recipe_text}
            요리 단계는 다음 규칙을 따라 말해:
            - 한 번에 한 단계씩만 말해
            - 필요한 경우 타이머 안내도 해줘
            - 다음 단계로 넘어갈 준비가 되면 '다음 단계로 넘어갈까요?'라고 물어봐
            - 사용자가 '응' 또는 '다음'이라고 말하면 다음 단계로 이동해
            """

           await openai_ws.send(json.dumps({
                "type": "conversation.item.create",
                "item": {
                    "type": "message",
                    "role": "user",
                    "content": [
                        { "type": "input_text", "text": recipe_prompt }
                    ]
                }
            }))

           async def receive_from_client():
               try:
                   while True:
                       data = await client_ws.receive_bytes()
                       # Client sends raw PCM16 bytes
                       # We need to base64 encode it and send to OpenAI
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
                           # Audio chunk from OpenAI
                           b64_data = event.get("delta")
                           if b64_data:
                               await client_ws.send_json({
                                   "type": "audio",
                                   "data": b64_data
                               })
                       elif event_type == "response.text.delta":
                           # Text chunk (if any)
                           text = event.get("delta")
                           # await client_ws.send_json({"type": "text", "data": text})
                       elif event_type == "response.audio_transcript.done":
                           transcript = event.get("transcript")
                           await client_ws.send_json({"type": "text", "data": transcript})
                       elif event_type == "error":
                           print(f"OpenAI Error: {event}")
               except Exception as e:
                   print(f"OpenAI receive error: {e}")


           # Run both tasks concurrently
           await asyncio.gather(receive_from_client(), receive_from_openai())


   except Exception as e:
       print(f"Connection error: {e}")
       await client_ws.close()


if __name__ == "__main__":
   uvicorn.run(app, host="0.0.0.0", port=8000)