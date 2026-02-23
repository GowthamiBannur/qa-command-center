import streamlit as st
import pandas as pd
from openai import OpenAI
import json
import os
import io
import re
import urllib.parse

# 1. Page Config
st.set_page_config(page_title="Principal AI QA Hub", layout="wide", page_icon="🛡️")

# 2. Setup AI Client
try:
    client = OpenAI(base_url="https://api.groq.com/openai/v1", api_key=st.secrets["GROQ_API_KEY"])
except Exception:
    st.error("API Key missing! Add GROQ_API_KEY to your Streamlit Secrets.")

# 3. Persistent Storage
DB_FILE = "qa_database.json"

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

def clean_text(text):
    return re.sub(r'\*\*|__', '', str(text)).strip()

# Initialize Session State
DEFAULT_COLS = ["ID", "Scenario", "Expected", "Status", "Severity", "Priority", "Evidence_Link", "Assigned_To", "Module"]

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
            st.session_state.project_db[p_id] = {
                "requirement": p_val.get("requirement", ""),
                "risk_summary": p_val.get("risk_summary", ""),
                "tracker_df": df
            }

# 4. Sidebar
with st.sidebar:
    st.title("🛡️ QA Hub Manager")
    existing_list = list(st.session_state.project_db.keys())
    selected_project = st.selectbox("Active Project:", options=existing_list + ["+ New Project"])
    
    if selected_project == "+ New Project":
        new_name = st.text_input("New Project Name:")
        if st.button("Create"):
            st.session_state.project_db[new_name] = {"requirement": "", "risk_summary": "", "tracker_df": pd.DataFrame(columns=DEFAULT_COLS)}
            st.rerun()
        active_id = existing_list[0]
    else:
        active_id = selected_project

    st.markdown("---")
    if st.button("💾 Save All Changes"):
        save_data(st.session_state.project_db)
        st.success("Changes Saved!")

current_data = st.session_state.project_db[active_id]

# 5. UI Tabs
tab1, tab2, tab3 = st.tabs(["🏗️ PRD & Risk Analysis", "✅ Execution Log", "🐞 Bug Center"])

# --- TAB 1: PRD ANALYSIS ---
with tab1:
    col1, col2 = st.columns([1, 1.2])
    with col1:
        st.subheader("📋 Requirements Document")
        user_req = st.text_area("Paste PRD here:", value=current_data.get("requirement", ""), height=400)
        current_data["requirement"] = user_req
        
        if st.button("🚀 Audit PRD & Map Risk"):
            with st.spinner("Analyzing Risks..."):
                prompt = f"Analyze PRD: {user_req}. 1. Cases: 'CASE: [Scenario] | [Expected] | [Severity] | [Priority]'. 2. 'RISK_REPORT' with mitigation."
                response = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role": "user", "content": prompt}])
                full_res = response.choices[0].message.content
                if "RISK_REPORT" in full_res:
                    parts = full_res.split("RISK_REPORT")
                    current_data["risk_summary"] = parts[1]
                lines = [l.replace("CASE:", "").strip() for l in full_res.split("\n") if "CASE:" in l]
                rows = []
                for i, l in enumerate(lines):
                    p = l.split("|")
                    rows.append({
                        "ID": f"TC-{i+1}", "Scenario": clean_text(p[0]), "Expected": clean_text(p[1]),
                        "Status": "Pending", "Severity": clean_text(p[2]), "Priority": clean_text(p[3]), 
                        "Evidence_Link": "", "Assigned_To": "developer@example.com", "Module": ""
                    })
                current_data["tracker_df"] = pd.DataFrame(rows)
                st.rerun()

    with col2:
        if current_data.get("risk_summary"):
            st.subheader("🔥 Risk & Mitigation")
            st.info(current_data["risk_summary"])
        st.subheader("🔍 Structured Suite")
        if not current_data["tracker_df"].empty:
            st.dataframe(current_data["tracker_df"][["ID", "Scenario", "Severity", "Priority"]], use_container_width=True, hide_index=True)

# --- TAB 2: EXECUTION LOG ---
with tab2:
    st.subheader(f"Execution Log: {active_id}")
    df = current_data.get("tracker_df", pd.DataFrame())
    if not df.empty:
        # Syncing data back to session state via data_editor
        edited_df = st.data_editor(df, column_config={
                "Status": st.column_config.SelectboxColumn("Status", options=["Pending", "Pass", "Fail"]),
                "Assigned_To": st.column_config.TextColumn("Assigned To (Email)"),
                "Evidence_Link": st.column_config.LinkColumn("Evidence Link")
            }, use_container_width=True, key=f"editor_{active_id}")
        current_data["tracker_df"] = edited_df

# --- TAB 3: BUG CENTER (Sync & Notify) ---
with tab3:
    st.subheader("🐞 Bug Center & Notifications")
    df_check = current_data.get("tracker_df", pd.DataFrame())
    fails = df_check[df_check["Status"] == "Fail"].copy()
    
    if fails.empty:
        st.info("No failures logged.")
    else:
        for index, bug in fails.iterrows():
            with st.expander(f"REPORT: {bug['ID']} - {bug['Scenario']}"):
                b1, b2 = st.columns(2)
                # Field Sync: Pulls directly from the dataframe edited in Tab 2
                dev_email = b1.text_input("Assigned To:", value=bug['Assigned_To'], key=f"email_{bug['ID']}")
                current_data["tracker_df"].at[index, "Assigned_To"] = dev_email
                
                mod_val = b2.text_input("Module:", value=bug.get("Module", ""), key=f"mod_{bug['ID']}")
                current_data["tracker_df"].at[index, "Module"] = mod_val
                
                bug_desc = st.text_area("Bug Description / Steps:", value=f"1. Open App\n2. Perform: {bug['Scenario']}\n3. Observed Fail.", key=f"desc_{bug['ID']}")
                st.markdown(f"**🔗 Evidence:** [{bug['Evidence_Link']}]({bug['Evidence_Link']})" if bug['Evidence_Link'] else "**🔗 Evidence:** None.")

                # Email Logic
                subject = f"BUG REPORT: {bug['ID']} - {active_id}"
                body = f"Hi,\n\nA bug has been assigned to you.\n\nScenario: {bug['Scenario']}\nExpected: {bug['Expected']}\nDescription: {bug_desc}\nEvidence: {bug['Evidence_Link']}\n\nPlease review."
                mailto_link = f"mailto:{dev_email}?subject={urllib.parse.quote(subject)}&body={urllib.parse.quote(body)}"
                
                st.markdown(f'<a href="{mailto_link}" style="padding: 10px; background-color: #ff4b4b; color: white; border-radius: 5px; text-decoration: none;">📧 Send Bug to Developer</a>', unsafe_allow_content_allowed=True)

                if st.button(f"Generate AI Jira Draft for {bug['ID']}", key=f"btn_{bug['ID']}"):
                    prompt = f"Ticket for: {bug['Scenario']}\nAssigned: {dev_email}\nDetails: {bug_desc}"
                    res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role": "user", "content": prompt}])
                    st.code(res.choices[0].message.content)