import streamlit as st
import pandas as pd
from openai import OpenAI

# 1. Page Config
st.set_page_config(page_title="Team QA Portal", layout="wide")

# 2. Safe Key Loading from Streamlit Secrets
# This will work both locally (from your secrets.toml) and on the web.
try:
    client = OpenAI(
        base_url="https://api.groq.com/openai/v1", 
        api_key=st.secrets["GROQ_API_KEY"]
    )
except Exception:
    st.error("API Key not found. Please check your Secrets settings.")

# 3. Sidebar Instructions for PM/Devs
with st.sidebar:
    st.title("📖 Handover Guide")
    st.write("""
    **To generate test cases:**
    1. Paste the Feature requirements in the box.
    2. Choose 'Web' or 'App'.
    3. Click 'Generate'.
    
    **To track progress:**
    Use the 'Execution Tracker' tab to mark items as Pass/Fail.
    """)

# 4. Main Dashboard UI
st.title("🚀 Shared QA Command Center")

tab1, tab2 = st.tabs(["Planner", "Execution Tracker"])

with tab1:
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("📋 Requirements")
        req_input = st.text_area("Paste Feature description here:", height=250)
        platform = st.selectbox("Platform", ["Web", "Android", "iOS"])
        
        if st.button("Generate Test Plan"):
            with st.spinner("AI is analyzing for edge cases..."):
                prompt = f"Act as a Senior QA. Create a detailed test plan for this {platform} feature: {req_input}. Include edge cases specifically for {platform}."
                response = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[{"role": "user", "content": prompt}]
                )
                st.session_state['plan'] = response.choices[0].message.content

    with col2:
        st.subheader("📝 Generated Plan")
        if 'plan' in st.session_state:
            st.markdown(st.session_state['plan'])
        else:
            st.info("The test plan will appear here after generation.")

with tab2:
    st.subheader("✅ Manual Test Log")
    if 'tracker_data' not in st.session_state:
        st.session_state.tracker_data = pd.DataFrame([{"Scenario": "Feature loads", "Status": "Pending"}])
    
    # Allows team members to add/edit rows directly
    st.data_editor(st.session_state.tracker_data, num_rows="dynamic")