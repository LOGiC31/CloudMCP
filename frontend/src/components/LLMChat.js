import React, { useState, useEffect, useRef } from 'react';
import { Send, Bot, User, Wrench, Loader, CheckCircle, XCircle } from 'lucide-react';
import { fixService } from '../services/api';
import './LLMChat.css';

const LLMChat = ({ selectedResource, onFixTriggered, degradedResources = [], resources = [], fixTriggered = false }) => {
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const chatEndRef = useRef(null);

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const scrollToBottom = () => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const handleTriggerFix = async () => {
    setLoading(true);
    const userMessage = {
      type: 'user',
      content: 'Triggering LLM fix for infrastructure issues...',
      timestamp: new Date(),
    };
    setMessages((prev) => [...prev, userMessage]);

    try {
      // Notify parent that fix is starting (this will stop status polling)
      onFixTriggered();
      
      // Trigger fix
      const fixResponse = await fixService.trigger();
      const fixId = fixResponse.data.id;

      // Add system message
      const systemMessage = {
        type: 'system',
        content: `Fix triggered: ${fixId}`,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, systemMessage]);

      // Poll for fix completion
      const fixExecutionStatus = await pollFixStatus(fixId);
      
      // After fix completes (SUCCESS, FAILED, TIMEOUT, or ERROR), notify parent to check status and resume polling
      // onFixTriggered() was already called at the start to stop polling
      // Now we need to check status and resume polling regardless of success/failure
      // Always call onFixTriggered with execution status to mark fix as completed and resume polling
      const finalStatus = fixExecutionStatus || 'UNKNOWN';
      console.log('[LLMChat] Fix polling completed with status:', finalStatus);
      onFixTriggered(finalStatus);
    } catch (error) {
      const errorMessage = {
        type: 'error',
        content: `Failed to trigger fix: ${error.message}`,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMessage]);
      
      // Even on error, notify parent to resume polling
      onFixTriggered('ERROR');
    } finally {
      setLoading(false);
    }
  };

  const pollFixStatus = async (fixId) => {
    const maxAttempts = 30;
    let attempts = 0;
    const processedToolMessages = new Set();
    let fixExecutionStatus = null; // Track execution status (SUCCESS, FAILED, or null)

    const poll = async () => {
      try {
        const response = await fixService.getById(fixId);
        const fix = response.data;

        // Handle fix_plan from fix_applied or fix_plan field
        const fixPlan = fix.fix_plan || (fix.fix_applied && { 
          root_cause: fix.root_cause,
          steps: fix.fix_applied 
        });

        if (fixPlan) {
          // Get tools from multiple possible locations
          const tools = fix.tools_used || 
                       fixPlan.tools_to_use || 
                       (fixPlan.steps && fixPlan.steps.map(s => s.tool_name)) ||
                       (fix.fix_applied && fix.fix_applied.map(f => f.tool_name)) ||
                       [];
          
          const planMessage = {
            type: 'llm',
            content: fixPlan.root_cause || fix.root_cause || 'Analyzing infrastructure issues...',
            reasoning: fixPlan.reasoning || '',
            tools: Array.isArray(tools) ? tools : [],
            timestamp: new Date(),
          };
          setMessages((prev) => {
            // Avoid duplicates
            const exists = prev.some((m) => m.type === 'llm' && m.content === planMessage.content);
            if (exists) return prev;
            return [...prev, planMessage];
          });
        }

        // Handle tool_results - can be direct array or in attempts
        let toolResults = fix.tool_results;
        if (!toolResults && fix.attempts && fix.attempts.length > 0) {
          // Get tool_results from latest attempt
          const latestAttempt = fix.attempts[fix.attempts.length - 1];
          toolResults = latestAttempt.tool_results || [];
        }

        if (toolResults && Array.isArray(toolResults)) {
          toolResults.forEach((toolResult) => {
            // Handle both formats: {step: {...}, result: {...}} and direct tool_result format
            const step = toolResult.step || toolResult;
            const result = toolResult.result || toolResult;
            
            const toolName = step?.tool_name || toolResult.tool_name;
            const messageKey = `${toolName}-${result?.timestamp || Date.now()}`;
            
            if (!processedToolMessages.has(messageKey)) {
              processedToolMessages.add(messageKey);
              
              const toolMessage = {
                type: 'tool',
                toolName: toolName,
                success: result?.success !== false,
                message: result?.message || 'Tool executed',
                timestamp: new Date(result?.timestamp || Date.now()),
              };
              
              setMessages((prev) => [...prev, toolMessage]);
            }
          });
        }

        // Check if complete (SUCCESS or FAILED)
        if (fix.execution_status && fix.execution_status !== 'PENDING') {
          fixExecutionStatus = fix.execution_status; // Store status for return value
          console.log('[LLMChat] Fix execution completed with status:', fixExecutionStatus);
          
          const statusMessage = {
            type: 'system',
            content: `Fix ${fix.execution_status}: ${fix.execution_status === 'SUCCESS' ? 'All issues resolved' : 'Some issues remain'}`,
            status: fix.execution_status,
            timestamp: new Date(),
          };
          setMessages((prev) => {
            const exists = prev.some((m) => m.type === 'system' && m.status === statusMessage.status);
            if (exists) return prev;
            return [...prev, statusMessage];
          });
          
          return; // Exit polling - fix is complete (SUCCESS or FAILED)
        }

        attempts++;
        if (attempts < maxAttempts) {
          setTimeout(poll, 2000);
        } else {
          // Timeout reached - fix may still be pending, but we'll treat it as done
          fixExecutionStatus = 'TIMEOUT';
          console.log('[LLMChat] Fix polling timed out after', maxAttempts, 'attempts');
          return;
        }
      } catch (error) {
        console.error('[LLMChat] Error polling fix status:', error);
        attempts++;
        if (attempts < maxAttempts) {
          setTimeout(poll, 2000);
        } else {
          // Timeout on error - treat as done
          fixExecutionStatus = 'ERROR';
          console.log('[LLMChat] Fix polling failed after', maxAttempts, 'attempts');
          return;
        }
      }
    };

    await poll();
    // Return execution status (SUCCESS, FAILED, TIMEOUT, ERROR, or null)
    return fixExecutionStatus;
  };

  const formatMessage = (message) => {
    switch (message.type) {
      case 'user':
        return (
          <div className="message user-message">
            <div className="message-avatar">
              <User size={20} />
            </div>
            <div className="message-content">
              <div className="message-text">{message.content}</div>
              <div className="message-time">{formatTime(message.timestamp)}</div>
            </div>
          </div>
        );
      case 'llm':
        return (
          <div className="message llm-message">
            <div className="message-avatar">
              <Bot size={20} />
            </div>
            <div className="message-content">
              <div className="message-header">
                <strong>LLM Analysis</strong>
              </div>
              <div className="message-text">{message.content}</div>
              {message.reasoning && (
                <div className="message-reasoning">
                  <strong>Reasoning:</strong> {message.reasoning}
                </div>
              )}
              {message.tools && message.tools.length > 0 && (
                <div className="message-tools">
                  <strong>MCP Tools Selected:</strong>
                  <div className="tools-list">
                    {message.tools.map((tool, idx) => (
                      <span key={idx} className="tool-tag">
                        {tool}
                      </span>
                    ))}
                  </div>
                </div>
              )}
              {(!message.tools || message.tools.length === 0) && (
                <div className="message-tools">
                  <strong>MCP Tools Selected:</strong>
                  <div className="tools-list">
                    <span className="tool-tag" style={{ opacity: 0.5 }}>
                      No tools specified yet
                    </span>
                  </div>
                </div>
              )}
              <div className="message-time">{formatTime(message.timestamp)}</div>
            </div>
          </div>
        );
      case 'tool':
        return (
          <div className="message tool-message">
            <div className="message-avatar">
              <Wrench size={20} />
            </div>
            <div className="message-content">
              <div className="message-header">
                <strong>MCP Tool Execution</strong>
                {message.success ? (
                  <CheckCircle size={16} className="tool-success" />
                ) : (
                  <XCircle size={16} className="tool-failed" />
                )}
              </div>
              <div className="message-text">
                <span className="tool-name-highlight">{message.toolName}</span>
                <span className="tool-message-text">: {message.message}</span>
              </div>
              <div className="message-time">{formatTime(message.timestamp)}</div>
            </div>
          </div>
        );
      case 'system':
        return (
          <div className={`message system-message ${message.status?.toLowerCase()}`}>
            <div className="message-content">
              <div className="message-text">{message.content}</div>
              <div className="message-time">{formatTime(message.timestamp)}</div>
            </div>
          </div>
        );
      case 'error':
        return (
          <div className="message error-message">
            <div className="message-content">
              <div className="message-text">{message.content}</div>
              <div className="message-time">{formatTime(message.timestamp)}</div>
            </div>
          </div>
        );
      default:
        return null;
    }
  };

  const formatTime = (timestamp) => {
    return new Date(timestamp).toLocaleTimeString();
  };

  return (
    <div className="llm-chat">
      <div className="chat-header">
        <Bot size={20} />
        <h2>LLM Fix Orchestrator</h2>
      </div>
      <div className="chat-messages">
        {messages.length === 0 && (
          <div className="chat-empty">
            <Bot size={48} />
            <p>No interactions yet. Trigger a fix to see LLM analysis and tool execution.</p>
          </div>
        )}
        {messages.map((message, index) => (
          <div key={index} className="message-wrapper">
            {formatMessage(message)}
          </div>
        ))}
        {loading && (
          <div className="message loading-message">
            <div className="message-avatar">
              <Loader size={20} className="spinning" />
            </div>
            <div className="message-content">
              <div className="message-text">Processing fix...</div>
            </div>
          </div>
        )}
        <div ref={chatEndRef} />
      </div>
      <div className="chat-input">
        <button
          className="btn-trigger"
          onClick={handleTriggerFix}
          disabled={loading || fixTriggered}
        >
          <Send size={18} />
          {(() => {
            // Check actual current resource status, not just validation state
            const currentDegraded = resources.filter(r => 
              (r.status === 'DEGRADED' || r.status === 'FAILED') && 
              !fixTriggered // Don't show button text if fix already triggered
            );
            
            if (fixTriggered) {
              return '⏳ Fix in Progress...';
            } else if (currentDegraded.length > 0) {
              const resourceNames = currentDegraded.map(r => 
                r.name.charAt(0).toUpperCase() + r.name.slice(1)
              );
              return `🔧 Auto-Fix ${resourceNames.join(' & ')}`;
            } else if (degradedResources.length > 0) {
              // Fallback to validation state if resources haven't updated yet
              return `🔧 Auto-Fix ${degradedResources.map(r => r.charAt(0).toUpperCase() + r.slice(1)).join(' & ')}`;
            } else {
              return '🚀 Trigger LLM Fix Orchestrator';
            }
          })()}
        </button>
      </div>
    </div>
  );
};

export default LLMChat;

