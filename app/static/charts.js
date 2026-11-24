(function () {
  function esc(value) {
    return String(value).replace(/[&<>"']/g, function (ch) {
      return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[ch];
    });
  }
  function bars(el, points) {
    var max = Math.max.apply(null, points.map(function (p) { return Math.max(Math.abs(p.value), p.limit, 1); }));
    el.innerHTML = '<div class="bars">' + points.map(function (p) {
      var width = Math.min(100, Math.abs(p.value) / max * 100);
      return '<div class="bar"><span>' + esc(p.label) + '</span><i class="' + (p.value < 0 ? 'negative' : '') + '" style="--w:' + width + '%"></i><b>' + p.value.toFixed(2) + '</b></div>';
    }).join('') + '</div>';
  }
  function line(el, points) {
    var max = Math.max.apply(null, points.map(function (p) { return Math.max(p.value, p.limit, 1); }));
    var step = points.length > 1 ? 260 / (points.length - 1) : 0;
    var coords = points.map(function (p, i) {
      return [20 + i * step, 165 - Math.min(150, p.value / max * 150)];
    });
    var d = coords.map(function (p, i) { return (i ? 'L' : 'M') + p[0] + ' ' + p[1]; }).join(' ');
    el.innerHTML = '<svg viewBox="0 0 300 185" role="img" aria-label="指标折线"><path d="' + d +
      '" fill="none" stroke="currentColor" stroke-width="2"/><path d="' + d +
      ' L280 175 L20 175 Z" fill="currentColor" opacity=".08"/>' + coords.map(function (p, i) {
      return '<circle cx="' + p[0] + '" cy="' + p[1] + '" r="2.5" fill="currentColor"><title>' + esc(points[i].label) + '</title></circle>';
    }).join('') + '</svg>';
  }
  function gauge(el, points) {
    var item = points[0] || {label: '--', value: 0, limit: 1};
    var ratio = item.limit ? Math.max(0, Math.min(1, item.value / item.limit)) : 0;
    el.innerHTML = '<div class="gauge" style="--value:' + (ratio * 100).toFixed(1) + '%"><strong>' +
      item.value.toFixed(2) + '</strong><span class="hint">' + esc(item.label) + '</span></div>';
  }
  function ladder(el, points) {
    var max = Math.max.apply(null, points.map(function (p) { return Math.max(Math.abs(p.value), p.limit, 1); }));
    el.innerHTML = '<div class="ladder">' + points.map(function (p) {
      return '<i style="--h:' + Math.max(5, p.value / max * 100) + '%"><span>' + p.value.toFixed(1) + '</span></i>';
    }).join('') + '</div>';
  }
  window.renderChart = function (el, kind, points) {
    if (!el) return;
    if (!points || !points.length) { el.innerHTML = '<p class="empty">暂无指标</p>'; return; }
    el.style.color = "var(--accent)";
    if (points.some(function (point) { return point.value < 0; })) return bars(el, points);
    if (kind === 'line') return line(el, points);
    if (kind === 'gauge') return gauge(el, points);
    if (kind === 'ladder') return ladder(el, points);
    return bars(el, points);
  };
})();
