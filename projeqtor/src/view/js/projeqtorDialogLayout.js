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
// = Layout
// =============================================================================

function showLayoutDialog(objectClass) {
  function callBack() {
    if (dojo.byId('objectClassList') && dojo.byId('objectClassList').value) dojo.byId('layoutObjectClass').value=dojo.byId('objectClassList').value;
    else if (dojo.byId('objectClassManual') && dojo.byId('objectClassManual').value) dojo.byId('layoutObjectClass').value=dojo.byId('objectClassManual').value;
    else if (dojo.byId('objectClass') && dojo.byId('objectClass').value) dojo.byId('layoutObjectClass').value=dojo.byId('objectClass').value;
    else dojo.byId('layoutObjectClass').value=null;
    layoutType="";
    var compUrl=(window.top.dijit.byId("dialogDetail").open) ? '&comboDetail=true' : '';
    dojo.xhrPost({
      url:"../tool/backupLayout.php?layoutObjectClass=" + dojo.byId('layoutObjectClass').value + compUrl +addTokenIndexToUrl(),
      handleAs:"text",
      load:function(data,args) {
      }
    });
    loadContent("../tool/displayLayoutList.php" + compUrl,"listStoredLayouts","dialogLayoutForm",false);
    loadContent("../tool/displayLayoutSharedList.php" + compUrl,"listSharedLayouts","dialogLayoutForm",false);
    loadContent("../tool/displayLayoutClause.php" + compUrl,"listSelectedLayout","dialogLayoutForm",false);
    dijit.byId("dialogLayout").show();
  }
  loadDialog('dialogLayout',callBack,true,"&objectClass="+objectClass,true);
}

function selectLayout() {
  selectLayoutContinue();
}

function selectLayoutContinue() {
  if (window.top.dijit.byId('dialogDetail').open) {
    var doc=window.top.frames['comboDetailFrame'];
  } else {
    var doc=window.top;
  }
  if (dijit.byId('layoutNameDisplay')) {
    dojo.byId('layoutName').value=dijit.byId('layoutNameDisplay').get('value');
  }
  var compUrl=(window.top.dijit.byId("dialogDetail").open) ? '&comboDetail=true' : '';
  dojo.xhrPost({
    url:"../tool/backupLayout.php?layoutObjectClass=" + dojo.byId('layoutObjectClass').value + compUrl +addTokenIndexToUrl(),
    handleAs:"text",
    load:function(data,args) {
    }
  });
  if (dojo.byId('objectClassList') && dojo.byId('objectClassList').value) {
    objectClass=dojo.byId('objectClassList').value;
  } else if (!window.top.dijit.byId('dialogDetail').open && dojo.byId("objectClassManual") && dojo.byId("objectClassManual").value) {
    objectClass=dojo.byId("objectClassManual").value;
  } else if (dojo.byId('objectClass') && dojo.byId('objectClass').value) {
    objectClass=dojo.byId('objectClass').value;
  }
  dijit.byId("dialogLayout").hide();
}

function saveLayout() {
  if (dijit.byId('layoutNameDisplay')) {
    if (dijit.byId('layoutNameDisplay').get('value') == "") {
      showAlert(i18n("messageMandatory",new Array(i18n("layoutName"))));
      return;
    }
    dojo.byId('layoutName').value=dijit.byId('layoutNameDisplay').get('value');
  }
  var compUrl=(window.top.dijit.byId("dialogDetail").open) ? '?comboDetail=true' : '';
  loadContent("../tool/saveLayout.php" + compUrl,"listStoredLayouts","dialogLayoutForm",false,null,null,null,function() {
    clearDivDelayed('saveLayoutResult');
  });
  if(dojo.byId('canAttributeLayout') && dojo.byId('canAttributeLayout').value == 1)dijit.byId('layoutAttribute').set('disabled',false);
}

/**
 * Select a stored layout in the list and fetch criteria
 * 
 */
