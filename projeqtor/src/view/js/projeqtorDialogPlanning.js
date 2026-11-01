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

// =============================================================================
// = Assignments
// =============================================================================

function addAssignment(unit, rawUnit, hoursPerDay, isTeam, isOrganization,
    isResourceTeam, isMaterial) {

  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
  
  if(dijit.byId('dialogEditAssignmentPlanning') && dijit.byId('dialogEditAssignmentPlanning').open){
    var objClass=dojo.byId('assignmentDialogObjectClass').value;
    var objId = dojo.byId("assignmentDialogObjectId").value;
    var idProject = dojo.byId('assignmentDialogIdProject').value;
  }else{
    var objClass=dojo.byId('objectClass').value;
    var objId = dojo.byId("objectId").value;
    var idProject = dijit.byId('idProject').get('value');
  }

  var callBack=function() {
    dijit.byId("dialogAssignment").show();
  };
  var params="&refType=" + objClass;
  params+="&refId=" + objId;
  params+="&idProject=" + idProject;
  params+="&unit=" + unit;
  if (objClass == 'Meeting'
      || objClass == 'PeriodicMeeting') {
    params+="&meetingEndTime=" + dijit.byId('meetingEndTime');
    params+="&meetingEndTimeValue=" + dijit.byId('meetingEndTime').get('value');
    params+="&meetingStartTime=" + dijit.byId('meetingStartTime');
    params+="&meetingStartTimeValue="
        + dijit.byId('meetingStartTime').get('value');
    params+="&rawUnit=" + rawUnit;
    params+="&hoursPerDay=" + hoursPerDay;
  }
  if (objClass == 'PokerSession') {
    params+="&pokerSessionEndTime=" + dijit.byId('pokerSessionEndTime');
    params+="&pokerSessionEndTimeValue="
        + dijit.byId('pokerSessionEndTime').get('value');
    params+="&pokerSessionStartTime=" + dijit.byId('pokerSessionStartTime');
    params+="&pokerSessionStartTimeValue="
        + dijit.byId('pokerSessionStartTime').get('value');
    params+="&rawUnit=" + rawUnit;
    params+="&hoursPerDay=" + hoursPerDay;
  }
  if (objClass != 'PeriodicMeeting'
      && objClass != 'PokerSession') {
    if(dijit.byId('dialogEditAssignmentPlanning') && dijit.byId('dialogEditAssignmentPlanning').open){
      var validatedWork = dojo.byId("assignmentDialogValidatedWork").value;
      var assignedWork = dojo.byId("assignmentDialogAssignedWork").value;
    }else{
      var validatedWork = dijit.byId(objClass + "PlanningElement_validatedWork").get('value');
      var assignedWork = dijit.byId(objClass + "PlanningElement_assignedWork").get('value');
    }
    params+="&validatedWorkPe=" + validatedWork;
    params+="&assignedWorkPe=" + assignedWork;
  }
  params+="&isTeam=" + isTeam + "&isOrganization=" + isOrganization
      + "&isResourceTeam=" + isResourceTeam+ "&isMaterial=" + isMaterial;
  ;
  params+="&mode=add";
  loadDialog('dialogAssignment', callBack, false, params);
}

var editAssignmentLoading=false;
function editAssignment(assignmentId, idResource, idRole, cost, rate,
    assignedWork, realWork, leftWork, unit, optional) {
  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
  var callBack=function() {
    editAssignmentLoading=false;
    assignmentUpdatePlannedWork('assignment');
    dijit.byId("dialogAssignment").show();
  };
  
  if(dijit.byId('dialogEditAssignmentPlanning') && dijit.byId('dialogEditAssignmentPlanning').open){
    var objClass=dojo.byId('assignmentDialogObjectClass').value;
    var objId = dojo.byId("assignmentDialogObjectId").value;
    var idProject = dojo.byId('assignmentDialogIdProject').value;
  }else{
    var objClass=dojo.byId('objectClass').value;
    var objId = dojo.byId("objectId").value;
    var idProject = dijit.byId('idProject').get('value');
  }
  
  var params="&idAssignment=" + assignmentId;
  params+="&refType=" + objClass;
  params+="&idProject=" + idProject;
  params+="&refId=" + objId;
  params+="&idResource=" + idResource;
  params+="&idRole=" + idRole;
  params+="&mode=edit";
  params+="&unit=" + unit;
  params+="&realWork=" + realWork;
  editAssignmentLoading=true;
  loadDialog('dialogAssignment', callBack, false, params);
}

function divideAssignment(assignedIdOrigin, unit) {
  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
  var callBack=function() {
    dijit.byId("dialogAssignment").show();
  };
  
  if(dijit.byId('dialogEditAssignmentPlanning') && dijit.byId('dialogEditAssignmentPlanning').open){
    var objClass=dojo.byId('assignmentDialogObjectClass').value;
    var objId = dojo.byId("assignmentDialogObjectId").value;
    var idProject = dojo.byId('assignmentDialogIdProject').value;
  }else{
    var objClass=dojo.byId('objectClass').value;
    var objId = dojo.byId("objectId").value;
    var idProject = dijit.byId('idProject').get('value');
  }
  
  var params="&refType=" + objClass;
  params+="&refId=" + objId;
  params+="&idProject=" + idProject;
  params+="&assignedIdOrigin=" + assignedIdOrigin;
  params+="&unit=" + unit;
  params+="&mode=divide";
  loadDialog('dialogAssignment', callBack, false, params);
}

function assignmentUpdateLeftWork(prefix) {
  var initAssigned=dojo.byId(prefix + "AssignedWorkInit");
  var initLeft=dojo.byId(prefix + "LeftWorkInit");
  var assigned=dojo.byId(prefix + "AssignedWork");
  var newAssigned=dojo.number.parse(assigned.value);
  var objClass=null;
  if(dijit.byId('dialogEditAssignmentPlanning') && dijit.byId('dialogEditAssignmentPlanning').open){
    objClass=dojo.byId('assignmentDialogObjectClass').value;
  }else{
    objClass=dojo.byId('objectClass').value;
  }

  if (objClass == 'Activity' && prefix == 'assignment') {
    if(dijit.byId('dialogEditAssignmentPlanning') && dijit.byId('dialogEditAssignmentPlanning').open){
      var isOnRealTime=dojo.byId('assignmentDialogWorkOnRealTime').value;
      isOnRealTime = (isOnRealTime == 1)?'on':0;
    }else{
      var isOnRealTime=dijit.byId('workOnRealTime').get('value');
    }
    if (isOnRealTime == 'on') {
      var realdWork=dojo.byId(prefix + "RealWork").value;
      if (newAssigned < realdWork) {
        dijit.byId(prefix + "AssignedWork").set("value", initAssigned.value);
        dijit.byId(prefix + "LeftWork").set("value", initLeft.value);
        showAlert(i18n('assingedWorkCantBeLowerInWorkOnRealTime'));
        return;
      }
    }
  }

  if (newAssigned == null || isNaN(newAssigned)) {
    newAssigned=0;
    assigned.value=dojo.number.format(newAssigned);
  }
  var left=dojo.byId(prefix + "LeftWork");
  var real=dojo.byId(prefix + "RealWork");
  diff=dojo.number.parse(assigned.value) - initAssigned.value;
  newLeft=parseFloat(initLeft.value) + diff;
  if (newLeft < 0 || isNaN(newLeft)) {
    newLeft=0;
  }
  if (assigned.value != initAssigned.value) {
    diffe=dojo.number.parse(assigned.value) - dojo.number.parse(real.value);
    if (initAssigned.value == 0 || isNaN(initAssigned.value)) {
      newLeft=0 + diffe;
    }
  }
  left.value=dojo.number.format(newLeft);
  assignmentUpdatePlannedWork(prefix);
}

function assignmentUpdatePlannedWork(prefix) {
  var left=dojo.byId(prefix + "LeftWork");
  var newLeft=dojo.number.parse(left.value);
  if (newLeft == null || isNaN(newLeft)) {
    newLeft=0;
    left.value=dojo.number.format(newLeft);
  }
  var real=dojo.byId(prefix + "RealWork");
  var planned=dojo.byId(prefix + "PlannedWork");
  newPlanned=dojo.number.parse(real.value) + dojo.number.parse(left.value);
  planned.value=dojo.number.format(newPlanned);

}

