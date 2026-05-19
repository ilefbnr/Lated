"""Build the LateD project presentation (in French) as a .pptx file."""
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR

# ---------------------------------------------------------------------------
# Theme (SOC / command-center look)
# ---------------------------------------------------------------------------
BG          = RGBColor(0x0B, 0x12, 0x1F)   # near-black navy
PANEL       = RGBColor(0x12, 0x1C, 0x2E)   # panel background
ACCENT      = RGBColor(0x22, 0xD3, 0xEE)   # cyan
ACCENT2     = RGBColor(0xA7, 0x8B, 0xFA)   # violet
ACCENT3     = RGBColor(0xF8, 0x71, 0x71)   # red
ACCENT4     = RGBColor(0x34, 0xD3, 0x99)   # green
TEXT        = RGBColor(0xE5, 0xE7, 0xEB)   # light gray
MUTED       = RGBColor(0x9C, 0xA3, 0xAF)   # muted gray
GRID        = RGBColor(0x1F, 0x2A, 0x44)

prs = Presentation()
prs.slide_width  = Inches(13.333)
prs.slide_height = Inches(7.5)
SW, SH = prs.slide_width, prs.slide_height

BLANK = prs.slide_layouts[6]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def add_bg(slide, color=BG):
    bg = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, SW, SH)
    bg.line.fill.background()
    bg.fill.solid()
    bg.fill.fore_color.rgb = color
    return bg


def add_rect(slide, x, y, w, h, fill=PANEL, line=None, radius=False):
    shape_kind = MSO_SHAPE.ROUNDED_RECTANGLE if radius else MSO_SHAPE.RECTANGLE
    s = slide.shapes.add_shape(shape_kind, x, y, w, h)
    s.fill.solid()
    s.fill.fore_color.rgb = fill
    if line is None:
        s.line.fill.background()
    else:
        s.line.color.rgb = line
        s.line.width = Pt(1)
    return s


def add_text(slide, x, y, w, h, text, *, size=14, color=TEXT, bold=False,
             italic=False, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP,
             font="Calibri"):
    tb = slide.shapes.add_textbox(x, y, w, h)
    tf = tb.text_frame
    tf.margin_left = tf.margin_right = Emu(40000)
    tf.margin_top = tf.margin_bottom = Emu(20000)
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    lines = text.split("\n") if isinstance(text, str) else text
    for i, line in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        r = p.add_run()
        r.text = line
        r.font.size = Pt(size)
        r.font.bold = bold
        r.font.italic = italic
        r.font.color.rgb = color
        r.font.name = font
    return tb


def add_header(slide, title, subtitle=None):
    # top bar
    add_rect(slide, 0, 0, SW, Inches(0.55), fill=PANEL)
    add_rect(slide, 0, Inches(0.55), SW, Emu(20000), fill=ACCENT)
    add_text(slide, Inches(0.35), Inches(0.05), Inches(8), Inches(0.5),
             "LateD  ·  Lateral Movement Detection Platform",
             size=12, color=ACCENT, bold=True)
    add_text(slide, Inches(10.5), Inches(0.05), Inches(2.7), Inches(0.5),
             "SOC · TGNN · Real-time",
             size=11, color=MUTED, align=PP_ALIGN.RIGHT)
    # title block
    add_text(slide, Inches(0.5), Inches(0.75), Inches(12.3), Inches(0.6),
             title, size=28, color=TEXT, bold=True)
    if subtitle:
        add_text(slide, Inches(0.5), Inches(1.30), Inches(12.3), Inches(0.4),
                 subtitle, size=14, color=MUTED, italic=True)
    # divider
    add_rect(slide, Inches(0.5), Inches(1.78), Inches(12.3), Emu(15000),
             fill=GRID)


def add_footer(slide, page, total):
    add_text(slide, Inches(0.5), Inches(7.15), Inches(6), Inches(0.3),
             "LateD — Présentation du projet  ·  2026", size=10, color=MUTED)
    add_text(slide, Inches(11.5), Inches(7.15), Inches(1.5), Inches(0.3),
             f"{page} / {total}", size=10, color=MUTED, align=PP_ALIGN.RIGHT)


def add_bullets(slide, x, y, w, h, items, *, size=14, gap=0.04,
                bullet="▸", color=TEXT, bullet_color=ACCENT):
    tb = slide.shapes.add_textbox(x, y, w, h)
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = Emu(40000)
    for i, item in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = PP_ALIGN.LEFT
        p.space_after = Pt(6)
        r1 = p.add_run(); r1.text = f"{bullet}  "
        r1.font.size = Pt(size); r1.font.color.rgb = bullet_color
        r1.font.bold = True; r1.font.name = "Calibri"
        r2 = p.add_run(); r2.text = item
        r2.font.size = Pt(size); r2.font.color.rgb = color
        r2.font.name = "Calibri"
    return tb


def add_kv_card(slide, x, y, w, h, title, value, *, sub=None,
                accent=ACCENT):
    add_rect(slide, x, y, w, h, fill=PANEL, radius=True)
    add_rect(slide, x, y, Emu(45000), h, fill=accent)
    add_text(slide, x + Inches(0.18), y + Inches(0.10),
             w - Inches(0.25), Inches(0.32),
             title, size=11, color=MUTED, bold=True)
    add_text(slide, x + Inches(0.18), y + Inches(0.38),
             w - Inches(0.25), Inches(0.6),
             value, size=22, color=TEXT, bold=True)
    if sub:
        add_text(slide, x + Inches(0.18), h + y - Inches(0.45),
                 w - Inches(0.25), Inches(0.35),
                 sub, size=10, color=MUTED, italic=True)


