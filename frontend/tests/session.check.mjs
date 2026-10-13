import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import { test } from 'node:test'
import assert from 'node:assert/strict'

const code = readFileSync(new URL('../public/session.js', import.meta.url), 'utf8')
const response = status => new Response('{}', {status})
function setup(results) {
  const calls = []
  const nativeFetch = async (...args) => {
    calls.push(args)
    const result = results.shift()
    if (result instanceof Error) throw result
    return result
  }
  const document = {visibilityState:'visible', addEventListener() {}}
  const location = {origin:'http://localhost:13089'}
  const window = {fetch:nativeFetch, dispatchEvent() {}}
  window.parent = window
  const RelativeRequest = class extends Request {
    constructor(input, init) { super(typeof input === 'string' ? new URL(input, location.origin) : input, init) }
  }
  vm.runInNewContext(code, {window, document, location, Request:RelativeRequest, URL, Event, setInterval() {}})
  return {window, calls}
}

test('retries a protected fetch after access expires', async () => {
  const {window, calls} = setup([response(401),response(401),response(200),response(200)])
  assert.equal((await window.fetch('/api/crm/query/notices')).status,200)
  assert.equal(calls[2][0],'/api/auth/refresh')
  assert.equal(calls[2][1].headers['X-Session-Refresh'],'1')
  assert.equal(calls.length,4)
})
test('does not renew invalid login or external requests', async () => {
  const {window, calls} = setup([response(401),response(401)])
  await window.fetch('/api/auth/login', {method:'POST',body:'{}'})
  await window.fetch('https://external.example/api/anything')
  assert.equal(calls.length,2)
})
test('shares concurrent renewal and stops after a definitive 401', async () => {
  const {window, calls} = setup([response(401),response(401)])
  const values = await Promise.all([window.ragmatchSession.refresh(),window.ragmatchSession.refresh()])
  assert.equal(values.every(value => value === false),true)
  assert.equal(calls.length,2)
  assert.equal(await window.ragmatchSession.refresh(),false)
  assert.equal(calls.length,2)
})
test('a network failure does not loop through refresh attempts', async () => {
  const {window, calls} = setup([response(401),new Error('offline')])
  assert.equal((await window.fetch('/api/crm/query/notices')).status,401)
  assert.equal(calls.length,2)
})
test('explicit bearer requests keep their original authentication identity', async () => {
  const {window, calls} = setup([response(401)])
  await window.fetch('/api/crm/query/notices',{headers:{Authorization:'Bearer explicit'}})
  assert.equal(calls.length,1)
})
