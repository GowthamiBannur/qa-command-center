import streamlit as st
import pandas as pd
import os
import re
from openai import OpenAI

# =========================
# PAGE CONFIG
# =========================
st.set_page_config(page_title="QA Command Center", layout="wide")

# =========================
# SAFE API SETUP (GROQ)
# =========================
if "GROQ_API_KEY" not in st.secrets or not st.secrets["GROQ_API_KEY"]:
    st.error("GROQ_API_KEY not configured in Streamlit Secrets.")
    st.stop()

client = OpenAI(
    api_key=st.secrets["GROQ_API_KEY"],
    base_url="https://api.groq.com/openai/v1",
)

TESTCASE_FILE = "testcases.csv"
BUG_FILE = "bugs.csv"

# =========================
# HELPERS
# =========================
def load_csv(file, columns):
    if os.path.exists(file):
        return pd.read_csv(file)
    else:
        return pd.DataFrame(columns=columns)

def save_csv(df, file):
    df.to_csv(file, index=False)

def clean_text(text):
    text = re.sub(r"^\d+\.\s*", "", text)
    text = re.sub(
        r"^(scenario|expected|expected result|severity|priority|module)\s*:\s*",
        "",
        text,
        flags=re.IGNORECASE,
    )
    return text.strip()

# =========================
# DATA
# =========================
testcase_columns = [
    "project_id","case_id","scenario",
    "expected","severity","priority",
    "module","status"
]

bug_columns = [
    "bug_id","project_id","case_id",
    "bug_title","severity","status"
]

tc_df = load_csv(TESTCASE_FILE, testcase_columns)
bug_df = load_csv(BUG_FILE, bug_columns)

# =========================
# SIDEBAR
# =========================
with st.sidebar:
    st.title("QA Command Center")

    st.markdown("### Projects")

    existing_projects = tc_df["project_id"].unique() if not tc_df.empty else []

    selected_project = st.selectbox(
        "Select Project",
        options=["Create New"] + list(existing_projects)
    )

    st.markdown("---")
    st.markdown("### Senior QA Audit & Strategy")

# =========================
# MAIN AREA TABS
# =========================
tab1, tab2, tab3 = st.tabs(
    ["Generate Testcases", "Execution Log", "Bug Center"]
)

# =========================================================
# TAB 1 — GENERATE
# =========================================================
with tab1:

    st.header("Generate AI Test Cases")

    if selected_project == "Create New":
        project_id = st.text_input("Enter New Project ID")
    else:
        project_id = selected_project

    feature_input = st.text_area("Enter Feature / PRD")

    if st.button("Generate Test Cases"):

        if not project_id or not feature_input:
            st.warning("Enter Project ID and Feature.")
        else:

            with st.spinner("Generating..."):

                # Remove old project testcases
                tc_df = tc_df[tc_df["project_id"] != project_id]

                prompt = f"""
Generate 15 QA test cases.

Format strictly:
Scenario | Expected Result | Severity | Priority | Module

No numbering.
No extra text.

Feature:
{feature_input}
"""

                response = client.chat.completions.create(
                    model="llama3-70b-8192",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.3,
                )

                lines = response.choices[0].message.content.strip().split("\n")

                rows = []
                counter = 1

                for line in lines:
                    if "|" not in line:
                        continue

                    parts = [clean_text(p) for p in line.split("|")]

                    if len(parts) != 5:
                        continue

                    scenario, expected, severity, priority, module = parts

                    rows.append({
                        "project_id": project_id,
                        "case_id": f"TC_{counter:03}",
                        "scenario": scenario,
                        "expected": expected,
                        "severity": severity,
                        "priority": priority,
                        "module": module,
                        "status": "Pending"
                    })

                    counter += 1

                new_df = pd.DataFrame(rows, columns=testcase_columns)
                tc_df = pd.concat([tc_df, new_df], ignore_index=True)
                save_csv(tc_df, TESTCASE_FILE)

                st.success("Test cases generated.")

# =========================================================
# TAB 2 — EXECUTION LOG
# =========================================================
with tab2:

    st.header("Execution Log")

    if tc_df.empty:
        st.info("No test cases available.")
    else:
        filtered = tc_df if selected_project == "Create New" else tc_df[tc_df["project_id"] == selected_project]

        edited = st.data_editor(filtered, use_container_width=True)

        if st.button("Save Execution Changes"):
            save_csv(tc_df, TESTCASE_FILE)
            st.success("Saved.")

# =========================================================
# TAB 3 — BUG CENTER
# =========================================================
with tab3:

    st.header("Bug Center")

    if tc_df.empty:
        st.info("Generate test cases first.")
    else:

        filtered = tc_df if selected_project == "Create New" else tc_df[tc_df["project_id"] == selected_project]

        if not filtered.empty:

            case_select = st.selectbox("Select Test Case", filtered["case_id"])

            bug_title = st.text_input("Bug Title")
            severity = st.selectbox("Severity", ["Low","Medium","High","Critical"])
            status = st.selectbox("Status", ["Open","In Progress","Closed"])

            if st.button("Report Bug"):
                bug_id = f"BUG_{len(bug_df)+1:03}"

                new_bug = pd.DataFrame([{
                    "bug_id": bug_id,
                    "project_id": selected_project,
                    "case_id": case_select,
                    "bug_title": bug_title,
                    "severity": severity,
                    "status": status
                }])

                bug_df = pd.concat([bug_df, new_bug], ignore_index=True)
                save_csv(bug_df, BUG_FILE)

                st.success("Bug reported.")

        st.subheader("Logged Bugs")
        st.dataframe(bug_df)