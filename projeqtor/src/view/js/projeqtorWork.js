/*******************************************************************************
 * COPYRIGHT NOTICE *
 * 
 * Copyright 2009-2017 ProjeQtOr - Pascal BERNARD - support@projeqtor.org
 * Contributors : -
 * 
 * This file is part of ProjeQtOr.
 * 
 * ProjeQtOr is free software: you can redistribute it and/or modify it under
 * the terms of the GNU Affero General Public License as published by the Free
 * Software Foundation, either version 3 of the License, or (at your option) any
 * later version.
 * 
 * ProjeQtOr is distributed in the hope that it will be useful, but WITHOUT ANY
 * WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
 * A PARTICULAR PURPOSE. See the GNU Affero General Public License for more
 * details.
 * 
 * You should have received a copy of the GNU Affero General Public License
 * along with ProjeQtOr. If not, see <http://www.gnu.org/licenses/>.
 * 
 * You can get complete code of ProjeQtOr, other resource, help and information
 * about contributors at http://www.projeqtor.org
 * 
 * DO NOT REMOVE THIS NOTICE **
 ******************************************************************************/

// ============================================================================
// All specific ProjeQtOr functions for work management
// This file is included in the main.php page, to be reachable in every context
// ============================================================================
function collapseExpandAll(tab,resourceId,action) {
  var line=1;
  for ( var key in tab) {
    if (tab.hasOwnProperty(key) && !tab[key]['elementary']) {
      var scope='Imputation_' + resourceId + '_' + tab[key]['refType'] + '_' + tab[key]['refId'];
      workOpenCloseLine(line,scope,action);
    }
    line++;
  }

}

/**
 * Open / Close Group : hide sub-lines
 */
function workOpenCloseLine(line,scope,action) {
  var nbLines=dojo.byId('nbLines').value;
  var wbsLine=dojo.byId('wbs_' + line).value;
  var wbsLineTop=wbsLine.substr(0,wbsLine.lastIndexOf("."));
  if (action == null) {
    var action=(dojo.byId('status_' + line).value == 'opened') ? "close" : "open";
  }

  if (action == "close") {
    dojo.byId('group_' + line).className="ganttExpandClosed";
    dojo.byId('status_' + line).value="closed";
    saveCollapsed(scope);
  } else {
    dojo.byId('group_' + line).className="ganttExpandOpened";
    dojo.byId('status_' + line).value="opened";
    saveExpanded(scope);
  }
  for (var i=line + 1;i <= nbLines;i++) {
    var wbs=dojo.byId('wbs_' + i).value;
    var wbsTop=wbs.substr(0,wbs.lastIndexOf("."));
    if (wbs.length <= wbsLine.length) {
      break;
    }
    if (wbsTop.substr(0,wbsLine.length) != wbsLine) {
      break;
    }
    if (action == "close") {
      dojo.byId('line_' + i).style.display="none";
    } else {
      dojo.byId('line_' + i).style.display="";
      var status=dojo.byId('status_' + i).value;
      if (status == 'closed') {
        var wbsClosed=dojo.byId('wbs_' + i).value;
        for (j=i + 1;j <= nbLines;j++) {
          var wbsSub=dojo.byId('wbs_' + j).value;
          if (wbsSub.indexOf(wbsClosed) == -1) {
            break;
          }
        }
        i=j - 1;
      }
    }
  }
}

/**
 * Refresh the imputation list
 * 
 * @return
 */
function refreshImputationList() {
  blockImputationSave();
  var rangeType=dojo.byId('monthSpinner').value;
  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return false;
  }
  formInitialize();
  dojo.byId('userId').value=dijit.byId('userName').get("value");
  //dojo.byId('idle').checked=dojo.byId('listShowIdle').checked;
  if(dijit.byId('listShowIdle').get('value')=='on'){
    dojo.byId('idle').checked = true;
  }else{
    dojo.byId('idle').checked = false;
  }
  //dojo.byId('showPlannedWork').checked=dojo.byId('listShowPlannedWork').checked;
  if(dijit.byId('listShowPlannedWork').get('value')=='on'){
    dojo.byId('showPlannedWork').checked = true;
  }else{
    dojo.byId('showPlannedWork').checked = false;
  }
  //dojo.byId('showIdT').checked=dojo.byId('showId').checked;
  if(dijit.byId('showId').get('value')=='on'){
    dojo.byId('showIdT').checked = true;
  }else{
    dojo.byId('showIdT').checked = false;
  }
  dojo.byId('yearSpinnerT').value=dojo.byId('yearSpinner').value;
  if (dojo.byId('weekSpinnerT')) dojo.byId('weekSpinnerT').value=dijit.byId('weekSpinner').get('value');
  if (dojo.byId('monthSpinnerT')) dojo.byId('monthSpinnerT').value=dijit.byId('monthSpinner').get('value');
  //dojo.byId('hideDone').checked=dojo.byId('listHideDone').checked;
  if(dijit.byId('listHideDone').get('value')=='off'){
    dojo.byId('hideDone').checked = true;
  }else{
    dojo.byId('hideDone').checked = false;
  }

  enableWidget("userName");
  enableWidget("yearSpinner");
  enableWidget("weekSpinner");
  enableWidget("monthSpinner");
  enableWidget("dateSelector");
  enableWidget("listDisplayOnlyCurrentWeekMeetings");
  enableWidget("listHideDone");
  enableWidget("listHideNotHandled");
  enableWidget("listShowIdle");
  enableWidget("listShowPlannedWork");
  enableWidget("showId");
  enableWidget("listDisplayProjectColorImputation");
  enableWidget("listDisplayActivityColorImputation");

  if (dojo.byId('hideNotHandled') && dijit.byId('listHideNotHandled')) {
  //if (dojo.byId('hideNotHandled') && dojo.byId('listHideNotHandled')) {
    //dojo.byId('hideNotHandled').checked=dojo.byId('listHideNotHandled').checked;
    if(dijit.byId('listHideNotHandled').get('value')=='off'){
      dojo.byId('hideNotHandled').checked = true;
    }else{
      dojo.byId('hideNotHandled').checked = false;
    }
  }
  
  //dojo.byId('displayOnlyCurrentWeekMeetings').checked=dojo.byId('listDisplayOnlyCurrentWeekMeetings').checked;
  if(dijit.byId('listDisplayOnlyCurrentWeekMeetings').get('value')=='on'){
    dojo.byId('displayOnlyCurrentWeekMeetings').checked = true;
  }else{
    dojo.byId('displayOnlyCurrentWeekMeetings').checked = false;
  }
  
  if(dijit.byId('listDisplayProjectColorImputation').get('value')=='on'){
    dojo.byId('displayProjectColorImputation').checked = true;
  }else{
    dojo.byId('displayProjectColorImputation').checked = false;
  }
  if(dijit.byId('listDisplayActivityColorImputation').get('value')=='on'){
    dojo.byId('displayActivityColorImputation').checked = true;
  }else{
    dojo.byId('displayActivityColorImputation').checked = false;
  }
  loadContent('../view/refreshImputationList.php','workDiv','listForm',false,null,null,null,function(){
      blockImputationSave();
  });
  return true;
}

/**
 * Refresh the imputation list after period update (check format first)
 * 
 * @return
 */
var refreshTimoutInProgress=null;
var refreshInProgress=false;
function refreshImputationPeriod(directDate) {
  blockImputationSave();
  if (refreshInProgress && directDate) {
    return true;
  }
  if (refreshTimoutInProgress !== null) {
    clearTimeout(refreshTimoutInProgress);
  }
  var periodType=dojo.byId('rangeType').value;
  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    var period=dojo.byId('rangeValue').value;
    var year=period.substr(0,4);
    dijit.byId('yearSpinner').set('value',year);
    if (periodType=='week') {
      var week=period.substr(4,2);
      dijit.byId('weekSpinner').set('value',week);
      var day=getFirstDayOfWeek(week,year);
    } else  if (periodType=='month') {
      var month=period.substr(4,2);
      dijit.byId('monthSpinner').set('value',week);
      var day=year+'-'+month+'-01';
    }
    dijit.byId('dateSelector').set('value',day);
    return false;
  }
  refreshInProgress=true;
  if (directDate) {
    var year=directDate.getFullYear();
    var week=getWeek(directDate.getDate(),directDate.getMonth() + 1,directDate.getFullYear()) + '';
    var month=directDate.getMonth() + 1;
    if (periodType=='week' && week == 1 && directDate.getMonth() > 10) {
      year+=1;
    }
    dijit.byId('yearSpinner').set('value',year);
    dijit.byId('weekSpinner').set('value',week);
    dijit.byId('monthSpinner').set('value',month);
    
  } else {
    var year=dijit.byId('yearSpinner').get('value');
    var week=dijit.byId('weekSpinner').get('value') + '';
    var month=dijit.byId('monthSpinner').get('value') + '';
  }
  if (week.length == 1 || parseInt(week,10) < 10) {
    week='0' + week;
  }
  if (month.length == 1 || parseInt(month,10) < 10) {
    month='0' + month;
  }
  if (periodType=='week') {
    if (week == '00') {
      week=getWeek(31,12,year - 1);
      if (week == 1) {
        var day=getFirstDayOfWeek(1,year);
        // day=day-1;
        week=getWeek(day.getDate() - 1,day.getMonth() + 1,day.getFullYear());
      }
      year=year - 1;
      dijit.byId('yearSpinner').set('value',year);
      dijit.byId('weekSpinner').set('value',week);
    } else if (parseInt(week,10) > 53) {
      week='01';
      year+=1;
      dijit.byId('yearSpinner').set('value',year);
      dijit.byId('weekSpinner').set('value',week);
    } else if (parseInt(week,10) > 52) {
      lastWeek=getWeek(31,12,year);
      if (lastWeek == 1) {
        var day=getFirstDayOfWeek(1,year + 1);
        // day=day-1;
        lastWeek=getWeek(day.getDate() - 1,day.getMonth() + 1,day.getFullYear());
      }
      if (parseInt(week,10) > parseInt(lastWeek,10)) {
        week='01';
        year+=1;
        dijit.byId('yearSpinner').set('value',year);
        dijit.byId('weekSpinner').set('value',week);
      }
    }
  } else if (periodType=='month') {
    if (parseInt(month)==0) {
      month='12';
      year=year - 1;
      dijit.byId('yearSpinner').set('value',year);
      dijit.byId('monthSpinner').set('value',month);
    } else if (parseInt(month)>12) {
      month='01';
      year=year + 1;
      dijit.byId('yearSpinner').set('value',year);
      dijit.byId('monthSpinner').set('value',month);
    }
  }
  if (periodType=='week') var day=getFirstDayOfWeek(week,year);
  else if (periodType=='month') var day=year+'-'+month+'-01';
  dijit.byId('dateSelector').set('value',day);
  if (periodType=='week') dojo.byId('rangeValue').value='' + year + week;
  else if (periodType=='month') dojo.byId('rangeValue').value='' + year + month; 
  if ((year + '').length == 4) {
    refreshTimoutInProgress=setTimeout("refreshImputationList();refreshInProgress=false;",500);
  }
  return true;
}

