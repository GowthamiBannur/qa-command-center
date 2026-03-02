import streamlit as st
from supabase import create_client
from groq import Groq
import json

# -------------------------
# CONFIG
# -------------------------

st.set_page_config(page_title="QA Command Center", layout="wide")

# Clients
supabase = create_client(
    st.secrets["SUPABASE_URL"],
    st.secrets["SUPABASE_KEY"]
)

groq_client = Groq(api_key=st.secrets["GROQ_API_KEY"])

# -------------------------
# FUNCTIONS
# -------------------------

def generate_audit(feature_name, prd_text):
    prompt = f"""
You are a Senior QA Architect.

For the feature: {feature_name}

Based on this PRD:
{prd_text}

Return strictly valid JSON:

{{
  "summary": "",
  "feature_table": "",
  "strategy": "",
  "pm_doubts": ""
}}
"""

    response = groq_client.chat.completions.create(
        model="llama3-70b-8192",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2
    )

    return json.loads(response.choices[0].message.content)


def generate_testcases(feature_name, prd_text):
    prompt = f"""
Generate structured JSON test cases.

Feature: {feature_name}
PRD:
{prd_text}

Return JSON array:

[
  {{
    "title": "",
    "type": "",
    "priority": "",
    "steps": "",
    "expected_result": ""
  }}
]
"""

    response = groq_client.chat.completions.create(
        model="llama3-70b-8192",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2
    )

    return json.loads(response.choices[0].message.content)

# -------------------------
# SIDEBAR
# -------------------------

st.sidebar.title("Projects")

projects = supabase.table("projects").select("*").execute().data
project_names = [p["name"] for p in projects]

selected_project = st.sidebar.selectbox(
    "Select Project",
    project_names if project_names else ["No Projects"]
)

new_project = st.sidebar.text_input("Create New Project")

if st.sidebar.button("Create"):
    if new_project:
        supabase.table("projects").insert({"name": new_project}).execute()
        st.rerun()

# Get project_id
project_id = None
for p in projects:
    if p["name"] == selected_project:
        project_id = p["id"]

# -------------------------
# MAIN
# -------------------------

st.title("Senior QA Audit & Strategy")

feature_name = st.text_input("Feature Name")
prd_text = st.text_area("Paste PRD Here", height=200)

if st.button("Generate Audit & Testcases"):

    if project_id and feature_name and prd_text:

        # Generate Audit
        audit_data = generate_audit(feature_name, prd_text)

        supabase.table("audits").insert({
            "project_id": project_id,
            "summary": audit_data["summary"],
            "feature_table": audit_data["feature_table"],
            "strategy": audit_data["strategy"],
            "pm_doubts": audit_data["pm_doubts"]
        }).execute()

        # Generate Testcases
        testcases = generate_testcases(feature_name, prd_text)

        for tc in testcases:
            supabase.table("testcases").insert({
                "project_id": project_id,
                "title": tc["title"],
                "type": tc["type"],
                "priority": tc["priority"],
                "steps": tc["steps"],
                "expected_result": tc["expected_result"]
            }).execute()

        st.success("Saved Successfully")

# -------------------------
# DISPLAY SAVED DATA
# -------------------------

if project_id:

    st.subheader("Saved Audits")

    audits = supabase.table("audits").select("*").eq("project_id", project_id).execute().data

    for a in audits:
        st.markdown("### Summary")
        st.write(a["summary"])

        st.markdown("### Feature Table")
        st.write(a["feature_table"])

        st.markdown("### Strategy")
        st.write(a["strategy"])

        st.markdown("### PM Doubts")
        st.write(a["pm_doubts"])

        st.divider()

    st.subheader("Saved Testcases")

    tcs = supabase.table("testcases").select("*").eq("project_id", project_id).execute().data

    for t in tcs:
        st.markdown(f"**{t['title']}**")
        st.write("Type:", t["type"])
        st.write("Priority:", t["priority"])
        st.write("Steps:", t["steps"])
        st.write("Expected:", t["expected_result"])
        st.divider()