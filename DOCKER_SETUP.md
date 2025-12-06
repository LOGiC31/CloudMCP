# Docker Setup Guide

## Docker Options on macOS

You have two options for running Docker on macOS:

### Option 1: Colima (Lightweight, CLI-based)
You appear to be using Colima. To start it:

```bash
# Start Colima
colima start

# Check status
colima status

# Verify Docker is working
docker ps
```

### Option 2: Docker Desktop (GUI-based)
If you prefer Docker Desktop:

1. Download and install Docker Desktop from https://www.docker.com/products/docker-desktop
2. Start Docker Desktop from Applications
3. Verify: `docker ps`

## Starting the Sample Application

Once Docker is running:

```bash
# Start all services
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

## Troubleshooting

### Colima Issues

If Colima is not starting:

```bash
# Check if Colima is installed
which colima

# If not installed, install via Homebrew
brew install colima docker docker-compose

# Start Colima with default settings
colima start

# Or start with more resources
colima start --cpu 4 --memory 8
```

### Docker Socket Issues

If you see socket connection errors:

```bash
# Check Docker context
docker context ls

# Set Colima context (if using Colima)
docker context use colima

# Or set default context
docker context use default
```

### Port Conflicts

If ports are already in use:

```bash
# Check what's using the ports
lsof -i :5432  # PostgreSQL
lsof -i :6379  # Redis
lsof -i :8001  # Sample app

# Kill processes if needed
kill -9 <PID>
```

## Verifying Setup

After starting Docker and containers:

```bash
# 1. Check Docker is running
docker ps

# 2. Check containers are up
docker-compose ps

# 3. Test PostgreSQL
docker exec -it postgres psql -U postgres -d sample_app -c "SELECT 1;"

# 4. Test Redis
docker exec -it redis redis-cli ping

# 5. Test sample app
curl http://localhost:8001/health
```

## Next Steps

Once Docker is running and containers are up:

1. Test the sample application endpoints
2. Generate failure scenarios
3. Test the LLM fix workflow

