import os
from pathlib import Path

# Paths
ROOT_DIR = Path(r"c:\Users\vvars\OneDrive\Desktop\Iron Web")
ROOT_KASHMIR = ROOT_DIR / "catalog" / "kashmir_trip"
PLATFORM_KASHMIR = ROOT_DIR / "stitch_ai_travel_booking_platform" / "catalog" / "kashmir_trip"

ROOT_KASHMIR.mkdir(parents=True, exist_ok=True)
PLATFORM_KASHMIR.mkdir(parents=True, exist_ok=True)

# Read base CSS from build_9page_catalogs
from build_9page_catalogs import COMMON_CSS, wrap_html, make_header, make_footer

DEST = "Kashmir"
SYSTEM_BADGE = "AI COUNCIL CERTIFIED"

# PAGE 1: SUMMARY (Cover & Trip Overview)
def page1_html():
    return f"""
  <div class="page" id="page1">
    <header class="top-nav">
      <div class="brand-logo">
        <svg viewBox="0 0 40 40" fill="none" width="36" height="36">
          <circle cx="20" cy="20" r="18" fill="#f59e0b" fill-opacity="0.15"/>
          <path d="M20 4C11.163 4 4 11.163 4 20C4 28.837 11.163 36 20 36C28.837 36 36 28.837 36 20" stroke="#0f273d" stroke-width="3" stroke-linecap="round"/>
          <path d="M28 14L16 26L12 22" stroke="#f59e0b" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
        <div>
          <div class="brand-title">Voyara</div>
          <div class="brand-sub">Tours • Travels</div>
        </div>
      </div>
      <div class="top-slogan">AI Multi-Agent Verified Itinerary ⚡ ♡</div>
    </header>

    <div class="hero-wrap">
      <img class="hero-img" src="https://images.unsplash.com/photo-1595815771614-ade9d652a65d?auto=format&fit=crop&w=1400&q=85" alt="Kashmir Dal Lake">
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

    <div class="wave-divider">
      <svg viewBox="0 0 920 38" fill="none" preserveAspectRatio="none"><path d="M0,0 C150,30 350,38 460,20 C600,0 750,25 920,10 L920,38 L0,38 Z" fill="#ffffff"/></svg>
    </div>

    <div class="page-body">
      <div style="background:linear-gradient(90deg, #1e1b4b 0%, #312e81 50%, #1e1b4b 100%); color:#ffffff; padding:8px 18px; border-radius:8px; display:flex; justify-content:space-between; align-items:center; border:1px solid #4338ca;">
        <div style="display:flex; align-items:center; gap:8px; font-size:11px; font-weight:700;">
          <span>⚡ NVIDIA NIM AI COUNCIL:</span>
          <span style="background:#10b981; color:#fff; padding:2px 8px; border-radius:999px; font-size:11px; font-weight:800;">8.9 / 10 · APPROVED</span>
        </div>
        <div style="display:flex; gap:16px; font-size:10px; color:#c7d2fe;">
          <span>🧭 Trip: <strong>9.1</strong></span>
          <span>🏨 Stay: <strong>8.8</strong></span>
          <span>🍲 Food: <strong>9.3</strong></span>
          <span>💳 Fare: <strong>8.5</strong></span>
        </div>
      </div>

      <div class="overview-grid">
        <div class="details-card">
          <div class="detail-row">
            <svg class="icon" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"/><path d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"/></svg>
            <div><span class="detail-label">Destination</span><span class="detail-val">Kashmir, India</span></div>
          </div>
          <div class="detail-row">
            <svg class="icon" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"/></svg>
            <div><span class="detail-label">Travel Dates</span><span class="detail-val">15 – 21 November 2026</span></div>
          </div>
          <div class="detail-row">
            <svg class="icon" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
            <div><span class="detail-label">Duration</span><span class="detail-val">7 Days, 6 Nights</span></div>
          </div>
          <div class="detail-row">
            <svg class="icon" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z"/></svg>
            <div><span class="detail-label">Travelers</span><span class="detail-val">2 Adults</span></div>
          </div>
          <div class="detail-row">
            <svg class="icon" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"/></svg>
            <div><span class="detail-label">Starting Point</span><span class="detail-val">New Delhi (DEL)</span></div>
          </div>
          <div class="detail-row">
            <svg class="icon" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7"/></svg>
            <div><span class="detail-label">Destinations</span><span class="detail-val">Srinagar → Gulmarg → Pahalgam</span></div>
          </div>
          <div class="detail-row">
            <svg class="icon" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z"/></svg>
            <div><span class="detail-label">Travel Style</span><span class="detail-val">Winter Alpine & Culinary Discovery</span></div>
          </div>
        </div>

        <div class="highlights-card">
          <div>
            <div class="highlights-title">🏔 AI-Curated Highlights</div>
            <ul class="highlights-list">
              <li><div class="check-icon"><svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M5 13l4 4L19 7"/></svg></div>Heated Snowline Lodge & Homestay stays</li>
              <li><div class="check-icon"><svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M5 13l4 4L19 7"/></svg></div>Dal Lake sunrise shikara & floating market</li>
              <li><div class="check-icon"><svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M5 13l4 4L19 7"/></svg></div>Gulmarg Gondola Phase 2 to Apharwat peak</li>
              <li><div class="check-icon"><svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M5 13l4 4L19 7"/></svg></div>Authentic 7-course Kashmiri Wazwan feast</li>
              <li><div class="check-icon"><svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M5 13l4 4L19 7"/></svg></div>Private heated 4x4 snow cab included</li>
            </ul>
          </div>
          <div class="mini-map-box" style="background:#eff6ff;">
            <svg viewBox="0 0 160 200" width="100%" height="100%">
              <path d="M 30,50 Q 80,20 135,45 Q 145,100 120,165 Q 75,190 35,160 Q 20,110 30,50 Z" fill="#dbeafe" stroke="#93c5fd" stroke-width="1.5"/>
              <path d="M 80,105 L 50,85 L 105,140" fill="none" stroke="#1e3a8a" stroke-width="2" stroke-dasharray="4,4"/>
              <circle cx="50" cy="85" r="5" fill="#f59e0b" stroke="#fff" stroke-width="2"/>
              <text x="8" y="75" font-size="9" font-weight="700" fill="#1e3a8a">Gulmarg</text>
              <circle cx="80" cy="105" r="5" fill="#f59e0b" stroke="#fff" stroke-width="2"/>
              <text x="88" y="105" font-size="9" font-weight="700" fill="#1e3a8a">Srinagar</text>
              <circle cx="105" cy="140" r="5" fill="#f59e0b" stroke="#fff" stroke-width="2"/>
              <text x="75" y="155" font-size="9" font-weight="700" fill="#1e3a8a">Pahalgam</text>
              <text x="50" y="38" font-size="10" font-weight="800" fill="#2563eb" letter-spacing="1">KASHMIR</text>
            </svg>
          </div>
        </div>
      </div>

      <div class="plan-section">
        <div class="plan-section-header">
          <div class="plan-heading">
            <svg width="18" height="18" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"/></svg>
            Your AI Council Evaluated Travel Plan
          </div>
          <span class="tag-pill tag-teal">4 Verified Components</span>
        </div>
        <div class="plan-cards-grid">
          <div class="plan-item-card">
            <img class="plan-card-img" src="https://images.unsplash.com/photo-1436491865332-7a61a109cc05?auto=format&fit=crop&w=600&q=80" alt="Flight">
            <div class="plan-card-body">
              <div><div class="plan-card-type">✈ Flights</div><div class="plan-card-details"><strong>DEL → SXR</strong>IndiGo 6E 214<br>15 Nov 07:15 AM</div></div>
              <div style="display:flex; justify-content:space-between; align-items:center;"><button class="btn-ghost">View</button><span class="tag-pill tag-green">Confirmed</span></div>
            </div>
          </div>
          <div class="plan-item-card">
            <img class="plan-card-img" src="https://images.unsplash.com/photo-1517048676732-d65bc937f952?auto=format&fit=crop&w=600&q=80" alt="Snowline Lodge">
            <div class="plan-card-body">
              <div><div class="plan-card-type">🏨 Hotels</div><div class="plan-card-details"><strong>Snowline Lodge</strong> Gulmarg (3N)<br>Slow Living Homestay (3N)</div></div>
              <div style="display:flex; justify-content:space-between; align-items:center;"><button class="btn-ghost">View</button><span class="tag-pill tag-green">Confirmed</span></div>
            </div>
          </div>
          <div class="plan-item-card">
            <img class="plan-card-img" src="https://images.unsplash.com/photo-1564013799919-ab600027ffc6?auto=format&fit=crop&w=600&q=80" alt="Gondola">
            <div class="plan-card-body">
              <div><div class="plan-card-type">📷 Experiences</div><div class="plan-card-details"><strong>Dal Lake Shikara</strong><br>Gulmarg Gondola & Wazwan</div></div>
              <div style="display:flex; justify-content:space-between; align-items:center;"><button class="btn-ghost">View</button><span class="tag-pill tag-teal">Selected</span></div>
            </div>
          </div>
          <div class="plan-item-card">
            <img class="plan-card-img" src="https://images.unsplash.com/photo-1549317661-bd32c8ce0db2?auto=format&fit=crop&w=600&q=80" alt="4x4 Cab">
            <div class="plan-card-body">
              <div><div class="plan-card-type">🚗 Transport</div><div class="plan-card-details"><strong>Private Heated 4x4</strong><br>Srinagar ↔ Gulmarg ↔ Pahalgam</div></div>
              <div style="display:flex; justify-content:space-between; align-items:center;"><button class="btn-ghost">View</button><span class="tag-pill tag-green">Confirmed</span></div>
            </div>
          </div>
        </div>
      </div>

      <div class="bottom-callout-grid">
        <div style="display:flex; align-items:center; gap:10px;">
          <div style="width:38px; height:38px; border-radius:8px; background:var(--gold-bg); color:var(--gold-warm); display:flex; align-items:center; justify-content:center;">
            <svg width="22" height="22" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
          </div>
          <div class="cost-text"><small>Estimated Trip Cost</small><strong>₹ 48,500</strong> <small style="display:inline;">per person</small></div>
        </div>
        <div style="display:flex; align-items:center; gap:10px; border-left:1px solid var(--border-light); padding-left:16px;">
          <div style="width:38px; height:38px; border-radius:8px; background:#dcfce7; color:#16a34a; display:flex; align-items:center; justify-content:center;">
            <svg width="20" height="20" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
          </div>
          <div><strong style="color:#16a34a; font-size:11px; display:block;">AI Council Approved — Ready</strong><small style="font-size:10px; color:var(--text-muted);">Zero geographic conflicts. Heating verified.</small></div>
        </div>
        <div class="download-cta-btn">
          <svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/></svg>
          <div><strong style="font-size:12px; display:block;">Download Travel Book</strong><small style="font-size:9.5px; color:#94a3b8;">Complete 9-page certified dossier</small></div>
        </div>
      </div>
    </div>
    {make_footer(DEST, 1)}
  </div>
    """

