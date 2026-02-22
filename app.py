import streamlit as st
import pandas as pd
from openai import OpenAI
from io import BytesIO

# 1. Page Config
st.set_page_config(page_title="QA Command Center Pro", layout="wide", page_icon="🛡️")

# 2. Setup Client
try:
    client = OpenAI(
        base_url="https://api.groq.com/openai/v1", 
        api_key=st.secrets["GROQ_API_KEY"]
    )
except Exception:
    st.error("API Key missing! Add GROQ_API_KEY to your Streamlit Secrets.")

# 3. Sidebar with Advanced Tools
with st.sidebar:
    st.title("🛡️ QA Toolbox")
    st.markdown("---")
    test_mode = st.select_slider("Test Rigor:", options=["Standard", "Regression", "Paranoid"])
    st.info(f"Current Mode: **{test_mode}**")
    
    st.markdown("### 📖 Quick Help")
    st.caption("1. Paste requirements in 'Planner'.")
    st.caption("2. Track progress in 'Execution'.")
    st.caption("3. Export results when finished.")

# 4. Main UI Logic
st.title("🚀 Shared QA Command Center")

tab1, tab2, tab3 = st.tabs(["📋 Test Planner", "✅ Execution Tracker", "🐞 Bug Reporter"])

# --- TAB 1: PLANNER ---
with tab1:
    col1, col2 = st.columns([1, 1])
    with col1:
        st.subheader("Input Requirements")
        req_input = st.text_area("User Story / Jira Description:", height=250, placeholder="Paste here...")
        platform = st.selectbox("Target Platform", ["Web Browser", "Android App", "iOS App", "API/Backend"])
        
        if st.button("✨ Generate Comprehensive Plan"):
            if not req_input:
                st.warning("Please paste a requirement first!")
            else:
                with st.spinner(f"AI is thinking in {test_mode} mode..."):
                    # Enhanced Prompt
                    prompt = f"""
                    Act as a Senior QA Lead. Generate a test plan for: {platform}.
                    Rigor Level: {test_mode}.
                    Requirement: {req_input}
                    
                    Format with:
                    - **Happy Path** (Standard flow)
                    - **Negative Testing** (Error states)
                    - **{platform} Specific Edge Cases** (Device/Browser quirks)
                    - **UI/UX Consistency**
                    """
                    
                    response = client.chat.completions.create(
                        model="llama-3.3-70b-versatile",
                        messages=[{"role": "user", "content": prompt}]
                    )
                    st.session_state['plan'] = response.choices[0].message.content

    with col2:
        st.subheader("Generated Strategy")
        if 'plan' in st.session_state:
            st.markdown(st.session_state['plan'])
        else:
            st.info("Your test strategy will appear here.")

# --- TAB 2: EXECUTION ---
with tab2:
    st.subheader("Manual Test Execution Log")
    
    # Initialize tracker data
    if 'tracker_data' not in st.session_state:
        st.session_state.tracker_data = pd.DataFrame([
            {"ID": "TC1", "Scenario": "Verify Login", "Status": "Pending", "Notes": ""}
        ])

    # Dynamic Editor
    edited_df = st.data_editor(st.session_state.tracker_data, num_rows="dynamic", use_container_width=True)
    st.session_state.tracker_data = edited_df

    # Export to CSV
    csv = edited_df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 Download Test Results (CSV)",
        data=csv,
        file_name='test_execution_report.csv',
        mime='text/csv',
    )

# --- TAB 3: BUG REPORTER ---
with tab3:
    st.subheader("Quick Bug Report Generator")
    st.write("Found a bug? Describe it simply, and let AI format it for Jira/GitHub.")
    
    bug_desc = st.text_area("Describe the bug (Steps/Observed/Expected):", height=150)
    
    if st.button("🛠️ Format Bug Report"):
        with st.spinner("Formatting..."):
            bug_prompt = f"Turn this messy bug description into a professional QA bug report with Title, Steps to Reproduce, Expected vs Observed Result: {bug_desc}"
            bug_res = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": bug_prompt}]
            )
            st.code(bug_res.choices[0].message.content, language="markdown")
            st.success("Copy the code above into your Bug Tracker!")