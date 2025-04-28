.PHONY: frontend dev up down rebuild clean prod prod-build prod-push

frontend:
	rm -rf frontend/dist
	cd frontend && npm install && npm run build

dev:
	cd frontend && npm run dev

up: frontend
	docker compose up --build web backend

down:
	docker compose down

rebuild: down frontend
	docker compose up --build web backend

clean:
	docker compose down --volumes
	docker system prune -f

prod:
	docker compose down --volumes
	docker system prune -f
	docker compose -f docker-compose.yaml -f docker-compose.prod.yaml up --build -d

soft-prod:
	docker compose -f docker-compose.yaml -f docker-compose.prod.yaml up --build -d

prod-build:
	docker compose -f docker-compose.yaml -f docker-compose.prod.yaml build

prod-push:
	docker compose -f docker-compose.yaml -f docker-compose.prod.yaml push
