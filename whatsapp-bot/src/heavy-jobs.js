'use strict';

/**
 * heavy-jobs worker — polling tabel `heavy_jobs` di Neon.
 * Dashboard (Vercel) INSERT job; VM bot mengeksekusi; VM mati = job menunggu (pending).
 *
 * Job types:
 *  - send_fee_slips_bulk: payload { slips: [{to, message, pdfUrl, filename}] }
 *    → untuk tiap slip: fetch pdfUrl (dari dashboard, via flaskBaseUrl), sendDirectMessage.
 *  - generic_send: payload { to, message, attachment? }
 */

const { Pool } = require('pg');

const POLL_INTERVAL_MS = Number(process.env.HEAVY_JOBS_INTERVAL_MS || 30_000);
const MAX_ATTEMPTS = 3;

function buildPool() {
  const url = process.env.DATABASE_URL || '';
  if (!url) return null;
  // Neon: pastikan ssl. psycopg-style URL + node-postgres ok.
  const cfg = { connectionString: url };
  if (url.includes('neon.tech')) cfg.ssl = { rejectUnauthorized: false };
  return new Pool(cfg);
}

async function claimJob(pool) {
  const { rows } = await pool.query(
    `UPDATE heavy_jobs
       SET status='running', started_at=now()
     WHERE id = (
       SELECT id FROM heavy_jobs
        WHERE status='pending'
        ORDER BY id ASC
        LIMIT 1
        FOR UPDATE SKIP LOCKED
     )
     RETURNING id, job_type, payload, attempts, requested_by`,
  );
  return rows[0] || null;
}

async function finishJob(pool, id, result, error) {
  if (error) {
    const { rows } = await pool.query(
      `UPDATE heavy_jobs
          SET status = CASE WHEN attempts+1 >= $2 THEN 'failed' ELSE 'pending' END,
              attempts = attempts + 1,
              finished_at = CASE WHEN attempts+1 >= $2 THEN now() END,
              error = $3
        WHERE id = $1
        RETURNING status`,
      [id, MAX_ATTEMPTS, String(error).slice(0, 2000)],
    );
    return rows[0]?.status;
  }
  await pool.query(
    `UPDATE heavy_jobs SET status='done', finished_at=now(), result=$2, error=NULL WHERE id=$1`,
    [id, JSON.stringify(result || {})],
  );
  return 'done';
}

async function sendSlip(ctx, slip) {
  const { flaskBaseUrl, flaskBotToken } = require('./config');
  // Dashboard memproses slip (logika kirim + status DB tetap milik Flask);
  // worker hanya memanggil endpoint per-slip yang sinkron ringan.
  const res = await fetch(
    `${flaskBaseUrl}/payroll/api/fee-slip-job/${encodeURIComponent(slip.payoutRef || slip.to)}`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Bot-Token': flaskBotToken || '',
      },
      body: JSON.stringify({ message: slip.message, baseUrl: slip.baseUrl }),
    },
  );
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(`fee-slip-job ${res.status}: ${data.error || res.statusText}`);
  return data;
}

async function runJob(ctx, job) {
  if (job.job_type === 'send_fee_slips_bulk') {
    const slips = job.payload?.slips || [];
    const baseUrl = job.payload?.baseUrl || null;
    const sent = [];
    const skipped = [];
    const failed = [];
    for (const slip of slips) {
      try {
        const r = await sendSlip(ctx, { ...slip, baseUrl });
        if (r.skipped) skipped.push(slip.payoutRef);
        else if (r.sent) sent.push(slip.payoutRef);
        else failed.push(`${slip.payoutRef}: ${r.error}`);
      } catch (e) {
        failed.push(`${slip.payoutRef}: ${e.message}`);
        console.error(`[heavy-jobs] slip gagal ${slip.payoutRef}: ${e.message}`);
      }
    }
    return { sent: sent.length, skipped: skipped.length, failed: failed.length, total: slips.length, detailFailed: failed.slice(0, 20) };
  }
  if (job.job_type === 'generic_send') {
    const r = await sendSlip(ctx, job.payload);
    return { sent: 1 };
  }
  throw new Error(`job_type tak dikenal: ${job.job_type}`);
}

function startHeavyJobsWorker(ctx) {
  // ctx: { sendDirectMessage, getSessionState, config }
  const pool = buildPool();
  if (!pool) {
    console.log('[heavy-jobs] DATABASE_URL kosong — worker OFF');
    return { stop: () => {} };
  }
  let stopped = false;
  let running = false;

  const ensureColumn = (async () => {
    try {
      await pool.query(`ALTER TABLE heavy_jobs ADD COLUMN IF NOT EXISTS attempts INTEGER NOT NULL DEFAULT 0`);
    } catch (e) {
      console.error('[heavy-jobs] kolom attempts:', e.message);
    }
  })();

  const tick = async () => {
    if (stopped || running) return;
    running = true;
    try {
      await ensureColumn;
      const job = await claimJob(pool);
      if (job) {
        console.log(`[heavy-jobs] run job #${job.id} type=${job.job_type}`);
        let result;
        try {
          result = await runJob(ctx, job);
        } catch (e) {
          const st = await finishJob(pool, job.id, null, e);
          console.error(`[heavy-jobs] job #${job.id} gagal → ${st}: ${e.message}`);
          return;
        }
        await finishJob(pool, job.id, result, null);
        console.log(`[heavy-jobs] job #${job.id} selesai`, result);
      }
    } catch (e) {
      console.error('[heavy-jobs] tick error:', e.message);
    } finally {
      running = false;
    }
  };

  // Heartbeat: beri tahu dashboard VM aktif (tiap tick).
  function sendHeartbeat() {
    try {
      const { flaskBaseUrl, flaskBotToken } = require('./config');
      const state = (ctx.getSessionState && ctx.getSessionState()) || {};
      fetch(`${flaskBaseUrl}/api/system/heartbeat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Bot-Token': flaskBotToken || '',
        },
        body: JSON.stringify({
          component: 'vm-bot',
          meta: {
            version: require('../package.json').version || 'unknown',
            session_status: state.status || null,
            authenticated: !!state.authenticated,
            uptime_sec: Math.round(process.uptime()),
          },
        }),
      }).catch(() => {});
    } catch (err) {
      // heartbeat gagal — tidak fatal
    }
  }

  const timer = setInterval(tick, POLL_INTERVAL_MS);
  tick();
  sendHeartbeat();
  setInterval(sendHeartbeat, 5 * 60 * 1000); // tiap 5 menit
  console.log(`[heavy-jobs] worker ON (interval ${POLL_INTERVAL_MS}ms) + heartbeat 5m`);
  return { stop: () => { stopped = true; clearInterval(timer); } };
}

module.exports = { startHeavyJobsWorker };
