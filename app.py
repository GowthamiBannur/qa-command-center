import streamlit as st
import pandas as pd
from openai import OpenAI
import re
import urllib.parse
from supabase import create_client, Client

# 1. Page Config
st.set_page_config(page_title="Team QA Strategy Hub", layout="wide", page_icon="🛡️")

# 2. Connections
@st.cache_resource
def init_connection():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = init_connection()
client = OpenAI(base_url="https://api.groq.com/openai/v1", api_key=st.secrets["GROQ_API_KEY"])

# 3. Persistence Logic
def load_projects():
    res = supabase.table("qa_tracker").select("project_name").execute()
    return sorted(list(set([r['project_name'] for r in res.data]))) if res.data else ["Default_Project"]

def load_project_data(project_name):
    res = supabase.table("qa_tracker").select("*").eq("project_name", project_name).execute()
    return pd.DataFrame(res.data)

def sync_to_db(df, project_name):
    supabase.table("qa_tracker").delete().eq("project_name", project_name).execute()
    if not df.empty:
        data_to_save = df.to_dict(orient='records')
        for row in data_to_save: row['project_name'] = project_name
        supabase.table("qa_tracker").insert(data_to_save).execute()

# 4. Sidebar
with st.sidebar:
    st.title("👥 Team QA Hub")
    project_list = load_projects()
    active_id = st.selectbox("Switch Project:", options=project_list + ["+ New Project"])
    
    if active_id == "+ New Project":
        new_name = st.text_input("Project Name:")
        if st.button("Create"):
            active_id = new_name
            st.rerun()

    if st.button("🌊 Sync Changes for Team"):
        sync_to_db(st.session_state.current_df, active_id)
        st.success("Cloud Database Updated!")

# 5. Load Data
if 'current_df' not in st.session_state or st.session_state.get('last_project') != active_id:
    df = load_project_data(active_id)
    if df.empty:
        df = pd.DataFrame(columns=["ID", "Scenario", "Expected", "Status", "Severity", "Priority", "Evidence_Link", "Assigned_To", "Module"])
    st.session_state.current_df = df
    st.session_state.last_project = active_id
    # Storage for Audit Report
    if 'audit_report' not in st.session_state: st.session_state.audit_report = None

# 6. Tabs
tab1, tab2, tab3 = st.tabs(["🏗️ Senior QA Audit & Strategy", "✅ Execution Log", "🐞 Bug Center"])

# --- TAB 1: DEEP AUDIT & REGRESSION STRATEGY ---
with tab1:
    st.subheader("📋 Requirement Intelligence & Impact Analysis")
    user_req = st.text_area("Paste PRD / Requirement Document here:", height=300, placeholder="Paste messy or complex requirements here...")
    
    if st.button("🚀 Run Deep Strategy Audit"):
        with st.spinner("Analyzing E-commerce dependencies and edge cases..."):
            prompt = f"""
            You are a Senior Lead QA & Business Analyst. Analyze this E-commerce PRD: {user_req}
            
            Provide the following in Markdown format:
            1. REWRITE: A simplified, clear summary of what this feature actually does.
            2. FEATURE_TABLE: A table with columns: [Feature Component | What to Test | Edge Cases | Regression Impact (Where else it affects in E-comm)]
            3. DOUBTS: List specific technical or functional questions to ask the developers/PO.
            4. RISK_MITIGATION: A table with [Risk Identified | Mitigation Strategy].
            5. TEST_CASES: Generate at least 30 test cases in format 'CASE: [Scenario] | [Expected] | [Severity] | [Priority]'
            """
            response = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role": "user", "content": prompt}]).choices[0].message.content
            st.session_state.audit_report = response
            
            # Extract Test Cases for Tab 2
            lines = [l.replace("CASE:", "").strip() for l in response.split("\n") if "CASE:" in l]
            rows = []
            for i, l in enumerate(lines):
                p = l.split("|")
                if len(p) >= 2:
                    rows.append({"ID": f"TC-{i+1}", "Scenario": p[0].strip(), "Expected": p[1].strip(), "Status": "Pending", "Severity": p[2].strip() if len(p)>2 else "Major", "Priority": p[3].strip() if len(p)>3 else "P1", "Evidence_Link": "", "Assigned_To": "dev@team.com", "Module": "Core"})
            st.session_state.current_df = pd.DataFrame(rows)
            st.rerun()

    if st.session_state.audit_report:
        st.markdown("---")
        # Display the AI analysis report
        st.markdown(st.session_state.audit_report)

# --- TAB 2: EXECUTION LOG ---
with tab2:
    st.subheader(f"Execution Log: {active_id}")
    edited_df = st.data_editor(st.session_state.current_df, use_container_width=True, hide_index=True, key="main_editor",
                               column_config={"Status": st.column_config.SelectboxColumn("Status", options=["Pending", "Pass", "Fail"])})
    st.session_state.current_df = edited_df

# --- TAB 3: BUG CENTER ---
with tab3:
    st.subheader("🐞 Bug Reports")
    fails = st.session_state.current_df[st.session_state.current_df["Status"] == "Fail"]
    if fails.empty: st.info("No bugs found. High-five!")
    else:
        for idx, bug in fails.iterrows():
            with st.expander(f"BUG: {bug['ID']} - {bug['Scenario']}"):
                st.write(f"**Impacted Module:** {bug['Module']}")
                st.write(f"**Expected:** {bug['Expected']}")
                st.info(f"Link: {bug['Evidence_Link']}")