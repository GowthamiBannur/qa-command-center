import streamlit as st
import pandas as pd
from openai import OpenAI
import json

# 1. Setup
st.set_page_config(page_title="QA Command Center Pro", layout="wide")
client = OpenAI(base_url="https://api.groq.com/openai/v1", api_key=st.secrets["GROQ_API_KEY"])

# Initialize Database in Session State
if 'project_db' not in st.session_state:
    st.session_state.project_db = {}

st.title("🛡️ Project-Based QA Dashboard")

# 2. Project Selection
project_name = st.sidebar.text_input("Current Project Name:", value="Project_ABC")
if project_name not in st.session_state.project_db:
    st.session_state.project_db[project_name] = {
        "requirement": "",
        "test_plan": "",
        "tracker": pd.DataFrame(columns=["ID", "Scenario", "Status", "Bug_Logged"])
    }

current_project = st.session_state.project_db[project_name]

# 3. Main Interface
tab1, tab2 = st.tabs(["🏗️ Planner & Auto-Log", "📊 Execution & Stats"])

with tab1:
    col1, col2 = st.columns(2)
    with col1:
        st.subheader(f"Requirements for {project_name}")
        req = st.text_area("Enter Requirement:", value=current_project["requirement"], height=200)
        current_project["requirement"] = req
        
        if st.button("🚀 Generate & Auto-Sync to Tracker"):
            with st.spinner("Writing test cases and syncing..."):
                # System prompt to force AI to return a specific format
                prompt = f"Act as a QA. For this req: {req}, provide a list of 5 key test scenarios. Format EACH one exactly like this: 'SCENARIO: [description]'"
                
                response = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[{"role": "user", "content": prompt}]
                )
                
                raw_plan = response.choices[0].message.content
                current_project["test_plan"] = raw_plan
                
                # AUTO-LOGGING LOGIC: Extract lines starting with SCENARIO
                new_scenarios = [line.replace("SCENARIO: ", "") for line in raw_plan.split("\n") if "SCENARIO: " in line]
                
                new_rows = pd.DataFrame([
                    {"ID": f"TC-{i+1}", "Scenario": s, "Status": "Pending", "Bug_Logged": "No"} 
                    for i, s in enumerate(new_scenarios)
                ])
                current_project["tracker"] = new_rows
                st.success("Successfully generated and synced to Execution Tracker!")

    with col2:
        st.subheader("Generated Plan")
        st.markdown(current_project["test_plan"])

with tab2:
    st.subheader(f"Execution Tracker: {project_name}")
    
    # Calculate Stats
    df = current_project["tracker"]
    if not df.empty:
        total = len(df)
        passed = len(df[df["Status"] == "Pass"])
        failed = len(df[df["Status"] == "Fail"])
        st.write(f"**Stats:** Total: {total} | ✅ Passed: {passed} | ❌ Failed: {failed}")

    # Interactive Tracker
    updated_df = st.data_editor(df, num_rows="dynamic", use_container_width=True)
    current_project["tracker"] = updated_df

    # Auto-Bug Logic Hint
    if not updated_df[updated_df["Status"] == "Fail"].empty:
        st.warning("⚠️ Failures detected! Head to the Bug Reporter to finalize logs.")