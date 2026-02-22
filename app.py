import streamlit as st
import pandas as pd
from openai import OpenAI
import json
import os
from datetime import datetime

# 1. Page Config
st.set_page_config(page_title="AI Risk-Aware QA Hub", layout="wide", page_icon="🛡️")

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
    if not loaded: 
        st.session_state.project_db["Project_ABC"] = {"requirement": "", "strategy": "", "tracker_df": pd.DataFrame(columns=["ID", "Scenario", "Expected", "Status", "Severity", "Priority", "Evidence_Link", "Assigned_To"])}
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
    existing_list = list(st.session_state.project_db.keys())
    selected_project = st.selectbox("Switch/Create Project:", options=existing_list + ["+ New Project"])
    
    if selected_project == "+ New Project":
        new_name = st.text_input("Project Name:")
        if st.button("Create"):
            st.session_state.project_db[new_name] = {
                "requirement": "", "strategy": "",
                "tracker_df": pd.DataFrame(columns=["ID", "Scenario", "Expected", "Status", "Severity", "Priority", "Evidence_Link", "Assigned_To"])
            }
            st.rerun()
        active_id = existing_list[0]
    else:
        active_id = selected_project
    
    st.markdown("---")
    if st.button("💾 Save All Changes"):
        save_data(st.session_state.project_db)
        st.success("Database Updated!")

current_data = st.session_state.project_db[active_id]

# 5. UI Tabs
tab1, tab2, tab3 = st.tabs(["🏗️ PRD & Risk Analysis", "✅ Execution Log", "🐞 Bug Center"])

# --- TAB 1: PRD ANALYSIS ---
with tab1:
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Paste Full PRD / Requirements")
        user_req = st.text_area("Input document here:", value=current_data.get("requirement", ""), height=300)
        current_data["requirement"] = user_req
        platform = st.selectbox("Target Platform", ["Web", "Android", "iOS", "Backend"])

        if st.button("🚀 Analyze PRD & Map Risk"):
            with st.spinner("Identifying modules, scenarios, and revenue risks..."):
                prompt = f"""
                Act as a Principal QA Lead. Analyze this PRD: {user_req}
                
                Identify 15+ test cases. For each, you MUST evaluate:
                - SEVERITY: Blocker (Revenue/Auth fail), Critical (Main flow break), Major (Functional issue), Minor (UI/UX).
                - PRIORITY: P0 (Fix immediately), P1 (Critical), P2 (Major), P3 (Minor).
                
                FORMAT: Return only lines starting with 'CASE: [Scenario Name] | [Expected Result] | [Severity] | [Priority]'
                """
                response = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role": "user", "content": prompt}])
                raw_out = response.choices[0].message.content.replace("**", "")
                current_data["strategy"] = raw_out
                
                lines = [l.replace("CASE:", "").strip() for l in raw_out.split("\n") if "CASE:" in l]
                rows = []
                for i, l in enumerate(lines):
                    p = l.split("|")
                    rows.append({
                        "ID": f"TC-{i+1}", 
                        "Scenario": p[0].strip() if len(p)>0 else "N/A",
                        "Expected": p[1].strip() if len(p)>1 else "Functionality works",
                        "Status": "Pending", 
                        "Severity": p[2].strip() if len(p)>2 else "Major",
                        "Priority": p[3].strip() if len(p)>3 else "P1", 
                        "Evidence_Link": "None",
                        "Assigned_To": "Developer"
                    })
                current_data["tracker_df"] = pd.DataFrame(rows)
                st.rerun()

    with col2:
        st.subheader("AI Risk-Mapped Strategy")
        if current_data.get("strategy"):
            st.markdown(current_data["strategy"])
        else:
            st.info("AI analysis will appear here after clicking 'Analyze PRD'.")

