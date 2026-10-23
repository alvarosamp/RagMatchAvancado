import { test } from 'node:test'
import assert from 'node:assert/strict'
import { artifactHash } from './crm-artifact-hash.mjs'

test('text checksums tolerate Git line-ending normalization but reject changed content', () => {
  assert.equal(artifactHash('placeholder.svg', Buffer.from('<svg>\r\n</svg>')), artifactHash('placeholder.svg', Buffer.from('<svg>\n</svg>')))
  assert.notEqual(artifactHash('index.html', Buffer.from('original')), artifactHash('index.html', Buffer.from('changed')))
})
test('binary artifact checksums remain byte-exact', () => {
  assert.notEqual(artifactHash('favicon.ico', Buffer.from([13, 10])), artifactHash('favicon.ico', Buffer.from([10])))
})
