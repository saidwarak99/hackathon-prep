import React, { useState } from 'react';
import { DatasetProvider, useDataset } from './context/DatasetContext';
import { Sidebar, PageId } from './components/layout/Sidebar';
import { Header } from './components/layout/Header';
import { OverviewPage } from './pages/OverviewPage';
import { AIWorkspacePage } from './pages/AIWorkspacePage';
import { SalesPage } from './pages/SalesPage';
import { MenuPage } from './pages/MenuPage';
import { FeedbackPage } from './pages/FeedbackPage';
import { InventoryPage } from './pages/InventoryPage';
import { RecommendationsPage } from './pages/RecommendationsPage';
import { KnowledgePage } from './pages/KnowledgePage';
import { DatasetPage } from './pages/DatasetPage';
import { WelcomePage } from './pages/WelcomePage';

function AppContent() {
  const { isDemoAuthenticated } = useDataset();
  const [activePage, setActivePage] = useState<PageId>('overview');

  if (!isDemoAuthenticated) {
    return <WelcomePage />;
  }

  const renderPage = () => {
    switch (activePage) {
      case 'overview':
        return <OverviewPage onNavigate={(p) => setActivePage(p)} />;
      case 'workspace':
        return <AIWorkspacePage />;
      case 'sales':
        return <SalesPage />;
      case 'menu':
        return <MenuPage />;
      case 'feedback':
        return <FeedbackPage />;
      case 'inventory':
        return <InventoryPage />;
      case 'recommendations':
        return <RecommendationsPage />;
      case 'knowledge':
        return <KnowledgePage />;
      case 'datasets':
        return <DatasetPage />;
      default:
        return <OverviewPage onNavigate={(p) => setActivePage(p)} />;
    }
  };

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-sandalwood text-ink font-sans">
      {/* Navigation Sidebar */}
      <Sidebar activePage={activePage} onSelectPage={setActivePage} />

      {/* Content Column */}
      <div className="flex-1 flex flex-col h-full min-w-0 overflow-hidden bg-sandalwood/40">
        {/* Top Header */}
        <Header activePage={activePage} />

        {/* Main Content Area */}
        <main className="flex-1 overflow-y-auto p-8 min-w-0">
          <div className="max-w-7xl mx-auto pb-12">
            {renderPage()}
          </div>
        </main>
      </div>
    </div>
  );
}

export function App() {
  return (
    <DatasetProvider>
      <AppContent />
    </DatasetProvider>
  );
}

export default App;
