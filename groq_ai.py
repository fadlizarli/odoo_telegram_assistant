import httpx
import config

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

async def ask(messages: list, system_prompt: str) -> str:
    try:
        return await _ask_groq(messages, system_prompt)
    except Exception as e:
        print(f"[Groq Error] {e}")
        return "Maaf, AI sedang sibuk. Coba lagi beberapa saat."

async def _ask_groq(messages: list, system_prompt: str) -> str:
    full_messages = [{"role": "system", "content": system_prompt}] + messages
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            GROQ_URL,
            headers={"Authorization": f"Bearer {config.GROQ_API_KEY}", "Content-Type": "application/json"},
            json={"model": config.GROQ_MODEL, "messages": full_messages, "max_tokens": 1024, "temperature": 0.7}
        )
        response.raise_for_status()
        return response.json()['choices'][0]['message']['content']
