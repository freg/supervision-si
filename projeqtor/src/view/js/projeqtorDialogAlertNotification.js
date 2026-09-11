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

// ====================================================================================
// ALERTS and NOTIFICATIONS
// ====================================================================================

function checkNotificationAsWindows(){
  var notif = checkAlertNotification();
  if(notif=='YES'){
    checkDisplayNotificationTree();
  }
  return notif;
}

function checkAlertNotification(){
  var notif = 'NO';
  if (!('Notification' in window)) {
  }else if (Notification.permission === 'granted') {
    notif = 'YES';
  }else if (Notification.permission !== 'denied') {
    Notification.requestPermission().then((permission) => {
      if (permission === 'granted') {
        notif = 'YES';
      }
    })
  }else if(Notification.permission === 'denied'){
  }
  return notif;
}

var checkDisplayNotificationTreeRetry=0;
function checkDisplayNotificationTree() {
  dojo.xhrGet({
    url : "../tool/checkAlertToDisplayNotificationTree.php"+addTokenIndexToUrl('?'),
    handleAs : "text",
    load : function(data, args) {
      checkDisplayNotificationTreeRetry=0;
      displayNotificationTree(data);
    },
    error : function() {
      if (!alertCheckTime) alertCheckTime=10;
      checkDisplayNotificationTreeRetry++;
      if (alertCheckTime>0) setTimeout('checkDisplayNotificationTree();', alertCheckTime * 1000 * checkDisplayNotificationTree);
    }
  });
}

function displayNotificationTree(data) {
  arrayData=data.split('#!#!#!#!#!#');
  size = arrayData.length;
  for (var i = 1; i < size; i=i+3) {
    var title = arrayData[i];
    var text = arrayData[i+1];
    var img = '';
    var idNotification = arrayData[i+2];
// if(iconText=='ALERT'){
// img = '../view/css/images/iconAlert.png';
// }
// if(iconText=='WARNING'){
// img = '../view/css/images/iconWarning.png';
// }
// if(iconText=='INFO'){
// img = '../view/css/images/iconInformation.png';
// }
    img = '../view/img/logoSmall.png';
    const notification  = new Notification(title, { body: text, icon: img , tag : idNotification , requireInteraction : true });
    notification.onclick = function () {
      dojo.xhrGet({
        url : '../tool/getSingleData.php?dataType=NotificationTree'
            +'&idNotification='+notification.tag
            +addTokenIndexToUrl(),
        handleAs : "text",
        load : function(data, args) {
          arrayDatas=data.split('#!#!#!#!#!#');
          if(arrayDatas[0]=='')return;
          gotoElement(arrayDatas[0],arrayDatas[1]);
        },
      });
    };
    notification.onclose = function () {
    var param="?idNotification="+notification.tag;
    dojo.xhrGet({
      url : "../tool/readNotificationTree.php"+param+addTokenIndexToUrl(),
      handleAs : "text",
      load : function(data, args) {
      },
    });
  };
  }
  if (alertCheckTime>0) setTimeout('checkDisplayNotificationTree();', alertCheckTime * 1000);
}

// gautier #5915
function checkAlert(){
  if (!('Notification' in window)) {
    checkRealAlert();
  }else if (Notification.permission === 'granted') {
    checkDisplayNotification();
  }else if (Notification.permission !== 'denied') {
    Notification.requestPermission().then((permission) => {
      if (permission === 'granted') {
        checkDisplayNotification();
      }
    })
  }else if(Notification.permission === 'denied'){
    checkRealAlert();
  } else {
    error.log("ERROR : Notification.permission = '"+Notification.permission+"' not expected");
  }
}

function checkDisplayNotification() {
  dojo.xhrGet({
    url : "../tool/checkAlertToDisplayNotification.php"+addTokenIndexToUrl('?'),
    handleAs : "text",
    load : function(data, args) {
      displayNotification(data);
    },
    error : function() {
      if (alertCheckTime>0) setTimeout('checkDisplayNotification();', alertCheckTime * 1000);
    }
  });
}

