/**
 * Voyara Travel Transitions & Loader Engine
 * Handles 3D Book Page Turns and Full-Screen Vehicle Page Wipes.
 */

class TravelTransitionEngine {
  constructor() {
    this.initOverlay();
  }

  initOverlay() {
    if (document.getElementById('travel-transition-overlay')) return;

    const overlay = document.createElement('div');
    overlay.id = 'travel-transition-overlay';
    overlay.style.cssText = `
      position: fixed;
      inset: 0;
      z-index: 9999;
      pointer-events: none;
      overflow: hidden;
      display: flex;
      align-items: center;
      justify-content: center;
    `;
    document.body.appendChild(overlay);
  }

  /**
   * Full-screen Airplane Sweep Transition (Bottom-Left to Top-Right)
   * @param {Function} onMidpoint - Callback when screen is covered to swap DOM/Page
   */
  async triggerAirplaneWipe(onMidpoint) {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      if (typeof onMidpoint === 'function') onMidpoint();
      return;
    }
    const overlay = document.getElementById('travel-transition-overlay');
    overlay.style.pointerEvents = 'all';

    const canvas = document.createElement('div');
    canvas.className = 'wipe-airplane-curtain';
    canvas.innerHTML = `
      <div class="sky-curtain"></div>
      <div class="jet-container">
        <svg class="jet-svg" viewBox="0 0 24 24" fill="currentColor">
          <path d="M21 16v-2l-8-5V3.5c0-.83-.67-1.5-1.5-1.5S10 2.67 10 3.5V9l-8 5v2l8-2.5V19l-2 1.5V22l3.5-1 3.5 1v-1.5L13 19v-5.5l8 2.5z"/>
        </svg>
        <div class="jet-vapor-trail"></div>
      </div>
    `;
    overlay.appendChild(canvas);

    // Midpoint trigger: swap views when screen is fully covered
    setTimeout(() => {
      if (typeof onMidpoint === 'function') onMidpoint();
    }, 600);

    // Cleanup after animation completes
    setTimeout(() => {
      canvas.remove();
      overlay.style.pointerEvents = 'none';
    }, 1200);
  }

  /**
   * Train Sweep Transition (Left to Right)
   */
  async triggerTrainWipe(onMidpoint) {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      if (typeof onMidpoint === 'function') onMidpoint();
      return;
    }
    const overlay = document.getElementById('travel-transition-overlay');
    overlay.style.pointerEvents = 'all';

    const curtain = document.createElement('div');
    curtain.className = 'wipe-train-curtain';
    overlay.appendChild(curtain);

    setTimeout(() => {
      if (typeof onMidpoint === 'function') onMidpoint();
    }, 500);

    setTimeout(() => {
      curtain.remove();
      overlay.style.pointerEvents = 'none';
    }, 1000);
  }

  /**
   * 3D Travel Journal Page Turn Effect
   * @param {HTMLElement} currentContainer - Element flipping away
   * @param {HTMLElement} nextContainer - Element being revealed
   */
  flipBookPage(currentContainer, nextContainer) {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      currentContainer.style.display = 'none';
      currentContainer.classList.remove('page-turn-out', 'page-turn-in');
      nextContainer.style.display = 'block';
      nextContainer.classList.remove('page-turn-out', 'page-turn-in');
      return;
    }
    currentContainer.classList.add('page-turn-out');
    setTimeout(() => {
      currentContainer.style.display = 'none';
      currentContainer.classList.remove('page-turn-out');

      nextContainer.style.display = 'block';
      nextContainer.classList.add('page-turn-in');

      setTimeout(() => {
        nextContainer.classList.remove('page-turn-in');
      }, 600);
    }, 300);
  }
}

export const travelFX = new TravelTransitionEngine();
