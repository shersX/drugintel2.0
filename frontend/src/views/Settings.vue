<template>
  <div>
    <!-- 大模型：三栏工作台 -->
    <div v-show="activeTab === 'models'" class="models-page reveal">
      <header class="models-hero">
        <h2 class="models-title">模型配置</h2>
        <p class="models-desc">管理对话、嵌入、重排与视觉模型组合</p>
      </header>

      <div class="models-work">
        <!-- 左：配置列表 -->
        <aside class="models-rail card">
          <div class="rail-head">
            <span class="rail-label">模型组合</span>
          </div>
          <ul class="rail-list" role="listbox" aria-label="已保存配置">
            <li
              v-for="item in profiles"
              :key="item.id"
              role="option"
              class="rail-item"
              :class="{
                on: selectedId === item.id && editingId !== 'new',
                active: item.is_active,
                warn: profileHasWarn(item),
              }"
              :aria-selected="selectedId === item.id && editingId !== 'new'"
              @click="selectProfile(item.id)"
            >
              <div class="rail-item-main">
                <strong class="rail-name">{{ item.name || `配置 #${item.id}` }}</strong>
                <span v-if="item.is_active" class="rail-badge">使用中</span>
              </div>
              <span class="rail-sub mono">{{ shortModel(item.chat_model) }}</span>
              <span v-if="profileHasWarn(item)" class="rail-dot" title="存在缺 Key 或未配置视觉" />
            </li>
          </ul>
          <p v-if="!profiles.length && !loading && editingId !== 'new'" class="rail-empty meta">尚无已保存配置</p>
          <button
            type="button"
            class="secondary rail-add"
            :disabled="busy || editingId === 'new'"
            @click="startCreate"
          >新增配置</button>
        </aside>

        <!-- 中：概览 / 编辑 -->
        <section class="models-main card">
          <template v-if="editingId === 'new'">
            <div class="main-head">
              <h3>新增一套接口</h3>
              <p class="meta">填写 Key 与模型后保存，再在右侧启用。</p>
            </div>
            <ProfileForm
              :key="draftKey"
              :model="draft"
              :busy="busy"
              :notices="draftNotices"
              allow-sync
              show-cancel
              submit-label="保存"
              @submit="create"
              @test="testDraft"
              @cancel="cancelEdit"
            />
            <p v-if="error" class="form-error">{{ error }}</p>
          </template>

          <template v-else-if="selectedProfile && editingId === selectedProfile.id">
            <div class="main-head">
              <h3>编辑 · {{ selectedProfile.name || `配置 #${selectedProfile.id}` }}</h3>
              <p class="meta">修改后点表单底部「保存修改」写入；启用请用右侧按钮。</p>
            </div>
            <ProfileForm
              :model="selectedProfile"
              :stamp="revision"
              :busy="busy"
              :notices="selectedProfile.notices"
              :profile-id="selectedProfile.id"
              :keep-chat="selectedProfile.has_chat_key"
              :keep-embedding="selectedProfile.has_embedding_key"
              :keep-rerank="selectedProfile.has_reranker_key"
              :keep-vision="selectedProfile.has_vision_key"
              show-cancel
              submit-label="保存修改"
              @submit="save(selectedProfile, $event)"
              @test="testSaved(selectedProfile, $event)"
              @cancel="cancelEdit"
            />
            <p v-if="selectedProfile.error" class="form-error">{{ selectedProfile.error }}</p>
          </template>

          <template v-else-if="selectedProfile">
            <div class="main-head">
              <h3>当前配置</h3>
              <p class="meta">{{ selectedProfile.name || `配置 #${selectedProfile.id}` }}</p>
            </div>
            <div class="slot-grid">
              <article
                v-for="slot in slotCards"
                :key="slot.key"
                class="slot-card"
                :class="{ warn: slot.warn }"
              >
                <div class="slot-k">{{ slot.label }}</div>
                <div class="slot-v mono">{{ slot.model }}</div>
                <div class="slot-meta">{{ slot.meta }}</div>
              </article>
            </div>
          </template>

          <template v-else>
            <div class="main-empty">
              <div class="empty-title">还没有保存的接口</div>
              <p class="meta">点左侧「新增配置」，保存后再启用。</p>
              <button type="button" :disabled="busy" @click="startCreate">新增配置</button>
            </div>
          </template>
        </section>

        <!-- 右：状态与操作 -->
        <aside class="models-side card">
          <div class="side-block">
            <div class="status-label">生效配置</div>
            <div class="side-active-name">{{ activeSourceLabel }}</div>
            <p v-if="!activeProfile" class="meta side-hint">未启用数据库配置时，对话/嵌入/重排回退到 .env</p>
          </div>

          <div class="side-block side-dims">
            <div class="side-dim">
              <span class="status-label">库向量维度</span>
              <strong class="mono">{{ vectorDim ?? '—' }}</strong>
            </div>
            <div class="side-dim">
              <span class="status-label">本配置嵌入维</span>
              <strong class="mono">{{ selectedProfile?.embedding_dim ?? '—' }}</strong>
            </div>
          </div>
          <p v-if="selectedDimMismatch" class="status-warn">
            本配置嵌入维度与库中不一致，启用或保存时会要求确认并重建向量索引。
          </p>
          <p v-else-if="dimMismatch && activeProfile" class="status-warn">
            当前生效配置的嵌入维度与库中不一致。
          </p>

          <div class="side-block">
            <div class="status-label">四槽就绪</div>
            <ul class="ready-list">
              <li v-for="cap in sideCaps" :key="cap.key" :class="{ warn: cap.warn }">
                <span class="ready-k">{{ cap.label }}</span>
                <span class="ready-v mono">{{ cap.text }}</span>
              </li>
            </ul>
          </div>

          <div class="side-actions">
            <button
              v-if="selectedProfile && editingId !== 'new'"
              type="button"
              :disabled="busy || selectedProfile.is_active"
              @click="activate(selectedProfile)"
            >{{ selectedProfile.is_active ? '已启用' : '启用此配置' }}</button>
            <button
              v-if="selectedProfile && editingId !== selectedProfile.id && editingId !== 'new'"
              type="button"
              class="secondary"
              :disabled="busy"
              @click="startEdit(selectedProfile.id)"
            >编辑此配置</button>
            <button
              v-if="editingId !== null"
              type="button"
              class="secondary"
              :disabled="busy"
              @click="cancelEdit"
            >取消编辑</button>
            <button
              v-if="selectedProfile && editingId !== 'new'"
              type="button"
              class="ghost danger-ghost"
              :disabled="busy"
              @click="remove(selectedProfile)"
            >删除</button>
          </div>
          <p v-if="selectedProfile?.error" class="form-error">{{ selectedProfile.error }}</p>
          <p v-if="error && editingId !== 'new'" class="form-error">{{ error }}</p>
        </aside>
      </div>
    </div>

    <!-- RAG -->
    <section v-show="activeTab === 'rag'" class="card reveal">
      <div class="sec-mark"><span class="no">01</span><h3>RAG 检索参数</h3><span class="rule"></span></div>
      <p class="meta hint">
        问答检索与生成共用此配置。客户端不再传 top_k。向量权重越高越偏语义检索，BM25 权重为 1−向量权重；温度越高回答越发散。
      </p>
      <div class="field-grid" :class="{ 'rag-readonly': !ragEditing }">
        <div class="field">
          <label for="rag-top-k">top_k（1–50）</label>
          <p class="field-help">重排后进入回答的资料条数</p>
          <input id="rag-top-k" type="number" min="1" max="50" v-model.number="ragForm.top_k" :disabled="!ragEditing || ragBusy" />
        </div>
        <div class="field">
          <label for="rag-min-score">相关性阈值（0–1）</label>
          <p class="field-help">向量检索最低相似度，过低结果会被过滤</p>
          <input id="rag-min-score" type="number" min="0" max="1" step="0.01" v-model.number="ragForm.min_relevance_score" :disabled="!ragEditing || ragBusy" />
        </div>
        <div class="field">
          <label for="rag-vec-w">向量权重（0–1）</label>
          <p class="field-help">当前 BM25 权重 ≈ {{ ragBm25Weight }}</p>
          <input id="rag-vec-w" type="number" min="0" max="1" step="0.05" v-model.number="ragForm.hybrid_vector_weight" :disabled="!ragEditing || ragBusy" />
        </div>
        <div class="field">
          <label for="rag-mult">重排候选倍数（1–5）</label>
          <p class="field-help">候选池 = top_k × 倍数，默认 2</p>
          <input id="rag-mult" type="number" min="1" max="5" v-model.number="ragForm.rerank_pool_multiplier" :disabled="!ragEditing || ragBusy" />
        </div>
        <div class="field">
          <label for="rag-hist">对话历史轮数（1–40）</label>
          <p class="field-help">改写与生成可见的近期消息条数</p>
          <input id="rag-hist" type="number" min="1" max="40" v-model.number="ragForm.history_turns" :disabled="!ragEditing || ragBusy" />
        </div>
        <div class="field">
          <label for="rag-temp">生成温度（0–2）</label>
          <p class="field-help">问答 / 改写共用；越高越发散</p>
          <input id="rag-temp" type="number" min="0" max="2" step="0.05" v-model.number="ragForm.temperature" :disabled="!ragEditing || ragBusy" />
        </div>
      </div>
      <div class="row rag-actions">
        <template v-if="!ragEditing">
          <button type="button" class="secondary" :disabled="ragBusy" @click="startRagEdit">编辑</button>
        </template>
        <template v-else>
          <button type="button" :disabled="ragBusy" @click="saveRag">{{ ragBusy ? '保存中…' : '保存' }}</button>
          <button type="button" class="secondary" :disabled="ragBusy" @click="cancelRagEdit">取消</button>
        </template>
      </div>
      <p v-if="ragMsg" class="meta" :class="{ 'form-error': ragErr }">{{ ragMsg }}</p>
    </section>

    <!-- 邮件 SMTP -->
    <section v-show="activeTab === 'mail'" class="card reveal mail-card">
      <div class="sec-mark"><span class="no">01</span><h3>告警邮件 SMTP</h3><span class="rule"></span></div>
      <p class="meta hint">
        监测订阅命中后经此通道发信。建议先保存配置，再发测试邮件确认可通。
        <span v-if="smtpForm.source === 'env' && smtpForm.env_host">当前生效来自 .env，保存后将写入数据库。</span>
      </p>
      <div class="mail-status" :class="{ ok: smtpForm.ready, bad: !smtpForm.ready }">
        <strong>{{ smtpForm.message || (smtpForm.ready ? '通道已就绪' : '通道未就绪') }}</strong>
        <span v-if="smtpForm.password_set" class="meta">密码已保存</span>
      </div>
      <div class="smtp-fields">
        <div class="field">
          <label for="smtp-host">SMTP 主机</label>
          <p class="field-help">邮箱服务商的发信服务器，如 QQ <code>smtp.qq.com</code>、163 <code>smtp.163.com</code>、Gmail <code>smtp.gmail.com</code></p>
          <input id="smtp-host" type="text" v-model="smtpForm.host" placeholder="smtp.qq.com" autocomplete="off" />
        </div>
        <div class="field">
          <label for="smtp-port">端口</label>
          <p class="field-help">网易/QQ 等若 587 超时，改用 <code>465</code>（SSL，无需 STARTTLS）；<code>587</code> 则勾选 STARTTLS</p>
          <input id="smtp-port" type="number" min="1" max="65535" v-model.number="smtpForm.port" />
        </div>
        <div class="field">
          <label for="smtp-user">用户名（登录账号）</label>
          <p class="field-help">用来<strong>登录 SMTP</strong>的账号，多数邮箱填完整邮箱地址（如 <code>name@qq.com</code>），不是昵称</p>
          <input id="smtp-user" type="text" v-model="smtpForm.user" placeholder="name@qq.com" autocomplete="username" />
        </div>
        <div class="field">
          <label for="smtp-password">密码 / 授权码</label>
          <p class="field-help">多数服务商要填网页邮箱里生成的<strong>授权码</strong>，不是登录密码；已保存后留空表示不改</p>
          <input
            id="smtp-password"
            type="password"
            v-model="smtpForm.password"
            :placeholder="smtpForm.password_set ? '已设置，留空不改' : '粘贴授权码'"
            autocomplete="new-password"
          />
        </div>
        <div class="field smtp-from">
          <label for="smtp-from">发件人（收件人看到的 From）</label>
          <p class="field-help">出现在邮件「发件人」里的地址；个人邮箱一般与用户名填<strong>同一个邮箱</strong>即可</p>
          <input id="smtp-from" type="text" v-model="smtpForm.from_addr" placeholder="name@qq.com（可与用户名相同）" />
        </div>
      </div>
      <div class="smtp-toggles">
        <label class="check"><input type="checkbox" v-model="smtpForm.use_tls" /> 启用 STARTTLS（仅端口 587；465 会自动走 SSL）</label>
        <label class="check"><input type="checkbox" v-model="smtpForm.enabled" /> 启用邮件通道</label>
      </div>
      <div class="smtp-actions-block">
        <div class="row smtp-actions">
          <button type="button" :disabled="smtpBusy" @click="saveSmtp">{{ smtpBusy ? '保存中…' : '保存配置' }}</button>
        </div>
        <div class="smtp-test-row">
          <div class="field smtp-test-input">
            <label for="smtp-test-to">测试收件邮箱</label>
            <p class="field-help">配置齐备后发一封测试信，确认通道可通</p>
            <input id="smtp-test-to" type="email" v-model="smtpTestTo" placeholder="you@example.com" />
          </div>
          <button
            type="button"
            class="secondary"
            :disabled="smtpBusy || !canTestSmtp || !smtpTestTo.trim()"
            @click="testSmtp"
          >{{ smtpBusy ? '处理中…' : '发送测试邮件' }}</button>
        </div>
        <p v-if="!canTestSmtp" class="meta smtp-test-hint">请先填完主机、登录账号、密码（或已保存密码）并启用通道，再测试。</p>
      </div>
      <p v-if="smtpMsg" class="meta" :class="{ 'form-error': smtpErr }">{{ smtpMsg }}</p>
    </section>

    <!-- 爬虫注册表 + 调度 -->
    <section v-show="activeTab === 'crawlers'" class="card reveal">
      <div class="sec-mark"><span class="no">01</span><h3>爬虫注册表</h3><span class="rule"></span></div>
      <div class="crawler-status" :class="{ warn: crawlerOffCount > 0 }">
        <strong>已启用 {{ crawlerOnCount }} / 共 {{ crawlerRows.length }}</strong>
        <span v-if="crawlerOffCount" class="meta">停用 {{ crawlerOffCount }} 个</span>
        <span v-if="crawlerDirtyCount" class="dirty-tag">{{ crawlerDirtyCount }} 行待保存</span>
      </div>
      <p class="meta hint">
        在此启停来源与采集调度；运行态与按源进度见
        <router-link to="/monitor">爬虫监控</router-link>。
        参数<strong>保存后下一轮</strong>生效。
      </p>
      <div v-if="crawlerLoading" class="meta">加载中…</div>
      <template v-else>
        <h4 class="sub-h">新闻爬虫</h4>
        <div class="table-wrap" v-if="newsCrawlerRows.length">
          <table class="cfg-table crawler-table">
            <thead>
              <tr>
                <th>来源</th><th>启用</th><th>页数</th><th>并发</th><th>抓详情</th><th></th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="row in newsCrawlerRows"
                :key="row.crawler_key"
                :class="{ 'is-off': !row.enabled, 'is-dirty': isCrawlerDirty(row) }"
              >
                <td>
                  <strong>{{ row.name }}</strong>
                  <div class="meta mono">{{ row.crawler_key }}</div>
                </td>
                <td>
                  <label class="enable-cell">
                    <input type="checkbox" v-model="row.enabled" />
                    <span :class="row.enabled ? 'on' : 'off'">{{ row.enabled ? '启用中' : '已停用' }}</span>
                  </label>
                </td>
                <td><input type="number" min="1" max="50" v-model.number="row.page_count" class="num" /></td>
                <td><input type="number" min="1" max="20" v-model.number="row.concurrency" class="num" /></td>
                <td><input type="checkbox" v-model="row.fetch_details" /></td>
                <td class="crawler-save-cell">
                  <button
                    type="button"
                    class="secondary"
                    :disabled="crawlerBusy === row.crawler_key || !isCrawlerDirty(row)"
                    @click="saveCrawler(row)"
                  >{{ crawlerBusy === row.crawler_key ? '…' : (crawlerSavedKey === row.crawler_key ? '已保存' : '保存') }}</button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <p v-else class="meta">暂无新闻爬虫</p>

        <h4 class="sub-h">新闻采集调度</h4>
        <div class="crawl-status">
          <span class="pill" :class="crawlLocked ? 'ok' : ''">{{ crawlLocked ? '调度运行中' : '未启动' }}</span>
          <span class="meta" v-if="crawlActive">本轮进行中</span>
        </div>
        <div v-if="crawlStatus && crawlStatus.llm_ready === false" class="form-error">
          {{ crawlStatus.llm_message || '尚未配置 LLM，无法启动采集。' }}
          <router-link to="/settings?tab=models">前往模型配置</router-link>
        </div>
        <div class="field">
          <label>本轮来源（仅已启用）</label>
          <div class="source-chip-row">
            <button
              type="button"
              v-for="row in newsEnabledRows"
              :key="row.crawler_key"
              class="source-chip"
              :class="{ on: crawlSelected.includes(row.crawler_key) }"
              :disabled="crawlLocked"
              @click="toggleCrawlSource(row.crawler_key)"
            >{{ row.name || row.crawler_key }}</button>
          </div>
          <p class="meta" v-if="!newsEnabledRows.length">请先启用至少一个新闻爬虫</p>
        </div>
        <div class="field">
          <label>节奏</label>
          <div class="seg">
            <button type="button" class="seg-btn" :class="{ on: crawlMode === 'manual' }" :disabled="crawlLocked" @click="crawlMode = 'manual'">手动</button>
            <button type="button" class="seg-btn" :class="{ on: crawlMode === 'interval' }" :disabled="crawlLocked" @click="crawlMode = 'interval'">间隔</button>
            <button type="button" class="seg-btn" :class="{ on: crawlMode === 'hourly' }" :disabled="crawlLocked" @click="crawlMode = 'hourly'">每小时</button>
            <button type="button" class="seg-btn" :class="{ on: crawlMode === 'daily' }" :disabled="crawlLocked" @click="crawlMode = 'daily'">每天</button>
          </div>
        </div>
        <div class="field" v-if="crawlMode === 'interval'">
          <label>间隔分钟（≥15）</label>
          <input type="number" min="15" max="1440" v-model.number="crawlInterval" :disabled="crawlLocked" />
        </div>
        <div class="field" v-if="crawlMode === 'daily'">
          <label>每天时刻</label>
          <input type="time" v-model="crawlDailyTime" :disabled="crawlLocked" />
        </div>
        <div class="row">
          <button type="button" :disabled="!canStartCrawl" @click="startCrawlSchedule">
            {{ crawlActionBusy && !crawlLocked ? '启动中…' : '启动' }}
          </button>
          <button type="button" class="secondary" :disabled="!crawlLocked || crawlActionBusy" @click="stopCrawlSchedule">停止</button>
          <button type="button" class="ghost" :disabled="crawlActionBusy || crawlLocked" @click="reprocessCrawlPending">补跑积压</button>
        </div>
        <p v-if="crawlActionMsg" class="meta" :class="{ 'form-error': crawlActionErr }">{{ crawlActionMsg }}</p>

        <h4 class="sub-h">管线爬虫</h4>
        <div class="table-wrap" v-if="pipelineCrawlerRows.length">
          <table class="cfg-table crawler-table">
            <thead>
              <tr>
                <th>来源</th><th>启用</th><th>说明</th><th></th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="row in pipelineCrawlerRows"
                :key="row.crawler_key"
                :class="{ 'is-off': !row.enabled, 'is-dirty': isCrawlerDirty(row) }"
              >
                <td>
                  <strong>{{ row.name }}</strong>
                  <div class="meta mono">{{ row.crawler_key }}</div>
                </td>
                <td>
                  <label class="enable-cell">
                    <input type="checkbox" v-model="row.enabled" />
                    <span :class="row.enabled ? 'on' : 'off'">{{ row.enabled ? '启用中' : '已停用' }}</span>
                  </label>
                </td>
                <td class="meta">下载管线图片 → 视觉模型抽取（调度见下方）</td>
                <td class="crawler-save-cell">
                  <button
                    type="button"
                    class="secondary"
                    :disabled="crawlerBusy === row.crawler_key || !isCrawlerDirty(row)"
                    @click="saveCrawler(row)"
                  >{{ crawlerBusy === row.crawler_key ? '…' : (crawlerSavedKey === row.crawler_key ? '已保存' : '保存') }}</button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <p v-else class="meta">暂无管线爬虫</p>

        <h4 class="sub-h">管线同步调度</h4>
        <p v-if="!visionReady" class="form-error">
          请先在
          <router-link to="/settings?tab=models">模型配置</router-link>
          中启用视觉模型后再同步管线。
        </p>
        <p v-else class="meta">视觉模型：{{ visionModel || '已就绪' }}</p>
        <div class="field">
          <label>来源 URL</label>
          <input v-model="pipeSourceUrl" type="url" placeholder="https://www.simcere.com/kxcx/yggx.aspx" />
        </div>
        <div class="field">
          <label>节奏</label>
          <div class="pipe-schedule-row">
            <div class="seg">
              <button type="button" class="seg-btn" :class="{ on: pipeMode === 'manual' }" @click="pipeMode = 'manual'">手动</button>
              <button type="button" class="seg-btn" :class="{ on: pipeMode === 'interval' }" @click="pipeMode = 'interval'">间隔</button>
              <button type="button" class="seg-btn" :class="{ on: pipeMode === 'daily' }" @click="pipeMode = 'daily'">每天</button>
              <button type="button" class="seg-btn" :class="{ on: pipeMode === 'weekly' }" @click="pipeMode = 'weekly'">每周</button>
            </div>
            <div class="row pipe-actions">
              <button type="button" :disabled="!visionReady || pipeBusy" @click="syncPipeline(false)">
                {{ pipeBusy ? '同步中…' : '立即同步管线' }}
              </button>
              <button type="button" class="secondary" :disabled="!visionReady || pipeBusy" @click="syncPipeline(true)">强制重跑视觉</button>
              <button type="button" class="secondary" :disabled="pipeBusy" @click="savePipeSchedule">保存调度</button>
              <button type="button" class="ghost" :disabled="pipeBusy || !pipeRunning" @click="stopPipeSchedule">停止定时</button>
            </div>
          </div>
        </div>
        <div class="field" v-if="pipeMode === 'interval'">
          <label>间隔分钟（≥15）</label>
          <input type="number" min="15" v-model.number="pipeInterval" />
        </div>
        <div class="field" v-if="pipeMode === 'daily' || pipeMode === 'weekly'">
          <label>时刻</label>
          <input type="time" v-model="pipeDailyTime" />
        </div>
        <div class="field" v-if="pipeMode === 'weekly'">
          <label>星期（0=周一 … 6=周日）</label>
          <input type="number" min="0" max="6" v-model.number="pipeWeeklyDay" />
        </div>
        <p v-if="pipeMsg" class="meta" :class="{ 'form-error': pipeErr }">{{ pipeMsg }}</p>
        <p class="meta">定时状态：{{ pipeRunning ? `运行中（${pipeMode}）` : '未启动' }}</p>
      </template>
      <p v-if="crawlerMsg" class="meta" :class="{ 'form-error': crawlerErr }">{{ crawlerMsg }}</p>
    </section>

    <!-- 关键词 -->
    <section v-show="activeTab === 'keywords'" class="card reveal">
      <div class="sec-mark"><span class="no">01</span><h3>过滤关键词</h3><span class="rule"></span></div>
      <p class="meta hint">修改后下一轮采集/过滤立即生效（服务端缓存已清）。首次启动会从 keywords.yaml 导入。</p>

      <div class="kw-toolbar">
        <div class="seg">
          <button type="button" class="seg-btn" :class="{ on: kwCategory === '靶点' }" @click="setKwCategory('靶点')">靶点</button>
          <button type="button" class="seg-btn" :class="{ on: kwCategory === '公司' }" @click="setKwCategory('公司')">公司</button>
        </div>
        <input class="search" type="search" placeholder="搜索规范名或别名" v-model="kwQuery" @keyup.enter="loadKeywords(1)" />
        <button type="button" class="secondary" :disabled="kwBusy" @click="loadKeywords(1)">搜索</button>
      </div>

      <div class="kw-new">
        <input type="text" placeholder="新规范名" v-model="kwNew.canonical" />
        <input type="text" placeholder="别名，逗号分隔" v-model="kwNew.aliasesText" />
        <button type="button" :disabled="kwBusy || !kwNew.canonical.trim()" @click="createKeyword">新增</button>
      </div>

      <div class="table-wrap" v-if="kwItems.length">
        <table class="cfg-table">
          <thead>
            <tr>
              <th>规范名</th>
              <th>别名</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in kwItems" :key="item.id">
              <td><input type="text" v-model="item.canonical" class="wide" /></td>
              <td><input type="text" v-model="item.aliasesText" class="wide" placeholder="逗号分隔" /></td>
              <td class="actions">
                <button type="button" class="secondary" :disabled="kwBusy" @click="saveKeyword(item)">保存</button>
                <button type="button" class="ghost danger-ghost" :disabled="kwBusy" @click="removeKeyword(item)">删除</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-else-if="!kwBusy" class="empty">
        <div class="empty-title">暂无关键词</div>
        <p>可新增，或从 YAML 重新导入。</p>
      </div>

      <div class="row kw-pager">
        <button type="button" class="secondary" :disabled="kwPage <= 1 || kwBusy" @click="loadKeywords(kwPage - 1)">上一页</button>
        <span class="meta">第 {{ kwPage }} 页 · 共 {{ kwTotal }} 条</span>
        <button type="button" class="secondary" :disabled="kwPage * kwPageSize >= kwTotal || kwBusy" @click="loadKeywords(kwPage + 1)">下一页</button>
        <button type="button" class="ghost" :disabled="kwBusy" @click="reimportKeywords">从 YAML 重新导入</button>
      </div>
      <p v-if="kwMsg" class="meta" :class="{ 'form-error': kwErr }">{{ kwMsg }}</p>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../api'