function displayNotification(data) {
  explode=data.split('##!##!##!##!##!##');
  data=explode[0];
  if (data.indexOf('name="lastOperation" value="testConnection"')>0 && data.indexOf('name="lastOperationStatus" value="ERROR"')>0) {
    showDisconnectedMessage(data);
  }
  var reminderDiv=dojo.byId('reminderDiv');
  var dialogReminder=dojo.byId('dialogReminder');
  reminderDiv.innerHTML=data;
  if (dojo.byId("cronStatusRefresh") && dojo.byId("cronStatusRefresh").value != "") {
    refreshCronIconStatus(dojo.byId("cronStatusRefresh").value);
  }
  if (dojo.byId("requestRefreshProject")&& dojo.byId("requestRefreshProject").value == "true") {
    refreshProjectSelectorList();
    // if (alertCheckTime>0) setTimeout('checkAlert();', alertCheckTime * 1000);
  } else if (dojo.byId("alertNeedStreamRefresh") && dojo.byId("alertNeedStreamRefresh").value>0) {
    loadContent("objectStream.php?onlyCenter=true", "activityStreamCenter", "listForm");
    // if (alertCheckTime>0) setTimeout('checkAlert();', alertCheckTime * 1000);
  }
  if ( data.indexOf('<input type="hidden" id="alertType" name="alertType"')>0) {
    // Keep data to display alert
  } else if (explode.length>1) {
    data=explode[1];
  }
  arrayData=data.split('#!#!#!#!#!#');
  size = arrayData.length;
  for (var i = 1; i < size; i=i+4) {
    var title = arrayData[i];
    var text = arrayData[i+1];
    var iconText = arrayData[i+2];
    var img = '';
    var idNotification = arrayData[i+3];
// if(iconText=='ALERT'){
// img = '../view/css/images/iconAlert.png';
// }
// if(iconText=='WARNING'){
// img = '../view/css/images/iconWarning.png';
// }
// if(iconText=='INFO'){
// img = '../view/css/images/iconInformation.png';
// }
    img = '../view/img/logoSmall.png';
    const notification  = new Notification(title, { body: text, icon: img , tag : idNotification , requireInteraction : true });
    notification.onclick = function () {
      var param="?dataType='"+notification.tag;
      dojo.xhrGet({
        url : '../tool/getSingleData.php?dataType=Notification'
            +'&idNotification='+notification.tag
            +addTokenIndexToUrl(),
        handleAs : "text",
        load : function(data, args) {
          arrayDatas=data.split('#!#!#!#!#!#');
          if(arrayDatas[0]=='')return;
          gotoElement(arrayDatas[0],arrayDatas[1]);
        },
      });

    };
    notification.onclose = function () {
    var param="?idNotification="+notification.tag;
    dojo.xhrGet({
      url : "../tool/readNotification.php"+param+addTokenIndexToUrl(),
      handleAs : "text",
      load : function(data, args) {
      },
    });
  };
  }
  if (alertCheckTime>0) setTimeout('checkAlert();', alertCheckTime * 1000);
}

// var alertDisplayed=false;
var checkAlertDisplayQuick=false;
var checkAlertOpenInProgress=false;

function checkRealAlert() {
  dojo.xhrGet({
    url : "../tool/checkAlertToDisplay.php"+addTokenIndexToUrl('?'),
    handleAs : "text",
    load : function(data, args) {
      checkAlertRetour(data);
    },
    error : function() {
      if (alertCheckTime>0) setTimeout('checkRealAlert();', alertCheckTime * 1000);
    }
  });
}

