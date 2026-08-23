import streamlit as st
import calendar
import fitz
import zipfile
from fpdf import FPDF
from io import BytesIO

st.set_page_config(page_title="KDPEasy Calendar Creator", page_icon="📅", layout="centered")

PASSWORD = "KDPCAL2026"

PAGE_SIZES = {
    "Letter (8.5 x 11 in)": (8.5, 11.0),
    "8 x 10 in": (8.0, 10.0),
    "6 x 9 in": (6.0, 9.0),
    "A4": (8.27, 11.69),
    "A5": (5.83, 8.27),
}

THEMES = {
    "Indigo Classic": {"primary": (79, 70, 229), "weekend": (238, 242, 255), "grid": (209, 213, 219), "text": (31, 41, 55)},
    "Emerald Fresh":  {"primary": (16, 185, 129), "weekend": (209, 250, 229), "grid": (209, 213, 219), "text": (31, 41, 55)},
    "Sunset Warm":    {"primary": (234, 88, 12),  "weekend": (255, 237, 213), "grid": (209, 213, 219), "text": (31, 41, 55)},
    "Mono Minimal":   {"primary": (31, 41, 55),   "weekend": (243, 244, 246), "grid": (209, 213, 219), "text": (31, 41, 55)},
}

CUSTOM_CSS = """
<style>
.stApp {
    background: linear-gradient(135deg, #eef2ff 0%, #ffffff 60%);
}
.kdp-card {
    background: white;
    border-radius: 16px;
    padding: 2rem 2rem 1.5rem;
    box-shadow: 0 4px 24px rgba(79, 70, 229, 0.08);
    margin-bottom: 1.5rem;
}
h1, h2, h3 { color: #4f46e5; }
.stButton>button, .stDownloadButton>button {
    background-color: #10b981;
    color: white;
    border-radius: 10px;
    border: none;
    padding: 0.6rem 1.4rem;
    font-weight: 600;
}
.stButton>button:hover, .stDownloadButton>button:hover {
    background-color: #059669;
    color: white;
}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


def check_password() -> bool:
    if st.session_state.get("authed"):
        return True
    st.markdown('<div class="kdp-card">', unsafe_allow_html=True)
    st.title("📅 KDPEasy Calendar Creator")
    pw = st.text_input("Enter access password", type="password")
    if st.button("Unlock"):
        if pw == PASSWORD:
            st.session_state["authed"] = True
            st.rerun()
        else:
            st.error("Incorrect password.")
    st.markdown('</div>', unsafe_allow_html=True)
    return False


def build_calendar_pdf(year, start_monday, page_w, page_h, theme, show_notes, cover_title):
    pdf = FPDF(unit="in", format=(page_w, page_h))
    pdf.set_auto_page_break(False)
    margin = 0.4

    primary = theme["primary"]
    weekend_bg = theme["weekend"]
    grid_color = theme["grid"]
    text_color = theme["text"]

    firstweekday = 0 if start_monday else 6
    cal = calendar.Calendar(firstweekday=firstweekday)

    if start_monday:
        day_names = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
        weekend_idx = {5, 6}
    else:
        day_names = ["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"]
        weekend_idx = {0, 6}

    title_font_size = 16 if page_w < 7 else 20

    if cover_title:
        pdf.add_page()
        pdf.set_fill_color(*primary)
        pdf.rect(0, 0, page_w, page_h, "F")
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Helvetica", "B", 28 if page_w < 7 else 34)
        pdf.set_xy(0.3, page_h / 2 - 0.5)
        pdf.multi_cell(page_w - 0.6, 0.55, cover_title, align="C")

    for month in range(1, 13):
        pdf.add_page()

        pdf.set_fill_color(*primary)
        pdf.rect(margin, margin, page_w - 2 * margin, 0.55, "F")
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Helvetica", "B", title_font_size)
        pdf.set_xy(margin, margin)
        pdf.cell(page_w - 2 * margin, 0.55, f"{calendar.month_name[month]} {year}", align="C")

        grid_top = margin + 0.55 + 0.15
        grid_width = page_w - 2 * margin
        col_w = grid_width / 7
        header_h = 0.3

        pdf.set_font("Helvetica", "B", 10)
        for i, name in enumerate(day_names):
            x = margin + i * col_w
            fill = weekend_bg if i in weekend_idx else (255, 255, 255)
            pdf.set_fill_color(*fill)
            pdf.set_draw_color(*grid_color)
            pdf.rect(x, grid_top, col_w, header_h, "DF")
            pdf.set_text_color(*text_color)
            pdf.set_xy(x, grid_top)
            pdf.cell(col_w, header_h, name, align="C")

        weeks = cal.monthdayscalendar(year, month)
        n_rows = 6
        row_h = (page_h - grid_top - header_h - margin) / n_rows

        pdf.set_font("Helvetica", "", 11)
        for r in range(n_rows):
            y = grid_top + header_h + r * row_h
            week = weeks[r] if r < len(weeks) else [0] * 7
            for i in range(7):
                x = margin + i * col_w
                fill = weekend_bg if i in weekend_idx else (255, 255, 255)
                pdf.set_fill_color(*fill)
                pdf.set_draw_color(*grid_color)
                pdf.rect(x, y, col_w, row_h, "DF")
                day = week[i]
                if day != 0:
                    pdf.set_text_color(*text_color)
                    pdf.set_xy(x + 0.06, y + 0.05)
                    pdf.cell(col_w - 0.12, 0.2, str(day), align="L")
                    if show_notes:
                        pdf.set_draw_color(*grid_color)
                        pdf.line(x + 0.1, y + row_h - 0.15, x + col_w - 0.1, y + row_h - 0.15)

    pdf_bytes = pdf.output()
    return BytesIO(bytes(pdf_bytes))


if check_password():
    st.markdown('<div class="kdp-card">', unsafe_allow_html=True)
    st.title("📅 KDPEasy Calendar Creator")
    st.caption("Create a print-ready 12-month calendar PDF for KDP in seconds.")

    col1, col2 = st.columns(2)
    with col1:
        year = st.number_input("Year", min_value=2020, max_value=2100, value=2027, step=1)
        start_monday = st.radio("Week starts on", ["Sunday", "Monday"], index=0) == "Monday"
        page_size_label = st.selectbox("Page size", list(PAGE_SIZES.keys()))
    with col2:
        theme_name = st.selectbox("Color theme", list(THEMES.keys()))
        show_notes = st.checkbox("Add a small note-line in each day", value=False)
        include_cover = st.checkbox("Include a cover page", value=True)
        export_png = st.checkbox("Also export as PNG images (zipped, 300 DPI)", value=False)

    cover_title = ""
    if include_cover:
        cover_title = st.text_input("Cover page title", value=f"{year} CALENDAR")

    if st.button("Generate Calendar PDF"):
        page_w, page_h = PAGE_SIZES[page_size_label]
        theme = THEMES[theme_name]
        pdf_buf = build_calendar_pdf(
            int(year), start_monday, page_w, page_h, theme, show_notes,
            cover_title if include_cover else ""
        )
        pdf_bytes = pdf_buf.getvalue()
        st.success("Your calendar is ready! Here's a preview before you download:")

        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        preview_count = min(2, doc.page_count)
        captions = ["Cover page", calendar.month_name[1]] if include_cover else [calendar.month_name[1], calendar.month_name[2]]
        preview_cols = st.columns(preview_count)
        for i in range(preview_count):
            pix = doc[i].get_pixmap(dpi=110)
            preview_cols[i].image(pix.tobytes("png"), caption=captions[i], use_container_width=True)

        st.download_button(
            "⬇️ Download Calendar PDF",
            data=pdf_bytes,
            file_name=f"KDPEasy_Calendar_{int(year)}.pdf",
            mime="application/pdf",
        )

        if export_png:
            zip_buf = BytesIO()
            with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
                for i in range(doc.page_count):
                    pix = doc[i].get_pixmap(dpi=300)
                    if include_cover and i == 0:
                        fname = "00_Cover.png"
                    else:
                        month_num = (i - 1 if include_cover else i) + 1
                        fname = f"{month_num:02d}_{calendar.month_name[month_num]}.png"
                    zf.writestr(fname, pix.tobytes("png"))
            zip_buf.seek(0)
            st.download_button(
                "⬇️ Download PNG Images (ZIP, 300 DPI)",
                data=zip_buf,
                file_name=f"KDPEasy_Calendar_{int(year)}_PNG.zip",
                mime="application/zip",
            )

        doc.close()
    st.markdown('</div>', unsafe_allow_html=True)
