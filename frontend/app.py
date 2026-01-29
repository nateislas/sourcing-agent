"""
Frontend application for the Deep Research Agent using Streamlit.
Allows users to input research topics and triggers Temporal workflows.
"""

import os
import asyncio
import re
import uuid
import streamlit as st
from dotenv import load_dotenv
from temporalio.client import Client, TLSConfig

load_dotenv()

# Centralize configuration
TEMPORAL_ADDRESS = os.getenv("TEMPORAL_ADDRESS", "localhost:7233")
TEMPORAL_NAMESPACE = os.getenv("TEMPORAL_NAMESPACE", "default")
TEMPORAL_API_KEY = os.getenv("TEMPORAL_API_KEY")


async def get_client():
    """
    Connects to the Temporal Client using centralized configuration.
    Returns:
        Client: Connected Temporal Client.
    """
    tls_config = TLSConfig() if TEMPORAL_API_KEY else None

    return await Client.connect(
        TEMPORAL_ADDRESS,
        namespace=TEMPORAL_NAMESPACE,
        api_key=TEMPORAL_API_KEY,
        tls=tls_config,
    )


def slugify(text: str) -> str:
    """
    Sanitizes text for use as a workflow ID.
    Args:
        text: The input text to sanitize.
    Returns:
        A sanitized slug containing only alphanumerics and hyphens.
    """
    text = text.lower()
    text = re.sub(r"[^a-z0-9]", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return text


def main():
    """
    Main entry point for the Streamlit application.
    """
    st.title("Deep Research Agent")

    topic = st.text_input("Enter Research Topic")

    if st.button("Start Research"):
        if not topic:
            st.error("Please enter a topic")
        else:
            st.info("Submitting workflow...")
            try:
                # Create a dedicated event loop for the async client creation and execution
                # Streamlit runs in a separate thread context

                async def run_workflow():
                    client = await get_client()
                    # Sanitize workflow ID with slugify and short UUID suffix
                    sanitized_id = f"{slugify(topic)}-{uuid.uuid4().hex[:8]}"
                    handle = await client.start_workflow(
                        "DeepResearchOrchestrator",
                        topic,
                        id=sanitized_id,
                        task_queue="deep-research-queue",
                    )
                    return handle.id

                workflow_id = asyncio.run(run_workflow())
                st.success(f"Workflow started! ID: {workflow_id}")

                # Format the URL safely using consistent namespace
                url = (
                    f"https://cloud.temporal.io/namespaces/{TEMPORAL_NAMESPACE}/"
                    f"workflows/{workflow_id}"
                )
                st.write(f"Check the [Temporal Web UI]({url})")

            # pylint: disable=broad-exception-caught
            except Exception as e:
                st.error(f"Failed to start workflow: {e}")


if __name__ == "__main__":
    main()