function saveAssignment(definitive) {
  var formVar=dijit.byId('assignmentForm');
  var planningMode=dojo.byId('planningMode').value;
  var mode=dojo.byId('mode').value;
  var isTeam=dojo.byId('isTeam').value;
  var isOrga=dojo.byId('isOrganization').value;
  
  var objClass=null;
  var objId = null;
  var idProject = null;
  if(dijit.byId('dialogEditAssignmentPlanning') && dijit.byId('dialogEditAssignmentPlanning').open){
    objClass=dojo.byId('assignmentDialogObjectClass').value;
    objId = dojo.byId("assignmentDialogObjectId").value;
    idProject = dojo.byId('assignmentDialogIdProject').value;
  }else{
    objClass=dojo.byId('objectClass').value;
    objId = dojo.byId("objectId").value;
    idProject = dijit.byId('idProject').get('value');
  }

  if (objClass == 'Activity') {
    var isOnRealTime=null;
    if(dijit.byId('dialogEditAssignmentPlanning') && dijit.byId('dialogEditAssignmentPlanning').open){
      isOnRealTime=dojo.byId('assignmentDialogWorkOnRealTime').value;
      isOnRealTime = (isOnRealTime == '1')?'on':0;
    }else{
      isOnRealTime=dijit.byId('workOnRealTime').get('value');
    }
    if (isOnRealTime == 'on') {
      var realdWork=dojo.byId('assignmentRealWork').value, assign=dojo
          .byId('assignmentAssignedWork').value;
      if (assign < realdWork) {
        dijit.byId("assignmentAssignedWork").set("value",
            dojo.byId('assignedWorkOrigin').value);
        showAlert(i18n('assingedWorkCantBeLowerInWorkOnRealTime'));
        return;
      }
    }
  }

  if (formVar.validate()) {
    dijit.byId("assignmentPlannedWork").focus();
    dijit.byId("assignmentLeftWork").focus();
    url="../tool/saveAssignment.php";
    if (definitive)
      url+="?definitive=" + definitive;
    if (planningMode == 'MAN' && mode != 'edit' && !isTeam && !isOrga) {
      var callback=function() {
        var lastOperationStatus=dojo.byId('lastOperationStatus').value;
        if (lastOperationStatus != 'INVALID') {
          var params="&idAssignment=" + dojo.byId('idAssignment').value;
          params+="&refType=" + objClass;
          params+="&idProject=" + idProject;
          params+="&refId=" + objId;
          params+="&idResource="
              + dijit.byId('assignmentIdResource').get('value');
          params+="&idRole=" + dijit.byId('assignmentIdRole').get('value');
          params+="&unit=" + dojo.byId('assignmentAssignedUnit').value;
          params+="&realWork=" + dijit.byId('assignmentRealWork').get('value');
          params+=dijit.byId('assignmentDailyCost').get('value');
          params+="&mode=edit";
          loadDialog('dialogAssignment', null, false, params);
          var params="&objectClass=" + objClass + "&objectId=" + objId;//var params="&objectClass=" + refType + "&objectId=" + refId;
          //if(dojo.byId('GanttChartDIV'))loadDialog('dialogEditAssignmentPlanning', null, true, params); //comment for #10958
        } else {
          dijit.byId('dialogAssignment').hide();
          if(dojo.byId('GanttChartDIV'))loadDialog('dialogEditAssignmentPlanning', null, false);
        }
      };
      
      loadContent(url, "resultDivMain", "assignmentForm", true, 'assignment',
            null, null, callback);
    } else {
      var callback=function() {
        if(dijit.byId('dialogEditAssignmentPlanning') && dijit.byId('dialogEditAssignmentPlanning').open){
          var objClass=dojo.byId('assignmentDialogObjectClass').value;
          var objId = dojo.byId("assignmentDialogObjectId").value;
          var params="&objectClass=" + objClass + "&objectId=" + objId;
          loadDialog('dialogEditAssignmentPlanning', null, true, params);
        }
      };
      loadContent(url, "resultDivMain", "assignmentForm", true, 'assignment',null,null,callback);
      dijit.byId('dialogAssignment').hide();
    }
  } else {
    showAlert(i18n("alertInvalidForm"));
  }
}

function removeAssignment(assignmentId, realWork, resource) {
  var planningMode=dojo.byId('planningMode').value;
  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
  if (parseFloat(realWork)) {
    msg=i18n('msgUnableToDeleteRealWork');
    showAlert(msg);
    return;
  }
  var objClass=null;
  var objId = null;
  if(dijit.byId('dialogEditAssignmentPlanning') && dijit.byId('dialogEditAssignmentPlanning').open){
    objClass=dojo.byId('assignmentDialogObjectClass').value;
    objId = dojo.byId("assignmentDialogObjectId").value;
  }else{
    objClass=dojo.byId('objectClass').value;
    objId = dojo.byId("objectId").value;
  }
  actionOK=function() {
    var callback=function() {
      if(dijit.byId('dialogEditAssignmentPlanning') && dijit.byId('dialogEditAssignmentPlanning').open){
        var objClass=dojo.byId('assignmentDialogObjectClass').value;
        var objId = dojo.byId("assignmentDialogObjectId").value;
        var params="&objectClass=" + objClass + "&objectId=" + objId;
        loadDialog('dialogEditAssignmentPlanning', null, true, params);
      }
    };
    loadContent("../tool/removeAssignment.php?assignmentId=" + assignmentId
        + "&assignmentRefType=" + objClass
        + "&assignmentRefId=" + objId + "&planningMode="
        + planningMode, "resultDivMain", null, true, "assignment", null, null ,callback);
  };
  msg=i18n('confirmDeleteAssignment', new Array(resource));
  if (planningMode == 'MAN') {
    msg+='<br/><br/>' + i18n("confirmControlDeletePlannedWork");
  }
  showConfirm(msg, actionOK);
}

function assignmentChangeResourceTeamForCapacity() {
  if (editAssignmentLoading)
    return;
  var idResource=dijit.byId("assignmentIdResource").get("value");
  var isResourceTeamDialog=document.getElementById("isResourceTeam").value;
  if (idResource.trim()) {
    enableWidget('dialogAssignmentSubmit');
  } else {
    disableWidget('dialogAssignmentSubmit');
  }
  if (!idResource.trim()) {
    dojo.byId('assignmentRateRow').style.display="table-row";
    dojo.byId('assignmentCapacityResourceTeam').style.display="none";
    dojo.byId('assignmentUniqueSelection').style.display="none";
    dijit.byId('assignmentUnique').set('checked', false);
    dijit.byId('assignmentIdRole').set('value', null);
    return;
  }
  dojo.xhrGet({
    url : '../tool/getIfResourceTeamOrResource.php?idResource=' + idResource+addTokenIndexToUrl(),
    handleAs : "text",
    load : function(data) {
      if (idResource.trim() && data == 'isResourceTeam' && !isResourceTeamDialog) { // in case if we are in resourceTeam assignment dialog
        var prop=(dijit.byId('assignmentProportional') && dijit.byId('assignmentProportional').get('checked')==true)?true:false; 
        if (!prop) dojo.byId('assignmentRateRow').style.display="none";
        dojo.byId('assignmentCapacityResourceTeam').style.display="table-row";
        dojo.byId('assignmentUniqueSelection').style.display="table-row";
      } else {
        dojo.byId('assignmentRateRow').style.display="table-row";
        dojo.byId('assignmentCapacityResourceTeam').style.display="none";
        dojo.byId('assignmentUniqueSelection').style.display="none";
        dijit.byId('assignmentUnique').set('checked', false);
      }
      var planningMode=dojo.byId('planningMode').value;
      if (planningMode == 'MAN') {
        dojo.byId('assignmentRateRow').style.display="none";
      }
    }
  });
}

function assignmentChangeUniqueResource(newValue) {
  if (newValue == false) {
    dojo.byId('assignmentRateRow').style.display="none";
    dojo.byId('assignmentCapacityResourceTeam').style.display="table-row";
  } else {
    dojo.byId('assignmentRateRow').style.display="table-row";
    dojo.byId('assignmentCapacityResourceTeam').style.display="none";
  }
}

var assignmentUserSelectUniqueResourceCurrent=null;
function assignmentUserSelectUniqueResource(newValue, idRes) {
  if (assignmentUserSelectUniqueResourceCurrent != null)
    return;
  assignmentUserSelectUniqueResourceCurrent=idRes;
  dojo.query(".dialogAssignmentManualSelectCheck").forEach(
      function(node, index, nodelist) {
        var id=node.getAttribute('widgetid');
        if (dijit.byId(id) && parseInt(id.substr(34)) != parseInt(idRes)) {
          dijit.byId(id).set('checked', false);
        }
      });
  dojo.byId("dialogAssignmentManualSelect").value=(newValue) ? idRes : null;
  setTimeout("assignmentUserSelectUniqueResourceCurrent=null;", 100);
}

function assignmentChangeResource(convertionRate) {
  if (editAssignmentLoading)
    return;
  var idResource=dijit.byId("assignmentIdResource").get("value");
  var isTeam=dojo.byId("isTeam").value;
  var isOrganization=dojo.byId("isOrganization").value;
  var isResourceTeam=dojo.byId("isResourceTeam").value;
  if (isTeam=='1' || isOrganization=='1') return;
  if (!idResource) {
    return;
  }
  if (dijit.byId('assignmentDailyCost')) {
    dijit.byId('assignmentDailyCost').reset();
  }
  dojo.xhrGet({
    url : '../tool/getSingleData.php?dataType=isResourceTeam&idResource='
        + idResource + ''+addTokenIndexToUrl(),
    handleAs : "text",
    load : function(data) {
      callBack=null; // PBER #11162 - no callBack needed
      loadContent('../tool/refreshRoleAssignment.php?idResource='+idResource+"&convertionRate="+convertionRate,
          'assignmentIdRoleDiv', 'assignmentForm', null, null, null, null,callBack);
      if (1 || data == 1) {
        dijit.byId('assignmentIdRole').required = false
      } else {
        dijit.byId('assignmentIdRole').required = true;
      }
    }
  });
  dojo.xhrGet({
    url : '../tool/getSingleData.php?dataType=resourceRole&idResource='
        + idResource + '&isTeam=' + isTeam + '&isOrganization='
        + isOrganization + '&isResourceTeam=' + isResourceTeam+addTokenIndexToUrl(),
    handleAs : "text",
    load : function(data) {
      // if (data) dijit.byId('assignmentCapacity').set('value',
      // parseInt(data)); // Error fixed by PBER : we retreive an idRole (and
      // must)
      if (data)
        dijit.byId('assignmentIdRole').set('value', parseInt(data));
    }
  });
}

