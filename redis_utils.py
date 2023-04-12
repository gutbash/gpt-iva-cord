import os
import aioredis
import cloudpickle as pickle

# Function to create an aioredis client
async def get_redis_client():
    REDIS_URL = os.getenv('REDIS_URL')
    return await aioredis.from_url(REDIS_URL)

# Async function to save a dictionary to Redis
async def save_pickle_to_redis(key, data):
    redis_client = await get_redis_client()
    pickled_data = pickle.dumps(data)
    await redis_client.set(key, pickled_data)
    await redis_client.close()

# Async function to load a dictionary from Redis
async def load_pickle_from_redis(key):
    redis_client = await get_redis_client()
    pickled_data = await redis_client.get(key)
    await redis_client.close()

    if pickled_data is None:
        return {}
    return pickle.loads(pickled_data)