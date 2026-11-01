///*******************************************************************************
// * COPYRIGHT NOTICE *
// *
// * Copyright 2009-2017 ProjeQtOr - Pascal BERNARD - support@projeqtor.org Contributors : -
// *
// * This file is part of ProjeQtOr.
// *
// * ProjeQtOr is free software: you can redistribute it and/or modify it under
// * the terms of the GNU Affero General Public License as published by the Free Software
// * Foundation, either version 3 of the License, or (at your option) any later
// * version.
// *
// * ProjeQtOr is distributed in the hope that it will be useful, but WITHOUT ANY
// * WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
// * A PARTICULAR PURPOSE. See the GNU Affero General Public License for more details.
// *
// * You should have received a copy of the GNU Affero General Public License along with
// * ProjeQtOr. If not, see <http://www.gnu.org/licenses/>.
// *
// * You can get complete code of ProjeQtOr, other resource, help and information
// * about contributors at http://www.projeqtor.org
// *
// * DO NOT REMOVE THIS NOTICE **
// ******************************************************************************/

var documentExplorerDrawInProgress = false;
function documentExplorerDraw() {
  documentExplorerDrawInProgress = true;

  if (dojo.byId('objectClass') && !dojo.byId('objectClass').value
      && dojo.byId('objectClassName') && dojo.byId('objectClassName').value) {
    dojo.byId('objectClass').value = dojo.byId('objectClassName').value;
  }
  if (dojo.byId('objectId') && !dojo.byId('objectId').value
      && dijit.byId('id') && dijit.byId('id').get('value')) {
    dojo.byId('objectId').value = dijit.byId('id').get('value');
  }

  var jsonData = dojo.byId('documentExplorerJsonData');
  if (!jsonData) {
    documentExplorerDrawInProgress = false;
    return;
  }
  var store;
  try {
    store = JSON.parse(dojo.trim(jsonData.innerHTML));
  } catch (e) {
    consoleTraceLog('documentExplorerDraw : JSON illisible');
    consoleTraceLog(jsonData.innerHTML.substring(0, 400));
    hideWait();
    documentExplorerDrawInProgress = false;
    return;
  }

  var items    = store.items || [];
  var docItems = (store.documents && store.documents.items) ? store.documents.items : [];

  documentExplorerSelectedDirectory = store.currentDirectory || null;


  documentExplorerDirectoryList = new DocumentExplorerList('documentExplorerDirectoryList', dojo.byId('leftGanttChartDIV'), 'week');
  documentExplorerDirectoryList.setPlanningType('directory');
  documentExplorerSetColumnsVisibility(documentExplorerDirectoryList, 'directory');

  documentExplorerDocumentList = new DocumentExplorerList('documentExplorerDocumentList', dojo.byId('rightGanttChartDIV'), 'week');
  documentExplorerDocumentList.setPlanningType('document');
  documentExplorerDocumentList.setIdPrefix('doc_');
  documentExplorerSetColumnsVisibility(documentExplorerDocumentList, 'document');

  documentExplorerResetFieldsDescription();

  if (!items.length) {
    if (dojo.byId('leftGanttChartDIV')) {
      dojo.byId('leftGanttChartDIV').innerHTML =
        '<div class="labelMessageEmptyArea" style="top:42px;">' + i18n('ganttMsgLeftPart') + '</div>';
    }
    if (dojo.byId('rightGanttChartDIV')) dojo.byId('rightGanttChartDIV').innerHTML = '';
    hideWait();
    documentExplorerDrawInProgress = false;
    return;
  }

  var i;
  for (i = 0; i < items.length; i++) {
    documentExplorerDirectoryList.AddTaskItem(new DocumentExplorerItem(items[i], 'directory'));
  }
  for (i = 0; i < docItems.length; i++) {
    documentExplorerDocumentList.AddTaskItem(new DocumentExplorerItem(docItems[i], 'document'));
  }

  documentExplorerDirectoryList.Draw();
  documentExplorerDocumentList.Draw();
  documentExplorerShowVisibleLines();

  documentExplorerCurrentEditList = null;
  currentRowToEdit = null;
  isEditRowFinishDisplay = false;
  cachedEditRowPlanningClick = null;
  vGanttCurrentLine = null;
  defaultValueOnchange = true;

  documentExplorerUnselectLines();

  documentExplorerDrawInProgress = false;
}

function documentExplorerShowLines(chart) {
  var chartList = chart || documentExplorerDirectoryList;
  if (!chartList) return;
  var vList = chartList.getList();
  for (var i = 0; i < vList.length; i++) {
    if (!vList[i]) continue;
    if (vList[i].getVisible() == 1) {
      documentExplorerShowOneLine(i, vList[i].getID(), chartList);
    }
  }
}

function documentExplorerShowOneLine(i, pID, chart) {
  var chartList = chart || documentExplorerDirectoryList;
  if (!chartList) return;
  if (!chartList.getLineByID(pID)) return;
  if (dojo.byId('child_' + pID)) {
    dojo.byId('child_' + pID).innerHTML = documentExplorerDrawLeftPart(i, chartList);
  }
}

function documentExplorerShowVisibleLines() {
  documentExplorerShowLines(documentExplorerDirectoryList);
  documentExplorerShowLines(documentExplorerDocumentList);
  documentExplorerBindHeaderDnd();
  documentExplorerBindDropGuard();
  documentExplorerRefreshDocumentPath();
  documentExplorerMarkCurrentDirectory();
  hideWait();
  if (window.top && window.top.hideField) window.top.hideField('wait');
}

function documentExplorerRunScript(refType, refId, id, keepDetailOnce) {
  /* A click on a row gives the option back the last word ; internal calls that
     reselect a row pass keepDetailOnce to hold what is shown. */
  if (! keepDetailOnce) documentExplorerPaneOverride = null;
  var vChart = (typeof documentExplorerListFor == 'function') ? documentExplorerListFor(refType) : documentExplorerDirectoryList;
  if (vChart) {
    var vList = vChart.getList();
    if (vList) {
      var vTask = null;
      for (var i = 0; i < vList.length; i++) {
        if (vList[i].getID() == id) {
          vTask = vList[i];
          break;
        }
      }
      if (vTask) {
        var idProject = vTask.getProjectId();
        JSGantt.closeEditRowObjectPlanning();
        cachedEditRowPlanningClick = 'JSGantt.planningRowClickAction(\'' + id + '\', ' + refId + ', \'' + refType + '\', \'' + idProject + '\')';
        JSGantt.editRowObjectPlanning(id, refId, refType, idProject);
        if ((documentExplorerClickAction != 1)) {
          var buttonDetail = dojo.byId('buttonEditRowDetail');
          if (buttonDetail) {
            dojo.removeClass(buttonDetail, 'iconButtonView16 iconButtonView');
            dojo.addClass(buttonDetail, 'iconButtonNoView16 iconButtonNoView');
            dojo.setAttr(buttonDetail, 'onclick', 'hideDetailScreen();JSGantt.closeAndSelectEditRow(\'' + id + '\', \'' + refId + '\', \'' + refType + '\', \'' + idProject + '\')');
            dojo.setAttr(buttonDetail, 'title', i18n('colHideDetail'));
          }
        }
      }
    }
  }
  if (dojo.byId('paramLayoutScreen') && dojo.byId('paramLayoutScreen').value != 'multiple') return;
  if (waitingForReply) {
    showInfo(i18n("alertOngoingQuery"));
    return;
  }
  if (checkFormChangeInProgress()) {
    return false;
  }
  dojo.byId('objectClass').value = refType;
  dojo.byId('objectId').value = refId;
  var ctrlPressed = (window.event && (window.event.ctrlKey || window.event.shiftKey)) ? true : false;
  if (ctrlPressed && refType && refId) {
    openInNewWindow(refType, refId);
    return;
  }
  hideList();
  var callBack = function() {
    if (dojo.byId('documentExplorerJsonData')) {
      setActionCoverListNonObj('OPEN', false);
    }
  }
  if (documentExplorerPreviewMode() && coverListAction == 'CLOSE' && !switchedMode && !notShowDetailAfterReplan) {
    /* The shared loader only unfolds a collapsed pane for a record page, so a click
       would fill a closed pane with the preview. The opener takes an address : it
       gets ours. */
    ShowDetailScreen(documentExplorerDetailPage());
  } else {
    loadContent(documentExplorerDetailPage(), 'detailDiv', 'listForm', false, null, null, null, callBack);
  }
  loadContentStream();
  documentExplorerHighlightLine(id);
}

