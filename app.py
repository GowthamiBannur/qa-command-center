import streamlit as st
import pandas as pd
from openai import OpenAI
import json
import os
import re
import urllib.parse

# 1. Page Config
st.set_page_config(page_title="Principal AI QA Hub", layout="wide", page_icon="🛡️")

# 2. AI Setup
try:
    client = OpenAI(base_url="https://api.groq.com/openai/v1", api_key=st.secrets["GROQ_API_KEY"])
except Exception:
    st.error("API Key missing! Add GROQ_API_KEY to your Streamlit Secrets.")

# 3. Data Persistence & Cleanup
DB_FILE = "qa_database.json"
DEFAULT_COLS = ["ID", "Scenario", "Expected", "Status", "Severity", "Priority", "Evidence_Link", "Assigned_To", "Module"]

def clean_text(text):
    """Removes ** and __ artifacts from AI text"""
    return re.sub(r'\*\*|__', '', str(text)).strip()

def load_data():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r") as f: return json.load(f)
        except: return {}
    return {}

def save_data(data):
    serializable = {}
    for p_id, p_val in data.items():
        serializable[p_id] = {
            "requirement": p_val.get("requirement", ""),
            "risk_summary": p_val.get("risk_summary", ""),
            "tracker_dict": p_val["tracker_df"].to_dict('records') if isinstance(p_val.get("tracker_df"), pd.DataFrame) else []
        }
    with open(DB_FILE, "w") as f: json.dump(serializable, f)

# Initialize Session State & Ensure Columns Exist
if 'project_db' not in st.session_state:
    loaded = load_data()
    st.session_state.project_db = {}
    if not loaded: 
        st.session_state.project_db["Project_ABC"] = {"requirement": "", "risk_summary": "", "tracker_df": pd.DataFrame(columns=DEFAULT_COLS)}
    else:
        for p_id, p_val in loaded.items():
            df = pd.DataFrame(p_val.get("tracker_dict", []))
            for col in DEFAULT_COLS:
                if col not in df.columns: df[col] = ""
            st.session_state.project_db[p_id] = {"requirement": p_val.get("requirement", ""), "risk_summary": p_val.get("risk_summary", ""), "tracker_df": df}

# 4. Sidebar
with st.sidebar:
    st.title("🛡️ QA Hub Manager")
    existing_list = list(st.session_state.project_db.keys())
    active_id = st.selectbox("Active Project:", options=existing_list)
    
    st.markdown("---")
    st.subheader("✉️ Notification Settings")
    manager_cc = st.text_input("CC Manager Email:", placeholder="manager@company.com", key="mgr_cc_sidebar")
    
    if st.button("💾 Save All Progress"):
        save_data(st.session_state.project_db)
        st.success("Changes Saved Successfully!")

current_data = st.session_state.project_db[active_id]

# 5. UI Tabs
tab1, tab2, tab3 = st.tabs(["🏗️ PRD & Risk Analysis", "✅ Execution Log", "🐞 Bug Center"])

# --- TAB 1: PRD & RISK ---
with tab1:
    col1, col2 = st.columns([1, 1.2])
    with col1:
        st.subheader("📋 Requirements Document")
        user_req = st.text_area("Paste PRD here:", value=current_data.get("requirement", ""), height=400)
        current_data["requirement"] = user_req
        
        if st.button("🚀 Audit PRD & Map Risk"):
            with st.spinner("Analyzing Risks & Scenarios..."):
                prompt = f"Analyze PRD: {user_req}. 1. Generate 15+ cases: 'CASE: [Scenario] | [Expected] | [Severity] | [Priority]'. 2. Provide a 'RISK_REPORT' section."
                res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role": "user", "content": prompt}]).choices[0].message.content
                
                if "RISK_REPORT" in res:
                    parts = res.split("RISK_REPORT")
                    current_data["risk_summary"] = parts[1].strip()
                
                lines = [l.replace("CASE:", "").strip() for l in res.split("\n") if "CASE:" in l]
                rows = []
                for i, l in enumerate(lines):
                    p = l.split("|")
                    rows.append({
                        "ID": f"TC-{i+1}", "Scenario": clean_text(p[0]), "Expected": clean_text(p[1]),
                        "Status": "Pending", "Severity": clean_text(p[2]), "Priority": clean_text(p[3]), 
                        "Evidence_Link": "", "Assigned_To": "dev@example.com", "Module": ""
                    })
                current_data["tracker_df"] = pd.DataFrame(rows)
                st.rerun()

    with col2:
        if current_data.get("risk_summary"):
            st.subheader("🔥 AI Risk & Mitigation")
            st.info(current_data["risk_summary"])
            st.divider()
        
        st.subheader("🔍 Test Suite View")
        if not current_data["tracker_df"].empty:
            st.dataframe(current_data["tracker_df"][["ID", "Scenario", "Severity", "Priority"]], use_container_width=True, hide_index=True)