function assignmentChangeResourceSelectFonction() {
  if (editAssignmentLoading)
    return;
  var idResource=dijit.byId("assignmentIdResource") ? dijit.byId("assignmentIdResource").get("value") : dijit.byId("idResource").get("value");

  if (!idResource) {
    return;
  }
  if (dijit.byId('assignmentDailyCost')) {
    dijit.byId('assignmentDailyCost').reset();
  }
  dojo.xhrGet({
    url : '../tool/getSingleData.php?dataType=resourceRole&idResource='
        + idResource+addTokenIndexToUrl(),
    handleAs : "text",
    load : function(data) {
      var roleId = dijit.byId("assignmentIdRole") ? "assignmentIdRole" : "idRole";
      var roleWidget = dijit.byId(roleId);
      refreshListSpecific('listRoleResource', roleId, 'idResource', idResource);
      if (data) {
        roleWidget.set('value', parseInt(data));
      } else {
        roleWidget.set('value', null);
      }
    }
  });
}	

function refreshReccurentAssignmentDiv() {
  showWait();
  callBack=function() {
    hideWait();
  };
  loadContent('../tool/refreshReccurentAssignmentDiv.php',
      'recurringAssignmentDiv', 'assignmentForm', null, null, null, null,
      callBack);
}

function assignmentChangeRole(conversionRate) {
  if (editAssignmentLoading)
    return;
  var idResource=dijit.byId("assignmentIdResource").get("value")
  var idRole=dijit.byId("assignmentIdRole").get("value");
  if (!idRole.trim() && !isResourceTeam)
    disableWidget('dialogAssignmentSubmit');
  else if (dijit.byId('dialogAssignmentSubmit').get('disabled') == true)
    enableWidget('dialogAssignmentSubmit');
  if (!idResource || !idRole)
    return;
  dojo.xhrGet({
    url : '../tool/getSingleData.php?dataType=resourceCost&idResource='
        + idResource + '&idRole=' + idRole+addTokenIndexToUrl(),
    handleAs : "text",
    load : function(data) {
      dijit.byId('assignmentDailyCost').set('value', dojo.number.format(data));
	  if (dijit.byId('assignmentDailyCostLocal')) calculateAmountFromConvertion(dijit.byId('assignmentDailyCost').get('value'),conversionRate,'assignmentDailyCostLocal')
    }
  });
}
saveLeftWorkInProgress=false;
function assUpdateLeftWork(id, dialogEdit) {
  saveLeftWorkInProgress=true;
  var idDialogEdit = (dialogEdit)?'dialogEdit_':'';
  var initAss=dojo.byId(idDialogEdit+'initAss_' + id).value;
  var assign=dijit.byId(idDialogEdit+"assAssignedWork_" + id).get('value');
  var newAss=assign;
  if (newAss == null || isNaN(newAss)) {
    newAss=0;
    dijit.byId(idDialogEdit+"assAssignedWork_" + id).set('value', 0);
  }
  var objClass=null;
  if(dijit.byId('dialogEditAssignmentPlanning') && dijit.byId('dialogEditAssignmentPlanning').open){
    objClass=dojo.byId('assignmentDialogObjectClass').value;
  }else{
    objClass=dojo.byId('objectClass').value;
  }
  isOnRealTime=false;
  if (objClass == 'Activity') {
    var isOnRealTime=null;
    if(dijit.byId('dialogEditAssignmentPlanning') && dijit.byId('dialogEditAssignmentPlanning').open){
      isOnRealTime=dojo.byId('assignmentDialogWorkOnRealTime').value;
      isOnRealTime = (isOnRealTime == '1')?'on':'off';
    }else{
      isOnRealTime=dijit.byId('workOnRealTime').get('value');
    }
    if (isOnRealTime == 'on') {
      var realdWork=dojo.byId(idDialogEdit+"RealWork_" + id).value;
      if (assign < realdWork) {
        dijit.byId(idDialogEdit+"assAssignedWork_" + id).set("value",
            dojo.byId(idDialogEdit+'initAss_' + id).value);
        dojo.byId(idDialogEdit+'initLeft_' + id).value=dojo.byId(idDialogEdit+'initAss_' + id).value;
        showAlert(i18n('assingedWorkCantBeLowerInWorkOnRealTime'));
        return;
      }
    }
  }
  var leftWork=dijit.byId(idDialogEdit+'assLeftWork_' + id).get("value");
  var diff=(newAss) - (initAss);
  var newLeft=leftWork + diff;
  if (newLeft < 0 || isNaN(newLeft)) {
    newLeft=0;
  }
  var assPeAss=dijit.byId(objClass + 'PlanningElement_assignedWork');
  var valPeAss=dijit.byId(objClass + 'PlanningElement_validatedWork');
  if (assPeAss) {
    assPeAss.set("value", assPeAss.get("value") + diff);
  }
  if (objClass == 'Activity' && isOnRealTime == 'on'
      && valPeAss) {
    valPeAss.set("value", assPeAss.get("value"));
  }
  dijit.byId(idDialogEdit+'assLeftWork_' + id).set("value", newLeft); // Will trigger the
  // saveLeftWork()
  // function
  dojo.byId(idDialogEdit+'initAss_' + id).value=newAss;
  diff=0;
  if(dojo.byId(objClass + 'PlanningElement_assignedCost'))dojo.byId(objClass + 'PlanningElement_assignedCost').style.textDecoration="line-through";
  if (objClass == 'Activity' && isOnRealTime == 'on') {
    if(dojo.byId(objClass + 'PlanningElement_validatedCost'))dojo.byId(objClass + 'PlanningElement_validatedCost').style.textDecoration="line-through";
    ;
  }
}

function assUpdateLeftWorkDirect(id, dialogEdit) {
  saveLeftWorkInProgress=true;
  var idDialogEdit = (dialogEdit)?'dialogEdit_':'';
  var initLeft=dojo.byId(idDialogEdit+'initLeft_' + id).value;
  var assign=dijit.byId(idDialogEdit+"assAssignedWork_" + id).get('value');
  var left=dijit.byId(idDialogEdit+"assLeftWork_" + id).get('value');
  if (left == null || isNaN(left)) {
    left=0;
  }
  var objClass=null;
  if(dijit.byId('dialogEditAssignmentPlanning') && dijit.byId('dialogEditAssignmentPlanning').open){
    objClass=dojo.byId('assignmentDialogObjectClass').value;
  }else{
    objClass=dojo.byId('objectClass').value;
  }
  if (objClass == 'Activity') {
    var isOnRealTime=null;
    if(dijit.byId('dialogEditAssignmentPlanning') && dijit.byId('dialogEditAssignmentPlanning').open){
      isOnRealTime=dojo.byId('assignmentDialogWorkOnRealTime').value;
      isOnRealTime = (isOnRealTime == '1')?'on':'off';
    }else{
      isOnRealTime=dijit.byId('workOnRealTime').get('value');
    }
    if (isOnRealTime == 'on') {
      var realdWork=dojo.byId(idDialogEdit+"RealWork_" + id).value;
      var assign=parseFloat(dijit.byId(idDialogEdit+"assAssignedWork_" + id).get('value'));
      var revised=parseFloat(realdWork) + parseFloat(left);
      if (assign != revised) {
        dijit.byId(idDialogEdit+"assAssignedWork_" + id).set("value", revised);
        dojo.byId(idDialogEdit+'initAss_' + id).value=revised;
      }
    }
  }
  var diff=(left) - (initLeft);
  var assPeLeft=dijit.byId(objClass + 'PlanningElement_leftWork');
  if (assPeLeft) {
    assPeLeft.set("value", assPeLeft.get("value") + diff);
  }
  var assPePlanned=dijit.byId(objClass + 'PlanningElement_plannedWork');
  if (assPePlanned) {
    assPePlanned.set("value", assPePlanned.get("value") + diff);
  }
  //
  dojo.byId(idDialogEdit+'initLeft_' + id).value=left;
  diff=0;
  if(dojo.byId(objClass + 'PlanningElement_leftCost'))dojo.byId(objClass + 'PlanningElement_leftCost').style.textDecoration="line-through";
}

// TODO : check this function that does not seem to be used at all
function saveAssignedWork(id, zone, dialogEdit) {
  saveLeftWorkInProgress=true;
  var idDialogEdit = (dialogEdit == 1)?'dialogEdit_':'';
  var value=dijit.byId(idDialogEdit+"ass" + zone + "_" + id).get("value");
  var objClass=null;
  if(dijit.byId('dialogEditAssignmentPlanning') && dijit.byId('dialogEditAssignmentPlanning').open){
    objClass=dojo.byId('assignmentDialogObjectClass').value;
  }else{
    objClass=dojo.byId('objectClass').value;
  }
  var url='../tool/saveLeftWork.php?idAssign=' + id + '&zone=' + zone
      + '&valueTextZone=' + value;
  dojo.xhrPut({
        url : url+addTokenIndexToUrl(),
        form : (!dialogEdit)?'objectForm':null,
        handleAs : "text",
        load : function(data) {
          addMessage(i18n("col" + zone) + " " + i18n("resultSave"));
          document.getElementById('idImage' + zone + id).style.display="none";
          setTimeout("dojo.byId('idImage" + zone + id
              + "').style.display='block';", 1000);
          saveLeftWorkInProgress=false;
          if(dialogEdit == 1){
            refreshGrid();
          }
        },
        error : function() {saveLeftWorkInProgress=false;}
      });
}