/** Preview mode, from the user option published as a global at page load. */
function documentExplorerPreviewMode() {
  return (typeof documentExplorerPreviewOnClick != 'undefined' && documentExplorerPreviewOnClick == 1);
}

/**
 * One-shot override of the pane, either way. null follows the option, 'detail' or
 * 'apercu' force what is shown, the buttons being offered whatever the option.
 *
 * It holds for the current row only : any click on a row clears it. An internal
 * reselection keeps it, or saving from the record would drop out of it.
 */
var documentExplorerPaneOverride = null;

/** Shows the record of the current object. */
function documentExplorerShowDetail() {
  documentExplorerPaneOverride = 'detail';
  documentExplorerReloadDetailPane();
}

/** Shows the file preview of the current object. */
function documentExplorerShowPreview() {
  documentExplorerPaneOverride = 'apercu';
  documentExplorerReloadDetailPane();
}

/**
 * Page the detail pane loads, the preview or the record. One place decides, so the
 * click, the override and any other reload cannot diverge.
 */
function documentExplorerDetailPage() {
  if (documentExplorerPaneOverride == 'apercu') return 'documentExplorerPreview.php';
  if (documentExplorerPaneOverride != 'detail' && documentExplorerPreviewMode()) {
    return 'documentExplorerPreview.php';
  }
  var vType = (dojo.byId('objectClassManual')) ? dojo.byId('objectClassManual').value : 'DocumentExplorer';
  if (vType == 'PlanningWorkPlan') vType = 'Planning';
  return 'objectDetail.php?planning=true&planningType=' + vType;
}

/**
 * Saves the preview-on-click option, then puts the pane back in step.
 *
 * The pane follows in the load handler, once the save is acknowledged. The global
 * is refreshed by hand, being published only at page load.
 */
function documentExplorerSavePreviewOnClick(value) {
  showWait();
  dojo.xhrPost({
    url: '../tool/saveUserParameter.php?parameter=documentExplorerPreviewOnClick&value=' + value + addTokenIndexToUrl(),
    handleAs: 'text',
    load: function() {
      documentExplorerPreviewOnClick = value;
      documentExplorerReloadDetailPane();
      hideWait();
    },
    error: function() {
      consoleTraceLog('documentExplorerSavePreviewOnClick : echec de l\'enregistrement');
      hideWait();
    }
  });
}

/** Reloads the detail pane in the current mode, if a row is selected. */
function documentExplorerReloadDetailPane() {
  var vDetail = dojo.byId('detailDiv');
  if (! vDetail || vDetail.style.display == 'none') return;
  if (! dojo.byId('objectId') || ! dojo.byId('objectId').value) return;
  loadContent(documentExplorerDetailPage(), 'detailDiv', 'listForm', false);
}
function documentExplorerHighlightLine(id, planningEditMode) {
  if (id == null) id = vGanttCurrentLine;
  if (id < 0) return;
  vGanttCurrentLine = id;
  documentExplorerUnselectLines();
  vTaskList = documentExplorerDirectoryList.getList();
  for (var i = 0; i < vTaskList.length; i++) {
    documentExplorerMouseOut(i);
  }
  if (planningEditMode == undefined) planningEditMode = false;
  var vRowObj1 = JSGantt.findObj('child_' + id);
  if (vRowObj1) {
    if (planningEditMode) {
      dojo.addClass(vRowObj1, "editModeRowSelected");
    } else {
      dojo.addClass(vRowObj1, "dojoxGridRowSelected");
      dojo.removeClass(vRowObj1, "editModeRowSelected");
    }
  }
  var vRowObj2 = JSGantt.findObj('childrow_' + id);
  if (vRowObj2) {
    if (planningEditMode) {
      dojo.addClass(vRowObj2, "editModeRowSelected");
    } else {
      dojo.addClass(vRowObj2, "dojoxGridRowSelected");
      dojo.removeClass(vRowObj2, "editModeRowSelected");
    }
  }
}

function documentExplorerSelectLineByObject(selClass, selId, autoscroll, reopen) {
  if (selClass == undefined && selId == undefined) return;
  if (reopen == undefined) reopen = false;
  var vChart = (typeof documentExplorerListFor == 'function') ? documentExplorerListFor(selClass) : documentExplorerDirectoryList;
  if (!vChart) return;
  vTaskList = vChart.getList();
  var tId = null;
  var idProject = null;
  for (var i = 0; i < vTaskList.length; i++) {
    if (vTaskList[i].getClass() == selClass && vTaskList[i].getId() == selId) {
      tId = vTaskList[i].getID();
      idProject = vTaskList[i].getProjectId();
      break;
    }
  }
  if (tId != null) {
    if (currentRowToEdit == null) currentRowToEdit = tId;
    if (currentRowToEdit != null && currentRowToEdit != -1 && idProject != null) {
      cachedAction = cachedEditRowPlanningClick;
      vGanttCurrentLine = currentRowToEdit;
      /* indexOf() >= 0, not indexOf() alone : a missing string gives -1, which is
         truthy, so the guard would never filter and the remembered click would be
         replayed instead of the one asked for. Only a recall=true click is replayed. */
      if (!reopen && currentRowToEdit == tId && cachedAction && cachedAction.indexOf('true') >= 0) {
        setTimeout(cachedAction, 100);
      } else {
        if (!reopen) {
          setTimeout('JSGantt.planningRowClickAction(\'' + tId + '\', ' + selId + ', \'' + selClass + '\', ' + idProject + ')', 100);
        } else {
          var isEditModeActive = (dojo.byId('editRowMode')) ? dojo.byId('editRowMode').value : false;
          setTimeout('JSGantt.closeAndSelectEditRow(\'' + tId + '\', ' + selId + ', \'' + selClass + '\', ' + idProject + ', ' + isEditModeActive + ', true)', 100);
        }
      }
    } else {
      documentExplorerUnselectLines();
      documentExplorerHighlightLine(tId, false);
      currentRowToEdit = null;
    }
  }
}
function documentExplorerUnselectLines() {
  dojo.query(".dojoxGridRowSelected").forEach(function(node, index, nodelist) {
    dojo.removeClass(node, "dojoxGridRowSelected");
  });
  dojo.query(".editModeRowSelected").forEach(function(node, index, nodelist) {
    dojo.removeClass(node, "editModeRowSelected");
  });
}

function documentExplorerGetVisibleIndex(lineId, chart) {
  if (!chart || !chart.getList) return null;
  var taskList = chart.getList();
  var visibleIndex = 0;
  for (var i = 0; i < taskList.length; i++) {
    var task = taskList[i];
    if (!task) continue;
    if (task.getID() == lineId) return visibleIndex;
    if (task.getVisible() == 1) visibleIndex++;
  }
  return null;
}

function documentExplorerOpenParents(lineId, chart) {
  if (!chart || !chart.getLineByID) return false;
  var task = chart.getLineByID(lineId);
  if (!task) return false;
  var parentIds = [];
  var parentId = task.getParent();
  while (parentId) {
    var parentTask = chart.getLineByID(parentId);
    if (!parentTask) break;
    parentIds.unshift(parentId);
    parentId = parentTask.getParent();
  }
  var opened = false;
  for (var i = 0; i < parentIds.length; i++) {
    var currentParent = chart.getLineByID(parentIds[i]);
    if (currentParent && currentParent.getGroup && currentParent.getGroup() && currentParent.getOpen && currentParent.getOpen() != 1) {
      documentExplorerFolder(parentIds[i], chart, true);
      opened = true;
    }
  }
  if (opened && typeof documentExplorerShowVisibleLines == 'function') documentExplorerShowVisibleLines();
  return opened;
}

function documentExplorerListHolding(lineId) {
  if (documentExplorerDocumentList && documentExplorerDocumentList.getLineByID && documentExplorerDocumentList.getLineByID(lineId)) return documentExplorerDocumentList;
  if (documentExplorerDirectoryList && documentExplorerDirectoryList.getLineByID && documentExplorerDirectoryList.getLineByID(lineId)) return documentExplorerDirectoryList;
  return null;
}

