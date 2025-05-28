from flask import Flask, request, send_file, jsonify
from PIL import Image, ImageDraw, ImageFont
import os
import uuid
import re

app = Flask(__name__)

# Config
UPLOAD_DIR = "/tmp"
FONT_PATH = "Anton-Regular.ttf"
LOGO_PATH = "hood_logo.png"  # Now using transparent PNG
IMAGE_SIZE = (1080, 1080)  # Force 1:1 output
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
        uid = str(uuid.uuid4())
        img_path = os.path.join(UPLOAD_DIR, f"{uid}.jpg")
        out_path = os.path.join(UPLOAD_DIR, f"{uid}_out.jpg")

        img_file.save(img_path)
        base = Image.open(img_path).convert("RGB")
        base = base.resize(IMAGE_SIZE)

        draw = ImageDraw.Draw(base)
        font = ImageFont.truetype(FONT_PATH, FONT_SIZE)

        # Draw smooth black gradient rectangle at bottom 1/3
        shadow_height = IMAGE_SIZE[1] // 3
        for i in range(shadow_height):
            alpha = int(255 * (i / shadow_height))
            draw.line([(0, IMAGE_SIZE[1] - shadow_height + i), (IMAGE_SIZE[0], IMAGE_SIZE[1] - shadow_height + i)], fill=(0, 0, 0, alpha))

        # Draw the headline text centered
        parsed = parse_highlighted_text(headline.upper())
        total_text = ''.join([t for t, _ in parsed])
        total_width = draw.textlength(total_text, font=font)
        x_start = (base.width - total_width) // 2
        y = base.height - shadow_height + MARGIN

        x = x_start
        for text, color in parsed:
            fill_color = "#FF3C3C" if color == "red" else "white"
            draw_text_with_shadow(draw, (x, y), text, font, fill_color)
            x += draw.textlength(text, font=font)

        # Draw the "NEWS" tag on top-right of the headline area
        label_font = ImageFont.truetype(FONT_PATH, 40)
        label_text = "NEWS"
        label_size = draw.textlength(label_text, font=label_font)
        label_box_w, label_box_h = label_size + 40, 50
        label_x = base.width - label_box_w - MARGIN
        label_y = y - 60
        draw.rectangle((label_x, label_y, label_x + label_box_w, label_y + label_box_h), fill="white")
        draw.text((label_x + 20, label_y + 5), label_text, font=label_font, fill="black")

        # Add HOOD logo (top-right corner)
        logo = Image.open(LOGO_PATH).convert("RGBA")
        logo.thumbnail((150, 150))
        logo_pos = (base.width - logo.width - MARGIN, MARGIN)
        base.paste(logo, logo_pos, logo)

        base.save(out_path, format="JPEG")
        return send_file(out_path, mimetype="image/jpeg", as_attachment=True)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