function blockImputationSave() {
  if (checkFormChangeInProgress()) {
    return false;
  }
  var divs = document.getElementsByClassName("imputationPlannedWorkCapacity");
  if (divs.length > 0){
    unblockImputationSave()
  }else {
    disableWidget('saveParameterButton'); 
  }
}
function unblockImputationSave() {
  enableWidget('saveParameterButton');
}

function recursiveAddWorkProject(idProject,day,diff) {
  if (dojo.byId('sumProject_' + idProject + '_' + day)) dojo.byId('sumProject_' + idProject + '_' + day).innerHTML=parseFloat(dojo.byId('sumProject_' + idProject + '_' + day).innerHTML)
      + parseFloat(diff);
  if (dojo.byId('sumProjectDisplay_' + idProject + '_' + day)) dojo.byId('sumProjectDisplay_' + idProject + '_' + day).value=formatDecimalToDisplay(dojo.byId('sumProject_' + idProject + '_' + day).innerHTML);
  if (dojo.byId('sumWeekProject_' + idProject)) dojo.byId('sumWeekProject_' + idProject).innerHTML=parseFloat(dojo.byId('sumWeekProject_' + idProject).innerHTML) + parseFloat(diff);
  if (dojo.byId('sumWeekProjectDisplay_' + idProject)) dojo.byId('sumWeekProjectDisplay_' + idProject).value=formatDecimalToDisplay(dojo.byId('sumWeekProject_' + idProject).innerHTML);
  if (dojo.byId('projectParent_' + idProject + '_' + day) && dojo.byId('projectParent_' + idProject + '_' + day) != null) recursiveAddWorkProject(
      dojo.byId('projectParent_' + idProject + '_' + day).value,day,diff);
}


function getPoolLineRowIdToUpdate(rowId){
  var idActivity = dojo.byId('idActivity_' + rowId).value;
  var idRole = dojo.byId('idRole_' + rowId).value;
  var greaterPoolLeft = 0;
  var poolRowId = null;
  dojo.query('[name="idActivity[]"]').forEach(function(node){
    if(node.id != 'idActivity_' + rowId){
      if(node.value == idActivity){
        var nodeRowId=node.id.split('_')[1];
        if(dojo.byId('imputable_' + nodeRowId).value != '' && dojo.byId('idAssignment_' + nodeRowId).value != '' && dojo.byId('idRole_' + nodeRowId).value == idRole){
          var nodeRowLeft = dijit.byId('leftWork_' + nodeRowId).get("value");
          if(nodeRowLeft > 0 && greaterPoolLeft <= nodeRowLeft){
            greaterPoolLeft=nodeRowLeft;
            poolRowId = nodeRowId;
          }
        }
      }
    }
  });
  return poolRowId;
}

function recursiveUpdatePoolLineLeft(rowId, diff){
  var poolRowId = getPoolLineRowIdToUpdate(rowId);
  if(poolRowId != null){
    var oldLeft=dijit.byId('leftWork_' + rowId).get("value");
    var oldPoolLeft=dijit.byId('leftWork_' + poolRowId).get("value");
    var newPoolLeft = oldPoolLeft;
    var oldLeftDiff = oldLeft - diff;
    if(oldLeftDiff < 0){
      newPoolLeft = oldPoolLeft - Math.abs(oldLeftDiff);
    }
    var newPoolLeftDiff = (newPoolLeft < 0)?Math.abs(newPoolLeft):0;
    newPoolLeft=(newPoolLeft < 0) ? 0 : newPoolLeft;
    dijit.byId('leftWork_' + poolRowId).set("value",newPoolLeft);
    if(newPoolLeftDiff > 0){
      recursiveUpdatePoolLineLeft(rowId, newPoolLeftDiff);
    }
  }
}

function showPoolLinesToUpdate(rowId, button){
  dojo.query('#showPoolLineButton .roundedButtonSmall').forEach(function(node){
    var icon = node.firstChild;
    if(dojo.hasClass(icon, 'iconResourceTeam')){
      dojo.removeClass(icon, 'iconResourceTeam iconResourceTeam16');
      dojo.addClass(icon, 'iconNoResourceTeam iconNoResourceTeam16');
      saveDataToSession('displayPoolLine_'+rowId, 1);
    }else{
      dojo.removeClass(icon, 'iconNoResourceTeam iconNoResourceTeam16');
      dojo.addClass(icon, 'iconResourceTeam iconResourceTeam16');
      saveDataToSession('displayPoolLine_'+rowId, 0);
    }
  });
  var idActivity = dojo.byId('idActivity_' + rowId).value;
  var poolRowId = null;
  dojo.query('[name="idActivity[]"]').forEach(function(node){
    if(node.id != 'idActivity_' + rowId){
      if(node.value == idActivity){
        var nodeRowId=node.id.split('_')[1];
        if(dojo.byId('idAssignment_' + nodeRowId).value != ''){
          poolRowId = nodeRowId;
          if(poolRowId != null){
            var poolRow = dojo.byId('line_'+poolRowId).parentNode;
            if(poolRow.style.display == 'none'){
              poolRow.style.display = '';
              saveDataToSession('displayPoolLine_'+poolRowId, 1);
            }else{
              poolRow.style.display = 'none';
              saveDataToSession('displayPoolLine_'+poolRowId, 0);
            }
          }
        }
      }
    }
  });
}

/**
 * Dispatch updates for a work value : to column sum, real work, left work and
 * planned work
 * 
 * @param rowId
 * @param colId
 * @return
 */
