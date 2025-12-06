# MCP-Enabled Infrastructure Orchestration System

An intelligent infrastructure orchestration system that uses LLM reasoning (Gemini API) and Model Context Protocol (MCP) to autonomously detect and fix infrastructure issues.

## Project Overview

This system implements a two-phase approach:

- **Phase 1 (Local)**: Test and validate concepts using Docker, PostgreSQL, and Redis
- **Phase 2 (Cloud)**: Deploy to GCP with Compute Engine, Cloud SQL, and Cloud Storage

## Features

- **Intelligent Failure Detection**: Collects and analyzes logs from infrastructure components
- **LLM-Powered Analysis**: Uses Gemini API to understand failures and create fix plans
- **MCP Tools**: Wraps CLI commands and API calls as MCP tools for LLM execution
- **Autonomous Fixes**: Automatically executes fix plans using MCP tools
- **Evaluation Tracking**: Stores all fix attempts with before/after metrics
- **Web Dashboard**: Modern UI to view resources, logs, LLM interactions, and trigger fixes

## Architecture

```
┌─────────────┐
│   Web UI    │
└──────┬──────┘
       │
┌──────▼──────────────────┐
│   FastAPI Backend       │
│  ┌──────────────────┐   │
│  │ MCP Orchestrator │   │
│  └────────┬─────────┘   │
│           │              │
│  ┌────────▼─────────┐   │
│  │ LLM Client       │   │
│  │ (Gemini API)     │   │
│  └────────┬─────────┘   │
│           │              │
│  ┌────────▼─────────┐   │
│  │ MCP Tools        │   │
│  └────────┬─────────┘   │
└───────────┼──────────────┘
            │
    ┌───────┼───────┐
    │       │       │
┌───▼───┐ ┌─▼──┐ ┌─▼──┐
│Docker │ │Post│ │Red │
│       │ │gres│ │is  │
└───────┘ └────┘ └────┘
```

## Setup

### Prerequisites

- Python 3.11+
- Docker and Docker Compose
- Gemini API key

### Installation

1. **Clone the repository** (if applicable)

2. **Install Python dependencies**:

```bash
pip install -r requirements.txt
```

3. **Set up environment variables**:

```bash
cp .env.example .env
# Edit .env and add your GEMINI_API_KEY
```

4. **Start the sample application infrastructure**:

```bash
docker-compose up -d
```

5. **Run the backend API**:

```bash
# Make sure you're in the project root (not inside backend/)
source venv/bin/activate  # Activate virtual environment
python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`
API documentation at `http://localhost:8000/docs`

## Usage

### API Endpoints

- `GET /api/resources` - Get all resources and their status
- `GET /api/logs` - Get logs (with filters)
- `GET /api/llm/interactions` - Get LLM interaction history
- `POST /api/fixes/trigger` - Trigger a fix workflow

### Sample Application

The sample application is an E-commerce API that uses PostgreSQL and Redis. It includes endpoints to simulate failures:

- `POST /load/database?connections=10` - Generate database connection load
- `POST /load/redis?size_mb=100` - Fill Redis memory
- `POST /load/cpu?duration=60` - Generate CPU load

### Triggering a Fix

1. Generate a failure scenario using the sample app endpoints
2. View logs and resource status in the dashboard (or via API)
3. Trigger a fix via `POST /api/fixes/trigger`
4. The system will:
   - Collect error logs
   - Analyze with LLM
   - Create a fix plan
   - Execute MCP tools
   - Verify the fix
   - Store evaluation data

## MCP Tools

The system includes the following MCP tools:

### Docker Tools

- `docker_restart` - Restart a container
- `docker_scale` - Scale a service
- `docker_logs` - Get container logs
- `docker_stats` - Get container statistics

### PostgreSQL Tools

- `postgres_restart` - Restart PostgreSQL
- `postgres_scale_connections` - Modify connection settings
- `postgres_vacuum` - Run VACUUM
- `postgres_kill_long_queries` - Kill long-running queries

### Redis Tools

- `redis_flush` - Flush cache
- `redis_restart` - Restart Redis
- `redis_memory_purge` - Purge memory
- `redis_info` - Get Redis info

## Project Structure

```
project/
├── backend/           # FastAPI backend
│   ├── api/          # API routes
│   ├── core/         # Core orchestration logic
│   ├── mcp/          # MCP tools
│   ├── monitoring/   # Log and resource monitoring
│   └── evaluation/   # Evaluation data storage
├── sample-app/       # Sample application for testing
├── frontend/         # React frontend (to be implemented)
└── docker-compose.yml
```

## Development

### Running Tests

```bash
pytest tests/
```

### Code Quality

```bash
black backend/
ruff check backend/
```

## Phase 2 (Cloud)

Phase 2 will extend the system to work with GCP resources:

- GCP Compute Engine instances
- Cloud SQL (PostgreSQL)
- Cloud Storage
- GCP Monitoring APIs

## License

MIT

## Author

Vinay Singh - 335008079
