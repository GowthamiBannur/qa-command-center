import streamlit as st
import pandas as pd
from openai import OpenAI
import re
from supabase import create_client, Client

# 1. Page Config
st.set_page_config(page_title="Principal QA Hub", layout="wide", page_icon="🛡️")

# 2. Advanced Cleaning & Schema
def clean_tc_text(text):
    """Aggressively removes AI numbering and markdown artifacts."""
    text = re.sub(r'^\d+\.\s*', '', str(text)) # Removes "1. ", "5. " etc.
    text = re.sub(r'TEST_CASES:.*', '', text) # Removes internal headers
    return re.sub(r'\*\*|__', '', text).strip()

def ensure_columns(df):
    req = ["ID", "Scenario", "Expected", "Status", "Severity", "Priority", "Evidence_Link", "Assigned_To", "Module", "Actual_Result"]
    for col in req:
        if col not in df.columns:
            df[col] = "Pending" if col == "Status" else ""
    return df

# 3. Initialization
if 'current_df' not in st.session_state:
    st.session_state.current_df = ensure_columns(pd.DataFrame())
if 'audit_report' not in st.session_state:
    st.session_state.audit_report = None

# 4. DB Connection
@st.cache_resource
def init_db():
    try:
        return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    except:
        st.error("Missing Supabase Secrets!")
        return None

supabase = init_db()
client = OpenAI(base_url="https://api.groq.com/openai/v1", api_key=st.secrets["GROQ_API_KEY"])

# 5. Sidebar & Project Management
with st.sidebar:
    st.title("👥 Team QA Hub")
    res = supabase.table("qa_tracker").select("project_name").execute()
    p_list = sorted(list(set([r['project_name'] for r in res.data]))) if res.data else ["Project_Alpha"]
    
    if 'active_id' not in st.session_state: st.session_state.active_id = p_list[0]
    
    active = st.selectbox("Project:", options=p_list + ["+ New"], index=p_list.index(st.session_state.active_id) if st.session_state.active_id in p_list else 0)
    
    if active == "+ New":
        new_n = st.text_input("Project Name:")
        if st.button("Create"): 
            st.session_state.active_id = new_n
            st.session_state.current_df = ensure_columns(pd.DataFrame())
            st.rerun()
    else:
        st.session_state.active_id = active
        rename = st.text_input("Rename Project:", value=st.session_state.active_id)
        if st.button("Update Name Everywhere") and rename != st.session_state.active_id:
            supabase.table("qa_tracker").update({"project_name": rename}).eq("project_name", st.session_state.active_id).execute()
            st.session_state.active_id = rename
            st.rerun()

    st.divider()
    if st.button("🌊 Sync Changes for Team", use_container_width=True):
        supabase.table("qa_tracker").delete().eq("project_name", st.session_state.active_id).execute()
        data = st.session_state.current_df.to_dict(orient='records')
        for r in data: r['project_name'] = st.session_state.active_id
        supabase.table("qa_tracker").insert(data).execute()
        st.success("Cloud Updated!")

# 6. Load Logic
if st.session_state.get('last_project') != st.session_state.active_id:
    res = supabase.table("qa_tracker").select("*").eq("project_name", st.session_state.active_id).execute()
    st.session_state.current_df = ensure_columns(pd.DataFrame(res.data))
    st.session_state.last_project = st.session_state.active_id

# 7. Tabs
t1, t2, t3 = st.tabs(["🏗️ Senior Strategy", "✅ Execution Log", "🐞 Bug Center"])

