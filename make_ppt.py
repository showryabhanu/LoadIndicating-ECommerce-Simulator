#!/usr/bin/env python3
"""
CloudMart Auto-Scaling Dashboard - Presentation Generator
Creates a professional dark-theme PowerPoint presentation (16:9).
"""

from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.util import Inches, Pt
import copy

# ── Colour palette ──────────────────────────────────────────────────────────
BG       = RGBColor(0x0F, 0x17, 0x2A)   # Dark navy
CARD     = RGBColor(0x1E, 0x29, 0x3B)   # Card background
BORDER   = RGBColor(0x33, 0x41, 0x55)   # Subtle border
PRIMARY  = RGBColor(0x38, 0xBD, 0xF8)   # Sky blue
ACCENT   = RGBColor(0x81, 0x8C, 0xF8)   # Indigo
SUCCESS  = RGBColor(0x10, 0xB9, 0x81)   # Emerald
WARNING  = RGBColor(0xF5, 0x9E, 0x0B)   # Amber
DANGER   = RGBColor(0xEF, 0x44, 0x44)   # Red
WHITE    = RGBColor(0xF8, 0xFA, 0xFC)   # Near-white
MUTED    = RGBColor(0x94, 0xA3, 0xB8)   # Slate 400

prs = Presentation()
prs.slide_width  = Inches(13.33)
prs.slide_height = Inches(7.5)

BLANK = prs.slide_layouts[6]  # Truly blank layout

# ── Helper: solid background ─────────────────────────────────────────────────
def set_bg(slide, color=BG):
    fill = slide.background.fill
    fill.solid()
    fill.fore_color.rgb = color

# ── Helper: add rectangle ────────────────────────────────────────────────────
def rect(slide, l, t, w, h, fill_color=CARD, line_color=None, line_w=Pt(0)):
    shape = slide.shapes.add_shape(1, Inches(l), Inches(t), Inches(w), Inches(h))
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill_color
    if line_color:
        shape.line.color.rgb = line_color
        shape.line.width = line_w
    else:
        shape.line.fill.background()
    return shape

