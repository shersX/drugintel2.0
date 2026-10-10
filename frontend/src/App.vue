<template>
  <div class="shell">
    <header class="masthead">
      <div class="masthead-inner">
        <div class="mast-top">
          <router-link to="/" class="mast-brand">
            <svg class="leaf" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">
              <path d="M5 20c0-8 5-14 14-15 .5 9-4 14-11 14.5" />
              <path d="M5 20c3-5 7-9 12-11.5" />
            </svg>
            DrugIntel<span style="color: var(--moss)">.ai</span>
          </router-link>
          <span class="mast-date">Vol. {{ issue }} · {{ today }}</span>
        </div>
        <nav class="mast-nav">
          <router-link
            v-for="item in navItems"
            :key="item.to"
            :to="item.to"
            class="mast-link"
          >{{ item.label }}</router-link>
        </nav>
      </div>
    </header>

    <main class="page">
      <router-view v-slot="{ Component }">
        <Transition name="page" mode="out-in">
          <component :is="Component" />
        </Transition>
      </router-view>
    </main>

    <footer class="colophon">
      <div class="colophon-inner">
        <span><b>DrugIntel.ai</b> — 医药情报 · 聚类 · RAG 问答</span>
        <span>pgvector × FastAPI × Vue 3 · 毕业设计版</span>
      </div>
    </footer>
  </div>
</template>

<script setup>
const navItems = [
  { to: '/', label: '仪表盘' },
  { to: '/news', label: '情报流' },
  { to: '/chat', label: 'AI 问答' },
  { to: '/alerts', label: '监测订阅' },
  { to: '/monitor', label: '系统监控' },
]

const now = new Date()
const today = `${now.getFullYear()} 年 ${now.getMonth() + 1} 月 ${now.getDate()} 日`
const issue = String(Math.floor((now - new Date(now.getFullYear(), 0, 0)) / 864e5))
</script>
