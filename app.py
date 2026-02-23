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

# 3. Persistent Storage Logic
DB_FILE = "qa_database.json"

def load_data():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r") as f:
                return json.load(f)
        except: return {}
    return {}

def save_data(data):
    serializable = {}
    for p_id, p_val in data.items():
        serializable[p_id] = {
            "requirement": p_val.get("requirement", ""),
            "strategy": p_val.get("strategy", ""),
            "risk_summary": p_val.get("risk_summary", ""),
            "tracker_dict": p_val["tracker_df"].to_dict('records') if isinstance(p_val.get("tracker_df"), pd.DataFrame) else []
        }
    with open(DB_FILE, "w") as f:
        json.dump(serializable, f)

# Initialize Session State
if 'project_db' not in st.session_state:
    loaded = load_data()
    st.session_state.project_db = {}
    if not loaded: 
        st.session_state.project_db["Project_ABC"] = {"requirement": "", "strategy": "", "risk_summary": "", "tracker_df": pd.DataFrame(columns=["ID", "Scenario", "Expected", "Status", "Severity", "Priority", "Evidence_Link", "Assigned_To", "Module"])}
    else:
        for p_id, p_val in loaded.items():
            st.session_state.project_db[p_id] = {
                "requirement": p_val.get("requirement", ""),
                "strategy": p_val.get("strategy", ""),
                "risk_summary": p_val.get("risk_summary", ""),
                "tracker_df": pd.DataFrame(p_val.get("tracker_dict", []))
            }

