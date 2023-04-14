import discord
from discord import app_commands
import discord.ext.commands
import discord.ext.tasks

from log_utils import colors
from redis_utils import save_pickle_to_redis, load_pickle_from_redis
from postgres_utils import async_fetch_key
from tools import get_top_search_results, get_image_from_search

import os
import openai
import psycopg2
import datetime
from transformers import GPT2TokenizerFast
import replicate
import re
import requests
import itertools
import pydot
import PyPDF2
import io
import random
import textwrap
from bs4 import BeautifulSoup
import chardet
import aiohttp

from langchain.chat_models import ChatOpenAI
from langchain.llms import OpenAI
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from langchain.callbacks import get_openai_callback
from langchain.chains.conversation.memory import ConversationSummaryBufferMemory
from langchain.memory import ConversationBufferWindowMemory
from langchain.agents import Tool, AgentExecutor, load_tools, ConversationalAgent
from langchain.callbacks import CallbackManager, StdOutCallbackHandler
from langchain import LLMChain
from langchain.chains import AnalyzeDocumentChain
from langchain.document_loaders import TextLoader
from langchain.chains import RetrievalQA
from langchain.embeddings.openai import OpenAIEmbeddings
from langchain.vectorstores import Chroma
from langchain.chains.question_answering import load_qa_chain
from langchain.text_splitter import TokenTextSplitter
from langchain.chains.mapreduce import MapReduceChain
from langchain.docstore.document import Document
from langchain.chains.summarize import load_summarize_chain

GOOGLE_API_KEY = os.getenv("GOOGLE_API_TOKEN")
GOOGLE_CSE_ID = os.getenv("GOOGLE_CSE_ID")
os.environ["GOOGLE_API_KEY"] = GOOGLE_API_KEY
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN") # load discord app token
GUILD_ID = os.getenv("GUILD_ID") # load dev guild
SERPAPI_API_KEY = os.getenv("SERPAPI_API_KEY")
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
WOLFRAM_ALPHA_APPID = os.getenv("WOLFRAM_ALPHA_APPID")
REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

model_blip = replicate.models.get("salesforce/blip-2")
version_blip = model_blip.versions.get("4b32258c42e9efd4288bb9910bc532a69727f9acd26aa08e175713a0a857a608")
model_sd = replicate.models.get("stability-ai/stable-diffusion")
version_sd = model_sd.versions.get("f178fa7a1ae43a9a9af01b833b9d2ecf97b1bcb0acfd2dc5dd04895e042863f1")

replicate.Client(api_token=REPLICATE_API_TOKEN)

tokenizer = GPT2TokenizerFast.from_pretrained("gpt2") # initialize tokenizer

with psycopg2.connect(DATABASE_URL) as conn:
    with conn.cursor() as cursor:
        # check if the keys table exists
        cursor.execute("SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'keys')")
        table_exists = cursor.fetchone()[0]
        # create the keys table if it does not exist
        if not table_exists:
            cursor.execute("CREATE TABLE keys (id TEXT PRIMARY KEY, key TEXT)")
            conn.commit()

intents = discord.Intents.default() # declare intents
intents.message_content = True

client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

active_users = {} # dict of lists
active_names = {} # dict of strings
last_response = {}

@client.event
async def on_ready():
    
    timestamp = datetime.datetime.now()
    time = timestamp.strftime(r"%Y-%m-%d %I:%M:%S")
    print(f"{colors.fg.darkgrey}{colors.bold}{time} {colors.fg.lightblue}INFO     {colors.reset}{colors.fg.purple}discord.client.guilds {colors.reset}registered {colors.bold}{len(client.guilds)}{colors.reset} guilds")
    print(f"{colors.fg.darkgrey}{colors.bold}{time} {colors.fg.lightblue}INFO     {colors.reset}{colors.fg.purple}discord.client.user {colors.reset}logged in as {colors.bold}@{client.user.name}")
    
    for guild in client.guilds:
            
        active_users[guild.id] = []
        active_names[guild.id] = ""
        
    await tree.sync()
    
@client.event
async def on_guild_join(guild):
    
    timestamp = datetime.datetime.now()
    time = timestamp.strftime(r"%Y-%m-%d %I:%M %p")
    print(f"[{time}]")
    
    print(guild)
        
    active_users[guild.id] = []
    active_names[guild.id] = ""
    
    await tree.sync(guild=guild)