# PAGE 2: DESTINATION
def page2_html():
    return f"""
  <div class="page" id="page2">
    {make_header(SYSTEM_BADGE, "SECTION 2: THE DESTINATION")}
    <div class="page-hero-banner">
      <div>
        <span class="eyebrow">DESTINATION DISCOVERY</span>
        <h1>Discover <span>Kashmir</span></h1>
        <div class="accent-bar"></div>
        <p>The crown of the Indian subcontinent. A land of snow-dusted chinars, serene shikara reflections, and high Himalayan peaks that has enchanted poets and travelers for centuries.</p>
      </div>
      <div class="page-hero-thumb">
        <img src="https://images.unsplash.com/photo-1595815771614-ade9d652a65d?auto=format&fit=crop&w=600&q=80" alt="Kashmir Landscape">
      </div>
    </div>

    <div class="page-content">
      <div style="background:#f0fdfa; border:1px solid #ccfbf1; border-radius:12px; padding:12px 18px; display:flex; align-items:center; gap:20px;">
        <div style="font-family:'Outfit',sans-serif; font-size:14px; font-weight:700; color:var(--navy); width:130px; line-height:1.2;">What makes Kashmir special?</div>
        <div style="display:flex; gap:14px; flex:1;">
          <div style="display:flex; flex-direction:column; align-items:center; gap:3px; font-size:10px; font-weight:600;">
            <div style="width:34px; height:34px; border-radius:50%; background:#2563eb; color:#fff; display:flex; align-items:center; justify-content:center;">❄</div>
            <span>Alpine Snow</span>
          </div>
          <div style="display:flex; flex-direction:column; align-items:center; gap:3px; font-size:10px; font-weight:600;">
            <div style="width:34px; height:34px; border-radius:50%; background:#0284c7; color:#fff; display:flex; align-items:center; justify-content:center;">⛵</div>
            <span>Dal Houseboats</span>
          </div>
          <div style="display:flex; flex-direction:column; align-items:center; gap:3px; font-size:10px; font-weight:600;">
            <div style="width:34px; height:34px; border-radius:50%; background:#d97706; color:#fff; display:flex; align-items:center; justify-content:center;">🍲</div>
            <span>Royal Wazwan</span>
          </div>
          <div style="display:flex; flex-direction:column; align-items:center; gap:3px; font-size:10px; font-weight:600;">
            <div style="width:34px; height:34px; border-radius:50%; background:#059669; color:#fff; display:flex; align-items:center; justify-content:center;">🌲</div>
            <span>Pine Valleys</span>
          </div>
          <div style="display:flex; flex-direction:column; align-items:center; gap:3px; font-size:10px; font-weight:600;">
            <div style="width:34px; height:34px; border-radius:50%; background:#7c3aed; color:#fff; display:flex; align-items:center; justify-content:center;">🧣</div>
            <span>Pashmina Art</span>
          </div>
        </div>
      </div>

      <div style="display:grid; grid-template-columns: repeat(3, 1fr) 210px; gap:12px;">
        <div class="card">
          <img style="height:110px; object-fit:cover;" src="https://images.unsplash.com/photo-1595815771614-ade9d652a65d?auto=format&fit=crop&w=400&q=80" alt="Srinagar">
          <div class="card-padded" style="padding:10px;">
            <div class="card-header">Srinagar</div>
            <p style="font-size:10.5px; color:var(--text-muted); margin-bottom:6px;">Venice of the East with wooden houseboats and Mughal history.</p>
            <ul style="font-size:10px; list-style:none; line-height:1.5;">
              <li>• Dal Lake sunrise shikara</li>
              <li>• Floating vegetable market</li>
              <li>• Old Srinagar Wazwan trail</li>
            </ul>
          </div>
        </div>

        <div class="card">
          <img style="height:110px; object-fit:cover;" src="https://images.unsplash.com/photo-1564013799919-ab600027ffc6?auto=format&fit=crop&w=400&q=80" alt="Gulmarg">
          <div class="card-padded" style="padding:10px;">
            <div class="card-header">Gulmarg</div>
            <p style="font-size:10.5px; color:var(--text-muted); margin-bottom:6px;">Meadow of flowers and Asia's highest operating cable car.</p>
            <ul style="font-size:10px; list-style:none; line-height:1.5;">
              <li>• Gondola Phase 2 to Apharwat</li>
              <li>• Pine meadow snow trek</li>
              <li>• Snowline Lodge heated suites</li>
            </ul>
          </div>
        </div>

        <div class="card">
          <img style="height:110px; object-fit:cover;" src="https://images.unsplash.com/photo-1595815771614-ade9d652a65d?auto=format&fit=crop&w=400&q=80" alt="Pahalgam">
          <div class="card-padded" style="padding:10px;">
            <div class="card-header">Pahalgam</div>
            <p style="font-size:10.5px; color:var(--text-muted); margin-bottom:6px;">Valley of shepherds with pine-scented mountain streams.</p>
            <ul style="font-size:10px; list-style:none; line-height:1.5;">
              <li>• Betaab & Aru valley trails</li>
              <li>• Lidder River riverside walk</li>
              <li>• Local walnut woodcrafts</li>
            </ul>
          </div>
        </div>

        <div style="background:#eff6ff; border:1px solid #bfdbfe; border-radius:10px; padding:12px; display:flex; flex-direction:column; align-items:center; justify-content:space-between; text-align:center;">
          <div style="font-family:'Outfit',sans-serif; font-size:12px; font-weight:700; color:var(--navy);">Regional Overview</div>
          <svg viewBox="0 0 140 150" width="100%" height="110">
            <path d="M 20,35 Q 70,15 120,30 Q 130,80 105,130 Q 65,150 25,125 Q 10,85 20,35 Z" fill="#bfdbfe" stroke="#93c5fd" stroke-width="1.5"/>
            <path d="M 70,85 L 40,65 L 90,115" fill="none" stroke="#1d4ed8" stroke-width="2" stroke-dasharray="3,3"/>
            <circle cx="40" cy="65" r="4" fill="#1d4ed8"/><text x="5" y="60" font-size="8" font-weight="700">Gulmarg</text>
            <circle cx="70" cy="85" r="4" fill="#1d4ed8"/><text x="75" y="88" font-size="8" font-weight="700">Srinagar</text>
            <circle cx="90" cy="115" r="4" fill="#1d4ed8"/><text x="65" y="130" font-size="8" font-weight="700">Pahalgam</text>
          </svg>
          <div style="font-family:'Caveat',cursive; font-size:16px; color:#1e40af;">Pir Panjal Range</div>
        </div>
      </div>

      <div style="display:grid; grid-template-columns: repeat(4, 1fr); gap:12px; background:#f8fafc; border:1px solid var(--border-light); border-radius:10px; padding:14px 16px;">
        <div>
          <span style="font-size:10px; color:var(--text-muted); font-weight:700; display:block;">📅 BEST SEASON</span>
          <strong style="font-size:12px; color:var(--navy);">Oct – Mar</strong>
          <small style="display:block; font-size:9.5px; color:var(--text-muted);">Snowfall & pleasant autumn</small>
        </div>
        <div>
          <span style="font-size:10px; color:var(--text-muted); font-weight:700; display:block;">☀ CLIMATE & TEMP</span>
          <strong style="font-size:12px; color:var(--navy);">-2°C to 12°C</strong>
          <small style="display:block; font-size:9.5px; color:var(--text-muted);">Crisp winter layers required</small>
        </div>
        <div>
          <span style="font-size:10px; color:var(--text-muted); font-weight:700; display:block;">🍲 REGIONAL CUISINE</span>
          <strong style="font-size:12px; color:var(--navy);">Royal Wazwan & Kahwa</strong>
          <small style="display:block; font-size:9.5px; color:var(--text-muted);">Saffron, lamb & walnuts</small>
        </div>
        <div>
          <span style="font-size:10px; color:var(--text-muted); font-weight:700; display:block;">🧳 PACKING ESSENTIALS</span>
          <strong style="font-size:12px; color:var(--navy);">Thermal Inners & Boots</strong>
          <small style="display:block; font-size:9.5px; color:var(--text-muted);">Waterproof jackets & gloves</small>
        </div>
      </div>

      <div class="notice-box">
        <strong>AI Council Destination Scoping:</strong> All selected sightseeing and stays are strictly geofenced within Kashmir Valley (Srinagar, Gulmarg, Pahalgam). No irrelevant inter-state transit or cross-destination leaks.
      </div>
    </div>
    {make_footer(DEST, 2)}
  </div>
    """

