import discord
from discord import app_commands
import discord.ext.commands
import discord.ext.tasks
import os
from dotenv import load_dotenv
import openai
import psycopg2
import datetime
from transformers import GPT2TokenizerFast
import replicate
import re
import itertools
import requests
import pydot
import requests
import PyPDF2
import io
import base64
from PIL import Image

from serpapi import GoogleSearch
import textwrap
import pickle
from xml.etree import ElementTree

from langchain.prompts.chat import (
    ChatPromptTemplate,
    SystemMessagePromptTemplate,
    AIMessagePromptTemplate,
    HumanMessagePromptTemplate,
)

from langchain.schema import (
    AIMessage,
    HumanMessage,
    SystemMessage
)

from langchain.memory import ConversationEntityMemory
from langchain.chat_models import ChatOpenAI
from langchain.llms import OpenAI
from langchain.llms import AzureOpenAI
from langchain.prompts import PromptTemplate
from langchain.chains import ConversationChain, LLMChain
from langchain.chains.conversation.memory import ConversationSummaryBufferMemory

from langchain.agents import initialize_agent, Tool, ConversationalAgent, AgentExecutor, load_tools, ZeroShotAgent
from langchain.utilities import GoogleSearchAPIWrapper, SerpAPIWrapper

from langchain.llms import OpenAI
from langchain.docstore.document import Document
import requests
from langchain.embeddings.openai import OpenAIEmbeddings
from langchain.text_splitter import CharacterTextSplitter
from langchain.prompts import PromptTemplate
import pathlib
import subprocess
import tempfile

from langchain import OpenAI, PromptTemplate, LLMChain
from langchain.text_splitter import CharacterTextSplitter
from langchain.chains.mapreduce import MapReduceChain
from langchain.prompts import PromptTemplate
from langchain.chains.summarize import load_summarize_chain

from langchain.chains import AnalyzeDocumentChain
from langchain import OpenAI
from langchain.chains.summarize import load_summarize_chain

from langchain.chains.question_answering import load_qa_chain
from langchain.llms import OpenAI

load_dotenv() # load .env file

class colors:

    reset = '\033[0m'
    bold = '\033[01m'
    disable = '\033[02m'
    underline = '\033[04m'
    reverse = '\033[07m'
    strikethrough = '\033[09m'
    invisible = '\033[08m'

    class fg:
        black = '\033[30m'
        red = '\033[31m'
        green = '\033[32m'
        orange = '\033[33m'
        blue = '\033[34m'
        purple = '\033[35m'
        cyan = '\033[36m'
        lightgrey = '\033[37m'
        darkgrey = '\033[90m'
        lightred = '\033[91m'
        lightgreen = '\033[92m'
        yellow = '\033[93m'
        lightblue = '\033[94m'
        pink = '\033[95m'
        lightcyan = '\033[96m'
 
    class bg:
        black = '\033[40m'
        red = '\033[41m'
        green = '\033[42m'
        orange = '\033[43m'
        blue = '\033[44m'
        purple = '\033[45m'
        cyan = '\033[46m'
        lightgrey = '\033[47m'

# create API client with custom host, port
#api = webuiapi.WebUIApi(host='127.0.0.1', port=7860)

GOOGLE_API_KEY = os.getenv("GOOGLE_API_TOKEN")
GOOGLE_CSE_ID = os.getenv("GOOGLE_CSE_ID")
os.environ["GOOGLE_API_KEY"] = GOOGLE_API_KEY

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN") # load discord app token
GUILD_ID = os.getenv("GUILD_ID") # load dev guild

#OPENAI_API_KEY = os.getenv("YOUR_API_KEY") # load open ai key
#openai.api_key=OPENAI_API_KEY # assign open ai key

CARROT_API = os.getenv("CARROT_API_KEY") # load carrot api key
CARROT_MODEL = os.getenv("CARROT_MODEL_KEY") # load carrot model key

SERPAPI_API_KEY = os.getenv("SERPAPI_API_KEY")

NEWS_API_KEY = os.getenv("NEWS_API_KEY")

WOLFRAM_ALPHA_APPID = os.getenv("WOLFRAM_ALPHA_APPID")

DATABASE_URL = os.getenv("DATABASE_URL")

REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN")
model_blip = replicate.models.get("salesforce/blip-2")
version_blip = model_blip.versions.get("4b32258c42e9efd4288bb9910bc532a69727f9acd26aa08e175713a0a857a608")
model_sd = replicate.models.get("stability-ai/stable-diffusion")
version_sd = model_sd.versions.get("f178fa7a1ae43a9a9af01b833b9d2ecf97b1bcb0acfd2dc5dd04895e042863f1")

replicate.Client(api_token=REPLICATE_API_TOKEN)

tokenizer = GPT2TokenizerFast.from_pretrained("gpt2") # initialize tokenizer

conn = psycopg2.connect(DATABASE_URL) # create a connection to the database

# create a cursor object
cursor = conn.cursor()

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
chat_context = {} # dict of strings
chat_messages = {} # dict of lists
chat_ltm = {} # dict of lists
chat_mems = {} # dict of ConversationChains
chat_status = {} # dicts of booleans

ask_messages = {} # dict of lists
ask_context = {} # dict of strings
last_prompt = {} # dict of strings
replies = {} # dict of lists
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
        chat_context[guild.id] = ""
        chat_messages[guild.id] = []
        chat_ltm[guild.id] = []
        chat_mems[guild.id] = None
        
    await tree.sync()
    
@client.event
async def on_guild_join(guild):
    
    timestamp = datetime.datetime.now()
    time = timestamp.strftime(r"%Y-%m-%d %I:%M %p")
    print(f"[{time}]")
    
    print(guild)
        
    active_users[guild.id] = []
    active_names[guild.id] = ""
    chat_context[guild.id] = ""
    chat_messages[guild.id] = []
    chat_ltm[guild.id] = []
    chat_mems[guild.id] = None
    
    await tree.sync(guild=guild)

