const test = require('node:test');
const assert = require('node:assert/strict');

const {
  isExcludedGroupName,
  parseExcludedGroupNames,
} = require('../src/group-filters');

test('parseExcludedGroupNames supports comma and newline separators', () => {
  assert.deepEqual(
    parseExcludedGroupNames('VPS / RDP MURAH III, Grup A\nGrup B\nGrup A'),
    ['VPS / RDP MURAH III', 'Grup A', 'Grup B'],
  );
});

test('isExcludedGroupName matches group names case-insensitively after normalization', () => {
  const excluded = parseExcludedGroupNames('VPS / RDP MURAH III');

  assert.equal(isExcludedGroupName('  vps / rdp murah iii ', excluded), true);
  assert.equal(isExcludedGroupName('English Ratih', excluded), false);
});
