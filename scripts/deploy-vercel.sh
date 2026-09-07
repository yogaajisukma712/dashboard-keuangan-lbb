#!/usr/bin/env bash
# Deploy dashboard ke Vercel dari repo utama. Regenerasi VERSION otomatis.
set -Eeuo pipefail
cd "$(dirname "$0")/.."
COMMIT=$(git rev-parse --short HEAD 2>/dev/null || echo nocache)
DATE=$(TZ=Asia/Jakarta date +%Y%m%d)
BASE=$(head -1 VERSION 2>/dev/null | cut -d+ -f1)
printf "%s+%s.%s\n" "${BASE:-1.0.0}" "$DATE" "$COMMIT" > VERSION
echo "[deploy] VERSION=$(cat VERSION)"
STAGE=/tmp/vercel-deploy
rm -rf "$STAGE" && mkdir -p "$STAGE/api"
rsync -a --exclude=__pycache__ --exclude=*.pyc app/ "$STAGE/app/"
cp run.py config.py requirements.txt vercel.json VERSION "$STAGE/"
cp api/index.py "$STAGE/api/"
cp logo.png logo_panjang.png "$STAGE/" 2>/dev/null || true
mkdir -p "$STAGE/.vercel"
cat > "$STAGE/.vercel/project.json" <<'EOF'
{
  "projectId": "prj_Fvlx3HeQBQ6FONGxitY5LSo7eMZR",
  "orgId": "team_gA7LBEZ4YKAh79VYwmgT33Ac",
  "project": "lbb-dashboard"
}
EOF
VC=${VERCEL_TOKEN:-$(cat "api key penting/vercel.key" 2>/dev/null)}
[ -n "$VC" ] || { echo "VERCEL_TOKEN kosong"; exit 1; }
cd "$STAGE"
git init -q 2>/dev/null; git add -A 2>/dev/null
git -c user.email=deploy@lbb -c user.name=deploy commit -qm "staging $(cat VERSION)" 2>/dev/null || true
vercel deploy --prod --token "$VC" --yes
