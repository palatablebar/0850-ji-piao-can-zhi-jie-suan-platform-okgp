(function () {
  var state = { run: null, ledger: null };
  var $ = function (id) { return document.getElementById(id); };
  function esc(value) {
    return String(value === null || value === undefined ? '' : value).replace(/[&<>"']/g, function (ch) {
      return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[ch];
    });
  }
  function notice(text) {
    var el = $('notice');
    if (el) el.textContent = text || '';
  }
  async function request(url, options) {
    var response = await fetch(url, Object.assign({headers: {'Content-Type': 'application/json'}}, options || {}));
    var data = await response.json().catch(function () { return {}; });
    if (!response.ok) throw new Error(data.error || ('HTTP ' + response.status));
    return data;
  }
  function thisMonth() {
    var now = new Date();
    return now.getFullYear() + '-' + String(now.getMonth() + 1).padStart(2, '0');
  }
  function bindRunState() {
    // 与 workbench.js 的批次状态联动：签发后才允许登记更正
    var sync = function () {
      var statusEl = $('run-status');
      var approved = statusEl && /^APPROVED/.test(statusEl.textContent);
      $('acct-correct').disabled = !approved;
      if (approved) {
        var link = $('download');
        var match = link && link.href.match(/\/api\/runs\/([^/]+)\//);
        state.runId = match ? match[1] : null;
      } else {
        state.runId = null;
      }
    };
    ['run', 'sign', 'hold'].forEach(function (id) {
      var el = $(id);
      if (el) el.addEventListener('click', function () { setTimeout(sync, 350); });
    });
    sync();
  }
  function renderSummary(data) {
    state.ledger = data;
    var t = data.totals;
    var closeLine = data.close
      ? '<div class="ledger-row"><span>封账时间</span><strong>' + esc(data.close.closed_at) + '</strong></div>'
        + '<div class="ledger-row"><span>快照校验</span><strong class="' +
          (data.snapshot_verified ? 'check-ok' : 'check-bad') + '">' +
          (data.snapshot_verified ? '通过' : '异常') + '</strong></div>'
      : '';
    $('acct-summary').innerHTML =
      '<div class="ledger-row"><span>账期状态</span><span class="acct-badge" data-s="' + esc(data.status) + '">' +
        (data.frozen ? '已封账（冻结）' : '未封账') + '</span></div>' +
      '<div class="ledger-row"><span>分录数</span><strong>' + t.entry_count + '</strong></div>' +
      '<div class="ledger-row"><span>借方合计(分)</span><strong>' + t.debit_total + '</strong></div>' +
      '<div class="ledger-row"><span>贷方合计(分)</span><strong>' + t.credit_total + '</strong></div>' +
      '<div class="ledger-row"><span>净额(分)</span><strong>' + t.net_total + '</strong></div>' + closeLine;
    $('acct-close').disabled = data.frozen;
    var dl = $('acct-download');
    dl.hidden = false;
    dl.href = '/api/accounting/periods/' + encodeURIComponent(data.period) + '/ledger?format=csv';
    $('acct-entries').innerHTML = data.entries.length ? data.entries.map(function (entry) {
      var canReverse = entry.entry_type === 'ADJUSTMENT' && !data.frozen;
      var action = canReverse
        ? '<button type="button" data-reverse="' + esc(entry.correction_id) + '">撤销</button>'
        : (entry.entry_type === 'REVERSAL' ? '撤销分录' : '已封账');
      return '<tr><td>' + esc(entry.entry_type) + '</td><td>' + esc(entry.ticket_id) +
        '</td><td><small>' + esc(entry.correction_id) + '</small></td>' +
        '<td class="num">' + entry.amount_cents + '</td><td>' + action + '</td></tr>';
    }).join('') : '<tr><td class="empty" colspan="5">该账期暂无分录</td></tr>';
    Array.from(document.querySelectorAll('[data-reverse]')).forEach(function (button) {
      button.addEventListener('click', function () { reverse(button.getAttribute('data-reverse')); });
    });
  }
  async function loadLedger() {
    var period = $('acct-period').value;
    if (!period) { notice('请先选择账期'); return; }
    try {
      notice('');
      renderSummary(await request('/api/accounting/periods/' + encodeURIComponent(period) + '/ledger'));
    } catch (error) { notice(error.message); }
  }
  async function close() {
    var period = $('acct-period').value;
    if (!period) { notice('请先选择账期'); return; }
    try {
      notice('');
      var result = await request('/api/accounting/periods/' + encodeURIComponent(period) + '/close', {method: 'POST'});
      notice(result.idempotent ? '封账已完成（重试幂等），快照摘要 ' + result.snapshot.snapshot_digest.slice(0, 12)
                               : '账期 ' + period + ' 已封账，新账期 ' + result.next_open_period);
      await loadLedger();
    } catch (error) { notice(error.message); }
  }
  async function correct() {
    if (!state.runId) { notice('请先执行并签发批次'); return; }
    var ticket = $('acct-ticket').value.trim();
    var fee = $('acct-fee').value.trim();
    var requestId = $('acct-request').value.trim();
    if (!ticket || fee === '' || !requestId) { notice('票号、更正后改期费和请求号均必填'); return; }
    try {
      notice('');
      var result = await request('/api/accounting/corrections', {
        method: 'POST',
        body: JSON.stringify({run_id: state.runId, ticket_id: ticket,
                              new_fee_cents: Number(fee), request_id: requestId})
      });
      notice((result.created ? '更正已入账' : '重复请求，返回既有更正') +
             '，差额 ' + result.difference_cents + ' 分进入 ' + result.adjustment.period);
      $('acct-period').value = result.adjustment.period;
      await loadLedger();
    } catch (error) { notice(error.message); }
  }
  async function reverse(correctionId) {
    try {
      notice('');
      var result = await request('/api/accounting/corrections/' + encodeURIComponent(correctionId) + '/reverse',
                                 {method: 'POST'});
      var r = result.reversal || {};
      notice(r.placement === 'SAME_PERIOD'
        ? '撤销已在同月抵消，净额归零'
        : '原账期已封账，撤销影响 ' + r.amount_cents + ' 分进入当期 ' + r.period);
      if (r.period) $('acct-period').value = r.period;
      await loadLedger();
    } catch (error) { notice(error.message); }
  }
  function boot() {
    $('acct-period').value = thisMonth();
    $('acct-load').addEventListener('click', loadLedger);
    $('acct-close').addEventListener('click', close);
    $('acct-correct').addEventListener('click', correct);
    bindRunState();
  }
  document.addEventListener('DOMContentLoaded', boot);
})();
