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

async function loadChatsInBatches(bot, chatIds, batchSize = 10) {
  const chats = [];
  const failures = [];

  for (let offset = 0; offset < chatIds.length; offset += batchSize) {
    const batch = chatIds.slice(offset, offset + batchSize);
    const results = await Promise.allSettled(
      batch.map((chatId) => bot.getChatById(chatId)),
    );

    results.forEach((result, index) => {
      if (result.status === 'fulfilled' && result.value) {
        chats.push(result.value);
        return;
      }
      failures.push({
        chatId: batch[index],
        error: errorMessage(result.reason || 'Chat returned no data.'),
      });
    });
  }

  return { chats, failures };
}

async function listChatsResilient(bot, { batchSize = 10 } = {}) {
  try {
    return {
      chats: await bot.getChats(),
      usedFallback: false,
      totalGroupIds: 0,
      failures: [],
      primaryError: null,
    };
  } catch (primaryError) {
    const groupIds = [...new Set(await listBrowserGroupIds(bot))];
    const { chats, failures } = await loadChatsInBatches(bot, groupIds, batchSize);

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
      failures,
      primaryError: errorMessage(primaryError),
    };
  }
}

module.exports = {
  errorMessage,
  listBrowserGroupIds,
  listChatsResilient,
  loadChatsInBatches,
};
