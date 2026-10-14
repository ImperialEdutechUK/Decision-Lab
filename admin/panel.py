"""Administrator interface. Reached via "Admin sign in". Admin identity lives in
st.session_state['admin'] (set only after a verified password login); learners never get it, and
every admin action is authorised server-side in the service layer."""
import streamlit as st

from services import admin_service as A
from services import course_service as C
from auth.tokens import issue_admin_session
from content.registry import TRACK_CODES, TRACKS, track_name
from components import styling
from components.viewers import embed_file
from database.models import ACTIVITY_TYPES, ACTIVITY_STATUSES, OPEN_MODES


def is_admin():
    return bool(st.session_state.get("admin"))


# ── auth ────────────────────────────────────────────────────────────────────
def render_login():
    styling.top_bar()
    if st.button("← Back", key="adm_back"):
        st.session_state["view"] = "dashboard"
        st.rerun()
    st.markdown("## Admin sign in")
    show = st.checkbox("Show password", key="adm_show")
    with st.form("admin_login"):
        email = st.text_input("Email")
        pw = st.text_input("Password", type=("default" if show else "password"))
        ok = st.form_submit_button("Sign in", type="primary")
    if ok:
        admin = A.authenticate_admin(email, pw)
        if not admin:
            st.error("Email or password is incorrect.")
        else:
            st.session_state["admin"] = admin
            st.session_state["admin_token"] = issue_admin_session(admin["id"])
            st.session_state["view"] = "admin"
            st.rerun()


def render_panel():
    admin = st.session_state["admin"]
    styling.top_bar(f'<b>{admin["display_name"] or admin["email"]}</b>')
    c1, c2 = st.columns([0.8, 0.2])
    if c1.button("← Learner view", key="adm_learner"):
        st.session_state["view"] = "dashboard"
        st.rerun()
    if c2.button("Sign out", key="adm_out"):
        st.session_state.pop("admin", None)
        st.session_state.pop("admin_token", None)
        st.session_state["view"] = "dashboard"
        st.rerun()

    tabs = st.tabs(["Overview", "Courses & guides", "Activities", "Learners", "Reports"])
    with tabs[0]:
        _overview()
    with tabs[1]:
        _courses()
    with tabs[2]:
        _activities()
    with tabs[3]:
        _learners()
    with tabs[4]:
        _results()


# ── overview ──────────────────────────────────────────────────────────────────
def _overview():
    o = A.overview()
    cols = st.columns(3)
    for col, (lbl, val) in zip(cols, [
        ("Learners", o["learners"]), ("Activities", o["activities"]),
        ("Completions", o["completions"]),
    ]):
        col.markdown(f'<div class="kpi"><div class="l">{lbl}</div><div class="v">{val}</div></div>',
                     unsafe_allow_html=True)
    if o["recent"]:
        st.markdown("### Recent activity")
        rows = "".join(
            f'<tr><td>{r["learner"]}</td><td>{track_name(r["track"])}</td><td>{r["activity"]}</td>'
            f'<td>{r["score"]}</td><td>{r["status"]}</td><td>{r["last_accessed_at"]:%Y-%m-%d %H:%M}</td></tr>'
            for r in o["recent"])
        st.markdown(f'<table class="simple"><thead><tr><th>Learner</th><th>Course</th><th>Activity</th>'
                    f'<th>Score</th><th>Status</th><th>Last accessed</th></tr></thead>'
                    f'<tbody>{rows}</tbody></table>', unsafe_allow_html=True)