def add_pipeline_box(slide, x, y, w, h, title, body, accent=ACCENT):
    add_rect(slide, x, y, w, h, fill=PANEL, radius=True)
    add_rect(slide, x, y, w, Inches(0.32), fill=accent, radius=True)
    add_text(slide, x + Inches(0.1), y + Inches(0.02), w, Inches(0.3),
             title, size=11, color=BG, bold=True)
    add_text(slide, x + Inches(0.15), y + Inches(0.4),
             w - Inches(0.25), h - Inches(0.5),
             body, size=10, color=TEXT)


def add_arrow(slide, x, y, w, h, color=ACCENT):
    a = slide.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW, x, y, w, h)
    a.fill.solid(); a.fill.fore_color.rgb = color
    a.line.fill.background()
    return a


def add_down_arrow(slide, x, y, w, h, color=ACCENT):
    a = slide.shapes.add_shape(MSO_SHAPE.DOWN_ARROW, x, y, w, h)
    a.fill.solid(); a.fill.fore_color.rgb = color
    a.line.fill.background()
    return a


def add_table(slide, x, y, w, h, headers, rows,
              header_fill=ACCENT, header_color=BG,
              row_fill=PANEL, alt_fill=RGBColor(0x18, 0x24, 0x3A),
              text_color=TEXT, size=11):
    cols = len(headers)
    rows_count = len(rows) + 1
    tbl_shape = slide.shapes.add_table(rows_count, cols, x, y, w, h)
    tbl = tbl_shape.table
    for j, htxt in enumerate(headers):
        cell = tbl.cell(0, j)
        cell.fill.solid(); cell.fill.fore_color.rgb = header_fill
        cell.text = ""
        tf = cell.text_frame; tf.word_wrap = True
        p = tf.paragraphs[0]; p.alignment = PP_ALIGN.LEFT
        r = p.add_run(); r.text = htxt
        r.font.size = Pt(size); r.font.bold = True
        r.font.color.rgb = header_color; r.font.name = "Calibri"
    for i, row in enumerate(rows, start=1):
        for j, val in enumerate(row):
            cell = tbl.cell(i, j)
            cell.fill.solid()
            cell.fill.fore_color.rgb = row_fill if i % 2 else alt_fill
            cell.text = ""
            tf = cell.text_frame; tf.word_wrap = True
            p = tf.paragraphs[0]; p.alignment = PP_ALIGN.LEFT
            r = p.add_run(); r.text = val
            r.font.size = Pt(size); r.font.color.rgb = text_color
            r.font.name = "Calibri"
    return tbl


# ---------------------------------------------------------------------------
# SLIDE COLLECTION
# ---------------------------------------------------------------------------
TOTAL = 16
page = 0


def new_slide():
    global page
    page += 1
    s = prs.slides.add_slide(BLANK)
    add_bg(s)
    return s


# --------------- Slide 1 : Couverture ---------------
s = new_slide()
add_rect(s, 0, 0, SW, SH, fill=BG)
# accent stripes
add_rect(s, 0, 0, Inches(0.18), SH, fill=ACCENT)
add_rect(s, SW - Inches(0.18), 0, Inches(0.18), SH, fill=ACCENT2)
add_text(s, Inches(0.9), Inches(1.2), Inches(11), Inches(0.6),
         "LateD", size=72, color=ACCENT, bold=True)
add_text(s, Inches(0.9), Inches(2.3), Inches(11), Inches(0.6),
         "Plateforme SOC de Détection du Mouvement Latéral",
         size=30, color=TEXT, bold=True)
add_text(s, Inches(0.9), Inches(3.05), Inches(11), Inches(0.5),
         "Temporal Graph Neural Networks · Détection de reconnaissance · "
         "Reconstruction des chemins d'attaque",
         size=16, color=MUTED, italic=True)

add_kv_card(s, Inches(0.9),  Inches(4.3), Inches(2.8), Inches(1.2),
            "MODÈLE IA", "TGNN", sub="Graph neural net temporel",
            accent=ACCENT)
add_kv_card(s, Inches(3.9),  Inches(4.3), Inches(2.8), Inches(1.2),
            "PHASES", "2", sub="Offline (train) + Online (detect)",
            accent=ACCENT2)
add_kv_card(s, Inches(6.9),  Inches(4.3), Inches(2.8), Inches(1.2),
            "MODULES", "9", sub="Strictement séparés",
            accent=ACCENT4)
add_kv_card(s, Inches(9.9),  Inches(4.3), Inches(2.8), Inches(1.2),
            "DONNÉES", "LANL", sub="Flows + Redteam labels",
            accent=ACCENT3)

add_text(s, Inches(0.9), Inches(6.6), Inches(11), Inches(0.4),
         "Présentation interne  ·  Mai 2026",
         size=14, color=MUTED, italic=True)


# --------------- Slide 2 : Idée / Problème ---------------
s = new_slide()
add_header(s, "1.  L'idée — Pourquoi LateD ?",
           "Le mouvement latéral est l'angle mort des défenses périmétriques")

add_rect(s, Inches(0.5), Inches(2.0), Inches(6.1), Inches(4.8),
         fill=PANEL, radius=True)
add_text(s, Inches(0.8), Inches(2.15), Inches(5.5), Inches(0.4),
         "🔴  LE PROBLÈME", size=14, color=ACCENT3, bold=True)
add_bullets(s, Inches(0.8), Inches(2.6), Inches(5.6), Inches(4.0), [
    "Les IDS/Firewalls voient l'entrée — pas la propagation interne.",
    "Une fois dans le LAN, l'attaquant pivote d'hôte en hôte (RDP, SMB, "
    "WMI, PsExec, Kerberos).",
    "Le SIEM agrège des logs : il ne « voit » pas le graphe temporel "
    "des connexions.",
    "Conséquence : MTTD moyen > 200 jours sur le mouvement latéral.",
    "Les attaques APT (NotPetya, SolarWinds…) exploitent exactement "
    "cet angle mort.",
], size=13, bullet_color=ACCENT3)