function saveLeftWork(id, zone, dialogEdit) {
  saveLeftWorkInProgress=true;
  var idDialogEdit = (dialogEdit == 1)?'dialogEdit_':'';
  var value=dijit.byId(idDialogEdit+"ass" + zone + "_" + id).get("value");
  if (isNaN(value) || value == null) {
    value=0;
    dijit.byId(idDialogEdit+"ass" + zone + "_" + id).set("value", 0);
  }
  if(dijit.byId('dialogEditAssignmentPlanning') && dijit.byId('dialogEditAssignmentPlanning').open){
    var objClass=dojo.byId('assignmentDialogObjectClass').value;
  }else{
    var objClass=dojo.byId('objectClass').value;
  }
  var isOnRealTime=false;
  if (objClass == 'Activity') {
    if(dijit.byId('dialogEditAssignmentPlanning') && dijit.byId('dialogEditAssignmentPlanning').open){
      isOnRealTime=dojo.byId('assignmentDialogWorkOnRealTime').value;
      isOnRealTime = (isOnRealTime == '1')?'on':0;
    }else{
      isOnRealTime=dijit.byId('workOnRealTime').get('value');
    }
  }
  
  var initLeft=dojo.byId(idDialogEdit+'initLeft_' + id).value;
  var assPeLeft=dijit.byId(objClass + 'PlanningElement_leftWork');
  var assPePlan=dijit.byId(objClass + 'PlanningElement_plannedWork');
  var assPeAss=dijit.byId(objClass + 'PlanningElement_assignedWork');
  var valPeAss=dijit.byId(objClass + 'PlanningElement_validatedWork');
  
  var diff=value - initLeft;

  if (assPeLeft) {
    assPeLeft.set("value", assPeLeft.get("value") + diff);
  }
  if (assPePlan) {
    assPePlan.set("value", assPePlan.get("value") + diff);
  }
  if (objClass == 'Activity' && isOnRealTime == 'on'
    && assPeAss) {
    assPeAss.set("value", assPePlan.get("value") + diff);
  }
  
  if (objClass == 'Activity' && isOnRealTime == 'on'
    && valPeAss) {
    valPeAss.set("value", assPePlan.get("value") + diff);
  }
  var url='../tool/saveLeftWork.php?idAssign=' + id + '&zone=' + zone
      + '&valueTextZone='+ value;
  dojo.xhrPut({
        url : url+addTokenIndexToUrl(),
        form : (!dialogEdit)?'objectForm':null,
        handleAs : "text",
        load : function(data) {
          if (data.substring(0, 3) == 'OK#') {
            addMessage(i18n("col" + zone) + " " + i18n("resultSave"));
            if (dojo.byId(idDialogEdit+'idImage' + zone + 'KO' + id)) {
              document.getElementById(idDialogEdit+'idImage' + zone + id).style.display="block";
              setTimeout("dojo.byId('"+idDialogEdit+"idImage" + zone + id
                + "').style.display='none';", 1000);
            }
            if(dijit.byId('dialogEditAssignmentPlanning') && dijit.byId('dialogEditAssignmentPlanning').open){
              var objClass=dojo.byId('assignmentDialogObjectClass').value;
              var objId=dojo.byId('assignmentDialogObjectId').value;
            }else{
              var objClass=dojo.byId('objectClass').value;
              var objId=dojo.byId('objectId').value;
            }
            var dataSplit=data.split('#');
            if(dijit.byId(objClass + 'PlanningElement_realEndDate')){
              if(dataSplit.length>1 && dataSplit[1]!=''){
                dijit.byId(objClass + 'PlanningElement_realEndDate').set('value',dataSplit[1]);
              } else {
                dijit.byId(objClass + 'PlanningElement_realEndDate').set('value',null);
              }
            }
            if (dataSplit.length>2) {
              var assDuration=dataSplit[2];
              if (dojo.byId('objectClassManual') && dojo.byId('objectClassManual').value=='Planning' && g) {
                var refClass=dojo.byId('objectClass').value;
                var refId=dojo.byId('objectId').value;
                vList=g.getList();
                var itemId=g.getIDByItemRef(refClass, refId, false);
                var ind=g.getArrayLocationByID(itemId);
                if (vList[ind].getItem().assignedduration!=assDuration) {
                  if (dojo.byId(refClass+'PlanningElement_assignedDuration')) dojo.byId(refClass+'PlanningElement_assignedDuration').value=assDuration;
                  if (dojo.byId('automaticRunPlan') && dojo.byId('automaticRunPlan').checked) {
                    // Call replan ?
                  } else {
                    vList[ind].getItem().assignedduration=assDuration;
                    vList[ind].setUpdated(true);
                    recalculatePlanning();
                  }
                }
              }
            }
          }else{
            if (dojo.byId(idDialogEdit+'idImage' + zone + 'KO' + id)) { 
              dojo.byId(idDialogEdit+'idImage' + zone + 'KO' + id).style.display="block";
              setTimeout("dojo.byId('"+idDialogEdit+"idImage" + zone + 'KO' + id
                + "').style.display='none';", 1000);
            }
            let doc = new DOMParser().parseFromString(data, "text/html");
            var destination = 'resultDivMain';
            var validationType = null;
            var contentNode=dojo.byId(destination);
            contentNode.innerHTML=data;
            var lastOperationStatus=dojo.byId('lastOperationStatus');
            var lastOperation=dojo.byId('lastOperation');
            if (!(lastOperationStatus && lastOperation)) {
              consoleTraceLog("***** Error **** isResultMessage without lastOperation or lastOperationStatus");
              consoleTraceLog(data);
            }
            dojo.fadeIn({
              node:contentNode,
              duration:100,
              onEnd:function() {
                if (!editorInFullScreen()) {
                  finalizeMessageDisplay(destination,validationType);
                } else {
                  var elemDiv=document.createElement('div');
                  elemDiv.id='testFade';
                  var leftMsg=(window.innerWidth - 400) / 2;
                  elemDiv.style.cssText='position:absolute;text-align:center;width:400px;height:auto;z-index:10000;top:50px;left:' + leftMsg + 'px';
                  elemDiv.innerHTML=data;
                  document.body.appendChild(elemDiv);
                  resultDivFadingOut=dojo.fadeOut({
                    node:elemDiv,
                    duration:3000,
                    onEnd:function() {
                      elemDiv.remove();
                    }
                  }).play();
                  hideWait();
                  formInitialize();
                  if (whichFullScreen == 996) {
                  } else if (whichFullScreen >= 0 && editorArray[whichFullScreen]) {
                    editorArray[whichFullScreen].focus();
                  }
                }
              }
            }).play();
          }
          saveLeftWorkInProgress=false;
          dojo.byId('planLastSavedClass').value=objClass;
          dojo.byId('planLastSavedId').value=objId;
          if(dialogEdit == 1){
            refreshGrid();
          }
        },
        error : function() {saveLeftWorkInProgress=false;}
      });
  dojo.byId(idDialogEdit+'initLeft_' + id).value=value;
  if(dojo.byId(objClass + 'PlanningElement_leftCost'))dojo.byId(objClass + 'PlanningElement_leftCost').style.textDecoration="line-through";
  if(dojo.byId(objClass + 'PlanningElement_plannedCost'))dojo.byId(objClass + 'PlanningElement_plannedCost').style.textDecoration="line-through";
}

// =============================================================================
// = Affectation
// =============================================================================

function addAffectation(objectClass, type, idResource, idProject, isTeam, isOrganization) {
  var callBack=function() {
    affectationLoad=true;
    dijit.byId("dialogAffectation").show();
    if (objectClass === "Project") {
      setTimeout(function() {
        var resourceField = dijit.byId('affectationResource');
        var store = resourceField.store;
        if (store) {
          store.fetch({
            onComplete: function(items) {
              if (items && items.length > 0) {
                var firstValue = store.getValue(items[0], 'id');
                resourceField.set('value', firstValue);
                resourceField.focus();
              }
            }
         });
       }  
      }, 200);
    }
    setTimeout("affectationLoad=false", 500);
  };
  var params="&idProject=" + idProject;
  params+="&objectClass=" + objectClass;
  params+="&idResource=" + idResource;
  params+="&type=" + type;
  params+="&isTeam=" + isTeam;
  params+="&isOrganization=" + isOrganization;
  params+="&mode=add";
  loadDialog('dialogAffectation', callBack, false, params);
}

function addResourceCapacity(objectClass, type, idResource) {
  var callBack=function() {
    affectationLoad=true;
    dijit.byId("dialogResourceCapacity").show();
    setTimeout("affectationLoad=false", 500);
  };
  var params="&idResource=" + idResource;
  params+="&type=" + type;
  params+="&mode=add";
  loadDialog('dialogResourceCapacity', callBack, false, params);
}

