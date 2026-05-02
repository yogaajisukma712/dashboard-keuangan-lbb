const config = require('./config');

async function postSyncPayload(payload) {
  const response = await fetch(`${config.flaskBaseUrl}/api/whatsapp/sync`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-WhatsApp-Bot-Token': config.flaskBotToken,
    },
    body: JSON.stringify(payload),
  });

  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error(`Flask sync failed with status ${response.status}`);
    error.details = data;
    throw error;
  }
  return data;
}

module.exports = {
  postSyncPayload,
};
