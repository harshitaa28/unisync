import json
import os
import sqlite3
import sys
import uuid
from datetime import datetime, timedelta

DB_PATH = os.environ.get("UNISYNC_DB", os.path.join(os.path.dirname(__file__), "unisync.db"))

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_schema(conn):
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        role TEXT NOT NULL,
        department TEXT NOT NULL,
        year TEXT NOT NULL,
        interests TEXT NOT NULL DEFAULT '[]',
        whatsapp_opt_in INTEGER NOT NULL DEFAULT 1,
        quiet_hours TEXT NOT NULL DEFAULT '22:00 - 07:00',
        onboarded INTEGER NOT NULL DEFAULT 1
    );

    CREATE TABLE IF NOT EXISTS tags (
        id TEXT PRIMARY KEY,
        name TEXT UNIQUE NOT NULL,
        color TEXT NOT NULL DEFAULT 'indigo',
        active INTEGER NOT NULL DEFAULT 1
    );

    CREATE TABLE IF NOT EXISTS clubs (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        description TEXT NOT NULL,
        rep_id TEXT NOT NULL,
        coordinator_id TEXT NOT NULL,
        requires_admin_check INTEGER NOT NULL DEFAULT 1,
        join_mode TEXT NOT NULL DEFAULT 'instant',
        whatsapp_link TEXT NOT NULL,
        member_count INTEGER NOT NULL DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS publishing_routes (
        category TEXT PRIMARY KEY,
        reviewer_role TEXT NOT NULL,
        auto_notify_whatsapp INTEGER NOT NULL DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS events (
        id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        description TEXT NOT NULL,
        category TEXT NOT NULL,
        department TEXT NOT NULL,
        target_year TEXT NOT NULL,
        event_date TEXT NOT NULL,
        deadline TEXT NOT NULL,
        venue TEXT NOT NULL,
        venue_id TEXT NOT NULL,
        registration_link TEXT NOT NULL,
        source_doc TEXT NOT NULL DEFAULT '',
        attachment_url TEXT NOT NULL DEFAULT '',
        status TEXT NOT NULL DEFAULT 'Pending review',
        red_flags TEXT NOT NULL DEFAULT '[]',
        tags TEXT NOT NULL DEFAULT '[]',
        is_free INTEGER NOT NULL DEFAULT 1,
        club_id TEXT DEFAULT NULL,
        author_id TEXT NOT NULL,
        reviewer_comment TEXT NOT NULL DEFAULT '',
        history TEXT NOT NULL DEFAULT '[]',
        merged_into TEXT DEFAULT NULL,
        acknowledged_by TEXT NOT NULL DEFAULT '[]',
        reached_count INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS tickets (
        id TEXT PRIMARY KEY,
        event_id TEXT NOT NULL,
        event_title TEXT NOT NULL,
        student_id TEXT NOT NULL,
        student_name TEXT NOT NULL,
        assigned_admin_id TEXT NOT NULL,
        assigned_admin_name TEXT NOT NULL,
        question TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'Open',
        messages TEXT NOT NULL DEFAULT '[]',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS deadlines (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        event_id TEXT NOT NULL,
        title TEXT NOT NULL,
        deadline TEXT NOT NULL,
        category TEXT NOT NULL,
        completed INTEGER NOT NULL DEFAULT 0,
        saved INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL,
        UNIQUE(user_id, event_id)
    );

    CREATE TABLE IF NOT EXISTS reminders (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        event_id TEXT NOT NULL,
        event_title TEXT NOT NULL,
        offset_label TEXT NOT NULL,
        scheduled_for TEXT NOT NULL,
        channel TEXT NOT NULL DEFAULT 'WhatsApp + Push',
        status TEXT NOT NULL DEFAULT 'Scheduled',
        message_preview TEXT NOT NULL,
        sent_at TEXT DEFAULT NULL
    );

    CREATE TABLE IF NOT EXISTS community_members (
        id TEXT PRIMARY KEY,
        community_id TEXT NOT NULL,
        user_id TEXT NOT NULL,
        user_name TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'joined',
        created_at TEXT NOT NULL,
        UNIQUE(community_id, user_id)
    );

    CREATE TABLE IF NOT EXISTS qa_posts (
        id TEXT PRIMARY KEY,
        community_id TEXT NOT NULL,
        author_id TEXT NOT NULL,
        author_name TEXT NOT NULL,
        author_role TEXT NOT NULL,
        title TEXT NOT NULL,
        body TEXT NOT NULL,
        upvotes INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS qa_answers (
        id TEXT PRIMARY KEY,
        post_id TEXT NOT NULL,
        author_id TEXT NOT NULL,
        author_name TEXT NOT NULL,
        author_role TEXT NOT NULL,
        body TEXT NOT NULL,
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS notifications (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        title TEXT NOT NULL,
        body TEXT NOT NULL,
        type TEXT NOT NULL DEFAULT 'info',
        read INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS outbox (
        id TEXT PRIMARY KEY,
        channel TEXT NOT NULL,
        recipient TEXT NOT NULL,
        subject TEXT NOT NULL,
        body TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'Simulated',
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS timetable (
        id TEXT PRIMARY KEY,
        department TEXT NOT NULL,
        year TEXT NOT NULL,
        day TEXT NOT NULL,
        time_slot TEXT NOT NULL,
        subject TEXT NOT NULL,
        room TEXT NOT NULL,
        faculty_name TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS faculty_cabins (
        id TEXT PRIMARY KEY,
        faculty_id TEXT NOT NULL,
        faculty_name TEXT NOT NULL,
        department TEXT NOT NULL,
        cabin_no TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'Available',
        free_slot TEXT NOT NULL,
        note TEXT NOT NULL DEFAULT ''
    );

    CREATE TABLE IF NOT EXISTS venue_slots (
        id TEXT PRIMARY KEY,
        venue_name TEXT NOT NULL,
        slot_time TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'Available',
        booked_by TEXT NOT NULL DEFAULT ''
    );

    CREATE TABLE IF NOT EXISTS audit_log (
        id TEXT PRIMARY KEY,
        actor_id TEXT NOT NULL,
        actor_name TEXT NOT NULL,
        actor_role TEXT NOT NULL,
        action TEXT NOT NULL,
        target_type TEXT NOT NULL,
        target_id TEXT NOT NULL,
        target_title TEXT NOT NULL,
        comment TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL
    );
    """)
    conn.commit()

def seed_if_empty(conn):
    count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if count > 0:
        return

    now = datetime(2026, 11, 18, 10, 0, 0)
    def ts(days_offset=0, hours_offset=0):
        return (now + timedelta(days=days_offset, hours=hours_offset)).strftime("%Y-%m-%d %H:%M")

    users = [
        ("u_student", "Kabir Sharma", "kabir.sharma@college.edu", "student", "CSE", "3rd Year", json.dumps(["AI/ML", "Placements", "Hackathons", "Web Dev"]), 1, "22:00 - 07:00", 1),
        ("u_rep", "Devansh Nair", "devansh.nair@college.edu", "club_rep", "CSE", "3rd Year", json.dumps(["Hackathons", "Web Dev", "Open Source"]), 1, "23:00 - 07:00", 1),
        ("u_faculty", "Prof. Ananya Rao", "ananya.rao@college.edu", "faculty", "CSE", "Faculty", json.dumps(["AI/ML", "Research", "Workshops"]), 1, "21:00 - 08:00", 1),
        ("u_admin", "Siddharth Joshi", "siddharth.joshi@college.edu", "admin", "Placements & Hackathons", "Staff", json.dumps(["Placements", "Hackathons"]), 1, "22:00 - 07:00", 1),
        ("u_admin_exam", "Meera Iyer", "meera.iyer@college.edu", "admin", "Exams & Timetable", "Staff", json.dumps(["Academics"]), 1, "22:00 - 07:00", 1),
        ("u_admin_venue", "Karan Malhotra", "karan.malhotra@college.edu", "admin", "Events & Auditorium", "Staff", json.dumps(["Clubs", "Workshops"]), 1, "22:00 - 07:00", 1),
    ]
    conn.executemany("INSERT INTO users VALUES (?,?,?,?,?,?,?,?,?,?)", users)

    tags = [
        ("t_1", "AI/ML", "indigo", 1),
        ("t_2", "Placements", "emerald", 1),
        ("t_3", "Hackathons", "violet", 1),
        ("t_4", "Web Dev", "sky", 1),
        ("t_5", "Internships", "amber", 1),
        ("t_6", "Workshops", "teal", 1),
        ("t_7", "Robotics", "rose", 1),
        ("t_8", "Design", "pink", 1),
    ]
    conn.executemany("INSERT INTO tags VALUES (?,?,?,?)", tags)

    clubs = [
        ("c_coding", "Coding Club", "Competitive programming, full-stack sprints, and campus hackathons.", "u_rep", "u_faculty", 1, "instant", "https://chat.whatsapp.com/coding-club-invite-demo", 142),
        ("c_robotics", "Robotics Society", "Autonomous bots, embedded systems, and hardware prototyping.", "u_rep", "u_faculty", 0, "request", "https://chat.whatsapp.com/robotics-soc-invite-demo", 86),
        ("c_placement", "Placement Prep Cell", "Mock interviews, resume reviews, and verified placement drives.", "u_rep", "u_faculty", 1, "request", "https://chat.whatsapp.com/placement-cell-invite-demo", 310),
        ("c_design", "Design & UI Guild", "Product design critiques, Figma jams, and portfolio reviews.", "u_rep", "u_faculty", 0, "instant", "https://chat.whatsapp.com/design-guild-invite-demo", 64),
    ]
    conn.executemany("INSERT INTO clubs VALUES (?,?,?,?,?,?,?,?,?)", clubs)

    routes = [
        ("Placements", "admin", 1),
        ("Academics", "admin", 1),
        ("Hackathons", "faculty_then_admin", 0),
        ("Workshops", "faculty", 0),
        ("Clubs", "faculty_then_admin", 0),
        ("General", "admin", 0),
    ]
    conn.executemany("INSERT INTO publishing_routes VALUES (?,?,?)", routes)

    events = [
        (
            "e_zenith",
            "Mega Hiring Drive: Zenith Corp",
            "Forwarded message circulating on student groups claiming a Rs 18 LPA package with immediate onboarding. Asks students to pay a Rs 499 'assessment verification fee' via an external UPI link.",
            "Placements", "CSE", "3rd Year",
            "2026-11-24 10:00", "2026-11-20 18:00",
            "Placement Cell", "v_placement",
            "https://example.com/zenith-form-unverified",
            "Forwarded WhatsApp Notice (Unverified)", "",
            "Pending review",
            json.dumps(["Registration fee requested (Rs 499)", "Unverified external form domain", "Not listed on Placement Cell portal"]),
            json.dumps(["Placements", "Internships"]), 0, None, "u_student",
            "", json.dumps([{"actor": "System", "action": "Flagged suspicious forward", "time": ts(-1)}]),
            None, json.dumps([]), 0, ts(-1)
        ),
        (
            "e_nimbus",
            "Nimbus Labs Summer Internship 2027",
            "Official 8-week software engineering internship for 3rd year CSE and IT students. Stipend Rs 35,000/month. Resume shortlisting followed by two technical rounds.",
            "Placements", "CSE", "3rd Year",
            "2026-11-28 09:30", "2026-11-21 23:59",
            "Placement Cell", "v_placement",
            "https://example.com/nimbus-official-apply",
            "Placement Cell Circular #PC-2026-41", "",
            "Pending review",
            json.dumps([]),
            json.dumps(["Placements", "Internships", "Web Dev"]), 1, None, "u_faculty",
            "", json.dumps([{"actor": "Prof. Ananya Rao", "action": "Submitted with circular #PC-2026-41", "time": ts(-1, -2)}]),
            None, json.dumps(["u_student"]), 128, ts(-1, -2)
        ),
        (
            "e_nimbus_dup",
            "Nimbus Labs Internship (CSE Group Forward)",
            "Duplicate notice for Nimbus Labs Summer Internship 2027 shared via department broadcast. Same eligibility and Placement Cell circular.",
            "Placements", "CSE", "3rd Year",
            "2026-11-28 09:30", "2026-11-21 23:59",
            "Placement Cell", "v_placement",
            "https://example.com/nimbus-official-apply",
            "Department Broadcast", "",
            "Pending review",
            json.dumps(["Possible duplicate of Nimbus Labs Summer Internship 2027"]),
            json.dumps(["Placements", "Internships"]), 1, None, "u_student",
            "", json.dumps([{"actor": "System", "action": "Detected duplicate match", "time": ts(-1)}]),
            None, json.dumps([]), 0, ts(-1)
        ),
        (
            "e_hackathon",
            "UniHack 2026: Campus AI & Systems Sprint",
            "24-hour student hackathon hosted by Coding Club. Build practical campus tools with mentorship from faculty and alumni. Free entry, meals included, Rs 50,000 prize pool.",
            "Hackathons", "All", "All",
            "2026-11-29 09:00", "2026-11-20 20:00",
            "Main Auditorium", "v_auditorium",
            "https://example.com/unihack-2026",
            "Dean Student Affairs Approval #DSA-19", "",
            "Verified",
            json.dumps([]),
            json.dumps(["Hackathons", "AI/ML", "Web Dev"]), 1, "c_coding", "u_rep",
            "Approved and verified for campus-wide broadcast.",
            json.dumps([
                {"actor": "Devansh Nair", "action": "Submitted event", "time": ts(-3)},
                {"actor": "Prof. Ananya Rao", "action": "Faculty approved", "time": ts(-2)},
                {"actor": "Siddharth Joshi", "action": "Admin verified & published", "time": ts(-2)}
            ]),
            None, json.dumps(["u_student"]), 412, ts(-3)
        ),
        (
            "e_ml_workshop",
            "Hands-On LLM & RAG Systems Workshop",
            "Interactive 3-hour technical workshop on building retrieval-augmented generation pipelines with open-source models. Bring your laptop.",
            "Workshops", "CSE", "3rd Year",
            "2026-11-23 14:00", "2026-11-22 17:00",
            "CS Seminar Hall", "v_cs_block",
            "https://example.com/llm-rag-workshop",
            "CSE Department Notice #CSE-88", "",
            "Verified",
            json.dumps([]),
            json.dumps(["AI/ML", "Workshops"]), 1, "c_coding", "u_faculty",
            "Verified official department workshop.",
            json.dumps([
                {"actor": "Prof. Ananya Rao", "action": "Published workshop", "time": ts(-2)},
                {"actor": "Siddharth Joshi", "action": "Verified", "time": ts(-1)}
            ]),
            None, json.dumps(["u_student"]), 215, ts(-2)
        ),
        (
            "e_exam_schedule",
            "End-Semester Practical Exam Schedule (Sem 5 & 6)",
            "Official timetable for November-December laboratory practical examinations across CSE, IT, and ECE departments.",
            "Academics", "All", "3rd Year",
            "2026-12-02 09:00", "2026-11-25 17:00",
            "Admin Block", "v_admin",
            "https://example.com/exam-timetable-pdf",
            "Controller of Examinations Circular #COE-12", "",
            "Verified",
            json.dumps([]),
            json.dumps(["Workshops"]), 1, None, "u_admin",
            "Official COE circular.",
            json.dumps([{"actor": "Siddharth Joshi", "action": "Published & Verified", "time": ts(-4)}]),
            None, json.dumps(["u_student"]), 640, ts(-4)
        ),
        (
            "e_robotics_draft",
            "Autonomous Rover Build Night",
            "Hands-on evening session assembling ROS2 rover kits for the inter-college robotics challenge.",
            "Clubs", "All", "All",
            "2026-11-26 17:30", "2026-11-25 12:00",
            "Innovation Lab", "v_innovation",
            "https://example.com/rover-night",
            "Lab Booking #LAB-04", "",
            "Pending faculty review",
            json.dumps([]),
            json.dumps(["Robotics", "Workshops"]), 1, "c_robotics", "u_rep",
            "",
            json.dumps([{"actor": "Devansh Nair", "action": "Submitted to Prof. Ananya Rao", "time": ts(0, -3)}]),
            None, json.dumps([]), 0, ts(0, -3)
        ),
    ]
    conn.executemany("INSERT INTO events VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", events)

    tickets = [
        (
            "TKT-101", "e_zenith", "Mega Hiring Drive: Zenith Corp",
            "u_student", "Kabir Sharma", "u_admin", "Siddharth Joshi",
            "This Zenith Corp link is circulating on our class WhatsApp group asking for Rs 499. Is it genuine?",
            "Open",
            json.dumps([{"sender": "Kabir Sharma", "role": "student", "text": "This Zenith Corp link is circulating on our class WhatsApp group asking for Rs 499. Is it genuine?", "time": ts(0, -4)}]),
            ts(0, -4), ts(0, -4)
        )
    ]
    conn.executemany("INSERT INTO tickets VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", tickets)

    deadlines = [
        ("dl_1", "u_student", "e_hackathon", "UniHack 2026: Campus AI & Systems Sprint", "2026-11-20 20:00", "Hackathons", 0, 1, ts(-1)),
        ("dl_2", "u_student", "e_ml_workshop", "Hands-On LLM & RAG Systems Workshop", "2026-11-22 17:00", "Workshops", 0, 1, ts(-1)),
    ]
    conn.executemany("INSERT INTO deadlines VALUES (?,?,?,?,?,?,?,?,?)", deadlines)

    reminders = [
        ("rem_1", "u_student", "e_hackathon", "UniHack 2026: Campus AI & Systems Sprint", "3 days before", "2026-11-17 20:00", "WhatsApp + Push", "Sent", "Reminder: UniHack 2026 registration closes in 3 days (20 Nov, 8:00 PM).", ts(-1)),
        ("rem_2", "u_student", "e_hackathon", "UniHack 2026: Campus AI & Systems Sprint", "1 day before", "2026-11-19 20:00", "WhatsApp + Push", "Due", "Reminder: UniHack 2026 registration closes tomorrow at 8:00 PM!", None),
        ("rem_3", "u_student", "e_hackathon", "UniHack 2026: Campus AI & Systems Sprint", "2 hours before", "2026-11-20 18:00", "WhatsApp + Push", "Scheduled", "Urgent: UniHack 2026 closes in 2 hours!", None),
    ]
    conn.executemany("INSERT INTO reminders VALUES (?,?,?,?,?,?,?,?,?,?)", reminders)

    members = [
        ("cm_1", "c_coding", "u_student", "Kabir Sharma", "joined", ts(-10)),
        ("cm_2", "c_coding", "u_rep", "Devansh Nair", "joined", ts(-30)),
    ]
    conn.executemany("INSERT INTO community_members VALUES (?,?,?,?,?,?)", members)

    qa_posts = [
        ("qa_1", "c_coding", "u_student", "Kabir Sharma", "student", "Can 2nd and 3rd year students form mixed teams for UniHack 2026?", "Our team has two 3rd-year CSE students and one 2nd-year ECE student. Is cross-year teaming allowed?", 7, ts(-2)),
        ("qa_2", "c_placement", "u_student", "Kabir Sharma", "student", "What is the official Placement Cell policy on drives asking for assessment fees?", "Several WhatsApp forwards ask for Rs 300-500 test fees. Does the college ever allow paid placement tests?", 14, ts(-1)),
    ]
    conn.executemany("INSERT INTO qa_posts VALUES (?,?,?,?,?,?,?,?,?)", qa_posts)

    qa_answers = [
        ("ans_1", "qa_1", "u_rep", "Devansh Nair", "club_rep", "Yes! Cross-year and cross-department teams of 2-4 members are welcome.", ts(-2, 2)),
        ("ans_2", "qa_2", "u_admin", "Siddharth Joshi", "admin", "Never. Official campus placement and internship drives are 100% free. Always click 'Request verification' if any forward asks for money.", ts(-1, 1)),
    ]
    conn.executemany("INSERT INTO qa_answers VALUES (?,?,?,?,?,?,?)", qa_answers)

    notifs = [
        ("n_1", "u_student", "Ticket TKT-101 received", "Your verification request for Mega Hiring Drive: Zenith Corp is assigned to Siddharth Joshi.", "info", 0, ts(0, -4)),
        ("n_2", "u_faculty", "New club event awaiting review", "Devansh Nair submitted 'Autonomous Rover Build Night' for Robotics Society.", "warning", 0, ts(0, -3)),
        ("n_3", "u_admin", "2 items in Verification Queue", "Nimbus Labs Summer Internship and Zenith Corp forward need review.", "warning", 0, ts(-1)),
    ]
    conn.executemany("INSERT INTO notifications VALUES (?,?,?,?,?,?,?)", notifs)

    outbox = [
        ("out_1", "WhatsApp", "+91-98XXX-XX104 (Kabir Sharma)", "UniHack 2026 Reminder (3 days)", "Reminder: UniHack 2026 registration closes in 3 days (20 Nov, 8:00 PM). View on UniSync.", "Simulated", ts(-1)),
        ("out_2", "Email", "siddharth.joshi@college.edu", "[UniSync] New Verification Ticket TKT-101", "Kabir Sharma flagged 'Mega Hiring Drive: Zenith Corp' for verification.", "Simulated", ts(0, -4)),
    ]
    conn.executemany("INSERT INTO outbox VALUES (?,?,?,?,?,?,?)", outbox)

    audit = [
        ("aud_1", "u_rep", "Devansh Nair", "club_rep", "SUBMIT_EVENT", "event", "e_hackathon", "UniHack 2026: Campus AI & Systems Sprint", "Submitted for faculty review", ts(-3)),
        ("aud_2", "u_faculty", "Prof. Ananya Rao", "faculty", "APPROVE_CLUB_EVENT", "event", "e_hackathon", "UniHack 2026: Campus AI & Systems Sprint", "Approved; routed to admin check", ts(-2)),
        ("aud_3", "u_admin", "Siddharth Joshi", "admin", "VERIFY_AND_PUBLISH", "event", "e_hackathon", "UniHack 2026: Campus AI & Systems Sprint", "Verified official DSA-19 approval", ts(-2)),
        ("aud_4", "u_rep", "Devansh Nair", "club_rep", "SUBMIT_EVENT", "event", "e_robotics_draft", "Autonomous Rover Build Night", "Routed to Prof. Ananya Rao", ts(0, -3)),
    ]
    conn.executemany("INSERT INTO audit_log VALUES (?,?,?,?,?,?,?,?,?,?)", audit)

    timetable_rows = [
        ("tt_1", "CSE", "3rd Year", "Today", "09:30 - 10:30", "Operating Systems", "Room 302", "Prof. Ananya Rao"),
        ("tt_2", "CSE", "3rd Year", "Today", "10:45 - 11:45", "Database Management", "Room 304", "Dr. Rajesh Verma"),
        ("tt_3", "CSE", "3rd Year", "Today", "12:00 - 01:00", "Computer Networks Lab", "Lab 2", "Prof. Sneha Patil"),
        ("tt_4", "CSE", "3rd Year", "Today", "02:00 - 03:00", "AI & Machine Learning", "Room 302", "Prof. Ananya Rao"),
    ]
    conn.executemany("INSERT INTO timetable VALUES (?,?,?,?,?,?,?,?)", timetable_rows)

    cabin_rows = [
        ("cab_1", "u_faculty", "Prof. Ananya Rao", "CSE", "CS-204", "Available", "03:00 PM - 04:30 PM", "In cabin for project & club doubts"),
        ("cab_2", "u_fac_2", "Dr. Rajesh Verma", "CSE", "CS-208", "In Lecture", "04:00 PM - 05:00 PM", "Teaching DBMS in Room 304"),
        ("cab_3", "u_fac_3", "Prof. Sneha Patil", "CSE", "CS-212", "On Break", "03:15 PM - 04:00 PM", "Back at 3:15 PM"),
    ]
    conn.executemany("INSERT INTO faculty_cabins VALUES (?,?,?,?,?,?,?,?)", cabin_rows)

    venue_rows = [
        ("vs_1", "Main Auditorium", "2026-11-29 (Full Day)", "Booked", "UniHack 2026 (Coding Club)"),
        ("vs_2", "Main Auditorium", "2026-11-30 (10:00 AM - 04:00 PM)", "Available", ""),
        ("vs_3", "CS Seminar Hall", "2026-11-23 (02:00 PM - 05:00 PM)", "Booked", "LLM & RAG Workshop"),
        ("vs_4", "Innovation Lab", "2026-11-26 (05:30 PM - 08:00 PM)", "Available", ""),
    ]
    conn.executemany("INSERT INTO venue_slots VALUES (?,?,?,?,?)", venue_rows)
    conn.commit()

def row_to_dict(r):
    return dict(r) if r else None

def parse_event(r):
    d = dict(r)
    for k in ("red_flags", "tags", "history", "acknowledged_by"):
        try:
            d[k] = json.loads(d[k])
        except Exception:
            d[k] = []
    d["is_free"] = bool(d["is_free"])
    return d

def parse_user(r):
    d = dict(r)
    try:
        d["interests"] = json.loads(d["interests"])
    except Exception:
        d["interests"] = []
    d["whatsapp_opt_in"] = bool(d["whatsapp_opt_in"])
    d["onboarded"] = bool(d["onboarded"])
    return d

def log_audit(conn, user, action, target_type, target_id, target_title, comment=""):
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    conn.execute(
        "INSERT INTO audit_log VALUES (?,?,?,?,?,?,?,?,?,?)",
        ("aud_" + uuid.uuid4().hex[:8], user["id"], user["name"], user["role"], action, target_type, target_id, target_title, comment, now_str)
    )

def notify_user(conn, user_id, title, body, ntype="info"):
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    conn.execute(
        "INSERT INTO notifications VALUES (?,?,?,?,?,?,?)",
        ("n_" + uuid.uuid4().hex[:8], user_id, title, body, ntype, 0, now_str)
    )

def add_outbox(conn, channel, recipient, subject, body):
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    conn.execute(
        "INSERT INTO outbox VALUES (?,?,?,?,?,?,?)",
        ("out_" + uuid.uuid4().hex[:8], channel, recipient, subject, body, "Simulated", now_str)
    )


def summarize_text(title, description, deadline="", venue="", department="All", target_year="All", is_free=True, red_flags=None):
    red_flags = red_flags or []
    sentences = [s.strip() for s in description.replace("\n", " ").split(".") if s.strip()]
    lead = sentences[0] if sentences else title
    if len(lead) > 110:
        lead = lead[:107].rsplit(" ", 1)[0] + "..."
    bullets = [f"Core: {lead}."]
    if deadline or venue:
        bullets.append(f"When & Where: {venue or 'Campus'} · Deadline {deadline or 'TBD'}.")
    elig = f"{department} · {target_year}" if (department != "All" or target_year != "All") else "All departments & years"
    cost = "Free entry" if is_free else "Fee/payment noted — verify before paying"
    bullets.append(f"Eligibility & Cost: {elig} ({cost}).")
    if red_flags:
        bullets.append(f"Caution: {red_flags[0]}.")
    return " | ".join(bullets)

def handle_rpc(conn, req):
    op = req.get("op")
    p = req.get("params", {})
    uid = req.get("userId", "u_student")

    user_row = conn.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    user = parse_user(user_row) if user_row else None

    if op == "bootstrap":
        users = [parse_user(r) for r in conn.execute("SELECT * FROM users").fetchall()]
        tags = [dict(r) for r in conn.execute("SELECT * FROM tags ORDER BY name").fetchall()]
        clubs = [dict(r) for r in conn.execute("SELECT * FROM clubs").fetchall()]
        routes = [dict(r) for r in conn.execute("SELECT * FROM publishing_routes").fetchall()]
        events = [parse_event(r) for r in conn.execute("SELECT * FROM events WHERE merged_into IS NULL ORDER BY created_at DESC").fetchall()]
        for ev in events:
            ev["ai_summary"] = summarize_text(ev["title"], ev["description"], ev["deadline"], ev["venue"], ev["department"], ev["target_year"], ev["is_free"], ev["red_flags"])
        tickets = [dict(r) for r in conn.execute("SELECT * FROM tickets ORDER BY updated_at DESC").fetchall()]
        for t in tickets:
            t["messages"] = json.loads(t["messages"])
        deadlines = [dict(r) for r in conn.execute("SELECT * FROM deadlines WHERE user_id=? ORDER BY deadline ASC", (uid,)).fetchall()]
        reminders = [dict(r) for r in conn.execute("SELECT * FROM reminders ORDER BY scheduled_for ASC").fetchall()]
        members = [dict(r) for r in conn.execute("SELECT * FROM community_members").fetchall()]
        qa_posts = [dict(r) for r in conn.execute("SELECT * FROM qa_posts ORDER BY created_at DESC").fetchall()]
        qa_answers = [dict(r) for r in conn.execute("SELECT * FROM qa_answers ORDER BY created_at ASC").fetchall()]
        notifications = [dict(r) for r in conn.execute("SELECT * FROM notifications WHERE user_id=? ORDER BY created_at DESC", (uid,)).fetchall()]
        outbox = [dict(r) for r in conn.execute("SELECT * FROM outbox ORDER BY created_at DESC").fetchall()]
        audit_log = [dict(r) for r in conn.execute("SELECT * FROM audit_log ORDER BY created_at DESC").fetchall()]
        return {
            "currentUser": user,
            "users": users,
            "tags": tags,
            "clubs": clubs,
            "routes": routes,
            "events": events,
            "tickets": tickets,
            "deadlines": deadlines,
            "reminders": reminders,
            "communityMembers": members,
            "qaPosts": qa_posts,
            "qaAnswers": qa_answers,
            "notifications": notifications,
            "outbox": outbox,
            "auditLog": audit_log,
            "timetable": [dict(r) for r in conn.execute("SELECT * FROM timetable").fetchall()],
            "facultyCabins": [dict(r) for r in conn.execute("SELECT * FROM faculty_cabins").fetchall()],
            "venueSlots": [dict(r) for r in conn.execute("SELECT * FROM venue_slots").fetchall()]
        }

    if op == "summarize_notice":
        summary = summarize_text(
            p.get("title", ""),
            p.get("description", ""),
            p.get("deadline", ""),
            p.get("venue", ""),
            p.get("department", "All"),
            p.get("target_year", "All"),
            p.get("is_free", True),
            p.get("red_flags", [])
        )
        return {"summary": summary}

    if op == "signup":
        email = p.get("email", "").strip().lower()
        name = p.get("name", "").strip()
        role = p.get("role", "student")
        if role not in ("student", "club_rep", "faculty", "admin"):
            role = "student"
        existing = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        if existing:
            return {"user": parse_user(existing)}
        new_id = "u_" + uuid.uuid4().hex[:8]
        conn.execute(
            "INSERT INTO users VALUES (?,?,?,?,?,?,?,?,?,?)",
            (new_id, name or "Campus User", email, role, p.get("department", "CSE"), p.get("year", "3rd Year"), json.dumps(p.get("interests", ["AI/ML", "Placements"])), 1, "22:00 - 07:00", 0)
        )
        conn.commit()
        return {"user": parse_user(conn.execute("SELECT * FROM users WHERE id=?", (new_id,)).fetchone())}

    if op == "update_profile":
        if not user:
            return {"error": "Unauthorized"}
        conn.execute(
            "UPDATE users SET department=?, year=?, interests=?, whatsapp_opt_in=?, quiet_hours=?, onboarded=1 WHERE id=?",
            (p.get("department", user["department"]), p.get("year", user["year"]), json.dumps(p.get("interests", user["interests"])), 1 if p.get("whatsapp_opt_in", True) else 0, p.get("quiet_hours", user["quiet_hours"]), uid)
        )
        conn.commit()
        return {"ok": True}

    if op == "create_event":
        if not user or user["role"] not in ("club_rep", "faculty", "admin"):
            return {"error": "Forbidden: insufficient role"}
        eid = "e_" + uuid.uuid4().hex[:8]
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        club_id = p.get("club_id") or None
        status = "Pending review"
        if user["role"] == "club_rep":
            status = "Pending faculty review"
        elif user["role"] == "admin":
            status = "Verified"
        hist = [{"actor": user["name"], "action": f"Created ({status})", "time": now_str}]
        conn.execute(
            "INSERT INTO events VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                eid, p["title"], p["description"], p.get("category", "General"),
                p.get("department", "All"), p.get("target_year", "All"),
                p.get("event_date", "2026-11-28 10:00"), p.get("deadline", "2026-11-26 23:59"),
                p.get("venue", "Main Auditorium"), p.get("venue_id", "v_auditorium"),
                p.get("registration_link", "https://example.com/register"),
                p.get("source_doc", ""), p.get("attachment_url", ""),
                status, json.dumps([]), json.dumps(p.get("tags", [])),
                1 if p.get("is_free", True) else 0, club_id, uid, "",
                json.dumps(hist), None, json.dumps([]), 120 if status == "Verified" else 0, now_str
            )
        )
        if club_id:
            club = conn.execute("SELECT * FROM clubs WHERE id=?", (club_id,)).fetchone()
            if club:
                notify_user(conn, club["coordinator_id"], "New club event submitted", f"{user['name']} submitted '{p['title']}' for review.", "warning")
                add_outbox(conn, "Email", "ananya.rao@college.edu", f"[UniSync] Review needed: {p['title']}", f"{user['name']} submitted '{p['title']}' for {club['name']}.")
        elif status == "Pending review":
            notify_user(conn, "u_admin", "New notice in Verification Queue", f"{user['name']} submitted '{p['title']}'.", "warning")
        log_audit(conn, user, "CREATE_EVENT", "event", eid, p["title"], f"Status: {status}")
        conn.commit()
        return {"id": eid, "status": status}

    if op == "edit_resubmit_event":
        if not user or user["role"] not in ("club_rep", "faculty", "admin"):
            return {"error": "Forbidden"}
        ev = conn.execute("SELECT * FROM events WHERE id=?", (p["event_id"],)).fetchone()
        if not ev:
            return {"error": "Not found"}
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        hist = json.loads(ev["history"])
        hist.append({"actor": user["name"], "action": "Edited & resubmitted for review", "time": now_str})
        new_status = "Pending faculty review" if ev["club_id"] else "Pending review"
        conn.execute(
            "UPDATE events SET title=?, description=?, event_date=?, deadline=?, venue=?, registration_link=?, tags=?, status=?, history=? WHERE id=?",
            (p.get("title", ev["title"]), p.get("description", ev["description"]), p.get("event_date", ev["event_date"]), p.get("deadline", ev["deadline"]), p.get("venue", ev["venue"]), p.get("registration_link", ev["registration_link"]), json.dumps(p.get("tags", json.loads(ev["tags"]))), new_status, json.dumps(hist), ev["id"])
        )
        log_audit(conn, user, "RESUBMIT_EVENT", "event", ev["id"], p.get("title", ev["title"]), "Resubmitted after edits")
        conn.commit()
        return {"ok": True}

    if op == "faculty_review_club_event":
        if not user or user["role"] != "faculty":
            return {"error": "Forbidden: Faculty only"}
        ev = conn.execute("SELECT * FROM events WHERE id=?", (p["event_id"],)).fetchone()
        if not ev:
            return {"error": "Not found"}
        club = conn.execute("SELECT * FROM clubs WHERE id=?", (ev["club_id"],)).fetchone()
        decision = p.get("decision") # approve | changes | reject
        comment = p.get("comment", "")
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        hist = json.loads(ev["history"])

        if decision == "approve":
            if club and club["requires_admin_check"]:
                new_status = "Pending admin review"
                hist.append({"actor": user["name"], "action": "Faculty approved -> Routed to Admin", "time": now_str, "comment": comment})
                notify_user(conn, "u_admin", "Club event awaiting admin check", f"'{ev['title']}' approved by faculty.", "info")
            else:
                new_status = "Verified"
                hist.append({"actor": user["name"], "action": "Faculty approved & Published", "time": now_str, "comment": comment})
            notify_user(conn, ev["author_id"], "Club event approved", f"Prof. Ananya Rao approved '{ev['title']}'.", "success")
        elif decision == "changes":
            new_status = "Changes requested"
            hist.append({"actor": user["name"], "action": "Changes requested", "time": now_str, "comment": comment})
            notify_user(conn, ev["author_id"], "Changes requested on event", f"Comment on '{ev['title']}': {comment}", "warning")
        else:
            new_status = "Rejected"
            hist.append({"actor": user["name"], "action": "Rejected by faculty", "time": now_str, "comment": comment})
            notify_user(conn, ev["author_id"], "Club event rejected", f"'{ev['title']}' was rejected: {comment}", "danger")

        conn.execute("UPDATE events SET status=?, reviewer_comment=?, history=? WHERE id=?", (new_status, comment, json.dumps(hist), ev["id"]))
        log_audit(conn, user, f"FACULTY_{decision.upper()}", "event", ev["id"], ev["title"], comment)
        conn.commit()
        return {"status": new_status}

    if op == "admin_verify_event":
        if not user or user["role"] != "admin":
            return {"error": "Forbidden: Admin only"}
        ev = conn.execute("SELECT * FROM events WHERE id=?", (p["event_id"],)).fetchone()
        if not ev:
            return {"error": "Not found"}
        decision = p.get("decision") # verify | reject | send_back
        comment = p.get("comment", "")
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        hist = json.loads(ev["history"])

        if decision == "verify":
            new_status = "Verified"
            hist.append({"actor": user["name"], "action": "Verified & Published", "time": now_str, "comment": comment})
            # Auto-resolve linked tickets!
            linked = conn.execute("SELECT * FROM tickets WHERE event_id=? AND status IN ('Open','Reopened')", (ev["id"],)).fetchall()
            for t in linked:
                msgs = json.loads(t["messages"])
                msgs.append({"sender": user["name"], "role": "admin", "text": f"Verified as genuine. {comment}".strip(), "time": now_str})
                conn.execute("UPDATE tickets SET status='Resolved', messages=?, updated_at=? WHERE id=?", (json.dumps(msgs), now_str, t["id"]))
                notify_user(conn, t["student_id"], f"Ticket {t['id']} Resolved", f"Admin verified '{ev['title']}'. Please confirm in Inbox.", "success")
                add_outbox(conn, "WhatsApp", "+91-98XXX-XX104", f"Ticket {t['id']} Resolved", f"UniSync Update: '{ev['title']}' has been verified by Admin.")
            # Auto-merge duplicate if requested
            if p.get("merge_duplicate_id"):
                conn.execute("UPDATE events SET merged_into=?, status='Merged' WHERE id=?", (ev["id"], p["merge_duplicate_id"]))
                log_audit(conn, user, "MERGE_DUPLICATE", "event", p["merge_duplicate_id"], ev["title"], f"Merged into {ev['id']}")
        elif decision == "send_back":
            new_status = "Changes requested"
            hist.append({"actor": user["name"], "action": "Admin sent back for edits", "time": now_str, "comment": comment})
            notify_user(conn, ev["author_id"], "Admin requested changes", f"'{ev['title']}': {comment}", "warning")
        else:
            new_status = "Rejected"
            hist.append({"actor": user["name"], "action": "Rejected as unverified/fake", "time": now_str, "comment": comment})
            linked = conn.execute("SELECT * FROM tickets WHERE event_id=? AND status IN ('Open','Reopened')", (ev["id"],)).fetchall()
            for t in linked:
                msgs = json.loads(t["messages"])
                msgs.append({"sender": user["name"], "role": "admin", "text": f"Warning: This notice was rejected as unverified/suspicious. {comment}".strip(), "time": now_str})
                conn.execute("UPDATE tickets SET status='Resolved', messages=?, updated_at=? WHERE id=?", (json.dumps(msgs), now_str, t["id"]))
                notify_user(conn, t["student_id"], f"Ticket {t['id']} Resolved (Rejected)", f"'{ev['title']}' was marked fake/rejected by Admin.", "danger")

        conn.execute("UPDATE events SET status=?, reviewer_comment=?, history=?, reached_count=CASE WHEN ?='Verified' THEN 320 ELSE reached_count END WHERE id=?", (new_status, comment, json.dumps(hist), new_status, ev["id"]))
        log_audit(conn, user, f"ADMIN_{decision.upper()}", "event", ev["id"], ev["title"], comment)
        conn.commit()
        return {"status": new_status}

    if op == "acknowledge_event":
        ev = conn.execute("SELECT * FROM events WHERE id=?", (p["event_id"],)).fetchone()
        if not ev:
            return {"error": "Not found"}
        acks = json.loads(ev["acknowledged_by"])
        if uid not in acks:
            acks.append(uid)
            conn.execute("UPDATE events SET acknowledged_by=? WHERE id=?", (json.dumps(acks), ev["id"]))
            conn.commit()
        return {"ok": True}

    if op == "create_ticket":
        ev = conn.execute("SELECT * FROM events WHERE id=?", (p["event_id"],)).fetchone()
        if not ev:
            return {"error": "Event not found"}
        tid = "TKT-" + str(102 + conn.execute("SELECT COUNT(*) FROM tickets").fetchone()[0])
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        q = p.get("question", "Please verify if this notice is genuine.")
        msgs = [{"sender": user["name"], "role": user["role"], "text": q, "time": now_str}]
        conn.execute(
            "INSERT INTO tickets VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (tid, ev["id"], ev["title"], uid, user["name"], "u_admin", "Siddharth Joshi", q, "Open", json.dumps(msgs), now_str, now_str)
        )
        notify_user(conn, "u_admin", f"New Ticket {tid}", f"{user['name']} requested verification for '{ev['title']}'.", "info")
        add_outbox(conn, "Email", "siddharth.joshi@college.edu", f"[UniSync] Ticket {tid}: {ev['title']}", q)
        log_audit(conn, user, "CREATE_TICKET", "ticket", tid, ev["title"], q)
        conn.commit()
        return {"id": tid}

    if op == "ticket_feedback":
        t = conn.execute("SELECT * FROM tickets WHERE id=?", (p["ticket_id"],)).fetchone()
        if not t:
            return {"error": "Not found"}
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        msgs = json.loads(t["messages"])
        action = p.get("action") # close | reopen
        if action == "close":
            new_status = "Closed"
            msgs.append({"sender": user["name"], "role": user["role"], "text": "Confirmed: Yes, resolved.", "time": now_str})
        else:
            new_status = "Reopened"
            note = p.get("note", "Still a problem — please recheck.")
            msgs.append({"sender": user["name"], "role": user["role"], "text": note, "time": now_str})
            notify_user(conn, "u_admin", f"Ticket {t['id']} Reopened", f"{user['name']} reported: {note}", "warning")
        conn.execute("UPDATE tickets SET status=?, messages=?, updated_at=? WHERE id=?", (new_status, json.dumps(msgs), now_str, t["id"]))
        log_audit(conn, user, f"TICKET_{action.upper()}", "ticket", t["id"], t["event_title"], new_status)
        conn.commit()
        return {"status": new_status}

    if op == "add_deadline":
        ev = conn.execute("SELECT * FROM events WHERE id=?", (p["event_id"],)).fetchone()
        if not ev:
            return {"error": "Not found"}
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        dl_id = "dl_" + uuid.uuid4().hex[:8]
        conn.execute(
            "INSERT OR IGNORE INTO deadlines VALUES (?,?,?,?,?,?,?,?,?)",
            (dl_id, uid, ev["id"], ev["title"], ev["deadline"], ev["category"], 0, 1, now_str)
        )
        # Auto-schedule 3d, 1d, 2h reminders
        for label, offset in [("3 days before", -3), ("1 day before", -1), ("2 hours before", 0)]:
            rid = "rem_" + uuid.uuid4().hex[:8]
            conn.execute(
                "INSERT INTO reminders VALUES (?,?,?,?,?,?,?,?,?,?)",
                (rid, uid, ev["id"], ev["title"], label, ev["deadline"], "WhatsApp + Push", "Scheduled", f"Reminder ({label}): {ev['title']} deadline is {ev['deadline']}.", None)
            )
        conn.commit()
        return {"ok": True}

    if op == "toggle_deadline":
        conn.execute("UPDATE deadlines SET completed = 1 - completed WHERE id=? AND user_id=?", (p["deadline_id"], uid))
        conn.commit()
        return {"ok": True}

    if op == "simulate_reminder":
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        rem = conn.execute("SELECT * FROM reminders WHERE id=?", (p["reminder_id"],)).fetchone()
        if rem:
            conn.execute("UPDATE reminders SET status='Sent', sent_at=? WHERE id=?", (now_str, rem["id"]))
            add_outbox(conn, "WhatsApp", "+91-98XXX-XX104", f"Deadline Reminder: {rem['event_title']}", rem["message_preview"])
            notify_user(conn, rem["user_id"], f"Reminder: {rem['event_title']}", rem["message_preview"], "info")
            conn.commit()
        return {"ok": True}

    if op == "join_community":
        cid = p["community_id"]
        club = conn.execute("SELECT * FROM clubs WHERE id=?", (cid,)).fetchone()
        if not club:
            return {"error": "Club not found"}
        status = "joined" if club["join_mode"] == "instant" else "pending"
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        conn.execute(
            "INSERT OR REPLACE INTO community_members VALUES (?,?,?,?,?,?)",
            ("cm_" + uuid.uuid4().hex[:8], cid, uid, user["name"], status, now_str)
        )
        if status == "joined":
            conn.execute("UPDATE clubs SET member_count = member_count + 1 WHERE id=?", (cid,))
        else:
            notify_user(conn, club["rep_id"], "New community join request", f"{user['name']} requested to join {club['name']}.", "info")
        log_audit(conn, user, "JOIN_COMMUNITY", "club", cid, club["name"], f"Status: {status}")
        conn.commit()
        return {"status": status, "whatsapp_link": club["whatsapp_link"] if status == "joined" else None}

    if op == "approve_community_member":
        if not user or user["role"] not in ("club_rep", "faculty", "admin"):
            return {"error": "Forbidden"}
        cm = conn.execute("SELECT * FROM community_members WHERE id=?", (p["member_id"],)).fetchone()
        if cm:
            conn.execute("UPDATE community_members SET status='joined' WHERE id=?", (cm["id"],))
            conn.execute("UPDATE clubs SET member_count = member_count + 1 WHERE id=?", (cm["community_id"],))
            notify_user(conn, cm["user_id"], "Community request approved", "Your request to join was approved. WhatsApp invite link is now unlocked.", "success")
            conn.commit()
        return {"ok": True}

    if op == "create_qa_post":
        pid = "qa_" + uuid.uuid4().hex[:8]
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        conn.execute(
            "INSERT INTO qa_posts VALUES (?,?,?,?,?,?,?,?,?)",
            (pid, p["community_id"], uid, user["name"], user["role"], p["title"], p["body"], 1, now_str)
        )
        conn.commit()
        return {"id": pid}

    if op == "create_qa_answer":
        aid = "ans_" + uuid.uuid4().hex[:8]
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        conn.execute(
            "INSERT INTO qa_answers VALUES (?,?,?,?,?,?,?)",
            (aid, p["post_id"], uid, user["name"], user["role"], p["body"], now_str)
        )
        post = conn.execute("SELECT * FROM qa_posts WHERE id=?", (p["post_id"],)).fetchone()
        if post and post["author_id"] != uid:
            notify_user(conn, post["author_id"], "New Q&A reply", f"{user['name']} answered your question: '{post['title']}'", "info")
        conn.commit()
        return {"id": aid}

    if op == "upvote_qa":
        conn.execute("UPDATE qa_posts SET upvotes = upvotes + 1 WHERE id=?", (p["post_id"],))
        conn.commit()
        return {"ok": True}

    if op == "admin_manage_tag":
        if not user or user["role"] != "admin":
            return {"error": "Forbidden"}
        if p.get("action") == "add":
            tid = "t_" + uuid.uuid4().hex[:6]
            conn.execute("INSERT OR IGNORE INTO tags VALUES (?,?,?,1)", (tid, p["name"].strip(), p.get("color", "indigo")))
        elif p.get("action") == "toggle":
            conn.execute("UPDATE tags SET active = 1 - active WHERE id=?", (p["tag_id"],))
        log_audit(conn, user, "MANAGE_TAG", "tag", p.get("name", p.get("tag_id", "")), p.get("name", "Tag"), p.get("action", ""))
        conn.commit()
        return {"ok": True}

    if op == "admin_update_club":
        if not user or user["role"] != "admin":
            return {"error": "Forbidden"}
        conn.execute(
            "UPDATE clubs SET requires_admin_check=?, join_mode=?, coordinator_id=?, rep_id=? WHERE id=?",
            (1 if p.get("requires_admin_check") else 0, p.get("join_mode", "instant"), p.get("coordinator_id", "u_faculty"), p.get("rep_id", "u_rep"), p["club_id"])
        )
        log_audit(conn, user, "UPDATE_CLUB_SETTINGS", "club", p["club_id"], p["club_id"], f"admin_check={p.get('requires_admin_check')}, join_mode={p.get('join_mode')}")
        conn.commit()
        return {"ok": True}

    if op == "admin_update_route":
        if not user or user["role"] != "admin":
            return {"error": "Forbidden"}
        conn.execute("UPDATE publishing_routes SET reviewer_role=?, auto_notify_whatsapp=? WHERE category=?", (p["reviewer_role"], 1 if p.get("auto_notify_whatsapp") else 0, p["category"]))
        log_audit(conn, user, "UPDATE_ROUTE", "route", p["category"], p["category"], p["reviewer_role"])
        conn.commit()
        return {"ok": True}

    if op == "update_cabin_status":
        if not user or user["role"] not in ("faculty", "admin"):
            return {"error": "Forbidden"}
        conn.execute("UPDATE faculty_cabins SET status=?, note=? WHERE id=?", (p.get("status", "Available"), p.get("note", ""), p["cabin_id"]))
        log_audit(conn, user, "UPDATE_CABIN_STATUS", "cabin", p["cabin_id"], p["cabin_id"], p.get("status", ""))
        conn.commit()
        return {"ok": True}

    if op == "toggle_venue_slot":
        if not user or user["role"] != "admin":
            return {"error": "Forbidden"}
        slot = conn.execute("SELECT * FROM venue_slots WHERE id=?", (p["slot_id"],)).fetchone()
        if slot:
            new_status = "Booked" if slot["status"] == "Available" else "Available"
            booked_by = p.get("booked_by", "Reserved by Events Admin") if new_status == "Booked" else ""
            conn.execute("UPDATE venue_slots SET status=?, booked_by=? WHERE id=?", (new_status, booked_by, slot["id"]))
            log_audit(conn, user, "TOGGLE_VENUE_SLOT", "venue", slot["id"], slot["venue_name"], new_status)
            conn.commit()
        return {"ok": True}

    if op == "mark_notifications_read":
        conn.execute("UPDATE notifications SET read=1 WHERE user_id=?", (uid,))
        conn.commit()
        return {"ok": True}

    return {"error": f"Unknown op: {op}"}

def main():
    conn = get_conn()
    init_schema(conn)
    seed_if_empty(conn)
    # Single-shot mode if arg passed, else stdin/stdout line JSON-RPC
    if len(sys.argv) > 1 and sys.argv[1] == "--init-only":
        print(json.dumps({"ok": True, "db": DB_PATH}))
        return
    while True:
        line = sys.stdin.readline()
        if not line:
            break
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            res = handle_rpc(conn, req)
            sys.stdout.write(json.dumps({"id": req.get("id"), "result": res}) + "\n")
            sys.stdout.flush()
        except Exception as e:
            sys.stdout.write(json.dumps({"id": None, "error": str(e)}) + "\n")
            sys.stdout.flush()

if __name__ == "__main__":
    main()