// var oldImputationWorkValue=0;
var listPlannedWork = {};
function dispatchWorkValueChange(rowId,colId,date,isPlannedWork) {
  var oldWorkValue=dojo.byId('workOldValue_' + rowId + '_' + colId).value;
  // var oldWorkValue=oldImputationWorkValue;
  if (oldWorkValue == null || oldWorkValue == '') {
    oldWorkValue=0;
  }
  var newWorkValue=dijit.byId('workValue_' + rowId + '_' + colId).get('value');
  if (isNaN(newWorkValue)) {
    newWorkValue=0;
  }
  listPlannedWork[colId] = (listPlannedWork[colId] === undefined) ? (isPlannedWork ? isPlannedWork : 0) : listPlannedWork[colId];
  if (newWorkValue==0 && isPlannedWork) listPlannedWork[colId]=0;
  if (parseInt(dojo.byId('isAdministrative_' + rowId + '_' + colId).value) == 0) {
    // daysWorkFuture daysWorkFutureBlocking
    isFuture=dojo.byId('colIsFuture_' + colId).value == 1;
    isFutureBlocking=dojo.byId('colIsFutureBlocking_' + colId).value == 1;
    daysWorkFutureV=dojo.byId('daysWorkFuture').value;
    daysWorkFutureBlockingV=dojo.byId('daysWorkFutureBlocking').value;
    toAdd=rowId + "|" + colId;
    if (newWorkValue != 0) {
      if (isFuture) {
        if (daysWorkFutureV == 0) {
          daysWorkFutureV=[];
          daysWorkFutureV.push(rowId + "|" + colId);
        } else {
          daysWorkFutureV=daysWorkFutureV.split(',');
          find=false;
          for ( var ite in daysWorkFutureV) {
            if (daysWorkFutureV[ite] == toAdd) find=true;
          }
          if (!find) {
            daysWorkFutureV.push(toAdd);
          }
        }
      }
      if (isFutureBlocking) {
        if (daysWorkFutureBlockingV == 0) {
          daysWorkFutureBlockingV=[];
          daysWorkFutureBlockingV.push(rowId + "|" + colId);
        } else {
          daysWorkFutureBlockingV=daysWorkFutureBlockingV.split(',');
          find=false;
          for ( var ite in daysWorkFutureBlockingV) {
            if (daysWorkFutureBlockingV[ite] == toAdd) find=true;
          }
          if (!find) {
            daysWorkFutureBlockingV.push(toAdd);
          }
        }
      }
    } else {
      if (isFuture) {
        if (daysWorkFutureV != 0) {
          daysWorkFutureV=daysWorkFutureV.split(',');
          find=false;
          for ( var ite in daysWorkFutureV) {
            if (daysWorkFutureV[ite] == toAdd) daysWorkFutureV.splice(ite,1);
          }
        }
      }
      if (isFutureBlocking) {
        if (daysWorkFutureBlockingV != 0) {
          daysWorkFutureBlockingV=daysWorkFutureBlockingV.split(',');
          for ( var ite in daysWorkFutureBlockingV) {
            if (daysWorkFutureBlockingV[ite] == toAdd) daysWorkFutureBlockingV.splice(ite,1);
          }
        }
      }
    }
    toAddFuture='';
    if (Array.isArray(daysWorkFutureV)) {
      for ( var ite in daysWorkFutureV) {
        toAddFuture+=(ite == 0 ? '' : ',') + daysWorkFutureV[ite];
      }
    }
    if (toAddFuture == '') toAddFuture='0';
    dojo.byId('daysWorkFuture').value=toAddFuture;
    toAddFutureBlocking='';
    if (Array.isArray(daysWorkFutureBlockingV)) {
      for ( var ite in daysWorkFutureBlockingV) {
        toAddFutureBlocking+=(ite == 0 ? '' : ',') + daysWorkFutureBlockingV[ite];
      }
    }
    if (toAddFutureBlocking == '') toAddFutureBlocking='0';
    dojo.byId('daysWorkFutureBlocking').value=toAddFutureBlocking;
  }
  var diff=newWorkValue - oldWorkValue;
  recursiveAddWorkProject(dojo.byId('idProject_' + rowId + '_' + colId).value,colId,diff);
  // Update sum for column
  var oldSum=dijit.byId('colSumWork_' + colId).get("value");
  var newSum=oldSum + diff;
  newSum=Math.round(newSum * 100) / 100;
  dijit.byId('colSumWork_' + colId).set("value",newSum);
  // Update real work
  var oldReal=formatDisplayToDecimal(dojo.byId('realWork_' + rowId).value);
  var newReal=oldReal + diff;
  dojo.byId('realWork_' + rowId).value=formatDecimalToDisplay(newReal);
  //Update left work for pool
  if(autoUpdateLeftWorkOnPool == 1 && diff > 0){
    recursiveUpdatePoolLineLeft(rowId, diff);
  }
  // Update left work
  var assigned=formatDisplayToDecimal(dojo.byId('assignedWork_' + rowId).value);
  var oldLeft=dijit.byId('leftWork_' + rowId).get("value");
  if (assigned > 0 || diff > 0 || oldLeft > 0) {
    var newLeft=oldLeft - diff;
    newLeft=(newLeft < 0) ? 0 : newLeft;
    dijit.byId('leftWork_' + rowId).set("value",newLeft);
  } else {
    var newLeft=oldLeft;
  }
  // Update planned work
  var newPlanned=newReal + newLeft;
  dojo.byId('plannedWork_' + rowId).value=formatDecimalToDisplay(newPlanned);
  // store new value for next calculation...
  dojo.byId('workOldValue_' + rowId + '_' + colId).value=newWorkValue;
  // oldImputationWorkValue=newWorkValue;
  if (dojo.byId("idWorkElement_" + rowId)) {
    var found=null;
    var rowAct=rowId - 1;
    while (found == null && rowAct > 0) {
      if (dojo.byId('realWork_' + rowAct) && !dojo.byId("idWorkElement_" + rowAct)) {
        found=rowAct;
      }
      rowAct--;
    }
    if (found) {
      if (dojo.byId('realWork_' + found)) {
        var oldActReal=formatDisplayToDecimal(dojo.byId('realWork_' + found).value);
        var newActReal=oldActReal + diff;
        dojo.byId('realWork_' + found).value=formatDecimalToDisplay(newActReal);
        var oldActLeft=formatDisplayToDecimal(dojo.byId('leftWork_' + found).value);
        var newActLeft=oldActLeft - diff;
        if (newActLeft < 0) newActLeft=0;
        if (dijit.byId('leftWork_' + found)) dijit.byId('leftWork_' + found).set("value",newActLeft);
        else dojo.byId('leftWork_' + found).value=formatDecimalToDisplay(newActLeft);
        var newActPlan=newActReal + newActLeft;
        dojo.byId('plannedWork_' + found).value=formatDecimalToDisplay(newActPlan);
      }
    }
  }
  if (!saveWorkDetailTimeout)formChanged();
 
  disableWidget("userName");
  disableWidget("yearSpinner");
  disableWidget("weekSpinner");
  disableWidget("monthSpinner");
  disableWidget("dateSelector");
  disableWidget("listDisplayOnlyCurrentWeekMeetings");
  disableWidget("listHideDone");
  disableWidget("listHideNotHandled");
  disableWidget("listShowIdle");
  disableWidget("listShowPlannedWork");
  disableWidget("showId");
  disableWidget("listDisplayProjectColorImputation");
  disableWidget("listDisplayActivityColorImputation");
  unblockImputationSave();
  checkCapacity(date,listPlannedWork[colId]);
  dijit.byId('totalWork').set("value",parseFloat(dijit.byId('totalWork').get("value")) + diff);
  totalWork=Math.round(parseFloat(dijit.byId('totalWork').get("value")) * 100) / 100;
  businessDay=Math.round(parseFloat(dojo.byId('businessDay').value) * 100) / 100;
  classTotalWork="imputationValidCapacity imputation";
  var maxWeeklyWork=parseFloat(dojo.byId('resourceMaxWeeklyWork').value);
  maxWeeklyWork=Math.round(maxWeeklyWork * 100) / 100;
  if (dojo.byId('rangeType').value=='week' && maxWeeklyWork && totalWork > maxWeeklyWork) {
    classTotalWork='imputationBlockedCapacity imputation';
  } else if (totalWork > businessDay) {
    classTotalWork='imputationInvalidCapacity imputation';
  } else if (totalWork < businessDay) {
    classTotalWork='displayTransparent imputation';
  }
  dijit.byId('totalWork').set("class",classTotalWork);
  var classCurrentInput="input imputation" + ((dijit.byId('workValue_' + rowId + '_' + colId).get("value") > 0) ? ' imputationHasValue' : '');
  dijit.byId('workValue_' + rowId + '_' + colId).set("class",classCurrentInput)
  if ((oldReal == 0 && newReal > 0) || (oldLeft > 0 && newLeft == 0) || (newReal < oldReal)) {
    var url='../tool/checkStatusChange.php';
    url+='?newReal=' + newReal;
    url+='&newLeft=' + newLeft;
    url+='&idAssignment=' + dojo.byId('idAssignment_' + rowId).value;
    dojo.xhrGet({
      url:url+addTokenIndexToUrl(url),
      handleAs:"text",
      load:function(data) {
        dojo.byId('extra_' + rowId).innerHTML=data;
      }
    });
  }
} 

function isOffDay(vDate,idProject) {
  if(idProject != undefined && projectCalendar[idProject] != undefined){
    if (globalDefaultOffDays[projectCalendar[idProject]] != undefined && globalDefaultOffDays[projectCalendar[idProject]].indexOf(vDate.getDay()) != -1) {
      var day=(vDate.getFullYear() * 10000) + ((vDate.getMonth() + 1) * 100) + vDate.getDate();
      if (globalWorkDayList[projectCalendar[idProject]] != undefined && globalWorkDayList[projectCalendar[idProject]].lastIndexOf('#' + day + '#') >= 0) {
        return false;
      } else {
        return true;
      }
    }else {
      var day=(vDate.getFullYear() * 10000) + ((vDate.getMonth() + 1) * 100) + vDate.getDate();
      if (globalOffDayList[projectCalendar[idProject]] != undefined && globalOffDayList[projectCalendar[idProject]].lastIndexOf('#' + day + '#') >= 0) {
        return true;
      } else {
        return false;
      }
    }
  }else{
    if (defaultOffDays.indexOf(vDate.getDay()) != -1) {
      var day=(vDate.getFullYear() * 10000) + ((vDate.getMonth() + 1) * 100) + vDate.getDate();
      if (workDayList.lastIndexOf('#' + day + '#') >= 0) {
        return false;
      } else {
        return true;
      }
    } else {
      var day=(vDate.getFullYear() * 10000) + ((vDate.getMonth() + 1) * 100) + vDate.getDate();
      if (offDayList.lastIndexOf('#' + day + '#') >= 0) {
        return true;
      } else {
        return false;
      }
    }
  }
}
// V6.0.0 : not used any more
/*
 * function isOffDayNotWeekEnd(vDate) { var
 * day=(vDate.getFullYear()*10000)+((vDate.getMonth()+1)*100)+vDate.getDate();
 * if (offDayList.lastIndexOf('#'+day+'#')>=0) { return true; } else { return
 * false; } }
 */

