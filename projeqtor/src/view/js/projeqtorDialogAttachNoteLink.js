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
// = Notes
// =============================================================================

// DOJO HACK
// Hack to be able to interact with ck_editor popups in Notes
// NEEDS TO CHANGE dijit/Dialog.js, in focus.watch
// Replace
//   if(node == topDialog.domNode || domClass.contains(node, "dijitPopup")){ return; }
// With
//   if(node == topDialog.domNode || domClass.contains(node, "dijitPopup") || domClass.contains(node, "cke_dialog_body")){ return; }
// And then rebuild dojo
// 7.3.0 Not usefull anymore with dojo 1.14 and 2 lines below

function pauseBodyFocus() {
  dojo.query(".cke_dialog_body").addClass("dijitPopup");
}

function resumeBodyFocus() {
  dojo.query(".cke_dialog_body").removeClass("dijitPopup");
}

// Function handling change in note size
function changeNoteSize(objName) {
  const
  collapse="iconButtonCollapseHide16 iconButtonCollapseHide iconSize16";
  const
  fullScreen="iconButtonCollapseOpen16 iconButtonCollapseOpen iconSize16";

  let
  noteDiv=document.getElementById(objName + "_Note");
  let
  mainDiv=document.getElementById("mainDiv");
  let
  newDiv;
  let
  count=1;

  if (document.getElementById("idIconButtonCollapseOpen").className == fullScreen) {

    mainDiv.style.visibility="hidden";
    document.getElementById("idIconButtonCollapseOpen").className=collapse;

    newDiv=document.createElement("div");
    newDiv.setAttribute("name",objName + "_Note");

    let
    temp=noteDiv.cloneNode(true);
    newDiv.appendChild(temp);

    noteDiv.id=objName + "_Note_Hidden";
    document.body.insertBefore(newDiv,document.body.firstChild);

    document.getElementById(objName + "_Note").style.width="98%";
    while (count <= newDiv.querySelectorAll("[id=idIconRemove]").length * 3 + 1) {
      newDiv.getElementsByClassName("roundedButtonSmall")[count].parentNode.style.visibility="collapse";
      count+=1;
    }
    document.getElementById(objName + "_Note_pane").style.height="94vh";
    document.getElementById(objName + "_Note_pane").style.overflow="auto";

  } else {
    document.getElementsByName(objName + "_Note")[0].remove();
    document.getElementById(objName + "_Note_Hidden").id=objName + "_Note";

    document.getElementById("idIconButtonCollapseOpen").className=fullScreen;
    mainDiv.style.visibility="visible";
  }
}
function addNote(reply, idParentNote, paramsRestore, mandatoryNoteOnStatusChange) {
  // A manually opened note must never continue a pending status-change save.
  if (!mandatoryNoteOnStatusChange) mandatoryNoteOnStatusChangeCallback=null;
  if (!paramsRestore) {
    if (document.querySelector('[id^="noteEditorMinimizedIcon_"]')) {
      var actionYes = function() {
        var minimizedIcon = document.querySelector('[id^="noteEditorMinimizedIcon_"]');
        if (minimizedIcon) {
          minimizedIcon.parentNode.removeChild(minimizedIcon);
        }
        completeAddNoteProcess(reply, idParentNote, paramsRestore, mandatoryNoteOnStatusChange);
      };
      var actionNo = function() {
        if (mandatoryNoteOnStatusChange) mandatoryNoteOnStatusChangeCallback=null;
        return;
      };
      showQuestion(i18n('noteIsMinimized'), actionYes, actionNo);
      return; 
    }
  }
  completeAddNoteProcess(reply, idParentNote, paramsRestore, mandatoryNoteOnStatusChange);
}

var mandatoryNoteOnStatusChangeCallback=null;

function openMandatoryNoteOnStatusChange(callback) {
  mandatoryNoteOnStatusChangeCallback=callback;
  addNote(false, null, null, true);
}

function completeAddNoteProcess (reply, idParentNote, paramsRestore, mandatoryNoteOnStatusChange) { 
  if (dijit.byId("noteToolTip")) {
    dijit.byId("noteToolTip").destroy();
    dijit.byId("noteNote").set("class","");
  }
  pauseBodyFocus();
  var callBack=function() {
    var editorType=dojo.byId("noteEditorType").value;
    if (editorType == "CK" || editorType == "CKInline") { // CKeditor type
      ckEditorReplaceEditor("noteNote",999);
    } else if (editorType == "text") {
      dijit.byId("noteNote").focus();
      dojo.byId("noteNote").style.height=(screen.height * 0.6) + 'px';
      dojo.byId("noteNote").style.width=(screen.width * 0.6) + 'px';
    } else if (dijit.byId("noteNoteEditor")) { // Dojo type editor
      dijit.byId("noteNoteEditor").set("class","input");
      dijit.byId("noteNoteEditor").focus();
      dijit.byId("noteNoteEditor").set("height",(screen.height * 0.6) + 'px'); // Works
      // on
      // first
      // time
      dojo.byId("noteNoteEditor_iframe").style.height=(screen.height * 0.6) + 'px'; // Works
      // after
      // first
      // time
    }
    dijit.byId('dialogNote').onCancel = function() {
      dijit.byId('dialogNote').hide();
      if (mandatoryNoteOnStatusChange) mandatoryNoteOnStatusChangeCallback=null;
      var minimizedIcon = dojo.query('[id^=noteEditorMinimizedIcon_]').shift();
      if (minimizedIcon) minimizedIcon.parentNode.removeChild(minimizedIcon);
    };
  };
  var params="&objectClass=" + dojo.byId('objectClass').value;
  params+="&objectId=" + dojo.byId("objectId").value;
  params+="&noteId="; // Null
  params+="&reply=" + reply;
  if (paramsRestore){
    params = paramsRestore;
	if (reply) params+="&reply=" + reply;
  }
  if (reply) {
    params+="&idParentNote=" + idParentNote;
  }
  if (mandatoryNoteOnStatusChange) params+="&mandatoryNoteOnStatusChange=true";
  loadDialog('dialogNote',callBack,true,params,true);
}

