# backend/llm/ollama_client.py
import json
import httpx
from config import settings


async def chat(messages: list[dict], response_format: str = "text") -> str:
    """
    Send a chat request to Ollama.
    messages: list of {"role": "user"|"assistant"|"system", "content": "..."}
    response_format: "text" or "json"
    Returns the model's response content as a string.
    """
    payload: dict = {
        "model": settings.ollama_model,
        "messages": messages,
        "stream": False,
    }
    if response_format == "json":
        payload["format"] = "json"

    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            f"{settings.ollama_base_url}/api/chat",
            json=payload,
        )
        response.raise_for_status()
        return response.json()["message"]["content"]


async def chat_json(messages: list[dict]) -> dict:
    """Like chat() but requests JSON output and parses the result."""
    content = await chat(messages, response_format="json")
    return json.loads(content)