# PAGE 3: STAY PLACE
def page3_html():
    return f"""
  <div class="page" id="page3">
    {make_header(SYSTEM_BADGE, "SECTION 3: HANDPICKED STAYS")}
    <div class="page-hero-banner">
      <div>
        <span class="eyebrow">ACCOMMODATIONS & HEATING</span>
        <h1>Where You'll <span>Rest</span></h1>
        <div class="accent-bar"></div>
        <p>Curated mountain resorts and cultural homestays equipped with 24/7 central heating, electric blankets, and breathtaking snow-valley panoramas.</p>
      </div>
      <div class="page-hero-thumb">
        <img src="https://images.unsplash.com/photo-1517048676732-d65bc937f952?auto=format&fit=crop&w=600&q=80" alt="Snow Lodge">
      </div>
    </div>

    <div class="page-content">
      <div class="grid-3">
        <div class="card">
          <img style="height:120px; object-fit:cover;" src="https://images.unsplash.com/photo-1517048676732-d65bc937f952?auto=format&fit=crop&w=500&q=80" alt="Snowline Lodge">
          <div class="card-padded">
            <span class="tag-pill tag-green" style="margin-bottom:4px;">Primary Luxury Stay</span>
            <div class="card-header">Snowline Lodge</div>
            <div style="font-size:11px; color:var(--teal); font-weight:700; margin-bottom:6px;">Gulmarg · 3 Nights (15-18 Nov)</div>
            <p style="font-size:11px; color:var(--text-muted); line-height:1.4; margin-bottom:8px;">Overlooking Apharwat Peak with wood-panelled suites, traditional bukhari fireplace, heated beds, and high-altitude restaurant.</p>
            <div style="font-size:10px; color:var(--text-dark); background:#f1f5f9; padding:6px 8px; border-radius:6px;">
              <strong>Included:</strong> Breakfast, Bukhari heating, WiFi, Snow boot rental
            </div>
            <div style="display:flex; justify-content:space-between; align-items:center; margin-top:8px;">
              <span style="font-size:12px; font-weight:800; color:var(--navy);">₹6,299 <small>/ night</small></span>
              <span class="tag-pill tag-gold">★ 4.8</span>
            </div>
          </div>
        </div>

        <div class="card">
          <img style="height:120px; object-fit:cover;" src="https://images.unsplash.com/photo-1582719478250-c89cae4dc85b?auto=format&fit=crop&w=500&q=80" alt="Homestay">
          <div class="card-padded">
            <span class="tag-pill tag-teal" style="margin-bottom:4px;">Cultural Heritage</span>
            <div class="card-header">Kashmir Slow Living</div>
            <div style="font-size:11px; color:var(--teal); font-weight:700; margin-bottom:6px;">Srinagar · 3 Nights (18-21 Nov)</div>
            <p style="font-size:11px; color:var(--text-muted); line-height:1.4; margin-bottom:8px;">Intimate cedarwood homestay near Dal Lake. Hosted by local culinary artisans serving authentic Kashmiri home-cooked Wazwan.</p>
            <div style="font-size:10px; color:var(--text-dark); background:#f1f5f9; padding:6px 8px; border-radius:6px;">
              <strong>Included:</strong> Breakfast, Home Wazwan dinner, Electric blanket
            </div>
            <div style="display:flex; justify-content:space-between; align-items:center; margin-top:8px;">
              <span style="font-size:12px; font-weight:800; color:var(--navy);">₹2,975 <small>/ night</small></span>
              <span class="tag-pill tag-gold">★ 4.8</span>
            </div>
          </div>
        </div>

        <div class="card">
          <img style="height:120px; object-fit:cover;" src="https://images.unsplash.com/photo-1549317661-bd32c8ce0db2?auto=format&fit=crop&w=500&q=80" alt="Hostel">
          <div class="card-padded">
            <span class="tag-pill tag-blue" style="margin-bottom:4px;">Budget Alternative</span>
            <div class="card-header">Backpackers' Nook</div>
            <div style="font-size:11px; color:var(--teal); font-weight:700; margin-bottom:6px;">Srinagar / Dal Footbridge</div>
            <p style="font-size:11px; color:var(--text-muted); line-height:1.4; margin-bottom:8px;">Vibrant social lodge with heated common library, bonfire patio, high-speed fiber internet, and local mountain trek desk.</p>
            <div style="font-size:10px; color:var(--text-dark); background:#f1f5f9; padding:6px 8px; border-radius:6px;">
              <strong>Included:</strong> High-speed WiFi, Hot water, Lockers, Community lounge
            </div>
            <div style="display:flex; justify-content:space-between; align-items:center; margin-top:8px;">
              <span style="font-size:12px; font-weight:800; color:var(--navy);">₹1,245 <small>/ night</small></span>
              <span class="tag-pill tag-gold">★ 4.3</span>
            </div>
          </div>
        </div>
      </div>

      <div class="card" style="margin-top:4px;">
        <div style="background:#f1f5f9; padding:10px 16px; font-weight:700; font-size:12px; color:var(--navy);">
          Stay Amenities & Winter Readiness Matrix
        </div>
        <table class="styled-table">
          <thead>
            <tr>
              <th>Property</th>
              <th>Room Category</th>
              <th>Heating Type</th>
              <th>Check-in / Out</th>
              <th>Meals Included</th>
              <th class="num">Score</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td><strong>Snowline Lodge</strong></td>
              <td>Deluxe Alpine Valley Suite</td>
              <td>Electric blankets + Bukhari wood fire</td>
              <td>14:00 / 11:00</td>
              <td>Buffet Breakfast & High Tea</td>
              <td class="num"><span class="tag-pill tag-green">9.2 / 10</span></td>
            </tr>
            <tr>
              <td><strong>Kashmir Slow Living</strong></td>
              <td>Traditional Cedar Room</td>
              <td>Under-carpet heating & radiators</td>
              <td>13:00 / 11:00</td>
              <td>Kashmiri Breakfast & 1 Wazwan</td>
              <td class="num"><span class="tag-pill tag-green">9.0 / 10</span></td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="notice-box">
        <strong>Stay Specialist Agent Verdict (Score 8.8/10):</strong> Both properties feature verified heating systems essential for November sub-zero nights. Pre-heated rooms are arranged 2 hours prior to guest arrival.
      </div>
    </div>
    {make_footer(DEST, 3)}
  </div>
    """

