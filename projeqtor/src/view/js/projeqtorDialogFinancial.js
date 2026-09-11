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
//= Situation
//=============================================================================

function addSituation() {
  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
  if (dijit.byId("situationToolTip")) {
    dijit.byId("situationToolTip").destroy();
    dijit.byId("situationComment").set("class","");
  }
  pauseBodyFocus();
  var callBack=function() {
    var editorType=dojo.byId("situationEditorType").value;
    if (editorType == "CK" || editorType == "CKInline") { // CKeditor type
      ckEditorReplaceEditor("situationComment",995);
    } else if (editorType == "text") {
      dijit.byId("situationComment").focus();
      dojo.byId("situationComment").style.height=(screen.height * 0.6) + 'px';
      dojo.byId("situationComment").style.width=(screen.width * 0.6) + 'px';
    } else if (dijit.byId("situationEditor")) { // Dojo type editor
      dijit.byId("situationEditor").set("class","input");
      dijit.byId("situationEditor").focus();
      dijit.byId("situationEditor").set("height",(screen.height * 0.6) + 'px'); // Works
      // on
      // first
      // time
      dojo.byId("situationEditor_iframe").style.height=(screen.height * 0.6) + 'px'; // Works
      // after
      // first
      // time
    }
  };
  var params="&objectClass=" + dojo.byId('objectClass').value;
  params+="&objectId=" + dojo.byId("objectId").value;
  loadDialog('dialogSituation',callBack,true,params,true);
}

function editSituation(situationId) {
  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
  if (dijit.byId("situationToolTip")) {
    dijit.byId("situationToolTip").destroy();
    dijit.byId("situationComment").set("class","");
  }
  pauseBodyFocus();
  var callBack=function() {
    var editorType=dojo.byId("situationEditorType").value;
    if (editorType == "CK" || editorType == "CKInline") { // CKeditor type
      ckEditorReplaceEditor("situationComment",995);
    } else if (editorType == "text") {
      dijit.byId("situationComment").focus();
      dojo.byId("situationComment").style.height=(screen.height * 0.6) + 'px';
      dojo.byId("situationComment").style.width=(screen.width * 0.6) + 'px';
    } else if (dijit.byId("situationEditor")) { // Dojo type editor
      dijit.byId("situationEditor").set("class","input");
      dijit.byId("situationEditor").focus();
      dijit.byId("situationEditor").set("height",(screen.height * 0.6) + 'px'); // Works
      // on
      // first
      // time
      dojo.byId("situationEditor_iframe").style.height=(screen.height * 0.6) + 'px'; // Works
      // after
      // first
      // time
    }
  };
  var params="&objectClass=" + dojo.byId('objectClass').value;
  params+="&objectId=" + dojo.byId("objectId").value;
  params+="&situationId=" + situationId;
  loadDialog('dialogSituation',callBack,true,params,true);
}

function saveSituation() {
  var formVar=dijit.byId('situationForm');
  if (formVar.validate()) {
    var editorType=dojo.byId("situationEditorType").value;
    if (editorType == "CK" || editorType == "CKInline") {
      situationEditor=CKEDITOR.instances['situationComment'];
      situationEditor.updateElement();
      var tmpCkEditor=situationEditor.document.getBody().getText();
      var tmpCkEditorData=situationEditor.getData();
    }
    loadContent("../tool/saveSituation.php","resultDivMain","situationForm",true,'situation');
    dijit.byId('dialogSituation').hide();
  } else {
    showAlert(i18n("alertInvalidForm"));
    return;
  }
}

function removeSituation(situationId) {
  var param="?situationId=" + situationId;
  param+="&situationRefType=" + dojo.byId('objectClass').value;
  param+="&situationRefId=" + dojo.byId("objectId").value;
  param+="&action=remove";
  actionOK=function() {
    loadContent("../tool/saveSituation.php" + param,"resultDivMain","situationForm",true,'situation');
  };
  msg=i18n('confirmDelete',new Array(i18n('Situation'),situationId));
  showConfirm(msg,actionOK);
}

function situationSelectPredefinedText(idPrefefinedText) {
  dojo.xhrPost({
    url:'../tool/getPredefinedSituation.php?id=' + idPrefefinedText + ''+addTokenIndexToUrl(),
    handleAs:"text",
    load:function(data,args) {
      if (data) {
        var ps=JSON.parse(data);
        dijit.byId('situationSituation').set('value',ps.situation);
        var editorType=dojo.byId("situationEditorType").value;
        if (editorType == "CK" || editorType == "CKInline") { // CKeditor type
          CKEDITOR.instances['situationComment'].setData(ps.comment);
        } else if (editorType == "text") {
          dijit.byId('situationComment').set('value',ps.comment);
          dijit.byId('situationComment').focus();
        } else if (dijit.byId('situationCommentEditor')) {
          dijit.byId('situationComment').set('value',ps.comment);
          dijit.byId('situationCommentEditor').set('value',ps.comment);
          dijit.byId("situationCommentEditor").focus();
        }
      }
    }
  });
}

function billLineChangeCatalog() {
  if (!dijit.byId("billLineIdCatalog") || !dijit.byId("billLineIdCatalog").get("value")) return;
  var idCatalog=dijit.byId("billLineIdCatalog").get("value");
  dojo.xhrGet({
    url:'../tool/getSingleData.php?dataType=catalogBillLine&idCatalog=' + idCatalog + ''+addTokenIndexToUrl(),
    handleAs:"text",
    load:function(data) {
      arrayData=data.split('#!#!#!#!#!#');
      dijit.byId('billLineDescription').set('value',arrayData[0]);
      dijit.byId('billLineDetail').set('value',arrayData[1]);
      dijit.byId('billLinePrice').set('value',parseFloat(arrayData[3]));
      dijit.byId('billLineUnit').set('value',arrayData[4]);
      if (arrayData[6]) {
        dijit.byId('billLineQuantity').set('value',parseFloat(arrayData[6]));
      }
    }
  });
}

// =============================================================================
// = ExpenseDetail
// =============================================================================

function addExpenseDetail(expenseType, refType, refId) {
  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
//  dojo.byId("expenseDetailId").value="";
//  dojo.byId("idExpense").value=dojo.byId("objectId").value;
//  dijit.byId("expenseDetailName").reset();
//  dijit.byId("expenseDetailReference").reset();
//  dijit.byId("expenseDetailDate").set('value',null);
//  dijit.byId("expenseDetailType").reset();
//  dojo.byId("expenseDetailDiv").innerHTML="";
//  dijit.byId("expenseDetailAmount").reset();
//  dijit.byId("expenseDetailAmountLocal").reset();
//  refreshList('idExpenseDetailType',expenseType,'1',null,'expenseDetailType',false);
//  dijit.byId("dialogExpenseDetail").show();
  var callBack=function() {
    refreshList('idExpenseDetailType',expenseType,'1',null,'expenseDetailType',false);
  };
  var params='&expenseType='+expenseType+'&refType='+refType+'&refId='+refId;
  loadDialog('dialogExpenseDetail',callBack,true,params,true);
}

var expenseDetailLoad=false;
function editExpenseDetail(expenseType, id, refType, refId) {
  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
  var callBack=function() {
    refreshList('idExpenseDetailType',expenseType,'1',null,'expenseDetailType',false);
    expenseDetailTypeChange(id);
  };
  
//  dojo.byId("expenseDetailId").value=id;
//  dojo.byId("idExpense").value=idExpense;
//  dijit.byId("expenseDetailName").set("value",dojo.byId('expenseDetail_' + id).value);
//  dijit.byId("expenseDetailReference").set("value",dojo.byId('expenseDetailRef_' + id).value);
//  dijit.byId("expenseDetailDate").set("value",getDate(expenseDate));
//  dijit.byId("expenseDetailAmount").set("value",dojo.number.parse(amount));
//  dijit.byId("dialogExpenseDetail").set('title',i18n("dialogExpenseDetail") + " #" + id);
//  dijit.byId("expenseDetailType").set("value",type);
  var params='&expenseType='+expenseType+'&id='+id+'&refType='+refType+'&refId='+refId;
  loadDialog('dialogExpenseDetail',callBack,true,params,true);
}

function saveExpenseDetail() {
  expenseDetailRecalculate();
  if (!dijit.byId('expenseDetailName').get('value')) {
    showAlert(i18n('messageMandatory',new Array(i18n('colName'))));
    return;
  }
  if (!dijit.byId('expenseDetailAmount').get('value')) {
    showAlert(i18n('messageMandatory',new Array(i18n('colAmount'))));
    return;
  }
  var formVar=dijit.byId('expenseDetailForm');
  if (formVar.validate()) {
    dijit.byId("expenseDetailName").focus();
    dijit.byId("expenseDetailAmount").focus();
    loadContent("../tool/saveExpenseDetail.php","resultDivMain","expenseDetailForm",true,'expenseDetail');
    dijit.byId('dialogExpenseDetail').hide();
  } else {
    showAlert(i18n("alertInvalidForm"));
  }
}

function removeExpenseDetail(expenseDetailId) {
  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
  actionOK=function() {
    loadContent("../tool/removeExpenseDetail.php?expenseDetailId="+expenseDetailId,"resultDivMain","expenseDetailForm",true,'expenseDetail');
  };
  msg=i18n('confirmDeleteExpenseDetail',new Array(dojo.byId('expenseDetail_' + expenseDetailId).value));
  showConfirm(msg,actionOK);
}

function expenseDetailTypeChange(expenseDetailId) {
  if (expenseDetailLoad) return;
  expenseDetailLoad=true;
  var idType=dijit.byId("expenseDetailType").get("value");
  var url='../tool/expenseDetailDiv.php?idType=' + idType;
  if (expenseDetailId) {
    url+='&expenseDetailId=' + expenseDetailId;
  }
  loadContent(url,'expenseDetailDiv',null,false);
  setTimeout('expenseDetailLoad=false;',500);
}

function expenseDetailRecalculate() {
  val=false;
  if (!dojo.byId('expenseDetailValue01')) return;
  if (dijit.byId('expenseDetailValue01')) {
    val01=dijit.byId('expenseDetailValue01').get("value");
  } else {
    val01=dojo.byId('expenseDetailValue01').value;
  }
  if (dijit.byId('expenseDetailValue02')) {
    val02=dijit.byId('expenseDetailValue02').get("value");
  } else {
    val02=dojo.byId('expenseDetailValue02').value;
  }
  if (dijit.byId('expenseDetailValue03')) {
    val03=dijit.byId('expenseDetailValue03').get("value");
  } else {
    val03=dojo.byId('expenseDetailValue03').value;
  }
  total=1;
  if (dojo.byId('expenseDetailUnit01').value) {
    total=total * val01;
    val=true;
  }
  if (dojo.byId('expenseDetailUnit02').value) {
    total=total * val02;
    val=true;
  }
  if (dojo.byId('expenseDetailUnit03').value) {
    total=total * val03;
    val=true;
  }
  if (val) {
    dijit.byId("expenseDetailAmount").set('value',total);
    lockWidget("expenseDetailAmount");
    lockWidget("expenseDetailAmountLocal");
  } else {
    unlockWidget("expenseDetailAmountLocal");
    if (! dijit.byId("expenseDetailAmountLocal")) unlockWidget("expenseDetailAmount");
  }
}

// =============================================================================
// = BillLines
// =============================================================================

function addBillLine(billingType) {
  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
  var postLoad=function() {
    var prj=dijit.byId('idProject').get('value');
    refreshListSpecific('listTermProject','billLineIdTerm','idProject',prj);
    refreshListSpecific('listResourceProject','billLineIdResource','idProject',prj);
    refreshList('idActivityPrice','idProject',prj,null,'billLineIdActivityPrice');
    dijit.byId("dialogBillLine").set('title',i18n("dialogBillLine"));
  };
  var params="&id=";
  params+="&refType=" + dojo.byId('objectClass').value;
  params+="&refId=" + dojo.byId("objectId").value;
  if (billingType) params+="&billingType=" + billingType;
  loadDialog('dialogBillLine',postLoad,true,params,true);
}

function editBillLine(id,billingType) {
  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
  var params="&id=" + id;
  params+="&refType=" + dojo.byId('objectClass').value;
  params+="&refId=" + dojo.byId("objectId").value;
  if (billingType) params+="&billingType=" + billingType;
  loadDialog('dialogBillLine',null,true,params,true);
}

