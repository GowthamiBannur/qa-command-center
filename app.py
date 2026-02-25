import streamlit as st
import pandas as pd
from openai import OpenAI
import re
import urllib.parse
from supabase import create_client, Client

# 1. Page Config
st.set_page_config(page_title="Team QA Strategy Hub", layout="wide", page_icon="🛡️")

# 2. Safety & Initialization
def ensure_standard_columns(df):
    required = ["ID", "Scenario", "Expected", "Status", "Severity", "Priority", "Evidence_Link", "Assigned_To", "Module"]
    for col in required:
        if col not in df.columns:
            df[col] = "Pending" if col == "Status" else ""
    return df

if 'current_df' not in st.session_state:
    st.session_state.current_df = pd.DataFrame(columns=["ID", "Scenario", "Expected", "Status", "Severity", "Priority", "Evidence_Link", "Assigned_To", "Module"])
if 'audit_report' not in st.session_state:
    st.session_state.audit_report = None

# 3. Connections
@st.cache_resource
def init_connection():
    try:
        return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    except:
        st.error("Check Supabase Secrets!")
        return None

supabase = init_connection()
client = OpenAI(base_url="https://api.groq.com/openai/v1", api_key=st.secrets["GROQ_API_KEY"])

# 4. Database Helpers
def load_projects():
    if not supabase: return ["Project_Alpha"]
    res = supabase.table("qa_tracker").select("project_name").execute()
    return sorted(list(set([r['project_name'] for r in res.data]))) if res.data else ["Project_Alpha"]

def rename_project_in_db(old_name, new_name):
    if not supabase: return
    supabase.table("qa_tracker").update({"project_name": new_name}).eq("project_name", old_name).execute()

# 5. Sidebar: Renamable Projects & Team Sync
with st.sidebar:
    st.title("👥 Team QA Hub")
    project_list = load_projects()
    
    # PROJECT RENAMING LOGIC
    if 'active_id' not in st.session_state:
        st.session_state.active_id = project_list[0]
    
    current_proj = st.selectbox("Switch Project:", options=project_list + ["+ New Project"], index=project_list.index(st.session_state.active_id) if st.session_state.active_id in project_list else 0)
    
    if current_proj == "+ New Project":
        new_name = st.text_input("Enter New Project Name:")
        if st.button("Create"):
            st.session_state.active_id = new_name
            st.session_state.current_df = ensure_standard_columns(pd.DataFrame())
            st.rerun()
    else:
        st.session_state.active_id = current_proj
        # Rename Functionality
        new_name = st.text_input("Rename Current Project:", value=st.session_state.active_id)
        if st.button("Update Name Everywhere") and new_name != st.session_state.active_id:
            rename_project_in_db(st.session_state.active_id, new_name)
            st.session_state.active_id = new_name
            st.rerun()

    st.markdown("---")
    if st.button("🌊 Sync Changes for Team", use_container_width=True):
        supabase.table("qa_tracker").delete().eq("project_name", st.session_state.active_id).execute()
        if not st.session_state.current_df.empty:
            data = st.session_state.current_df.to_dict(orient='records')
            for row in data: row['project_name'] = st.session_state.active_id
            supabase.table("qa_tracker").insert(data).execute()
            st.success("Synced to Cloud!")

# 6. Load Project Logic
if st.session_state.get('last_project') != st.session_state.active_id:
    res = supabase.table("qa_tracker").select("*").eq("project_name", st.session_state.active_id).execute()
    st.session_state.current_df = ensure_standard_columns(pd.DataFrame(res.data))
    st.session_state.last_project = st.session_state.active_id

# 7. Tabs
tab1, tab2, tab3 = st.tabs(["🏗️ Senior QA Strategy", "✅ Execution Log", "🐞 Bug Center"])

