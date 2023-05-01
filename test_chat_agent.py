import discord
from discord import app_commands
import discord.ext.commands
import discord.ext.tasks

from utils.log_utils import colors
from utils.redis_utils import save_pickle_to_redis, load_pickle_from_redis
from utils.postgres_utils import fetch_key, fetch_keys_table, upsert_key, delete_key
from utils.tool_utils import dummy_sync_function
from tools import (
    get_image_from_search,
    get_organic_results,
    get_shopping_results,
    question_answer_webpage,
    summarize_webpage,
    get_full_blip,
)

import asyncio
import os
import openai
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
import logging

from langchain.chat_models import ChatOpenAI
from langchain.llms import OpenAI
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from langchain.callbacks import get_openai_callback
from langchain.chains.conversation.memory import ConversationSummaryBufferMemory
from langchain.memory import ConversationBufferWindowMemory
from langchain.agents import Tool, AgentExecutor, load_tools, ConversationalAgent, ConversationalChatAgent, initialize_agent, AgentType
from langchain.text_splitter import TokenTextSplitter
from langchain.schema import (
    AIMessage,
    HumanMessage,
    SystemMessage
)
from langchain.prompts.chat import (
    ChatPromptTemplate,
    SystemMessagePromptTemplate,
    AIMessagePromptTemplate,
    HumanMessagePromptTemplate,
)

from constants import (
    ORGANIC_RESULTS_ASK_TOOL_DESCRIPTION,
    QA_WEBPAGE_ASK_TOOL_DESCRIPTION,
    IMAGE_SEARCH_ASK_TOOL_DESCRIPTION,
    RECOGNIZE_IMAGE_ASK_TOOL_DESCRIPTION,
    SUMMARIZE_WEBPAGE_ASK_TOOL_DESCRIPTION,
    
    QA_WEBPAGE_CHAT_TOOL_DESCRIPTION,
    IMAGE_SEARCH_CHAT_TOOL_DESCRIPTION,
    ORGANIC_RESULTS_CHAT_TOOL_DESCRIPTION,
    RECOGNIZE_IMAGE_CHAT_TOOL_DESCRIPTION,
    SUMMARIZE_WEBPAGE_CHAT_TOOL_DESCRIPTION,
    
    get_ask_prefix,
    get_ask_custom_format_instructions,
    get_ask_suffix,
    
    get_chat_prefix,
    get_chat_custom_format_instructions,
    get_chat_suffix,
    
    get_human_message,
    
    get_thread_namer_prompt,
    
    FEATURES,
)

GOOGLE_API_KEY = os.getenv("GOOGLE_API_TOKEN")
GOOGLE_CSE_ID = os.getenv("GOOGLE_CSE_ID")
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN") # load discord app token
GUILD_ID = os.getenv("GUILD_ID") # load dev guild
SERPAPI_API_KEY = os.getenv("SERPAPI_API_KEY")
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
WOLFRAM_ALPHA_APPID = os.getenv("WOLFRAM_ALPHA_APPID")
DATABASE_URL = os.getenv("DATABASE_URL")

logical_llm = ChatOpenAI(
    openai_api_key="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",
    temperature=0,
    verbose=False,
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

ask_llm = ChatOpenAI(
    temperature=0.5,
    model_name="gpt-3.5-turbo",
    openai_api_key="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",
    request_timeout=600,
    verbose=False,
    #callback_manager=manager,
    #max_tokens=max_tokens,
    )

tools.append(Tool(
    name = "Organic Results",
    func=dummy_sync_function,
    coroutine=get_organic_results,
    description=ORGANIC_RESULTS_ASK_TOOL_DESCRIPTION,
))

tools.append(Tool(
    name = "Summarize Webpage",
    func=dummy_sync_function,
    coroutine=parse_summary_webpage_input,
    description=SUMMARIZE_WEBPAGE_ASK_TOOL_DESCRIPTION,
))

tools.append(Tool(
    name = "Q&A Webpage",
    func=dummy_sync_function,
    coroutine=parse_qa_webpage_input,
    description=QA_WEBPAGE_ASK_TOOL_DESCRIPTION,
))

tools.append(Tool(
    name = "Recognize Image",
    func=dummy_sync_function,
    coroutine=parse_blip_recognition,
    description=RECOGNIZE_IMAGE_ASK_TOOL_DESCRIPTION,
))

tools.append(Tool(
    name = "Image Search",
    func=dummy_sync_function,
    coroutine=get_image_from_search,
    description=IMAGE_SEARCH_ASK_TOOL_DESCRIPTION,
))

k_limit = 3

memory = ConversationBufferWindowMemory(
    k=k_limit,
    #return_messages=True,
    memory_key="chat_history",
    return_messages=True,
)

agent_chain = initialize_agent(
    tools=tools,
    llm=ask_llm,
    agent=AgentType.CHAT_CONVERSATIONAL_REACT_DESCRIPTION,
    verbose=True,
    memory=memory,
)

while True:
    prompt = input("User: ")
    reply = agent_chain.run(prompt)
    print(f"Agent: {reply}")