function saveBillLine() {
  /*
  var formVar=dijit.byId('billedWorkCommandForm');
  if (dijit.byId('billedWorkCommandBilled').get('value') > dijit.byId('billedWorkCommandCommand').get('value')) {
    showAlert(i18n("billedQuantityCantBeSuperiorThanCommand"));
  } else {
    if (formVar.validate()) {
      loadContent("../tool/saveBilledWorkCommand.php","resultDivMain","billedWorkCommandForm",true,'billedWorkCommand');
      dijit.byId('dialogBilledWorkCommand').hide();
    } else {
      showAlert(i18n("alertInvalidForm"));
    }
  }*/
  var billingType = dojo.byId('billLineBillingType').value;
  if (billingType=='R') {
    var alert = ""; 
    var startDate = dijit.byId('billLineStartDate');
    var endDate = dijit.byId('billLineEndDate');
    var resource = dijit.byId('billLineIdResource');
    var activityPrice = dijit.byId('billLineIdActivityPrice');       
    if (resource.getValue() == null || resource.getValue() == "") {
      resource.focus();
      alert +=  i18n('messageMandatory',new Array(i18n('colIdResource'))) + '<br/>';
    } 
    if (activityPrice.getValue() == null || activityPrice.getValue()== "") {
      activityPrice.focus();
      alert +=  i18n('messageMandatory',new Array(i18n('colIdActivityPrice'))) + '<br/>';
    } 
    if (startDate.getValue() == null || startDate.getValue() == "") {
      startDate.focus();
      alert +=  i18n('messageMandatory',new Array(i18n('colStartDate'))) + '<br/>';
    } 
    if (endDate.getValue() == null || endDate.getValue() == "") {
      endDate.focus();
      alert +=  i18n('messageMandatory',new Array(i18n('colEndDate'))) + '<br/>';
    } 
    if (alert != "") {
      showAlert(alert);
      return;
    }
  }
  /*if (isNaN(dijit.byId("billLineLine").getValue())) {
    dijit.byId("billLineLine").set("class","dijitError");
    alert +=i18n('messageMandatory',new Array(i18n('BillLine'))) + '<br/>';
    new dijit.Tooltip({
      id:"billLineToolTip",
      connectId:["billLineLine"],
      label:alert,
      showDelay:0
    });
    dijit.byId("billLineLine").focus();
  } */
  loadContent("../tool/saveBillLine.php","resultDivMain","billLineForm",true,'billLine');
  dijit.byId('dialogBillLine').hide();
}

function removeBillLine(lineId) {
  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
  actionOK=function() {
    loadContent("../tool/removeBillLine.php?billLineId=" + lineId,"resultDivMain",null,true,'billLine');
  };
  msg=i18n('confirmDelete',new Array(i18n('BillLine'),lineId));
  showConfirm(msg,actionOK);
}

function billLineUpdateAmount() {
  var price=dijit.byId('billLinePrice').get('value');
  var quantity=dijit.byId('billLineQuantity').get('value');
  var amount=price * quantity;
  dijit.byId('billLineAmount').set('value',amount);
  if (dijit.byId('billLinePriceLocal') && dijit.byId('billLineAmountLocal')) {
    var priceLocal=dijit.byId('billLinePriceLocal').get('value');
    var amountLocal=priceLocal * quantity;
    dijit.byId('billLineAmountLocal').set('value',amountLocal);
  }
}
function billLineUpdateNumberDays() {
  if (dijit.byId('billLineUnit') && dijit.byId('billLineUnit').get("value") == '3') { // If
    // unit
    // =
    // day
    if (dijit.byId('billLineNumberDays') && dijit.byId('billLineQuantity') && dijit.byId('billLineQuantity').get("value") > 0) {
      dijit.byId('billLineNumberDays').set("value",dijit.byId('billLineQuantity').get("value"));
    }
  }
}

// =============================================================================
// = Resource Cost
// =============================================================================

function addResourceCost(idResource,idRole,funcList) {
  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
  var callBack=function() {
    affectationLoad=true;
    dojo.byId("resourceCostId").value="";
    dojo.byId("resourceCostIdResource").value=idResource;
    dojo.byId("resourceCostFunctionList").value=funcList;
    dijit.byId("resourceCostIdRole").set('readOnly',false);
    if (idRole) {
      dijit.byId("resourceCostIdRole").set('value',idRole);
    } else {
      dijit.byId("resourceCostIdRole").reset();
    }
    dijit.byId("resourceCostValue").reset('value');
    dijit.byId("resourceCostStartDate").set('value',null);
    resourceCostUpdateRole();
    dijit.byId("dialogResourceCost").show();
    setTimeout("affectationLoad=false",500);
  };
  var params="&idResource=" + idResource;
  //params+="&funcList=" + funcList;
  params+="&idRole=" + idRole;
  params+="&mode=add";
  loadDialog('dialogResourceCost',callBack,true,params);
}

function removeResourceCost(id,idRole,nameRole,startDate) {
  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
  var params="&idResource=" + dijit.byId('id').get("value");
  //params+="&funcList=";
  params+="&idRole=" + idRole;
  params+="&mode=delete";
  var callBack=function() {
    dojo.byId("resourceCostId").value=id;
  }
  loadDialog('dialogResourceCost',callBack,false,params,false);
  actionOK=function() {

    loadContent("../tool/removeResourceCost.php","resultDivMain","resourceCostForm",true,'resourceCost');
  };
  msg=i18n('confirmDeleteResourceCost',new Array(nameRole,startDate));
  showConfirm(msg,actionOK);
}

reourceCostLoad=false;
function editResourceCost(id,idResource,idRole,cost,startDate,endDate) {
  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
  var callBack=function() {
    dojo.byId("resourceCostId").value=id;
    dojo.byId("resourceCostIdResource").value=idResource;
    dijit.byId("resourceCostIdRole").set('readOnly',true);
    dijit.byId("resourceCostValue").set('value',dojo.number.format(cost / 100));
    var dateStartDate=getDate(startDate);
    dijit.byId("resourceCostStartDate").set('value',dateStartDate);
    dijit.byId("resourceCostStartDate").set('disabled',true);
    dijit.byId("resourceCostStartDate").set('required','false');
    reourceCostLoad=true;
    dijit.byId("resourceCostIdRole").set('value',idRole);
    setTimeout('reourceCostLoad=false;',300);
    dijit.byId("dialogResourceCost").show();
  };
  loadDialog('dialogResourceCost',callBack,true,null);
}

function saveResourceCost() {
  var formVar=dijit.byId('resourceCostForm');
  if (formVar.validate()) {
    loadContent("../tool/saveResourceCost.php","resultDivMain","resourceCostForm",true,'resourceCost');
    dijit.byId('dialogResourceCost').hide();
  } else {
    showAlert(i18n("alertInvalidForm"));
  }
}

function resourceCostUpdateRole() {
  if (reourceCostLoad) {
    return;
  }
  if (dijit.byId("resourceCostIdRole").get('value')) {
    dojo.xhrGet({
      url:'../tool/getSingleData.php?dataType=resourceCostDefault&idRole=' + dijit.byId("resourceCostIdRole").get('value') + '&isSubContractor='+dijit.byId("subcontractor").get("checked")+addTokenIndexToUrl(),
      handleAs:"text",
      load:function(data) {
        dijit.byId('resourceCostValue').set('value',dojo.number.format(data));
      }
    });
  }
  var funcList=dojo.byId('resourceCostFunctionList').value;
  $key='#' + dijit.byId("resourceCostIdRole").get('value') + '#';
  if (funcList.indexOf($key) >= 0) {
    dijit.byId("resourceCostStartDate").set('disabled',false);
    dijit.byId("resourceCostStartDate").set('required','true');
  } else {
    dijit.byId("resourceCostStartDate").set('disabled',true);
    dijit.byId("resourceCostStartDate").set('value',null);
    dijit.byId("resourceCostStartDate").set('required','false');
  }
}

function saveComplexity(id,idZone) {
  var value=dijit.byId("complexity" + idZone).get("value");
  var url='../tool/saveComplexity.php?idCatalog=' + id + '&name=' + value + '&idZone=' + idZone + ''+addTokenIndexToUrl();
  dojo.xhrPut({
    url:url,
    form:'objectForm',
    handleAs:"text",
    load:function(data) {
      if (data) {
        dijit.byId("complexity" + idZone).set("value",data);
        showAlert(i18n("cantDeleteUsingUOComplexity"));
      } else {
        loadContent("objectDetail.php?refreshComplexitiesValues=true","CatalogUO_unitOfWork",'listForm');
      }
    }
  });
}

// =============================================================================
// = Add-Edit-Remove an organization's Budget Element
// =============================================================================

function addBudgetElement(objectClassName,refId,id,year,scope) {
  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
  params='&objectClass=' + objectClassName;
  params+='&action=ADD';
  params+='&refId=' + refId;
  params+='&id=' + id;
  params+='&year=' + year;
  params+='&scope=' + scope;
  loadDialog('dialogAddChangeBudgetElement',null,true,params,true,true,'addBudgetElement');
}

function changeBudgetElement(objectClassName,refId,id,year,budgetWork,budgetCost,budgetExpenseAmount) {
  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
  params='&objectClass=' + objectClassName;
  params+='&action=CHANGE';
  params+='&refId=' + refId;
  params+='&id=' + id;
  params+='&year=' + year;
  params+='&budgetWork=' + budgetWork;
  params+='&budgetCost=' + budgetCost;
  params+='&budgetExpenseAmount=' + budgetExpenseAmount;

  loadDialog('dialogAddChangeBudgetElement',null,true,params,false,true,'changeBudgetElement');
}

function saveOrganizationBudgetElement() {
  loadContent("../tool/saveOrganizationBudgetElement.php","resultDivMain","addChangeBudgetElementForm",true);
  dijit.byId('dialogAddChangeBudgetElement').hide();
  showWait();
}

function closeUncloseBudgetElement(objectClassName,refId,id,idle,year) {
  var param="?objectClassName=" + objectClassName;
  param+="&refId=" + refId;
  param+="&budgetElementId=" + id;
  param+="&idle=" + idle;
  param+="&year=" + year;
  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
  if (idle == 0) {
    msg=i18n('confirmCloseBudgetElement');
  } else {
    msg=i18n('confirmUncloseBudgetElement');
  }
  actionOK=function() {
    loadContent("../tool/closeUncloseOrganizationBudgetElement.php" + param,"detailDiv","");
  };

  showConfirm(msg,actionOK);
}

function removeBudgetElement(objectClassName,refId,id,year) {
  var param="?objectClassName=" + objectClassName;
  param+="&refId=" + refId;
  param+="&budgetElementId=" + id;
  param+="&year=" + year;

  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }

  actionOK=function() {
    loadContent("../tool/removeOrganizationBudgetElement.php" + param,"detailDiv","");
  };

  msg=i18n('confirmRemoveBudgetElement');
  showConfirm(msg,actionOK);

}

// =============================================================================
// = Financial
// =============================================================================

function editProviderTerm(objectClass,idProviderOrder,isLine,id,name,date,tax,discount,untaxed,taxAmount,fullAmount,totalUntaxed) {
  affectationLoad=true;
  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
  // var percent = Math.round(untaxed*100000/totalUntaxed)/1000;
  var percent=untaxed * 100 / totalUntaxed;
  var callBack=function() {
    if (name) {
      dijit.byId("providerTermName").set('value',name);
    }
    if (date) {
      dijit.byId("providerTermDate").set('value',date);
    }
    if (tax) {
      dijit.byId("providerTermTax").set('value',tax);
    }
    if (discount) {
      dijit.byId("providerTermDiscount").set('value',discount);
    }
    if (isLine == 'false') {
      dijit.byId("providerTermPercent").set('value',percent);

      if (untaxed) {
        dijit.byId("providerTermUntaxedAmount").set('value',untaxed);
      }
      if (taxAmount) {
        dijit.byId("providerTermTaxAmount").set('value',taxAmount);
      }
      if (fullAmount) {
        dijit.byId("providerTermFullAmount").set('value',fullAmount);
      }
    }
    dijit.byId("dialogProviderTerm").show();
    setTimeout("affectationLoad=false",500);
  };
  var params="&objectClass=" + objectClass;
  params+="&id=" + id;
  params+="&idProviderOrderEdit=" + idProviderOrder;
  params+="&isLineMulti=" + isLine;
  params+="&mode=edit";
  loadDialog('dialogProviderTerm',callBack,false,params);
}

function removeProviderTerm(id,fromBill) {
  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
  actionOK=function() {
    var url="../tool/removeProviderTerm.php?providerTermId=" + id;
    if (fromBill) url+="&fromBill=true";
    loadContent(url,"resultDivMain",null,true,'providerTerm');
  };
  msg=i18n('confirmDeleteProviderTerm',new Array(id));
  showConfirm(msg,actionOK);
}

function removeProviderTermFromBill(id,idProviderBill) {
  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
  actionOK=function() {
    loadContent("../tool/removeProviderTerm.php?providerTermId=" + id + "&isProviderBill=true","resultDivMain",null,true,'providerTerm');
  };
  msg=i18n('confirmRemoveProviderTermFromBill',new Array(id));
  showConfirm(msg,actionOK);
}

function addWorkCommand(id) {
  var callBack=function() {
    affectationLoad=true;
    dijit.byId("dialogWorkCommand").show();
    setTimeout("affectationLoad=false",500);
  };
  var params="&idCommand=" + id;
  params+="&mode=add";
  params+="&isWorkCommandParent=" + false;
  loadDialog('dialogWorkCommand',callBack,false,params);
}

function addParentWorkCommand(id) {
  var callBack=function() {
    affectationLoad=true;
    dijit.byId("dialogWorkCommand").show();
    setTimeout("affectationLoad=false",500);
  };
  var params="&idCommand=" + id;
  params+="&mode=add";
  params+="&isWorkCommandParent=" + true;
  loadDialog('dialogWorkCommand',callBack,false,params);
}

