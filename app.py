import streamlit as st
import pandas as pd
from supabase import create_client
from openai import OpenAI

# --------------------------------------------------
# CONFIG
# --------------------------------------------------
st.set_page_config(page_title="Senior QA Command Center", layout="wide")

# --------------------------------------------------
# INIT CONNECTIONS
# --------------------------------------------------
@st.cache_resource
def init_supabase():
    return create_client(
        st.secrets["SUPABASE_URL"],
        st.secrets["SUPABASE_KEY"]
    )

@st.cache_resource
def init_groq():
    return OpenAI(
        base_url="https://api.groq.com/openai/v1",
        api_key=st.secrets["GROQ_API_KEY"]
    )

supabase = init_supabase()
client = init_groq()

# --------------------------------------------------
# HELPERS
# --------------------------------------------------
def get_projects():
    return supabase.table("projects").select("*").execute().data or []

def create_project(name):
    supabase.table("projects").insert({"name": name}).execute()

def get_project_id(name):
    res = supabase.table("projects").select("id").eq("name", name).execute()
    return res.data[0]["id"]

def save_strategy(pid, rewrite, feature_table, strategy, doubts):
    supabase.table("strategies").upsert({
        "project_id": pid,
        "rewrite": rewrite,
        "feature_table": feature_table,
        "strategy_text": strategy,
        "doubts": doubts
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
        "title": f"Bug from: {row['scenario']}",
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
    st.title("📂 Projects")

    projects = get_projects()
    names = [p["name"] for p in projects]

    selected = st.selectbox("Switch Project", names + ["+ New Project"])

    if selected == "+ New Project":
        new_name = st.text_input("New Project Name")
        if st.button("Create Project"):
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
    "🏗️ Senior QA Audit & Strategy",
    "✅ Execution Log",
    "🐞 Bug Center"
])

# --------------------------------------------------
# TAB 1 – AUDIT (NO TEST CASE DISPLAY)
# --------------------------------------------------
with tab1:
    st.subheader("Senior QA Audit & Strategy")

    prd = st.text_area("Paste PRD", height=200)

    if st.button("Generate Strategy"):
        prompt = f"""
        Analyze the PRD and generate:

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

        save_strategy(pid, result, "", "", "")
        st.success("Generated & Saved")

    strategy = load_strategy(pid)

    if strategy:
        st.markdown(strategy["rewrite"])

# --------------------------------------------------
# TAB 2 – EXECUTION LOG
# --------------------------------------------------
with tab2:
    st.subheader("Execution Log")

    df = load_testcases(pid)

    if df.empty:
        st.info("No test cases found.")
    else:
        df["status"] = df["status"].fillna("Pending")

        edited_df = st.data_editor(
            df,
            column_config={
                "status": st.column_config.SelectboxColumn(
                    "Status",
                    options=["Pending", "Pass", "Fail"]
                )
            },
            use_container_width=True
        )

        if st.button("Save Execution Updates"):
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
        st.info("No Bugs Yet.")
    else:
        for bug in bugs:
            with st.expander(bug["title"]):
                st.write("**Scenario:**", bug["test_cases"]["scenario"])
                st.write("**Assigned To:**", bug["test_cases"]["assigned_to"])
                st.write("**Severity:**", bug["test_cases"]["severity"])
                st.write("**Priority:**", bug["test_cases"]["priority"])
                st.write("**Status:**", bug["status"])
                st.write("**Created At:**", bug["created_at"])
                st.write("**Description:**")
                st.write(bug["description"])