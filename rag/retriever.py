"""RAG (Retrieval-Augmented Generation) retriever."""
import logging
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery
from azure.core.credentials import AzureKeyCredential
from typing import List, Dict, Optional
from config.env import AZURE_SEARCH_KEY, AZURE_SEARCH_ENDPOINT

logger = logging.getLogger("nova.rag.retriever")


class RAGRetriever:
    """Retrieves documents from Azure Search for RAG."""
    
    def __init__(self, index_name: str, timeout: int = 500):
        from azure.core.pipeline.policies import RetryPolicy
        from azure.core.pipeline.transport import RequestsTransport
        from openai import AzureOpenAI
        from config.env import AZURE_OPENAI_KEY, AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_VERSION
        
        self.search_client = SearchClient(
            endpoint=AZURE_SEARCH_ENDPOINT,
            index_name=index_name,
            credential=AzureKeyCredential(AZURE_SEARCH_KEY),
            transport=RequestsTransport(connection_timeout=timeout, read_timeout=timeout)
        )
        # Construct semantic configuration name dynamically
        self.semantic_config_name = f"{index_name}-semantic-configuration"
        
        # Initialize OpenAI client for embeddings
        self.openai_client = AzureOpenAI(
            api_key=AZURE_OPENAI_KEY,
            api_version=AZURE_OPENAI_API_VERSION,
            azure_endpoint=AZURE_OPENAI_ENDPOINT
        )
    
    def search(self, query: str, top: int = 25, min_relevance: float = 0.3) -> List[Dict]:
        """Search for documents matching the query.
        
        Args:
            query: Search query text
            top: Maximum number of results to return
            min_relevance: Minimum relevance score threshold (0.0 to 1.0)
        """
        logger.info(f"[RAGRetriever] Searching with query='{query}', top={top}, min_relevance={min_relevance}")
        
        # Generate embedding for the query
        try:
            embedding_response = self.openai_client.embeddings.create(
                input=query,
                model="text-embedding-3-large"
            )
            query_embedding = embedding_response.data[0].embedding
            logger.info(f"[RAGRetriever] Generated embedding vector (dim={len(query_embedding)})")
        except Exception as e:
            logger.error(f"[RAGRetriever] Error generating embedding: {e}")
            query_embedding = None
        
        # Prepare vector query for hybrid search
        vector_queries = []
        if query_embedding:
            vector_queries.append(VectorizedQuery(
                vector=query_embedding,
                k_nearest_neighbors=50,
                fields="content_embedding"
            ))
        
        # Hybrid search: text + vector + semantic reranking
        results = self.search_client.search(
            search_text=query, 
            top=top,
            vector_queries=vector_queries if vector_queries else None,
            query_type="semantic",
            semantic_configuration_name=self.semantic_config_name
        )
        
        # Convert to list and log raw results
        all_results = list(results)
        logger.info(f"[RAGRetriever] Azure Search returned {len(all_results)} results")
        
        # Log scores before filtering
        for i, result in enumerate(all_results[:5]):  # Log first 5
            score = result.get('@search.score', 0)
            logger.info(f"[RAGRetriever] Result {i}: score={score}")
        
        # Filter results by minimum relevance score
        filtered_results = [
            result for result in all_results 
            if result.get('@search.score', 0) >= min_relevance
        ]
        
        logger.info(f"[RAGRetriever] After filtering with min_relevance={min_relevance}: {len(filtered_results)} results")
        
        return filtered_results
    
    def retrieve(self, query: str, top: int = 25, min_relevance: float = 0.3) -> str:
        """Retrieve documents and format as context string.
        
        Args:
            query: Search query text
            top: Maximum number of results to return
            min_relevance: Minimum relevance score threshold (0.0 to 1.0)
        """
        results = self.search(query, top, min_relevance)
        context = ""
        for result in results:
            context += f"{result.get('content', '')}\n\n"
        return context.strip()