function editWorkCommand(idCommand,id,idWorkUnit,idComplexity,quantity,unitAmount,commandAmount,unitAmountLocal,commandAmountLocal,idWorkCommand,nameWorkCommand,isWorkCommandParent) {
  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
  pauseBodyFocus();
  var callBack=function() {
    dijit.byId("dialogWorkCommand").show();
  };
  var params="&id=" + id;
  params+="&idCommand=" + idCommand;
  params+="&idWorkUnit=" + idWorkUnit;
  params+="&idComplexity=" + idComplexity;
  params+="&quantity=" + quantity;
  params+="&unitAmount=" + unitAmount;
  params+="&commandAmount=" + commandAmount;
  params+="&unitAmountLocal=" + unitAmountLocal;
  params+="&commandAmountLocal=" + commandAmountLocal;
  params+="&idWorkCommand=" + idWorkCommand;
  params+="&nameWorkCommand=" +nameWorkCommand;
  params+="&mode=edit";
  params+="&isWorkCommandParent=" + isWorkCommandParent;
  loadDialog('dialogWorkCommand',callBack,false,params);
}

function editBilledWorkCommand(idBill,id,idWorkCommand,quantity) {
  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
  pauseBodyFocus();
  var callBack=function() {
    dijit.byId("dialogBilledWorkCommand").show();
  };
  var params="&id=" + id;
  params+="&idBill=" + idBill;
  params+="&idWorkCommand=" + idWorkCommand;
  params+="&quantity=" + quantity;
  params+="&mode=edit";
  loadDialog('dialogBilledWorkCommand',callBack,false,params);
}

function addBilledWorkCommand(id) {
  var callBack=function() {
    affectationLoad=true;
    dijit.byId("dialogBilledWorkCommand").show();
    setTimeout("affectationLoad=false",500);
  };
  var params="&idBill=" + id;
  params+="&mode=add";
  loadDialog('dialogBilledWorkCommand',callBack,false,params);
}

function saveWorkCommand() {
  var formVar=dijit.byId('workCommandForm');
  if (formVar.validate()) {
    loadContent("../tool/saveWorkCommand.php","resultDivMain","workCommandForm",true,'workCommand');
    dijit.byId('dialogWorkCommand').hide();
  } else {
    showAlert(i18n("alertInvalidForm"));
  }
}

function saveParentWorkCommand() {
  var formVar=dijit.byId('workCommandForm');
  if (formVar.validate()) {
    loadContent("../tool/saveWorkCommand.php","resultDivMain","workCommandForm",true,'workCommand');
    dijit.byId('dialogWorkCommand').hide();
  } else {
    showAlert(i18n("alertInvalidForm"));
  }
}

function saveBilledWorkCommand() {
  var formVar=dijit.byId('billedWorkCommandForm');
  if (dijit.byId('billedWorkCommandBilled').get('value') > dijit.byId('billedWorkCommandCommand').get('value')) {
    showAlert(i18n("billedQuantityCantBeSuperiorThanCommand"));
  } else {
    if (formVar.validate()) {
      loadContent("../tool/saveBilledWorkCommand.php","resultDivMain","billedWorkCommandForm",true,'billedWorkCommand');
      dijit.byId('dialogBilledWorkCommand').hide();
    } else {
      showAlert(i18n("alertInvalidForm"));
    }
  }
}

function removeWorkCommand(id) {
  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
  actionOK=function() {
    loadContent("../tool/removeWorkCommand.php?idWorkCommand=" + id,"resultDivMain",null,true,'workCommand');
  };
  msg=i18n('confirmRemoveWorkCommand',new Array(id));
  showConfirm(msg,actionOK);
}

function removeBilledWorkCommand(idWorkCommandBilled,idWorkCommand) {
  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
  actionOK=function() {
    loadContent("../tool/removeBilledWorkCommand.php?idWorkCommandBilled=" + idWorkCommandBilled + '&idWorkCommand=' + idWorkCommand,"resultDivMain",null,true,'workCommand');
  };
  msg=i18n('confirmRemoveWorkCommand',new Array(id));
  showConfirm(msg,actionOK);
}

function activityWorkUnitChangeIdWorkUnit() {
  if (dijit.byId('ActivityWorkCommandWorkUnit').get('value') == '' || dijit.byId('ActivityWorkCommandWorkUnit').get('value') == ' ') {
    dijit.byId('ActivityWorkCommandComplexity').set('value','');
    dijit.byId("ActivityWorkCommandComplexity").set('readOnly',true);
    dijit.byId('ActivityBilledWorkCommandWorkCommand').set('value','');
    dijit.byId("ActivityBilledWorkCommandWorkCommand").set('readOnly',true);
  } else {
    dijit.byId("ActivityWorkCommandComplexity").set('readOnly',false);
    if (dijit.byId('ActivityWorkCommandComplexity').get('value') != '') {
      dijit.byId('ActivityWorkCommandComplexity').set('value','');
    }
    refreshListSpecific("idWorkUnit","ActivityWorkCommandComplexity","idWorkUnit",dijit.byId('ActivityWorkCommandWorkUnit').get('value'));
    dijit.byId('ActivityBilledWorkCommandWorkCommand').set('value','');
    dijit.byId("ActivityBilledWorkCommandWorkCommand").set('readOnly',true);
  }
}

function activityWorkUnitChangeIdComplexity() {
  dijit.byId("ActivityWorkCommandAmount").set('value','');
  dijit.byId("ActivityWorkCommandQuantity").set('readOnly',false);
  if (dijit.byId("ActivityBilledWorkCommandWorkCommand")) {
    var idComplexity=dijit.byId("ActivityWorkCommandComplexity").get("value");
    var idWorkUnit=dijit.byId("ActivityWorkCommandWorkUnit").get("value");
    dijit.byId("ActivityBilledWorkCommandWorkCommand").set("value","");
    if (idComplexity != " " && idComplexity != "") {
      refreshListSpecific("idWorkCommand","ActivityBilledWorkCommandWorkCommand","idWorkCommand",idWorkUnit + "separator" + idComplexity + "separator" + dojo.byId("id").value);
      dijit.byId("ActivityBilledWorkCommandWorkCommand").set("readOnly",false);
    } else {
      dijit.byId("ActivityBilledWorkCommandWorkCommand").set("readOnly",true);
    }
  }

}

function activityWorkUnitChangeQuantity() {
  unit=dijit.byId('ActivityWorkCommandQuantity').get('value');
  dojo.xhrGet({
    url:'../tool/getSingleData.php?dataType=workCommand' + '&idWorkUnit=' + dijit.byId('ActivityWorkCommandWorkUnit').get('value') + '&idComplexity='
        + dijit.byId('ActivityWorkCommandComplexity').get('value') + ''+addTokenIndexToUrl(),
    handleAs:"text",
    load:function(data) {
	  datas=data.split('#');
      total=datas[0] * unit;
      dijit.byId('ActivityWorkCommandAmount').set('value',total);
	    if (datas.length>1 && dijit.byId('ActivityWorkCommandAmountLocal')) {
		    totalLocal=datas[1] * unit;
		    dijit.byId('ActivityWorkCommandAmountLocal').set('value',totalLocal);
	    }
    }
  });
}

function workCommandChangeIdWorkUnit() {
  if (dijit.byId('workCommandWorkUnit').get('value') == '' || dijit.byId('workCommandWorkUnit').get('value') == ' ') {
    dijit.byId('workCommandComplexity').set('value','');
    dijit.byId("workCommandComplexity").set('readOnly',true);
  } else {
    dijit.byId("workCommandComplexity").set('readOnly',false);
    if (dijit.byId('workCommandComplexity').get('value') != '') {
      dijit.byId('workCommandComplexity').set('value','');
    }
    refreshListSpecific("idWorkUnit","workCommandComplexity","idWorkUnit",dijit.byId('workCommandWorkUnit').get('value'));
  }
}

function workCommandChangeIdComplexity() {
  dijit.byId("workCommandQuantity").set('value','');
  dijit.byId("workCommandAmount").set('value','');
  if (dijit.byId("workCommandAmountLocal")) dijit.byId("workCommandAmountLocal").set('value','');
  dijit.byId("workCommandQuantity").set('readOnly',false);
  dojo.xhrGet({
    url:'../tool/getSingleData.php?dataType=workCommand' + '&idWorkUnit=' + dijit.byId('workCommandWorkUnit').get('value') + '&idComplexity=' + dijit.byId('workCommandComplexity').get('value')
        + ''+addTokenIndexToUrl(),
    handleAs:"text",
    load:function(data) {
      vals=data.split('#');
      dijit.byId('workCommandUnitAmount').set('value',vals[0]);
      if (dijit.byId('workCommandUnitAmountLocal') && vals.length>1) dijit.byId('workCommandUnitAmountLocal').set('value',vals[1]);
    }
  });
}

//remi #9958
function workCommandParentChangeVerif() {
  var idWkCdP = dijit.byId("workCommandParent").get('value');
  if(idWkCdP==" "){ 
    dijit.byId("workCommandWorkUnit").set('readOnly',false);
    setTimeout("dijit.byId('workCommandComplexity').set('readOnly',false)",100);
    dijit.byId("workCommandWorkUnit").set('value','');
    dijit.byId("workCommandComplexity").set('value','');
  }
  //recover UO and complexity of Parent 
  dojo.xhrGet({
    url:'../tool/getSingleData.php?dataType=workCommandParent' + '&idWorkCommandParent=' + idWkCdP+ ''+addTokenIndexToUrl(),
    handleAs:"text",
    load:function(data) {
      var vals=data.split('#');
      var idwkWorkUnit = vals[0];
      var idwkComplexity = vals[1];
      if(idwkWorkUnit!="" && idwkComplexity!=""){
        //set UO and complexity of Parent for the child item 
        //dijit.byId("workCommandComplexity").set('readOnly',false);
        dijit.byId("workCommandWorkUnit").set('value',idwkWorkUnit);
        dijit.byId("workCommandWorkUnit").set('readOnly',true);
        setTimeout("dijit.byId('workCommandComplexity').set('value',"+idwkComplexity+")", 100);
        setTimeout("dijit.byId('workCommandComplexity').set('readOnly',true)",110);
      }
    }
  });
}

function changeBilledWorkCommand() {
  dijit.byId("billedWorkCommandQuantityBilled").set('readOnly',false);
  dojo.xhrGet({
    url:'../tool/getSingleData.php?dataType=billedWorkCommand' + '&idWorkCommand=' + dijit.byId('billedWorkCommandWorkCommand').get('value') + ''+addTokenIndexToUrl(),
    handleAs:"text",
    load:function(data) {
      arrayData=data.split('#!#!#!#!#!#');
      dijit.byId('billedWorkCommandWorkUnit').set('value',arrayData[0]);
      dijit.byId('billedWorkCommandComplexity').set('value',arrayData[1]);
      dijit.byId('billedWorkCommandUnitAmount').set('value',parseFloat(arrayData[2]));
      dijit.byId('billedWorkCommandCommand').set('value',parseFloat(arrayData[3]));
      dijit.byId('billedWorkCommandDone').set('value',parseFloat(arrayData[4]));
      dijit.byId('billedWorkCommandBilled').set('value',parseFloat(arrayData[5]));
      dijit.byId('billedWorkCommandAccepted').set('value',parseFloat(arrayData[6]));
      if (dijit.byId('billedWorkCommandUnitAmountLocal') && arrayData.length>7) dijit.byId('billedWorkCommandUnitAmountLocal').set('value',parseFloat(arrayData[7]));
    }
  });
}

function billedWorkCommandChangeQuantity(mode,id) {
  var total=dijit.byId('billedWorkCommandUnitAmount').get('value') * dijit.byId('billedWorkCommandQuantityBilled').get('value');
  dijit.byId('billedWorkCommandAmount').set('value',total);
  var totalLocal=(dijit.byId('billedWorkCommandUnitAmountLocal'))?dijit.byId('billedWorkCommandUnitAmountLocal').get('value') * dijit.byId('billedWorkCommandQuantityBilled').get('value'):0;
  if (dijit.byId('billedWorkCommandAmountLocal')) dijit.byId('billedWorkCommandAmountLocal').set('value',totalLocal);

  if (mode == 'add') {
    dojo.xhrGet({
      url:'../tool/getSingleData.php?dataType=billedWorkCommandQuantityAdd' + '&idWorkCommand=' + dijit.byId('billedWorkCommandWorkCommand').get('value') + ''+addTokenIndexToUrl(),
      handleAs:"text",
      load:function(data) {
		var quantity=dijit.byId('billedWorkCommandQuantityBilled').get('value');
		var totalQuantityBilled = (dojo.byId('statusBill').value==1) ? parseInt(data) + quantity: parseInt(data);
		dijit.byId('billedWorkCommandBilled').set('value',totalQuantityBilled);
      }
    });
  } else {
    dojo.xhrGet({
      url:'../tool/getSingleData.php?dataType=billedWorkCommandQuantityEdit'+'&idWorkCommandBill='+id+'&idWorkCommand='+dijit.byId('billedWorkCommandWorkCommand').get('value')+addTokenIndexToUrl(),
      handleAs:"text",
      load:function(data) {
		var quantity=dijit.byId('billedWorkCommandQuantityBilled').get('value');
		var totalQuantityBilled = (dojo.byId('statusBill').value==1) ? parseInt(data) + quantity: '0';
		dijit.byId('billedWorkCommandBilled').set('value',totalQuantityBilled);
      }
    });
  }

}

