from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).parent
size = 1024
image = Image.new("RGB", (size, size), "#202126")
pixels = image.load()
for y in range(size):
    for x in range(size):
        blend = (x + size - y) / (2 * size)
        pixels[x, y] = (
            round(30 + 30 * blend),
            round(34 + 20 * blend),
            round(47 + 60 * blend),
        )

mask = Image.new("L", (size, size), 0)
ImageDraw.Draw(mask).rounded_rectangle((40, 40, 984, 984), radius=220, fill=255)
background = Image.new("RGB", (size, size), "#202126")
background.paste(image, mask=mask)
draw = ImageDraw.Draw(background)

# Three quiet candlesticks with a rising close line.
bars = [(260, 390, 720, 650), (450, 290, 660, 480), (640, 160, 530, 360)]
for x, high, low, close in bars:
    draw.rounded_rectangle((x - 10, high, x + 10, low), radius=10, fill="#9fc9ff")
    draw.rounded_rectangle(
        (x - 45, close - 55, x + 45, close + 55), radius=18, fill="#dceaff"
    )
draw.line(
    [(180, 680), (430, 520), (650, 420), (845, 250)],
    fill="#68b5ff",
    width=22,
    joint="curve",
)
draw.ellipse((816, 220, 874, 278), fill="#9fd1ff")
background.save(ROOT / "app_icon.png")
