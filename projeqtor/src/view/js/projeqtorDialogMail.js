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
//= Columns Mail
//=============================================================================

function dialogMailToOtherChange() {
  var show = dijit.byId('dialogMailToOther').get('checked');
  if (show) {
    showField('dialogOtherMail');
    showField('otherMailDetailButton');
  } else {
    hideField('dialogOtherMail');
    hideField('otherMailDetailButton');
  }
}

function mailerTextEditor(code) {
  var callBack = function() {
    var codeParam = dojo.byId("codeParam");
    codeParam.value = code;
    var editorType = dojo.byId("mailEditorType").value;
    if (editorType == "CK" || editorType == "CKInline") { // CKeditor type
      ckEditorReplaceEditor("mailEditor", 999);
    } else if (editorType == "text") {
      dijit.byId("mailEditor").focus();
      dojo.byId("mailEditor").style.height = (screen.height * 0.6) + 'px';
      dojo.byId("mailEditor").style.width = (screen.width * 0.6) + 'px';
    } else if (dijit.byId("mailMessageEditor")) { // Dojo type editor
      dijit.byId("mailMessageEditor").set("class", "input");
      dijit.byId("mailMessageEditor").focus();
      dijit.byId("mailMessageEditor").set("height", (screen.height * 0.6) + 'px'); // Works
      // on
      // first
      // time
      dojo.byId("mailMessageEditor_iframe").style.height = (screen.height * 0.6) + 'px'; // Works
      // after
      // first
      // time
    }
    dojo.byId("mailEditor").innerHTML = dojo.byId(code).value;
  };
  loadDialog('dialogMailEditor', callBack, true, null, true, true);
}

function saveMailMessage() {
  var codeParam = dojo.byId("codeParam").value;
  var editorType = dojo.byId("mailEditorType").value;
  if (editorType == "CK" || editorType == "CKInline") {
    noteEditor = CKEDITOR.instances['mailEditor'];
    noteEditor.updateElement();
    var tmpCkEditor = noteEditor.document.getBody().getText();
    var tmpCkEditorData = noteEditor.getData();
    if (tmpCkEditor.trim() == "" && tmpCkEditorData.indexOf('<img') <= 0) {
      var msg = i18n('messageMandatory', new Array(i18n('Message')));
      noteEditor.focus();
      showAlert(msg);
      return;
    }
  } else if (dijit.byId("messageMailEditor")) {
    if (dijit.byId("mailEditor").getValue() == '') {
      dijit.byId("messageMailEditor").set("class", "input required");
      var msg = i18n('messageMandatory', new Array(i18n('Message')));
      dijit.byId("messageMailEditor").focus();
      dojo.byId("messageMailEditor").focus();
      showAlert(msg);
      return;
    }
  }
  var callBack = function() {
    dojo.byId(codeParam).value = tmpCkEditorData;
    dojo.byId(codeParam + "_display").innerHTML = tmpCkEditorData;
  };
  loadDiv("../tool/saveParameter.php", "resultDivMain", "parameterForm", callBack);
  dijit.byId('dialogMailEditor').hide();
}

var doNotTriggerEmailChange = false;
function findAutoEmail() {
  if (doNotTriggerEmailChange == true) return;
  var adress = dijit.byId('dialogOtherMail').get('value');
  var regex = /,[ ]*|;[ ]*/gi;
  adress = adress.replace(regex, ",");
  dojo.xhrGet({
    url: '../tool/saveFindEmail.php?&isId=false&adress=' + adress + '' + addTokenIndexToUrl(),
    load: function(data, args) {
      var email = data;
      doNotTriggerEmailChange = true;
      dijit.byId('dialogOtherMail').set('value', email);
      doNotTriggerEmailChange = false;
    }
  });
}

function dialogMailIdEmailChange() {
  if (doNotTriggerEmailChange == true) return;
  doNotTriggerEmailChange = true;
  var value = dijit.byId('dialogOtherMail').get('value');
  var id = dijit.byId('dialogMailObjectIdEmail').get('value');
  id = id + ',' + value;
  dojo.xhrGet({
    url: '../tool/saveFindEmail.php?&isId=true&id=' + id + '' + addTokenIndexToUrl(),
    load: function(data, args) {
      var email = data;
      dijit.byId('dialogOtherMail').set('value', email);
      doNotTriggerEmailChange = false;
    }
  });
}
// end

// damian #2936
function stockEmailCurrent() {
  var adress = dijit.byId('dialogOtherMail').get('value');
  var adressSplit = adress.split(',');
  adressSplit.forEach(function(emailSplit) {
    if (stockEmailHistory.indexOf(emailSplit) == -1) {
      stockEmailHistory.push(emailSplit);
    }
  });
}

