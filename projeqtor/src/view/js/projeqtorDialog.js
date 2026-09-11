/*******************************************************************************
 * COPYRIGHT NOTICE *
 * 
 * Copyright 2009-2021 ProjeQtOr - Pascal BERNARD - support@projeqtor.org
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
// All specific ProjeQtOr functions and variables for Dialog Purpose
// This file is included in the main.php page, to be reachable in every context
// ============================================================================

// =============================================================================
// = Variables (global)
// =============================================================================
var filterType="";
var closeFilterListTimeout;
var openFilterListTimeout;
var closeFavoriteReportsTimeout;
var openFavoriteReportsTimeout=null;
var closeFavoriteTimeout;
var openFavoriteTimeout=null;
var popupOpenDelay=200;
var closeMenuListTimeout=null;
var openMenuListTimeout=null;
var menuListAutoshow=false;
var hideUnderMenuTimeout;
var hideUnderMenuId;
var previewhideUnderMenuId;
var stockEmailHistory = new Array();
var lastKeys= new Array();
var cplastKey;
var tabLastKeys= new Array();
var addVal= [0,0,0,0];
var paramLength;
var cpMaj=0;
var cpNum=0;
var cpChar=0;
var cpParamLength=0;
var coverListAction='';

// =============================================================================
// = Dialog Management
// =============================================================================

// CHANGE BY Marc TABARY - 2017-03-13 - CHANGE TITLE DYNAMIC DIALOG
function loadDialog(dialogDiv, callBack, autoShow, params, clearOnHide, closable, dialogTitle, dialogTitleKeepAsIs, formName) {
  // Before loading, be sure to clear dialogs containing
  // "directAccessToListButton"
  // This is mandatory as these dialogs may not be cleared on direct access, as
  // they are not showed so .hide() and no effect and clearOnHide is not
  // triggered
  if (dojo.byId('directAccessToListButton')) {
   var parentName=dojo.byId('directAccessToListButton').parentNode.id;
   var dialogName="dialog"+parentName.substr(0,1).toUpperCase()+parentName.substr(1,parentName.length-5);
   if (dijit.byId(dialogName)){
     dijit.byId(dialogName).set("content",null);
   }
  }
  // Old
  // function loadDialog(dialogDiv, callBack, autoShow, params, clearOnHide,
  // closable) {
  // END CHANGE BY Marc TABARY - 2017-03-13 - PERIODIC YEAR BUDGET ELEMENT
  if(typeof closable =='undefined')closable=true;
  	var hideCallback=function() {
   	if (dialogDiv=='dialogNote') resumeBodyFocus();
   	if (dialogDiv == 'dialogNote' || dialogDiv == 'dialogMail') repositionMinimizedIcons();
   	removeFullScreenDialog(dialogDiv, false);
  };
  
  if (clearOnHide) {
   	hideCallback=function() {
    dijit.byId(dialogDiv).set('content', null);
    if (dialogDiv=='dialogNote') resumeBodyFocus();
	if (dialogDiv == 'dialogNote' || dialogDiv == 'dialogMail') repositionMinimizedIcons();
    removeFullScreenDialog(dialogDiv, false);
   };
  }
  
  // ADD BY Marc TABARY - 2017-03-13 - CHANGE TITLE DYNAMIC DIALOG
  var setTitle=false;
  if(typeof dialogTitle == 'undefined') {
     theDialogTitle = dialogDiv;
  } else if (dialogTitle=='') {
     theDialogTitle = dialogDiv;    
  } else {
     theDialogTitle = dialogTitle;
     setTitle=true;
  }
  if (! dialogTitleKeepAsIs) theDialogTitle=i18n(theDialogTitle);
  // END ADD BY Marc TABARY - 2017-03-13 - CHANGE TITLE DYNAMIC DIALOG
  
  extraClass="projeqtorDialogClass";
  if (dialogDiv=="dialogLogfile") {
   extraClass="logFile";
  }
  if (!dijit.byId(dialogDiv)) {
   dialog=new dijit.Dialog({
     id : dialogDiv,
  // CHANGE BY Marc TABARY - 2017-03-13 - CHANGE TITLE DYNAMIC DIALOG
     title : theDialogTitle,
     // Old
  // title : i18n(dialogDiv),
  // END CHANGE BY Marc TABARY - 2017-03-13 - CHANGE TITLE DYNAMIC DIALOG
     width : '500px',
     onHide : hideCallback,
     content : i18n("loading"),
     'class' : extraClass,
     closable : closable
   });
  } else {
   dialog=dijit.byId(dialogDiv);
  // ADD BY Marc TABARY - 2017-03-13 - CHANGE TITLE DYNAMIC DIALOG
   if (setTitle) {
       dialog.set('title',theDialogTitle);
  }
  
  // END ADD BY Marc TABARY - 2017-03-13 - CHANGE TITLE DYNAMIC DIALOG
  }
  if (dialogDiv === 'dialogMail') {
    var mailParams = params || "";
    dialog.dialogMailObjectId = (mailParams.match(/objectId=([^&]*)/) || [])[1];
    dialog.dialogMailObjectClass = (mailParams.match(/objectClass=([^&]*)/) || [])[1];
    if (!dialog.dialogMailIconsConnected) {
      dialog.dialogMailIconsConnected = true;
      dialog.on("show", function () {
        const titleBar = dojo.query("#" + dialogDiv + " .dijitDialogTitleBar")[0];
        if (!titleBar) return;

        if (!dojo.byId("dialogMailFullScreenIcon")) {
          const fullIcon = document.createElement("div");
          fullIcon.id = "dialogMailFullScreenIcon";
          fullIcon.title = i18n("fullScreen");
          fullIcon.className = "fullScreenIcon";
          fullIcon.tabIndex = -1;
          fullIcon.style.cssText = "cursor:pointer; margin-right:8px; float:right;";
          fullIcon.onclick = function () {
            toggleFullScreenDialog('dialogMail');
          };
          titleBar.appendChild(fullIcon);
        }

        if (!dojo.byId("dialogMailMinimizeIcon")) {
          const icon = document.createElement("div");
          icon.id = "dialogMailMinimizeIcon";
          icon.title = i18n('minimize');
          icon.className = "minimizeMailIcon";
          icon.tabIndex = -1;
          icon.style.cssText = "cursor:pointer; margin-right:8px; float:right;";
          titleBar.appendChild(icon);
        }
        dojo.byId("dialogMailMinimizeIcon").onclick = function () {
          minimizeMailEditor('dialogMail', dialog.dialogMailObjectId, dialog.dialogMailObjectClass);
        };
        setTimeout(function() {
          if (dijit.byId('dialogMail') && !dojo.hasClass(dijit.byId('dialogMail').domNode, 'fullScreenDialog') && typeof scheduleDialogMailNormalLayoutResize == 'function') {
            scheduleDialogMailNormalLayoutResize();
          }
        }, 100);
      });
    }
  }
  
  
    
  if (!params) {
   params="";
  }

  showWait();
  var url='../tool/dynamicDialog.php?dialog='+dialogDiv+'&isIE='+((dojo.isIE)?dojo.isIE:'')+params+addTokenIndexToUrl();
  dojo.xhrPost({
   url : url,
   form : formName,
   handleAs : "text",
   load : function(data) {
     var contentWidget=dijit.byId(dialogDiv);
     contentWidget.set('content', data);
	 if (autoShow) {
	   setTimeout(function () {
	     dijit.byId(dialogDiv).show().then(function () {
	       if (dialogDiv === 'dialogCopy') {
	         var nameWidget = dijit.byId('copyToVersionNumber') || dijit.byId('copyToName')  || dijit.byId('copyProjectToName');
	         if (nameWidget && nameWidget.textbox) {
	           nameWidget.textbox.focus();
	           nameWidget.textbox.select();
	         }
	       }
	     });
	   }, 100);
	 
       if (dialogDiv=='dialogNote') {
		var objectId = (params.match(/objectId=([^&]*)/) || [])[1];
		var objectClass = (params.match(/objectClass=([^&]*)/) || [])[1];
		var idParentNote = (params.match(/idParentNote=([^&]*)/) || [])[1];
		var reply = idParentNote ? true : false ; 
		dijit.byId('dialogNote').onShow = function(){
		  var editor=CKEDITOR.instances["noteNote"].focus();
		  const titleBar = dojo.query("#" + dialogDiv + " .dijitDialogTitleBar")[0];

		  // FULLSCREEN ICON
		  var fullIcon = dojo.byId("dialogNoteFullScreenIcon");
		  if (!fullIcon) {
		    fullIcon = document.createElement("div");
		    fullIcon.id = "dialogNoteFullScreenIcon";
		    fullIcon.title = i18n("fullScreen");
		    fullIcon.className = "fullScreenIcon";
		    fullIcon.tabIndex = -1;
		    fullIcon.style.cssText = "cursor:pointer; margin-right:8px; float:right;";
		    titleBar.appendChild(fullIcon);
		  }
		  fullIcon.onclick = function () {
		    toggleFullScreenDialog('dialogNote');
		  };

		  // MINIMIZE ICON
		  var minimizeIcon = dojo.byId("dialogNoteMinimizeIcon");
		  if (!minimizeIcon) {
		    minimizeIcon = document.createElement("div");
		    minimizeIcon.id = "dialogNoteMinimizeIcon";
		    minimizeIcon.title = i18n("minimize");
		    minimizeIcon.className = "minimizeIcon";
		    minimizeIcon.tabIndex = -1;
		    minimizeIcon.style.cssText = "cursor:pointer; margin-right:8px; float:right;";
		    titleBar.appendChild(minimizeIcon);
		  }

		  minimizeIcon.onclick = function () {
		    minimizeNoteEditor('dialogNote', objectId, objectClass, reply, idParentNote);
		  };
		};
       }
     }
     hideWait();
     if (callBack) {
       setTimeout(callBack, 10);
     }
   },
   error : function() {
     consoleTraceLog("error loading dialog " + dialogDiv);
     hideWait();
   }
  });
}

// =============================================================================
// = Wait spinner
// =============================================================================

var waitingForReply=false;

function showWait(waitMessage) {
  if(waitMessage == undefined)waitMessage=false;
  if (dojo.byId("wait")) {
    showField("wait", waitMessage);
    waitingForReply=true;
  } else {
    showField("waitLogin");
  }
}

function hideWait() {
  waitingForReply=false;
  hideField("wait");
  hideField("waitLogin");
  if (window.top.dijit.byId("dialogInfo")) {
    window.top.dijit.byId("dialogInfo").hide();
  }
  if(dojo.byId('waitMessage')){
  	dojo.byId('waitMessage').innerHTML = '';
	dojo.removeClass('wait', 'waitDivMessageDisplay');
  }
}

// =============================================================================
// = Generic field visibility properties
// =============================================================================

function showField(field, waitMessage) {
  if(waitMessage == undefined)waitMessage=false;
  var dest=dojo.byId(field);
  if (dijit.byId(field)) {
    dest=dijit.byId(field).domNode;
  }
  if (dest) {
	if(waitMessage){
		dojo.addClass(dest, 'waitDivMessageDisplay');
	    dojo.style(dest, {
	      display : 'flex'
	    });
		if(waitingForReply && dojo.byId('waitMessage')){
			dojo.byId('waitMessage').innerHTML = waitMessage;
	    }
	}else{
		dojo.style(dest, {
	      display : 'inline'
	    });
	}
	dojo.style(dest, {
      visibility : 'visible'
    });
  }
}

/**
 * ============================================================================
 * Setup the style properties of a field to set it invisible (hide it)
 * 
 * @param field
 *          the name of the field to be set
 * @return void
 */
function hideField(field) {
  var dest=dojo.byId(field);
  if (dijit.byId(field)) {
    dest=dijit.byId(field).domNode;
  }
  if (dest) {
    dojo.style(dest, {
      visibility : 'hidden'
    });
    dojo.style(dest, {
      display : 'none'
    });
  }
}

function protectDblClick(widget){
  if (!widget.id) return;
  disableWidget(widget.id);
  setTimeout("enableWidget('"+widget.id+"');",300);
}

// =============================================================================
// = Message boxes
// =============================================================================

/**
 * ============================================================================
 * Display a Dialog Error Message Box
 * 
 * @param msg
 *          the message to display in the box
 * @return void
 */
function showError(msg) {
  window.top.hideWait();
  dojo.byId('dialogErrorIcon').style.display=(msg.includes('<div class='))?'none':'table-cell';
  if (window.top.dojo.byId("dialogErrorMessage")) {
    window.top.dojo.byId("dialogErrorMessage").innerHTML=msg;
    window.top.dijit.byId("dialogError").show();
  } else if (dojo.byId('loginResultDiv')) {
    dojo.byId('loginResultDiv').innerHTML=
      '<input type="hidden" id="isLoginPage" name="isLoginPage" value="true" />'
      +'<div class="messageERROR" style="width:100%">'+msg+'</div>';
  } else {
    alert(msg);
  }
}

/**
 * ============================================================================
 * Display a Dialog Information Message Box
 * 
 * @param msg
 *          the message to display in the box
 * @return void
 */
function showInfo(msg,callback) {
  dojo.byId('dialogInfoIcon').style.display=(msg.includes('<div class='))?'none':'table-cell';
  var callbackFunc=function() {};
  if (callback) { 
    callbackFunc=callback;
  }
  window.top.dojo.byId("dialogInfoMessage").innerHTML=msg;
  window.top.dijit.byId("dialogInfo").acceptCallback=callbackFunc;
  window.top.dijit.byId("dialogInfo").show();
}

/**
 * ============================================================================
 * Display a Dialog Alert Message Box
 * 
 * @param msg
 *          the message to display in the box
 * @return void
 */
function showAlert(msg,callback) {
  window.top.hideWait();
  dojo.byId('dialogAlertIcon').style.display=(msg.includes('<div class='))?'none':'table-cell';
  var callbackFunc=function() {};
  if (callback) { 
    callbackFunc=callback;
  }
  window.top.dojo.byId("dialogAlertMessage").innerHTML=msg;
  window.top.dijit.byId("dialogAlert").acceptCallback=callbackFunc;
  window.top.dijit.byId("dialogAlert").show();
}

/**
 * ============================================================================
 * Display a Dialog Question Message Box, with Yes/No buttons
 * 
 * @param msg
 *          the message to display in the box
 * @param actionYes
 *          the function to be executed if click on Yes button
 * @param actionNo
 *          the function to be executed if click on No button
 * @return void
 */
function showQuestion(msg, actionYes, actionNo) {
  dojo.byId('dialogQuestionIcon').style.display=(msg.includes('<div class='))?'none':'table-cell';
  dojo.byId("dialogQuestionMessage").innerHTML=msg;
  dijit.byId("dialogQuestion").acceptCallbackYes=actionYes;
  dijit.byId("dialogQuestion").acceptCallbackNo=actionNo;
  dijit.byId("dialogQuestion").show();
}

/**
 * remi 7823
 * ============================================================================
 * Display a Dialog Question for quit with no save, Message Box, with Save/Skip/No buttons
 * 
 * @param msg
 *          the message to display in the box
 * @param actionSave
 *          the function to be executed if click on Save button     
 * @param actionYes
 *          the function to be executed if click on Yes button
 * @param actionNo
 *          the function to be executed if click on No button
 * @return void
 */
function showQuestionNoSave(msg,actionYes,actionNo,actionSave) {
  dojo.byId('dialogQuestionNoSaveIcon').style.display=(msg.includes('<div class='))?'none':'table-cell';
  dojo.byId("dialogQuestionNoSaveMessage").innerHTML=msg;
  dijit.byId("dialogQuestionNoSave").acceptCallbackSave=actionSave;
  dijit.byId("dialogQuestionNoSave").acceptCallbackYes=actionYes;
  dijit.byId("dialogQuestionNoSave").acceptCallbackNo=actionNo;
  dijit.byId("dialogQuestionNoSave").show();
}


/**
 * ============================================================================
 * Display a Dialog Confirmation Message Box, with OK/Cancel buttons NB : no
 * action on Cancel click
 * 
 * @param msg
 *          the message to display in the box
 * @param actionOK
 *          the function to be executed if click on OK button
 * @return void
 */
function showConfirm(msg, actionOK) {
  dojo.byId('dialogConfirmIcon').style.display=(msg.includes('<div class='))?'none':'table-cell';
  window.top.dojo.byId("dialogConfirmMessage").innerHTML=msg;
  window.top.dijit.byId("dialogConfirm").acceptCallback=actionOK;
  window.top.dijit.byId("dialogConfirm").show();
}

/**
 * ============================================================================
 * Display a About Box
 * 
 * @param msg
 *          the message of the about box (must be passed here because built in
 *          php)
 * @return void
 */
function showAbout(msg) {
  showInfo(msg);
}

function showMsg(id,value){
  if(dojo.byId("divMsgFull"+id).style.display=="none"){
    dojo.byId("divSubTitle"+id).style.display="none";
    if(value==0.25 || value==1.25 || value==2.25){
      if(dojo.byId("divMsgTitle"+(id+1))){
        dojo.byId("divMsgTitle"+(id+1)).style.display="none";
      }
      if(dojo.byId("divMsgTitle"+(id+2))){
        dojo.byId("divMsgTitle"+(id+2)).style.display="none";
      }
      if(dojo.byId("divMsgTitle"+(id+3))){
        dojo.byId("divMsgTitle"+(id+3)).style.display="none";
      }
    }
    if(value==0.5 || value==1.5 || value==2.5){
      if(dojo.byId("divMsgTitle"+(id+1))){
        dojo.byId("divMsgTitle"+(id+1)).style.display="none";
      }
      if(dojo.byId("divMsgTitle"+(id+2))){
        dojo.byId("divMsgTitle"+(id+2)).style.display="none";
      }
      if(dojo.byId("divMsgTitle"+(id-1))){
        dojo.byId("divMsgTitle"+(id-1)).style.display="none";
      }
    }
    if(value==0.75 || value==1.75 || value==2.75){
      if(dojo.byId("divMsgTitle"+(id+1))){
        dojo.byId("divMsgTitle"+(id+1)).style.display="none";
      }
      if(dojo.byId("divMsgTitle"+(id-1))){
        dojo.byId("divMsgTitle"+(id-1)).style.display="none";
      }
      if(dojo.byId("divMsgTitle"+(id-2))){
        dojo.byId("divMsgTitle"+(id-2)).style.display="none";
      }
    }
    if(value==1 || value==2 || value==3){
      if(dojo.byId("divMsgTitle"+(id-1))){
        dojo.byId("divMsgTitle"+(id-1)).style.display="none";
      }
      if(dojo.byId("divMsgTitle"+(id-2))){
        dojo.byId("divMsgTitle"+(id-2)).style.display="none";
      }
      if(dojo.byId("divMsgTitle"+(id-3))){
        dojo.byId("divMsgTitle"+(id-3)).style.display="none";
      }
    }
    
    dojo.byId("divMsgTitle"+id).style.height=50+'px';
    dojo.byId("divMsgTitle"+id).style.margin = 0+'px';
    dojo.byId("divMsgTitle"+id).style.width=340+'px';
    dojo.byId("divMsgTitle"+id).style.borderRadius = 5+'px '+5+'px '+0+'px '+0+'px';
    dojo.addClass(dojo.byId("divMsgTitle"+id),"colorMediumDiv");
    dojo.byId("divMsgFull"+id).style.display="block";
    dojo.byId("divMsgFull"+id).style.height=270+'px';
    dojo.byId("divMsgFull"+id).style.width=340+'px';
    dojo.byId("divMsgTitle"+id).style.fontSize=13+'px';
    
  }else{
    dojo.byId("divMsgFull"+id).style.display="none";
    dojo.byId("divMsgTitle"+id).style.height=155+'px';
    dojo.byId("divMsgTitle"+id).style.width=165+'px';
    dojo.byId("divMsgTitle"+id).style.borderRadius = 5+'px '+5+'px '+5+'px '+5+'px';
    dojo.byId("divMsgTitle"+id).style.flexDirection="column";
    dojo.byId("divMsgTitle"+id).style.justifyContent="center";
    dojo.byId("divMsgTitle"+id).style.fontSize=13+'px';
    dojo.byId("divMsgtextTitle"+id).style.padding = 15+'px';
    dojo.byId("arrowNewsDown"+id).style.display="block";
    if(id==1 || id==3 || id==5 || id==7 || id==9 || id==11){
      dojo.byId("divMsgTitle"+id).style.marginRight = 10+'px';
    }
    dojo.byId("divMsgTitle"+id).style.marginBottom = 10+'px';
    
    dojo.removeClass(dojo.byId("divMsgTitle"+id),"colorMediumDiv");
    if(value==0.25 || value==1.25 || value==2.25){
      if(dojo.byId("divMsgTitle"+(id+1))){
        dojo.byId("divMsgTitle"+(id+1)).style.display="flex";
      }
      if(dojo.byId("divMsgTitle"+(id+2))){
        dojo.byId("divMsgTitle"+(id+2)).style.display="flex";
      }
      if(dojo.byId("divMsgTitle"+(id+3))){
        dojo.byId("divMsgTitle"+(id+3)).style.display="flex";
      }
    }
    if(value==0.5 || value==1.5 || value==2.5){
      if(dojo.byId("divMsgTitle"+(id+1))){
        dojo.byId("divMsgTitle"+(id+1)).style.display="flex";
      }
      if(dojo.byId("divMsgTitle"+(id+2))){
        dojo.byId("divMsgTitle"+(id+2)).style.display="flex";
      }
      if(dojo.byId("divMsgTitle"+(id-1))){
        dojo.byId("divMsgTitle"+(id-1)).style.display="flex";
      }
    }
    if(value==0.75 || value==1.75 || value==2.75){
      if(dojo.byId("divMsgTitle"+(id+1))){
        dojo.byId("divMsgTitle"+(id+1)).style.display="flex";
      }
      if(dojo.byId("divMsgTitle"+(id-1))){
        dojo.byId("divMsgTitle"+(id-1)).style.display="flex";
      }
      if(dojo.byId("divMsgTitle"+(id-2))){
        dojo.byId("divMsgTitle"+(id-2)).style.display="flex";
      }
    }
    if(value==1 || value==2 || value==3){
      if(dojo.byId("divMsgTitle"+(id-1))){
        dojo.byId("divMsgTitle"+(id-1)).style.display="flex";
      }
      if(dojo.byId("divMsgTitle"+(id-2))){
        dojo.byId("divMsgTitle"+(id-2)).style.display="flex";
      }
      if(dojo.byId("divMsgTitle"+(id-3))){
        dojo.byId("divMsgTitle"+(id-3)).style.display="flex";
      }
    }
  }
}
function showIntrotext(id){
  if(dojo.byId("divMsgFull"+id).style.display=="none"){
    dojo.byId("divMsgTitle"+id).style.height=39+'px';
    dojo.byId("divMsgTitle"+id).style.width=165+'px';
    dojo.byId("divMsgTitle"+id).style.margin = 0+'px';
    dojo.byId("divMsgTitle"+id).style.borderRadius = 5+'px '+5+'px '+0+'px '+0+'px';
    dojo.addClass(dojo.byId("divMsgTitle"+id),"colorMediumDiv");
    dojo.byId("divSubTitle"+id).style.display="block";
    dojo.byId("divSubTitle"+id).style.height=116+'px';
    dojo.byId("divSubTitle"+id).style.fontSize=10+'px';
    dojo.byId("divMsgTitle"+id).style.fontSize=10+'px';
    dojo.byId("divMsgTitle"+id).style.textOverflow='ellipsis';
    dojo.byId("arrowNewsDown"+id).style.display="none";
    dojo.byId("divMsgtextTitle"+id).style.padding = 0+'px';
  }
}

function hideIntrotext(id){
  if(dojo.byId("divMsgFull"+id).style.display=="none"){
    dojo.byId("divSubTitle"+id).style.display="none";
    dojo.byId("divMsgTitle"+id).style.height=155+'px';
    dojo.byId("divMsgTitle"+id).style.width=165+'px';
    if(id==1 || id==3 || id==5 || id==7 || id==9 || id==11){
      dojo.byId("divMsgTitle"+id).style.marginRight = 10+'px';
    }
    dojo.byId("divMsgTitle"+id).style.marginBottom = 10+'px';
    dojo.byId("divMsgTitle"+id).style.borderRadius = 5+'px '+5+'px '+5+'px '+5+'px';
    dojo.byId("divMsgTitle"+id).style.flexDirection="column";
    dojo.byId("divMsgTitle"+id).style.justifyContent="center";
    dojo.byId("divMsgTitle"+id).style.display="flex";
    dojo.byId("divMsgTitle"+id).style.fontSize=13+'px';
    dojo.removeClass(dojo.byId("divMsgTitle"+id),"colorMediumDiv");
    dojo.byId("arrowNewsDown"+id).style.display="block";
    dojo.byId("divMsgtextTitle"+id).style.padding = 15+'px';
  }
}

function hideMsg(id,value){
  dojo.byId("divMsgFull"+id).style.display="none";
  dojo.byId("divMsgTitle"+id).style.height=155+'px';
  dojo.byId("divMsgTitle"+id).style.width=165+'px';
  if(id==1 || id==3 || id==5 || id==7 || id==9 || id==11){
    dojo.byId("divMsgTitle"+id).style.marginRight = 10+'px';
  }
  dojo.byId("arrowNewsDown"+id).style.display="block";
  dojo.removeClass(dojo.byId("divMsgTitle"+id),"colorMediumDiv");
  if(value==0.25 || value==1.25 || value==2.25){
    if(dojo.byId("divMsgTitle"+(id+1))){
      dojo.byId("divMsgTitle"+(id+1)).style.display="flex";
    }
    if(dojo.byId("divMsgTitle"+(id+2))){
      dojo.byId("divMsgTitle"+(id+2)).style.display="flex";
    }
    if(dojo.byId("divMsgTitle"+(id+3))){
      dojo.byId("divMsgTitle"+(id+3)).style.display="flex";
    }
  }
  if(value==0.5 || value==1.5 || value==2.5){
    if(dojo.byId("divMsgTitle"+(id+1))){
      dojo.byId("divMsgTitle"+(id+1)).style.display="flex";
    }
    if(dojo.byId("divMsgTitle"+(id+2))){
      dojo.byId("divMsgTitle"+(id+2)).style.display="flex";
    }
    if(dojo.byId("divMsgTitle"+(id-1))){
      dojo.byId("divMsgTitle"+(id-1)).style.display="flex";
    }
  }
  if(value==0.75 || value==1.75 || value==2.75){
    if(dojo.byId("divMsgTitle"+(id+1))){
      dojo.byId("divMsgTitle"+(id+1)).style.display="flex";
    }
    if(dojo.byId("divMsgTitle"+(id-2))){
      dojo.byId("divMsgTitle"+(id-2)).style.display="flex";
    }
    if(dojo.byId("divMsgTitle"+(id-1))){
      dojo.byId("divMsgTitle"+(id-1)).style.display="flex";
    }
  }
  if(value==1 || value==2 || value==3){
    if(dojo.byId("divMsgTitle"+(id-1))){
      dojo.byId("divMsgTitle"+(id-1)).style.display="block";
    }
    if(dojo.byId("divMsgTitle"+(id-2))){
      dojo.byId("divMsgTitle"+(id-2)).style.display="block";
    }
    if(dojo.byId("divMsgTitle"+(id-3))){
      dojo.byId("divMsgTitle"+(id-3)).style.display="block";
    }
  }
}

// =============================================================================
// = Print
// =============================================================================

function showPrint(page, context, comboName, outMode, orientation, attach) {
  showWait();
  quitConfirmed=true;
  noDisconnect=true;
  if (!orientation)
    orientation='L';
  if (!outMode)
    outMode='html';
  var printInNewWin=printInNewWindow;
  if (outMode == "pdf") {
    printInNewWin=pdfInNewWindow;
  }
  if (outMode == "csv") {
    printInNewWin=true;
  }
  if (outMode == "mpp") {
    printInNewWin=true;
  }
  if (context=='favorite' || context=='admin' || context=='organization' || context=='asset') {
    printInNewWin=false;
  }
  if (outMode == "csv" || outMode == "word" || outMode == "excel" || outMode == "download" || context=="download" || context=="downloadList") {
    printInNewWin=true; // Will not show print frame
  }
  if (!printInNewWin) {
    dijit.byId("dialogPrint").show();
  }
  
  cl='';
  if ( (context == 'list' || context == 'downloadList') && dojo.byId('objectClassList')) {
    cl=dojo.byId('objectClassList').value;
  } else if (dojo.byId('objectClass')) {
    cl=dojo.byId('objectClass').value;
  }
  
  id='';
  if (context == 'contextMenuObject'){
    id=dojo.byId('objectIdRow').value;
  }else if (dojo.byId('objectId')) {
    id=dojo.byId('objectId').value;
  }
  
  if(context == 'contextMenu'){
    cl=dojo.byId("contextMenuRefType").value;
    id=dojo.byId("contextMenuRefId").value;
  }

  var params="&orientation=" + orientation+addTokenIndexToUrl();
  dojo.byId("sentToPrinterDiv").style.display='block';
  if (outMode) {
    params+="&outMode=" + outMode;
    if (outMode == 'pdf') {
      dojo.byId("sentToPrinterDiv").style.display='none';
    }
  }

  if (cl=='Organization' && dijit.byId('OrganizationBudgetElementCurrent__byMet_periodYear')) {
    params+='&OrganizationBudgetPeriod='+dijit.byId('OrganizationBudgetElementCurrent__byMet_periodYear').get("value");
  }
  if (context == 'list' || context == 'downloadList' || context == 'download') {
    if (dijit.byId("listShowIdle")) {
      if (dijit.byId("listShowIdle").get('checked')) {
        params+="&idle=true";
      }
    }
    if (dijit.byId("listIdFilter")) {
      if (dijit.byId("listIdFilter").get('value')) {
        params+="&listIdFilter="
            + encodeURIComponent(dijit.byId("listIdFilter").get('value'));
      }
    }
    if (dijit.byId("listNameFilter")) {
      if (dijit.byId("listNameFilter").get('value')) {
        params+="&listNameFilter="
            + encodeURIComponent(dijit.byId("listNameFilter").get('value'));
      }
    }
    if (dijit.byId("listTypeFilter")) {
      if (trim(dijit.byId("listTypeFilter").get('value'))) {
        params+="&objectType="
            + encodeURIComponent(dijit.byId("listTypeFilter").get('value'));
      }
    }
    if (dijit.byId("listBudgetParentFilter")) {
      if (trim(dijit.byId("listBudgetParentFilter").get('value'))) {
        params+="&budgetParent="
            + encodeURIComponent(dijit.byId("listBudgetParentFilter").get('value'));
      }
    }
    if (dijit.byId("listClientFilter")) {
      if (trim(dijit.byId("listClientFilter").get('value'))) {
        params+="&objectClient="
            + encodeURIComponent(dijit.byId("listClientFilter").get('value'));
      }
    }
    if (dijit.byId("listElementableFilter")) {
      if (trim(dijit.byId("listElementableFilter").get('value'))) {
        params+="&objectElementable="
            + encodeURIComponent(dijit.byId("listElementableFilter").get('value'));
      }
    }
    if (attach == 1 || attach === true) {
      params+="&attach=true";
    }
	// #10596 -- status
	if (dojo.byId('countStatus')){
		urlStatus=''
		var countStatus = dojo.byId('countStatus').value;
		for (var i=1;i <= countStatus;i++) {
			if (dijit.byId('showStatus' + i).checked) {
				urlStatus=urlStatus + "&objectStatus" + i + "=" + dijit.byId('showStatus' + i).value;
			}
		}
		if(urlStatus){
			params+="&countStatus="+countStatus;
			params+=urlStatus;
		}
	}

	// #10596 -- Tags 
	if (dojo.byId('countTags')) {
		  var tagsDataToSave = {};
		  var urlObjectTags = '';
		  var urlCountTags = '';
		  var className = dojo.byId('objectClass').value;
		  for (var i=1;i <= dojo.byId('countTags').value;i++) {
			var tagId = dijit.byId('showTags' + i).value;
			var tagIsChecked = dijit.byId('showTags' + i).checked;
			tagsDataToSave['showTags' + tagId + className] = tagIsChecked;
		    if (tagIsChecked) {
		      urlObjectTags=urlObjectTags + "&objectTags" + i + "=" + dijit.byId('showTags' + i).value;
		      directFilterArray[className]['objectTags' + i]=dijit.byId('showTags' + i).value;
			}
			urlCountTags=urlCountTags + "&countTags=" + dojo.byId('countTags').value;
		  }
		  if(urlObjectTags){
			params+=urlCountTags;
			params+=urlObjectTags;
		  }
	}
		
  } else if (context == 'planning') {
    if (dijit.byId("startDatePlanView")) {
      params+="&startDate="
          + encodeURIComponent(formatDate(dijit.byId("startDatePlanView").get(
              "value")));
      params+="&endDate="
          + encodeURIComponent(formatDate(dijit.byId("endDatePlanView").get(
              "value")));
      params+="&format=" + g.getFormat();
      if(dijit.byId('listShowIdleSwitch')){
        if (dijit.byId('listShowIdleSwitch').get("value")=='on') {
          params+="&idle=true";
        }
      }
      if(dijit.byId('showWBS')!=null){
        if (dijit.byId('showWBS').checked) {
          params+="&showWBS=true";
        }
      }
      if (dijit.byId('listShowResource')) {
        if (dijit.byId('listShowResource').checked) {
          params+="&showResource=true";
        }
      }
      if (dojo.byId('showProjectModel')) {
        if (dojo.byId('showProjectModel').checked) {
          url += (param) ? "&" : "?";
          url += "showProjectModel=true";
          param = true;
        }
      }
      if (dijit.byId('listShowLeftWork')) {
        if (dijit.byId('listShowLeftWork').checked) {
          params+="&showWork=true";
        }
      }
      if (dijit.byId('listShowProject')) {
        if (dijit.byId('listShowProject').checked) {
          params+="&showProject=true";
        }
      }
    }
  } else if (context == 'report' || context=='favorite') {
    if (context == 'report' ) { 
      var frm=dojo.byId('reportForm'); 
    } else {
      var frm=dojo.byId('favoriteForm'); 
    }
    frm.action="../view/print.php"+addTokenIndexToUrl('?');
    if (outMode) {
      frm.page.value=page;
      dojo.byId('outMode').value=outMode;
    } else {
      dojo.byId('outMode').value='';
    }
    if (printInNewWin && !attach) {
      frm.target='#';
    } else {
      frm.target='printFrame';
    }
    frm.submit();
    hideWait();
    quitConfirmed=false;
    noDisconnect=false;
    return;
  } else if (context == 'criticalResource') {
    var frm=dojo.byId('criticalResourcesForm'); 
    frm.action="../view/print.php"+addTokenIndexToUrl('?');
    if (outMode) {
      frm.page.value=page;
      dojo.byId('outMode').value='excel';
    } else {
      dojo.byId('outMode').value='';
    }
//    if (0 && printInNewWin && !attach) {
//      frm.target='#';
//    } else {
    frm.target='printFrame';
//    }
    frm.submit();
    hideWait();
    quitConfirmed=false;
    noDisconnect=false;
    return;
  } else if (context == 'imputation' || context == 'hierarchicalBudget') {
    var frm=dojo.byId('listForm');
    frm.action="../view/print.php?orientation=" + orientation
               +"&outMode=" + outMode+"&page="+page
               +"&userId="+dojo.byId("userId").value
               +"&rangeType="+dojo.byId("rangeType").value
               +"&rangeValue="+dojo.byId("rangeValue").value
               +addTokenIndexToUrl();
    if (printInNewWin) {
      frm.target='#';
    } else {
      frm.target='printFrame';
    }
    if (outMode) {
      dojo.byId('outMode').value=outMode;
    } else {
      dojo.byId('outMode').value='';
    }
    frm.submit();
    hideWait();
    quitConfirmed=false;
    noDisconnect=false;
    return;
  }
  var grid=dijit.byId('objectGrid');
  if (grid) {
    var sortWay=(grid.getSortAsc()) ? 'asc' : 'desc';
    var sortIndex=grid.getSortIndex();
    if (sortIndex >= 0) {
      params+="&sortIndex=" + sortIndex;
      params+="&sortWay=" + sortWay;
    }
  }
  if (attach === true) {
    params+="&attach=true";
    redirectOnTab('', '', 'fichier');
    dojo.byId("generateAttachPDFFrame").src="print.php?print=true&page=" + page
    + "&context="+context
    + "&objectClass=" + cl + "&objectId=" + id + params;
  } else if (outMode=="download" && context=='template') {
    dojo.byId("printFrame").src="print.php?print=true&page=" + page+addTokenIndexToUrl();
    hideWait();
  } else if (outMode == "csv" || outMode == "word" || outMode == "excel" || outMode == "download" || context=="download" || context == 'downloadList') {
    dojo.byId("printFrame").src="print.php?print=true&page=" + page
        + "&context="+context
        + "&objectClass=" + cl + "&objectId=" + id + params;
    hideWait();
  } else if (printInNewWin) {
    var newWin=window.open("print.php?print=true&page=" + page
        + "&context="+context
        + "&objectClass=" + cl + "&objectId=" + id + params);
    hideWait();
  } else if(context=='contextMenu'){
    dojo.byId("printFrame").src="print.php?print=true&page=" + page
        + "&context="+context + "&objectClass=" + dojo.byId("contextMenuRefType").value + "&objectId=" + dojo.byId("contextMenuRefId").value + params;
  } else {
    dojo.byId("printFrame").src="print.php?print=true&page=" + page
        + "&context="+context
        + "&objectClass=" + cl + "&objectId=" + id + params;
    if (outMode == 'pdf') {
      // hideWait();
    } 
  }

  quitConfirmed=false;
  noDisconnect=false;
}

function sendFrameToPrinter() {
  dojo.byId("sendToPrinter").blur();
  window.frames['printFrame'].focus();
  window.frames['printFrame'].print();
  dijit.byId('dialogPrint').hide();
  return true;
}

// =============================================================================
// = Detail (from combo)
// =============================================================================

function showDetailDependency() {
  var depType=dijit.byId('dependencyRefTypeDep').get("value");
  if (depType) {
    var dependable=dependableArray[depType];
    var canCreate=0;
    if (canCreateArray[dependable] == "YES") {
      canCreate=1;
    }
    showDetail('dependencyRefIdDep', canCreate, dependable, true);

  } else {
    showInfo(i18n('messageMandatory', new Array(i18n('linkType'))));
  }
}

function showDetailLink() {
  var linkType=dijit.byId('linkRef2Type').get("value");
  if (linkType) {
    var linkable=linkableArray[linkType];
    var canCreate=0;
    if (canCreateArray[linkable] == "YES") {
      canCreate=1;
    }
    showDetail('linkRef2Id', canCreate, linkable, true);

  } else {
    showInfo(i18n('messageMandatory', new Array(i18n('linkType'))));
  }
}

function showDetailOrigin() {
  var originType=dijit.byId('originOriginType').get("value");
  if (originType) {
    var originable=originableArray[originType];
    var canCreate=0;
    if (canCreateArray[originable] == "YES") {
      canCreate=1;
    }
    showDetail('originOriginId', canCreate, originable);

  } else {
    showInfo(i18n('messageMandatory', new Array(i18n('originType'))));
  }
}

function showDetailLinkedObject() {
  var mainObjectClassName = dojo.byId("mainObjectClass").value;
  var linkObjectClassName = dojo.byId("linkObjectClassName").value;
  if(linkObjectClassName){
    var canCreate=0;
    if (canCreateArray[linkObjectClassName] == "YES") {
      canCreate=1;
    }
    showDetail('linkedObjectId', canCreate, linkObjectClassName, true);
  } else {
    return;
  }
}

function showDetail(comboName, canCreate, objectClass, multiSelect, objectId, forceSearch) {
  if (comboName=='projectSelectorFiletering') {
    if (dojo.byId('projectSelectorMode') && dojo.byId('projectSelectorMode').value=='Standard') {
      multiSelect=true;
    } else {
      multiSelect=false;
    }
  }
  var contentWidget=dijit.byId("comboDetailResult");
  dojo.byId("canCreateDetail").value=canCreate;
  if (contentWidget) {
    contentWidget.set('content', '');
  }
  if (!objectClass) {
    objectClass=comboName.substring(2);
  }
  dojo.byId('comboName').value=comboName;
  dojo.byId('comboClass').value=objectClass;
  dojo.byId('comboMultipleSelect').value=(multiSelect) ? 'true' : 'false';
  dijit.byId('comboDetailResult').set('content',null);
  var val=null;
  if (dijit.byId(comboName)) {
    val=dijit.byId(comboName).get('value');
  } else if(dojo.byId(comboName)) {
    val=dojo.byId(comboName).value;
  }
  if (forceSearch) val=null; // will force search
  if (objectId) {
    if (objectId=='new') {
      cl=objectClass;
      id=null;
      window.frames['comboDetailFrame'].document.body.innerHTML='<i>'
          + i18n("messagePreview") + '</i>';
      dijit.byId("dialogDetail").show();
      // frames['comboDetailFrame'].location.href="print.php?print=true&page=preparePreview.php";
      newDetailItem(objectClass);
    } else {
      cl=objectClass;
      id=objectId;
      window.frames['comboDetailFrame'].document.body.innerHTML='<i>'
          + i18n("messagePreview") + '</i>';
      dijit.byId("dialogDetail").show();
      gotoDetailItem(objectClass,objectId);
    }
    
  } else if (!val || val == "" || val == " " || val == "*") {
    cl=objectClass;
    window.frames['comboDetailFrame'].document.body.innerHTML='<i>'
        + i18n("messagePreview") + '</i>';
    dijit.byId("dialogDetail").show();
    displaySearch(cl);
  } else {
    cl=objectClass;
    id=val;
    window.frames['comboDetailFrame'].document.body.innerHTML='<i>'
        + i18n("messagePreview") + '</i>';
    dijit.byId("dialogDetail").show();
    displayDetail(cl, id);
  }
  dojo.connect(dijit.byId("dialogDetail"),"onhide", 
    function(){
      // nothing to do;
    });
}

function displayDetail(objClass, objId) {
  showWait();
  showField('comboSearchButton');
  hideField('comboSelectButton');
  hideField('comboNewButton');
  hideField('comboSaveButton');
  showField('comboCloseButton');
  dijit.byId('comboDetailResult').set('content',null);
  frames['comboDetailFrame'].location.href="print.php?print=true&page=objectDetail.php&objectClass="
      + objClass + "&objectId=" + objId + "&detail=true"+addTokenIndexToUrl();
}

function directDisplayDetail(objClass, objId) {
  showWait();
  hideField('comboSearchButton');
  hideField('comboSelectButton');
  hideField('comboNewButton');
  hideField('comboSaveButton');
  showField('comboCloseButton');
  dijit.byId('comboDetailResult').set('content',null);
  window.frames['comboDetailFrame'].document.body.innerHTML='<i>'
    + i18n("messagePreview") + '</i>';
  dijit.byId("dialogDetail").show();
  frames['comboDetailFrame'].location.href="print.php?print=true&page=objectDetail.php&objectClass="
    + objClass + "&objectId=" + objId + "&detail=true"+addTokenIndexToUrl();
}

function selectDetailItem(selectedValue, lastSavedName) {
  var idFldVal="";
  if (selectedValue) {
    idFldVal=selectedValue;
  } else {
    var idFld=frames['comboDetailFrame'].dojo.byId('comboDetailId');
    var comboGrid=frames['comboDetailFrame'].dijit.byId('objectGrid');
    if (comboGrid) {
      idFldVal="";
      var items=comboGrid.selection.getSelected();
      dojo.forEach(items, function(selectedItem) {
        if (selectedItem !== null) {
          idFldVal+=(idFldVal != "") ? '_' : '';
          idFldVal+=parseInt(selectedItem.id, 10) + '';
        }
      });
    } else {
      if (!idFld) {
        showError('error : comboDetailId not defined');
        return;
      }
      idFldVal=idFld.value;
    }
    if (!idFldVal || idFldVal=="") {
      showAlert(i18n('noItemSelected'));
      return;
    }
  }
  var comboName=dojo.byId('comboName').value;
  var combo=dijit.byId(comboName);
  var comboClass=dojo.byId('comboClass').value;
  crit=null;
  critVal=null;
  if (comboClass == 'Activity' || comboClass == 'Resource'
      || comboClass == 'Ticket') {
    if (comboName.substr(0,15)=='filterValueList') {
      // Do not set current project (would be project of selected item), will
      // apply restriction to selected project
    } else {
      prj=dijit.byId('idProject');
      if (prj) {
        crit='idProject';
        critVal=prj.get("value");
      }else{
        var project = dojo.byId('idProject');
        if (project) {
          crit='idProject';
          critVal=project.value;
        }
      }
    }  
  }
  if (comboName && comboName.indexOf("abacusResource") === 0) {
    var match = comboName.match(/^abacusResource(\d+)$/);
    if (match) {
      var classNum = match[1];
      var fieldId = "idClassName" + classNum;
      var field = dijit.byId(fieldId);
      if (field) {
        field.set("value", idFldVal);
      }
    }
  }
  if (comboName != 'idStatus'  && comboName != 'versionsPlanningDetail' && comboName != 'projectSelectorFiletering') { 
    if (combo) {
      if (comboClass=='ResourceAllNoMaterial' && comboName=='affectationResource') { // Multiple
        var list=idFldVal.split('_');
        refreshList('id' + comboClass, crit, critVal, list, comboName);
        hideDetail();
        return;
      } else {
        refreshList('id' + comboClass, crit, critVal, idFldVal, comboName);
      }
    } else {
      if (comboName == 'dependencyRefIdDep') {
        refreshDependencyList(idFldVal);
        setTimeout("dojo.byId('dependencyRefIdDep').focus()", 1000);
        enableWidget('dialogDependencySubmit');
      } else if (comboName == 'linkRef2Id') {
        refreshLinkList(idFldVal);
        setTimeout("dojo.byId('linkRef2Id').focus()", 1000);
        enableWidget('dialogLinkSubmit');
      } else if (comboName == 'pokerItemRef2Id') {
          refreshPokerItemList(idFldVal);
          setTimeout("dojo.byId('pokerItemRef2Id').focus()", 1000);
          enableWidget('dialogPokerItemSubmit');
      } else if (comboName == 'productStructureListId') {
        refreshProductStructureList(idFldVal,lastSavedName);
        setTimeout("dojo.byId('productStructureListId').focus()",500);
        enableWidget('dialogProductStructureSubmit');
      // ADD aGaye - Ticket 179
      } else if (comboName == 'versionCompatibilityListId'){
    	  refreshVersionCompatibilityList(idFldVal,lastSavedName);
    	  setTimeout("dojo.byId('versionCompatibilityListId').focus()",500);
          enableWidget('dialogVersionCompatibilitySubmit');
      // END aGaye - Ticket 179
      } else if (comboName == 'productVersionStructureListId') {
    	  refreshProductVersionStructureList(idFldVal,lastSavedName);
        setTimeout("dojo.byId('productVersionStructureListId').focus()",500);
        enableWidget('dialogProductVersionStructureSubmit');
      } else if (comboName == 'otherVersionIdVersion') {
        refreshOtherVersionList(idFldVal);
        setTimeout("dojo.byId('otherVersionIdVersion').focus()", 1000);
        enableWidget('dialogOtherVersionSubmit');
      } else if (comboName == 'otherClientIdClient') {
        refreshOtherClientList(idFldVal);
        setTimeout("dojo.byId('otherClientIdClient').focus()", 1000);
        enableWidget('dialogOtherClientSubmit');
      } else if (comboName == 'approverId') {
        refreshApproverList(idFldVal);
        setTimeout("dojo.byId('approverId').focus()", 1000);
        enableWidget('dialogApproverSubmit');
      } else if (comboName == 'originOriginId') {
        refreshOriginList(idFldVal);
        setTimeout("dojo.byId('originOriginId').focus()", 1000);
        enableWidget('dialogOriginSubmit');
      } else if (comboName == 'testCaseRunTestCaseList') {
        refreshTestCaseRunList(idFldVal);
        setTimeout("dojo.byId('testCaseRunTestCaseList').focus()", 1000);
        enableWidget('dialogTestCaseRunSubmit');
      } else if (comboName == 'linkedObjectId') {
        var mainObjectClassName = dojo.byId("mainObjectClass").value;
        var linkObjectClassName = dojo.byId("linkObjectClassName").value;
        refreshLinkObjectList(idFldVal, mainObjectClassName, linkObjectClassName);
        setTimeout("dojo.byId('linkedObjectId').focus()", 1000);
        enableWidget('dialogObjectSubmit');
      } else if (comboName == 'linkProviderTerm') {
        refreshLinkProviderTerm(idFldVal);
      } else if (comboName == 'skillId') {
        refreshSkillList(idFldVal);
        setTimeout("dojo.byId('skillId').focus()", 1000);
        enableWidget('dialogResourceSkillSubmit');
      } else if (comboName == 'userStoryId') {
	    refreshUserStoryList(idFldVal);
	    setTimeout("dojo.byId('userStoryId').focus()", 1000);
	    enableWidget('dialogUserStorySubmit');
	  }   
    }
  }
  if (comboName == 'versionsPlanningDetail') {
	  displayVersionsPlanning(idFldVal,'ProductVersion');
	  hideDetail();
	  return;
  }else if(comboName == 'versionsComponentPlanningDetail'){
    displayVersionsPlanning(idFldVal,'ComponentVersion');
    hideDetail();
    return;                                                    
  }  
  if(comboClass=='Contact' && (dojo.byId('objectClass').value=='Client' || dojo.byId('objectClass').value=='Provider') ){
    saveContact(idFldVal,comboClass,comboName);
    hideDetail();
    return;
  }
  if (combo) {
  	if(comboName == 'projectSelectorFiletering'){
  		var pos = idFldVal.indexOf('_');
  		if(pos != -1){
  		  if (dijit.byId('multiProjectSelector')) {
  			  dijit.byId('multiProjectSelector').set("value", idFldVal);
  		  } else {
  		    showAlert(i18n("errorMultiSelectProject"));
  		  }
  		}else{
  			combo.set("value", idFldVal);
  		}
  	}else if(comboName.substr(0,15) == 'filterValueList'){
  		idFldVal=idFldVal.split('_');
  		combo.set("value", idFldVal);
  		// }
    }else if (comboName=='multipleUpdateValueList'){
      combo.set("selected", idFldVal);
      var nodeList=combo.domNode;
      for (var i = 0; i < nodeList.length; ++i) {
        if(nodeList[i].value==idFldVal){
          nodeList[i].selected=true;
          break;
        }
      }

    }else if (comboName.includes('refreshBottom')){
      if(dijit.byId('new'+inputName))dijit.byId('new'+inputName).focus();
      combo.set("value", idFldVal);
      var inputName = comboName.replace('refreshBottom', '');
      if(dijit.byId('new'+inputName))dijit.byId('new'+inputName).focus();
    }else{
  	  combo.set("value", idFldVal);
  	}
  }
  hideDetail();
  if (dojo.byId('directAccessToList') && dojo.byId('directAccessToList').value=='true' && dojo.byId('directAccessToListButton')) {
    var idButton = dojo.byId('directAccessToListButton').value;
    setTimeout("dijit.byId('" + idButton + "').onClick();", 20);
  }
}

function displaySearch(objClass) {
  if (!objClass) {
    objClass=dojo.byId('comboClass').value;
  }
  showWait();
  hideField('comboSearchButton');
  showField('comboSelectButton');
  if (dojo.byId("canCreateDetail").value=="1" && objClass!='Project' && objClass!='Status' ) {
    showField('comboNewButton');
  } else {
    hideField('comboNewButton');
  }
  hideField('comboSaveButton');
  showField('comboCloseButton');
  var multipleSelect=(dojo.byId('comboMultipleSelect').value == 'true') ? '&multipleSelect=true'
      : '';
  var currentProject=(top.dijit.byId('idProject'))?'&currentSelectedProject='+top.dijit.byId('idProject').get("value"):'';
  if (top.dojo.byId('objectClass') && top.dojo.byId('objectClass')=='Project' && top.dojo.byId('id')) currentProject='&currentSelectedProject='+top.dojo.byId('id').value;
  window.top.frames['comboDetailFrame'].location.href="comboSearch.php?objectClass="
      + objClass + "&mode=search" + multipleSelect+currentProject+addTokenIndexToUrl();
  setTimeout('dijit.byId("dialogDetail").show()', 10);
}

function newDetailItem(objectClass,paramField, paramVal) {
  gotoDetailItem(objectClass,null,paramField, paramVal);
}
function gotoDetailItem(objectClass,objectId, paramField, paramVal) {
  // comboName=dojo.byId('comboName').value;
  dijit.byId("dialogDetail").show();
  hideField('comboSearchButton');
  var objClass=objectClass;
  if (!objectClass) {
    objClass=dojo.byId('comboClass').value;
    showField('comboSearchButton');
  }
  showWait();
  hideField('comboSelectButton');
  hideField('comboNewButton');
  if (dojo.byId("canCreateDetail").value == "1") {
    showField('comboSaveButton');
  } else {
    hideField('comboSaveButton');
  }
  showField('comboCloseButton');
  destinationWidth=frames['comboDetailFrame'].document.body.offsetWidth
  page="comboSearch.php";
  page+="?objectClass=" + objClass;
  if (objectId) {
    page+="&objectId="+objectId;
    page+="&mode=new";    
  } else {
    var curClass = dojo.byId('objectClass').value;
    var curId = dojo.byId('objectId').value;
    var currentScreen=(historyTable[historyPosition] !== undefined) ? historyTable[historyPosition][2] : '';
    var currentItem = new Array(curClass, curId, currentScreen);
    if (currentScreen == "Planning" || currentScreen == "GlobalPlanning" || ((currentScreen == "VersionsPlanning" || currentScreen == "ResourcePlanning") && objectClass == "Activity")) {
      var currentItemParent=(currentItem[1]!=null)?currentItem[1]:curId;
      var originClass=(currentItem[0] && currentScreen != "Planning" && currentScreen != "GlobalPlanning" && currentScreen != "VersionsPlanning" && currentScreen != "ResourcePlanning")?currentItem[0]:curClass;
      page+='&insertItem=true&currentItemParent=' + currentItemParent + '&originClass=' + originClass;
      if (currentScreen == "VersionsPlanning" || currentScreen == "ResourcePlanning") {
        page+="&currentPlanning=" + currentScreen;
      }
    }
    page+="&objectId=0";
    page+="&mode=new";
    if(dijit.byId('idClient')){
    	if(trim(dijit.byId('idClient').get('value')) != ''){
    		page+="&idClient="+dijit.byId('idClient').get('value');
    	}
    }
    if (top.dojo.byId('objectClassManual') && top.dojo.byId('objectClassManual').value=='LiveMeeting' && top.dojo.byId('meetingId') ) {
      page+="&sourceItem=Meeting_"+top.dojo.byId('meetingId').value;
    }
  }
  page+="&destinationWidth=" + destinationWidth;
  if(paramField && paramVal){
    // field array split by ',' and value to corresponding to field array position
    page+="&paramField="+paramField+"&paramVal="+paramVal;
  }
  window.top.frames['comboDetailFrame'].location.href=page+addTokenIndexToUrl();
  setTimeout('dijit.byId("dialogDetail").show()', 10);   
}

window.kanbanScrollToRestore = null;
function saveCurrentKanbanScrollPosition() {
  var kanbanContainer = dojo.byId('divKanbanContainer');
  if (!kanbanContainer) return;
  var columns = dojo.query('[id^="dialogRow"]');
  var columnScrolls = {};
  columns.forEach(function(col) {
    // each column
    columnScrolls[col.id] = (typeof col.scrollTop === 'number') ? col.scrollTop : 0;
  });

  // Scroll horizontal
  var scrollHorizontal = (typeof kanbanContainer.scrollLeft === 'number') ? kanbanContainer.scrollLeft : 0;

  window.kanbanScrollToRestore = {
    horizontal: scrollHorizontal,
    verticals: columnScrolls
  };
}

function saveDetailItem() {
  var comboName=dojo.byId('comboName').value;
  var formVar=frames['comboDetailFrame'].dijit.byId("objectForm");
  if (!formVar) {
    showError(i18n("errorSubmitForm", new Array(page, destination, formName)));
    return;
  }
  var isKanban = dojo.byId('kanbanContainer') !== null;
  if (isKanban) {
	saveCurrentKanbanScrollPosition();
  }
  
  for(name in frames['comboDetailFrame'].CKEDITOR.instances) {
    frames['comboDetailFrame'].CKEDITOR.instances[name].updateElement();
  }
  // validate form Data
  if (1) { // if (formVar.validate()) {
    showWait();
    frames['comboDetailFrame'].dojo
        .xhrPost({
          url : "../tool/saveObject.php?comboDetail=true"+addTokenIndexToUrl(),
          form : "objectForm",
          handleAs : "text",
          load : function(data, args) {
            var contentWidget=dijit.byId("comboDetailResult");
            if (!contentWidget) {
              return;
            }
            contentWidget.set('content', data);
            checkDestination("comboDetailResult");
            var lastOperationStatus=window.top.dojo.byId('lastOperationStatusComboDetail');
            var lastOperation=window.top.dojo.byId('lastOperationComboDetail');
            var lastSaveId=window.top.dojo.byId('lastSaveIdComboDetail');
            if (lastOperationStatus.value == "OK") {
              var currentItemName="";
              if (frames['comboDetailFrame'].dijit.byId("name")) {
                currentItemName=frames['comboDetailFrame'].dijit.byId("name").get("value");
              }
              var currentItem=historyTable[historyPosition];
              var currentScreen=(currentItem !== undefined) ? currentItem[2] : '';			  
              var linkForm = dojo.byId('linkForm');
			  var dependencyForm = dojo.byId('dependencyForm');
              if(currentScreen == 'Diary')loadContent('../view/diary.php','detailDiv','diaryForm');
              if(currentScreen == 'Planning' && !linkForm && !dependencyForm){
                dojo.byId('objectClass').value = dojo.byId('comboClass').value;
                dojo.byId('objectId').value = lastSaveId.value;
              }
              selectDetailItem(lastSaveId.value,currentItemName);
			  if (isKanban && window.kanbanScrollToRestore) {
			      window.needRestoreKanbanScroll = true;
			  }
              if(fromContextMenu){
                var needRefresh=false; 
                if (lastOperation.value=='insert') needRefresh=true;
                fromContextMenu=false;
                var found=false;
                if(currentScreen == 'Planning' && !linkForm) {
                  lClass=dojo.byId('objectClass').value;
                  lId=dojo.byId('objectId').value;
                  var vList=window.top.g.getList();
                  for (var j=0; j<vList.length; j++) {
                    if (vList[j].getItem().reftype==lClass && vList[j].getItem().refid==lId) {
                      found=true;
                      taskPos=j;
                      needRefresh=vList[taskPos].checkParentChangeFromDetail(true); 
                      var planningTypeIndice=window.top.getIndiceForPlanningType(window.top.g.planningType);
                      for (var i=0;i<window.top.planningFieldsDescription[planningTypeIndice].length;i++) {
                        vList[taskPos].setFieldValueFromDetail(window.top.planningFieldsDescription[planningTypeIndice][i],true);
                      }
                      break;
                    }
                  }
                }
                noReplan=( (dojo.byId('automaticRunPlan') && dojo.byId('automaticRunPlan').checked) || found)?false:true;
                if (needRefresh && !noReplan) showWait();
                if (needRefresh && noReplan) refreshJsonPlanning(); 
                else refreshGrid(noReplan);
                //refreshGrid();
              }
            }else{
              dojo.byId('comboDetailResult').style.display = 'inline-block';
              dojo.byId('comboDetailResult').style.visibility = 'visible';
            }
            hideWait();
          },
          error : function() {
            hideWait();
          }
        });

  } else {
    showAlert(i18n("alertInvalidForm"));
  }
}

function hideDetail() {
  hideField('comboSearchButton');
  hideField('comboSelectButton');
  hideField('comboNewButton');
  hideField('comboSaveButton');
  hideField('comboCloseButton');
  frames['comboDetailFrame'].location.href="preparePreview.php"+addTokenIndexToUrl('?');
  dijit.byId("dialogDetail").hide();
  if (dijit.byId(dojo.byId('comboName').value)) {
    dijit.byId(dojo.byId('comboName').value).focus();
  }
}

// =============================================================================
// = Copy Object
// =============================================================================

/**
 * Display a copy object Box
 * 
 */
function copyObjectBox(copyType, contextMenu) {
  if (!contextMenu) contextMenu=false;
  var callBack=function() {

  };
  if (copyType=="copyDocument") {
    callBack=function() {
    };
    var params="&objectClass="+dojo.byId('objectClass').value;
    params+="&objectId="+dojo.byId("objectId").value;   
    params+="&copyType="+copyType;  
    loadDialog('dialogCopyDocument', callBack, true, params, false);
  }else{
  if (copyType=="copyVersion") {
    callBack=function() {
	  var editorType=dojo.byId("copyEditorType").value;
	  if (editorType == "CK" || editorType == "CKInline") {
		ckEditorReplaceEditor("copyToDescription",999);
	  } 
    };
  } else if(copyType=="copyObjectTo"){
    callBack=function() {
	  var editorType=dojo.byId("copyEditorType").value;
	  if (editorType == "CK" || editorType == "CKInline") {
		ckEditorReplaceEditor("copyToDescription",999);
	  }
      dojo.byId('copyClass').value=dojo.byId('objectClass').value;
      dojo.byId('copyId').value=dojo.byId("objectId").value;
      copyObjectToShowStructure();
    };
  }else if(copyType=="copyProject"){
    callBack=function() {
      dojo.byId('copyProjectId').value=dojo.byId("objectId").value;
	  var editorType=dojo.byId("copyEditorType").value;
	  if (editorType == "CK" || editorType == "CKInline") {
	  	ckEditorReplaceEditor("copyToDescription",999);
	  } 
      if (contextMenu==false){
        dijit.byId('copyProjectToName').set('value', dijit.byId('name').get('value')); 
        dijit.byId('copyProjectToType').reset(); 
        if (dijit.byId('idProjectType') && dojo.byId('codeType') && dojo.byId('codeType').value != 'TMP') {
          var runModif="dijit.byId('copyProjectToType').set('value',dijit.byId('idProjectType').get('value'))";
          setTimeout(runModif, 1);
        }
      }  
    };
  }
  var params="&objectClass="+dojo.byId('objectClass').value;
  params+="&objectId="+dojo.byId("objectId").value;   
  params+="&copyType="+copyType+"&fromContextMenu="+fromContextMenu;
  loadDialog('dialogCopy', callBack, true, params, false);
  }
}

function copySubTaskObjectBox(refType,refId) {
  callBack=function() {
    dojo.byId('copyClass').value=refType;
    dojo.byId('copyId').value=refId;
  };
  
  var params="&objectClass="+refType;
  params+="&objectId="+refId;
  params+="&copyType=copyObjectTo";   
  loadDialog('dialogCopy', callBack, true, params, false);
  
}
//WIP #10367 remi
function copyPasteObjectBox(copyType, contextMenu) {
  if (!contextMenu) contextMenu=false;
  var numericIds = [];
  dndSourceTable.getSelectedNodes().forEach(function(node){
	var fullId = node.getAttribute("id"); 
	var numericId = fullId.split("_")[1];
	var line = g.getLineByID(numericId);  
	if(line.getClass() != line.getClass()){
		showAlert(i18n("cantCopy"));
		return;
	}
	numericIds.push(line.getClass()+'_'+line.getId());
  });
  
  var callBack=function() {
	//dojo.byId('copyClass').value=dojo.byId('objectClass').value;
	//dojo.byId('copyId').value=dojo.byId("objectId").value;
  };
  var params ="&copyObjectArray="+numericIds;
  params+="&targetObjectId="+dojo.byId("contextMenuRefId").value;   
  params+="&targetObjectClass="+dojo.byId("contextMenuRefType").value;
  params+="&copyType="+copyType+"&fromContextMenu="+fromContextMenu;
  loadDialog('dialogCopyPaste', callBack, true, params, false);
}

// =============================================================================
// = Origin
// =============================================================================

function addOrigin() {
  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
  var objectClass=dojo.byId('objectClass').value;
  var objectId=dojo.byId("objectId").value;
  dijit.byId("originOriginType").reset();
  refreshOriginList();
  dojo.byId("originId").value="";
  dojo.byId("originRefType").value=objectClass;
  dojo.byId("originRefId").value=objectId;
  dijit.byId("dialogOrigin").show();
  disableWidget('dialogOriginSubmit');
}

function refreshOriginList(selected) {
  disableWidget('dialogOriginSubmit');
  var url='../tool/dynamicListOrigin.php';
  if (selected) {
    url+='?selected=' + selected;
  }
  loadContent(url, 'dialogOriginList', 'originForm', false);
}

function saveOrigin() {
  if (dojo.byId("originOriginId").value == "")
    return;
  loadContent("../tool/saveOrigin.php", "resultDivMain", "originForm", true,
      'origin');
  dijit.byId('dialogOrigin').hide();
}

function removeOrigin(id, origType, origId) {
  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
  dojo.byId("originId").value=id;
  dojo.byId("originRefType").value=dojo.byId('objectClass').value;
  dojo.byId("originRefId").value=dojo.byId("objectId").value;
  dijit.byId("originOriginType").set('value', origType);
  dojo.byId("originOriginId").value=origId;
  actionOK=function() {
    loadContent("../tool/removeOrigin.php", "resultDivMain", "originForm", true,
        'origin');
  };
  msg=i18n('confirmDeleteOrigin', new Array(i18n(origType), origId));
  showConfirm(msg, actionOK);
}


// =============================================================================
// = ChecklistDefinitionLine
// =============================================================================

function addChecklistDefinitionLine(checkId) {
  var params="&checkId=" + checkId;
  loadDialog('dialogChecklistDefinitionLine', null, true, params);
}

function editChecklistDefinitionLine(checkId, lineId) {
  var params="&checkId=" + checkId + "&lineId=" + lineId;
  loadDialog('dialogChecklistDefinitionLine', null, true, params);
}

function saveChecklistDefinitionLine() {
  if (!dijit.byId("dialogChecklistDefinitionLineName").get('value')) {
    showAlert(i18n('messageMandatory', new Array(i18n('colName'))));
    return false;
  }
  loadContent("../tool/saveChecklistDefinitionLine.php", "resultDivMain",
      "dialogChecklistDefinitionLineForm", true, 'checklistDefinitionLine');
  dijit.byId('dialogChecklistDefinitionLine').hide();

}

function removeChecklistDefinitionLine(lineId) {
  var params="?lineId=" + lineId;
  actionOK=function() {
    loadContent("../tool/removeChecklistDefinitionLine.php" + params,
        "resultDivMain", null, true, 'checklistDefinitionLine');
  };
  msg=i18n('confirmDelete', new Array(i18n('ChecklistDefinitionLine'), lineId));
  showConfirm(msg, actionOK);
}

// =============================================================================
// = Checklist
// =============================================================================

function showChecklist(objectClass) {
  if (!objectClass) {
    return;
  }
  if (dijit.byId('id')) {
    var objectId=dijit.byId('id').get('value');
  } else {
    return;
  }
  var params="&objectClass=" + objectClass + "&objectId=" + objectId;
  loadDialog('dialogChecklist', null, true, params, true);
}

function saveChecklist() {
  loadContent('../tool/saveChecklist.php', 'resultDivMain', 'dialogChecklistForm',
      true, 'checklist');
  dijit.byId('dialogChecklist').hide();
  return false;
}

function checkClick(line, item) {
  checkName="check_" + line + "_" + item;
  if (dijit.byId(checkName).get('checked')) {
    for (var i=1; i <= 5; i++) {
      if (i != item && dijit.byId("check_" + line + "_" + i)) {
        dijit.byId("check_" + line + "_" + i).set('checked', false);
      }
    }
  }
}

// =============================================================================
// = History
// =============================================================================

function showHistory(objectClass) {
  if (!objectClass) {
    return;
  }
  if (dijit.byId('id')) {
    var objectId=dijit.byId('id').get('value');
  } else {
    return;
  }
  var params="&objectClass=" + objectClass + "&objectId=" + objectId;
  loadDialog('dialogHistory', null, true, params);
}

//=============================================================================
//= PlanningHistory
//=============================================================================

function showPlanningHistory() {
loadDialog('dialogPlanningHistory', null, true);
}

function scrollDetailPlanningHistory(id,me){
  detailPlaHist = dojo.byId("detailPlanningHistory"+id);
  dojo.byId(me).addEventListener("wheel", function (event) {
    detailPlaHist.scrollBy({ top: event.deltaY*2, behavior: "smooth" });
    event.preventDefault(); 
  });
}

function showDetailPlanningHistory (element, object, result, id) {
  if (!this) return;
  const tooltip = document.createElement('div');
  tooltip.classList.add('tooltipDepPlannigHistory');
  tooltip.style.display = 'block';
  let tooltipContent = '';
  if (object) tooltipContent += '<div id="detailPlanningHistory'+id+'" class="tooltip-section '+((result=='OK')?'messageOK':'messageINVALID')+'" style="height:100% !important; top:0; max-width: 650px; min-height:16px; overflow-y: auto;">'+object+'</div>';
  tooltipContent += '</div>';
    
  tooltip.innerHTML = tooltipContent;
  document.body.appendChild(tooltip);
    
  const rect = element.getBoundingClientRect();
  var space = window.innerHeight - rect.bottom;
  tooltip.style.left = rect.left - window.pageXOffset - tooltip.offsetWidth + rect.width + 'px';
  if(space > tooltip.offsetHeight){
    tooltip.style.top = rect.bottom + window.pageYOffset + 'px';
  }else{
    tooltip.style.top = (rect.top - tooltip.offsetHeight) + window.pageYOffset + 'px';
  }
  element._tooltip = tooltip;
}
// =============================================================================
// = Import
// =============================================================================

/**
 * Display an import Data Box (Not used, for an eventual improvement)
 * 
 */
function importData() {
  var controls = controlImportData();
  if (controls) {
    var frame = getOrCreatePersistentImportFrame();
    frame.onload = function() {
      window.top.importBackgroundFinished();
    };

    dojo.byId('importDataForm').target = 'persistentImportFrame';

    if (dijit.byId('runImportData')) {
      dijit.byId('runImportData').set('disabled', true);
    }
	var visibleFrame = frames['resultImportData'];
	if (visibleFrame && visibleFrame.document) {
	  var oldBody = visibleFrame.document.getElementById('importLastResult');
	  if (oldBody) {
	    oldBody.style.display = 'none';
	  }
	}
	var msgDiv = dojo.byId('importInProgressMessage');
	if (msgDiv) msgDiv.style.display = 'inline-block';

    startImportProgressPolling();

    waitingForReply = false;
    formChangeInProgress = false;
  }
  return controls;
}

function showHelpImportData() {
  var controls=controlImportData(true);
  if (controls) {
    showWait();
    var url='../tool/importHelp.php?elementType='
        + dijit.byId('elementType').get('value');
    url+='&fileType=' + dijit.byId('fileType').get('value');
    frames['resultImportData'].location.href=url+addTokenIndexToUrl();
  }
}

function controlImportData(help) {
  var elementType=dijit.byId('elementType').get('value');
  if (!elementType) {
    showAlert(i18n('messageMandatory', new Array(i18n('colImportElementType'))));
    return false;
  }
  var fileType=dijit.byId('fileType').get('value');
  if (!fileType) {
    showAlert(i18n('messageMandatory', new Array(i18n('colImportFileType'))));
    return false;
  }
  var fileInput = dijit.byId('importFile')
  if (!help && (!fileInput || !fileInput.fileInput || !fileInput.fileInput.value)) {
    showAlert(i18n('messageMandatory', new Array(i18n('colFile'))));
    return false;
  }
  return true;
}
function importFinished() {
  stopImportProgressPolling();
  if (dijit.byId('elementType') && dijit.byId('elementType').get('displayedValue') == i18n('Project')) {
    refreshProjectSelectorList();
  }
  var fileInput = dijit.byId('importFile');
  if (fileInput) {
    fileInput.reset();
  }
}

function importBackgroundFinished() {
  stopImportProgressPolling();
  var onImportScreen = dijit.byId('elementType') ? true : false;
  if (onImportScreen) {
    var visibleFrame = frames['resultImportData'];
    if (visibleFrame) {
      visibleFrame.location.href = '../tool/importLastResult.php' + addTokenIndexToUrl('?');
    }
    if (dijit.byId('runImportData')) {
      dijit.byId('runImportData').set('disabled', false);
    }
    var msgDiv = dojo.byId('importInProgressMessage');
    if (msgDiv) msgDiv.style.display = 'none';
    importFinished();
    showInfo(i18n('ImportCompleted'));
  } else {
    showQuestion(i18n('importCompletedViewResult'), function() {loadMenuBarItem('ImportData', i18n('menuImportData'), 'bar');}, function() {});
  }
}

var importProgressTimer = null;
var importProgressElapsed = 0;

function startImportProgressPolling() {
  importProgressElapsed = 0;
  showImportProgressBar();
  scheduleNextImportPoll();
}

function scheduleNextImportPoll() {
  var delay;
  if (importProgressElapsed < 10) {
    delay = 1000;
  } else if (importProgressElapsed < 60) {
    delay = 5000;
  } else {
    delay = 10000;
  }
  importProgressTimer = setTimeout(pollImportProgress, delay);
}

function purgeImportResult() {
  dojo.xhrGet({
    url: "../tool/purgeImportResult.php" + addTokenIndexToUrl('?'),
    handleAs: "json",
    load: function() {
      var frame = frames['resultImportData'];
      if (frame) {
        frame.location.href = '../tool/importLastResult.php' + addTokenIndexToUrl('?');
      }
    },
    error: function() {
      consoleTraceLog("error purging import result");
    }
  });
}

function pollImportProgress() {
  dojo.xhrGet({
    url: "../tool/importProgress.php" + addTokenIndexToUrl('?'),
    handleAs: "json",
    load: function(data) {
      importProgressElapsed += (importProgressTimer ? 0 : 0);
      if (!data || data.status === 'none' || data.status === 'done' || data.status === 'error') {
        stopImportProgressPolling();
        return;
      }
      updateImportProgressBar(data.current, data.total);
      importProgressElapsed += (delayInSeconds(importProgressElapsed));
      scheduleNextImportPoll();
    },
    error: function() {
      stopImportProgressPolling();
    }
  });
}

function delayInSeconds(elapsed) {
  if (elapsed < 10) return 1;
  if (elapsed < 60) return 5;
  return 10;
}

function stopImportProgressPolling() {
  if (importProgressTimer) {
    clearTimeout(importProgressTimer);
    importProgressTimer = null;
  }
  hideImportProgressBar();
}

function showImportProgressBar() {
  var bar = dojo.byId('topBarImportProgress');
  if (bar) bar.style.display = 'block';
}
function hideImportProgressBar() {
  var bar = dojo.byId('topBarImportProgress');
  if (bar) bar.style.display = 'none';
}
function updateImportProgressBar(current, total) {
  var fill = dojo.byId('topBarImportProgressFill');
  var label = dojo.byId('topBarImportProgressLabel');
  if (fill && total > 0) {
    var pct = Math.round((current / total) * 100);
    fill.style.width = pct + '%';
    if (label) label.innerHTML = current + ' / ' + total + ' (' + pct + '%)';
  }
}

function getOrCreatePersistentImportFrame() {
  var frameName = 'persistentImportFrame';
  var frame = window.top.document.getElementById(frameName);
  if (!frame) {
    frame = window.top.document.createElement('iframe');
    frame.name = frameName;
    frame.id = frameName;
    frame.style.display = 'none';
    window.top.document.body.appendChild(frame);
  }
  return frame;
}

function checkImportDataScreen() {
  dojo.xhrGet({
    url: "../tool/importProgress.php" + addTokenIndexToUrl('?'),
    handleAs: "json",
    load: function(data) {
      if (data && data.status === 'running') {
		var msgDiv = dojo.byId('importInProgressMessage');
        if (dijit.byId('runImportData')) {
          dijit.byId('runImportData').set('disabled', true);
        }
		if (msgDiv) msgDiv.style.display = 'inline-block';
        startImportProgressPolling();
      } else {
        var frame = frames['resultImportData'];
        if (frame) {
          frame.location.href = '../tool/importLastResult.php' + addTokenIndexToUrl('?');
        }
      }
    },
    error: function() {
      consoleTraceLog("error checking import status on screen load");
    }
  });
}

// =============================================================================
// = Report
// =============================================================================

function runReport() {
  clearCharts();
  var fileName = dojo.byId('reportFile').value;
  var listheight=dojo.byId('listHeightReport').value;
  var listReportDivHeight=dojo.byId('listReportDiv').offsetHeight;
  var mainReportDivHeight=dojo.byId('mainReportContainer').offsetHeight;
  var divHeight=dojo.byId('detailReportDiv').offsetHeight;
  var reportMenuListHeight=dojo.byId('reportMenuList').offsetHeight;
  var height = (listheight >= 3*mainReportDivHeight/4)?(270):listheight;
  if(height <=70) height=70;
  //if((height >= dojo.byId('mainReportContainer').offsetHeight) || height==0 )height=250;
  saveContentPaneResizing('contentPaneDetailReportDiv',height,true);
  dijit.byId('listReportDiv').resize({h:height});
  dijit.byId('mainReportContainer').resize();
  var formVar=dijit.byId('reportForm');
  var reportParams='';
  dojo.forEach(
    formVar.getChildren(),  
    function(widget){
      var name=widget.id;
      if (!name || name=='') return;
      if (name.substr(0,6)=='report') return;
      if (reportParams!='') reportParams+='|';
      if (widget.declaredClass=='dijit.form.DateTextBox') reportParams+=widget.id+'='+widget.displayedValue;
      //else if (widget.declaredClass=='dijit.form.NumberSpinner') reportParams+=widget.id+'='+widget.displayedValue;
      else reportParams+=widget.id+'='+widget.value;
    }
  );
  var currentItem=historyTable[historyPosition];
  currentItem[3]=reportParams;
  historyTable[historyPosition]=currentItem;
  if(formVar.validate()) {
    showWait();
    loadContent("../report/" + fileName, "detailReportDiv", "reportForm", false);
  } else {
    showAlert(i18n("alertInvalidForm"));
  }
  
}
function saveReportInToday() {
  var fileName = dojo.byId('reportFile').value;
  var form="reportForm";
  if(fileName=="showIntervention" && dojo.byId("consultationPlannedWorkManualParamDiv")){
    form="listFormConsPlannedWorkManual";
  }
    loadContent("../tool/saveReportInToday.php", "resultDivMain", form, true,
    'report');
}
function saveReportParametersForDialog() {
  var callback=function(){
  hideWait();
  showDialogAutoSendReport();
  };
  loadDiv("../tool/saveReportParametersForDialog.php", "resultDivMain", "reportForm", callback);
}   

function reportSelectCategory(idCateg) {
  if (isNaN(idCateg)) return;
  loadContent("../view/reportsParameters.php?idReport=", "reportParametersDiv",
      null, false);
  var tmpStore=new dojo.data.ItemFileReadStore(
      {
        url : '../tool/jsonList.php?required=true&listType=list&dataType=idReport&critField=idReportCategory&critValue='
            + idCateg+addTokenIndexToUrl()
      });
  var mySelectWidget=dijit.byId("reportsList");
  mySelectWidget.reset();
  var mySelect=dojo.byId("reportsList");
  mySelect.options.length=0;
  var nbVal=0;
  tmpStore.fetch({
    query : {
      id : "*"
    },
    onItem : function(item) {
      mySelect.options[mySelect.length]=new Option(tmpStore.getValue(item,
          "name", ""), tmpStore.getValue(item, "id", ""));
      nbVal++;
    },
    onError : function(err) {
      console.info(err.message);
    }
  });
}

function reportSelectReport(idReport) {
  if (isNaN(idReport)) return;
  clearCharts();
  dojo.query(".section").removeClass("reportSelected");
  dojo.addClass(dojo.byId('report'+idReport),"reportSelected");
  var height=dojo.byId('mainReportContainer').offsetHeight;
  dijit.byId('listReportDiv').resize({h:height});
  dijit.byId('mainReportContainer').resize();
  loadContent("../view/reportsParameters.php?idReport=" + idReport,
  "reportParametersDiv", null, false);
  // mehdi Ticket #3092
  detailReportDiv.innerHTML = ""; 
}
function clearCharts() {
// if (dojo.byId('reportChart')) {
// Chart.getChart("reportChart").destroy();
// }
  dojo.query(".reportChart").forEach(function(node, index, nodelist) {
    var name=node.getAttribute('id');
    Chart.getChart(name).destroy();
  });
}

// favorite reports management

function refreshFavoriteReportList(idFavoriteRow) {
  if (!dijit.byId('favoriteReports_'+idFavoriteRow)) return;
  dijit.byId('favoriteReports_'+idFavoriteRow).refresh();
  // var listContent=trim(dijit.byId('favoriteReports').get('content'));
}
function saveReportAsFavorite(idFavoriteRow) {
  if(!idFavoriteRow)idFavoriteRow=1;
  var fileName=dojo.byId('reportFile').value;
  var callback=function(){
   refreshFavoriteReportList(idFavoriteRow);
   dijit.byId('listFavoriteReports_'+idFavoriteRow).openDropDown();
   var delay=2000;
   var listContent=trim(dijit.byId('favoriteReports_'+idFavoriteRow).get('content'));
   if (listContent=="") {delay=1;}
   hideReportFavoriteTooltip(delay, idFavoriteRow);
  };
  loadContent("../tool/saveReportAsFavorite.php" , "resultDivMain", "reportForm", true, 'report',false,false, callback);
}

function showReportFavoriteTooltip(idFavoriteRow) {
  if(!idFavoriteRow)idFavoriteRow=1;
  var listContent=trim(dijit.byId('favoriteReports_'+idFavoriteRow).get('content'));
  if (listContent=="") {
   return;
  }
  clearTimeout(closeFavoriteReportsTimeout);
  clearTimeout(openFavoriteReportsTimeout);
  openFavoriteReportsTimeout=setTimeout('dijit.byId("listFavoriteReports_'+idFavoriteRow+'").openDropDown()',popupOpenDelay);
}

function hideReportFavoriteTooltip(delay, idFavoriteRow) {
  if(!idFavoriteRow)idFavoriteRow=1;
  if (!dijit.byId("listFavoriteReports_"+idFavoriteRow)) return;
  clearTimeout(closeFavoriteReportsTimeout);
  clearTimeout(openFavoriteReportsTimeout);
  closeFavoriteReportsTimeout=setTimeout('dijit.byId("listFavoriteReports_'+idFavoriteRow+'").closeDropDown()',delay);
}

function removeFavoriteReport(id, idFavoriteRow) {
var callBack=function() { refreshFavoriteReportList(idFavoriteRow);};
dojo.xhrGet({
 url: '../tool/removeFavoriteReport.php?idFavorite='+id+addTokenIndexToUrl(),
 handleAs : "text",
 load: callBack
});
}

function reorderFavoriteReportItems() {
var nodeList=dndFavoriteReports.getAllNodes();
var param="";
for (var i=0; i < nodeList.length; i++) {
 var domNode=nodeList[i];
 var item=nodeList[i].id.substr(11);
 var order=dojo.byId("favoriteReportOrder" + item);
 if (dojo.hasClass(domNode,'dojoDndItemAnchor')) {
   order.value=null;
   dojo.removeClass(domNode,'dojoDndItemAnchor');
   dojo.query('dojoDndItemAnchor').removeClass('dojoDndItemAnchor');
   // continue;
 }
 if (order) {
   order.value=i + 1;
   param+=((param)?'&':'?')+"favoriteReportOrder"+item+"="+(i+1);
 }
}
dojo.xhrPost({
 url: '../tool/saveReportFavoriteOrder.php'+param+addTokenIndexToUrl(),
 handleAs: "text",
 load: function(data,args) {
   refreshFavoriteReportList(); 
 }
});
}

function checkEmptyReportFavoriteTooltip(idFavoriteRow) {
if(!idFavoriteRow)idFavoriteRow=1;
var listContent=trim(dijit.byId('favoriteReports_'+idFavoriteRow).get('content'));
if (listContent=="") {
 dijit.byId("listFavoriteReports_"+idFavoriteRow).closeDropDown();
}
}

// =============================================================================
// = Linked Object by id to main object
// =============================================================================

function addLinkObjectToObject(mainObjectClassName, idOfInstanceOfMainClass, linkObjectClassName) {
  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
  if (typeof dojo.byId('linkedObjectId') !== 'undefined') {
    var node = document.getElementById("linkedObjectId");
    while (node.firstChild) node.removeChild(node.firstChild);
  }
  refreshLinkObjectList(0,mainObjectClassName, linkObjectClassName);
  dijit.byId("dialogObject").show();

  dojo.byId("mainObjectClass").value = mainObjectClassName;
  dojo.byId("idInstanceOfMainClass").value = idOfInstanceOfMainClass;
  dojo.byId("linkObjectClassName").value = linkObjectClassName;

  disableWidget('dialogObjectSubmit');
}

function saveLinkObject() {  
  var param="";  
  var nbSelected=0;
  if (dojo.byId("linkedObjectId").value == "") {
      return;
  }
  list=dojo.byId("linkedObjectId");
  if (list.options) {
    selected=new Array();
    for (var i=0; i < list.options.length; i++) {
      if (list.options[i].selected) {
        selected.push(list.options[i].value);
        nbSelected++;
      }
    }
  }  
  param="?linkedObjectId="+selected;
  param+="&mainObjectClass="+dojo.byId('mainObjectClass').value;
  param+="&idInstanceOfMainClass="+dojo.byId('idInstanceOfMainClass').value;
  param+="&linkObjectClassName="+dojo.byId('linkObjectClassName').value;
  loadContent("../tool/saveObjectLinkedByIdToMainObject.php"+param, "resultDivMain", "objectFormDialog", true, 'linkObject');
  dijit.byId('dialogObject').hide();
}

function removeLinkObjectFromObject(mainObjectClassName, linkObjectClassName, idLinkObject, nameLinkObject) {
  var param="?mainObjectClassName="+mainObjectClassName;
  param+="&linkObjectClassName="+linkObjectClassName;
  param+="&idLinkObject="+idLinkObject;

if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }

  actionOK=function() {
    loadContent("../tool/removeObjectLinkedByIdToMainObject.php"+param, "resultDivMain", "objectForm", true, 'linkObject');
  };

  msg=i18n('confirmRemoveLinkObjFromObj') + '<br/>' + nameLinkObject;
  showConfirm(msg, actionOK);
}

function refreshLinkObjectList(selected, mainObjectClassName, linkObjectClassName) {
  var param='';  
  selected = typeof selected !== 'undefined' ? selected : 0;
  mainObjectClassName = typeof mainObjectClassName !== 'undefined' ? mainObjectClassName : '';
  linkObjectClassName = typeof linkObjectClassName !== 'undefined' ? linkObjectClassName : '';
  disableWidget('dialogObjectSubmit');
  var url='../tool/dynamicListObjectLinkedByIdToMainObject.php';
  param='?selected=' + selected;    
  if (mainObjectClassName!='') {
    param+='&mainObjectClass=' + mainObjectClassName;      
  }
  if (linkObjectClassName!='') {
    param+='&linkObjectClassName=' + linkObjectClassName;      
  }
  url+=param;
  loadContent(url, 'dialogObjectList', 'objectForm', false);
  selectLinkObjectItem();
}

function selectLinkObjectItem() {
  var nbSelected=0;
  list=dojo.byId('linkedObjectId');
  if (list.options) {
    for (var i=0; i < list.options.length; i++) {
      if (list.options[i].selected) {
        nbSelected++;
      }
    }
  }
  if (nbSelected > 0) {
    enableWidget('dialogObjectSubmit');
  } else {
    disableWidget('dialogObjectSubmit');
  }
}
function saveChangedStatusObject() {
    list=dojo.byId("changeStatusId");
    if (list.options) {
      selected=0;
      for (var i=0; i < list.options.length; i++) {
        if (list.options[i].selected) {
          selected=list.options[i].value;
          i = list.options.length+10;
        }
      }
      var objectClass = dojo.byId("objectClassChangeStatus").value;
      var objectId = dojo.byId("idInstanceOfClassChangeStatus").value;   
      var saveStatus=function() {
        url = "";
        param="?newStatusId="+selected;
        param+="&objectClass="+objectClass;
        param+="&idInstanceOfClass="+objectId;
        loadContent("../tool/changeObjectStatus.php"+param, "resultDivMain", "objectForm", true, objectClass);
        dijit.byId('dialogChangeStatus').hide();
      };
      checkMandatoryNoteOnStatusChange(objectClass, objectId, selected, function() {
        dijit.byId('dialogChangeStatus').hide();
        openMandatoryNoteOnStatusChange(saveStatus);
      }, saveStatus);
    }  
}

function selectChangeStatusItem() {
  var nbSelected=0;
  list=dojo.byId('changeStatusId');
  if (list.options) {
    for (var i=0; i < list.options.length; i++) {
      if (list.options[i].selected) {
        nbSelected=1;
        break;
      }
    }
  }
  if (nbSelected > 0) {
    enableWidget('dialogChangeStatusSubmit');
  } else {
    disableWidget('dialogChangeStatusSubmit');
  }
}

function changeObjectStatus(objClass, objId, objTypeId, objStatusId) {
  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
  
  // empty select of previous options
  if (typeof dojo.byId('changeStatusId') !== 'undefined') {
    var node = document.getElementById("changeStatusId");
    while (node.firstChild) node.removeChild(node.firstChild);
  }
  
  var param='';
    
  disableWidget('dialogChangeStatusSubmit');
  var url='../tool/dynamicListChangeStatus.php';

  param = '?objectId=' + objId;
  param += '&objectClass=' + objClass;
  param += '&idType=' + objTypeId;
  param += '&idStatus=' + objStatusId;

  url+=param;
  loadContent(url, 'dialogChangeStatusList', 'changeStatusForm', false);
  selectChangeStatusItem();

  dijit.byId("dialogChangeStatus").show();

  dojo.byId("objectClassChangeStatus").value = objClass;
  dojo.byId("idInstanceOfClassChangeStatus").value = objId;
  dojo.byId("idStatusOfInstanceOfClassChangeStatus").value = objStatusId;
  dojo.byId("idTypeOfInstanceOfClassChangeStatus").value = objTypeId;
}

function changeStatusNotification(objId, objStatusId) {
  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
  
  if (objStatusId == 1) { newStatusId = 2; } else { newStatusId = 1;}
  param="?newStatusId="+newStatusId;
  param+="&idInstanceOfClass="+objId;

  loadContent("../tool/changeStatusNotification.php"+param, "resultDivMain", "objectForm", true, "Notification");
  refreshNotificationTree(false);
}
 
// =============================================================================
// = Misceallanous
// =============================================================================

var manualWindow=null;
var helpTimer=false;
function showHelp(link) {
  if (helpTimer) return; // avoid double open
  helpTimer=true;
  if (manualWindow) manualWindow.close();
  var objectClass=(dojo.byId('objectClassList'))?dojo.byId('objectClassList'):dojo.byId('objectClass');
  var objectClassManual=dojo.byId('objectClassManual');
  var section='';
  var selectedTab=(dijit.byId('parameterTabContainer'))?dijit.byId('parameterTabContainer').selectedChildWidget.get("id"):null;
  if (objectClassManual) {
    section=objectClassManual.value;
  } else if (objectClass) {
    section=objectClass.value;
  }
  if(link == 'ShortCut'){
    section = link;
  }else if(link == 'Client'){
    section = link;
  }else if(link == 'Contact'){
    section = link;
  }else if(link == 'Resource'){
    section = link; 
  }else if(link == 'User'){
    section = link;
  }else if(link == 'Project'){
    section = link;
  }else if(link == 'Affectation'){
    section = link;
  }else if(link == 'Activity'){
    section = link;
  }else if(link == 'Milestone'){
    section = link;
  }else if(link == 'Planning'){
    section = link;
  }else if(link == 'Imputation'){
    section = link; 
  }else if(link == 'Ticket'){
    section = link;  
  }
  
//  if(link == 'ShortCut'){
//    section = link;
//  }

  dojo.xhrGet({
    url : "../tool/getManualUrl.php?section=" + section+"&tab="+selectedTab+addTokenIndexToUrl(),
    handleAs : "text",
    load : function(data, args) {
      var url=data;
      var name="Manual";
      var attributes='toolbar=yes, titlebar=no, menubar=no, status=no, scrollbars=yes, directories=no, location=no, resizable=yes,'
          + 'height=650, width=1024, top=0, left=0';
      manualWindow=window.open(url, name, attributes);
      manualWindow.focus();
    },
    error : function() {
      consoleTraceLog("Error retrieving Manual URL for section '"+section+"'");
    }
  });
  setTimeout("helpTimer=false;",1000);
  return false;
}
/**
 * Refresh a list (after update)
 */
var refreshListInProgress=new Array();
function refreshList(field, param, paramVal, selected, destination, required, param1, paramVal1,objectClass) {
  if (destination && refreshListInProgress.indexOf(destination)>-1) return; // update already in progress, skip update to avoid infinite loop
  if (destination) refreshListInProgress.push(destination);
  //if (field=='idContact') field='idAffectable';
  var urlList='../tool/jsonList.php?listType=list&dataType=' + field+addTokenIndexToUrl();
  if (param) {
    urlList+='&critField=' + param;
    urlList+='&critValue=' + paramVal;
    if(Array.isArray(paramVal)) {
      urlList += '&critArray=1';
    }
  }
  if (param1) {
    urlList+='&critField1=' + param1;
    urlList+='&critValue1=' + paramVal1;
  }
  if (selected && field!='planning') {
    urlList+='&selected=' + selected;
  }
  if (required || Array.isArray(paramVal)) {
    urlList+='&required=true';
  }
  if (objectClass) urlList+='&objectClass='+objectClass;
  if (destination=='idProjectPlan') {
      urlList+='&withoutLeaveProject=1';
  }
  if (directAccessIndex) {
    urlList += "&directAccessIndex=" + directAccessIndex;
  }

  var datastore=new dojo.data.ItemFileReadStore({
    url : urlList+addTokenIndexToUrl()
  });
  var store=new dojo.store.DataStore({
    store : datastore
  });
  if (destination) {
    var mySelect=dijit.byId(destination);
  } else {
    var mySelect=dijit.byId(field);
  }
  // mySelect.set('store', store);
  mySelect.set({labelAttr: 'name', store: store, sortByLabel: false});
  store.query({
    id : "*"
  }).then(function(items) {
    if (destination) {
      var mySelect=dijit.byId(destination);
    } else {
      var mySelect=dijit.byId(field);
    }
    if (required && ! selected && ! trim(mySelect.get('value')) ) { // required but no value set : select first
      mySelect.set("value", items[0].id);
    }
    if (selected) { // Check that selected is in the list
      var found=false;
      items.forEach(function(item) {
        if(Array.isArray(selected)==false){
          if(Number.isInteger(selected)==true)selected=selected.toString();
          selectionList=selected.split('_');
        }else{
          selectionList=selected;
        }
        if (selectionList.includes(item.id)) found=true;
      });
      if (! found) {
        mySelect.reset();
        if (required) mySelect.set("value", items[0].id);
        else mySelect.set("value", null);
      }
    }
    if (field=='planning' || field=='idWorkCategory') {
      mySelect.set("value",selected); 
    }
    if(destination){
      if(destination.substr(0,15)=='filterValueList' || destination=='multipleUpdateValueList') {
        var list=dojo.byId(destination);
        if(Array.isArray(selected)==false){
          if(Number.isInteger(selected)==true)selected=selected.toString();
          selectionList=selected.split('_');
        }else{
          selectionList=selected;
        }
        // while (list.options.length) {list.remove(0);} // Clean combo
        items.forEach(function(item) {
          if (!item.name || item.id==' ' || item.name==selected) {
          } else {
            if (selectionList.indexOf(item.id)>=0 && 1) {
              var found=false;
              for (var i=0;i<list.options.length;i++) { if (list.options[i].value==item.id) found=true; }
              if (!found) {
                var option = document.createElement("option");
                option.text = item.name;
                option.value = item.id;
                option.selected=true;
                list.add(option);
              }
            }
          }
        });
      } else if (destination=='affectationResource' && Array.isArray(selected)) {
        items.forEach(function(item) {
          if (!item.name || item.id==' ') return;
          if (selectionList.indexOf(item.id)>=0) {
            var already=dojo.some(affectationResourceIds, function(r){ return r.id==item.id; });
            if (!already) affectationResourceIds.push({id: item.id, label: item.name});
          }
        });
        renderAffectationResourceChips();
      }
    }
    if (destination) setTimeout("refreshListInProgress.splice(refreshListInProgress.indexOf('"+destination+"'),1);",100);
  });
}

function refreshListSpecific(listType, destination, param, paramVal, selected, required, param2, paramVal2) {
  var urlList='../tool/jsonList.php?listType=' + listType;
  if (param) {
    urlList+='&' + param + '=' + paramVal;
  }
  if (param2) {
    urlList+='&' + param2 + '=' + paramVal2;
  }
  if (selected) {
    urlList+='&selected=' + selected;
  }
  if (required) {
    urlList+='&required=true';
  }
  if (directAccessIndex) {
    urlList += "&directAccessIndex=" + directAccessIndex;
  }
  var datastore=new dojo.data.ItemFileReadStore({
    url : urlList+addTokenIndexToUrl()
  });
  var store=new dojo.store.DataStore({
    store : datastore
  });
  store.query({
    id : "*"
  });
  
  var mySelect=dijit.byId(destination);
  if (mySelect) mySelect.set('store', store);
  else console.error("ERROR on refreshListSpecific() for destinarion='"+destination+"' that does not exist");
}

function setClientValueFromProject(field, projectId) {
  dojo.xhrGet({
    url : "../tool/getClientValueFromProject.php?idProject=" + projectId+addTokenIndexToUrl(),
    handleAs : "text",
    load : function(data, args) {
      client=dijit.byId(field);
      if (client && data) {
        client.set("value", data);
      }
    },
    error : function() {
    }
  });
}

var menuHidden=false;
var menuActualStatus='visible';
var menuDivSize=0;
var menuShowMode='CLICK';
var hideShowMenuInProgress=false;
var hideShowTries=0;
/**
 * Hide or show the Menu (left part of the screen
 */
function hideShowMenu(noRefresh,noStore) {
  if(isNewGui)return;
  var disableSlide=true;
  if (!dijit.byId("leftDiv")) {
    return;
  }
  if (!dijit.byId("leftDiv") || !dijit.byId("centerDiv") || !dijit.byId("leftDiv_splitter")) {
    hideShowTries++;
    if (hideShowTries<10) setTimeout("hideShowMenu();",100);
    return;
  }
  hideShowTries=0;
  hideShowMenuInProgress=true;
  duration=1;
  if (menuActualStatus == 'visible' || !menuHidden) {
    saveDataToSession("hideMenu","YES",true);
    if (!noStore) menuDivSize=dojo.byId("leftDiv").offsetWidth;
    fullWidth=dojo.byId("mainDiv").offsetWidth;
    if (menuDivSize < 2) {
      menuDivSize=dojo.byId("mainDiv").offsetWidth * .2;
    }
    if (disableSlide || !isHtml5()) {
      duration=0;
      dojo.byId('menuBarShow').style.display='block';
      dojo.byId('leftDiv_splitter').style.display='none';
      dijit.byId("leftDiv").resize({
        w : dojo.byId("menuBarShow").offsetWidth
      });
    } else {
      dojox.fx.combine([ dojox.fx.animateProperty({
        node : "leftDiv",
        properties : {
          width : 34
        },
        duration : duration
      }), dojox.fx.animateProperty({
        node : "centerDiv",
        properties : {
          left : 45,
          width : fullWidth
        },
        duration : duration
      }), dojox.fx.animateProperty({
        node : "leftDiv_splitter",
        properties : {
          left : 31
        },
        duration : duration
      }) ]).play();
      setTimeout("dojo.byId('menuBarShow').style.display='block'", duration);
      setTimeout("dojo.byId('leftDiv_splitter').style.display='none';",duration);
    }
    menuHidden=true;
    menuActualStatus='hidden'; 
    dojo.byId('hideMenuBarShowButton2').style.display='none';
  } else {
    saveDataToSession("hideMenu","NO",true);  
    if (menuDivSize < 20) {
      menuDivSize=dojo.byId("mainDiv").offsetWidth * .2;
    }
    if (disableSlide || !isHtml5()) {
      duration=0;
      dijit.byId("leftDiv").resize({
        w : menuDivSize
      });
      dojo.byId('menuBarShow').style.display='none';
      dojo.byId('leftDiv_splitter').style.left='20px';
      dojo.byId('leftDiv_splitter').style.display='block';
    } else {
      dojox.fx.combine([ dojox.fx.animateProperty({
        node : "leftDiv",
        properties : {
          width : menuDivSize
        },
        duration : duration
      }), dojox.fx.animateProperty({
        node : "centerDiv",
        properties : {
          left : menuDivSize + 5
        },
        duration : duration
      }), dojox.fx.animateProperty({
        node : "leftDiv_splitter",
        properties : {
          left : menuDivSize
        },
        duration : duration
      }) ]).play();
      dojo.byId('menuBarShow').style.display='none';
      dojo.byId('leftDiv_splitter').style.left='20px';
      dojo.byId('leftDiv_splitter').style.display='block';
    }
    menuHidden=false;
    menuActualStatus='visible';
    dojo.byId('hideMenuBarShowButton2').style.display='block';
  }
  setTimeout('dijit.byId("globalContainer").resize();', duration + 10);
  var detailHidden=false;
  if (dojo.byId('detailBarShow') && dojo.byId('detailBarShow').style.display=='block') detailHidden=true;
  if (!noRefresh && !formChangeInProgress && dojo.byId('id') && dojo.byId('id').value && !detailHidden) {
    setTimeout('loadContent("objectDetail.php", "detailDiv", "listForm");',
        duration + 50);
  }
  setTimeout("hideShowMenuInProgress=false;",duration+50);
  dojo.byId("hideMenuBarShowButton2").style.left=dojo.byId("leftDiv").offsetWidth+3+"px";
}

function hideMenuBarShowMode() {
  hideShowMenu(false);
  dijit.byId("iconMenuUserScreen").closeDropDown();
}

function hideMenuBarShowModeTop(){ 
  if(dojo.byId('statusBarDiv').style.height == '0px'){
    saveDataToSession("hideMenuTop","NO",true);
    dojo.byId('statusBarDiv').style.height="48px";
    dojo.byId('statusBarDiv').style.padding="1px";
    dojo.byId('leftDiv').style.top='82px';
    dojo.byId('centerDiv').style.top='82px';
    dojo.byId('menuBarShow').style.top='82px';
    var height=parseInt(dojo.byId('mainDiv').offsetHeight)-82;
    dijit.byId('centerDiv').resize({h:height});
    dijit.byId('leftDiv').resize({h:height});
    if(dojo.byId('menuBarShow').style.display=='none' || dojo.byId('menuBarShow').style.display == ''){
      dojo.byId('leftDiv_splitter').style.top='82px';
      var height = dojo.byId("leftDiv").offsetHeight+50;
      dojo.byId('leftDiv_splitter').style.height=height+'px';
    }
  }else{
    saveDataToSession("hideMenuTop","YES",true);
    // dojo.byId('statusBarDiv').style.display='none';
    dojo.byId('statusBarDiv').style.height="0px";
    dojo.byId('statusBarDiv').style.padding="0px";
    dojo.byId('leftDiv').style.top='30px';
    dojo.byId('centerDiv').style.top='30px';
    dojo.byId('menuBarShow').style.top='30px';
    var height=parseInt(dojo.byId('mainDiv').offsetHeight)-30;
    dijit.byId('centerDiv').resize({h:height});
    dijit.byId('leftDiv').resize({h:height});
    if(dojo.byId('menuBarShow').style.display=='none' || dojo.byId('menuBarShow').style.display == '' ){
      dojo.byId('leftDiv_splitter').style.top='32px';
      var height = dojo.byId("leftDiv").offsetHeight;
      dojo.byId('leftDiv_splitter').style.height=height+'px';
    }
    if(switchedMode==true){
      switchModeOn();
    }
  }
  dijit.byId("iconMenuUserScreen").closeDropDown();
}

function menuClick() {
  if (menuHidden) {
    menuHidden=false;
    hideShowMenu(true);
    menuHidden=true;
  }
}

var switchedMode=false;
var loadingContentDiv=false;
var listDivSize=0;
var switchedVisible='';
var switchListMode='CLICK';

function switchModeOn(objectIdScreen){
  switchedMode=true;
  // saveDataToSession('coversListPlan', 'CLOSE', true)
  if (!dojo.byId("listDiv")) {
    if (listDivSize == 0) {
      listDivSize=dojo.byId("centerDiv").offsetHeight * .4;
    }
    return;
  } else {
    listDivSize=dojo.byId("listDiv").offsetHeight;
  }
  if (dojo.byId('listDiv_splitter')) {
    dojo.byId('listDiv_splitter').style.display='none';
  }
  if (dijit.byId('id')) {
    hideList();
  } else {
    loadingContentDiv=false;
    showList();
  }
}

function switchModeOff(){
  switchedMode=false;
  if (!dojo.byId("listDiv")) {
    return;
  }
  if (dojo.byId('listBarShow')) {
    dojo.byId('listBarShow').style.display='none';
  }
  if (dojo.byId('detailBarShow')) {
    dojo.byId('detailBarShow').style.display='none';
  }
  if (dojo.byId('listDiv_splitter')) {
    dojo.byId('listDiv_splitter').style.display='block';
  }
  if (listDivSize == 0) {
    listDivSize=dojo.byId("centerDiv").offsetHeight * .4;
  }
  dijit.byId("listDiv").resize({
    h : listDivSize
  });
  dijit.byId("mainDivContainer").resize();
}

function switchModeLayout(paramToSend,notGlobal){
  var currentScreen=(dojo.byId('objectClassManual'))?dojo.byId('objectClassManual').value:'Object';
  if((currentScreen == "PlanningWorkPlan") || (dojo.byId('objectClass') && dojo.byId('objectClass').value!='Work' && dojo.byId('objectClass').value!='')){
    var currentObject=(dojo.byId('objectClass'))?dojo.byId('objectClass').value:null;
  }else{
    showInfo(i18n("alertIncorrectScreenSwitch"));
    return;
  }
  if(checkFormChangeInProgress()){
    return;
  }
  var objectIdScreen=(dojo.byId('objectId'))?dojo.byId('objectId').value:null;
  var currentItem=historyTable[historyPosition];
  if (currentItem && currentItem!='undefined' && currentItem.length>2) currentScreen=currentItem[2];
  if(currentScreen=='Reports'){
    return false;
  }
  if (paramToSend=='top' || paramToSend=='left' || paramToSend=='multiple'){
      var screen=(dojo.byId('objectClassManual'))?currentScreen  : currentObject;
      var paramDiv=(!notGlobal)?'paramScreen':'paramScreen_'+screen;
      if(switchedMode==true){
        paramDiv='paramScreen';
        notGlobal=false;
        switchModeOff();
      }
      switchModeLoad(currentScreen,currentObject,paramDiv,paramToSend,objectIdScreen,notGlobal);
      setActionCoverListNonObj ('CLOSE',true);
  }else if(paramToSend=='bottom' || paramToSend=='trailing'){
    var screen=(dojo.byId('objectClassManual'))?currentScreen  : currentObject;
    var paramDiv=(!notGlobal)?'paramRightDiv':'paramRightDiv_'+screen;
    switchModeLoad(currentScreen,currentObject,paramDiv,paramToSend,objectIdScreen,notGlobal);
  }else if(paramToSend=='col' || paramToSend=='tab'){
    var paramDiv='paramLayoutObjectDetail';
    switchModeLoad(currentScreen,currentObject,paramDiv,paramToSend,objectIdScreen,notGlobal);
  }else if (paramToSend=='switch'){
    notGlobal=false;
    var paramDiv='paramScreen';
    if(objectIdScreen!=null){
      loadingContentDiv=true;
    }
    switchModeLoad(currentScreen,currentObject,paramDiv,paramToSend,objectIdScreen,notGlobal);
    switchModeOn(objectIdScreen);
  }
  dijit.byId('iconMenuUserScreen').closeDropDown();
}

function switchModeLoad(currentScreen,currentObject,paramDiv,paramToSend,objectIdScreen,notGlobal){
  // var urlParams="?objectClass="+
  // currentObject+"&"+paramDiv+"="+paramToSend+"&objectId="+objectIdScreen;
  var notGlob=(notGlobal)?"&notGlobal=true":"&notGlobal=false";
  var urlParams="?"+paramDiv+"="+paramToSend;
  if (currentObject) urlParams+="&objectClass="+ currentObject;
  if (objectIdScreen) urlParams+="&objectId="+objectIdScreen;
  var urlPage="objectMain.php";
  if(currentScreen=='Planning'){
    urlPage="planningMain.php";
  }else if(currentScreen=='PlanningWorkPlan'){
    urlPage="planningWorkPlanMain.php";
  }else if(currentScreen=='GlobalPlanning'){
    urlPage="globalPlanningMain.php";
  }else if(currentScreen=='PortfolioPlanning' ){
    urlPage="portfolioPlanningMain.php";
  }else if(currentScreen=='ResourcePlanning') {
    urlPage="resourcePlanningMain.php";
  }else if(currentScreen=='VersionsPlanning') {
    var productVersionsListId=dojo.byId('productVersionsListId').value;
    urlPage="versionsPlanningMain.php";
    urlParams+="&productVersionsListId="+productVersionsListId;
  }else if(currentScreen=='ContractGantt') {
    urlPage="contractGanttMain.php";
  }else if(currentScreen=='HierarchicalBudget') {
    urlPage="hierarchicalBudgetMain.php";
  }else if(currentScreen=='ResourceSkill') {
    urlPage="resourceSkillMain.php?notResourceSkillSimple="+true;
  }	else if(currentScreen=='ResourceSkillSimple') {
	urlPage="resourceSkillMain.php?notResourceSkillSimple="+false;
  }else if(currentScreen=='HierarchicalSkill'){
    urlPage="hierarchicalSkillMain.php";
  }
  var param="";
  if(urlPage!="objectMain.php"){
    currentObject=currentScreen;
    if(currentScreen=='PlanningWorkPlan'){
      param ="?planningType=planning";
    }else{
      param ="?planningType="+currentScreen;
    }
  }
  var callBack=null;
  if(objectIdScreen !=''){
    callBack=function(){loadContent("objectDetail.php"+param, "detailDiv", 'listForm');};
  }
  if (currentScreen=='PlanningWorkPlan' || (dojo.byId('objectClass') && (dojo.byId('objectClass').value || urlPage!="objectMain.php"))) {loadContent(urlPage+urlParams+notGlob, "centerDiv",null,null,null,null,null,callBack);}
  if(currentScreen!='PlanningWorkPlan' && !notGlobal)loadDiv("menuUserScreenOrganization.php?currentScreen="+currentScreen+"&"+paramDiv+"="+paramToSend,"mainDivMenu");
}

var listDivWidth=0;
function setActionCoverListNonObj (action,changePose){
  if(coverListAction==action)return;
  coverListAction=action;
  if(dijit.byId('id') && changePose){
    coverListAction='OPEN';
  }
  saveDataToSession('coversListPlan', coverListAction, true);
}

var detailDivScreenWidth=400;
var detailDivScreenHeight=400;
function hideDetailScreen(){
  if (checkFormChangeInProgress()) {
    return;
  }
  var oldCoverListAction = coverListAction;
  if(dojo.byId('workPlanJsonData') && dojo.byId('planningJsonData')){
    if (dojo.byId('detailDiv')){
      dojo.byId("detailDiv").innerHTML='<div align="center" class="labelMessageEmptyAreaCentered">'+ i18n('noItemSelected') + '</div>';
    }
    var lockSaveRefreshButton=dojo.byId("lockSaveRefreshButtonTd");
    if (lockSaveRefreshButton) {
      dojo.style(lockSaveRefreshButton, "display", "");
    }
    if(coverListAction!='CLOSE')setActionCoverListNonObj('CLOSE',false);
    /* planningClickActionOf() et non planningClickAction : l'explorateur documentaire
       a son propre parametre "detail au simple clic". Avec le nom global, la garde
       ne tenait que pour le planning, et refermer le detail refermait ici l'edition
       en ligne que l'on venait d'ouvrir. */
    if(currentRowToEdit && oldCoverListAction == 'OPEN' && planningClickActionOf() != 1){
      var refId = dojo.byId('objectIdRow').value;
      var refType = dojo.byId('objectClassName').value;
      var idProject = dojo.byId('idProjectRow').value;
      JSGantt.closeAndSelectEditRow(currentRowToEdit, refId, refType, idProject);
    }
    return;
  }
  //unselectPlanningLines();
  if(coverListAction!='CLOSE')setActionCoverListNonObj('CLOSE',false);
  duration=300;
  detailRightDivName=(dijit.byId("detailRightDiv"))?'detailRightDiv':'detailRightDivAlt';
  if (dojo.attr(dojo.byId("listDiv"),"region")=='top'){
    fullSize=dojo.byId("listDiv").offsetHeight + dojo.byId("contentDetailDiv").offsetHeight+5 ;
    detailDivScreenHeight=dojo.byId("contentDetailDiv").offsetHeight;   
    if ( !isHtml5()) {
      dijit.byId("listDiv").resize({
        h : fullSize
      });
      dijit.byId("contentDetailDiv").resize({
        h : 0
      });
      dijit.byId("detailRightDiv").resize({
        h : 0
      });
      duration=0;
    } else {
      dojox.fx.combine([
        dojox.fx.animateProperty({
          node : "listDiv",
          properties : {
            height : fullSize
          },
          duration : duration
        }),
        dojox.fx.animateProperty({
          node : "contentDetailDiv",
          properties : {
            height : 0
          },
          duration : duration
        }),
        dojox.fx.animateProperty({
          node : detailRightDivName,
          properties : {
            height : 0
          },
          duration : duration
        })
        
      ]).play();
    }
  }else{
    detailDivScreenWidth=dojo.byId("contentDetailDiv").offsetWidth;
    fullSize=dojo.byId("centerDiv").offsetWidth+5 ;
    if (!isHtml5()) {
      dijit.byId("listDiv").resize({
        w : fullSize
      });
      dijit.byId("contentDetailDiv").resize({
        w : 0
      });
      duration=0;
    } else {
      dojox.fx.combine([
        dojox.fx.animateProperty({
          node : "listDiv",
          properties : {
            width : fullSize
          },
          duration : duration
        }),
        dojox.fx.animateProperty({
          node : "contentDetailDiv",
          properties : {
            width : 0
          },
          duration : duration
        })
        ]).play();
    }
  }
  var lockSaveRefreshButton=dojo.byId("lockSaveRefreshButtonTd");
  if (lockSaveRefreshButton) {
    dojo.style(lockSaveRefreshButton, "display", "");
  }
  resizeContainer("mainDivContainer", duration);
  /* Voir plus haut : le parametre de l'ecran courant, pas celui du planning. C'est
     ce point d'appel qui fermait l'edition en ligne de l'explorateur au moment meme
     ou jsgantt.js l. 5240 replie le detail pour l'afficher. */
  if(currentRowToEdit && oldCoverListAction == 'OPEN' && planningClickActionOf() != 1){
    var refId = (dojo.byId('objectIdRow'))?dojo.byId('objectIdRow').value:dojo.byId('objectId').value;
    var refType = dojo.byId('objectClassName').value;
    var idProject = dojo.byId('idProjectRow').value;
    JSGantt.closeAndSelectEditRow(currentRowToEdit, refId, refType, idProject);
  }
}

var ShowDetailScreenRun=false;
var showActivityStreamVar=false;
function ShowDetailScreen(url){
  ShowDetailScreenRun=true;
  var lockSaveRefreshButton=dojo.byId("lockSaveRefreshButtonTd");
  if (lockSaveRefreshButton) {
    dojo.style(lockSaveRefreshButton, "display", "none");
  }
  var displayAnotherDetail=false;
  var currentItem=historyTable[historyPosition];
  if (!currentItem || undoItemButtonRun || redoItemButtonRun || (currentItem && dojo.byId('objectId') && dojo.byId('objectClass')  && ((dojo.byId('objectClass').value == currentItem[0] && dojo.byId('objectId').value != currentItem[1]) || dojo.byId('objectClass').value != currentItem[0] ))) {
    displayAnotherDetail=true;
    dojo.byId('detailDiv').style.display="none";
  }
  if(undoItemButtonRun)undoItemButtonRun=false;
  if(redoItemButtonRun)redoItemButtonRun=false;

  setActionCoverListNonObj('OPEN',false);
  paramMode=(dojo.byId("listDiv"))?dojo.attr(dojo.byId("listDiv"),"region"):'';
  paramDiv=(dojo.byId("listDiv"))?dojo.attr(dojo.byId("listDiv"),"region"):'';
  paramRightDiv=(dojo.byId("detailRightDiv"))?dojo.attr(dojo.byId("detailRightDiv"),"region"):'';
  
  var callBack=null;
  // PBER : force reload of detail on every opening in Gantt mode
  //if(displayAnotherDetail){
  if (1) {  
    callBack = function(){
      callBFunc=function(){
        dojo.byId("detailDiv").style.display="block";
        resizeContainer("detailDiv", null);
      };
      if(!url)url="objectDetail.php?planning=true&planningType="+currentItem[0];
      loadContent(url,"detailDiv","listForm",null,null,null,null,callBFunc);
    };
  }
  
  checkValidatedSize(paramDiv,paramRightDiv, paramMode,'true',callBack);
  if(dojo.byId('detailRightDiv') && dojo.byId('detailRightDiv').offsetHeight>10){
    showActivityStreamVar=true;
  }

}

var switchModeSkipAnimation=true;
function showList(mode, skipAnimation) {
  duration=300;
  if (switchModeSkipAnimation) {
    skipAnimation=true;
    duration=0;
  }
  if (mode == 'mouse' && switchListMode == 'CLICK')
    return;
  if (!switchedMode) {
    return;
  }
  if (!dijit.byId("listDiv") || !dijit.byId("mainDivContainer")) {
    return;
  }
  if (dojo.byId('listDiv_splitter')) {
    setTimeout("dojo.byId('listDiv_splitter').style.display='none';",duration+50);
  }
  if (dojo.byId('listBarShow')) {
    setTimeout("dojo.byId('listBarShow').style.display='none';",duration+50);
  }
  correction=0;
  if (dojo.byId("listDiv").offsetHeight > 100)
    correction=5;
  fullSize=dojo.byId("listDiv").offsetHeight
      + dojo.byId("contentDetailDiv").offsetHeight -20+correction;
  if (!mode && ! dijit.byId('objectGrid')) fullSize-=8;
  if (skipAnimation || !isHtml5()) {
    dijit.byId("listDiv").resize({
      h : fullSize
    });
    duration=0;
  } else {
    dojox.fx.animateProperty({
      node : "listDiv",
      properties : {
        height : fullSize
      },
      duration : duration
    }).play();
  }
  if (dojo.byId('detailBarShow')) {
    setTimeout("dojo.byId('detailBarShow').style.display='block';",
        duration + 50);
  }
  resizeContainer("mainDivContainer", duration);
  switchedVisible='list';
}

function hideList(mode, skipAnimation) {
  duration=300; 
  if (mode == 'mouse' && switchListMode == 'CLICK'){
    return;
  }
  if (!switchedMode) {
    return;
  }
  if (!dijit.byId("listDiv") || !dijit.byId("mainDivContainer")) {
    return;
  }
  if (skipAnimation && dijit.byId("detailDiv")) {
    dijit.byId("detailDiv").set('content', '');
  }
  if (switchModeSkipAnimation) {
    skipAnimation=true;
    duration=0;
  }
  if (dojo.byId('listDiv_splitter')) {
    dojo.byId('listDiv_splitter').style.display='none';
  }
  if (dojo.byId('listBarShow')) {
    setTimeout("dojo.byId('listBarShow').style.display='block';",duration+50);
  }
  if (dojo.byId('detailBarShow')) {
    setTimeout("dojo.byId('detailBarShow').style.display='none';",duration+50);
  }
  if (!isHtml5() || skipAnimation) {
    dijit.byId("listDiv").resize({
      h : 20
    });
    duration=0;
  } else {
    dojox.fx.combine([ dojox.fx.animateProperty({
      node : "listDiv",
      properties : {
        height : 20
      },
      duration : duration
    }) ]).play();
  }
  resizeContainer("mainDivContainer", duration);
  switchedVisible='detail';
}

function resizeContainer(container, duration) {
  sequ=10;
  if (!dijit.byId(container)) return;
  if (duration) {
    for (var i=0; i < sequ; i++) {
      setTimeout('dijit.byId("' + container + '").resize();', i * duration / sequ);
    }
  }
  setTimeout('dijit.byId("' + container + '").resize();', duration + 10);
}

function listClick() {
  // stockHistory(dojo.byId('objectClass').value, dojo.byId('objectId').value);
  if (!switchedMode ) {
    return;
  }
  setTimeout("hideList(null,true);", 1);
}

function consoleLogHistory(msg) {
  consoleTraceLog('====='+msg+'==== ('+historyTable.length+')');
  if (historyTable.length==0) {
    consoleTraceLog(msg+' => Empty');
  }
  for (var i=0;i<historyTable.length;i++) {
    current=historyTable[i];
    consoleTraceLog(msg+' => '+current[0]+ ' | '+current[1]+' | '+current[2]);
  }
}

function stockHistory(curClass, curId, currentScreen) {
  if (!currentScreen) {
    currentScreen="object";
    if (dojo.byId("objectClassManual")){
      currentScreen=dojo.byId("objectClassManual").value;
    }
  }
  if (dojo.byId('objectClassList') && dojo.byId('objectClassList').value=='GlobalView' && curId) {
    curId=curClass+'|'+parseInt(curId);
    curClass=dojo.byId('objectClassList').value;
  }
  if (historyPosition>=0) {
    current=historyTable[historyPosition];
    if (current[0]==curClass && current[1]==curId && current[2]==currentScreen) return; // do not re-stock current item
    if (current[0]==curClass && current[1]==null && current[2]==currentScreen) historyPosition-=1; // previous is same class but with no selection, will overwrite
    if (current[0]==curClass && current[1]==curId && current[2]=='Planning' && currentScreen=='object') historyPosition-=1; // previous is same class but with no selection, will overwrite
  }
  historyPosition+=1;
  historyTable[historyPosition]=new Array(curClass, curId,currentScreen);
  // Purge next history (not valid any more)
  for (var i=historyPosition+1;i<historyTable.length;i++) {
    historyTable.splice(i,1); 
  }
  if (historyPosition > 0) {
    enableWidget('menuBarUndoButton');
  }
  if (historyPosition == historyTable.length - 1) {
    disableWidget('menuBarRedoButton');
  }
}

var undoItemButtonRun=false;
var redoItemButtonRun=false;
function undoRedoItemButton(action) {
  if (checkFormChangeInProgress()) {
    return ;
  }
  if (dijit.byId('dialogNote') && dijit.byId('dialogNote').open) {
    return;
  }
  var len=historyTable.length;
  if (len == 0) {
    return;
  }
  if(action=='redo'){
    redoItemButtonRun=true;
    if (historyPosition == len - 1) {
      return;
    }
    historyPosition+=1;
  }
  if(action=='undo'){
    undoItemButtonRun=true;
    if (historyPosition == 0) {
      return;
    }
    historyPosition-=1;
  }
  var currentItem=historyTable[historyPosition];
  var currentScreen=currentItem[2];
  var target="";
  var screenPlanning = currentScreen.toLowerCase();
  if (currentScreen=="object" && currentItem[1]!=null){
	//#11052 noHistory true
    gotoElement(currentItem[0], currentItem[1], false, false, currentScreen, false, true);
  }else if (currentScreen=="object") {
    loadContent("objectMain.php?objectClass=" + currentItem[0],"centerDiv");
    // gautier #3413
  } else if (screenPlanning.indexOf('planning') != -1 && currentItem[1]!=null){
	//#11052 noHistory true	
    gotoElement(currentItem[0], currentItem[1], true, false, screenPlanning, false);
  }else if(currentScreen=='ConsultationValidation'){
    loadMenuBarItem('ConsultationValidation','menuConsultationValidation','bar');
  }else if(currentScreen=='ViewAllSubTask'){
    loadMenuBarItem('ViewAllSubTask','menuViewAllSubTask','bar');
  }else if(currentScreen=='GanttSupplierContract' || currentScreen=='GanttClientContract' || currentScreen=='ContractGantt' || currentScreen=="HierarchicalBudget" || currentScreen=="HierarchicalSkill" ){
    if(currentScreen=="HierarchicalBudget")page="hierarchicalBudgetMain.php";
    else if (currentScreen=='GanttSupplierContract' || currentScreen=='GanttClientContract' || currentScreen=='ContractGantt')page="contractGanttMain.php";
    else page="hierarchicalSkillMain.php";
    var classEl=currentItem[0];
    if(currentItem[0]==currentScreen){
      loadMenuBarItem(currentScreen,'menu'+currentScreen,'bar');
    }else{
      var param="?objectClass="+currentItem[0];
      var callB=null;
      if(currentItem[1]!=null){
        param+="&objectId="+currentItem[1];
        callB=function(){
          loadContent('objectDetail.php', 'detailDiv', 'listForm');
        };
      }
        objectExist='true';
        vGanttCurrentLine=-1;
        cleanContent("centerDiv");
        loadContent(page+param, "centerDiv",null,null,null,null,null,callB);

    }
  } else if (currentScreen == 'ProjectDashboardDetail') {
	  loadContent("projectDashboardDetailMain.php?idProject=" + currentItem[1], "centerDiv");
  } else if (currentScreen == 'ProjectDashboard') {
	  var params = "&objectClass=ProjectDashboard";
	  loadMenuBarItem('ProjectDashboard', 'ProjectDashboard', params);
  } else if (currentScreen=="LiveMeeting" && currentItem[1]!=null){
    loadContent("../view/liveMeetingView.php?idMeeting="+currentItem[1]+"&saveDescription=false", "centerDiv");
  } else if (currentScreen=="Reports" && currentItem[1]!=null) {
    var executeNow=function() {
      dojo.byId('outMode').value='';
      if (currentItem.length>3) {
        params=currentItem[3];
        listParams=params.split('|');
        for (var i=0;i<listParams.length;i++) {
          par=listParams[i].split('=');
          field=par[0];
          value=par[1];
          if (dijit.byId(field)) {
            if (dijit.byId(field).declaredClass=='dijit.form.DateTextBox') dijit.byId(field).set('displayedValue',value);
            else if (dijit.byId(field).declaredClass=='dijit.form.NumberSpinner') dijit.byId(field).set('displayedValue',value);
            else if (dijit.byId(field).declaredClass=='dojox.form.CheckedMultiSelect') dijit.byId(field).set('value',value.split(','));
            else dijit.byId(field).set('value',value);
          }
        }
      }
      runReport();
    };
    loadContent("../view/reportsMain.php?" + currentItem[1],"centerDiv", null, false,null, null,null,executeNow);
  } else if (currentScreen == 'ResourceSkill'){
	loadContent("resourceSkillMain.php?notResourceSkillSimple="+true,"centerDiv");
  } else if (currentScreen == 'ResourceSkillSimple'){
	loadContent("resourceSkillMain.php?notResourceSkillSimple="+false,"centerDiv");
  } else {
    target=getTargetFromCurrentScreen(currentScreen);
    if(target=='dashboardEmployeeManagerMain.php'){
      target='dashboardEmployeeManager.php';
    }
	var checkPlanningTarget = target.toLowerCase();
	if(checkPlanningTarget.indexOf('planning') != -1){
		loadMenuBarItem(currentScreen,'menu'+currentScreen,'bar');
	}else{
		loadContent(target,"centerDiv"); 
	}
  }
  if(action=='undo'){
    enableWidget('menuBarRedoButton');
    if (historyPosition == 0) {
      disableWidget('menuBarUndoButton');
    }
  }
  if(action=='redo'){
    enableWidget('menuBarUndoButton');
    if (historyPosition == (len - 1)) {
      disableWidget('menuBarRedoButton');
    }
  }
  selectIconMenuBar(currentItem[0]);
  if(isNewGui){
    refreshSelectedMenuLeft('menu'+currentItem[0]);
    refreshSelectedItem(currentItem[0], defaultMenu);
  }
  if(action=='redo')getTargetFromCurrentScreen(currentScreen);
 // setActionCoverListNonObj('CLOSE',false); 
}

function getTargetFromCurrentScreen(currentScreen){
  if (currentScreen=="Administration" || currentScreen=="Admin"){ 
    target="admin.php";
  } else if (currentScreen=="Import" || currentScreen=="ImportData"){ 
    target="importData.php";
  } else if (currentScreen=="DashboardTicket") {
    target="dashboardTicketMain.php";
  } else if (currentScreen=="DashboardRequirement") { // ADD qCazelles -
                                                      // Requirements dashboard
                                                      // - Ticket 90
  target="dashboardRequirementMain.php";
  } else if (currentScreen=="ActivityStream") {
    target="activityStreamMain.php";
  } else if (currentScreen=="Plugin"){ 
    target="pluginManagement.php";
  }else if (currentScreen=="Today"){ 
    target="today.php";
  } else if (currentScreen=="Kanban"){ 
    target="kanbanViewMain.php";
  } else if (currentScreen=="UserParameter") {
    target="parameter.php?type=userParameter";
  } else if (currentScreen=="ProjectParameter") {
    target="parameter.php?type=projectParameter";
  } else if (currentScreen=="GlobalParameter") {
    target="parameter.php?type=globalParameter";
  } else if (currentScreen=="Habilitation") {
    target="parameter.php?type=habilitation";
  } else if (currentScreen=="HabilitationReport") {
    target="parameter.php?type=habilitationReport";
  } else if (currentScreen=="HabilitationOther") {
    target="parameter.php?type=habilitationOther";
  } else if (currentScreen=="AccessRight") {
    target="parameter.php?type=accessRight";
  } else if (currentScreen=="AccessRightNoProject") {
    target="parameter.php?type=accessRightNoProject";
  } else if (pluginMenuPage['menu'+currentScreen]) {
    target=pluginMenuPage['menu'+currentScreen];
  } else {
    target=currentScreen.charAt(0).toLowerCase()+currentScreen.substr(1)+"Main.php";
  }
  return target;
}

function getTargetFromCurrentScreenChangeLang(currentScreen){
  if (currentScreen=="Administration" || currentScreen=="Admin"){ 
    target="admin.php";
  } else if (currentScreen=="Import" || currentScreen=="ImportData"){ 
    target="importData.php";
  } else if (currentScreen=="DashboardTicket") {
    target="dashboardTicketMain.php";
  } else if (currentScreen=="DashboardRequirement") { // ADD qCazelles -
                                                      // Requirements dashboard
                                                      // - Ticket 90
    target="dashboardRequirementMain.php";
  } else if (currentScreen=="ActivityStream") {
    target="activityStreamMain.php";
  } else if (currentScreen=="PlannedWorkManual") {
    target="plannedWorkManualMain.php";
  } else if (currentScreen=="Today"){ 
    target="today.php";
  } else {
    target="parameter.php";
  }
  return target;
}

var quickSearchStockId=null;
var quickSearchStockName=null;
var quickSearchIsOpen=false;

function quickSearchOpen() {
  dojo.style("quickSearchDiv", "display", "block");
  if (dijit.byId("listTypeFilter")) {
    dojo.style("listTypeFilter", "display", "none");
  }
  if (dijit.byId("listClientFilter")) {
    dojo.style("listClientFilter", "display", "none");
  }
  if (dijit.byId("listElementableFilter")) {
    dojo.style("listElementableFilter", "display", "none");
  }
  quickSearchStockId=dijit.byId('listIdFilter').get("value");
  if (dijit.byId('listNameFilter')) {
    quickSearchStockName=dijit.byId('listNameFilter').get("value");
    dojo.style("listNameFilter", "display", "none");
    dijit.byId('listNameFilter').reset();
  }
  dijit.byId('listIdFilter').reset();
  dojo.style("listIdFilter", "display", "none");
  dijit.byId("quickSearchValue").reset();
  dijit.byId("quickSearchValue").focus();
  quickSearchIsOpen=true;
}

function quickSearchClose() {
  quickSearchIsOpen=false;
  dojo.style("quickSearchDiv", "display", "none");
  if (dijit.byId("listTypeFilter")) {
    dojo.style("listTypeFilter", "display", "block");
  }
  if (dijit.byId("listClientFilter")) {
    dojo.style("listClientFilter", "display", "block");
  }
  if (dijit.byId("listElementableFilter")) {
    dojo.style("listElementableFilter", "display", "block");
  }
  dojo.style("listIdFilter", "display", "block");
  if (dijit.byId('listNameFilter')) {
    dojo.style("listNameFilter", "display", "block");
    dijit.byId('listNameFilter').set("value", quickSearchStockName);
  }
  dijit.byId("quickSearchValue").reset();
  dijit.byId('listIdFilter').set("value", quickSearchStockId);
  var objClass=(dojo.byId('objectClassList'))?dojo.byId('objectClassList').value:dojo.byId('objectClass').value;
  refreshJsonList(objClass);
}

function synchronizeQuickSearchQuickFilter(value) {
  var quickSearchSwitch=dijit.byId('quickSearchValueQuickSw');
  var listQuickSearch=dijit.byId('listQuickSearchFilter');
  if (!quickSearchSwitch || !listQuickSearch) return;
  if (value==='' && quickSearchSwitch.get('value')==='off') {
    dojo.byId('listQuickSearchFilterSpan').style.display='none';
    listQuickSearch.domNode.style.display='none';
    dojo.byId('listQuickSearchFilterBtnSearch').style.display='none';
    dojo.byId('listQuickSearchFilterBtnClose').style.display='none';
  } else {
    if (dojo.byId('filterDivs').style.display==='none') {
      dojo.byId('filterDivs').style.display='block';
    }
    dojo.byId('listQuickSearchFilterSpan').style.display='block';
    listQuickSearch.domNode.style.display='block';
    dojo.byId('listQuickSearchFilterBtnSearch').style.display='block';
    dojo.byId('listQuickSearchFilterBtnClose').style.display='block';
  }
  listQuickSearch.set('value',value);
  resizeListDiv();
}

function quickSearchCloseQuick(type) {
  dijit.byId("listQuickSearchFilter").reset();
  dojo.byId("listQuickSearchValueFilter").value = '';
  dijit.byId("quickSearchValueQuick").reset();
  dojo.byId("quickSearchValueQuickValue").value = '';
  var objClass=(dojo.byId('objectClassList'))?dojo.byId('objectClassList').value:dojo.byId('objectClass').value;
  refreshJsonList(objClass);
  if(type=='quick')dijit.byId('listFilterFilter').closeDropDown();
}
function getQuickSearchI18nKey() {
  var classNode=dojo.byId('objectClassList');
  if (!classNode || !classNode.value) classNode=dojo.byId('objectClass');
  return (classNode && classNode.value==='GlobalView')?'globalQuickSearch':'quickSearch';
}

function quickSearchExecute() {
  if (!quickSearchIsOpen) {
    return;
  }
  if (!dijit.byId("quickSearchValue").get("value")) {
    showInfo(i18n('messageMandatory', new Array(i18n(getQuickSearchI18nKey()))));
    return;
  }
  var objClass=(dojo.byId('objectClassList'))?dojo.byId('objectClassList').value:dojo.byId('objectClass').value;
  refreshJsonList(objClass);
}

function quickSearchExecuteQuick(type) {
  if ((type == 'quick' && !dijit.byId("quickSearchValueQuick").get("value")) || (type == 'list' && !dijit.byId("listQuickSearchFilter").get("value"))) {
    showInfo(i18n('messageMandatory', new Array(i18n(getQuickSearchI18nKey()))));
    return;
  }
  if(type == 'list'){
    dojo.byId('listQuickSearchValueFilter').value = dijit.byId("listQuickSearchFilter").get('value');
  }else{
    dojo.byId('quickSearchValueQuickValue').value = dijit.byId("quickSearchValueQuick").get('value');
  }
  var objClass=(dojo.byId('objectClassList'))?dojo.byId('objectClassList').value:dojo.byId('objectClass').value;
  refreshJsonList(objClass);
  dijit.byId('listFilterFilter').closeDropDown();
}

/*
 * ========================================== Copy functions
 * ==========================================
 */

function copyObject(objectClass, objectId, fromContextMenu) {  
  if (dojo.byId("copyButton")) dojo.byId("copyButton").blur();
  action = function() {
    unselectAllRows('objectGrid');
	var callback = function(){
		if(fromContextMenu && dojo.byId('objectClassManual') && (dojo.byId('objectClassManual').value == 'SprintBacklog' || dojo.byId('objectClassManual').value == 'ProductBacklog')){
			refreshBacklog();
		}
    };
    if (objectId || dojo.byId('objectIdRow').value) {
      if (dojo.byId('objectIdRow')) objectId = dojo.byId('objectIdRow').value;
      if (dojo.byId('objectClassRow')) objectClass = dojo.byId('objectClassRow').value;
      loadContent("../tool/copyObject.php?objectId=" + objectId +  "&objectClass=" + objectClass + "&objectClassName=" + objectClass, "resultDivMain", 'objectForm', true,
	  null, null, false, callback);
    } else {
      loadContent("../tool/copyObject.php", "resultDivMain", 'objectForm', true, null, null, false, callback);
    }
  };
  if (objectId || dojo.byId('objectIdRow').value) {
    objectIdRow = dojo.byId('objectIdRow') ? dojo.byId('objectIdRow').value : objectId;
    showConfirm(i18n("confirmCopy", new Array(i18n(objectClass), objectIdRow)), action);
  } else {
    showConfirm(i18n("confirmCopy", new Array(i18n(objectClass), dojo.byId('id').value)), action);
  }
}

function copyLinkTo(objectClass) {
  dojo.byId("copyButton").blur();
  action=function() {
    unselectAllRows('objectGrid');
    loadContent("../tool/copyObject.php", "linkRef2Id", 'objectForm', true);
  };
  showConfirm(i18n("confirmCopy", new Array(i18n(objectClass),
      dojo.byId('id').value)), action);
}

function copyObjectToShowStructure() {
  if (dojo.byId('copyClass').value == 'Activity'
      && copyableArray[dijit.byId('copyToClass').get('value')] == 'Activity') {
    dojo.byId('copyWithStructureDiv').style.display='block';
  } else {
	if(dojo.byId('copyClass').value == 'Sprint'){
		dojo.byId('copyWithStructureDiv').style.display='block';
		dojo.query('.copyWithStructureClass', dojo.byId('copyWithStructureDiv')).forEach(function(node){
				node.style.display='none';
			});
	}else{
		if (dojo.byId('copyWithStructureDiv')) dojo.byId('copyWithStructureDiv').style.display='none';
	}
  }
}

function copyObjectToSubmit(objectClass) {
  var formVar=dijit.byId('copyForm');
  if (typeof CKEDITOR !== 'undefined' && CKEDITOR.instances['copyToDescription']) {
    CKEDITOR.instances['copyToDescription'].updateElement();
  }
  if (!formVar.validate()) {
    showAlert(i18n("alertInvalidForm"));
    return;
  }
  unselectAllRows('objectGrid');

  if(dojo.byId('copyFromContextMenu') && dojo.byId('copyFromContextMenu').value){
	var copyFromContextMenu = dojo.byId('copyFromContextMenu').value;
    var callback = function(){
		if(dojo.byId('objectClassManuel') && (dojo.byId('objectClassManuel').value == 'SprintBacklog' || dojo.byId('objectClassManuel').value == 'ProductBacklog')){
			refreshBacklog();
		}
    };
    loadContent("../tool/copyObjectTo.php?fromContextMenu="+copyFromContextMenu+"&objectId=" + dojo.byId('objectId').value
      + "&objectClass="+dojo.byId('copyClass').value, "resultDivMain", 'copyForm', true,
        'copyTo', null, false, callback);
  }else{
    loadContent("../tool/copyObjectTo.php?objectClass="+dojo.byId('objectClass').value, "resultDivMain", 'copyForm', true, 'copyTo');
  }
  dijit.byId('dialogCopy').hide();
  if (typeof formChangeInProgress !== 'undefined') {
    formChangeInProgress = false;
  }
}

function copyDocumentToSubmit(objectClass) {
  loadContent("../tool/copyDocumentTo.php", "resultDivMain", 'copyDocumentForm', true );
  dijit.byId('dialogCopyDocument').hide();
}

function copyProjectToSubmit(objectClass) {
  var formVar=dijit.byId('copyProjectForm');
  if (!formVar.validate()) {
    showAlert(i18n("alertInvalidForm"));
    return;
  }
  if (typeof CKEDITOR !== 'undefined' && CKEDITOR.instances['copyToDescription']) {
    CKEDITOR.instances['copyToDescription'].updateElement();
  }
  unselectAllRows('objectGrid');
  if(fromContextMenu){
    var callback = function(){
      fromContextMenu=false;
    };
    loadContent("../tool/copyProjectTo.php?fromContextMenu="+fromContextMenu+"&objectId=" + dojo.byId('objectId').value
      + "&objectClass="+dojo.byId('objectClass').value, "resultDivMain", 'copyProjectForm',
        true, 'copyProject', null, false, callback);
  }else{
    loadContent("../tool/copyProjectTo.php", "resultDivMain", 'copyProjectForm', true, 'copyProject');
  }
  dijit.byId('dialogCopy').hide();
  if (typeof formChangeInProgress !== 'undefined') {
    formChangeInProgress = false;
  }
}

function copyProjectStructureChange() {
  var cpStr=dijit.byId('copyProjectStructure');
  if (cpStr) {
    if (!cpStr.get('checked')) {
      dijit.byId('copyProjectAssignments').set('checked', false);
      dijit.byId('copyProjectAssignments').set('readOnly', 'readOnly');
    } else {
      dijit.byId('copyProjectAssignments').set('readOnly', false);
    }
  }
}

//#10367 remi
function copyPasteObjectToSubmit(){
	fromContextMenu=true;
	var callback = function(){
//	  fromContextMenu=false;
	};
  var formVar=dijit.byId('copyPasteForm');
  if (!formVar.validate()) {
    showAlert(i18n("alertInvalidForm"));
    return;
  }
  unselectAllRows('objectGrid');
  loadContent("../tool/copyObjectTo.php?fromContextMenu=true", "resultDivMain", 'copyPasteForm', true, 'copyTo',null,null,callback);
  dijit.byId('dialogCopyPaste').hide();
}

/*
 * ========================================================================
 * Planning columns management
 * ========================================================================
 */
function openPlanningColumnMgt() {
  // alert("openPlanningColumnMgt");
}

function changePlanningColumn(col, status, order, planningType) {
  if(!planningType)planningType = (dojo.byId('planningType'))?dojo.byId('planningType').value:'planning';
  if (status) {
    //order=planningColumnOrder[getIndiceForPlanningType(planningType)].indexOf('Hidden'+col);
    order=dojo.indexOf(planningColumnOrder[getIndiceForPlanningType(planningType)], 'Hidden' + col);
    planningColumnOrder[getIndiceForPlanningType(planningType)][order]=col;
    movePlanningColumn(col, col, planningType);
  } else {
    order=planningColumnOrder[getIndiceForPlanningType(planningType)].indexOf(col);
    //order=dojo.indexOf(planningColumnOrder[getIndiceForPlanningType(planningType)], col);
    planningColumnOrder[getIndiceForPlanningType(planningType)][order]='Hidden' + col;
  } 
  // moveListColumn(); // Removed as sets error
  if (col=='IdStatus' || col=='Type') {
    validatePlanningColumnNeedRefresh=true;
  }
  setPlanningFieldShow(col,status, planningType);
  
  var objectClass=dojo.byId('objectClass').value;
  if (dojo.byId('objectClassList') && dojo.byId('objectClassList').value) {
    objectClass=dojo.byId('objectClassList').value;
  } else if (!window.top.dijit.byId('dialogDetail').open && dojo.byId("objectClassManual") && dojo.byId("objectClassManual").value) {
    objectClass=dojo.byId("objectClassManual").value;
  }
  
  dojo.xhrGet({
    url : '../tool/savePlanningColumn.php?objectClass='+objectClass+'&action=status&status='
        + ((status) ? 'visible' : 'hidden') + '&item=' + col+'&planningType='+planningType+addTokenIndexToUrl(),
    handleAs : "text",
    load : function(data, args) {
    },
    error : function() {
    }
  });
}
function changePlanningColumnWidth(col, width, planningType, needRefresh) {
  if(!planningType)planningType = (dojo.byId('planningType'))?dojo.byId('planningType').value:'planning';
  setPlanningFieldWidth(col,width, planningType);
  showWait();
  JSGantt.changeFormat(g.getFormat(), g);
  
  var objectClass=dojo.byId('objectClass').value;
  if (dojo.byId('objectClassList') && dojo.byId('objectClassList').value) {
    objectClass=dojo.byId('objectClassList').value;
  } else if (!window.top.dijit.byId('dialogDetail').open && dojo.byId("objectClassManual") && dojo.byId("objectClassManual").value) {
    objectClass=dojo.byId("objectClassManual").value;
  }
  
  dojo.xhrGet({
    url : '../tool/savePlanningColumn.php?objectClass='+objectClass+'&action=width&width='+width+'&item=' + col+addTokenIndexToUrl(),
    handleAs : "text",
    load : function(data, args) {
      if(needRefresh){
        loadContent('../tool/refreshPlanningColumnSelector.php?planningType='+planningType+'&layoutObjectClass=' + objectClass + ''+addTokenIndexToUrl(),'divPlanningColumnSelector', null, false, null, null,true);
      }
    },
    error : function() {
    }
  });
  hideWait();
}

function resetPlanningListColumn() {
  var planningType = (dojo.byId('planningType'))?dojo.byId('planningType').value:'planning';
  var actionOK=function() {
    showWait();
    dijit.byId('planningColumnSelector').closeDropDown();
    var objectClass=dojo.byId('objectClass').value;
    if (dojo.byId('objectClassList') && dojo.byId('objectClassList').value) {
      objectClass=dojo.byId('objectClassList').value;
    } else if (!window.top.dijit.byId('dialogDetail').open && dojo.byId("objectClassManual") && dojo.byId("objectClassManual").value) {
      objectClass=dojo.byId("objectClassManual").value;
    }
    dojo.xhrGet({
      url : '../tool/savePlanningColumn.php?action=reset&objectClass='
          + objectClass+'&planningType='+planningType+addTokenIndexToUrl(),
      handleAs : "text",
      load : function(data, args) {
        var planningType = (dojo.byId('planningType'))?dojo.byId('planningType').value:'planning';
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
        loadContent('../tool/refreshPlanningColumnSelector.php?planningType='+planningType+'&layoutObjectClass=' + objectClass + ''+addTokenIndexToUrl(),'divPlanningColumnSelector', null, false, null, null,true, callback);
      },
      error : function() {
      }
    });
  };
  showConfirm(i18n('confirmResetList'), actionOK);
}

var validatePlanningColumnNeedRefresh=false;
function validatePlanningColumn(planningType) {
  if(!planningType)planningType = (dojo.byId('planningType'))?dojo.byId('planningType').value:'planning';
  dijit.byId('planningColumnSelector').closeDropDown();
  showWait();
  setGanttVisibility(g, planningType);
  if (validatePlanningColumnNeedRefresh) { 
    refreshJsonPlanning();
  } else {
    JSGantt.closeEditRowObjectPlanning();
    JSGantt.changeFormat(g.getFormat(), g);
    hideWait();
  }
  validatePlanningColumnNeedRefresh=false;
}

function movePlanningColumn(source, destination, planningType) {
  if(!planningType)planningType = (dojo.byId('planningType'))?dojo.byId('planningType').value:'planning';
  var mode='';
  var list='Name|';
  var nodeList=dndPlanningColumnSelector.getAllNodes();
  planningColumnOrder[getIndiceForPlanningType(planningType)]=new Array();
  for (var i=0; i < nodeList.length; i++) {
    var itemSelected=nodeList[i].id.substr(14);
    check=(dijit.byId('checkColumnSelector' + itemSelected).get('checked')) ? ''
        : 'hidden';
    check=(dojo.byId('columnSelector' + itemSelected).style.display == 'none') ? 'hidden'
        : check;
    list+=check + itemSelected + "|";
    planningColumnOrder[getIndiceForPlanningType(planningType)][i]=check + itemSelected;
  }
  // alert(planningColumnOrder);
  var objectClass=dojo.byId('objectClass').value;
  if (dojo.byId('objectClassList') && dojo.byId('objectClassList').value) {
    objectClass=dojo.byId('objectClassList').value;
  } else if (!window.top.dijit.byId('dialogDetail').open && dojo.byId("objectClassManual") && dojo.byId("objectClassManual").value) {
    objectClass=dojo.byId("objectClassManual").value;
  }
  
  var url='../tool/movePlanningColumn.php?objectClass='+objectClass+'&orderedList=' + list+addTokenIndexToUrl();
  dojo.xhrPost({
    url : url,
    handleAs : "text",
    load : function(data, args) {
    }
  });
  // loadContent(url, "resultDivMain");
}

function movePlanningHeaderColumn(source, destination, planningType) {
  if(!planningType)planningType = (dojo.byId('planningType'))?dojo.byId('planningType').value:'planning';
  var list='Name|';
  var dndPlanningHeaderColumnList=dndPlanningHeaderColumn.getAllNodes();
  planningColumnOrder[getIndiceForPlanningType(planningType)]=new Array();
  planningColumnOrder[getIndiceForPlanningType(planningType)].push('Name');
  for (var i=0; i < dndPlanningHeaderColumnList.length; i++) {
    var itemSelected=dndPlanningHeaderColumnList[i].id.substr(15);
    list+=itemSelected + "|";
    planningColumnOrder[getIndiceForPlanningType(planningType)].push(itemSelected);
  }
  var dndPlanningColumnSelectorList=dndPlanningColumnSelector.getAllNodes();
  for (var i=0; i < dndPlanningColumnSelectorList.length; i++) {
    var itemSelected=dndPlanningColumnSelectorList[i].id.substr(14);
    var check=(dijit.byId('checkColumnSelector' + itemSelected).get('checked')) ? '':'hidden';
    check=(dojo.byId('columnSelector' + itemSelected).style.display == 'none') ? 'hidden':check;
    if(check){
      list+=check+itemSelected + "|";
      planningColumnOrder[getIndiceForPlanningType(planningType)].push(check + itemSelected);
    }
  }
  var objectClass=dojo.byId('objectClass').value;
  if (dojo.byId('objectClassList') && dojo.byId('objectClassList').value) {
    objectClass=dojo.byId('objectClassList').value;
  } else if (!window.top.dijit.byId('dialogDetail').open && dojo.byId("objectClassManual") && dojo.byId("objectClassManual").value) {
    objectClass=dojo.byId("objectClassManual").value;
  }
  
  var url='../tool/movePlanningColumn.php?objectClass='+objectClass+'&orderedList=' + list+addTokenIndexToUrl();
  dojo.xhrPost({
    url : url,
    handleAs : "text",
    load : function(data, args) {
      var callback = function(){
        validatePlanningColumnNeedRefresh=true;
        validatePlanningColumn(planningType);
      };
      loadContent('../tool/refreshPlanningColumnSelector.php?planningType='+planningType+'&layoutObjectClass=' + objectClass + ''+addTokenIndexToUrl(),'divPlanningColumnSelector', null, false, null, null,true, callback);
    }
  });
}

function tooglePlanningColumnList(){
  event.preventDefault();
  dijit.byId('planningColumnSelector').toggleDropDown();
}

/*
 * ======================================================================== List
 * columns management
 * ========================================================================
 */

function changeListColumn(tableId, fieldId, status, order) {
  var spinner=dijit.byId('checkListColumnSelectorWidthId' + fieldId);
  spinner.set('disabled', !status);
  var orderedList=getListColumnSelectorOrder();
  dojo.xhrPost({
    url : '../tool/saveSelectedColumn.php?action=status&status='
        + ((status) ? 'visible' : 'hidden') + '&item=' + tableId+addTokenIndexToUrl(),
    content : {
      orderedList : orderedList
    },
    handleAs : "text",
    load : function(data, args) {
    },
    error : function() {
    }
  });
  recalculateColumnSelectorName();
}

function changeListColumnWidth(tableId, fieldId, width) {
  if (width < 1) {
    width=1;
    dijit.byId('checkListColumnSelectorWidthId' + fieldId).set('value', width);
  } else if (width > 50) {
    width=50;
    dijit.byId('checkListColumnSelectorWidthId' + fieldId).set('value', width);
  }
  dojo.xhrGet({
    url : '../tool/saveSelectedColumn.php?action=width&item=' + tableId
        + '&width=' + width+addTokenIndexToUrl(),
    handleAs : "text",
    load : function(data, args) {
    },
    error : function() {
    }
  });
  recalculateColumnSelectorName();
}

function validateListColumn() {
  showWait();
  dijit.byId('listColumnSelector').closeDropDown();
  var callBack=function(){resizeListDiv();};
  loadContent("objectList.php?objectClass=" + dojo.byId('objectClassList').value+ "&objectId="+dojo.byId('objectId').value, 
              "listDiv",null,null,null,null,null,callBack);
}

function resetListColumn() {
  var actionOK=function() {
    showWait();
    dijit.byId('listColumnSelector').closeDropDown();
    dojo.xhrGet({
      url : '../tool/saveSelectedColumn.php?action=reset&objectClass='
          + dojo.byId('objectClassList').value+addTokenIndexToUrl(),
      handleAs : "text",
      load : function(data, args) {
        var callBack=function(){resizeListDiv();};
        loadContent("objectList.php?objectClass="+dojo.byId('objectClassList').value+"&objectId="+dojo.byId('objectId').value,
                    "listDiv",null,null,null,null,null,callBack);
      },
      error : function() {
      }
    });
  };
  showConfirm(i18n('confirmResetList'), actionOK);
}

function moveListColumn(source, destination) {
  saveListColumnOrder(getListColumnSelectorOrder());
}

function getListColumnSelectorOrder() {
  var list='';
  if (typeof dndListColumnSelector == 'undefined' || !dndListColumnSelector || !dndListColumnSelector.node) return list;
  var nodeList=dndListColumnSelector.getAllNodes();
  listColumnOrder=new Array();
  for (var i=0; i < nodeList.length; i++) {
    var itemSelected=nodeList[i].id.substr(20);
    list+=itemSelected + "|";
  }
  return list;
}

function saveListColumnOrder(list) {
  if (!list) return;
  var url='../tool/moveListColumn.php?orderedList=' + list;
  dojo.xhrPost({
    url : url+addTokenIndexToUrl(),
    handleAs : "text",
    load : function(data, args) {
    }
  });
}

function sortListColumnSelector() {
  if (typeof dndListColumnSelector == 'undefined' || !dndListColumnSelector || !dndListColumnSelector.node) return;
  var nodeList=dndListColumnSelector.getAllNodes();
  var selectedNodes=new Array();
  var unselectedNodes=new Array();
  for (var i=0; i < nodeList.length; i++) {
    var fieldId=nodeList[i].getAttribute('data-field-id');
    var checkbox=dijit.byId('checkListColumnSelectorId' + fieldId);
    if (checkbox && checkbox.get('checked')) {
      selectedNodes.push(nodeList[i]);
    } else {
      unselectedNodes.push(nodeList[i]);
    }
  }
  unselectedNodes.sort(function(nodeA, nodeB) {
    var labelA=dojo.query('.checkLabel', nodeA)[0];
    var labelB=dojo.query('.checkLabel', nodeB)[0];
    var nameA=(labelA)?dojo.trim(labelA.textContent || labelA.innerText || ''):'';
    var nameB=(labelB)?dojo.trim(labelB.textContent || labelB.innerText || ''):'';
    return nameA.localeCompare(nameB);
  });
  var sortedNodes=selectedNodes.concat(unselectedNodes);
  for (var i=0; i < sortedNodes.length; i++) {
    dndListColumnSelector.node.appendChild(sortedNodes[i]);
  }
}

function moveFilterListColumn() {
    var mode='';
    var list='';
    var nodeList=dndListFilterSelector.getAllNodes();
    listColumnOrder=new Array();
    for (var i=0; i < nodeList.length; i++) {
      var itemSelected=nodeList[i].id.substr(6);
      list+=itemSelected + "|";
    }  
    
    var callback=function() {
        if (window.top.dijit.byId('dialogDetail').open) {
          var doc=window.top.frames['comboDetailFrame'];
        } else {
          var doc=top;
        }
        if (dojo.byId('objectClassList') && dojo.byId('objectClassList').value){
          var objectClass=dojo.byId('objectClassList').value;
        }else if (! window.top.dijit.byId('dialogDetail').open && dojo.byId("objectClassManual") && dojo.byId("objectClassManual").value){ 
          var objectClass=dojo.byId("objectClassManual").value;
        }else if (dojo.byId('objectClass') && dojo.byId('objectClass').value){
          var objectClass=dojo.byId('objectClass').value;
        } 
        var compUrl=(window.top.dijit.byId("dialogDetail").open) ? '?comboDetail=true' : '';
        if (dojo.byId("objectClassManual") && dojo.byId("objectClassManual").value=='Kanban') {
			compUrl+='&context=directFilterList';
	        compUrl+='&contentLoad=../tool/jsonKanban.php';
	        compUrl+='&container=kanbanJsonData';
        }
		doc.loadContent(
            "../tool/displayFilterList.php?context=directFilterList&filterObjectClass="
                + objectClass + compUrl, "directFilterList", null,
           false, 'returnFromFilter', false);
      };
    
    var url='../tool/moveFilterColumn.php?orderedList=' + list;
    dojo.xhrPost({
      url : url+addTokenIndexToUrl()+addTokenIndexToUrl(),
      handleAs : "text",
      load : function(data, args) {
        if (callback)
          setTimeout(callback, 10);
      }
    });
}

function moveFilterListColumn2() {
  var mode='';
  var list='';
  var nodeList=dndListFilterSelector2.getAllNodes();
  listColumnOrder=new Array();
  for (var i=0; i < nodeList.length; i++) {
    var itemSelected=nodeList[i].id.substr(6);
    list+=itemSelected + "|";
  }  
  
  var url='../tool/moveFilterColumn.php?orderedList=' + list+addTokenIndexToUrl();
  dojo.xhrPost({
    url : url,
    handleAs : "text",
    load : function(data, args) {
    }
  });
}

function recalculateColumnSelectorName() {
  cpt=0;
  tot=0;
  while (cpt < 999) {
    var itemSelected=dijit.byId('checkListColumnSelectorWidthId' + cpt);
    if (itemSelected) {
      if (!itemSelected.get('disabled')) {
        tot+=itemSelected.get('value');
      }
    } else {
      cpt=999;
    }
    cpt++;
  }
  if (!dojo.byId('columnSelectorNameFieldId')) return;
  name="checkListColumnSelectorWidthId"+dojo.byId('columnSelectorNameFieldId').value;
  nameWidth=100 - tot;
  color="";
  if (nameWidth < 10) {
    nameWidth=10;
    color="#FFAAAA";
  }
  if (dijit.byId(name)) dijit.byId(name).set('value', nameWidth);
  totWidth=tot + nameWidth;
  totWidthDisplay="";
  if (color) {
    totWidthDisplay='<div style="background-color:' + color + '">' + totWidth
        + '&nbsp;%</div>';
  }
  dojo.byId('columnSelectorTotWidthTop').innerHTML=totWidthDisplay;
  dojo.byId('columnSelectorTotWidthBottom').innerHTML=totWidthDisplay;
  dojo.xhrGet({
    url : '../tool/saveSelectedColumn.php?action=width&item='
        + dojo.byId('columnSelectorNameTableId').value + '&width=' + nameWidth+addTokenIndexToUrl(),
    handleAs : "text",
    load : function(data, args) {
    },
    error : function() {
    }
  });
}

// =========================================================
// Items selector
// =========================================================
var oldSelectedItems=null;

function diarySelectItems(value) {
	  if (!oldSelectedItems || oldSelectedItems==value) return;
	  if (oldSelectedItems.indexOf("All")>=0 && value.length>1 ) {
	    value[0]=null;
	    oldSelectedItems=value;
	    dijit.byId("diarySelectItems").set("value",value);
	  } else if (value.indexOf("All")>=0 && oldSelectedItems.indexOf("All")===-1) {
	    value=["All"];
	    oldSelectedItems=value;
	    dijit.byId("diarySelectItems").set("value",value);
	  }
	  var finish=function() {
          loadContent("../view/diary.php","detailDiv","diaryForm");
	  };
	  if (value.length==0) value='none';
	  saveDataToSession('diarySelectedItems', value, true, finish);
	  oldSelectedItems=value;
}

function globalViewSelectItems(value) {
  if (!oldSelectedItems || oldSelectedItems==value) return;
  if (oldSelectedItems.indexOf(" ")>=0 && value.length>1 ) {
    value[0]=null;
    oldSelectedItems=value;
    dijit.byId("globalViewSelectItems").set("value",value);
  } else if (value.indexOf(" ")>=0 && oldSelectedItems.indexOf(" ")===-1) {
    value=[" "];
    oldSelectedItems=value;
    dijit.byId("globalViewSelectItems").set("value",value);
  }
  var finish=function() {
    refreshJsonList("GlobalView");
  };
  if (value.length==0) value='none';
  saveDataToSession('globalViewSelectedItems', value, true, finish);
  oldSelectedItems=value;
}
function globalPlanningSelectItems(value) {
  if (!oldSelectedItems || oldSelectedItems==value) return;
  if (oldSelectedItems.indexOf(" ")>=0 && value.length>1 ) {
    value[0]=null;
    oldSelectedItems=value;
    dijit.byId("globalPlanningSelectItems").set("value",value);
  } else if (value.indexOf(" ")>=0 && oldSelectedItems.indexOf(" ")===-1) {
    value=[" "];
    oldSelectedItems=value;
    dijit.byId("globalPlanningSelectItems").set("value",value);
  }
  var finish=function() {
    refreshJsonPlanning();
  };
  if (value.length==0) value='none';
  saveDataToSession('globalPlanningSelectedItems', value, true, finish);
  oldSelectedItems=value;
}



/*
 * ========================================================================
 * Today management
 * ========================================================================
 */

function setTodayParameterHideSection(section){
  var url='../tool/saveNewTodayParameters.php?section=' + section;
  dojo.xhrPost({
    url : url+addTokenIndexToUrl(),
    handleAs : "text",
    load : function(data, args) {
    }
  });
}

function setTodayParameterHiderReportSection(section){
  var url='../tool/saveNewTodayParameters.php?idReport=' + section;
  dojo.xhrPost({
    url : url+addTokenIndexToUrl(),
    handleAs : "text",
    load : function(data, args) {
    }
  });
}

function setTodayParameterDeleteReport(idReport){
  var url='../tool/saveTodayDeleteReport.php?idReport=' + idReport;
  dojo.xhrPost({
    url : url+addTokenIndexToUrl(),
    handleAs : "text",
    load : function(data, args) {
    }
  });
}

function saveTodayParameters() {
  loadContent('../tool/saveTodayParameters.php', 'centerDiv',
      'todayParametersForm');
  dijit.byId('dialogTodayParameters').hide();
}

function saveTodayParametersSwitch() {
  loadContent('../tool/saveTodayParametersSwitch.php', 'centerDiv',
      'todayParametersForm');
  dijit.byId('dialogNewTodayParameters').hide();
}

function setTodayParameterDeleted(id) {
  dojo.byId('dialogTodayParametersDelete' + id).value=1;
  dojo.byId('dialogTodayParametersRow' + id).style.display='none';
}

function loadReport(url, dialogDiv) {
  var contentWidget=dijit.byId(dialogDiv);
  contentWidget.set('content',
      '<img src="../view/css/images/treeExpand_loading.gif" />');
  dojo.xhrGet({
    url : url+addTokenIndexToUrl(),
    handleAs : "text",
    load : function(data) {
      var contentWidget=dijit.byId(dialogDiv);
      if (!contentWidget) {
        return;
      }
      contentWidget.set('content', data);
    },
    error : function() {
      consoleTraceLog("error loading report " + url + " into " + dialogDiv);
    }
  });
}

function reorderTodayItems() {
  var nodeList=dndTodayParameters.getAllNodes();
  for (var i=0; i < nodeList.length; i++) {
    var item=nodeList[i].id.substr(24);
    var order=dojo.byId("dialogTodayParametersOrder" + item);
    if (order) {
      order.value=i + 1;
    }
  }
}
var multiSelection=false;
var switchedModeBeforeMultiSelection=false;
function startMultipleUpdateMode(objectClass) {
  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
  grid=dijit.byId("objectGrid"); // if the element is not a widget, exit.
  if (!grid) {
    return;
  }
  multiSelection=true;
  formChangeInProgress=true;
  switchedModeBeforeMultiSelection=switchedMode;
  if (switchedModeBeforeMultiSelection) {
    switchModeOn();
  }
  unselectAllRows("objectGrid");
  dijit.byId('objectGrid').selection.setMode('extended');
  loadContent('../view/objectMultipleUpdate.php?objectClass=' + objectClass,
      'detailDiv');
}

function saveMultipleUpdateMode(objectClass) {
  // submitForm("../tool/saveObject.php","resultDivMain", "objectForm", true);
  grid=dijit.byId("objectGrid"); // if the element is not a widget, exit.
  if (!grid) {
    return;
  }
  dojo.byId("selection").value="";
  var items=grid.selection.getSelected();
  if (items.length) {
    dojo.forEach(items, function(selectedItem) {
      if (selectedItem !== null) {
        dojo.byId("selection").value+=parseInt(selectedItem.id) + ";";
      }
    });
  }
  var inputMultipleUpdate = dojo.byId('idMultipleUpdateAttribute').value;
  if ( inputMultipleUpdate == ''){
    msg=i18n('errorNoFieldSelected');
    showAlert(msg);
    return; 
  }
  var callBack = function(){
    setTimeout("updateSelectedCountMultiple();",100);
  };
  loadContent('../tool/saveObjectMultiple.php?objectClass=' + objectClass,
      'resultDivMultiple', 'objectFormMultiple',null,null,null,null,callBack);
}

function endMultipleUpdateMode(objectClass) {
  if (dijit.byId('objectGrid')) {
    dijit.byId('objectGrid').selection.setMode('single');
    unselectAllRows("objectGrid");
  }
  multiSelection=false;
  formChangeInProgress=false;
  var sm='';
  if (switchedModeBeforeMultiSelection) {
    if (!switchedMode) {
      switchModeOn();
      sm='&switchedMode=on';
    }
  } else {
    if (switchedMode) {
      switchModeOn();
    }
  }
  if (objectClass) {
    loadContent('../view/objectDetail.php?noselect=true'+sm+'&objectClass='
        + objectClass, 'detailDiv');
  }
}

function deleteMultipleUpdateMode(objectClass) {
  grid=dijit.byId("objectGrid"); // if the element is not a widget, exit.
  if (!grid) {
    return;
  }
  dojo.byId("selection").value="";
  var items=grid.selection.getSelected();
  if (items.length) {
    dojo.forEach(items, function(selectedItem) {
      if (selectedItem !== null) {
        dojo.byId("selection").value+=parseInt(selectedItem.id) + ";";
      }
    });
  }
  actionOK=function() {
    actionOK2=function() {
      if (dijit.byId('deleteMultipleResultDiv').get('content')!='') {
        showConfirm(dijit.byId('deleteMultipleResultDiv').get('content'), function(){loadContent('../tool/deleteObjectMultiple.php?objectClass=' + objectClass,
          'resultDivMultiple', 'objectFormMultiple');});
      } else {
        loadContent('../tool/deleteObjectMultiple.php?objectClass=' + objectClass,
            'resultDivMultiple', 'objectFormMultiple');
      } 
    };
    setTimeout(function(){
      loadContent('../tool/deleteObjectMultipleControl.php?objectClass=' + objectClass,
          'deleteMultipleResultDiv', 'objectFormMultiple',null,null,null,null,actionOK2);
    },200);
  };
  msg=i18n('confirmDeleteMultiple', new Array(i18n('menu' + objectClass),
      items.length));
  showConfirm(msg, actionOK);
}
function updateSelectedCountMultiple() {
  if (dojo.byId('selectedCount')) {
    countSelectedItem('objectGrid','selectedCount');
  }
}
// gautier #533
function multipleUpdateResetPwd(objectClass) {
  grid=dijit.byId("objectGrid"); // if the element is not a widget, exit.
  if (!grid) {
    return;
  }
  dojo.byId("selection").value="";
  var items=grid.selection.getSelected();
  if (items.length) {
    dojo.forEach(items, function(selectedItem) {
      if (selectedItem !== null) {
        dojo.byId("selection").value+=parseInt(selectedItem.id) + ";";
      }
    });
  }
  var callBack = function(){
    
  };
  loadContent('../tool/saveObjectMultiplePwd.php?objectClass=' + objectClass,
      'resultDivMultiple', 'objectFormMultiple',null,null,null,null,callBack);
}

function addMultipleInsert(){
	grid=dijit.byId("objectGrid"); // if the element is not a widget, exit.
	if (!grid) {
	  return;
	}
	dojo.byId("selectionIdMultipleInsert").value="";
	var items=grid.selection.getSelected();
	if (items.length) {
	  dojo.forEach(items, function(selectedItem) {
	    if (selectedItem !== null) {
	      dojo.byId("selectionIdMultipleInsert").value+=parseInt(selectedItem.id) + ",";
	    }
	  });
	}
	var idSelect=dojo.byId("selectionIdMultipleInsert").value;
	var valueSelect=dojo.byId("selectionValueMultipleInsert").value;
	if(idSelect == undefined || idSelect ==""){
		showAlert(i18n("noItemSelected"));
	}else{
		window["add" + valueSelect]();
	}
}

function showImage(objectClass, objectId, imageName, mode, size, idResource) {
  if(mode == undefined)mode=false;
  if(size == undefined)size=false;
  if (objectClass == 'Affectable' || objectClass == 'Resource' || objectClass == 'User' || objectClass == 'Contact') {
    imageUrl="../files/thumbs/Affectable_" + objectId + "/thumb80.png";
  }else if(objectClass == 'Note'){
	  imageUrl=objectId;
  }else if(mode == "dialogMail"){
	imageUrl="../tool/download.php?class=" + objectClass + "&id=" + objectId + "&mode=" + mode + "&imageName=" + imageName+ "&size=" + size+addTokenIndexToUrl();
  }else {
    imageUrl="../tool/download.php?class=" + objectClass + "&id=" + objectId+addTokenIndexToUrl();
  }
  var dialogShowImage=dijit.byId("dialogShowImage");
  if (!dialogShowImage) {
    dialogShowImage=new dojox.image.LightboxDialog({});
    dialogShowImage.startup();
  }
  if (dialogShowImage && dialogShowImage.show) {
    if (dojo.isFF) {
      dojo.xhrGet({
        url : imageUrl,
        handleAs : "text",
        load : function(data) {
          dialogShowImage.show({
            title : imageName,
            href : imageUrl
          });
          dijit.byId('formDiv').resize();
        }
      });
    } else {
      dialogShowImage.show({
        title : imageName,
        href : imageUrl
      });
      if (dijit.byId('formDiv')) dijit.byId('formDiv').resize();
    }
    // dialogShowImage.show({ title:imageName, href:imageUrl });
  } else {
    showError("Error loading image " + imageName);
  }
  // dijit.byId('formDiv').resize();
}
function showBigImage(objectClass, objectId, node, title, hideImage, nocache) {
  var top=node.getBoundingClientRect().top;
  var left=node.getBoundingClientRect().left;
  var height=node.getBoundingClientRect().height;
  var width=node.getBoundingClientRect().width;
  if (!objectClass && !objectId) top+=15;
  if (!height) height=40;
  if (objectClass == 'Affectable' || objectClass == 'Resource'
      || objectClass == 'User' || objectClass == 'Contact') {
    imageUrl="../files/thumbs/Affectable_" + objectId + "/thumb80.png";
    if (nocache) {
      imageUrl+=nocache+addTokenIndexToUrl();
    }
  } else {
    imageUrl="../tool/download.php?class=" + objectClass + "&id=" + objectId+addTokenIndexToUrl();
  }
  var centerThumb80=dojo.byId("centerThumb80");
  if (centerThumb80) {
    var htmlPhoto='';
    var alone='';
    if (objectClass && objectId && !hideImage) {
      htmlPhoto='<img style="border-radius:40px;" src="' + imageUrl + '" />';
    } else {
      alone='Alone';
    }
    if (title) {
      htmlPhoto+='<div id="centerThumb80TitleContainer" class="thumbBigImageTitle' + alone + '">' + title
          + '</div>';
    }
    var topPx=(top - 40 + (height / 2)) + "px";
    var leftPx=(left - 125) + "px";
    if(dojo.byId('objectClassManual') && dojo.byId('objectClassManual').value=='ActivityStream'){
      leftPx=(left + 125) + "px";
    }
    if (parseInt(leftPx)<3) {
      leftPx=(left+width+5)+"px";
    }
    
    centerThumb80.innerHTML=htmlPhoto;
    centerThumb80.style.top=topPx;
    centerThumb80.style.left=leftPx;
    centerThumb80.style.display="block";
    var titleDivRect=(dojo.byId('centerThumb80TitleContainer'))?dojo.byId('centerThumb80TitleContainer').getBoundingClientRect():null;
    var globalDivRect=document.documentElement.getBoundingClientRect();
    if (titleDivRect && titleDivRect.top+titleDivRect.height+50>globalDivRect.height) {
      var newTop=globalDivRect.height-titleDivRect.height-50;
      if (newTop<0) newTop=0;
      centerThumb80.style.top=newTop+'px';
    }
  }
  
}
function hideBigImage(objectClass, objectId) {
  var centerThumb80=dojo.byId("centerThumb80");
  if (centerThumb80) {
    centerThumb80.innerHTML="";
    centerThumb80.style.display="none";
  }
}

// *******************************************************
// ToolTip for mention
// *******************************************************
function pqGetMentionTooltipNode() {
  var node=dojo.byId('pqMentionTooltip');
  if (!node) {
    node=document.createElement('div');
    node.id='pqMentionTooltip';
    node.className='ktip dijitLikeTooltip';
    node.style.position='fixed';
    node.style.display='none';
    node.style.pointerEvents='none';
    node.style.zIndex='999999';
    node.innerHTML='<div class="ktipArrow"></div>'
      +'<div class="ktipRow"><div class="ktipLeft"></div><div class="ktipText"></div></div>';
    document.body.appendChild(node);
  }
  return node;
}

function _pqMentionClosest(node) {
  while (node && node !== document) {
    if (node.classList && node.classList.contains('pqMentionLink')) return node;
    node = node.parentNode;
  }
  return null;
}

function showMentionTooltip(node, offset) {
  if (!node) return;
  var tip=pqGetMentionTooltipNode();
  if (window._pqMentionCurrent === node && tip.style.display!=='none') {
    return;
  }

  var token=(window._pqMentionToken||0)+1;
  window._pqMentionToken=token;
  window._pqMentionCurrent=node;
  var id=node.getAttribute('data-mention-id');
  var name=node.getAttribute('data-mention-name') || '';
  if (!name) {
    var raw=(node.textContent||'').replace(/^\s*@/, '').trim();
    if (raw) name=raw;
  }
  var arrayColors=['#1abc9c','#2ecc71','#3498db','#9b59b6','#34495e','#16a085','#27ae60','#2980b9','#8e44ad','#2c3e50','#f1c40f','#e67e22','#99CC00','#e74c3c','#95a5a6','#d35400','#c0392b','#bdc3c7','#7f8c8d'];
  var bgColor='#777777';
  var numId=parseInt(id,10);
  if (!isNaN(numId)) {
    var ind=numId%arrayColors.length;
    if (arrayColors[ind]) bgColor=arrayColors[ind];
  }
  var initial=(name)?name.trim().charAt(0).toUpperCase():'?';
  var left=tip.querySelector('.ktipLeft');
  var label=tip.querySelector('.ktipText');
  left.innerHTML='<div class="ktipUserBox"><div class="ktipUserInitial" style="background:'+bgColor+';">'+htmlEncode(initial)+'</div></div>';
  label.textContent=name;

  var _pqLoadPhoto = function(uid) {
    if (!uid) return;
    var imageUrl="../files/thumbs/Affectable_"+uid+"/thumb80.png?_d="+new Date().toISOString().slice(0,10);
    var probe=new Image();
    probe.onload=function() {

      if (window._pqMentionToken !== token) return;
      if (!dojo.byId('pqMentionTooltip') || dojo.byId('pqMentionTooltip').style.display==='none') return;
      left.innerHTML='<div class="ktipUserBox"><img class="ktipUserImg" src="'+imageUrl+'" /></div>';
    };
    probe.src=imageUrl;
  };
  if (id) {
    _pqLoadPhoto(id);
  } else if (name) {
    if (!window._pqMentionResolveCache) window._pqMentionResolveCache={};
    var key=name.toLowerCase();
    if (window._pqMentionResolveCache.hasOwnProperty(key)) {
      var cached=window._pqMentionResolveCache[key];
      if (cached) _pqLoadPhoto(cached);
    } else {
      try {
        var resolveUrl='../tool/resolveMention.php?alias='+encodeURIComponent(name);
        resolveUrl+=addTokenIndexToUrl(resolveUrl);
        var xhr=new XMLHttpRequest();
        xhr.open('GET', resolveUrl, true);
        xhr.onload=function() {
          var rid=null;
          try {
            var resp=JSON.parse(xhr.responseText);
            if (resp && resp.id) rid=resp.id;
          } catch(e) {}
          window._pqMentionResolveCache[key]=rid;
          if (rid && window._pqMentionToken === token) _pqLoadPhoto(rid);
        };
        xhr.onerror=function() { window._pqMentionResolveCache[key]=null; };
        xhr.send();
      } catch(e) {}
    }
  }
  tip.style.display='block';
  var rect=node.getBoundingClientRect();
  var off=offset || {top:0,left:0};
  var leftPx=rect.left+off.left-5;
  var maxLeft=window.innerWidth-tip.offsetWidth-8;
  if (leftPx>maxLeft) leftPx=maxLeft;
  if (leftPx<8) leftPx=8;
  var top=rect.top+off.top+rect.height+8;
  var maxTop=window.innerHeight-tip.offsetHeight-8;
  if (top>maxTop) top=rect.top+off.top-tip.offsetHeight-8;
  if (top<8) top=8;
  tip.style.left=leftPx+'px';
  tip.style.top=top+'px';
}

function hideMentionTooltip() {
  var tip=dojo.byId('pqMentionTooltip');
  if (tip) tip.style.display='none';
  window._pqMentionCurrent=null;
  window._pqMentionToken=(window._pqMentionToken||0)+1;
}

if (!window._pqMentionDelegationInstalled) {
  window._pqMentionDelegationInstalled=true;
  document.addEventListener('mouseover', function(e) {
    var span=_pqMentionClosest(e.target);
    if (!span) return;
    showMentionTooltip(span);
  }, true);
  document.addEventListener('mouseout', function(e) {
    var span=_pqMentionClosest(e.target);
    if (!span) return;
    var related=e.relatedTarget;
    if (related && span.contains(related)) return;
    if (related && _pqMentionClosest(related)) return;
    hideMentionTooltip();
  }, true);
  window.addEventListener('scroll', function() { hideMentionTooltip(); }, true);
}

// *******************************************************
// Autocomplete for mention
// *******************************************************
function pqGetMentionSuggestNode() {
  var node=dojo.byId('pqMentionSuggest');
  if (!node) {
    node=document.createElement('div');
    node.id='pqMentionSuggest';
    node.className='pqMentionSuggest';
    node.style.position='fixed';
    node.style.display='none';
    node.style.zIndex='999999';
    document.body.appendChild(node);
  }
  return node;
}

function pqNormalizeMentionSearch(value) {
  value=(value || '').toString().toLowerCase();
  if (value.normalize) {
    value=value.normalize('NFD').replace(/[\u0300-\u036f]/g, '');
  }
  return value;
}

function pqLoadMentionCandidates(callback, forceReload) {
  if (window._pqMentionCandidates && !forceReload) {
    callback(window._pqMentionCandidates);
    if (!window._pqMentionCandidatesLoading) return;
  }
  if (!window._pqMentionCandidateCallbacks) window._pqMentionCandidateCallbacks=[];
  window._pqMentionCandidateCallbacks.push(callback);
  if (window._pqMentionCandidatesLoading) return;

  window._pqMentionCandidatesLoading=true;
  var url='../tool/mentionList.php';
  url+=addTokenIndexToUrl(url);
  url+=(url.indexOf('?') >= 0 ? '&' : '?')+'mentionRefresh='+Date.now();
  var xhr=new XMLHttpRequest();
  xhr.open('GET', url, true);
  xhr.onload=function() {
    var list=[];
    try {
      var data=JSON.parse(xhr.responseText);
      list=(data && data.items) ? data.items : [];
    } catch(e) {
      list=[];
    }
    for (var i=0;i<list.length;i++) {
      var item=list[i];
      item.initials=item.initials || '';
      item.fullName=item.fullName || '';
      item.userName=item.userName || '';
      item.profileName=item.profileName || '';
      item.photoUrl=item.photoUrl || '';
      item.hasEmail=!!item.hasEmail;
      item.isResource=!!item.isResource;
      item.isResourceTeam=!!item.isResourceTeam;
      item.canMentionFollowup=!!item.canMentionFollowup;
      item.canMentionMail=!!item.canMentionMail;
      item.canMentionNotification=!!item.canMentionNotification;
      item.mentionFollowupActive=!!item.mentionFollowupActive;
      item.mentionMailActive=!!item.mentionMailActive;
      item.mentionNotificationActive=!!item.mentionNotificationActive;
      item.insert=item.insert || item.userName || item.fullName || item.initials;
      item.searchText=pqNormalizeMentionSearch(item.initials+' '+item.fullName+' '+item.userName+' '+item.profileName);
    }
    window._pqMentionCandidates=list;
    window._pqMentionCandidatesLoading=false;
    var callbacks=window._pqMentionCandidateCallbacks || [];
    window._pqMentionCandidateCallbacks=[];
    for (var c=0;c<callbacks.length;c++) callbacks[c](list);
  };
  xhr.onerror=function() {
    window._pqMentionCandidates=[];
    window._pqMentionCandidatesLoading=false;
    var callbacks=window._pqMentionCandidateCallbacks || [];
    window._pqMentionCandidateCallbacks=[];
    for (var c=0;c<callbacks.length;c++) callbacks[c]([]);
  };
  xhr.send();
}

function pqGetMentionMatch(text) {
  var match=/(^|\s)@([^\s@]*)$/.exec(text);
  if (!match) return null;
  return {
    query: match[2],
    start: text.length - match[2].length - 1,
    end: text.length
  };
}

function pqMentionContextFromTextarea(node) {
  if (!node || typeof node.selectionStart == 'undefined') return null;
  var cursor=node.selectionStart;
  if (node.selectionEnd !== cursor) return null;
  var match=pqGetMentionMatch(node.value.substring(0, cursor));
  if (!match) return null;
  match.type='textarea';
  match.node=node;
  match.cursor=cursor;
  return match;
}

function pqMentionGetSelectionDocument(editor) {
  if (editor && editor.document && editor.document.$) {
    return editor.document.$;
  }
  return document;
}

function pqMentionContextFromSelection(editor) {
  var doc=pqMentionGetSelectionDocument(editor);
  var win=doc.defaultView || doc.parentWindow;
  if (!win || !win.getSelection) return null;
  var sel=win.getSelection();
  if (!sel || !sel.rangeCount || !sel.isCollapsed) return null;
  var range=sel.getRangeAt(0);
  var node=range.startContainer;
  if (!node || node.nodeType != 3) return null;
  var text=node.nodeValue.substring(0, range.startOffset);
  var match=pqGetMentionMatch(text);
  if (!match) return null;
  match.type='contenteditable';
  match.editor=editor || null;
  match.doc=doc;
  match.node=node;
  match.range=range.cloneRange();
  return match;
}

function pqMentionGetPosition(context) {
  if (context.type == 'textarea') {
    var rect=context.node.getBoundingClientRect();
    return {left:rect.left+8, top:rect.bottom+4};
  }
  var rect=null;
  try {
    var clone=context.range.cloneRange();
    clone.collapse(false);
    rect=clone.getBoundingClientRect();
  } catch(e) {
    rect=null;
  }
  if ((!rect || (!rect.left && !rect.top)) && context.node.parentNode && context.node.parentNode.getBoundingClientRect) {
    rect=context.node.parentNode.getBoundingClientRect();
  }
  if (!rect) return {left:8, top:8};
  var frameOffset={left:0, top:0};
  if (context.editor && context.doc && context.doc.defaultView && context.doc.defaultView.frameElement) {
    var frameRect=context.doc.defaultView.frameElement.getBoundingClientRect();
    frameOffset.left=frameRect.left;
    frameOffset.top=frameRect.top;
  }
  return {left:rect.left+frameOffset.left, top:rect.bottom+frameOffset.top+4};
}

function pqMentionFilterCandidates(query, list) {
  var normalized=pqNormalizeMentionSearch(query);
  var result=[];
  for (var i=0;i<list.length;i++) {
    if (!normalized || list[i].searchText.indexOf(normalized) >= 0) {
      result.push(list[i]);
    }
  }
  return result;
}

function pqMentionShowSuggestions(context) {
  var renderToken=(window._pqMentionSuggestRenderToken || 0)+1;
  window._pqMentionSuggestRenderToken=renderToken;
  var previousContext=window._pqMentionCandidateContext;
  var isNewContext=!previousContext
    || previousContext.type != context.type
    || previousContext.node !== context.node
    || previousContext.start != context.start;
  window._pqMentionCandidateContext={
    type: context.type,
    node: context.node,
    start: context.start
  };
  pqLoadMentionCandidates(function(list) {
    if (renderToken !== window._pqMentionSuggestRenderToken) return;
    var matches=pqMentionFilterCandidates(context.query, list);
    if (!matches.length) {
      pqMentionHideSuggestions();
      return;
    }
    window._pqMentionSuggestState={
      context: context,
      matches: matches,
      selected: 0
    };
    pqMentionRenderSuggestions();
  }, isNewContext);
}

function pqMentionRenderSuggestions() {
  var state=window._pqMentionSuggestState;
  if (!state) return;
  var node=pqGetMentionSuggestNode();
  var firstMatch=state.matches.length ? state.matches[0] : null;
  var hasActiveMentionOption=firstMatch && (firstMatch.mentionFollowupActive || firstMatch.mentionMailActive || firstMatch.mentionNotificationActive);
  var html=hasActiveMentionOption ? '' : '<div class="pqMentionSuggestNoOption">'+htmlEncode(i18n('mentionNoOptionActivated'))+'</div>';
  html+='<div class="pqMentionSuggestList">';
  for (var i=0;i<state.matches.length;i++) {
    var item=state.matches[i];
    var selected=(i == state.selected) ? ' pqMentionSuggestSelected' : '';
    var initials=item.initials || '?';
    var photoHtml=item.photoUrl ? '<img src="'+htmlEncode(item.photoUrl)+'" onerror="this.style.display=\'none\';" />' : '';
    var avatarColor=pqMentionColorFromId(item.id);
    var followupIcon=pqMentionFlagImage(item.mentionFollowupActive, item.canMentionFollowup, 'pqMentionSuggestFollowupIcon', i18n(item.canMentionFollowup?'mentionFollowupWillBeAdded':'mentionFollowupOptionDisabled'));
    var notificationIcon=pqMentionFlagImage(item.mentionNotificationActive, item.canMentionNotification, 'pqMentionSuggestNotificationIcon', i18n(item.canMentionNotification?'mentionNotificationWillBeSent':'mentionNotificationOptionDisabled'));
    var emailIcon=pqMentionFlagSvg(item.mentionMailActive, item.canMentionMail, i18n(item.canMentionMail?'mentionEmailWillBeSent':'mentionEmailOptionDisabled'), pqMentionEmailIcon());
    html+='<div class="pqMentionSuggestRow'+selected+'" data-index="'+i+'" data-insert="'+htmlEncode(item.insert)+'">'
      +'<div class="pqMentionSuggestAvatar">'
      +'<span class="pqMentionSuggestAvatarFallback" style="background-color:'+avatarColor+';">'+htmlEncode(initials.substring(0,2).toUpperCase())+'</span>'
      +photoHtml
      +'</div>'
      +'<div class="pqMentionSuggestIdentity">'
      +'<div class="pqMentionSuggestFullName">'+(item.isResourceTeam?'<span class="pqMentionSuggestPoolIcon imageColorNewGui iconResourceTeam iconSize16"></span>':'')+'<span class="pqMentionSuggestFullNameText">'+htmlEncode(item.fullName || item.insert)+'</span></div>'
      +'<div class="pqMentionSuggestMeta"><span class="pqMentionSuggestInitials">'+htmlEncode(initials)+'</span><span class="pqMentionSuggestUserName">'+htmlEncode(item.userName || '-')+'</span></div>'
      +'</div>'
      +'<div class="pqMentionSuggestProfile">'+htmlEncode(item.profileName || '-')+'</div>'
      +'<div class="pqMentionSuggestFlags">'
      +followupIcon
      +notificationIcon
      +emailIcon
      +'</div>'
      +'</div>';
  }
  html+='</div>';
  node.innerHTML=html;
  node.style.display='block';
  var pos=pqMentionGetPosition(state.context);
  var left=pos.left;
  var top=pos.top;
  var maxLeft=window.innerWidth-node.offsetWidth-8;
  if (left>maxLeft) left=maxLeft;
  if (left<8) left=8;
  var maxTop=window.innerHeight-node.offsetHeight-8;
  if (top>maxTop) top=pos.top-node.offsetHeight-24;
  if (top<8) top=8;
  node.style.left=left+'px';
  node.style.top=top+'px';
}

function pqMentionEmailIcon() {
  return '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 6h18v12H3z"></path><path d="M3 7l9 7 9-7"></path></svg>';
}

function pqMentionFlagClass(active) {
  return active ? ' pqMentionSuggestFlagActive' : ' pqMentionSuggestFlagInactive';
}

function pqMentionFlagImage(optionActive, available, iconClass, title) {
  if (!optionActive) return '<span class="pqMentionSuggestFlagSlot"></span>';
  return '<span class="pqMentionSuggestFlagSlot"><span class="pqMentionSuggestFlag pqMentionSuggestFlagImage'+pqMentionFlagClass(available)+' '+iconClass+'" title="'+htmlEncode(title)+'"></span></span>';
}

function pqMentionFlagSvg(optionActive, available, title, iconHtml) {
  if (!optionActive) return '<span class="pqMentionSuggestFlagSlot"></span>';
  return '<span class="pqMentionSuggestFlagSlot"><span class="pqMentionSuggestFlag'+pqMentionFlagClass(available)+'" title="'+htmlEncode(title)+'">'+iconHtml+'</span></span>';
}

function pqMentionColorFromId(id) {
  var arrayColors=['#1abc9c','#2ecc71','#3498db','#9b59b6','#34495e','#16a085','#27ae60','#2980b9','#8e44ad','#2c3e50','#f1c40f','#e67e22','#99CC00','#e74c3c','#95a5a6','#d35400','#c0392b','#bdc3c7','#7f8c8d'];
  var numId=parseInt(id,10);
  if (isNaN(numId)) return '#777777';
  var ind=numId%arrayColors.length;
  return arrayColors[ind] || '#777777';
}

function pqMentionHideSuggestions() {
  var node=dojo.byId('pqMentionSuggest');
  if (node) node.style.display='none';
  window._pqMentionSuggestRenderToken=(window._pqMentionSuggestRenderToken || 0)+1;
  window._pqMentionSuggestState=null;
}

function pqMentionInsertValue(value) {
  var state=window._pqMentionSuggestState;
  if (!state || !value) return;
  var context=state.context;
  var text='@'+value+' ';
  if (context.type == 'textarea') {
    var node=context.node;
    var before=node.value.substring(0, context.start);
    var after=node.value.substring(context.cursor);
    node.value=before+text+after;
    var newPos=(before+text).length;
    node.selectionStart=newPos;
    node.selectionEnd=newPos;
    node.focus();
    if (typeof formChanged == 'function') formChanged();
  } else {
    var doc=context.doc;
    var win=doc.defaultView || doc.parentWindow;
    var range=context.range.cloneRange();
    range.setStart(context.node, context.start);
    range.setEnd(context.node, context.range.startOffset);
    range.deleteContents();
    var textNode=doc.createTextNode(text);
    range.insertNode(textNode);
    range.setStartAfter(textNode);
    range.collapse(true);
    var sel=win.getSelection();
    sel.removeAllRanges();
    sel.addRange(range);
    if (context.editor) context.editor.updateElement();
  }
  pqMentionHideSuggestions();
}

function pqMentionRefreshFromEvent(event, editor) {
  var target=(event && event.target) ? event.target : null;
  var context=null;
  if (editor) {
    context=pqMentionContextFromSelection(editor);
  } else if (target && target.tagName == 'TEXTAREA') {
    context=pqMentionContextFromTextarea(target);
  } else {
    context=pqMentionContextFromSelection(null);
  }
  if (!context) {
    window._pqMentionCandidateContext=null;
    pqMentionHideSuggestions();
    return;
  }
  pqMentionShowSuggestions(context);
}

function pqMentionHandleKeyDown(event) {
  var state=window._pqMentionSuggestState;
  if (!state) return false;
  var key=event.key || event.keyCode;
  if (key == 'ArrowDown' || key == 40) {
    state.selected=(state.selected+1) % state.matches.length;
    pqMentionRenderSuggestions();
    event.preventDefault();
    return true;
  }
  if (key == 'ArrowUp' || key == 38) {
    state.selected=(state.selected+state.matches.length-1) % state.matches.length;
    pqMentionRenderSuggestions();
    event.preventDefault();
    return true;
  }
  if (key == 'Enter' || key == 13 || key == 'Tab' || key == 9) {
    pqMentionInsertValue(state.matches[state.selected].insert);
    event.preventDefault();
    return true;
  }
  if (key == 'Escape' || key == 27) {
    pqMentionHideSuggestions();
    event.preventDefault();
    return true;
  }
  return false;
}

function pqMentionIsSuggestControlKey(event) {
  var key=event.key || event.keyCode;
  return (key == 'ArrowDown' || key == 40
      || key == 'ArrowUp' || key == 38
      || key == 'Enter' || key == 13
      || key == 'Tab' || key == 9
      || key == 'Escape' || key == 27);
}

function pqInstallMentionAutocompleteOnCkEditor(editor) {
  if (!editor || editor._pqMentionAutocompleteInstalled) return;
  editor._pqMentionAutocompleteInstalled=true;
  editor.on('instanceReady', function(evt) {
    var doc=evt.editor.document ? evt.editor.document.$ : null;
    if (!doc || !doc.body) return;
    doc.addEventListener('keydown', function(e) {
      pqMentionHandleKeyDown(e);
    }, true);
    doc.addEventListener('keyup', function(e) {
      if (pqMentionIsSuggestControlKey(e)) return;
      window.setTimeout(function() { pqMentionRefreshFromEvent(e, evt.editor); }, 0);
    }, true);
    doc.addEventListener('click', function() { pqMentionHideSuggestions(); }, true);
  });
}

if (!window._pqMentionSuggestDelegationInstalled) {
  window._pqMentionSuggestDelegationInstalled=true;
  document.addEventListener('keydown', pqMentionHandleKeyDown, true);
  document.addEventListener('keyup', function(e) {
    if (pqMentionIsSuggestControlKey(e)) return;
    window.setTimeout(function() { pqMentionRefreshFromEvent(e, null); }, 0);
  }, true);
  document.addEventListener('input', function(e) {
    window.setTimeout(function() { pqMentionRefreshFromEvent(e, null); }, 0);
  }, true);
  document.addEventListener('mousedown', function(e) {
    var suggest=dojo.byId('pqMentionSuggest');
    if (suggest && suggest.contains(e.target)) return;
    pqMentionHideSuggestions();
  }, true);
  document.addEventListener('click', function(e) {
    var suggest=dojo.byId('pqMentionSuggest');
    if (!suggest || !suggest.contains(e.target)) return;
    var insert=e.target.getAttribute('data-insert');
    if (!insert) {
      var row=e.target;
      while (row && row !== suggest && (!row.classList || !row.classList.contains('pqMentionSuggestRow'))) {
        row=row.parentNode;
      }
      if (row) insert=row.getAttribute('data-insert');
    }
    if (insert) {
      e.preventDefault();
      pqMentionInsertValue(insert);
    }
  }, true);
  window.addEventListener('scroll', function(e) {
    var suggest=dojo.byId('pqMentionSuggest');
    if (suggest && e.target && suggest.contains(e.target)) return;
    pqMentionHideSuggestions();
  }, true);
}

showHtmlContent=null;
function showLink(link) {
  if (dojo.isIE) {
    if (showHtmlContent==null) {
      showHtmlContent=dijit.byId("dialogShowHtml").get('content');
    } else {
      dijit.byId("dialogShowHtml").set('content',showHtmlContent);
    }
  }
  // window.frames['showHtmlFrame'].location.href='../view/preparePreview.php';
  dijit.byId("dialogShowHtml").title=link;
  window.frames['showHtmlFrame'].location.href=link;
  dijit.byId("dialogShowHtml").show();
  window.frames['showHtmlFrame'].focus();
}
function showHtml(id, file, className) {
  if (dojo.isIE) {
    if (showHtmlContent==null) {
      showHtmlContent=dijit.byId("dialogShowHtml").get('content');
    } else {
      dijit.byId("dialogShowHtml").set('content',showHtmlContent);
    }
  }
  dijit.byId("dialogShowHtml").title=file;
  window.frames['showHtmlFrame'].location.href='../tool/download.php?class='+className+'&id='
      + id + '&showHtml=true'+addTokenIndexToUrl();
  dijit.byId("dialogShowHtml").clearOnHide=false;
  dijit.byId("dialogShowHtml").show();
  window.frames['showHtmlFrame'].focus();
} 

// *******************************************************
// Dojo code to position into a tree
// *******************************************************
function recursiveHunt(lookfor, model, buildme, item) {
  var id=model.getIdentity(item);
  buildme.push(id);
  if (id == lookfor) {
    return buildme;
  }
  for ( var idx in item.children) {
    var buildmebranch=buildme.slice(0);
    var r=recursiveHunt(lookfor, model, buildmebranch, item.children[idx]);
    if (r) {
      return r;
    }
  }
  return undefined;
}

function selectTreeNodeById(tree, lookfor) {
  var buildme=[];
  var result=recursiveHunt(lookfor, tree.model, buildme, tree.model.root);
  if (result && result.length > 0) {
    tree.set('path', result);
  }
}


// ==================================================================
// Project Selector Functions
// ==================================================================
function changeProjectSelectorType(displayMode) {
	// #2887
	
	
	var callBack = function(){
	  loadContent("../view/menuProjectSelector.php", 'projectSelectorDiv', null,null,null,null,null,function(){ pqSelectorInit(); });
	};
	
	saveDataToSession('projectSelectorDisplayMode', displayMode, true, callBack);
	if(displayMode=='select'){
	  if(dojo.byId('favoriteProjectEditRow')){
	    dojo.byId('favoriteProjectEditRow').style.display = 'none';
	  }
	}else{
	  if(dojo.byId('favoriteProjectEditRow')){
      dojo.byId('favoriteProjectEditRow').style.display = '';
    }
	}
  if (dijit.byId('dialogProjectSelectorParameters')) {
    dijit.byId('dialogProjectSelectorParameters').hide();
  }
}

// The search covers every project, since the whole list is in the dom
function filterProjects() {
  var input = dojo.byId('projectFilterInput');
  dojo.byId('clearSearchSelectorProject').style.display = (input.value.length > 0) ? 'block' : 'none';
  pqSelectorFilter(input.value);
  var pane = document.getElementById('projectTitlePaneDiv');
  if (pane) { pane.scrollTop = 0; }
  if (typeof resizeTitlePanProjectSelector == 'function') { resizeTitlePanProjectSelector(); }
}

// Enter checks every search result
function validateSearchProject(){
  if(event.keyCode != '13')return;
  var ids = pqSelectorVisibleIds();
  for(var i = 0; i < ids.length; i++){ pqProjectCheckSet(ids[i], true); }
  checkProjectToSelect();
  selectedMultiProject();
}

function refreshProjectSelectorList(skipRefreshPlanningList, openDropDown, hideParam) {
  if (skipRefreshPlanningList==null || skipRefreshPlanningList==undefined) skipRefreshPlanningList=false;
  if (openDropDown==null || openDropDown==undefined) openDropDown=false;
  if (hideParam==null || hideParam==undefined) hideParam=true;
  dojo.xhrPost({
    url : "../tool/refreshVisibleProjectsList.php"+addTokenIndexToUrl('?'),
    load : function() {
      var callback = function(){
        // The loaded fragment carries data only, so rebuild the list from here
        pqSelectorInit();
        if(openDropDown){
          dijit.byId('selectedProject').openDropDown();
        }
      };
      loadContent('../view/menuProjectSelector.php', 'projectSelectorDiv', null,null,null,null,null,callback);
      if (dijit.byId('idProjectPlan')) {
        if (! skipRefreshPlanningList){
		  var projectPlanValue = dijit.byId('idProjectPlan').get('value');
	      var objectIdValue = dojo.byId('objectId').value;
		  if(arraySelectedProject.length == 0){
  			if(favoriteProjectsArray != ''){
  				projectPlanValue = favoriteProjectsArray.split(',');
  			}else{
  				projectPlanValue = new Array(' ');
  			}
  		  }else if (projectPlanValue.length > 0 && objectIdValue) {
			projectPlanValue.push(objectIdValue);
			saveDataToSession('projectSelected',dijit.byId('idProjectPlan').get('value'),true);
		  }
		  refreshList('planning', null, null, projectPlanValue, 'idProjectPlan', false);
		}
      }
    }
  });
  if (hideParam && dijit.byId('dialogProjectSelectorParameters')) {
    dijit.byId('dialogProjectSelectorParameters').hide();
  }
}

// ********************************************************************************************
// Diary
// ********************************************************************************************
function diaryPrevious() {
  diaryPreviousNext(-1);
}
function diaryNext() {
  diaryPreviousNext(1);
}

var noRefreshDiaryPeriod=false;
function diarySelectDate() {
  if (noRefreshDiaryPeriod) {
    return;
  }
  noRefreshDiaryPeriod=true;
  var directDate = dijit.byId('dateSelectorDiary').get('value');
  if (!directDate)return;
  var period=dijit.byId('diaryPeriod').get("value");
  var year=directDate.getFullYear();
  var month=directDate.getMonth()+1;
  var week=directDate.getWeek();
  var day=formatDate(directDate);
  if (period == "month") {
    diaryMonth(month, directDate);
  } else if (period == "week") {
    diaryWeek(week, directDate);
  } else if (period == "day") {
    diaryDay(day);
  }
  setTimeout("noRefreshDiaryPeriod=false;", 10);
  setTimeout('loadContent("../view/diary.php", "detailDiv", "diaryForm");',200);
  return true;
}

function diaryPreviousNext(way) {
  if (waitingForReply)  {
    showInfo(i18n("alertOngoingQuery"));
    return;
  }
  var dateSelector = dijit.byId('dateSelectorDiary').get('value');
  if (!dateSelector)return;
  var period=dijit.byId('diaryPeriod').get("value");
  if (period == "month") {
    var nextDate = new Date(dojo.byId("diaryDay").value);
    var nextMonth=(parseInt(dojo.byId("diaryMonth").value)-1) + parseInt(way);
    nextDate.setMonth(nextMonth);
    var month=nextDate.getMonth();
    var year=nextDate.getFullYear();
    var date=new Date(year, month , 1);
    diaryMonth(month+1, date);
  } else if (period == "week") {
    var wayWeek = way*7;
    var date = new Date(formatDate(dateSelector));
    date.setDate(date.getDate() + parseInt(wayWeek));
    var week = date.getWeek();
    diaryWeek(week, date);
  } else if (period == "day") {
    var date = new Date(formatDate(dateSelector));
    date.setDate(date.getDate() + parseInt(way));
    var day = formatDate(date);
    diaryDay(day);
  }
}

function diaryChangePeriod(){
  if (noRefreshDiaryPeriod) {
    return;
  }
  var period = dijit.byId('diaryPeriod').get("value");
  saveDataToSession('diaryPeriod', period, true);
  var date = dijit.byId('dateSelectorDiary').get('value');
  if (!date)return;
  var year=parseInt(dojo.byId("diaryYear").value);
  var month=parseInt(dojo.byId("diaryMonth").value);
  var week=parseInt(dojo.byId("diaryWeek").value);
  var day=dojo.byId("diaryDay").value;
  if (period == "month") {
    diaryMonth(month, date);
  } else if (period == "week") {
    diaryWeek(week, date);
  } else if (period == "day") {
    diaryDay(day);
  }
}

function diaryWeek(week, currentDate) {
  var date = new Date(currentDate);
  var year = date.getFullYear();
  var week = date.getWeek();
  var month = date.getMonth()+1;
  dojo.byId("diaryYear").value=year;
  dojo.byId("diaryMonth").value=month;
  dojo.byId("diaryWeek").value=week;
  diaryDisplayWeek(week, year);
}

function diaryMonth(month, currentDate) {
  var date = new Date(currentDate);
  var year=date.getFullYear();
  var week = date.getWeek();
  dojo.byId("diaryYear").value=year;
  dojo.byId("diaryMonth").value=month;
  dojo.byId("diaryWeek").value=week;
  diaryDisplayMonth(month, year);
}
function diaryDay(day) {
  var date = new Date(day);
  var year=date.getFullYear();
  var week = date.getWeek();
  var month = date.getMonth()+1;
  dojo.byId("diaryYear").value=year;
  dojo.byId("diaryMonth").value=month;
  dojo.byId("diaryWeek").value=week;
  dojo.byId("diaryDay").value=day;
  diaryDisplayDay(day);
}

function diaryDisplayMonth(month, year) {
  var vMonthArr=new Array();
  vMonthArr[1]=i18n("January");
  vMonthArr[2]=i18n("February");
  vMonthArr[3]=i18n("March");
  vMonthArr[4]=i18n("April");
  vMonthArr[5]=i18n("May");
  vMonthArr[6]=i18n("June");
  vMonthArr[7]=i18n("July");
  vMonthArr[8]=i18n("August");
  vMonthArr[9]=i18n("September");
  vMonthArr[10]=i18n("October");
  vMonthArr[11]=i18n("November");
  vMonthArr[12]=i18n("December");
  caption=vMonthArr[month] + " " + year;
  dojo.byId("diaryCaption").innerHTML=caption;
  var firstday=new Date(year, month-1, 1);
  var date=getFirstDayOfWeek(firstday.getWeek(), year);
  dojo.byId("diaryDay").value=formatDate(firstday);
  saveDataToSession('dateSelectorDiary',formatDate(firstday), false);
  noRefreshDiaryPeriod=true;
  dijit.byId('dateSelectorDiary').set('value', date);
  dijit.byId("diaryPeriod").set('value', "month");
  setTimeout("noRefreshDiaryPeriod=false;", 10);
  loadContent("../view/diary.php", "detailDiv", "diaryForm");
}

function diaryDisplayWeek(week, year) {
  var firstday=getFirstDayOfWeek(week, year);
  var lastday=new Date(firstday);
  lastday.setDate(firstday.getDate() + 6);
  if (week<10) week='0'+parseInt(week);
  caption=year + ' #' + week + "<span style='font-size:12px'> (" + dateFormatter(formatDate(firstday))
      + " - " + dateFormatter(formatDate(lastday)) + ") </span>";
  dojo.byId("diaryCaption").innerHTML=caption;
  noRefreshDiaryPeriod=true;
  dijit.byId('dateSelectorDiary').set('value', firstday);
  dojo.byId("diaryDay").value=formatDate(firstday);
  saveDataToSession('dateSelectorDiary',formatDate(firstday), false);
  dijit.byId("diaryPeriod").set('value', "week");
  setTimeout("noRefreshDiaryPeriod=false;", 10);
  loadContent("../view/diary.php", "detailDiv", "diaryForm");
}

function diaryDisplayDay(day) {
  var vDayArr=new Array(i18n("Sunday"), i18n("Monday"), i18n("Tuesday"),
      i18n("Wednesday"), i18n("Thursday"), i18n("Friday"), i18n("Saturday"));
  var currentDate=new Date(day);
  caption=vDayArr[currentDate.getDay()] + " " + dateFormatter(day);
  dojo.byId("diaryCaption").innerHTML=caption;
  noRefreshDiaryPeriod=true;
  dijit.byId('dateSelectorDiary').set('value', currentDate);
  dijit.byId("diaryPeriod").set('value', "day");
  saveDataToSession('dateSelectorDiary',day, false);
  setTimeout("noRefreshDiaryPeriod=false;", 10);
  loadContent("../view/diary.php", "detailDiv", "diaryForm");
}

function diaryShowFullWidthElement(value){
  saveDataToSession("diaryFullWidthElement",value,true);
  if(value == 'on'){
    dojo.byId('diarySeeWorkTR').style.display = '';
  }else{
    dojo.byId('diarySeeWorkTR').style.display = 'none';
  }
  loadContent("../view/diary.php","detailDiv","diaryForm");
}

var hideDiaryContextMenuTimeout = null;
function hideDiaryContextMenu(delay) {
  var contextMenu = dijit.byId('diaryContextMenu');
  var contextMenuDiv = dojo.byId('dialogDiaryContextMenu');
  if (contextMenu) {
    var callback = function () {
      if (dojo.byId('addFromDiary')) dojo.byId('addFromDiary').setAttribute('onClick', '');
      if (dojo.byId('editFromDiary')) dojo.byId('editFromDiary').setAttribute('onClick', '');
      if (dojo.byId('gotoTimesheetFromDiary')) dojo.byId('gotoTimesheetFromDiary').setAttribute('onClick', '');
      if (dojo.byId('gotoItemFromDiary')) dojo.byId('gotoItemFromDiary').setAttribute('onClick', '');
	  if (dojo.byId('searchInPlanningFromDiary')) dojo.byId('searchInPlanningFromDiary').setAttribute('onClick', '');
      contextMenu.closeDropDown();
      contextMenuDiv.blur();
    };
    hideDiaryContextMenuTimeout = setTimeout(callback, delay);
  }
}

function openDiaryContextMenu(refId, refType, idResource, targetDate, targetTime, idAssignment){
  var contextMenu = dijit.byId('diaryContextMenu');
  var contextMenuDiv = dojo.byId('dialogDiaryContextMenu');
  event.preventDefault();
  var divDiaryContainer = dojo.byId('detailDiv');
  var scrollX = divDiaryContainer.scrollLeft;
  var mousePosition = {
      x: event.clientX + scrollX, 
      y: event.clientY -80
    };
  if(dojo.byId('isMenuLeftOpen').value == 'true'){
    mousePosition.x -= 250;
  }
  dojo.query('.contextMenuClass').forEach(function(node){
    node.style.cssText='position:absolute;width:0px;height:0px;overflow:hidden;top:'+mousePosition.y+'px;left:'+mousePosition.x+'px';
  });
  if(dojo.byId('contextMenuRefId'))dojo.byId('contextMenuRefId').value = refId;
  if(dojo.byId('contextMenuRefType'))dojo.byId('contextMenuRefType').value = refType;
  
  if(!targetTime){
	if(dojo.byId('addFromDiaryAction')){
	    dojo.byId('addFromDiaryAction').style.display = '';
	    var canCreate = (canCreateArray['Action'] == 'YES')?1:0;
	    dojo.byId('objectClass').value = 'Action';
	    dojo.byId('addFromDiaryAction').setAttribute('onClick', 'addDiaryItem(\'Action\',\''+idResource+'\',\''+targetDate+'\')');
	  }
	  if(dojo.byId('addFromDiaryDelivery')){
	    dojo.byId('addFromDiaryDelivery').style.display = '';
	    var canCreate = (canCreateArray['Delivery'] == 'YES')?1:0;
	    dojo.byId('objectClass').value = 'Delivery';
	    dojo.byId('addFromDiaryDelivery').setAttribute('onClick', 'addDiaryItem(\'Delivery\',\''+idResource+'\',\''+targetDate+'\')');
	  }
  }else{
	dojo.byId('addFromDiaryAction').style.display = 'none';
	dojo.byId('addFromDiaryDelivery').style.display = 'none';
  }
  if(dojo.byId('addFromDiaryMeeting')){
    dojo.byId('addFromDiaryMeeting').style.display = '';
    var canCreate = (canCreateArray['Meeting'] == 'YES')?1:0;
    dojo.byId('objectClass').value = 'Meeting';
    dojo.byId('addFromDiaryMeeting').setAttribute('onClick', 'addDiaryItem(\'Meeting\',\''+idResource+'\',\''+targetDate+'\', \''+targetTime+'\')');
  }else{
	dojo.byId('addFromDiaryMeeting').style.display = 'none';
  }
  if(refType && refId && dojo.byId('editFromDiary')){
    dojo.byId('editFromDiary').style.display = '';
    dojo.byId('editFromDiary').setAttribute('onClick', 'showDetail(null, '+canCreate+', \''+refType+'\', false, '+refId+')');
  }else{
	dojo.byId('editFromDiary').style.display = 'none';
  }
  if(refType && refId && dojo.byId('gotoTimesheetFromDiary')){
      dojo.byId('gotoTimesheetFromDiary').style.display = '';
	  var date = new Date(targetDate);
	  var year = date.getFullYear();
	  var week = date.getWeek();
	  var day = formatDate(date);
	  dojo.byId('gotoTimesheetFromDiary').setAttribute('onClick', 'diaryGotoTimesheet('+idResource+','+year+','+week+',\''+day+'\','+idAssignment+')');
  }else{
	dojo.byId('gotoTimesheetFromDiary').style.display = 'none';
  }
  if(refType && refId && dojo.byId('gotoItemFromDiary')){
	dojo.byId('gotoItemFromDiary_label').innerHTML = i18n('diaryGotoItem', new Array(i18n(refType), refId));
    dojo.byId('gotoItemFromDiary').style.display = '';
	dojo.byId('gotoItemFromDiary').setAttribute('onClick', 'gotoElement(\''+refType+'\','+refId+', true)');
  }else{
	dojo.byId('gotoItemFromDiary').style.display = 'none';
  }
  
  if(refType && refId && dojo.byId('searchInPlanningFromDiary')){
    var plannableTypes = ['Meeting', 'PeriodicMeeting', 'Milestone', 'Activity', 'Project','TestSession'];    
    if(plannableTypes.indexOf(refType) !== -1){
      dojo.byId('searchInPlanningFromDiary').style.display = '';
      dojo.byId('searchInPlanningFromDiary').setAttribute('onClick', 'directSelectProject(\''+refType+'\','+refId+', true, true)');
    }else{
      dojo.byId('searchInPlanningFromDiary').style.display = 'none';
    }
  }else{
    dojo.byId('searchInPlanningFromDiary').style.display = 'none';
  }
  
  contextMenu.openDropDown();
  contextMenuDiv.focus();
}

function changeCreationInfo() {
  toShow=false;
  if (dijit.byId('idUser')) {
    dijit.byId('dialogCreationInfoCreator').set('value',
        dijit.byId('idUser').get('value'));
    dojo.byId('dialogCreationInfoCreatorLine').style.display='inline';
    toShow=true;
  } else if (dojo.byId('idUser')) {
    dijit.byId('dialogCreationInfoCreator').set('value',
        dojo.byId('idUser').value);
    dojo.byId('dialogCreationInfoCreatorLine').style.display='inline';
    toShow=true;
  } else {
    dojo.byId('dialogCreationInfoCreatorLine').style.display='none';
  }

  if (dijit.byId('creationDate')) {
    dijit.byId('dialogCreationInfoDate').set('value',
        dijit.byId('creationDate').get('value'));
    dojo.byId('dialogCreationInfoDateLine').style.display='inline';
    dojo.byId('dialogCreationInfoTimeLine').style.display='none';
    toShow=true;
  } else if (dojo.byId('creationDate')) {
    dijit.byId('dialogCreationInfoDate').set('value',
        dojo.byId('creationDate').value);
    dojo.byId('dialogCreationInfoDateLine').style.display='inline';
    dojo.byId('dialogCreationInfoTimeLine').style.display='none';
    toShow=true;
  } else if (dijit.byId('creationDateTime')) {
    val=dijit.byId('creationDateTime').get('value');
    valDate=val.substr(0, 10);
    valTime='T' + val.substr(11, 8);
    dijit.byId('dialogCreationInfoDate').set('value', valDate);
    dijit.byId('dialogCreationInfoTime').set('value', valTime);
    dojo.byId('dialogCreationInfoDateLine').style.display='inline';
    dojo.byId('dialogCreationInfoTimeLine').style.display='inline';
    toShow=true;
  } else if (dojo.byId('creationDateTime')) {
    val=dojo.byId('creationDateTime').value;
    valDate=val.substr(0, 10);
    valTime=val.substr(11, 8);
    dijit.byId('dialogCreationInfoDate').set('value', valDate);
    dijit.byId('dialogCreationInfoTime').set('value', valTime);
    dojo.byId('dialogCreationInfoDateLine').style.display='inline';
    dojo.byId('dialogCreationInfoTimeLine').style.display='inline';
    toShow=true;
  } else {
    dojo.byId('dialogCreationInfoDateLine').style.display='none';
    dojo.byId('dialogCreationInfoTimeLine').style.display='none';
  }
  if (toShow) {
    dijit.byId('dialogCreationInfo').show();
  }

  if (toShow) {
    dijit.byId('dialogCreationInfo').show();
  }
}

function saveCreationInfo() {
  if (dijit.byId('idUser')) {
    dijit.byId('idUser').set('value',
        dijit.byId('dialogCreationInfoCreator').get('value'));
  } else if (dojo.byId('idUser')) {
    dojo.byId('idUser').value=dijit.byId('dialogCreationInfoCreator').get(
        'value');
  }

  if (dijit.byId('creationDate')) {
    dijit.byId('creationDate').set('value',
        formatDate(dijit.byId('dialogCreationInfoDate').get('value')));
  } else if (dojo.byId('creationDate')) {
    dojo.byId('creationDate').value=formatDate(dijit.byId(
        'dialogCreationInfoDate').get('value'));
  } else {
    if (dijit.byId('creationDateTime')) {
      valDate=formatDate(dijit.byId('dialogCreationInfoDate').get('value'));
      valTime=formatTime(dijit.byId('dialogCreationInfoTime').get('value'));
      val=valDate + ' ' + valTime;
      dijit.byId('creationDateTime').set('value', val);
    } else if (dojo.byId('creationDateTime')) {
      valDate=format(Datedijit.byId('dialogCreationInfoDate').get('value'));
      valTime=format(Datedijit.byId('dialogCreationInfoTime').get('value'));
      val=valDate + ' ' + valTime;
      dojo.byId('dialogCreationInfoDate').value=val;
    }
  }
  formChanged();
  // dojo.byId('buttonDivCreationInfo').innerHTML="";
  // forceRefreshCreationInfo=true;
  saveObject();
  dijit.byId('dialogCreationInfo').hide();
}

function logLevel(value){
  var url='../tool/storeLogLevel.php?value=' + value;
  dojo.xhrPost({
    url : url+addTokenIndexToUrl(),
    handleAs : "text",
    load : function(data, args) {
    }
  });
}

function showLogfile(name) {
  var atEnd=null;
  if (name=='last') {
    atEnd=function(name){
      scrollIndex=0;
      setTimeout("scrollLogFile();",100);
    };
  }
  loadDialog('dialogLogfile', atEnd, true, '&logname='+name, true);
}
var scrollIndex=0;
function scrollLogFile() {
  dojo.query(".logFile .dijitDialogPaneContent").forEach(function(node, index, arr){
    node.scrollTop=parseInt(dojo.byId('logTableContainer').offsetHeight);
  });
  scrollIndex++;
  if (scrollIndex<10) setTimeout("scrollLogFile();",100);
}

function installPlugin(fileName,confirmed) {
  if (! confirmed) {
    actionOK=function() {
      installPlugin(fileName, true);
    };
    msg=i18n('confirmInstallPlugin', new Array(fileName));
    showConfirm(msg,actionOK);
  } else {
    showWait();
    dojo.xhrGet({
      url : "../plugin/loadPlugin.php?pluginFile="
          + encodeURIComponent(fileName)+addTokenIndexToUrl(),
      load : function(data) {
        if (data=="OK") {
          loadContent("pluginManagement.php", "centerDiv");
        } else if (data=="RELOAD") {
          showWait();
          noDisconnect=true;
          quitConfirmed=true;        
          dojo.byId("directAccessPage").value="pluginManagement.php";
          dojo.byId("menuActualStatus").value=menuActualStatus;
          dojo.byId("p1name").value="type";
          dojo.byId("p1value").value=forceRefreshMenu;
          forceRefreshMenu="";
          dojo.byId("directAccessForm").submit();     
        } else if (data.substr(0,8)=="CALLBACK") {
          var url=data.substring(9,data.indexOf('#'));
          window.open(url);
          var msg=data.substring(data.indexOf('#')+1,data.indexOf('##'));
          hideWait();
          callback=function() {loadContent("pluginManagement.php", "centerDiv");};
          showInfo(msg,callback);
          // setTimeout(callback,5000);
        } else {
          hideWait();
          showError(data+'<br/>');
        }
      },
      error : function(data) {
        hideWait();
        showError(data);
      }
    });
  }
}
function deletePlugin(fileName,confirmed) {
  if (! confirmed) {
    actionOK=function() {
      deletePlugin(fileName, true);
    };
    msg=i18n('confirmDeletePluginFile', new Array(fileName));
    showConfirm(msg,actionOK);
  } else {
    showWait();
    dojo.xhrGet({
      url : "../plugin/deletePlugin.php?pluginFile="
          + encodeURIComponent(fileName)+addTokenIndexToUrl(),
      load : function(data) {
        if (data=="OK") {
          loadContent("pluginManagement.php", "centerDiv");
        } else {
          hideWait();
          showError(data+'<br/>');
        }
      },
      error : function(data) {
        hideWait();
        showError(data);
      }
    });
  }
}

function uninstallPlugin(uniqueCode, name, confirmed) {
	  if (! confirmed) {
	    actionOK=function() {
	    	uninstallPlugin(uniqueCode, name, true);
	    };
	    msg=i18n('confirmUninstallPlugin', new Array(name));
	    showConfirm(msg,actionOK);
	  } else {
	    showWait();
	    dojo.xhrGet({
	      url : "../plugin/uninstallPlugin.php?uniqueCode="+ uniqueCode +"&pluginName="+name+addTokenIndexToUrl(),
	      load : function(data) {
	          showWait();
	          noDisconnect=true;
	          quitConfirmed=true;        
	          dojo.byId("directAccessPage").value="pluginManagement.php";
	          dojo.byId("menuActualStatus").value=menuActualStatus;
	          dojo.byId("p1name").value="type";
	          dojo.byId("p1value").value=forceRefreshMenu;
	          forceRefreshMenu="";
	          dojo.byId("directAccessForm").submit();
	      },
	      error : function(data) {
	        hideWait();
	        showError(data);
	      }
	    });
	  }
	}

var historyShowHideWorkStatus=0;
function historyShowHideWork() {
  if (! dojo.byId('objectClass')) {return;}
  historyShowHideWorkStatus=((historyShowHideWorkStatus)?0:1);
  if (dijit.byId('dialogHistory')) {
    dijit.byId('dialogHistory').hide();
  } 
  var callBack = function(){
	showHistory(dojo.byId('objectClass').value);
  };
  saveDataToSession("showWorkHistory", historyShowHideWorkStatus, null, callBack);
}

// ====================================================
// * UPLOAD PLUGIN * //
// ====================================================

function uploadPlugin() {
  if (!isHtml5()) {
    return true;
  }
  if (dojo.byId('pluginFileName').innerHTML == "") {
    return false;
  }
  dojo.style(dojo.byId('downloadProgress'), {
    display : 'block'
  });
  showWait();
  return true;
}

function changePluginFile(list) {
  if (list.length > 0) {
    dojo.byId("pluginFileName").innerHTML=list[0]['name'];
    return true;
  }
}

function savePluginAck(dataArray) {
  if (!isHtml5()) {
    resultFrame=document.getElementById("resultPost");
    resultText=resultPost.document.body.innerHTML;
    dijit.byId('resultDivMain').set('content',resultText);
    savePluginFinalize();
    return;
  }
  if (dojo.isArray(dataArray)) {
    result=dataArray[0];
  } else {
    result=dataArray;
  }
  dojo.style(dojo.byId('downloadProgress'), {
    display : 'none'
  });
  if (dojo.isArray(dataArray)) {
    result=dataArray[0];
  } else {
    result=dataArray;
  }
  dojo.style(dojo.byId('downloadProgress'), {
    display : 'none'
  });
  contentNode = dojo.byId('resultDivMain');
  contentNode.innerHTML=result.message;
  contentNode.style.display="block"; 
  contentNode.style.opacity=1; 
  setTimeout("dojo.byId('resultDivMain').style.display='none';",2000);
  savePluginFinalize();
}
function savePluginFinalize() {
  contentNode = dojo.byId('resultDivMain');
  if (contentNode.innerHTML.indexOf('resultOK')>0) {
    setTimeout('loadContent("pluginManagement.php", "centerDiv");',1000);
  } else {
    hideWait();
  }
}


function showMenuList() {
  clearTimeout(closeMenuListTimeout);
  menuListAutoshow=true;
  clearTimeout(openMenuListTimeout);
  openMenuListTimeout=setTimeout("dijit.byId('menuSelector').loadAndOpenDropDown();",popupOpenDelay);
  
}
function hideMenuList(delay, item) {
  if (! menuListAutoshow) return;
  clearTimeout(closeMenuListTimeout);
  clearTimeout(openMenuListTimeout);
  closeMenuListTimeout=setTimeout("dijit.byId('menuSelector').closeDropDown();",delay);
}

function saveRestrictTypes() {
  callback=function() {
    var fnClBk=function(data) {
      dojo.byId('resctrictedTypeClassList').innerHTML=data;
    };
    dojo.xhrGet({
      url : '../tool/getSingleData.php?dataType=restrictedTypeClass'
        +'&idProject='+dojo.byId('idProjectParam').value
        +'&idProjectType='+dojo.byId('idProjectTypeParam').value
        +'&idProfile='+dojo.byId('idProfile').value+addTokenIndexToUrl(),
      handleAs : "text",
      load : fnClBk
    });
  }
  loadContent("../tool/saveRestrictTypes.php" , "resultDivMain", "restrictTypesForm", true, 'report',false,false, callback);
  dijit.byId('dialogRestrictTypes').hide();
}

function getMaxWidth(document){
  return Math.max( document.scrollWidth, document.offsetWidth, 
      document.clientWidth);
}

function getMaxHeight(document){
  return Math.max( document.scrollHeight, document.offsetHeight, 
      document.clientHeight);
}

function changeParamDashboardTicket(paramToSend){
  loadContent('dashboardTicketMain.php?'+paramToSend, 'centerDiv', 'dashboardTicketMainForm');
}

function changeDashboardTicketMainTabPos(){
  var listChild=dojo.byId('dndDashboardLeftParameters').childNodes[1].childNodes;
  addLeft="";
  iddleList=',"iddleList":[';
  if(listChild.length>1){
    addLeft="[";
    for(var i=1;i<listChild.length;i++){
      getId="";
      if(listChild[i].id.includes('dialogDashboardLeftParametersRow')){
        getId=listChild[i].id.split('dialogDashboardLeftParametersRow')[1];
      }
      if(listChild[i].id.includes('dialogDashboardRightParametersRow')){
        getId=listChild[i].id.split('dialogDashboardRightParametersRow')[1];
      }
      // iddleList+='"'+dijit.byId('dialogTodayParametersIdle'+listChild[i].id.split('dialogDashboardLeftParametersRow')[1]).get('checked')+'"';
      if(getId!=""){
        addLeft+='"'+getId+'"';
        iddleList+='{"name":"'+getId+'","idle":'+dijit.byId('tableauBordTabIdle'+getId).get('checked')+'}';
        if(i+1!=listChild.length){
          addLeft+=',';
          iddleList+=',';
        } 
      }
    }
    addLeft+="]";
    if(dojo.byId('dndDashboardRightParameters').childNodes[0].childNodes.length>1){
      iddleList+=',';
    }
  }
  
  var listChild=dojo.byId('dndDashboardRightParameters').childNodes[0].childNodes;
  addRight="";
  if(listChild.length>1){
    addRight="[";
    for(var i=1;i<listChild.length;i++){
      getId="";
        if(listChild[i].id.includes('dialogDashboardLeftParametersRow')){
          getId=listChild[i].id.split('dialogDashboardLeftParametersRow')[1];
        }
        if(listChild[i].id.includes('dialogDashboardRightParametersRow')){
          getId=listChild[i].id.split('dialogDashboardRightParametersRow')[1];
        }
        // iddleList+='"'+dijit.byId('dialogTodayParametersIdle'+listChild[i].id.split('dialogDashboardLeftParametersRow')[1]).get('checked')+'"';
        if(getId!=""){
          addRight+='"'+getId+'"';
          iddleList+='{"name":"'+getId+'","idle":'+dijit.byId('tableauBordTabIdle'+getId).get('checked')+'}';
          if(i+1!=listChild.length){
            addRight+=',';
            iddleList+=',';
          }
        }
      }
    addRight+="]";
  }
  toSend='{"addLeft":';
  if(addLeft==""){
    addLeft="[]";
  }
  toSend+=addLeft;
  
  toSend+=',"addRight":';
  if(addRight==""){
    addRight="[]";
  }
  iddleList+="]";
  toSend+=addRight+iddleList+"}";
  if (dojo.byId('objectClassManual') && dojo.byId('objectClassManual').value=='DashboardRequirement') {
	  loadContent('dashboardRequirementMain.php?updatePosTab='+toSend, 'centerDiv', 'dashboardRequirementMainForm');
  } else {
	  loadContent('dashboardTicketMain.php?updatePosTab='+toSend, 'centerDiv', 'dashboardTicketMainForm');
  }
}

function changeParamDashboardRequirement(paramToSend){
  loadContent('dashboardRequirementMain.php?'+paramToSend, 'centerDiv', 'dashboardRequirementMainForm');
}

var currentWorkPlanDurationMode = null;
var workPlanDurationChangeInProgress = false;
var workPlanDurationRefreshTimeout = null;
function changeParamWorkPlanDurationMode(paramToSend){
  currentWorkPlanDurationMode = (paramToSend === '') ? null : paramToSend;
  saveDataToSession('workPlanDurationMode', currentWorkPlanDurationMode, false);
  var projectDate = dijit.byId('projectDate').get('checked');
  if(projectDate)return;
  if(currentWorkPlanDurationMode === null){
    refreshJsonWorkPlan(true);
    return;
  }
  var startDate = dijit.byId('startDatePlanView').get('value');
  if(!startDate)return;
  var endDate = new Date(startDate.getTime());
  if(paramToSend == '0'){
    endDate.setDate(endDate.getDate() + 7);
  }else if(paramToSend == '1'){
    endDate = addMonthsToWorkPlanDate(endDate, 1);
  }else if(paramToSend == '2'){
    endDate = addMonthsToWorkPlanDate(endDate, 3);
  }else if(paramToSend == '3'){
    endDate = addMonthsToWorkPlanDate(endDate, 6);
  }else if(paramToSend == '4'){
    endDate.setFullYear(endDate.getFullYear() + 1);
  }
  endDate.setDate(endDate.getDate() - 1);
  workPlanDurationChangeInProgress = true;
  dijit.byId('endDatePlanView').set('value', endDate);
  if(workPlanDurationRefreshTimeout)clearTimeout(workPlanDurationRefreshTimeout);
  workPlanDurationRefreshTimeout = setTimeout(function(){
    workPlanDurationChangeInProgress = false;
    workPlanDurationRefreshTimeout = null;
    refreshJsonWorkPlan(true);
  }, 10);
}

function addMonthsToWorkPlanDate(dateToChange, monthCount){
  var initialDay = dateToChange.getDate();
  dateToChange.setDate(1);
  dateToChange.setMonth(dateToChange.getMonth() + monthCount);
  var lastDayOfMonth = new Date(dateToChange.getFullYear(), dateToChange.getMonth() + 1, 0).getDate();
  dateToChange.setDate(Math.min(initialDay, lastDayOfMonth));
  return dateToChange;
}
var workPlanChangeInProgress=null;
function workPlanChangeSelection(field){
  if(workPlanChangeInProgress)return;
  var resourceField = dijit.byId('selectResourceName');
  var poolField = dijit.byId('selectPoolName');
  var teamField = dijit.byId('teamName');
  var organizationField = dijit.byId('organizationName');
  workPlanChangeInProgress = true;
  if(field == 'selectResourceName' && resourceField.get('value').trim() != ''){
    poolField.set('value', null);
    saveDataToSession('selectPoolName', '', true);
    teamField.set('value', null);
    saveDataToSession('teamName', '', true);
    organizationField.set('value', null);
    saveDataToSession('organizationName', '', true);
  }else if(field == 'selectPoolName' && poolField.get('value').trim() != ''){
    resourceField.set('value', null);
    saveDataToSession('selectResourceName', '', true);
    teamField.set('value', null);
    saveDataToSession('teamName', '', true);
    organizationField.set('value', null);
    saveDataToSession('organizationName', '', true);
  }else if(field == 'teamName' && teamField.get('value').trim() != ''){
    resourceField.set('value', null);
    saveDataToSession('selectResourceName', '', true);
    poolField.set('value', null);
    saveDataToSession('selectPoolName', '', true);
    organizationField.set('value', null);
    saveDataToSession('organizationName', '', true);
  }else if(field == 'organizationName' && organizationField.get('value').trim() != ''){
    resourceField.set('value', null);
    saveDataToSession('selectResourceName', '', true);
    poolField.set('value', null);
    saveDataToSession('selectPoolName', '', true);
    teamField.set('value', null);
    saveDataToSession('teamName', '', true);
  }else{
    resourceField.set('value', null);
    saveDataToSession('selectResourceName', '', true);
    poolField.set('value', null);
    saveDataToSession('selectPoolName', '', true);
    teamField.set('value', null);
    saveDataToSession('teamName', '', true);
    organizationField.set('value', null);
    saveDataToSession('organizationName', '', true);
  }
  setTimeout('workPlanChangeInProgress=false', 10);
}

function getLocalLocation(){
  var availableScaytLocales=["en_US", "en_GB", "pt_BR", "da_DK", "nl_NL", "en_CA", "fi_FI", "fr_FR", "fr_CA", "de_DE", "el_GR", "it_IT", "nb_NO", "pt_PT", "es_ES", "sv_SE"];
  var correspondingLocales= ["en",    "",      "pt-br", "",      "nl",    "",      "",      "fr",    "fr-ca", "de",    "el",    "it",    "",      "pt",    "es",    ""];
  var locale=dojo.locale;
  if (currentLocale) {
    var pos=correspondingLocales.indexOf(currentLocale);
    if (pos>=0) {
      locale=availableScaytLocales[pos];
    }
  }
  return locale;
}
function getLocalScaytAutoStartup() {
  if (typeof scaytAutoStartup == "undefined" || scaytAutoStartup===null || scaytAutoStartup==='' || scaytAutoStartup=='YES' || scaytAutoStartup===true) {
    return true;
  } else {
    return scaytAutoStartup;
  }
}

// =============================================================================
// = JobDefinition
// =============================================================================

/**
 * Display a add line Box
 * 
 */
function addJobDefinition(checkId) {
  var params="&checkId=" + checkId;
  loadDialog('dialogJobDefinition', null, true, params);
}

/**
 * Display a edit line Box
 * 
 */
function editJobDefinition(checkId, lineId) {
  var params="&checkId=" + checkId + "&lineId=" + lineId;
  loadDialog('dialogJobDefinition', null, true, params);
}

/**
 * save a line (after addDetail or editDetail)
 * 
 */
function saveJobDefinition() {
  if (!dijit.byId("dialogJobDefinitionName").get('value')) {
    showAlert(i18n('messageMandatory', new Array(i18n('colName'))));
    return false;
  }
  loadContent("../tool/saveJobDefinition.php", "resultDivMain",
      "dialogJobDefinitionForm", true, 'jobDefinition');
  dijit.byId('dialogJobDefinition').hide();

}

/**
 * Display a delete line Box
 * 
 */
function removeJobDefinition(lineId) {
  var params="?lineId=" + lineId;
  // loadDialog('dialogJobDefinition',null, true, params)
  // dojo.byId("jobDefinitionId").value=lineId;
  actionOK=function() {
    loadContent("../tool/removeJobDefinition.php" + params,
        "resultDivMain", null, true, 'jobDefinition');
  };
  msg=i18n('confirmDelete', new Array(i18n('JobDefinition'), lineId));
  showConfirm(msg, actionOK);
}

// =============================================================================
// = Joblist
// =============================================================================

function showJoblist(objectClass) {
  if (!objectClass) {
    return;
  }
  if (dijit.byId('id')) {
    var objectId=dijit.byId('id').get('value');
  } else {
    return;
  }
  var params="&objectClass=" + objectClass + "&objectId=" + objectId;
  loadDialog('dialogJoblist', null, true, params, true);
}

function saveJoblist() {
  // var params="&objectClass="+objectClass+"&objectId="+objectId;
  // loadDialog('dialogJoblist',null, true, params);
  loadContent('../tool/saveJoblist.php', 'resultDivMain', 'dialogJoblistForm',
      true, 'joblist');
  dijit.byId('dialogJoblist').hide();
  return false;
}

function jobClick(line) {
  jobName="check_" + line;
  if (dijit.byId(jobName).get('checked') && dijit.byId("check_" + line)) {
    dijit.byId("check_" + line).set('checked', false);
  }
}

function changeJobInfo(jobId) {
  toShow=false;
  if(dijit.byId('dialogJobInfoJobId')) {
    dijit.byId('dialogJobInfoJobId').set('value', jobId);
  } else if (dijit.byId('dialogJobInfoJobId')) {
    dojo.byId('dialogJobInfoJobId').value = jobId;
  }

  if (dijit.byId('job_'+jobId+'_idUser')) {
    dijit.byId('dialogJobInfoCreator').set('value',
        dijit.byId('job_'+jobId+'_idUser').get('value'));
    dojo.byId('dialogJobInfoCreatorLine').style.display='inline';
    toShow=true;
  } else if (dojo.byId('job_'+jobId+'_idUser')) {
    dijit.byId('dialogJobInfoCreator').set('value',
        dojo.byId('job_'+jobId+'_idUser').value);
    dojo.byId('dialogJobInfoCreatorLine').style.display='inline';
    toShow=true;
  } else {
    dojo.byId('dialogJobInfoCreatorLine').style.display='none';
  }

  if (dijit.byId('job_'+jobId+'_creationDate')) {
    if(dijit.byId('job_'+jobId+'_creationDate').get('value') != '') {
      dijit.byId('dialogJobInfoDate').set('value', dijit.byId('job_'+jobId+'_creationDate').get('value'));
    }
    dojo.byId('dialogJobInfoDateLine').style.display='inline';
    toShow=true;
  } else if (dojo.byId('job_'+jobId+'_creationDate')) {
    if(dojo.byId('job_'+jobId+'_creationDate').value != '') {
      dojo.byId('dialogJobInfoDate').set('value', dojo.byId('job_'+jobId+'_creationDate').value);
    }
    dojo.byId('dialogJobInfoDateLine').style.display='inline';
    toShow=true;
  } else {
    dojo.byId('dialogJobInfoDateLine').style.display='none';
  }

  if (toShow) {
    dijit.byId('dialogJobInfo').show();
  }
}

function saveJobInfo() {
  if(dijit.byId('dialogJobInfoJobId')) {
    jobId = dijit.byId('dialogJobInfoJobId').get('value');
  } else if (dijit.byId('dialogJobInfoJobId')) {
    jobId = dijit.byId('dialogJobInfoJobId').get('value');
  }
  if(jobId) {
    if (dijit.byId('job_'+jobId+'_idUser')) {
      dijit.byId('job_'+jobId+'_idUser').set('value',
        dijit.byId('dialogJobInfoCreator').get('value'));
    } else if (dojo.byId('job_'+jobId+'_idUser')) {
      dojo.byId('job_'+jobId+'_idUser').value = dijit.byId('dialogJobInfoCreator').get(
          'value');
    }

    if(dijit.byId('dialogJobInfoDate').get('value') != '') {
        if (dijit.byId('job_'+jobId+'_creationDate')) {
            dijit.byId('job_'+jobId+'_creationDate').set('value',
              formatDate(dijit.byId('dialogJobInfoDate').get('value')));
        } else if (dojo.byId('job_'+jobId+'_creationDate')) {
            dojo.byId('job_'+jobId+'_creationDate').value = formatDate(dijit.byId(
              'dialogJobInfoDate').get('value'));
        }
    }
    formChanged();
    // To implement if we want to hide before reload after save
    /* dojo.byId('buttonDivCreationInfo').innerHTML=""; */
    forceRefreshJobInfo=true;
    saveObject();
    dijit.byId('dialogJobInfo').hide();
  }
}

function toggleFullScreen() {
  if ((document.fullScreenElement && document.fullScreenElement !== null) ||    
   (!document.mozFullScreen && !document.webkitIsFullScreen)) {
    enterFullScreen();
  } else { 
    exitFullScreen();
  }
  dijit.byId("iconMenuUserScreen").closeDropDown();
}
function enterFullScreen() {
  if (document.documentElement.requestFullScreen) {
    document.documentElement.requestFullScreen();  
  } else if (document.documentElement.mozRequestFullScreen) {  
    document.documentElement.mozRequestFullScreen();  
  } else if (document.documentElement.webkitRequestFullScreen) {  
    document.documentElement.webkitRequestFullScreen(Element.ALLOW_KEYBOARD_INPUT);  
  }
}
function exitFullScreen() {
  if (document.cancelFullScreen ) {
    document.cancelFullScreen(); 
  } else if (document.mozCancelFullScreen) {  
    document.mozCancelFullScreen(); 
  } else if (document.webkitCancelFullScreen) {  
    document.webkitCancelFullScreen(); 
  }
}
function fullTab(){
  if (menuLeft.prototype.isMenuOpen=='false'){
    menuLeft.prototype._closeMenu();
    setTimeout('menuLeft.prototype._openMenu();',200);
  }else{
    menuLeft.prototype._openMenu();
    setTimeout('menuLeft.prototype._closeMenu();',200);
  }
}
/**
 * Subscription
 * 
 */
function subscribeToItem(objectClass, objectId, userId) {
    if (! objectId && dojo.byId('id')) objectId=dojo.byId('id').value;
    var url="../tool/saveSubscription.php?mode=on";
    url+="&objectClass="+objectClass;
    url+="&objectId="+objectId;
    url+="&userId="+userId;
  dojo.xhrGet({
    url : url+addTokenIndexToUrl(),
    handleAs : "text",
    load : function(data) {
      var result="KO";
      var itemLabel="";
      var response=JSON.parse(data);
      if (response.hasOwnProperty('result')) result=response.result;
      if (response.hasOwnProperty('itemLabel')) itemLabel=response.itemLabel;
      if (result=='OK') {
        addMessage(i18n('subscriptionSuccess',new Array(itemLabel)));
        dijit.byId('subscribeButton').set('iconClass','dijitButtonIcon dijitButtonIconSubscribeValid');
        enableWidget('subscribeButtonUnsubscribe');
        disableWidget('subscribeButtonSubscribe');
      } else {
        showError(i18n('subscriptionFailed'));
      }
    },
    error : function() {
      showError(i18n('subscriptionFailed'));
    }
  });
}

function unsubscribeFromItem(objectClass, objectId, userId) {
  if (! objectId && dojo.byId('id')) objectId=dojo.byId('id').value;
  var url="../tool/saveSubscription.php?mode=off";
  url+="&objectClass="+objectClass;
  url+="&objectId="+objectId;
  url+="&userId="+userId;
  dojo.xhrGet({
    url : url+addTokenIndexToUrl(),
    handleAs : "text",
    load : function(data) {
      var result="KO";
      var itemLabel="";
      var message="";
      var response=JSON.parse(data);
      if (response.hasOwnProperty('result')) result=response.result;
      if (response.hasOwnProperty('itemLabel')) itemLabel=response.itemLabel;
      if (response.hasOwnProperty('message')) message=response.message;
      if (result=='OK') {
        addMessage(i18n('unsubscriptionSuccess',new Array(itemLabel)));
        dijit.byId('subscribeButton').set('iconClass','dijitButtonIcon dijitButtonIconSubscribe');
        enableWidget('subscribeButtonSubscribe');
        disableWidget('subscribeButtonUnsubscribe');
      } else {
        showError(i18n('subscriptionFailed')+'<br/>'+message);
      }
    },
    error : function() {
      showError(i18n('subscriptionFailed'));
    }
  });
}

function subscribeForOthers(objectClass, objectId) {
  if (! objectId && dojo.byId('id')) objectId=dojo.byId('id').value;
  loadDialog('dialogSubscriptionForOthers',null,true,'&objectClass='+objectClass+'&objectId='+objectId,true);
}
function showSubscribersList(objectClass, objectId) {
  if (! objectId && dojo.byId('id')) objectId=dojo.byId('id').value;
  loadDialog('dialogSubscribersList',null,true,'&objectClass='+objectClass+'&objectId='+objectId,true);
}

function showSubscriptionList(userId) {
  loadDialog('dialogSubscriptionList',null,true,'&userId='+userId,true);
}

function changeSubscriptionFromDialog(mode,dialog,objectClass,objectId,userId,key,currentUserId) {
  if (! objectId && dojo.byId('id')) objectId=dojo.byId('id').value;
  var url="../tool/saveSubscription.php?mode="+mode;
  url+="&objectClass="+objectClass;
  url+="&objectId="+objectId;
  url+="&userId="+userId;
  dojo.xhrGet({
    url : url+addTokenIndexToUrl(),
    handleAs : "text",
    load : function(data) {
      var result="KO";
      var itemLabel="";
      var message="";
      var userName="";
      var userId="";
      var currentUserId="";
      var objectClass="";
      var objectId="";
      var response=JSON.parse(data);
      if (response.hasOwnProperty('result')) result=response.result;
      if (response.hasOwnProperty('itemLabel')) itemLabel=response.itemLabel;
      if (response.hasOwnProperty('userName')) userName=response.userName;
      if (response.hasOwnProperty('userId')) userId=response.userId;
      if (response.hasOwnProperty('currentUserId')) currentUserId=response.currentUserId;
      if (response.hasOwnProperty('objectClass')) objectClass=response.objectClass;
      if (response.hasOwnProperty('objectId')) objectId=response.objectId;
      if (response.hasOwnProperty('message'))  message=response.message;
      if (result=='OK') {
        if (dialog=='list') {
          addMessage(i18n('unsubscriptionSuccess',new Array(itemLabel)));
        } else if (dialog=='other') {
          if (mode=='on') {
            addMessage(i18n('subscriptionSuccess',new Array(userName)));
          } else {
            addMessage(i18n('unsubscriptionSuccess',new Array(userName)));
          }
        }
        if (key) {
          if (mode=='on') {
            dojo.byId('subscribtionButton'+key).style.display="none";
            dojo.byId('unsubscribtionButton'+key).style.display="inline-block";
          } else {
            dojo.byId('unsubscribtionButton'+key).style.display="none";
            dojo.byId('subscribtionButton'+key).style.display="inline-block";
          }
        }
        if (userId && currentUserId && userId==currentUserId && objectClass && objectId) {
          if (dojo.byId('objectClass') && objectClass==dojo.byId('objectClass').value && dojo.byId('objectId') && parseInt(objectId)==parseInt(dojo.byId('objectId').value)) {
            if (mode=='on') {
              if (dijit.byId('subscribeButton')) dijit.byId('subscribeButton').set('iconClass','dijitButtonIcon dijitButtonIconSubscribeValid');
              enableWidget('subscribeButtonUnsubscribe');
              disableWidget('subscribeButtonSubscribe');
            } else {
              if (dijit.byId('subscribeButton')) dijit.byId('subscribeButton').set('iconClass','dijitButtonIcon dijitButtonIconSubscribe');
              enableWidget('subscribeButtonSubscribe');
              disableWidget('subscribeButtonUnsubscribe');
            }
          }
        }
      } else {
        showError(i18n('subscriptionFailed')+'<br/>'+message);
      }
    },
    error : function() {
      showError(i18n('subscriptionFailed'));
    }
  });
}

function filterDnDList(search,list) {
  var searchVal=dojo.byId(search).value;
  searchVal=searchVal.replace(/\*/gi,'.*');
  var pattern = new RegExp(searchVal, 'i');
  dojo.map(dojo.byId(list).children, function(child){
    if (searchVal!='' && ! pattern.test(child.getAttribute('value')) ) {
      child.style.display="none";
    } else if (dojo.hasClass(child,'raciPerson')) {
      child.style.display="flex";
    } else {
      child.style.display="block";
    }
  });
}

function filterDnDListLayout(search,list) {
  var searchVal=dojo.byId(search).value;
  if(list=='layoutAvailable'){
    dojo.byId('iconSearchLayout').style.display="none";
    dojo.byId('iconCancelLayout').style.display="block";
  }
  searchVal=searchVal.replace(/\*/gi,'.*');
  var pattern = new RegExp(searchVal, 'i');
  dojo.map(dojo.byId(list).children, function(child){
    if (searchVal!='' && ! pattern.test(child.getAttribute('value')) ) {
      child.style.display="none";
    } else {
      child.style.display="block";
    }
  });
}

function clearFilterDnDListLayout() {
    dojo.byId('iconSearchLayout').style.display="block";
    dojo.byId('iconCancelLayout').style.display="none";
    dojo.map(dojo.byId('layoutAvailable').children, function(child){
      child.style.display="block";
    });
    dojo.byId('layoutAvailableSearch').value="";
}


var arrayPaneSize=[];
function storePaneSize(paneName,sizeValue) {
  if (arrayPaneSize[paneName] && arrayPaneSize[paneName]==sizeValue) {
    return;
  }
  arrayPaneSize[paneName]=sizeValue;
  saveDataToSession(paneName, sizeValue, true);
}

function displayMenu(id){
  if(hideUnderMenuId){
    if (hideUnderMenuId == id ){
      clearTimeout(hideUnderMenuTimeout);
      hideUnderMenuId=null;
    }else{
      hideUnderMenu(hideUnderMenuId);
    }
  }
  dojo.byId('UnderMenu'+id).style.zIndex="999999";
  dojo.byId('UnderMenu'+id).style.display="block";
  setTimeout("repositionMenuDiv("+id+","+id+");",10);
}

function displayUnderMenu(id,idParent){
  if (hideUnderMenuId==null && previewhideUnderMenuId!=null){
    hideUnderMenu(previewhideUnderMenuId,0);
  }
  else 
    if(hideUnderMenuId){
      if (hideUnderMenuId == id ){
        dojo.byId('UnderMenu'+id).style.display="none";
        clearTimeout(hideUnderMenuTimeout);
      }else{
        hideUnderMenu(hideUnderMenuId);
      }
    }
    dojo.byId('UnderMenu'+id).style.display="block";
    setTimeout("repositionMenuDiv("+id+","+idParent+");",10);
  // Florent
    previewhideUnderMenuId=id;
}

function repositionMenuDiv(id,idParent) {
  var parentDiv=dojo.byId('Menu'+idParent);
  var currentDiv=dojo.byId('UnderMenu'+id);
  var top = parentDiv.offsetTop;
  var totalHeight = dojo.byId('centerDiv').offsetHeight;
  currentDiv.style.maxHeight=(totalHeight-50)+'px';
  var height = currentDiv.offsetHeight;
  if(id==152 && top + height > totalHeight - 45){
    newTop = totalHeight - (top + height) - 10 ; 
    currentDiv.style.top = newTop+'px';
  }
  if (top + height > totalHeight - 30){
    newTop = totalHeight - (top + height) - 10 ; 
    currentDiv.style.top = newTop+'px';
  };
}

function hideMenu(id,delay){
  if(! delay){ 
    delay=300;
  }
  if(hideUnderMenuTimeout){
    clearTimeout(hideUnderMenuTimeout);
  }  
  hideUnderMenuId = id;
  hideUnderMenuTimeout=setTimeout("hideUnderMenu("+id+")",delay);
}

function hideUnderMenu(id){
  dojo.query(".hideUndermenu"+id+".dijitAccordionTitle2.reportTableColumnHeader2.largeReportHeader2").forEach(function(node, index, nodelist) {
    node.style.display="none";
   });
  dojo.byId('UnderMenu'+id).style.display="none";
  hideUnderMenuId = null;
}

function hidePreviewUnderMenu(id){
  if(previewhideUnderMenuId!=id && previewhideUnderMenuId!=null){
    hideUnderMenu(previewhideUnderMenuId);
  }
}
// end
function displayListOfApprover(id){
  var params="&objectId=" + id;
  loadDialog('dialogListApprover', null, true,params,null,true);
}

function readNotification(id){
  var url='../view/menuNotificationRead.php?id=' + id;
  dojo.xhrPost({
    url : url+addTokenIndexToUrl(),
    handleAs : "text",
    load : function(data, args) {
      var objClass = 'objectClass';
      try {
        objClass = dojo.byId('objectClass').value;
      } catch(e) {
        objClass = 'Other';
      }
      if (objClass == 'Notification'){
        loadContent("objectMain.php?objectClass="+objClass,"centerDiv");
      }
        refreshNotificationTree(false);
        loadContent("../view/menuNotificationRead.php", "drawNotificationUnread");
    }
  });
}

function readNotificationAndHide(id) {
  var url = '../view/menuNotificationRead.php?id=' + id + '&inline=1'; 
  dojo.xhrPost({
    url: url + addTokenIndexToUrl(),
    handleAs: "json",
    load: function(data, args) {
		var objClass = 'objectClass';
		try {
		  objClass = dojo.byId('objectClass').value;
		} catch(e) {
		  objClass = 'Other';
		}
		if (objClass == 'Notification'){
		  loadContent("objectMain.php?objectClass="+objClass,"centerDiv");
		}
        var notifDiv = dojo.byId('notif_' + id);
        if (notifDiv) {
          notifDiv.style.opacity = '0';
          setTimeout(function() {
            if (notifDiv.parentNode) {
              notifDiv.parentNode.removeChild(notifDiv);
            }
            checkAndClosePopupIfEmpty();
          }, 300);
        }        
      
    },
    error: function(error) {
            console.error('Error readNotificationAndHide:', error);
    }
  });
}

function checkAndClosePopupIfEmpty() {
  var visibleNotifs = dojo.query('.notification-item').length; 
  updateNotificationCounter(visibleNotifs);  
  if (visibleNotifs === 0) {
    var popup = dojo.byId('notificationPopup') || dojo.byId('notification-popup');
    if (popup) popup.style.display = 'none';
	  refreshNotificationTree(false);
  }
}

function updateNotificationCounter(count) {
    var countElement = document.getElementById("countNotifications");
    if (countElement) {
        countElement.innerHTML = count;
        
        if (count == 0) {
            countElement.style.visibility = "hidden";
        } else {
            countElement.style.visibility = "visible";
            if (document.getElementById("notificationTree")) {
                document.getElementById("notificationTree").style.visibility = "visible";
            }
            if (document.getElementById("menuBarNotificationCount")) {
                document.getElementById("menuBarNotificationCount").style.visibility = "visible";
            }
            if (document.getElementById("drawNotificationUnread")) {
                document.getElementById("drawNotificationUnread").style.visibility = "visible";
            }
        }
    }
}

// MTY - GENERIC DAY OFF
function addGenericBankOffDays(idCalendarDefinition) {
    if (checkFormChangeInProgress()) {
      showAlert(i18n('alertOngoingChange'));
      return;
    }

    var params="&idGenericBankOffDays=0";
    params += "&idCalendarDefinition="+idCalendarDefinition;
    params += "&addMode=true&editMode=false";
    
    loadDialog('dialogGenericBankOffDays',null,true,params,true);        
}

function editGenericBankOffDays(idGenericBankOffDays,
                                idCalendarDefinition,
                                name,
                                month,
                                day,
                                easterDay
                                ) {
    if (checkFormChangeInProgress()) {
      showAlert(i18n('alertOngoingChange'));
      return;
    }
    var params = "&idGenericBankOffDays="+idGenericBankOffDays;
    params+="&idCalendarDefinition="+idCalendarDefinition;
    params+="&name="+name;
    params+="&month="+month;
    params+="&day="+day;
    params+="&easterDay="+easterDay;
    params +="&addMode=false&editMode=true";
    loadDialog('dialogGenericBankOffDays',null,true,params,true);    
}

function saveGenericBankOffDays() {
  var formVar=dijit.byId('genericBankOffDaysForm');
  if (formVar.validate()) {
    loadContent("../tool/saveGenericBankOffDays.php", "resultDivMain", "genericBankOffDaysForm", true, 'calendarBankOffDays');
    dijit.byId('dialogGenericBankOffDays').hide();
  } else {
    showAlert(i18n("alertInvalidForm"));
  }
}

function removeGenericBankOffDays(id, name) {
    if (checkFormChangeInProgress()) {
        showAlert(i18n('alertOngoingChange'));
        return;
    }
    actionOK=function() {
        loadContent("../tool/removeGenericBankOffDay.php?idBankOffDay="+id, "resultDivMain", null, true, 'calendarBankOffDays');
    };
    msg=i18n('confirmDeleteGenericBankOffDay', new Array(name));
    showConfirm(msg, actionOK);
}
// MTY - GENERIC DAY OFF

function showDialogAutoSendReport(){
	setTimeout(loadDialog('dialogAutoSendReport',null,true,null,true), 200);
}

function saveAutoSendReport(){
	var formVar=dijit.byId('autoSendReportForm');
	  if (dijit.byId('destinationInput').get('value') == '' && dijit.byId('otherDestinationInput').get('value') == '') {
	      showAlert(i18n("errorNoReceivers"));
	      return;
	  }
	  if (formVar.validate()) {
		  loadContent("../tool/saveAutoSendReport.php", "resultDivMain", "autoSendReportForm", true, "report");
		  dijit.byId('dialogAutoSendReport').hide();
	  } else {
	    showAlert(i18n("alertInvalidForm"));
	  }
}

function refreshRadioButtonDiv(){
	loadContent("../tool/refreshButtonAutoSendReport.php", "radioButtonDiv", "autoSendReportForm");
}
		  
function saveModuleStatus(id,status) {
  if (id==12 && (status==false || status=='false')) {
      actionOK = function () {
        adminDisconnectAll(false);
        saveModuleStatusContinue(id,status);
      };
      actionKO = function () {
          dijit.byId("module_12").set("checked",true);
      };
      msg=i18n("thisActionWillDeleteAllsLeavesSystemElements")+"<br/><br/>"+i18n("AreYouSure")+" ?";
      showQuestion(msg, actionOK, actionKO);
  } else {
    saveModuleStatusContinue(id,status);
  }
}   

function saveModuleStatusContinue(id,status) {
  var url='../tool/saveModuleStatus.php?idModule='+id+'&status='+status;
  dojo.xhrGet({
    url : url+addTokenIndexToUrl(),
    handleAs : "text",
    load : function(){
    }
  });
  dojo.query(".moduleClass.parentModule"+id).forEach(function(domNode){
    var name=domNode.getAttribute('widgetid');
    var widget=dijit.byId(name);
    if (widget) {
      var idSub=name.replace('module_','');
      var parentActive=dojo.byId('parentActive_'+idSub).value;
      if((parentActive==1 && status==true) || status==false){
        widget.set('checked',(status==true)?true:false);
        var url='../tool/saveModuleStatus.php?idModule='+idSub+'&status='+status;
        dojo.xhrGet({
          url : url+addTokenIndexToUrl(),
          handleAs : "text",
          load : function(){
          }
        });
      }
    }
  });
  saveModuleStatusCheckParent(id);  
}

function saveModuleStatusCheckParent(id) {
  var wdgt=dijit.byId('module_'+id);
  var parent=wdgt.get('parent');
  var notActiveAlone=(dojo.byId('notActiveAlone_'+parent))?dojo.byId('notActiveAlone_'+parent).value:false;
  if (dojo.byId('module_'+parent)) {
    var oneOn=false;
    var allOff=true;
    dojo.query(".moduleClass.parentModule"+parent).forEach(function(domNode){
      var name=domNode.getAttribute('widgetid');
      var widget=dijit.byId(name);
      if (widget) {
        if (widget.get('checked')==true) {
          allOff=false;
          oneOn=true;
        }
      }
    });
    var status=(oneOn==true)?true:false;
    var widget=dijit.byId('module_'+parent);
    if (widget.get('checked')!=status && ((notActiveAlone=='1' && status==false) || status==true)) {
      widget.set('checked',status);
      var url='../tool/saveModuleStatus.php?idModule='+parent+'&status='+status;
      dojo.xhrGet({
        url : url+addTokenIndexToUrl(),
        handleAs : "text",
        load : function(){         
        }
      });
    }
  }
}

function controlChar (){
  var requiredLength=dojo.byId('paramPwdLth').value;
  var gen= new RegExp(["^(?=.*[a-zA-Z0-9!@#$&()-`.+,/\"])"]);
  var min =new RegExp([ "^(?=.*[a-z])"]);
  var maj =new RegExp([ "^(?=.*[A-Z])"]);
  var num=new RegExp(["^(?=.*[0-9])"]);
  //var char=new RegExp("(\?\=\.\*\[\@\#\$\%\^\&\\\/\~\"\'\])");
  var char=new RegExp(/[!@#$%^&*(),.?":;{}|<>~'Â°\=\+â‚¬Â£_\\\/|Â§\{\}\[\]\-]/);
  var progress=dojo.byId('progress');
  var value=0;
  var curpwd=dojo.byId('dojox_form__NewPWBox_0').value;
  addVal=[0,0,0,0];
  if (curpwd.length>=requiredLength) {
    addVal[0]=1;
    value+=1; 
  }
  if( min.test(curpwd) && maj.test(curpwd) ){
    addVal[1]=1;
    value+=1;    
  }
  if(num.test(curpwd)){
    addVal[2]=1;
    if (min.test(curpwd) || maj.test(curpwd) ) value+=1;
  } 
  if(char.test(curpwd)){
    addVal[3]=1;
    if (min.test(curpwd) || maj.test(curpwd) ) value+=1;
  }
  progress.value=value;
  var strength=dojo.byId('parmPwdSth').value;
  var enough=false;
  var msg=i18n('pwdRequiredStrength');
  if(strength==1){
    if (addVal[0]==1) enough=true;
  }else if(strength==2){
    if (addVal[0]==1 && addVal[1]==1) enough=true;
  }else if(strength==3){
    if (addVal[0]==1 && addVal[1]==1 && addVal[2]==1) enough=true; 
  }else if(strength==4){
    if (addVal[0]==1 && addVal[1]==1 && addVal[2]==1 && addVal[3]==1) enough=true;
  }
  if (addVal[0]==0 && strength>=1) msg+='<br/>&nbsp;-&nbsp;'+i18n("pwdErrorLength",[requiredLength]);
  if (addVal[1]==0 && strength>=2) msg+='<br/>&nbsp;-&nbsp;'+i18n("pwdErrorCase");
  if (addVal[2]==0 && strength>=3) msg+='<br/>&nbsp;-&nbsp;'+i18n("pwdErrorDijit");
  if (addVal[3]==0 && strength>=4) msg+='<br/>&nbsp;-&nbsp;'+i18n("pwdErrorChar");
  var strengthMsg=document.getElementById('strength');
  dojo.byId('passwordValidate').value=(enough)?'true':'false';
  dojo.byId('criteria').value=msg;
  require(["dijit/Tooltip", "dojo/domReady!"], function(Tooltip) {
    var node = dojo.byId('dojox_form__NewPWBox_0');
    if (enough) {
      Tooltip.hide(node);
      strengthMsg.innerHTML=i18n('pwdValidStrength');
      strengthMsg.style="color:green;";
    } else {      
      Tooltip.show(msg, node);
      strengthMsg.innerHTML=i18n('pwdInvalidStrength');
      strengthMsg.style="color:red;";
    }
  });
}

function refreshDataCloningCountDiv(userSelected){
	loadContent("../tool/refreshDataCloningCountDiv.php?userSelected="+userSelected+'&destinationWidth='+dojo.byId('listDiv').offsetWidth, "labelDataCloningCountDiv", "addDataCloningForm");
}

function saveContact(idFldVal,comboClass){
  var addVal=dojo.byId('objectId').value;
  var obj=dojo.byId('objectClass').value;
  var parm="operation=add&objectClass="+comboClass+"&listId="+idFldVal+"&class="+obj+"&addVal="+addVal;
  loadContent("../tool/saveContact.php?"+parm, "resultDivMain",null,true,"contact"+dojo.byId('objectClass'));
}

function removeContact(idFldVal){
  var obj=dojo.byId('objectClass').value;
  var parm="operation=remove&objectClass=Contact&objectId="+idFldVal+"&class="+obj;
  actionOK=function() {
    loadContent("../tool/removeContact.php?"+parm, "resultDivMain",null,true,"contact"+dojo.byId('objectClass'));
  };
  msg=i18n('confirmDissociate', new Array(i18n('Contact'),idFldVal));
  showConfirm(msg, actionOK);
}
// End

var currentSelectedModuleMenu=null;
function showDisplayModule(id,total){
  if(dojo.byId("displayModule"+id).style.display=="block"){
      dojo.byId("moduleTitle_"+id).style.width=260+'px';
      dojo.byId("displayModule"+id).style.display="none";
  }else{
    for (var i=1; i <= total; i++) {
      if(dojo.byId("moduleTitle_"+i)){
        if(dojo.byId("moduleTitle_"+i).style.width==290+'px'){
          dojo.byId("moduleTitle_"+i).style.width=260+'px';
        }
      }
      if(dojo.byId("displayModule"+i)){
        if(dojo.byId("displayModule"+i).style.display=="block"){
          dojo.byId("displayModule"+i).style.display="none";
          dojo.byId("displayModule"+i).style.visibility = 'hidden';
          dojo.byId("displayModule"+i).style.opacity = 0;
        }
      }
    }
    if(dojo.byId("displayModule"+id)){
      currentSelectedModuleMenu=id;
      dojo.byId("displayModule"+id).style.display="block";
      dojo.byId("displayModule"+id).style.visibility="visible";
      dojo.byId("displayModule"+id).style.opacity=1;
      positionTopForCurrentSelectedModule(id);  
    }
    dojo.byId("moduleTitle_"+id).style.width=290+'px';
  }
}
function positionTopForCurrentSelectedModule(id) {
  if (!id) id=currentSelectedModuleMenu;
  if (!id) return;
  if (!dojo.byId("displayModule"+id)) return;
  dojo.byId("displayModule"+id).style.top=dojo.byId("moduleMenuDiv_"+id).offsetTop+"px";
  actualTop=dojo.byId("displayModule"+id).offsetTop;
  scroll=dojo.byId("detailDiv").scrollTop;
  position=actualTop - scroll;
  height=dojo.byId("displayModule"+id).offsetHeight;
  containerHeight=dojo.byId("detailDiv").offsetHeight;
  border=5;
  if (actualTop<scroll) {
    dojo.byId("displayModule"+id).style.top=scroll+"px";
  } else if (position+height+border>containerHeight ) {
    newTop=actualTop-(position+height+border)+containerHeight;
    if (newTop<scroll) newTop=scroll;
    dojo.byId("displayModule"+id).style.top=newTop+"px";
  }
}

function filterMenuModule(id,nbTotal){
  var reset = 0;
  for (var i=1; i <= 7; i++) {
    if(dojo.hasClass(dojo.byId("menuFilterModuleTop"+i),'menuBarItemSelectedModule')){
      if(id==i){
        reset = 1;
      }
      dojo.removeClass(dojo.byId("menuFilterModuleTop"+i),"menuBarItemSelectedModule");
      dojo.removeClass(dojo.byId("menuFilterModuleTopIcon"+i),"menuFilterModuleTopIcon");
    }
  }
  if(reset==0){
    dojo.addClass(dojo.byId("menuFilterModuleTop"+id),"menuBarItemSelectedModule");
    dojo.addClass(dojo.byId("menuFilterModuleTopIcon"+id),"menuFilterModuleTopIcon");
  }else{
    id=1;
    dojo.addClass(dojo.byId("menuFilterModuleTop"+id),"menuBarItemSelectedModule");
    dojo.addClass(dojo.byId("menuFilterModuleTopIcon"+id),"menuFilterModuleTopIcon");
  }
  
  if(id==2){
    var tab = [1,9,16,22];
  }else if(id==3){
    var tab = [2,16];
  }else if(id==4){
    var tab = [4,8,9,10];
  }else if(id==5){
    var tab = [5,6,7,19,20];
  }else if(id==6){
    var tab = [17,13,15];
  }
  for (var i=1; i <= nbTotal; i++) {
    if(id==1){
      if(dojo.byId("moduleMenuDiv_"+i)){
        dojo.byId("moduleMenuDiv_"+i).style.display="block";
      }
    }else{
      if(dojo.byId("moduleMenuDiv_"+i)){
        if(tab.indexOf(i) !== -1){
          dojo.byId("moduleMenuDiv_"+i).style.display="block";
        }else{
          dojo.byId("moduleMenuDiv_"+i).style.display="none";
          if(dojo.byId("displayModule"+i).style.display=="block"){
            dojo.byId("displayModule"+i).style.display="none";
            dojo.byId("moduleTitle_"+i).style.width=260+'px';
          }
        }
      }
    }
  }
}

function filterMenuModuleDisable(nbTotal){
  for (var i=1; i <= 6; i++) {
    if(dojo.hasClass(dojo.byId("menuFilterModuleTop"+i),'menuBarItemSelectedModule')){
      dojo.removeClass(dojo.byId("menuFilterModuleTop"+i),"menuBarItemSelectedModule");
      dojo.removeClass(dojo.byId("menuFilterModuleTopIcon"+i),"menuFilterModuleTopIcon");
    }
  }
  var reset = 0;
  if(dojo.hasClass(dojo.byId("menuFilterModuleTop7"),'menuBarItemSelectedModule')){
    reset = 1;
  }
  if(reset==0){
    dojo.addClass(dojo.byId("menuFilterModuleTop7"),"menuBarItemSelectedModule");
    dojo.addClass(dojo.byId("menuFilterModuleTopIcon7"),"menuFilterModuleTopIcon");
    for (var i=1; i <= nbTotal; i++) {
      if(dojo.byId("moduleTitle_"+i)){
        if(dojo.hasClass(dojo.byId("moduleMenuDiv_"+i),'activeModuleMenu')){
          dojo.byId("moduleMenuDiv_"+i).style.display="none";
          if(dojo.byId("displayModule"+i).style.display=="block"){
            dojo.byId("displayModule"+i).style.display="none";
            dojo.byId("moduleTitle_"+i).style.width=260+'px';
          }
        }else{
          dojo.byId("moduleMenuDiv_"+i).style.display="block";
        }
      }
    }
  }else{
    filterMenuModule(1,nbTotal);
  }
}

function changeSpeedAnimation (val){
  dojo.byId('animationSpeed').value=val;
  dijit.byId('lowAnimation').selected='false';
  dijit.byId('medAnimation').selected='false';
  dijit.byId('fastAnimation').selected='false';
  
  switch(val){
  case 'Low':
      dijit.byId('lowAnimation').selected='true';
    break;
  case 'Med':
      dijit.byId('medAnimation').selected='true';
    break;
  case 'Fast':
      dijit.byId('fastAnimation').selected='true';
    break;
  }
  saveUserParameter('animationSpeedMode',val);
}

function multipleUpadteSelectAtribute(value) {
  if (value) {
    filterStartInput=true;
    var displayFormatInputation=false;
    var displayFormatWork=false;
	dijit.byId("saveButtonMultiple").set("disabled", false);
    dijit.byId('idMultipleUpdateAttribute').store.fetchItemByIdentity({
      identity : value,
      onItem : function(item){
        var dataType=dijit.byId('idMultipleUpdateAttribute').store.getValue(
            item, "dataType", "inconnu");
        if(value=="refTypeIncome" || value=="refTypeExpense"){
          dataType="list";
        }
        if(value=="maxDailyWork" || value=="maxWeeklyWork"){
          displayFormatInputation=true;
        }
        if(value=="workVal"){
          displayFormatWork=true;
        }
        if (value == "tags") dataType ='textarea';
        var datastoreOperator=new dojo.data.ItemFileReadStore({
          url : '../tool/jsonList.php?listType=operator&actualView=MultipleUpadate&dataType=' + dataType+addTokenIndexToUrl()
        });
        var storeOperator=new dojo.store.DataStore({
          store : datastoreOperator
        });
        storeOperator.query({
          id : "*"
        });
        dojo.byId('multipleUpdateOperateur').visibility = 'visible';
        if(dataType!='textarea'){
          dojo.byId('isLongText').value="";
          if(dojo.byId('multipleUpdateOperateur').firstChild.innerHTML==undefined || dojo.byId('multipleUpdateOperateur').firstChild.innerHTML!=i18n('replaceMultipleUpadte') ){
            var spanVal=document.createElement('span');
            spanVal.setAttribute('style','position:relative;');
            spanVal.innerHTML=i18n('replaceMultipleUpadte');
            if(dojo.byId('multipleUpdateOperateur').firstChild.innerHTML!=undefined )dojo.byId('multipleUpdateOperateur').removeChild(dojo.byId('multipleUpdateOperateur').firstChild);
            dojo.byId('multipleUpdateOperateur').insertAdjacentElement('afterbegin',spanVal);
          }
        }
        dojo.byId('dataTypeSelected').value=dataType;
        if (dataType == "bool") {
          filterType="bool";
		  dojo.style(dojo.byId('multipleInsert'), {
		     display : 'none'
		  });
          dojo.style(dojo.byId('multipleUpdateColorButton'), {
            display : 'none'
          });
		  dojo.style(dijit.byId('multipleUpdateValueHatch').domNode,{
		      display:'none'
		  });
          dojo.style(dijit.byId('newMultipleUpdateValue').domNode, {
            display : 'none'
          });
          dojo.style(dijit.byId('newMultipleUpdateValueNum').domNode,{
            display : 'none'
          });
          dojo.style(dijit.byId('multipleUpdateValueList').domNode, {
            display : 'none'
          });
          dojo.style(dijit.byId('showDetailInMultipleUpdate').domNode, {
            display : 'none'
          });
          if (dijit.byId('multipleUpdateValueCheckboxSwitch')) { 
            dojo.style(dijit.byId('multipleUpdateValueCheckboxSwitch').domNode, {
              display : 'block'
            });
            dijit.byId('multipleUpdateValueCheckbox').set('value', 'off');
          } else {
            dojo.style(dijit.byId('multipleUpdateValueCheckbox').domNode, {
              display : 'block'
            });
            dijit.byId('multipleUpdateValueCheckbox').set('checked', '');
          }
          dojo.style(dijit.byId('multipleUpdateValueDate').domNode, {
            display : 'none'
          });
          dojo.style(dijit.byId('multipleUpdateTextArea').domNode, {
            display : 'none'
          });
          dojo.style(dijit.byId('multipleUpdateValueTime').domNode, {
            display : 'none'
          });
        }else if(dataType == "color"){
          filterType="color";
          dojo.style(dojo.byId('multipleUpdateColorButton'), {
            display : 'block'
          });
		  dojo.style(dijit.byId('multipleUpdateValueHatch').domNode,{
		      display:'none'
		  });
		  dojo.style(dojo.byId('multipleInsert'), {
		     display : 'none'
		  });
          dojo.style(dijit.byId('newMultipleUpdateValue').domNode, {
            display : 'none'
          });
          dojo.style(dijit.byId('newMultipleUpdateValueNum').domNode,{
            display : 'none'
          });
          dojo.style(dijit.byId('multipleUpdateValueList').domNode, {
            display : 'none'
          });
          dojo.style(dijit.byId('showDetailInMultipleUpdate').domNode, {
            display : 'none'
          });
          if (dijit.byId('multipleUpdateValueCheckboxSwitch')) { 
            dojo.style(dijit.byId('multipleUpdateValueCheckboxSwitch').domNode, {
              display : 'none'
            });
            dijit.byId('multipleUpdateValueCheckbox').set('value', 'off');
          } else {
            dojo.style(dijit.byId('multipleUpdateValueCheckbox').domNode, {
              display : 'none'
            });
            dijit.byId('multipleUpdateValueCheckbox').set('checked', '');
          }
          dojo.style(dijit.byId('multipleUpdateValueDate').domNode, {
            display : 'none'
          });
          dojo.style(dijit.byId('multipleUpdateTextArea').domNode, {
            display : 'none'
          });
          dojo.style(dijit.byId('multipleUpdateValueTime').domNode, {
            display : 'none'
          });
        } else if (dataType=="hatchPattern") {
		  filterType="hatchPattern";
		  dojo.style(dojo.byId('multipleUpdateColorButton'), {
			 display : 'none'
		  });
		  dojo.style(dojo.byId('multipleInsert'), {
			display : 'none'
		  });
		  dojo.style(dijit.byId('newMultipleUpdateValue').domNode, {
			display : 'none'
		  });
		  dojo.style(dijit.byId('newMultipleUpdateValueNum').domNode,{
			display : 'none'
		  });
		  dojo.style(dijit.byId('multipleUpdateValueList').domNode, {
			display : 'none'
		  });
		  dojo.style(dijit.byId('showDetailInMultipleUpdate').domNode, {
			display : 'none'
		  });
		  if (dijit.byId('multipleUpdateValueCheckboxSwitch')) { 
			dojo.style(dijit.byId('multipleUpdateValueCheckboxSwitch').domNode, {
			  display : 'none'
			});
			dijit.byId('multipleUpdateValueCheckbox').set('value', 'off');
		  } else {
			dojo.style(dijit.byId('multipleUpdateValueCheckbox').domNode, {
			  display : 'none'
			});
			dijit.byId('multipleUpdateValueCheckbox').set('checked', '');
		  }
		  dojo.style(dijit.byId('multipleUpdateValueDate').domNode, {
			display : 'none'
		  });
		  dojo.style(dijit.byId('multipleUpdateTextArea').domNode, {
			display : 'none'
		  });
		  dojo.style(dijit.byId('multipleUpdateValueTime').domNode, {
			display : 'none'
		  });
		  dojo.style(dijit.byId('multipleUpdateValueHatch').domNode,{
			display:'block'
		  });			
		}else if (dataType == "decimal" || dataType=="numeric") {
          filterType=dataType;
		  dojo.style(dojo.byId('multipleInsert'), {
		     display : 'none'
		  });
          dojo.style(dojo.byId('multipleUpdateColorButton'), {
            display : 'none'
          });
		  dojo.style(dijit.byId('multipleUpdateValueHatch').domNode,{
		      display:'none'
		  });
          dojo.style(dijit.byId('newMultipleUpdateValue').domNode, {
            display : 'none'
          });
          dojo.style(dijit.byId('newMultipleUpdateValueNum').domNode,{
            display : 'inline-block'
          });
          if(displayFormatInputation){
            dojo.byId('formatInputation').style.display= 'inline-block';
          }
          if(displayFormatWork){
            dojo.byId('formatWork').style.display ='inline-block';
          }
          dojo.style(dijit.byId('multipleUpdateValueList').domNode, {
            display : 'none'
          });
          dojo.style(dijit.byId('showDetailInMultipleUpdate').domNode, {
            display : 'none'
          });
          if (dijit.byId('multipleUpdateValueCheckboxSwitch')) { 
            dojo.style(dijit.byId('multipleUpdateValueCheckboxSwitch').domNode, {
              display : 'none'
            });
            dijit.byId('multipleUpdateValueCheckbox').set('value', 'off');
          } else {
            dojo.style(dijit.byId('multipleUpdateValueCheckbox').domNode, {
              display : 'none'
            });
            dijit.byId('multipleUpdateValueCheckbox').set('checked', '');
          }
          dojo.style(dijit.byId('multipleUpdateValueDate').domNode, {
            display : 'none'
          });
          dojo.style(dijit.byId('multipleUpdateTextArea').domNode, {
            display : 'none'
          });
          dojo.style(dijit.byId('multipleUpdateValueTime').domNode, {
            display : 'none'
          });
        } else if (dataType == "list") {
          filterType="list";
          var extraUrl="";
          if (value == 'idTargetVersion' || value == 'idTargetProductVersion' || value == 'idOriginalProductVersion') {
            value='idProductVersion';
            extraUrl='&critField=idle&critValue=all';
          } else if (value == 'idTargetComponentVersion' || value == 'idOriginalComponentVersion') {
            value='idComponentVersion';
            extraUrl='&critField=idle&critValue=all';
          }
		  var objectClass = dojo.byId('objectClass').value;
          var urlListFilter='../tool/jsonList.php?listType=list&dataType='+value+'&actualView=MultipleUpadate&objectClass='+objectClass;

          if (typeof currentSelectedProject!='undefined' && currentSelectedProject!='' && currentSelectedProject!='*') {
          if (value=='idActivity') {
              urlListFilter+='&critField=idProjectSub&critValue='+currentSelectedProject;
            } if (value=='idComponent') {
              // noting
            } else {
              urlListFilter+='&critField=idProject&critValue='+currentSelectedProject;
            }
            if (extraUrl=='&critField=idle&critValue=all') {
              extraUrl=='&critField1=idle&critValue1=all';
            }
          }
          if (extraUrl!="") {
            urlListFilter+=extraUrl;
          }  
          var tmpStore=new dojo.data.ItemFileReadStore({
            url : urlListFilter+addTokenIndexToUrl()
          });
          var mySelect=dojo.byId("multipleUpdateValueList");
          mySelect.options.length=0;
          var nbVal=0;
          if(dijit.byId('idMultipleUpdateAttribute').getValue()=="idBusinessFeature"){
            var listId = "";
            tmpStore.fetch({
                query : {
                  id : "*"
                },
                onItem : function(item) {
                  if (tmpStore.getValue(item, "id", "")!=' ') {
                    listId += (listId != "") ? '_' : '';
                    listId += parseInt(tmpStore.getValue(item, "id", ""), 10) + '';
                    nbVal++;
                  }
                },
                onError : function(err) {
                  console.info(err.message);
                },
                onComplete : function() { 
                  dojo.xhrGet({
                  url : '../tool/getProductNameFromBusinessFeature.php?listId=' + listId+addTokenIndexToUrl(),
                handleAs : "text",
                load: function(data){
                  var listName = JSON.parse(data);
                  tmpStore.fetch({
                          query : {
                            id : "*"
                          },
                          onItem : function(item) {
                            mySelect.options[mySelect.length]=new Option(tmpStore.getValue(item, "name", "") + " (" + listName[tmpStore.getValue(item, "id", "")] + ")", tmpStore.getValue(item, "id", ""));
                          },
                          onError : function(err) {
                            console.info(err.message);
                          }
                        });
                }
                  });
                 }
              });
          }else{
            tmpStore.fetch({
                  query : {
                    id : "*"
                  },
                  onItem : function(item) {
                    mySelect.options[mySelect.length]=new Option(tmpStore.getValue(
                        item, "name", ""), tmpStore.getValue(item, "id", ""));
                    nbVal++;
                  },
                  onError : function(err) {
                    console.info(err.message);
                  }
                });
          }
          dojo.removeAttr('multipleUpdateValueList','multiple');
          dojo.style(dojo.byId('multipleUpdateColorButton'), {
            display : 'none'
          });
		  dojo.style(dijit.byId('multipleUpdateValueHatch').domNode,{
		      display:'none'
		  });
          dojo.style(dijit.byId('newMultipleUpdateValue').domNode, {
            display : 'none'
          });
          dojo.style(dijit.byId('newMultipleUpdateValueNum').domNode,{
            display : 'none'
          });
		  dojo.style(dojo.byId('multipleInsert'), {
		     display : 'none'
		  });
          dojo.style(dijit.byId('multipleUpdateValueList').domNode, {
            display : 'block'
          });
          dojo.xhrGet({
            url : "../tool/checkAccessForScreen.php?listType="+value+addTokenIndexToUrl(),
            handleAs : "text",
            load : function(data) {
              if(data && data=="YES"){          
                dojo.style(dijit.byId('showDetailInMultipleUpdate').domNode, {display : 'block'}); 
              } else {
                dojo.style(dijit.byId('showDetailInMultipleUpdate').domNode, {display : 'none'});
              }
            }
          });
          dijit.byId('showDetailInMultipleUpdate').set('value', item.id);
          dijit.byId('multipleUpdateValueList').reset();
          dojo.style(dijit.byId('multipleUpdateValueCheckbox').domNode, {
            display : 'none'
          });
          if (dijit.byId('multipleUpdateValueCheckboxSwitch')) { 
            dojo.style(dijit.byId('multipleUpdateValueCheckboxSwitch').domNode, {
              display : 'none'
            });
          }
          dojo.style(dijit.byId('multipleUpdateValueDate').domNode, {
            display : 'none'
          });
          dojo.style(dijit.byId('multipleUpdateTextArea').domNode, {
            display : 'none'
          });
          dojo.style(dijit.byId('multipleUpdateValueTime').domNode, {
            display : 'none'
          });
        } else if (dataType == "date" || dataType=="datetime" || dataType=="time") {
          filterType="date";
		  dojo.style(dojo.byId('multipleInsert'), {
		     display : 'none'
		  });
          dojo.style(dojo.byId('multipleUpdateColorButton'), {
            display : 'none'
          });
		  dojo.style(dijit.byId('multipleUpdateValueHatch').domNode,{
		      display:'none'
		  });
          dojo.style(dijit.byId('newMultipleUpdateValue').domNode, {
            display : 'none'
          });
          dojo.style(dijit.byId('newMultipleUpdateValueNum').domNode,{
            display : 'none'
          });
          dojo.style(dijit.byId('multipleUpdateValueList').domNode, {
            display : 'none'
          });
          dojo.style(dijit.byId('showDetailInMultipleUpdate').domNode, {
            display : 'none'
          });
          dojo.style(dijit.byId('multipleUpdateValueCheckbox').domNode, {
            display : 'none'
          });
          if (dijit.byId('multipleUpdateValueCheckboxSwitch')) { 
            dojo.style(dijit.byId('multipleUpdateValueCheckboxSwitch').domNode, {
              display : 'none'
            });
          }
          dojo.style(dijit.byId('multipleUpdateTextArea').domNode, {
            display : 'none'
          });
          if(dataType=="datetime" || dataType=="date") {
            dojo.style(dijit.byId('multipleUpdateValueDate').domNode, {
              display : 'block'
            });
          }
          if(dataType=="datetime" || dataType=="time"){
            dojo.style(dijit.byId('multipleUpdateValueTime').domNode, {
              display : 'block'
            });
          }
          dijit.byId('multipleUpdateValueDate').reset();
          dijit.byId('multipleUpdateValueTime').reset();
        } else if (dataType=="textarea" || dataType=="note"){
          dojo.byId('isLongText').value="true";
          dojo.style(dijit.byId('multipleUpdateTextArea').domNode, {
            display : 'block'
          });
          if(dojo.byId('multipleUpdateOperateur').firstChild.innerHTML==undefined || dojo.byId('multipleUpdateOperateur').firstChild.innerHTML!=i18n('addMultipleUpdate')){
            var spanVal=document.createElement('span');
            spanVal.setAttribute('style','position:relative;top:10px;');
            spanVal.innerHTML=i18n('addMultipleUpdate');
            if(dojo.byId('multipleUpdateOperateur').firstChild.innerHTML!=undefined )dojo.byId('multipleUpdateOperateur').removeChild(dojo.byId('multipleUpdateOperateur').firstChild);
            dojo.byId('multipleUpdateOperateur').insertAdjacentElement('afterbegin',spanVal);
          }
          dojo.byId('multipleUpdateOperateur').visibility = 'hidden';
		  dojo.style(dojo.byId('multipleInsert'), {
		     display : 'none'
		  });
          dojo.style(dojo.byId('multipleUpdateColorButton'), {
            display : 'none'
          });
		  dojo.style(dijit.byId('multipleUpdateValueHatch').domNode,{
		      display:'none'
		  });
          dojo.style(dijit.byId('newMultipleUpdateValue').domNode, {
            display : 'none'
          });
          dojo.style(dijit.byId('newMultipleUpdateValueNum').domNode,{
            display : 'none'
          });
          dojo.style(dijit.byId('multipleUpdateValueList').domNode, {
            display : 'none'
          });
          dojo.style(dijit.byId('showDetailInMultipleUpdate').domNode, {
            display : 'none'
          });
          dojo.style(dijit.byId('multipleUpdateValueCheckbox').domNode, {
            display : 'none'
          });
          if (dijit.byId('multipleUpdateValueCheckboxSwitch')) { 
            dojo.style(dijit.byId('multipleUpdateValueCheckboxSwitch').domNode, {
              display : 'none'
            });
          }
          dojo.style(dijit.byId('multipleUpdateValueDate').domNode, {
            display : 'none'
          });
          dojo.style(dijit.byId('multipleUpdateValueTime').domNode, {
            display : 'none'
          });
		} else if (dataType == "multipleInsert"){
			 dijit.byId("saveButtonMultiple").set("disabled", true);
			 filterType="multipleInsert";
			 dojo.byId('selectionValueMultipleInsert').value = value;
			 dojo.style(dojo.byId('multipleInsert'), {
			    display : 'block'
			  });
			 dojo.byId('multipleUpdateOperateur').firstChild.innerHTML = i18n('addProspectEvent');
			 dojo.style(dojo.byId('multipleUpdateColorButton'), {
			   display : 'none'
			 });
			 dojo.style(dijit.byId('multipleUpdateValueHatch').domNode,{
			     display:'none'
			 });
			 dojo.style(dijit.byId('newMultipleUpdateValue').domNode, {
			   display : 'none'
			 });
			 dojo.style(dijit.byId('newMultipleUpdateValueNum').domNode,{
			   display : 'none'
			 });
			 dijit.byId('newMultipleUpdateValue').reset();
			 dijit.byId('newMultipleUpdateValueNum').reset();
			 dojo.style(dijit.byId('multipleUpdateValueList').domNode, {
			   display : 'none'
			 });
			 dojo.style(dijit.byId('showDetailInMultipleUpdate').domNode, {
			   display : 'none'
			 });
			 dojo.style(dijit.byId('multipleUpdateValueCheckbox').domNode, {
			   display : 'none'
			 });
			 if (dijit.byId('multipleUpdateValueCheckboxSwitch')) { 
			   dojo.style(dijit.byId('multipleUpdateValueCheckboxSwitch').domNode, {
			     display : 'none'
			   });
			 }
			 dojo.style(dijit.byId('multipleUpdateValueDate').domNode, {
			   display : 'none'
			 });
			 dojo.style(dijit.byId('multipleUpdateTextArea').domNode, {
			   display : 'none'
			 });
			 dojo.style(dijit.byId('multipleUpdateValueTime').domNode, {
			   display : 'none'
			 });
			 dijit.byId('multipleUpdateValueDate').reset();
			 dijit.byId('multipleUpdateValueTime').reset();
        } else {
          filterType="text";
		  dojo.style(dojo.byId('multipleInsert'), {
		     display : 'none'
		  });
          dojo.style(dojo.byId('multipleUpdateColorButton'), {
            display : 'none'
          });
		  dojo.style(dijit.byId('multipleUpdateValueHatch').domNode,{
		      display:'none'
		  });
          dojo.style(dijit.byId('newMultipleUpdateValue').domNode, {
            display : 'block'
          });
          dojo.style(dijit.byId('newMultipleUpdateValueNum').domNode,{
            display : 'none'
          });
          dijit.byId('newMultipleUpdateValue').reset();
          dijit.byId('newMultipleUpdateValueNum').reset();
          dojo.style(dijit.byId('multipleUpdateValueList').domNode, {
            display : 'none'
          });
          dojo.style(dijit.byId('showDetailInMultipleUpdate').domNode, {
            display : 'none'
          });
          dojo.style(dijit.byId('multipleUpdateValueCheckbox').domNode, {
            display : 'none'
          });
          if (dijit.byId('multipleUpdateValueCheckboxSwitch')) { 
            dojo.style(dijit.byId('multipleUpdateValueCheckboxSwitch').domNode, {
              display : 'none'
            });
          }
          dojo.style(dijit.byId('multipleUpdateValueDate').domNode, {
            display : 'none'
          });
          dojo.style(dijit.byId('multipleUpdateTextArea').domNode, {
            display : 'none'
          });
          dojo.style(dijit.byId('multipleUpdateValueTime').domNode, {
            display : 'none'
          });
        }
      },
      onError : function(err) {
        dojo.style(dojo.byId('multipleUpdateColorButton'), {
          display : 'none'
        });
		dojo.style(dijit.byId('multipleUpdateValueHatch').domNode,{
		    display:'none'
		});
        dojo.byId('multipleUpdateOperateur').visibility = 'hidden';
        dojo.style(dijit.byId('newMultipleUpdateValue').domNode, {
          display : 'none'
        });
        dojo.style(dijit.byId('newMultipleUpdateValueNum').domNode,{
          display : 'none'
        });
        dojo.style(dijit.byId('newMultipleUpdateValueueList').domNode, {
          display : 'none'
        });
        dojo.style(dijit.byId('showDetailInMultipleUpdate').domNode, {
          display : 'none'
        });
        dojo.style(dijit.byId('multipleUpdateValueCheckbox').domNode, {
          display : 'none'
        });
        if (dijit.byId('multipleUpdateValueCheckboxSwitch')) { 
          dojo.style(dijit.byId('multipleUpdateValueCheckboxSwitch').domNode, {
            display : 'none'
          });
        }
        dojo.style(dijit.byId('multipleUpdateValueDate').domNode, {
          display : 'none'
        });
        dojo.style(dijit.byId('multipleUpdateTextArea').domNode, {
          display : 'none'
        });
        // hideWait();
      }
    });
    dijit.byId('newMultipleUpdateValueNum').reset();
    dijit.byId('newMultipleUpdateValue').reset();
    dijit.byId('multipleUpdateValueList').reset();
    dijit.byId('multipleUpdateValueCheckbox').reset();
    if (dijit.byId('multipleUpdateValueCheckboxSwitch')) { dijit.byId('multipleUpdateValueCheckboxSwitch').reset();}
    dijit.byId('multipleUpdateValueDate').reset();
    dijit.byId('multipleUpdateTextArea').reset();
    
  } else {
    dojo.byId('multipleUpdateOperateur').visibility = 'hidden';
    dojo.style(dojo.byId('multipleUpdateColorButton'), {
      display : 'none'
    });
	dojo.style(dijit.byId('multipleUpdateValueHatch').domNode,{
	    display:'none'
	});
	dojo.style(dojo.byId('multipleInsert'), {
	   display : 'none'
	});
    dojo.style(dijit.byId('newMultipleUpdateValue').domNode, {
      display : 'none'
    });
    dojo.style(dijit.byId('newMultipleUpdateValueNum').domNode,{
      display : 'none'
    });
    dojo.style(dijit.byId('multipleUpdateValueList').domNode, {
      display : 'none'
    });
    dojo.style(dijit.byId('showDetailInMultipleUpdate').domNode, {
      display : 'none'
    });
    dojo.style(dijit.byId('multipleUpdateValueCheckbox').domNode, {
      display : 'none'
    });
    if (dijit.byId('multipleUpdateValueCheckboxSwitch')) { 
      dojo.style(dijit.byId('multipleUpdateValueCheckboxSwitch').domNode, {
        display : 'none'
      });
    }
    dojo.style(dijit.byId('multipleUpdateValueDate').domNode, {
      display : 'none'
    });
    dojo.style(dijit.byId('multipleUpdateValueTime').domNode, {
      display : 'none'
    });
    dojo.style(dijit.byId('multipleUpdateTextArea').domNode, {
      display : 'none'
    });
  }
}

function setLstDocumentRight(lst,val){
  var valueLst=dojo.byId(lst).value;
  if (valueLst.indexOf(val)!=-1)return;
  if(valueLst==''){
    dojo.byId(lst).value=val;
  }else{
    dojo.byId(lst).value=valueLst+','+val;
  }
}

var activFuncHideShowDropDiv=false;
function hideShowDropDiv(mode,subTaskRawId){
  event.preventDefault();
  var el=dojo.byId(subTaskRawId);
  divAttach=el.querySelector('.divAttachSubTask');
  if(dijit.byId('attachmentFileDirect'))dijit.byId('attachmentFileDirect').reset();
  if(mode=='show'){
      el.style.background="var(--color-button-background-selected)";
      el.style.opacity='50%';
      el.style.border=" 2px dashed grey";

      activFuncHideShowDropDiv=true;
  }else if(mode =='hide'){
    el.style.background="unset";
    el.style.opacity='unset';
    el.style.border="";
      activFuncHideShowDropDiv=false;
  }else {
    activFuncHideShowDropDiv=false;
    el.style.background="unset";
    el.style.opacity='unset';
    el.style.border="";
  }

}

function setDragAndDropAttachmentSubTask(destination,tableClass,rawClass,attachmentDivClass){
  var dest=dojo.byId(destination);
  var allTable=dest.querySelectorAll('.'+tableClass);
  
  allTable.forEach(function(table){
    var allRaw=table.querySelectorAll('.'+rawClass);
    allRaw.forEach(function(el){
      var divAttach=el.querySelector('.'+attachmentDivClass);
      if(divAttach.childNodes[1] && divAttach.childNodes[1].firstChild && divAttach.childNodes[1].firstChild.id){
        var idDiv=divAttach.childNodes[1].firstChild.id;
        dijit.byId(idDiv).reset();
        dijit.byId(idDiv).addDropTarget(el,false);
      }
      
    });
  });
}

function refreshSubTaskAttachment(idSubTask){
  loadDiv('../view/refreshSubTaskAttachmentDiv.php?idSubTask='+idSubTask ,'divAttachement_'+idSubTask);
}


function selectResources(type,target,project) {
  loadDialog('dialogSelectResources',null,true,'&type='+type+'&list='+dojo.byId(target).value+'&target='+target+'&project='+project,true);
}

function selectResourcesValidated(targeted,target2) {
  selectResourcesSelected.sync();
  var nodeList=selectResourcesSelected.getAllNodes();
  var arrayValues=new Array();
  for (var i=0; i < nodeList.length; i++) {
    arrayValues[i]=nodeList[i].getAttribute('userid');
  }
  var result = "";
  for (var i=0; i < nodeList.length; i++) {
    if(result==""){
      result += arrayValues[i];
    }else{
      result += ";"+arrayValues[i];
    }
  }
  var dest = target2+'Display';
  dojo.byId(targeted).value=result;
  dijit.byId(dest).set('value',result);
  setTimeout('selectResourcesTransformIdToName( \''+dest+'\')', 100);
  setTimeout("dijit.byId('dialogSelectResources').hide()", 200);
}

function selectResourcesTransformIdToName(target){
    dojo.xhrGet({
      url : '../tool/getSingleData.php?dataType=selectResourceTransformIdToName&idResource='+dijit.byId('paramTryToHackUserListDisplay').get('value')+addTokenIndexToUrl(),
      handleAs : "text",
      load : function(data) {
         dijit.byId(target).setDisplayedValue(data);
      }
    });
}

function resizeActivityStreamToday (){
  if(showHideActivityStreamTodayRun)return;
  var dimension =250;
  var duration=50;
  todayActiStreamDivLastWidth=dimension;
  var classicViewDim = dojo.byId("centerDiv").offsetWidth-dimension-5;
  saveContentPaneResizing("contentPaneTodayActStreamWidth", dimension, true);
  saveContentPaneResizing("contentPaneTodayClassicViewWidth", classicViewDim, true);
  dojox.fx.combine([ dojox.fx.animateProperty({
    node : "todayClassicView",
    properties : {
     width : classicViewDim,
  },
  duration : duration
  }), dojox.fx.animateProperty({
    node : "todayActStream",
    properties : {
    width : dimension
  },
  duration : duration
  })]).play();
  setTimeout('dijit.byId("globalContainer").resize();', duration+5);
}

function saveSynchronizeDefinition() {
  var formVar=dijit.byId('synchroniseDefinitionForm');
  if (formVar.validate()) {
    loadContent("../tool/saveSynchronizationDefinition.php", "resultDivMain", "synchroniseDefinitionForm",true, 'Synchronization');
    dijit.byId('dialogSynchroniseDefinition').hide();
  } else {
    showAlert(i18n("alertInvalidForm"));
  }
}

function saveDisableSynchronizeDefinition() {
  var formVar=dijit.byId('disableSynchronizeDefinitionForm');
  if (formVar.validate()) {
    loadContent("../tool/saveDisableSynchronizationDefinition.php", "resultDivMain", "disableSynchronizeDefinitionForm",true, 'Synchronization');
    dijit.byId('dialogDisableSynchronizeDefinition').hide();
  } else {
    showAlert(i18n("alertInvalidForm"));
  }
}

function setAttributionVoteElement() {
  if (!dijit.byId("attributionVoteRule")|| !dijit.byId("attributionVoteRule").get("value"))return;
  var idVoteRule=dijit.byId("attributionVoteRule").get("value");
  dojo.xhrGet({
    url : '../tool/getSingleData.php?dataType=attributionVoteRule&id='+idVoteRule+addTokenIndexToUrl(),
    handleAs : "text",
    load : function(data) {
      arrayData=data.split('#!#!#!#!#!#');
        if(arrayData[0] == 'none'){
          dijit.byId("attributionVoteElement").set("readOnly",false);
          dijit.byId('attributionVoteElement').set('value', '');
        }else{
          dijit.byId("attributionVoteElement").set("readOnly",true);
          dijit.byId('attributionVoteElement').set('value', arrayData[0]);
        }
        dijit.byId('attributionVoteTotal').set('value', arrayData[1]);
      }
  });
    
}

function newDetailItemLink (){
  var linkType=dijit.byId('linkRef2Type').get("value");
  if (linkType) {
    var objectClass=linkableArray[linkType];
    if (canCreateArray[objectClass] == "YES") {
      dojo.byId('comboName').value='linkRef2Id';
      dojo.byId('comboClass').value=objectClass;
      dijit.byId("dialogDetail").show();
      hideField('comboSearchButton');
      hideField('comboDetailResult');
      showWait();
      hideField('comboSelectButton');
      hideField('comboNewButton');
      showField('comboSaveButton');
      showField('comboCloseButton');
      destinationWidth=frames['comboDetailFrame'].document.body.offsetWidth
      page="comboSearch.php?objectClass=" + objectClass+"&objectId=0&mode=new&destinationWidth=" + destinationWidth;
      window.top.frames['comboDetailFrame'].location.href=page+addTokenIndexToUrl();
      setTimeout('dijit.byId("dialogDetail").show()', 10);   
    }else{
      showInfo(i18n('errorCreateRights'));
    }

  } else {
    showInfo(i18n('messageMandatory', new Array(i18n('linkType'))));
  }
 
}

function changeVoteSelf(voteUserId,valueUser){
  var voteSelfValue=dijit.byId("voteSelf").get("value");
  if(!voteSelfValue)voteSelfValue=0;
  dojo.xhrGet({
    url : '../tool/getSingleData.php?dataType=voteSelf&id='+voteSelfValue+'&voteUserId='+voteUserId+'&valueUser='+valueUser+addTokenIndexToUrl(),
    handleAs : "text",
    load : function(data) {
        dijit.byId('pointsVote').set('value', data);
      }
  });
}


//=========================================================
//Other
//=========================================================

//var objectClass=dojo.byId('objectClass').value;
//var objectId=dojo.byId('objectId').value;
//var param='';
//if(objectClass!=null && objectId!=null && dojo.byId('mailRefType') &&
//dojo.byId('mailRefId').value){
//dojo.byId('mailRefType').value=dojo.byId('objectClass').value;
//dojo.byId('mailRefId').value=dojo.byId('objectId').value;
//param="&objectClass=" +objectClass+"&objectId=" +objectId;
//}

// florent ticket 4442
function showAttachedSize(size,name,id,type,mode=""){
  var totalSize=dojo.byId('totalSizeNoConvert').value;
  var maxSize=Number(dojo.byId('maxSizeNoconvert').value);
  var attachments=dojo.byId('attachments').value;
  var addAttachments='';
  if(isNaN(size)){
   size=0;
  }
  if(dijit.byId('dialogMail'+name).get('checked')==true){
   totalSize=Number(totalSize)+Number(size);
   if(attachments!=''){
	 addAttachments=attachments+'/'+id+'_'+type;
	 if(mode=="DialogMail"){
		addAttachments+='_'+dojo.byId('objectClass').value;
	 }
   }else{
	  addAttachments=id+'_'+type;
	  if(mode=="DialogMail"){
	 	addAttachments+='_'+dojo.byId('objectClass').value;
	  }
   }
   dojo.byId('attachments').value=addAttachments;
  }else{
   var regex='/'+id+'_'+type;
   if(attachments.indexOf('/'+id+'_'+type)!=-1){
     addAttachments=attachments.replace(regex,'');
   }else{
     regex=id+'_'+type;
     addAttachments=attachments.replace(regex,'');
   }
   dojo.byId('attachments').value=addAttachments;
   totalSize=Number(totalSize)-Number(size);
  }
  saveDataToSession('dialogMailAttachments',addAttachments,false);
  var noConvert=totalSize;
  if(totalSize!=0){
   totalSize=octetConvertSize(totalSize);
  }
  if( maxSize < noConvert ){
   dojo.byId('infoSize').style.color="red";
   dojo.byId('totalSize').style.color="red";
  }else if ((maxSize >= noConvert) || noConvert==0) {
   dojo.byId('infoSize').style.color="green";
   dojo.byId('totalSize').style.color="green";
  }
  dojo.byId('totalSizeNoConvert').value=noConvert;
  dojo.byId('totalSize').value=totalSize;
}



function octetConvertSize(octet){
  if(octet!=0 && octet!='-'){
   octet = Math.abs(parseInt(octet, 10));
   var def = [[1, ' octets'], [1024, ' ko'], [1024*1024, ' Mo'], [1024*1024*1024, ' Go'], [1024*1024*1024*1024, ' To']];
   for(var i=0; i<def.length; i++){
     if(octet<def[i][0]) return (octet/def[i-1][0]).toFixed(2)+' '+def[i-1][1];
   }
  }else{
   return i18n('errorNotFoundAttachment');
  }

}

clearDivDelayedTimeout=[];
function clearDivDelayed(divName,delay) {
  if (clearDivDelayedTimeout[divName]) clearTimeout(clearDivDelayedTimeout[divName]);
  if (!divName) return;
  if (!delay) delay=2000;
  clearDivDelayedTimeout[divName]=setTimeout("if (dojo.byId('" + divName + "')) dojo.byId('" + divName + "').innerHTML='';",delay);
}

function purgeAssignmentTable(){
  var objectClass = null;
  var objectId = null;
  if(dijit.byId('dialogEditAssignmentPlanning') && dijit.byId('dialogEditAssignmentPlanning').open){
    objectClass=dojo.byId('assignmentDialogObjectClass').value;
    objectId = dojo.byId("assignmentDialogObjectId").value;
  }else{
    objectClass=dojo.byId('objectClass').value;
    objectId = dojo.byId("objectId").value;
  }
  
  var actionOK = function(){
    showWait();
    dojo.xhrGet({url : '../tool/purgeAssignment.php?'+addTokenIndexToUrl()+'&objectClass='+objectClass+'&objectId='+objectId,
      handleAs : "text",
      load : function(data) {
          var callBack = function(){
            refreshGrid();
          };
          if(dijit.byId('dialogEditAssignmentPlanning') && dijit.byId('dialogEditAssignmentPlanning').open){
            var params="&objectClass=" + objectClass + "&objectId=" + objectId;
            loadDialog('dialogEditAssignmentPlanning', callBack, true, params);
          }else{
            loadContent("objectDetail.php", "detailDiv", "listForm", false, null, null, false, callBack);
          }
        }
    });
  };
  showConfirm(i18n('confirmPurgeAssignment', new Array(i18n(objectClass), parseInt(objectId))), actionOK);
}

function resetAssignmentTable(){
  var objectClass = null;
  var objectId = null;
  if(dijit.byId('dialogEditAssignmentPlanning') && dijit.byId('dialogEditAssignmentPlanning').open){
    objectClass=dojo.byId('assignmentDialogObjectClass').value;
    objectId = dojo.byId("assignmentDialogObjectId").value;
  }else{
    objectClass=dojo.byId('objectClass').value;
    objectId = dojo.byId("objectId").value;
  }
  
  var actionOK = function(){
    showWait();
    dojo.xhrGet({url : '../tool/resetAssignment.php?'+addTokenIndexToUrl()+'&objectClass='+objectClass+'&objectId='+objectId,
      handleAs : "text",
      load : function(data) {
          var callBack = function(){
            refreshGrid();
          };
          if(dijit.byId('dialogEditAssignmentPlanning') && dijit.byId('dialogEditAssignmentPlanning').open){
            var params="&objectClass=" + objectClass + "&objectId=" + objectId;
            loadDialog('dialogEditAssignmentPlanning', callBack, true, params);
          }else{
            loadContent("objectDetail.php", "detailDiv", "listForm", false, null, null, false, callBack);
          }
        }
    });
  };
  showConfirm(i18n('confirmResetAssignment', new Array(i18n(objectClass), parseInt(objectId))), actionOK);
}

function resourceListTransformation(field) {
  var store=dijit.byId(field).store;
  for (var i=0;i<store.data.length;i++) {
    store.data[i].label=store.data[i].name.replace('[[POOL]]','<span style="font-family: Verdana, Arial, Tahoma, sans-serif, icomoon;">&#xe903&nbsp;</span>');
    store.data[i].name=store.data[i].name.replace('[[POOL]]','');
  }
  if (dijit.byId(field).get("displayedValue").substr(0,8)=='[[POOL]]') {
    var val=dijit.byId(field).get("value");
    dijit.byId(field).set("value",null);
    dijit.byId(field).set("value",val);
  }
}

function showUpdateResourceCost(idRole) {
  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
  var params="&idRole=" + idRole;
  loadDialog('dialogUpdateResourceCost',null,true,params,true);
}

function updateResourceCost(){
  var formVar=dijit.byId('updateResourceCostForm');
  if (formVar.validate()) {
    loadContent("../tool/updateResourceCost.php","resultDivMain",'updateResourceCostForm', true, 'updateResourceCost');
    dijit.byId('dialogUpdateResourceCost').hide();
  } else {
    showAlert(i18n("alertInvalidForm"));
  }
}

var hideToolTipTimeout=null;
function showToolTip(idToolTip){
  clearTimeout(hideToolTipTimeout);
  var toolTip = dijit.byId(idToolTip);
  if(toolTip){
    toolTip.openDropDown();
  }
}

function hideToolTip(idToolTip, delay){
  var toolTip = dijit.byId(idToolTip);
  clearTimeout(hideToolTipTimeout);
  if(toolTip){
    var callback = function(){
      toolTip.closeDropDown();
    }
    hideToolTipTimeout = setTimeout(callback, delay);
  }
}

var oldPrintWidth=null;
var oldPrintHeight=null;
var oldPrintFrameWidth=null;
var oldPrintFrameHeight=null;
var oldCkHeight=null;
var oldMailCkHeight=null;
var oldMailFullScreenLayoutStyles=null;
var dialogMailNormalButtonStyle=null;
var dialogMailNormalWidth=1350;
var dialogMailNormalHeight=700;
var dialogMailNormalMessageWidth=600;
var dialogMailNormalMessageHeight=150;
var dialogMailNormalMessageBottomMargin=20;
var dialogMailAttachmentBlockWidth=700;
var dialogMailFullScreenHorizontalMargin=60;
var dialogMailSmallScreenBreakpoint=1600;
var dialogMailFullScreenMessageBottomMargin=25;
var dialogMailFullScreenButtonGap=20;
var dialogMailFullScreenScreenPadding=30;
var dialogMailAttachmentDefaultHeight=154;
var dialogMailAddedAttachmentDefaultHeight=232;
var dialogMailAttachmentVerticalGap=6;
var dialogMailAttachmentButtonGap=15;
var dialogMailFullScreenStyleIds=[
  'dialogMail',
  'dialogMailGeneralTable',
  'dialogMailGlobalTop',
  'dialogMailCheckboxOptionAndReceiver',
  'dialogMailEmailTemplate',
  'dialogMailMessage',
  'mailMailEditor',
  'mailForm',
  'receiverTableContainer',
  'dialogMailLabelBeforeTable',
  'dialogMailAddAttachmentButton',
  'dialogMailSpanForButtonAddAttachment',
  'attachmentFileEmail',
  'showattachmentPJ',
  'showAddAttachment',
  'dialogMailButtonOkCancel'
];
function storeDialogMailStyle(id) {
  var node=dojo.byId(id);
  if (node) oldMailFullScreenLayoutStyles[id]=node.style.cssText;
}
function restoreDialogMailStyle(id) {
  var node=dojo.byId(id);
  if (node && oldMailFullScreenLayoutStyles && typeof oldMailFullScreenLayoutStyles[id] != 'undefined') node.style.cssText=oldMailFullScreenLayoutStyles[id];
}
function getDialogMailNamedNode(name) {
  var nodes=dojo.query("#dialogMail [name='" + name + "']");
  return nodes.length ? nodes[0] : null;
}
function storeDialogMailNodeStyle(key, node) {
  if (node) oldMailFullScreenLayoutStyles[key]=node.style.cssText;
}
function restoreDialogMailNodeStyle(key, node) {
  if (node && oldMailFullScreenLayoutStyles && typeof oldMailFullScreenLayoutStyles[key] != 'undefined') node.style.cssText=oldMailFullScreenLayoutStyles[key];
}
function getDialogMailViewportSize() {
  return {
    w: window.innerWidth || document.documentElement.clientWidth || screen.width,
    h: window.innerHeight || document.documentElement.clientHeight || screen.height
  };
}
function getDialogMailNormalBox() {
  var viewport=getDialogMailViewportSize();
  var horizontalMargin=(viewport.w <= dialogMailSmallScreenBreakpoint) ? 120 : 40;
  var verticalMargin=(viewport.h <= 820) ? 80 : 120;
  return {
    w: Math.min(dialogMailNormalWidth, Math.max(760, viewport.w - horizontalMargin)),
    h: Math.min(dialogMailNormalHeight, Math.max(500, viewport.h - verticalMargin))
  };
}
function getDialogMailFullScreenMargin() {
  var viewport=getDialogMailViewportSize();
  return (viewport.w <= dialogMailSmallScreenBreakpoint || viewport.h <= 1100) ? 30 : dialogMailFullScreenHorizontalMargin;
}
function getDialogMailAttachmentBlockWidth(rightPart) {
  var rightPartWidth=rightPart ? rightPart.clientWidth : dialogMailAttachmentBlockWidth;
  return Math.max(320, Math.min(dialogMailAttachmentBlockWidth, rightPartWidth - 20));
}
function getDialogMailAttachmentCells(row) {
  var cells=[];
  if (!row || !row.children) return cells;
  dojo.forEach(row.children, function(child) {
    if (child.tagName=='TD' || child.tagName=='TH') cells.push(child);
  });
  return cells;
}
function resizeDialogMailAttachmentTable(table, width) {
  if (!table) return;
  var tableWidth=Math.max(200, Math.floor(width));
  table.style.width=tableWidth+'px';
  table.style.maxWidth=tableWidth+'px';
  table.style.tableLayout='fixed';
  table.style.borderCollapse='collapse';
  dojo.query('tr', table).forEach(function(row) {
    var cells=getDialogMailAttachmentCells(row);
    var widths=(cells.length==5) ? [40,17,16,27,0] : ((cells.length==4) ? [40,17,16,27] : null);
    if (!widths) return;
    dojo.forEach(cells, function(cell, index) {
      cell.style.width=widths[index]+'%';
      cell.style.maxWidth=widths[index]+'%';
      cell.style.boxSizing='border-box';
      if (index==0 && table.id!='dialogMailTableHeader') {
        cell.style.textAlign='left';
        cell.style.paddingLeft='5px';
        cell.style.paddingRight='0';
      }
      dojo.forEach(cell.children, function(child) {
        if (child.tagName=='DIV') {
          child.style.width='100%';
          child.style.maxWidth='100%';
          child.style.boxSizing='border-box';
          if (index==0 && table.id!='dialogMailTableHeader') {
            child.style.marginLeft='0';
            child.style.textAlign='left';
          }
        }
      });
      if (index==cells.length-1) {
        cell.style.borderRight='2px solid #AAAAAA';
      }
    });
  });
}
function resizeDialogMailAttachmentArea() {
  var mailDialog=dijit.byId('dialogMail');
  var rightPart=getDialogMailNamedNode('dialogMailRightPartAttachment');
  var firstAttachmentArea=dojo.byId('showattachmentPJ');
  var addedAttachmentArea=dojo.byId('showAddAttachment');
  if (!mailDialog || !rightPart || !addedAttachmentArea) return;

  var fullScreen=dojo.hasClass(mailDialog.domNode, 'fullScreenDialog');
  var viewport=getDialogMailViewportSize();
  var compactScreen=viewport.w <= dialogMailSmallScreenBreakpoint;
  var attachmentWidth=fullScreen
    ? Math.max(300, Math.floor(rightPart.clientWidth - 10))
    : dialogMailAttachmentBlockWidth;

  dojo.forEach([
    dojo.byId('dialogMailLabelBeforeTable'),
    dojo.byId('dialogMailAddAttachmentButton'),
    dojo.byId('dialogMailTableAttachment'),
    dojo.byId('dialogMailTableHeader'),
    dojo.byId('showAttachment'),
    firstAttachmentArea,
    addedAttachmentArea
  ], function(node) {
    if (!node) return;
    node.style.width=attachmentWidth+'px';
    node.style.maxWidth=attachmentWidth+'px';
    node.style.boxSizing='border-box';
  });
  if (dojo.byId('showAttachment')) {
    dojo.byId('showAttachment').style.overflow='hidden';
  }
  dojo.forEach([firstAttachmentArea, addedAttachmentArea], function(node) {
    if (!node) return;
    node.style.overflowY='auto';
    node.style.overflowX='hidden';
    node.style.scrollbarGutter='stable';
  });

  // The compact popup already has the expected historical proportions.
  if (!fullScreen && compactScreen) {
    if (firstAttachmentArea) setDialogMailNodeHeight(firstAttachmentArea, dialogMailAttachmentDefaultHeight);
    setDialogMailNodeHeight(addedAttachmentArea, firstAttachmentArea ? dialogMailAddedAttachmentDefaultHeight : 435);
    if (dojo.byId('showAttachment')) {
      setDialogMailNodeHeight(dojo.byId('showAttachment'), dialogMailAttachmentDefaultHeight + dialogMailAddedAttachmentDefaultHeight);
    }
    var compactFirstWidth=firstAttachmentArea ? firstAttachmentArea.clientWidth : attachmentWidth;
    resizeDialogMailAttachmentTable(dojo.byId('dialogMailTableHeader'), compactFirstWidth);
    dojo.query('#showattachmentPJ table').forEach(function(table) {
      resizeDialogMailAttachmentTable(table, compactFirstWidth);
    });
    var compactAddedWidth=addedAttachmentArea.clientWidth || attachmentWidth;
    dojo.query('#showAddAttachment table').forEach(function(table) {
      resizeDialogMailAttachmentTable(table, compactAddedWidth);
    });
    return;
  }

  if (!firstAttachmentArea) return;
  var buttonTable=dojo.byId('dialogMailButtonOkCancel');
  var dialogRect=mailDialog.domNode.getBoundingClientRect();
  var firstRect=firstAttachmentArea.getBoundingClientRect();
  var bottomLimit=buttonTable
    ? buttonTable.getBoundingClientRect().top - dialogMailAttachmentButtonGap
    : dialogRect.bottom - 70;
  var availableHeight=Math.max(
    dialogMailAttachmentDefaultHeight + dialogMailAddedAttachmentDefaultHeight,
    Math.floor(bottomLimit - firstRect.top)
  );
  var firstHeight;
  var addedHeight;

  if (fullScreen && !compactScreen) {
    firstHeight=Math.floor((availableHeight - dialogMailAttachmentVerticalGap) / 2);
    addedHeight=availableHeight - dialogMailAttachmentVerticalGap - firstHeight;
  } else {
    addedHeight=dialogMailAddedAttachmentDefaultHeight;
    firstHeight=availableHeight - dialogMailAttachmentVerticalGap - addedHeight;
  }

  firstHeight=Math.max(dialogMailAttachmentDefaultHeight, firstHeight);
  addedHeight=Math.max(120, addedHeight);
  setDialogMailNodeHeight(firstAttachmentArea, firstHeight);
  setDialogMailNodeHeight(addedAttachmentArea, addedHeight);
  if (dojo.byId('showAttachment')) {
    setDialogMailNodeHeight(dojo.byId('showAttachment'), firstHeight + dialogMailAttachmentVerticalGap + addedHeight);
  }
  var firstContentWidth=firstAttachmentArea.clientWidth || attachmentWidth;
  var addedContentWidth=addedAttachmentArea.clientWidth || attachmentWidth;
  resizeDialogMailAttachmentTable(dojo.byId('dialogMailTableHeader'), firstContentWidth);
  dojo.query('#showattachmentPJ table').forEach(function(table) {
    resizeDialogMailAttachmentTable(table, firstContentWidth);
  });
  dojo.query('#showAddAttachment table').forEach(function(table) {
    resizeDialogMailAttachmentTable(table, addedContentWidth);
  });
}
function setDialogMailNodeHeight(node, height) {
  if (!node || !height) return;
  node.style.height=height+'px';
  node.style.minHeight=height+'px';
  node.style.maxHeight=height+'px';
}
function setDialogMailNodeBox(node, width, height) {
  if (!node) return;
  if (width) {
    node.style.width=width+'px';
    node.style.maxWidth=width+'px';
  }
  setDialogMailNodeHeight(node, height);
}
function getDialogMailNormalMessageHeight() {
  var mailDialog=dijit.byId('dialogMail');
  var mailEditor=CKEDITOR.instances['dialogMailMessage'];
  var messageNode=(mailEditor && mailEditor.container)
    ? mailEditor.container.$
    : (dojo.byId('mailMailEditor') ? dojo.byId('mailMailEditor') : dojo.byId('dialogMailMessage'));
  if (!mailDialog || !messageNode) return dialogMailNormalMessageHeight;
  var dialogRect=mailDialog.domNode.getBoundingClientRect();
  var messageRect=messageNode.getBoundingClientRect();
  var availableHeight=Math.floor(dialogRect.bottom - messageRect.top - dialogMailNormalMessageBottomMargin);
  return Math.max(90, availableHeight);
}
function isDialogMailCkEditorReady(mailEditor) {
  if (!mailEditor || mailEditor.status!='ready' || !mailEditor.container || !mailEditor.container.$ || !mailEditor.ui || !mailEditor.ui.space) return false;
  return !!mailEditor.ui.space('contents');
}
function resizeDialogMailMessageArea(width, height) {
  if (!height) return;
  if (dojo.byId('dialogMailMessage')) {
    setDialogMailNodeBox(dojo.byId('dialogMailMessage'), width, height);
  }
  if (dijit.byId('dialogMailMessage')) {
    var messageWidget=dijit.byId('dialogMailMessage');
    setDialogMailNodeBox(messageWidget.domNode, width, height);
    setDialogMailNodeHeight(messageWidget.textbox, height);
    setDialogMailNodeHeight(messageWidget.focusNode, height);
    if (messageWidget.resize) {
      var widgetBox={h:height};
      if (width) widgetBox.w=width;
      messageWidget.resize(widgetBox);
    }
  }
  var mailEditor=CKEDITOR.instances['dialogMailMessage'];
  if (isDialogMailCkEditorReady(mailEditor)) {
    if (width) {
      mailEditor.resize(width,height);
    } else {
      resizeDialogMailEditorFullScreen(height);
    }
  }
  if (dojo.byId('mailMailEditor')) {
    setDialogMailNodeBox(dojo.byId('mailMailEditor'), width, height);
  }
  if (dijit.byId('mailMailEditor')) {
    var mailEditorWidget=dijit.byId('mailMailEditor');
    setDialogMailNodeHeight(mailEditorWidget.domNode, height);
    setDialogMailNodeHeight(mailEditorWidget.editNode, height);
    if (mailEditorWidget.resize) mailEditorWidget.resize({h:height});
  }
}
function restoreDialogMailFullScreenLayout() {
  if (!oldMailFullScreenLayoutStyles) return;
  dojo.forEach(dialogMailFullScreenStyleIds, function(id) {
    restoreDialogMailStyle(id);
  });
  restoreDialogMailNodeStyle('leftPart', getDialogMailNamedNode('dialogMailLeftPartOptionEmailTemplateMessage'));
  restoreDialogMailNodeStyle('rightPart', getDialogMailNamedNode('dialogMailRightPartAttachment'));
  restoreDialogMailNodeStyle('receiverTableBox', dojo.query('#receiverTableContainer > div')[0]);
  restoreDialogMailNodeStyle('attachmentTable', dojo.query('#showattachmentPJ table')[0]);
  restoreDialogMailNodeStyle('paneContent', dojo.query('#dialogMail .dijitDialogPaneContent')[0]);
  if (dijit.byId('selectEmailTemplate') && oldMailFullScreenLayoutStyles.selectEmailTemplateWidget !== undefined) {
    dijit.byId('selectEmailTemplate').domNode.style.cssText=oldMailFullScreenLayoutStyles.selectEmailTemplateWidget;
  }
  if (dijit.byId('attachmentFileEmail') && oldMailFullScreenLayoutStyles.attachmentFileEmailWidget !== undefined) {
    dijit.byId('attachmentFileEmail').domNode.style.cssText=oldMailFullScreenLayoutStyles.attachmentFileEmailWidget;
  }
  oldMailFullScreenLayoutStyles=null;
}
function resetDialogMailFullScreenState() {
  restoreDialogMailFullScreenLayout();
  if (dojo.byId('dialogMailFullScreenIcon')) dojo.byId('dialogMailFullScreenIcon').className='fullScreenIcon';
  oldMailCkHeight=null;
}
function alignDialogMailFullScreenControls() {
  var selectWidget=dijit.byId('selectEmailTemplate');
  var leftPart=getDialogMailNamedNode('dialogMailLeftPartOptionEmailTemplateMessage');
  if (selectWidget && leftPart && selectWidget.domNode) {
    var leftPartRect=leftPart.getBoundingClientRect();
    var selectRect=selectWidget.domNode.getBoundingClientRect();
    var selectWidth=Math.max(250, Math.floor(leftPartRect.right - selectRect.left - 2));
    selectWidget.domNode.style.width=selectWidth+'px';
    if (selectWidget.resize) selectWidget.resize({w:selectWidth});
  }
  var uploaderWidget=dijit.byId('attachmentFileEmail');
  var uploaderNode=uploaderWidget ? uploaderWidget.domNode : dojo.byId('attachmentFileEmail');
  var rightPart=getDialogMailNamedNode('dialogMailRightPartAttachment');
  var attachmentBlockWidth=getDialogMailAttachmentBlockWidth(rightPart);
  var uploadTable=dojo.byId('dialogMailAddAttachmentButton');
  var uploadCells=uploadTable ? getDialogMailAttachmentCells(dojo.query('tr', uploadTable)[0]) : [];
  var uploadLabelWidth=190;
  if (uploadCells.length>=2) {
    uploadCells[0].style.width='auto';
    uploadCells[0].style.whiteSpace='nowrap';
    uploadLabelWidth=Math.max(150, Math.min(260, uploadCells[0].scrollWidth + 10));
  }
  var uploaderWidth=Math.max(220, attachmentBlockWidth - uploadLabelWidth);
  if (uploadTable) {
    uploadTable.style.width=attachmentBlockWidth+'px';
    uploadTable.style.marginLeft='auto';
    uploadTable.style.marginRight='0';
    uploadTable.style.tableLayout='fixed';
    if (uploadCells.length>=2) {
      uploadCells[0].style.width=uploadLabelWidth+'px';
      uploadCells[0].style.paddingRight='10px';
      uploadCells[0].style.boxSizing='border-box';
      uploadCells[1].style.width=uploaderWidth+'px';
      uploadCells[1].style.boxSizing='border-box';
    }
  }
  if (uploaderNode) uploaderNode.style.width=uploaderWidth+'px';
  if (uploaderWidget && uploaderWidget.resize) uploaderWidget.resize({w:uploaderWidth});
  if (dojo.byId('dialogMailSpanForButtonAddAttachment')) {
    dojo.byId('dialogMailSpanForButtonAddAttachment').style.display='block';
    dojo.byId('dialogMailSpanForButtonAddAttachment').style.left='155px';
    dojo.byId('dialogMailSpanForButtonAddAttachment').style.width=Math.max(120, uploaderWidth - 165)+'px';
    dojo.byId('dialogMailSpanForButtonAddAttachment').style.whiteSpace='nowrap';
    dojo.byId('dialogMailSpanForButtonAddAttachment').style.overflow='hidden';
    dojo.byId('dialogMailSpanForButtonAddAttachment').style.textOverflow='ellipsis';
  }
}
function applyDialogMailNormalLayoutAfterFullScreen() {
  var mailDialog=dijit.byId('dialogMail');
  var buttonTable=dojo.byId('dialogMailButtonOkCancel');
  var mailForm=dojo.byId('mailForm');
  var paneContent=dojo.query('#dialogMail .dijitDialogPaneContent')[0];
  if (mailDialog) {
    var normalBox=getDialogMailNormalBox();
    dojo.marginBox(mailDialog.domNode, normalBox);
    if (mailDialog.resize) mailDialog.resize(normalBox);
    if (mailDialog._position) mailDialog._position();
  }
  if (buttonTable) {
    if (dialogMailNormalButtonStyle !== null) {
      buttonTable.style.cssText=dialogMailNormalButtonStyle;
    }
  }
  if (mailForm) {
    mailForm.style.maxHeight='none';
    mailForm.style.overflowY='hidden';
    mailForm.style.overflowX='hidden';
  }
  if (paneContent) {
    paneContent.style.overflow='hidden';
  }
  resizeDialogMailMessageArea(dialogMailNormalMessageWidth, getDialogMailNormalMessageHeight());
  resizeDialogMailAttachmentArea();
}
function scheduleDialogMailNormalLayoutResize() {
  var resizeNormalMailDialog=function() {
    var mailDialog=dijit.byId('dialogMail');
    if (mailDialog && mailDialog.open && !dojo.hasClass(mailDialog.domNode, 'fullScreenDialog')) {
      applyDialogMailNormalLayoutAfterFullScreen();
    }
  };
  resizeNormalMailDialog();
  setTimeout(resizeNormalMailDialog, 50);
  setTimeout(resizeNormalMailDialog, 150);
  setTimeout(resizeNormalMailDialog, 400);
  setTimeout(resizeNormalMailDialog, 900);
  setTimeout(resizeNormalMailDialog, 1300);
  setTimeout(resizeNormalMailDialog, 1800);
}
function resizeDialogMailEditorFullScreen(ckHeight) {
  var mailEditor=CKEDITOR.instances['dialogMailMessage'];
  if (!isDialogMailCkEditorReady(mailEditor) || !ckHeight) return;
  var leftPart=getDialogMailNamedNode('dialogMailLeftPartOptionEmailTemplateMessage');
  var ckWidth=null;
  if (dojo.byId('dialogMailEmailTemplate')) ckWidth=dojo.byId('dialogMailEmailTemplate').clientWidth;
  if (!ckWidth && leftPart) ckWidth=leftPart.clientWidth;
  if (!ckWidth && mailEditor.container && mailEditor.container.$ && mailEditor.container.$.parentNode) ckWidth=mailEditor.container.$.parentNode.clientWidth;
  if (!ckWidth) ckWidth=600;
  if (mailEditor.container && mailEditor.container.$) {
    mailEditor.container.$.style.width=ckWidth+'px';
    mailEditor.container.$.style.maxWidth=ckWidth+'px';
  }
  mailEditor.resize(ckWidth,ckHeight);
}
function alignDialogMailFullScreenButtons(messageNode) {
  var mailDialog=dijit.byId('dialogMail');
  var buttonTable=dojo.byId('dialogMailButtonOkCancel');
  if (!mailDialog || !dojo.hasClass(mailDialog.domNode, 'fullScreenDialog') || !buttonTable || !messageNode) return;
  var messageRect=messageNode.getBoundingClientRect();
  var viewport=getDialogMailViewportSize();
  var buttonWidth=buttonTable.offsetWidth || 160;
  var buttonHeight=buttonTable.offsetHeight || 40;
  var rightSpaceStart=messageRect.right + dialogMailFullScreenButtonGap;
  var rightSpaceEnd=viewport.w - dialogMailFullScreenScreenPadding;
  var rightSpaceWidth=rightSpaceEnd - rightSpaceStart;
  var buttonLeft=(rightSpaceWidth > buttonWidth) ? rightSpaceStart + Math.floor((rightSpaceWidth - buttonWidth) / 2) : rightSpaceStart;
  buttonLeft=Math.min(buttonLeft, viewport.w - buttonWidth - dialogMailFullScreenScreenPadding);
  var buttonTop=Math.min(messageRect.bottom - Math.floor(buttonHeight / 2), viewport.h - buttonHeight - dialogMailFullScreenScreenPadding);
  buttonTop=Math.max(messageRect.top, buttonTop);
  buttonTable.style.position='fixed';
  buttonTable.style.left=buttonLeft+'px';
  buttonTable.style.top=buttonTop+'px';
  buttonTable.style.margin='0';
  buttonTable.style.zIndex='1';
}
function resizeDialogMailMessageFullScreen() {
  var mailDialog=dijit.byId('dialogMail');
  if (!mailDialog || !dojo.hasClass(mailDialog.domNode, 'fullScreenDialog')) return;
  var mailEditor=CKEDITOR.instances['dialogMailMessage'];
  var dialogRect=mailDialog.domNode.getBoundingClientRect();
  var mailTarget=(mailEditor && mailEditor.container) ? mailEditor.container.$ : (dojo.byId('mailMailEditor') ? dojo.byId('mailMailEditor') : dojo.byId('dialogMailMessage'));
  var targetRect=mailTarget ? mailTarget.getBoundingClientRect() : null;
  var messageHeight=targetRect ? Math.floor(dialogRect.height - (targetRect.top - dialogRect.top) - dialogMailFullScreenMessageBottomMargin) : mailDialog.domNode.offsetHeight-420;
  messageHeight=Math.max(150, messageHeight);
  resizeDialogMailMessageArea(null, messageHeight);
  alignDialogMailFullScreenButtons(mailTarget);
  resizeDialogMailAttachmentArea();
}
function scheduleDialogMailFullScreenMessageResize() {
  var resizeFullScreenMessage=function() {
    resizeDialogMailMessageFullScreen();
  };
  resizeFullScreenMessage();
  setTimeout(resizeFullScreenMessage, 100);
  setTimeout(resizeFullScreenMessage, 300);
  setTimeout(resizeFullScreenMessage, 600);
}
function applyDialogMailFullScreenLayout() {
  oldMailFullScreenLayoutStyles={};
  if (dojo.byId('dialogMailButtonOkCancel') && dialogMailNormalButtonStyle === null) {
    dialogMailNormalButtonStyle=dojo.byId('dialogMailButtonOkCancel').style.cssText;
  }
  dojo.forEach(dialogMailFullScreenStyleIds, function(id) {
    storeDialogMailStyle(id);
  });
  var leftPart=getDialogMailNamedNode('dialogMailLeftPartOptionEmailTemplateMessage');
  var rightPart=getDialogMailNamedNode('dialogMailRightPartAttachment');
  var receiverTableBox=dojo.query('#receiverTableContainer > div')[0];
  var attachmentTable=dojo.query('#showattachmentPJ table')[0];
  storeDialogMailNodeStyle('leftPart', leftPart);
  storeDialogMailNodeStyle('rightPart', rightPart);
  storeDialogMailNodeStyle('receiverTableBox', receiverTableBox);
  storeDialogMailNodeStyle('attachmentTable', attachmentTable);
  storeDialogMailNodeStyle('paneContent', dojo.query('#dialogMail .dijitDialogPaneContent')[0]);
  if (dijit.byId('selectEmailTemplate')) oldMailFullScreenLayoutStyles.selectEmailTemplateWidget=dijit.byId('selectEmailTemplate').domNode.style.cssText;
  if (dijit.byId('attachmentFileEmail')) oldMailFullScreenLayoutStyles.attachmentFileEmailWidget=dijit.byId('attachmentFileEmail').domNode.style.cssText;
}
function resizeDialogMailFullScreenWidget() {
  var mailDialog=dijit.byId('dialogMail');
  if (!mailDialog) return;
  var viewport=getDialogMailViewportSize();
  mailDialog.domNode.style.position='fixed';
  mailDialog.domNode.style.left='0px';
  mailDialog.domNode.style.top='0px';
  mailDialog.domNode.style.right='auto';
  mailDialog.domNode.style.bottom='auto';
  mailDialog.domNode.style.margin='0px';
  mailDialog.domNode.style.width=viewport.w+'px';
  mailDialog.domNode.style.height=viewport.h+'px';
  mailDialog.domNode.style.maxWidth=viewport.w+'px';
  mailDialog.domNode.style.maxHeight=viewport.h+'px';
  if (mailDialog.resize) mailDialog.resize({w:viewport.w,h:viewport.h});
}
function applyDialogMailFullScreenLayoutSize() {
  var leftPart=getDialogMailNamedNode('dialogMailLeftPartOptionEmailTemplateMessage');
  var rightPart=getDialogMailNamedNode('dialogMailRightPartAttachment');
  var receiverTableBox=dojo.query('#receiverTableContainer > div')[0];
  var attachmentTable=dojo.query('#showattachmentPJ table')[0];
  var mailDialog=dijit.byId('dialogMail');
  var dialogContentNode=(mailDialog && mailDialog.containerNode) ? mailDialog.containerNode : (mailDialog ? mailDialog.domNode : null);
  var renderedDialogWidth=dialogContentNode ? dialogContentNode.clientWidth : (window.innerWidth || document.documentElement.clientWidth || screen.width);
  var fullScreenMargin=getDialogMailFullScreenMargin();
  var fullScreenContentWidth=Math.max(760, renderedDialogWidth - (fullScreenMargin * 2));
  if (dojo.byId('dialogMailGeneralTable')) {
    dojo.byId('dialogMailGeneralTable').style.width=fullScreenContentWidth+'px';
    dojo.byId('dialogMailGeneralTable').style.maxWidth='none';
    dojo.byId('dialogMailGeneralTable').style.margin='10px '+fullScreenMargin+'px 0 '+fullScreenMargin+'px';
    dojo.byId('dialogMailGeneralTable').style.tableLayout='fixed';
  }
  if (leftPart) {
    leftPart.style.width='55%';
    leftPart.style.maxWidth='none';
    leftPart.style.paddingRight='40px';
  }
  if (rightPart) {
    rightPart.style.width='45%';
    rightPart.style.maxWidth='none';
    rightPart.style.textAlign='right';
  }
  var attachmentBlockWidth=getDialogMailAttachmentBlockWidth(rightPart);
  if (dojo.byId('dialogMailGlobalTop')) dojo.byId('dialogMailGlobalTop').style.width='100%';
  if (dojo.byId('dialogMailEmailTemplate')) dojo.byId('dialogMailEmailTemplate').style.width='100%';
  if (dojo.byId('dialogMailMessage')) {
    dojo.byId('dialogMailMessage').style.width='100%';
    dojo.byId('dialogMailMessage').style.maxWidth='none';
  }
  if (dojo.byId('mailMailEditor')) dojo.byId('mailMailEditor').style.width='100%';
  if (dijit.byId('selectEmailTemplate')) dijit.byId('selectEmailTemplate').domNode.style.width='100%';
  if (dojo.byId('receiverTableContainer')) dojo.byId('receiverTableContainer').style.width='100%';
  if (receiverTableBox) receiverTableBox.style.width='100%';
  if (dojo.byId('dialogMailLabelBeforeTable')) {
    dojo.byId('dialogMailLabelBeforeTable').style.width=attachmentBlockWidth+'px';
    dojo.byId('dialogMailLabelBeforeTable').style.marginLeft='auto';
    dojo.byId('dialogMailLabelBeforeTable').style.marginRight='0';
  }
  if (dojo.byId('showAddAttachment')) {
    dojo.byId('showAddAttachment').style.width=attachmentBlockWidth+'px';
    dojo.byId('showAddAttachment').style.marginLeft='auto';
    dojo.byId('showAddAttachment').style.marginRight='0';
    dojo.byId('showAddAttachment').style.textAlign='right';
  }
  if (dojo.byId('showattachmentPJ')) {
    dojo.byId('showattachmentPJ').style.width=attachmentBlockWidth+'px';
    dojo.byId('showattachmentPJ').style.marginLeft='auto';
    dojo.byId('showattachmentPJ').style.marginRight='0';
  }
  if (attachmentTable) attachmentTable.style.width=attachmentBlockWidth+'px';
  alignDialogMailFullScreenControls();
  resizeDialogMailAttachmentArea();
}
function toggleFullScreenDialog(dialog) {
  if (dojo.hasClass(dijit.byId(dialog).domNode, 'fullScreenDialog')) {
    dojo.toggleClass(dijit.byId(dialog).domNode, 'fullScreenDialog', false);
    dojo.byId(dialog+'FullScreenIcon').className='fullScreenIcon';
    if (dialog=="dialogPrint") {
      dojo.byId('printFrame').style.width=oldPrintFrameWidth+'px';
      dojo.byId('printFrame').style.height=oldPrintFrameHeight+'px';
      dojo.byId('printDialogFrameContainer').style.width=oldPrintWidth+'px';
      dojo.byId('printDialogFrameContainer').style.height=oldPrintHeight+'px';
      oldPrintWidth=null;
      oldPrintHeight=null;
      oldPrintFrameWidth=null;
      oldPrintFrameHeight=null;
    } else if (dialog=="dialogNote") {
      var editor=CKEDITOR.instances['noteNote'];
      if (editor && oldCkHeight) editor.resize(null,oldCkHeight);
      oldCkHeight=null;
    } else if (dialog=="dialogMail") {
      resetDialogMailFullScreenState();
      applyDialogMailNormalLayoutAfterFullScreen();
    } else if (dialog=="dialogShowHtml") {
      dojo.byId('showHtmlFrame').style.width=oldPrintFrameWidth+'px';
      dojo.byId('showHtmlFrame').style.height=oldPrintFrameHeight+'px';
      dojo.byId('showHtmlContainer').style.width=oldPrintWidth+'px';
      dojo.byId('showHtmlContainer').style.height=oldPrintHeight+'px';
      oldPrintWidth=null;
      oldPrintHeight=null;
      oldPrintFrameWidth=null;
      oldPrintFrameHeight=null;
    }
  } else {
    if (dialog=="dialogPrint") {
      oldPrintWidth=dojo.byId('printDialogFrameContainer').offsetWidth;
      oldPrintHeight=dojo.byId('printDialogFrameContainer').offsetHeight;
      oldPrintFrameWidth=dojo.byId('printFrame').offsetWidth;
      oldPrintFrameHeight=dojo.byId('printFrame').offsetHeight;
    } else if (dialog=="dialogNote") {
      var editor=CKEDITOR.instances['noteNote'];
      oldCkHeight=editor.container.$.clientHeight - 102;
    } else if (dialog=="dialogMail") {
      var mailEditor=CKEDITOR.instances['dialogMailMessage'];
      if (mailEditor && mailEditor.editable && mailEditor.editable()) {
        oldMailCkHeight=mailEditor.editable().$.clientHeight;
      } else if (mailEditor && mailEditor.container) {
        oldMailCkHeight=mailEditor.container.$.clientHeight - 102;
      }
    } else if (dialog=="dialogShowHtml") {
      oldPrintWidth=dojo.byId('showHtmlContainer').offsetWidth;
      oldPrintHeight=dojo.byId('showHtmlContainer').offsetHeight;
      oldPrintFrameWidth=dojo.byId('showHtmlFrame').offsetWidth;
      oldPrintFrameHeight=dojo.byId('showHtmlFrame').offsetHeight;
    }
    dojo.toggleClass(dijit.byId(dialog).domNode, 'fullScreenDialog', true);
    dojo.byId(dialog+'FullScreenIcon').className='fullScreenReverseIcon';
    if (dialog=="dialogPrint") {
      frameWidth=dijit.byId(dialog).domNode.offsetWidth-20;
      dojo.byId('printFrame').style.width=(frameWidth)+'px';
      frameHeight=dijit.byId(dialog).domNode.offsetHeight-65;
      if (dojo.byId('sentToPrinterDiv') && dojo.byId('sentToPrinterDiv').style.display=='block') frameHeight-=36;
      dojo.byId('printFrame').style.height=(frameHeight)+'px';
    } else if (dialog=="dialogNote") {
      ckHeight=dijit.byId(dialog).domNode.offsetHeight-170;
      if (! dijit.byId('dialogNotePredefinedNote')) ckHeight+=40;
      var editor=CKEDITOR.instances['noteNote'];
      if (editor && ckHeight) editor.resize(null,ckHeight);
    } else if (dialog=="dialogMail") {
      applyDialogMailFullScreenLayout();
      resizeDialogMailFullScreenWidget();
      applyDialogMailFullScreenLayoutSize();
      scheduleDialogMailFullScreenMessageResize();
      setTimeout(function() {
        if (dojo.hasClass(dijit.byId('dialogMail').domNode, 'fullScreenDialog')) {
          resizeDialogMailFullScreenWidget();
          applyDialogMailFullScreenLayoutSize();
          scheduleDialogMailFullScreenMessageResize();
        }
      }, 100);
      if (dojo.byId('mailForm')) {
        dojo.byId('mailForm').style.maxHeight='none';
        dojo.byId('mailForm').style.overflowY='hidden';
      }
      if (dojo.query('#dialogMail .dijitDialogPaneContent')[0]) dojo.query('#dialogMail .dijitDialogPaneContent')[0].style.overflow='hidden';
    } else if (dialog=="dialogShowHtml") {
      frameWidth=dijit.byId(dialog).domNode.offsetWidth-20;
      dojo.byId('showHtmlFrame').style.width=(frameWidth)+'px';
      frameHeight=dijit.byId(dialog).domNode.offsetHeight-65;
      dojo.byId('showHtmlFrame').style.height=(frameHeight)+'px';
    } 
  }
}
function removeFullScreenDialog(dialog, applyNormalLayout) {
  if (dialog=="dialogPrint" && oldPrintWidth) {
    dojo.byId('printFrame').style.width=oldPrintFrameWidth+'px';
    dojo.byId('printFrame').style.height=oldPrintFrameHeight+'px';
    dojo.byId('printDialogFrameContainer').style.width=oldPrintWidth+'px';
    dojo.byId('printDialogFrameContainer').style.height=oldPrintHeight+'px';
    dojo.byId(dialog+'FullScreenIcon').className='fullScreenIcon';
    oldPrintWidth=null;
    oldPrintHeight=null;
    oldPrintFrameWidth=null;
    oldPrintFrameHeight=null;
  } else if (dialog=="dialogShowHtml" && oldPrintWidth) {
    dojo.byId('showHtmlFrame').style.width=oldPrintFrameWidth+'px';
    dojo.byId('showHtmlFrame').style.height=oldPrintFrameHeight+'px';
    dojo.byId('showHtmlContainer').style.width=oldPrintWidth+'px';
    dojo.byId('showHtmlContainer').style.height=oldPrintHeight+'px';
    dojo.byId(dialog+'FullScreenIcon').className='fullScreenIcon';
    oldPrintWidth=null;
    oldPrintHeight=null;
    oldPrintFrameWidth=null;
    oldPrintFrameHeight=null;
  } else if (dialog=="dialogMail" && dijit.byId(dialog) && dojo.hasClass(dijit.byId(dialog).domNode, 'fullScreenDialog')) {
    dojo.toggleClass(dijit.byId(dialog).domNode, 'fullScreenDialog', false);
    resetDialogMailFullScreenState();
    if (applyNormalLayout) applyDialogMailNormalLayoutAfterFullScreen();
    else dijit.byId(dialog).domNode.style.display='none';
  }
  if (dijit.byId(dialog)) dojo.toggleClass(dijit.byId(dialog).domNode, 'fullScreenDialog', false);
}

var synchResizeTimeout = null;
var saveLeftSizeTimeout = null;
var synchResizeInProgress = false;
var refreshDetailPlanningWorkPlanTimeout=null;
function synchResizePlanningWorkPlan(paneToResize){
  if(synchResizeInProgress)return;
  synchResizeInProgress = true;
  var globalDivSize = dojo.byId('globalDivBorderContainer').offsetWidth;
  var divContainer=(paneToResize == 'contentDetailDiv')?'workPlanDivContainer':'planningDivContainer';
  var rightPane=(paneToResize == 'contentDetailDiv')?'workPlanDivContent':'GanttChartDIV';
  var synchPane=(paneToResize == 'contentDetailDiv')?'leftGanttChartDIV':'contentDetailDiv';
  var duration = 0;
  var leftSize = dojo.byId(synchPane).offsetWidth;
  var rightSize = (globalDivSize-leftSize)-5;
  if (!isHtml5()) {
    dijit.byId(paneToResize).resize({
      w : leftSize
    });
    dijit.byId(rightPane).resize({
      w : rightSize
    });
    duration=0;
  } else {
    dojox.fx.combine([
      dojox.fx.animateProperty({
        node : paneToResize,
        properties : {
          width : leftSize
        },
        duration : duration
      }),
      dojox.fx.animateProperty({
        node : rightPane,
        properties : {
          width : rightSize
        },
        duration : duration
      })
      ]).play();
  }
  resizeContainer(divContainer, 0);
  if (saveLeftSizeTimeout) clearTimeout(saveLeftSizeTimeout);
  saveLeftSizeTimeout = setTimeout("saveUserParameter('planningWorkPlanLeftSize','"+leftSize+"px');",50);
  if (synchResizeTimeout) clearTimeout(synchResizeTimeout);
  synchResizeTimeout = setTimeout('synchResizeInProgress = false', 10);
  if (refreshDetailPlanningWorkPlanTimeout) clearTimeout(refreshDetailPlanningWorkPlanTimeout);
  // Resizing the auto-hidden left menu must only resize the work-plan panes.
  // Its resize notifications are asynchronous, so closeOpenLeftMenu may already
  // be reset when they arrive. The menu action timestamp covers that full cycle.
  var leftMenuAutoHideInProgress=(typeof isPlanningWorkPlanLeftMenuAutoHideInProgress == 'function'
      && isPlanningWorkPlanLeftMenuAutoHideInProgress());
  if(!formChangeInProgress && !closeOpenLeftMenu && !leftMenuAutoHideInProgress){
    refreshDetailPlanningWorkPlanTimeout=setTimeout("if (dijit.byId('refreshButton')) dijit.byId('refreshButton').onClick();",500);
  }
}

function diaryGotoTimesheet(user, year, week, date, idAssignment){
  if (checkFormChangeInProgress()) {
    return;
  }
  var callback = accessImputationCallBack(true);
  saveDataToSession('userName',user,false, function() {
    saveDataToSession('yearSpinner',year,false, function() {
      saveDataToSession('weekSpinner',week,false, function() {
        saveDataToSession('dateSelector',date,false, function() {
          loadContent('../view/imputationMain.php?idAssignment='+idAssignment+'&focusDate='+date,'centerDiv',null,null,null,null,null,callback);
        });
      });
    });
  });
}

function filterParameter(searchValue){
	var parameterSearchMenu = dijit.byId('parameterSearchMenu');
	var parameterSeachCancel = dojo.byId('clearSearchInputParameter');
	var searchFound = false;
	var parameterArray = new Array();
	var searchValue = searchValue.toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "");
	dojo.query('.parameterSearchSection').forEach(function(node){
		node.style.display = 'none';
	});
	dojo.query('.parameterSearchName').forEach(function(node){
		var parameterName = node.innerHTML.toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "");
		var parameterId = node.id.replace('searchFor', '');
		var sectionName = 'section_'+dojo.byId('sectionFor'+parameterId).value;
		if(parameterName.indexOf(searchValue) != -1){
			parameterArray[parameterId]=sectionName;
			node.style.display = '';
			searchFound = true;
		}else{
			node.style.display = 'none';
		}
	});
	Object.entries(parameterArray).forEach(([idParameter, sectionName]) => {
		var section = dojo.byId(sectionName);
		if(section)section.style.display = '';
	});
	var noParameterFound = dojo.byId('noSearchParamaterFound');
	if(noParameterFound){
		if(!searchFound){
			noParameterFound.style.display = '';
		}else{
			noParameterFound.style.display = 'none';
		}
	}
	if(searchValue){
		parameterSeachCancel.style.display = '';
		parameterSearchMenu.openDropDown();
	}else{
		parameterSeachCancel.style.display = 'none';
		parameterSearchMenu.closeDropDown();
	}
}

function selectSearchParameter(tabName, tabSection, tabField, tabType){
	redirectOnParameter(tabName, tabSection, tabField, tabType);
}

function clearSearchInputParameter(){
	var parameterSearchInput = dojo.byId('parameterSearchFilterInput');
	var parameterSeachCancel = dojo.byId('clearSearchInputParameter');
	var parameterSearchMenu = dijit.byId('parameterSearchMenu');
	if(parameterSearchInput){
		parameterSearchInput.value = '';
		parameterSeachCancel.style.display = 'none';
		parameterSearchMenu.closeDropDown();
	}
	dojo.query('.parameterFocusTitlePane').forEach(function(node){
		dojo.removeClass(node, 'parameterFocusTitlePane');
	});
	dojo.query('.parameterFocusLine').forEach(function(node){
		dojo.removeClass(node, 'parameterFocusLine');
	});
	dojo.query('.parameterFocusLabel').forEach(function(node){
		dojo.removeClass(node, 'parameterFocusLabel');
	});
}

function addNewOauthSource() {
  param='&idOAuth=';
  loadDialog('dialogOAuthSource',null,true,param); 
}
function editOauthSource() {
  if (! dijit.byId('idOAuthClient') || ! trim(dijit.byId('idOAuthClient').get('value'))) {
    showAlert(i18n('selectSourceFirst'));
    return;
  }
  param='&idOAuth='+trim(dijit.byId('idOAuthClient').get('value'));
  loadDialog('dialogOAuthSource',null,true,param); 
}
function getOauthToken() {
  dojo.xhrPost({
    url:"../tool/saveOAuthClient.php?action=getToken"+addTokenIndexToUrl(),
    form:"oauthManagement",
    handleAs:"text",
    load:function(data) {
      values=data.split('|');
      dijit.byId('dialogOAuthSource').hide();
      if (values.length!=2) {
        showError(i18n("planningResultError")+"<br/>"+data);
        return;
      }
      window.open(values[1],'_blank');
      refreshList('idOAuthClient', null, null, values[0]);
      setTimeout('dijit.byId("idOAuthClient").set("value",'+values[0]+');formChanged();',3000);
    },
    error:function() {
      hideWait();
    }
  });
}

function saveOAuth() {
  dojo.xhrPost({
    url:"../tool/saveOAuthClient.php?action=getToken"+addTokenIndexToUrl(),
    form:"oauthManagement",
    handleAs:"text",
    load:function(data) {
      values=data.split('|');
      dijit.byId('dialogOAuthSource').hide();
      if (values.length!=2) {
        showError(i18n("planningResultError")+"<br/>"+data);
        return;
      }
      refreshList('idOAuthClient', null, null, values[0]);
      setTimeout('dijit.byId("idOAuthClient").set("value",'+values[0]+');formChanged();',1000);
    },
    error:function() {
      hideWait();
    }
  });
}

function deleteOauthSource() {
  var idOauthClient=trim(dijit.byId('idOAuthClient').get("value"));
  if (! idOauthClient) {
    showAlert(i18n("noItemSelected"));
    return;
  }
  var actionOK=function() {
    var url="../tool/deleteOAuthClient.php?id="+dijit.byId('idOAuthClient').get("value")+addTokenIndexToUrl();
    dojo.xhrPost({
      url: url,
      handleAs:"text",
      load:function(data) {
        refreshList('idOAuthClient', null, null, null);
        setTimeout('dijit.byId("idOAuthClient").set("value",null);formChanged();',1000);
      },
      error:function() {
        hideWait();
      }
    });
  };
  var msg=i18n("confirmDelete", new Array(i18n("colIdOAuthClient"),  idOauthClient+" ("+dijit.byId('idOAuthClient').get("displayedValue")+")") );
  showConfirm(msg,actionOK);
}
function addAttachmentProfilePic(idUser) {
  addAttachment('file','User',idUser,'profilePic');
  var funcRetry="addAttachment('file','User',"+idUser+",'profilePic');";
  setTimeout(funcRetry,100);
}

function addUserStory(objClass, objId){
  var callBack=function() {
    dijit.byId("dialogUserStory").show();
	refreshUserStoryList();
  };
  var params="&objectClass=" + objClass + "&objectId=" + objId;
  loadDialog('dialogUserStory',callBack,false,params);
}

var norefreshUserStoryList=false;
function refreshUserStoryList(selected) {
  if (norefreshUserStoryList)
    return;
  disableWidget('dialogUserStorySubmit');
  var url='../tool/dynamicListUserStory.php';
  if (selected) {
    url+='?selected=' + selected;
  }
  loadContent(url, 'dialogUserStoryList', 'userStoryForm', false);
}

function saveUserStory() {
  var formVar=dijit.byId('userStoryForm');
  if (formVar.validate()) {
    loadContent("../tool/saveUserStory.php","resultDivMain","userStoryForm",true,null,false);
    dijit.byId('dialogUserStory').hide();
  } else {
    showAlert(i18n("alertInvalidForm"));
  }
}

function removeUserStory(objClass, id) {
  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
  actionOK=function() {
    loadContent("../tool/saveUserStory.php?mode=delete&userStoryId=" + id + '&objectClass=' + objClass,"resultDivMain","listForm",true,null,false);
  };
  msg=i18n('confirmDeleteUserStory',new Array(id,i18n('UserStory')));
  showConfirm(msg,actionOK);
}


//facturX function
function importFacturXOnFileChange(input){
  var label = dojo.byId('importFacturXFileLabel');
  if(!label){ return; }

  if(!input.files || !input.files.length){
    label.style.color = "#999";
    label.style.fontStyle = "italic";
    return;
  }

  var fileName = input.files[0].name || "";
  label.textContent = fileName;
  label.style.color = "#444";
  label.style.fontStyle = "normal";
}

//------------------------------------------
// D&D Import FacturX
//------------------------------------------
window.importFacturXDragEnter = function(e){
  e.preventDefault();
  var z = dojo.byId('importFacturXFileLabel');
  if(z){ z.style.borderColor = '#BBBBBB'; }
};

window.importFacturXDragOver = function(e){
  e.preventDefault();
  if (e.dataTransfer) e.dataTransfer.dropEffect = 'copy';
};

window.importFacturXDragLeave = function(e){
  e.preventDefault();
  var z = dojo.byId('importFacturXFileLabel');
  if(z){ z.style.borderColor = '#EEEEEE'; }
};

window.importFacturXDrop = function(e){
  e.preventDefault();

  var z = dojo.byId('importFacturXFileLabel');
  if(z){ z.style.borderColor = '#EEEEEE'; }

  var input = dojo.byId('pdfFacturxExtract');
  if(!input || !e.dataTransfer || !e.dataTransfer.files || !e.dataTransfer.files.length){
    return;
  }

  var file = e.dataTransfer.files[0];

  try {
    var dt = new DataTransfer();
    dt.items.add(file);
    input.files = dt.files;
  } catch(err) {
    try {
      if(window.top && window.top.showError) window.top.showError('Drag and drop non supporté ici, utilisez Browse.');
      else alert('Drag and drop non supporté ici, utilisez Browse.');
    } catch(ex) {}
    return;
  }

  window.importFacturXOnFileChange(input);
};
//------------------------------------------
