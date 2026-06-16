import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api.js'

const TYPE = { ban_an: 'Bản án', quyet_dinh: 'Quyết định' }

// Trang tìm bản án tương tự cho THẨM PHÁN (test). Dev: backend tự embed query
// (server lazy-load model). Production = app Tauri embed tại máy rồi gửi vector.
export default function Search() {
  const [query, setQuery] = useState('')
  const [docType, setDocType] = useState('')
  const [top, setTop] = useState(20)
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)

  const run = async (e) => {
    e?.preventDefault()
    if (!query.trim()) return
    setLoading(true); setData(null)
    const body = { query, top: Number(top) }
    if (docType) body.doc_type = docType
    try {
      const r = await api('/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      setData(r)
    } catch (err) {
      setData({ error: String(err) })
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="search-page">
      <p className="muted">Dán <b>tình tiết vụ án</b> đang xử (hoặc mô tả tranh chấp) → tìm các bản án/quyết định tương tự đã xử để tham khảo.</p>

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

      {loading && <p className="muted">Đang embed query + tìm kiếm… (lần đầu server nạp model ~30–40s)</p>}
      {data?.error && <p className="err">{data.error}</p>}

      {data?.results && (
        <div className="results">
          <p className="muted">{data.count} kết quả gần nhất (theo độ tương đồng ngữ nghĩa):</p>
          {data.results.map((r, i) => (
            <Link key={r.doc_id} to={'/docs/' + r.doc_id} className="result">
              <div className="result-head">
                <span className="rank">#{i + 1}</span>
                <span className="score" title="độ tương đồng cosine">{(r.score * 100).toFixed(1)}%</span>
                <span className={'badge t-' + r.doc_type}>{TYPE[r.doc_type] || r.doc_type}</span>
                <span className="fname">{r.filename}</span>
              </div>
              <p className="snippet">{r.snippet}…</p>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}
