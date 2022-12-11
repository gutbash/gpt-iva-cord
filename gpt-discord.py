import discord
import os
from dotenv import load_dotenv
import openai

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
OAI_API_KEY = os.getenv("YOUR_API_KEY") #OPENAI
openai.api_key=OAI_API_KEY #OPEN AI INIT

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)

chat_messages = []
ask_messages = []
chat_context = ""
ask_context = ""
message_limit = 0
active_users = []
active_names = ""

@client.event
async def on_ready():
    print(f'We have logged in as {client.user}\n')

@client.event
async def on_message(message):

    global chat_messages
    global chat_context
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
    prompt = (message.content[len(command)+1:])
    prompt_gpt = (message.content[4:])
    
    if user_name not in active_users:
        active_users.append(user_mention)
    
    if len(active_users) >= 2:
        
        for name_index in range(len(active_users)-1):
            active_names += f", {active_users[name_index]}"
        
        active_users += f", and {active_users[-1]}"
            
    else:
        active_names = f" and {active_users[0]}"
        

    if message.content.startswith(command):
        
        reply = openai.Completion.create(
            engine="text-davinci-003",
            prompt= f"This is a casual chat between {command}{active_names} on Discord. You are {command}. Make sure names are written <@name>. Format and organize your response aesthetically and consistently with :emoji:, **bold**, *italic*, and > blockquote (start new line, include space):\n\n{chat_context}{user_mention}: {prompt}\n{command}:",
            temperature=0.7,
            max_tokens=375,
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
        
        if len(chat_context) > 16000:
            chat_messages.pop()
        
        print(f"{user_name}: {prompt}\n")
        print(f"{bot}: {reply}\n")
        
        if len(reply) > 2000:
            await message.channel.send('iva#6125 error: 2000 char limit reached')
        else:
            await message.channel.send(f"{reply}")
    
    if message.content.startswith("iva?clear"):
        chat_context = ""
        chat_messages = []
        await message.channel.send('**memory cleared...**')
    
    elif message.content.startswith("iva?"):
        
        response = await message.channel.send('**loading...**')
        max_tokens = 1250
        
        reply = openai.Completion.create(
            engine="text-davinci-003",
            prompt=f"{ask_context}{prompt_gpt} (Format only code with `code` and ```fenced code block```. Format and organize your response aesthetically and consistently with :emoji:, **bold**, *italic*, and > blockquote (start new line, include space)):",
            #prompt=prompt_gpt,
            temperature=0.7,
            max_tokens=1250,
            top_p=1.0,
            frequency_penalty=0.0,
            presence_penalty=0.0,
            echo=False,
            #logit_bias={"50256": -100},
        )
        
        reply = reply['choices'][0].text
        print(reply)
        interaction = f"{prompt}\n{reply}\n\n"
        ask_messages.append(interaction)
        ask_context = "".join(ask_messages)
        embed = discord.Embed(description=reply)
        
        if len(chat_context) > 16000:
            chat_messages.pop()
        
        if len(reply) > 4096:
            await response.edit(content='iva#6125 error: 4096 char limit reached')
        else:
            await response.edit(content=None, embed=embed)
        
client.run(DISCORD_TOKEN)