function compareEmailCurrent() {
  if (stockEmailHistory.length > 0) {
    var inputEmail = dijit.byId('dialogOtherMail').get('value');
    var split = inputEmail.split(',');
    inputEmail = split[split.length - 1];
    var count = 0;
    var email = "";
    var divCount = 0;
    // var display = '';
    stockEmailHistory.forEach(function(element) {
      count++;
      if (split.indexOf(element) <= -1) {
        divCount++;
        if (divCount < 0) {
          dojo.byId('dialogOtherMailHistorical').style.display = 'none';
        }
        if (element.search(inputEmail) > -1) {
          dojo.byId('dialogOtherMailHistorical').style.display = 'block';
          email += '<div class="emailHistorical" id="email' + count + '" style="cursor:pointer;"' + 'onclick="selectEmailHistorical(\'' + element + '\')">' + element + '</div>';
          dojo.byId('dialogOtherMailHistorical').innerHTML = email;
        }
      } else {
        divCount--;
      }
      if (divCount > 7) {
        dojo.byId('dialogOtherMailHistorical').style.height = '100px';
      } else {
        dojo.byId('dialogOtherMailHistorical').style.height = 'auto';
      }
    });
  } else {
    dojo.byId('dialogOtherMailHistorical').style.display = 'none';
  }
}

function hideEmailHistorical() {
  setTimeout(function() {
    dojo.byId('dialogOtherMailHistorical').style.display = 'none';
  }, 200);
}

function selectEmailHistorical(email) {
  var currentValue = dijit.byId('dialogOtherMail').get("value");
  var tab = currentValue.split(',');
  var tabLength = tab.length;
  var newValue = "";
  if (currentValue != "") {
    if (tabLength > 1) {
      for (var i = 0; i < tabLength - 1; i++) {
        if (tab[i].search('@') > -1) {
          newValue += tab[i] + ',';
        }
      }
    }
    newValue += email + ',';
    dijit.byId('dialogOtherMail').set("value", newValue);
  } else {
    dijit.byId('dialogOtherMail').set("value", email + ',');
  }
  dojo.byId('dialogOtherMailHistorical').style.display = 'none';
}
// end #2936

function extractEmails(str) {
  var current = '';
  var result = '';
  var name = false;
  for (var i = 0; i < str.length; i++) {
    car = str.charAt(i);
    if (car == '"') {
      if (name == true) {
        name = false;
        current = "";
      } else {
        if (current != '') {
          if (result != '') {
            result += ', ';
          }
          result += trimTag(current);
          current = '';
        }
        name = true;
      }
    } else if (name == false) {
      if (car == ',' || car == ';' || car == ' ') {
        if (current != '') {
          if (result != '') {
            result += ', ';
          }
          result += trimTag(current);
          current = '';
        }
      } else {
        current += car;
      }
    }
  }
  if (current != "") {
    if (result != '') {
      result += ', ';
    }
    result += trimTag(current);
  }
  return result;
}

function sendMail(mode) {
  if (mode == undefined) mode = false;
  repositionMinimizedIcons();
  var checkotherMail = dijit.byId('dialogMailToOther').get("checked");
  var otherMail = dijit.byId('dialogOtherMail').get("value");
  var idEmailTemplate = dijit.byId('selectEmailTemplate').get("value");
  otherMail = otherMail.trim();
  var emailList = otherMail
   .split(',')
   .map(e => e.trim()) 
   .filter(e => e.length > 0);
   
   var emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
   
   var invalidEmails = emailList.filter(e => {
     var isInvalid = e.includes(" ") || !emailRegex.test(e);
     return isInvalid;
   });
   
  if (checkotherMail && invalidEmails.length > 0) {
	var msgError = invalidEmails.join(", ");
	  showAlert(i18n("errorMailFormat",new Array(msgError)));
  } else {
	  if (dojo.byId('maxSizeNoconvert') && dojo.byId('totalSizeNoConvert').value > Number(dojo.byId('maxSizeNoconvert').value)) {
	    showAlert(i18n('errorAttachmentSize'));
	    return;
	  } else {
	    var callBack = function() {
	      hideWait();
	      loadContentStream();
	    };
	    var selectedEmails = [];
	    var receiverContainer = document.getElementById('receiverTableContainer');
	    if (receiverContainer) {
	      dojo.query("[id^='dialogMailCheckReceiver_']", receiverContainer).forEach(function(node) {
	        var widget = dijit.byId(node.id);
	        if (widget && widget.get('checked')) {
	          var tr = node.closest('tr');
	          if (tr) {
	            var tdEmail = tr.querySelectorAll('td')[1];
	            if (tdEmail) {
	              var email = tdEmail.textContent.trim();
	              if (email && !email.includes(i18n('noEmail'))) {
	                selectedEmails.push(email);
	              }
	            }
	          }
	        }
	      });
	    }
	    var selectedReceivers = selectedEmails.join('##');
	    if (dojo.byId('dialogMailSelectedReceivers')) dojo.byId('dialogMailSelectedReceivers').value = selectedReceivers;
	    if (mode == "DialogMail") {
	      loadContent("../tool/sendMail.php?className=Mailable&idEmailTemplate=" + idEmailTemplate, "resultDivMain", "mailForm", true, 'mail', false, false, callBack);
	    } else {
	      loadContent("../tool/sendMail.php?className=Mailable&mode='DialogMail'&idEmailTemplate=" + idEmailTemplate, "resultDivMain", "mailForm", true, 'mail', false, false, callBack);
	    }
	    dijit.byId("dialogMail").hide();
	
	  }
	}
}