add_rect(s, Inches(6.8), Inches(2.0), Inches(6.0), Inches(4.8),
         fill=PANEL, radius=True)
add_text(s, Inches(7.1), Inches(2.15), Inches(5.5), Inches(0.4),
         "✅  NOTRE APPROCHE", size=14, color=ACCENT4, bold=True)
add_bullets(s, Inches(7.1), Inches(2.6), Inches(5.5), Inches(4.0), [
    "Modéliser le trafic interne comme un graphe temporel "
    "(nœuds = hôtes, arêtes = flux).",
    "Apprendre la « normalité dynamique » par TGNN sur LANL.",
    "Coupler avec un détecteur de reconnaissance (scans, énumération).",
    "Fusionner les signaux → score de suspicion par hôte / fenêtre.",
    "Reconstruire les chemins d'attaque pour l'analyste SOC.",
    "Tout est expliquable : chaque alerte remonte à ses flux sources.",
], size=13, bullet_color=ACCENT4)

add_footer(s, page, TOTAL)


# --------------- Slide 3 : Vision & objectifs ---------------
s = new_slide()
add_header(s, "2.  Vision & objectifs produit",
           "Une plateforme SOC opérationnelle, pas un POC académique")

cards = [
    ("Détection temps-réel", "TGNN",
     "Score par arête à la volée sur le flux Zeek/PCAP/NetFlow.",
     ACCENT),
    ("Explicabilité", "100 %",
     "Chaque alerte porte ses flux sources et son raisonnement.",
     ACCENT2),
    ("Isolation de panne", "Strict",
     "Une panne TGNN n'éteint pas la détection recon, et vice-versa.",
     ACCENT4),
    ("Replayability", "Forensic",
     "Toute détection re-jouable depuis les flows canoniques.",
     ACCENT3),
]
for i, (t, v, sub, c) in enumerate(cards):
    col = i % 2; row = i // 2
    x = Inches(0.6) + col * Inches(6.3)
    y = Inches(2.1) + row * Inches(2.45)
    add_rect(s, x, y, Inches(6.1), Inches(2.25), fill=PANEL, radius=True)
    add_rect(s, x, y, Inches(6.1), Inches(0.35), fill=c, radius=True)
    add_text(s, x + Inches(0.2), y + Inches(0.03),
             Inches(5.7), Inches(0.3),
             t.upper(), size=12, color=BG, bold=True)
    add_text(s, x + Inches(0.2), y + Inches(0.5),
             Inches(5.7), Inches(0.7),
             v, size=30, color=TEXT, bold=True)
    add_text(s, x + Inches(0.2), y + Inches(1.25),
             Inches(5.7), Inches(1.0),
             sub, size=13, color=MUTED, italic=True)

add_footer(s, page, TOTAL)


# --------------- Slide 4 : Architecture globale ---------------
s = new_slide()
add_header(s, "3.  Architecture globale (vue système)",
           "Empilement strict : ingestion → graphe → détection → corrélation → SOC")

# Stack vertical (7 layers)
layers = [
    ("SOC Dashboard (UI)",
     "Next.js · TypeScript · Tailwind · Framer · Cytoscape",  ACCENT2),
    ("Supervision Layer (FastAPI)",
     "REST API · WebSocket server · Alert engine",            ACCENT),
    ("Correlation Engine",
     "recon → LM chaining · pivots · timelines · attack paths", ACCENT4),
    ("Detection Core (AI)",
     "TGNN LM · Recon detector · Suspicion fusion",           ACCENT3),
    ("Temporal Graph Modeling",
     "snapshots · edge features · node features · stats",     ACCENT),
    ("Ingestion Layer",
     "PCAP · Zeek · NetFlow → Canonical Flow schema",         ACCENT2),
    ("Network Discovery (bootstrap)",
     "passive · active · hybrid → baseline topology",         ACCENT4),
]
y = Inches(2.0)
H = Inches(0.62)
for title, body, c in layers:
    add_rect(s, Inches(0.7), y, Inches(11.9), H, fill=PANEL, radius=True)
    add_rect(s, Inches(0.7), y, Inches(0.18), H, fill=c)
    add_text(s, Inches(1.0), y + Inches(0.06), Inches(5.5), Inches(0.32),
             title, size=14, color=TEXT, bold=True)
    add_text(s, Inches(1.0), y + Inches(0.32), Inches(11), Inches(0.32),
             body, size=11, color=MUTED, italic=True)
    y += H + Inches(0.08)

# arrows on the right
yy = Inches(2.0)
for _ in range(6):
    add_down_arrow(s, Inches(12.7), yy + Inches(0.55), Inches(0.18), Inches(0.14),
                   color=ACCENT)
    yy += H + Inches(0.08)

add_footer(s, page, TOTAL)


# --------------- Slide 5 : Deux phases ---------------
s = new_slide()
add_header(s, "4.  Deux phases strictement séparées",
           "Offline = entraînement TGNN sur LANL.   Online = inférence sur trafic d'entreprise.")

# Offline column
add_rect(s, Inches(0.5), Inches(2.0), Inches(6.1), Inches(4.9),
         fill=PANEL, radius=True)
add_rect(s, Inches(0.5), Inches(2.0), Inches(6.1), Inches(0.4),
         fill=ACCENT2, radius=True)
add_text(s, Inches(0.7), Inches(2.04), Inches(5.5), Inches(0.35),
         "PHASE A — OFFLINE  (entraînement)",
         size=14, color=BG, bold=True)

