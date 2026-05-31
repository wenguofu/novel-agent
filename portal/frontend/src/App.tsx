import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { ConfigProvider, theme } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import { Layout } from './components/Layout'
import { Dashboard } from './pages/Dashboard'
import { Writing } from './pages/Writing'
import { Review } from './pages/Review'
import { Characters } from './pages/Characters'
import { Foreshadowing } from './pages/Foreshadowing'
import { Chapters } from './pages/Chapters'
import { Outlines } from './pages/Outlines'
import { Workflow } from './pages/Workflow'
import { NewBook } from './pages/NewBook'
import { NovelsPage } from './pages/NovelsPage'
import { SearchPage } from './pages/SearchPage'
import { ConfigPage } from './pages/ConfigPage'
import { QualityPage } from './pages/QualityPage'
import { WorldBuilding } from './pages/WorldBuilding'
import { PlotArcs } from './pages/PlotArcs'
import { PacingControl } from './pages/PacingControl'
import { RevelationSchedule } from './pages/RevelationSchedule'
import { InitWizard } from './pages/InitWizard'
import { UsagePage } from './pages/UsagePage'
import { Onboarding } from './pages/Onboarding'
import { ErrorBoundary } from './components/ErrorBoundary'
import { Settings } from './pages/Placeholders'

function App() {

  return (
    <ConfigProvider
      locale={zhCN}
      theme={{
        algorithm: theme.defaultAlgorithm,
        token: { colorPrimary: '#1677ff' },
      }}
    >
      <BrowserRouter>
        <Layout>
          <ErrorBoundary>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/novels" element={<NovelsPage />} />
            <Route path="/novels/new" element={<NewBook />} />
            <Route path="/writing" element={<Writing />} />
            <Route path="/chapters" element={<Chapters />} />
            <Route path="/outlines" element={<Outlines />} />
            <Route path="/review" element={<Review />} />
            <Route path="/characters" element={<Characters />} />
            <Route path="/foreshadowing" element={<Foreshadowing />} />
            <Route path="/world" element={<WorldBuilding />} />
            <Route path="/arcs" element={<PlotArcs />} />
            <Route path="/pacing" element={<PacingControl />} />
            <Route path="/revelation" element={<RevelationSchedule />} />
            <Route path="/onboarding" element={<Onboarding />} />
            <Route path="/init" element={<InitWizard />} />
            <Route path="/workflow" element={<Workflow />} />
            <Route path="/quality" element={<QualityPage />} />
            <Route path="/search" element={<SearchPage />} />
            <Route path="/config" element={<ConfigPage />} />
            <Route path="/usage" element={<UsagePage />} />
            <Route path="/settings" element={<Settings />} />
          </Routes>
          </ErrorBoundary>
        </Layout>
      </BrowserRouter>
    </ConfigProvider>
  )
}

export default App