function documentExplorerSelectLineWhenReady(lineId, chart, retries, label) {
  if (retries == undefined) retries = 15;
  if (!label) label = 'documentExplorer';
  var vChart = chart || documentExplorerListHolding(lineId);
  var task = (vChart && vChart.getLineByID) ? vChart.getLineByID(lineId) : null;
  if (!task) {
    vChart = documentExplorerListHolding(lineId);
    task = (vChart) ? vChart.getLineByID(lineId) : null;
  }
  if (!task) {
    if (retries > 0) {
      setTimeout(function(){ documentExplorerSelectLineWhenReady(lineId, chart, retries - 1, label); }, 100);
    } else {
      consoleTraceLog(label + ' : ligne ' + lineId + ' absente des deux listes apres 1500 ms');
    }
    return;
  }
  documentExplorerOpenParents(lineId, vChart);
  var visibleIndex = documentExplorerGetVisibleIndex(lineId, vChart);
  var container = dojo.byId((vChart === documentExplorerDocumentList) ? 'rightGanttChartDIV' : 'leftGanttChartDIV');
  if (container && visibleIndex !== null) {
    var newPos = (visibleIndex * 21) - (container.offsetHeight / 2) + 10;
    container.scrollTop = (newPos < 0) ? 0 : newPos;
    if (typeof documentExplorerShowVisibleLines == 'function') documentExplorerShowVisibleLines();
  }
  setTimeout(function(){
    if (vChart.getArrayLocationByID && typeof documentExplorerShowOneLine == 'function') {
      var lineIndex = vChart.getArrayLocationByID(lineId);
      if (lineIndex !== null && !dojo.byId('childrow_' + lineId)) {
        documentExplorerShowOneLine(lineIndex, lineId, vChart);
      }
    }
    documentExplorerUnselectLines();
    documentExplorerCurrentEditList = vChart;
    var vRefClass  = task.getClass();
    var vRefId     = task.getId();
    var vIdProject = task.getProjectId();
    var vOpenDetail = (documentExplorerClickAction == 1)
                   || (coverListAction == 'OPEN')
                   || (typeof switchedMode != 'undefined' && switchedMode && switchedVisible == 'detail');
    JSGantt.selectGanttRowToEdit(lineId);
    if (vOpenDetail) {
      documentExplorerRunScript(vRefClass, vRefId, lineId, true);
    } else {
      JSGantt.editRowObjectPlanning(lineId, vRefId, vRefClass, vIdProject);
    }
  }, 60);
}

/**
 * Opens the pane on this object, in the current mode. Reached from the context menu
 * and from the row button, so it follows the option : in preview mode it shows the
 * preview. Forcing the record is a separate entry.
 */
function documentExplorerOpenObjectFromContextMenu(refType, refId, taskId, idProject) {
  JSGantt.hideMenu();
  JSGantt.closeAndSelectEditRow(taskId, refId, refType, idProject);
  notShowDetailAfterReplan = false;
  documentExplorerRunScript(refType, refId, taskId);
}

/**
 * Close entry of the context menu. The shared close also destroys the inline edit
 * and clears the current line, leaving the row selected until the next mouse move.
 *
 * Closing the pane means neither deselecting nor leaving the edit : the shared close
 * runs as it is, then the row is put back in the state it had.
 */
function documentExplorerCloseObjectFromContextMenu(refType, refId, taskId, idProject) {
  closeObjectFromContextMenu();
  if (! taskId) return;
  documentExplorerHighlightLine(taskId);
  if (JSGantt.editRowObjectPlanning) {
    JSGantt.editRowObjectPlanning(taskId, refId, refType, idProject);
  }
}

/** Show detail entry of the context menu : a one-shot override to the record. */
function documentExplorerShowDetailFromContextMenu(refType, refId, taskId, idProject) {
  JSGantt.hideMenu();
  JSGantt.closeAndSelectEditRow(taskId, refId, refType, idProject);
  notShowDetailAfterReplan = false;
  documentExplorerPaneOverride = 'detail';
  documentExplorerRunScript(refType, refId, taskId, true);
}

function documentExplorerGetSelectedItemsForDelete(refId, refType) {
  var selectedItems = new Array();
  var selectedKeys = new Array();
  var vChart = documentExplorerListFor(refType);
  var vDnd = documentExplorerDndSourceFor(refType);
  if (!vDnd || !vDnd.getSelectedNodes || !vChart || !vChart.getLineByID) {
    return selectedItems;
  }
  vDnd.getSelectedNodes().forEach(function(node) {
    if (!node || !node.id || node.id.indexOf('child_') !== 0) return;
    var taskId = node.id.substr(6);
    var task = vChart.getLineByID(taskId);
    if (!task) return;
    var itemRefType = task.getClass();
    var itemRefId = task.getId();
    if (!itemRefType || !itemRefId) return;
    var key = itemRefType + ':' + itemRefId;
    if (selectedKeys.indexOf(key) >= 0) return;
    selectedKeys.push(key);
    selectedItems.push({
      refType:itemRefType,
      refId:itemRefId
    });
  });
  return selectedItems;
}

function documentExplorerDeleteSelectedItemsFromContextMenu(items) {
  if (!items || !items.length) return;
  var selection = '';
  items.forEach(function(item) {
    selection += item.refType + ':' + item.refId + ';';
  });
  var vFormName = documentExplorerListFormNameFor(items[0].refType);
  var form = dojo.byId(vFormName);
  if (!form) return;
  var selectionInput = dojo.byId('documentExplorerDeleteSelection');
  if (!selectionInput) {
    selectionInput = document.createElement('input');
    selectionInput.type = 'hidden';
    selectionInput.id = 'documentExplorerDeleteSelection';
    selectionInput.name = 'selection';
    form.appendChild(selectionInput);
  }
  selectionInput.value = selection;
  loadContent('../tool/deletePlanningSelection.php', 'resultDivMain', vFormName, false, null, null, null, function() {
    fromContextMenu = false;
    var deleteFailureMessages = new Array();
    dojo.query('#resultDivMain table tr').forEach(function(row) {
      var statusNode = row.querySelector('.messageERROR, .messageWARNING, .messageNO_CHANGE');
      if (!statusNode) return;
      var status = statusNode.className.indexOf('messageERROR') >= 0
        ? 'ERROR'
        : (statusNode.className.indexOf('messageWARNING') >= 0 ? 'WARNING' : 'NO_CHANGE');
      deleteFailureMessages.push({
        status:status,
        message:row.textContent.replace(/\s+/g, ' ').trim()
      });
    });
    var resultNodes = [
      dojo.byId('summaryResult'),
      dojo.byId('needProjectListRefresh')
    ].filter(function(node) {
      return node;
    });
    resultNodes.forEach(function(node) {
      form.appendChild(node);
    });
    finalizeMultipleSave();
    var resultDiv = dojo.byId('resultDivMain');
    deleteFailureMessages.forEach(function(deleteFailure) {
      var messageNode = document.createElement('div');
      messageNode.className = 'message' + deleteFailure.status;
      messageNode.textContent = deleteFailure.message;
      resultDiv.appendChild(messageNode);
      addMessage(deleteFailure.message);
    });
    resultNodes.forEach(function(node) {
      dojo.destroy(node);
    });
    showWait();
    documentExplorerRefreshExplorer();
  });
}

function documentExplorerDeleteObjectFromContextMenu(refId, refType, viewObjectList) {
  fromContextMenu = true;
  if (viewObjectList == false) {
    hideDetailScreen();
    JSGantt.closeEditRowObjectPlanning();
  }
  var selectedItems = documentExplorerGetSelectedItemsForDelete(refId, refType);
  if (selectedItems.length > 1) {
    showConfirm(i18n('confirmDeleteMultiplePlanning'), function() {
      documentExplorerDeleteSelectedItemsFromContextMenu(selectedItems);
    });
    return;
  }
  var action = function() {
    var resetContextMenuVariable = function() {
      if (!(dojo.byId('confirmControl') && dojo.byId('confirmControl').value == 'delete')) {
        fromContextMenu = false;
      }
    }
    dojo.byId('objectClass').value = refType;
    dojo.byId('objectId').value = refId;
    loadContent('../tool/deleteObject.php?objectId=' + refId
      + '&objectClassName=' + refType + '&fromContextMenu=' + fromContextMenu, 'resultDivMain', 'objectForm', true, null, null, null, resetContextMenuVariable);
  };
  showConfirm(i18n('confirmDelete', new Array(refType, refId)), action);
}

