import { readFile, readdir } from 'node:fs/promises'
import { artifactHash } from './crm-artifact-hash.mjs'
import { execFileSync } from 'node:child_process'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const bundle = path.join(root, 'frontend/public/crm')
const metadata = JSON.parse(await readFile(path.join(bundle, 'tor-sync.json'), 'utf8'))
const pinned = execFileSync('git', ['ls-files', '--stage', 'bid-buddy'], {cwd: root, encoding: 'utf8'}).trim().split(/\s+/)[1]
if (!pinned || metadata.sourceCommit !== pinned) throw new Error('CRM bundle does not match the pinned source revision. Run build:crm.')
if (!metadata.artifactHashes?.['index.html']) throw new Error('CRM artifact manifest missing. Run build:crm.')
if (metadata.artifactHashFormat !== 'sha256-lf-text-v1') throw new Error('CRM artifact hash format missing. Run build:crm.')
const found = {}
async function verify(directory) {
  for (const entry of await readdir(directory, {withFileTypes: true})) {
    const file = path.join(directory, entry.name)
    if (entry.isDirectory()) await verify(file)
    else {
      const relative = path.relative(bundle, file).split(path.sep).join('/')
      if (relative === 'tor-sync.json') continue
      found[relative] = artifactHash(relative, await readFile(file))
      if (found[relative] !== metadata.artifactHashes[relative]) throw new Error(`CRM artifact changed: ${relative}`)
    }
  }
}
await verify(bundle)
if (Object.keys(found).length !== Object.keys(metadata.artifactHashes).length) throw new Error('CRM artifact files missing.')
console.log(`Verified ${Object.keys(found).length} CRM artifacts from ${pinned}.`)