steps_off = [
    ("lanl_parser",     "Lecture brute du dataset LANL"),
    ("weak_labeler",    "Labels faibles à partir du redteam log"),
    ("dataset_builder", "Snapshots temporels + features"),
    ("pretrain_ssl",    "Pré-entraînement auto-supervisé"),
    ("finetune_lm",     "Fine-tuning semi-supervisé LM"),
    ("evaluate",        "Métriques (PR-AUC, FPR@TPR)"),
    ("export_model",    "→ tgnn_lm.pt  (artefact unique)"),
]
yy = Inches(2.55)
for name, body in steps_off:
    add_rect(s, Inches(0.7), yy, Inches(5.7), Inches(0.32),
             fill=RGBColor(0x18, 0x24, 0x3A), radius=True)
    add_text(s, Inches(0.85), yy + Inches(0.03), Inches(2.0), Inches(0.3),
             name, size=11, color=ACCENT2, bold=True)
    add_text(s, Inches(2.85), yy + Inches(0.03), Inches(3.5), Inches(0.3),
             body, size=10, color=MUTED)
    yy += Inches(0.36)

# Online column
add_rect(s, Inches(6.8), Inches(2.0), Inches(6.0), Inches(4.9),
         fill=PANEL, radius=True)
add_rect(s, Inches(6.8), Inches(2.0), Inches(6.0), Inches(0.4),
         fill=ACCENT, radius=True)
add_text(s, Inches(7.0), Inches(2.04), Inches(5.5), Inches(0.35),
         "PHASE B — ONLINE  (détection temps réel)",
         size=14, color=BG, bold=True)
steps_on = [
    ("discovery",        "Baseline topology (passif / actif)"),
    ("ingestion",        "PCAP/Zeek/NetFlow → CanonicalFlow"),
    ("graph builder",    "Temporal snapshots (30 s par défaut)"),
    ("TGNN LM detector", "Score par arête / par hôte"),
    ("Recon detector",   "Score par hôte source (sliding win.)"),
    ("Suspicion fusion", "Score unifié + métadonnées"),
    ("Correlation",      "AttackPath chronologique"),
    ("Alert engine",     "REST + WebSocket → SOC UI"),
]
yy = Inches(2.55)
for name, body in steps_on:
    add_rect(s, Inches(7.0), yy, Inches(5.6), Inches(0.30),
             fill=RGBColor(0x18, 0x24, 0x3A), radius=True)
    add_text(s, Inches(7.15), yy + Inches(0.025), Inches(2.0), Inches(0.3),
             name, size=11, color=ACCENT, bold=True)
    add_text(s, Inches(9.15), yy + Inches(0.025), Inches(3.5), Inches(0.3),
             body, size=10, color=MUTED)
    yy += Inches(0.34)

add_footer(s, page, TOTAL)


# --------------- Slide 6 : Index des modules ---------------
s = new_slide()
add_header(s, "5.  Carte des modules — backend/src/lated/",
           "Chaque dossier = une responsabilité unique, un contrat narrow")

headers = ["Module", "Chemin", "Responsabilité"]
rows = [
    ["Network Discovery", "discovery/",
     "Découverte passive/active — baseline topologique"],
    ["Ingestion", "ingestion/",
     "Normaliser PCAP / Zeek / NetFlow → flows canoniques"],
    ["Temporal Graph", "graph/",
     "Construction de snapshots + features arêtes/nœuds"],
    ["Detection Core", "detection/",
     "TGNN LM + détecteur recon + fusion de suspicion"],
    ["Correlation", "correlation/",
     "Chaînage recon→LM, pivots, reconstruction de chemins"],
    ["Supervision", "supervision/",
     "API REST, WebSocket, alert engine, persistence"],
    ["Pipelines offline", "pipelines/offline/",
     "Pipeline complet d'entraînement LANL"],
    ["Pipelines online", "pipelines/online/",
     "Orchestration du streaming temps-réel"],
    ["Frontend SOC", "frontend/src/",
     "Console opérateur React/Next.js"],
]
add_table(s, Inches(0.5), Inches(2.0), Inches(12.3), Inches(4.8),
          headers, rows, size=12)

add_footer(s, page, TOTAL)


# --------------- Slide 7 : Discovery + Ingestion ---------------
s = new_slide()
add_header(s, "6.  Modules — Discovery & Ingestion",
           "Avant tout calcul IA : connaître le terrain et normaliser les entrées")

# Discovery card
add_rect(s, Inches(0.5), Inches(2.0), Inches(6.1), Inches(4.8),
         fill=PANEL, radius=True)
add_rect(s, Inches(0.5), Inches(2.0), Inches(6.1), Inches(0.4),
         fill=ACCENT4, radius=True)
add_text(s, Inches(0.7), Inches(2.04), Inches(5.5), Inches(0.35),
         "DISCOVERY  ·  discovery/", size=14, color=BG, bold=True)
add_text(s, Inches(0.7), Inches(2.5), Inches(5.7), Inches(0.4),
         "Bootstrapper le graphe de référence du réseau",
         size=12, color=ACCENT4, italic=True)
add_bullets(s, Inches(0.7), Inches(2.95), Inches(5.7), Inches(3.7), [
    "passive_discovery.py — sniff ARP / DNS / Zeek logs",
    "active_discovery.py — scans (opt-in, désactivé par défaut)",
    "host_registry.py — référentiel des hôtes (IP, MAC, OS, rôle)",
    "topology_builder.py — assemble la baseline graph",
    "baseline_graph.py — modèle immuable de la topologie",
    "discovery_service.py — orchestrateur du bootstrap",
], size=12, bullet_color=ACCENT4)

# Ingestion card
add_rect(s, Inches(6.8), Inches(2.0), Inches(6.0), Inches(4.8),
         fill=PANEL, radius=True)
