import re
from typing import Union

from langchain.agents.agent import AgentOutputParser
from langchain.agents.conversational.prompt import FORMAT_INSTRUCTIONS
from langchain.output_parsers.json import parse_json_markdown
from langchain.schema import AgentAction, AgentFinish, OutputParserException

from constants import (
    ORGANIC_RESULTS_TOOL_DESCRIPTION,
    QA_WEBPAGE_TOOL_DESCRIPTION,
    WEBPAGE_WINDOW_TOOL_DESCRIPTION,
    IMAGE_SEARCH_TOOL_DESCRIPTION,
    RECOGNIZE_IMAGE_TOOL_DESCRIPTION,
    SUMMARIZE_WEBPAGE_TOOL_DESCRIPTION,
    PYTHON_REPL_TOOL_DESCRIPTION,
    
    get_ask_prefix,
    get_ask_custom_format_instructions,
    get_ask_suffix,
    get_template_tool_response,
    
    get_chat_prefix,
    get_chat_custom_format_instructions,
    get_chat_suffix,
    
    get_thread_namer_prompt,
    
    FEATURES,
)

class ConvoOutputParser(AgentOutputParser):
    ai_prefix: str = "Iva"

    def get_format_instructions(self) -> str:
        return FORMAT_INSTRUCTIONS

    def parse(self, text: str) -> Union[AgentAction, AgentFinish]:
        if f"{self.ai_prefix}:" in text:
            return AgentFinish(
                {"output": text.split(f"{self.ai_prefix}:")[-1].strip()}, text
            )
        regex = r"(?s)Action: (.*?)[\n]*Action Input: (.*)"
        match = re.search(regex, text)
        if not match:
            raise OutputParserException(f"Could not parse LLM output: `{text}`")
        action = match.group(1)
        action_input = match.group(2)
        return AgentAction(action.strip(), action_input.strip(" ").strip('"'), text)

    @property
    def _type(self) -> str:
        return "conversational"
    
class ChatConvoOutputParser(AgentOutputParser):
    def get_format_instructions(self) -> str:
        custom_format_instructions = get_ask_custom_format_instructions()
        return custom_format_instructions

    def parse(self, text: str) -> Union[AgentAction, AgentFinish]:
        try:
            if "action: Final Answer" in text:
                return AgentFinish({"output": text.split("action_input:")[-1].strip()}, text)
            else:
                regex = r"(?s)action: (.*?)[\n]*action_input: (.*)"
                match = re.search(regex, text)
                if not match:
                    raise OutputParserException(f"Could not parse LLM output: `{text}`")
                action = match.group(1)
                action_input = match.group(2)
                return AgentAction(action.strip(), action_input.strip(" ").strip('"'), text)
        except Exception as e:
            raise OutputParserException(f"Could not parse LLM output: {text}") from e
    @property
    def _type(self) -> str:
        return "conversational_chat"