function checkAlertRetour(data) {
  if (data) {
    if (data.indexOf('name="lastOperation" value="testConnection"')>0 && data.indexOf('name="lastOperationStatus" value="ERROR"')>0) {
      showDisconnectedMessage(data);
    }
    var reminderDiv=dojo.byId('reminderDiv');
    var dialogReminder=dojo.byId('dialogReminder');
    reminderDiv.innerHTML=data;
    if (dojo.byId("cronStatusRefresh") && dojo.byId("cronStatusRefresh").value != "") {
      refreshCronIconStatus(dojo.byId("cronStatusRefresh").value);
    }
    if (dojo.byId("requestRefreshProject")&& dojo.byId("requestRefreshProject").value == "true") {
      refreshProjectSelectorList();
      if (alertCheckTime>0) setTimeout('checkAlert();', alertCheckTime * 1000);
    } else if (dojo.byId("alertNeedStreamRefresh") && dojo.byId("alertNeedStreamRefresh").value>0) {
      loadContent("objectStream.php?onlyCenter=true", "activityStreamCenter", "listForm");
      if (alertCheckTime>0) setTimeout('checkAlert();', alertCheckTime * 1000);
    } else if (dojo.byId('alertType')) {
      checkAlertOpenInProgress=true;
      if (dojo.byId('alertCount') && dojo.byId('alertCount').value>1) {
        dijit.byId('markAllAsReadButton').set('label',i18n('markAllAsRead',new Array(dojo.byId('alertCount').value)));
        dojo.byId("markAllAsReadButtonDiv").style.display="inline";
      } else {
        dojo.byId("markAllAsReadButtonDiv").style.display="none";
		dojo.byId("trMarkAs").style.gap="0px";
      }
      dojo.style(dialogReminder, {
        visibility : 'visible',
        display : 'flex',
        bottom : '-200px'
      });
      var toColor='#FFCCCC';
      if (dojo.byId('alertType') && dojo.byId('alertType').value == 'WARNING') {
        toColor='#FEF6E5';
		addReminderWarningTitle(reminderDiv);
      }
      if (dojo.byId('alertType') && dojo.byId('alertType').value == 'INFO') {
        toColor='#EDF4FB';
		addReminderInfoTitle(reminderDiv);
      }
	  
	  if (dojo.byId('alertType') && dojo.byId('alertType').value == 'ALERT') {
	    toColor='#FCF8F9';
	  	addReminderAlertTitle(reminderDiv);
	  }
      var duration=2000;
      if (checkAlertDisplayQuick) duration=200;
      dojo.animateProperty({
        node : dialogReminder,
        properties : {
          bottom : {
            start : -200,
            end : 0
          },
          right : 0,
          backgroundColor : {
            start : '#FFFFFF',
            end : toColor
          }
        },
        duration : duration,
        onEnd : function() {
          checkAlertOpenInProgress=false;
        }
      }).play();
    } else {
      if (alertCheckTime>0) setTimeout('checkAlert();', alertCheckTime * 1000);
    }
  } else {
    if (alertCheckTime>0) setTimeout('checkAlert();', alertCheckTime * 1000);
  }
  checkAlertDisplayQuick=false;
  if (dojo.byId("alertCount")) {
    if (dojo.byId("alertCount").value>1) {
      checkAlertDisplayQuick=true;
    }
  }
}

function addReminderInfoTitle(reminderDiv) {
    if (reminderDiv.querySelector('.reminderInfoTitle')) return;
    reminderDiv.classList.remove('messageWARNING2', 'messageALERT2');
    reminderDiv.classList.add('messageINFO');
    dojo.byId('dialogReminder').classList.remove('reminder-warning', 'reminder-alert');

    var title = document.createElement('b');
    title.className = 'reminderInfoTitle';
    title.textContent = String(i18n('INFO')).charAt(0).toUpperCase() + String(i18n('INFO')).slice(1);;
    reminderDiv.insertBefore(title, reminderDiv.firstChild);
}

function addReminderWarningTitle(reminderDiv) {
    if (reminderDiv.querySelector('.reminderWarningTitle')) return;
    reminderDiv.classList.remove('messageINFO', 'messageALERT2');
    reminderDiv.classList.add('messageWARNING2');
    dojo.byId('dialogReminder').classList.remove('reminder-alert');
    dojo.byId('dialogReminder').classList.add('reminder-warning');

    var title = document.createElement('b');
    title.className = 'reminderWarningTitle';
    title.textContent = i18n('WARNING');
    reminderDiv.insertBefore(title, reminderDiv.firstChild);
}

