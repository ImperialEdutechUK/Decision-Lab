"""H5P activity player.

Honest limitation (documented): Streamlit cannot host the xAPI HTTP endpoint the H5P player
needs, so reliable score/completion tracking requires the FastAPI companion (companion/lti_app.py),
which serves the package and receives xAPI. When COMPANION_URL is configured, the activity is
embedded from the companion and tracking flows into the same database. Without the companion, the
package still plays (preview), but completion is recorded only when the companion relays xAPI.
"""
import streamlit as st
import streamlit.components.v1 as components

from config import config
from services import progress_service as P

H5P_CDN = "https://cdn.jsdelivr.net/npm/h5p-standalone@3.8.0/dist"


def render():
    code = st.session_state["act_code"]
    track = st.session_state["track"]
    from components import styling
    styling.top_bar(f'<b>{st.session_state["learner"].get("display_name") or "Learner"}</b>')
    if st.button("← Back", key="h5p_back"):
        st.session_state["view"] = "activity"
        st.rerun()

    try:
        started = P.h5p_start(st.session_state["learner"]["id"], code, track)
    except ValueError as e:
        st.error("This activity has no published H5P version yet." if str(e) == "no_published_version" else str(e))
        return

    st.markdown("## H5P activity")

    if not config.COMPANION_URL:
        st.warning("H5P playback runs through the companion service. Set COMPANION_URL to the "
                   "running companion (see docs/H5P-AND-LTI.md).")
        return

    # Embed the player from the companion origin, which also receives xAPI for this attempt.
    base = config.COMPANION_URL.rstrip("/")
    content_base = f"{base}/h5p/play/{started['version_id']}"
    token = st.session_state.get("session_token", "")
    html = f"""
    <div id="h5p-mount"></div>
    <p id="h5p-status" style="font:12px Inter,sans-serif;color:#4a5a6a">Loading…</p>
    <link rel="stylesheet" href="{H5P_CDN}/styles/h5p.css">
    <script src="{H5P_CDN}/main.bundle.js"></script>
    <script>
      const opts = {{ h5pJsonPath: "{content_base}", frameJs: "{H5P_CDN}/frame.bundle.js", frameCss: "{H5P_CDN}/styles/h5p.css" }};
      new H5PStandalone.H5P(document.getElementById("h5p-mount"), opts).then(() => {{
        document.getElementById("h5p-status").textContent = "Your attempt is being recorded. Finish the activity to save completion.";
        if (window.H5P && H5P.externalDispatcher) {{
          H5P.externalDispatcher.on("xAPI", async (e) => {{
            try {{
              const st = e && e.data && e.data.statement; if (!st) return;
              const r = await fetch("{base}/h5p/event", {{
                method: "POST", headers: {{ "Content-Type": "application/json" }},
                body: JSON.stringify({{ token: "{token}", attemptId: "{started['attempt_id']}",
                  code: "{code}", level: "{track}", statement: st }})
              }});
              const d = await r.json();
              if (d.completed) document.getElementById("h5p-status").textContent =
                "Completed" + (d.percentage!=null? " · "+d.percentage+"%":"") + ". Saved to your record.";
            }} catch (err) {{}}
          }});
        }}
      }}).catch(() => {{ document.getElementById("h5p-status").textContent = "Could not render this H5P package."; }});
    </script>
    """
    components.html(html, height=560, scrolling=True)
    st.caption("When you finish, return to the activity page to see your saved score.")
