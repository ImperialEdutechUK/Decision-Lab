"""Visual identity for Decision Lab (palette, typography, cards, panels), injected into Streamlit."""
import streamlit as st

from config import config

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,600&family=Inter:wght@400;500;600;700&family=IBM+Plex+Mono:wght@500;600&display=swap');
:root{
  --bg:#f4f5f7; --surface:#ffffff; --surface-2:#eef1f4; --ink:#13293d; --ink-2:#4a5a6a;
  --line:#d9e0e6; --navy:#13293d; --teal:#0f8a84; --teal-ink:#0b6b66;
  --amber:#c98a1a; --rose:#c1375b; --green:#2f8f5b;
  --good:#2f8f5b; --warn:#c98a1a; --bad:#c1375b; --radius:12px; --radius-s:8px;
}
html, body, [class*="css"] { font-family:'Inter',system-ui,-apple-system,'Segoe UI',Roboto,sans-serif; }
.stApp { background:var(--bg); color:var(--ink); }
#MainMenu, header[data-testid="stHeader"], footer { visibility:hidden; height:0; }
.block-container { padding-top:1.1rem; padding-bottom:3rem; max-width:960px; }
h1,h2,h3,h4 { font-family:'Fraunces','Georgia',serif; color:var(--ink); }

/* brand top bar */
.kdl-top{display:flex;align-items:center;gap:12px;padding:12px 16px;background:var(--surface);
  border:1px solid var(--line);border-radius:var(--radius);margin-bottom:14px}
