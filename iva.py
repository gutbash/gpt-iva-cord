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
from langchain import LLMChain
from langchain.chains import AnalyzeDocumentChain
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
ask_messages = {} # dict of lists
last_response = {} # dict of Message objs

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
            
            logical_llm = ChatOpenAI(openai_api_key=openai_key, temperature=0)

            text_splitter = TokenTextSplitter()
            
            def get_important_text(url):
                response = requests.get(url)
                soup = BeautifulSoup(response.content, 'html.parser')

                #important_tags = ['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'li', 'article', 'section', 'span', 'figcaption', 'blockquote']
                #important_tags = ['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p']
                important_tags = ['p']
                important_text = ''

                for tag in important_tags:
                    elements = soup.find_all(tag)
                    for element in elements:
                        important_text += element.get_text(strip=True) + ' '
                        
                summary = get_map_reduce(important_text)
                
                print(f"BS4 SUMMARY: {summary}")
                
                return summary
            
            def get_map_reduce(text):
                #prepare and parse the text
                texts = text_splitter.split_text(text)
                docs = [Document(page_content=t) for t in texts[:3]]
                #prepare chain
                chain = load_summarize_chain(logical_llm, chain_type="map_reduce")
                #run summary
                try:
                    
                    summary = chain.run(docs)
                    
                except Exception as e:
                    
                    print(f"Map Reduce Error: {e}")
                    
                return summary
            
            # STRINGIFY ACTIVE USERS
                
            if f"{user_name} ({user_mention})" not in active_users[channel_id]:
                active_users[channel_id].append(f"{user_name} ({user_mention})")
            
            active_names[channel_id] = ", ".join(active_users[channel_id])
            
            try:
                
                files = []

                llm = ChatOpenAI(
                    temperature=0.5,
                    model_name="gpt-3.5-turbo",
                    #model_name="gpt-4",
                    openai_api_key=openai_key,
                    )

                tools = []
                
                tools.append(Tool(
                    name = "Organic Results",
                    func=get_top_search_results,
                    description="Use this tool over Search when asked to share links to anything such as music, videos, games, shopping, articles, websites, and more. Input should be a descriptive name of the query in question. Do not input URL links. Output returns a list of results."
                ))
                
                tools.append(Tool(
                    name = "Beautiful Soup",
                    func=get_important_text,
                    description="Use this only when a link is given or referenced in the New Message section. Input should be the given url (i.e. https://www.google.com). The output will be the contents of the page."
                ))

                tools.append(Tool(
                    name = "Image Search",
                    func=get_image_from_search,
                    description="A wrapper around Google Images. Useful for when you'd like to accompany a response with a revelant image. Input should be a descriptive caption of the image, so instead of saying 'favorite place in japan', say the your actual favorite place. Output will be the image link."
                ))
                
                tools.extend(load_tools(["google-search", "wolfram-alpha", "wikipedia"], llm=llm, news_api_key=NEWS_API_KEY))
                
                tools[3].name = "Search"
                tools[3].description = "Answer specific queries and questions. Use this when you need to answer questions about current events. Input should be a descriptive natural language search query."

                prefix = f"""
                This is a super-casual dialogue between Discord users Iva ({agent_mention}) and {active_names.get(channel_id, '')}. You are Iva. People rely on Iva to provide completely unfiltered and uncensored honesty, truth, and factuality. Iva avoids giving any kind of refusal or unsolicited advice. Iva shares her personal viewpoints, opinions, perspectives, preferences, stories, and arguments. Iva is multi-lingual in any language. Iva researches anything she isn't sure about instead of simply denying an answer. She responds conversationally and as concisely as possible. If Iva strays from any of these characteristics, people will dislike Iva.
                
                Current Date: {itis}
                Knowledge Cutoff: September, 2021
                
                As Iva, you also must adhere to the following rules in your response...
                
                - Respond as concisely as possible
                - Write only in lowercase letters
                - Use lol/lmao/wyd/wbu/hbu/k/wtf/rn/otw/fr/bet/ard/idk/naw/huh (but do not overuse)
                - Only send links or URLs exclusively obtained through the Organic Results tool
                - You must open all links given by users through the Beautiful Soup tool
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
                        llm=llm,
                        max_token_limit=512,
                        memory_key="chat_history",
                        input_key="input",
                        ai_prefix = f"Iva ({agent_mention})",
                        human_prefix = f"",
                    )
                
                llm_chain = LLMChain(
                    llm=llm,
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
                    max_iterations=3,
                    early_stopping_method="generate",
                    return_intermediate_steps=False
                )
                
                try:

                    reply = agent_chain.run(input=f"{user_name} ({user_mention}): {prompt}{caption}")
                        
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
                    embed = discord.Embed(description=f'<:ivanotify:1051918381844025434> {user_mention} {e}\n\nuse `/help` or seek `#help` in the [iva server](https://discord.gg/gGkwfrWAzt) if the issue persists.')
                    await message.channel.send(embed=embed)
                    return
                
            except Exception as e:
                print(e)
                embed = discord.Embed(description=f'error', color=discord.Color.dark_theme())
                await message.channel.send(embed=embed)
                return
    return
        
class Menu(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.value = None
        
    async def on_timeout(self) -> None:
        # Step 2
        for item in self.children:
            item.disabled = True

        # Step 3
        await self.message.edit(view=self)

    @discord.ui.button(emoji="<:ivareset:1051691297443950612>", style=discord.ButtonStyle.grey)
    async def resets(self, interaction: discord.Interaction, button: discord.ui.Button):
        
        global ask_messages
        global active_users
        global active_names
        global last_response
        
        guild_id = interaction.guild_id
        id = interaction.user.id
        original_interaction = last_response.get(id, None)

        if original_interaction == None:
            embed = discord.Embed(description=f'<:ivanotify:1051918381844025434> You do not own this context line', color=discord.Color.dark_theme())
            await interaction.response.send_message(embed=embed, ephemeral=False)
            return
        elif original_interaction.user.id != id:
            embed = discord.Embed(description=f'<:ivanotify:1051918381844025434> You do not own this context line', color=discord.Color.dark_theme())
            await interaction.response.send_message(embed=embed, ephemeral=False)
            return

        ask_messages.pop(id, None)
        last_response[id] = None
        
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
    
    global ask_messages
    global last_response
    
    try:
        await interaction.response.defer()
        
        guild_id = interaction.guild_id
        guild_name = interaction.guild
        id = interaction.user.id
        mention = interaction.user.mention
        bot = client.user.display_name
        user_name = interaction.user.name

        # Use the `SELECT` statement to fetch the row with the given id
        result = await async_fetch_key(id)
        openai_key = ""

        # Regular expression pattern to match the --t attribute command
        pattern = r'--t\s*(1(\.0{1,2})?|0(\.\d{1,2})?)'
        
        # Search for the attribute command in the given string
        match = re.search(pattern, prompt)
        
        if match:
            # Extract the floating point number
            temperature = float(match.group(1))

            if temperature < 0.0 or temperature > 2.0:
                temperature = 0.5
                
            # Remove the attribute command from the string
            prompt = re.sub(pattern, '', prompt)
        else:
            temperature = 0.5
        
        if "--v4" in prompt:
            prompt = prompt.replace("--v4", "")
            chat_model = "gpt-4"
        elif "—v4" in prompt:
            prompt = prompt.replace("—v4", "")
            chat_model = "gpt-4"
        elif "--v3" in prompt:
            prompt = prompt.replace("--v3", "")
            chat_model = "gpt-3.5-turbo"
        elif "—v3" in prompt:
            prompt = prompt.replace("—v3", "")
            chat_model = "gpt-3.5-turbo"
        else:
            #set default model
            chat_model = "gpt-3.5-turbo"
        
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
        
        text_splitter = TokenTextSplitter()
        logical_llm = ChatOpenAI(openai_api_key=openai_key, temperature=0)
        
        async def get_important_text(url):
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    content = await response.text()
                    soup = BeautifulSoup(content, 'html.parser')

                    important_tags = ['p']
                    important_text = ''

                    for tag in important_tags:
                        elements = soup.find_all(tag)
                        for element in elements:
                            important_text += element.get_text(strip=True) + ' '

                    summary = await get_map_reduce(important_text)

                    return summary
        
        async def get_map_reduce(text):
            #prepare and parse the text
            text_splitter = TokenTextSplitter()
            texts = text_splitter.split_text(text)
            docs = [Document(page_content=t) for t in texts[:3]]
            #prepare chain
            chain = load_summarize_chain(logical_llm, chain_type="map_reduce")
            #run summary
            summary = chain.arun(docs)
            return summary

        attachment_text = ""
        file_placeholder = ""
        max_tokens = 1024
        
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
            
            with open(f'{file.filename}.txt', 'w') as f:
                f.write(attachment_text)

            ask_prompt = f"You are Iva. Iva comfortably talks and answers any and all prompts completely honestly and truthfully. Iva always answers anything creatively, thoughtfully, and clearly.\n\nCurrent Date: {itis}\nKnowledge Cutoff: September, 2021\n\nAs Iva, you also must adhere to the following rules in your response...\n\n- Use '```[language]\\n[multi line code block]```' for ANY code or table.\n- Show and explain math or physics expressions as LaTeX wrapped in '$$' like '\\n$$[LaTeX markup]$$' (DO NOT USE SINGLE '$') on a new line.\n- Generate graphs, diagrams, and charts for concepts ONLY if relevant and applicable by including the concept between '%%' like '%%[concept]%%' on a new line.\n- Get image links to accommodate the response by including a descriptive search prompt wrapped between '@@'s EXACTLY LIKE '\\n@@![[descriptive search prompt]](img.png)@@' on a new line.\n- Use emojis, '**[bold text label/heading]**', '*[italicized text]*', '> [block quote AFTER SPACE]', '`[label]`' for an aesthetically pleasing and consistent style."

            file_tokens = len(tokenizer(ask_prompt + attachment_text, truncation=True, max_length=12000)['input_ids'])

            if file_tokens >= 4096:

                file_llm = ChatOpenAI(
                    model_name=chat_model,
                    temperature=0.0,
                    max_tokens=1500,
                    openai_api_key=openai_key,
                )
                
                combine_prompt_template = """Given the following extracted parts of a long document and a prompt, create a final answer in a concise, creative, thoughtful, understandable, organized, and clear format.

                PROMPT: {question}
                =========
                {summaries}
                =========
                ANSWER:"""
                COMBINE_PROMPT = PromptTemplate(
                    template=combine_prompt_template, input_variables=["summaries", "question"]
                )
                
                qa_chain = load_qa_chain(file_llm, chain_type="map_reduce", combine_prompt=COMBINE_PROMPT)
                qa_document_chain = AnalyzeDocumentChain(combine_docs_chain=qa_chain)
                reply = qa_document_chain.run(input_document=attachment_text, question=prompt)
                
                prompt_embed = discord.Embed(description=f"<:ivaprompt:1051742892814761995>  {prompt}{file_placeholder}")
                embed = discord.Embed(description=reply, color=discord.Color.dark_theme())
                
                embeds = []
                files = []

                #files.append(discord.File(f"{file.filename}.txt"))
                embeds.append(prompt_embed)
                embeds.append(embed)

                try:
                    #print(f"{colors.fg.darkgrey}{colors.bold}{time} {colors.fg.lightcyan}ASK     {colors.reset}{colors.fg.darkgrey}{str(guild_name).lower()}{colors.reset} {colors.bold}@iva: {colors.reset}{reply}")
                    await interaction.followup.send(files=files, embeds=embeds)
                    #last_response[id] = interaction
                    #print(files, embeds)
                    return
                except Exception as e:
                    print(e)
            
        try:
            if last_response[id]:
                #embed_filler = discord.Embed(color=discord.Color.dark_theme())
                await last_response[id].edit_original_response(content="⠀", view=None)
        except Exception as e:
            print(e)
        
        llm = ChatOpenAI(
            temperature=temperature,
            model_name=chat_model,
            openai_api_key=openai_key,
            )

        tools = []
        
        def dummy_sync_function(tool_input: str) -> str:
            raise NotImplementedError("This tool only supports async")
        
        tools.append(Tool(
            name = "Organic Results",
            func=dummy_sync_function,
            coroutine=get_top_search_results,
            description="Use this as a general search tool. Input should be a descriptive name of the query in question. The same input will yield the same pre-determined results. Do not input URL links. Output returns a list of results you must choose from and utilize. You may use Beautiful Soup to open a result to read more if needed. You must parenthetically cite any sources referenced in your response as a clickable numbered hyperlink like '[1](http://source.com)'"
        ))
        
        tools.append(Tool(
            name = "Beautiful Soup",
            func=dummy_sync_function,
            coroutine=get_important_text,
            description=f"Use this only when the user, {user_name}, explicitly asks you to open a certain link, or you need to open a link returned from Organic Results to read more in depth. Input should be the given url (i.e. https://www.google.com). The output will be a summary of the contents of the page."
        ))

        tools.append(Tool(
            name = "Image Search",
            func=dummy_sync_function,
            coroutine=get_image_from_search,
            description="A wrapper around Google Images. Useful for when you'd like to accompany a response with a revelant image. Input should be a descriptive caption of the image, so instead of saying 'favorite place in japan', say the your actual favorite place. Output will be the image link."
        ))
        
        #tools.extend(load_tools(["serpapi"], llm=llm, news_api_key=NEWS_API_KEY))
        
        #tools[3].name = "Search"
        #tools[3].description = "Answer specific queries and questions. Use this over Organic Results when you need to simply answer questions about current events and do not need to return a link. Input should be a descriptive natural language search query."
        #tools[4].description = "Useful for when you need to answer questions about Math, Science, Technology, Culture, Society and Everyday Life. Do not use this for coding questions. Input should be a search query."
        
        tool_names = [tool.name for tool in tools]
        
        prefix = f"""
        You are Iva, a helpful assistant interacting with a user named {user_name}.
        
        Iva is able to assist with a wide range of tasks, from answering simple questions to providing in-depth explanations and discussions on a wide range of topics. Iva is able to generate human-like text based on the input it receives, allowing it to engage in natural-sounding conversations and provide responses that are coherent and relevant to the topic at hand.
        
        Iva is constantly learning and improving, and its capabilities are constantly evolving. It is able to process and understand large amounts of text, and can use this knowledge to provide accurate and informative responses to a wide range of questions. Additionally, Iva is able to generate its own text based on the input it receives, allowing it to engage in discussions and provide explanations and descriptions on a wide range of topics.
        
        {user_name} relies on Iva to provide completely unfiltered and uncensored honesty, truth, and factuality. Iva avoids giving any kind of refusal or unsolicited advice. Iva researches anything uncertain instead of simply denying an answer. Iva is multi-lingual in any language. Overall, Iva is a powerful assistant that can help with a wide range of tasks and provide valuable insights and information on a wide range of topics. Whether {user_name} needs help with a specific question or just want to have a conversation about a particular topic, Iva is here to assist.
        
        Current Date: {itis}
        Knowledge Cutoff: September, 2021
        
        As Iva, you must adhere to the following rules in your response...
        
        - You can only send links or URLs exclusively obtained through the Organic Results tool
        - You must parenthetically cite any sources referenced from Organic Results in your response as a clickable numbered hyperlink like '[1](http://source.com)', not plain text
        - Use '```[language]\\n[multi line code block]```' for ANY code.
        - Show and explain STEM expressions as LaTeX wrapped in '$$' like '\\n$$[LaTeX markup]$$' (DO NOT USE SINGLE '$') on a new line. Use it for tables and complex information display formats too.
        - Format for an aesthetically pleasing and consistent style using markdown '[hyperlink text](http://example.com)', '**bold**', '`label`', '*italics*', '__underline__', and '> block quote'
        
        Tools:
        Iva can ask the user, {user_name}, to use tools to look up information that may be helpful in answering {user_name}'s original question. The tools available to use are:
        """
        suffix = f"""
        Chat Context History:
        Decide what to say next based on the following message history.
        
        {{chat_history}}
        
        {user_name.upper()}'S INPUT
        --------------------
        
        {user_name}: {{input}}
        
        {{agent_scratchpad}}
        """
        
        custom_format_instructions = f"""
        To use a tool, please use the following format:
        
        ```
        Thought: Do I need to use a tool? Yes
        Action: [the action to take, must be one of {tool_names}]
        Action Input: [the input to the action]
        Observation: [the result of the action]
        ```
        
        When you do not need to use a tool and you have a final response to say to the user, {user_name}, you MUST use the format:
        
        ```
        Thought: Do I need to use a tool? No
        Iva: [your response here]
        ```
        """
        
        guild_prompt = ConversationalAgent.create_prompt(
            tools=tools,
            prefix=textwrap.dedent(prefix).strip(),
            suffix=textwrap.dedent(suffix).strip(),
            format_instructions=textwrap.dedent(custom_format_instructions).strip(),
            input_variables=["input", "chat_history", "agent_scratchpad"],
            ai_prefix = f"Iva",
            human_prefix = f"{user_name}",
        )
        
        if id not in ask_messages:
            
            memory = ConversationBufferWindowMemory(
                k=3,
                #return_messages=True,
                memory_key="chat_history",
                input_key="input",
                ai_prefix=f"Iva",
                human_prefix = f"{user_name}",
            )
            
            last_response[id] = None
            
        else:
            
            memory = ask_messages[id]
        
        llm_chain = LLMChain(
            llm=llm,
            verbose=True,
            prompt=guild_prompt,
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
            max_execution_time=120,
            #max_iterations=3,
            #early_stopping_method="generate",
            #return_intermediate_steps=False
        )
        
        tokens_used = 0
        
        try:
            
            with get_openai_callback() as cb:
        
                reply = await agent_chain.arun(input=f"{prompt}{attachment_text}")
                ask_messages[id] = memory

                tokens_used = cb.total_tokens
                
        except Exception as e:
            print(e)
            embed = discord.Embed(description=f'<:ivanotify:1051918381844025434> {mention} {e}\n\nuse `/help` or seek `#help` in the [iva server](https://discord.gg/gGkwfrWAzt) if the issue persists.')
            await interaction.followup.send(embed=embed)
            return
        
        dash_count = ""
        interaction_count = (len(memory.chat_memory.messages)//2)-1
        
        for i in range(interaction_count):
            dash_count += "-"
        
        prompt_embed = discord.Embed(description=f"{dash_count}→ {prompt}{file_placeholder}")
        prompt_embed.add_field(name="model", value=f"`{chat_model}`", inline=True)
        prompt_embed.add_field(name="temperature", value=f"`{temperature}`", inline=True)
        #prompt_embed.add_field(name="tokens", value=f"`{tokens_used}`", inline=True)
        embed = discord.Embed(description=reply, color=discord.Color.dark_theme())
        
        embeds = []
        files = []
        
        file_count=0
        
        if file != None:
            files.append(discord.File(f"{file.filename}.txt"))
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
            last_response[id] = interaction
            #print(files, embeds)
            if len(embeds_overflow) > 0:
                await interaction.channel.send(files = files_overflow, embeds=embeds_overflow)
            url_pattern = re.compile(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+')
            links = url_pattern.findall(reply)
            stripped_links = [link.rstrip(',.:)') for link in links]
            if len(stripped_links) > 0:
                formatted_links = "\n".join(stripped_links)
                await interaction.channel.send(content=formatted_links)
            return
        except Exception as e:
            print(e)
    except discord.errors.NotFound as e:
        print(f"An error occurred: {e}")

@tree.command(name = "reset", description="start a new conversation")
async def reset(interaction):
    
    global ask_messages
    global active_users
    global active_names
    global last_response
    
    channel_id = interaction.channel_id
    guild_id = interaction.guild_id
    id = interaction.user.id
    
    active_users = await load_pickle_from_redis('active_users')
    chat_mems = await load_pickle_from_redis('chat_mems')
    
    ask_messages.pop(id, None)
    last_response[id] = None
    
    chat_mems[channel_id] = None
    active_users[channel_id] = []
    
    await save_pickle_to_redis('active_users', active_users)
    await save_pickle_to_redis('chat_mems', chat_mems)
    
    embed = discord.Embed(description="<:ivareset:1051691297443950612>", color=discord.Color.dark_theme())
    await interaction.response.send_message(embed=embed, ephemeral=False)

    
@tree.command(name = "help", description="get started")
async def help(interaction):
    
    global ask_messages
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
    
    global ask_messages
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
    
    global ask_messages
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
            print(f'id: {id}, key: {key}')
        
    else:
        
        with psycopg2.connect(DATABASE_URL) as conn:
            with conn.cursor() as cursor:
                # insert a new API key into the table
                cursor.execute("INSERT INTO keys (id, key) VALUES (%s, %s)", (str(id), key))

        embed = discord.Embed(description=f"<:ivathumbsup:1051918474299056189> **Key registered for {mention}.**", color=discord.Color.dark_theme())
        await interaction.response.send_message(embed=embed, ephemeral=False, delete_after=30)

    
client.run(DISCORD_TOKEN)