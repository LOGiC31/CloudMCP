import React, { useEffect, useState } from 'react';
import { CheckCircle, XCircle, AlertCircle, Loader, Trash2 } from 'lucide-react';
import './ValidationPanel.css';

const ValidationPanel = ({ validationState, resources, onReset, onClearAll }) => {
  const [currentStatus, setCurrentStatus] = useState({});

  useEffect(() => {
    // Update current status from resources
    const status = {};
    resources.forEach(r => {
      status[r.name] = r.status;
    });
    setCurrentStatus(status);
  }, [resources]);

  const getDegradedResources = () => {
    return resources.filter(r => r.status === 'DEGRADED' || r.status === 'FAILED');
  };

  const getAllHealthy = () => {
    return resources.length > 0 && resources.every(r => r.status === 'HEALTHY');
  };

  const validateFailureIntroduced = () => {
    if (!validationState.failureIntroduced) {
      // Still waiting for failure to be introduced
      return {
        pending: true,
        message: 'Waiting for failure to be introduced...',
      };
    }
    
    // Use the snapshot of degraded state when failure was detected
    // This prevents false negatives if the LLM fix happens very quickly
    const degradedSnapshot = validationState.degradedStateSnapshot || {};
    const expectedResources = validationState.failureType === 'redis' ? ['redis'] :
                             validationState.failureType === 'database' ? ['postgres'] :
                             validationState.failureType === 'nginx' ? ['nginx'] :
                             ['redis', 'postgres', 'nginx'];
    
    // Check if we have a snapshot of degraded resources
    const foundInSnapshot = expectedResources.filter(expected => {
      return Object.keys(degradedSnapshot).some(name => 
        name.toLowerCase().includes(expected.toLowerCase())
      );
    });
    
    if (foundInSnapshot.length > 0) {
      // We have a snapshot showing degraded state - validation passed
      const snapshotStatus = foundInSnapshot.map(expected => {
        const snapshotKey = Object.keys(degradedSnapshot).find(name => 
          name.toLowerCase().includes(expected.toLowerCase())
        );
        return snapshotKey ? `${snapshotKey}: ${degradedSnapshot[snapshotKey]}` : null;
      }).filter(Boolean).join(', ');
      
      // Check if resources are still degraded or have been fixed
      const currentDegraded = getDegradedResources();
      const stillDegraded = currentDegraded.filter(r => {
        const nameLower = r.name.toLowerCase();
        return foundInSnapshot.some(expected => nameLower.includes(expected.toLowerCase()));
      });
      
      if (stillDegraded.length > 0) {
        // Still degraded - show both snapshot and current state
        const currentStatus = stillDegraded.map(r => `${r.name}: ${r.status}`).join(', ');
        return {
          success: true,
          message: `✅ Failure validated: ${snapshotStatus} (detected when failure was introduced). Current status: ${currentStatus} - still needs fixing.`,
          resources: foundInSnapshot,
        };
      } else {
        // Already fixed - clarify this
        return {
          success: true,
          message: `✅ Failure validated: ${snapshotStatus} (detected when failure was introduced). Resource is now HEALTHY (may have been auto-fixed or recovered).`,
          resources: foundInSnapshot,
        };
      }
    } else {
      // Fallback: check current state if no snapshot
      const degraded = getDegradedResources();
      const foundDegraded = degraded.filter(r => {
        const nameLower = r.name.toLowerCase();
        return expectedResources.some(expected => nameLower.includes(expected.toLowerCase()));
      });
      
      if (foundDegraded.length > 0) {
        return {
          success: true,
          message: `✅ Failure validated: ${foundDegraded.map(r => `${r.name} (${r.status})`).join(', ')}`,
          resources: foundDegraded.map(r => r.name),
        };
      } else {
        // Check current status of expected resources
        const expectedStatus = expectedResources.map(expected => {
          const resource = resources.find(r => r.name.toLowerCase().includes(expected.toLowerCase()));
          return resource ? `${resource.name}: ${resource.status}` : `${expected}: not found`;
        }).join(', ');
        
        // No snapshot and no degraded resources found - failure detection timed out or failed
        return {
          success: false,
          message: `❌ Validation failed: Expected ${expectedResources.join(' or ')} to be DEGRADED. Current: ${expectedStatus}. The failure may not have been introduced properly, or it takes longer to manifest.`,
        };
      }
    }
  };

  const validateFixCompleted = () => {
    if (!validationState.fixTriggered) {
      return null; // Fix not triggered yet
    }
    
    if (!validationState.fixCompleted) {
      return {
        pending: true,
        message: 'Waiting for LLM fix to complete...',
      };
    }
    
    const allHealthy = getAllHealthy();
    const degraded = getDegradedResources();
    
    if (allHealthy) {
      return {
        success: true,
        message: '✅ Fix validated: All resources are now HEALTHY',
      };
    } else if (degraded.length > 0) {
      return {
        success: false,
        message: `❌ Fix incomplete: ${degraded.map(r => r.name).join(', ')} is still DEGRADED`,
        resources: degraded.map(r => r.name),
      };
    }
    
    // Fix completed but status unclear
    return {
      success: false,
      message: '⚠️ Fix completed but resource status is unclear',
    };
  };

  const failureValidation = validateFailureIntroduced();
  const fixValidation = validateFixCompleted();

  if (!validationState.failureIntroduced && !validationState.fixTriggered) {
    return null;
  }

  return (
    <div className="validation-panel">
      <div className="validation-header">
        <AlertCircle size={20} />
        <h2>Validation Status</h2>
        <div className="validation-actions">
          <button className="btn-reset" onClick={onReset}>
            Reset
          </button>
          <button className="btn-clear-all" onClick={onClearAll} title="Clear fix history and reset validation">
            <Trash2 size={16} />
            Clear All
          </button>
        </div>
      </div>
      
      <div className="validation-steps">
        {/* Step 1: Failure Introduction */}
        <div className="validation-step">
          <div className="step-header">
            {failureValidation?.pending ? (
              <Loader size={20} className="step-icon pending spinning" />
            ) : failureValidation?.success ? (
              <CheckCircle size={20} className="step-icon success" />
            ) : failureValidation ? (
              <XCircle size={20} className="step-icon failed" />
            ) : (
              <Loader size={20} className="step-icon pending spinning" />
            )}
            <span className="step-title">1. Failure Introduction</span>
          </div>
          {failureValidation && (
            <div className={`step-message ${failureValidation.pending ? 'pending' : (failureValidation.success ? 'success' : 'warning')}`}>
              {failureValidation.message}
              {failureValidation.resources && (
                <div className="step-resources">
                  <div className="resource-status-group">
                    <span className="status-label">Snapshot (when detected):</span>
                    {failureValidation.resources.map((r, idx) => {
                      const snapshotKey = Object.keys(validationState.degradedStateSnapshot || {}).find(name => 
                        name.toLowerCase().includes(r.toLowerCase())
                      );
                      const snapshotStatus = snapshotKey ? validationState.degradedStateSnapshot[snapshotKey] : 'UNKNOWN';
                      return (
                        <span key={idx} className="resource-badge snapshot">
                          {r}: {snapshotStatus}
                        </span>
                      );
                    })}
                  </div>
                  <div className="resource-status-group">
                    <span className="status-label">Current status:</span>
                    {failureValidation.resources.map((r, idx) => (
                      <span key={idx} className={`resource-badge current ${currentStatus[r] === 'HEALTHY' ? 'healthy' : 'degraded'}`}>
                        {r}: {currentStatus[r] || 'UNKNOWN'}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Step 2: LLM Fix Triggered */}
        {validationState.fixTriggered && (
          <div className="validation-step">
            <div className="step-header">
              <CheckCircle size={20} className="step-icon success" />
              <span className="step-title">2. LLM Fix Triggered</span>
            </div>
            <div className="step-message success">
              ✅ LLM fix has been triggered and is processing...
            </div>
          </div>
        )}

        {/* Step 3: Fix Completion */}
        {validationState.fixTriggered && (
          <div className="validation-step">
            <div className="step-header">
              {fixValidation?.pending ? (
                <Loader size={20} className="step-icon pending spinning" />
              ) : fixValidation?.success ? (
                <CheckCircle size={20} className="step-icon success" />
              ) : fixValidation ? (
                <XCircle size={20} className="step-icon failed" />
              ) : (
                <Loader size={20} className="step-icon pending spinning" />
              )}
              <span className="step-title">3. Fix Completion</span>
            </div>
            {fixValidation && (
              <div className={`step-message ${fixValidation.pending ? 'pending' : (fixValidation.success ? 'success' : 'warning')}`}>
                {fixValidation.message}
                {fixValidation.resources && (
                  <div className="step-resources">
                    {fixValidation.resources.map((r, idx) => (
                      <span key={idx} className="resource-badge">
                        {r}: {currentStatus[r] || 'UNKNOWN'}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default ValidationPanel;

