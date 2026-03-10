/**
 * AppShell — top-level layout: header + TabBar + page content + CheckpointModal overlay.
 */
import { useStore } from '@/store'
import TabBar from '@/components/TabBar'
import IntakePage from '@/pages/IntakePage'
import GalleryPage from '@/pages/GalleryPage'
import ExportPage from '@/pages/ExportPage'
import CheckpointModal from '@/components/CheckpointModal'

export default function AppShell() {
  const activeTab = useStore((s) => s.activeTab)
  const checkpointModalOpen = useStore((s) => s.checkpointModalOpen)

  return (
    <div className="min-h-screen flex flex-col">
      {/* ── Header ── */}
      <header className="bg-white border-b border-gray-200 px-6 py-3 flex items-center gap-3 shrink-0">
        <div className="flex items-center gap-2">
          <span className="text-2xl">🎯</span>
          <span className="font-bold text-xl text-gray-900">
            {import.meta.env.VITE_APP_NAME || 'DeckForge AI'}
          </span>
        </div>
        <span className="text-gray-400 text-sm hidden sm:inline">
          AI-powered executive presentation builder
        </span>
      </header>

      {/* ── Tab bar ── */}
      <TabBar />

      {/* ── Page content ── */}
      <main className="flex-1 overflow-auto">
        {activeTab === 'intake' && <IntakePage />}
        {activeTab === 'gallery' && <GalleryPage />}
        {activeTab === 'export' && <ExportPage />}
      </main>

      {/* ── HITL Checkpoint Modal overlay ── */}
      {checkpointModalOpen && <CheckpointModal />}
    </div>
  )
}
