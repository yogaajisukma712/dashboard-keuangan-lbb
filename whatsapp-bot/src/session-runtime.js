const fs = require('fs');
const path = require('path');

function createInitialState() {
  return {
    status: 'idle',
    authenticated: false,
    ready: false,
    qr: null,
    qrDataUrl: null,
    lastError: null,
    lastSyncAt: null,
    lastReadyAt: null,
    lastRestartAt: null,
    reconnectAttempts: 0,
    me: null,
    syncInProgress: false,
    syncProgress: createInitialSyncProgress(),
    autoSync: createInitialAutoSyncState(),
  };
}

function createInitialSyncProgress() {
  return {
    phase: 'idle',
    fullSync: false,
    startedAt: null,
    finishedAt: null,
    totalGroups: 0,
    processedGroups: 0,
    currentGroupId: null,
    currentGroupName: null,
    scannedMessages: 0,
    relevantMessages: 0,
    storedMessages: 0,
    evaluationCount: 0,
    linkedAttendanceCount: 0,
    error: null,
  };
}

function createInitialAutoSyncState() {
  return {
    enabled: false,
    intervalMs: null,
    fullSync: true,
    nextRunAt: null,
    lastStartedAt: null,
    lastFinishedAt: null,
    lastError: null,
    runCount: 0,
    skipCount: 0,
    lastResult: null,
  };
}

function errorMessage(errorLike) {
  if (!errorLike) return '';
  if (typeof errorLike === 'string') return errorLike;
  if (typeof errorLike.message === 'string') return errorLike.message;
  return String(errorLike);
}

function isRecoverableWhatsAppRuntimeError(errorLike) {
  const message = errorMessage(errorLike);
  return [
    'Execution context was destroyed',
    'Attempted to use detached Frame',
    'Protocol error',
    'Runtime.callFunctionOn timed out',
    'Target closed',
    'Session closed',
    'Navigation timeout',
    'ERR_NAME_NOT_RESOLVED',
    'ERR_INTERNET_DISCONNECTED',
    'net::ERR',
  ].some((needle) => message.includes(needle));
}

function jidToPhone(jid) {
  return String(jid || '').split('@')[0] || '';
}

function extractSelfIdentity(botClient) {
  const wid = botClient?.info?.wid?._serialized || botClient?.info?.wid?.user || null;
  return {
    wid,
    phone_number: jidToPhone(wid),
    pushname: botClient?.info?.pushname || null,
    platform: botClient?.info?.platform || null,
  };
}

function resetSessionState(target, overrides = {}) {
  Object.assign(target, createInitialState(), overrides);
  return target;
}

function updateAutoSyncState(target, overrides = {}) {
  target.autoSync = {
    ...createInitialAutoSyncState(),
    ...(target.autoSync || {}),
    ...overrides,
  };
  return target.autoSync;
}

function startSyncProgress(target, overrides = {}) {
  target.syncInProgress = true;
  target.syncProgress = {
    ...createInitialSyncProgress(),
    phase: 'preparing_groups',
    startedAt: new Date().toISOString(),
    ...overrides,
  };
  return target.syncProgress;
}

function updateSyncProgress(target, overrides = {}) {
  target.syncProgress = {
    ...createInitialSyncProgress(),
    ...(target.syncProgress || {}),
    ...overrides,
  };
  return target.syncProgress;
}

function finishSyncProgress(target, overrides = {}) {
  target.syncInProgress = false;
  target.syncProgress = {
    ...createInitialSyncProgress(),
    ...(target.syncProgress || {}),
    phase: 'completed',
    finishedAt: new Date().toISOString(),
    currentGroupId: null,
    currentGroupName: null,
    ...overrides,
  };
  return target.syncProgress;
}

function failSyncProgress(target, errorLike, overrides = {}) {
  target.syncInProgress = false;
  target.syncProgress = {
    ...createInitialSyncProgress(),
    ...(target.syncProgress || {}),
    phase: 'failed',
    finishedAt: new Date().toISOString(),
    currentGroupId: null,
    currentGroupName: null,
    error: errorMessage(errorLike),
    ...overrides,
  };
  return target.syncProgress;
}

function clearChromiumSingletonLocks(rootPath) {
  const targetNames = new Set([
    'SingletonLock',
    'SingletonSocket',
    'SingletonCookie',
    'lockfile',
  ]);

  function visit(currentPath) {
    let stats;
    try {
      stats = fs.lstatSync(currentPath);
    } catch (_error) {
      return;
    }
    const basename = path.basename(currentPath);
    if (targetNames.has(basename)) {
      fs.rmSync(currentPath, { force: true, recursive: false });
      return;
    }

    if (stats.isDirectory()) {
      for (const entry of fs.readdirSync(currentPath)) {
        visit(path.join(currentPath, entry));
      }
    }
  }

  visit(rootPath);
}

module.exports = {
  clearChromiumSingletonLocks,
  createInitialAutoSyncState,
  createInitialState,
  createInitialSyncProgress,
  errorMessage,
  extractSelfIdentity,
  failSyncProgress,
  finishSyncProgress,
  isRecoverableWhatsAppRuntimeError,
  resetSessionState,
  startSyncProgress,
  updateAutoSyncState,
  updateSyncProgress,
};