/**
 * Draws the screen. The shell hooks this too, some entry paths passing no callback,
 * so the flag lives on the container, recreated on every visit.
 */
function explorerInit() {
  var container = dojo.byId('mainDivContainer');
  if (container) {
    if (container.documentExplorerInitialised) return;
    container.documentExplorerInitialised = true;
  }
  documentExplorerDraw();
}

/**
 * Reloads the whole screen, as the menu does. Called when the scope changes, a
 * project or a favourite list. Reloading the list alone would leave the detail pane
 * open on a document now out of scope, and would not trigger the drawing.
 */
function documentExplorerReloadScreen() {
  if (typeof JSGantt != 'undefined' && JSGantt.closeEditRowObjectPlanning) {
    JSGantt.closeEditRowObjectPlanning();
  }
  if (dojo.byId('objectId')) dojo.byId('objectId').value = '';
  loadContent('documentExplorerMain.php', 'centerDiv', null, null, null, null, null, explorerInit);
}

var documentExplorerSelectedDirectory = null;

function documentExplorerApplyDirectory(refId, afterDraw, force) {
  if (!refId) return;
  if (!force && documentExplorerSelectedDirectory == refId) {
    if (typeof afterDraw === 'function') afterDraw();
    return;
  }
  documentExplorerSelectedDirectory = refId;
  saveDataToSession('Directory', refId, false, function(){
    documentExplorerRefreshDocuments(afterDraw);
  });
}

function documentExplorerRefreshDocuments(afterDraw) {
  refreshJsonDocumentExplorerInProgress = true;
  dojo.xhrGet({
    url: '../tool/jsonDocumentExplorer.php?refresh=' + (new Date()).getTime() + addTokenIndexToUrl(),
    handleAs: 'text',
    load: function(data) {
      var store;
      try {
        store = JSON.parse(dojo.trim(data));
      } catch (e) {
        consoleTraceLog('documentExplorerRefreshDocuments : JSON illisible');
        refreshJsonDocumentExplorerInProgress = false;
        return;
      }
      var items = (store.documents && store.documents.items) ? store.documents.items : [];
      if (!documentExplorerDocumentList) {
        refreshJsonDocumentExplorerInProgress = false;
        return;
      }
      documentExplorerDocumentList.ClearList();
      for (var i = 0; i < items.length; i++) {
        documentExplorerDocumentList.AddTaskItem(new DocumentExplorerItem(items[i], 'document'));
      }
      documentExplorerDocumentList.Draw();
      documentExplorerShowLines(documentExplorerDocumentList);
      documentExplorerBindHeaderDnd();
      documentExplorerBindDropGuard();
      documentExplorerRefreshDocumentPath();
      documentExplorerMarkCurrentDirectory();
      refreshJsonDocumentExplorerInProgress = false;
      if (typeof afterDraw === 'function') afterDraw();
    },
    error: function() {
      refreshJsonDocumentExplorerInProgress = false;
      consoleTraceLog('documentExplorerRefreshDocuments : echec du chargement');
    }
  });
}

/* Rafraichissements complets en attente : voir documentExplorerRefreshExplorer(). */
var documentExplorerFullRefreshInProgress = false;
var documentExplorerRefreshWaiting = [];

function documentExplorerDrainRefreshWaiting() {
  var vList = documentExplorerRefreshWaiting;
  documentExplorerRefreshWaiting = [];
  for (var i = 0; i < vList.length; i++) {
    try { vList[i](); } catch (e) { consoleTraceLog('documentExplorerRefreshExplorer : rappel en echec'); }
  }
}

function documentExplorerRefreshExplorer(afterDraw) {
  var jsonData = dojo.byId('documentExplorerJsonData');
  if (!jsonData) {
    hideWait();
    return;
  }
  /* A save triggers two refreshes. The first closes the inline edit and clears the
     current line, so the second captures no row to reselect and, drawing last, would
     undo what the first restored. The first is served, the second only queues. */
  if (documentExplorerFullRefreshInProgress) {
    if (typeof afterDraw === 'function') documentExplorerRefreshWaiting.push(afterDraw);
    return;
  }
  documentExplorerFullRefreshInProgress = true;
  /* Captured before the close, which clears both variables. The fallback covers a
     row selected with no inline edit open, as when saving from the detail. A caller
     passing a callback already aims at a row : one selection per refresh. */
  var vRowToReselect = null;
  if (typeof afterDraw !== 'function') {
    if (typeof currentRowToEdit != 'undefined' && currentRowToEdit) {
      vRowToReselect = currentRowToEdit;
    } else if (typeof vGanttCurrentLine != 'undefined' && vGanttCurrentLine) {
      vRowToReselect = vGanttCurrentLine;
    }
    /* After a creation the row to aim at is the new object, not the one captured,
       which was the directory it was created in. The save response carries its id,
       and a document row id takes a d prefix where a directory takes none. */
    var vLastOperation = dojo.byId('lastOperation');
    var vLastSaveId    = dojo.byId('lastSaveId');
    var vSavedClass    = dojo.byId('objectClass');
    if (vLastOperation && vLastOperation.value == 'insert'
     && vLastSaveId && vLastSaveId.value && vSavedClass && vSavedClass.value) {
      vRowToReselect = ((vSavedClass.value == 'Document') ? 'd' : '') + vLastSaveId.value;
      /* A new object shows its record, not its preview, which has no file yet. The
         override is one-shot, the next click gives the option back the last word. */
      documentExplorerPaneOverride = 'detail';
    }
  }
  if (currentRowToEdit && JSGantt.closeEditRowObjectPlanning) {
    JSGantt.closeEditRowObjectPlanning();
  }
  refreshJsonDocumentExplorerInProgress = true;
  dojo.xhrGet({
    url: '../tool/jsonDocumentExplorer.php?refresh=' + (new Date()).getTime() + addTokenIndexToUrl(),
    handleAs: 'text',
    load: function(data) {
      var payload = dojo.trim(data);
      try {
        JSON.parse(payload);
      } catch (e) {
        consoleTraceLog('documentExplorerRefreshExplorer : JSON illisible');
        consoleTraceLog(payload.substring(0, 400));
        refreshJsonDocumentExplorerInProgress = false;
        documentExplorerFullRefreshInProgress = false;
        documentExplorerRefreshWaiting = [];
        hideWait();
        return;
      }
      jsonData.innerHTML = payload;
      refreshJsonDocumentExplorerInProgress = false;
      documentExplorerDraw();
      hideWait();
      documentExplorerFullRefreshInProgress = false;
      if (vRowToReselect) {
        documentExplorerSelectLineWhenReady(vRowToReselect, null, 15, 'documentExplorer apres rafraichissement');
      }
      if (typeof afterDraw === 'function') afterDraw();
      documentExplorerDrainRefreshWaiting();
    },
    error: function() {
      refreshJsonDocumentExplorerInProgress = false;
      documentExplorerFullRefreshInProgress = false;
      documentExplorerRefreshWaiting = [];
      consoleTraceLog('documentExplorerRefreshExplorer : echec du chargement');
      hideWait();
    }
  });
}

/**
 * Saves the show-closed option, then redraws. The redraw reads the parameter back
 * from the server, so it must start once the save is acknowledged : firing both at
 * once leaves their order open and would show the previous state.
 *
 * Tree and document list both change : a full refresh.
 */
function documentExplorerSaveShowClosed(value) {
  showWait();
  dojo.xhrPost({
    url: '../tool/saveUserParameter.php?parameter=documentExplorerShowClosed&value=' + value + addTokenIndexToUrl(),
    handleAs: 'text',
    load: function() {
      documentExplorerRefreshExplorer();
    },
    error: function() {
      consoleTraceLog('documentExplorerSaveShowClosed : echec de l\'enregistrement');
      hideWait();
    }
  });
}

function documentExplorerListForType(explorerType) {
  return (explorerType == 'document') ? documentExplorerDocumentList : documentExplorerDirectoryList;
}

