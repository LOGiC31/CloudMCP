import React from 'react';
import { Cpu, Zap, RefreshCw } from 'lucide-react';
import './Header.css';

const Header = ({ onRefresh }) => {
  return (
    <header className="header">
      <div className="header-content">
        <div className="header-logo">
          <div className="logo-icon">
            <Cpu size={28} />
            <div className="logo-pulse"></div>
          </div>
          <div className="logo-text">
            <h1>Infra Orchestrator</h1>
            <span className="logo-subtitle">AI-Powered Infrastructure Management</span>
          </div>
        </div>
        <div className="header-actions">
          {onRefresh && (
            <button 
              className="refresh-button" 
              onClick={onRefresh}
              title="Refresh resources list and tools"
            >
              <RefreshCw size={18} />
              <span>Refresh</span>
            </button>
          )}
          <div className="header-status">
            <Zap size={20} />
            <span>System Operational</span>
          </div>
        </div>
      </div>
    </header>
  );
};

export default Header;

