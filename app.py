import streamlit as st
import database as db

st.set_page_config(
    page_title="MedAdhere — Medication Adherence Tracker",
    page_icon="💊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Bootstrap DB ─────────────────────────────────────────────────────────────
db.init_db()

# ── Session helpers ───────────────────────────────────────────────────────────

def is_logged_in():
    return "user" in st.session_state and st.session_state["user"] is not None


def logout():
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()


# ── Auth Pages ────────────────────────────────────────────────────────────────

def render_login_page():
    st.markdown(
        """
        <div style='text-align:center;padding:40px 0 20px 0'>
            <span style='font-size:64px'>💊</span>
            <h1 style='margin:10px 0 4px 0;color:#1f2328'>MedAdhere</h1>
            <p style='color:#57606a;font-size:16px'>AI-Powered Medication Adherence Tracking</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col_left, col_center, col_right = st.columns([1, 1.2, 1])
    with col_center:
        tab_login, tab_register = st.tabs(["🔐 Login", "📝 Register"])

        with tab_login:
            st.markdown("### Welcome Back")
            with st.form("login_form"):
                username = st.text_input("Username", placeholder="Enter your username")
                password = st.text_input("Password", type="password", placeholder="Enter your password")
                submitted = st.form_submit_button("Login", use_container_width=True, type="primary")

            if submitted:
                if username and password:
                    user = db.authenticate_user(username, password)
                    if user:
                        st.session_state["user"] = user
                        st.session_state["chat_messages"] = []
                        st.success(f"Welcome, {user['full_name']}!")
                        st.rerun()
                    else:
                        st.error("Invalid username or password.")
                else:
                    st.warning("Please enter both username and password.")

            st.markdown("---")
            st.markdown("**Demo Accounts:**")
            demo_data = {
                "👤 Patient": ("patient1", "pass123"),
                "👨‍👩‍👧 Caregiver": ("caregiver1", "pass123"),
                "🏥 Doctor": ("doctor1", "pass123"),
            }
            for label, (uname, pwd) in demo_data.items():
                if st.button(f"Login as {label}", key=f"demo_{uname}", use_container_width=True):
                    user = db.authenticate_user(uname, pwd)
                    if user:
                        st.session_state["user"] = user
                        st.session_state["chat_messages"] = []
                        st.rerun()

        with tab_register:
            st.markdown("### Create Account")
            with st.form("register_form"):
                reg_username = st.text_input("Username *")
                reg_password = st.text_input("Password *", type="password")
                reg_confirm = st.text_input("Confirm Password *", type="password")
                reg_full_name = st.text_input("Full Name *")
                reg_email = st.text_input("Email")
                reg_role = st.selectbox("Role", ["patient", "caregiver", "doctor"],
                                        format_func=lambda r: {"patient": "👤 Patient",
                                                                "caregiver": "👨‍👩‍👧 Caregiver",
                                                                "doctor": "🏥 Doctor"}[r])
                reg_submit = st.form_submit_button("Register", use_container_width=True, type="primary")

            if reg_submit:
                if not all([reg_username, reg_password, reg_full_name]):
                    st.error("Please fill in all required fields.")
                elif reg_password != reg_confirm:
                    st.error("Passwords do not match.")
                elif len(reg_password) < 6:
                    st.error("Password must be at least 6 characters.")
                else:
                    success, msg = db.register_user(reg_username, reg_password, reg_role, reg_full_name, reg_email)
                    if success:
                        st.success(msg + " Please log in.")
                    else:
                        st.error(msg)


# ── Sidebar ───────────────────────────────────────────────────────────────────

def render_sidebar(user: dict):
    with st.sidebar:
        st.markdown(
            f"""
            <div style='background:#f7f8fa;border-radius:10px;padding:16px;margin-bottom:16px;
                        border:1px solid #e5e7eb;text-align:center'>
                <div style='font-size:40px'>
                    {"👤" if user["role"] == "patient" else "👨‍👩‍👧" if user["role"] == "caregiver" else "🏥"}
                </div>
                <div style='font-weight:700;font-size:16px;color:#1f2328;margin-top:6px'>
                    {user["full_name"]}
                </div>
                <div style='font-size:12px;color:#57606a;margin-top:2px'>
                    {user["role"].capitalize()} · @{user["username"]}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if user["role"] == "patient":
            _render_patient_sidebar_widgets(user)

        st.markdown("---")
        if st.button("🚪 Logout", use_container_width=True):
            logout()

        st.markdown(
            "<div style='text-align:center;color:#aaa;font-size:11px;margin-top:20px'>"
            "💊 MedAdhere v1.0<br>Powered by Gemini 2.5 Flash</div>",
            unsafe_allow_html=True,
        )


def _render_patient_sidebar_widgets(user: dict):
    """Show today's dose status in the sidebar for patients."""
    from datetime import date as d_date
    today = d_date.today().isoformat()
    logs_today = [
        l for l in db.get_logs(user["id"], days=1)
        if l["scheduled_date"] == today
    ]

    medications = db.get_medications(user["id"])
    total_doses = sum(m["times_per_day"] for m in medications)
    taken_today = sum(1 for l in logs_today if l["status"] == "taken")

    st.markdown("### 📅 Today's Summary")
    if total_doses > 0:
        pct = round(taken_today / total_doses * 100)
        st.progress(pct / 100, text=f"{taken_today}/{total_doses} doses taken ({pct}%)")

        if pct == 100:
            st.success("🎉 All doses taken today!")
        elif pct >= 50:
            st.info(f"💊 {total_doses - taken_today} dose(s) remaining")
        else:
            st.warning(f"⚠️ {total_doses - taken_today} dose(s) pending")
    else:
        st.info("No medications scheduled.")

    # Upcoming reminders
    from datetime import datetime as dt
    from database import get_reminders
    reminders = get_reminders(user["id"])
    now_time = dt.now().strftime("%H:%M")
    upcoming = [r for r in reminders if r["reminder_time"] >= now_time][:3]

    if upcoming:
        st.markdown("### ⏰ Upcoming Reminders")
        for r in upcoming:
            st.markdown(f"🔔 **{r['reminder_time']}** — {r['med_name']}")

    # Streak
    st.markdown("### 🔥 Adherence Stats")
    stats = db.get_adherence_stats(user["id"], 7)
    color = "#2ecc71" if stats["rate"] >= 80 else "#f39c12" if stats["rate"] >= 60 else "#e74c3c"
    st.markdown(
        f"<div style='background:{color}22;border-left:4px solid {color};padding:8px 12px;"
        f"border-radius:6px;'><b style='color:{color};font-size:20px'>{stats['rate']}%</b>"
        f"<span style='color:#57606a;font-size:12px;margin-left:8px'>7-day adherence</span></div>",
        unsafe_allow_html=True,
    )


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    if not is_logged_in():
        render_login_page()
        return

    user = st.session_state["user"]
    render_sidebar(user)

    if user["role"] == "patient":
        import patient_dashboard
        patient_dashboard.render_patient_dashboard(user)
    elif user["role"] in ("caregiver", "doctor"):
        import caregiver_dashboard
        caregiver_dashboard.render_caregiver_dashboard(user)
    else:
        st.error("Unknown role. Please contact support.")


if __name__ == "__main__":
    main()
