# utils.py
import random, string

def draw_text_with_shadow(draw, position, text, font, fill):
    x, y = position
    shadow_color = "black"
    # Draw shadow
    draw.text((x + 2, y + 2), text, font=font, fill=shadow_color)
    # Draw actual text
    draw.text((x, y), text, font=font, fill=fill)

def generate_spoofed_filename():
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=12)) + ".jpg"

def postprocess_image(path):
    import piexif
    from PIL import Image
    img = Image.open(path)
    img.save(path, format="JPEG", quality=88, icc_profile=open("sRGB.icc", "rb").read())
    piexif.remove(path)
    return path
