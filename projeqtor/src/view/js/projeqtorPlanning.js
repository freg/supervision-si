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
//
//// ============================================================================
//// All specific ProjeQtOr functions and variables for Dialog Purpose
//// This file is included in the main.php page, to be reachable in every context
//// ============================================================================

//=============================================================================
//= Planning PDF
//=============================================================================

var startDatePlanViewSaved = null;
var endDatePlanViewSaved = null;

//#11179
var planningJsonListFilter = {
  active: false,
  objectClass: null,
  idProject: null,
  wbsSortable: null,
  refId: null
};


function planningPDFBox(copyType) {
  loadDialog('dialogPlanningPdf', null, true, "", false);
}

// =============================================================================
// = Dependency
// =============================================================================
function addDependency(depType) {
  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
  noRefreshDependencyList = false;
  var objectClass = dojo.byId('objectClass').value;
  var objectId = dojo.byId("objectId").value;
  var message = i18n("dialogDependency");
  if (depType) {
    dojo.byId("dependencyType").value = depType;
    message = i18n("dialogDependencyRestricted", new Array(i18n(objectClass),
      objectId, i18n(depType)));
  } else {
    dojo.byId("dependencyType").value = null;
    message = i18n("dialogDependencyExtended", new Array(i18n(objectClass),
      objectId.value));
  }
  if (objectClass == 'Requirement') {
    refreshList('idDependable', 'scope', 'R', '4', 'dependencyRefTypeDep', true);
    dijit.byId("dependencyRefTypeDep").set('value', '4');
    dijit.byId("dependencyDelay").set('value', '0');
    dojo.byId("dependencyDelayDiv").style.display = "none";
    dojo.byId("dependencyTypeDiv").style.display = "none";
  } else if (objectClass == 'TestCase') {
    refreshList('idDependable', 'scope', 'TC', '5', 'dependencyRefTypeDep',
      true);
    dijit.byId("dependencyRefTypeDep").set('value', '5');
    dijit.byId("dependencyDelay").set('value', '0');
    dojo.byId("dependencyDelayDiv").style.display = "none";
    dojo.byId("dependencyTypeDiv").style.display = "none";
  } else {
    if (objectClass == 'Project') {
      dijit.byId("dependencyRefTypeDep").set('value', '3');
      refreshList('idDependable', 'scope', 'PE', '3', 'dependencyRefTypeDep',
        true);
    } else {
      dijit.byId("dependencyRefTypeDep").set('value', '1');
      refreshList('idDependable', 'scope', 'PE', '1', 'dependencyRefTypeDep',
        true);
    }
    if (objectClass == 'Term') {
      dojo.byId("dependencyDelayDiv").style.display = "none";
      dojo.byId("dependencyTypeDiv").style.display = "none";
      dijit.byId("typeOfDependency").set("value", "E-S");
    } else {
      dojo.byId("dependencyDelayDiv").style.display = "block";
      dojo.byId("dependencyTypeDiv").style.display = "block";
    }
  }
  dojo.byId("dependencyRefType").value = objectClass;
  dojo.byId("dependencyRefId").value = objectId;
  refreshList('idActivity', 'id', '-1', null, 'dependencyRefIdDepEdit', false);;
  dijit.byId('dependencyRefIdDepEdit').reset();
  dojo.byId("dependencyId").value = "";
  dijit.byId("dialogDependency").set('title', message);
  dijit.byId("dialogDependency").show();
  dojo.byId('dependencyAddDiv').style.display = 'block';
  dojo.byId('dependencyEditDiv').style.display = 'none';
  dijit.byId("dependencyRefTypeDep").set('readOnly', false);
  dijit.byId("dependencyComment").set('value', null);
  disableWidget('dialogDependencySubmit');
  refreshDependencyList();
}

function editDependency(depType, id, refType, refTypeName, refId, delay,typeOfDependency) {
  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
  if (! delay) delay=0;
  noRefreshDependencyList = true;
  var objectClass = dojo.byId('objectClass').value;
  var objectId = dojo.byId("objectId").value;
  var message = i18n("dialogDependencyEdit");
  if (objectClass == 'Requirement') {
    refreshList('idDependable', 'scope', 'R', refType, 'dependencyRefTypeDep', true);
    dijit.byId("dependencyRefTypeDep").set('value', refType);
    dijit.byId("dependencyDelay").set('value', '0');
    dojo.byId("dependencyDelayDiv").style.display = "none";
    dojo.byId("dependencyTypeDiv").style.display = "none";
  } else if (objectClass == 'TestCase') {
    refreshList('idDependable', 'scope', 'TC', refType, 'dependencyRefTypeDep', true);
    dijit.byId("dependencyRefTypeDep").set('value', refType);
    dijit.byId("dependencyDelay").set('value', '0');
    dojo.byId("dependencyDelayDiv").style.display = "none";
    dojo.byId("dependencyTypeDiv").style.display = "none";
  } else {
    refreshList('idDependable', 'scope', 'PE', refType, 'dependencyRefTypeDep', true);
    dijit.byId("dependencyRefTypeDep").set('value', refType);
    dijit.byId("dependencyDelay").set('value', delay);
    dojo.byId("dependencyDelayDiv").style.display = "block";
    dojo.byId("dependencyTypeDiv").style.display = "block";
  }
  refreshList('id' + refTypeName, 'id', refId, refId, 'dependencyRefIdDepEdit', true);
  dijit.byId('dependencyRefIdDepEdit').set('value', refId);
  dojo.byId("dependencyId").value = id;
  dojo.byId("dependencyRefType").value = objectClass;
  dojo.byId("dependencyRefId").value = objectId;
  dojo.byId("dependencyType").value = depType;
  dijit.byId("typeOfDependency").set('value', typeOfDependency);
  dijit.byId("dialogDependency").set('title', message);
  dijit.byId("dialogDependency").show();
  dojo.byId('dependencyAddDiv').style.display = 'none';
  dojo.byId('dependencyEditDiv').style.display = 'block';
  dijit.byId("dependencyRefTypeDep").set('readOnly', true);
  dijit.byId("dependencyRefIdDepEdit").set('readOnly', true);
  disableWidget('dialogDependencySubmit');
  disableWidget('dependencyComment');
  dijit.byId('dependencyComment').set('value', "");
  dojo.xhrGet({
    url: '../tool/getSingleData.php?dataType=dependencyComment&idDependency='
      + id + addTokenIndexToUrl(),
    handleAs: "text",
    load: function(data) {
      dijit.byId('dependencyComment').set('value', data);
      enableWidget('dialogDependencySubmit');
      enableWidget('dependencyComment');
    }
  });
}

var noRefreshDependencyList = false;
function refreshDependencyList(selected) {
  if (noRefreshDependencyList)
    return;
  disableWidget('dialogDependencySubmit');
  var url = '../tool/dynamicListDependency.php';
  if (selected) {
    url += '?selected=' + selected;
  }
  loadContent(url, 'dialogDependencyList', 'dependencyForm', false);
}

function saveDependency() {
  var formVar = dijit.byId('dependencyForm');
  if (!formVar.validate()) {
    showAlert(i18n("alertInvalidForm"));
    return;
  }
  if (dojo.byId("dependencyRefIdDep").value == ""
    && !dojo.byId('dependencyId').value)
    return;
  loadContent("../tool/saveDependency.php", "resultDivMain", "dependencyForm",
    true, 'dependency');
  dijit.byId('dialogDependency').hide();
}

function saveDependencyFromDndLink(ref1Type, ref1Id, ref2Type, ref2Id) {
  graphicalChange = true;
  if (ref1Type == ref2Type && ref1Id == ref2Id)
    return;
  param = "ref1Type=" + ref1Type;
  param += "&ref1Id=" + ref1Id;
  param += "&ref2Type=" + ref2Type;
  param += "&ref2Id=" + ref2Id;
  loadContent("../tool/saveDependencyDnd.php?" + param, "resultDivMain", null,
    true, 'dependency');
}

function removeDependency(dependencyId, refType, refId) {
  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
  dojo.byId("dependencyId").value = dependencyId;
  actionOK = function() {
    loadContent("../tool/removeDependency.php", "resultDivMain",
      "dependencyForm", true, 'dependency');
  };
  msg = i18n('confirmDeleteLink', new Array(i18n(refType), refId));
  showConfirm(msg, actionOK);
}

// =============================================================================
// = Plan
// =============================================================================

var oldSelectedProjectsToPlan = null;
function showPlanParam(selectedProject) {
  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
  //dijit.byId("dialogPlan").show();
  var callBack=function() {
    pqPlanListInit();
    oldSelectedProjectsToPlan = dijit.byId("idProjectPlan").get("value");
  };
  var params='';
  loadDialog('dialogPlan', callBack, true, params, true);
}

function lockSaveRefresh() {
  if (lockPlanningSaveRefresh == 1) {
    dojo.query('.iconLock').forEach(function(node) {
      dojo.removeClass(node, 'iconLock');
      dojo.addClass(node, 'iconDeLock');
    });
    saveDataToSession('lockPlanningSaveRefresh', 0, false);
    lockPlanningSaveRefresh = 0;
    dojo.removeClass('automaticRunPlanSwitch', 'mblSwitchDisabled');
    refreshGrid();
  } else {
    dojo.query('.iconDeLock').forEach(function(node) {
      dojo.removeClass(node, 'iconDeLock');
      dojo.addClass(node, 'iconLock');
    });
    saveDataToSession('lockPlanningSaveRefresh', 1, false);
    lockPlanningSaveRefresh = 1;
    dojo.addClass('automaticRunPlanSwitch', 'mblSwitchDisabled');
  }
}

function GotoPlanningToday() {
  var today = [];
  dojo.query('.specificDayToday').forEach(function(node) {
    today.push(node);
  });
  if (today) {
    var currentPos = today[0].offsetTop;
    var ratio=(typeof JSGantt != 'undefined' && JSGantt.getPlanningZoomRatio)?JSGantt.getPlanningZoomRatio():1;
    var containerScroll = document.getElementById('rightGanttChartDIV').scrollTop;
    var containerHeight = document.getElementById('rightGanttChartDIV').offsetHeight;
    var newPos = null;
    if ((currentPos*ratio) < containerScroll || (currentPos*ratio) > containerScroll + containerHeight) {
      newPos = currentPos - ((containerHeight/ratio) / 2) + 10;
      if (newPos < 0) newPos = 0;
    }
    if (today.length > 1) {
      setTimeout("scrollBarIntoView(null," + newPos + ", true, " + today[0].id + ");", 100);
    } else {
      setTimeout("scrollBarIntoView(null," + newPos + ", false, " + today[0].id + ");", 100);
    }
  }
}

function changedIdProjectPlan(value) {
  if (dijit.byId("idProjectPlan")){
    var selectField = dijit.byId("idProjectPlan").get("value");
    if (selectField.length <= 0) {
      dijit.byId('dialogPlanSubmit').set('disabled', true);
    } else {
      dijit.byId('dialogPlanSubmit').set('disabled', false);
    }
  }
  if (!oldSelectedProjectsToPlan || oldSelectedProjectsToPlan == value) return;
  if (oldSelectedProjectsToPlan.indexOf(" ") >= 0 && value.length > 1) {
    if (value.indexOf(" ") >= 0) {
      value.splice(0, 1);
    }
    oldSelectedProjectsToPlan = value;
    if (dijit.byId("idProjectPlan")) dijit.byId("idProjectPlan").set("value", value);
  } else if (value.indexOf(" ") >= 0
    && oldSelectedProjectsToPlan.indexOf(" ") === -1) {
    value = [" "];
    oldSelectedProjectsToPlan = value;
    if (dijit.byId("idProjectPlan")) dijit.byId("idProjectPlan").set("value", value);
  }
  saveDataToSession('planSelectedProjects',value,false);
  dojo.byId("planSelectedProjects").value=value;
  oldSelectedProjectsToPlan = value;
}

function saveProjectCriticalResources(value) {
  if (oldValueProjectCriticalResources.indexOf(" ") >= 0 && value.length > 1) {
    if (value.indexOf(" ") >= 0) {
      value.splice(0, 1);
    }
    oldValueProjectCriticalResources = value;
    dijit.byId("idProjectCriticalResources").set("value", value);
  } else if (value.length == 0) {
    value = [" "];
    dijit.byId("idProjectCriticalResources").set("value", value);
  } else if (value.indexOf(" ") >= 0
    && oldValueProjectCriticalResources.indexOf(" ") === -1) {
    value = [" "];
    oldValueProjectCriticalResources = value;
    dijit.byId("idProjectCriticalResources").set("value", value);
  }

  oldValueProjectCriticalResources = value;
  saveDataToSession('idProjectCriticalResources', value, false);
}


function showSelectedProject(value) {
  if (! dijit.byId('dialogPlanSubmit')) return; // PBER #1199 dialogPlan is now dynamic
  var selectedProj = oldSelectedProjectsToPlan;
  var callback = function() {
    pqPlanListInit();
    dijit.byId("idProjectPlan").set("value", selectedProj);
    var selectField = dijit.byId("idProjectPlan").get("value");
    if (selectField.length <= 0) {
      dijit.byId('dialogPlanSubmit').set('disabled', true);
    } else {
      dijit.byId('dialogPlanSubmit').set('disabled', false);
    }
  };
  loadContent("../view/refreshSelectedProjectListDiv.php?isChecked=" + value
    + "&selectedProjectPlan=" + selectedProj, "selectProjectList",
    "dialogPlanForm", false, null, null, null, callback);
}

function plan(allItems) {
  if (allItems && allItems != undefined) {
    dojo.byId('planLastSavedClass').value = "";
    dojo.byId('planLastSavedId').value = "";
  }
  var bt = dijit.byId('planButton');
  if (bt) {
    bt.set('iconClass', "dijitIcon iconPlan");
  }
  if (dijit.byId('idProjectPlan') && !dijit.byId('idProjectPlan').get('value')) {
    dijit.byId('idProjectPlan').set('value', ' ');
  }
  if (! dojo.byId('planStartDate').value) {
    showAlert(i18n('messageInvalidDate'));
    return;
  }
  // PBER #
  var params="?planLastSavedClass="+dojo.byId("planLastSavedClass").value;
  params+="&planLastSavedId="+dojo.byId("planLastSavedId").value;
  if (!dijit.byId('idProjectPlan')) params+="&idProjectPlan="+dojo.byId('planSelectedProjects').value;
  if (!dijit.byId('startDatePlan')) params+="&startDatePlan="+dojo.byId('planStartDate').value;
  loadContent("../tool/plan.php"+params, "resultDivMain", "dialogPlanForm", true, null);
  quickPlanning = false;
  // The dialog is built on demand : it is absent when the replan comes from the planning
  var planDialog=dijit.byId("dialogPlan");
  if (planDialog) planDialog.hide();
}

function cancelPlan() {
  if (!dijit.byId('idProjectPlan').get('value')) {
    dijit.byId('idProjectPlan').set('value', ' ');
  }
  dijit.byId('dialogPlan').hide();
}

function showPlanSaveDates() {
  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
  callBack = function() {
    var proj = dijit.byId('idProjectPlan');
    if (proj && proj.get('value') && proj.get('value') != '*') {
      dijit.byId('idProjectPlanSaveDates').set('value', proj.get('value'));
    }
  };
  loadDialog('dialogPlanSaveDates', callBack, true, null, true);
}

function planSaveDates() {
  var formVar = dijit.byId('dialogPlanSaveDatesForm');
  if (!formVar.validate()) {
    showAlert(i18n("alertInvalidForm"));
    return;
  }
  if (!dijit.byId('idProjectPlanSaveDates').get('value')) {
    dijit.byId('idProjectPlanSaveDates').set('value', ' ');
  }
  loadContent("../tool/planSaveDates.php", "resultDivMain",
    "dialogPlanSaveDatesForm", true, null);
  dijit.byId("dialogPlanSaveDates").hide();
}

// =============================================================================
// = Baseline
// =============================================================================

function showPlanningBaseline() {
  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
  //  callBack=function() {
  //    var proj=dijit.byId('idProjectPlan');
  //    if (proj) {
  //      dijit.byId('idProjectPlanBaseline').set('value', proj.get('value'));
  //    }
  //  };
  callBack = null;
  loadDialog('dialogPlanBaseline', callBack, true);
}

function savePlanningBaseline() {
  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
  var callback = function() {
    dijit.byId('selectBaselineTop').reset();
    dijit.byId('selectBaselineBottom').reset();
    refreshList('idBaselineSelect', null, null, null, 'selectBaselineTop');
    refreshList('idBaselineSelect', null, null, null, 'selectBaselineBottom');
  };
  if (dojo.byId('isGlobalPlanning')) {
    if (dojo.byId('globalPlanning')
      && dojo.byId('globalPlanning').value == 'true') {
      dojo.byId('isGlobalPlanning').value = 'true';
    }
  }
  var formVar = dijit.byId('dialogPlanBaselineForm');
  if (formVar.validate()) {
    loadContent("../tool/savePlanningBaseline.php", "resultDivMain",
      "dialogPlanBaselineForm", true, null, null, null, callback);
    dijit.byId("dialogPlanBaseline").hide();
  } else {
    showAlert(i18n("alertInvalidForm"));
  }
}

function editBaseline(baselineId) {
  var params = "&editMode=true&baselineId=" + baselineId;
  loadDialog('dialogPlanBaseline', null, true, params, true);
}

function removeBaseline(baselineId) {
  var param = "?baselineId=" + baselineId;
  actionOK = function() {
    var callback = function() {
      dijit.byId('selectBaselineTop').reset();
      dijit.byId('selectBaselineBottom').reset();
      refreshList('idBaselineSelect', null, null, null, 'selectBaselineTop');
      refreshList('idBaselineSelect', null, null, null, 'selectBaselineBottom');
    };
    loadContent("../tool/removePlanningBaseline.php" + param, "dialogPlanBaseline", null, null, null, null, null, callback);
  };
  msg = i18n('confirmDelete', new Array(i18n('Baseline'), baselineId));
  showConfirm(msg, actionOK);
}

