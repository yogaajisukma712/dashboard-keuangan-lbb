const test = require('node:test');
const assert = require('node:assert/strict');

const {
  DEFAULT_SYNC_START_AT,
  normalizeSyncStartAt,
  partitionMessagesBySyncStart,
} = require('../src/sync-window');

test('sync window starts at 1 July 2026 WIB by default', () => {
  assert.equal(DEFAULT_SYNC_START_AT, '2026-06-30T17:00:00.000Z');
  assert.equal(normalizeSyncStartAt(), DEFAULT_SYNC_START_AT);
});

test('sync window keeps cutoff and newer messages while preserving invalid timestamps', () => {
  const messages = [
    { id: 'june', timestamp: 1_782_838_799 },
    { id: 'cutoff', timestamp: 1_782_838_800 },
    { id: 'july', timestamp: 1_782_838_801 },
    { id: 'unknown', timestamp: null },
  ];

  const result = partitionMessagesBySyncStart(messages);

  assert.deepEqual(
    result.eligibleMessages.map((message) => message.id),
    ['cutoff', 'july', 'unknown'],
  );
  assert.equal(result.skippedBeforeSyncStartCount, 1);
  assert.equal(result.syncStartAt, DEFAULT_SYNC_START_AT);
});

test('sync window rejects an invalid configured timestamp', () => {
  assert.throws(
    () => partitionMessagesBySyncStart([], 'not-a-date'),
    /Invalid WHATSAPP_SYNC_START_AT/,
  );
});
