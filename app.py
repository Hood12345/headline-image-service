from flask import Flask, request, send_file, jsonify
from PIL import Image, ImageDraw, ImageFont
import os
import uuid
import re

app = Flask(__name__)

# Config
UPLOAD_DIR = "/tmp"
FONT_PATH = "Anton-Regular.ttf"
LOGO_PATH = "hood_logo.png"
IMAGE_SIZE = (1080, 1350)  # 4:5 aspect ratio
MARGIN = 60
FONT_SCALE = 0.063
SHADOW_OFFSET = [(0, 0), (2, 2), (-2, -2), (-2, 2), (2, -2)]
MAX_LINE_WIDTH_RATIO = 0.85
MAX_TOTAL_TEXT_HEIGHT_RATIO = 0.3
MAX_LINE_COUNT = 3

# Helper to draw shadowed text
def draw_text_with_shadow(draw, position, text, font, fill):
    x, y = position
    for dx, dy in SHADOW_OFFSET:
        draw.text((x + dx, y + dy), text, font=font, fill="black")
    draw.text((x, y), text, font=font, fill=fill)

# Parse **red** segments
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
        base = Image.open(img_path).convert("RGBA").resize(IMAGE_SIZE)
        overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        font_size = int(IMAGE_SIZE[1] * FONT_SCALE)
        parsed = parse_highlighted_text(headline.upper())
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

        # Draw black gradient
        shadow_height = IMAGE_SIZE[1] * 2 // 3
        for i in range(shadow_height):
            alpha = min(255, int(255 * (i / shadow_height) * 1.5))
            draw.line([(0, IMAGE_SIZE[1] - shadow_height + i), (IMAGE_SIZE[0], IMAGE_SIZE[1] - shadow_height + i)], fill=(0, 0, 0, alpha))

        # Calculate vertical start
        text_height = len(lines) * (font_size + 15)
        start_y = IMAGE_SIZE[1] - text_height - 80

        # NEWS label
        label_font = ImageFont.truetype(FONT_PATH, int(font_size * 0.6))
        label_text = "NEWS"
        label_box_w = draw.textlength(label_text, font=label_font) + 40
        label_box_h = int(font_size * 0.9)
        label_y = start_y - label_box_h - 15
        draw.rectangle((MARGIN, label_y, MARGIN + label_box_w, label_y + label_box_h), fill="white")
        draw.text((MARGIN + 20, label_y + (label_box_h - font_size * 0.6) // 2), label_text, font=label_font, fill="black")
        draw.line((MARGIN, label_y + label_box_h, MARGIN + label_box_w, label_y + label_box_h), fill="white", width=4)

        # Draw headline
        y = start_y
        for line in lines:
            total_w = sum(draw.textlength(w, font=font) for w, _ in line)
            spaces = len(line) - 1
            spacing = space_width if spaces > 0 else 0
            total_spacing = spacing * spaces
            x = (IMAGE_SIZE[0] - (total_w + total_spacing)) // 2

            for i, (word, color) in enumerate(line):
                fill_color = "#FF3C3C" if color == "red" else "white"
                draw_text_with_shadow(draw, (x, y), word, font, fill_color)
                word_w = draw.textlength(word, font=font)
                x += word_w + (spacing if i < spaces else 0)
            y += font_size + 15

        logo = Image.open(LOGO_PATH).convert("RGBA")
        logo_size = int(IMAGE_SIZE[0] * 0.23)
        logo = logo.resize((logo_size, logo_size), Image.LANCZOS)
        combined = Image.alpha_composite(base, overlay)
        combined.paste(logo, (IMAGE_SIZE[0] - logo_size, 0), logo)
        combined = combined.convert("RGB")
        combined.save(out_path, format="JPEG")

        return send_file(out_path, mimetype="image/jpeg", as_attachment=True)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
