# LLM-Driven Infrastructure Orchestration System

An intelligent infrastructure orchestration system that leverages Large Language Models (LLMs) and the Model Context Protocol (MCP) to autonomously detect, analyze, and remediate infrastructure failures across both local and cloud environments.

## Overview

This system demonstrates the practical application of LLM reasoning for infrastructure management, achieving a **100% success rate** in automated failure detection and remediation. It supports both local Docker environments and Google Cloud Platform (GCP) with a unified interface.

### Key Achievements

- ✅ **100% Test Success Rate** (4/4 test scenarios passed)
- 🎯 **Autonomous Failure Detection** with real-time monitoring and application-level metrics
- 🤖 **LLM-Powered Analysis** using Google's Gemini API for intelligent failure analysis
- 🔧 **20+ MCP Tools** for infrastructure operations across Docker, PostgreSQL, Redis, Nginx, and GCP
- ☁️ **Multi-Environment Support** for local Docker and GCP cloud resources
- 📊 **Comprehensive Evaluation** with detailed metrics and reporting

### Test Results

| Environment | Test Scenario                  | Status  | Duration |
| ----------- | ------------------------------ | ------- | -------- |
| GCP         | Redis Memory Pressure          | ✅ PASS | 316.43s  |
| GCP         | Compute Engine Memory Pressure | ✅ PASS | 277.52s  |
| Local       | Redis Memory Pressure          | ✅ PASS | 232.13s  |
| Local       | PostgreSQL Connection Overload | ✅ PASS | 217.22s  |

## Features

- **Autonomous Failure Detection**: Real-time monitoring of infrastructure resources with application-level health checks (CPU, memory, connections, disk)
- **LLM-Powered Analysis**: Context-aware failure analysis using Gemini API for root cause identification and fix plan generation
- **Automated Remediation**: Automatic tool execution with proper sequencing, status verification, and retry mechanisms
- **Multi-Environment Support**: Unified interface for local Docker containers and GCP resources (Compute Engine, Cloud SQL, Memorystore)
- **MCP Tool Integration**: 20+ MCP tools for infrastructure operations with async execution and error handling
- **Evaluation & Reporting**: Comprehensive tracking of before/after metrics, LLM reasoning, and tool execution results
- **Web Dashboard**: Modern React UI for resource visualization, real-time status updates, and interactive fix triggering

## Architecture

The system consists of a React frontend, FastAPI backend, LLM client (Gemini API), MCP tools registry, and monitoring system. The orchestrator coordinates failure detection, LLM interactions, fix plan execution, and status verification.

**Key Components:**
- **Frontend**: React.js dashboard with real-time status polling and interactive fix triggering
- **Backend API**: FastAPI server with async operations, parallel resource monitoring, and optimized polling
- **Orchestrator**: Core logic for failure detection, LLM interaction management, retry logic (max 2 retries), and tool execution coordination
- **LLM Client**: Google Gemini API integration (`gemini-2.5-pro` or `gemini-2.5-flash`) with structured prompts and response parsing
- **MCP Tools**: 20+ tools for Docker, PostgreSQL, Redis, Nginx, and GCP services
- **Monitoring**: Real-time resource monitoring with application-level metrics and log aggregation

## Setup

### Prerequisites

- Python 3.11+
- Docker and Docker Compose
- Google Gemini API key
- (Optional) GCP account with service account key for cloud resources

### Installation

1. **Clone the repository**

2. **Install Python dependencies**:

```bash
pip install -r requirements.txt
```

3. **Set up environment variables**:

```bash
cp .env.example .env
# Edit .env and add:
# GEMINI_API_KEY=your_gemini_api_key
# (Optional) GCP_SERVICE_ACCOUNT_KEY_PATH=path/to/service-account-key.json
```

4. **Start the sample application infrastructure**:

```bash
docker-compose up -d
```

5. **Run the backend API**:

```bash
# Make sure you're in the project root
source venv/bin/activate  # Activate virtual environment
python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

6. **Run the frontend** (optional):

```bash
cd frontend
npm install
npm start
```

**Access Points:**
- API: `http://localhost:8000`
- API Docs: `http://localhost:8000/docs`
- Frontend: `http://localhost:3000` (if running)
- Sample App: `http://localhost:8001`

### GCP Setup (Optional)

For GCP resource support:

1. **Create a GCP service account** with the following roles:
   - Compute Engine Admin
   - Cloud SQL Admin
   - Redis Admin
   - Monitoring Viewer

2. **Download the service account key** and save it as `gcp-service-account-key.json`

3. **Set the path in `.env`**:
   ```
   GCP_SERVICE_ACCOUNT_KEY_PATH=./gcp-service-account-key.json
   ```

4. **Ensure your GCP resources are accessible** (VPC configuration, firewall rules, etc.)

## Usage

### API Endpoints

**Resources:**
- `GET /api/resources` - Get all resources and their status
- `GET /api/resources/status` - Get lightweight status updates
- `GET /api/logs` - Get error logs with filtering

**Fixes:**
- `POST /api/fixes/trigger` - Trigger LLM fix workflow
- `GET /api/fixes/{id}` - Get fix details
- `GET /api/fixes` - List all fixes

**LLM & MCP:**
- `GET /api/llm/interactions` - Get LLM interaction history
- `GET /api/mcp/tools` - Get available MCP tools

**GCP Failures (for testing):**
- `POST /api/gcp/failures/redis/{id}/memory-pressure` - Introduce Redis memory pressure
- `POST /api/gcp/failures/compute/{name}/cpu-stress` - Introduce CPU stress
- `POST /api/gcp/failures/compute/{name}/memory-pressure` - Introduce memory pressure

