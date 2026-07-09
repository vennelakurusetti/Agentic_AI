"""
app.py - Streamlit UI for the College FAQ Chatbot.
Modern chat interface with sidebar configuration, streaming responses, and debug mode.
"""

import os
import time
import json
from pathlib import Path
from typing import Dict, Any, List, Optional

import streamlit as st
from dotenv import load_dotenv

import config
from rag import answer_question, get_vector_store, retrieve_chunks
from ingest import get_chunk_count
from intent_classifier import handle_intent, INTENT_COLLEGE_QUERY
from utils import logger, Timer

# ── Memory subsystem ──────────────────────────────────────
from memory.memory_manager import (
    process_and_store_memories,
    retrieve_user_context,
    clear_user_data,
    run_cleanup,
    get_stats,
    get_session_id,
)
from memory.memory_bootstrapper import (
    bootstrap_memories_from_history,
    append_to_chat_history,
    load_chat_history,
)

# ── Observability & Governance ────────────────────────────
from observability.llm_logger import log_llm_call, read_logs
from observability.session_stats import compute_session_stats, render_stats_html
from observability.threshold_alerts import (
    validate_input_length,
    check_all_alerts,
)
from observability.ab_testing import get_prompt_version, log_ab_result
from observability.log_analyzer import analyze_logs
from governance.safety_scanner import run_full_scan
from governance.report import generate_report

