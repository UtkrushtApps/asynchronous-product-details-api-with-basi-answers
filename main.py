import asyncio
import json
from typing import Dict, Optional

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
import aioredis
from pydantic import BaseModel, Field

# ----- Mock Database (in-memory) -----
PRODUCTS_DB: Dict[int, Dict] = {
    1: {"id": 1, "name": "Laptop", "price": 1000.00},
    2: {"id": 2, "name": "Smartphone", "price": 500.00},
    3: {"id": 3, "name": "Headphones", "price": 100.00},
}

REDIS_URL = "redis://localhost"
CACHE_TTL = 60  # seconds

redis: Optional[aioredis.Redis] = None

app = FastAPI(title="Product API with Redis Caching")

class Product(BaseModel):
    id: int
    name: str
    price: float

class ProductUpdate(BaseModel):
    name: Optional[str] = Field(None)
    price: Optional[float] = Field(None)

# ----- Async Redis Connection -----
@app.on_event("startup")
async def on_startup():
    global redis
    try:
        redis = await aioredis.from_url(REDIS_URL, decode_responses=True)
        await redis.ping()
    except Exception as e:
        print(f"[WARN] Redis unavailable on startup: {e}")
        redis = None

@app.on_event("shutdown")
async def on_shutdown():
    global redis
    if redis:
        await redis.close()

# ----- Helper Functions -----
async def get_product_from_db(product_id: int) -> Optional[Dict]:
    # Simulate async db by sleeping
    await asyncio.sleep(0.05)
    return PRODUCTS_DB.get(product_id)

def _product_cache_key(product_id: int) -> str:
    return f"product:{product_id}"

async def get_redis_connection() -> Optional[aioredis.Redis]:
    global redis
    if redis:
        try:
            await redis.ping()
            return redis
        except Exception:
            return None
    return None

# ----- Endpoints -----
@app.get("/products/{product_id}", response_model=Product)
async def get_product(product_id: int):
    cache_key = _product_cache_key(product_id)
    redis_conn = await get_redis_connection()
    # Try to get from cache
    if redis_conn:
        try:
            cached = await redis_conn.get(cache_key)
            if cached:
                data = json.loads(cached)
                return Product(**data)
        except Exception:
            pass  # Redis unavailable, fallback to DB
    # Fallback: get from DB
    prod = await get_product_from_db(product_id)
    if not prod:
        raise HTTPException(status_code=404, detail="Product not found")
    # Save to cache (cache-aside)
    if redis_conn:
        try:
            await redis_conn.set(cache_key, json.dumps(prod), ex=CACHE_TTL)
        except Exception:
            pass  # Redis error: skip caching
    return Product(**prod)

@app.put("/products/{product_id}", response_model=Product)
async def update_product(product_id: int, update: ProductUpdate, background_tasks: BackgroundTasks):
    existing = await get_product_from_db(product_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Product not found")
    # Apply updates
    updated = existing.copy()
    if update.name is not None:
        updated["name"] = update.name
    if update.price is not None:
        updated["price"] = update.price
    PRODUCTS_DB[product_id] = updated
    # Background cache invalidation
    background_tasks.add_task(invalidate_cache, product_id)
    return Product(**updated)

async def invalidate_cache(product_id: int):
    redis_conn = await get_redis_connection()
    if redis_conn:
        try:
            await redis_conn.delete(_product_cache_key(product_id))
        except Exception:
            pass

@app.get("/health")
async def health_check():
    return {"status": "ok"}