# --- TAB 1: STRATEGY & QUALITY GATES ---
with tab1:
    st.subheader("📋 Test Strategy & Release Quality Gate")
    user_req = st.text_area("Paste PRD Document:", height=200)
    
    if st.button("🚀 Generate Quality Strategy"):
        with st.spinner("Analyzing Risks & Quality Gates..."):
            prompt = f"""
            Analyze this E-commerce PRD: {user_req}
            1. REWRITE: Simplified requirement.
            2. FEATURE_TABLE: Columns [Feature | Testing Focus | Edge Cases | Regression Impact].
            3. RELEASE_QUALITY_GATE: List 'Must-Pass' criteria for production.
            4. DOUBTS: Queries for Dev/PO.
            5. RISK_MITIGATION: Table of risks.
            6. TEST_CASES: 30+ cases. FORMAT: 'CASE: [Scenario] | [Expected] | [Severity] | [Priority]'
            (Note: Do not use ** or __ in the CASE lines).
            """
            res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role": "user", "content": prompt}]).choices[0].message.content
            st.session_state.audit_report = res
            
            # Extract Test Cases
            lines = [l.replace("CASE:", "").replace("**", "").replace("__", "").strip() for l in res.split("\n") if "CASE:" in l]
            rows = [{"ID": f"TC-{i+1}", "Scenario": l.split("|")[0].strip(), "Expected": l.split("|")[1].strip() if "|" in l else "Verify behavior", "Status": "Pending", "Severity": "Major", "Priority": "P1"} for i, l in enumerate(lines)]
            st.session_state.current_df = ensure_standard_columns(pd.DataFrame(rows))
            st.rerun()

    if st.session_state.get('audit_report'):
        # Filter out the TEST_CASES from display in Tab 1 to keep it Strategic
        display_report = st.session_state.audit_report.split("TEST_CASES")[0]
        st.markdown(display_report)

# --- TAB 2: EXECUTION LOG (FIXED DOUBLE ENTER & EVIDENCE) ---
with tab2:
    st.subheader(f"Execution Log: {st.session_state.active_id}")
    
    # Use on_change to force update session state immediately
    def update_df():
        st.session_state.current_df = st.session_state["editor_key"]["edited_rows"]

    edited_df = st.data_editor(
        st.session_state.current_df, 
        use_container_width=True, 
        hide_index=True, 
        key="editor_key",
        column_config={
            "Status": st.column_config.SelectboxColumn("Status", options=["Pending", "Pass", "Fail"]),
            "Evidence_Link": st.column_config.LinkColumn("Evidence URL")
        }
    )
    # This prevents the 'double enter' bug by ensuring state is updated every frame
    st.session_state.current_df = edited_df

    st.divider()
    st.subheader("🎥 Attach Evidence Link")
    ec1, ec2 = st.columns([1, 2])
    target_tc = ec1.selectbox("Select TC ID:", options=st.session_state.current_df["ID"])
    link_val = ec2.text_input("Paste Evidence URL:")
    if st.button("🔗 Save Evidence"):
        idx = st.session_state.current_df.index[st.session_state.current_df["ID"] == target_tc][0]
        st.session_state.current_df.at[idx, "Evidence_Link"] = link_val
        st.success("Linked!")
        st.rerun()

# --- TAB 3: BUG CENTER (RESTORED VIEW) ---
with tab3:
    st.subheader("🐞 Bug Reporter")
    df = st.session_state.current_df
    fails = df[df["Status"] == "Fail"]
    
    if fails.empty:
        st.info("No failed cases logged.")
    else:
        for idx, bug in fails.iterrows():
            with st.expander(f"BUG: {bug['ID']} - {bug['Scenario']}"):
                c1, c2 = st.columns(2)
                # Editable fields that sync back to main DF
                mod = c1.text_input("Module:", value=bug['Module'], key=f"mod_{bug['ID']}")
                st.session_state.current_df.at[idx, "Module"] = mod
                
                assign = c2.text_input("Assigned To:", value=bug['Assigned_To'], key=f"assign_{bug['ID']}")
                st.session_state.current_df.at[idx, "Assigned_To"] = assign
                
                desc = st.text_area("Bug Description:", value=f"Requirement failed: {bug['Scenario']}\nExpected: {bug['Expected']}", key=f"desc_{bug['ID']}")
                
                st.markdown(f"**🔗 Evidence attached in Execution Log:** [{bug['Evidence_Link']}]({bug['Evidence_Link']})" if bug['Evidence_Link'] else "**🔗 Evidence: Not provided.**")
                
                st.warning(f"Severity: {bug['Severity']} | Priority: {bug['Priority']}")