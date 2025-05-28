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
IMAGE_SIZE = (1080, 1080)
MARGIN = 60
FONT_SCALE = 0.063  # relative to image height
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
        base = Image.open(img_path).convert("RGBA")
        base = base.resize(IMAGE_SIZE)

        overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        # FONT autosize loop
        font_size = int(IMAGE_SIZE[1] * FONT_SCALE)
        while font_size > 10:
            font = ImageFont.truetype(FONT_PATH, font_size)
            parsed = parse_highlighted_text(headline.upper())
            words = [(text, color) for text, color in parsed if text.strip() != ""]
            lines = []
            current_line = []
            max_width = IMAGE_SIZE[0] * MAX_LINE_WIDTH_RATIO

            for text, color in words:
                test_line = current_line + [(text + ' ', color)]
                test_text = ''.join([t for t, _ in test_line])
                test_width = draw.textlength(test_text, font=font)
                if test_width > max_width and current_line:
                    lines.append(current_line)
                    current_line = [(text + ' ', color)]
                else:
                    current_line.append((text + ' ', color))
            if current_line:
                lines.append(current_line)

            total_text_height = len(lines) * (font_size + 15)
            if total_text_height <= IMAGE_SIZE[1] * MAX_TOTAL_TEXT_HEIGHT_RATIO and len(lines) <= MAX_LINE_COUNT:
                break
            font_size -= 2

        # Draw black gradient
        shadow_height = IMAGE_SIZE[1] * 2 // 3
        for i in range(shadow_height):
            alpha = min(255, int(255 * (i / shadow_height) * 1.5))
            draw.line([(0, IMAGE_SIZE[1] - shadow_height + i), (IMAGE_SIZE[0], IMAGE_SIZE[1] - shadow_height + i)], fill=(0, 0, 0, alpha))

        # Render text lines
        line_height = font_size + 15
        y = IMAGE_SIZE[1] - len(lines) * line_height - 40

        for idx, line in enumerate(lines):
            words_only = [t.strip() for t, _ in line if t.strip()]
            num_spaces = len(words_only) - 1
            total_words_width = sum(draw.textlength(t.strip(), font=font) for t, _ in line)
            available_width = IMAGE_SIZE[0] - 2 * MARGIN
            spacing = (available_width - total_words_width) / num_spaces if num_spaces > 0 else 0
            x = MARGIN if num_spaces > 0 else (IMAGE_SIZE[0] - total_words_width) // 2

            if idx == 0:
                label_font = ImageFont.truetype(FONT_PATH, int(font_size * 0.6))
                label_text = "NEWS"
                label_size = draw.textlength(label_text, font=label_font)
                label_box_w, label_box_h = label_size + 40, int(font_size * 0.9)
                label_x = MARGIN
                label_y = y - int(font_size * 0.2)
                draw.rectangle((label_x, label_y, label_x + label_box_w, label_y + label_box_h), fill="white")
                draw.text((label_x + 20, label_y + (label_box_h - font_size * 0.6) // 2), label_text, font=label_font, fill="black")
                draw.line((label_x, label_y + label_box_h, label_x + label_box_w, label_y + label_box_h), fill="white", width=4)

            for i, (text, color) in enumerate(line):
                fill_color = "#FF3C3C" if color == "red" else "white"
                draw_text_with_shadow(draw, (x, y), text.strip(), font, fill_color)
                text_width = draw.textlength(text.strip(), font=font)
                x += text_width + (spacing if i < num_spaces else 0)
            y += line_height

        logo = Image.open(LOGO_PATH).convert("RGBA")
        logo_size = int(IMAGE_SIZE[0] * 0.23)
        logo = logo.resize((logo_size, logo_size), Image.LANCZOS)
        logo_x = IMAGE_SIZE[0] - logo_size
        combined = Image.alpha_composite(base, overlay)
        combined.paste(logo, (logo_x, 0), logo)

        combined = combined.convert("RGB")
        combined.save(out_path, format="JPEG")
        return send_file(out_path, mimetype="image/jpeg", as_attachment=True)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
