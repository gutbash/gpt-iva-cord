import discord
from discord import app_commands
import discord.ext.commands
import discord.ext.tasks
from discord.ext import commands
import os
from dotenv import load_dotenv
import openai
#import sympy
#import datetime
#import clipboard
import sqlite3
import banana_dev as banana
import datetime
from transformers import GPT2TokenizerFast

#handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')

## create /tutorial slash command #
## copy and paste by clipboard button (text or .txt file returned)
## undo button
## continue should only continue from current embed requested from message

## auto latex 2 trans png https://help.openai.com/en/articles/6681258-doing-math-in-the-playground
## buttons disappear after clicked #
## BANANA.DEV INTEGRATION
## speech 2 speech integration
## calculate tokens https://help.openai.com/en/articles/4936856-what-are-tokens-and-how-to-count-them
## editing messages for continue and regenerate #

# create a connection to the database
conn = sqlite3.connect("data.db")
# create a cursor object
cursor = conn.cursor()
# initialize tokenizer
tokenizer = GPT2TokenizerFast.from_pretrained("gpt2")
# check if the keys table exists
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()

if ("keys",) not in tables:
    # the table does not exist, so create it
    cursor.execute("CREATE TABLE keys (id TEXT PRIMARY KEY, key TEXT)")
    conn.commit()
if ("guilds",) not in tables:
    # the table does not exist, so create it
    cursor.execute('''CREATE TABLE guilds (guild_id TEXT PRIMARY KEY, chat_context TEXT, ask_context TEXT, chat_messages DICTIONARY, ask_messages DICTIONARY, active_users DICTIONARY, active_names TEXT, last_prompt TEXT, replies DICTIONARY)''')
    conn.commit()

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = os.getenv("GUILD_ID")
OAI_API_KEY = os.getenv("YOUR_API_KEY") #OPENAI
openai.api_key=OAI_API_KEY #OPEN AI INIT
CARROT_API = os.getenv("CARROT_API_KEY")
CARROT_MODEL = os.getenv("CARROT_MODEL_KEY")

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

active_users = {} # dict of lists
active_names = {} # dict of strings
chat_context = {} # dict of strings
chat_messages = {} # dict of lists

ask_messages = {} # dict of lists
ask_context = {} # dict of strings
last_prompt = {} # dict of strings
replies = {} # dict of lists
last_response = {} # dict of Message objs

@client.event
async def on_ready():
    print()
    for guild in client.guilds:
        
        print(guild)
            
        active_users[guild.id] = []
        active_names[guild.id] = ""
        chat_context[guild.id] = ""
        chat_messages[guild.id] = []
        
    await tree.sync()
    print(f'\nwe have logged in as {client.user}\n')
    
@client.event
async def on_guild_join(guild):
    
    print(guild)
        
    active_users[guild.id] = []
    active_names[guild.id] = ""
    chat_context[guild.id] = ""
    chat_messages[guild.id] = []
    
    await tree.sync(guild=guild)
    

