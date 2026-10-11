import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import { onUnauthorized } from './api'
import { clearUser } from './session'
import './styles.css'

onUnauthorized(() => {
  clearUser()
  if (router.currentRoute.value.path !== '/login') {
    const next = router.currentRoute.value.fullPath
    router.replace({ path: '/login', query: next && next !== '/' ? { next } : {} })
  }
})

createApp(App).use(router).mount('#app')
