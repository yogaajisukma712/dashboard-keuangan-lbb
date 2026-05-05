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
  syncGroupsAndMessages,
} = require('./whatsapp-client');
const { backupPathFor } = require('./session-backup');

const app = express();

app.use(express.json({ limit: '25mb' }));

function pxToInches(value) {
  return `${Math.max(value, 1) / 96}in`;
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
    await page.emulateMediaType('print');
    await page.addStyleTag({
      content: `
        @page { margin: 0; }
        html, body { margin: 0 !important; padding: 0 !important; background: #fff !important; }
        .fee-slip-wrapper { padding: 0 !important; margin: 0 !important; }
        .fee-slip-document { margin: 0 auto !important; box-shadow: none !important; }
      `,
    });
    await page.evaluate(() => (document.fonts ? document.fonts.ready : Promise.resolve()));

    const selector = options.selector || '.fee-slip-document';
    const dimensions = await page.evaluate((targetSelector) => {
      const target = document.querySelector(targetSelector) || document.body;
      const rect = target.getBoundingClientRect();
      const styles = window.getComputedStyle(target);
      const marginX = parseFloat(styles.marginLeft || '0') + parseFloat(styles.marginRight || '0');
      const marginY = parseFloat(styles.marginTop || '0') + parseFloat(styles.marginBottom || '0');
      return {
        width: Math.ceil(Math.max(rect.width + marginX + 24, document.documentElement.scrollWidth)),
        height: Math.ceil(Math.max(rect.height + marginY + 24, document.documentElement.scrollHeight)),
      };
    }, selector);

    return await page.pdf({
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
    });
    res.json({
      ok: true,
      pdf_base64: Buffer.from(pdf).toString('base64'),
      page_mode: 'single-page-fit-content',
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
    res.status(500).json({ ok: false, error: error.message, details: error.details || null });
  }
});

app.post('/sync/messages/full', async (req, res) => {
  try {
    const groupIds = Array.isArray(req.body?.groupIds) ? req.body.groupIds : null;
    const result = await syncGroupsAndMessages({ groupIds, fullSync: true });
    res.json({ ok: true, result });
  } catch (error) {
    res.status(500).json({ ok: false, error: error.message, details: error.details || null });
  }
});

app.post('/sync/group/:groupId/messages', async (req, res) => {
  try {
    const limit = Number(req.body?.limit || config.defaultMessageLimit);
    const result = await syncGroupsAndMessages({
      groupIds: [req.params.groupId],
      limit,
    });
    res.json({ ok: true, result });
  } catch (error) {
    res.status(500).json({ ok: false, error: error.message, details: error.details || null });
  }
});

app.post('/sync/messages', async (req, res) => {
  try {
    const limit = Number(req.body?.limit || config.defaultMessageLimit);
    const groupIds = Array.isArray(req.body?.groupIds) ? req.body.groupIds : null;
    const result = await syncGroupsAndMessages({ groupIds, limit });
    res.json({ ok: true, result });
  } catch (error) {
    res.status(500).json({ ok: false, error: error.message, details: error.details || null });
  }
});

app.listen(config.port, () => {
  console.log(`whatsapp-bot listening on ${config.port}`);
});
