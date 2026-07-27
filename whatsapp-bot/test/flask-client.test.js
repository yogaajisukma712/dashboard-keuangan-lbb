const test = require('node:test');
const assert = require('node:assert/strict');

const configPath = require.resolve('../src/config');
require.cache[configPath] = {
  id: configPath,
  filename: configPath,
  loaded: true,
  exports: {
    flaskBaseUrl: 'http://flask.test',
    flaskBotToken: 'test-token',
    syncMessageBatchSize: 2000,
  },
};

const {
  chunkMessages,
  postSyncPayload,
} = require('../src/flask-client');

function responseForBody(body) {
  return {
    ok: true,
    json: async () => ({
      ok: true,
      result: {
        groups: body.groups.length,
        contacts: body.contacts.length,
        memberships: body.memberships.length,
        messages: body.messages.length,
        evaluations: body.messages.length,
        linked_attendance: body.messages.length,
        excluded_groups: ['Excluded'],
      },
    }),
  };
}

test('chunkMessages creates stable batches without dropping messages', () => {
  assert.deepEqual(
    chunkMessages([1, 2, 3, 4, 5], 2),
    [[1, 2], [3, 4], [5]],
  );
});

test('postSyncPayload sends small payloads in one request', async (t) => {
  const calls = [];
  t.mock.method(global, 'fetch', async (_url, options) => {
    const body = JSON.parse(options.body);
    calls.push(body);
    return responseForBody(body);
  });
  const payload = {
    groups: [{ id: 1 }],
    contacts: [{ id: 1 }],
    memberships: [{ id: 1 }],
    messages: [{ id: 1 }, { id: 2 }],
  };

  const result = await postSyncPayload(payload, { messageBatchSize: 3 });

  assert.equal(calls.length, 1);
  assert.equal(result.result.messages, 2);
});

test('postSyncPayload batches large payloads and aggregates counters', async (t) => {
  const calls = [];
  t.mock.method(global, 'fetch', async (_url, options) => {
    const body = JSON.parse(options.body);
    calls.push(body);
    return responseForBody(body);
  });
  const payload = {
    groups: [{ id: 1 }],
    contacts: [{ id: 1 }],
    memberships: [{ id: 1 }, { id: 2 }],
    messages: Array.from({ length: 5 }, (_value, id) => ({ id })),
  };

  const result = await postSyncPayload(payload, { messageBatchSize: 2 });

  assert.deepEqual(calls.map((call) => call.messages.length), [2, 2, 1]);
  assert.deepEqual(calls.map((call) => call.memberships.length), [2, 0, 0]);
  assert.equal(result.batches, 3);
  assert.deepEqual(result.result, {
    groups: 1,
    contacts: 1,
    memberships: 2,
    messages: 5,
    evaluations: 5,
    linked_attendance: 5,
    excluded_groups: ['Excluded'],
  });
});