add_rect(s, Inches(6.8), Inches(2.0), Inches(6.0), Inches(0.4),
         fill=ACCENT2, radius=True)
add_text(s, Inches(7.0), Inches(2.04), Inches(5.5), Inches(0.35),
         "INGESTION  ·  ingestion/", size=14, color=BG, bold=True)
add_text(s, Inches(7.0), Inches(2.5), Inches(5.7), Inches(0.4),
         "Du capteur brut au schéma canonique unique",
         size=12, color=ACCENT2, italic=True)
add_bullets(s, Inches(7.0), Inches(2.95), Inches(5.7), Inches(3.7), [
    "pcap_parser.py — scapy, lecture binaire PCAP",
    "zeek_parser.py — conn.log / dns.log / kerberos.log",
    "netflow_parser.py — NetFlow v5/v9, IPFIX",
    "flow_normalizer.py — uniformisation des champs",
    "flow_validator.py — schéma strict (pydantic)",
    "canonical_schema.py — modèle CanonicalFlow",
    "flow_store.py — persistance immuable (forensic-ready)",
], size=12, bullet_color=ACCENT2)

add_footer(s, page, TOTAL)


# --------------- Slide 8 : Graph + Detection ---------------
s = new_slide()
add_header(s, "7.  Modules — Temporal Graph & Detection Core",
           "Le cœur scientifique de la plateforme")

# Graph card
add_rect(s, Inches(0.5), Inches(2.0), Inches(6.1), Inches(4.8),
         fill=PANEL, radius=True)
add_rect(s, Inches(0.5), Inches(2.0), Inches(6.1), Inches(0.4),
         fill=ACCENT, radius=True)
add_text(s, Inches(0.7), Inches(2.04), Inches(5.5), Inches(0.35),
         "TEMPORAL GRAPH  ·  graph/", size=14, color=BG, bold=True)
add_text(s, Inches(0.7), Inches(2.5), Inches(5.7), Inches(0.4),
         "Transforme un flux de flows en graphe dynamique",
         size=12, color=ACCENT, italic=True)
add_bullets(s, Inches(0.7), Inches(2.95), Inches(5.7), Inches(3.7), [
    "snapshot_manager.py — fenêtres temporelles (30 s)",
    "graph_builder.py — assemblage nœuds/arêtes par snapshot",
    "edge_features.py — durée, octets, ports, protocoles",
    "node_features.py — degré, rôle, historique",
    "graph_statistics.py — betweenness, degree-Δ, …",
    "temporal_graph.py — modèle de graphe dynamique",
    "graph_store.py — persistance + retrieval",
], size=12, bullet_color=ACCENT)

# Detection card
add_rect(s, Inches(6.8), Inches(2.0), Inches(6.0), Inches(4.8),
         fill=PANEL, radius=True)
add_rect(s, Inches(6.8), Inches(2.0), Inches(6.0), Inches(0.4),
         fill=ACCENT3, radius=True)
add_text(s, Inches(7.0), Inches(2.04), Inches(5.5), Inches(0.35),
         "DETECTION CORE  ·  detection/", size=14, color=BG, bold=True)
add_text(s, Inches(7.0), Inches(2.5), Inches(5.7), Inches(0.4),
         "Trois sous-modules indépendants, fusion finale",
         size=12, color=ACCENT3, italic=True)
add_bullets(s, Inches(7.0), Inches(2.95), Inches(5.7), Inches(3.7), [
    "tgnn/ — Modèle TGN (LM scoring sur arêtes/hôtes)",
    "recon/ — Heuristique + behavioral (scans, énumération)",
    "fusion/ — Combine LMScore + ReconScore → SuspicionScore",
    "Failure isolation : panne TGNN ≠ panne recon",
    "Tous les scores sont expliquables (flux sources)",
    "Sorties typées (pydantic) consommées par la corrélation",
], size=12, bullet_color=ACCENT3)

add_footer(s, page, TOTAL)


# --------------- Slide 9 : Correlation + Supervision ---------------
s = new_slide()
add_header(s, "8.  Modules — Correlation & Supervision",
           "Du score brut à l'expérience analyste SOC")

# Correlation
add_rect(s, Inches(0.5), Inches(2.0), Inches(6.1), Inches(4.8),
         fill=PANEL, radius=True)
add_rect(s, Inches(0.5), Inches(2.0), Inches(6.1), Inches(0.4),
         fill=ACCENT2, radius=True)
add_text(s, Inches(0.7), Inches(2.04), Inches(5.5), Inches(0.35),
         "CORRELATION  ·  correlation/", size=14, color=BG, bold=True)
add_text(s, Inches(0.7), Inches(2.5), Inches(5.7), Inches(0.4),
         "Recon → LM chaining, pivots, timelines",
         size=12, color=ACCENT2, italic=True)
add_bullets(s, Inches(0.7), Inches(2.95), Inches(5.7), Inches(3.7), [
    "correlation_engine.py — chef d'orchestre du chaînage",
    "graph_adjacency.py — voisinage temporel pour la propagation",
    "propagation_analyzer.py — détecte les sauts d'hôte en hôte",
    "pivot_identifier.py — repère les hôtes-pivots (bridge)",
    "attack_path_builder.py — assemble AttackPath",
    "timeline_reconstructor.py — chronologie horodatée",
    "correlation_store.py — persistance des paths",
], size=12, bullet_color=ACCENT2)

# Supervision
add_rect(s, Inches(6.8), Inches(2.0), Inches(6.0), Inches(4.8),
         fill=PANEL, radius=True)
add_rect(s, Inches(6.8), Inches(2.0), Inches(6.0), Inches(0.4),
         fill=ACCENT, radius=True)
add_text(s, Inches(7.0), Inches(2.04), Inches(5.5), Inches(0.35),
         "SUPERVISION  ·  supervision/", size=14, color=BG, bold=True)
