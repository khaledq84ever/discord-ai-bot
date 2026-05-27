"""Generate 5 branded promo images for the AI Bot (GitHub README + website).

Uses the project design system (navy / red / gold / blurple), Inter (variable,
Latin) + Tajawal (Arabic). Arabic is shaped natively by PIL via libraqm
(direction='rtl'), so it renders fully cursive/connected.
Output: assets/promo/*.png at 1280x640 (GitHub-card friendly).
"""
import os
from PIL import Image, ImageDraw, ImageFont, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
FONTS = os.path.join(HERE, "fonts")
OUT = os.path.join(HERE, "promo")
os.makedirs(OUT, exist_ok=True)

W, H = 1280, 640

# --- design system ---
NAVY = (10, 14, 39)
RED = (232, 0, 28)
GOLD = (212, 168, 67)
BLURPLE = (88, 101, 242)
CARD = (20, 26, 58)
LINE = (38, 48, 94)
MUTED = (154, 166, 212)
WHITE = (255, 255, 255)
GREEN = (87, 242, 135)
BLUE = (66, 153, 245)
PURPLE = (163, 113, 247)


def has_ar(s: str) -> bool:
    return any("؀" <= c <= "ۿ" or "ݐ" <= c <= "ݿ"
               for c in s)


def _kw(s: str) -> dict:
    return dict(direction="rtl", language="ar") if has_ar(s) else {}


def inter(size: int, weight: int = 700):
    f = ImageFont.truetype(os.path.join(FONTS, "Inter-var.ttf"), size)
    try:
        f.set_variation_by_axes([14, weight])
    except Exception:
        pass
    return f


def taj(size: int, bold=True):
    name = "Tajawal-ExtraBold.ttf" if bold else "Tajawal-Bold.ttf"
    return ImageFont.truetype(os.path.join(FONTS, name), size)


def T(d, xy, s, font, fill, anchor="la"):
    """Draw text, auto RTL-shaping for Arabic via libraqm."""
    d.text(xy, s, font=font, fill=fill, anchor=anchor, **_kw(s))


def tw(d, s, font):
    """Measure text width (shaping-aware)."""
    b = d.textbbox((0, 0), s, font=font, **_kw(s))
    return b[2] - b[0], b[3] - b[1]


# Module-scratch draw for measuring before a canvas exists.
_scratch = ImageDraw.Draw(Image.new("RGB", (10, 10)))


def base(glow1=BLURPLE, glow2=RED):
    """Navy canvas with two soft radial glows, like the landing page."""
    img = Image.new("RGB", (W, H), NAVY)
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse([W * 0.45, -H * 0.5, W * 1.15, H * 0.6], fill=glow1 + (90,))
    gd.ellipse([-W * 0.25, H * 0.35, W * 0.45, H * 1.25], fill=glow2 + (70,))
    glow = glow.filter(ImageFilter.GaussianBlur(140))
    return Image.alpha_composite(img.convert("RGBA"), glow).convert("RGB")


def draw_center(d, cy, lines):
    """lines = list of (text, font, fill); vertically centered block at cy."""
    heights = [tw(d, t, f)[1] for t, f, _ in lines]
    gap = 16
    total = sum(heights) + gap * (len(lines) - 1)
    y = cy - total / 2
    for (t, f, c), h in zip(lines, heights):
        T(d, (W / 2, y), t, f, c, anchor="ma")
        y += h + gap


def chip_size(d, label, font, dot=False, pad=22, hpad=14):
    w0, h0 = tw(d, label, font)
    return w0 + pad * 2 + (26 if dot else 0), h0 + hpad * 2


def chip(d, x, y, label, font, dot=None, pad=22, hpad=14, fill=CARD,
         outline=LINE, text_fill=WHITE):
    """Pill chip with optional colored leading dot."""
    w, h = chip_size(d, label, font, dot=bool(dot), pad=pad, hpad=hpad)
    d.rounded_rectangle([x, y, x + w, y + h], radius=h // 2,
                        fill=fill, outline=outline, width=2)
    cx = x + pad
    if dot:
        d.ellipse([cx, y + h / 2 - 8, cx + 16, y + h / 2 + 8], fill=dot)
        cx += 26
    T(d, (cx, y + h / 2), label, font, text_fill, anchor="lm")
    return w, h


def avatar(size):
    p = os.path.join(HERE, "avatar.png")
    if not os.path.exists(p):
        return None
    a = Image.open(p).convert("RGBA").resize((size, size))
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, size, size],
                                           radius=size // 4, fill=255)
    a.putalpha(mask)
    return a


def footer(d, text="github.com/khaledq84ever/discord-ai-bot"):
    T(d, (W / 2, H - 34), text, inter(20, 600), MUTED, anchor="mm")


# ---------------------------------------------------------------- 1 · HERO
def img_hero():
    img = base()
    d = ImageDraw.Draw(img)
    av = avatar(150)
    if av:
        img.paste(av, (int(W / 2 - 75), 64), av)
    draw_center(d, 330, [
        ("بوت الذكاء الاصطناعي", taj(76), WHITE),
        ("Multi-Model AI for Discord", inter(40, 900), GOLD),
    ])
    T(d, (W / 2, 432), "GPT · Gemini · Claude · توليد الصور",
      taj(34), MUTED, anchor="ma")
    items = [("GPT", GREEN), ("Gemini", BLUE), ("Claude", PURPLE),
             ("Images", GOLD)]
    f = inter(26, 700)
    widths = [chip_size(d, t, f, dot=True)[0] for t, _ in items]
    gap = 18
    x = (W - (sum(widths) + gap * (len(items) - 1))) / 2
    for (t, c), w in zip(items, widths):
        chip(d, x, 500, t, f, dot=c)
        x += w + gap
    return img


