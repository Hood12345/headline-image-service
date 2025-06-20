from flask import Flask, request, send_file, jsonify
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps, ImageEnhance
import piexif
from datetime import datetime
import os
import uuid
import re
import random

app = Flask(__name__)

# Import the second endpoint
import quote
quote.register(app)

# Config
UPLOAD_DIR = "/tmp"
FONT_PATH = "Anton-Regular.ttf"
LOGO_PATH = "hood_logo.png"
ICC_PROFILE_PATH = "sRGB.icc"  # Ensure this exists
IMAGE_SIZE = (2160, 2700)  # 4K (4:5)
MARGIN = 120
FONT_SCALE = 0.085  # Increased for larger text
SHADOW_OFFSET = [(0, 0), (4, 4), (-4, -4), (-4, 4), (4, -4)]
MAX_LINE_WIDTH_RATIO = 0.85
MAX_TOTAL_TEXT_HEIGHT_RATIO = 0.3
MAX_LINE_COUNT = 3

def generate_spoofed_filename():
    now = datetime.now().strftime("%Y%m%d%H%M%S")
    rand_suffix = random.choice(["W39CS", "A49EM", "N52TX", "G20VK"])
    return f"IMG_{now}_{rand_suffix}.jpg"

def draw_text_with_shadow(draw, position, text, font, fill):
    x, y = position
    for dx, dy in SHADOW_OFFSET:
        draw.text((x + dx, y + dy), text, font=font, fill="black")
    draw.text((x, y), text, font=font, fill=fill)

def parse_highlighted_text(raw):
    parts = re.split(r'(\*\*[^*]+\*\*)', raw)
    parsed = []
    for part in parts:
        if part.startswith("**") and part.endswith("**"):
            parsed.append((part[2:-2], "red"))
        else:
            parsed.append((part, "white"))
    return parsed

def postprocess_image(image_path):
    try:
        img = Image.open(image_path)
        new_path = image_path.replace(".jpg", "_processed.jpg")
        img = img.convert("RGB")

        # Embed metadata
        exif_dict = {
            "0th": {
                piexif.ImageIFD.Make: u"Apple",
                piexif.ImageIFD.Model: u"iPhone 15 Pro",
                piexif.ImageIFD.Software: u"Photos 16.1",
            },
            "Exif": {
                piexif.ExifIFD.DateTimeOriginal: datetime.now().strftime("%Y:%m:%d %H:%M:%S"),
                piexif.ExifIFD.LensMake: u"Apple",
            },
        }
        exif_bytes = piexif.dump(exif_dict)

        img.save(
            new_path,
            format="JPEG",
            quality=100,
            subsampling=0,
            dpi=(300, 300),
            optimize=False,
            progressive=False,
            icc_profile=open(ICC_PROFILE_PATH, "rb").read() if os.path.exists(ICC_PROFILE_PATH) else None,
            exif=exif_bytes
        )
        return new_path
    except Exception as e:
        print("[POSTPROCESS ERROR]", str(e))
        return image_path

@app.route("/generate-headline", methods=["POST"])
def generate_headline():
    if 'file' not in request.files or 'headline' not in request.form:
        return jsonify({"error": "Missing file or headline"}), 400

    img_file = request.files['file']
    headline = request.form['headline']

    try:
        uid = str(uuid.uuid4())
        img_path = os.path.join(UPLOAD_DIR, f"{uid}.jpg")
        img_file.save(img_path)

        original = Image.open(img_path).convert("RGBA")
        base = ImageOps.fit(original, IMAGE_SIZE, Image.LANCZOS, centering=(0.5, 0.5))
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

        shadow_height = IMAGE_SIZE[1] * 2 // 3
        for i in range(shadow_height):
            alpha = min(255, int(255 * (i / shadow_height) * 1.5))
            draw.line([(0, IMAGE_SIZE[1] - shadow_height + i), (IMAGE_SIZE[0], IMAGE_SIZE[1] - shadow_height + i)], fill=(0, 0, 0, alpha))

        text_height = len(lines) * (font_size + 15)
        start_y = IMAGE_SIZE[1] - text_height - 160

        label_font = ImageFont.truetype(FONT_PATH, int(font_size * 0.6))
        label_text = request.form.get("label", "NEWS").upper().strip()
        label_box_w = draw.textlength(label_text, font=label_font) + 60
        label_box_h = int(label_font.getbbox(label_text)[3] - label_font.getbbox(label_text)[1]) + 20
        label_y = start_y - label_box_h - 30
        draw.rectangle((MARGIN, label_y, MARGIN + label_box_w, label_y + label_box_h), fill="white")
        text_bbox = label_font.getbbox(label_text)
        text_y = label_y + (label_box_h - (text_bbox[3] - text_bbox[1])) // 2 - text_bbox[1]
        draw.text((MARGIN + 30, text_y), label_text, font=label_font, fill="black")
        draw.line((MARGIN, label_y + label_box_h, MARGIN + label_box_w, label_y + label_box_h), fill="white", width=6)

        y = start_y
        for line in lines:
            total_w = sum(draw.textlength(w, font=font) for w, _ in line)
            spaces = len(line) - 1
            spacing = space_width if spaces > 0 else 0
            x = (IMAGE_SIZE[0] - (total_w + spacing * spaces)) // 2

            for i, (word, color) in enumerate(line):
                fill_color = "#FF3C3C" if color == "red" else "white"
                draw_text_with_shadow(draw, (x, y), word, font, fill_color)
                word_w = draw.textlength(word, font=font)
                x += word_w + (spacing if i < spaces else 0)
            y += font_size + 15

        logo = Image.open(LOGO_PATH).convert("RGBA")
        logo_size = int(IMAGE_SIZE[0] * 0.23)
        logo = logo.resize((logo_size, logo_size), Image.LANCZOS)

        combined = Image.alpha_composite(base, overlay).convert("RGB")
        combined.paste(logo, (IMAGE_SIZE[0] - logo_size, 0), logo)

        final_path = os.path.join(UPLOAD_DIR, generate_spoofed_filename())
        combined.save(final_path, format="JPEG")

        final_path = postprocess_image(final_path)
        return send_file(final_path, mimetype="image/jpeg", as_attachment=True, download_name=os.path.basename(final_path))

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Register file upload endpoint
from upload import register as register_upload
register_upload(app)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
