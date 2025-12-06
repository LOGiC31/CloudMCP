import React, { useState } from 'react';
import { Wrench, Database, HardDrive, Server, ChevronDown, ChevronRight } from 'lucide-react';
import './MCPToolsPanel.css';

const MCPToolsPanel = ({ tools, selectedResource }) => {
  const [expandedTools, setExpandedTools] = useState(new Set());
  const getResourceTools = () => {
    if (!selectedResource) {
      return tools;
    }

    const resourceName = selectedResource.name.toLowerCase();
    const resourceType = selectedResource.type ? selectedResource.type.toLowerCase() : '';
    return tools.filter((tool) => {
      const toolName = tool.name.toLowerCase();
      
      // GCP resource matching
      if (resourceType.startsWith('gcp-')) {
        if (resourceType.includes('sql') || resourceName.includes('sql')) {
          return toolName.includes('gcp_sql');
        } else if (resourceType.includes('redis') || resourceName.includes('redis')) {
          return toolName.includes('gcp_redis');
        } else if (resourceType.includes('compute') || resourceName.includes('vm') || resourceName.includes('compute')) {
          return toolName.includes('gcp_compute');
        }
        // For other GCP resources, show all GCP tools
        return toolName.startsWith('gcp_');
      }
      
      // Local resource matching
      if (resourceName.includes('postgres') || resourceName.includes('database')) {
        return toolName.includes('postgres');
      } else if (resourceName.includes('redis')) {
        return toolName.includes('redis');
      } else if (resourceName.includes('nginx')) {
        return toolName.includes('nginx');
      } else if (resourceName.includes('docker')) {
        return toolName.includes('docker');
      }
      return true;
    });
  };

  const getToolIcon = (toolName) => {
    if (toolName.includes('postgres') || toolName.includes('sql')) {
      return <Database size={18} />;
    } else if (toolName.includes('redis')) {
      return <HardDrive size={18} />;
    } else if (toolName.includes('nginx')) {
      return <Server size={18} />;
    } else if (toolName.includes('docker') || toolName.includes('compute')) {
      return <Server size={18} />;
    }
    return <Wrench size={18} />;
  };

  const toggleTool = (toolName) => {
    setExpandedTools(prev => {
      const newSet = new Set(prev);
      if (newSet.has(toolName)) {
        newSet.delete(toolName);
      } else {
        newSet.add(toolName);
      }
      return newSet;
    });
  };

  const filteredTools = getResourceTools();

  return (
    <div className="mcp-tools-panel">
      <div className="tools-header">
        <Wrench size={20} />
        <h2>MCP Tools</h2>
        {selectedResource && (
          <span className="tools-filter">
            ({filteredTools.length} for {selectedResource.name})
          </span>
        )}
      </div>
      <div className="tools-list">
        {filteredTools.length === 0 ? (
          <div className="tools-empty">
            {selectedResource
              ? `No tools available for ${selectedResource.name}`
              : 'Select a resource to see available tools'}
          </div>
        ) : (
          filteredTools.map((tool, index) => {
            const isExpanded = expandedTools.has(tool.name);
            return (
              <div key={index} className={`tool-card ${isExpanded ? 'expanded' : ''}`}>
                <div 
                  className="tool-header-clickable"
                  onClick={() => toggleTool(tool.name)}
                >
                  <div className="tool-header-left">
                    <div className="tool-expand-icon">
                      {isExpanded ? <ChevronDown size={18} /> : <ChevronRight size={18} />}
                    </div>
                    <div className="tool-icon">{getToolIcon(tool.name)}</div>
                    <h3 className="tool-name">{tool.name}</h3>
                  </div>
                </div>
                {isExpanded && (
                  <div className="tool-details">
                    <p className="tool-description">{tool.description}</p>
                    {tool.parameters && Object.keys(tool.parameters).length > 0 && (
                      <div className="tool-parameters">
                        <strong>Parameters:</strong>
                        <div className="parameters-list">
                          {Object.entries(tool.parameters).map(([key, param]) => (
                            <div key={key} className="parameter-item">
                              <code>{key}</code>
                              <span className="parameter-type">{param.type || 'any'}</span>
                              {param.required && <span className="parameter-required">required</span>}
                            </div>
                          ))}
                        </div>
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

export default MCPToolsPanel;