.kdl-mark{width:34px;height:34px;border-radius:9px;flex:none;background:linear-gradient(145deg,var(--navy),var(--teal-ink));
  display:grid;place-items:center;color:#fff;font-family:'Fraunces',serif;font-weight:600}
.kdl-top b{font-family:'Fraunces',serif;font-size:16px;display:block;line-height:1.1}
.kdl-top span{font-size:11px;color:var(--ink-2)}
.kdl-who{margin-left:auto;font-size:12.5px;color:var(--ink-2);text-align:right}
.kdl-who b{color:var(--ink);font-family:'Inter',sans-serif}

.fic{font-size:11px;font-weight:600;letter-spacing:.02em;color:var(--amber);
  background:color-mix(in srgb,var(--amber) 9%,transparent);border:1px solid color-mix(in srgb,var(--amber) 35%,var(--line));
  border-radius:8px;padding:8px 12px;margin:0 0 16px;text-align:center}

.eyebrow{font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:var(--teal-ink);font-weight:700;margin-bottom:6px}

/* document / evidence cards */
.doc{border:1px solid var(--line);border-radius:var(--radius-s);background:var(--surface);overflow:hidden;margin:10px 0}
.doc-h{padding:9px 13px;background:var(--surface-2);border-bottom:1px solid var(--line);font-size:11px;font-weight:700;
  letter-spacing:.03em;text-transform:uppercase;color:var(--ink-2)}
.doc-b{padding:13px 15px;font-size:13.8px;line-height:1.55;color:var(--ink)}
.doc-b .row{margin-bottom:3px} .doc-b .subject{font-weight:600;margin:6px 0 9px}

/* panels */
.panel{border-radius:var(--radius);padding:15px 17px;margin:14px 0;border:1px solid var(--line);background:var(--surface)}
.panel.good{border-left:4px solid var(--good)} .panel.warn{border-left:4px solid var(--warn)}
.panel.bad{border-left:4px solid var(--bad)} .panel.method{border-left:4px solid var(--navy);background:var(--surface-2)}
.panel h4{font-family:'Inter',sans-serif;font-weight:700;font-size:12px;letter-spacing:.05em;text-transform:uppercase;
  color:var(--ink-2);margin:0 0 8px}
.panel.good h4{color:var(--good)} .panel.warn h4{color:var(--warn)} .panel.bad h4{color:var(--bad)}
.panel p{font-size:14px;line-height:1.55;margin:0 0 8px}
.scoreflag{display:inline-block;font-family:'IBM Plex Mono',monospace;font-weight:700;font-size:13px;padding:4px 10px;
  border-radius:7px;margin-bottom:10px}
.scoreflag.s2{color:var(--good);background:color-mix(in srgb,var(--good) 13%,transparent)}
.scoreflag.s1{color:var(--warn);background:color-mix(in srgb,var(--warn) 13%,transparent)}
.scoreflag.s0{color:var(--bad);background:color-mix(in srgb,var(--bad) 13%,transparent)}

/* track + activity cards */
.tcard{background:var(--surface);border:1px solid var(--line);border-radius:var(--radius);padding:18px;margin-bottom:8px}
.tcard .md{display:inline-block;font-size:11px;font-weight:700;letter-spacing:.04em;text-transform:uppercase;
  padding:3px 9px;border-radius:99px;color:var(--teal-ink);background:color-mix(in srgb,var(--teal) 12%,transparent)}
.tcard.p .md{color:var(--rose);background:color-mix(in srgb,var(--rose) 12%,transparent)}
.tcard .tt{font-family:'Fraunces',serif;font-size:20px;margin:8px 0 6px}
.tcard .meta{font-size:13px;color:var(--ink-2)}
.bar{height:8px;border-radius:99px;background:var(--surface-2);overflow:hidden;margin:8px 0}
.bar i{display:block;height:100%;background:var(--teal)}
.tcard.p .bar i{background:var(--rose)}

.kpi{background:var(--surface);border:1px solid var(--line);border-radius:var(--radius-s);padding:12px 14px;text-align:center}
.kpi .l{font-size:10.5px;text-transform:uppercase;letter-spacing:.03em;color:var(--ink-2);font-weight:700}
.kpi .v{font-family:'Fraunces',serif;font-size:24px;margin-top:3px}

.arow{display:flex;align-items:center;gap:11px;background:var(--surface);border:1px solid var(--line);
  border-radius:var(--radius-s);padding:11px 13px;margin-bottom:2px}
.arow .code{font-family:'IBM Plex Mono',monospace;font-size:12px;font-weight:700;color:var(--ink-2)}
.arow .t{flex:1} .arow .sc{font-family:'IBM Plex Mono',monospace;font-weight:700}
.stico{width:20px;height:20px;border-radius:50%;display:inline-grid;place-items:center;font-size:11px;font-weight:700;color:#fff}
.stico.done{background:var(--good)} .stico.prog{background:var(--amber)} .stico.open{background:var(--line);color:var(--ink-2)}
.badge{font-size:10.5px;font-weight:700;padding:3px 8px;border-radius:99px;border:1px solid var(--line);color:var(--ink-2)}

.steps{display:flex;gap:6px;flex-wrap:wrap;margin:4px 0 14px}
.stp{font-size:11px;color:var(--ink-2);background:var(--surface-2);border:1px solid var(--line);border-radius:99px;padding:4px 10px}
.stp.cur{background:var(--navy);color:#fff;border-color:var(--navy)}
.stp.ok{color:var(--good);border-color:var(--good)}

.levelchip{display:inline-block;font-size:11px;font-weight:700;letter-spacing:.03em;padding:3px 10px;border-radius:99px}
.lv-f{color:var(--teal-ink);background:color-mix(in srgb,var(--teal) 12%,transparent)}
.lv-p{color:var(--rose);background:color-mix(in srgb,var(--rose) 12%,transparent)}

.echo{border:1px dashed color-mix(in srgb,var(--teal) 45%,var(--line));border-radius:var(--radius-s);
  background:color-mix(in srgb,var(--teal) 7%,transparent);padding:11px 13px;margin:6px 0 14px;font-size:13px}

/* native Streamlit button → brand button */
.stButton > button{border-radius:9px;border:1px solid var(--line);background:var(--surface);color:var(--ink);
  font-weight:600;padding:9px 16px}
.stButton > button:hover{border-color:var(--teal);background:var(--surface-2);color:var(--ink)}
.stButton > button[kind="primary"]{background:var(--teal);border-color:var(--teal);color:#fff}
.stButton > button[kind="primary"]:hover{background:var(--teal-ink);border-color:var(--teal-ink);color:#fff}

table.simple{width:100%;border-collapse:collapse;font-size:13px}
table.simple th,table.simple td{text-align:left;padding:8px 10px;border-bottom:1px solid var(--line)}
table.simple th{font-size:11px;text-transform:uppercase;letter-spacing:.03em;color:var(--ink-2)}
.disclaim{font-size:11.5px;color:var(--ink-2);border-top:1px solid var(--line);padding-top:11px;margin-top:14px}
</style>
"""


def inject():
    st.markdown(CSS, unsafe_allow_html=True)


def top_bar(who_html=""):
    name = config.APP_NAME
    initial = (name.strip()[:1] or "D").upper()
    st.markdown(
        f"""<div class="kdl-top"><div class="kdl-mark">{initial}</div>
        <div><b>{name}</b></div>
        <div class="kdl-who">{who_html}</div></div>""",
        unsafe_allow_html=True,
    )
