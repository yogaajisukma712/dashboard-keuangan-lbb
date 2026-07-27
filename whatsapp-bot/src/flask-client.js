const config = require('./config');

async function postSingleSyncPayload(payload) {
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

function chunkMessages(messages, batchSize) {
  const chunks = [];
  for (let offset = 0; offset < messages.length; offset += batchSize) {
    chunks.push(messages.slice(offset, offset + batchSize));
  }
  return chunks;
}

function mergeSyncResult(target, response) {
  const result = response?.result || {};
  target.groups = Math.max(target.groups, Number(result.groups || 0));
  target.contacts = Math.max(target.contacts, Number(result.contacts || 0));
  target.memberships += Number(result.memberships || 0);
  target.messages += Number(result.messages || 0);
  target.evaluations += Number(result.evaluations || 0);
  target.linked_attendance += Number(result.linked_attendance || 0);
  target.excluded_groups = result.excluded_groups || target.excluded_groups;
}

async function postSyncPayload(
  payload,
  { messageBatchSize = config.syncMessageBatchSize } = {},
) {
  const messages = Array.isArray(payload.messages) ? payload.messages : [];
  const batchSize = Number.isFinite(messageBatchSize) && messageBatchSize > 0
    ? Math.floor(messageBatchSize)
    : 2000;

  if (messages.length <= batchSize) {
    return postSingleSyncPayload(payload);
  }

  const batches = chunkMessages(messages, batchSize);
  const aggregate = {
    groups: 0,
    contacts: 0,
    memberships: 0,
    messages: 0,
    evaluations: 0,
    linked_attendance: 0,
    excluded_groups: [],
  };

  for (const [index, messageBatch] of batches.entries()) {
    const response = await postSingleSyncPayload({
      ...payload,
      memberships: index === 0 ? payload.memberships : [],
      messages: messageBatch,
    });
    mergeSyncResult(aggregate, response);
  }

  return {
    ok: true,
    result: aggregate,
    batches: batches.length,
  };
}

module.exports = {
  chunkMessages,
  mergeSyncResult,
  postSingleSyncPayload,
  postSyncPayload,
};
