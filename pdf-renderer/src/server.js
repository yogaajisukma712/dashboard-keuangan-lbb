const { timingSafeEqual } = require('crypto');
const express = require('express');
const puppeteer = require('puppeteer-core');
const config = require('./config');

const app = express();

app.use((req, res, next) => {
  if (req.path === '/health') return next();
  const expected = Buffer.from(config.token);
  const provided = Buffer.from(req.get('X-Bot-Token') || '');
  if (!expected.length || expected.length !== provided.length || !timingSafeEqual(expected, provided)) {
    return res.status(401).json({ ok: false, error: 'Unauthorized bot token' });
  }
  return next();
});

app.use(express.json({ limit: '25mb' }));

function pxToInches(value) {
  return `${Math.max(value, 1) / 96}in`;
}

function pngDimensions(buffer) {
  const isPng =
    buffer.length >= 24 &&
    buffer[0] === 0x89 &&
    buffer[1] === 0x50 &&
    buffer[2] === 0x4e &&
    buffer[3] === 0x47;
  if (!isPng) {
    throw new Error('Rendered slip screenshot is not a PNG');
  }
  return {
    width: buffer.readUInt32BE(16),
    height: buffer.readUInt32BE(20),
  };
}

async function renderHtmlToSinglePagePdf(html, options = {}) {
  const browser = await puppeteer.launch({
    executablePath: config.chromiumPath,
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage'],
  });

  try {
    const page = await browser.newPage();
    await page.setViewport({ width: 920, height: 1400, deviceScaleFactor: 1 });
    const baseTag = options.baseUrl ? `<base href="${options.baseUrl}">` : '';
    await page.setContent(`${baseTag}${html}`, {
      waitUntil: ['load', 'networkidle0'],
      timeout: 45000,
    });
    await page.emulateMediaType('screen');
    await page.addStyleTag({
      content: `
        html, body { margin: 0 !important; padding: 0 !important; background: #fff !important; }
        #topbar, #sidebar, .flash-container, .no-print { display: none !important; }
        #main-content { margin: 0 !important; padding: 0 !important; min-height: auto !important; }
        .container, .container-fluid { max-width: 100% !important; padding: 0 !important; margin: 0 !important; }
        .fee-slip-wrapper { padding: 0 !important; margin: 0 !important; }
        .fee-slip-document { margin: 0 auto !important; box-shadow: none !important; }
      `,
    });
    await page.evaluate(() => (document.fonts ? document.fonts.ready : Promise.resolve()));

    const selector = options.selector || '.fee-slip-document';
    const target = await page.$(selector);
    if (!target) {
      throw new Error(`PDF target element not found: ${selector}`);
    }
    if (options.pageMode === 'standard-a4') {
      return await page.pdf({
        format: 'A4',
        printBackground: true,
        preferCSSPageSize: true,
        margin: { top: '0', right: '0', bottom: '0', left: '0' },
      });
    }
    // Single-page PDF asli (teks tajam, bukan screenshot): satu halaman dengan
    // tinggi mengikuti konten. Default baru; dipakai bila pageMode bukan
    // 'standard-a4' atau 'single-page-element-screenshot'.
    if (options.pageMode !== 'single-page-element-screenshot') {
      // Ukur elemen target + isolasi agar hanya elemen slip yang dirender,
      // tanpa whitespace dari body di sekitarnya.
      const box = await page.evaluate((sel) => {
        const el = document.querySelector(sel);
        if (!el) return null;
        // Lepaskan margin/transform yang bisa menambah ruang kosong.
        el.style.margin = '0';
        const rect = el.getBoundingClientRect();
        return {
          width: Math.ceil(rect.width),
          // scrollHeight menangkap konten yang melebihi tinggi viewport.
          height: Math.ceil(Math.max(rect.height, el.scrollHeight)),
        };
      }, selector);
      if (!box || box.width < 1 || box.height < 1) {
        throw new Error(`PDF target element has no size: ${selector}`);
      }
      // Render hanya elemen slip sebagai satu-satunya isi dokumen agar
      // page.pdf menghasilkan tepat satu halaman seukuran konten.
      // PENTING: semua <style> template fee slip ada di {% block scripts %},
      // yaitu anak <body> juga (bukan <head>) — jadi document.body.innerHTML=''
      // ikut menghapusnya. Simpan dulu semua <style>, baru wipe body, lalu
      // pasang kembali style + clone agar CSS slip tetap berlaku.
      await page.evaluate((sel) => {
        const el = document.querySelector(sel);
        const clone = el.cloneNode(true);
        const styleTags = Array.from(document.querySelectorAll('style')).map(s => s.cloneNode(true));
        document.body.innerHTML = '';
        styleTags.forEach(s => document.body.appendChild(s));
        document.body.appendChild(clone);
        document.body.style.margin = '0';
        document.body.style.padding = '0';
      }, selector);
      await page.evaluate(() => (document.fonts ? document.fonts.ready : Promise.resolve()));
      return await page.pdf({
        printBackground: true,
        preferCSSPageSize: false,
        width: pxToInches(box.width),
        height: pxToInches(box.height),
        pageRanges: '1',
        margin: { top: '0', right: '0', bottom: '0', left: '0' },
      });
    }
    const screenshot = await target.screenshot({
      type: 'png',
      omitBackground: false,
      captureBeyondViewport: true,
    });
    const dimensions = pngDimensions(screenshot);

    const pdfPage = await browser.newPage();
    await pdfPage.setViewport({
      width: dimensions.width,
      height: dimensions.height,
      deviceScaleFactor: 1,
    });
    await pdfPage.setContent(
      `<!doctype html>
      <html>
        <head>
          <style>
            @page { margin: 0; size: ${dimensions.width}px ${dimensions.height}px; }
            html, body { margin: 0; padding: 0; width: ${dimensions.width}px; height: ${dimensions.height}px; overflow: hidden; background: #fff; }
            img { display: block; width: ${dimensions.width}px; height: ${dimensions.height}px; }
          </style>
        </head>
        <body><img src="data:image/png;base64,${screenshot.toString('base64')}" alt="Fee Slip"></body>
      </html>`,
      { waitUntil: 'load' },
    );

    return await pdfPage.pdf({
      printBackground: true,
      preferCSSPageSize: false,
      width: pxToInches(dimensions.width),
      height: pxToInches(dimensions.height),
      margin: { top: '0', right: '0', bottom: '0', left: '0' },
    });
  } finally {
    await browser.close();
  }
}

app.get('/health', (req, res) => {
  res.json({ ok: true, service: 'pdf-renderer' });
});

app.post('/render/pdf', async (req, res) => {
  try {
    const html = req.body?.html;
    if (!html || typeof html !== 'string') {
      res.status(400).json({ ok: false, error: 'html wajib diisi' });
      return;
    }
    const pdf = await renderHtmlToSinglePagePdf(html, {
      baseUrl: req.body?.baseUrl,
      selector: req.body?.selector,
      pageMode: req.body?.pageMode || 'single-page-native',
    });
    res.json({ ok: true, pdf_base64: Buffer.from(pdf).toString('base64') });
  } catch (error) {
    res.status(500).json({ ok: false, error: error.message });
  }
});

app.listen(config.port, () => {
  console.log(`pdf-renderer listening on :${config.port}`);
});