function removeAttachmentSendMail(objectClass, objectId, name) {
  if (name == undefined) name = false;
  if (dialogSendMailIconized == false) {

    var fileName = String(name).replace("'", "");

    var size = (dojo.byId('size_dialogMail' + fileName)) ? dojo.byId('size_dialogMail' + fileName).value : 0;
    var totalSize = dojo.byId('totalSizeNoConvert').value;
    var maxSize = Number(dojo.byId('maxSizeNoconvert').value);
    totalSize = Number(totalSize) - Number(size);
    var noConvert = totalSize;
    if (totalSize != 0) {
      totalSize = octetConvertSize(totalSize);
    }
    if (maxSize < noConvert) {
      dojo.byId('infoSize').style.color = "red";
      dojo.byId('totalSize').style.color = "red";
    } else if ((maxSize >= noConvert) || noConvert == 0) {
      dojo.byId('infoSize').style.color = "green";
      dojo.byId('totalSize').style.color = "green";
    }
    dojo.byId('totalSizeNoConvert').value = noConvert;
    dojo.byId('totalSize').value = totalSize;


    dojo.xhrGet({
      url: "../tool/removeAttachmentSendMail.php?objectClass=" + objectClass + "&objectId=" + objectId + "&name=" + name + addTokenIndexToUrl(),
      handleAs: "text",
      load: function(data, args) {
        if (name != false) {
          refreshAttachmentSendMail('false', objectClass, objectId, true);
        }
      },
      error: function() {
      }
    });
  }
}

function showMail(paramsRestore) {
  if (!paramsRestore) {
    if (document.querySelector('[id^="mailEditorMinimizedIcon_"]')) {
      var actionYes = function() {
        var minimizedIcon = document.querySelector('[id^="mailEditorMinimizedIcon_"]');
        if (minimizedIcon) {
          minimizedIcon.parentNode.removeChild(minimizedIcon);
        }
        showMailOptions(paramsRestore);
      };
      var actionNo = function() {
        return;
      };
      showQuestion(i18n('mailIsMinimized'), actionYes, actionNo);
      return;
    }
  }
  showMailOptions(paramsRestore);
}

