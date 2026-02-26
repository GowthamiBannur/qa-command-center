import streamlit as st
import pandas as pd
from openai import OpenAI
import re
from supabase import create_client, Client

# 1. Page Config & Re-stabilized Layout
st.set_page_config(page_title="Principal QA Hub", layout="wide", page_icon="🛡️")

# 2. Connections (Restored Original Reliable Connection)
@st.cache_resource
def init_connection():
    try: return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    except: return None

supabase = init_connection()
client = OpenAI(base_url="https://api.groq.com/openai/v1", api_key=st.secrets["GROQ_API_KEY"])

# 3. Schema & Missing Column Protection
def ensure_standard_columns(df):
    required = ["ID", "Scenario", "Expected", "Status", "Severity", "Priority", "Assigned_To", "Module", "Actual_Result"]
    for col in required:
        if col not in df.columns:
            df[col] = "Pending" if col == "Status" else ("P1" if col == "Priority" else ("Major" if col == "Severity" else ""))
    return df

# 4. State Management
if 'current_df' not in st.session_state: st.session_state.current_df = ensure_standard_columns(pd.DataFrame())
if 'audit_report' not in st.session_state: st.session_state.audit_report = ""

# 5. Sidebar Project Management (Simplified to stop breaks)
with st.sidebar:
    st.title("👥 Team QA Hub")
    proj_name = st.text_input("Project Name:", value="Project_Alpha")
    
    if st.button("🌊 Sync & Save Project"):
        # Clear and Sync logic that actually works
        supabase.table("qa_tracker").delete().eq("project_name", proj_name).execute()
        data = st.session_state.current_df.to_dict(orient='records')
        for row in data: 
            row['project_name'] = proj_name
            row['strategy_text'] = st.session_state.audit_report
        supabase.table("qa_tracker").insert(data).execute()
        st.success("Full Project State Saved.")

# 6. Tabs
tab1, tab2, tab3 = st.tabs(["🏗️ Senior Audit & Doubts", "✅ Execution Log", "🐞 Bug Center"])

# --- TAB 1: SENIOR AUDIT ---
with tab1:
    user_req = st.text_area("Paste PRD Document:", height=150)
    if st.button("🚀 Generate Audit"):
        with st.spinner("Analyzing..."):
            prompt = f"PRD: {user_req}\n\n1. Summary\n2. Feature Table\n3. Strategy\n4. PM Doubts\n###SPLIT###\n5. Test Cases. Format: 'CASE: Scenario | Expected | Severity | Priority'"
            res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role": "user", "content": prompt}]).choices[0].message.content
            st.session_state.audit_report = res
            
            # Parsing Test Cases for Tab 2
            case_part = res.split("###SPLIT###")[1] if "###SPLIT###" in res else ""
            lines = [l.replace("CASE:", "").strip() for l in case_part.split("\n") if "CASE:" in l and "|" in l]
            rows = []
            for i, l in enumerate(lines):
                p = l.split("|")
                if len(p) >= 2:
                    rows.append({
                        "ID": f"TC-{i+1}", "Scenario": p[0].strip(), "Expected": p[1].strip(), "Status": "Pending", 
                        "Severity": p[2].strip() if len(p)>2 else "Major", "Priority": p[3].strip() if len(p)>3 else "P1"
                    })
            st.session_state.current_df = ensure_standard_columns(pd.DataFrame(rows))
            st.rerun()

    if st.session_state.audit_report:
        # THE CLEAN DISPLAY FIX
        # Only show content before the split
        report_view = st.session_state.audit_report.split("###SPLIT###")[0].strip()
        # Regex to kill that specific header and any trailing asterisks
        report_view = re.split(r'(\*\*5\.|5\.)', report_view, flags=re.IGNORECASE)[0].strip()
        report_view = re.sub(r'[\s\*_#\-]*$', '', report_view)
        
        st.markdown(report_view)

# --- TAB 2: EXECUTION ---
with tab2:
    # Restored full interactivity
    st.session_state.current_df = st.data_editor(st.session_state.current_df, use_container_width=True, hide_index=True)

# --- TAB 3: BUG CENTER ---
with tab3:
    # Restored bug visibility
    fails = st.session_state.current_df[st.session_state.current_df["Status"] == "Fail"]
    if not fails.empty:
        for _, bug in fails.iterrows():
            with st.expander(f"🐞 Bug: {bug['ID']} - {bug['Scenario']}"):
                st.write(f"**Expected:** {bug['Expected']}")
                st.write(f"**Status:** {bug['Status']} | **Priority:** {bug['Priority']}")
    else:
        st.info("No active bugs.")