function documentExplorerApplyColumnDescription(store) {
  if (!store || !store.columns) return;
  var explorerType = store.type || 'directory';
  var idx = getIndiceForPlanningType(explorerType);
  documentExplorerColumnOrder[idx] = new Array();
  store.columns.forEach(function(col, i){
    setPlanningFieldShow(col.name, (col.show == 1), explorerType);
    setPlanningFieldWidth(col.name, col.width, explorerType);
    setPlanningFieldMinWidth(col.name, col.minWidth, explorerType);
    if (col.label) documentExplorerSetFieldLabel(col.name, col.label, explorerType);
    setPlanningFieldOrder(col.name, i, explorerType);
    documentExplorerColumnOrder[idx][i] = col.name;
  });
}

function documentExplorerColumnAction(explorerType, params, afterApply, applyStore) {
  var url = '../tool/documentExplorerColumnAction.php?explorerType=' + explorerType
          + params + addTokenIndexToUrl();
  dojo.xhrGet({
    url: url,
    handleAs: 'text',
    load: function(data) {
      var store = null;
      try {
        store = JSON.parse(dojo.trim(data));
      } catch (e) {
        consoleTraceLog('documentExplorerColumnAction : JSON illisible');
        consoleTraceLog(dojo.trim(data).substring(0, 400));
        return;
      }
      if (applyStore) documentExplorerApplyColumnDescription(store);
      if (typeof afterApply === 'function') afterApply(store);
    },
    error: function(err, ioargs) {
      var vStatus = (ioargs && ioargs.xhr) ? ioargs.xhr.status : '?';
      consoleTraceLog('documentExplorerColumnAction : echec de l\'enregistrement (HTTP ' + vStatus + ') ' + url);
    }
  });
}

var documentExplorerColumnSyncInProgress = false;

function documentExplorerChangeColumn(col, status, explorerType) {
  if (documentExplorerColumnSyncInProgress) return;
  setPlanningFieldShow(col, status, explorerType);
  var spinner = dijit.byId('documentExplorerColumnWidth' + explorerType + col);
  if (spinner) spinner.set('disabled', !status);
  documentExplorerColumnAction(explorerType,
    '&action=status&item=' + col + '&status=' + ((status) ? 'visible' : 'hidden'));
}

function documentExplorerChangeColumnWidth(col, width, explorerType) {
  if (documentExplorerColumnSyncInProgress) return;
  setPlanningFieldWidth(col, width, explorerType);
  documentExplorerColumnAction(explorerType,
    '&action=width&item=' + col + '&width=' + width,
    function(){ documentExplorerRedrawList(explorerType); });
}

function documentExplorerSaveColumnOrder(explorerType) {
  var source = window['dndDocumentExplorerColumnSelector' + explorerType];
  if (!source || !source.getAllNodes) return;
  var prefix = 'documentExplorerColumnSelector' + explorerType;
  var idx = getIndiceForPlanningType(explorerType);
  var list = 'Name|';
  var order = ['Name'];
  source.getAllNodes().forEach(function(node){
    if (!node.id || node.id.indexOf(prefix) !== 0) return;
    var col = node.id.substr(prefix.length);
    if (col == 'Name') return;
    var check = dijit.byId('documentExplorerCheckColumn' + explorerType + col);
    var hidden = (check && !check.get('checked')) ? 'hidden' : '';
    list += hidden + col + '|';
    order.push(col);
  });
  if (order.length > 1) {
    documentExplorerColumnOrder[idx] = order;
    order.forEach(function(col, i){ setPlanningFieldOrder(col, i, explorerType); });
  }
  documentExplorerColumnAction(explorerType, '&action=order&orderedList=' + encodeURIComponent(list),
    function(){ documentExplorerRedrawList(explorerType); });
}

function documentExplorerBindColumnDnd() {
  ['directory','document'].forEach(function(explorerType){
    var source = window['dndDocumentExplorerColumnSelector' + explorerType];
    if (!source || source._documentExplorerBound) return;
    source._documentExplorerBound = true;
    dojo.connect(source, 'onDndDrop', null, function(src, nodes, copy, target){
      if (target !== source) return;
      setTimeout(function(){ documentExplorerSaveColumnOrder(explorerType); }, 10);
    });
  });
}

function documentExplorerRedrawList(explorerType) {
  var chart = documentExplorerListForType(explorerType);
  if (!chart) return;
  /* Captured before the close, which clears the current line : the redraw that
     follows rebuilds the rows without their highlight. */
  var vSelected = (typeof vGanttCurrentLine != 'undefined' && vGanttCurrentLine) ? vGanttCurrentLine : null;
  JSGantt.closeEditRowObjectPlanning();
  documentExplorerSetColumnsVisibility(chart, explorerType);
  chart.Draw();
  documentExplorerShowLines(chart);
  documentExplorerBindHeaderDnd();
  documentExplorerBindDropGuard();
  documentExplorerRefreshDocumentPath();
  documentExplorerMarkCurrentDirectory();
  /* Highlight only : a column change leaves the detail pane alone. */
  if (vSelected) documentExplorerHighlightLine(vSelected);
  hideWait();
}

function documentExplorerValidateColumns() {
  if (dijit.byId('documentExplorerColumnSelector')) dijit.byId('documentExplorerColumnSelector').closeDropDown();
  showWait();
  documentExplorerRedrawList('directory');
  documentExplorerRedrawList('document');
  hideWait();
}

function documentExplorerResetColumns() {
  var actionOK = function() {
    showWait();
    var done = 0;
    var after = function(store) {
      documentExplorerSyncColumnSelectorWidgets(store);
      done++;
      if (done == 2) documentExplorerValidateColumns();
    };
    documentExplorerColumnAction('directory', '&action=reset', after, true);
    documentExplorerColumnAction('document',  '&action=reset', after, true);
  };
  showConfirm(i18n('confirmResetList'), actionOK);
}

function documentExplorerSyncColumnSelectorWidgets(store) {
  if (!store || !store.columns) return;
  var explorerType = store.type || 'directory';
  documentExplorerColumnSyncInProgress = true;
  try {
    store.columns.forEach(function(col){
      var check = dijit.byId('documentExplorerCheckColumn' + explorerType + col.name);
      if (check) check.set('checked', (col.show == 1));
      var swtch = dijit.byId('documentExplorerCheckColumn' + explorerType + col.name + 'Sw');
      if (swtch) swtch.set('value', (col.show == 1) ? 'on' : 'off');
      var spinner = dijit.byId('documentExplorerColumnWidth' + explorerType + col.name);
      if (spinner) {
        spinner.set('value', col.width);
        spinner.set('disabled', (col.show != 1));
      }
    });
  } finally {
    documentExplorerColumnSyncInProgress = false;
  }
}

var documentExplorerIsResizingHeaderColumn = false;
var documentExplorerResizerHeaderColumnEventIsInit = false;

function documentExplorerPrefixForType(explorerType) {
  var chart = documentExplorerListForType(explorerType);
  return (chart && chart.getIdPrefix) ? chart.getIdPrefix() : '';
}

