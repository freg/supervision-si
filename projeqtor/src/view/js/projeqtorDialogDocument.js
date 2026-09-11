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

function showDetailApprover() {
  var canCreate=0;
  if (canCreateArray['Resource'] == "YES") {
    canCreate=1;
  }
  showDetail('approverId',canCreate,'Resource',true);
}

// =============================================================================
// = Approvers
// =============================================================================

function addApprover() {
  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
  var objectClass=dojo.byId('objectClass').value;
  var objectId=dojo.byId("objectId").value;
  dojo.byId("approverRefType").value=objectClass;
  dojo.byId("approverRefId").value=objectId;
  refreshApproverList();
  dijit.byId("dialogApprover").show();
  disableWidget('dialogApproverSubmit');
}

function selectApproverItem() {
  var nbSelected=0;
  list=dojo.byId('approverId');
  if (list.options) {
    for (var i=0;i < list.options.length;i++) {
      if (list.options[i].selected) {
        nbSelected++;
      }
    }
  }
  if (nbSelected > 0) {
    enableWidget('dialogApproverSubmit');
  } else {
    disableWidget('dialogApproverSubmit');
  }
}

function refreshApproverList(selected) {
  disableWidget('dialogApproverSubmit');
  var url='../tool/dynamicListApprover.php';
  if (selected) {
    url+='?selected=' + selected;
  }
  selectApproverItem();
  loadContent(url,'dialogApproverList','approverForm',false);
}

function saveApprover() {
  if (dojo.byId("approverId").value == "") return;
  loadContent("../tool/saveApprover.php","resultDivMain","approverForm",true,'approver');
  dijit.byId('dialogApprover').hide();
}

function removeApprover(approverId,approverName) {
  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
  dojo.byId("approverItemId").value=approverId;
  dojo.byId("approverRefType").value=dojo.byId('objectClass').value;
  dojo.byId("approverRefId").value=dojo.byId("objectId").value;
  actionOK=function() {
    loadContent("../tool/removeApprover.php","resultDivMain","approverForm",true,'approver');
  };
  msg=i18n('confirmDeleteApprover',new Array(approverName));
  showConfirm(msg,actionOK);
}

function approveItem(approverId,action) {
  var form=null;
  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
  if (action == 'disapproved') {
    form='confirmDisapproveForm';
  }
  loadContent("../tool/approveItem.php?approverId=" + approverId + "&action=" + action,"resultDivMain",form,true,'approver');
}

function disapproveItem(approverId) {
  var params="&approverId=" + approverId;
  loadDialog('dialogConfirmDisapprove',null,true,params,false);
}

function enableConfirmDisapproveSubmit(value) {
  var value=dijit.byId('disapproveDescription').get('value');
  if (value != "") {
    enableWidget('dialogConfirmDisapproveSubmit');
  } else {
    disableWidget('dialogConfirmDisapproveSubmit');
  }
}

// =============================================================================
// = DocumentVersion
// =============================================================================

