from pathlib import Path

# Paths
ROOT_DIR = Path(r"c:\Users\vvars\OneDrive\Desktop\Iron Web")
ROOT_CATALOG = ROOT_DIR / "catalog"
PLATFORM_CATALOG = ROOT_DIR / "stitch_ai_travel_booking_platform" / "catalog"

KASHMIR_DIR = ROOT_CATALOG / "kashmir_trip"
KERALA_DIR = ROOT_CATALOG / "kerala_trip"
PLATFORM_KASHMIR_DIR = PLATFORM_CATALOG / "kashmir_trip"
PLATFORM_KERALA_DIR = PLATFORM_CATALOG / "kerala_trip"

for d in [KASHMIR_DIR, KERALA_DIR, PLATFORM_KASHMIR_DIR, PLATFORM_KERALA_DIR]:
    d.mkdir(parents=True, exist_ok=True)

COMMON_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Caveat:wght@600;700&family=Inter:wght@400;500;600;700;800&family=Playfair+Display:ital,wght@0,600;0,700;1,600&family=Outfit:wght@500;600;700;800&display=swap');

:root {
  --navy: #0f273d;
  --navy-dark: #071524;
  --teal: #10777c;
  --teal-light: #e6f4f4;
  --teal-border: #99f6e4;
  --gold: #f59e0b;
  --gold-warm: #d97706;
  --gold-bg: #fef3c7;
  --text-dark: #1e293b;
  --text-muted: #64748b;
  --card-bg: #f8fafc;
  --border-light: #e2e8f0;
  --green: #10b981;
  --green-bg: #ecfdf5;
  --blue: #2563eb;
  --blue-bg: #eff6ff;
}

* { margin:0; padding:0; box-sizing:border-box; }

body {
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
  color: var(--text-dark);
  background: #cbd5e1;
  padding: 24px 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 32px;
}

.page {
  width: 920px;
  min-height: 1300px;
  background: #ffffff;
  box-shadow: 0 20px 40px -15px rgba(0,0,0,0.25);
  border-radius: 6px;
  position: relative;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  margin-bottom: 24px;
}

/* Page 1 Cover Styles */
.top-nav {
  padding: 16px 36px 12px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: #ffffff;
}

.brand-logo {
  display: flex;
  align-items: center;
  gap: 10px;
}

.brand-title {
  font-family: 'Outfit', sans-serif;
  font-size: 24px;
  font-weight: 800;
  color: var(--navy);
  line-height: 1;
}

.brand-sub {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 2px;
  color: var(--gold-warm);
  font-weight: 600;
}

.top-slogan {
  font-family: 'Caveat', cursive;
  font-size: 20px;
  color: var(--navy);
}

.hero-wrap {
  position: relative;
  height: 310px;
  overflow: hidden;
}

.hero-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  object-position: center 35%;
}

.hero-overlay {
  position: absolute;
  inset: 0;
  background: linear-gradient(180deg, rgba(15,39,61,0.25) 0%, rgba(15,39,61,0.65) 100%);
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  padding: 24px 36px 32px;
  color: #ffffff;
}

.hero-pill {
  align-self: flex-start;
  background: linear-gradient(90deg, #f59e0b, #d97706);
  color: #ffffff;
  padding: 6px 16px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 1.5px;
  text-transform: uppercase;
  box-shadow: 0 4px 10px rgba(0,0,0,0.15);
}

.hero-vibe {
  position: absolute;
  top: 24px;
  right: 36px;
  font-family: 'Caveat', cursive;
  font-size: 26px;
  color: #ffffff;
  transform: rotate(-5deg);
  text-shadow: 0 2px 4px rgba(0,0,0,0.4);
}

.hero-title-area h1 {
  font-family: 'Outfit', sans-serif;
  font-size: 42px;
  font-weight: 800;
  line-height: 1.1;
  color: #ffffff;
  margin-bottom: 4px;
}

.hero-title-area h1 span.script {
  font-family: 'Playfair Display', serif;
  font-style: italic;
  font-weight: 600;
  color: #fbbf24;
  margin-left: 8px;
}

.hero-subtitle {
  font-size: 14px;
  color: #e2e8f0;
  max-width: 650px;
  margin-bottom: 14px;
  line-height: 1.4;
}

.hero-badges {
  display: flex;
  gap: 22px;
}

.hero-badge-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  font-weight: 500;
  color: #f1f5f9;
}

.hero-badge-item svg {
  width: 16px;
  height: 16px;
  stroke-width: 2;
}

.wave-divider {
  position: relative;
  margin-top: -30px;
  z-index: 2;
}

.wave-divider svg {
  display: block;
  width: 100%;
  height: 38px;
}

