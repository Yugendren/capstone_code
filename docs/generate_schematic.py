#!/usr/bin/env python3
"""
Industry-standard electrical schematic for 40x30 Pressure Sensor Matrix.
Uses matplotlib for precise control over layout, symbols, and wiring.
Multi-page PDF: Page 1 = MCU + bus, Page 2 = 595 cascade, Page 3 = MUX + sensing.
Proper IEEE/IEC symbols, real wire routing, no overlapping text.
"""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.backends.backend_pdf import PdfPages
import numpy as np
from datetime import date

# ── Global Style ──────────────────────────────────────────────────────────
WIRE_LW = 0.9
COMP_LW = 1.0
WIRE_COLOR = '#000000'
POWER_COLOR = '#CC0000'
GND_COLOR = '#000000'
BG = '#FFFFFF'
NET_COLOR = '#0055AA'
REF_COLOR = '#CC0000'
VALUE_COLOR = '#006600'
PIN_FONT = 7
LABEL_FONT = 7
NET_FONT = 7.5
TITLE_FONT = 11
SMALL_FONT = 5.5

def setup_page(fig, ax, page_w, page_h):
    ax.set_xlim(0, page_w)
    ax.set_ylim(0, page_h)
    ax.set_aspect('equal')
    ax.axis('off')
    fig.patch.set_facecolor(BG)
    # Border
    border = patches.Rectangle((0.3, 0.3), page_w - 0.6, page_h - 0.6,
                                linewidth=2, edgecolor='#000', facecolor='none', zorder=0)
    ax.add_patch(border)

def draw_title_block(ax, page_w, page_h, sheet_num, total_sheets, subtitle=''):
    bx = page_w - 6.5
    by = 0.4
    bw = 6.0
    bh = 1.6
    rect = patches.Rectangle((bx, by), bw, bh, linewidth=1.2,
                              edgecolor='#000', facecolor='#FAFAFA', zorder=10)
    ax.add_patch(rect)
    # Horizontal lines
    ax.plot([bx, bx+bw], [by+1.1, by+1.1], color='#000', lw=0.6, zorder=10)
    ax.plot([bx, bx+bw], [by+0.55, by+0.55], color='#000', lw=0.6, zorder=10)
    # Vertical line
    ax.plot([bx+3, bx+3], [by, by+1.1], color='#000', lw=0.6, zorder=10)

    ax.text(bx+bw/2, by+1.35, '40x30 PRESSURE SENSOR MATRIX', ha='center',
            fontsize=9, fontweight='bold', zorder=11)
    if subtitle:
        ax.text(bx+bw/2, by+1.15, subtitle, ha='center', fontsize=6, zorder=11)

    ax.text(bx+0.1, by+0.85, f'Date: {date.today().isoformat()}', fontsize=SMALL_FONT, zorder=11)
    ax.text(bx+0.1, by+0.65, f'Rev: 1.0', fontsize=SMALL_FONT, zorder=11)
    ax.text(bx+3.1, by+0.85, f'Sheet: {sheet_num} of {total_sheets}', fontsize=SMALL_FONT, zorder=11)
    ax.text(bx+3.1, by+0.65, 'ESP32-S3 Breadboard Prototype', fontsize=SMALL_FONT, zorder=11)

    ax.text(bx+0.1, by+0.35, 'Components:', fontsize=SMALL_FONT, fontweight='bold', zorder=11)
    ax.text(bx+0.1, by+0.15, 'U1: ESP32-S3  U2-U6: SN74HC595N', fontsize=4.5, zorder=11)
    ax.text(bx+0.1, by+0.02, 'U7-U8: CD74HC4067  D1-D40: 1N4148TA', fontsize=4.5, zorder=11)
    ax.text(bx+3.1, by+0.15, 'R1-R2: 10K  J1: FFC-40  J2: FFC-30', fontsize=4.5, zorder=11)

# ── Symbol Drawing Functions ──────────────────────────────────────────────

def draw_wire(ax, x1, y1, x2, y2, color=WIRE_COLOR):
    ax.plot([x1, x2], [y1, y2], color=color, linewidth=WIRE_LW, solid_capstyle='round', zorder=2)

def draw_wire_path(ax, points, color=WIRE_COLOR):
    for i in range(len(points)-1):
        draw_wire(ax, points[i][0], points[i][1], points[i+1][0], points[i+1][1], color)

def draw_junction(ax, x, y):
    ax.plot(x, y, 'o', color=WIRE_COLOR, markersize=3.5, zorder=6, markeredgewidth=0)

def draw_no_connect(ax, x, y, size=0.12):
    ax.plot([x-size, x+size], [y-size, y+size], color='#CC0000', lw=1.2, zorder=5)
    ax.plot([x-size, x+size], [y+size, y-size], color='#CC0000', lw=1.2, zorder=5)

def draw_gnd_symbol(ax, x, y):
    """IEEE standard ground: 3 decreasing horizontal bars."""
    draw_wire(ax, x, y, x, y-0.15)
    for i, (hw, dy) in enumerate([(0.18, -0.15), (0.12, -0.22), (0.06, -0.29)]):
        ax.plot([x-hw, x+hw], [y+dy, y+dy], color=GND_COLOR, lw=max(1.4-i*0.3, 0.6), zorder=5)

def draw_vcc_symbol(ax, x, y, label='3.3V'):
    """Power rail: upward bar with label."""
    draw_wire(ax, x, y, x, y+0.2)
    ax.plot([x-0.15, x+0.15], [y+0.2, y+0.2], color=POWER_COLOR, lw=1.5, zorder=5)
    ax.text(x, y+0.32, label, ha='center', va='bottom', fontsize=SMALL_FONT,
            fontweight='bold', color=POWER_COLOR, zorder=5)