# ── courses & guides ─────────────────────────────────────────────────────────
def _courses():
    C.ensure_courses()
    code = st.selectbox("Course", TRACK_CODES, format_func=track_name, key="course_pick")
    course = C.get_course(code)

    with st.expander("Course information", expanded=False):
        with st.form(f"course_info_{code}"):
            info = st.text_area("Information shown to learners", value=course.get("info") or "", height=100)
            if st.form_submit_button("Save", type="primary"):
                C.update_course_info(code, info)
                st.success("Saved.")
                st.rerun()

    st.markdown("### Course guide")
    guide = C.get_guide(code, with_file=True)
    status = guide["status"] if guide else "none"
    st.caption(f"Status: {status}")

    with st.form(f"guide_text_{code}"):
        title = st.text_input("Guide title", value=(guide or {}).get("title") or "")
        body = st.text_area("Guide text (Markdown: headings, lists, links)",
                            value=(guide or {}).get("body") or "", height=220)
        if st.form_submit_button("Save guide text", type="primary"):
            C.save_guide(code, title=title, body=body)
            st.success("Saved.")
            st.rerun()

    st.markdown("#### Guide file")
    if guide and guide.get("has_file"):
        st.caption(f'Current file: {guide.get("file_name")}')
        d1, d2 = st.columns(2)
        with d1.popover("Preview"):
            embed_file(guide.get("file_name") or "guide", guide.get("file_bytes"),
                       guide.get("file_mime") or "application/octet-stream", height=460)
        if d2.button("Remove file", key=f"guide_rm_{code}"):
            C.remove_guide_file(code)
            st.rerun()
    up = st.file_uploader("Upload or replace guide file (PDF, DOCX, ...)",
                          type=["pdf", "docx", "doc", "pptx", "txt", "html"], key=f"guide_up_{code}")
    if up is not None and st.button("Save file", key=f"guide_savefile_{code}"):
        try:
            C.set_guide_file(code, up.name, up.getvalue(), up.type or "application/octet-stream")
            st.success("File saved.")
            st.rerun()
        except ValueError as ex:
            st.error(str(ex))

    b1, b2, b3 = st.columns(3)
    if b1.button("Publish guide", key=f"guide_pub_{code}", type="primary"):
        try:
            C.set_guide_status(code, "PUBLISHED")
            st.success("Published.")
            st.rerun()
        except ValueError as ex:
            st.error(str(ex))
    if b2.button("Unpublish", key=f"guide_unp_{code}"):
        C.set_guide_status(code, "DRAFT")
        st.rerun()
    if b3.button("Delete guide", key=f"guide_del_{code}"):
        C.delete_guide(code)
        st.rerun()


# ── activities ────────────────────────────────────────────────────────────────
_TYPE_HELP = {
    "H5P": "Upload an .h5p package (played in-app via the companion runtime).",
    "H5P_LINK": "A published H5P link or embed (e.g. H5P.com).",
    "EXTERNAL_QUIZ": "A quiz or assessment link on another platform.",
    "EMBED": "An embedded activity from an approved provider (iframe).",
    "VIDEO": "A video link or embed.",
    "DOCUMENT": "An uploaded document shown in-app where the format allows.",
    "LINK": "Any other approved external learning resource.",
}