with t1:
    st.subheader("📋 Test Strategy & Quality Gate")
    st.info("Focus: Regression Risk & Leadership Alignment")
    user_req = st.text_area("Paste PRD:", height=200)
    if st.button("🚀 Run Strategy Audit"):
        with st.spinner("Analyzing..."):
            prompt = f"Analyze PRD: {user_req}. 1. REWRITE (clear), 2. FEATURE_TABLE (with Regression Impact), 3. QUALITY_GATE (Prioritization/Must-Pass), 4. DOUBTS, 5. TEST_CASES: FORMAT 'CASE: [Scenario] | [Expected] | [Severity] | [Priority]'. No bolding."
            res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role": "user", "content": prompt}]).choices[0].message.content
            st.session_state.audit_report = res
            cases = [l.replace("CASE:", "").strip() for l in res.split("\n") if "CASE:" in l and "|" in l]
            rows = []
            for i, l in enumerate(cases):
                p = l.split("|")
                rows.append({
                    "ID": f"TC-{i+1}", "Scenario": clean_tc_text(p[0]), "Expected": clean_tc_text(p[1]),
                    "Status": "Pending", "Severity": clean_tc_text(p[2]) if len(p)>2 else "Major",
                    "Priority": clean_tc_text(p[3]) if len(p)>3 else "P1", "Assigned_To": "dev@team.com"
                })
            st.session_state.current_df = ensure_columns(pd.DataFrame(rows))
            st.rerun()
    if st.session_state.get('audit_report'):
        st.markdown(st.session_state.audit_report.split("TEST_CASES")[0])

with t2:
    st.subheader("✅ Execution Log")
    # THE FIX: Assign directly to session state to prevent "double enter" lag
    st.session_state.current_df = st.data_editor(
        st.session_state.current_df,
        use_container_width=True,
        hide_index=True,
        key="editor_main",
        column_config={
            "Status": st.column_config.SelectboxColumn("Status", options=["Pending", "Pass", "Fail"]),
            "Severity": st.column_config.SelectboxColumn("Severity", options=["Blocker", "Critical", "Major", "Minor"]),
            "Priority": st.column_config.SelectboxColumn("Priority", options=["P0", "P1", "P2", "P3"]),
            "Evidence_Link": st.column_config.LinkColumn("Attach URL")
        }
    )

with t3:
    st.subheader("🐞 Bug Center")
    df = st.session_state.current_df
    fails = df[df["Status"] == "Fail"]
    
    if fails.empty: st.info("No failed cases.")
    else:
        for idx, bug in fails.iterrows():
            with st.expander(f"FIX: {bug['ID']} - {bug['Scenario']}", expanded=True):
                colA, colB = st.columns(2)
                # EVERYTHING EDITABLE & SYNCED
                st.session_state.current_df.at[idx, 'Module'] = colA.text_input("Module:", value=bug['Module'], key=f"m_{bug['ID']}")
                st.session_state.current_df.at[idx, 'Assigned_To'] = colB.text_input("Assignee Email:", value=bug['Assigned_To'], key=f"e_{bug['ID']}")
                
                st.session_state.current_df.at[idx, 'Actual_Result'] = st.text_area("Actual Result / Bug Desc:", value=bug['Actual_Result'], key=f"act_{bug['ID']}")
                
                colC, colD = st.columns(2)
                st.session_state.current_df.at[idx, 'Severity'] = colC.selectbox("Severity:", options=["Blocker", "Critical", "Major", "Minor"], index=["Blocker", "Critical", "Major", "Minor"].index(bug['Severity']) if bug['Severity'] in ["Blocker", "Critical", "Major", "Minor"] else 2, key=f"sev_{bug['ID']}")
                st.session_state.current_df.at[idx, 'Priority'] = colD.selectbox("Priority:", options=["P0", "P1", "P2", "P3"], index=["P0", "P1", "P2", "P3"].index(bug['Priority']) if bug['Priority'] in ["P0", "P1", "P2", "P3"] else 1, key=f"pri_{bug['ID']}")
                
                st.markdown(f"**Expected:** {bug['Expected']}")
                if bug['Evidence_Link']:
                    st.markdown(f"**🔗 Evidence Link:** [{bug['Evidence_Link']}]({bug['Evidence_Link']})")
                else:
                    st.warning("⚠️ No evidence attached in Execution Log.")