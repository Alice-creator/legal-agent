// Tô màu full_text: ký tự RÁC (legacy/VNI/PUA/control — đỏ) + TỪ KHOÁ search (vàng).
// "Rác" = ký tự non-ASCII KHÔNG thuộc bộ chữ Việt hợp lệ + control char. Dấu toán/
// đơn vị hợp lệ (× ÷ ½ ² °…) được cho qua để khỏi nhiễu trên bản án tài chính.

const _vn = 'àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ'
const ALLOWED = new Set([
  ..._vn, ..._vn.toUpperCase(),
  ...'–—‒―•·…°×÷½¼¾²³±₫“”‘’«»', ...' ',
])

export function isGarble(ch) {
  const c = ch.charCodeAt(0)
  if (c < 0x20) return ch !== '\n' && ch !== '\t' && ch !== '\r'
  if (c <= 0x7e) return false
  return !ALLOWED.has(ch)
}

export function countGarble(text) {
  let n = 0
  for (const ch of text || '') if (isGarble(ch)) n++
  return n
}

// Trả mảng React node: gộp chữ thường thành 1 đoạn, bọc rác / từ khoá vào <mark>.
export function highlight(text, q) {
  if (!text) return null
  const ranges = []
  if (q && q.trim()) {
    const low = text.toLowerCase(), ql = q.trim().toLowerCase()
    let i = 0
    while ((i = low.indexOf(ql, i)) >= 0) { ranges.push([i, i + ql.length]); i += ql.length }
  }
  let ri = 0
  const inQ = i => {
    while (ri < ranges.length && ranges[ri][1] <= i) ri++
    return ri < ranges.length && i >= ranges[ri][0] && i < ranges[ri][1]
  }
  const out = []
  let buf = '', type = null
  const flush = () => {
    if (!buf) return
    if (type === 'q') out.push(<mark className="hq" key={out.length}>{buf}</mark>)
    else if (type === 'g') out.push(<mark className="hg" key={out.length}>{buf}</mark>)
    else out.push(buf)
    buf = ''
  }
  for (let i = 0; i < text.length; i++) {
    const ch = text[i]
    const t = inQ(i) ? 'q' : isGarble(ch) ? 'g' : 'n'
    if (t !== type) { flush(); type = t }
    buf += ch
  }
  flush()
  return out
}
