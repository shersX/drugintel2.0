import { reactive } from 'vue'

export const authPrompt = reactive({
  open: false,
  kind: 'login',
  next: '/',
})

export function promptCopy(path) {
  if (path.startsWith('/chat')) return '登录后才能使用 AI 问答。'
  if (path.startsWith('/alerts')) return '登录后才能使用监测订阅。'
  if (path.startsWith('/account')) return '登录后才能查看账户。'
  return '登录后才能继续。'
}

export function openLoginPrompt(next = '/') {
  authPrompt.kind = 'login'
  authPrompt.next = next || '/'
  authPrompt.open = true
}

export function openAdminPrompt() {
  authPrompt.kind = 'admin'
  authPrompt.next = '/'
  authPrompt.open = true
}

export function closeAuthPrompt() {
  authPrompt.open = false
}
