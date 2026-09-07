const express = require('express');
const puppeteer = require('puppeteer');

const config = require('./config');
const {
  startClient,
  getSessionState,
  getSessionManagementState,
  listGroups,
  sendDirectMessage,
  backupSession,
  deleteBackup,
  logout,
  recoverFromRuntimeError,
  restoreSession,
  startRuntimeSupervisor,
  syncGroupsAndMessages,
} = require('./whatsapp-client');
const { backupPathFor } = require('./session-backup');

const app = express();

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

function logFatalRuntime(kind, errorLike) {
  const message = errorLike instanceof Error ? errorLike.stack || errorLike.message : String(errorLike);
  console.error(`[whatsapp-bot:${kind}]`, message);
}

process.on('unhandledRejection', (reason) => {
  void recoverFromRuntimeError(reason, 'unhandledRejection').then((recovered) => {
    if (!recovered) {
      logFatalRuntime('unhandledRejection', reason);
    }
  });
});

process.on('uncaughtException', (error) => {
  void recoverFromRuntimeError(error, 'uncaughtException').then((recovered) => {
    if (!recovered) {
      logFatalRuntime('uncaughtException', error);
      process.exit(1);
    }
  });
});

app.get('/health', (_req, res) => {
  res.json({ ok: true, service: 'whatsapp-bot', session: getSessionState() });
});

// ===== File storage untuk dashboard serverless (Vercel) =====
// Dashboard Vercel PUT file mentah ke sini (auth X-Bot-Token); file disimpan
// di volume bot. Serving via GET (auth sama, dashboard yang mem-broadcast).
const FILE_ROOT = process.env.FILE_ROOT_PATH || '/app/uploads';
const FILE_TOKEN = process.env.WHATSAPP_BOT_TOKEN || '';

function _fileSafePath(relativeName) {
  const path = require('path');
  const resolved = path.resolve(FILE_ROOT, relativeName);
  if (!resolved.startsWith(path.resolve(FILE_ROOT) + path.sep)) return null;
  return resolved;
}