/**
 * Dispatch updates for left work : re-calculate planned work
 */
function dispatchLeftWorkValueChange(rowId,isOnRealTime) {
  var newLeft=dijit.byId('leftWork_' + rowId).get("value");
  if (newLeft == null || isNaN(newLeft) || newLeft == '') {
    dijit.byId('leftWork_' + rowId).set("value",'0');
    newLeft=0;
  }
  var newReal=formatDisplayToDecimal(dojo.byId('realWork_' + rowId).value);
  var newPlanned=newReal + newLeft;
  dojo.byId('plannedWork_' + rowId).value=formatDecimalToDisplay(newPlanned);
  if (isOnRealTime == 1) {
    dojo.byId('assignedWork_' + rowId).value=formatDecimalToDisplay(newPlanned);
  }
  formChanged();

  disableWidget("userName");
  disableWidget("yearSpinner");
  disableWidget("weekSpinner");
  disableWidget("monthSpinner");
  disableWidget("dateSelector");
  disableWidget("listDisplayOnlyCurrentWeekMeetings");
  disableWidget("listHideDone");
  disableWidget("listHideNotHandled");
  disableWidget("listShowIdle");
  disableWidget("listShowPlannedWork");
  disableWidget("showId");
  disableWidget("listDisplayProjectColorImputation");
  disableWidget("listDisplayActivityColorImputation");
  unblockImputationSave();
  if (dojo.byId('leftChanged_' + rowId)) {
    dojo.byId('leftChanged_' + rowId).value='1';
  }

  if (newLeft || newLeft == 0) {
    var url='../tool/checkStatusChange.php';
    url+='?newReal=' + newReal;
    url+='&newLeft=' + newLeft;
    url+='&idAssignment=' + dojo.byId('idAssignment_' + rowId).value;
    dojo.xhrGet({
      url:url+addTokenIndexToUrl(url),
      handleAs:"text",
      load:function(data) {
        dojo.byId('extra_' + rowId).innerHTML=data;
        regex=/statusFinishKO/g;
        if (data.match(regex)) {
          var callBack=function() {
            var editorType=dojo.byId("timesheetResultEditorType").value;
            if (editorType == "CK" || editorType == "CKInline") { // CKeditor
                                                                  // type
              ckEditorReplaceEditor("timesheetResult",999);
              dojo.byId("dialogTimesheet").style.height='450px';
              dojo.byId("dialogTimesheet").style.width='800px';
            } else if (editorType == "text") {
              dijit.byId("timesheetResult").focus();
              dojo.byId("timesheetResult").style.height=(screen.height * 0.6) + 'px';
              dojo.byId("timesheetResult").style.width=(screen.width * 0.6) + 'px';
            } else if (dijit.byId("timesheetResultEditor")) { // Dojo type
              // editor
              dijit.byId("timesheetResultEditor").set("class","input");
              dijit.byId("timesheetResultEditor").focus();
              dijit.byId("timesheetResultEditor").set("height",(screen.height * 0.6) + 'px'); // Works
              // on
              // first
              // time
              dojo.byId("timesheetResultEditor_iframe").style.height=(screen.height * 0.6) + 'px'; // Works
              // after
              // first
              // time
            }
          }
          var idActivity=dojo.byId('idActivity_' + rowId).value;
          var params="&idActivity=" + idActivity + '&newReal=' + newReal + '&newLeft=' + newLeft + '&idAssignment=' + dojo.byId('idAssignment_' + rowId).value + '&rowId=' + rowId;
          loadDialog('dialogTimesheet',callBack,true,params,true,true,'addResult');
        }
      }
    });
  }
}

function startMove(id) {
  document.body.style.cursor='help';
}

function endMove(id) {
  document.body.style.cursor='normal';
}

// ==========================================================
// Work Period Locking
// ==========================================================

function submitWorkPeriod(action) {
  if (checkFormChangeInProgress()) {
    return false;
  }
  var rangeValue=dojo.byId('rangeValue').value;
  var rangeType='week';
  var resource=dijit.byId('userName').get('value');
  dojo.xhrGet({
    url:'../tool/submitWorkPeriod.php?action=' + action + '&rangeType=' + rangeType + '&rangeValue=' + rangeValue + '&resource=' + resource + ''+addTokenIndexToUrl(),
    handleAs:"text",
    load:function(data,args) {
      refreshImputationList();
      sendAlertOnSubmitWork(action,rangeType,rangeValue,resource);
    },
    error:function() {
    }
  });
}

function sendAlertOnSubmitWork(action,rangeType,rangeValue,resource) {
  dojo.xhrGet({
    url:'../tool/sendMail.php?className=Imputation&action=' + action + '&rangeType=' + rangeType + '&rangeValue=' + rangeValue + '&resource=' + resource + ''+addTokenIndexToUrl(),
    handleAs:"text",
    load:function(data,args) {
    },
    error:function() {
    }
  });
}

function enterRealAsPlanned(nbDays) {
  //if (!dojo.byId('listShowPlannedWork').checked) {
  if(dijit.byId('listShowPlannedWork').get('value')!='on'){
    showAlert(i18n('enterRealAsPlannedNeedsPlannedWork'));
    return;
  }
  var cptUpdates=0;
  var nblines=dojo.byId("nbLines").value;
  for (line=1;line <= nblines;line++) {
    if (dojo.byId('locked_' + line) && dojo.byId('locked_' + line).value == '1') continue;
    for (day=1;day <= nbDays;day++) {
      var workValue=dijit.byId('workValue_' + line + '_' + day);
      var plannedValue=dojo.byId('plannedValue_' + line + '_' + day);
      var isResourceTeam='';
      if (dojo.byId('isResourceTeam_' + line + '_' + day)) {
        isResourceTeam=dojo.byId('isResourceTeam_' + line + '_' + day).value;
      }
      if (plannedValue && isResourceTeam != '1') {
        workValue.set('value',plannedValue.getAttribute("data-value"));
        cptUpdates++;
      }
    }
  }
  if (cptUpdates == 0) {
    showAlert(i18n('messageNoImputationChange'));
  }
}

function checkCapacity(date,isPlannedWork) {
  var capacity=parseFloat(dojo.byId('resourceCapacity_' + date).value);
  capacity=Math.round(capacity * 100) / 100;
  var maxDailyWork=parseFloat(dojo.byId('resourceMaxDailyWork').value);
  maxDailyWork=Math.round(maxDailyWork * 100) / 100;
  // for (colId=1; colId<=7; colId++) {
  colId=dojo.byId('colId_' + date).value;
  valSum=Math.round(parseFloat(dijit.byId('colSumWork_' + colId).get("value")) * 100) / 100;
  listPlannedWork[colId]=isPlannedWork;
  if (maxDailyWork && valSum > maxDailyWork) {
    dijit.byId('colSumWork_' + colId).set("class","imputationBlockedCapacity imputation");
  } else if (valSum > capacity) {
    // dojo.style('colSumWork_' + colId, "backgroung","red");
    dijit.byId('colSumWork_' + colId).set("class","imputationInvalidCapacity imputation");
  } else if (valSum < capacity && !isPlannedWork) {
    dijit.byId('colSumWork_' + colId).set("class","displayTransparent imputation");
    // domClass.remove('colSumWork_' + colId, "imputationInvalidCapacity");
  } else if (isPlannedWork){
    dijit.byId('colSumWork_' + colId).set("class","imputationPlannedWorkCapacity imputation");
  } else {
    // dojo.style('colSumWork_' + colId, "backgroung","red");
    dijit.byId('colSumWork_' + colId).set("class","imputationValidCapacity imputation");
  }
  // }
}

function validFutureWorkDate() {
  valid=function() {
    formChangeInProgress=false;
    submitForm("../tool/saveImputation.php"+addTokenIndexToUrl('?'),"resultDivMain","listForm",true);
  };
  nbDays=dojo.byId('nbFutureDays').value;
  var msg=i18n('msgRealWorkInTheFuture',new Array(nbDays));
  showConfirm(msg,valid);
}

