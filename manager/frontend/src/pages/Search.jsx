import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api.js'

const TYPE = { ban_an: 'Bản án', quyet_dinh: 'Quyết định' }
const N_CTX = 6   // số nguồn đưa cho LLM tóm tắt

// Trang tìm + tóm tắt án lệ cho THẨM PHÁN.
// - Search: server (dense) trả {chunk + tên file}, KHÔNG trả full doc.
// - Tóm tắt: LLM sinh câu trả lời tự nhiên (dev: backend gọi ollama local;
//   production: app Tauri gọi ollama TẠI MÁY user). Ràng prompt chỉ-dựa-trích-dẫn.
// - Bấm tên file → mở full nội dung (DocDetail).
export default function Search() {
  const [query, setQuery] = useState('')
  const [docType, setDocType] = useState('')
  const [top, setTop] = useState(20)
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [answer, setAnswer] = useState('')
  const [generating, setGenerating] = useState(false)

  const streamAnswer = async (q, results) => {
    setAnswer(''); setGenerating(true)
    try {
      const contexts = results.slice(0, N_CTX).map((r, i) => ({ n: i + 1, name: r.filename, chunk: r.chunk }))
      const res = await fetch('/api/search/answer', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: q, contexts }),
      })
      if (!res.ok || !res.body) { setAnswer(`(không sinh được tóm tắt — ${res.status})`); return }
      const reader = res.body.getReader(); const dec = new TextDecoder()
      let acc = ''
      for (;;) {
        const { done, value } = await reader.read()
        if (done) break
        acc += dec.decode(value, { stream: true }); setAnswer(acc)
      }
    } catch (e) {
      setAnswer('(lỗi sinh tóm tắt: ' + e + ')')
    } finally { setGenerating(false) }
  }

  const run = async (e) => {
    e?.preventDefault()
    if (!query.trim()) return
    setLoading(true); setData(null); setAnswer('')
    const body = { query, top: Number(top) }
    if (docType) body.doc_type = docType
    try {
      const r = await api('/search', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      setData(r)
      if (r.results?.length) streamAnswer(query, r.results)
    } catch (err) {
      setData({ error: String(err) })
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="search-page">
      <p className="muted">Dán <b>tình tiết vụ án</b> đang xử → tìm bản án/quyết định tương tự + tóm tắt AI để tham khảo.</p>

      <form onSubmit={run} className="search-form">
        <textarea rows={5} value={query} onChange={e => setQuery(e.target.value)}
          placeholder="VD: Tranh chấp hợp đồng tín dụng. Ngân hàng khởi kiện đòi nợ gốc và lãi quá hạn, yêu cầu xử lý tài sản thế chấp là quyền sử dụng đất của hộ gia đình…" />
        <div className="search-controls">
          <select value={docType} onChange={e => setDocType(e.target.value)}>
            <option value="">— mọi loại —</option>
            <option value="ban_an">Bản án</option>
            <option value="quyet_dinh">Quyết định</option>
          </select>
          <select value={top} onChange={e => setTop(e.target.value)}>
            <option value={10}>10 kết quả</option>
            <option value={20}>20 kết quả</option>
            <option value={50}>50 kết quả</option>
          </select>
          <button type="submit" className="primary" disabled={loading || !query.trim()}>
            {loading ? 'Đang tìm…' : '🔍 Tìm vụ tương tự'}
          </button>
        </div>
      </form>

      {loading && <p className="muted">Đang tìm kiếm… (lần đầu server nạp model ~30–40s)</p>}
      {data?.error && <p className="err">{data.error}</p>}

      {(answer || generating) && (
        <div className="answer">
          <div className="answer-head">✨ Tóm tắt AI {generating && <span className="muted">— đang viết…</span>}</div>
          <div className="answer-body">{answer || '…'}</div>
          <div className="answer-disclaimer">⚠️ Tóm tắt do AI sinh từ các trích đoạn bên dưới — có thể sai/thiếu. <b>Phải bấm vào bản án gốc để xác minh</b> trước khi dùng.</div>
        </div>
      )}

      {data?.results && (
        <div className="results">
          <p className="muted">{data.count} bản án/quyết định gần nhất — nguồn cho tóm tắt: [1]–[{Math.min(N_CTX, data.count)}]:</p>
          {data.results.map((r, i) => (
            <Link key={r.doc_id} to={'/docs/' + r.doc_id} className="result">
              <div className="result-head">
                <span className="rank">{i < N_CTX ? `[${i + 1}]` : `#${i + 1}`}</span>
                <span className="score" title="độ tương đồng cosine">{(r.score * 100).toFixed(1)}%</span>
                <span className={'badge t-' + r.doc_type}>{TYPE[r.doc_type] || r.doc_type}</span>
                <span className="fname">{r.filename}</span>
              </div>
              <p className="snippet">{r.chunk.slice(0, 300)}…</p>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}
