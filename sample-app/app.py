"""Sample E-commerce API application for testing infrastructure orchestration."""
import os
import time
import random
import asyncio
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
import psycopg2
from psycopg2 import pool
import redis
from contextlib import contextmanager
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Sample E-commerce API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database connection pool
db_pool = None
redis_client = None

# Configuration
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgres")
POSTGRES_DB = os.getenv("POSTGRES_DB", "sample_app")
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))


@app.on_event("startup")
async def startup():
    """Initialize database and Redis connections."""
    global db_pool, redis_client
    
    # Initialize PostgreSQL connection pool
    try:
        db_pool = psycopg2.pool.SimpleConnectionPool(
            1, 10,
            host=POSTGRES_HOST,
            port=POSTGRES_PORT,
            user=POSTGRES_USER,
            password=POSTGRES_PASSWORD,
            database=POSTGRES_DB
        )
        logger.info("PostgreSQL connection pool created")
        
        # Initialize database schema
        init_database()
    except Exception as e:
        logger.error(f"Failed to create database pool: {e}")
    
    # Initialize Redis
    try:
        redis_client = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            decode_responses=True
        )
        redis_client.ping()
        logger.info("Redis connection established")
    except Exception as e:
        logger.error(f"Failed to connect to Redis: {e}")


@app.on_event("shutdown")
async def shutdown():
    """Close connections."""
    if db_pool:
        db_pool.closeall()
    if redis_client:
        redis_client.close()


def init_database():
    """Initialize database schema."""
    conn = db_pool.getconn()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                price DECIMAL(10, 2) NOT NULL,
                stock INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id SERIAL PRIMARY KEY,
                product_id INTEGER REFERENCES products(id),
                quantity INTEGER NOT NULL,
                total_price DECIMAL(10, 2) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        logger.info("Database schema initialized")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        conn.rollback()
    finally:
        db_pool.putconn(conn)


@contextmanager
def get_db_connection():
    """Get database connection from pool."""
    conn = db_pool.getconn()
    try:
        yield conn
    finally:
        db_pool.putconn(conn)


@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "Sample E-commerce API", "status": "running"}


@app.get("/health")
async def health():
    """Health check."""
    db_healthy = False
    redis_healthy = False
    
    try:
        conn = db_pool.getconn()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.fetchone()
        db_pool.putconn(conn)
        db_healthy = True
    except:
        pass
    
    try:
        redis_client.ping()
        redis_healthy = True
    except:
        pass
    
    return {
        "status": "healthy" if (db_healthy and redis_healthy) else "degraded",
        "database": "healthy" if db_healthy else "unhealthy",
        "redis": "healthy" if redis_healthy else "unhealthy"
    }


@app.get("/products")
async def get_products():
    """Get all products."""
    cache_key = "products:all"
    
    # Try cache first
    if redis_client:
        try:
            cached = redis_client.get(cache_key)
            if cached:
                logger.info("Cache hit for products")
                import json
                products = json.loads(cached)
                return {"source": "cache", "products": products}
        except Exception as e:
            logger.warning(f"Cache read error: {e}")
    
    # Query database
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, name, price, stock FROM products ORDER BY id")
            rows = cursor.fetchall()
            products = [
                {"id": r[0], "name": r[1], "price": float(r[2]), "stock": r[3]}
                for r in rows
            ]
            
            # Cache result
            if redis_client:
                try:
                    import json
                    redis_client.setex(cache_key, 60, json.dumps(products))
                except Exception as e:
                    logger.warning(f"Cache write error: {e}")
            
            return {"source": "database", "products": products}
    except Exception as e:
        logger.error(f"Database error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/products")
