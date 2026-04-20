# Speaking Coach - Local Development Setup

## Prerequisites

- Docker & Docker Compose
- Python 3.11+
- Node.js 20+
- Xcode 15+ (for iOS development)
- Git

## Quick Start

### 1. Clone & Environment Setup

```bash
git clone https://github.com/chouksep/Agentic-System.git
cd Agentic-System
cp .env.example .env
```

### 2. Configure Environment Variables

Edit `.env` with your API keys:

```bash
# Critical for Phase 1
DEEPGRAM_API_KEY=your-deepgram-key
ANTHROPIC_API_KEY=sk-ant-...
TWILIO_ACCOUNT_SID=your-twilio-sid
TWILIO_AUTH_TOKEN=your-twilio-token

# Optional AWS (for production audio storage)
AWS_ACCESS_KEY_ID=your-key
AWS_SECRET_ACCESS_KEY=your-secret

# Local development defaults work as-is
SECRET_KEY=dev-secret-key-change-in-production
DATABASE_URL=postgresql://speaking_coach:password@db:5432/speaking_coach
REDIS_URL=redis://redis:6379
```

### 3. Start Docker Services

```bash
docker-compose up -d
```

This starts:
- PostgreSQL (port 5432)
- Redis (port 6379)
- Backend API (port 8000)

Verify services:
```bash
docker-compose ps
```

### 4. Initialize Backend Database

```bash
docker-compose exec backend python -c "from backend.src.db.database import init_db; init_db()"
```

### 5. Start Web Frontend

```bash
cd web
npm install
npm run dev
```

Open http://localhost:3000

### 6. iOS Development

```bash
cd ios/SpeakingCoach
# Open in Xcode
open SpeakingCoach.xcodeproj
```

Update `APIClient.swift` base URL for your machine:
```swift
private let baseURL = URL(string: "http://YOUR_LOCAL_IP:8000/api")!
```

## API Testing

### Health Check
```bash
curl http://localhost:8000/health
```

### Create User
```bash
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "password123",
    "display_name": "Test User"
  }'
```

## Getting API Keys

### Deepgram (Speech-to-Text)
1. Go to https://console.deepgram.com
2. Sign up free account
3. Create API key in Settings
4. Add to `.env`

**Cost**: ~$0.0043 per minute for real-time streaming

### Anthropic (Claude API)
1. Go to https://console.anthropic.com
2. Create API key
3. Add to `.env`

**Cost**: ~$0.003 per 1K input tokens (cheap for coaching tips)

### Twilio (Phone Calls)
1. Go to https://www.twilio.com/console
2. Create project
3. Get Account SID and Auth Token
4. Add to `.env`
5. Buy a Twilio phone number (optional for production)

**Cost**: ~$0.015 per minute for calls

### AWS (Optional - Audio Storage)
1. Create AWS account
2. Create IAM user with S3 permissions
3. Add credentials to `.env`
4. Create S3 buckets: `speaking-coach-audio`, `speaking-coach-reports`

## Development Workflow

### Backend Development
```bash
# Hot reload on file changes
docker-compose up backend

# Run tests
docker-compose exec backend pytest backend/tests -v

# Run linting
docker-compose exec backend ruff check backend/src
```

### Web Development
```bash
cd web
npm run dev  # Hot reload at localhost:3000
npm run build  # Production build
npm run lint  # Check code
```

### iOS Development
- Use Xcode simulator
- Update API base URL to match your machine's IP
- Test with sample test data

## Useful Commands

```bash
# View logs
docker-compose logs backend -f
docker-compose logs db -f

# Database shell
docker-compose exec db psql -U speaking_coach -d speaking_coach

# Redis shell
docker-compose exec redis redis-cli

# Restart services
docker-compose restart

# Full clean rebuild
docker-compose down -v
docker-compose up -d
```

## Running Tests

```bash
# Backend tests
cd backend
pip install -r requirements.txt
pytest tests/ -v --cov=src

# Web tests (coming in Phase 2)
cd web
npm test
```

## Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│  Client Layer                                       │
├─────────┬──────────────────────────────────────────┤
│ iOS App │ React Web App                            │
│ (Swift) │ (React 18 + TypeScript)                  │
└────┬────┴────────────┬──────────────────────────────┘
     │                 │
     └────────┬────────┘
              │ HTTP + WebSocket
              ▼
┌─────────────────────────────────────────────────────┐
│  Backend API (FastAPI)                              │
│                                                     │
│  ├─ /api/auth (Login/Register)                     │
│  ├─ /api/profiles (CRUD coaching profiles)         │
│  ├─ /api/calls (Start/End calls)                   │
│  └─ /api/analytics (User metrics)                  │
│                                                     │
│  WebSocket (Socket.IO) → Real-time metrics         │
└────────┬────────────────────────────────────────────┘
         │
    ┌────┴────────────┐
    │                 │
    ▼                 ▼
PostgreSQL          Redis
(Users,              (Sessions,
 Calls,              Cache,
 Analytics)          Real-time)
```

## Phase 1 Features Being Added

- ✅ Deepgram real-time speech-to-text
- ✅ Claude API for coaching tips generation
- ✅ Twilio call bridging (web → phone)
- ✅ Real-time metrics streaming via WebSocket
- ✅ Audio processing pipeline
- ✅ Post-call feedback generation

## Troubleshooting

### Port Already in Use
```bash
# Find and kill process on port
lsof -i :8000
kill -9 <PID>
```

### Docker Container Issues
```bash
# Rebuild containers
docker-compose build --no-cache

# Check logs
docker-compose logs backend --tail=50
```

### Database Connection Failed
```bash
# Reset database
docker-compose down -v
docker-compose up -d db
# Wait 30 seconds for DB to be ready
docker-compose up backend
```

### API Key Issues
- Verify `.env` is in project root (not in git)
- Check API key is valid and not expired
- Verify service quotas/billing is active

## Next Steps

1. Add your API keys to `.env`
2. Run `docker-compose up -d`
3. Test backend: `curl http://localhost:8000/health`
4. Start web frontend: `cd web && npm run dev`
5. Begin Phase 1 feature development

For support, check logs: `docker-compose logs -f`
