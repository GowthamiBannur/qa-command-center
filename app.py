import streamlit as st
import pandas as pd
from openai import OpenAI
import re
import urllib.parse
from supabase import create_client, Client

# 1. Page Config
st.set_page_config(page_title="Team QA Strategy Hub", layout="wide", page_icon="🛡️")

# 2. INITIALIZE SESSION STATE (The Fix)
# We define these at the very start so the app knows they exist from second one.
if 'current_df' not in st.session_state:
    st.session_state.current_df = pd.DataFrame(columns=["ID", "Scenario", "Expected", "Status", "Severity", "Priority", "Evidence_Link", "Assigned_To", "Module"])
if 'audit_report' not in st.session_state:
    st.session_state.audit_report = None

# 3. Connections
@st.cache_resource
def init_connection():
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        return create_client(url, key)
    except Exception as e:
        st.error("Missing Supabase Secrets!")
        return None

supabase = init_connection()
client = OpenAI(base_url="https://api.groq.com/openai/v1", api_key=st.secrets["GROQ_API_KEY"])

# 4. Database Functions
def load_projects():
    if not supabase: return ["Default_Project"]
    res = supabase.table("qa_tracker").select("project_name").execute()
    return sorted(list(set([r['project_name'] for r in res.data]))) if res.data else ["Default_Project"]

def load_project_data(project_name):
    if not supabase: return pd.DataFrame()
    res = supabase.table("qa_tracker").select("*").eq("project_name", project_name).execute()
    return pd.DataFrame(res.data)

def sync_to_db(df, project_name):
    if not supabase: return
    supabase.table("qa_tracker").delete().eq("project_name", project_name).execute()
    if not df.empty:
        data_to_save = df.to_dict(orient='records')
        for row in data_to_save: row['project_name'] = project_name
        supabase.table("qa_tracker").insert(data_to_save).execute()

# 5. Sidebar
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

# 6. Load Project Logic
if st.session_state.get('last_project') != active_id:
    df = load_project_data(active_id)
    if not df.empty:
        st.session_state.current_df = df
    st.session_state.last_project = active_id

# 7. Tabs
tab1, tab2, tab3 = st.tabs(["🏗️ Senior QA Audit & Strategy", "✅ Execution Log", "🐞 Bug Center"])

with tab1:
    st.subheader("📋 Requirement Intelligence & Impact Analysis")
    user_req = st.text_area("Paste PRD / Requirement Document here:", height=300)
    
    if st.button("🚀 Run Deep Strategy Audit"):
        with st.spinner("Analyzing E-commerce dependencies..."):
            prompt = f"Senior QA Lead: Analyze this E-comm PRD: {user_req}. Provide REWRITE, FEATURE_TABLE (with Regression Impact), DOUBTS, RISK_MITIGATION, and 30+ TEST_CASES."
            response = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role": "user", "content": prompt}]).choices[0].message.content
            st.session_state.audit_report = response
            
            # Parsing logic
            lines = [l.replace("CASE:", "").strip() for l in response.split("\n") if "CASE:" in l]
            rows = []
            for i, l in enumerate(lines):
                p = l.split("|")
                if len(p) >= 2:
                    rows.append({"ID": f"TC-{i+1}", "Scenario": p[0].strip(), "Expected": p[1].strip(), "Status": "Pending", "Severity": p[2].strip() if len(p)>2 else "Major", "Priority": p[3].strip() if len(p)>3 else "P1", "Evidence_Link": "", "Assigned_To": "dev@team.com", "Module": "Core"})
            st.session_state.current_df = pd.DataFrame(rows)
            st.rerun()

    # The Crash-Proof Check
    if st.session_state.get('audit_report'):
        st.markdown("---")
        st.markdown(st.session_state.audit_report)

with tab2:
    st.subheader(f"Project: {active_id}")
    st.session_state.current_df = st.data_editor(st.session_state.current_df, use_container_width=True, hide_index=True)

with tab3:
    st.subheader("🐞 Team Bug Reports")
    fails = st.session_state.current_df[st.session_state.current_df["Status"] == "Fail"]
    if fails.empty: st.info("No bugs found.")
    else:
        for idx, bug in fails.iterrows():
            with st.expander(f"BUG: {bug['ID']} - {bug['Scenario']}"):
                st.write(f"**Expected:** {bug['Expected']}")
                st.write(f"**Side Effects:** {bug['Module']}")