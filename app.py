import streamlit as st
import pandas as pd
from openai import OpenAI
import re
from supabase import create_client, Client

# 1. Page & Schema Config
st.set_page_config(page_title="Principal QA Hub", layout="wide", page_icon="🛡️")

def ensure_columns(df):
    """Guarantees all features (Bugs, Evidence, Assignees) have a place to live."""
    cols = ["ID", "Scenario", "Expected", "Status", "Severity", "Priority", "Evidence_Link", "Assigned_To", "Module", "Actual_Result"]
    for c in cols:
        if c not in df.columns:
            df[c] = "Pending" if c == "Status" else ("Major" if c == "Severity" else ("P1" if c == "Priority" else ""))
    return df

# 2. Initialization & Connections
if 'current_df' not in st.session_state: st.session_state.current_df = ensure_columns(pd.DataFrame())
if 'audit_report' not in st.session_state: st.session_state.audit_report = None

@st.cache_resource
def init_db():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = init_db()
client = OpenAI(base_url="https://api.groq.com/openai/v1", api_key=st.secrets["GROQ_API_KEY"])

# 3. Sidebar (Project Rename & Team Sync)
with st.sidebar:
    st.title("👥 Team QA Hub")
    res = supabase.table("qa_tracker").select("project_name").execute()
    p_list = sorted(list(set([r['project_name'] for r in res.data]))) if res.data else ["Project_Alpha"]
    if 'active_id' not in st.session_state: st.session_state.active_id = p_list[0]
    
    active = st.selectbox("Switch Project:", options=p_list + ["+ New"], index=p_list.index(st.session_state.active_id) if st.session_state.active_id in p_list else 0)
    
    if active == "+ New":
        new_n = st.text_input("Name:")
        if st.button("Create"): 
            st.session_state.active_id, st.session_state.current_df = new_n, ensure_columns(pd.DataFrame())
            st.rerun()
    else:
        st.session_state.active_id = active
        ren = st.text_input("Rename:", value=st.session_state.active_id)
        if st.button("Update Everywhere") and ren != st.session_state.active_id:
            supabase.table("qa_tracker").update({"project_name": ren}).eq("project_name", st.session_state.active_id).execute()
            st.session_state.active_id = ren
            st.rerun()

    if st.button("🌊 Sync Changes for Team", use_container_width=True):
        supabase.table("qa_tracker").delete().eq("project_name", st.session_state.active_id).execute()
        data = st.session_state.current_df.to_dict(orient='records')
        for r in data: r['project_name'] = st.session_state.active_id
        supabase.table("qa_tracker").insert(data).execute()
        st.success("Synced to Cloud!")

# 4. Load Data
if st.session_state.get('last_project') != st.session_state.active_id:
    res = supabase.table("qa_tracker").select("*").eq("project_name", st.session_state.active_id).execute()
    st.session_state.current_df = ensure_columns(pd.DataFrame(res.data))
    st.session_state.last_project = st.session_state.active_id

# 5. Tabs
t1, t2, t3 = st.tabs(["🏗️ Senior Strategy", "✅ Execution Log", "🐞 Bug Center"])

with t1:
    st.subheader("📋 Test Strategy & Quality Gate")
    user_req = st.text_area("Paste PRD:", height=150)
    if st.button("🚀 Run Strategy Audit"):
        with st.spinner("Analyzing Strategy..."):
            prompt = f"Analyze PRD: {user_req}. Provide REWRITE, FEATURE_TABLE (with Regression), QUALITY_GATE, and 30+ TEST_CASES: FORMAT 'CASE: [Scenario] | [Expected] | [Severity] | [Priority]'. No bolding."
            res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role": "user", "content": prompt}]).choices[0].message.content
            st.session_state.audit_report = res
            cases = [l.replace("CASE:", "").strip() for l in res.split("\n") if "CASE:" in l]
            rows = []
            for i, l in enumerate(cases):
                p = l.split("|")
                if len(p) >= 2:
                    rows.append({"ID": f"TC-{i+1}", "Scenario": re.sub(r'^\d+\.\s*|\*\*|_', '', p[0]).strip(), 
                                 "Expected": re.sub(r'\*\*|_', '', p[1]).strip(), "Status": "Pending", 
                                 "Severity": p[2].strip() if len(p)>2 else "Major", "Priority": p[3].strip() if len(p)>3 else "P1", "Assigned_To": "dev@team.com"})
            st.session_state.current_df = ensure_columns(pd.DataFrame(rows))
            st.rerun()
    if st.session_state.get('audit_report'): st.markdown(st.session_state.audit_report.split("TEST_CASES")[0])

with t2:
    st.subheader(f"Log: {st.session_state.active_id}")
    st.session_state.current_df = st.data_editor(st.session_state.current_df, use_container_width=True, hide_index=True, key="ed_main",
        column_config={
            "Status": st.column_config.SelectboxColumn("Status", options=["Pending", "Pass", "Fail"]),
            "Severity": st.column_config.SelectboxColumn("Severity", options=["Blocker", "Critical", "Major", "Minor"]),
            "Priority": st.column_config.SelectboxColumn("Priority", options=["P0", "P1", "P2", "P3"]),
            "Evidence_Link": st.column_config.LinkColumn("Evidence URL")
        })

with t3:
    st.subheader("🐞 Bug Center")
    fails = st.session_state.current_df[st.session_state.current_df["Status"] == "Fail"]
    if fails.empty: st.info("No failed cases.")
    else:
        for idx, bug in fails.iterrows():
            with st.expander(f"BUG: {bug['ID']} - {bug['Scenario']}", expanded=True):
                c1, c2 = st.columns(2)
                st.session_state.current_df.at[idx, 'Module'] = c1.text_input("Module:", value=bug['Module'], key=f"m_{bug['ID']}")
                st.session_state.current_df.at[idx, 'Assigned_To'] = c2.text_input("Assignee:", value=bug['Assigned_To'], key=f"e_{bug['ID']}")
                st.session_state.current_df.at[idx, 'Actual_Result'] = st.text_area("Actual Result:", value=bug['Actual_Result'], key=f"ar_{bug['ID']}")
                st.markdown(f"**Expected:** {bug['Expected']}\n\n**Evidence:** {bug['Evidence_Link']}")