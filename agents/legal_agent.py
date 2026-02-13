"""Legal specialist agent."""
import logging
import os
from typing import List
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

from config.llm import get_llm
from rag.retriever import RAGRetriever
from utils.doc_utils import truncate_doc, get_last_user_text, MAX_DOC_CHARS


class LegalAgent:
    """Specialist agent for legal queries."""
    
    def __init__(self):
        """Initialize legal agent with LLM and RAG retriever."""
        self.llm = get_llm(temperature=1.0)
        try:
            index_name = os.getenv("AZURE_SEARCH_INDEX_LEGAL") or "multimodal-rag-1770652413829"
            self.search_client = RAGRetriever(index_name)
            self.index_name = index_name
        except Exception as e:
            print(f"[LegalAgent] Warning: Could not initialize search client: {e}")
            self.search_client = None
            self.index_name = ""

        self.logger = logging.getLogger("nova.rag.legal")
        if not self.logger.handlers:
            logging.basicConfig(level=logging.INFO)
    
    def analyze(
        self, 
        query: str, 
        document_text: str = "",
        messages: List[BaseMessage] = None
    ) -> str:
        """
        Analyze legal query using RAG context and document.
        
        Args:
            query: User's legal question
            document_text: Extracted text from user documents
            messages: Conversation history
            
        Returns:
            Analysis response in Spanish
        """
        if not query:
            return "No he recibido ninguna pregunta."
        
        # Get RAG context
        rag_data = ""
        if self.search_client:
            self.logger.info(f"[LegalAgent] RAG lookup index={self.index_name}")
            try:
                results = list(self.search_client.search(query=query, top=3))
                self.logger.info(f"[LegalAgent] RAG results={len(results)}")
                rag_texts = []
                for r in results:
                    txt = self._extract_text_from_result(r)
                    if txt:
                        rag_texts.append(txt)
                rag_data = "\n".join(rag_texts)
            except Exception as e:
                self.logger.warning(f"[LegalAgent] RAG error: {e}")
                rag_data = ""
        
        # Prepare context
        doc_text = truncate_doc(document_text or "", MAX_DOC_CHARS)

        history_text = ""
        if messages:
            recent = []
            for m in messages[-6:]:
                role = "Usuario"
                if isinstance(m, SystemMessage):
                    role = "Sistema"
                elif not isinstance(m, HumanMessage):
                    role = "Asistente"
                content = getattr(m, "content", "") or ""
                if content.strip():
                    recent.append(f"{role}: {content.strip()}")
            history_text = "\n".join(recent)
        
        # Build prompt
        prompt = (
            "Eres un especialista legal experto. RESPONDE usando el DOCUMENTO del usuario, el contexto RAG y, si aplica, la conversacion previa.\n"
            "Si el usuario pide repetir o aclarar una respuesta previa, responde usando la conversacion.\n"
            "Si la pregunta es confusa o sin sentido, pide al usuario que la reformule de forma educada.\n"
            "Si la pregunta esta claramente fuera del ambito legal/financiero, responde exactamente: 'Lo siento, no dispongo de información sobre ese tema. Sólo puedo ayudarte en temas financieros y legales.'\n"
            "Si no hay suficiente informacion en el contexto disponible, indicalo y pide mas detalle o un documento.\n"
            "Responde en español (castellano), de forma clara y profesional.\n"
            "\nCONVERSACION RECIENTE:\n"
            f"{history_text}\n"
            "\nDOCUMENTO DEL USUARIO:\n"
            f"{doc_text}\n"
            "\nCONTEXTO RAG (Base de conocimientos legales):\n"
            f"{rag_data}\n"
        )
        
        # Get response from LLM
        response = self.llm.invoke([
            SystemMessage(content=prompt),
            HumanMessage(content=query)
        ])
        
        return (response.content or "").strip()
    
    def _extract_text_from_result(self, r: dict) -> str:
        """Extract text from Azure Search result."""
        candidates = [
            "content_text", "content", "text", "document_text", 
            "body", "searchable_text",
        ]
        
        # Try standard fields
        for k in candidates:
            try:
                v = None
                if hasattr(r, "get"):
                    v = r.get(k, None)
                if not v and hasattr(r, "__getitem__"):
                    v = r[k]
                if not v:
                    v = getattr(r, k, None)
                if v:
                    return str(v)
            except Exception:
                pass
        
        # Try to find any string field with substantial content
        try:
            d = dict(r)
            for kk, vv in d.items():
                if isinstance(vv, str) and len(vv.strip()) > 30:
                    return vv
        except Exception:
            pass
        
        # Fallback: convert to string
        return str(r) if r else ""
