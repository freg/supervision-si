// Project selector : builds the project list from the json model of the page.

var pqSelectorState = { rows: [], index: {}, checked: {} };

var PQ_INDENT = 40;   // horizontal step per project level

// Reads the model from the hidden pane of the selector page and draws the list.
// Called on first display and after every refresh of the selector.
function pqSelectorInit() {
  var holder = document.getElementById('projectSelectorJsonData');
  if (!holder) { return; }
  var payload;
  try { payload = JSON.parse(holder.textContent || holder.innerText); }
  catch (e) { console.error('pqSelectorInit : invalid project model', e); return; }

  pqSelectorState.rows = (payload && payload.rows) ? payload.rows : [];
  pqSelectorState.checked = {};
  pqSelectorState.index = {};
  var i;
  var checkedIds = (payload && payload.checked) ? payload.checked : [];
  for (i = 0; i < checkedIds.length; i++) {
    pqSelectorState.checked[checkedIds[i]] = true;
  }
  for (i = 0; i < pqSelectorState.rows.length; i++) {
    pqSelectorState.index[pqSelectorState.rows[i][0]] = i;
  }
  pqSelectorDraw();
  if (typeof resizeTitlePanProjectSelector == 'function') {
    resizeTitlePanProjectSelector();
  }
}

// Draws every row in one pass
function pqSelectorDraw() {
  var viewport = document.getElementById('pqSelectorViewport');
  if (!viewport) { return; }
  var html = '';
  for (var i = 0; i < pqSelectorState.rows.length; i++) {
    html += pqSelectorRowHtml(pqSelectorState.rows[i]);
  }
  viewport.innerHTML = html;
  if (!viewport.pqBound) {
    viewport.pqBound = true;
    viewport.onclick = pqSelectorOnClick;
  }
}

// One row : the checkbox holds a fixed left column, a spacer indents icon and
// label by PQ_INDENT per level.
function pqSelectorRowHtml(row) {
  var id = row[0], name = row[1], level = row[2], reachable = row[3];
  var checked = pqSelectorState.checked[id] ? true : false;
  var shift = (level - 1) * PQ_INDENT;
  var esc = pqSelectorEscape(name);

  var s = '<div class="pqSelectorRow" data-pqid="' + id + '"';
  s += ' style="height:25px;line-height:25px;white-space:nowrap;">';

  s += '<span class="dijit dijitReset dijitInline dijitCheckBox projectSelectorCheckbox';
  s += (checked ? ' dijitCheckBoxChecked dijitChecked' : '') + '" role="presentation"';
  s += ' style="display:inline-block;vertical-align:middle;">';
  s += '<input type="checkbox" role="checkbox" aria-checked="' + (checked ? 'true' : 'false') + '"';
  s += ' class="dijitReset dijitCheckBoxInput" tabindex="0" id="checkBoxProj' + id + '"';
  s += ' value="' + id + '"' + (checked ? ' checked="checked"' : '');
  s += ' onchange="pqProjectCheckChanged(this);"></span>';

  if (shift > 0) {
    s += '<span style="display:inline-block;width:' + shift + 'px;"></span>';
  }
  s += '<span class="imageColorNewGuiNoSelection iconProject iconSize16"';
  s += ' style="display:inline-block;vertical-align:middle;margin:0 5px 0 2px;"></span>';

  // width:auto is required : the label class pins a fixed width, which would
  // both pad short names and clip long ones
  if (!reachable) {
    s += '<span class="classLinkName display" style="display:inline-block;width:auto;vertical-align:middle;color:#AAAAAA;">' + esc + '</span>';
  } else {
    s += '<span class="classLinkName menuTree pqSelectorLabel" style="display:inline-block;width:auto;vertical-align:middle;cursor:pointer;">' + esc + '</span>';
  }
  s += '</div>';
  return s;
}

// Clicking a label selects the project. The name is read from the model, never
// injected into markup.
function pqSelectorOnClick(evt) {
  var node = evt.target || evt.srcElement;
  while (node && node !== this && !dojo.hasClass(node, 'pqSelectorLabel')) {
    node = node.parentNode;
  }
  if (!node || node === this) { return; }
  var id = node.parentNode.getAttribute('data-pqid');
  var pos = pqSelectorState.index[id];
  if (pos === undefined) { return; }
  setSelectedProject(id, pqSelectorState.rows[pos][1], 'selectedProject');
}

function pqSelectorEscape(s) {
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
                  .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

// Filters the rows on a name fragment, hiding the others
function pqSelectorFilter(text) {
  var filter = String(text || '').toLowerCase();
  var rows = document.querySelectorAll('#pqSelectorViewport .pqSelectorRow');
  for (var i = 0; i < rows.length; i++) {
    var pos = pqSelectorState.index[rows[i].getAttribute('data-pqid')];
    var name = (pos === undefined) ? '' : String(pqSelectorState.rows[pos][1]).toLowerCase();
    rows[i].style.display = (filter === '' || name.indexOf(filter) > -1) ? '' : 'none';
  }
}

// Ids of the rows currently matching the search, or all of them when idle
function pqSelectorVisibleIds() {
  var out = [];
  var rows = document.querySelectorAll('#pqSelectorViewport .pqSelectorRow');
  for (var i = 0; i < rows.length; i++) {
    if (rows[i].style.display !== 'none') { out.push(rows[i].getAttribute('data-pqid')); }
  }
  return out;
}

// Mirrors an input state onto its wrapper classes and aria attribute
function pqProjectCheckSync(input) {
  if (!input) { return; }
  var wrap = input.parentNode;
  if (!wrap) { return; }
  if (input.checked) {
    dojo.addClass(wrap, 'dijitCheckBoxChecked');
    dojo.addClass(wrap, 'dijitChecked');
    input.setAttribute('aria-checked', 'true');
  } else {
    dojo.removeClass(wrap, 'dijitCheckBoxChecked');
    dojo.removeClass(wrap, 'dijitChecked');
    input.setAttribute('aria-checked', 'false');
  }
}

// Called from the onchange attribute of each checkbox
function pqProjectCheckChanged(input) {
  if (input.checked) { pqSelectorState.checked[input.value] = true; }
  else { delete pqSelectorState.checked[input.value]; }
  pqProjectCheckSync(input);
  checkProjectToSelect();
}

// Checks or unchecks by project id
function pqProjectCheckSet(idProject, checked) {
  var input = document.getElementById('checkBoxProj' + idProject);
  if (!input) { return false; }
  input.checked = checked ? true : false;
  if (checked) { pqSelectorState.checked[idProject] = true; }
  else { delete pqSelectorState.checked[idProject]; }
  pqProjectCheckSync(input);
  return true;
}

// Ids of every checked project
function pqProjectCheckList() {
  var out = [];
  for (var id in pqSelectorState.checked) {
    if (pqSelectorState.checked[id]) { out.push(id); }
  }
  return out;
}

// Clears the whole selection
function pqProjectCheckClearAll() {
  for (var id in pqSelectorState.checked) {
    var input = document.getElementById('checkBoxProj' + id);
    if (input) { input.checked = false; pqProjectCheckSync(input); }
  }
  pqSelectorState.checked = {};
}