# Page configuration
st.set_page_config(
    page_title="BVRIT Hyderabad - College FAQ Chatbot",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS - Beautiful modern design
st.markdown(
    """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    
    * { font-family: 'Inter', sans-serif; }
    
    /* Main app background with gradient */
    .stApp {
        background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%) !important;
    }
    
    /* Main header with gradient */
    .main-header {
        text-align: center;
        padding: 1.5rem 0;
        background: linear-gradient(135deg, #1a237e 0%, #283593 50%, #3949ab 100%);
        border-radius: 16px;
        margin-bottom: 1.5rem;
        box-shadow: 0 8px 32px rgba(26, 35, 126, 0.25);
    }
    .main-header h1 {
        color: #ffffff !important;
        font-size: 2rem;
        margin: 0;
        font-weight: 700;
        text-shadow: 0 2px 4px rgba(0,0,0,0.2);
    }
    .main-header p {
        color: #e8eaf6 !important;
        font-size: 0.95rem;
        margin: 0.3rem 0 0 0;
        font-weight: 300;
    }

    /* Chat message containers */
    .chat-message {
        padding: 1rem 1.2rem;
        border-radius: 12px;
        margin-bottom: 0.8rem;
        box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        line-height: 1.6;
    }
    
    /* User message - blue */
    .user-message {
        background: linear-gradient(135deg, #e3f2fd 0%, #bbdefb 100%);
        border-left: 4px solid #1565c0;
        color: #1a1a1a !important;
        max-width: 85%;
    }
    .user-message strong {
        color: #1565c0 !important;
    }
    
    /* Assistant message - green */
    .assistant-message {
        background: linear-gradient(135deg, #ffffff 0%, #f1f8e9 100%);
        border-left: 4px solid #2e7d32;
        color: #1a1a1a !important;
        max-width: 85%;
    }
    .assistant-message strong {
        color: #2e7d32 !important;
    }

    /* Unknown answer - amber warning */
    .unknown-message {
        background: linear-gradient(135deg, #fff8e1 0%, #ffecb3 100%);
        border-left: 4px solid #f57f17;
        padding: 1rem 1.2rem;
        border-radius: 12px;
        margin-bottom: 0.8rem;
        color: #1a1a1a !important;
        box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        max-width: 85%;
    }
    .unknown-message strong {
        color: #e65100 !important;
    }

    /* Citation badges */
    .citation {
        display: inline-block;
        background: linear-gradient(135deg, #e8eaf6 0%, #c5cae9 100%);
        color: #283593 !important;
        padding: 0.15rem 0.6rem;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 600;
        margin: 0.15rem;
        border: 1px solid #9fa8da;
    }

    /* Buttons */
    .stButton button {
        width: 100%;
        border-radius: 8px !important;
        font-weight: 500 !important;
        transition: all 0.3s ease !important;
    }
    .stButton button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    }

    /* Sidebar styling */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #1a237e 0%, #283593 40%, #1a237e 100%);
    }
    section[data-testid="stSidebar"] .stMarkdown p,
    section[data-testid="stSidebar"] .stMarkdown span,
    section[data-testid="stSidebar"] .stMarkdown h1,
    section[data-testid="stSidebar"] .stMarkdown h2,
    section[data-testid="stSidebar"] .stMarkdown h3,
    section[data-testid="stSidebar"] .stMarkdown h4,
    section[data-testid="stSidebar"] .st-bb {
        color: #ffffff !important;
    }
    section[data-testid="stSidebar"] label {
        color: #e8eaf6 !important;
    }
    
    /* Sidebar status boxes */
    .sidebar-status {
        padding: 0.6rem 0.8rem;
        border-radius: 8px;
        margin-bottom: 0.6rem;
        font-size: 0.85rem;
    }
    .status-ok {
        background: linear-gradient(135deg, #1b5e20 0%, #2e7d32 100%);
        color: #ffffff !important;
        border: 1px solid #4caf50;
    }
    .status-warn {
        background: linear-gradient(135deg, #e65100 0%, #ef6c00 100%);
        color: #ffffff !important;
        border: 1px solid #ff9800;
    }
    .status-error {
        background: linear-gradient(135deg, #b71c1c 0%, #c62828 100%);
        color: #ffffff !important;
        border: 1px solid #ef5350;
    }
    .status-ok small, .status-warn small, .status-error small {
        color: rgba(255,255,255,0.85) !important;
    }

    /* Sidebar slider */
    .stSlider label {
        color: #ffffff !important;
    }
    .stSlider div[data-testid="stTickBar"] {
        color: #e8eaf6 !important;
    }

    /* Sidebar toggle */
    .stToggle label {
        color: #ffffff !important;
    }

    /* Clear chat button area */
    .clear-btn button {
        background: linear-gradient(135deg, #e53935 0%, #d32f2f 100%) !important;
        color: white !important;
        border: none !important;
        box-shadow: 0 4px 12px rgba(211, 47, 47, 0.3);
    }

    /* Chat input */
    .stChatInputContainer {
        border-radius: 12px !important;
        border: 2px solid #c5cae9 !important;
        background: white !important;
        box-shadow: 0 4px 16px rgba(0,0,0,0.06);
    }
    .stChatInputContainer input {
        color: #1a1a1a !important;
    }
    .stChatInputContainer:focus-within {
        border-color: #3949ab !important;
        box-shadow: 0 4px 20px rgba(57, 73, 171, 0.15);
    }

    /* Captions */
    .stCaption {
        color: #666 !important;
        font-size: 0.8rem;
    }

    /* Sidebar example buttons */
    section[data-testid="stSidebar"] .stButton button {
        background: rgba(255,255,255,0.1) !important;
        color: #e8eaf6 !important;
        border: 1px solid rgba(255,255,255,0.2) !important;
        font-size: 0.8rem !important;
        padding: 0.4rem 0.6rem !important;
    }
    section[data-testid="stSidebar"] .stButton button:hover {
        background: rgba(255,255,255,0.2) !important;
        border-color: rgba(255,255,255,0.4) !important;
    }

    /* Sidebar divider */
    section[data-testid="stSidebar"] hr {
        border-color: rgba(255,255,255,0.2);
    }

    /* Debug expander */
    .streamlit-expanderHeader {
        color: #3949ab !important;
        font-weight: 500 !important;
    }

    /* Download/copy buttons in citations */
    .source-label {
        color: #666 !important;
        font-size: 0.85rem;
        margin-top: 0.3rem;
    }
</style>
""",
    unsafe_allow_html=True,
)


def initialize_session_state() -> None:
    """Initialize Streamlit session state variables."""
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "vector_store_ready" not in st.session_state:
        st.session_state.vector_store_ready = False
    if "chunk_count" not in st.session_state:
        st.session_state.chunk_count = 0
    if "debug_mode" not in st.session_state:
        st.session_state.debug_mode = False
    if "top_k" not in st.session_state:
        st.session_state.top_k = config.TOP_K
    # ── Memory session state ──
    if "user_id" not in st.session_state:
        st.session_state.user_id = config.MEMORY_DEFAULT_USER_ID
    if "session_id" not in st.session_state:
        st.session_state.session_id = get_session_id()
    if "memory_count" not in st.session_state:
        st.session_state.memory_count = 0
    if "memory_initialized" not in st.session_state:
        st.session_state.memory_initialized = False
    # ── Bootstrapping flag (runs only once per user) ──
    if "bootstrapped" not in st.session_state:
        st.session_state.bootstrapped = False


def check_vector_store() -> bool:
    """Check if the vector store exists and is ready."""
    chroma_path = config.CHROMA_DIR
    if chroma_path.exists() and any(chroma_path.iterdir()):
        try:
            count = get_chunk_count()
            st.session_state.chunk_count = count or 0
            st.session_state.vector_store_ready = True
            return True
        except Exception as e:
            logger.warning(f"Vector store check failed: {e}")
            st.session_state.vector_store_ready = False
            return False
    st.session_state.vector_store_ready = False
    return False


def render_sidebar() -> None:
    """Render the sidebar with status and settings."""
    with st.sidebar:
        st.markdown(
            '<div style="text-align: center; padding: 0.5rem 0;">'
            '<h2 style="color: #ffffff; margin: 0; font-weight: 700;">🎓 BVRIT Hyderabad</h2>'
            '<p style="color: #e8eaf6; margin: 0; font-size: 0.85rem;">College FAQ Chatbot</p>'
            "</div>",
            unsafe_allow_html=True,
        )

        # ── Username / Identity ──
        st.markdown("#### 👤 Your Identity")
        new_user_id = st.text_input(
            "Username",
            value=st.session_state.user_id,
            placeholder="Enter your username...",
            label_visibility="collapsed",
            key="username_input",
        )
        if new_user_id and new_user_id != st.session_state.user_id:
            # User changed — reset for new user
            st.session_state.user_id = new_user_id
            st.session_state.bootstrapped = False
            st.session_state.messages = []
            st.session_state.memory_count = 0
            st.rerun()

        if st.session_state.bootstrapped:
            st.markdown(
                f'<div class="sidebar-status status-ok" style="font-size:0.8rem;">'
                f"✅ Bootstrapped<br><small>{st.session_state.memory_count} memories</small>"
                f"</div>",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                '<div class="sidebar-status status-warn" style="font-size:0.8rem;">'
                "⚠️ Not bootstrapped"
                "</div>",
                unsafe_allow_html=True,
            )

        st.markdown("---")

        # Document status
        st.markdown("#### 📄 Document Status")
        doc_exists = config.DOCX_PATH.exists()
        if doc_exists:
            doc_size = config.DOCX_PATH.stat().st_size / 1024
            st.markdown(
                '<div class="sidebar-status status-ok">'
                f"✅ Document Loaded<br><small>{config.DOCX_PATH.name} ({doc_size:.0f} KB)</small>"
                "</div>",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                '<div class="sidebar-status status-error">❌ Document Not Found</div>',
                unsafe_allow_html=True,
            )

        # Vector store status
        st.markdown("#### 🗄️ Vector Store Status")
        if st.session_state.vector_store_ready:
            st.markdown(
                '<div class="sidebar-status status-ok">'
                f"✅ Ready<br><small>{st.session_state.chunk_count} chunks indexed</small>"
                "</div>",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                '<div class="sidebar-status status-warn">⚠️ Not Initialized</div>',
                unsafe_allow_html=True,
            )
            if st.button("🔄 Initialize Vector Store"):
                with st.spinner("Running ingestion..."):
                    from ingest import ingest_document
                    try:
                        ingest_document()
                        st.session_state.vector_store_ready = True
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed to initialize: {e}")

        st.markdown("---")

        # Chunking settings
        st.markdown("#### ⚙️ Chunking Settings")
        st.markdown(f"**Size:** {config.CHUNK_SIZE} | **Overlap:** {config.CHUNK_OVERLAP}")
        st.markdown(f"**Total Chunks:** {st.session_state.chunk_count}")

        st.markdown("---")

        # Retrieval settings
        st.markdown("#### 🔍 Retrieval Settings")
        top_k = st.slider(
            "Top-K Chunks",
            min_value=1,
            max_value=10,
            value=st.session_state.top_k,
            help="Number of chunks to retrieve",
        )
        st.session_state.top_k = top_k

        # Debug mode toggle
        st.session_state.debug_mode = st.toggle(
            "🐛 Debug Mode",
            value=st.session_state.debug_mode,
            help="Show retrieved chunks in responses",
        )

        st.markdown("---")
        st.markdown("#### ❓ Try Asking")
        example_questions = [
            "What is the admission process?",
            "What departments are available?",
            "Tell me about placements",
            "What campus facilities are available?",
            "How is the research at the college?",
            "What are the fees for B.Tech?",
            "Tell me about the CSE department",
            "What student clubs are there?",
        ]
        for q in example_questions:
            if st.button(q, key=f"example_{q[:20]}", use_container_width=True):
                st.session_state.messages.append({"role": "user", "content": q})
                st.rerun()


def render_chat_message(message: Dict[str, Any]) -> None:
    """Render a single chat message with beautiful styling."""
    role = message["role"]
    content = message.get("content", "")
    extra = message.get("extra", {})

    if role == "user":
        st.markdown(
            f'<div class="chat-message user-message">'
            f"<strong>🧑 You</strong><br>{content}"
            f"</div>",
            unsafe_allow_html=True,
        )
    else:
        # Check if it's an unknown answer
        is_unknown = "not available in the uploaded knowledge base" in content.lower()

        if is_unknown:
            st.markdown(
                f'<div class="unknown-message">'
                f"<strong>🤖 Assistant</strong><br>{content}"
                f"</div>",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f'<div class="chat-message assistant-message">'
                f"<strong>🤖 Assistant</strong><br>{content}"
                f"</div>",
                unsafe_allow_html=True,
            )

        # Show citations with section names
        citations = extra.get("citations", [])
        if citations:
            citation_html = " ".join(
                f'<span class="citation">📄 {c}</span>' for c in citations
            )
            st.markdown(
                f'<div class="source-label"><strong>Sources:</strong> {citation_html}</div>',
                unsafe_allow_html=True,
            )

        # Show latency and metadata
        col1, col2, col3 = st.columns(3)
        with col1:
            latency = extra.get("latency", 0)
            st.caption(f"⏱️ Response: {latency:.2f}s")
        with col2:
            chunks_count = extra.get("chunks_retrieved", 0)
            st.caption(f"📚 Chunks: {chunks_count}")
        with col3:
            tokens = extra.get("tokens_used", 0)
            if tokens:
                st.caption(f"🔤 Tokens: {tokens}")

        # Debug mode: show retrieved chunks
        if st.session_state.debug_mode and extra.get("chunks"):
            with st.expander("🐛 Debug: Retrieved Chunks", expanded=False):
                for i, chunk in enumerate(extra["chunks"]):
                    section = chunk.metadata.get("section", "Unknown")
                    score = chunk.metadata.get("relevance_score", "N/A")
                    st.markdown(f"**Chunk {i + 1}** | Section: `{section}` | Score: `{score}`")
                    st.code(chunk.page_content[:300], language="text")
                    st.markdown("---")


def process_user_input(prompt: str) -> None:
    """Process user input and generate a response with memory integration + observability."""
    # ── Input validation ──
    validation_error = validate_input_length(prompt)
    if validation_error:
        st.session_state.messages.append({"role": "user", "content": prompt})
        st.session_state.messages.append(
            {"role": "assistant", "content": validation_error, "extra": {}}
        )
        st.rerun()
        return

    # Check for "clear my data" privacy command
    if prompt.lower().strip() in ["clear my data", "clear my memories", "forget me"]:
        deleted = clear_user_data(st.session_state.user_id)
        answer = f"✅ I've cleared {deleted} memory entries for you. I won't remember anything about our past conversations."
        st.session_state.messages.append({"role": "user", "content": prompt})
        st.session_state.messages.append(
            {"role": "assistant", "content": answer, "extra": {}}
        )
        st.session_state.memory_count = 0
        st.rerun()
        return

    # Add user message
    st.session_state.messages.append({"role": "user", "content": prompt})

    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        start_time = time.time()

        try:
            # Step 1: Classify intent
            intent, intent_response = handle_intent(prompt)

            if intent != INTENT_COLLEGE_QUERY:
                answer = intent_response
                message_placeholder.markdown(answer)
                extra = {
                    "citations": [], "chunks_retrieved": 0,
                    "latency": 0, "tokens_used": 0, "chunks": [],
                }
                st.session_state.messages.append(
                    {"role": "assistant", "content": answer, "extra": extra}
                )
                # Log non-college query
                log_llm_call(
                    model=config.LLM_MODEL,
                    input_tokens=len(prompt),
                    output_tokens=len(answer),
                    latency=time.time() - start_time,
                    success=True,
                    metadata={"intent": "non_college_query"},
                )
                return

            # Step 2: A/B test — assign prompt version (random A/B)
            ab_version, _ = get_prompt_version()

            # Step 3: Retrieve user memories for context injection
            user_id = st.session_state.user_id
            memory_context = retrieve_user_context(user_id, prompt, top_k=config.MEMORY_TOP_K)
            if memory_context:
                logger.info(f"Injected memory context for user {user_id}")

            # Step 4: Build chat history
            chat_history = [
                {"role": m["role"], "content": m["content"]}
                for m in st.session_state.messages[:-1]
            ]

            # Step 5: Run RAG pipeline with memory context
            with Timer("Full RAG Pipeline"):
                result = answer_question(
                    question=prompt,
                    chat_history=chat_history,
                    top_k=st.session_state.top_k,
                    debug=st.session_state.debug_mode,
                    memory_context=memory_context,  # passed to prompt
                )

            answer = result.get("answer", "")
            citations = result.get("citations", [])
            chunks = result.get("chunks", [])
            latency = time.time() - start_time
            refused = "not available in the uploaded knowledge base" in answer.lower()

            # Step 6: Log the LLM call to JSONL
            log_llm_call(
                model=config.LLM_MODEL,
                input_tokens=len(prompt) + len(memory_context),
                output_tokens=len(answer),
                latency=latency,
                success=True,
                prompt_version=ab_version,
                metadata={
                    "citations_count": len(citations),
                    "refused": refused,
                    "memory_injected": bool(memory_context),
                },
            )

            # Log A/B test result
            log_ab_result(ab_version, citations, refused)

            # Step 7: Threshold alerts
            cost_est = 0.00015 * len(prompt) / 1000 + 0.00060 * len(answer) / 1000
            alerts = check_all_alerts(latency, cost_est)
            for alert in alerts:
                logger.warning(f"THRESHOLD: {alert}")

            # Step 8: Safety scan (in background, not blocking)
            try:
                from rag import retrieve_chunks as rc
                safety_context = " ".join(c.page_content[:200] for c in chunks[:3])
                scan_result = run_full_scan(prompt, answer, safety_context)
                if scan_result.get("hallucination", {}).get("hallucination"):
                    logger.warning(f"Hallucination detected: {scan_result['hallucination']['details']}")
                if scan_result.get("toxicity", {}).get("toxic_detected"):
                    logger.warning(f"Toxic content detected: {scan_result['toxicity']}")
            except Exception as e:
                logger.debug(f"Safety scan skipped: {e}")

            # Step 9: Simulate streaming
            displayed_answer = ""
            for char in answer:
                displayed_answer += char
                if char in ".!?\n":
                    message_placeholder.markdown(displayed_answer + "▌")
                    time.sleep(0.02)
            message_placeholder.markdown(displayed_answer)

            extra = {
                "citations": citations,
                "chunks_retrieved": result.get("chunks_retrieved", 0),
                "latency": round(latency, 2),
                "tokens_used": len(answer) // 4,  # rough estimate
                "chunks": chunks if st.session_state.debug_mode else [],
                "memory_context": memory_context if memory_context else "",
                "ab_version": ab_version,
            }

            st.session_state.messages.append(
                {"role": "assistant", "content": answer, "extra": extra}
            )

            # Step 10: Persist this turn to chat history file
            append_to_chat_history(
                user_id=user_id,
                user_message=prompt,
                assistant_message=answer,
                metadata={"session_id": st.session_state.session_id},
            )

            # Step 11: Extract and store memories from this conversation turn
            stored = process_and_store_memories(
                user_input=prompt,
                assistant_response=answer,
                user_id=user_id,
                session_id=st.session_state.session_id,
                use_llm_extraction=False,
            )
            if stored > 0:
                st.session_state.memory_count += stored
                logger.info(f"Stored {stored} new memories for user {user_id}")

        except Exception as e:
            latency = time.time() - start_time
            error_msg = f"Sorry, an error occurred: {str(e)}"
            message_placeholder.error(error_msg)
            st.session_state.messages.append(
                {"role": "assistant", "content": error_msg, "extra": {}}
            )
            logger.error(f"Error processing question: {e}")
            log_llm_call(
                model=config.LLM_MODEL,
                input_tokens=len(prompt),
                output_tokens=0,
                latency=latency,
                success=False,
                error=str(e),
            )


def main() -> None:
    """Main application entry point."""
    load_dotenv()
    initialize_session_state()
    check_vector_store()

    # ── Initialize memory: cleanup old memories on first run ──
    if not st.session_state.memory_initialized:
        try:
            deleted = run_cleanup(days=config.MEMORY_CLEANUP_DAYS)
            stats = get_stats(st.session_state.user_id)
            st.session_state.memory_count = stats["total_memories"]
            st.session_state.memory_initialized = True
            if deleted > 0:
                logger.info(f"Startup cleanup: removed {deleted} expired memories")
        except Exception as e:
            logger.warning(f"Memory init skipped (first run?): {e}")

    # ── One-time memory bootstrapping from chat history ──
    if not st.session_state.bootstrapped and st.session_state.memory_initialized:
        try:
            result = bootstrap_memories_from_history(
                st.session_state.user_id,
                use_llm=False,
            )
            st.session_state.bootstrapped = True
            stats = get_stats(st.session_state.user_id)
            st.session_state.memory_count = stats["total_memories"]
            if result["new_count"] > 0 or result["updated_count"] > 0:
                logger.info(
                    f"Bootstrapped {result['new_count']} new, "
                    f"{result['updated_count']} updated, "
                    f"{result['skipped_count']} skipped from {result['total_turns']} turns"
                )
        except Exception as e:
            logger.warning(f"Bootstrapping skipped: {e}")

    # Header
    st.markdown(
        '<div class="main-header">'
        "<h1>🎓 BVRIT Hyderabad College FAQ</h1>"
        "<p>Ask any question about admissions, departments, placements, facilities, and more</p>"
        "</div>",
        unsafe_allow_html=True,
    )

    # Render sidebar
    render_sidebar()

    # Memory status + Session Stats in sidebar
    with st.sidebar:
        st.markdown("---")
        st.markdown("#### 📊 Session Stats")
        stats = compute_session_stats()
        st.markdown(render_stats_html(stats), unsafe_allow_html=True)

        # Run log analyzer and governance report buttons
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔍 Analyze Logs", use_container_width=True):
                analysis = analyze_logs()
                if analysis["anomaly_detected"]:
                    st.error(f"⚠️ {len(analysis['anomalies'])} anomalies found")
                    for a in analysis["anomalies"]:
                        st.caption(f"• {a}")
                else:
                    st.success("✅ No anomalies detected")
        with col2:
            if st.button("📋 Governance Report", use_container_width=True):
                try:
                    report = generate_report()
                    st.success(f"✅ Report saved ({report['report_metadata']['version']})")
                except Exception as e:
                    st.error(f"Report generation failed: {e}")

        if st.session_state.memory_initialized:
            st.markdown("---")
            st.markdown("#### 🧠 Memory")
            st.markdown(
                f'<div class="sidebar-status status-ok" style="font-size:0.8rem;">'
                f"✅ Active<br><small>{st.session_state.memory_count} memories stored</small>"
                f"</div>",
                unsafe_allow_html=True,
            )
            if st.button("🗑️ Clear My Data", use_container_width=True, key="clear_memory"):
                deleted = clear_user_data(st.session_state.user_id)
                st.session_state.memory_count = 0
                st.success(f"Cleared {deleted} memories!")
                st.rerun()

    # Chat history
    for message in st.session_state.messages:
        render_chat_message(message)

    # Chat input
    if prompt := st.chat_input("Ask a question about BVRIT Hyderabad..."):
        process_user_input(prompt)
        st.rerun()

    # Clear chat button
    if st.session_state.messages:
        col1, col2, col3 = st.columns([1, 1, 1])
        with col2:
            if st.button("🗑️ Clear Chat", use_container_width=True):
                st.session_state.messages = []
                st.rerun()


if __name__ == "__main__":
    main()