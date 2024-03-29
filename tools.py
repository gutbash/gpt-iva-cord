from serpapi import GoogleSearch
import random
import aiohttp
import os
import asyncio
import json
from bs4 import BeautifulSoup

import sys
import asyncio
from io import StringIO
from typing import Dict, Optional
from pydantic import BaseModel, Field

from utils.tool_utils import get_formatted_key_values, get_formatted_key_values_from_list, get_important_text

from langchain.docstore.document import Document
from langchain.chains.summarize import load_summarize_chain
from langchain.chains.question_answering import load_qa_chain
from langchain.text_splitter import TokenTextSplitter

GOOGLE_API_KEY = os.getenv("GOOGLE_API_TOKEN")
GOOGLE_CSE_ID = os.getenv("GOOGLE_CSE_ID")
SERPAPI_API_KEY = os.getenv("SERPAPI_API_KEY")
REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN")

text_splitter = TokenTextSplitter()

async def get_sublinks(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            content = await response.text()

    soup = BeautifulSoup(content, 'html.parser')

    sublinks = "\n\nLINKS WITHIN WEBPAGE:\n------\n\n"
    for link in soup.find_all('a'):
        href = link.get('href')
        text = link.text.strip()

        # Ignore empty text or href
        if not text or not href:
            continue

        # Ignore external links (optional)
        if not href.startswith(url) and not href.startswith('/') and not href.startswith('#'):
            continue

        # Append the base URL to relative links
        if href.startswith('/'):
            href = url.rstrip('/') + href

        sublinks += f"{text}: {href}\n"

    return sublinks
        
async def question_answer_webpage(url: str, question: str, llm) -> str:
    
    url = url.strip("[").strip("]")
    text = await get_important_text(url)

    print(text)

    texts = text_splitter.split_text(text)

    if not texts:
        return "No text found!"

    docs = [Document(page_content=t) for t in texts[:3]]

    """
    if len(docs) > 2:
        docs = docs[:2]
    """
    chain = load_qa_chain(llm, chain_type="map_reduce", verbose=True)
    #chain = load_qa_with_sources_chain(logical_llm, chain_type="map_reduce", verbose=True)
    answer = await chain.arun(input_documents=docs, question=question)
    #answer = await chain.arun({"input_documents": docs, "question": question}, return_only_outputs=True)
    
    return f"{answer}\n\nAdvice: If you need more information, use Webpage Window to read the page or use Search to search for something else.\nCitation: Remember that you must cite the URL {url} in your final response as a hyperlink like [title](https://www.example.com)."

async def view_webpage_window(url: str, span_index: int) -> str:
    
    url = url.strip("[").strip("]")
    text = await get_important_text(url)
    
    spans = []
    
    for span in range(0, len(text), 4096):
        subspan = text[span:span+4096]
        spans.append(subspan)
        
    if 0 <= span_index < len(spans):
        return f"\n---START OF PAGE {span_index}---\n{spans[span_index-1]}\n---END OF PAGE {span_index}---\n\nAdvice: If you need more information, explore pages 1-{len(spans)} or use Search for something else.\nCitation: Remember that you must cite the URL {url} in your final response as a hyperlink like [title](https://www.example.com)."
    else:
        return f"there are only {len(spans)} pages!"

async def summarize_webpage(url, llm):
    
    url = url.strip("[").strip("]")
    text = await get_important_text(url)
    
    print(text)

    #prepare and parse the text
    texts = text_splitter.split_text(text)

    if not texts:
        return "No text found!"

    docs = [Document(page_content=t) for t in texts[:3]]

    """
    if len(docs) > 2:
        docs = docs[:2]
    """
    #prepare chain
    chain = load_summarize_chain(llm, chain_type="map_reduce")
    #run summary
    summary = await chain.arun(docs)
    
    return f"{summary}\n"

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

async def get_organic_results(query: str, llm, recency_days: int = None) -> str:
    
    # Configure the GoogleSearch object with the provided query and API keyd
    search = {
        "engine": "google",
        "q": query,
        "api_key": SERPAPI_API_KEY,
        "gl": "us",
        "hl": "en",
        "safe": "active",
    }
    
    if recency_days != None:
        if recency_days <= 1:
            search["qdr"] = "d"
        elif recency_days <= 7:
            search["qdr"] = "w"
        elif recency_days <= 30:
            search["qdr"] = "m"
        else:
            search["qdr"] = "y"

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
        
        organic_results = "\n\n".join(organic_results)
        
        #first_result = organic_results_raw[0]
        #sublinks = await get_sublinks(first_result["link"])
        #organic_results += sublinks
        
    if knowledge_graph_raw is not None:
        
        knowledge_graph_keys = [
            "title",
            "type",
            "website",
            "description",
            "source",
        ]
        
        knowledge_graph = await get_formatted_key_values(knowledge_graph_keys, knowledge_graph_raw)
        knowledge_graph = f"{knowledge_graph}"
        
    final_results = f"\n\n{organic_results}\n\nAdvice: If you need to answer simple questions about the result, use Query Webpage. If you need to read specific information from the result, use Webpage Window. Otherwise, search for something else.\nCitation: Remember that you must cite the observation's URL in your final response as a hyperlink like [title](https://www.example.com)."
    
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
    
    if immersive_products_raw[0] is not None:
        
        immersive_products_keys = [
            "source",
            "title",
            "snippets",
            "rating",
            "price",
            "original_price",
        ]
        
        immersive_products = await get_formatted_key_values(immersive_products_keys, immersive_products_raw)
        immersive_products = f"\n\n{immersive_products}"
        
    if inline_products_raw[0] is not None:
        
        inline_products_keys = [
            "title",
            "source",
            "price",
            "original_price",
            "rating",
            "specifications",
        ]
        
        inline_products = await get_formatted_key_values(inline_products_keys, inline_products_raw)
        inline_products = f"\n\n{inline_products}"
        
    if shopping_results_raw[0] is not None:
        
        shopping_results_keys = [
            "title",
            "price",
            "link",
            "source",
            "rating",
        ]
        
        shopping_results = await get_formatted_key_values(shopping_results_keys, shopping_results_raw)
        shopping_results = f"\n\n{shopping_results}"
        
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
        product_result = f"\n\n{product_result}"
        
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
    
async def async_request(method, url, headers=None, data=None):
    async with aiohttp.ClientSession() as session:
        async with session.request(method, url, headers=headers, data=data) as response:
            return await response.json()

async def wait_for_completion(prediction_url, headers):
    status = 'starting'
    while status not in ('succeeded', 'error'):
        await asyncio.sleep(2)  # Wait for 2 seconds before sending the next request.
        response = await async_request('GET', prediction_url, headers=headers)
        status = response.get('status', '')

    return response
    
async def get_full_blip(image_url: str, question: str) -> str:
    description = await get_blip_recognition(image_url=image_url, caption=True)
    answer = await get_blip_recognition(image_url=image_url, question=question)
    
    caption = f"[Image Caption: {description}, Answer:{answer}]"
    
    return caption
    
async def get_blip_recognition(image_url: str, question: str = "What is this a picture of?", caption: bool = False, context: str = None) -> str:
    replicate_api_token = REPLICATE_API_TOKEN
    url = 'https://api.replicate.com/v1/predictions'
    headers = {
        'Authorization': f'Token {replicate_api_token}',
        'Content-Type': 'application/json',
    }
    data = json.dumps({
        'version': '4b32258c42e9efd4288bb9910bc532a69727f9acd26aa08e175713a0a857a608',
        'input': {
            'image': image_url,
            'caption': caption,
            'question': question,
            },
    })
    
    response = await async_request('POST', url, headers=headers, data=data)
    prediction_url = response['urls']['get']
    completed_response = await wait_for_completion(prediction_url, headers=headers)
    print(json.dumps(completed_response, indent=2))
    
    return completed_response['output']