def _activity_fields(prefix, atype, e=None):
    """Render create/edit fields for the given type. Returns a data dict (plus file uploads)."""
    e = e or {}
    c1, c2 = st.columns(2)
    title = c1.text_input("Title", value=e.get("title", ""), key=f"{prefix}_title")
    track = c2.selectbox("Course", TRACK_CODES, format_func=track_name,
                         index=(TRACK_CODES.index(e["track"]) if e.get("track") in TRACK_CODES else 0),
                         key=f"{prefix}_track")
    description = st.text_area("Short description", value=e.get("description") or "", height=70,
                              key=f"{prefix}_desc")

    url = embed_url = None
    open_mode = "NEW_TAB"
    doc_file = h5p_file = None

    if atype in ("H5P_LINK", "EXTERNAL_QUIZ", "VIDEO", "LINK", "EMBED"):
        if atype == "EMBED":
            open_mode = "EMBED"
            embed_url = st.text_input("Embed URL (https, approved domains)",
                                      value=e.get("embed_url") or "", key=f"{prefix}_embed")
        else:
            open_mode = st.selectbox("Open mode", OPEN_MODES,
                                     index=(OPEN_MODES.index(e.get("open_mode")) if e.get("open_mode") in OPEN_MODES else 0),
                                     key=f"{prefix}_mode")
            url = st.text_input("Launch URL (https)", value=e.get("url") or "", key=f"{prefix}_url")
            embed_url = st.text_input("Embed URL (https, approved domains) - for Open mode EMBED",
                                      value=e.get("embed_url") or "", key=f"{prefix}_embed")
    elif atype == "DOCUMENT":
        doc_file = st.file_uploader("Activity document (PDF, DOCX, PPTX, ...)",
                                    key=f"{prefix}_docfile")
        if e.get("has_file"):
            st.caption(f'Current file: {e.get("file_name")}')
    elif atype == "H5P":
        h5p_file = st.file_uploader("H5P package (.h5p)", type=["h5p"], key=f"{prefix}_h5pfile")

    st.markdown("**Guidelines for learners** (optional)")
    instructions = st.text_area("Guidelines text (Markdown)", value=e.get("instructions") or "",
                               height=90, key=f"{prefix}_instr")
    guideline_file = st.file_uploader("Optional guidelines file", key=f"{prefix}_gfile")

    c3, c4, c5 = st.columns(3)
    est = c3.text_input("Estimated minutes", value=e.get("est_minutes") or "", key=f"{prefix}_est")
    pass_mark = c4.number_input("Pass mark (%)", min_value=0, max_value=100,
                                value=int(e["pass_mark"]) if e.get("pass_mark") is not None else 0,
                                key=f"{prefix}_pass")
    status = c5.selectbox("Status", ACTIVITY_STATUSES,
                          index=(ACTIVITY_STATUSES.index(e.get("status")) if e.get("status") in ACTIVITY_STATUSES else 0),
                          key=f"{prefix}_status")

    return {
        "title": title, "track": track, "activity_type": atype, "open_mode": open_mode,
        "url": (url or "").strip() or None, "embed_url": (embed_url or "").strip() or None,
        "description": description, "instructions": instructions,
        "est_minutes": est.strip() or None,
        "pass_mark": int(pass_mark) if pass_mark else None,
        "status": status,
        "_doc_file": doc_file, "_h5p_file": h5p_file, "_guideline_file": guideline_file,
    }


def _attach_files(activity_id, data, *, is_h5p=False):
    """Persist any uploaded files from an activity form. Returns a list of notes."""
    notes = []
    gf = data.get("_guideline_file")
    if gf is not None:
        try:
            A.save_guideline_file(activity_id, gf.name, gf.getvalue(), gf.type or "application/octet-stream")
        except ValueError as ex:
            notes.append(f"Guidelines file: {ex}")
    if not is_h5p:
        df = data.get("_doc_file")
        if df is not None:
            try:
                A.save_activity_file(activity_id, df.name, df.getvalue(), df.type or "application/octet-stream")
            except ValueError as ex:
                notes.append(f"Document: {ex}")
    return notes


