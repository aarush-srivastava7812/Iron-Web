import os
import shutil
from pathlib import Path

ROOT_DIR = Path(r"c:\Users\vvars\OneDrive\Desktop\Iron Web")
ROOT_CATALOG = ROOT_DIR / "catalog"
PLATFORM_CATALOG = ROOT_DIR / "stitch_ai_travel_booking_platform" / "catalog"

# Clean directories
for cat_dir in [ROOT_CATALOG, PLATFORM_CATALOG]:
    if cat_dir.exists():
        shutil.rmtree(cat_dir)
    cat_dir.mkdir(parents=True, exist_ok=True)
    (cat_dir / "kashmir_trip").mkdir(parents=True, exist_ok=True)
    (cat_dir / "kerala_trip").mkdir(parents=True, exist_ok=True)

# Authentic Vector Map for Kerala
KERALA_MAP_SVG = """
<svg viewBox="0 0 260 290" width="100%" height="100%" style="border-radius:8px; overflow:hidden; background:#f0fdf4;">
  <defs>
    <linearGradient id="oceanGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#bae6fd"/>
      <stop offset="100%" stop-color="#e0f2fe"/>
    </linearGradient>
    <linearGradient id="ghatsGrad" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#86efac"/>
      <stop offset="100%" stop-color="#22c55e"/>
    </linearGradient>
    <filter id="shadow" x="-20%" y="-20%" width="140%" height="140%">
      <feDropShadow dx="1" dy="2" stdDeviation="2" flood-opacity="0.25"/>
    </filter>
  </defs>

  <!-- Arabian Sea (West) -->
  <rect x="0" y="0" width="260" height="290" fill="url(#oceanGrad)"/>
  
  <!-- Subtle wave lines in ocean -->
  <path d="M 10,60 Q 25,55 40,60 T 70,60" fill="none" stroke="#7dd3fc" stroke-width="1.2" opacity="0.7"/>
  <path d="M 15,120 Q 30,115 45,120 T 75,120" fill="none" stroke="#7dd3fc" stroke-width="1.2" opacity="0.7"/>
  <path d="M 10,180 Q 25,175 40,180 T 65,180" fill="none" stroke="#7dd3fc" stroke-width="1.2" opacity="0.7"/>
  <path d="M 20,240 Q 35,235 50,240 T 80,240" fill="none" stroke="#7dd3fc" stroke-width="1.2" opacity="0.7"/>
  
  <!-- Sailboat in ocean -->
  <g transform="translate(22, 140) scale(0.7)" opacity="0.6">
    <path d="M 0,15 L 12,0 L 12,15 Z" fill="#0284c7"/>
    <path d="M 15,15 L 23,4 L 15,15 Z" fill="#38bdf8"/>
    <path d="M -3,17 L 27,17 L 22,23 L 2,23 Z" fill="#0369a1"/>
  </g>
  <text x="14" y="270" font-family="'Inter', sans-serif" font-size="10" font-weight="700" fill="#0369a1" letter-spacing="1">ARABIAN SEA</text>

  <!-- Kerala State Geographical Contour -->
  <!-- Starts north near Kasaragod, curves along Malabar coast down to Kovalam, with eastern spine of Western Ghats -->
  <path d="M 85,15 
           C 115,12 155,25 175,45 
           C 200,70 215,110 220,150 
           C 225,190 205,235 185,265 
           C 170,285 155,288 145,285 
           C 135,275 140,250 130,225 
           C 115,185 100,165 90,135 
           C 78,105 70,60 85,15 Z" 
        fill="#dcfce7" stroke="#4ade80" stroke-width="2" filter="url(#shadow)"/>

  <!-- Western Ghats Mountain Ridge Texture (East) -->
  <path d="M 135,35 
           C 160,50 185,85 195,125 
           C 205,165 190,210 170,245 
           L 185,265 C 205,235 225,190 220,150 C 215,110 200,70 175,45 Z" 
        fill="url(#ghatsGrad)" opacity="0.75"/>

  <!-- Mountain peak symbols in Western Ghats -->
  <g fill="#15803d" opacity="0.8">
    <polygon points="175,85 182,73 189,85"/>
    <polygon points="186,105 194,92 202,105"/>
    <polygon points="168,140 176,128 184,140"/>
    <polygon points="172,175 180,163 188,175"/>
  </g>

  <!-- Vembanad Lake & Backwaters Network (Blue in coastal plain) -->
  <path d="M 92,130 C 95,145 92,165 102,185 C 106,195 104,208 108,220" 
        fill="none" stroke="#0284c7" stroke-width="3" stroke-linecap="round" opacity="0.85"/>
  <text x="114" y="200" font-family="'Inter', sans-serif" font-size="7.5" font-weight="600" fill="#0369a1">Vembanad Lake</text>

  <!-- Route Line (Connecting Kochi -> Munnar -> Alleppey) -->
  <!-- Kochi to Munnar (climb into hills) -->
  <path d="M 92,135 Q 130,105 168,88" fill="none" stroke="#0f273d" stroke-width="3" stroke-linecap="round"/>
  <path d="M 92,135 Q 130,105 168,88" fill="none" stroke="#f59e0b" stroke-width="2" stroke-dasharray="4,4"/>
  
  <!-- Munnar to Alleppey (hills to backwaters) -->
  <path d="M 168,88 Q 155,160 108,210" fill="none" stroke="#0f273d" stroke-width="3" stroke-linecap="round"/>
  <path d="M 168,88 Q 155,160 108,210" fill="none" stroke="#f59e0b" stroke-width="2" stroke-dasharray="4,4"/>

  <!-- Munnar Pin (In Highlands) -->
  <circle cx="168" cy="88" r="8" fill="#f59e0b" stroke="#ffffff" stroke-width="2.5" filter="url(#shadow)"/>
  <circle cx="168" cy="88" r="3" fill="#0f273d"/>
  <rect x="178" y="76" width="68" height="24" rx="4" fill="#ffffff" stroke="#e2e8f0" stroke-width="1" filter="url(#shadow)"/>
  <text x="183" y="88" font-family="'Outfit', sans-serif" font-size="9.5" font-weight="800" fill="#0f273d">Munnar</text>
  <text x="183" y="96" font-family="'Inter', sans-serif" font-size="7.5" font-weight="600" fill="#16a34a">1,600m Tea Hills</text>

  <!-- Kochi Pin (Coast / Harbor) -->
  <circle cx="92" cy="135" r="8" fill="#f59e0b" stroke="#ffffff" stroke-width="2.5" filter="url(#shadow)"/>
  <circle cx="92" cy="135" r="3" fill="#0f273d"/>
  <rect x="24" y="123" width="62" height="24" rx="4" fill="#ffffff" stroke="#e2e8f0" stroke-width="1" filter="url(#shadow)"/>
  <text x="29" y="135" font-family="'Outfit', sans-serif" font-size="9.5" font-weight="800" fill="#0f273d">Kochi</text>
  <text x="29" y="143" font-family="'Inter', sans-serif" font-size="7.5" font-weight="600" fill="#0284c7">Historic Port</text>

  <!-- Alleppey Pin (Backwaters) -->
  <circle cx="108" cy="210" r="8" fill="#f59e0b" stroke="#ffffff" stroke-width="2.5" filter="url(#shadow)"/>
  <circle cx="108" cy="210" r="3" fill="#0f273d"/>
  <rect x="118" y="200" width="76" height="24" rx="4" fill="#ffffff" stroke="#e2e8f0" stroke-width="1" filter="url(#shadow)"/>
  <text x="123" y="212" font-family="'Outfit', sans-serif" font-size="9.5" font-weight="800" fill="#0f273d">Alleppey</text>
  <text x="123" y="220" font-family="'Inter', sans-serif" font-size="7.5" font-weight="600" fill="#0d9488">Serene Houseboats</text>

  <!-- Route Tags -->
  <g transform="translate(112, 102)">
    <rect x="0" y="0" width="38" height="12" rx="3" fill="#0f273d" opacity="0.85"/>
    <text x="19" y="9" font-family="'Inter', sans-serif" font-size="6.5" font-weight="700" fill="#ffffff" text-anchor="middle">3.5 hrs</text>
  </g>
  <g transform="translate(136, 155)">
    <rect x="0" y="0" width="34" height="12" rx="3" fill="#0f273d" opacity="0.85"/>
    <text x="17" y="9" font-family="'Inter', sans-serif" font-size="6.5" font-weight="700" fill="#ffffff" text-anchor="middle">4.0 hrs</text>
  </g>

  <!-- State Badge Label -->
  <text x="155" y="40" font-family="'Outfit', sans-serif" font-size="12" font-weight="800" fill="#15803d" letter-spacing="2">KERALA</text>

  <!-- Compass Rose (Top Right) -->
  <g transform="translate(230, 25)">
    <circle cx="0" cy="0" r="14" fill="#ffffff" stroke="#cbd5e1" stroke-width="1" filter="url(#shadow)"/>
    <polygon points="0,-11 3,0 -3,0" fill="#dc2626"/>
    <polygon points="0,11 3,0 -3,0" fill="#64748b"/>
    <text x="0" y="-13" font-family="'Inter', sans-serif" font-size="7" font-weight="800" fill="#dc2626" text-anchor="middle">N</text>
  </g>
</svg>
"""

