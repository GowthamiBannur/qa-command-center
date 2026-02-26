import streamlit as st
import pandas as pd
from openai import OpenAI
import re
import urllib.parse
from supabase import create_client, Client

# 1. Page Config
st.set_page_config(page_title="Principal QA Strategy Hub", layout="wide", page_icon="🛡️")

# 2. Cleanup & Schema Logic
def clean_text(text):
    """Removes ** and __ and leading/trailing whitespace."""
    if not isinstance(text, str): return text
    return re.sub(r'\*\*|__', '', text).strip()

def ensure_standard_columns(df):
    required = ["ID", "Scenario", "Expected", "Status", "Severity", "Priority", "Evidence_Link", "Assigned_To", "Module"]
    for col in required:
        if col not in df.columns:
            df[col] = "Pending" if col == "Status" else ""
    return df

# 3. Initialization
if 'current_df' not in st.session_state:
    st.session_state.current_df = pd.DataFrame(columns=["ID", "Scenario", "Expected", "Status", "Severity", "Priority", "Evidence_Link", "Assigned_To", "Module"])
if 'audit_report' not in st.session_state:
    st.session_state.audit_report = None

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

# 5. Database Functions
def load_projects():
    if not supabase: return ["Project_Alpha"]
    res = supabase.table("qa_tracker").select("project_name").execute()
    return sorted(list(set([r['project_name'] for r in res.data]))) if res.data else ["Project_Alpha"]

def rename_project_in_db(old_name, new_name):
    if not supabase: return
    supabase.table("qa_tracker").update({"project_name": new_name}).eq("project_name", old_name).execute()

# 6. Sidebar: Project Management
with st.sidebar:
    st.title("👥 Team QA Hub")
    project_list = load_projects()
    
    if 'active_id' not in st.session_state:
        st.session_state.active_id = project_list[0]
    
    current_proj = st.selectbox("Switch Project:", options=project_list + ["+ New Project"], 
                                index=project_list.index(st.session_state.active_id) if st.session_state.active_id in project_list else 0)
    
    if current_proj == "+ New Project":
        new_name = st.text_input("New Project Name:")
        if st.button("Create"):
            st.session_state.active_id = new_name
            st.session_state.current_df = ensure_standard_columns(pd.DataFrame())
            st.rerun()
    else:
        st.session_state.active_id = current_proj
        # Rename logic
        edit_name = st.text_input("Rename Current Project:", value=st.session_state.active_id)
        if st.button("Update Everywhere") and edit_name != st.session_state.active_id:
            rename_project_in_db(st.session_state.active_id, edit_name)
            st.session_state.active_id = edit_name
            st.rerun()

    st.markdown("---")
    if st.button("🌊 Sync Changes for Team", use_container_width=True):
        supabase.table("qa_tracker").delete().eq("project_name", st.session_state.active_id).execute()
        if not st.session_state.current_df.empty:
            data = st.session_state.current_df.to_dict(orient='records')
            for row in data: row['project_name'] = st.session_state.active_id
            supabase.table("qa_tracker").insert(data).execute()
            st.success("Synced!")

# 7. Load Data Logic
if st.session_state.get('last_project') != st.session_state.active_id:
    res = supabase.table("qa_tracker").select("*").eq("project_name", st.session_state.active_id).execute()
    df = pd.DataFrame(res.data)
    st.session_state.current_df = ensure_standard_columns(df)
    st.session_state.last_project = st.session_state.active_id

# 8. Tabs
tab1, tab2, tab3 = st.tabs(["🏗️ Senior QA Audit & Strategy", "✅ Execution Log", "🐞 Bug Center"])

# --- TAB 1: SENIOR STRATEGY ---
with tab1:
    st.subheader("📋 Test Strategy & Release Quality Gate")
    user_req = st.text_area("Paste PRD Document:", height=200)
    
    if st.button("🚀 Generate Quality Strategy"):
        with st.spinner("Analyzing Strategy..."):
            prompt = f"""
            Analyze this PRD: {user_req}
            
            1. REWRITE: Clear, simplified summary.
            2. FEATURE_TABLE: Columns [Feature | Testing Focus | Edge Cases | Regression Impact].
            3. TEST_STRATEGY_&_QUALITY_GATE:
               - List 'Must-Pass' criteria for production.
               - Prioritization for overloaded sprints.
               - Narrative for PM transition.
            4. DOUBTS: Queries for Dev/PO.
            
            res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role": "user", "content": prompt}]).choices[0].message.content
            st.session_state.audit_report = res
            
            # Reset ID and parse Test Cases
            lines = [l.replace("CASE:", "").strip() for l in res.split("\n") if "CASE:" in l]
            rows = []
            for i, l in enumerate(lines):
                p = l.split("|")
                if len(p) >= 2:
                    rows.append({
                        "ID": f"TC-{i+1}", 
                        "Scenario": clean_text(p[0]), 
                        "Expected": clean_text(p[1]), 
                        "Status": "Pending", 
                        "Severity": clean_text(p[2]) if len(p)>2 else "Major", 
                        "Priority": clean_text(p[3]) if len(p)>3 else "P1",
                        "Assigned_To": "dev@team.com"
                    })
            st.session_state.current_df = ensure_standard_columns(pd.DataFrame(rows))
            st.rerun()

    if st.session_state.get('audit_report'):
        # Only show the Strategy portion
        strategy_view = st.session_state.audit_report.split("TEST_CASES")[0]
        st.markdown(strategy_view)

# --- TAB 2: EXECUTION LOG (FIXED SYNC) ---
with tab2:
    st.subheader(f"Execution Log: {st.session_state.active_id}")
    
    # Using key and data_editor properly to ensure state updates on first edit
    edited_df = st.data_editor(
        st.session_state.current_df,
        use_container_width=True,
        hide_index=True,
        key="main_editor",
        column_config={
            "Status": st.column_config.SelectboxColumn("Status", options=["Pending", "Pass", "Fail"]),
            "Severity": st.column_config.SelectboxColumn("Severity", options=["Blocker", "Critical", "Major", "Minor"]),
            "Priority": st.column_config.SelectboxColumn("Priority", options=["P0", "P1", "P2", "P3"]),
            "Evidence_Link": st.column_config.LinkColumn("Evidence URL")
        }
    )
    # Immediate state update
    st.session_state.current_df = edited_df

# --- TAB 3: BUG CENTER ---
with tab3:
    st.subheader("🐞 Bug Center")
    df = st.session_state.current_df
    fails = df[df["Status"] == "Fail"]
    
    if fails.empty:
        st.info("No failed cases.")
    else:
        for idx, bug in fails.iterrows():
            with st.expander(f"BUG: {bug['ID']} - {bug['Scenario']}"):
                c1, c2 = st.columns(2)
                
                # These update st.session_state.current_df directly via indexing
                mod = c1.text_input("Module:", value=bug['Module'], key=f"mod_{bug['ID']}")
                st.session_state.current_df.at[idx, 'Module'] = mod
                
                assign = c2.text_input("Assigned To:", value=bug['Assigned_To'], key=f"assign_{bug['ID']}")
                st.session_state.current_df.at[idx, 'Assigned_To'] = assign
                
                st.markdown(f"**Description:** {bug['Scenario']}")
                st.markdown(f"**Expected:** {bug['Expected']}")
                st.markdown(f"**Evidence:** [{bug['Evidence_Link']}]({bug['Evidence_Link']})" if bug['Evidence_Link'] else "None")
                
                st.info(f"Priority: {bug['Priority']} | Severity: {bug['Severity']}")