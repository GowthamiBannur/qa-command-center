import streamlit as st
import pandas as pd
from openai import OpenAI
import json
import os
import io

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

# Initialize Session State with default columns to prevent KeyErrors
DEFAULT_COLS = ["ID", "Scenario", "Expected", "Status", "Severity", "Priority", "Evidence_Link", "Assigned_To", "Module"]

if 'project_db' not in st.session_state:
    loaded = load_data()
    st.session_state.project_db = {}
    if not loaded: 
        st.session_state.project_db["Project_ABC"] = {"requirement": "", "risk_summary": "", "tracker_df": pd.DataFrame(columns=DEFAULT_COLS)}
    else:
        for p_id, p_val in loaded.items():
            df = pd.DataFrame(p_val.get("tracker_dict", []))
            # Ensure all columns exist even in loaded data
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
        
        if st.button("🚀 Audit PRD"):
            with st.spinner("Processing..."):
                prompt = f"Analyze PRD: {user_req}. Generate 15+ test cases in format: 'CASE: [Scenario] | [Expected] | [Severity] | [Priority]'."
                response = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role": "user", "content": prompt}])
                full_res = response.choices[0].message.content
                lines = [l.replace("CASE:", "").strip() for l in full_res.split("\n") if "CASE:" in l]
                rows = []
                for i, l in enumerate(lines):
                    p = l.split("|")
                    rows.append({
                        "ID": f"TC-{i+1}", "Scenario": p[0].strip() if len(p)>0 else "N/A",
                        "Expected": p[1].strip() if len(p)>1 else "Pass",
                        "Status": "Pending", "Severity": p[2].strip() if len(p)>2 else "Major",
                        "Priority": p[3].strip() if len(p)>3 else "P1", 
                        "Evidence_Link": "", "Assigned_To": "Developer", "Module": ""
                    })
                current_data["tracker_df"] = pd.DataFrame(rows)
                st.rerun()

    with col2:
        st.subheader("🔥 Structured Strategy")
        if not current_data["tracker_df"].empty:
            st.dataframe(current_data["tracker_df"][["ID", "Scenario", "Severity", "Priority"]], use_container_width=True, hide_index=True)

# --- TAB 2: EXECUTION LOG ---
with tab2:
    st.subheader(f"Execution Log: {active_id}")
    df = current_data.get("tracker_df", pd.DataFrame())
    
    # SAFETY CHECK: Ensure Status column exists before editing
    if not df.empty and "Status" in df.columns:
        edited_df = st.data_editor(df, column_config={
                "Status": st.column_config.SelectboxColumn("Status", options=["Pending", "Pass", "Fail"]),
                "Evidence_Link": st.column_config.LinkColumn("Evidence Link")
            }, use_container_width=True, key=f"editor_{active_id}")
        current_data["tracker_df"] = edited_df
        
        st.markdown("---")
        st.subheader("🎥 Attach Evidence Link")
        ec1, ec2 = st.columns([1, 2])
        target_tc = ec1.selectbox("Select TC:", options=edited_df["ID"])
        link_val = ec2.text_input("Paste URL (Loom/Drive):")
        if st.button("🔗 Save Link"):
            idx = current_data["tracker_df"].index[current_data["tracker_df"]["ID"] == target_tc][0]
            current_data["tracker_df"].at[idx, "Evidence_Link"] = link_val
            st.success("Link Saved!")
    else:
        st.warning("Please go to Tab 1 and click 'Audit PRD' to initialize the project.")

# --- TAB 3: BUG CENTER ---
with tab3:
    st.subheader("🐞 Bug Center")
    df_check = current_data.get("tracker_df", pd.DataFrame())
    
    # SAFETY CHECK: Ensure column exists before filtering
    if not df_check.empty and "Status" in df_check.columns:
        fails = df_check[df_check["Status"] == "Fail"].copy()
        
        if fails.empty:
            st.info("No failures logged. Mark a test as 'Fail' in Tab 2 to report a bug.")
        else:
            for index, bug in fails.iterrows():
                prd_text = current_data.get("requirement", "").upper()
                found_mod = ""
                for m in ["PDP", "PLP", "CHECKOUT", "HOME", "CART"]:
                    if m in prd_text and m in bug['Scenario'].upper():
                        found_mod = m.title()
                        break

                with st.expander(f"REPORT: {bug['ID']} - {bug['Scenario']}"):
                    b_col1, b_col2 = st.columns(2)
                    with b_col1:
                        mod_val = st.text_input("Module:", value=found_mod if found_mod else bug.get("Module", ""), key=f"mod_{bug['ID']}", placeholder="Identify Module")
                        current_data["tracker_df"].at[index, "Module"] = mod_val
                    with b_col2:
                        final_pri = st.selectbox("Priority:", options=["P0", "P1", "P2", "P3"], index=["P0", "P1", "P2", "P3"].index(bug['Priority']) if bug['Priority'] in ["P0", "P1", "P2", "P3"] else 1, key=f"pri_{bug['ID']}")

                    s_col1, s_col2 = st.columns(2)
                    with s_col1:
                        final_sev = st.selectbox("Severity:", options=["Blocker", "Critical", "Major", "Minor"], index=["Blocker", "Critical", "Major", "Minor"].index(bug['Severity']) if bug['Severity'] in ["Blocker", "Critical", "Major", "Minor"] else 2, key=f"sev_{bug['ID']}")
                    with s_col2:
                        final_ass = st.text_input("Assigned To:", value=bug['Assigned_To'], key=f"ass_{bug['ID']}")

                    bug_desc = st.text_area("Bug Description / Steps:", value=f"1. Navigate to {mod_val if mod_val else 'Target Module'}\n2. Scenario: {bug['Scenario']}\n3. Observed Failure.", key=f"desc_{bug['ID']}")
                    
                    st.markdown(f"**🔗 Evidence Link:** [{bug['Evidence_Link']}]({bug['Evidence_Link']})" if bug['Evidence_Link'] else "**🔗 Evidence Link:** None attached.")

                    r_col1, r_col2 = st.columns(2)
                    with r_col1:
                        final_exp = st.text_input("Expected Result:", value=bug['Expected'], key=f"exp_{bug['ID']}")
                    with r_col2:
                        final_act = st.text_input("Actual Result:", value="System did not match PRD criteria.", key=f"act_{bug['ID']}")

                    if st.button(f"Generate AI Jira Draft for {bug['ID']}", key=f"btn_{bug['ID']}"):
                        prompt = f"Severity: {final_sev}\nPriority: {final_pri}\nModule: {mod_val}\nDescription: {bug_desc}\nExpected: {final_exp}\nActual: {final_act}\nEvidence: {bug['Evidence_Link']}"
                        res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role": "user", "content": f"Write a professional Jira ticket: {prompt}"}])
                        st.code(res.choices[0].message.content)
    else:
        st.warning("Generate scenarios in Tab 1 first.")