import { useEffect } from 'react'
import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { HomePage } from '@/HomePage'
import { TodoPage } from '@/components/TodoPage'

function CrawlableHomeCopy() {
  const { pathname } = useLocation()
  useEffect(() => {
    const copy = document.getElementById('about-lernyra')
    if (copy) copy.hidden = pathname !== '/'
  }, [pathname])
  return null
}

export default function App() {
  return (
    <>
      <CrawlableHomeCopy />
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/learning-list" element={<TodoPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </>
  )
}
