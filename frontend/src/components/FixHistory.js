import React, { useState, useEffect } from 'react';
import { History, CheckCircle, XCircle, Clock, Trash2, Download } from 'lucide-react';
import { fixService } from '../services/api';
import './FixHistory.css';

const FixHistory = ({ refreshKey }) => {
  const [fixes, setFixes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedFix, setSelectedFix] = useState(null);

  useEffect(() => {
    loadFixHistory();
    // Refresh every 1 minute
    const interval = setInterval(loadFixHistory, 60000);
    return () => clearInterval(interval);
  }, []);

  // Refresh when refreshKey changes (triggered by parent when clearing)
  useEffect(() => {
    if (refreshKey > 0) {
      loadFixHistory();
    }
  }, [refreshKey]);

  const loadFixHistory = async () => {
    try {
      const response = await fixService.getAll({ limit: 20 });
      setFixes(response.data || []);
      setLoading(false);
    } catch (error) {
      console.error('Error loading fix history:', error);
      setLoading(false);
    }
  };

  const formatTimestamp = (timestamp) => {
    const date = new Date(timestamp);
    return date.toLocaleString();
  };

  const getStatusIcon = (status) => {
    switch (status) {
      case 'SUCCESS':
        return <CheckCircle size={16} className="status-icon success" />;
      case 'FAILED':
        return <XCircle size={16} className="status-icon failed" />;
      default:
        return <Clock size={16} className="status-icon pending" />;
    }
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'SUCCESS':
        return 'var(--accent-success)';
      case 'FAILED':
        return 'var(--accent-danger)';
      default:
        return 'var(--accent-warning)';
    }
  };

  const getResourceStatusChange = (fix) => {
    const before = fix.before_metrics || {};
    const after = fix.after_metrics || {};
    const changes = [];

    for (const resourceName of Object.keys(before)) {
      const beforeStatus = before[resourceName]?.status;
      const afterStatus = after[resourceName]?.status;
      if (beforeStatus !== afterStatus) {
        changes.push({
          resource: resourceName,
          before: beforeStatus,
          after: afterStatus,
        });
      }
    }
    return changes;
  };

  const handleDeleteAll = async () => {
    if (!window.confirm('Are you sure you want to delete all fix history? This action cannot be undone.')) {
      return;
    }

    try {
      await fixService.deleteAll();
      setFixes([]);
      setSelectedFix(null);
      console.log('Fix history deleted successfully');
    } catch (error) {
      console.error('Error deleting fix history:', error);
      alert('Failed to delete fix history. Please try again.');
    }
  };

  const handleExportCSV = () => {
    if (fixes.length === 0) {
      alert('No fix history to export.');
      return;
    }

    // Prepare CSV headers
    const headers = [
      'ID',
      'Timestamp',
      'Status',
      'Root Cause',
      'Reasoning',
      'Tools Used',
      'Resource Changes',
      'Before Metrics',
      'After Metrics',
    ];

    // Convert fixes to CSV rows
    const rows = fixes.map((fix) => {
      const tools = (fix.tools_used || []).join('; ');
      const statusChanges = getResourceStatusChange(fix);
      const changes = statusChanges.map(c => `${c.resource}: ${c.before}→${c.after}`).join('; ');
      const beforeMetrics = JSON.stringify(fix.before_metrics || {});
      const afterMetrics = JSON.stringify(fix.after_metrics || {});

      return [
        fix.id || '',
        formatTimestamp(fix.timestamp),
        fix.execution_status || 'PENDING',
        (fix.root_cause || '').replace(/"/g, '""'), // Escape quotes
        (fix.fix_plan?.reasoning || '').replace(/"/g, '""'),
        tools,
        changes,
        beforeMetrics.replace(/"/g, '""'),
        afterMetrics.replace(/"/g, '""'),
      ];
    });

    // Escape CSV values (wrap in quotes if contains comma, quote, or newline)
    const escapeCSV = (value) => {
      if (value === null || value === undefined) return '';
      const str = String(value);
      if (str.includes(',') || str.includes('"') || str.includes('\n')) {
        return `"${str.replace(/"/g, '""')}"`;
      }
      return str;
    };

    // Build CSV content
    const csvContent = [
      headers.map(escapeCSV).join(','),
      ...rows.map(row => row.map(escapeCSV).join(',')),
    ].join('\n');

    // Create blob and download
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    const url = URL.createObjectURL(blob);
    link.setAttribute('href', url);
    link.setAttribute('download', `fix_history_${new Date().toISOString().split('T')[0]}.csv`);
    link.style.visibility = 'hidden';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  if (loading) {
    return (
      <div className="fix-history">
        <div className="history-header">
          <History size={20} />
          <h2>Fix History</h2>
        </div>
        <div className="history-loading">Loading...</div>
      </div>
    );
  }

  return (
    <div className="fix-history">
      <div className="history-header">
        <History size={20} />
        <h2>Fix History</h2>
        <span className="history-count">{fixes.length}</span>
        <div className="history-actions">
          <button 
            className="btn-export-csv" 
            onClick={handleExportCSV}
            disabled={fixes.length === 0}
            title="Export fix history as CSV"
          >
            <Download size={16} />
            Export CSV
          </button>
          <button 
            className="btn-delete-history" 
            onClick={handleDeleteAll}
            disabled={fixes.length === 0}
            title="Delete all fix history"
          >
            <Trash2 size={16} />
            Delete All
          </button>
        </div>
      </div>
      <div className="history-list">
        {fixes.length === 0 ? (
          <div className="history-empty">No fixes yet</div>
        ) : (
          fixes.map((fix) => {
            const statusChanges = getResourceStatusChange(fix);
            const tools = fix.tools_used || [];
            
            return (
              <div
                key={fix.id}
                className={`fix-item ${fix.execution_status?.toLowerCase() || 'unknown'}`}
                onClick={() => setSelectedFix(selectedFix?.id === fix.id ? null : fix)}
              >
                <div className="fix-header">
                  <div className="fix-info">
                    {getStatusIcon(fix.execution_status)}
                    <div>
                      <div className="fix-id">{fix.id}</div>
                      <div className="fix-time">{formatTimestamp(fix.timestamp)}</div>
                    </div>
                  </div>
                  <div className="fix-status" style={{ color: getStatusColor(fix.execution_status) }}>
                    {fix.execution_status || 'PENDING'}
                  </div>
                </div>
                
                {fix.root_cause && (
                  <div className="fix-root-cause">
                    {fix.root_cause.substring(0, 100)}...
                  </div>
                )}
                
                {tools.length > 0 && (
                  <div className="fix-tools">
                    <strong>Tools:</strong>
                    <div className="tools-list">
                      {tools.map((tool, idx) => (
                        <span key={idx} className="tool-tag-small">
                          {tool}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
                
                {statusChanges.length > 0 && (
                  <div className="fix-changes">
                    {statusChanges.map((change, idx) => (
                      <div key={idx} className="status-change">
                        <span className="resource-name">{change.resource}:</span>
                        <span className="status-before">{change.before}</span>
                        <span>→</span>
                        <span className={`status-after ${change.after === 'HEALTHY' ? 'healthy' : 'unhealthy'}`}>
                          {change.after}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
                
                {selectedFix?.id === fix.id && (
                  <div className="fix-details">
                    <div className="detail-section">
                      <strong>Root Cause:</strong>
                      <p>{fix.root_cause || 'N/A'}</p>
                    </div>
                    {fix.fix_plan?.reasoning && (
                      <div className="detail-section">
                        <strong>Reasoning:</strong>
                        <p>{fix.fix_plan.reasoning}</p>
                      </div>
                    )}
                    {fix.tool_results && fix.tool_results.length > 0 && (
                      <div className="detail-section">
                        <strong>Tool Execution:</strong>
                        {fix.tool_results.map((tr, idx) => {
                          const step = tr.step || tr;
                          const result = tr.result || tr;
                          return (
                            <div key={idx} className="tool-execution">
                              <div className="tool-name">{step.tool_name || 'Unknown'}</div>
                              <div className={`tool-result ${result.success ? 'success' : 'failed'}`}>
                                {result.success ? '✓' : '✗'} {result.message || 'Executed'}
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};

export default FixHistory;

