# Dockerfile for Onboarding Mascot - Intercom-only (Cloud Run)
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y gcc g++ git && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src ./src
COPY docs ./docs

ENV PYTHONUNBUFFERED=1
ENV PORT=8080

EXPOSE 8080

# Intercom-only FastAPI app (no Slack)
CMD ["python", "-m", "src.integrations.intercom.app"]
