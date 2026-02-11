"""LLM (Language Model) configuration."""
from langchain_openai import AzureChatOpenAI
from .env import AZURE_OPENAI_KEY, AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_VERSION, AZURE_OPENAI_DEPLOYMENT


def get_llm(model: str = None, temperature: float = 0.0):
    """Create and return an Azure OpenAI LLM instance."""
    deployment = model if model else AZURE_OPENAI_DEPLOYMENT
    return AzureChatOpenAI(
        azure_deployment=deployment,
        api_version=AZURE_OPENAI_API_VERSION,
        azure_endpoint=AZURE_OPENAI_ENDPOINT,
        api_key=AZURE_OPENAI_KEY,
        temperature=temperature,
    )