function runExportPlanningToCanvasToPDF() {
  var callBack = function() {
    planningToCanvasToPDF();
  };
  refreshMissingLines(callBack);
}
// ==========================
// Export Planning to PDF
// ==========================
function planningToCanvasToPDF() {
  var iframe = document.createElement('iframe');

  // this onload is for firefox but also work on others browsers
  iframe.onload = function() {
    var orientation = "landscape";  // "portrait" ou "landscape"
    if (!document.getElementById("printLandscape").checked) orientation = "portrait";
    var ratio = parseInt(document.getElementById("printZoom").value) / 100;
    var repeatIconTask = document.getElementById("printRepeat").checked; // If true
    // this
    // will
    // repeat
    // on each
    // page
    // the
    // icon
    loadContent("../tool/submitPlanningPdf.php", "resultDivMain", 'planningPdfForm', false, null, null, null, function() { showWait(); });
    var sizeElements = [];
    var marge = 30;
    var widthIconTask = 0; // the width that icon+task represent
    // var
    // heightColumn=parseInt(document.getElementById('leftsideTop').offsetHeight)*ratio;
    // damian #exportPDF
    var deviceRatio = window.devicePixelRatio;
    if (!deviceRatio) {
      deviceRatio = 1;
    }
    var heightColumn = parseInt(document.getElementById('leftsideTop').offsetHeight) * deviceRatio;
    // var heightRow=21*ratio;
    var heightRow = 21 * deviceRatio;
    // var
    // widthRow=(parseInt(dojo.query('.ganttRightTitle')[0].offsetWidth)-1)*ratio;
    var widthRow = (parseInt(dojo.query('.ganttRightTitle')[0].offsetWidth) - 1);
    var nbRowTotal = 0;
    var nbColTotal = 0;
    // init max width/height by orientation
    var pageFormat = 'A4';
    if (document.getElementById("printFormatA3").checked) pageFormat = "A3";
    var imageZoomIn = 1.3 / ratio;
    var imageZoomOut = 1 / imageZoomIn;
    ratio = 1;
    var maxWidth = (596 - (2 * marge)) * imageZoomIn;
    var maxHeight = (842 - (2 * marge)) * imageZoomIn;
    if (pageFormat == 'A3') {
      var maxTemp = maxWidth;
      maxWidth = maxHeight;
      maxHeight = 2 * maxTemp;
    }
    if (orientation == "landscape") {
      var maxTemp = maxWidth;
      maxWidth = maxHeight;
      maxHeight = maxTemp;
    }

    // We create an iframe will which contain the planning to transform it in
    // image
    var frameContent = document.getElementById("iframeTmpPlanning");

    var cssLink2 = document.createElement("link");
    cssLink2.href = "css/projeqtor.css";
    cssLink2.rel = "stylesheet";
    cssLink2.type = "text/css";
    frameContent.contentWindow.document.head.appendChild(cssLink2);

    var cssLink3 = document.createElement("link");
    cssLink3.href = "css/projeqtorNew.css";
    cssLink3.rel = "stylesheet";
    cssLink3.type = "text/css";
    frameContent.contentWindow.document.head.appendChild(cssLink3);

    var cssLink = document.createElement("link");
    cssLink.href = "css/jsgantt.css";
    cssLink.rel = "stylesheet";
    cssLink.type = "text/css";
    frameContent.contentWindow.document.head.appendChild(cssLink);

    // var jsLink = document.createElement("script");
    // jsLink.setAttribute("src", "js/dynamicCss.js");
    // jsLink.setAttribute("type", "text/javascript");
    // frameContent.contentWindow.document.head.appendChild(jsLink);
    // frameContent.contentWindow.setColorTheming(); // Not found ?
    frameContent.contentWindow.document.body.style.setProperty("--image-hue-rotate", document.body.style.getPropertyValue("--image-hue-rotate"));
    frameContent.contentWindow.document.body.style.setProperty("--image-hue-rotate-reverse", document.body.style.getPropertyValue("--image-hue-rotate-reverse"));
    frameContent.contentWindow.document.body.style.setProperty("--image-saturate", document.body.style.getPropertyValue("--image-saturate"));
    frameContent.contentWindow.document.body.style.setProperty("--image-brightness", document.body.style.getPropertyValue("--image-brightness"));
    // addColor("--image-hue-rotate", hueRotate+'deg');
    // addColor("--image-hue-rotate-reverse", (-1*hueRotate)+'deg');
    // addColor("--image-saturate", saturate+'%');
    // addColor("--image-brightness", brightness+'%');

    var heightV = (heightColumn + getMaxHeight(document.getElementById('leftside')) + (getMaxHeight(document.getElementById('leftside')) / 21)) + 'px';

    frameContent.style.position = 'absolute';
    frameContent.style.width = (4 + parseInt(document.getElementById('leftGanttChartDIV').style.width) + getMaxWidth(document.getElementById('rightTableContainer'))) + 'px';
    frameContent.style.height = heightV;
    frameContent.style.border = '0';
    // frameContent.style.top='0';
    // frameContent.style.left='0';
    var bodyClass = document.body.className;
    bodyClass = 'ProjeQtOrFlatGrey';
    frameContent.contentWindow.document.body.innerHTML = '<div class="' + bodyClass + '" style="float:left;width:' + document.getElementById('leftGanttChartDIV').style.width + ';overflow:hidden;height:' + heightV + ';">' + document.getElementById('leftGanttChartDIV').innerHTML + '</div><div style="float:left;width:' + getMaxWidth(document.getElementById('rightTableContainer')) + 'px;height:' + heightV + ';">' + document.getElementById('GanttChartDIV').innerHTML + "</div>";

    frameContent.contentWindow.document.getElementById('ganttScale').style.display = 'none';
    frameContent.contentWindow.document.getElementById('topGanttChartDIV').style.width = getMaxWidth(document.getElementById('rightTableContainer')) + 'px';
    frameContent.contentWindow.document.getElementById('topGanttChartDIV').style.overflow = 'visible';
    frameContent.contentWindow.document.getElementById('mainRightPlanningDivContainer').style.overflow = 'visible';
    frameContent.contentWindow.document.getElementById('rightGanttChartDIV').style.overflow = 'visible';
    frameContent.contentWindow.document.getElementById('mainRightPlanningDivContainer').style.height = (getMaxHeight(document.getElementById('leftside'))) + 'px';
    frameContent.contentWindow.document.getElementById('rightGanttChartDIV').style.height = (getMaxHeight(document.getElementById('leftside'))) + 'px';
    frameContent.contentWindow.document.getElementById('rightGanttChartDIV').style.height = (getMaxHeight(document.getElementById('leftside'))) + 'px';
    frameContent.contentWindow.document.getElementById('dndSourceTable').style.height = (getMaxHeight(document.getElementById('leftside'))) + 'px';
    frameContent.contentWindow.document.getElementById('vScpecificDay_1').style.height = (getMaxHeight(document.getElementById('leftside'))) + 'px';
    frameContent.contentWindow.document.getElementById('leftside').style.top = "0";
    frameContent.contentWindow.document.getElementById('leftsideTop').style.width = document.getElementById('leftGanttChartDIV').style.width;
    frameContent.contentWindow.document.getElementById('leftside').style.width = document.getElementById('leftGanttChartDIV').style.width;
    frameContent.contentWindow.document.getElementById('rightGanttChartDIV').style.overflowX = "visible";
    frameContent.contentWindow.document.getElementById('rightGanttChartDIV').style.overflowY = "visible";
    // Calculate each width column in left top side
    for (var i = 0; i < dojo.query("[id^='topSourceTable'] tr")[1].childNodes.length; i++) {
      sizeElements.push((dojo.query("[id^='topSourceTable'] tr")[1].childNodes[i].offsetWidth) * ratio);
    }
    for (var i = 0; i < dojo.query("[class^='rightTableLine']").length; i++) {
      dojo.query("[class^='rightTableLine']")[i].style.width = (parseInt(dojo.query("[class^='rightTableLine']")[i].style.width) - 1) + "px";
    }
    for (var i = 0; i < dojo.query("[class^='ganttDetail weekBackground']").length; i++) {
      dojo.query("[class^='ganttDetail weekBackground']")[i].style.width = (parseInt(dojo.query("[class^='ganttDetail weekBackground']")[i].style.width) - 1) + "px";
    }

    widthIconTask = (sizeElements[0] + sizeElements[1]) * deviceRatio;
    if (widthIconTask > parseInt(document.getElementById('leftGanttChartDIV').style.width) * deviceRatio) widthIconTask = parseInt(document.getElementById('leftGanttChartDIV').style.width) * deviceRatio;

    sizeColumn = parseInt(dojo.query(".ganttRightTitle")[0].style.width) * ratio;

    frameContent.contentWindow.document.getElementById('rightGanttChartDIV').style.width = getMaxWidth(frameContent.contentWindow.document.getElementById('rightGanttChartDIV')) + 'px';
    frameContent.contentWindow.document.getElementById('topGanttChartDIV').style.width = getMaxWidth(frameContent.contentWindow.document.getElementById('rightGanttChartDIV')) + 'px';
    frameContent.contentWindow.document.getElementById('mainRightPlanningDivContainer').style.width = getMaxWidth(frameContent.contentWindow.document.getElementById('rightGanttChartDIV')) + 'px';
    // add border into final print
    frameContent.contentWindow.document.getElementById('leftsideTop').innerHTML = '<div id="separatorLeftGanttChartDIV2" style="position:absolute;height:100%;z-index:10000;width:4px;background-color:#C0C0C0;"></div>' + frameContent.contentWindow.document.getElementById('leftsideTop').innerHTML;
    frameContent.contentWindow.document.getElementById('leftside').innerHTML = '<div id="separatorLeftGanttChartDIV" style="position:absolute;height:100%;z-index:10000;width:4px;background-color:#C0C0C0;"></div>' + frameContent.contentWindow.document.getElementById('leftside').innerHTML;
    frameContent.contentWindow.document.getElementById('leftside').style.width = (parseInt(frameContent.contentWindow.document.getElementById('leftside').style.width) + parseInt(frameContent.contentWindow.document.getElementById('separatorLeftGanttChartDIV').style.width)) + 'px';
    frameContent.contentWindow.document.getElementById('leftsideTop').style.width = frameContent.contentWindow.document.getElementById('leftside').style.width;
    frameContent.contentWindow.document.getElementById('separatorLeftGanttChartDIV').style.left = (parseInt(frameContent.contentWindow.document.getElementById('leftside').style.width) - 4) + 'px';
    frameContent.contentWindow.document.getElementById('separatorLeftGanttChartDIV2').style.left = (parseInt(frameContent.contentWindow.document.getElementById('leftsideTop').style.width) - 4) + 'px';
    frameContent.contentWindow.document.getElementById('rightGanttChartDIV').style.width = frameContent.contentWindow.document.getElementById('rightTableContainer').style.width;
    frameContent.contentWindow.document.getElementById('rightGanttChartDIV').style.height = frameContent.contentWindow.document.getElementById('rightTableContainer').style.height;

    var tabImage = []; // Contain pictures
    var mapImage = {}; // Contain pictures like key->value, cle=namePicture,
    // value=base64(picture)

    // Start the 4 prints function
    // Print image activities and projects
    html2canvas(frameContent.contentWindow.document.getElementById('leftside')).then(function(leftElement) {
      // Print image column left side
      html2canvas(frameContent.contentWindow.document.getElementById('leftsideTop')).then(function(leftColumn) {
        // Print right Line
        html2canvas(frameContent.contentWindow.document.getElementById('rightGanttChartDIV')).then(function(rightElement) {
          // Print right column
          html2canvas(frameContent.contentWindow.document.getElementById('rightside')).then(function(rightColumn) {
            if (ratio != 1) {
              leftElement = cropCanvas(leftElement, 0, 0, leftElement.width, leftElement.height, ratio);
              leftColumn = cropCanvas(leftColumn, 0, 0, leftColumn.width, leftColumn.height, ratio);
              rightElement = cropCanvas(rightElement, 0, 0, rightElement.width, rightElement.height, ratio);
              rightColumn = cropCanvas(rightColumn, 0, 0, rightColumn.width, rightColumn.height, ratio);
            }
            // Init number of total rows
            nbRowTotal = Math.round(leftElement.height / heightRow);
            // frameContent.parentNode.removeChild(frameContent);
            // Start pictures's calcul
            firstEnterHeight = true;
            var EHeightValue = 0; // Height pointer cursor
            var EHeight = leftElement.height; // total height
            while ((Math.ceil(EHeight / maxHeight) >= 1 || firstEnterHeight) && EHeight > heightRow) {
              var calculHeight = maxHeight;
              var ELeftWidth = leftElement.width; // total width
              var ERightWidth = rightElement.width; // total width
              var addHeighColumn = 0;
              if (firstEnterHeight || (!firstEnterHeight && repeatIconTask)) {
                addHeighColumn = heightColumn;
              }
              var heightElement = 0;
              while (calculHeight - addHeighColumn >= heightRow && nbRowTotal != 0) {
                calculHeight -= heightRow;
                heightElement += heightRow;
                nbRowTotal--;
              }
              var iterateurColumnLeft = 0;
              firstEnterWidth = true;
              var widthElement = 0;
              var imageRepeat = null;
              if (repeatIconTask) {
                imageRepeat = combineCanvasIntoOne(
                  cropCanvas(leftColumn, 0, 0, widthIconTask, heightColumn),
                  cropCanvas(leftElement, 0, EHeightValue, widthIconTask, heightElement),
                  true);
              }
              var canvasList = [];
              while (ELeftWidth / maxWidth >= 1 || (!firstEnterWidth && ELeftWidth > 0)) {
                firstEnterWidth2 = true;
                oldWidthElement = widthElement;
                while (iterateurColumnLeft < sizeElements.length && ELeftWidth >= sizeElements[iterateurColumnLeft]) {
                  ELeftWidth -= sizeElements[iterateurColumnLeft];
                  widthElement += sizeElements[iterateurColumnLeft] * deviceRatio;
                  if (repeatIconTask && !firstEnterWidth && firstEnterWidth2) ELeftWidth += widthIconTask;
                  iterateurColumnLeft++;
                  firstEnterWidth2 = false;
                }
                if (oldWidthElement == widthElement) {
                  widthElement += ELeftWidth;
                  ELeftWidth = 0;
                }
                if (!firstEnterWidth) {
                  if (repeatIconTask) {
                    canvasList.push(combineCanvasIntoOne(imageRepeat,
                      combineCanvasIntoOne(
                        cropCanvas(leftColumn, oldWidthElement, 0, widthElement - oldWidthElement, heightColumn),
                        cropCanvas(leftElement, oldWidthElement, EHeightValue, widthElement - oldWidthElement, heightElement),
                        true),
                      false));
                  } else {
                    if (firstEnterHeight) {
                      canvasList.push(combineCanvasIntoOne(
                        cropCanvas(leftColumn, oldWidthElement, 0, widthElement - oldWidthElement, heightColumn),
                        cropCanvas(leftElement, oldWidthElement, EHeightValue, widthElement - oldWidthElement, heightElement),
                        true));
                    } else {
                      canvasList.push(cropCanvas(leftElement, oldWidthElement, EHeightValue, widthElement - oldWidthElement, heightElement));
                    }
                  }
                } else {
                  if (firstEnterHeight || repeatIconTask) {
                    canvasList.push(combineCanvasIntoOne(
                      cropCanvas(leftColumn, oldWidthElement, 0, widthElement - oldWidthElement, heightColumn),
                      cropCanvas(leftElement, oldWidthElement, EHeightValue, widthElement - oldWidthElement, heightElement),
                      true));
                  } else {
                    canvasList.push(cropCanvas(leftElement, oldWidthElement, EHeightValue, widthElement - oldWidthElement, heightElement));
                  }
                }
                firstEnterWidth = false;
              }
              if (canvasList.length == 0) {
                if (firstEnterHeight || repeatIconTask) {
                  canvasList.push(combineCanvasIntoOne(
                    cropCanvas(leftColumn, 0, 0, leftColumn.width, heightColumn),
                    cropCanvas(leftElement, 0, EHeightValue, leftElement.width, heightElement),
                    true));
                } else {
                  canvasList.push(cropCanvas(leftElement, 0, EHeightValue, leftElement.width, heightElement));
                }
              }
              firstEnterWidth = true;
              if (repeatIconTask && leftColumn.width > widthIconTask) {
                imageRepeat = combineCanvasIntoOne(combineCanvasIntoOne(
                  cropCanvas(leftColumn, 0, 0, widthIconTask, heightColumn),
                  cropCanvas(leftElement, 0, EHeightValue, widthIconTask, heightElement),
                  true),
                  combineCanvasIntoOne(
                    cropCanvas(leftColumn, leftColumn.width - 4, 0, 4, heightColumn),
                    cropCanvas(leftElement, leftElement.width - 4, EHeightValue, 4, heightElement),
                    true),
                  false);
              }
              widthElement = 0;
              firstEnterWidth = true;
              var canvasList2 = [];
              // Init number of total cols
              nbColTotal = Math.round(rightElement.width / widthRow);
              var countIteration = 0;
              while ((Math.ceil(ERightWidth / maxWidth) >= 1 || (!firstEnterWidth && ERightWidth > 0)) && nbColTotal > 0) {
                countIteration++;
                firstEnterWidth2 = true;
                oldWidthElement = widthElement;
                limit = 0;
                if (firstEnterWidth) limit = canvasList[canvasList.length - 1].width;
                if (!firstEnterWidth && repeatIconTask) limit = widthIconTask;
                var currentWidthElm = 0;
                while (ERightWidth > widthRow && currentWidthElm + widthRow < maxWidth - limit && nbColTotal > 0) {
                  ERightWidth -= widthRow;
                  widthElement += widthRow;
                  currentWidthElm += widthRow;
                  firstEnterWidth2 = false;
                  nbColTotal--;
                }
                if (!firstEnterWidth) {
                  if (currentWidthElm != 0 && widthElement != oldWidthElement)
                    if (repeatIconTask) {
                      canvasList2.push(combineCanvasIntoOne(imageRepeat,
                        combineCanvasIntoOne(
                          cropCanvas(rightColumn, oldWidthElement + 1, 0, currentWidthElm, heightColumn),
                          cropCanvas(rightElement, oldWidthElement, EHeightValue, currentWidthElm, heightElement),
                          true),
                        false));
                    } else {
                      if (firstEnterHeight) {
                        canvasList2.push(combineCanvasIntoOne(
                          cropCanvas(rightColumn, oldWidthElement + 1, 0, currentWidthElm, heightColumn),
                          cropCanvas(rightElement, oldWidthElement, EHeightValue, currentWidthElm, heightElement),
                          true));
                      } else {
                        canvasList2.push(cropCanvas(rightElement, oldWidthElement, EHeightValue, currentWidthElm, heightElement));
                      }
                    }
                } else {
                  if (widthElement == 0) {
                    canvasList2.push(canvasList[canvasList.length - 1]);
                  } else if (firstEnterHeight || repeatIconTask) {
                    canvasList2.push(combineCanvasIntoOne(canvasList[canvasList.length - 1],
                      combineCanvasIntoOne(
                        cropCanvas(rightColumn, oldWidthElement + 1, 0, currentWidthElm, heightColumn),
                        cropCanvas(rightElement, oldWidthElement, EHeightValue, currentWidthElm, heightElement),
                        true),
                      false));
                  } else {
                    canvasList2.push(combineCanvasIntoOne(canvasList[canvasList.length - 1],
                      cropCanvas(rightElement, oldWidthElement, EHeightValue, currentWidthElm, heightElement),
                      false));
                  }
                }
                if (nbColTotal == 0 || countIteration > 100) {
                  ERightWidth = 0;
                }
                firstEnterWidth = false;
              }
              var baseIterateur = tabImage.length;
              for (var i = 0; i < canvasList.length - 1; i++) {

                // Add image to mapImage in base64 format
                mapImage["image" + (i + baseIterateur)] = canvasList[i].toDataURL();

                // Add to tabImage an array wich contain parameters to put an
                // image into a pdf page with a pagebreak if necessary
                ArrayToPut = { image: "image" + (i + baseIterateur), width: canvasList[i].width * imageZoomOut, height: canvasList[i].height * imageZoomOut };
                if (!(canvasList2.length == 0 && i == canvasList.length - 1)) {
                  ArrayToPut['pageBreak'] = 'after';
                }
                tabImage.push(ArrayToPut);
              }
              for (var i = 0; i < canvasList2.length; i++) {
                if (canvasList2[i].width - widthIconTask > 4) {
                  // Add image to mapImage in base64 format
                  mapImage["image" + (i + canvasList.length + baseIterateur)] = canvasList2[i].toDataURL();

                  // Add to tabImage an array wich contain parameters to put an
                  // image into a pdf page with a pagebreak if necessary
                  ArrayToPut = { image: "image" + (i + canvasList.length + baseIterateur), width: canvasList2[i].width * imageZoomOut, height: canvasList2[i].height * imageZoomOut };
                  if (i != canvasList2.length - 1) {
                    ArrayToPut['pageBreak'] = 'after';
                  }
                  tabImage.push(ArrayToPut);
                }
              }
              EHeight -= maxHeight - calculHeight;
              EHeightValue += maxHeight - calculHeight;
              firstEnterHeight = false;
            }
            var dd = {
              pageMargins: [marge, marge, marge, marge],
              pageOrientation: orientation,
              content: tabImage,
              images: mapImage,
              footer: function(currentPage, pageCount) { return { fontSize: 8, text: currentPage.toString() + ' / ' + pageCount, alignment: 'center' }; },
              pageSize: pageFormat
            };
            if (!dojo.isIE) {
              var userAgent = navigator.userAgent.toLowerCase();
              var IEReg = /(msie\s|trident.*rv:)([\w.]+)/;
              var match = IEReg.exec(userAgent);
              if (match)
                dojo.isIE = match[2] - 0;
              else
                dojo.isIE = undefined;
            }
            var pdfFileName = 'ProjeQtOr_Planning';
            var now = new Date();
            pdfFileName += '_' + formatDate(now).replace(/-/g, '') + '_' + formatTime(now).replace(/:/g, '');
            pdfFileName += '.pdf';
            if ((dojo.isIE && dojo.isIE > 0) || window.navigator.userAgent.indexOf("Edge") > -1) {
              pdfMake.createPdf(dd).download(pdfFileName);
            } else {
              pdfMake.createPdf(dd).download(pdfFileName);
            }
            // open the PDF in a new window
            // pdfMake.createPdf(dd).open();
            // print the PDF (temporarily Chrome-only)
            // pdfMake.createPdf(dd).print();
            // download the PDF (temporarily Chrome-only)
            dijit.byId('dialogPlanningPdf').hide();
            iframe.parentNode.removeChild(iframe);
            setTimeout('hideWait();', 100);
          });
        });
      });
    });
  };
  iframe.id = "iframeTmpPlanning";
  document.body.appendChild(iframe);
}
function cropCanvas(canvasToCrop, x, y, w, h, r) {
  if (typeof r == 'undefined') r = 1;
  var tempCanvas = document.createElement("canvas"),
    tCtx = tempCanvas.getContext("2d");
  tempCanvas.width = w * r;
  tempCanvas.height = h * r;
  if (w != 0 && h != 0) tCtx.drawImage(canvasToCrop, x, y, w, h, 0, 0, w * r, h * r);
  return tempCanvas;
}

// addBottom=true : we add the canvas2 at the bottom of canvas1, addBottom=false
// : we add the canvas2 at the right of canvas1
function combineCanvasIntoOne(canvas1, canvas2, addBottom) {
  var tempCanvas = document.createElement("canvas");
  var tCtx = tempCanvas.getContext("2d");
  var ajoutWidth = 0;
  var ajoutHeight = 0;
  var x = 0;
  var y = 0;
  if (addBottom) {
    ajoutHeight = canvas2.height;
    y = canvas1.height;
  } else {
    ajoutWidth = canvas2.width;
    x = canvas1.width;
  }
  tempCanvas.width = canvas1.width + ajoutWidth;
  tempCanvas.height = canvas1.height + ajoutHeight;
  if (canvas1.width != 0 && canvas1.height != 0) tCtx.drawImage(canvas1, 0, 0, canvas1.width, canvas1.height);
  if (canvas1.width != 0 && canvas1.height != 0) if (canvas2.width != 0 && canvas2.height != 0) tCtx.drawImage(canvas2, 0, 0, canvas2.width, canvas2.height, x, y, canvas2.width, canvas2.height);
  return tempCanvas;
}

