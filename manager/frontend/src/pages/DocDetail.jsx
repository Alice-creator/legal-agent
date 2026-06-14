import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { api } from '../api.js'

export default function DocDetail() {
  const { id } = useParams()
  const nav = useNavigate()
  const [d, setD] = useState(null)
  const [edit, setEdit] = useState(false)
  const [txt, setTxt] = useState('')
  const [busy, setBusy] = useState(false)

  const load = () => api('/docs/' + id).then(x => { setD(x); setTxt(x.full_text || '') })
  useEffect(() => { setD(null); setEdit(false); load() }, [id])

  if (!d) return <p className="muted">Đang tải…</p>
  if (d.error) return <p className="err">{d.error}</p>

  const save = async () => {
    setBusy(true)
    try {
      await api('/docs/' + id, {
        method: 'PUT', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ full_text: txt }),
      })
      setEdit(false); await load()
    } catch (e) { alert('Lỗi: ' + e) } finally { setBusy(false) }
  }
  const reproc = async () => {
    setBusy(true)
    try {
      const r = await api('/docs/' + id + '/reprocess', { method: 'POST' })
      setD(r); setTxt(r.full_text || '')
      alert('Đã decode lại ' + (r._decoded_lines || 0) + ' dòng ($0)')
    } catch (e) { alert('Lỗi: ' + e) } finally { setBusy(false) }
  }
  const del = async () => {
    if (!confirm('Xoá ' + d.filename + '?')) return
    try { await api('/docs/' + id, { method: 'DELETE' }); nav('/docs') }
    catch (e) { alert('Lỗi: ' + e) }
  }

  return (
    <div>
      <div className="detail-head">
        <button onClick={() => nav(-1)}>← quay lại</button>
        <h2>{d.filename}</h2>
        <span className={'badge b-' + d.bucket}>{d.bucket}{d.reocr_reason ? ' · ' + d.reocr_reason : ''}</span>
      </div>
      <div className="meta">
        route <b>{d.route}</b> · {d.char_count?.toLocaleString()} ký tự ·
        mật độ dấu {d.diacritic_density?.toFixed(3)} · legacy {d.legacy_density?.toFixed(4)}
      </div>
      <div className="actions">
        {!edit
          ? <button onClick={() => setEdit(true)}>✏️ Sửa</button>
          : <>
              <button className="primary" onClick={save} disabled={busy}>💾 Lưu</button>
              <button onClick={() => { setEdit(false); setTxt(d.full_text || '') }}>huỷ</button>
            </>}
        <button onClick={reproc} disabled={busy}>🔄 Decode lại ($0)</button>
        <button className="danger" onClick={del} disabled={busy}>🗑 Xoá</button>
      </div>

      <div className="split">
        <div className="pane">
          <h4>full_text</h4>
          {edit
            ? <textarea value={txt} onChange={e => setTxt(e.target.value)} />
            : <pre>{d.full_text}</pre>}
        </div>
        <div className="pane">
          <h4>PDF gốc (đối chiếu)</h4>
          <iframe title="pdf" src={'/api/docs/' + id + '/pdf'} />
        </div>
      </div>
    </div>
  )
}
