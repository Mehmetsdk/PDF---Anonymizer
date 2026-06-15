import math
import random
import tempfile
from PIL import Image, ImageDraw


def generate_signature_png(name: str = "", width: int = 200, height: int = 60) -> str:
    """Generate a handwriting-style signature PNG and return its temp file path."""
    img = Image.new("RGBA", (width, height), (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)

    seed = hash(name) % 100_000
    random.seed(seed)

    strokes = _build_strokes(width, height)
    for stroke in strokes:
        if len(stroke) >= 2:
            draw.line(stroke, fill=(10, 10, 60, 210), width=2)

    # Occasional underline flourish
    if random.random() > 0.4:
        ux0 = int(width * 0.05)
        ux1 = int(width * random.uniform(0.5, 0.9))
        uy = int(height * random.uniform(0.75, 0.85))
        draw.line([(ux0, uy), (ux1, uy)], fill=(10, 10, 60, 160), width=1)

    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    img.save(tmp.name)
    return tmp.name


def _build_strokes(width, height):
    strokes = []
    x = width * 0.05
    baseline = height * 0.6
    num_strokes = random.randint(2, 4)

    for _ in range(num_strokes):
        stroke = []
        y = baseline + random.uniform(-height * 0.1, height * 0.1)
        length = random.randint(20, max(21, int(width * 0.35)))
        freq = random.uniform(0.2, 0.5)
        amp = random.uniform(height * 0.1, height * 0.25)

        for i in range(length):
            x += random.uniform(1.5, 3.5)
            y += amp * math.sin(i * freq) * 0.15 + random.uniform(-1, 1)
            if x > width * 0.95:
                break
            stroke.append((x, y))

        strokes.append(stroke)
        x += random.uniform(3, 10)

    return strokes