# PAGE 4: EATING PLACES AND TIMINGS
def page4_html():
    return f"""
  <div class="page" id="page4">
    {make_header(SYSTEM_BADGE, "SECTION 4: DINING & TIMINGS")}
    <div class="page-hero-banner">
      <div>
        <span class="eyebrow">CULINARY SCHEDULE</span>
        <h1>Flavours & <span>Timings</span></h1>
        <div class="accent-bar"></div>
        <p>A systematic culinary rhythm featuring traditional noon chai breakfasts, mountain cafe lunches, and slow-cooked Wazwan evening feasts.</p>
      </div>
      <div class="page-hero-thumb">
        <img src="https://images.unsplash.com/photo-1595815771614-ade9d652a65d?auto=format&fit=crop&w=600&q=80" alt="Wazwan Dining">
      </div>
    </div>

    <div class="page-content">
      <div class="grid-2">
        <div class="card card-padded">
          <div class="card-header" style="display:flex; justify-content:space-between; align-items:center;">
            <span>Daily Dining Schedule</span>
            <span class="tag-pill tag-gold">Curated Slots</span>
          </div>

          <div class="timeline-item">
            <div class="time-slot">🍳 07:30 – 09:30 AM</div>
            <div class="timeline-body">
              <div class="timeline-title">Breakfast & Noon Chai</div>
              <div class="timeline-desc">Salted pink noon chai, freshly baked girda/sheermal from local kandur bakery, butter, eggs and honey.</div>
            </div>
          </div>

          <div class="timeline-item">
            <div class="time-slot">☕ 11:00 – 11:30 AM</div>
            <div class="timeline-body">
              <div class="timeline-title">Mid-Morning Saffron Kahwa</div>
              <div class="timeline-desc">Hot green tea brewed with pure Pampore saffron, green cardamom, cinnamon, and crushed almonds.</div>
            </div>
          </div>

          <div class="timeline-item">
            <div class="time-slot">🍲 01:00 – 02:30 PM</div>
            <div class="timeline-body">
              <div class="timeline-title">Alpine Lunch Stop</div>
              <div class="timeline-desc">Freshly caught Himalayan river trout, steamed basmati, nadru yakhni (lotus stem in yogurt gravy).</div>
            </div>
          </div>

          <div class="timeline-item">
            <div class="time-slot">🫖 05:00 – 06:00 PM</div>
            <div class="timeline-body">
              <div class="timeline-title">Sunset High Tea</div>
              <div class="timeline-desc">Walnut pastries, lavender cookies, and hot apple-cinnamon brew at Kashmir Corner Cafe.</div>
            </div>
          </div>

          <div class="timeline-item" style="border-bottom:none;">
            <div class="time-slot">🍖 08:00 – 10:00 PM</div>
            <div class="timeline-body">
              <div class="timeline-title">Grand Wazwan Evening Banquet</div>
              <div class="timeline-desc">Traditional 7-course royal feast: Tabakh Maaz, Rogan Josh, Rista, Daniwal Korma, Gushtaba, and Phirni.</div>
            </div>
          </div>
        </div>

        <div style="display:flex; flex-direction:column; gap:12px;">
          <div class="card card-padded" style="border-left:4px solid var(--teal);">
            <div style="display:flex; justify-content:space-between; align-items:center;">
              <strong style="font-size:13px; color:var(--navy);">Kashmir Family Kitchen</strong>
              <span class="tag-pill tag-green">Veg & Non-Veg</span>
            </div>
            <small style="color:var(--text-muted); display:block; margin:2px 0 6px;">Residency Road, Srinagar · Rating 4.8★</small>
            <p style="font-size:11px; color:var(--text-dark); line-height:1.4;">Renowned master waza chefs preparing slow-cooked Rogan Josh over charcoal embers. Authentic seating in traditional copper trami plates.</p>
            <div style="font-size:10px; font-weight:700; color:var(--navy); margin-top:6px;">Average Cost: ₹795 / person</div>
          </div>

          <div class="card card-padded" style="border-left:4px solid var(--gold);">
            <div style="display:flex; justify-content:space-between; align-items:center;">
              <strong style="font-size:13px; color:var(--navy);">Kashmir Corner Cafe</strong>
              <span class="tag-pill tag-teal">Cafe & Bakery</span>
            </div>
            <small style="color:var(--text-muted); display:block; margin:2px 0 6px;">Boulevard Road, Dal Lake · Rating 4.6★</small>
            <p style="font-size:11px; color:var(--text-dark); line-height:1.4;">Lakeside coffeehouse offering artisanal walnut pies, freshly baked bakarkhani, espresso, and herbal mountain infusions.</p>
            <div style="font-size:10px; font-weight:700; color:var(--navy); margin-top:6px;">Average Cost: ₹450 / person</div>
          </div>

          <div class="card card-padded" style="border-left:4px solid var(--blue);">
            <div style="display:flex; justify-content:space-between; align-items:center;">
              <strong style="font-size:13px; color:var(--navy);">Kashmir Market Bites</strong>
              <span class="tag-pill tag-gold">Street Flavours</span>
            </div>
            <small style="color:var(--text-muted); display:block; margin:2px 0 6px;">Khayam Chowk & Lal Chowk · Rating 4.7★</small>
            <p style="font-size:11px; color:var(--text-dark); line-height:1.4;">Evening barbecue street hub famous for seekh kebabs on skewers, barbecued lamb ribs, hot lavasa wraps with mint chutney.</p>
            <div style="font-size:10px; font-weight:700; color:var(--navy); margin-top:6px;">Average Cost: ₹360 / person</div>
          </div>
        </div>
      </div>

      <div class="notice-box">
        <strong>Food Guide Agent Verdict (Score 9.3/10):</strong> Meal timings prevent digestive fatigue from rich gravies. Wazwan dinner is scheduled on Days 2 & 5 with lighter herbal kahwa breaks between main meals.
      </div>
    </div>
    {make_footer(DEST, 4)}
  </div>
    """