function selectStoredLayout(idLayout) {
  var compUrl=(window.top.dijit.byId("dialogDetail").open) ? '&comboDetail=true' : '';
  loadContent("../tool/selectStoredLayout.php?idLayout=" + idLayout + compUrl,"listSelectedLayout","dialogLayoutForm",false);
  if (dojo.byId('objectClassList') && dojo.byId('objectClassList').value) {
    objectClass=dojo.byId('objectClassList').value;
  } else if (!window.top.dijit.byId('dialogDetail').open && dojo.byId("objectClassManual") && dojo.byId("objectClassManual").value) {
    objectClass=dojo.byId("objectClassManual").value;
  } else if (dojo.byId('objectClass') && dojo.byId('objectClass').value) {
    objectClass=dojo.byId('objectClass').value;
  }
  loadContent("../tool/displayLayoutList.php?context=directLayoutList&layoutObjectClass="+ objectClass + compUrl, "listStoredLayouts", null, false, null, false);
  if(dojo.byId('canAttributeLayout') && dojo.byId('canAttributeLayout').value == 1)dijit.byId('layoutAttribute').set('disabled',false);
  if(dojo.byId('idForcedLayout') && dojo.byId('idForcedLayout').value == idLayout)dijit.byId('layoutAttribute').set('disabled',true);
}

function removeStoredLayout(idLayout,nameLayout) {
  var compUrl=(window.top.dijit.byId("dialogDetail").open) ? '&comboDetail=true' : '';
  var action=function() {
    var callBack=function() {
      clearDivDelayed('saveLayoutResult');
    };
    loadContent("../tool/removeLayout.php?idLayout=" + idLayout + compUrl,"listStoredLayouts","dialogLayoutForm",false,null,null,null,callBack);
  };
  window.top.showConfirm(i18n("confirmRemoveLayout",new Array(nameLayout)),action);
}

function shareStoredLayout(idLayout,nameLayout) {
  var compUrl=(window.top.dijit.byId("dialogDetail").open) ? '&comboDetail=true' : '';
  loadContent("../tool/shareLayout.php?idLayout=" + idLayout + compUrl,"listStoredLayouts","dialogLayoutForm",false);
}

function validateLayoutListColumn(planningType){
  if (!planningType) planningType = (dojo.byId('planningType'))?dojo.byId('planningType').value:'planning';
  var compUrl=(window.top.dijit.byId("dialogDetail").open) ? '&comboDetail=true' : '';
  if (window.top.dijit.byId('dialogDetail').open) {
    var doc=window.top.frames['comboDetailFrame'];
  } else {
    var doc=window.top;
  }
  if (planningType=='noRefreshLayout') {
    if (compUrl) {
      doc.refreshJsonList(dojo.byId('objectClassList').value);
    } else {
      loadContent("objectList.php?objectClass="+dojo.byId('objectClassList').value+"&objectId="+dojo.byId('objectId').value + compUrl,
                "listDiv",null,null,null,null,null,callBack);
    }
  }
  if (dojo.byId('objectClassList') && dojo.byId('objectClassList').value) {
    objectClass=dojo.byId('objectClassList').value;
  } else if (!window.top.dijit.byId('dialogDetail').open && dojo.byId("objectClassManual") && dojo.byId("objectClassManual").value) {
    objectClass=dojo.byId("objectClassManual").value;
  } else if (dojo.byId('objectClass') && dojo.byId('objectClass').value) {
    objectClass=dojo.byId('objectClass').value;
  }
  showWait();
  dojo.xhrPost({
    url:"../tool/backupLayout.php?layoutObjectClass=" + objectClass + compUrl +addTokenIndexToUrl(),
    handleAs:"text",
    load:function(data,args) {
    }
  });
  dojo.xhrPost({
    url:"../tool/saveSelectedLayoutColumn.php?layoutObjectClass=" + objectClass + compUrl +addTokenIndexToUrl(),
    handleAs:"text",
    load:function(data,args) {
      if(dijit.byId("dialogLayout"))dijit.byId("dialogLayout").hide();
      if(objectClass.indexOf('Planning') != -1 && objectClass!='PlanningMode'){
        var callback = function(){
          var nodeList=dndPlanningColumnSelector.getAllNodes();
          planningColumnOrder[getIndiceForPlanningType(planningType)]=new Array();
          for (var i=0; i < nodeList.length; i++) {
            var col=nodeList[i].id.substr(14);
            var status=(dijit.byId('checkColumnSelector' + col).get('checked')) ? true
                : false;
            var check = (status)?'':'hidden';
            planningColumnOrder[getIndiceForPlanningType(planningType)][i]=check + col;
            setPlanningFieldShow(col,status,planningType);
            if (col=='IdStatus' || col=='Type') {
              validatePlanningColumnNeedRefresh=true;
            }
          }
          validatePlanningColumn(planningType);
        };
        loadContent('../tool/refreshPlanningColumnSelector.php?planningType='+planningType+'&layoutObjectClass=' + objectClass + compUrl + ''+addTokenIndexToUrl(),'divPlanningColumnSelector', null, false, null, null,true, callback);
      }else if (planningType == "kanban") {
        refreshKanban();
      }else{
        var callBack=function(){
          if (dijit.byId('listColumnSelector')) {
            dijit.byId('listColumnSelector').closeDropDown();
            resizeListDiv();
          }
          filterJsonList(dojo.byId("objectClass").value);
        };
        if (compUrl) {
          doc.refreshJsonList(dojo.byId('objectClassList').value);
        } else {
          loadContent("objectList.php?objectClass="+dojo.byId('objectClassList').value+"&objectId="+dojo.byId('objectId').value + compUrl,
                    "listDiv",null,null,null,null,null,callBack);
        }
      }
    }
  });
}

