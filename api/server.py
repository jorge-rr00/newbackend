import os
import re
import uuid
import shutil
from flask import Flask, request, jsonify, Response
from flask_cors import CORS
from pydantic import ValidationError
from werkzeug.security import generate_password_hash, check_password_hash

from agents.orchestrator import OrchestratorAgent, VoiceOrchestratorAgent
from agents.guardrail import GuardrailAgent
from agents.azure_client import AzureOpenAIClient
from config.sql import (
    init_db,
    create_user,
    get_user_by_username,
    get_user_by_token,
    create_auth_token,
    revoke_auth_token,
    create_session,
    session_exists,
    add_message,
    get_recent_messages,
    clear_session,
    list_sessions,
    delete_session,
    delete_all_sessions,
)
from utils.doc_utils import strip_hidden_doc_tags

from models.request import QueryRequest, CreateSessionRequest, LoginRequest, RegisterRequest
from models.response import (
    QueryResponse,
    ErrorResponse,
    SessionResponse,
    SessionsListResponse,
    MessagesResponse,
    SuccessResponse,
    AuthResponse,
    SessionInfo,
    MessageInfo,
)

UPLOADS_DIR = os.path.join(os.path.dirname(__file__), "..", "uploads")
os.makedirs(UPLOADS_DIR, exist_ok=True)

app = Flask(__name__)
frontend_origin = os.getenv("FRONTEND_ORIGIN", "*")
CORS(app, resources={r"/api/*": {"origins": frontend_origin}, r"/health/*": {"origins": frontend_origin}})

_db_ready = False


def _ensure_db_ready():
    global _db_ready
    if _db_ready:
        return
    try:
        init_db()
        _db_ready = True
    except Exception as e:
        print(f"DB init failed: {e}")


_ensure_db_ready()

USERNAME_RE = re.compile(r"^[A-Za-z0-9]+$")


def _get_auth_token() -> str:
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        return auth.split(" ", 1)[1].strip()
    return ""


def _get_authenticated_user():
    token = _get_auth_token()
    if not token:
        return None
    return get_user_by_token(token)


def _format_validation_error(err: ValidationError) -> str:
    try:
        details = err.errors() or []
    except Exception:
        details = []
    if not details:
        return "Datos invalidos"
    first = details[0]
    loc = ".".join(str(item) for item in first.get("loc", []) if item != "__root__")
    msg = first.get("msg", "Datos invalidos")
    return f"{loc}: {msg}" if loc else msg


def _require_user():
    user = _get_authenticated_user()
    if not user:
        error_resp = ErrorResponse(
            error="unauthorized",
            code="UNAUTHORIZED"
        )
        return None, (jsonify(error_resp.dict()), 401)
    return user, None


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/health/db")
def health_db():
    try:
        import psycopg2

        dsn = os.getenv("DATABASE_URL")
        if not dsn:
            return jsonify({"ok": False, "error": "DATABASE_URL missing"}), 500
        conn = psycopg2.connect(dsn)
        with conn.cursor() as cur:
            cur.execute("SELECT current_user, current_database();")
            user, dbname = cur.fetchone()
        conn.close()
        return jsonify({"ok": True, "current_user": user, "database": dbname})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.post("/admin/init-db")
def admin_init_db():
    token = os.getenv("INIT_DB_TOKEN", "")
    sent = request.headers.get("x-init-token", "")
    if token and sent != token:
        return jsonify({"ok": False, "error": "unauthorized"}), 401

    try:
        init_db()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.post("/api/auth/register")
def register_user():
    try:
        data = request.get_json(silent=True) or {}
        req = RegisterRequest(
            username=data.get("username"),
            password=data.get("password"),
            password_confirm=data.get("password_confirm"),
        )
    except ValidationError as e:
        error_resp = ErrorResponse(
            error=_format_validation_error(e),
            code="VALIDATION_ERROR"
        )
        return jsonify(error_resp.dict()), 400

    username = req.username.strip()
    if not USERNAME_RE.match(username):
        error_resp = ErrorResponse(
            error="Nombre de usuario no válido",
            code="INVALID_USERNAME"
        )
        return jsonify(error_resp.dict()), 400

    if req.password != req.password_confirm:
        error_resp = ErrorResponse(
            error="Las contraseñas no coinciden",
            code="PASSWORD_MISMATCH"
        )
        return jsonify(error_resp.dict()), 400

    if get_user_by_username(username):
        error_resp = ErrorResponse(
            error="Usuario ya registrado",
            code="USER_EXISTS"
        )
        return jsonify(error_resp.dict()), 409

    password_hash = generate_password_hash(req.password)
    user_id = create_user(username, password_hash)
    token = create_auth_token(user_id)

    response = AuthResponse(token=token, username=username)
    return jsonify(response.dict())