# PAGE 5: TOUR TAKEN OR PLACES TO VISIT
def page5_html():
    return f"""
  <div class="page" id="page5">
    {make_header(SYSTEM_BADGE, "SECTION 5: PLACES TO VISIT")}
    <div class="page-hero-banner">
      <div>
        <span class="eyebrow">CURATED SIGHTSEEING</span>
        <h1>Tours & <span>Attractions</span></h1>
        <div class="accent-bar"></div>
        <p>A handpicked itinerary of iconic Kashmir wonders — from morning mist on Dal Lake to the snow summits of Apharwat Peak.</p>
      </div>
      <div class="page-hero-thumb">
        <img src="https://images.unsplash.com/photo-1564013799919-ab600027ffc6?auto=format&fit=crop&w=600&q=80" alt="Attractions">
      </div>
    </div>

    <div class="page-content">
      <div class="grid-2">
        <div class="card">
          <img style="height:125px; object-fit:cover;" src="https://images.unsplash.com/photo-1595815771614-ade9d652a65d?auto=format&fit=crop&w=500&q=80" alt="Dal Lake">
          <div class="card-padded">
            <span class="tag-pill tag-green" style="margin-bottom:4px;">Day 2 · 06:30 – 08:30 AM</span>
            <div class="card-header">Dal Lake Shikara & Floating Market</div>
            <p style="font-size:11px; color:var(--text-muted); line-height:1.4; margin-bottom:8px;">Glide across the calm glassy waters as dawn rises over Zabarwan hills. Visit the century-old floating vegetable bazaar where boatmen barter vegetables from canoe to canoe.</p>
            <div style="font-size:10.5px; color:var(--navy); font-weight:600; line-height:1.3;">
              ✓ Private wooden shikara with cushions & blanket<br>
              ✓ Char Chinar & Lotus garden photo stop<br>
              ✓ Traditional kahwa served on board
            </div>
          </div>
        </div>

        <div class="card">
          <img style="height:125px; object-fit:cover;" src="https://images.unsplash.com/photo-1564013799919-ab600027ffc6?auto=format&fit=crop&w=500&q=80" alt="Gulmarg Gondola">
          <div class="card-padded">
            <span class="tag-pill tag-blue" style="margin-bottom:4px;">Day 3 · 10:00 AM – 02:30 PM</span>
            <div class="card-header">Gulmarg Gondola to Apharwat (Phase 1 & 2)</div>
            <p style="font-size:11px; color:var(--text-muted); line-height:1.4; margin-bottom:8px;">Ride Asia's highest operating cable car to 3,980 meters altitude. Walk on deep powder snow with 360-degree views of Nanga Parbat and Pir Panjal ranges.</p>
            <div style="font-size:10.5px; color:var(--navy); font-weight:600; line-height:1.3;">
              ✓ VIP fast-track Phase 1 & Phase 2 cable car passes<br>
              ✓ Snow boot & woollen coat rental included<br>
              ✓ Certified mountain guide for snow walk
            </div>
          </div>
        </div>

        <div class="card">
          <img style="height:125px; object-fit:cover;" src="https://images.unsplash.com/photo-1595815771614-ade9d652a65d?auto=format&fit=crop&w=500&q=80" alt="Old Srinagar">
          <div class="card-padded">
            <span class="tag-pill tag-gold" style="margin-bottom:4px;">Day 4 · 03:00 – 06:30 PM</span>
            <div class="card-header">Old Srinagar & Artisan Heritage Trail</div>
            <p style="font-size:11px; color:var(--text-muted); line-height:1.4; margin-bottom:8px;">Walk through 600-year-old architectural streets of Shehr-e-Khaas. Marvel at the 378 deodar pillars of Jama Masjid and observe master walnut woodcarvers at work.</p>
            <div style="font-size:10.5px; color:var(--navy); font-weight:600; line-height:1.3;">
              ✓ Shah-e-Hamdan wooden shrine architecture<br>
              ✓ Saffron & dried fruit master guild tasting<br>
              ✓ Pashmina weaving demonstration
            </div>
          </div>
        </div>

        <div class="card">
          <img style="height:125px; object-fit:cover;" src="https://images.unsplash.com/photo-1595815771614-ade9d652a65d?auto=format&fit=crop&w=500&q=80" alt="Pahalgam Valleys">
          <div class="card-padded">
            <span class="tag-pill tag-teal" style="margin-bottom:4px;">Day 5 · 09:30 AM – 04:00 PM</span>
            <div class="card-header">Betaab Valley & Lidder Riverside Trail</div>
            <p style="font-size:11px; color:var(--text-muted); line-height:1.4; margin-bottom:8px;">Explore the picturesque valley named after the movie Betaab. Stroll along the crystal blue Lidder river and experience alpine meadows encircled by pine peaks.</p>
            <div style="font-size:10.5px; color:var(--navy); font-weight:600; line-height:1.3;">
              ✓ Private entry to Betaab Valley sanctuary<br>
              ✓ Riverside trout lunch pavilion reservation<br>
              ✓ Gentle pine forest walking trail
            </div>
          </div>
        </div>
      </div>

      <div class="notice-box">
        <strong>Trip Consultant Agent Advice (Score 9.1/10):</strong> Gondola Phase 2 requires morning departure to avoid afternoon cloud cover. Tickets are pre-booked in slot 10:00 AM to eliminate on-site queues.
      </div>
    </div>
    {make_footer(DEST, 5)}
  </div>
    """

