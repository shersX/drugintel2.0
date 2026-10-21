import { createRouter, createWebHistory } from 'vue-router'
import Dashboard from './views/Dashboard.vue'
import NewsList from './views/NewsList.vue'
import NewsDetail from './views/NewsDetail.vue'
import Chat from './views/Chat.vue'
import Alerts from './views/Alerts.vue'
import PipelineList from './views/PipelineList.vue'
import PipelineDetail from './views/PipelineDetail.vue'
import Monitor from './views/Monitor.vue'
import Settings from './views/Settings.vue'
import Login from './views/Login.vue'
import Users from './views/Users.vue'
import Account from './views/Account.vue'
import { loadMe, session } from './session'
import { openAdminPrompt, openLoginPrompt } from './authPrompt'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', component: Login, meta: { public: true } },
    { path: '/', component: Dashboard, meta: { public: true } },
    { path: '/news', component: NewsList, meta: { public: true } },
    { path: '/news/:id', component: NewsDetail, props: true, meta: { public: true } },
    { path: '/chat', component: Chat, meta: { public: true } },
    { path: '/alerts', component: Alerts },
    { path: '/pipeline', component: PipelineList },
    { path: '/pipeline/:id', component: PipelineDetail, props: true },
    { path: '/account', component: Account },
    { path: '/monitor', component: Monitor, meta: { admin: true } },
    { path: '/settings', component: Settings, meta: { admin: true } },
    { path: '/users', component: Users, meta: { admin: true } },
  ],
})

router.beforeEach(async (to, from) => {
  if (!session.ready) await loadMe()
  if (to.meta.public) {
    if (session.user && to.path === '/login') return '/'
    return true
  }
  const insideApp = from.matched.length > 0
  if (!session.user) {
    if (insideApp) {
      openLoginPrompt(to.fullPath)
      return false
    }
    return true
  }
  if (to.meta.admin && session.user.role !== 'admin') {
    openAdminPrompt()
    return from.path === '/' ? false : '/'
  }
  return true
})

export default router