function addDocumentVersion(defaultStatus,typeEvo,numVers,dateVers,nameVers,lockStatus) {
  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
  content=dijit.byId('dialogDocumentVersion').get('content');
  if (content == "") {
    callBack=function() {
      dojo.connect(dijit.byId("documentVersionFile"),"onComplete",function(dataArray) {
        saveDocumentVersionAck(dataArray);
      });
      dojo.connect(dijit.byId("documentVersionFile"),"onProgress",function(data) {
        saveDocumentVersionProgress(data);
      });
      addDocumentVersion(defaultStatus,typeEvo,numVers,dateVers,nameVers,lockStatus);
    };
    loadDialog('dialogDocumentVersion',callBack);
    return;
  }
  dojo.style(dojo.byId('downloadProgress'),{
    display:'none'
  });
  if (dijit.byId("documentVersionFile")) {
    dijit.byId("documentVersionFile").reset();
    if (!isHtml5()) {
      enableWidget('dialogDocumentVersionSubmit');
    } else {
      disableWidget('dialogDocumentVersionSubmit');
    }
  }
  dojo.byId("documentVersionId").value="";
  dojo.byId('documentVersionFileName').innerHTML="";
  refreshListSpecific('listStatusDocumentVersion','documentVersionIdStatus','idDocumentVersion','');
  dijit.byId('documentVersionIdStatus').set('value',defaultStatus);
  dojo.style(dojo.byId('inputFileDocumentVersion'),{
    display:'block'
  });
  dojo.byId("documentId").value=dojo.byId("objectId").value;
  dojo.byId("documentVersionVersion").value=dojo.byId('version').value;
  dojo.byId("documentVersionRevision").value=dojo.byId('revision').value;
  dojo.byId("documentVersionDraft").value=dojo.byId('draft').value;
  dojo.byId("typeEvo").value=typeEvo;
  dijit.byId("documentVersionLink").set('value','');
  dijit.byId("documentVersionFile").reset();
  dijit.byId('documentVersionFile').addDropTarget(dojo.byId('formDivDoc'),true);
  dijit.byId("documentVersionDescription").set('value','');
  dijit.byId("documentVersionUpdateMajor").set('checked','true');
  dijit.byId("documentVersionUpdateDraft").set('checked',false);
  dijit.byId("documentVersionDate").set('value',new Date());
  dijit.byId("documentVersionUpdateMajor").set('readOnly',false);
  dijit.byId("documentVersionUpdateMinor").set('readOnly',false);
  dijit.byId("documentVersionUpdateNo").set('readonly',false);
  dijit.byId("documentVersionUpdateDraft").set('readonly',false);
  dijit.byId("documentVersionIsRef").set('checked',false);
  dijit.byId('documentVersionVersionDisplay').set('value',
      getDisplayVersion(typeEvo,dojo.byId('documentVersionVersion').value,dojo.byId('documentVersionRevision').value,dojo.byId('documentVersionDraft').value),numVers,dateVers,nameVers);
  dojo.byId('documentVersionMode').value="add";
  calculateNewVersion();
  setDisplayIsRefDocumentVersion();
  if (lockStatus == 1) {
    dojo.byId("lockedMsg").style.display='block';
  } else {
    dojo.byId("lockedMsg").style.display='none';
  }
  dijit.byId("dialogDocumentVersion").show();
  dojo.setStyle('widget_documentVersionNewVersionDisplay',"border-color","#b3b3b3");
}

function editDocumentVersion(id,version,revision,draft,versionDate,status,isRef,typeEvo,numVers,dateVers,nameVers) {
  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
  content=dijit.byId('dialogDocumentVersion').get('content');
  if (content == "") {
    callBack=function() {
      dojo.connect(dijit.byId("documentVersionFile"),"onComplete",function(dataArray) {
        saveDocumentVersionAck(dataArray);
      });
      dojo.connect(dijit.byId("documentVersionFile"),"onProgress",function(data) {
        saveDocumentVersionProgress(data);
      });
      editDocumentVersion(id,version,revision,draft,versionDate,status,isRef,typeEvo,numVers,dateVers,nameVers);
    };
    loadDialog('dialogDocumentVersion',callBack);
    return;
  }
  dijit.byId('documentVersionIdStatus').store;
  refreshListSpecific('listStatusDocumentVersion','documentVersionIdStatus','idDocumentVersion',id);
  dijit.byId('documentVersionIdStatus').set('value',status);
  dojo.style(dojo.byId('inputFileDocumentVersion'),{
    display:'none'
  });
  dojo.byId("documentVersionId").value=id;
  dojo.byId("documentId").value=dojo.byId("objectId").value;
  dojo.byId("documentVersionVersion").value=version;
  dojo.byId("documentVersionRevision").value=revision;
  dojo.byId("documentVersionDraft").value=draft;
  dojo.byId("typeEvo").value=typeEvo;
  if (draft) {
    dijit.byId('documentVersionUpdateDraft').set('checked',true);
  } else {
    dijit.byId('documentVersionUpdateDraft').set('checked',false);
  }
  if (isRef == '1') {
    dijit.byId('documentVersionIsRef').set('checked',true);
  } else {
    dijit.byId('documentVersionIsRef').set('checked',false);
  }
  dijit.byId("documentVersionLink").set('value','');
  dijit.byId("documentVersionFile").reset();
  dijit.byId('documentVersionFile').addDropTarget(dojo.byId('formDivDoc'),true);
  dijit.byId("documentVersionDescription").set("value",dojo.byId("documentVersion_" + id).value);
  dijit.byId("documentVersionUpdateMajor").set('readOnly','readOnly');
  dijit.byId("documentVersionUpdateMinor").set('readOnly','readOnly');
  dijit.byId("documentVersionUpdateNo").set('readonly','readonly');
  dijit.byId("documentVersionUpdateNo").set('checked',true);
  dijit.byId("documentVersionUpdateDraft").set('readonly','readonly');
  dijit.byId("documentVersionDate").set('value',versionDate);
  dojo.byId('documentVersionMode').value="edit";
  dijit.byId('documentVersionVersionDisplay').set('value',nameVers);
  calculateNewVersion(false);
  setDisplayIsRefDocumentVersion();
  dijit.byId("dialogDocumentVersion").show();
}