@app.post("/api/auth/login")
def login_user():
    try:
        data = request.get_json(silent=True) or {}
        req = LoginRequest(
            username=data.get("username"),
            password=data.get("password"),
        )
    except ValidationError as e:
        error_resp = ErrorResponse(
            error=_format_validation_error(e),
            code="VALIDATION_ERROR"
        )
        return jsonify(error_resp.dict()), 400

    username = req.username.strip()
    user = get_user_by_username(username)
    if not user:
        error_resp = ErrorResponse(
            error="Usuario no encontrado",
            code="USER_NOT_FOUND"
        )
        return jsonify(error_resp.dict()), 404

    if not check_password_hash(user.get("password_hash", ""), req.password):
        error_resp = ErrorResponse(
            error="Contraseña incorrecta",
            code="INVALID_PASSWORD"
        )
        return jsonify(error_resp.dict()), 401

    token = create_auth_token(user["id"])
    response = AuthResponse(token=token, username=user["username"])
    return jsonify(response.dict())


@app.get("/api/auth/me")
def auth_me():
    user, error = _require_user()
    if error:
        return error
    response = AuthResponse(token=_get_auth_token(), username=user["username"])
    return jsonify(response.dict())


@app.post("/api/auth/logout")
def auth_logout():
    token = _get_auth_token()
    if token:
        revoke_auth_token(token)
    response = SuccessResponse(message="Sesión cerrada")
    return jsonify(response.dict())


def save_uploads(files, session_id: str) -> list:
    """Save uploaded files into uploads/{session_id}/ and return stored paths."""
    out_dir = os.path.join(UPLOADS_DIR, session_id)
    os.makedirs(out_dir, exist_ok=True)
    stored_paths = []
    for f in files:
        orig = f.filename or "upload"
        suffix = os.path.splitext(orig)[1]
        stored_name = f"{uuid.uuid4().hex}{suffix}"
        path = os.path.join(out_dir, stored_name)
        with open(path, "wb") as out:
            out.write(f.read())
        stored_paths.append(path)
    return stored_paths