# ── Helper: add text box ─────────────────────────────────────────────────────
def txt(slide, text, l, t, w, h,
        size=18, bold=False, color=WHITE,
        align=PP_ALIGN.LEFT, wrap=True):
    tb = slide.shapes.add_textbox(Inches(l), Inches(t), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = wrap
    p = tf.paragraphs[0]
    p.alignment = align
    run = p.add_run()
    run.text = text
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = color
    return tb

# ── Helper: multi-line bullet block ─────────────────────────────────────────
def bullets(slide, items, l, t, w, h,
            size=14, color=WHITE, bullet_color=PRIMARY,
            line_space=1.15):
    from pptx.util import Pt
    from pptx.oxml.ns import qn
    import lxml.etree as etree

    tb = slide.shapes.add_textbox(Inches(l), Inches(t), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True

    for i, item in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = PP_ALIGN.LEFT

        # bullet character
        brun = p.add_run()
        brun.text = "▸  "
        brun.font.size = Pt(size)
        brun.font.color.rgb = bullet_color
        brun.font.bold = True

        trun = p.add_run()
        trun.text = item
        trun.font.size = Pt(size)
        trun.font.color.rgb = color

# ══════════════════════════════════════════════════════════════════════════════
#  SLIDE 1 – Title Slide
# ══════════════════════════════════════════════════════════════════════════════
s = prs.slides.add_slide(BLANK)
set_bg(s)

# Gradient accent bar (left edge)
rect(s, 0, 0, 0.08, 7.5, fill_color=PRIMARY)

# Decorative circle top-right
c = s.shapes.add_shape(9, Inches(10.5), Inches(-1.2), Inches(4), Inches(4))
c.fill.solid(); c.fill.fore_color.rgb = RGBColor(0x1E, 0x3A, 0x8A)
c.line.fill.background()

c2 = s.shapes.add_shape(9, Inches(11.2), Inches(4.8), Inches(2.5), Inches(2.5))
c2.fill.solid(); c2.fill.fore_color.rgb = RGBColor(0x1E, 0x29, 0x3B)
c2.line.fill.background()

# Title
txt(s, "CloudMart", 0.5, 1.6, 10, 1.2, size=52, bold=True, color=PRIMARY)
txt(s, "Auto-Scaling Dashboard", 0.5, 2.7, 10, 1.0, size=36, bold=False, color=WHITE)

# Subtitle line
rect(s, 0.5, 3.75, 6, 0.04, fill_color=PRIMARY)

txt(s, "Cloud Computing Project  ·  AWS Academy Learner Lab  ·  2026",
    0.5, 3.95, 10, 0.5, size=14, color=MUTED)

txt(s, "Automatic horizontal scaling of an e-commerce backend,\n"
       "visualised live through a serverless observability dashboard.",
    0.5, 4.5, 9, 1.0, size=16, color=WHITE)

# AWS badge
rect(s, 0.5, 6.4, 2.6, 0.55, fill_color=RGBColor(0x1E,0x3A,0x8A), line_color=PRIMARY, line_w=Pt(1))
txt(s, "☁  Built on Amazon Web Services", 0.55, 6.43, 2.5, 0.5,
    size=11, bold=True, color=PRIMARY, align=PP_ALIGN.CENTER)

# ══════════════════════════════════════════════════════════════════════════════
#  SLIDE 2 – Project Overview
# ══════════════════════════════════════════════════════════════════════════════
s = prs.slides.add_slide(BLANK)
set_bg(s)
rect(s, 0, 0, 13.33, 0.9, fill_color=CARD)
txt(s, "Project Overview", 0.4, 0.15, 9, 0.65, size=28, bold=True, color=PRIMARY)
rect(s, 0.4, 0.88, 2.0, 0.05, fill_color=PRIMARY)

# Two-column cards
for lx, title, body, col in [
    (0.3, "What it Does", [
        "An e-commerce shop (Flask + Gunicorn) runs on EC2 instances",
        "Traffic is distributed by an Application Load Balancer (ALB)",
        "Auto Scaling Group (ASG) adds/removes EC2s based on CPU load",
        "A live web dashboard visualises all metrics in real time",
        "A synthetic load generator simulates real-world traffic spikes",
    ], PRIMARY),
    (6.8, "Why it Matters", [
        "Demonstrates elasticity – scale out under load, scale in after",
        "Cost-efficient – you only pay for instances you actually need",
        "Fault-tolerant – multi-AZ deployment across 6 availability zones",
        "Observable – live CloudWatch metrics surfaced in the dashboard",
        "Fully automated – no manual intervention required to scale",
    ], SUCCESS),
]:
    rect(s, lx, 1.1, 6.2, 5.9, fill_color=CARD, line_color=col, line_w=Pt(1.5))
    txt(s, title, lx+0.2, 1.2, 5.8, 0.55, size=18, bold=True, color=col)
    rect(s, lx+0.2, 1.75, 5.5, 0.03, fill_color=col)
    bullets(s, body, lx+0.2, 1.9, 5.8, 4.5, size=14, color=WHITE, bullet_color=col)

# ══════════════════════════════════════════════════════════════════════════════
#  SLIDE 3 – System Architecture
# ══════════════════════════════════════════════════════════════════════════════
s = prs.slides.add_slide(BLANK)
set_bg(s)
rect(s, 0, 0, 13.33, 0.9, fill_color=CARD)
txt(s, "System Architecture", 0.4, 0.15, 9, 0.65, size=28, bold=True, color=PRIMARY)
rect(s, 0.4, 0.88, 2.5, 0.05, fill_color=PRIMARY)

# Architecture diagram boxes and arrows drawn with shapes
def arch_box(slide, label, sublabel, lx, ty, w=2.2, h=0.85, fc=CARD, bc=PRIMARY):
    rect(slide, lx, ty, w, h, fill_color=fc, line_color=bc, line_w=Pt(1.5))
    txt(slide, label, lx+0.08, ty+0.05, w-0.1, 0.4, size=13, bold=True, color=bc, align=PP_ALIGN.CENTER)
    if sublabel:
        txt(slide, sublabel, lx+0.08, ty+0.44, w-0.1, 0.35, size=10, color=MUTED, align=PP_ALIGN.CENTER)

def arrow(slide, lx, ty, w, h=0.0, vertical=False):
    # simple line arrow
    from pptx.util import Pt
    if vertical:
        shp = slide.shapes.add_shape(1, Inches(lx), Inches(ty), Inches(0.02), Inches(h))
    else:
        shp = slide.shapes.add_shape(1, Inches(lx), Inches(ty), Inches(w), Inches(0.02))
    shp.fill.solid(); shp.fill.fore_color.rgb = BORDER
    shp.line.fill.background()

# Row 1: User + S3
arch_box(s, "User Browser", "Opens Dashboard URL", 0.3, 1.1, bc=ACCENT)
arch_box(s, "Amazon S3", "Static Website Hosting\nindex.html + config.js", 3.1, 1.1, bc=ACCENT)
# arrow user→s3
rect(s, 2.52, 1.48, 0.6, 0.04, fill_color=BORDER)
txt(s, "→", 2.95, 1.35, 0.3, 0.3, size=14, color=BORDER, align=PP_ALIGN.CENTER)

# Row 2: API Gateway + Lambda api
arch_box(s, "API Gateway", "HTTP API  /metrics\n/load/start  /load/stop", 0.3, 2.3, bc=PRIMARY)
arch_box(s, "cloudmart-api", "Lambda  Python 3.12\n256 MB · 30s timeout", 3.1, 2.3, bc=PRIMARY)
rect(s, 2.52, 2.68, 0.6, 0.04, fill_color=BORDER)
txt(s, "→", 2.95, 2.55, 0.3, 0.3, size=14, color=BORDER, align=PP_ALIGN.CENTER)

# Row 2 → CloudWatch & ASG (right side)
arch_box(s, "CloudWatch", "CPU / Requests\nResponseTime / Hosts", 6.1, 2.3, bc=WARNING)
arch_box(s, "Auto Scaling Group", "Min 1 · Max 4\nSimple ±1 Policies", 9.0, 2.3, bc=SUCCESS)
rect(s, 5.32, 2.68, 0.8, 0.04, fill_color=BORDER)
txt(s, "→", 5.86, 2.55, 0.3, 0.3, size=14, color=BORDER, align=PP_ALIGN.CENTER)
rect(s, 8.22, 2.68, 0.8, 0.04, fill_color=BORDER)
txt(s, "→", 8.76, 2.55, 0.3, 0.3, size=14, color=BORDER, align=PP_ALIGN.CENTER)

# Row 3: loadgen + ALB + EC2s
arch_box(s, "cloudmart-loadgen", "Lambda  512 MB\n900s · /checkout loop", 0.3, 3.55, bc=DANGER)
arch_box(s, "App Load Balancer", "HTTP :80 → :8000\nInternet-facing", 3.1, 3.55, bc=PRIMARY)
arch_box(s, "EC2 Instance 1", "AL2023 · t3.micro\nGunicorn 4 workers", 6.1, 3.55, bc=SUCCESS)
arch_box(s, "EC2 Instance 2+", "Auto-launched\nby ASG scale-out", 9.0, 3.55, bc=SUCCESS)

rect(s, 2.52, 3.93, 0.6, 0.04, fill_color=BORDER)
txt(s, "→", 2.95, 3.80, 0.3, 0.3, size=14, color=BORDER, align=PP_ALIGN.CENTER)
rect(s, 5.32, 3.93, 0.8, 0.04, fill_color=BORDER)
txt(s, "→", 5.86, 3.80, 0.3, 0.3, size=14, color=BORDER, align=PP_ALIGN.CENTER)
rect(s, 8.22, 3.93, 0.8, 0.04, fill_color=BORDER)
txt(s, "→", 8.76, 3.80, 0.3, 0.3, size=14, color=BORDER, align=PP_ALIGN.CENTER)

# State S3
arch_box(s, "S3 State Store", "state/load.json\nrun_id · duration", 0.3, 4.8, bc=ACCENT)
rect(s, 1.4, 4.4, 0.04, 0.42, fill_color=BORDER)

# Legend
for lx2, lbl, col in [
    (0.3,  "Frontend / Storage", ACCENT),
    (2.8,  "API Layer",         PRIMARY),
    (5.1,  "Monitoring",        WARNING),
    (7.3,  "Compute",           SUCCESS),
    (9.4,  "Load Generator",    DANGER),
]:
    rect(s, lx2, 6.9, 0.25, 0.25, fill_color=col)
    txt(s, lbl, lx2+0.3, 6.88, 2.0, 0.3, size=11, color=MUTED)

# ══════════════════════════════════════════════════════════════════════════════
#  SLIDE 4 – AWS Services Used
# ══════════════════════════════════════════════════════════════════════════════
s = prs.slides.add_slide(BLANK)
set_bg(s)
rect(s, 0, 0, 13.33, 0.9, fill_color=CARD)
txt(s, "AWS Services Used", 0.4, 0.15, 9, 0.65, size=28, bold=True, color=PRIMARY)
rect(s, 0.4, 0.88, 2.2, 0.05, fill_color=PRIMARY)

services = [
    ("EC2",            PRIMARY,  "Virtual machines that run the Flask+Gunicorn shop.\nAmazon Linux 2023 · t3.micro · Detailed monitoring ON."),
    ("Auto Scaling",   SUCCESS,  "Automatically adjusts the number of EC2 instances.\nMin 1 · Max 4 · Desired 1 · ELB health checks."),
    ("ALB (ELBv2)",    PRIMARY,  "Layer-7 load balancer distributing traffic to EC2 on :8000.\nInternet-facing · Multi-AZ · /health check every 15 s."),
    ("CloudWatch",     WARNING,  "Collects CPU, RequestCount, ResponseTime, HealthyHostCount.\nTriggers alarms that activate scaling policies."),
    ("Lambda",         ACCENT,   "Serverless functions – cloudmart-api (metrics/load API)\nand cloudmart-loadgen (synthetic traffic generator)."),
    ("API Gateway",    PRIMARY,  "HTTP API v2 fronting cloudmart-api Lambda.\nCORS enabled · Payload v2 · $default auto-deploy stage."),
    ("S3",             ACCENT,   "Static website hosting for the dashboard HTML/JS.\nAlso stores load-test run state (state/load.json)."),
    ("SSM Param Store",MUTED,    "Read-only lookup of the latest Amazon Linux 2023 AMI ID.\nAvoids hard-coding AMI IDs in the codebase."),
]

cols = [(0.3, 0), (0.3, 1), (0.3, 2), (0.3, 3),
        (6.8, 0), (6.8, 1), (6.8, 2), (6.8, 3)]

for i, (name, col, desc) in enumerate(services):
    lx = 0.3 if i < 4 else 6.8
    ty = 1.1 + (i % 4) * 1.5
    rect(s, lx, ty, 6.2, 1.35, fill_color=CARD, line_color=col, line_w=Pt(1.5))
    # colour strip on left
    rect(s, lx, ty, 0.12, 1.35, fill_color=col)
    txt(s, name, lx+0.22, ty+0.12, 5.7, 0.4, size=15, bold=True, color=col)
    txt(s, desc, lx+0.22, ty+0.52, 5.7, 0.75, size=12, color=WHITE)

# ══════════════════════════════════════════════════════════════════════════════
#  SLIDE 5 – Auto-Scaling Mechanics
# ══════════════════════════════════════════════════════════════════════════════
s = prs.slides.add_slide(BLANK)
set_bg(s)
rect(s, 0, 0, 13.33, 0.9, fill_color=CARD)
txt(s, "Auto-Scaling Mechanics", 0.4, 0.15, 9, 0.65, size=28, bold=True, color=PRIMARY)
rect(s, 0.4, 0.88, 2.8, 0.05, fill_color=PRIMARY)

# Timeline flow chart – Scale Out
rect(s, 0.3, 1.1, 12.7, 2.5, fill_color=RGBColor(0x14,0x20,0x33), line_color=DANGER, line_w=Pt(1))
txt(s, "⬆  SCALE-OUT FLOW  (CPU > 50 %)", 0.5, 1.15, 8, 0.4, size=14, bold=True, color=DANGER)

steps_out = [
    ("Load Test\nStarts",       "POST /load/start\ncloudmart-loadgen"),
    ("CPU Spikes\n> 50 %",      "EC2 CPUUtilization\ndetailed 1-min metric"),
    ("Alarm IN\nALARM",         "cloudmart-cpu-high\n2 periods × 60 s"),
    ("Policy\nFires",           "cloudmart-scale-out\n+1  Cooldown: 120 s"),
    ("New EC2\nLaunches",       "AL2023 · Gunicorn\nSystemd auto-start"),
    ("Healthy &\nIn Service",   "ALB health check\n/health → 200 OK"),
]
bx = 0.4
for i, (top, bot) in enumerate(steps_out):
    fc = DANGER if i in (0, 2, 4) else CARD
    rect(s, bx, 1.65, 1.95, 1.65, fill_color=fc, line_color=DANGER, line_w=Pt(1))
    txt(s, top, bx+0.05, 1.72, 1.85, 0.5, size=12, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
    txt(s, bot, bx+0.05, 2.22, 1.85, 0.75, size=10, color=MUTED, align=PP_ALIGN.CENTER)
    if i < 5:
        txt(s, "→", bx+1.98, 2.1, 0.35, 0.5, size=20, bold=True, color=DANGER, align=PP_ALIGN.CENTER)
    bx += 2.18

# Timeline flow chart – Scale In
rect(s, 0.3, 3.8, 12.7, 2.5, fill_color=RGBColor(0x14,0x20,0x33), line_color=SUCCESS, line_w=Pt(1))
txt(s, "⬇  SCALE-IN FLOW  (CPU < 20 %)", 0.5, 3.85, 8, 0.4, size=14, bold=True, color=SUCCESS)

steps_in = [
    ("Load Test\nStops",        "POST /load/stop\nor duration expires"),
    ("CPU Drops\n< 20 %",       "EC2 CPUUtilization\nreturns to baseline"),
    ("Alarm IN\nALARM",         "cloudmart-cpu-low\n3 periods × 60 s"),
    ("Policy\nFires",           "cloudmart-scale-in\n−1  Cooldown: 120 s"),
    ("Excess EC2\nTerminated",  "ASG drains &\nterminates instance"),
    ("Back to\nMin=1",          "1 instance serving\nnormal traffic"),
]
bx = 0.4
for i, (top, bot) in enumerate(steps_in):
    fc = SUCCESS if i in (0, 2, 4) else CARD
    rect(s, bx, 4.35, 1.95, 1.65, fill_color=fc, line_color=SUCCESS, line_w=Pt(1))
    txt(s, top, bx+0.05, 4.42, 1.85, 0.5, size=12, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
    txt(s, bot, bx+0.05, 4.92, 1.85, 0.75, size=10, color=MUTED, align=PP_ALIGN.CENTER)
    if i < 5:
        txt(s, "→", bx+1.98, 4.8, 0.35, 0.5, size=20, bold=True, color=SUCCESS, align=PP_ALIGN.CENTER)
    bx += 2.18

txt(s, "ASG Config:  Min=1  |  Max=4  |  Desired=1  |  Grace Period=180 s  |  Health Check=ELB",
    0.4, 6.95, 12.5, 0.4, size=12, color=MUTED, align=PP_ALIGN.CENTER)

# ══════════════════════════════════════════════════════════════════════════════
#  SLIDE 6 – The E-Commerce Shop (Backend)
# ══════════════════════════════════════════════════════════════════════════════
s = prs.slides.add_slide(BLANK)
set_bg(s)
rect(s, 0, 0, 13.33, 0.9, fill_color=CARD)
txt(s, "The Shop Backend (EC2 + Flask)", 0.4, 0.15, 9, 0.65, size=28, bold=True, color=PRIMARY)
rect(s, 0.4, 0.88, 3.2, 0.05, fill_color=PRIMARY)

# Left: code-style card
rect(s, 0.3, 1.1, 6.2, 5.9, fill_color=RGBColor(0x0D,0x14,0x26), line_color=PRIMARY, line_w=Pt(1.5))
txt(s, "shop/application.py  (key parts)", 0.5, 1.2, 5.8, 0.4, size=13, bold=True, color=PRIMARY)
rect(s, 0.5, 1.6, 5.7, 0.03, fill_color=BORDER)
code = (
    "PRODUCTS = [\n"
    '  {"id":1, "name":"Laptop",     "price":55000},\n'
    '  {"id":2, "name":"Headphones", "price":2500},\n'
    '  {"id":3, "name":"Keyboard",   "price":1800},\n'
    "]\n\n"
    "def burn_cpu(ms=150):\n"
    "    # SHA-256 loops to simulate\n"
    "    # heavy order processing\n"
    "    ...\n\n"
    "@app.route('/checkout')\n"
    "def checkout():\n"
    "    burn_cpu(150)   # ← drives CPU\n"
    '    return {"status":"order placed"}\n\n'
    "@app.route('/health')\n"
    "def health():\n"
    '    return "ok"   # ALB health probe'
)
txt(s, code, 0.5, 1.7, 5.8, 5.0, size=11.5, color=RGBColor(0xA5,0xF3,0xFC))

# Right: endpoint table + systemd
rect(s, 6.8, 1.1, 6.2, 2.7, fill_color=CARD, line_color=PRIMARY, line_w=Pt(1))
txt(s, "HTTP Endpoints", 7.0, 1.2, 5.8, 0.4, size=14, bold=True, color=PRIMARY)
endpoints = [
    ("GET  /",          "Product catalogue (HTML)"),
    ("GET  /api/products", "JSON product list"),
    ("GET  /checkout",  "CPU burn + JSON response"),
    ("GET  /health",    "ALB health probe → 'ok'"),
]
for i, (ep, desc) in enumerate(endpoints):
    ty2 = 1.75 + i * 0.47
    rect(s, 6.9, ty2, 6.0, 0.4, fill_color=RGBColor(0x0F,0x17,0x2A))
    txt(s, ep,   7.0,  ty2+0.05, 2.2, 0.32, size=11, bold=True, color=SUCCESS)
    txt(s, desc, 9.25, ty2+0.05, 3.4, 0.32, size=11, color=WHITE)

rect(s, 6.8, 4.0, 6.2, 2.9, fill_color=CARD, line_color=ACCENT, line_w=Pt(1))
txt(s, "Systemd Service on EC2", 7.0, 4.1, 5.8, 0.4, size=14, bold=True, color=ACCENT)
systemd = (
    "[Unit]\n"
    "Description=CloudMart Gunicorn\n\n"
    "[Service]\n"
    "ExecStart=/usr/local/bin/gunicorn\n"
    "  --bind 0.0.0.0:8000\n"
    "  --workers 4 --timeout 60\n"
    "  application:application\n"
    "Restart=always\n\n"
    "[Install]\n"
    "WantedBy=multi-user.target"
)
txt(s, systemd, 7.0, 4.6, 5.8, 2.2, size=11, color=RGBColor(0xA5,0xF3,0xFC))

# ══════════════════════════════════════════════════════════════════════════════
#  SLIDE 7 – Live Dashboard Features
# ══════════════════════════════════════════════════════════════════════════════
s = prs.slides.add_slide(BLANK)
set_bg(s)
rect(s, 0, 0, 13.33, 0.9, fill_color=CARD)
txt(s, "Live Dashboard Features", 0.4, 0.15, 9, 0.65, size=28, bold=True, color=PRIMARY)
rect(s, 0.4, 0.88, 2.5, 0.05, fill_color=PRIMARY)

features = [
    ("🟢  LIVE Badge",         PRIMARY,
     "Pulsing green dot + last-updated timestamp.\nPolls every 5 seconds automatically."),
    ("📊  4 KPI Cards",        ACCENT,
     "Current CPU %, Requests/min, Avg Response Time (ms),\nand InService Instances / Max."),
    ("🎯  CPU Semicircle Gauge", WARNING,
     "Animated needle – green (<40%), amber (40-70%), red (>70%).\nLabelled LOW / MEDIUM / HIGH LOAD."),
    ("📈  3 Line Charts",      PRIMARY,
     "30-min history: CPU % (with dashed 50% threshold),\nRequests/min, and Healthy Host Count (stepped line)."),
    ("🖥  Instance Tiles",     SUCCESS,
     "One card per EC2: short ID, AZ, state.\nPulses amber while Pending, red while Terminating."),
    ("📜  Scaling Timeline",   ACCENT,
     "10 latest ASG activities with time, status, description,\nand cause. Newest first."),
    ("⚡  Load Generator",    DANGER,
     "Duration select (1–6 min) + threads slider (10–60).\nCountdown progress bar while test is running."),
    ("🔴  Error Banner",       MUTED,
     "Red banner if API fails, with auto-retry every 5 s.\n'Waiting for data' message for empty CloudWatch series."),
]

for i, (title, col, desc) in enumerate(features):
    lx = 0.3 if i < 4 else 6.8
    ty = 1.1 + (i % 4) * 1.55
    rect(s, lx, ty, 6.2, 1.4, fill_color=CARD, line_color=col, line_w=Pt(1.5))
    rect(s, lx, ty, 0.12, 1.4, fill_color=col)
    txt(s, title, lx+0.22, ty+0.12, 5.8, 0.4, size=14, bold=True, color=col)
    txt(s, desc,  lx+0.22, ty+0.55, 5.8, 0.75, size=12, color=WHITE)

# ══════════════════════════════════════════════════════════════════════════════
#  SLIDE 8 – Lambda Functions Deep-Dive
# ══════════════════════════════════════════════════════════════════════════════
s = prs.slides.add_slide(BLANK)
set_bg(s)
rect(s, 0, 0, 13.33, 0.9, fill_color=CARD)
txt(s, "Serverless Backend – Lambda Functions", 0.4, 0.15, 9, 0.65, size=28, bold=True, color=PRIMARY)
rect(s, 0.4, 0.88, 3.8, 0.05, fill_color=PRIMARY)

for lx, name, config, col, routes in [
    (0.3, "cloudmart-api",
     "Python 3.12  ·  256 MB  ·  30 s timeout",
     PRIMARY,
     [
         "GET  /metrics",
         "  → CloudWatch get_metric_data (last 30 min, 60 s periods)",
         "  → ASG describe_auto_scaling_groups + scaling activities",
         "  → S3 state/load.json for active load test info",
         "",
         "POST  /load/start  {duration, threads}",
         "  → Writes state/load.json (run_id, started, duration, threads)",
         "  → Invokes cloudmart-loadgen asynchronously (Event type)",
         "",
         "POST  /load/stop",
         "  → Clears state/load.json  {run_id: null}",
         "",
         "OPTIONS  /{proxy+}",
         "  → Returns 200 with CORS headers (Access-Control-Allow-Origin: *)",
     ]),
    (6.8, "cloudmart-loadgen",
     "Python 3.12  ·  512 MB  ·  900 s timeout",
     DANGER,
     [
         "Input: {run_id, duration, threads, url}",
         "",
         "Spawns N worker threads (up to 60)",
         "  → Each calls GET {url}/checkout in a tight loop",
         "  → Uses urllib (no external deps needed in Lambda)",
         "  → Counts ok / err responses",
         "",
         "Watcher thread (every 5 s):",
         "  → Reads state/load.json from S3",
         "  → If run_id changed → sets stop_event → all workers stop",
         "",
         "On exit:",
         "  → Clears run_id in S3 state/load.json",
         "  → Returns {ok, err, duration_sec}",
     ]),
]:
    rect(s, lx, 1.1, 6.2, 5.9, fill_color=CARD, line_color=col, line_w=Pt(1.5))
    txt(s, name,   lx+0.2, 1.2,  5.8, 0.45, size=18, bold=True, color=col)
    txt(s, config, lx+0.2, 1.65, 5.8, 0.35, size=11, color=MUTED)
    rect(s, lx+0.2, 2.0, 5.5, 0.03, fill_color=col)
    body = "\n".join(routes)
    txt(s, body, lx+0.2, 2.1, 5.8, 4.7, size=11, color=WHITE)

# ══════════════════════════════════════════════════════════════════════════════
#  SLIDE 9 – Deployment & Security
# ══════════════════════════════════════════════════════════════════════════════
s = prs.slides.add_slide(BLANK)
set_bg(s)
rect(s, 0, 0, 13.33, 0.9, fill_color=CARD)
txt(s, "Deployment & Security Design", 0.4, 0.15, 9, 0.65, size=28, bold=True, color=PRIMARY)
rect(s, 0.4, 0.88, 3.0, 0.05, fill_color=PRIMARY)

# Deployment steps card
rect(s, 0.3, 1.1, 6.2, 5.9, fill_color=CARD, line_color=PRIMARY, line_w=Pt(1.5))
txt(s, "▶  Deploy in 2 Commands", 0.5, 1.2, 5.8, 0.45, size=16, bold=True, color=PRIMARY)
rect(s, 0.5, 1.65, 5.6, 0.03, fill_color=BORDER)
steps = [
    ("1", "python infra.py create",
          "Creates: SGs, ALB, TG, Launch Template, ASG\n"
          "Scaling policies, CloudWatch alarms\n"
          "Waits for first healthy target, then curls the ALB"),
    ("2", "python deploy.py deploy",
          "Creates: S3 bucket (public website), Lambdas,\n"
          "API Gateway HTTP API with CORS + routes\n"
          "Uploads web/ assets, prints dashboard URL"),
]
ty2 = 1.8
for num, cmd, desc in steps:
    rect(s, 0.4, ty2, 6.0, 0.35, fill_color=PRIMARY)
    txt(s, f"Step {num}  —  {cmd}", 0.55, ty2+0.04, 5.6, 0.3, size=12, bold=True, color=BG)
    txt(s, desc, 0.55, ty2+0.42, 5.6, 0.75, size=11.5, color=WHITE)
    ty2 += 1.4

rect(s, 0.4, ty2+0.1, 6.0, 0.35, fill_color=DANGER)
txt(s, "Teardown  —  python deploy.py destroy  +  python infra.py destroy",
    0.55, ty2+0.14, 5.6, 0.3, size=11, bold=True, color=WHITE)
txt(s, "Removes all AWS resources safely in reverse order.\n"
       "ALB, ASG (ForceDelete), TG, LT, SGs deleted with retry waits.",
    0.55, ty2+0.55, 5.6, 0.6, size=11, color=WHITE)

# Security card
rect(s, 6.8, 1.1, 6.2, 5.9, fill_color=CARD, line_color=WARNING, line_w=Pt(1.5))
txt(s, "🔒  Security Measures", 7.0, 1.2, 5.8, 0.45, size=16, bold=True, color=WARNING)
rect(s, 7.0, 1.65, 5.6, 0.03, fill_color=BORDER)
sec_items = [
    ("Security Groups",
     "cloudmart-alb-sg: inbound TCP 80 from 0.0.0.0/0 only.\n"
     "cloudmart-ec2-sg: inbound TCP 8000 from ALB SG only.\n"
     "EC2 instances are NOT directly internet-reachable."),
    ("IAM / LabRole",
     "All Lambdas and EC2s use pre-existing LabRole.\n"
     "No new IAM roles created. Credentials never printed or committed.\n"
     "config.json is in .gitignore."),
    ("S3 Static Site",
     "Public GetObject policy on /*, but write operations\n"
     "are denied to the public (AWS IAM).\n"
     "No sensitive data stored in the website bucket."),
    ("CORS Policy",
     "API Gateway configured with AllowOrigins: ['*'].\n"
     "Only GET, POST, OPTIONS allowed.\n"
     "Content-Type header required on POST routes."),
]
ty3 = 1.8
for stitle, sdesc in sec_items:
    rect(s, 6.9, ty3, 6.0, 1.3, fill_color=RGBColor(0x0F,0x17,0x2A))
    txt(s, stitle, 7.05, ty3+0.08, 5.6, 0.35, size=13, bold=True, color=WARNING)
    txt(s, sdesc,  7.05, ty3+0.44, 5.6, 0.75, size=11, color=WHITE)
    ty3 += 1.4

# ══════════════════════════════════════════════════════════════════════════════
#  SLIDE 10 – Live Demo Results
# ══════════════════════════════════════════════════════════════════════════════
s = prs.slides.add_slide(BLANK)
set_bg(s)
rect(s, 0, 0, 13.33, 0.9, fill_color=CARD)
txt(s, "Live Demo Results", 0.4, 0.15, 9, 0.65, size=28, bold=True, color=PRIMARY)
rect(s, 0.4, 0.88, 1.9, 0.05, fill_color=PRIMARY)

# Results timeline
results = [
    (SUCCESS, "Phase 0 – Setup",
     "✓ aws sts get-caller-identity  →  Account 183833977366\n"
     "✓ LabRole ARN retrieved\n"
     "✓ Local Gunicorn test: /health → 200 OK, /checkout → {status: order placed}"),
    (PRIMARY, "Phase 1 – Infrastructure",
     "✓ ALB DNS: cloudmart-alb-1239664865.us-east-1.elb.amazonaws.com\n"
     "✓ Instance i-082e42a58751fdaae became Healthy in <5 min\n"
     "✓ curl / → <h1>CloudMart</h1> … Served by: ip-172-31-33-14.ec2.internal"),
    (ACCENT,  "Phase 2 & 3 – Backend + Dashboard",
     "✓ cloudmart-api Lambda: Python 3.12, 256 MB – Active\n"
     "✓ cloudmart-loadgen Lambda: Python 3.12, 512 MB – Active\n"
     "✓ API Gateway: https://xdcqnoje72.execute-api.us-east-1.amazonaws.com"),
    (WARNING, "Phase 4 – Live Scaling Observed",
     "✓ 30-thread load test → CPU spiked to 100% across cluster\n"
     "✓ cloudmart-cpu-high alarm triggered → scale-out policy fired\n"
     "✓ New instance i-0a8a6e5580606d007 launched (us-east-1d, Healthy)\n"
     "✓ ALB traffic: 1,453 req/min across 2 instances simultaneously"),
]

ty2 = 1.05
for col, phase, detail in results:
    rect(s, 0.3, ty2, 12.7, 1.4, fill_color=CARD, line_color=col, line_w=Pt(1.5))
    rect(s, 0.3, ty2, 0.12, 1.4, fill_color=col)
    txt(s, phase,  0.5, ty2+0.1,  5.0, 0.4,  size=14, bold=True, color=col)
    txt(s, detail, 0.5, ty2+0.52, 12.3, 0.78, size=11.5, color=WHITE)
    ty2 += 1.5

# URLs block
rect(s, 0.3, 7.0, 12.7, 0.38, fill_color=RGBColor(0x14,0x20,0x33), line_color=BORDER, line_w=Pt(1))
txt(s, "Dashboard:  http://cloudmart-dash-183833977366.s3-website-us-east-1.amazonaws.com    "
       "│    Shop ALB:  http://cloudmart-alb-1239664865.us-east-1.elb.amazonaws.com",
    0.5, 7.03, 12.3, 0.35, size=11, color=PRIMARY, align=PP_ALIGN.CENTER)

# ══════════════════════════════════════════════════════════════════════════════
#  SLIDE 11 – Summary & Viva Prep
# ══════════════════════════════════════════════════════════════════════════════
s = prs.slides.add_slide(BLANK)
set_bg(s)
rect(s, 0, 0, 13.33, 0.9, fill_color=CARD)
txt(s, "Summary & Viva Preparation", 0.4, 0.15, 9, 0.65, size=28, bold=True, color=PRIMARY)
rect(s, 0.4, 0.88, 2.8, 0.05, fill_color=PRIMARY)

rect(s, 0.3, 1.1, 6.2, 5.9, fill_color=CARD, line_color=PRIMARY, line_w=Pt(1.5))
txt(s, "What We Built", 0.5, 1.2, 5.8, 0.4, size=16, bold=True, color=PRIMARY)
bullets(s, [
    "Public-facing Flask e-commerce shop on EC2 (AL2023 + Gunicorn)",
    "Multi-AZ Auto Scaling Group (Min 1, Max 4) with ELB health checks",
    "Application Load Balancer distributing live HTTP traffic",
    "CloudWatch alarms driving automatic +1 / -1 simple scaling policies",
    "Serverless API (Lambda + API Gateway) aggregating live metrics",
    "Synthetic load generator Lambda for on-demand traffic spikes",
    "Dark-mode live dashboard with Chart.js, CPU gauge, and instance tiles",
    "Idempotent infra.py and deploy.py scripts for repeatability",
], 0.5, 1.75, 5.8, 5.0, size=13, color=WHITE, bullet_color=PRIMARY)

rect(s, 6.8, 1.1, 6.2, 5.9, fill_color=CARD, line_color=WARNING, line_w=Pt(1.5))
txt(s, "Expected Viva Questions", 7.0, 1.2, 5.8, 0.4, size=16, bold=True, color=WARNING)
qas = [
    ("Why use an ASG and not just one EC2?",
     "Single point of failure. ASG replaces failed instances\nautomatically and scales under traffic."),
    ("What is the ALB health check?",
     "Hits GET /health every 15 s. If 2 consecutive\nchecks fail, the instance is deregistered."),
    ("Why Lambda for the API and not EC2?",
     "No idle cost, auto-scales to zero, no server management."),
    ("What triggers scale-out?",
     "CloudWatch alarm: avg CPU > 50% for 2 consecutive\n60-second periods fires cloudmart-scale-out (+1)."),
    ("What is ELB health check type in ASG?",
     "ELB health check; instance must pass both EC2 status\nchecks AND the ALB target health check."),
]
ty3 = 1.75
for q, a in qas:
    txt(s, f"Q: {q}", 7.0, ty3, 5.8, 0.38, size=12, bold=True, color=WARNING)
    txt(s, f"A: {a}", 7.0, ty3+0.38, 5.8, 0.6, size=11, color=WHITE)
    ty3 += 1.08

# ══════════════════════════════════════════════════════════════════════════════
#  SLIDE 12 – Thank You
# ══════════════════════════════════════════════════════════════════════════════
s = prs.slides.add_slide(BLANK)
set_bg(s)

rect(s, 0, 0, 0.08, 7.5, fill_color=SUCCESS)
c3 = s.shapes.add_shape(9, Inches(-1.5), Inches(-1.5), Inches(5), Inches(5))
c3.fill.solid(); c3.fill.fore_color.rgb = RGBColor(0x0C,0x2E,0x24)
c3.line.fill.background()
c4 = s.shapes.add_shape(9, Inches(10), Inches(5), Inches(4), Inches(4))
c4.fill.solid(); c4.fill.fore_color.rgb = RGBColor(0x1E,0x3A,0x8A)
c4.line.fill.background()

txt(s, "Thank You", 0.5, 2.0, 12, 1.4, size=60, bold=True, color=SUCCESS, align=PP_ALIGN.CENTER)
txt(s, "CloudMart Auto-Scaling Dashboard", 0.5, 3.4, 12, 0.65, size=22, color=WHITE, align=PP_ALIGN.CENTER)
rect(s, 4.0, 4.1, 5.33, 0.04, fill_color=SUCCESS)

txt(s, "Dashboard URL", 2.5, 4.3, 3.5, 0.4, size=12, bold=True, color=MUTED, align=PP_ALIGN.RIGHT)
txt(s, "http://cloudmart-dash-183833977366.s3-website-us-east-1.amazonaws.com",
    6.2, 4.3, 6.9, 0.4, size=12, color=PRIMARY)
txt(s, "Shop ALB URL", 2.5, 4.85, 3.5, 0.4, size=12, bold=True, color=MUTED, align=PP_ALIGN.RIGHT)
txt(s, "http://cloudmart-alb-1239664865.us-east-1.elb.amazonaws.com",
    6.2, 4.85, 6.9, 0.4, size=12, color=PRIMARY)
txt(s, "API Gateway", 2.5, 5.4, 3.5, 0.4, size=12, bold=True, color=MUTED, align=PP_ALIGN.RIGHT)
txt(s, "https://xdcqnoje72.execute-api.us-east-1.amazonaws.com",
    6.2, 5.4, 6.9, 0.4, size=12, color=PRIMARY)
txt(s, "Source Code", 2.5, 5.95, 3.5, 0.4, size=12, bold=True, color=MUTED, align=PP_ALIGN.RIGHT)
txt(s, "/Users/showryabhanu/Desktop/cloudmart-dashboard/",
    6.2, 5.95, 6.9, 0.4, size=12, color=PRIMARY)

txt(s, "Built with:  EC2  ·  Auto Scaling  ·  ALB  ·  CloudWatch  ·  Lambda  ·  API Gateway  ·  S3  ·  SSM",
    0.5, 7.0, 12.33, 0.38, size=12, color=MUTED, align=PP_ALIGN.CENTER)

# ── Save ─────────────────────────────────────────────────────────────────────
OUT = "CloudMart_Auto_Scaling_Dashboard.pptx"
prs.save(OUT)
print(f"Saved: {OUT}")
print(f"Slides: {len(prs.slides)}")
