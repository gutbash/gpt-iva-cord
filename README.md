# iva

An academic research project that aims to extend the capabilities of the [OpenAI](https://platform.openai.com/overview) large language models.

This bot uses the [LangChain](https://python.langchain.com/en/latest/) framework for interacting with [OpenAI Python Library](https://github.com/openai/openai-python). It is interfaced through the [discord.py](https://discordpy.readthedocs.io/) API wrapper.

## Commands
There are two separate ways to talk to iva, both with their own conversation history: `@iva` and `/iva`.

### `@iva`
Provides chat and conversation oriented answers. has personality, asks questions back, is more creative.
- Responds to any mention in any type of channel, even without an argument.
- Each conversation carries a summary memory window buffer according to token count, so there is no hard context limit, and conversations carry extreme longevity and efficiency without the need for embeddings.

### `/iva`
Provides academic and work oriented answers. has less personality, is more focused on consistency and reliability.
- Starts a named public thread if in a text channel, with a `prompt` argument and an optional `file` argument.
- Conversation carries a memory window buffer according to token count, so there is no hard context limit.
  ### Buttons
  - `Delete` the last interaction with iva in the conversation.
  - `Reset` conversation history, clear iva's memory with you in the channel.

## Other
### `/reset`
Reset `@iva` and `/iva` conversation history.
### `/model`
Switch between `gpt-4`, `gpt-3.5`, and `text-davinci-003` models. enter with no argument to get current value.
### `/temperature`
Change the model's `temperature` parameter, takes in float point value between `0.0` to `2.0`. enter with no argument to get current value.
### `/help`
Show instructions for setup.
### `/setup`
Enter the OpenAI API key to use iva. enter with no argument to get current value.
### `/features`
Learn all the features iva has to offer.

## Features
### :newspaper: **Internet Browsing**
Iva safely searches, summarizes, and answers questions on the web, sharing articles, videos, images, social media posts, music, wikis, movies, shopping, and more.
### :pencil: **Citations**
Iva cites any sources utilized to give users the power to explore and verify information on their own in the pursuit of truthfulness and prevention of hallucinations.
### :file_folder: **File Input**
Drag and drop your file in context. Iva will process pretty much any popular file type (`.txt`, `.pdf`, `.py`, `.cs`, etc.) for debugging, Q&A, and more.
### :link: **Link Input**
Send `.pdf` or article URLs to Iva with *no length limit*. Iva will perform summarization and/or Q&A on the content for uncompromised results.
### :brain: **Persistent Seamless Memory**
Iva's memory never runs into length limits, and retains the chat history. Pick up where you left off and refer to previous chat events.
### :busts_in_silhouette: **Group Conversations**
Iva can optionally speak to multiple users in one channel and recognizes individual users, enabling collaborative discussions and more inclusive ideas.
### :eye: **Image Recognition with BLIP2**
Iva intelligently recognizes and answers questions of a given image, all while remaining in the context of the conversation.
### :abacus: **LaTeX Formatting**
Iva writes STEM expressions in beautiful LaTeX.
### :computer: **Codex**
Iva debugs and codes in formatted blocks.
### :bust_in_silhouette: **User Settings**
Personal settings such as model switching between `gpt-4` and `gpt-3.5` persist for a familiar workflow you can return to at any time.
### :mag: **AI Content Detector** (TBA)
We are collaborating with a leading content detection service to provide on-the-fly content detection.
