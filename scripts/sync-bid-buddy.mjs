import { existsSync } from 'node:fs'
import { cp, mkdir, rm, writeFile, readdir, readFile } from 'node:fs/promises'
import { artifactHash } from './crm-artifact-hash.mjs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { spawnSync } from 'node:child_process'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)
const repoRoot = path.resolve(__dirname, '..')
const sourceArgument = process.argv.find(argument => argument.startsWith('--source-path='))
const crmRoot = sourceArgument ? path.resolve(repoRoot, sourceArgument.slice('--source-path='.length)) : path.join(repoRoot, 'bid-buddy')
const crmDist = path.join(crmRoot, 'dist-embed')
const crmNodeModules = path.join(crmRoot, 'node_modules')
const targetRoot = path.join(repoRoot, 'frontend', 'public', 'crm')
const npmCommand = process.platform === 'win32' ? 'npm.cmd' : 'npm'
const shouldPull = process.argv.includes('--pull')

function run(command, args, cwd, capture = false) {
  const result = spawnSync(command, args, {
    cwd,
    encoding: 'utf8',
    shell: process.platform === 'win32',
    stdio: capture ? ['ignore', 'pipe', 'pipe'] : 'inherit',
  })

  if (result.error || result.status !== 0) {
    const details = capture
      ? `${result.stdout || ''}\n${result.stderr || ''}`.trim()
      : `${command} ${args.join(' ')}`
    throw new Error(result.error?.message || details || `Falha ao executar ${command} ${args.join(' ')}`)
  }

  return capture ? (result.stdout || '').trim() : ''
}

function readGitValue(args) {
  try {
    return run('git', args, crmRoot, true) || null
  } catch {
    return null
  }
}

function ensureCrmDependencies() {
  if (existsSync(crmNodeModules)) {
    console.log('[crm-sync] Dependencias do bid-buddy ja estao instaladas. Pulando instalacao.')
    return
  }

  console.log('[crm-sync] Instalando dependencias do bid-buddy...')
  try {
    run(npmCommand, ['ci'], crmRoot)
  } catch {
    console.log('[crm-sync] npm ci nao pode ser usado com o lock atual. Fazendo fallback para npm install...')
    run(npmCommand, ['install'], crmRoot)
  }
}

async function main() {
  if (!existsSync(crmRoot)) {
    throw new Error('Pasta bid-buddy nao encontrada. Verifique se o repositorio do CRM esta presente ao lado do frontend.')
  }

  if (shouldPull) {
    console.log('[crm-sync] Atualizando o repositorio bid-buddy...')
    run('git', ['pull', '--ff-only'], crmRoot)
  }

  ensureCrmDependencies()

  // Keep the private CRM source fix reproducible without publishing that source.
  for (const patchName of ['crm-session-source.patch', 'crm-manual-match-source.patch', 'crm-technical-sheet-source.patch', 'crm-catalog-import-source.patch', 'crm-lpu-lifecycle-source.patch']) {
    const sessionPatch = path.join(repoRoot, 'docs', patchName)
    if (!existsSync(sessionPatch)) continue;
    const applied = spawnSync('git', ['apply', '--reverse', '--check', sessionPatch], { cwd: crmRoot })
    if (applied.status !== 0) {
      run('git', ['apply', '--check', sessionPatch], crmRoot)
      run('git', ['apply', sessionPatch], crmRoot)
    }
  }

  console.log('[crm-sync] Gerando build embarcado em /crm/ ...')
  run(npmCommand, ['run', 'build:embed'], crmRoot)

  console.log('[crm-sync] Copiando artefatos para frontend/public/crm ...')
  await rm(targetRoot, { recursive: true, force: true })
  await mkdir(targetRoot, { recursive: true })
  await cp(crmDist, targetRoot, { recursive: true })
  const indexFile = path.join(targetRoot, 'index.html')
  const indexHtml = await readFile(indexFile, 'utf8')
  if (!indexHtml.includes('src="/session.js"')) {
    await writeFile(indexFile, indexHtml.replace('<head>', '<head>\n    <script src="/session.js"></script>'), 'utf8')
  }

  const artifactHashes = {}
  async function fingerprint(directory) {
    for (const entry of await readdir(directory, { withFileTypes: true })) {
      const file = path.join(directory, entry.name)
      if (entry.isDirectory()) await fingerprint(file)
      else artifactHashes[path.relative(targetRoot, file).split(path.sep).join('/')] = artifactHash(file, await readFile(file))
    }
  }
  await fingerprint(targetRoot)

  const metadata = {
    app: 'bid-buddy',
    sourcePath: 'bid-buddy',
    sourceRepo: readGitValue(['config', '--get', 'remote.origin.url']),
    sourceBranch: readGitValue(['rev-parse', '--abbrev-ref', 'HEAD']),
    sourceCommit: readGitValue(['rev-parse', 'HEAD']),
    sourceDirty: Boolean(readGitValue(['status', '--porcelain'])),
    sourcePatches: ['docs/crm-session-source.patch', 'docs/crm-manual-match-source.patch', 'docs/crm-technical-sheet-source.patch', 'docs/crm-catalog-import-source.patch', 'docs/crm-lpu-lifecycle-source.patch'],
    artifactHashes,
    artifactHashFormat: 'sha256-lf-text-v1',
    builtAt: new Date().toISOString(),
    pulledBeforeBuild: shouldPull,
  }

  await writeFile(
    path.join(targetRoot, 'tor-sync.json'),
    `${JSON.stringify(metadata, null, 2)}\n`,
    'utf8'
  )

  console.log('[crm-sync] CRM sincronizado com sucesso.')
}

main().catch((error) => {
  console.error('[crm-sync] Falha na sincronizacao do CRM.')
  console.error(error.message)
  process.exit(1)
})
