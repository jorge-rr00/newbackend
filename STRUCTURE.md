# Nova Backend - Project Structure

## Overview
The Nova backend follows a modular, scalable architecture with clear separation of concerns using LangGraph for workflow orchestration.

## Directory Structure

```
backend/
├── api/
│   ├── __init__.py
│   └── server.py          # Flask application with Pydantic validation
│
├── config/
│   ├── __init__.py
│   ├── env.py             # Environment variables configuration
│   ├── llm.py             # LLM (Azure OpenAI) configuration
│   └── sql.py             # Database configuration and queries
│
├── agents/
│   ├── __init__.py
│   ├── orchestrator.py     # Main orchestrator agents
│   ├── guardrail.py        # Content validation agent
│   ├── azure_client.py     # Azure OpenAI client wrapper
│   ├── financial_agent.py  # Financial domain specialist with RAG
│   ├── legal_agent.py      # Legal domain specialist with RAG
│   ├── employees/          # Employee-specific agents
│   │   ├── __init__.py
│   │   └── agents.py
│   ├── executives/         # Executive/management agents
│   │   ├── __init__.py
│   │   └── agents.py
│   ├── all_users/          # General-purpose agents
│   │   ├── __init__.py
│   │   └── agents.py
│   └── clients/            # External client agents
│       ├── __init__.py
│       └── agents.py
│
├── graph/
│   ├── __init__.py
│   └── workflow.py         # LangGraph workflow orchestrator
│
├── models/
│   ├── __init__.py
│   ├── request.py          # Pydantic request models with validation
│   ├── response.py         # Pydantic response models
│   └── domain.py           # Domain entity models
│
├── rag/
│   ├── __init__.py
│   └── retriever.py        # RAG with Azure AI Search
│
├── utils/
│   ├── __init__.py
│   ├── doc_utils.py        # Document processing utilities
│   └── chat_history.py     # Chat history management
│
├── tests/
│   ├── unit/               # Unit tests
│   └── integration/        # Integration tests
│       ├── test_financial_agent.py
│       └── test_law_agent.py
│
├── main.py                 # Application entry point
├── requirements.txt        # Python dependencies
└── README.md              # Project documentation
```

## Key Components

### API (`api/server.py`)
- Flask application with CORS support and Pydantic validation
- REST endpoints with type-safe request/response models
- Structured error responses with error codes (VALIDATION_ERROR, CLIENT_ERROR, GUARDRAIL_REJECTED, etc.)
- File upload handling with persistent storage
- Session-based conversation management

**Main Routes:**
- `POST /api/query` - Submit a query (validates QueryRequest, returns QueryResponse/ErrorResponse)
- `POST /api/sessions` - Create a new session (validates CreateSessionRequest, returns SessionResponse)
- `GET /api/sessions` - List all sessions (returns SessionsListResponse)
- `POST /api/sessions/<id>/clear` - Clear session messages (returns SuccessResponse/ErrorResponse)
- `GET /api/sessions/<id>/messages` - Get session messages (returns MessagesResponse)

### Configuration (`config/`)
- **env.py**: Environment variables (Azure credentials, API keys)
- **sql.py**: PostgreSQL database operations for session and message persistence
- **llm.py**: Azure OpenAI LLM initialization

### Agents (`agents/`)
- **orchestrator.py**: `OrchestratorAgent` and `VoiceOrchestratorAgent` - Main conversation orchestrators
- **guardrail.py**: `GuardrailAgent` - Validates user queries for content policy
- **financial_agent.py**: `FinancialAgent` - Financial domain specialist with RAG integration
- **legal_agent.py**: `LegalAgent` - Legal domain specialist with RAG integration
- **azure_client.py**: `AzureOpenAIClient` - Azure OpenAI compatibility wrapper
- **Specialized agents**: Employee, executive, all_users, and client specific agents

### Graph (`graph/`)
- **workflow.py**: `LangGraphAssistant` - Main LangGraph-based orchestrator with:
  - **Tool Node**: Extracts text from PDFs, images (OCR), and Word documents
  - **Orchestrator Node**: Routes queries or answers directly from documents
  - **Specialist Node**: Uses FinancialAgent or LegalAgent with RAG for domain-specific knowledge
  - **Final Redactor Node**: Refines specialist responses for user presentation

### Models (`models/`)
- **request.py**: Pydantic request validation models
  - `QueryRequest`: Validates query (1-10000 chars), voice_mode (bool conversion), session_id (UUID)
  - `CreateSessionRequest`: Validates optional session name (max 200 chars)
- **response.py**: Pydantic response models for all endpoints
  - `QueryResponse`, `ErrorResponse`, `SessionResponse`, `SessionsListResponse`, `MessagesResponse`, `SuccessResponse`
- **domain.py**: Domain entity models (Message, Session, DocumentMetadata) with ORM compatibility

### Tests (`tests/`)
- **integration/**: End-to-end tests for agents and workflows
  - `test_financial_agent.py`: Financial agent integration tests
  - `test_law_agent.py`: Legal agent integration tests
- **unit/**: Unit tests for individual components (to be expanded)

### Utilities (`utils/`)
- **doc_utils.py**: Document processing (text extraction, hidden tag management)
- **chat_history.py**: Session conversation history management

### RAG (`rag/`)
- **retriever.py**: Azure Cognitive Search integration for document retrieval

## Workflow Flow

```
User Query
    ↓
Tool Node (Extract document text)
    ↓
Orchestrator Node (Route or answer directly)
    ├─→ Has Answer? → End
    └─→ Need Specialist? → Continue
    ↓
Specialist Node (RAG lookup + analysis)
    ↓
Final Redactor Node (Polish response)
    ↓
Return Response
```

## Running the Application

```bash
# Set environment variables
export AZURE_OPENAI_KEY="..."
export AZURE_OPENAI_ENDPOINT="..."
export AZURE_SEARCH_KEY="..."
export AZURE_SEARCH_ENDPOINT="..."

# Install dependencies
pip install -r requirements.txt

# Run the server
python main.py
```

## Environment Variables

Required:
- `AZURE_OPENAI_KEY` - Azure OpenAI API key
- `AZURE_OPENAI_ENDPOINT` - Azure OpenAI endpoint URL
- `AZURE_OPENAI_DEPLOYMENT` - Azure OpenAI deployment name (e.g., gpt-5-mini)
- `AZURE_SEARCH_KEY` - Azure AI Search API key
- `AZURE_SEARCH_ENDPOINT` - Azure AI Search endpoint URL
- `AZURE_DOC_INTELLIGENCE_KEY` - Azure Document Intelligence API key
- `AZURE_DOC_INTELLIGENCE_ENDPOINT` - Azure Document Intelligence endpoint URL

Optional:
- `DEBUG` - Enable debug mode (default: False)
- `HOST` - Server host (default: 0.0.0.0)
- `PORT` - Server port (default: 5100)

## Data Persistence

- **Sessions**: PostgreSQL database (`chat_sessions` / `chat_messages`)
- **Messages**: Stored with timestamps and roles (user/assistant/system)
- **Uploads**: Stored in `uploads/{session_id}/` directory
- **Hidden Document Memory**: Invisible tags preserve document context across turns

## Version
1.0.0
