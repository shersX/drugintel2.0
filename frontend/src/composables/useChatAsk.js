import { api } from '../api'

export function chatWsUrl() {
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${proto}//${window.location.host}/ws/chat`
}

/**
 * 共享 WebSocket / REST 问答协议。
 * @param {{
 *   messages: import('vue').Ref,
 *   conversationId: import('vue').Ref,
 *   loadingStage: import('vue').Ref,
 *   activeSearchQuery: import('vue').Ref,
 *   getNewsId?: () => (number|null|undefined),
 * }} opts
 */
export function useChatAsk(opts) {
  function resolveNewsId() {
    const id = opts.getNewsId?.()
    if (id == null || id === '') return null
    const n = Number(id)
    return Number.isFinite(n) ? n : null
  }

  function askViaRest(q) {
    const body = {
      query: q,
      conversation_id: opts.conversationId.value || null,
    }
    const newsId = resolveNewsId()
    if (newsId != null) body.news_id = newsId
    return api.ask(body)
  }

  function askViaWs(q) {
    return new Promise((resolve, reject) => {
      let settled = false
      let assistantIndex = -1
      let pendingSources = []
      const originalQuery = q
      const ws = new WebSocket(chatWsUrl())

      const fail = (err) => {
        if (settled) return
        settled = true
        try { ws.close() } catch { /* ignore */ }
        reject(err instanceof Error ? err : new Error(String(err || 'WebSocket 失败')))
      }

      const finish = (payload) => {
        if (settled) return
        settled = true
        try { ws.close() } catch { /* ignore */ }
        resolve(payload)
      }

      ws.onopen = () => {
        const payload = {
          query: q,
          conversation_id: opts.conversationId.value || null,
        }
        const newsId = resolveNewsId()
        if (newsId != null) payload.news_id = newsId
        ws.send(JSON.stringify(payload))
      }

      ws.onerror = () => fail(new Error('无法建立问答连接'))
      ws.onclose = () => {
        if (!settled) fail(new Error('问答连接已断开'))
      }

      ws.onmessage = (ev) => {
        let event
        try {
          event = JSON.parse(ev.data)
        } catch {
          fail(new Error('服务端返回无效数据'))
          return
        }
        const type = event.type
        if (type === 'error') {
          fail(new Error(event.message || '问答失败'))
          return
        }
        if (type === 'stage') {
          opts.loadingStage.value = event.stage || ''
          if (event.search_query && event.search_query !== originalQuery) {
            opts.activeSearchQuery.value = event.search_query
          }
          return
        }
        if (type === 'clarify') {
          opts.loadingStage.value = 'clarify'
          if (event.search_query && event.search_query !== originalQuery) {
            opts.activeSearchQuery.value = event.search_query
          }
          const cid = event.conversation_id || event.session_id || opts.conversationId.value
          if (cid) opts.conversationId.value = cid
          opts.messages.value.push({
            role: 'assistant',
            content: event.question || '请补充更多信息。',
            sources: [],
            clarify: true,
          })
          finish({
            conversation_id: cid,
            clarify: true,
            answer: event.question,
          })
          return
        }
        if (type === 'meta') {
          const cid = event.conversation_id || event.session_id || opts.conversationId.value
          if (cid) opts.conversationId.value = cid
          if (event.search_query && event.search_query !== originalQuery) {
            opts.activeSearchQuery.value = event.search_query
          }
          opts.loadingStage.value = 'generate'
          pendingSources = event.sources || []
          return
        }
        if (type === 'token') {
          if (assistantIndex < 0) {
            opts.messages.value.push({ role: 'assistant', content: '', sources: [] })
            assistantIndex = opts.messages.value.length - 1
          }
          const row = opts.messages.value[assistantIndex]
          if (row) row.content = (row.content || '') + (event.content || '')
          return
        }
        if (type === 'done') {
          const cid = event.conversation_id || event.session_id || opts.conversationId.value
          if (cid) opts.conversationId.value = cid
          if (event.clarify) {
            finish({ conversation_id: cid, clarify: true, answer: event.answer })
            return
          }
          if (assistantIndex >= 0) {
            const row = opts.messages.value[assistantIndex]
            if (row) {
              if (event.answer) row.content = event.answer
              const finalSources = event.sources?.length ? event.sources : pendingSources
              row.sources = finalSources || []
            }
          }
          finish({
            conversation_id: cid,
            clarify: false,
            answer: event.answer,
          })
        }
      }
    })
  }

  return { askViaWs, askViaRest }
}
