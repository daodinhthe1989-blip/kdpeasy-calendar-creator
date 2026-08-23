import streamlit as st
import calendar
import fitz
import zipfile
import holidays
from datetime import date
from fpdf import FPDF
from io import BytesIO
from PIL import Image

st.set_page_config(page_title="KDPEasy Calendar Creator", page_icon="📅", layout="centered")

# Password -> expiry date, or None for permanent access (paying customers).
# To add a new trial password: pick a unique string and set its expiry date (issue date + trial length).
PASSWORD_EXPIRY = {
    "KDPCAL2026": None,
    "KDPCALBETA2026": date(2026, 8, 26),  # 3-day trial issued 2026-08-24 (24, 25, 26)
}

MARGIN = 0.4
TITLE_H = 0.55
GAP = 0.15
PHOTO_H_FRACTION = 0.45
PHOTO_W_FRACTION = 0.72
BG_PANEL_OPACITY = 0.30
BG_CHIP_OPACITY = 0.88

PAGE_SIZES = {
    "Letter (8.5 x 11 in)": (8.5, 11.0),
    "Square (8.5 x 8.5 in)": (8.5, 8.5),
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
:root {
    color-scheme: light;
}
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
        if pw in PASSWORD_EXPIRY:
            expiry = PASSWORD_EXPIRY[pw]
            if expiry is None or date.today() <= expiry:
                st.session_state["authed"] = True
                st.rerun()
            else:
                st.error("This trial password has expired. Please reach out to get full access.")
        else:
            st.error("Incorrect password.")
    st.markdown('</div>', unsafe_allow_html=True)
    return False


def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))


def truncate_label(text, max_chars=18):
    if len(text) <= max_chars:
        return text
    cut = text[:max_chars]
    if " " in cut:
        cut = cut.rsplit(" ", 1)[0]
    return cut + "..."


def tint_toward_white(color, amount=0.85):
    r, g, b = color
    return (
        int(r + (255 - r) * amount),
        int(g + (255 - g) * amount),
        int(b + (255 - b) * amount),
    )


def get_photo_box(page_w, page_h):
    content_w = page_w - 2 * MARGIN
    content_h_available = page_h - MARGIN - (MARGIN + TITLE_H + GAP)
    box_h = content_h_available * PHOTO_H_FRACTION
    box_w = content_w * PHOTO_W_FRACTION
    return box_w, box_h


def prepare_photo(uploaded_file, box_w, box_h, fill_mode):
    uploaded_file.seek(0)
    img = Image.open(uploaded_file).convert("RGB")
    target_ratio = box_w / box_h
    img_ratio = img.width / img.height

    if fill_mode:
        if img_ratio > target_ratio:
            new_w = int(img.height * target_ratio)
            left = (img.width - new_w) // 2
            img = img.crop((left, 0, left + new_w, img.height))
        else:
            new_h = int(img.width / target_ratio)
            top = (img.height - new_h) // 2
            img = img.crop((0, top, img.width, top + new_h))
        return img, box_w, box_h
    else:
        if img_ratio > target_ratio:
            draw_w = box_w
            draw_h = box_w / img_ratio
        else:
            draw_h = box_h
            draw_w = box_h * img_ratio
        return img, draw_w, draw_h


