import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api.js'

const TYPE = { ban_an: 'Bản án', quyet_dinh: 'Quyết định' }
const N_CTX = 6                       // số nguồn đưa cho LLM
const GMODEL = 'gemini-2.5-flash'

// Tóm tắt do CHÍNH MÁY USER gọi Gemini bằng key riêng của họ (BYOK, lưu localStorage).
// Không qua server mình → server chỉ dense-retrieve, không giữ key, không tốn quota.
// Luật nhạy cảm → ràng prompt chỉ-dựa-trích-dẫn + bắt buộc dẫn nguồn + cấm bịa.
const SYSTEM = `Bạn là trợ lý tra cứu án lệ cho thẩm phán Việt Nam. Người dùng đưa TÌNH TIẾT vụ đang xử và một số ĐOẠN TRÍCH từ các bản án/quyết định tương tự (đánh số [1], [2]...).

Nhiệm vụ: tóm tắt NGẮN GỌN (tiếng Việt) các vụ tìm được liên quan thế nào tới vụ đang xử — điểm CHUNG và KHÁC BIỆT về quan hệ pháp luật tranh chấp và hướng giải quyết — để thẩm phán THAM KHẢO.

QUY TẮC BẮT BUỘC (luật là lĩnh vực nhạy cảm):
1. CHỈ dùng thông tin có trong các đoạn trích. TUYỆT ĐỐI KHÔNG bịa tình tiết, số liệu, tên, điều luật, kết quả xử không có trong trích dẫn.
2. Mỗi nhận định phải DẪN NGUỒN [số].
3. Nếu trích dẫn KHÔNG đủ để kết luận → nói rõ "cần đọc bản án đầy đủ", đừng đoán.
4. KHÔNG phán quyết / khuyên pháp lý. Chỉ là tóm tắt tham khảo; thẩm phán phải tự đọc bản án gốc.`

export default function Search() {
  const [query, setQuery] = useState('')
  const [docType, setDocType] = useState('')
  const [top, setTop] = useState(20)
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [answer, setAnswer] = useState('')
  const [generating, setGenerating] = useState(false)
  const [gkey, setGkey] = useState(() => localStorage.getItem('gemini_key') || '')
  const [keyInput, setKeyInput] = useState('')
  const [editKey, setEditKey] = useState(false)

  const saveKey = () => {
    const k = keyInput.trim()
    if (!k) return
    localStorage.setItem('gemini_key', k); setGkey(k); setKeyInput(''); setEditKey(false)
  }

  const streamAnswer = async (q, results) => {
    if (!gkey) { setAnswer('⚠️ Chưa có Gemini API key — nhập ở trên để bật tóm tắt AI.'); return }
    setAnswer(''); setGenerating(true)
    try {
      const ctx = results.slice(0, N_CTX)
        .map((r, i) => `[${i + 1}] ${r.filename}:\n${r.chunk}`).join('\n\n')
      const body = {
        systemInstruction: { parts: [{ text: SYSTEM }] },
        contents: [{ role: 'user', parts: [{ text:
          `TÌNH TIẾT VỤ ĐANG XỬ:\n${q}\n\nCÁC BẢN ÁN/QUYẾT ĐỊNH TƯƠNG TỰ:\n${ctx}` }] }],
      }
      const res = await fetch(
        `https://generativelanguage.googleapis.com/v1beta/models/${GMODEL}:streamGenerateContent?alt=sse&key=${gkey}`,
        { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
      if (!res.ok || !res.body) {
        setAnswer(`(Gemini lỗi ${res.status}: ${(await res.text()).slice(0, 200)})`); return
      }
      const reader = res.body.getReader(); const dec = new TextDecoder()
      let buf = '', acc = ''
      for (;;) {
        const { done, value } = await reader.read()
        if (done) break
        buf += dec.decode(value, { stream: true })
        const lines = buf.split('\n'); buf = lines.pop()
        for (const line of lines) {
          const s = line.trim()
          if (!s.startsWith('data:')) continue
          try {
            const t = JSON.parse(s.slice(5).trim())?.candidates?.[0]?.content?.parts?.[0]?.text
            if (t) { acc += t; setAnswer(acc) }
          } catch { /* dòng SSE chưa trọn */ }
        }
      }
    } catch (e) {
      setAnswer('(lỗi gọi Gemini: ' + e + ')')
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
    } finally { setLoading(false) }
  }

  return (
    <div className="search-page">
      <div className="keybar">
        {gkey && !editKey ? (
          <span className="muted">🔑 Đã lưu Gemini key (trên máy bạn) ·
            <a onClick={() => setEditKey(true)}> đổi</a></span>
        ) : (
          <>
            <input type="password" placeholder="Dán Gemini API key…" value={keyInput}
                   onChange={e => setKeyInput(e.target.value)} />
            <button onClick={saveKey} disabled={!keyInput.trim()}>Lưu</button>
            <span className="muted">key chỉ lưu trên máy bạn ·
              <a href="https://aistudio.google.com/apikey" target="_blank" rel="noreferrer"> lấy key free</a></span>
          </>
        )}
      </div>

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