.page-body {
  padding: 0 36px 20px;
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.overview-grid {
  display: grid;
  grid-template-columns: 290px 1fr;
  gap: 20px;
}

.details-card {
  background: #f8fafc;
  border: 1px solid var(--border-light);
  border-radius: 12px;
  padding: 16px 20px;
  display: flex;
  flex-direction: column;
  gap: 11px;
}

.detail-row {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  font-size: 12px;
}

.detail-row .icon {
  width: 18px;
  height: 18px;
  color: var(--teal);
  flex-shrink: 0;
  margin-top: 1px;
}

.detail-label {
  font-size: 10.5px;
  color: var(--text-muted);
  display: block;
}

.detail-val {
  font-weight: 600;
  color: var(--navy);
}

.highlights-card {
  background: #ffffff;
  border: 1px solid var(--border-light);
  border-radius: 12px;
  padding: 18px 22px;
  display: grid;
  grid-template-columns: 1fr 180px;
  gap: 14px;
}

.highlights-title {
  font-family: 'Caveat', cursive;
  font-size: 24px;
  color: var(--navy);
  margin-bottom: 12px;
}

.highlights-list {
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.highlights-list li {
  font-size: 12px;
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--text-dark);
}

.check-icon {
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: var(--gold-bg);
  color: var(--gold-warm);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.check-icon svg {
  width: 11px;
  height: 11px;
  stroke-width: 3;
}

.mini-map-box {
  background: #eaf4f0;
  border-radius: 8px;
  padding: 10px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}

.plan-section {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.plan-section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.plan-heading {
  font-family: 'Outfit', sans-serif;
  font-size: 16px;
  font-weight: 700;
  color: var(--navy);
  display: flex;
  align-items: center;
  gap: 8px;
}

.plan-cards-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}

.plan-item-card {
  background: #ffffff;
  border: 1px solid var(--border-light);
  border-radius: 10px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.plan-card-img {
  height: 80px;
  width: 100%;
  object-fit: cover;
}

.plan-card-body {
  padding: 10px;
  display: flex;
  flex-direction: column;
  flex: 1;
  justify-content: space-between;
  gap: 8px;
}

.plan-card-type {
  font-size: 11.5px;
  font-weight: 700;
  color: var(--navy);
  margin-bottom: 2px;
}

.plan-card-details {
  font-size: 10.5px;
  color: var(--text-muted);
  line-height: 1.35;
}

.plan-card-details strong {
  color: var(--text-dark);
  display: block;
}

.bottom-callout-grid {
  display: grid;
  grid-template-columns: 210px 1fr 270px;
  gap: 16px;
  background: #f8fafc;
  border: 1px solid var(--border-light);
  border-radius: 12px;
  padding: 14px 18px;
  align-items: center;
}

.cost-text small {
  font-size: 10px;
  color: var(--text-muted);
  display: block;
}

.cost-text strong {
  font-family: 'Outfit', sans-serif;
  font-size: 20px;
  font-weight: 800;
  color: var(--navy);
}

.download-cta-btn {
  background: var(--navy);
  color: #ffffff;
  border-radius: 8px;
  padding: 10px 14px;
  display: flex;
  align-items: center;
  gap: 12px;
}

.download-cta-btn svg {
  width: 20px;
  height: 20px;
  flex-shrink: 0;
}

/* Nav header for inner pages */
.page-top-nav {
  background: var(--navy);
  color: #ffffff;
  padding: 14px 36px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.brand-box {
  display: flex;
  align-items: center;
  gap: 8px;
}

.brand-name {
  font-family: 'Outfit', sans-serif;
  font-size: 18px;
  font-weight: 800;
  color: #ffffff;
  letter-spacing: 0.5px;
}

.brand-badge {
  font-size: 9px;
  color: var(--gold);
  font-weight: 700;
  letter-spacing: 1px;
  text-transform: uppercase;
}

.page-category-tag {
  font-size: 11px;
  color: #cbd5e1;
  letter-spacing: 0.5px;
  font-weight: 500;
}

.page-hero-banner {
  padding: 24px 36px 14px;
  display: grid;
  grid-template-columns: 1fr 280px;
  gap: 24px;
  align-items: center;
}

.eyebrow {
  font-size: 11px;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: 2px;
  color: var(--text-muted);
  display: block;
  margin-bottom: 4px;
}

.page-hero-banner h1 {
  font-family: 'Outfit', sans-serif;
  font-size: 32px;
  font-weight: 800;
  color: var(--navy);
  line-height: 1.15;
  margin-bottom: 6px;
}

.page-hero-banner h1 span {
  color: var(--teal);
}

.accent-bar {
  width: 50px;
  height: 4px;
  background: var(--gold);
  border-radius: 2px;
  margin-bottom: 10px;
}

.page-hero-banner p {
  font-size: 13px;
  color: var(--text-muted);
  line-height: 1.45;
}

.page-hero-thumb {
  height: 130px;
  border-radius: 10px;
  overflow: hidden;
  box-shadow: 0 8px 20px -5px rgba(0,0,0,0.15);
}

.page-hero-thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.page-content {
  padding: 0 36px 20px;
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.page-footer {
  background: var(--navy);
  color: #ffffff;
  padding: 12px 36px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 11px;
  margin-top: auto;
}

.page-footer .meta {
  color: #94a3b8;
}

.page-footer .page-number {
  font-weight: 700;
  color: #e2e8f0;
}

/* Grids & Cards */
.grid-3 {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 14px;
}

.grid-2 {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
}

.grid-4 {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}

.card {
  background: #ffffff;
  border: 1px solid var(--border-light);
  border-radius: 10px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.card-padded {
  padding: 16px;
}

.card-header {
  font-family: 'Outfit', sans-serif;
  font-size: 14px;
  font-weight: 700;
  color: var(--navy);
  margin-bottom: 4px;
}

.tag-pill {
  display: inline-block;
  font-size: 9.5px;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: 999px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.tag-green { background: var(--green-bg); color: var(--green); border: 1px solid #a7f3d0; }
.tag-gold { background: var(--gold-bg); color: var(--gold-warm); border: 1px solid #fde68a; }
.tag-teal { background: var(--teal-light); color: var(--teal); border: 1px solid var(--teal-border); }
.tag-blue { background: var(--blue-bg); color: var(--blue); border: 1px solid #bfdbfe; }

/* Tables */
.styled-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 11.5px;
}

.styled-table th {
  background: #f1f5f9;
  color: var(--navy);
  text-align: left;
  padding: 10px 14px;
  font-weight: 700;
  border-bottom: 2px solid var(--border-light);
}

.styled-table td {
  padding: 9px 14px;
  border-bottom: 1px solid var(--border-light);
  color: var(--text-dark);
}

.styled-table tr:last-child td {
  border-bottom: none;
}

.styled-table .num {
  text-align: right;
  font-weight: 600;
}

.total-row td {
  background: #f8fafc;
  font-weight: 800;
  font-size: 13.5px;
  color: var(--navy);
  border-top: 2px solid var(--navy);
}

/* Timeline & Schedule */
.timeline-item {
  display: flex;
  gap: 14px;
  padding: 11px 0;
  border-bottom: 1px dashed var(--border-light);
}

.time-slot {
  width: 120px;
  flex-shrink: 0;
  font-weight: 700;
  font-size: 11.5px;
  color: var(--teal);
  display: flex;
  align-items: center;
  gap: 6px;
}

.timeline-body {
  flex: 1;
}

.timeline-title {
  font-size: 13px;
  font-weight: 700;
  color: var(--navy);
  margin-bottom: 2px;
}

.timeline-desc {
  font-size: 11px;
  color: var(--text-muted);
  line-height: 1.4;
}

.notice-box {
  background: #f8fafc;
  border-left: 4px solid var(--teal);
  padding: 12px 16px;
  border-radius: 0 8px 8px 0;
  font-size: 11.5px;
  color: var(--text-muted);
  line-height: 1.45;
}

.notice-box strong {
  color: var(--navy);
}

@media print {
  body { background: transparent; padding: 0; gap: 0; }
  .page { box-shadow: none; border-radius: 0; page-break-after: always; width: 100%; min-height: 100vh; margin: 0; }
}
"""

def wrap_html(title, content):
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>{title}</title>
  <style>{COMMON_CSS}</style>
</head>
<body>
{content}
</body>
</html>"""

def make_header(brand_badge, page_tag):
    return f"""
    <div class="page-top-nav">
      <div class="brand-box">
        <svg viewBox="0 0 32 32" width="22" height="22" fill="none">
          <circle cx="16" cy="16" r="14" fill="#f59e0b" fill-opacity="0.2"/>
          <path d="M16 4C9.373 4 4 9.373 4 16C4 22.627 9.373 28 16 28C22.627 28 28 22.627 28 16" stroke="#ffffff" stroke-width="2.5" stroke-linecap="round"/>
          <path d="M22 11L13 20L10 17" stroke="#f59e0b" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
        <span class="brand-name">VOYARA</span>
        <span class="brand-badge">{brand_badge}</span>
      </div>
      <div class="page-category-tag">{page_tag}</div>
    </div>
    """

def make_footer(dest, page_num, total=9):
    return f"""
    <footer class="page-footer">
      <div class="brand-box" style="gap:6px;">
        <span class="brand-name" style="font-size:13px;">VOYARA</span>
        <span class="brand-badge" style="font-size:8px;">TRAVEL BOOK</span>
      </div>
      <div class="meta">📍 {dest}, India &nbsp;|&nbsp; Verified Curated Catalog</div>
      <div class="page-number">Page {page_num} of {total}</div>
    </footer>
    """

print("Common template ready.")