add_text(s, Inches(7.0), Inches(2.5), Inches(5.7), Inches(0.4),
         "L'interface entre l'IA et l'analyste SOC",
         size=12, color=ACCENT, italic=True)
add_bullets(s, Inches(7.0), Inches(2.95), Inches(5.7), Inches(3.7), [
    "api/ — endpoints REST FastAPI (alerts, hosts, paths)",
    "websocket/ — push temps réel vers le dashboard",
    "alerts/ — alert engine + dédoublonnage + priorisation",
    "storage/ — Postgres + Redis (snapshots, queues)",
    "flows_repository.py / hosts_repository.py / paths_repository.py",
    "graph_repository.py — accès aux snapshots persistés",
    "auth.py — RBAC analyste SOC",
], size=12, bullet_color=ACCENT)

add_footer(s, page, TOTAL)


# --------------- Slide 10 : Pipelines + Frontend ---------------
s = new_slide()
add_header(s, "9.  Pipelines & Frontend",
           "Les orchestrateurs end-to-end et la console opérateur")

# Pipelines
add_rect(s, Inches(0.5), Inches(2.0), Inches(6.1), Inches(4.8),
         fill=PANEL, radius=True)
add_rect(s, Inches(0.5), Inches(2.0), Inches(6.1), Inches(0.4),
         fill=ACCENT4, radius=True)
add_text(s, Inches(0.7), Inches(2.04), Inches(5.5), Inches(0.35),
         "PIPELINES  ·  pipelines/", size=14, color=BG, bold=True)
add_text(s, Inches(0.7), Inches(2.5), Inches(5.7), Inches(0.4),
         "Glue entre tous les modules — invocable en CLI",
         size=12, color=ACCENT4, italic=True)
add_bullets(s, Inches(0.7), Inches(2.95), Inches(5.7), Inches(3.7), [
    "offline/pretrain_ssl.py — pré-entraînement auto-supervisé",
    "offline/finetune_lm.py — fine-tuning supervisé LM",
    "offline/evaluate.py — métriques + courbes",
    "offline/export_model.py — sérialisation tgnn_lm.pt",
    "online/pipeline_runner.py — orchestre l'inférence",
    "Console scripts : lated-train, lated-finetune, lated-online, lated-api",
], size=12, bullet_color=ACCENT4)

# Frontend
add_rect(s, Inches(6.8), Inches(2.0), Inches(6.0), Inches(4.8),
         fill=PANEL, radius=True)
add_rect(s, Inches(6.8), Inches(2.0), Inches(6.0), Inches(0.4),
         fill=ACCENT3, radius=True)
add_text(s, Inches(7.0), Inches(2.04), Inches(5.5), Inches(0.35),
         "FRONTEND SOC  ·  frontend/src/", size=14, color=BG, bold=True)
add_text(s, Inches(7.0), Inches(2.5), Inches(5.7), Inches(0.4),
         "Command center : visuel, temps réel, dense",
         size=12, color=ACCENT3, italic=True)
add_bullets(s, Inches(7.0), Inches(2.95), Inches(5.7), Inches(3.7), [
    "components/ — composants UI (cards, tables, alert panes)",
    "pages/ — routes Next.js (dashboard, hosts, paths, replay)",
    "visualization/ — graphes interactifs (Cytoscape)",
    "websocket/ — client WS pour la stream d'alertes",
    "services/ — clients REST typés",
    "stores/ — état global (Zustand/Redux)",
    "hooks/ · layouts/ · themes/ · types/  — couche UX",
], size=12, bullet_color=ACCENT3)

add_footer(s, page, TOTAL)


# --------------- Slide 11 : Schéma de données ---------------
s = new_slide()
add_header(s, "10.  Contrats de données entre modules",
           "Tout passe par des objets typés et immuables")

headers = ["Étape", "Entrée", "Sortie", "Détenteur du contrat"]
rows = [
    ["Discovery",       "ARP/DNS/scan",        "BaselineGraph",     "discovery/baseline_graph.py"],
    ["Ingestion",       "PCAP/Zeek/NetFlow",   "CanonicalFlow*",    "ingestion/canonical_schema.py"],
    ["Graph building",  "CanonicalFlow*",      "TemporalSnapshot*", "graph/temporal_graph.py"],
    ["TGNN detection",  "TemporalSnapshot",    "LMScore",           "detection/tgnn/"],
    ["Recon detection", "CanonicalFlow window","ReconScore",        "detection/recon/"],
    ["Fusion",          "LMScore + ReconScore","SuspicionScore",    "detection/fusion/"],
    ["Correlation",     "SuspicionScore*",     "AttackPath",        "correlation/attack_path_builder.py"],
    ["Supervision",     "AttackPath + alerts", "REST + WS events",  "supervision/api · websocket"],
]
add_table(s, Inches(0.5), Inches(2.0), Inches(12.3), Inches(4.8),
          headers, rows, size=12)
add_text(s, Inches(0.5), Inches(6.9), Inches(12), Inches(0.3),
         "Garanties : flows immuables · snapshots non-recouvrants · scoring monotone-expliquable",
         size=11, color=MUTED, italic=True)

add_footer(s, page, TOTAL)


# --------------- Slide 12 : Stack technique ---------------
s = new_slide()
add_header(s, "11.  Stack technique",
           "Choisi pour la séparation runtime/training et le SOC temps-réel")

