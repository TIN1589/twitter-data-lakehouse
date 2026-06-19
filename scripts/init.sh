#!/bin/bash
# =============================================================================
# EC2 Ubuntu 22.04 Setup Script for Twitter Data Lakehouse
# Target: AWS EC2 t3.micro (1GB RAM + 4GB Swap)
# =============================================================================

set -e

echo "========================================="
echo "  Twitter Data Lakehouse — EC2 Setup"
echo "========================================="

# --- 1. Check Docker ---
if ! command -v docker &> /dev/null; then
    echo "❌ Docker not found. Installing..."
    sudo apt-get update
    sudo apt-get install -y ca-certificates curl gnupg
    sudo install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    sudo chmod a+r /etc/apt/keyrings/docker.gpg
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
    sudo apt-get update
    sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
    sudo usermod -aG docker $USER
    echo "✅ Docker installed. Please log out and back in, then re-run this script."
    exit 0
else
    echo "✅ Docker found: $(docker --version)"
fi

# --- 2. Check/Setup Swap (4GB recommended for t3.micro) ---
SWAP_SIZE=$(free -m | awk '/Swap/{print $2}')
if [ "$SWAP_SIZE" -lt 1000 ]; then
    echo "⚠️  Swap is ${SWAP_SIZE}MB (< 4GB). Setting up 4GB swap..."
    sudo fallocate -l 4G /swapfile
    sudo chmod 600 /swapfile
    sudo mkswap /swapfile
    sudo swapon /swapfile
    echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
    # Optimize swap usage for low-RAM server
    sudo sysctl vm.swappiness=60
    echo "✅ 4GB swap enabled"
else
    echo "✅ Swap OK: ${SWAP_SIZE}MB"
fi

# --- 3. Project Setup ---
echo "Setting up project directories..."
mkdir -p app/logs data
chmod -R 777 app/logs

# --- 4. Create .env ---
if [ ! -f .env ]; then
    cp sample.env .env
    echo "✅ Created .env from sample.env"
    echo "   Edit .env to customize passwords if needed."
else
    echo "✅ .env already exists"
fi

# --- 5. Build & Start ---
echo ""
echo "Building Docker images (this may take a few minutes on t3.micro)..."
docker compose build

echo ""
echo "Starting services..."
docker compose up -d

echo ""
echo "========================================="
echo "  ✅ Setup Complete!"
echo "========================================="
echo ""
echo "  Services:"
echo "    Airflow:   http://<EC2-IP>:8080  (airflow / airflow)"
echo "    MinIO:     http://<EC2-IP>:9090  (minioadmin / minioadmin)"
echo "    Drill:     http://<EC2-IP>:8047"
echo "    Superset:  http://<EC2-IP>:8088  (admin / admin)"
echo ""
echo "  Commands:"
echo "    make status   — Check service health"
echo "    make logs     — View logs"
echo "    make stop     — Stop services"
echo ""
echo "  ⚠️  First startup takes 2-5 minutes on t3.micro (swap usage is normal)"
echo ""
