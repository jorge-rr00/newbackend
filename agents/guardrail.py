"""Guardrail agent for validating queries."""
from langchain_core.messages import SystemMessage, HumanMessage
from config.llm import get_llm


class GuardrailAgent:
    """Validates user queries for content policy compliance."""
    
    def __init__(self, client=None):
        """Initialize guardrail agent."""
        self.llm = get_llm(temperature=1.0)

    def validate(self, query: str, files: list) -> tuple:
        """
        Validate if query is on legal or financial topics.
        
        Args:
            query: User query text
            files: List of uploaded file names
            
        Returns:
            (is_valid, reason) tuple
        """
        # If files are attached, allow (assumes user intent is domain-specific)
        if files:
            return True, None

        sys = (
            "Eres un clasificador de guardrail para un asistente especializado en temas legales y financieros.\n\n"
            "Tu tarea es determinar si una consulta del usuario está relacionada con:\n"
            "- Temas LEGALES (contratos, leyes, regulaciones, derechos, obligaciones legales, etc.)\n"
            "- Temas FINANCIEROS (análisis de estados financieros, inversiones, presupuestos, métricas económicas, etc.)\n\n"
            "Instrucciones:\n"
            "- Si la consulta está claramente relacionada con legal o finanzas, responde SOLO con: ACCEPT\n"
            "- Si la consulta es sobre otros temas (tecnología, medicina, recetas, historia, etc.), responde SOLO con: REJECT\n"
            "- Si la consulta es ambigua o un saludo inicial, responde con: ACCEPT\n\n"
            "Responde únicamente con ACCEPT o REJECT, sin explicaciones adicionales."
        )
        res = self.llm.invoke([SystemMessage(content=sys), HumanMessage(content=query or "")])
        ok = "ACCEPT" in (res.content or "").upper()
        return (ok, None if ok else "Lo siento, solo puedo ayudarte con consultas legales o financieras. Por favor, reformula tu pregunta dentro de estos temas.")
