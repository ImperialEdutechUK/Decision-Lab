"""Generate the printable practice record as PDF bytes (reportlab). A formative record, not a
certificate."""
import io

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.pdfgen import canvas

from config import config


def practice_record_pdf(record: dict) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    w, h = A4
    navy = colors.HexColor("#13293d")
    mute = colors.HexColor("#64748b")

    c.setFillColor(navy)
    c.rect(0, h - 70, w, 70, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(40, h - 40, config.APP_NAME)
    c.setFont("Helvetica", 10)
    c.drawString(40, h - 56, "Practice Record")

    y = h - 95
    c.setFillColor(navy)
    c.setFont("Helvetica-Bold", 13)
    c.drawString(40, y, record["learner"]["name"] or "Learner")
    y -= 15
    c.setFillColor(mute)
    c.setFont("Helvetica", 9)
    if record["learner"].get("email"):
        c.drawString(40, y, record["learner"]["email"]); y -= 12
    c.drawString(40, y, f'Generated {record["generated_at"]:%Y-%m-%d %H:%M}')
    y -= 24

    for code in ("FOUNDATION", "PRACTITIONER"):
        t = record["tracks"][code]
        c.setFillColor(navy)
        c.setFont("Helvetica-Bold", 11)
        c.drawString(40, y, t["name"]); y -= 15
        c.setFillColor(colors.black)
        c.setFont("Helvetica", 9)
        avg = t["average_score"] if t["average_score"] is not None else "-"
        c.drawString(50, y, f'Attempted {t["attempted"]} · Completed {t["completed"]} · '
                            f'Score {t["total_practice_score"]}/{t["max_practice_score"]} · '
                            f'Average {avg} · Completion {t["completion_pct"]}%')
        y -= 20

    c.setFillColor(navy)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(40, y, "Recently completed"); y -= 16
    c.setFillColor(colors.black)
    c.setFont("Helvetica", 9)
    done = [r for r in record["recent"] if r.get("last_accessed_at")]
    if not done:
        c.setFillColor(mute); c.drawString(50, y, "No completed activities yet."); y -= 14
    for r in done:
        if y < 70:
            c.showPage(); y = h - 60; c.setFont("Helvetica", 9)
        c.setFillColor(colors.black)
        c.drawString(50, y, f'{r["activity"]} {r["title"]}  ·  {r["track"]}  ·  {r["score"]}  ·  '
                            f'{r["last_accessed_at"]:%Y-%m-%d}')
        y -= 13

    c.setFillColor(mute)
    c.setFont("Helvetica", 7.5)
    c.drawString(40, 40, "An automatically generated record of practice. Not a certificate, qualification, "
                         "assessed portfolio, or exam result.")
    c.showPage()
    c.save()
    return buf.getvalue()