var savedNotesContent = {};
var savedParams = {};
function minimizeNoteEditor(translatedNoteText, objId, objClass, reply, idParentNote) {
  savedParams[objId] = { reply: reply, idParentNote: idParentNote };
  var dialog = document.getElementById('dialogNote');
  var noteTextarea = document.getElementById('noteNote');
  if (dialog) {
    var ckEditorInstance = CKEDITOR.instances.noteNote;
    if (ckEditorInstance) {
      savedNotesContent[objId] = ckEditorInstance.getData();
    } else if (noteTextarea) {
      var dojoEditor = dijit.byId("noteNoteEditor");
      if (dojoEditor) {
        savedNotesContent[objId] = dojoEditor.get("value");
      } else {
        savedNotesContent[objId] = noteTextarea.value || noteTextarea.innerHTML || noteTextarea.innerText;
      }
    }
	var selectedPrivacy = null;
	if (document.getElementById('notePrivacyPublic').checked) selectedPrivacy = '1';
	else if (document.getElementById('notePrivacyTeam').checked) selectedPrivacy = '2';
	else if (document.getElementById('notePrivacyPrivate').checked) selectedPrivacy = '3';    
	savedParams[objId].privacy = selectedPrivacy;
    dijit.byId('dialogNote').hide();
    var minimizedIcon = document.getElementById('noteEditorMinimizedIcon_' + objId);
    if (!minimizedIcon) {
      minimizedIcon = document.createElement('div');
      minimizedIcon.id = 'noteEditorMinimizedIcon_' + objId;
      var button = document.createElement('button');
      button.style.cursor = 'pointer';
      button.style.border = '1px solid #d3d3d3';
      button.style.borderRadius = '5px';
      button.style.background = 'none';  
      button.style.padding = '5px 10px'; 
      button.innerHTML = '✎ ' + i18n('dialogNote');
      button.onclick = function() { restoreNoteEditor(objId, objClass); };
      minimizedIcon.appendChild(button);
      minimizedIcon.style.position = 'fixed';
      minimizedIcon.style.bottom = '10px';
	  minimizedIcon.classList.add('minimized-icon');
	  var offset = getNextMinimizedIconOffset();
	  minimizedIcon.style.right = (10 + offset) + 'px';
      minimizedIcon.style.zIndex = '1000';
      minimizedIcon.style.backgroundColor = '#f0f0f0';
      minimizedIcon.style.padding = '5px';
      minimizedIcon.style.border = 'none';
      minimizedIcon.style.borderRadius = '5px';
      document.body.appendChild(minimizedIcon);
    } else {
      minimizedIcon.style.display = 'block';
    }
  }
}

function restoreNoteEditor(objId, objClass) {
  var minimizedIcon = document.getElementById('noteEditorMinimizedIcon_' + objId);
  if (minimizedIcon) {
    minimizedIcon.style.display = 'none'; 
  }
  var params = savedParams[objId];

  if (params) {
    var reply = params.reply;
    var idParentNote = params.idParentNote;
    addNote(reply, idParentNote, "&objectClass=" + objClass + "&objectId=" + objId);
  }
  setTimeout(function() {
      var noteTextarea = document.getElementById('noteNote');
      var ckEditorInstance = CKEDITOR.instances.noteNote;
      var noteInfoDiv = document.getElementById('noteInfoDiv');
      
      if (noteInfoDiv) {
        noteInfoDiv.style.display = 'block';
      }
      
      if (ckEditorInstance) {
        ckEditorInstance.setData(savedNotesContent[objId] || "");
      } else if (noteTextarea) {
        var dojoEditor = dijit.byId("noteNoteEditor");
        if (dojoEditor) {
          dojoEditor.set("value", savedNotesContent[objId] || "");
        } else {
          noteTextarea.value = savedNotesContent[objId] || "";
        }
      }
      if (params && params.privacy) {
        var privacyRestored = false;
        var attempts = 0;
        var maxAttempts = 20;
        var restorePrivacyInterval = setInterval(function() {
          attempts++;
          if (params.privacy === '1' && dijit.byId('notePrivacyPublic')) {
            dijit.byId('notePrivacyPublic').set('checked', true);
            privacyRestored = true;
          } else if (params.privacy === '2' && dijit.byId('notePrivacyTeam')) {
            dijit.byId('notePrivacyTeam').set('checked', true);
            privacyRestored = true;
          } else if (params.privacy === '3' && dijit.byId('notePrivacyPrivate')) {
            dijit.byId('notePrivacyPrivate').set('checked', true);
            privacyRestored = true;
          }
          
          if (privacyRestored || attempts >= maxAttempts) {
            clearInterval(restorePrivacyInterval);
          }
        }, 50);
      }
  }, 500);
}