function documentExplorerHandleResizeHeaderColumn(column, minWidth, incrementWidth, explorerType) {
  if (documentExplorerIsResizingHeaderColumn) return;
  if (!explorerType) explorerType = 'directory';
  var prefix = documentExplorerPrefixForType(explorerType);
  var columnDiv = dojo.byId(prefix + 'jsGanttHeader' + column);
  var resizer = dojo.byId(prefix + column + 'ColumnResizer');
  var resizerIndicator = dojo.byId(prefix + column + 'ColumnResizerIndicator');
  if (!columnDiv || !resizer || !resizerIndicator) return;
  var width = 0, left = 0, startX, startLeft, startWidth, maxWidth = 500;

  resizer.addEventListener('mousedown', initDrag, false);

  function initDrag(e) {
    e.preventDefault();
    if (documentExplorerResizerHeaderColumnEventIsInit) return;
    documentExplorerResizerHeaderColumnEventIsInit = true;
    resizerIndicator.style.display = '';
    startX = e.clientX;
    startLeft = columnDiv.offsetLeft;
    startWidth = parseInt(document.defaultView.getComputedStyle(columnDiv).width, 10);
    document.documentElement.addEventListener('mousemove', doDrag, false);
    document.documentElement.addEventListener('mouseup', stopDrag, false);
  }

  function doDrag(e) {
    documentExplorerIsResizingHeaderColumn = true;
    left = (Math.ceil((startLeft + startWidth + (e.clientX - startX)) / incrementWidth) * incrementWidth < startLeft)
         ? startLeft + incrementWidth
         : Math.ceil((startLeft + startWidth + (e.clientX - startX)) / incrementWidth) * incrementWidth;
    resizerIndicator.style.left = (left - 2) + 'px';
    width = (Math.ceil((startWidth + e.clientX - startX) / incrementWidth) * incrementWidth > incrementWidth)
          ? Math.ceil((startWidth + e.clientX - startX) / incrementWidth) * incrementWidth
          : incrementWidth;
    if (width < minWidth) width = minWidth;
    if (width > maxWidth) width = maxWidth;
    columnDiv.style.width = width + 'px';
  }

  function stopDrag(e) {
    resizerIndicator.style.display = 'none';
    document.documentElement.removeEventListener('mouseup', stopDrag, false);
    resizer.removeEventListener('mousedown', initDrag, false);
    document.documentElement.removeEventListener('mousemove', doDrag, false);
    if (width) {
      var spinner = dijit.byId('documentExplorerColumnWidth' + explorerType + column);
      if (spinner) {
        documentExplorerColumnSyncInProgress = true;
        try { spinner.set('value', width); } finally { documentExplorerColumnSyncInProgress = false; }
      }
      documentExplorerChangeColumnWidth(column, width, explorerType);
    }
    setTimeout('documentExplorerIsResizingHeaderColumn=false;', 150);
    setTimeout('documentExplorerResizerHeaderColumnEventIsInit=false;', 150);
  }
}

function documentExplorerToggleColumnList() {
  if (typeof event != 'undefined' && event) event.preventDefault();
  if (dijit.byId('documentExplorerColumnSelector')) dijit.byId('documentExplorerColumnSelector').toggleDropDown();
}

function documentExplorerBindHeaderDnd() {
  ['directory','document'].forEach(function(explorerType){
    var prefix = documentExplorerPrefixForType(explorerType);
    var source = window[prefix + 'dndDocumentExplorerHeaderColumn'];
    if (!source || source._documentExplorerBound) return;
    source._documentExplorerBound = true;
    dojo.connect(source, 'onDndDrop', null, function(src, nodes, copy, target){
      if (target !== source) return;
      setTimeout(function(){ documentExplorerSaveHeaderColumnOrder(explorerType); }, 10);
    });
  });
}

function documentExplorerSaveHeaderColumnOrder(explorerType) {
  var prefix = documentExplorerPrefixForType(explorerType);
  var source = window[prefix + 'dndDocumentExplorerHeaderColumn'];
  if (!source || !source.getAllNodes) return;
  var head = prefix + 'jsGanttHeaderTD';
  var visible = new Array();
  source.getAllNodes().forEach(function(node){
    if (!node.id || node.id.indexOf(head) !== 0) return;
    var col = node.id.substr(head.length);
    if (col && col != 'Name') visible.push(col);
  });
  if (!visible.length) return;
  var idx = getIndiceForPlanningType(explorerType);
  var list = 'Name|';
  var order = ['Name'];
  visible.forEach(function(col){ list += col + '|'; order.push(col); });
  (documentExplorerColumnOrder[idx] || []).forEach(function(col){
    if (col == 'Name' || visible.indexOf(col) >= 0) return;
    list += 'hidden' + col + '|';
    order.push(col);
  });
  documentExplorerColumnOrder[idx] = order;
  order.forEach(function(col, i){ setPlanningFieldOrder(col, i, explorerType); });
  documentExplorerColumnAction(explorerType, '&action=order&orderedList=' + encodeURIComponent(list),
    function(){ documentExplorerRedrawList(explorerType); });
}

(function(){
  if (typeof refreshJsonList != 'function' || refreshJsonList.documentExplorerBridge) return;
  var vOriginal = refreshJsonList;
  var vBridge = function(className, keepUrl) {
    var vOnExplorer = dojo.byId('objectClassManual')
                   && dojo.byId('objectClassManual').value == 'DocumentExplorer';
    if (vOnExplorer && !dijit.byId('objectGrid')) {
      showWait();
      documentExplorerRefreshExplorer();
      return;
    }
    return vOriginal.apply(this, arguments);
  };
  vBridge.documentExplorerBridge = true;
  refreshJsonList = vBridge;
})();

(function(){
  if (typeof switchModeLayout != 'function' || switchModeLayout.documentExplorerBridge) return;
  var vOriginal = switchModeLayout;
  var vBridge = function(paramToSend, notGlobal) {
    var vOnExplorer = dojo.byId('objectClassManual')
                   && dojo.byId('objectClassManual').value == 'DocumentExplorer';
    if (!vOnExplorer) return vOriginal.apply(this, arguments);
    if (checkFormChangeInProgress()) return;

    var vParamDiv = null;
    if (paramToSend == 'top' || paramToSend == 'left' || paramToSend == 'multiple') {
      vParamDiv = (notGlobal) ? 'paramScreen_DocumentExplorer' : 'paramScreen';
    } else if (paramToSend == 'bottom' || paramToSend == 'trailing') {
      vParamDiv = (notGlobal) ? 'paramRightDiv_DocumentExplorer' : 'paramRightDiv';
    } else if (paramToSend == 'col' || paramToSend == 'tab') {
      vParamDiv = 'paramLayoutObjectDetail';
    } else {
      return;
    }

    var vUrl = 'documentExplorerMain.php?' + vParamDiv + '=' + paramToSend
             + ((notGlobal) ? '&notGlobal=true' : '&notGlobal=false');

    loadContent(vUrl, 'centerDiv', null, null, null, null, null, explorerInit);
    if (!notGlobal) {
      loadDiv('menuUserScreenOrganization.php?currentScreen=DocumentExplorer&'
              + vParamDiv + '=' + paramToSend, 'mainDivMenu');
    }
    if (dijit.byId('iconMenuUserScreen'))    dijit.byId('iconMenuUserScreen').closeDropDown();
    if (dijit.byId('menuLayoutScreenButton'))dijit.byId('menuLayoutScreenButton').closeDropDown();
  };
  vBridge.documentExplorerBridge = true;
  switchModeLayout = vBridge;
})();

function documentExplorerIsEditRowActive() {
  return (dojo.byId('objectClassManual')
       && dojo.byId('objectClassManual').value == 'DocumentExplorer'
       && dojo.byId('editRowMode') && dojo.byId('editRowMode').value == 'true'
       && isEditRowFinishDisplay) ? true : false;
}

function documentExplorerPressEditRowSave() {
  var selectFieldOpen = false;
  dojo.query('.ganttEditableField .dijitHasDropDownOpen').forEach(function(node){
    if (node) selectFieldOpen = true;
  });
  if (selectFieldOpen) return false;
  if (!dijit.byId('buttonEditRowSave')) return false;
  JSGantt.saveEditRowObject(true, null);
  return true;
}

(function(){
  if (typeof globalSave == 'function' && !globalSave.documentExplorerBridge) {
    var vOriginalSave = globalSave;
    var vBridgeSave = function() {
      if (documentExplorerIsEditRowActive() && documentExplorerPressEditRowSave()) return;
      return vOriginalSave.apply(this, arguments);
    };
    vBridgeSave.documentExplorerBridge = true;
    globalSave = vBridgeSave;
  }
  if (typeof inlineSave == 'function' && !inlineSave.documentExplorerBridge) {
    var vOriginalInline = inlineSave;
    var vBridgeInline = function() {
      if (documentExplorerIsEditRowActive() && documentExplorerPressEditRowSave()) return;
      return vOriginalInline.apply(this, arguments);
    };
    vBridgeInline.documentExplorerBridge = true;
    inlineSave = vBridgeInline;
  }
})();

