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
//= Requirements and test cases
//=============================================================================

function addTestCaseRun() {
  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
  // disableWidget('dialogTestCaseRunSubmit');
  var params="&testSessionId=" + dijit.byId('id').get('value');
  loadDialog('dialogTestCaseRun',null,true,params);
}

function refreshTestCaseRunList(selected) {
  disableWidget('dialogTestCaseRunSubmit');
  var url='../tool/dynamicListTestCase.php';
  url+='?idProject=' + dijit.byId('idProject').get('value');
  if (dijit.byId('idProduct')) url+='&idProduct=' + dijit.byId('idProduct').get('value');
  else if (dijit.byId('idProductOrComponent')) url+='&idProduct=' + dijit.byId('idProductOrComponent').get('value');
  else if (dijit.byId('idComponent')) url+='&idComponent=' + dijit.byId('idComponent').get('value');
  if (selected) {
    url+='&selected=' + selected;
  }
  loadContent(url,'testCaseRunListDiv','testCaseRunForm',false);
}

function editTestCaseRun(testCaseRunId,idRunStatus,callback) {
  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
  var testSessionId=dijit.byId('id').get('value');
  var params="&testCaseRunId=" + testCaseRunId + "&testSessionId=" + testSessionId;
  if (idRunStatus) params+="&runStatusId=" + idRunStatus;
  loadDialog('dialogTestCaseRun',callback,((callback) ? false : true),params);
}

function passedTestCaseRun(idTestCaseRun) {
  var callback=function() {
    if (saveTestCaseRun()) dijit.byId('dialogTestCaseRun').hide();
  };
  editTestCaseRun(idTestCaseRun,'2',callback);
}

function failedTestCaseRun(idTestCaseRun) {
  editTestCaseRun(idTestCaseRun,'3',null);
}

function blockedTestCaseRun(idTestCaseRun) {
  var callback=function() {
    if (saveTestCaseRun()) dijit.byId('dialogTestCaseRun').hide();
  };
  editTestCaseRun(idTestCaseRun,'4',callback);
}

function testCaseRunChangeStatus() {
  var status=dijit.byId('testCaseRunStatus').get('value');
  if (status == '3') {
    dojo.byId('testCaseRunTicketDiv').style.display="block";
  } else {
    if (!trim(dijit.byId('testCaseRunTicket').get('value'))) {
      dojo.byId('testCaseRunTicketDiv').style.display="none";
    } else {
      dojo.byId('testCaseRunTicketDiv').style.display="block";
    }
  }
}

function removeTestCaseRun(id,idTestCase) {
  formInitialize();
  if (!dojo.byId("testCaseRunId")) {
    var callBack=function() {
      if (dijit.byId('dialogAlert')) {
        dijit.byId('dialogAlert').hide();
      }
      removeTestCaseRun(id,idTestCase);
    }
    loadDialog('dialogTestCaseRun',callBack,false);
  }
  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
  dojo.byId("testCaseRunId").value=id;
  actionOK=function() {
    loadContent("../tool/removeTestCaseRun.php","resultDivMain","testCaseRunForm",true,'testCaseRun');
  };
  msg=i18n('confirmDeleteTestCaseRun',new Array(idTestCase));
  showConfirm(msg,actionOK);
}

function saveTestCaseRun() {
  var formVar=dijit.byId('testCaseRunForm');
  var mode=dojo.byId("testCaseRunMode").value;
  if ((mode == 'add' && dojo.byId("testCaseRunTestCaseList").value == "") || (mode == 'edit' && dojo.byId("testCaseRunTestCase").value == "")) return;
  if (mode == 'edit') {
    var status=dijit.byId('testCaseRunStatus').get('value');
    if (status == '3' || status == '4') {
      if (trim(dijit.byId('testCaseRunTicket').get('value')) == '' && trim(dijit.byId('testCaseRunComment').get('value')) == '') {
        dijit.byId("dialogTestCaseRun").show();
        showAlert(i18n('messageMandatory',new Array(i18n('colTicket')+"' "+i18n('OR').toLowerCase()+" '"+i18n('colComment'))));
        return;
      }
    }
  }
  if (formVar.validate()) {
    loadContent("../tool/saveTestCaseRun.php","resultDivMain","testCaseRunForm",true,'testCaseRun');
    dijit.byId('dialogTestCaseRun').hide();
    return true;
  } else {
    dijit.byId("dialogTestCaseRun").show();
    showAlert(i18n("alertInvalidForm"));
    return false;
  }
}

