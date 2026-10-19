import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import { onUnauthorized } from './api'
import { openLoginPrompt } from './authPrompt'
import { clearUser } from './session'
import './styles.css'

onUnauthorized(() => {
  clearUser()
  const current = router.currentRoute.value
  if (current.meta.public || current.path === '/login') return
  openLoginPrompt(current.fullPath)
})

createApp(App).use(router).mount('#app')
