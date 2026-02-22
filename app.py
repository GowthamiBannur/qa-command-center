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

# 3. Persistent Storage (JSON File)
DB_FILE = "qa_database.json"

def load_data():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r") as f:
                return json.load(f)
        except: return {}
    return {}

def save_data(data):
    serializable = {}
    for p_id, p_val in data.items():
        serializable[p_id] = {
            "requirement": p_val.get("requirement", ""),
            "strategy": p_val.get("strategy", ""),
            "tracker_dict": p_val["tracker_df"].to_dict('records') if isinstance(p_val.get("tracker_df"), pd.DataFrame) else []
        }
    with open(DB_FILE, "w") as f:
        json.dump(serializable, f)

# Initialize Session State
if 'project_db' not in st.session_state:
    loaded = load_data()
    st.session_state.project_db = {}
    if not loaded: # Default starting project
        st.session_state.project_db["Project_ABC"] = {"requirement": "", "strategy": "", "tracker_df": pd.DataFrame()}
    else:
        for p_id, p_val in loaded.items():
            st.session_state.project_db[p_id] = {
                "requirement": p_val.get("requirement", ""),
                "strategy": p_val.get("strategy", ""),
                "tracker_df": pd.DataFrame(p_val.get("tracker_dict", []))
            }

# 4. Sidebar: Project Management
with st.sidebar:
    st.title("🛡️ QA Hub Manager")
    
    # Switcher
    existing_list = list(st.session_state.project_db.keys())
    selected_project = st.selectbox("Switch/Create Project:", options=existing_list + ["+ New Project"])
    
    active_id = selected_project
    if selected_project == "+ New Project":
        new_name = st.text_input("Project Name:")
        if st.button("Create"):
            st.session_state.project_db[new_name] = {
                "requirement": "", "strategy": "",
                "tracker_df": pd.DataFrame(columns=["ID", "Scenario", "Status", "Severity", "Priority", "Evidence_Link"])
            }
            st.rerun()
    
    st.markdown("---")
    if st.button("💾 Save All Changes"):
        save_data(st.session_state.project_db)
        st.success("Saved to database!")

# Safely get current data
current_data = st.session_state.project_db.get(active_id, st.session_state.project_db[existing_list[0]])

# 5. UI Tabs
tab1, tab2, tab3 = st.tabs(["🏗️ Strategy & Planning", "✅ Execution Log", "🐞 Bug Center"])

# --- TAB 1: STRATEGY ---
with tab1:
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Requirements")
        user_req = st.text_area("Description:", value=current_data.get("requirement", ""), height=200)
        current_data["requirement"] = user_req
        platform = st.selectbox("Platform", ["Web", "Android", "iOS", "Backend"])

        if st.button("🚀 Generate Deep-Dive Plan"):
            with st.spinner("Analyzing for Edge Cases..."):
                prompt = f"Principal QA: Generate 15+ complex test cases for {platform}: {user_req}. Format: 'CASE: [Scenario] | [Expected] | [Severity] | [Priority]'"
                response = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role": "user", "content": prompt}])
                raw_out = response.choices[0].message.content.replace("**", "") # Clean UI
                current_data["strategy"] = raw_out
                
                # Auto-parse to Log
                lines = [l.replace("CASE:", "").strip() for l in raw_out.split("\n") if "CASE:" in l]
                rows = []
                for i, l in enumerate(lines):
                    p = l.split("|")
                    rows.append({
                        "ID": f"TC-{i+1}", "Scenario": p[0] if len(p)>0 else "N/A",
                        "Status": "Pending", "Severity": p[2].strip() if len(p)>2 else "Major",
                        "Priority": p[3].strip() if len(p)>3 else "P1", "Evidence_Link": "None"
                    })
                current_data["tracker_df"] = pd.DataFrame(rows)
                st.rerun()

    with col2:
        st.subheader("Professional Strategy View")
        if current_data.get("strategy"):
            # Display clean strategy
            st.info("💡 High-impact scenarios identified for this requirement.")
            st.markdown(current_data["strategy"])
        else:
            st.write("No strategy logged for this project.")

# --- TAB 2: EXECUTION ---
with tab2:
    st.subheader(f"Execution Log: {active_id}")
    df = current_data.get("tracker_df", pd.DataFrame())
    if not df.empty:
        # Status, Severity, Priority are all editable
        edited_df = st.data_editor(df, column_config={
                "Status": st.column_config.SelectboxColumn("Status", options=["Pending", "Pass", "Fail"]),
                "Severity": st.column_config.SelectboxColumn("Severity", options=["Blocker", "Critical", "Major", "Minor"]),
                "Priority": st.column_config.SelectboxColumn("Priority", options=["P0", "P1", "P2", "P3"])
            }, use_container_width=True)
        current_data["tracker_df"] =