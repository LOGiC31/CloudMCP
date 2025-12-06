import React from 'react';
import { Database, HardDrive, Server, Activity, AlertCircle, CheckCircle, XCircle } from 'lucide-react';
import './ResourceDashboard.css';

const ResourceDashboard = ({ resources, selectedResource, onResourceSelect, activeResources = [] }) => {
  const getStatusIcon = (status) => {
    // Treat READY, RUNNING, RUNNABLE as healthy
    const healthyStatuses = ['HEALTHY', 'READY', 'RUNNING', 'RUNNABLE'];
    if (healthyStatuses.includes(status)) {
      return <CheckCircle size={20} className="status-icon healthy" />;
    }
    switch (status) {
      case 'DEGRADED':
        return <AlertCircle size={20} className="status-icon degraded" />;
      case 'FAILED':
        return <XCircle size={20} className="status-icon failed" />;
      default:
        return <Activity size={20} className="status-icon unknown" />;
    }
  };

  const getResourceIcon = (name) => {
    const nameLower = name.toLowerCase();
    if (nameLower.includes('postgres') || nameLower.includes('database')) {
      return <Database size={24} />;
    } else if (nameLower.includes('redis') || nameLower.includes('cache')) {
      return <HardDrive size={24} />;
    } else {
      return <Server size={24} />;
    }
  };

  const getStatusColor = (status) => {
    // Treat READY, RUNNING, RUNNABLE as healthy (green)
    const healthyStatuses = ['HEALTHY', 'READY', 'RUNNING', 'RUNNABLE'];
    if (healthyStatuses.includes(status)) {
      return 'var(--accent-success)';
    }
    switch (status) {
      case 'DEGRADED':
        return 'var(--accent-warning)';
      case 'FAILED':
        return 'var(--accent-danger)';
      default:
        return 'var(--text-secondary)';
    }
  };

  const getStatusClassName = (status) => {
    // Map status to CSS class name
    // Treat READY, RUNNING, RUNNABLE as healthy
    const healthyStatuses = ['HEALTHY', 'READY', 'RUNNING', 'RUNNABLE'];
    if (healthyStatuses.includes(status)) {
      return 'healthy';
    }
    const unhealthyStatuses = ['DEGRADED', 'UPDATING', 'CREATING', 'STAGING', 'PROVISIONING', 'PENDING_CREATE', 'PENDING_UPDATE'];
    if (unhealthyStatuses.includes(status)) {
      return 'degraded';
    }
    const failedStatuses = ['FAILED', 'TERMINATED', 'STOPPING', 'MAINTENANCE', 'DELETING', 'REPAIRING'];
    if (failedStatuses.includes(status)) {
      return 'failed';
    }
    return status.toLowerCase();
  };

  const formatMetrics = (resource) => {
    const metrics = resource.metrics || {};
    const parts = [];

    if (resource.name.toLowerCase().includes('postgres')) {
      const connPct = metrics.connection_usage_percent || 0;
      const total = metrics.total_connections || 0;
      const max = metrics.max_connections || 0;
      parts.push(`Connections: ${total}/${max} (${connPct.toFixed(1)}%)`);
    }

    if (resource.name.toLowerCase().includes('redis')) {
      const memPct = metrics.redis_memory_usage_percent || 0;
      const usedMB = (metrics.redis_used_memory_bytes || 0) / 1024 / 1024;
      const maxMB = (metrics.redis_max_memory_bytes || 0) / 1024 / 1024;
      parts.push(`Memory: ${usedMB.toFixed(1)}MB/${maxMB.toFixed(1)}MB (${memPct.toFixed(1)}%)`);
    }

    if (metrics.cpu_usage_percent !== undefined) {
      parts.push(`CPU: ${metrics.cpu_usage_percent.toFixed(1)}%`);
    }

    return parts.join(' • ');
  };

  return (
    <div className="resource-dashboard">
      <div className="dashboard-header">
        <h2>Resources</h2>
        <span className="resource-count">{resources.length}</span>
      </div>
      <div className="resource-list">
        {resources.map((resource) => {
          const isSelected = selectedResource?.id === resource.id;
          const isActive = activeResources.some(name => 
            resource.name.toLowerCase().includes(name.toLowerCase())
          );
          return (
            <div
              key={resource.id || resource.name}
              className={`resource-card ${getStatusClassName(resource.status)} ${isSelected ? 'selected' : ''} ${isActive ? 'active-fixing' : ''}`}
              onClick={() => onResourceSelect(resource)}
            >
              <div className="resource-header">
                <div className="resource-icon">
                  {getResourceIcon(resource.name)}
                </div>
                <div className="resource-info">
                  <h3>{resource.name}</h3>
                  <div className="resource-status">
                    {getStatusIcon(resource.status)}
                    <span style={{ color: getStatusColor(resource.status) }}>
                      {resource.status}
                    </span>
                  </div>
                </div>
              </div>
              {resource.metrics && (
                <div className="resource-metrics">
                  {formatMetrics(resource)}
                </div>
              )}
              <div
                className="status-indicator"
                style={{ backgroundColor: getStatusColor(resource.status) }}
              ></div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default ResourceDashboard;

