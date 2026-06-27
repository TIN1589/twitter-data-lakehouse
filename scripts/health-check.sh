#!/bin/bash
# =============================================================================
# Health Check Script — Twitter Data Lakehouse
# =============================================================================
# Usage: bash scripts/health-check.sh
# Cron:  */5 * * * * /path/to/scripts/health-check.sh >> /var/log/lakehouse-health.log 2>&1
# =============================================================================

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

echo "======================================================"
echo "  Lakehouse Health Check — $TIMESTAMP"
echo "======================================================"

FAIL_COUNT=0

# --- Function: check service ---
check_service() {
    local name=$1
    local url=$2
    local expected_code=${3:-200}
    
    code=$(curl -s -o /dev/null -w '%{http_code}' --connect-timeout 5 "$url" 2>/dev/null || echo "000")
    
    if [ "$code" = "$expected_code" ]; then
        echo -e "  ${GREEN}✅ $name${NC}: HTTP $code"
    else
        echo -e "  ${RED}❌ $name${NC}: HTTP $code (expected $expected_code)"
        FAIL_COUNT=$((FAIL_COUNT + 1))
    fi
}

# --- 1. Container Status ---
echo ""
echo "📦 Container Status:"
for container in postgres twitter-data-lakehouse-minio-1 twitter-data-lakehouse-drill-1 \
                 airflow-scheduler airflow-webserver twitter-data-lakehouse-superset-1; do
    status=$(sudo docker inspect --format='{{.State.Status}}' "$container" 2>/dev/null || echo "not found")
    if [ "$status" = "running" ]; then
        echo -e "  ${GREEN}✅ $container${NC}: $status"
    else
        echo -e "  ${RED}❌ $container${NC}: $status"
        FAIL_COUNT=$((FAIL_COUNT + 1))
    fi
done

# --- 2. HTTP Endpoints ---
echo ""
echo "🌐 HTTP Endpoints:"
check_service "Airflow" "http://localhost:8080/health"
check_service "MinIO" "http://localhost:9090"
check_service "Drill" "http://localhost:8047"
check_service "Superset" "http://localhost:8088/login/" 200

# --- 3. Memory Usage ---
echo ""
echo "💾 Memory Usage:"
echo "  System:"
free -m | awk 'NR==2{printf "    RAM:  %sMB / %sMB (%.1f%%)\n", $3, $2, $3*100/$2}'
free -m | awk 'NR==3{printf "    Swap: %sMB / %sMB (%.1f%%)\n", $3, $2, $3*100/$2}'
echo "  Containers:"
sudo docker stats --no-stream --format "    {{.Name}}: {{.MemUsage}} ({{.MemPerc}})" 2>/dev/null

# --- 4. Disk Usage ---
echo ""
echo "💿 Disk Usage:"
df -h / | awk 'NR==2{printf "  Root: %s / %s (%s used)\n", $3, $2, $5}'

# --- 5. MinIO Data ---
echo ""
echo "📊 MinIO Data:"
file_count=$(sudo docker exec twitter-data-lakehouse-minio-1 mc ls --recursive local/twitter-data/ 2>/dev/null | wc -l || echo "0")
echo "  Files in bucket: $file_count"

# --- Summary ---
echo ""
echo "======================================================"
if [ "$FAIL_COUNT" -eq 0 ]; then
    echo -e "  ${GREEN}✅ ALL CHECKS PASSED${NC}"
else
    echo -e "  ${RED}❌ $FAIL_COUNT CHECK(S) FAILED${NC}"
fi
echo "======================================================"

exit $FAIL_COUNT
