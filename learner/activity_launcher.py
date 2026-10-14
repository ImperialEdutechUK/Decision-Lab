"""Launch view for admin-managed activities: H5P links, external quizzes, embeds, videos,
documents and other links.

Tracking is honest: we persist what we genuinely observe (ACCESS and LAUNCH, with timestamps and
counts). A score or completion is stored only when a trusted integration (xAPI/LTI-AGS) supplies
it. A plain link or iframe never records a score.
"""
import streamlit as st
import streamlit.components.v1 as components

from components import styling
from components.viewers import embed_file
from services import tracking_service as T
from services import url_safety
from services.admin_service import get_activity_file


def _access_once(learner_id, activity):
    key = f"_accessed_{activity['id']}"
    if not st.session_state.get(key):
        T.touch_access(learner_id, activity_id=activity["id"], code=activity["code"], track=activity["track"])
        st.session_state[key] = True


def _launch_once(learner_id, activity, code, track, detail=None):
    key = f"_launched_{activity['id']}"
    if not st.session_state.get(key):
        T.record_launch(learner_id, activity_id=activity["id"], code=code, track=track, detail=detail)
        st.session_state[key] = True


def _tracking_note():
    st.caption("We record that you opened and launched this activity. Your score and completion are "
               "not received from the external provider unless your administrator has configured a "
               "supported integration (for example xAPI or LTI 1.3 grade services).")


def render():
    code = st.session_state["act_code"]
    track = st.session_state["track"]
    learner = st.session_state["learner"]
    # Give the activity the full width of the page (no cramped column, no horizontal scroll).
    st.markdown("<style>.block-container{max-width:1240px !important;}</style>", unsafe_allow_html=True)
    styling.top_bar(f'<b>{learner.get("display_name") or "Learner"}</b>')
    if st.button("← Back", key="launch_back"):
        st.session_state["view"] = "activity"
        st.rerun()

    from services import progress_service as P
    d = P.activity_detail(learner["id"], code, track)
    if not d:
        st.error("Activity not available.")
        return
    a = d["activity"]
    atype = a["activity_type"]

    st.markdown(f"## {a['title']}")
    _access_once(learner["id"], a)

    # DOCUMENT: show the uploaded file inline (no download required) where the format allows.
    if atype == "DOCUMENT" and not (a.get("url") or a.get("embed_url")):
        gf = get_activity_file(a["id"])
        if gf:
            name, data, mime = gf
            _launch_once(learner["id"], a, code, track, detail={"file": name})
            embed_file(name, data, mime, height=840, download_label="Download document")
        else:
            st.info("No file has been added for this activity yet.")
        _tracking_note()
        _show_progress(d.get("external"))
        return

    target = a.get("embed_url") or a.get("url")
    if not target:
        st.info("This activity has no link configured yet.")
        return

    if a.get("open_mode") == "EMBED":
        if not url_safety.is_allowed_embed(target):
            st.warning("This activity cannot be embedded here (its host is not approved). Open it in "
                       "a new tab instead.")
            st.link_button("Open in a new tab →", target, type="primary")
            _launch_once(learner["id"], a, code, track)
        else:
            _launch_once(learner["id"], a, code, track)
            safe = target.replace('"', "%22")
            components.html(
                f'<iframe src="{safe}" style="width:100%;height:600px;border:1px solid #d9e0e6;'
                f'border-radius:10px" allow="autoplay; fullscreen" referrerpolicy="no-referrer" '
                f'sandbox="allow-scripts allow-same-origin allow-forms allow-popups"></iframe>',
                height=620, scrolling=True,
            )
    else:
        st.link_button("Launch in a new tab →", target, type="primary")
        _launch_once(learner["id"], a, code, track)

    _tracking_note()
    _show_progress(d.get("external"))


def _show_progress(ext):
    if not ext:
        return
    st.markdown("### Your record")
    score_txt = "Not available"
    if ext.get("score_verified") and ext.get("best_score") is not None:
        mx = ext.get("best_max_score")
        score_txt = f'{ext["best_score"]}{("/" + str(mx)) if mx else ""} (verified)'
    first = ext.get("first_access_at")
    last = ext.get("last_access_at")
    rows = [
        ("Status", ext.get("completion_status") or "NOT_STARTED"),
        ("Launches", ext.get("launch_count") or 0),
        ("First opened", f"{first:%Y-%m-%d %H:%M}" if first else "-"),
        ("Last opened", f"{last:%Y-%m-%d %H:%M}" if last else "-"),
        ("Score", score_txt),
    ]
    html = "".join(f"<tr><td>{k}</td><td>{v}</td></tr>" for k, v in rows)
    st.markdown(f'<table class="simple"><tbody>{html}</tbody></table>', unsafe_allow_html=True)