function noteSelectPredefinedText(idPrefefinedText) {
  dojo.xhrGet({
    url:'../tool/getPredefinedText.php?id=' + idPrefefinedText + ''+addTokenIndexToUrl(),
    handleAs:"text",
    load:function(data) {
      var editorType=dojo.byId("noteEditorType").value;
      if (editorType == "CK" || editorType == "CKInline") { // CKeditor type
        CKEDITOR.instances['noteNote'].setData(data);
      } else if (editorType == "text") {
        dijit.byId('noteNote').set('value',data);
        dijit.byId('noteNote').focus();
      } else if (dijit.byId('noteNoteEditor')) {
        dijit.byId('noteNote').set('value',data);
        dijit.byId('noteNoteEditor').set('value',data);
        dijit.byId("noteNoteEditor").focus();
      }
    }
  });
}

function editNote(noteId, privacy) {
  if (document.querySelector('[id^="noteEditorMinimizedIcon_"]')) {
    var actionYes = function() {
      var minimizedIcon = document.querySelector('[id^="noteEditorMinimizedIcon_"]');
      if (minimizedIcon) {
        minimizedIcon.parentNode.removeChild(minimizedIcon);
      }
      completeEditNote(noteId, privacy);
    };
    var actionNo = function() {
      return;
    };
    showQuestion(i18n('noteIsMinimized'), actionYes, actionNo);
    return; 
  }
  completeEditNote(noteId, privacy);
}

function completeEditNote(noteId,privacy) { 
  if (dijit.byId("noteToolTip")) {
    dijit.byId("noteToolTip").destroy();
    dijit.byId("noteNote").set("class","");
  }
  pauseBodyFocus();
  var callBack=function() {
    // dijit.byId('notePrivacyPublic').set('checked', 'true');
    var editorType=dojo.byId("noteEditorType").value;
    if (editorType == "CK" || editorType == "CKInline") { // CKeditor type
      ckEditorReplaceEditor("noteNote",999);
    } else if (editorType == "text") {
      dijit.byId("noteNote").focus();
      dojo.byId("noteNote").style.height=(screen.height * 0.6) + 'px';
      dojo.byId("noteNote").style.width=(screen.width * 0.6) + 'px';
    } else if (dijit.byId("noteNoteEditor")) { // Dojo type editor
      dijit.byId("noteNoteEditor").set("class","input");
      dijit.byId("noteNoteEditor").focus();
      dijit.byId("noteNoteEditor").set("height",(screen.height * 0.6) + 'px'); // Works
      // on
      // first
      // time
      dojo.byId("noteNoteEditor_iframe").style.height=(screen.height * 0.6) + 'px'; // Works
      // after
      // first
      // time
    }
  };
  var params="&objectClass=" + dojo.byId('objectClass').value;
  params+="&objectId=" + dojo.byId("objectId").value;
  params+="&noteId=" + noteId;
  loadDialog('dialogNote',callBack,true,params,true);
}

function saveNote() {
  var editorType=dojo.byId("noteEditorType").value;
  if (editorType == "CK" || editorType == "CKInline") {
    noteEditor=CKEDITOR.instances['noteNote'];
    noteEditor.updateElement();
    var tmpCkEditor=noteEditor.document.getBody().getText();
    var tmpCkEditorData=noteEditor.getData();
    if (tmpCkEditor.trim() == "" && tmpCkEditorData.indexOf('<img') <= 0) {
      var msg=i18n('messageMandatory',new Array(i18n('Note')));
      noteEditor.focus();
      showAlert(msg);
      return;
    }
  } else if (dijit.byId("noteNoteEditor")) {
    if (dijit.byId("noteNote").getValue() == '') {
      dijit.byId("noteNoteEditor").set("class","input required");
      var msg=i18n('messageMandatory',new Array(i18n('Note')));
      dijit.byId("noteNoteEditor").focus();
      dojo.byId("noteNoteEditor").focus();
      showAlert(msg);
      return;
    }
  }

  // The callback is valid only for the dialog opened by openMandatoryNoteOnStatusChange().
  // A normal manually-created note always posts this flag as 0 and cannot save the object.
  var isMandatoryNoteOnStatusChange=(dojo.byId('mandatoryNoteOnStatusChange')
      && dojo.byId('mandatoryNoteOnStatusChange').value=='1');
  var callback=isMandatoryNoteOnStatusChange?mandatoryNoteOnStatusChangeCallback:null;
  var validationType=isMandatoryNoteOnStatusChange?'mandatoryNoteOnStatusChange':'note';
  loadContent("../tool/saveNote.php","resultDivMain","noteForm",true,validationType,null,null,function() {
    var status=dojo.byId('lastOperationStatus');
    mandatoryNoteOnStatusChangeCallback=null;
    if (callback && status && status.value=='OK') {
      // The note request has completed: allow the deferred object save to start.
      // This is intentionally restricted to the mandatory-note workflow.
      waitingForReply=false;
      callback();
    }
  });
  dijit.byId('dialogNote').hide();
  var minimizedIcon = document.querySelector('[id^="noteEditorMinimizedIcon_"]');
  if (minimizedIcon) {
    minimizedIcon.parentNode.removeChild(minimizedIcon);
	repositionMinimizedIcons();
  }
}