function showMailOptions(paramsRestore) {
  if (dijit.byId("mailToolTip")) {
    dijit.byId("mailToolTip").destroy();
    dijit.byId("dialogMailMessage").set("class", "");
  }
  var objClass = dojo.byId("objectClass").value;
  var objId = parseInt(dojo.byId("objectId").value, 10);
  var callback = function() {
    var dialog = dijit.byId('dialogMail');
    dialog.connect(dialog, "hide", function(e) {
      if (!dialogSendMailIconized) {
        var allWidgets = dijit.registry.toArray();
        var dialogMailWidgets = allWidgets.filter(function(widget) {
          return widget.id && widget.id.indexOf('dialogMail') === 0;
        });
        dialogMailWidgets.forEach(function(widget) {
          if (widget.class == "checkBoxAttachmentMail") {
            saveDataToSession(widget.id, false, false);
          }
        });
        saveDataToSession("dialogMailAttachments", "", false);
      }
      if (paramsRestore) {
        removeAttachmentSendMail(objClass, objId);
      }
    });
    var editorType = dojo.byId("mailEditorType").value;
    if (editorType == "CK" || editorType == "CKInline") {
      setTimeout(function() {
        if (restoreMailEditorData == false) { ckEditorReplaceEditor("dialogMailMessage", 998); }
        else { setTimeout('ckEditorReplaceEditor("dialogMailMessage", 998);', 200); }
      }, 200);
    }
    if (paramsRestore) {
      param = paramsRestore;
      var objectId = (paramsRestore.match(/objectId=([^&]*)/) || [])[1];
      var objectClass = (paramsRestore.match(/objectClass=([^&]*)/) || [])[1];
    }
    title = i18n('buttonMail', new Array(i18n(dojo.byId('objectClass').value)));
    if (dijit.byId('attendees')) {
      dijit.byId('dialogMailToOther').set('checked', 'checked');
      dijit.byId('dialogOtherMail').set('value', extractEmails(dijit.byId('attendees').get('value')));
      dialogMailToOtherChange();
    }
    dijit.byId("dialogMail").set('title', title);

    setTimeout(function() {
      updateReceivers();
    }, 300);

    if (dojo.byId('objectClassRow') && dojo.byId('objectClassRow').value && dojo.byId('objectIdRow') && dojo.byId('objectIdRow').value) {
      if (!paramsRestore) {
        param = '&objectClass=' + dojo.byId('objectClassRow').value + '&objectId=' + dojo.byId('objectIdRow').value;
        var objectId = dojo.byId('objectIdRow').value;
        var objectClass = dojo.byId('objectClassRow').value;
      }
      if (dojo.byId('selectEmailTemplate')) refreshListSpecific('emailTemplate', 'selectEmailTemplate', 'objectIdClass', objectId + '_' + objectClass);
      restoreMailEditorData = false;
      loadDialog("dialogMail", null, true, param);
    } else {
      if (!paramsRestore) {
        param = '&objectClass=' + dojo.byId('objectClass').value + '&objectId=' + dojo.byId('objectId').value;
        var objectId = dojo.byId('objectId').value;
        var objectClass = dojo.byId('objectClass').value;
      }
      if (dojo.byId('selectEmailTemplate')) refreshListSpecific('emailTemplate', 'selectEmailTemplate', 'objectIdClass', objectId + '_' + objectClass);
      restoreMailEditorData = false;
      loadDialog("dialogMail", null, true, param);
    }
  }
  var minimizedIcon = dojo.query('[id^=mailEditorMinimizedIcon_]').shift();
  if (minimizedIcon) {
    minimizedIcon.parentNode.removeChild(minimizedIcon);
  }
  if (paramsRestore) param = paramsRestore;
  var callbackckEditor = function() {
    var dialog = dijit.byId('dialogMail');
    dialog.connect(dialog, "hide", function(e) {
      if (!dialogSendMailIconized) {
        var allWidgets = dijit.registry.toArray();
        var dialogMailWidgets = allWidgets.filter(function(widget) {
          return widget.id && widget.id.indexOf('dialogMail') === 0;
        });
        dialogMailWidgets.forEach(function(widget) {
          if (widget.class == "checkBoxAttachmentMail") {
            saveDataToSession(widget.id, false, false);
          }
        });
      }
      removeAttachmentSendMail(objClass, objId);
    });
    var editorType = dojo.byId("mailEditorType").value;
    if (editorType == "CK" || editorType == "CKInline") {
      setTimeout(function() {
        if (restoreMailEditorData == false) { ckEditorReplaceEditor("dialogMailMessage", 998); }
        else { setTimeout('ckEditorReplaceEditor("dialogMailMessage", 998);', 200); }
      }, 100);
    }
    setTimeout(function() {
      updateReceivers();
    }, 300);
  }
  //if (dijit.byId("dialogMail") && dojo.byId('dialogMailObjectClass') && dojo.byId('dialogMailObjectClass').value == dojo.byId('objectClass').value) { // PBER : fix
  if (dijit.byId("dialogMail") && dojo.byId('dialogMailObjectClass')) {
    if (dojo.byId('selectEmailTemplate')) refreshListSpecific('emailTemplate', 'selectEmailTemplate', 'objectIdClass', dojo.byId('objectId').value + '_' + dojo.byId('objectClass').value);
    if (dojo.byId('objectClassRow') && dojo.byId('objectClassRow').value && dojo.byId('objectIdRow') && dojo.byId('objectIdRow').value) {
      if (!paramsRestore) param = '&objectClass=' + dojo.byId('objectClassRow').value + '&objectId=' + dojo.byId('objectIdRow').value;
      restoreMailEditorData = false;
      loadDialog("dialogMail", callbackckEditor, true, param);
    } else {
      if (!paramsRestore) param = '&objectClass=' + dojo.byId('objectClass').value + '&objectId=' + dojo.byId('objectId').value;
      restoreMailEditorData = false;
      loadDialog("dialogMail", callbackckEditor, true, param);
    }
  } else {
    if (dojo.byId('objectClassRow') && dojo.byId('objectClassRow').value && dojo.byId('objectIdRow') && dojo.byId('objectIdRow').value) {
      var param = "&objectClass=" + dojo.byId('objectClassRow').value + "&objectId=" + dojo.byId('objectIdRow').value;
    } else {
      var param = "&objectClass=" + dojo.byId('objectClass').value + "&objectId=" + dojo.byId('objectId').value;
    }
    restoreMailEditorData = false;
    loadDialog("dialogMail", callback, false, param);
  }
}

