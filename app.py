import streamlit as st
import pandas as pd
import re
from supabase import create_client
from openai import OpenAI

# --------------------------------------------------
# CONFIG
# --------------------------------------------------
st.set_page_config(page_title="Senior QA Command Center", layout="wide")

# --------------------------------------------------
# CONNECTIONS
# --------------------------------------------------
@st.cache_resource
def init_supabase():
    return create_client(
        st.secrets["SUPABASE_URL"],
        st.secrets["SUPABASE_KEY"]
    )

@st.cache_resource
def init_ai():
    return OpenAI(
        base_url="https://api.groq.com/openai/v1",
        api_key=st.secrets["GROQ_API_KEY"]
    )

supabase = init_supabase()
client = init_ai()

# --------------------------------------------------
# DATABASE HELPERS
# --------------------------------------------------
def get_projects():
    return supabase.table("projects").select("*").execute().data or []

def create_project(name):
    supabase.table("projects").insert({"name": name}).execute()

def get_project_id(name):
    res = supabase.table("projects").select("id").eq("name", name).execute()
    return res.data[0]["id"]

def save_strategy(pid, content):
    supabase.table("strategies").upsert({
        "project_id": pid,
        "rewrite": content
    }).execute()

def load_strategy(pid):
    res = supabase.table("strategies").select("*").eq("project_id", pid).execute()
    return res.data[0] if res.data else None

def load_testcases(pid):
    res = supabase.table("test_cases").select("*").eq("project_id", pid).execute()
    return pd.DataFrame(res.data) if res.data else pd.DataFrame()

def save_testcases(df):
    if not df.empty:
        supabase.table("test_cases").upsert(df.to_dict("records")).execute()

def bug_exists(test_case_id):
    res = supabase.table("bugs").select("id").eq("test_case_id", test_case_id).execute()
    return bool(res.data)

def create_bug(row):
    supabase.table("bugs").insert({
        "test_case_id": row["id"],
        "title": f"Bug: {row['scenario']}",
        "description": f"Expected:\n{row['expected']}\n\nActual:\n{row.get('actual_result','')}",
        "status": "Open"
    }).execute()

def load_bugs_for_project(pid):
    res = supabase.table("bugs") \
        .select("*, test_cases!inner(project_id, scenario, assigned_to, severity, priority)") \
        .eq("test_cases.project_id", pid) \
        .execute()
    return res.data or []

# --------------------------------------------------
# SIDEBAR
# --------------------------------------------------
with st.sidebar:
    st.title("Projects")

    projects = get_projects()
    names = [p["name"] for p in projects]

    selected = st.selectbox("Select Project", names + ["+ New Project"])

    if selected == "+ New Project":
        new_name = st.text_input("New Project Name")
        if st.button("Create"):
            create_project(new_name)
            st.rerun()
    else:
        pid = get_project_id(selected)
        st.session_state.project_id = pid

if "project_id" not in st.session_state:
    st.info("Create or select a project.")
    st.stop()

pid = st.session_state.project_id

# --------------------------------------------------
# TABS
# --------------------------------------------------
tab1, tab2, tab3 = st.tabs([
    "Senior QA Audit & Strategy",
    "Execution Log",
    "Bug Center"
])

# --------------------------------------------------
# TAB 1 – AUDIT
# --------------------------------------------------
with tab1:
    st.subheader("Senior QA Audit & Strategy")

    prd = st.text_area("Paste PRD", height=250)

    if st.button("Generate Audit Strategy"):
        prompt = f"""
You are a Senior QA Architect.

Generate:
1. REWRITE
2. FEATURE TABLE
3. STRATEGY
4. DOUBTS

Do NOT generate test cases.

PRD:
{prd}
"""

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}]
        )

        result = response.choices[0].message.content
        save_strategy(pid, result)
        st.success("Audit Strategy Saved")

    strategy = load_strategy(pid)
    if strategy:
        st.markdown(strategy["rewrite"])

