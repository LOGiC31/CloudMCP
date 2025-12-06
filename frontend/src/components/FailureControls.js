import React, { useState } from 'react';
import { AlertTriangle, RefreshCw, Database, HardDrive, Zap, Globe } from 'lucide-react';
import { sampleAppService } from '../services/api';
import './FailureControls.css';

const FailureControls = ({ onFailureIntroduced, onRefresh, gcpMode = false }) => {
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState(null);

  const handleIntroduceFailure = async (type) => {
    setLoading(true);
    setMessage(null);
    try {
      await sampleAppService.introduceFailure(type);
      setMessage({
        type: 'success',
        text: `Failure introduced: ${type}. Monitoring status...`,
      });
      
      // Trigger smart polling (only once, it will handle its own polling)
      onFailureIntroduced(type);
      
      // Clear message after a delay
      setTimeout(() => setMessage(null), 10000);
    } catch (error) {
      setMessage({
        type: 'error',
        text: `Failed to introduce failure: ${error.message}`,
      });
    } finally {
      setLoading(false);
    }
  };

  const handleReset = async (type) => {
    setLoading(true);
    setMessage(null);
    try {
      if (type === 'redis') {
        await sampleAppService.resetRedis();
      } else if (type === 'postgres') {
        await sampleAppService.resetPostgres();
      } else if (type === 'nginx') {
        await sampleAppService.resetNginx();
      }
      setMessage({
        type: 'success',
        text: `${type} reset successfully`,
      });
      onRefresh();
      setTimeout(() => setMessage(null), 3000);
    } catch (error) {
      setMessage({
        type: 'error',
        text: `Failed to reset: ${error.message}`,
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="failure-controls">
      <div className="controls-header">
        <AlertTriangle size={20} />
        <h2>Failure Management</h2>
      </div>
      {message && (
        <div className={`message ${message.type}`}>
          {message.text}
        </div>
      )}
      <div className="controls-content">
        {gcpMode && (
          <div className="control-section">
            <h3>GCP Failure Introduction</h3>
            <p style={{ color: 'var(--text-secondary)', fontSize: '14px', marginBottom: '16px' }}>
              Use MCP tools to introduce failures or trigger LLM fixes directly. Select a resource and use the LLM chat to trigger fixes.
            </p>
            <div className="button-group">
              <button
                className="btn btn-info"
                onClick={() => {
                  setMessage({
                    type: 'info',
                    text: 'Select a GCP resource and use the LLM chat to trigger fixes. MCP tools can also be used to stop instances, scale resources, etc.',
                  });
                  setTimeout(() => setMessage(null), 5000);
                }}
              >
                <AlertTriangle size={18} />
                How to Use
              </button>
            </div>
            <div style={{ marginTop: '16px', padding: '12px', backgroundColor: 'var(--bg-secondary)', borderRadius: '8px', fontSize: '13px' }}>
              <strong>Available GCP Operations:</strong>
              <ul style={{ marginTop: '8px', paddingLeft: '20px' }}>
                <li><strong>Compute Engine:</strong> Stop instance, restart, scale machine type</li>
                <li><strong>Cloud SQL:</strong> Restart instance, scale tier, kill connections</li>
                <li><strong>Memorystore Redis:</strong> Restart instance, scale memory, flush data</li>
              </ul>
              <p style={{ marginTop: '8px', marginBottom: 0 }}>
                Select a resource from the sidebar, then use the LLM chat to trigger automatic fixes.
              </p>
            </div>
          </div>
        )}
        {!gcpMode && (
          <>
            <div className="control-section">
              <h3>Introduce Failure</h3>
              <div className="button-group">
                <button
                  className="btn btn-danger"
                  onClick={() => handleIntroduceFailure('redis')}
                  disabled={loading}
                >
                  <HardDrive size={18} />
                  Redis Memory
                </button>
                <button
                  className="btn btn-danger"
                  onClick={() => handleIntroduceFailure('database')}
                  disabled={loading}
                >
                  <Database size={18} />
                  Database Connections
                </button>
                <button
                  className="btn btn-danger"
                  onClick={() => handleIntroduceFailure('nginx')}
                  disabled={loading}
                >
                  <Globe size={18} />
                  Nginx Connections
                </button>
                <button
                  className="btn btn-danger"
                  onClick={() => handleIntroduceFailure('both')}
                  disabled={loading}
                >
                  <Zap size={18} />
                  Both
                </button>
              </div>
            </div>
            <div className="control-section">
              <h3>Reset Resources</h3>
          <div className="button-group">
            <button
              className="btn btn-secondary"
              onClick={() => handleReset('redis')}
              disabled={loading}
            >
              <RefreshCw size={18} />
              Reset Redis
            </button>
            <button
              className="btn btn-secondary"
              onClick={() => handleReset('postgres')}
              disabled={loading}
            >
              <RefreshCw size={18} />
              Reset PostgreSQL
            </button>
            <button
              className="btn btn-secondary"
              onClick={() => handleReset('nginx')}
              disabled={loading}
            >
              <RefreshCw size={18} />
              Reset Nginx
            </button>
          </div>
        </div>
          </>
        )}
      </div>
    </div>
  );
};

export default FailureControls;