function workCommandChangeQuantity() {
  var quantity=dijit.byId('workCommandQuantity').get('value');
  var amountUnity=dijit.byId('workCommandUnitAmount').get('value');
  var amountUnityLocal=(dijit.byId('workCommandUnitAmountLocal'))?dijit.byId('workCommandUnitAmountLocal').get('value'):0;
  var amount=quantity * amountUnity;
  var amountLocal=quantity * amountUnityLocal;
  dijit.byId('workCommandAmount').set('value',amount);
  if (dijit.byId('workCommandAmountLocal')) dijit.byId('workCommandAmountLocal').set('value',amountLocal);
}

function addProviderTerm(objectClass,type,idProviderOrder,isLine) {
  var callBack=function() {
    affectationLoad=true;
    dijit.byId("dialogProviderTerm").show();
    setTimeout("affectationLoad=false",500);
  };
  var params="&idProviderOrder=" + idProviderOrder;
  params+="&type=" + type;
  params+="&isLine=" + isLine;
  params+="&mode=add";
  params+="&objectClass=" + objectClass;
  loadDialog('dialogProviderTerm',callBack,false,params);
}

function saveProviderTerm() {
  var formVar=dijit.byId('providerTermForm');
  if (formVar.validate()) {
    loadContent("../tool/saveProviderTerm.php","resultDivMain","providerTermForm",true,'providerTerm');
    dijit.byId('dialogProviderTerm').hide();
  } else {
    showAlert(i18n("alertInvalidForm"));
  }
}

var cancelRecursiveChange_OnGoingChange=false;
function providerTermLine(totalUntaxedAmount) {
  if (cancelRecursiveChange_OnGoingChange) return;
  cancelRecursiveChange_OnGoingChange=true;
  var totalUntaxedAmountValue=totalUntaxedAmount;
  var untaxedAmount=dijit.byId("providerTermUntaxedAmount").get("value");
  if (!untaxedAmount) untaxedAmount=0;
  var taxPct=dijit.byId("providerTermTax").get("value");
  if (!taxPct) taxPct=0;
  var taxAmount=Math.round(untaxedAmount * taxPct) / 100;
  var fullAmount=taxAmount + untaxedAmount;
  var percent=untaxedAmount * 100 / totalUntaxedAmountValue;
  dijit.byId("providerTermPercent").set('value',percent);
  dijit.byId("providerTermTaxAmount").set('value',taxAmount);
  dijit.byId("providerTermFullAmount").set('value',fullAmount);
  setTimeout("cancelRecursiveChange_OnGoingChange = false;",50);
}
function providerTermLineLocal(totalUntaxedAmountLocal, conversionRate) {
  if (cancelRecursiveChange_OnGoingChange) return;
  cancelRecursiveChange_OnGoingChange=true;
  var totalUntaxedAmountValueLocal=totalUntaxedAmountLocal;
  var untaxedAmountLocal=dijit.byId("providerTermUntaxedAmountLocal").get("value");
  if (!untaxedAmountLocal) untaxedAmountLocal=0;
  var taxPct=dijit.byId("providerTermTax").get("value");
  if (!taxPct) taxPct=0;
  var taxAmountLocal=Math.round(untaxedAmountLocal * taxPct) / 100;
  var fullAmountLocal=taxAmountLocal + untaxedAmountLocal;
  var percent=untaxedAmountLocal * 100 / totalUntaxedAmountValueLocal;
  dijit.byId("providerTermPercent").set('value',percent);
  dijit.byId("providerTermTaxAmountLocal").set('value',taxAmountLocal);
  dijit.byId("providerTermFullAmountLocal").set('value',fullAmountLocal);
  if (dojo.byId('conversionRate')) {
    conv=dojo.byId('conversionRate').value;
    dijit.byId("providerTermTaxAmount").set('value',taxAmountLocal*conv);
    dijit.byId("providerTermFullAmount").set('value',fullAmountLocal*conv);
    dijit.byId("providerTermUntaxedAmount").set('value',untaxedAmountLocal*conv);
  }
  setTimeout("cancelRecursiveChange_OnGoingChange = false;",50);
}
function providerTermLinePercent(totalUntaxedAmount,totalUntaxedAmountLocal) {
  if (cancelRecursiveChange_OnGoingChange) return;
  cancelRecursiveChange_OnGoingChange=true;
  var totalUntaxedAmountValue=totalUntaxedAmount;
  var percent=dijit.byId("providerTermPercent").get("value");
  var taxPct=dijit.byId("providerTermTax").get("value");
  if (!taxPct) taxPct=0;
  var untaxedAmount=percent * totalUntaxedAmountValue / 100;
  var taxAmount=Math.round(untaxedAmount * taxPct) / 100;
  var fullAmount=taxAmount + untaxedAmount;
  dijit.byId("providerTermUntaxedAmount").set('value',untaxedAmount);
  dijit.byId("providerTermTaxAmount").set('value',taxAmount);
  dijit.byId("providerTermFullAmount").set('value',fullAmount);
  if (dojo.byId('conversionRate') && dijit.byId("providerTermTaxAmountLocal") && totalUntaxedAmountLocal) {
    var totalUntaxedAmountValueLocal=totalUntaxedAmountLocal;
    var untaxedAmountLocal=percent * totalUntaxedAmountValueLocal / 100;
    var taxAmountLocal=Math.round(untaxedAmountLocal * taxPct) / 100;
    var fullAmountLocal=taxAmountLocal + untaxedAmountLocal;
    dijit.byId("providerTermUntaxedAmountLocal").set('value',untaxedAmountLocal);
    dijit.byId("providerTermTaxAmountLocal").set('value',taxAmountLocal);
    dijit.byId("providerTermFullAmountLocal").set('value',fullAmountLocal);
  }
  setTimeout("cancelRecursiveChange_OnGoingChange = false;",50);
}

function providerTermLineBillLine(id) {
  if (cancelRecursiveChange_OnGoingChange) return;
  cancelRecursiveChange_OnGoingChange=true;
  var totalUntaxedAmountValue=dijit.byId("providerTermBillLineUntaxed" + id).get("value");
  var totalUntaxedAmountValueLocal=(dijit.byId("providerTermBillLineUntaxedLocal" + id))?dijit.byId("providerTermBillLineUntaxedLocal" + id).get("value"):0;
  var untaxedAmount=dijit.byId("providerTermUntaxedAmount" + id).get("value");
  var untaxedAmountLocal=(dijit.byId("providerTermUntaxedAmountLocal" + id))?dijit.byId("providerTermUntaxedAmountLocal" + id).get("value"):0;
  var percent=untaxedAmount * 100 / totalUntaxedAmountValue;
  if (dijit.byId("providerTermUntaxedAmountLocal" + id) && totalUntaxedAmountValueLocal) {
    percent=untaxedAmountLocal * 100 / totalUntaxedAmountValueLocal;
    untaxedAmount=totalUntaxedAmountValue*percent/100;
    dijit.byId("providerTermUntaxedAmount" + id).set('value',untaxedAmount);
  }
  var discount=dijit.byId("providerTermDiscount").get("value");
  if (!untaxedAmount) untaxedAmount=0;
  if (!untaxedAmountLocal) untaxedAmountLocal=0;
  var taxPct=dijit.byId("providerTermTax").get("value");
  if (!taxPct) taxPct=0;
  var discountBill=(untaxedAmount * discount / 100);
  var discountBillLocal=(untaxedAmountLocal * discount / 100);
  var taxAmount=Math.round((untaxedAmount - discountBill) * taxPct) / 100;
  var taxAmountLocal=Math.round((untaxedAmountLocal - discountBillLocal) * taxPct) / 100;
  var fullAmount=untaxedAmount - discountBill + taxAmount;
  var fullAmountLocal=untaxedAmountLocal - discountBillLocal + taxAmountLocal;
  dijit.byId("providerTermDiscountAmount" + id).set('value',discountBill);
  dijit.byId("providerTermPercent" + id).set('value',percent);
  dijit.byId("providerTermTaxAmount" + id).set('value',taxAmount);
  dijit.byId("providerTermFullAmount" + id).set('value',fullAmount);
  if (dijit.byId("providerTermDiscountAmountLocal" + id)) dijit.byId("providerTermDiscountAmountLocal" + id).set('value',discountBillLocal);
  if (dijit.byId("providerTermTaxAmountLocal" + id)) dijit.byId("providerTermTaxAmountLocal" + id).set('value',taxAmountLocal);
  if (dijit.byId("providerTermFullAmounLocalt" + id)) dijit.byId("providerTermFullAmounLocalt" + id).set('value',fullAmountLocal);
  setTimeout("cancelRecursiveChange_OnGoingChange = false;",50);
}

function providerTermLinePercentBilleLine(id) {
  if (cancelRecursiveChange_OnGoingChange) return;
  cancelRecursiveChange_OnGoingChange=true;
  var totalUntaxedAmountValue=dijit.byId("providerTermBillLineUntaxed" + id).get("value");
  var totalUntaxedAmountValueLocal=(dijit.byId("providerTermBillLineUntaxedLocal" + id))?dijit.byId("providerTermBillLineUntaxedLocal" + id).get("value"):0;
  var percent=dijit.byId("providerTermPercent" + id).get("value");
  var taxPct=dijit.byId("providerTermTax").get("value");
  var discount=dijit.byId("providerTermDiscount").get("value");
  var discountLocal=(dijit.byId("providerTermDiscountLocal"))?dijit.byId("providerTermDiscountLocal").get("value"):0;
  if (!taxPct) taxPct=0;
  var untaxedAmount=percent * totalUntaxedAmountValue / 100;
  var untaxedAmountLocal=percent * totalUntaxedAmountValueLocal / 100;
  var discountBill=(untaxedAmount * discount / 100);
  var discountBillLocal=(untaxedAmountLocal * discount / 100);
  var taxAmount=Math.round((untaxedAmount - discountBill) * taxPct) / 100;
  var taxAmountLocal=Math.round((untaxedAmountLocal - discountBillLocal) * taxPct) / 100;
  var fullAmount=untaxedAmount - discountBill + taxAmount;
  var fullAmountLocal=untaxedAmountLocal - discountBillLocal + taxAmountLocal;
  dijit.byId("providerTermUntaxedAmount" + id).set('value',untaxedAmount);
  dijit.byId("providerTermDiscountAmount" + id).set('value',discountBill);
  dijit.byId("providerTermTaxAmount" + id).set('value',taxAmount);
  dijit.byId("providerTermFullAmount" + id).set('value',fullAmount);
  if (dijit.byId("providerTermUntaxedAmountLocal" + id)) dijit.byId("providerTermUntaxedAmountLocal" + id).set('value',untaxedAmountLocal);
  if (dijit.byId("providerTermDiscountAmountLocal" + id)) dijit.byId("providerTermDiscountAmountLocal" + id).set('value',discountBillLocal);
  if (dijit.byId("providerTermTaxAmountLocal" + id)) dijit.byId("providerTermTaxAmountLocal" + id).set('value',taxAmountLocal);
  if (dijit.byId("providerTermTaxAmountLocal" + id)) dijit.byId("providerTermFullAmountLocal" + id).set('value',fullAmountLocal);
  setTimeout("cancelRecursiveChange_OnGoingChange = false;",50);
}

function addProviderTermFromProviderBill() {
  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
  var params="&providerBillId=" + dijit.byId('id').get('value');
  loadDialog('dialogProviderTermFromProviderBill',null,true,params);
}

function saveProviderTermFromProviderBill() {
  var formVar=dijit.byId('providerTermFromProviderBillForm');
  if (formVar.validate() && dojo.byId('linkProviderTerm') && dojo.byId('linkProviderTerm').value) {
    loadContent("../tool/saveProviderTermFromProviderBill.php","resultDivMain","providerTermFromProviderBillForm",true,'ProviderTerm');
    dijit.byId('dialogProviderTermFromProviderBill').hide();
  } else {
    showAlert(i18n("alertInvalidForm"));
  }
}