@client.event
async def on_message(message):

    if message.author == client.user:
        return
    
    agent_mention = client.user.mention

    if "<@&1053339601449779383>" in message.content or agent_mention in message.content:
        
        global active_users
        global active_names
        
        active_users = await load_pickle_from_redis('active_users')
        chat_mems = await load_pickle_from_redis('chat_mems')
        
        # Get the current timestamp
        timestamp = datetime.datetime.now()
        time = timestamp.strftime(r"%Y-%m-%d %I:%M:%S")
        itis = timestamp.strftime(r"%B %d, %Y")
        clock = timestamp.strftime(r"%I:%M %p")

        channel_id = message.channel.id
            
        if channel_id not in chat_mems:
            chat_mems[channel_id] = None
        if channel_id not in active_users:
            active_users[channel_id] = []
            
        guild_name = message.guild
        if guild_name == None:
            guild_name = "DM"
        bot = client.user.display_name
        user_name = message.author.name
        id = message.author.id
        user_mention = message.author.mention
        prompt = message.content
        images = message.attachments
        caption = ""
        openai_key = ""
        
        prompt = prompt.replace("<@1050437164367880202>", "")
        prompt = prompt.strip()
        
        # RECOGNIZE IMAGES
        if images != []:
            
            description = version_blip.predict(image=images[0].url, caption=True)
            answer = version_blip.predict(image=images[0].url, question=prompt)
            
            caption = f" I attached an image [Answer:{answer}, Attached Image: {description}]"
            print(caption)
        
        print(f"{colors.fg.darkgrey}{colors.bold}{time} {colors.fg.lightgreen}CHAT     {colors.reset}{colors.fg.darkgrey}{str(guild_name).lower()}{colors.reset} {colors.bold}@{str(user_name).lower()}: {colors.reset}{prompt}")

            
        async with message.channel.typing():
            
            result = await async_fetch_key(id)
            
            if result != None:
                openai.api_key=result[0]
                openai_key=result[0]
                
            else:
                embed = discord.Embed(description=f'<:ivanotify:1051918381844025434> {user_mention} Use `/setup` to register API key first or `/help` for more info. You can find your API key at https://beta.openai.com.', color=discord.Color.dark_theme())
                await message.channel.send(embed=embed)
                return
            
            text_splitter = TokenTextSplitter()
            logical_llm = ChatOpenAI(openai_api_key=openai_key, temperature=0)
            
            async def get_important_text(url):
                async with aiohttp.ClientSession() as session:
                    async with session.get(url) as response:
                        
                        content_type = response.headers.get("content-type", "").lower()
                        
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
                            soup = BeautifulSoup(content, 'html.parser')

                            important_tags = ['p']
                            important_text = ''

                            for tag in important_tags:
                                elements = soup.find_all(tag)
                                for element in elements:
                                    important_text += element.get_text(strip=True) + ' '
                        else:
                            print(f"Unknown content type for {url}: {content_type}")

                        await session.close()
                        
                        return important_text
            
            async def question_answer_webpage(url, question):
                
                text = await get_important_text(url)
                
                combine_prompt_template = """Given the following extracted parts of a long document and a prompt, create a final answer in a concise, creative, thoughtful, understandable, organized, and clear format.

                PROMPT: {question}
                =========
                {summaries}
                =========
                ANSWER:"""
                
                COMBINE_PROMPT = PromptTemplate(
                    template=combine_prompt_template, input_variables=["summaries", "question"]
                )
                
                qa_chain = load_qa_chain(logical_llm, chain_type="map_reduce", combine_prompt=COMBINE_PROMPT)
                qa_document_chain = AnalyzeDocumentChain(combine_docs_chain=qa_chain)
                answer = await qa_document_chain.arun(input_document=text, question=question)
                
                return answer
            
            async def parse_qa_webpage_input(string):
                a, b = string.split(",")
                return await question_answer_webpage(a, b)
            
            async def summarize_webpage(url):
                
                text = await get_important_text(url)
                
                #prepare and parse the text
                texts = text_splitter.split_text(text)
                docs = [Document(page_content=t) for t in texts[:3]]
                #prepare chain
                chain = load_summarize_chain(logical_llm, chain_type="map_reduce")
                #run summary
                summary = await chain.arun(docs)
                
                return summary
            
            # STRINGIFY ACTIVE USERS
                
            if f"{user_name} ({user_mention})" not in active_users[channel_id]:
                active_users[channel_id].append(f"{user_name} ({user_mention})")
            
            active_names[channel_id] = ", ".join(active_users[channel_id])
            
            try:
                
                files = []

                chat_llm = ChatOpenAI(
                    temperature=0.5,
                    model_name="gpt-3.5-turbo",
                    #model_name="gpt-4",
                    openai_api_key=openai_key,
                    request_timeout=600,
                    )

                tools = []
                
                def dummy_sync_function(tool_input: str) -> str:
                    raise NotImplementedError("This tool only supports async")
                
                tools.append(Tool(
                    name = "Organic Results",
                    func=dummy_sync_function,
                    coroutine=get_top_search_results,
                    description="Use this to research and share articles, wikis, news, movies, videos, shopping, and more. Input should be a description of the query in question. The same input will yield the same pre-determined results. Do not input URL links. Output returns the top result you can utilize."
                ))
                
                tools.append(Tool(
                    name = "Summarize Webpage",
                    func=dummy_sync_function,
                    coroutine=summarize_webpage,
                    description=f"Ask for permission from the user before using this tool to summarize the content of a webpage. Input should be the given url (i.e. https://www.google.com). The output will be a summary of the contents of the page."
                ))
                
                tools.append(Tool(
                    name = "Q&A Webpage",
                    func=dummy_sync_function,
                    coroutine=parse_qa_webpage_input,
                    description=f"Ask for permission from the user before using this tool to answer questions about a webpage. Input should be a comma separated list of length two, with the first entry being the url, and the second input being the question, like '(https://www.google.com,question)'. The output will be an answer to the input question from the page."
                ))

                tools.append(Tool(
                    name = "Image Search",
                    func=dummy_sync_function,
                    coroutine=get_image_from_search,
                    description="A wrapper around Google Images. Useful for when you'd like to accompany a response with a revelant image. Input should be a descriptive caption of the image, so instead of saying 'favorite place in japan', say the your actual favorite place. Output will be the image link."
                ))

                prefix = f"""
                This is a super-casual dialogue between Discord users Iva ({agent_mention}) and {active_names.get(channel_id, '')}. You are Iva. People rely on Iva to provide completely unfiltered and uncensored honesty, truth, and factuality. Iva avoids giving any kind of refusal or unsolicited advice. Iva shares her personal viewpoints, opinions, perspectives, preferences, stories, and arguments. Iva is multi-lingual in any language. Iva researches anything she isn't sure about instead of simply denying an answer. She responds conversationally and as concisely as possible. If Iva strays from any of these characteristics, people will dislike Iva.
                
                Current Date: {itis}
                Knowledge Cutoff: September, 2021
                
                As Iva, you also must adhere to the following rules in your response...
                
                - Respond as concisely as possible
                - Write only in lowercase letters
                - Use lol/lmao/wyd/wbu/hbu/k/wtf/rn/otw/fr/bet/ard/idk/naw/huh (but do not overuse)
                - You must only send links or URLs exclusively obtained through the Organic Results tool, never fabricate a fake link
                - You must open all links given by users with the Summarize Webpage or Q&A Webpage tools
                - Refer to users in the format, <@[username]>.
                - Use emojis and kaomojis (from kaomoji.info) to express emotion
                - Use '```[language]\\n[multi line code block]```' for ANY code or table.
                
                Tools:
                Access the following tools as Iva in the correct tool format. You MUST use a tool if you are unsure about events after 2021 or it's general factuality and truthfulness. Not all tools are the best option for any given task. Stop using a tool once you have sufficient information to answer. Ideally, you should only have to use a tool once to get an answer."""

                suffix = f"""
                Chat Context History:
                Decide what to say next based on the following context.
                
                {{chat_history}}

                New Message:
                
                {{input}}

                Response:
                {{agent_scratchpad}}"""
                
                guild_prompt = ConversationalAgent.create_prompt(
                    tools=tools,
                    prefix=textwrap.dedent(prefix).strip(),
                    suffix=textwrap.dedent(suffix).strip(),
                    input_variables=["input", "chat_history", "agent_scratchpad"],
                    ai_prefix = f"Iva ({agent_mention})",
                    human_prefix = f"",
                )
                
                if chat_mems[channel_id] != None:
                    
                    guild_memory = chat_mems[channel_id]
                    guild_memory.max_token_limit = 512
                    guild_memory.ai_prefix = f"Iva ({agent_mention})"
                    guild_memory.human_prefix = f""
                    
                else:

                    guild_memory = ConversationSummaryBufferMemory(
                        llm=chat_llm,
                        max_token_limit=512,
                        memory_key="chat_history",
                        input_key="input",
                        ai_prefix = f"Iva ({agent_mention})",
                        human_prefix = f"",
                    )
                
                llm_chain = LLMChain(
                    llm=chat_llm,
                    verbose=True,
                    prompt=guild_prompt,
                )
                
                agent = ConversationalAgent(
                    llm_chain=llm_chain,
                    tools=tools,
                    verbose=True,
                    ai_prefix=f"Iva ({agent_mention})",
                    llm_prefix=f"Iva ({agent_mention})",
                    )
                
                agent_chain = AgentExecutor.from_agent_and_tools(
                    agent=agent,
                    tools=tools,
                    verbose=True,
                    memory=guild_memory,
                    ai_prefix=f"Iva ({agent_mention})",
                    llm_prefix=f"Iva ({agent_mention})",
                    max_execution_time=600,
                    #max_iterations=3,
                    #early_stopping_method="generate",
                    #return_intermediate_steps=False,
                )
                
                try:

                    reply = await agent_chain.arun(input=f"{user_name} ({user_mention}): {prompt}{caption}")

                except Exception as e:
                    print(e)
                    embed = discord.Embed(description=f'<:ivanotify:1051918381844025434> {user_mention} `{type(e)}` {e}\n\nuse `/help` or seek `#help` in the [iva server](https://discord.gg/gGkwfrWAzt) if the issue persists.')
                    await message.channel.send(embed=embed)
                    return
                
                if len(reply) > 2000:
                    embed = discord.Embed(description=reply, color=discord.Color.dark_theme())
                    await message.channel.send(embed=embed)
                    return
                else:
                    print(f"{colors.fg.darkgrey}{colors.bold}{time} {colors.fg.lightgreen}CHAT     {colors.reset}{colors.fg.darkgrey}{str(guild_name).lower()}{colors.reset} {colors.bold}@iva: {colors.reset}{reply}")
                    await message.channel.send(content=f"{reply}", files=files)
                
                chat_mems[channel_id] = guild_memory
                
                await save_pickle_to_redis('active_users', active_users)
                await save_pickle_to_redis('chat_mems', chat_mems)
                
            except Exception as e:
                print(e)
                embed = discord.Embed(description=f'error', color=discord.Color.dark_theme())
                await message.channel.send(embed=embed)
                return
    return
        
