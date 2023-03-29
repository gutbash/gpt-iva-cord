import psycopg2
import os
import asyncio

DATABASE_URL = os.getenv("DATABASE_URL")

def fetch_key(id):
    with psycopg2.connect(DATABASE_URL) as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT key FROM keys WHERE id = %s", (str(id),))
            result = cursor.fetchone()
    return result

async def async_fetch_key(id):
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, fetch_key, id)
    return result