function saveImputation() {
  return new Promise((resolve, reject) => {
    var divs = document.getElementsByClassName("imputationPlannedWorkCapacity");
    Array.from(divs).forEach(function(div) {
      var nextSibling = div.nextElementSibling;
      if (nextSibling && nextSibling.tagName.toLowerCase() === 'input' && nextSibling.id.startsWith("colId_")) {
        var date = nextSibling.id.replace("colId_", "");
        checkCapacity(date,0);
      }     
    });
    var futureInput=dojo.byId('daysWorkFuture').value != '0' ? true : false;
    var futureInputBlocking=dojo.byId('daysWorkFutureBlocking').value != '0' ? true : false;
    var maxDailyWork=Math.round(parseFloat(dojo.byId('resourceMaxDailyWork').value) * 100) / 100;
    var maxWeeklyWork=Math.round(parseFloat(dojo.byId('resourceMaxWeeklyWork').value) * 100) / 100;
    var maxDailyWorkError=false;
    var maxWeeklyWorkError=false;
    if (maxDailyWork) {
      var nbDays=parseInt(dojo.byId('nbDays').value);
      for (var day=1;day <= nbDays;day++) {
        workValue=Math.round(dijit.byId('colSumWork_' + day).get("value") * 100) / 100;
        if (workValue > maxDailyWork) {
          maxDailyWorkError=true;
        }
      }
    }
    if (maxWeeklyWork && dojo.byId('rangeType').value=='week') {
      totalWork=Math.round(parseFloat(dijit.byId('totalWork').get("value")) * 100) / 100;
      if (totalWork > maxWeeklyWork) {
        maxWeeklyWorkError=true;
      }
    }
    if (maxWeeklyWorkError || maxDailyWorkError) {
      var msg='';
      var unit=dojo.byId('unitWorkDisplay').value;
      if (maxWeeklyWorkError) {
        msg+=i18n('maxWeeklyWorkError',new Array(maxWeeklyWork + ' ' + unit)) + '<br/>';
      }
      if (maxDailyWorkError) {
        msg+=i18n('maxDailyWorkError',new Array(maxDailyWork + ' ' + unit)) + '<br/>';
      }
      showAlert(msg);
      return reject('Work limit exceeded');
    } else if (futureInputBlocking) {
      nbDays=dojo.byId('nbFutureDaysBlocking').value;
      hideWait();
      showAlert(i18n('msgRealWorkInTheFutureBlocking',new Array(nbDays)));
      return reject('Future input work blocking');
    } else if (futureInput) {
      nbDays=dojo.byId('nbFutureDays').value;
      var msg=i18n('msgRealWorkInTheFuture',new Array(nbDays));
      hideWait();
      showConfirm(msg, function valid() {
        formChangeInProgress = false;
        submitForm("../tool/saveImputation.php" + addTokenIndexToUrl('?'), "resultDivMain", "listForm", true);
        resolve();
      });
    } else {
      formChangeInProgress=false;
      submitForm("../tool/saveImputation.php"+addTokenIndexToUrl('?'),"resultDivMain","listForm",true);
      resolve();
    }
  
    enableWidget("userName");
    enableWidget("yearSpinner");
    enableWidget("weekSpinner");
    enableWidget("monthSpinner");
    enableWidget("dateSelector");
    enableWidget("listDisplayOnlyCurrentWeekMeetings");
    enableWidget("listHideDone");
    enableWidget("listHideNotHandled");
    enableWidget("listShowIdle");
    enableWidget("listShowPlannedWork");
    enableWidget("showId");
    enableWidget("listDisplayProjectColorImputation");
    enableWidget("listDisplayActivityColorImputation");
  });
}

function dispatchWork(refType,refId) {
  var params="&refType=" + refType + "&refId=" + refId;
  var height=dojo.byId('body').offsetHeight;
  if (dijit.byId('WorkElement_realWork')) {
    params+="&work=" + dijit.byId('WorkElement_realWork').get('value') + "&heightWindow=" + height;
  }
  loadDialog('dialogDispatchWork',null,true,params,true);
}

function dispatchWorkImputation(refType,refId,curDate,idAssignment,idProject,idWorkValue,readonlyDispatchWorkDetail) {
  var idResource = dojo.byId('userId').value;
  var workOldValue=dojo.byId('workOldValue'+idWorkValue).value;
  var params="&refType=" + refType + "&refId=" + refId + "&idResource=" + idResource + "&curDate=" + curDate + "&idAssignment=" + idAssignment + "&idProject=" + idProject + "&idWorkValue=" + idWorkValue + "&workOldValue=" + workOldValue + "&readonlyDispatchWorkDetail=" +readonlyDispatchWorkDetail ;
  loadDialog('dialogDispatchWorkImputation',null,true,params,true);
}

var currentWorkImputationLine=null;
var currentWorkImputationRefType=null;
var currentWorkImputationRefId=null;
function addWorkImputationLine(refType,refId,cpt){
  currentWorkImputationLine=cpt;
  currentWorkImputationRefType=refType;
  currentWorkImputationRefId=refId;
  var params="&refType=" + refType + "&refId=" + refId;
  loadDialog('dialogWorkImputationLine',null,true,params,true);
}

function toggleSelectState(inputId,workId,uncertaintiesId, progressId) {
  const inputElem = document.getElementById(inputId);
  const addButton = document.getElementById('addWorkImputationLine');
  const selectWork = dijit.byId(workId); 
  const selectUncertainties = dijit.byId(uncertaintiesId); 
  const selectProgress = dijit.byId(progressId);
  if (inputElem.value != 0) {
    addButton.style.pointerEvents = 'auto';
    addButton.style.opacity = 1;
    selectWork.set('readOnly', false);
    selectUncertainties.set('readOnly', false);
    selectProgress.set('readOnly', false);
  } else {
    addButton.style.pointerEvents = 'none';
    addButton.style.opacity = 0.5; 
    selectWork.set("readOnly",true);
    selectUncertainties.set("readOnly",true);
    selectProgress.set("readOnly",true);
  }
}


function saveWorkCategory(){
  var callBack=function() {
    if (dojo.byId('lastSaveId') == null) return;
    var lastSaveId=dojo.byId('lastSaveId').value;
    cpt=1;
    while (dijit.byId('dispatchWorkImputation_'+cpt)) {
      if (currentWorkImputationLine == cpt ){
        var idValue = lastSaveId;
      }else{
        var workBeforNewValue = dojo.byId('dispatchWorkImputation_'+cpt).nextElementSibling.value;
        var idValue = workBeforNewValue;
      }
      refreshList('idWorkCategory', 'refId', currentWorkImputationRefId, idValue, 'dispatchWorkImputation_'+cpt, false, 'refType', currentWorkImputationRefType);
      cpt++;
      if (cpt>100) break;
    }
    refreshList('idWorkCategory', 'refId', currentWorkImputationRefId, lastSaveId, 'dispatchWorkImputation_'+currentWorkImputationLine, false, 'refType', currentWorkImputationRefType);
  	hideWait();
  }
  loadContent("../tool/saveWorkCategory.php","resultDivMain","workImputationForm",true, "workCategory",null,null,callBack);
  dijit.byId('dialogWorkImputationLine').hide();
}

function addDispatchWorkImputationLine(unit, refType, refId) {
  cpt=0;
  while (dijit.byId('dispatchWorkImputation_'+cpt)) {
    cpt++;
  }  
  index = updateDispatchWorkTotal('dispatchWorkImputationValue_', 'dispatchWorkImputationTotal');
  var tbody = dojo.byId("dialogDispatchImputationTable");

  var tr = dojo.create("tr", {}, tbody);

  var td1 = dojo.create("td", { style: "text-align: right; font-weight: bold; visibility: hidden;" }, tr);
  td1.innerHTML = "<?php echo i18n('sum'); ?>";

  dojo.create("td", { innerHTML: "&nbsp;&nbsp;" }, tr);

  var td3 = dojo.create("td", { style: "text-align: center; width: 52px; vertical-align: top;" }, tr);
  var workImputationValueId = "dispatchWorkImputationValue_" + cpt;
  var numberTextBox = new dijit.form.NumberTextBox({
    'class': "input",
    id: workImputationValueId,
    name: "dispatchWorkImputationValue[]",
    style: "width: 50px;",
    value: 0,
    onChange: function () {
      updateDispatchWorkImputationTotal('dispatchWorkImputationValue_', 'dispatchWorkImputationTotal');
      toggleSelectState(
          'dispatchWorkImputationValue_' + cpt, 
          'dispatchWorkImputation_' + cpt, 
          'uncertaintiesDispatchWorkImputation_' + cpt, 
          'progressDispatchWorkImputation_' + cpt
        );
    },
    onKeyDown: function (event) {
      if (event.keyCode == 110) {
        return intercepPointKey(this, event);
      }
    }
  }, dojo.create("div", {}, td3));

  var td4 = dojo.create("td", { style: "text-align: left; padding-top: 5px; width: 1px; vertical-align: top; line-height: 30px;" }, tr);
  td4.innerHTML = '&nbsp;' + unit;

  dojo.create("td", { innerHTML: "&nbsp;" }, tr);

  var td6 = dojo.create("td", { colspan: 2, style: "text-align: center; vertical-align: top;" }, tr);
  var workImputationId = "dispatchWorkImputation_" + cpt;
  var filteringSelect = new dijit.form.FilteringSelect({
    'class': "input",
    id: workImputationId,
    name: "dispatchWorkImputation[]",
    style: "width: 150px;",
    readOnly: true,
    onMouseDown: function () {
      dijit.byId(this.id).toggleDropDown();
    },
    selectOnClick: true
  }, dojo.create("div", {}, td6));
  
  refreshList('idWorkCategory', 'refId', refId, null, 'dispatchWorkImputation_'+cpt, false, 'refType', refType);
  
  var td8 = dojo.create("td", {
    style: "text-align: center; padding: 8px 5px 5px 5px; vertical-align: top; line-height: 30px;",
    className: "imageColorNewGui",
    name: "addWorkImputationLine"
  }, tr);

  td8.innerHTML = '<span class="roundedButtonSmall roundedButtonNoBorder" ' +
                  'style="top:0px;display:inline-block;width:22px;height:22px;" ' +
                  'onclick="addWorkImputationLine(\'' + refType + '\', \'' + refId + '\', ' + cpt + ');">' +
                  '<div class="iconButtonAdd22 iconButtonAdd iconSize22"></div>' +
                  '</span>';
  
  dojo.create("td", { innerHTML: "&nbsp;" }, tr);

  var td10 = dojo.create("td", { style: "text-align: center; padding: 0 2px 7px 0;" }, tr);
  var uncertaintiesId = "uncertaintiesDispatchWorkImputation_" + cpt;
  var uncertaintiesTextArea = new dijit.form.SimpleTextarea({
    'class': "input",
    name: "uncertaintiesDispatchWorkImputation[]",
    id: uncertaintiesId,
    maxlength: "4000",
    readOnly: true,
    style: "width: 250px; height: 50px; margin: 0 auto; display: block;"
  }, dojo.create("div", {}, td10));

  dojo.create("td", { innerHTML: "&nbsp;" }, tr);
  
  var td12 = dojo.create("td", { style: "text-align: center; padding: 0 2px 7px 0;" }, tr);
  var progressId = "progressDispatchWorkImputation_" + cpt;
  var progressTextArea = new dijit.form.SimpleTextarea({
    'class': "input",
    name: "progressDispatchWorkImputation[]",
    id: progressId,
    maxlength: "4000",
    readOnly: true,
    style: "width: 250px; height: 50px; margin: 0 auto; display: block;"
  }, dojo.create("div", {}, td12));
  
  tbody.appendChild(tr);
}