# --------------------------------------------------
# TAB 2 – EXECUTION LOG
# --------------------------------------------------
with tab2:
    st.subheader("Execution Log")

    # ---------- Generate Test Cases ----------
    if st.button("Generate Test Cases"):

        strategy = load_strategy(pid)

        if not strategy:
            st.warning("Generate Audit Strategy first.")
        else:
            prompt = """
Generate 15 professional test cases.

Return ONLY pipe separated values.

Format strictly:
Scenario | Expected Result | Severity | Priority | Module
"""

            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}]
            )

            raw_text = response.choices[0].message.content.strip()

            rows = []
            tc_counter = 1

            for line in raw_text.split("\n"):
                if "|" not in line:
                    continue

                parts = [p.strip() for p in line.split("|")]
                if len(parts) != 5:
                    continue

                def clean(text):
                    text = re.sub(r"^\d+\.\s*", "", text)
                    text = re.sub(r"^(scenario|expected|expected result|severity|priority|module)\s*:\s*", "", text, flags=re.IGNORECASE)
                    return text.strip()

                scenario = clean(parts[0])
                expected = clean(parts[1])
                severity = clean(parts[2])
                priority = clean(parts[3])
                module = clean(parts[4])

                rows.append({
                    "project_id": pid,
                    "case_id": f"TC_{tc_counter:03}",
                    "scenario": scenario,
                    "expected": expected,
                    "severity": severity,
                    "priority": priority,
                    "module": module,
                    "status": "Pending"
                })

                tc_counter += 1

            if rows:
                supabase.table("test_cases").insert(rows).execute()
                st.success(f"{len(rows)} Test Cases Generated")
                st.rerun()

    # ---------- Load & Execute ----------
    df = load_testcases(pid)

    if df.empty:
        st.info("No test cases found.")
    else:
        df_display = df.drop(columns=["id", "project_id", "created_at"], errors="ignore")

        edited_df = st.data_editor(
            df_display,
            column_config={
                "status": st.column_config.SelectboxColumn(
                    "Status",
                    options=["Pending", "Pass", "Fail"]
                )
            },
            use_container_width=True
        )

        if st.button("Save Execution Updates"):

            edited_df["id"] = df["id"]
            edited_df["project_id"] = df["project_id"]

            save_testcases(edited_df)

            for _, row in edited_df.iterrows():
                if row["status"] == "Fail":
                    if not bug_exists(row["id"]):
                        create_bug(row)

            st.success("Execution Updated")
            st.rerun()

# --------------------------------------------------
# TAB 3 – BUG CENTER
# --------------------------------------------------
with tab3:
    st.subheader("Bug Center")

    bugs = load_bugs_for_project(pid)

    if not bugs:
        st.info("No Bugs Reported.")
    else:
        for bug in bugs:
            with st.expander(f"{bug['title']}"):

                st.write("Scenario:", bug["test_cases"]["scenario"])
                st.write("Severity:", bug["test_cases"]["severity"])
                st.write("Priority:", bug["test_cases"]["priority"])
                st.write("Assigned To:", bug["test_cases"]["assigned_to"])

                new_status = st.selectbox(
                    "Status",
                    ["Open", "In Progress", "Fixed", "Closed"],
                    index=["Open", "In Progress", "Fixed", "Closed"].index(bug["status"]),
                    key=f"status_{bug['id']}"
                )

                detailed_desc = st.text_area(
                    "Detailed Description / Steps to Reproduce",
                    value=bug["description"],
                    height=150,
                    key=f"desc_{bug['id']}"
                )

                if st.button("Update Bug", key=f"btn_{bug['id']}"):
                    supabase.table("bugs").update({
                        "status": new_status,
                        "description": detailed_desc
                    }).eq("id", bug["id"]).execute()

                    st.success("Bug Updated")
                    st.rerun()