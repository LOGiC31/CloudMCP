# Implementation Plan: MCP-Enabled Infrastructure Orchestration System

## Table of Contents
1. [System Architecture](#system-architecture)
2. [Technology Stack](#technology-stack)
3. [Project Structure](#project-structure)
4. [Component Design](#component-design)
5. [Data Models](#data-models)
6. [API Interfaces](#api-interfaces)
7. [Implementation Phases](#implementation-phases)
8. [UI/UX Design](#uiux-design)
9. [Testing Strategy](#testing-strategy)

---

## System Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Web Dashboard (UI)                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │Resources │  │  Logs    │  │   LLM    │  │  Fix     │   │
│  │  View    │  │  View    │  │Interact. │  │  Button  │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
└───────────────────────┬─────────────────────────────────────┘
                        │ HTTP/REST API
┌───────────────────────┴─────────────────────────────────────┐
│              Orchestration Service (Backend)                 │
│  ┌──────────────────────────────────────────────────────┐  │
│  │         MCP Orchestrator (Core Controller)           │  │
│  └──────────────────────────────────────────────────────┘  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │ Log          │  │ LLM          │  │ MCP Tools    │    │
│  │ Accumulator  │  │ Interaction  │  │ Manager      │    │
│  └──────────────┘  └──────────────┘  └──────────────┘    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │ Resource     │  │ Evaluation   │  │ State        │    │
│  │ Monitor      │  │ Store        │  │ Manager      │    │
│  └──────────────┘  └──────────────┘  └──────────────┘    │
└───────────────────────┬─────────────────────────────────────┘
                        │
        ┌───────────────┼───────────────┐
        │               │               │
┌───────▼──────┐ ┌──────▼──────┐ ┌──────▼──────┐
│   Docker     │ │  PostgreSQL │ │    Redis    │
│  Application │ │  Database   │ │    Cache    │
└──────────────┘ └─────────────┘ └─────────────┘
```

### Phase 1 (Local) Architecture

- **Sample Application**: Docker containerized app (e.g., Flask/FastAPI)
- **Database**: PostgreSQL in Docker
- **Cache**: Redis in Docker
- **Monitoring**: Docker stats, container logs, DB metrics, Redis metrics
- **MCP Tools**: CLI wrappers for Docker, PostgreSQL, Redis operations

### Phase 2 (Cloud) Architecture

- **Sample Application**: Deployed on GCP Compute Engine
- **Database**: Cloud SQL (PostgreSQL)
- **Cache**: Redis on Compute Engine or Memorystore
- **Monitoring**: GCP Monitoring APIs, Cloud Logging
- **MCP Tools**: GCP API wrappers for Compute Engine, Cloud SQL, Cloud Storage

---

## Technology Stack

### Backend
- **Language**: Python 3.11+
- **Framework**: FastAPI (REST API + WebSocket for real-time updates)
- **LLM Integration**: Google Gemini API (`google-generativeai`)
- **MCP SDK**: `mcp` Python SDK (or custom implementation)
- **Database**: SQLite (for evaluation data) + PostgreSQL (sample app)
- **Cache**: Redis (sample app)
- **Container Management**: Docker SDK for Python (`docker`)
- **Cloud Integration**: Google Cloud SDK (`google-cloud-compute`, `google-cloud-sql`, etc.)
- **Logging**: Python `logging` + structured logging
- **Task Queue**: Celery (optional, for async operations)

### Frontend
- **Framework**: React 18+ with TypeScript
- **UI Library**: Material-UI (MUI) or Tailwind CSS + shadcn/ui
- **State Management**: React Query / TanStack Query
- **Real-time**: WebSocket client
- **Charts**: Recharts or Chart.js
- **HTTP Client**: Axios

### Infrastructure
- **Containerization**: Docker & Docker Compose
- **Orchestration**: Docker Compose (Phase 1)
- **Cloud**: Google Cloud Platform (Phase 2)

### Development Tools
- **Package Management**: Poetry or uv
- **Code Quality**: Black, Ruff, mypy
- **Testing**: pytest, pytest-asyncio
- **API Documentation**: FastAPI auto-generated docs

---

## Project Structure

```
project/
├── README.md
├── IMPLEMENTATION_PLAN.md
├── proposal.md
├── instructions.txt
├── pyproject.toml              # Python dependencies
├── docker-compose.yml          # Local infrastructure
├── .env.example                # Environment variables template
├── .gitignore
│
├── backend/
│   ├── __init__.py
│   ├── main.py                 # FastAPI application entry
│   ├── config.py               # Configuration management
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── routes/
│   │   │   ├── __init__.py
│   │   │   ├── resources.py   # Resource status endpoints
│   │   │   ├── logs.py        # Log viewing endpoints
│   │   │   ├── llm.py         # LLM interaction endpoints
│   │   │   └── fixes.py       # Fix trigger endpoint
│   │   └── websocket.py       # WebSocket for real-time updates
│   │
│   ├── core/
│   │   ├── __init__.py
│   │   ├── orchestrator.py    # Main MCP orchestrator
│   │   ├── llm_client.py      # Gemini API client
│   │   └── state_manager.py   # System state management
│   │
│   ├── mcp/
│   │   ├── __init__.py
│   │   ├── server.py          # MCP server implementation
│   │   ├── tools/
│   │   │   ├── __init__.py
│   │   │   ├── base.py        # Base tool interface
│   │   │   ├── docker_tools.py    # Docker CLI wrappers
│   │   │   ├── postgres_tools.py  # PostgreSQL tools
│   │   │   ├── redis_tools.py     # Redis tools
│   │   │   └── gcp_tools.py       # GCP API wrappers (Phase 2)
│   │   └── registry.py        # Tool registry
│   │
│   ├── monitoring/
│   │   ├── __init__.py
│   │   ├── log_accumulator.py # Log collection and aggregation
│   │   ├── resource_monitor.py # Resource status monitoring
│   │   ├── collectors/
│   │   │   ├── __init__.py
│   │   │   ├── docker_collector.py
│   │   │   ├── postgres_collector.py
│   │   │   ├── redis_collector.py
│   │   │   └── gcp_collector.py   # Phase 2
│   │   └── metrics.py         # Metrics aggregation
│   │
│   ├── evaluation/
│   │   ├── __init__.py
│   │   ├── store.py           # Evaluation data storage
│   │   └── models.py          # Evaluation data models
│   │
│   └── utils/
│       ├── __init__.py
│       ├── logger.py          # Logging utilities
│       └── exceptions.py      # Custom exceptions
│
├── frontend/
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   ├── index.html
│   │
│   ├── src/
│   │   ├── main.tsx
│   │   ├── App.tsx
│   │   │
│   │   ├── components/
│   │   │   ├── Layout/
│   │   │   │   ├── Navbar.tsx
│   │   │   │   └── Sidebar.tsx
│   │   │   ├── Resources/
│   │   │   │   ├── ResourceCard.tsx
│   │   │   │   ├── ResourceList.tsx
│   │   │   │   └── ResourceStatus.tsx
│   │   │   ├── Logs/
│   │   │   │   ├── LogViewer.tsx
│   │   │   │   └── LogFilter.tsx
│   │   │   ├── LLM/
│   │   │   │   ├── LLMInteractionList.tsx
│   │   │   │   ├── LLMInteractionDetail.tsx
│   │   │   │   └── FixButton.tsx
│   │   │   └── Dashboard/
│   │   │       ├── MetricsChart.tsx
│   │   │       └── StatusOverview.tsx
│   │   │
│   │   ├── pages/
│   │   │   ├── Dashboard.tsx
│   │   │   ├── Resources.tsx
│   │   │   ├── Logs.tsx
│   │   │   └── LLMInteractions.tsx
│   │   │
│   │   ├── services/
│   │   │   ├── api.ts          # API client
│   │   │   └── websocket.ts    # WebSocket client
│   │   │
│   │   ├── hooks/
│   │   │   ├── useResources.ts
│   │   │   ├── useLogs.ts
│   │   │   └── useLLMInteractions.ts
│   │   │
│   │   └── types/
│   │       └── index.ts        # TypeScript types
│   │
│   └── public/
│
├── sample-app/                 # Sample application for testing
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── app.py                  # Flask/FastAPI app
│   ├── models.py               # Database models
│   └── load_generator.py       # Script to generate load/failures
│
├── tests/
│   ├── __init__.py
│   ├── test_orchestrator.py
│   ├── test_mcp_tools.py
│   ├── test_llm_client.py
│   └── integration/
│       └── test_fix_flow.py
│
└── docs/
    ├── API.md
    ├── MCP_TOOLS.md
    └── DEPLOYMENT.md
```

---

## Component Design

### 1. MCP Orchestrator (Core)

**File**: `backend/core/orchestrator.py`

**Responsibilities**:
- Coordinate between log accumulator, LLM client, and MCP tools
- Manage fix workflow: detect → analyze → fix → verify
- Maintain system state
- Handle user-triggered fix requests

**Key Methods**:
```python
class MCPOrchestrator:
    async def trigger_fix(failure_context: FailureContext) -> FixResult
    async def analyze_failure(logs: List[Log], config: AppConfig) -> AnalysisResult
    async def execute_fix(fix_plan: FixPlan) -> FixResult
    async def verify_fix(fix_result: FixResult) -> VerificationResult
```

### 2. Log Accumulator

**File**: `backend/monitoring/log_accumulator.py`

**Responsibilities**:
- Collect logs from Docker containers, PostgreSQL, Redis
- Aggregate and structure log data
- Detect error patterns
- Provide log context to orchestrator

**Key Methods**:
```python
class LogAccumulator:
    async def collect_logs(resource_type: str, resource_id: str) -> List[Log]
    async def get_error_logs(time_range: TimeRange) -> List[Log]
    async def get_application_config() -> AppConfig
```

### 3. LLM Interaction Module

**File**: `backend/core/llm_client.py`

**Responsibilities**:
- Interface with Gemini API
- Format prompts with logs, config, and available tools
- Parse LLM responses to extract fix plans
- Store interaction history

**Key Methods**:
```python
class LLMClient:
    async def analyze_and_plan(
        logs: List[Log],
        config: AppConfig,
        available_tools: List[MCPTool]
    ) -> FixPlan
    async def get_interaction_history() -> List[LLMInteraction]
```

### 4. MCP Tools Manager

**File**: `backend/mcp/tools/`

**Responsibilities**:
- Register and manage MCP tools
- Execute tool calls (CLI or API)
- Provide tool metadata to LLM
- Handle tool errors

**Tool Categories**:
- **Docker Tools**: `docker_restart`, `docker_scale`, `docker_logs`, `docker_stats`
- **PostgreSQL Tools**: `pg_restart`, `pg_scale_connections`, `pg_vacuum`, `pg_analyze`
- **Redis Tools**: `redis_flush`, `redis_restart`, `redis_memory_purge`
- **GCP Tools** (Phase 2): `gcp_scale_instance`, `gcp_restart_instance`, `gcp_modify_db`, etc.

**Tool Interface**:
```python
class MCPTool:
    name: str
    description: str
    parameters: Dict[str, Any]
    
    async def execute(params: Dict[str, Any]) -> ToolResult
```

### 5. Resource Monitor

**File**: `backend/monitoring/resource_monitor.py`

**Responsibilities**:
- Monitor Docker containers, PostgreSQL, Redis status
- Collect metrics (CPU, memory, disk, network)
- Detect resource issues
- Provide real-time status to UI

**Key Methods**:
```python
class ResourceMonitor:
    async def get_resource_status(resource_id: str) -> ResourceStatus
    async def get_all_resources() -> List[ResourceStatus]
    async def get_metrics(resource_id: str, time_range: TimeRange) -> Metrics
```

### 6. Evaluation Store

**File**: `backend/evaluation/store.py`

**Responsibilities**:
- Store fix attempts: root cause, fix applied, before/after metrics
- Track success/failure rates
- Provide evaluation data for analysis

**Data Model**:
```python
class FixEvaluation:
    id: str
    timestamp: datetime
    root_cause: str
    fix_applied: str
    tools_used: List[str]
    before_metrics: Dict[str, Any]
    after_metrics: Dict[str, Any]
    success: bool
    llm_interaction_id: str
```

---

## Data Models

### Core Models

```python
# Resource Status
class ResourceStatus:
    id: str
    name: str
    type: ResourceType  # DOCKER, POSTGRES, REDIS, GCP_INSTANCE, etc.
    status: Status  # HEALTHY, DEGRADED, FAILED, UNKNOWN
    metrics: Metrics
    last_updated: datetime

# Log Entry
class Log:
    id: str
    timestamp: datetime
    resource_id: str
    level: LogLevel  # INFO, WARNING, ERROR, CRITICAL
    message: str
    metadata: Dict[str, Any]

# Failure Context
class FailureContext:
    logs: List[Log]
    resource_status: List[ResourceStatus]
    app_config: AppConfig
    detected_at: datetime

# Fix Plan (from LLM)
class FixPlan:
    root_cause: str
    reasoning: str
    steps: List[FixStep]
    tools_to_use: List[str]

class FixStep:
    tool_name: str
    parameters: Dict[str, Any]
    description: str

# Fix Result
class FixResult:
    id: str
    fix_plan: FixPlan
    execution_status: ExecutionStatus  # SUCCESS, FAILED, PARTIAL
    tool_results: List[ToolResult]
    before_metrics: Dict[str, Any]
    after_metrics: Dict[str, Any]
    timestamp: datetime

# LLM Interaction
class LLMInteraction:
    id: str
    timestamp: datetime
    prompt: str
    response: str
    fix_plan: Optional[FixPlan]
    tokens_used: int
    duration_ms: int
```

---

## API Interfaces

### REST API Endpoints

#### Resources
- `GET /api/resources` - Get all resources and their status
- `GET /api/resources/{resource_id}` - Get specific resource status
- `GET /api/resources/{resource_id}/metrics` - Get resource metrics

#### Logs
- `GET /api/logs` - Get logs (with filters: level, resource, time_range)
- `GET /api/logs/errors` - Get error logs only
- `GET /api/logs/{log_id}` - Get specific log entry

#### LLM Interactions
- `GET /api/llm/interactions` - Get all LLM interactions
- `GET /api/llm/interactions/{interaction_id}` - Get specific interaction
- `POST /api/llm/analyze` - Trigger LLM analysis (manual)

#### Fixes
- `POST /api/fixes/trigger` - User-triggered fix
  ```json
  {
    "failure_context": {
      "resource_ids": ["..."],
      "time_range": {...}
    }
  }
  ```
- `GET /api/fixes` - Get all fix attempts
- `GET /api/fixes/{fix_id}` - Get specific fix result
- `GET /api/fixes/evaluations` - Get evaluation data

#### WebSocket
- `WS /ws` - Real-time updates for resources, logs, fixes

---

## Implementation Phases

### Phase 1: Foundation (Week 1)

**Tasks**:
1. Set up project structure
2. Initialize FastAPI backend with basic routes
3. Set up React frontend with routing
4. Create Docker Compose for sample app (PostgreSQL + Redis)
5. Implement basic log accumulator (Docker logs)
6. Set up Gemini API client
7. Create basic MCP tool interface

**Deliverables**:
- Working backend API
- Basic UI with resource view
- Sample app running in Docker
- Log collection working

### Phase 2: Core Functionality (Week 2)

**Tasks**:
1. Implement MCP orchestrator core logic
2. Create MCP tools for Docker, PostgreSQL, Redis
3. Implement LLM interaction module with prompt engineering
4. Build log accumulator with error detection
5. Implement resource monitor
6. Create fix workflow: analyze → plan → execute → verify
7. Build evaluation store

**Deliverables**:
- Complete fix workflow working
- MCP tools functional
- LLM can analyze and create fix plans
- Evaluation data being stored

### Phase 3: UI & Integration (Week 3)

**Tasks**:
1. Build comprehensive UI dashboard
2. Implement real-time updates via WebSocket
3. Create LLM interaction viewer
4. Add fix trigger button and workflow
5. Implement log viewer with filters
6. Add metrics visualization
7. Create failure simulation scripts
8. End-to-end testing

**Deliverables**:
- Complete UI with all views
- User can trigger fixes from UI
- Real-time status updates
- Failure simulation working

### Phase 4: Cloud Integration (Week 4-5)

**Tasks**:
1. Set up GCP project and credentials
2. Deploy sample app to GCP Compute Engine
3. Set up Cloud SQL (PostgreSQL)
4. Implement GCP resource monitor
5. Create GCP MCP tools
6. Integrate GCP APIs into orchestrator
7. Update UI for cloud resources
8. Test cloud fix workflow

**Deliverables**:
- Sample app running on GCP
- Cloud resource monitoring working
- GCP MCP tools functional
- Cloud fixes working

### Phase 5: Testing & Documentation (Week 6)

**Tasks**:
1. Comprehensive testing (unit, integration, end-to-end)
2. Failure scenario testing
3. Performance testing
4. Documentation (API, deployment, usage)
5. Evaluation data collection and analysis
6. Demo preparation

**Deliverables**:
- Test suite complete
- Documentation complete
- Evaluation results
- Demo ready

---

## UI/UX Design

### Dashboard Layout

```
┌─────────────────────────────────────────────────────────┐
│  Logo  │  Dashboard  │  Resources  │  Logs  │  LLM     │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐   │
│  │   Status    │  │   Metrics   │  │  Recent     │   │
│  │  Overview   │  │   Charts    │  │  Fixes      │   │
│  └─────────────┘  └─────────────┘  └─────────────┘   │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### Resources View

- **Resource Cards**: Each resource (Docker container, DB, Redis) as a card
- **Status Indicators**: Color-coded (green/yellow/red)
- **Metrics Display**: CPU, memory, disk usage
- **Actions**: View logs, view details

### Logs View

- **Log Table**: Timestamp, level, resource, message
- **Filters**: Level, resource, time range
- **Search**: Full-text search
- **Error Highlighting**: Red for errors/critical

### LLM Interactions View

- **Interaction List**: Timestamp, status, root cause summary
- **Interaction Detail**: 
  - Full prompt and response
  - Fix plan visualization
  - Tools used
  - Execution results
- **Fix Button**: Prominent button to trigger fix

### Design Principles

- **Modern & Clean**: Material Design or similar
- **Real-time Updates**: WebSocket for live data
- **Responsive**: Works on desktop and tablet
- **Accessible**: WCAG 2.1 AA compliance
- **Dark Mode**: Optional dark theme

---

## Testing Strategy

### Unit Tests

- MCP tools execution
- LLM client prompt formatting and response parsing
- Log accumulator logic
- Resource monitor collectors
- Evaluation store operations

### Integration Tests

- Orchestrator workflow (analyze → fix → verify)
- MCP tool execution with real Docker/PostgreSQL/Redis
- LLM interaction end-to-end
- API endpoints

### End-to-End Tests

- Complete fix workflow from UI trigger
- Failure simulation → detection → fix → verification
- Real-time updates in UI
- Evaluation data collection

### Failure Scenarios

1. **Database Connection Pool Exhaustion**
   - Simulate: High concurrent connections
   - Expected Fix: Increase connection pool, restart DB

2. **Redis Memory Full**
   - Simulate: Fill Redis with data
   - Expected Fix: Flush cache, increase memory limit

3. **Application Container Crash**
   - Simulate: Kill container process
   - Expected Fix: Restart container

4. **High CPU/Memory Usage**
   - Simulate: CPU/memory intensive operations
   - Expected Fix: Scale containers, optimize queries

5. **Database Query Timeout**
   - Simulate: Long-running queries
   - Expected Fix: Kill long queries, optimize indexes

---

## Sample Application Choice

**Recommended**: **E-commerce API** (Flask/FastAPI)

**Why**:
- Realistic workload patterns
- Database-heavy operations (products, orders, users)
- Cache usage (product listings, user sessions)
- Easy to simulate failures:
  - High traffic → DB connection exhaustion
  - Large product catalog → Redis memory full
  - Complex queries → DB timeouts
  - Concurrent orders → Deadlocks

**Features**:
- Product catalog (PostgreSQL)
- Shopping cart (Redis)
- User authentication
- Order processing
- Load generator script

**Alternative**: **Blog Platform** or **Task Management System**

---

## Next Steps

1. **Review and approve this plan**
2. **Set up development environment**
3. **Initialize project structure**
4. **Start Phase 1 implementation**

---

## Notes

- Keep resources minimal initially (1 app container, 1 DB, 1 Redis)
- Focus on core fix workflow first, then add advanced features
- Store all LLM interactions for evaluation
- Make UI user-friendly for testing and demos
- Document all MCP tools with clear descriptions for LLM