function providerTermLineChangeNumber() {
  if (!dijit.byId('providerTermNumberOfTerms')) return;
  var number=dijit.byId('providerTermNumberOfTerms').get("value");
  if (!number || number <= 0) return;
  if (number > 1) {
    cancelRecursiveChange_OnGoingChange=true;
    dijit.byId('providerTermUntaxedAmount').set('value',dijit.byId('providerTermOrderUntaxedAmount').get('value') / number);
    dijit.byId('providerTermPercent').set('value',100 / number);
    dijit.byId('providerTermFullAmount').set('value',dijit.byId('providerTermOrderFullAmount').get('value') / number);
    dijit.byId('providerTermTaxAmount').set('value',dijit.byId('providerTermFullAmount').get('value') - dijit.byId('providerTermUntaxedAmount').get('value'));
    lockWidget('providerTermPercent');
    lockWidget('providerTermUntaxedAmount');
    var termDate=dijit.byId('providerTermDate').get('value');
    if (!termDate) {
      dojo.byId('labelRegularTerms').innerHTML='<br/>' + '<span style="color:red">' + i18n('messageMandatory',new Array(i18n('colDate'))) + '</span>';
    } else {
      var termDay=termDate.getDate();
      var lastDayOfMonth=(new Date(termDate.getFullYear(),termDate.getMonth() + 1,0)).getDate();
      if (termDay == lastDayOfMonth) {
        termDay=i18n('colLastDay');
      }
      var startDate=dateFormatter(formatDate(termDate));
      dojo.byId('labelRegularTerms').innerHTML='<br/>' + i18n('labelRegularTerms',new Array(number,termDay,startDate));
    }
    setTimeout("cancelRecursiveChange_OnGoingChange=false;",50);
  } else {
    unlockWidget('providerTermPercent');
    unlockWidget('providerTermUntaxedAmount');
    dojo.byId('labelRegularTerms').innerHTML="";
  }
}
function refreshLinkProviderTerm(selected) {
  var url='../tool/dynamicListLinkProviderTerm.php';
  if (selected) {
    url+='?selected=' + selected;
    if (dojo.byId("ProviderBillId")) {
      url+="&providerBillId=" + dojo.byId("ProviderBillId").value;
    }
    var callback=function() {
      dojo.byId('linkProviderTerm').focus();
    };
    loadDiv(url,'linkProviderTermDiv',null,callback);
  }
}

function addWorkUnit(idCatalogUO) {
  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
  pauseBodyFocus();
  var callBack=function() {
    ckEditorReplaceEditor("WUDescriptions",992);
    ckEditorReplaceEditor("WUIncomings",993);
    ckEditorReplaceEditor("WULivrables",994);
    dijit.byId("dialogWorkUnit").show();
  };
  var params="&idCatalog=" + idCatalogUO;
  params+="&mode=add";
  loadDialog('dialogWorkUnit',callBack,false,params);
}

function removeWorkUnit(idWorkUnit) {
  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
  actionOK=function() {
    loadContent("../tool/removeWorkUnit.php?idWorkUnit=" + idWorkUnit,"resultDivMain",null,true,'affectation');
  };
  msg=i18n('confirmDeleteWorkUnit',new Array(id,i18n('WorkUnit'),idWorkUnit));
  showConfirm(msg,actionOK);
}

function addWorkUnitCatalogPhase(idCatalogUO) {
  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
  pauseBodyFocus();
  var callBack=function() {
    dijit.byId("dialogWorkUnitCatalogPhase").show();
  };
  var params="&idCatalog=" + idCatalogUO;
  params+="&mode=add";
  loadDialog('dialogWorkUnitCatalogPhase',callBack,false,params);
}

function removeWorkUnitCatalogPhase(idWorkUnit) {
  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
  actionOK=function() {
    loadContent("../tool/removeWorkUnitCatalogPhase.php?idWorkUnit=" + idWorkUnit,"resultDivMain",null,true,'affectation');
  };
  msg=i18n('confirmDeleteWorkUnitCatalogPhase',new Array(id,i18n('WorkUnitCatalogPhase'),idWorkUnit));
  showConfirm(msg,actionOK);
}

function addActivityWorkUnit(id,visibility) {
  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
  var callBack=function() {
    affectationLoad=true;
    dijit.byId("dialogActivityWorkUnit").show();
    setTimeout("affectationLoad=false",500);
  };
  var params="&id=" + id;
  params+="&mode=add";
  params+="&visibility=" + visibility;
  loadDialog('dialogActivityWorkUnit',callBack,false,params);
}

function removeActivityWorkUnit(idWorkUnit) {
  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
  actionOK=function() {
    loadContent("../tool/removeActivityWorkUnit.php?idWorkUnit=" + idWorkUnit,"resultDivMain",null,true,'affectation');
  };
  msg=i18n('confirmDeleteWorkUnit',new Array(id,i18n('WorkUnit'),idWorkUnit));
  showConfirm(msg,actionOK);
}

function saveActivityWorkUnit() {
  if (trim(dijit.byId('ActivityWorkCommandComplexity').get("value")) == "") {
    showAlert(i18n("ActivityWorkCommandComplexityIsMissing"));
    return;
  }
  var formVar=dijit.byId('activityWorkUnitForm');
  if (formVar.validate()) {
    var idWorkUnit=dijit.byId("ActivityWorkCommandWorkUnit").get("value");
    var today=(new Date()).toISOString().substr(0,10);
    dojo.xhrGet({
      url:'../tool/getSingleData.php?dataType=validityDate&idWorkUnit=' + idWorkUnit + ''+addTokenIndexToUrl(),
      handleAs:"text",
      load:function(data) {
        if (data) {
          if (data < today) {
            actionOK=function() {
              loadContent("../tool/saveActivityWorkUnit.php","resultDivMain","activityWorkUnitForm",true,'workUnit');
              dijit.byId('dialogActivityWorkUnit').hide();
            };
            msg=i18n('errorValidityDate');
            showConfirm(msg,actionOK);
          } else {
            loadContent("../tool/saveActivityWorkUnit.php","resultDivMain","activityWorkUnitForm",true,'workUnit');
            dijit.byId('dialogActivityWorkUnit').hide();
          }
        } else {
          loadContent("../tool/saveActivityWorkUnit.php","resultDivMain","activityWorkUnitForm",true,'workUnit');
          dijit.byId('dialogActivityWorkUnit').hide();
        }
      }
    });
  } else {
    showAlert(i18n("alertInvalidForm"));
  }
}

function saveWorkUnit() {
  editorDescriptions=CKEDITOR.instances['WUDescriptions'];
  editorDescriptions.updateElement();
  editorWUIncomings=CKEDITOR.instances['WUIncomings'];
  editorWUIncomings.updateElement();
  editorWULivrables=CKEDITOR.instances['WULivrables'];
  editorWULivrables.updateElement();
  if (trim(dijit.byId('WUReferences').get("value")) == "") {
    showAlert(i18n("referenceIsMissing"));
    return;
  }
  var formVar=dijit.byId('workUnitForm');
  if (formVar.validate()) {
    loadContent("../tool/saveWorkUnit.php","resultDivMain","workUnitForm",true,'WorkUnit');
    dijit.byId('dialogWorkUnit').hide();
    loadContent("objectDetail.php?refreshComplexitiesValues=true","CatalogUO_unitOfWork",'listForm');
  } else {
    showAlert(i18n("alertInvalidForm"));
  }
}

function saveWorkUnitCatalogPhase() {
  if (trim(dijit.byId('WUCPReferences').get("value")) == "") {
    showAlert(i18n("referenceIsMissing"));
    return;
  }
  var formVar=dijit.byId('WorkUnitCatalogPhaseForm');
  if (formVar.validate()) {
    loadContent("../tool/saveWorkUnitCatalogPhase.php","resultDivMain","WorkUnitCatalogPhaseForm",true,'WorkUnitCatalogPhase');
    dijit.byId('dialogWorkUnitCatalogPhase').hide();
    loadContent("objectDetail.php?refreshComplexitiesValues=true","CatalogUO_unitOfWork",'listForm');
  } else {
    showAlert(i18n("alertInvalidForm"));
  }
}

function editActivityWorkUnit(idActivityWorkUnit,id,visibility) {
  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
  pauseBodyFocus();
  var callBack=function() {
    dijit.byId("dialogActivityWorkUnit").show();
  };
  var params="&id=" + id;
  params+="&idActivityWorkUnit=" + idActivityWorkUnit;
  params+="&mode=edit";
  params+="&visibility=" + visibility;
  loadDialog('dialogActivityWorkUnit',callBack,false,params);
}

function editWorkUnit(id,idCatalogUO,validityDate,idle) {
  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
  pauseBodyFocus();
  var callBack=function() {
    ckEditorReplaceEditor("WUDescriptions",992);
    ckEditorReplaceEditor("WUIncomings",993);
    ckEditorReplaceEditor("WULivrables",994);
    if (validityDate) {
      dijit.byId("ValidityDateWU").set('value',validityDate);
    } else {
      dijit.byId("ValidityDateWU").reset();
    }
    if (idle == 1) {
      dijit.byId("idleWU").set('value',idle);
    } else {
      dijit.byId("idleWU").reset();
    }
    dijit.byId("dialogWorkUnit").show();
  };
  var params="&id=" + id;
  params+="&idCatalog=" + idCatalogUO;
  params+="&mode=edit";
  loadDialog('dialogWorkUnit',callBack,false,params);
}

function editWorkUnitCatalogPhase(id,idCatalogUO) {
  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
  pauseBodyFocus();
  var callBack=function() {
    dijit.byId("dialogWorkUnitCatalogPhase").show();
  };
  var params="&id=" + id;
  params+="&idCatalog=" + idCatalogUO;
  params+="&mode=edit";
  loadDialog('dialogWorkUnitCatalogPhase',callBack,false,params);
}

function moveBudgetFromHierarchicalView(idFrom,idTo) {
  var mode='before';
  dndSourceTableBudget.sync();
  var nodeList=dndSourceTableBudget.getAllNodes();
  for (var i=0;i < nodeList.length;i++) {
    if (nodeList[i].id == idFrom) {
      mode='before';
      break;
    } else if (nodeList[i].id == idTo) {
      mode='after';
      break;
    }
  }
  var url='../tool/moveBudgetFromHierarchicalView.php?idFrom=' + idFrom + '&idTo=' + idTo + '&mode=' + mode + ''+addTokenIndexToUrl();
  dojo.xhrPost({
    url:url,
    handleAs:"text",
    load:function() {
      refreshHierarchicalBudgetList();
    }
  });
}

function addTenderEvaluationCriteria(callForTenderId) {
  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
  var params="&mode=add&callForTenderId=" + callForTenderId;
  loadDialog('dialogCallForTenderCriteria',null,true,params,false);
}

function editTenderEvaluationCriteria(criteriaId) {
  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
  var params="&mode=edit&criteriaId=" + criteriaId;
  loadDialog('dialogCallForTenderCriteria',null,true,params,false);
}

function saveTenderEvaluationCriteria() {
  var formVar=dijit.byId("dialogTenderCriteriaForm");
  if (!formVar) {
    showError(i18n("errorSubmitForm",new Array("n/a","n/a","dialogTenderCriteriaForm")));
    return;
  }
  if (formVar.validate()) {
    loadContent("../tool/saveTenderEvaluationCriteria.php","resultDivMain","dialogTenderCriteriaForm",true,'tenderEvaluationCriteria');
    dijit.byId('dialogCallForTenderCriteria').hide();
  }
}

function removeTenderEvaluationCriteria(criteriaId) {
  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
  actionOK=function() {
    loadContent("../tool/removeTenderEvaluationCriteria.php?criteriaId=" + criteriaId,"resultDivMain",null,true,'tenderEvaluationCriteria');
  };
  msg=i18n('confirmDelete',new Array(i18n('TenderEvaluationCriteria'),criteriaId));
  showConfirm(msg,actionOK);
}

function addTenderSubmission(callForTenderId) {
  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
  var params="&mode=add&callForTenderId=" + callForTenderId;
  loadDialog('dialogCallForTenderSubmission',null,true,params,false);
}

function editTenderSubmission(tenderId) {
  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
  var params="&mode=edit&tenderId=" + tenderId;
  loadDialog('dialogCallForTenderSubmission',null,true,params,false);
}

function saveTenderSubmission() {
  var formVar=dijit.byId("dialogTenderSubmissionForm");
  if (dijit.byId('dialogCallForTenderSubmissionProvider') && !trim(dijit.byId('dialogCallForTenderSubmissionProvider').get("value"))) {
    showAlert(i18n('messageMandatory',new Array(i18n('colIdProvider'))));
    return;
  }
  if (!formVar) {
    showAlert(i18n("errorSubmitForm",new Array("n/a","n/a","dialogTenderSubmissionForm")));
    return;
  }
  if (formVar.validate()) {
    loadContent("../tool/saveTenderSubmission.php","resultDivMain","dialogTenderSubmissionForm",true,'tenderSubmission');
    dijit.byId('dialogCallForTenderSubmission').hide();
  }
}

function removeTenderSubmission(tenderId) {
  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
  actionOK=function() {
    loadContent("../tool/removeTenderSubmission.php?tenderId=" + tenderId,"resultDivMain",null,true,'tenderSubmission');
  };
  msg=i18n('confirmDelete',new Array(i18n('Tender'),tenderId)) + '<br/><b>' + i18n('messageAlerteDeleteTender') + '</b>';
  showConfirm(msg,actionOK);
}

function changeTenderEvaluationValue(index) {
  var value=dijit.byId("tenderEvaluation_" + index).get("value");
  var coef=dojo.byId("tenderCoef_" + index).value;
  var total=value * coef;
  dijit.byId("tenderTotal_" + index).set("value",total);
  var list=dojo.byId('idTenderCriteriaList').value.split(';');
  var sum=0;
  for (var i=0;i < list.length;i++) {
    sum+=dijit.byId('tenderTotal_' + list[i]).get('value');
  }
  dijit.byId("tenderTotal").set("value",sum);
  var newValue=Math.round(sum * dojo.byId('evaluationMaxCriteriaValue').value / dojo.byId('evaluationSumCriteriaValue').value * 100) / 100;
  dijit.byId("evaluationValue").set("value",newValue);
}

