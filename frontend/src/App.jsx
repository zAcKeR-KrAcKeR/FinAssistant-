import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Sidebar from './components/Layout/Sidebar'
import ExecutiveOverview from './pages/ExecutiveOverview'
import RiskAnalysis from './pages/RiskAnalysis'
import CustomerSegmentation from './pages/CustomerSegmentation'
import DataQuality from './pages/DataQuality'
import Assistant from './pages/Assistant'
import WhatIfPage from './pages/WhatIfPage'

export default function App() {
  return (
    <BrowserRouter>
      <div className="app-shell">
        <Sidebar />
        <Routes>
          <Route path="/"          element={<ExecutiveOverview />} />
          <Route path="/risk"      element={<RiskAnalysis />} />
          <Route path="/segments"  element={<CustomerSegmentation />} />
          <Route path="/quality"   element={<DataQuality />} />
          <Route path="/assistant" element={<Assistant />} />
          <Route path="/whatif"    element={<WhatIfPage />} />
        </Routes>
      </div>
    </BrowserRouter>
  )
}
