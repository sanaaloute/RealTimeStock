"""Ollama Cloud example. Uses same config as agent/bot (.env: OLLAMA_CLOUD=true, OLLAMA_API_KEY)."""
import config

if not config.OLLAMA_CLOUD or not config.OLLAMA_API_KEY:
    raise SystemExit(
        "OLLAMA_CLOUD=true and OLLAMA_API_KEY required. Add to .env (from https://ollama.com/settings/keys)"
    )

from ollama import Client

client = Client(
    host=config.OLLAMA_CLOUD_HOST,
    headers={"Authorization": f"Bearer {config.OLLAMA_API_KEY}"},
)

messages = [{"role": "user", "content": "Why is the sky blue?"}]

for part in client.chat(config.OLLAMA_CLOUD_MODEL, messages=messages, stream=True):
    print(part["message"]["content"], end="", flush=True)