async def create_product(name: str, price: float, stock: int):
    """Create a product."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO products (name, price, stock) VALUES (%s, %s, %s) RETURNING id",
                (name, price, stock)
            )
            product_id = cursor.fetchone()[0]
            conn.commit()
            
            # Invalidate cache
            if redis_client:
                try:
                    redis_client.delete("products:all")
                except:
                    pass
            
            return {"id": product_id, "name": name, "price": price, "stock": stock}
    except Exception as e:
        logger.error(f"Database error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/load/database")
async def generate_database_load(background_tasks: BackgroundTasks, connections: int = 10):
    """Generate database load by creating many connections."""
    logger.warning(f"Generating database load with {connections} connections")
    background_tasks.add_task(create_many_connections, connections)
    return {"message": f"Generating load with {connections} connections"}


@app.post("/load/database/blocking")
async def generate_blocking_queries(background_tasks: BackgroundTasks, queries: int = 10):
    """Generate blocking queries that persist until killed (won't auto-recover)."""
    logger.warning(f"Generating {queries} blocking queries that won't auto-recover")
    background_tasks.add_task(create_blocking_queries, queries)
    return {"message": f"Generating {queries} blocking queries (will persist until killed)"}


def create_many_connections(num_connections: int):
    """Create many database connections to simulate load."""
    import threading
    
    connections = []
    connection_lock = threading.Lock()
    
    def keep_connection_alive(conn, conn_id):
        """Keep a connection alive with periodic queries."""
        try:
            cursor = conn.cursor()
            # Keep connection alive for 5 minutes with periodic sleep queries
            # (Increased from 2 minutes to give LLM time to fix before connections expire)
            for _ in range(30):  # 30 * 10 seconds = 5 minutes
                cursor.execute("SELECT pg_sleep(10)")
                conn.commit()
        except Exception as e:
            logger.error(f"Connection {conn_id} error: {e}")
        finally:
            try:
                cursor.close()
                conn.close()
                with connection_lock:
                    if conn in connections:
                        connections.remove(conn)
            except:
                pass
    
    try:
        for i in range(num_connections):
            try:
                conn = psycopg2.connect(
                    host=POSTGRES_HOST,
                    port=POSTGRES_PORT,
                    user=POSTGRES_USER,
                    password=POSTGRES_PASSWORD,
                    database=POSTGRES_DB
                )
                with connection_lock:
                    connections.append(conn)
                
                # Start a thread to keep connection alive
                thread = threading.Thread(target=keep_connection_alive, args=(conn, i), daemon=True)
                thread.start()
                
                logger.info(f"Created connection {i+1}/{num_connections}")
            except Exception as e:
                logger.error(f"Failed to create connection {i}: {e}")
        
        # Wait a bit to ensure connections are established
        time.sleep(2)
        logger.info(f"Created {len(connections)} connections, keeping them alive for 5 minutes")
    except Exception as e:
        logger.error(f"Error creating connections: {e}")


def create_blocking_queries(num_queries: int):
    """Create long-running blocking queries that persist until killed."""
    import threading
    
    def run_blocking_query(query_id):
        """Run a query that blocks indefinitely until killed."""
        try:
            conn = psycopg2.connect(
                host=POSTGRES_HOST,
                port=POSTGRES_PORT,
                user=POSTGRES_USER,
                password=POSTGRES_PASSWORD,
                database=POSTGRES_DB
            )
            cursor = conn.cursor()
            
            # Create a long-running query that blocks
            # Using pg_sleep in a loop to keep the query active indefinitely
            # This query will run until the connection is killed
            logger.info(f"Starting blocking query {query_id}")
            try:
                # Run a very long sleep query (effectively infinite)
                # This will keep the connection active and consuming a connection slot
                cursor.execute("SELECT pg_sleep(3600)")  # 1 hour sleep
                conn.commit()
            except Exception as e:
                logger.info(f"Blocking query {query_id} terminated: {e}")
            finally:
                try:
                    cursor.close()
                    conn.close()
                    logger.info(f"Blocking query {query_id} connection closed")
                except:
                    pass
        except Exception as e:
            logger.error(f"Failed to create blocking query {query_id}: {e}")
    
    try:
        threads = []
        for i in range(num_queries):
            thread = threading.Thread(target=run_blocking_query, args=(i,), daemon=True)
            thread.start()
            threads.append(thread)
            logger.info(f"Started blocking query thread {i+1}/{num_queries}")
        
        # Wait a bit to ensure queries are started
        time.sleep(2)
        logger.info(f"Created {num_queries} blocking queries (will persist until killed)")
    except Exception as e:
        logger.error(f"Error creating blocking queries: {e}")


@app.post("/load/redis")
async def generate_redis_load(size_mb: int = 100):
    """Generate Redis load by filling memory."""
    logger.warning(f"Generating Redis load: {size_mb}MB")
    if not redis_client:
        raise HTTPException(status_code=500, detail="Redis not available")
    
    try:
        # Fill Redis with data
        data_size = size_mb * 1024 * 1024  # Convert to bytes
        chunk_size = 1024  # 1KB chunks
        num_keys = data_size // chunk_size
        
        for i in range(num_keys):
            key = f"load:data:{i}"
            value = "x" * chunk_size
            redis_client.set(key, value)
            if i % 1000 == 0:
                logger.info(f"Filled {i}/{num_keys} keys")
        
        return {"message": f"Filled Redis with {num_keys} keys (~{size_mb}MB)"}
    except Exception as e:
        logger.error(f"Redis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/load/cpu")
async def generate_cpu_load(duration: int = 60):
    """Generate CPU load."""
    logger.warning(f"Generating CPU load for {duration} seconds")
    import threading
    
    def cpu_intensive():
        end_time = time.time() + duration
        while time.time() < end_time:
            # CPU intensive operation
            sum(range(1000000))
    
    thread = threading.Thread(target=cpu_intensive)
    thread.start()
    
    return {"message": f"Generating CPU load for {duration} seconds"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