def draw_resistor(ax, x, y, length=1.0, orientation='v', ref='R1', value='10K'):
    """IEEE rectangle resistor symbol. Returns (start, end) coordinates."""
    body_len = 0.5
    lead = (length - body_len) / 2
    if orientation == 'v':
        # Vertical: start at top (x,y), goes down
        p1 = (x, y)
        p2 = (x, y - length)
        by = y - lead
        rect = patches.Rectangle((x-0.08, by - body_len), 0.16, body_len,
                                  lw=COMP_LW, edgecolor='#000', facecolor=BG, zorder=4)
        ax.add_patch(rect)
        draw_wire(ax, x, y, x, by)
        draw_wire(ax, x, by - body_len, x, y - length)
        ax.text(x+0.2, y - length/2, ref, ha='left', va='center', fontsize=SMALL_FONT,
                fontweight='bold', color=REF_COLOR, zorder=5)
        ax.text(x-0.2, y - length/2, value, ha='right', va='center', fontsize=SMALL_FONT,
                color=VALUE_COLOR, zorder=5)
        return p1, p2
    else:
        # Horizontal: start at left (x,y), goes right
        p1 = (x, y)
        p2 = (x + length, y)
        bx = x + lead
        rect = patches.Rectangle((bx, y-0.08), body_len, 0.16,
                                  lw=COMP_LW, edgecolor='#000', facecolor=BG, zorder=4)
        ax.add_patch(rect)
        draw_wire(ax, x, y, bx, y)
        draw_wire(ax, bx + body_len, y, x + length, y)
        ax.text(x + length/2, y+0.2, ref, ha='center', va='bottom', fontsize=SMALL_FONT,
                fontweight='bold', color=REF_COLOR, zorder=5)
        ax.text(x + length/2, y-0.2, value, ha='center', va='top', fontsize=SMALL_FONT,
                color=VALUE_COLOR, zorder=5)
        return p1, p2

def draw_diode(ax, x1, y1, x2, y2, ref=''):
    """Standard diode symbol. Anode at (x1,y1), cathode at (x2,y2). Horizontal only."""
    mx = (x1 + x2) / 2
    my = (y1 + y2) / 2
    tri_w = 0.15
    tri_h = 0.1

    # Lead wires
    draw_wire(ax, x1, y1, mx - tri_w, my)
    draw_wire(ax, mx + tri_w, my, x2, y2)

    # Triangle (anode side)
    tri = plt.Polygon([(mx-tri_w, my-tri_h), (mx-tri_w, my+tri_h), (mx+tri_w, my)],
                      closed=True, facecolor='#000', edgecolor='#000', lw=0.6, zorder=4)
    ax.add_patch(tri)
    # Cathode bar
    ax.plot([mx+tri_w, mx+tri_w], [my-tri_h, my+tri_h], color='#000', lw=1.5, zorder=4)

    if ref:
        ax.text(mx, my+0.18, ref, ha='center', va='bottom', fontsize=4.5,
                color=REF_COLOR, zorder=5)

def draw_net_label(ax, x, y, text, anchor='left'):
    """Net label with flag shape."""
    ha = 'left' if anchor == 'left' else 'right'
    ax.text(x, y, text, ha=ha, va='center', fontsize=NET_FONT,
            fontweight='bold', color=NET_COLOR, zorder=6,
            bbox=dict(boxstyle='round,pad=0.08', facecolor='#EDF4FF',
                      edgecolor=NET_COLOR, linewidth=0.5, alpha=0.9))

def draw_ic_block(ax, x, y, w, h, name, ref, left_pins, right_pins,
                  pin_spacing=0.45, pkg='', top_pins=None, bot_pins=None):
    """
    Draw a proper IC block with evenly spaced pins.
    left_pins/right_pins: list of (pin_num, pin_name)
    Returns dict: pin_name -> (wire_end_x, wire_end_y)
    """
    lead_len = 0.4

    # IC body
    rect = patches.FancyBboxPatch((x, y), w, h, boxstyle="square,pad=0",
                                   lw=COMP_LW, edgecolor='#000', facecolor=BG, zorder=3)
    ax.add_patch(rect)

    # Notch at top
    notch_r = 0.12
    notch = patches.Arc((x + w/2, y + h), notch_r*2, notch_r*2, angle=0,
                        theta1=180, theta2=360, lw=0.8, edgecolor='#000', zorder=4)
    ax.add_patch(notch)

    # IC name + ref
    ax.text(x + w/2, y + h/2 + 0.15, name, ha='center', va='center',
            fontsize=7, fontweight='bold', zorder=4)
    ax.text(x + w/2, y + h/2 - 0.15, ref, ha='center', va='center',
            fontsize=6, color=REF_COLOR, fontweight='bold', zorder=4)
    if pkg:
        ax.text(x + w/2, y - 0.12, pkg, ha='center', va='top',
                fontsize=4.5, color='#888', zorder=4)

    pin_coords = {}

    # Left pins: evenly spaced, top to bottom
    n_left = len(left_pins)
    total_pin_height = (n_left - 1) * pin_spacing
    start_y = y + h/2 + total_pin_height/2

    for i, (pnum, pname) in enumerate(left_pins):
        py = start_y - i * pin_spacing
        # Pin stub
        draw_wire(ax, x - lead_len, py, x, py)
        # Pin number (outside, near stub end)
        ax.text(x + 0.06, py, str(pnum), ha='left', va='center',
                fontsize=4.5, color='#666', zorder=4)
        # Pin name (inside)
        ax.text(x + 0.3, py, pname, ha='left', va='center',
                fontsize=PIN_FONT, zorder=4)
        pin_coords[pname] = (x - lead_len, py)

    # Right pins
    n_right = len(right_pins)
    total_pin_height = (n_right - 1) * pin_spacing
    start_y = y + h/2 + total_pin_height/2

    for i, (pnum, pname) in enumerate(right_pins):
        py = start_y - i * pin_spacing
        draw_wire(ax, x + w, py, x + w + lead_len, py)
        ax.text(x + w - 0.06, py, str(pnum), ha='right', va='center',
                fontsize=4.5, color='#666', zorder=4)
        ax.text(x + w - 0.3, py, pname, ha='right', va='center',
                fontsize=PIN_FONT, zorder=4)
        pin_coords[pname] = (x + w + lead_len, py)

    return pin_coords


