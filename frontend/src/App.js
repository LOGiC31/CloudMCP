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

  // Load resources list and tools only once on mount (they don't change often)
  useEffect(() => {
    loadResourcesAndTools();
  }, []); // Only run once on mount

  // Poll for status updates only (lightweight)
  // Stop polling when LLM fix is in progress to reduce API load
  useEffect(() => {
    if (!loading) {
      // Start polling for status updates
      // Stop polling when: isPolling is true OR fix is in progress (fixTriggered but not completed)
      const statusInterval = setInterval(() => {
        const shouldPoll = !isPolling && !(validationState.fixTriggered && !validationState.fixCompleted);
        if (shouldPoll) {
          updateResourceStatus();
        }
      }, 30000); // Poll every 30 seconds for status updates
      
      return () => clearInterval(statusInterval);
    }
  }, [loading, isPolling, validationState.fixTriggered, validationState.fixCompleted]); // eslint-disable-line react-hooks/exhaustive-deps

  const loadResourcesAndTools = async () => {
    try {
      setLoading(true);
      const { resourceService, toolService } = await import('./services/api');
      const [resourcesRes, toolsRes] = await Promise.all([
        resourceService.getAll(),
        toolService.getAll(),
      ]);
      const newResources = resourcesRes.data;
      setResources(newResources);
      setTools(toolsRes.data || []);
      setLoading(false);
    } catch (error) {
      console.error('Error loading resources and tools:', error);
      setLoading(false);
    }
  };

  const updateResourceStatus = async () => {
    try {
      const { resourceService } = await import('./services/api');
      const statusRes = await resourceService.getStatusUpdates();
      const statusUpdates = statusRes.data;
      
      // Update status and metrics for existing resources, and add any new resources
      setResources(prevResources => {
        const resourceMap = new Map(prevResources.map(r => [r.id || r.name, r]));
        
        // Update existing resources and add new ones
        statusUpdates.forEach(statusUpdate => {
          const key = statusUpdate.id || statusUpdate.name;
          if (resourceMap.has(key)) {
            // Update existing resource
            resourceMap.set(key, {
              ...resourceMap.get(key),
              status: statusUpdate.status,
              metrics: statusUpdate.metrics,
              last_updated: statusUpdate.last_updated,
            });
          } else {
            // Add new resource (e.g., newly discovered GCP resource)
            resourceMap.set(key, statusUpdate);
          }
        });
        
        const updatedResources = Array.from(resourceMap.values());
        
        // Update validation state based on status changes
        updateValidationState(updatedResources);
        
        return updatedResources;
      });
    } catch (error) {
      console.error('Error updating resource status:', error);
    }
  };

  const updateValidationState = (newResources) => {
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
  };

  const handleResourceSelect = (resource) => {
    // Toggle selection: if clicking the same resource, deselect it
    if (selectedResource?.id === resource.id) {
      setSelectedResource(null);
    } else {
      setSelectedResource(resource);
    }
  };

  const handleFailureIntroduced = async (failureType, resourceName = null) => {
    setIsPolling(true);
    
    // Wait for status to update (longer for database connections, Redis needs time to fill memory)
    // For GCP compute CPU stress, wait a bit longer for metrics to update
    const initialWait = failureType === 'database' ? 10000 : 
                       failureType === 'redis' ? 12000 : 
                       failureType === 'nginx' ? 10000 : 
                       failureType === 'compute' ? 15000 : // GCP compute needs more time for CPU metrics
                       10000;
    await new Promise(resolve => setTimeout(resolve, initialWait));
    
    // Smart polling: check status until we see degraded resources or timeout
    let attempts = 0;
    const maxAttempts = failureType === 'compute' ? 15 : 10; // More attempts for GCP (30 seconds)
    const pollInterval = 2000; // Check every 2 seconds
    
    const pollForStatus = async () => {
      attempts++;
      
      // Fetch latest status updates directly from API
      const { resourceService } = await import('./services/api');
      try {
        const statusRes = await resourceService.getStatusUpdates();
        const statusUpdates = statusRes.data;
        
        // Update only status for existing resources
        setResources(prevResources => {
          const updated = prevResources.map(prevResource => {
            const statusUpdate = statusUpdates.find(su => su.id === prevResource.id || su.name === prevResource.name);
            if (statusUpdate) {
              return {
                ...prevResource,
                status: statusUpdate.status,
                metrics: statusUpdate.metrics,
                last_updated: statusUpdate.last_updated,
              };
            }
            return prevResource;
          });
          return updated;
        });
        
        // Get updated resources for validation (merge with existing)
        const newResources = statusUpdates.map(su => {
          const existing = resources.find(r => r.id === su.id || r.name === su.name);
          return existing ? { ...existing, ...su } : su;
        });
        
        const degraded = newResources.filter(r => r.status === 'DEGRADED' || r.status === 'FAILED');
        
        // Determine expected resources based on failure type and resource name
        let expectedResources;
        if (resourceName) {
          // GCP failure: check the specific resource name
          expectedResources = [resourceName.toLowerCase()];
        } else {
          // Local failure: use type-based mapping
          expectedResources = failureType === 'redis' ? ['redis'] :
                             failureType === 'database' ? ['postgres'] :
                             failureType === 'nginx' ? ['nginx'] :
                             ['redis', 'postgres', 'nginx'];
        }
        
        const foundDegraded = degraded.filter(r => {
          const nameLower = r.name.toLowerCase();
          return expectedResources.some(expected => nameLower === expected || nameLower.includes(expected));
        });
        
        if (foundDegraded.length > 0 || attempts >= maxAttempts) {
          // Found degraded resources or timeout - store snapshot of degraded state
          const degradedSnapshot = {};
          newResources.forEach(r => {
            if (r.status === 'DEGRADED' || r.status === 'FAILED') {
              degradedSnapshot[r.name] = r.status;
            }
          });
          
          // Always set failureIntroduced to true, even if timeout (so validation can show status)
          setValidationState(prev => ({
            ...prev,
            failureIntroduced: true,
            failureType: failureType,
            resourceName: resourceName, // Store resource name for GCP validation
            degradedResources: foundDegraded.map(r => r.name),
            degradedStateSnapshot: degradedSnapshot, // Store snapshot for validation (may be empty if timeout)
          }));
          setIsPolling(false);
          
          if (foundDegraded.length === 0 && attempts >= maxAttempts) {
            console.warn(`Timeout: Failed to detect ${expectedResources.join(' or ')} as degraded after ${maxAttempts} attempts`);
          }
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
          // Timeout - set failureIntroduced to true so validation can show status
          setValidationState(prev => ({
            ...prev,
            failureIntroduced: true,
            failureType: failureType,
            resourceName: resourceName, // Store resource name for GCP validation
            degradedResources: [],
            degradedStateSnapshot: {}, // Empty snapshot on error/timeout
          }));
          setIsPolling(false);
        }
      }
    };
    
    pollForStatus();
  };

  const handleFixTriggered = async (executionStatus = null) => {
    // Check if this is the first call (fix starting) or second call (fix completed)
    // First call: executionStatus is null/undefined
    // Second call: executionStatus is provided (SUCCESS, FAILED, TIMEOUT, ERROR, UNKNOWN)
    const isFirstCall = executionStatus === null || executionStatus === undefined;
    
    if (isFirstCall) {
      // First call: Mark fix as triggered - this will stop status polling
      console.log('[Fix] First call: Stopping status polling');
      setValidationState(prev => ({
        ...prev,
        fixTriggered: true,
        fixCompleted: false, // Reset completion status
      }));
      
      // Stop status polling during LLM processing
      setIsPolling(true);
    } else {
      // Second call: Fix has completed (executionStatus is provided)
      console.log('[Fix] Second call: Fix completed with status:', executionStatus);
      
      // Wait a bit for fix to be applied and status to update
      await new Promise(resolve => setTimeout(resolve, 3000));
      
      // Check status once - fix should already be complete
      const { resourceService } = await import('./services/api');
      try {
        console.log('[Fix] Fetching updated resource status...');
        const statusRes = await resourceService.getStatusUpdates();
        const statusUpdates = statusRes.data;
        
        // Update only status for existing resources
        setResources(prevResources => {
          return prevResources.map(prevResource => {
            const statusUpdate = statusUpdates.find(su => su.id === prevResource.id || su.name === prevResource.name);
            if (statusUpdate) {
              return {
                ...prevResource,
                status: statusUpdate.status,
                metrics: statusUpdate.metrics,
                last_updated: statusUpdate.last_updated,
              };
            }
            return prevResource;
          });
        });
        
        // Get updated resources for validation
        const newResources = statusUpdates.map(su => {
          const existing = resources.find(r => r.id === su.id || r.name === su.name);
          return existing ? { ...existing, ...su } : su;
        });
        
        const allHealthy = newResources.length > 0 && newResources.every(r => 
          r.status === 'HEALTHY' || r.status === 'READY' || r.status === 'RUNNING' || r.status === 'RUNNABLE'
        );
        
        console.log('[Fix] Resources healthy:', allHealthy, 'Status updates:', statusUpdates.length);
        
        // Mark fix as completed (execution is done, regardless of success/failure)
        // This will update validation panel and resume status polling
        setValidationState(prev => {
          const newState = {
            ...prev,
            fixCompleted: true, // Fix execution is complete (SUCCESS, FAILED, or TIMEOUT)
            // Clear degraded resources when fix completes successfully
            degradedResources: allHealthy ? [] : prev.degradedResources,
          };
          console.log('[Fix] Setting fixCompleted to true, new state:', newState);
          return newState;
        });
      } catch (error) {
        console.error('[Fix] Error checking fix status:', error);
        // Even if status check fails, mark fix as completed so polling resumes
        setValidationState(prev => {
          const newState = {
            ...prev,
            fixCompleted: true,
          };
          console.log('[Fix] Error case: Setting fixCompleted to true, new state:', newState);
          return newState;
        });
      } finally {
        // Resume status polling after fix completes (always, regardless of success/failure)
        console.log('[Fix] Resuming status polling');
        setIsPolling(false);
      }
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

  const handleRefreshResources = async () => {
    // Manual refresh of resources list and tools (in case containers were added/removed)
    await loadResourcesAndTools();
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
      await loadResourcesAndTools();
      
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

  // Filter resources by type for badges
  const localResources = resources.filter(r => !r.type || !r.type.startsWith('gcp-'));
  const gcpResources = resources.filter(r => r.type && r.type.startsWith('gcp-'));
  
  const tabs = [
    {
      id: 'local',
      label: 'Local',
      icon: '💻',
      badge: localResources.filter(r => r.status === 'DEGRADED' || r.status === 'FAILED').length || null,
    },
    {
      id: 'gcp',
      label: 'GCP',
      icon: '☁️',
      badge: gcpResources.filter(r => r.status === 'DEGRADED' || r.status === 'FAILED').length || null,
    },
  ];

  const renderLocalTab = () => {
    // Filter local resources (exclude GCP)
    const localResourcesFiltered = resources.filter(r => !r.type || !r.type.startsWith('gcp-'));
    const localTools = tools.filter(t => !t.name || !t.name.startsWith('gcp_'));
    
    return (
      <div className="app-container">
        <div className="app-sidebar">
          <ResourceDashboard
            resources={localResourcesFiltered}
            selectedResource={selectedResource}
            onResourceSelect={handleResourceSelect}
            activeResources={validationState.fixTriggered ? validationState.degradedResources : []}
          />
          <MCPToolsPanel
            tools={localTools}
            selectedResource={selectedResource}
          />
        </div>
      <div className="app-main">
        <FailureControls
          onFailureIntroduced={handleFailureIntroduced}
          onRefresh={handleRefreshResources}
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
  };

  const renderGCPTab = () => {
    // Filter GCP resources (type starts with 'gcp-')
    const gcpResources = resources.filter(r => r.type && r.type.startsWith('gcp-'));
    const gcpTools = tools.filter(t => t.name && t.name.startsWith('gcp_'));
    
    return (
      <div className="app-container">
        <div className="app-sidebar">
          <ResourceDashboard
            resources={gcpResources}
            selectedResource={selectedResource}
            onResourceSelect={handleResourceSelect}
            activeResources={validationState.fixTriggered ? validationState.degradedResources : []}
          />
          <MCPToolsPanel
            tools={gcpTools}
            selectedResource={selectedResource}
          />
        </div>
        <div className="app-main">
          {gcpResources.length === 0 ? (
            <div className="gcp-tab-placeholder">
              <div className="placeholder-content">
                <div className="placeholder-icon">☁️</div>
                <h2>Google Cloud Platform</h2>
                <p>No GCP resources found.</p>
                <p className="placeholder-subtitle">
                  To enable GCP resources:
                  <br />1. Set GCP_PROJECT_ID in backend .env
                  <br />2. Set GCP_ENABLED=true
                  <br />3. Configure service account credentials
                  <br />4. Deploy resources to GCP
                </p>
              </div>
            </div>
          ) : (
            <>
              <FailureControls
                onFailureIntroduced={handleFailureIntroduced}
                onRefresh={handleRefreshResources}
                gcpMode={true}
                selectedResource={selectedResource}
              />
              <ValidationPanel
                validationState={validationState}
                resources={gcpResources}
                onReset={handleResetValidation}
                onClearAll={handleClearAll}
              />
              <LLMChat
                selectedResource={selectedResource}
                onFixTriggered={handleFixTriggered}
                degradedResources={validationState.degradedResources}
                resources={gcpResources}
                fixTriggered={validationState.fixTriggered}
              />
              <FixHistory refreshKey={fixHistoryRefreshKey} />
            </>
          )}
        </div>
      </div>
    );
  };

  return (
    <div className="app">
      <Header onRefresh={handleRefreshResources} />
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

