# WhatsApp Bot Migration Notes

## Runtime readiness

- Bot starts automatically when the container starts.
- Watchdog reconnects when runtime falls to `idle`, `error`, or `disconnected`.
- `auth_failure` and `awaiting_qr` are not forced-retried because they need a valid WhatsApp session or QR scan.
- Current session data lives in Docker volume `aplikasilembaga_whatsapp_bot_auth`.
- Session backups live in Docker volume `aplikasilembaga_whatsapp_bot_backups`.

## Before moving server

1. Open WhatsApp management page and create a session backup.
2. Export both Docker volumes:

```bash
docker run --rm -v aplikasilembaga_whatsapp_bot_auth:/data -v "$PWD":/backup alpine tar -czf /backup/whatsapp_bot_auth.tar.gz -C /data .
docker run --rm -v aplikasilembaga_whatsapp_bot_backups:/data -v "$PWD":/backup alpine tar -czf /backup/whatsapp_bot_backups.tar.gz -C /data .
```

3. Copy both `.tar.gz` files to the new server.
4. Create volumes and restore:

```bash
docker volume create aplikasilembaga_whatsapp_bot_auth
docker volume create aplikasilembaga_whatsapp_bot_backups
docker run --rm -v aplikasilembaga_whatsapp_bot_auth:/data -v "$PWD":/backup alpine sh -c "tar -xzf /backup/whatsapp_bot_auth.tar.gz -C /data"
docker run --rm -v aplikasilembaga_whatsapp_bot_backups:/data -v "$PWD":/backup alpine sh -c "tar -xzf /backup/whatsapp_bot_backups.tar.gz -C /data"
```

5. Start stack:

```bash
docker compose up -d --build
```

6. Verify:

```bash
docker exec billing_supersmart_whatsapp_bot node -e "fetch('http://127.0.0.1:3000/session').then(r=>r.json()).then(j=>console.log(j.session.status, j.session.authenticated, j.session.ready, j.session.lastError))"
```
