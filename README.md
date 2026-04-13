# AutoFigure Bot — COMP7940

A cloud-native Telegram bot that generates publication-quality academic figures from paper descriptions using Google Gemini.

- **Telegram**: [@HKBU_Fly_bot](https://t.me/HKBU_Fly_bot)
- **Deployed on**: AWS EC2 (t2.micro, us-east-2) via Docker Compose
- **CI/CD**: GitHub Actions — every push to `main` auto-deploys

---

## Bot Commands

| Command | Description |
|---------|-------------|
| `/start` | Activate the bot and see welcome message |
| `/help` | Show usage instructions |
| `/generate` | Start figure generation (Mode 1 or Mode 2) |
| `/history` | View your last 5 generation records |
| `/cancel` | Cancel the current operation |

### Generation Modes

- **Mode 1 — Text Only**: paste your paper method description → receive a 4K PNG figure
- **Mode 2 — Reference Image**: send a reference diagram first, then paste your description → style-matched figure

---

## Quickstart 

No local environment setup needed. Just clone, edit, and push — CI/CD handles the rest.

### 1. Clone the repo

```bash
git clone https://github.com/Fly-cpu-source/COMP7940-LLM-Image.git
cd COMP7940-LLM-Image
```

### 2. Edit code and push

```bash
git add .
git commit -m "your message"
git push origin main
```

Every push to `main` automatically triggers GitHub Actions, which deploys the updated code to the EC2 server.

### 3. Test on Telegram

Search for **@HKBU_Fly_bot** on Telegram. After pushing, wait ~1 minute for the deployment to complete, then test your changes.

---

## Project Structure

```
├── bot/
│   ├── main.py            # Entry point, CloudWatch logging setup
│   ├── handlers.py        # Telegram command & conversation handlers
│   ├── figure_service.py  # Gemini API image generation
│   ├── rate_limiter.py    # Redis-backed per-user rate limiting (3 req/60s)
│   ├── s3.py              # AWS S3 diagram upload
│   └── db.py              # DynamoDB request logging
├── .github/
│   └── workflows/
│       └── deploy.yml     # CI/CD: auto-deploy on push to main
├── Dockerfile             # Python 3.11-slim container image
├── docker-compose.yml     # Orchestrates bot + Redis containers
├── requirements.txt       # Python dependencies
├── .env.example           # Environment variable template
└── README.md
```

---

## Run Locally (optional)

Only needed if you want to run the bot on your own machine.

1. Copy `.env.example` to `.env` and fill in your credentials:

```bash
cp .env.example .env
```

2. Install dependencies and run:

```bash
pip install -r requirements.txt
python -m bot.main
```

---

## Deployment

Deployment is automated via GitHub Actions on every push to `main`.

The pipeline (`.github/workflows/deploy.yml`) will:
1. Install Python 3.11 dependencies
2. SSH into the EC2 instance using stored secrets
3. Pull the latest code (`git pull origin main`)
4. Rebuild and restart both containers (`docker-compose-v2 up -d --build`)

Required GitHub Secrets (already configured):
- `EC2_HOST` — EC2 public IP
- `EC2_SSH_KEY` — EC2 SSH private key

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Interface | Telegram Bot API (python-telegram-bot v21) |
| AI Engine | Google Gemini (gemini-2.5-flash-image / gemini-3-pro-image-preview) |
| Deployment | AWS EC2 t2.micro + Docker Compose |
| Database | AWS DynamoDB (request logging) |
| Storage | AWS S3 (figure storage) |
| Monitoring | AWS CloudWatch (via watchtower) |
| Rate Limiting | Redis (3 requests / 60s per user) |
| CI/CD | GitHub Actions |
