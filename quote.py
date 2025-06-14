from flask import request, send_file, jsonify
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps
import os, uuid, re, random
from utils import draw_text_with_shadow, generate_spoofed_filename

UPLOAD_DIR = "/tmp"
FONT_PATH = "Anton-Regular.ttf"
LOGO_PATH = "hood_logo.png"
ICC_PROFILE_PATH = "sRGB.icc"
IMAGE_SIZE = (2160, 2700)
FONT_SCALE = 0.085
MARGIN = 120
SHADOW_OFFSET = [(0, 0), (4, 4), (-4, -4), (-4, 4), (4, -4)]
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

            original = Image.open(img_path).convert("RGBA")
            base = ImageOps.fit(original, IMAGE_SIZE, Image.LANCZOS, centering=(0.5, 0.5))
            overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
            draw = ImageDraw.Draw(overlay)

            font_size = int(IMAGE_SIZE[1] * FONT_SCALE)
            parsed = [(headline.upper(), "white")]
            words = [(word, color) for part, color in parsed for word in part.split()]

            while font_size > 10:
                font = ImageFont.truetype(FONT_PATH, font_size)
                max_width = IMAGE_SIZE[0] * MAX_LINE_WIDTH_RATIO
                lines = []
                current_line = []
                current_width = 0
                space_width = draw.textlength(" ", font=font)

                for word, color in words:
                    word_width = draw.textlength(word, font=font)
                    projected_width = current_width + word_width + (space_width if current_line else 0)
                    if projected_width > max_width and current_line:
                        lines.append(current_line)
                        current_line = []
                        current_width = 0
                    if current_line:
                        current_width += space_width
                    current_line.append((word, color))
                    current_width += word_width
                if current_line:
                    lines.append(current_line)

                total_height = len(lines) * (font_size + 15)
                if total_height <= IMAGE_SIZE[1] * MAX_TOTAL_TEXT_HEIGHT_RATIO and len(lines) <= MAX_LINE_COUNT:
                    break
                font_size -= 2

            shadow_height = IMAGE_SIZE[1] * 2 // 3
            for i in range(shadow_height):
                alpha = min(255, int(255 * (i / shadow_height) * 1.5))
                draw.line(
                    [(0, IMAGE_SIZE[1] - shadow_height + i), (IMAGE_SIZE[0], IMAGE_SIZE[1] - shadow_height + i)],
                    fill=(0, 0, 0, alpha)
                )

            text_height = len(lines) * (font_size + 15)
            start_y = IMAGE_SIZE[1] - text_height - 160

            font = ImageFont.truetype(FONT_PATH, font_size)
            y = start_y
            for line in lines:
                total_w = sum(draw.textlength(w, font=font) for w, _ in line)
                spaces = len(line) - 1
                spacing = draw.textlength(" ", font=font) if spaces > 0 else 0
                x = (IMAGE_SIZE[0] - (total_w + spacing * spaces)) // 2

                for i, (word, color) in enumerate(line):
                    draw_text_with_shadow(draw, (x, y), word, font, "white")
                    word_w = draw.textlength(word, font=font)
                    x += word_w + (spacing if i < spaces else 0)
                y += font_size + 15

            logo = Image.open(LOGO_PATH).convert("RGBA")
            logo_size = int(IMAGE_SIZE[0] * 0.23)
            logo = logo.resize((logo_size, logo_size), Image.LANCZOS)

            combined = Image.alpha_composite(base, overlay).convert("RGB")
            combined.paste(logo, (IMAGE_SIZE[0] - logo_size, 0), logo)
            combined = combined.filter(ImageFilter.UnsharpMask(radius=1, percent=180, threshold=2))

            final_path = os.path.join(UPLOAD_DIR, generate_spoofed_filename())
            combined.save(
                final_path,
                format="JPEG",
                quality=95,
                subsampling=0,
                optimize=True,
                icc_profile=open(ICC_PROFILE_PATH, "rb").read() if os.path.exists(ICC_PROFILE_PATH) else None
            )

            return send_file(final_path, mimetype="image/jpeg", as_attachment=True, download_name=os.path.basename(final_path))

        except Exception as e:
            return jsonify({"error": str(e)}), 500