function moveLayoutListColumn() {
  var mode='';
  var list='';
  var nodeList=dndListLayoutSelector.getAllNodes();
  listColumnOrder=new Array();
  for (var i=0; i < nodeList.length; i++) {
    var itemSelected=nodeList[i].id.substr(6);
    list+=itemSelected + "|";
  }  
  var callback=function() {
      if (dojo.byId('objectClassList') && dojo.byId('objectClassList').value){
        var objectClass=dojo.byId('objectClassList').value;
      }else if (! window.top.dijit.byId('dialogDetail').open && dojo.byId("objectClassManual") && dojo.byId("objectClassManual").value){ 
        var objectClass=dojo.byId("objectClassManual").value;
      }else if (dojo.byId('objectClass') && dojo.byId('objectClass').value){
        var objectClass=dojo.byId('objectClass').value;
      } 
      var compUrl=(window.top.dijit.byId("dialogDetail").open) ? '?comboDetail=true' : '';
      loadContent("../tool/displayLayoutList.php?context=directLayoutList&layoutObjectClass="
              + objectClass + compUrl, "listStoredLayouts", null, false, null, false);
    };
  
  var url='../tool/moveLayoutColumn.php?orderedList=' + list;
  dojo.xhrPost({
    url : url+addTokenIndexToUrl()+addTokenIndexToUrl(),
    handleAs : "text",
    load : function(data, args) {
      if (callback)
        setTimeout(callback, 10);
    }
  });
}

function changelayoutForOtherFromDialog(mode,objectClass,scope,objectId,userId,key,currentUserId) {
//  if (! objectId && dojo.byId('id')) objectId=dojo.byId('id').value;
//  var url="../tool/saveLayoutForOthers.php?mode="+mode;
//  url+="&objectClass="+objectClass;
//  url+="&objectId="+objectId;
//  url+="&scope="+scope;
//  url+="&userId="+userId;
//  dojo.xhrGet({
//    url : url+addTokenIndexToUrl(),
//    handleAs : "text",
//    load : function(data) {
//      var result="KO";
//      var itemLabel="";
//      var message="";
//      var userName="";
//      var userId="";
//      var currentUserId="";
//      var objectClass="";
//      var objectId="";
//      var response=JSON.parse(data);
//      if (response.hasOwnProperty('result')) result=response.result;
//      if (response.hasOwnProperty('itemLabel')) itemLabel=response.itemLabel;
//      if (response.hasOwnProperty('userName')) userName=response.userName;
//      if (response.hasOwnProperty('userId')) userId=response.userId;
//      if (response.hasOwnProperty('currentUserId')) currentUserId=response.currentUserId;
//      if (response.hasOwnProperty('objectClass')) objectClass=response.objectClass;
//      if (response.hasOwnProperty('objectId')) objectId=response.objectId;
//      if (response.hasOwnProperty('message'))  message=response.message;
//      if (result=='OK') {
//        if (dialog=='list') {
//          addMessage(i18n('unsubscriptionSuccess',new Array(itemLabel)));
//        } else if (dialog=='other') {
//          if (mode=='on') {
//            addMessage(i18n('subscriptionSuccess',new Array(userName)));
//          } else {
//            addMessage(i18n('unsubscriptionSuccess',new Array(userName)));
//          }
//        }
//        if (key) {
//          if (mode=='on') {
//            dojo.byId('subscribtionButton'+key).style.display="none";
//            dojo.byId('unsubscribtionButton'+key).style.display="inline-block";
//          } else {
//            dojo.byId('unsubscribtionButton'+key).style.display="none";
//            dojo.byId('subscribtionButton'+key).style.display="inline-block";
//          }
//        }
//        if (userId && currentUserId && userId==currentUserId && objectClass && objectId) {
//          if (dojo.byId('objectClass') && objectClass==dojo.byId('objectClass').value && dojo.byId('objectId') && parseInt(objectId)==parseInt(dojo.byId('objectId').value)) {
//            if (mode=='on') {
//              if (dijit.byId('subscribeButton')) dijit.byId('subscribeButton').set('iconClass','dijitButtonIcon dijitButtonIconSubscribeValid');
//              enableWidget('subscribeButtonUnsubscribe');
//              disableWidget('subscribeButtonSubscribe');
//            } else {
//              if (dijit.byId('subscribeButton')) dijit.byId('subscribeButton').set('iconClass','dijitButtonIcon dijitButtonIconSubscribe');
//              enableWidget('subscribeButtonSubscribe');
//              disableWidget('subscribeButtonUnsubscribe');
//            }
//          }
//        }
//      } else {
//        showError(i18n('subscriptionFailed')+'<br/>'+message);
//      }
//    },
//    error : function() {
//      showError(i18n('subscriptionFailed'));
//    }
//  });
}