function saveTcrData(id,textZone) {
  var value=(dijit.byId("tcr" + textZone + "_" + id))?dijit.byId("tcr" + textZone + "_" + id).get("value"):dojo.byId("tcr" + textZone + "_" + id).value;
  var url='../tool/saveTcrData.php?idTcr=' + id + '&zone=' + textZone + '&valueZone=' + value;
  dojo.xhrPut({
    url:url+addTokenIndexToUrl(url),
    form:'objectForm',
    handleAs:"text",
    load:function(data) {
      addMessage(i18n("col" + textZone) + " " + i18n("resultSave"));
      document.getElementById('idImage' + textZone + id).style.display="block";
      setTimeout("dojo.byId('idImage" + textZone + id + "').style.display='none';",1000);
    }
  });
}
function tcrDirectEdit(idTcr,field,width) {
  var tdNodeId='tdTcr'+field+'_'+idTcr;
  var tdNode=dojo.byId(tdNodeId);
  if (tdNode.innerHTML.indexOf('<textarea dojoType')>=0) return;
  var htmlText='<textarea onkeyup="tcrDirectTextareaResize(this);" dojoType="dijit.form.Textarea" id="tcr'+field+'_'+idTcr+'" name="tcr'+field+'_'+idTcr+'"';
  htmlText+=' style="resize: none;overflow: auto hidden; box-sizing: border-box; float: left; width: 100%; ' 
                  +' background: none; display: block; font-family:verdana; font-size:9pt; margin:0; padding:0; border:1px solid #eeeeee;"';
  htmlText+=' maxlength="4000" onchange="saveTcrData('+idTcr+',\''+field+'\');">';
  htmlText+=(tdNode.innerHTML!=undefined)?tdNode.innerHTML:'xxxxx';
  htmlText+='</textarea>';
  htmlText+='<img  id="idImage'+field+idTcr+'" src="../view/img/savedOk.png" style="display: none; position:absolute; top:5px;right:5px; height:16px;"/>';
  tdNode.innerHTML=htmlText;
  tdNode.onclick=null;
  dojo.byId('tcr'+field+'_'+idTcr).focus();
  tcrDirectTextareaResize(dojo.byId('tcr'+field+'_'+idTcr));
}
function tcrDirectTextareaResize(elt) {
  elt.style.height = "";
  elt.style.height = (elt.scrollHeight) + "px";
}
function lockRequirement() {
  if (checkFormChangeInProgress()) {
    return false;
  }
  dijit.byId('locked').set('checked',true);
  dijit.byId('idLocker').set('value',dojo.byId('idCurrentUser').value);
  var curDate=new Date();
  dijit.byId('lockedDate').set('value',curDate);
  dijit.byId('lockedDateBis').set('value',curDate);
  formChanged();
  submitForm("../tool/saveObject.php"+addTokenIndexToUrl('?'),"resultDivMain","objectForm",true);
  return true;
}

function unlockRequirement() {
  if (checkFormChangeInProgress()) {
    return false;
  }
  dijit.byId('locked').set('checked',false);
  dijit.byId('idLocker').set('value',null);
  dijit.byId('lockedDate').set('value',null);
  dijit.byId('lockedDateBis').set('value',null);
  formChanged();
  submitForm("../tool/saveObject.php"+addTokenIndexToUrl('?'),"resultDivMain","objectForm",true);
  return true;
}

function showTickets(refType,refId) {
  loadDialog('dialogShowTickets',null,true,'&refType=' + refType + '&refId=' + refId,true);
}

function showUserStories(refType, refId){
	loadDialog('dialogShowUserStories',null,true,'&refType=' + refType + '&refId=' + refId,true);
}

function showStatusPeriod(refType,refId) {
  loadDialog('dialogStatusPeriod',null,true,'&refType=' + refType + '&refId=' + refId,true);
}

