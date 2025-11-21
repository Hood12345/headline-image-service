from flask import Flask, request, send_file, jsonify
from PIL import Image, ImageDraw, ImageFont, ImageOps
import piexif
from datetime import datetime
import os
import uuid
import re
import random

app = Flask(__name__)

# Config
UPLOAD_DIR = "/tmp"
FONT_PATH = "Anton-Regular.ttf"
LOGO_PATH = "hood_logo.png"
ICC_PROFILE_PATH = "sRGB.icc"
IMAGE_SIZE = (2160, 2700)  # 4K (4:5)
MARGIN = 120

# LAYOUT CONFIGURATION (used to limit text height)
SPLIT_RATIO = 0.63  # Image takes ~63%, text ~37% logically
IMAGE_AREA_HEIGHT = int(IMAGE_SIZE[1] * SPLIT_RATIO)
TEXT_AREA_HEIGHT = IMAGE_SIZE[1] - IMAGE_AREA_HEIGHT

MAX_LINE_COUNT = 7
MAX_LINE_WIDTH_RATIO = 0.9

def generate_spoofed_filename():
    now = datetime.now().strftime("%Y%m%d%H%M%S")
    rand_suffix = random.choice(["W39CS", "A49EM", "N52TX", "G20VK"])
    return f"IMG_{now}_{rand_suffix}.jpg"

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

        # 1. Base image: full-frame like original service (no solid black)
        original = Image.open(img_path).convert("RGBA")
        base = ImageOps.fit(original, IMAGE_SIZE, Image.LANCZOS, centering=(0.5, 0.5))

        # Transparent overlay for gradient, label, and text
        overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        # 2. Text wrapping / sizing (your "better code" logic)
        font_size = 350  # Start massive
        parsed = parse_highlighted_text(headline.upper())
        words = [(word, color) for part, color in parsed for word in part.split()]

        lines = []

        while font_size > 50:
            font = ImageFont.truetype(FONT_PATH, font_size)
            max_width = IMAGE_SIZE[0] * MAX_LINE_WIDTH_RATIO
            lines = []
            current_line = []
            current_width = 0
            space_width = draw.textlength(" ", font=font)

            for word, color in words:
                word_width = draw.textlength(word, font=font)
                if current_width + word_width > max_width and current_line:
                    lines.append(current_line)
                    current_line = []
                    current_width = 0

                if current_line:
                    current_width += space_width

                current_line.append((word, color))
                current_width += word_width

            if current_line:
                lines.append(current_line)

            total_text_height = len(lines) * (font_size * 1.1)

            # Ensure it fits in the "text area" with some padding
            if total_text_height <= (TEXT_AREA_HEIGHT - 200) and len(lines) <= MAX_LINE_COUNT:
                break

            font_size -= 5

        # 3. Position text near bottom (like meme)
        total_text_height = len(lines) * (font_size * 1.1)
        bottom_margin = 160
        start_y = IMAGE_SIZE[1] - bottom_margin - total_text_height

        # 4. Gradient background that starts above the first text line
        #    and is already dark at that point
        shadow_top = max(0, int(start_y) - 40)  # 40px above first line
        shadow_height = IMAGE_SIZE[1] - shadow_top

        for i in range(shadow_height):
            t = i / shadow_height
            # Start fairly dark (around 200) and go to 255 at bottom
            alpha = int(200 + 55 * t)
            if alpha > 255:
                alpha = 255
            y_shadow = shadow_top + i
            draw.line(
                [(0, y_shadow), (IMAGE_SIZE[0], y_shadow)],
                fill=(0, 0, 0, alpha)
            )

        # 5. Label box (NEWS / VIRAL) above the text, left side
        label_font = ImageFont.truetype(FONT_PATH, int(font_size * 0.6))
        label_text = request.form.get("label", "NEWS").upper().strip()
        label_box_w = draw.textlength(label_text, font=label_font) + 60
        label_box_h = int(label_font.getbbox(label_text)[3] - label_font.getbbox(label_text)[1]) + 20
        label_y = start_y - label_box_h - 30

        # White rectangle
        draw.rectangle(
            (MARGIN, label_y, MARGIN + label_box_w, label_y + label_box_h),
            fill="white"
        )

        # Label text vertically centered
        text_bbox = label_font.getbbox(label_text)
        text_y = label_y + (label_box_h - (text_bbox[3] - text_bbox[1])) // 2 - text_bbox[1]
        draw.text((MARGIN + 30, text_y), label_text, font=label_font, fill="black")

        # Optional underline line under label box (like old code)
        draw.line(
            (MARGIN, label_y + label_box_h, MARGIN + label_box_w, label_y + label_box_h),
            fill="white",
            width=6
        )

        # 6. Draw the headline text itself
        y = start_y
        font = ImageFont.truetype(FONT_PATH, font_size)

        for line in lines:
            total_w = sum(draw.textlength(w, font=font) for w, _ in line)
            spaces = len(line) - 1
            spacing = space_width if spaces > 0 else 0

            x = (IMAGE_SIZE[0] - (total_w + spacing * spaces)) // 2

            for i, (word, color) in enumerate(line):
                fill_color = "#FF3C3C" if color == "red" else "white"
                draw.text((x, y), word, font=font, fill=fill_color)
                word_w = draw.textlength(word, font=font)
                x += word_w + (spacing if i < spaces else 0)

            y += font_size * 1.1

        # 7. Composite base + overlay
        final_canvas = Image.alpha_composite(base, overlay)

        # 8. Place logo (same as before)
        try:
            logo = Image.open(LOGO_PATH).convert("RGBA")
            logo_size = int(IMAGE_SIZE[0] * 0.23)
            logo = logo.resize((logo_size, logo_size), Image.LANCZOS)
            final_canvas.paste(logo, (IMAGE_SIZE[0] - logo_size, 0), logo)
        except Exception as e:
            print("Logo not found or error loading logo:", e)

        # Save
        final_canvas = final_canvas.convert("RGB")
        final_path = os.path.join(UPLOAD_DIR, generate_spoofed_filename())
        final_canvas.save(final_path, format="JPEG")

        final_path = postprocess_image(final_path)
        return send_file(
            final_path,
            mimetype="image/jpeg",
            as_attachment=True,
            download_name=os.path.basename(final_path)
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))