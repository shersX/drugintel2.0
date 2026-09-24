import { createRouter, createWebHistory } from 'vue-router'
import Dashboard from './views/Dashboard.vue'
import NewsList from './views/NewsList.vue'
import NewsDetail from './views/NewsDetail.vue'
import Chat from './views/Chat.vue'
import Alerts from './views/Alerts.vue'
import Monitor from './views/Monitor.vue'

export default createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: Dashboard },
    { path: '/news', component: NewsList },
    { path: '/news/:id', component: NewsDetail, props: true },
    { path: '/chat', component: Chat },
    { path: '/alerts', component: Alerts },
    { path: '/monitor', component: Monitor },
  ],
})
