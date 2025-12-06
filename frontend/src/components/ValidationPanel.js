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
    if (!validationState.failureIntroduced) return null;
    
    // Use the snapshot of degraded state when failure was detected
    // This prevents false negatives if the LLM fix happens very quickly
    const degradedSnapshot = validationState.degradedStateSnapshot || {};
    const expectedResources = validationState.failureType === 'redis' ? ['redis'] :
                             validationState.failureType === 'database' ? ['postgres'] :
                             ['redis', 'postgres'];
    
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
      
      return {
        success: true,
        message: `✅ Failure validated: ${snapshotStatus} (detected when failure was introduced)`,
        resources: foundInSnapshot,
      };
    } else {
      // Fallback: check current state if no snapshot (shouldn't happen, but just in case)
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
        
        return {
          success: false,
          message: `⚠️ Validation: Expected ${expectedResources.join(' or ')} to be DEGRADED. Current: ${expectedStatus}. Note: If LLM fix completed quickly, check the snapshot.`,
        };
      }
    }
  };

  const validateFixCompleted = () => {
    if (!validationState.fixTriggered || !validationState.fixCompleted) return null;
    
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
        message: `⚠️ Fix incomplete: ${degraded.map(r => r.name).join(', ')} is still DEGRADED`,
        resources: degraded.map(r => r.name),
      };
    }
    return null;
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
            {validationState.failureIntroduced ? (
              failureValidation?.success ? (
                <CheckCircle size={20} className="step-icon success" />
              ) : (
                <XCircle size={20} className="step-icon failed" />
              )
            ) : (
              <Loader size={20} className="step-icon pending spinning" />
            )}
            <span className="step-title">1. Failure Introduction</span>
          </div>
          {validationState.failureIntroduced && failureValidation && (
            <div className={`step-message ${failureValidation.success ? 'success' : 'warning'}`}>
              {failureValidation.message}
              {failureValidation.resources && (
                <div className="step-resources">
                  {failureValidation.resources.map((r, idx) => (
                    <span key={idx} className="resource-badge">
                      {r}: {currentStatus[r] || 'UNKNOWN'}
                    </span>
                  ))}
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
        {validationState.fixCompleted && (
          <div className="validation-step">
            <div className="step-header">
              {fixValidation?.success ? (
                <CheckCircle size={20} className="step-icon success" />
              ) : (
                <XCircle size={20} className="step-icon failed" />
              )}
              <span className="step-title">3. Fix Completion</span>
            </div>
            {fixValidation && (
              <div className={`step-message ${fixValidation.success ? 'success' : 'warning'}`}>
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

