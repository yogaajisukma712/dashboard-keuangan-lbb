function errorMessage(error) {
  if (error instanceof Error) return error.message;
  if (typeof error === 'string') return error;
  try {
    return JSON.stringify(error);
  } catch (_error) {
    return String(error);
  }
}

async function listBrowserGroupIds(bot) {
  if (!bot?.pupPage?.evaluate) {
    throw new Error('WhatsApp browser page is unavailable for chat fallback.');
  }

  return bot.pupPage.evaluate(() => {
    const chats = window.require('WAWebCollections').Chat.getModelsArray();
    return chats
      .map((chat) => chat?.id?._serialized || chat?.id?.toString?.() || '')
      .filter((id) => typeof id === 'string' && id.endsWith('@g.us'));
  });
}

async function fetchMessagesByGroupId(bot, chatId, searchOptions = {}) {
  const requestedLimit = searchOptions.limit;
  const loadAll = requestedLimit === Infinity;
  const limit = Number.isFinite(requestedLimit) && requestedLimit > 0
    ? requestedLimit
    : null;

  return bot.pupPage.evaluate(async (groupId, options) => {
    const serializeId = (value) => (
      value?._serialized || value?.toString?.() || ''
    );
    const chat = await window.WWebJS.getChat(groupId, { getAsModel: false });
    if (!chat) throw new Error(`Group model is unavailable: ${groupId}`);

    const messageFilter = (message) => !message.isNotification;
    let messages = chat.msgs.getModelsArray().filter(messageFilter);

    if (options.loadAll || options.limit) {
      const target = options.loadAll ? Infinity : options.limit;
      while (messages.length < target) {
        const loaded = await window
          .require('WAWebChatLoadMessages')
          .loadEarlierMsgs({ chat });
        if (!loaded?.length) break;
        messages = [...loaded.filter(messageFilter), ...messages];
      }
    }

    if (options.limit && messages.length > options.limit) {
      messages.sort((left, right) => (left.t > right.t ? 1 : -1));
      messages = messages.slice(messages.length - options.limit);
    }

    return messages.map((message) => ({
      id: {
        _serialized: serializeId(message.id),
        fromMe: Boolean(message.id?.fromMe),
      },
      timestamp: message.t,
      body: message.body || message.caption || '',
      author: serializeId(message.author),
      from: serializeId(message.from),
      type: message.type || 'chat',
      fromMe: Boolean(message.id?.fromMe),
      hasMedia: Boolean(message.mediaData || message.isMedia),
    }));
  }, chatId, { loadAll, limit });
}

async function createDirectGroupChat(bot, chatId) {
  const metadata = await bot.pupPage.evaluate(async (groupId) => {
    const serializeId = (value) => (
      value?._serialized || value?.toString?.() || ''
    );
    const chat = await window.WWebJS.getChat(groupId, { getAsModel: false });
    if (!chat) throw new Error(`Group model is unavailable: ${groupId}`);
    const participantCollection = chat.groupMetadata?.participants;
    const participantModels = participantCollection?.getModelsArray?.()
      || participantCollection?.models
      || [];

    return {
      id: serializeId(chat.id) || groupId,
      name: chat.formattedTitle || chat.name || groupId,
      timestamp: chat.t || null,
      archived: Boolean(chat.archive),
      isMuted: Boolean(chat.mute?.expiration),
      unreadCount: Number(chat.unreadCount || 0),
      participants: participantModels.map((participant) => ({
        id: { _serialized: serializeId(participant.id) },
        isAdmin: Boolean(participant.isAdmin),
        isSuperAdmin: Boolean(participant.isSuperAdmin),
      })),
    };
  }, chatId);

  return {
    id: { _serialized: metadata.id || chatId },
    name: metadata.name || chatId,
    timestamp: metadata.timestamp,
    archived: metadata.archived,
    isMuted: metadata.isMuted,
    unreadCount: metadata.unreadCount,
    participants: metadata.participants,
    isGroup: true,
    directFallback: true,
    fetchMessages: (searchOptions) => (
      fetchMessagesByGroupId(bot, chatId, searchOptions)
    ),
  };
}

async function loadChatsInBatches(bot, chatIds, batchSize = 10) {
  const chats = [];
  const failures = [];
  const directFallbacks = [];

  for (let offset = 0; offset < chatIds.length; offset += batchSize) {
    const batch = chatIds.slice(offset, offset + batchSize);
    const results = await Promise.allSettled(
      batch.map((chatId) => bot.getChatById(chatId)),
    );
    const failedBatch = [];

    results.forEach((result, index) => {
      if (result.status === 'fulfilled' && result.value) {
        chats.push(result.value);
        return;
      }
      failedBatch.push({ chatId: batch[index], primaryError: result.reason });
    });

    const directResults = await Promise.allSettled(
      failedBatch.map(({ chatId }) => createDirectGroupChat(bot, chatId)),
    );
    directResults.forEach((result, index) => {
      const failed = failedBatch[index];
      if (result.status === 'fulfilled' && result.value) {
        chats.push(result.value);
        directFallbacks.push(failed.chatId);
        return;
      }
      failures.push({
        chatId: failed.chatId,
        error: [
          errorMessage(failed.primaryError || 'Chat returned no data.'),
          errorMessage(result.reason || 'Direct group fallback returned no data.'),
        ].join('; direct fallback: '),
      });
    });
  }

  return { chats, directFallbacks, failures };
}

async function listChatsResilient(bot, { batchSize = 10 } = {}) {
  try {
    return {
      chats: await bot.getChats(),
      usedFallback: false,
      totalGroupIds: 0,
      directFallbacks: [],
      failures: [],
      primaryError: null,
    };
  } catch (primaryError) {
    const groupIds = [...new Set(await listBrowserGroupIds(bot))];
    const {
      chats,
      directFallbacks,
      failures,
    } = await loadChatsInBatches(bot, groupIds, batchSize);

    if (groupIds.length === 0 || chats.length === 0) {
      const firstFailure = failures[0]?.error || 'no group IDs returned';
      throw new Error(
        `WhatsApp chat fallback loaded 0 of ${groupIds.length} groups after getChats failed: `
        + `${errorMessage(primaryError)}; first fallback error: ${firstFailure}`,
      );
    }

    return {
      chats,
      usedFallback: true,
      totalGroupIds: groupIds.length,
      directFallbacks,
      failures,
      primaryError: errorMessage(primaryError),
    };
  }
}

module.exports = {
  createDirectGroupChat,
  errorMessage,
  fetchMessagesByGroupId,
  listBrowserGroupIds,
  listChatsResilient,
  loadChatsInBatches,
};
