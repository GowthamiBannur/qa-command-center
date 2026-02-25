import streamlit as st
import pandas as pd
from openai import OpenAI
import json
import os

# 1. Page Config
st.set_page_config(page_title="Pro QA Hub", layout="wide", page_icon="🛡️")

# 2. Setup AI Client
try:
    client = OpenAI(base_url="https://api.groq.com/openai/v1", api_key=st.secrets["GROQ_API_KEY"])
except Exception:
    st.error("API Key missing! Add GROQ_API_KEY to your Streamlit Secrets.")

# 3. Persistent Storage Logic (Saves to a local file)
DB_FILE = "qa_database.json"

def load_data():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f:
            return json.load(f)
    return {}

def save_data(data):
    # Convert DataFrames to dict for JSON storage
    serializable_data = {}
    for p_id, p_val in data.items():
        serializable_data[p_id] = {
            "requirement": p_val["requirement"],
            "strategy": p_val["strategy"],
            "tracker_dict": p_val["tracker_df"].to_dict('records')
        }
    with open(DB_FILE, "w") as f:
        json.dump(serializable_data, f)

# Initialize Session State from Storage
if 'project_db' not in st.session_state:
    loaded = load_data()
    st.session_state.project_db = {}
    for p_id, p_val in loaded.items():
        st.session_state.project_db[p_id] = {
            "requirement": p_val["requirement"],
            "strategy": p_val["strategy"],
            "tracker_df": pd.DataFrame(p_val["tracker_dict"])
        }

# 4. Sidebar: Project Management
with st.sidebar:
    st.title("🛡️ QA Hub Manager")
    
    # Switch between projects
    existing_projects = list(st.session_state.project_db.keys())
    selected_project = st.selectbox("Switch Project:", options=existing_projects + ["+ Create New Project"])
    
    if selected_project == "+ Create New Project":
        new_name = st.text_input("New Project Name:")
        if st.button("Initialize Project"):
            st.session_state.project_db[new_name] = {
                "requirement": "", "strategy": "",
                "tracker_df": pd.DataFrame(columns=["ID", "Scenario", "Status", "Severity", "Priority", "Evidence_Link"])
            }
            st.rerun()
    else:
        project_id = selected_project

    st.markdown("---")
    if st.button("💾 Save All Changes (Persistent)"):
        save_data(st.session_state.project_db)
        st.success("All projects saved for tomorrow!")

current_data = st.session_state.project_db[project_id]

# 5. UI Tabs
tab1, tab2, tab3 = st.tabs(["🏗️ Strategy & Planning", "✅ Execution Log", "🐞 Bug Center"])

# --- TAB 1: STRATEGY & PLANNING ---
with tab1:
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Business Requirements")
        user_req = st.text_area("Requirement Description:", value=current_data["requirement"], height=200)
        current_data["requirement"] = user_req
        platform = st.selectbox("Platform", ["Web", "Android", "iOS", "Backend"])

        if st.button("🚀 Generate Deep-Dive Suite"):
            with st.spinner("Analyzing for Edge Cases & Revenue Impact..."):
                prompt = f"""
                Act as a Principal QA. For the requirement: {user_req}
                Generate 15+ test cases covering: 
                1. Happy Path 2. Extreme Edge Cases 3. Negative Scenarios 4. UI/UX 5. Performance.
                
                For each case, determine Severity (Blocker/Critical/Major/Minor) and Priority (P0/P1/P2/P3) 
                based on user impact and revenue risk.
                
                FORMAT: Provide a clean list. Each line must be:
                'CASE: [Scenario] | [Expected] | [Severity] | [Priority]'
                """
                response = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role": "user", "content": prompt}])
                raw_out = response.choices[0].message.content
                current_data["strategy"] = raw_out
                
                # Auto-parse into Execution Log
                lines = [l.replace("CASE:", "").strip() for l in raw_out.split("\n") if "CASE:" in l]
                rows = []
                for i, l in enumerate(lines):
                    p = l.split("|")
                    rows.append({
                        "ID": f"TC-{i+1}", 
                        "Scenario": p[0] if len(p)>0 else "N/A",
                        "Status": "Pending",
                        "Severity": p[2] if len(p)>2 else "Major",
                        "Priority": p[3] if len(p)>3 else "P1",
                        "Evidence_Link": "None"
                    })
                current_data["tracker_df"] = pd.DataFrame(rows)
                st.rerun()

    with col2:
        st.subheader("Refined Test Strategy")
        # Display without ** markers, using clean UI components
        if current_data["strategy"]:
            clean_strategy = current_data["strategy"].replace("**", "")
            st.markdown(clean_strategy)
        else:
            st.info("No strategy generated yet.")

# --- TAB 2: EXECUTION LOG ---
with tab2:
    st.subheader(f"Execution Tracker: {project_id}")
    if not current_data["tracker_df"].empty:
        # User can edit Severity and Priority manually if AI's choice is wrong
        edited_df = st.data_editor(
            current_data["tracker_df"],
            column_config={
                "Status": st.column_config.SelectboxColumn("Status", options=["Pending", "Pass", "Fail"]),
                "Severity": st.column_config.SelectboxColumn("Severity", options=["Blocker", "Critical", "Major", "Minor"]),
                "Priority": st.column_config.SelectboxColumn("Priority", options=["P0", "P1", "P2", "P3"]),
            },
            use_container_width=True
        )
        current_data["tracker_df"] = edited_df

        # Handle Screenshot/Link Attachment
        st.markdown("### 📎 Evidence Attachment")
        tc_to_attach = st.selectbox("Select Test Case for Evidence:", options=edited_df["ID"])
        evidence_url = st.text_input("Paste Screenshot/Recording Link (e.g., Drive/Cloudinary):")
        if st.button("Attach Link to Scenario"):
            idx = current_data["tracker_df"].index[current_data["tracker_df"]["ID"] == tc_to_attach][0]
            current_data["tracker_df"].at[idx, "Evidence_Link"] = evidence_url
            st.success(f"Linked evidence to {tc_to_attach}")
    else:
        st.warning("Generate scenarios in the Planner tab.")

# --- TAB 3: BUG CENTER ---
with tab3:
    st.subheader("Automated Bug Tracker")
    fails = current_data["tracker_df"][current_data["tracker_df"]["Status"] == "Fail"]
    if fails.empty:
        st.info("Zero failures logged. Great job!")
    else:
        for _, bug in fails.iterrows():
            with st.expander(f"🐞 BUG: {bug['ID']} - {bug['Scenario']}"):
                st.error(f"Severity: {bug['Severity']} | Priority: {bug['Priority']}")
                st.markdown(f"**Evidence:** {bug['Evidence_Link']}")
                st.write("---")
                if st.button(f"Draft Jira Report for {bug['ID']}"):
                    bug_prompt = f"Write a Jira bug report for {bug['Scenario']}. Severity: {bug['Severity']}. Evidence Link: {bug['Evidence_Link']}"
                    res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role": "user", "content": bug_prompt}])
                    st.code(res.choices[0].message.content)