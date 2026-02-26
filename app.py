import streamlit as st
import pandas as pd
from openai import OpenAI
import re
from supabase import create_client, Client

# 1. Page Config
st.set_page_config(page_title="Principal QA Hub", layout="wide")

# 2. Connections
@st.cache_resource
def init_connection():
    try: return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    except: return None

supabase = init_connection()
client = OpenAI(base_url="https://api.groq.com/openai/v1", api_key=st.secrets["GROQ_API_KEY"])

# 3. State Setup
if 'current_df' not in st.session_state: st.session_state.current_df = pd.DataFrame()
if 'audit_report' not in st.session_state: st.session_state.audit_report = ""

# 4. Tabs
tab1, tab2, tab3 = st.tabs(["🏗️ Senior Audit & Doubts", "✅ Execution Log", "🐞 Bug Center"])

with tab1:
    user_req = st.text_area("Paste PRD Document:", height=150)
    if st.button("🚀 Generate Full Audit"):
        with st.spinner("Processing..."):
            prompt = f"""Analyze PRD: {user_req}
            Provide these exact sections:
            1. Summary
            2. Feature Table
            3. Strategy
            4. Doubts for PM
            [END_AUDIT]
            5. Test Cases (35+). Format: 'CASE: Scenario | Expected | Severity | Priority'"""
            
            full_res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role": "user", "content": prompt}]).choices[0].message.content
            st.session_state.audit_report = full_res
            
            # --- PARSING TEST CASES (For Tab 2) ---
            case_part = full_res.split("[END_AUDIT]")[1] if "[END_AUDIT]" in full_res else full_res
            lines = [l.replace("CASE:", "").strip() for l in case_part.split("\n") if "CASE:" in l and "|" in l]
            rows = []
            for i, l in enumerate(lines):
                p = l.split("|")
                if len(p) >= 2:
                    rows.append({
                        "ID": f"TC-{i+1}", "Scenario": p[0].strip(), "Expected": p[1].strip(), "Status": "Pending", 
                        "Severity": p[2].strip() if len(p)>2 else "Major", "Priority": p[3].strip() if len(p)>3 else "P1"
                    })
            st.session_state.current_df = pd.DataFrame(rows)
            st.rerun()

    if st.session_state.audit_report:
        # --- DISPLAY LOGIC: PROTECTING DOUBTS & STRATEGY ---
        # 1. Extract only the portion before the marker
        display_output = st.session_state.audit_report.split("[END_AUDIT]")[0].strip()
        
        # 2. Remove the specific leaked header shown in your screenshot
        display_output = re.sub(r'(\*\*5\. Test Cases|\*\*5\. TEST_CASES|5\. Test Cases).*$', '', display_output, flags=re.IGNORECASE | re.MULTILINE)
        
        # 3. Final scrub for trailing bold markers
        display_output = display_output.rstrip(" \n\t*#_")
        
        st.markdown(display_output)

with tab2:
    if not st.session_state.current_df.empty:
        st.session_state.current_df = st.data_editor(st.session_state.current_df, use_container_width=True, hide_index=True)

with tab3:
    if not st.session_state.current_df.empty and "Status" in st.session_state.current_df.columns:
        fails = st.session_state.current_df[st.session_state.current_df["Status"] == "Fail"]
        for _, bug in fails.iterrows():
            with st.expander(f"🐞 Bug: {bug['Scenario']}"):
                st.write(f"**Expected:** {bug['Expected']}")
    else:
        st.info("No bugs logged.")