# --- TAB 2: EXECUTION LOG ---
with tab2:
    st.subheader(f"Execution Log: {active_id}")
    df = current_data.get("tracker_df", pd.DataFrame())
    if not df.empty:
        # FULLY EDITABLE: User can override AI's Severity/Priority choices
        edited_df = st.data_editor(df, column_config={
                "Status": st.column_config.SelectboxColumn("Status", options=["Pending", "Pass", "Fail"]),
                "Severity": st.column_config.SelectboxColumn("Severity", options=["Blocker", "Critical", "Major", "Minor"]),
                "Priority": st.column_config.SelectboxColumn("Priority", options=["P0", "P1", "P2", "P3"]),
                "Assigned_To": st.column_config.SelectboxColumn("Assigned To", options=["Dev_Lead", "Frontend_Dev", "Backend_Dev", "QA_Manager"])
            }, use_container_width=True, key=f"editor_{active_id}")
        current_data["tracker_df"] = edited_df

        st.markdown("### 📎 Evidence Linker")
        e_col1, e_col2 = st.columns(2)
        with e_col1:
            tc_id = st.selectbox("Select Test Case:", options=edited_df["ID"])
        with e_col2:
            link = st.text_input("Evidence Link (Recording/Image URL):")
        
        if st.button("Update Evidence"):
            idx = current_data["tracker_df"].index[current_data["tracker_df"]["ID"] == tc_id][0]
            current_data["tracker_df"].at[idx, "Evidence_Link"] = link
            st.success(f"Evidence saved for {tc_id}!")
    else:
        st.warning("Analyze a PRD first to populate this log.")

# --- TAB 3: BUG CENTER ---
with tab3:
    st.subheader("Bug Center")
    df_check = current_data.get("tracker_df", pd.DataFrame())
    fails = df_check[df_check["Status"] == "Fail"] if not df_check.empty else pd.DataFrame()
    
    if fails.empty:
        st.info("No failures logged.")
    else:
        for _, bug in fails.iterrows():
            with st.expander(f"🐞 BUG: {bug['ID']} - {bug['Scenario']}"):
                # Pre-filled from Tab 2, but editable here
                st.markdown(f"**Project:** {active_id}")
                st.markdown(f"**Evidence:** {bug['Evidence_Link']}")
                
                rep_col1, rep_col2 = st.columns(2)
                with rep_col1:
                    b_mod = st.text_input("Module:", value="Identify Module (e.g. Checkout)", key=f"mod_{bug['ID']}")
                    b_sev = st.selectbox("Severity:", options=["Blocker", "Critical", "Major", "Minor"], index=["Blocker", "Critical", "Major", "Minor"].index(bug['Severity']) if bug['Severity'] in ["Blocker", "Critical", "Major", "Minor"] else 2, key=f"sev_{bug['ID']}")
                with rep_col2:
                    b_pri = st.selectbox("Priority:", options=["P0", "P1", "P2", "P3"], index=["P0", "P1", "P2", "P3"].index(bug['Priority']) if bug['Priority'] in ["P0", "P1", "P2", "P3"] else 1, key=f"pri_{bug['ID']}")
                    b_ass = st.text_input("Assigned To:", value=bug['Assigned_To'], key=f"ass_{bug['ID']}")
                
                b_desc = st.text_area("Description:", value=f"Requirement failure in {bug['Scenario']}.", key=f"desc_{bug['ID']}")
                b_exp = st.text_input("Expected:", value=bug['Expected'], key=f"exp_{bug['ID']}")
                b_act = st.text_input("Actual:", value="Result did not match PRD criteria.", key=f"act_{bug['ID']}")

                if st.button(f"Generate AI Jira Draft for {bug['ID']}", key=f"btn_{bug['ID']}"):
                    prompt_ctx = f"Project: {active_id}\nModule: {b_mod}\nScenario: {bug['Scenario']}\nExpected: {b_exp}\nActual: {b_act}\nSeverity: {b_sev}\nPriority: {b_pri}\nEvidence: {bug['Evidence_Link']}"
                    res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role": "user", "content": f"Write a detailed Jira bug report: {prompt_ctx}"}])
                    st.code(res.choices[0].message.content)