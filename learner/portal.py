"""Learner portal: dashboard, per-course activity list (guide shown first), and activity detail."""
import streamlit as st

from config import config
from services import progress_service as P
from services import course_service as C
from content.registry import track_name
from components import styling
from components.viewers import embed_file


def _who_html():
    l = st.session_state["learner"]
    return f'<b>{l.get("display_name") or "Learner"}</b><br>{l.get("email") or ""}'


def render_dashboard():
    styling.top_bar(_who_html())
    st.markdown(f"# {config.APP_NAME}")

    tp = P.track_progress(st.session_state["learner"]["id"])
    F, Pr = tp["FOUNDATION"], tp["PRACTITIONER"]

    k = st.columns(4)
    kpis = [
        ("Completed", F["completed"] + Pr["completed"]),
        ("Attempted", F["attempted"] + Pr["attempted"]),
        ("Foundation", f'{F["completed"]}/{F["activities_available"]}'),
        ("Practitioner", f'{Pr["completed"]}/{Pr["activities_available"]}'),
    ]
    for col, (lbl, val) in zip(k, kpis):
        col.markdown(f'<div class="kpi"><div class="l">{lbl}</div><div class="v">{val}</div></div>',
                     unsafe_allow_html=True)

    try:
        from auth.email_identity import is_unverified_identity
        if is_unverified_identity(st.session_state["learner"]):
            st.caption("Signed in with a self-declared email (unverified). Your progress is saved to "
                       "this email; it is not a verified identity.")
    except Exception:
        pass

    st.write("")
    c1, c2 = st.columns(2)
    _track_card(c1, "FOUNDATION", F, "f")
    _track_card(c2, "PRACTITIONER", Pr, "p")

    recent = P.recently_opened(st.session_state["learner"]["id"], limit=8)
    if recent:
        st.markdown("### Recent activity")
        rows = ""
        for r in recent:
            when = f'{r["last_accessed_at"]:%Y-%m-%d %H:%M}' if r.get("last_accessed_at") else "-"
            if r.get("score") is not None and r.get("score_verified"):
                sc = f'{r["score"]}/{r["max_score"]}' if r.get("max_score") is not None else str(r["score"])
            else:
                sc = "-"
            statusword = {"COMPLETED": "Completed", "IN_PROGRESS": "In progress",
                          "ACCESSED": "Opened"}.get(r.get("status"), r.get("status") or "-")
            rows += (f'<tr><td><b>{r["code"]}</b> {r["title"]}</td>'
                     f'<td>{track_name(r["track"])}</td>'
                     f'<td>{statusword}</td><td>{sc}</td><td>{when}</td></tr>')
        st.markdown(f'<table class="simple"><thead><tr><th>Activity</th><th>Course</th>'
                    f'<th>Status</th><th>Score</th><th>Opened</th></tr></thead>'
                    f'<tbody>{rows}</tbody></table>', unsafe_allow_html=True)


def _track_card(col, code, t, cls):
    last = (f'Last: {t["last_activity"]["code"]} {t["last_activity"]["title"]}'
            if t["last_activity"] else "Not started")
    with col:
        st.markdown(
            f'<div class="tcard {cls}"><div class="tt">{t["name"]}</div>'
            f'<div class="bar"><i style="width:{t["completion_pct"]}%"></i></div>'
            f'<div class="meta"><b>{t["completed"]}</b> of {t["activities_available"]} activities · '
            f'{t["completion_pct"]}%</div>'
            f'<div class="meta" style="opacity:.8">{last}</div></div>',
            unsafe_allow_html=True,
        )
        if st.button("Open", type="primary", key=f"open_{code}"):
            st.session_state.update(view="track", track=code)
            st.rerun()


