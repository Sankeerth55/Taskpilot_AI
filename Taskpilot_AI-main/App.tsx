import React, { useState } from 'react';
import LandingPage from './components/LandingPage';
import ChatInterface from './components/ChatInterface';
import { AppView } from './types';

const App: React.FC = () => {
  const [currentView, setCurrentView] = useState<AppView>(AppView.Landing);

  return (
    <>
      {currentView === AppView.Landing ? (
        <LandingPage onStart={() => setCurrentView(AppView.Chat)} />
      ) : (
        <ChatInterface onBack={() => setCurrentView(AppView.Landing)} />
      )}
    </>
  );
};

export default App;