# PAGE 6: TRAVELLING
def page6_html():
    return f"""
  <div class="page" id="page6">
    {make_header(SYSTEM_BADGE, "SECTION 6: TRANSIT & TRANSPORT")}
    <div class="page-hero-banner">
      <div>
        <span class="eyebrow">LOGISTICS & MOBILITY</span>
        <h1>Seamless <span>Travelling</span></h1>
        <div class="accent-bar"></div>
        <p>Private heated 4x4 mountain transit, confirmed flight schedules, and zero-hassle airport transfers across the valley.</p>
      </div>
      <div class="page-hero-thumb">
        <img src="https://images.unsplash.com/photo-1549317661-bd32c8ce0db2?auto=format&fit=crop&w=600&q=80" alt="Vehicle Transit">
      </div>
    </div>

    <div class="page-content">
      <div class="card card-padded">
        <div class="card-header">Confirmed Inbound & Outbound Flight Details</div>
        <table class="styled-table">
          <thead>
            <tr>
              <th>Sector</th>
              <th>Airline & Flight</th>
              <th>Departure</th>
              <th>Arrival</th>
              <th>Baggage</th>
              <th class="num">Status</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td><strong>Delhi (DEL) → Srinagar (SXR)</strong></td>
              <td>IndiGo • 6E 214</td>
              <td>15 Nov · 07:15 AM (T2)</td>
              <td>15 Nov · 08:50 AM</td>
              <td>15 kg check-in + 7 kg cabin</td>
              <td class="num"><span class="tag-pill tag-green">Confirmed</span></td>
            </tr>
            <tr>
              <td><strong>Srinagar (SXR) → Delhi (DEL)</strong></td>
              <td>IndiGo • 6E 532</td>
              <td>21 Nov · 03:40 PM</td>
              <td>21 Nov · 05:15 PM (T2)</td>
              <td>15 kg check-in + 7 kg cabin</td>
              <td class="num"><span class="tag-pill tag-green">Confirmed</span></td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="grid-2">
        <div class="card card-padded">
          <div class="card-header">Dedicated Private 4x4 Vehicle</div>
          <p style="font-size:11.5px; color:var(--text-muted); line-height:1.45; margin-bottom:10px;">
            A dedicated Mahindra Scorpio 4WD / Toyota Innova Crysta is assigned for your entire 7-day trip, featuring snow chains, heavy heating, and an experienced local mountain chauffeur.
          </p>
          <ul style="font-size:11px; color:var(--text-dark); list-style:none; line-height:1.6;">
            <li>✓ 24/7 dedicated chauffeur for all city & mountain transfers</li>
            <li>✓ Snow chains pre-installed for Tangmarg to Gulmarg climb</li>
            <li>✓ All toll taxes, state parking permits, and driver allowances paid</li>
            <li>✓ Clean sanitized interior with bottled mineral water & tissues</li>
          </ul>
        </div>

        <div class="card card-padded">
          <div class="card-header">Mountain Route Timelines</div>
          <div style="display:flex; flex-direction:column; gap:8px;">
            <div style="background:#f8fafc; padding:8px 10px; border-radius:6px; font-size:11px;">
              <strong>Srinagar Airport → Gulmarg</strong><br>
              <span style="color:var(--text-muted);">54 km · Approx 1 hr 45 min · Scenic apple orchard route</span>
            </div>
            <div style="background:#f8fafc; padding:8px 10px; border-radius:6px; font-size:11px;">
              <strong>Gulmarg → Srinagar Heritage District</strong><br>
              <span style="color:var(--text-muted);">51 km · Approx 1 hr 30 min · Boulevard road entry</span>
            </div>
            <div style="background:#f8fafc; padding:8px 10px; border-radius:6px; font-size:11px;">
              <strong>Srinagar → Pahalgam Valley Day Tour</strong><br>
              <span style="color:var(--text-muted);">88 km · Approx 2 hrs 15 min · Saffron fields & willow bat street</span>
            </div>
          </div>
        </div>
      </div>

      <div class="card card-padded" style="background:#f0f9ff; border-color:#bfdbfe;">
        <div style="font-size:12px; font-weight:700; color:var(--navy); margin-bottom:4px;">Airport Security & Winter Transit Guidelines</div>
        <p style="font-size:11px; color:var(--text-muted); line-height:1.4;">
          Srinagar International Airport (SXR) has strict secondary security screening. The private cab will pick you up 3 hours prior to scheduled departure. Electronic power banks and spare batteries must be carried in hand luggage only.
        </p>
      </div>
    </div>
    {make_footer(DEST, 6)}
  </div>
    """