cards = [
    ("BACKEND CORE",   "Python 3.11+",
     "FastAPI · pydantic v2 · uvicorn · websockets · structlog",
     ACCENT),
    ("IA / TRAINING",  "PyTorch",
     "torch-geometric · scikit-learn · pandas (extra `train`)",
     ACCENT3),
    ("INGESTION",      "scapy + Zeek",
     "PCAP binaire · conn.log · NetFlow v5/v9/IPFIX",
     ACCENT4),
    ("PERSISTANCE",    "Postgres + Redis",
     "SQLAlchemy 2.0 · psycopg · queues temps-réel",
     ACCENT2),
    ("FRONTEND",       "Next.js 14",
     "TypeScript · Tailwind · Framer Motion · Cytoscape",
     ACCENT),
    ("OBSERVABILITÉ",  "Prometheus",
     "structlog JSON · health endpoints · dashboards Grafana",
     ACCENT4),
]
for i, (t, v, sub, c) in enumerate(cards):
    col = i % 3; row = i // 3
    x = Inches(0.5) + col * Inches(4.25)
    y = Inches(2.1) + row * Inches(2.45)
    add_rect(s, x, y, Inches(4.05), Inches(2.25), fill=PANEL, radius=True)
    add_rect(s, x, y, Inches(4.05), Inches(0.32), fill=c, radius=True)
    add_text(s, x + Inches(0.18), y + Inches(0.02),
             Inches(4), Inches(0.3),
             t, size=11, color=BG, bold=True)
    add_text(s, x + Inches(0.18), y + Inches(0.5),
             Inches(3.8), Inches(0.6),
             v, size=22, color=TEXT, bold=True)
    add_text(s, x + Inches(0.18), y + Inches(1.2),
             Inches(3.8), Inches(1.0),
             sub, size=11, color=MUTED, italic=True)

add_footer(s, page, TOTAL)


# --------------- Slide 13 : Sécurité ---------------
s = new_slide()
add_header(s, "12.  Posture de sécurité",
           "Une plateforme de SOC ne peut pas avoir d'angle mort interne")

points = [
    ("Isolation ingestion / IA",
     "L'ingestion ne peut pas corrompre le modèle : pas d'import croisé, "
     "tout passe par CanonicalFlow validé pydantic."),
    ("Recon ⊥ TGNN",
     "Les deux détecteurs sont strictement séparés : une panne ou un "
     "biais d'un côté ne peut pas masquer une attaque de l'autre."),
    ("Explicabilité",
     "Chaque alerte porte ses flows sources, son score, sa fenêtre, son "
     "raisonnement. Forensic-ready."),
    ("Active discovery = opt-in",
     "Le mode passif est la valeur par défaut. Aucun scan actif sans "
     "autorisation explicite."),
    ("Threat model explicite",
     "Capteurs supposés de confiance · attaquant à l'intérieur · "
     "training set bruyant mais non empoisonné."),
    ("Mypy strict + ruff sécu",
     "Type errors et imports morts ne shipent pas. Règles `S` (bandit) "
     "actives sur tout le backend."),
]
y = Inches(2.0)
for t, body in points:
    add_rect(s, Inches(0.5), y, Inches(12.3), Inches(0.75),
             fill=PANEL, radius=True)
    add_rect(s, Inches(0.5), y, Inches(0.14), Inches(0.75), fill=ACCENT3)
    add_text(s, Inches(0.85), y + Inches(0.06),
             Inches(4.5), Inches(0.3),
             t, size=13, color=ACCENT, bold=True)
    add_text(s, Inches(5.4), y + Inches(0.10),
             Inches(7.3), Inches(0.65),
             body, size=11, color=MUTED)
    y += Inches(0.82)

add_footer(s, page, TOTAL)


# --------------- Slide 14 : Détection — 6 têtes (le tableau de l'utilisateur) ---------------
s = new_slide()
add_header(s, "13.  Detection — proposition des 6 têtes",
           "Le tableau récapitulatif évalué : qui consomme quoi")

headers = ["Tête", "Input", "Sortie naturelle", "Modèle"]
rows = [
    ["A. Rules",    "flows enrichis",          "score par flow",            "Règles MITRE Python pures"],
    ["B. TGN",      "(src, dst, t, edge_feat)","score par edge",            "src/models/tgn.py existant"],
    ["C. Anomaly",  "host × window features",  "score par (host, window)",  "Autoencoder dense / IsoForest"],
    ["D. Sequence", "événements ordonnés par acteur", "score par séquence", "LSTM ou template match"],
    ["E. Topology", "graphe par snapshot",     "score par host par snapshot","NetworkX (betweenness Δ)"],
    ["F. Fusion",   "tous les scores ci-dessus","Alert par (host, window)", "Logistic / XGBoost"],
]
add_table(s, Inches(0.5), Inches(2.0), Inches(12.3), Inches(3.2),
          headers, rows, size=12)

add_rect(s, Inches(0.5), Inches(5.4), Inches(12.3), Inches(1.6),
         fill=PANEL, radius=True)
add_rect(s, Inches(0.5), Inches(5.4), Inches(0.14), Inches(1.6),
         fill=ACCENT4)
add_text(s, Inches(0.85), Inches(5.45), Inches(11.8), Inches(0.35),
         "Verdict : structure très solide ✓",
         size=14, color=ACCENT4, bold=True)
add_text(s, Inches(0.85), Inches(5.8), Inches(11.8), Inches(1.2),
         "Couvre les 4 niveaux de signal (règle, edge, host, séquence) + "
         "vue topologique + fusion. C'est exactement le découplage "
         "« failure isolation » qu'on a posé dans ARCHITECTURE.md.",
         size=12, color=MUTED, italic=True)

add_footer(s, page, TOTAL)


# --------------- Slide 15 : Avis détaillé sur la structure 6 têtes ---------------
s = new_slide()
add_header(s, "14.  Mon avis détaillé sur les 6 têtes",
           "Ce qui est juste, ce qui mérite d'être affiné")