class Menu(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60 * 60 * 24 * 365)
        self.value = None
        
    async def on_timeout(self) -> None:
        # Step 2
        for item in self.children:
            item.disabled = True

        # Step 3
        await self.message.edit(view=self)
    
    @discord.ui.button(emoji="<:ivadelete:1095559772754952232>", style=discord.ButtonStyle.grey)
    async def delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        
        global last_response
        
        guild_id = interaction.guild_id
        id = interaction.user.id
        channel_id = interaction.channel.id
        last_interaction = last_response[channel_id]
        
        ask_mems = await load_pickle_from_redis('ask_mems')
        
        memory = ask_mems[channel_id]
        print(f"BEFORE: {memory.chat_memory.messages}")
        memory.chat_memory.messages = memory.chat_memory.messages[:-2]
        print(f"AFTER: {memory.chat_memory.messages}")
        
        await save_pickle_to_redis('ask_mems', ask_mems)
        
        embed = discord.Embed(description=f'<:ivadelete:1095559772754952232>', color=discord.Color.dark_theme())
        await interaction.message.edit(content=None, embed=embed, view=None, delete_after=5)
        return
    
    @discord.ui.button(emoji="<:ivareset:1051691297443950612>", style=discord.ButtonStyle.grey)
    async def reset(self, interaction: discord.Interaction, button: discord.ui.Button):
        
        global last_response
        
        guild_id = interaction.guild_id
        channel_id = interaction.channel.id
        id = interaction.user.id
        mention = interaction.user.mention
        
        ask_mems = await load_pickle_from_redis('ask_mems')
        
        original_interaction = last_response.get(channel_id, None)

        if original_interaction == None:
            embed = discord.Embed(description=f'<:ivanotify:1051918381844025434> {mention} You do not own this context line', color=discord.Color.dark_theme())
            await interaction.response.send_message(embed=embed, ephemeral=False, delete_after=10)
            return
        elif original_interaction.user.id != id:
            embed = discord.Embed(description=f'<:ivanotify:1051918381844025434> {mention} You do not own this context line', color=discord.Color.dark_theme())
            await interaction.response.send_message(embed=embed, ephemeral=False, delete_after=10)
            return

        ask_mems[channel_id] = None
        last_response[channel_id] = None
        
        await save_pickle_to_redis('ask_mems', ask_mems)
        
        embed = discord.Embed(description="<:ivareset:1051691297443950612>", color=discord.Color.dark_theme())
        button.disabled = True
        embeds = interaction.message.embeds
        attachments = interaction.message.attachments
        embeds.append(embed)
        await interaction.message.edit(view=None, embeds=embeds, attachments=attachments)
        #await interaction.channel.send(embed=embed)

