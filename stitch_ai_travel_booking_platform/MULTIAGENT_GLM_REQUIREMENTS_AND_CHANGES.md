# Voyara Multi-Agent System & Catalog-Style Booking Guide

## Overview of User Issues & Solutions

This document details the issues identified, architectural requirements, and changes made to satisfy the following requirements:
1. **Catalog-Style Booking Request Review**: The review screen at `#booking?place=<Destination>` previously displayed raw plain text. It now renders a rich, catalog-style summary card with destination artwork, rating, duration, guest details, price itemization, and zero-risk booking assurances.
2. **Multi-Agent System Execution**: Previously, travel planning requests containing custom notes or natural language were blocked by a strict regex match (`QUERY.fullmatch`), causing the system to fall back to generic responses instead of running the agent graph. This has been relaxed so all travel planning queries trigger the multi-agent pipeline.
3. **NVIDIA NIM `glm-5.3-flash` Integration**: Configured the agent runtime and environment to target `z-ai/glm-5.3-flash` across all agent tools.

---

## 1. Booking Request Review: Catalog-Style Implementation

### Problem
When the user navigated to `#booking?place=Kashmir` and submitted the traveler information form by clicking **Review trip request →**, the review container rendered a bare text box with unformatted text lines (as seen in the screenshot):
```
REVIEW YOUR REQUEST
₹49,998
Kashmir × 2 · ₹49,998
2026-10-20 · Voyara Developer · developer@voyara.example.com
Booking request only. Provider confirmation is required; no payment will be taken.
```
This lacked the catalog visual identity (destination photography, rating pills, guest/duration metadata cells, and clean itemized billing).

### Changes Implemented
1. **Frontend Template Helpers (`frontend/templates.js`)**:
   - Exported `photo(imageId)` and `money(amount)` from `createViews` so the review card can format destination images and currency.
2. **Catalog Review Card Component (`frontend/app.js`)**:
   - Replaced bare `.detail-block` with `.booking-review-catalog-card`:
     - **Visual Header**: Cover photo of the destination/stay with orange tag pill and dark blurred rating badge (`★ 4.8 (12.4k reviews)`).
     - **Structured Details Grid**:
       - Travel Date & Duration (e.g. `2026-10-20 · 5 Nights / 6 Days`)
       - Guests / Room breakdown (e.g. `2 Travelers`)
       - Lead Traveler name (`Voyara Developer`)
       - Contact Email & Phone
     - **Itemized Price Breakdown**: Line items with unit pricing, quantity, and bold total estimated quote.
     - **Booking Assurance**: Zero-risk booking notice with guarantee shield.
     - **Action Buttons**: Primary orange `Confirm booking request →` button and outline `Edit details` button.
3. **Responsive Styling (`frontend/connected.css`)**:
   - Added styles for `.booking-review-catalog-card`, `.review-catalog-header`, `.review-details-grid`, `.review-line-items`, `.review-total-price`, and responsive layout for mobile screens.

---

## 2. Multi-Agent System Pipeline

### Why Agents Seemed Not to Run
- The backend `AgentRuntime.reply()` method checked incoming user text with `QUERY.fullmatch(text.strip())`.
- When users submitted trip notes through the planner (e.g., `"Plan my trip. Additional request: Want slow pace and mountain views"`), the regex failed to match.
- This forced the system to return an early clarification response without executing the LangGraph workflow.

### Architecture of the Multi-Agent System
Voyara uses a multi-agent orchestration graph:
```
[User Request]
       │
       ▼
[1. Parse Request & Memory Recall]
       │
       ▼
[2. Resolve Destination]
       │
       ├──► [Explore Agent (Atlas)] ───┐
       ├──► [Stay Agent (Haven)] ──────┤
       ├──► [Tour Guide (Roam)] ───────┼──► [Collect Results]
       ├──► [Food Guide (Saffron)] ────┤            │
       └──► [Support Agent (Anchor)] ──┘            ▼
                                             [Itinerary Planner (Weaver)]
                                                    │
                                                    ▼
                                             [Budget & Booking (Ledger)]
                                                    │
                                                    ▼
                                             [Validation & Synthesize]
                                                    │
                                                    ▼
                                             [Durable Memory Persistence]
```

### Changes Implemented
- Updated `backend/app/agent_runtime.py` to use `QUERY.search(text.strip())` and check for `"plan my trip"` or planning keywords.
- Queries submitted through the AI trip planner now proceed to `TravelOrchestrator` and execute the full specialist agent team.

---

## 3. NVIDIA NIM Key & `glm-5.3-flash` Model Setup

### Key Status Check
- **Current Key Found in `agents/.env`**:
  `NVIDIA_API_KEY=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`
- **Verification Result**:
  - The key is **valid** and authenticated successfully with NVIDIA NIM (`HTTP 200` on `/v1/models` and `/v1/chat/completions` for `openai/gpt-oss-20b`).
  - Available models on NVIDIA NIM include `z-ai/glm-5.3` and `z-ai/glm-5.3-flash`.
  - However, direct requests to `z-ai/glm-5.3-flash` via the public NIM endpoint experienced high latency / read timeouts on the NVIDIA server side.

### Configuration Applied
1. **`agents/config.py`**:
   - Updated default `nim_model` to `"z-ai/glm-5.3-flash"`.
   - Updated default `nim_agent_model` to `"z-ai/glm-5.3-flash"`.
2. **`agents/.env` and `stitch_ai_travel_booking_platform/backend/.env`**:
   - Added:
     ```env
     NVIDIA_API_KEY=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
     NIM_MODEL=z-ai/glm-5.3-flash
     NIM_AGENT_MODEL=z-ai/glm-5.3-flash
     NIM_BASE_URL=https://integrate.api.nvidia.com/v1
     ```

### If You Wish to Update or Use a Fresh NVIDIA API Key
To replace the key with a new one:
1. Open [agents/.env](file:///c:/Users/vvars/OneDrive/Desktop/Iron%20Web/agents/.env)
2. Replace `NVIDIA_API_KEY=...` with your new key:
   ```env
   NVIDIA_API_KEY=nvapi-your-new-key-here
   NIM_MODEL=z-ai/glm-5.3-flash
   NIM_AGENT_MODEL=z-ai/glm-5.3-flash
   ```
3. Restart the background server or run `python scripts/run_voyara.py --port 8088`.
