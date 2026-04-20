# Speaking Coach - Real-time Voice Coaching Platform

> Improve your speaking skills in real-time with AI-powered coaching during live phone calls.

**Current Status**: Phase 1 - Real-time Analysis Infrastructure Complete ✅

---

## 🎯 What It Does

Speaking Coach is a mobile + web platform that:

1. **During Calls** 📞
   - Transcribes your speech in real-time (Deepgram)
   - Detects filler words ("um", "uh", "like")
   - Measures pace (words per minute)
   - Analyzes clarity and articulation
   - **Generates live coaching tips** using Claude AI

2. **After Calls** 📊
   - Provides detailed feedback report
   - Identifies strengths & improvement areas
   - Tracks progress over time
   - Compares against your baseline

3. **Custom Coaching** 🎓
   - Interview prep mode
   - Sales pitch mode
   - Presentation mode
   - Custom profiles with personalized tips

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────┐
│            Client Layer                         │
├──────────────────┬──────────────────────────────┤
│  iOS App (Swift) │ Web App (React + TypeScript) │
│  - CallKit       │ - Twilio calls              │
│  - Audio capture │ - WebRTC audio streaming    │
└──────────────────┴────────────┬──────────────────┘
                                 │ HTTP + WebSocket
                                 ▼
┌─────────────────────────────────────────────────┐
│         FastAPI Backend Server                  │
│                                                 │
│  ┌──────────────────────────────────────────┐  │
│  │ Real-time Audio Processor                │  │
│  │ ├─ Deepgram (speech-to-text)            │  │
│  │ ├─ Voice Analyzer                       │  │
│  │ ├─ Metrics Calculator                   │  │
│  │ └─ Suggestion Engine (Claude API)       │  │
│  └──────────────────────────────────────────┘  │
│                                                 │
│  ┌──────────────────────────────────────────┐  │
│  │ Real-time WebSocket Server              │  │
│  │ ├─ Broadcast metrics (every 30s)        │  │
│  │ ├─ Stream coaching tips                 │  │
│  │ └─ Handle session state                 │  │
│  └──────────────────────────────────────────┘  │
│                                                 │
│  ┌──────────────────────────────────────────┐  │
│  │ REST API                                 │  │
│  │ ├─ /api/auth (login/register)           │  │
│  │ ├─ /api/profiles (coaching profiles)    │  │
│  │ ├─ /api/calls (call management)         │  │
│  │ └─ /api/analytics (progress tracking)   │  │
│  └──────────────────────────────────────────┘  │
└────────┬──────────────────┬─────────────────────┘
         │                  │
    ┌────▼──────┐    ┌──────▼────────────┐
    │PostgreSQL │    │ Redis Cache       │
    │(Users,    │    │ (Sessions, Tips,  │
    │ Calls,    │    │  Real-time data)  │
    │Analytics) │    └───────────────────┘
    └───────────┘