@client.event
async def on_message(message):

    if message.author == client.user:
        return
    
    command = client.user.mention

    if message.content.startswith(command):
        
        global chat_messages
        global chat_context
        global ask_messages
        global ask_context
        global message_limit
        global active_users
        global active_names
        
        # Get the current timestamp
        timestamp = datetime.datetime.now()
        time = timestamp.strftime(r"%Y-%m-%d %I:%M %p")
        
        guild_id = message.guild.id
        bot = client.user.display_name
        user_name = message.author.name
        id = message.author.id
        user_mention = message.author.mention
        prompt = message.content[len(command)+1:]
        prompt_gpt = message.content[4:]
        ask_gpt = message.content
        images = message.attachments
        caption = ""
        
        async with message.channel.typing():
        
            # Use the `SELECT` statement to fetch the row with the given id
            cursor.execute("SELECT key FROM keys WHERE id = ?", (id,))
            result = cursor.fetchone()
            
            if result != None:
                openai.api_key=result[0]
            else:
                embed = discord.Embed(description=f'<:ivanotify:1051918381844025434> {user_mention} Use `/setup` to register API key first or `/help` for more info. You can find your API key at https://beta.openai.com.', color=discord.Color.dark_theme())
                await message.channel.send(embed=embed)
                return
            
            if user_mention not in active_users[guild_id]:
                active_users[guild_id].append(user_mention)
            
            if len(active_users[guild_id]) >= 2:
                
                for name_index in range(len(active_users[guild_id])-1):
                    active_names[guild_id] += f", {active_users[guild_id][name_index]}"
                
                active_users[guild_id] += f", and {active_users[guild_id][-1]}"
                    
            else:
                active_names[guild_id] = f"{active_users[guild_id][0]}"

            if images != []:
                
                model_parameters = {
                        "text":prompt, #text for QA / Similarity
                        "imageURL":images[0].url, #image for the model
                        "similarity":False, #whether to return text-image similarity
                        "maxLength":100, #max length of the generation
                        "minLength":50 #min length of the generation
                        }

                #To generate captions, only send the image in model_parameters

                out = banana.run(CARROT_API, CARROT_MODEL, model_parameters)
                print(out)
                caption = f" (IMAGE CAPTION: {out['modelOutputs'][0]['answer']})"
            
            max_tokens = 375
                
            chat_prompt = f"You are {command}, a charismatic and intelligent chatter. You have vast amount of knowledge, so you always have an answer in a conversation. You don't lie, so sometimes you can be brutally honest. Casually chat with {active_names.get(guild_id, '')} on Discord.\n\n(Write usernames in the format, <@username>. Format your response with aesthetically pleasing and consistent style using '**bold_text**', '*italicized_text*', '> block_quote_AFTER_SPACE', or ':unicode_cldr_emoji_shortcode:'.):\n\n{chat_context.get(guild_id, '')}\n[{time}] {user_mention}: {prompt}\n{command}{caption}:"
            
            tokens = len(tokenizer(chat_prompt)['input_ids'])
            print(f"PRE-COMPLETION TOKENS: {tokens}")
            
            while tokens > 4096 - max_tokens:
                if chat_messages.get(guild_id, []) != []:
                    chat_messages[guild_id].pop(0)
                    chat_context[guild_id] = "".join(chat_messages[guild_id])
                    chat_prompt = f"You are {command}, a charismatic and intelligent chatter. You have vast amount of knowledge, so you always have an answer in a conversation. You don't lie, so sometimes you can be brutally honest. Casually chat with {active_names[guild_id]} on Discord.\n\n(Write usernames in the format, <@username>. Format your response with aesthetically pleasing and consistent style using '**bold_text**', '*italicized_text*', '> block_quote_AFTER_SPACE', or ':unicode_cldr_emoji_shortcode:'.):\n\n{chat_context[guild_id]}\n{user_mention}: {prompt}\n{command}{caption}:"
                tokens = len(tokenizer(chat_context[guild_id])['input_ids'])
                print(f"PRE-TRIMMED TOKENS: {tokens}")
            
            try:
                reply = openai.Completion.create(
                    engine="text-davinci-003",
                    prompt= chat_prompt,
                    temperature=1.0,
                    max_tokens=max_tokens,
                    top_p=1.0,
                    frequency_penalty=2.0,
                    presence_penalty=1.0,
                    stop=[f"{user_mention}:", f"{command}:"],
                    echo=False,
                    #logit_bias={43669:5, 8310:5, 47288:5, 1134:5, 35906:5, 388:5, 37659:5, 36599:5,},
                )

            except Exception as e:
                print(e)
                embed = discord.Embed(description=f'<:ivaverify:1051918344464380125> {user_mention} Your API key is not valid. Try `/setup` again or `/help` for more info. You can find your API key at https://beta.openai.com.', color=discord.Color.dark_theme())
                response = await message.channel.send(embed=embed)
                response_id = response.id
                return
            
            reply = reply['choices'][0].text
            
            interaction = f"[{time}] {user_mention}: {prompt}\n{command}: {reply}\n"
            chat_messages[guild_id].append(interaction)
            chat_context[guild_id] = "".join(chat_messages[guild_id])
            
            chat_prompt = f"You are {command}, a charismatic and intelligent chatter. You have vast amount of knowledge, so you always have an answer in a conversation. You don't lie, so sometimes you can be brutally honest. Casually chat with {active_names[guild_id]} on Discord.\n\n(Write usernames in the format, <@username>. Format your response with aesthetically pleasing and consistent style using '**bold_text**', '*italicized_text*', '> block_quote_AFTER_SPACE', or ':unicode_cldr_emoji_shortcode:'.):\n\n{chat_context[guild_id]}\n{user_mention}: {prompt}\n{command}{caption}:"
            
            tokens = len(tokenizer(chat_prompt)['input_ids'])
            print(f"POST-COMPLETION TOKENS: {tokens}")
            
            while tokens > 4096 - max_tokens:
                if chat_messages.get(guild_id, []) != []:
                    chat_messages[guild_id].pop(0)
                    chat_context[guild_id] = "".join(chat_messages[guild_id])
                    chat_prompt = f"You are {command}, a charismatic and intelligent chatter. You have vast amount of knowledge, so you always have an answer in a conversation. You don't lie, so sometimes you can be brutally honest. Casually chat with {active_names[guild_id]} on Discord.\n\n(Write usernames in the format, <@username>. Format your response with aesthetically pleasing and consistent style using '**bold_text**', '*italicized_text*', '> block_quote_AFTER_SPACE', or ':unicode_cldr_emoji_shortcode:'.):\n\n{chat_context[guild_id]}\n{user_mention}: {prompt}\n{command}{caption}:"
                tokens = len(tokenizer(chat_context[guild_id])['input_ids'])
                print(f"POST-TRIMMED TOKENS: {tokens}")
                
            print(f"[CHAT {time}] {user_name}: {prompt}")
            print(f"[CHAT {time}] {bot}: {reply}\n")
                
        if len(reply) > 2000:
            embed = discord.Embed(description=f'<:ivaerror:1051918443840020531> **{user_mention} 2000 character prompt limit reached.', color=discord.Color.dark_theme())
            await message.channel.send(embed=embed)
        else:
            await message.channel.send(f"{reply}")
        
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
        cursor.execute("SELECT key FROM keys WHERE id = ?", (id,))
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
        print(f"PRE-COMPLETION TOKENS: {tokens}")
        
        while tokens > 4096 - max_tokens:
            if ask_messages.get(id, []) != []:
                ask_messages[id].pop(0)
                ask_context[id] = "".join(ask_messages[id])
                ask_prompt = f"(Format your response with an aesthetically pleasing and consistent style using '**bold_text**', '*italicized_text*', '> block_quote_AFTER_SPACE', or ':unicode_cldr_emoji_shortcode:'. For code, always use '`code_block`', or '```[css,yaml,fix,diff,latex,bash,cpp,cs,ini,json,md,py,xml,java,js]\\nmulti_line_code_block```'.):\n\n{ask_context[id]}continue:\n\n"
            tokens = len(tokenizer(ask_context[id])['input_ids'])
            print(f"PRE-TRIMMED TOKENS: {tokens}")
        
        try:
            reply = openai.Completion.create(
                engine="text-davinci-003",
                prompt=ask_prompt,
                #prompt=prompt_gpt,
                temperature=0.7,
                max_tokens=max_tokens,
                top_p=1.0,
                frequency_penalty=0.0,
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
        print(f"POST-COMPLETION TOKENS: {tokens}")
        
        while tokens > 4096 - max_tokens:
            if ask_messages.get(id, []) != []:
                ask_messages[id].pop(0)
                ask_context[id] = "".join(ask_messages[id])
                ask_prompt = f"(Format your response with an aesthetically pleasing and consistent style using '**bold_text**', '*italicized_text*', '> block_quote_AFTER_SPACE', or ':unicode_cldr_emoji_shortcode:'. For code, always use '`code_block`', or '```[css,yaml,fix,diff,latex,bash,cpp,cs,ini,json,md,py,xml,java,js]\\nmulti_line_code_block```'.):\n\n{ask_context[id]}continue:\n\n"
            tokens = len(tokenizer(ask_context[id])['input_ids'])
            print(f"POST-TRIMMED TOKENS: {tokens}")
        
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
        cursor.execute("SELECT key FROM keys WHERE id = ?", (id,))
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
                frequency_penalty=0.0,
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
    """
    @discord.ui.button(label="Undo", emoji="<:ivaundo:1053048583538094220>", style=discord.ButtonStyle.grey)
    async def undo(self, interaction, button: discord.ui.Button):
        
        await interaction.response.defer()
        
        guild_id = interaction.guild_id
        id = interaction.user.id
        mention = interaction.user.mention
        # Use the `SELECT` statement to fetch the row with the given id
        cursor.execute("SELECT key FROM keys WHERE id = ?", (id,))
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
        
        chat_context = ""
        chat_messages = []
        
        embed = discord.Embed(description="<:ivareset:1051691297443950612>", color=discord.Color.dark_theme())
        button.disabled = True
        embeds = interaction.message.embeds
        embeds.append(embed)
        await interaction.message.edit(view=None, embeds=embeds)
        #await interaction.channel.send(embed=embed)

@tree.command(name = "iva", description="write a prompt")
@app_commands.describe(prompt = "prompt")
async def iva(interaction: discord.Interaction, prompt: str):
    
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
    id = interaction.user.id
    mention = interaction.user.mention
    bot = client.user.display_name
    user_name = interaction.user.name
    # Use the `SELECT` statement to fetch the row with the given id
    cursor.execute("SELECT key FROM keys WHERE id = ?", (id,))
    result = cursor.fetchone()
    
    if result != None:
        openai.api_key=result[0]
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
    
    # Get the current timestamp
    timestamp = datetime.datetime.now()
    time = timestamp.strftime(r"%Y-%m-%d %I:%M %p")

    if last_response[id]:
        await last_response[id].edit_original_response(view=None)
    
    last_prompt[id] = prompt
    max_tokens = 1250

    ask_prompt = f"Answer all questions with creativity, detail, and truth (Format response with an aesthetically pleasing and consistent style using '**bold_text**', '*italicized_text*', '> block_quote_AFTER_SPACE', or ':emoji_shortcode:'. ONLY USE '`code_block`', or '```[css,yaml,fix,diff,latex,bash,cpp,cs,ini,json,md,py,xml,java,js]\\nmulti_line_code_block```' FOR CODING.):\n\n{ask_context[id]}{prompt}\n\n"
    
    tokens = len(tokenizer(ask_prompt)['input_ids'])
    print(f"PRE-COMPLETION TOKENS: {tokens}")
    
    while tokens > 4096 - max_tokens:
        if ask_messages.get(id, []) != []:
            ask_messages[id].pop(0)
            ask_context[id] = "".join(ask_messages[id])
            ask_prompt = f"Answer all questions with creativity, detail, and truth (Format response with an aesthetically pleasing and consistent style using '**bold_text**', '*italicized_text*', '> block_quote_AFTER_SPACE', or ':emoji_shortcode:'. ONLY USE '`code_block`', or '```[css,yaml,fix,diff,latex,bash,cpp,cs,ini,json,md,py,xml,java,js]\\nmulti_line_code_block```' FOR CODING.):\n\n{ask_context[id]}{prompt}\n\n"
        tokens = len(tokenizer(ask_context[id])['input_ids'])
        print(f"PRE-TRIMMED TOKENS: {tokens}")
    
    try:
    
        reply = openai.Completion.create(
            engine="text-davinci-003",
            #prompt=f"(Format your response with an aesthetically pleasing and consistent style using '**bold_text**', '*italicized_text*', '> block_quote_after_space', or 'emoji'. For code, always use '`code_block`', or '```[css,yaml,fix,diff,latex,bash,cpp,cs,ini,json,md,py,xml,java,js]\\nmulti_line_code_block```'.):\n\n{ask_context}{prompt}\n\n",
            prompt=ask_prompt,
            #prompt=prompt_gpt,
            temperature=0.7,
            max_tokens=max_tokens,
            top_p=1.0,
            frequency_penalty=0.0,
            presence_penalty=0.0,
            echo=False,
            #logit_bias={"50256": -100},
        )
        
    except Exception as e:
        embed = discord.Embed(description=f'<:ivaverify:1051918344464380125> {mention} Your API key is not valid. Try `/setup` again or `/help` for more info. You can find your API key at https://beta.openai.com.')
        await interaction.followup.send(embed=embed, ephemeral=False, color=discord.Color.dark_theme())
        return
    
    last_response[id] = interaction
    
    reply = (reply['choices'][0].text).strip("\n")
    
    engagement = f"{prompt}\n{reply}"
    ask_messages[id].append(engagement)
    ask_context[id] = "\n".join(ask_messages[id])

    replies[id].append(reply)
    
    ask_prompt = f"Answer all questions with creativity, detail, and truth (Format response with an aesthetically pleasing and consistent style using '**bold_text**', '*italicized_text*', '> block_quote_AFTER_SPACE', or ':emoji_shortcode:'. ONLY USE '`code_block`', or '```[css,yaml,fix,diff,latex,bash,cpp,cs,ini,json,md,py,xml,java,js]\\nmulti_line_code_block```' FOR CODING.):\n\n{ask_context[id]}{prompt}\n\n"
    
    tokens = len(tokenizer(ask_prompt)['input_ids'])
    print(f"POST-COMPLETION TOKENS: {tokens}")
    
    while tokens > 4096 - max_tokens:
        if ask_messages.get(id, []) != []:
            ask_messages[id].pop(0)
            ask_context[id] = "".join(ask_messages[id])
            ask_prompt = f"Answer all questions with creativity, detail, and truth (Format response with an aesthetically pleasing and consistent style using '**bold_text**', '*italicized_text*', '> block_quote_AFTER_SPACE', or ':emoji_shortcode:'. ONLY USE '`code_block`', or '```[css,yaml,fix,diff,latex,bash,cpp,cs,ini,json,md,py,xml,java,js]\\nmulti_line_code_block```' FOR CODING.):\n\n{ask_context[id]}{prompt}\n\n"
        tokens = len(tokenizer(ask_context[id])['input_ids'])
        print(f"POST-TRIMMED TOKENS: {tokens}")
    
    print(f"[ASK {time}] {user_name}: {prompt}")
    print(f"[ASK {time}] {bot}: {reply}\n")

    """
    special_words = []

    while "$" in reply:
        start_index = reply.index("$")
        end_index = reply.index("$", start_index+1)
        special_word = reply[start_index:end_index+1]
        special_words.append(special_word)
        reply = reply[:start_index] + reply[end_index+1:]
        
    latex = "\n".join(special_words)
    
    sympy.preview(latex, filename="latex.png")
    
    file = discord.File("latex.png", filename="latex.png")
    
    embed = discord.Embed(description=reply)
    
    embed.set_image(url="attachment://latex.png")
    """
    
    prompt_embed = discord.Embed(description=f"<:ivaprompt:1051742892814761995>  {prompt}")
    embed = discord.Embed(description=reply, color=discord.Color.dark_theme())
    
    if len(reply) > 4096:
        embed = discord.Embed(description=f'<:ivaerror:1051918443840020531> **{mention} 4096 character response limit reached. Use `/reset`.**', color=discord.Color.dark_theme())
        await interaction.followup.send(embed=embed, ephemeral=False)
    else:
        await interaction.followup.send(embeds=[prompt_embed, embed], view=view)

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
    
    guild_id = interaction.guild_id
    id = interaction.user.id
    
    ask_context[id] = ""
    ask_messages[id] = []
    replies[id] = []
    last_response[id] = None
    
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
    embed.add_field(name="Step 1", value="Iva uses **[OpenAI](https://beta.openai.com)** to generate responses. Create an account with them to start.")
    embed.add_field(name="Step 2", value="Visit your **[API Keys](https://beta.openai.com/account/api-keys)** page and click **`+ Create new secret key`**.")
    embed.add_field(name="Step 3", value=f"Copy and paste that secret key (`sk-...`) when you run `/setup` with {client.user.mention}")
    
    await interaction.response.send_message(embed=embed, ephemeral=False)
    
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

    embed = discord.Embed(title="Commands", color=discord.Color.dark_theme())
    embed.set_thumbnail(url=client.user.avatar.url)
    embed.add_field(name="`@iva`", value="provides **chat** and **conversation** oriented answers. has personality, asks questions back, is more creative.")
    embed.add_field(name="`/iva`", value="provides **academic** and **work** oriented answers. has less personality, is more focused on consistency and reliability.")
    embed.add_field(name="`/reset`", value="resets the `/iva` conversation history. also available as button on messages.")
    embed.add_field(inline=False, name="`/help`", value="shows instructions for setup.")
    embed.add_field(inline=False, name="`/setup`", value="to enter your key. `/help` for more info.")
    
    embed1 = discord.Embed(title="Buttons", color=discord.Color.dark_theme())
    embed1.add_field(name="<:ivacontinue1:1051714712242491392> `Continue`", value="say more, extend the last prompt's response")
    embed1.add_field(name="<:ivaregenerate:1051697145713000580> `Regenerate`", value="replace the last prompt's response with a different one")
    embed1.add_field(name="<:ivareset:1051691297443950612> `Reset`", value="reset the conversation history, clear iva's memory")
    await interaction.response.send_message(embeds=[embed, embed1], ephemeral=False)
    
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
    cursor.execute("SELECT * FROM keys WHERE id = ?", (id,))
    
    result = cursor.fetchone()
    
    if result != None:
    
        # Access the values of the columns in the row
        if key != result[1]:
            
            # insert a new API key into the table
            cursor.execute("UPDATE keys SET key = ? WHERE id = ?", (key, id))
            
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
        cursor.execute("INSERT INTO keys (id, key) VALUES (?, ?)", (id, key))
        
        conn.commit()

        embed = discord.Embed(description=f"<:ivathumbsup:1051918474299056189> **Key registered for {mention}.**", color=discord.Color.dark_theme())
        await interaction.response.send_message(embed=embed, ephemeral=False, delete_after=30)
    
client.run(DISCORD_TOKEN)