# 4. Sidebar: Project Management, Health Chart, and Export
with st.sidebar:
    st.title("🛡️ QA Hub Manager")
    existing_list = list(st.session_state.project_db.keys())
    selected_project = st.selectbox("Switch/Create Project:", options=existing_list + ["+ New Project"])
    
    if selected_project == "+ New Project":
        new_name = st.text_input("Project Name:")
        if st.button("Create"):
            st.session_state.project_db[new_name] = {
                "requirement": "", "strategy": "", "risk_summary": "",
                "tracker_df": pd.DataFrame(columns=["ID", "Scenario", "Expected", "Status", "Severity", "Priority", "Evidence_Link", "Assigned_To", "Module"])
            }
            st.rerun()
        active_id = existing_list[0]
    else:
        active_id = selected_project

    # MODULE HEALTH CHART
    st.markdown("---")
    st.subheader("📊 Bug Density by Module")
    current_df = st.session_state.project_db[active_id]["tracker_df"]
    if not current_df.empty and "Fail" in current_df["Status"].values:
        fail_data = current_df[current_df["Status"] == "Fail"]
        # Filter out empty module strings for the chart
        clean_fail_data = fail_data[fail_data["Module"].str.strip() != ""]
        if not clean_fail_data.empty:
            chart_data = clean_fail_data["Module"].value_counts()
            st.bar_chart(chart_data)
        else:
            st.info("Assign modules in Bug Center to see health metrics.")
    else:
        st.success("Clean Build: No Bugs!")

    # SAFE EXCEL EXPORT
    st.markdown("---")
    if not current_df.empty:
        try:
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                current_df.to_excel(writer, index=False, sheet_name='Execution_Log')
            st.download_button(
                label="📥 Export Log to Excel",
                data=output.getvalue(),
                file_name=f"{active_id}_QA_Report.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        except ModuleNotFoundError:
            st.warning("Excel library 'xlsxwriter' is installing. Please refresh in a moment.")

    if st.button("💾 Save All Changes"):
        save_data(st.session_state.project_db)
        st.success("Database Saved!")

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
        platform = st.selectbox("Platform", ["Web", "Android", "iOS", "API"])

        if st.button("🚀 Audit PRD & Map Risk"):
            with st.spinner("Analyzing business impact..."):
                prompt = f"""
                Act as a Principal QA Lead. Analyze this PRD: {user_req}
                1. Identify 15+ complex test cases. 
                   Format: 'CASE: [Scenario] | [Expected] | [Severity] | [Priority]'
                2. Provide a 'RISK_REPORT' using clear Markdown headers and bullet points.
                """
                response = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role": "user", "content": prompt}])
                full_res = response.choices[0].message.content.replace("**", "")
                
                if "RISK_REPORT" in full_res:
                    parts = full_res.split("RISK_REPORT")
                    current_data["strategy"] = parts[0]
                    current_data["risk_summary"] = parts[1]
                else:
                    current_data["strategy"] = full_res
                
                lines = [l.replace("CASE:", "").strip() for l in full_res.split("\n") if "CASE:" in l]
                rows = []
                for i, l in enumerate(lines):
                    p = l.split("|")
                    rows.append({
                        "ID": f"TC-{i+1}", 
                        "Scenario": p[0].strip() if len(p)>0 else "N/A",
                        "Expected": p[1].strip() if len(p)>1 else "Functionality works",
                        "Status": "Pending", 
                        "Severity": p[2].strip() if len(p)>2 else "Major",
                        "Priority": p[3].strip() if len(p)>3 else "P1", 
                        "Evidence_Link": "None", "Assigned_To": "Developer", "Module": ""
                    })
                current_data["tracker_df"] = pd.DataFrame(rows)
                st.rerun()

    with col2:
        if current_data.get("risk_summary"):
            st.subheader("🔥 Risk Assessment")
            st.info(current_data["risk_summary"])
            st.divider()
        
        st.subheader("🔍 Structured Test Suite")
        if not current_data["tracker_df"].empty:
            st.dataframe(current_data["tracker_df"][["ID", "Scenario", "Severity", "Priority"]], use_container_width=True, hide_index=True)
        else:
            st.info("Run Audit to generate test suite.")

# --- TAB 2: EXECUTION LOG ---
with tab2:
    st.subheader(f"Execution Log: {active_id}")
    df = current_data.get("tracker_df", pd.DataFrame())
    if not df.empty:
        edited_df = st.data_editor(df, column_config={
                "Status": st.column_config.SelectboxColumn("Status", options=["Pending", "Pass", "Fail"]),
                "Severity": st.column_config.SelectboxColumn("Severity", options=["Blocker", "Critical", "Major", "Minor"]),
                "Priority": st.column_config.SelectboxColumn("Priority", options=["P0", "P1", "P2", "P3"]),
            }, use_container_width=True, key=f"editor_{active_id}")
        current_data["tracker_df"] = edited_df
    else:
        st.warning("Generate scenarios in Tab 1.")

# --- TAB 3: BUG CENTER ---
with tab3:
    st.subheader("🐞 Automated Bug Reports")
    df_check = current_data.get("tracker_df", pd.DataFrame())
    fails = df_check[df_check["Status"] == "Fail"] if not df_check.empty else pd.DataFrame()
    
    if fails.empty:
        st.info("No failed cases detected.")
    else:
        for index, bug in fails.iterrows():
            prd_context = current_data.get("requirement", "").upper()
            found_mod = ""
            for m in ["HOME", "LANDING", "PLP", "PDP", "CART", "CHECKOUT"]:
                if m in prd_context and m in bug['Scenario'].upper():
                    found_mod = m.title()
                    break

            with st.expander(f"Report: {bug['ID']} - {bug['Scenario']}"):
                b_col1, b_col2 = st.columns(2)
                with b_col1:
                    final_mod = st.text_input("Module Name:", value=found_mod if found_mod else bug.get("Module", ""), key=f"mod_{bug['ID']}", placeholder="e.g. Checkout")
                    current_data["tracker_df"].at[index, "Module"] = final_mod
                    
                    final_sev = st.selectbox("Severity:", options=["Blocker", "Critical", "Major", "Minor"], 
                                             index=["Blocker", "Critical", "Major", "Minor"].index(bug['Severity']) if bug['Severity'] in ["Blocker", "Critical", "Major", "Minor"] else 2, 
                                             key=f"sev_{bug['ID']}")
                with b_col2:
                    final_pri = st.selectbox("Priority:", options=["P0", "P1", "P2", "P3"], 
                                             index=["P0", "P1", "P2", "P3"].index(bug['Priority']) if bug['Priority'] in ["P0", "P1", "P2", "P3"] else 1, 
                                             key=f"pri_{bug['ID']}")
                    final_ass = st.text_input("Assigned To:", value=bug['Assigned_To'], key=f"ass_{bug['ID']}")
                
                final_exp = st.text_input("Expected Result:", value=bug['Expected'], key=f"exp_{bug['ID']}")
                final_act = st.text_input("Actual Result:", value="Does not meet criteria.", key=f"act_{bug['ID']}")

                if st.button(f"Generate Jira Draft for {bug['ID']}", key=f"btn_{bug['ID']}"):
                    report_prompt = f"Professional Jira bug report for {bug['Scenario']}. Module: {final_mod}. Severity: {final_sev}. Link: {bug['Evidence_Link']}"
                    res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role": "user", "content": report_prompt}])
                    st.code(res.choices[0].message.content)