function scenarioProjectSwitchType(idProject) {
  showWait();
  lockedStatus=(dojo.byId("scenarioProjectIcon_"+idProject).className=="roundedIconButton iconLocked iconSize22")?"Locked":"UnLocked";
  dojo.xhrGet({
    url:'../tool/scenarioProjectSwitch.php?operation=type&project=' + idProject + '&status=' + lockedStatus+addTokenIndexToUrl(),
    handleAs:"text",
    load:function(data) {
      var result=JSON.parse(data);
      hideWait();
      if (result.result=='OK') {
        dojo.byId("scenarioProjectIcon_"+idProject).className="roundedIconButton icon"+result.newstatus+" iconSize22";
        dojo.byId("scenarioProjectTD_"+idProject).className=(result.altered=='YES')?"reportTableData alteredScenario":"reportTableData";
      } else {
        showAlert(result.message);
      }
    }
  });
}
function scenarioProjectSwitchDelay(idProject) {
  showWait();
  var delay=dijit.byId("scenarioProjectDelay_"+idProject).get('value');
  dojo.xhrGet({
    url:'../tool/scenarioProjectSwitch.php?operation=delay&project=' + idProject + '&delay=' + delay+addTokenIndexToUrl(),
    handleAs:"text",
    load:function(data) {
      var result=JSON.parse(data);
      hideWait();
      if (result.result=='OK') {
        dojo.byId("scenarioProjectDelayTD1_"+idProject).className=(result.altered=='YES')?"reportTableData alteredScenario":"reportTableData";
        dojo.byId("scenarioProjectDelayTD2_"+idProject).className=(result.altered=='YES')?"reportTableData alteredScenario":"reportTableData";
        dojo.byId("scenarioProjectDelayTD3_"+idProject).className=(result.altered=='YES')?"reportTableData alteredScenario":"reportTableData";
        dojo.byId("scenarioProjectDelayValue_"+idProject).innerHTML=sortFixLengthNumeric(delay,3);
      } else {
        showAlert(result.message);
      }
    }
  });
}
function sortFixLengthNumeric(val, numericLength) {
  if (!numericLength) return val;
  if (parseInt(val)>=0) {
    return '>'+padString(val,numericLength,'0');
  } else {
    max=parseInt(padString('',numericLength,'9'));
    val=Math.abs(val);
    if (max<val) inverse=0;
    else inverse=max-val;
    return '<'+padString(inverse,numericLength,'0');
  }
}
function padString(val,length,char){
  if (!char) char='0';
  var s = val+"";
  while (s.length < length) {
      s = char + s;
  }
  return s;
};


function scenarioPoolSwitchCapacity(idPool) {
  showWait();
  var capa=dijit.byId("scenarioPoolExtraCapa_"+idPool).get('value');
  dojo.xhrGet({
    url:'../tool/scenarioPoolSwitch.php?operation=extra&pool=' + idPool + '&capa=' + capa+addTokenIndexToUrl(),
    handleAs:"text",
    load:function(data) {
      var result=JSON.parse(data);
      hideWait();
      if (result.result=='OK') {
        dojo.byId("scenarioPoolTD1_"+idPool).className=(result.altered=='YES')?"reportTableData alteredScenario":"reportTableData";
        dojo.byId("scenarioPoolTD2_"+idPool).className=(result.altered=='YES')?"reportTableData alteredScenario":"reportTableData";
        dojo.byId("scenarioPoolTD3_"+idPool).className=(result.altered=='YES')?"reportTableData alteredScenario":"reportTableData";
        dojo.byId("scenarioPoolExtraCapa_"+idPool).innerHTML=sortFixLengthNumeric(capa*10,4);
        
      } else if (result.result=='DEL'){
        dojo.byId("scenarioPoolTD1_"+idPool).className=(result.altered=='YES')?"reportTableData alteredScenario":"reportTableData";
        dojo.byId("scenarioPoolTD2_"+idPool).className=(result.altered=='YES')?"reportTableData alteredScenario":"reportTableData";
        dojo.byId("scenarioPoolTD3_"+idPool).className=(result.altered=='YES')?"reportTableData alteredScenario":"reportTableData";
        dojo.byId("scenarioPoolExtraCapa_"+idPool).innerHTML=sortFixLengthNumeric(capa*10,4);
        refreshDataCriticalResources();
      } else {
        showAlert(result.message);
      }
    }
  });
}

function scenarioPoolSaveDate(idPool) {
  var date=dijit.byId("givenDate_"+idPool).get("value");
  date=formatDate(date);
  dojo.xhrGet({
    url:'../tool/scenarioPoolDate.php?operation=extra&pool=' + idPool + '&date=' + date+addTokenIndexToUrl(),
    handleAs:"text",
    load:function(data) {
      var result=JSON.parse(data);
      hideWait();
    }
  });
}