# Authentic Vector Map for Kashmir
KASHMIR_MAP_SVG = """
<svg viewBox="0 0 260 290" width="100%" height="100%" style="border-radius:8px; overflow:hidden; background:#f8fafc;">
  <defs>
    <linearGradient id="snowGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#ffffff"/>
      <stop offset="100%" stop-color="#e2e8f0"/>
    </linearGradient>
    <linearGradient id="valleyGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#dbeafe"/>
      <stop offset="100%" stop-color="#eff6ff"/>
    </linearGradient>
    <filter id="kashShadow" x="-20%" y="-20%" width="140%" height="140%">
      <feDropShadow dx="1" dy="2" stdDeviation="2" flood-opacity="0.2"/>
    </filter>
  </defs>

  <!-- Alpine Background with Elevation Terrain -->
  <rect x="0" y="0" width="260" height="290" fill="#f1f5f9"/>

  <!-- Pir Panjal Mountain Range Silhouette (Southwest) -->
  <path d="M 0,160 
           C 20,130 50,110 70,85 
           C 90,60 110,35 150,20 
           L 150,0 L 0,0 Z" 
        fill="#cbd5e1" opacity="0.6"/>

  <!-- Great Himalayan Mountain Range (Northeast) -->
  <path d="M 120,0 
           C 160,20 200,50 225,90 
           C 245,130 255,180 260,240 
           L 260,0 Z" 
        fill="#cbd5e1" opacity="0.6"/>

  <!-- The Kashmir Valley Basin (Geographic Oval Bowl) -->
  <path d="M 45,75 
           C 85,35 165,30 210,65 
           C 240,95 245,165 220,215 
           C 195,255 125,275 75,250 
           C 35,225 20,165 28,115 
           C 32,95 38,82 45,75 Z" 
        fill="url(#valleyGrad)" stroke="#93c5fd" stroke-width="2" filter="url(#kashShadow)"/>

  <!-- Snow Peak Mountain Triangles (High Altitude) -->
  <g fill="#ffffff" stroke="#94a3b8" stroke-width="1" filter="url(#kashShadow)">
    <!-- Apharwat Range -->
    <polygon points="35,70 45,45 55,70"/>
    <polygon points="48,65 60,38 72,65"/>
    <!-- Harmukh / Zabarwan Peaks -->
    <polygon points="150,45 162,25 174,45"/>
    <polygon points="170,50 182,30 194,50"/>
    <polygon points="190,60 202,38 214,60"/>
    <!-- Kolahoi / Pahalgam Peaks -->
    <polygon points="215,160 228,140 241,160"/>
    <polygon points="205,190 218,170 231,190"/>
  </g>

  <!-- Jhelum River (Meandering through the central valley) -->
  <path d="M 215,225 
           C 185,200 160,185 140,165 
           C 120,145 105,135 90,115 
           C 75,95 65,80 55,75" 
        fill="none" stroke="#3b82f6" stroke-width="3" stroke-linecap="round" opacity="0.75"/>
  <text x="138" y="185" font-family="'Inter', sans-serif" font-size="7.5" font-weight="600" fill="#2563eb">Jhelum River</text>

  <!-- Dal Lake Water Body (Near Srinagar) -->
  <path d="M 125,115 C 135,110 145,118 142,130 C 138,138 128,135 125,115 Z" 
        fill="#60a5fa" stroke="#3b82f6" stroke-width="1.5" opacity="0.9"/>
  <text x="146" y="125" font-family="'Inter', sans-serif" font-size="7.5" font-weight="700" fill="#1d4ed8">Dal Lake</text>

  <!-- Connecting Highway Route Lines -->
  <!-- Srinagar to Gulmarg (Tangmarg climb) -->
  <path d="M 115,135 Q 85,115 58,100" fill="none" stroke="#0f273d" stroke-width="3" stroke-linecap="round"/>
  <path d="M 115,135 Q 85,115 58,100" fill="none" stroke="#f59e0b" stroke-width="2" stroke-dasharray="4,4"/>

  <!-- Srinagar to Pahalgam (Lidder valley road) -->
  <path d="M 115,135 Q 155,175 195,210" fill="none" stroke="#0f273d" stroke-width="3" stroke-linecap="round"/>
  <path d="M 115,135 Q 155,175 195,210" fill="none" stroke="#f59e0b" stroke-width="2" stroke-dasharray="4,4"/>

  <!-- Gulmarg Pin (High Mountain Slope) -->
  <circle cx="58" cy="100" r="8" fill="#f59e0b" stroke="#ffffff" stroke-width="2.5" filter="url(#kashShadow)"/>
  <circle cx="58" cy="100" r="3" fill="#0f273d"/>
  <rect x="6" y="85" width="85" height="26" rx="4" fill="#ffffff" stroke="#e2e8f0" stroke-width="1" filter="url(#kashShadow)"/>
  <text x="11" y="98" font-family="'Outfit', sans-serif" font-size="9.5" font-weight="800" fill="#0f273d">Gulmarg</text>
  <text x="11" y="107" font-family="'Inter', sans-serif" font-size="7.5" font-weight="600" fill="#2563eb">2,650m – 3,980m Gondola</text>

  <!-- Srinagar Pin (Valley Basin Heart) -->
  <circle cx="115" cy="135" r="9" fill="#f59e0b" stroke="#ffffff" stroke-width="2.5" filter="url(#kashShadow)"/>
  <circle cx="115" cy="135" r="3.5" fill="#0f273d"/>
  <rect x="75" y="146" width="80" height="26" rx="4" fill="#ffffff" stroke="#e2e8f0" stroke-width="1" filter="url(#kashShadow)"/>
  <text x="80" y="158" font-family="'Outfit', sans-serif" font-size="9.5" font-weight="800" fill="#0f273d">Srinagar</text>
  <text x="80" y="167" font-family="'Inter', sans-serif" font-size="7.5" font-weight="600" fill="#0284c7">Dal Lake & Heritage</text>

  <!-- Pahalgam Pin (Pine Valley) -->
  <circle cx="195" cy="210" r="8" fill="#f59e0b" stroke="#ffffff" stroke-width="2.5" filter="url(#kashShadow)"/>
  <circle cx="195" cy="210" r="3" fill="#0f273d"/>
  <rect x="155" y="222" width="85" height="26" rx="4" fill="#ffffff" stroke="#e2e8f0" stroke-width="1" filter="url(#kashShadow)"/>
  <text x="160" y="234" font-family="'Outfit', sans-serif" font-size="9.5" font-weight="800" fill="#0f273d">Pahalgam</text>
  <text x="160" y="243" font-family="'Inter', sans-serif" font-size="7.5" font-weight="600" fill="#15803d">Lidder River & Valleys</text>

  <!-- Route Distance & Time Tags -->
  <g transform="translate(68, 122)">
    <rect x="0" y="0" width="40" height="12" rx="3" fill="#0f273d" opacity="0.85"/>
    <text x="20" y="9" font-family="'Inter', sans-serif" font-size="6.5" font-weight="700" fill="#ffffff" text-anchor="middle">51 km · 1.5h</text>
  </g>
  <g transform="translate(150, 180)">
    <rect x="0" y="0" width="40" height="12" rx="3" fill="#0f273d" opacity="0.85"/>
    <text x="20" y="9" font-family="'Inter', sans-serif" font-size="6.5" font-weight="700" fill="#ffffff" text-anchor="middle">88 km · 2.0h</text>
  </g>

  <!-- Basin Title Label -->
  <text x="80" y="45" font-family="'Outfit', sans-serif" font-size="12" font-weight="800" fill="#1e3a8a" letter-spacing="2">KASHMIR VALLEY</text>

  <!-- Compass Rose (Top Right) -->
  <g transform="translate(235, 25)">
    <circle cx="0" cy="0" r="14" fill="#ffffff" stroke="#cbd5e1" stroke-width="1" filter="url(#kashShadow)"/>
    <polygon points="0,-11 3,0 -3,0" fill="#1e3a8a"/>
    <polygon points="0,11 3,0 -3,0" fill="#94a3b8"/>
    <text x="0" y="-13" font-family="'Inter', sans-serif" font-size="7" font-weight="800" fill="#1e3a8a" text-anchor="middle">N</text>
  </g>
</svg>
"""