@app.route("/api/query", methods=["POST"])
def handle_query():
    """Handle user queries with optional file uploads."""
    user, error = _require_user()
    if error:
        return error
    # Validate request with Pydantic
    try:
        req = QueryRequest(
            query=request.form.get("query", ""),
            voice_mode=request.form.get("voice_mode", "false"),
            session_id=request.form.get("session_id")
        )
    except ValidationError as e:
        error_resp = ErrorResponse(
            error="Invalid request data",
            code="VALIDATION_ERROR"
        )
        return jsonify(error_resp.dict()), 400
    
    uploaded = request.files.getlist("files") or []
    
    # Generate session_id if not provided
    session_id = req.session_id or uuid.uuid4().hex

    if req.session_id and session_exists(req.session_id) and not session_exists(req.session_id, user["id"]):
        error_resp = ErrorResponse(
            error="Session not found",
            code="SESSION_NOT_FOUND"
        )
        return jsonify(error_resp.dict()), 404

    # ensure session exists
    create_session(user["id"], session_id)

    filenames = [f.filename for f in uploaded]

    try:
        client = AzureOpenAIClient()
    except Exception as e:
        error_resp = ErrorResponse(
            error=f"Azure client setup error: {str(e)}",
            code="CLIENT_ERROR"
        )
        return jsonify(error_resp.dict()), 500

    # Guardrail only on first message
    guard = GuardrailAgent(client=client)
    recent_one = get_recent_messages(session_id, limit=1, user_id=user["id"])
    is_first_message = len(recent_one) == 0

    # Check if this is the first message and user is declaring intent
    if is_first_message:
        valid, reason = guard.validate(req.query, filenames)
        if not valid:
            error_resp = ErrorResponse(
                error=reason or "Query rejected by guardrail",
                code="GUARDRAIL_REJECTED",
                rejected=True,
                reason=reason
            )
            return jsonify(error_resp.dict()), 400

        qnorm = req.query.strip().lower()
        if qnorm in ("financiera", "legal"):
            # persist intent
            add_message(session_id, "user", req.query)
            add_message(session_id, "system", f"intent:{qnorm}")
            confirm = f"Intento registrado: '{qnorm}'. Ahora puedes enviar tu consulta o adjuntar archivos."
            response = QueryResponse(
                reply=confirm,
                session_id=session_id,
                voice_mode=req.voice_mode
            )
            return jsonify(response.dict())

    filepaths = save_uploads(uploaded, session_id)

    try:
        orch = VoiceOrchestratorAgent(client) if req.voice_mode else OrchestratorAgent(client)

        # fetch recent messages for context
        recent = get_recent_messages(session_id, limit=50, user_id=user["id"])
        session_history = [{"role": r["role"], "content": r["content"]} for r in recent]

        reply_with_tags = orch.respond(req.query, filepaths, session_history=session_history)

        # IMPORTANT: return clean reply to user, but persist full reply for memory
        reply_clean = strip_hidden_doc_tags(reply_with_tags)

    except Exception as e:
        error_resp = ErrorResponse(
            error=f"Processing error: {str(e)}",
            code="PROCESSING_ERROR"
        )
        return jsonify(error_resp.dict()), 500
    finally:
        # files are intentionally kept in uploads/{session_id}/ for later retrieval
        pass

    # persist messages
    add_message(session_id, "user", req.query)
    add_message(session_id, "assistant", reply_with_tags)

    response = QueryResponse(
        reply=reply_clean,
        session_id=session_id,
        voice_mode=req.voice_mode
    )
    return jsonify(response.dict())


@app.route("/api/sessions", methods=["POST"])
def create_session_endpoint():
    """Create a new session."""
    user, error = _require_user()
    if error:
        return error
    # Validate request with Pydantic (optional name)
    try:
        # Handle both JSON body and empty requests
        req_data = request.get_json(silent=True) or {}
        req = CreateSessionRequest(
            name=req_data.get("name")
        )
    except ValidationError as e:
        error_resp = ErrorResponse(
            error="Invalid request data",
            code="VALIDATION_ERROR"
        )
        return jsonify(error_resp.dict()), 400
    
    sid = create_session(user["id"])
    welcome = "Bienvenido. Por favor indica junto a tu mensaje si tu consulta será 'financiera' o 'legal'."
    
    response = SessionResponse(
        session_id=sid,
        welcome=welcome
    )
    return jsonify(response.dict())


@app.route("/api/sessions", methods=["GET"])
def list_sessions_endpoint():
    """List all sessions."""
    user, error = _require_user()
    if error:
        return error

    lst = list_sessions(user["id"])

    def to_iso(value):
        if hasattr(value, "isoformat"):
            return value.isoformat()
        return value
    
    # Convert to Pydantic models
    sessions = [
        SessionInfo(
            id=s.get("id") or s.get("session_id", ""),
            session_id=s.get("id") or s.get("session_id", ""),
            created_at=to_iso(s.get("created_at")),
            message_count=s.get("message_count")
        )
        for s in lst
    ]
    
    response = SessionsListResponse(sessions=sessions)
    return jsonify(response.dict())


@app.route("/api/sessions/<session_id>/clear", methods=["POST"])
def clear_session_endpoint(session_id):
    """Clear messages from a session."""
    user, error = _require_user()
    if error:
        return error

    if not session_exists(session_id, user["id"]):
        error_resp = ErrorResponse(
            error="Session not found",
            code="SESSION_NOT_FOUND"
        )
        return jsonify(error_resp.dict()), 404
    
    clear_session(session_id, user["id"])
    response = SuccessResponse(message="Session cleared successfully")
    return jsonify(response.dict())