# --- TAB 2: EXECUTION LOG ---
with tab2:
    st.subheader(f"Execution Log: {active_id}")
    if not current_data["tracker_df"].empty:
        edited_df = st.data_editor(current_data["tracker_df"], column_config={
                "Status": st.column_config.SelectboxColumn("Status", options=["Pending", "Pass", "Fail"]),
                "Assigned_To": st.column_config.TextColumn("Dev Email"),
                "Evidence_Link": st.column_config.LinkColumn("Evidence Link")
            }, use_container_width=True, key=f"edit_{active_id}")
        current_data["tracker_df"] = edited_df

# --- TAB 3: BUG CENTER ---
with tab3:
    st.subheader("🐞 Bug Reporter")
    # CRASH GUARD: Ensure df is valid before filtering
    df_for_bugs = current_data["tracker_df"]
    if not df_for_bugs.empty and "Status" in df_for_bugs.columns:
        fails = df_for_bugs[df_for_bugs["Status"] == "Fail"].copy()
        
        if fails.empty:
            st.info("No failures logged.")
        else:
            for idx, bug in fails.iterrows():
                with st.expander(f"REPORT: {bug['ID']} - {bug['Scenario']}"):
                    # ROW 1: Module & Severity
                    c1, c2 = st.columns(2)
                    mod_val = c1.text_input("Module:", value=bug.get("Module", ""), key=f"m_{bug['ID']}")
                    current_data["tracker_df"].at[idx, "Module"] = mod_val
                    sev = c2.selectbox("Severity:", ["Blocker", "Critical", "Major", "Minor"], index=2, key=f"s_{bug['ID']}")
                    
                    # ROW 2: Priority & Assigned To
                    c3, c4 = st.columns(2)
                    pri = c3.selectbox("Priority:", ["P0", "P1", "P2", "P3"], index=1, key=f"p_{bug['ID']}")
                    dev_email = c4.text_input("Assigned To:", value=bug['Assigned_To'], key=f"e_{bug['ID']}")
                    current_data["tracker_df"].at[idx, "Assigned_To"] = dev_email

                    # DESCRIPTION BOX
                    desc = st.text_area("Bug Description / Steps:", value=f"1. Navigate to {mod_val}\n2. Perform: {bug['Scenario']}\n3. Observe Failure.", key=f"d_{bug['ID']}")
                    
                    # EVIDENCE LINK (BELOW DESCRIPTION)
                    st.markdown(f"**🔗 Evidence:** [{bug['Evidence_Link']}]({bug['Evidence_Link']})" if bug['Evidence_Link'] else "**🔗 Evidence:** None.")

                    # ROW 3: Expected & Actual
                    c5, c6 = st.columns(2)
                    exp = c5.text_input("Expected:", value=bug['Expected'], key=f"exp_{bug['ID']}")
                    act = c6.text_input("Actual:", value="Does not match PRD criteria.", key=f"act_{bug['ID']}")

                    # EMAIL INTEGRATION
                    subject = f"[{sev}] BUG: {bug['ID']} - {active_id}"
                    body = f"Bug details assigned to you:\n\nScenario: {bug['Scenario']}\nSteps: {desc}\nExpected: {exp}\nEvidence: {bug['Evidence_Link']}"
                    params = {"subject": subject, "body": body, "cc": manager_cc if manager_cc else ""}
                    mailto_link = f"mailto:{dev_email}?" + urllib.parse.urlencode(params).replace('+', '%20')
                    
                    st.markdown(f'<a href="{mailto_link}" style="padding: 10px; background-color: #ff4b4b; color: white; border-radius: 5px; text-decoration: none;">📧 Email Bug (CC Manager)</a>', unsafe_allow_html=True)
    else:
        st.warning("Audit PRD in Tab 1 to begin.")