function removeNote(noteId) {
  var param="?noteId=" + noteId;
  var dest="resultDivMain";
  if (dojo.byId('objectClass') && dojo.byId("objectId")) {
    param+="&noteRefType=" + dojo.byId('objectClass').value;
    param+="&noteRefId=" + dojo.byId("objectId").value;
  } else if (dojo.byId('noteRefType') && dojo.byId('noteRefId')) {
    param+="&noteRefType=" + dojo.byId('noteRefType').value;
    param+="&noteRefId=" + dojo.byId('noteRefId').value;
    // dest="resultKanbanStreamDiv";
  }
  actionOK=function() {
    loadContent("../tool/removeNote.php" + param,dest,"noteForm",true,'note');
  };
  msg=i18n('confirmDelete',new Array(i18n('Note'),noteId));
  showConfirm(msg,actionOK);
}

// =============================================================================
// = Attachments
// =============================================================================

function addAttachment(attachmentType,refType,refId,mode, callback) {
  if(mode ==undefined)mode=false;
  var content="";
  if (dijit.byId('dialogAttachment')) content=dijit.byId('dialogAttachment').get('content');
  if (content == "") {
      callBack=function() {
        dojo.connect(dijit.byId("attachmentFile"),"onComplete",function(dataArray) {
          saveAttachmentAck(dataArray);
          if (typeof callback === "function") {
              callback(dataArray);
          }
        });
        dojo.connect(dijit.byId("attachmentFile"),"onProgress",function(data) {
          saveAttachmentProgress(data);
        });
        dojo.connect(dijit.byId("attachmentFile"),"onError",function(__evt__) {
          hideWait();
          showError(i18n("uploadUncomplete"));
        });
		//#10328--remi
		//why dose this below?
		//addAttachment(attachmentType,refType,refId);
        if (isHtml5() && dijit.byId('attachmentFileDirect')) {
          dijit.byId('attachmentFileDirect').reset();
          dijit.byId('attachmentFileDirect').addDropTarget(dojo.byId('attachmentFileDropArea'));
        }
        dojo.byId("attachmentId").value="";
        dojo.byId("attachmentRefType").value=(refType) ? refType : ((dojo.byId('objectClass')) ? dojo.byId('objectClass').value : 'User');
        dojo.byId("attachmentRefId").value=(refId) ? refId : ((dojo.byId('objectId')) ? dojo.byId("objectId").value : dojo.byId("userMenuIdUser").value);
        dojo.byId("attachmentType").value=attachmentType;
        dojo.byId("attachmentMode").value=mode;
        if (dojo.byId("attachmentFileName")) {
          dojo.byId("attachmentFileName").innerHTML="";
        }
        dojo.style(dojo.byId('downloadProgress'),{display:'none'});
        
        if (attachmentType == 'file') {
          if (dijit.byId("attachmentFile")) {
            dijit.byId("attachmentFile").reset();
            if (!isHtml5()) {
              enableWidget('dialogAttachmentSubmit');
            } else {
              disableWidget('dialogAttachmentSubmit');
            }
          }
          dojo.style(dojo.byId('dialogAttachmentFileDiv'),{display:'block'});
          dojo.style(dojo.byId('dialogAttachmentLinkDiv'),{display:'none'});
        } else {
          if (dijit.byId("attachmentLink")) {
            dijit.byId("attachmentLink").set('value',null);
          }
          dojo.style(dojo.byId('dialogAttachmentFileDiv'),{display:'none'});
          dojo.style(dojo.byId('dialogAttachmentLinkDiv'),{display:'block'});
          enableWidget('dialogAttachmentSubmit');
        }
        
        if (dijit.byId("attachmentDescription").get('checked') == true && refType != 'SubTask') {
          dijit.byId("attachmentDescription").set('disabled',false);
          dijit.byId('attachmentPrivacyPrivate').set('disabled',false);
        }
        dijit.byId("attachmentDescription").set('value',null);
        dijit.byId("dialogAttachment").set('title',i18n("dialogAttachment"));
        dijit.byId('attachmentPrivacyPublic').set('checked','true');
        if (refType == 'SubTask') {
          dijit.byId("attachmentDescription").set('disabled',true);
          dijit.byId('attachmentPrivacyPrivate').set('disabled',true);
        }

        dijit.byId("dialogAttachment").show();
      };
      var params=(mode)?'&attachmentMode='+mode:'';
      loadDialog('dialogAttachment',callBack, null, params);
      return;
  }
  dojo.byId("attachmentId").value="";
  dojo.byId("attachmentRefType").value=(refType) ? refType : ((dojo.byId('objectClass')) ? dojo.byId('objectClass').value : 'User');
  dojo.byId("attachmentRefId").value=(refId) ? refId : ((dojo.byId('objectId')) ? dojo.byId("objectId").value : dojo.byId("userMenuIdUser").value);
  dojo.byId("attachmentType").value=attachmentType;
  dojo.byId("attachmentMode").value=mode;
  if (dojo.byId("attachmentFileName")) {
    dojo.byId("attachmentFileName").innerHTML="";
  }
  dojo.style(dojo.byId('downloadProgress'),{
    display:'none'
  });
  if (attachmentType == 'file') {
    if (dijit.byId("attachmentFile")) {
      dijit.byId("attachmentFile").reset();
      if (!isHtml5()) {
        enableWidget('dialogAttachmentSubmit');
      } else {
        disableWidget('dialogAttachmentSubmit');
      }
    }
    dojo.style(dojo.byId('dialogAttachmentFileDiv'),{
      display:'block'
    });
    dojo.style(dojo.byId('dialogAttachmentLinkDiv'),{
      display:'none'
    });
  } else {
    if (dijit.byId("attachmentLink")) {
      dijit.byId("attachmentLink").set('value',null);
    }
    dojo.style(dojo.byId('dialogAttachmentFileDiv'),{
      display:'none'
    });
    dojo.style(dojo.byId('dialogAttachmentLinkDiv'),{
      display:'block'
    });
    enableWidget('dialogAttachmentSubmit');
  }
  if (dijit.byId("attachmentDescription").get('checked') == true && refType != 'SubTask') {
    dijit.byId("attachmentDescription").set('disabled',false);
    dijit.byId('attachmentPrivacyPrivate').set('disabled',false);
  }
  dijit.byId("attachmentDescription").set('value',null);
  dijit.byId("dialogAttachment").set('title',i18n("dialogAttachment"));
  dijit.byId('attachmentPrivacyPublic').set('checked','true');
  if (refType == 'SubTask') {
    dijit.byId("attachmentDescription").set('disabled',true);
    dijit.byId('attachmentPrivacyPrivate').set('disabled',true);
  }

  dijit.byId("dialogAttachment").show();
}

