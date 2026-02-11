"""RAG (Retrieval-Augmented Generation) retriever."""
from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential
from typing import List, Dict, Optional
from config.env import AZURE_SEARCH_KEY, AZURE_SEARCH_ENDPOINT


class RAGRetriever:
    """Retrieves documents from Azure Search for RAG."""
    
    def __init__(self, index_name: str):
        self.search_client = SearchClient(
            endpoint=AZURE_SEARCH_ENDPOINT,
            index_name=index_name,
            credential=AzureKeyCredential(AZURE_SEARCH_KEY)
        )
    
    def search(self, query: str, top: int = 5) -> List[Dict]:
        """Search for documents matching the query."""
        results = self.search_client.search(search_text=query, top=top)
        return [result for result in results]
    
    def retrieve(self, query: str, top: int = 5) -> str:
        """Retrieve documents and format as context string."""
        results = self.search(query, top)
        context = ""
        for result in results:
            context += f"{result.get('content', '')}\n\n"
        return context.strip()
