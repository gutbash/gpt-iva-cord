import asyncpg
import asyncio
import logging

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives import hashes, hmac
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend
import os
import base64

DATABASE_URL = os.getenv("DATABASE_URL")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

async def fetch_key(id):
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        result = await conn.fetchrow("SELECT key FROM keys WHERE id = $1", str(id))
        logging.info("Fetched key from keys table.")
    finally:
        await conn.close()
    return result

async def fetch_keys_table():
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        # check if the keys table exists
        table_exists = await conn.fetchval("SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'keys')")
        logging.info("Fetched existing 'keys' table.")
        # create the keys table if it does not exist
        if not table_exists:
            await conn.execute("CREATE TABLE keys (id TEXT PRIMARY KEY, key TEXT)")
            logging.info("Created new 'keys' table.")
    finally:
        await conn.close()

async def upsert_key(id, key):
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        await conn.execute("""
            INSERT INTO keys (id, key)
            VALUES ($1, $2)
            ON CONFLICT (id)
            DO UPDATE SET key = $2
        """, str(id), key)
        logging.info("Upserted key in the 'keys' table.")
    finally:
        await conn.close()