function changeDocumentVersion(list) {
  if (list.length > 0) {
    dojo.byId('documentVersionFileName').innerHTML=list[0]['name'];
    enableWidget('dialogDocumentVersionSubmit');
  } else {
    dojo.byId('documentVersionFileName').innerHTML="";
    disableWidget('dialogDocumentVersionSubmit');
  }
}

function saveDocumentVersion() {
  if (!isHtml5()) {
    showWait();
    dijit.byId('dialogDocumentVersion').hide();
    return true;
  }
  if (dojo.byId('documentVersionFileName').innerHTML == "") {
    setTimeout("loadContent('objectDetail.php', 'detailDiv', 'listForm');",200);
    return false;
  }
  dojo.style(dojo.byId('downloadProgress'),{
    display:'block'
  });
  showWait();
  dijit.byId('dialogDocumentVersion').hide();
  setTimeout("loadContent('objectDetail.php', 'detailDiv', 'listForm');",200);
  return true;
}

function saveDocumentVersionAck(dataArray) {
  if (!isHtml5()) {
    resultFrame=document.getElementById("documentVersionPost");
    resultText=documentVersionPost.document.body.innerHTML;
    dojo.byId('resultAckDocumentVersion').value=resultText;
    loadContent("../tool/ack.php","resultDivMain","documentVersionAckForm",true,'documentVersion');
    return;
  }
  dijit.byId('dialogDocumentVersion').hide();
  if (dojo.isArray(dataArray)) {
    result=dataArray[0];
  } else {
    result=dataArray;
  }
  dojo.style(dojo.byId('downloadProgress'),{
    display:'none'
  });
  dojo.byId('resultAckDocumentVersion').value=result.message;
  loadContent("../tool/ack.php","resultDivMain","documentVersionAckForm",true,'documentVersion');
}

function saveDocumentVersionProgress(data) {
  done=data.bytesLoaded;
  total=data.bytesTotal;
  if (total) {
    progress=done / total;
  }
  dijit.byId('downloadProgress').set('value',progress);
}

function removeDocumentVersion(documentVersionId,documentVersionName) {
  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
  content=dijit.byId('dialogDocumentVersion').get('content');
  if (content == "") {
    callBack=function() {
      dojo.connect(dijit.byId("documentVersionFile"),"onComplete",function(dataArray) {
        saveDocumentVersionAck(dataArray);
      });
      dojo.connect(dijit.byId("documentVersionFile"),"onProgress",function(data) {
        saveDocumentVersionProgress(data);
      });
      removeDocumentVersion(documentVersionId,documentVersionName);
    };
    loadDialog('dialogDocumentVersion',callBack);
    return;
  }
  dojo.byId("documentVersionId").value=documentVersionId;
  actionOK=function() {
    loadContent("../tool/removeDocumentVersion.php","resultDivMain","documentVersionForm",true,'documentVersion');
  };
  msg=i18n('confirmDeleteDocumentVersion',new Array(documentVersionName));
  showConfirm(msg,actionOK);
}

function getDisplayVersion(typeEvo,version,revision,draft,numVers,dateVers,nameVers) {
  var res="";
  if (typeEvo == "EVO") {
    if (version != "" && revision != "") {
      res="V" + version + "." + revision;
    }
  } else if (typeEvo == "EVT") {
    res=dateVers;
  } else if (typeEvo == "SEQ") {
    res=numVers;
  } else if (typeEvo == "EXT") {
    res=nameVers;
  }
  if (typeEvo == "EVO" || typeEvo == "EVT" || typeEvo == "SEQ") {
    if (draft) {
      res+=draftSeparator + draft;
    }
  }
  return res;
}