import { useAsync } from '../composables'
import ProfileForm from './ProfileForm.vue'

const route = useRoute()
const router = useRouter()

const tabIds = new Set(['models', 'rag', 'mail', 'crawlers', 'keywords'])
const activeTab = ref(tabIds.has(route.query.tab) ? String(route.query.tab) : 'models')

const { loading, error, run } = useAsync()
const profiles = ref([])
const vectorDim = ref(null)
const busy = ref(false)
const slotLabel = { chat: '对话', embedding: '嵌入', rerank: '重排', vision: '视觉' }
const draftNotices = reactive({ chat: null, embedding: null, rerank: null, vision: null })
const revision = ref(0)
const draftKey = ref(0)
const draft = reactive(blank())
/** @type {import('vue').Ref<'new' | number | null>} */
const editingId = ref(null)
/** 左栏选中的 profile id（浏览/编辑目标） */
const selectedId = ref(null)

const activeProfile = computed(() => profiles.value.find((item) => item.is_active) || null)
const selectedProfile = computed(() =>
  profiles.value.find((item) => item.id === selectedId.value) || null,
)

const activeSourceLabel = computed(() => {
  if (activeProfile.value) return activeProfile.value.name || `配置 #${activeProfile.value.id}`
  return '未启用 · 回退 .env'
})

