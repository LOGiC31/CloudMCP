# Testing Guide

## Automated Test Script

Use the `test_llm_fix.sh` script to run end-to-end tests of the LLM fix workflow.

### Usage

```bash
# Test with Redis failure (default)
./test_llm_fix.sh

# Test with database failure
./test_llm_fix.sh database

# Test with both failures
./test_llm_fix.sh both
```

### What the Script Does

1. **Introduces Failure**
   - Redis: Fills Redis with 250MB of data
   - Database: Creates 50 concurrent connections
   - Both: Does both

2. **Validates Failure**
   - Checks resource status for unhealthy resources
   - Checks error logs
   - Confirms failure is detected

3. **Triggers LLM Fix**
   - Calls the `/api/fixes/trigger` endpoint
   - Waits for fix to complete (up to 60 seconds)
   - Monitors fix status

4. **Validates Results**
   - Runs `check_llm_fixes.sh` to show results
   - Checks if all resources are healthy
   - Shows tool execution statistics

### Example Output

```
🧪 LLM Fix Test Script
======================

[INFO] Checking if services are running...
[SUCCESS] Services are running

[INFO] Step 1: Introducing failure...
[INFO] Filling Redis with data to cause memory pressure...
[SUCCESS] Redis failure introduced: {"message":"Filled Redis with 256000 keys (~250MB)"}

[INFO] Step 2: Validating failure...
[SUCCESS] Failure detected: 1 resource(s) not healthy
  - redis: DEGRADED

[INFO] Step 3: Triggering LLM fix...
[SUCCESS] Fix triggered successfully: fix_abc123
[INFO] Waiting for fix to complete (this may take 30-60 seconds)...
[SUCCESS] Fix completed with status: SUCCESS

[INFO] Step 4: Validating fix results...
🔍 Checking LLM Fix Results
...
```

## Manual Testing

### 1. Introduce Failure

```bash
# Redis memory overload
curl -X POST "http://localhost:8001/load/redis?size_mb=250"

# Database connection overload
curl -X POST "http://localhost:8001/load/database?connections=50"
```

### 2. Check Resource Status

```bash
curl http://localhost:8000/api/resources | python3 -m json.tool
```

### 3. Trigger Fix

```bash
curl -X POST http://localhost:8000/api/fixes/trigger \
  -H "Content-Type: application/json" \
  -d '{}'
```

### 4. Check Results

```bash
./check_llm_fixes.sh
```

## Test Scenarios

### Scenario 1: Redis Memory Pressure
- **Failure**: Fill Redis beyond capacity
- **Expected Fix**: LLM should flush Redis or restart it
- **Validation**: Redis should be healthy after fix

### Scenario 2: Database Connection Overload
- **Failure**: Create too many database connections
- **Expected Fix**: LLM should kill long queries or restart PostgreSQL
- **Validation**: Database should be healthy after fix

### Scenario 3: Container Failure
- **Failure**: Stop a container manually
- **Expected Fix**: LLM should restart the container
- **Validation**: Container should be running after fix

```bash
# Manually stop a container
docker stop redis

# Trigger fix
curl -X POST http://localhost:8000/api/fixes/trigger \
  -H "Content-Type: application/json" \
  -d '{}'
```

## Troubleshooting

### Script fails at "Checking if services are running"
- Make sure backend is running: `./start_server.sh`
- Make sure sample app is running: `docker compose up -d`

### No failures detected
- Check if the failure actually occurred
- Check resource status manually
- Check logs: `curl http://localhost:8000/api/logs`

### Fix doesn't complete
- Check server logs for errors
- Verify LLM API key is set: `echo $GEMINI_API_KEY`
- Check fix status: `curl http://localhost:8000/api/fixes | python3 -m json.tool`

### Resources still unhealthy after fix
- Check tool execution results in fix evaluation
- Verify Docker is accessible
- Check container logs: `docker logs <container-name>`

