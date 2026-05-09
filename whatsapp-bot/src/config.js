require('dotenv').config();

const path = require('path');

const { parseExcludedGroupNames } = require('./group-filters');

const authDataPath = process.env.WWEBJS_DATA_PATH || '/app/.wwebjs_auth';

function numberFromEnv(name, fallback) {
  const value = Number(process.env[name]);
  return Number.isFinite(value) && value > 0 ? value : fallback;
}

function booleanFromEnv(name, fallback) {
  const raw = process.env[name];
  if (raw == null || raw === '') return fallback;
  return ['1', 'true', 'yes', 'on'].includes(String(raw).trim().toLowerCase());
}

const sixHoursMs = 6 * 60 * 60 * 1000;

module.exports = {
  port: numberFromEnv('WHATSAPP_BOT_PORT', 3000),
  flaskBaseUrl: process.env.WHATSAPP_FLASK_BASE_URL || 'http://web:5000',
  flaskBotToken: process.env.WHATSAPP_BOT_TOKEN || '',
  authDataPath,
  authBackupPath: process.env.WWEBJS_BACKUP_PATH || path.join(authDataPath, '_backups'),
  clientId: process.env.WWEBJS_CLIENT_ID || 'billing-supersmart',
  chromiumPath: process.env.PUPPETEER_EXECUTABLE_PATH || '/usr/bin/chromium',
  defaultMessageLimit: numberFromEnv('WHATSAPP_SYNC_MESSAGE_LIMIT', 500),
  autoStart: booleanFromEnv('WHATSAPP_AUTO_START', true),
  autoSyncEnabled: booleanFromEnv('WHATSAPP_AUTO_SYNC_ENABLED', true),
  autoSyncFullSync: booleanFromEnv('WHATSAPP_AUTO_SYNC_FULL_SYNC', true),
  autoSyncIntervalMs: numberFromEnv('WHATSAPP_AUTO_SYNC_INTERVAL_MS', sixHoursMs),
  watchdogIntervalMs: numberFromEnv('WHATSAPP_WATCHDOG_INTERVAL_MS', 60_000),
  reconnectDelayMs: numberFromEnv('WHATSAPP_RECONNECT_DELAY_MS', 15_000),
  readyTimeoutMs: numberFromEnv('WHATSAPP_READY_TIMEOUT_MS', 120_000),
  protocolTimeoutMs: numberFromEnv('PUPPETEER_PROTOCOL_TIMEOUT_MS', 180_000),
  excludedGroupNames: parseExcludedGroupNames(
    process.env.WHATSAPP_EXCLUDED_GROUP_NAMES || 'VPS / RDP MURAH III',
  ),
};