def _activities():
    st.markdown("### Add activity")
    atype = st.selectbox("Type", list(ACTIVITY_TYPES), key="create_type",
                         format_func=lambda t: t.replace("_", " ").title())
    st.caption(_TYPE_HELP.get(atype, ""))
    with st.form("create_form", clear_on_submit=False):
        data = _activity_fields("create", atype)
        submitted = st.form_submit_button("Create", type="primary")
    if submitted:
        h5p_file = data.get("_h5p_file")
        try:
            if atype == "H5P" and not h5p_file:
                raise ValueError("Upload an .h5p package for an H5P activity.")
            # For H5P, create as DRAFT first; publish only after the package is attached.
            create_status = data["status"]
            if atype == "H5P":
                data["status"] = "DRAFT"
            res = A.create_activity(st.session_state["admin"]["id"], data)
            notes = _attach_files(res["id"], data, is_h5p=(atype == "H5P"))
            if atype == "H5P" and h5p_file:
                up = A.h5p_upload(st.session_state["admin"]["id"], res["code"], res["track"],
                                  h5p_file.name, h5p_file.getvalue(), data["title"])
                if up["validated_ok"]:
                    A.h5p_validate(up["id"])
                    if create_status == "PUBLISHED":
                        A.h5p_publish(up["id"])
                else:
                    notes.append(f"H5P validation: {up['validation']}")
            for n in notes:
                st.warning(n)
            st.success(f'Created "{data["title"]}" ({res["code"]}, {track_name(res["track"])}).')
            st.rerun()
        except ValueError as ex:
            st.error(str(ex))

    st.markdown("### Activities")
    acts = A.list_activities_admin()
    if not acts:
        st.info("No activities yet.")
        return
    rows = "".join(
        f'<tr><td>{a["code"]}</td><td>{track_name(a["track"])}</td><td>{a["title"]}</td>'
        f'<td>{(a.get("activity_type") or a["kind"]).replace("_"," ").title()}</td>'
        f'<td>{a.get("status") or "-"}</td><td>{len(a["versions"])}</td></tr>' for a in acts)
    st.markdown(f'<table class="simple"><thead><tr><th>Code</th><th>Course</th><th>Title</th><th>Type</th>'
                f'<th>Status</th><th>H5P versions</th></tr></thead><tbody>{rows}</tbody></table>',
                unsafe_allow_html=True)

    st.markdown("### Manage activity")
    labels = {f'{a["code"]} · {track_name(a["track"])} · {a["title"]} [{a.get("status")}]': a["id"] for a in acts}
    pick = st.selectbox("Select", list(labels.keys()), key="manage_pick")
    aid = labels[pick]
    full = A.get_activity_admin(aid)
    atype = full.get("activity_type") or full.get("kind")

    b = st.columns(6)
    if b[0].button("Publish", key="mg_pub"):
        A.set_activity_status(aid, "PUBLISHED"); st.rerun()
    if b[1].button("Unpublish", key="mg_unp"):
        A.set_activity_status(aid, "UNPUBLISHED"); st.rerun()
    if b[2].button("Draft", key="mg_draft"):
        A.set_activity_status(aid, "DRAFT"); st.rerun()
    if b[3].button("Move up", key="mg_up"):
        A.move_activity(aid, "up"); st.rerun()
    if b[4].button("Move down", key="mg_down"):
        A.move_activity(aid, "down"); st.rerun()
    if b[5].button("Delete", key="mg_del"):
        st.session_state["confirm_delete"] = aid
    if st.session_state.get("confirm_delete") == aid:
        st.warning("Delete this activity? Learner records, if any, are preserved by archiving instead.")
        d1, d2 = st.columns(2)
        if d1.button("Confirm delete", key="mg_del_yes", type="primary"):
            res = A.delete_activity(aid)
            st.session_state.pop("confirm_delete", None)
            st.info(res.get("message") or ("Deleted." if res.get("deleted") else "Archived."))
            st.rerun()
        if d2.button("Cancel", key="mg_del_no"):
            st.session_state.pop("confirm_delete", None)
            st.rerun()

    with st.expander("Preview (admin)"):
        _preview_activity(A.get_activity_admin(aid))

    with st.expander("Edit"):
        with st.form(f"edit_form_{aid}"):
            data = _activity_fields(f"edit_{aid}", atype, e=full)
            saved = st.form_submit_button("Save", type="primary")
        if saved:
            try:
                A.update_activity(aid, data)
                for n in _attach_files(aid, data, is_h5p=(atype == "H5P")):
                    st.warning(n)
                st.success("Saved.")
                st.rerun()
            except ValueError as ex:
                st.error(str(ex))
        if full.get("has_guideline_file"):
            st.caption(f'Guidelines file: {full.get("guideline_file_name")}')
            if st.button("Remove guidelines file", key=f"rmg_{aid}"):
                A.clear_guideline_file(aid); st.rerun()
        if full.get("has_file"):
            st.caption(f'Document file: {full.get("file_name")}')
            if st.button("Remove document file", key=f"rmd_{aid}"):
                A.clear_activity_file(aid); st.rerun()

    if atype == "H5P":
        _h5p_versions(aid)


