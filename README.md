# NOVA Assistant — Backend

Este backend gestiona los agentes (Guardrail y Orquestador), el procesamiento de documentos, la persistencia de sesiones y la integración con Azure OpenAI.

Resumen
- Lenguaje: Python 3.x
- Framework: Flask (endpoints REST) con validación Pydantic
- Persistencia: PostgreSQL (mensajes y sesiones)
- Soporte de archivos: PDFs, Word (.docx), imágenes (OCR con Tesseract + fallback Azure Vision)
- Cliente de modelo: Azure OpenAI (cliente compatible con la versión 1.x del SDK)
- Validación: Pydantic models para request/response type safety

Qué hace
- `GuardrailAgent`: valida la intención al inicio de una sesión (solo consultas financieras o legales) y bloquea/acepta solicitudes fuera de alcance.
- `FinancialAgent` y `LegalAgent`: agentes especializados con RAG para dominios financiero y legal respectivamente.
- `OrchestratorAgent`: extrae texto de archivos (PyPDF2, python-docx, OCR con Pillow + pytesseract), construye el prompt con el historial de la sesión y consulta el modelo desplegado en Azure.
- LangGraph Workflow: orquesta el flujo entre tools, orchestrator, specialists y redactor final.
- Endpoints REST: crear/listar/limpiar sesiones, enviar consultas (`/api/query`) y obtener mensajes de sesión, todos con validación Pydantic.

Variables de entorno obligatorias
- `AZURE_OPENAI_KEY` o `AZURE_OPENAI_API_KEY` — clave API de Azure OpenAI.
- `AZURE_OPENAI_ENDPOINT` — endpoint del servicio Azure OpenAI (por ejemplo: `https://mi-recurso.openai.azure.com`).
- `AZURE_OPENAI_DEPLOYMENT` — nombre del deployment (p. ej. `gpt-5-mini` o el nombre que hayas creado en Azure).
- `AZURE_SEARCH_ENDPOINT` — endpoint del servicio Azure AI Search.
- `AZURE_SEARCH_KEY` o `AZURE_SEARCH_API_KEY` — clave API de Azure AI Search.
- `DATABASE_URL` — cadena de conexión PostgreSQL (ejemplo: `postgresql://user:pass@host:5432/dbname?sslmode=require`).

Variables de entorno opcionales
- `AZURE_SPEECH_KEY` - Azure Speech API key for TTS
- `AZURE_SPEECH_REGION` - Azure Speech region
- `AZURE_SPEECH_VOICE` - Voice name (default: es-ES-AlvaroNeural)
- `AZURE_VISION_ENDPOINT` - Azure Vision OCR endpoint
- `AZURE_VISION_KEY` - Azure Vision OCR key
- `FRONTEND_ORIGIN` - CORS origin for the frontend
- `INIT_DB_TOKEN` - Token for `/admin/init-db`

Requisitos del sistema
- Python 3.10+ (recomendado)
- Tesseract OCR instalado en la máquina (si quieres extraer texto de imágenes). En macOS:

```bash
brew install tesseract
```

En Debian/Ubuntu:

```bash
sudo apt update && sudo apt install -y tesseract-ocr
```

Nota: `pytesseract` (Python) requiere que el binario `tesseract` esté en el `PATH`.

Instalación y ejecución local

```bash
# desde la raíz del repo
cd backend
# crear y activar entorno virtual
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# exportar variables de entorno necesarias (macOS/linux)
export AZURE_OPENAI_KEY="<tu_azure_key>"
export AZURE_OPENAI_ENDPOINT="https://<tu_resource>.openai.azure.com"
export AZURE_OPENAI_DEPLOYMENT="<tu_deployment_name>"
export DATABASE_URL="postgresql://user:pass@host:5432/dbname?sslmode=require"

# ejecutar el servidor Flask desde /backend
python main.py 

# por defecto el backend corre en http://localhost:5100
```

**⚠️ Nota importante sobre acceso a la base de datos**

Si estás ejecutando el código en local y la base de datos PostgreSQL está alojada en Azure, debes configurar el acceso de red:

1. Accede al recurso de PostgreSQL en el portal de Azure
2. Ve a la sección de **Networking** o **Firewalls and virtual networks**
3. Añade tu IP pública actual a la lista de direcciones IP permitidas

Para obtener tu IP pública, puedes ejecutar:

```bash
curl ifconfig.me
```

Sin este paso, la conexión a la base de datos será rechazada por el firewall de Azure.

Probar la demo (flujo backend + frontend)

1) Levantar el backend (ver arriba).

2) Levantar el frontend (desde la carpeta `frontend`) apuntando al backend:

