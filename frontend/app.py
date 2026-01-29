"""
Frontend application for the Deep Research Agent using Streamlit.
Allows users to input research topics and triggers Temporal workflows.
"""

import os
import asyncio
import streamlit as st
from dotenv import load_dotenv
from temporalio.client import Client, TLSConfig

load_dotenv()


async def get_client():
    """
    Connects to the Temporal Client using environment variables.
    Returns:
        Client: Connected Temporal Client.
    """
    address = os.getenv("TEMPORAL_ADDRESS", "localhost:7233")
    namespace = os.getenv("TEMPORAL_NAMESPACE", "default")
    api_key = os.getenv("TEMPORAL_API_KEY")

    tls_config = TLSConfig() if api_key else None

    return await Client.connect(
        address, namespace=namespace, api_key=api_key, tls=tls_config
    )


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
                    handle = await client.start_workflow(
                        "DeepResearchOrchestrator",
                        topic,
                        id=f"research-{topic}",
                        task_queue="deep-research-queue",
                    )
                    return handle.id

                workflow_id = asyncio.run(run_workflow())
                st.success(f"Workflow started! ID: {workflow_id}")

                # Format the URL safely
                namespace = os.getenv("TEMPORAL_NAMESPACE")
                url = f"https://cloud.temporal.io/namespaces/{namespace}/workflows/{workflow_id}"
                st.write(f"Check the [Temporal Web UI]({url})")

            # pylint: disable=broad-exception-caught
            except Exception as e:
                st.error(f"Failed to start workflow: {e}")


if __name__ == "__main__":
    main()
