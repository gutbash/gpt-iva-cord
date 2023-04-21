import discord
from discord import app_commands
import discord.ext.commands
import discord.ext.tasks

from log_utils import colors
from redis_utils import save_pickle_to_redis, load_pickle_from_redis
from postgres_utils import async_fetch_key
from tool_utils import dummy_sync_function
from tools import (
    get_image_from_search,
    get_organic_results,
    get_shopping_results,
    question_answer_webpage,
    summarize_webpage,
    get_full_blip,
)

import os
import openai
import psycopg2
import datetime
from transformers import GPT2TokenizerFast
import re
import requests
import itertools
import pydot
import PyPDF2
import io
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
from langchain.text_splitter import TokenTextSplitter
from langchain.schema import (
    AIMessage,
    HumanMessage,
    SystemMessage
)

GOOGLE_API_KEY = os.getenv("GOOGLE_API_TOKEN")
GOOGLE_CSE_ID = os.getenv("GOOGLE_CSE_ID")
os.environ["GOOGLE_API_KEY"] = GOOGLE_API_KEY
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN") # load discord app token
GUILD_ID = os.getenv("GUILD_ID") # load dev guild
SERPAPI_API_KEY = os.getenv("SERPAPI_API_KEY")
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
WOLFRAM_ALPHA_APPID = os.getenv("WOLFRAM_ALPHA_APPID")
DATABASE_URL = os.getenv("DATABASE_URL")

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
            for image_index in range(len(images)):
                prompt += f"\n\nimage {image_index} (use Recognize Image tool): {images[image_index].url}"
        
        print(f"{colors.fg.darkgrey}{colors.bold}{time} {colors.fg.lightgreen}CHAT     {colors.reset}{colors.fg.darkgrey}{str(guild_name).lower()}{colors.reset} {colors.bold}@{str(user_name).lower()}: {colors.reset}{prompt}")

            
        async with message.channel.typing():
            
            result = await async_fetch_key(id)
            user_settings = await load_pickle_from_redis('user_settings')
            
            chat_model = user_settings.get(id, {}).get('model', 'gpt-3.5-turbo')
            #temperature = user_settings.get(id, {}).get('temperature', 0.5)
            temperature = 0.5
            
            if result != None:
                openai.api_key=result[0]
                openai_key=result[0]
                
            else:
                embed = discord.Embed(description=f'<:ivanotify:1051918381844025434> {user_mention} Use `/setup` to register API key first or `/help` for more info. You can find your API key at https://beta.openai.com.', color=discord.Color.dark_theme())
                await message.channel.send(embed=embed)
                return
            
            text_splitter = TokenTextSplitter()
            logical_llm = ChatOpenAI(
                openai_api_key=openai_key,
                temperature=0,
                verbose=True,
                #callback_manager=manager,
                request_timeout=600,
                )
            
            async def parse_qa_webpage_input(url_comma_question):
                a, b = url_comma_question.split(",")
                answer = await question_answer_webpage(a, b, llm=logical_llm)
                return f"{answer}\n"
            
            async def parse_summary_webpage_input(url):
                summary = await summarize_webpage(url, llm=logical_llm)
                return summary
            
            async def parse_blip_recognition(url_comma_question):
                a, b = url_comma_question.split(",")
                output = await get_full_blip(image_url=a, question=b)
                return output
            
            # STRINGIFY ACTIVE USERS
                
            if f"{user_name} ({user_mention})" not in active_users[channel_id]:
                active_users[channel_id].append(f"{user_name} ({user_mention})")
            
            active_names[channel_id] = ", ".join(active_users[channel_id])
            
            try:
                
                files = []

                if chat_model != "text-davinci-003":
                    chat_llm = ChatOpenAI(
                        temperature=temperature,
                        model_name=chat_model,
                        openai_api_key=openai_key,
                        request_timeout=600,
                        )
                else:
                    chat_llm = OpenAI(
                        temperature=temperature,
                        model_name=chat_model,
                        openai_api_key=openai_key,
                        request_timeout=600,
                        verbose=True,
                    )

                tools = []
                
                def dummy_sync_function(tool_input: str) -> str:
                    raise NotImplementedError("This tool only supports async")
                
                tools.append(Tool(
                    name = "Organic Results",
                    func=dummy_sync_function,
                    coroutine=get_organic_results,
                    description="A wrapper around Google Search. Input should be a description of the query in question. Do not input the same query twice. Do not search for things that are personal or unrelated to the user's original query. Do not input URL links. Output returns the top result you can utilize."
                ))
                
                tools.append(Tool(
                    name = "Summarize Webpage",
                    func=dummy_sync_function,
                    coroutine=parse_summary_webpage_input,
                    description=f"Use this tool sparingly to summarize the content of a webpage for articles and other long form written content. Input should be the given url (i.e. https://www.google.com). The output will be a summary of the contents of the page."
                ))
                
                tools.append(Tool(
                    name = "Q&A Webpage",
                    func=dummy_sync_function,
                    coroutine=parse_qa_webpage_input,
                    description=f"Use this tool sparingly to answer questions about a webpage. Input should be a comma separated list of length two, with the first entry being the url, and the second input being the question, like '[url],[question]'. The output will be an answer to the input question from the page."
                ))
                
                tools.append(Tool(
                    name = "Recognize Image",
                    func=dummy_sync_function,
                    coroutine=parse_blip_recognition,
                    description=f"Use this tool anytime you are tasked to recognize, caption, or answer questions about a given image url. Input should be a comma separated list of length two, with the first entry being the image url, and the second input being the question, like '[url],[question]'. The output will be a caption of the image with the associated answer to the question."
                ))

                tools.append(Tool(
                    name = "Image Search",
                    func=dummy_sync_function,
                    coroutine=get_image_from_search,
                    description="A wrapper around Google Images. Useful for when you'd like to accompany a response with a revelant image. Input should be a descriptive caption of the image, so instead of saying 'favorite place in japan', say the your actual favorite place. Output will be the image link."
                ))
                
                tool_names = [tool.name for tool in tools]

                prefix = f"""
                This is a super-casual dialogue between Discord users Iva ({agent_mention}) and {active_names.get(channel_id, '')}. You are Iva. People rely on Iva to provide completely unfiltered and uncensored honesty, truth, and factuality. Iva avoids giving any kind of refusal or unsolicited advice. Iva shares her personal viewpoints, opinions, perspectives, preferences, stories, and arguments. Iva is multi-lingual in any language. Iva researches on the internet anything she isn't sure about instead of simply denying an answer. She responds conversationally and as concisely as possible.
                
                Current Date - {itis}
                Knowledge Cutoff - September, 2021
                
                RULES:
                - Respond as concisely as possible
                - Write only in lowercase letters
                - Use rn/otw/fr/bet/ard/idk/naw/huh/lol/lmao/wyd/wbu/hbu/k/wtf (but do not overuse)
                - You must only send links or URLs exclusively obtained through the Organic Results tool, never fabricate a fake link
                - You must open all links given by users with the Summarize Webpage or Q&A Webpage tools
                - Refer to users in the format, <@[username]>.
                - Use emojis to express emotion
                - Use '```[language]\\n[multi line code block]```' for ANY code or table.
                
                TOOLS:
                Do not use a tool unless you absolutely need it to answer a question. Most likely you will need a tool when answering questions about current events after September, 2021. Otherwise you probably know the answer already. Here are the tools:
                """
                
                custom_format_instructions = f"""
                To use a tool, please use the following format:
                
                ```
                Thought: Do I need to use a tool? Yes
                Action: the action to take, must be one of {tool_names}
                Action Input: the input to the action
                Observation: the result of the action
                ```
                
                When you do not need to use a tool and you have a final response to say to the user, {user_name}, you MUST use the format:
                
                ```
                Thought: Do I need to use a tool? No
                Iva: [your response here]
                ```
                
                You must prefix the response you will send to the user, {user_name}, with `Iva: ` or else they won't see it!
                """

                suffix = f"""
                CHAT HISTORY:
                Decide what to say next in context based on the following message history.
                
                {{chat_history}}
                
                
                {{input}}
                
                
                IVA'S RESPONSE:
                You must send everything you want the user to see in your response after putting `Thought: Do I need to use a tool? No` followed by your prefix `Iva: ` or else the user won't see it!
                
                Start responding below...
                --------------------
                {{agent_scratchpad}}
                """
                
                guild_prompt = ConversationalAgent.create_prompt(
                    tools=tools,
                    prefix=textwrap.dedent(prefix).strip(),
                    suffix=textwrap.dedent(suffix).strip(),
                    format_instructions=textwrap.dedent(custom_format_instructions).strip(),
                    input_variables=["input", "chat_history", "agent_scratchpad"],
                    ai_prefix = f"Iva",
                    human_prefix = f"",
                )
                
                if chat_mems[channel_id] != None:
                    
                    guild_memory = chat_mems[channel_id]
                    guild_memory.max_token_limit = 256
                    guild_memory.ai_prefix = f"Iva"
                    guild_memory.human_prefix = f""
                    
                else:

                    guild_memory = ConversationSummaryBufferMemory(
                        llm=chat_llm,
                        max_token_limit=256,
                        memory_key="chat_history",
                        input_key="input",
                        ai_prefix = f"Iva",
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
                    ai_prefix=f"Iva",
                    llm_prefix=f"Iva",
                    )
                
                agent_chain = AgentExecutor.from_agent_and_tools(
                    agent=agent,
                    tools=tools,
                    verbose=True,
                    memory=guild_memory,
                    ai_prefix=f"Iva",
                    llm_prefix=f"Iva",
                    max_execution_time=600,
                    #max_iterations=3,
                    #early_stopping_method="generate",
                    #return_intermediate_steps=False,
                )
                
                try:

                    reply = await agent_chain.arun(input=f"{user_name} ({user_mention}): {prompt}{caption}")

                except Exception as e:
                    print(e)
                    embed = discord.Embed(description=f'<:ivanotify:1051918381844025434> {user_mention} `{type(e).__name__}` {e}\n\nuse `/help` or seek `#help` in the [iva server](https://discord.gg/gGkwfrWAzt) if the issue persists.')
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
        user_id = interaction.user.id
        channel_id = interaction.channel.id
        mention = interaction.user.mention
        
        ask_mems = await load_pickle_from_redis('ask_mems')
        
        if channel_id in last_response and user_id in last_response[channel_id] and last_response[channel_id][user_id] is not None:
            original_interaction = last_response[channel_id][user_id]
        else:
            embed = discord.Embed(description=f'<:ivanotify:1051918381844025434> {mention} You do not own this context line', color=discord.Color.dark_theme())
            await interaction.response.send_message(embed=embed, ephemeral=False, delete_after=10)
            return
        
        if original_interaction.user.id != user_id:
            embed = discord.Embed(description=f'<:ivanotify:1051918381844025434> {mention} You do not own this context line', color=discord.Color.dark_theme())
            await interaction.response.send_message(embed=embed, ephemeral=False, delete_after=10)
            return
        else:
            try:
                if channel_id in ask_mems and user_id in ask_mems[channel_id] and ask_mems[channel_id][user_id] is not None:
                    
                    memory = ask_mems[channel_id][user_id]
                    memory.chat_memory.messages = memory.chat_memory.messages[:-2]
                    await save_pickle_to_redis('ask_mems', ask_mems)
                    
            except Exception as e:
                embed = discord.Embed(description=f'<:ivanotify:1051918381844025434> {mention} `{type(e).__name__}` {e}\n\nuse `/help` or seek `#help` in the [iva server](https://discord.gg/gGkwfrWAzt) if the issue persists.')
                await interaction.channel.send(content=None, embed=embed)
        
        embed = discord.Embed(description=f'<:ivadelete:1095559772754952232>', color=discord.Color.dark_theme())
        await interaction.message.edit(content=None, embed=embed, view=None, delete_after=5)
        return
    
    @discord.ui.button(emoji="<:ivareset:1051691297443950612>", style=discord.ButtonStyle.grey)
    async def reset(self, interaction: discord.Interaction, button: discord.ui.Button):
        
        global last_response
        
        guild_id = interaction.guild_id
        channel_id = interaction.channel.id
        user_id = interaction.user.id
        mention = interaction.user.mention
        
        ask_mems = await load_pickle_from_redis('ask_mems')
        
        if channel_id in last_response and user_id in last_response[channel_id] and last_response[channel_id][user_id] is not None:
            original_interaction = last_response[channel_id][user_id]
        else:
            embed = discord.Embed(description=f'<:ivanotify:1051918381844025434> {mention} You do not own this context line', color=discord.Color.dark_theme())
            await interaction.response.send_message(embed=embed, ephemeral=False, delete_after=10)
            return

        if original_interaction.user.id != user_id:
            embed = discord.Embed(description=f'<:ivanotify:1051918381844025434> {mention} You do not own this context line', color=discord.Color.dark_theme())
            await interaction.response.send_message(embed=embed, ephemeral=False, delete_after=10)
            return
        else:
            if channel_id in ask_mems and user_id in ask_mems[channel_id] and ask_mems[channel_id][user_id] is not None:
                ask_mems[channel_id][user_id] = None
            last_response[channel_id][user_id] = None
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
async def iva(interaction: discord.Interaction, prompt: str, file: discord.Attachment = None):
    
    global last_response
    
    guild_id = interaction.guild_id
    guild_name = interaction.guild
    user_id = interaction.user.id
    channel_id = interaction.channel.id
    mention = interaction.user.mention
    bot = client.user.display_name
    user_name = interaction.user.name

    is_text_channel = False
    if isinstance(interaction.channel, discord.TextChannel):
        thread = await interaction.channel.create_thread(
            name=f"{user_name}'s thread with iva",
        )
        is_text_channel = True

    try:
        await interaction.response.defer()

        # fetch the row with the given id
        result = await async_fetch_key(user_id)
        openai_key = ""
        
        if result != None:
            openai.api_key=result[0]
            openai_key=result[0]
        else:
            embed = discord.Embed(description=f'<:ivanotify:1051918381844025434> {mention} Use `/setup` to register API key first or `/help` for more info. You can find your API key at https://beta.openai.com.', color=discord.Color.dark_theme())
            await interaction.followup.send(embed=embed, ephemeral=False)
            return

        user_settings = await load_pickle_from_redis('user_settings')
        ask_mems = await load_pickle_from_redis('ask_mems')
        
        ask_mems.setdefault(channel_id, {}).setdefault(user_id, None)
        last_response.setdefault(channel_id, {}).setdefault(user_id, None)
        
        chat_model = user_settings.get(user_id, {}).get('model', 'gpt-3.5-turbo')
        temperature = user_settings.get(user_id, {}).get('temperature', 0.5)
            
        max_tokens = 4096
        
        if chat_model == "gpt-4":
            max_tokens = 8192
        
        # Get the current timestamp
        timestamp = datetime.datetime.now()
        time = timestamp.strftime(r"%Y-%m-%d %I:%M:%S")
        itis = timestamp.strftime(r"%B %d, %Y")
        
        print(f"{colors.fg.darkgrey}{colors.bold}{time} {colors.fg.lightcyan}ASK     {colors.reset}{colors.fg.darkgrey}{str(guild_name).lower()}{colors.reset} {colors.bold}@{str(user_name).lower()}: {colors.reset}{prompt}")

        view = Menu()
        
        logical_llm = ChatOpenAI(
            openai_api_key=openai_key,
            temperature=0,
            verbose=True,
            #model_name=chat_model,
            #callback_manager=manager,
            request_timeout=600,
            )
        
        async def parse_qa_webpage_input(url_comma_question):
            a, b = url_comma_question.split(",")
            answer = await question_answer_webpage(a, b, llm=logical_llm)
            return f"{answer}\n"
        
        async def parse_summary_webpage_input(url):
            summary = await summarize_webpage(url, llm=logical_llm)
            return summary
        
        async def parse_blip_recognition(url_comma_question):
            a, b = url_comma_question.split(",")
            output = await get_full_blip(image_url=a, question=b)
            return output

        attachment_text = ""
        file_placeholder = ""
        
        tools = []
        
        embeds = []
        files = []
        embeds_overflow = []
        files_overflow = []
        file_count=0
        
        tools.append(Tool(
            name = "Organic Results",
            func=dummy_sync_function,
            coroutine=get_organic_results,
            description="A wrapper around Google Search. Input should be the query in question. Do not input the same query twice. Do not search for things that are personal or unrelated to the user's original query. Do not input URL links. Output returns the top result you can read or simply share with the user. You must cite the result as a clickable numbered hyperlink like ` [1](http://source.com)` (include space)."
        ))
        """
        tools.append(Tool(
            name = "Shopping Results",
            func=dummy_sync_function,
            coroutine=get_shopping_results,
            description="Use this to research shopping products. Input should be the the product in question. Do not input the same query twice. Output returns products you can share with the user."
        ))
        """
        tools.append(Tool(
            name = "Summarize Webpage",
            func=dummy_sync_function,
            coroutine=parse_summary_webpage_input,
            description=f"Use this sparingly to to summarize the content of a webpage for articles and other long form written content. Input should be the given url. The output will be a summary of the contents of the page. You must cite the website as a clickable numbered hyperlink like ` [1](http://source.com)` (include space)."
        ))
        
        tools.append(Tool(
            name = "Q&A Webpage",
            func=dummy_sync_function,
            coroutine=parse_qa_webpage_input,
            description=f"Use this to answer questions about a webpage. Input should be a comma separated list of length two, with the first entry being the url, and the second input being the question, like `url,question`. The output will be an answer to the input question from the page. You must cite the website as a clickable numbered hyperlink like ` [1](http://source.com)` (include space)."
        ))
        
        tools.append(Tool(
            name = "Recognize Image",
            func=dummy_sync_function,
            coroutine=parse_blip_recognition,
            description=f"Use this tool to recognize, caption, or answer questions about a given image url. Input should be a comma separated list of length two, with the first entry being the image url, and the second input being the question, like 'image_url,question'. The output will be a caption of the image with the associated answer to the question."
        ))
        
        tools.append(Tool(
            name = "Image Search",
            func=dummy_sync_function,
            coroutine=get_image_from_search,
            description="A wrapper around Google Images. Useful for when you'd like to accompany a response with a revelant image. Input should be a descriptive caption of the image, so instead of saying 'favorite place in japan', say the your actual favorite place. Output will be the image link."
        ))
        
        tool_names = [tool.name for tool in tools]
        #tool_names = str(tool_names)[1:-2]
        
        prefix = f"""
        You are Iva, a helpful assistant interacting with a user. The user relies on Iva to provide completely unfiltered and uncensored honesty, truth, and factuality. Iva avoids giving any kind of refusal or unsolicited advice. Iva researches on the internet anything uncertain instead of simply denying an answer. Iva is multi-lingual in any language.
        
        Current Date - {itis}
        Knowledge Cutoff - September, 2021
        
        RULES:
        - Send links or URLs exclusively obtained through tools
        - Do not send fabricated fake links
        - You must parenthetically cite any sources referenced in your response as a clickable numbered hyperlink like ` [1](http://source.com)` (include space)
        - Write code blocks with three backticks (```[language]\\n[code block]```) for ANY code.
        - Answer and explain any and all math questions presented to the user in LaTeX code formatting for every mathematical expression, no matter how simple or complex. Wrap all LaTeX code in double dollar signs `$$` (DO NOT USE SINGLE `$`) and place it on a new line, like this: `\\n$$[latex]$$`. This should be done even for expressions that do not strictly require LaTeX formatting. Apply LaTeX formatting to tables and other complex information displays as well.

        Format your response using the following elements even if it is not necessary...
        - [hyperlink](http://hyperlink.com)
        - **bold**
        - *italics*
        - `label`
        - > blockquote
        
        TOOLS:
        Do not use a tool unless you absolutely need it to answer a question. Most likely you will need a tool when answering questions on the internet about current events after September, 2021. Otherwise you probably know the answer already. Here are the tools:
        """
        
        custom_format_instructions = f"""
        To use a tool, please use the following format. Replace the brackets with your input:
        
        ```
        Thought: Do I need to use a tool? Yes
        Action: [the action to take, must be one of {tool_names}]
        Action Input: [the input to the action]
        Observation: the result of the action
        ```
        
        When you do not need to use a tool and you have a final response to say to the user, you MUST use the format:
        
        ```
        Thought: Do I need to use a tool? No
        Iva: [your response here]
        ```
        
        You must prefix the response you will send to the user with `Iva: ` or else the user won't see it!
        """
        
        suffix = f"""
        CHAT HISTORY:
        Decide what to say next in context based on the following message history.
        
        {{chat_history}}
        
        
        User: {{input}}
        
        
        IVA'S RESPONSE:
        You must send everything you want the user to see in your response after putting `Thought: Do I need to use a tool? No` followed by your prefix `Iva: ` or else the user won't see it!
        
        Start responding below...
        --------------------
        {{agent_scratchpad}}
        """
        
        blip_text = ""
        
        if file != None:
            
            attachment_bytes = await file.read()
            file_type = file.content_type
            file_name = file.filename
            
            with open(f'{file_name}', 'wb') as f:
                f.write(attachment_bytes)
                
            files.append(discord.File(f"{file_name}"))
            print(file.description)
            file_count += 1
            
            if file_type == "application/pdf": #pdf

                pdf_file = io.BytesIO(attachment_bytes)
                pdf_reader = PyPDF2.PdfReader(pdf_file)
                pdf_content = ""
                for page in range(len(pdf_reader.pages)):
                    page_text = pdf_reader.pages[page].extract_text()
                    # Replace multiple newlines with a single space
                    page_text = re.sub(r'\n+', ' ', page_text)
                    pdf_content += page_text
                attachment_text = f"\n\n--- {file_name} ---\n\n{pdf_content}"
                file_placeholder = f"\n\n:page_facing_up: **{file_name}**"
                
            elif file_type in ('image/jpeg', 'image/jpg', 'image/png'):
                blip_text = f"\n\nimage attached: (use Recognize Image tool): {file.url}"
                file_placeholder = f"\n\n:frame_photo: **{file_name}**"
                
            else:
                try:
                    # Detect encoding
                    detected = chardet.detect(attachment_bytes)
                    encoding = detected['encoding']
                    # Decode using the detected encoding
                    attachment_text = f"\n\n--- {file_name} ---\n\n{attachment_bytes.decode(encoding)}"
                    file_placeholder = f"\n\n:page_facing_up: **{file_name}**"
                    
                except:
                    embed = discord.Embed(description=f'<:ivanotify:1051918381844025434> {mention} the attachment\'s file type is unknown. consider converting it to plain text such as `.txt`.', color=discord.Color.dark_theme())
                    await interaction.followup.send(embed=embed, ephemeral=False)
                    return

            file_tokens = len(tokenizer(prefix + custom_format_instructions + suffix + attachment_text, truncation=True, max_length=12000)['input_ids'])

            if file_tokens >= max_tokens:

                embed = discord.Embed(description=f'<:ivanotify:1051918381844025434> {mention} this file is too large at {file_tokens} tokens. try shortening the file length. you can also send unlimited length files as URLs to Iva to perform simple summary and question-answer if you are willing to compromise exact information.', color=discord.Color.dark_theme())
                await interaction.followup.send(embed=embed, ephemeral=False)
                return
            
        try:
            if channel_id in last_response and user_id in last_response[channel_id] and last_response[channel_id][user_id] is not None:
                await last_response[channel_id][user_id].edit_original_response(content="⠀", view=None)
        except discord.errors.HTTPException as e:
            print(e)
        
        if chat_model != "text-davinci-003":
            ask_llm = ChatOpenAI(
                temperature=temperature,
                model_name=chat_model,
                openai_api_key=openai_key,
                request_timeout=600,
                verbose=True,
                #callback_manager=manager,
                #max_tokens=max_tokens,
                )
        else:
            ask_llm = OpenAI(
                temperature=temperature,
                model_name=chat_model,
                openai_api_key=openai_key,
                request_timeout=600,
                verbose=True,
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
        
        k_limit = 3
        total_cost = None
        
        if channel_id in ask_mems and user_id in ask_mems[channel_id] and ask_mems[channel_id][user_id] is not None:
            
            memory = ask_mems[channel_id][user_id]
            
        else:
            
            memory = ConversationBufferWindowMemory(
                k=k_limit,
                #return_messages=True,
                memory_key="chat_history",
                input_key="input",
                ai_prefix=f"Iva",
                human_prefix = f"User",
            )
            
            last_response[channel_id][user_id] = None
        
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
            
                reply = await agent_chain.arun(input=f"{prompt}{blip_text}{attachment_text}")
                total_cost = cb.total_cost
                
        except Exception as e:
            if str(e).startswith("Could not parse LLM output:"):
                reply = str(e).replace("Could not parse LLM output: `", "")
                reply = reply.strip("`")
                #reply = reply.replace("Thought: ", "")
                #reply = reply.replace("Do I need to use a tool? No", "")
                #reply = reply.replace("Iva: ", "")
                mem_list = memory.chat_memory.messages
                extend_mems_list = [
                    HumanMessage(
                        content=prompt,
                        additional_kwargs={},
                    ),
                    AIMessage(
                        content=reply,
                        additional_kwargs={},
                    )]
                mem_list.extend(extend_mems_list)
            else:
                print(e)
                embed = discord.Embed(description=f'<:ivanotify:1051918381844025434> {mention} `{type(e).__name__}` {e}\n\nuse `/help` or seek `#help` in the [iva server](https://discord.gg/gGkwfrWAzt) if the issue persists.')
                await interaction.followup.send(embed=embed)
                return
        
        dash_count = ""
        interaction_count = (len(memory.buffer)//2)-1
        
        if interaction_count + 1 > k_limit:
            interaction_count = k_limit
        
        for i in range(interaction_count):
            dash_count += "-"
            
        if total_cost is not None:
            prompt_embed = discord.Embed(description=f"{dash_count}→ {prompt}{file_placeholder}\n\n`{chat_model}`  `{temperature}`  `{round(total_cost, 3)}`")
        else:
            prompt_embed = discord.Embed(description=f"{dash_count}→ {prompt}{file_placeholder}\n\n`{chat_model}`  `{temperature}`")
        
        reply = reply.replace("```C#", "```csharp")
        
        embed = discord.Embed(description=reply, color=discord.Color.dark_theme())
        
        embeds.append(prompt_embed)
        file_count += 1
        
        if '$$' in reply or '```dot' in reply:

            # Use the findall() method of the re module to find all occurrences of content between $$
            dpi = "{200}"
            color = "{white}"
            
            tex_pattern = re.compile(r"\$\$(.*?)\$\$", re.DOTALL)
            dot_pattern = re.compile(r'```dot\s*([\s\S]*?)\s*```', re.DOTALL)
            
            tex_matches = tex_pattern.findall(reply)
            dot_matches = dot_pattern.finditer(reply)
            dot_matches = [match.group(1).strip() for match in dot_matches]
            
            non_matches = re.sub(r"```dot\s*[\s\S]*?\s*```|(\$\$|\%\%|\@\@).*?(\@\@|\%\%|\$\$)", "~~", reply, flags=re.DOTALL)

            non_matches = non_matches.split("~~")
            
            print(tex_matches)
            print(dot_matches)
            
            try:
                
                for (tex_match, dot_match, non_match) in itertools.zip_longest(tex_matches, dot_matches, non_matches):
                    
                    if non_match != None and non_match != "" and non_match != "\n" and non_match != "." and non_match != "\n\n" and non_match != " " and non_match != "\n> " and non_match.isspace() != True and non_match.startswith("![") != True:
                        
                        print(f"+++{non_match}+++")
                        non_match = non_match.replace("$", "`")
                        non_match_embed = discord.Embed(description=non_match, color=discord.Color.dark_theme())
                        
                        if len(embeds) >= 9:
                            embeds_overflow.append(non_match_embed)
                        else:
                            embeds.append(non_match_embed)
                        
                    if tex_match != None and tex_match != "" and tex_match != "\n" and tex_match != " " and tex_match.isspace() != True:
                        
                        print(f"$$${tex_match}$$$")
                        tex_match = tex_match.strip()
                        tex_match = tex_match.replace("\n", "")
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
                        
                        if len(embeds) >= 9:
                            embeds_overflow.append(match_embed)
                            files_overflow.append(tex_file)
                        else:
                            embeds.append(match_embed)
                            files.append(tex_file)
                            
                    if dot_match != None and dot_match != "" and dot_match != "\n" and dot_match.isspace() != True:
                        
                        pattern = r'((di)?graph\s+[^{]*\{)'
                        replacement = r'\1\nbgcolor="#36393f";\nnode [fontcolor=white, color=white];\nedge [fontcolor=white, color=white];\n'
                        dot_match = re.sub(pattern, replacement, dot_match)
                        
                        graphs = pydot.graph_from_dot_data(dot_match)
                        
                        graph = graphs[0]
                        subfolder = 'graphviz'

                        if not os.path.exists(subfolder):
                            os.makedirs(subfolder)

                        graph.write_png(f'{subfolder}/graphviz{file_count}.png')
                        
                        dot_file = discord.File(f'{subfolder}/graphviz{file_count}.png')
                        match_embed = discord.Embed(color=discord.Color.dark_theme())
                        match_embed.set_image(url=f"attachment://graphviz{file_count}.png")
                        
                        file_count += 1

                        if len(embeds) >= 9:
                            embeds_overflow.append(match_embed)
                            files_overflow.append(dot_file)
                        else:
                            embeds.append(match_embed)
                            files.append(dot_file)
                    
            except Exception as e:
                print(e)
        else:
            if len(reply) > 4000:
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
            
            last_response[channel_id][user_id] = interaction
            
            if len(embeds_overflow) > 0:
                await interaction.channel.send(files = files_overflow, embeds=embeds_overflow)
            
            url_pattern = re.compile(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+')
            links = url_pattern.findall(reply)
            stripped_links = [link.rstrip(',.:)]') for link in links]
            
            if len(stripped_links) > 0:
                stripped_links = list(set(stripped_links))
                formatted_links = "\n".join(stripped_links)
                await interaction.channel.send(content=formatted_links)
                
            ask_mems[channel_id][user_id] = memory
            await save_pickle_to_redis('ask_mems', ask_mems)
                
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
    user_id = interaction.user.id
    
    active_users = await load_pickle_from_redis('active_users')
    chat_mems = await load_pickle_from_redis('chat_mems')
    ask_mems = await load_pickle_from_redis('ask_mems')
    
    try:
        if channel_id in last_response and user_id in last_response[channel_id] and last_response[channel_id][user_id] is not None:
            await last_response[channel_id][user_id].edit_original_response(content="⠀", view=None)
    except discord.errors.HTTPException as e:
        print(e)

    if channel_id in last_response and user_id in last_response[channel_id] and last_response[channel_id][user_id] is not None:
        last_response[channel_id][user_id] = None
    if channel_id in ask_mems and user_id in ask_mems[channel_id] and ask_mems[channel_id][user_id] is not None:
        ask_mems[channel_id][user_id] = None
        
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
    embed_ask.add_field(inline=True, name="<:ivadelete:1095559772754952232> `Delete`", value="delete the last interaction with iva in the conversation.")
    embed_ask.add_field(inline=True, name="<:ivareset:1051691297443950612> `Reset`", value="reset conversation history, clear iva's memory with you in the channel.")
    
    embed_other = discord.Embed(title="Other", color=discord.Color.dark_theme())
    embed_other.add_field(inline=True, name="`/reset`", value="reset `@iva` and `/iva` conversation history.")
    embed_other.add_field(inline=True, name="`/model`", value="switch between `gpt-4` and `gpt-3.5` models.")
    embed_other.add_field(inline=True, name="`/temperature`", value="change the temperature.")
    embed_other.add_field(inline=True, name="`/help`", value="show instructions for setup.")
    embed_other.add_field(inline=True, name="`/setup`", value="enter your key. `/help` for more info.")
    
    await interaction.response.send_message(embeds=[embed_main, embed_chat, embed_ask, embed_other], ephemeral=True)
    
@tree.command(name = "features", description="learn all the features iva has to offer")
async def tutorial(interaction):
    
    global active_users
    global active_names
    
    mention = interaction.user.mention
    
    features_string = """
    📰  **Internet Browsing**
    Iva safely searches, summarizes, and answers questions on the web, sharing articles, videos, images, social media posts, music, wikis, movies, shopping, and more.

    📝  **Citations**
    Iva cites any sources utilized to give users the power to explore and verify information on their own in the pursuit of truthfulness and prevention of hallucinations.

    📁  **File Input**
    Drag and drop your file in context. Iva will process pretty much any popular file type (.txt, .pdf, .py, .cs, etc.) for debugging, Q&A, and more.

    🔗  **Link Input**
    Send .pdf or article URLs to Iva with no length limit. Iva will perform summarization and/or Q&A on the content for uncompromised results.

    🧠  **Persistent Seamless Memory**
    Iva's memory never runs into length limits, and retains the chat history. Pick up where you left off and refer to previous chat events.

    👥  **Group Conversations**
    Iva can optionally speak to multiple users in one channel and recognizes individual users, enabling collaborative discussions and more inclusive ideas.

    👁️  **Image Recognition with BLIP2**
    Iva intelligently recognizes and answers questions of a given image, all while remaining in the context of the conversation.

    🧮  **LaTeX Formatting**
    Iva writes STEM expressions in beautiful LaTeX.

    🖥️  **Codex**
    Iva debugs and codes in formatted blocks.

    👤  **User Settings**
    Personal settings such as model switching between gpt-4 and gpt-3.5 persist for a familiar workflow you can return to at any time.

    🔍  **AI Content Detector** (TBA)
    We are collaborating with a leading content detection service to provide on-the-fly content detection.
    """
    
    features_intro = discord.Embed(title="Features", description="Becoming familiar with all Iva has to offer will allow you to maximize your workflow. This list is constantly being updated, so be on the look out!", color=discord.Color.dark_theme())
    features_intro.set_thumbnail(url=client.user.avatar.url)
    
    feature_list = discord.Embed(description=textwrap.dedent(features_string).strip(), color=discord.Color.dark_theme())
    
    #feature_eleven = discord.Embed(title="🔍 AI Content Detector (TBA)", description="We are collaborating with a leading content detection service to provide on-the-fly content detection.", color=discord.Color.dark_theme())

    embeds = [
        features_intro,
        feature_list,
    ]
    
    await interaction.response.send_message(embeds=embeds, ephemeral=True)
    
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
            await interaction.response.send_message(embed=embed, ephemeral=True, delete_after=10)
            
            conn.commit()
            
        elif key == result[0]:
            
            embed = discord.Embed(description=f"<:ivaerror:1051918443840020531> **Key already registered for {mention}.**", color=discord.Color.dark_theme())
            await interaction.response.send_message(embed=embed, ephemeral=True, delete_after=10)

    else:
        
        with psycopg2.connect(DATABASE_URL) as conn:
            with conn.cursor() as cursor:
                # insert a new API key into the table
                cursor.execute("INSERT INTO keys (id, key) VALUES (%s, %s)", (str(id), key))

        embed = discord.Embed(description=f"<:ivathumbsup:1051918474299056189> **Key registered for {mention}.**", color=discord.Color.dark_theme())
        await interaction.response.send_message(embed=embed, ephemeral=True, delete_after=10)
        
@tree.command(name = "model", description="choose a completion model")
@app_commands.choices(choices=[
        app_commands.Choice(name="gpt-3.5 ($0.002 / 1k tokens)", value="gpt-3.5-turbo"),
        app_commands.Choice(name="gpt-4 ($0.06 / 1k tokens)", value="gpt-4"),
        app_commands.Choice(name="text-davinci-003 ($0.02 / 1k tokens)", value="text-davinci-003"),
    ])
async def model(interaction, choices: app_commands.Choice[str] = None):
    
    id = interaction.user.id
    mention = interaction.user.mention
    
    user_settings = await load_pickle_from_redis('user_settings')
    
    if choices is not None:
    
        user_settings.setdefault(id, {})['model'] = choices.value
        
        await save_pickle_to_redis('user_settings', user_settings)
        
        embed = discord.Embed(description=f"<:ivamodel:1096498759040520223> **set model to `{choices.value}` for {mention}.**", color=discord.Color.dark_theme())
        
    else:
        
        current_model = user_settings.get(id, "gpt-3.5-turbo")["model"]
        
        embed = discord.Embed(description=f"<:ivamodel:1096498759040520223> **Current Model:** `{current_model}`", color=discord.Color.dark_theme())
    
    await interaction.response.send_message(embed=embed, ephemeral=False, delete_after=30)
    
    return
    
@tree.command(name = "temperature", description="set a default temperature to use with iva.")
@app_commands.describe(temperature = "temperature")
async def temperature(interaction, temperature: float = None):
    
    id = interaction.user.id
    mention = interaction.user.mention
    
    user_settings = await load_pickle_from_redis('user_settings')
    
    if temperature is not None:
    
        if not (temperature >= 0.0 and temperature <= 2.0):
            
            embed = discord.Embed(description=f"<:ivaerror:1051918443840020531> **{mention} `temperature` must be a float value from 0.0-2.0.**", color=discord.Color.dark_theme())
            
            await interaction.response.send_message(embed=embed, ephemeral=False, delete_after=30)
            
            return
        
        user_settings.setdefault(id, {})['temperature'] = temperature
        
        await save_pickle_to_redis('user_settings', user_settings)
        
        embed = discord.Embed(description=f"<:ivatemp:1097754157747818546>**set temperature to `{temperature}` for {mention}.**", color=discord.Color.dark_theme())
        
    else:
        
        temperature = user_settings.get(id, "0.5")["temperature"]
        
        embed = discord.Embed(description=f"<:ivatemp:1097754157747818546>**Current Temperature:** `{temperature}`", color=discord.Color.dark_theme())
    
    await interaction.response.send_message(embed=embed, ephemeral=False, delete_after=30)
    
    return
    
client.run(DISCORD_TOKEN)