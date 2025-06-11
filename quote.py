from flask import request, send_file, jsonify
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import os, uuid
from utils import draw_text_with_shadow, generate_spoofed_filename, postprocess_image

UPLOAD_DIR = "/tmp"
FONT_PATH = "Anton-Regular.ttf"
LOGO_PATH = "hood_logo.png"
IMAGE_SIZE = (2160, 2700)
FONT_SCALE = 0.063
MARGIN = 120
MAX_LINE_WIDTH_RATIO = 0.85
MAX_TOTAL_TEXT_HEIGHT_RATIO = 0.3
MAX_LINE_COUNT = 3

def register(app):
    @app.route("/generate-quote", methods=["POST"])
    def generate_quote():
        if 'file' not in request.files or 'headline' not in request.form:
            return jsonify({"error": "Missing file or headline"}), 400

        img_file = request.files['file']
        headline = request.form['headline'].strip()

        try:
            uid = str(uuid.uuid4())
            img_path = os.path.join(UPLOAD_DIR, f"{uid}.jpg")
            img_file.save(img_path)

            base = Image.open(img_path).convert("RGBA").resize(IMAGE_SIZE)
            overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
            draw = ImageDraw.Draw(overlay)

            # Prepare font sizes
            font_size = int(IMAGE_SIZE[1] * FONT_SCALE)
            quote_font_size = int(font_size * 2.1)
            normal_font = ImageFont.truetype(FONT_PATH, font_size)
            quote_font = ImageFont.truetype(FONT_PATH, quote_font_size)

            max_width = IMAGE_SIZE[0] * MAX_LINE_WIDTH_RATIO

            # Split headline into words (preserving punctuation)
            words = headline.upper().split()
            lines = []
            current_line = []
            current_width = 0
            space_width = draw.textlength(" ", font=normal_font)

            def get_word_width(word):
                font = quote_font if any(q in word for q in ['“', '”']) else normal_font
                return draw.textlength(word, font=font)

            for word in words:
                word_width = get_word_width(word)
                projected_width = current_width + word_width + (space_width if current_line else 0)

                if projected_width > max_width and current_line:
                    lines.append(current_line)
                    current_line = []
                    current_width = 0
                if current_line:
                    current_width += space_width
                current_line.append(word)
                current_width += word_width

            if current_line:
                lines.append(current_line)

            # Check if height fits
            while True:
                total_height = len(lines) * (font_size + 15)
                if total_height <= IMAGE_SIZE[1] * MAX_TOTAL_TEXT_HEIGHT_RATIO and len(lines) <= MAX_LINE_COUNT:
                    break
                font_size -= 2
                quote_font_size = int(font_size * 2.1)
                normal_font = ImageFont.truetype(FONT_PATH, font_size)
                quote_font = ImageFont.truetype(FONT_PATH, quote_font_size)
                space_width = draw.textlength(" ", font=normal_font)
                current_width = 0
                lines = []
                current_line = []

                for word in words:
                    word_width = get_word_width(word)
                    projected_width = current_width + word_width + (space_width if current_line else 0)
                    if projected_width > max_width and current_line:
                        lines.append(current_line)
                        current_line = []
                        current_width = 0
                    if current_line:
                        current_width += space_width
                    current_line.append(word)
                    current_width += word_width

                if current_line:
                    lines.append(current_line)

            # Draw shadow gradient
            shadow_height = IMAGE_SIZE[1] * 2 // 3
            for i in range(shadow_height):
                alpha = min(255, int(255 * (i / shadow_height) * 1.5))
                draw.line(
                    [(0, IMAGE_SIZE[1] - shadow_height + i), (IMAGE_SIZE[0], IMAGE_SIZE[1] - shadow_height + i)],
                    fill=(0, 0, 0, alpha)
                )

            # Draw text centered
            start_y = IMAGE_SIZE[1] - (len(lines) * (font_size + 15)) - 160
            y = start_y
            for line in lines:
                total_width = sum(draw.textlength(w, font=quote_font if any(q in w for q in ['“', '”']) else normal_font) for w in line)
                total_width += space_width * (len(line) - 1)
                x = (IMAGE_SIZE[0] - total_width) // 2

                for word in line:
                    font = quote_font if any(q in word for q in ['“', '”']) else normal_font
                    draw_text_with_shadow(draw, (x, y), word, font, "white")
                    x += draw.textlength(word, font=font) + space_width
                y += font_size + 15

            # Paste logo
            logo = Image.open(LOGO_PATH).convert("RGBA")
            logo_size = int(IMAGE_SIZE[0] * 0.23)
            logo = logo.resize((logo_size, logo_size), Image.LANCZOS)

            combined = Image.alpha_composite(base, overlay).convert("RGB")
            combined.paste(logo, (IMAGE_SIZE[0] - logo_size, 0), logo)
            combined = combined.filter(ImageFilter.UnsharpMask(radius=1, percent=180, threshold=2))

            # Save and return
            final_path = os.path.join(UPLOAD_DIR, generate_spoofed_filename())
            combined.save(final_path, format="JPEG")
            final_path = postprocess_image(final_path)
            return send_file(final_path, mimetype="image/jpeg", as_attachment=True, download_name=os.path.basename(final_path))

        except Exception as e:
            return jsonify({"error": str(e)}), 500