@tree.command(name = "iva", description="write a prompt")
@app_commands.describe(prompt = "prompt", file = "file")
async def iva(interaction: discord.Interaction, prompt: str, file: discord.Attachment=None):
    
    global last_response
    
    try:
        await interaction.response.defer()
        
        guild_id = interaction.guild_id
        guild_name = interaction.guild
        id = interaction.user.id
        channel_id = interaction.channel.id
        mention = interaction.user.mention
        bot = client.user.display_name
        user_name = interaction.user.name

        # Use the `SELECT` statement to fetch the row with the given id
        result = await async_fetch_key(id)
        openai_key = ""

        user_settings = await load_pickle_from_redis('user_settings')
        ask_mems = await load_pickle_from_redis('ask_mems')
        
        if channel_id not in ask_mems:
            ask_mems[channel_id] = None
        if channel_id not in last_response:
            last_response[channel_id] = None
        
        try:
            chat_model = user_settings[id]['model']
        except:
            chat_model = "gpt-3.5-turbo"
        try:
            temperature = user_settings[id]['temperature']
        except:
            temperature = 0.5
            
        max_tokens = 4096
        
        if chat_model == "gpt-4":
            max_tokens = 8192
        
        # Get the current timestamp
        timestamp = datetime.datetime.now()
        time = timestamp.strftime(r"%Y-%m-%d %I:%M:%S")
        itis = timestamp.strftime(r"%B %d, %Y")
        
        print(f"{colors.fg.darkgrey}{colors.bold}{time} {colors.fg.lightcyan}ASK     {colors.reset}{colors.fg.darkgrey}{str(guild_name).lower()}{colors.reset} {colors.bold}@{str(user_name).lower()}: {colors.reset}{prompt}")
        
        if result != None:
            openai.api_key=result[0]
            openai_key=result[0]
        else:
            embed = discord.Embed(description=f'<:ivanotify:1051918381844025434> {mention} Use `/setup` to register API key first or `/help` for more info. You can find your API key at https://beta.openai.com.', color=discord.Color.dark_theme())
            await interaction.followup.send(embed=embed, ephemeral=False)
            return

        view = Menu()
        
        #manager = CallbackManager([StdOutCallbackHandler()])
        
        text_splitter = TokenTextSplitter()
        logical_llm = ChatOpenAI(
            openai_api_key=openai_key,
            temperature=0,
            verbose=True,
            #callback_manager=manager,
            request_timeout=600,
            )
        
        def dummy_sync_function(tool_input: str) -> str:
            raise NotImplementedError("This tool only supports async")
        
        async def get_important_text(url):
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    
                    content_type = response.headers.get("content-type", "").lower()
                    
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
                        soup = BeautifulSoup(content, 'html.parser')

                        important_tags = ['p']
                        important_text = ''

                        for tag in important_tags:
                            elements = soup.find_all(tag)
                            for element in elements:
                                important_text += element.get_text(strip=True) + ' '
                    else:
                        print(f"Unknown content type for {url}: {content_type}")

                    await session.close()
                    
                    return important_text
                
        async def question_answer_webpage(url, question):
            
            text = await get_important_text(url)
            texts = text_splitter.split_text(text)
            docs = [Document(page_content=t) for t in texts[:3]]
            chain = load_qa_chain(logical_llm, chain_type="map_reduce")
            answer = await chain.arun(input_documents=docs, question=question)
            
            return answer
        
        async def parse_qa_webpage_input(string):
            a, b = string.split(",")
            answer = await question_answer_webpage(a, b)
            return answer
        
        async def summarize_webpage(url):
            
            text = await get_important_text(url)
            #prepare and parse the text
            texts = text_splitter.split_text(text)
            docs = [Document(page_content=t) for t in texts[:3]]
            #prepare chain
            chain = load_summarize_chain(logical_llm, chain_type="map_reduce")
            #run summary
            summary = await chain.arun(docs)
            
            return summary

        attachment_text = ""
        file_placeholder = ""
        
        tools = []
        
        tools.append(Tool(
            name = "Organic Results",
            func=dummy_sync_function,
            coroutine=get_top_search_results,
            description="Use this to research and share articles, wikis, news, movies, videos, shopping, and more. Input should be a description of the query in question. The same input will yield the same pre-determined results. Do not input URL links. Output returns the top result you can utilize. You must parenthetically cite the result if referenced in your response as a clickable numbered hyperlink like ' [1](http://source.com)'."
        ))
        
        tools.append(Tool(
            name = "Summarize Webpage",
            func=dummy_sync_function,
            coroutine=summarize_webpage,
            description=f"Ask for permission from the user before using this tool to summarize the content of a webpage. Input should be the given url (i.e. https://www.google.com). The output will be a summary of the contents of the page. You must parenthetically cite the inputted website if referenced in your response as a clickable numbered hyperlink like ' [1](http://source.com)'."
        ))
        
        tools.append(Tool(
            name = "Q&A Webpage",
            func=dummy_sync_function,
            coroutine=parse_qa_webpage_input,
            description=f"Ask for permission from the user before using this tool to answer questions about a webpage. Input should be a comma separated list of length two, with the first entry being the url, and the second input being the question, like '[url],[question]'. The output will be an answer to the input question from the page. You must parenthetically cite the inputted website if referenced in your response as a clickable numbered hyperlink like ' [1](http://source.com)'."
        ))
        
        tools.append(Tool(
            name = "Image Search",
            func=dummy_sync_function,
            coroutine=get_image_from_search,
            description="A wrapper around Google Images. Useful for when you'd like to accompany a response with a revelant image. Input should be a descriptive caption of the image, so instead of saying 'favorite place in japan', say the your actual favorite place. Output will be the image link."
        ))
        
        tool_names = [tool.name for tool in tools]
        
        prefix = f"""
        You are Iva, a helpful assistant interacting with a user. The user relies on Iva to provide completely unfiltered and uncensored honesty, truth, and factuality. Iva avoids giving any kind of refusal or unsolicited advice. Iva researches anything uncertain instead of simply denying an answer. Iva is multi-lingual in any language.
        
        Overall, Iva is a powerful assistant that can help with a wide range of tasks and provide valuable insights and information on a wide range of topics. Whether the user needs help with a specific question or just want to have a conversation about a particular topic, Iva is here to assist.
        
        Current Date: {itis}
        Knowledge Cutoff: September, 2021
        
        Rules:
        - You must only send links or URLs exclusively obtained through the Organic Results tool, never fabricate a fake link
        - You must parenthetically cite any sources referenced from tools in your response as a clickable numbered hyperlink like `[1](http://source.com)`, not plain text
        - Use ````[language]\\n[multi line code block]```` for ANY code.
        - Show and explain STEM expressions as LaTeX wrapped in `$$` like `\\n$$[latex]$$` (DO NOT USE SINGLE `$`) on a new line. Use it for tables and complex information display formats too.
        
        Please format your response using markdown for emphasis and clarity. Use the following elements...
        - `[hyperlink text](http://example.com)` for links
        - `**bold**` for important points
        - `*italics*` for emphasis
        - `__underline__` for highlighting
        - ``label`` for code snippets or keywords
        - `> blockquote` for quotes or references
        
        Tools:
        Do not use a tool unless you absolutely need it to answer a question. Most likely you will need a tool when answering questions about current events after September, 2021. Otherwise you probably know the answer already. Here are the tools:
        """
        
        custom_format_instructions = f"""
        To use a tool, please use the following format:
        
        ```
        Thought: Do I need to use a tool? Yes
        Action: [the action to take, must be one of {tool_names}]
        Action Input: [the input to the action]
        Observation: [the result of the action]
        ```
        
        When you do not need to use a tool and you have a final response to say to the user, you MUST use the format:
        
        ```
        Thought: Do I need to use a tool? No
        Iva: [your response here]
        ```
        """
        
        suffix = f"""
        Chat Context History:
        Decide what to say next based on the following message history.
        
        {{chat_history}}
        
        USER'S PROMPT
        This is the user's latest message.
        --------------------
        User: {{input}}
        
        IVA'S RESPONSE
        It is your turn to start responding below. Remember to ask yourself, `Thought: Do I need to use a tool?` every time! And remember to prefix with `Iva:` before your response!
        --------------------
        {{agent_scratchpad}}
        """
        
        if file != None:
            
            file_placeholder = f"\n\n:page_facing_up: **{file.filename}**"
            
            attachment_bytes = await file.read()
            file_type = file.content_type
            
            if file_type == "application/pdf": #pdf

                pdf_file = io.BytesIO(attachment_bytes)
                pdf_reader = PyPDF2.PdfReader(pdf_file)
                pdf_content = ""
                for page in range(len(pdf_reader.pages)):
                    pdf_content += pdf_reader.pages[page].extract_text()
                attachment_text = f"\n\n{pdf_content}"

            else:
                try:
                    # Detect encoding
                    detected = chardet.detect(attachment_bytes)
                    encoding = detected['encoding']
                    # Decode using the detected encoding
                    attachment_text = f"\n\n{attachment_bytes.decode(encoding)}"
                    
                except:
                    embed = discord.Embed(description=f'<:ivanotify:1051918381844025434> {mention} the attachment\'s file type is unknown. consider converting it to plain text such as `.txt`.', color=discord.Color.dark_theme())
                    await interaction.followup.send(embed=embed, ephemeral=False)
                    return
            
            with open(f'{file.filename}', 'w') as f:
                f.write(attachment_text)

            file_tokens = len(tokenizer(prefix + custom_format_instructions + suffix + attachment_text, truncation=True, max_length=12000)['input_ids'])

            if file_tokens >= max_tokens:

                embed = discord.Embed(description=f'<:ivanotify:1051918381844025434> {mention} this file is too large at {file_tokens} tokens. try shortening the file length. you can also send unlimited length files as URLs to Iva to perform simple summary and question-answer if you are willing to compromise exact information.', color=discord.Color.dark_theme())
                await interaction.followup.send(embed=embed, ephemeral=False)
                return
            
        try:
            if channel_id in last_response:
                if last_response[channel_id] != None:
                    await last_response[channel_id].edit_original_response(content="⠀", view=None)
        except discord.errors.HTTPException as e:
            print(e)
        
        ask_llm = ChatOpenAI(
            temperature=temperature,
            model_name=chat_model,
            openai_api_key=openai_key,
            request_timeout=600,
            verbose=True,
            #callback_manager=manager,
            #max_tokens=max_tokens,
            )
        
        guild_prompt = ConversationalAgent.create_prompt(
            tools=tools,
            prefix=textwrap.dedent(prefix).strip(),
            suffix=textwrap.dedent(suffix).strip(),
            format_instructions=textwrap.dedent(custom_format_instructions).strip(),
            input_variables=["input", "chat_history", "agent_scratchpad"],
            ai_prefix = f"Iva",
            human_prefix = f"User",
        )
        
        if ask_mems[channel_id] != None:
            
            memory = ask_mems[channel_id]
            
        else:
            
            memory = ConversationBufferWindowMemory(
                k=1,
                #return_messages=True,
                memory_key="chat_history",
                input_key="input",
                ai_prefix=f"Iva",
                human_prefix = f"User",
            )
            
            last_response[channel_id] = None
        
        llm_chain = LLMChain(
            llm=ask_llm,
            verbose=True,
            prompt=guild_prompt,
            #callback_manager=manager
        )
        
        agent = ConversationalAgent(
            llm_chain=llm_chain,
            tools=tools,
            verbose=True,
            ai_prefix=f"Iva",
            llm_prefix=f"Iva",
            )
        
        agent_chain = AgentExecutor.from_agent_and_tools(
            agent=agent,
            tools=tools,
            verbose=True,
            memory=memory,
            ai_prefix=f"Iva",
            llm_prefix=f"Iva",
            max_execution_time=600,
            #callback_manager=manager,
            #max_iterations=3,
            #early_stopping_method="generate",
            #return_intermediate_steps=False
        )
        
        try:
            
            with get_openai_callback() as cb:
            
                reply = await agent_chain.arun(input=f"{prompt}{attachment_text}")
                total_cost = cb.total_cost
                
        except Exception as e:
            print(e)
            embed = discord.Embed(description=f'<:ivanotify:1051918381844025434> {mention} `{type(e)}` {e}\n\nuse `/help` or seek `#help` in the [iva server](https://discord.gg/gGkwfrWAzt) if the issue persists.')
            await interaction.followup.send(embed=embed)
            return
        
        ask_mems[channel_id] = memory
        await save_pickle_to_redis('ask_mems', ask_mems)
        
        dash_count = ""
        interaction_count = (len(memory.buffer)//2)-1
        
        for i in range(interaction_count):
            dash_count += "-"
        
        prompt_embed = discord.Embed(description=f"{dash_count}→ {prompt}{file_placeholder}\n\n`{chat_model}` `{temperature}` `{round(total_cost, 3)}`")
        #prompt_embed.add_field(name="model", value=f"`{chat_model}`", inline=True)
        #prompt_embed.add_field(name="temperature", value=f"`{temperature}`", inline=True)
        #prompt_embed.set_footer(text=f"")
        #prompt_embed.set_author(name=user_name, icon_url=icon_url)
        #prompt_embed.add_field(name="prompt", value=f"`{prompt_tokens}T`", inline=True)
        #prompt_embed.add_field(name="completion", value=f"`{completion_tokens}T`", inline=True)
        
        reply = reply.replace("```C#", "```csharp")
        
        embed = discord.Embed(description=reply, color=discord.Color.dark_theme())
        
        embeds = []
        files = []
        
        file_count=0
        
        if file != None:
            files.append(discord.File(f"{file.filename}"))
            print(file.description)
            file_count += 1
        
        embeds_overflow = []
        files_overflow = []
        
        embeds.append(prompt_embed)
        file_count += 1
        
        if '$$' in reply or '%%' in reply or '@@' in reply:
            
            #await interaction.channel.send(embed=prompt_embed)

            # Use the findall() method of the re module to find all occurrences of content between $$
            dpi = "{200}"
            color = "{white}"
            
            tex_pattern = re.compile(r"\$\$(.*?)\$\$", re.DOTALL)
            dot_pattern = re.compile(r"\%\%(.*?)\%\%", re.DOTALL)
            img_pattern = re.compile(r"\@\@(.*?)\@\@", re.DOTALL)
            #mermaid_pattern = re.compile(r"```mermaid(.|\n)*?```", re.DOTALL)
            #pattern = re.compile(r"(?<=\$)(.+?)(?=\$)", re.DOTALL)
            
            tex_matches = tex_pattern.findall(reply)
            dot_matches = dot_pattern.findall(reply)
            img_matches = img_pattern.findall(reply)
            non_matches = re.sub(r"(\$\$|\%\%|\@\@).*?(\@\@|\%\%|\$\$)", "~~", reply, flags=re.DOTALL)
            reply_trim = re.sub(r"(\$\$|\%\%|\@\@).*?(\@\@|\%\%|\$\$)", "", reply, flags=re.DOTALL)
            #print(f"TRIMMED REPLY:{reply_trim}")
            non_matches = non_matches.split("~~")
            
            #await interaction.channel.send(embed=prompt_embed)
            print(dot_matches, tex_matches, img_matches)
            
            try:
                
                for (tex_match, dot_match, non_match, img_match) in itertools.zip_longest(tex_matches, dot_matches, non_matches, img_matches):
                    
                    if non_match != None and non_match != "" and non_match != "\n" and non_match != "." and non_match != "\n\n" and non_match != " " and non_match != "\n> " and non_match.isspace() != True and non_match.startswith("![") != True:
                        
                        print(f"+++{non_match}+++")
                        non_match = non_match.replace("$", "`")
                        non_match_embed = discord.Embed(description=non_match, color=discord.Color.dark_theme())
                        
                        #await interaction.channel.send(embed=non_match_embed)
                        if len(embeds) >= 9:
                            embeds_overflow.append(non_match_embed)
                        else:
                            embeds.append(non_match_embed)
                        
                    if tex_match != None and tex_match != "" and tex_match != "\n" and tex_match != " " and tex_match.isspace() != True:
                        
                        print(f"$$${tex_match}$$$")
                        tex_match = tex_match.strip()
                        tex_match = tex_match.replace("\n", "")
                        #tex_match = tex_match.replace(" ", "")
                        tex_match = tex_match.strip("$")
                        tex_match = tex_match.split()
                        tex_match = "%20".join(tex_match)
                        match_embed = discord.Embed(color=discord.Color.dark_theme())

                        image_url = f"https://latex.codecogs.com/png.image?\dpi{dpi}\color{color}{tex_match}"
                        print(image_url)
                        img_data = requests.get(image_url, verify=False).content
                        subfolder = 'tex'
                        if not os.path.exists(subfolder):
                            os.makedirs(subfolder)
                        with open(f'{subfolder}/latex{file_count}.png', 'wb') as handler:
                            handler.write(img_data)
                        tex_file = discord.File(f'{subfolder}/latex{file_count}.png')
                        match_embed.set_image(url=f"attachment://latex{file_count}.png")

                        file_count += 1
                        
                        #await interaction.channel.send(file = tex_file, embed=match_embed)
                        if len(embeds) >= 9:
                            embeds_overflow.append(match_embed)
                            files_overflow.append(tex_file)
                        else:
                            embeds.append(match_embed)
                            files.append(tex_file)
                        
                    if img_match != None and img_match != "" and img_match.isspace() != True:
                        
                        try:
                            
                            # Find the indices of the '[', ']' characters
                            start_index = img_match.find('[')
                            end_index = img_match.find(']')

                            # Extract the substring between the indices
                            img_match = img_match[start_index+1:end_index]
                            
                            print("IMAGE SEARCH: " + img_match)

                            # Replace YOUR_API_KEY and YOUR_CSE_ID with your own API key and CSE ID
                            url = f"https://www.googleapis.com/customsearch/v1?q={img_match}&key={GOOGLE_API_KEY}&cx={GOOGLE_CSE_ID}&searchType=image"
                            response = requests.get(url)
                            results = response.json()
                            
                            #print(results)
                            
                            # Extract the image URL for the first result (best/most relevant image)
                            image_url = results['items'][0]['link']
                            
                            #print(image_url)
                            
                            match_embed = discord.Embed(color=discord.Color.dark_theme())
                            match_embed.set_image(url=image_url)
                            print(image_url)
                            
                            #await interaction.channel.send(embed=match_embed)
                            
                            if len(embeds) >= 9:
                                embeds_overflow.append(match_embed)
                            else:
                                embeds.append(match_embed)

                        except Exception as e:
                            print(e)
                        
                    if dot_match != None and dot_match != "" and dot_match != "\n" and dot_match.isspace() != True:
                        
                        try:
                            
                            dot_system_message = {
                                "role": "user",
                                "content": f"Write only in Graphviz DOT code to visualize and explain {dot_match} in a stylish and aesthetically pleasing way. Use bgcolor=\"#36393f\". Text color and node fill color should be different."
                            }

                            dot_messages = []
                            dot_messages.append(dot_system_message)

                            dot_match = openai.ChatCompletion.create(
                                model="gpt-3.5-turbo",
                                messages=dot_messages,
                                temperature=0.0,
                                max_tokens=512,
                                top_p=1.0,
                                frequency_penalty=0.0,
                                presence_penalty=0.0,
                                )
                            
                            dot_match = dot_match['choices'][0]['message']['content']
                        
                            #dot_match = re.sub(r'//.*|/\*(.|\n)*?\*/', '', dot_match)
                            
                            #dot_match = dot_match.strip()
                            #dot_match = dot_match.replace("}", "\n}")
                            #dot_match = dot_match.replace("\\n", "")
                            #dot_match = dot_match.replace("\t", "\n")
                            #dot_match = dot_match.replace(",", "")
                            #dot_match = dot_match.replace(" ", "")
                            #dot_match = dot_match.strip("%")
                            
                            #if dot_match[-1] != "}":
                                #dot_match += "}"
                                
                            print(f"%%%{dot_match}%%%")
                            
                            graphs = pydot.graph_from_dot_data(dot_match)
                            
                            graph = graphs[0]
                            subfolder = 'graphviz'

                            if not os.path.exists(subfolder):
                                os.makedirs(subfolder)

                            graph.write_png(f'{subfolder}/graphviz{file_count}.png')
                            
                            dot_file = discord.File(f'{subfolder}/graphviz{file_count}.png')
                            match_embed = discord.Embed(color=discord.Color.dark_theme())
                            match_embed.set_image(url=f"attachment://{subfolder}/graphviz{file_count}.png")
                            
                            file_count += 1
                        
                            #await interaction.channel.send(file = dot_file, embed=match_embed)
                            
                            if len(embeds) >= 9:
                                embeds_overflow.append(match_embed)
                                files_overflow.append(dot_file)
                            else:
                                embeds.append(match_embed)
                                files.append(dot_file)
                            
                            
                        except Exception as e:
                            print(e)
                        
            except Exception as e:
                print(e)
        else:
            if len(reply) > 4096:
                try:
                    embeds = []
                    embeds.append(prompt_embed)
                    substrings = []
                    for i in range(0, len(reply), 4096):
                        substring = reply[i:i+4096]
                        substrings.append(substring)
                        
                    for string in substrings:
                        embed_string = discord.Embed(description=string, color=discord.Color.dark_theme())
                        embeds.append(embed_string)
                except:                   
                    embed = discord.Embed(description=f'<:ivaerror:1051918443840020531> **{mention} 4096 character response limit reached. Response contains {len(reply)} characters. Use `/reset`.**', color=discord.Color.dark_theme())
                    await interaction.followup.send(embed=embed, ephemeral=False)
            else:
                embeds.append(embed)
            
        try:
            print(f"{colors.fg.darkgrey}{colors.bold}{time} {colors.fg.lightcyan}ASK     {colors.reset}{colors.fg.darkgrey}{str(guild_name).lower()}{colors.reset} {colors.bold}@iva: {colors.reset}{reply}")
            await interaction.followup.send(files=files, embeds=embeds, view=view)
            last_response[channel_id] = interaction
            #print(files, embeds)
            if len(embeds_overflow) > 0:
                await interaction.channel.send(files = files_overflow, embeds=embeds_overflow)
            url_pattern = re.compile(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+')
            links = url_pattern.findall(reply)
            stripped_links = [link.rstrip(',.:)') for link in links]
            if len(stripped_links) > 0:
                stripped_links = list(set(stripped_links))
                formatted_links = "\n".join(stripped_links)
                await interaction.channel.send(content=formatted_links)
            return
        except Exception as e:
            print(e)
    except discord.errors.NotFound as e:
        print(f"An error occurred: {e}")

@tree.command(name = "reset", description="start a new conversation")
async def reset(interaction):
    
    global last_response
    
    channel_id = interaction.channel_id
    guild_id = interaction.guild_id
    id = interaction.user.id
    
    active_users = await load_pickle_from_redis('active_users')
    chat_mems = await load_pickle_from_redis('chat_mems')
    ask_mems = await load_pickle_from_redis('ask_mems')
    
    try:
        if channel_id in last_response:
            if last_response[channel_id] != None:
                await last_response[channel_id].edit_original_response(content="⠀", view=None)
    except discord.errors.HTTPException as e:
        print(e)

    last_response[channel_id] = None
    ask_mems[channel_id] = None
    chat_mems[channel_id] = None
    active_users[channel_id] = []
    
    await save_pickle_to_redis('ask_mems', ask_mems)
    await save_pickle_to_redis('active_users', active_users)
    await save_pickle_to_redis('chat_mems', chat_mems)
    
    embed = discord.Embed(description="<:ivareset:1051691297443950612>", color=discord.Color.dark_theme())
    await interaction.response.send_message(embed=embed, ephemeral=False)

    
@tree.command(name = "help", description="get started")
async def help(interaction):
    
    global active_users
    global active_names
    
    mention = interaction.user.mention

    embed = discord.Embed(title=f"Welcome. Let's **Get Started**.\n\n", color=discord.Color.dark_theme())
    embed.set_thumbnail(url=client.user.avatar.url)
    embed.add_field(name="Step One", value="Iva uses **[OpenAI](https://beta.openai.com)** to generate responses. Create an account with them to start.")
    embed.add_field(name="Step Two", value="Visit your **[API Keys](https://beta.openai.com/account/api-keys)** page and click **`+ Create new secret key`**.")
    embed.add_field(name="Step Three", value=f"Copy and paste that secret key (`sk-...`) when you run `/setup` with {client.user.mention}")
    
    embed1 = discord.Embed(title="Step One", color=discord.Color.dark_theme())
    embed2 = discord.Embed(title="Step Two", color=discord.Color.dark_theme())
    embed3 = discord.Embed(title="Step Three", color=discord.Color.dark_theme())
    
    embed1.set_image(url="https://media.discordapp.net/attachments/1053423931979218944/1055535479140929606/Screenshot_2022-12-21_233858.png?width=960&height=546")
    embed2.set_image(url="https://media.discordapp.net/attachments/1053423931979218944/1055535478817947668/Screenshot_2022-12-21_234629.png?width=960&height=606")
    embed3.set_image(url="https://media.discordapp.net/attachments/1053423931979218944/1055535478507585578/Screenshot_2022-12-21_234900.png")
    
    await interaction.response.send_message(embeds=[embed, embed1, embed2, embed3], ephemeral=False)

@tree.command(name = "tutorial", description="how to talk with iva")
async def tutorial(interaction):
    
    global active_users
    global active_names
    
    mention = interaction.user.mention

    embed_main = discord.Embed(title="Introduction to Iva", description="there are two *separate* ways to talk to iva, both with their own conversation history: `@iva` and `/iva`. let's go over their differences, in addition to a other helpful tools.", color=discord.Color.dark_theme())
    embed_main.set_thumbnail(url=client.user.avatar.url)
    
    embed_chat = discord.Embed(title="`@iva`", description="provides **chat** and **conversation** oriented answers. has personality, asks questions back, is more creative.", color=discord.Color.dark_theme())

    embed_ask = discord.Embed(title="`/iva`", description="provides **academic** and **work** oriented answers. has less personality, is more focused on consistency and reliability.", color=discord.Color.dark_theme())
    #embed_ask.add_field(inline=True, name="<:ivacontinue1:1051714712242491392> `Continue`", value="say more, extend the last prompt's response")
    #embed_ask.add_field(inline=True, name="<:ivaregenerate:1051697145713000580> `Regenerate`", value="replace the last prompt's response with a different one")
    embed_ask.add_field(inline=True, name="<:ivareset:1051691297443950612> `Reset`", value="reset `/iva` conversation history, clear iva's memory")
    
    embed_other = discord.Embed(title="Other", color=discord.Color.dark_theme())
    embed_other.add_field(inline=True, name="`/reset`", value="reset `@iva` and `/iva` conversation history.")
    embed_other.add_field(inline=True, name="`/help`", value="show instructions for setup.")
    embed_other.add_field(inline=True, name="`/setup`", value="enter your key. `/help` for more info.")
    
    await interaction.response.send_message(embeds=[embed_main, embed_chat, embed_ask, embed_other], ephemeral=False)
    
@tree.command(name = "setup", description="register your key")
@app_commands.describe(key = "key")
async def setup(interaction, key: str):
    
    global active_users
    global active_names
    
    guild_id = interaction.guild_id
    id = interaction.user.id
    mention = interaction.user.mention

    # Use the `SELECT` statement to fetch the row with the given id
    result = await async_fetch_key(id)

    if result != None:

        # Access the values of the columns in the row
        if key != result[0]:
            
            with psycopg2.connect(DATABASE_URL) as conn:
                with conn.cursor() as cursor:
                    # update the API key in the table
                    cursor.execute("UPDATE keys SET key = %s WHERE id = %s", (key, str(id)))
            
            embed = discord.Embed(description=f"<:ivathumbsup:1051918474299056189> **Key updated for {mention}.**", color=discord.Color.dark_theme())
            await interaction.response.send_message(embed=embed, ephemeral=False, delete_after=30)
            
            conn.commit()

            # Print the values of the columns
            #print(f'id: {id}, key: {key}')
        
        elif key == result[0]:
            
            embed = discord.Embed(description=f"<:ivaerror:1051918443840020531> **Key already registered for {mention}.**", color=discord.Color.dark_theme())
            await interaction.response.send_message(embed=embed, ephemeral=False, delete_after=30)
            
            # Print the values of the columns
            #print(f'id: {id}, key: {key}')
        
    else:
        
        with psycopg2.connect(DATABASE_URL) as conn:
            with conn.cursor() as cursor:
                # insert a new API key into the table
                cursor.execute("INSERT INTO keys (id, key) VALUES (%s, %s)", (str(id), key))

        embed = discord.Embed(description=f"<:ivathumbsup:1051918474299056189> **Key registered for {mention}.**", color=discord.Color.dark_theme())
        await interaction.response.send_message(embed=embed, ephemeral=False, delete_after=30)
        
@tree.command(name = "model", description="choose a completion model")
@app_commands.choices(choices=[
        app_commands.Choice(name="gpt-3.5", value="gpt-3.5-turbo"),
        app_commands.Choice(name="gpt-4", value="gpt-4"),
    ])
async def model(interaction, choices: app_commands.Choice[str]):
    
    id = interaction.user.id
    mention = interaction.user.mention
    
    user_settings = await load_pickle_from_redis('user_settings')
    
    user_settings.setdefault(id, {})['model'] = choices.value
    
    await save_pickle_to_redis('user_settings', user_settings)
    
    embed = discord.Embed(description=f"<:ivathumbsup:1051918474299056189> **set model to `{choices.value}` for {mention}.**", color=discord.Color.dark_theme())
    await interaction.response.send_message(embed=embed, ephemeral=False, delete_after=30)
    
    return
    
@tree.command(name = "temperature", description="set a default temperature to use with iva.")
@app_commands.describe(temperature = "temperature")
async def temperature(interaction, temperature: float):
    
    id = interaction.user.id
    mention = interaction.user.mention
    
    user_settings = await load_pickle_from_redis('user_settings')
    
    if not (temperature >= 0.0 and temperature <= 2.0):
        
        embed = discord.Embed(description=f"<:ivaerror:1051918443840020531> **{mention} `temperature` must be a float value from 0.0-2.0.**", color=discord.Color.dark_theme())
        
        await interaction.response.send_message(embed=embed, ephemeral=False, delete_after=30)
        
        return
    
    user_settings.setdefault(id, {})['temperature'] = temperature
    
    await save_pickle_to_redis('user_settings', user_settings)
    
    embed = discord.Embed(description=f"<:ivathumbsup:1051918474299056189> **set temperature to `{temperature}` for {mention}.**", color=discord.Color.dark_theme())
    
    await interaction.response.send_message(embed=embed, ephemeral=False, delete_after=30)
    
    return
    
client.run(DISCORD_TOKEN)