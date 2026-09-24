<template>
  <div class="layout">
    <aside class="nav">
      <h1>DrugIntel.ai</h1>
      <router-link to="/">仪表盘</router-link>
      <router-link to="/news">新闻</router-link>
      <router-link to="/chat">问答</router-link>
      <router-link to="/alerts">告警</router-link>
      <router-link to="/monitor">监控</router-link>
    </aside>
    <main class="main">
      <router-view />
    </main>
  </div>
</template>
