import streamlit as st
from supabase import create_client
from datetime import date, timedelta
import pandas as pd

# ------------------ App Setup ------------------
st.set_page_config(page_title="Accountability Tracker (Beta)", page_icon="✅", layout="wide")

# Supabase (anon key OK for this beta; make sure policies are permissive as we set earlier)
sb = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
APP_PASSCODE = st.secrets.get("APP_PASSCODE", "")  # set in .streamlit/secrets.toml

# ------------------ Habits ------------------
HABITS = pd.DataFrame([
    {"key": "productivity",  "name": "Productivity",        "type": "bool", "frequency": "daily"},
    {"key": "fitness",       "name": "Fitness",             "type": "bool", "frequency": "daily"},
    {"key": "faith_bible",   "name": "Bible Reading",       "type": "bool", "frequency": "daily"},
    {"key": "faith_prayer",  "name": "Prayer",              "type": "bool", "frequency": "daily"},
    {"key": "faith_fasting", "name": "Fasting",             "type": "bool", "frequency": "weekly"},
    {"key": "food_healthy",  "name": "Healthy Eating",      "type": "bool", "frequency": "daily"},
    {"key": "water_liters",  "name": "Water (L)",           "type": "num",  "frequency": "daily"},
    {"key": "job_apps",      "name": "Job Applications",    "type": "num",  "frequency": "daily"},
]).set_index("key")

DEFAULT_TARGETS = {"water_liters": 2.0, "job_apps": 10}

# ------------------ DB Helpers ------------------
def create_team(name, passcode):
    data = sb.table("teams_beta").insert({"name": name, "passcode": passcode}).execute().data[0]
    return data["id"]

def get_team(team_id):
    r = sb.table("teams_beta").select("*").eq("id", team_id).execute()
    return r.data[0] if r.data else None

def save_checkin(team_id, user, key, d, vbool=None, vnum=None, note=None):
    sb.table("checkins_beta").upsert({
        "team_id": team_id, "user_name": user, "habit_key": key, "date": str(d),
        "value_bool": vbool, "value_number": vnum, "note": note
    }, on_conflict="team_id,user_name,habit_key,date").execute()

def get_week_checkins(team_id, start, end):
    r = (sb.table("checkins_beta").select("*")
         .eq("team_id", team_id)
         .gte("date", str(start)).lte("date", str(end)).execute())
    return pd.DataFrame(r.data) if r.data else pd.DataFrame()

def get_targets(team_id, user):
    r = sb.table("targets_beta").select("*").eq("team_id", team_id).eq("user_name", user).execute()
    return {row["habit_key"]: float(row["target_number"]) for row in (r.data or [])}

def set_target(team_id, user, key, num):
    sb.table("targets_beta").upsert({
        "team_id": team_id, "user_name": user, "habit_key": key, "target_number": num
    }, on_conflict="team_id,user_name,habit_key").execute()

# ------------------ UI: Gate ------------------
st.title("✅ Accountability Tracker — Beta (no email login)")
with st.expander("How this beta works", expanded=False):
    st.write("""
    • Enter the **shared passcode**, then either **Create** a team (you) or **Join** with the Team ID (partner).  
    • Pick your display name (e.g., "Joshua" / "Partner").  
    • Data is accessible to anyone with the link + passcode + team ID. Keep it private.
    """)

if "ok" not in st.session_state: st.session_state.ok = False
if "team_id" not in st.session_state: st.session_state.team_id = ""
if "user_name" not in st.session_state: st.session_state.user_name = ""

passcode = st.text_input("Beta Passcode", type="password")

colA, colB = st.columns(2)
with colA:
    team_name = st.text_input("Create team (name)")
    if st.button("Create new team"):
        if not APP_PASSCODE or passcode == APP_PASSCODE:
            if team_name.strip():
                st.session_state.team_id = create_team(team_name.strip(), passcode or APP_PASSCODE or "")
                st.success(f"Team created. Share this Team ID with partner:\n{st.session_state.team_id}")
                st.session_state.ok = True
        else:
            st.error("Wrong passcode.")
with colB:
    join_id = st.text_input("Or join existing team (paste Team ID)")
    if st.button("Join team"):
        if not APP_PASSCODE or passcode == APP_PASSCODE:
            t = get_team(join_id.strip())
            if t:
                st.session_state.team_id = t["id"]
                st.session_state.ok = True
                st.success("Joined team.")
            else:
                st.error("Team not found.")
        else:
            st.error("Wrong passcode.")

if not st.session_state.ok or not st.session_state.team_id:
    st.stop()

st.info(f"Team ID: `{st.session_state.team_id}`  (share only with your partner)")
st.session_state.user_name = st.text_input("Your display name (e.g., Joshua / Partner)",
                                           value=st.session_state.user_name or "")
if not st.session_state.user_name.strip():
    st.stop()

# ------------------ Tabs ------------------
tab_today, tab_week, tab_compare, tab_settings = st.tabs(["Today", "Week", "Compare", "Settings"])