function addAttachmentWithUpdate(btnElement, refType, refId, mode) {
  btnElement.style.pointerEvents = 'none';
  btnElement.style.opacity = '0.5';
  addAttachment('file', refType, refId, mode);
}


function changeAttachment(list) {
  if (list.length > 0) {
    htmlList="";
    for (var i=0;i < list.length;i++) {
      htmlList+=list[i]['name'] + '<br/>';
    }
    dojo.byId('attachmentFileName').innerHTML=htmlList;
    enableWidget('dialogAttachmentSubmit');
    dojo.byId('attachmentFile').height="200px";
  } else {
    dojo.byId('attachmentFileName').innerHTML="";
    disableWidget('dialogAttachmentSubmit');
    dojo.byId('attachmentFile').height="20px";
  }
}

var cancelDupplicate=false;
function saveAttachment(direct,idName) {
  // disableWidget('dialogAttachmentSubmit');
  if (cancelDupplicate) return;
  cancelDupplicate=true;
  if (!isHtml5()) {
    if (dojo.isIE && dojo.isIE <= 8) {
      dojo.byId('attachmentForm').submit();
    }
    showWait();
    dijit.byId('dialogAttachment').hide();
    return true;
  }
  if (dojo.byId("attachmentType") && dojo.byId("attachmentType").value == 'file' && dojo.byId('attachmentFileName') && dojo.byId('attachmentFileName').innerHTML == "") {
    return false;
  }

  if (direct) {
    if (dijit.byId(idName)) {
      if (dijit.byId(idName).getFileList().length > 20) {
        showAlert(i18n('uploadLimitNumberFiles'));
        return false;
      }
    }
  } else {
    if (dijit.byId("attachmentFile")) {
      if (dijit.byId("attachmentFile").getFileList().length > 20) {
        showAlert(i18n('uploadLimitNumberFiles'));
        return false;
      }
    }
  }
  dojo.style(dojo.byId('downloadProgress'),{
    display:'block'
  });
  showWait();
  dijit.byId('dialogAttachment').hide();
  return true;
}

