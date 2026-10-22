/**
 * DrugIntel 双层导航单一数据源。
 * sidebar: false → 不渲染 App 侧栏（仪表盘 / AI 问答等）。
 */

export const TOP_MODULES = [
  {
    key: 'dashboard',
    label: '仪表盘',
    to: '/',
    match: (route) => route.path === '/',
    sidebar: false,
    auth: null,
  },
  {
    key: 'news',
    label: '情报流',
    to: '/news',
    match: (route) => route.path === '/news' || route.path.startsWith('/news/'),
    sidebar: true,
    auth: null,
  },
  {
    key: 'pipeline',
    label: '研发管线',
    to: '/pipeline',
    match: (route) => route.path === '/pipeline' || route.path.startsWith('/pipeline/'),
    sidebar: true,
    auth: 'login',
  },
  {
    key: 'chat',
    label: 'AI 问答',
    to: '/chat',
    match: (route) => route.path === '/chat',
    sidebar: true,
    auth: null,
  },
  {
    key: 'alerts',
    label: '监测订阅',
    to: '/alerts',
    match: (route) => route.path === '/alerts',
    sidebar: true,
    auth: 'login',
  },
  {
    key: 'admin',
    label: '系统管理',
    to: '/settings',
    match: (route) =>
      route.path === '/settings'
      || route.path === '/monitor'
      || route.path === '/users',
    sidebar: true,
    auth: 'admin',
  },
]

/** 二级导航：按一级 module key 索引 */
export const SIDE_ITEMS = {
  news: [
    { key: 'news-all', label: '全部情报', to: '/news', icon: 'list', match: (r) => r.path === '/news' || r.path.startsWith('/news/') },
  ],
  pipeline: [
    { key: 'pipe-overview', label: '管线总览', to: '/pipeline', icon: 'grid', match: (r) => r.path === '/pipeline' || r.path.startsWith('/pipeline/') },
  ],
  chat: [
    {
      key: 'chat-new',
      label: '新对话',
      to: '/chat',
      icon: 'plus',
      match: (r) => r.path === '/chat' && !r.query.c,
    },
  ],
  alerts: [
    { key: 'alerts-mine', label: '我的订阅', to: '/alerts', icon: 'bell', match: (r) => r.path === '/alerts' },
  ],
  admin: [
    { key: 'admin-models', label: '模型配置', to: '/settings?tab=models', icon: 'cpu', match: (r) => r.path === '/settings' && (r.query.tab === 'models' || !r.query.tab) },
    { key: 'admin-rag', label: 'RAG 检索', to: '/settings?tab=rag', icon: 'search', match: (r) => r.path === '/settings' && r.query.tab === 'rag' },
    { key: 'admin-mail', label: '邮件服务', to: '/settings?tab=mail', icon: 'mail', match: (r) => r.path === '/settings' && r.query.tab === 'mail' },
    { key: 'admin-crawlers', label: '爬虫注册表', to: '/settings?tab=crawlers', icon: 'bot', match: (r) => r.path === '/settings' && r.query.tab === 'crawlers' },
    { key: 'admin-keywords', label: '过滤关键词', to: '/settings?tab=keywords', icon: 'tag', match: (r) => r.path === '/settings' && r.query.tab === 'keywords' },
    { key: 'admin-monitor', label: '爬虫监控', to: '/monitor', icon: 'activity', match: (r) => r.path === '/monitor' },
    { key: 'admin-users', label: '用户与权限', to: '/users', icon: 'users', match: (r) => r.path === '/users' },
  ],
}

export function resolveModule(route) {
  if (route.path === '/account') return null
  return TOP_MODULES.find((m) => m.match(route)) || null
}

export function visibleTopModules(user) {
  return TOP_MODULES.filter((m) => {
    if (m.auth === 'admin') return user?.role === 'admin'
    if (m.auth === 'login') return Boolean(user)
    return true
  })
}

export function sideItemsFor(moduleKey) {
  return SIDE_ITEMS[moduleKey] || []
}

export function moduleShowsSidebar(mod) {
  return Boolean(mod?.sidebar && sideItemsFor(mod.key).length)
}
