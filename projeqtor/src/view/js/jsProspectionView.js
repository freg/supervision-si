/*** COPYRIGHT NOTICE *********************************************************
 *
 * Copyright 2009-2017 ProjeQtOr - Pascal BERNARD - support@projeqtor.org
 * Contributors : -
 *
 * This file is part of ProjeQtOr.
 *
 * ProjeQtOr is free software: you can redistribute it and/or modify it under
 * the terms of the GNU Affero General Public License as published by the Free
 * Software Foundation, either version 3 of the License, or (at your option)
 * any later version.
 *
 * ProjeQtOr is distributed in the hope that it will be useful, but WITHOUT ANY
 * WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
 * FOR A PARTICULAR PURPOSE.  See the GNU Affero General Public License for
 * more details.
 *
 * You should have received a copy of the GNU Affero General Public License along with
 * ProjeQtOr. If not, see <http://www.gnu.org/licenses/>.
 *
 * You can get complete code of ProjeQtOr, other resource, help and information
 * about contributors at http://www.projeqtor.org
 *
 *** DO NOT REMOVE THIS NOTICE ************************************************/

/**
 * The whole screen, fetched once and kept here : the drawing never goes back to the
 * server, so filtering and scrolling cost nothing.
 */
var prospectionViewData = null;

/**
 * Column layout, shared by the header band and by every line. Widths are fixed : the
 * header is drawn once, so tables sizing their own columns would drift from it.
 */
var prospectionViewColumns = {
  company: [
    { key: 'company', label: 'colProspectNameCompany', width: 160, icon: true },
    { key: 'contact', label: 'colProspectNameContact', width: 160 }
  ],
  info: [
    { key: 'domain',        label: 'colIdDomainProspect',       width: 120 },
    { key: 'source',        label: 'colIdProspectionSource',    width: 120 },
    { key: 'email',         label: 'colEmail',                  width: 160 },
    { key: 'qualification', label: 'colIdProspectQualification', width: 110 },
    { key: 'language',      label: 'colIdLanguage',             width: 90 },
    { key: 'engagement',    label: 'colIdEngagement',           width: 100, pill: 'engagementColor' },
    { key: 'status',        label: 'colIdStatus',               width: 110, pill: 'statusColor' },
    { key: 'responsible',   label: 'colResponsible',            width: 120, thumb: 'idResponsible' }
  ],
  events: [
    { key: 'date',            label: 'colDate',            width: 90 },
    { key: 'type',            label: 'colType',            width: 110 },
    { key: 'name',            label: 'colName',            width: 200 },
    { key: 'toBeRecontacted', label: 'colToBeRecontacted', width: 100 }
  ],
  bills: [
    { key: 'name',      label: 'colName',       width: 180 },
    { key: 'date',      label: 'colDate',       width: 90 },
    { key: 'ca',        label: 'colCA',         width: 100, html: true },
    { key: 'caN',       label: 'colCAN',        width: 100, html: true },
    { key: 'caNMinus1', label: 'colCANMinus1',  width: 100, html: true },
    { key: 'status',    label: 'colIdStatus',   width: 100, pill: 'statusColor' }
  ]
};

/**
 * The three sub blocks that share the same shape, the date column apart.
 */
function prospectionViewMoneyColumns(dateLabel) {
  return [
    { key: 'name',   label: 'colName',     width: 180 },
    { key: 'date',   label: dateLabel,     width: 90 },
    { key: 'amount', label: prospectionViewAmountLabel(), width: 100, html: true },
    { key: 'status', label: 'colIdStatus', width: 100, pill: 'statusColor' }
  ];
}

/**
 * Header of the amount column. The server has already resolved which amount it
 * sends, the label only has to follow.
 */
function prospectionViewAmountLabel() {
  if (prospectionViewData && prospectionViewData.amountMode == 'TTC') return 'colFullAmount';
  return 'colUntaxedAmount';
}

/**
 * Loads and draws the screen. The shell hooks this too, some entry paths passing no
 * callback, so the guard lives on the container node, recreated on every visit.
 */
function prospectionViewInit() {
  var container = dojo.byId('prospectionViewContainer');
  if (!container || container.prospectionViewInitialised) return;
  container.prospectionViewInitialised = true;
  prospectionViewReadCollapsed();
  prospectionViewReload();
}

/**
 * Fetches the data, then draws.
 */
