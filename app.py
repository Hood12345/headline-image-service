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

# Reverted to full screen logic, removing the split constants
MAX_LINE_COUNT = 7
MAX_LINE_WIDTH_RATIO = 0.9
MAX_TEXT_HEIGHT_RATIO = 0.45 # Limit text to bottom 45% of screen
BOTTOM_PAD = 180 # Padding from bottom edge

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

        # 1. Base Image (Full Screen now, no black split)
        original = Image.open(img_path).convert("RGBA")
        # Fit original image to the full 4K canvas
        base = ImageOps.fit(original, IMAGE_SIZE, Image.LANCZOS, centering=(0.5, 0.5))
        
        # Create overlay for text/gradient
        overlay = Image.new("RGBA", IMAGE_SIZE, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        # 2. Process Text Sizing
        font_size = 350 # Start massive
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

            total_text_height = len(lines) * (font_size * 1.1)
            
            # Check if it fits in the bottom area
            if total_text_height <= max_allowed_height and len(lines) <= MAX_LINE_COUNT:
                break
            
            font_size -= 5

        # 3. Calculate Text Position
        line_height = font_size * 1.1
        total_text_height = len(lines) * line_height
        # Position text at bottom with padding
        text_start_y = IMAGE_SIZE[1] - BOTTOM_PAD - total_text_height

        # 4. Draw Dynamic Gradient
        # "Always go right above the first line of text of the headline"
        gradient_start_y = int(text_start_y) # Start exactly at text top
        gradient_height = IMAGE_SIZE[1] - gradient_start_y

        for i in range(gradient_height):
            # Alpha ramp from 0 to 240
            alpha = min(240, int(255 * (i / gradient_height) * 2))
            y_pos = gradient_start_y + i
            draw.line([(0, y_pos), (IMAGE_SIZE[0], y_pos)], fill=(0, 0, 0, alpha))

        # 5. Draw Text
        y = text_start_y
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

        # 6. Place Logo (Top Right as per provided code)
        try:
            logo = Image.open(LOGO_PATH).convert("RGBA")
            logo_size = int(IMAGE_SIZE[0] * 0.23)
            logo = logo.resize((logo_size, logo_size), Image.LANCZOS)
            final_canvas = Image.alpha_composite(base, overlay)
            final_canvas.paste(logo, (IMAGE_SIZE[0] - logo_size, 0), logo)
        except:
            print("Logo not found")
            final_canvas = Image.alpha_composite(base, overlay)

        # Save
        final_canvas = final_canvas.convert("RGB")
        final_path = os.path.join(UPLOAD_DIR, generate_spoofed_filename())
        final_canvas.save(final_path, format="JPEG")

        final_path = postprocess_image(final_path)
        return send_file(final_path, mimetype="image/jpeg", as_attachment=True, download_name=os.path.basename(final_path))

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))