function addDispatchWorkLine(unit,nbLines) {
  index=updateDispatchWorkTotal('dispatchWorkValue_','dispatchWorkTotal');
  var moduleTokenWork=false;
  var tr=dojo.create("tr",{},"dialogDispatchTable");
  var td1=dojo.create("td",{},tr);
  var td2=dojo.create("td",{},tr);
  var td3=dojo.create("td",{},tr);
  var td4=dojo.create("td",{},tr);
  var td5=dojo.create("td",{},tr);
  var td6=dojo.create("td",{},tr);
  if (dojo.byId('moduleTokenActive') && dojo.byId('moduleTokenActive').value == '1') {
    moduleTokenWork=true;
    var td7=dojo.create("td",{},tr);
    var td8=dojo.create("td",{},tr);
    var td9=dojo.create("td",{},tr);
    var td10=dojo.create("td",{},tr);
    var td11=dojo.create("td",{},tr);
    var td12=dojo.create("td",{},tr);
    var td13=dojo.create("td",{},tr);
    var td14=dojo.create("td",{},tr);
    var td15=dojo.create("td",{},tr);
    var td16=dojo.create("td",{},tr);
    var td17=dojo.create("td",{},tr);
    var td18=dojo.create("td",{},tr);
    var div=dojo.create("div",{},td18);
    var td19=dojo.create("td",{},tr);
  }

  workDateId="dispatchWorkDate_" + index;
  var dt=new dijit.form.DateTextBox({
    'class':"input",
    name:"dispatchWorkDate[]",
    id:workDateId,
    maxlength:"10",
    style:"width:100px; text-align: center;",
    hasDownArrow:"true"
  },td1);

  workResourceId="dispatchWorkResource_" + index;
  var lst=new dijit.form.FilteringSelect({
    'class':"input",
    id:workResourceId,
    name:"dispatchWorkResource[]",
    style:"width:150px;"
  },(moduleTokenWork) ? td5 : td3);

  workValueId="dispatchWorkValue_" + index;
  var val=new dijit.form.NumberTextBox({
    'class':"input",
    id:workValueId,
    name:"dispatchWorkValue[]",
    style:"width:50px;",
    value:0,
    onChange:function() {
      updateDispatchWorkTotal('dispatchWorkValue_','dispatchWorkTotal');
    },
    onKeyDown:function() {
      if (event.keyCode == 110) {
        return intercepPointKey(this,event);
      }
    }
  },(moduleTokenWork) ? td7 : td5);

  if (moduleTokenWork) {
    td8.innerHTML+='&nbsp;' + unit;

    tokenTimeId="tokenTime_" + index;
    var time=new dijit.form.TimeTextBox({
      'class':"input",
      name:"tokenTime[]",
      id:tokenTimeId,
      maxlength:"10",
      style:"width:65px; text-align: center;",
      hasDownArrow:"true"
    },td3);

    tokentType="tokenType_" + index;
    var lstTokentType=new dijit.form.FilteringSelect({
      'class':"input",
      id:tokentType,
      name:"tokenType[]",
      style:"width:150px;",
      onChange:function() {
        dispatchSetTokenTypeEvents(index);
      }
    },td10);

    tokentMakupType="tokenMarkupType_" + index;
    var lstTokentMakupType=new dijit.form.FilteringSelect({
      'class':"input",
      id:tokentMakupType,
      name:"tokentMakupType[]",
      style:"width:150px;",
      onChange:function() {
        dispatchTokenMarkupTypeEvents(index);
      }
    },td12);

    tokenQuantityId="tokenQuantityValue_" + index;
    var valToken=new dijit.form.NumberTextBox({
      'class':"input",
      id:tokenQuantityId,
      name:"tokenQuantityValue[]",
      style:"width:50px;margin-left:10px;",
      value:'',
      onChange:function() {
        dispatchTokenQuantityValueEvents(index);
      },
      onKeyDown:function() {
        if (event.keyCode == 110) {
          return intercepPointKey(this,event);
        }
      }
    },td14);

    tokenQuantityMarkupId="tokenQuantityMarkupValue_" + index;
    var valTokenMarkup=new dijit.form.NumberTextBox({
      'class':"input",
      id:tokenQuantityMarkupId,
      name:"tokenQuantityMarkupValue[]",
      style:"width:50px;margin-left:10px;",
      value:''
    },td16);

    switchId="billableSiwtched_" + index;
    var switchButton=new dojox.mobile.Switch({
      'class':"colorSwitch",
      id:switchId,
      style:"width:10px;position:relative;top:2px;z-index:99;",
      value:"on",
      leftLabel:"",
      rightLabel:"",
      onStateChanged:function() {
        dijit.byId("billableToken_" + index).set("checked",(this.value == "on") ? true : false);
      }
    },div);
    switchButton.startup();

    var billableToken=new dijit.form.CheckBox({
      'class':"colorSwitch",
      id:"billableToken_" + index,
      name:"billableToken[]",
      style:(isNewGui) ? "display:none;" : '',
      value:'off',
      onChange:function() {
        dojo.byId("billableTokenInput_" + index).value=(this.checked == true) ? 1 : 0;
      }
    },td19);

    var billableTokenInput=document.createElement("input");
    billableTokenInput.setAttribute("type","hidden");
    billableTokenInput.setAttribute("id","billableTokenInput_" + id);
    billableTokenInput.setAttribute("name","billableTokenInput[]");
    billableTokenInput.value=1;
    td18.insertAdjacentElement('afterend',billableTokenInput);

    dijit.byId(lstTokentType).set("readOnly",true);
    dijit.byId(lstTokentMakupType).set("readOnly",true);
    dijit.byId(valToken).set("readOnly",true);
    dijit.byId(valTokenMarkup).set("readOnly",true);
    td11.style="text-align:center";
    td18.style="text-align:center";

    refreshListSpecific('idWorkToken','tokenType_' + index,'idProject',dojo.byId('idProjectToken').value);
    dojo.connect(dijit.byId('dispatchWorkValue_' + index),"onChange",function() {
      changeValueWorkTokenElement(index);
    });
  } else {
    td6.innerHTML+='&nbsp;' + unit;
  }

  refreshList('idResource','idProject',dijit.byId('idProject').get('value'),null,workResourceId,false);
}

function updateDispatchWorkTotal(elementId,divTotalID) {
  var cpt=1;
  var sum=0;
  while (dijit.byId(elementId + cpt)) {
    val=dijit.byId(elementId + cpt).get('value');
    if (isNaN(val)) {
      val=(dojo.byId(elementId + cpt).value) ? dojo.byId(elementId + cpt).value : 0;
    }
    sum+=parseFloat(val);
    cpt++;
  }
  dijit.byId(divTotalID).set('value',sum);
  return cpt; // return next available value
}

function updateDispatchWorkImputationTotal(elementId,divTotalID) {
  var cpt=1;
  if (dijit.byId('dispatchWorkImputationValue_0')) var cpt = 0;
  var sum=0;
  while (dijit.byId(elementId + cpt)) {
    val=dijit.byId(elementId + cpt).get('value');
    if (isNaN(val)) {
      val=(dojo.byId(elementId + cpt).value) ? dojo.byId(elementId + cpt).value : 0;
    }
    sum+=parseFloat(val);
    cpt++;
  }
  dijit.byId(divTotalID).set('value',sum);
  return cpt;
}