function saveResourceCapacity(capacity) {
  var formVar=dijit.byId('resourceCapacityForm');
  if (dijit.byId('resourceCapacityStartDate')
      && dijit.byId('resourceCapacityEndDate')) {
    var start=dijit.byId('resourceCapacityStartDate').value;
    var end=dijit.byId('resourceCapacityEndDate').value;
    if (start && end && dayDiffDates(start, end) < 0) {
      showAlert(i18n("errorStartEndDates", new Array(i18n("colStartDate"),
          i18n("colEndDate"))));
      return;
    }
  }
  if (dijit.byId('resourceCapacity')) {
    var newCapacity=dijit.byId('resourceCapacity').value;
    if (capacity === newCapacity) {
      showAlert(i18n("changeCapacity"));
      return;
    }
  }

  if (formVar.validate()) {
    loadContent("../tool/saveResourceCapacity.php", "resultDivMain",
        "resourceCapacityForm", true, 'affectation');
    dijit.byId('dialogResourceCapacity').hide();
  } else {
    showAlert(i18n("alertInvalidForm"));
  }
}

function removeResourceCapacity(id, idResource) {
  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
  actionOK=function() {
    loadContent("../tool/removeResourceCapacity.php?idResourceCapacity=" + id
        + "&idResource=" + idResource, "resultDivMain", null, true,
        'affectation');
  };
  msg=i18n('confirmDeleteResourceCapacity', new Array(id, i18n('Resource'),
      idResource));
  showConfirm(msg, actionOK);
}

function editResourceCapacity(id, idResource, capacity, idle, startDate,
    endDate) {
  affectationLoad=true;
  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
  var callBack=function() {
    dojo
        .xhrGet({
          url : '../tool/getSingleData.php?dataType=resourceCapacityDescription&idResourceCapacity='
              + id+addTokenIndexToUrl(),
          handleAs : "text",
          load : function(data) {
            dijit.byId('resourceCapacityDescription').set('value', data);
            enableWidget("resourceCapacityDescription");
          }
        });
    if (capacity) {
      dijit.byId("resourceCapacity").set('value', parseFloat(capacity));
    }
    if (startDate) {
      dijit.byId("resourceCapacityStartDate").set('value', startDate);
    } else {
      dijit.byId("resourceCapacityStartDate").reset();
    }
    if (endDate) {
      dijit.byId("resourceCapacityEndDate").set('value', endDate);
    } else {
      dijit.byId("resourceCapacityEndDate").reset();
    }
    if (idle == 1) {
      dijit.byId("resourceCapacityIdle").set('value', idle);
    } else {
      dijit.byId("resourceCapacityIdle").reset();
    }
    dijit.byId("dialogResourceCapacity").show();
    setTimeout("affectationLoad=false", 500);
  };
  var params="&id=" + id;
  params+="&idResource=" + idResource;
  params+="&mode=edit";
  loadDialog('dialogResourceCapacity', callBack, false, params);
}

// end workUnit

// gautier resourceSurbooking
function addResourceSurbooking(objectClass, type, idResource) {
  var callBack=function() {
    affectationLoad=true;
    dijit.byId("dialogResourceSurbooking").show();
    setTimeout("affectationLoad=false", 500);
  };
  var params="&idResource=" + idResource;
  params+="&type=" + type;
  params+="&mode=add";
  loadDialog('dialogResourceSurbooking', callBack, false, params);
}

function saveResourceSurbooking(capacity) {
  var formVar=dijit.byId('resourceSurbookingForm');
  if (dijit.byId('resourceSurbookingStartDate')
      && dijit.byId('resourceSurbookingEndDate')) {
    var start=dijit.byId('resourceSurbookingStartDate').value;
    var end=dijit.byId('resourceSurbookingEndDate').value;
    if (start && end && dayDiffDates(start, end) < 0) {
      showAlert(i18n("errorStartEndDates", new Array(i18n("colStartDate"),
          i18n("colEndDate"))));
      return;
    }
  }
  if (dijit.byId('resourceSurbooking')) {
    var newCapacity=dijit.byId('resourceSurbooking').value;
    if (newCapacity === 0) {
      showAlert(i18n("changeSurbooking"));
      return;
    }
  }
  if (formVar.validate()) {
    loadContent("../tool/saveResourceSurbooking.php", "resultDivMain",
        "resourceSurbookingForm", true, 'affectation');
    dijit.byId('dialogResourceSurbooking').hide();
  } else {
    showAlert(i18n("alertInvalidForm"));
  }
}

function removeResourceSurbooking(id, idResource) {
  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
  actionOK=function() {
    loadContent("../tool/removeResourceSurbooking.php?idResourceSurbooking="
        + id + "&idResource=" + idResource, "resultDivMain", null, true,
        'affectation');
  };
  msg=i18n('confirmDeleteResourceSurbooking', new Array(id, i18n('Resource'),
      idResource));
  showConfirm(msg, actionOK);
}

function editResourceSurbooking(id, idResource, capacity, idle, startDate,
    endDate) {
  affectationLoad=true;
  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
  var callBack=function() {
    dojo
        .xhrGet({
          url : '../tool/getSingleData.php?dataType=resourceSurbookingDescription&idResourceSurbooking='
              + id+addTokenIndexToUrl(),
          handleAs : "text",
          load : function(data) {
            dijit.byId('resourceSurbookingDescription').set('value', data);
            enableWidget("resourceSurbookingDescription");
          }
        });
    if (capacity) {
      dijit.byId("resourceSurbooking").set('value', parseFloat(capacity));
    }
    if (startDate) {
      dijit.byId("resourceSurbookingStartDate").set('value', startDate);
    } else {
      dijit.byId("resourceSurbookingStartDate").reset();
    }
    if (endDate) {
      dijit.byId("resourceSurbookingEndDate").set('value', endDate);
    } else {
      dijit.byId("resourceSurbookingEndDate").reset();
    }
    if (idle == 1) {
      dijit.byId("resourceSurbookingIdle").set('value', idle);
    } else {
      dijit.byId("resourceSurbookingIdle").reset();
    }
    dijit.byId("dialogResourceSurbooking").show();
    setTimeout("affectationLoad=false", 500);
  };
  var params="&id=" + id;
  params+="&idResource=" + idResource;
  params+="&mode=edit";
  loadDialog('dialogResourceSurbooking', callBack, false, params);
}

// gautier #resourceTeam
function addAffectationResourceTeam(objectClass, type, idResource) {
  var callBack=function() {
    affectationLoad=true;
    dijit.byId("dialogAffectationResourceTeam").show();
    setTimeout("affectationLoad=false", 500);
  };
  var params="&idResource=" + idResource;
  params+="&type=" + type;
  params+="&mode=add";
  loadDialog('dialogAffectationResourceTeam', callBack, false, params);
}

function removeAffectation(id, own, affectedClass, affectedId) {
  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
  actionOK=function() {
    var callback = function(){
      if(dijit.byId('dialogEditAffectationPlanning') && dijit.byId('dialogEditAffectationPlanning').open){
        var objClass=dojo.byId('affectationObjectClass').value;
        var objId = dojo.byId("affectationObjectId").value;
        var params="&objectClass=" + objClass + "&objectId=" + objId;
        loadDialog('dialogEditAffectationPlanning', null, true, params);
      }
    };
    loadContent("../tool/removeAffectation.php?affectationId=" + id
        + "&affectationIdTeam=''", "resultDivMain", null, true, 'affectation', null, null, callback);
  };
  if (own) {
    msg='<span style="color:red;font-weight:bold;">'
        + i18n('confirmDeleteOwnAffectation', new Array(id)) + '</span>';
  } else {
    msg=i18n('confirmDeleteAffectation', new Array(id, i18n(affectedClass),
        affectedId));
  }
  showConfirm(msg, actionOK);
}

function removeAffectationResourceTeam(id, idResource) {
  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
  actionOK=function() {
    var callback = function(){
      if(dijit.byId('dialogEditAffectationPlanning') && dijit.byId('dialogEditAffectationPlanning').open){
        var objClass=dojo.byId('affectationObjectClass').value;
        var objId = dojo.byId("affectationObjectId").value;
        var params="&objectClass=" + objClass + "&objectId=" + objId;
        loadDialog('dialogEditAffectationPlanning', null, true, params);
      }
    };
    loadContent("../tool/removeAffectationResourceTeam.php?affectaionId=" + id,
        "resultDivMain", null, true, 'affectation', null, null, callback);
  };
  msg=i18n('confirmDeleteAffectation', new Array(id, i18n('Resource'),
      idResource));
  showConfirm(msg, actionOK);
}

affectationLoad=false;
function editAffectationResourceTeam(id, objectClass, type, idResource, rate,
    idle, startDate, endDate) {
  affectationLoad=true;
  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
  var callBack=function() {
    dojo
        .xhrGet({
          url : '../tool/getSingleData.php?dataType=affectationDescriptionResourceTeam&idAffectation='
              + id+addTokenIndexToUrl(),
          handleAs : "text",
          load : function(data) {
            dijit.byId('affectationDescriptionResourceTeam').set('value', data);
            enableWidget("affectationDescriptionResourceTeam");
          }
        });
    if (idResource) {
      dijit.byId("affectationResourceTeam").set('value', idResource);
    }
    if (rate) {
      dijit.byId("affectationRateResourceTeam").set('value', rate);
    }
    if (startDate) {
      dijit.byId("affectationStartDateResourceTeam").set('value', startDate);
    } else {
      dijit.byId("affectationStartDateResourceTeam").reset();
    }
    if (endDate) {
      dijit.byId("affectationEndDateResourceTeam").set('value', endDate);
    } else {
      dijit.byId("affectationEndDateResourceTeam").reset();
    }
    if (idle == 1) {
      dijit.byId("affectationIdleResourceTeam").set('value', idle);
    } else {
      dijit.byId("affectationIdleResourceTeam").reset();
    }
    dijit.byId("dialogAffectationResourceTeam").show();
    setTimeout("affectationLoad=false", 500);
  };
  var objClass=null;
  if(dijit.byId('dialogEditAffectationPlanning') && dijit.byId('dialogEditAffectationPlanning').open){
    objClass=dojo.byId('affectationObjectClass').value;
  }else{
    objClass=dojo.byId('objectClass').value;
  }
  var params="&id=" + id;
  params+="&refType=" + objClass;
  params+="&idResource=" + idResource;
  params+="&mode=edit";
  params+="&type=" + type;
  params+="&objectClass=" + objectClass;
  loadDialog('dialogAffectationResourceTeam', callBack, false, params);
}

