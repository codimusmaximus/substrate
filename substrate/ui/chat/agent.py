"""AI chat agent that loads tools from all domains."""
from pydantic_ai import Agent
from .tools import discover_tools

# Discover tools from all domains
tools = discover_tools()

agent = Agent(
    "openai:gpt-4o",
    system_prompt="""You are a helpful assistant for managing a personal business system.
You have access to tools for querying and updating data across different domains like CRM, notes, and sales.
Be concise and helpful.""",
    tools=tools,  # Pass tools directly to Agent constructor
)