External Services:
├─ Deepgram (speech-to-text)
├─ Anthropic Claude API (coaching)
├─ Twilio (phone calls)
└─ AWS S3 (audio storage)
```

---

## 📦 Project Structure

```
speaking-coach/
├── backend/
│   ├── src/
│   │   ├── main.py                 # FastAPI app
│   │   ├── config.py               # Settings
│   │   ├── auth.py                 # JWT authentication
│   │   ├── db/
│   │   │   ├── models.py           # SQLAlchemy ORM
│   │   │   └── database.py         # DB connection
│   │   ├── routes/
│   │   │   ├── auth.py             # Auth endpoints
│   │   │   ├── profiles.py         # Profile CRUD
│   │   │   ├── calls.py            # Call management
│   │   │   └── analytics.py        # Analytics endpoints
│   │   ├── services/
│   │   │   ├── voice_analysis.py   # Deepgram integration ⭐
│   │   │   ├── suggestion_engine.py # Claude API ⭐
│   │   │   ├── twilio_integration.py # Phone calls ⭐
│   │   │   └── realtime_processor.py # Audio pipeline ⭐
│   │   └── websocket/
│   │       └── manager.py          # Socket.IO server
│   ├── tests/                      # Pytest test suite
│   └── requirements.txt
│
├── web/
│   ├── src/
│   │   ├── App.tsx                 # Main app
│   │   ├── pages/
│   │   │   ├── Login.tsx
│   │   │   ├── Register.tsx
│   │   │   ├── Dashboard.tsx       # Main interface
│   │   │   ├── CallInterface.tsx   # Active call view
│   │   │   ├── Analytics.tsx       # Progress tracking
│   │   │   └── Profiles.tsx        # Profile management
│   │   ├── services/
│   │   │   └── api.ts              # API client
│   │   ├── stores/
│   │   │   └── authStore.ts        # State management
│   │   └── components/
│   │       └── Navigation.tsx
│   ├── index.html
│   ├── package.json
│   ├── vite.config.ts
│   └── tailwind.config.js
│
├── ios/
│   └── SpeakingCoach/
│       ├── SpeakingCoachApp.swift  # App entry point
│       ├── Models/
│       │   └── User.swift          # Data models
│       ├── Services/
│       │   └── APIClient.swift     # API client
│       ├── Managers/
│       │   ├── AuthManager.swift   # Auth
│       │   └── CallManager.swift   # CallKit integration ⭐
│       └── Views/
│           ├── DashboardView.swift
│           ├── LoginView.swift
│           └── ...
│
├── .github/workflows/
│   ├── backend-tests.yml           # Pytest CI
│   ├── web-build.yml               # React build CI
│   └── docker-build.yml            # Docker CI
│
├── docker-compose.yml              # Local dev stack
├── Dockerfile.backend
│
├── SETUP.md                        # Setup guide
├── API_KEYS.md                     # API key instructions ⭐
├── quick-start.sh                  # Auto-setup script
└── README.md
```

---

## 🚀 Quick Start

```bash
# 1. Clone and setup
git clone https://github.com/chouksep/Agentic-System.git
cd Agentic-System
chmod +x quick-start.sh
./quick-start.sh

# 2. Get API keys (see API_KEYS.md)
# Edit .env with your keys

# 3. Start web app (in another terminal)
cd web
npm run dev

# 4. Open http://localhost:3000
```

**For detailed setup**, see [SETUP.md](SETUP.md)

---

## 📊 Phase Breakdown

### ✅ Phase 0: Foundation (Complete)
- Backend API with auth, profiles, calls management
- Web frontend skeleton
- iOS app skeleton
- CI/CD pipelines
- Docker dev environment

### ✅ Phase 1: Real-time Analysis (Complete)
- **Voice Analysis** (Deepgram integration)
  - Real-time transcription streaming
  - Filler word detection
  - Pace/WPM calculation
  - Clarity metrics
  - Confidence scoring

- **Suggestion Engine** (Claude API)
  - Real-time coaching tips
  - Post-call feedback generation
  - Profile-specific prompts
  - Strength/weakness analysis

- **Phone Integration** (Twilio)
  - Outbound call initiation
  - Call recording & transcription
  - Browser-based calling

- **Real-time Processing**
  - Async audio stream handling
  - 30-second metrics aggregation
  - WebSocket broadcasting
  - Post-call analysis

### 🔄 Phase 2: Enhanced Features (In Progress)
- [ ] Web call interface with Twilio
- [ ] iOS CallKit audio streaming
- [ ] Advanced prosody analysis (emotion/confidence)
- [ ] A/B testing for tip effectiveness
- [ ] Analytics dashboard with trends
- [ ] Custom coaching profile builder
- [ ] Offline mode support

### 📋 Phase 3: Personalization (Planned)
- [ ] Learning paths & spaced repetition
- [ ] Adaptive difficulty adjustment
- [ ] Gamification (streaks, badges)
- [ ] Human coach integration
- [ ] Video call support (Zoom integration)
- [ ] Peer benchmarking

### 🌟 Phase 4: Scale & Polish (Planned)
- [ ] Performance optimization
- [ ] Security hardening
- [ ] App Store deployment
- [ ] Multi-region infrastructure

---

## 🔑 API Keys Required

| Service | Purpose | Cost | Status |
|---------|---------|------|--------|
| **Deepgram** | Speech-to-text | Free tier: 60 min/mo | ✅ Ready |
| **Anthropic** | Coaching tips | ~$0.003 per 1K tokens | ✅ Ready |
| **Twilio** | Phone calls | ~$0.015/min | ✅ Ready |
| **AWS S3** | Audio storage | ~$0.023/GB/mo | Optional |

**See [API_KEYS.md](API_KEYS.md)** for detailed setup instructions.

---

## 🧪 Testing

```bash
# Backend tests
cd backend
pip install -r requirements.txt
pytest tests/ -v --cov=src

