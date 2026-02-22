import streamlit as st
import pandas as pd
from openai import OpenAI

# 1. Page Config
st.set_page_config(page_title="QA Command Center Pro", layout="wide", page_icon="🛡️")

# 2. Setup AI Client
try:
    client = OpenAI(
        base_url="https://api.groq.com/openai/v1", 
        api_key=st.secrets["GROQ_API_KEY"]
    )
except Exception:
    st.error("API Key missing! Please add GROQ_API_KEY to your Streamlit Secrets.")

# 3. Project Database (Persistence in Session State)
if 'project_db' not in st.session_state:
    st.session_state.project_db = {}

# 4. Sidebar: Project Management
with st.sidebar:
    st.title("🛡️ Project Manager")
    project_id = st.text_input("Enter Project ID/Name:", value="Project_ABC")
    
    # Initialize project if new
    if project_id not in st.session_state.project_db:
        st.session_state.project_db[project_id] = {
            "requirement": "",
            "plan_text": "",
            "tracker_df": pd.DataFrame(columns=["ID", "Scenario", "Status", "Notes"])
        }
    
    current_data = st.session_state.project_db[project_id]
    st.success(f"Active: {project_id}")
    st.markdown("---")
    st.info("💡 Generate a plan in Tab 1, and it will auto-populate the log in Tab 2.")

# 5. Main UI Header
st.title(f"🚀 QA Dashboard: {project_id}")

tab1, tab2, tab3 = st.tabs(["🏗️ Test Planner", "✅ Execution Tracker", "🐞 Bug Reporter"])

# --- TAB 1: PLANNER (The Brain) ---
with tab1:
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("Requirements")
        user_req = st.text_area("Paste User Story / Requirement:", 
                               value=current_data["requirement"], 
                               height=250, 
                               placeholder="e.g., Login with OTP and Google Auth...")
        current_data["requirement"] = user_req
        
        platform = st.selectbox("Platform", ["Web", "Android", "iOS", "API"])

        if st.button("✨ Generate & Auto-Log Test Cases"):
            if not user_req:
                st.warning("Please enter a requirement first.")
            else:
                with st.spinner("Analyzing for edge cases and deep-dive scenarios..."):
                    # Paranoid Senior QA Prompt for better quality
                    prompt = f"""
                    Act as a Senior Lead QA. Create a detailed test plan for: {platform}.
                    Requirement: {user_req}
                    
                    Include: Happy Path, Negative cases, Security, and {platform} edge cases.
                    
                    FORMAT: Return ONLY a list of test cases starting with 'CASE: [Title] | [Expected Result]'
                    """
                    
                    response = client.chat.completions.create(
                        model="llama-3.3-70b-versatile",
                        messages=[{"role": "system", "content": "You are a meticulous QA Engineer."},
                                  {"role": "user", "content": prompt}]
                    )
                    
                    plan_result = response.choices[0].message.content
                    current_data["plan_text"] = plan_result
                    
                    # AUTO-LOGGING LOGIC: Extract and move to Tracker
                    lines = [line.replace("CASE:", "").strip() for line in plan_result.split("\n") if "CASE:" in line]
                    new_rows = []
                    for i, line in enumerate(lines):
                        parts = line.split("|")
                        scenario = parts[0].strip() if len(parts) > 0 else line
                        expected = parts[1].strip() if len(parts) > 1 else "Works as expected"
                        new_rows.append({"ID": f"TC-{i+1}", "Scenario": scenario, "Status": "Pending", "Notes": expected})
                    
                    current_data["tracker_df"] = pd.DataFrame(new_rows)
                    st.rerun()

    with col2:
        st.subheader("Detailed Test Strategy")
        if current_data["plan_text"]:
            st.markdown(current_data["plan_text"])
        else:
            st.info("AI-generated plan will appear here.")

# --- TAB 2: EXECUTION (The Log) ---
with tab2:
    st.subheader("Manual Execution Tracker")
    if not current_data["tracker_df"].empty:
        # Interactive Editor
        updated_tracker = st.data_editor(
            current_data["tracker_df"], 
            num_rows="dynamic", 
            use_container_width=True,
            key=f"editor_{project_id}"
        )
        current_data["tracker_df"] = updated_tracker
        
        # Download Button
        csv = updated_tracker.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Export Project Results (CSV)", csv, f"{project_id}_report.csv", "text/csv")
    else:
        st.warning("No test cases found. Generate them in the Planner tab first.")

# --- TAB 3: BUG REPORTER (The Secretary) ---
with tab3:
    st.subheader("AI Bug Formatter")
    raw_bug = st.text_area("Quickly describe the failure:", placeholder="Login fails on Android when no internet...")
    if st.button("🛠️ Format for Developers"):
        with st.spinner("Formatting..."):
            bug_prompt = f"Format this into a professional bug report for {platform}: {raw_bug}"
            res = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": bug_prompt}]
            )
            st.code(res.choices[0].message.content, language="markdown")