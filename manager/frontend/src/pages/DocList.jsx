import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api } from '../api.js'

export default function DocList() {
  const [sp, setSp] = useSearchParams()
  const [data, setData] = useState(null)
  const bucket = sp.get('bucket') || ''
  const route = sp.get('route') || ''
  const q = sp.get('q') || ''
  const page = parseInt(sp.get('page') || '1')
  const [qInput, setQInput] = useState(q)
  useEffect(() => { setQInput(q) }, [q])

  useEffect(() => {
    const p = new URLSearchParams()
    if (bucket) p.set('bucket', bucket)
    if (route) p.set('route', route)
    if (q) p.set('q', q)
    p.set('page', page); p.set('page_size', '50')
    setData(null)
    api('/docs?' + p).then(setData).catch(e => setData({ error: String(e) }))
  }, [bucket, route, q, page])

  const upd = (k, v) => {
    const n = new URLSearchParams(sp)
    v ? n.set(k, v) : n.delete(k)
    if (k !== 'page') n.set('page', '1')
    setSp(n)
  }

  if (data?.error) return <p className="err">{data.error}</p>
  const pages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 0

  return (
    <div>
      <div className="filters">
        <form onSubmit={e => { e.preventDefault(); upd('q', qInput) }}>
          <input placeholder="Tìm trong nội dung / tên file…" value={qInput}
                 onChange={e => setQInput(e.target.value)} />
        </form>
        <select value={bucket} onChange={e => upd('bucket', e.target.value)}>
          <option value="">— bucket —</option>
          <option>clean</option><option>minor</option><option>reocr</option>
        </select>
        <select value={route} onChange={e => upd('route', e.target.value)}>
          <option value="">— route —</option>
          <option>clean</option><option>glued</option><option>scanned</option>
        </select>
        {(bucket || route || q) &&
          <button onClick={() => setSp(new URLSearchParams())}>xoá lọc</button>}
      </div>

      {!data ? <p className="muted">Đang tải…</p> : (
        <>
          <p className="muted">{data.total.toLocaleString()} kết quả</p>
          <table>
            <thead><tr>
              <th>Tên file</th><th>route</th><th>bucket</th><th>lý do</th><th>ký tự</th><th>mật độ dấu</th>
            </tr></thead>
            <tbody>
              {data.items.map(d => (
                <tr key={d.id}>
                  <td><Link to={'/docs/' + d.id}>{d.filename}</Link></td>
                  <td>{d.route}</td>
                  <td><span className={'badge b-' + d.bucket}>{d.bucket}</span></td>
                  <td className="muted">{d.reocr_reason || ''}</td>
                  <td>{d.char_count?.toLocaleString()}</td>
                  <td>{d.diacritic_density?.toFixed(3)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="pager">
            <button disabled={page <= 1} onClick={() => upd('page', String(page - 1))}>‹ trước</button>
            <span>{page} / {pages}</span>
            <button disabled={page >= pages} onClick={() => upd('page', String(page + 1))}>sau ›</button>
          </div>
        </>
      )}
    </div>
  )
}
