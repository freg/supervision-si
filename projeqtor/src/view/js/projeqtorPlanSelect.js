// Visible list of plannable projects, drawn over a hidden native select.
// The select holds the state, so no widget is created per row.

function pqPlanSelectNode() {
  return document.getElementById('idProjectPlan');
}

// Builds every row from the options of the hidden select
function pqPlanListInit() {
  var sel = pqPlanSelectNode();
  var box = document.getElementById('pqPlanList');
  if (!sel || !box) { return; }
  var html = '';
  for (var i = 0; i < sel.options.length; i++) {
    html += pqPlanRowHtml(sel.options[i]);
  }
  box.innerHTML = html;
  if (!box.pqBound) {
    box.pqBound = true;
    box.onclick = pqPlanOnClick;
  }
  // The widget fires onChange on every set('value'), which callers use to force
  // a selection ; the rows have to follow.
  var w = dijit.byId('idProjectPlan');
  pqPlanPatchWidget(w);
  if (w && !w.pqSyncBound) {
    w.pqSyncBound = true;
    dojo.connect(w, 'onChange', function () { pqPlanListSync(); });
  }
}

// Restores what dijit.form.MultiSelect lacks : callers pass a plain string or
// null, where it clears the whole selection instead of selecting that project.
function pqPlanPatchWidget(w) {
  if (!w || w.pqPatched) { return; }
  w.pqPatched = true;
  w._setValueAttr = function (value, priorityChange) {
    if (value === null || value === undefined) { return; }
    if (!dojo.isArray(value)) { value = [value]; }
    var wanted = [];
    for (var i = 0; i < value.length; i++) { wanted.push(String(value[i])); }
    var opts = this.containerNode.getElementsByTagName('option');
    for (var j = 0; j < opts.length; j++) {
      opts[j].selected = (wanted.indexOf(opts[j].value) != -1);
    }
    pqPlanListSync();
    this._handleOnChange(this.get('value'), priorityChange);
  };
}

// One row, matching the markup of the widget template
function pqPlanRowHtml(option) {
  var checked = option.selected;
  var s = '<div class="dijitReset dojoxMultiSelectItem" data-pqval="' + pqPlanEscape(option.value) + '">';
  s += '<span class="dijit dijitReset dijitInline dijitCheckBox';
  s += (checked ? ' dijitCheckBoxChecked dijitChecked' : '') + '"';
  s += ' role="checkbox" aria-checked="' + (checked ? 'true' : 'false') + '"';
  s += ' style="display:inline-block;vertical-align:middle;cursor:pointer;"></span>';
  s += '<div class="dijitInline dojoxMultiSelectItemLabel">' + option.innerHTML + '</div>';
  s += '</div>';
  return s;
}

function pqPlanEscape(s) {
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;')
                  .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

// Clicking a row toggles the matching option of the hidden select
function pqPlanOnClick(evt) {
  var node = evt.target || evt.srcElement;
  while (node && node !== this && !dojo.hasClass(node, 'dojoxMultiSelectItem')) {
    node = node.parentNode;
  }
  if (!node || node === this) { return; }
  pqPlanListToggle(node.getAttribute('data-pqval'));
}

function pqPlanListToggle(value) {
  var sel = pqPlanSelectNode();
  if (!sel) { return; }
  for (var i = 0; i < sel.options.length; i++) {
    if (sel.options[i].value === value) {
      sel.options[i].selected = !sel.options[i].selected;
      break;
    }
  }
  pqPlanListSync();
  if (typeof changedIdProjectPlan == 'function') {
    var w = dijit.byId('idProjectPlan');
    changedIdProjectPlan(w ? w.get('value') : null);
  }
}

// Reflects option.selected onto the rows, without rebuilding them
function pqPlanListSync() {
  var sel = pqPlanSelectNode();
  var box = document.getElementById('pqPlanList');
  if (!sel || !box) { return; }
  var state = {};
  for (var j = 0; j < sel.options.length; j++) {
    state[sel.options[j].value] = sel.options[j].selected;
  }
  var rows = box.getElementsByClassName('dojoxMultiSelectItem');
  for (var i = 0; i < rows.length; i++) {
    var mark = rows[i].firstChild;
    if (!mark) { continue; }
    if (state[rows[i].getAttribute('data-pqval')]) {
      dojo.addClass(mark, 'dijitCheckBoxChecked');
      dojo.addClass(mark, 'dijitChecked');
      mark.setAttribute('aria-checked', 'true');
    } else {
      dojo.removeClass(mark, 'dijitCheckBoxChecked');
      dojo.removeClass(mark, 'dijitChecked');
      mark.setAttribute('aria-checked', 'false');
    }
  }
}
