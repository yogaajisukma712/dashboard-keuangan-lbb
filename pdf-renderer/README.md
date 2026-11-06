# LBB PDF Renderer

Service stateless untuk mengubah HTML menjadi PDF base64. Penyimpanan file ditangani layanan pemanggil.

## Build dan run

```bash
docker build -t lbb-pdf-renderer ./pdf-renderer
docker run --rm -p 3001:3001 -e PDF_RENDERER_TOKEN='token-terpisah' lbb-pdf-renderer
```

Konfigurasi: `PDF_RENDERER_PORT` (default `3001`), `PDF_RENDERER_TOKEN` (wajib untuk render), `PUPPETEER_EXECUTABLE_PATH` (default `/usr/bin/chromium`).

## API

- `GET /health` — tanpa autentikasi; respons `{ "ok": true, "service": "pdf-renderer" }`.
- `POST /render/pdf` — header `X-Bot-Token`; body JSON `html` wajib, opsional `baseUrl`, `selector`, `pageMode` (`standard-a4`, `single-page-element-screenshot`, atau default `single-page-native`); respons `{ "ok": true, "pdf_base64": "..." }`.

```bash
curl -X POST http://localhost:3001/render/pdf \
  -H 'Content-Type: application/json' \
  -H 'X-Bot-Token: token-terpisah' \
  -d '{"html":"<html><body><div class=\"fee-slip-document\">Contoh</div></body></html>"}'
```
