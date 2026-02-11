import sys
import os
from pathlib import Path

# Add backend root to Python path
backend_root = Path(__file__).parent.parent
sys.path.insert(0, str(backend_root))

from agents import LangGraphAssistant, OrchestratorAgent


def main():
    engine = LangGraphAssistant()

    query = "Hablame del fondo de inversión del bbva"
    print("--- RAG detailed results (up to 3) ---")

    client = getattr(engine, 'financial_search', None)
    if client:
        try:
            results = client.search(query=query, top=3)
            found = False
            for i, r in enumerate(results):
                found = True
                print(f"---- RESULT {i+1} ----")
                # print all available fields for inspection
                try:
                    for k, v in r.items():
                        # truncate long strings for readability
                        if isinstance(v, str):
                            print(k + ":", (v[:800] + '...') if len(v) > 800 else v)
                        else:
                            print(k + ":", v)
                except Exception:
                    print("Could not iterate result fields; raw repr:\n", repr(r))
                print("-------------------\n")
            if not found:
                print("No RAG documents found.")
        except Exception as e:
            print(f"RAG search error: {e}")
    else:
        print("Financial search client not initialized; skipping RAG test.")

    print("\n--- OrchestratorAgent.respond() -> full pipeline (may call LLM) ---")
    try:
        orchestrator = OrchestratorAgent()
        ans = orchestrator.respond(query, filepaths=[])
        print("Answer:\n", ans)
    except Exception as e:
        print(f"Error calling OrchestratorAgent.respond(): {e}")


if __name__ == '__main__':
    main()