def _preview_activity(a):
    st.markdown(f"**{a['code']} - {a['title']}**")
    if a.get("description"):
        st.write(a["description"])
    if a.get("instructions"):
        st.markdown("**Guidelines**")
        st.markdown(a["instructions"])
    atype = a.get("activity_type")
    if atype == "DOCUMENT" and a.get("has_file"):
        gf = A.get_activity_file(a["id"])
        if gf:
            embed_file(gf[0], gf[1], gf[2], height=460)
        return
    target = a.get("embed_url") or a.get("url")
    if target:
        from services import url_safety
        if a.get("open_mode") == "EMBED" and url_safety.is_allowed_embed(target):
            import streamlit.components.v1 as components
            safe = target.replace('"', "%22")
            components.html(
                f'<iframe src="{safe}" style="width:100%;height:420px;border:1px solid #d9e0e6;'
                f'border-radius:10px" sandbox="allow-scripts allow-same-origin allow-forms allow-popups">'
                f'</iframe>', height=440, scrolling=True)
        else:
            st.link_button("Open target in a new tab →", target)
    elif atype == "H5P":
        st.caption("H5P package preview requires the companion runtime (COMPANION_URL).")
    else:
        st.info("Nothing to preview yet.")


def _h5p_versions(activity_id):
    st.markdown("#### H5P package versions")
    acts = {a["id"]: a for a in A.list_activities_admin()}
    a = acts.get(activity_id)
    if not a:
        return
    up = st.file_uploader("Upload a new version (.h5p)", type=["h5p"], key=f"h5pv_{activity_id}")
    if up is not None and st.button("Upload version", key=f"h5pv_btn_{activity_id}"):
        try:
            r = A.h5p_upload(st.session_state["admin"]["id"], a["code"], a["track"], up.name, up.getvalue())
            A.h5p_validate(r["id"])
            st.success(f'Uploaded v{r["version"]}. Publish it below when ready.')
            st.rerun()
        except ValueError as ex:
            st.error(str(ex))
    for v in a["versions"]:
        cols = st.columns([0.1, 0.2, 0.4, 0.3])
        cols[0].markdown(f'v{v["version"]}')
        cols[1].markdown(f'<span class="badge">{v["status"]}</span>', unsafe_allow_html=True)
        cols[2].markdown(f'{v["file_name"]} ({round(v["file_size"]/1024)} KB)')
        with cols[3]:
            bb = st.columns(2)
            if v["status"] != "PUBLISHED":
                if bb[0].button("Publish", key=f"pub_{v['id']}"):
                    try:
                        A.h5p_publish(v["id"]); st.rerun()
                    except ValueError as ex:
                        st.error(str(ex))
            else:
                if bb[0].button("Unpublish", key=f"unp_{v['id']}"):
                    A.h5p_unpublish(v["id"]); st.rerun()


