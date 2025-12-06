import React, { useState } from 'react';
import { AlertTriangle, RefreshCw, Database, HardDrive, Zap, Globe, Server } from 'lucide-react';
import { sampleAppService, gcpFailureService } from '../services/api';
import './FailureControls.css';

const FailureControls = ({ onFailureIntroduced, onRefresh, gcpMode = false, selectedResource = null }) => {
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

  const handleGCPFailure = async (action, resourceType) => {
    if (!selectedResource) {
      setMessage({
        type: 'error',
        text: 'Please select a GCP resource first',
      });
      setTimeout(() => setMessage(null), 3000);
      return;
    }

    setLoading(true);
    setMessage(null);
    try {
      const resourceName = selectedResource.name;
      let response;

      if (action === 'memory-pressure') {
        if (resourceType === 'redis') {
          response = await gcpFailureService.redisMemoryPressure(resourceName, 0.95);
          setMessage({
            type: 'success',
            text: `Redis memory pressure: Filling memory to 95%. This simulates real memory exhaustion. Monitoring status...`,
          });
          // Trigger smart polling for Redis memory pressure
          onFailureIntroduced('redis', resourceName);
        } else if (resourceType === 'compute') {
          const zone = selectedResource.gcp_zone || null;
          response = await gcpFailureService.computeMemoryPressure(resourceName, zone, 0.90);
          setMessage({
            type: 'success',
            text: `Compute memory pressure: Allocating memory to 90%. This simulates memory leak. Monitoring status...`,
          });
          // Trigger smart polling for Compute memory pressure
          onFailureIntroduced('compute', resourceName);
        }
      } else if (action === 'cpu-stress') {
        if (resourceType === 'compute') {
          const zone = selectedResource.gcp_zone || null;
          response = await gcpFailureService.computeCpuStress(resourceName, zone, 600, 90);
          setMessage({
            type: 'success',
            text: `Compute CPU stress: Creating 90% CPU load for 10 minutes. This simulates high CPU usage. Monitoring status...`,
          });
          // Trigger smart polling for CPU stress failure
          // Pass the actual resource name for GCP validation
          onFailureIntroduced('compute', resourceName);
        }
      } else if (action === 'connection-overload') {
        if (resourceType === 'sql') {
          response = await gcpFailureService.sqlConnectionOverload(resourceName, 100);
          setMessage({
            type: 'success',
            text: `SQL connection overload: Creating 100 connections. This simulates connection pool exhaustion. Monitoring status...`,
          });
          // Trigger smart polling for SQL connection overload
          onFailureIntroduced('sql', resourceName);
        }
      } else if (action === 'blocking-queries') {
        if (resourceType === 'sql') {
          response = await gcpFailureService.sqlBlockingQueries(resourceName, 10, 300);
          setMessage({
            type: 'success',
            text: `SQL blocking queries: Creating 10 blocking queries for 5 minutes. This simulates lock contention. Monitoring status...`,
          });
          // Trigger smart polling for SQL blocking queries
          onFailureIntroduced('sql', resourceName);
        }
      } else if (action === 'degrade') {
        if (resourceType === 'redis') {
          response = await gcpFailureService.degradeRedis(resourceName, 0.5);
          setMessage({
            type: 'success',
            text: `Redis failure introduced: Scaling down memory to 0.5GB. Monitoring status...`,
          });
          // Trigger smart polling for Redis degradation
          onFailureIntroduced('redis', resourceName);
        } else if (resourceType === 'compute') {
          const zone = selectedResource.gcp_zone || null;
          response = await gcpFailureService.stopCompute(resourceName, zone);
          setMessage({
            type: 'success',
            text: `Compute failure introduced: Stopping instance. Monitoring status...`,
          });
          // Trigger smart polling for Compute stop
          onFailureIntroduced('compute', resourceName);
        } else if (resourceType === 'sql') {
          response = await gcpFailureService.stopSQL(resourceName);
          setMessage({
            type: 'success',
            text: `SQL failure introduced: Stopping instance. Monitoring status...`,
          });
          // Trigger smart polling for SQL stop
          onFailureIntroduced('sql', resourceName);
        }
      } else if (action === 'clear-memory') {
        if (resourceType === 'redis') {
          response = await gcpFailureService.clearRedisMemory(resourceName);
          setMessage({
            type: 'success',
            text: `Redis memory cleared: All data flushed. Resource should recover.`,
          });
          onRefresh();
          setTimeout(() => setMessage(null), 3000);
          return;
        }
      } else if (action === 'reset') {
        if (resourceType === 'redis') {
          response = await gcpFailureService.resetRedis(resourceName, 1.0);
          setMessage({
            type: 'success',
            text: `Redis reset: Scaling memory back to 1GB`,
          });
        } else if (resourceType === 'compute') {
          const zone = selectedResource.gcp_zone || null;
          response = await gcpFailureService.startCompute(resourceName, zone);
          setMessage({
            type: 'success',
            text: `Compute reset: Starting instance`,
          });
        } else if (resourceType === 'sql') {
          response = await gcpFailureService.startSQL(resourceName);
          setMessage({
            type: 'success',
            text: `SQL reset: Starting instance`,
          });
        }
        onRefresh();
        setTimeout(() => setMessage(null), 3000);
        return;
      }

      // Note: Smart polling is triggered individually for each action above
      // This ensures the correct resource name is passed for validation

      // Clear message after a delay
      setTimeout(() => setMessage(null), 10000);
    } catch (error) {
      setMessage({
        type: 'error',
        text: `Failed to ${action} ${resourceType}: ${error.response?.data?.detail || error.message}`,
      });
      setTimeout(() => setMessage(null), 5000);
    } finally {
      setLoading(false);
    }
  };

  const getGCPResourceType = () => {
    if (!selectedResource) return null;
    const type = selectedResource.type || '';
    const name = selectedResource.name?.toLowerCase() || '';
    
    if (type.includes('redis') || name.includes('redis')) return 'redis';
    if (type.includes('compute') || name.includes('vm') || name.includes('compute')) return 'compute';
    if (type.includes('sql') || name.includes('sql')) return 'sql';
    return null;
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
          <>
            <div className="control-section">
              <h3>Introduce Failure</h3>
              {!selectedResource ? (
                <p style={{ color: 'var(--text-secondary)', fontSize: '14px', marginBottom: '16px' }}>
                  Select a GCP resource from the sidebar to introduce failures
                </p>
              ) : (
                <>
                  <p style={{ color: 'var(--text-secondary)', fontSize: '14px', marginBottom: '16px' }}>
                    Selected: <strong>{selectedResource.name}</strong> ({getGCPResourceType() || 'unknown'})
                  </p>
                  <div className="button-group">
                    {getGCPResourceType() === 'redis' && (
                      <>
                        <button
                          className="btn btn-danger"
                          onClick={() => handleGCPFailure('memory-pressure', 'redis')}
                          disabled={loading}
                          title="Fill Redis memory to 95% to simulate memory pressure"
                        >
                          <HardDrive size={18} />
                          Memory Pressure
                        </button>
                        <button
                          className="btn btn-warning"
                          onClick={() => handleGCPFailure('degrade', 'redis')}
                          disabled={loading}
                          title="Scale down memory (simpler failure)"
                        >
                          <HardDrive size={18} />
                          Scale Down
                        </button>
                      </>
                    )}
                    {getGCPResourceType() === 'compute' && (
                      <>
                        <button
                          className="btn btn-danger"
                          onClick={() => handleGCPFailure('cpu-stress', 'compute')}
                          disabled={loading}
                          title="Create high CPU load (90% for 10 minutes)"
                        >
                          <Server size={18} />
                          CPU Stress
                        </button>
                        <button
                          className="btn btn-danger"
                          onClick={() => handleGCPFailure('memory-pressure', 'compute')}
                          disabled={loading}
                          title="Fill memory to 90% to simulate memory pressure"
                        >
                          <Server size={18} />
                          Memory Pressure
                        </button>
                        <button
                          className="btn btn-warning"
                          onClick={() => handleGCPFailure('degrade', 'compute')}
                          disabled={loading}
                          title="Stop instance (simpler failure)"
                        >
                          <Server size={18} />
                          Stop Instance
                        </button>
                      </>
                    )}
                    {getGCPResourceType() === 'sql' && (
                      <>
                        <button
                          className="btn btn-danger"
                          onClick={() => handleGCPFailure('connection-overload', 'sql')}
                          disabled={loading}
                          title="Create 100 connections to overload the database"
                        >
                          <Database size={18} />
                          Connection Overload
                        </button>
                        <button
                          className="btn btn-danger"
                          onClick={() => handleGCPFailure('blocking-queries', 'sql')}
                          disabled={loading}
                          title="Create blocking queries that hold locks"
                        >
                          <Database size={18} />
                          Blocking Queries
                        </button>
                        <button
                          className="btn btn-warning"
                          onClick={() => handleGCPFailure('degrade', 'sql')}
                          disabled={loading}
                          title="Stop instance (simpler failure)"
                        >
                          <Database size={18} />
                          Stop Instance
                        </button>
                      </>
                    )}
                    {!getGCPResourceType() && (
                      <p style={{ color: 'var(--text-secondary)', fontSize: '13px' }}>
                        Unsupported resource type. Select Redis, Compute, or SQL.
                      </p>
                    )}
                  </div>
                </>
              )}
            </div>
            <div className="control-section">
              <h3>Reset Resource</h3>
              {!selectedResource ? (
                <p style={{ color: 'var(--text-secondary)', fontSize: '14px', marginBottom: '16px' }}>
                  Select a GCP resource from the sidebar to reset
                </p>
              ) : (
                <>
                  <div className="button-group">
                    {getGCPResourceType() === 'redis' && (
                      <>
                        <button
                          className="btn btn-secondary"
                          onClick={() => handleGCPFailure('clear-memory', 'redis')}
                          disabled={loading}
                          title="Clear memory pressure by flushing all data"
                        >
                          <RefreshCw size={18} />
                          Clear Memory
                        </button>
                        <button
                          className="btn btn-secondary"
                          onClick={() => handleGCPFailure('reset', 'redis')}
                          disabled={loading}
                          title="Scale memory back up"
                        >
                          <RefreshCw size={18} />
                          Scale Up
                        </button>
                      </>
                    )}
                    {getGCPResourceType() === 'compute' && (
                      <button
                        className="btn btn-secondary"
                        onClick={() => handleGCPFailure('reset', 'compute')}
                        disabled={loading}
                        title="Start stopped instance"
                      >
                        <RefreshCw size={18} />
                        Start Instance
                      </button>
                    )}
                    {getGCPResourceType() === 'sql' && (
                      <button
                        className="btn btn-secondary"
                        onClick={() => handleGCPFailure('reset', 'sql')}
                        disabled={loading}
                        title="Start stopped instance"
                      >
                        <RefreshCw size={18} />
                        Start Instance
                      </button>
                    )}
                  </div>
                </>
              )}
            </div>
          </>
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

