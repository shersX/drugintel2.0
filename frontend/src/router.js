import { createRouter, createWebHistory } from 'vue-router'
import Dashboard from './views/Dashboard.vue'
import NewsList from './views/NewsList.vue'
import NewsDetail from './views/NewsDetail.vue'
import Chat from './views/Chat.vue'
import Alerts from './views/Alerts.vue'
import Monitor from './views/Monitor.vue'
import Settings from './views/Settings.vue'
import Login from './views/Login.vue'
import Users from './views/Users.vue'
import Account from './views/Account.vue'
import { loadMe, session } from './session'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', component: Login, meta: { public: true } },
    { path: '/', component: Dashboard },
    { path: '/news', component: NewsList },
    { path: '/news/:id', component: NewsDetail, props: true },
    { path: '/chat', component: Chat },
    { path: '/alerts', component: Alerts },
    { path: '/account', component: Account },
    { path: '/monitor', component: Monitor, meta: { admin: true } },
    { path: '/settings', component: Settings, meta: { admin: true } },
    { path: '/users', component: Users, meta: { admin: true } },
  ],
})

router.beforeEach(async (to) => {
  if (!session.ready) await loadMe()
  if (to.meta.public) {
    if (session.user && to.path === '/login') return '/'
    return true
  }
  if (!session.user) {
    return { path: '/login', query: { next: to.fullPath } }
  }
  if (to.meta.admin && session.user.role !== 'admin') return '/'
  return true
})

export default router
