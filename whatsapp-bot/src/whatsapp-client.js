const QRCode = require('qrcode');
const { Client, LocalAuth } = require('whatsapp-web.js');

const config = require('./config');
const { classifyEvaluationMessage, parseEvaluationMessage } = require('./evaluation/parser');
const { postSyncPayload } = require('./flask-client');
const { isExcludedGroupName } = require('./group-filters');
const {
  createSessionBackup,
  deleteSessionBackup,
  listAuthSessions,
  listSessionBackups,
  restoreSessionBackup,
} = require('./session-backup');
const {
  clearChromiumSingletonLocks,
  createInitialState,
  errorMessage,
  extractSelfIdentity,
  failSyncProgress,
  finishSyncProgress,
  isRecoverableWhatsAppRuntimeError,
  resetSessionState,
  startSyncProgress,
  updateSyncProgress,
} = require('./session-runtime');

let client = null;
let initializing = null;
let readyPromise = null;
let resolveReady = null;

const state = {
  ...createInitialState(),
};

function toIsoFromUnix(timestampSeconds) {
  return new Date(Number(timestampSeconds || 0) * 1000).toISOString();
}

function jidToPhone(jid) {
  return String(jid || '').split('@')[0] || '';
}

function serializeGroup(chat) {
  return {
    whatsapp_group_id: chat.id?._serialized || chat.id?.user || chat.id,
    name: chat.name,
    participant_count: Array.isArray(chat.participants) ? chat.participants.length : 0,
    last_message_at: chat.timestamp ? toIsoFromUnix(chat.timestamp) : null,
    metadata: {
      archived: !!chat.archived,
      muted: !!chat.isMuted,
      unreadCount: Number(chat.unreadCount || 0),
    },
  };
}

function pickContactName(participant, contactProfile) {
  return (
    participant?.name ||
    participant?.pushname ||
    participant?.shortName ||
    contactProfile?.name ||
    contactProfile?.pushname ||
    contactProfile?.shortName ||
    null
  );
}

function serializeParticipant(groupId, participant, contactProfile) {
  const jid = participant?.id?._serialized || participant?.id?.user || '';
  const displayName = pickContactName(participant, contactProfile);
  return {
    whatsapp_group_id: groupId,
    whatsapp_contact_id: jid,
    phone_number: jidToPhone(jid),
    display_name: displayName,
    is_admin: !!participant?.isAdmin,
    is_super_admin: !!participant?.isSuperAdmin,
  };
}

function serializeContact(participant, contactProfile) {
  const jid = participant?.id?._serialized || participant?.id?.user || '';
  return {
    whatsapp_contact_id: jid,
    phone_number: jidToPhone(jid),
    display_name: pickContactName(participant, contactProfile),
    push_name: participant?.pushname || contactProfile?.pushname || null,
    short_name: participant?.shortName || contactProfile?.shortName || null,
    metadata: {},
  };
}

async function fetchContactProfile(bot, jid, cache) {
  if (!jid) return null;
  if (cache.has(jid)) return cache.get(jid);
  let value = null;
  try {
    value = await bot.getContactById(jid);
  } catch (_error) {
    value = null;
  }
  cache.set(jid, value);
  return value;
}

function createReadyPromise() {
  readyPromise = new Promise((resolve) => {
    resolveReady = resolve;
  });
}

function logBotEvent(event, details = {}) {
  console.log(JSON.stringify({
    scope: 'whatsapp-bot',
    event,
    at: new Date().toISOString(),
    ...details,
  }));
}

function resetRuntime(overrides = {}) {
  resetSessionState(state, {
    lastSyncAt: state.lastSyncAt,
    ...overrides,
  });
}

function clearClientReferences() {
  client = null;
  initializing = null;
  readyPromise = null;
  resolveReady = null;
}

async function destroyClientInstance() {
  if (!client) {
    clearClientReferences();
    return;
  }

  const currentClient = client;
  clearClientReferences();

  try {
    await currentClient.destroy();
  } catch (_error) {
    // best effort cleanup
  }
}

async function handleRuntimeFailure(error, overrides = {}) {
  const message = errorMessage(error);
  const recoverable = isRecoverableWhatsAppRuntimeError(error);
  await destroyClientInstance();
  clearChromiumSingletonLocks(config.authDataPath);
  resetRuntime({
    status: recoverable ? 'idle' : 'error',
    lastError: message,
    ...overrides,
  });
  logBotEvent('runtime_failure', {
    recoverable,
    status: state.status,
    message,
  });
  return recoverable;
}