function dispatchWorkSave() {
  var formVar=dijit.byId('dialogDispatchWorkForm');
  var cpt=1;
  if(dijit.byId('dispatchWorkValue_' + cpt)) {
    var wDate=dijit.byId('dispatchWorkDate_' + cpt).get('value');
    wDate = wDate.toString();
    wDate = parseInt(wDate.substr(11, 4));
  } 
   if(wDate<=2000 || wDate>2100){
     showAlert(i18n("alertInvalidForm"));
     return;
   }
  if (!formVar.validate()) {
    showAlert(i18n("alertInvalidForm"));
    return;
  }
  var listArray=new Array();
  var cpt=1;
  var futureInput=false;
  var futureInputBlocking=false;
  var nbDays=dojo.byId('nbFutureDays').value;
  var nbDaysTime=dojo.byId('nbFutureDaysTime').value;
  var nbDaysBlocking=dojo.byId('nbFutureDaysBlocking').value;
  var nbDaysBlockingTime=dojo.byId('nbFutureDaysBlockingTime').value;
  var isAdministrative=dojo.byId('isAdministrative').value == 1;
  while (dijit.byId('dispatchWorkValue_' + cpt)) {
    res=dijit.byId('dispatchWorkResource_' + cpt).get('value');
    dat=dijit.byId('dispatchWorkDate_' + cpt).get('value');
    val=dijit.byId('dispatchWorkValue_' + cpt).get('value');
    if (val != 0 && dat != '' && res.trim() == '') {
      showAlert(i18n('selectRes'));
      return;
    } else if (res.trim() != '' && val != 0 && dat == null) {
      showAlert(i18n('selectDate'));
      return;
    }
    if (res && dat) {
      var key=res + "#" + dat;
      if (key in listArray) {
        showAlert(i18n('duplicateEntry'));
        return;
      }
      listArray[res + "#" + dat]='OK';
    }
    if (dat != null && !isAdministrative) {
      if (dat.getTime() / 1000 > nbDaysTime && val != 0) futureInput=true;
      if (dat.getTime() / 1000 > nbDaysBlockingTime && val != 0) futureInputBlocking=true;
    }
    cpt++;
  }

  if (futureInputBlocking && parseInt(nbDaysBlocking) != -1) {
    showAlert(i18n('msgRealWorkInTheFutureBlocking',new Array(nbDaysBlocking)));
  } else if (futureInput && parseInt(nbDays) != -1) {
    valid=function() {
      finishDispatchWorkSave();
    };
    var msg=i18n('msgRealWorkInTheFuture',new Array(nbDays));
    showConfirm(msg,valid);
  } else {
    finishDispatchWorkSave();
  }

}
var saveWorkDetailTimeout=null;
function saveWorkDetailImputation(cpt,date,idWorkValue){
  var totalField = dijit.byId("dispatchWorkImputationTotal").value;
  var hiddenField = dojo.byId("inputWorkValue").value;
  var maxDailyWork = parseFloat(dojo.byId('resourceMaxDailyWork').value);
  maxDailyWork = Math.round(maxDailyWork * 100) / 100;
  var workOldValue = dojo.byId(idWorkValue);
  if (workOldValue) workOldValue = workOldValue.value
  else workOldValue = 0;
  var maxWeeklyWork = parseFloat(dojo.byId('resourceMaxWeeklyWork').value);
  maxWeeklyWork = Math.round(maxWeeklyWork * 100) / 100;
  var maxWeeklyWorkError = false;
  var maxDailyWorkError = false;
  totalWork = Math.round(parseFloat(dijit.byId('totalWork').get("value")) * 100) / 100;
  colId=dojo.byId(date).value;
  totalWorkDay=Math.round(parseFloat(dijit.byId('colSumWork_' + colId).get("value")) * 100) / 100;
  var msg='';
  var unit=dojo.byId('unitWorkDisplay').value;
  
  if (maxWeeklyWork>0 && maxWeeklyWork<(totalWork - workOldValue + totalField) && dojo.byId('rangeType').value=='week'){
    maxWeeklyWorkError = true;
  }
  if (maxDailyWork>0 && maxDailyWork<(totalWorkDay - workOldValue + totalField)){
    maxDailyWorkError = true;
  }
  
  if (maxWeeklyWorkError || maxDailyWorkError) {
    var msg='';
    var unit=dojo.byId('unitWorkDisplay').value;
    if (maxWeeklyWorkError) {
      msg+=i18n('maxWeeklyWorkError',new Array(maxWeeklyWork + ' ' + unit)) + '<br/>';
    }
    if (maxDailyWorkError) {
      msg+=i18n('maxDailyWorkError',new Array(maxDailyWork + ' ' + unit)) + '<br/>';
    }
    showAlert(msg);
  }else {
    var callBack=function() {
      dijit.byId(hiddenField).set("value",totalField); 
      dijit.byId(hiddenField).set("readOnly",true);
      if(saveWorkDetailTimeout)clearTimeout(saveWorkDetailTimeout);
      saveWorkDetailTimeout=setTimeout('formChangeInProgress= false', 100);
    }
    loadContent("../tool/saveWorkDetailImputation.php","resultDivMain","dialogDispatchWorkImputationForm",true,null,false, false,callBack);
    dijit.byId('dialogDispatchWorkImputation').hide(); 
  }
}

function finishDispatchWorkSave() {
  updateDispatchWorkTotal('dispatchWorkValue_','dispatchWorkTotal');
  // var callBack=function(data) {
  // dijit.byId('dialogDispatchWork').hide();
  // var lastOperationStatus=window.top.dojo.byId('lastOperationStatus');
  // if (lastOperationStatus.value == "OK") {
  // refreshGrid(true);
  // }
  // };
  var callBack=null;
  loadContent("../tool/saveDispatchWork.php","resultDivMain","dialogDispatchWorkForm",true,'dispatchWork',false,false,callBack);
  // dojo.xhrPost({
  // url : "../tool/saveDispatchWork.php",
  // form: "dialogDispatchWorkForm",
  // handleAs : "text",
  // load : function(data) {
  // var contentWidget=dijit.byId("comboDetailResult");
  // if (!contentWidget) {
  // return;
  // }
  // contentWidget.set('content', data);
  // checkDestination("comboDetailResult");
  // var lastOperationStatus=window.top.dojo.byId('lastOperationStatus');
  // if (lastOperationStatus.value == "OK") {
  // refreshGrid(true);
  // }
  // dijit.byId('dialogDispatchWork').hide();
  // }
  // });

}

function formatDisplayToDecimal(val) {
  val=val + "";
  val=val.replace(browserLocaleDecimalSeparator,".");
  if (val == null || isNaN(val) || val == '') {
    val=0;
  }
  return parseFloat(val);
}
function formatDecimalToDisplay(val) {
  val=Math.round(val * 100) / 100;
  val=val + "";
  val=val.replace(".",browserLocaleDecimalSeparator);
  return val;
}

// PlannedWorkManual functions
var selectInterventionDateInProgress = 0;
var firstClickedDate = null;
var firstClickedResource = null;
//var firstClickedDatePlusOne = null;
//var shiftClickedDateMinusOne = null;
var myfirstPeriod = null;
function selectInterventionDate(date, resource, period, allowDouble, event, multiSelect) {
  if (allowDouble && event.ctrlKey) period = period + 'X';
  if (event.shiftKey && firstClickedDate && multiSelect && resource==firstClickedResource) {
    period = period + 'W';
    var shiftClickedDate = getLastDateInRange(firstClickedDate, date);    
    firstClickedDatePlusOne = addOneDay(firstClickedDate);
    shiftClickedDateMinusOne = supprOneDay(shiftClickedDate);
    var myfirstClickedDate = firstClickedDate;
  } else {
    firstClickedDate = date; 
    firstClickedResource = resource;
    myfirstClickedDate = date;
    firstClickedDateAddOne = date;
    myfirstPeriod = period;
  }
  var idMode=(dojo.byId('idInterventionMode')) ? dojo.byId('idInterventionMode').value : '';
  var letterMode=(dojo.byId('letterInterventionMode')) ? dojo.byId('letterInterventionMode').value : '';
  var refType=(dojo.byId('interventionActivityType')) ? dojo.byId('interventionActivityType').value : '';
  var refId=(dojo.byId('interventionActivityId')) ? dojo.byId('interventionActivityId').value : '';
  var url="../tool/selectInterventionDate.php?date=" + date + "&resource=" + resource + "&period=" + period;
  url+='&idMode=' + idMode + "&letterMode=" + letterMode;
  url+='&refType=' + refType + "&refId=" + refId;
  url+='&firstClickedDate=' + myfirstClickedDate+ '&shiftClickedDate=' + shiftClickedDate+'&myfirstPeriod='+myfirstPeriod;
  if (!idMode && !refType && !refId) {
    var msg=i18n('errorInterventionInput');
    displayMessageInResultDiv(msg,'WARNING',true,false);
    return;
  }
  selectInterventionDateInProgress+=1;
  showWait();
  dojo.xhrGet({
    url:url+addTokenIndexToUrl(url),
    handleAs:"text",
    load:function(data) {
      hideWait();
      var result={};
      if (data) try {
        result=JSON.parse(data);
      } catch (error) {
        return;
      }
      if (result.error) {
        displayMessageInResultDiv(result.error,'WARNING',true,false);
        return;
      }
      if (dijit.byId('assignmentAssignedWork') && dijit.byId('assignmentRealWork') && dijit.byId('assignmentLeftWork')) {
        // var result=JSON.parse(data);
        if (result.assigned !== null) dijit.byId('assignmentAssignedWork').set('value',result.assigned);
        if (result.real !== null) dijit.byId('assignmentRealWork').set('value',result.real);
        if (result.left !== null) dijit.byId('assignmentLeftWork').set('value',result.left);
        if (result.real !== null && result.left !== null) dijit.byId('assignmentPlannedWork').set('value',result.real + result.left);
      }
      selectInterventionDateInProgress-=1;
      if (selectInterventionDateInProgress == 0) hideWait();
      if (dojo.byId('selectInterventionDataResult')) dojo.byId('selectInterventionDataResult').value=data;
      var refreshUrl='../tool/refreshInterventionTable.php';
      if (dojo.byId('plannedWorkManualInterventionDiv') && dojo.byId('plannedWorkManualInterventionResourceList') && dojo.byId('plannedWorkManualInterventionMonthList')) {
        refreshUrl="../tool/refreshInterventionTable.php?scope=intervention&resources=" + dojo.byId('plannedWorkManualInterventionResourceList').value + '&months='
            + dojo.byId('plannedWorkManualInterventionMonthList').value;
        if (dojo.byId('plannedWorkManualInterventionSize')) refreshUrl+='&size=' + dojo.byId('plannedWorkManualInterventionSize').value;
        loadDiv(refreshUrl,'plannedWorkManualInterventionDiv');
      }
      if (dojo.byId('plannedWorkManualAssignmentDiv') && dojo.byId('plannedWorkManualAssignmentResourceList') && dojo.byId('plannedWorkManualAssignmentMonthList')) {
        refreshUrl="../tool/refreshInterventionTable.php?scope=assignment&resources=" + dojo.byId('plannedWorkManualAssignmentResourceList').value + '&months='
            + dojo.byId('plannedWorkManualAssignmentMonthList').value;
        if (dojo.byId('plannedWorkManualAssignmentSize')) refreshUrl+='&size=' + dojo.byId('plannedWorkManualAssignmentSize').value;
        if (dojo.byId('assignmentRefType') && dojo.byId('assignmentRefId')) {
          refreshUrl+='&refType=' + dojo.byId('assignmentRefType').value + '&refId=' + dojo.byId('assignmentRefId').value
        }
        loadDiv(refreshUrl,'plannedWorkManualAssignmentDiv');
      }
      if (multiSelect) refreshInterventionCapacity(myfirstClickedDate, date,refId,'XXX');
      else refreshInterventionCapacity(date, date, refId,period);
    }
  });
}