function prospectionViewReload() {
  dojo.xhrGet({
    url: '../tool/jsonProspectionView.php?refresh=' + (new Date()).getTime() + addTokenIndexToUrl(),
    handleAs: 'text',
    load: function(data) {
      try {
        prospectionViewData = JSON.parse(dojo.trim(data));
      } catch (e) {
        consoleTraceLog('prospectionViewReload : JSON illisible');
        return;
      }
      prospectionViewRender();
    },
    error: function() {
      consoleTraceLog('prospectionViewReload : echec du chargement');
    }
  });
}

/**
 * Escapes text coming from the database. Amounts and status pills are the only
 * values injected as markup.
 */
function prospectionViewEscape(value) {
  if (value === null || value === undefined) return '';
  return String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

/**
 * Black or white, whichever reads on the given background.
 */
function prospectionViewForeColor(color) {
  if (color.length !== 7) return '#000000';
  var light = 0.3 * parseInt(color.substr(1, 2), 16)
            + 0.6 * parseInt(color.substr(3, 2), 16)
            + 0.1 * parseInt(color.substr(5, 2), 16);
  return (light < 128) ? '#FFFFFF' : '#000000';
}

/**
 * Plain text of a cell already built as markup, for its title : amounts arrive
 * wrapped in a span and spaced with non breaking spaces.
 */
function prospectionViewPlainText(html) {
  if (html === null || html === undefined) return '';
  return String(html)
    .replace(/<[^>]*>/g, '')
    .replace(/&nbsp;/g, ' ')
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .trim();
}

/**
 * The title attribute of a cell, so a value cut by the ellipsis stays readable on
 * hover. An empty value gets no attribute : an empty tooltip is worse than none.
 */
function prospectionViewTitle(text) {
  var t = prospectionViewPlainText(text);
  return t ? ' title="' + prospectionViewEscape(t) + '"' : '';
}

/**
 * Colours of the initials. A resource always gets the same one, by its identifier.
 */
var prospectionViewColors = [
  '#1abc9c', '#2ecc71', '#3498db', '#9b59b6', '#34495e',
  '#16a085', '#27ae60', '#2980b9', '#8e44ad', '#2c3e50',
  '#f1c40f', '#e67e22', '#99CC00', '#e74c3c', '#95a5a6',
  '#d35400', '#c0392b', '#bdc3c7', '#7f8c8d'
];

/**
 * Draws the thumbnail of a resource : the server sends a picture or an initial, the
 * data-ktip attributes carry what the tooltip needs.
 */
function prospectionViewThumbOf(id) {
  if (!id || !prospectionViewData || !prospectionViewData.thumbs) return '';
  var res = prospectionViewData.thumbs[id];
  if (!res) return '';
  var commun = ' class="prospectionViewThumb kanbanTooltipTrigger"'
             + ' data-ktip="1" data-ktip-html="1" data-ktip-pos="bottom"'
             + ' data-ktip-text="' + res.name + '" data-ktip-mode="user"';
  if (res.isfile) {
    return '<img' + commun
         + ' data-ktip-user-mode="img" data-ktip-user-src="' + res.file + '"'
         + ' src="' + res.file + '" />';
  }
  var fond = prospectionViewColors[id % prospectionViewColors.length];
  return '<span' + commun
       + ' data-ktip-user-mode="initial" data-ktip-user-initial="' + res.file + '"'
       + ' data-ktip-user-bg="' + fond + '"'
       + ' style="background-color:' + fond + ';">' + res.file + '</span>';
}

/**
 * The icon of the object a line describes : the class name gives the picture.
 * refType reaches a class attribute, so it is checked against a pattern.
 */
function prospectionViewIcon(refType) {
  if (!refType || ! /^[A-Za-z]+$/.test(refType)) return '';
  return '<div class="imageColorNewGui icon' + refType + ' iconSize16 prospectionViewRowIcon"></div>';
}

/**
 * Opens the record that carries an action, on the tab that lists them. The tab is
 * chosen through the session value objectDetail reads to pick it, so the record
 * opens in the right place rather than moving once shown.
 */
function prospectionViewGotoAction(type, id) {
  if (! /^[A-Za-z]+$/.test(type) || !id) return;
  saveDataToSession('detailTab' + type, 'Treatment', true);
  gotoElement(type, id, true);
  prospectionViewOpenActions(type, 15);
}

/**
 * Unfolds the section that lists the actions, once the record is drawn. The record
 * loads asynchronously, so this waits for the pane, up to three seconds.
 */
function prospectionViewOpenActions(type, tries) {
  // The client names its section loyaltyEvent since the actions became loyalty
  // actions ; the prospect keeps eventProspect.
  var section = (type == 'Prospect') ? '_eventProspect' : '_loyaltyEvent';
  var pane = dijit.byId(type + section);
  if (pane && pane.set) { pane.set('open', true); return; }
  if (tries > 0) {
    setTimeout(function() { prospectionViewOpenActions(type, tries - 1); }, 200);
  }
}

/**
 * Draws a pill as a single div, cheap enough to repeat on every cell. The column
 * says which field holds the colour, which reaches a style attribute and is
 * therefore checked against a hex pattern.
 */
function prospectionViewPillCell(line, col) {
  if (!line[col.key]) return '';
  var text = prospectionViewEscape(line[col.key]);
  var color = line[col.pill] || '';
  if (! /^#[0-9A-Fa-f]{6}$/.test(color)) return text;
  return '<div class="prospectionViewPill" style="background-color:' + color
       + ';color:' + prospectionViewForeColor(color) + ';">' + text + '</div>';
}

/**
 * Column widths go on the cells, never in a colgroup : a colgroup stops applying
 * once tbody is display:block, which is what makes a block scroll.
 */
function prospectionViewWidth(columns, from, span) {
  var width = 0;
  for (var i = from; i < from + (span || 1) && i < columns.length; i++) { width += columns[i].width; }
  return ' style="width:' + width + 'px;"';
}

function prospectionViewTotalWidth(columns) {
  var width = 0;
  for (var i = 0; i < columns.length; i++) { width += columns[i].width; }
  return width;
}

/**
 * The blocks, in order, described once. The header band and every line read this
 * same list : a block declared here appears in both, or in neither.
 *
 * fixed marks the block that never folds and stays put on a horizontal scroll.
 * source names the field of the row the block draws, footer the builder of its
 * total row. icon dresses the button of a folded block, titleIcon the title of an
 * open one.
 */
function prospectionViewBlocks() {
  return [
    { key: 'company',    label: 'company',              columns: prospectionViewColumns.company,
      source: 'info',       rowClass: true, fixed: true },
    { key: 'info',       label: 'informations',         columns: prospectionViewColumns.info,
      source: 'info',       rowClass: true, icon: 'iconButtonProspectInformation', titleIcon: 'iconCRMProspectInformation' },
    { key: 'events',     label: 'menuProspectEvent',    columns: prospectionViewColumns.events,
      source: 'events',     rowClass: true, icon: 'iconButtonProspectEvent', titleIcon: 'iconCRMProspectEvent' },
    { key: 'estimates',  label: 'menuProspectEstimate', columns: prospectionViewMoneyColumns('colCreationDate'),
      source: 'estimates',  footer: prospectionViewMoneyFooter, icon: 'iconButtonProspectEstimate', titleIcon: 'iconCRMProspectEstimate' },
    { key: 'quotations', label: 'menuQuotation',        columns: prospectionViewMoneyColumns('colSendDate'),
      source: 'quotations', footer: prospectionViewMoneyFooter, icon: 'iconButtonQuotation', titleIcon: 'iconCRMQuotation' },
    { key: 'commands',   label: 'menuCommand',          columns: prospectionViewMoneyColumns('colReceptionDate'),
      source: 'commands',   footer: prospectionViewMoneyFooter, icon: 'iconButtonCommand', titleIcon: 'iconCRMCommand' },
    { key: 'bills',      label: 'menuBill',             columns: prospectionViewColumns.bills,
      source: 'bills',      footer: prospectionViewBillFooter, icon: 'iconButtonBill', titleIcon: 'iconCRMBill' }
  ];
}

/**
 * The class of a block, which its header and its cells share : the stylesheet needs
 * it to pin the fixed one.
 */
function prospectionViewBlockClass(block) {
  return 'prospectionViewBlock' + block.key.charAt(0).toUpperCase() + block.key.slice(1);
}

/**
 * Blocks the user has folded away, by key. Read once from the shell, which carries
 * what was kept from the last visit.
 */
var prospectionViewCollapsed = {};

/**
 * Reads the folded blocks the shell carries. An unknown key is dropped : a block
 * renamed since would otherwise stay folded with no way to reopen it.
 */
function prospectionViewReadCollapsed() {
  prospectionViewCollapsed = {};
  var champ = dojo.byId('prospectionViewCollapsedBlocks');
  if (!champ || !champ.value) return;
  var connus = {};
  var blocks = prospectionViewBlocks();
  for (var i = 0; i < blocks.length; i++) { if (!blocks[i].fixed) connus[blocks[i].key] = true; }
  var cles = String(champ.value).split(',');
  for (var j = 0; j < cles.length; j++) {
    var cle = dojo.trim(cles[j]);
    if (connus[cle]) prospectionViewCollapsed[cle] = true;
  }
}

/**
 * Folds a block away or brings it back, keeps the choice, and redraws. The scroll
 * position is put back : folding a block is not a reason to lose one's place.
 */
function prospectionViewToggleBlock(key) {
  if (prospectionViewCollapsed[key]) delete prospectionViewCollapsed[key];
  else prospectionViewCollapsed[key] = true;
  var liste = [];
  for (var cle in prospectionViewCollapsed) {
    if (prospectionViewCollapsed.hasOwnProperty(cle)) liste.push(cle);
  }
  prospectionViewSaveFilter('prospectionViewCollapsedBlocks', liste.join(','), false);
  var container = dojo.byId('prospectionViewContainer');
  var haut = container ? container.scrollTop : 0;
  var gauche = container ? container.scrollLeft : 0;
  prospectionViewRender();
  if (container) { container.scrollTop = haut; container.scrollLeft = gauche; }
  prospectionViewDrawWindow();
}

/**
 * Width of an unfolding button, the same value the stylesheet sets. Folded blocks
 * have no width, so their buttons all land on one seam : laying them out side by
 * side needs this number. Only that button is concerned, and it is the larger of
 * the two : the folding one stays at 16.
 */
var prospectionViewUnfoldWidth = 22;

/**
 * Space between two neighbouring unfolding buttons, so their icons do not touch.
 */
var prospectionViewUnfoldGap = 2;

/**
 * Where each folded block puts its reopening button, in pixels from the seam it
 * sits on. Blocks folded next to one another share that seam : their buttons are
 * laid out side by side and the run is centred on it, or they would overlap.
 */
function prospectionViewFoldedOffsets(blocks) {
  var offsets = {};
  var i = 0;
  while (i < blocks.length) {
    if (!prospectionViewCollapsed[blocks[i].key]) { i++; continue; }
    var debut = i;
    while (i < blocks.length && prospectionViewCollapsed[blocks[i].key]) { i++; }
    var nombre = i - debut;
    var pas = prospectionViewUnfoldWidth + prospectionViewUnfoldGap;
    // The run is n buttons and n-1 gaps wide, centred on the seam.
    var largeur = nombre * pas - prospectionViewUnfoldGap;
    for (var j = debut; j < i; j++) {
      offsets[blocks[j].key] = (j - debut) * pas - largeur / 2;
    }
  }
  return offsets;
}

/**
 * The header band, drawn once at the top of the screen, one group per block. It
 * takes the same width as the lines : a pinned element never leaves its containing
 * block, and a band as wide as the viewport would let the company block drift as
 * soon as the scroll passed the difference.
 */
function prospectionViewHeader(width) {
  var blocks = prospectionViewBlocks();
  // The band takes room above the titles only when something is folded : that is
  // where the reopening buttons sit.
  var replie = false;
  for (var k = 0; k < blocks.length; k++) { if (prospectionViewCollapsed[blocks[k].key]) replie = true; }
  var decalages = prospectionViewFoldedOffsets(blocks);
  var top = ['<div class="prospectionViewHeader' + (replie ? ' prospectionViewHeaderFolded' : '')
           + '" style="width:' + width + 'px;">'];
  var i, j, block, columns;
  for (i = 0; i < blocks.length; i++) {
    block = blocks[i];
    // A folded block disappears entirely, lines included. Only its reopening button
    // stays, on the seam where it stood, in a marker of no width : it reopens where
    // it vanished, and shifts nothing to its right.
    if (prospectionViewCollapsed[block.key]) {
      top.push('<div class="prospectionViewHeadBlock prospectionViewBlockFolded" style="width:0;">'
             + '<div class="' + block.icon + ' imageColorNewGui iconSize22'
             + ' prospectionViewToggle prospectionViewUnfold"'
             + ' style="left:' + decalages[block.key] + 'px;"'
             + ' onclick="prospectionViewToggleBlock(\'' + block.key + '\');"'
             + prospectionViewTitle(i18n(block.label)) + '></div></div>');
      continue;
    }
    columns = block.columns;
    top.push('<div class="prospectionViewHeadBlock ' + prospectionViewBlockClass(block)
           + '" style="width:' + prospectionViewTotalWidth(columns) + 'px;">');
    // The title icon of an open block, from the iconCRM set : the button of a folded
    // block keeps its own. imageColorNewGui is what tints it : the icons
    // are drawn in pure red and the theme recolours them by filter.
    top.push('<div class="prospectionViewGroup">'
           + (block.titleIcon ? '<div class="' + block.titleIcon + ' imageColorNewGui iconSize22'
                             + ' prospectionViewGroupIcon"></div>' : '')
           + prospectionViewEscape(i18n(block.label))
           + (block.fixed ? '' : '<div class="ganttExpandOpened prospectionViewToggle prospectionViewFold"'
                                 + ' onclick="prospectionViewToggleBlock(\'' + block.key + '\');"'
                                 + prospectionViewTitle(i18n('collapseThisSection')) + '></div>')
           + '</div>');
    top.push('<table class="prospectionViewTable"><tbody><tr>');
    for (j = 0; j < columns.length; j++) {
      // A head cell aligns like the values under it : centred over a pill, right
      // over an amount, left otherwise. Two classes, since a column is never both.
      top.push('<td class="prospectionViewHeadCell'
             + (columns[j].pill ? ' prospectionViewHeadCellCenter' : '')
             + (columns[j].html ? ' prospectionViewHeadCellRight' : '') + '"'
             + prospectionViewWidth(columns, j)
             + prospectionViewTitle(i18n(columns[j].label))
             + '>' + prospectionViewEscape(i18n(columns[j].label)) + '</td>');
    }
    top.push('</tr></tbody></table></div>');
  }
  top.push('</div>');
  return top.join('');
}

/**
 * One scrolling table : three lines are visible, the rest is reached by scroll.
 * footer, when given, is a row of already built cells that stays visible.
 */
function prospectionViewTable(columns, lines, rowClass, footer) {
  // A footed table scrolls on two lines : its total takes the third row, so every
  // block shows three rows whether it carries a total or not.
  var cls = 'prospectionViewTable' + (footer ? ' prospectionViewTableScrolled' : '');
  var out = ['<table class="' + cls + '"><tbody>'];
  var i, j, line, col, cell, rowCls;
  for (i = 0; i < lines.length; i++) {
    line = lines[i];
    rowCls = 'prospectionViewRow';
    if (rowClass) rowCls += ' ' + rowClass(line);
    // An action opens the record that carries it, on the tab that lists them ;
    // every other line opens itself.
    var clic = line.parentType
      ? 'prospectionViewGotoAction(\'' + prospectionViewEscape(line.parentType) + '\',' + parseInt(line.parentId, 10) + ');'
      : 'gotoElement(\'' + prospectionViewEscape(line.refType) + '\',' + parseInt(line.refId, 10) + ',true);';
    out.push('<tr class="' + rowCls + '" onclick="' + clic + '">');
    for (j = 0; j < columns.length; j++) {
      col = columns[j];
      var titre;
      if (col.pill)      { cell = prospectionViewPillCell(line, col); titre = line[col.key]; }
      else if (col.html) { cell = (line[col.key] === undefined) ? '' : line[col.key]; titre = cell; }
      else               { cell = prospectionViewEscape(line[col.key]); titre = line[col.key]; }
      if (col.icon)      cell = prospectionViewIcon(line.refType) + cell;
      // The thumbnails come from a table sent once, not from the line itself.
      if (col.thumb)     cell = prospectionViewThumbOf(line[col.thumb]) + cell;
      // The pill fills its cell edge to edge, so that cell carries no padding. The
      // column key reaches a class name too, a hook for the company name and the
      // amount columns to read differently from a plain cell.
      out.push('<td class="prospectionViewCell prospectionViewCell-' + col.key
             + (col.pill ? ' prospectionViewCellPill' : '') + (col.html ? ' prospectionViewCellAmount' : '') + '"'
             + prospectionViewWidth(columns, j) + prospectionViewTitle(titre) + '>' + cell + '</td>');
    }
    out.push('</tr>');
  }
  out.push('</tbody></table>');
  // The total sits in its own table, outside the scrolling one : a sticky row would
  // do the same visually but makes the compositor rebuild its layers on every scroll.
  if (footer) {
    out.push('<table class="prospectionViewTable prospectionViewFooterTable"><tbody>'
           + '<tr class="prospectionViewFooter">' + footer + '</tr>'
           + '</tbody></table>');
  }
  return out.join('');
}

/**
 * The fixed footer of the three sub blocks that carry a single total.
 */
function prospectionViewMoneyFooter(block, columns) {
  return '<td class="prospectionViewCell prospectionViewTotalLabel" colspan="2"' + prospectionViewWidth(columns, 0, 2) + prospectionViewTitle(i18n('sum')) + '>' + prospectionViewEscape(i18n('sum')) + '</td>'
       + '<td class="prospectionViewCell prospectionViewTotal"' + prospectionViewWidth(columns, 2) + prospectionViewTitle(block.total) + '>' + (block.total || '') + '</td>'
       + '<td class="prospectionViewCell"' + prospectionViewWidth(columns, 3) + '></td>';
}

/**
 * The fixed footer of the bills sub block : the three turnover totals.
 */
function prospectionViewBillFooter(block, columns) {
  return '<td class="prospectionViewCell prospectionViewTotalLabel" colspan="2"' + prospectionViewWidth(columns, 0, 2) + prospectionViewTitle(i18n('sum')) + '>' + prospectionViewEscape(i18n('sum')) + '</td>'
       + '<td class="prospectionViewCell prospectionViewTotal"' + prospectionViewWidth(columns, 2) + prospectionViewTitle(block.totalCA) + '>' + (block.totalCA || '') + '</td>'
       + '<td class="prospectionViewCell prospectionViewTotal"' + prospectionViewWidth(columns, 3) + prospectionViewTitle(block.totalCAN) + '>' + (block.totalCAN || '') + '</td>'
       + '<td class="prospectionViewCell prospectionViewTotal"' + prospectionViewWidth(columns, 4) + prospectionViewTitle(block.totalCANMinus1) + '>' + (block.totalCANMinus1 || '') + '</td>'
       + '<td class="prospectionViewCell"' + prospectionViewWidth(columns, 5) + '></td>';
}

/**
 * Background colour, by the kind of record the line describes. An action of the
 * prospect and one of its clients must be told apart at a glance.
 */
function prospectionViewKindRowClass(line) {
  if (line.kind == 'prospect') return 'prospectionViewRowProspect';
  if (line.kind == 'client')   return 'prospectionViewRowClient';
  if (line.kind == 'contact')  return 'prospectionViewRowContact';
  return '';
}

function prospectionViewBlock(cls, columns, content) {
  return '<div class="prospectionViewBlock ' + cls + '" style="width:'
       + prospectionViewTotalWidth(columns) + 'px;">' + content + '</div>';
}

/**
 * Builds one main line, block by block, from the same list the header reads.
 */
function prospectionViewLineHtml(row, first) {
  var blocks = prospectionViewBlocks();
  var out = ['<div class="prospectionViewLine' + (first ? ' prospectionViewLineFirst' : '') + '">'];
  for (var i = 0; i < blocks.length; i++) {
    var block = blocks[i];
    if (prospectionViewCollapsed[block.key]) continue;
    var content;
    if (block.footer) {
      // A financial block : its lines hang from a sub object, and an empty one gets
      // no total row, a Total facing nothing reading as a defect.
      var sub = row[block.source];
      var lines = (sub && sub.lines) ? sub.lines : [];
      content = prospectionViewTable(block.columns, lines, null,
                                     lines.length ? block.footer(sub, block.columns) : null);
    } else {
      content = prospectionViewTable(block.columns, row[block.source] || [],
                                     block.rowClass ? prospectionViewKindRowClass : null, null);
    }
    out.push(prospectionViewBlock(prospectionViewBlockClass(block), block.columns, content));
  }
  out.push('</div>');
  return out.join('');
}

/**
 * Height of a main line, the same value the stylesheet sets. The windowing
 * arithmetic needs every line to be the same height.
 */
var prospectionViewLineHeight = 91;

/** Lines drawn above and below the visible area, so a fast scroll finds them ready. */
var prospectionViewOverscan = 6;

var prospectionViewDrawn = { first: -1, last: -1 };
var prospectionViewScrollPending = false;

/**
 * The lines the filters keep. The screen draws from this array, never from the rows
 * as received, so filtering costs no round trip.
 */
var prospectionViewRows = [];

/**
 * Reads the header widgets : a text box answers through its node, a FilteringSelect
 * through its widget.
 */
function prospectionViewFilterValues() {
  function texte(id) { var n = dojo.byId(id); return n ? String(n.value).toLowerCase().trim() : ''; }
  function liste(id) {
    var w = dijit.byId(id);
    var v = w ? w.get('value') : null;
    return (v === null || v === undefined) ? '' : String(v).trim();
  }
  return {
    name:          texte('prospectionViewFilterName'),
    domain:        liste('prospectionViewFilterDomain'),
    source:        liste('prospectionViewFilterSource'),
    qualification: liste('prospectionViewFilterQualification'),
    engagement:    liste('prospectionViewFilterEngagement'),
    status:        liste('prospectionViewFilterStatus'),
    responsible:   liste('prospectionViewFilterResponsible')
  };
}

/**
 * Applies the filters and redraws. Called by every header widget.
 */
function prospectionViewApplyFilters() {
  if (!prospectionViewData) return;
  var f = prospectionViewFilterValues();
  var all = prospectionViewData.rows || [];
  prospectionViewRows = [];
  for (var i = 0; i < all.length; i++) {
    var row = all[i];
    // row.search holds every name of the line, already folded to lower case.
    if (f.name && String(row.search || row.name).indexOf(f.name) < 0) continue;
    if (f.domain && String(row.idDomain) !== f.domain) continue;
    if (f.source && String(row.idSource) !== f.source) continue;
    if (f.qualification && String(row.idQualification) !== f.qualification) continue;
    if (f.engagement && String(row.idEngagement) !== f.engagement) continue;
    if (f.status && String(row.idStatus) !== f.status) continue;
    if (f.responsible && String(row.idResponsible) !== f.responsible) continue;
    prospectionViewRows.push(row);
  }
  var container = dojo.byId('prospectionViewContainer');
  if (container) container.scrollTop = 0;
  prospectionViewDrawn.first = -1;
  prospectionViewDrawn.last = -1;
  var visible = dojo.byId('prospectionViewVisible');
  if (visible) visible.innerHTML = '';
  prospectionViewShowCount();
  prospectionViewDrawWindow();
}

/** Pending save of the text filter, so typing does not fire a request per letter. */
var prospectionViewSaveTimer = null;

/**
 * Keeps a filter as a user parameter, so it survives leaving the screen. Deferred
 * for the text box, or typing would fire a request per letter.
 *
 * Trimmed : the blank entry of a reference list carries a space, which the screen
 * would then read back as a value.
 */
function prospectionViewSaveFilter(param, value, deferred) {
  var v = (value === null || value === undefined) ? '' : String(value).trim();
  if (!deferred) { saveDataToSession(param, v, true); return; }
  clearTimeout(prospectionViewSaveTimer);
  prospectionViewSaveTimer = setTimeout(function() { saveDataToSession(param, v, true); }, 400);
}

/**
 * Empties every filter, forgets them, and redraws.
 */
function prospectionViewResetFilters() {
  var champ = dojo.byId('prospectionViewFilterName');
  if (champ) champ.value = '';
  prospectionViewSaveFilter('prospectionViewFilterName', '', false);
  var ids = ['prospectionViewFilterDomain', 'prospectionViewFilterSource',
             'prospectionViewFilterQualification', 'prospectionViewFilterEngagement',
             'prospectionViewFilterStatus', 'prospectionViewFilterResponsible'];
  for (var i = 0; i < ids.length; i++) {
    var w = dijit.byId(ids[i]);
    if (w) w.set('value', '');
    prospectionViewSaveFilter(ids[i], '', false);
  }
  prospectionViewApplyFilters();
}

/**
 * Shows how many lines the filters keep, and the message when they keep none.
 */
function prospectionViewShowCount() {
  var total = (prospectionViewData && prospectionViewData.rows) ? prospectionViewData.rows.length : 0;
  var compte = dojo.byId('prospectionViewCount');
  if (compte) compte.innerHTML = (prospectionViewRows.length === total)
    ? prospectionViewEscape(total)
    : prospectionViewEscape(prospectionViewRows.length + ' / ' + total);
  var msg = dojo.byId('prospectionViewMessage');
  if (msg) msg.innerHTML = prospectionViewRows.length ? '' : i18n('noDataToDisplay');
}

/**
 * Draws the screen from prospectionViewData, with no network call : this is what a
 * filter calls back. Only the visible lines reach the document, framed by two
 * spacers that hold the scroll height.
 */
function prospectionViewRender() {
  var body = dojo.byId('prospectionViewBody');
  if (!body || !prospectionViewData) return;

  var rows = prospectionViewData.rows || [];
  if (!rows.length) {
    var vide = dojo.byId('prospectionViewMessage');
    if (vide) vide.innerHTML = i18n('noDataToDisplay');
    body.innerHTML = '';
    return;
  }

  var blocksForWidth = prospectionViewBlocks();
  var width = 0;
  for (var w = 0; w < blocksForWidth.length; w++) {
    if (prospectionViewCollapsed[blocksForWidth[w].key]) continue;
    width += prospectionViewTotalWidth(blocksForWidth[w].columns);
  }

  body.innerHTML = prospectionViewHeader(width)
    + '<div id="prospectionViewLines" style="width:' + width + 'px;">'
    + '<div id="prospectionViewSpacerTop"></div>'
    + '<div id="prospectionViewVisible"></div>'
    + '<div id="prospectionViewSpacerBottom"></div>'
    + '</div>';

  prospectionViewDrawn.first = -1;
  prospectionViewDrawn.last = -1;
  prospectionViewBindScroll();
  // The tooltip listens on the container and reads the data-ktip attributes.
  if (typeof KanbanTooltip != 'undefined') {
    KanbanTooltip.init({ root: dojo.byId('prospectionViewContainer') || document });
  }
  // Applying rather than resetting : the header keeps whatever was typed before.
  prospectionViewApplyFilters();
}

/**
 * Listens to the container once. The flag lives on the node, which is rebuilt on
 * every visit, so it goes away with it.
 */
function prospectionViewBindScroll() {
  var container = dojo.byId('prospectionViewContainer');
  if (!container || container.prospectionViewBound) return;
  container.prospectionViewBound = true;
  container.addEventListener('scroll', function() {
    if (prospectionViewScrollPending) return;
    prospectionViewScrollPending = true;
    requestAnimationFrame(function() {
      prospectionViewScrollPending = false;
      prospectionViewDrawWindow();
    });
  });
}

/**
 * Puts in the document the lines the viewport needs, and nothing else.
 */
function prospectionViewDrawWindow() {
  var container = dojo.byId('prospectionViewContainer');
  var visible = dojo.byId('prospectionViewVisible');
  if (!container || !visible || !prospectionViewData) return;

  var rows = prospectionViewRows;
  var header = document.querySelector('.prospectionViewHeader');
  var top = Math.max(0, container.scrollTop - (header ? header.offsetHeight : 0));

  var first = Math.max(0, Math.floor(top / prospectionViewLineHeight) - prospectionViewOverscan);
  var count = Math.ceil(container.clientHeight / prospectionViewLineHeight) + prospectionViewOverscan * 2;
  var last = Math.min(rows.length, first + count);
  var drawn = prospectionViewDrawn;
  if (first === drawn.first && last === drawn.last) return;

  // Only the lines that entered or left are touched : a scroll of one line shifts
  // the window by one, so rebuilding it whole would redraw everything each time.
  if (drawn.first < 0 || first >= drawn.last || last <= drawn.first) {
    var out = [];
    for (var i = first; i < last; i++) { out.push(prospectionViewLineHtml(rows[i], i === 0)); }
    visible.innerHTML = out.join('');
    drawn.first = first;
    drawn.last = last;
  } else {
    while (drawn.first < first) { visible.removeChild(visible.firstChild); drawn.first++; }
    while (drawn.last > last)   { visible.removeChild(visible.lastChild);  drawn.last--; }
    while (drawn.first > first) { drawn.first--; visible.insertAdjacentHTML('afterbegin', prospectionViewLineHtml(rows[drawn.first], drawn.first === 0)); }
    while (drawn.last < last)   { visible.insertAdjacentHTML('beforeend', prospectionViewLineHtml(rows[drawn.last], drawn.last === 0)); drawn.last++; }
  }

  dojo.byId('prospectionViewSpacerTop').style.height = (first * prospectionViewLineHeight) + 'px';
  dojo.byId('prospectionViewSpacerBottom').style.height = ((rows.length - last) * prospectionViewLineHeight) + 'px';
}
