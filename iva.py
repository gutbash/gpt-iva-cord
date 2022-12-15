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

#handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')

## copy and paste by clipboard
## auto latex 2 trans png https://help.openai.com/en/articles/6681258-doing-math-in-the-playground
## buttons disappear after clicked
## BANANA.DEV INTEGRATION
## speech 2 speech integration
## calculate tokens https://help.openai.com/en/articles/4936856-what-are-tokens-and-how-to-count-them
## editing messages for continue and regenerate #

# create a connection to the database
conn = sqlite3.connect("data.db")
# create a cursor object
cursor = conn.cursor()

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
    
    for guild in client.guilds:
        
        if guild.id not in active_users:
            
            active_users[guild.id] = []
            active_names[guild.id] = ""
            chat_context[guild.id] = ""
            chat_messages[guild.id] = []
            
            ask_messages[guild.id] = []
            ask_context[guild.id] = ""
            last_prompt[guild.id] = ""
            replies[guild.id] = []
            last_response[guild.id] = None
        
        await tree.sync(guild=discord.Object(id=guild.id))

    print(f'we have logged in as {client.user}\n')

@client.event
async def on_message(message):

    if message.author == client.user:
        return

    global chat_messages
    global chat_context
    global ask_messages
    global ask_context
    global message_limit
    global active_users
    global active_names
    
    guild_id = message.guild.id
    bot = client.user.display_name
    user_name = message.author.name
    id = message.author.id
    user_mention = message.author.mention
    command = client.user.mention
    prompt = message.content[len(command)+1:]
    prompt_gpt = message.content[4:]
    ask_gpt = message.content

    if message.content.startswith(command):
        
        # Use the `SELECT` statement to fetch the row with the given id
        cursor.execute("SELECT key FROM keys WHERE id = ?", (id,))
        result = cursor.fetchone()
        
        if result != None:
            openai.api_key=result[0]
        else:
            embed = discord.Embed(description=f'<:ivanotify:1051918381844025434> {user_mention} Use `/setup` to register API key first or `/help` for more info. You can find your API key at https://beta.openai.com.', color=discord.Color.dark_theme())
            await message.channel.send(embed=embed)
            return
        
        if user_name not in active_users[guild_id]:
            active_users[guild_id].append(user_mention)
        
        if len(active_users[guild_id]) >= 2:
            
            for name_index in range(len(active_users[guild_id])-1):
                active_names += f", {active_users[guild_id][name_index]}"
            
            active_users[guild_id] += f", and {active_users[guild_id][-1]}"
                
        else:
            active_names = f" and {active_users[guild_id][0]}"
        
        max_tokens = 375
        max_chars = max_tokens * 4
        total_char_limit = 16384
        max_char_limit = total_char_limit - max_chars
        
        try:
            reply = openai.Completion.create(
                engine="text-davinci-003",
                prompt= f"You are {command}. Casually chat with {active_names} on Discord.\n\n(Write names in the format, <@name>. Format your response with aesthetically pleasing and consistent style using '**bold_text**', '*italicized_text*', '> block_quote_after_space', or 'emoji'.):\n\n{chat_context[guild_id]}{user_mention}: {prompt}\n{command}:",
                temperature=1.0,
                max_tokens=max_tokens,
                top_p=1.0,
                frequency_penalty=2.0,
                presence_penalty=2.0,
                stop=[f"{user_mention}:", f"{command}:"],
                echo=False,
                #logit_bias={43669:5, 8310:5, 47288:5, 1134:5, 35906:5, 388:5, 37659:5, 36599:5,},
            )
        except Exception as e:
            embed = discord.Embed(description=f'<:ivaverify:1051918344464380125> {user_mention} Your API key is not valid. Try `/setup` again or `/help` for more info. You can find your API key at https://beta.openai.com.', color=discord.Color.dark_theme())
            response = await message.channel.send(embed=embed)
            response_id = response.id
            return

        reply = reply['choices'][0].text
        
        interaction = f"{user_mention}: {prompt}\n{command}: {reply}\n"
        chat_messages[guild_id].append(interaction)
        chat_context[guild_id] = "".join(chat_messages[guild_id])
        
        if len(chat_context[guild_id]) > max_char_limit:
            chat_messages[guild_id].pop(0)
        """
        cursor.execute('''
            UPDATE guilds
            SET chat_context=%s, ask_context=%s, chat_messages=%s, ask_messages=%s, active_users=%s, active_names=%s, last_prompt=%s, replies=%s
            WHERE guild_id=%s
        ''', (chat_context, ask_context, chat_messages, ask_messages, active_users, active_names, last_prompt, replies, guild_id))
        conn.commit()
        """
        #print(f"{user_name}: {prompt}\n")
        #print(f"{bot}: {reply}\n")
        
        if len(reply) > 2000:
            embed = discord.Embed(description=f'<:ivaerror:1051918443840020531> **{user_mention} 2000 character prompt limit reached. Use `/reset`.**', color=discord.Color.dark_theme())
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
    
    @discord.ui.button(label="Continue", emoji="<:ivacontinue:1051710718489137254>", style=discord.ButtonStyle.grey)
    async def continues(self, interaction, button: discord.ui.Button):
        
        await interaction.response.defer()
        
        id = interaction.user.id
        mention = interaction.user.mention
        # Use the `SELECT` statement to fetch the row with the given id
        cursor.execute("SELECT key FROM keys WHERE id = ?", (id,))
        result = cursor.fetchone()
        
        if result != None:
            openai.api_key=result[0]
        else:
            embed = discord.Embed(description=f'<:ivanotify:1051918381844025434> {mention} Use `/setup` to register API key first or `/help` for more info. You can find your API key at https://beta.openai.com.', color=discord.Color.dark_theme())
            await interaction.response.send_message(embed=embed, ephemeral=True)
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
        
        if ask_messages == [] and ask_context == "" and replies == []:
            embed = discord.Embed(description=f'<:ivaerror:1051918443840020531> **Cannot continue because the conversation was reset.**', color=discord.Color.dark_theme())
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        max_tokens = 1250
        max_chars = max_tokens * 4
        total_char_limit = 16384
        max_char_limit = total_char_limit - max_chars
        
        try:
        
            reply = openai.Completion.create(
                engine="text-davinci-003",
                prompt=f"(Format your response with an aesthetically pleasing and consistent style using '**bold_text**', '*italicized_text*', '> block_quote_after_space', or 'emoji'. For code, always use '`code_block`', or '```[css,yaml,fix,diff,latex,bash,cpp,cs,ini,json,md,py,xml,java,js]\\nmulti_line_code_block```'.):\n\n{ask_context}continue:\n\n",
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
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        reply = (reply['choices'][0].text).strip("\n")
        
        ask_messages.append(reply)
        ask_context = "\n".join(ask_messages)

        replies.append(reply)
        replies_string = "\n\n".join(replies)
        
        prompt_embed = discord.Embed(description=f"<:ivacontinue2:1051714854165159958> {last_prompt}")
        embed = discord.Embed(description=replies_string, color=discord.Color.dark_theme())
        
        #button.disabled = True
        #message_id = interaction.message.id
        
        if len(chat_context) > max_char_limit:
            chat_messages.pop(0)
        if len(reply) > 4096:
            embed = discord.Embed(description=f'<:ivaerror:1051918443840020531> **{mention} 4096 character response limit reached. Use `/reset`.**', color=discord.Color.dark_theme())
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            await interaction.message.edit(embeds=[prompt_embed, embed])
    
    @discord.ui.button(label="Regenerate", emoji="<:ivaregenerate:1051697145713000580>", style=discord.ButtonStyle.grey)
    async def regenerates(self, interaction, button: discord.ui.Button):
        
        await interaction.response.defer()
        
        id = interaction.user.id
        mention = interaction.user.mention
        # Use the `SELECT` statement to fetch the row with the given id
        cursor.execute("SELECT key FROM keys WHERE id = ?", (id,))
        result = cursor.fetchone()
        
        if result != None:
            openai.api_key=result[0]
        else:
            embed = discord.Embed(description=f'<:ivanotify:1051918381844025434> {mention} Use `/setup` to register API key first or `/help` for more info. You can find your API key at https://beta.openai.com.', color=discord.Color.dark_theme())
            await interaction.response.send_message(embed=embed, ephemeral=True)
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
        
        if ask_messages == [] and ask_context == "" and replies == []:
            button.disabled = True
            await interaction.response.edit_message(view=self)
            embed = discord.Embed(description=f'<:ivaerror:1051918443840020531> **Cannot regenerate because the conversation was reset.**', color=discord.Color.dark_theme())
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        max_tokens = 1250
        max_chars = max_tokens * 4
        total_char_limit = 16384
        max_char_limit = total_char_limit - max_chars
        
        ask_messages.pop()
        ask_context = "\n".join(ask_messages)
        
        replies.pop()
        
        try:
        
            reply = openai.Completion.create(
                engine="text-davinci-003",
                prompt=f"(Format your response with an aesthetically pleasing and consistent style using '**bold_text**', '*italicized_text*', '> block_quote_after_space', or 'emoji'. For code, always use '`code_block`', or '```[css,yaml,fix,diff,latex,bash,cpp,cs,ini,json,md,py,xml,java,js]\\nmulti_line_code_block```'.):\n\n{ask_context}{last_prompt}\n\n",
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
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        reply = (reply['choices'][0].text).strip("\n")
        
        engagement = f"{last_prompt}\n{reply}"
        ask_messages.append(engagement)
        ask_context = "\n".join(ask_messages)
        
        replies.append(reply)
        replies_string = "\n\n".join(replies)
        
        prompt_embed = discord.Embed(description=f"<:ivaregenerate:1051697145713000580> {last_prompt}")
        embed = discord.Embed(description=replies_string, color=discord.Color.dark_theme())
        
        #button.disabled = True
        #await interaction.response.edit_message(view=self)
        
        if len(chat_context) > max_char_limit:
            chat_messages.pop(0)
        if len(reply) > 4096:
            embed = discord.Embed(description=f'<:ivaerror:1051918443840020531> **{mention} 4096 character response limit reached. Use `/reset`.**', color=discord.Color.dark_theme())
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            await interaction.message.edit(embeds=[prompt_embed, embed])
    
    @discord.ui.button(label="Reset", emoji="<:ivaresetdot:1051716771423473726>", style=discord.ButtonStyle.grey)
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

        ask_context = ""
        ask_messages = []
        replies = []
        last_response = None
        
        embed = discord.Embed(description="<:ivaresetdot:1051716771423473726>", color=discord.Color.dark_theme())
        button.disabled = True
        embeds = interaction.message.embeds
        embeds.append(embed)
        await interaction.message.edit(view=None, embeds=embeds)
        #await interaction.channel.send(embed=embed)

@tree.command(name = "iva", description="write a prompt", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(prompt = "prompt")
async def iva(interaction: discord.Interaction, prompt: str):
    
    print(interaction.guild_id)
    id = interaction.user.id
    mention = interaction.user.mention
    # Use the `SELECT` statement to fetch the row with the given id
    cursor.execute("SELECT key FROM keys WHERE id = ?", (id,))
    result = cursor.fetchone()
    
    if result != None:
        openai.api_key=result[0]
    else:
        embed = discord.Embed(description=f'<:ivanotify:1051918381844025434> {mention} Use `/setup` to register API key first or `/help` for more info. You can find your API key at https://beta.openai.com.', color=discord.Color.dark_theme())
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    await interaction.response.defer()

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
    global last_response

    if last_response:
        await last_response.edit_original_response(view=None)
    
    last_prompt = prompt
    max_tokens = 1250
    max_chars = max_tokens * 4
    total_char_limit = 16384
    max_char_limit = total_char_limit - max_chars
    
    try:
    
        reply = openai.Completion.create(
            engine="text-davinci-003",
            #prompt=f"(Format your response with an aesthetically pleasing and consistent style using '**bold_text**', '*italicized_text*', '> block_quote_after_space', or 'emoji'. For code, always use '`code_block`', or '```[css,yaml,fix,diff,latex,bash,cpp,cs,ini,json,md,py,xml,java,js]\\nmulti_line_code_block```'.):\n\n{ask_context}{prompt}\n\n",
            prompt=f"(Format response with an aesthetically pleasing and consistent style using '**bold_text**', '*italicized_text*', '> block_quote_after_space', or 'emoji'. For code, always use '`code_block`', or '```[css,yaml,fix,diff,latex,bash,cpp,cs,ini,json,md,py,xml,java,js]\\nmulti_line_code_block```'.):\n\n{ask_context}{prompt}\n\n",
            #prompt=prompt_gpt,
            temperature=0.0,
            max_tokens=max_tokens,
            top_p=1.0,
            frequency_penalty=0.0,
            presence_penalty=0.0,
            echo=False,
            #logit_bias={"50256": -100},
        )
        
    except Exception as e:
        embed = discord.Embed(description=f'<:ivaverify:1051918344464380125> {mention} Your API key is not valid. Try `/setup` again or `/help` for more info. You can find your API key at https://beta.openai.com.')
        await interaction.followup.send(embed=embed, ephemeral=True, color=discord.Color.dark_theme())
        return
    
    last_response = interaction
    
    reply = (reply['choices'][0].text).strip("\n")
    
    engagement = f"{prompt}\n{reply}"
    ask_messages.append(engagement)
    ask_context = "\n".join(ask_messages)

    replies.append(reply)

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
    
    if len(chat_context) > max_char_limit:
        chat_messages.pop(0)
    if len(reply) > 4096:
        embed = discord.Embed(description=f'<:ivaerror:1051918443840020531> **{mention} 4096 character response limit reached. Use `/reset`.**', color=discord.Color.dark_theme())
        await interaction.followup.send(embed=embed, ephemeral=True)
    else:
        await interaction.followup.send(embeds=[prompt_embed, embed], view=view)

@tree.command(name = "reset", description="start a new conversation", guild=discord.Object(id=GUILD_ID))
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
    
    ask_context = ""
    ask_messages = []
    replies = []
    last_response = None
    
    embed = discord.Embed(description="<:ivaresetdot:1051716771423473726>", color=discord.Color.dark_theme())
    await interaction.response.send_message(embed=embed, ephemeral=False)

    
@tree.command(name = "help", description="how to talk with iva", guild=discord.Object(id=GUILD_ID))
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
    
    ask_context = ""
    ask_messages = []
    replies = []
    
    mention = interaction.user.mention

    embed = discord.Embed(description=f"<:ivanotify:1051918381844025434>\n\nWelcome. Let's **Get Started**.\n\n**1 ** Iva uses **[OpenAI](https://beta.openai.com)** to generate responses. Create an account with them to start.\n**2 ** Visit your **[API Keys](https://beta.openai.com/account/api-keys)** page to create the API key you'll use in your requests.\n**3 ** Hit **`+ Create new secret key`**, then copy and paste that key (`sk-...`) when you run `/setup` with {client.user.mention}\n\nDone  <:ivathumbsup:1051918474299056189>", color=discord.Color.dark_theme())
    await interaction.response.send_message(embed=embed, ephemeral=False)
    
@tree.command(name = "setup", description="register your key", guild=discord.Object(id=GUILD_ID))
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
            await interaction.response.send_message(embed=embed, ephemeral=True, delete_after=30)
            
            conn.commit()

            # Print the values of the columns
            print(f'id: {id}, key: {key}')
        
        elif key == result[1]:
            
            embed = discord.Embed(description=f"<:ivaerror:1051918443840020531> **Key already registered for {mention}.**", color=discord.Color.dark_theme())
            await interaction.response.send_message(embed=embed, ephemeral=True, delete_after=30)
            
            # Print the values of the columns
            print(f'id: {id}, key: {key}')
        
    else:
        
        # insert a new API key into the table
        cursor.execute("INSERT INTO keys (id, key) VALUES (?, ?)", (id, key))
        
        conn.commit()

        embed = discord.Embed(description=f"<:ivathumbsup:1051918474299056189> **Key registered for {mention}.**", color=discord.Color.dark_theme())
        await interaction.response.send_message(embed=embed, ephemeral=True, delete_after=30)
    
client.run(DISCORD_TOKEN)