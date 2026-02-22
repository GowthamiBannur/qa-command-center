import streamlit as st
import pandas as pd
from openai import OpenAI
from datetime import datetime

# 1. Page Config
st.set_page_config(page_title="Advanced QA Portal", layout="wide", page_icon="🛡️")

# 2. Setup AI Client
try:
    client = OpenAI(
        base_url="https://api.groq.com/openai/v1", 
        api_key=st.secrets["GROQ_API_KEY"]
    )
except Exception:
    st.error("API Key missing! Please add GROQ_API_KEY to your Streamlit Secrets.")

# 3. Persistent Project Database
if 'project_db' not in st.session_state:
    st.session_state.project_db = {}

# 4. Sidebar: Project Management
with st.sidebar:
    st.title("🛡️ Project Manager")
    custom_project_name = st.text_input("Enter/Edit Project Name:", value="New_Project_1")
    
    if custom_project_name not in st.session_state.project_db:
        st.session_state.project_db[custom_project_name] = {
            "requirement": "",
            "plan_list": [],
            "tracker_df": pd.DataFrame(columns=["ID", "Scenario", "Expected Result", "Status", "Screenshot", "Bug_Link"])
        }
    
    current_data = st.session_state.project_db[custom_project_name]
    st.success(f"Editing: {custom_project_name}")
    st.markdown("---")
    st.info("💡 Fails are automatically prepared for the Bug Reporter tab.")

# 5. UI Tabs
tab1, tab2, tab3 = st.tabs(["🏗️ Strategy Planner", "✅ Execution Tracker", "🐞 Automated Bug Reports"])

# --- TAB 1: STRATEGY PLANNER ---
with tab1:
    col1, col2 = st.columns([1, 1])
    with col1:
        st.subheader("Requirements")
        user_req = st.text_area("User Story / Description:", value=current_data["requirement"], height=200)
        current_data["requirement"] = user_req
        platform = st.selectbox("Platform", ["Web", "Android", "iOS", "API"])

        if st.button("🚀 Generate & Sync Strategy"):
            with st.spinner("Analyzing for edge cases..."):
                prompt = f"""
                Act as a Senior QA. Create a detailed test plan for {platform}: {user_req}.
                FORMAT: Provide exactly 8 scenarios. Start each scenario line with 'CASE: [Title] | [Expected Result]'
                """
                response = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[{"role": "user", "content": prompt}]
                )
                raw_plan = response.choices[0].message.content
                
                # Parsing logic for structured display and table sync
                lines = [l.replace("CASE:", "").strip() for l in raw_plan.split("\n") if "CASE:" in l]
                new_scenarios = []
                current_data["plan_list"] = lines # Save for display
                
                for i, line in enumerate(lines):
                    parts = line.split("|")
                    scen = parts[0].strip() if len(parts) > 0 else "N/A"
                    exp = parts[1].strip() if len(parts) > 1 else "Works as expected"
                    new_scenarios.append({"ID": f"TC-{i+1}", "Scenario": scen, "Expected Result": exp, "Status": "Pending", "Screenshot": None, "Bug_Link": "N/A"})
                
                current_data["tracker_df"] = pd.DataFrame(new_scenarios)
                st.rerun()

    with col2:
        st.subheader("Aligned Test Strategy")
        if current_data["plan_list"]:
            for item in current_data["plan_list"]:
                st.markdown(f"- **{item.split('|')[0]}**")
                st.caption(f"↳ Expected: {item.split('|')[1] if '|' in item else ''}")
        else:
            st.info("Generate a plan to see the aligned strategy.")

# --- TAB 2: EXECUTION TRACKER ---
with tab2:
    st.subheader(f"Execution Log: {custom_project_name}")
    if not current_data["tracker_df"].empty:
        # Use data_editor with dropdown for Status
        updated_df = st.data_editor(
            current_data["tracker_df"],
            column_config={
                "Status": st.column_config.SelectboxColumn(
                    "Status",
                    options=["Pending", "Pass", "Fail", "Blocked"],
                    required=True,
                ),
                "Screenshot": st.column_config.ImageColumn("Preview"),
            },
            num_rows="dynamic",
            use_container_width=True,
            key=f"editor_{custom_project_name}"
        )
        current_data["tracker_df"] = updated_df

        # Handle Screenshot Uploads for Failures
        failed_tests = updated_df[updated_df["Status"] == "Fail"]
        if not failed_tests.empty:
            st.warning("📸 Attachment Section: Failed test cases detected.")
            for index, row in failed_tests.iterrows():
                uploaded_file = st.file_uploader(f"Attach screenshot for {row['ID']} (Optional)", key=f"file_{row['ID']}")
                if uploaded_file:
                    st.success(f"Attached to {row['ID']}")
    else:
        st.warning("Generate a plan first.")

# --- TAB 3: AUTOMATED BUG REPORTS ---
with tab3:
    st.subheader("Pending Bug Reports")
    failures = current_data["tracker_df"][current_data["tracker_df"]["Status"] == "Fail"]
    
    if failures.empty:
        st.info("No failures logged in the Execution Tracker.")
    else:
        for _, bug in failures.iterrows():
            with st.expander(f"🐞 Bug Report: {bug['ID']} - {bug['Scenario']}"):
                st.markdown(f"**Title:** [BUG] {bug['Scenario']} failed on {platform}")
                st.markdown(f"**Description:** During execution, the expected result '{bug['Expected Result']}' was not met.")
                st.markdown(f"**Status:** Critical / Fail")
                st.markdown(f"**Date:** {datetime.now().strftime('%Y-%m-%d')}")
                
                if st.button(f"Generate AI Breakdown for {bug['ID']}"):
                    with st.spinner("Drafting professional report..."):
                        bug_res = client.chat.completions.create(
                            model="llama-3.3-70b-versatile",
                            messages=[{"role": "user", "content": f"Create a professional Jira bug report for this failed test: {bug['Scenario']}. Expected: {bug['Expected Result']}."}]
                        )
                        st.code(bug_res.choices[0].message.content, language="markdown")