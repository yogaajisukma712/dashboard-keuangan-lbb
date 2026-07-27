const test = require('node:test');
const assert = require('node:assert/strict');

const {
  listChatsResilient,
  loadChatsInBatches,
} = require('../src/chat-loader');

test('listChatsResilient keeps the normal getChats path', async () => {
  const expected = [{ id: 'one' }, { id: 'two' }];
  const bot = {
    getChats: async () => expected,
  };

  const result = await listChatsResilient(bot);

  assert.equal(result.usedFallback, false);
  assert.equal(result.chats, expected);
  assert.deepEqual(result.failures, []);
});

test('listChatsResilient recovers valid groups when one chat model is broken', async () => {
  const bot = {
    getChats: async () => {
      throw 'r';
    },
    pupPage: {
      evaluate: async (_operation, chatId) => {
        if (!chatId) {
          return [
            'valid-one@g.us',
            'broken@g.us',
            'valid-two@g.us',
            'valid-one@g.us',
          ];
        }
        return {
          id: chatId,
          name: 'Recovered group',
          timestamp: 123,
          archived: false,
          isMuted: false,
          unreadCount: 0,
          participants: [],
        };
      },
    },
    getChatById: async (chatId) => {
      if (chatId === 'broken@g.us') throw new Error('model serialization failed');
      return { id: chatId, isGroup: true };
    },
  };

  const result = await listChatsResilient(bot, { batchSize: 2 });

  assert.equal(result.usedFallback, true);
  assert.equal(result.primaryError, 'r');
  assert.equal(result.totalGroupIds, 3);
  assert.deepEqual(
    result.chats.map((chat) => chat.id),
    ['valid-one@g.us', { _serialized: 'broken@g.us' }, 'valid-two@g.us'],
  );
  assert.deepEqual(result.directFallbacks, ['broken@g.us']);
  assert.deepEqual(result.failures, []);
});

test('listChatsResilient reports a useful error when every group fails', async () => {
  const bot = {
    getChats: async () => {
      throw 'r';
    },
    pupPage: {
      evaluate: async (_operation, chatId) => {
        if (!chatId) return ['broken@g.us'];
        throw new Error('direct model unavailable');
      },
    },
    getChatById: async () => {
      throw new Error('cannot serialize group');
    },
  };

  await assert.rejects(
    () => listChatsResilient(bot),
    /loaded 0 of 1 groups.*getChats failed: r.*cannot serialize group.*direct model unavailable/,
  );
});

test('loadChatsInBatches records empty results when direct fallback also fails', async () => {
  const bot = {
    getChatById: async () => null,
    pupPage: {
      evaluate: async () => {
        throw new Error('missing raw model');
      },
    },
  };

  const result = await loadChatsInBatches(bot, ['empty@g.us']);

  assert.deepEqual(result.chats, []);
  assert.deepEqual(result.failures, [{
    chatId: 'empty@g.us',
    error: 'Chat returned no data.; direct fallback: missing raw model',
  }]);
});
