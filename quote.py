from flask import request, send_file, jsonify
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import os, uuid, re, random
from datetime import datetime
from app import app, draw_text_with_shadow, generate_spoofed_filename, postprocess_image

UPLOAD_DIR = "/tmp"
FONT_PATH = "Anton-Regular.ttf"
LOGO_PATH = "hood_logo.png"
IMAGE_SIZE = (2160, 2700)
FONT_SCALE = 0.063

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
        font = ImageFont.truetype(FONT_PATH, font_size)

        headline = f'“{headline.upper()}”'
        text_width = draw.textlength(headline, font=font)
        text_height = font.getbbox(headline)[3] - font.getbbox(headline)[1]
        x = (IMAGE_SIZE[0] - text_width) // 2
        y = (IMAGE_SIZE[1] - text_height) // 2

        draw_text_with_shadow(draw, (x, y), headline, font, "white")

        logo = Image.open(LOGO_PATH).convert("RGBA")
        logo_size = int(IMAGE_SIZE[0] * 0.23)
        logo = logo.resize((logo_size, logo_size), Image.LANCZOS)

        combined = Image.alpha_composite(base, overlay).convert("RGB")
        combined.paste(logo, (IMAGE_SIZE[0] - logo_size, 0), logo)
        combined = combined.filter(ImageFilter.UnsharpMask(radius=1, percent=180, threshold=2))

        final_path = os.path.join(UPLOAD_DIR, generate_spoofed_filename())
        combined.save(final_path, format="JPEG")

        final_path = postprocess_image(final_path)
        return send_file(final_path, mimetype="image/jpeg", as_attachment=True, download_name=os.path.basename(final_path))

    except Exception as e:
        return jsonify({"error": str(e)}), 500