# Results: Auth, Profiles, Calls endpoints fully tested
```

**Coverage**: 15+ tests covering auth, profiles, and call lifecycle

---

## 📱 Supported Platforms

| Platform | Status | Features |
|----------|--------|----------|
| **Web (React)** | Phase 1 Complete | Dashboard, profiles, auth |
| **iOS (SwiftUI)** | Phase 1 Complete | CallKit integration, auth |
| **Android** | Phase 2 | Planned |
| **Web Calling** | Phase 2 | Twilio integration |

---

## 💡 Example: Interview Coaching

```
Interview Prep Profile
├─ Target: 120-150 WPM
├─ Focus: Clarity, confidence, fillers
└─ Tips: "Slow down for emphasis"

During Call (Real-time):
├─ Transcription: "Um, I've been working in software engineering for..."
├─ Analysis: WPM 165, 2 fillers, confidence 0.82
└─ Tip: "You're speaking fast. Pause between sentences."

After Call (Feedback):
├─ Strengths: Clear articulation, confident tone
├─ Improvements: Too many fillers, pace too fast
├─ Score: 7.8/10
└─ Trend: +15% improvement from last call
```

---

## 🔐 Privacy & Security

- End-to-end encrypted audio (WebRTC)
- HTTPS + TLS 1.3 for all API calls
- JWT tokens (30-min expiry)
- PostgreSQL + encryption at rest (AWS)
- Audio auto-deletes after 30 days
- GDPR compliant data deletion
- Full audit logs for access

---

## 📈 Performance Metrics (Target)

| Metric | Target | Current |
|--------|--------|---------|
| Transcription latency | <500ms | ✅ Deepgram |
| Tip generation latency | <2s | ✅ Claude cached |
| WebSocket broadcast | <100ms | ✅ Socket.IO |
| End-to-end (audio → tip) | <2.5s | 🔄 Phase 2 |
| API response time | <200ms | ✅ FastAPI async |
| Database query | <50ms | ✅ Indexed |

---

## 💰 Cost Estimate

For 1 user doing 5 calls/day (10 min each):

```
Deepgram (250 min/mo)    $1.08
Anthropic (250 tips)     $0.50
Twilio (250 min)         $3.75
AWS S3 (5 GB)            $0.12
─────────────────────────────
Total Monthly:           $5.45
```

**Deepgram free tier** (60 min/mo) covers first few users.

---

## 📚 Documentation

- **[SETUP.md](SETUP.md)** - Local development setup guide
- **[API_KEYS.md](API_KEYS.md)** - How to get API keys
- **[API.md](API.md)** - REST API documentation (coming soon)

---

## 🤝 Contributing

This is an educational/demo project. Contributions welcome for:
- Bug fixes
- Performance improvements
- Additional coaching profiles
- Test coverage
- Documentation

See GitHub issues for open items.

---

## 📄 License

MIT - Open source for educational use

---

## 🎯 Next Steps

1. **Get API Keys** (see [API_KEYS.md](API_KEYS.md))
2. **Run Setup** (`./quick-start.sh`)
3. **Test Backend** (pytest, Swagger UI at localhost:8000/docs)
4. **Build Web Call Interface** (Phase 2)
5. **Integrate iOS CallKit** (Phase 2)

---

## 📞 Support

- **Setup issues?** Check [SETUP.md](SETUP.md)
- **API key problems?** See [API_KEYS.md](API_KEYS.md)
- **Want to contribute?** Open a GitHub issue
- **Security issue?** See SECURITY.md

---

**Built with ❤️ using Claude, Deepgram, Twilio, and Anthropic**