@client.event
async def on_message(message):

    if message.author == client.user:
        return
    
    agent_mention = client.user.mention

    if "<@&1053339601449779383>" in message.content or agent_mention in message.content:
        
        global active_users
        global active_names
        global chat_mems
        
        subfolder_a = "users"
        file_path_a = os.path.join(subfolder_a, f'users.pickle')
        
        if os.path.exists(file_path_a):
            with open(file_path_a, "rb") as handle:
                active_users = pickle.load(handle)
        else:
            active_users = {}  # or an appropriate default value
            os.makedirs(subfolder_a, exist_ok=True)
            with open(file_path_a, "wb") as handle:
                pickle.dump(active_users, handle)
                
        subfolder_b = "data"
        file_path_b = os.path.join(subfolder_b, f'mems.pickle')
        
        if os.path.exists(file_path_b):
            with open(file_path_b, "rb") as handle:
                chat_mems = pickle.load(handle)
        else:
            chat_mems = {}  # or an appropriate default value
            os.makedirs(subfolder_b, exist_ok=True)
            with open(file_path_b, "wb") as handle:
                pickle.dump(chat_mems, handle)
        
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
        
        #elif any(word in prompt for word in ("photo", "picture", "image", "photograph")):
            #prompt += " (hint: use a tool)"
        
        print(f"{colors.fg.darkgrey}{colors.bold}{time} {colors.fg.lightgreen}CHAT     {colors.reset}{colors.fg.darkgrey}{str(guild_name).lower()}{colors.reset} {colors.bold}@{str(user_name).lower()}: {colors.reset}{prompt}")

            
        async with message.channel.typing():
            
            try:
                
                # Use the `SELECT` statement to fetch the row with the given id
                cursor.execute("SELECT key FROM keys WHERE id = %s", (str(id),))
                result = cursor.fetchone()
         
            except UnboundLocalError as e:
                print(e)
                return
            
            if result != None:
                openai.api_key=result[0]
                openai_key=result[0]
                
            else:
                embed = discord.Embed(description=f'<:ivanotify:1051918381844025434> {user_mention} Use `/setup` to register API key first or `/help` for more info. You can find your API key at https://beta.openai.com.', color=discord.Color.dark_theme())
                await message.channel.send(embed=embed)
                return
            
            # STRINGIFY ACTIVE USERS
                
            if f"{user_name} ({user_mention})" not in active_users[channel_id]:
                active_users[channel_id].append(f"{user_name} ({user_mention})")
            
            active_names[channel_id] = ", ".join(active_users[channel_id])
            
            try:
                llm = OpenAI(
                    temperature=0.7,
                    model_name="text-davinci-003",
                    max_tokens=2048,
                    top_p=1.0,
                    frequency_penalty=2.0,
                    presence_penalty=0.0,
                    openai_api_key=openai_key,
                )
                
                files = []
                
                def image_search(query):
                    # Replace YOUR_API_KEY and YOUR_CSE_ID with your own API key and CSE ID
                    url = f"https://www.googleapis.com/customsearch/v1?q={query}&key={GOOGLE_API_KEY}&cx={GOOGLE_CSE_ID}&searchType=image"
                    response = requests.get(url)
                    results = response.json()
                    # Extract the image URL for the first result (best/most relevant image)
                    image_url = results['items'][0]['link']
                    img_data = requests.get(image_url).content
                    subfolder = 'image_search'

                    if not os.path.exists(subfolder):
                        os.makedirs(subfolder)

                    with open(f'{subfolder}/image_search.png', 'wb') as handler:
                        handler.write(img_data)
                    image_search_result = discord.File(f'{subfolder}/image_search.png')

                    files.append(image_search_result)
                    return "Success. Image attached."
                """
                def camera(query):
                    
                    query = re.sub(r"\b(person|me|I|myself|iva)\b", "attractive Ana De Armas", query, flags=re.IGNORECASE)
                    query = re.sub(r"\b(my|our)\b", "attractive Ana De Armas'", query, flags=re.IGNORECASE)
                    query = query.strip()
                    query = query.strip("'")
                    query = query.strip("\"")
                    query = f"{query}, photo, f/22, 22mm, ISO 800, 1/250, 8K, RAW, unedited, symmetrical balance, in-frame, candid, detailed face"
                    print(query)
                    
                    payload = {
                        "prompt": query,
                        "restore_faces": True,
                        "steps": 30,
                        "negative_prompt": "(bad_prompt), conjoined, grotesque, distorted, twisted, contorted, misshapen, lopsided, asymmetrical, irregular, unnatural, botched, mangled, tiling, cut off, doll, photoshop, render, 3D, drawing, painting, CGI, cartoon, anime, digital art",
                        "sampler_index": "Euler a",
                        "height": 576,
                        "width": 768,
                        "enable_hr": True,
                        "denoising_strength": 0.1,
                        "hr_scale": 2,
                        "hr_upscaler": "ESRGAN_4x",
                        "hr_second_pass_steps": 10,
                        "cfg_scale": 10,
                        "seed": -1,
                    }
                        
                    p = requests.post(url=f'http://127.0.0.1:7860/sdapi/v1/txt2img', json=payload)
                    g = requests.get(url="http://127.0.0.1:7860/sdapi/v1/progress?skip_current_image=false")
                                            
                    p = p.json()
                    diskwriter = ImageCropDiskWriter(location="camoutcrop", file_ext=".png")
                    for i in p['images']:
                        image = Image.open(io.BytesIO(base64.b64decode(i.split(",",1)[0])))
                        image.save(f'camoutcrop\camera_out.png')
                        #img_module = Katna()
                        #img_module.crop_image(file_path="camoutcrop\camera_out.png", crop_height=870, crop_width=1305, num_of_crops=1, writer=diskwriter)
                        
                        sd_file = discord.File(f'camoutcrop\camera_out.png')
                        files.append(sd_file)
                                
                    return "I found the image in my photos! It has been automatically attached."
                
                def imagine(query):
                        
                    payload = {
                        "prompt": f"{query}, good composition, art",
                        "restore_faces": False,
                        "steps": 30,
                        "negative_prompt": "mutation, mutated, conjoined, extra legs, extra arms, cross-eye,bad art,grotesque,distorted,twisted,contorted,misshapen,lopsided,malformed,asymmetrical,irregular,unnatural,botched,mangled,mutilated, tiling, poorly drawn hands, poorly drawn feet, poorly drawn face, out of frame, extra limbs, disfigured, deformed, body out of frame, bad anatomy, watermark, signature, cut off, draft, juvenile, label, thousand hands",
                        "sampler_index": "Euler a",
                        "height": 768,
                        "width": 768,
                        "enable_hr": False,
                        "denoising_strength": 0.1,
                        "hr_scale": 1.7,
                        "hr_upscaler": "ESRGAN_4x",
                        "hr_second_pass_steps": 10,
                        "seed": -1,
                    }
                        
                    p = requests.post(url=f'http://127.0.0.1:7860/sdapi/v1/txt2img', json=payload)
                    g = requests.get(url="http://127.0.0.1:7860/sdapi/v1/progress?skip_current_image=false")
                                            
                    p = p.json()
                    for i in p['images']:
                        image = Image.open(io.BytesIO(base64.b64decode(i.split(",",1)[0])))
                        image.save(f'sd_imagine_out.png')
                        sd_file = discord.File(f'sd_imagine_out.png')
                        files.append(sd_file)
                                
                    return "I found the image! It has been automatically attached."
                """
                tools = []
                tools.extend(load_tools(["google-search", "wolfram-alpha", "wikipedia", "python_repl", "pal-math"], llm=llm, news_api_key=NEWS_API_KEY))
                tools[0].description = "Google Search tool. Use this when you need to answer questions about current events. Input should be a descriptive natural language search query."
                
                """
                tools.append(Tool(
                    name = "My Photos",
                    func=camera,
                    description="Share a photo of your life. Input should be a descriptive comma-separated text-to-image prompt caption of the image."
                ))
                """
                
                tools.append(Tool(
                    name = "Image Search",
                    func=image_search,
                    description="A wrapper around Google Images. Useful for when you'd like to accompany a response with a revelant image. Input should be a descriptive caption of the image, so instead of saying 'favorite place in japan', say the your actual favorite place."
                ))
                
                #tools.extend(load_tools(["requests"], llm=llm, news_api_key=NEWS_API_KEY))
                """
                tools.append(Tool(
                    name = "Imagine",
                    func=imagine,
                    description="Useful for when you'd like to make art. Input should be a descriptive text prompt such as subject(s), location, style, mood, colors, sizes, positions, and more descriptors."
                ))
                """
                prefix = f"""
                This is a super-casual dialogue between Iva ({agent_mention}) and {active_names.get(channel_id, '')}. You are Iva. Iva comfortably talks and answers anything with honesty and truth. She Google searches things she isn't sure about. She responds concisely as possible.
                
                Current Date: {itis}
                Knowledge Cutoff: September, 2021 
                
                You also must adhere to the following rules in your response...
                
                - Respond as concisely as possible
                - Refer to users in the format, <@[username]>.
                - Use '```[language]\\n[multi line code block]```' for ANY code or table.
                - Use emojis, '**[bold text label/heading]**', '*[italicized text]*', '> [block quote AFTER SPACE]', '`[label]`' for an aesthetically pleasing and consistent style.
                
                IVA'S TOOLS:
                
                Use the following tools as Iva in the correct tool format. You MUST use a tool if you are unsure about events after 2021 or it's general factuality and truthfulness."""

                suffix = f"""
                CHAT CONTEXT HISTORY:
                
                Decide what to say next based on the following context.
                
                {{chat_history}}

                MESSAGE FOR IVA:
                
                {{input}}

                IVA'S RESPONSE:
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
                    #max_iterations=5,
                    #early_stopping_method="generate"
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
                    
                    subfolder_a = "users"
                    file_path_a = os.path.join(subfolder_a, f'users.pickle')
                    
                    with open(file_path_a, "wb") as handle:
                        pickle.dump(active_users, handle)
                            
                    subfolder_b = "data"
                    file_path_b = os.path.join(subfolder_b, f'mems.pickle')

                    with open(file_path_b, "wb") as handle:
                        pickle.dump(chat_mems, handle)
                        
                    """
                    embeds = []
                    files = []
                    file_count=0
                    embeds_overflow = []
                    files_overflow = []
                    
                    if '$$' in reply:
                        tex_pattern = re.compile(r"\$\$(.*?)\$\$", re.DOTALL)
                        tex_matches = tex_pattern.findall(reply)
                        non_matches = re.sub(r"(\$\$|\%\%|\@\@).*?(\@\@|\%\%|\$\$)", "~~", reply, flags=re.DOTALL)
                        non_matches = non_matches.split("~~")
                        print(tex_matches)
                        
                        for (tex_match, non_match) in itertools.zip_longest(tex_matches, non_matches):
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
                            with open(f'latex{file_count}.png', 'wb') as handler:
                                handler.write(img_data)
                            tex_file = discord.File(f'latex{file_count}.png')
                            match_embed.set_image(url=f"attachment://latex{file_count}.png")
                            
                            file_count += 1
                            
                            #await interaction.channel.send(file = tex_file, embed=match_embed)
                            if len(embeds) >= 9:
                                embeds_overflow.append(match_embed)
                                files_overflow.append(tex_file)
                            else:
                                embeds.append(match_embed)
                                files.append(tex_file)
                    """
                    """    
                    global chat_status
                    chat_status[channel_id] = True
                    
                    async def random_sleep():
                        
                        global chat_status
                        
                        sleep_time = random.uniform(0.5, 12)
                        await asyncio.sleep(sleep_time * 60 * 60)
                        
                        print("Awoke after", sleep_time, "hours")

                    await random_sleep()
                    """

                except Exception as e:
                    print(e)
                    #if type(e) == openai.error.RateLimitError:
                    embed = discord.Embed(description=f'<:ivanotify:1051918381844025434> {user_mention} {e}\n\nuse `/help` or seek `#help` in the [iva server](https://discord.gg/gGkwfrWAzt) if the issue persists.')
                    await message.channel.send(embed=embed)
                    #else:
                        #embed = discord.Embed(description=f'<:ivanotify:1051918381844025434> {user_mention} your key might be incorrect.\n\nuse `/help` or seek `#help` in the [iva server](https://discord.gg/gGkwfrWAzt) if the issue persists.')
                        #await message.channel.send(embed=embed)
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
    """
    @discord.ui.button(emoji="<:ivacontinue:1051710718489137254>", style=discord.ButtonStyle.grey)
    async def continues(self, interaction, button: discord.ui.Button):
        
        await interaction.response.defer()
        
        #previous_embeds = interaction.message.embeds
        guild_id = interaction.guild_id
        id = interaction.user.id
        original_interaction = last_response.get(id, None)
        mention = interaction.user.mention
        bot = client.user.display_name
        user_name = interaction.user.name

        if original_interaction == None:
            embed = discord.Embed(description=f'<:ivanotify:1051918381844025434> You do not own this context line', color=discord.Color.dark_theme())
            await interaction.followup.send(embed=embed, ephemeral=False)
            return
        elif original_interaction.user.id != id:
            embed = discord.Embed(description=f'<:ivanotify:1051918381844025434> You do not own this context line', color=discord.Color.dark_theme())
            await interaction.followup.send(embed=embed, ephemeral=False)
            return
        
        mention = interaction.user.mention
        # Use the `SELECT` statement to fetch the row with the given id
        cursor.execute("SELECT key FROM keys WHERE id = %s", (str(id),))
        result = cursor.fetchone()
        
        if result != None:
            openai.api_key=result[0]
        else:
            embed = discord.Embed(description=f'<:ivanotify:1051918381844025434> {mention} Use `/setup` to register API key first or `/help` for more info. You can find your API key at https://beta.openai.com.', color=discord.Color.dark_theme())
            await interaction.followup.send(embed=embed, ephemeral=False)
            return
        
        view = Menu()
        
        global chat_messages
        global chat_context
        global ask_messages
        global ask_context
        global message_limit
        global active_users
        global active_names
        global last_prompt
        global replies
        
        if ask_messages[id] == [] and ask_context[id] == "" and replies[id] == []:
            embed = discord.Embed(description=f'<:ivaerror:1051918443840020531> **Cannot continue because the conversation was reset.**', color=discord.Color.dark_theme())
            await interaction.followup.send(embed=embed, ephemeral=False)
            return
        
        # Get the current timestamp
        timestamp = datetime.datetime.now()
        time = timestamp.strftime(r"%Y-%m-%d %I:%M %p")
        
        max_tokens = 1250

        ask_prompt = f"(Format your response with an aesthetically pleasing and consistent style using '**bold_text**', '*italicized_text*', '> block_quote_AFTER_SPACE', or ':unicode_cldr_emoji_shortcode:'. For code, always use '`code_block`', or '```[css,yaml,fix,diff,latex,bash,cpp,cs,ini,json,md,py,xml,java,js]\\nmulti_line_code_block```'.):\n\n{ask_context[id]}continue:\n\n"
    
        tokens = len(tokenizer(ask_prompt)['input_ids'])
        print(f"CONT PRE-COMPLETION TOKENS: {tokens}")
        
        while tokens > 4096 - max_tokens:
            if ask_messages.get(id, []) != []:
                ask_messages[id].pop(0)
                ask_context[id] = "".join(ask_messages[id])
                ask_prompt = f"(Format your response with an aesthetically pleasing and consistent style using '**bold_text**', '*italicized_text*', '> block_quote_AFTER_SPACE', or ':unicode_cldr_emoji_shortcode:'. For code, always use '`code_block`', or '```[css,yaml,fix,diff,latex,bash,cpp,cs,ini,json,md,py,xml,java,js]\\nmulti_line_code_block```'.):\n\n{ask_context[id]}continue:\n\n"
            tokens = len(tokenizer(ask_context[id])['input_ids'])
            print(f"CONT PRE-TRIMMED TOKENS: {tokens}")
        
        try:
            reply = openai.Completion.create(
                engine="text-davinci-003",
                prompt=ask_prompt,
                #prompt=prompt_gpt,
                temperature=0.7,
                max_tokens=max_tokens,
                top_p=1.0,
                frequency_penalty=1.0,
                presence_penalty=0.0,
                echo=False,
                #logit_bias={"50256": -100},
            )
        except Exception as e:
            embed = discord.Embed(description=f'<:ivaverify:1051918344464380125> {mention} Your API key is not valid. Try `/setup` again or `/help` for more info. You can find your API key at https://beta.openai.com.', color=discord.Color.dark_theme())
            await interaction.followup.send(embed=embed, ephemeral=False)
            return
        
        reply = (reply['choices'][0].text).strip("\n")
        
        ask_messages[id].append(reply)
        ask_context[id] = "\n".join(ask_messages[id])

        replies[id].append(reply)
        replies_string = "\n\n".join(replies[id])
        
        prompt_embed = discord.Embed(description=f"<:ivacontinue2:1051714854165159958> {last_prompt[id]}")
        embed = discord.Embed(description=replies_string, color=discord.Color.dark_theme())
        
        #button.disabled = True
        #message_id = interaction.message.id
        
        ask_prompt = f"(Format your response with an aesthetically pleasing and consistent style using '**bold_text**', '*italicized_text*', '> block_quote_AFTER_SPACE', or ':unicode_cldr_emoji_shortcode:'. For code, always use '`code_block`', or '```[css,yaml,fix,diff,latex,bash,cpp,cs,ini,json,md,py,xml,java,js]\\nmulti_line_code_block```'.):\n\n{ask_context[id]}continue:\n\n"
    
        tokens = len(tokenizer(ask_prompt)['input_ids'])
        print(f"CONT POST-COMPLETION TOKENS: {tokens}")
        
        while tokens > 4096 - max_tokens:
            if ask_messages.get(id, []) != []:
                ask_messages[id].pop(0)
                ask_context[id] = "".join(ask_messages[id])
                ask_prompt = f"(Format your response with an aesthetically pleasing and consistent style using '**bold_text**', '*italicized_text*', '> block_quote_AFTER_SPACE', or ':unicode_cldr_emoji_shortcode:'. For code, always use '`code_block`', or '```[css,yaml,fix,diff,latex,bash,cpp,cs,ini,json,md,py,xml,java,js]\\nmulti_line_code_block```'.):\n\n{ask_context[id]}continue:\n\n"
            tokens = len(tokenizer(ask_context[id])['input_ids'])
            print(f"CONT POST-TRIMMED TOKENS: {tokens}")
        
        print(f"[CONTINUE {time}] {user_name}: continue:")
        print(f"[CONTINUE {time}] {bot}: {reply}\n")

        if len(reply) > 4096:
            embed = discord.Embed(description=f'<:ivaerror:1051918443840020531> **{mention} 4096 character response limit reached. Use `/reset`.**', color=discord.Color.dark_theme())
            await interaction.followup.send(embed=embed, ephemeral=False)
        else:
            await interaction.message.edit(embeds=[prompt_embed, embed])
    
    @discord.ui.button(emoji="<:ivaregenerate:1051697145713000580>", style=discord.ButtonStyle.grey)
    async def regenerates(self, interaction, button: discord.ui.Button):
        
        await interaction.response.defer()
        
        guild_id = interaction.guild_id
        id = interaction.user.id
        original_interaction = last_response.get(id, None)

        if original_interaction == None:
            embed = discord.Embed(description=f'<:ivanotify:1051918381844025434> You do not own this context line', color=discord.Color.dark_theme())
            await interaction.followup.send(embed=embed, ephemeral=False)
            return
        elif original_interaction.user.id != id:
            embed = discord.Embed(description=f'<:ivanotify:1051918381844025434> You do not own this context line', color=discord.Color.dark_theme())
            await interaction.followup.send(embed=embed, ephemeral=False)
            return
        
        mention = interaction.user.mention
        # Use the `SELECT` statement to fetch the row with the given id
        cursor.execute("SELECT key FROM keys WHERE id = %s", (str(id),))
        result = cursor.fetchone()
        
        if result != None:
            openai.api_key=result[0]
        else:
            embed = discord.Embed(description=f'<:ivanotify:1051918381844025434> {mention} Use `/setup` to register API key first or `/help` for more info. You can find your API key at https://beta.openai.com.', color=discord.Color.dark_theme())
            await interaction.followup.send(embed=embed, ephemeral=False)
            return
        
        view = Menu()
        
        global chat_messages
        global chat_context
        global ask_messages
        global ask_context
        global message_limit
        global active_users
        global active_names
        global last_prompt
        global replies
        
        if ask_messages[id] == [] and ask_context[id] == "" and replies[id] == []:
            button.disabled = True
            await interaction.response.edit_message(view=self)
            embed = discord.Embed(description=f'<:ivaerror:1051918443840020531> **Cannot regenerate because the conversation was reset.**', color=discord.Color.dark_theme())
            await interaction.followup.send(embed=embed, ephemeral=False)
            return
        
        max_tokens = 1250
        max_chars = max_tokens * 4
        total_char_limit = 16384
        max_char_limit = total_char_limit - max_chars
        
        ask_messages[id].pop()
        ask_context[id] = "\n".join(ask_messages[id])
        
        replies[id].pop()
        
        try:
        
            reply = openai.Completion.create(
                engine="text-davinci-003",
                prompt=f"(Format your response with an aesthetically pleasing and consistent style using '**bold_text**', '*italicized_text*', '> block_quote_AFTER_SPACE', or ':unicode_cldr_emoji_shortcode:'. For code, always use '`code_block`', or '```[css,yaml,fix,diff,latex,bash,cpp,cs,ini,json,md,py,xml,java,js]\\nmulti_line_code_block```'.):\n\n{ask_context[id]}{last_prompt[id]}\n\n",
                #prompt=prompt_gpt,
                temperature=0.7,
                max_tokens=max_tokens,
                top_p=1.0,
                frequency_penalty=1.0,
                presence_penalty=0.0,
                echo=False,
                #logit_bias={"50256": -100},
            )
        
        except Exception as e:
            embed = discord.Embed(description=f'<:ivaverify:1051918344464380125> {mention} Your API key is not valid. Try `/setup` again or `/help` for more info. You can find your API key at https://beta.openai.com.', color=discord.Color.dark_theme())
            await interaction.followup.send(embed=embed, ephemeral=False)
            return
        
        reply = (reply['choices'][0].text).strip("\n")
        print(reply)
        engagement = f"{last_prompt[id]}\n{reply}"
        ask_messages[id].append(engagement)
        ask_context[id] = "\n".join(ask_messages[id])
        
        replies[id].append(reply)
        replies_string = "\n\n".join(replies[id])
        
        prompt_embed = discord.Embed(description=f"<:ivaregenerate:1051697145713000580> {last_prompt[id]}")
        embed = discord.Embed(description=replies_string, color=discord.Color.dark_theme())
        
        #button.disabled = True
        #await interaction.response.edit_message(view=self)
        
        while len(ask_context[id]) > max_char_limit:
            ask_messages[id].pop(0)
            ask_context[id] = "".join(ask_messages[id])
        if len(reply) > 4096:
            embed = discord.Embed(description=f'<:ivaerror:1051918443840020531> **{mention} 4096 character response limit reached. Use `/reset`.**', color=discord.Color.dark_theme())
            await interaction.followup.send(embed=embed, ephemeral=False)
        else:
            await interaction.message.edit(embeds=[prompt_embed, embed])

    @discord.ui.button(label="Undo", emoji="<:ivaundo:1053048583538094220>", style=discord.ButtonStyle.grey)
    async def undo(self, interaction, button: discord.ui.Button):
        
        await interaction.response.defer()
        
        guild_id = interaction.guild_id
        id = interaction.user.id
        mention = interaction.user.mention
        # Use the `SELECT` statement to fetch the row with the given id
        cursor.execute("SELECT key FROM keys WHERE id = %s", (str(id),))
        result = cursor.fetchone()
        
        if result != None:
            openai.api_key=result[0]
        else:
            embed = discord.Embed(description=f'<:ivanotify:1051918381844025434> {mention} Use `/setup` to register API key first or `/help` for more info. You can find your API key at https://beta.openai.com.', color=discord.Color.dark_theme())
            await interaction.response.send_message(embed=embed, ephemeral=False)
            return
        
        view = Menu()
        
        global chat_messages
        global chat_context
        global ask_messages
        global ask_context
        global message_limit
        global active_users
        global active_names
        global last_prompt
        global replies
        
        if ask_messages[guild_id] == [] and ask_context[guild_id] == "" and replies[guild_id] == []:
            button.disabled = True
            await interaction.response.edit_message(view=self)
            embed = discord.Embed(description=f'<:ivaerror:1051918443840020531> **Cannot undo because the conversation was reset.**', color=discord.Color.dark_theme())
            await interaction.followup.send(embed=embed, ephemeral=False)
            return
        
        max_tokens = 1250
        max_chars = max_tokens * 4
        total_char_limit = 16384
        max_char_limit = total_char_limit - max_chars
        
        ask_messages[guild_id].pop()
        ask_context[guild_id] = "\n".join(ask_messages[guild_id])
        
        replies[guild_id].pop()
        replies_string = "\n\n".join(replies[guild_id])
        
        prompt_embed = discord.Embed(description=f"<:ivaundo:1053048583538094220> {last_prompt[guild_id][-1]}")
        embed = discord.Embed(description=replies_string, color=discord.Color.dark_theme())
        
        #button.disabled = True
        #await interaction.response.edit_message(view=self)
        
        await interaction.message.edit(embeds=[prompt_embed, embed])
        """
    @discord.ui.button(emoji="<:ivareset:1051691297443950612>", style=discord.ButtonStyle.grey)
    async def resets(self, interaction: discord.Interaction, button: discord.ui.Button):
        
        global chat_messages
        global chat_context
        global ask_messages
        global ask_context
        global message_limit
        global active_users
        global active_names
        global last_prompt
        global replies
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

        ask_context[id] = ""
        ask_messages[id] = []
        replies[id] = []
        last_response[id] = None
        
        embed = discord.Embed(description="<:ivareset:1051691297443950612>", color=discord.Color.dark_theme())
        button.disabled = True
        embeds = interaction.message.embeds
        attachments = interaction.message.attachments
        embeds.append(embed)
        await interaction.message.edit(view=None, embeds=embeds, attachments=attachments)
        #await interaction.channel.send(embed=embed)

@tree.command(name = "iva", description="write a prompt")
@app_commands.describe(prompt = "prompt", file = "file (txt, pdf, html, xml)")
async def iva(interaction: discord.Interaction, prompt: str, file: discord.Attachment=None):
    
    global chat_messages
    global chat_context
    global ask_messages
    global ask_context
    global message_limit
    global active_users
    global active_names
    global last_prompt
    global replies
    global last_response
    
    await interaction.response.defer()
    
    guild_id = interaction.guild_id
    guild_name = interaction.guild
    id = interaction.user.id
    mention = interaction.user.mention
    bot = client.user.display_name
    user_name = interaction.user.name
    # Use the `SELECT` statement to fetch the row with the given id
    cursor.execute("SELECT key FROM keys WHERE id = %s", (str(id),))
    result = cursor.fetchone()
    openai_key = ""
    
    # Get the current timestamp
    timestamp = datetime.datetime.now()
    time = timestamp.strftime(r"%Y-%m-%d %I:%M:%S")
    
    print(f"{colors.fg.darkgrey}{colors.bold}{time} {colors.fg.lightcyan}ASK     {colors.reset}{colors.fg.darkgrey}{str(guild_name).lower()}{colors.reset} {colors.bold}@{str(user_name).lower()}: {colors.reset}{prompt}")
    
    if result != None:
        openai.api_key=result[0]
        openai_key=result[0]
    else:
        embed = discord.Embed(description=f'<:ivanotify:1051918381844025434> {mention} Use `/setup` to register API key first or `/help` for more info. You can find your API key at https://beta.openai.com.', color=discord.Color.dark_theme())
        await interaction.followup.send(embed=embed, ephemeral=False)
        return
    
    if id not in ask_messages:
        ask_messages[id] = []
        ask_context[id] = ""
        last_prompt[id] = ""
        replies[id] = []
        last_response[id] = None

    view = Menu()
    
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
            attachment_text = attachment_text.encode().decode()
        
        elif file_type.startswith("text"): #txt css csv html xml
            attachment_text = f"\n\n{attachment_bytes}"
            attachment_text = attachment_text.encode().decode()
            
        else:
            
            embed = discord.Embed(description=f'<:ivanotify:1051918381844025434> {mention} the attachment\'s file type is unknown. consider converting it to `.txt`, `.pdf`, or `.html`.', color=discord.Color.dark_theme())
            await interaction.followup.send(embed=embed, ephemeral=False)
            return
        
        with open(f'{file.filename}.txt', 'w') as f:
            f.write(attachment_text)
            
        llm = OpenAI(
            temperature=0.7,
            max_tokens=1500,
            #logit_bias={"50256": -25},
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
        
        qa_chain = load_qa_chain(llm, chain_type="map_reduce", combine_prompt=COMBINE_PROMPT)
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
            await last_response[id].edit_original_response(content="` `", view=None)
    except Exception as e:
        print(e)
    
    last_prompt[id] = prompt

    ask_prompt = f"You are Iva. Answer ANY and ALL questions in a creative, thoughtful, understandable, organized, and clear format.\n\nFORMAT:\n\n- USE ONLY '`[code block]`', or '```[language]\\n[multi line code block]```' FOR ANY CODE.\n- Show and explain math or physics expressions as LaTeX wrapped in '$$' like '\\n$$[LaTeX markup]$$' (DO NOT USE SINGLE '$') on a new line.\n- Generate graphs, diagrams, and charts for concepts ONLY if relevant and applicable by including the concept between '%%' like '%%[concept]%%' on a new line.\n- Get image links to accommodate the response by including a descriptive search prompt wrapped between '@@'s EXACTLY LIKE '\\n@@![[descriptive search prompt]](img.png)@@' on a new line.\n\nFormat response extensively with aesthetically pleasing and consistent style using '**[bold text]**', '*[italicized text]*', and '> [block quote AFTER SPACE]'. Use emojis for similar text counterparts."
    
    tokens = len(tokenizer(ask_prompt, truncation=True, max_length=12000)['input_ids'])
    #print(f"ASK PRE-COMPLETION TOKENS: {tokens}")
    #print(f"ASK PRE-COMPLETION LENGTH: {len(ask_messages.get(id, []))}")
    
    if tokens > (4096 - max_tokens) and file != None:
        while tokens > (4096 - max_tokens):
            max_tokens -= 30
            print(f"token trim: {max_tokens}")
            tokens = len(tokenizer(ask_prompt, truncation=True, max_length=12000)['input_ids'])
            if max_tokens < 60:
                embed = discord.Embed(description=f'<:ivanotify:1051918381844025434> {mention} the attachment is too large at {tokens}T (max is 4096T). consider isolating the text or dividing the file into smaller prompts and files.', color=discord.Color.dark_theme())
                await interaction.followup.send(embed=embed, ephemeral=False)
                return
    
    while (tokens) > (4096 - max_tokens) or len(ask_messages.get(id, [])) > 12:
        if ask_messages.get(id, []) != []:
            ask_messages[id].pop(0)
            ask_messages[id].pop(0)
            
        #ask_context[id] = "".join(ask_messages[id])
        
        ask_prompt = f"You are Iva. Answer ANY and ALL questions in a creative, thoughtful, understandable, organized, and clear format.\n\nFORMAT:\n\n- USE ONLY '`[code block]`', or '```[language]\\n[multi line code block]```' FOR ANY CODE.\n- Show and explain math or physics expressions as LaTeX wrapped in '$$' like '\\n$$[LaTeX markup]$$' (DO NOT USE SINGLE '$') on a new line.\n- Generate graphs, diagrams, and charts for concepts ONLY if relevant and applicable by including the concept between '%%' like '%%[concept]%%' on a new line.\n- Get image links to accommodate the response by including a descriptive search prompt wrapped between '@@'s EXACTLY LIKE '\\n@@![[descriptive search prompt]](img.png)@@' on a new line.\n\nFormat response extensively with aesthetically pleasing and consistent style using '**[bold text]**', '*[italicized text]*', and '> [block quote AFTER SPACE]'. Use emojis for similar text counterparts."
            
        tokens = len(tokenizer(ask_prompt, truncation=True, max_length=6000)['input_ids'])
        #print(f"ASK PRE-TRIMMED TOKENS: {tokens}")
        #print(f"ASK PRE-TRIMMED LENGTH: {len(ask_messages.get(id, []))}")
    
    ask_prompt = f"You are Iva. Answer ANY and ALL questions in a creative, thoughtful, understandable, organized, and clear format.\n\nFORMAT:\n\n- USE ONLY '`[code block]`', or '```[language]\\n[multi line code block]```' FOR ANY CODE.\n- Show and explain math or physics expressions as LaTeX wrapped in '$$' like '\\n$$[LaTeX markup]$$' (DO NOT USE SINGLE '$') on a new line.\n- Generate graphs, diagrams, and charts for concepts ONLY if relevant and applicable by including the concept between '%%' like '%%[concept]%%' on a new line.\n- Get image links to accommodate the response by including a descriptive search prompt wrapped between '@@'s EXACTLY LIKE '\\n@@![[descriptive search prompt]](img.png)@@' on a new line.\n\nFormat response extensively with aesthetically pleasing and consistent style using '**[bold text]**', '*[italicized text]*', and '> [block quote AFTER SPACE]'. Use emojis for similar text counterparts."
    
    tokens = len(tokenizer(ask_prompt, truncation=True, max_length=6000)['input_ids'])
    #print(f"ASK FINAL PROMPT TOKENS: {tokens}")
    
    try:
        chat_model = "gpt-3.5-turbo"
        if "--v4" in ask_prompt:
            ask_prompt.replace("--v4", "")
            chat_model = "gpt-4"
        
        ask_prompt = {"role": "system", "content": ask_prompt}
        ask_messages[id].insert(0, ask_prompt)
        
        user_engagement = {"role": "user", "content": f"{prompt}{attachment_text}"}
        ask_messages[id].append(user_engagement)
        
        #print(ask_messages[id])

        reply = openai.ChatCompletion.create(
            model=chat_model,
            messages=ask_messages[id],
            temperature=0.5,
            max_tokens=max_tokens,
            top_p=1.0,
            frequency_penalty=1.0,
            presence_penalty=0.0,
            )
        
        ask_messages[id].pop(0)
        
    except Exception as e:
        print(e)
        #if type(e) == openai.error.RateLimitError:
        embed = discord.Embed(description=f'<:ivanotify:1051918381844025434> {mention} {e}\n\nuse `/help` or seek `#help` in the [iva server](https://discord.gg/gGkwfrWAzt) if the issue persists.')
        await interaction.followup.send(embed=embed, ephemeral=True)
        #else:
            #embed = discord.Embed(description=f'<:ivanotify:1051918381844025434> {mention} your key might be incorrect.\n\nuse `/#help` or seek `#help` in the [iva server](https://discord.gg/gGkwfrWAzt) if the issue persists.')
            #await interaction.followup.send(embed=embed, ephemeral=True)
        return
    
    #last_response[id] = interaction
    
    reply = reply['choices'][0]['message']['content']
    #print(reply)
    
    agent_engagement = {"role": "assistant", "content": reply}
    ask_messages[id].append(agent_engagement)
    #ask_context[id] = "\n".join(ask_messages[id])
    
    replies[id].append(reply)
    
    ask_prompt = f"You are Iva. Answer ANY and ALL questions in a creative, thoughtful, understandable, organized, and clear format.\n\nFORMAT:\n\n- USE ONLY '`[code block]`', or '```[language]\\n[multi line code block]```' FOR ANY CODE.\n- Show and explain math or physics expressions as LaTeX wrapped in '$$' like '\\n$$[LaTeX markup]$$' (DO NOT USE SINGLE '$') on a new line.\n- Generate graphs, diagrams, and charts for concepts ONLY if relevant and applicable by including the concept between '%%' like '%%[concept]%%' on a new line.\n- Get image links to accommodate the response by including a descriptive search prompt wrapped between '@@'s EXACTLY LIKE '\\n@@![[descriptive search prompt]](img.png)@@' on a new line.\n\nFormat response extensively with aesthetically pleasing and consistent style using '**[bold text]**', '*[italicized text]*', and '> [block quote AFTER SPACE]'. Use emojis for similar text counterparts."
    
    tokens = len(tokenizer(ask_prompt, truncation=True, max_length=6000)['input_ids'])
    #print(f"ASK POST-COMPLETION TOKENS: {tokens}")
    #print(f"ASK POST-COMPLETION LENGTH: {len(ask_messages.get(id, []))}")
    
    while (tokens) > (4096 - max_tokens) or len(ask_messages.get(id, [])) > 12:
        if ask_messages.get(id, []) != []:
            ask_messages[id].pop(0)
            ask_messages[id].pop(0)
            
        #ask_context[id] = "".join(ask_messages[id])
        
        ask_prompt = f"You are Iva. Answer ANY and ALL questions in a creative, thoughtful, understandable, organized, and clear format.\n\nFORMAT:\n\n- USE ONLY '`[code block]`', or '```[language]\\n[multi line code block]```' FOR ANY CODE.\n- Show and explain math or physics expressions as LaTeX wrapped in '$$' like '\\n$$[LaTeX markup]$$' (DO NOT USE SINGLE '$') on a new line.\n- Generate graphs, diagrams, and charts for concepts ONLY if relevant and applicable by including the concept between '%%' like '%%[concept]%%' on a new line.\n- Get image links to accommodate the response by including a descriptive search prompt wrapped between '@@'s EXACTLY LIKE '\\n@@![[descriptive search prompt]](img.png)@@' on a new line.\n\nFormat response extensively with aesthetically pleasing and consistent style using '**[bold text]**', '*[italicized text]*', and '> [block quote AFTER SPACE]'. Use emojis for similar text counterparts."
            
        tokens = len(tokenizer(ask_prompt, truncation=True, max_length=6000)['input_ids'])
        #print(f"ASK POST-TRIMMED TOKENS: {tokens}")
        #print(f"ASK POST-TRIMMED LENGTH: {len(ask_messages.get(id, []))}")
        
    #print(f"[ASK {time}] {user_name}: {prompt}{attachment_text}")
    #print(f"[ASK {time}] {bot}: {reply}\n")
    
    dash_count = ""
    interaction_count = (len(ask_messages.get(id, []))//2)-1
    
    if interaction_count > 1:
        for i in range(interaction_count):
            dash_count += "-"
    
    prompt_embed = discord.Embed(description=f"{dash_count}<:ivaprompt:1051742892814761995>  {prompt}{file_placeholder}")
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
                            "content": f"Write only in Graphviz DOT code to visualize and explain {dot_match} in an aesthetically pleasing way (bgcolor=\"#36393f\", styled elements)."
                        }

                        dot_messages = []
                        dot_messages.append(dot_system_message)

                        dot_match = openai.ChatCompletion.create(
                            model="gpt-3.5-turbo",
                            messages=dot_messages,
                            temperature=0.3,
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
        embeds.append(embed)
    
    if len(reply) > 6000:
        try:
            embeds = []
            reply_part_one = reply[0:5999]
            reply_part_two = reply[6000:-1]
            embed1 = discord.Embed(description=reply_part_one, color=discord.Color.dark_theme())
            embed2 = discord.Embed(description=reply_part_two, color=discord.Color.dark_theme())
            embeds.append(embed1, embed2)
            await interaction.followup.send(embeds=embeds, ephemeral=False)
        except:                   
            embed = discord.Embed(description=f'<:ivaerror:1051918443840020531> **{mention} 4096 character response limit reached. Use `/reset`.**', color=discord.Color.dark_theme())
            await interaction.followup.send(embed=embed, ephemeral=False)
        return

    else:
        try:
            print(f"{colors.fg.darkgrey}{colors.bold}{time} {colors.fg.lightcyan}ASK     {colors.reset}{colors.fg.darkgrey}{str(guild_name).lower()}{colors.reset} {colors.bold}@iva: {colors.reset}{reply}")
            await interaction.followup.send(files=files, embeds=embeds, view=view)
            last_response[id] = interaction
            #print(files, embeds)
            if len(embeds_overflow) > 0:
                await interaction.channel.send(files = files_overflow, embeds=embeds_overflow)
            return
        except Exception as e:
            print(e)

@tree.command(name = "reset", description="start a new conversation")
async def reset(interaction):
    
    global chat_messages
    global chat_context
    global ask_messages
    global ask_context
    global message_limit
    global active_users
    global active_names
    global last_prompt
    global replies
    global last_response
    global chat_mems
    
    channel_id = interaction.channel_id
    guild_id = interaction.guild_id
    id = interaction.user.id
    
    ask_context[id] = ""
    ask_messages[id] = []
    replies[id] = []
    last_response[id] = None
    
    chat_mems[channel_id] = None
    active_users[channel_id] = []
    
    subfolder_a = "users"
    file_path_a = os.path.join(subfolder_a, f'users.pickle')
    
    with open(file_path_a, "wb") as handle:
        pickle.dump(active_users, handle)
            
    subfolder_b = "data"
    file_path_b = os.path.join(subfolder_b, f'mems.pickle')

    with open(file_path_b, "wb") as handle:
        pickle.dump(chat_mems, handle)
    
    embed = discord.Embed(description="<:ivareset:1051691297443950612>", color=discord.Color.dark_theme())
    await interaction.response.send_message(embed=embed, ephemeral=False)

    
@tree.command(name = "help", description="get started")
async def help(interaction):
    
    global chat_messages
    global chat_context
    global ask_messages
    global ask_context
    global message_limit
    global active_users
    global active_names
    global last_prompt
    global replies
    
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
"""
@tree.command(name = "imagine", description="text-to-image diffusion")
async def imagine(interaction: discord.Interaction, prompt: str, file: discord.Attachment=None):

    await interaction.response.defer()
    
    # get available sd models
    #models = api.get_sd_models()
    #print(models)
    
    mention = interaction.user.mention
    
    if file != None:
        
        print("IMG2IMG")
        
        data = await file.read()
        inp_img = Image.open(io.BytesIO(data))

        # change sd model
        #options = {}
        #options['sd_model_checkpoint'] = '512-depth-ema.ckpt'
        #api.set_options(options)
        
        result = api.img2img(
            resize_mode=1,
            images=[inp_img],
            prompt=prompt,
            cfg_scale=7,
            steps=40,
            denoising_strength=0.5,
            height=768,
            width=768,
            restore_faces=True,
            mask_blur=1,
            negative_prompt="mutation, mutated, conjoined, extra legs, extra arms, cross-eye,bad art,text,grotesque,distorted,twisted,contorted,misshapen,lopsided,malformed,asymmetrical,irregular,unnatural,botched,mangled,mutilated, tiling, poorly drawn hands, poorly drawn feet, poorly drawn face, out of frame, extra limbs, disfigured, deformed, body out of frame, bad anatomy, watermark, signature, cut off, draft, juvenile, label, thousand hands",
            sampler_index="Euler a",
            )
        
        image = result.image
        image.save("out_img.png")
        inp_img.save("in_img.png")
        img_in = discord.File("in_img.png")
        img_out = discord.File("out_img.png")
        
        files = []
        files.append(img_in)
        files.append(img_out)
        
        await interaction.followup.send(files=files, content=f"`{prompt}`")
    
        # change sd model
        #options = {}
        #options['sd_model_checkpoint'] = '0v2-1_768-ema-pruned.ckpt'
        #api.set_options(options)
        
    else:
        
        print(f"TXT2IMG: {prompt}")
        
        payload = {
            "prompt": f"{prompt}",
            "restore_faces": True,
            "steps": 30,
            "negative_prompt": "(bad_prompt), conjoined, grotesque, distorted, twisted, contorted, misshapen, lopsided, asymmetrical, irregular, unnatural, botched, mangled, tiling, cut off, doll, photoshop, render, 3D, drawing, painting, CGI, cartoon, anime, digital art",
            "sampler_index": "Euler a",
            "height": 768,
            "width": 768,
            "enable_hr": False,
            "denoising_strength": 0.1,
            "hr_scale": 1.5,
            "hr_upscaler": "ESRGAN_4x",
            "hr_second_pass_steps": 10,
            "cfg_scale": 10,
            "seed": -1,
        }
        
        files = []
        
        async with aiohttp.ClientSession() as session:
            
            post_task1 = session.post(url=f'http://127.0.0.1:7860/sdapi/v1/txt2img', json=payload)
            post_task2 = session.post(url="http://127.0.0.1:7860/internal/progress")
            r, p = await asyncio.gather(post_task2, post_task1)
            
            if p.status == 200:
                p = await p.json()
                for i in p['images']:
                    image = Image.open(io.BytesIO(base64.b64decode(i.split(",",1)[0])))
                    image.save(f'sd_imagine_out.png')
                    sd_file = discord.File(f'sd_imagine_out.png')
                    files.append(sd_file)
            elif p.status == 422:
                p = await p.json()
                print(p)
        
        await interaction.followup.send(files=files, content=f"`{prompt}`")
