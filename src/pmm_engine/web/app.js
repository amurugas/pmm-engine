(() => {
  const state = { result: null, view: "pmm", selected: 1, yaw: -0.72, pitch: 0.52, drag: null };
  const byId = (id) => document.getElementById(id);
  const svgNS = "http://www.w3.org/2000/svg";

  function element(name, attributes = {}, text = "") {
    const node = document.createElementNS(svgNS, name);
    Object.entries(attributes).forEach(([key, value]) => node.setAttribute(key, value));
    if (text) node.textContent = text;
    return node;
  }

  function number(id) { return Number(byId(id).value); }

  function demands() {
    return [...document.querySelectorAll("#demand-table tbody tr")].map((row, index) => {
      const inputs = row.querySelectorAll("input");
      return { label: inputs[0].value || `LC-${index + 1}`, pu_kip: Number(inputs[1].value), mux_kip_ft: Number(inputs[2].value), muy_kip_ft: Number(inputs[3].value) };
    });
  }

  function payload() {
    return {
      schema_version: 1,
      section: { width_in: number("width"), depth_in: number("depth"), fc_ksi: number("fc"), fy_ksi: number("fy"), clear_cover_in: number("cover"), tie_bar_size: byId("tie-size").value, longitudinal_bar_size: byId("bar-size").value, maximum_spacing_in: number("spacing") },
      analysis: { angle_step_deg: number("dcr-step"), include_onion: true, onion_angle_step_deg: 10, onion_layer_count: 13 },
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
      status.textContent = `${body.cached ? "Cached" : "Complete"} · ${serverMs} ms server / ${elapsed} ms total`;
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
      cells[1].className = `result ${result && result.status === "OK" ? "status-ok" : "status-ng"}`;
      row.classList.toggle("selected-row", index === state.selected);
    });
    const s = state.result.section;
    byId("section-summary").innerHTML = `<div class="metric"><span>Bars</span><strong>${s.bar_count} ${s.longitudinal_bar_size}</strong></div><div class="metric"><span>Steel area</span><strong>${s.steel_area_in2.toFixed(2)} in²</strong></div><div class="metric"><span>ρg</span><strong>${(100 * s.reinforcement_ratio).toFixed(3)}%</strong></div>`;
    byId("project-title").textContent = `${s.width} × ${s.depth} in · ACI 318-19`;
    byId("calculation-text").textContent = state.result.calculation_report.map(row => row[0]).join("\n");
  }

  function renderSection() {
    const svg = byId("section-svg");
    svg.replaceChildren();
    svg.setAttribute("viewBox", "0 0 480 330");
    const s = state.result ? state.result.section : { width: number("width"), depth: number("depth") };
    const bars = state.result ? state.result.bars : [];
    const scale = Math.min(330 / s.width, 250 / s.depth);
    const w = s.width * scale, h = s.depth * scale, left = 240 - w / 2, top = 155 - h / 2;
    svg.append(element("rect", { x: left, y: top, width: w, height: h, rx: 2, fill: "#edf0ec", stroke: "#27333c", "stroke-width": 2 }));
    bars.forEach(bar => svg.append(element("circle", { cx: 240 + bar.x_in * scale, cy: 155 - bar.y_in * scale, r: Math.max(4, Math.sqrt(bar.area_in2 / Math.PI) * scale), fill: "#d67a31", stroke: "#4c2d18", "stroke-width": 1 })));
    svg.append(element("line", { x1: left, y1: top - 18, x2: left + w, y2: top - 18, stroke: "#60717e" }));
    svg.append(element("text", { x: 240, y: top - 24, "text-anchor": "middle", class: "axis-label" }, `${s.width.toFixed(2)} in`));
    svg.append(element("line", { x1: left - 18, y1: top, x2: left - 18, y2: top + h, stroke: "#60717e" }));
    svg.append(element("text", { x: left - 27, y: 155, "text-anchor": "middle", transform: `rotate(-90 ${left - 27} 155)`, class: "axis-label" }, `${s.depth.toFixed(2)} in`));
    if (state.result) svg.append(element("text", { x: 240, y: 312, "text-anchor": "middle", class: "axis-label" }, `${s.bar_count}–${s.longitudinal_bar_size} · centerline cover ${s.centerline_cover.toFixed(2)} in`));
  }

  function renderError(message) { byId("capacity-chart").innerHTML = `<div class="error-message">${escapeHtml(message)}</div>`; }
  function escapeHtml(text) { const div = document.createElement("div"); div.textContent = text; return div.innerHTML; }

  function renderChart() {
    const host = byId("capacity-chart");
    host.replaceChildren();
    if (!state.result) return;
    const width = Math.max(420, host.clientWidth), height = host.clientHeight || 390;
    const svg = element("svg", { viewBox: `0 0 ${width} ${height}`, role: "img", "aria-label": "PMM capacity plot" });
    host.append(svg);
    if (state.view === "three") { renderThree(svg, width, height); return; }
    renderTwo(svg, width, height);
  }

  function extent(values) { return [Math.min(...values), Math.max(...values)]; }
  function scale(domain, range) { return value => range[0] + (value - domain[0]) * (range[1] - range[0]) / (domain[1] - domain[0]); }
  function linePath(points, x, y, close = false) { return points.map((p, i) => `${i ? "L" : "M"}${x(p).toFixed(2)},${y(p).toFixed(2)}`).join(" ") + (close ? " Z" : ""); }

  function renderTwo(svg, width, height) {
    const margin = { top: 26, right: 24, bottom: 48, left: 64 };
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
    if (!points.length) { renderError("No capacity contour is available for this axial load."); return; }
    const xd = extent(points.map(p => p[0])), yd = extent(points.map(p => p[1]));
    const xp = Math.max(1, (xd[1] - xd[0]) * .08), yp = Math.max(1, (yd[1] - yd[0]) * .08);
    const x = scale([xd[0] - xp, xd[1] + xp], [margin.left, width - margin.right]);
    const y = scale([yd[0] - yp, yd[1] + yp], [height - margin.bottom, margin.top]);
    drawAxes(svg, width, height, margin, x, y, [xd[0]-xp,xd[1]+xp], [yd[0]-yp,yd[1]+yp], xTitle, yTitle);
    svg.append(element("path", { d: linePath(points, p => x(p[0]), p => y(p[1])), class: "capacity-line" }));
    svg.append(element("text", { x: margin.left + 7, y: margin.top + 14, class: "chart-title" }, subtitle));
    if (state.view === "pmm") {
      const d = state.result.demands[state.selected] || state.result.demands[0];
      if (d) {
        svg.append(element("line", { x1: x(0), y1: y(0), x2: x(d.mux_kip_ft), y2: y(d.muy_kip_ft), class: "demand-line" }));
        svg.append(element("circle", { cx: x(d.mux_kip_ft), cy: y(d.muy_kip_ft), r: 5, class: "demand-point" }));
        const dcrLabel = Number.isFinite(d.dcr) ? d.dcr.toFixed(3) : "N/A";
        svg.append(element("text", { x: x(d.mux_kip_ft) + 8, y: y(d.muy_kip_ft) - 8, class: "chart-title" }, `${d.label} · DCR ${dcrLabel}`));
      }
    } else {
      const momentKey = state.view === "pmx" ? "mux_kip_ft" : "muy_kip_ft";
      state.result.demands.forEach(d => {
        svg.append(element("circle", { cx: x(d[momentKey]), cy: y(d.pu_kip), r: 4.5, class: "demand-point" }));
        svg.append(element("text", { x: x(d[momentKey]) + 7, y: y(d.pu_kip) - 7, class: "tick-label" }, d.label));
      });
      const pMax=Math.max(...points.map(p=>p[1])), pMin=Math.min(...points.map(p=>p[1]));
      [pMax,pMin].forEach((pValue,index) => {
        const atLimit=points.filter(p=>Math.abs(p[1]-pValue)<=Math.max(1,Math.abs(pValue)*.001));
        const moments=atLimit.map(p=>p[0]);
        if (!moments.length) return;
        svg.append(element("line",{x1:x(Math.min(...moments)),y1:y(pValue),x2:x(Math.max(...moments)),y2:y(pValue),class:"capacity-limit"}));
        svg.append(element("text",{x:x(Math.max(...moments))+6,y:y(pValue)+(index?14:-7),class:"tick-label"},index?"(Pmin)":"(Pmax)"));
      });
    }
  }

  function drawAxes(svg, width, height, margin, x, y, xd, yd, xTitle, yTitle) {
    const xAxisY = yd[0] <= 0 && yd[1] >= 0 ? y(0) : height-margin.bottom;
    const yAxisX = xd[0] <= 0 && xd[1] >= 0 ? x(0) : margin.left;
    for (let i=0;i<=5;i++) {
      const xv = xd[0] + i*(xd[1]-xd[0])/5, yv = yd[0] + i*(yd[1]-yd[0])/5;
      svg.append(element("line", { x1: x(xv), y1: xAxisY-5, x2: x(xv), y2: xAxisY+5, class: "axis-tick" }));
      svg.append(element("line", { x1: yAxisX-5, y1: y(yv), x2: yAxisX+5, y2: y(yv), class: "axis-tick" }));
      if (i===0 || i===5 || Math.abs(xv) < (xd[1]-xd[0])*.06) svg.append(element("text", { x: x(xv), y: xAxisY+18, "text-anchor": "middle", class: "tick-label" }, Math.round(xv)));
      if (i===0 || i===5) svg.append(element("text", { x: yAxisX+8, y: y(yv)+4, class: "tick-label" }, Math.round(yv)));
    }
    svg.append(element("line", { x1: margin.left, y1: xAxisY, x2: width-margin.right, y2: xAxisY, class: "axis-line" }));
    svg.append(element("line", { x1: yAxisX, y1: margin.top, x2: yAxisX, y2: height-margin.bottom, class: "axis-line" }));
    svg.append(element("text", { x: width-margin.right, y: xAxisY-8, "text-anchor": "end", class: "axis-label" }, xTitle));
    svg.append(element("text", { x: yAxisX+8, y: margin.top+12, class: "axis-label" }, yTitle));
  }

  function renderThree(svg, width, height) {
    const layers = state.result.onion_contours;
    if (!layers.length) { renderError("No 3D contour layers were returned."); return; }
    const center = [width*.5, height*.56], factor = Math.min(width/1900,height/2300);
    const project = (point) => { const [mx,my,p]=point; const x1=mx*Math.cos(state.yaw)-my*Math.sin(state.yaw); const y1=mx*Math.sin(state.yaw)+my*Math.cos(state.yaw); const y2=y1*Math.cos(state.pitch)-p*Math.sin(state.pitch); return [center[0]+x1*factor,center[1]-y2*factor]; };
    const rings = layers.map(layer => ({ p: layer.pu_kip, points: layer.points.map(point => [point.mx_kip_ft,point.my_kip_ft,layer.pu_kip]) }));
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
      svg.append(element("circle",{cx:load[0],cy:load[1],r:5,fill:demand.status==="OK"?"#2f363b":"#d32727",stroke:"#fff","stroke-width":1.2}));
    }
    const axes=[[[-900,0,-650],[950,0,-650],"Mx","#d32727","arrow-x"],[[0,-600,-650],[0,600,-650],"My","#14a23c","arrow-y"],[[0,0,-650],[0,0,1500],"Pu","#174ed4","arrow-z"]];
    axes.forEach(axis=>{ const a=project(axis[0]),b=project(axis[1]); svg.append(element("line",{x1:a[0],y1:a[1],x2:b[0],y2:b[1],stroke:axis[3],"stroke-width":2.2,"marker-end":`url(#${axis[4]})`})); svg.append(element("text",{x:b[0]+7,y:b[1]-6,fill:axis[3],"font-size":12},axis[2])); });
    svg.append(element("text", { x: 15, y: 20, class: "chart-title" }, "Factored PMM boundary · orange = selected Pu slice"));
    const handle=element("g",{transform:`translate(${width-48} 45)`,role:"img","aria-label":"Drag plot to rotate"});
    handle.append(element("circle",{cx:0,cy:0,r:25,fill:"#f8fafb",stroke:"#738391","stroke-width":1.5}));
    handle.append(element("path",{d:"M-15 0H15M0-15V15M-15 0l5-4m-5 4l5 4m25-4l-5-4m5 4l-5 4M0-15l-4 5m4-5l4 5M0 15l-4-5m4 5l4-5",fill:"none",stroke:"#3e4e5a","stroke-width":1.4}));
    handle.append(element("text",{x:0,y:40,"text-anchor":"middle",class:"layer-label"},"drag to spin")); svg.append(handle);
    svg.style.cursor = state.drag ? "grabbing" : "grab";
  }

  byId("run-analysis").addEventListener("click", analyze);
  byId("print-calculation").addEventListener("click", () => { if (state.result) byId("calculation-dialog").showModal(); });
  byId("close-dialog").addEventListener("click", () => byId("calculation-dialog").close());
  byId("print-dialog").addEventListener("click", () => window.print());
  byId("add-demand").addEventListener("click", () => byId("demand-table").querySelector("tbody").append(byId("demand-row-template").content.cloneNode(true)));
  byId("demand-table").addEventListener("click", event => {
    const row = event.target.closest("tr"); if (!row) return;
    const rows=[...row.parentElement.children]; state.selected=rows.indexOf(row);
    if (event.target.classList.contains("remove")) { row.remove(); state.selected=0; }
    if (state.result) { updateResults(); renderChart(); }
  });
  document.querySelectorAll("[data-view]").forEach(button => button.addEventListener("click", () => { state.view=button.dataset.view; document.querySelectorAll("[data-view]").forEach(item=>item.setAttribute("aria-pressed",String(item===button))); renderChart(); }));
  byId("capacity-chart").addEventListener("pointerdown", event => { if (state.view !== "three") return; state.drag=[event.clientX,event.clientY]; byId("capacity-chart").setPointerCapture(event.pointerId); });
  byId("capacity-chart").addEventListener("pointermove", event => { if (!state.drag || state.view !== "three") return; state.yaw+=(event.clientX-state.drag[0])*.01; state.pitch=Math.max(-1.2,Math.min(1.2,state.pitch-(event.clientY-state.drag[1])*.01)); state.drag=[event.clientX,event.clientY]; renderChart(); });
  byId("capacity-chart").addEventListener("pointerup", event => { state.drag=null; if (byId("capacity-chart").hasPointerCapture(event.pointerId)) byId("capacity-chart").releasePointerCapture(event.pointerId); renderChart(); });
  window.addEventListener("resize", () => { renderSection(); renderChart(); });
  renderSection();
  analyze();
})();
