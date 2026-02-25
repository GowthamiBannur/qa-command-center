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
    # Hard-filling empty cells
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

# 3. Sidebar (Project Management)
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

    if st.button("🌊 Sync Changes for Team", use_container_width=True):
        supabase.table("qa_tracker").delete().eq("project_name", st.session_state.active_id).execute()
        data = st.session_state.current_df.to_dict(orient='records')
        for r in data: r['project_name'] = st.session_state.active_id
        supabase.table("qa_tracker").insert(data).execute()
        st.success("Synced!")

# 4. Tabs
t1, t2, t3 = st.tabs(["🏗️ Senior QA Audit", "✅ Execution Log", "🐞 Bug Center"])

# --- TAB 1: SENIOR AUDIT (STRATEGY ONLY) ---
with t1:
    st.subheader("📋 Test Strategy & Quality Gate")
    user_req = st.text_area("Paste PRD Document:", height=150)
    if st.button("🚀 Run Final Audit"):
        with st.spinner("Analyzing Leadership Strategy..."):
            prompt = f"""Analyze PRD: {user_req}. 
            Provide:
            1. REWRITE: Simplified version.
            2. FEATURE_TABLE: Columns [Feature | Testing Focus | Edge Cases | Regression Impact].
            3. RELEASE_QUALITY_GATE: [Must-Pass, Prioritization, Leadership Narrative, PM Transition].
            
            ---SEPARATOR---
            
            TEST_CASES: List 35+ cases. 
            FORMAT: 'CASE: [Scenario] | [Expected] | [Severity] | [Priority]'. 
            NO bolding."""
            
            res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role": "user", "content": prompt}]).choices[0].message.content
            st.session_state.audit_report = res
            
            # THE FIX: Split strictly by a hard separator so test cases NEVER show in Tab 1
            parts = res.split("---SEPARATOR---")
            strategy_text = parts[0]
            case_text = parts[1] if len(parts) > 1 else ""

            # PARSER: Only looks at the text AFTER the separator
            raw_lines = [l for l in case_text.split("\n") if "CASE:" in l and "|" in l]
            rows = []
            for i, l in enumerate(raw_lines):
                # Triple-check to kill header rows
                if any(x in l for x in ["FORMAT:", "[Scenario]", "30+ cases", "TEST_CASES:"]): continue
                
                p = l.replace("CASE:", "").strip().split("|")
                if len(p) >= 2:
                    rows.append({
                        "ID": f"TC-{i+1}", 
                        "Scenario": re.sub(r'^\d+\.\s*|\*\*|_', '', p[0]).strip(), 
                        "Expected": re.sub(r'\*\*|_', '', p[1]).strip(), 
                        "Status": "Pending", 
                        "Severity": p[2].strip() if len(p) > 2 and p[2].strip() else "Major", 
                        "Priority": p[3].strip() if len(p) > 3 and p[3].strip() else "P1", 
                        "Assigned_To": "dev@team.com"
                    })
            st.session_state.current_df = ensure_columns(pd.DataFrame(rows))
            st.rerun()
            
    if st.session_state.get('audit_report'): 
        # Display ONLY the strategy part
        st.markdown(st.session_state.audit_report.split("---SEPARATOR---")[0])

# --- TAB 2: EXECUTION LOG ---
with t2:
    st.subheader("✅ Execution Log")
    st.session_state.current_df = st.data_editor(st.session_state.current_df, use_container_width=True, hide_index=True, key="ed_main",
        column_config={
            "Status": st.column_config.SelectboxColumn("Status", options=["Pending", "Pass", "Fail"]),
            "Severity": st.column_config.SelectboxColumn("Severity", options=["Blocker", "Critical", "Major", "Minor"]),
            "Priority": st.column_config.SelectboxColumn("Priority", options=["P0", "P1", "P2", "P3"]),
            "Evidence_Link": st.column_config.LinkColumn("Attach URL")
        })

# --- TAB 3: BUG CENTER ---
with t3:
    st.subheader("🐞 Bug Center")
    fails = st.session_state.current_df[st.session_state.current_df["Status"] == "Fail"]
    if fails.empty:
        st.info("No bugs found.")
    else:
        for idx, bug in fails.iterrows():
            with st.expander(f"🐞 BUG: {bug['ID']} - {bug['Scenario']}", expanded=True):
                c1, c2 = st.columns(2)
                st.session_state.current_df.at[idx, 'Module'] = c1.text_input("Module:", value=bug['Module'], key=f"m_{bug['ID']}")
                st.session_state.current_df.at[idx, 'Assigned_To'] = c2.text_input("Assignee:", value=bug['Assigned_To'], key=f"a_{bug['ID']}")
                
                c3, c4 = st.columns(2)
                st.session_state.current_df.at[idx, 'Severity'] = c3.selectbox("Severity:", options=["Blocker", "Critical", "Major", "Minor"], index=["Blocker", "Critical", "Major", "Minor"].index(bug['Severity']) if bug['Severity'] in ["Blocker", "Critical", "Major", "Minor"] else 2, key=f"s_{bug['ID']}")
                st.session_state.current_df.at[idx, 'Priority'] = c4.selectbox("Priority:", options=["P0", "P1", "P2", "P3"], index=["P0", "P1", "P2", "P3"].index(bug['Priority']) if bug['Priority'] in ["P0", "P1", "P2", "P3"] else 1, key=f"p_{bug['ID']}")
                
                st.session_state.current_df.at[idx, 'Actual_Result'] = st.text_area("Description:", value=bug['Actual_Result'] if bug['Actual_Result'] else f"Requirement failed: {bug['Scenario']}", key=f"d_{bug['ID']}")
                
                st.markdown(f"**Expected:** {bug['Expected']}")
                if bug['Evidence_Link']: st.markdown(f"**🔗 Evidence:** {bug['Evidence_Link']}")