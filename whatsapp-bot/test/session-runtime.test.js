const fs = require('fs');
const os = require('os');
const path = require('path');
const test = require('node:test');
const assert = require('node:assert/strict');

const {
  clearChromiumSingletonLocks,
  createInitialState,
  extractSelfIdentity,
  failSyncProgress,
  finishSyncProgress,
  isRecoverableWhatsAppRuntimeError,
  startSyncProgress,
  updateSyncProgress,
} = require('../src/session-runtime');

test('clearChromiumSingletonLocks removes broken Chromium singleton symlinks', () => {
  const tempRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'wa-locks-'));
  const sessionDir = path.join(tempRoot, 'session-billing-supersmart');
  fs.mkdirSync(sessionDir, { recursive: true });

  const lockPath = path.join(sessionDir, 'SingletonLock');
  const socketPath = path.join(sessionDir, 'SingletonSocket');
  const cookiePath = path.join(sessionDir, 'SingletonCookie');
  fs.symlinkSync('missing-host-26', lockPath);
  fs.symlinkSync('/tmp/.org.chromium.Chromium.dead/SingletonSocket', socketPath);
  fs.symlinkSync('1234567890', cookiePath);

  assert.doesNotThrow(() => fs.lstatSync(lockPath));
  assert.doesNotThrow(() => fs.lstatSync(socketPath));
  assert.doesNotThrow(() => fs.lstatSync(cookiePath));
  assert.doesNotThrow(() => clearChromiumSingletonLocks(tempRoot));
  assert.throws(() => fs.lstatSync(lockPath));
  assert.throws(() => fs.lstatSync(socketPath));
  assert.throws(() => fs.lstatSync(cookiePath));

  fs.rmSync(tempRoot, { recursive: true, force: true });
});

test('isRecoverableWhatsAppRuntimeError detects transient frame/navigation failures', () => {
  assert.equal(
    isRecoverableWhatsAppRuntimeError(
      new Error('Execution context was destroyed, most likely because of a navigation.'),
    ),
    true,
  );
  assert.equal(
    isRecoverableWhatsAppRuntimeError(
      new Error("Attempted to use detached Frame 'ABC123'."),
    ),
    true,
  );
  assert.equal(
    isRecoverableWhatsAppRuntimeError(new Error('Authentication failure')),
    false,
  );
});

test('extractSelfIdentity uses client.info instead of getMe', () => {
  const result = extractSelfIdentity({
    info: {
      wid: { _serialized: '6281234567890@c.us' },
      pushname: 'Bot LBB',
      platform: 'android',
    },
  });

  assert.deepEqual(result, {
    wid: '6281234567890@c.us',
    phone_number: '6281234567890',
    pushname: 'Bot LBB',
    platform: 'android',
  });
});

test('sync progress state tracks start update finish without losing counters', () => {
  const state = createInitialState();

  startSyncProgress(state, { totalGroups: 4, fullSync: true });
  updateSyncProgress(state, {
    phase: 'syncing_group',
    processedGroups: 2,
    currentGroupName: 'English Ratih',
    scannedMessages: 18,
    relevantMessages: 3,
  });
  finishSyncProgress(state, {
    storedMessages: 18,
    evaluationCount: 3,
    linkedAttendanceCount: 2,
  });

  assert.equal(state.syncInProgress, false);
  assert.equal(state.syncProgress.phase, 'completed');
  assert.equal(state.syncProgress.totalGroups, 4);
  assert.equal(state.syncProgress.processedGroups, 2);
  assert.equal(state.syncProgress.storedMessages, 18);
  assert.equal(state.syncProgress.evaluationCount, 3);
  assert.equal(state.syncProgress.linkedAttendanceCount, 2);
  assert.ok(state.syncProgress.startedAt);
  assert.ok(state.syncProgress.finishedAt);
});

test('failSyncProgress stores raw runtime error message for dashboard polling', () => {
  const state = createInitialState();

  startSyncProgress(state, { totalGroups: 2 });
  failSyncProgress(state, new Error('Bot fetch timeout'));

  assert.equal(state.syncInProgress, false);
  assert.equal(state.syncProgress.phase, 'failed');
  assert.equal(state.syncProgress.error, 'Bot fetch timeout');
  assert.ok(state.syncProgress.finishedAt);
});
