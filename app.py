import streamlit as st
import pandas as pd
from openai import OpenAI
import re
from supabase import create_client, Client

# 1. Page Config
st.set_page_config(page_title="Principal QA Strategy Hub", layout="wide", page_icon="🛡️")

# 2. Schema Logic & Crash Protection
def ensure_standard_columns(df):
    required = ["ID", "Scenario", "Expected", "Status", "Severity", "Priority", "Evidence_Link", "Assigned_To", "Module", "Actual_Result"]
    for col in required:
        if col not in df.columns:
            if col == "Status": df[col] = "Pending"
            elif col == "Assigned_To": df[col] = "dev@team.com"
            elif col in ["Severity", "Priority"]: df[col] = "Major" if col == "Severity" else "P1"
            else: df[col] = ""
    df["Severity"] = df["Severity"].fillna("Major").replace("", "Major")
    df["Priority"] = df["Priority"].fillna("P1").replace("", "P1")
    df["Actual_Result"] = df["Actual_Result"].fillna("")
    return df

def clean_text(text):
    if not isinstance(text, str): return text
    return re.sub(r'\*\*|__', '', text).strip()

# 3. Initialization
if 'current_df' not in st.session_state:
    st.session_state.current_df = ensure_standard_columns(pd.DataFrame())
if 'audit_report' not in st.session_state:
    st.session_state.audit_report = ""

# 4. Connections
@st.cache_resource
def init_connection():
    try:
        return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    except:
        st.error("Check Supabase Secrets!")
        return None

supabase = init_connection()
client = OpenAI(base_url="https://api.groq.com/openai/v1", api_key=st.secrets["GROQ_API_KEY"])

# 5. Sidebar & Project Management
with st.sidebar:
    st.title("👥 Team QA Hub")
    try:
        res = supabase.table("qa_tracker").select("project_name").execute()
        project_list = sorted(list(set([r['project_name'] for r in res.data]))) if res.data else ["Project_Alpha"]
    except:
        project_list = ["Project_Alpha"]
    
    if 'active_id' not in st.session_state: st.session_state.active_id = project_list[0]
    current_proj = st.selectbox("Switch Project:", options=project_list + ["+ New Project"], 
                                index=project_list.index(st.session_state.active_id) if st.session_state.active_id in project_list else 0)
    
    if current_proj == "+ New Project":
        new_name = st.text_input("New Project Name:")
        if st.button("Create"):
            st.session_state.active_id, st.session_state.current_df, st.session_state.audit_report = new_name, ensure_standard_columns(pd.DataFrame()), ""
            st.rerun()
    else:
        st.session_state.active_id = current_proj

    if st.button("🌊 Sync Full Project (All Tabs)", use_container_width=True):
        supabase.table("qa_tracker").delete().eq("project_name", st.session_state.active_id).execute()
        data = st.session_state.current_df.to_dict(orient='records')
        for row in data: 
            row['project_name'] = st.session_state.active_id
            row['strategy_text'] = st.session_state.audit_report
        supabase.table("qa_tracker").insert(data).execute()
        st.success("Synced Full State!")

# Load Logic
if st.session_state.get('last_project') != st.session_state.active_id:
    res = supabase.table("qa_tracker").select("*").eq("project_name", st.session_state.active_id).execute()
    if res.data:
        st.session_state.current_df = ensure_standard_columns(pd.DataFrame(res.data))
        st.session_state.audit_report = res.data[0].get('strategy_text', "")
    st.session_state.last_project = st.session_state.active_id

# 6. Tabs
tab1, tab2, tab3 = st.tabs(["🏗️ Senior QA Audit & Strategy", "✅ Execution Log", "🐞 Bug Center"])

