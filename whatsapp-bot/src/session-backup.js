const crypto = require('crypto');
const fs = require('fs');
const path = require('path');
const { execFile } = require('child_process');
const { promisify } = require('util');

const config = require('./config');
const { clearChromiumSingletonLocks } = require('./session-runtime');

const execFileAsync = promisify(execFile);
const BACKUP_EXTENSION = '.tar.gz';

function ensureDir(targetPath) {
  fs.mkdirSync(targetPath, { recursive: true });
}

function safeFilename(value) {
  return String(value || '').replace(/[^a-zA-Z0-9._-]/g, '');
}

function backupPathFor(filename) {
  const safe = safeFilename(filename);
  if (!safe || !safe.endsWith(BACKUP_EXTENSION)) {
    throw new Error('Nama backup tidak valid.');
  }
  const target = path.resolve(config.authBackupPath, safe);
  const backupRoot = path.resolve(config.authBackupPath);
  if (!target.startsWith(`${backupRoot}${path.sep}`)) {
    throw new Error('Path backup tidak valid.');
  }
  return target;
}

function getDirectorySize(targetPath) {
  let total = 0;
  function visit(currentPath) {
    let stats;
    try {
      stats = fs.lstatSync(currentPath);
    } catch (_error) {
      return;
    }
    if (stats.isDirectory()) {
      for (const entry of fs.readdirSync(currentPath)) {
        visit(path.join(currentPath, entry));
      }
      return;
    }
    total += stats.size || 0;
  }
  visit(targetPath);
  return total;
}

function getLatestMtime(targetPath) {
  let latest = 0;
  function visit(currentPath) {
    let stats;
    try {
      stats = fs.lstatSync(currentPath);
    } catch (_error) {
      return;
    }
    latest = Math.max(latest, Number(stats.mtimeMs || 0));
    if (stats.isDirectory()) {
      for (const entry of fs.readdirSync(currentPath)) {
        visit(path.join(currentPath, entry));
      }
    }
  }
  visit(targetPath);
  return latest ? new Date(latest).toISOString() : null;
}

function listAuthSessions(runtimeState = {}) {
  ensureDir(config.authDataPath);
  ensureDir(config.authBackupPath);
  const entries = fs.readdirSync(config.authDataPath, { withFileTypes: true });
  const sessions = entries
    .filter((entry) => entry.isDirectory() && entry.name !== '_backups')
    .map((entry) => {
      const fullPath = path.join(config.authDataPath, entry.name);
      return {
        name: entry.name,
        active: entry.name === `session-${config.clientId}`,
        path: fullPath,
        sizeBytes: getDirectorySize(fullPath),
        updatedAt: getLatestMtime(fullPath),
      };
    });

  return {
    clientId: config.clientId,
    authDataPath: config.authDataPath,
    authBackupPath: config.authBackupPath,
    currentSessionName: `session-${config.clientId}`,
    runtime: {
      status: runtimeState.status || 'idle',
      authenticated: Boolean(runtimeState.authenticated),
      ready: Boolean(runtimeState.ready),
      me: runtimeState.me || null,
      lastError: runtimeState.lastError || null,
    },
    sessions,
  };
}

function listSessionBackups() {
  ensureDir(config.authBackupPath);
  return fs
    .readdirSync(config.authBackupPath, { withFileTypes: true })
    .filter((entry) => entry.isFile() && entry.name.endsWith(BACKUP_EXTENSION))
    .map((entry) => {
      const fullPath = path.join(config.authBackupPath, entry.name);
      const stats = fs.statSync(fullPath);
      return {
        filename: entry.name,
        sizeBytes: stats.size,
        createdAt: stats.birthtime?.toISOString?.() || stats.ctime.toISOString(),
        updatedAt: stats.mtime.toISOString(),
      };
    })
    .sort((left, right) => String(right.updatedAt).localeCompare(String(left.updatedAt)));
}

async function createSessionBackup(runtimeState = {}) {
  ensureDir(config.authDataPath);
  ensureDir(config.authBackupPath);
  clearChromiumSingletonLocks(config.authDataPath);

  const stamp = new Date().toISOString().replace(/[:.]/g, '-');
  const token = crypto.randomBytes(4).toString('hex');
  const filename = `wa-session-${config.clientId}-${stamp}-${token}${BACKUP_EXTENSION}`;
  const targetPath = path.join(config.authBackupPath, filename);

  await execFileAsync('tar', [
    '--exclude',
    './_backups',
    '--exclude',
    './SingletonLock',
    '--exclude',
    './SingletonSocket',
    '--exclude',
    './SingletonCookie',
    '-czf',
    targetPath,
    '-C',
    config.authDataPath,
    '.',
  ]);

  const stats = fs.statSync(targetPath);
  return {
    filename,
    sizeBytes: stats.size,
    createdAt: stats.mtime.toISOString(),
    session: listAuthSessions(runtimeState),
    backups: listSessionBackups(),
  };
}

async function restoreSessionBackup(filename) {
  const sourcePath = backupPathFor(filename);
  if (!fs.existsSync(sourcePath)) {
    throw new Error('File backup tidak ditemukan.');
  }

  ensureDir(config.authDataPath);
  ensureDir(config.authBackupPath);
  clearChromiumSingletonLocks(config.authDataPath);

  const restoreSafetyName = `pre-restore-${config.clientId}-${new Date()
    .toISOString()
    .replace(/[:.]/g, '-')}${BACKUP_EXTENSION}`;
  const restoreSafetyPath = path.join(config.authBackupPath, restoreSafetyName);
  await execFileAsync('tar', [
    '--exclude',
    './_backups',
    '--exclude',
    './SingletonLock',
    '--exclude',
    './SingletonSocket',
    '--exclude',
    './SingletonCookie',
    '-czf',
    restoreSafetyPath,
    '-C',
    config.authDataPath,
    '.',
  ]);

  for (const entry of fs.readdirSync(config.authDataPath)) {
    if (entry === '_backups') continue;
    fs.rmSync(path.join(config.authDataPath, entry), { recursive: true, force: true });
  }

  await execFileAsync('tar', ['-xzf', sourcePath, '-C', config.authDataPath]);
  clearChromiumSingletonLocks(config.authDataPath);

  return {
    restoredFrom: filename,
    safetyBackup: restoreSafetyName,
    sessions: listAuthSessions(),
    backups: listSessionBackups(),
  };
}

function deleteSessionBackup(filename) {
  const targetPath = backupPathFor(filename);
  if (!fs.existsSync(targetPath)) {
    throw new Error('File backup tidak ditemukan.');
  }
  fs.rmSync(targetPath, { force: true });
  return { filename, backups: listSessionBackups() };
}

module.exports = {
  backupPathFor,
  createSessionBackup,
  deleteSessionBackup,
  listAuthSessions,
  listSessionBackups,
  restoreSessionBackup,
};