@app.route("/api/sessions", methods=["DELETE"])
def delete_all_sessions_endpoint():
    user, error = _require_user()
    if error:
        return error

    current_sessions = list_sessions(user["id"])
    delete_all_sessions(user["id"])

    if os.path.isdir(UPLOADS_DIR):
        for s in current_sessions:
            session_dir = os.path.join(UPLOADS_DIR, s.get("id", ""))
            if os.path.isdir(session_dir):
                try:
                    shutil.rmtree(session_dir)
                except Exception:
                    pass
        os.makedirs(UPLOADS_DIR, exist_ok=True)

    response = SuccessResponse(message="All sessions deleted")
    return jsonify(response.dict())


@app.route("/api/sessions/<session_id>", methods=["DELETE"])
def delete_session_endpoint(session_id):
    user, error = _require_user()
    if error:
        return error

    if not session_exists(session_id, user["id"]):
        error_resp = ErrorResponse(
            error="Session not found",
            code="SESSION_NOT_FOUND"
        )
        return jsonify(error_resp.dict()), 404

    delete_session(session_id, user["id"])

    session_dir = os.path.join(UPLOADS_DIR, session_id)
    if os.path.isdir(session_dir):
        try:
            shutil.rmtree(session_dir)
        except Exception:
            pass

    response = SuccessResponse(message="Session deleted successfully")
    return jsonify(response.dict())


@app.route("/api/sessions/<session_id>/messages", methods=["GET"])
def get_session_messages_endpoint(session_id):
    """Get messages from a session."""
    user, error = _require_user()
    if error:
        return error

    if not session_exists(session_id, user["id"]):
        error_resp = ErrorResponse(
            error="Session not found",
            code="SESSION_NOT_FOUND"
        )
        return jsonify(error_resp.dict()), 404
    
    limit = int(request.args.get("limit", 200))
    msgs = get_recent_messages(session_id, limit=limit, user_id=user["id"])

    # Convert to Pydantic models and optionally hide tags
    messages = []
    for m in msgs:
        content = m.get("content", "")
        if m.get("role") == "assistant":
            content = strip_hidden_doc_tags(content)

        created_at = m.get("created_at")
        if hasattr(created_at, "isoformat"):
            created_at = created_at.isoformat()
        
        messages.append(
            MessageInfo(
                id=m.get("id", 0),
                role=m.get("role", "user"),
                content=content,
                timestamp=created_at
            )
        )
    
    response = MessagesResponse(messages=messages)
    return jsonify(response.dict())


@app.route("/api/tts", methods=["POST"])
def tts():
    user, error = _require_user()
    if error:
        return error
    data = request.get_json(silent=True) or {}
    text = (data.get("text") or "").strip()
    if not text:
        return jsonify({"ok": False, "error": "text required"}), 400

    if len(text) > 4000:
        text = text[:4000]

    key = os.getenv("AZURE_SPEECH_KEY")
    region = os.getenv("AZURE_SPEECH_REGION")
    if not key or not region:
        return jsonify({"ok": False, "error": "AZURE_SPEECH_KEY/REGION missing"}), 500

    try:
        import azure.cognitiveservices.speech as speechsdk

        speech_config = speechsdk.SpeechConfig(subscription=key, region=region)
        voice = os.getenv("AZURE_SPEECH_VOICE", "es-ES-AlvaroNeural")
        speech_config.speech_synthesis_voice_name = voice
        speech_config.set_speech_synthesis_output_format(
            speechsdk.SpeechSynthesisOutputFormat.Audio24Khz48KBitRateMonoMp3
        )

        synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=None)
        result = synthesizer.speak_text_async(text).get()

        if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
            audio_data = result.audio_data
            return Response(audio_data, mimetype="audio/mpeg", headers={"Cache-Control": "no-store"})

        if result.reason == speechsdk.ResultReason.Canceled:
            details = result.cancellation_details
            return jsonify({"ok": False, "error": details.error_details or "tts_canceled"}), 500

        return jsonify({"ok": False, "error": "tts_failed"}), 500
    except Exception as e:
        return jsonify({"ok": False, "error": f"tts_failed: {str(e)}"}), 500