function calculateNewVersion(update) {
  var typeEvo=dojo.byId("typeEvo").value;
  var numVers="";
  var dateVers="";
  var nameVers="";
  if (dijit.byId('documentVersionUpdateMajor').get('checked')) {
    type="major";
  } else if (dijit.byId('documentVersionUpdateMinor').get('checked')) {
    type="minor";
  } else if (dijit.byId('documentVersionUpdateNo').get('checked')) {
    type="none";
  }
  version=dojo.byId('documentVersionVersion').value;
  revision=dojo.byId('documentVersionRevision').value;
  draft=dojo.byId('documentVersionDraft').value;
  isDraft=dijit.byId('documentVersionUpdateDraft').get('checked');
  version=(version == '') ? 0 : parseInt(version,10);
  revision=(revision == '') ? 0 : parseInt(revision,10);
  draft=(draft == '') ? 0 : parseInt(draft,10);
  if (type == "major") {
    dojo.byId('documentVersionNewVersion').value=version + 1;
    dojo.byId('documentVersionNewRevision').value=0;
    dojo.byId('documentVersionNewDraft').value=(isDraft) ? '1' : '';
  } else if (type == "minor") {
    dojo.byId('documentVersionNewVersion').value=version;
    dojo.byId('documentVersionNewRevision').value=revision + 1;
    dojo.byId('documentVersionNewDraft').value=(isDraft) ? '1' : '';
  } else { // 'none'
    dojo.byId('documentVersionNewVersion').value=version;
    dojo.byId('documentVersionNewRevision').value=revision;
    if (dojo.byId('documentVersionId').value) {
      dojo.byId('documentVersionNewDraft').value=(isDraft) ? ((draft) ? draft : 1) : '';
    } else {
      dojo.byId('documentVersionNewDraft').value=(isDraft) ? draft + 1 : '';
    }
  }
  dateVers=dojo.date.locale.format(dijit.byId("documentVersionDate").get('value'),{
    datePattern:"yyyyMMdd",
    selector:"date"
  });
  nameVers=dijit.byId("documentVersionVersionDisplay").get('value');
  numVers=nameVers;
  if (typeEvo == "SEQ" && dojo.byId('documentVersionMode').value == "add") {
    if (!nameVers) {
      nameVers=0;
    }
    numVers=parseInt(nameVers,10) + 1;
  }
  dijit.byId("documentVersionNewVersionDisplay").set('readOnly','readOnly');
  if (typeEvo == "EXT") {
    dijit.byId("documentVersionNewVersionDisplay").set('readOnly',false);
  }
  var newVers=getDisplayVersion(typeEvo,dojo.byId('documentVersionNewVersion').value,dojo.byId('documentVersionNewRevision').value,dojo.byId('documentVersionNewDraft').value,numVers,dateVers,nameVers);
  if (typeEvo == "EXT") {
    dojo.byId('oldDocumentVersionNewVersionDisplay').value=newVers;
  } else {
    dijit.byId('documentVersionNewVersionDisplay').set('value',newVers);
  }
  if (isDraft) {
    dijit.byId('documentVersionIsRef').set('checked',false);
    setDisplayIsRefDocumentVersion();
  }
}

function setDisplayIsRefDocumentVersion() {
  if (dijit.byId('documentVersionIsRef').get('checked')) {
    dojo.style(dojo.byId('documentVersionIsRefDisplay'),{
      display:'block'
    });
    dijit.byId('documentVersionUpdateDraft').set('checked',false);
    calculateNewVersion();
  } else {
    dojo.style(dojo.byId('documentVersionIsRefDisplay'),{
      display:'none'
    });
  }
}

function lockDocument() {
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

function unlockDocument() {
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

function showExtractDocument(objId,objClass) {
  if (!objId) objId=dojo.byId('objectId').value;
  if (!objClass) objClass=dojo.byId('objectClass').value;
  var param="&objectClass=" + objClass + "&objectId=" + objId;
  loadDialog('dialogDocumentExtraction',null,true,param);
}

function submitDocumentExtraction() {
  showWait();
  dojo.xhrPost({
    url:'../tool/extractDocumentFromObject.php'+addTokenIndexToUrl('?'),
    form:'documentExtractionForm',
    handleAs:"text",
    load:function(data,args) {
      hideWait();
      if (data != 'noFilesFound') {
        dijit.byId('dialogDocumentExtraction').hide();
        window.open(data);
        dojo.xhrGet({
          url:'../tool/extractDocumentFromObject.php'+addTokenIndexToUrl('?') + '&download=true',
          handleAs:"text",
          load:function(data,args) {
          }
        });
      } else {
        showAlert(i18n(data));
      }
    }
  });
}