import discord
from discord import app_commands
#from discord.ext import commands
import os
from dotenv import load_dotenv
import openai
#import sympy
#import datetime
#import clipboard


load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = os.getenv("GUILD_ID")
OAI_API_KEY = os.getenv("YOUR_API_KEY") #OPENAI
openai.api_key=OAI_API_KEY #OPEN AI INIT

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)


chat_messages = []
ask_messages = []
chat_context = ""
ask_context = ""
message_limit = 0
active_users = []
active_names = ""
last_prompt = ""
replies = []

@client.event
async def on_ready():
    await tree.sync(guild=discord.Object(id=GUILD_ID))
    print(f'we have logged in as {client.user}\n')

@client.event
async def on_message(message):

    global chat_messages
    global chat_context
    global ask_messages
    global ask_context
    global message_limit
    global active_users
    global active_names
    
    if message.author == client.user:
        return
    
    bot = client.user.display_name
    user_name = message.author.name
    user_mention = message.author.mention
    command = client.user.mention
    prompt = message.content[len(command)+1:]
    prompt_gpt = message.content[4:]
    ask_gpt = message.content
    
    if user_name not in active_users:
        active_users.append(user_mention)
    
    if len(active_users) >= 2:
        
        for name_index in range(len(active_users)-1):
            active_names += f", {active_users[name_index]}"
        
        active_users += f", and {active_users[-1]}"
            
    else:
        active_names = f" and {active_users[0]}"
        

    if message.content.startswith(command):
        
        max_tokens = 375
        max_chars = max_tokens * 4
        total_char_limit = 16384
        max_char_limit = total_char_limit - max_chars
        
        reply = openai.Completion.create(
            engine="text-davinci-003",
            prompt= f"This is a casual chat between {command}{active_names} on Discord. You are {command}.\n\n(Make sure names are written <@name>. Format your response with an aesthetically pleasing and consistent style using '**bold_text**', '*italicized_text*', '> block_quote', or ':emoji_name:'.):\n\n{chat_context}{user_mention}: {prompt}\n{command}:",
            temperature=0.7,
            max_tokens=max_tokens,
            top_p=1.0,
            frequency_penalty=2.0,
            presence_penalty=2.0,
            stop=[f"{user_mention}:", f"{command}:"],
            echo=False,
        )

        reply = reply['choices'][0].text
        
        interaction = f"{user_mention}: {prompt}\n{command}: {reply}\n"
        chat_messages.append(interaction)
        chat_context = "".join(chat_messages)
        
        if len(chat_context) > max_char_limit:
            chat_messages.pop(0)
        
        #print(f"{user_name}: {prompt}\n")
        #print(f"{bot}: {reply}\n")
        
        if len(reply) > 2000:
            await message.channel.send('iva#6125 error: 2000 char limit reached')
        else:
            await message.channel.send(f"{reply}")
        
