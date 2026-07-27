const test = require('node:test');
const assert = require('node:assert/strict');

const filters = require('../../app/static/js/persistent-filters');

test('storage keys are stable and isolated by user and page', () => {
  const first = filters.buildStorageKey(
    '7',
    '/payments',
    '/payments',
    'fields:month,year',
  );
  const same = filters.buildStorageKey(
    '7',
    '/payments',
    '/payments',
    'fields:month,year',
  );
  const otherUser = filters.buildStorageKey(
    '8',
    '/payments',
    '/payments',
    'fields:month,year',
  );

  assert.equal(first, same);
  assert.notEqual(first, otherUser);
});

test('saved filters fill missing query values and preserve explicit values', () => {
  const result = filters.mergeRestoredSearch('?month=7&notice=paid&page=3', [
    {
      month: '6',
      year: '2026',
      tutor_ref: 'T-17',
    },
  ]);
  const params = new URLSearchParams(result.search);

  assert.equal(result.changed, true);
  assert.equal(params.get('month'), '7');
  assert.equal(params.get('year'), '2026');
  assert.equal(params.get('tutor_ref'), 'T-17');
  assert.equal(params.get('notice'), 'paid');
  assert.equal(params.has('page'), false);
});

test('empty and internal fields are not restored', () => {
  const result = filters.mergeRestoredSearch('', [
    {
      csrf_token: 'secret',
      page: '4',
      search: '',
      status: [],
    },
  ]);

  assert.equal(result.changed, false);
  assert.equal(result.search, '');
});
