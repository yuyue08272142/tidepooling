(function () {
  const el = document.getElementById("station-map");
  if (!el || !window.L) return;
  const data = JSON.parse(document.getElementById("map-data").textContent);

  const css = getComputedStyle(document.documentElement);
  const color = (name) => css.getPropertyValue(name).trim();
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
  const hm = (iso) => iso.slice(11, 16);
  const stars = (n) => "★".repeat(n) + "☆".repeat(5 - n);
  const fill = (sg) => {
    if (!sg) return color("--muted");
    if (sg.verdict === "不宜赶海") return color("--big");
    if (sg.stars >= 4) return color("--low");
    if (sg.stars === 3) return color("--mid");
    return color("--small");
  };
  const offsets = { right: [12, 0], left: [-12, 0], top: [0, -12], bottom: [0, 12] };

  const map = L.map(el, { scrollWheelZoom: false, zoomSnap: 0.5 });
  map.attributionControl.setPrefix('<a href="https://leafletjs.com">Leaflet</a>');
  data.tiles.forEach((t) =>
    L.tileLayer(t.url, { subdomains: t.subdomains || "abc", attribution: t.attribution, maxZoom: t.maxZoom }).addTo(map)
  );

  const markers = data.points.map((p) => {
    const sg = p.suggestion;
    const marker = L.circleMarker([p.lat, p.lon], {
      radius: 11, color: "#fff", weight: 2.5, fillColor: fill(sg), fillOpacity: 1,
    });
    const label = `<b>${esc(p.name)}</b>` + (sg ? `<span class="map-stars">${stars(sg.stars)}</span>` : "");
    marker.bindTooltip(label, {
      permanent: true, interactive: true, className: "map-label",
      direction: p.label in offsets ? p.label : "right", offset: offsets[p.label] || offsets.right,
    });

    let body;
    if (sg) {
      body = `
        <div class="map-pop-stars"><span class="stars">${stars(sg.stars)}</span> ${esc(sg.verdict)}</div>
        <dl>
          <dt>${sg.night ? "夜间" : ""}最佳时段</dt><dd>${hm(sg.window_start)} – ${hm(sg.window_end)}</dd>
          <dt>低潮</dt><dd>${hm(sg.low.time)} · ${sg.low.height.toFixed(2)} m</dd>
          <dt>最晚离开</dt><dd class="must">${hm(sg.leave_by)}</dd>
        </dl>`;
    } else {
      body = `<p>今天的数据还没有缓存。</p>`;
    }
    marker.bindPopup(`
      <div class="map-pop">
        <div class="map-pop-head"><b>${esc(p.name)}</b>${p.period ? ` <span class="badge period-${esc(p.period)}">${esc(p.period)}</span>` : ""}</div>
        ${body}
        <div class="map-pop-links"><a href="${esc(p.url)}">潮汐详情 ›</a><a href="${esc(p.calendar)}">赶海日历 ›</a></div>
      </div>`);
    marker.on("tooltipopen", (e) => e.tooltip.getElement()?.addEventListener("click", () => marker.openPopup()));
    return marker.addTo(map);
  });

  // 左右多留些边距，给最外侧站点的标签（约 80px 宽）留位置
  map.fitBounds(L.featureGroup(markers).getBounds(), { padding: [90, 50], maxZoom: 12 });
  window.addEventListener("resize", () => map.invalidateSize());
})();
