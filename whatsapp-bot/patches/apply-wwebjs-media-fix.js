'use strict';

/**
 * Patch whatsapp-web.js 1.34.7 with upstream media-upload fix.
 *
 * Upstream commit 064a3d5 ("fix(media): drop __x_id before spreading
 * mediaOptions into outgoing Msg") lands after the 1.34.7 npm release. Without
 * it, sending any media attachment fails inside WhatsApp Web with:
 *   "upload failed: media entry was not created"
 *   "Data passed to getter must include an id property (it's how we memoize)"
 * because MediaData's internal __x_id property overwrites the outgoing Msg id.
 *
 * This script injects the `delete message.__x_id` guard right before the
 * existing canonicalUrl guard. It is idempotent and fails loudly if the anchor
 * is missing so a library bump cannot silently drop the fix.
 */

const fs = require('fs');
const path = require('path');

const target = path.join(
  __dirname,
  '..',
  'node_modules',
  'whatsapp-web.js',
  'src',
  'util',
  'Injected',
  'Utils.js',
);

const source = fs.readFileSync(target, 'utf8');

const anchor = "        // Bot's won't reply if canonicalUrl is set (linking)";
if (!source.includes(anchor)) {
  console.error('[patch] ERROR: anchor not found in Utils.js; refusing to continue');
  process.exit(1);
}

const injection = [
  '        // MediaData is a model whose private __x_id field collides with Msg\'s',
  '        // internal id field when its enumerable properties are spread above,',
  '        // breaking getValidatedSender() during Msg initialization (upstream 064a3d5).',
  '        if (message.__x_id) {',
  '            delete message.__x_id;',
  '        }',
  anchor,
].join('\n');

let patched = source.includes('delete message.__x_id')
  ? source
  : source.replace(anchor, injection);
// Upstream 58ddf15: WA renamed serialized IDs to $1. Without this, a
// successfully uploaded document can return no message to Client.sendMessage.
patched = patched.replace(
  '.Msg.get(newMsgKey._serialized);',
  '.Msg.get(newMsgKey._serialized || newMsgKey.$1);',
);
if (!patched.includes('if (msg.id && !msg.id._serialized && msg.id.$1)')) {
  patched = patched.replace(
    '        const msg = message.serialize();',
    '        const msg = message.serialize();\n' +
      '        if (msg.id && !msg.id._serialized && msg.id.$1) msg.id._serialized = msg.id.$1;',
  );
}
fs.writeFileSync(target, patched, 'utf8');
console.log('[patch] wwebjs media fix applied to', target);
