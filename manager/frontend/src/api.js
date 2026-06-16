// Web/Tauri-dev: BASE='' -> fetch('/api/..') đi qua Vite proxy (:5173 -> :8000).
// Tauri BUILD (app đóng gói, không có proxy): đặt VITE_API_BASE=<url server> lúc build
// (vd VITE_API_BASE=http://localhost:8000 npm run build, hoặc URL server thật khi prod).
export const API_BASE = import.meta.env.VITE_API_BASE || ''

export async function api(path, opts) {
  const r = await fetch(API_BASE + '/api' + path, opts)
  if (!r.ok) throw new Error((await r.text()) || r.statusText)
  return r.json()
}
