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

# 3. Schema Management
DB_FILE = "qa_database.json"
DEFAULT_COLS = ["ID", "Scenario", "Expected", "Status", "Severity", "Priority", "Evidence_Link", "Assigned_To", "Module"]

def clean_text(text):
    return re.sub(r'\*\*|__', '', str(text)).strip()

def enforce_schema(df):
    """Ensures all required columns exist in the dataframe to prevent KeyErrors."""
    for col in DEFAULT_COLS:
        if col not in df.columns:
            df[col] = "" if col != "Status" else "Pending"
    return df

def get_session_as_json():
    serializable = {}
    for p_id, p_val in st.session_state.project_db.items():
        serializable[p_id] = {
            "requirement": p_val.get("requirement", ""),
            "risk_summary": p_val.get("risk_summary", ""),
            "tracker_dict": p_val["tracker_df"].to_dict('records') if isinstance(p_val.get("tracker_df"), pd.DataFrame) else []
        }
    return json.dumps(serializable, indent=4)

# 4. Sidebar: Project Management
with st.sidebar:
    st.title("🛡️ QA Hub Manager")
    
    st.subheader("💾 Data Protection")
    uploaded_file = st.file_uploader("Restore from Backup (.json)", type="json")
    if uploaded_file:
        try:
            raw = json.load(uploaded_file)
            restored_db = {}
            for p_id, p_val in raw.items():
                df = pd.DataFrame(p_val.get("tracker_dict", []))
                df = enforce_schema(df) # Schema fix on upload
                restored_db[p_id] = {"requirement": p_val.get("requirement", ""), "risk_summary": p_val.get("risk_summary", ""), "tracker_df": df}
            st.session_state.project_db = restored_db
            st.success("Data Restored!")
        except:
            st.error("Invalid Backup File")

    if 'project_db' not in st.session_state:
        st.session_state.project_db = {"Project_ABC": {"requirement": "", "risk_summary": "", "tracker_df": pd.DataFrame(columns=DEFAULT_COLS)}}

    active_id = st.selectbox("Active Project:", options=list(st.session_state.project_db.keys()))
    
    backup_data = get_session_as_json()
    st.download_button(label="📥 Download My Data", data=backup_data, file_name=f"qa_backup.json", mime="application/json")

    st.markdown("---")
    st.subheader("✉️ Notification Settings")
    manager_cc = st.text_input("CC Manager Email:", placeholder="manager@company.com", key="mgr_cc")

current_data = st.session_state.project_db[active_id]
# Emergency schema check before UI renders
current_data["tracker_df"] = enforce_schema(current_data["tracker_df"])

# 5. UI Tabs
tab1, tab2, tab3 = st.tabs(["🏗️ Senior QA Audit", "✅ Execution Log", "🐞 Bug Center"])

# --- TAB 1: SENIOR QA AUDIT ---
with tab1:
    col1, col2 = st.columns([1, 1.2])
    with col1:
        st.subheader("📋 Requirements Document")
        user_req = st.text_area("Paste PRD here:", value=current_data.get("requirement", ""), height=400)
        current_data["requirement"] = user_req
        
        if st.button("🚀 Run Deep Stress Audit"):
            with st.spinner("Generating 30+ Senior Scenarios..."):
                prompt = f"Senior QA Lead: Analyze {user_req}. 1. Generate 30+ cases 'CASE: [Scenario] | [Expected] | [Severity] | [Priority]'. 2. 'RISK_REPORT'."
                res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role": "user", "content": prompt}]).choices[0].message.content
                if "RISK_REPORT" in res:
                    parts = res.split("RISK_REPORT")
                    current_data["risk_summary"] = parts[1].strip()
                lines = [l.replace("CASE:", "").strip() for l in res.split("\n") if "CASE:" in l]
                rows = []
                for i, l in enumerate(lines):
                    p = l.split("|")
                    if len(p) >= 2:
                        rows.append({"ID": f"TC-{i+1}", "Scenario": clean_text(p[0]), "Expected": clean_text(p[1]), "Status": "Pending", "Severity": clean_text(p[2]) if len(p)>2 else "Major", "Priority": clean_text(p[3]) if len(p)>3 else "P1", "Evidence_Link": "", "Assigned_To": "dev@company.com", "Module": ""})
                current_data["tracker_df"] = pd.DataFrame(rows)
                st.rerun()

    with col2:
        if current_data.get("risk_summary"):
            st.subheader("🔥 Strategic Risk Assessment")
            st.info(current_data["risk_summary"])
        st.subheader("🔍 Master Test Suite")
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
            }, use_container_width=True, key=f"edit_log_{active_id}")
        current_data["tracker_df"] = edited_df
        
        st.markdown("---")
        st.subheader("🎥 Attach Evidence Link")
        ec1, ec2 = st.columns([1, 2])
        target_tc = ec1.selectbox("Select TC ID:", options=edited_df["ID"])
        link_val = ec2.text_input("Paste URL:", key="ev_input")
        if st.button("🔗 Save Link to Case"):
            idx = current_data["tracker_df"].index[current_data["tracker_df"]["ID"] == target_tc][0]
            current_data["tracker_df"].at[idx, "Evidence_Link"] = link_val
            st.success("Linked!")
            st.rerun()

# --- TAB 3: BUG CENTER ---
with tab3:
    st.subheader("🐞 Bug Reporter")
    df_bugs = current_data["tracker_df"]
    if not df_bugs.empty:
        fails = df_bugs[df_bugs["Status"] == "Fail"].copy()
        if fails.empty:
            st.info("No failures logged.")
        else:
            for idx, bug in fails.iterrows():
                with st.expander(f"REPORT: {bug['ID']} - {bug['Scenario']}"):
                    c1, c2 = st.columns(2)
                    mod_val = c1.text_input("Module:", value=bug.get("Module", ""), key=f"mod_{bug['ID']}")
                    current_data["tracker_df"].at[idx, "Module"] = mod_val
                    # SCHEMA FIX: Using .get() or ensuring column exists prevents crash
                    dev_email = c2.text_input("Assigned To:", value=bug.get('Assigned_To', 'dev@company.com'), key=f"email_{bug['ID']}")
                    current_data["tracker_df"].at[idx, "Assigned_To"] = dev_email

                    desc = st.text_area("Steps:", value=f"Observe failure in {bug['Scenario']}", key=f"desc_{bug['ID']}")
                    st.markdown(f"**🔗 Evidence:** [{bug['Evidence_Link']}]({bug['Evidence_Link']})" if bug['Evidence_Link'] else "**🔗 Evidence: None**")

                    subject = f"[{bug.get('Severity', 'Major')}] BUG: {bug['ID']}"
                    body = f"Scenario: {bug['Scenario']}\nSteps: {desc}\nEvidence: {bug['Evidence_Link']}"
                    params = {"subject": subject, "body": body, "cc": manager_cc if manager_cc else ""}
                    mailto_link = f"mailto:{dev_email}?" + urllib.parse.urlencode(params).replace('+', '%20')
                    st.markdown(f'<a href="{mailto_link}" style="padding: 10px; background-color: #ff4b4b; color: white; border-radius: 5px; text-decoration: none;">📧 Email Bug (CC Manager)</a>', unsafe_allow_html=True)