# --------------------------------------------------------- 2 · MULTI-MODEL
def img_models():
    img = base(glow1=PURPLE, glow2=BLUE)
    d = ImageDraw.Draw(img)
    draw_center(d, 120, [
        ("بدّل بين النماذج بأمر واحد", taj(58), WHITE),
        ("Switch models with /model", inter(34, 900), GOLD),
    ])
    rows = [
        ("GPT-4o · GPT-4o-mini", GREEN, "OpenAI"),
        ("Gemini 2.0 / 2.5 · Pro", BLUE, "Google"),
        ("Claude Sonnet · Opus", PURPLE, "Anthropic"),
    ]
    bw, bh, gap = 820, 92, 24
    x = (W - bw) / 2
    y = 245
    for label, color, brand in rows:
        d.rounded_rectangle([x, y, x + bw, y + bh], radius=20,
                            fill=CARD, outline=LINE, width=2)
        d.ellipse([x + 28, y + bh / 2 - 16, x + 60, y + bh / 2 + 16],
                  fill=color)
        T(d, (x + 86, y + bh / 2), label, inter(30, 800), WHITE, anchor="lm")
        T(d, (x + bw - 28, y + bh / 2), brand, inter(24, 600), MUTED,
          anchor="rm")
        y += bh + gap
    footer(d)
    return img


# ------------------------------------------------------- 3 · IMAGE GEN
def img_imagine():
    img = base(glow1=GOLD, glow2=RED)
    d = ImageDraw.Draw(img)
    draw_center(d, 120, [
        ("ولّد الصور من وصفك", taj(58), WHITE),
        ("Generate images with /imagine", inter(34, 900), GOLD),
    ])
    grads = [(RED, GOLD), (BLURPLE, PURPLE), (BLUE, GREEN)]
    fw, gap = 250, 40
    total = fw * 3 + gap * 2
    x = (W - total) / 2
    y = 245
    for c1, c2 in grads:
        thumb = Image.new("RGB", (fw, fw), c1)
        td = ImageDraw.Draw(thumb)
        for i in range(fw):
            t = i / fw
            col = tuple(int(c1[k] + (c2[k] - c1[k]) * t) for k in range(3))
            td.line([(0, i), (fw, i)], fill=col)
        mask = Image.new("L", (fw, fw), 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, fw, fw], 28, fill=255)
        img.paste(thumb, (int(x), y), mask)
        d.rounded_rectangle([x, y, x + fw, y + fw], radius=28,
                            outline=LINE, width=2)
        T(d, (x + fw / 2, y + fw / 2), "✦", inter(70, 900), WHITE,
          anchor="mm")
        x += fw + gap
    T(d, (W / 2, 560), "DALL·E   +   Google Imagen", inter(26, 700), MUTED,
      anchor="mm")
    return img


# ------------------------------------------------------- 4 · ARABIC-FIRST
def img_arabic():
    img = base(glow1=RED, glow2=GOLD)
    d = ImageDraw.Draw(img)
    draw_center(d, 110, [
        ("عربي أولاً — يفهمك ويرد بلهجتك", taj(56), WHITE),
        ("Arabic-first, bilingual replies", inter(32, 900), GOLD),
    ])

    def bubble(x, y, w, h, text, font, fill, tcol):
        d.rounded_rectangle([x, y, x + w, y + h], radius=24, fill=fill)
        T(d, (x + w / 2, y + h / 2), text, font, tcol, anchor="mm")

    bubble(W - 720, 240, 560, 80, "شلونك؟ سوّي لي صورة قطو فضائي",
           taj(30), BLURPLE, WHITE)
    bubble(160, 350, 520, 80, "تمّ! يا هلا فيك، هذي صورتك",
           taj(30), CARD, WHITE)
    bubble(W - 540, 460, 380, 70, "Works in English too!",
           inter(26, 700), CARD, MUTED)
    footer(d)
    return img


# ------------------------------------------------------- 5 · COMMANDS
def img_commands():
    img = base(glow1=BLURPLE, glow2=GOLD)
    d = ImageDraw.Draw(img)
    draw_center(d, 105, [
        ("كل الأوامر في مكان واحد", taj(56), WHITE),
        ("Simple slash commands", inter(32, 900), GOLD),
    ])
    cmds = [
        ("/ask", "Ask anything", GREEN),
        ("/imagine", "Make an image", GOLD),
        ("/model", "Switch AI model", PURPLE),
        ("/setchannel", "AI-room a channel", BLUE),
        ("/info", "About the bot", RED),
        ("/help", "All commands", BLURPLE),
    ]
    cw, ch, gx, gy, cols = 520, 86, 40, 24, 2
    total_w = cw * cols + gx * (cols - 1)
    x0, y0 = (W - total_w) / 2, 225
    for i, (cmd, desc, color) in enumerate(cmds):
        cx = x0 + (i % cols) * (cw + gx)
        cy = y0 + (i // cols) * (ch + gy)
        d.rounded_rectangle([cx, cy, cx + cw, cy + ch], radius=18,
                            fill=CARD, outline=LINE, width=2)
        d.rounded_rectangle([cx, cy, cx + 8, cy + ch], radius=4, fill=color)
        T(d, (cx + 34, cy + ch / 2), cmd, inter(30, 900), color, anchor="lm")
        T(d, (cx + 230, cy + ch / 2), desc, inter(24, 600), MUTED,
          anchor="lm")
    return img


builders = {
    "01-hero.png": img_hero,
    "02-models.png": img_models,
    "03-imagine.png": img_imagine,
    "04-arabic.png": img_arabic,
    "05-commands.png": img_commands,
}

for name, fn in builders.items():
    fn().save(os.path.join(OUT, name), "PNG")
    print("wrote", os.path.join("assets/promo", name))