# ===== TODAY =====
with tab_today:
    st.subheader("Today")
    today = date.today()

    # Prefill today's entries
    r = (sb.table("checkins_beta").select("*")
         .eq("team_id", st.session_state.team_id)
         .eq("user_name", st.session_state.user_name)
         .eq("date", str(today)).execute())
    pref = {row["habit_key"]: row for row in (r.data or [])}

    c1, c2, c3 = st.columns(3)
    with c1:
        prod = st.checkbox("Productivity", bool(pref.get("productivity", {}).get("value_bool", False)))
        fit  = st.checkbox("Fitness", bool(pref.get("fitness", {}).get("value_bool", False)))
        food = st.checkbox("Healthy Eating", bool(pref.get("food_healthy", {}).get("value_bool", False)))
    with c2:
        bible = st.checkbox("Bible Reading", bool(pref.get("faith_bible", {}).get("value_bool", False)))
        prayer= st.checkbox("Prayer", bool(pref.get("faith_prayer", {}).get("value_bool", False)))
        fast  = st.checkbox("Fasting (weekly)", bool(pref.get("faith_fasting", {}).get("value_bool", False)))
    with c3:
        water = st.number_input("Water (liters)", 0.0, step=0.25,
                                value=float(pref.get("water_liters", {}).get("value_number") or 0.0))
        apps  = st.number_input("Job applications", 0, step=1,
                                value=int(pref.get("job_apps", {}).get("value_number") or 0))
        note  = st.text_input("Optional note")

    if st.button("Save today", type="primary"):
        save_checkin(st.session_state.team_id, st.session_state.user_name, "productivity",  today, vbool=prod,  note=note or None)
        save_checkin(st.session_state.team_id, st.session_state.user_name, "fitness",       today, vbool=fit)
        save_checkin(st.session_state.team_id, st.session_state.user_name, "food_healthy",  today, vbool=food)
        save_checkin(st.session_state.team_id, st.session_state.user_name, "faith_bible",   today, vbool=bible)
        save_checkin(st.session_state.team_id, st.session_state.user_name, "faith_prayer",  today, vbool=prayer)
        save_checkin(st.session_state.team_id, st.session_state.user_name, "faith_fasting", today, vbool=fast)
        save_checkin(st.session_state.team_id, st.session_state.user_name, "water_liters",  today, vnum=water)
        save_checkin(st.session_state.team_id, st.session_state.user_name, "job_apps",      today, vnum=apps)
        st.success("Saved!")

# ===== WEEK =====
with tab_week:
    st.subheader("This week (team)")
    start = date.today() - timedelta(days=date.today().weekday())
    end   = start + timedelta(days=6)
    df = get_week_checkins(st.session_state.team_id, start, end)
    if df.empty:
        st.info("No data yet this week.")
    else:
        st.dataframe(
            df.sort_values(["user_name", "date", "habit_key"]),
            use_container_width=True, hide_index=True
        )

# ===== COMPARE (side-by-side) =====
with tab_compare:
    st.subheader("Compare (side-by-side)")

    start = date.today() - timedelta(days=date.today().weekday())
    end   = start + timedelta(days=6)
    df = get_week_checkins(st.session_state.team_id, start, end)
    if df.empty:
        st.info("No data yet.")
    else:
        users = sorted(df["user_name"].unique())

        def summarize_user(user_df, user_name):
            achieved_slots = 0.0
            total_slots    = 0.0
            per_habit_display = {}
            targets = DEFAULT_TARGETS | get_targets(st.session_state.team_id, user_name)

            for key, h in HABITS.iterrows():
                dsub = user_df[user_df["habit_key"] == key]
                if h["type"] == "bool":
                    if h["frequency"] == "daily":
                        done = int(dsub["value_bool"].fillna(False).sum())
                        per_habit_display[key] = f"{done}/7"
                        total_slots += 7
                        achieved_slots += done
                    else:
                        done = 1 if bool(dsub["value_bool"].fillna(False).any()) else 0
                        per_habit_display[key] = "✅ once" if done else "❌ not yet"
                        total_slots += 1
                        achieved_slots += done
                else:
                    total_val = float(dsub["value_number"].fillna(0).sum())
                    goal      = float(targets.get(key, 0.0)) * 7
                    per_habit_display[key] = f"{total_val:.1f}/{goal:.1f}" if goal > 0 else f"{total_val:.1f}"
                    total_slots += 7
                    achieved_slots += (min(total_val/goal, 1.0) * 7) if goal > 0 else 0.0

            overall_pct = round(100 * achieved_slots / total_slots, 1) if total_slots else 0.0
            return {"per_habit": per_habit_display, "overall_pct": overall_pct}

        # Build summaries
        summaries = {u: summarize_user(df[df["user_name"] == u], u) for u in users}

        # Table: habits as rows, users as columns
        rows = []
        for key, h in HABITS.iterrows():
            row = {"Habit": h["name"]}
            for u in users:
                row[u] = summaries[u]["per_habit"][key] if u in summaries else ""
            rows.append(row)

        overall = {"Habit": "Overall %"}
        for u in users:
            overall[u] = f'{summaries[u]["overall_pct"]}%'
        rows.append(overall)

        compare_table = pd.DataFrame(rows)
        st.dataframe(compare_table, use_container_width=True, hide_index=True)

        # Bar chart of overall completion %
        chart_df = pd.DataFrame({
            "user": users,
            "completion_%": [summaries[u]["overall_pct"] for u in users]
        }).set_index("user")
        st.bar_chart(chart_df)

# ===== SETTINGS =====
with tab_settings:
    st.subheader("Targets")
    t = DEFAULT_TARGETS | get_targets(st.session_state.team_id, st.session_state.user_name)
    water = st.number_input("Water (L/day)", 0.0, step=0.25, value=float(t.get("water_liters", 2.0)))
    apps  = st.number_input("Job applications per day", 0, step=1, value=int(t.get("job_apps", 10)))
    if st.button("Save targets"):
        set_target(st.session_state.team_id, st.session_state.user_name, "water_liters", water)
        set_target(st.session_state.team_id, st.session_state.user_name, "job_apps", apps)
        st.success("Targets saved.")