// ==================================================================
// Draw a gantt chart - Use Lazy Loading and Lazy rendering
// ==================================================================
/**
 * Draw a gantt chart using jsGantt
 * 
 * @return
 */
var arrProjectStart = {};
var arrayVisible = new Array();
var drawGanttInProgress = false;
function drawGantt(onlyRefresh) {
  drawGanttInProgress = true;
  if (onlyRefresh == undefined) onlyRefresh = false;
  // first, if detail is displayed, reload class
  if (dojo.byId('objectClass') && !dojo.byId('objectClass').value
    && dojo.byId("objectClassName") && dojo.byId("objectClassName").value) {
    dojo.byId('objectClass').value = dojo.byId("objectClassName").value;
  }
  var planningType = 'planning';
  if (dojo.byId('planningType')) {
    planningType = dojo.byId('planningType').value;
  }
  if (dojo.byId("objectId") && !dojo.byId("objectId").value && dijit.byId("id")
    && dijit.byId("id").get("value")) {
    dojo.byId("objectId").value = dijit.byId("id").get("value");
  }
  var startDateView = (dojo.byId('projectDate') && dojo.byId('projectDate').checked) ? null : new Date();
  if (dijit.byId('startDatePlanView') && dojo.byId('projectDate')) {
    //gautier #6924
    if (!dojo.byId('projectDate').checked) {
      startDateView = dijit.byId('startDatePlanView').get('value');
    }
  }
  var endDateView = null;
  if (dijit.byId('endDatePlanView') && dojo.byId('projectDate')) {
    if (!dojo.byId('projectDate').checked) {
      endDateView = dijit.byId('endDatePlanView').get('value');
    }
  }
  var showWBS = null;
  if (dijit.byId('showWBS')) {
    //showWBS = dijit.byId('showWBS').get('checked');
    showWBS = dijit.byId('showWBS').get('value');
    if (dijit.byId('showWBS').get('checked')) {
      showWBS == 'on';
    }
    if (showWBS == 'on') {
      showWBS = true;
    } else {
      showWBS = false;
    }
  }
  // showWBS=true;
  var gFormat = "day";
  if (g) {
    gFormat = g.getFormat();
    if (dijit.byId('selectBaselineBottom')) {
      g.setBaseBottomName(dijit.byId('selectBaselineBottom').get('displayedValue'));
    }
    if (dijit.byId('selectBaselineTop')) {
      g.setBaseTopName(dijit.byId('selectBaselineTop').get('displayedValue'));
    }
  }
  // Only first display, refresh JSGantt object
  if (!onlyRefresh) {
	criticalPathFilterActive = false;
    showGanttOneLineWaitRefresh = false;
    lineRefreshArray = {};
    g = new JSGantt.GanttChart('g', dojo.byId('GanttChartDIV'), gFormat);
    g.ClearGraph();
    resetPlanningFieldDescription();
    setGanttVisibility(g, planningType);
    g.setCaptionType('Caption'); // Set to Show Caption (None,Caption,Resource,Duration,Complete)
    // g.setShowStartDate(1); // Show/Hide Start Date(0/1)
    // g.setShowEndDate(1); // Show/Hide End Date(0/1)
    g.setDateInputFormat('yyyy-mm-dd'); // Set format of input dates ('mm/dd/yyyy', 'dd/mm/yyyy', 'yyyy-mm-dd')
    g.setDateDisplayFormat('default'); // Set format to display dates ('mm/dd/yyyy', 'dd/mm/yyyy', 'yyyy-mm-dd')
    g.setFormatArr("day", "week", "month", "quarter"); // Set format options (up
    // to 4 :
    // "minute","hour","day","week","month","quarter")
    if (ganttPlanningScale) {
      g.setFormat(ganttPlanningScale, true);
    }
    if (dijit.byId('selectBaselineBottom')) {
      g.setBaseBottomName(dijit.byId('selectBaselineBottom').get('displayedValue'));
    }
    if (dijit.byId('selectBaselineTop')) {
      g.setBaseTopName(dijit.byId('selectBaselineTop').get('displayedValue'));
    }
    g.setStartDateView(startDateView);
    g.setEndDateView(endDateView);
    if (dijit.byId('criticalPathPlanning')) g.setShowCriticalPath(dijit.byId('criticalPathPlanning').get('checked'));
    if (dijit.byId('criticalPathPlanning')) {
      if (dijit.byId('criticalPathPlanning').get('value') == 'on') {
        g.setShowCriticalPath(true);
      }
    }
    var contentNode = dojo.byId('gridContainerDiv');
    if (contentNode) {
      g.setWidth(dojo.style(contentNode, "width"));
    }
    arrProjectStart = {};
    arrayVisible = new Array();
  }
  jsonData = dojo.byId('planningJsonData');
  // Error in jsonData
  if (jsonData.innerHTML.indexOf('{"identifier"') < 0 || jsonData.innerHTML.indexOf('{"identifier":"id", "items":[ ],"totalRows":"0"') >= 0) {
    if (dijit.byId('leftGanttChartDIV')) dijit.byId('leftGanttChartDIV').set('content', null);
    if (dijit.byId('rightGanttChartDIV')) dijit.byId('rightGanttChartDIV').set('content', null);
    if (dijit.byId('topGanttChartDIV')) dijit.byId('topGanttChartDIV').set('content', null);
    if (jsonData.innerHTML.length > 10 && jsonData.innerHTML.indexOf('{"identifier":"id", "items":[ ],"totalRows":"0"') < 0) {
      showAlert(jsonData.innerHTML);
    } else {
      dojo.byId("leftGanttChartDIV").innerHTML = '<div class="labelMessageEmptyArea" style="top:42px;">'
        + i18n('ganttMsgLeftPart') + '</div>';
      dojo.byId("rightGanttChartDIV").innerHTML = '<div class="labelMessageEmptyArea" style="top:0px;">'
        + i18n('ganttMsgRightPart') + '</div>';
    }
    hideWait();
    drawGanttInProgress = false;
    return;
  }
  var now = formatDate(new Date());
  // g.AddTaskItem(new JSGantt.TaskItem( 0, 'project', '', '', 'ff0000', '',
  // 0, '', '10', 1, '', 1, '' , 'test'));
  // Parse the jsonData and set Store values
  if (g && jsonData) {
    try {
      var store = JSON.parse(jsonData.innerHTML);
    } catch (e) {
      consoleTraceLog("ERROR Parsing jsonData in drawGantt()");
      consoleTraceLog(jsonData.innerHTML);
      hideWait();
      return;
    }
    var items = store.items;
    var totalRows = store.totalRows;              // number on lines in the Query
    var fullLines = store.fullLines;              // number of lines with complete data 
    var firstFullLine = store.firstFullLine;      // position of the first line with complete data 
    var lastFullLine = store.lastFullLine;        // position of the last line with complete data 
    var hiddenLines = store.hiddenLines;          // number of line returned with partial data because hidden (wbs closed)
    var firstHiddenLine = store.firstHiddenLine;  // position of first line returned with partial data because hidden (wbs closed) 
    var lastHiddenLine = store.lastHiddenLine;    // position of last line returned with partial data because hidden (wbs closed) 
    var partialLines = store.partialLines;         // number of lines returned with partial data (whatever the reason)
    var needRefresh = store.needRefresh;          // should refresh lines ?
    var immediateRefresh = store.immediateRefresh;// immediateRefresh, must display lines
    if (items.length && needRefresh == '1') {
      //      var firstNextLine=(hiddenLines>0)?firstHiddenLine:(parseInt(lastFullLine)+1);
      //      var refreshFunc=function() {refreshPlanningLines(firstNextLine,getPageLinesCount());};
      //      setTimeout(refreshFunc,10);
      var firstNextLine = (hiddenLines > 0) ? firstHiddenLine : (parseInt(lastFullLine) + 1);
      refreshPlanningLines(firstNextLine, getPageLinesCount());
    }
    // var arrayKeys=new Array();
    var keys = "";
    var currentResource = null;
    //    if(dojo.byId('portfolioPlanning')){
    //      for(var j=0;j <items.length; j++){
    //        var item = items[j];
    //        if(item.reftype == 'Milestone'){
    //          items[j-1]+=item;
    //        }
    //      }
    //    }
    // Treat all lines
    for (var i = (items.length) - 1; i >= 0; i--) {
      var item = items[i];
      if (item.id == 0 && item.msgErrorDisplay) { continue; }
      var wbs = item.wbssortable;
      if ((item.hidden == undefined || item.hidden == "0" || item.hidden == "" || !item.hidden) && wbs && wbs != undefined) {
        while (wbs.length >= 5 && arrayVisible.indexOf(wbs) == -1) {
          arrayVisible.push(wbs);
          wbs = wbs.substring(0, wbs.length - 6);
        }
      }
    }
    for (var i = 0; i < items.length; i++) {
      var item = items[i];
      if (item.id == 0 && item.msgErrorDisplay) {
        var msg = item.msgErrorDisplay,
          displayLimited = true;
        break;
      }
      if (item.wbssortable && arrayVisible.length > 0 && arrayVisible.indexOf(item.wbssortable) < 0) continue;
      // var topId=(i==0)?'':item.topid;
      var topId = item.topid;
      // pStart : start date of task
      var pStart = now;
      var pStartFraction = 0;
      pStart = (trim(item.initialstartdate) != "") ? item.initialstartdate : pStart;
      pStart = (trim(item.validatedstartdate) != "") ? item.validatedstartdate : pStart;
      pStart = (trim(item.plannedstartdate) != "") ? item.plannedstartdate : pStart;
      pStart = (trim(item.realstartdate) != "") ? item.realstartdate : pStart;
      pStart = (trim(item.plannedstartdate) && trim(item.realstartdate) && item.plannedstartdate < item.realstartdate && parseFloat(item.leftwork) > 0) ? item.plannedstartdate : pStart;
      if (trim(item.plannedstartdate) != "" && trim(item.realenddate) == "") {
        pStartFraction = item.plannedstartfraction;
      }
      // If real work in the future, don't take it in account
      if (trim(item.plannedstartdate) && trim(item.realstartdate)
        && item.plannedstartdate < item.realstartdate
        && item.realstartdate > now) {
        pStart = item.plannedstartdate;
      }
      // PBER - Display project after validated start date when planning is not
      // calculated yet
      if (dojo.byId('projectNotStartBeforeValidatedDate') && dojo.byId('projectNotStartBeforeValidatedDate').value == 1) {
        if (item.reftype == 'Project') {
          arrProjectStart[item.refid] = item.validatedstartdate;
        } else if (!trim(item.plannedstartdate) && !trim(item.realstartdate)) {
          if (arrProjectStart[item.idproject] && arrProjectStart[item.idproject] != undefined) {
            pStart = arrProjectStart[item.idproject];
          }
        }
      }
      // pEnd : end date of task
      var pEnd = now;
      // var pEndFraction = 1;
      pEnd = (trim(item.initialenddate) != "") ? item.initialenddate : pEnd;
      pEnd = (trim(item.validatedenddate) != "") ? item.validatedenddate : pEnd;
      pEnd = (trim(item.plannedenddate) != "") ? item.plannedenddate : pEnd;

      pRealEnd = "";
      pPlannedStart = "";
      pWork = "";
      if (dojo.byId('resourcePlanning')) {
        pRealEnd = item.realenddate;
        pPlannedStart = item.plannedstartdate;
        if (pEnd == item.validatedenddate && !item.plannedenddate && item.peplannedend) pEnd = item.peplannedend;
        pWork = item.leftworkdisplay;
        g.setSplitted(true);
      } else if (dojo.byId('contractGantt') && item.reftype == 'Milestone') {
        pEnd = item.realstartdate;
      } else {
        pEnd = (trim(item.realenddate) != "") ? item.realenddate : pEnd;
      }
      if (pEnd < pStart)
        pEnd = pStart;
      //
      var realWork = parseFloat(item.realwork);
      var plannedWork = parseFloat(item.plannedwork);
      var validatedWork = parseFloat(item.validatedwork);
      var progress = 0;
      if (item.isglobal && item.isglobal == 1 && item.progress) {
        progress = item.progress;
      } else {
        progress = item.progress;
        if (plannedWork > 0 && item.idplanningmode != 8 && item.idplanningmode != 14) { // Not calculate for FDUR
          progress = Math.round(100 * realWork / plannedWork);
        } else {
          if (item.done == 1) {
            progress = 100;
          }
        }
      }
      // pGroup : is the task a group one ?
      var pGroup = (item.elementary == '0') ? 1 : 0;
      // MODIF qCazelles - GANTT
      if (item.reftype == 'Project' || item.reftype == 'Fixed' || item.reftype == 'Replan' || item.reftype == 'Construction' || item.reftype == 'ProductVersionhasChild' || item.reftype == 'ComponentVersionhasChild' || item.reftype == 'SupplierContracthasChild' || item.reftype == 'ClientContracthasChild' || item.reftype == 'ActivityhasChild') pGroup = 1;
      // END MODIF qCazelles - GANTT
      var pobjecttype = '';
      var pHealthStatus = '';
      var pQualityLevel = '';
      var pTrend = '';
      var pExtRessource = '';
      var pDurationContract = '';
      var pOverallProgress = '';
      if (dojo.byId('contractGantt') && item.reftype != 'Milestone') {
        pExtRessource = item.externalressource;
        pDurationContract = item.duration;
        pobjecttype = item.objecttype;
      }
      if (dojo.byId('portfolio')) {
        pHealthStatus = item.health;
        pQualityLevel = item.quality;
        pTrend = item.trend;
        pOverallProgress = item.overallprogress;
      }

      if (dojo.byId('versionsPlanning')) {
        pobjecttype = item.objecttype;
      }

      // runScript : JavaScript to run when click on task (to display the
      // detail of the task)
      var runScript = "";
      if (!(dojo.byId('contractGantt') && item.reftype == 'Milestone')) {
        runScript = "runScript('" + item.reftype + "','" + item.refid + "','" + item.id + "');";
      }
      elementIdRef = " \' " + item.reftype + " \',\' " + item.refid + "\',\'" + item.id + " \' ";
      if (!(dojo.byId('contractGantt'))) {
        var contextMenu = "runScriptContextMenu('" + item.reftype + "','" + item.refid + "','" + item.id + "');";
      }

      // display Name of the task
      var pName = ((showWBS) ? item.wbs : '') + " " + htmlDecode(item.refname); // for testeing
      // purpose, add
      // wbs code
      // var pName=item.refname;
      // display color of the task bar
      var pColor = (pGroup) ? '003000' : '50BB50'; // Default green
      var pElementaryColor = '50BB50';
      var pColorBlindColor = (pGroup) ? '#50BB50' : '#67ff00';
      var pElementaryBlindColor = '#67ff00';
      var pColorBlindTaskColor = '67ff00';
      var pElementaryBlindTaskColor = '67ff00';
      if (!pGroup && item.notplannedwork > 0) { // Some left work not planned : purple
        pColor = '9933CC';
        pElementaryColor = pColor;
        pColorBlindColor = '#BB5050';
        pElementaryBlindColor = pColorBlindColor;
      } else if (trim(item.validatedenddate) != "" && item.validatedenddate < pEnd) { // Not respected constraints end date : red
        if (item.reftype != 'Milestone' && (!item.assignedwork || item.assignedwork == 0) && (!item.leftwork || item.leftwork == 0) && (!item.realwork || item.realwork == 0)) {
          pColor = (pGroup) ? '650000' : 'BB9099';
          pElementaryColor = 'BB9099';
          pColorBlindColor = (pGroup) ? '#63226b' : 'linear-gradient(45deg, #63226b 5%, #9a3ec9 5%, #9a3ec9 45%, #63226b 45%, #63226b 55%, #9a3ec9 55%, #9a3ec9 95%, #63226b 95%);';
          pElementaryBlindColor = 'linear-gradient(45deg, #63226b 5%, #9a3ec9 5%, #9a3ec9 45%, #63226b 45%, #63226b 55%, #9a3ec9 55%, #9a3ec9 95%, #63226b 95%);';
          pColorBlindTaskColor = '9a3ec9';
          pElementaryBlindTaskColor = pColorBlindTaskColor;
        } else {
          pColor = (pGroup) ? '650000' : 'BB5050';
          pElementaryColor = 'BB5050';
          pColorBlindColor = (pGroup) ? '#63226b' : 'linear-gradient(45deg, #63226b 5%, #9a3ec9 5%, #9a3ec9 45%, #63226b 45%, #63226b 55%, #9a3ec9 55%, #9a3ec9 95%, #63226b 95%);';
          pElementaryBlindColor = 'linear-gradient(45deg, #63226b 5%, #9a3ec9 5%, #9a3ec9 45%, #63226b 45%, #63226b 55%, #9a3ec9 55%, #9a3ec9 95%, #63226b 95%);';
          pColorBlindTaskColor = '9a3ec9';
          pElementaryBlindTaskColor = pColorBlindTaskColor;
        }
      } else if ((item.idplanningmode == 29 || item.idplanningmode == 30) && trim(item.validatedstartdate) != "" && item.validatedstartdate < pStart) {
        pColor = (item.assignedwork > 0 || item.leftwork > 0 || item.realwork > 0) ? 'BB5050' : 'BB9099';
        pElementaryColor = pColor;
        pColorBlindColor = (pGroup) ? '#9a3ec9' : 'linear-gradient(45deg, #63226b 5%, #9a3ec9 5%, #9a3ec9 45%, #63226b 45%, #63226b 55%, #9a3ec9 55%, #9a3ec9 95%, #63226b 95%);';
        pElementaryBlindColor = 'linear-gradient(45deg, #63226b 5%, #9a3ec9 5%, #9a3ec9 45%, #63226b 45%, #63226b 55%, #9a3ec9 55%, #9a3ec9 95%, #63226b 95%);';
        pColorBlindTaskColor = '9a3ec9';
        pElementaryBlindTaskColor = pColorBlindTaskColor;
      } else if (((item.idplanningmode == 8 || item.idplanningmode == 14 || item.idplanningmode == 29 || item.idplanningmode == 30) && parseInt(item.validatedduration) > 0 && parseInt(item.validatedduration) < parseInt(item.plannedduration))
        || ((item.idplanningmode == 25 || item.idplanningmode == 26) && item.plannedstartdate != item.validatedstartdate)
        || ((item.idplanningmode == 19 || item.idplanningmode == 21) && item.plannedstartdate < item.validatedstartdate)) {
        pColor = (pGroup) ? '650000' : ((item.assignedwork > 0 || item.leftwork > 0 || item.realwork > 0) ? 'BB5050' : 'BB9099');
        pElementaryColor = (item.assignedwork > 0 || item.leftwork > 0 || item.realwork > 0) ? 'BB5050' : 'BB9099';
        pColorBlindColor = (pGroup) ? '#63226b' : 'linear-gradient(45deg, #63226b 5%, #9a3ec9 5%, #9a3ec9 45%, #63226b 45%, #63226b 55%, #9a3ec9 55%, #9a3ec9 95%, #63226b 95%);';
        pElementaryBlindColor = 'linear-gradient(45deg, #63226b 5%, #9a3ec9 5%, #9a3ec9 45%, #63226b 45%, #63226b 55%, #9a3ec9 55%, #9a3ec9 95%, #63226b 95%);';
        pColorBlindTaskColor = '9a3ec9';
        pElementaryBlindTaskColor = pColorBlindTaskColor;
      } else if (!pGroup && item.reftype != 'Milestone' && (!item.assignedwork || item.assignedwork == 0) && (!item.leftwork || item.leftwork == 0) && (!item.realwork || item.realwork == 0)) { // No workassigned : greyed 
        pColor = 'AEC5AE';
        pElementaryColor = pColor;
      }

      if (pGroup && item.notplannedwork > 0) { // Some left work not planned : purple
        pElementaryColor = '9933CC';
        pElementaryBlindColor = '#BB5050';
      } else if (pGroup && item.reftype != 'Milestone' && (!item.assignedwork || item.assignedwork == 0) && (!item.leftwork || item.leftwork == 0) && (!item.realwork || item.realwork == 0)) { // No workassigned : greyed 
        pElementaryColor = 'AEC5AE';
      }

      if (item.surbooked == 1 && pColor != '9933CC') {
        pColor = 'f4bf42';
        pElementaryColor = pColor;
        pColorBlindColor = '#bfbfbf';
        pElementaryBlindColor = pColorBlindColor;
        pColorBlindTaskColor = 'bfbfbf';
        pElementaryBlindTaskColor = pColorBlindTaskColor;
      }
      // Following code is for VersionPlanning and ContractPlanning only 
      // item.redElement not defined in othjer cases
      if (item.redElement == '1') {
        pColor = (item.assignedwork > 0 || item.leftwork > 0 || item.realwork > 0) ? 'BB5050' : 'BB9099';
        pElementaryColor = pColor;
        pColorBlindColor = (pGroup) ? '#9a3ec9' : 'linear-gradient(45deg, #63226b 5%, #9a3ec9 5%, #9a3ec9 45%, #63226b 45%, #63226b 55%, #9a3ec9 55%, #9a3ec9 95%, #63226b 95%);';
        pElementaryBlindColor = 'linear-gradient(45deg, #63226b 5%, #9a3ec9 5%, #9a3ec9 45%, #63226b 45%, #63226b 55%, #9a3ec9 55%, #9a3ec9 95%, #63226b 95%);';
        pColorBlindTaskColor = '9a3ec9';
        pElementaryBlindTaskColor = pColorBlindTaskColor;
      } else if (item.redElement == '0') {
        pColor = '50BB50';
        pElementaryColor = pColor;
        pColorBlindColor = (pGroup) ? '#50BB50' : '#67ff00';
        pElementaryBlindColor = '#67ff00';
        pColorBlindTaskColor = '67ff00';
        pElementaryBlindTaskColor = pColorBlindTaskColor;
      }
      // Color for late from inheritedEndDate
      if (trim(item.validatedenddate) == "" && trim(item.inheritedenddate) != "" && item.inheritedenddate < pEnd) {
        if (item.assignedwork > 0) pColor = 'DA70D6';    // Orchid
        else pColor = 'DDA0DD';    // Plum
        pElementaryColor = pColor;
      }
      // gautier #3925
      if (trim(item.validatedenddate) != "" && item.done == 0 && item.notplannedwork == 0) {
        var today = (new Date()).toISOString().substr(0, 10);
        var endDate = item.validatedenddate.substr(0, 10);
        if (endDate < today) {
          if (item.reftype == "Project") {
            pColor = '650000';
            pColorBlindColor = '#63226b';
            pElementaryBlindColor = pColorBlindColor;
            pColorBlindTaskColor = '63226b';
          } else {
            pColor = (item.assignedwork > 0 || item.leftwork > 0 || item.realwork > 0) ? 'BB5050' : 'BB9099';
            pColorBlindColor = (pGroup) ? '#9a3ec9' : 'linear-gradient(45deg, #63226b 5%, #9a3ec9 5%, #9a3ec9 45%, #63226b 45%, #63226b 55%, #9a3ec9 55%, #9a3ec9 95%, #63226b 95%);';
            pElementaryBlindColor = 'linear-gradient(45deg, #63226b 5%, #9a3ec9 5%, #9a3ec9 45%, #63226b 45%, #63226b 55%, #9a3ec9 55%, #9a3ec9 95%, #63226b 95%);';
            pColorBlindTaskColor = '9a3ec9';
          }
          pElementaryColor = pColor;
          pElementaryBlindTaskColor = pColorBlindTaskColor;
        }
      }
      var pItemColor = item.color;
      // pMile : is it a milestone ?
      var pMile = (item.reftype == 'Milestone') ? 1 : 0;
      if (pMile) {
        pStart = pEnd;
      }
      pClass = item.reftype;
      pId = item.refid;
      pScope = "Planning_" + pClass + "_" + pId;
      pOpen = (item.collapsed == '1') ? '0' : '1';
      var pResource = item.resource;
      var pCaption = "";

      if (dojo.byId('listShowResource')) {
        if (dojo.byId('listShowResource').checked) {
          pCaption = pResource;
        }
      }
      if (dijit.byId('displayRessourceCheck')) {
        listShowResource = dijit.byId('displayRessourceCheck').get('value');
        if (listShowResource == 'on') {
          pCaption = pResource;
        } else {
          pCaption = "";
        }
      }
      if (dijit.byId('showRessourceComponentVersion')) {
        listShowResource = dijit.byId('showRessourceComponentVersion').get('value');
        if (listShowResource == 'on') {
          pCaption = pResource;
        } else {
          pCaption = "";
        }
      }
      if (dojo.byId('showRessourceComponentVersion')) {
        if (dojo.byId('showRessourceComponentVersion').checked) {
          pCaption = pResource;
        }
      }

      if (dojo.byId('listShowLeftWork')
        && dojo.byId('listShowLeftWork').checked) {
        if (item.leftwork > 0) {
          pCaption = item.leftworkdisplay;
        } else {
          pCaption = "";
        }
      }

      if (dijit.byId('listShowLeftWork')) {
        showLeftWork = dijit.byId('listShowLeftWork').get('value');
        if (showLeftWork == 'on') {
          pCaption = item.leftworkdisplay;
        } else {
          pCaption = "";
        }
      }

      var pDepend = item.depend;
      topKey = "#" + topId + "#";
      curKey = "#" + item.id + "#";
      if (keys.indexOf(topKey) == -1) {
        topId = '';
      }
      if (item.paused == 1) {
        pColor = 'A0A0A0';
        pElementaryColor = pColor;
        pColorBlindColor = '#4d4d4d';
        pElementaryBlindColor = pColorBlindColor;
        pItemColor = 'A0A0A0';
        pColorBlindTaskColor = '4d4d4d';
        pElementaryBlindTaskColor = pColorBlindTaskColor;
      }
      keys += "#" + curKey + "#";
      pColorBaselineBottom = (dojo.byId('colorBaselineBottomValue')) ? dojo.byId('colorBaselineBottomValue').value : "";
      pColorBaselineUpper = (dojo.byId('colorBaselineUpperValue')) ? dojo.byId('colorBaselineUpperValue').value : "";

      if (pColor == 'BB5050' && !(item.assignedwork > 0 || item.leftwork > 0 || item.realwork > 0)) {
        pColor = 'BB9099';
        pElementaryColor = pColor;
      }
      var pIdPlanningMode = item.idplanningmode;
      var pIdStatus = item.idstatus;
      var newTaskItem = new JSGantt.TaskItem(item, planningType, pName, pStart, pEnd, pColor,
        runScript, contextMenu, progress, topId, pCaption, pScope, pRealEnd, pPlannedStart,
        pHealthStatus, pQualityLevel, pTrend, pOverallProgress, pobjecttype, pExtRessource, pIdPlanningMode, pIdStatus,
        pDurationContract, elementIdRef, pColorBlindColor, pColorBlindTaskColor, pColorBaselineBottom, pColorBaselineUpper, pElementaryColor, pElementaryBlindColor, pElementaryBlindTaskColor)
      if (onlyRefresh == true) g.ReplaceTaskItem(newTaskItem);
      else g.AddTaskItem(newTaskItem);
    }
    showGanttOneLineWaitRefresh = false;
    lineRefreshArray = {};
    dojo.query(".inputDateGantBarResize").forEach(function(node, index, nodelist) {
      node.value = '';
    });
    if (onlyRefresh == true || immediateRefresh == 1) {
      JSGantt.processRows(g.getList(), 0, -1, 1, 1);
      if (immediateRefresh == '1') {
        showGanttLinesVisible();
      }
      if (typeof planningSearchRefreshAll == 'function') planningSearchRefreshAll();
      return;
    }
    g.Draw();
    //g.DrawDependencies();
    if (displayLimited !== undefined && displayLimited == true) {
      drawLimitedDisplayMessage(msg);
    }
  } else {
    drawGanttInProgress = false;
    // showAlert("Gantt chart not defined");
    return;
  }
  if (dojo.byId('leftGanttChartDIV') && (dojo.byId('leftGanttChartDIV').offsetWidth > dojo.byId('listHeaderDiv').offsetWidth - 15)) {
    var resizeWidth = dojo.byId('listHeaderDiv').offsetWidth - 15;
    dijit.byId('leftGanttChartDIV').resize({ w: resizeWidth });
    dijit.byId("centerDiv").resize();
  }
  highlightPlanningLine();
  //  for (var i=0; i<g.getList().length;i++) {
  //    setTimeout("showGanttLines("+(i)+","+(i)+");",100*i);
  //    //setTimeout("showGanttLines("+(g.getList().length-1-i)+","+(g.getList().length-1-i)+");",100*i); // Reverse
  //  }
  drawGanttInProgress = false;
  showGanttLinesVisible();
  if (typeof planningSearchRefreshAll == 'function') planningSearchRefreshAll();
}