# Import page builder functions from previous scripts and update their map SVG
import generate_kashmir_9pages as kash_builder
import generate_kerala_9pages as ker_builder

# Monkey patch or substitute the improved maps
def get_kashmir_page1():
    h = kash_builder.page1_html()
    # Replace the mini map SVG in page 1
    start_tag = '<div class="mini-map-box"'
    end_tag = '</div>\n        </div>\n      </div>\n\n      <div class="plan-section">'
    if start_tag in h and end_tag in h:
        p1 = h[:h.find(start_tag)]
        p2 = h[h.find(end_tag):]
        h = p1 + '<div class="mini-map-box" style="padding:4px; height:185px;">' + KASHMIR_MAP_SVG + p2
    return h

def get_kashmir_page2():
    h = kash_builder.page2_html()
    # Replace the map card SVG in page 2
    start_tag = '<div style="background:#eff6ff; border:1px solid #bfdbfe;'
    end_tag = '</div>\n      </div>\n\n      <div style="display:grid; grid-template-columns: repeat(4, 1fr);'
    if start_tag in h and end_tag in h:
        p1 = h[:h.find(start_tag)]
        p2 = h[h.find(end_tag):]
        h = p1 + '<div style="background:#eff6ff; border:1px solid #bfdbfe; border-radius:10px; padding:6px; display:flex; flex-direction:column; align-items:center; height:240px;">' + KASHMIR_MAP_SVG + p2
    return h