class Menu(discord.ui.View):
    def __init__(self):
        super().__init__()
        self.value = None
    
    @discord.ui.button(label="Continue", emoji="<:ivacontinue:1051710718489137254>", style=discord.ButtonStyle.grey)
    async def continues(self, interaction, button: discord.ui.Button):
        
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
        
        max_tokens = 1250
        max_chars = max_tokens * 4
        total_char_limit = 16384
        max_char_limit = total_char_limit - max_chars
        
        reply = openai.Completion.create(
            engine="text-davinci-003",
            prompt=f"(Format your response with an aesthetically pleasing and consistent style using '**bold_text**', '*italicized_text*', '> block_quote', or ':emoji_name:'. Always use '`code_block`', or '```[css,yaml,fix,diff,latex,bash,cpp,cs,ini,json,md,py,xml,java,js]\\nmulti_line_code_block```' for code.):\n\n{ask_context}continue:\n\n",
            #prompt=prompt_gpt,
            temperature=0.7,
            max_tokens=max_tokens,
            top_p=1.0,
            frequency_penalty=0.0,
            presence_penalty=0.0,
            echo=False,
            #logit_bias={"50256": -100},
        )
        
        reply = reply['choices'][0].text
        print(reply)
        engagement = f"{reply}\n"
        reply = f"{reply}\n\n"
        replies.append(reply)
        ask_messages.append(engagement)
        ask_context = "".join(ask_messages)
        replies_string = "\n".join(replies)
        
        embed = discord.Embed(description=replies_string)
        
        if len(chat_context) > max_char_limit:
            chat_messages.pop(0)
        if len(reply) > 4096:
            await interaction.channel.send('iva#6125 error: 4096 char limit reached')
        else:
            await interaction.channel.send(content=f"<:ivacontinue2:1051714854165159958> {last_prompt}", embed=embed, view=view)
    
    @discord.ui.button(label="Regenerate", emoji="<:ivaregenerate:1051697145713000580>", style=discord.ButtonStyle.grey)
    async def regenerates(self, interaction, button: discord.ui.Button):
        
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
        
        max_tokens = 1250
        max_chars = max_tokens * 4
        total_char_limit = 16384
        max_char_limit = total_char_limit - max_chars
        
        ask_messages.pop()
        replies.pop()
        ask_context = "".join(ask_messages)
        
        reply = openai.Completion.create(
            engine="text-davinci-003",
            prompt=f"(Format your response with an aesthetically pleasing and consistent style using '**bold_text**', '*italicized_text*', '> block_quote', or ':emoji_name:'. Always use '`code_block`', or '```[css,yaml,fix,diff,latex,bash,cpp,cs,ini,json,md,py,xml,java,js]\\nmulti_line_code_block```' for code.):\n\n{ask_context}{last_prompt}\n\n",
            #prompt=prompt_gpt,
            temperature=0.7,
            max_tokens=max_tokens,
            top_p=1.0,
            frequency_penalty=0.0,
            presence_penalty=0.0,
            echo=False,
            #logit_bias={"50256": -100},
        )
        
        reply = reply['choices'][0].text
        print(reply)
        engagement = f"{last_prompt}\n\n{reply}\n"
        reply = f"{reply}\n"
        replies.append(reply)
        ask_messages.append(engagement)
        ask_context = "".join(ask_messages)
        
        embed = discord.Embed(description=reply)
        
        if len(chat_context) > max_char_limit:
            chat_messages.pop(0)
        if len(reply) > 4096:
            await interaction.followup.send('iva#6125 error: 4096 char limit reached')
        else:
            await interaction.followup.send(content=f"<:ivaregenerate:1051697145713000580> {last_prompt}", embed=embed, view=view)
    
    @discord.ui.button(label="Reset", emoji="<:ivaresetdot:1051716771423473726>", style=discord.ButtonStyle.grey)
    async def resets(self, interaction, button: discord.ui.Button):
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
        await interaction.response.send_message("<:reset:1051716903791513720>")

@tree.command(name = "iva", description="write a prompt", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(prompt = "prompt")
async def iva(interaction, prompt: str):
    
    await interaction.response.defer(ephemeral=False)
    
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
    
    last_prompt = prompt
    max_tokens = 1250
    max_chars = max_tokens * 4
    total_char_limit = 16384
    max_char_limit = total_char_limit - max_chars
    
    reply = openai.Completion.create(
        engine="text-davinci-003",
        prompt=f"(Format your response with an aesthetically pleasing and consistent style using '**bold_text**', '*italicized_text*', '> block_quote', or ':emoji_name:'. Always use '`code_block`', or '```[css,yaml,fix,diff,latex,bash,cpp,cs,ini,json,md,py,xml,java,js]\\nmulti_line_code_block```' for code.):\n\n{ask_context}{prompt}\n\n",
        #prompt=prompt_gpt,
        temperature=0.7,
        max_tokens=max_tokens,
        top_p=1.0,
        frequency_penalty=0.0,
        presence_penalty=0.0,
        echo=False,
        #logit_bias={"50256": -100},
    )
    
    reply = reply['choices'][0].text
    print(reply)
    engagement = f"{prompt}\n{reply}\n"
    reply = f"{reply}\n"
    replies.append(reply)
    ask_messages.append(engagement)
    ask_context = "".join(ask_messages)
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
    
    embed = discord.Embed(description=reply)
    
    if len(chat_context) > max_char_limit:
        chat_messages.pop(0)
    if len(reply) > 4096:
        await interaction.followup.send('iva#6125 error: 4096 char limit reached')
    else:
        await interaction.followup.send(content=f"<:ivaprompt:1051742892814761995>  {prompt}", embed=embed, view=view)

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
    
    ask_context = ""
    ask_messages = []
    replies = []
    await interaction.response.send_message("<:reset:1051716903791513720>")
    
client.run(DISCORD_TOKEN)