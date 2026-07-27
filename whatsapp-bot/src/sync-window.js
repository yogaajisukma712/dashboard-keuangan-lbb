const DEFAULT_SYNC_START_AT = '2026-06-30T17:00:00.000Z';

function normalizeSyncStartAt(value = DEFAULT_SYNC_START_AT) {
  const timestamp = Date.parse(value);
  if (!Number.isFinite(timestamp)) {
    throw new Error(`Invalid WHATSAPP_SYNC_START_AT value: ${value}`);
  }
  return new Date(timestamp).toISOString();
}

function partitionMessagesBySyncStart(messages, syncStartAt = DEFAULT_SYNC_START_AT) {
  const normalizedSyncStartAt = normalizeSyncStartAt(syncStartAt);
  const cutoffSeconds = Date.parse(normalizedSyncStartAt) / 1000;
  const eligibleMessages = [];
  let skippedBeforeSyncStartCount = 0;

  for (const message of messages || []) {
    const messageTimestamp = Number(message?.timestamp);
    if (
      Number.isFinite(messageTimestamp)
      && messageTimestamp > 0
      && messageTimestamp < cutoffSeconds
    ) {
      skippedBeforeSyncStartCount += 1;
      continue;
    }
    eligibleMessages.push(message);
  }

  return {
    eligibleMessages,
    skippedBeforeSyncStartCount,
    syncStartAt: normalizedSyncStartAt,
  };
}

module.exports = {
  DEFAULT_SYNC_START_AT,
  normalizeSyncStartAt,
  partitionMessagesBySyncStart,
};
