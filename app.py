import streamlit as st
import pandas as pd
from openai import OpenAI
import re
import urllib.parse
from supabase import create_client, Client # Requires: pip install supabase

# 1. Page Config
st.set_page_config(page_title="Team QA Command Center", layout="wide", page_icon="🛡️")

# 2. Connections (Database & AI)
@st.cache_resource
def init_connection():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = init_connection()
client = OpenAI(base_url="https://api.groq.com/openai/v1", api_key=st.secrets["GROQ_API_KEY"])

# 3. Database Functions (The Persistence Layer)
def load_projects():
    # Fetch list of unique project names
    res = supabase.table("qa_tracker").select("project_name").execute()
    if res.data:
        return sorted(list(set([r['project_name'] for r in res.data])))
    return ["Default_Project"]

def load_project_data(project_name):
    res = supabase.table("qa_tracker").select("*").eq("project_name", project_name).execute()
    return pd.DataFrame(res.data)

def sync_to_db(df, project_name):
    # Upsert logic: Delete existing and re-insert current state
    supabase.table("qa_tracker").delete().eq("project_name", project_name).execute()
    data_to_save = df.to_dict(orient='records')
    for row in data_to_save:
        row['project_name'] = project_name
    supabase.table("qa_tracker").insert(data_to_save).execute()

# 4. Sidebar: Team Collaboration
with st.sidebar:
    st.title("👥 Team QA Hub")
    
    project_list = load_projects()
    active_id = st.selectbox("Switch Project:", options=project_list + ["+ New Project"])
    
    if active_id == "+ New Project":
        new_name = st.text_input("Project Name:")
        if st.button("Create Project"):
            active_id = new_name
            st.rerun()

    st.markdown("---")
    manager_cc = st.text_input("CC Manager Email:", placeholder="manager@company.com")
    
    if st.button("🌊 Sync Changes for Team"):
        sync_to_db(st.session_state.current_df, active_id)
        st.success("Synced! Your team can now see these updates.")
    
    if st.button("🗑️ Delete Project Permanently", type="secondary"):
        supabase.table("qa_tracker").delete().eq("project_name", active_id).execute()
        st.rerun()

# 5. Load Data into Session
if 'current_df' not in st.session_state or st.session_state.get('last_project') != active_id:
    df = load_project_data(active_id)
    if df.empty:
        df = pd.DataFrame(columns=["ID", "Scenario", "Expected", "Status", "Severity", "Priority", "Evidence_Link", "Assigned_To", "Module"])
    st.session_state.current_df = df
    st.session_state.last_project = active_id

# 6. Tabs
tab1, tab2, tab3 = st.tabs(["🏗️ Senior QA Audit", "✅ Execution Log", "🐞 Bug Center"])

with tab1:
    col1, col2 = st.columns([1, 1.2])
    with col1:
        st.subheader("📋 Requirements Document")
        user_req = st.text_area("Paste PRD:", height=300)
        if st.button("🚀 Run Team Audit (30+ Cases)"):
            with st.spinner("Lead QA Engineer at work..."):
                prompt = f"Lead QA: Generate 30+ scenarios for {user_req}. Format: 'CASE: [Scenario] | [Expected] | [Severity] | [Priority]'"
                res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role": "user", "content": prompt}]).choices[0].message.content
                lines = [l.replace("CASE:", "").strip() for l in res.split("\n") if "CASE:" in l]
                rows = []
                for i, l in enumerate(lines):
                    p = l.split("|")
                    if len(p) >= 2:
                        rows.append({"ID": f"TC-{i+1}", "Scenario": p[0].strip(), "Expected": p[1].strip(), "Status": "Pending", "Severity": "Major", "Priority": "P1", "Evidence_Link": "", "Assigned_To": "dev@team.com", "Module": "Core"})
                st.session_state.current_df = pd.DataFrame(rows)
                sync_to_db(st.session_state.current_df, active_id)
                st.rerun()

with tab2:
    st.subheader(f"Project: {active_id}")
    edited_df = st.data_editor(st.session_state.current_df, use_container_width=True, hide_index=True, key="main_editor")
    st.session_state.current_df = edited_df

with tab3:
    st.subheader("🐞 Team Bug Reports")
    fails = st.session_state.current_df[st.session_state.current_df["Status"] == "Fail"]
    for idx, bug in fails.iterrows():
        with st.expander(f"FIX REQUIRED: {bug['ID']}"):
            st.write(f"**Scenario:** {bug['Scenario']}")
            st.write(f"**Evidence:** {bug['Evidence_Link']}")
            # Standard mailto logic here...