# PAGE 7: BUDGET TOTALING AND TOTAL PAYMENT
def page7_html():
    return f"""
  <div class="page" id="page7">
    {make_header(SYSTEM_BADGE, "SECTION 7: BUDGET & PAYMENT")}
    <div class="page-hero-banner">
      <div>
        <span class="eyebrow">TRANSPARENT ACCOUNTING</span>
        <h1>Budget & <span>Payment</span></h1>
        <div class="accent-bar"></div>
        <p>Complete transparent financial breakdown. Zero hidden charges, all taxes included, with secure milestone-based payment.</p>
      </div>
      <div class="page-hero-thumb">
        <img src="https://images.unsplash.com/photo-1549317661-bd32c8ce0db2?auto=format&fit=crop&w=600&q=80" alt="Finance">
      </div>
    </div>

    <div class="page-content">
      <div class="card">
        <table class="styled-table">
          <thead>
            <tr>
              <th>Item / Service Description</th>
              <th>Category</th>
              <th>Basis / Details</th>
              <th class="num">Amount (INR)</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td><strong>Roundtrip Flights (DEL ↔ SXR)</strong></td>
              <td>Airfare</td>
              <td>2 Adults, IndiGo 15kg baggage included</td>
              <td class="num">₹22,400</td>
            </tr>
            <tr>
              <td><strong>Snowline Lodge Gulmarg (3 Nights)</strong></td>
              <td>Lodging</td>
              <td>Deluxe Alpine Heated Suite, Breakfast included</td>
              <td class="num">₹18,897</td>
            </tr>
            <tr>
              <td><strong>Kashmir Slow Living Homestay (3 Nights)</strong></td>
              <td>Lodging</td>
              <td>Heritage Cedar Room, Traditional Breakfast</td>
              <td class="num">₹8,925</td>
            </tr>
            <tr>
              <td><strong>Dedicated Heated 4x4 Cab (7 Days)</strong></td>
              <td>Transit</td>
              <td>Dedicated chauffeur, fuel, snow chains, all tolls</td>
              <td class="num">₹21,000</td>
            </tr>
            <tr>
              <td><strong>Gulmarg Gondola Passes (Phase 1 & 2)</strong></td>
              <td>Sightseeing</td>
              <td>Fast-track VIP snow summit tickets for 2 guests</td>
              <td class="num">₹5,798</td>
            </tr>
            <tr>
              <td><strong>Private Dal Lake Shikara Sunrise Tour</strong></td>
              <td>Experience</td>
              <td>2-Hour chartered shikara with tea & blankets</td>
              <td class="num">₹2,998</td>
            </tr>
            <tr>
              <td><strong>Royal Wazwan 7-Course Dinner Feast</strong></td>
              <td>Dining</td>
              <td>Banquet for 2 at Kashmir Family Kitchen</td>
              <td class="num">₹1,590</td>
            </tr>
            <tr>
              <td><strong>Betaab & Aru Valley Sanctuary Permits</strong></td>
              <td>Permits</td>
              <td>Local wildlife conservation & eco-park passes</td>
              <td class="num">₹1,200</td>
            </tr>
            <tr>
              <td><strong>GST (5%) & Platform Travel Protection</strong></td>
              <td>Taxes</td>
              <td>Mandatory tax and Voyara 24/7 concierge support</td>
              <td class="num">₹4,192</td>
            </tr>
            <tr class="total-row">
              <td colspan="3"><strong>TOTAL INDICATIVE INVESTMENT (2 ADULTS)</strong></td>
              <td class="num" style="color:var(--navy); font-size:16px;">₹97,000</td>
            </tr>
            <tr style="background:#ecfdf5;">
              <td colspan="3"><strong style="color:#047857;">COST PER PERSON</strong></td>
              <td class="num" style="color:#047857; font-size:16px; font-weight:800;">₹48,500</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="grid-2">
        <div class="card card-padded">
          <div class="card-header">Payment Milestone Schedule</div>
          <div style="display:flex; flex-direction:column; gap:8px; font-size:11.5px;">
            <div style="display:flex; justify-content:space-between; border-bottom:1px solid #f1f5f9; padding-bottom:4px;">
              <span><strong>Deposit (25%)</strong> to lock dates:</span>
              <strong style="color:var(--navy);">₹24,250</strong>
            </div>
            <div style="display:flex; justify-content:space-between; border-bottom:1px solid #f1f5f9; padding-bottom:4px;">
              <span><strong>Pre-Departure (50%)</strong> 15 days prior:</span>
              <strong style="color:var(--navy);">₹48,500</strong>
            </div>
            <div style="display:flex; justify-content:space-between;">
              <span><strong>On-Arrival Balance (25%)</strong>:</span>
              <strong style="color:var(--navy);">₹24,250</strong>
            </div>
          </div>
        </div>

        <div class="card card-padded">
          <div class="card-header">Cancellation & Refund Policy</div>
          <ul style="font-size:11px; color:var(--text-muted); list-style:none; line-height:1.5;">
            <li>• <strong>15+ days prior:</strong> 100% refund (minus airline ticket fees)</li>
            <li>• <strong>7–14 days prior:</strong> 75% refund of total package value</li>
            <li>• <strong>Within 7 days:</strong> Weather disruption emergency reschedule guarantee</li>
          </ul>
        </div>
      </div>

      <div class="notice-box">
        <strong>Fare & Booking Agent Verdict (Score 8.5/10):</strong> Pricing reflects locked wholesale accommodation rates for winter 2026. No hidden surcharges for heater usage or vehicle mountain permits.
      </div>
    </div>
    {make_footer(DEST, 7)}
  </div>
    """

# PAGE 8: DAY-BY-DAY ITINERARY & GUIDELINES
def page8_html():
    return f"""
  <div class="page" id="page8">
    {make_header(SYSTEM_BADGE, "SECTION 8: DAY-BY-DAY ITINERARY")}
    <div class="page-hero-banner">
      <div>
        <span class="eyebrow">CHRONOLOGICAL PLAN</span>
        <h1>Day-by-Day <span>Schedule</span></h1>
        <div class="accent-bar"></div>
        <p>A balanced, weather-conscious flow designed to maximize natural daylight, alpine visibility, and cultural relaxation.</p>
      </div>
      <div class="page-hero-thumb">
        <img src="https://images.unsplash.com/photo-1595815771614-ade9d652a65d?auto=format&fit=crop&w=600&q=80" alt="Itinerary">
      </div>
    </div>

    <div class="page-content">
      <div class="card card-padded">
        <div class="timeline-item">
          <div class="time-slot">DAY 1 · 15 NOV</div>
          <div class="timeline-body">
            <div class="timeline-title">Delhi Arrival & Ascent to Gulmarg</div>
            <div class="timeline-desc">08:50 AM arrival at Srinagar Airport. Meet chauffeur, scenic drive via Tangmarg to Snowline Lodge. Check-in, hot kahwa welcome, and evening meadow sunset walk.</div>
          </div>
        </div>

        <div class="timeline-item">
          <div class="time-slot">DAY 2 · 16 NOV</div>
          <div class="timeline-body">
            <div class="timeline-title">Apharwat Peak Snow & Gondola Adventure</div>
            <div class="timeline-desc">10:00 AM cable car ascent through Kongdoori to Apharwat Peak (Phase 2). Snow trek, hot mountain lunch at 3,000m, and evening bukhari fireside dinner.</div>
          </div>
        </div>

        <div class="timeline-item">
          <div class="time-slot">DAY 3 · 17 NOV</div>
          <div class="timeline-body">
            <div class="timeline-title">Pine Forest Treks & Leisure in the Meadow</div>
            <div class="timeline-desc">Guided pine forest nature walk, visit historic St. Mary’s Church and Maharaja Palace ruins. Evening sledging and leisure at Gulmarg golf course snow bowl.</div>
          </div>
        </div>

        <div class="timeline-item">
          <div class="time-slot">DAY 4 · 18 NOV</div>
          <div class="timeline-body">
            <div class="timeline-title">Descent to Srinagar & Dal Lake Shikara</div>
            <div class="timeline-desc">Check-out and transfer to Srinagar Slow Living Homestay. Afternoon sunrise shikara cruise, floating bazaar tour, and evening tea at Kashmir Corner Cafe.</div>
          </div>
        </div>

        <div class="timeline-item">
          <div class="time-slot">DAY 5 · 19 NOV</div>
          <div class="timeline-body">
            <div class="timeline-title">Betaab Valley & Lidder River Day Excursion</div>
            <div class="timeline-desc">Full-day private excursion to Pahalgam. Stroll through Betaab Valley, pine riverbanks, and walnut orchards. Evening return for 7-course royal Wazwan banquet.</div>
          </div>
        </div>

        <div class="timeline-item">
          <div class="time-slot">DAY 6 · 20 NOV</div>
          <div class="timeline-body">
            <div class="timeline-title">Old Srinagar Heritage Walk & Souvenir Guild</div>
            <div class="timeline-desc">Explore Jama Masjid, Shah-e-Hamdan, saffron spice bazaar, and master artisan workshops for authentic GI-tagged Pashmina shawls and papier-mâché crafts.</div>
          </div>
        </div>

        <div class="timeline-item" style="border-bottom:none;">
          <div class="time-slot">DAY 7 · 21 NOV</div>
          <div class="timeline-body">
            <div class="timeline-title">Farewell Noon Chai & Departure Flight</div>
            <div class="timeline-desc">Relaxed morning breakfast with fresh bakery breads. Private transfer to Srinagar Airport for 03:40 PM departure flight back to New Delhi.</div>
          </div>
        </div>
      </div>

      <div class="grid-2">
        <div class="card card-padded" style="background:#eff6ff;">
          <div class="card-header" style="color:#1d4ed8;">Winter Health & Altitude Care</div>
          <p style="font-size:10.5px; color:#1e3a8a; line-height:1.4;">
            Stay hydrated with warm water and saffron kahwa. Gulmarg sits at 2,650m and Apharwat at 3,980m; take gentle steps and carry lip balm, SPF 50 sunscreen, and moisturizing cream.
          </p>
        </div>
        <div class="card card-padded" style="background:#fef3c7;">
          <div class="card-header" style="color:#92400e;">Authentic Shopping Guarantee</div>
          <p style="font-size:10.5px; color:#78350f; line-height:1.4;">
            Look for Kashmir Government GI (Geographical Indication) tags on saffron and Pashmina. The guide will accompany you only to certified government artisan emporiums.
          </p>
        </div>
      </div>
    </div>
    {make_footer(DEST, 8)}
  </div>
    """

