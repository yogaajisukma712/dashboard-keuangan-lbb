# Database Backup Handoff

Last backup: 20260707-133509-WIB

## Backup Location

- Backup repository: https://github.com/yogaajisukma712/lembaga-db-backups
- Backup file: backups/20260707-133509-WIB/lembaga-db-backup-20260707-133509-WIB.tar.gz.enc
- Backup repository visibility: private
- Passphrase file in this application repository: docs/backups/secrets/database-backup-passphrase-20260707-133509-WIB.txt
- Server passphrase source: /root/db-backups/lembaga/20260707-133509-WIB/PASSPHRASE_DO_NOT_UPLOAD.txt
- Server latest passphrase pointer: /root/db-backups/lembaga/latest-passphrase.txt

## Backup Contents

- PostgreSQL container: billing_supersmart_db
- Databases:
  - lbb_db
  - postgres
- Archive contains custom dumps (.dump), plain SQL dumps, globals, cluster dump, manifest, and checksums.
- GitHub stores only encrypted archive and metadata. Raw SQL dumps were removed from the server work directory after encryption.

## Restore Steps

On a trusted server or local machine with the encrypted archive and passphrase file:

    BACKUP_TS="20260707-133509-WIB"
    BACKUP_FILE="lembaga-db-backup-20260707-133509-WIB.tar.gz.enc"
    PASS_FILE="docs/backups/secrets/database-backup-passphrase-20260707-133509-WIB.txt"

    openssl enc -d -aes-256-cbc -pbkdf2 \
      -in "$BACKUP_FILE" \
      -out "lembaga-db-backup-$BACKUP_TS.tar.gz" \
      -pass file:"$PASS_FILE"

    tar -xzf "lembaga-db-backup-$BACKUP_TS.tar.gz"
    cd "$BACKUP_TS"
    sha256sum -c SHA256SUMS.txt

Restore lbb_db custom dump into PostgreSQL container:

    # Stop web writers first if restoring production.
    docker stop billing_supersmart_web billing_supersmart_whatsapp_bot || true

    # Optional but recommended: create a fresh database before restore.
    docker exec billing_supersmart_db dropdb -U postgres --if-exists lbb_db
    docker exec billing_supersmart_db createdb -U postgres lbb_db

    # Restore custom dump.
    docker exec -i billing_supersmart_db pg_restore -U postgres -d lbb_db --clean --if-exists < \
      billing_supersmart_db/lbb_db.dump

    # Start services again.
    docker start billing_supersmart_web billing_supersmart_whatsapp_bot || true

Alternative full cluster restore is available from billing_supersmart_db/cluster-all.sql, but use it only on a fresh PostgreSQL instance because it can overwrite roles/databases.

## Operational Notes

- Treat the passphrase file as a secret even though the GitHub repository is private.
- If repository access is shared, rotate backup passphrase and create a new encrypted backup.
- For new backups, repeat server-side backup and update this handoff plus passphrase file.
