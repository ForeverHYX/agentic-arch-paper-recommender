"use strict";
(() => {
  function initHomeLiquidGlass() {
    const cards = Array.from(
      document.querySelectorAll(".home-liquid-card")
    );
    if (!cards.length) return () => {
    };
    const SVG_NS = "http://www.w3.org/2000/svg";
    const XLINK_NS = "http://www.w3.org/1999/xlink";
    const desktopLiquidGlass = window.matchMedia("(min-width: 801px)");
    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
    const POINTER_SYNC_INTERVAL = 40;
    const clamp = (value, min, max) => Math.min(max, Math.max(min, value));
    const lerp = (from, to, t) => from + (to - from) * t;
    const displacementMapCache = /* @__PURE__ */ new Map();
    const smoothstep = (edge0, edge1, value) => {
      const t = clamp((value - edge0) / Math.max(edge1 - edge0, 1e-4), 0, 1);
      return t * t * (3 - 2 * t);
    };
    const roundedRectSDF = (x, y, halfWidth, halfHeight, radius) => {
      const qx = Math.abs(x) - halfWidth + radius;
      const qy = Math.abs(y) - halfHeight + radius;
      const ax = Math.max(qx, 0);
      const ay = Math.max(qy, 0);
      return Math.hypot(ax, ay) + Math.min(Math.max(qx, qy), 0) - radius;
    };
    const liquidRest = {
      lightX: 18,
      lightY: 12,
      angle: 135,
      glow: 0.58
    };
    const ensureSvgRoot = () => {
      let svg = document.getElementById("home-liquid-svg-root");
      if (svg) {
        const defs3 = svg.querySelector("defs");
        if (defs3) {
          return { svg, defs: defs3 };
        }
      }
      svg = document.createElementNS(SVG_NS, "svg");
      svg.setAttribute("id", "home-liquid-svg-root");
      svg.setAttribute("aria-hidden", "true");
      svg.setAttribute("width", "0");
      svg.setAttribute("height", "0");
      svg.style.position = "absolute";
      svg.style.width = "0";
      svg.style.height = "0";
      svg.style.pointerEvents = "none";
      svg.style.overflow = "hidden";
      document.body.appendChild(svg);
      const defs2 = document.createElementNS(SVG_NS, "defs");
      svg.appendChild(defs2);
      return { svg, defs: defs2 };
    };
    const getMapSpec = (width, height, radius) => {
      const mapWidth = clamp(Math.round(width), 160, 360);
      const mapHeight = clamp(Math.round(height), 120, 420);
      const halfWidth = mapWidth * 0.5 - 1.5;
      const halfHeight = mapHeight * 0.5 - 1.5;
      const mapRadius = Math.max(
        6,
        Math.min(radius, Math.min(halfWidth, halfHeight) - 2)
      );
      const normalizedRadius = Number(mapRadius.toFixed(2));
      return {
        mapWidth,
        mapHeight,
        mapRadius,
        key: `${mapWidth}x${mapHeight}x${normalizedRadius}`
      };
    };
    const createDisplacementMap = (mapWidth, mapHeight, radius) => {
      const canvas = document.createElement("canvas");
      const context = canvas.getContext("2d", { alpha: false });
      if (!context) return "";
      canvas.width = mapWidth;
      canvas.height = mapHeight;
      const image = context.createImageData(mapWidth, mapHeight);
      const data = image.data;
      const halfWidth = mapWidth * 0.5 - 1.5;
      const halfHeight = mapHeight * 0.5 - 1.5;
      const maxRadius = radius;
      const edgeWidth = Math.max(14, Math.min(mapWidth, mapHeight) * 0.16);
      const eps = 1.15;
      for (let y = 0; y < mapHeight; y += 1) {
        for (let x = 0; x < mapWidth; x += 1) {
          const px = x + 0.5 - mapWidth * 0.5;
          const py = y + 0.5 - mapHeight * 0.5;
          const dist = roundedRectSDF(px, py, halfWidth, halfHeight, maxRadius);
          const depth = Math.max(-dist, 0);
          let red = 128;
          let blue = 128;
          if (dist <= edgeWidth * 2.6) {
            const gradX = roundedRectSDF(px + eps, py, halfWidth, halfHeight, maxRadius) - roundedRectSDF(px - eps, py, halfWidth, halfHeight, maxRadius);
            const gradY = roundedRectSDF(px, py + eps, halfWidth, halfHeight, maxRadius) - roundedRectSDF(px, py - eps, halfWidth, halfHeight, maxRadius);
            const gradLength = Math.hypot(gradX, gradY) || 1;
            const nx = gradX / gradLength;
            const ny = gradY / gradLength;
            const rim = 1 - smoothstep(0, edgeWidth * 0.92, depth);
            const shoulder = smoothstep(edgeWidth * 0.14, edgeWidth * 0.52, depth) * (1 - smoothstep(edgeWidth * 0.52, edgeWidth * 1.3, depth));
            const plateau = smoothstep(edgeWidth * 1.05, edgeWidth * 1.95, depth) * (1 - smoothstep(edgeWidth * 1.95, edgeWidth * 3.1, depth));
            const refraction = rim * 0.84 + shoulder * 0.24 + plateau * 0.06;
            const dome = plateau * 0.12;
            const domeX = px / Math.max(halfWidth, 1) * dome * 26;
            const domeY = py / Math.max(halfHeight, 1) * dome * 26;
            const shiftX = nx * refraction * 88 - domeX;
            const shiftY = ny * refraction * 88 - domeY;
            red = clamp(Math.round(128 + shiftX), 0, 255);
            blue = clamp(Math.round(128 + shiftY), 0, 255);
          }
          const offset = (y * mapWidth + x) * 4;
          data[offset] = red;
          data[offset + 1] = 128;
          data[offset + 2] = blue;
          data[offset + 3] = 255;
        }
      }
      context.putImageData(image, 0, 0);
      return canvas.toDataURL("image/png");
    };
    const getDisplacementMap = (width, height, radius) => {
      const spec = getMapSpec(width, height, radius);
      let mapUrl = displacementMapCache.get(spec.key);
      if (!mapUrl) {
        mapUrl = createDisplacementMap(
          spec.mapWidth,
          spec.mapHeight,
          spec.mapRadius
        );
        displacementMapCache.set(spec.key, mapUrl);
      }
      return {
        key: spec.key,
        url: mapUrl
      };
    };
    const setHref = (node, value) => {
      node.setAttribute("href", value);
      node.setAttributeNS(XLINK_NS, "href", value);
    };
    const createNode = (tag, attrs) => {
      const node = document.createElementNS(SVG_NS, tag);
      Object.entries(attrs).forEach(
        ([key, value]) => node.setAttribute(key, String(value))
      );
      return node;
    };
    const createFilter = (defs2, id) => {
      defs2.querySelector(`#${id}`)?.remove();
      const filter = createNode("filter", {
        id,
        x: "-2%",
        y: "-2%",
        width: "104%",
        height: "104%",
        "color-interpolation-filters": "sRGB"
      });
      const image = createNode("feImage", {
        x: "0",
        y: "0",
        width: "100%",
        height: "100%",
        result: "DISPLACEMENT_MAP",
        preserveAspectRatio: "none"
      });
      filter.appendChild(image);
      filter.appendChild(
        createNode("feColorMatrix", {
          in: "DISPLACEMENT_MAP",
          type: "matrix",
          values: [
            "0.3 0.3 0.3 0 0",
            "0.3 0.3 0.3 0 0",
            "0.3 0.3 0.3 0 0",
            "0 0 0 1 0"
          ].join(" "),
          result: "EDGE_INTENSITY"
        })
      );
      const edgeMask = createNode("feComponentTransfer", {
        in: "EDGE_INTENSITY",
        result: "EDGE_MASK"
      });
      const edgeMaskAlpha = createNode("feFuncA", {
        type: "discrete",
        tableValues: "0 0.09 1"
      });
      edgeMask.appendChild(edgeMaskAlpha);
      filter.appendChild(edgeMask);
      filter.appendChild(
        createNode("feOffset", {
          in: "SourceGraphic",
          dx: "0",
          dy: "0",
          result: "CENTER_ORIGINAL"
        })
      );
      const channels = [
        ["RED", "1 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 1 0", 1],
        ["GREEN", "0 0 0 0 0  0 1 0 0 0  0 0 0 0 0  0 0 0 1 0", 1],
        ["BLUE", "0 0 0 0 0  0 0 0 0 0  0 0 1 0 0  0 0 0 1 0", 1]
      ];
      const displacements = channels.map(([name, matrix, channelScale]) => {
        const displacement = createNode("feDisplacementMap", {
          in: "SourceGraphic",
          in2: "DISPLACEMENT_MAP",
          scale: channelScale,
          xChannelSelector: "R",
          yChannelSelector: "B",
          result: `${name}_DISPLACED`
        });
        filter.appendChild(displacement);
        filter.appendChild(
          createNode("feColorMatrix", {
            in: `${name}_DISPLACED`,
            type: "matrix",
            values: matrix,
            result: `${name}_CHANNEL`
          })
        );
        return displacement;
      });
      filter.appendChild(
        createNode("feBlend", {
          in: "GREEN_CHANNEL",
          in2: "BLUE_CHANNEL",
          mode: "screen",
          result: "GB_BLEND"
        })
      );
      filter.appendChild(
        createNode("feBlend", {
          in: "RED_CHANNEL",
          in2: "GB_BLEND",
          mode: "screen",
          result: "RGB_BLEND"
        })
      );
      const blur = createNode("feGaussianBlur", {
        in: "RGB_BLEND",
        stdDeviation: "0.32",
        result: "ABERRATED_BLURRED"
      });
      filter.appendChild(
        blur
      );
      filter.appendChild(
        createNode("feComposite", {
          in: "ABERRATED_BLURRED",
          in2: "EDGE_MASK",
          operator: "in",
          result: "EDGE_ABERRATION"
        })
      );
      const invertedMask = createNode("feComponentTransfer", {
        in: "EDGE_MASK",
        result: "INVERTED_MASK"
      });
      invertedMask.appendChild(
        createNode("feFuncA", {
          type: "table",
          tableValues: "1 0"
        })
      );
      filter.appendChild(invertedMask);
      filter.appendChild(
        createNode("feComposite", {
          in: "CENTER_ORIGINAL",
          in2: "INVERTED_MASK",
          operator: "in",
          result: "CENTER_CLEAN"
        })
      );
      filter.appendChild(
        createNode("feComposite", {
          in: "EDGE_ABERRATION",
          in2: "CENTER_CLEAN",
          operator: "over",
          result: "FINAL_COMPOSITE"
        })
      );
      filter.appendChild(
        createNode("feComposite", {
          in: "FINAL_COMPOSITE",
          in2: "SourceAlpha",
          operator: "in"
        })
      );
      defs2.appendChild(filter);
      return {
        filter,
        image,
        edgeMaskAlpha,
        displacements,
        blur
      };
    };
    const updateFilter = (refs, mapUrl, scale, aberration) => {
      setHref(refs.image, mapUrl);
      refs.edgeMaskAlpha.setAttribute(
        "tableValues",
        `0 ${Math.min(aberration * 0.05, 0.24).toFixed(3)} 1`
      );
      const channelScales = [
        scale,
        Math.max(scale * (1 - aberration * 0.05), 1),
        Math.max(scale * (1 - aberration * 0.1), 1)
      ];
      refs.displacements.forEach((displacement, index) => {
        displacement.setAttribute("scale", channelScales[index].toFixed(3));
      });
      refs.blur.setAttribute(
        "stdDeviation",
        Math.max(0.1, 0.5 - aberration * 0.1).toFixed(3)
      );
    };
    const { defs } = ensureSvgRoot();
    const states = cards.flatMap((card, index) => {
      const warp = card.querySelector(".home-liquid-warp");
      if (!warp) {
        return [];
      }
      const globalAmbient = card.classList.contains("home-profile-card") || card.classList.contains("home-news-card") || card.classList.contains("ambient-liquid-card");
      card.classList.contains("home-profile-card") || card.classList.contains("home-news-card");
      return [{
        card,
        warp,
        id: `home-liquid-filter-${index + 1}`,
        width: 0,
        height: 0,
        radius: 0,
        theme: "",
        mapKey: "",
        displacementScale: 0,
        aberration: 0,
        backdropFilter: "",
        active: false,
        focused: false,
        globalAmbient,
        filterRefs: null,
        bounds: { left: 0, top: 0, width: 0, height: 0 },
        current: { ...liquidRest },
        target: { ...liquidRest },
        rendered: { ...liquidRest }
      }];
    });
    if (!states.length) return () => {
    };
    const syncGeometry = (state) => {
      const rect = state.card.getBoundingClientRect();
      state.bounds.left = rect.left;
      state.bounds.top = rect.top;
      state.bounds.width = rect.width;
      state.bounds.height = rect.height;
      return rect;
    };
    const clearFilter = (state) => {
      if (!state.active && !state.backdropFilter) {
        return;
      }
      state.active = false;
      state.backdropFilter = "";
      state.warp.style.filter = "";
      state.warp.style.backdropFilter = "";
      state.warp.style.removeProperty("-webkit-backdrop-filter");
      state.current = { ...liquidRest };
      state.target = { ...liquidRest };
      state.rendered = { ...liquidRest };
    };
    const syncFilter = (state) => {
      const rect = syncGeometry(state);
      const styles = getComputedStyle(state.card);
      const width = Math.round(rect.width);
      const height = Math.round(rect.height);
      const radius = parseFloat(styles.borderTopLeftRadius) || 32;
      const theme = document.documentElement.getAttribute("data-theme") === "dark" ? "dark" : "light";
      const warpVisible = getComputedStyle(state.warp).display !== "none";
      const displacementScale = parseFloat(styles.getPropertyValue("--liquid-displacement-scale")) || (theme === "dark" ? 22 : 25);
      const aberration = parseFloat(styles.getPropertyValue("--liquid-aberration")) || (theme === "dark" ? 1.4 : 1.8);
      const backdropFilter = `blur(${styles.getPropertyValue("--liquid-blur").trim() || "22px"}) saturate(${styles.getPropertyValue("--liquid-saturation").trim() || "180%"}) brightness(${styles.getPropertyValue("--liquid-brightness").trim() || "1.08"})`;
      const enabled = desktopLiquidGlass.matches && warpVisible && width >= 20 && height >= 20;
      const runtimeEnabled = enabled && (reduceMotion.matches || state.focused || state.globalAmbient);
      if (!runtimeEnabled) {
        state.width = width;
        state.height = height;
        state.radius = radius;
        state.theme = theme;
        state.displacementScale = displacementScale;
        state.aberration = aberration;
        state.mapKey = "";
        clearFilter(state);
        return;
      }
      const geometryChanged = state.width !== width || state.height !== height || state.radius !== radius;
      const themeChanged = state.theme !== theme;
      const filterChanged = state.displacementScale !== displacementScale || state.aberration !== aberration;
      const backdropChanged = state.backdropFilter !== backdropFilter;
      state.width = width;
      state.height = height;
      state.radius = radius;
      state.theme = theme;
      state.displacementScale = displacementScale;
      state.aberration = aberration;
      state.backdropFilter = backdropFilter;
      if (state.active && !geometryChanged && !themeChanged && !filterChanged && !backdropChanged) {
        return;
      }
      const refs = state.filterRefs ?? (state.filterRefs = createFilter(defs, state.id));
      if (geometryChanged || !state.mapKey || filterChanged || themeChanged) {
        const map = getDisplacementMap(width, height, radius);
        state.mapKey = map.key;
        updateFilter(refs, map.url, displacementScale, aberration);
      }
      state.warp.style.filter = `url(#${state.id})`;
      state.warp.style.backdropFilter = backdropFilter;
      state.warp.style.setProperty(
        "-webkit-backdrop-filter",
        backdropFilter
      );
      state.active = true;
    };
    let rafId = 0;
    let targetSyncRafId = 0;
    let targetSyncTimeoutId = 0;
    let lastTargetSyncAt = 0;
    let geometrySyncRafId = 0;
    let filterSyncRafId = 0;
    let refreshTargetsAfterFilter = false;
    let focusedStateId = "";
    const stateDelta = (from, to) => Math.abs(from.lightX - to.lightX) + Math.abs(from.lightY - to.lightY) + Math.abs(from.angle - to.angle) + Math.abs(from.glow - to.glow);
    const applyState = (state, force = false) => {
      if (!force && stateDelta(state.current, state.rendered) < 0.12) {
        return false;
      }
      const lightX = Number(state.current.lightX.toFixed(2));
      const lightY = Number(state.current.lightY.toFixed(2));
      const angle = Number(state.current.angle.toFixed(2));
      const glow = Number(state.current.glow.toFixed(3));
      state.card.style.setProperty("--liquid-light-x", `${lightX}%`);
      state.card.style.setProperty("--liquid-light-y", `${lightY}%`);
      state.card.style.setProperty("--liquid-angle", `${angle}deg`);
      state.card.style.setProperty("--liquid-glow", glow.toFixed(3));
      state.rendered = {
        lightX,
        lightY,
        angle,
        glow
      };
      return true;
    };
    const resetTarget = (state) => {
      state.target.lightX = liquidRest.lightX;
      state.target.lightY = liquidRest.lightY;
      state.target.angle = liquidRest.angle;
      state.target.glow = liquidRest.glow;
    };
    const isPointerNearState = (state) => {
      const margin = clamp(
        Math.max(state.bounds.width, state.bounds.height) * 0.28,
        88,
        220
      );
      return pagePointer.x >= state.bounds.left - margin && pagePointer.x <= state.bounds.left + state.bounds.width + margin && pagePointer.y >= state.bounds.top - margin && pagePointer.y <= state.bounds.top + state.bounds.height + margin;
    };
    const syncFocusedState = () => {
      if (!desktopLiquidGlass.matches || reduceMotion.matches) {
        const hadFocus = focusedStateId !== "";
        focusedStateId = "";
        states.forEach((state) => {
          state.focused = false;
          if (!state.globalAmbient) {
            resetTarget(state);
          }
        });
        return hadFocus;
      }
      const nextFocusedId = states.filter((state) => {
        const width = Math.max(state.bounds.width, 1);
        const height = Math.max(state.bounds.height, 1);
        return width >= 20 && height >= 20 && isPointerNearState(state);
      }).map((state) => {
        const centerX = state.bounds.left + state.bounds.width * 0.5;
        const centerY = state.bounds.top + state.bounds.height * 0.5;
        const distance = Math.hypot(pagePointer.x - centerX, pagePointer.y - centerY);
        return { state, distance };
      }).sort((left, right) => left.distance - right.distance)[0]?.state.id ?? "";
      const focusChanged = nextFocusedId !== focusedStateId;
      focusedStateId = nextFocusedId;
      states.forEach((state) => {
        state.focused = state.id === focusedStateId;
        if (!state.focused && !state.globalAmbient) {
          resetTarget(state);
        }
      });
      return focusChanged;
    };
    const frame = () => {
      rafId = 0;
      let pending = false;
      states.forEach((state) => {
        state.current.lightX = lerp(state.current.lightX, state.target.lightX, 0.14);
        state.current.lightY = lerp(state.current.lightY, state.target.lightY, 0.14);
        state.current.angle = lerp(state.current.angle, state.target.angle, 0.14);
        state.current.glow = lerp(state.current.glow, state.target.glow, 0.12);
        applyState(state);
        const delta = stateDelta(state.current, state.target);
        if (delta > 0.08) pending = true;
      });
      if (pending) {
        rafId = window.requestAnimationFrame(frame);
      }
    };
    const scheduleFrame = () => {
      if (!rafId) {
        rafId = window.requestAnimationFrame(frame);
      }
    };
    const scheduleFilterSync = (refreshTargets = false) => {
      refreshTargetsAfterFilter = refreshTargetsAfterFilter || refreshTargets;
      if (filterSyncRafId) {
        return;
      }
      filterSyncRafId = window.requestAnimationFrame(() => {
        filterSyncRafId = 0;
        states.forEach(syncFilter);
        if (refreshTargetsAfterFilter) {
          refreshTargetsAfterFilter = false;
          scheduleTargetSync();
        }
      });
    };
    const cleanups = [];
    const pagePointer = { x: window.innerWidth * 0.5, y: window.innerHeight * 0.2 };
    states.forEach(syncGeometry);
    syncFocusedState();
    states.forEach((state) => {
      syncFilter(state);
      applyState(state, true);
    });
    const syncTargetsFromPointer = () => {
      if (!desktopLiquidGlass.matches || reduceMotion.matches) {
        return;
      }
      if (syncFocusedState()) {
        scheduleFilterSync();
      }
      const viewportWidth = Math.max(window.innerWidth, 1);
      const viewportHeight = Math.max(window.innerHeight, 1);
      const ambientX = clamp(pagePointer.x / viewportWidth * 100, 10, 90);
      const ambientY = clamp(pagePointer.y / viewportHeight * 100, 8, 92);
      const ambientDx = (ambientX - 50) / 50;
      const ambientDy = (ambientY - 50) / 50;
      states.forEach((state) => {
        const width = Math.max(state.bounds.width, 1);
        const height = Math.max(state.bounds.height, 1);
        if (state.globalAmbient) {
          state.target.lightX = ambientX;
          state.target.lightY = ambientY;
          state.target.angle = 135 + ambientDx * 18 + ambientDy * 10;
          state.target.glow = 0.58 + (Math.abs(ambientDx) + Math.abs(ambientDy)) * 0.035;
          return;
        }
        if (width < 20 || height < 20 || !state.focused) {
          resetTarget(state);
          return;
        }
        const x = clamp((pagePointer.x - state.bounds.left) / width * 100, 8, 92);
        const y = clamp((pagePointer.y - state.bounds.top) / height * 100, 8, 92);
        const dx = (x - 50) / 50;
        const dy = (y - 50) / 50;
        state.target.lightX = x;
        state.target.lightY = y;
        state.target.angle = 135 + dx * 18 + dy * 10;
        state.target.glow = 0.58 + (Math.abs(dx) + Math.abs(dy)) * 0.035;
      });
      if (states.some((state) => stateDelta(state.current, state.target) > 0.08)) {
        scheduleFrame();
      }
    };
    function scheduleTargetSync() {
      if (!desktopLiquidGlass.matches || reduceMotion.matches || targetSyncRafId || targetSyncTimeoutId) {
        return;
      }
      const delay = Math.max(0, POINTER_SYNC_INTERVAL - (performance.now() - lastTargetSyncAt));
      const requestSync = () => {
        targetSyncTimeoutId = 0;
        if (targetSyncRafId) {
          return;
        }
        targetSyncRafId = window.requestAnimationFrame(() => {
          targetSyncRafId = 0;
          lastTargetSyncAt = performance.now();
          syncTargetsFromPointer();
        });
      };
      if (delay > 0) {
        targetSyncTimeoutId = window.setTimeout(requestSync, delay);
      } else {
        requestSync();
      }
    }
    const scheduleGeometrySync = () => {
      if (!desktopLiquidGlass.matches || geometrySyncRafId) {
        return;
      }
      geometrySyncRafId = window.requestAnimationFrame(() => {
        geometrySyncRafId = 0;
        states.forEach(syncGeometry);
        scheduleTargetSync();
      });
    };
    if (!reduceMotion.matches) {
      const handlePagePointerMove = (event) => {
        pagePointer.x = event.clientX;
        pagePointer.y = event.clientY;
        scheduleTargetSync();
      };
      const handlePagePointerReset = () => {
        pagePointer.x = window.innerWidth * 0.5;
        pagePointer.y = window.innerHeight * 0.2;
        scheduleTargetSync();
      };
      window.addEventListener("pointermove", handlePagePointerMove, { passive: true });
      window.addEventListener("pointerleave", handlePagePointerReset);
      window.addEventListener("pointercancel", handlePagePointerReset);
      window.addEventListener("blur", handlePagePointerReset);
      cleanups.push(() => {
        window.removeEventListener("pointermove", handlePagePointerMove);
        window.removeEventListener("pointerleave", handlePagePointerReset);
        window.removeEventListener("pointercancel", handlePagePointerReset);
        window.removeEventListener("blur", handlePagePointerReset);
      });
      scheduleTargetSync();
    }
    const resizeObserver = new ResizeObserver(() => {
      scheduleFilterSync(true);
    });
    states.forEach((state) => resizeObserver.observe(state.card));
    const themeObserver = new MutationObserver(() => {
      scheduleFilterSync();
    });
    themeObserver.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["data-theme"]
    });
    const handleResize = () => {
      scheduleFilterSync(true);
    };
    window.addEventListener("resize", handleResize, { passive: true });
    window.addEventListener("scroll", scheduleGeometrySync, { passive: true });
    const handleMotionChange = () => {
      if (reduceMotion.matches) {
        states.forEach((state) => {
          state.current = { ...liquidRest };
          state.target = { ...liquidRest };
          state.rendered = { ...liquidRest };
          applyState(state, true);
        });
        scheduleFilterSync(true);
        return;
      }
      scheduleFilterSync(true);
      scheduleTargetSync();
    };
    const handleBreakpointChange = () => {
      scheduleFilterSync(true);
    };
    if (typeof reduceMotion.addEventListener === "function") {
      reduceMotion.addEventListener("change", handleMotionChange);
      cleanups.push(() => reduceMotion.removeEventListener("change", handleMotionChange));
    } else if (typeof reduceMotion.addListener === "function") {
      reduceMotion.addListener(handleMotionChange);
      cleanups.push(() => reduceMotion.removeListener(handleMotionChange));
    }
    if (typeof desktopLiquidGlass.addEventListener === "function") {
      desktopLiquidGlass.addEventListener("change", handleBreakpointChange);
      cleanups.push(
        () => desktopLiquidGlass.removeEventListener("change", handleBreakpointChange)
      );
    } else if (typeof desktopLiquidGlass.addListener === "function") {
      desktopLiquidGlass.addListener(handleBreakpointChange);
      cleanups.push(
        () => desktopLiquidGlass.removeListener(handleBreakpointChange)
      );
    }
    return () => {
      if (rafId) {
        window.cancelAnimationFrame(rafId);
      }
      if (targetSyncRafId) {
        window.cancelAnimationFrame(targetSyncRafId);
      }
      if (targetSyncTimeoutId) {
        window.clearTimeout(targetSyncTimeoutId);
      }
      if (geometrySyncRafId) {
        window.cancelAnimationFrame(geometrySyncRafId);
      }
      if (filterSyncRafId) {
        window.cancelAnimationFrame(filterSyncRafId);
      }
      resizeObserver.disconnect();
      themeObserver.disconnect();
      window.removeEventListener("resize", handleResize);
      window.removeEventListener("scroll", scheduleGeometrySync);
      cleanups.forEach((cleanup) => cleanup());
      states.forEach((state) => state.filterRefs?.filter.remove());
    };
  }
  // Auto-initialize on DOM ready
  if (typeof document !== "undefined") {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", initHomeLiquidGlass);
    } else {
      initHomeLiquidGlass();
    }
  }
})();