# ══════════════════════════════════════════════════════════════════════════
# PAGE DIMENSIONS (11x8.5 landscape, in inches scaled to coordinate units)
# ══════════════════════════════════════════════════════════════════════════
PW = 20  # page width in units
PH = 14  # page height in units

output_path = '/mnt/c/Users/19thk/Capstone/capstone_esp32/docs/schematic_40x30_pressure_matrix.pdf'

with PdfPages(output_path) as pdf:

    # ══════════════════════════════════════════════════════════════════════
    # PAGE 1: MCU + POWER + BUS CONNECTIONS
    # ══════════════════════════════════════════════════════════════════════
    fig1, ax1 = plt.subplots(1, 1, figsize=(20, 14), dpi=150)
    setup_page(fig1, ax1, PW, PH)

    ax1.text(PW/2, PH - 0.7, 'SHEET 1 — MCU, POWER DISTRIBUTION, BUS CONNECTIONS',
             ha='center', fontsize=TITLE_FONT, fontweight='bold',
             bbox=dict(boxstyle='round,pad=0.3', facecolor='#E8E8E8', edgecolor='#999'))

    # ── ESP32-S3 ──────────────────────────────────────────────────────────
    esp_x, esp_y = 2.5, 4.5
    esp_w, esp_h = 3.0, 7.0

    esp_left = [
        ('11', 'IO11'),
        ('12', 'IO12'),
        ('13', 'IO13'),
        ('4',  'IO4'),
        ('5',  'IO5'),
        ('6',  'IO6'),
        ('7',  'IO7'),
        ('9',  'IO9'),
        ('10', 'IO10'),
    ]
    esp_right = [
        ('', '3V3'),
        ('', 'GND'),
        ('', 'USB'),
        ('', '5V'),
        ('', 'EN'),
    ]

    esp_pins = draw_ic_block(ax1, esp_x, esp_y, esp_w, esp_h,
                             'ESP32-S3-WROOM-1', 'U1',
                             esp_left, esp_right,
                             pin_spacing=0.7, pkg='N16R8  (16MB Flash, 8MB PSRAM)')

    # Power on right side of ESP32
    vcc_x, vcc_y = esp_pins['3V3']
    draw_wire(ax1, vcc_x, vcc_y, vcc_x + 0.5, vcc_y)
    draw_vcc_symbol(ax1, vcc_x + 0.5, vcc_y, '3.3V')

    gnd_x, gnd_y = esp_pins['GND']
    draw_wire(ax1, gnd_x, gnd_y, gnd_x + 0.5, gnd_y)
    draw_gnd_symbol(ax1, gnd_x + 0.5, gnd_y)

    # USB label
    usb_x, usb_y = esp_pins['USB']
    draw_wire(ax1, usb_x, usb_y, usb_x + 0.8, usb_y)
    ax1.text(usb_x + 0.9, usb_y, 'USB-C (Native)\nVID:PID 303a:1001',
             ha='left', va='center', fontsize=SMALL_FONT, color='#444', zorder=5)

    # 5V
    v5_x, v5_y = esp_pins['5V']
    draw_wire(ax1, v5_x, v5_y, v5_x + 0.5, v5_y)
    draw_vcc_symbol(ax1, v5_x + 0.5, v5_y, '5V (USB)')

    # EN - no connect
    en_x, en_y = esp_pins['EN']
    draw_no_connect(ax1, en_x, en_y)

    # ── LEFT SIDE: Net labels from ESP32 GPIO ─────────────────────────────
    # SPI bus
    io11_x, io11_y = esp_pins['IO11']
    draw_wire(ax1, io11_x, io11_y, io11_x - 1.0, io11_y)
    draw_net_label(ax1, io11_x - 1.05, io11_y, 'SPI_MOSI', anchor='right')
    ax1.text(io11_x - 0.5, io11_y + 0.15, 'HW SPI 10MHz', ha='center',
             fontsize=4, color='#888', zorder=5)

    io12_x, io12_y = esp_pins['IO12']
    draw_wire(ax1, io12_x, io12_y, io12_x - 1.0, io12_y)
    draw_net_label(ax1, io12_x - 1.05, io12_y, 'SPI_SCK', anchor='right')

    io13_x, io13_y = esp_pins['IO13']
    draw_wire(ax1, io13_x, io13_y, io13_x - 1.0, io13_y)
    draw_net_label(ax1, io13_x - 1.05, io13_y, 'RCLK', anchor='right')
    ax1.text(io13_x - 0.5, io13_y + 0.15, 'GPIO toggle', ha='center',
             fontsize=4, color='#888', zorder=5)

    # MUX select lines
    for pin_name, net_name in [('IO4', 'MUX_S0'), ('IO5', 'MUX_S1'),
                                ('IO6', 'MUX_S2'), ('IO7', 'MUX_S3')]:
        px, py = esp_pins[pin_name]
        draw_wire(ax1, px, py, px - 1.0, py)
        draw_net_label(ax1, px - 1.05, py, net_name, anchor='right')

    # ADC lines
    io9_x, io9_y = esp_pins['IO9']
    draw_wire(ax1, io9_x, io9_y, io9_x - 1.0, io9_y)
    draw_net_label(ax1, io9_x - 1.05, io9_y, 'MUX1_SIG', anchor='right')
    ax1.text(io9_x - 0.5, io9_y + 0.15, 'ADC1_CH8', ha='center',
             fontsize=4, color='#888', zorder=5)

    io10_x, io10_y = esp_pins['IO10']
    draw_wire(ax1, io10_x, io10_y, io10_x - 1.0, io10_y)
    draw_net_label(ax1, io10_x - 1.05, io10_y, 'MUX2_SIG', anchor='right')
    ax1.text(io10_x - 0.5, io10_y + 0.15, 'ADC1_CH9', ha='center',
             fontsize=4, color='#888', zorder=5)

    # ── BUS SUMMARY TABLE ─────────────────────────────────────────────────
    table_x, table_y = 9.0, 8.5
    table_w, table_h = 9.5, 4.5
    trect = patches.FancyBboxPatch((table_x, table_y), table_w, table_h,
                                    boxstyle="round,pad=0.1", lw=0.8,
                                    edgecolor='#555', facecolor='#FAFAFA', zorder=3)
    ax1.add_patch(trect)
    ax1.text(table_x + table_w/2, table_y + table_h - 0.3,
             'GPIO PIN ASSIGNMENT & BUS ROUTING', ha='center',
             fontsize=8, fontweight='bold', zorder=4)

    # Header line
    hy = table_y + table_h - 0.65
    ax1.plot([table_x+0.2, table_x+table_w-0.2], [hy, hy], color='#999', lw=0.5, zorder=4)
    headers = ['GPIO', 'Net Name', 'Function', 'Destination']
    hx_positions = [table_x+0.3, table_x+1.3, table_x+3.3, table_x+6.5]
    for hx, ht in zip(hx_positions, headers):
        ax1.text(hx, hy+0.15, ht, fontsize=SMALL_FONT, fontweight='bold', zorder=4)

    pin_rows = [
        ('IO11', 'SPI_MOSI', 'SPI Master Out', 'U2 pin 14 (SER) — cascades to U3-U6'),
        ('IO12', 'SPI_SCK',  'SPI Clock',      'U2-U6 pin 11 (SRCLK) — parallel'),
        ('IO13', 'RCLK',     'Latch (GPIO)',    'U2-U6 pin 12 (RCLK) — parallel'),
        ('IO4',  'MUX_S0',   'MUX Select bit 0','U7+U8 S0 — parallel'),
        ('IO5',  'MUX_S1',   'MUX Select bit 1','U7+U8 S1 — parallel'),
        ('IO6',  'MUX_S2',   'MUX Select bit 2','U7+U8 S2 — parallel'),
        ('IO7',  'MUX_S3',   'MUX Select bit 3','U7+U8 S3 — parallel'),
        ('IO9',  'MUX1_SIG', 'ADC1_CH8 input',  'U7 SIG (Columns 0-14)'),
        ('IO10', 'MUX2_SIG', 'ADC1_CH9 input',  'U8 SIG (Columns 15-29)'),
    ]
    for i, (gpio, net, func, dest) in enumerate(pin_rows):
        ry = hy - 0.35 - i * 0.35
        ax1.text(hx_positions[0], ry, gpio, fontsize=SMALL_FONT, fontfamily='monospace', zorder=4)
        ax1.text(hx_positions[1], ry, net, fontsize=SMALL_FONT, fontweight='bold',
                 color=NET_COLOR, zorder=4)
        ax1.text(hx_positions[2], ry, func, fontsize=SMALL_FONT, zorder=4)
        ax1.text(hx_positions[3], ry, dest, fontsize=5, color='#444', zorder=4)

    # ── POWER DISTRIBUTION ────────────────────────────────────────────────
    pwr_x, pwr_y = 9.0, 4.5
    pwr_w, pwr_h = 9.5, 3.5
    prect = patches.FancyBboxPatch((pwr_x, pwr_y), pwr_w, pwr_h,
                                    boxstyle="round,pad=0.1", lw=0.8,
                                    edgecolor='#555', facecolor='#FAFAF0', zorder=3)
    ax1.add_patch(prect)
    ax1.text(pwr_x + pwr_w/2, pwr_y + pwr_h - 0.3,
             'POWER DISTRIBUTION (3.3V RAIL)', ha='center',
             fontsize=8, fontweight='bold', zorder=4)

    # 3.3V rail - horizontal bus bar
    rail_y = pwr_y + pwr_h - 0.9
    rail_x1 = pwr_x + 0.5
    rail_x2 = pwr_x + pwr_w - 0.5
    draw_wire(ax1, rail_x1, rail_y, rail_x2, rail_y, color=POWER_COLOR)
    draw_vcc_symbol(ax1, rail_x1, rail_y, '3.3V')

    # Components on rail
    comp_labels = ['U1\nESP32', 'U2\n595', 'U3\n595', 'U4\n595', 'U5\n595', 'U6\n595', 'U7\nMUX', 'U8\nMUX']
    spacing = (rail_x2 - rail_x1 - 1.0) / (len(comp_labels) - 1)
    for i, label in enumerate(comp_labels):
        cx = rail_x1 + 0.5 + i * spacing
        draw_junction(ax1, cx, rail_y)
        draw_wire(ax1, cx, rail_y, cx, rail_y - 0.4)
        ax1.text(cx, rail_y - 0.55, label, ha='center', va='top',
                 fontsize=5, fontweight='bold', zorder=4)
        # VCC pin label
        ax1.text(cx, rail_y - 1.1, 'VCC', ha='center', va='top', fontsize=4.5, color='#666', zorder=4)
        # GND below
        draw_wire(ax1, cx, rail_y - 1.3, cx, rail_y - 1.6)
        draw_gnd_symbol(ax1, cx, rail_y - 1.6)
        ax1.text(cx, rail_y - 1.35, 'GND', ha='center', va='bottom', fontsize=4.5, color='#666', zorder=4)

    # Power notes
    pnotes = [
        'All ICs: VCC = 3.3V, GND = 0V',
        '595 pin 10 (SRCLR) tied to 3.3V (clear disabled)',
        '595 pin 13 (OE) tied to GND (outputs enabled)',
        'MUX EN pin tied to GND (always enabled)',
    ]
    for i, note in enumerate(pnotes):
        ax1.text(pwr_x + 0.4, pwr_y + 0.95 - i*0.22, f'{i+1}. {note}',
                 fontsize=5, color='#333', zorder=4)

    draw_title_block(ax1, PW, PH, 1, 3, 'MCU + Power + Bus')
    fig1.tight_layout(pad=0.5)
    pdf.savefig(fig1, dpi=150)
    plt.close(fig1)

    # ══════════════════════════════════════════════════════════════════════
    # PAGE 2: 595 CASCADE + DIODE ARRAY
    # ══════════════════════════════════════════════════════════════════════
    fig2, ax2 = plt.subplots(1, 1, figsize=(20, 14), dpi=150)
    setup_page(fig2, ax2, PW, PH)

    ax2.text(PW/2, PH - 0.7, 'SHEET 2 — 74HC595 SHIFT REGISTER CASCADE + DIODE ARRAY (ACTIVE-HIGH ROW DRIVE)',
             ha='center', fontsize=TITLE_FONT-1, fontweight='bold',
             bbox=dict(boxstyle='round,pad=0.3', facecolor='#E8E8E8', edgecolor='#999'))

    # Draw 5 shift registers side by side
    sr_w = 2.2
    sr_h = 5.5
    sr_spacing = 3.6
    sr_y_base = 5.5

    for idx in range(5):
        sr_x = 0.8 + idx * sr_spacing
        chip_num = idx + 1

        left_pins = [
            (14, 'SER'),
            (11, 'SRCLK'),
            (12, 'RCLK'),
            (10, 'SRCLR'),
            (13, 'OE'),
            (16, 'VCC'),
            (8,  'GND'),
        ]
        right_pins = [
            (15, 'Q0'),
            (1,  'Q1'),
            (2,  'Q2'),
            (3,  'Q3'),
            (4,  'Q4'),
            (5,  'Q5'),
            (6,  'Q6'),
            (7,  'Q7'),
            (9,  "Q7'"),
        ]

        pins = draw_ic_block(ax2, sr_x, sr_y_base, sr_w, sr_h,
                             'SN74HC595N', f'U{chip_num+1}',
                             left_pins, right_pins,
                             pin_spacing=0.55, pkg='DIP-16')

        # ── POWER ──
        vx, vy = pins['VCC']
        draw_wire(ax2, vx, vy, vx - 0.3, vy)
        draw_vcc_symbol(ax2, vx - 0.3, vy, '3.3V')

        gx, gy = pins['GND']
        draw_wire(ax2, gx, gy, gx - 0.3, gy)
        draw_gnd_symbol(ax2, gx - 0.3, gy)

        # SRCLR → VCC (tie high)
        sx, sy = pins['SRCLR']
        draw_wire(ax2, sx, sy, sx - 0.3, sy)
        draw_vcc_symbol(ax2, sx - 0.3, sy, '3.3V')

        # OE → GND (tie low)
        ox, oy = pins['OE']
        draw_wire(ax2, ox, oy, ox - 0.3, oy)
        draw_gnd_symbol(ax2, ox - 0.3, oy)

        # ── SER INPUT ──
        ser_x, ser_y = pins['SER']
        if chip_num == 1:
            # First chip: SER from SPI_MOSI
            draw_wire(ax2, ser_x, ser_y, ser_x - 0.8, ser_y)
            draw_net_label(ax2, ser_x - 0.85, ser_y, 'SPI_MOSI', anchor='right')
        else:
            # Cascade: SER from previous Q7'
            draw_wire(ax2, ser_x, ser_y, ser_x - 0.5, ser_y)
            # This wire comes from the previous chip's Q7' — draw connection
            prev_q7_x = 0.8 + (idx-1) * sr_spacing + sr_w + 0.4
            prev_q7_y = pins["Q7'"][1]  # same row position
            # Route: down from Q7' of prev, across, up to SER of current
            mid_y = sr_y_base - 0.5
            draw_wire_path(ax2, [
                (prev_q7_x, prev_q7_y),
                (prev_q7_x, mid_y),
                (ser_x - 0.5, mid_y),
                (ser_x - 0.5, ser_y),
                (ser_x, ser_y)
            ])
            # Label the cascade net
            ax2.text((prev_q7_x + ser_x - 0.5)/2, mid_y - 0.15,
                     f"Q7'_U{chip_num}", ha='center', fontsize=5,
                     color=NET_COLOR, fontweight='bold', zorder=5)

        # ── SRCLK ──
        ck_x, ck_y = pins['SRCLK']
        draw_wire(ax2, ck_x, ck_y, ck_x - 0.8, ck_y)
        draw_net_label(ax2, ck_x - 0.85, ck_y, 'SPI_SCK', anchor='right')

        # ── RCLK ──
        rx, ry = pins['RCLK']
        draw_wire(ax2, rx, ry, rx - 0.6, ry)
        draw_net_label(ax2, rx - 0.65, ry, 'RCLK', anchor='right')

        # ── Q7' OUTPUT (last chip has no cascade) ──
        q7p_x, q7p_y = pins["Q7'"]
        if chip_num == 5:
            draw_no_connect(ax2, q7p_x, q7p_y)

        # ── OUTPUT PINS Q0-Q7 → DIODE → ROW ──
        row_base = idx * 8
        for bit in range(8):
            qx, qy = pins[f'Q{bit}']
            row_num = row_base + bit
            diode_ref = f'D{row_num + 1}'

            # Wire from Q output, then diode, then row label
            d_start = qx + 0.1
            d_end = d_start + 0.6
            draw_diode(ax2, d_start, qy, d_end, qy, ref=diode_ref)

            # Row net label after diode
            draw_wire(ax2, d_end, qy, d_end + 0.3, qy)
            ax2.text(d_end + 0.35, qy, f'ROW_{row_num}', ha='left', va='center',
                     fontsize=5, fontweight='bold', color=VALUE_COLOR, zorder=5)
            # FFC pin
            ax2.text(d_end + 1.5, qy, f'→ J1 pin {row_num+1}', ha='left', va='center',
                     fontsize=4, color='#888', zorder=5)

    # ── SPI BUFFER NOTE ───────────────────────────────────────────────────
    note_x, note_y = 0.8, 2.5
    note_w, note_h = 18.0, 2.5
    nrect = patches.FancyBboxPatch((note_x, note_y), note_w, note_h,
                                    boxstyle="round,pad=0.1", lw=0.6,
                                    edgecolor='#555', facecolor='#FFFFF8', zorder=3)
    ax2.add_patch(nrect)
    ax2.text(note_x + 0.3, note_y + note_h - 0.3, 'NOTES — 595 CASCADE OPERATION',
             fontsize=7, fontweight='bold', zorder=4)

    notes_text = [
        '1. SPI sends MSB first.  Buffer layout: buf[0] = U6 (farthest, rows 32-39),  buf[4] = U2 (closest, rows 0-7)',
        '2. Row select formula:  chip = row / 8,   bit = row % 8,   buf[NUM_595 - 1 - chip] = (1 << bit)',
        '3. Only ONE row driven HIGH at a time. All other 595 outputs = LOW.',
        '4. Diodes D1-D40 (1N4148TA): Anode (no band) faces 595 output, Cathode (band) faces FFC row pin.',
        '   Purpose: prevent ghosting / sneak current paths through the resistive velostat matrix.',
        '5. After SPI transfer of 5 bytes: toggle RCLK (IO13) HIGH then LOW to latch all outputs simultaneously.',
        '6. 595 pin 10 (SRCLR) = 3.3V (clear disabled),  pin 13 (OE) = GND (outputs always enabled).',
    ]
    for i, nt in enumerate(notes_text):
        ax2.text(note_x + 0.3, note_y + note_h - 0.65 - i * 0.28, nt,
                 fontsize=5, fontfamily='monospace', color='#333', zorder=4)

    draw_title_block(ax2, PW, PH, 2, 3, '595 Cascade + Diode Array')
    fig2.tight_layout(pad=0.5)
    pdf.savefig(fig2, dpi=150)
    plt.close(fig2)

    # ══════════════════════════════════════════════════════════════════════
    # PAGE 3: MUX + PULLDOWNS + FFC + SENSING LAYER
    # ══════════════════════════════════════════════════════════════════════
    fig3, ax3 = plt.subplots(1, 1, figsize=(20, 14), dpi=150)
    setup_page(fig3, ax3, PW, PH)

    ax3.text(PW/2, PH - 0.7, 'SHEET 3 — COLUMN MUX READERS + FFC CONNECTORS + SENSING LAYER',
             ha='center', fontsize=TITLE_FONT-1, fontweight='bold',
             bbox=dict(boxstyle='round,pad=0.3', facecolor='#E8E8E8', edgecolor='#999'))

    # ── MUX 1 (U7) ───────────────────────────────────────────────────────
    for mux_idx in range(2):
        mux_x = 1.5 + mux_idx * 9.5
        mux_y = 3.0
        mux_w = 2.8
        mux_h = 9.0
        mux_num = mux_idx + 1
        ch_start = mux_idx * 15

        left_pins = [
            ('', 'S0'),
            ('', 'S1'),
            ('', 'S2'),
            ('', 'S3'),
            ('', 'EN'),
            ('', 'VCC'),
            ('', 'GND'),
            ('', 'SIG'),
        ]

        right_pins = []
        for ch in range(16):
            right_pins.append(('', f'CH{ch}'))

        pins = draw_ic_block(ax3, mux_x, mux_y, mux_w, mux_h,
                             'CD74HC4067', f'U{7 + mux_idx}',
                             left_pins, right_pins,
                             pin_spacing=0.52, pkg='16-CH MUX Breakout')

        # ── Power ──
        vx, vy = pins['VCC']
        draw_wire(ax3, vx, vy, vx - 0.3, vy)
        draw_vcc_symbol(ax3, vx - 0.3, vy, '3.3V')

        gx, gy = pins['GND']
        draw_wire(ax3, gx, gy, gx - 0.3, gy)
        draw_gnd_symbol(ax3, gx - 0.3, gy)

        # EN → GND
        ex, ey = pins['EN']
        draw_wire(ax3, ex, ey, ex - 0.3, ey)
        draw_gnd_symbol(ax3, ex - 0.3, ey)

        # ── Select lines ──
        for si in range(4):
            sx, sy = pins[f'S{si}']
            draw_wire(ax3, sx, sy, sx - 0.8, sy)
            draw_net_label(ax3, sx - 0.85, sy, f'MUX_S{si}', anchor='right')

        # ── SIG output with pulldown resistor ──
        sig_x, sig_y = pins['SIG']
        sig_net = f'MUX{mux_num}_SIG'

        # Wire left from SIG
        draw_wire(ax3, sig_x, sig_y, sig_x - 1.5, sig_y)
        draw_net_label(ax3, sig_x - 1.55, sig_y, sig_net, anchor='right')

        # Pulldown resistor: from SIG wire down to GND
        r_x = sig_x - 0.8
        draw_junction(ax3, r_x, sig_y)
        r_top, r_bot = draw_resistor(ax3, r_x, sig_y, length=1.2,
                                      orientation='v',
                                      ref=f'R{mux_num}', value='10K\u03A9')
        draw_gnd_symbol(ax3, r_x, r_bot[1])

        # ── Channel outputs → Column labels ──
        for ch in range(16):
            cx, cy = pins[f'CH{ch}']
            if ch < 15:
                col_num = ch_start + ch
                draw_wire(ax3, cx, cy, cx + 0.8, cy)
                ax3.text(cx + 0.85, cy, f'COL_{col_num}', ha='left', va='center',
                         fontsize=5, fontweight='bold', color=VALUE_COLOR, zorder=5)
                ax3.text(cx + 2.2, cy, f'J2 pin {col_num+1}', ha='left', va='center',
                         fontsize=4, color='#888', zorder=5)
            else:
                # CH15 unused
                draw_no_connect(ax3, cx, cy)
                ax3.text(cx + 0.3, cy, 'NC (unused)', ha='left', va='center',
                         fontsize=4.5, color='#999', zorder=5)

    # ── FFC CONNECTOR BLOCKS ──────────────────────────────────────────────
    # J1 - 40-pin (rows)
    j1_x, j1_y = 8.0, 10.5
    j1_w, j1_h = 2.5, 2.0
    j1rect = patches.FancyBboxPatch((j1_x, j1_y), j1_w, j1_h,
                                     boxstyle="round,pad=0.08", lw=1.2,
                                     edgecolor='#006600', facecolor='#F0FFF0', zorder=3)
    ax3.add_patch(j1rect)
    ax3.text(j1_x + j1_w/2, j1_y + j1_h - 0.25, 'J1', ha='center',
             fontsize=8, fontweight='bold', color=REF_COLOR, zorder=4)
    ax3.text(j1_x + j1_w/2, j1_y + j1_h - 0.6, 'FFC Breakout', ha='center',
             fontsize=6, zorder=4)
    ax3.text(j1_x + j1_w/2, j1_y + j1_h - 0.9, '40-pin, 1.0mm pitch', ha='center',
             fontsize=SMALL_FONT, color='#444', zorder=4)
    ax3.text(j1_x + j1_w/2, j1_y + j1_h/2 - 0.5, 'ROWS 0-39', ha='center',
             fontsize=7, fontweight='bold', color='#006600', zorder=4)
    ax3.text(j1_x + j1_w/2, j1_y + 0.15, 'Pin 1 = Row 0 ... Pin 40 = Row 39', ha='center',
             fontsize=4.5, color='#666', zorder=4)

    # Arrow: from 595 outputs to J1
    ax3.annotate('', xy=(j1_x, j1_y + j1_h/2),
                 xytext=(j1_x - 1.5, j1_y + j1_h/2),
                 arrowprops=dict(arrowstyle='->', color='#006600', lw=2), zorder=2)
    ax3.text(j1_x - 0.75, j1_y + j1_h/2 + 0.2, 'from 595\ndiode outputs\n(Sheet 2)',
             ha='center', va='bottom', fontsize=5, color='#006600', zorder=4)

    # J2 - 30-pin (columns)
    j2_x, j2_y = 8.0, 7.5
    j2_w, j2_h = 2.5, 2.0
    j2rect = patches.FancyBboxPatch((j2_x, j2_y), j2_w, j2_h,
                                     boxstyle="round,pad=0.08", lw=1.2,
                                     edgecolor='#0000AA', facecolor='#F0F0FF', zorder=3)
    ax3.add_patch(j2rect)
    ax3.text(j2_x + j2_w/2, j2_y + j2_h - 0.25, 'J2', ha='center',
             fontsize=8, fontweight='bold', color=REF_COLOR, zorder=4)
    ax3.text(j2_x + j2_w/2, j2_y + j2_h - 0.6, 'FFC Breakout', ha='center',
             fontsize=6, zorder=4)
    ax3.text(j2_x + j2_w/2, j2_y + j2_h - 0.9, '30-pin, 1.0mm pitch', ha='center',
             fontsize=SMALL_FONT, color='#444', zorder=4)
    ax3.text(j2_x + j2_w/2, j2_y + j2_h/2 - 0.5, 'COLS 0-29', ha='center',
             fontsize=7, fontweight='bold', color='#0000AA', zorder=4)
    ax3.text(j2_x + j2_w/2, j2_y + 0.15, 'Pin 1 = Col 0 ... Pin 30 = Col 29', ha='center',
             fontsize=4.5, color='#666', zorder=4)

    # Arrows: J2 to MUX inputs
    ax3.annotate('', xy=(j2_x, j2_y + j2_h/2 + 0.3),
                 xytext=(j2_x - 1.2, j2_y + j2_h/2 + 0.3),
                 arrowprops=dict(arrowstyle='<-', color='#0000AA', lw=1.5), zorder=2)
    ax3.text(j2_x - 0.6, j2_y + j2_h/2 + 0.55, 'to U7\nCH0-14',
             ha='center', fontsize=5, color='#0000AA', zorder=4)

    ax3.annotate('', xy=(j2_x + j2_w, j2_y + j2_h/2 + 0.3),
                 xytext=(j2_x + j2_w + 1.2, j2_y + j2_h/2 + 0.3),
                 arrowprops=dict(arrowstyle='<-', color='#0000AA', lw=1.5), zorder=2)
    ax3.text(j2_x + j2_w + 0.6, j2_y + j2_h/2 + 0.55, 'to U8\nCH0-14',
             ha='center', fontsize=5, color='#0000AA', zorder=4)

    # ── SENSING LAYER CROSS-SECTION ───────────────────────────────────────
    sl_x, sl_y = 6.5, 3.0
    sl_w, sl_h = 6.5, 3.8

    slrect = patches.FancyBboxPatch((sl_x, sl_y), sl_w, sl_h,
                                     boxstyle="round,pad=0.1", lw=1.0,
                                     edgecolor='#555', facecolor='#FAFAFA', zorder=3)
    ax3.add_patch(slrect)
    ax3.text(sl_x + sl_w/2, sl_y + sl_h - 0.25, 'SENSING LAYER CROSS-SECTION',
             ha='center', fontsize=8, fontweight='bold', zorder=4)

    # Layer stack with proper sizing
    layers = [
        ('30-pin Flex PCB (TOP)', '#8888DD', 'Copper face DOWN toward velostat', 'J2 columns'),
        ('Velostat Sheet', '#444444', 'Piezoresistive carbon-impregnated polymer', 'Variable R'),
        ('40-pin Flex PCB (BOTTOM)', '#88BB88', 'Copper face UP toward velostat', 'J1 rows'),
    ]
    for i, (name, color, desc, conn) in enumerate(layers):
        ly = sl_y + sl_h - 1.0 - i * 0.9
        lrect = patches.Rectangle((sl_x + 0.3, ly - 0.2), sl_w - 0.6, 0.4,
                                   facecolor=color, edgecolor='#333', lw=0.8,
                                   alpha=0.6, zorder=4)
        ax3.add_patch(lrect)
        tc = 'white' if i == 1 else '#000'
        ax3.text(sl_x + sl_w/2, ly, name, ha='center', va='center',
                 fontsize=6, fontweight='bold', color=tc, zorder=5)
        ax3.text(sl_x + sl_w/2, ly - 0.35, desc, ha='center', va='top',
                 fontsize=4.5, color='#555', zorder=5)
        ax3.text(sl_x + sl_w - 0.4, ly, conn, ha='right', va='center',
                 fontsize=4.5, color=tc, zorder=5)

    # Pressure arrows
    for px in [sl_x + 1.5, sl_x + sl_w/2, sl_x + sl_w - 1.5]:
        ax3.annotate('', xy=(px, sl_y + sl_h - 0.7),
                     xytext=(px, sl_y + sl_h - 0.45),
                     arrowprops=dict(arrowstyle='->', color='#CC6600', lw=1.5), zorder=5)
    ax3.text(sl_x + sl_w/2, sl_y + sl_h - 0.42, 'PRESSURE', ha='center',
             fontsize=5, fontweight='bold', color='#CC6600', zorder=5)

    # Matrix info
    ax3.text(sl_x + sl_w/2, sl_y + 0.55, '40 rows x 30 cols = 1,200 sensing intersections',
             ha='center', fontsize=6, fontweight='bold', color='#333', zorder=4)
    ax3.text(sl_x + sl_w/2, sl_y + 0.25,
             'Row pitch: 4mm (3mm trace, 1mm gap)    Col pitch: 5mm (4mm trace, 1mm gap)',
             ha='center', fontsize=5, color='#555', zorder=4)

    # ── EQUIVALENT CIRCUIT ────────────────────────────────────────────────
    eq_x, eq_y = 14.5, 3.0
    eq_w, eq_h = 5.0, 3.8
    eqrect = patches.FancyBboxPatch((eq_x, eq_y), eq_w, eq_h,
                                     boxstyle="round,pad=0.1", lw=1.0,
                                     edgecolor='#555', facecolor='#FFFFF8', zorder=3)
    ax3.add_patch(eqrect)
    ax3.text(eq_x + eq_w/2, eq_y + eq_h - 0.25, 'SINGLE CELL EQUIVALENT CIRCUIT',
             ha='center', fontsize=7, fontweight='bold', zorder=4)

    # Draw the equivalent circuit: 595 → diode → R_velostat → R_pulldown → GND
    #                                                          |
    #                                                        ADC_IN
    cy_mid = eq_y + eq_h/2

    # 595 output
    ax3.text(eq_x + 0.3, cy_mid + 0.6, '595 Qn', fontsize=6, fontweight='bold', zorder=4)
    draw_wire(ax3, eq_x + 0.3, cy_mid + 0.4, eq_x + 0.3, cy_mid)
    draw_wire(ax3, eq_x + 0.3, cy_mid, eq_x + 0.8, cy_mid)

    # Diode
    draw_diode(ax3, eq_x + 0.8, cy_mid, eq_x + 1.5, cy_mid, 'D')

    # R_velostat (variable)
    draw_wire(ax3, eq_x + 1.5, cy_mid, eq_x + 1.8, cy_mid)
    rv_start, rv_end = draw_resistor(ax3, eq_x + 1.8, cy_mid, length=1.2,
                                      orientation='h', ref='', value='R_velostat')
    # Diagonal arrow through resistor (variable)
    ax3.annotate('', xy=(eq_x + 2.85, cy_mid + 0.25),
                 xytext=(eq_x + 2.15, cy_mid - 0.25),
                 arrowprops=dict(arrowstyle='->', color='#CC6600', lw=1), zorder=5)

    # Junction point (ADC tap)
    jx = eq_x + 3.3
    draw_wire(ax3, rv_end[0], rv_end[1], jx, cy_mid)
    draw_junction(ax3, jx, cy_mid)

    # ADC label
    draw_wire(ax3, jx, cy_mid, jx + 1.0, cy_mid)
    ax3.text(jx + 1.1, cy_mid, 'ADC IN\n(IO9/IO10)', ha='left', va='center',
             fontsize=5.5, fontweight='bold', color=NET_COLOR, zorder=5)

    # R_pulldown to GND
    rp_top, rp_bot = draw_resistor(ax3, jx, cy_mid, length=1.2,
                                    orientation='v', ref='R1/R2', value='10K\u03A9')
    draw_gnd_symbol(ax3, jx, rp_bot[1])

    # Formula
    ax3.text(eq_x + eq_w/2, eq_y + 0.55,
             'V_adc = 2.6V  x  10K / (R_velostat + 10K)', ha='center',
             fontsize=6, fontfamily='monospace', fontweight='bold', color='#333', zorder=4)
    ax3.text(eq_x + eq_w/2, eq_y + 0.25,
             'No press: R > 1M\u03A9, V \u2248 0    |    Hard press: R \u2248 4\u03A9, V \u2248 2.6V',
             ha='center', fontsize=5, color='#555', zorder=4)

    draw_title_block(ax3, PW, PH, 3, 3, 'MUX + Connectors + Sensing')
    fig3.tight_layout(pad=0.5)
    pdf.savefig(fig3, dpi=150)
    plt.close(fig3)

print(f'Schematic saved: {output_path}')
print('3 pages: (1) MCU+Bus  (2) 595 Cascade+Diodes  (3) MUX+FFC+Sensing')
print('Done.')