# ── learners ──────────────────────────────────────────────────────────────────
def _learners():
    q = st.text_input("Search by email, name or LMS id", key="learner_search")
    rows = A.search_learners(q) if q else A.list_learners()
    st.markdown(f"### Learners ({len(rows)})")
    for l in rows:
        c1, c2 = st.columns([0.85, 0.15])
        c1.markdown(f'**{l["display_name"] or "-"}** · {l["email"] or "-"} · {l["attempts"]} attempts · '
                    f'{l["total_points"]} pts · {l["completed_missions"]} completed')
        if c2.button("View", key=f"lv_{l['id']}"):
            st.session_state["admin_learner"] = l["id"]
            st.rerun()
    lid = st.session_state.get("admin_learner")
    if lid:
        d = A.learner_detail(lid)
        if d:
            st.markdown("---")
            st.markdown(f'### {d["learner"]["display_name"] or d["learner"]["email"]}')
            st.caption(f'LMS id: {d["learner"]["external_learner_id"]} · issuer: {d["learner"]["issuer"]}')
            cols = st.columns(2)
            for col, code in zip(cols, TRACK_CODES):
                bt = d["by_track"][code]
                col.markdown(f'<div class="kpi"><div class="l">{TRACKS[code]["name"]}</div>'
                             f'<div class="v" style="font-size:18px">{bt["completed"]}/{bt["attempted"]} · '
                             f'{bt["points"]} pts</div></div>', unsafe_allow_html=True)
            if st.button("Close", key="lclose"):
                st.session_state.pop("admin_learner", None)
                st.rerun()


# ── reports ───────────────────────────────────────────────────────────────────
_REPORT_STATUSES = ["(any)", "NOT_STARTED", "ACCESSED", "IN_PROGRESS", "COMPLETED"]


def _results():
    st.markdown("### Reports")
    acts = A.list_activities_admin()
    codes = ["(all)"] + sorted({a["code"] for a in acts})
    f1, f2, f3 = st.columns(3)
    code = f1.selectbox("Activity", codes, key="rep_code")
    track = f2.selectbox("Course", ["(all)"] + list(TRACK_CODES), key="rep_track")
    status = f3.selectbox("Status", _REPORT_STATUSES, key="rep_status")
    learner_q = st.text_input("Learner (email/name/id)", key="rep_learner")

    filters = dict(
        activity_code=None if code == "(all)" else code,
        track=None if track == "(all)" else track,
        status=None if status == "(any)" else status,
        learner_q=learner_q or None,
    )
    rows = A.report_rows(**filters)
    st.markdown(f"**{len(rows)} record(s)**")
    st.download_button("Export CSV", data=A.tracking_csv(**filters),
                       file_name="decision-lab-tracking.csv", mime="text/csv", key="rep_csv")

    def _score(r):
        if r["score"] is None:
            return "-"
        base = f'{r["score"]}/{r["max_score"]}' if r["max_score"] is not None else str(r["score"])
        return base + ("" if r["score_verified"] else " (unverified)")

    html = "".join(
        f'<tr><td>{r["learner"]}</td><td>{r["code"]}</td><td>{r["type"]}</td>'
        f'<td>{track_name(r["track"])}</td><td>{r["status"]}</td><td>{_score(r)}</td>'
        f'<td>{r["last_accessed_at"]:%Y-%m-%d %H:%M}</td></tr>'
        for r in rows[:500]) or '<tr><td colspan="7">No records.</td></tr>'
    st.markdown(f'<table class="simple"><thead><tr><th>Learner</th><th>Activity</th><th>Type</th>'
                f'<th>Course</th><th>Status</th><th>Score</th><th>Last accessed</th></tr></thead>'
                f'<tbody>{html}</tbody></table>', unsafe_allow_html=True)

    lim = A.integration_limitations()["limited_activities"]
    if lim:
        with st.expander("Tracking coverage"):
            st.caption("For these types we record launch/access only. A score or completion is stored "
                       "just for those with a confirmed integration (xAPI / LTI-AGS).")
            h = "".join(f'<tr><td>{r["code"]}</td><td>{r["type"]}</td>'
                        f'<td>{"Yes" if r["has_verified_scores"] else "No"}</td></tr>' for r in lim)
            st.markdown(f'<table class="simple"><thead><tr><th>Activity</th><th>Type</th>'
                        f'<th>Verified scores?</th></tr></thead><tbody>{h}</tbody></table>',
                        unsafe_allow_html=True)