//==================================================================
//Draw workPlan gantt chart - Use Lazy Loading and Lazy rendering
//==================================================================
/**
* Draw workPlan gantt chart using jsGantt
* 
* @return
*/
function drawWorkPlanGantt(onlyRefresh) {
  if (onlyRefresh == undefined) onlyRefresh = false;

  var startDateView = (dojo.byId('projectDate') && dojo.byId('projectDate').checked) ? null : new Date();
  if (dijit.byId('startDatePlanView') && dojo.byId('projectDate')) {
    if (!dojo.byId('projectDate').checked) {
      startDateView = dijit.byId('startDatePlanView').get('value');
    }
  }
  var endDateView = null;
  if (dijit.byId('endDatePlanView') && dojo.byId('projectDate')) {
    if (!dojo.byId('projectDate').checked) {
      endDateView = dijit.byId('endDatePlanView').get('value');
    }
  }

  var gFormat = "day";
  if (gwp) {
    gFormat = gwp.getFormat();
  }
  // Only first display, refresh JSGantt object
  if (!onlyRefresh) {
    lineRefreshArray = {};
    gwp = new JSGantt.GanttChart('gwp', dojo.byId('workPlanGanttChartDIV'), gFormat);
    gwp.setDateInputFormat('yyyy-mm-dd'); // Set format of input dates ('mm/dd/yyyy', 'dd/mm/yyyy', 'yyyy-mm-dd')
    gwp.setDateDisplayFormat('default'); // Set format to display dates ('mm/dd/yyyy', 'dd/mm/yyyy', 'yyyy-mm-dd')
    gwp.setFormatArr("day", "week", "month", "quarter"); // Set format options (up
    if (ganttPlanningScale) {
      gwp.setFormat(ganttPlanningScale, true);
    }
    gwp.setStartDateView(startDateView);
    gwp.setEndDateView(endDateView);
    var contentNode = dojo.byId('workPlanGridContainerDiv');
    if (contentNode) {
      gwp.setWidth(dojo.style(contentNode, "width"));
    }
    arrProjectStart = {};
    arrayVisible = new Array();
  }
  jsonData = dojo.byId('workPlanJsonData');
  // Error in jsonData
  if (jsonData.innerHTML.indexOf('{"identifier"') < 0 || jsonData.innerHTML.indexOf('{"identifier":"id", "items":[ ],"totalRows":"0"') >= 0) {
    if (dijit.byId('workPlanRightGanttChartDIV')) dijit.byId('workPlanRightGanttChartDIV').set('content', null);
    if (dijit.byId('workPlanTopGanttChartDIV')) dijit.byId('workPlanTopGanttChartDIV').set('content', null);
    if (jsonData.innerHTML.length > 10 && jsonData.innerHTML.indexOf('{"identifier":"id", "items":[ ],"totalRows":"0"') < 0) {
      if (dojo.byId('planningJsonData')) {
        dojo.byId("workPlanRightGanttChartDIV").innerHTML = '<div style="background:#FFDDDD;font-size:150%;color:#808080;text-align:center;padding:15px 0px;width:100%;">'
          + jsonData.innerHTML + '</div>';
      } else {
        if (dojo.byId('confirmCheckNoParam')) {
          dojo.byId("workPlanRightGanttChartDIV").innerHTML = '<div align="center" class="labelMessageEmptyAreaTop">'
            + i18n('workPlanMsgNoAutoRefresh') + '</div>';
          var confirm = function() {
            var callback = function() {
              activeRefreshWorkPlan = true;
              if (dojo.byId('skipLimitCalculWeight')) dojo.byId('skipLimitCalculWeight').value = false;
            };
            if (dojo.byId("workPlanRightGanttChartDIV")) {
              dojo.byId("workPlanRightGanttChartDIV").innerHTML = '<div style="width: 100%;position: absolute;top: 50%;" align="center"><img src="../view/css/images/spinner02.gif" />&nbsp;&nbsp;<i>' + i18n("messagePreview") + '</i></div>';
            }
            url = getJsonPlanningUrl('workPlan');
            url += '&skipNoParamCheck=true';
            if (dojo.byId('skipLimitCalculWeight')) dojo.byId('skipLimitCalculWeight').value = true;
            loadContent(url, 'workPlanJsonData', 'listForm', false, null, null, null, callback);
          };
          if (dojo.byId('skipLimitCalculWeight')) dojo.byId('skipLimitCalculWeight').value = true;
          activeRefreshWorkPlan = false;
          showQuestion(i18n('confirmWorkPlanNoParam'), confirm, function() {});
        } else if (dojo.byId('confirmCheckCalculTime')) {
          dojo.byId("workPlanRightGanttChartDIV").innerHTML = '<div align="center" class="labelMessageEmptyAreaTop">'
            + i18n('workPlanMsgNoAutoRefresh') + '</div>';
          var confirm = function() {
            var callback = function() {
              activeRefreshWorkPlan = true;
              if (dojo.byId('skipLimitCalculWeight')) dojo.byId('skipLimitCalculWeight').value = false;
            };
            if (dojo.byId("workPlanRightGanttChartDIV")) {
              dojo.byId("workPlanRightGanttChartDIV").innerHTML = '<div style="width: 100%;position: absolute;top: 50%;" align="center"><img src="../view/css/images/spinner02.gif" />&nbsp;&nbsp;<i>' + i18n("messagePreview") + '</i></div>';
            }
            url = getJsonPlanningUrl('workPlan');
            url += '&skipNoParamCheck=true';
            if (dojo.byId('skipLimitCalculWeight')) dojo.byId('skipLimitCalculWeight').value = true;
            loadContent(url, 'workPlanJsonData', 'listForm', false, null, null, null, callback);
          };
          if (dojo.byId('skipLimitCalculWeight')) dojo.byId('skipLimitCalculWeight').value = true;
          activeRefreshWorkPlan = false;
          showQuestion(i18n('confirmWorkPlanCalculToLong'), confirm, function() {});
        } else {
          showAlert(jsonData.innerHTML);
        }
      }
    } else {
      dojo.byId("workPlanRightGanttChartDIV").innerHTML = '<div align="center" class="labelMessageEmptyAreaCentered">'
        + i18n('workPlanMsgRightPart') + '</div>';
    }
    hideWait();
    return;
  }

  var now = formatDate(new Date());
  // Parse the jsonData and set Store values
  if (gwp && jsonData) {
    try {
      var store = JSON.parse(jsonData.innerHTML);
    } catch (e) {
      consoleTraceLog("ERROR Parsing jsonData in drawWorkPlanGantt()");
      consoleTraceLog(jsonData.innerHTML);
      hideWait();
      return;
    }
    var items = store.items;
    var keys = "";
    var currentResource = null;
    // Treat all lines
    for (var i = (items.length) - 1; i >= 0; i--) {
      var item = items[i];
      if (item.id == 0 && item.msgErrorDisplay) { continue; }
      var wbs = item.wbssortable;
      if ((item.hidden == undefined || item.hidden == "0" || item.hidden == "" || !item.hidden) && wbs && wbs != undefined) {
        while (wbs.length >= 5 && arrayVisible.indexOf(wbs) == -1) {
          arrayVisible.push(wbs);
          wbs = wbs.substring(0, wbs.length - 6);
        }
      }
    }
    for (var i = 0; i < items.length; i++) {
      var item = items[i];
      if (item.id == 0 && item.msgErrorDisplay) {
        var msg = item.msgErrorDisplay,
          displayLimited = true;
        break;
      }
      if (item.wbssortable && arrayVisible.length > 0 && arrayVisible.indexOf(item.wbssortable) < 0) continue;
      var topId = item.topid;
      var pStart = now;
      var pStartFraction = 0;
      pStart = (trim(item.initialstartdate) != "") ? item.initialstartdate : pStart;
      pStart = (trim(item.validatedstartdate) != "") ? item.validatedstartdate : pStart;
      pStart = (trim(item.plannedstartdate) != "") ? item.plannedstartdate : pStart;
      pStart = (trim(item.realstartdate) != "") ? item.realstartdate : pStart;
      pStart = (trim(item.plannedstartdate) && trim(item.realstartdate) && item.plannedstartdate < item.realstartdate && parseFloat(item.leftwork) > 0) ? item.plannedstartdate : pStart;
      if (trim(item.plannedstartdate) != "" && trim(item.realenddate) == "") {
        pStartFraction = item.plannedstartfraction;
      }
      var pEnd = now;
      pEnd = (trim(item.initialenddate) != "") ? item.initialenddate : pEnd;
      pEnd = (trim(item.validatedenddate) != "") ? item.validatedenddate : pEnd;
      pEnd = (trim(item.plannedenddate) != "") ? item.plannedenddate : pEnd;

      pRealEnd = "";
      pPlannedStart = "";
      pRealEnd = item.realenddate;
      pPlannedStart = item.plannedstartdate;
      if (pEnd == item.validatedenddate && !item.plannedenddate && item.peplannedend) pEnd = item.peplannedend;

      if (pEnd < pStart)
        pEnd = pStart;
      var pName = htmlDecode(item.refname);
      var pScope = "WorkPlan_" + item.reftype + "_" + item.refid;
      //     pOpen = (item.collapsed == '1') ? '0' : '1';
      //     topKey = "#" + topId + "#";
      //     curKey = "#" + item.id + "#";
      //     if (keys.indexOf(topKey) == -1) {
      //       topId = '';
      //     }
      var newWorkPlanItem = new JSGantt.WorkPlanItem(item, pName, pScope, pStart, pEnd, topId, pRealEnd, pPlannedStart);
      if (onlyRefresh == true) {
        if (gwp.getArrayLocationByID(item.id, true) !== null) {
          gwp.ReplaceWorkPlanItem(newWorkPlanItem);
        } else {
          gwp.InsertWorkPlanItem(newWorkPlanItem);
        }
      } else {
        gwp.AddWorkPlanItem(newWorkPlanItem);
      }
    }
    if (onlyRefresh == false) {
      gwp.DrawWorkPlan();
      if (displayLimited !== undefined && displayLimited == true) {
        drawLimitedDisplayMessage(msg);
      }
    }
  } else {
    return;
  }
}

var delayShowGanttLines = null;
var delayShowGanttLinesBefore = null;
var delayShowGanttLinesAfter = null;
var delayHideGanttLines = null;
function showGanttLines(start, length, prepareAfter, prepareBefore) {
  if (prepareBefore == undefined || prepareBefore == null) prepareBefore = 0;
  if (prepareAfter == undefined || prepareAfter == null) prepareAfter = 0;
  if (start < 0 && start + length <= 0) return; // Skip trying to get before line zero
  if (dojo.byId('portfolio')) {
    start -= prepareBefore;
    length += prepareAfter + prepareBefore;
  }
  if (prepareAfter || prepareBefore) showWait();
  var vList = g.getList();
  if (start == null || start < 0) start = 0;
  if (start > vList.length - 1) start = vList.length - 1;
  var min = null;
  var max = null;
  var cpt = 0;
  for (var i = start; i < vList.length; i++) {
    if (!vList[i]) continue;
    if (vList[i].getVisible() == 1 || (dojo.byId('portfolio') && vList[i].getMile())) {
      pID = vList[i].getID();
      if (min == null) min = i;
      max = i;
      if (!dojo.byId('portfolio') || !vList[i].getMile()) cpt++;
      setTimeout(showGanttOneLine(i, pID), 10);
      if (cpt >= length) {
        break;
      }
    }
  }
  if (start <= 1) adjustSpecificDaysHeight();
  if (prepareAfter > 0 && prepareBefore > 0) setTimeout("g.DrawDependencies();", 1);
  hideWait();
  if (dojo.byId("portfolioPlanning")) { return; }
  if (prepareAfter) {
    if (delayShowGanttLinesAfter) clearTimeout(delayShowGanttLinesAfter);
    delayShowGanttLinesAfter = setTimeout("showGanttLines(" + max + "," + prepareAfter + ",0,0);", 50);
  }
  if (prepareBefore) {
    if (delayShowGanttLinesBefore) clearTimeout(delayShowGanttLinesBefore);
    delayShowGanttLinesBefore = setTimeout("showGanttLines(" + (start - prepareBefore) + "," + prepareBefore + ",0,0);", 60);
  }
}

function hideGanttLines(start, length, prepareAfter, prepareBefore) {
  return; // Testing : remove delete that erases the end of the file
  var vList = g.getList();
  if (start == null || start < 0) start = 0;
  if (start > vList.length - 1) start = vList.length - 1;
  // Clear before
  var cptBefore = 0;
  for (var i = start; i >= 0; i--) {
    if (!vList[i]) continue;
    if (vList[i].getVisible() == 1) cptBefore++;
    if (cptBefore < prepareBefore) continue;
    pID = vList[i].getID();
    setTimeout(hideGanttOneLine(i, pID), 10);
  }
  // Clear after
  var cptAfter = 0;
  for (var i = start; i < vList.length; i++) {
    if (!vList[i]) continue;
    if (vList[i].getVisible() == 1) cptAfter++;
    if (cptAfter < length + prepareAfter) continue;
    pID = vList[i].getID();
    setTimeout(hideGanttOneLine(i, pID), 10);
  }
}

