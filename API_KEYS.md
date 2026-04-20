# Getting API Keys for Speaking Coach

All services required for local development and how to get them.

## Critical Services (Required for Phase 1)

### 1. Deepgram (Speech-to-Text) 🎤

**What it does**: Real-time transcription of speech during calls
**Cost**: Free tier: 60 min/month. ~$0.0043/min thereafter

**Steps**:
1. Go to https://console.deepgram.com
2. Click "Sign up" (GitHub auth available)
3. Create a free account
4. Go to **Settings** → **API Keys**
5. Click "Create a new key"
6. Choose scope: "General"
7. Copy the key
8. Add to `.env`: `DEEPGRAM_API_KEY=your_key_here`

**Test it**:
```bash
curl -X POST https://api.deepgram.com/v1/listen \
  -H "Authorization: Token your_key_here" \
  -H "Content-Type: audio/wav" \
  --data-binary @test.wav
```

---

### 2. Anthropic Claude API (Coaching Tips) 🤖

**What it does**: Generates real-time coaching tips and post-call feedback
**Cost**: Cheap! ~$0.003 per 1K input tokens for Sonnet. ~$0.50-2.00 per call

**Steps**:
1. Go to https://console.anthropic.com
2. Sign up with email or Google
3. Go to **Account** → **API Keys**
4. Click "Generate API Key"
5. Copy the full key (starts with `sk-ant-`)
6. Add to `.env`: `ANTHROPIC_API_KEY=sk-ant-xxxxx`

**Safety**:
- Don't share this key
- Rotate it monthly
- Set usage limits in Console

**Test it**:
```python
from anthropic import Anthropic
client = Anthropic(api_key="sk-ant-xxx")
response = client.messages.create(
    model="claude-3-5-sonnet-20241022",
    max_tokens=100,
    messages=[{"role": "user", "content": "Hello"}]
)
print(response.content[0].text)
```

---

### 3. Twilio (Phone Calls) 📞

**What it does**: Enable phone calls from web app, IVR, recording
**Cost**: $0.015/min for calls + $0.50/month per number

**Steps**:
1. Go to https://www.twilio.com/console
2. Sign up (phone verification required)
3. You get a free trial number automatically
4. Go to **Account** → **API Credentials**
5. Copy:
   - Account SID
   - Auth Token
6. Add to `.env`:
   ```
   TWILIO_ACCOUNT_SID=ACxxxxxxxx
   TWILIO_AUTH_TOKEN=your_token_here
   ```

**Getting a Real Twilio Number** (optional):
- In Console, go to **Develop** → **Phone Numbers**
- Click "Get a Number"
- Choose country, area code
- Costs $1-2/month

**Test it**:
```python
from twilio.rest import Client
account_sid = "AC..."
auth_token = "..."
client = Client(account_sid, auth_token)

# Get account balance
account = client.api.account.fetch()
print(account.type)  # Should print 'Trial'
```

---

## Optional Services (For Production/Advanced Features)

### 4. AWS S3 (Audio Storage) 📦

**What it does**: Store call recordings and reports
**Cost**: Pay-as-you-go. ~$0.023 per GB stored/month

**Steps**:
1. Create AWS account at https://aws.amazon.com
2. Go to **IAM** → **Users** → **Create User**
3. Attach policy: `AmazonS3FullAccess`
4. Create **Access Key**
5. Copy:
   - Access Key ID
   - Secret Access Key
6. Add to `.env`:
   ```
   AWS_ACCESS_KEY_ID=AKIA...
   AWS_SECRET_ACCESS_KEY=...
   AWS_REGION=us-east-1
   S3_BUCKET_AUDIO=speaking-coach-audio
   S3_BUCKET_REPORTS=speaking-coach-reports
   ```

**Create S3 Buckets**:
```bash
aws s3 mb s3://speaking-coach-audio --region us-east-1
aws s3 mb s3://speaking-coach-reports --region us-east-1
```

---

## Local Development Setup Checklist

```bash
# 1. Get API keys from above
# 2. Create .env file
cp .env.example .env

# 3. Edit .env with your keys
nano .env  # or vi, code, etc

# 4. Start services
docker-compose up -d

# 5. Initialize database
docker-compose exec backend python -c "from backend.src.db.database import init_db; init_db()"

# 6. Run tests
docker-compose exec backend pytest backend/tests -v

# 7. Start web app
cd web && npm install && npm run dev

# 8. Open browser
open http://localhost:3000
```

---

## Troubleshooting API Keys

### "Invalid API Key" Error

**Deepgram**:
- Key should start with nothing special
- Check for extra spaces: `DEEPGRAM_API_KEY=key_here` (not `key_here `)
- Regenerate key in console if in doubt

**Anthropic**:
- Key must start with `sk-ant-`
- Free trial: max 5 API keys, 40K tokens/min
- Check Console → Account → API Keys

**Twilio**:
- Account SID starts with `AC`
- Auth Token is 32 characters
- Keep both in sync (regenerate together)
- Check account type (Trial, Paid) in Console

### Rate Limiting

Each service has rate limits:

- **Deepgram**: 600 requests/minute (free tier)
- **Anthropic**: 40K tokens/minute (free tier)
- **Twilio**: 100 calls/second

For development, these are plenty. Contact support if you hit limits.

---

## Security Best Practices

1. **Never commit .env to git** ✓ (Already in .gitignore)
2. **Use different keys for dev/prod**
3. **Rotate keys monthly**
4. **Use least-privilege IAM roles** (AWS)
5. **Monitor usage in consoles** to catch unauthorized access
6. **Set API limits** where available
7. **Use environment variables** only, never hardcode

---

## Cost Estimates (Monthly)

For a typical user doing 5 practice calls/day:

| Service | Usage | Cost |
|---------|-------|------|
| Deepgram | 25 calls × 10 min = 250 min | ~$1.08 |
| Anthropic | 25 calls × 100 tips = 2,500 tips | ~$0.50 |
| Twilio | 250 min of calls | ~$3.75 |
| AWS S3 | ~5 GB stored | ~$0.12 |
| **Total** | | **~$5.45** |

**Deepgram free tier** includes 60 min/month, so you only pay after that.

---

## Next Steps

1. Get the keys above
2. Add to `.env`
3. Run `docker-compose up -d`
4. Test in http://localhost:8000/docs (Swagger UI)
5. Create account and start a call!

For issues, check `docker-compose logs backend -f`