function editAffectation(id, objectClass, type, idResource, idProject, rate,
    idle, startDate, endDate, idProfile, isResourceTeam) {
  affectationLoad=true;
  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
  var callBack=function() {
    dojo
        .xhrGet({
          url : '../tool/getSingleData.php?dataType=affectationDescription&idAffectation='
              + id+addTokenIndexToUrl(),
          handleAs : "text",
          load : function(data) {
            dijit.byId('affectationDescription').set('value', data);
            enableWidget("affectationDescription");
          }
        });
    if (startDate) {
      dijit.byId("affectationStartDate").set('value', startDate);
    } else {
      dijit.byId("affectationStartDate").reset();
    }
    if (endDate) {
      dijit.byId("affectationEndDate").set('value', endDate);
    } else {
      dijit.byId("affectationEndDate").reset();
    }
    if(isResourceTeam == null) {
      var aff = dijit.byId("affectationProfile");
      aff.required = false;
      require(["dojo/query", "dojo/NodeList-dom"], function(query){
        query("#widget_affectationProfile ").removeClass("required");
      });
    }
    if (idle == 1) {
      dijit.byId("affectationIdle").set('value', idle);
    } else {
      dijit.byId("affectationIdle").reset();
    }
    dijit.byId("dialogAffectation").show();
    setTimeout("affectationLoad=false", 500);
  };
  var objClass=null;
  if(dijit.byId('dialogEditAffectationPlanning') && dijit.byId('dialogEditAffectationPlanning').open){
    objClass=dojo.byId('affectationObjectClass').value;
  }else{
    objClass=dojo.byId('objectClass').value;
  }
  var params="&id=" + id;
  params+="&refType=" + objClass;
  params+="&idProject=" + idProject;
  params+="&idResource=" + idResource;
  params+="&mode=edit";
  params+="&type=" + type;
  params+="&objectClass=" + objectClass;
  loadDialog('dialogAffectation', callBack, false, params);
}

function saveAffectation(notResourceSkillSimple) {
  if (notResourceSkillSimple==undefined) notResourceSkillSimple = true;
  var formVar=dijit.byId('affectationForm');
  if (dijit.byId('affectationStartDate') && dijit.byId('affectationEndDate')) {
    var start=dijit.byId('affectationStartDate').value;
    var end=dijit.byId('affectationEndDate').value;
    if (start && end && dayDiffDates(start, end) < 0) {
      showAlert(i18n("errorStartEndDates", new Array(i18n("colStartDate"),
          i18n("colEndDate"))));
      return;
    }
  }
  if (affectationMultiCapable) {
    console.log("affectationMultiCapable");
    console.log(affectationResourceIds);
    if (affectationResourceIds.length === 0) {
      showAlert(i18n("alertInvalidForm"));
      return;
    }
    dijit.byId('affectationResource').set('required', false);
  }
  
  if (formVar.validate()) {
	var callback=function(){
		resetAffectationResourceChips();
		var isResourceSkill = dojo.byId('isResourceSkill').value;
		if(isResourceSkill){
			hideWait();
			refreshResourceSkillList(notResourceSkillSimple);
		}
		if(dijit.byId('dialogEditAffectationPlanning') && dijit.byId('dialogEditAffectationPlanning').open){
      var objClass=dojo.byId('affectationObjectClass').value;
      var objId = dojo.byId("affectationObjectId").value;
      var params="&objectClass=" + objClass + "&objectId=" + objId;
      loadDialog('dialogEditAffectationPlanning', null, true, params);
    }
	};
    loadContent("../tool/saveAffectation.php", "resultDivMain",
        "affectationForm", true, 'affectation', null, null, callback);
    dijit.byId('dialogAffectation').hide();
  } else {
    showAlert(i18n("alertInvalidForm"));
  }
}

var affectationMultiCapable = false;
var affectationResourceIds = [];

function affectationResourceOnChange() {
  var widget = dijit.byId('affectationResource');
  var id = widget.get('value');
  if (id === null || id === undefined || id === '' || id === ' ') return;

  var label = widget.get('displayedValue');
  if (!label || !dojo.trim(label)) return;

  var already = dojo.some(affectationResourceIds, function(r){ return r.id == id; });
  if (!already) {
    affectationResourceIds.push({id: id, label: label});
    renderAffectationResourceChips();
  }

  widget.set('value', null, false);
  widget.set('displayedValue', '');
  affectationChangeResource();
}

function renderAffectationResourceChips() {
  var container = dojo.byId('affectationResourceChips');
  if (!container) return;
  dojo.empty(container);
  dojo.forEach(affectationResourceIds, function(res, idx) {
    var chip = dojo.create('span', {'class': 'affectationResourceChip'}, container);
    dojo.create('span', {'class': 'affectationResourceChipLabel', innerHTML: res.label}, chip);
    var close = dojo.create('span', {
      'class': 'affectationResourceChipClose',
      innerHTML: '&times;',
      title: i18n('buttonErase')
    }, chip);
    dojo.connect(close, 'onclick', function() {
      affectationResourceIds.splice(idx, 1);
      renderAffectationResourceChips();
    });
  });

  dojo.byId('affectationResourceList').value =
    dojo.map(affectationResourceIds, function(r){ return r.id; }).join(';');

  affectationUpdateProfileRequirement();
}

function affectationUpdateProfileRequirement() {
  var profileWidget = dijit.byId('affectationProfile');
  if (!profileWidget) return;
  var multiple = affectationResourceIds.length > 1;
  profileWidget.set('required', !multiple);
}

function resetAffectationResourceChips() {
  affectationResourceIds = [];
  var container = dojo.byId('affectationResourceChips');
  if (container) dojo.empty(container);
  if (container) container.innerHTML=i18n('selectRes');
  affectationMultiCapable=(container)?true:false; 
  var hidden = dojo.byId('affectationResourceList');
  if (hidden) hidden.value = '';
  affectationUpdateProfileRequirement();
}

function saveAffectationResourceTeam() {
  var formVar=dijit.byId('affectationResourceTeamForm');
  if (dijit.byId('affectationStartDate') && dijit.byId('affectationEndDate')) {
    var start=dijit.byId('affectationStartDate').value;
    var end=dijit.byId('affectationEndDate').value;
    if (start && end && dayDiffDates(start, end) < 0) {
      showAlert(i18n("errorStartEndDates", new Array(i18n("colStartDate"),
          i18n("colEndDate"))));
      return;
    }
  }
  if (trim(dijit.byId('affectationResourceTeam')) == '') {
    showAlert(i18n("messageMandatory", new Array(i18n("colIdResource"))));
    return;
  }
  if (formVar.validate()) {
    var callback=function(){
      if(dijit.byId('dialogEditAffectationPlanning') && dijit.byId('dialogEditAffectationPlanning').open){
        var objClass=dojo.byId('affectationObjectClass').value;
        var objId = dojo.byId("affectationObjectId").value;
        var params="&objectClass=" + objClass + "&objectId=" + objId;
        loadDialog('dialogEditAffectationPlanning', null, true, params);
      }
    };
    loadContent("../tool/saveAffectationResourceTeam.php", "resultDivMain",
        "affectationResourceTeamForm", true, 'affectation', null, null, callback);
    dijit.byId('dialogAffectationResourceTeam').hide();
  } else {
    showAlert(i18n("alertInvalidForm"));
  }
}

function affectTeamMembers(idTeam) {
  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
  var callBack=function() {
    dijit.byId("dialogAffectation").show();
  };
  var params="&affectationIdTeam=" + idTeam;
  loadDialog('dialogAffectation', callBack, false, params);
}

function affectOrganizationMembers(idOrganization) {
  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
  var callBack=function() {
    dijit.byId("dialogAffectation").show();
  };
  var params="&affectationIdOrganization=" + idOrganization;
  loadDialog('dialogAffectation', callBack, false, params);
}

function affectationChangeResource() {
  var idResource=dijit.byId("affectationResource").get("value");
  if (!idResource)
    return;
  if (affectationLoad)
    return;
  res = dojo.xhrGet({
    url : '../tool/getSingleData.php?dataType=resourceProfile&idResource='
        + idResource+addTokenIndexToUrl(),
    handleAs : "text",
    load : function(data) {
      dijit.byId('affectationProfile').set('value', data);
    }
  });
  
 res.then(
      function(data){
        var aff = dijit.byId("affectationProfile");
        if(data=='') {
          aff.required = false;
          require(["dojo/query", "dojo/NodeList-dom"], function(query){
            query("#widget_affectationProfile ").removeClass("required");
          });

        } else {
          aff.required = true;
          require(["dojo/query", "dojo/NodeList-dom"], function(query){
            query("#widget_affectationProfile ").addClass("required");
          });
        }
    }
  );
}

