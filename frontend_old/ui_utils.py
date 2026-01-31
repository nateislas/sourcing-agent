import csv
import io
from datetime import datetime

import pandas as pd
import streamlit as st


def load_css(file_name):
    with open(file_name) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


def render_worker_cards(workers):
    """Renders visual cards for active research workers with detailed insights."""
    st.subheader("Active Knowledge Workers")

    if not workers:
        st.write("Initializing workers...")
        return

    # Use columns for layout
    cols = st.columns(min(3, len(workers)))
    for i, (w_id, w) in enumerate(workers.items()):
        col = cols[i % len(cols)]

        status_class = "worker-active"
        if w.status == "PRODUCTIVE":
            status_class = "worker-productive"
        elif w.status == "DECLINING":
            status_class = "worker-declining"
        elif w.status == "DEAD_END":
            status_class = "worker-dead"

        with col:
            st.markdown(
                f"""
            <div class="glass-card worker-card {status_class}">
                <div style="font-weight: bold; margin-bottom: 5px; color: var(--text-primary);">{w.strategy}</div>
                <div style="font-size: 0.8rem; color: var(--text-secondary);">ID: {w_id[:8]}... | Status: {w.status}</div>
                <div style="display: flex; justify-content: space-between; margin-top: 10px; font-size: 0.85rem;">
                    <span>Pages: {w.pages_fetched}</span>
                    <span>Entities: {w.entities_found}</span>
                    <span>New: {w.new_entities}</span>
                </div>
            </div>
            """,
                unsafe_allow_html=True,
            )

            with st.expander("Worker Insights", expanded=False):
                st.markdown(f"**Strategy:** {w.strategy}")

                if hasattr(w, "query_history") and w.query_history:
                    st.markdown("**Recent Queries:**")
                    for q_entry in list(w.query_history)[-3:]:
                        query_text = q_entry.get("query", "Unknown")
                        novelty = q_entry.get("new_entities", 0)
                        st.markdown(f"- `{query_text}` (Found: {novelty})")

                if hasattr(w, "explored_domains") and w.explored_domains:
                    st.markdown(f"**Domains Explored:** {len(w.explored_domains)}")
                    st.caption(", ".join(list(w.explored_domains)[:5]) + "...")


def render_log_stream(logs):
    """Renders an auto-scrolling log terminal."""
    st.subheader("Process Logs")

    log_html = '<div class="terminal-container">'
    for log in logs:
        # Simple parsing for log types
        line_class = "terminal-info"
        if "Found" in log or "New" in log:
            line_class = "terminal-success"
        elif "Stopping" in log or "Killed" in log:
            line_class = "terminal-warning"

        log_html += f'<div class="terminal-line"><span class="terminal-timestamp">[{datetime.now().strftime("%H:%M:%S")}]</span> <span class="{line_class}">{log}</span></div>'

    log_html += "</div>"
    st.markdown(log_html, unsafe_allow_html=True)


def render_source_panel(visited_urls, discovered_links=None):
    """Renders a panel showing source exploration progress."""
    st.subheader("Link Discovery")

    c1, c2 = st.columns(2)
    with c1:
        st.metric("Sites Visited", len(visited_urls))
    with c2:
        st.metric("Frontier Size", len(discovered_links) if discovered_links else 0)

    with st.expander("Show Discovery Frontier"):
        if discovered_links:
            links_html = '<div class="scroll-container">'
            for url in list(discovered_links)[:100]:
                links_html += f'<a href="{url}" target="_blank" class="source-link">{url[:120]}...</a>'
            links_html += "</div>"
            st.markdown(links_html, unsafe_allow_html=True)
        else:
            st.write("No links discovered yet.")


def render_result_table(entities):
    """Renders the final results with an evidence inspector."""
    st.subheader("Discovered Assets")

    if not entities:
        st.info("No assets discovered yet.")
        return

    data = []
    # Sort by mention count descending
    sorted_entities = sorted(
        entities.items(), key=lambda x: x[1].mention_count, reverse=True
    )

    for name, ent in sorted_entities:
        data.append(
            {
                "Name": ent.canonical_name,
                "Aliases": ", ".join(list(ent.aliases)[:3]),
                "Phase": ent.clinical_phase or "Unknown",
                "Mentions": ent.mention_count,
                "Status": ent.verification_status,
                "Confidence": f"{ent.confidence_score}%"
                if ent.confidence_score
                else "N/A",
            }
        )

    df = pd.DataFrame(data)
    st.dataframe(df, width="stretch", hide_index=True)

    with st.expander("Evidence Inspector"):
        selected_entity = st.selectbox(
            "Select Asset to Inspect", options=[e[0] for e in sorted_entities]
        )
        if selected_entity:
            ent = entities[selected_entity]
            st.markdown(f"### Evidence for **{ent.canonical_name}**")
            for ev in ent.evidence:
                st.markdown(
                    f"""
                <div class="glass-card">
                    <div style="font-size: 0.8rem; color: var(--status-productive); margin-bottom: 8px;">Source: {ev.source_url}</div>
                    <div style="font-style: italic; border-left: 2px solid var(--border-color); padding-left: 10px; color: var(--text-primary);">"{ev.content}"</div>
                </div>
                """,
                    unsafe_allow_html=True,
                )


