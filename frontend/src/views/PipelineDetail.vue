<template>
  <div>
    <header class="ed-head reveal">
      <router-link to="/pipeline" class="meta">← 返回管线列表</router-link>
      <div class="ed-kicker">Pipeline · 资产详情</div>
      <h1 class="ed-title">{{ asset?.drug_name || '…' }}</h1>
      <p class="ed-lede">
        {{ asset?.company_name }} · {{ asset?.indication || '适应症未标注' }} ·
        {{ asset?.stage_label || asset?.current_stage }}
      </p>
    </header>

    <p v-if="error" class="form-error">{{ error }}</p>
    <div v-if="loading" class="meta">加载中…</div>

    <template v-else-if="asset">
      <section class="card reveal">
        <div class="sec-mark"><span class="no">01</span><h3>当前状态</h3><span class="rule"></span></div>
        <dl class="kv">
          <div><dt>药物</dt><dd>{{ asset.drug_name }}</dd></div>
          <div><dt>通用名</dt><dd>{{ asset.generic_name || '—' }}</dd></div>
          <div><dt>机制 / 靶点</dt><dd>{{ asset.mechanism || '—' }}</dd></div>
          <div><dt>阶段</dt><dd>{{ asset.stage_label }}</dd></div>
          <div><dt>治疗领域</dt><dd>{{ asset.therapeutic_area || '—' }}</dd></div>
          <div><dt>区域</dt><dd>{{ asset.region || '—' }}</dd></div>
          <div><dt>状态</dt><dd>{{ asset.status }}</dd></div>
          <div><dt>来源</dt><dd><a v-if="asset.source_url" :href="asset.source_url" target="_blank" rel="noopener">官网管线页</a><span v-else>—</span></dd></div>
        </dl>
      </section>

      <section class="card reveal">
        <div class="sec-mark"><span class="no">02</span><h3>变更时间线</h3><span class="rule"></span></div>
        <div v-if="!(asset.changes || []).length" class="meta">尚无变更记录</div>
        <ul v-else class="timeline">
          <li v-for="c in asset.changes" :key="c.id">
            <div class="t-head">
              <span class="kind" :class="c.change_kind">{{ kindLabel(c.change_kind) }}</span>
              <span class="mono">{{ formatTime(c.detected_at) }}</span>
            </div>
            <p>
              <strong>{{ c.field }}</strong>：
              {{ c.old_label || c.old_value || '—' }} → {{ c.new_label || c.new_value || '—' }}
            </p>
            <p v-if="c.snapshot_id" class="meta">
              快照 #{{ c.snapshot_id }}
              <a v-if="c.prev_snapshot_id" href="#" @click.prevent>对比上次 #{{ c.prev_snapshot_id }}</a>
            </p>
            <div v-if="c.snapshot_id" class="snap-img">
              <img :src="api.pipelineSnapshotImageUrl(c.snapshot_id, 0)" alt="当次管线快照" loading="lazy" />
            </div>
          </li>
        </ul>
      </section>

      <section class="card reveal">
        <div class="sec-mark"><span class="no">03</span><h3>关联交易</h3><span class="rule"></span></div>
        <ul v-if="(asset.deals || []).length" class="deal-list">
          <li v-for="d in asset.deals" :key="d.id">
            <span class="pill">{{ d.deal_type }}</span>
            {{ d.counterparty || '' }} — {{ d.summary }}
          </li>
        </ul>
        <p v-else class="meta">暂无</p>
      </section>

      <section class="card reveal">
        <div class="sec-mark"><span class="no">04</span><h3>关联新闻</h3><span class="rule"></span></div>
        <ul v-if="(asset.related_news || []).length" class="news-list">
          <li v-for="n in asset.related_news" :key="n.id">
            <router-link :to="`/news/${n.id}`">{{ n.title }}</router-link>
            <span class="mono meta">{{ formatTime(n.publish_time) }}</span>
          </li>
        </ul>
        <p v-else class="meta">暂无匹配新闻</p>
      </section>
    </template>
  </div>
</template>

<script setup>
import { onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { api } from '../api'
import { formatTime } from '../format'
import { useAsync } from '../composables'

const route = useRoute()
const asset = ref(null)
const { loading, error, run } = useAsync()

function kindLabel(k) {
  return { created: '新建', updated: '更新', removed: '消失' }[k] || k
}

async function load() {
  const id = Number(route.params.id)
  const data = await run(() => api.pipelineAsset(id))
  asset.value = data || null
}

watch(() => route.params.id, load)
onMounted(load)
</script>

<style scoped>
.kv {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 12px;
  margin: 0;
}
.kv dt { font-size: 12px; color: var(--ink-mute); font-weight: 700; }
.kv dd { margin: 4px 0 0; }
.timeline { list-style: none; padding: 0; margin: 0; display: grid; gap: 16px; }
.timeline li { border-left: 2px solid var(--line); padding-left: 14px; }
.t-head { display: flex; gap: 12px; align-items: center; margin-bottom: 4px; }
.kind { font-size: 12px; font-weight: 700; }
.kind.removed { color: var(--clay); }
.snap-img img {
  max-width: min(100%, 480px);
  border-radius: 8px;
  border: 1px solid var(--line);
  margin-top: 8px;
}
.deal-list, .news-list { list-style: none; padding: 0; margin: 0; display: grid; gap: 8px; }
</style>
