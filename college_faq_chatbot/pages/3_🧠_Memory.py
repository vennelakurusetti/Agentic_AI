"""
pages/3_🧠_Memory.py — User Memory management page.
View, search, and manage stored user memories from the ChromaDB memory store.
"""

import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st
import pandas as pd
from dotenv import load_dotenv

load_dotenv()
import config
from memory.memory_manager import (
    get_stats,
    clear_user_data,
    run_cleanup,
    retrieve_user_context,
)
from memory.memory_store import (
    get_memory_collection,
    get_memory_count,
)

st.set_page_config(
    page_title="Memory — BVRIT FAQ",
    page_icon="🧠",
    layout="wide",
)

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    * { font-family: 'Inter', sans-serif; }
    .stApp { background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%) !important; }
    .memory-card {
        background: white;
        border-radius: 10px;
        padding: 0.8rem 1rem;
        margin-bottom: 0.6rem;
        box-shadow: 0 1px 4px rgba(0,0,0,0.08);
        border-left: 4px solid #7c4dff;
    }
    .memory-type {
        display: inline-block;
        background: #ede7f6;
        color: #4a148c;
        padding: 0.1rem 0.5rem;
        border-radius: 12px;
        font-size: 0.75rem;
        font-weight: 600;
        margin-bottom: 0.3rem;
    }
    .memory-content { font-size: 0.9rem; color: #333; }
    .memory-meta { font-size: 0.75rem; color: #888; margin-top: 0.3rem; }
    .stat-box {
        background: white;
        border-radius: 10px;
        padding: 1rem;
        text-align: center;
        box-shadow: 0 2px 6px rgba(0,0,0,0.08);
    }
    .stat-num { font-size: 2rem; font-weight: 700; color: #4a148c; }
    .stat-lbl { font-size: 0.8rem; color: #666; }
</style>
""", unsafe_allow_html=True)


def main():
    st.markdown("## 🧠 User Memory Management")
    st.caption("View, search, and manage ChromaDB-backed user memories (30-day auto-expiry).")

    # ── User selector ──────────────────────────────────────────────────────
    st.markdown("### 👤 Select User")
    col1, col2 = st.columns([3, 1])
    with col1:
        user_id = st.text_input(
            "User ID",
            value=config.MEMORY_DEFAULT_USER_ID,
            placeholder="Enter user ID to inspect...",
        )
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🔄 Load", use_container_width=True):
            st.rerun()

    st.markdown("---")

    # ── Stats row ──────────────────────────────────────────────────────────
    try:
        stats = get_stats(user_id)
        total_all = get_memory_count()
        user_count = get_memory_count(user_id)

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.markdown(f'<div class="stat-box"><div class="stat-num">{user_count}</div><div class="stat-lbl">Memories for this User</div></div>', unsafe_allow_html=True)
        with col2:
            st.markdown(f'<div class="stat-box"><div class="stat-num">{total_all}</div><div class="stat-lbl">Total Memories (All Users)</div></div>', unsafe_allow_html=True)
        with col3:
            mem_types = stats.get("by_type", {})
            st.markdown(f'<div class="stat-box"><div class="stat-num">{len(mem_types)}</div><div class="stat-lbl">Memory Types Used</div></div>', unsafe_allow_html=True)
        with col4:
            oldest = stats.get("oldest_memory", "N/A")
            if oldest and oldest != "N/A":
                try:
                    oldest = datetime.fromisoformat(oldest).strftime("%Y-%m-%d")
                except Exception:
                    pass
            st.markdown(f'<div class="stat-box"><div class="stat-num" style="font-size:1.3rem">{oldest}</div><div class="stat-lbl">Oldest Memory</div></div>', unsafe_allow_html=True)

    except Exception as e:
        st.warning(f"Could not load memory stats: {e}")
        stats = {}
        user_count = 0

    st.markdown("---")

    # ── Actions ────────────────────────────────────────────────────────────
    st.markdown("### ⚙️ Memory Actions")
    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("🗑️ Clear This User's Memories", use_container_width=True):
            deleted = clear_user_data(user_id)
            st.success(f"✅ Cleared {deleted} memories for user '{user_id}'")
            st.rerun()

    with col2:
        if st.button(f"🧹 Run Cleanup (delete >{config.MEMORY_CLEANUP_DAYS}d old)", use_container_width=True):
            deleted = run_cleanup(days=config.MEMORY_CLEANUP_DAYS)
            st.success(f"✅ Cleanup: deleted {deleted} expired memories")
            st.rerun()

    with col3:
        days = st.number_input("Days threshold", value=30, min_value=1, max_value=365)
        if st.button("🧹 Custom Cleanup", use_container_width=True):
            deleted = run_cleanup(days=days)
            st.success(f"✅ Deleted {deleted} memories older than {days} days")
            st.rerun()

    st.markdown("---")

    # ── Memory retrieval test ──────────────────────────────────────────────
    st.markdown("### 🔍 Test Memory Retrieval")
    test_query = st.text_input(
        "Test query",
        placeholder="Enter a query to test what memories would be retrieved...",
    )
    if test_query:
        with st.spinner("Retrieving memories..."):
            try:
                context = retrieve_user_context(user_id, test_query, top_k=config.MEMORY_TOP_K)
                if context:
                    st.success("Retrieved memory context:")
                    st.code(context, language="text")
                else:
                    st.info("No relevant memories found for this query.")
            except Exception as e:
                st.error(f"Memory retrieval failed: {e}")

    st.markdown("---")

    # ── Memory browser ─────────────────────────────────────────────────────
    st.markdown("### 📋 Memory Browser")

    try:
        collection = get_memory_collection()
        if user_id:
            results = collection.get(where={"user_id": user_id})
        else:
            results = collection.get()

        ids = results.get("ids", [])
        documents = results.get("documents", [])
        metadatas = results.get("metadatas", [])

        if not ids:
            st.info(f"No memories found for user '{user_id}'.")
        else:
            st.markdown(f"**{len(ids)} memories found**")

            # Filter by type
            all_types = list(set(m.get("memory_type", "unknown") for m in (metadatas or [])))
            selected_type = st.selectbox("Filter by type", ["All"] + sorted(all_types))

            # Build rows
            rows = []
            for i, (mid, doc, meta) in enumerate(zip(ids, documents, metadatas or [{}] * len(ids))):
                mem_type = meta.get("memory_type", "unknown")
                if selected_type != "All" and mem_type != selected_type:
                    continue
                ts = meta.get("ts_iso", meta.get("timestamp", "N/A"))
                try:
                    ts_display = datetime.fromisoformat(str(ts)).strftime("%Y-%m-%d %H:%M") if ts != "N/A" else "N/A"
                except Exception:
                    ts_display = str(ts)[:16]
                rows.append({
                    "ID": mid[:12] + "...",
                    "Type": mem_type,
                    "Content": (doc or "")[:100],
                    "Importance": meta.get("importance", 0.5),
                    "Stored At": ts_display,
                    "Session": meta.get("session_id", "")[:12],
                })

            if rows:
                df = pd.DataFrame(rows)
                st.dataframe(df, use_container_width=True, height=400)

                # Download
                csv = df.to_csv(index=False)
                st.download_button(
                    "⬇️ Export Memories as CSV",
                    data=csv,
                    file_name=f"memories_{user_id}_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv",
                )
            else:
                st.info(f"No memories of type '{selected_type}' found.")

    except Exception as e:
        st.error(f"Could not browse memories: {e}")

    st.markdown("---")

    # ── Privacy Notice ─────────────────────────────────────────────────────
    st.markdown("### 🔒 Privacy Information")
    st.markdown(
        """
        **How memories work:**
        - Conversation memories are automatically extracted from your chats.
        - Memories are stored in a separate ChromaDB instance (`memory_db/`).
        - Memories older than **30 days** are automatically deleted.
        - You can delete all your data at any time using the **Clear** button above.
        - No personal data is shared with third parties.
        - In compliance with **DPDP (Digital Personal Data Protection Act)** requirements.
        """
    )


if __name__ == "__main__":
    main()
