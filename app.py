import streamlit as st
import pandas as pd
from openai import OpenAI
import re
from supabase import create_client, Client

# 1. Page Config
st.set_page_config(page_title="Team QA Strategy Hub", layout="wide", page_icon="🛡️")

# --- NEW: SAFETY FUNCTION ---
def ensure_standard_columns(df):
    """Ensures the DataFrame always has the columns needed for filtering and UI."""
    required_columns = ["ID", "Scenario", "Expected", "Status", "Severity", "Priority", "Evidence_Link", "Assigned_To", "Module"]
    for col in required_columns:
        if col not in df.columns:
            # Default 'Status' to 'Pending', others to empty string
            df[col] = "Pending" if col == "Status" else ""
    return df

# 2. Initialize State
if 'current_df' not in st.session_state:
    st.session_state.current_df = pd.DataFrame(columns=["ID", "Scenario", "Expected", "Status", "Severity", "Priority", "Evidence_Link", "Assigned_To", "Module"])
if 'audit_report' not in st.session_state:
    st.session_state.audit_report = None

# 3. Connections (Supabase & AI)
@st.cache_resource
def init_connection():
    try:
        return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    except:
        st.error("Check your Supabase Secrets!")
        return None

supabase = init_connection()
client = OpenAI(base_url="https://api.groq.com/openai/v1", api_key=st.secrets["GROQ_API_KEY"])

# 4. Database Helpers
def load_projects():
    if not supabase: return ["Default_Project"]
    res = supabase.table("qa_tracker").select("project_name").execute()
    return sorted(list(set([r['project_name'] for r in res.data]))) if res.data else ["Default_Project"]

def load_project_data(project_name):
    if not supabase: return pd.DataFrame()
    res = supabase.table("qa_tracker").select("*").eq("project_name", project_name).execute()
    df = pd.DataFrame(res.data)
    return ensure_standard_columns(df) # Safe Load

# 5. Sidebar
with st.sidebar:
    st.title("👥 Team QA Hub")
    project_list = load_projects()
    active_id = st.selectbox("Switch Project:", options=project_list + ["+ New Project"])
    
    if active_id == "+ New Project":
        new_name = st.text_input("New Project Name:")
        if st.button("Create"):
            active_id = new_name
            st.session_state.current_df = ensure_standard_columns(pd.DataFrame())
            st.rerun()

    if st.button("🌊 Sync Changes for Team"):
        supabase.table("qa_tracker").delete().eq("project_name", active_id).execute()
        if not st.session_state.current_df.empty:
            data = st.session_state.current_df.to_dict(orient='records')
            for row in data: row['project_name'] = active_id
            supabase.table("qa_tracker").insert(data).execute()
            st.success("Synced to Cloud!")

# 6. Load Project Logic
if st.session_state.get('last_project') != active_id:
    st.session_state.current_df = load_project_data(active_id)
    st.session_state.last_project = active_id

# 7. Tabs
tab1, tab2, tab3 = st.tabs(["🏗️ Senior QA Audit", "✅ Execution Log", "🐞 Bug Center"])

with tab1:
    st.subheader("📋 Requirement Strategy Audit")
    user_req = st.text_area("Paste PRD Document:", height=250)
    
    if st.button("🚀 Run Deep Strategy Audit"):
        with st.spinner("Analyzing E-commerce dependencies..."):
            prompt = f"Lead QA: Analyze {user_req}. Provide 1. Simplified Rewrite, 2. Feature Table with 'Regression Impact' column, 3. Doubts for Devs, 4. Risk & Mitigation, and 5. 30+ TEST_CASES in 'CASE: [Scenario] | [Expected] | [Severity] | [Priority]' format."
            res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role": "user", "content": prompt}]).choices[0].message.content
            st.session_state.audit_report = res
            
            # Extract TCs
            lines = [l.replace("CASE:", "").strip() for l in res.split("\n") if "CASE:" in l]
            rows = [{"ID": f"TC-{i+1}", "Scenario": l.split("|")[0].strip(), "Expected": l.split("|")[1].strip() if "|" in l else "Verify behavior", "Status": "Pending", "Severity": "Major", "Priority": "P1"} for i, l in enumerate(lines)]
            st.session_state.current_df = ensure_standard_columns(pd.DataFrame(rows))
            st.rerun()

    if st.session_state.get('audit_report'):
        st.markdown(st.session_state.audit_report)

with tab2:
    st.subheader(f"Execution Log: {active_id}")
    # Always ensure columns before rendering editor
    st.session_state.current_df = ensure_standard_columns(st.session_state.current_df)
    edited_df = st.data_editor(st.session_state.current_df, use_container_width=True, hide_index=True, 
                               column_config={"Status": st.column_config.SelectboxColumn("Status", options=["Pending", "Pass", "Fail"])})
    st.session_state.current_df = edited_df

with tab3:
    st.subheader("🐞 Bug Reports")
    # THE FIX: We ensure "Status" exists before filtering
    df = ensure_standard_columns(st.session_state.current_df)
    fails = df[df["Status"] == "Fail"]
    
    if fails.empty:
        st.info("No failed cases yet.")
    else:
        for _, bug in fails.iterrows():
            with st.expander(f"FIX: {bug['ID']} - {bug['Scenario']}"):
                st.write(f"**Expected Result:** {bug['Expected']}")
                st.error(f"Priority: {bug['Priority']} | Severity: {bug['Severity']}")