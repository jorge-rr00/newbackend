"""Orchestrator agents for managing conversations."""
from typing import List, Dict, Optional
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage, AIMessage

from graph.workflow import LangGraphAssistant
from utils.doc_utils import (
    strip_hidden_doc_tags, 
    extract_hidden_doc_text, 
    truncate_doc, 
    HIST_TAG_START, 
    HIST_TAG_END,
    MAX_DOC_CHARS
)


class OrchestratorAgent:
    """Main orchestrator agent for handling user queries."""
    
    def __init__(self, client=None):
        """Initialize orchestrator agent."""
        self.engine = LangGraphAssistant()

    def respond(
        self, 
        user_query: str, 
        filepaths: List[str], 
        session_history: List[dict] = None
    ) -> str:
        """
        Respond to user query with optional file context.
        
        Args:
            user_query: The user's question
            filepaths: List of file paths to process
            session_history: Previous conversation history
            
        Returns:
            Response text with hidden doc tags
        """
        messages: List[BaseMessage] = []
        historical_doc_text = ""

        # 1) Rebuild messages from session history
        if session_history:
            for m in session_history:
                raw_content = (m.get("content") or "")
                role = (m.get("role") or "").strip().lower()

                # extract doc memory if present
                extracted = extract_hidden_doc_text(raw_content)
                if extracted:
                    historical_doc_text = extracted

                # strip tags before giving to LLM
                clean_content = strip_hidden_doc_tags(raw_content)
                if not clean_content:
                    continue

                if role == "user":
                    messages.append(HumanMessage(content=clean_content))
                elif role == "assistant":
                    messages.append(AIMessage(content=clean_content))
                elif role == "system":
                    messages.append(SystemMessage(content=clean_content))
                else:
                    messages.append(AIMessage(content=clean_content))

        # 2) Append current user message
        messages.append(HumanMessage(content=(user_query or "").strip()))

        # 3) Run graph
        result = self.engine.app.invoke(
            {
                "messages": messages,
                "file_paths": filepaths or [],
                "extracted_text": truncate_doc(historical_doc_text, MAX_DOC_CHARS),
                "domain": "",
                "specialist_analysis": "",
                "final_response": "",
                "voice_mode": False,
            }
        )

        final_ans = (result.get("final_response") or "").strip()

        # 4) Persist document text invisibly for next turns
        extracted_text = truncate_doc((result.get("extracted_text") or "").strip(), MAX_DOC_CHARS)
        if extracted_text:
            final_ans = final_ans + "\n" + HIST_TAG_START + extracted_text + HIST_TAG_END

        return final_ans


class VoiceOrchestratorAgent(OrchestratorAgent):
    """Voice-specific orchestrator agent."""
    
    def respond(
        self, 
        user_query: str, 
        filepaths: List[str], 
        session_history: List[dict] = None
    ) -> str:
        """
        Voice mode response (same flow as regular orchestrator).
        
        Args:
            user_query: The user's question
            filepaths: List of file paths to process
            session_history: Previous conversation history
            
        Returns:
            Response text with hidden doc tags
        """
        return super().respond(user_query, filepaths, session_history)