function changeFileSizeMail(name) {
  var attachments = dojo.byId('attachments').value;
  var addAttachments = '';
  var totalSize = dojo.byId('totalSizeNoConvert').value;
  var maxSize = Number(dojo.byId('maxSizeNoconvert').value);
  var val1 = dojo.byId('v1_' + name).value;
  var val2 = dojo.byId('v2_' + name).value;
  var id = dojo.byId('addVersion' + name).value;
  var type = 'DocumentVersion';
  var docVersRef = dojo.byId('idDocRef' + name).value;
  var docVers = dojo.byId('idDoc' + name).value;
  if (dijit.byId('dialogMail' + name).get('checked') == true) {

    if (totalSize != 0) {
      size = Number(totalSize) - Number(dojo.byId('filesizeNoConvert' + name).value);
    }
    var regex = '/' + id + '_' + type;
    if (attachments.indexOf(regex) == -1) {
      regex = id + '_' + type;
    }
    suprAttachments = attachments.replace(regex, '');
    if (dijit.byId('versionRef' + name).get('checked') == true) {
      if (suprAttachments != '') {
        addAttachments = suprAttachments + '/' + docVersRef + '_' + type;
      } else {
        addAttachments = docVersRef + '_' + type;
      }
      totalSize = size + Number(val1);
      dojo.byId('filesize' + name).value = octetConvertSize(val1);
      dojo.byId('filesizeNoConvert' + name).value = val1;
      dojo.byId('addVersion' + name).value = docVersRef;
      dojo.byId('attachments').value = addAttachments;
    } else {
      if (suprAttachments != '') {
        addAttachments = suprAttachments + '/' + docVers + '_' + type;
      } else {
        addAttachments = docVers + '_' + type;
      }
      dojo.byId('filesize' + name).value = octetConvertSize(val2);
      dojo.byId('filesizeNoConvert' + name).value = val2;
      dojo.byId('addVersion' + name).value = docVers;
      dojo.byId('attachments').value = addAttachments;
    }
    var noConvert = totalSize;
    if (totalSize != 0) {
      totalSize = octetConvertSize(totalSize);
    }
    if (maxSize < noConvert) {
      dojo.byId('infoSize').style.color = "red";
      dojo.byId('totalSize').style.color = "red";
    } else if ((maxSize >= noConvert) || noConvert == 0) {
      dojo.byId('infoSize').style.color = "green";
      dojo.byId('totalSize').style.color = "green";
    }
    dojo.byId('totalSizeNoConvert').value = noConvert;
    dojo.byId('totalSize').value = totalSize;
  } else {
    if (dijit.byId('versionRef' + name).get('checked') == true) {
      dojo.byId('filesize' + name).value = octetConvertSize(val1);
      dojo.byId('filesizeNoConvert' + name).value = val1;
      dojo.byId('addVersion' + name).value = docVersRef;
    } else {
      dojo.byId('filesize' + name).value = octetConvertSize(val2);
      dojo.byId('filesizeNoConvert' + name).value = val2;
      dojo.byId('addVersion' + name).value = docVers;
    }
  }
}

