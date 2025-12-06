import React from 'react';
import { Cpu, Zap } from 'lucide-react';
import './Header.css';

const Header = () => {
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
        <div className="header-status">
          <Zap size={20} />
          <span>System Operational</span>
        </div>
      </div>
    </header>
  );
};

export default Header;