# PAGE 9: CONFIRMATION, GUIDELINES & BACK COVER
def page9_html():
    return f"""
  <div class="page" id="page9">
    {make_header(SYSTEM_BADGE, "SECTION 9: CONFIRMATION & CONTACTS")}
    <div class="page-hero-banner">
      <div>
        <span class="eyebrow">OFFICIAL CONFIRMATION</span>
        <h1>Voyara <span>Guarantee</span></h1>
        <div class="accent-bar"></div>
        <p>Your journey is backed by 24/7 dedicated local concierge support, vetted mountain drivers, and guaranteed heated hospitality.</p>
      </div>
      <div class="page-hero-thumb">
        <img src="https://images.unsplash.com/photo-1595815771614-ade9d652a65d?auto=format&fit=crop&w=600&q=80" alt="Back Cover">
      </div>
    </div>

    <div class="page-content">
      <div class="grid-2">
        <div class="card card-padded">
          <div class="card-header">Booking Dossier Credentials</div>
          <table class="styled-table" style="font-size:11px;">
            <tr><td><strong>Booking Reference</strong></td><td>VYR-KSH-2026-98124</td></tr>
            <tr><td><strong>Lead Traveler</strong></td><td>Arjun Mehta (2 Adults)</td></tr>
            <tr><td><strong>Dates</strong></td><td>15 Nov – 21 Nov 2026 (7D/6N)</td></tr>
            <tr><td><strong>AI Council Version</strong></td><td>NVIDIA NIM v2.4 (Fast Turn)</td></tr>
            <tr><td><strong>Audit Status</strong></td><td><span class="tag-pill tag-green">Zero Conflict Passed</span></td></tr>
          </table>
        </div>

        <div class="card card-padded" style="background:#f8fafc;">
          <div class="card-header">24/7 On-Ground Support Contacts</div>
          <div style="font-size:11px; line-height:1.6; color:var(--text-dark);">
            📞 <strong>Voyara Srinagar Concierge:</strong> +91 194 245 8899<br>
            🚗 <strong>Dedicated Chauffeur (Bilal):</strong> +91 98580 12345<br>
            🏨 <strong>Snowline Lodge Desk:</strong> +91 195 425 4400<br>
            🚑 <strong>Srinagar Emergency Medical:</strong> 108 / 112
          </div>
        </div>
      </div>

      <div class="card card-padded">
        <div class="card-header">Responsible Tourism & Cultural Guidelines</div>
        <div class="grid-3" style="font-size:10.5px; color:var(--text-muted); line-height:1.45;">
          <div>
            <strong style="color:var(--navy); display:block; margin-bottom:2px;">Sacred Shrines</strong>
            Dress modestly when entering mosques and shrines. Remove shoes and cover heads with a scarf or cap.
          </div>
          <div>
            <strong style="color:var(--navy); display:block; margin-bottom:2px;">Lake Conservation</strong>
            Dal Lake is an eco-sensitive water body. Do not dispose of plastic bottles or wrappers into the lake.
          </div>
          <div>
            <strong style="color:var(--navy); display:block; margin-bottom:2px;">Local Photography</strong>
            Always ask permission before photographing local artisans, market boatmen, or women in traditional attire.
          </div>
        </div>
      </div>

      <div style="background:var(--navy); color:#ffffff; border-radius:12px; padding:24px; text-align:center; display:flex; flex-direction:column; align-items:center; gap:10px; margin-top:10px;">
        <svg viewBox="0 0 40 40" width="44" height="44" fill="none">
          <circle cx="20" cy="20" r="18" fill="#f59e0b" fill-opacity="0.25"/>
          <path d="M20 4C11.163 4 4 11.163 4 20C4 28.837 11.163 36 20 36C28.837 36 36 28.837 36 20" stroke="#ffffff" stroke-width="2.5" stroke-linecap="round"/>
          <path d="M28 14L16 26L12 22" stroke="#f59e0b" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
        <div style="font-family:'Outfit',sans-serif; font-size:20px; font-weight:800; letter-spacing:0.5px;">VOYARA TOURS & TRAVELS</div>
        <div style="font-family:'Caveat',cursive; font-size:22px; color:#f59e0b;">Let's turn your travel dreams into plans ♡</div>
        <p style="font-size:11px; color:#cbd5e1; max-width:500px;">New Delhi · Srinagar · Kochi · Mumbai · Bengaluru | concierge@voyara.com | www.voyara.com</p>
        <div style="font-size:10px; color:#94a3b8; margin-top:4px;">© 2026 Voyara Technologies Pvt. Ltd. All rights reserved.</div>
      </div>
    </div>
    {make_footer(DEST, 9)}
  </div>
    """

def generate_all():
    pages = [
        ("page1_summary.html", page1_html()),
        ("page2_destination.html", page2_html()),
        ("page3_stays.html", page3_html()),
        ("page4_dining_timings.html", page4_html()),
        ("page5_tours_places_to_visit.html", page5_html()),
        ("page6_travel_transport.html", page6_html()),
        ("page7_budget_payment.html", page7_html()),
        ("page8_itinerary_guidelines.html", page8_html()),
        ("page9_confirmation_backcover.html", page9_html()),
    ]

    # Write each individual page
    for filename, content in pages:
        full_html = wrap_html(f"Kashmir Travel Book — {filename}", content)
        for target_dir in [ROOT_KASHMIR, PLATFORM_KASHMIR]:
            with open(target_dir / filename, "w", encoding="utf-8") as f:
                f.write(full_html)
        print(f"Wrote Kashmir {filename}")

    # Write combined 9-page book
    combined_content = "\n".join(c for _, c in pages)
    combined_html = wrap_html("Voyara — Complete 9-Page Kashmir Travel Book (AI Council Certified)", combined_content)
    for target_dir in [ROOT_KASHMIR, PLATFORM_KASHMIR]:
        with open(target_dir / "kashmir_complete_travel_book.html", "w", encoding="utf-8") as f:
            f.write(combined_html)
    print("Wrote Kashmir kashmir_complete_travel_book.html")

if __name__ == "__main__":
    generate_all()
