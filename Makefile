.PHONY: setup build start stop restart logs status clean help

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

setup: ## Create .env from sample.env and prepare directories
	@if [ ! -f .env ]; then \
		cp sample.env .env; \
		echo "✅ Created .env from sample.env"; \
	else \
		echo "⚠️  .env already exists, skipping"; \
	fi
	@mkdir -p app/logs data
	@chmod -R 777 app/logs || true
	@echo "✅ Directories ready"

build: ## Build Docker images (Airflow + Superset)
	docker compose build
	@echo "✅ Images built"

start: ## Start all services
	docker compose up -d
	@echo "✅ Services starting..."
	@echo "  Airflow:  http://localhost:8080"
	@echo "  MinIO:    http://localhost:9090"
	@echo "  Drill:    http://localhost:8047"
	@echo "  Superset: http://localhost:8088"

stop: ## Stop all services
	docker compose down
	@echo "✅ Services stopped"

restart: ## Restart all services
	docker compose down
	docker compose up -d

logs: ## View logs (all services)
	docker compose logs -f --tail=50

status: ## Check service health
	@echo "=== Service Status ==="
	@docker compose ps
	@echo ""
	@echo "=== Memory Usage ==="
	@docker stats --no-stream --format "table {{.Name}}\t{{.MemUsage}}\t{{.MemPerc}}" 2>/dev/null || true

clean: ## Remove all containers, volumes, and data (DESTRUCTIVE)
	@echo "⚠️  This will delete all data!"
	@read -p "Are you sure? [y/N] " confirm; \
	if [ "$$confirm" = "y" ] || [ "$$confirm" = "Y" ]; then \
		docker compose down -v --rmi local; \
		rm -rf data app/logs; \
		echo "✅ Cleaned"; \
	else \
		echo "Cancelled"; \
	fi