# Forces
add_rect(s, Inches(0.5), Inches(2.0), Inches(6.1), Inches(4.8),
         fill=PANEL, radius=True)
add_rect(s, Inches(0.5), Inches(2.0), Inches(6.1), Inches(0.4),
         fill=ACCENT4, radius=True)
add_text(s, Inches(0.7), Inches(2.04), Inches(5.5), Inches(0.35),
         "✅  POINTS FORTS", size=14, color=BG, bold=True)
add_bullets(s, Inches(0.7), Inches(2.55), Inches(5.7), Inches(4.2), [
    "Granularités complémentaires : flow / edge / host / "
    "séquence / topologie — pas de redondance inutile.",
    "Fusion en dernier (F) : préserve le failure-isolation du "
    "design global. Aucun head n'éteint un autre.",
    "TGN reste sur son terrain naturel (l'arête temporelle).",
    "Rules en tête : utile pour l'explicabilité et le SOC "
    "(les analystes lisent du MITRE, pas du tenseur).",
    "Topology (E) capte le pivoting que TGN seul peut "
    "manquer (signal lent type betweenness Δ).",
    "Fusion ML (Logistic/XGBoost) → seuils ajustables sans "
    "ré-entraîner les têtes lourdes.",
], size=12, bullet_color=ACCENT4)

# À affiner
add_rect(s, Inches(6.8), Inches(2.0), Inches(6.0), Inches(4.8),
         fill=PANEL, radius=True)
add_rect(s, Inches(6.8), Inches(2.0), Inches(6.0), Inches(0.4),
         fill=ACCENT3, radius=True)
add_text(s, Inches(7.0), Inches(2.04), Inches(5.5), Inches(0.35),
         "⚠️  À AFFINER / POINTS D'ATTENTION",
         size=14, color=BG, bold=True)
add_bullets(s, Inches(7.0), Inches(2.55), Inches(5.7), Inches(4.2), [
    "Aligner les granularités avant fusion : tout doit "
    "remonter à (host, window) — prévoyez un aggregator "
    "(max-pool / weighted) par head.",
    "C (Anomaly host×window) recoupe partiellement E "
    "(topology par host×snapshot). Définir clairement ce que "
    "chacun ne couvre PAS.",
    "D (Sequence) demande une notion d'« acteur » stable : "
    "user, host, ou session ? À trancher avant impl.",
    "Calibration : Logistic suppose des scores comparables. "
    "Pensez Platt-scaling ou isotonic par head avant XGBoost.",
    "Explicabilité de F : si XGBoost, prévoir SHAP par alerte "
    "(sinon on perd la promesse SOC).",
    "Cold-start : E (betweenness Δ) a besoin d'un baseline "
    "stable — fixer la durée d'apprentissage initiale.",
], size=12, bullet_color=ACCENT3)

add_footer(s, page, TOTAL)


# --------------- Slide 16 : Recommandation + Roadmap + Q&A ---------------
s = new_slide()
add_header(s, "15.  Recommandation & next steps",
           "Adopter la structure 6 têtes — avec 4 garde-fous")

# Reco
add_rect(s, Inches(0.5), Inches(2.0), Inches(12.3), Inches(2.1),
         fill=PANEL, radius=True)
add_rect(s, Inches(0.5), Inches(2.0), Inches(0.14), Inches(2.1),
         fill=ACCENT)
add_text(s, Inches(0.85), Inches(2.10), Inches(11), Inches(0.4),
         "✔  Garder la structure 6 têtes telle quelle, sous 4 conditions :",
         size=14, color=ACCENT, bold=True)
add_bullets(s, Inches(0.85), Inches(2.55), Inches(11.5), Inches(1.6), [
    "Un FeatureAggregator commun (host, window) qui aligne A/B/C/D/E "
    "avant la fusion F.",
    "Une étape de calibration par head (Platt ou isotonic) pour que "
    "les scores soient comparables avant XGBoost.",
    "Explicabilité obligatoire : SHAP côté F + remontée des flows "
    "sources côté A et B.",
    "Tests d'isolation : chaque head doit pouvoir être désactivée sans "
    "casser les autres (failure isolation testé en CI).",
], size=12, bullet_color=ACCENT)

# Roadmap mini
add_rect(s, Inches(0.5), Inches(4.3), Inches(12.3), Inches(2.5),
         fill=PANEL, radius=True)
add_rect(s, Inches(0.5), Inches(4.3), Inches(0.14), Inches(2.5),
         fill=ACCENT2)
add_text(s, Inches(0.85), Inches(4.4), Inches(11), Inches(0.4),
         "🗺  Roadmap d'implémentation suggérée",
         size=14, color=ACCENT2, bold=True)
add_bullets(s, Inches(0.85), Inches(4.85), Inches(11.5), Inches(1.9), [
    "Sprint 1 : A (Rules) + E (Topology) → baseline démontrable "
    "sans dépendance GPU.",
    "Sprint 2 : B (TGN) branché sur les snapshots existants — "
    "intégration avec src/models/tgn.py.",
    "Sprint 3 : C + D (anomaly host-window + sequence LSTM) — "
    "entraînés sur LANL.",
    "Sprint 4 : F (Fusion + calibration + SHAP) + tests "
    "failure-isolation en CI.",
], size=12, bullet_color=ACCENT2)

# Footer
add_text(s, Inches(0.5), Inches(7.0), Inches(12), Inches(0.4),
         "Questions ?  ·  ilef.bennour@ensi-uma.tn",
         size=14, color=ACCENT, bold=True, align=PP_ALIGN.CENTER)


# ---------------------------------------------------------------------------
out = r"c:\Users\ilefb\OneDrive\Bureau\LateD\LateD_presentation_FR.pptx"
prs.save(out)
print(f"Saved: {out}")
print(f"Slides: {len(prs.slides)}")
