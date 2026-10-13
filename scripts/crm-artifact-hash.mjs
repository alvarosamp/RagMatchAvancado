import { createHash } from 'node:crypto'

export function artifactHash(filename, bytes) {
  // Git normalizes text line endings on Windows/Linux checkouts. Binary files
  // remain byte-exact; textual artifacts use a documented LF representation.
  const value = /\.(html|css|js|json|svg|xml|txt|md)$/i.test(filename)
    ? bytes.toString('utf8').replace(/\r\n/g, '\n') : bytes
  return createHash('sha256').update(value).digest('hex')
}