async function startClient() {
  if (client && ['error', 'auth_failure', 'disconnected'].includes(state.status)) {
    await destroyClientInstance();
    clearChromiumSingletonLocks(config.authDataPath);
  }
  if (client) return client;
  if (initializing) return initializing;

  resetRuntime({ status: 'initializing' });
  initializing = new Promise((resolve) => {
    createReadyPromise();
    clearChromiumSingletonLocks(config.authDataPath);
    client = new Client({
      authStrategy: new LocalAuth({
        clientId: config.clientId,
        dataPath: config.authDataPath,
      }),
      puppeteer: {
        executablePath: config.chromiumPath,
        headless: true,
        args: ['--no-sandbox', '--disable-setuid-sandbox'],
      },
    });

    client.on('qr', async (qr) => {
      state.status = 'awaiting_qr';
      state.qr = qr;
      state.qrDataUrl = await QRCode.toDataURL(qr);
      logBotEvent('qr', { hasQr: true });
    });

    client.on('authenticated', () => {
      state.authenticated = true;
      state.lastError = null;
      logBotEvent('authenticated');
    });

    client.on('ready', async () => {
      state.status = 'ready';
      state.ready = true;
      state.qr = null;
      state.qrDataUrl = null;
      try {
        state.me = extractSelfIdentity(client);
      } catch (error) {
        state.lastError = error.message;
      }
      if (resolveReady) {
        resolveReady(client);
      }
      logBotEvent('ready');
    });

    client.on('change_state', (value) => {
      logBotEvent('change_state', { value: String(value || '') });
    });

    client.on('loading_screen', (percent, message) => {
      logBotEvent('loading_screen', {
        percent: Number(percent || 0),
        message: String(message || ''),
      });
    });

    client.on('auth_failure', (message) => {
      resetRuntime({
        status: 'auth_failure',
        lastError: String(message || 'Authentication failure'),
      });
      clearChromiumSingletonLocks(config.authDataPath);
      void destroyClientInstance();
      logBotEvent('auth_failure', { message: state.lastError });
    });

    client.on('disconnected', (reason) => {
      resetRuntime({
        status: 'disconnected',
        lastError: String(reason || 'Disconnected'),
      });
      clearChromiumSingletonLocks(config.authDataPath);
      void destroyClientInstance();
      logBotEvent('disconnected', { reason: state.lastError });
    });

    client.initialize().catch(async (error) => {
      await handleRuntimeFailure(error);
    });

    resolve(client);
  });

  return initializing;
}

async function ensureReady() {
  await startClient();
  if (state.ready) return client;
  return readyPromise;
}

function getSessionState() {
  return {
    ...state,
    hasQr: Boolean(state.qr),
  };
}

function getSessionManagementState() {
  return {
    ...listAuthSessions(state),
    backups: listSessionBackups(),
  };
}

async function backupSession() {
  return createSessionBackup(state);
}

async function restoreSession(filename) {
  await destroyClientInstance();
  const result = await restoreSessionBackup(filename);
  resetRuntime({
    status: 'idle',
    lastError: `Session restored from ${filename}. Klik Mulai / Login untuk memuat ulang sesi.`,
  });
  logBotEvent('session_restore', { filename });
  return {
    ...result,
    session: getSessionManagementState(),
  };
}

async function deleteBackup(filename) {
  return deleteSessionBackup(filename);
}

async function listGroups() {
  const bot = await ensureReady();
  const chats = await bot.getChats();
  return chats.filter(
    (chat) => chat.isGroup && !isExcludedGroupName(chat.name, config.excludedGroupNames),
  );
}

