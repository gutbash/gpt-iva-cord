import aiohttp
import PyPDF2
import io
from bs4 import BeautifulSoup

def dummy_sync_function(tool_input: str) -> str:
    raise NotImplementedError("This tool only supports async")

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

async def get_important_text(url):
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.82 Safari/537.36',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
    }
    
    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.get(url) as response:
            
            content_type = response.headers.get("content-type", "").lower()
            #print(f"Content type: {content_type}")
            
            # Check if the content type is a PDF
            if "application/pdf" in content_type:
                
                # Read the PDF content into a BytesIO buffer
                pdf_content = await response.read()
                pdf_buffer = io.BytesIO(pdf_content)

                # Extract text from the PDF using PyPDF2
                reader = PyPDF2.PdfReader(pdf_buffer)
                important_text = ""
                
                for page_num in range(len(reader.pages)):
                    important_text += reader.pages[page_num].extract_text()
                
            elif "text/html" in content_type:
                
                content = await response.text()
                #print(f"HTML content: {content}")
                soup = BeautifulSoup(content, 'lxml')

                important_tags = ['p', 'li', 'ul', 'a', 'h1', 'h2', 'h3']
                important_text = ''

                for tag in important_tags:
                    elements = soup.find_all(tag)
                    for element in elements:
                        important_text += element.get_text(strip=True) + ' '
                        
                #print(f"Important text: {important_text}")
            else:
                print(f"Unknown content type for {url}: {content_type}")

            await session.close()
            
            return important_text