function capsFor(row) {
  if (!row) {
    return {
      chat: { text: '.env 默认', warn: false },
      embedding: { text: '.env 默认', warn: false },
      rerank: { text: '.env 默认', warn: false },
      vision: { text: '未配置', warn: true },
    }
  }
  return {
    chat: {
      text: row.has_chat_key ? (row.chat_model || '—') : '缺少 Key',
      warn: !row.has_chat_key,
    },
    embedding: {
      text: row.has_embedding_key
        ? `${row.embedding_model || '—'} · ${row.embedding_dim || '—'} 维`
        : '缺少 Key',
      warn: !row.has_embedding_key,
    },
    rerank: {
      text: row.has_reranker_key ? (row.reranker_model || '—') : '缺少 Key',
      warn: !row.has_reranker_key,
    },
    vision: {
      text: row.vision_model || '未配置（管线同步需要）',
      warn: !row.vision_model,
    },
  }
}

const sideCaps = computed(() => {
  const row = selectedProfile.value || activeProfile.value
  const caps = capsFor(row)
  return [
    { key: 'chat', label: '对话', ...caps.chat },
    { key: 'embedding', label: '嵌入', ...caps.embedding },
    { key: 'rerank', label: '重排', ...caps.rerank },
    { key: 'vision', label: '视觉', ...caps.vision },
  ]
})

