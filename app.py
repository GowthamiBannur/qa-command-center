import streamlit as st
import pandas as pd
from openai import OpenAI
import re
from supabase import create_client, Client

# 1. Page Config
st.set_page_config(page_title="Principal QA Hub", layout="wide", page_icon="🛡️")

# 2. Schema Logic
def ensure_standard_columns(df):
    required = ["ID", "Scenario", "Expected", "Status", "Severity", "Priority", "Evidence_Link", "Assigned_To", "Module", "Actual_Result"]
    for col in required:
        if col not in df.columns:
            if col == "Status": df[col] = "Pending"
            elif col == "Assigned_To": df[col] = "dev@team.com"
            elif col in ["Severity", "Priority"]: df[col] = "Major" if col == "Severity" else "P1"
            else: df[col] = ""
    return df

# 3. Connections
@st.cache_resource
def init_connection():
    try: return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    except: return None

supabase = init_connection()
client = OpenAI(base_url="https://api.groq.com/openai/v1", api_key=st.secrets["GROQ_API_KEY"])

# 4. State Management
if 'current_df' not in st.session_state: st.session_state.current_df = ensure_standard_columns(pd.DataFrame())
if 'audit_report' not in st.session_state: st.session_state.audit_report = ""

# 5. Sidebar
with st.sidebar:
    st.title("👥 Team QA Hub")
    st.session_state.active_id = st.text_input("Project Name:", value="Project_Alpha")
    if st.button("🌊 Save Everything"):
        supabase.table("qa_tracker").delete().eq("project_name", st.session_state.active_id).execute()
        data = st.session_state.current_df.to_dict(orient='records')
        for row in data: 
            row['project_name'] = st.session_state.active_id
            row['strategy_text'] = st.session_state.audit_report
        supabase.table("qa_tracker").insert(data).execute()
        st.success("Project Synced to Database")

# 6. Tabs
tab1, tab2, tab3 = st.tabs(["🏗️ Senior Audit & Doubts", "✅ Execution Log", "🐞 Bug Center"])

# --- TAB 1: SENIOR AUDIT ---
with tab1:
    user_req = st.text_area("Paste PRD Document:", height=150)
    if st.button("🚀 Generate Audit"):
        with st.spinner("Analyzing..."):
            prompt = f"PRD: {user_req}\nReturn exactly:\n1. Summary\n2. Feature Table\n3. Strategy\n4. Doubts for PM\n[SPLIT]\n5. 35+ Test Cases. Format: 'CASE: Scenario | Expected | Severity | Priority'"
            res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role": "user", "content": prompt}]).choices[0].message.content
            st.session_state.audit_report = res
            
            # Parsing Test Cases for Tab 2
            case_part = res.split("[SPLIT]")[1] if "[SPLIT]" in res else ""
            lines = [l.replace("CASE:", "").strip() for l in case_part.split("\n") if "CASE:" in l and "|" in l]
            rows = []
            for i, l in enumerate(lines):
                p = l.split("|")
                if len(p) >= 2:
                    rows.append({
                        "ID": f"TC-{i+1}", "Scenario": p[0].strip(), "Expected": p[1].strip(), "Status": "Pending", 
                        "Severity": p[2].strip() if len(p)>2 else "Major", 
                        "Priority": p[3].strip() if len(p)>3 else "P1"
                    })
            st.session_state.current_df = ensure_standard_columns(pd.DataFrame(rows))
            st.rerun()

    if st.session_state.audit_report:
        # Show ONLY what is before [SPLIT] - includes Summary, Table, Strategy, and DOUBTS
        display_text = st.session_state.audit_report.split("[SPLIT]")[0].strip()
        # Remove any lingering asterisks or partial headers at the very end
        display_text = re.sub(r'(\n.*5\..*|\n.*Test Cases.*|\s*\**)$', '', display_text, flags=re.IGNORECASE | re.DOTALL)
        st.markdown(display_text)

# --- TAB 2: EXECUTION ---
with tab2:
    st.session_state.current_df = st.data_editor(st.session_state.current_df, use_container_width=True, hide_index=True)

# --- TAB 3: BUG CENTER ---
with tab3:
    fails = st.session_state.current_df[st.session_state.current_df["Status"] == "Fail"]
    if not fails.empty:
        for _, bug in fails.iterrows():
            with st.expander(f"🐞 BUG: {bug['ID']} - {bug['Scenario']}"):
                st.write(f"**Expected:** {bug['Expected']}")
                st.write(f"**Priority:** {bug['Priority']} | **Severity:** {bug['Severity']}")
    else:
        st.info("No active bugs.")