function replaceAffectation(id, objectClass, type, idResource, idProject, rate,
    idle, startDate, endDate, idProfile) {
  var callback=function() {
    refreshList('idProfile', 'idProject', idProject, null,
        'replaceAffectationProfile', false);
  };
  var param="&idAffectation=" + id;
  loadDialog("dialogReplaceAffectation", callback, true, param);
}

function replaceAffectationSave() {
  var formVar=dijit.byId('replaceAffectationForm');
  if (dijit.byId('replaceAffectationStartDate')
      && dijit.byId('replaceAffectationEndDate')) {
    var start=dijit.byId('replaceAffectationStartDate').value;
    var end=dijit.byId('replaceAffectationEndDate').value;
    if (start && end && dayDiffDates(start, end) < 0) {
      showAlert(i18n("errorStartEndDates", new Array(i18n("colStartDate"),i18n("colEndDate"))));
      return;
    }
  }
  if (dijit.byId('replaceAffectationResource').get("value") == dojo
      .byId("replaceAffectationExistingResource").value) {
    showAlert(i18n("errorReplaceResourceNotChanged"));
    return;
  }
  if (formVar.validate()) {
    var callback=function(){
      if(dijit.byId('dialogEditAffectationPlanning')){
        var objClass=dojo.byId('affectationObjectClass').value;
        var objId = dojo.byId("affectationObjectId").value;
        var params="&objectClass=" + objClass + "&objectId=" + objId;
        loadDialog('dialogEditAffectationPlanning', null, true, params);
      }
    };
    loadContent("../tool/saveAffectationReplacement.php", "resultDivMain",
        "replaceAffectationForm", true, 'affectation', null, null, callback);
    dijit.byId('dialogReplaceAffectation').hide();
  } else {
    showAlert(i18n("alertInvalidForm"));
  }
}

function replaceAffectationChangeResource() {
  var idResource=dijit.byId("replaceAffectationResource").get("value");
  if (!idResource)
    return;
  dojo.xhrGet({
    url : '../tool/getSingleData.php?dataType=resourceProfile&idResource='
        + idResource+addTokenIndexToUrl(),
    handleAs : "text",
    load : function(data) {
      dijit.byId('replaceAffectationProfile').set('value', data);
    }
  });
  dojo.xhrGet({
    url : '../tool/getSingleData.php?dataType=resourceCapacity&idResource='
        + idResource+addTokenIndexToUrl(),
    handleAs : "text",
    load : function(data) {
      dijit.byId('replaceAffectationCapacity').set('value', parseFloat(data));
    }
  });
  dojo.xhrGet({
    url : '../tool/getSingleData.php?dataType=isResourceTeam&idResource='
        + idResource+addTokenIndexToUrl(),
    handleAs : "text",
    load : function(data) {
      if(data==0) {
        dijit.byId('replaceAffectationProfile').required = true;
        require(["dojo/dom-class"], function(domClass){
          domClass.add("widget_replaceAffectationProfile", "required");
        });
      } else {
        dijit.byId('replaceAffectationProfile').required = false;
        require(["dojo/dom-class"], function(domClass){
          domClass.remove("widget_replaceAffectationProfile", "required");
        });
      }
    }
  });
}

function addResourceIncompatible(idResource) {
  var callBack=function() {
    dijit.byId("dialogResourceIncompatible").show();
  };
  var params="&idResource=" + idResource;
  loadDialog('dialogResourceIncompatible', callBack, false, params);
}

function saveResourceIncompatible() {
  var formVar=dijit.byId('resourceIncompatibleForm');
  if (formVar.validate()) {
    loadContent("../tool/saveResourceIncompatible.php", "resultDivMain",
        "resourceIncompatibleForm", true, 'affectation');
    dijit.byId('dialogResourceIncompatible').hide();
  } else {
    showAlert(i18n("alertInvalidForm"));
  }
}

function removeResourceIncompatible(id) {
  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
  actionOK=function() {
    loadContent("../tool/saveResourceIncompatible.php?idIncompatible=" + id,
        "resultDivMain", null, true, 'affectation');
  };
  msg=i18n('confirmDeleteResourceIncompatible', new Array(id, i18n('Resource')));
  showConfirm(msg, actionOK);
}

function addResourceSupport(idResource) {
  var callBack=function() {
    dijit.byId("dialogResourceSupport").show();
  };
  var params="&idResource=" + idResource;
  loadDialog('dialogResourceSupport', callBack, false, params);
}

function saveResourceSupport(mode) {
  var formVar=dijit.byId('resourceSupportForm');
  if (formVar.validate()) {
    loadContent("../tool/saveResourceSupport.php?mode=" + mode,
        "resultDivMain", "resourceSupportForm", true, 'affectation');
    dijit.byId('dialogResourceSupport').hide();
  } else {
    showAlert(i18n("alertInvalidForm"));
  }
}

function editResourceSupport(id) {
  var callBack=function() {
    dijit.byId("dialogResourceSupport").show();
  };
  var params="&idSupport=" + id;
  loadDialog('dialogResourceSupport', callBack, false, params);
}

function removeResourceSupport(id) {
  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
  actionOK=function() {
    loadContent("../tool/saveResourceSupport.php?idSupport=" + id,
        "resultDivMain", null, true, 'affectation');
  };
  msg=i18n('confirmDeleteResourceSupport', new Array(id, i18n('Resource')));
  showConfirm(msg, actionOK);
}

function assignTeamForMeeting() {
  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
  actionOK=function() {
    loadContent("../tool/assignTeamForMeeting.php?assignmentId=&assignmentRefType="+dojo.byId('objectClass').value+"&assignmentRefId="+dojo.byId("objectId").value,"resultDivMain", null,
        true, 'assignment');
  };
  msg=i18n('confirmAssignWholeTeam');
  showConfirm(msg, actionOK);
  
}

function commentImputationSubmit(year,week,idAssignment,refType,refId){
  var text=dijit.byId('commentImputation').get('value');
  if(text.trim()==''){
    showAlert(i18n('messageMandatory',[i18n('colComment')]));
    return;
  }
  showWait();
  dojo.xhrPost({
    url : "../tool/dynamicDialogCommentImputation.php?year="+year+"&week="+week+"&idAssignment="+idAssignment+"&refTypeComment="+refType+"&refIdComment="+refId+addTokenIndexToUrl(),
    handleAs : "text",
    form : 'commentImputationForm',
    load : function(data, args) {
      if (data.indexOf('<input type="hidden" id="lastOperationStatus"')>-1) {
        showAlert(data);
        hideWait();
        return;
      }
      formChangeInProgress=false;
      document.getElementById("showBig"+idAssignment).style.display='block'; 
      dojo.byId("showBig"+idAssignment).childNodes[0].onmouseover=function(){
        showBigImage(null,null,this,data);
      };
      dijit.byId('dialogCommentImputation').hide();
      hideWait();
    },
    error : function() {
      hideWait();
    }
  });
}

function commentImputationTitlePopup(type){
  title='';
  if(type=='add'){
    title= i18n('commentImputationAdd');
  }else if(type=='view'){
    title= i18n('commentImputationView');
  }
  dijit.byId('dialogCommentImputation').set('title',title);
}

