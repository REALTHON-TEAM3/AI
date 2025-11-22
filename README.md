# 🍳 Realtime AI Chef Assistant

> **Realthon Team 3**

<div align="center">

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)
![OpenAI](https://img.shields.io/badge/OpenAI-Realtime%20API-412991?style=for-the-badge&logo=openai&logoColor=white)
![WebSockets](https://img.shields.io/badge/WebSockets-Realtime-red?style=for-the-badge)

**당신의 주방을 스마트하게 만드는 실시간 음성 요리 파트너**

[기능 소개](#-key-features) • [설치 방법](#-getting-started) • [기술 스택](#-tech-stack)

</div>

---

## 📖 Project Overview

**Realtime AI Chef Assistant**는 요리 중 손을 쓰기 어려운 상황을 위해 설계된 **음성 인식 기반 AI 요리사**입니다.
OpenAI의 최신 **Realtime API**를 활용하여, 마치 옆에서 셰프가 알려주는 것처럼 지연 없는 대화가 가능합니다.

단순히 레시피를 읽어주는 것을 넘어, **"3분 뒤에 알람 울려줘"** 같은 맥락 기반의 명령을 수행하며 요리 과정을 완벽하게 서포트합니다.

---

## ✨ Key Features

| 기능                               | 설명                                                                                        |
| :--------------------------------- | :------------------------------------------------------------------------------------------ |
| **🗣️ Real-time Voice Interaction** | 텍스트 입력 없이, **목소리만으로** AI와 자연스럽게 대화하세요.                              |
| **📝 Smart Recipe Analysis**       | 인터넷 레시피 URL이나 텍스트를 입력하면 AI가 **구조화된 단계**로 변환합니다.                |
| **⏰ Context-Aware Timer**         | 요리 중 "면 삶는 시간 재줘"라고 말하면 **자동으로 타이머**를 실행합니다.                    |
| **⚡ Ultra Low Latency**           | WebSocket과 OpenAI Realtime API의 조합으로 **사람과 대화하듯 빠른 반응 속도**를 자랑합니다. |

---

## 🛠️ Tech Stack

### Backend

- **Core**: `Python 3.10+`
- **Framework**: `FastAPI` (Asynchronous Server)
- **Communication**: `WebSockets` (Real-time bidirectional communication)
- **AI Model**: `OpenAI GPT-4o Audio Preview`

### Frontend

- **Language**: `HTML5`, `JavaScript (Vanilla)`
- **Audio**: `Web Audio API` (Audio Worklet, ScriptProcessor)
- **Styling**: `CSS3` (Responsive Design)

---

## 📂 Directory Structure

```bash
Realthon/
├── AI/
│   ├── main.py              # FastAPI 서버 및 WebSocket 핸들러
│   ├── index.html           # 메인 프론트엔드 인터페이스
│   ├── requirements.txt     # 프로젝트 의존성 목록
│   ├── .env                 # 환경 변수 (OpenAI API Key)
│   └── ...
└── README.md                # 프로젝트 문서
```

---

## 🚀 Getting Started

### 1. Prerequisites

- **Python 3.10** 이상이 설치되어 있어야 합니다.
- **OpenAI API Key** (Realtime API 접근 권한 필요)가 준비되어야 합니다.

### 2. Installation

프로젝트를 클론하고 의존성 패키지를 설치합니다.

```bash
# 프로젝트 폴더로 이동
cd AI

# 패키지 설치
pip install -r requirements.txt
```

### 3. Configuration

`AI` 폴더 내에 `.env` 파일을 생성하고 API 키를 설정합니다.

```bash
# .env 파일 생성
OPENAI_API_KEY=sk-proj-your-api-key-here...
```

### 4. Run Server

서버를 실행하여 AI 셰프를 깨우세요!

```bash
python main.py
# 또는
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 5. Usage Guide

1. 브라우저를 열고 `http://localhost:8000`에 접속합니다.
2. **Recipe Input** 섹션에 요리하고 싶은 레시피(URL 또는 텍스트)를 입력하고 `Set Recipe`를 클릭합니다.
3. `Start Conversation` 버튼을 누르고 마이크 권한을 허용합니다.
4. **"안녕, 오늘 파스타 만드는 법 좀 알려줘"** 라고 말해보세요!

---

<div align="center">

**Developed by Realthon Team 3**
<br>
_Hackathon Project 2025_

</div>