document.addEventListener('keydown', function(event){
    if (!event) return;
    if (typeof dojo == 'undefined') return;
    if (!dojo.byId('objectClassManual')
        || dojo.byId('objectClassManual').value != 'DocumentExplorer') return;
    if (!currentRowToEdit || !focusEditRowLine) return;
    if (event.keyCode == 27) {
      if (dojo.byId('objectIdRow') && dojo.byId('objectClassName') && dojo.byId('idProjectRow')) {
        JSGantt.closeAndSelectEditRow(currentRowToEdit,
                                    dojo.byId('objectIdRow').value,
                                    dojo.byId('objectClassName').value,
                                    dojo.byId('idProjectRow').value);
      } else {
        JSGantt.closeEditRowObjectPlanning();
      }
    } else if (event.keyCode == 13) {
      if (isEditRowFinishDisplay) {
        documentExplorerPressEditRowSave();
      } else if (dojo.byId('objectIdRow') && dojo.byId('objectClassName') && dojo.byId('idProjectRow')) {
        var refClass = dojo.byId('objectClassName').value;
        JSGantt.planningRowClickAction(currentRowToEdit,
                                     dojo.byId('objectIdRow').value,
                                     refClass,
                                     dojo.byId('idProjectRow').value, false);
      }
    }
});

(function(){
  if (typeof saveDataToSession != 'function' || saveDataToSession.documentExplorerBridge) return;
  var vOriginal = saveDataToSession;
  var vBridge = function(param, value, saveUserParameter, callBack) {
    var vOnExplorer = dojo.byId('objectClassManual')
                   && dojo.byId('objectClassManual').value == 'DocumentExplorer';
    if (vOnExplorer && typeof param == 'string' && param.indexOf('listSort_') === 0) {
      var vInner = callBack;
      callBack = function() {
        resetResponse = '0';
        if (vInner) vInner();
      };
    }
    return vOriginal.call(this, param, value, saveUserParameter, callBack);
  };
  vBridge.documentExplorerBridge = true;
  saveDataToSession = vBridge;
})();

(function(){
  if (typeof loadContent != 'function' || loadContent.documentExplorerBridge) return;
  var vOriginal = loadContent;
  var vBridge = function(page, destination, formName, isResultMessage, validationType,
                         directAccess, silent, callBackFunction, noFading) {
    var vOnExplorer = dojo.byId('objectClassManual')
                   && dojo.byId('objectClassManual').value == 'DocumentExplorer';
    if (!vOnExplorer || typeof page != 'string') return vOriginal.apply(this, arguments);

    if (destination == 'listDiv' && page.indexOf('objectList.php') >= 0) {
      documentExplorerRefreshExplorer();
      return;
    }

    if (destination != 'directFilterList') return vOriginal.apply(this, arguments);

    var vPage = page;
    if (vPage.indexOf('selectStoredFilter.php') >= 0) {
      vPage = vPage.replace('selectStoredFilter.php', 'documentExplorerStoredFilter.php');
    } else if (vPage.indexOf('displayFilterList.php') >= 0) {
      vPage = vPage.replace('displayQuickFilter=true&', '').replace('&displayQuickFilter=true', '');
    } else {
      return vOriginal.apply(this, arguments);
    }
    /* Every kind of filter return, not only the skipRefresh ones. The others count
       on a shared dispatch that has no branch for this screen and ends on a refresh
       which returns at once : nobody refreshes, so there is no risk of doing it twice. */
    if (validationType == 'skipRefresh'
        || (typeof validationType == 'string' && validationType.indexOf('returnFromFilter') === 0)) {
      var vInner = callBackFunction;
      callBackFunction = function() {
        if (vInner) vInner();
        documentExplorerRefreshExplorer();
      };
    }
    return vOriginal.call(this, vPage, destination, formName, isResultMessage, validationType,
                          directAccess, silent, callBackFunction, noFading);
  };
  vBridge.documentExplorerBridge = true;
  loadContent = vBridge;
})();

/** Is the drop target one of our three sources ? */
function documentExplorerIsOurDndTarget(target) {
  if (! target || ! target.id) return false;
  if (target.id == 'documentExplorerRootDropZone') return true;
  var vTree = documentExplorerDndSourceFor('DocumentDirectory');
  var vDocs = documentExplorerDndSourceFor('Document');
  if (vTree && vTree.node && target.id == vTree.node.id) return true;
  if (vDocs && vDocs.node && target.id == vDocs.node.id) return true;
  return false;
}

/** Which row is this ? The "d" prefix of document ids is never parsed : reftype
 *  and refid are read from the item itself. */
function documentExplorerRowRef(rowNodeId) {
  if (! rowNodeId || rowNodeId.indexOf('child_') !== 0) return null;
  var vId = rowNodeId.substring(6);
  var vLists = [documentExplorerListFor('DocumentDirectory'),
                documentExplorerListFor('Document')];
  for (var i = 0; i < vLists.length; i++) {
    var vChart = vLists[i];
    if (! vChart || ! vChart.getLineByID) continue;
    var vLine = vChart.getLineByID(vId);
    if (vLine) {
      return {rowId:vId, refType:vLine.getClass(), refId:vLine.getId()};
    }
  }
  return null;
}

/** Where does the drop land ? null means this is not a move. */
function documentExplorerDropTarget(target) {
  if (target.id == 'documentExplorerRootDropZone') return {mode:'root'};
  var vTree = documentExplorerDndSourceFor('DocumentDirectory');
  if (! vTree || ! vTree.node || target.id != vTree.node.id) return null;
  if (! target.current || ! target.current.id) return null;
  var vRef = documentExplorerRowRef(target.current.id);
  if (! vRef || vRef.refType != 'DocumentDirectory') return null;
  return {mode:'directory', id:vRef.refId};
}

/**
 * Path of the current directory, "Product > Conception".
 *
 * Built in memory, without a server call : starts from the selected directory
 * and walks up the parents. No root crumb.
 */
function documentExplorerDocumentPathCrumbs() {
  if (! documentExplorerSelectedDirectory) return [];
  var vChart = documentExplorerListFor('DocumentDirectory');
  if (! vChart || ! vChart.getList) return [];
  var vList = vChart.getList();
  if (! vList) return [];
  var vById = {};
  for (var i = 0; i < vList.length; i++) vById[vList[i].getID()] = vList[i];
  var vCurrent = vById[documentExplorerSelectedDirectory];
  if (! vCurrent) {
    for (var j = 0; j < vList.length; j++) {
      if (vList[j].getId() == documentExplorerSelectedDirectory) { vCurrent = vList[j]; break; }
    }
  }
  var vCrumbs = [];
  var vDepth = 0;
  while (vCurrent && vDepth < 100) {
    vCrumbs.unshift({rowId:vCurrent.getID(), refId:vCurrent.getId(), name:vCurrent.getName()});
    var vParent = vCurrent.getParent();
    vCurrent = (vParent) ? vById[vParent] : null;
    vDepth++;
  }
  return vCrumbs;
}

function documentExplorerGoToDirectory(rowId, refId) {
  if (! refId) return;
  documentExplorerApplyDirectory(refId, function() {
    documentExplorerSelectLineWhenReady(rowId, documentExplorerListFor('DocumentDirectory'), 15,
        'documentExplorer depuis le chemin');
  });
}

function documentExplorerRefreshDocumentPath() {
  var vNode = dojo.byId('explorerDocumentPath');
  if (! vNode) return;
  var vCrumbs = documentExplorerDocumentPathCrumbs();
  if (! vCrumbs.length) {
    vNode.innerHTML = '&nbsp;';
    vNode.title = '';
    return;
  }
  var vHtml = '<div class="iconChangeLayout iconSize16 imageColorWhite documentExplorerPathIcon">&nbsp;</div>';
  var vPlain = [];
  for (var i = 0; i < vCrumbs.length; i++) {
    vPlain.push(vCrumbs[i].name);
    if (i) vHtml += '<span class="documentExplorerPathSep">&gt;</span>';
    if (i == vCrumbs.length - 1) {
      vHtml += '<span class="documentExplorerPathCurrent">' + htmlEncode(vCrumbs[i].name) + '</span>';
    } else {
      vHtml += '<span class="link" title="' + htmlEncode(vCrumbs[i].name) + '"'
             + ' onclick="documentExplorerGoToDirectory(\'' + vCrumbs[i].rowId + '\',\''
             + vCrumbs[i].refId + '\');">' + htmlEncode(vCrumbs[i].name) + '</span>';
    }
  }
  vNode.innerHTML = vHtml;
  vNode.title = vPlain.join(' > ');
}

