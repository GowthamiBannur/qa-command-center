import streamlit as st
import pandas as pd
from openai import OpenAI
import re
from supabase import create_client, Client

# 1. Page & Schema Config
st.set_page_config(page_title="Principal QA Hub", layout="wide", page_icon="🛡️")

def ensure_columns(df):
    """Guarantees every field is correctly mapped and filled."""
    cols = ["ID", "Scenario", "Expected", "Status", "Severity", "Priority", "Evidence_Link", "Assigned_To", "Module", "Actual_Result"]
    for c in cols:
        if c not in df.columns:
            if c == "Status": df[c] = "Pending"
            elif c == "Severity": df[c] = "Major"
            elif c == "Priority": df[c] = "P1"
            elif c == "Assigned_To": df[c] = "dev@team.com"
            else: df[c] = ""
    # Scrub empty data to prevent blank cells in Execution Log
    df["Severity"] = df["Severity"].fillna("Major").replace("", "Major")
    df["Priority"] = df["Priority"].fillna("P1").replace("", "P1")
    return df

# 2. Initialization & Connections
if 'current_df' not in st.session_state: st.session_state.current_df = ensure_columns(pd.DataFrame())
if 'audit_report' not in st.session_state: st.session_state.audit_report = None

@st.cache_resource
def init_db():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = init_db()
client = OpenAI(base_url="https://api.groq.com/openai/v1", api_key=st.secrets["GROQ_API_KEY"])

# 3. Sidebar (Project Management & Cloud Sync)
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
        st.success("Cloud Sync Complete!")

# 4. Load Data Logic
if st.session_state.get('last_project') != st.session_state.active_id:
    res = supabase.table("qa_tracker").select("*").eq("project_name", st.session_state.active_id).execute()
    st.session_state.current_df = ensure_columns(pd.DataFrame(res.data))
    st.session_state.last_project = st.session_state.active_id

# 5. Tabs
t1, t2, t3 = st.tabs(["🏗️ Senior QA Audit", "✅ Execution Log", "🐞 Bug Center"])

# --- TAB 1: SENIOR AUDIT (STRATEGY ONLY) ---
with t1:
    st.subheader("📋 Test Strategy & Quality Gate")
    user_req = st.text_area("Paste PRD Document:", height=150)
    if st.button("🚀 Generate Comprehensive Audit"):
        with st.spinner("Analyzing Leadership Strategy & Generating 35+ Test Cases..."):
            prompt = f"""Analyze PRD: {user_req}. 
            Provide strictly:
            1. REWRITE: Simplified version for quick review.
            2. FEATURE_TABLE: Columns [Feature | Testing Focus | Edge Cases | Regression Impact].
            3. RELEASE_QUALITY_GATE: 
               - Specific 'Must-Pass' criteria for production.
               - Prioritization strategy when overloaded.
               - Narrative to improve leadership perception.
               - PM transition narrative to reduce risk.
            4. TEST_CASES: List at least 35 specific cases. 
            FORMAT: 'CASE: [Scenario] | [Expected] | [Severity] | [Priority]'. 
            NO bolding. NO other text on CASE lines."""
            
            res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role": "user", "content": prompt}]).choices[0].message.content
            st.session_state.audit_report = res
            
            # PARSER: Scans for CASE: and pipes, ignoring junk headers
            raw_lines = [l for l in res.split("\n") if "CASE:" in l and "|" in l]
            rows = []
            for i, l in enumerate(raw_lines):
                if any(x in l for x in ["FORMAT:", "[Scenario]", "30+ cases"]): continue
                parts = l.replace("CASE:", "").strip().split("|")
                if len(parts) >= 2:
                    rows.append({
                        "ID": f"TC-{i+1}", 
                        "Scenario": re.sub(r'^\d+\.\s*|\*\*|_', '', parts[0]).strip(), 
                        "Expected": re.sub(r'\*\*|_', '', parts[1]).strip(), 
                        "Status": "Pending", 
                        "Severity": parts[2].strip() if len(parts) > 2 else "Major", 
                        "Priority": parts[3].strip() if len(parts) > 3 else "P1", 
                        "Assigned_To": "dev@team.com"
                    })
            st.session_state.current_df = ensure_columns(pd.DataFrame(rows))
            st.rerun()
            
    if st.session_state.get('audit_report'): 
        # Display only Strategy, completely removing test cases from this view
        st.markdown(st.session_state.audit_report.split("TEST_CASES")[0])

# --- TAB 2: EXECUTION LOG (CLEANED) ---
with t2:
    st.subheader(f"Execution Log: {st.session_state.active_id}")
    # Capturing edits immediately to prevent data loss
    st.session_state.current_df = st.data_editor(st.session_state.current_df, use_container_width=True, hide_index=True, key="ed_main",
        column_config={
            "Status": st.column_config.SelectboxColumn("Status", options=["Pending", "Pass", "Fail"]),
            "Severity": st.column_config.SelectboxColumn("Severity", options=["Blocker", "Critical", "Major", "Minor"]),
            "Priority": st.column_config.SelectboxColumn("Priority", options=["P0", "P1", "P2", "P3"]),
            "Evidence_Link": st.column_config.LinkColumn("Attach URL")
        })

# --- TAB 3: BUG CENTER (LINKED & EDITABLE) ---
with t3:
    st.subheader("🐞 Bug Center")
    fails = st.session_state.current_df[st.session_state.current_df["Status"] == "Fail"]
    if fails.empty:
        st.info("No failed cases logged.")
    else:
        for idx, bug in fails.iterrows():
            with st.expander(f"🐞 BUG: {bug['ID']} - {bug['Scenario']}", expanded=True):
                # Row 1: Module & Assignee
                c1, c2 = st.columns(2)
                st.session_state.current_df.at[idx, 'Module'] = c1.text_input("Module:", value=bug['Module'], key=f"m_{bug['ID']}")
                st.session_state.current_df.at[idx, 'Assigned_To'] = c2.text_input("Assignee:", value=bug['Assigned_To'], key=f"a_{bug['ID']}")
                
                # Row 2: Severity & Priority Dropdowns
                c3, c4 = st.columns(2)
                st.session_state.current_df.at[idx, 'Severity'] = c3.selectbox("Severity:", options=["Blocker", "Critical", "Major", "Minor"], index=["Blocker", "Critical", "Major", "Minor"].index(bug['Severity']) if bug['Severity'] in ["Blocker", "Critical", "Major", "Minor"] else 2, key=f"s_{bug['ID']}")
                st.session_state.current_df.at[idx, 'Priority'] = c4.selectbox("Priority:", options=["P0", "P1", "P2", "P3"], index=["P0", "P1", "P2", "P3"].index(bug['Priority']) if bug['Priority'] in ["P0", "P1", "P2", "P3"] else 1, key=f"p_{bug['ID']}")
                
                # Row 3: Full Description
                st.session_state.current_df.at[idx, 'Actual_Result'] = st.text_area("Bug Description / Actual Result:", value=bug['Actual_Result'] if bug['Actual_Result'] else f"FAILED: Expected {bug['Expected']}", key=f"d_{bug['ID']}")
                
                st.markdown(f"**Expected:** {bug['Expected']}")
                if bug['Evidence_Link']: st.markdown(f"**🔗 Evidence:** [{bug['Evidence_Link']}]({bug['Evidence_Link']})")