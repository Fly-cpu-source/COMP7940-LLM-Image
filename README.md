# AutoFigure Bot — COMP7940

A Telegram bot that generates publication-quality academic figures from paper descriptions using Google Gemini.

## Setup Guide

### 1. Clone the repo

```bash
git clone https://github.com/Fly-cpu-source/COMP7940-LLM-Image.git
cd COMP7940-LLM-Image
```

### 2. Add the `.env` file

Get the `.env` file from a teammate and place it in the project root (`COMP7940-LLM-Image/`).
It should contain:

```
TELEGRAM_TOKEN=...
GEMINI_API_KEY=...
GEMINI_MODEL=gemini-2.5-flash-image
AWS_REGION=ap-southeast-1
DYNAMODB_TABLE=autofigure_requests
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
```

### 3. Run locally

```bash
pip install -r requirements.txt
python -m bot.main
```

### 4. Run with Docker

```bash
docker-compose -f docker-compose.yml up -d --build
```

Or with Docker Compose v2:

```bash
/usr/local/bin/docker-compose-v2 up -d --build
```

---

## Project Structure

```
├── bot/
│   ├── main.py            # Entry point
│   ├── handlers.py        # Telegram command handlers
│   ├── figure_service.py  # Gemini image generation
│   └── db.py              # DynamoDB logging
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env                   # Not in repo — get from teammate
```

---

## Bot Usage

1. Open Telegram and search for the bot
2. Send `/generate`
3. Choose a mode:
   - **Mode 1 — Text Only**: paste your paper method description
   - **Mode 2 — Reference Image**: send a reference image, then paste the description
4. The bot returns a generated figure as a PNG file

---

## Deployment (EC2)

Deployment is automated via GitHub Actions on every push to `main`.

The CI/CD pipeline (`.github/workflows/deploy.yml`) will:
1. Run tests
2. SSH into the EC2 instance
3. Pull the latest code
4. Rebuild and restart the Docker container

Required GitHub Secrets:
- `EC2_HOST` — EC2 public IP
- `EC2_SSH_KEY` — EC2 SSH private key content
