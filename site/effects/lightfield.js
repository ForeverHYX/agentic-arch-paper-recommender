"use strict";
(() => {
  function initHomeLightfield() {
    const field = document.querySelector(".home-lightfield");
    if (!field) return () => {
    };
    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
    const coarsePointer = window.matchMedia("(pointer: coarse)");
    const LIGHTFIELD_UPDATE_INTERVAL = [4600, 9200];
    const LIGHTFIELD_TRANSITION = [5200, 9800];
    const POINTER_TRANSITION_MS = 220;
    const POINTER_IDLE_MS = 240;
    const spotsConfig = [
      {
        size: [420, 620],
        blur: [74, 108],
        opacity: [0.42, 0.62],
        x: [-0.02, 0.18],
        y: [0.02, 0.22],
        scale: [0.92, 1.16],
        parallax: 32,
        lightColors: [
          "rgba(99, 102, 241, 0.72)",
          "rgba(59, 130, 246, 0.46)",
          "rgba(59, 130, 246, 0.12)",
          "rgba(59, 130, 246, 0)"
        ],
        darkColors: [
          "rgba(129, 140, 248, 0.74)",
          "rgba(96, 165, 250, 0.48)",
          "rgba(59, 130, 246, 0.14)",
          "rgba(59, 130, 246, 0)"
        ]
      },
      {
        size: [400, 560],
        blur: [72, 102],
        opacity: [0.36, 0.54],
        x: [0.18, 0.42],
        y: [-0.04, 0.18],
        scale: [0.9, 1.18],
        parallax: 26,
        lightColors: [
          "rgba(56, 189, 248, 0.64)",
          "rgba(103, 232, 249, 0.36)",
          "rgba(56, 189, 248, 0.1)",
          "rgba(56, 189, 248, 0)"
        ],
        darkColors: [
          "rgba(34, 211, 238, 0.54)",
          "rgba(59, 130, 246, 0.34)",
          "rgba(56, 189, 248, 0.08)",
          "rgba(56, 189, 248, 0)"
        ]
      },
      {
        size: [360, 520],
        blur: [64, 92],
        opacity: [0.28, 0.42],
        x: [0.52, 0.78],
        y: [0.14, 0.42],
        scale: [0.9, 1.14],
        parallax: 20,
        lightColors: [
          "rgba(168, 85, 247, 0.48)",
          "rgba(192, 132, 252, 0.28)",
          "rgba(192, 132, 252, 0.08)",
          "rgba(192, 132, 252, 0)"
        ],
        darkColors: [
          "rgba(192, 132, 252, 0.5)",
          "rgba(129, 140, 248, 0.28)",
          "rgba(129, 140, 248, 0.08)",
          "rgba(129, 140, 248, 0)"
        ]
      },
      {
        size: [380, 540],
        blur: [68, 96],
        opacity: [0.24, 0.4],
        x: [0.06, 0.24],
        y: [0.58, 0.84],
        scale: [0.92, 1.2],
        parallax: 28,
        lightColors: [
          "rgba(34, 197, 94, 0.22)",
          "rgba(45, 212, 191, 0.2)",
          "rgba(125, 211, 252, 0.08)",
          "rgba(125, 211, 252, 0)"
        ],
        darkColors: [
          "rgba(45, 212, 191, 0.26)",
          "rgba(56, 189, 248, 0.18)",
          "rgba(56, 189, 248, 0.08)",
          "rgba(56, 189, 248, 0)"
        ]
      },
      {
        size: [420, 580],
        blur: [72, 102],
        opacity: [0.26, 0.42],
        x: [0.64, 0.9],
        y: [0.54, 0.86],
        scale: [0.9, 1.16],
        parallax: 24,
        lightColors: [
          "rgba(244, 114, 182, 0.28)",
          "rgba(251, 191, 36, 0.18)",
          "rgba(251, 191, 36, 0.08)",
          "rgba(251, 191, 36, 0)"
        ],
        darkColors: [
          "rgba(236, 72, 153, 0.24)",
          "rgba(168, 85, 247, 0.16)",
          "rgba(129, 140, 248, 0.08)",
          "rgba(129, 140, 248, 0)"
        ]
      },
      {
        size: [300, 420],
        blur: [58, 84],
        opacity: [0.18, 0.3],
        x: [0.34, 0.58],
        y: [0.34, 0.6],
        scale: [0.88, 1.12],
        parallax: 16,
        lightColors: [
          "rgba(255, 255, 255, 0.72)",
          "rgba(224, 242, 254, 0.34)",
          "rgba(224, 242, 254, 0.1)",
          "rgba(224, 242, 254, 0)"
        ],
        darkColors: [
          "rgba(255, 255, 255, 0.18)",
          "rgba(96, 165, 250, 0.16)",
          "rgba(96, 165, 250, 0.06)",
          "rgba(96, 165, 250, 0)"
        ]
      }
    ];
    const rand = (min, max) => min + Math.random() * (max - min);
    const clamp = (value, min, max) => Math.min(max, Math.max(min, value));
    const isDark = () => document.documentElement.getAttribute("data-theme") === "dark";
    const getOpacityBounds = () => isDark() ? { min: 0.14, max: 0.42 } : { min: 0.18, max: 0.6 };
    const chooseMotionTarget = (config) => {
      const opacityBounds = getOpacityBounds();
      return {
        x: rand(config.x[0], config.x[1]),
        y: rand(config.y[0], config.y[1]),
        scale: rand(config.scale[0], config.scale[1]),
        opacity: clamp(rand(config.opacity[0], config.opacity[1]), opacityBounds.min, opacityBounds.max),
        duration: rand(LIGHTFIELD_TRANSITION[0], LIGHTFIELD_TRANSITION[1])
      };
    };
    const chooseGeometry = (config) => ({
      size: rand(config.size[0], config.size[1]),
      blur: rand(config.blur[0], config.blur[1])
    });
    const renderGradient = (colors) => `radial-gradient(circle at 50% 50%, ${colors[0]} 0%, ${colors[1]} 28%, ${colors[2]} 58%, ${colors[3]} 80%)`;
    const pointer = { x: 0, y: 0 };
    let renderRafId = 0;
    let ambientTimerId = 0;
    let pointerIdleTimerId = 0;
    const setTransition = (spot, motionMs, opacityMs = motionMs * 0.72) => {
      spot.element.style.setProperty("--spot-motion-duration", `${Math.round(motionMs)}ms`);
      spot.element.style.setProperty("--spot-opacity-duration", `${Math.round(opacityMs)}ms`);
    };
    const applyGeometry = (spot) => {
      spot.element.style.setProperty("--spot-size", `${spot.size.toFixed(1)}px`);
      spot.element.style.setProperty("--spot-blur", `${spot.blur.toFixed(1)}px`);
    };
    const applyPalette = () => {
      const dark = isDark();
      spots.forEach((spot) => {
        spot.element.style.background = renderGradient(
          dark ? spot.config.darkColors : spot.config.lightColors
        );
      });
    };
    const applySpot = (spot, viewport) => {
      const parallax = coarsePointer.matches ? 0 : spot.config.parallax;
      const px = spot.x * viewport.width + pointer.x * parallax;
      const py = spot.y * viewport.height + pointer.y * parallax;
      spot.element.style.setProperty("--spot-opacity", spot.opacity.toFixed(3));
      spot.element.style.transform = `translate3d(${px.toFixed(1)}px, ${py.toFixed(1)}px, 0) scale(${spot.scale.toFixed(3)})`;
    };
    const renderSpots = () => {
      const viewport = {
        width: window.innerWidth,
        height: window.innerHeight
      };
      spots.forEach((spot) => applySpot(spot, viewport));
    };
    const scheduleRender = () => {
      if (renderRafId || document.visibilityState !== "visible") {
        return;
      }
      renderRafId = window.requestAnimationFrame(() => {
        renderRafId = 0;
        renderSpots();
      });
    };
    const setAmbientTransition = (spot) => {
      setTransition(spot, spot.duration);
    };
    const updateAmbientTargets = () => {
      spots.forEach((spot) => {
        Object.assign(spot, chooseMotionTarget(spot.config));
        setAmbientTransition(spot);
      });
      scheduleRender();
    };
    const clearAmbientTimer = () => {
      if (ambientTimerId) {
        window.clearTimeout(ambientTimerId);
        ambientTimerId = 0;
      }
    };
    const scheduleAmbientUpdate = () => {
      clearAmbientTimer();
      if (reduceMotion.matches || document.visibilityState !== "visible") {
        return;
      }
      ambientTimerId = window.setTimeout(() => {
        ambientTimerId = 0;
        updateAmbientTargets();
        scheduleAmbientUpdate();
      }, rand(LIGHTFIELD_UPDATE_INTERVAL[0], LIGHTFIELD_UPDATE_INTERVAL[1]));
    };
    const resetPointer = () => {
      pointer.x = 0;
      pointer.y = 0;
      spots.forEach((spot) => setTransition(spot, POINTER_TRANSITION_MS, 480));
      scheduleRender();
    };
    const handlePointerMove = (event) => {
      if (reduceMotion.matches || coarsePointer.matches) {
        return;
      }
      const x = clamp(event.clientX / Math.max(window.innerWidth, 1), 0, 1);
      const y = clamp(event.clientY / Math.max(window.innerHeight, 1), 0, 1);
      pointer.x = (x - 0.5) * 42;
      pointer.y = (y - 0.5) * 34;
      spots.forEach((spot) => setTransition(spot, POINTER_TRANSITION_MS, 480));
      scheduleRender();
      if (pointerIdleTimerId) {
        window.clearTimeout(pointerIdleTimerId);
      }
      pointerIdleTimerId = window.setTimeout(() => {
        pointerIdleTimerId = 0;
        spots.forEach(setAmbientTransition);
      }, POINTER_IDLE_MS);
    };
    const stop = () => {
      clearAmbientTimer();
      if (renderRafId) {
        window.cancelAnimationFrame(renderRafId);
        renderRafId = 0;
      }
      if (pointerIdleTimerId) {
        window.clearTimeout(pointerIdleTimerId);
        pointerIdleTimerId = 0;
      }
    };
    const start = () => {
      if (reduceMotion.matches) {
        stop();
        resetPointer();
        return;
      }
      scheduleAmbientUpdate();
    };
    const handleVisibility = () => {
      if (document.visibilityState === "visible") {
        renderSpots();
        start();
      } else {
        stop();
      }
    };
    const handleMotionChange = () => {
      renderSpots();
      start();
    };
    const handleResize = () => {
      scheduleRender();
    };
    const spots = spotsConfig.map((config) => {
      const element = document.createElement("span");
      element.className = "home-lightspot";
      field.appendChild(element);
      const geometry = chooseGeometry(config);
      const target = chooseMotionTarget(config);
      const spot = {
        element,
        config,
        ...geometry,
        ...target
      };
      setTransition(spot, 0, 0);
      applyGeometry(spot);
      return spot;
    });
    applyPalette();
    renderSpots();
    window.requestAnimationFrame(() => {
      spots.forEach(setAmbientTransition);
    });
    const themeObserver = new MutationObserver(() => {
      applyPalette();
      updateAmbientTargets();
    });
    themeObserver.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["data-theme"]
    });
    document.addEventListener("visibilitychange", handleVisibility);
    window.addEventListener("resize", handleResize, { passive: true });
    window.addEventListener("pointermove", handlePointerMove, { passive: true });
    window.addEventListener("pointerleave", resetPointer);
    window.addEventListener("blur", resetPointer);
    if (typeof reduceMotion.addEventListener === "function") {
      reduceMotion.addEventListener("change", handleMotionChange);
    } else if (typeof reduceMotion.addListener === "function") {
      reduceMotion.addListener(handleMotionChange);
    }
    start();
    return () => {
      stop();
      document.removeEventListener("visibilitychange", handleVisibility);
      window.removeEventListener("resize", handleResize);
      window.removeEventListener("pointermove", handlePointerMove);
      window.removeEventListener("pointerleave", resetPointer);
      window.removeEventListener("blur", resetPointer);
      if (typeof reduceMotion.removeEventListener === "function") {
        reduceMotion.removeEventListener("change", handleMotionChange);
      } else if (typeof reduceMotion.removeListener === "function") {
        reduceMotion.removeListener(handleMotionChange);
      }
      themeObserver.disconnect();
      spots.forEach((spot) => spot.element.remove());
    };
  }
  // Auto-initialize on DOM ready
  if (typeof document !== "undefined") {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", initHomeLightfield);
    } else {
      initHomeLightfield();
    }
  }
})();