async function buildSyncPayloadForGroups(groupIds, limit, { fullSync = false } = {}) {
  const groups = [];
  const contactMap = new Map();
  const membershipMap = new Map();
  const messages = [];

  const groupChats = await listGroups();
  const selected = groupIds?.length
    ? groupChats.filter((chat) => groupIds.includes(chat.id?._serialized))
    : groupChats;
  const bot = await ensureReady();
  const contactProfileCache = new Map();
  let scannedMessages = 0;
  let relevantMessages = 0;

  startSyncProgress(state, {
    fullSync,
    totalGroups: selected.length,
    processedGroups: 0,
    scannedMessages: 0,
    relevantMessages: 0,
  });

  for (const [index, chat] of selected.entries()) {
    const groupId = chat.id?._serialized;
    updateSyncProgress(state, {
      phase: 'syncing_group',
      currentGroupId: groupId,
      currentGroupName: chat.name || groupId,
      processedGroups: index,
      scannedMessages,
      relevantMessages,
    });
    groups.push(serializeGroup(chat));

    const participantRows = Array.isArray(chat.participants) ? chat.participants : [];
    for (const participant of participantRows) {
      const jid = participant?.id?._serialized || participant?.id?.user || '';
      const contactProfile = await fetchContactProfile(bot, jid, contactProfileCache);
      contactMap.set(jid, serializeContact(participant, contactProfile));
      membershipMap.set(
        `${groupId}:${jid}`,
        serializeParticipant(groupId, participant, contactProfile),
      );
    }

    if (typeof chat.syncHistory === 'function') {
      try {
        await chat.syncHistory();
      } catch (_error) {
        // best effort
      }
    }

    const fetchOptions = {};
    if (limit === Infinity) {
      fetchOptions.limit = Infinity;
    } else if (Number.isFinite(limit) && limit > 0) {
      fetchOptions.limit = limit;
    }

    const fetchedMessages = await chat.fetchMessages(fetchOptions);
    let groupRelevantMessages = 0;
    for (const item of fetchedMessages) {
      const classification = classifyEvaluationMessage(item.body);
      const parsed = classification.shouldStore ? parseEvaluationMessage(item.body) : null;
      if (parsed) {
        groupRelevantMessages += 1;
      }

      const authorJid = item.author || item.from || '';
      const authorProfile = await fetchContactProfile(bot, authorJid, contactProfileCache);
      if (authorJid && !contactMap.has(authorJid)) {
        contactMap.set(authorJid, {
          whatsapp_contact_id: authorJid,
          phone_number: jidToPhone(authorJid),
          display_name: pickContactName(authorProfile, authorProfile),
          push_name: authorProfile?.pushname || null,
          short_name: authorProfile?.shortName || null,
          metadata: {},
        });
      }
      messages.push({
        whatsapp_message_id: item.id?._serialized || `${groupId}-${item.timestamp}`,
        whatsapp_group_id: groupId,
        whatsapp_contact_id: authorJid,
        author_phone_number: jidToPhone(authorJid),
        author_name: pickContactName(authorProfile, authorProfile),
        sent_at: toIsoFromUnix(item.timestamp),
        body: item.body,
        message_type: item.type || 'chat',
        from_me: !!item.fromMe,
        has_media: !!item.hasMedia,
        filter_status: parsed ? 'relevant' : 'ignored',
        relevance_reason: classification.reason,
        raw_payload: {
          from: item.from,
          author: item.author,
          timestamp: item.timestamp,
        },
        parsed_payload: parsed || {},
        evaluation: parsed
          ? {
              student_name: parsed.studentName,
              tutor_name: parsed.tutorName,
              subject_name: parsed.subjectName,
              focus_topic: parsed.focusTopic,
              summary_text: parsed.summaryText,
              source_language: parsed.sourceLanguage,
              reported_lesson_date: parsed.reportedLessonDate,
              reported_time_label: parsed.reportedTimeLabel,
            }
          : null,
      });
    }
    scannedMessages += fetchedMessages.length;
    relevantMessages += groupRelevantMessages;
    updateSyncProgress(state, {
      phase: 'syncing_group',
      currentGroupId: groupId,
      currentGroupName: chat.name || groupId,
      processedGroups: index + 1,
      scannedMessages,
      relevantMessages,
    });
  }

  updateSyncProgress(state, {
    phase: 'posting_to_backend',
    currentGroupId: null,
    currentGroupName: null,
    processedGroups: selected.length,
    scannedMessages,
    relevantMessages,
    storedMessages: messages.length,
  });

  return {
    groups,
    contacts: Array.from(contactMap.values()),
    memberships: Array.from(membershipMap.values()),
    messages,
  };
}

async function syncGroupsAndMessages({
  groupIds = null,
  limit = config.defaultMessageLimit,
  fullSync = false,
} = {}) {
  try {
    const effectiveLimit = fullSync ? Infinity : limit;
    const payload = await buildSyncPayloadForGroups(groupIds, effectiveLimit, { fullSync });
    updateSyncProgress(state, {
      phase: 'saving_to_database',
      processedGroups: payload.groups.length,
      totalGroups: payload.groups.length,
      storedMessages: payload.messages.length,
    });
    const syncResult = await postSyncPayload(payload);
    state.lastSyncAt = new Date().toISOString();
    finishSyncProgress(state, {
      fullSync,
      totalGroups: payload.groups.length,
      processedGroups: payload.groups.length,
      storedMessages: syncResult?.result?.messages || payload.messages.length,
      evaluationCount: syncResult?.result?.evaluations || 0,
      linkedAttendanceCount: syncResult?.result?.linked_attendance || 0,
    });
    return {
      fullSync,
      syncedGroups: payload.groups.length,
      syncedMessages: payload.messages.length,
      syncedContacts: payload.contacts.length,
      ingest: syncResult,
    };
  } catch (error) {
    failSyncProgress(state, error);
    throw error;
  }
}

async function logout() {
  if (client) {
    try {
      await client.logout();
    } catch (_error) {
      // best effort logout for expired/disconnected sessions
    }
  }
  await destroyClientInstance();
  clearChromiumSingletonLocks(config.authDataPath);
  resetRuntime({ status: 'idle' });
  logBotEvent('logout');
}

async function recoverFromRuntimeError(error, source = 'process') {
  const recoverable = await handleRuntimeFailure(error);
  if (recoverable) {
    logBotEvent('process_recovery', {
      source,
      message: errorMessage(error),
    });
  }
  return recoverable;
}

module.exports = {
  startClient,
  ensureReady,
  getSessionState,
  getSessionManagementState,
  listGroups,
  syncGroupsAndMessages,
  backupSession,
  restoreSession,
  deleteBackup,
  logout,
  recoverFromRuntimeError,
  __private: {
    clearChromiumSingletonLocks,
    handleRuntimeFailure,
    isRecoverableWhatsAppRuntimeError,
    resetRuntime,
  },
};
