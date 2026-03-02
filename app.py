import streamlit as st
from supabase import create_client
from groq import Groq
import json

# -------------------------------------------------
# CONFIG
# -------------------------------------------------

st.set_page_config(page_title="QA Command Center", layout="wide")

supabase = create_client(
    st.secrets["SUPABASE_URL"],
    st.secrets["SUPABASE_KEY"]
)

groq_client = Groq(api_key=st.secrets["GROQ_API_KEY"])

# -------------------------------------------------
# HELPER: Safe JSON Extractor
# -------------------------------------------------

def extract_json(text):
    try:
        start = text.find("{")
        end = text.rfind("}") + 1
        return json.loads(text[start:end])
    except:
        return None

# -------------------------------------------------
# SIDEBAR NAVIGATION
# -------------------------------------------------

st.sidebar.title("QA Command Center")

menu = st.sidebar.radio(
    "Navigate",
    ["Senior QA Audit", "AI Testcase Generator", "Testcases", "Bug Center", "Execution Log"]
)

# -------------------------------------------------
# PROJECT MANAGEMENT
# -------------------------------------------------

projects_response = supabase.table("projects").select("*").execute()
projects = projects_response.data or []

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

# -------------------------------------------------
# 1️⃣ SENIOR QA AUDIT
# -------------------------------------------------

if menu == "Senior QA Audit":

    st.title("Senior QA Audit & Strategy")

    feature_name = st.text_input("Feature Name")
    prd_text = st.text_area("Paste PRD Here", height=250)

    if st.button("Generate Audit"):

        if not project_id:
            st.error("Select a project first.")
            st.stop()

        prd_text = prd_text[:5000]

        prompt = f"""
You are a Senior QA Architect.

Return ONLY valid JSON.
No markdown.
No explanations.

Feature: {feature_name}

PRD:
{prd_text}

JSON format:
{{
  "summary": "",
  "feature_table": "",
  "strategy": "",
  "pm_doubts": ""
}}
"""

        try:
            response = groq_client.chat.completions.create(
                model="llama3-8b-8192",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2
            )

            raw_text = response.choices[0].message.content.strip()
            audit_data = extract_json(raw_text)

            if not audit_data:
                st.error("AI did not return valid JSON.")
                st.stop()

            supabase.table("audits").insert({
                "project_id": project_id,
                "summary": audit_data.get("summary"),
                "feature_table": audit_data.get("feature_table"),
                "strategy": audit_data.get("strategy"),
                "pm_doubts": audit_data.get("pm_doubts")
            }).execute()

            st.success("Audit Saved Successfully")

        except Exception as e:
            st.error(f"Groq Error: {e}")

# -------------------------------------------------
# 2️⃣ AI TESTCASE GENERATOR
# -------------------------------------------------

elif menu == "AI Testcase Generator":

    st.title("AI Testcase Generator")

    feature_name = st.text_input("Feature Name")
    prd_text = st.text_area("Paste PRD Here", height=250)

    if st.button("Generate Testcases"):

        if not project_id:
            st.error("Select a project first.")
            st.stop()

        prd_text = prd_text[:5000]

        prompt = f"""
You are a Senior QA Architect.

Return ONLY valid JSON.
No markdown.
No explanations.

Feature: {feature_name}

PRD:
{prd_text}

JSON format:
{{
  "testcases": [
    {{
      "title": "",
      "type": "",
      "priority": "",
      "steps": "",
      "expected_result": ""
    }}
  ]
}}
"""

        try:
            response = groq_client.chat.completions.create(
                model="llama3-8b-8192",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2
            )

            raw_text = response.choices[0].message.content.strip()
            data = extract_json(raw_text)

            if not data or "testcases" not in data:
                st.error("AI did not return valid testcases.")
                st.stop()

            for tc in data["testcases"]:
                supabase.table("testcases").insert({
                    "project_id": project_id,
                    "title": tc.get("title"),
                    "type": tc.get("type"),
                    "priority": tc.get("priority"),
                    "steps": tc.get("steps"),
                    "expected_result": tc.get("expected_result")
                }).execute()

            st.success("Testcases Saved Successfully")

        except Exception as e:
            st.error(f"Groq Error: {e}")

# -------------------------------------------------
# 3️⃣ TESTCASE VIEW
# -------------------------------------------------

elif menu == "Testcases":

    st.title("Saved Testcases")

    tcs = supabase.table("testcases").select("*").eq("project_id", project_id).execute().data or []

    for t in tcs:
        st.markdown(f"### {t['title']}")
        st.write("Type:", t["type"])
        st.write("Priority:", t["priority"])
        st.write("Steps:", t["steps"])
        st.write("Expected:", t["expected_result"])
        st.divider()

# -------------------------------------------------
# 4️⃣ BUG CENTER
# -------------------------------------------------

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

# -------------------------------------------------
# 5️⃣ EXECUTION LOG
# -------------------------------------------------

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