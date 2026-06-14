import { Routes, Route, NavLink } from 'react-router-dom'
import Dashboard from './pages/Dashboard.jsx'
import DocList from './pages/DocList.jsx'
import DocDetail from './pages/DocDetail.jsx'

export default function App() {
  return (
    <div className="app">
      <header>
        <h1>⚖️ Quản lý corpus bản án</h1>
        <nav>
          <NavLink to="/" end>Bảng chất lượng</NavLink>
          <NavLink to="/docs">Tài liệu</NavLink>
        </nav>
      </header>
      <main>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/docs" element={<DocList />} />
          <Route path="/docs/:id" element={<DocDetail />} />
        </Routes>
      </main>
    </div>
  )
}
