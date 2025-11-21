from flask import Flask, request, send_file, jsonify
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageFilter
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

# Layout Tuning
MAX_TEXT_HEIGHT_RATIO = 0.45 
BOTTOM_MARGIN = 180 
GRADIENT_PADDING = 80  # kept for flexibility, not heavily used
MAX_LINE_COUNT = 7
MAX_LINE_WIDTH_RATIO = 0.85

# Shadow / border offsets (from old code)
SHADOW_OFFSET = [(0, 0), (4, 4), (-4, -4), (-4, 4), (4, -4)]

def generate_spoofed_filename():
    now = datetime.now().strftime("%Y%m%d%H%M%S")
    rand_suffix = random.choice(["W39CS", "A49EM", "N52TX", "G20VK"])
    return f"IMG_{now}_{rand_suffix}.jpg"

def draw_text_with_shadow(draw, position, text, font, fill):
    """Old 3D-style border: multiple black offsets + main text."""
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
    label_text = request.form.get("label", "NEWS").upper().strip()

    try:
        uid = str(uuid.uuid4())
        img_path = os.path.join(UPLOAD_DIR, f"{uid}.jpg")
        img_file.save(img_path)

        # 1. Base Image
        original = Image.open(img_path).convert("RGBA")
        base = ImageOps.fit(original, IMAGE_SIZE, Image.LANCZOS, centering=(0.5, 0.5))
        
        overlay = Image.new("RGBA", IMAGE_SIZE, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        # 2. Calculate Headline Wrapping
        font_size = 300 
        parsed = parse_highlighted_text(headline.upper())
        words = [(word, color) for part, color in parsed for word in part.split()]
        
        lines = []
        max_allowed_height = IMAGE_SIZE[1] * MAX_TEXT_HEIGHT_RATIO

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

            line_height = font_size * 1.1
            total_text_height = len(lines) * line_height
            
            if total_text_height <= max_allowed_height and len(lines) <= MAX_LINE_COUNT:
                break
            
            font_size -= 5

        # 3. Positions: headline + label
        line_height = font_size * 1.1
        total_text_height = len(lines) * line_height
        headline_start_y = IMAGE_SIZE[1] - BOTTOM_MARGIN - total_text_height

        # --- OLD LABEL BOX LOGIC (positioned relative to headline_start_y)
        label_font = ImageFont.truetype(FONT_PATH, int(font_size * 0.6))
        # width of label text
        label_box_w = draw.textlength(label_text, font=label_font) + 60
        # height from font bbox + padding
        label_bbox = label_font.getbbox(label_text)
        label_box_h = (label_bbox[3] - label_bbox[1]) + 20
        # box 30px above headline block
        label_y = headline_start_y - label_box_h - 30

        # 4. Guardian Gradient – starts just below label, fully behind text
        gradient_top = label_y + label_box_h  # do not cover label box
        gradient_height = IMAGE_SIZE[1] - gradient_top

        for i in range(gradient_height):
            t = i / gradient_height
            # start already dark (≈200) and go to 255
            alpha = int(200 + 55 * t)
            if alpha > 255:
                alpha = 255
            y_pos = gradient_top + i
            draw.line([(0, y_pos), (IMAGE_SIZE[0], y_pos)], fill=(0, 0, 0, alpha))

        # 5. Draw Label (NEWS / VIRAL) – exactly like old code
        draw.rectangle(
            (MARGIN, label_y, MARGIN + label_box_w, label_y + label_box_h),
            fill="white"
        )
        text_y = label_y + (label_box_h - (label_bbox[3] - label_bbox[1])) // 2 - label_bbox[1]
        draw.text(
            (MARGIN + 30, text_y),
            label_text,
            font=label_font,
            fill="black"
        )
        draw.line(
            (MARGIN, label_y + label_box_h, MARGIN + label_box_w, label_y + label_box_h),
            fill="white",
            width=6
        )

        # 6. Draw Headline Text with 3D border
        y = headline_start_y
        font = ImageFont.truetype(FONT_PATH, font_size)

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
            
            y += line_height

        # 7. Place Logo (Top Right) and Composite
        try:
            logo = Image.open(LOGO_PATH).convert("RGBA")
            logo_size = int(IMAGE_SIZE[0] * 0.23)
            logo = logo.resize((logo_size, logo_size), Image.LANCZOS)
            final_canvas = Image.alpha_composite(base, overlay)
            final_canvas.paste(logo, (IMAGE_SIZE[0] - logo_size, 0), logo)
        except Exception:
            final_canvas = Image.alpha_composite(base, overlay)
            print("Logo not found")

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