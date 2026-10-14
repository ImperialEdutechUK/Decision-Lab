"""Learner practice record with PDF download."""
import streamlit as st

from services import progress_service as P
from services.pdf_service import practice_record_pdf
from components import styling
from content.registry import track_name


def render():
    styling.top_bar(f'<b>{st.session_state["learner"].get("display_name") or "Learner"}</b>')
    if st.button("← Dashboard", key="pr_back"):
        st.session_state["view"] = "dashboard"
        st.rerun()

    r = P.practice_record(st.session_state["learner"]["id"])
    st.markdown(f"# {r['title']}")
    st.caption(f'{r["learner"]["name"]} · {r["learner"]["email"] or ""} · {r["generated_at"]:%Y-%m-%d %H:%M}')

    c1, c2 = st.columns(2)
    for col, code in zip((c1, c2), ("FOUNDATION", "PRACTITIONER")):
        t = r["tracks"][code]
        avg = t["average_score"] if t["average_score"] is not None else "-"
        col.markdown(
            f'<div class="kpi" style="text-align:left;padding:16px"><div class="l">{t["name"]}</div>'
            f'<div style="margin-top:8px;font-size:13px">Completed <b>{t["completed"]}</b>/{t["attempted"] or 0} · '
            f'Score <b>{t["total_practice_score"]}/{t["max_practice_score"]}</b> · Avg <b>{avg}</b> · '
            f'{t["completion_pct"]}%</div></div>', unsafe_allow_html=True)

    st.markdown("### Recently completed")
    rows = "".join(
        f'<tr><td><b>{x["activity"]}</b> {x["title"]}</td><td>{track_name(x["track"])}</td>'
        f'<td>{x["score"]}</td><td>{x["last_accessed_at"]:%Y-%m-%d}</td></tr>'
        for x in r["recent"] if x["last_accessed_at"]) or '<tr><td colspan="4">No completed activities yet.</td></tr>'
    st.markdown(f'<table class="simple"><thead><tr><th>Activity</th><th>Course</th><th>Score</th>'
                f'<th>Completed</th></tr></thead><tbody>{rows}</tbody></table>', unsafe_allow_html=True)

    pdf = practice_record_pdf(r)
    st.download_button("Download practice record (PDF)", data=pdf,
                       file_name="practice-record.pdf", mime="application/pdf", type="primary")