function addWorkTokenMarkup(idToken) {
  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
  pauseBodyFocus();
  var callBack=function() {
    dijit.byId("dialogWorkTokenMarkup").show();
  };
  var params="&idToken=" + idToken;
  params+="&mode=add";
  loadDialog('dialogWorkTokenMarkup',null,true,params);
}

function addTokenClientContract(idClientContract,idProject) {
  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
  pauseBodyFocus();
  var callBack=function() {
    dijit.byId("dialogWorkTokenClientContract").show();
  };
  var params="&idClientContract=" + idClientContract + "&idProject=" + idProject;
  params+="&mode=add";
  loadDialog('dialogWorkTokenClientContract',callBack,false,params);
}

function saveWorkTokenMarkup() {
  if (trim(dijit.byId('LabelMarkup').get("value")) == "" || isNaN(dijit.byId('coefValue').get("value"))) {
    if (trim(dijit.byId('LabelMarkup').get("value")) == "") var msg=i18n("messageMandatory",new Array('colLabelMarkup'));
    else var msg=i18n("messageMandatory",new Array(i18n("colCoefValue")));
    showAlert(msg);
    return;
  }
  var formVar=dijit.byId('workTokenMarkupForm');
  if (formVar.validate()) {
    loadContent("../tool/saveWorkTokenMarkup.php","resultDivMain","workTokenMarkupForm",true,'workTokenMarkup');
    dijit.byId('dialogWorkTokenMarkup').hide();
    loadContent("objectDetail.php?refreshWorkTokenMarkup=true","TokenDefinition_treatment",'listForm');
  } else {
    showAlert(i18n("alertInvalidForm"));
  }
}

function saveWorkTokenClientContract() {
  if (isNaN(dijit.byId('quantity').get("value")) || trim(dijit.byId('tokentType').get("value")) == "") {
    if (trim(dijit.byId('tokentType').get("value")) == "") msg=i18n("messageMandatory",new Array('tokentType'));
    else var msg=i18n("messageMandatory",new Array('quantity'));
    showAlert(msg);
    return;
  }
  var formVar=dijit.byId('workTokenClientContractForm');
  if (formVar.validate()) {
    loadContent("../tool/saveWorkTokenClientContract.php","resultDivMain","workTokenClientContractForm",true,'workTokenClientContract');
    dijit.byId('dialogWorkTokenClientContract').hide();
    var callback = function(){
      refreshGrid(true);
    };
    loadContent("objectDetail.php?refreshWorkClientContract=true","ClientContract_WorkTokenClientContract",'listForm', false, null, null, true, callback);
  } else {
    showAlert(i18n("alertInvalidForm"));
  }
}

function removeTokenMarkUp(tokenMarkupId) {
  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
  actionOK=function() {
    loadContent("../tool/saveWorkTokenMarkup.php?mode=delete&idWorkTokenMarkup=" + tokenMarkupId,"resultDivMain",null,true,'workTokenMarkup');
  };
  msg=i18n('confirmDelete',new Array(i18n('TokenMarkup'),tokenMarkupId)) + '<br/><b>';
  showConfirm(msg,actionOK);
}

function removeTokenClientContract(id) {
  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
  actionOK=function() {
    var callback = function(){
      refreshGrid(true);
    };
    loadContent("../tool/saveWorkTokenClientContract.php?mode=delete&idWorkTokenClientContract=" + id,"resultDivMain",null,true,'workTokenClientContract', null, false, callback);
  };
  msg=i18n('confirmDelete',new Array(i18n('WorkTokenClientContract'),id)) + '<br/><b>';
  showConfirm(msg,actionOK);
}

function editTokenMarkUp(tokenMarkupId,used) {
  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
  var params="&mode=edit&idWorkTokenMarkup=" + tokenMarkupId + "&used=" + used;
  loadDialog('dialogWorkTokenMarkup',null,true,params,false);
}

function editTokenClientContract(id,idProject,used) {
  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
  var params="&mode=edit&idWorkTokenClientContract=" + id + "&idProject=" + idProject + "&used=" + used;
  loadDialog('dialogWorkTokenClientContract',null,true,params,false);
}

function changeValueWorkTokenElement(cp) {
  var val=dijit.byId('dispatchWorkValue_' + cp).get('value');

  if (val == 0) {
    dijit.byId("tokenQuantityValue_" + cp).set('value','');
    dijit.byId("tokenQuantityValue_" + cp).set('readOnly',true);
    dijit.byId("tokenQuantityValue_" + cp).set('style','background-color:#F0F0F0');
    dijit.byId("tokenQuantityMarkupValue_" + cp).set('value','');
    dijit.byId("tokenMarkupType_" + cp).set('value','');
    dijit.byId("tokenMarkupType_" + cp).set('readOnly',true);
    dijit.byId("tokenMarkupType_" + cp).set('style','background-color:#F0F0F0');
    dijit.byId("tokenType_" + cp).set('value','');
    dijit.byId("tokenType_" + cp).set('readOnly',true);
    dijit.byId("tokenType_" + cp).set('style','background-color:#F0F0F0');
    if (dijit.byId("billableToken_" + cp).get("checked") == true) {
      dijit.byId("billableToken_" + cp).set("checked",false);
    }
    if (dijit.byId("billableTokenInput_" + cp).get("value") == 1) {
      dijit.byId("billableTokenInput_" + cp).set("value",0);
    }
    if (dijit.byId("billableSiwtched_" + cp).get("value") == "on") {
      dijit.byId("billableSiwtched_" + cp).set("value","off");
    }
  } else {

    if (dijit.byId("tokenQuantityValue_" + cp).get('readOnly') == true) {
      dijit.byId("tokenQuantityValue_" + cp).set('readOnly',false);
      dijit.byId("tokenQuantityValue_" + cp).set('style','background-color:unset');
    }
    if (dijit.byId("tokenMarkupType_" + cp).get('readOnly') == true) {
      dijit.byId("tokenMarkupType_" + cp).set('readOnly',false);
      dijit.byId("tokenMarkupType_" + cp).set('style','background-color:unset');
    }
    if (dijit.byId("tokenType_" + cp).get('readOnly') == true) {
      dijit.byId("tokenType_" + cp).set('readOnly',false);
      dijit.byId("tokenType_" + cp).set('style','background-color:unset');
    }

  }
}

function dispatchSetTokenTypeEvents(index) {
  var val=(dijit.byId('tokenType_' + index).get('value') != "") ? dijit.byId('tokenType_' + index).get('value') : 0;
  refreshListSpecific('idWorkTokenMarkup','tokenMarkupType_' + index,'idWorkTokenCC',val);
  if (val == "") {
    dijit.byId("tokenQuantityValue_" + index).set('value','');
    dijit.byId("tokenQuantityValue_" + index).set('readOnly',true);
    dijit.byId("tokenQuantityValue_" + index).set('style','background-color:#F0F0F0');
    dijit.byId("tokenQuantityMarkupValue_" + index).set('value','');
    dijit.byId("tokenMarkupType_" + index).set('value','');
  } else {
    if (dijit.byId("tokenQuantityValue_" + index).get('readOnly') == true) {
      dijit.byId("tokenQuantityValue_" + index).set('readOnly',false);
      dijit.byId("tokenQuantityValue_" + index).set('style','background-color:unset');
    }
    dijit.byId("tokenQuantityMarkupValue_" + index).set('value',dijit.byId("tokenQuantityValue_" + index).get('value'));
    dijit.byId("tokenMarkupType_" + index).set('value','');
  }
  isplitStr=dojo.byId('lstTokenDefSplittable').value;
  isplit=isplitStr.split(',');
  if (isplit.indexOf(val) != -1) {
    quantity=dijit.byId('tokenQuantityValue_' + index).get('value');
    dijit.byId('tokenQuantityValue_' + index).set("constraints",{
      min:0,
      places:'0,2'
    });
    dijit.byId('tokenQuantityValue_' + index).set('value',quantity);
  } else {
    dijit.byId('tokenQuantityValue_' + index).set("constraints",{
      min:0,
      places:'0'
    });
  }

}

function dispatchTokenMarkupTypeEvents(index) {
  if (dijit.byId('tokenMarkupType_' + index) == undefined) return;
  var val=dijit.byId('tokenMarkupType_' + index).get('value');
  if (val == "") {
    var val=dijit.byId("tokenQuantityValue_" + index).get('value');
    dijit.byId("tokenQuantityMarkupValue_" + index).set('value',val);
  } else {
    var coef=val.substr(val.indexOf('_') + 1);
    if (isNaN(coef)) coef=1;
    var value=dijit.byId("tokenQuantityValue_" + index).get('value') * coef;
    dijit.byId("tokenQuantityMarkupValue_" + index).set('value',dojo.number.format(value));
  }
  updateDispatchWorkTotal("tokenQuantityMarkupValue_","quantityMarkupTotal");
}

function dispatchTokenQuantityValueEvents(index) {
  var tokenMakupType=dijit.byId("tokenMarkupType_" + index).get('value');
  if (tokenMakupType == "" || tokenMakupType == 0) {
    dijit.byId("tokenQuantityMarkupValue_" + index).set('value',dijit.byId('tokenQuantityValue_' + index).get('value'));
    dijit.byId("tokenMarkupType_" + index).set('value','');
  } else {
    var coef=(tokenMakupType != '') ? tokenMakupType.substr(tokenMakupType.indexOf('_') + 1) : 1;
    if (isNaN(coef)) coef=1;
    var newVal=dijit.byId('tokenQuantityValue_' + index).get('value') * coef;
    dijit.byId("tokenQuantityMarkupValue_" + index).set('value',newVal);
  }
  updateDispatchWorkTotal("tokenQuantityValue_","quantityTotal");
  updateDispatchWorkTotal("tokenQuantityMarkupValue_","quantityMarkupTotal");
}

function updateCommandTotal() {
  if (cancelRecursiveChange_OnGoingChange) return;
  cancelRecursiveChange_OnGoingChange=true;
  // Retrieve values used for calculation
  var untaxedAmount=dijit.byId("untaxedAmount").get("value");
  if (!untaxedAmount) untaxedAmount=0;
  var untaxedAmountLocal=(dijit.byId("untaxedAmountLocal"))?dijit.byId("untaxedAmountLocal").get("value"):0;
  if (!untaxedAmountLocal) untaxedAmountLocal=0;
  var taxPct=dijit.byId("taxPct").get("value");
  if (!taxPct) taxPct=0;
  var addUntaxedAmount=dijit.byId("addUntaxedAmount").get("value");
  if (!addUntaxedAmount) addUntaxedAmount=0;
  var addUntaxedAmountLocal=(dijit.byId("addUntaxedAmountLocal"))?dijit.byId("addUntaxedAmountLocal").get("value"):0;
  if (!addUntaxedAmountLocal) addUntaxedAmountLocal=0;
  var initialWork=dijit.byId("initialWork").get("value");
  var addWork=dijit.byId("addWork").get("value");
  var initialWorkLocal=(dijit.byId("initialWorkLocal"))?dijit.byId("initialWorkLocal").get("value"):initialWork;
  var addWorkLocal=(dijit.byId("addWorkLocal"))?dijit.byId("addWorkLocal").get("value"):addWork;
  // Calculated values
  var taxAmount=Math.round(untaxedAmount * taxPct) / 100;
  var fullAmount=taxAmount + untaxedAmount;
  var addTaxAmount=Math.round(addUntaxedAmount * taxPct) / 100;
  var addFullAmount=addTaxAmount + addUntaxedAmount;
  var totalUntaxedAmount=untaxedAmount + addUntaxedAmount;
  var totalTaxAmount=taxAmount + addTaxAmount;
  var totalFullAmount=fullAmount + addFullAmount;
  var validatedWork=initialWork + addWork;
  var validatedWorkLocal=initialWorkLocal + addWorkLocal;
  var taxAmountLocal=Math.round(untaxedAmountLocal * taxPct) / 100;
  var fullAmountLocal=taxAmountLocal + untaxedAmountLocal;
  var addTaxAmountLocal=Math.round(addUntaxedAmountLocal * taxPct) / 100;
  var addFullAmountLocal=addTaxAmountLocal + addUntaxedAmountLocal;
  var totalUntaxedAmountLocal=untaxedAmountLocal + addUntaxedAmountLocal;
  var totalTaxAmountLocal=taxAmountLocal + addTaxAmountLocal;
  var totalFullAmountLocal=fullAmountLocal + addFullAmountLocal;
  // Set values to fields
  dijit.byId("taxAmount").set('value',taxAmount);
  dijit.byId("fullAmount").set('value',fullAmount);
  dijit.byId("addTaxAmount").set('value',addTaxAmount);
  dijit.byId("addFullAmount").set('value',addFullAmount);
  dijit.byId("totalUntaxedAmount").set('value',totalUntaxedAmount);
  dijit.byId("totalTaxAmount").set('value',totalTaxAmount);
  dijit.byId("totalFullAmount").set('value',totalFullAmount);
  dijit.byId("validatedWork").set('value',validatedWork);
  if (dijit.byId("validatedWorkLocal")) dijit.byId("validatedWorkLocal").set('value',validatedWorkLocal);
  if (dijit.byId("taxAmountLocal")) dijit.byId("taxAmountLocal").set('value',taxAmountLocal);
  if (dijit.byId("fullAmountLocal")) dijit.byId("fullAmountLocal").set('value',fullAmountLocal);
  if (dijit.byId("addTaxAmountLocal")) dijit.byId("addTaxAmountLocal").set('value',addTaxAmountLocal);
  if (dijit.byId("addFullAmountLocal")) dijit.byId("addFullAmountLocal").set('value',addFullAmountLocal);
  if (dijit.byId("totalUntaxedAmountLocal")) dijit.byId("totalUntaxedAmountLocal").set('value',totalUntaxedAmountLocal);
  if (dijit.byId("totalTaxAmountLocal")) dijit.byId("totalTaxAmountLocal").set('value',totalTaxAmountLocal);
  if (dijit.byId("totalFullAmountLocal")) dijit.byId("totalFullAmountLocal").set('value',totalFullAmountLocal);
  cancelRecursiveChange_OnGoingChange=false;
}

