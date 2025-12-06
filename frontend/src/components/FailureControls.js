import React, { useState } from 'react';
import { AlertTriangle, RefreshCw, Database, HardDrive, Zap } from 'lucide-react';
import { sampleAppService } from '../services/api';
import './FailureControls.css';

const FailureControls = ({ onFailureIntroduced, onRefresh }) => {
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
          </div>
        </div>
      </div>
    </div>
  );
};

export default FailureControls;

