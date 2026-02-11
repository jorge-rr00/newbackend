"""LangGraph-based LLM orchestrator engine."""
import operator
from typing import List, Dict, TypedDict, Annotated

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage, AIMessage
from langgraph.graph import StateGraph, END
from PyPDF2 import PdfReader
import docx

from config.llm import get_llm
from agents.financial_agent import FinancialAgent
from agents.legal_agent import LegalAgent
from utils.doc_utils import (
    truncate_doc,
    get_last_user_text,
    ocr_image,
    HIST_TAG_START,
    HIST_TAG_END,
    MAX_DOC_CHARS,
)

TOPIC_KEYWORDS = {
    "financial": [
        "financ", "financial", "financiero", "finanzas", "banco", "invers", 
        "contab", "crédito", "hipote", "impuest", "iva", "amortiz",
    ],
    "legal": [
        "legal", "contrato", "demanda", "ley", "juríd", "abogado", 
        "testamento", "acuerdo", "litigio", "arrend",
    ],
}


class AgentState(TypedDict):
    """State definition for the LangGraph workflow."""
    messages: Annotated[List[BaseMessage], operator.add]
    file_paths: List[str]
    extracted_text: str
    domain: str
    specialist_analysis: str
    final_response: str
    voice_mode: bool


class LangGraphAssistant:
    """Main LangGraph-based assistant orchestrator."""
    
    def __init__(self):
        """Initialize the assistant and build workflow."""
        self.llm = get_llm(temperature=1.0)

        # Specialist agents
        try:
            self.legal_agent = LegalAgent()
            self.financial_agent = FinancialAgent()
        except Exception as e:
            print(f"[LangGraphAssistant] Warning: Could not initialize specialist agents: {e}")
            self.legal_agent = None
            self.financial_agent = None

        self.app = self._build_workflow()

    def tool_node(self, state: AgentState):
        """Extract text from uploaded files."""
        # If no new files, keep previous extracted_text (from memory)
        if not state.get("file_paths"):
            return {"extracted_text": state.get("extracted_text", "") or ""}

        print("[Node: Tool] Processing new files...")
        text_dump = ""
        for p in state["file_paths"]:
            ext = p.split(".")[-1].lower()
            try:
                if ext == "pdf":
                    reader = PdfReader(p)
                    text_dump += "".join([(page.extract_text() or "") for page in reader.pages])
                elif ext in ("jpg", "jpeg", "png"):
                    text_dump += ocr_image(p)
                elif ext in ("docx", "doc"):
                    d = docx.Document(p)
                    text_dump += "\n".join([para.text for para in d.paragraphs])
                else:
                    print(f"[Node: Tool] Unsupported extension: {ext}")
            except Exception as e:
                print(f"[Node: Tool] Error processing {p}: {e}")

        # Combine previous (memory) + new
        combined_text = (state.get("extracted_text", "") or "") + "\n" + (text_dump or "")
        combined_text = truncate_doc(combined_text.strip(), MAX_DOC_CHARS)
        print(f"[Node: Tool] Extracted chars: {len(combined_text)}")
        return {"extracted_text": combined_text}

    def orchestrator_node(self, state: AgentState):
        """Route query or answer directly from document."""
        user_query = get_last_user_text(state.get("messages", []))
        if not user_query:
            return {"final_response": "No he recibido la pregunta del usuario. Reintenta."}

        doc_context = truncate_doc(state.get("extracted_text", "") or "", MAX_DOC_CHARS)

        sys_prompt = (
            "You are the Senior Orchestrator.\n"
            "Your top priority is to answer using the USER UPLOADED DOCUMENT, if present.\n"
            "Rules:\n"
            "1) If the answer is in the document, answer directly and stop.\n"
            "2) If NOT in the document and need legal/financial knowledge, respond with 'DOMAIN:LEGAL' or 'DOMAIN:FINANCIAL'.\n"
            "3) Respond in Spanish (Castellano).\n"
            "\nDOCUMENT:\n"
            f"{doc_context}"
        )

        res = self.llm.invoke([SystemMessage(content=sys_prompt), HumanMessage(content=user_query)])
        upper = (res.content or "").upper().strip()

        # Route if the model explicitly emits DOMAIN:...
        if "DOMAIN:" in upper:
            domain = "legal" if "LEGAL" in upper else "financial"
            print(f"[Node: Orchestrator] Routing -> {domain}")
            return {"domain": domain, "final_response": ""}

        # Direct answer
        direct_answer = (res.content or "").strip()
        ql = (user_query or "").lower()
        is_finlegal = any(k in ql for k in TOPIC_KEYWORDS.get("financial", [])) or \
                     any(k in ql for k in TOPIC_KEYWORDS.get("legal", []))

        if not is_finlegal:
            polite_msg = (
                "Lo siento, no dispongo de información sobre ese tema. Sólo puedo ayudarte en temas financieros y legales."
            )
            return {"final_response": polite_msg}

        return {"final_response": direct_answer}

    def specialist_node(self, state: AgentState):
        """Specialist analysis using domain-specific agents."""
        domain = (state.get("domain") or "").strip().lower() or "legal"
        query = get_last_user_text(state.get("messages", []))
        document_text = state.get("extracted_text", "") or ""

        # Select appropriate agent
        agent = self.legal_agent if domain == "legal" else self.financial_agent
        
        if not agent:
            return {"specialist_analysis": "No se pudo acceder al agente especialista."}

        print(f"[Node: Specialist] Using {domain} agent...")
        try:
            analysis = agent.analyze(
                query=query,
                document_text=document_text,
                messages=state.get("messages", [])
            )
            return {"specialist_analysis": analysis}
        except Exception as e:
            print(f"[Node: Specialist] Agent error: {e}")
            return {"specialist_analysis": "Lo siento, ocurrió un error al procesar tu consulta."}

    def final_redactor_node(self, state: AgentState):
        """Final redaction of specialist analysis."""
        if state.get("final_response"):
            return {}

        analysis = (state.get("specialist_analysis") or "").strip()
        if not analysis:
            return {"final_response": "No tengo suficiente información para responder."}

        sys_msg = SystemMessage(
            content=(
                "You are the Orchestrator. Rewrite this analysis into natural Spanish.\n"
                "Be brief, direct. Respond in Spanish (Castellano).\n"
            )
        )
        res = self.llm.invoke([sys_msg, HumanMessage(content=analysis)])
        return {"final_response": (res.content or "").strip()}

    def _build_workflow(self):
        """Build the LangGraph workflow."""
        builder = StateGraph(AgentState)
        builder.add_node("tool", self.tool_node)
        builder.add_node("orchestrator", self.orchestrator_node)
        builder.add_node("specialist", self.specialist_node)
        builder.add_node("final_redactor", self.final_redactor_node)

        builder.set_entry_point("tool")
        builder.add_edge("tool", "orchestrator")
        builder.add_conditional_edges(
            "orchestrator",
            lambda x: "end" if (x.get("final_response") or "").strip() else "specialist",
            {"end": END, "specialist": "specialist"},
        )
        builder.add_edge("specialist", "final_redactor")
        builder.add_edge("final_redactor", END)

        return builder.compile()
