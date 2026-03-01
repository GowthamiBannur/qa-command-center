import streamlit as st
import pandas as pd
import os
import re
from openai import OpenAI

# =========================
# PAGE CONFIG
# =========================
st.set_page_config(page_title="QA Command Center", layout="wide")

client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

TESTCASE_FILE = "testcases.csv"
BUG_FILE = "bugs.csv"

# =========================
# HELPER FUNCTIONS
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
# LOAD DATA
# =========================
testcase_columns = [
    "project_id",
    "case_id",
    "scenario",
    "expected",
    "severity",
    "priority",
    "module",
    "status",
]

bug_columns = [
    "bug_id",
    "project_id",
    "case_id",
    "bug_title",
    "severity",
    "status",
]

tc_df = load_csv(TESTCASE_FILE, testcase_columns)
bug_df = load_csv(BUG_FILE, bug_columns)

# =========================
# TABS
# =========================
tab1, tab2, tab3 = st.tabs(
    ["Generate Testcases", "Execution Log", "Bug Centre"]
)

# =========================================================
# TAB 1 — GENERATE TESTCASES
# =========================================================
with tab1:

    st.header("Generate AI Test Cases")

    project_id = st.text_input("Project ID")
    feature_input = st.text_area("Enter Feature / PRD")

    if st.button("Generate Test Cases"):

        if not project_id or not feature_input:
            st.warning("Please enter Project ID and Feature.")
        else:

            with st.spinner("Generating test cases..."):

                # CLEAN MODE: delete old test cases of this project
                tc_df = tc_df[tc_df["project_id"] != project_id]

                prompt = f"""
You are a senior QA architect.

Generate 15 structured test cases.

Return STRICTLY in this format:
Scenario | Expected Result | Severity | Priority | Module

No numbering.
No prefixes.
No explanations.

Feature:
{feature_input}
"""

                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.3,
                )

                output = response.choices[0].message.content.strip()
                lines = output.split("\n")

                rows = []
                tc_counter = 1

                for line in lines:

                    if "|" not in line:
                        continue

                    parts = [clean_text(p) for p in line.split("|")]

                    if len(parts) != 5:
                        continue

                    scenario, expected, severity, priority, module = parts

                    rows.append(
                        {
                            "project_id": project_id,
                            "case_id": f"TC_{tc_counter:03}",
                            "scenario": scenario,
                            "expected": expected,
                            "severity": severity,
                            "priority": priority,
                            "module": module,
                            "status": "Pending",
                        }
                    )

                    tc_counter += 1

                new_df = pd.DataFrame(rows, columns=testcase_columns)

                tc_df = pd.concat([tc_df, new_df], ignore_index=True)

                save_csv(tc_df, TESTCASE_FILE)

                st.success("Test cases generated successfully.")

# =========================================================
# TAB 2 — EXECUTION LOG
# =========================================================
with tab2:

    st.header("Execution Log")

    if tc_df.empty:
        st.info("No test cases available.")
    else:

        edited_df = st.data_editor(
            tc_df,
            use_container_width=True,
        )

        if st.button("Save Execution Updates"):
            save_csv(edited_df, TESTCASE_FILE)
            st.success("Execution log updated successfully.")

# =========================================================
# TAB 3 — BUG CENTRE
# =========================================================
with tab3:

    st.header("Bug Centre")

    if tc_df.empty:
        st.info("Generate test cases first.")
    else:

        project_filter = st.selectbox(
            "Select Project",
            tc_df["project_id"].unique(),
        )

        project_cases = tc_df[
            tc_df["project_id"] == project_filter
        ]

        case_select = st.selectbox(
            "Select Test Case",
            project_cases["case_id"],
        )

        bug_title = st.text_input("Bug Title")
        bug_severity = st.selectbox(
            "Severity",
            ["Low", "Medium", "High", "Critical"],
        )

        bug_status = st.selectbox(
            "Status",
            ["Open", "In Progress", "Closed"],
        )

        if st.button("Report Bug"):

            if not bug_title:
                st.warning("Enter bug title.")
            else:

                bug_id = f"BUG_{len(bug_df)+1:03}"

                new_bug = pd.DataFrame(
                    [
                        {
                            "bug_id": bug_id,
                            "project_id": project_filter,
                            "case_id": case_select,
                            "bug_title": bug_title,
                            "severity": bug_severity,
                            "status": bug_status,
                        }
                    ]
                )

                bug_df = pd.concat(
                    [bug_df, new_bug], ignore_index=True
                )

                save_csv(bug_df, BUG_FILE)

                st.success("Bug reported successfully.")

        st.subheader("Logged Bugs")
        st.dataframe(bug_df)