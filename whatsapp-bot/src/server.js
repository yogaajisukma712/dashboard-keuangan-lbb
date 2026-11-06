const express = require('express');
const { timingSafeEqual } = require('crypto');

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

app.use((req, res, next) => {
  if (req.path === '/health') return next();
  const expected = Buffer.from(config.flaskBotToken);
  const provided = Buffer.from(req.get('X-Bot-Token') || '');
  if (!expected.length || expected.length !== provided.length || !timingSafeEqual(expected, provided)) {
    return res.status(401).json({ ok: false, error: 'Unauthorized bot token' });
  }
  return next();
});

app.use(express.json({ limit: '25mb' }));

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
  const { status, authenticated, ready } = getSessionState();
  res.json({ ok: true, service: 'whatsapp-bot', session: { status, authenticated, ready } });
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
    if (req.body?.dryRun === true) {
      const to = String(req.body?.to || '').trim();
      const message = String(req.body?.message || '').trim();
      const attachment = req.body?.attachment || null;
      if (!to || !message) {
        res.status(400).json({ ok: false, error: 'to dan message wajib diisi' });
        return;
      }
      if (attachment && (!attachment.data || !attachment.filename)) {
        res.status(400).json({ ok: false, error: 'attachment data dan filename wajib diisi' });
        return;
      }
      res.json({
        ok: true,
        dryRun: true,
        result: {
          to,
          hasAttachment: Boolean(attachment),
          filename: attachment?.filename || null,
          attachmentBytes: attachment?.data
            ? Buffer.from(String(attachment.data), 'base64').length
            : 0,
          messageId: 'dry-run-message',
        },
      });
      return;
    }
    const state = getSessionState();
    if (!state.ready || !state.authenticated) {
      res.status(503).json({
        ok: false,
        error: 'WhatsApp session belum siap. Coba lagi setelah status ready.',
        status: state.status,
      });
      return;
    }
    const result = await sendDirectMessage(req.body?.to, req.body?.message, req.body?.attachment);
    res.json({ ok: true, result });
  } catch (error) {
    res.status(error.statusCode || 500).json({ ok: false, error: error.message });
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