# --- TAB 1: SENIOR STRATEGY ---
with tab1:
    st.subheader("📋 Test Strategy & Quality Gate")
    user_req = st.text_area("Paste PRD Document:", height=200)
    
    if st.button("🚀 Generate Quality Strategy"):
        with st.spinner("Analyzing Strategy & 35+ Cases..."):
            prompt = f"""Analyze PRD: {user_req}
            1. REWRITE: Summary.
            2. FEATURE_TABLE: [Feature | Testing Focus | Edge Cases | Regression Impact].
            3. STRATEGY: Must-Pass criteria & PM Narrative.
            4. DOUBTS: Queries.
            [STOP_STRATEGY]
            5. TEST_CASES: List 35+ cases. 
            FORMAT: 'CASE: [Scenario] | [Expected] | [Severity] | [Priority]'"""
            
            res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role": "user", "content": prompt}]).choices[0].message.content
            st.session_state.audit_report = res
            
            # PARSER: Extract ONLY valid CASE lines
            case_text = res.split("[STOP_STRATEGY]")[1] if "[STOP_STRATEGY]" in res else res
            lines = [l.replace("CASE:", "").strip() for l in case_text.split("\n") if "CASE:" in l and "|" in l]
            
            rows = []
            for i, l in enumerate(lines):
                # Hard filter against instruction lines
                if any(x in l for x in ["FORMAT:", "[Scenario]", "35+", "Note:"]): continue
                p = l.split("|")
                if len(p) >= 2:
                    rows.append({
                        "ID": f"TC-{i+1}", "Scenario": clean_text(p[0]), "Expected": clean_text(p[1]), "Status": "Pending", 
                        "Severity": clean_text(p[2]) if len(p)>2 and p[2].strip() else "Major", 
                        "Priority": clean_text(p[3]) if len(p)>3 and p[3].strip() else "P1",
                        "Assigned_To": "dev@team.com", "Module": "", "Actual_Result": ""
                    })
            st.session_state.current_df = ensure_standard_columns(pd.DataFrame(rows))
            st.rerun()

    if st.session_state.audit_report:
        # NUCLEAR FILTER for Tab 1
        # 1. Split at the hard tag
        strategy_only = st.session_state.audit_report.split("[STOP_STRATEGY]")[0]
        # 2. Cut off at Point 5 regardless of naming
        strategy_only = re.split(r'\n\s*5[\.\)]', strategy_only, flags=re.IGNORECASE)[0]
        # 3. Clean up any trailing text like "Here are test cases:" or "Note:"
        strategy_only = re.split(r'Here are.*?test cases|Note:.*?severity', strategy_only, flags=re.IGNORECASE | re.DOTALL)[0]
        # 4. Final filter for any remaining CASE: lines
        strategy_only = "\n".join([line for line in strategy_only.split("\n") if "CASE:" not in line])
        st.markdown(strategy_only)

# --- TAB 2: EXECUTION LOG ---
with tab2:
    st.subheader(f"Execution Log: {st.session_state.active_id}")
    st.session_state.current_df = st.data_editor(
        st.session_state.current_df, use_container_width=True, hide_index=True, key="main_editor",
        column_config={
            "Status": st.column_config.SelectboxColumn("Status", options=["Pending", "Pass", "Fail"]),
            "Severity": st.column_config.SelectboxColumn("Severity", options=["Blocker", "Critical", "Major", "Minor"]),
            "Priority": st.column_config.SelectboxColumn("Priority", options=["P0", "P1", "P2", "P3"])
        }
    )

# --- TAB 3: BUG CENTER ---
with tab3:
    st.subheader("🐞 Bug Center")
    st.session_state.current_df = ensure_standard_columns(st.session_state.current_df)
    fails = st.session_state.current_df[st.session_state.current_df["Status"] == "Fail"]
    if fails.empty:
        st.info("No bugs found.")
    else:
        for idx, bug in fails.iterrows():
            with st.expander(f"🐞 BUG: {bug['ID']} - {bug['Scenario']}", expanded=True):
                c1, c2 = st.columns(2)
                st.session_state.current_df.at[idx, 'Module'] = c1.text_input("Module:", value=bug['Module'], key=f"mod_{bug['ID']}")
                st.session_state.current_df.at[idx, 'Assigned_To'] = c2.text_input("Assignee:", value=bug['Assigned_To'], key=f"asgn_{bug['ID']}")
                st.session_state.current_df.at[idx, 'Actual_Result'] = st.text_area("Actual Result / Details:", value=bug['Actual_Result'], key=f"desc_{bug['ID']}")
                st.markdown(f"**Expected:** {bug['Expected']}")
                st.info(f"Priority: {bug['Priority']} | Severity: {bug['Severity']}")