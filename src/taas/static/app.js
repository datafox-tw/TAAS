"use strict";

const COLORS = {
  baseline: "#8da5b3",
  staggered: "#49d8dd",
  flexible: "#67a8ff",
  shuttle: "#ffc857",
  shuttle_priority: "#ff8d6b",
  combined: "#b38cff",
};

const state = {
  meta: null,
  map: null,
  tileLayer: null,
  markers: [],
  requestTimer: null,
  latestScenario: null,
};

const $ = (id) => document.getElementById(id);
const fmt = (value, digits = 0) => Number(value ?? 0).toLocaleString("zh-TW", { maximumFractionDigits: digits });
const money = (value) => `NT$ ${fmt(value)}`;

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`;
    try {
      const body = await response.json();
      message = body.detail || message;
    } catch (_) {}
    throw new Error(message);
  }
  return response.json();
}

function showError(error) {
  const toast = $("errorToast");
  toast.textContent = `資料更新失敗：${error.message}`;
  toast.hidden = false;
  window.setTimeout(() => { toast.hidden = true; }, 6000);
}

function scenarioPayload() {
  return {
    corridor: $("corridorSelect").value,
    addressable_commuters: Number($("addressableInput").value),
    switch_rate: Number($("switchRateInput").value) / 100,
    from_car_share: 0.65,
    from_motorcycle_share: 0.25,
    from_transit_share: 0.10,
    average_car_occupancy: Number($("occupancyInput").value),
    shuttle_capacity: Number($("capacityInput").value),
    target_load_factor: 0.85,
    one_way_minutes: 55,
    turnaround_minutes: 15,
    service_window_minutes: 150,
    priority_time_saving_pct: Number($("priorityInput").value) / 100,
    assumed_daily_cost_per_bus: Number($("costInput").value),
    staggered_share: Number($("staggeredInput").value) / 100,
    flexible_share: Number($("flexibleInput").value) / 100,
    funding_preset: $("fundingInput").value,
  };
}

function syncLabels() {
  $("addressableValue").textContent = `${fmt($("addressableInput").value)} 人`;
  $("switchRateValue").textContent = `${$("switchRateInput").value}%`;
  $("staggeredValue").textContent = `${$("staggeredInput").value}%`;
  $("flexibleValue").textContent = `${$("flexibleInput").value}%`;
  $("occupancyValue").textContent = Number($("occupancyInput").value).toFixed(2);
  $("priorityValue").textContent = `${$("priorityInput").value}%`;
}

function initMap() {
  if (!window.L) return;
  state.map = L.map("map", { zoomControl: true, attributionControl: true }).setView([25.075, 121.58], 12.6);
  state.tileLayer = L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: "&copy; OpenStreetMap contributors",
  });
  state.tileLayer.addTo(state.map);
}

function speedColor(speed, status) {
  if (status !== 0) return "#8da5b3";
  if (speed == null || speed < 20) return "#ff6b6b";
  if (speed < 35) return "#ffc857";
  return "#49d8dd";
}

function renderFallback(stations) {
  const svg = $("mapFallback");
  if (!stations.length) return;
  const width = 800, height = 480, pad = 38;
  const lons = stations.map((row) => row.lon);
  const lats = stations.map((row) => row.lat);
  const minLon = Math.min(...lons), maxLon = Math.max(...lons);
  const minLat = Math.min(...lats), maxLat = Math.max(...lats);
  const x = (lon) => pad + ((lon - minLon) / (maxLon - minLon || 1)) * (width - pad * 2);
  const y = (lat) => height - pad - ((lat - minLat) / (maxLat - minLat || 1)) * (height - pad * 2);
  const grid = Array.from({ length: 8 }, (_, i) => `<line x1="${i * 115}" y1="0" x2="${i * 115}" y2="480" stroke="rgba(141,165,179,.08)"/><line x1="0" y1="${i * 70}" x2="800" y2="${i * 70}" stroke="rgba(141,165,179,.08)"/>`).join("");
  const points = stations.map((row) => {
    const radius = Math.max(4, Math.min(14, 4 + Math.sqrt(row.volume_total || 0) * 0.9));
    return `<circle cx="${x(row.lon)}" cy="${y(row.lat)}" r="${radius}" fill="${speedColor(row.speed_weighted_kph, row.status)}" fill-opacity=".68" stroke="#071019" stroke-width="1"><title>${escapeHtml(row.road_name)} ${fmt(row.volume_total)} 車次</title></circle>`;
  }).join("");
  svg.innerHTML = `${grid}<path d="M0 320 C180 260 300 360 470 300 S690 250 800 290" fill="none" stroke="rgba(73,216,221,.12)" stroke-width="28"/>${points}`;
}

function renderMapStations(stations) {
  renderFallback(stations);
  if (!state.map) return;
  state.markers.forEach((marker) => marker.remove());
  state.markers = stations.map((row) => {
    const radius = Math.max(4, Math.min(13, 4 + Math.sqrt(row.volume_total || 0) * 0.75));
    const color = speedColor(row.speed_weighted_kph, row.status);
    const marker = L.circleMarker([row.lat, row.lon], {
      radius, color: "#071019", weight: 1, fillColor: color, fillOpacity: 0.78,
    }).addTo(state.map);
    marker.bindPopup(`<strong>${escapeHtml(row.road_name)}</strong><br>${escapeHtml(row.vd_id)}<br>流量 ${fmt(row.volume_total)} · 速度 ${row.speed_weighted_kph == null ? "缺值" : `${fmt(row.speed_weighted_kph, 1)} km/h`}`);
    return marker;
  });
  if (stations.length) {
    const bounds = L.latLngBounds(stations.map((row) => [row.lat, row.lon]));
    state.map.fitBounds(bounds.pad(0.12), { animate: false, maxZoom: 14 });
  }
}

function svgLineChart(container, labels, series, options = {}) {
  const width = 820, height = options.height || 270;
  const margin = { top: 22, right: 18, bottom: 38, left: 64 };
  const plotW = width - margin.left - margin.right;
  const plotH = height - margin.top - margin.bottom;
  const allValues = series.flatMap((item) => item.values);
  const maxValue = Math.max(1, ...allValues) * 1.08;
  const x = (index) => margin.left + (labels.length === 1 ? 0 : index / (labels.length - 1)) * plotW;
  const y = (value) => margin.top + plotH - value / maxValue * plotH;
  const ticks = 4;
  let content = "";
  for (let i = 0; i <= ticks; i += 1) {
    const value = maxValue * (ticks - i) / ticks;
    const yy = margin.top + plotH * i / ticks;
    content += `<line class="grid" x1="${margin.left}" y1="${yy}" x2="${width - margin.right}" y2="${yy}"/><text x="${margin.left - 9}" y="${yy + 3}" text-anchor="end">${fmt(value)}</text>`;
  }
  labels.forEach((label, index) => {
    if (index % Math.max(1, Math.floor(labels.length / 5)) === 0 || index === labels.length - 1) {
      content += `<text x="${x(index)}" y="${height - 12}" text-anchor="middle">${escapeHtml(label)}</text>`;
    }
  });
  series.forEach((item) => {
    const path = item.values.map((value, index) => `${index ? "L" : "M"}${x(index).toFixed(1)},${y(value).toFixed(1)}`).join(" ");
    const area = `${path} L${x(item.values.length - 1)},${margin.top + plotH} L${x(0)},${margin.top + plotH} Z`;
    if (item.area) content += `<path class="area" d="${area}" fill="${item.color}"/>`;
    content += `<path class="line" d="${path}" stroke="${item.color}" ${item.dash ? `stroke-dasharray="${item.dash}"` : ""}/>`;
  });
  container.innerHTML = `<svg viewBox="0 0 ${width} ${height}" role="img"><line class="axis" x1="${margin.left}" y1="${margin.top + plotH}" x2="${width - margin.right}" y2="${margin.top + plotH}"/>${content}</svg>`;
}

function renderSensitivity(points) {
  const labels = points.map((point) => `${Math.round(point.switch_rate * 100)}%`);
  const values = points.map((point) => point.net_vehicle_trips_removed);
  svgLineChart($("sensitivityChart"), labels, [{ values, color: COLORS.shuttle, area: true }], { height: 250 });
}

async function updateTraffic() {
  const corridor = $("corridorSelect").value;
  const selectedTime = state.meta.times[Number($("timeSlider").value)];
  const [snapshot, series] = await Promise.all([
    api(`/api/traffic/snapshot?at=${encodeURIComponent(selectedTime)}&corridor=${encodeURIComponent(corridor)}`),
    api(`/api/traffic/series?corridor=${encodeURIComponent(corridor)}`),
  ]);
  $("timeLabel").textContent = selectedTime.slice(11, 16);
  $("minuteVolume").textContent = fmt(snapshot.summary.volume_total);
  $("minuteSpeed").textContent = snapshot.summary.speed_weighted_kph == null ? "缺值" : fmt(snapshot.summary.speed_weighted_kph, 1);
  $("minuteCompleteness").textContent = `${fmt(snapshot.summary.completeness_pct, 1)}%`;
  $("stationStatus").textContent = `${snapshot.summary.normal_stations}/${snapshot.summary.station_count} 個正常`;
  $("seriesStationCount").textContent = `${series.station_count} 個 VD`;
  renderMapStations(snapshot.stations);
  const peak = series.series.reduce((best, row) => row.volume_total > best.volume_total ? row : best, series.series[0]);
  $("baselineInsight").textContent = `${series.corridor_label}在 ${peak.label} 出現代表日最高 15 分鐘通過量 ${fmt(peak.volume_total)}；請搭配速度與 VD 方向人工檢查，不把單日峰值稱為典型值。`;
  svgLineChart($("baselineChart"), series.series.map((row) => row.label), [{ values: series.series.map((row) => row.volume_total), color: COLORS.staggered, area: true }]);
}

function renderPolicyLegend(policies) {
  $("policyLegend").innerHTML = policies.map((policy) => `<span class="legend-item"><i class="legend-swatch" style="background:${COLORS[policy.id]}"></i>${escapeHtml(policy.label)}</span>`).join("");
}

function renderPolicyTable(policies) {
  $("policyTable").innerHTML = policies.map((policy) => `<tr><td>${escapeHtml(policy.label)}</td><td>${fmt(policy.peak_vehicle_passages)}</td><td class="${policy.peak_reduction_pct > 0 ? "positive" : ""}">${policy.peak_reduction_pct > 0 ? "−" : ""}${fmt(policy.peak_reduction_pct, 1)}%</td><td>${escapeHtml(policy.note)}</td></tr>`).join("");
}

function renderFunding(result) {
  const preset = state.meta.funding_presets[result.shuttle.funding_preset.id];
  const parts = [
    ["市府", "city", "#49d8dd"],
    ["企業", "employers", "#b38cff"],
    ["業者", "operator", "#ff8d6b"],
    ["乘客", "riders", "#ffc857"],
  ];
  $("fundingBar").innerHTML = parts.map(([label, key, color]) => `<span title="${label} ${Math.round(preset[key] * 100)}%" style="width:${preset[key] * 100}%;background:${color}"></span>`).join("");
  $("fundingBreakdown").innerHTML = parts.map(([label, key, color]) => `<div class="funding-item"><span><i class="dot" style="background:${color}"></i>${label} · ${Math.round(preset[key] * 100)}%</span><strong>${money(result.shuttle.funding[key])}</strong></div>`).join("");
  $("dailyCost").textContent = `${money(result.shuttle.daily_cost)}／日`;
}

async function updateScenario() {
  syncLabels();
  const result = await api("/api/scenarios/evaluate", { method: "POST", body: JSON.stringify(scenarioPayload()) });
  state.latestScenario = result;
  const shuttle = result.shuttle;
  $("decisionHeadline").textContent = result.decision.headline;
  $("decisionRiders").textContent = `${fmt(shuttle.riders)} 人轉搭`;
  $("decisionCopy").textContent = `在目前假設下，${result.decision.best_peak_policy}的尖峰改善幅度最大（${fmt(result.decision.best_peak_reduction_pct, 1)}%）。這是情境投影，下一步是用多日 VD 與企業調查驗證。`;
  $("netVehicles").textContent = fmt(shuttle.net_vehicle_trips_removed, 1);
  $("busDepartures").textContent = `${fmt(shuttle.bus_departures)} 班`;
  $("fleetRequired").textContent = `${fmt(shuttle.fleet_required)} 輛`;
  $("priorityFleet").textContent = `優先通行 ${fmt(shuttle.priority_fleet_required)} 輛`;
  $("costPerRider").textContent = shuttle.cost_per_rider == null ? "—" : money(shuttle.cost_per_rider);
  const selectedPolicies = result.policies;
  renderPolicyLegend(selectedPolicies);
  renderPolicyTable(selectedPolicies);
  svgLineChart($("policyChart"), result.labels, selectedPolicies.map((policy) => ({
    values: policy.curve,
    color: COLORS[policy.id],
    area: policy.id === "combined",
    dash: policy.id === "baseline" ? "5 5" : null,
  })), { height: 310 });
  renderSensitivity(result.sensitivity);
  renderFunding(result);
}

function scheduleScenarioUpdate() {
  window.clearTimeout(state.requestTimer);
  state.requestTimer = window.setTimeout(() => updateScenario().catch(showError), 180);
}

async function loadOrigins() {
  const result = await api("/api/demand/origins?limit=8");
  const maxValue = Math.max(...result.origins.map((row) => row.average_per_workday));
  $("originBars").innerHTML = result.origins.map((row) => `<div class="origin-row"><span title="${escapeHtml(row.origin_station)}">${escapeHtml(row.origin_station)}</span><span class="origin-track"><i style="width:${100 * row.average_per_workday / maxValue}%"></i></span><strong>${fmt(row.average_per_workday)}</strong></div>`).join("");
}

function bindControls() {
  ["addressableInput", "switchRateInput", "occupancyInput", "priorityInput"].forEach((id) => {
    $(id).addEventListener("input", scheduleScenarioUpdate);
  });
  ["staggeredInput", "flexibleInput"].forEach((id) => {
    $(id).addEventListener("input", () => {
      const otherId = id === "staggeredInput" ? "flexibleInput" : "staggeredInput";
      const total = Number($(id).value) + Number($(otherId).value);
      if (total > 100) $(otherId).value = 100 - Number($(id).value);
      scheduleScenarioUpdate();
    });
  });
  ["capacityInput", "costInput", "fundingInput"].forEach((id) => {
    $(id).addEventListener("change", scheduleScenarioUpdate);
  });
  $("timeSlider").addEventListener("input", () => updateTraffic().catch(showError));
  $("corridorSelect").addEventListener("change", () => {
    Promise.all([updateTraffic(), updateScenario()]).catch(showError);
  });
  $("resetButton").addEventListener("click", () => {
    const defaults = state.meta.defaults;
    $("addressableInput").value = defaults.addressable_commuters;
    $("switchRateInput").value = defaults.switch_rate * 100;
    $("staggeredInput").value = defaults.staggered_share * 100;
    $("flexibleInput").value = defaults.flexible_share * 100;
    $("capacityInput").value = defaults.shuttle_capacity;
    $("costInput").value = defaults.assumed_daily_cost_per_bus;
    $("fundingInput").value = defaults.funding_preset;
    $("occupancyInput").value = defaults.average_car_occupancy;
    $("priorityInput").value = defaults.priority_time_saving_pct * 100;
    syncLabels();
    updateScenario().catch(showError);
  });
}

function renderLineage() {
  $("lineageList").innerHTML = state.meta.lineage.map((item) => `<div class="lineage-item"><strong><span class="tag ${item.type}">${item.type.toUpperCase()}</span> ${escapeHtml(item.label)}</strong><span>${escapeHtml(item.source)} · ${escapeHtml(item.date)}</span></div>`).join("");
}

async function boot() {
  state.meta = await api("/api/meta");
  $("corridorSelect").innerHTML = state.meta.corridors.map((item) => `<option value="${item.id}">${escapeHtml(item.label)}（${item.station_count}）</option>`).join("");
  $("timeSlider").max = state.meta.times.length - 1;
  $("timeSlider").value = Math.min(60, state.meta.times.length - 1);
  $("timeStart").textContent = state.meta.times[0].slice(11, 16);
  $("timeEnd").textContent = state.meta.times.at(-1).slice(11, 16);
  renderLineage();
  initMap();
  bindControls();
  syncLabels();
  await Promise.all([updateTraffic(), updateScenario(), loadOrigins()]);
}

boot().catch(showError);
