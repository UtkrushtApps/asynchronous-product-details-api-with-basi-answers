# Solution Steps

1. 1. Identify the endpoints to patch: the product GET and PUT endpoints both require async and caching updates.

2. 2. Ensure all FastAPI endpoints are marked async and all data access/database interactions are performed asynchronously (use asyncio.sleep to simulate async DB, since a real async DB is not present).

3. 3. Establish a global aioredis Redis connection pool at startup using aioredis.from_url, handle Redis unavailable scenarios gracefully.

4. 4. Implement cache-aside: On product GET, first try to get data from Redis using an async get, fall back to the DB if not cached, on DB hit, store the serialized JSON of the product in Redis with an async set and a TTL (set by ex=CACHE_TTL).

5. 5. Handle Redis unavailability gracefully by wrapping Redis calls in try/except and ignoring Redis errors (serve data from DB if cache fails).

6. 6. For the PUT/Update endpoint, on success, launch a background task to invalidate (delete) the product's cache key from Redis using aioredis' async delete so the next GET will reload from DB.

7. 7. Ensure all serialization and deserialization to/from Redis is done as JSON to handle the Python dicts.

8. 8. On Redis connection or operation errors, never fail the endpoint: instead, serve up-to-date DB content always, only caching when possible.

9. 9. Add a /health endpoint to confirm API liveness (optional, for completeness).

10. 10. Test with Redis running/not running: GET will cache and serve products; PUT will invalidate cache. Ensure fallback behavior is robust.

