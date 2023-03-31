from serpapi import GoogleSearch
import requests
import random
import os

GOOGLE_API_KEY = os.getenv("GOOGLE_API_TOKEN")
GOOGLE_CSE_ID = os.getenv("GOOGLE_CSE_ID")
os.environ["GOOGLE_API_KEY"] = GOOGLE_API_KEY
SERPAPI_API_KEY = os.getenv("SERPAPI_API_KEY")

def get_top_search_results(query):
    try:
        # Configure the GoogleSearch object with the provided query and API key
        search = GoogleSearch({
            "q": query,
            "api_key": SERPAPI_API_KEY
        })

        # Perform the search and get the search results
        results = search.get_dict()
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
        result_list = []
        for result in top_results:
            result_list.append(f"{result['title']}\n{result['link']}\n{result['description']}")
            results =  "\n\n".join(result_list)

        return results

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