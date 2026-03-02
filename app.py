import streamlit as st
from supabase import create_client
from groq import Groq
import json

st.set_page_config(page_title="QA Command Center", layout="wide")

# -------------------------
# Clients
# -------------------------

supabase = create_client(
    st.secrets["SUPABASE_URL"],
    st.secrets["SUPABASE_KEY"]
)

groq_client = Groq(api_key=st.secrets["GROQ_API_KEY"])

# -------------------------
# Navigation
# -------------------------

st.sidebar.title("QA Command Center")

menu = st.sidebar.radio(
    "Navigate",
    ["Senior QA Audit", "Testcases", "Bug Center", "Execution Log"]
)

# -------------------------
# Project Selection
# -------------------------

projects = supabase.table("projects").select("*").execute().data or []
project_names = [p["name"] for p in projects]

selected_project = st.sidebar.selectbox(
    "Select Project",
    project_names if project_names else ["No Projects"]
)

new_project = st.sidebar.text_input("Create New Project")

if st.sidebar.button("Create Project"):
    if new_project:
        supabase.table("projects").insert({"name": new_project}).execute()
        st.rerun()

project_id = None
for p in projects:
    if p["name"] == selected_project:
        project_id = p["id"]

# -------------------------
# 1️⃣ SENIOR QA AUDIT
# -------------------------

if menu == "Senior QA Audit":

    st.title("Senior QA Audit & Strategy")

    feature_name = st.text_input("Feature Name")
    prd_text = st.text_area("Paste PRD Here", height=200)

    if st.button("Generate Audit"):

        if not project_id:
            st.error("Select project first.")
            st.stop()

        prd_text = prd_text[:6000]

        prompt = f"""
Return valid JSON only.

Feature: {feature_name}

PRD:
{prd_text}

Return:
{{
  "summary": "",
  "feature_table": "",
  "strategy": "",
  "pm_doubts": ""
}}
"""

        response = groq_client.chat.completions.create(
            model="llama3-8b-8192",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            response_format={"type": "json_object"}
        )

        audit_data = json.loads(response.choices[0].message.content)

        supabase.table("audits").insert({
            "project_id": project_id,
            "summary": audit_data.get("summary"),
            "feature_table": audit_data.get("feature_table"),
            "strategy": audit_data.get("strategy"),
            "pm_doubts": audit_data.get("pm_doubts")
        }).execute()

        st.success("Audit Saved")

# -------------------------
# 2️⃣ TESTCASE SECTION
# -------------------------

elif menu == "Testcases":

    st.title("Testcase Management")

    tcs = supabase.table("testcases").select("*").eq("project_id", project_id).execute().data or []

    for t in tcs:
        st.markdown(f"### {t['title']}")
        st.write("Type:", t["type"])
        st.write("Priority:", t["priority"])
        st.write("Steps:", t["steps"])
        st.write("Expected:", t["expected_result"])
        st.divider()

# -------------------------
# 3️⃣ BUG CENTER
# -------------------------

elif menu == "Bug Center":

    st.title("Bug Center")

    summary = st.text_input("Bug Summary")
    severity = st.selectbox("Severity", ["Low", "Medium", "High", "Critical"])
    status = st.selectbox("Status", ["Open", "In Progress", "Resolved"])
    steps = st.text_area("Steps to Reproduce")

    if st.button("Report Bug"):
        supabase.table("bugs").insert({
            "project_id": project_id,
            "summary": summary,
            "severity": severity,
            "status": status,
            "steps": steps
        }).execute()

        st.success("Bug Reported")

    bugs = supabase.table("bugs").select("*").eq("project_id", project_id).execute().data or []

    for b in bugs:
        st.markdown(f"### {b['summary']}")
        st.write("Severity:", b["severity"])
        st.write("Status:", b["status"])
        st.write("Steps:", b["steps"])
        st.divider()

# -------------------------
# 4️⃣ EXECUTION LOG
# -------------------------

elif menu == "Execution Log":

    st.title("Execution Log")

    tcs = supabase.table("testcases").select("*").eq("project_id", project_id).execute().data or []

    tc_map = {tc["title"]: tc["id"] for tc in tcs}

    selected_tc = st.selectbox("Select Testcase", list(tc_map.keys()) if tc_map else [])

    status = st.selectbox("Execution Status", ["Pass", "Fail", "Blocked"])
    executed_by = st.text_input("Executed By")
    notes = st.text_area("Notes")

    if st.button("Log Execution") and selected_tc:
        supabase.table("execution_logs").insert({
            "testcase_id": tc_map[selected_tc],
            "status": status,
            "executed_by": executed_by,
            "notes": notes
        }).execute()

        st.success("Execution Logged")

    logs = supabase.table("execution_logs").select("*").execute().data or []

    for l in logs:
        st.markdown(f"### Status: {l['status']}")
        st.write("Executed By:", l["executed_by"])
        st.write("Notes:", l["notes"])
        st.divider()