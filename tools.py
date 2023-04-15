from serpapi import GoogleSearch
import random
import aiohttp
import os

GOOGLE_API_KEY = os.getenv("GOOGLE_API_TOKEN")
GOOGLE_CSE_ID = os.getenv("GOOGLE_CSE_ID")
os.environ["GOOGLE_API_KEY"] = GOOGLE_API_KEY
SERPAPI_API_KEY = os.getenv("SERPAPI_API_KEY")

async def get_top_search_results(query: str) -> str:
    try:
        # Configure the GoogleSearch object with the provided query and API key
        search = {
            "q": query,
            "api_key": SERPAPI_API_KEY,
            "gl": "us",
            "hl": "en",
            "safe": "active",
        }

        async with aiohttp.ClientSession() as session:
            async with session.get("https://serpapi.com/search", params=search) as response:
                results = await response.json()

        organic_results = results.get("organic_results")

        # Extract the URLs and short descriptions of the top 10 search results
        top_results = []
        if organic_results and len(organic_results) > 0:
            for i in range(3):
                if i < len(organic_results):
                    result = {}
                    result["title"] = organic_results[i]["title"]
                    result["link"] = organic_results[i]["link"]
                    result["description"] = organic_results[i].get("snippet", "No snippet available.")
                    top_results.append(result)
                else:
                    break

        # Format the results as a plain text unordered list
        results = ""
        for result_index in range(len(top_results)):
            results += f"\n\n[Result {result_index + 1}]\nTitle: {top_results[result_index]['title']}\nURL: {top_results[result_index]['link']}\nDescription: {top_results[result_index]['description']}"

        return results

    except Exception as e:
        print(f"Error: {e}")
        return None

    
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
    
    organic_results = ""
    knowledge_graph = ""
    
    if organic_results_raw is not None:
        
        organic_results_keys = [
            #"position",
            "title",
            "link",
            "snippet",
            "sitelinks",
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
        
    final_results = f"\n\n{organic_results}{knowledge_graph}"
    
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
    
    immersive_products = results.get("immersive_products", None)
    inline_products = results.get("inline_products", None)
    shopping_results = results.get("shopping_results", None)
    product_result = results.get("product_result", None)
    
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
                formatted_str += f"{prefix}{key} - {dictionary[key]}\n"

    return formatted_str.strip()