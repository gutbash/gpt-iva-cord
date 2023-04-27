import os
import logging
import aioredis
import pickle
from utils.crypto_utils import envelope_decrypt, envelope_encrypt

async def get_redis_client():
    REDIS_TLS_URL = os.getenv('REDIS_TLS_URL')
    return await aioredis.from_url(REDIS_TLS_URL)

async def get_redis_master_key():
    hex_redis_master_key = os.getenv("REDIS_MASTER_KEY")
    REDIS_MASTER_KEY = bytes.fromhex(hex_redis_master_key)
    return REDIS_MASTER_KEY

async def save_pickle_to_redis(key, data):
    async with await get_redis_client() as redis_client:
        redis_master_key = await get_redis_master_key()
        pickled_data = pickle.dumps(data)
        encrypted_message = envelope_encrypt(pickled_data, redis_master_key)
        await redis_client.set(key, encrypted_message)

async def load_pickle_from_redis(key):
    async with await get_redis_client() as redis_client:
        redis_master_key = await get_redis_master_key()
        encrypted_message = await redis_client.get(key)
        pickled_data = envelope_decrypt(encrypted_message, redis_master_key)
        if pickled_data is None:
            return {}
        loaded_data = pickle.loads(pickled_data)
    return loaded_data