def render_track(track):
    styling.top_bar(_who_html())
    if st.button("← Dashboard", key="t_back"):
        st.session_state["view"] = "dashboard"
        st.rerun()
    st.markdown(f"# {track_name(track)}")

    course = C.get_course(track)
    if course and course.get("info"):
        st.write(course["info"])

    _render_course_guide(track)

    rows = P.activities_with_status(st.session_state["learner"]["id"])[track]
    st.markdown("### Activities")
    if not rows:
        st.info("No activities available yet.")
        return

    for a in rows:
        ico = {"COMPLETED": '<span class="stico done">✓</span>',
               "IN_PROGRESS": '<span class="stico prog">•</span>'}.get(a["status"], '<span class="stico open"></span>')
        sc = ""
        if a["status"] == "COMPLETED" and a.get("score") is not None and a.get("score_verified"):
            sc = f'<span class="sc">{a["score"]}/{a["max_score"]}</span>' if a.get("max_score") is not None \
                 else f'<span class="sc">{a["score"]}</span>'
        _type_labels = {"H5P": "H5P", "H5P_LINK": "H5P", "EXTERNAL_QUIZ": "Quiz",
                        "EMBED": "Embed", "VIDEO": "Video", "DOCUMENT": "Document", "LINK": "Link"}
        tl = _type_labels.get(a.get("activity_type"))
        badge = f'<span class="badge">{tl}</span>' if tl else ""
        statusword = {"COMPLETED": "Completed", "IN_PROGRESS": "In progress",
                      "ACCESSED": "Opened"}.get(a["status"], "Not started")
        row, btn = st.columns([0.82, 0.18])
        with row:
            st.markdown(
                f'<div class="arow">{ico}<span class="code">{a["code"]}</span>'
                f'<span class="t"><b>{a["title"]}</b><br>'
                f'<span style="font-size:12px;color:var(--ink-2)">{statusword}</span></span>'
                f'{badge} {sc}</div>', unsafe_allow_html=True)
        with btn:
            if st.button("Open", key=f"act_{track}_{a['code']}"):
                st.session_state.update(view="activity", act_code=a["code"], track=track)
                st.rerun()


def _render_course_guide(track):
    guide = C.get_published_guide(track, with_file=True)
    if not guide:
        return
    with st.expander("Course guide", expanded=True):
        if guide.get("title"):
            st.markdown(f"#### {guide['title']}")
        if guide.get("body"):
            st.markdown(guide["body"])
        if guide.get("has_file") and guide.get("file_bytes"):
            st.markdown("**Guide document**")
            embed_file(guide.get("file_name") or "guide", guide["file_bytes"],
                       guide.get("file_mime") or "application/octet-stream",
                       download_label="Download guide")


def render_activity():
    code = st.session_state["act_code"]
    track = st.session_state["track"]
    styling.top_bar(_who_html())
    if st.button("← Back", key="a_back"):
        st.session_state["view"] = "track"
        st.rerun()

    d = P.activity_detail(st.session_state["learner"]["id"], code, track)
    if not d:
        st.error("Activity not available.")
        return
    a = d["activity"]

    lvlcls = "lv-f" if track == "FOUNDATION" else "lv-p"
    st.markdown(f'<span class="levelchip {lvlcls}">{track_name(track)}</span>', unsafe_allow_html=True)
    st.markdown(f"# {a['title']}")
    if a.get("description"):
        st.markdown(f'<p class="doc-b">{a["description"]}</p>', unsafe_allow_html=True)

    meta = []
    if a.get("est_minutes"):
        meta.append(f"Time: {a['est_minutes']} min")
    if a.get("pass_mark") is not None:
        meta.append(f"Pass mark: {a['pass_mark']}%")
    if a.get("due_date"):
        meta.append(f"Due: {a['due_date']:%Y-%m-%d}")
    if meta:
        st.caption(" · ".join(meta))

    # Guidelines (shown before the learner starts) - only when present.
    if a.get("instructions") or a.get("has_guideline_file"):
        with st.container():
            st.markdown('<div class="panel method"><h4>Guidelines</h4></div>', unsafe_allow_html=True)
            if a.get("instructions"):
                st.markdown(a["instructions"])
            if a.get("has_guideline_file"):
                from services.admin_service import get_guideline_file
                gf = get_guideline_file(a["id"])
                if gf:
                    name, data, mime = gf
                    embed_file(name, data, mime, height=420, download_label="Download guidelines file")

    if st.button("Open activity →", type="primary", key="open_activity"):
        st.session_state["view"] = "h5p" if a["activity_type"] == "H5P" else "launch"
        st.rerun()