var dialogSendMailIconized = false;
var savedMailContent = {};
var savedReceiversState = {};
function minimizeMailEditor(translatedMailText, objId, objClass) {
  var dialog = document.getElementById('dialogMail');
  var mailTextarea = document.getElementById('dialogMailMessage');
  if (dialog) {
    objId = objId || (dojo.byId('dialogMailObjectId') ? dojo.byId('dialogMailObjectId').value : null) || (dojo.byId('objectId') ? dojo.byId('objectId').value : null);
    objClass = objClass || (dojo.byId('dialogMailObjectClass') ? dojo.byId('dialogMailObjectClass').value : null) || (dojo.byId('objectClass') ? dojo.byId('objectClass').value : null);
    if (!objId || !objClass) return;
    var ckEditorInstance = CKEDITOR.instances.dialogMailMessage;
    if (ckEditorInstance) {
      ckEditorInstance.updateElement();
      savedMailContent[objId] = ckEditorInstance.getData();
    } else if (mailTextarea) {
      var dojoEditor = dijit.byId("mailMailEditor");
      if (dojoEditor) {
        savedMailContent[objId] = dojoEditor.get("value");
      } else if (mailTextarea) {
        savedMailContent[objId] = mailTextarea.value || mailTextarea.innerHTML || "";
      }
    }
    var receiverContainer = document.getElementById('receiverTableContainer');
    if (receiverContainer) {
      savedReceiversState[objId] = {
        html: receiverContainer.innerHTML,
        checkboxStates: {}
      };
      dojo.query("[id^='dialogMailCheckReceiver_']", receiverContainer).forEach(function(node) {
        var widget = dijit.byId(node.id);
        if (widget) {
          savedReceiversState[objId].checkboxStates[node.id] = widget.get('checked');
        }
      });
    }
    dialogSendMailIconized = true;
    if (dijit.byId('dialogMail') && dojo.hasClass(dijit.byId('dialogMail').domNode, 'fullScreenDialog')) {
      removeFullScreenDialog('dialogMail', true);
    } else if (typeof scheduleDialogMailNormalLayoutResize == 'function') {
      scheduleDialogMailNormalLayoutResize();
    }
    dijit.byId('dialogMail').hide();
    var minimizedIcon = document.getElementById('mailEditorMinimizedIcon_' + objId);
    if (!minimizedIcon) {
      minimizedIcon = document.createElement('div');
      minimizedIcon.id = 'mailEditorMinimizedIcon_' + objId;
      var button = document.createElement('button');
      button.style.cursor = 'pointer';
      button.style.border = '1px solid #d3d3d3';
      button.style.borderRadius = '5px';
      button.style.background = 'none';
      button.style.padding = '5px 10px';
      button.innerHTML = '✉ ' + translatedMailText;
      button.onclick = function() { restoreMailEditor(objId, objClass); };
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
    dialogSendMailIconized = false;
  }
}

var restoreMailEditorData = false;
function restoreMailEditor(objId, objClass) {
  var minimizedIcon = document.getElementById('mailEditorMinimizedIcon_' + objId);
  if (minimizedIcon) {
    minimizedIcon.style.display = 'none';
  }

  var params = "&objectClass=" + objClass;
  params += "&objectId=" + objId;
  showMail(params);

  setTimeout(function() {
    document.getElementById('mailInfoDiv').style.display = 'block';
    if (typeof scheduleDialogMailNormalLayoutResize == 'function') {
      scheduleDialogMailNormalLayoutResize();
    }
    function restoreContent() {
      var mailTextarea = document.getElementById('dialogMailMessage');
      var ckEditorInstance = CKEDITOR.instances.dialogMailMessage;
      var savedContent = savedMailContent[objId] || "";
      if (savedContent && ckEditorInstance && ckEditorInstance.status === 'ready') {
        restoreMailEditorData = true;
        //ckEditorInstance.fire('lockSnapshot');
        ckEditorInstance.setData(savedContent, {
          callback: function() {
            //ckEditorInstance.fire('unlockSnapshot');
            ckEditorInstance.updateElement();

          }
        });
        setTimeout("restoreMailEditorData = false;", 250);
      } else if (mailTextarea) {
        var dojoEditor = dijit.byId("mailMailEditor");
        if (dojoEditor) {
          dojoEditor.set("value", savedContent);
        } else {
          mailTextarea.value = savedContent;
        }
      } else {
        setTimeout(restoreContent, 200);
        return;
      }
    }
    if (CKEDITOR.instances.dialogMailMessage) {
      if (CKEDITOR.instances.dialogMailMessage.status === 'ready') {
        restoreContent();
      } else {
        var instanceReadyHandler = function() {
          CKEDITOR.instances.dialogMailMessage.removeListener('instanceReady', instanceReadyHandler);
          restoreContent();
        };
        CKEDITOR.instances.dialogMailMessage.on('instanceReady', instanceReadyHandler);
      }
    } else {
      var checkInstance = function() {
        if (CKEDITOR.instances.dialogMailMessage) {
          if (CKEDITOR.instances.dialogMailMessage.status === 'ready') {
            restoreContent();
          } else {
            var instanceReadyHandler = function() {
              CKEDITOR.instances.dialogMailMessage.removeListener('instanceReady', instanceReadyHandler);
              restoreContent();
            };
            CKEDITOR.instances.dialogMailMessage.on('instanceReady', instanceReadyHandler);
          }
        } else {
          setTimeout(checkInstance, 100);
        }
      };
      checkInstance();
    }
    if (savedReceiversState[objId]) {
      updateReceivers();
      setTimeout(function() {
        for (var checkboxId in savedReceiversState[objId].checkboxStates) {
          var widget = dijit.byId(checkboxId);
          if (widget) {
            widget.set('checked', savedReceiversState[objId].checkboxStates[checkboxId]);
          }
        }
      }, 300);
    }
    refreshAttachmentSendMail('false', objClass, objId, false, function() {
      if (typeof scheduleDialogMailNormalLayoutResize == 'function') {
        scheduleDialogMailNormalLayoutResize();
      }
    });
    getAddedAttachment();
  }, 800);
}


function updateDialogMailMessageField() {
  var editorType = dojo.byId("mailEditorType")?.value || '';
  if (editorType == "CK" || editorType == "CKInline") {
    var ckEditorInstance = CKEDITOR.instances['dialogMailMessage'];
    if (ckEditorInstance) {
      dojo.byId('dialogMailMessage').value = ckEditorInstance.getData();
    }
  } else {
    var dojoEditor = dijit.byId("mailMailEditor");
    if (dojoEditor) {
      dojo.byId('dialogMailMessage').value = dojoEditor.get('value');
    }
  }
}
updateReceiversInProgress = false;
function updateReceivers() {
  if (updateReceiversInProgress) return;
  updateReceiversInProgress = true;
  var checkContact = (dojo.byId('dialogMailToContact') && dojo.byId('dialogMailToContact').checked) ? true : false;
  var checkUser = (dojo.byId('dialogMailToUser') && dojo.byId('dialogMailToUser').checked) ? true : false;
  var checkAccountable = (dojo.byId('dialogMailToAccountable') && dojo.byId('dialogMailToAccountable').checked) ? true : false;
  var checkResource = (dojo.byId('dialogMailToResource') && dojo.byId('dialogMailToResource').checked) ? true : false;
  var checkFinancialResponsible = (dojo.byId('dialogMailToFinancialResponsible') && dojo.byId('dialogMailToFinancialResponsible').checked) ? true : false;
  var checkSponsor = (dojo.byId('dialogMailToSponsor') && dojo.byId('dialogMailToSponsor').checked) ? true : false;
  var checkProject = (dojo.byId('dialogMailToProject') && dojo.byId('dialogMailToProject').checked) ? true : false;
  var checkIncludingParentProject = (dojo.byId('dialogMailToProjectIncludingParentProject') && dojo.byId('dialogMailToProjectIncludingParentProject').checked) ? true : false;
  var checkLeader = (dojo.byId('dialogMailToLeader') && dojo.byId('dialogMailToLeader').checked) ? true : false;
  var checkManager = (dojo.byId('dialogMailToManager') && dojo.byId('dialogMailToManager').checked) ? true : false;
  var checkAssigned = (dojo.byId('dialogMailToAssigned') && dojo.byId('dialogMailToAssigned').checked) ? true : false;
  var checkSubscribers = (dojo.byId('dialogMailToSubscribers') && dojo.byId('dialogMailToSubscribers').checked) ? true : false;

  var previousCheckboxStates = {};

  var tbodyNode = dojo.byId("receiversTableBody");
  if (tbodyNode) {
    dojo.query("[id^='dialogMailCheckReceiver_']", tbodyNode).forEach(function(node) {
      var widget = dijit.byId(node.id);
      if (widget) {
        previousCheckboxStates[node.id] = widget.get('checked');
      }
    });
  }
  if (tbodyNode) {
    dijit.registry.findWidgets(tbodyNode).forEach(function(widget) {
      widget.destroyRecursive();
    });
    tbodyNode.innerHTML = "";
    dojo.query("[id^='dialogMailCheckReceiver_']", tbodyNode).forEach(function(node) {
      if (dijit.registry.byId(node.id)) {
        dijit.registry.remove(node.id);
      }
    });
  }
  if (tbodyNode) {
    tbodyNode.style.visibility = 'hidden';
    tbodyNode.style.opacity = '0';
  }

  
  dojo.xhrGet({
    url: "../tool/getReceivers.php?objectClass=" + dojo.byId('mailRefType').value + "&objectId=" + dojo.byId('mailRefId').value
      + '&dialogMailToContact=' + checkContact
      + '&dialogMailToUser=' + checkUser
      + '&dialogMailToAccountable=' + checkAccountable
      + '&dialogMailToResource=' + checkResource
      + '&dialogMailToFinancialResponsible=' + checkFinancialResponsible
      + '&dialogMailToSponsor=' + checkSponsor
      + '&dialogMailToProject=' + checkProject
      + '&dialogMailToProjectIncludingParentProject=' + checkIncludingParentProject
      + '&dialogMailToLeader=' + checkLeader
      + '&dialogMailToManager=' + checkManager
      + '&dialogMailToAssigned=' + checkAssigned
      + '&dialogMailToSubscribers=' + checkSubscribers
      + addTokenIndexToUrl(),
    handleAs: "text",
    load: function(data, args) {
      try {
        var tbody = dojo.byId("receiversTableBody");
        if (tbody) {
          tbody.innerHTML = "";
          tbody.innerHTML = data;
          dojo.parser.parse(tbody).then(function() {
            tbody.style.visibility = 'visible';
            tbody.style.opacity = '1';
            tbody.style.transition = 'opacity 0.2s ease-in';
            dojo.query("[id^='dialogMailCheckReceiver_']", tbody).forEach(function(node) {
              var widget = dijit.byId(node.id);
              if (widget && previousCheckboxStates.hasOwnProperty(node.id)) widget.set('checked', previousCheckboxStates[node.id]);
            });
            updateReceiversInProgress = false;
          }).catch(function(parseError) {
            console.error("Error parsing widgets:", parseError);
            updateReceiversInProgress = false;
          });
        } else {
          updateReceiversInProgress = false;
        }
      } catch (error) {
        console.error("Error in load callback:", error);
        updateReceiversInProgress = false;
      }
    },
    error: function(err) {
      console.error("Error retrieving receivers: ", err);
      updateReceiversInProgress = false;
    }
  });
}

function getAddedAttachment(getSize, getName, remove) {
  if (getSize == undefined) getSize = false;
  if (getName == undefined) getName = false;
  if (remove == undefined) remove = false;
  var allWidgets = dijit.registry.toArray();
  var dialogMailWidgets = allWidgets.filter(function(widget) {
    return widget.id && widget.id.indexOf('dialogMail') === 0;
  });
  dialogMailWidgets.forEach(function(widget) {
    var name = (dojo.byId('name_' + widget.id)) ? dojo.byId('name_' + widget.id).value : null;
    var size = (dojo.byId('size_' + widget.id)) ? dojo.byId('size_' + widget.id).value : null;
    if (getSize && getName && name && size) {
      var id = parseInt(dojo.byId('objectId').value);
      showAttachedSize(size, name, id, 'file', "DialogMail");
    } else if (size && getSize && !getName) {
      var totalSize = dojo.byId('totalSizeNoConvert').value;
      var maxSize = Number(dojo.byId('maxSizeNoconvert').value);
      if (!remove) {
        totalSize = Number(totalSize) + Number(size);
      }
      var noConvert = totalSize;
      if (totalSize != 0) {
        totalSize = octetConvertSize(totalSize);
      }
      if (maxSize < noConvert) {
        dojo.byId('infoSize').style.color = "red";
        dojo.byId('totalSize').style.color = "red";
      } else if ((maxSize >= noConvert) || noConvert == 0) {
        dojo.byId('infoSize').style.color = "green";
        dojo.byId('totalSize').style.color = "green";
      }
      dojo.byId('totalSizeNoConvert').value = noConvert;
      dojo.byId('totalSize').value = totalSize;
      return size;
    } else if (name && getName && !getSize) {
      return name;
    } else if (getName && getSize) {
    }

  });
}

function selectAllCheckBox(val) {
  dojo.query(val).forEach(function(node, index, nodelist) {
    if (dijit.byId('dialogMailAll').get('checked') != true) {
      dijit.byId(node.getAttribute('widgetid')).set('checked', false);
    } else {
      dijit.byId(node.getAttribute('widgetid')).set('checked', true);
    }
  });
}

function refreshAttachmentSendMail(isIE, objectClass, objectId, remove, afterRefresh) {
  if (isIE == undefined) isIE = false;
  if (remove == undefined) remove = false;
  var callback = function() {
    getAddedAttachment(true, null, remove);
    if (afterRefresh) afterRefresh();
    var mailDialog=dijit.byId('dialogMail');
    if (mailDialog && dojo.hasClass(mailDialog.domNode, 'fullScreenDialog')) {
      if (typeof applyDialogMailFullScreenLayoutSize == 'function') applyDialogMailFullScreenLayoutSize();
      if (typeof scheduleDialogMailFullScreenMessageResize == 'function') scheduleDialogMailFullScreenMessageResize();
    } else if (mailDialog && typeof scheduleDialogMailNormalLayoutResize == 'function') {
      scheduleDialogMailNormalLayoutResize();
    }
  };
  loadContent("../tool/refreshAttachmentSendMail.php?isIE=" + isIE + '&objectClass=' + objectClass + '&objectId=' + objectId, "showAddAttachment", null, null, null, null, null, callback);
}
