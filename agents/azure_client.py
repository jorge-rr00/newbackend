"""Azure OpenAI client wrapper."""


class AzureOpenAIClient:
    """Azure OpenAI client for compatibility."""
    
    def __init__(self, config: dict = None):
        """Initialize Azure OpenAI client."""
        self.config = config or {}
