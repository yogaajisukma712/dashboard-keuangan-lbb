require('dotenv').config();

const path = require('path');

const { parseExcludedGroupNames } = require('./group-filters');

const authDataPath = process.env.WWEBJS_DATA_PATH || '/app/.wwebjs_auth';

module.exports = {
  port: Number(process.env.WHATSAPP_BOT_PORT || 3000),
  flaskBaseUrl: process.env.WHATSAPP_FLASK_BASE_URL || 'http://web:5000',
  flaskBotToken: process.env.WHATSAPP_BOT_TOKEN || '',
  authDataPath,
  authBackupPath: process.env.WWEBJS_BACKUP_PATH || path.join(authDataPath, '_backups'),
  clientId: process.env.WWEBJS_CLIENT_ID || 'billing-supersmart',
  chromiumPath: process.env.PUPPETEER_EXECUTABLE_PATH || '/usr/bin/chromium',
  defaultMessageLimit: Number(process.env.WHATSAPP_SYNC_MESSAGE_LIMIT || 500),
  excludedGroupNames: parseExcludedGroupNames(
    process.env.WHATSAPP_EXCLUDED_GROUP_NAMES || 'VPS / RDP MURAH III',
  ),
};