function saveAttachmentAck(dataArray) {
  if (dataArray == undefined) {
    dojo.style(dojo.byId('downloadProgress'),{
      display:'none'
    });
    dojo.byId('resultAck').value=i18n("uploadUncomplete");
    hideWait();
    return;
  }
  if (!isHtml5()) {
    resultFrame=document.getElementById("resultPost");
    resultText=resultPost.document.body.innerHTML;
    dojo.byId('resultAck').value=resultText;
    loadContent("../tool/ack.php","resultDivMain","attachmentAckForm",true,'attachment');
    return;
  }
  dijit.byId('dialogAttachment').hide();
  if (dojo.isArray(dataArray)) {
    result=dataArray[0];
  } else {
    result=dataArray;
  }
  
  if (dojo.byId('objectClassManual') && (dojo.byId('objectClassManual').value === 'ProjectDashboard' || dojo.byId('objectClassManual').value === 'ProjectDetail')) {
      if (result && result.message) {
        var modeElement = dojo.byId("attachmentMode");
        var mode = modeElement ? modeElement.value : null;       
        if (mode === 'profilePic') {       
          var refTypeMatch = result.message.match(/id=["']lastSaveRefType["']\s+value=["'](\w+)["']/);
          var refIdMatch = result.message.match(/id=["']lastSaveRefId["']\s+value=["'](\d+)["']/);
          var photoIdMatch = result.message.match(/id=["']lastSaveId["']\s+value=["'](\d+)["']/);          
          if (refTypeMatch && refTypeMatch[1] === 'Project' && refIdMatch && photoIdMatch) {
            var projectId = parseInt(refIdMatch[1], 10);
            var photoId = parseInt(photoIdMatch[1], 10);
            var photoUrl = "../tool/download.php?class=Attachment&id=" + photoId + addTokenIndexToUrl();
            var tile = document.getElementById('project_' + projectId);
            if (tile) {
              var dateSection = dojo.byId('objectClassManual').value === 'ProjectDetail' ?  tile.querySelector('.detail-photo') : tile.querySelector('.tile-dates-section');
              if (dateSection) {
                dateSection.style.transition = 'background 0.3s ease';
                dateSection.style.backgroundImage = 'url("' + photoUrl + '")';
                dateSection.style.backgroundPosition = 'center';
                dateSection.style.backgroundSize = 'cover';
                dateSection.style.backgroundRepeat = 'no-repeat';
              }             
              var btn = document.getElementById('addAttachementProjectPic_' + projectId);
              if (btn) {
                btn.style.pointerEvents = 'auto';
                btn.style.opacity = '1';
                btn.dataset.photoId = photoId;
                btn.dataset.projectId = projectId;
                btn.removeAttribute('onclick');
                btn.onclick = function(event) {
                  event.stopPropagation();
                  removeAttachmentWithConfirm(this, photoId, projectId);
                };
                btn.title = i18n('removeAttachementProjectPic');
                btn.innerHTML = '<div class="iconRemove16 imageColorNewGui iconRemove iconSize16"></div>';
              }
            } 
          }
        }
      }
    }
  
  dojo.style(dojo.byId('downloadProgress'),{
    display:'none'
  });
  dojo.byId('resultAck').value=result.message;
  loadContent("../tool/ack.php","resultDivMain","attachmentAckForm",true,'attachment');
  loadContent("../view/menuUserTop.php","drawMenuUser");
}

function saveAttachmentProgress(data) {
  done=data.bytesLoaded;
  total=data.bytesTotal;
  if (total) {
    progress=done / total;
  }
  dijit.byId('downloadProgress').set('value',progress);
}

function removeAttachment(attachmentId, onSuccessCallback) {
  var content="";
  if (dijit.byId('dialogAttachment')) content=dijit.byId('dialogAttachment').get('content');
  if (content == "") {
    callBack=function() {
      dojo.connect(dijit.byId("attachmentFile"), "onComplete", function(dataArray) {
        saveAttachmentAck(dataArray);
      });
      dojo.connect(dijit.byId("attachmentFile"), "onProgress", function(data) {
        saveAttachmentProgress(data);
      });
      dijit.byId('dialogAttachment').hide();
      removeAttachment(attachmentId,onSuccessCallback);
    };
    loadDialog('dialogAttachment', callBack);
    return;
  }
  
  dojo.byId("attachmentId").value = attachmentId;
  dojo.byId("attachmentRefType").value = dojo.byId('objectClass').value;
  dojo.byId("attachmentRefId").value = dojo.byId("objectId").value;

  actionOK = function(reftype, refId, idResource) {
    loadContent("../view/menuUserTop.php", "drawMenuUser");
    if (dojo.byId('refreshSTDivValues')) {
      var idSubTask = dojo.byId('refreshSTDivValues').value;
      setTimeout('refreshSubTaskAttachment(' + idSubTask + ')', 200);
    }
    if (typeof onSuccessCallback === "function") {
      loadContent("../tool/removeAttachment.php", "resultDivMain", "attachmentForm", true, 'attachment', null, null, function() {
        onSuccessCallback(attachmentId);
      });
    } else {
      loadContent("../tool/removeAttachment.php", "resultDivMain", "attachmentForm", true, 'attachment');
    }
  };

  msg = i18n('confirmDelete', [i18n('Attachment'), attachmentId]);
  showConfirm(msg, actionOK);
}


function removeProjectPhotoFromTile(projectId) { 
  var tile = document.getElementById('project_' + projectId);
  if (!tile) return;
  var dateSection =  dojo.byId('objectClassManual') && dojo.byId('objectClassManual').value === 'ProjectDetail' ?  tile.querySelector('.detail-photo') : tile.querySelector('.tile-dates-section'); 
  if (!dateSection) return;
  var projectColor = tile.dataset.projectColor || '#999999';
  dateSection.style.transition = 'background 0.3s ease';
  dateSection.style.background = 'linear-gradient(135deg, ' + projectColor + ' 0%, #e9ecef 100%)';
  var btn = document.getElementById('addAttachementProjectPic_' + projectId);
  if (btn) {
    btn.style.pointerEvents = 'auto';
    btn.style.removeProperty('opacity');
    delete btn.dataset.photoId;
    btn.dataset.projectId = projectId;
    btn.removeAttribute('onclick');
    btn.onclick = function(event) {
      event.stopPropagation();
      addAttachmentWithUpdate(this, 'Project', projectId, 'profilePic');
    };
    btn.title = i18n('addAttachementProjectPic');
    btn.innerHTML = '<div class="iconAdd16 imageColorNewGui iconAdd iconSize16"></div>';
  }
}

function removeAttachmentWithConfirm(btnElement, vIdPhoto, projectId) {
  removeAttachment(vIdPhoto, function(id) {
    btnElement.style.pointerEvents = 'none';
    btnElement.style.opacity = '0.5';
    removeProjectPhotoFromTile(projectId);
  });
}

function editAttachment(id) {
  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
  var callBack=function() {
    dojo.xhrGet({
      url:'../tool/getSingleData.php?dataType=editAttachment&id=' + id + ''+addTokenIndexToUrl(),
      handleAs:"text",
      load:function(data) {
        dijit.byId('attachmentDescriptionEdit').set('value',data);
      }
    });
    dijit.byId("dialogAttachmentEdit").show();
  };
  var params="&id=" + id;
  params+="&mode=edit";
  loadDialog('dialogAttachmentEdit',callBack,false,params);
}

function saveAttachmentEdit() {
  var privacy=0;
  if (dijit.byId('attachmentPrivacyPublicEdit').get('checked')) privacy=1;
  if (dijit.byId('attachmentPrivacyTeamEdit').get('checked')) privacy=2;
  if (dijit.byId('attachmentPrivacyPrivateEdit').get('checked')) privacy=3;
  var url='../tool/saveAttachmentEdit.php';
  url+='?privacy=' + privacy;
  loadContent(url,"resultDivMain","attachmentFormEdit",true,"attachment");
  dijit.byId('dialogAttachmentEdit').hide();
}

// =============================================================================
// = Links
// =============================================================================

var noRefreshLink=false;
function addLink(classLink,defaultLink) {
  if (dojo.byId('objectClass') && dojo.byId('objectClass').value == 'Requirement' && classLink == 'TestCase' && checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
  if (!classLink) {
    var params="&objectClass=" + dojo.byId('objectClass').value + "&objectId=" + dojo.byId("objectId").value;
  }
  loadDialog('dialogLink',function() {
    noRefreshLink=true;
    var objectClass=dojo.byId('objectClass').value;
    var objectId=parseInt(dojo.byId("objectId").value);
    var message=i18n("dialogLink");
    dojo.byId("linkId").value="";
    dojo.byId("linkRef1Type").value=objectClass;
    dojo.byId("linkRef1Id").value=objectId;
    dojo.style(dojo.byId('linkDocumentVersionDiv'),{
      display:'none'
    });
    dijit.byId("linkDocumentVersion").reset();
    if (classLink) {
      dojo.byId("linkFixedClass").value=classLink;
      message=i18n("dialogLinkRestricted",new Array(i18n(objectClass),objectId,i18n(classLink)));
      dijit.byId("linkRef2Type").setDisplayedValue(i18n(classLink));
      lockWidget("linkRef2Type");
      noRefreshLink=false;
      refreshLinkList();
    } else {
		dojo.byId("linkFixedClass").value="";
		var storedLinkType = (dojo.byId("linkStoredType")) ? dojo.byId("linkStoredType").value : "";
	
        if (storedLinkType) {
		  dijit.byId("linkRef2Type").set('value', storedLinkType);
		} else if (defaultLink) {
	      dijit.byId("linkRef2Type").set('value', defaultLink);
	  	} else {
		  dijit.byId("linkRef2Type").reset();
		}
	
		message=i18n("dialogLinkExtended",new Array(i18n(objectClass),objectId));
		unlockWidget("linkRef2Type");
		noRefreshLink=false;
		refreshLinkList();
    }
    dijit.byId("dialogLink").set('title',message);
    dijit.byId("linkComment").set('value','');
    if (0 && dojo.byId('objectClass').value=='Prospect' && classLink=='ProspectEvent') {
      setTimeout("newDetailItemLink();",100);
      setTimeout('dijit.byId("dialogLink").hide();',200);
    } else {
      dijit.byId("dialogLink").show();
      disableWidget('dialogLinkSubmit');
    }
  },true,params,true);
}

function selectLinkItem() {
  var nbSelected=0;
  list=dojo.byId('linkRef2Id');
  if (dojo.byId("linkRef2Type").value == "Document") {
    if (list.options) {
      selected=new Array();
      for (var i=0;i < list.options.length;i++) {
        if (list.options[i].selected) {
          selected.push(list.options[i].value);
          nbSelected++;
        }
      }
      if (selected.length == 1) {
        dijit.byId("linkDocumentVersion").reset();
        refreshList('idDocumentVersion','idDocument',selected[0],null,'linkDocumentVersion',false);
        dojo.style(dojo.byId('linkDocumentVersionDiv'),{
          display:'block'
        });
      } else {
        dojo.style(dojo.byId('linkDocumentVersionDiv'),{
          display:'none'
        });
        dijit.byId("linkDocumentVersion").reset();
      }
    }
  } else {
    if (list.options) {
      for (var i=0;i < list.options.length;i++) {
        if (list.options[i].selected) {
          nbSelected++;
        }
      }
    }
    dojo.style(dojo.byId('linkDocumentVersionDiv'),{
      display:'none'
    });
    dijit.byId("linkDocumentVersion").reset();
  }
  if (nbSelected > 0) {
    enableWidget('dialogLinkSubmit');
  } else {
    disableWidget('dialogLinkSubmit');
  }
}

function refreshLinkList(selected) {
  if (noRefreshLink) return;
  disableWidget('dialogLinkSubmit');
  var url='../tool/dynamicListLink.php';
  if (selected) {
    url+='?selected=' + selected;
  }
  if (!selected) {
    selectLinkItem();
  }
  loadContent(url,'dialogLinkList','linkForm',false);
}

function saveLink() {
  if (dojo.byId("linkRef2Id").value == "") return;
  var fixedClass=(dojo.byId('linkFixedClass')) ? dojo.byId('linkFixedClass').value : '';
  loadContent("../tool/saveLink.php","resultDivMain","linkForm",true,'link' + fixedClass);
  dijit.byId('dialogLink').hide();
}

function removeLink(linkId,refType,refId,refTypeName,fixedClass) {
  if (dojo.byId('objectClass') && dojo.byId('objectClass').value == 'Requirement' && fixedClass == 'TestCase' && checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
  actionOK=function() {
    if (fixedClass && fixedClass == refType) {
      loadContent("../tool/removeLink.php?linkId=" + linkId + "&linkRef1Type=" + dojo.byId('objectClass').value + "&linkRef1Id=" + dojo.byId("objectId").value + "&linkRef2Type=" + refType
          + "&linkRef2Id=" + refId,"resultDivMain",null,true,'link' + fixedClass);
    } else {
      loadContent("../tool/removeLink.php?linkId=" + linkId + "&linkRef1Type=" + dojo.byId('objectClass').value + "&linkRef1Id=" + dojo.byId("objectId").value + "&linkRef2Type=" + refType
          + "&linkRef2Id=" + refId,"resultDivMain",null,true,'link');
    }
  };
  if (!refTypeName) {
    refTypeName=i18n(refType);
  }
  msg=i18n('confirmDeleteLink',new Array(refTypeName,refId));
  showConfirm(msg,actionOK);
}

function editLink(linkId,id,classLink) {
  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
  var objectClass=dojo.byId('objectClass').value;
  var objectId=parseInt(dojo.byId("objectId").value);
  var callBack=function() {
    dojo.xhrGet({
      url:'../tool/getSingleData.php?dataType=editLink&idLink=' + linkId + ''+addTokenIndexToUrl(),
      handleAs:"text",
      load:function(data) {
        dijit.byId('linkComment').set('value',data);
        if (classLink) {
          dojo.byId("linkFixedClass").value=classLink;
        }
      }
    });
    dijit.byId("dialogLink").show();
  };
  var params="&id=" + id;
  params+="&linkId=" + linkId;
  params+="&mode=edit";
  params+="&objId=" + objectId;
  message=i18n("dialogEditLinkExtended",new Array(i18n(objectClass),objectId));
  loadDialog('dialogLink',callBack,false,params);
  dijit.byId("dialogLink").set('title',message);
}

function removeFollowup(followupId,all) {
  var param="?messageFollowup=" + followupId;
  param+="&deleteAll=" + all;

  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
  actionOK=function() {
    loadContent("../tool/removeMessageFollowup.php" + param,"resultDivMain","objectForm",true,'MessageLegalFollowup');
  };

  msg=i18n('confirmRemoveMessageFollowup');
  showConfirm(msg,actionOK);
}

function addProspectEvent() {
  if(dojo.byId("selectionIdMultipleInsert")){
	//#10589 || When pop-up is opened, selection is not displayed any more in the list : selection should be preserved, even after save (like all other Multiple Updates)
    // checkFormChangeInProgress break all ! 
  }else{
	if (checkFormChangeInProgress()) {
	  showAlert(i18n('alertOngoingChange'));
	  return;
	}
  }
  var callBack=function() {
    ckEditorReplaceEditor("eventDescription",989);
  };
  var params="&objectClass=" + dojo.byId('objectClass').value;
  if(dojo.byId("selectionIdMultipleInsert")){
    var idSelect = dojo.byId("selectionIdMultipleInsert").value;
    //idSelect = idSelect.replace(/,+$/,'');
    params+="&objectId="+idSelect;
  }else{
    params+="&objectId=" + dojo.byId("objectId").value;
  }
  loadDialog('dialogProspectEvent',callBack,true,params,true);
}

function editProspectEvent(eventId) {
  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
  var callBack=function() {
    ckEditorReplaceEditor("eventDescription",989);
  };
  var params="&objectClass=" + dojo.byId('objectClass').value;
  params+="&objectId=" + dojo.byId("objectId").value;
  params+="&eventId=" + eventId;
  loadDialog('dialogProspectEvent',callBack,true,params,true);
}

function saveProspectEvent() {
  var formVar=dijit.byId('prospectEventForm');
  if (formVar.validate() && dijit.byId('eventName').get('value')!=""){
    eventEditor=CKEDITOR.instances['eventDescription'];
    eventEditor.updateElement();
//    var tmpCkEditor=eventEditor.document.getBody().getText();
//    var tmpCkEditorData=eventEditor.getData();
	var callback=function(){
	  hideWait();
	};
    loadContent("../tool/saveProspectEvent.php","resultDivMain","prospectEventForm",true,'prospectEvent',null,null,callback);
    dijit.byId('dialogProspectEvent').hide();
  } else {
    showAlert(i18n("alertInvalidForm"));
    return;
  }
}

function removeProspectEvent(eventId) {
  var param="?eventId=" + eventId;
  param+="&action=remove";
  actionOK=function() {
    loadContent("../tool/saveProspectEvent.php" + param,"resultDivMain","prospectEventForm",true,'prospectEvent');
  };
  msg=i18n('confirmDelete',new Array(i18n('ProspectEvent'),eventId));
  showConfirm(msg,actionOK);
}
