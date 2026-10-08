'use strict';

const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const script = fs.readFileSync(
  path.join(__dirname, '..', 'patches', 'apply-wwebjs-media-fix.js'), 'utf8',
);

function runPatch(input) {
  let output = input;
  vm.runInNewContext(script, {
    require(name) {
      if (name === 'fs') return {
        readFileSync: () => output,
        writeFileSync: (_file, value) => { output = value; },
      };
      return require(name);
    },
    __dirname: '/app/patches',
    console: { log() {}, error() {} },
    process: { exit(code) { throw new Error(`exit ${code}`); } },
  });
  return output;
}

test('media patch fixes private model ID collision and renamed message IDs idempotently', () => {
  const source = [
    "        // Bot's won't reply if canonicalUrl is set (linking)",
    '        const msg = message.serialize();',
    '            .Msg.get(newMsgKey._serialized);',
  ].join('\n');
  const patched = runPatch(source);
  assert.ok(patched.includes('delete message.__x_id'));
  assert.ok(patched.includes('newMsgKey._serialized || newMsgKey.$1'));
  assert.ok(patched.includes('msg.id._serialized = msg.id.$1'));
  assert.equal(runPatch(patched), patched);
});

test('media patch rejects incompatible library rather than silently skipping', () => {
  assert.throws(() => runPatch('unknown upstream source'), /exit 1/);
});