app.put('/files/*', (req, res) => {
  if (!FILE_TOKEN || req.get('X-Bot-Token') !== FILE_TOKEN) {
    return res.status(401).json({ ok: false, error: 'Unauthorized bot token' });
  }
  let relativeName;
  try {
    relativeName = decodeURIComponent(req.path.replace(/^\/files\//, ''));
  } catch (err) {
    return res.status(400).json({ ok: false, error: 'Nama file tidak valid' });
  }
  const target = _fileSafePath(relativeName);
  if (!target) return res.status(400).json({ ok: false, error: 'Path tidak valid' });
  const fs = require('fs');
  const path = require('path');
  fs.mkdirSync(path.dirname(target), { recursive: true });
  const chunks = [];
  let size = 0;
  let aborted = false;
  req.on('data', (chunk) => {
    if (aborted) return;
    size += chunk.length;
    if (size > 25 * 1024 * 1024) {
      aborted = true;
      res.status(413).json({ ok: false, error: 'File terlalu besar (maks 25MB)' });
      req.destroy();
      return;
    }
    chunks.push(chunk);
  });
  req.on('end', () => {
    if (aborted) return;
    try {
      fs.writeFileSync(target, Buffer.concat(chunks));
      res.json({ ok: true, path: relativeName, bytes: size });
    } catch (err) {
      res.status(500).json({ ok: false, error: err.message });
    }
  });
  req.on('error', () => res.status(500).end());
});

app.get('/files/*', (req, res) => {
  if (!FILE_TOKEN || req.get('X-Bot-Token') !== FILE_TOKEN) {
    return res.status(401).json({ ok: false, error: 'Unauthorized bot token' });
  }
  let relativeName;
  try {
    relativeName = decodeURIComponent(req.path.replace(/^\/files\//, ''));
  } catch (err) {
    return res.status(400).json({ ok: false, error: 'Nama file tidak valid' });
  }
  const target = _fileSafePath(relativeName);
  if (!target) return res.status(400).json({ ok: false, error: 'Path tidak valid' });
  const fs = require('fs');
  if (!fs.existsSync(target)) return res.status(404).json({ ok: false, error: 'File tidak ditemukan' });
  res.sendFile(target);
});

app.get('/session', (_req, res) => {
  res.json({ ok: true, session: getSessionState() });
});

app.get('/session/management', (_req, res) => {
  try {
    res.json({ ok: true, management: getSessionManagementState() });
  } catch (error) {
    res.status(500).json({ ok: false, error: error.message });
  }
});

app.post('/session/initialize', async (_req, res) => {
  try {
    await startClient();
    res.json({ ok: true, session: getSessionState() });
  } catch (error) {
    res.status(500).json({ ok: false, error: error.message });
  }
});

app.post('/session/logout', async (_req, res) => {
  try {
    await logout();
    res.json({ ok: true, session: getSessionState() });
  } catch (error) {
    res.status(500).json({ ok: false, error: error.message });
  }
});

app.post('/session/backup', async (_req, res) => {
  try {
    const backup = await backupSession();
    res.json({ ok: true, backup, management: getSessionManagementState() });
  } catch (error) {
    res.status(500).json({ ok: false, error: error.message });
  }
});

app.post('/session/restore', async (req, res) => {
  try {
    const filename = req.body?.filename;
    if (!filename) {
      res.status(400).json({ ok: false, error: 'filename wajib diisi' });
      return;
    }
    const restore = await restoreSession(filename);
    res.json({ ok: true, restore, session: getSessionState(), management: getSessionManagementState() });
  } catch (error) {
    res.status(500).json({ ok: false, error: error.message });
  }
});

app.delete('/session/backup/:filename', async (req, res) => {
  try {
    const result = await deleteBackup(req.params.filename);
    res.json({ ok: true, result, management: getSessionManagementState() });
  } catch (error) {
    res.status(500).json({ ok: false, error: error.message });
  }
});

app.get('/session/backup/:filename/download', (req, res) => {
  try {
    const filePath = backupPathFor(req.params.filename);
    res.download(filePath, req.params.filename);
  } catch (error) {
    res.status(404).json({ ok: false, error: error.message });
  }
});

app.get('/groups', async (_req, res) => {
  try {
    // Fail-fast: jika sesi belum authenticated, jangan tunggu ready gate 120s
    // (menghindari pile-up hang di proxy dashboard/Vercel).
    const st = getSessionState();
    if (!st.authenticated && !st.ready) {
      return res.status(503).json({
        ok: false,
        error: 'WhatsApp session belum ready (awaiting QR). Scan QR terlebih dahulu.',
        status: st.status,
      });
    }
    const groups = await listGroups();
    res.json({
      ok: true,
      groups: groups.map((chat) => ({
        id: chat.id?._serialized,
        name: chat.name,
        participantCount: Array.isArray(chat.participants) ? chat.participants.length : 0,
      })),
    });
  } catch (error) {
    res.status(500).json({ ok: false, error: error.message });
  }
});

app.post('/messages/send', async (req, res) => {
  try {
    const result = await sendDirectMessage(req.body?.to, req.body?.message, req.body?.attachment);
    res.json({ ok: true, result });
  } catch (error) {
    res.status(error.statusCode || 500).json({ ok: false, error: error.message });
  }
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
      pageMode: req.body?.pageMode,
    });
    res.json({
      ok: true,
      pdf_base64: Buffer.from(pdf).toString('base64'),
      page_mode: req.body?.pageMode || 'single-page-element-screenshot',
    });
  } catch (error) {
    res.status(500).json({ ok: false, error: error.message });
  }
});

app.post('/sync/groups', async (req, res) => {
  try {
    const fullSync = Boolean(req.body?.full_sync || req.body?.fullSync);
    const rawLimit = req.body?.limit;
    const limit = rawLimit == null ? config.defaultMessageLimit : Number(rawLimit);
    const result = await syncGroupsAndMessages({ limit, fullSync });
    res.json({ ok: true, result });
  } catch (error) {
    res.status(error.statusCode || 500).json({ ok: false, error: error.message, details: error.details || null });
  }
});

app.post('/sync/messages/full', async (req, res) => {
  try {
    const groupIds = Array.isArray(req.body?.groupIds) ? req.body.groupIds : null;
    const result = await syncGroupsAndMessages({ groupIds, fullSync: true });
    res.json({ ok: true, result });
  } catch (error) {
    res.status(error.statusCode || 500).json({ ok: false, error: error.message, details: error.details || null });
  }
});

app.post('/sync/group/:groupId/messages', async (req, res) => {
  try {
    const limit = Number(req.body?.limit || config.defaultMessageLimit);
    const fullSync = Boolean(req.body?.full_sync || req.body?.fullSync);
    const result = await syncGroupsAndMessages({
      groupIds: [req.params.groupId],
      limit,
      fullSync,
    });
    res.json({ ok: true, result });
  } catch (error) {
    res.status(error.statusCode || 500).json({ ok: false, error: error.message, details: error.details || null });
  }
});

app.post('/sync/messages', async (req, res) => {
  try {
    const limit = Number(req.body?.limit || config.defaultMessageLimit);
    const groupIds = Array.isArray(req.body?.groupIds) ? req.body.groupIds : null;
    const result = await syncGroupsAndMessages({ groupIds, limit });
    res.json({ ok: true, result });
  } catch (error) {
    res.status(error.statusCode || 500).json({ ok: false, error: error.message, details: error.details || null });
  }
});

app.listen(config.port, () => {
  console.log(`whatsapp-bot listening on ${config.port}`);
  startRuntimeSupervisor();
  // Heavy-jobs worker: poll tabel heavy_jobs (Neon) — dashboard INSERT, VM eksekusi
  const { startHeavyJobsWorker } = require('./heavy-jobs');
  startHeavyJobsWorker({
    sendDirectMessage,
    getSessionState,
    config,
  });
});
