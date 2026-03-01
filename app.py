import streamlit as st
import sqlite3
import json
from datetime import datetime

# ---------------- DB SETUP ---------------- #

conn = sqlite3.connect("qa_tool.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS audit (
    project_id INTEGER,
    rewrite TEXT,
    feature_table TEXT,
    strategy TEXT,
    doubts TEXT,
    FOREIGN KEY(project_id) REFERENCES projects(id)
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS test_cases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER,
    title TEXT,
    steps TEXT,
    expected TEXT,
    assigned_to TEXT,
    status TEXT DEFAULT 'Pending',
    FOREIGN KEY(project_id) REFERENCES projects(id)
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS bugs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER,
    test_case_id INTEGER,
    title TEXT,
    description TEXT,
    assigned_to TEXT,
    created_at TEXT,
    FOREIGN KEY(project_id) REFERENCES projects(id)
)
""")

conn.commit()

# ---------------- HELPER FUNCTIONS ---------------- #

def get_projects():
    cursor.execute("SELECT id, name FROM projects")
    return cursor.fetchall()

def get_audit(project_id):
    cursor.execute("SELECT rewrite, feature_table, strategy, doubts FROM audit WHERE project_id=?", (project_id,))
    return cursor.fetchone()

def save_audit(project_id, rewrite, feature_table, strategy, doubts):
    cursor.execute("DELETE FROM audit WHERE project_id=?", (project_id,))
    cursor.execute("INSERT INTO audit VALUES (?, ?, ?, ?, ?)", 
                   (project_id, rewrite, feature_table, strategy, doubts))
    conn.commit()

def get_test_cases(project_id):
    cursor.execute("SELECT id, title, steps, expected, assigned_to, status FROM test_cases WHERE project_id=?", (project_id,))
    return cursor.fetchall()

def save_bug(project_id, test_case_id, title, desc, assigned):
    cursor.execute("""
        INSERT INTO bugs (project_id, test_case_id, title, description, assigned_to, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (project_id, test_case_id, title, desc, assigned, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()

def get_bugs(project_id):
    cursor.execute("SELECT id, title, description, assigned_to, created_at FROM bugs WHERE project_id=?", (project_id,))
    return cursor.fetchall()

# ---------------- UI ---------------- #

st.title("🏗️ Senior QA Operating System")

# Project Selection
projects = get_projects()
project_names = [p[1] for p in projects]

new_project = st.text_input("Create New Project")
if st.button("Create Project"):
    cursor.execute("INSERT INTO projects (name) VALUES (?)", (new_project,))
    conn.commit()
    st.rerun()

if projects:
    selected_name = st.selectbox("Select Project", project_names)
    selected_project = [p for p in projects if p[1] == selected_name][0]
    project_id = selected_project[0]

    tabs = st.tabs(["🏗️ Senior QA Audit & Strategy", "🧪 Test Cases", "✅ Execution Log", "🐞 Bug Center"])

    # ---------------- TAB A ---------------- #
    with tabs[0]:
        st.subheader("Senior QA Audit & Strategy")

        audit_data = get_audit(project_id)
        rewrite = audit_data[0] if audit_data else ""
        feature_table = audit_data[1] if audit_data else ""
        strategy = audit_data[2] if audit_data else ""
        doubts = audit_data[3] if audit_data else ""

        rewrite = st.text_area("1️⃣ REWRITE", rewrite, height=150)
        feature_table = st.text_area("2️⃣ FEATURE TABLE", feature_table, height=150)
        strategy = st.text_area("3️⃣ STRATEGY", strategy, height=150)
        doubts = st.text_area("4️⃣ DOUBTS", doubts, height=150)

        if st.button("Save Audit"):
            save_audit(project_id, rewrite, feature_table, strategy, doubts)
            st.success("Saved")

    # ---------------- TAB B ---------------- #
    with tabs[1]:
        st.subheader("Test Case Management")

        title = st.text_input("Test Case Title")
        steps = st.text_area("Steps")
        expected = st.text_area("Expected Result")
        assigned = st.text_input("Assign Developer")

        if st.button("Add Test Case"):
            cursor.execute("""
                INSERT INTO test_cases (project_id, title, steps, expected, assigned_to)
                VALUES (?, ?, ?, ?, ?)
            """, (project_id, title, steps, expected, assigned))
            conn.commit()
            st.success("Test Case Added")
            st.rerun()

        st.divider()

        test_cases = get_test_cases(project_id)

        for tc in test_cases:
            st.markdown(f"### {tc[1]}")
            st.write(f"**Assigned To:** {tc[4]}")
            st.write(f"Steps: {tc[2]}")
            st.write(f"Expected: {tc[3]}")
            st.write(f"Status: {tc[5]}")
            st.divider()

    # ---------------- TAB C ---------------- #
    with tabs[2]:
        st.subheader("Execution Log")

        test_cases = get_test_cases(project_id)

        for tc in test_cases:
            st.markdown(f"### {tc[1]}")
            status = st.selectbox(
                "Status",
                ["Pending", "Pass", "Fail"],
                index=["Pending", "Pass", "Fail"].index(tc[5]),
                key=f"status_{tc[0]}"
            )

            if status != tc[5]:
                cursor.execute("UPDATE test_cases SET status=? WHERE id=?", (status, tc[0]))
                conn.commit()

                if status == "Fail":
                    save_bug(
                        project_id,
                        tc[0],
                        f"Bug from: {tc[1]}",
                        f"Auto-generated from failed test case.\n\nSteps:\n{tc[2]}",
                        tc[4]
                    )
                st.rerun()

            st.write(f"Assigned To: {tc[4]}")
            st.divider()

    # ---------------- TAB D ---------------- #
    with tabs[3]:
        st.subheader("Bug Center")

        bugs = get_bugs(project_id)

        if bugs:
            for bug in bugs:
                st.markdown(f"### 🐞 {bug[1]}")
                st.write(f"**Assigned To:** {bug[3]}")
                st.write(f"**Created At:** {bug[4]}")
                st.text_area("Description", bug[2], key=f"bug_{bug[0]}")
                st.divider()
        else:
            st.info("No Bugs Yet")

else:
    st.info("Create a project to begin.")