function addReminderAlertTitle(reminderDiv) {
    if (reminderDiv.querySelector('.reminderAlertTitle')) return;
    reminderDiv.classList.remove('messageINFO', 'messageWARNING2');
    reminderDiv.classList.add('messageALERT2');
    dojo.byId('dialogReminder').classList.remove('reminder-warning');
    dojo.byId('dialogReminder').classList.add('reminder-alert');

    var title = document.createElement('b');
    title.className = 'reminderAlertTitle';
    title.textContent = String(i18n('ALERT')).charAt(0).toUpperCase() + String(i18n('ALERT')).slice(1);
    reminderDiv.insertBefore(title, reminderDiv.firstChild);
}

function showDisconnectedMessage(data) {
  dojo.byId('disconnectionMessageText').innerHTML=data;
  dojo.byId('disconnectionMessage').style.display='block';
}

function setAlertReadMessage() {
  closeAlertBox();
  if (dojo.byId('idAlert') && dojo.byId('idAlert').value) {
    setAlertRead(dojo.byId('idAlert').value);
  }
}

function setAllAlertReadMessage() {
  checkAlertDisplayQuick=false;
  closeAlertBox();
  setAlertRead('*');
}

function setAlertReadMessageInForm() {
  dijit.byId('readFlag').set('checked', 'checked');
  submitForm("../tool/saveObject.php"+addTokenIndexToUrl('?'), "resultDivMain", "objectForm", true);
}

function setAlertRemindMessage() {
  closeAlertBox();
  if (dojo.byId('idAlert') && dojo.byId('idAlert').value) {
    setAlertRead(dojo.byId('idAlert').value, dijit.byId('remindAlertTime').get(
        'value'));
  }
}

function setAlertRead(id, remind) {
  var url="../tool/setAlertRead.php?idAlert=" + id;
  if (remind) {
    url+='&remind=' + remind;
  }
  dojo.xhrGet({
    url : url+addTokenIndexToUrl(),
    handleAs : "text",
    load : function(data, args) {
      setTimeout('checkAlert();', 100);
    },
    error : function() {
      setTimeout('checkAlert();', 100);
    }
  });
}

function closeAlertBox() {
  var dialogReminder=dojo.byId('dialogReminder');
  var duration=900;
  if (checkAlertDisplayQuick && dialogReminder) duration=90;

  dialogReminder.style.transition = 'transform ' + duration + 'ms ease';
  dialogReminder.style.transform = 'translateY(150%)';

  setTimeout(function() {
    if (dojo.byId('dialogReminder') && ! checkAlertOpenInProgress) {
      dialogReminder=dojo.byId('dialogReminder');
      dojo.style(dialogReminder, {
        visibility : 'hidden',
        display : 'none'
      });
      dialogReminder.style.transform = '';
      dialogReminder.style.transition = '';
    }
  }, duration);
}

function setReadMessageLegalFollowup(idMessageLegal){
  var param="?idMessageLegal="+idMessageLegal;
  dojo.xhrGet({
    url : "../tool/saveMessageLegalFollowup.php"+param+addTokenIndexToUrl(),
    handleAs : "text",
    load : function(data, args) {
    },
  });
}

function setNewGui(idMessageLegal, newGuiActivated){
	var param="?idMessageLegal="+idMessageLegal+"&newGuiActivated="+newGuiActivated;
	  dojo.xhrGet({
	    url : "../tool/saveMessageLegalFollowup.php"+param+addTokenIndexToUrl(),
	    handleAs : "text",
	    load : function(data, args) {
	    	if(newGuiActivated){
	    	  showWait();
	          noDisconnect=true;
	          quitConfirmed=true;        
	          dojo.byId("directAccessPage").value="today.php";
	          dojo.byId("directAccessForm").submit();
	    	}
	    },
	  });
}