const slotCards = computed(() => {
  const row = selectedProfile.value
  if (!row) return []
  return [
    {
      key: 'chat',
      label: '对话模型',
      model: row.chat_model || '—',
      meta: row.has_chat_key ? 'Key 已配置' : '缺少 Key',
      warn: !row.has_chat_key,
    },
    {
      key: 'embedding',
      label: '嵌入模型',
      model: row.embedding_model || '—',
      meta: row.has_embedding_key
        ? `Key 已配置 · ${row.embedding_dim || '—'} 维`
        : '缺少 Key',
      warn: !row.has_embedding_key,
    },
    {
      key: 'rerank',
      label: '重排模型',
      model: row.reranker_model || '—',
      meta: row.has_reranker_key ? 'Key 已配置' : '缺少 Key',
      warn: !row.has_reranker_key,
    },
    {
      key: 'vision',
      label: '视觉模型',
      model: row.vision_model || '未配置',
      meta: row.vision_model
        ? (row.has_vision_key ? 'Key 已配置' : '沿用对话 Key 或未单独存 Key')
        : '管线同步前需配置',
      warn: !row.vision_model,
    },
  ]
})

const dimMismatch = computed(() => {
  const row = activeProfile.value
  if (!row || vectorDim.value == null || row.embedding_dim == null) return false
  return Number(row.embedding_dim) !== Number(vectorDim.value)
})

const selectedDimMismatch = computed(() => {
  const row = selectedProfile.value
  if (!row || vectorDim.value == null || row.embedding_dim == null) return false
  return Number(row.embedding_dim) !== Number(vectorDim.value)
})

function shortModel(name) {
  if (!name) return '—'
  const s = String(name)
  const slash = s.lastIndexOf('/')
  return slash >= 0 ? s.slice(slash + 1) : s
}

function profileHasWarn(item) {
  return !item.has_chat_key || !item.has_embedding_key || !item.has_reranker_key || !item.vision_model
}

function syncSelection() {
  if (editingId.value === 'new') return
  const ids = new Set(profiles.value.map((p) => p.id))
  if (selectedId.value != null && ids.has(selectedId.value)) return
  const active = profiles.value.find((p) => p.is_active)
  selectedId.value = active?.id ?? profiles.value[0]?.id ?? null
}

function selectProfile(id) {
  selectedId.value = id
  if (editingId.value === 'new') {
    editingId.value = null
    error.value = ''
  } else if (editingId.value !== null && editingId.value !== id) {
    editingId.value = null
  }
}

function startCreate() {
  error.value = ''
  Object.assign(draft, blank())
  draftKey.value += 1
  editingId.value = 'new'
}

function startEdit(id) {
  selectedId.value = id
  editingId.value = id
  error.value = ''
}

function cancelEdit() {
  editingId.value = null
  error.value = ''
}

const ragForm = reactive({
  top_k: 10,
  min_relevance_score: 0.25,
  hybrid_vector_weight: 0.6,
  rerank_pool_multiplier: 2,
  history_turns: 12,
  temperature: 0.3,
})
const ragSnapshot = ref(null)
const ragEditing = ref(false)
const ragBm25Weight = computed(() => {
  const w = Number(ragForm.hybrid_vector_weight)
  if (!Number.isFinite(w)) return '—'
  return Math.max(0, Math.min(1, 1 - w)).toFixed(2)
})
const ragBusy = ref(false)
const smtpForm = reactive({
  host: '',
  port: 587,
  user: '',
  password: '',
  from_addr: '',
  use_tls: true,
  enabled: true,
  password_set: false,
  ready: false,
  message: '',
  source: 'db',
  env_host: '',
})
const smtpBusy = ref(false)
const smtpMsg = ref('')
const smtpErr = ref(false)
const smtpTestTo = ref('')
const ragMsg = ref('')
const ragErr = ref(false)

const crawlerRows = ref([])
const crawlerSnapshot = ref({})
const crawlerLoading = ref(false)
const crawlerBusy = ref('')
const crawlerSavedKey = ref('')
const crawlerMsg = ref('')
const crawlerErr = ref(false)
let crawlerSavedTimer = null

const crawlStatus = ref(null)
const crawlMode = ref('hourly')
const crawlDailyTime = ref('08:00')
const crawlInterval = ref(60)
const crawlSelected = ref([])
const crawlActionBusy = ref(false)
const crawlActionMsg = ref('')
const crawlActionErr = ref(false)

const visionReady = ref(false)
const visionModel = ref('')
const pipeSourceUrl = ref('https://www.simcere.com/kxcx/yggx.aspx')
const pipeMode = ref('manual')
const pipeInterval = ref(60)
const pipeDailyTime = ref('08:00')
const pipeWeeklyDay = ref(0)
const pipeRunning = ref(false)
const pipeBusy = ref(false)
const pipeMsg = ref('')
const pipeErr = ref(false)

const crawlerOnCount = computed(() => crawlerRows.value.filter((r) => r.enabled).length)
const crawlerOffCount = computed(() => crawlerRows.value.length - crawlerOnCount.value)
const crawlerDirtyCount = computed(() => crawlerRows.value.filter((r) => isCrawlerDirty(r)).length)
const newsCrawlerRows = computed(() => crawlerRows.value.filter((r) => (r.kind || 'news') === 'news'))
const pipelineCrawlerRows = computed(() => crawlerRows.value.filter((r) => r.kind === 'pipeline'))
const newsEnabledRows = computed(() => newsCrawlerRows.value.filter((r) => r.enabled))
const crawlLocked = computed(() => Boolean(crawlStatus.value?.running))
const crawlActive = computed(() => Boolean(crawlStatus.value?.active))
const canStartCrawl = computed(() => {
  if (crawlLocked.value || crawlActionBusy.value) return false
  if (crawlStatus.value?.llm_ready === false) return false
  if (!crawlSelected.value.length) return false
  if (crawlMode.value === 'daily' && !crawlDailyTime.value) return false
  if (crawlMode.value === 'interval' && Number(crawlInterval.value) < 15) return false
  return true
})

