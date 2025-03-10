from typing import Dict, List, Literal, Optional, Union
from openai import (
    APIError,
    AsyncAzureOpenAI,
    AsyncOpenAI,
    AuthenticationError,
    OpenAIError,
    RateLimitError,
)
from openai.types.chat import ChatCompletionMessage  # Correct import path
from tenacity import retry, stop_after_attempt, wait_random_exponential, retry_if_exception_type, wait_fixed
import httpx
import json
from app.config import LLMSettings, config
from app.logger import logger
from app.schema import Message, GeminiToolCallMessage
import time

class LLM:
    _instances: Dict[str, "LLM"] = {}

    def __new__(
            cls, config_name: str = "default", llm_config: Optional[LLMSettings] = None
    ):
        if config_name not in cls._instances:
            instance = super().__new__(cls)
            instance.__init__(config_name, llm_config)
            cls._instances[config_name] = instance
        return cls._instances[config_name]

    def __init__(
            self, config_name: str = "default", llm_config: Optional[LLMSettings] = None
    ):
        if not hasattr(self, "client"):  # Only initialize if not already initialized
            llm_config = llm_config or config.llm
            llm_config = llm_config.get(config_name, llm_config["default"])
            self.model = llm_config.model
            self.max_tokens = llm_config.max_tokens
            self.temperature = llm_config.temperature
            self.api_type = llm_config.api_type
            self.api_key = llm_config.api_key
            self.api_version = llm_config.api_version
            self.base_url = llm_config.base_url
            if self.api_type == "azure":
                self.client = AsyncAzureOpenAI(
                    base_url=self.base_url,
                    api_key=self.api_key,
                    api_version=self.api_version,
                )
            elif self.model.startswith("gemini"):
                self.client = httpx.AsyncClient()  # using httpx async client
            else:
                self.client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)

    @staticmethod
    def format_messages(messages: List[Union[dict, Message]]) -> List[dict]:
        """
        Format messages for LLM by converting them to OpenAI message format.
        Args:
            messages: List of messages that can be either dict or Message objects
        Returns:
            List[dict]: List of formatted messages in OpenAI format
        Raises:
            ValueError: If messages are invalid or missing required fields
            TypeError: If unsupported message types are provided
        """
        formatted_messages = []
        for message in messages:
            if isinstance(message, dict):
                # If message is already a dict, ensure it has required fields
                if "role" not in message:
                    raise ValueError("Message dict must contain 'role' field")
                formatted_messages.append(message)
            elif isinstance(message, Message):
                # If message is a Message object, convert it to dict
                formatted_messages.append(message.to_dict())
            else:
                raise TypeError(f"Unsupported message type: {type(message)}")
        # Validate all messages have required fields
        for msg in formatted_messages:
            if msg["role"] not in ["system", "user", "assistant", "tool"]:
                raise ValueError(f"Invalid role: {msg['role']}")
            if "content" not in msg and "tool_calls" not in msg:
                raise ValueError(
                    "Message must contain either 'content' or 'tool_calls'"
                )
        return formatted_messages

    @retry(
        wait=wait_random_exponential(min=1, max=60),
        stop=stop_after_attempt(6),
        retry=retry_if_exception_type(httpx.HTTPStatusError) # add retry for httpx error
    )
    async def ask(
            self,
            messages: List[Union[dict, Message]],
            system_msgs: Optional[List[Union[dict, Message]]] = None,
            stream: bool = True,
            temperature: Optional[float] = None,
    ) -> str:
        """
        Send a prompt to the LLM and get the response.
        Args:
            messages: List of conversation messages
            system_msgs: Optional system messages to prepend
            stream (bool): Whether to stream the response
            temperature: Sampling temperature for the response
        Returns:
            str: The generated response
        Raises:
            ValueError: If messages are invalid or response is empty
            OpenAIError: If API call fails after retries
            Exception: For unexpected errors
        """
        try:
            # Format system and user messages
            if system_msgs:
                system_msgs = self.format_messages(system_msgs)
                messages = system_msgs + self.format_messages(messages)
            else:
                messages = self.format_messages(messages)
            if self.model.startswith("gemini"):
                response = await self._gemini_completion(messages)
                return response
            if not stream:
                # Non-streaming request
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    max_tokens=self.max_tokens,
                    temperature=temperature or self.temperature,
                    stream=False,
                )
                if not response.choices or not response.choices[0].message.content:
                    raise ValueError("Empty or invalid response from LLM")
                return response.choices[0].message.content
            # Streaming request
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=self.max_tokens,
                temperature=temperature or self.temperature,
                stream=True,
            )
            collected_messages = []
            async for chunk in response:
                chunk_message = chunk.choices[0].delta.content or ""
                collected_messages.append(chunk_message)
                print(chunk_message, end="", flush=True)
            print()  # Newline after streaming
            full_response = "".join(collected_messages).strip()
            if not full_response:
                raise ValueError("Empty response from streaming LLM")
            return full_response
        except httpx.HTTPStatusError as e:
            logger.error(f"OpenAI API error: {e}")
            raise
        except ValueError as ve:
            logger.error(f"Validation error: {ve}")
            raise
        except OpenAIError as oe:
            logger.error(f"OpenAI API error: {oe}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in ask: {e}")
            raise

    @retry(
        wait=wait_random_exponential(min=1, max=60),
        stop=stop_after_attempt(6),
        retry=retry_if_exception_type(httpx.HTTPStatusError) # add retry for httpx error
    )
    async def ask_tool(
            self,
            messages: List[Union[dict, Message]],
            system_msgs: Optional[List[Union[dict, Message]]] = None,
            timeout: int = 60,
            tools: Optional[List[dict]] = None,
            tool_choice: Literal["none", "auto", "required"] = "auto",
            temperature: Optional[float] = None,
            **kwargs,
    ) -> Union[str, ChatCompletionMessage, GeminiToolCallMessage]:  # add `GeminiToolCallMessage`
        """
        Ask LLM using functions/tools and return the response.
        Args:
            messages: List of conversation messages
            system_msgs: Optional system messages to prepend
            timeout: Request timeout in seconds
            tools: List of tools to use
            tool_choice: Tool choice strategy
            temperature: Sampling temperature for the response
            **kwargs: Additional completion arguments
        Returns:
            ChatCompletionMessage: The model's response
        Raises:
            ValueError: If tools, tool_choice, or messages are invalid
            OpenAIError: If API call fails after retries
            Exception: For unexpected errors
        """
        if self.model.startswith("gemini"):
            # Gemini tool calling logic
            return await self._gemini_completion_with_tool(
                messages=messages,
                system_msgs=system_msgs,
                tools=tools,
                temperature=temperature,
            )

        try:
            # Validate tool_choice
            if tool_choice not in ["none", "auto", "required"]:
                raise ValueError(f"Invalid tool_choice: {tool_choice}")
            # Format messages
            if system_msgs:
                system_msgs = self.format_messages(system_msgs)
                messages = system_msgs + self.format_messages(messages)
            else:
                messages = self.format_messages(messages)
            # Validate tools if provided
            if tools:
                for tool in tools:
                    if not isinstance(tool, dict) or "type" not in tool:
                        raise ValueError("Each tool must be a dict with 'type' field")
            # Set up the completion request
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature or self.temperature,
                max_tokens=self.max_tokens,
                tools=tools,
                tool_choice=tool_choice,
                timeout=timeout,
                **kwargs,
            )
            # Check if response is valid
            if not response.choices or not response.choices[0].message:
                print(response)
                raise ValueError("Invalid or empty response from LLM")
            return response.choices[0].message
        except httpx.HTTPStatusError as e:
            logger.error(f"OpenAI API error: {e}")
            raise
        except ValueError as ve:
            logger.error(f"Validation error in ask_tool: {ve}")
            raise
        except OpenAIError as oe:
            if isinstance(oe, AuthenticationError):
                logger.error("Authentication failed. Check API key.")
            elif isinstance(oe, RateLimitError):
                logger.error("Rate limit exceeded. Consider increasing retry attempts.")
            elif isinstance(oe, APIError):
                logger.error(f"API error: {oe}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in ask_tool: {e}")
            raise

    async def _gemini_completion(self, messages):
        """
        Use the Gemini API to complete message.
        """
        api_endpoint = (
            f"{self.base_url}/models/{self.model}:generateContent?key={self.api_key}"
        )
        headers = {"Content-Type": "application/json"}
        gemini_messages = []
        for item in messages:
            if item["role"] == "system":
                gemini_messages.append(
                    {"role": "user", "parts": [{"text": item["content"]}]}
                )
            else:
                gemini_messages.append(
                    {"role": item["role"], "parts": [{"text": item["content"]}]}
                )
        data = {"contents": gemini_messages}
        # remove the `async with` code.
        try:
            response = await self.client.post(api_endpoint, headers=headers, json=data, timeout=30) # add timeout
            response.raise_for_status()
            response_json = response.json()
            if "candidates" in response_json and response_json["candidates"]:
                return response_json["candidates"][0]["content"]["parts"][0]["text"]
            else:
                return "Gemini Model error!"
        except httpx.HTTPStatusError as e:
            logger.error(f"Gemini API error: {e}")
            raise

    async def _gemini_completion_with_tool(
            self, messages, system_msgs, tools, temperature
    ) -> GeminiToolCallMessage:  # add return type
        """
        Use the Gemini API to complete message with tools
        """
        # 1. Construct the tool descriptions for Gemini
        tool_descriptions = self._format_tools_for_gemini(tools)

        # 2. Add tool instructions to the system prompt
        system_msgs_content = ""
        if system_msgs and isinstance(system_msgs[0], Message):
            system_msgs_content = system_msgs[0].content

        system_prompt_with_tools = (
            f"{system_msgs_content}\n\n"  # Add origin system prompt
            f"You are an intelligent agent designed to call tools based on user instructions.\n" # add more description.
            f"You have access to the following tools. "
            f"Please use JSON format for tool calls:\n"
            f"{tool_descriptions}\n\n"
            f"**Important Instructions:**\n" # make the instructions more clear.
            f"- **Read Carefully**: Understand the instructions and available tools thoroughly.\n"
            f"- **Select Tool**: Select only one tool that is most appropriate for the task.\n"
            f"- **JSON Format**: Always use JSON format for tool calls.\n"
            f"- **Fill all required arguments**: Make sure you have fill all the required arguments.\n"
            f"- **Example**: If you need to call 'google_search' with query 'AI', the response should be:\n"
            f'{{"tool_calls": [{{"id": "call_abc123", "type": "function", "function": {{"name": "google_search", "arguments": {{"query": "AI"}}}}}}]}}' # make the example more clear
        )

        # update the system message
        # system_msgs[0]["content"] = system_prompt_with_tools # old wrong code.
        if system_msgs and isinstance(system_msgs[0], Message):
            system_msgs[0].content = system_prompt_with_tools

        # 3. call the completion.
        response = await self.ask(
            messages=messages, system_msgs=system_msgs, temperature=temperature
        )
        # 4. parse the response.
        tool_call = self._parse_gemini_tool_call(response)
        return GeminiToolCallMessage(
            content=response, tool_calls=tool_call.get("tool_calls") if tool_call else None
        )  # Change here!

    def _format_tools_for_gemini(self, tools):
        """Format tool descriptions for Gemini."""
        if not tools:
            return "No tools available."

        tool_descriptions = []
        for tool in tools:
            name = tool["function"]["name"]
            description = tool["function"]["description"]
            parameters = tool["function"]["parameters"]
            tool_descriptions.append(
                f"Tool Name: {name}\n"
                f"Description: {description}\n"
                f"Parameters: {json.dumps(parameters, ensure_ascii=False)}\n"
            )
        return "\n".join(tool_descriptions)

    def _parse_gemini_tool_call(self, response):
        """Parse tool calls from Gemini's response."""
        try:
            start_index = response.find("{")
            end_index = response.rfind("}") + 1
            if start_index != -1 and end_index != -1:
                json_str = response[start_index:end_index]
                tool_call_data = json.loads(json_str)

                if "tool_calls" in tool_call_data:
                    # Return the tool_calls part
                    return tool_call_data
                else:
                    return {}  # change here.
            else:
                return {}  # change here.
        except json.JSONDecodeError:
            return {}  # change here.