from pathlib import Path

# Paths
ROOT_CATALOG = Path(r"c:\Users\vvars\OneDrive\Desktop\Iron Web\catalog")
PLATFORM_CATALOG = Path(r"c:\Users\vvars\OneDrive\Desktop\Iron Web\stitch_ai_travel_booking_platform\catalog")
ROOT_CATALOG.mkdir(parents=True, exist_ok=True)
PLATFORM_CATALOG.mkdir(parents=True, exist_ok=True)

# Shared CSS styles replicating the user's provided images
COMMON_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Caveat:wght@600;700&family=Inter:wght@400;500;600;700&family=Playfair+Display:ital,wght@0,600;0,700;1,600&family=Outfit:wght@500;600;700;800&display=swap');

:root {
  --navy: #0f273d;
  --navy-dark: #0a1b2b;
  --teal: #10777c;
  --teal-light: #e6f4f4;
  --gold: #f59e0b;
  --gold-warm: #d97706;
  --gold-bg: #fef3c7;
  --text-dark: #1e293b;
  --text-muted: #64748b;
  --card-bg: #f8fafc;
  --border-light: #e2e8f0;
  --green: #10b981;
  --green-bg: #ecfdf5;
}

* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

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

.page-container {
  width: 920px;
  min-height: 1300px;
  background: #ffffff;
  box-shadow: 0 20px 40px -15px rgba(0,0,0,0.25);
  border-radius: 6px;
  position: relative;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

/* Page 1 Header */
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

.brand-logo svg {
  width: 38px;
  height: 38px;
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
  display: flex;
  align-items: center;
  gap: 6px;
}

/* Hero Section */
.hero-wrap {
  position: relative;
  height: 320px;
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
  margin-bottom: 16px;
  line-height: 1.4;
}

.hero-badges {
  display: flex;
  gap: 24px;
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

/* Wavy separator */
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

/* Page Body */
.page-body {
  padding: 0 36px 20px;
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

/* Middle Split Section */
.overview-grid {
  display: grid;
  grid-template-columns: 290px 1fr;
  gap: 20px;
}

.details-card {
  background: #f8fafc;
  border: 1px solid var(--border-light);
  border-radius: 12px;
  padding: 18px 20px;
  display: flex;
  flex-direction: column;
  gap: 12px;
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
  font-size: 11px;
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
  position: relative;
}

.highlights-title {
  font-family: 'Caveat', cursive;
  font-size: 24px;
  color: var(--navy);
  margin-bottom: 12px;
  display: flex;
  align-items: center;
  gap: 6px;
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
  position: relative;
}

/* Travel Plan Section */
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

.plan-more-link {
  font-size: 12px;
  font-weight: 600;
  color: var(--teal);
  text-decoration: none;
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
  height: 85px;
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
  font-size: 12px;
  font-weight: 700;
  color: var(--navy);
  display: flex;
  align-items: center;
  gap: 6px;
}

.plan-card-details {
  font-size: 10.5px;
  color: var(--text-muted);
  line-height: 1.35;
}

.plan-card-details strong {
  color: var(--text-dark);
  font-weight: 600;
  display: block;
  margin-bottom: 2px;
}

.plan-card-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-top: 6px;
  border-top: 1px solid #f1f5f9;
}

.btn-ghost {
  font-size: 10px;
  font-weight: 600;
  color: var(--text-muted);
  border: 1px solid var(--border-light);
  padding: 3px 8px;
  border-radius: 4px;
  background: transparent;
}

.pill-confirmed {
  font-size: 9.5px;
  font-weight: 700;
  background: var(--green-bg);
  color: var(--green);
  padding: 3px 8px;
  border-radius: 999px;
  border: 1px solid #a7f3d0;
}

.pill-selected {
  font-size: 9.5px;
  font-weight: 700;
  background: var(--teal-light);
  color: var(--teal);
  padding: 3px 8px;
  border-radius: 999px;
  border: 1px solid #99f6e4;
}

/* Callout Bar */
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

.callout-cost {
  display: flex;
  align-items: center;
  gap: 10px;
}

.cost-icon-box {
  width: 38px;
  height: 38px;
  border-radius: 8px;
  background: var(--gold-bg);
  color: var(--gold-warm);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
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

.callout-status {
  display: flex;
  align-items: center;
  gap: 10px;
  border-left: 1px solid var(--border-light);
  padding-left: 16px;
}

.status-icon-box {
  width: 38px;
  height: 38px;
  border-radius: 8px;
  background: #fed7aa;
  color: #ea580c;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.status-text strong {
  font-size: 11px;
  color: #ea580c;
  display: block;
  font-weight: 700;
}

.status-text small {
  font-size: 10px;
  color: var(--text-muted);
  line-height: 1.25;
  display: block;
}

.download-cta-btn {
  background: var(--navy);
  color: #ffffff;
  border-radius: 8px;
  padding: 10px 14px;
  display: flex;
  align-items: center;
  gap: 12px;
  text-decoration: none;
  cursor: pointer;
}

.download-cta-btn svg {
  width: 22px;
  height: 22px;
  color: #ffffff;
  flex-shrink: 0;
}

.download-cta-text strong {
  font-size: 12px;
  font-weight: 700;
  display: block;
}

.download-cta-text small {
  font-size: 9.5px;
  color: #94a3b8;
  display: block;
}

/* Footer */
.catalog-footer {
  background: var(--navy);
  color: #ffffff;
  padding: 16px 36px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  position: relative;
  overflow: hidden;
}

.footer-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.footer-left .brand-title {
  color: #ffffff;
}

.footer-center {
  font-family: 'Caveat', cursive;
  font-size: 22px;
  color: #ffffff;
}

.footer-right {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 10px;
  color: #94a3b8;
}

.footer-qr {
  width: 32px;
  height: 32px;
  background: #ffffff;
  border-radius: 4px;
  padding: 2px;
}

/* PAGE 2 STYLES */
.page2-header {
  background: var(--navy);
  color: #ffffff;
  padding: 14px 36px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.page2-header .slogan {
  font-size: 12px;
  color: #cbd5e1;
  letter-spacing: 0.5px;
}

.page2-hero {
  padding: 28px 36px 16px;
  display: grid;
  grid-template-columns: 1fr 340px;
  gap: 28px;
  align-items: center;
}

.page2-hero-copy .eyebrow {
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 2px;
  color: var(--text-muted);
  display: block;
  margin-bottom: 4px;
}

.page2-hero-copy h1 {
  font-family: 'Outfit', sans-serif;
  font-size: 38px;
  font-weight: 800;
  color: var(--navy);
  line-height: 1.1;
  margin-bottom: 8px;
}

.page2-hero-copy h1 span {
  color: var(--teal);
}

.page2-hero-copy .accent-line {
  width: 60px;
  height: 4px;
  background: var(--gold);
  border-radius: 2px;
  margin-bottom: 12px;
}

.page2-hero-copy p {
  font-size: 13.5px;
  color: var(--text-muted);
  line-height: 1.5;
}

.page2-hero-img-box {
  height: 180px;
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 10px 25px -5px rgba(0,0,0,0.15);
}

.page2-hero-img-box img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

/* What makes it special */
.special-section {
  padding: 0 36px;
}

.special-box {
  background: #f0fdfa;
  border: 1px solid #ccfbf1;
  border-radius: 12px;
  padding: 14px 20px;
  display: flex;
  align-items: center;
  gap: 24px;
}

.special-title {
  font-family: 'Outfit', sans-serif;
  font-size: 15px;
  font-weight: 700;
  color: var(--navy);
  line-height: 1.2;
  width: 140px;
  flex-shrink: 0;
}

.special-pills {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  flex: 1;
}

.special-pill-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  text-align: center;
  font-size: 10.5px;
  font-weight: 600;
  color: var(--navy);
}

.special-icon-circle {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: #14b8a6;
  color: #ffffff;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 2px 6px rgba(20,184,166,0.3);
}

.special-icon-circle svg {
  width: 18px;
  height: 18px;
}

/* Selected destinations section */
.destinations-section {
  padding: 0 36px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.destinations-header h2 {
  font-family: 'Outfit', sans-serif;
  font-size: 18px;
  font-weight: 800;
  color: var(--navy);
}

.destinations-header p {
  font-size: 12px;
  color: var(--text-muted);
}

.destinations-layout {
  display: grid;
  grid-template-columns: repeat(3, 1fr) 220px;
  gap: 14px;
}

.destination-card {
  background: #ffffff;
  border: 1px solid var(--border-light);
  border-radius: 10px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.destination-img-box {
  position: relative;
  height: 110px;
}

.destination-img-box img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.dest-selected-tag {
  position: absolute;
  top: 8px;
  left: 8px;
  background: rgba(16,185,129,0.92);
  color: #ffffff;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 9px;
  font-weight: 700;
}

.destination-card-content {
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  flex: 1;
}

.destination-card-content h3 {
  font-family: 'Outfit', sans-serif;
  font-size: 14px;
  font-weight: 700;
  color: var(--navy);
}

.destination-card-content .dest-summary {
  font-size: 11px;
  color: var(--text-muted);
  line-height: 1.35;
  margin-bottom: 4px;
}

.dest-exp-list-title {
  font-size: 10.5px;
  font-weight: 700;
  color: var(--navy);
  display: flex;
  align-items: center;
  gap: 4px;
}

.dest-exp-list {
  list-style: none;
  font-size: 10px;
  color: var(--text-dark);
  display: flex;
  flex-direction: column;
  gap: 3px;
  padding-left: 2px;
}

.dest-exp-list li::before {
  content: "• ";
  color: var(--teal);
  font-weight: bold;
}

.map-card-box {
  background: #eef8f6;
  border: 1px solid #c7ece6;
  border-radius: 10px;
  padding: 12px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: space-between;
  text-align: center;
}

.map-card-box h4 {
  font-family: 'Outfit', sans-serif;
  font-size: 13px;
  font-weight: 700;
  color: var(--navy);
}

.map-card-box .map-slogan {
  font-family: 'Caveat', cursive;
  font-size: 18px;
  color: #d97706;
}

/* Bottom info section */
.bottom-info-row {
  padding: 0 36px 20px;
  display: grid;
  grid-template-columns: 1fr 240px;
  gap: 16px;
}

.info-grid-card {
  background: #f0f9ff;
  border: 1px solid #e0f2fe;
  border-radius: 10px;
  padding: 14px 18px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.info-grid-title {
  font-family: 'Outfit', sans-serif;
  font-size: 13px;
  font-weight: 700;
  color: var(--navy);
}

.info-cols {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 10px;
}

.info-col-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 10.5px;
}

.info-col-item .info-label {
  color: var(--text-muted);
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 10px;
  font-weight: 600;
}

.info-col-item .info-val {
  font-weight: 600;
  color: var(--navy);
  line-height: 1.3;
}

.promo-card {
  background: linear-gradient(135deg, #e0f2fe 0%, #dbeafe 100%);
  border: 1px solid #bfdbfe;
  border-radius: 10px;
  padding: 14px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  position: relative;
  overflow: hidden;
}

.promo-card-bg-img {
  position: absolute;
  right: 0;
  bottom: 0;
  width: 120px;
  height: 90px;
  object-fit: cover;
  opacity: 0.85;
  border-radius: 8px 0 0 0;
}

.promo-card-content {
  position: relative;
  z-index: 2;
}

.promo-card h3 {
  font-family: 'Playfair Display', serif;
  font-style: italic;
  font-size: 18px;
  color: var(--navy);
  margin-bottom: 6px;
}

.promo-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  background: var(--navy);
  color: #ffffff;
  padding: 6px 12px;
  border-radius: 6px;
  font-size: 10.5px;
  font-weight: 600;
  text-decoration: none;
  align-self: flex-start;
  margin-top: 10px;
}

/* Page 2 Footer */
.page2-footer {
  background: var(--navy);
  color: #ffffff;
  padding: 12px 36px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 11px;
}

.page2-footer .meta {
  color: #94a3b8;
}

/* AI Council Specific Badge */
.ai-council-banner {
  background: linear-gradient(90deg, #1e1b4b 0%, #312e81 50%, #1e1b4b 100%);
  color: #ffffff;
  padding: 8px 18px;
  border-radius: 8px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
  border: 1px solid #4338ca;
}

.ai-council-badge-left {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.5px;
}

.ai-council-score-pill {
  background: #10b981;
  color: #ffffff;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 800;
}

.ai-agent-breakdown {
  display: flex;
  gap: 16px;
  font-size: 10px;
  color: #c7d2fe;
}

@media print {
  body {
    background: transparent;
    padding: 0;
    gap: 0;
  }
  .page-container {
    box-shadow: none;
    border-radius: 0;
    page-break-after: always;
    margin: 0;
    width: 100%;
    min-height: 100vh;
  }
}
"""

def generate_kerala_html():
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Voyara — Your Kerala Escape (Manual Catalog)</title>
  <style>{COMMON_CSS}</style>
</head>
<body>

  <!-- PAGE 1: COVER & TRAVEL PLAN -->
  <div class="page-container" id="page1">
    
    <!-- Top Nav -->
    <header class="top-nav">
      <div class="brand-logo">
        <svg viewBox="0 0 40 40" fill="none">
          <circle cx="20" cy="20" r="18" fill="#f59e0b" fill-opacity="0.15"/>
          <path d="M20 4C11.163 4 4 11.163 4 20C4 28.837 11.163 36 20 36C28.837 36 36 28.837 36 20" stroke="#0f273d" stroke-width="3" stroke-linecap="round"/>
          <path d="M28 14L16 26L12 22" stroke="#f59e0b" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
        <div>
          <div class="brand-title">Voyara</div>
          <div class="brand-sub">Tours • Travels</div>
        </div>
      </div>
      <div class="top-slogan">
        More Destinations More Stories ✈ ♡
      </div>
    </header>

    <!-- Hero Image Area -->
    <div class="hero-wrap">
      <img class="hero-img" src="https://images.unsplash.com/photo-1602216056096-3b40cc0c9944?auto=format&fit=crop&w=1400&q=85" alt="Kerala Houseboat Backwaters">
      <div class="hero-overlay">
        <div style="display:flex; justify-content:space-between; width:100%;">
          <div class="hero-pill">YOUR PERSONAL TRAVEL BOOK</div>
          <div class="hero-vibe">Good Vibes Only ♡</div>
        </div>
        <div class="hero-title-area">
          <h1>Your Kerala<span class="script">Escape</span></h1>
          <p class="hero-subtitle">Backwaters, beaches, hills and a whole lot of memories. Your perfect getaway is here!</p>
          <div class="hero-badges">
            <div class="hero-badge-item">
              <svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/></svg>
              Nature & Relaxation
            </div>
            <div class="hero-badge-item">
              <svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4"/></svg>
              Culture & Heritage
            </div>
            <div class="hero-badge-item">
              <svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M3 3v18h18"/></svg>
              Local Cuisine
            </div>
            <div class="hero-badge-item">
              <svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z"/><path d="M15 13a3 3 0 11-6 0 3 3 0 016 0z"/></svg>
              Scenic Experiences
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Wave divider -->
    <div class="wave-divider">
      <svg viewBox="0 0 920 38" fill="none" preserveAspectRatio="none">
        <path d="M0,0 C150,30 350,38 460,20 C600,0 750,25 920,10 L920,38 L0,38 Z" fill="#ffffff"/>
      </svg>
    </div>

    <!-- Page Body -->
    <div class="page-body">
      
      <!-- Details & Highlights Grid -->
      <div class="overview-grid">
        
        <!-- Left: Trip Details -->
        <div class="details-card">
          <div class="detail-row">
            <svg class="icon" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"/><path d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"/></svg>
            <div>
              <span class="detail-label">Destination</span>
              <span class="detail-val">Kerala, India</span>
            </div>
          </div>
          <div class="detail-row">
            <svg class="icon" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"/></svg>
            <div>
              <span class="detail-label">Travel Dates</span>
              <span class="detail-val">12 – 18 December 2026</span>
            </div>
          </div>
          <div class="detail-row">
            <svg class="icon" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
            <div>
              <span class="detail-label">Duration</span>
              <span class="detail-val">7 Days, 6 Nights</span>
            </div>
          </div>
          <div class="detail-row">
            <svg class="icon" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z"/></svg>
            <div>
              <span class="detail-label">Travelers</span>
              <span class="detail-val">2 Adults</span>
            </div>
          </div>
          <div class="detail-row">
            <svg class="icon" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"/></svg>
            <div>
              <span class="detail-label">Starting Point</span>
              <span class="detail-val">New Delhi</span>
            </div>
          </div>
          <div class="detail-row">
            <svg class="icon" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7"/></svg>
            <div>
              <span class="detail-label">Destinations</span>
              <span class="detail-val">Kochi → Munnar → Alleppey</span>
            </div>
          </div>
          <div class="detail-row">
            <svg class="icon" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z"/></svg>
            <div>
              <span class="detail-label">Travel Style</span>
              <span class="detail-val">Nature, Relaxation & Cultural Experience</span>
            </div>
          </div>
        </div>

        <!-- Right: Trip Highlights + Map -->
        <div class="highlights-card">
          <div>
            <div class="highlights-title">☀ Trip Highlights</div>
            <ul class="highlights-list">
              <li>
                <div class="check-icon"><svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M5 13l4 4L19 7"/></svg></div>
                Stay in handpicked 4★ hotels
              </li>
              <li>
                <div class="check-icon"><svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M5 13l4 4L19 7"/></svg></div>
                Explore vibrant Kochi and its heritage
              </li>
              <li>
                <div class="check-icon"><svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M5 13l4 4L19 7"/></svg></div>
                Scenic drive to Munnar's tea gardens
              </li>
              <li>
                <div class="check-icon"><svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M5 13l4 4L19 7"/></svg></div>
                Relax with a serene backwaters cruise
              </li>
              <li>
                <div class="check-icon"><svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M5 13l4 4L19 7"/></svg></div>
                Experience authentic Kerala cuisine
              </li>
              <li>
                <div class="check-icon"><svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M5 13l4 4L19 7"/></svg></div>
                Private cab for comfortable travel
              </li>
            </ul>
          </div>

          <!-- Mini Map SVG -->
          <div class="mini-map-box">
            <svg viewBox="0 0 160 210" width="100%" height="100%">
              <!-- Kerala Shape Silhouette -->
              <path d="M 65,15 Q 95,30 110,65 Q 115,110 95,150 Q 80,185 60,200 Q 55,160 50,110 Q 40,60 65,15 Z" fill="#bbf7d0" stroke="#86efac" stroke-width="1.5"/>
              
              <!-- Route Dashed Line -->
              <path d="M 52,105 L 98,68 L 68,145" fill="none" stroke="#0f273d" stroke-width="2" stroke-dasharray="4,4"/>
              
              <!-- Munnar Pin -->
              <circle cx="98" cy="68" r="6" fill="#f59e0b" stroke="#ffffff" stroke-width="2"/>
              <text x="108" y="72" font-size="10" font-weight="700" fill="#0f273d" font-family="Inter">Munnar</text>
              
              <!-- Kochi Pin -->
              <circle cx="52" cy="105" r="6" fill="#f59e0b" stroke="#ffffff" stroke-width="2"/>
              <text x="8" y="109" font-size="10" font-weight="700" fill="#0f273d" font-family="Inter">Kochi</text>
              
              <!-- Alleppey Pin -->
              <circle cx="68" cy="145" r="6" fill="#f59e0b" stroke="#ffffff" stroke-width="2"/>
              <text x="78" y="149" font-size="10" font-weight="700" fill="#0f273d" font-family="Inter">Alleppey</text>

              <!-- State label -->
              <text x="75" y="125" font-size="11" font-weight="800" fill="#059669" letter-spacing="1.5" font-family="Outfit">KERALA</text>
              <text x="140" y="25" font-size="9" font-weight="700" fill="#64748b">N</text>
              <path d="M 143,15 L 143,8" stroke="#64748b" stroke-width="1.5" marker-end="url(#arrow)"/>
            </svg>
          </div>
        </div>

      </div>

      <!-- Selected Travel Plan -->
      <div class="plan-section">
        <div class="plan-section-header">
          <div class="plan-heading">
            <svg width="18" height="18" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"/></svg>
            Your Selected Travel Plan
          </div>
          <a href="#itinerary" class="plan-more-link">View Full Itinerary →</a>
        </div>

        <div class="plan-cards-grid">
          
          <!-- Flights -->
          <div class="plan-item-card">
            <img class="plan-card-img" src="https://images.unsplash.com/photo-1436491865332-7a61a109cc05?auto=format&fit=crop&w=600&q=80" alt="Flight">
            <div class="plan-card-body">
              <div>
                <div class="plan-card-type">✈ Flights</div>
                <div class="plan-card-details">
                  <strong>Delhi → Kochi</strong>
                  IndiGo • 6E 123<br>
                  12 Dec 2026 • 08:00 AM
                </div>
              </div>
              <div class="plan-card-actions">
                <button class="btn-ghost">View Ticket</button>
                <span class="pill-confirmed">Confirmed</span>
              </div>
            </div>
          </div>

          <!-- Hotels -->
          <div class="plan-item-card">
            <img class="plan-card-img" src="https://images.unsplash.com/photo-1582719478250-c89cae4dc85b?auto=format&fit=crop&w=600&q=80" alt="Resort">
            <div class="plan-card-body">
              <div>
                <div class="plan-card-type">🏨 Hotels</div>
                <div class="plan-card-details">
                  <strong>Kochi</strong> Hotel Grand Hyatt (2N)<br>
                  <strong>Munnar</strong> Tea Mount Resort (2N)<br>
                  <strong>Alleppey</strong> Backwater Retreat (2N)
                </div>
              </div>
              <div class="plan-card-actions">
                <button class="btn-ghost">View Hotels</button>
                <span class="pill-confirmed">Confirmed</span>
              </div>
            </div>
          </div>

          <!-- Experiences -->
          <div class="plan-item-card">
            <img class="plan-card-img" src="https://images.unsplash.com/photo-1602216056096-3b40cc0c9944?auto=format&fit=crop&w=600&q=80" alt="Kathakali">
            <div class="plan-card-body">
              <div>
                <div class="plan-card-type">📷 Experiences</div>
                <div class="plan-card-details">
                  <strong>Kochi Sightseeing Tour</strong><br>
                  Munnar Tea Plantation Tour<br>
                  Alleppey Houseboat Cruise
                </div>
              </div>
              <div class="plan-card-actions">
                <button class="btn-ghost">View Details</button>
                <span class="pill-selected">Selected</span>
              </div>
            </div>
          </div>

          <!-- Transport -->
          <div class="plan-item-card">
            <img class="plan-card-img" src="https://images.unsplash.com/photo-1549317661-bd32c8ce0db2?auto=format&fit=crop&w=600&q=80" alt="Cab">
            <div class="plan-card-body">
              <div>
                <div class="plan-card-type">🚗 Transport</div>
                <div class="plan-card-details">
                  <strong>Private Cab (Kochi → Munnar)</strong><br>
                  Private Cab (Munnar → Alleppey)<br>
                  Local Transfers & Airport Pickup
                </div>
              </div>
              <div class="plan-card-actions">
                <button class="btn-ghost">View Details</button>
                <span class="pill-confirmed">Confirmed</span>
              </div>
            </div>
          </div>

        </div>
      </div>

      <!-- Cost, Status & Download Bar -->
      <div class="bottom-callout-grid">
        <div class="callout-cost">
          <div class="cost-icon-box">
            <svg width="22" height="22" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
          </div>
          <div class="cost-text">
            <small>Estimated Trip Cost</small>
            <strong>₹ 65,000</strong> <small style="display:inline;">per person</small>
          </div>
        </div>

        <div class="callout-status">
          <div class="status-icon-box">
            <svg width="20" height="20" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/></svg>
          </div>
          <div class="status-text">
            <strong>Draft — Awaiting Confirmation</strong>
            <small>You can still make changes before finalizing and proceeding to payment.</small>
          </div>
        </div>

        <div class="download-cta-btn">
          <svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/></svg>
          <div class="download-cta-text">
            <strong>Download Travel Book</strong>
            <small>Get your complete trip details in a beautiful PDF format.</small>
          </div>
        </div>
      </div>

    </div>

    <!-- Footer -->
    <footer class="catalog-footer">
      <div class="footer-left">
        <svg viewBox="0 0 32 32" width="28" height="28" fill="none">
          <circle cx="16" cy="16" r="14" fill="#f59e0b" fill-opacity="0.2"/>
          <path d="M16 4C9.373 4 4 9.373 4 16C4 22.627 9.373 28 16 28C22.627 28 28 22.627 28 16" stroke="#ffffff" stroke-width="2.5" stroke-linecap="round"/>
          <path d="M22 11L13 20L10 17" stroke="#f59e0b" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
        <div>
          <span class="brand-title" style="font-size:18px;">Voyara</span>
          <span style="font-size:9px; color:#f59e0b; display:block; letter-spacing:1px; text-transform:uppercase;">Tours • Travels</span>
        </div>
      </div>
      <div class="footer-center">
        Let's turn your travel dreams into plans ♡
      </div>
      <div class="footer-right">
        <div class="footer-qr">
          <svg viewBox="0 0 24 24" width="100%" height="100%" fill="#0f273d">
            <rect x="2" y="2" width="8" height="8" rx="1"/>
            <rect x="14" y="2" width="8" height="8" rx="1"/>
            <rect x="2" y="14" width="8" height="8" rx="1"/>
            <rect x="14" y="14" width="4" height="4"/>
            <rect x="18" y="18" width="4" height="4"/>
          </svg>
        </div>
        <span>Scan to view your trip<br>in the Voyara app</span>
      </div>
    </footer>

  </div>


  <!-- PAGE 2: DISCOVER DESTINATION -->
  <div class="page-container" id="page2">
    
    <!-- Top Bar -->
    <div class="page2-header">
      <div class="brand-logo">
        <svg viewBox="0 0 32 32" width="24" height="24" fill="none">
          <circle cx="16" cy="16" r="14" fill="#f59e0b" fill-opacity="0.2"/>
          <path d="M16 4C9.373 4 4 9.373 4 16C4 22.627 9.373 28 16 28C22.627 28 28 22.627 28 16" stroke="#ffffff" stroke-width="2.5" stroke-linecap="round"/>
          <path d="M22 11L13 20L10 17" stroke="#f59e0b" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
        <span style="font-family:'Outfit',sans-serif; font-size:18px; font-weight:800; color:#fff;">VOYARA</span>
        <span style="font-size:9px; color:#f59e0b; font-weight:600; letter-spacing:1px;">TOURS & TRAVELS</span>
      </div>
      <div class="slogan">More Than a Trip — A Story to Tell</div>
    </div>

    <!-- Discover Kerala Hero -->
    <div class="page2-hero">
      <div class="page2-hero-copy">
        <span class="eyebrow">YOUR DESTINATION</span>
        <h1>Discover <span>Kerala</span></h1>
        <div class="accent-line"></div>
        <p>Tropical beaches, misty hills, serene backwaters and a rich cultural heritage — Kerala is a paradise that feels like home.</p>
      </div>
      <div class="page2-hero-img-box">
        <img src="https://images.unsplash.com/photo-1602216056096-3b40cc0c9944?auto=format&fit=crop&w=800&q=80" alt="Houseboat on serene backwaters">
      </div>
    </div>

    <!-- What Makes Kerala Special? -->
    <div class="special-section">
      <div class="special-box">
        <div class="special-title">What makes Kerala special?</div>
        <div class="special-pills">
          <div class="special-pill-item">
            <div class="special-icon-circle">
              <svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z"/></svg>
            </div>
            <span>Lush Nature</span>
          </div>
          <div class="special-pill-item">
            <div class="special-icon-circle">
              <svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M13 10V3L4 14h7v7l9-11h-7z"/></svg>
            </div>
            <span>Backwater Experiences</span>
          </div>
          <div class="special-pill-item">
            <div class="special-icon-circle">
              <svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"/></svg>
            </div>
            <span>Local Cuisine</span>
          </div>
          <div class="special-pill-item">
            <div class="special-icon-circle">
              <svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4"/></svg>
            </div>
            <span>Culture & Heritage</span>
          </div>
          <div class="special-pill-item">
            <div class="special-icon-circle">
              <svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z"/></svg>
            </div>
            <span>Beaches & Relaxation</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Your Selected Destinations -->
    <div class="destinations-section">
      <div class="destinations-header">
        <h2>Your Selected Destinations</h2>
        <p>Explore the best of Kerala with your chosen destinations.</p>
      </div>

      <div class="destinations-layout">
        
        <!-- Kochi Card -->
        <div class="destination-card">
          <div class="destination-img-box">
            <img src="https://images.unsplash.com/photo-1590490360182-c33d57733427?auto=format&fit=crop&w=500&q=80" alt="Kochi Chinese Fishing Nets">
            <span class="dest-selected-tag">✔ Selected</span>
          </div>
          <div class="destination-card-content">
            <h3>Kochi</h3>
            <p class="dest-summary">Colonial charm, vibrant markets and rich culture.</p>
            <div class="dest-exp-list-title">📍 Key Experiences</div>
            <ul class="dest-exp-list">
              <li>Fort Kochi sightseeing</li>
              <li>Chinese fishing nets</li>
              <li>Local food walk</li>
            </ul>
          </div>
        </div>

        <!-- Munnar Card -->
        <div class="destination-card">
          <div class="destination-img-box">
            <img src="https://images.unsplash.com/photo-1512343879784-a960bf40e7f2?auto=format&fit=crop&w=500&q=80" alt="Munnar Tea Hills">
            <span class="dest-selected-tag">✔ Selected</span>
          </div>
          <div class="destination-card-content">
            <h3>Munnar</h3>
            <p class="dest-summary">Misty hills, tea gardens and breathtaking views.</p>
            <div class="dest-exp-list-title">📍 Key Experiences</div>
            <ul class="dest-exp-list">
              <li>Tea plantation tour</li>
              <li>Mattupetty Lake</li>
              <li>Scenic viewpoints</li>
            </ul>
          </div>
        </div>

        <!-- Alleppey Card -->
        <div class="destination-card">
          <div class="destination-img-box">
            <img src="https://images.unsplash.com/photo-1602216056096-3b40cc0c9944?auto=format&fit=crop&w=500&q=80" alt="Alleppey Backwaters">
            <span class="dest-selected-tag">✔ Selected</span>
          </div>
          <div class="destination-card-content">
            <h3>Alleppey</h3>
            <p class="dest-summary">Serene backwaters and traditional village life.</p>
            <div class="dest-exp-list-title">📍 Key Experiences</div>
            <ul class="dest-exp-list">
              <li>Houseboat cruise</li>
              <li>Village tour</li>
              <li>Sunset views</li>
            </ul>
          </div>
        </div>

        <!-- Kerala at a Glance (Map) -->
        <div class="map-card-box">
          <h4>Kerala at a Glance</h4>
          <svg viewBox="0 0 150 180" width="100%" height="130">
            <path d="M 60,10 Q 90,25 105,55 Q 110,95 90,135 Q 75,165 55,175 Q 50,140 45,95 Q 35,50 60,10 Z" fill="#a7f3d0" stroke="#6ee7b7" stroke-width="1.5"/>
            <path d="M 48,90 L 92,58 L 64,125" fill="none" stroke="#047857" stroke-width="2" stroke-dasharray="3,3"/>
            <circle cx="92" cy="58" r="5" fill="#047857"/>
            <text x="100" y="61" font-size="9" font-weight="700" fill="#0f273d" font-family="Inter">Munnar</text>
            <circle cx="48" cy="90" r="5" fill="#047857"/>
            <text x="15" y="93" font-size="9" font-weight="700" fill="#0f273d" font-family="Inter">Kochi</text>
            <circle cx="64" cy="125" r="5" fill="#047857"/>
            <text x="72" y="128" font-size="9" font-weight="700" fill="#0f273d" font-family="Inter">Alleppey</text>
            <text x="10" y="150" font-size="8" fill="#0d9488" font-family="Inter">Arabian<br>Sea</text>
          </svg>
          <div class="map-slogan">Same state, endless experiences</div>
        </div>

      </div>
    </div>

    <!-- Travel Information & Promo Card -->
    <div class="bottom-info-row">
      <div class="info-grid-card">
        <div class="info-grid-title">Travel Information</div>
        <div class="info-cols">
          <div class="info-col-item">
            <span class="info-label">📅 Best Time to Visit</span>
            <span class="info-val">Oct – Mar<br><small style="color:#64748b; font-weight:normal;">(Pleasant weather)</small></span>
          </div>
          <div class="info-col-item">
            <span class="info-label">☀ Weather</span>
            <span class="info-val">24°C – 32°C<br><small style="color:#64748b; font-weight:normal;">(Varies by region)</small></span>
          </div>
          <div class="info-col-item">
            <span class="info-label">🍴 Local Cuisine</span>
            <span class="info-val">Appam, Kerala Sadya, Seafood</span>
          </div>
          <div class="info-col-item">
            <span class="info-label">🧳 Packing Tips</span>
            <span class="info-val">Light clothes, comfortable shoes, sunscreen</span>
          </div>
        </div>
      </div>

      <div class="promo-card">
        <img class="promo-card-bg-img" src="https://images.unsplash.com/photo-1590490360182-c33d57733427?auto=format&fit=crop&w=400&q=80" alt="Kerala Beach">
        <div class="promo-card-content">
          <h3>Kerala Awaits You</h3>
          <a href="#destination/Kerala" class="promo-btn">View Destination Guide ↗</a>
        </div>
      </div>
    </div>

    <!-- Page 2 Footer -->
    <footer class="page2-footer">
      <div class="brand-logo" style="gap:6px;">
        <span style="font-family:'Outfit',sans-serif; font-size:14px; font-weight:800; color:#fff;">VOYARA</span>
        <span style="font-size:8px; color:#f59e0b; font-weight:600;">TOURS & TRAVELS</span>
      </div>
      <div class="meta">📍 Kerala, India &nbsp;|&nbsp; Your Journey, Our Expertise</div>
      <div style="font-weight:700; color:#cbd5e1;">Page 2 of 8</div>
    </footer>

  </div>

</body>
</html>
"""

def generate_kashmir_html():
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Voyara — Your Kashmir Escape (AI + Catalog)</title>
  <style>{COMMON_CSS}</style>
</head>
<body>

  <!-- PAGE 1: COVER & AI-EVALUATED TRAVEL PLAN -->
  <div class="page-container" id="page1">
    
    <!-- Top Nav with AI Council Badge -->
    <header class="top-nav">
      <div class="brand-logo">
        <svg viewBox="0 0 40 40" fill="none">
          <circle cx="20" cy="20" r="18" fill="#f59e0b" fill-opacity="0.15"/>
          <path d="M20 4C11.163 4 4 11.163 4 20C4 28.837 11.163 36 20 36C28.837 36 36 28.837 36 20" stroke="#0f273d" stroke-width="3" stroke-linecap="round"/>
          <path d="M28 14L16 26L12 22" stroke="#f59e0b" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
        <div>
          <div class="brand-title">Voyara</div>
          <div class="brand-sub">Tours • Travels</div>
        </div>
      </div>
      <div class="top-slogan">
        AI Multi-Agent Verified Itinerary ⚡ ♡
      </div>
    </header>

    <!-- Hero Image Area (Snow / Dal Lake) -->
    <div class="hero-wrap">
      <img class="hero-img" src="https://images.unsplash.com/photo-1595815771614-ade9d652a65d?auto=format&fit=crop&w=1400&q=85" alt="Kashmir Dal Lake and Snow Peaks">
      <div class="hero-overlay">
        <div style="display:flex; justify-content:space-between; width:100%;">
          <div class="hero-pill">YOUR PERSONAL TRAVEL BOOK · AI COUNCIL CERTIFIED</div>
          <div class="hero-vibe">Alpine Paradise ♡</div>
        </div>
        <div class="hero-title-area">
          <h1>Your Kashmir<span class="script">Escape</span></h1>
          <p class="hero-subtitle">Snow-capped peaks, shikara mornings, pine forests and royal Wazwan feasts. Evaluated by 4 AI Travel Agents!</p>
          <div class="hero-badges">
            <div class="hero-badge-item">
              <svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/></svg>
              Alpine Snow & Meadows
            </div>
            <div class="hero-badge-item">
              <svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4"/></svg>
              Heritage Houseboats
            </div>
            <div class="hero-badge-item">
              <svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M3 3v18h18"/></svg>
              7-Course Wazwan Trail
            </div>
            <div class="hero-badge-item">
              <svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z"/><path d="M15 13a3 3 0 11-6 0 3 3 0 016 0z"/></svg>
              Gulmarg Gondola
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Wave divider -->
    <div class="wave-divider">
      <svg viewBox="0 0 920 38" fill="none" preserveAspectRatio="none">
        <path d="M0,0 C150,30 350,38 460,20 C600,0 750,25 920,10 L920,38 L0,38 Z" fill="#ffffff"/>
      </svg>
    </div>

    <!-- Page Body -->
    <div class="page-body">
      
      <!-- AI Council Evaluation Top Banner -->
      <div class="ai-council-banner">
        <div class="ai-council-badge-left">
          <span>⚡ NVIDIA NIM AI COUNCIL:</span>
          <span class="ai-council-score-pill">8.9 / 10 · APPROVED</span>
        </div>
        <div class="ai-agent-breakdown">
          <span>🧭 Trip: <strong>9.1</strong></span>
          <span>🏨 Stay: <strong>8.8</strong></span>
          <span>🍲 Food: <strong>9.3</strong></span>
          <span>💳 Fare: <strong>8.5</strong></span>
        </div>
      </div>

      <!-- Details & Highlights Grid -->
      <div class="overview-grid">
        
        <!-- Left: Trip Details -->
        <div class="details-card">
          <div class="detail-row">
            <svg class="icon" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"/><path d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"/></svg>
            <div>
              <span class="detail-label">Destination</span>
              <span class="detail-val">Kashmir, India</span>
            </div>
          </div>
          <div class="detail-row">
            <svg class="icon" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"/></svg>
            <div>
              <span class="detail-label">Travel Dates</span>
              <span class="detail-val">15 – 21 November 2026</span>
            </div>
          </div>
          <div class="detail-row">
            <svg class="icon" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
            <div>
              <span class="detail-label">Duration</span>
              <span class="detail-val">7 Days, 6 Nights</span>
            </div>
          </div>
          <div class="detail-row">
            <svg class="icon" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z"/></svg>
            <div>
              <span class="detail-label">Travelers</span>
              <span class="detail-val">2 Adults</span>
            </div>
          </div>
          <div class="detail-row">
            <svg class="icon" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"/></svg>
            <div>
              <span class="detail-label">Starting Point</span>
              <span class="detail-val">New Delhi (DEL)</span>
            </div>
          </div>
          <div class="detail-row">
            <svg class="icon" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7"/></svg>
            <div>
              <span class="detail-label">Destinations</span>
              <span class="detail-val">Srinagar → Gulmarg → Pahalgam</span>
            </div>
          </div>
          <div class="detail-row">
            <svg class="icon" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z"/></svg>
            <div>
              <span class="detail-label">Travel Style</span>
              <span class="detail-val">Winter Alpine & Culinary Discovery</span>
            </div>
          </div>
        </div>

        <!-- Right: Trip Highlights + Map -->
        <div class="highlights-card">
          <div>
            <div class="highlights-title">🏔 AI-Curated Highlights</div>
            <ul class="highlights-list">
              <li>
                <div class="check-icon"><svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M5 13l4 4L19 7"/></svg></div>
                Stay in heated Snowline Lodge & Homestay
              </li>
              <li>
                <div class="check-icon"><svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M5 13l4 4L19 7"/></svg></div>
                Dal Lake morning shikara & floating market
              </li>
              <li>
                <div class="check-icon"><svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M5 13l4 4L19 7"/></svg></div>
                Gulmarg Gondola Phase 2 to Apharwat peak
              </li>
              <li>
                <div class="check-icon"><svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M5 13l4 4L19 7"/></svg></div>
                Authentic 7-course Kashmiri Wazwan feast
              </li>
              <li>
                <div class="check-icon"><svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M5 13l4 4L19 7"/></svg></div>
                Kashmir Family Kitchen regional dining
              </li>
              <li>
                <div class="check-icon"><svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M5 13l4 4L19 7"/></svg></div>
                Private heated 4x4 snow transit included
              </li>
            </ul>
          </div>

          <!-- Mini Map SVG (Kashmir) -->
          <div class="mini-map-box" style="background:#eff6ff;">
            <svg viewBox="0 0 160 210" width="100%" height="100%">
              <!-- Kashmir Valley Mountain Silhouette -->
              <path d="M 30,50 Q 80,20 135,45 Q 145,100 120,165 Q 75,190 35,160 Q 20,110 30,50 Z" fill="#dbeafe" stroke="#93c5fd" stroke-width="1.5"/>
              
              <!-- Route Dashed Line -->
              <path d="M 80,105 L 50,85 L 105,140" fill="none" stroke="#1e3a8a" stroke-width="2" stroke-dasharray="4,4"/>
              
              <!-- Gulmarg Pin -->
              <circle cx="50" cy="85" r="6" fill="#f59e0b" stroke="#ffffff" stroke-width="2"/>
              <text x="8" y="75" font-size="10" font-weight="700" fill="#1e3a8a" font-family="Inter">Gulmarg</text>
              
              <!-- Srinagar Pin -->
              <circle cx="80" cy="105" r="6" fill="#f59e0b" stroke="#ffffff" stroke-width="2"/>
              <text x="88" y="105" font-size="10" font-weight="700" fill="#1e3a8a" font-family="Inter">Srinagar</text>
              
              <!-- Pahalgam Pin -->
              <circle cx="105" cy="140" r="6" fill="#f59e0b" stroke="#ffffff" stroke-width="2"/>
              <text x="75" y="155" font-size="10" font-weight="700" fill="#1e3a8a" font-family="Inter">Pahalgam</text>

              <!-- State label -->
              <text x="50" y="40" font-size="11" font-weight="800" fill="#2563eb" letter-spacing="1.5" font-family="Outfit">KASHMIR</text>
              <text x="140" y="25" font-size="9" font-weight="700" fill="#64748b">N</text>
            </svg>
          </div>
        </div>

      </div>

      <!-- AI Council Evaluated Travel Plan -->
      <div class="plan-section">
        <div class="plan-section-header">
          <div class="plan-heading">
            <svg width="18" height="18" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"/></svg>
            Your AI Council Evaluated Travel Plan
          </div>
          <a href="#itinerary" class="plan-more-link">View Agent Review Cards →</a>
        </div>

        <div class="plan-cards-grid">
          
          <!-- Flights -->
          <div class="plan-item-card">
            <img class="plan-card-img" src="https://images.unsplash.com/photo-1436491865332-7a61a109cc05?auto=format&fit=crop&w=600&q=80" alt="Flight">
            <div class="plan-card-body">
              <div>
                <div class="plan-card-type">✈ Flights</div>
                <div class="plan-card-details">
                  <strong>Delhi → Srinagar (SXR)</strong>
                  IndiGo • 6E 214<br>
                  15 Nov 2026 • 07:15 AM
                </div>
              </div>
              <div class="plan-card-actions">
                <button class="btn-ghost">View Ticket</button>
                <span class="pill-confirmed">Confirmed</span>
              </div>
            </div>
          </div>

          <!-- Hotels (Snowline Lodge) -->
          <div class="plan-item-card">
            <img class="plan-card-img" src="https://images.unsplash.com/photo-1517048676732-d65bc937f952?auto=format&fit=crop&w=600&q=80" alt="Snowline Lodge Gulmarg">
            <div class="plan-card-body">
              <div>
                <div class="plan-card-type">🏨 Hotels</div>
                <div class="plan-card-details">
                  <strong>Snowline Lodge</strong> Gulmarg (3N)<br>
                  <strong>Kashmir Slow Living</strong> Homestay (3N)<br>
                  <em>Heated rooms & mountain view</em>
                </div>
              </div>
              <div class="plan-card-actions">
                <button class="btn-ghost">View Stays</button>
                <span class="pill-confirmed">Confirmed</span>
              </div>
            </div>
          </div>

          <!-- Experiences (Dal Lake & Gulmarg) -->
          <div class="plan-item-card">
            <img class="plan-card-img" src="https://images.unsplash.com/photo-1564013799919-ab600027ffc6?auto=format&fit=crop&w=600&q=80" alt="Gulmarg Gondola">
            <div class="plan-card-body">
              <div>
                <div class="plan-card-type">📷 Experiences</div>
                <div class="plan-card-details">
                  <strong>Dal Lake Shikara Tour</strong><br>
                  Gulmarg Gondola & Meadow Trek<br>
                  Old Srinagar & Wazwan Trail
                </div>
              </div>
              <div class="plan-card-actions">
                <button class="btn-ghost">View Details</button>
                <span class="pill-selected">Selected</span>
              </div>
            </div>
          </div>

          <!-- Transport (Heated 4x4) -->
          <div class="plan-item-card">
            <img class="plan-card-img" src="https://images.unsplash.com/photo-1549317661-bd32c8ce0db2?auto=format&fit=crop&w=600&q=80" alt="4x4 Snow Cab">
            <div class="plan-card-body">
              <div>
                <div class="plan-card-type">🚗 Transport</div>
                <div class="plan-card-details">
                  <strong>Private Heated 4x4 Cab</strong><br>
                  Srinagar ↔ Gulmarg ↔ Pahalgam<br>
                  Chained snow tires & local driver
                </div>
              </div>
              <div class="plan-card-actions">
                <button class="btn-ghost">View Details</button>
                <span class="pill-confirmed">Confirmed</span>
              </div>
            </div>
          </div>

        </div>
      </div>

      <!-- Cost, Status & Download Bar -->
      <div class="bottom-callout-grid">
        <div class="callout-cost">
          <div class="cost-icon-box">
            <svg width="22" height="22" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
          </div>
          <div class="cost-text">
            <small>Estimated Trip Cost</small>
            <strong>₹ 48,500</strong> <small style="display:inline;">per person</small>
          </div>
        </div>

        <div class="callout-status">
          <div class="status-icon-box" style="background:#dcfce7; color:#16a34a;">
            <svg width="20" height="20" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
          </div>
          <div class="status-text">
            <strong style="color:#16a34a;">AI Council Approved — Ready</strong>
            <small>Zero cross-destination conflicts detected. Meal slots and heating verified.</small>
          </div>
        </div>

        <div class="download-cta-btn">
          <svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/></svg>
          <div class="download-cta-text">
            <strong>Download Travel Book</strong>
            <small>Complete PDF with multi-agent council verdict.</small>
          </div>
        </div>
      </div>

    </div>

    <!-- Footer -->
    <footer class="catalog-footer">
      <div class="footer-left">
        <svg viewBox="0 0 32 32" width="28" height="28" fill="none">
          <circle cx="16" cy="16" r="14" fill="#f59e0b" fill-opacity="0.2"/>
          <path d="M16 4C9.373 4 4 9.373 4 16C4 22.627 9.373 28 16 28C22.627 28 28 22.627 28 16" stroke="#ffffff" stroke-width="2.5" stroke-linecap="round"/>
          <path d="M22 11L13 20L10 17" stroke="#f59e0b" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
        <div>
          <span class="brand-title" style="font-size:18px;">Voyara</span>
          <span style="font-size:9px; color:#f59e0b; display:block; letter-spacing:1px; text-transform:uppercase;">Tours • Travels</span>
        </div>
      </div>
      <div class="footer-center">
        Let's turn your travel dreams into plans ♡
      </div>
      <div class="footer-right">
        <div class="footer-qr">
          <svg viewBox="0 0 24 24" width="100%" height="100%" fill="#0f273d">
            <rect x="2" y="2" width="8" height="8" rx="1"/>
            <rect x="14" y="2" width="8" height="8" rx="1"/>
            <rect x="2" y="14" width="8" height="8" rx="1"/>
            <rect x="14" y="14" width="4" height="4"/>
            <rect x="18" y="18" width="4" height="4"/>
          </svg>
        </div>
        <span>Scan to view in Voyara app<br>NVIDIA AI Council Certified</span>
      </div>
    </footer>

  </div>


  <!-- PAGE 2: DISCOVER KASHMIR & AI AGENT INSIGHTS -->
  <div class="page-container" id="page2">
    
    <!-- Top Bar -->
    <div class="page2-header">
      <div class="brand-logo">
        <svg viewBox="0 0 32 32" width="24" height="24" fill="none">
          <circle cx="16" cy="16" r="14" fill="#f59e0b" fill-opacity="0.2"/>
          <path d="M16 4C9.373 4 4 9.373 4 16C4 22.627 9.373 28 16 28C22.627 28 28 22.627 28 16" stroke="#ffffff" stroke-width="2.5" stroke-linecap="round"/>
          <path d="M22 11L13 20L10 17" stroke="#f59e0b" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
        <span style="font-family:'Outfit',sans-serif; font-size:18px; font-weight:800; color:#fff;">VOYARA</span>
        <span style="font-size:9px; color:#f59e0b; font-weight:600; letter-spacing:1px;">AI COUNCIL CATALOG</span>
      </div>
      <div class="slogan">More Than a Trip — A Story to Tell</div>
    </div>

    <!-- Discover Kashmir Hero -->
    <div class="page2-hero">
      <div class="page2-hero-copy">
        <span class="eyebrow">YOUR DESTINATION</span>
        <h1>Discover <span>Kashmir</span></h1>
        <div class="accent-line"></div>
        <p>The crown of India — where snow-dusted chinars, serene mountain valleys and warm hospitality create an unforgettable winter journey.</p>
      </div>
      <div class="page2-hero-img-box">
        <img src="https://images.unsplash.com/photo-1595815771614-ade9d652a65d?auto=format&fit=crop&w=800&q=80" alt="Dal Lake Shikara Morning">
      </div>
    </div>

    <!-- What Makes Kashmir Special? -->
    <div class="special-section">
      <div class="special-box">
        <div class="special-title">What makes Kashmir special?</div>
        <div class="special-pills">
          <div class="special-pill-item">
            <div class="special-icon-circle" style="background:#2563eb;">
              <svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z"/></svg>
            </div>
            <span>Alpine Snow</span>
          </div>
          <div class="special-pill-item">
            <div class="special-icon-circle" style="background:#0284c7;">
              <svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M13 10V3L4 14h7v7l9-11h-7z"/></svg>
            </div>
            <span>Dal Houseboats</span>
          </div>
          <div class="special-pill-item">
            <div class="special-icon-circle" style="background:#d97706;">
              <svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"/></svg>
            </div>
            <span>Royal Wazwan</span>
          </div>
          <div class="special-pill-item">
            <div class="special-icon-circle" style="background:#059669;">
              <svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4"/></svg>
            </div>
            <span>Chinar Valleys</span>
          </div>
          <div class="special-pill-item">
            <div class="special-icon-circle" style="background:#7c3aed;">
              <svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z"/></svg>
            </div>
            <span>Pashmina Artisans</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Your Selected Destinations -->
    <div class="destinations-section">
      <div class="destinations-header">
        <h2>Your Selected Destinations</h2>
        <p>Explore the highlights of Kashmir selected and verified by the AI council.</p>
      </div>

      <div class="destinations-layout">
        
        <!-- Srinagar Card -->
        <div class="destination-card">
          <div class="destination-img-box">
            <img src="https://images.unsplash.com/photo-1595815771614-ade9d652a65d?auto=format&fit=crop&w=500&q=80" alt="Srinagar Dal Lake">
            <span class="dest-selected-tag">✔ Selected</span>
          </div>
          <div class="destination-card-content">
            <h3>Srinagar</h3>
            <p class="dest-summary">Venice of the East with wooden houseboats and Mughal history.</p>
            <div class="dest-exp-list-title">📍 Key Experiences</div>
            <ul class="dest-exp-list">
              <li>Dal Lake sunrise shikara</li>
              <li>Floating vegetable market</li>
              <li>Old Srinagar Wazwan trail</li>
            </ul>
          </div>
        </div>

        <!-- Gulmarg Card -->
        <div class="destination-card">
          <div class="destination-img-box">
            <img src="https://images.unsplash.com/photo-1564013799919-ab600027ffc6?auto=format&fit=crop&w=500&q=80" alt="Gulmarg Gondola">
            <span class="dest-selected-tag">✔ Selected</span>
          </div>
          <div class="destination-card-content">
            <h3>Gulmarg</h3>
            <p class="dest-summary">Meadow of flowers and Asia's highest operating cable car.</p>
            <div class="dest-exp-list-title">📍 Key Experiences</div>
            <ul class="dest-exp-list">
              <li>Gondola Phase 2 to Apharwat</li>
              <li>Pine meadow snow trek</li>
              <li>Snowline Lodge heating stay</li>
            </ul>
          </div>
        </div>

        <!-- Pahalgam Card -->
        <div class="destination-card">
          <div class="destination-img-box">
            <img src="https://images.unsplash.com/photo-1595815771614-ade9d652a65d?auto=format&fit=crop&w=500&q=80" alt="Pahalgam Valleys">
            <span class="dest-selected-tag">✔ Selected</span>
          </div>
          <div class="destination-card-content">
            <h3>Pahalgam</h3>
            <p class="dest-summary">Valley of shepherds with pine-scented mountain streams.</p>
            <div class="dest-exp-list-title">📍 Key Experiences</div>
            <ul class="dest-exp-list">
              <li>Betaab & Aru valley trails</li>
              <li>Lidder River riverside walk</li>
              <li>Local walnut woodcrafts</li>
            </ul>
          </div>
        </div>

        <!-- Kashmir at a Glance (Map) -->
        <div class="map-card-box" style="background:#eff6ff; border-color:#bfdbfe;">
          <h4>Kashmir at a Glance</h4>
          <svg viewBox="0 0 150 180" width="100%" height="130">
            <path d="M 25,40 Q 75,15 130,35 Q 140,90 115,150 Q 70,175 30,145 Q 15,95 25,40 Z" fill="#bfdbfe" stroke="#93c5fd" stroke-width="1.5"/>
            <path d="M 75,95 L 45,75 L 100,130" fill="none" stroke="#1d4ed8" stroke-width="2" stroke-dasharray="3,3"/>
            <circle cx="45" cy="75" r="5" fill="#1d4ed8"/>
            <text x="5" y="70" font-size="9" font-weight="700" fill="#0f273d" font-family="Inter">Gulmarg</text>
            <circle cx="75" cy="95" r="5" fill="#1d4ed8"/>
            <text x="82" y="98" font-size="9" font-weight="700" fill="#0f273d" font-family="Inter">Srinagar</text>
            <circle cx="100" cy="130" r="5" fill="#1d4ed8"/>
            <text x="75" y="145" font-size="9" font-weight="700" fill="#0f273d" font-family="Inter">Pahalgam</text>
            <text x="15" y="160" font-size="8" fill="#1e40af" font-family="Inter">Pir Panjal<br>Range</text>
          </svg>
          <div class="map-slogan">Paradise on Earth, Curated</div>
        </div>

      </div>
    </div>

    <!-- AI Council Expert Notes & Recommendations -->
    <div class="bottom-info-row">
      <div class="info-grid-card" style="background:#f8fafc; border-color:#e2e8f0;">
        <div class="info-grid-title">🧭 AI Travel Council Recommendations</div>
        <div class="info-cols">
          <div class="info-col-item">
            <span class="info-label">👤 Trip Consultant (9.1)</span>
            <span class="info-val">Take 06:30 AM sunrise shikara for serene photography without crowds.</span>
          </div>
          <div class="info-col-item">
            <span class="info-label">🏨 Stay Specialist (8.8)</span>
            <span class="info-val">Snowline Lodge confirmed with electric blankets and wood bukhari heating.</span>
          </div>
          <div class="info-col-item">
            <span class="info-label">🍲 Food Guide (9.3)</span>
            <span class="info-val">Kashmir Family Kitchen Wazwan scheduled. Try Tabakh Maaz & Gushtaba.</span>
          </div>
          <div class="info-col-item">
            <span class="info-label">💳 Fare & Booking (8.5)</span>
            <span class="info-val">Book flights 60 days ahead; private 4x4 snow transit avoids taxi union delays.</span>
          </div>
        </div>
      </div>

      <div class="promo-card" style="background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%); border-color:#bfdbfe;">
        <img class="promo-card-bg-img" src="https://images.unsplash.com/photo-1564013799919-ab600027ffc6?auto=format&fit=crop&w=400&q=80" alt="Kashmir Gondola">
        <div class="promo-card-content">
          <h3>Kashmir Awaits You</h3>
          <a href="#destination/Kashmir" class="promo-btn">Explore Kashmir Guide ↗</a>
        </div>
      </div>
    </div>

    <!-- Page 2 Footer -->
    <footer class="page2-footer">
      <div class="brand-logo" style="gap:6px;">
        <span style="font-family:'Outfit',sans-serif; font-size:14px; font-weight:800; color:#fff;">VOYARA</span>
        <span style="font-size:8px; color:#f59e0b; font-weight:600;">AI COUNCIL TRAVEL BOOK</span>
      </div>
      <div class="meta">📍 Kashmir, India &nbsp;|&nbsp; Multi-Agent System Verified</div>
      <div style="font-weight:700; color:#cbd5e1;">Page 2 of 8</div>
    </footer>

  </div>

</body>
</html>
"""

def main():
    kerala_html = generate_kerala_html()
    kashmir_html = generate_kashmir_html()

    for target_dir in [ROOT_CATALOG, PLATFORM_CATALOG]:
        kerala_file = target_dir / "kerala_manual_catalog.html"
        kashmir_file = target_dir / "kashmir_ai_catalog.html"

        with open(kerala_file, "w", encoding="utf-8") as f:
            f.write(kerala_html)
        with open(kashmir_file, "w", encoding="utf-8") as f:
            f.write(kashmir_html)

        print(f"Wrote {kerala_file}")
        print(f"Wrote {kashmir_file}")

if __name__ == "__main__":
    main()
