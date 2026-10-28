export const INTERNAL_REGISTER_PATH = import.meta.env.VITE_INTERNAL_REGISTER_PATH || '/cadastro-tor-gestao-interna'

const normalizedPath = (path) => String(path || '/').replace(/\/+$/, '') || '/'
const publicPaths = new Set([
  '/', '/login', '/esqueci-senha', '/redefinir-senha', INTERNAL_REGISTER_PATH,
].map(normalizedPath))

// The initial session probe is allowed to fail on pages used before signing in.
export function shouldRedirectUnauthorized(currentPath, requestPath = '') {
  return !publicPaths.has(normalizedPath(currentPath)) && !requestPath.includes('/auth/login')
}