/**
 * Marks the row of the current directory, so the place being worked in stays visible
 * once a document is selected.
 *
 * Its own class, not the selection one, which is cleared as soon as another row is
 * selected and even on hover : selected row and working directory are two states,
 * and they may sit on the same row. The list is walked because the identifier held
 * is that of the object, not of the row.
 */
function documentExplorerMarkCurrentDirectory() {
  dojo.query('.documentExplorerCurrentDirectory').forEach(function(node) {
    dojo.removeClass(node, 'documentExplorerCurrentDirectory');
  });
  if (! documentExplorerSelectedDirectory) return;
  var vChart = documentExplorerListFor('DocumentDirectory');
  if (! vChart || ! vChart.getList) return;
  var vList = vChart.getList();
  if (! vList) return;
  for (var i = 0; i < vList.length; i++) {
    if (! vList[i] || vList[i].getId() != documentExplorerSelectedDirectory) continue;
    var vRowObj1 = JSGantt.findObj('child_' + vList[i].getID());
    if (vRowObj1) dojo.addClass(vRowObj1, 'documentExplorerCurrentDirectory');
    var vRowObj2 = JSGantt.findObj('childrow_' + vList[i].getID());
    if (vRowObj2) dojo.addClass(vRowObj2, 'documentExplorerCurrentDirectory');
    return;
  }
}

/** Is rowId a descendant of ancestorRowId, or that very directory ? */
function documentExplorerIsDescendantOf(rowId, ancestorRowId) {
  var vChart = documentExplorerListFor('DocumentDirectory');
  if (! vChart || ! vChart.getLineByID) return false;
  var vId = rowId, vDepth = 0;
  while (vId && vDepth < 100) {
    if (vId == ancestorRowId) return true;
    var vLine = vChart.getLineByID(vId);
    if (! vLine || ! vLine.getParent) return false;
    vId = vLine.getParent();
    vDepth++;
  }
  return false;
}

/** Is a drop allowed on this row ? Only the cycle is judged here, being the one
 *  refusal decidable without the server, the tree being wholly in memory. Every
 *  other control stays in the model's control(). */
function documentExplorerDropAllowed(nodes, currentNode) {
  if (! nodes || ! currentNode || ! currentNode.id) return true;
  var vTargetRef = documentExplorerRowRef(currentNode.id);
  if (! vTargetRef || vTargetRef.refType != 'DocumentDirectory') return true;
  for (var i = 0; i < nodes.length; i++) {
    var vRef = documentExplorerRowRef(nodes[i].id);
    if (! vRef || vRef.refType != 'DocumentDirectory') continue;
    if (documentExplorerIsDescendantOf(vTargetRef.rowId, vRef.rowId)) return false;
  }
  return true;
}

/**
 * Refuses the gesture itself when it would create a cycle.
 *
 * dojo/dnd/Manager.onMouseUp publishes "/dnd/drop" only when target AND
 * canDropFlag are true, otherwise it publishes "/dnd/cancel". Setting
 * canDrop(false) therefore prevents the drop for real : the node is not moved in
 * the DOM and our handler is never called, so there is nothing to redraw.
 *
 * Hooked after Source.onMouseMove, which has just called m.canDrop() - ours
 * wins. The flag avoids hooking the same instance twice ; dojo.parser builds a
 * new one on every redraw.
 */
function documentExplorerBindDropGuard() {
  var source = documentExplorerDndSourceFor('DocumentDirectory');
  if (! source || source._documentExplorerDropGuard) return;
  source._documentExplorerDropGuard = true;
  dojo.connect(source, 'onMouseMove', null, function(e){
    if (! source.isDragging) return;
    var m = dojo.dnd.manager();
    if (m.target !== source) return;
    if (! documentExplorerDropAllowed(m.nodes, source.current)) {
      m.canDrop(false);
    }
  });
}

/** Rows to move, with the no-op cases dropped. */
function documentExplorerDropItems(nodes, dropTarget) {
  var vItems = [];
  for (var i = 0; i < nodes.length; i++) {
    var vRef = documentExplorerRowRef(nodes[i].id);
    if (! vRef) continue;
    /* Sur soi-meme */
    if (dropTarget.mode == 'directory'
        && vRef.refType == 'DocumentDirectory'
        && vRef.refId == dropTarget.id) continue;
    /* Already there. The current parent is read from the item, not guessed. */
    var vChart = documentExplorerListFor(vRef.refType);
    var vLine  = (vChart && vChart.getLineByID) ? vChart.getLineByID(vRef.rowId) : null;
    var vParent = (vLine && vLine.getParent) ? vLine.getParent() : null;
    if (dropTarget.mode == 'root' && ! vParent) continue;
    /* No label from the client side : the server names the refused rows, using the
       stored name rather than the row text. */
    vItems.push({refType:vRef.refType, refId:vRef.refId, rowId:vRef.rowId});
  }
  return vItems;
}

/** Calls the entry point, then redraws in every case. */
function documentExplorerSendMove(items, dropTarget) {
  var vList = [];
  for (var i = 0; i < items.length; i++) {
    vList.push(items[i].refType + ':' + items[i].refId);
  }
  var vTarget = (dropTarget.mode == 'root') ? 'root' : ('directory:' + dropTarget.id);
  var vRowToSelect = (items.length == 1) ? items[0].rowId : null;
  showWait();
  dojo.xhrGet({
    url:'../tool/documentExplorerMove.php?items=' + vList.join(',')
        + '&target=' + vTarget + addTokenIndexToUrl(),
    handleAs:'text',
    load:function(data) {
      var vAnswer = null;
      try {
        vAnswer = JSON.parse(dojo.trim(data));
      } catch (e) {
        consoleTraceLog('documentExplorerSendMove : JSON illisible');
        consoleTraceLog(dojo.trim(data).substring(0, 400));
      }
      documentExplorerRefreshExplorer(function() {
        if (vRowToSelect) {
          documentExplorerSelectLineWhenReady(vRowToSelect, null, 15,
              'documentExplorer apres deplacement');
        }
        documentExplorerShowMoveResult(vAnswer);
      });
    },
    error:function(err, ioargs) {
      var vStatus = (ioargs && ioargs.xhr) ? ioargs.xhr.status : '?';
      consoleTraceLog('documentExplorerSendMove : echec (HTTP ' + vStatus + ')');
      documentExplorerRefreshExplorer();
    }
  });
}

/**
 * Result banner after a move, the one the whole application uses.
 *
 * message is the raw save payload : the reader takes the type from its operation
 * status and the text is the one the save produced, not a wording of ours. Refusals
 * past the first are inserted before the hidden fields, which that reader expects at
 * the end of the string. With no payload, an information box is shown instead.
 */
function documentExplorerShowMoveResult(answer) {
  if (! answer) return;
  var vRefused = (answer.refused) ? answer.refused : [];
  if (! answer.message) {
    if (vRefused.length) showInfo(documentExplorerMoveRefusedText(vRefused, 0));
    return;
  }
  var vMsg = answer.message;
  if (vRefused.length > 1) {
    var vCut = vMsg.indexOf('<input');
    var vExtra = '<br/>' + documentExplorerMoveRefusedText(vRefused, 1);
    vMsg = (vCut > -1) ? vMsg.substring(0, vCut) + vExtra + vMsg.substring(vCut)
                       : vMsg + vExtra;
  }
  showSqlElementResultInPopup(vMsg);
}

/** Refusals listed one per line, from the given rank. */
function documentExplorerMoveRefusedText(refused, from) {
  var vLines = [];
  for (var i = from; i < refused.length; i++) {
    var vLabel = refused[i].label;
    vLines.push((vLabel ? vLabel + ' : ' : '') + refused[i].reason);
  }
  return vLines.join('<br/>');
}

/** Absorbs every drop aimed at our sources. Returns true when it did. */
function documentExplorerHandleDrop(source, nodes, target) {
  if (! documentExplorerIsOurDndTarget(target)) return false;
  var vDropTarget = documentExplorerDropTarget(target);
  if (! vDropTarget) { documentExplorerRefreshExplorer(); return true; }
  var vItems = documentExplorerDropItems(nodes, vDropTarget);
  if (! vItems.length) { documentExplorerRefreshExplorer(); return true; }
  documentExplorerSendMove(vItems, vDropTarget);
  return true;
}
