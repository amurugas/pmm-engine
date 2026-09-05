(() => {
  const initialView = { yaw: -0.72, pitch: 0.52 };
  const state = {
    result: null, view: "pmm", selected: 1,
    yaw: initialView.yaw, pitch: initialView.pitch,
    zoom: 1, threeZoom: 1, pan: [0, 0], drag: null, plotBounds: null
  };
  const byId = (id) => document.getElementById(id);
  const svgNS = "http://www.w3.org/2000/svg";

  function element(name, attributes = {}, text = "") {
    const node = document.createElementNS(svgNS, name);
    Object.entries(attributes).forEach(([key, value]) => node.setAttribute(key, value));
    if (text) node.textContent = text;
    return node;
  }

  function number(id) { return Number(byId(id).value); }

  function finite(value) { return Number.isFinite(value); }

  function utilizationClass(demand) {
    if (!demand || !finite(demand.dcr)) return "demand-unknown";
    if (demand.dcr <= 0.90 + 1e-9) return "demand-safe";
    if (demand.dcr <= 1.00 + 1e-9) return "demand-watch";
    return "demand-fail";
  }

  function plotLoadClass(demand) {
    return demand && finite(demand.dcr) && demand.dcr <= 1.00 + 1e-9 ? "load-inside" : "load-outside";
  }

  function formatNumber(value, digits = 1) {
    return finite(value) ? value.toLocaleString(undefined, { minimumFractionDigits: digits, maximumFractionDigits: digits }) : "N/A";
  }

  function capacityIntersection(demand) {
    if (!demand || !finite(demand.capacity_radius_kip_ft) || !finite(demand.mux_kip_ft) || !finite(demand.muy_kip_ft)) return null;
    const demandRadius = Math.hypot(demand.mux_kip_ft, demand.muy_kip_ft);
    if (!finite(demandRadius) || demandRadius <= Number.EPSILON) return null;
    return [demand.capacity_radius_kip_ft * demand.mux_kip_ft / demandRadius, demand.capacity_radius_kip_ft * demand.muy_kip_ft / demandRadius];
  }

  function demandDetails(demand, heading = "Demand") {
    const radius = demand && finite(demand.capacity_radius_kip_ft) ? `${formatNumber(demand.capacity_radius_kip_ft, 1)} kip-ft` : "N/A";
    const dcr = demand && finite(demand.dcr) ? demand.dcr.toFixed(3) : "N/A";
    const residual = demand && finite(demand.max_contour_axial_residual_kip) ? `${formatNumber(demand.max_contour_axial_residual_kip, 3)} kip` : "N/A";
    const note = demand && demand.note ? demand.note : "None";
    return `${heading}: ${demand.label}\nPu ${formatNumber(demand.pu_kip, 1)} kip · Mx ${formatNumber(demand.mux_kip_ft, 1)} kip-ft · My ${formatNumber(demand.muy_kip_ft, 1)} kip-ft\nCapacity radius ${radius}\nDCR ${dcr} · ${demand.status || "Unknown"}\nEquilibrium residual ${residual} · Warning: ${note}`;
  }

  function inspectable(node, detail) {
    node.classList.add("inspection-target");
    node.setAttribute("tabindex", "0");
    node.setAttribute("data-tooltip", detail);
    node.append(element("title", {}, detail));
    return node;
  }

  function demands() {
    return [...document.querySelectorAll("#demand-table tbody tr")].map((row, index) => {
      const inputs = row.querySelectorAll("input");
      return { label: inputs[0].value || `LC-${index + 1}`, pu_kip: Number(inputs[1].value), mux_kip_ft: Number(inputs[2].value), muy_kip_ft: Number(inputs[3].value) };
    });
  }

  function payload() {
    return {
      schema_version: 1,
      section: { beam_id: byId("beam-id").value.trim() || "B-1", shape: byId("section-shape").value, width_in: number("width"), depth_in: number("depth"), diameter_in: number("diameter"), fc_ksi: number("fc"), fy_ksi: number("fy"), clear_cover_in: number("cover"), tie_bar_size: byId("tie-size").value, longitudinal_bar_size: byId("bar-size").value, maximum_spacing_in: number("spacing") },
      analysis: {
        concrete_model: byId("concrete-model").value,
        integration_method: byId("integration-method").value,
        fiber_divisions: number("fiber-divisions"),
        angle_step_deg: number("dcr-step"),
        include_response_diagrams: true,
        include_onion: state.view === "three",
        onion_angle_step_deg: number("onion-step"),
        onion_layer_count: number("onion-layers")
      },
      demands: demands()
    };
  }

  async function analyze() {
    const status = byId("run-state");
    status.textContent = "Running…";
    byId("run-analysis").disabled = true;
    const started = performance.now();
    try {
      const response = await fetch("/api/analyze", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload()) });
      const body = await response.json();
      if (!response.ok || !body.ok) throw new Error(body.error || `HTTP ${response.status}`);
      state.result = body.result;
      state.selected = Math.min(state.selected, Math.max(0, body.result.demands.length - 1));
      updateResults();
      renderSection();
      renderChart();
      const elapsed = Math.round(performance.now() - started);
      const serverMs = body.meta ? Math.round(body.meta.server_ms) : elapsed;
      status.textContent = `Complete · ${serverMs} ms server / ${elapsed} ms total`;
    } catch (error) {
      status.textContent = `Error: ${error.message}`;
      renderError(error.message);
    } finally {
      byId("run-analysis").disabled = false;
    }
  }

  function updateResults() {
    const rows = [...document.querySelectorAll("#demand-table tbody tr")];
    rows.forEach((row, index) => {
      const result = state.result.demands[index];
      const cells = row.querySelectorAll("td.result");
      cells[0].textContent = result && Number.isFinite(result.dcr) ? result.dcr.toFixed(3) : "—";
      cells[1].textContent = result ? result.status : "—";
      const tier = utilizationClass(result);
      cells[0].className = `result ${tier}`;
      cells[1].className = `result ${tier}`;
      row.classList.toggle("selected-row", index === state.selected);
    });
    const s = state.result.section;
    byId("section-summary").innerHTML = `<div class="metric"><span>Bars</span><strong>${s.bar_count} ${s.longitudinal_bar_size}</strong></div><div class="metric"><span>Steel area</span><strong>${s.steel_area_in2.toFixed(2)} in²</strong></div><div class="metric"><span>ρg</span><strong>${(100 * s.reinforcement_ratio).toFixed(3)}%</strong></div>`;
    const dimensions = s.shape === "circular" ? `Ø${s.diameter} in` : `${s.width} × ${s.depth} in`;
    byId("project-title").textContent = `${s.beam_id || s.name} · ${dimensions} · ACI 318-19`;
    const responseLoad = byId("response-load");
    responseLoad.replaceChildren(...state.result.demands.map((demand, index) => {
      const option = document.createElement("option"); option.value = index; option.textContent = demand.label; return option;
    }));
    responseLoad.value = String(state.selected);
    const analysis = state.result.analysis;
    const maximumResidual = Math.max(0, ...state.result.demands.map(item => item.max_contour_axial_residual_kip || 0));
    byId("analysis-note").textContent = analysis.integration_method === "fiber"
      ? `Fiber integration used ${analysis.fiber_count.toLocaleString()} concrete midpoint fibers (${analysis.fiber_target_size_in.toFixed(3)} in target size; ${(100 * analysis.fiber_area_error_ratio).toFixed(4)}% represented-area error). Maximum demand-contour axial residual: ${maximumResidual.toFixed(3)} kip. Refine the mesh to check convergence.`
      : "Shape integration is exact for the Whitney block and is the recommended production setting.";
  }

  function renderSection() {
    const svg = byId("section-svg");
    svg.replaceChildren();
    svg.setAttribute("viewBox", "0 0 480 330");
    const s = state.result ? state.result.section : { width: number("width"), depth: number("depth") };
    const bars = state.result ? state.result.bars : [];
    const scale = Math.min(330 / s.width, 250 / s.depth);
    const w = s.width * scale, h = s.depth * scale, left = 240 - w / 2, top = 155 - h / 2;
    if (s.shape === "circular") svg.append(element("circle", { cx: 240, cy: 155, r: w / 2, fill: "#edf0ec", stroke: "#27333c", "stroke-width": 2 }));
    else svg.append(element("rect", { x: left, y: top, width: w, height: h, rx: 2, fill: "#edf0ec", stroke: "#27333c", "stroke-width": 2 }));
    bars.forEach(bar => svg.append(element("circle", { cx: 240 + bar.x_in * scale, cy: 155 - bar.y_in * scale, r: Math.max(4, Math.sqrt(bar.area_in2 / Math.PI) * scale), fill: "#d67a31", stroke: "#4c2d18", "stroke-width": 1 })));
    svg.append(element("line", { x1: left, y1: top - 18, x2: left + w, y2: top - 18, stroke: "#60717e" }));
    svg.append(element("text", { x: 240, y: top - 24, "text-anchor": "middle", class: "axis-label" }, `${s.shape === "circular" ? "Ø" : ""}${s.width.toFixed(2)} in`));
    if (s.shape !== "circular") {
      svg.append(element("line", { x1: left - 18, y1: top, x2: left - 18, y2: top + h, stroke: "#60717e" }));
      svg.append(element("text", { x: left - 27, y: 155, "text-anchor": "middle", transform: `rotate(-90 ${left - 27} 155)`, class: "axis-label" }, `${s.depth.toFixed(2)} in`));
    }
    if (state.result) svg.append(element("text", { x: 240, y: 312, "text-anchor": "middle", class: "axis-label" }, `${s.bar_count}–${s.longitudinal_bar_size} · centerline cover ${s.centerline_cover.toFixed(2)} in`));
  }

  function renderError(message) { byId("capacity-chart").innerHTML = `<div class="error-message">${escapeHtml(message)}</div>`; }
  function escapeHtml(text) { const div = document.createElement("div"); div.textContent = text; return div.innerHTML; }

  function renderChart() {
    const host = byId("capacity-chart");
    const isThree = state.view === "three";
    const isResponse = state.view === "response";
    byId("three-zoom-control").hidden = !isThree;
    byId("response-load-control").hidden = !isResponse;
    host.classList.toggle("response-chart", isResponse);
    host.replaceChildren();
    byId("chart-tooltip").hidden = true;
    state.plotBounds = null;
    if (!state.result) return;
    const width = Math.max(420, host.clientWidth), height = host.clientHeight || 390;
    const svg = element("svg", { viewBox: `0 0 ${width} ${height}`, role: "img", "aria-label": "PMM capacity plot" });
    host.append(svg);
    try {
      if (state.view === "three") { renderThree(svg, width, height); return; }
      if (state.view === "response") { renderResponse(svg, width, height); return; }
      renderTwo(svg, width, height);
    } catch (error) {
      console.error("Chart render failed", error);
      svg.replaceChildren();
      svg.append(element("text", { x: 18, y: 28, class: "chart-title" }, "The chart could not be rendered."));
      svg.append(element("text", { x: 18, y: 54, class: "axis-label" }, error.message || String(error)));
      byId("run-state").textContent = `Render error: ${error.message || error}`;
    }
  }

  function extent(values) { return [Math.min(...values), Math.max(...values)]; }
  function scale(domain, range) { return value => range[0] + (value - domain[0]) * (range[1] - range[0]) / (domain[1] - domain[0]); }
  function linePath(points, x, y, close = false) { return points.map((p, i) => `${i ? "L" : "M"}${x(p).toFixed(2)},${y(p).toFixed(2)}`).join(" ") + (close ? " Z" : ""); }

  function niceStep(span, count = 5) {
    const raw = Math.max(Number.EPSILON, span / count), power = Math.pow(10, Math.floor(Math.log10(raw))), ratio = raw / power;
    const factor = ratio <= 1 ? 1 : ratio <= 2 ? 2 : ratio <= 5 ? 5 : 10;
    return factor * power;
  }

  function niceDomain(domain) {
    const step = niceStep(domain[1] - domain[0]);
    return [Math.floor(domain[0] / step) * step, Math.ceil(domain[1] / step) * step];
  }

  function ticks(domain) {
    const step = niceStep(domain[1] - domain[0]), values = [];
    let value = Math.ceil((domain[0] - step * 1e-9) / step) * step;
    while (value <= domain[1] + step * 1e-9 && values.length < 20) { values.push(value); value += step; }
    return values;
  }

  function renderTwo(svg, width, height) {
    const margin = { top: 64, right: 30, bottom: 50, left: 72 };
    let points, xTitle, yTitle, subtitle;
    if (state.view === "pmm") {
      const selected = state.result.demands[state.selected] || state.result.demands[0];
      points = state.result.contours.filter(p => selected && p.demand_label === selected.label).map(p => [p.mx_kip_ft, p.my_kip_ft]);
      if (points.length) points.push(points[0]);
      xTitle = "Mx (kip-ft)"; yTitle = "My (kip-ft)"; subtitle = selected ? `${selected.label} contour at Pu = ${selected.pu_kip.toFixed(1)} kip` : "No demand selected";
    } else {
      const curve = state.view === "pmx" ? state.result.pm_x : state.result.pm_y;
      points = curve.map(p => [p.moment_kip_ft, p.pu_kip]);
      xTitle = state.view === "pmx" ? "Mx (kip-ft)" : "My (kip-ft)"; yTitle = "Pu (kip)"; subtitle = "ACI factored interaction envelope";
    }
    if (!points.length) {
      const selected = state.result.demands[state.selected] || state.result.demands[0];
      const message = selected ? `No capacity contour is available at Pu = ${formatNumber(selected.pu_kip, 1)} kip. ${selected.note || "The axial demand is outside the analyzed range."}` : "No capacity contour is available for this axial load.";
      renderError(message);
      return;
    }
    const domainPoints = [...points];
    if (state.view === "pmm") {
      const demand = state.result.demands[state.selected] || state.result.demands[0];
      if (demand && finite(demand.mux_kip_ft) && finite(demand.muy_kip_ft)) domainPoints.push([demand.mux_kip_ft, demand.muy_kip_ft]);
    } else {
      const momentKey = state.view === "pmx" ? "mux_kip_ft" : "muy_kip_ft";
      state.result.demands.forEach(demand => {
        if (finite(demand[momentKey]) && finite(demand.pu_kip)) domainPoints.push([demand[momentKey], demand.pu_kip]);
      });
    }
    const xd = extent(domainPoints.map(p => p[0])), yd = extent(domainPoints.map(p => p[1]));
    const xp = Math.max(1, (xd[1] - xd[0]) * .08), yp = Math.max(1, (yd[1] - yd[0]) * .08);
    const baseXd = niceDomain([xd[0] - xp, xd[1] + xp]), baseYd = niceDomain([yd[0] - yp, yd[1] + yp]);
    const viewDomain = (domain, axis) => {
      const span = domain[1] - domain[0], center = (domain[0] + domain[1]) / 2 + state.pan[axis] * span;
      return [center - span / (2 * state.zoom), center + span / (2 * state.zoom)];
    };
    const viewXd = viewDomain(baseXd, 0), viewYd = viewDomain(baseYd, 1);
    const x = scale(viewXd, [margin.left, width - margin.right]);
    const y = scale(viewYd, [height - margin.bottom, margin.top]);
    state.plotBounds = { left: margin.left, right: width - margin.right, top: margin.top, bottom: height - margin.bottom };
    drawAxes(svg, width, height, margin, x, y, viewXd, viewYd, xTitle, yTitle);
    const clip = element("clipPath", { id: "plot-clip" });
    clip.append(element("rect", { x: margin.left, y: margin.top, width: width - margin.left - margin.right, height: height - margin.top - margin.bottom }));
    const defs = element("defs"); defs.append(clip); svg.append(defs);
    const plotLayer = element("g", { "clip-path": "url(#plot-clip)" }); svg.append(plotLayer);
    plotLayer.append(element("path", { d: linePath(points, p => x(p[0]), p => y(p[1])), class: "capacity-line" }));
    svg.append(element("text", { x: margin.left, y: 14, class: "chart-title" }, subtitle));
    if (state.view === "pmm") {
      const d = state.result.demands[state.selected] || state.result.demands[0];
      if (d) {
        const intersection = capacityIntersection(d), demandPoint = finite(d.mux_kip_ft) && finite(d.muy_kip_ft) ? [d.mux_kip_ft, d.muy_kip_ft] : null;
        const rayEnd = intersection && d.dcr <= 1 ? intersection : demandPoint || intersection;
        if (rayEnd) plotLayer.append(element("line", { x1: x(0), y1: y(0), x2: x(rayEnd[0]), y2: y(rayEnd[1]), class: "demand-line" }));
        if (intersection) {
          const marker = inspectable(element("circle", { cx: x(intersection[0]), cy: y(intersection[1]), r: 5.5, class: "capacity-intersection" }), demandDetails(d, "Capacity intersection"));
          plotLayer.append(marker);
        }
        const demandMarker = inspectable(element("circle", { cx: x(d.mux_kip_ft), cy: y(d.muy_kip_ft), r: 4, class: `demand-point ${plotLoadClass(d)}` }), demandDetails(d));
        plotLayer.append(demandMarker);
      }
      drawLegend(svg, margin.left, 35, ["capacity", "demand", "intersection"]);
    } else {
      const momentKey = state.view === "pmx" ? "mux_kip_ft" : "muy_kip_ft";
      state.result.demands.forEach((d, index) => {
        if (!finite(d[momentKey]) || !finite(d.pu_kip)) return;
        const selected = index === state.selected;
        const marker = inspectable(element("circle", { cx: x(d[momentKey]), cy: y(d.pu_kip), r: selected ? 4 : 3, class: `demand-point ${plotLoadClass(d)}` }), demandDetails(d));
        plotLayer.append(marker);
      });
      const pMax=Math.max(...points.map(p=>p[1])), pMin=Math.min(...points.map(p=>p[1]));
      [pMax,pMin].forEach((pValue,index) => {
        const atLimit=points.filter(p=>Math.abs(p[1]-pValue)<=Math.max(1,Math.abs(pValue)*.001));
        const moments=atLimit.map(p=>p[0]);
        if (!moments.length) return;
        plotLayer.append(element("line",{x1:x(Math.min(...moments)),y1:y(pValue),x2:x(Math.max(...moments)),y2:y(pValue),class:"capacity-limit"}));
        plotLayer.append(element("text",{x:x(Math.max(...moments))+6,y:y(pValue)+(index?14:-7),class:"tick-label"},index?"(Pmin)":"(Pmax)"));
      });
      drawLegend(svg, margin.left, 35, ["capacity", "demand", "limit"]);
    }
  }

  function drawLegend(svg, startX, y, kinds) {
    const labels = { capacity: "Factored capacity", demand: "Demand · red = outside", intersection: "Capacity intersection", limit: "Axial limits" };
    const viewWidth = Number(svg.getAttribute("viewBox").split(" ")[2]);
    let x = startX;
    kinds.forEach(kind => {
      const itemWidth = kind === "intersection" ? 145 : kind === "demand" ? 155 : 126;
      if (x + itemWidth > viewWidth - 12 && x > startX) { x = startX; y += 14; }
      if (kind === "capacity" || kind === "limit") {
        svg.append(element("line", { x1: x, y1: y - 3, x2: x + 22, y2: y - 3, class: kind === "limit" ? "capacity-limit" : "capacity-line" }));
      } else {
        svg.append(element("circle", { cx: x + 10, cy: y - 3, r: kind === "intersection" ? 4.5 : 3, class: kind === "intersection" ? "capacity-intersection" : "demand-point load-inside" }));
      }
      svg.append(element("text", { x: x + 28, y, class: "legend-label" }, labels[kind]));
      x += itemWidth;
    });
  }

  function tickLabel(value, span) {
    const digits = span < 10 ? 1 : 0;
    return Math.abs(value) < Math.pow(10, -digits) / 2 ? "0" : value.toLocaleString(undefined, { maximumFractionDigits: digits });
  }

  function drawAxes(svg, width, height, margin, x, y, xd, yd, xTitle, yTitle) {
    const xAxisY = yd[0] <= 0 && yd[1] >= 0 ? y(0) : height-margin.bottom;
    const yAxisX = xd[0] <= 0 && xd[1] >= 0 ? x(0) : margin.left;
    ticks(xd).forEach(xv => {
      svg.append(element("line", { x1: x(xv), y1: margin.top, x2: x(xv), y2: height-margin.bottom, class: "grid-line" }));
      svg.append(element("line", { x1: x(xv), y1: xAxisY-5, x2: x(xv), y2: xAxisY+5, class: "axis-tick" }));
      const xLabelY = Math.min(height - margin.bottom + 20, Math.max(margin.top + 12, xAxisY + 18));
      svg.append(element("text", { x: x(xv), y: xLabelY, "text-anchor": "middle", class: "tick-label" }, tickLabel(xv, xd[1]-xd[0])));
    });
    ticks(yd).forEach(yv => {
      svg.append(element("line", { x1: margin.left, y1: y(yv), x2: width-margin.right, y2: y(yv), class: "grid-line" }));
      svg.append(element("line", { x1: yAxisX-5, y1: y(yv), x2: yAxisX+5, y2: y(yv), class: "axis-tick" }));
      const yAnchorRight = yAxisX < width - margin.right - 55;
      if (Math.abs(yv) > (yd[1]-yd[0]) * 1e-9) svg.append(element("text", { x: yAxisX + (yAnchorRight ? 8 : -8), y: y(yv)+4, "text-anchor": yAnchorRight ? "start" : "end", class: "tick-label" }, tickLabel(yv, yd[1]-yd[0])));
    });
    svg.append(element("line", { x1: margin.left, y1: xAxisY, x2: width-margin.right, y2: xAxisY, class: "axis-line" }));
    svg.append(element("line", { x1: yAxisX, y1: margin.top, x2: yAxisX, y2: height-margin.bottom, class: "axis-line" }));
    svg.append(element("text", { x: (margin.left + width - margin.right) / 2, y: height-7, "text-anchor": "middle", class: "axis-label" }, xTitle));
    svg.append(element("text", { x: 16, y: height / 2, class: "axis-label", transform: `rotate(-90 16 ${height / 2})`, "text-anchor": "middle" }, yTitle));
  }

  function responseCard(svg, x, y, width, height, title, subtitle = "") {
    svg.append(element("rect", { x, y, width, height, rx: 4, class: "response-card" }));
    svg.append(element("text", { x: x + 10, y: y + 18, class: "chart-title" }, title));
    if (subtitle) svg.append(element("text", { x: x + width - 10, y: y + 18, "text-anchor": "end", class: "response-note" }, subtitle));
    return { left: x + 12, right: x + width - 12, top: y + 31, bottom: y + height - 12 };
  }

  function clippedLineToPolygon(center, direction, polygon) {
    const intersections = [], epsilon = 1e-9;
    const cross = (first, second) => first.x * second.y - first.y * second.x;
    for (let index = 0; index < polygon.length; index++) {
      const start = polygon[index], end = polygon[(index + 1) % polygon.length];
      const edge = { x: end.x_in - start.x_in, y: end.y_in - start.y_in };
      const relative = { x: start.x_in - center.x, y: start.y_in - center.y };
      const denominator = cross(direction, edge);
      if (Math.abs(denominator) <= epsilon) continue;
      const lineParameter = cross(relative, edge) / denominator;
      const edgeParameter = cross(relative, direction) / denominator;
      if (edgeParameter < -epsilon || edgeParameter > 1 + epsilon) continue;
      const point = { x: center.x + lineParameter * direction.x, y: center.y + lineParameter * direction.y, lineParameter };
      if (!intersections.some(item => Math.hypot(item.x - point.x, item.y - point.y) < epsilon)) intersections.push(point);
    }
    if (intersections.length < 2) return null;
    intersections.sort((a, b) => a.lineParameter - b.lineParameter);
    return [intersections[0], intersections[intersections.length - 1]];
  }

  function renderResponse(svg, width, height) {
    const response = state.result.response_diagrams && state.result.response_diagrams[state.selected];
    const demand = state.result.demands[state.selected];
    if (!response || !response.available) {
      svg.append(element("text", { x: 18, y: 25, class: "chart-title" }, demand ? `${demand.label} · strain and stress response` : "Strain and stress response"));
      svg.append(element("text", { x: 18, y: 52, class: "axis-label" }, response ? response.note : "No response diagram was returned."));
      return;
    }
    svg.append(element("text", { x: 12, y: 17, class: "chart-title" }, `${response.load_label} · controlling section response · ${response.classification}`));
    svg.append(element("text", { x: 12, y: 33, class: "response-note" }, response.note));
    const gap=10, cardWidth=(width-gap*3)/2, cardHeight=(height-52-gap*3)/2;
    const firstX=gap, secondX=gap*2+cardWidth, firstY=48, secondY=firstY+cardHeight+gap;

    const sectionBox=responseCard(svg,firstX,firstY,cardWidth,cardHeight,"Section strain plane",`θ = ${response.neutral_axis_angle_deg.toFixed(1)}°`);
    const outlines=response.section_outlines.flat(), xBounds=extent(outlines.map(point=>point.x_in)), yBounds=extent(outlines.map(point=>point.y_in));
    const sectionScale=Math.min((sectionBox.right-sectionBox.left)/(xBounds[1]-xBounds[0]),(sectionBox.bottom-sectionBox.top)/(yBounds[1]-yBounds[0]))*.82;
    const sectionCenter=[(sectionBox.left+sectionBox.right)/2,(sectionBox.top+sectionBox.bottom)/2];
    const sectionX=value=>sectionCenter[0]+(value-(xBounds[0]+xBounds[1])/2)*sectionScale;
    const sectionY=value=>sectionCenter[1]-(value-(yBounds[0]+yBounds[1])/2)*sectionScale;
    response.block_polygons.forEach(polygon=>svg.append(element("path",{d:linePath(polygon,p=>sectionX(p.x_in),p=>sectionY(p.y_in),true),class:"response-block"})));
    response.section_outlines.forEach(polygon=>svg.append(element("path",{d:linePath(polygon,p=>sectionX(p.x_in),p=>sectionY(p.y_in),true),class:"response-outline"})));
    response.bars.forEach(bar=>{
      const marker=inspectable(element("circle",{cx:sectionX(bar.x_in),cy:sectionY(bar.y_in),r:3.2,fill:bar.stress_ksi>=0?"#3979a6":"#d67a31",class:"response-bar"}),`${bar.label}\nStrain ${bar.strain.toFixed(6)}\nStress ${bar.stress_ksi.toFixed(2)} ksi`);
      svg.append(marker);
    });
    const normal=response.normal, tangent={x:-normal.y,y:normal.x};
    if (response.neutral_axis_offset_in >= response.projection_min_in && response.neutral_axis_offset_in <= response.projection_max_in) {
      const naCenter={x:normal.x*response.neutral_axis_offset_in,y:normal.y*response.neutral_axis_offset_in};
      const neutralLine=clippedLineToPolygon(naCenter,tangent,response.section_outlines[0]);
      if (neutralLine) svg.append(element("line",{x1:sectionX(neutralLine[0].x),y1:sectionY(neutralLine[0].y),x2:sectionX(neutralLine[1].x),y2:sectionY(neutralLine[1].y),class:"neutral-axis"}));
    }
    svg.append(element("text",{x:sectionBox.left+3,y:sectionBox.bottom-2,class:"response-note"},"blue = Whitney compression block · red dash = neutral axis"));

    const strainBox=responseCard(svg,secondX,firstY,cardWidth,cardHeight,"Section strain distribution","compression +");
    const strainValues=[response.minimum_section_strain,response.maximum_concrete_strain,0,...response.bars.map(bar=>bar.strain)];
    let strainDomain=extent(strainValues), strainPad=Math.max(.00025,(strainDomain[1]-strainDomain[0])*.12);
    strainDomain=[strainDomain[0]-strainPad,strainDomain[1]+strainPad];
    const strainX=scale(strainDomain,[strainBox.left+28,strainBox.right-7]), projectionY=scale([response.projection_min_in,response.projection_max_in],[strainBox.bottom-18,strainBox.top+7]);
    svg.append(element("line",{x1:strainX(0),y1:strainBox.top,x2:strainX(0),y2:strainBox.bottom-14,class:"axis-line"}));
    if (response.neutral_axis_offset_in >= response.projection_min_in && response.neutral_axis_offset_in <= response.projection_max_in) svg.append(element("line",{x1:strainBox.left+22,y1:projectionY(response.neutral_axis_offset_in),x2:strainBox.right,y2:projectionY(response.neutral_axis_offset_in),class:"neutral-axis"}));
    svg.append(element("path",{d:linePath([[response.minimum_section_strain,response.projection_min_in],[response.maximum_concrete_strain,response.projection_max_in]],p=>strainX(p[0]),p=>projectionY(p[1])),class:"strain-line"}));
    response.bars.forEach(bar=>svg.append(inspectable(element("circle",{cx:strainX(bar.strain),cy:projectionY(bar.projection_in),r:2.5,fill:"#111"}),`${bar.label}\nε = ${bar.strain.toFixed(6)}`)));
    svg.append(element("text",{x:strainX(response.maximum_concrete_strain)-3,y:projectionY(response.projection_max_in)+11,"text-anchor":"end",class:"response-note"},`εcu = ${response.maximum_concrete_strain.toFixed(4)}`));
    svg.append(element("text",{x:(strainBox.left+strainBox.right)/2,y:strainBox.bottom,"text-anchor":"middle",class:"axis-label"},"strain, ε (in/in)"));

    const blockBox=responseCard(svg,firstX,secondY,cardWidth,cardHeight,"ACI equivalent stress block",`β1 = ${response.beta1.toFixed(3)}`);
    const blockY=scale([response.projection_min_in,response.projection_max_in],[blockBox.bottom-19,blockBox.top+7]), stressZero=blockBox.left+35, stressMax=blockBox.right-12;
    svg.append(element("line",{x1:stressZero,y1:blockBox.top,x2:stressZero,y2:blockBox.bottom-16,class:"axis-line"}));
    const activeBottom=Math.max(response.projection_min_in,response.block_offset_in), blockTop=blockY(response.projection_max_in), blockBottom=blockY(activeBottom);
    svg.append(element("rect",{x:stressZero,y:blockTop,width:stressMax-stressZero,height:Math.max(1,blockBottom-blockTop),class:"response-block"}));
    const visibleBlockOffset=Math.max(response.projection_min_in,Math.min(response.projection_max_in,response.block_offset_in));
    svg.append(element("line",{x1:blockBox.left+20,y1:blockY(visibleBlockOffset),x2:blockBox.right,y2:blockY(visibleBlockOffset),class:"capacity-limit"}));
    svg.append(element("text",{x:stressMax-3,y:blockTop+13,"text-anchor":"end",class:"axis-label"},`0.85 f′c = ${response.block_stress_ksi.toFixed(2)} ksi`));
    svg.append(element("text",{x:blockBox.left+8,y:blockBox.bottom,class:"response-note"},`a = β1c = ${response.block_depth_in.toFixed(3)} in · design idealization, not a constitutive curve`));

    const steelBox=responseCard(svg,secondX,secondY,cardWidth,cardHeight,"Steel stress–strain",`fy = ${response.steel.fy_ksi.toFixed(0)} ksi`);
    const yieldStrain=response.steel.yield_strain, allSteelStrains=[...response.bars.map(bar=>bar.strain),-2.5*yieldStrain,2.5*yieldStrain];
    let steelStrainDomain=extent(allSteelStrains), steelSpan=Math.max(steelStrainDomain[1]-steelStrainDomain[0],yieldStrain*5);
    steelStrainDomain=[Math.min(steelStrainDomain[0],-steelSpan/2),Math.max(steelStrainDomain[1],steelSpan/2)];
    const steelX=scale(steelStrainDomain,[steelBox.left+30,steelBox.right-8]), steelY=scale([-1.15*response.steel.fy_ksi,1.15*response.steel.fy_ksi],[steelBox.bottom-20,steelBox.top+7]);
    svg.append(element("line",{x1:steelX(0),y1:steelBox.top,x2:steelX(0),y2:steelBox.bottom-15,class:"axis-line"}));
    svg.append(element("line",{x1:steelBox.left+25,y1:steelY(0),x2:steelBox.right,y2:steelY(0),class:"axis-line"}));
    const steelStress=strain=>Math.max(-response.steel.fy_ksi,Math.min(response.steel.fy_ksi,response.steel.elastic_modulus_ksi*strain));
    const steelCurve=[steelStrainDomain[0],-yieldStrain,0,yieldStrain,steelStrainDomain[1]].sort((a,b)=>a-b).map(strain=>[strain,steelStress(strain)]);
    svg.append(element("path",{d:linePath(steelCurve,p=>steelX(p[0]),p=>steelY(p[1])),class:"steel-curve"}));
    response.bars.forEach(bar=>svg.append(inspectable(element("circle",{cx:steelX(bar.strain),cy:steelY(bar.stress_ksi),r:2.4,fill:bar.stress_ksi>=0?"#3979a6":"#d67a31",class:"response-bar"}),`${bar.label}\nε = ${bar.strain.toFixed(6)}\nfs = ${bar.stress_ksi.toFixed(2)} ksi`)));
    svg.append(element("text",{x:(steelBox.left+steelBox.right)/2,y:steelBox.bottom,"text-anchor":"middle",class:"axis-label"},"steel strain, εs (in/in)"));
  }

  function renderThree(svg, width, height) {
    const layers = state.result.onion_contours;
    if (!layers.length) { renderError("No 3D contour layers were returned."); return; }
    const rings = layers.map(layer => ({ p: layer.pu_kip, points: layer.points.map(point => [point.mx_kip_ft,point.my_kip_ft,layer.pu_kip]) }));
    const axes=[[[-900,0,-650],[950,0,-650],"Mx","#d32727","arrow-x"],[[0,-600,-650],[0,600,-650],"My","#14a23c","arrow-y"],[[0,0,-650],[0,0,1500],"Pu","#174ed4","arrow-z"]];
    const rotate = (point) => {
      const [mx,my,p]=point, x1=mx*Math.cos(state.yaw)-my*Math.sin(state.yaw), y1=mx*Math.sin(state.yaw)+my*Math.cos(state.yaw);
      return [x1, -(y1*Math.cos(state.pitch)-p*Math.sin(state.pitch))];
    };
    const extentPoints = [...rings.flatMap(ring => ring.points), ...axes.flatMap(axis => [axis[0], axis[1]])].map(rotate);
    const xExtent=extent(extentPoints.map(point=>point[0])), yExtent=extent(extentPoints.map(point=>point[1]));
    const inset={left:38,right:72,top:38,bottom:52}, spanX=Math.max(1,xExtent[1]-xExtent[0]), spanY=Math.max(1,yExtent[1]-yExtent[0]);
    const fitFactor=Math.min((width-inset.left-inset.right)/spanX,(height-inset.top-inset.bottom)/spanY), factor=fitFactor*state.threeZoom;
    const center=[inset.left+(width-inset.left-inset.right)/2-factor*(xExtent[0]+xExtent[1])/2,inset.top+(height-inset.top-inset.bottom)/2-factor*(yExtent[0]+yExtent[1])/2];
    const project = (point) => { const projected=rotate(point); return [center[0]+projected[0]*factor,center[1]+projected[1]*factor]; };
    const count = Math.min(...rings.map(r=>r.points.length));
    const defs = element("defs");
    [["arrow-x","#d32727"],["arrow-y","#14a23c"],["arrow-z","#174ed4"]].forEach(([id,color]) => {
      const marker=element("marker",{id,viewBox:"0 0 10 10",refX:9,refY:5,markerWidth:6,markerHeight:6,orient:"auto-start-reverse"});
      marker.append(element("path",{d:"M 0 0 L 10 5 L 0 10 z",fill:color})); defs.append(marker);
    });
    svg.append(defs);
    for (let layer=0;layer<rings.length-1;layer++) {
      for (let i=0;i<count;i++) {
        const next=(i+1)%count;
        const face=[rings[layer].points[i],rings[layer].points[next],rings[layer+1].points[next],rings[layer+1].points[i]];
        svg.append(element("path",{d:linePath(face,p=>project(p)[0],p=>project(p)[1],true),fill:"#9fb6ce",opacity:.17,stroke:"none"}));
      }
    }
    for (let i=0;i<count;i+=Math.max(1,Math.floor(count/12))) svg.append(element("path", { d: linePath(rings.map(r=>r.points[i]), p=>project(p)[0], p=>project(p)[1]), class: "mesh-line" }));
    rings.forEach((ring,index) => {
      svg.append(element("path", { d: linePath(ring.points, p=>project(p)[0], p=>project(p)[1], true), class: "onion-line", opacity: .5 + index*.08 }));
      if (index % 3 === 0 || index === rings.length-1) { const label=project(ring.points[Math.floor(count/4)]); svg.append(element("text", { x: label[0]+5, y: label[1], class: "layer-label" }, `P=${Math.round(ring.p)}`)); }
    });
    const demand=state.result.demands[state.selected] || state.result.demands[0];
    if (demand) {
      const selectedRing=state.result.contours.filter(point=>point.demand_label===demand.label).map(point=>[point.mx_kip_ft,point.my_kip_ft,demand.pu_kip]);
      if (selectedRing.length) svg.append(element("path",{d:linePath(selectedRing,p=>project(p)[0],p=>project(p)[1],true),fill:"#ee933f",opacity:.62,stroke:"#9a4d12","stroke-width":1.6}));
      const load=project([demand.mux_kip_ft,demand.muy_kip_ft,demand.pu_kip]);
      const marker = inspectable(element("circle",{cx:load[0],cy:load[1],r:4,class:`demand-point ${plotLoadClass(demand)}`}), demandDetails(demand));
      svg.append(marker);
    }
    axes.forEach(axis=>{ const a=project(axis[0]),b=project(axis[1]); svg.append(element("line",{x1:a[0],y1:a[1],x2:b[0],y2:b[1],stroke:axis[3],"stroke-width":2.2,"marker-end":`url(#${axis[4]})`})); svg.append(element("text",{x:b[0]+7,y:b[1]-6,fill:axis[3],"font-size":12},axis[2])); });
    svg.append(element("text", { x: 15, y: 20, class: "chart-title" }, "Factored PMM boundary · orange = selected Pu slice"));
    const handle=element("g",{transform:`translate(${width-48} 45)`,role:"img","aria-label":"Drag plot to rotate"});
    handle.append(element("circle",{cx:0,cy:0,r:25,fill:"#f8fafb",stroke:"#738391","stroke-width":1.5}));
    handle.append(element("path",{d:"M-15 0H15M0-15V15M-15 0l5-4m-5 4l5 4m25-4l-5-4m5 4l-5 4M0-15l-4 5m4-5l4 5M0 15l-4-5m4 5l4-5",fill:"none",stroke:"#3e4e5a","stroke-width":1.4}));
    handle.append(element("text",{x:0,y:40,"text-anchor":"middle",class:"layer-label"},"drag to spin")); svg.append(handle);
    svg.style.cursor = state.drag ? "grabbing" : "grab";
  }

  const exportedChartCss = `
    text { font-family: "Futura Light", Futura, "Futura PT", "Century Gothic", sans-serif; font-weight:300; }
    .chart-title{font-family:"Futura Heavy",Futura,"Futura PT","Century Gothic",sans-serif;font-size:10.5pt;font-weight:800}
    .axis-label,.tick-label,.layer-label{fill:#31404d;font-size:12px}
    .legend-label{fill:#4b5b67;font-size:11px}
    .axis-line{stroke:#57636d;stroke-width:1.15}.axis-tick{stroke:#69757e}.grid-line{stroke:#dfe6ea}
    .capacity-line{stroke:#62a8c8;stroke-width:1.9;fill:none}.capacity-limit{stroke:#62a8c8;stroke-width:1.25;stroke-dasharray:8 7;fill:none}
    .demand-line{stroke:#c16a25;stroke-width:1.5}.demand-point{stroke:none}.load-inside{fill:#111}.load-outside{fill:#c74335}
    .demand-safe{fill:#25836f}.demand-watch{fill:#db8a22}.demand-fail,.demand-unknown{fill:#c74335}.capacity-intersection{fill:#fff;stroke:#c16a25;stroke-width:2.2}
    .onion-line{stroke:#496782;stroke-width:1.35;fill:none}.mesh-line{stroke:#71879b;stroke-width:.85;fill:none}
    .response-card{fill:#fbfcfd;stroke:#d7e0e5}.response-outline{fill:none;stroke:#26343e;stroke-width:1.5}.response-block{fill:#bcd9e4;stroke:#62a8c8}.neutral-axis{stroke:#c74335;stroke-width:1.5;stroke-dasharray:6 4}.strain-line{fill:none;stroke:#2c756a;stroke-width:2}.steel-curve{fill:none;stroke:#334b61;stroke-width:2}.response-bar{stroke:#fff;stroke-width:.8}.response-note{fill:#586975;font-size:10px}
  `;

  function exportedSvg() {
    const source = byId("capacity-chart").querySelector("svg");
    if (!source) return null;
    const clone = source.cloneNode(true);
    const viewBox = clone.getAttribute("viewBox").split(" ").map(Number);
    clone.setAttribute("xmlns", svgNS);
    clone.setAttribute("width", viewBox[2]);
    clone.setAttribute("height", viewBox[3]);
    const style = element("style", {}, exportedChartCss);
    clone.insertBefore(style, clone.firstChild);
    const background = element("rect", { x: 0, y: 0, width: "100%", height: "100%", fill: "#fff" });
    clone.insertBefore(background, style.nextSibling);
    return { markup: new XMLSerializer().serializeToString(clone), width: viewBox[2], height: viewBox[3] };
  }

  function exportName(extension) {
    const demand = state.result && state.result.demands[state.selected];
    const suffix = state.view === "pmm" && demand ? `-${demand.label}` : "";
    return `pmm-${state.view}${suffix}.${extension}`.replace(/[^a-z0-9._-]+/gi, "-").toLowerCase();
  }

  function download(blob, filename) {
    const link = document.createElement("a"), url = URL.createObjectURL(blob);
    link.href = url; link.download = filename; document.body.append(link); link.click(); link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  function exportPng() {
    const chart = exportedSvg();
    if (!chart) return;
    const blob = new Blob([chart.markup], { type: "image/svg+xml;charset=utf-8" });
    const url = URL.createObjectURL(blob), image = new Image();
    image.onload = () => {
      const ratio = 2, canvas = document.createElement("canvas"), context = canvas.getContext("2d");
      canvas.width = chart.width * ratio; canvas.height = chart.height * ratio;
      context.scale(ratio, ratio); context.drawImage(image, 0, 0, chart.width, chart.height);
      URL.revokeObjectURL(url);
      canvas.toBlob(result => { if (result) download(result, exportName("png")); }, "image/png");
    };
    image.onerror = () => { URL.revokeObjectURL(url); byId("run-state").textContent = "Could not export the chart as PNG."; };
    image.src = url;
  }

  async function downloadPdfReport() {
    const status=byId("run-state"), reportPayload=payload(), selected=demands()[state.selected];
    reportPayload.analysis.include_onion=false;
    reportPayload.report={selected_load_label:selected ? selected.label : null};
    status.textContent="Building PDF report…";
    byId("print-calculation").disabled=true;
    try {
      const response=await fetch("/api/v1/report",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(reportPayload)});
      if (!response.ok) {
        let message=`HTTP ${response.status}`;
        try { const body=await response.json(); message=body.error||message; } catch (_) { /* PDF endpoint returned non-JSON error text. */ }
        throw new Error(message);
      }
      download(await response.blob(),`pmm-report-${selected ? selected.label : "section"}.pdf`.replace(/[^a-z0-9._-]+/gi,"-").toLowerCase());
      status.textContent="PDF report complete";
    } catch (error) {
      status.textContent=`PDF error: ${error.message}`;
    } finally {
      byId("print-calculation").disabled=false;
    }
  }

  function showTooltip(target, event) {
    const tooltip = byId("chart-tooltip"), shell = document.querySelector(".chart-shell");
    if (!target || !target.dataset.tooltip) { tooltip.hidden = true; return; }
    tooltip.textContent = target.dataset.tooltip; tooltip.hidden = false;
    const shellBox = shell.getBoundingClientRect(), targetBox = target.getBoundingClientRect();
    let left = event ? event.clientX - shellBox.left + 12 : targetBox.right - shellBox.left + 8;
    let top = event ? event.clientY - shellBox.top + 12 : targetBox.top - shellBox.top + targetBox.height + 8;
    left = Math.max(6, Math.min(left, shellBox.width - tooltip.offsetWidth - 6));
    top = Math.max(6, Math.min(top, shellBox.height - tooltip.offsetHeight - 6));
    tooltip.style.left = `${left}px`; tooltip.style.top = `${top}px`;
  }

  function resetView() {
    state.zoom = 1; state.threeZoom = 1; state.pan = [0, 0]; state.yaw = initialView.yaw; state.pitch = initialView.pitch;
    setThreeZoom(1);
    renderChart();
  }

  function setThreeZoom(value) {
    state.threeZoom=Math.max(.6,Math.min(2.5,value));
    byId("three-zoom").value=state.threeZoom;
    byId("three-zoom-value").value=`${Math.round(state.threeZoom*100)}%`;
  }

  byId("run-analysis").addEventListener("click", analyze);
  byId("print-calculation").addEventListener("click", downloadPdfReport);
  byId("three-zoom").addEventListener("input", event => { setThreeZoom(Number(event.target.value)); renderChart(); });
  byId("response-load").addEventListener("change", event => {
    state.selected=Number(event.target.value); updateResults(); renderChart();
  });
  byId("reset-view").addEventListener("click", resetView);
  byId("export-png").addEventListener("click", exportPng);
  byId("add-demand").addEventListener("click", () => byId("demand-table").querySelector("tbody").append(byId("demand-row-template").content.cloneNode(true)));
  byId("demand-table").addEventListener("click", event => {
    const row = event.target.closest("tr"); if (!row) return;
    const rows=[...row.parentElement.children]; state.selected=rows.indexOf(row);
    if (event.target.classList.contains("remove")) { row.remove(); state.selected=0; }
    if (state.result) { updateResults(); renderChart(); }
  });
  document.querySelectorAll("[data-settings-tab]").forEach(button => button.addEventListener("click", () => {
    const selected = button.dataset.settingsTab;
    document.querySelectorAll("[data-settings-tab]").forEach(item => item.setAttribute("aria-selected", String(item === button)));
    byId("basic-settings").hidden = selected !== "basic";
    byId("advanced-settings").hidden = selected !== "advanced";
  }));
  byId("integration-method").addEventListener("change", () => {
    const fiber = byId("integration-method").value === "fiber";
    byId("fiber-divisions").disabled = !fiber;
    byId("analysis-note").textContent = fiber
      ? "Fiber mode discretizes concrete into midpoint cells while keeping reinforcing bars discrete. Runtime grows quickly with mesh density and rotation refinement."
      : "Shape integration is exact for the Whitney block and is the recommended production setting.";
  });
  byId("section-shape").addEventListener("change", () => {
    const circular = byId("section-shape").value === "circular";
    byId("width-field").hidden = circular;
    byId("depth-field").hidden = circular;
    byId("diameter-field").hidden = !circular;
    analyze();
  });
  document.querySelectorAll("[data-view]").forEach(button => button.addEventListener("click", async () => {
    state.view=button.dataset.view;
    state.zoom=1; state.pan=[0,0];
    document.querySelectorAll("[data-view]").forEach(item=>item.setAttribute("aria-pressed",String(item===button)));
    const responseDiagrams = state.result && state.result.response_diagrams;
    const responseDataMissing = state.view === "response" && state.result && (
      !Array.isArray(responseDiagrams) || responseDiagrams.length !== state.result.demands.length
    );
    if (responseDataMissing) await analyze();
    else if (state.view === "three" && state.result && !state.result.onion_contours.length) await analyze();
    else renderChart();
  }));
  byId("capacity-chart").addEventListener("pointerdown", event => {
    const target = event.target.closest && event.target.closest("[data-tooltip]");
    if (target) { showTooltip(target, event); return; }
    state.drag={ mode: state.view === "three" ? "rotate" : "pan", x: event.clientX, y: event.clientY };
    byId("capacity-chart").setPointerCapture(event.pointerId);
  });
  byId("capacity-chart").addEventListener("pointermove", event => {
    const target = event.target.closest && event.target.closest("[data-tooltip]");
    if (target && !state.drag) showTooltip(target, event);
    else if (!state.drag) byId("chart-tooltip").hidden = true;
    if (!state.drag) return;
    const dx=event.clientX-state.drag.x, dy=event.clientY-state.drag.y;
    if (state.drag.mode === "rotate") {
      state.yaw+=dx*.01; state.pitch=Math.max(-1.2,Math.min(1.2,state.pitch-dy*.01));
    } else if (state.plotBounds) {
      const plotWidth=state.plotBounds.right-state.plotBounds.left, plotHeight=state.plotBounds.bottom-state.plotBounds.top;
      state.pan[0]-=dx/(plotWidth*state.zoom); state.pan[1]+=dy/(plotHeight*state.zoom);
    }
    state.drag.x=event.clientX; state.drag.y=event.clientY; renderChart();
  });
  byId("capacity-chart").addEventListener("pointerup", event => {
    state.drag=null;
    if (byId("capacity-chart").hasPointerCapture(event.pointerId)) byId("capacity-chart").releasePointerCapture(event.pointerId);
    renderChart();
  });
  byId("capacity-chart").addEventListener("pointercancel", () => { state.drag=null; renderChart(); });
  byId("capacity-chart").addEventListener("pointerleave", () => { if (!state.drag) byId("chart-tooltip").hidden = true; });
  byId("capacity-chart").addEventListener("focusin", event => showTooltip(event.target.closest && event.target.closest("[data-tooltip]")));
  byId("capacity-chart").addEventListener("focusout", () => { byId("chart-tooltip").hidden = true; });
  byId("capacity-chart").addEventListener("wheel", event => {
    if (state.view === "three") {
      event.preventDefault();
      setThreeZoom(state.threeZoom*(event.deltaY < 0 ? 1.1 : 1/1.1));
      renderChart();
      return;
    }
    if (!state.plotBounds) return;
    event.preventDefault();
    state.zoom=Math.max(.65,Math.min(8,state.zoom*(event.deltaY < 0 ? 1.18 : 1/1.18)));
    renderChart();
  }, { passive: false });
  window.addEventListener("resize", () => { renderSection(); renderChart(); });
  renderSection();
  analyze();
})();