```bash
cd ../frontend
npm install
VITE_API_URL="http://localhost:5100" npm run dev
```

3) Crear una sesión desde la CLI o dejar que el frontend la cree automáticamente. Ejemplo con `curl`:

```bash
API="http://localhost:5100"
# crear sesión
curl -s -X POST "$API/api/sessions" | jq

# respuesta: { "session_id": "<SESSION_ID>", "message": "..." }
```

4) Enviar una consulta con un archivo adjunto (ejemplo PDF):

```bash
SID=<SESSION_ID>
curl -X POST "$API/api/query" \
   -F "session_id=$SID" \
   -F "query=Analiza este contrato y resume obligaciones clave" \
   -F "files=@/ruta/a/ejemplo.pdf"
```

5) Consultar el historial de mensajes de la sesión:

```bash
curl "$API/api/sessions/$SID/messages" | jq
```

Puntos importantes sobre el comportamiento
- La primera interacción de una sesión pasa por el `GuardrailAgent`. Se espera que el usuario responda si la sesión será de tipo `financial` o `legal` (o escribir directamente la consulta si ya es del dominio correcto). Si la intención está fuera de alcance, la petición será rechazada.
- Los archivos PDF/Word son procesados por extractores (`PyPDF2`, `python-docx`). Las imágenes usan OCR (`pytesseract`) para extraer texto y evitar enviar imágenes en base64 al modelo.
- Las conversaciones se guardan en PostgreSQL; el endpoint `/api/sessions` lista sesiones y `/api/sessions/<id>/messages` devuelve el historial.
- Puedes eliminar sesiones con `DELETE /api/sessions/<id>` o borrar todo el historial con `DELETE /api/sessions`.
- Para voz, `POST /api/tts` devuelve audio MP3 (usa Azure Speech).

Endpoints principales
Todos los endpoints usan validación Pydantic y devuelven respuestas tipadas con códigos de error estructurados:

- `POST /api/sessions` — crea una nueva sesión; devuelve `SessionResponse` con `session_id`.
- `GET /api/sessions` — lista sesiones disponibles; devuelve `SessionsListResponse` con metadatos.
- `POST /api/query` — envía una consulta; valida `QueryRequest` (query, voice_mode, session_id) y devuelve `QueryResponse` o `ErrorResponse` con códigos como `VALIDATION_ERROR`, `GUARDRAIL_REJECTED`, `CLIENT_ERROR`.
- `GET /api/sessions/<id>/messages` — devuelve `MessagesResponse` con mensajes recientes tipados.
- `POST /api/sessions/<id>/clear` — limpia los mensajes; devuelve `SuccessResponse` o `ErrorResponse(404)`.
- `DELETE /api/sessions/<id>` — elimina la sesión y sus mensajes.
- `DELETE /api/sessions` — elimina todas las sesiones y mensajes.
- `POST /api/tts` — sintetiza voz (audio MP3).
- `GET /health` y `GET /health/db` — health checks.

Depuración y pruebas rápidas
- Si obtienes errores de OCR, verifica que `tesseract` esté instalado y accesible desde la terminal (`tesseract --version`).
- Para OCR en producción sin binario, configura `AZURE_VISION_ENDPOINT` y `AZURE_VISION_KEY`.
- Si la llamada al modelo falla, revisa las variables de entorno y que el `AZURE_OPENAI_DEPLOYMENT` exista en tu recurso Azure.
- Para ver los archivos subidos revisa el directorio `backend/uploads/<session_id>/`.

Estructura del proyecto
Para detalles completos de la arquitectura, consulta `STRUCTURE.md`.

Carpetas principales:
- `agents/` — GuardrailAgent, FinancialAgent, LegalAgent, y agentes especializados por roles
- `api/` — Flask server con endpoints validados por Pydantic
- `config/` — Configuración centralizada (env, llm, sql)
- `graph/` — LangGraph workflow orchestration
- `models/` — Pydantic schemas para request/response validation
- `rag/` — RAG retriever con Azure AI Search
- `tests/` — Tests unitarios e integración
- `utils/` — Utilidades de documentos y chat history

Recomendaciones para producción
- Configurar CORS de forma segura y usar HTTPS.
- Guardar las claves de Azure en un servicio de secrets (KeyVault) y no en variables de entorno en texto plano.
- Añadir resumidores automáticos para truncar historial antes de llamar al modelo cuando la conversación sea muy larga.
- Los modelos Pydantic ya proveen validación automática; considera agregar rate limiting y autenticación.

¿Qué sigue?
- Añadir un README de despliegue para Azure (deployment de la API, contenedores) o generar ejemplos Postman/Insomnia si quieres. Indícame qué prefieres.