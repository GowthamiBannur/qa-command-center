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

# 3. Data Persistence
DB_FILE = "qa_database.json"
DEFAULT_COLS = ["ID", "Scenario", "Expected", "Status", "Severity", "Priority", "Evidence_Link", "Assigned_To", "Module"]

def clean_text(text):
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

# Initialize Session State
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
    active_id = st.selectbox("Active Project:", options=list(st.session_state.project_db.keys()))
    
    st.markdown("---")
    st.subheader("✉️ Notification Settings")
    manager_cc = st.text_input("CC Manager Email:", placeholder="manager@company.com", key="mgr_cc")
    
    if st.button("💾 Save All Progress"):
        save_data(st.session_state.project_db)
        st.success("Changes Saved!")

current_data = st.session_state.project_db[active_id]

# 5. UI Tabs
tab1, tab2, tab3 = st.tabs(["🏗️ PRD & Risk Analysis", "✅ Execution Log", "🐞 Bug Center"])

# --- TAB 1: PRD & RISK (RESTORED) ---
with tab1:
    col1, col2 = st.columns([1, 1.2])
    with col1:
        st.subheader("📋 Requirements Document")
        user_req = st.text_area("Paste PRD here:", value=current_data.get("requirement", ""), height=400)
        current_data["requirement"] = user_req
        if st.button("🚀 Audit PRD & Map Risk"):
            with st.spinner("Generating 15+ Cases & Risk Report..."):
                prompt = f"Analyze PRD: {user_req}. 1. Cases: 'CASE: [Scenario] | [Expected] | [Severity] | [Priority]'. 2. 'RISK_REPORT' section."
                res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role": "user", "content": prompt}]).choices[0].message.content
                if "RISK_REPORT" in res:
                    parts = res.split("RISK_REPORT")
                    current_data["risk_summary"] = parts[1].strip()
                lines = [l.replace("CASE:", "").strip() for l in res.split("\n") if "CASE:" in l]
                rows = []
                for i, l in enumerate(lines):
                    p = l.split("|")
                    rows.append({"ID": f"TC-{i+1}", "Scenario": clean_text(p[0]), "Expected": clean_text(p[1]), "Status": "Pending", "Severity": clean_text(p[2]), "Priority": clean_text(p[3]), "Evidence_Link": "", "Assigned_To": "dev@company.com", "Module": ""})
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

# --- TAB 2: EXECUTION LOG (RESTORED EVIDENCE ATTACH FIELD) ---
with tab2:
    st.subheader(f"Execution Log: {active_id}")
    if not current_data["tracker_df"].empty:
        edited_df = st.data_editor(current_data["tracker_df"], column_config={
                "Status": st.column_config.SelectboxColumn("Status", options=["Pending", "Pass", "Fail"]),
                "Assigned_To": st.column_config.TextColumn("Dev Email"),
                "Evidence_Link": st.column_config.LinkColumn("Evidence Link")
            }, use_container_width=True, key=f"edit_log_{active_id}")
        current_data["tracker_df"] = edited_df
        
        # --- FEATURE RESTORED: ATTACH EVIDENCE FIELD ---
        st.markdown("---")
        st.subheader("🎥 Attach Evidence Link")
        ec1, ec2 = st.columns([1, 2])
        target_tc = ec1.selectbox("Select TC ID:", options=edited_df["ID"])
        link_val = ec2.text_input("Paste Evidence URL (Loom/Drive/S3):", key="ev_input")
        if st.button("🔗 Save Link to Case"):
            idx = current_data["tracker_df"].index[current_data["tracker_df"]["ID"] == target_tc][0]
            current_data["tracker_df"].at[idx, "Evidence_Link"] = link_val
            st.success(f"Link added to {target_tc}!")
            st.rerun()

# --- TAB 3: BUG CENTER (UNCHANGED) ---
with tab3:
    st.subheader("🐞 Bug Reporter")
    df_bugs = current_data["tracker_df"]
    if not df_bugs.empty and "Status" in df_bugs.columns:
        fails = df_bugs[df_bugs["Status"] == "Fail"].copy()
        if fails.empty:
            st.info("No failures logged.")
        else:
            for idx, bug in fails.iterrows():
                with st.expander(f"REPORT: {bug['ID']} - {bug['Scenario']}"):
                    c1, c2 = st.columns(2)
                    mod_val = c1.text_input("Module:", value=bug.get("Module", ""), key=f"mod_{bug['ID']}")
                    current_data["tracker_df"].at[idx, "Module"] = mod_val
                    sev = c2.selectbox("Severity:", ["Blocker", "Critical", "Major", "Minor"], index=2, key=f"sev_{bug['ID']}")
                    
                    c3, c4 = st.columns(2)
                    pri = c3.selectbox("Priority:", ["P0", "P1", "P2", "P3"], index=1, key=f"pri_{bug['ID']}")
                    dev_email = c4.text_input("Assigned To:", value=bug['Assigned_To'], key=f"email_{bug['ID']}")
                    current_data["tracker_df"].at[idx, "Assigned_To"] = dev_email

                    desc = st.text_area("Bug Description / Steps:", value=f"1. Navigate to {mod_val}\n2. Perform: {bug['Scenario']}\n3. Observe Failure.", key=f"desc_{bug['ID']}")
                    st.markdown(f"**🔗 Evidence:** [{bug['Evidence_Link']}]({bug['Evidence_Link']})" if bug['Evidence_Link'] else "**🔗 Evidence:** None.")

                    c5, c6 = st.columns(2)
                    exp = c5.text_input("Expected:", value=bug['Expected'], key=f"exp_{bug['ID']}")
                    act = c6.text_input("Actual:", value="Does not match PRD criteria.", key=f"act_{bug['ID']}")

                    subject = f"[{sev}] BUG: {bug['ID']} - {active_id}"
                    body = f"Bug details assigned to you:\n\nScenario: {bug['Scenario']}\nSteps: {desc}\nExpected: {exp}\nEvidence: {bug['Evidence_Link']}"
                    params = {"subject": subject, "body": body, "cc": manager_cc if manager_cc else ""}
                    mailto_link = f"mailto:{dev_email}?" + urllib.parse.urlencode(params).replace('+', '%20')
                    st.markdown(f'<a href="{mailto_link}" style="padding: 10px; background-color: #ff4b4b; color: white; border-radius: 5px; text-decoration: none;">📧 Email Bug (CC Manager)</a>', unsafe_allow_html=True)