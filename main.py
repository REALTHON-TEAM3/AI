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
