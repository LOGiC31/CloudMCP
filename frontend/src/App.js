import React, { useState, useEffect } from 'react';
import './styles/App.css';
import ResourceDashboard from './components/ResourceDashboard';
import LLMChat from './components/LLMChat';
import MCPToolsPanel from './components/MCPToolsPanel';
import FailureControls from './components/FailureControls';
import FixHistory from './components/FixHistory';
import ValidationPanel from './components/ValidationPanel';
import Header from './components/Header';
import Tabs from './components/Tabs';

function App() {
  const [resources, setResources] = useState([]);
  const [selectedResource, setSelectedResource] = useState(null);
  const [tools, setTools] = useState([]);
  const [loading, setLoading] = useState(true);
  const [isPolling, setIsPolling] = useState(false);
  const [fixHistoryRefreshKey, setFixHistoryRefreshKey] = useState(0);
  const [activeTab, setActiveTab] = useState('local');
  const [validationState, setValidationState] = useState({
    failureIntroduced: false,
    failureType: null,
    degradedResources: [],
    degradedStateSnapshot: {}, // Store the state when failure was detected
    fixTriggered: false,
    fixCompleted: false,
  });

  useEffect(() => {
    loadData();
    // Auto-refresh every 1 minute (60 seconds), but pause during active polling
    const interval = setInterval(() => {
      if (!isPolling) {
        loadData();
      }
    }, 60000); // 60 seconds = 1 minute
    return () => clearInterval(interval);
  }, [isPolling]); // eslint-disable-line react-hooks/exhaustive-deps

  const loadData = async () => {
    try {
      const { resourceService, toolService } = await import('./services/api');
      const [resourcesRes, toolsRes] = await Promise.all([
        resourceService.getAll(),
        toolService.getAll(),
      ]);
      const newResources = resourcesRes.data;
      setResources(newResources);
      setTools(toolsRes.data || []);
      setLoading(false);
      
      // Update validation state if failure was introduced
      setValidationState(prev => {
        if (prev.failureIntroduced && !prev.fixTriggered) {
          const degraded = newResources.filter(r => r.status === 'DEGRADED' || r.status === 'FAILED');
          return {
            ...prev,
            degradedResources: degraded.map(r => r.name),
          };
        }
        return prev;
      });
      
      // Update validation state if fix was completed
      setValidationState(prev => {
        if (prev.fixTriggered) {
          const allHealthy = newResources.length > 0 && newResources.every(r => r.status === 'HEALTHY');
          return {
            ...prev,
            fixCompleted: allHealthy || prev.fixCompleted,
          };
        }
        return prev;
      });
    } catch (error) {
      console.error('Error loading data:', error);
      setLoading(false);
    }
  };

  const handleResourceSelect = (resource) => {
    // Toggle selection: if clicking the same resource, deselect it
    if (selectedResource?.id === resource.id) {
      setSelectedResource(null);
    } else {
      setSelectedResource(resource);
    }
  };

  const handleFailureIntroduced = async (failureType) => {
    setIsPolling(true);
    
    // Wait for status to update (longer for database connections, Redis needs time to fill memory)
    // Redis needs more time because it has to fill memory to trigger DEGRADED status
    const initialWait = failureType === 'database' ? 10000 : failureType === 'redis' ? 12000 : 10000;
    await new Promise(resolve => setTimeout(resolve, initialWait));
    
    // Smart polling: check status until we see degraded resources or timeout
    let attempts = 0;
    const maxAttempts = 10; // 10 attempts = ~20 seconds max
    const pollInterval = 2000; // Check every 2 seconds
    
    const pollForStatus = async () => {
      attempts++;
      
      // Fetch latest resources directly from API
      const { resourceService } = await import('./services/api');
      try {
        const resourcesRes = await resourceService.getAll();
        const newResources = resourcesRes.data;
        
        // Update state
        setResources(newResources);
        
        const degraded = newResources.filter(r => r.status === 'DEGRADED' || r.status === 'FAILED');
        
        // Check if expected resources are degraded
        const expectedResources = failureType === 'redis' ? ['redis'] :
                                 failureType === 'database' ? ['postgres'] :
                                 ['redis', 'postgres'];
        
        const foundDegraded = degraded.filter(r => {
          const nameLower = r.name.toLowerCase();
          return expectedResources.some(expected => nameLower.includes(expected.toLowerCase()));
        });
        
        if (foundDegraded.length > 0 || attempts >= maxAttempts) {
          // Found degraded resources or timeout - store snapshot of degraded state
          const degradedSnapshot = {};
          newResources.forEach(r => {
            if (r.status === 'DEGRADED' || r.status === 'FAILED') {
              degradedSnapshot[r.name] = r.status;
            }
          });
          
          setValidationState(prev => ({
            ...prev,
            failureIntroduced: true,
            failureType: failureType,
            degradedResources: foundDegraded.map(r => r.name),
            degradedStateSnapshot: degradedSnapshot, // Store snapshot for validation
          }));
          setIsPolling(false);
        } else {
          // Continue polling
          setTimeout(pollForStatus, pollInterval);
        }
      } catch (error) {
        console.error('Error polling for status:', error);
        // Continue polling even on error
        if (attempts < maxAttempts) {
          setTimeout(pollForStatus, pollInterval);
        } else {
          setIsPolling(false);
        }
      }
    };
    
    pollForStatus();
  };

  const handleFixTriggered = async () => {
    setValidationState(prev => ({
      ...prev,
      fixTriggered: true,
    }));
    
    setIsPolling(true);
    
    // Wait a bit for fix to be applied (fix is already complete when this is called)
    await new Promise(resolve => setTimeout(resolve, 3000));
    
    // Check status once - fix should already be complete
    const { resourceService } = await import('./services/api');
    try {
      const resourcesRes = await resourceService.getAll();
      const newResources = resourcesRes.data;
      setResources(newResources);
      
      const allHealthy = newResources.length > 0 && newResources.every(r => r.status === 'HEALTHY');
      
      setValidationState(prev => ({
        ...prev,
        fixCompleted: allHealthy,
        // Clear degraded resources when fix completes successfully
        degradedResources: allHealthy ? [] : prev.degradedResources,
      }));
    } catch (error) {
      console.error('Error checking fix status:', error);
    } finally {
      setIsPolling(false);
    }
  };
  
  const handleResetValidation = () => {
    setValidationState({
      failureIntroduced: false,
      failureType: null,
      degradedResources: [],
      degradedStateSnapshot: {},
      fixTriggered: false,
      fixCompleted: false,
    });
  };

  const handleClearAll = async () => {
    try {
      // Clear fix history from backend
      const { fixService } = await import('./services/api');
      await fixService.deleteAll();
      
      // Reset validation state
      handleResetValidation();
      
      // Refresh fix history by incrementing refresh key
      setFixHistoryRefreshKey(prev => prev + 1);
      
      // Refresh data
      await loadData();
      
      // Show success message (you could add a toast notification here)
      console.log('Fix history and validation cleared successfully');
    } catch (error) {
      console.error('Error clearing fix history:', error);
      alert('Failed to clear fix history. Please try again.');
    }
  };

  if (loading) {
    return (
      <div className="app-loading">
        <div className="loading-spinner"></div>
        <p>Loading infrastructure status...</p>
      </div>
    );
  }

  const tabs = [
    {
      id: 'local',
      label: 'Local',
      icon: '💻',
      badge: resources.filter(r => r.status === 'DEGRADED' || r.status === 'FAILED').length || null,
    },
    {
      id: 'gcp',
      label: 'GCP',
      icon: '☁️',
    },
  ];

  const renderLocalTab = () => (
    <div className="app-container">
      <div className="app-sidebar">
        <ResourceDashboard
          resources={resources}
          selectedResource={selectedResource}
          onResourceSelect={handleResourceSelect}
          activeResources={validationState.fixTriggered ? validationState.degradedResources : []}
        />
        <MCPToolsPanel
          tools={tools}
          selectedResource={selectedResource}
        />
      </div>
      <div className="app-main">
        <FailureControls
          onFailureIntroduced={handleFailureIntroduced}
          onRefresh={loadData}
        />
        <ValidationPanel
          validationState={validationState}
          resources={resources}
          onReset={handleResetValidation}
          onClearAll={handleClearAll}
        />
        <LLMChat
          selectedResource={selectedResource}
          onFixTriggered={handleFixTriggered}
          degradedResources={validationState.degradedResources}
          resources={resources}
          fixTriggered={validationState.fixTriggered}
        />
        <FixHistory refreshKey={fixHistoryRefreshKey} />
      </div>
    </div>
  );

  const renderGCPTab = () => (
    <div className="gcp-tab-placeholder">
      <div className="placeholder-content">
        <div className="placeholder-icon">☁️</div>
        <h2>Google Cloud Platform</h2>
        <p>GCP resource management coming soon...</p>
        <p className="placeholder-subtitle">
          This tab will display GCP resources, their status, and allow LLM-based fixes for cloud infrastructure.
        </p>
      </div>
    </div>
  );

  return (
    <div className="app">
      <Header />
      <Tabs tabs={tabs} activeTab={activeTab} onTabChange={setActiveTab}>
        {activeTab === 'local' && (
          <div className="tab-panel">
            {renderLocalTab()}
          </div>
        )}
        {activeTab === 'gcp' && (
          <div className="tab-panel">
            {renderGCPTab()}
          </div>
        )}
      </Tabs>
    </div>
  );
}

export default App;

