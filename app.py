from flask import Flask, request, send_file, jsonify
from PIL import Image, ImageDraw, ImageFont
import os
import uuid
import re

app = Flask(__name__)

# Config
UPLOAD_DIR = "/tmp"
FONT_PATH = "Anton-Regular.ttf"
LOGO_PATH = "hood_logo.jpeg"  # You can convert to PNG if you want transparency
IMAGE_WIDTH = 1080
MARGIN = 60
FONT_SIZE = 68
SHADOW_OFFSET = [(0, 0), (2, 2), (-2, -2), (-2, 2), (2, -2)]

# Helper to draw shadowed text
def draw_text_with_shadow(draw, position, text, font, fill):
    x, y = position
    for dx, dy in SHADOW_OFFSET:
        draw.text((x + dx, y + dy), text, font=font, fill="black")
    draw.text((x, y), text, font=font, fill=fill)

# Helper to parse **red** text segments
def parse_highlighted_text(raw):
    parts = re.split(r'(\*\*[^*]+\*\*)', raw)
    parsed = []
    for part in parts:
        if part.startswith("**") and part.endswith("**"):
            parsed.append((part[2:-2], "red"))
        else:
            parsed.append((part, "white"))
    return parsed

@app.route("/generate-headline", methods=["POST"])
def generate_headline():
    if 'file' not in request.files or 'headline' not in request.form:
        return jsonify({"error": "Missing file or headline"}), 400

    img_file = request.files['file']
    headline = request.form['headline']

    try:
        # Generate unique filename paths
        uid = str(uuid.uuid4())
        img_path = os.path.join(UPLOAD_DIR, f"{uid}.jpg")
        out_path = os.path.join(UPLOAD_DIR, f"{uid}_out.jpg")

        img_file.save(img_path)
        base = Image.open(img_path).convert("RGB")
        draw = ImageDraw.Draw(base)
        font = ImageFont.truetype(FONT_PATH, FONT_SIZE)

        # Draw the "NEWS" label
        label_font = ImageFont.truetype(FONT_PATH, 40)
        draw.text((MARGIN, MARGIN), "NEWS", font=label_font, fill="black")
        line_w = draw.textlength("NEWS", font=label_font)
        draw.line((MARGIN, MARGIN + 48, MARGIN + line_w, MARGIN + 48), fill="black", width=4)

        # Draw the headline (bottom area)
        parsed = parse_highlighted_text(headline.upper())
        total_text = ''.join([t for t, _ in parsed])
        total_width = draw.textlength(total_text, font=font)
        x_start = (base.width - total_width) // 2
        y = base.height - FONT_SIZE * 3

        x = x_start
        for text, color in parsed:
            fill_color = "#FF3C3C" if color == "red" else "white"
            draw_text_with_shadow(draw, (x, y), text, font, fill_color)
            x += draw.textlength(text, font=font)

        # Add HOOD logo (top-right)
        logo = Image.open(LOGO_PATH).convert("RGBA")
        logo.thumbnail((150, 150))
        logo_pos = (base.width - logo.width - MARGIN, MARGIN)
        base.paste(logo, logo_pos, logo if logo.mode == 'RGBA' else None)

        # Save and return
        base.save(out_path, format="JPEG")
        return send_file(out_path, mimetype="image/jpeg", as_attachment=True)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
