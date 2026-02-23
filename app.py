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

# Initialize Session State
if 'project_db' not in st.session_state:
    loaded = load_data()
    st.session_state.project_db = {}
    if not loaded: 
        st.session_state.project_db["Project_ABC"] = {"requirement": "", "risk_summary": "", "tracker_df": pd.DataFrame(columns=["ID", "Scenario", "Expected", "Status", "Severity", "Priority", "Evidence_Link", "Assigned_To", "Module"])}
    else:
        for p_id, p_val in loaded.items():
            st.session_state.project_db[p_id] = {
                "requirement": p_val.get("requirement", ""),
                "risk_summary": p_val.get("risk_summary", ""),
                "tracker_df": pd.DataFrame(p_val.get("tracker_dict", []))
            }

# 4. Sidebar & Project Management
with st.sidebar:
    st.title("🛡️ QA Hub Manager")
    existing_list = list(st.session_state.project_db.keys())
    selected_project = st.selectbox("Active Project:", options=existing_list + ["+ New Project"])
    
    if selected_project == "+ New Project":
        new_name = st.text_input("New Project Name:")
        if st.button("Create"):
            st.session_state.project_db[new_name] = {"requirement": "", "risk_summary": "", "tracker_df": pd.DataFrame(columns=["ID", "Scenario", "Expected", "Status", "Severity", "Priority", "Evidence_Link", "Assigned_To", "Module"])}
            st.rerun()
        active_id = existing_list[0]
    else:
        active_id = selected_project

    st.markdown("---")
    if st.button("💾 Save All Changes"):
        save_data(st.session_state.project_db)
        st.success("Data Persistence Secured!")

current_data = st.session_state.project_db[active_id]

# 5. UI Tabs
tab1, tab2, tab3 = st.tabs(["🏗️ PRD & Risk Analysis", "✅ Execution Log", "🐞 Bug Center"])

# --- TAB 1: PRD ANALYSIS (Formatting Fix) ---
with tab1:
    col1, col2 = st.columns([1, 1.2])
    with col1:
        st.subheader("📋 Requirements Document")
        user_req = st.text_area("Paste PRD here:", value=current_data.get("requirement", ""), height=400)
        current_data["requirement"] = user_req
        
        if st.button("🚀 Audit PRD & Generate Strategy"):
            with st.spinner("Processing..."):
                prompt = f"Analyze PRD: {user_req}. Generate 15+ test cases in format: 'CASE: [Scenario] | [Expected] | [Severity] | [Priority]'. Also include a 'RISK_REPORT' in markdown."
                response = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role": "user", "content": prompt}])
                full_res = response.choices[0].message.content
                
                if "RISK_REPORT" in full_res:
                    parts = full_res.split("RISK_REPORT")
                    current_data["risk_summary"] = parts[1]
                
                # Parsing Logic
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
        st.subheader("🔥 AI Risk-Mapped Strategy")
        if not current_data["tracker_df"].empty:
            # FIX: Using dataframe for table view to prevent continuous text wall
            st.dataframe(current_data["tracker_df"][["ID", "Scenario", "Severity", "Priority"]], use_container_width=True, hide_index=True)
            if current_data.get("risk_summary"):
                with st.expander("View Risk Analysis"):
                    st.markdown(current_data["risk_summary"])
        else:
            st.info("Upload PRD to see structured strategy.")

# --- TAB 2: EXECUTION LOG ---
with tab2:
    st.subheader(f"Execution Log: {active_id}")
    df = current_data.get("tracker_df", pd.DataFrame())
    if not df.empty:
        edited_df = st.data_editor(df, column_config={
                "Status": st.column_config.SelectboxColumn("Status", options=["Pending", "Pass", "Fail"]),
                "Evidence_Link": st.column_config.LinkColumn("Evidence Link")
            }, use_container_width=True, key=f"editor_{active_id}")
        current_data["tracker_df"] = edited_df
        
        st.markdown("---")
        st.subheader("🎥 Attach Evidence")
        ec1, ec2 = st.columns([1, 2])
        target_tc = ec1.selectbox("Select TC:", options=edited_df["ID"])
        link_val = ec2.text_input("Paste Screen Recording URL (Loom/Drive):")
        if st.button("🔗 Link Evidence"):
            idx = current_data["tracker_df"].index[current_data["tracker_df"]["ID"] == target_tc][0]
            current_data["tracker_df"].at[idx, "Evidence_Link"] = link_val
            st.success("Evidence Linked!")
    else:
        st.warning("Generate scenarios in Tab 1.")

# --- TAB 3: BUG CENTER ---
with tab3:
    st.subheader("🐞 Bug Center")
    df_check = current_data.get("tracker_df", pd.DataFrame())
    fails = df_check[df_check["Status"] == "Fail"].copy()
    
    if fails.empty:
        st.info("No failures logged.")
    else:
        for index, bug in fails.iterrows():
            # Module Logic: Pre-fill only if certain
            prd_text = current_data.get("requirement", "").upper()
            found_mod = ""
            for m in ["PDP", "PLP", "CHECKOUT", "HOME", "CART"]:
                if m in prd_text and m in bug['Scenario'].upper():
                    found_mod = m.title()
                    break

            with st.expander(f"REPORT: {bug['ID']} - {bug['Scenario']}"):
                b1, b2 = st.columns(2)
                # FIX: If found_mod is empty, placeholder "Identify Module" shows as requested
                mod_val = b1.text_input("Module:", value=found_mod if found_mod else bug.get("Module", ""), key=f"mod_{bug['ID']}", placeholder="Identify Module (e.g. Checkout)")
                current_data["tracker_df"].at[index, "Module"] = mod_val
                
                # FIX: Visualizing Evidence Link
                st.markdown(f"**🔗 Evidence:** [{bug['Evidence_Link']}]({bug['Evidence_Link']})" if bug['Evidence_Link'] else "**🔗 Evidence:** None attached.")
                
                # FIX: Added Bug Description Box
                bug_desc = st.text_area("Bug Description / Steps:", value=f"1. Navigate to {mod_val}\n2. Perform: {bug['Scenario']}\n3. Result: Failure.", key=f"desc_{bug['ID']}")
                
                r1, r2 = st.columns(2)
                exp_res = r1.text_input("Expected:", value=bug['Expected'], key=f"exp_{bug['ID']}")
                act_res = r2.text_input("Actual:", value="Result did not match PRD criteria.", key=f"act_{bug['ID']}")

                if st.button(f"Generate AI Jira Draft for {bug['ID']}", key=f"btn_{bug['ID']}"):
                    prompt = f"Project: {active_id}\nModule: {mod_val}\nDescription: {bug_desc}\nExpected: {exp_res}\nActual: {act_res}\nLink: {bug['Evidence_Link']}"
                    res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role": "user", "content": f"Write a Jira bug report: {prompt}"}])
                    st.code(res.choices[0].message.content)