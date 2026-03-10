/**
 * TabBar — 3-tab navigation: Intake | Gallery | Export
 */
import { useStore } from '@/store'
import type { Tab } from '@/types'
import clsx from 'clsx'

interface TabConfig {
  id: Tab
  label: string
  icon: string
  disabled?: boolean
}

const TABS: TabConfig[] = [
  { id: 'intake', label: 'Intake', icon: '📋' },
  { id: 'gallery', label: 'Gallery', icon: '🖼️' },
  { id: 'export', label: 'Export', icon: '📤' },
]

export default function TabBar() {
  const { activeTab, setTab, envelope, status } = useStore((s) => ({
    activeTab: s.activeTab,
    setTab: s.setTab,
    envelope: s.envelope,
    status: s.status,
  }))

  const isComplete = status === 'completed' || status === 'complete'

  return (
    <nav
      className="bg-white border-b border-gray-200 px-4"
      aria-label="Main navigation"
      role="tablist"
    >
      <div className="flex gap-0 max-w-screen-xl mx-auto">
        {TABS.map((tab) => {
          const isDisabled =
            (tab.id === 'gallery' && !envelope && !isComplete) ||
            (tab.id === 'export' && !isComplete)

          return (
            <button
              key={tab.id}
              role="tab"
              aria-selected={activeTab === tab.id}
              aria-disabled={isDisabled}
              disabled={isDisabled}
              onClick={() => !isDisabled && setTab(tab.id)}
              className={clsx(
                'flex items-center gap-2 px-5 py-3.5 text-sm font-medium border-b-2 transition-colors',
                activeTab === tab.id
                  ? 'border-brand-600 text-brand-700'
                  : isDisabled
                  ? 'border-transparent text-gray-300 cursor-not-allowed'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300 cursor-pointer',
              )}
            >
              <span aria-hidden="true">{tab.icon}</span>
              {tab.label}
            </button>
          )
        })}
      </div>
    </nav>
  )
}
