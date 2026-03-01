import streamlit as st
import sqlite3
from datetime import datetime

# ---------------- DATABASE ---------------- #

conn = sqlite3.connect("qa_system.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS audit (
    project_id INTEGER PRIMARY KEY,
    rewrite TEXT,
    feature_table TEXT,
    strategy TEXT,
    doubts TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS testcases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER,
    title TEXT,
    steps TEXT,
    expected TEXT,
    assigned_to TEXT,
    status TEXT DEFAULT 'Pending'
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS bugs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER,
    testcase_id INTEGER,
    title TEXT,
    description TEXT,
    assigned_to TEXT,
    created_at TEXT
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
    cursor.execute("""
    INSERT OR REPLACE INTO audit (project_id, rewrite, feature_table, strategy, doubts)
    VALUES (?, ?, ?, ?, ?)
    """, (project_id, rewrite, feature_table, strategy, doubts))
    conn.commit()

def get_testcases(project_id):
    cursor.execute("SELECT * FROM testcases WHERE project_id=?", (project_id,))
    return cursor.fetchall()

def update_status(testcase_id, new_status):
    cursor.execute("UPDATE testcases SET status=? WHERE id=?", (new_status, testcase_id))
    conn.commit()

def create_bug(project_id, testcase_id, title, steps, assigned):
    cursor.execute("""
    INSERT INTO bugs (project_id, testcase_id, title, description, assigned_to, created_at)
    VALUES (?, ?, ?, ?, ?, ?)
    """, (
        project_id,
        testcase_id,
        f"Bug from: {title}",
        f"Auto generated from failed testcase\n\nSteps:\n{steps}",
        assigned,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ))
    conn.commit()

def get_bugs(project_id):
    cursor.execute("SELECT * FROM bugs WHERE project_id=?", (project_id,))
    return cursor.fetchall()

# ---------------- UI ---------------- #

st.title("🏗️ Senior QA Operating System")

# Project Section
projects = get_projects()
project_names = [p[1] for p in projects]

new_project = st.text_input("Create New Project")
if st.button("Create Project"):
    cursor.execute("INSERT INTO projects (name) VALUES (?)", (new_project,))
    conn.commit()
    st.rerun()

if projects:
    selected_name = st.selectbox("Select Project", project_names)
    project_id = [p[0] for p in projects if p[1] == selected_name][0]

    tabs = st.tabs(["🏗️ Senior QA Audit & Strategy", "🧪 Test Case Section", "🐞 Bug Center"])

    # ---------------- TAB 1 ---------------- #
    with tabs[0]:
        st.subheader("A) 🏗️ Senior QA Audit & Strategy")

        audit = get_audit(project_id)

        rewrite = audit[0] if audit else ""
        feature_table = audit[1] if audit else ""
        strategy = audit[2] if audit else ""
        doubts = audit[3] if audit else ""

        rewrite = st.text_area("1️⃣ REWRITE", rewrite, height=150)
        feature_table = st.text_area("2️⃣ FEATURE TABLE", feature_table, height=150)
        strategy = st.text_area("3️⃣ STRATEGY", strategy, height=150)
        doubts = st.text_area("4️⃣ DOUBTS", doubts, height=150)

        if st.button("Save Audit Section"):
            save_audit(project_id, rewrite, feature_table, strategy, doubts)
            st.success("Saved Successfully")

    # ---------------- TAB 2 ---------------- #
    with tabs[1]:
        st.subheader("B) 🧪 Test Case Section")

        title = st.text_input("Test Case Title")
        steps = st.text_area("Steps")
        expected = st.text_area("Expected Result")
        assigned_to = st.text_input("Assign Developer")

        if st.button("Add Test Case"):
            cursor.execute("""
            INSERT INTO testcases (project_id, title, steps, expected, assigned_to)
            VALUES (?, ?, ?, ?, ?)
            """, (project_id, title, steps, expected, assigned_to))
            conn.commit()
            st.rerun()

        st.divider()

        testcases = get_testcases(project_id)

        for tc in testcases:
            st.markdown(f"### {tc[2]}")
            st.write(f"**Assigned To:** {tc[5]}")
            st.write(f"Steps: {tc[3]}")
            st.write(f"Expected: {tc[4]}")

            new_status = st.selectbox(
                "Status",
                ["Pending", "Pass", "Fail"],
                index=["Pending", "Pass", "Fail"].index(tc[6]),
                key=f"status_{tc[0]}"
            )

            if new_status != tc[6]:
                update_status(tc[0], new_status)

                if new_status == "Fail":
                    create_bug(project_id, tc[0], tc[2], tc[3], tc[5])

                st.rerun()

            st.divider()

    # ---------------- TAB 3 ---------------- #
    with tabs[2]:
        st.subheader("C) 🐞 Bug Center")

        bugs = get_bugs(project_id)

        if bugs:
            for bug in bugs:
                st.markdown(f"### 🐞 {bug[3]}")
                st.write(f"**Assigned To:** {bug[5]}")
                st.write(f"**Created At:** {bug[6]}")
                desc = st.text_area("Bug Description", bug[4], key=f"bug_{bug[0]}")
                st.divider()
        else:
            st.info("No Bugs Reported Yet")

else:
    st.info("Create a project to begin.")