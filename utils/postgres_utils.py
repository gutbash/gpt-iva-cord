import asyncpg
import logging
import os
from utils.crypto_utils import envelope_decrypt, envelope_encrypt

async def get_pg_client():
    DATABASE_URL = os.getenv("DATABASE_URL")
    return await asyncpg.connect(DATABASE_URL)

async def get_pg_master_key():
    hex_pg_master_key = os.getenv("PG_MASTER_KEY")
    PG_MASTER_KEY = bytes.fromhex(hex_pg_master_key)
    return PG_MASTER_KEY

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

async def fetch_key(id):
    conn = await get_pg_client()
    try:
        pg_master_key = await get_pg_master_key()
        row = await conn.fetchrow("SELECT key FROM keys WHERE id = $1", str(id))
        logging.info("Fetched key from keys table.")
        if row is None:
            return None
        else:
            encrypted_key = row['key']
            decrypted_key = envelope_decrypt(encrypted_key, pg_master_key).decode()
    finally:
        await conn.close()
    logging.info(f"KEY DECRYPTED: {decrypted_key}")
    return decrypted_key

async def fetch_keys_table():
    conn = await get_pg_client()
    try:
        # check if the keys table exists
        table_exists = await conn.fetchval("SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'keys')")
        logging.info("Fetched existing 'keys' table.")
        # create the keys table if it does not exist
        if not table_exists:
            await conn.execute("CREATE TABLE keys (id TEXT PRIMARY KEY, key bytea)")
            logging.info("Created new 'keys' table.")
    finally:
        await conn.close()

async def upsert_key(id, key):
    conn = await get_pg_client()
    try:
        pg_master_key = await get_pg_master_key()
        encrypted_key = envelope_encrypt(key.encode(), pg_master_key)
        logging.info(f"KEY ENCRYPTED: {encrypted_key}")
        await conn.execute("""
            INSERT INTO keys (id, key)
            VALUES ($1, $2)
            ON CONFLICT (id)
            DO UPDATE SET key = $2
        """, str(id), encrypted_key)
        logging.info("Upserted key in the 'keys' table.")
    finally:
        await conn.close()