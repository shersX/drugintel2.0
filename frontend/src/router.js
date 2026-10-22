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
import Users from './views/Users.vue'
import Account from './views/Account.vue'
import { loadMe, session } from './session'
import { openAdminPrompt, openLoginPrompt } from './authPrompt'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    // 占位：beforeEach 会打开弹窗并导航到 next / 首页，不渲染整页登录
    { path: '/login', component: Dashboard, meta: { public: true, module: 'dashboard' } },
    { path: '/', component: Dashboard, meta: { public: true, module: 'dashboard' } },
    { path: '/news', component: NewsList, meta: { public: true, module: 'news' } },
    { path: '/news/:id', component: NewsDetail, props: true, meta: { public: true, module: 'news' } },
    { path: '/chat', component: Chat, meta: { public: true, module: 'chat' } },
    { path: '/alerts', component: Alerts, meta: { module: 'alerts' } },
    { path: '/pipeline', component: PipelineList, meta: { module: 'pipeline' } },
    { path: '/pipeline/:id', component: PipelineDetail, props: true, meta: { module: 'pipeline' } },
    { path: '/account', component: Account, meta: { module: null } },
    { path: '/monitor', component: Monitor, meta: { admin: true, module: 'admin' } },
    { path: '/settings', component: Settings, meta: { admin: true, module: 'admin' } },
    { path: '/users', component: Users, meta: { admin: true, module: 'admin' } },
  ],
})

function safeNext(raw) {
  const next = typeof raw === 'string' ? raw : '/'
  return next.startsWith('/') && !next.startsWith('//') ? next : '/'
}

router.beforeEach(async (to, from) => {
  if (!session.ready) await loadMe()

  if (to.path === '/login') {
    if (session.user) return '/'
    const dest = safeNext(to.query.next)
    openLoginPrompt(dest)
    return dest === '/login' ? '/' : dest
  }

  if (to.meta.public) return true

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
