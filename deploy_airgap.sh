#!/usr/bin/env bash
# ==============================================================================
# deploy_airgap.sh
# Zero-internet deployment script for air-gapped target environments.
# Verifies cryptographic checksums before loading images and launching stack.
# ==============================================================================
set -euo pipefail

TARGET_ARCHIVE="${1:-}"
WORK_DIR="."

verify_checksums() {
    echo "[1/4] Verifying cryptographic integrity (SHA256SUMS)..."
    if [ ! -f "SHA256SUMS" ]; then
        echo "ERROR: SHA256SUMS manifest missing!"
        exit 1
    fi

    if command -v sha256sum >/dev/null 2>&1; then
        sha256sum -c SHA256SUMS
    else
        shasum -a 256 -c SHA256SUMS
    fi

    echo " Cryptographic verification PASSED: all bundle files intact."
}

# If an archive was provided as argument, extract it first
if [ -n "${TARGET_ARCHIVE}" ]; then
    if [ ! -f "${TARGET_ARCHIVE}" ]; then
        echo "ERROR: Release archive '${TARGET_ARCHIVE}' not found."
        exit 1
    fi
    echo "[0/4] Extracting release bundle '${TARGET_ARCHIVE}'..."
    tar -xzf "${TARGET_ARCHIVE}"
    EXTRACTED_DIR=$(tar -tzf "${TARGET_ARCHIVE}" | head -1 | cut -f1 -d"/")
    cd "${EXTRACTED_DIR}"
fi

echo "======================================================================"
echo " Starting Air-Gapped Deployment"
echo " Working Directory: $(pwd)"
echo "======================================================================"

# Step 1: Verify Checksums
verify_checksums

# Step 2: Load Docker Images
echo "[2/4] Loading offline container images from images.tar.gz..."
if [ -f "images.tar.gz" ]; then
    if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
        docker load -i images.tar.gz
        echo " Images loaded into Docker daemon successfully."
    else
        echo "WARN: Docker daemon not running or not accessible. Skipping image load."
    fi
else
    echo "ERROR: images.tar.gz missing from bundle!"
    exit 1
fi

# Step 3: Configure Environment
echo "[3/4] Validating local environment configuration (.env)..."
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        echo "Creating default .env from .env.example..."
        cp .env.example .env
        chmod 600 .env
        echo " Created .env with default site configuration."
    else
        echo "ERROR: Neither .env nor .env.example found!"
        exit 1
    fi
else
    echo " Existing .env file found. Preserving site configuration."
fi

# Step 4: Bring up stack
echo "[4/4] Starting service stack with Docker Compose..."
if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
    docker compose up -d

    echo "Waiting for services to become healthy..."
    MAX_ATTEMPTS=15
    ATTEMPT=1
    STACK_READY=0

    while [ "${ATTEMPT}" -le "${MAX_ATTEMPTS}" ]; do
        sleep 2
        HEALTH_STATUS=$(python3 -c "
import urllib.request, json
try:
    with urllib.request.urlopen('http://localhost:8000/health', timeout=2) as r:
        if r.status == 200:
            d = json.loads(r.read().decode())
            if d.get('status') == 'healthy' and d.get('worker_ready') is True:
                print('READY')
except Exception:
    pass
" 2>/dev/null || true)

        if [ "${HEALTH_STATUS}" = "READY" ]; then
            STACK_READY=1
            break
        fi
        echo "  [Attempt ${ATTEMPT}/${MAX_ATTEMPTS}] Waiting for vision_api and inference_worker..."
        ATTEMPT=$(( ATTEMPT + 1 ))
    done

    if [ "${STACK_READY}" -eq 1 ]; then
        echo " Smoke Test: GET http://localhost:8000/health -> 200 OK"
        DETECT_STATUS=$(python3 -c "
import urllib.request
try:
    with urllib.request.urlopen('http://localhost:8000/api/v1/detect', timeout=2) as r:
        print(r.status)
except Exception as e:
    print(e)
" 2>/dev/null || true)
        echo " Smoke Test: GET http://localhost:8000/api/v1/detect -> HTTP ${DETECT_STATUS}"
        echo "======================================================================"
        echo " Air-Gapped Deployment Successful! Stack is operational."
        echo "======================================================================"
    else
        echo "WARN: Stack did not reach ready state within timeout. Check 'docker compose logs'."
    fi
else
    echo "WARN: Docker daemon not available to run compose. Bundle verified successfully."
fi
