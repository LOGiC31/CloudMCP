# Quick Start Guide

## Phase 1 Setup (Local)

### 1. Install Dependencies

```bash
# Install Python dependencies
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
# Copy environment template
cp .env.example .env

# Edit .env and add your Gemini API key
# GEMINI_API_KEY=your_actual_api_key_here
```

### 3. Start Infrastructure

```bash
# Start PostgreSQL, Redis, and sample app
docker-compose up -d

# Verify containers are running
docker ps
```

### 4. Initialize Sample App Database

The sample app will automatically initialize the database schema on startup. You can verify by checking the logs:

```bash
docker logs sample-app
```

### 5. Start Backend API

```bash
# From project root (NOT inside backend/)
source venv/bin/activate  # Activate virtual environment first
python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at:
- API: http://localhost:8000
- Docs: http://localhost:8000/docs
- Health: http://localhost:8000/health

### 6. Test the System

#### Check Resources
```bash
curl http://localhost:8000/api/resources
```

#### Generate a Failure Scenario

**Database Connection Exhaustion:**
```bash
curl -X POST "http://localhost:8001/load/database?connections=20"
```

**Redis Memory Full:**
```bash
curl -X POST "http://localhost:8001/load/redis?size_mb=200"
```

#### View Logs
```bash
curl http://localhost:8000/api/logs/errors
```

#### Trigger a Fix
```bash
curl -X POST http://localhost:8000/api/fixes/trigger \
  -H "Content-Type: application/json" \
  -d '{}'
```

#### View Fix Results
```bash
curl http://localhost:8000/api/fixes
```

### 7. View LLM Interactions

```bash
curl http://localhost:8000/api/llm/interactions
```

## Sample Application Endpoints

The sample app runs on port 8001:

- `GET /` - Root endpoint
- `GET /health` - Health check
- `GET /products` - List products
- `POST /products?name=Product&price=10.99&stock=100` - Create product
- `POST /load/database?connections=10` - Generate DB load
- `POST /load/redis?size_mb=100` - Fill Redis memory
- `POST /load/cpu?duration=60` - Generate CPU load

## Troubleshooting

### Docker Issues
```bash
# Check container status
docker-compose ps

# View logs
docker-compose logs

# Restart services
docker-compose restart
```

### Database Connection Issues
```bash
# Check PostgreSQL is running
docker exec -it postgres psql -U postgres -d sample_app -c "SELECT 1;"
```

### Redis Connection Issues
```bash
# Check Redis is running
docker exec -it redis redis-cli ping
```

### API Issues
- Check that GEMINI_API_KEY is set in .env
- Verify backend is running on port 8000
- Check logs for errors

## Next Steps

1. Set up the React frontend (Phase 1, Week 3)
2. Add more MCP tools as needed
3. Test various failure scenarios
4. Review evaluation data

