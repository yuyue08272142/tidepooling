(function () {
  const data = JSON.parse(document.getElementById("tide-data").textContent);
  const el = document.getElementById("tide-chart");
  if (!el || !window.echarts) return;

  const css = getComputedStyle(document.documentElement);
  const color = (name) => css.getPropertyValue(name).trim();
  const ms = (iso) => new Date(iso).getTime();
  const hm = (t) =>
    new Date(t).toLocaleTimeString("zh-CN", {
      timeZone: "Asia/Shanghai", hour: "2-digit", minute: "2-digit", hour12: false,
    });

  const start = ms(data.curve[0][0]);
  const end = ms(data.curve[data.curve.length - 1][0]);
  const now = Date.now();
  const night = [];
  if (data.astro.sunrise) night.push([{ xAxis: start }, { xAxis: ms(data.astro.sunrise) }]);
  if (data.astro.sunset) night.push([{ xAxis: ms(data.astro.sunset) }, { xAxis: end }]);

  const chart = echarts.init(el, null, { renderer: "svg" });
  chart.setOption({
    animation: false,
    grid: { left: 40, right: 22, top: 48, bottom: 36 },
    tooltip: {
      trigger: "axis",
      valueFormatter: (v) => (v == null ? "--" : v.toFixed(2) + " m"),
      axisPointer: { label: { formatter: (p) => hm(p.value) } },
    },
    xAxis: {
      type: "time", min: start, max: end, interval: 3 * 3600 * 1000,
      axisLabel: { formatter: (v) => (v === end ? "24:00" : hm(v)), color: color("--muted") },
      axisLine: { lineStyle: { color: color("--line") } },
    },
    yAxis: {
      type: "value", name: "m", nameTextStyle: { color: color("--muted") },
      axisLabel: { color: color("--muted") },
      splitLine: { lineStyle: { color: color("--line") } },
    },
    series: [{
      name: "潮高",
      type: "line",
      showSymbol: false,
      smooth: false,
      connectNulls: false,
      data: data.curve.map(([t, h]) => [ms(t), h]),
      lineStyle: { width: 2.5, color: color("--sea") },
      areaStyle: { color: color("--sea-soft") },
      markArea: { silent: true, itemStyle: { color: color("--night") }, data: night },
      markLine: now >= start && now <= end ? {
        silent: true, symbol: "none",
        lineStyle: { color: color("--now"), type: "dashed" },
        label: { formatter: "现在", color: color("--now") },
        data: [{ xAxis: now }],
      } : undefined,
      markPoint: {
        symbol: "circle", symbolSize: 8,
        label: {
          position: "top", color: color("--fg"), fontSize: 11,
          formatter: (p) => hm(p.value[0]) + "\n" + p.value[1].toFixed(2),
        },
        data: data.extremes.map((e) => ({
          coord: [ms(e.time), e.height],
          value: [ms(e.time), e.height],
          itemStyle: { color: e.kind === "high" ? color("--high") : color("--low") },
          label: { position: e.kind === "high" ? "top" : "bottom" },
        })),
      },
    }],
  });
  window.addEventListener("resize", () => chart.resize());
})();
