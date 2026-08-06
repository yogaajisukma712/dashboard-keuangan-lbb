#!/usr/bin/env bash
set -Eeuo pipefail

# Uji offline logika seleksi retensi lembaga-daily-backup.sh menggunakan fixture.
# Meniru PERSIS pipeline jq/sort + pengaman keras yang dipasang di skrip utama,
# lalu membuktikan: (1) tag run saat ini tidak pernah terpilih untuk dihapus,
# (2) hanya rilis daily-* tertua di luar 14 yang terpilih, (3) seri pada
# createdAt tidak berpengaruh karena pengurutan memakai nama tag.

command -v jq >/dev/null || { echo "jq wajib tersedia untuk uji ini" >&2; exit 1; }

readonly GITHUB_RETENTION=14
readonly RETENTION_DELETE_LIMIT=10
readonly tag="daily-20260806-142905-WIB"   # tag run saat ini (paling baru)

# Fixture: 18 rilis daily-* (tag run saat ini + 17 hari berurutan) dengan
# createdAt SERI/identik seperti seed produksi, ditambah dua rilis non-daily
# yang harus diabaikan. Urutan array sengaja diacak dan tag run saat ini
# diletakkan di tengah untuk memastikan hasil tidak bergantung urutan masukan.
fixture_json='[
  {"tagName":"daily-20260723-000050-WIB","createdAt":"2026-07-07T06:36:00Z"},
  {"tagName":"daily-20260731-000050-WIB","createdAt":"2026-07-07T06:36:00Z"},
  {"tagName":"daily-20260722-000050-WIB","createdAt":"2026-07-07T06:36:00Z"},
  {"tagName":"daily-20260806-142905-WIB","createdAt":"2026-07-07T06:36:00Z"},
  {"tagName":"daily-20260728-000050-WIB","createdAt":"2026-07-07T06:36:00Z"},
  {"tagName":"daily-20260724-000050-WIB","createdAt":"2026-07-07T06:36:00Z"},
  {"tagName":"v1.0.0-config","createdAt":"2026-07-07T06:36:00Z"},
  {"tagName":"daily-20260730-000050-WIB","createdAt":"2026-07-07T06:36:00Z"},
  {"tagName":"daily-20260721-000050-WIB","createdAt":"2026-07-07T06:36:00Z"},
  {"tagName":"daily-20260726-000050-WIB","createdAt":"2026-07-07T06:36:00Z"},
  {"tagName":"daily-20260801-000050-WIB","createdAt":"2026-07-07T06:36:00Z"},
  {"tagName":"daily-20260725-000050-WIB","createdAt":"2026-07-07T06:36:00Z"},
  {"tagName":"daily-20260729-000050-WIB","createdAt":"2026-07-07T06:36:00Z"},
  {"tagName":"latest","createdAt":"2026-07-07T06:36:00Z"},
  {"tagName":"daily-20260802-000050-WIB","createdAt":"2026-07-07T06:36:00Z"},
  {"tagName":"daily-20260727-000050-WIB","createdAt":"2026-07-07T06:36:00Z"},
  {"tagName":"daily-20260803-000050-WIB","createdAt":"2026-07-07T06:36:00Z"},
  {"tagName":"daily-20260720-000050-WIB","createdAt":"2026-07-07T06:36:00Z"},
  {"tagName":"daily-20260804-000050-WIB","createdAt":"2026-07-07T06:36:00Z"},
  {"tagName":"daily-20260805-000050-WIB","createdAt":"2026-07-07T06:36:00Z"}
]'

# --- PERSIS pipeline jq yang dipakai skrip utama (hanya tagName) ---
mapfile -t expired_tags < <(
  printf '%s' "${fixture_json}" \
    | jq -r "map(.tagName) | map(select(startswith(\"daily-\"))) | sort | reverse | .[${GITHUB_RETENTION}:][]"
)

# --- PERSIS pengaman keras yang dipakai skrip utama ---
current_tag_in_list=0
filtered_expired_tags=()
for candidate_tag in "${expired_tags[@]}"; do
  if [[ "${candidate_tag}" == "${tag}" ]]; then
    current_tag_in_list=1
    continue
  fi
  filtered_expired_tags+=("${candidate_tag}")
done
expired_tags=("${filtered_expired_tags[@]}")

echo "Tag run saat ini      : ${tag}"
echo "Jumlah kandidat hapus : ${#expired_tags[@]}"
echo "Kandidat dihapus      : ${expired_tags[*]:-<none>}"
echo "current_tag_in_list   : ${current_tag_in_list}"

status=0

# Asersi 1: tag run saat ini TIDAK PERNAH terpilih untuk dihapus.
for t in "${expired_tags[@]}"; do
  if [[ "${t}" == "${tag}" ]]; then
    echo "GAGAL: tag run saat ini (${tag}) terpilih untuk dihapus" >&2
    status=1
  fi
done

# Asersi 2: hanya 4 rilis daily-* tertua di luar 14 yang terpilih.
expected=(
  "daily-20260723-000050-WIB"
  "daily-20260722-000050-WIB"
  "daily-20260721-000050-WIB"
  "daily-20260720-000050-WIB"
)
if [[ "${expired_tags[*]}" != "${expected[*]}" ]]; then
  echo "GAGAL: daftar hapus tidak sesuai harapan" >&2
  echo "  diharapkan: ${expected[*]}" >&2
  echo "  didapat   : ${expired_tags[*]:-<none>}" >&2
  status=1
fi

# Asersi 3: tidak ada tag non-daily (latest, v1.0.0-config) yang tersentuh.
for t in "${expired_tags[@]}"; do
  if [[ "${t}" != daily-* ]]; then
    echo "GAGAL: tag non-daily terpilih: ${t}" >&2
    status=1
  fi
done

if [[ "${status}" -eq 0 ]]; then
  echo "LULUS: tag saat ini aman, hanya 4 rilis tertua di luar 14 yang terpilih, seri createdAt diabaikan."
fi
exit "${status}"
