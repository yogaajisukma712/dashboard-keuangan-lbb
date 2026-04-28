# =============================================================================
# Makefile — LBB Super Smart Dashboard
# Penggunaan: make <target>
# =============================================================================

COMPOSE      = docker compose -f docker-compose.yml --env-file .env
WEB          = billing_supersmart_web
DB           = billing_supersmart_db
PORT         = 6001

# Warna
GREEN  = \033[0;32m
CYAN   = \033[0;36m
YELLOW = \033[1;33m
RED    = \033[0;31m
RESET  = \033[0m

.PHONY: help deploy build up down restart logs shell db-shell \
        push status clean prune create-admin backup-db

# ── Default ───────────────────────────────────────────────────────────────────
help:
	@echo ""
	@echo "$(CYAN)╔══════════════════════════════════════════════════════╗$(RESET)"
	@echo "$(CYAN)║   LBB Super Smart — Makefile Commands               ║$(RESET)"
	@echo "$(CYAN)╚══════════════════════════════════════════════════════╝$(RESET)"
	@echo ""
	@echo "  $(GREEN)Deploy$(RESET)"
	@echo "    make deploy          → full deploy (sync + git push + build + up)"
	@echo "    make deploy msg=\"..\" → deploy dengan custom commit message"
	@echo "    make build           → build image ulang tanpa cache"
	@echo "    make up              → jalankan container (tanpa rebuild)"
	@echo "    make down            → hentikan semua container"
	@echo "    make restart         → down + up (tanpa rebuild)"
	@echo "    make push            → git add + commit + push saja"
	@echo "    make push msg=\"..\"   → git push dengan custom message"
	@echo ""
	@echo "  $(GREEN)Monitoring$(RESET)"
	@echo "    make status          → status container"
	@echo "    make logs            → log realtime (Ctrl+C untuk berhenti)"
	@echo "    make logs-tail       → 50 baris log terakhir"
	@echo "    make health          → cek HTTP response app"
	@echo ""
	@echo "  $(GREEN)Database$(RESET)"
	@echo "    make db-shell        → masuk ke psql PostgreSQL"
	@echo "    make create-admin    → buat user admin"
	@echo "    make backup-db       → backup database ke file SQL"
	@echo "    make restore-db f=X  → restore dari file SQL (f=nama_file.sql)"
	@echo ""
	@echo "  $(GREEN)Maintenance$(RESET)"
	@echo "    make shell           → masuk bash container web"
	@echo "    make clean           → hapus image & container yang tidak terpakai"
	@echo "    make prune           → docker system prune (hati-hati!)"
	@echo ""

# ── Full Deploy ───────────────────────────────────────────────────────────────
deploy:
	@bash deploy.sh $(if $(msg),"$(msg)",)

# ── Build image baru (no cache) ───────────────────────────────────────────────
build:
	@echo "$(CYAN)→ Building Docker image...$(RESET)"
	@$(COMPOSE) build --no-cache
	@echo "$(GREEN)✓ Build selesai$(RESET)"

# ── Jalankan container ────────────────────────────────────────────────────────
up:
	@echo "$(CYAN)→ Starting containers...$(RESET)"
	@$(COMPOSE) up -d
	@sleep 5
	@$(MAKE) --no-print-directory status

# ── Hentikan container ────────────────────────────────────────────────────────
down:
	@echo "$(CYAN)→ Stopping containers...$(RESET)"
	@$(COMPOSE) down
	@echo "$(GREEN)✓ Containers stopped$(RESET)"

# ── Restart (down + up, tanpa rebuild) ───────────────────────────────────────
restart:
	@echo "$(CYAN)→ Restarting containers...$(RESET)"
	@$(COMPOSE) down
	@$(COMPOSE) up -d
	@sleep 5
	@$(MAKE) --no-print-directory status

# ── Git push ─────────────────────────────────────────────────────────────────
push:
	@echo "$(CYAN)→ Git add + commit + push...$(RESET)"
	@git add -A
	@if git diff --cached --quiet; then \
		echo "$(YELLOW)  Tidak ada perubahan untuk di-commit$(RESET)"; \
	else \
		if [ -n "$(msg)" ]; then \
			git commit -m "$(msg)"; \
		else \
			git commit -m "deploy: update $$(date '+%d/%m/%Y %H:%M')"; \
		fi; \
		git push && echo "$(GREEN)✓ Push berhasil ke GitHub$(RESET)"; \
	fi

# ── Status container ──────────────────────────────────────────────────────────
status:
	@echo ""
	@echo "$(CYAN)► Container Status:$(RESET)"
	@docker ps --format "  {{.Names}}\t{{.Status}}\t{{.Ports}}" \
		| grep "billing_supersmart" \
		| column -t \
		|| echo "  (tidak ada container billing_supersmart yang berjalan)"
	@echo ""
	@echo "$(CYAN)► Disk Image:$(RESET)"
	@docker images aplikasilembaga-web --format "  {{.Repository}}:{{.Tag}}\t{{.Size}}\t{{.CreatedSince}}" \
		| column -t || true
	@echo ""

# ── Logs realtime ─────────────────────────────────────────────────────────────
logs:
	@docker logs -f $(WEB)

logs-tail:
	@docker logs --tail 50 $(WEB)

# ── Cek kesehatan app ─────────────────────────────────────────────────────────
health:
	@echo "$(CYAN)→ Cek HTTP response...$(RESET)"
	@HTTP=$$(curl -s -o /dev/null -w "%{http_code}" http://localhost:$(PORT)/auth/login); \
	if [ "$$HTTP" = "200" ]; then \
		echo "$(GREEN)✓ App OK — HTTP $$HTTP$(RESET) — http://localhost:$(PORT)"; \
	else \
		echo "$(RED)✗ App tidak merespons — HTTP $$HTTP$(RESET)"; \
	fi

# ── Shell masuk container web ─────────────────────────────────────────────────
shell:
	@echo "$(CYAN)→ Masuk ke bash container $(WEB)...$(RESET)"
	@docker exec -it $(WEB) bash || docker exec -it $(WEB) sh

# ── PostgreSQL shell ──────────────────────────────────────────────────────────
db-shell:
	@echo "$(CYAN)→ Masuk ke psql container $(DB)...$(RESET)"
	@docker exec -it $(DB) psql -U postgres -d lbb_db

# ── Buat admin ────────────────────────────────────────────────────────────────
create-admin:
	@echo "$(CYAN)→ Membuat user admin...$(RESET)"
	@docker exec $(WEB) python create_admin.py

# ── Backup database ───────────────────────────────────────────────────────────
backup-db:
	@mkdir -p backups
	@FNAME="backups/lbb_db_$$(date '+%Y%m%d_%H%M%S').sql"; \
	docker exec $(DB) pg_dump -U postgres lbb_db > $$FNAME; \
	echo "$(GREEN)✓ Backup tersimpan: $$FNAME$(RESET)"

# ── Restore database ──────────────────────────────────────────────────────────
restore-db:
	@if [ -z "$(f)" ]; then \
		echo "$(RED)✗ Berikan nama file: make restore-db f=backups/nama_file.sql$(RESET)"; exit 1; \
	fi
	@echo "$(YELLOW)⚠ Restore akan menimpa database yang ada!$(RESET)"
	@read -p "  Yakin? (ketik 'ya' untuk lanjut): " konfirm; \
	if [ "$$konfirm" = "ya" ]; then \
		docker exec -i $(DB) psql -U postgres -d lbb_db < $(f); \
		echo "$(GREEN)✓ Restore selesai dari $(f)$(RESET)"; \
	else \
		echo "$(YELLOW)  Dibatalkan$(RESET)"; \
	fi

# ── Hapus image tidak terpakai ────────────────────────────────────────────────
clean:
	@echo "$(CYAN)→ Menghapus image dan container tidak terpakai...$(RESET)"
	@docker image prune -f
	@docker container prune -f
	@echo "$(GREEN)✓ Selesai$(RESET)"

# ── Docker system prune ───────────────────────────────────────────────────────
prune:
	@echo "$(YELLOW)⚠ PERINGATAN: Ini akan menghapus semua resource Docker yang tidak terpakai$(RESET)"
	@read -p "  Yakin? (ketik 'ya' untuk lanjut): " konfirm; \
	if [ "$$konfirm" = "ya" ]; then \
		docker system prune -f --volumes; \
		echo "$(GREEN)✓ Prune selesai$(RESET)"; \
	else \
		echo "$(YELLOW)  Dibatalkan$(RESET)"; \
	fi
