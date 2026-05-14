from langchain_openai import ChatOpenAI

from app.config import settings

DEFAULT_MODELS = {
    "rfp": "anthropic/claude-3.5-sonnet",
    "proposal_intake": "anthropic/claude-3-haiku",
    "evaluation": "anthropic/claude-3.5-sonnet",
    "contract": "anthropic/claude-3.5-sonnet",
}


def get_llm(model_id: str, temperature: float = 0.3) -> ChatOpenAI:
    return ChatOpenAI(
        model=model_id,
        openai_api_key=settings.OPENROUTER_API_KEY,
        openai_api_base="https://openrouter.ai/api/v1",
        temperature=temperature,
        extra_headers={
            "HTTP-Referer": settings.APP_URL,
            "X-Title": "Procura",
        },
    )