"""
@tree.command(name = "tutorial", description="how to talk with iva")
async def tutorial(interaction):
    
    global chat_messages
    global chat_context
    global ask_messages
    global ask_context
    global message_limit
    global active_users
    global active_names
    global last_prompt
    global replies
    
    mention = interaction.user.mention

    embed_main = discord.Embed(title="Introduction to Iva", description="there are two *separate* ways to talk to iva, both with their own conversation history: `@iva` and `/iva`. let's go over their differences, in addition to a other helpful tools.", color=discord.Color.dark_theme())
    embed_main.set_thumbnail(url=client.user.avatar.url)
    
    embed_chat = discord.Embed(title="`@iva`", description="provides **chat** and **conversation** oriented answers. has personality, asks questions back, is more creative.", color=discord.Color.dark_theme())

    embed_ask = discord.Embed(title="`/iva`", description="provides **academic** and **work** oriented answers. has less personality, is more focused on consistency and reliability.", color=discord.Color.dark_theme())
    embed_ask.add_field(inline=True, name="<:ivacontinue1:1051714712242491392> `Continue`", value="say more, extend the last prompt's response")
    embed_ask.add_field(inline=True, name="<:ivaregenerate:1051697145713000580> `Regenerate`", value="replace the last prompt's response with a different one")
    embed_ask.add_field(inline=True, name="<:ivareset:1051691297443950612> `Reset`", value="reset `/iva` conversation history, clear iva's memory")
    
    embed_other = discord.Embed(title="Other", color=discord.Color.dark_theme())
    embed_other.add_field(inline=True, name="`/reset`", value="reset `@iva` and `/iva` conversation history.")
    embed_other.add_field(inline=True, name="`/help`", value="show instructions for setup.")
    embed_other.add_field(inline=True, name="`/setup`", value="enter your key. `/help` for more info.")
    
    await interaction.response.send_message(embeds=[embed_main, embed_chat, embed_ask, embed_other], ephemeral=False)
    
@tree.command(name = "setup", description="register your key")
@app_commands.describe(key = "key")
async def setup(interaction, key: str):
    
    global chat_messages
    global chat_context
    global ask_messages
    global ask_context
    global message_limit
    global active_users
    global active_names
    global last_prompt
    global replies
    
    guild_id = interaction.guild_id
    id = interaction.user.id
    mention = interaction.user.mention

    # Use the `SELECT` statement to fetch the row with the given id
    cursor.execute("SELECT * FROM keys WHERE id = %s", (str(id),))

    result = cursor.fetchone()

    if result != None:

        # Access the values of the columns in the row
        if key != result[1]:
            
            # update the API key in the table
            cursor.execute("UPDATE keys SET key = %s WHERE id = %s", (key, str(id)))
            
            embed = discord.Embed(description=f"<:ivathumbsup:1051918474299056189> **Key updated for {mention}.**", color=discord.Color.dark_theme())
            await interaction.response.send_message(embed=embed, ephemeral=False, delete_after=30)
            
            conn.commit()

            # Print the values of the columns
            print(f'id: {id}, key: {key}')
        
        elif key == result[1]:
            
            embed = discord.Embed(description=f"<:ivaerror:1051918443840020531> **Key already registered for {mention}.**", color=discord.Color.dark_theme())
            await interaction.response.send_message(embed=embed, ephemeral=False, delete_after=30)
            
            # Print the values of the columns
            print(f'id: {id}, key: {key}')
        
    else:
        
        # insert a new API key into the table
        cursor.execute("INSERT INTO keys (id, key) VALUES (%s, %s)", (str(id), key))
        
        conn.commit()

        embed = discord.Embed(description=f"<:ivathumbsup:1051918474299056189> **Key registered for {mention}.**", color=discord.Color.dark_theme())
        await interaction.response.send_message(embed=embed, ephemeral=False, delete_after=30)

    
client.run(DISCORD_TOKEN)