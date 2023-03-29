from serpapi import GoogleSearch
import requests
import random
import os

GOOGLE_API_KEY = os.getenv("GOOGLE_API_TOKEN")
GOOGLE_CSE_ID = os.getenv("GOOGLE_CSE_ID")
os.environ["GOOGLE_API_KEY"] = GOOGLE_API_KEY
SERPAPI_API_KEY = os.getenv("SERPAPI_API_KEY")

def get_top_search_result(query):
    try:
        # Configure the GoogleSearch object with the provided query and API key
        search = GoogleSearch({
            "q": query,
            "api_key": SERPAPI_API_KEY
        })

        # Perform the search and get the search results
        results = search.get_dict()
        organic_results = results.get("organic_results")

        # Return the URL of the top search result
        if organic_results and len(organic_results) > 0:
            return organic_results[0]["link"]
        else:
            return None

    except Exception as e:
        print(f"Error: {e}")
        return None
    
def get_image_from_search(query):
    # Replace YOUR_API_KEY and YOUR_CSE_ID with your own API key and CSE ID
    url = f"https://www.googleapis.com/customsearch/v1?q={query}&key={GOOGLE_API_KEY}&cx={GOOGLE_CSE_ID}&searchType=image"
    response = requests.get(url)
    results = response.json()
    # Extract the image URL for the first result (best/most relevant image)
    image_urls = [item['link'] for item in results['items'][:10]]
    chosen_image_url = random.choice(image_urls)
    return chosen_image_url