from serpapi import GoogleSearch
import random
import aiohttp
import os

GOOGLE_API_KEY = os.getenv("GOOGLE_API_TOKEN")
GOOGLE_CSE_ID = os.getenv("GOOGLE_CSE_ID")
os.environ["GOOGLE_API_KEY"] = GOOGLE_API_KEY
SERPAPI_API_KEY = os.getenv("SERPAPI_API_KEY")

async def get_image_from_search(query: str) -> str:
    # Replace YOUR_API_KEY and YOUR_CSE_ID with your own API key and CSE ID
    url = f"https://www.googleapis.com/customsearch/v1?q={query}&key={GOOGLE_API_KEY}&cx={GOOGLE_CSE_ID}&searchType=image"

    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            results = await response.json()

    # Extract the image URL for the first result (best/most relevant image)
    image_urls = [item['link'] for item in results['items'][:10]]
    chosen_image_url = random.choice(image_urls)
    return chosen_image_url

async def get_organic_results(query: str) -> str:
    
    # Configure the GoogleSearch object with the provided query and API key
    search = {
        "engine": "google",
        "q": query,
        "api_key": SERPAPI_API_KEY,
        "gl": "us",
        "hl": "en",
        "safe": "active",
    }

    async with aiohttp.ClientSession() as session:
        async with session.get("https://serpapi.com/search", params=search) as response:
            results = await response.json()
    
    organic_results_raw = results.get("organic_results", None)
    knowledge_graph_raw = results.get("knowledge_graph", None)
    
    organic_results, knowledge_graph = "", ""
    
    if organic_results_raw is not None:
        
        organic_results_keys = [
            #"position",
            "title",
            "link",
            "snippet",
            #"sitelinks",
        ]
        
        organic_results = await get_formatted_key_values_from_list(organic_results_keys, organic_results_raw)
        
        organic_results = "\n".join(organic_results)
        
    if knowledge_graph_raw is not None:
        
        knowledge_graph_keys = [
            "title",
            "type",
            "website",
            "description",
            "source",
        ]
        
        knowledge_graph = await get_formatted_key_values(knowledge_graph_keys, knowledge_graph_raw)
        knowledge_graph = f"\n\n{knowledge_graph}"
        
    final_results = f"\n\n{organic_results}{knowledge_graph}\n"
    
    return final_results

async def get_shopping_results(query: str) -> str:
    
    # Configure the GoogleSearch object with the provided query and API key
    search = {
        "engine": "google",
        "q": query,
        "api_key": SERPAPI_API_KEY,
        "gl": "us",
        "hl": "en",
        "safe": "active",
    }

    async with aiohttp.ClientSession() as session:
        async with session.get("https://serpapi.com/search", params=search) as response:
            results = await response.json()
    
    immersive_products_raw = results.get("immersive_products", None)
    inline_products_raw = results.get("inline_products", None)
    shopping_results_raw = results.get("shopping_results", None)
    product_result_raw = results.get("product_result", None)
    
    immersive_products, inline_products, shopping_results, product_result = "", "", "", ""
    
    if immersive_products_raw is not None:
        
        immersive_products_keys = [
            "source",
            "title",
            "snippets",
            "rating",
            "price",
            "original_price",
        ]
        
        immersive_products = await get_formatted_key_values_from_list(immersive_products_keys, immersive_products_raw)
        immersive_products = "\n".join(immersive_products)
        
    if inline_products_raw is not None:
        
        inline_products_keys = [
            "title",
            "source",
            "price",
            "original_price",
            "rating",
            "specifications",
        ]
        
        inline_products = await get_formatted_key_values_from_list(inline_products_keys, inline_products_raw)
        inline_products = "\n".join(inline_products)
        
    if shopping_results_raw is not None:
        
        shopping_results_keys = [
            "title",
            "price",
            "link",
            "source",
            "rating",
        ]
        
        shopping_results = await get_formatted_key_values_from_list(shopping_results_keys, shopping_results_raw)
        shopping_results = "\n".join(shopping_results)
        
    if product_result_raw is not None:
        
        product_result_keys = [
            "title",
            "rating",
            "pricing",
            "manufacturer",
            "description",
            "features",
            "review_results",
            "videos",
        ]
        
        product_result = await get_formatted_key_values(product_result_keys, product_result_raw)
        product_result = "\n".join(product_result)
        
    final_results = f"\n\n{immersive_products}{inline_products}{shopping_results}{product_result}\n"
    
    return final_results
    
async def get_news_results(query: str) -> str:
    
    # Configure the GoogleSearch object with the provided query and API key
    search = {
        "engine": "google",
        "q": query,
        "api_key": SERPAPI_API_KEY,
        "gl": "us",
        "hl": "en",
        "safe": "active",
    }

    async with aiohttp.ClientSession() as session:
        async with session.get("https://serpapi.com/search", params=search) as response:
            results = await response.json()
    
    news_results = results.get("news_results", None)
    top_stories = results.get("top_stories", None)
    
    news_results_keys = []
    top_stories_keys = []
    
async def get_formatted_key_values_from_list(keys: list, list_of_dictionaries: list) -> list:
    all_results = []

    for dictionary_index in range(1):
        formatted_str = await get_formatted_key_values(keys, list_of_dictionaries[dictionary_index])
        all_results.append(formatted_str)

    return all_results

async def get_formatted_key_values(keys: list, dictionary: dict, prefix="") -> str:
    formatted_str = ""

    for key in keys:
        if key in dictionary and dictionary[key]:
            if isinstance(dictionary[key], dict):
                # Handle nested dictionaries recursively
                nested_prefix = f"{prefix}{key}."
                formatted_str += await get_formatted_key_values(dictionary[key].keys(), dictionary[key], nested_prefix) + "\n"
            elif isinstance(dictionary[key], list) and all(isinstance(item, dict) for item in dictionary[key]):
                # Handle lists of dictionaries
                for idx, nested_dict in enumerate(dictionary[key], start=1):
                    nested_prefix = f"{prefix}{key}[{idx}]."
                    formatted_str += await get_formatted_key_values(nested_dict.keys(), nested_dict, nested_prefix) + "\n"
            else:
                #formatted_str += f"{prefix}{key} - {dictionary[key]}\n"
                formatted_str += f"{dictionary[key]}\n"

    return formatted_str.strip()