def get_kerala_page1():
    h = ker_builder.page1_html()
    start_tag = '<div class="mini-map-box">'
    end_tag = '</div>\n        </div>\n      </div>\n\n      <div class="plan-section">'
    if start_tag in h and end_tag in h:
        p1 = h[:h.find(start_tag)]
        p2 = h[h.find(end_tag):]
        h = p1 + '<div class="mini-map-box" style="padding:4px; height:185px;">' + KERALA_MAP_SVG + p2
    return h

def get_kerala_page2():
    h = ker_builder.page2_html()
    start_tag = '<div style="background:#eef8f6; border:1px solid #c7ece6;'
    end_tag = '</div>\n      </div>\n\n      <div style="display:grid; grid-template-columns: repeat(4, 1fr);'
    if start_tag in h and end_tag in h:
        p1 = h[:h.find(start_tag)]
        p2 = h[h.find(end_tag):]
        h = p1 + '<div style="background:#eef8f6; border:1px solid #c7ece6; border-radius:10px; padding:6px; display:flex; flex-direction:column; align-items:center; height:240px;">' + KERALA_MAP_SVG + p2
    return h

def build_single_file_kashmir():
    pages = [
        get_kashmir_page1(),
        get_kashmir_page2(),
        kash_builder.page3_html(),
        kash_builder.page4_html(),
        kash_builder.page5_html(),
        kash_builder.page6_html(),
        kash_builder.page7_html(),
        kash_builder.page8_html(),
        kash_builder.page9_html(),
    ]
    content = "\n".join(pages)
    html = kash_builder.wrap_html("Voyara — Kashmir Travel Book (Complete 9-Page Dossier)", content)
    
    # Save to both target directories
    for t_dir in [ROOT_CATALOG / "kashmir_trip", PLATFORM_CATALOG / "kashmir_trip"]:
        target_file = t_dir / "kashmir_catalog.html"
        with open(target_file, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"Generated single-file: {target_file}")

def build_single_file_kerala():
    pages = [
        get_kerala_page1(),
        get_kerala_page2(),
        ker_builder.page3_html(),
        ker_builder.page4_html(),
        ker_builder.page5_html(),
        ker_builder.page6_html(),
        ker_builder.page7_html(),
        ker_builder.page8_html(),
        ker_builder.page9_html(),
    ]
    content = "\n".join(pages)
    html = ker_builder.wrap_html("Voyara — Kerala Travel Book (Complete 9-Page Dossier)", content)
    
    # Save to both target directories
    for t_dir in [ROOT_CATALOG / "kerala_trip", PLATFORM_CATALOG / "kerala_trip"]:
        target_file = t_dir / "kerala_catalog.html"
        with open(target_file, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"Generated single-file: {target_file}")

if __name__ == "__main__":
    build_single_file_kashmir()
    build_single_file_kerala()
    print("All single-file 9-page catalogs built with authentic cartographic maps and zero screenshot clutter.")
