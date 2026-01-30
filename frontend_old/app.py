"""
Frontend application for the Deep Research Agent using Streamlit.
Redesigned with a premium dashboard aesthetic and real-time polling.
"""

import os
import asyncio
import re
import uuid
import time
import streamlit as st
from dotenv import load_dotenv
from temporalio.client import Client, TLSConfig
from temporalio.contrib.pydantic import pydantic_data_converter

from backend.db.connection import AsyncSessionLocal
from backend.db.repository import ResearchRepository
from backend.research.state import ResearchState
from frontend.ui_utils import (
    load_css,
    render_worker_cards,
    render_log_stream,
    render_source_panel,
    render_result_table,
    render_export_tools,
    render_research_plan
)

load_dotenv()

# Configuration
TEMPORAL_ADDRESS = os.getenv("TEMPORAL_ADDRESS", "localhost:7233")
TEMPORAL_NAMESPACE = os.getenv("TEMPORAL_NAMESPACE", "default")
TEMPORAL_API_KEY = os.getenv("TEMPORAL_API_KEY")

st.set_page_config(
    page_title="Deep Research Agent",
    page_icon="🧬",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Load custom styles
load_css("frontend/styles.css")

async def get_client():
    tls_config = TLSConfig() if TEMPORAL_API_KEY else None
    return await Client.connect(
        TEMPORAL_ADDRESS,
        namespace=TEMPORAL_NAMESPACE,
        api_key=TEMPORAL_API_KEY,
        tls=tls_config,
        data_converter=pydantic_data_converter,
    )

async def start_research(topic: str) -> str:
    """Triggers the Temporal workflow and returns the session ID."""
    sanitized_id = f"{slugify(topic)}-{uuid.uuid4().hex[:8]}"

    # Optimistically create the research session in DB
    # This prevents the UI from "hanging" while waiting for the worker to pick up the task
    initial_state = ResearchState(
        id=sanitized_id, 
        topic=topic,
        status="initialized",
        logs=["Initializing research session..."]
    )
    
    async with AsyncSessionLocal() as session:
        repo = ResearchRepository(session)
        await repo.save_session(initial_state)

    client = await get_client()
    handle = await client.start_workflow(
        "DeepResearchOrchestrator",
        topic,
        id=sanitized_id,
        task_queue="deep-research-queue",
    )
    return handle.id

def slugify(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9]", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return text

async def fetch_state(session_id: str):
    """Fetches the current research state from the database by session ID."""
    async with AsyncSessionLocal() as session:
        repo = ResearchRepository(session)
        return await repo.get_session(session_id)

async def fetch_history():
    """Fetches recent research sessions."""
    async with AsyncSessionLocal() as session:
        repo = ResearchRepository(session)
        return await repo.list_sessions(limit=5)

def home_page():
    """Renders the search entry page."""
    st.markdown('<h1>Deep Research Agent</h1>', unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.container(border=True):
            with st.form(key="search_form", border=False):
                topic = st.text_input("Enter Research Topic", placeholder="e.g., CDK12 small molecule, preclinical, TNBC, China")
                
                # Using form_submit_button handles "Enter" key correctly
                submitted = st.form_submit_button("Initialize Deep Scan", type="primary", use_container_width=True)
                
                if submitted:
                    if not topic:
                        st.error("Please enter a topic")
                    else:
                        with st.status("Launching Orbital Agents...", expanded=True) as status:
                            try:
                                # Get the session ID from the workflow
                                session_id = asyncio.run(start_research(topic))
                                status.update(label="Scanning Initialized!", state="complete")
                                st.query_params["session_id"] = session_id
                                st.rerun()
                            except Exception as e:
                                st.error(f"Launch sequence failed: {e}")

    st.markdown("---")
    st.subheader("Recent Research Sessions")
    
    try:
        history = asyncio.run(fetch_history())
    except Exception:
        history = []
    
    if not history:
        st.info("No research history found. Start your first scan above!")
    else:
        for session in history:
            with st.container():
                c1, c2, c3, c4 = st.columns([3, 1, 1, 1])
                c1.markdown(f"**{session['topic']}**")
                c2.write(f"Status: `{session['status']}`")
                c3.write(f"Found: {session['entities_count']} assets")
                if c4.button("View Scan", key=f"hist_{session['session_id']}"):
                    st.query_params["session_id"] = session['session_id']
                    st.rerun()

def monitor_page(session_id: str):
    """Renders the real-time monitoring dashboard."""
    
    if st.button("← Back to Launcher"):
        st.query_params.clear()
        st.rerun()

    # Polling Logic
    try:
        state = asyncio.run(fetch_state(session_id))
    except Exception as e:
        st.error(f"Error fetching state: {e}")
        time.sleep(2)
        st.rerun()
    
    if not state:
        st.warning("Waiting for state to initialize...")
        time.sleep(1)
        st.rerun()
    
    # Display topic from state
    st.markdown(f'<h2>Research: {state.topic}</h2>', unsafe_allow_html=True)
    
    # Status Banner
    if state.status == "completed":
        st.success("✅ Deep Scan Complete")
    elif state.status in ["running", "verification_pending", "initialized"]:
        st.info(f"🛰️ {state.status.replace('_', ' ').title()}...")
    else:
        st.warning(f"Status: {state.status.replace('_', ' ').title()}")
    
    # Main Content Area
    tab_dash, tab_strat, tab_explore = st.tabs(["📊 Dashboard", "🎯 Research Strategy", "🌐 Link Explorer"])
    
    with tab_dash:
        c1, c2 = st.columns([2, 1])
        with c1:
            render_log_stream(state.logs)
            render_result_table(state.known_entities)
        with c2:
            render_worker_cards(state.workers)
            
    with tab_strat:
        render_research_plan(state.plan)
        
    with tab_explore:
        # Aggregate Discovery Frontier from all workers
        frontier = set()
        for worker in state.workers.values():
            if hasattr(worker, 'personal_queue'):
                frontier.update(worker.personal_queue)
        
        render_source_panel(state.visited_urls, list(frontier)) 

    # Export Tools
    render_export_tools(state.known_entities)

    # Polling
    if state.status not in ["completed", "failed"]:
        time.sleep(3) # Slightly longer sleep to reduce blinking
        st.rerun()

def main():
    # Use session_id from query params if available
    session_id = st.query_params.get("session_id")
    
    if session_id:
        monitor_page(session_id)
        st.stop()
    else:
        home_page()
        st.stop()

if __name__ == "__main__":
    main()