const canTestSmtp = computed(() => {
  if (!smtpForm.enabled) return false
  if (!smtpForm.host.trim()) return false
  if (!smtpForm.user.trim() && !smtpForm.from_addr.trim()) return false
  if (!smtpForm.password.trim() && !smtpForm.password_set) return false
  return true
})

function crawlerSnapKey(row) {
  return JSON.stringify({
    enabled: Boolean(row.enabled),
    page_count: Number(row.page_count),
    concurrency: Number(row.concurrency),
    fetch_details: Boolean(row.fetch_details),
  })
}

function rememberCrawlerSnapshot(rows) {
  const map = {}
  for (const row of rows) map[row.crawler_key] = crawlerSnapKey(row)
  crawlerSnapshot.value = map
}

function isCrawlerDirty(row) {
  const prev = crawlerSnapshot.value[row.crawler_key]
  if (!prev) return false
  return prev !== crawlerSnapKey(row)
}

const kwCategory = ref('靶点')
const kwQuery = ref('')
const kwItems = ref([])
const kwPage = ref(1)
const kwPageSize = 20
const kwTotal = ref(0)
const kwBusy = ref(false)
const kwMsg = ref('')
const kwErr = ref(false)
const kwNew = reactive({ canonical: '', aliasesText: '' })
const loaded = reactive({ models: false, rag: false, mail: false, crawlers: false, keywords: false })

function applySmtp(data) {
  smtpForm.host = data.host || ''
  smtpForm.port = data.port ?? 587
  smtpForm.user = data.user || ''
  smtpForm.from_addr = data.from_addr || ''
  smtpForm.use_tls = data.use_tls !== false
  smtpForm.enabled = data.enabled !== false
  smtpForm.password_set = Boolean(data.password_set)
  smtpForm.ready = Boolean(data.ready)
  smtpForm.message = data.message || ''
  smtpForm.source = data.source || 'db'
  smtpForm.env_host = data.env_host || ''
  smtpForm.password = ''
}

function blank() {
  return {
    name: '',
    api_key: '',
    base_url: 'https://api.siliconflow.cn/v1',
    chat_model: 'deepseek-ai/DeepSeek-V4-Flash',
    embedding_api_key: '',
    embedding_base_url: 'https://api.siliconflow.cn/v1',
    embedding_model: 'BAAI/bge-m3',
    embedding_dim: 1024,
    reranker_api_key: '',
    reranker_base_url: 'https://api.siliconflow.cn/v1',
    reranker_model: 'BAAI/bge-reranker-v2-m3',
    vision_api_key: '',
    vision_base_url: 'https://api.siliconflow.cn/v1',
    vision_model: '',
  }
}

function parseAliases(text) {
  return String(text || '')
    .split(/[,，;；\n]/)
    .map((s) => s.trim())
    .filter(Boolean)
}

function applyDefaults(defaults) {
  if (!defaults) return
  draft.base_url = defaults.base_url || draft.base_url
  draft.chat_model = defaults.chat_model || draft.chat_model
  draft.embedding_base_url = defaults.embedding_base_url || draft.embedding_base_url
  draft.embedding_model = defaults.embedding_model || draft.embedding_model
  draft.embedding_dim = defaults.embedding_dim || draft.embedding_dim
  draft.reranker_base_url = defaults.reranker_base_url || draft.reranker_base_url
  draft.reranker_model = defaults.reranker_model || draft.reranker_model
  draft.vision_base_url = defaults.vision_base_url || draft.vision_base_url
  draft.vision_model = defaults.vision_model || draft.vision_model
}

function isDimMismatch(err) {
  return err?.status === 409 && err.detail?.code === 'dimension_mismatch'
}

async function load() {
  const data = await run(() => api.llmProfiles())
  if (!data) return
  profiles.value = (data.profiles || []).map((item) => ({
    ...item,
    api_key: '',
    embedding_api_key: '',
    reranker_api_key: '',
    vision_api_key: '',
    notices: { chat: null, embedding: null, rerank: null, vision: null },
    error: '',
  }))
  vectorDim.value = data.vector_dim
  applyDefaults(data.defaults)
  revision.value += 1
  loaded.models = true
  syncSelection()
}

async function create(form) {
  busy.value = true
  error.value = ''
  try {
    const before = new Set(profiles.value.map((p) => p.id))
    await api.createLlmProfile(form)
    Object.assign(draft, blank())
    draftKey.value += 1
    editingId.value = null
    await load()
    const added = profiles.value.find((p) => !before.has(p.id))
    if (added) selectedId.value = added.id
  } catch (e) {
    error.value = e.message || '保存失败'
  } finally {
    busy.value = false
  }
}

async function save(item, form, rebuild = false) {
  item.error = ''
  busy.value = true
  try {
    await api.updateLlmProfile(item.id, { ...form, rebuild })
    editingId.value = null
    await load()
  } catch (e) {
    if (!rebuild && isDimMismatch(e) && window.confirm(e.message)) {
      try {
        await api.updateLlmProfile(item.id, { ...form, rebuild: true })
        editingId.value = null
        await load()
      } catch (err) {
        item.error = err.message || '保存失败'
      }
      return
    }
    item.error = e.message || '保存失败'
  } finally {
    busy.value = false
  }
}

async function activate(item, rebuild = false) {
  item.error = ''
  busy.value = true
  try {
    await api.activateLlmProfile(item.id, rebuild)
    await load()
  } catch (e) {
    if (!rebuild && isDimMismatch(e) && window.confirm(e.message)) {
      try {
        await api.activateLlmProfile(item.id, true)
        await load()
      } catch (err) {
        item.error = err.message || '启用失败'
      }
      return
    }
    item.error = e.message || '启用失败'
  } finally {
    busy.value = false
  }
}