function getLastDateInRange(startDate, endDate) {
  var stopDate = new Date(endDate);
  return stopDate.toISOString().split('T')[0];
}
function addOneDay(date) {
  var result = new Date(date);
  result.setDate(result.getDate() + 1);
  return result.toISOString().split('T')[0]; 
}
function supprOneDay(date) {
  var result = new Date(date);
  result.setDate(result.getDate() - 1);
  return result.toISOString().split('T')[0]; 
}
function selectSingleDate(date, resource, period, allowDouble, event) {
  var idMode = (dojo.byId('idInterventionMode')) ? dojo.byId('idInterventionMode').value : '';
  var letterMode = (dojo.byId('letterInterventionMode')) ? dojo.byId('letterInterventionMode').value : '';
  var refType = (dojo.byId('interventionActivityType')) ? dojo.byId('interventionActivityType').value : '';
  var refId = (dojo.byId('interventionActivityId')) ? dojo.byId('interventionActivityId').value : '';

  var url = "../tool/selectInterventionDate.php?date=" + date + "&resource=" + resource + "&period=" + period;
  url += '&idMode=' + idMode + "&letterMode=" + letterMode;
  url += '&refType=' + refType + "&refId=" + refId;

  if (!idMode && !refType && !refId) {
    var msg = i18n('errorInterventionInput');
    displayMessageInResultDiv(msg, 'WARNING', true, false);
    return;
  }
}

function selectInterventionNoCapacity() {
  showInfo(i18n("selectInterventionNoCapacity"));
}
function selectInterventionMode(id,letter) {
  var mode='select';
  if (dojo.byId('idInterventionMode')) {
    if (dojo.byId('idInterventionMode').value == id) {
      dojo.byId('idInterventionMode').value='';
      if (dojo.byId('letterInterventionMode')) dojo.byId('letterInterventionMode').value='';
      mode='unselect';
    } else {
      dojo.byId('idInterventionMode').value=id;
      if (dojo.byId('letterInterventionMode')) dojo.byId('letterInterventionMode').value=letter;
    }
  }
  dojo.query(".interventionModeSelector").forEach(function(node,index,nodelist) {
    dojo.removeClass(node,'dojoxGridRowSelected');
  });
  if (mode == 'select') {
    dojo.query(".interventionModeSelector" + id).forEach(function(node,index,nodelist) {
      dojo.addClass(node,'dojoxGridRowSelected');
    });
  }
  saveDataToSession('selectInterventionPlannedWorkManual',id);
}

function selectInterventionActivity(refType,refId,peId) {
  var mode='select';
  if (dojo.byId('interventionActivityType') && dojo.byId('interventionActivityId')) {
    if (dojo.byId('interventionActivityType').value == refType && dojo.byId('interventionActivityId').value == refId) {
      dojo.byId('interventionActivityType').value='';
      dojo.byId('interventionActivityId').value='';
      mode='unselect';
    } else {
      dojo.byId('interventionActivityType').value=refType;
      dojo.byId('interventionActivityId').value=refId;
    }
  }
  dojo.query(".interventionActivitySelector").forEach(function(node,index,nodelist) {
    dojo.removeClass(node,'dojoxGridRowSelected');
  });
  dojo.query(".iconGoto").forEach(function(node,index,nodelist) {
    dojo.removeClass(node,'iconGotoWhite16');
  });
  if (mode == 'select') {
    dojo.query(".interventionActivitySelector" + peId).forEach(function(node,index,nodelist) {
      dojo.addClass(node,'dojoxGridRowSelected');
    });
    dojo.query(".iconGoto").forEach(function(node,index,nodelist) {
      dojo.addClass(node,'iconGotoWhite16');
    });
  }
  if (mode == 'unselect') {
    saveDataToSession('selectActivityPlannedWorkManual','');
  } else {
    saveDataToSession('selectActivityPlannedWorkManual',refId);
  }

}

function saveInterventionCapacity(refType,refId,month,id) {
  var value=dijit.byId("interventionActivitySelector" + refId).get("value");
  if (isNaN(value) || value == null) {
    value='noVal';
    dijit.byId("interventionActivitySelector" + refId).set("value"," ");
  }
  var url='../tool/saveInterventionCapacity.php?refType=' + refType + '&refId=' + refId + '&month=' + month + '&value=' + value;
  dojo.xhrPut({
    url:url+addTokenIndexToUrl(url),
    form:'listFormPlannedWorkManual',
    handleAs:"text",
    load:function(data) {
      document.getElementById('idImageInterventionActivitySelector' + refId).style.display="block";
      setTimeout("dojo.byId('idImageInterventionActivitySelector" + refId + "').style.display='none';",1000);
      refreshPlannedWorkManualList();
    }
  });
}

function refreshInterventionCapacity(firstdate,lastdate,idActivity,period) {
  var url='../tool/refreshInterventionCapacity.php?firstdate=' + firstdate + '&lastdate='+lastdate+ '&refId=' + idActivity + '&period=' + period;
  dojo.xhrPut({
    url:url+addTokenIndexToUrl(url),
    form:'listFormPlannedWorkManual',
    handleAs:"text",
    load:function(data) {
      if (data) {
        var objList=JSON.parse(data);
        for (i=0; i< objList.length; i++) {
          obj=objList[i];
          date=obj.date;
          color=obj.color;
          date=date.replace("-","");
          date=date.replace("-","");
          if (color.length == 7 && dojo.byId(date + period + idActivity)) {
            dojo.byId(date + period + idActivity).style.background=color;
          } else if (dojo.byId(date + 'AM' + idActivity) && dojo.byId(date + 'PM' + idActivity)) {
            dojo.byId(date + 'AM' + idActivity).style.background=color.substr(0,7);
            dojo.byId(date + 'PM' + idActivity).style.background=color.substr(7,13);
          }
        }
      }
    }
  });
}

function startStopWork(action,type,id,paused,start) {
  if (paused) {
    showAlert(i18n('cantStartPausedWrok'));
    return;
  }
  loadContent("../tool/startStopWork.php?action=" + action,"resultDivMain","objectForm",true);
  var now=new Date();
  var vars=new Array();
  if (start) {
    vars[0]=start;
  } else {
    vars[0]=now.getHours() + ':' + now.getMinutes();
  }
  var msg='<div style="cursor:pointer" onClick="gotoElement(' + "'" + type + "'," + id + ');">' + type + ' #' + id + ' ' + i18n("workStartedAt",vars) + '</div>';
  if (action == 'start') {
    if (dojo.byId("currentWorkDiv")) {
      dojo.byId("currentWorkDiv").innerHTML=msg;
      dojo.byId("currentWorkDiv").style.display='block';
    }
    if (dojo.byId("statusBarInfoDiv")) dojo.byId("statusBarInfoDiv").style.display='none';
  } else {
    if (dojo.byId("currentWorkDiv")) {
      dojo.byId("currentWorkDiv").innerHTML="";
      dojo.byId("currentWorkDiv").style.display='none';
    }
    if (dojo.byId("statusBarInfoDiv")) dojo.byId("statusBarInfoDiv").style.display='block';
  }
}