function updateCommandTotalTTC() {
  if (cancelRecursiveChange_OnGoingChange) return;
  cancelRecursiveChange_OnGoingChange=true;
  // Retrieve values used for calculation
  var fullAmount=dijit.byId("fullAmount").get("value");
  if (!fullAmount) fullAmount=0;
  var fullAmountLocal=(dijit.byId("fullAmountLocal"))?dijit.byId("fullAmountLocal").get("value"):0;
  if (!fullAmountLocal) fullAmountLocal=0;
  var taxPct=dijit.byId("taxPct").get("value");
  if (!taxPct) taxPct=0;
  var addFullAmount=dijit.byId("addFullAmount").get("value");
  if (!addFullAmount) addFullAmount=0;
  var addFullAmountLocal=(dijit.byId("addFullAmountLocal"))?dijit.byId("addFullAmountLocal").get("value"):0;
  if (!addFullAmountLocal) addFullAmountLocal=0;
  var initialWork=dijit.byId("initialWork").get("value");
  var addWork=dijit.byId("addWork").get("value");
  var initialWorkLocal=(dijit.byId("initialWorkLocal"))?dijit.byId("initialWorkLocal").get("value"):initialWork;
  var addWorkLocal=(dijit.byId("addWorkLocal"))?dijit.byId("addWorkLocal").get("value"):addWork;
  // Calculated values
  var untaxedAmount=Math.round(fullAmount / (1 + (taxPct / 100)));
  var taxAmount=fullAmount - untaxedAmount;
  var addUntaxedAmount=Math.round(addFullAmount / (1 + (taxPct / 100)));
  var addTaxAmount=addFullAmount - addUntaxedAmount;
  var totalUntaxedAmount=untaxedAmount + addUntaxedAmount;
  var totalTaxAmount=taxAmount + addTaxAmount;
  var totalFullAmount=fullAmount + addFullAmount;
  var untaxedAmountLocal=Math.round(fullAmountLocal / (1 + (taxPct / 100)));
  var taxAmountLocal=fullAmountLocal - untaxedAmountLocal;
  var addUntaxedAmountLocal=Math.round(addFullAmountLocal / (1 + (taxPct / 100)));
  var addTaxAmountLocal=addFullAmountLocal - addUntaxedAmountLocal;
  var totalUntaxedAmountLocal=untaxedAmountLocal + addUntaxedAmountLocal;
  var totalTaxAmountLocal=taxAmountLocal + addTaxAmountLocal;
  var totalFullAmountLocal=fullAmountLocal + addFullAmountLocal;
  var validatedWork=initialWork + addWork;
  var validatedWorkLocal=initialWorkLocal + addWorkLocal;
  // Set values to fields
  dijit.byId("taxAmount").set('value',taxAmount);
  dijit.byId("untaxedAmount").set('value',untaxedAmount);
  dijit.byId("addTaxAmount").set('value',addTaxAmount);
  dijit.byId("addUntaxedAmount").set('value',addUntaxedAmount);
  dijit.byId("totalUntaxedAmount").set('value',totalUntaxedAmount);
  dijit.byId("totalTaxAmount").set('value',totalTaxAmount);
  dijit.byId("totalFullAmount").set('value',totalFullAmount);
  dijit.byId("validatedWork").set('value',validatedWork);
  if (dijit.byId("validatedWorkLocal")) dijit.byId("validatedWorkLocal").set('value',validatedWorkLocal);
  if (dijit.byId("taxAmountLocal")) dijit.byId("taxAmountLocal").set('value',taxAmountLocal);
  if (dijit.byId("untaxedAmountLocal")) dijit.byId("untaxedAmountLocal").set('value',untaxedAmountLocal);
  if (dijit.byId("addTaxAmountLocal")) dijit.byId("addTaxAmountLocal").set('value',addTaxAmountLocal);
  if (dijit.byId("addUntaxedAmountLocal")) dijit.byId("addUntaxedAmountLocal").set('value',addUntaxedAmountLocal);
  if (dijit.byId("totalUntaxedAmountLocal")) dijit.byId("totalUntaxedAmountLocal").set('value',totalUntaxedAmountLocal);
  if (dijit.byId("totalTaxAmountLocal")) dijit.byId("totalTaxAmountLocal").set('value',totalTaxAmountLocal);
  if (dijit.byId("totalFullAmountLocal")) dijit.byId("totalFullAmountLocal").set('value',totalFullAmountLocal);
  cancelRecursiveChange_OnGoingChange=false;
}

// gautier
function providerPaymentIdProviderBill() {
  var idBill=dijit.byId("idProviderBill").get("value");
  url='../tool/getSingleData.php?dataType=providerPayment&idBill=' + idBill;
  dojo.xhrGet({
    url:url+addTokenIndexToUrl(url),
    handleAs:"text",
    load:function(data) {
      if (data) {
        datas=data.split('#');
        dijit.byId("paymentAmount").set("value",dojo.number.format(datas[0]));
        if (dijit.byId("paymentAmountLocal") && datas.length>1) dijit.byId("paymentAmountLocal").set("value",dojo.number.format(datas[1]));
      }
    }
  });
}
function providerPaymentIdProviderTerm() {
  var idTerm=dijit.byId("idProviderTerm").get("value");
  url='../tool/getSingleData.php?dataType=providerPayment&idTerm=' + idTerm;
  dojo.xhrGet({
    url:url+addTokenIndexToUrl(url),
    handleAs:"text",
    load:function(data) {
      if (data) {
        datas=data.split('#');
        dijit.byId("paymentAmount").set("value",dojo.number.format(datas[0]));
        if (dijit.byId("paymentAmountLocal") && datas.length>1) dijit.byId("paymentAmountLocal").set("value",dojo.number.format(datas[1]));
      }
    }
  });
}
function updateComplexities(number,idCatalog,parameterNumber) {
  url="../tool/removeWorkUnit.php?number=" + number + "&idCatalog=" + idCatalog;
  var notRefresh=false;
  dojo.xhrGet({
    url:url+addTokenIndexToUrl(),
    handleAs:"text",
    load:function(data) {
      if (data) {
        showAlert(i18n("cantDeleteUsingUOComplexity"));
        notRefresh=true;
        dijit.byId("numberComplexities").set("value",dojo.number.format(data));
      }
      var numberComplexities=dijit.byId("numberComplexities").get("value");
      if (numberComplexities > 0 && numberComplexities < parameterNumber + 1 && notRefresh == false) {
        loadContent("objectDetail.php?refreshComplexities=true&nb=" + numberComplexities,"drawComplexity",'listForm');
        loadContent("objectDetail.php?refreshComplexitiesValues=true","CatalogUO_unitOfWork",'listForm');
      }
      if (numberComplexities > parameterNumber && notRefresh == false) {
        showAlert(i18n("complexityCantBeSuperiorThan",new Array('' + parameterNumber)));
        dijit.byId("numberComplexities").set("value",dojo.number.format(parameterNumber));
      }
    }
  });
}

