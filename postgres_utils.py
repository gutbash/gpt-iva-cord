import psycopg2
import os
import asyncio
import logging

DATABASE_URL = os.getenv("DATABASE_URL")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def fetch_key(id):
    with psycopg2.connect(DATABASE_URL) as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT key FROM keys WHERE id = %s", (str(id),))
            result = cursor.fetchone()
            logging.info("Fetched key from keys table.")
    return result

def fetch_keys_table():
    with psycopg2.connect(DATABASE_URL) as conn:
        with conn.cursor() as cursor:
            # check if the keys table exists
            cursor.execute("SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'keys')")
            table_exists = cursor.fetchone()[0]
            logging.info("Fetched existing 'keys' table.")
            # create the keys table if it does not exist
            if not table_exists:
                cursor.execute("CREATE TABLE keys (id TEXT PRIMARY KEY, key TEXT)")
                conn.commit()
                logging.info("Created new 'keys' table.")
                

async def async_fetch_key(id):
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, fetch_key, id)
    return result

async def async_fetch_keys_table():
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, fetch_keys_table)
    return