def build_calendar_pdf(year, start_monday, page_w, page_h, theme, show_notes,
                        include_cover, cover_title, cover_photo,
                        photos_enabled=False, month_photos=None, photo_fill=False,
                        photo_background_layout=False, show_holidays=False):
    pdf = FPDF(unit="in", format=(page_w, page_h))
    pdf.set_auto_page_break(False)

    primary = theme["primary"]
    weekend_bg = theme["weekend"]
    grid_color = theme["grid"]
    text_color = theme["text"]
    us_holidays = (
        holidays.US(years=year, categories=("public", "unofficial"), observed=False)
        if show_holidays else {}
    )

    firstweekday = 0 if start_monday else 6
    cal = calendar.Calendar(firstweekday=firstweekday)

    if start_monday:
        day_names = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
        weekend_idx = {5, 6}
    else:
        day_names = ["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"]
        weekend_idx = {0, 6}

    title_font_size = 16 if page_w < 7 else 20

    if include_cover:
        pdf.add_page()
        if cover_photo is not None:
            pil_img, draw_w, draw_h = prepare_photo(cover_photo, page_w, page_h, photo_fill)
            offset_x = (page_w - draw_w) / 2
            offset_y = (page_h - draw_h) / 2
            pdf.image(pil_img, x=offset_x, y=offset_y, w=draw_w, h=draw_h)
            if cover_title:
                band_h = 1.1 if page_h >= 8 else 0.85
                pdf.set_fill_color(*primary)
                pdf.rect(0, page_h - band_h, page_w, band_h, "F")
                pdf.set_text_color(255, 255, 255)
                pdf.set_font("Helvetica", "B", 26 if page_w < 7 else 30)
                pdf.set_xy(0.3, page_h - band_h + (band_h - 0.5) / 2)
                pdf.multi_cell(page_w - 0.6, 0.5, cover_title, align="C")
        elif cover_title:
            pdf.set_fill_color(*primary)
            pdf.rect(0, 0, page_w, page_h, "F")
            pdf.set_text_color(255, 255, 255)
            pdf.set_font("Helvetica", "B", 28 if page_w < 7 else 34)
            pdf.set_xy(0.3, page_h / 2 - 0.5)
            pdf.multi_cell(page_w - 0.6, 0.55, cover_title, align="C")

    for month in range(1, 13):
        pdf.add_page()
        bg_layout = photos_enabled and photo_background_layout

        if bg_layout:
            photo_file = month_photos[month - 1] if month_photos else None
            if photo_file is not None:
                pil_img, draw_w, draw_h = prepare_photo(photo_file, page_w, page_h, True)
                pdf.image(pil_img, x=(page_w - draw_w) / 2, y=(page_h - draw_h) / 2, w=draw_w, h=draw_h)

        pdf.set_fill_color(*primary)
        pdf.rect(MARGIN, MARGIN, page_w - 2 * MARGIN, TITLE_H, "F")
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Helvetica", "B", title_font_size)
        pdf.set_xy(MARGIN, MARGIN)
        pdf.cell(page_w - 2 * MARGIN, TITLE_H, f"{calendar.month_name[month]} {year}", align="C")

        content_w = page_w - 2 * MARGIN
        photo_h = 0.0
        if photos_enabled and not bg_layout:
            box_w, box_h = get_photo_box(page_w, page_h)
            photo_h = box_h
            photo_y = MARGIN + TITLE_H + GAP
            box_x = MARGIN + (content_w - box_w) / 2
            pdf.set_draw_color(*grid_color)
            pdf.rect(box_x, photo_y, box_w, box_h)
            photo_file = month_photos[month - 1] if month_photos else None
            if photo_file is not None:
                pil_img, draw_w, draw_h = prepare_photo(photo_file, box_w, box_h, photo_fill)
                offset_x = box_x + (box_w - draw_w) / 2
                offset_y = photo_y + (box_h - draw_h) / 2
                pdf.image(pil_img, x=offset_x, y=offset_y, w=draw_w, h=draw_h)

        grid_top = MARGIN + TITLE_H + GAP + (photo_h + GAP if photos_enabled and not bg_layout else 0)

        if bg_layout:
            panel_h = page_h - grid_top - MARGIN
            with pdf.local_context(fill_opacity=BG_PANEL_OPACITY):
                pdf.set_fill_color(255, 255, 255)
                pdf.rect(MARGIN, grid_top, content_w, panel_h, "F")

        col_w = content_w / 7
        header_h = 0.3

        pdf.set_font("Helvetica", "B", 10)
        for i, name in enumerate(day_names):
            x = MARGIN + i * col_w
            pdf.set_draw_color(*grid_color)
            if bg_layout:
                pdf.rect(x, grid_top, col_w, header_h, "D")
            else:
                fill = weekend_bg if i in weekend_idx else (255, 255, 255)
                pdf.set_fill_color(*fill)
                pdf.rect(x, grid_top, col_w, header_h, "DF")
            pdf.set_text_color(*text_color)
            pdf.set_xy(x, grid_top)
            pdf.cell(col_w, header_h, name, align="C")

        weeks = cal.monthdayscalendar(year, month)
        n_rows = 6
        row_h = (page_h - grid_top - header_h - MARGIN) / n_rows

        pdf.set_font("Helvetica", "", 11)
        for r in range(n_rows):
            y = grid_top + header_h + r * row_h
            week = weeks[r] if r < len(weeks) else [0] * 7
            for i in range(7):
                x = MARGIN + i * col_w
                pdf.set_draw_color(*grid_color)
                if bg_layout:
                    pdf.rect(x, y, col_w, row_h, "D")
                else:
                    fill = weekend_bg if i in weekend_idx else (255, 255, 255)
                    pdf.set_fill_color(*fill)
                    pdf.rect(x, y, col_w, row_h, "DF")
                day = week[i]
                if day != 0:
                    if bg_layout:
                        with pdf.local_context(fill_opacity=BG_CHIP_OPACITY):
                            pdf.set_fill_color(255, 255, 255)
                            pdf.rect(x + 0.04, y + 0.04, 0.36, 0.2, "F")
                    pdf.set_text_color(*text_color)
                    pdf.set_xy(x + 0.06, y + 0.05)
                    pdf.cell(col_w - 0.12, 0.2, str(day), align="L")
                    if show_holidays and not bg_layout:
                        hol_name = us_holidays.get(date(year, month, day))
                        if hol_name:
                            label = truncate_label(hol_name.split("; ")[0])
                            pdf.set_text_color(*primary)
                            pdf.set_font("Helvetica", "", 6.5)
                            pdf.set_xy(x + 0.05, y + 0.22)
                            pdf.multi_cell(col_w - 0.1, 0.09, label, align="L")
                            pdf.set_font("Helvetica", "", 11)
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
        orientation = st.radio("Orientation", ["Portrait", "Landscape"], index=0, horizontal=True)
    with col2:
        theme_mode = st.radio("Color theme", ["Preset", "Custom color"], index=0, horizontal=True)
        if theme_mode == "Preset":
            theme_name = st.selectbox("Choose a preset", list(THEMES.keys()))
            theme = THEMES[theme_name]
        else:
            custom_hex = st.color_picker("Pick any color", "#4f46e5")
            primary_rgb = hex_to_rgb(custom_hex)
            theme = {
                "primary": primary_rgb,
                "weekend": tint_toward_white(primary_rgb, 0.85),
                "grid": (209, 213, 219),
                "text": (31, 41, 55),
            }
        show_notes = st.checkbox("Add a small note-line in each day", value=False)
        show_holidays = st.checkbox("Add major US holidays", value=False)
        include_cover = st.checkbox("Include a cover page", value=True)
        export_png = st.checkbox("Also export as PNG images (zipped, 300 DPI)", value=False)

    page_w, page_h = PAGE_SIZES[page_size_label]
    if orientation == "Landscape":
        page_w, page_h = page_h, page_w

    cover_title = ""
    cover_photo = None
    if include_cover:
        cover_title = st.text_input("Cover page title", value=f"{year} CALENDAR")
        cover_photo = st.file_uploader("Cover photo (optional, fills the whole cover page)", type=["png", "jpg", "jpeg"], key="cover_photo")

    photos_enabled = st.checkbox("Add your own photo to each month", value=False)
    month_photos = [None] * 12
    photo_fill = False
    if photos_enabled or (include_cover and cover_photo is not None):
        fit_choice = st.radio(
            "Photo style (applies to the cover photo and every month photo)",
            ["Fit — show the full photo, may add white bars (recommended for portrait photos)",
             "Fill — crop to fill the box, no white bars (best for landscape/square photos)"],
            index=0,
        )
        photo_fill = fit_choice.startswith("Fill")
        st.caption("Tip: if a photo looks too cropped in the preview below, switch back to Fit.")

    if include_cover and cover_photo is not None:
        cover_prev_img, cover_draw_w, cover_draw_h = prepare_photo(cover_photo, page_w, page_h, photo_fill)
        st.image(cover_prev_img, caption="Cover photo preview", width=220)

    bg_layout = False
    if photos_enabled:
        layout_choice = st.radio(
            "Monthly photo layout",
            ["Box — photo sits above the calendar grid",
             "Full background — photo fills the whole page behind the grid"],
            index=0,
        )
        bg_layout = layout_choice.startswith("Full")
        if bg_layout:
            st.caption("Full background always crops the photo to fill the page completely (no white bars). The photo stays clearly visible behind a light haze, with a small white tag behind each date number so it's always easy to read.")

        if bg_layout:
            preview_box_w, preview_box_h, preview_fill = page_w, page_h, True
        else:
            preview_box_w, preview_box_h = get_photo_box(page_w, page_h)
            preview_fill = photo_fill

        with st.expander("Upload a photo for each month (any month can be left empty)"):
            photo_cols = st.columns(3)
            for m in range(12):
                with photo_cols[m % 3]:
                    f = st.file_uploader(calendar.month_name[m + 1], type=["png", "jpg", "jpeg"], key=f"photo_{m}")
                    month_photos[m] = f
                    if f is not None:
                        prev_img, _, _ = prepare_photo(f, preview_box_w, preview_box_h, preview_fill)
                        st.image(prev_img, caption="Preview", use_container_width=True)

    if st.button("Generate Calendar PDF"):
        pdf_buf = build_calendar_pdf(
            int(year), start_monday, page_w, page_h, theme, show_notes,
            include_cover, cover_title, cover_photo,
            photos_enabled=photos_enabled, month_photos=month_photos, photo_fill=photo_fill,
            photo_background_layout=bg_layout, show_holidays=show_holidays,
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
