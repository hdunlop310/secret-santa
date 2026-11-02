import { Navigate, Route, Routes } from 'react-router-dom'
import { NotFoundPage } from './components/States'
import { CreateGroupPage } from './pages/CreateGroup'
import { DashboardPage } from './pages/Dashboard'
import { ExclusionsPage } from './pages/Exclusions'
import { GifteePage } from './pages/Giftee'
import { CheckEmailPage, JoinPage } from './pages/Join'
import { WishListPage } from './pages/WishList'

export function App() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/new" replace />} />
      <Route path="/new" element={<CreateGroupPage />} />
      <Route path="/g/:adminToken" element={<DashboardPage />} />
      <Route path="/g/:adminToken/exclusions" element={<ExclusionsPage />} />
      <Route path="/join/:inviteToken" element={<JoinPage />} />
      <Route path="/join/:inviteToken/check-email" element={<CheckEmailPage />} />
      <Route path="/p/:participantToken" element={<WishListPage />} />
      <Route path="/p/:participantToken/giftee" element={<GifteePage />} />
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  )
}