function calculateCurrencyConversionDisplay() {
  globalCurrency=window.top.paramCurrency;
  globalCurrencyPosition=window.top.paramCurrencyPosition;
  if ( ! dijit.byId('localCurrency')) return;
  localCurrency=dijit.byId('localCurrency').get('value');
  localCurrencyPosition=dijit.byId('localCurrencyPosition').get('value');
  if (trim(localCurrency)=='') {
    dojo.query(".inputlocalToGlobalDisplayClass").forEach(function(domNode) { domNode.innerHTML=''; });
    dojo.query(".inputglobalToLocalDisplayClass").forEach(function(domNode) { domNode.innerHTML=''; });
  	dijit.byId("globalToLocalConversion").set('value',null);
  	dijit.byId("localToGlobalConversion").set('value',null);
  	dijit.byId("localCurrencyPosition").set('value',null);
  	setReadonlyField('globalToLocalConversion');
  	setReadonlyField('localToGlobalConversion');
  	setReadonlyField('localCurrencyPosition');
    return;
  }
  localToGlobalConversion=dijit.byId('localToGlobalConversion').get('value');
  globalToLocalConversion=dijit.byId('globalToLocalConversion').get('value');
  
  localToGlobalDisplay=((localCurrencyPosition=='before')?localCurrency:'')+" 1 "+((localCurrencyPosition!='before')?localCurrency:'')
    +" = "+((globalCurrencyPosition=='before')?globalCurrency:'')+" "+((localToGlobalConversion>0)?localToGlobalConversion:'___')+" "+((globalCurrencyPosition!='before')?globalCurrency:'');
 
  globalToLocalDisplay=((globalCurrencyPosition=='before')?globalCurrency:'')+" 1 "+((globalCurrencyPosition!='before')?globalCurrency:'')
    +" = "+((localCurrencyPosition=='before')?localCurrency:'')+" "+((globalToLocalConversion>0)?globalToLocalConversion:'___')+" "+((localCurrencyPosition!='before')?localCurrency:'');
  dojo.query(".inputlocalToGlobalDisplayClass").forEach(function(domNode) { domNode.innerHTML=localToGlobalDisplay; });
  dojo.query(".inputglobalToLocalDisplayClass").forEach(function(domNode) { domNode.innerHTML=globalToLocalDisplay; });
  setRequiredField('globalToLocalConversion');
  setRequiredField('localToGlobalConversion');
  setRequiredField('localCurrencyPosition');
}
function setRequiredField(field) {
  dojo.addClass(dijit.byId(field).domNode,'required');
  dijit.byId(field).set('required',true);
  dojo.removeClass(dijit.byId(field).domNode,'readOnly');
  dijit.byId(field).set('readOnly',false);
  dijit.byId(field).set('disabled',false);
}
function setReadonlyField(field) {
  dojo.removeClass(dijit.byId(field).domNode,'required');
  dijit.byId(field).set('required',false);
  dojo.addClass(dijit.byId(field).domNode,'readOnly');
  dijit.byId(field).set('readOnly',true);
  dijit.byId(field).set('disabled',true);
}
var converionInProgress=null;
function calculateAmountFromConvertion(val, conv, target) { // Can also be used to convert from LocalToGlobal (for resource price)
  if (converionInProgress!==null && converionInProgress!=conv) {// Avoid recursive conversion : A=>B, then B=>A than can lead to loop due to roundings
	if (target && dijit.byId(target)) return dijit.byId(target).get("value"); 
	else return;  
  }
  converionInProgress=conv;
  var retVal=(conv)?Math.round(val*conv*100)/100:val;
  if (target && dijit.byId(target)) dijit.byId(target).set('value',retVal);
  setTimeout("converionInProgress=null;",10);
  return retVal;
}

function storeValueHidden(objectClass,id,value) {
  idProject=dojo.byId('selectedListProject').value;
  var url='../tool/storeValueHidden.php?idProject='+idProject+'&objectClass='+objectClass+"&id="+id+"&value="+((value)?1:0);
  dojo.xhrPost({
    url : url+addTokenIndexToUrl(),
    handleAs : "text",
    load : function(data, args) {
		if (data=='OK') {
		  if (value) {
			dojo.byId('hiddenNo_'+id).style.display='none';
			dojo.byId('hidden_'+id).style.display='block';
		  } else {
			dojo.byId('hiddenNo_'+id).style.display='block';
			dojo.byId('hidden_'+id).style.display='none';
		  }
	    } else {
		  showError(data);
        } 
    }
  });
}