function validateLayoutForOthers(){
    var tab = '';
    dojo.map(dojo.byId('layoutSubscribed').children, function(child){
      tab += child.getAttribute('userid')+'-';
    });
    validateLayoutForOthersSave(tab);
}


function validateLayoutForOthersSave(tab){
  loadContent("../tool/saveValidateLayoutForOthers.php?test="+tab,"detailDiv","dialogLayoutForOthersForm");
  dijit.byId('dialogLayoutForOthers').hide();
}

function saveGroup() {
  var idLayoutGroup = (dijit.byId('selectGroup'))?dijit.byId('selectGroup').value:' ';
  if (dijit.byId('saveGroup')) {
    if (dijit.byId('saveGroup').get('value') == "") {
      showAlert(i18n("messageMandatory",new Array(i18n("saveGroup"))));
      return;
    }
    dojo.byId('saveGroup').value=dijit.byId('saveGroup').get('value');
  }
  var tab = '';
  dojo.map(dojo.byId('layoutSubscribed').children, function(child){
    tab += child.getAttribute('userid')+'-';
  });
  loadContent("../tool/saveGroup.php?tab="+tab,"listGroup","dialogLayoutForOthersForm",false,null,null,null,function() {
    var newIdLayoutGroup = ' ';
    if(dojo.byId('newIdLayoutGroup')){
      newIdLayoutGroup = dojo.byId('newIdLayoutGroup').value;
    }
    var callback = function(){
      clearDivDelayed('saveGroupResult');
      if(dijit.byId('selectGroup')){
        dijit.byId('selectGroup').set('value', newIdLayoutGroup);
      }
    };
    loadDialog('dialogLayoutForOthers',callback,true,'&layoutObjectClass='+ dojo.byId('layoutObjectClass').value,true);
  });
}

function removeGroup() {
  if (dijit.byId('saveGroup')) {
    if (dijit.byId('saveGroup').get('value') == "") {
      showAlert(i18n("messageMandatory",new Array(i18n("saveGroup"))));
      return;
    }
    dojo.byId('saveGroup').value=dijit.byId('saveGroup').get('value');
  }
  loadContent("../tool/removeLayoutGroup.php","listGroup","dialogLayoutForOthersForm",false,null,null,null,function() {
    var callback = function(){
      clearDivDelayed('saveGroupResult');
    };
    loadDialog('dialogLayoutForOthers',callback,true,'&layoutObjectClass='+ dojo.byId('layoutObjectClass').value,true);
  });
}

function layoutAll(container){
  dojo.query('.layoutIsAvaible', dojo.byId('layoutAvailable')).forEach(function(label){
    var style = label.getAttribute("style");
    var word = "display: block";
    if(style.includes(word)){
      dojo.byId('layoutSubscribed').appendChild(label);
    } 
  });
}

