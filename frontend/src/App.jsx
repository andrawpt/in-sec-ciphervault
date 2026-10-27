import { Navigate, Outlet, Route, Routes } from 'react-router-dom'
import Layout from './components/Layout'
import { Spinner } from './components/ui'
import { useAuth } from './context/AuthContext'
import Login from './pages/Login'
import Register from './pages/Register'
import Dashboard from './pages/pelapor/Dashboard'
import NewReport from './pages/pelapor/NewReport'
import Profile from './pages/pelapor/Profile'
import ReportDetail from './pages/pelapor/ReportDetail'
import Verification from './pages/pelapor/Verification'
import AuditLog from './pages/petugas/AuditLog'
import CaseDetail from './pages/petugas/CaseDetail'
import Queue from './pages/petugas/Queue'
import Stats from './pages/petugas/Stats'
import VerifyDetail from './pages/petugas/VerifyDetail'
import VerifyQueue from './pages/petugas/VerifyQueue'

const HOME = { pelapor: '/pelapor', petugas: '/petugas' }

function RequireRole({ role }) {
  const { user, loading } = useAuth()
  if (loading) return <Spinner />
  if (!user) return <Navigate to="/login" replace />
  if (user.role !== role) return <Navigate to={HOME[user.role]} replace />
  return <Outlet />
}

function Home() {
  const { user, loading } = useAuth()
  if (loading) return <Spinner />
  return <Navigate to={user ? HOME[user.role] : '/login'} replace />
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Home />} />
      <Route path="/login" element={<Login />} />
      <Route path="/daftar" element={<Register />} />

      <Route element={<RequireRole role="pelapor" />}>
        <Route element={<Layout />}>
          <Route path="/pelapor" element={<Dashboard />} />
          <Route path="/pelapor/lapor-baru" element={<NewReport />} />
          <Route path="/pelapor/laporan/:id" element={<ReportDetail />} />
          <Route path="/pelapor/profil" element={<Profile />} />
          <Route path="/pelapor/verifikasi" element={<Verification />} />
        </Route>
      </Route>

      <Route element={<RequireRole role="petugas" />}>
        <Route element={<Layout />}>
          <Route path="/petugas" element={<Queue />} />
          <Route path="/petugas/kasus/:id" element={<CaseDetail />} />
          <Route path="/petugas/statistik" element={<Stats />} />
          <Route path="/petugas/audit" element={<AuditLog />} />
          <Route path="/petugas/verifikasi" element={<VerifyQueue />} />
          <Route path="/petugas/verifikasi/:userId" element={<VerifyDetail />} />
        </Route>
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