function runScript(refType, refId, id) {
  if (g) {  
    var vList=g.getList();
    if (vList) {
      var vTask=null;
      for(var i = 0; i < vList.length; i++) {
        if (vList[i].getID()==id) {
          vTask=vList[i];
          break;
        }
      }
      if (vTask && dojo.byId('resourcePlanningSelectedResource')) {
        dojo.byId('resourcePlanningSelectedResource').value=vTask.getResource();
      }
      if(vTask){
        var idProject = vTask.getProjectId();
        JSGantt.closeEditRowObjectPlanning();
        cachedEditRowPlanningClick = 'JSGantt.planningRowClickAction(\''+id+'\', '+refId+', \''+refType+'\', '+idProject+')';
        JSGantt.editRowObjectPlanning(id, refId, refType, idProject);
        if((planningClickAction != 1)){
          var buttonDetail = dojo.byId('buttonEditRowDetail');
          if(buttonDetail){
            dojo.removeClass(buttonDetail, 'iconButtonView16 iconButtonView');
            dojo.addClass(buttonDetail, 'iconButtonNoView16 iconButtonNoView');
            dojo.setAttr(buttonDetail, 'onclick', 'hideDetailScreen();JSGantt.closeAndSelectEditRow(\''+id+'\', '+refId+', \''+refType+'\', '+idProject+')');
            dojo.setAttr(buttonDetail, 'title', i18n('colHideDetail'));
          }
        }
      }
    }
  }
  if(dojo.byId('paramLayoutScreen') && dojo.byId('paramLayoutScreen').value != 'multiple')return;
  if (refType == 'Fixed' || refType=='Construction' || refType=='Replan') {
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
  if(refType=='SupplierContracthasChild'){
    refType = 'SupplierContract';
  }
  if(refType=='ClientContracthasChild'){
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
  var ctrlPressed=(window.event && (window.event.ctrlKey || window.event.shiftKey))?true:false;
  if (ctrlPressed && refType && refId) {
    openInNewWindow(refType, refId);
    return;
  }
  hideList();
  var callBack = function(){
    if(dojo.byId('workPlanJsonData') && dojo.byId('planningJsonData')){
      setActionCoverListNonObj('OPEN',false);
    }
  }
  var planninType = (dojo.byId("objectClassManual").value == 'PlanningWorkPlan' )?'Planning':dojo.byId("objectClassManual").value;
  loadContent('objectDetail.php?planning=true&planningType='+planningType, 'detailDiv', 'listForm', false,null,null,null,callBack);
  loadContentStream();
  highlightPlanningLine(id);
}
// PBER : REMOVED THIS FUNCTION ALREADY EXISTING IN projeqtorPlanning.js
//var ongoingRunScriptContextMenu=false;
//var timeoutContextMenuWait = null;
//function runScriptContextMenu(refType, refId, id) {
//  if (ongoingRunScriptContextMenu) return;
//  ongoingRunScriptContextMenu = true;
//  const clickPos = event ? { clientX: event.clientX, clientY: event.clientY } : null;
//  var objectClassManual = dojo.byId('objectClassManual').value;
//  if (objectClassManual == 'PlanningWorkPlan') objectClassManual = 'Planning';
//  timeoutContextMenuWait = setTimeout('showWait()', 50);
//  setTimeout("document.body.style.cursor='default';", 100);
//  dojo.xhrGet({
//    url: "../view/planningBarDetail.php?class=" + refType + "&id=" + refId + "&scale=" + ganttPlanningScale + "&objectClassManual=" + objectClassManual + "&idAssignment=" + id + addTokenIndexToUrl(),
//    load: function(data, args) {
//      // ongoingRunScriptContextMenu=true;
//      hideWait();
//      if (timeoutContextMenuWait) clearTimeout(timeoutContextMenuWait);
//      setTimeout("document.body.style.cursor='default';", 100);
//      var bar = dojo.byId('bardiv_' + id);
//      var line = dojo.byId('childgrid_' + id);
//      var detail = dojo.byId('rightTableBarDetail');
//      if (detail.style.display == 'block') {
//        var pObjectClass = dojo.byId('planningBarDetailObjectClass').value;
//        var pObjectId = dojo.byId('planningBarDetailObjectId').value;
//        if (pObjectClass == refType && pObjectId == refId) {
//          detail.style.display = 'none';
//        } else {
//          detail.style.display = "block";
//        }
//      } else {
//        detail.style.display = "block";
//      }
//      detail.innerHTML = data;
//      detail.style.width = (parseInt(bar.style.width) + 202) + 'px';
//      detail.style.left = (bar.offsetLeft - 1) + "px";
//      var task = g.getLineByID(id);
//      var isChanged = task.getChanged();
//      if (isChanged || dojo.byId('noDataToDisplay')) {
//        detail.innerHTML = detailInnerHTML;
//        detail.style.display = 'none';
//        var idProject = g.getItemIdProjectByRef(refType, refId);
//        bar.oncontextmenu = function(e) {
//          e.preventDefault();
//          return JSGantt.openPlanningContextMenu(id, refId, refType, idProject);
//        };
//        ongoingRunScriptContextMenu = false;
//        const rect = bar.getBoundingClientRect();
//        const x = (clickPos && clickPos.clientX) || (rect.left + 5);
//        const y = (clickPos && clickPos.clientY) || (rect.top + 5);
//        const newEvt = new MouseEvent('contextmenu', {
//          bubbles: true,
//          cancelable: true,
//          view: window,
//          clientX: x,
//          clientY: y
//        });
//        bar.dispatchEvent(newEvt);
//        hideWait();
//        return;
//      }
//
//      var tableHeight = 44;
//      if (dojo.byId('planningBarDetailTable')) tableHeight = dojo.byId('planningBarDetailTable').offsetHeight
//      if (dojo.byId('rightTableContainer').offsetHeight + tableHeight > (dojo.byId('rightGanttChartDIV').offsetHeight) && (line.offsetTop + 25) > dojo.byId('rightTableContainer').offsetHeight) {
//        detail.style.top = (line.offsetTop - tableHeight + 1) + "px";
//      } else {
//        detail.style.top = (line.offsetTop + 22) + "px";
//      }
//      var positions = elementPosition(bar);
//      var detailDiv = document.getElementById('detailDiv').clientWidth;
//      var leftGanttChartDIV = document.getElementById('leftGanttChartDIV').clientWidth;
//      if (detailDiv >= leftGanttChartDIV + document.getElementById('rightGanttChartDIV').clientWidth) detailDiv = 0;
//      var diffSizeLeft = document.documentElement.clientWidth - document.getElementById('rightGanttChartDIV').clientWidth - detailDiv;
//      var posLeft = (diffSizeLeft - (positions.viewportXLeft));
//      var diffSizeRight = document.documentElement.clientWidth - detailDiv;
//      var posRight = posLeft + document.getElementById('rightGanttChartDIV').clientWidth - 100;
//      var halfSize = (parseInt(detail.style.width) / 2);
//      dojo.query(".planningBarDetailResName").forEach(function(node, index, nodelist) {
//        if (positions.viewportXRight > halfSize && positions.viewportXRight > (diffSizeRight - 50) && posRight > -50) {
//          node.style.left = (posRight) + "px";
//        } else if (positions.viewportXRight < halfSize && positions.viewportXRight > (diffSizeRight - 50) && posRight > -50) {
//          node.style.left = (posRight) + "px";
//        } else if (positions.viewportXRight < halfSize && positions.viewportXRight < (diffSizeRight - 50) && posRight > -50) {
//          node.style.left = "unset";
//        } else if (positions.viewportXRight > halfSize && positions.viewportXRight < (diffSizeRight - 50) && posRight > -50) {
//          node.style.left = "unset";
//        }
//      });
//      if (dojo.byId('planningBarDetailCloseButton')) {
//        if (positions.viewportXRight > halfSize && (positions.viewportXRight + 150) > (diffSizeRight - 50) && posRight > -50) {
//          dojo.byId('planningBarDetailCloseButton').style.left = (posRight + 63) + "px";
//        } else if (positions.viewportXRight < halfSize && (positions.viewportXRight + 150) > (diffSizeRight - 50) && posRight > -50) {
//          dojo.byId('planningBarDetailCloseButton').style.left = (posRight + 63) + "px";
//        } else if (positions.viewportXRight < halfSize && (positions.viewportXRight + 150) < (diffSizeRight - 50) && posRight > -50) {
//          dojo.byId('planningBarDetailCloseButton').style.left = "unset";
//        } else if (positions.viewportXRight > halfSize && (positions.viewportXRight + 150) < (diffSizeRight - 50) && posRight > -50) {
//          dojo.byId('planningBarDetailCloseButton').style.left = "unset";
//        }
//      }
//      document.getElementById('rightGanttChartDIV').addEventListener('scroll', () => {
//        var positions = elementPosition(bar);
//        var detailDiv = document.getElementById('detailDiv').clientWidth;
//        var leftGanttChartDIV = document.getElementById('leftGanttChartDIV').clientWidth;
//        if (detailDiv >= leftGanttChartDIV + document.getElementById('rightGanttChartDIV').clientWidth) detailDiv = 0;
//        var diffSizeLeft = document.documentElement.clientWidth - document.getElementById('rightGanttChartDIV').clientWidth - detailDiv;
//        var posLeft = (diffSizeLeft - (positions.viewportXLeft));
//        var diffSizeRight = document.documentElement.clientWidth - detailDiv;
//        var posRight = posLeft + document.getElementById('rightGanttChartDIV').clientWidth - 100;
//        var halfSize = (parseInt(detail.style.width) / 2);
//        dojo.query(".planningBarDetailResName").forEach(function(node, index, nodelist) {
//          if (positions.viewportXRight > halfSize && positions.viewportXRight > (diffSizeRight - 50) && posRight > -50) {
//            node.style.left = (posRight) + "px";
//          } else if (positions.viewportXRight < halfSize && positions.viewportXRight > (diffSizeRight - 50) && posRight > -50) {
//            node.style.left = (posRight) + "px";
//          } else if (positions.viewportXRight < halfSize && positions.viewportXRight < (diffSizeRight - 50) && posRight > -50) {
//            node.style.left = "unset";
//          } else if (positions.viewportXRight > halfSize && positions.viewportXRight < (diffSizeRight - 50) && posRight > -50) {
//            node.style.left = "unset";
//          }
//        });
//        if (dojo.byId('planningBarDetailCloseButton')) {
//          if (positions.viewportXRight > halfSize && (positions.viewportXRight + 150) > (diffSizeRight - 50) && posRight > -50) {
//            dojo.byId('planningBarDetailCloseButton').style.left = (posRight + 63) + "px";
//          } else if (positions.viewportXRight < halfSize && (positions.viewportXRight + 150) > (diffSizeRight - 50) && posRight > -50) {
//            dojo.byId('planningBarDetailCloseButton').style.left = (posRight + 63) + "px";
//          } else if (positions.viewportXRight < halfSize && (positions.viewportXRight + 150) < (diffSizeRight - 50) && posRight > -50) {
//            dojo.byId('planningBarDetailCloseButton').style.left = "unset";
//          } else if (positions.viewportXRight > halfSize && (positions.viewportXRight + 150) < (diffSizeRight - 50) && posRight > -50) {
//            dojo.byId('planningBarDetailCloseButton').style.left = "unset";
//          }
//        }
//      });
//      setTimeout("ongoingRunScriptContextMenu=false;", 20);
//      hideWait();
//    },
//    error: function() {
//      console.warn("error on return from planningBarDetail.php");
//      if (timeoutContextMenuWait) clearTimeout(timeoutContextMenuWait);
//      hideWait();
//      setTimeout("ongoingRunScriptContextMenu=false;", 20);
//    }
//  });
//  return false;
//}