showGanttOneLineWaitRefresh = false;
lineRefreshArray = {};
function showGanttOneLine(i, pID) {
  if (showHiddenLevelCondensed != '1' && dojo.byId('taskbar_' + pID) && g.getLineByID(pID).getClass() != 'Meeting') {
    return;
  }
  if (dojo.byId("portfolioPlanning") && g.getLineByID(pID).getClass() == 'Milestone') {
    if (g.getLineByID(pID).getStart() < g.getStartDateView()) {
      return; // On portfolio skip display of milestone that start before display start
    }
  }
  if (showGanttOneLineWaitRefresh) {
    if (dojo.byId("portfolioPlanning") && g.getLineByID(pID).getClass() == 'Milestone') return;
    if (lineRefreshArray[pID] && lineRefreshArray[pID] != undefined) lineRefreshArray[pID] += 1;
    else lineRefreshArray[pID] = 1;
    if (lineRefreshArray[pID] > 10) {
      hideWait();
      return;
    }
    setTimeout(function() { showGanttOneLine(i, pID) }, 500);
    return;
  }
  lineRefreshArray = {};
  if (dojo.byId("childrow_" + pID) && !dojo.byId("childrow_" + pID + "_partial")) {
    return;
  }
  var vList = g.getList();
  if ((dojo.byId("childrow_" + pID) && dojo.byId("childrow_" + pID + "_partial")) || vList[i].isPartialQuery() == 1) {
    if (dojo.byId("portfolioPlanning") && g.getLineByID(pID).getClass() == 'Milestone') {
      // Do not stop here for Milestones on Portfolio, will continue
    } else {
      var clBk = function() {
        showGanttOneLineWaitRefresh = false;
        showGanttOneLine(i, pID);
      };
      showGanttOneLineWaitRefresh = true;
      refreshPlanningLines(i, getPageLinesCount(), true, clBk);
      return;
    }
  }
  if (!g.getLineByID(pID)) {
    return;
  }
  var background = (isColorBlind == 'YES') ? g.getLineByID(pID).getActivityBlindColor() : g.getLineByID(pID).getActivityColor();
  var colorAct = false;
  if (dojo.byId('showColorActivity') && dojo.byId('showColorActivity').checked) colorAct = true;
  if (dijit.byId('showColorActivity') && dijit.byId('showColorActivity').get('value') == 'on') colorAct = true;
  if (!(dojo.byId("portfolioPlanning") && g.getLineByID(pID).getClass() == 'Milestone')) {
    if (dojo.byId("child_" + pID)) dojo.byId("child_" + pID).innerHTML = JSGantt.drawLeftPart(i);
    if (dojo.byId("childgrid_" + pID)) dojo.byId("childgrid_" + pID).innerHTML = JSGantt.drawRightPart(i);
  }
  if (colorAct && dojo.byId("child_" + pID)) {
    if (background) dojo.byId("child_" + pID).style.background = '#' + background;
  }
  if (dojo.byId("portfolioPlanning") && g.getLineByID(pID).getClass() == 'Milestone') {
    var idParent = vList[i].getParent();
    if (dojo.byId("childgrid_" + idParent)) {
      var tagParent = '<tag id="mile_' + idParent + '"></tag>';
      var value = dojo.byId("childgrid_" + idParent).innerHTML.replace(tagParent, tagParent + JSGantt.drawRightPart(i));
      dojo.byId("childgrid_" + idParent).innerHTML = value;
    }
  }
  if (g.getLineByID(pID).getClass() == 'PeriodicMeeting') {
    var parentGrid = dojo.byId("childgrid_" + pID);
    if (parentGrid) {
      var tagParent = '<tag id="meeting_' + pID + '"></tag>';
      var childHtml = '';
      for (var j = 0; j < vList.length; j++) {
        if (vList[j].getParent() == pID && vList[j].getClass() == 'Meeting') {
          childHtml += JSGantt.drawRightPart(j, true);
        }
      }
      if (childHtml) parentGrid.innerHTML = parentGrid.innerHTML.replace(tagParent, tagParent + childHtml);
    }
  } else if (g.getLineByID(pID).getGroup() && showHiddenLevelCondensed == '1') {
    var parentGrid = dojo.byId("childgrid_" + pID);
    if (parentGrid) {
      var tagParent = '<tag id="element_' + pID + '"></tag>';
      var childItems = g.getChildTaskList(pID);
      var childHtml = '';
      var contractedContext = JSGantt.getContractedContext();
      for (var j = 0; j < childItems.length; j++) {
        childHtml += JSGantt.drawRightPart(childItems[j].taskIndex, true, contractedContext);
      }
      if (childHtml) parentGrid.innerHTML = parentGrid.innerHTML.replace(tagParent, tagParent + childHtml);
    }
  }
  if (isPredecessorSuccessorEnabled()) g.DrawDependencies(true);
}
function hideGanttOneLine(i, pID) {
  if (!dojo.byId("childrow_" + pID)) return;
  dojo.byId("child_" + pID).innerHTML = "";
  dojo.byId("childgrid_" + pID).innerHTML = "";
}

var temporizedShowGanttLinesVisible = false;
var currentQueryMin = null;
function showGanttLinesVisible() {
  if (delayShowGanttLines) clearTimeout(delayShowGanttLines);
  if (delayShowGanttLinesBefore) clearTimeout(delayShowGanttLinesBefore);
  if (delayShowGanttLinesAfter) clearTimeout(delayShowGanttLinesAfter);
  if (delayHideGanttLines) clearTimeout(delayHideGanttLines);
  var container = dojo.byId('rightGanttChartDIV');
  scroll = container.scrollTop;
  height = container.offsetHeight;
  start = Math.round(scroll / 21);
  length = getVisibleLinesCount();
  var vList = g.getList();
  var min = -1;
  var minRefresh = -1;
  var max = 0;
  var cpt = 0;
  var needRefresh = false;
  for (var i = 0; i < vList.length; i++) {
    if (vList[i].getVisible() == 1) {
      //cpt++;
      if (!dojo.byId('portfolio') || !vList[i].getMile()) cpt++;
      if (min == -1 && cpt >= start) {
        min = i;
      }
      if (vList[i].isPartialQuery() && min > -1) {
        minRefresh = i;
        needRefresh = true;
        break;
      }
      if (cpt >= start + length) {
        break;
      }
    }
  }
  if (minRefresh == currentQueryMin) needRefresh = false;
  // Show lines
  if (needRefresh == false) {
    if (temporizedShowGanttLinesVisible) {
      temporizedShowGanttLinesVisible = false;
      delayShowGanttLines = setTimeout("showGanttLines(" + min + "," + length + "," + (2 * length) + "," + (1 * length) + ");", 10);
    } else {
      delayShowGanttLines = setTimeout("showGanttLines(" + min + "," + length + "," + (2 * length) + "," + (1 * length) + ");", 10);
    }
    //hideWait();
    // hides lines that are not visible any more, and not in the page before / after
    if (delayHideGanttLines) clearTimeout(delayHideGanttLines);
    delayHideGanttLines = setTimeout("hideGanttLines(" + min + "," + length + "," + 2 * length + "," + 2 * length + ");", 10000);
  } else {
    showWait();
    //STUDY THIS PART					
    //    if (! temporizedShowGanttLinesVisible) { // NOT WORKING YET
    //      temporizedShowGanttLinesVisible=true;
    //	    showWait();	  
    //      refreshPlanningLines(min,2*length, true);
    //    }
    currentQueryMin = minRefresh;
    refreshPlanningLines(minRefresh, 2 * length, true);
    //setTimeout("showGanttLinesVisible();",100);
  }
}
function getVisibleLinesCount() {
  var container = dojo.byId('rightGanttChartDIV');
  if (container) height = container.offsetHeight;
  else height = 1024;
  length = Math.round(height / 21) + 2;
  return length;
}
// Pagination size to fetch queries
function getPageLinesCount() {
  return globalPageLinesCount;
  //  var max=(5*getVisibleLinesCount())%50;
  //  var min=(2*getVisibleLinesCount());
  //  if (min>val) val=min;
  //  if (max>val && max<300) val=max;
  //  return val;
}
var alertLatencyForBigGanttConfirmed = false;
function setShowAllGanttLines() {
  var confimedFunc = function() {
    alertLatencyForBigGanttConfirmed = true;
    var callBack = function() {
      refreshJsonPlanning();
    };
    saveDataToSession('showAllGanttLines', 'true', false, callBack);
  };
  if (alertLatencyForBigGanttConfirmed) confimedFunc();
  else showConfirm(i18n('alertLatencyForBigGantt'), confimedFunc);
}

function runScript(refType, refId, id) {
  if (g) {
    var vList = g.getList();
    if (vList) {
      var vTask = null;
      for (var i = 0; i < vList.length; i++) {
        if (vList[i].getID() == id) {
          vTask = vList[i];
          break;
        }
      }
      if (vTask && dojo.byId('resourcePlanningSelectedResource')) {
        dojo.byId('resourcePlanningSelectedResource').value = vTask.getResource();
      }
      if (vTask) {
        var idProject = vTask.getProjectId();
        JSGantt.closeEditRowObjectPlanning();
        cachedEditRowPlanningClick = 'JSGantt.planningRowClickAction(\'' + id + '\', ' + refId + ', \'' + refType + '\', ' + idProject + ')';
        JSGantt.editRowObjectPlanning(id, refId, refType, idProject);
        if ((planningClickAction != 1)) {
          var buttonDetail = dojo.byId('buttonEditRowDetail');
          if (buttonDetail) {
            dojo.removeClass(buttonDetail, 'iconButtonView16 iconButtonView');
            dojo.addClass(buttonDetail, 'iconButtonNoView16 iconButtonNoView');
            dojo.setAttr(buttonDetail, 'onclick', 'hideDetailScreen();JSGantt.closeAndSelectEditRow(\'' + id + '\', ' + refId + ', \'' + refType + '\', ' + idProject + ')');
            dojo.setAttr(buttonDetail, 'title', i18n('colHideDetail'));
          }
        }
      }
    }
  }
  if (dojo.byId('paramLayoutScreen') && dojo.byId('paramLayoutScreen').value != 'multiple') return;
  if (refType == 'Fixed' || refType == 'Construction' || refType == 'Replan') {
    refType = 'Project';
  }
  // ADD by qCazelles - GANTT
  if (refType == 'ActivityhasChild') {
    refType = 'Activity';
  }
  if (refType == 'ProductVersionhasChild') {
    refType = 'ProductVersion';
  }
  if (refType == 'ComponentVersionhasChild') {
    refType = 'ComponentVersion';
  }
  if (refType == 'SupplierContracthasChild') {
    refType = 'SupplierContract';
  }
  if (refType == 'ClientContracthasChild') {
    refType = 'ClientContract';
  }
  // END ADD qCazelles - GANTT
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
    if (dojo.byId('workPlanJsonData') && dojo.byId('planningJsonData')) {
      setActionCoverListNonObj('OPEN', false);
    }
  }
  var planningType = (dojo.byId('objectClassManual').value == 'PlanningWorkPlan') ? 'Planning' : dojo.byId('objectClassManual').value;
  loadContent('objectDetail.php?planning=true&planningType=' + planningType, 'detailDiv', 'listForm', false, null, null, null, callBack);
  loadContentStream();
  highlightPlanningLine(id);
}
var ongoingRunScriptContextMenu = false;
var timeoutContextMenuWait = null;
function runScriptContextMenu(refType, refId, id) {
  if (ongoingRunScriptContextMenu) return;
  ongoingRunScriptContextMenu = true;
  const clickPos = event ? { clientX: event.clientX, clientY: event.clientY } : null;
  var objectClassManual = dojo.byId('objectClassManual').value;
  if (objectClassManual == 'PlanningWorkPlan') objectClassManual = 'Planning';
  timeoutContextMenuWait = setTimeout('showWait()', 250);
  setTimeout("document.body.style.cursor='default';", 100);
  dojo.xhrGet({
    url: "../view/planningBarDetail.php?class=" + refType + "&id=" + refId + "&scale=" + ganttPlanningScale + "&objectClassManual=" + objectClassManual + "&idAssignment=" + id + addTokenIndexToUrl(),
    load: function(data, args) {
      // ongoingRunScriptContextMenu=true;
      if (timeoutContextMenuWait) clearTimeout(timeoutContextMenuWait);
      hideWait();
      setTimeout("document.body.style.cursor='default';", 100);
      var taskbar = dijit.byId('bardiv_' + id);
      var bar = dojo.byId('bardiv_' + id);
      var line = dojo.byId('childgrid_' + id);
      var detail = dojo.byId('rightTableBarDetail');

      if (detail.style.display == 'block') {
        var pObjectClass = dojo.byId('planningBarDetailObjectClass').value;
        var pObjectId = dojo.byId('planningBarDetailObjectId').value;
        if (pObjectClass == refType && pObjectId == refId) {
          detail.style.display = 'none';
        } else {
          detail.style.display = "block";
        }
      } else {
        detail.style.display = "block";
      }
      var detailInnerHTML = detail.innerHTML;
      detail.innerHTML = data;
      detail.style.width = (parseInt(bar.style.width) + 202) + 'px';
      detail.style.left = (bar.offsetLeft - 1) + "px";

      var task = g.getLineByID(id);
      var isChanged = task.getChanged();
      if (isChanged || dojo.byId('noDataToDisplay')) {
        clearTimeout(timeoutContextMenuWait);
        detail.innerHTML = detailInnerHTML;
        detail.style.display = 'none';
        var idProject = g.getItemIdProjectByRef(refType, refId);
        bar.oncontextmenu = function(e) {
          e.preventDefault();
          return JSGantt.openPlanningContextMenu(id, refId, refType, idProject);
        };

        ongoingRunScriptContextMenu = false;

        const rect = bar.getBoundingClientRect();
        const x = (clickPos && clickPos.clientX) || (rect.left + 5);
        const y = (clickPos && clickPos.clientY) || (rect.top + 5);

        const newEvt = new MouseEvent('contextmenu', {
          bubbles: true,
          cancelable: true,
          view: window,
          clientX: x,
          clientY: y
        });
        bar.dispatchEvent(newEvt);
        return;
      }

      var tableHeight = 44;
      if (dojo.byId('planningBarDetailTable')) tableHeight = dojo.byId('planningBarDetailTable').offsetHeight
      if (dojo.byId('rightTableContainer').offsetHeight + tableHeight > (dojo.byId('rightGanttChartDIV').offsetHeight) && (line.offsetTop + 25) > dojo.byId('rightTableContainer').offsetHeight) {
        detail.style.top = (line.offsetTop - tableHeight + 1) + "px";
      } else {
        detail.style.top = (line.offsetTop + 22) + "px";
      }
      var positions = elementPosition(bar);
      var detailDiv = document.getElementById('detailDiv').clientWidth;
      var leftGanttChartDIV = document.getElementById('leftGanttChartDIV').clientWidth;
      if (detailDiv >= leftGanttChartDIV + document.getElementById('rightGanttChartDIV').clientWidth) detailDiv = 0;
      var diffSizeLeft = document.documentElement.clientWidth - document.getElementById('rightGanttChartDIV').clientWidth - detailDiv;
      var posLeft = (diffSizeLeft - (positions.viewportXLeft));
      var diffSizeRight = document.documentElement.clientWidth - detailDiv;
      var posRight = posLeft + document.getElementById('rightGanttChartDIV').clientWidth - 100;
      var halfSize = (parseInt(detail.style.width) / 2);
      dojo.query(".planningBarDetailResName").forEach(function(node, index, nodelist) {
        if (positions.viewportXRight > halfSize && positions.viewportXRight > (diffSizeRight - 50) && posRight > -50) {
          node.style.left = (posRight) + "px";
        } else if (positions.viewportXRight < halfSize && positions.viewportXRight > (diffSizeRight - 50) && posRight > -50) {
          node.style.left = (posRight) + "px";
        } else if (positions.viewportXRight < halfSize && positions.viewportXRight < (diffSizeRight - 50) && posRight > -50) {
          node.style.left = "unset";
        } else if (positions.viewportXRight > halfSize && positions.viewportXRight < (diffSizeRight - 50) && posRight > -50) {
          node.style.left = "unset";
        }
      });
      if (dojo.byId('planningBarDetailCloseButton')) {
        if (positions.viewportXRight > halfSize && (positions.viewportXRight + 150) > (diffSizeRight - 50) && posRight > -50) {
          dojo.byId('planningBarDetailCloseButton').style.left = (posRight + 63) + "px";
        } else if (positions.viewportXRight < halfSize && (positions.viewportXRight + 150) > (diffSizeRight - 50) && posRight > -50) {
          dojo.byId('planningBarDetailCloseButton').style.left = (posRight + 63) + "px";
        } else if (positions.viewportXRight < halfSize && (positions.viewportXRight + 150) < (diffSizeRight - 50) && posRight > -50) {
          dojo.byId('planningBarDetailCloseButton').style.left = "unset";
        } else if (positions.viewportXRight > halfSize && (positions.viewportXRight + 150) < (diffSizeRight - 50) && posRight > -50) {
          dojo.byId('planningBarDetailCloseButton').style.left = "unset";
        }
      }
      document.getElementById('rightGanttChartDIV').addEventListener('scroll', () => {
        var positions = elementPosition(bar);
        var detailDiv = document.getElementById('detailDiv').clientWidth;
        var leftGanttChartDIV = document.getElementById('leftGanttChartDIV').clientWidth;
        if (detailDiv >= leftGanttChartDIV + document.getElementById('rightGanttChartDIV').clientWidth) detailDiv = 0;
        var diffSizeLeft = document.documentElement.clientWidth - document.getElementById('rightGanttChartDIV').clientWidth - detailDiv;
        var posLeft = (diffSizeLeft - (positions.viewportXLeft));
        var diffSizeRight = document.documentElement.clientWidth - detailDiv;
        var posRight = posLeft + document.getElementById('rightGanttChartDIV').clientWidth - 100;
        var halfSize = (parseInt(detail.style.width) / 2);
        dojo.query(".planningBarDetailResName").forEach(function(node, index, nodelist) {
          if (positions.viewportXRight > halfSize && positions.viewportXRight > (diffSizeRight - 50) && posRight > -50) {
            node.style.left = (posRight) + "px";
          } else if (positions.viewportXRight < halfSize && positions.viewportXRight > (diffSizeRight - 50) && posRight > -50) {
            node.style.left = (posRight) + "px";
          } else if (positions.viewportXRight < halfSize && positions.viewportXRight < (diffSizeRight - 50) && posRight > -50) {
            node.style.left = "unset";
          } else if (positions.viewportXRight > halfSize && positions.viewportXRight < (diffSizeRight - 50) && posRight > -50) {
            node.style.left = "unset";
          }
        });
        if (dojo.byId('planningBarDetailCloseButton')) {
          if (positions.viewportXRight > halfSize && (positions.viewportXRight + 150) > (diffSizeRight - 50) && posRight > -50) {
            dojo.byId('planningBarDetailCloseButton').style.left = (posRight + 63) + "px";
          } else if (positions.viewportXRight < halfSize && (positions.viewportXRight + 150) > (diffSizeRight - 50) && posRight > -50) {
            dojo.byId('planningBarDetailCloseButton').style.left = (posRight + 63) + "px";
          } else if (positions.viewportXRight < halfSize && (positions.viewportXRight + 150) < (diffSizeRight - 50) && posRight > -50) {
            dojo.byId('planningBarDetailCloseButton').style.left = "unset";
          } else if (positions.viewportXRight > halfSize && (positions.viewportXRight + 150) < (diffSizeRight - 50) && posRight > -50) {
            dojo.byId('planningBarDetailCloseButton').style.left = "unset";
          }
        }
      });
      hideWait();
      setTimeout('hideWait()', 250);
      setTimeout("ongoingRunScriptContextMenu=false;", 20);
    },
    error: function() {
      console.warn("error on return from planningBarDetail.php");
      if (timeoutContextMenuWait) clearTimeout(timeoutContextMenuWait);
      hideWait();
      setTimeout("ongoingRunScriptContextMenu=false;", 20);
    }
  });
  return false;
}
function highlightPlanningLine(id, planningEditMode, autoScrollPlanning) {
  if (id == null) id = vGanttCurrentLine;
  if (id < 0) return;
  vGanttCurrentLine = id;
  vTaskList = g.getList();
  for (var i = 0; i < vTaskList.length; i++) {
    JSGantt.ganttMouseOut(i);
  }
  if (autoScrollPlanning == undefined) autoScrollPlanning = false;
  if (autoScrollPlanningBar == 1) autoScrollPlanning = true; // From user parameter
  //  var currenttop = (document.getElementById('child_' + id))?document.getElementById('child_' + id).offsetTop:0;
  //  document.getElementById('rightGanttChartDIV').scrollTop = currenttop;
  //  if(autoScrollPlanning) graphicalChange = false;
  if (!graphicalChange) {
    if (document.getElementById('child_' + id)) {
      var currentPos = document.getElementById('child_' + id).offsetTop;
      var ratio=(typeof JSGantt != 'undefined' && JSGantt.getPlanningZoomRatio)?JSGantt.getPlanningZoomRatio():1;
      var containerScroll = document.getElementById('rightGanttChartDIV').scrollTop;
      var containerHeight = document.getElementById('rightGanttChartDIV').offsetHeight;
      var newPos = null;
      if ((currentPos*ratio) < containerScroll || (currentPos*ratio) > containerScroll + containerHeight) {
        newPos = currentPos - ((containerHeight/ratio) / 2) + 10;
        if (newPos < 0) newPos = 0;
        document.getElementById('rightGanttChartDIV').scrollTop = newPos*ratio;
        if (typeof JSGantt != 'undefined' && JSGantt.syncPlanningScroll) JSGantt.syncPlanningScroll();
        //setTimeout("document.getElementById('rightGanttChartDIV').scrollTop = "+newPos+";",1000);
      }
      if (autoScrollPlanning) setTimeout("scrollBarIntoView(" + id + "," + newPos + ");", 100);
    }
  } else {
    setTimeout("scrollGraphicalChange();", 250);
  }
  if (planningEditMode == undefined) planningEditMode = false;
  var vRowObj1 = JSGantt.findObj('child_' + id);
  if (vRowObj1) {
    // vRowObj1.className = "dojoxGridRowSelected dojoDndItem";// ganttTask" +h
    // pType;
    if (planningEditMode) {
      dojo.addClass(vRowObj1, "editModeRowSelected");
    } else {
      dojo.addClass(vRowObj1, "dojoxGridRowSelected");
      dojo.removeClass(vRowObj1, "editModeRowSelected");
    }
  }
  var vRowObj2 = JSGantt.findObj('childrow_' + id);
  if (vRowObj2) {
    // vRowObj2.className = "dojoxGridRowSelected";
    if (planningEditMode) {
      dojo.addClass(vRowObj2, "editModeRowSelected");
    } else {
      dojo.addClass(vRowObj2, "dojoxGridRowSelected");
      dojo.removeClass(vRowObj2, "editModeRowSelected");
    }
  }
}
var scrollBarIntoViewRetry = 0;
function scrollBarIntoView(id, topPos, forWorkPlan, today) {
  if (forWorkPlan == undefined) forWorkPlan = false;
  if (today == undefined) today = null;
  if (topPos == undefined) topPos = null;
  var bar = (today) ? dojo.byId(today) : dojo.byId("bardiv_" + id);
  if (!bar) {
    scrollBarIntoViewRetry++;
    if (scrollBarIntoViewRetry <= 5) setTimeout("scrollBarIntoView(" + id + "," + topPos + ");", 500 * scrollBarIntoViewRetry);
    return;
  }
  pos = bar.offsetLeft;
  var divName = (forWorkPlan) ? 'workPlanRightGanttChartDIV' : 'rightGanttChartDIV';
  if (!forWorkPlan && typeof JSGantt != 'undefined' && JSGantt.getPlanningZoomRatio) {
    var ratio=JSGantt.getPlanningZoomRatio();
    pos=pos*ratio;
    if (topPos !== null) topPos=topPos*ratio;
  }
  if (topPos == null) document.getElementById(divName).scrollLeft = pos - 100;
  else document.getElementById(divName).scrollTo(pos - 100, topPos);
  if (!forWorkPlan && typeof JSGantt != 'undefined' && JSGantt.syncPlanningScroll) JSGantt.syncPlanningScroll();
}

