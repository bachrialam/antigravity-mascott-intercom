#!/bin/bash
# Deployment script for Onboarding Mascot (Intercom-only) to Google Cloud Run
# Usage: ./deploy.sh
# Requires .env in the same directory as this script with INTERCOM + Weaviate + OpenAI vars.

set -e  # Exit on error

# Project root = directory containing this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# =============================================================================
# CONFIGURATION
# =============================================================================

PROJECT_ID="${GOOGLE_CLOUD_PROJECT:-mascot-intercom-staging}"
SERVICE_NAME="onboarding-assistant"
REGION="us-central1"
REPOSITORY="cloud-run-images"
IMAGE_NAME="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY}/${SERVICE_NAME}"

# =============================================================================
# COLORS FOR OUTPUT
# =============================================================================

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo_info() {
    echo -e "${GREEN}✓${NC} $1"
}

echo_warn() {
    echo -e "${YELLOW}⚠${NC} $1"
}

echo_error() {
    echo -e "${RED}✗${NC} $1"
}

# =============================================================================
# VALIDATION
# =============================================================================

echo_info "Validating environment..."

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    echo_error "gcloud CLI not found. Please install it: https://cloud.google.com/sdk/install"
    exit 1
fi

# .env next to deploy.sh (project root)
ENV_FILE="${SCRIPT_DIR}/.env"
if [ ! -f "$ENV_FILE" ]; then
    echo_error ".env not found at $ENV_FILE. Copy .env.example to .env and set INTERCOM_TOKEN, INTERCOM_ADMIN_ID, WEAVIATE_*, OPENAI_API_KEY_DATA_BOT."
    exit 1
fi