def render_research_plan(plan):
    """Renders the comprehensive research plan and strategic reasoning."""
    st.subheader("Research Strategy & Plan")

    if not plan:
        st.info("Plan is being formulated by the orchestrator...")
        return

    # Tabs for different plan components
    tab1, tab2, tab3 = st.tabs(["🎯 Strategy", "🧠 Reasoning", "🚧 Gaps & Next Steps"])

    with tab1:
        st.markdown("### Initial Query Analysis")
        if plan.query_analysis:
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("**Targets Identified:**")
                targets = plan.query_analysis.get("targets", [])
                st.write(", ".join(targets) if targets else "None")

                st.markdown("**Indications:**")
                indications = plan.query_analysis.get("indications", [])
                st.write(", ".join(indications) if indications else "None")

            with c2:
                st.markdown("**Modality Constraints:**")
                modalities = plan.query_analysis.get("modalities", [])
                st.write(", ".join(modalities) if modalities else "None")

                st.markdown("**Geographic Focus:**")
                geo = plan.query_analysis.get("geography", [])
                st.write(", ".join(geo) if geo else "None")

        if plan.synonyms:
            st.markdown("---")
            st.markdown("**Expansion Synonyms:**")
            for key, syns in plan.synonyms.items():
                st.markdown(f"> **{key.title()}**: {', '.join(syns)}")

    with tab2:
        st.markdown("### Strategic Rationale")
        st.markdown(
            f"""
        <div class="strategy-container">
            <div class="strategy-content">{plan.reasoning or "No detailed reasoning provided."}</div>
        </div>
        """,
            unsafe_allow_html=True,
        )

        if hasattr(plan, "findings_summary") and plan.findings_summary:
            st.markdown("---")
            st.markdown("**Latest Findings Summary:**")
            st.info(plan.findings_summary)

    with tab3:
        col_gaps, col_steps = st.columns(2)

        with col_gaps:
            st.markdown("### Knowledge Gaps")
            if plan.gaps:
                for gap in plan.gaps:
                    st.warning(
                        f"**{gap.description}**\n\n*Priority: {gap.priority.title()}*"
                    )
            else:
                st.success("No critical gaps identified at this stage.")

        with col_steps:
            st.markdown("### Next Steps")
            if plan.next_steps:
                for step in plan.next_steps:
                    st.markdown(f"- [ ] {step}")
            else:
                st.write("Orchestrating next moves...")


def prepare_csv_data(entities):
    """Converts entities to a CSV string for download."""
    output = io.StringIO()
    fieldnames = [
        "Canonical Label",
        "Aliases",
        "Target",
        "Modality",
        "Stage",
        "Indication",
        "Geography",
        "Owner",
        "Verification Status",
        "Confidence Score",
        "Rejection Reason",
        "Evidence Package",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()

    for name, entity in entities.items():
        aliases_str = "; ".join(entity.aliases) if entity.aliases else ""
        attrs = entity.attributes or {}

        evidence_lines = []
        for ev in entity.evidence:
            clean_content = ev.content.replace("\n", " ").strip()
            line = f"[{ev.timestamp[:10]}] {ev.source_url} - {clean_content}"
            evidence_lines.append(line)
        evidence_package = "\n".join(evidence_lines)

        row = {
            "Canonical Label": entity.canonical_name,
            "Aliases": aliases_str,
            "Target": attrs.get("target") or "Unknown",
            "Modality": attrs.get("modality") or "Unknown",
            "Stage": attrs.get("product_stage") or "Unknown",
            "Indication": attrs.get("indication") or "Unknown",
            "Geography": attrs.get("geography") or "Unknown",
            "Owner": attrs.get("owner") or "Unknown",
            "Verification Status": entity.verification_status,
            "Confidence Score": entity.confidence_score,
            "Rejection Reason": entity.rejection_reason,
            "Evidence Package": evidence_package,
        }
        writer.writerow(row)

    return output.getvalue()


def render_export_tools(entities):
    """Renders data export tools (e.g. Download CSV)."""
    if not entities:
        return

    st.markdown("---")
    st.subheader("Data Export")
    csv_data = prepare_csv_data(entities)

    st.download_button(
        label="📥 Download Research CSV",
        data=csv_data,
        file_name=f"research_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        mime="text/csv",
        use_container_width=True,
    )