function scrollGraphicalChange() {
  if (graphicalChange == false || ! graphicalChangeValue) return;
  //data recup
  idGraphicalChange = graphicalChangeValue.getID();
  //scrollHorizontal
  document.getElementById('taskbar_' + idGraphicalChange)
    ?.scrollIntoView({ block: 'nearest', inline: 'center' });
  /*	//scrollVertical - not realy usefull
  /*			 document.getElementById('child_' + idGraphicalChange)
          ?.scrollIntoView({ block: 'center', inline: 'nearest' });*/
  //resetData
  graphicalChangeValue = null;
  graphicalChange = false;
}

function selectPlanningLine(selClass, selId, autoscroll, reopen) {
  if (selClass == undefined && selId == undefined) return;
  if (autoscroll == undefined) autoscroll = false;
  if (reopen == undefined) reopen = false;
  vGanttCurrentLine = id;
  vTaskList = g.getList();
  var tId = null;
  var idProject = null;
  for (var i = 0; i < vTaskList.length; i++) {
    scope = vTaskList[i].getScope();
    spl = scope.split("_");
    var taskListClass = spl[1];
    if (taskListClass == 'Replan' || taskListClass == 'Construction' || taskListClass == 'Fixed') taskListClass = 'Project';
    if (spl.length > 2 && taskListClass == selClass && spl[2] == selId) {
      tId = vTaskList[i].getID();
      idProject = vTaskList[i].getProjectId();
    }
  }
  if (tId != null) {
    if (currentRowToEdit == null) currentRowToEdit = tId;
    if (currentRowToEdit != null && currentRowToEdit != -1 && idProject != null) {
      //if(currentRowToEdit!= null tId!=currentRowToEdit && idProject != null){
      if (selClass == 'Replan' || selClass == 'Construction' || selClass == 'Fixed') selClass = 'Project';
      cachedAction = cachedEditRowPlanningClick;
      vGanttCurrentLine = currentRowToEdit; //#10433 :Planning calculation : pink message (with warning) disapears when detail is open
      //JSGantt.closeEditRowObjectPlanning();
      if (!reopen && currentRowToEdit == tId && cachedAction && cachedAction.indexOf('true')) {
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
      unselectPlanningLines();
      highlightPlanningLine(tId, false, autoscroll);
      currentRowToEdit = null;
    }
  }
}
function unselectPlanningLines() {
  dojo.query(".dojoxGridRowSelected").forEach(function(node, index, nodelist) {
    dojo.removeClass(node, "dojoxGridRowSelected");
  });
  dojo.query(".editModeRowSelected").forEach(function(node, index, nodelist) {
    dojo.removeClass(node, "editModeRowSelected");
  });
}

var planningSearchState = {
  id: { value: '', matches: [], index: -1 },
  name: { value: '', matches: [], index: -1 }
};
var planningSearchSelectRequest = 0;
var planningSearchSelectTimeout = null;

function planningSearchGetFieldIds(type) {
  return (type == 'id') ? ['planningSearchIdQuick', 'planningSearchIdBar'] : ['planningSearchNameQuick', 'planningSearchNameBar'];
}

function planningSearchGetCounterIds(type) {
  return (type == 'id') ? ['planningSearchIdCount', 'planningSearchIdBarCount'] : ['planningSearchNameCount', 'planningSearchNameBarCount'];
}

function planningSearchGetFieldValue(fieldId) {
  if (!dijit.byId(fieldId)) return '';
  var value = dijit.byId(fieldId).get('value');
  return trim((value == null) ? '' : '' + value);
}

function planningSearchGetValue(type, source) {
  var fieldIds = planningSearchGetFieldIds(type);
  if (source == 'bar') return planningSearchGetFieldValue(fieldIds[1]);
  if (source == 'quick') return planningSearchGetFieldValue(fieldIds[0]);
  for (var i = 0; i < fieldIds.length; i++) {
    var value = planningSearchGetFieldValue(fieldIds[i]);
    if (value) return value;
  }
  return '';
}

function planningSearchSyncFields(type, source, value) {
  var fieldIds = planningSearchGetFieldIds(type);
  for (var i = 0; i < fieldIds.length; i++) {
    if ((source == 'quick' && i == 0) || (source == 'bar' && i == 1)) continue;
    var widget = dijit.byId(fieldIds[i]);
    if (widget && widget.get('value') != value) widget.set('value', value);
  }
}

function planningSearchSetCounter(type) {
  var state = planningSearchState[type];
  var total = state.matches.length;
  var current = (total > 0 && state.index >= 0) ? state.index + 1 : 0;
  var counterIds = planningSearchGetCounterIds(type);
  for (var i = 0; i < counterIds.length; i++) {
    var node = dojo.byId(counterIds[i]);
    if (node) node.innerHTML = current + '/' + total;
  }
}

function planningSearchGetComparableValue(task, type) {
  var item = (task && task.getItem) ? task.getItem() : null;
  if (type == 'id') {
    if (item && item.refid != undefined) return '' + item.refid;
    var scope = (task && task.getScope) ? task.getScope() : '';
    var scopeParts = scope.split('_');
    return (scopeParts.length > 2) ? scopeParts[2] : '';
  }
  var value = '';
  if (item && item.refname != undefined) value = item.refname;
  else if (task && task.getName) value = task.getName();
  if (typeof htmlDecode == 'function') value = htmlDecode(value);
  return ('' + value).toLowerCase();
}

function planningSearchBuildMatches(type, source, preservePosition) {
  var state = planningSearchState[type];
  var previousMatch = (preservePosition && state.index >= 0) ? state.matches[state.index] : null;
  var rawValue = planningSearchGetValue(type, source);
  planningSearchSyncFields(type, source, rawValue);
  var value = rawValue;
  if (type == 'name') value = value.toLowerCase();
  state.value = value;
  state.matches = [];
  state.index = -1;
  if (!value || typeof g == 'undefined' || !g || !g.getList) {
    planningSearchSetCounter(type);
    return state.matches;
  }
  var taskList = g.getList();
  for (var i = 0; i < taskList.length; i++) {
    var task = taskList[i];
    if (!task) continue;
    var comparableValue = planningSearchGetComparableValue(task, type);
    if (comparableValue.indexOf(value) >= 0) state.matches.push(task.getID());
  }
  if (preservePosition && state.matches.length > 0) {
    var previousIndex = (previousMatch !== null) ? state.matches.indexOf(previousMatch) : -1;
    if (previousIndex >= 0) state.index = previousIndex;
    else state.index = 0;
  }
  planningSearchSetCounter(type);
  return state.matches;
}

function planningSearchUpdate(type, source) {
  if (!planningSearchState[type]) return;
  planningSearchBuildMatches(type, source);
}

function planningSearchGetVisibleIndex(lineId) {
  if (typeof g == 'undefined' || !g || !g.getList) return null;
  var taskList = g.getList();
  var visibleIndex = 0;
  for (var i = 0; i < taskList.length; i++) {
    var task = taskList[i];
    if (!task) continue;
    if (task.getID() == lineId) return visibleIndex;
    if (task.getVisible() == 1 && (!dojo.byId('portfolio') || !task.getMile())) visibleIndex++;
  }
  return null;
}

function planningSearchOpenParents(lineId) {
  if (typeof g == 'undefined' || !g || !g.getLineByID) return false;
  var task = g.getLineByID(lineId);
  if (!task) return false;
  var parentIds = [];
  var parentId = task.getParent();
  while (parentId) {
    var parentTask = g.getLineByID(parentId);
    if (!parentTask) break;
    parentIds.unshift(parentId);
    parentId = parentTask.getParent();
  }
  var opened = false;
  for (var i = 0; i < parentIds.length; i++) {
    var currentParent = g.getLineByID(parentIds[i]);
    if (currentParent && currentParent.getGroup && currentParent.getGroup() && currentParent.getOpen && currentParent.getOpen() != 1) {
      JSGantt.folder(parentIds[i], g, true);
      opened = true;
    }
  }
  if (opened && typeof showGanttLinesVisible == 'function') showGanttLinesVisible();
  return opened;
}

function planningSearchSelectLine(lineId) {
  planningSearchSelectRequest++;
  var currentRequest = planningSearchSelectRequest;
  if (planningSearchSelectTimeout) clearTimeout(planningSearchSelectTimeout);
  planningSearchOpenParents(lineId);
  var visibleIndex = planningSearchGetVisibleIndex(lineId);
  var container = dojo.byId('rightGanttChartDIV');
  if (container && visibleIndex !== null) {
    var containerHeight = container.offsetHeight;
    var ratio=(typeof JSGantt != 'undefined' && JSGantt.getPlanningZoomRatio)?JSGantt.getPlanningZoomRatio():1;
    var newPos = (visibleIndex * 21 * ratio) - (containerHeight / 2) + 10;
    if (newPos < 0) newPos = 0;
    container.scrollTop = newPos;
    if (typeof JSGantt != 'undefined' && JSGantt.syncPlanningScroll) JSGantt.syncPlanningScroll();
    if (typeof showGanttLinesVisible == 'function') showGanttLinesVisible();
  }
  var selectFunction = function() {
    if (currentRequest != planningSearchSelectRequest) return;
    if (typeof g != 'undefined' && g && g.getArrayLocationByID && typeof showGanttOneLine == 'function') {
      var lineIndex = g.getArrayLocationByID(lineId);
      if (lineIndex !== null && (!dojo.byId('childrow_' + lineId) || dojo.byId('childrow_' + lineId + '_partial') || !dojo.byId('taskbar_' + lineId))) {
        showGanttOneLine(lineIndex, lineId);
      }
    }
    unselectPlanningLines();
    highlightPlanningLine(lineId, false, true);
    currentRowToEdit = null;
  };
  planningSearchSelectTimeout = setTimeout(selectFunction, 100);
}

function planningSearchValidateInput(type, source) {
  if (!planningSearchState[type]) return;
  var state = planningSearchState[type];
  var value = planningSearchGetValue(type, source);
  var normalizedValue = (type == 'name') ? value.toLowerCase() : value;
  if (normalizedValue != state.value || state.matches.length == 0) {
    planningSearchBuildMatches(type, source);
  }
  if (state.matches.length == 0) return;
  if (state.index >= 0 && normalizedValue == state.value) {
    state.index++;
    if (state.index >= state.matches.length) state.index = 0;
  } else {
    state.index = 0;
  }
  planningSearchSelectLine(state.matches[state.index]);
  planningSearchSetCounter(type);
}

function planningSearchInputKeyUp(event, type, source) {
  var keyCode = event ? event.keyCode : null;
  if (keyCode == 13) {
    planningSearchValidateInput(type, source);
  } else if (keyCode == 9) {
    return false;
  } else {
    planningSearchUpdate(type, source);
  }
}

function planningSearchInputKeyDown(event, type, source) {
  var keyCode = event ? event.keyCode : null;
  if (keyCode != 9) return true;
  if (event.preventDefault) event.preventDefault();
  event.returnValue = false;
  planningSearchValidateInput(type, source);
  return false;
}

function planningSearchMove(type, direction) {
  if (!planningSearchState[type]) return;
  var state = planningSearchState[type];
  var value = planningSearchGetValue(type);
  if ((type == 'name' ? value.toLowerCase() : value) != state.value) {
    planningSearchBuildMatches(type);
  }
  if (state.matches.length == 0) {
    planningSearchSetCounter(type);
    return;
  }
  state.index = state.index + direction;
  if (state.index >= state.matches.length) state.index = 0;
  if (state.index < 0) state.index = state.matches.length - 1;
  planningSearchSelectLine(state.matches[state.index]);
  planningSearchSetCounter(type);
}

function planningSearchRefreshAll() {
  if (!planningSearchState) return;
  planningSearchBuildMatches('id', null, true);
  planningSearchBuildMatches('name', null, true);
}

function planningRestoreSelectedLineAfterRefresh(id) {
  if (id == null || id < 0 || typeof g == 'undefined' || !g || !g.getLineByID) return;
  if (!g.getLineByID(id)) return;
  planningSearchOpenParents(id);
  unselectPlanningLines();
  highlightPlanningLine(id, false, false);
}

function planningSearchToggleBar(type, value) {
  var spanId = (type == 'id') ? 'planningSearchIdBarSpan' : 'planningSearchNameBarSpan';
  var span = dojo.byId(spanId);
  if (!span) return;
  span.style.display = (value == 'on') ? 'inline-flex' : 'none';
  if (value == 'on') {
    planningSearchSyncFields(type, 'quick', planningSearchGetValue(type, 'quick'));
  }
}

function addToTimeline(refId, refType) {
  var callback = function() {
    JSGantt.hideMenu(0);
    if (dojo.query('.hiddenTimelineTask').length == 0) {
      if (dojo.byId('workPlanJsonData') && dojo.byId('planningJsonData')) {
        loadMenuBarItem('PlanningWorkPlan', 'PlanningWorkPlan', 'bar');
      } else {
        loadMenuBarItem('Planning', 'Planning', 'bar');
      }
    } else {
      refreshTimeline();
    }
  };
  loadContent("../tool/setTimelineItem.php?refId=" + refId
    + "&refType=" + refType + "&mode=add", "resultDivMain", null, true, 'Timeline', null, true, callback);
}

function removeFromTimeline(refId, refType) {
  var callback = function() {
    JSGantt.hideMenu(0);
    if (dojo.query('.hiddenTimelineTask').length == 1) {
      if (dojo.byId('workPlanJsonData') && dojo.byId('planningJsonData')) {
        loadMenuBarItem('PlanningWorkPlan', 'PlanningWorkPlan', 'bar');
      } else {
        loadMenuBarItem('Planning', 'Planning', 'bar');
      }
    } else {
      refreshTimeline();
    }
  };
  loadContent("../tool/setTimelineItem.php?refId=" + refId
    + "&refType=" + refType + "&mode=remove", "resultDivMain", null, true, 'Timeline', null, true, callback);
}

function refreshTimeline() {
  loadContent("../tool/jsonTimeline.php", "timelineGanttDiv", null, false);
}

function openTimelineContextMenu(taskId, refId, refType) {
  var contextMenu = dijit.byId('planningContextMenu');
  var contextMenuDiv = dojo.byId('dialogPlanningContextMenu');
  var mousePosition = {};
  mousePosition.x = event.clientX;
  if (dojo.byId('isMenuLeftOpen').value == 'true') {
    mousePosition.x -= 250;
  }
  mousePosition.y = event.clientY - 220;
  dojo.query('.contextMenuClass').forEach(function(node) {
    node.style.cssText = 'position:absolute;width:0px;height:0px;overflow:hidden;top:' + mousePosition.y + 'px;left:' + mousePosition.x + 'px';
  });

  if (dojo.byId('cm_addFromPlanning')) dojo.byId('cm_addFromPlanning').style.display = 'none';
  if (dojo.byId('cm_openFromPlanning')) dojo.byId('cm_openFromPlanning').style.display = 'none';
  if (dojo.byId('cm_closeFromPlanning')) dojo.byId('cm_closeFromPlanning').style.display = 'none';
  if (dojo.byId('cm_editFromPlanning')) dojo.byId('cm_editFromPlanning').style.display = 'none';
  if (dojo.byId('cm_removeFromPlanning')) dojo.byId('cm_removeFromPlanning').style.display = 'none';
  if (dojo.byId('cm_copyFromPlanning')) dojo.byId('cm_copyFromPlanning').style.display = 'none';
  if (dojo.byId('cm_splitFromPlanning')) dojo.byId('cm_splitFromPlanning').style.display = 'none';
  if (dojo.byId('cm_editAssignmentFromPlanning')) dojo.byId('cm_editAssignmentFromPlanning').style.display = 'none';
  if (dojo.byId('cm_editAffectationFromPlanning')) dojo.byId('cm_editAffectationFromPlanning').style.display = 'none';
  if (dojo.byId('cm_emailFromPlanning')) dojo.byId('cm_emailFromPlanning').style.display = 'none';
  if (dojo.byId('cm_historyFromPlanning')) dojo.byId('cm_historyFromPlanning').style.display = 'none';
  if (dojo.byId('cm_printFromPlanning')) dojo.byId('cm_printFromPlanning').style.display = 'none';
  if (dojo.byId('cm_pdfFromPlanning')) dojo.byId('cm_pdfFromPlanning').style.display = 'none';
  if (dojo.byId('cm_successorFromPlanning')) dojo.byId('cm_successorFromPlanning').style.display = 'none';
  if (dojo.byId('cm_predecessorFromPlanning')) dojo.byId('cm_predecessorFromPlanning').style.display = 'none';
  if (dojo.byId('cm_sectionTimeline')) dojo.byId('cm_sectionTimeline').style.display = 'none';
  if (dojo.byId('cm_editOnlineFromPlanning')) dojo.byId('cm_editOnlineFromPlanning').style.display = 'none';

  if (dojo.byId('TimelineItemTask_' + taskId)) {
    dojo.byId('cm_addToTimeline').style.display = 'none';
    dojo.byId('cm_removeFromTimeline').style.display = '';
    dojo.byId('cm_removeFromTimeline').setAttribute('onClick', 'removeFromTimeline(' + refId + ', \'' + refType + '\')');
  } else {
    dojo.byId('cm_addToTimeline').style.display = '';
    dojo.byId('cm_removeFromTimeline').style.display = 'none';
    dojo.byId('cm_addToTimeline').setAttribute('onClick', 'addToTimeline(' + refId + ', \'' + refType + '\')');
  }
  contextMenu.openDropDown();
  contextMenuDiv.focus();
}

function openObjectFromContextMenu(refType, refId, taskId, idProject) {
  if (refType == 'Replan' || refType == 'Construction' || refType == 'Fixed') refType = 'Project';
  JSGantt.hideMenu();
  JSGantt.closeAndSelectEditRow(taskId, refId, refType, idProject);
  notShowDetailAfterReplan = false;
  runScript(refType, refId, taskId);
}

function closeObjectFromContextMenu() {
  JSGantt.hideMenu();
  hideDetailScreen();
  JSGantt.closeEditRowObjectPlanning();
}

function addObjectFromContextMenu(refId, refType, taskId, idProject, viewObjectList) {
  fromContextMenu = true;
  if (refType == 'Replan' || refType == 'Construction' || refType == 'Fixed') refType = 'Project';
  if (viewObjectList == false) {
    JSGantt.closeAndSelectEditRow(taskId, refId, refType, idProject);
  }
  var canCreate = (canCreateArray[refType] == 'YES') ? 1 : 0;
  dojo.byId('objectClass').value = refType;
  dojo.byId('objectId').value = refId;
  showDetail(null, canCreate, refType, false, 'new', true);
}

function editObjectFromContextMenu(refId, refType, taskId, idProject) {
  fromContextMenu = true;
  if (refType == 'Replan' || refType == 'Construction' || refType == 'Fixed') refType = 'Project';
  hideDetailScreen();
  JSGantt.closeAndSelectEditRow(taskId, refId, refType, idProject);
  var canCreate = (canCreateArray[refType] == 'YES') ? 1 : 0;
  showDetail(null, canCreate, refType, false, refId, true);
}

function editRowObjectFromContextMenu(taskId, refId, refType, idProject) {
  if (checkFormChangeInProgress()) return;
  if (refType == 'Replan' || refType == 'Construction' || refType == 'Fixed') refType = 'Project';
  JSGantt.hideMenu();
  hideDetailScreen();
  if (currentRowToEdit && currentRowToEdit != taskId) {
    JSGantt.closeAndSelectEditRow(taskId, refId, refType, idProject, true);
  } else {
    JSGantt.editRowObjectPlanning(taskId, refId, refType, idProject, true);
  }
}

function getPlanningDeleteRefType(refType) {
  if (refType == 'Replan' || refType == 'Construction' || refType == 'Fixed') return 'Project';
  if (refType == 'ProductVersionhasChild') return 'ProductVersion';
  if (refType == 'ComponentVersionhasChild') return 'ComponentVersion';
  return refType;
}

function getSelectedPlanningItemsForDelete(refId, refType) {
  var selectedItems = new Array();
  var selectedKeys = new Array();
  if (typeof dndSourceTable == 'undefined' || !dndSourceTable || !dndSourceTable.getSelectedNodes || typeof g == 'undefined' || !g) {
    return selectedItems;
  }
  dndSourceTable.getSelectedNodes().forEach(function(node) {
    if (!node || !node.id || node.id.indexOf('child_') !== 0) return;
    var taskId = node.id.substr(6);
    var task = g.getLineByID(taskId);
    if (!task) return;
    var itemRefType = getPlanningDeleteRefType(task.getClass());
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

function deleteSelectedPlanningItemsFromContextMenu(items) {
  var selection = '';
  items.forEach(function(item) {
    selection += item.refType + ':' + item.refId + ';';
  });
  var form = dojo.byId('planningListForm');
  if (!form) return;
  var selectionInput = dojo.byId('planningDeleteSelection');
  if (!selectionInput) {
    selectionInput = document.createElement('input');
    selectionInput.type = 'hidden';
    selectionInput.id = 'planningDeleteSelection';
    selectionInput.name = 'selection';
    form.appendChild(selectionInput);
  }
  selectionInput.value = selection;
  loadContent('../tool/deletePlanningSelection.php', 'resultDivMain', 'planningListForm', false, null, null, null, function() {
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
    refreshJsonPlanning();
  });
}

function deleteObjectFromContextMenu(refId, refType, viewObjectList) {
  fromContextMenu = true;
  refType = getPlanningDeleteRefType(refType);
  if (viewObjectList == false) {
    hideDetailScreen();
    JSGantt.closeEditRowObjectPlanning();
  }
  var selectedItems = getSelectedPlanningItemsForDelete(refId, refType);
  if (selectedItems.length > 1) {
    showConfirm(i18n('confirmDeleteMultiplePlanning'), function() {
      deleteSelectedPlanningItemsFromContextMenu(selectedItems);
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

function copyObjectFromContextMenu(refId, refType, taskId, idProject, viewObjectList) {
  fromContextMenu = true;
  if (refType == 'Replan' || refType == 'Construction' || refType == 'Fixed') refType = 'Project';
  if (viewObjectList == false) {
    hideDetailScreen();
    JSGantt.closeAndSelectEditRow(taskId, refId, refType, idProject);
  }
  var paramCopy = "copyProject";
  dojo.byId('objectClass').value = refType;
  dojo.byId('objectId').value = refId;
  if (refType != "Project") {
    if (refType == 'ComponentVersion') {
      paramCopy = "copyVersion";
      copyObjectBox(paramCopy, fromContextMenu);
    } else if (copyableArray.indexOf(refType) != -1) {
      paramCopy = "copyObjectTo";
      copyObjectBox(paramCopy, fromContextMenu);
    } else {
      if (refType == 'Document') {
        paramCopy = "copyDocument";
        copyObjectBox(paramCopy, fromContextMenu);
      } else {
        copyObject(refType, refId, fromContextMenu);
      }
    }
  } else {
    copyObjectBox(paramCopy, fromContextMenu);
  }
}


function copyPasteObjectFromContextMenu(refId, refType, taskId, idProject, viewObjectList) {
  fromContextMenu = true;
  if (refType == 'Replan' || refType == 'Construction' || refType == 'Fixed') refType = 'Project';
  if (viewObjectList == false) {
    hideDetailScreen();
    JSGantt.closeAndSelectEditRow(taskId, refId, refType, idProject);
  }
  var paramCopy = "copyProject";
  dojo.byId('objectClass').value = refType;
  dojo.byId('objectId').value = refId;
  if (refType != "Project") {
    if (copyableArray.indexOf(refType) != -1) {
      paramCopy = "copyObjectTo";
    }
  } else if (copyableArray.indexOf(refType) != -1) {
    paramCopy = "copyObjectTo";
  }
  copyPasteObjectBox(paramCopy, fromContextMenu);
}


function splitObjectFromContextMenu(refId, refType) {
  var action = function() {
    loadContent("../tool/splitActivity.php?objectId=" + refId
      + "&objectClass=" + refType, "resultDivMain", null, true);
  };
  showConfirm(i18n('confirmSplit', new Array(i18n(refType), refId)), action);
}

function editAssignmentFromContextMenu(refId, refType, taskId, idProject) {
  if (refType == 'Replan' || refType == 'Construction' || refType == 'Fixed') refType = 'Project';
  hideDetailScreen();
  if (coverListAction == 'CLOSE') {
    JSGantt.closeAndSelectEditRow(taskId, refId, refType, idProject);
  }
  var params = "&objectClass=" + refType + "&objectId=" + refId;
  loadDialog('dialogEditAssignmentPlanning', null, true, params);
}

function editAffectationFromContextMenu(refId, refType, taskId, idProject) {
  if (refType == 'Replan' || refType == 'Construction' || refType == 'Fixed') refType = 'Project';
  hideDetailScreen();
  if (coverListAction == 'CLOSE') {
    JSGantt.closeAndSelectEditRow(taskId, refId, refType, idProject);
  }
  var params = "&objectClass=" + refType + "&objectId=" + refId;
  loadDialog('dialogEditAffectationPlanning', null, true, params);
}

function sendMailFromContextMenu(refId, refType, taskId, idProject) {
  if (refType == 'Replan' || refType == 'Construction' || refType == 'Fixed') refType = 'Project';
  if (coverListAction == 'CLOSE') {
    JSGantt.closeAndSelectEditRow(taskId, refId, refType, idProject);
  }
  dojo.byId('objectClass').value = refType;
  dojo.byId('objectId').value = refId;
  showMailOptions();
}

function showHistoryFromContextMenu(refId, refType, taskId, idProject) {
  if (refType == 'Replan' || refType == 'Construction' || refType == 'Fixed') refType = 'Project';
  if (coverListAction == 'CLOSE') {
    JSGantt.closeAndSelectEditRow(taskId, refId, refType, idProject);
  }
  var params = "&objectClass=" + refType + "&objectId=" + refId;
  loadDialog('dialogHistory', null, true, params);
}

function successorFromContextMenu(refId, refType, taskId, idProject) {
  if (refType == 'Replan' || refType == 'Construction' || refType == 'Fixed') refType = 'Project';
  if (coverListAction == 'CLOSE') {
    JSGantt.closeAndSelectEditRow(taskId, refId, refType, idProject);
  }
  dojo.byId('objectClass').value = refType;
  dojo.byId('objectId').value = refId;
  indentTask("increase");
}

function predecessorFromContextMenu(refId, refType, taskId, idProject) {
  if (refType == 'Replan' || refType == 'Construction' || refType == 'Fixed') refType = 'Project';
  if (coverListAction == 'CLOSE') {
    JSGantt.closeAndSelectEditRow(taskId, refId, refType, idProject);
  }
  dojo.byId('objectClass').value = refType;
  dojo.byId('objectId').value = refId;
  indentTask("decrease");
}

function invertSwitchValue(switchName) {
  if (!dijit.byId(switchName)) return;
  if (dijit.byId(switchName).get('value') == 'on') dijit.byId(switchName).set('value', 'off');
  else dijit.byId(switchName).set('value', 'on');
}

function drawButtonPredecessorElement() {
	resetCriticalPathFilterIfActive();  
  if (!dojo.byId("predecessorSequence")) return;
  var value = dojo.byId("predecessorSequence").innerHTML;
  if (value == '') {
    if (!vGanttCurrentLine) {
      showInfo(i18n('selectItemForDependency'));
      return;
    }
    dojo.byId("predecessorSequence").innerHTML = '1';
  } else if (value == '1') {
    dojo.byId("predecessorSequence").innerHTML = '&infin;';
  } else {
    dojo.byId("predecessorSequence").innerHTML = '';
  }
  drawPredecessorsAndSuccessors();
}

function drawButtonSuccessorElement() {
	resetCriticalPathFilterIfActive(); 
  if (!dojo.byId("successorSequence")) return;
  var value = dojo.byId("successorSequence").innerHTML;
  if (value == '') {
    if (!vGanttCurrentLine) {
      showInfo(i18n('selectItemForDependency'));
      return;
    }
    dojo.byId("successorSequence").innerHTML = '1';
  } else if (value == '1') {
    dojo.byId("successorSequence").innerHTML = '&infin;';
  } else {
    dojo.byId("successorSequence").innerHTML = '';
  }
  drawPredecessorsAndSuccessors();
}

function predecessorSuccessorReset() {
  if (!dojo.byId("predecessorSequence") || !dojo.byId("successorSequence")) return;
  dojo.byId("successorSequence").innerHTML = '';
  dojo.byId("predecessorSequence").innerHTML = '';
  drawPredecessorsAndSuccessors();
}

var drawPredecessorsAndSuccessorsScrollPosition = null;
function drawPredecessorsAndSuccessors() {
  if (!dojo.byId("predecessorSequence") || !dojo.byId("successorSequence")) return;
  var valuePred = dojo.byId("predecessorSequence").innerHTML;
  var valueSucc = dojo.byId("successorSequence").innerHTML;
  var predecessorElement = dojo.byId('predecessor');
  var successorElement = dojo.byId('successor');
  var listToShow = new Array();
  if (drawPredecessorsAndSuccessorsScrollPosition == null && (valuePred != '' || valueSucc != '')) {
    var container = dojo.byId('rightGanttChartDIV');
    var scroll = container.scrollTop;
    drawPredecessorsAndSuccessorsScrollPosition = scroll;
  }

  dojo.byId("predecessorSuccessorReset").style.display = 'none';
  if (valuePred == '') {
    predecessorElement.classList.remove('dependencySelectedPredecessor');
    predecessorElement.classList.add('dependencyPredecessor');
  } else {
    predecessorElement.classList.remove('dependencyPredecessor');
    predecessorElement.classList.add('dependencySelectedPredecessor');
    dojo.byId("predecessorSuccessorReset").style.display = 'block';
    listToShow = getPredecessorsFromCurrent(vGanttCurrentLine, listToShow, valuePred);
  }
  if (valueSucc == '') {
    successorElement.classList.remove('dependencySelectedSuccessor');
    successorElement.classList.add('dependencySuccessor');
  } else {
    successorElement.classList.remove('dependencySuccessor');
    successorElement.classList.add('dependencySelectedSuccessor');
    dojo.byId("predecessorSuccessorReset").style.display = 'block';
    listToShow = getSuccessorFromCurrent(vGanttCurrentLine, listToShow, valueSucc);
  }
  showWait();
  showOnlySelectedLines(listToShow);
  hideWait();
  // Remove / Reset spacing for level
  dojo.query(".ganttSpacingDiv").forEach(function(node, index, nodelist) {
    node.style.display = (listToShow.length > 0) ? 'none' : 'block';
  });

  if (valuePred == '' && valueSucc == '') {
    dojo.byId('rightGanttChartDIV').scrollTop = drawPredecessorsAndSuccessorsScrollPosition;
    if (typeof JSGantt != 'undefined' && JSGantt.syncPlanningScroll) JSGantt.syncPlanningScroll();
    setTimeout("dojo.byId('rightGanttChartDIV').scrollTop=" + drawPredecessorsAndSuccessorsScrollPosition + ";if (typeof JSGantt != 'undefined' && JSGantt.syncPlanningScroll) JSGantt.syncPlanningScroll();", 50);
    drawPredecessorsAndSuccessorsScrollPosition = null;
  }
}
function isPredecessorSuccessorEnabled() {
  if (!dojo.byId("predecessorSequence") || !dojo.byId("successorSequence")) return false;
  var valuePred = dojo.byId("predecessorSequence").innerHTML;
  var valueSucc = dojo.byId("successorSequence").innerHTML;
  return (valuePred || valueSucc) ? true : false;
}
function getPredecessorsFromCurrent(vGanttCurrentLine, listToShow, valuePred) {
  line = g.getLineByID(vGanttCurrentLine);
  if (!line) return listToShow;
  listToShow.push(vGanttCurrentLine);
  vDepend = line.getDepend();
  if (vDepend) {
    vList = g.getList();
    var vDependStr = vDepend + '';
    var vDepList = vDependStr.split(',');
    for (var k = 0; k < vDepList.length; k++) {
      var depListSplit = vDepList[k].split("#");
      listToShow.push(depListSplit[0]);
      if (valuePred != '1') listToShow = getPredecessorsFromCurrent(depListSplit[0], listToShow, valuePred);
    }
  }
  return listToShow;
}

function getSuccessorFromCurrent(vGanttCurrentLine, listToShow, valueSucc) {
  line = g.getLineByID(vGanttCurrentLine);
  if (!line) return listToShow;
  listToShow.push(vGanttCurrentLine);
  vList = g.getList();
  for (var i = 0; i < vList.length; i++) {
    vDepend = vList[i].getDepend();
    if (vDepend) {
      var vDependStr = vDepend + '';
      var vDepList = vDependStr.split(',');
      for (var k = 0; k < vDepList.length; k++) {
        var depListSplit = vDepList[k].split("#");
        if (depListSplit[0] == vGanttCurrentLine) {
          listToShow.push(vList[i].getID());
          if (valueSucc != '1') listToShow = getSuccessorFromCurrent(vList[i].getID(), listToShow, valueSucc);
          break;
        }
      }
    }
  }
  return listToShow;
}

function showOnlySelectedLines(listToShow) {
  if (criticalPathFilterActive === undefined) criticalPathFilterActive = false;
  var vList = g.getList();
  g.clearDependencies();
  var mustReprocess = false;
  for (var i = 0; i < vList.length; i++) {
    pId = vList[i].getID();
    if ((listToShow.length > 0 && listToShow.indexOf(pId) < 0) || (listToShow.length == 0 && !vList[i].getVisible())) {
      if (dojo.byId("child_" + pId)) dojo.byId("child_" + pId).style.display = 'none';
      if (dojo.byId("childgrid_" + pId)) dojo.byId("childgrid_" + pId).style.display = 'none';
    } else {
      if (listToShow.length > 0 || vList[i].getVisible()) {
        if (dojo.byId("child_" + pId)) dojo.byId("child_" + pId).style.display = '';
        if (dojo.byId("childgrid_" + pId)) dojo.byId("childgrid_" + pId).style.display = '';
        if (listToShow.length > 0) {
          showGanttOneLine(i, pId);
          //if (! dojo.byId("childrow_"+pId)) mustReprocess=true;
        }
      }
    }
  }
  //if (mustReprocess) JSGantt.processRows(vList, 0, -1, 1, 1);
  g.DrawDependencies(listToShow.length > 0 ? true : false);
  adjustSpecificDaysHeight();
}

function getRandomArbitrary(min, max) {
  return Math.random() * (max - min) + min;
}

var needRecalculatePlanning = false;
function recalculatePlanning() {
  if (removeQuickPlanningFeature == "1") return;
  var vList = g.getList();
  var needRefresh = false;
  openDetail = (dojo.byId('contentDetailDiv') && dojo.byId('contentDetailDiv').offsetWidth > 10 && dojo.byId('contentDetailDiv').offsetHeight > 10 && dijit.byId("name")) ? true : false;
  if (dojo.byId("dependencyChanged") && dojo.byId("dependencyChanged").value) {
    var dependencyChanged = JSON.parse(dojo.byId("dependencyChanged").value);
    for (var key in dependencyChanged) {
      var taskPos = g.getArrayLocationByID(key);
      if (taskPos === null || ! vList[taskPos]) continue;
      if ((vList[taskPos].getDependPred() ?? '') != dependencyChanged[key].dependPred || (vList[taskPos].getDependSucc() ?? '') != dependencyChanged[key].dependSucc) {
        vList[taskPos].setUpdated(true);
        // Must refresh if field predecessor is visible
        needRefresh = true;
      }
      vList[taskPos].setDependPred(dependencyChanged[key].dependPred);
      vList[taskPos].setDependSucc(dependencyChanged[key].dependSucc);
      needRefresh = false; // PBER #11867 - Workaround when add / remove dependency
    }
  } else if (openDetail && vGanttCurrentLine && dojo.byId('lastOperationStatus') && dojo.byId('lastOperationStatus').value == 'OK') {
	  var taskPos = g.getArrayLocationByID(vGanttCurrentLine);
	  if (taskPos !== null && vList[taskPos]) {
	    needRefresh = vList[taskPos].checkParentChangeFromDetail();
	    var planningTypeIndice = getIndiceForPlanningType(g.planningType);
	    for (var i = 0; i < planningFieldsDescription[planningTypeIndice].length; i++) {
	      vList[taskPos].setFieldValueFromDetail(planningFieldsDescription[planningTypeIndice][i]);
	    }
	  }
	}
  if (needRefresh) {
    needRefresh=false;
    refreshJsonPlanning();
  } else {
    recalculatePlanningCompute();
    recalculatePlanningDisplay();
  }
}
function recalculatePlanningDisplay() {
  if (removeQuickPlanningFeature == "1") return;
  if (dojo.byId('lastOperationStatus') && dojo.byId('lastOperationStatus').value == 'OK'
    && (!dojo.byId('editRowObjetFieldToRefresh') || dojo.byId('editRowObjetFieldToRefresh').value != 'Predecessor')
    && (!dojo.byId("dependencyChanged") || !dojo.byId("dependencyChanged").value)
    && dojo.byId('lastOperation') && (dojo.byId('lastOperation').value == 'insert'
      || dojo.byId('lastOperation').value == 'delete'
      || dojo.byId('lastOperation').value == 'move'
      || dojo.byId('lastOperation').value == 'copy'
      || dojo.byId('savedAssignment'))) {
    refreshJsonPlanning();
    return;
  }
  if (dojo.byId("dependencyChanged")) dojo.byId("dependencyChanged").value = '';
  //refreshJsonPlanning();
  g.Draw();
  showGanttLinesVisible();
  //adjustSpecificDaysHeight();
  //ganttObj.DrawDependencies();
  if (cachedEditRowPlanningClick) {
    setTimeout(cachedEditRowPlanningClick, 100);
  } else if (currentRowToEdit) {
    var currentClass = (dojo.byId('objectClass')) ? dojo.byId('objectClass').value : null;
    var currentId = (dojo.byId('objectId')) ? dojo.byId('objectId').value : null;
    var editRowClass = (dojo.byId('objectClassName')) ? dojo.byId('objectClassName').value : null;
    var editRowId = (dojo.byId('objectIdRow')) ? dojo.byId('objectIdRow').value : null;
    selectPlanningLine(currentClass, currentId);
  }

  var valuePred = (dojo.byId("predecessorSequence")) ? dojo.byId("predecessorSequence").innerHTML : '';
  var valueSucc = (dojo.byId("successorSequence")) ? dojo.byId("successorSequence").innerHTML : '';
  if (valuePred != '' || valueSucc != '') drawPredecessorsAndSuccessos();
  //setTimeout("highlightPlanningLine();",100);
}

function recalculatePlanningSaveData(id, dateStart, dateEnd, duration, resizer) {
  if (removeQuickPlanningFeature == "1") return;
  var vList = g.getList();
  var taskPos = g.getArrayLocationByID(id);
  var task = vList[taskPos];
  var refItem = g.getRefItemByID(task.getID());
  var codePm = task.getCodePlanningMode();
  task.setStart(JSGantt.parseDateStr(dateStart, g.getDateInputFormat()));
  task.setEnd(JSGantt.parseDateStr(dateEnd, g.getDateInputFormat()));
  duration = workDayDiffDates(task.getStart(), task.getEnd(), task.getItem().idproject);
  //item.setDuration(duration);
  //if (resizer=='start' && (codePm=='DDUR' || codePm=='CDUR')) {
  if (resizer == 'start') {
    task.setValidatedStart(task.getStart());
    task.getItem().validatedstartdate = dateStart;
    setPlanningFieldValue('ValidatedStartDate', refItem, task.getStart(), 'raw', g.planningType);
    if (task.getValidatedEnd()) {
      task.setValidatedEnd(task.getEnd());
      task.getItem().validatedenddate = dateEnd;
      setPlanningFieldValue('ValidatedEndDate', refItem, task.getEnd(), 'raw', g.planningType);
    }
    task.vDuration = duration;
    //} else if (resizer=='end'  && (codePm=='FDUR' ||codePm=='DDUR' || codePm=='CDUR')) {
  } else if (resizer == 'end') {
    task.getItem().validatedduration = duration;
    setPlanningFieldValue('ValidatedDuration', refItem, duration, 'raw', g.planningType);
    task.vDuration = duration;
    if (task.getValidatedEnd()) {
      task.setValidatedEnd(task.getEnd());
      task.getItem().validatedenddate = dateEnd;
      setPlanningFieldValue('ValidatedEndDate', refItem, task.getEnd(), 'raw', g.planningType);
    }
  }
  task.setUpdated(true);
  task = recalculatePlanningSaveDates(task, task.getStart(), task.getEnd(), true);
  vList[taskPos] = task;
}

function getDateForPlanning(pDate) {
  if (!pDate) return null;
  if (!(pDate instanceof Date)) {
    pDate = JSGantt.parseDateStr(pDate, g.getDateInputFormat());
  }
  var cDate = new Date();
  return new Date(pDate.getFullYear(), pDate.getMonth(), pDate.getDate(), cDate.getHours(), cDate.getMinutes(), cDate.getSeconds());
}
function recalculatePlanningCompute() {
  if (removeQuickPlanningFeature == "1") return;
  console.time('recalculatePlanningCompute()');
  quickPlanning = true;
  var startPlan = new Date();
  if (dijit.byId('startDatePlan')) {
    startPlan = getDateForPlanning(dijit.byId('startDatePlan').get('value'));
  }

  var startPlanMain = startPlan;
  //while (isOffDay(startPlan)) { startPlan=addDaysToDate(startPlan,1); }
  var graph = [];
  var indegree = [];
  var delay = [];
  var position = [];
  var parent = [];
  var vList = g.getList();
  // Initialization
  for (var i = 0; i < vList.length; i++) {
    var pId = vList[i].getID();
    graph["#" + pId] = [];
    indegree["#" + pId] = 0;
    position["#" + pId] = i;
    var parentId = vList[i].getParent();
    if (parentId) {
      if (!parent['#' + parentId]) parent['#' + parentId] = [];
      parent['#' + parentId].push(pId)
    }
  }

  // Sort tasks from dependencies and parents
  for (var i = 0; i < vList.length; i++) {
    var pId = vList[i].getID();
    var parentId = vList[i].getParent();
    var pmCode = vList[i].getCodePlanningMode();
    // Delay Recurring
    if (pmCode == 'RECW') {
      graph["#" + parentId].push("#" + pId);
      indegree["#" + pId]++;
      continue;
    }
    // Delay Parent
    if (parentId && graph["#" + parentId] && pmCode != 'RECW') {
      graph["#" + pId].push("#" + parentId);
      indegree["#" + parentId]++;
    }
    // Delay successor
    var dependPred = vList[i].getDependPredWithParent(vList);
    if (!dependPred) continue;
    var dependStr = dependPred + '';
    var depList = dependStr.split(',');
    var nbPred = depList.length;
    for (var k = 0; k < nbPred; k++) {
      var depListSplit = depList[k].split("#");
      var predId = depListSplit[0];
      var dependencyKey = depListSplit[1];
      var delay = depListSplit[2];
      var predInd = (position["#" + predId]) ?? null; //g.getArrayLocationByID(predId);
      if (!predInd) continue;
      predTask = vList[predInd];
      var type = (depListSplit[3]) ? depListSplit[3] : "E-S";
      if (type == 'E-S' || type == 'E-E' || type == 'S-S') delay[predId + "." + pId] = delay;
      else continue;
      if (graph["#" + predId]) {
        graph["#" + predId].push("#" + pId);
        indegree["#" + pId]++;
      }
    }
  }
  var queue = [];
  for (var key in indegree) {
    if (indegree[key] == 0) queue.push(key);
  }
  var sorted = [];
  while (queue.length > 0) {
    current = queue.shift();
    sorted.push(current);
    for (var key in graph[current]) {
      var next = graph[current][key];
      indegree[next]--;
      if (indegree[next] == 0) queue.push(next);
    }
  }
  if (sorted.length < vList.length) {
    console.error("Infinite dependency loop detected on recalculatePlanningCompute");
    return null;
  }
  for (var i = 0; i < sorted.length; i++) {
    var pId = sorted[i];
    var task = vList[position[pId]];
    var codePm = task.getCodePlanningMode();
    if (codePm == 'MAN') continue;
    var dependPred = task.getSortedDependPredWithParent(vList);
    //if (!dependPred) continue;
    var dependStr = dependPred + '';
    var depList = dependStr.split(',');
    var nbPred = depList.length;
    var newStart = 0;
    var newEnd = 0;
    var duration = parseInt(task.getCalculatedDuration());
    var changed = false;
    var left = parseFloat(task.getItem().leftwork);
    var hasEE = false; var hasES = false; var hasSS = false;
    var idProject = task.getProjectId(vList);
    startPlan = startPlanMain;
    var realStart = (task.getItem().realstartdate) ? getDateForPlanning(task.getItem().realstartdate) : null;
    var realEnd = (task.getItem().realenddate) ? getDateForPlanning(task.getItem().realenddate) : null;
    var plannedStart = (task.getItem().plannedstartdate) ? getDateForPlanning(task.getItem().plannedstartdate) : null;
    var plannedEnd = (task.getItem().plannedenddate) ? getDateForPlanning(task.getItem().plannedenddate) : null;
    if (isOffDay(startPlan, idProject)) startPlan = addWorkDaysToDate(startPlan, 2, idProject);
    if (codePm == 'RECW') {
      var parentId = task.getParent();
      var parent = vList[position['#' + parentId]];
      if (parent) {
        changed = true;
        newStart = parent.getStart();
        newEnd = parent.getEnd();
        //duration=0;//parseInt(parent.getDuration());
      }
    }
    if (!dependPred && codePm != 'RECW' && !realStart) {
      if (left==0 || ! plannedStart || plannedStart<startPlan ) newStart = startPlan;
      else newStart=plannedStart;
      while (isOffDay(newStart, idProject)) { newStart = addDaysToDate(newStart, 1); }
      if (JSGantt.formatDateStr(task.getStart(), 'default') != JSGantt.formatDateStr(newStart, 'default')) {
        newEnd = addWorkDaysToDate(newStart, duration, idProject);
        changed = true;
      }
    } else for (var k = 0; k < nbPred; k++) {
      var depListSplit = depList[k].split("#");
      var predId = depListSplit[0];
      var dependencyKey = depListSplit[1];
      var delay = parseInt(depListSplit[2]);
      var type = (depListSplit[3]) ? depListSplit[3] : "E-S";
      var predItem = (position['#' + predId]) ? vList[position['#' + predId]] : null;
      if (!predItem) {
        continue;
      } else if (type == "E-S") {
        hasES = true;
        if (delay >= 0) {
          decal = (predItem.getMile()) ? delay + 1 : delay + 2;
          testStart = addWorkDaysToDate(predItem.getEnd(), decal, idProject);
        } else {
          decal = delay * -1;
          testStart = removeWorkDaysToDate(predItem.getEnd(), decal, idProject);
        }
        if (testStart > newStart) {
          newStart = testStart;
          if (codePm == 'RECW') duration = workDayDiffDates(newStart, newEnd, idProject)
          else newEnd = addWorkDaysToDate(newStart, duration, idProject);

          changed = true;
        }
      } else if (type == "S-S") {
        hasSS = true;
        decal = delay;
        if (decal < 0) decal -= 1;
        else if (decal > 0) decal += 1;
        testStart = addWorkDaysToDate(predItem.getStart(), decal, idProject);
        if (testStart > newStart) {
          newStart = testStart;
          newEnd = addWorkDaysToDate(newStart, duration, idProject);
          changed = true;
        }
      } else if (type == "E-E") {
        hasEE = true;
        testEnd = predItem.getEnd();
        if (codePm == 'RECW' && testEnd < newEnd) {
          newEnd = testEnd;
          changed = true;
        } else if (testEnd > newEnd) {
          newEnd = testEnd;
          newStart = removeWorkDaysToDate(newEnd, duration, idProject);
          changed = true;
        }
      }
    }
    var realEnd = (task.getItem().realenddate) ? JSGantt.parseDateStr(task.getItem().realenddate, g.getDateInputFormat()) : null;
    if (task.getGroup()) {
      newStart = realStart;
      newEnd = realEnd;
      changed = false;
      for (var j = 0; j < vList.length; j++) {
        if (vList[j].getParent() == task.getID()) {
          if (vList[j].getCodePlanningMode() == 'RECW') continue;
          if (!newStart || vList[j].getStart() < newStart) newStart = vList[j].getStart();
          if (!newEnd || vList[j].getEnd() > newEnd) newEnd = vList[j].getEnd();
        }
      }
      if (newStart != task.getStart() || newEnd != task.getEnd()) changed = true;
    } else if (codePm == 'DDUR' || codePm == 'CDUR') {
      valStart = task.getValidatedStart();
      if (valStart && (valStart > newStart || (valStart < newStart && codePm == 'DDUR' && !hasES && !hasSS)) && !hasEE) {
        newStart = valStart;
        newEnd = addWorkDaysToDate(valStart, duration, idProject);
        changed = true;
      } else if (duration != task.getDuration()) {
        changed = true;
        newEnd = addWorkDaysToDate(newStart, duration, idProject);
      }
    } else if (codePm == 'REGUL' || codePm == 'FULL' || codePm == 'HALF' || codePm == 'QUART') {
      valStart = task.getValidatedStart();
      valEnd = task.getValidatedEnd();
      if (valStart != newStart && valStart >= startPlan && !hasES && !hasSS) {
        newStart = valStart;
        changed = true;
      }
      if (valEnd != newEnd) {
        newEnd = valEnd;
        changed = true;
      }
    } else if (codePm == 'START' || codePm == 'STARR') {
      if (task.getValidatedStart() > newStart) {
        newStart = task.getValidatedStart();
        newEnd = addWorkDaysToDate(newStart, duration, idProject);
        changed = true;
      }
    } else if (codePm == 'FIXED') {
      if (task.getClass() == "Milestone" && task.getPlannedEnd()) {
        newStart = getDateForPlanning(task.getPlannedEnd());
      } else {
        newStart = getDateForPlanning(task.getValidatedStart());
      }
      newEnd = newStart;
      changed = true;
    } else if (codePm == 'FLOAT') {
      if (task.getClass() == "Milestone" && task.getValidatedEnd() && task.getSortedDependPredWithParent(vList).length==0) {
        newStart = getDateForPlanning(task.getValidatedEnd());
        if (newStart<new Date()) newStart=new Date();
        //newStart=getDateForPlanning(newStart);
        changed = true;
      }
    } else {
      if (duration != task.getDuration()) {
        changed = true;
        newEnd = addWorkDaysToDate(newStart, duration, idProject);
      }
    }
    if (realStart) newStart = realStart;
    if (realEnd) newEnd = realEnd;
    if (realStart && !realEnd && (codePm == 'FDUR' || codePm == 'DDUR' || codePm == 'CDUR' || codePm == 'ASAP' || codePm == 'GROUP')) {
      if (realStart < startPlan) newEnd = addWorkDaysToDate(realStart, duration, idProject);
      else newEnd = addWorkDaysToDate(startPlan, duration, idProject);
    }
    // Control if planning is already constrained
    var plannedStart = getDateForPlanning(task.getItem().plannedstartdate);
    var plannedEnd = getDateForPlanning(task.getItem().plannedenddate);
    var inheritedStart = getDateForPlanning(task.getItem().inheritedstartdate);
    if (!task.getGroup() && plannedStart && newStart < plannedStart && inheritedStart < plannedStart
      && codePm != 'FIXED' && codePm != 'FLOAT' && codePm != 'REGUL' && codePm != 'QUART' && codePm != 'FULL' && codePm != 'HALF') {
      newStart = plannedStart;
      newPlannedEnd = addWorkDaysToDate(newStart, duration, idProject);
      newEnd = (plannedEnd > newPlannedEnd) ? plannedEnd : newPlannedEnd;
    }
    if (changed) {
      if (newEnd < newStart) newEnd = newStart;
      task = recalculatePlanningSaveDates(task, newStart, newEnd);
      vList[position[pId]] = task;
      var parentId = vList[i].getParent();
      if (parentId && codePm != 'RECW') recalculatePlanningUpdateParent(parentId, parent, position, vList);
    }

  }
  console.timeEnd('recalculatePlanningCompute()');
}
function recalculatePlanningUpdateParent(parentId, parent, position, vList) {
  if (removeQuickPlanningFeature == "1") return;
  if (parentId && parent['#' + parentId]) {
    parentItem = vList[position['#' + parentId]];
    var startParent = null;
    var endParent = null;
    for (var k = 0; k < parent['#' + parentId].length; k++) {
      var child = vList[position['#' + parent['#' + parentId][k]]];
      if (child.getCodePlanningMode() == 'RECW') continue;
      if (!startParent || startParent > child.getStart()) startParent = child.getStart();
      if (!endParent || endParent < child.getEnd()) endParent = child.getEnd();
    }
    if ((startParent && startParent != parentItem.getStart()) || (endParent && endParent != parentItem.getEnd())) {
      parentItem = recalculatePlanningSaveDates(parentItem, startParent, endParent);
    }
    topId = parentItem.getParent();
    recalculatePlanningUpdateParent(topId, parent, position, vList);
  }
}

var recalculatePlanningSaveDatesTimeout = null;
var recalculatePlanningSaveDatesAllData = '';
function recalculatePlanningSaveDates(task, start, end, forced) {
  if (removeQuickPlanningFeature == "1") return task;
  var taskIsChanged = false;
  if (forced == undefined) forced = false;
  if (forced
    || (start && transformDateToSqlDate(task.getStart()) != transformDateToSqlDate(start))
    || (end && transformDateToSqlDate(task.getEnd()) != transformDateToSqlDate(end))) {
    task.setChanged(true, false); //includes setting color : task.setColor((task.getGroup())?'676784':'a9a9dc');
    if (task.getChanged() || forced) taskIsChanged = true; // only if really changed
    else return task;
  }
  if (start) task.setStart(start);
  if (end) task.setEnd(end);
  task.getItem().quickplanstartdate = start;
  task.getItem().quickplanenddate = end;
  if (taskIsChanged) {
    if (recalculatePlanningSaveDatesTimeout) clearTimeout(recalculatePlanningSaveDatesTimeout);
    currentVal = task.getItem().id + '|' + transformDateToSqlDate(start) + '|' + transformDateToSqlDate(end) + '|' + task.getUpdated();
    recalculatePlanningSaveDatesAllData += ((recalculatePlanningSaveDatesAllData) ? "XXX" : "") + currentVal;
    recalculatePlanningSaveDatesTimeout = setTimeout("recalculatePlanningSaveDatesCallServer();", 100);
  }
  return task;
}
function recalculatePlanningSaveDatesCallServer() {
  if (removeQuickPlanningFeature == "1") return;
  url = "../tool/recalculatePlanningSaveDates.php" + addTokenIndexToUrl('?') + '&data=' + recalculatePlanningSaveDatesAllData;
  recalculatePlanningSaveDatesAllData = '';
  dojo.xhrGet({
    url: url,
    handleAs: "text",
    load: function(data) {
      // Nothing here
    }
  });
}
//#11177
function gotoListFromPlanning(refId, refType, taskId, idProject) {
  if (refType == 'Replan' || refType == 'Construction' || refType == 'Fixed') {
    refType = 'Project';
  }

  gotoObjectList = true;
  directSelectProject(refType, refId, true, false);
}

//#11179
function filterListFromPlanning(refId, refType, taskId, idProject) {
  if (refType != 'Activity') {
    return;
  }

  JSGantt.hideMenu();
  hideDetailScreen();
  JSGantt.closeEditRowObjectPlanning();

  dojo.xhrGet({
    url: '../tool/getSingleData.php?dataType=getWbsSortable&objectClass=' + refType + '&objectId=' + refId + addTokenIndexToUrl(),
    handleAs: "text",
    load: function(wbsSortable) {
      if (!wbsSortable) return;

      planningJsonListFilter.active = true;
      planningJsonListFilter.objectClass = 'Activity';
      planningJsonListFilter.idProject = idProject;
      planningJsonListFilter.wbsSortable = wbsSortable;
      planningJsonListFilter.refId = refId;

      var callBack = function() {
        applyPlanningFilterProjectSelection(idProject);
        setTimeout(function() {
          refreshJsonList('Activity');
          setTimeout(function() {
            selectRowById("objectGrid", parseInt(refId));
          }, 300);
        }, 150);
      };

      loadContent("objectMain.php?objectClass=Activity", "centerDiv", null, false, false, refId, false, callBack);
    }
  });
}

function applyPlanningFilterProjectSelection(idProject) {
  if (!idProject) return;

  currentSelectedProject = idProject;

  if (dijit.byId('projectSelectorFiletering')) {
    dijit.byId('projectSelectorFiletering').set('value', idProject);
  }

  pqProjectCheckClearAll();

  arraySelectedProject.splice(0);

  if (pqProjectCheckSet(idProject, true)) {
    arraySelectedProject.push(String(idProject));
  }

  if (dojo.byId('selectedProject')) {
    dojo.byId('selectedProject').value = idProject;
  }
}



var criticalPathFilterActive = false;
function getCriticalPathLines() {
  if (typeof g == 'undefined' || !g || !g.getList) return null;
  if (!g.getShowCriticalPath()) return null; 

  var vList = g.getList();
  var listToShow = [];
  for (var i = 0; i < vList.length; i++) {
    if (vList[i].getIsOnCriticalPath && vList[i].getIsOnCriticalPath() == '1') {
      listToShow.push(vList[i].getID());
    }
  }
  return listToShow;
}

function toggleCriticalPathFilter() {
  if (typeof g == 'undefined' || !g) return;
  if (!criticalPathFilterActive) {
    if (dojo.byId("predecessorSequence") && dojo.byId("successorSequence")
        && (dojo.byId("predecessorSequence").innerHTML != '' || dojo.byId("successorSequence").innerHTML != '')) {
      predecessorSuccessorReset();
    }
    var listToShow = getCriticalPathLines();
    if (listToShow === null) { showAlert(i18n('criticalPathFilterNotActive')); return; }
    if (listToShow.length == 0) { showAlert(i18n('criticalPathFilterEmpty')); return; }
    criticalPathFilterActive = true;
    g.setCriticalPathFilterActive(true);
	
    showWait();
    showOnlySelectedLines(listToShow);
    hideWait();
	
    var leftsideNode = dojo.byId("leftside");
    var spacingNodes = dojo.query(".ganttSpacingDiv", leftsideNode);
    spacingNodes.forEach(function(node) { node.style.display = 'none'; });
    var expandNodes = dojo.query(".ganttExpandOpened, .ganttExpandClosed", leftsideNode);
    expandNodes.forEach(function(node) {
      node.style.display = 'none';
    });
    dojo.addClass('criticalPathFilterButton', 'criticalPathFilterActive');
  } else {
    criticalPathFilterActive = false;
    g.setCriticalPathFilterActive(false);
    showWait();
    showOnlySelectedLines([]);
    hideWait();
    var leftsideNode = dojo.byId("leftside");
    dojo.query(".ganttSpacingDiv", leftsideNode).forEach(function(node) { node.style.display = 'block'; });
    dojo.query(".ganttExpandOpened, .ganttExpandClosed", leftsideNode).forEach(function(node) { node.style.display = ''; });
    dojo.removeClass('criticalPathFilterButton', 'criticalPathFilterActive');
  }
}

function resetCriticalPathFilterIfActive() {
  if (criticalPathFilterActive) {
    criticalPathFilterActive = false;
    dojo.removeClass('criticalPathFilterButton', 'criticalPathFilterActive');
  }
}