# Load environment variables from .env (strip CR and trim so CRLF/space tidak bikin variabel kosong)
set -a
while IFS= read -r line || [ -n "$line" ]; do
    line="${line//$'\r'/}"
    line="${line#"${line%%[![:space:]]*}"}"
    line="${line%"${line##*[![:space:]]}"}"
    [[ "$line" =~ ^#.*$ ]] && continue
    [[ -z "$line" ]] && continue
    
    # Split on first '='
    if [[ "$line" == *"="* ]]; then
        key="${line%%=*}"
        value="${line#*=}"
        
        # Trim spaces from key and value
        key="${key#"${key%%[![:space:]]*}"}"
        key="${key%"${key##*[![:space:]]}"}"
        value="${value#"${value%%[![:space:]]*}"}"
        value="${value%"${value##*[![:space:]]}"}"
        
        value="${value%\"}"
        value="${value#\"}"
        
        case "$key" in
            ONBOARDING_SLACK_BOT_TOKEN|ONBOARDING_SLACK_SIGNING_SECRET|INTERCOM_TOKEN|INTERCOM_ADMIN_ID|OPENAI_API_KEY_DATA_BOT|WEAVIATE_URL|WEAVIATE_API_KEY|WEAVIATE_COLLECTION|RAG_TOP_K|RAG_SIMILARITY_THRESHOLD|DEBUG|GOOGLE_CLOUD_PROJECT)
                export "$key=$value"
                ;;
        esac
    fi
done < "$ENV_FILE"
set +a

# Required for Intercom-only deployment (no Slack)
REQUIRED_VARS=(
    "OPENAI_API_KEY_DATA_BOT"
    "WEAVIATE_URL"
    "WEAVIATE_API_KEY"
    "INTERCOM_TOKEN"
    "INTERCOM_ADMIN_ID"
)

for var in "${REQUIRED_VARS[@]}"; do
    if [ -z "${!var}" ]; then
        echo_error "Required environment variable $var is not set in .env"
        exit 1
    fi
done

echo_info "All required environment variables are set"

# =============================================================================
# ARTIFACT REGISTRY SETUP
# =============================================================================

echo_info "Using GCP project: ${PROJECT_ID}"
gcloud config set project "${PROJECT_ID}" 2>/dev/null || true

echo_info "Configuring Artifact Registry..."
gcloud auth configure-docker ${REGION}-docker.pkg.dev --quiet

echo_info "Checking if Artifact Registry repository exists..."
if ! gcloud artifacts repositories describe ${REPOSITORY} --location=${REGION} --project=${PROJECT_ID} &>/dev/null; then
    echo_warn "Repository '${REPOSITORY}' doesn't exist. Creating it..."
    gcloud artifacts repositories create ${REPOSITORY} \
        --repository-format=docker \
        --location=${REGION} \
        --project=${PROJECT_ID} \
        --description="Docker images for Cloud Run services"
    echo_info "Repository created successfully"
else
    echo_info "Repository '${REPOSITORY}' already exists"
fi

# =============================================================================
# BUILD & DEPLOY
# =============================================================================

if command -v docker &>/dev/null; then
    echo_info "Building Docker image locally (AMD64)..."
    docker buildx build --platform linux/amd64 -t "${IMAGE_NAME}:latest" -f "${SCRIPT_DIR}/Dockerfile" "${SCRIPT_DIR}" --load
    echo_info "Pushing image to Artifact Registry..."
    docker push "${IMAGE_NAME}:latest"
else
    echo_warn "Docker tidak ditemukan. Build lewat Google Cloud Build (tidak perlu Docker di Mac)."
    echo_info "Pastikan Cloud Build API aktif: https://console.cloud.google.com/apis/library/cloudbuild.googleapis.com?project=${PROJECT_ID}"
    echo_info "Building image di Cloud Build..."
    gcloud builds submit --tag "${IMAGE_NAME}:latest" "${SCRIPT_DIR}" --project "${PROJECT_ID}"
fi

echo_info "Deploying to Cloud Run (Intercom-only). Service akan dibuat otomatis jika belum ada."
gcloud run deploy ${SERVICE_NAME} \
    --image "${IMAGE_NAME}:latest" \
    --platform managed \
    --region ${REGION} \
    --project ${PROJECT_ID} \
    --allow-unauthenticated \
    --set-env-vars "OPENAI_API_KEY_DATA_BOT=${OPENAI_API_KEY_DATA_BOT}" \
    --set-env-vars "WEAVIATE_URL=${WEAVIATE_URL}" \
    --set-env-vars "WEAVIATE_API_KEY=${WEAVIATE_API_KEY}" \
    --set-env-vars "WEAVIATE_COLLECTION=${WEAVIATE_COLLECTION:-MascotHelpArticles}" \
    --set-env-vars "RAG_TOP_K=${RAG_TOP_K:-3}" \
    --set-env-vars "RAG_SIMILARITY_THRESHOLD=${RAG_SIMILARITY_THRESHOLD:-0.4}" \
    --set-env-vars "SYSTEM_PROMPT_FILE=src/config/system_prompt_intercom.txt" \
    --set-env-vars "INTERCOM_TOKEN=${INTERCOM_TOKEN}" \
    --set-env-vars "INTERCOM_ADMIN_ID=${INTERCOM_ADMIN_ID}" \
    --set-env-vars "DEBUG=${DEBUG:-false}" \
    --set-env-vars "ENVIRONMENT=production" \
    --set-env-vars "GOOGLE_CLOUD_PROJECT=${PROJECT_ID}" \
    --memory 512Mi \
    --cpu 1 \
    --timeout 300 \
    --max-instances 10 \
    --min-instances 1 \
    --no-cpu-throttling \
    --port 8080

# =============================================================================
# GET SERVICE URL
# =============================================================================

SERVICE_URL=$(gcloud run services describe ${SERVICE_NAME} \
    --platform managed \
    --region ${REGION} \
    --project ${PROJECT_ID} \
    --format 'value(status.url)')

echo ""
echo_info "Deployment successful! 🎉"
echo ""
echo "Service URL:  ${SERVICE_URL}"
echo "Intercom webhook URL: ${SERVICE_URL}/intercom/webhook"
echo ""
echo "Next steps (Intercom):"
echo "1. Go to Intercom → Settings → Developers → Webhooks"
echo "2. Add a webhook URL: ${SERVICE_URL}/intercom/webhook"
echo "3. Subscribe to: conversation.user.created, conversation.user.replied"
echo "4. Save and test a conversation."
echo ""
echo_info "To view logs:"
echo "gcloud logging read \"resource.type=cloud_run_revision AND resource.labels.service_name=${SERVICE_NAME}\" --project=${PROJECT_ID} --limit=50"