### Sample Application

The sample application is an E-commerce API that uses PostgreSQL and Redis. It includes endpoints to simulate failures:

- `POST /load/database?connections=10` - Generate database connection load
- `POST /load/database/blocking` - Create persistent blocking queries
- `POST /load/redis?size_mb=100` - Fill Redis memory
- `POST /load/cpu?duration=60` - Generate CPU load

### Triggering a Fix

1. **Introduce a failure** using the sample app endpoints or GCP failure endpoints
2. **Monitor resource status** via the dashboard or `GET /api/resources`
3. **Trigger a fix** via `POST /api/fixes/trigger`
4. **The system will automatically:**
   - Collect resource status and error logs
   - Analyze failures with LLM (Gemini API)
   - Generate a fix plan with tool selection
   - Execute MCP tools with proper sequencing
   - Verify fix effectiveness
   - Store evaluation data with before/after metrics

### Example: Fixing Redis Memory Pressure

```bash
# 1. Fill Redis memory
curl -X POST "http://localhost:8001/load/redis?size_mb=200"

# 2. Check resource status (should show DEGRADED)
curl "http://localhost:8000/api/resources"

# 3. Trigger LLM fix
curl -X POST "http://localhost:8000/api/fixes/trigger"

# 4. Monitor fix execution
curl "http://localhost:8000/api/fixes"
```

## MCP Tools

The system includes **20+ MCP tools** organized into local and GCP infrastructure categories:

### Local Infrastructure Tools (12 tools)

**Docker:**
- `docker_restart` - Restart a container
- `docker_scale` - Scale a service
- `docker_logs` - Get container logs
- `docker_stats` - Get container statistics

**PostgreSQL:**
- `postgres_restart` - Restart PostgreSQL
- `postgres_scale_connections` - Modify connection settings
- `postgres_vacuum` - Run VACUUM
- `postgres_kill_long_queries` - Kill long-running queries

**Redis:**
- `redis_flush` - Flush cache
- `redis_restart` - Restart Redis
- `redis_memory_purge` - Purge memory
- `redis_info` - Get Redis info

**Nginx:**
- `nginx_restart` - Restart Nginx
- `nginx_reload` - Reload configuration
- `nginx_scale_connections` - Scale worker connections
- `nginx_clear_connections` - Clear active connections
- `nginx_info` - Get Nginx status

### GCP Infrastructure Tools (8 tools)

**Compute Engine:**
- `gcp_compute_restart_instance` - Restart a VM instance
- `gcp_compute_start_instance` - Start a stopped instance
- `gcp_compute_stop_instance` - Stop a running instance

**Cloud SQL:**
- `gcp_sql_restart_instance` - Restart Cloud SQL instance
- `gcp_sql_scale_tier` - Scale instance tier
- `gcp_sql_kill_long_queries` - Kill long-running queries

**Memorystore Redis:**
- `gcp_redis_flush` - Flush Redis cache
- `gcp_redis_restart` - Restart Redis instance
- `gcp_redis_scale_memory` - Scale Redis memory size

## Project Structure

```
project/
├── backend/              # FastAPI backend
│   ├── api/             # API routes
│   │   └── routes/      # Route handlers (resources, fixes, gcp_failures)
│   ├── core/            # Core orchestration logic
│   ├── mcp/             # MCP tools (Docker, PostgreSQL, Redis, Nginx, GCP)
│   ├── monitoring/      # Resource and log monitoring
│   ├── gcp/             # GCP integration (auth, monitoring, tools)
│   ├── evaluation/      # Evaluation data storage (SQLite)
│   └── utils/           # Utility functions
├── frontend/            # React frontend
│   ├── src/
│   │   ├── components/  # React components
│   │   ├── services/    # API services
│   │   └── styles/      # CSS styles
│   └── public/          # Static assets
├── sample-app/          # Sample E-commerce API for testing
├── nginx/               # Nginx configuration
├── test/                # Test scripts and evaluation reports
└── docker-compose.yml   # Local infrastructure setup
```

## Development

### Running Tests

```bash
# Run evaluation tests
python test_evaluation.py

# Run GCP-specific tests
bash test_gcp_llm_fix.sh

# Run local tests
bash test_llm_fix.sh
```

### Code Quality

```bash
black backend/
ruff check backend/
```

## Key Technologies

- **Backend**: FastAPI (Python 3.11+), SQLite, AsyncIO
- **Frontend**: React.js 18+, Axios
- **LLM**: Google Gemini API (gemini-2.5-pro, gemini-2.5-flash)
- **Infrastructure**: Docker, PostgreSQL, Redis, Nginx
- **Cloud**: Google Cloud Platform (Compute Engine, Cloud SQL, Memorystore)
- **Protocol**: Model Context Protocol (MCP) for tool integration

## Evaluation Results

The system achieved **100% success rate** across 4 comprehensive test scenarios:

- **Average fix execution time**: ~4.3 minutes
- **Failure detection time**: < 120 seconds
- **LLM analysis time**: < 60 seconds
- **Tool selection accuracy**: 100%

All fixes executed successfully on the first attempt, demonstrating the effectiveness of LLM-driven infrastructure management.

## Documentation

For detailed information, see:
- [PROJECT_REPORT.md](PROJECT_REPORT.md) - Comprehensive project report with architecture, implementation details, and evaluation results
- [test/evaluation_report.md](test/evaluation_report.md) - Detailed test evaluation report

## License

MIT

## Author

**Vinay Singh**  