function remindGroup(){
  if(dijit.byId('selectGroup').get('value') != ' '){
    dojo.byId('removeGroupButtonTD').style.display = '';
    dojo.xhrGet({
      url:'../tool/getSingleData.php?dataType=selectGroup&idGroup=' + dijit.byId('selectGroup').get('value') + ''+addTokenIndexToUrl(),
      handleAs:"text",
      load:function(data) {
        arrayData=data.split('#!#!#!#!#!#');
        arrayData.forEach(function(item) {
          if(item != ''){
            dojo.query('.layoutIsAvaible', dojo.byId('layoutAvailable')).forEach(function(label){
              if(label.getAttribute("id")== "layoutForOther"+item){
              dojo.byId('layoutSubscribed').appendChild(label);
              }
            });
          }
        });
        dijit.byId('saveGroup').set('value', dojo.byId('selectGroup').value);
      }
    });
  }else{
    dojo.byId('removeGroupButtonTD').style.display = 'none';
  }
}

//=========================================================================//
//============================== Report List ==============================//
//=========================================================================//

function showReportLayoutDialog(objectClass) {
  function callBack() {
    if (dojo.byId('objectClassList') && dojo.byId('objectClassList').value) dojo.byId('reportLayoutObjectClass').value=dojo.byId('objectClassList').value;
    else if (dojo.byId('objectClassManual') && dojo.byId('objectClassManual').value) dojo.byId('layoutObjectClass').value=dojo.byId('objectClassManual').value;
    else if (dojo.byId('objectClass') && dojo.byId('objectClass').value) dojo.byId('reportLayoutObjectClass').value=dojo.byId('objectClass').value;
    else dojo.byId('reportLayoutObjectClass').value=null;
    var compUrl=(window.top.dijit.byId("dialogDetail").open) ? '&comboDetail=true' : '';
    dojo.xhrPost({
      url:"../tool/backupReportLayout.php?reportLayoutObjectClass=" + dojo.byId('reportLayoutObjectClass').value + compUrl +addTokenIndexToUrl(),
      handleAs:"text",
      load:function(data,args) {
      }
    });
    loadContent("../tool/displayReportLayoutList.php" + compUrl,"listStoredReportLayouts","dialogReportLayoutForm",false);
    loadContent("../tool/displayReportLayoutSharedList.php" + compUrl,"listSharedReportLayouts","dialogReportLayoutForm",false);
    loadContent("../tool/displayReportLayoutClause.php" + compUrl,"listSelectedReportLayout","dialogReportLayoutForm",false);
    dijit.byId("dialogReportLayout").show();
  }
  loadDialog('dialogReportLayout',callBack,true,"&objectClass="+objectClass,true);
}

function selectReportLayout() {
  selectReportLayoutContinue();
}

function selectReportLayoutContinue() {
  if (window.top.dijit.byId('dialogDetail').open) {
    var doc=window.top.frames['comboDetailFrame'];
  } else {
    var doc=window.top;
  }
  if (dijit.byId('reportLayoutNameDisplay')) {
    dojo.byId('reportLayoutName').value=dijit.byId('reportLayoutNameDisplay').get('value');
  }
  var compUrl=(window.top.dijit.byId("dialogDetail").open) ? '&comboDetail=true' : '';
  dojo.xhrPost({
    url:"../tool/backupReportLayout.php?reportLayoutObjectClass=" + dojo.byId('reportLayoutObjectClass').value + compUrl +addTokenIndexToUrl(),
    handleAs:"text",
    load:function(data,args) {
    }
  });
  if (dojo.byId('objectClassList') && dojo.byId('objectClassList').value) {
    objectClass=dojo.byId('objectClassList').value;
  } else if (!window.top.dijit.byId('dialogDetail').open && dojo.byId("objectClassManual") && dojo.byId("objectClassManual").value) {
    objectClass=dojo.byId("objectClassManual").value;
  } else if (dojo.byId('objectClass') && dojo.byId('objectClass').value) {
    objectClass=dojo.byId('objectClass').value;
  }
  dijit.byId("dialogReportLayout").hide();
}

function saveReportLayout() {
  if (dijit.byId('reportLayoutNameDisplay')) {
    if (dijit.byId('reportLayoutNameDisplay').get('value') == "") {
      showAlert(i18n("messageMandatory",new Array(i18n("reportLayoutName"))));
      return;
    }
    dojo.byId('reportLayoutName').value=dijit.byId('reportLayoutNameDisplay').get('value');
  }
  if (dojo.byId('objectClassList') && dojo.byId('objectClassList').value) {
    objectClass=dojo.byId('objectClassList').value;
  } else if (!window.top.dijit.byId('dialogDetail').open && dojo.byId("objectClassManual") && dojo.byId("objectClassManual").value) {
    objectClass=dojo.byId("objectClassManual").value;
  } else if (dojo.byId('objectClass') && dojo.byId('objectClass').value) {
    objectClass=dojo.byId('objectClass').value;
  }
  var compUrl=(window.top.dijit.byId("dialogDetail").open) ? '?comboDetail=true' : '';
  var directFilterJSON = JSON.stringify(Object.assign({}, directFilterArray[objectClass]));
  directFilterJSON = (compUrl)?'&directFilterList='+directFilterJSON:'?directFilterList='+directFilterJSON;
  loadContent("../tool/saveReportLayout.php" + compUrl + directFilterJSON,"listStoredReportLayouts","dialogReportLayoutForm",false,null,null,null,function() {
    clearDivDelayed('saveReportLayoutResult');
  });
}

