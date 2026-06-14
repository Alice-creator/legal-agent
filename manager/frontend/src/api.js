export async function api(path, opts) {
  const r = await fetch('/api' + path, opts)
  if (!r.ok) throw new Error((await r.text()) || r.statusText)
  return r.json()
}
