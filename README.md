# AutoFigure Bot — COMP7940

A Telegram bot that generates publication-quality academic figures from paper descriptions using Google Gemini.

## Quickstart for Teammates

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

Every push to `main` automatically triggers GitHub Actions, which deploys the updated code to the EC2 server. No `.env` or local setup required.

### 3. Test on Telegram

Search for **@HKBU_Fly_bot** on Telegram and test directly — the bot is always running on the cloud server.

After pushing, wait ~1 minute for the deployment to complete, then test your changes on Telegram.

---

## Bot Usage

1. Send `/generate`
2. Choose a mode:
   - **Mode 1 — Text Only**: paste your paper method description
   - **Mode 2 — Reference Image**: send a reference image, then paste the description
3. The bot returns a generated figure as a PNG file

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
└── .env                   # Not in repo — only needed to run locally
```

---

## Run Locally (optional)

Only needed if you want to run the bot on your own machine. Get the `.env` file from the project owner and place it in the project root, then:

```bash
pip install -r requirements.txt
python -m bot.main
```

---

## Deployment

Deployment is automated via GitHub Actions on every push to `main`.

The pipeline (`.github/workflows/deploy.yml`) will:
1. Run tests
2. SSH into the EC2 instance
3. Pull the latest code
4. Rebuild and restart the Docker container

Required GitHub Secrets (already configured):
- `EC2_HOST` — EC2 public IP
- `EC2_SSH_KEY` — EC2 SSH private key