function updateFinancialTotal(mode,col) {
  if (cancelRecursiveChange_OnGoingChange) {
    return;
  }
  cancelRecursiveChange_OnGoingChange=true;
  if (mode == 'HT') {
    // Retrieve values used for calculation
    var untaxedAmount=dijit.byId("untaxedAmount").get("value");
    var fullAmount=dijit.byId("fullAmount").get("value");
    if (!untaxedAmount) untaxedAmount=0;
    var taxPct=dijit.byId("taxPct").get("value");
    if (!taxPct) taxPct=0;
    var discount=dijit.byId("discountAmount").get("value");
    var discountRate=dijit.byId("discountRate").get("value");
    var untaxedAmountLocal=(dijit.byId("untaxedAmountLocal"))?dijit.byId("untaxedAmountLocal").get("value"):0;
    var fullAmountLocal=(dijit.byId("fullAmountLocal"))?dijit.byId("fullAmountLocal").get("value"):0;
    if (!untaxedAmountLocal) untaxedAmountLocal=0;
    var taxPctLocal=(dijit.byId("taxPctLocal"))?dijit.byId("taxPctLocal").get("value"):0;
    if (!taxPctLocal) taxPctLocal=0;
    var discountLocal=(dijit.byId("discountAmountLocal"))?dijit.byId("discountAmountLocal").get("value"):0;
    var discountRateLocal=(dijit.byId("discountRateLocal"))?dijit.byId("discountRateLocal").get("value"):0;
    if (!isNaN(discount) && (!dijit.byId('discountFrom') || dijit.byId('discountFrom').get('value') == 'amount')) {
      if (col != 'discountRate' && col != 'discountRateLocal') {
        discountRate=Math.round(10000 * discount / untaxedAmount) / 100;
        dijit.byId("discountRate").set("value",discountRate);
        discountRateLocal=Math.round(10000 * discountLocal / untaxedAmountLocal) / 100;
        if (dijit.byId("discountRateLocal")) dijit.byId("discountRateLocal").set("value",discountRateLocal);
      }
    } else if (!isNaN(discountRate) && !isNaN(discountRateLocal)) {
      if (col != 'discountAmount' && col != 'discountAmountLocal') {
        discount=Math.round(discountRate * untaxedAmount) / 100;
        dijit.byId("discountAmount").set("value",discount);
        discountLocal=Math.round(discountRateLocal * untaxedAmountLocal) / 100;
        if (dijit.byId("discountAmountLocal")) dijit.byId("discountAmountLocal").set("value",discountLocal);
      }
    }
    if (!discount) discount=0;
    if (!discountLocal) discountLocal=0;
    // Calculated values
    var taxAmount=Math.round(untaxedAmount * taxPct) / 100;
    var fullAmount=taxAmount + untaxedAmount;
    var totalUntaxedAmount=untaxedAmount - discount;
    var totalTaxAmount=Math.round(totalUntaxedAmount * taxPct) / 100;
    var totalFullAmount=totalUntaxedAmount + totalTaxAmount;
    var discountFull=fullAmount - totalFullAmount;
    var taxAmountLocal=Math.round(untaxedAmountLocal * taxPctLocal) / 100;
    var fullAmountLocal=taxAmountLocal + untaxedAmountLocal;
    var totalUntaxedAmountLocal=untaxedAmountLocal - discountLocal;
    var totalTaxAmountLocal=Math.round(totalUntaxedAmountLocal * taxPctLocal) / 100;
    var totalFullAmountLocal=totalUntaxedAmountLocal + totalTaxAmountLocal;
    var discountFullLocal=fullAmountLocal - totalFullAmountLocal;
    // Set values to fields
    dijit.byId("taxAmount").set('value',taxAmount);
    dijit.byId("fullAmount").set('value',fullAmount);
    dijit.byId("totalUntaxedAmount").set('value',totalUntaxedAmount);
    dijit.byId("totalTaxAmount").set('value',totalTaxAmount);
    dijit.byId("totalFullAmount").set('value',totalFullAmount);
    dijit.byId("discountFullAmount").set("value",discountFull);
    if (dijit.byId("taxAmountLocal")) dijit.byId("taxAmountLocal").set('value',taxAmountLocal);
    if (dijit.byId("fullAmountLocal")) dijit.byId("fullAmountLocal").set('value',fullAmountLocal);
    if (dijit.byId("totalUntaxedAmountLocal")) dijit.byId("totalUntaxedAmountLocal").set('value',totalUntaxedAmountLocal);
    if (dijit.byId("totalTaxAmountLocal")) dijit.byId("totalTaxAmountLocal").set('value',totalTaxAmountLocal);
    if (dijit.byId("totalFullAmountLocal")) dijit.byId("totalFullAmountLocal").set('value',totalFullAmountLocal);
    if (dijit.byId("discountFullAmountLocal")) dijit.byId("discountFullAmountLocal").set("value",discountFullLocal);
  } else { // TTC
    var fullAmount=dijit.byId("fullAmount").get("value");
    var untaxedAmount=dijit.byId("untaxedAmount").get("value");
    if (!fullAmount) fullAmount=0;
    var taxPct=dijit.byId("taxPct").get("value");
    if (!taxPct) taxPct=0;
    var discountFull=dijit.byId("discountFullAmount").get("value");
    var discountRate=dijit.byId("discountRate").get("value");
    var fullAmountLocal=dijit.byId("fullAmountLocal").get("value");
    var untaxedAmountLocal=dijit.byId("untaxedAmountLocal").get("value");
    if (!fullAmountLocal) fullAmountLocal=0;
    var taxPctLocal=dijit.byId("taxPctLocal").get("value");
    if (!taxPctLocal) taxPctLocal=0;
    var discountFullLocal=dijit.byId("discountFullAmountLocal").get("value");
    var discountRateLocal=dijit.byId("discountRateLocal").get("value");
    if (!isNaN(discountFull) && !isNaN(discountFullLocal) && (!dijit.byId('discountFrom') || dijit.byId('discountFrom').get('value') == 'amount')) {
      if (col != 'discountRate' && col != 'discountRateLocal') {
        discountRate=Math.round(10000 * discountFull / fullAmount) / 100;
        dijit.byId("discountRate").set("value",discountRate);
        discountRateLocal=Math.round(10000 * discountFullLocal / fullAmountLocal) / 100;
        if (dijit.byId("discountRateLocal")) dijit.byId("discountRateLocal").set("value",discountRateLocal);      
      }
    } else if (!isNaN(discountRate) && !isNaN(discountRateLocal)) {
      if (col != 'discountFullAmount') {
        discountFull=Math.round(discountRate * fullAmount) / 100;
        dijit.byId("discountFullAmount").set("value",discountFull);
        discountFullLocal=Math.round(discountRateLocal * fullAmountLocal) / 100;
        if (dijit.byId("discountFullAmountLocal")) dijit.byId("discountFullAmountLocal").set("value",discountFullLocal);      
      }
    }
    if (!discountFull) discountFull=0;
    if (!discountFullLocal) discountFullLocal=0;
    // Calculated values
    var untaxedAmount=Math.round(fullAmount / (1 + (taxPct / 100)) * 100) / 100;
    var taxAmount=fullAmount - untaxedAmount;
    var totalFullAmount=fullAmount - discountFull;
    var totalUntaxedAmount=Math.round(totalFullAmount / (1 + (taxPct / 100)) * 100) / 100;
    var totalTaxAmount=totalFullAmount - totalUntaxedAmount;
    var discount=untaxedAmount - totalUntaxedAmount;
    var untaxedAmountLocal=Math.round(fullAmountLocal / (1 + (taxPctLocal / 100)) * 100) / 100;
    var taxAmountLocal=fullAmountLocal - untaxedAmountLocal;
    var totalFullAmountLocal=fullAmountLocal - discountFullLocal;
    var totalUntaxedAmountLocal=Math.round(totalFullAmountLocal / (1 + (taxPctLocal / 100)) * 100) / 100;
    var totalTaxAmountLocal=totalFullAmountLocal - totalUntaxedAmountLocal;
    var discountLocal=untaxedAmountLocal - totalUntaxedAmountLocal;
    // Set values to fields
    dijit.byId("taxAmount").set('value',taxAmount);
    dijit.byId("untaxedAmount").set('value',untaxedAmount);
    dijit.byId("totalUntaxedAmount").set('value',totalUntaxedAmount);
    dijit.byId("totalTaxAmount").set('value',totalTaxAmount);
    dijit.byId("totalFullAmount").set('value',totalFullAmount);
    dijit.byId("discountAmount").set("value",discount);
    if (dijit.byId("taxAmountLocal")) dijit.byId("taxAmountLocal").set('value',taxAmountLocal);
    if (dijit.byId("untaxedAmountLocal")) dijit.byId("untaxedAmountLocal").set('value',untaxedAmountLocal);
    if (dijit.byId("totalUntaxedAmountLocal")) dijit.byId("totalUntaxedAmountLocal").set('value',totalUntaxedAmountLocal);
    if (dijit.byId("totalTaxAmountLocal")) dijit.byId("totalTaxAmountLocal").set('value',totalTaxAmountLocal);
    if (dijit.byId("totalFullAmountLocal")) dijit.byId("totalFullAmountLocal").set('value',totalFullAmountLocal);
    if (dijit.byId("discountAmountLocal")) dijit.byId("discountAmountLocal").set("value",discountLocal);
  }
  setTimeout("cancelRecursiveChange_OnGoingChange = false;",5);
}
// end
function updateBillTotal() { // Also used for Quotation !!!
  if (cancelRecursiveChange_OnGoingChange) return;
  cancelRecursiveChange_OnGoingChange=true;
  // Retrieve values used for calculation
  var untaxedAmount=dijit.byId("untaxedAmount").get("value");
  var untaxedAmountLocal=(dijit.byId("untaxedAmountLocal"))?dijit.byId("untaxedAmountLocal").get("value"):0;
  if (!untaxedAmount) untaxedAmount=0;
  if (!untaxedAmountLocal) untaxedAmountLocal=0;
  var taxPct=dijit.byId("taxPct").get("value");
  if (!taxPct) taxPct=0;
  // Calculated values
  var taxAmount=Math.round(untaxedAmount * taxPct) / 100;
  var taxAmountLocal=Math.round(untaxedAmountLocal * taxPct) / 100;
  var fullAmount=taxAmount + untaxedAmount;
  var fullAmountLocal=taxAmountLocal + untaxedAmountLocal;
  // Set values to fields
  dijit.byId("taxAmount").set('value',taxAmount);
  if (dijit.byId("taxAmountLocal")) dijit.byId("taxAmountLocal").set('value',taxAmountLocal);
  dijit.byId("fullAmount").set('value',fullAmount);
  if (dijit.byId("fullAmountLocal")) dijit.byId("fullAmountLocal").set('value',fullAmountLocal);
  cancelRecursiveChange_OnGoingChange=false;
}

function updateBillTotalTTC() { // Also used for Quotation !!!
  if (cancelRecursiveChange_OnGoingChange) return;
  cancelRecursiveChange_OnGoingChange=true;
  // Retrieve values used for calculation
  var fullAmount=dijit.byId("fullAmount").get("value");
  var fullAmountLocal=(dijit.byId("fullAmountLocal"))?dijit.byId("fullAmountLocal").get("value"):0;
  if (!fullAmount) fullAmount=0;
  if (!fullAmountLocal) fullAmountLocal=0;
  var taxPct=dijit.byId("taxPct").get("value");
  if (!taxPct) taxPct=0;
  // Calculated values
  var untaxedAmount=Math.round(fullAmount / (1 + (taxPct / 100)));
  var untaxedAmountLocal=Math.round(fullAmountLocal / (1 + (taxPct / 100)));
  var taxAmount=fullAmount - untaxedAmount;
  var taxAmountLocal=fullAmountLocal - untaxedAmountLocal;
  // Set values to fields
  dijit.byId("taxAmount").set('value',taxAmount);
  if (dijit.byId("taxAmountLocal")) dijit.byId("taxAmountLocal").set('value',taxAmountLocal);
  dijit.byId("untaxedAmount").set('value',untaxedAmount);
  if (dijit.byId("untaxedAmountLocal")) dijit.byId("untaxedAmountLocal").set('value',untaxedAmountLocal);

  cancelRecursiveChange_OnGoingChange=false;
}

function editAcceptedWorkCommand(idAcceptance,id,idWorkCommand,quantity) {
  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
  pauseBodyFocus();
  var callBack=function() {
    dijit.byId("dialogAcceptedWorkCommand").show();
  };
  var params="&id=" + id;
  params+="&idAcceptance=" + idAcceptance;
  params+="&idWorkCommand=" + idWorkCommand;
  params+="&quantity=" + quantity;
  params+="&mode=edit";
  loadDialog('dialogAcceptedWorkCommand',callBack,false,params);
}

function addAcceptedWorkCommand(id) {
  var callBack=function() {
    affectationLoad=true;
    dijit.byId("dialogAcceptedWorkCommand").show();
    setTimeout("affectationLoad=false",500);
  };
  var params="&idAcceptance=" + id;
  params+="&mode=add";
  loadDialog('dialogAcceptedWorkCommand',callBack,false,params);
}

function saveAcceptedWorkCommand() {
  var formVar=dijit.byId('acceptedWorkCommandForm');
  if (dijit.byId('acceptedWorkCommandAccepted').get('value') > dijit.byId('acceptedWorkCommandCommand').get('value')) {
    showAlert(i18n("acceptedQuantityCantBeSuperiorThanCommand"));
  } else {
    if (formVar.validate()) {
      loadContent("../tool/saveAcceptedWorkCommand.php","resultDivMain","acceptedWorkCommandForm",true,'acceptedWorkCommand');
      dijit.byId('dialogAcceptedWorkCommand').hide();
    } else {
      showAlert(i18n("alertInvalidForm"));
    }
  }
}

function removeAcceptedWorkCommand(idWorkCommandAccepted,idWorkCommand) {
  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
  actionOK=function() {
    loadContent("../tool/removeAcceptedWorkCommand.php?idWorkCommandAccepted=" + idWorkCommandAccepted + '&idWorkCommand=' + idWorkCommand,"resultDivMain",null,true,'workCommand');
  };
  msg=i18n('confirmRemoveWorkCommand',new Array(id));
  showConfirm(msg,actionOK);
}

function changeAcceptedWorkCommand() {
  dijit.byId("acceptedWorkCommandQuantityAccepted").set('readOnly',false);
  dojo.xhrGet({
    url:'../tool/getSingleData.php?dataType=acceptedWorkCommand' + '&idWorkCommand=' + dijit.byId('acceptedWorkCommandWorkCommand').get('value') + ''+addTokenIndexToUrl(),
    handleAs:"text",
    load:function(data) {
      arrayData=data.split('#!#!#!#!#!#');
      dijit.byId('acceptedWorkCommandWorkUnit').set('value',arrayData[0]);
      dijit.byId('acceptedWorkCommandComplexity').set('value',arrayData[1]);
      dijit.byId('acceptedWorkCommandUnitAmount').set('value',parseFloat(arrayData[2]));
      dijit.byId('acceptedWorkCommandCommand').set('value',parseFloat(arrayData[3]));
      dijit.byId('acceptedWorkCommandDone').set('value',parseFloat(arrayData[4]));
      dijit.byId('acceptedWorkCommandBilled').set('value',parseFloat(arrayData[5]));
      dijit.byId('acceptedWorkCommandAccepted').set('value',parseFloat(arrayData[6]));
      if (dijit.byId('acceptedWorkCommandUnitAmountLocal') && arrayData.length>7) dijit.byId('acceptedWorkCommandUnitAmountLocal').set('value',parseFloat(arrayData[7]));
    }
  });
}

function acceptedWorkCommandChangeQuantity(mode,id) {
  var total=dijit.byId('acceptedWorkCommandUnitAmount').get('value') * dijit.byId('acceptedWorkCommandQuantityAccepted').get('value');
  dijit.byId('acceptedWorkCommandAmount').set('value',total);
  var totalLocal=(dijit.byId('acceptedWorkCommandUnitAmountLocal'))?dijit.byId('acceptedWorkCommandUnitAmountLocal').get('value') * dijit.byId('acceptedWorkCommandQuantityAccepted').get('value'):0;
  if (dijit.byId('acceptedWorkCommandAmountLocal')) dijit.byId('acceptedWorkCommandAmountLocal').set('value',totalLocal);
  return; // PBER : no dynamic update needed 
  
  if (mode == 'add') {
    dojo.xhrGet({
      url:'../tool/getSingleData.php?dataType=acceptedWorkCommandQuantityAdd' + '&idWorkCommand=' + dijit.byId('acceptedWorkCommandWorkCommand').get('value') + ''+addTokenIndexToUrl(),
      handleAs:"text",
      load:function(data) {
        var quantity=dijit.byId('acceptedWorkCommandQuantityAccepted').get('value');
        var totalQuantityAccepted=parseInt(data) + quantity;
        dijit.byId('acceptedWorkCommandAccepted').set('value',totalQuantityAccepted);
      }
    });
  } else {
    dojo.xhrGet({
      url:'../tool/getSingleData.php?dataType=acceptedWorkCommandQuantityEdit' + '&idWorkCommandBill=' + id + '&idWorkCommand=' + dijit.byId('acceptedWorkCommandWorkCommand').get('value')+addTokenIndexToUrl(),
      handleAs:"text",
      load:function(data) {
        var quantity=dijit.byId('acceptedWorkCommandQuantityAccepted').get('value');
        var totalQuantityAccepted=parseInt(data) + quantity;
        dijit.byId('acceptedWorkCommandAccepted').set('value',totalQuantityAccepted);
      }
    });
  }
}

function switchShowGlobalCurrency(val) {
  var oldVal=(val=='NO')?'Yes':'No';
  var newVal=(val=='NO')?'No':'Yes';
  dojo.byId('showGlobalCurrency'+oldVal).style.display='none';
  dojo.byId('showGlobalCurrency'+newVal).style.display='';
  saveDataToSession('multiCurrencyShowGlobal',val,true);
  if (!formChangeInProgress && dijit.byId('listForm') && dojo.byId('objectClass').value) setTimeout('loadContent("objectDetail.php", "detailDiv", "listForm");',50);
}