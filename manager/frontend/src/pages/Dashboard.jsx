import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api.js'

export default function Dashboard() {
  const [s, setS] = useState(null)
  useEffect(() => { api('/stats').then(setS).catch(e => setS({ error: String(e) })) }, [])
  if (!s) return <p className="muted">Đang tải…</p>
  if (s.error) return <p className="err">{s.error}</p>
  const pct = n => (n * 100 / s.total).toFixed(1)
  return (
    <div>
      <div className="cards">
        <div className="card total"><b>{s.total.toLocaleString()}</b><span>tổng tài liệu</span></div>
        {s.buckets.map(b => (
          <Link key={b.bucket} className={'card b-' + b.bucket} to={'/docs?bucket=' + b.bucket}>
            <b>{b.n.toLocaleString()}</b><span>{b.bucket} · {pct(b.n)}%</span>
          </Link>
        ))}
      </div>

      <h3>Nhánh trích xuất</h3>
      <Bars data={s.routes} field="route" />

      <h3>Lý do cần re-OCR (nhóm reocr)</h3>
      <Bars data={s.reocr_reasons} field="reocr_reason" />
    </div>
  )
}

function Bars({ data, field }) {
  const max = Math.max(...data.map(d => d.n), 1)
  return (
    <div className="bars">
      {data.map(d => (
        <div key={d[field] || '?'} className="bar-row">
          <span className="bar-label">{d[field] || '—'}</span>
          <div className="bar"><div style={{ width: (d.n * 100 / max) + '%' }} /></div>
          <span className="bar-n">{d.n.toLocaleString()}</span>
        </div>
      ))}
    </div>
  )
}