function shareStoredReportLayout(idReportLayout,nameReportLayout) {
  var compUrl=(window.top.dijit.byId("dialogDetail").open) ? '&comboDetail=true' : '';
  loadContent("../tool/shareReportLayout.php?idReportLayout=" + idReportLayout + compUrl,"listStoredReportLayouts","dialogReportLayoutForm",false);
}

function selectStoredReportLayout(idReportLayout) {
  var compUrl=(window.top.dijit.byId("dialogDetail").open) ? '&comboDetail=true' : '';
  loadContent("../tool/selectStoredReportLayout.php?idReportLayout=" + idReportLayout + compUrl,"listSelectedReportLayout","dialogReportLayoutForm",false);
  if (dojo.byId('objectClassList') && dojo.byId('objectClassList').value) {
    objectClass=dojo.byId('objectClassList').value;
  } else if (!window.top.dijit.byId('dialogDetail').open && dojo.byId("objectClassManual") && dojo.byId("objectClassManual").value) {
    objectClass=dojo.byId("objectClassManual").value;
  } else if (dojo.byId('objectClass') && dojo.byId('objectClass').value) {
    objectClass=dojo.byId('objectClass').value;
  }
  loadContent("../tool/displayReportLayoutList.php?context=directReportLayoutList&reportLayoutObjectClass="+ objectClass + compUrl, "listStoredReportLayouts", null, false, null, false);
}

function removeStoredReportLayout(idReportLayout,nameReportLayout) {
  var compUrl=(window.top.dijit.byId("dialogDetail").open) ? '&comboDetail=true' : '';
  var action=function() {
    var callBack=function() {
      clearDivDelayed('saveReportLayoutResult');
      var idFavoriteRow = (dojo.byId('idFavoriteRow'))?dojo.byId('idFavoriteRow').value:1;
      refreshFavoriteReportList(idFavoriteRow);
    };
    loadContent("../tool/removeReportLayout.php?idReportLayout=" + idReportLayout + compUrl,"listStoredReportLayouts","dialogReportLayoutForm",false,null,null,null,callBack);
  };
  window.top.showConfirm(i18n("confirmRemoveReportLayout",new Array(nameReportLayout)),action);
}

function moveReportLayoutListColumn() {
  var mode='';
  var list='';
  var nodeList=dndListReportLayoutSelector.getAllNodes();
  listColumnOrder=new Array();
  for (var i=0; i < nodeList.length; i++) {
    var itemSelected=nodeList[i].id.substr(12);
    list+=itemSelected + "|";
  }  
  var callback=function() {
      if (dojo.byId('objectClassList') && dojo.byId('objectClassList').value){
        var objectClass=dojo.byId('objectClassList').value;
      }else if (! window.top.dijit.byId('dialogDetail').open && dojo.byId("objectClassManual") && dojo.byId("objectClassManual").value){ 
        var objectClass=dojo.byId("objectClassManual").value;
      }else if (dojo.byId('objectClass') && dojo.byId('objectClass').value){
        var objectClass=dojo.byId('objectClass').value;
      } 
      var compUrl=(window.top.dijit.byId("dialogDetail").open) ? '?comboDetail=true' : '';
      loadContent("../tool/displayReportLayoutList.php?context=directReportLayoutList&reportLayoutObjectClass="
              + objectClass + compUrl, "listStoredReportLayouts", null, false, null, false);
    };
  
  var url='../tool/moveReportLayoutColumn.php?orderedList=' + list;
  dojo.xhrPost({
    url : url+addTokenIndexToUrl()+addTokenIndexToUrl(),
    handleAs : "text",
    load : function(data, args) {
      if (callback)
        setTimeout(callback, 10);
    }
  });
}