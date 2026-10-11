import { reactive } from 'vue'
import { api } from './api'

export const session = reactive({
  user: null,
  ready: false,
})

export async function loadMe() {
  if (session.ready) return session.user
  try {
    session.user = await api.me()
  } catch {
    session.user = null
  }
  session.ready = true
  return session.user
}

export function setUser(user) {
  session.user = user
  session.ready = true
}

export function clearUser() {
  session.user = null
  session.ready = true
}
