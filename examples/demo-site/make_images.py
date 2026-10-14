"""Create the three plain test images used by index.html (needs Pillow)."""
from PIL import Image, ImageDraw

im = Image.new("RGB", (400, 260), (240, 200, 120))
d = ImageDraw.Draw(im)
d.rectangle((40, 120, 360, 240), fill=(60, 90, 160))
d.ellipse((290, 20, 370, 100), fill=(250, 240, 80))
d.polygon([(40, 120), (200, 40), (360, 120)], fill=(170, 60, 50))
d.rectangle((170, 170, 230, 240), fill=(90, 60, 30))
im.save("house.png")

im = Image.new("RGB", (300, 120), (20, 40, 90))
ImageDraw.Draw(im).text((20, 50), "ACME Coffee Roasters", fill=(255, 255, 255))
im.save("IMG_1234.jpg")

im = Image.new("RGB", (360, 200), (120, 170, 230))
ImageDraw.Draw(im).ellipse((140, 60, 220, 140), fill=(255, 220, 0))
im.save("sunny.png")