async function remove(item) {
  if (!window.confirm(`删除「${item.name || `配置 #${item.id}`}」？`)) return
  busy.value = true
  try {
    await api.deleteLlmProfile(item.id)
    if (editingId.value === item.id) editingId.value = null
    if (selectedId.value === item.id) selectedId.value = null
    await load()
  } catch (e) {
    error.value = e.message || '删除失败'
  } finally {
    busy.value = false
  }
}

function beginTest(target, slot) {
  const label = slotLabel[slot] || '接口'
  target[slot] = { ok: null, text: `正在测试${label}…` }
}

async function finishTest(target, slot, runFn) {
  beginTest(target, slot)
  const label = slotLabel[slot] || '接口'
  busy.value = true
  try {
    await runFn()
    target[slot] = { ok: true, text: `${label}连接成功` }
  } catch (e) {
    target[slot] = { ok: false, text: e.message || '连接失败' }
  } finally {
    busy.value = false
  }
}

async function testDraft(form) {
  if (form.ok === true || form.ok === false) {
    draftNotices[form.slot] = { ok: form.ok, text: form.text || (form.ok ? '成功' : '失败') }
    return
  }
  await finishTest(draftNotices, form.slot, () => api.testLlmProfile({
    base_url: form.base_url,
    api_key: form.api_key,
    slot: form.slot,
  }))
}

async function testSaved(item, form) {
  if (form.ok === true || form.ok === false) {
    item.notices[form.slot] = { ok: form.ok, text: form.text || (form.ok ? '成功' : '失败') }
    return
  }
  await finishTest(item.notices, form.slot, () => api.testLlmProfile({
    base_url: form.base_url,
    api_key: form.api_key,
    profile_id: item.id,
    slot: form.slot,
  }))
}

async function loadRag() {
  ragMsg.value = ''
  try {
    const data = await api.ragConfig()
    applyRagForm(data)
    ragEditing.value = false
    ragSnapshot.value = null
    loaded.rag = true
  } catch (e) {
    ragErr.value = true
    ragMsg.value = e.message || '加载失败'
  }
}

function applyRagForm(data) {
  if (!data) return
  ragForm.top_k = data.top_k ?? 10
  ragForm.min_relevance_score = data.min_relevance_score ?? 0.25
  ragForm.hybrid_vector_weight = data.hybrid_vector_weight ?? 0.6
  ragForm.rerank_pool_multiplier = data.rerank_pool_multiplier ?? 2
  ragForm.history_turns = data.history_turns ?? 12
  ragForm.temperature = data.temperature ?? 0.3
}

function snapshotRag() {
  return {
    top_k: ragForm.top_k,
    min_relevance_score: ragForm.min_relevance_score,
    hybrid_vector_weight: ragForm.hybrid_vector_weight,
    rerank_pool_multiplier: ragForm.rerank_pool_multiplier,
    history_turns: ragForm.history_turns,
    temperature: ragForm.temperature,
  }
}

function startRagEdit() {
  ragSnapshot.value = snapshotRag()
  ragEditing.value = true
  ragMsg.value = ''
  ragErr.value = false
}

function cancelRagEdit() {
  if (ragSnapshot.value) applyRagForm(ragSnapshot.value)
  ragSnapshot.value = null
  ragEditing.value = false
  ragMsg.value = ''
  ragErr.value = false
}

async function loadSmtp() {
  smtpMsg.value = ''
  smtpErr.value = false
  try {
    applySmtp(await api.smtpConfig())
    loaded.mail = true
  } catch (e) {
    smtpErr.value = true
    smtpMsg.value = e.message || '加载失败'
  }
}

async function saveSmtp({ quiet = false } = {}) {
  smtpBusy.value = true
  if (!quiet) {
    smtpMsg.value = ''
    smtpErr.value = false
  }
  try {
    const body = {
      host: smtpForm.host.trim(),
      port: smtpForm.port,
      user: smtpForm.user.trim(),
      from_addr: smtpForm.from_addr.trim() || smtpForm.user.trim(),
      use_tls: smtpForm.use_tls,
      enabled: smtpForm.enabled,
    }
    if (smtpForm.password.trim()) body.password = smtpForm.password.trim()
    applySmtp(await api.updateSmtpConfig(body))
    if (!quiet) {
      smtpMsg.value = smtpForm.ready
        ? '已保存，通道就绪'
        : (smtpForm.message ? `已保存。${smtpForm.message}` : '已保存，通道仍未就绪')
    }
    return true
  } catch (e) {
    smtpErr.value = true
    smtpMsg.value = e.message || '保存失败'
    return false
  } finally {
    smtpBusy.value = false
  }
}

async function testSmtp() {
  const to = smtpTestTo.value.trim()
  if (!to || !canTestSmtp.value) return
  smtpMsg.value = ''
  smtpErr.value = false
  // 先保存当前表单，避免测到旧库配置
  const saved = await saveSmtp({ quiet: true })
  if (!saved) return
  if (!smtpForm.ready) {
    smtpErr.value = true
    smtpMsg.value = smtpForm.message || '配置仍未就绪，无法发送测试邮件'
    return
  }
  smtpBusy.value = true
  try {
    await api.testSmtpConfig({ to_email: to })
    smtpMsg.value = `测试邮件已发出，请到 ${to} 查收收件箱（含垃圾箱）`
  } catch (e) {
    smtpErr.value = true
    smtpMsg.value = e.message || '测试失败'
  } finally {
    smtpBusy.value = false
  }
}

async function saveRag() {
  ragBusy.value = true
  ragMsg.value = ''
  ragErr.value = false
  try {
    const data = await api.updateRagConfig({
      top_k: ragForm.top_k,
      min_relevance_score: ragForm.min_relevance_score,
      hybrid_vector_weight: ragForm.hybrid_vector_weight,
      rerank_pool_multiplier: ragForm.rerank_pool_multiplier,
      history_turns: ragForm.history_turns,
      temperature: ragForm.temperature,
    })
    applyRagForm(data)
    ragSnapshot.value = null
    ragEditing.value = false
    ragMsg.value = '已保存'
  } catch (e) {
    ragErr.value = true
    ragMsg.value = e.message || '保存失败'
  } finally {
    ragBusy.value = false
  }
}

function applyCrawlStatus(status) {
  crawlStatus.value = status
  if (!status) return
  crawlMode.value = status.schedule_mode || 'hourly'
  crawlDailyTime.value = status.daily_time || '08:00'
  crawlInterval.value = status.interval_minutes || 60
  const enabledKeys = newsEnabledRows.value.map((r) => r.crawler_key)
  const enabled = new Set(enabledKeys)
  if (status.crawler_keys?.length) {
    crawlSelected.value = status.crawler_keys.filter((k) => enabled.has(k))
  } else {
    crawlSelected.value = [...enabledKeys]
  }
  if (!crawlSelected.value.length) crawlSelected.value = [...enabledKeys]
}

function applyPipeConfig(cfg) {
  if (!cfg) return
  pipeRunning.value = Boolean(cfg.running)
  pipeMode.value = cfg.schedule_mode || 'manual'
  pipeInterval.value = cfg.interval_minutes || 60
  pipeDailyTime.value = cfg.daily_time || '08:00'
  pipeWeeklyDay.value = cfg.weekly_day ?? 0
  if (cfg.source_url) pipeSourceUrl.value = cfg.source_url
}

function toggleCrawlSource(key) {
  if (crawlLocked.value) return
  if (crawlSelected.value.includes(key)) {
    crawlSelected.value = crawlSelected.value.filter((k) => k !== key)
  } else {
    crawlSelected.value = [...crawlSelected.value, key]
  }
}

async function loadCrawlers() {
  crawlerMsg.value = ''
  crawlerErr.value = false
  crawlerLoading.value = true
  crawlerSavedKey.value = ''
  try {
    const [data, status, vs, pipeCfg] = await Promise.all([
      api.adminCrawlers(),
      api.crawlStatus().catch(() => null),
      api.pipelineVisionStatus().catch(() => null),
      api.pipelineCrawlConfig().catch(() => null),
    ])
    crawlerRows.value = Array.isArray(data) ? data : []
    rememberCrawlerSnapshot(crawlerRows.value)
    applyCrawlStatus(status)
    visionReady.value = Boolean(vs?.ready)
    visionModel.value = vs?.model || ''
    if (!vs?.ready && vs?.message) {
      pipeMsg.value = vs.message
      pipeErr.value = true
    }
    applyPipeConfig(pipeCfg)
    loaded.crawlers = true
  } catch (e) {
    crawlerErr.value = true
    crawlerMsg.value = e.message || '加载失败'
    crawlerRows.value = []
    crawlerSnapshot.value = {}
  } finally {
    crawlerLoading.value = false
  }
}

async function startCrawlSchedule() {
  crawlActionMsg.value = ''
  crawlActionErr.value = false
  crawlActionBusy.value = true
  try {
    const enabled = new Set(newsEnabledRows.value.map((r) => r.crawler_key))
    const status = await api.crawlStart({
      schedule_mode: crawlMode.value,
      daily_time: crawlMode.value === 'daily' ? crawlDailyTime.value : null,
      interval_minutes: crawlMode.value === 'interval' ? crawlInterval.value : null,
      crawler_keys: crawlSelected.value.filter((k) => enabled.has(k)),
    })
    applyCrawlStatus(status)
    crawlActionMsg.value = '采集调度已启动'
  } catch (e) {
    crawlActionErr.value = true
    crawlActionMsg.value = e.message || '启动失败'
  } finally {
    crawlActionBusy.value = false
  }
}

async function stopCrawlSchedule() {
  crawlActionBusy.value = true
  crawlActionMsg.value = ''
  crawlActionErr.value = false
  try {
    const status = await api.crawlStop()
    applyCrawlStatus(status)
    crawlActionMsg.value = '已停止采集调度'
  } catch (e) {
    crawlActionErr.value = true
    crawlActionMsg.value = e.message || '停止失败'
  } finally {
    crawlActionBusy.value = false
  }
}

async function reprocessCrawlPending() {
  crawlActionBusy.value = true
  crawlActionMsg.value = ''
  crawlActionErr.value = false
  try {
    const stats = await api.crawlReprocess(50)
    crawlActionMsg.value = `补跑完成：捞取 ${stats.pending ?? 0} 条，ready ${stats.ready_updated ?? stats.after_embedding ?? 0}`
  } catch (e) {
    crawlActionErr.value = true
    crawlActionMsg.value = e.message || '补跑失败'
  } finally {
    crawlActionBusy.value = false
  }
}

async function syncPipeline(force) {
  pipeBusy.value = true
  pipeMsg.value = ''
  pipeErr.value = false
  try {
    if (!visionReady.value) throw new Error('请先配置并启用视觉模型')
    const data = await api.pipelineSync({
      force: Boolean(force),
      source_url: pipeSourceUrl.value || undefined,
    })
    pipeMsg.value = data?.skipped
      ? '图片未变化，已跳过视觉抽取'
      : `同步完成：新建 ${data?.stats?.created ?? 0} · 更新 ${data?.stats?.updated ?? 0} · 消失 ${data?.stats?.removed ?? 0}`
  } catch (e) {
    pipeErr.value = true
    const detail = e.detail
    pipeMsg.value = (typeof detail === 'object' && detail?.message) || e.message || '同步失败'
  } finally {
    pipeBusy.value = false
  }
}

async function savePipeSchedule() {
  pipeBusy.value = true
  pipeMsg.value = ''
  pipeErr.value = false
  try {
    if (!visionReady.value && pipeMode.value !== 'manual') {
      throw new Error('启用定时前请先配置视觉模型')
    }
    const data = await api.updatePipelineCrawlConfig({
      running: pipeMode.value !== 'manual',
      schedule_mode: pipeMode.value,
      interval_minutes: pipeInterval.value,
      daily_time: pipeDailyTime.value,
      weekly_day: pipeWeeklyDay.value,
      source_url: pipeSourceUrl.value,
      crawler_keys: ['simcere_pipeline'],
    })
    applyPipeConfig(data)
    pipeMsg.value = '管线调度已保存'
  } catch (e) {
    pipeErr.value = true
    pipeMsg.value = e.message || '保存失败'
  } finally {
    pipeBusy.value = false
  }
}

async function stopPipeSchedule() {
  pipeBusy.value = true
  try {
    const data = await api.updatePipelineCrawlConfig({ running: false, schedule_mode: 'manual' })
    applyPipeConfig(data)
    pipeMsg.value = '已停止管线定时'
    pipeErr.value = false
  } catch (e) {
    pipeErr.value = true
    pipeMsg.value = e.message || '停止失败'
  } finally {
    pipeBusy.value = false
  }
}

function ensureTabLoaded(tab) {
  if (tab === 'models' && !loaded.models) load()
  if (tab === 'rag' && !loaded.rag) loadRag()
  if (tab === 'mail' && !loaded.mail) loadSmtp()
  if (tab === 'crawlers' && !loaded.crawlers) loadCrawlers()
  if (tab === 'keywords' && !loaded.keywords) loadKeywords(1)
}

async function saveCrawler(row) {
  crawlerBusy.value = row.crawler_key
  crawlerMsg.value = ''
  crawlerErr.value = false
  try {
    const data = await api.updateAdminCrawler(row.crawler_key, {
      enabled: row.enabled,
      page_count: row.page_count,
      concurrency: row.concurrency,
      fetch_details: row.fetch_details,
    })
    Object.assign(row, data)
    crawlerSnapshot.value = {
      ...crawlerSnapshot.value,
      [row.crawler_key]: crawlerSnapKey(row),
    }
    crawlerMsg.value = `已保存「${row.name}」；下一轮采集生效`
    crawlerSavedKey.value = row.crawler_key
    if (crawlerSavedTimer) clearTimeout(crawlerSavedTimer)
    crawlerSavedTimer = setTimeout(() => {
      if (crawlerSavedKey.value === row.crawler_key) crawlerSavedKey.value = ''
    }, 1800)
  } catch (e) {
    crawlerErr.value = true
    crawlerMsg.value = e.message || '保存失败'
  } finally {
    crawlerBusy.value = ''
  }
}

function setKwCategory(cat) {
  kwCategory.value = cat
  loadKeywords(1)
}

async function loadKeywords(page = 1) {
  kwBusy.value = true
  kwMsg.value = ''
  kwErr.value = false
  try {
    const data = await api.adminKeywords({
      category: kwCategory.value,
      q: kwQuery.value.trim(),
      page,
      page_size: kwPageSize,
    })
    kwItems.value = (data.items || []).map((item) => ({
      ...item,
      aliasesText: (item.aliases || []).join(', '),
    }))
    kwTotal.value = data.total || 0
    kwPage.value = data.page || page
    loaded.keywords = true
  } catch (e) {
    kwErr.value = true
    kwMsg.value = e.message || '加载失败'
  } finally {
    kwBusy.value = false
  }
}

async function createKeyword() {
  kwBusy.value = true
  kwMsg.value = ''
  kwErr.value = false
  try {
    await api.createAdminKeyword({
      category: kwCategory.value,
      canonical: kwNew.canonical.trim(),
      aliases: parseAliases(kwNew.aliasesText),
    })
    kwNew.canonical = ''
    kwNew.aliasesText = ''
    kwMsg.value = '已新增'
    await loadKeywords(1)
  } catch (e) {
    kwErr.value = true
    kwMsg.value = e.message || '新增失败'
  } finally {
    kwBusy.value = false
  }
}

async function saveKeyword(item) {
  kwBusy.value = true
  kwMsg.value = ''
  kwErr.value = false
  try {
    await api.updateAdminKeyword(item.id, {
      category: kwCategory.value,
      canonical: item.canonical.trim(),
      aliases: parseAliases(item.aliasesText),
    })
    kwMsg.value = '已保存'
    await loadKeywords(kwPage.value)
  } catch (e) {
    kwErr.value = true
    kwMsg.value = e.message || '保存失败'
  } finally {
    kwBusy.value = false
  }
}

async function removeKeyword(item) {
  if (!window.confirm(`删除「${item.canonical}」？`)) return
  kwBusy.value = true
  kwMsg.value = ''
  kwErr.value = false
  try {
    await api.deleteAdminKeyword(item.id)
    kwMsg.value = '已删除'
    await loadKeywords(kwPage.value)
  } catch (e) {
    kwErr.value = true
    kwMsg.value = e.message || '删除失败'
  } finally {
    kwBusy.value = false
  }
}

async function reimportKeywords() {
  const overwrite = kwTotal.value > 0
  if (overwrite && !window.confirm('将清空当前过滤关键词并从 keywords.yaml 重新导入，继续？')) {
    return
  }
  kwBusy.value = true
  kwMsg.value = ''
  kwErr.value = false
  try {
    const data = await api.reimportAdminKeywords(overwrite)
    kwMsg.value = `已导入 ${data.inserted} 条`
    await loadKeywords(1)
  } catch (e) {
    kwErr.value = true
    kwMsg.value = e.message || '导入失败'
  } finally {
    kwBusy.value = false
  }
}

watch(activeTab, (tab) => {
  if (route.query.tab !== tab) {
    router.replace({ query: { ...route.query, tab } })
  }
  ensureTabLoaded(tab)
})

watch(
  () => route.query.tab,
  (tab) => {
    if (typeof tab === 'string' && tabIds.has(tab) && activeTab.value !== tab) {
      activeTab.value = tab
    }
  },
)

onMounted(() => {
  ensureTabLoaded(activeTab.value)
})
</script>

<style scoped>
.sub-h {
  margin: 18px 0 10px;
  font-size: var(--fs-sm);
  font-weight: 700;
  letter-spacing: 0.04em;
  color: var(--ink-soft);
}
.status-label {
  font-size: var(--fs-xs);
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--ink-mute);
  font-weight: 700;
  margin-bottom: 4px;
}
.status-warn { margin: 8px 0 0; color: var(--clay); font-size: var(--fs-sm); line-height: 1.45; }
.form-error { color: var(--clay); margin: 8px 0 0; }
.mono { font-family: var(--font-mono); }
.rag-readonly input:disabled {
  opacity: 1;
  color: var(--ink);
  background: color-mix(in srgb, var(--paper-deep) 55%, var(--surface));
  cursor: default;
}
.rag-actions { margin-top: 4px; gap: 10px; }

/* —— 模型配置三栏工作台 —— */
.models-page { display: grid; gap: 16px; }
.models-hero { margin: 0 0 4px; }
.models-title {
  margin: 0;
  font-family: var(--font-serif);
  font-size: var(--fs-h1);
  color: var(--pine);
  font-weight: 700;
}
.models-desc { margin: 6px 0 0; color: var(--ink-mute); font-size: var(--fs-sm); }

.models-work {
  display: grid;
  grid-template-columns: minmax(180px, 220px) minmax(0, 1fr) minmax(200px, 240px);
  gap: 12px;
  align-items: start;
}
.models-rail,
.models-main,
.models-side {
  margin: 0;
  padding: 14px 14px 16px;
  min-width: 0;
}

.rail-head { margin-bottom: 10px; }
.rail-label {
  font-size: var(--fs-xs);
  letter-spacing: 0.12em;
  text-transform: uppercase;
  font-weight: 700;
  color: var(--ink-mute);
}
.rail-list {
  list-style: none;
  margin: 0 0 12px;
  padding: 0;
  display: grid;
  gap: 6px;
  max-height: min(52vh, 420px);
  overflow-y: auto;
}
.rail-item {
  position: relative;
  display: grid;
  gap: 2px;
  padding: 10px 12px;
  border: 1px solid var(--rule);
  border-radius: var(--r-sm);
  background: transparent;
  cursor: pointer;
  text-align: left;
}
.rail-item:hover { border-color: color-mix(in srgb, var(--pine) 35%, var(--rule)); }
.rail-item.on {
  border-color: var(--pine);
  background: color-mix(in srgb, var(--moss) 8%, var(--surface));
}
.rail-item-main {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
}
.rail-name {
  font-size: 13px;
  font-weight: 700;
  color: var(--ink);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.rail-badge {
  flex: none;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.04em;
  padding: 1px 6px;
  border-radius: 99px;
  background: color-mix(in srgb, var(--moss) 18%, transparent);
  color: var(--pine);
}
.rail-sub {
  font-size: 11px;
  color: var(--ink-mute);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.rail-dot {
  position: absolute;
  top: 10px;
  right: 10px;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--clay);
}
.rail-empty { margin: 0 0 12px; }
.rail-add { width: 100%; }

.main-head { margin-bottom: 14px; }
.main-head h3 {
  margin: 0;
  font-family: var(--font-serif);
  font-size: var(--fs-h2);
  color: var(--ink);
}
.main-head .meta { margin: 4px 0 0; }
.main-empty {
  display: grid;
  gap: 10px;
  place-items: start;
  padding: 28px 8px;
}
.slot-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}
.slot-card {
  padding: 12px 14px;
  border: 1px solid var(--rule);
  border-radius: var(--r-sm);
  background: color-mix(in srgb, var(--wash) 55%, var(--surface));
  display: grid;
  gap: 6px;
  min-width: 0;
}
.slot-card.warn {
  border-color: color-mix(in srgb, var(--clay) 35%, var(--rule));
  background: color-mix(in srgb, var(--clay) 8%, var(--surface));
}
.slot-k {
  font-size: var(--fs-xs);
  letter-spacing: 0.1em;
  text-transform: uppercase;
  font-weight: 700;
  color: var(--ink-mute);
}
.slot-v {
  font-size: 14px;
  font-weight: 650;
  color: var(--pine);
  word-break: break-all;
  line-height: 1.35;
}
.slot-card.warn .slot-v { color: var(--clay); }
.slot-meta { font-size: 12px; color: var(--ink-mute); }

.side-block { margin-bottom: 16px; }
.side-active-name {
  font-family: var(--font-serif);
  font-size: 18px;
  font-weight: 700;
  color: var(--pine);
  word-break: break-word;
  line-height: 1.3;
}
.side-hint { margin: 6px 0 0; }
.side-dims {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}
.side-dim strong {
  display: block;
  font-size: 20px;
  color: var(--pine);
  margin-top: 2px;
}
.ready-list {
  list-style: none;
  margin: 8px 0 0;
  padding: 0;
  display: grid;
  gap: 8px;
}
.ready-list li {
  display: grid;
  gap: 2px;
  padding: 8px 10px;
  border-radius: var(--r-sm);
  background: var(--wash);
}
.ready-list li.warn {
  background: color-mix(in srgb, var(--clay) 10%, var(--paper));
}
.ready-k {
  font-size: 10px;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  font-weight: 700;
  color: var(--ink-mute);
}
.ready-v {
  font-size: 12px;
  color: var(--ink);
  word-break: break-all;
}
.ready-list li.warn .ready-v { color: var(--clay); font-weight: 650; }
.side-actions {
  display: grid;
  gap: 8px;
  margin-top: 4px;
}
.side-actions button { width: 100%; }

@media (max-width: 1100px) {
  .models-work {
    grid-template-columns: 1fr;
  }
  .rail-list {
    display: flex;
    flex-wrap: nowrap;
    gap: 8px;
    max-height: none;
    overflow-x: auto;
    padding-bottom: 4px;
  }
  .rail-item {
    flex: 0 0 auto;
    min-width: 140px;
    max-width: 200px;
  }
  .rail-add { width: auto; }
  .models-side { order: 3; }
}

@media (max-width: 700px) {
  .slot-grid { grid-template-columns: 1fr; }
  .side-dims { grid-template-columns: 1fr; }
}
.field-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 16px; margin: 16px 0; }
.field {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
}
.field label {
  font-size: var(--fs-xs);
  color: var(--ink-mute);
  letter-spacing: 0.08em;
  text-transform: uppercase;
  font-weight: 700;
}
.field input[type="text"],
.field input[type="email"],
.field input[type="password"],
.field input[type="number"] {
  width: 100%;
  box-sizing: border-box;
}
.check {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: var(--fs-sm);
  color: var(--ink-soft);
  cursor: pointer;
}
.mail-status {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 6px 12px;
  font-size: var(--fs-sm);
  padding: 10px 12px;
  border-radius: var(--r-sm);
  margin: 12px 0 4px;
}
.mail-status strong { font-weight: 700; }
.mail-status.ok {
  color: var(--moss);
  background: color-mix(in srgb, var(--lime) 22%, transparent);
}
.mail-status.bad {
  color: var(--clay);
  background: color-mix(in srgb, var(--clay) 10%, var(--paper));
}
.smtp-fields {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px 16px;
  margin: 16px 0 12px;
  align-items: stretch;
}
.smtp-fields > .field {
  /* 同行两列等高，说明区撑开，输入框底对齐 */
  height: 100%;
}
.smtp-fields > .field .field-help {
  flex: 1 1 auto;
  min-height: 2.9em;
}
.smtp-fields .smtp-from { grid-column: 1 / -1; }
.smtp-toggles {
  display: flex;
  flex-wrap: wrap;
  gap: 12px 20px;
  margin: 0 0 14px;
}
.field-help {
  margin: 0;
  font-size: var(--fs-xs);
  color: var(--ink-mute);
  line-height: 1.45;
  font-weight: 400;
  letter-spacing: 0;
  text-transform: none;
  /* 预留约两行，避免与邻列说明长短差导致输入框错位 */
  min-height: 2.9em;
}
.field-help code {
  font-family: var(--font-mono);
  font-size: 0.95em;
  background: var(--wash);
  padding: 0 4px;
  border-radius: 3px;
}
.smtp-actions-block {
  margin-top: 8px;
  padding-top: 16px;
  border-top: 1px dashed var(--rule, #d8d2c8);
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.smtp-actions { margin: 0; }
.smtp-test-row {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  gap: 12px;
}
.smtp-test-input { flex: 1 1 240px; min-width: 0; }
.smtp-test-row button { flex: none; }
.smtp-test-hint { margin: 0; color: var(--ink-mute); }
.compact-empty { margin-top: 12px; padding: 20px; }
@media (max-width: 700px) {
  .smtp-fields { grid-template-columns: 1fr; }
  .smtp-fields .smtp-from { grid-column: auto; }
}
.hint { margin: 0 0 12px; }
.crawler-status {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 8px 14px;
  margin: 12px 0 8px;
  padding: 10px 12px;
  border-radius: var(--r-sm);
  background: color-mix(in srgb, var(--lime) 18%, transparent);
  color: var(--pine);
  font-size: var(--fs-sm);
}
.crawler-status.warn {
  background: color-mix(in srgb, var(--brass, #9a6b2f) 12%, var(--paper));
  color: var(--ink);
}
.crawler-status .dirty-tag {
  font-size: var(--fs-xs);
  font-weight: 700;
  color: var(--clay);
}
.cfg-table { width: 100%; border-collapse: collapse; }
.cfg-table th, .cfg-table td { text-align: left; padding: 10px 8px; border-bottom: 1px solid var(--line, #e6e0d6); vertical-align: middle; }
.cfg-table .num { width: 72px; }
.cfg-table .wide { width: 100%; min-width: 140px; }
.col-hint {
  font-size: 10px;
  font-weight: 500;
  color: var(--ink-mute);
  letter-spacing: 0;
  text-transform: none;
  margin-top: 2px;
}
.crawler-table tbody tr.is-off {
  opacity: 0.62;
  box-shadow: inset 3px 0 0 var(--ink-mute);
}
.crawler-table tbody tr.is-dirty {
  background: color-mix(in srgb, var(--brass, #9a6b2f) 8%, transparent);
}
.enable-cell {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  font-size: var(--fs-xs);
}
.enable-cell .on { color: var(--moss); font-weight: 650; }
.enable-cell .off { color: var(--ink-mute); }
.crawler-save-cell {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}
.dirty-dot {
  font-size: 10px;
  font-weight: 700;
  color: var(--clay);
}
.actions { white-space: nowrap; display: flex; gap: 8px; }
.kw-toolbar, .kw-new, .kw-pager { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; margin: 12px 0; }
.kw-toolbar .search { flex: 1; min-width: 160px; }
.kw-new input { flex: 1; min-width: 140px; }

.crawl-status {
  display: flex;
  flex-wrap: wrap;
  gap: 12px 16px;
  align-items: center;
  margin: 8px 0 14px;
}
.seg { display: flex; flex-wrap: wrap; gap: 8px; }
.seg-btn {
  background: transparent;
  color: var(--pine);
  padding: 8px 14px;
}
.seg-btn.on { background: var(--pine); color: var(--paper); }
.source-chip-row { display: flex; flex-wrap: wrap; gap: 8px; }
.source-chip {
  background: var(--paper);
  color: var(--ink);
  border: 1.5px solid var(--line);
  border-radius: var(--r-sm);
  padding: 6px 12px;
  font-size: var(--fs-sm);
  cursor: pointer;
}
.source-chip.on {
  border-color: var(--pine);
  background: color-mix(in srgb, var(--pine) 10%, var(--paper));
  color: var(--pine);
  font-weight: 650;
}
.source-chip:disabled { opacity: 0.75; cursor: not-allowed; }
.pipe-schedule-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.pipe-actions { margin: 0; flex-wrap: wrap; }
</style>
