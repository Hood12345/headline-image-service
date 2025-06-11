from flask import request, send_file, jsonify
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import os, uuid, re, random, piexif
from datetime import datetime
from utils import draw_text_with_shadow, generate_spoofed_filename, postprocess_image

UPLOAD_DIR = "/tmp"
FONT_PATH = "Anton-Regular.ttf"
LOGO_PATH = "hood_logo.png"
ICC_PROFILE_PATH = "sRGB.icc"
IMAGE_SIZE = (2160, 2700)
FONT_SCALE = 0.063
SHADOW_OFFSET = [(0, 0), (4, 4), (-4, -4), (-4, 4), (4, -4)]


def register(app):
    @app.route("/generate-quote", methods=["POST"])
    def generate_quote():
        if 'file' not in request.files or 'headline' not in request.form:
            return jsonify({"error": "Missing file or headline"}), 400

        img_file = request.files['file']
        headline = request.form['headline']

        try:
            uid = str(uuid.uuid4())
            img_path = os.path.join(UPLOAD_DIR, f"{uid}.jpg")
            img_file.save(img_path)

            base = Image.open(img_path).convert("RGBA").resize(IMAGE_SIZE)
            overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
            draw = ImageDraw.Draw(overlay)

            font_size = int(IMAGE_SIZE[1] * FONT_SCALE)
            quote_font = ImageFont.truetype(FONT_PATH, font_size)
            quote_symbol_font = ImageFont.truetype(FONT_PATH, int(font_size * 2.5))

            # Prepare strings
            quote_text = headline.upper()
            left_quote = "\u201C"  # “
            right_quote = "\u201D"  # ”

            # Measure and position
            text_width = draw.textlength(quote_text, font=quote_font)
            quote_left_width = draw.textlength(left_quote, font=quote_symbol_font)
            quote_right_width = draw.textlength(right_quote, font=quote_symbol_font)
            total_width = quote_left_width + text_width + quote_right_width + 60

            y = IMAGE_SIZE[1] // 2 - quote_font.getbbox(quote_text)[1] // 2
            x = (IMAGE_SIZE[0] - total_width) // 2

            # Draw left quote
            draw_text_with_shadow(draw, (x, y), left_quote, quote_symbol_font, "white")
            x += quote_left_width + 20

            # Draw main text
            draw_text_with_shadow(draw, (x, y), quote_text, quote_font, "white")
            x += text_width + 20

            # Draw right quote
            draw_text_with_shadow(draw, (x, y), right_quote, quote_symbol_font, "white")

            # Bottom gradient
            shadow_height = IMAGE_SIZE[1] * 2 // 3
            for i in range(shadow_height):
                alpha = min(255, int(255 * (i / shadow_height) * 1.5))
                draw.line(
                    [(0, IMAGE_SIZE[1] - shadow_height + i), (IMAGE_SIZE[0], IMAGE_SIZE[1] - shadow_height + i)],
                    fill=(0, 0, 0, alpha)
                )

            # Paste logo
            logo = Image.open(LOGO_PATH).convert("RGBA")
            logo_size = int(IMAGE_SIZE[0] * 0.23)
            logo = logo.resize((logo_size, logo_size), Image.LANCZOS)

            # Combine and finalize
            combined = Image.alpha_composite(base, overlay).convert("RGB")
            combined.paste(logo, (IMAGE_SIZE[0] - logo_size, 0), logo)
            combined = combined.filter(ImageFilter.UnsharpMask(radius=1, percent=180, threshold=2))

            # Save and spoof
            final_path = os.path.join(UPLOAD_DIR, generate_spoofed_filename())
            combined.save(final_path, format="JPEG")

            # Add EXIF spoof
            final_path = postprocess_image(final_path)
            return send_file(final_path, mimetype="image/jpeg", as_attachment=True, download_name=os.path.basename(final_path))

        except Exception as e:
            return jsonify({"error": str(e)}), 500
