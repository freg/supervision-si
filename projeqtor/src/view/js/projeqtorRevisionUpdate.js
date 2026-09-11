/*** COPYRIGHT NOTICE *********************************************************
 *
 * Copyright 2015 ProjeQtOr - Pascal BERNARD - support@projeqtor.org
 *
 ******************************************************************************
 *** WARNING *** T H I S    F I L E    I S    N O T    O P E N    S O U R C E *
 ******************************************************************************
 *
 * This file is an add-on to ProjeQtOr, packaged as a plug-in module.
 * It is NOT distributed under an open source license. 
 * It is distributed in a proprietary mode, only to the customer who bought
 * corresponding licence. 
 * The company ProjeQtOr remains owner of all add-ons it delivers.
 * Any change to an add-ons without the explicit agreement of the company 
 * ProjeQtOr is prohibited.
 * The diffusion (or any kind if distribution) of an add-on is prohibited.
 * Violators will be prosecuted.
 *    
 *** DO NOT REMOVE THIS NOTICE ************************************************/

var currentRevisionSelected = '';
function refreshRevisionUpdateTable(table, forceUpdate){
  currentRevisionSelected = (forceUpdate)?'':currentRevisionSelected;
  var div = table+'RevisionUpdateTableDiv';
  loadContent('../tool/refreshRevisionUpdateTable.php?revisionId='+currentRevisionSelected+'&table='+table,div,null,false);
}

function refreshFrequencyUpdateTable(table, frequency){
  var divTable = table+'FrequencyUpdateTableDiv';
  dojo.byId(divTable).style.display = (frequency == 'manual')?'none':'';
}

function refreshFrequencyUpdateTableDiv(type){
  var frequencyDiv = type+'FrequencyUpdateTableDiv';
  loadContent('../tool/updateRevisionFrequencyTable.php?type='+type,frequencyDiv,null,false);
}

currentTicketSelected = '';
currentFileSelected = '';
function reapplyRevisionDateFilter(table){
  var w = dijit.byId((table === 'new' ? 'new' : 'current') + 'RevisionDateFilter');
  if (w && w.get('value')) {
    filterInstalledRevisionByDate(w.get('value'), table);
  }
}

function updateRevisionSelectedLine(revisionId, ticketId, filePath, table){
  var cb = function(){ reapplyRevisionDateFilter(table); };
  currentRevisionSelected = (revisionId)?revisionId:false;
  if(currentRevisionSelected != ''){
    dojo.query('.subsUpdateVersionLineSelected').forEach(function(node){
      dojo.removeClass(node, 'subsUpdateVersionLineSelected');
      if(node.id == table+'RevisionLine'+revisionId){
        currentRevisionSelected = '';
      }
    });
    if(currentRevisionSelected != '')dojo.addClass(table+'RevisionLine'+currentRevisionSelected, 'subsUpdateVersionLineSelected');
    if(dojo.byId(table+'RevisionUpdateTickets'))loadDiv('../tool/updateRevisionTickets.php?revisionId='+currentRevisionSelected+'&table='+table,table+'RevisionUpdateTickets',null,cb);
    if(dojo.byId(table+'RevisionUpdateFiles'))loadDiv('../tool/updateRevisionFiles.php?revisionId='+currentRevisionSelected+'&table='+table,table+'RevisionUpdateFiles',null,cb);
  }

  currentTicketSelected = (ticketId)?ticketId:'';
  if(currentTicketSelected){
    dojo.query('.subsUpdateVersionLineSelected').forEach(function(node){
      dojo.removeClass(node, 'subsUpdateVersionLineSelected');
      if(node.id == table+'TicketLine'+currentTicketSelected){
        currentTicketSelected = '';
      }
    });
    if(currentTicketSelected != '')dojo.addClass(table+'TicketLine'+currentTicketSelected, 'subsUpdateVersionLineSelected');
    if(dojo.byId(table+'RevisionUpdateAvailables'))loadDiv('../tool/updateRevisionAvailables.php?ticketId='+currentTicketSelected+'&table='+table,table+'RevisionUpdateAvailables',null,cb);
    if(dojo.byId(table+'RevisionUpdateFiles'))loadDiv('../tool/updateRevisionFiles.php?ticketId='+currentTicketSelected+'&table='+table,table+'RevisionUpdateFiles',null,cb);
  }

  currentFileSelected = (filePath)?filePath:'';
  if(currentFileSelected != ''){
    dojo.query('.subsUpdateVersionLineSelected').forEach(function(node){
      dojo.removeClass(node, 'subsUpdateVersionLineSelected');
      if(node.id == table+'FileLine_('+currentFileSelected+')'){
        currentFileSelected = '';
      }
    });
    if(currentFileSelected != '')dojo.addClass(table+'FileLine_('+currentFileSelected+')', 'subsUpdateVersionLineSelected');
    if(dojo.byId(table+'RevisionUpdateTickets'))loadDiv('../tool/updateRevisionTickets.php?filePath='+currentFileSelected+'&table='+table,table+'RevisionUpdateTickets',null,cb);
    if(dojo.byId(table+'RevisionUpdateAvailables'))loadDiv('../tool/updateRevisionAvailables.php?filePath='+currentFileSelected+'&table='+table,table+'RevisionUpdateAvailables',null,cb);
  }
  if(!currentRevisionSelected && !currentTicketSelected && !currentFileSelected){
    if(dojo.byId(table+'RevisionUpdateAvailables'))loadDiv('../tool/updateRevisionAvailables.php?&table='+table,table+'RevisionUpdateAvailables',null,cb);
    if(dojo.byId(table+'RevisionUpdateTickets'))loadDiv('../tool/updateRevisionTickets.php?&table='+table,table+'RevisionUpdateTickets',null,cb);
    if(dojo.byId(table+'RevisionUpdateFiles'))loadDiv('../tool/updateRevisionFiles.php?&table='+table,table+'RevisionUpdateFiles',null,cb);
  }
}

function filterRevisionList(search, table) {
  var searchVal=dojo.byId(table+'RevisionUpdate'+search+'Search').value;
  dojo.byId(table+'IconSearch'+search).style.display="none";
  dojo.byId(table+'IconCancel'+search).style.display="";
  searchVal=searchVal.replace(/\*/gi,'.*');
  var pattern = new RegExp(searchVal, 'i');
  dojo.query('.'+table+search).forEach(function(node){
    if (searchVal!='' && ! pattern.test(node.getAttribute('value')) ) {
      node.parentNode.style.display="none";
    } else {
      node.parentNode.style.display="";
    }
  });
}

function clearFilterRevisionList(search, table) {
  if(dojo.byId(table+'IconSearch'+search))dojo.byId(table+'IconSearch'+search).style.display="";
  if(dojo.byId(table+'IconCancel'+search))dojo.byId(table+'IconCancel'+search).style.display="none";
  dojo.query('.'+table+search).forEach(function(node){
    node.parentNode.style.display="";
  });
  if(dojo.byId(table+'RevisionUpdate'+search+'Search'))dojo.byId(table+'RevisionUpdate'+search+'Search').value="";
}

function clearAllFilterRevisionList(table){
  clearFilterRevisionList('Availables', table);
  clearFilterRevisionList('Tickets', table);
  clearFilterRevisionList('Files', table);
}

function clearAllFilter(){
  updateRevisionSelectedLine(null,null,null,'new');
  clearAllFilterRevisionList('new');
  updateRevisionSelectedLine(null,null,null,'current');
  clearAllFilterRevisionList('current');
}

function subscriptionSetApplicationTo(newStatus, confirmed) {
  if (newStatus != 'Open' && (typeof confirmed=='undefined' || ! confirmed)) {
    actionOK=function() {
      subscriptionSetApplicationTo(newStatus, true);
    };
    msg=i18n('subscriptionSetApplicationToConfirm');
    showConfirm(msg,actionOK);
  } else {
    var url="../tool/adminFunctionalities.php?adminFunctionality=setApplicationStatusTo&newStatus="+newStatus+"&fromSubscriptionUpdate=true";
    showWait();
    dojo.xhrPost({
      url : url,
      handleAs : "text",
      load : function(data, args) {
        loadContent("SubscriptionView.php","centerDiv");
      },
      error : function() {
      }
    });
  }
}

function loadSubscriptionView(){
  if(subscriptionCodeStatus != 'OK'){
    checkSubscribeCode('menu');
  }else{
    loadContent("SubscriptionView.php","centerDiv");
  }
}

function checkSubscribeCode(method){
  if(method == 'manual'){
    var callback = function(){
      var lastOperationStatus=dojo.byId('lastOperationStatus');
      subscriptionCodeStatus = (lastOperationStatus)?lastOperationStatus.value:'KO';
      if(subscriptionCodeStatus != 'KO' && subscriptionCodeStatus != 'OK')subscriptionCodeStatus='KO';
      loadContent("SubscriptionView.php?needCacheRefresh=true","centerDiv", null, false, null, null, null, null, true);
	  showWait(i18n('refreshRevisionUpdateInProgress'));
    }
    loadContent("../tool/checkSubscriptionCode.php?method="+method,"resultDivMain","subscriptionConfigurationForm",true,null,null,null,callback);
  }else{
    dojo.xhrGet({
      url : "../tool/checkSubscriptionCode.php?method="+method+addTokenIndexToUrl(),
      handleAs : "text",
      load : function(data, args) {
        subscriptionCodeStatus = (data)?data:'KO';
		if(method == 'menu'){
			showWait(i18n('refreshRevisionUpdateInProgress'));
			loadContent("SubscriptionView.php","centerDiv");
		}
      },
      error : function() {
        subscriptionCodeStatus = 'KO';
      }
    });
  }
}

function installRevisionUpdate(zipValidated){
  var callback = function(){
    setTimeout('loadContent("SubscriptionView.php","centerDiv");',1000);
  }
  loadContent("../tool/subscriptionInstallUpdate.php?zipValidated="+zipValidated,"resultDivMain",null,true,null,null,null,callback);
}

function downloadRevisionUpdate(confirmed, lockConfirm) {
  if (! confirmed) {
    actionOK=function() {
      downloadRevisionUpdate(true, false);
    };
    msg=i18n('installRevisionConfirmInstall');
    showConfirm(msg,actionOK);
  } else {
    showWait();
    dojo.xhrGet({
      url : "../tool/subscriptionDownloadUpdate.php?lockConfirm="+lockConfirm+addTokenIndexToUrl(),
      load : function(data) {
        if(data.length > 1){
          hideWait();
          actionOK=function() {
            downloadRevisionUpdate(true, true);
          };
          showConfirm(data,actionOK);
        }else{
          installRevisionUpdate(data);
        }
      },
      error : function(data) {
        hideWait();
        showError(data);
      }
    });
  }
}

function subscriptionDisconnectAll(toConfirm) {
  actionOK=function() {
    var callback = function(){
      loadContent("SubscriptionView.php","centerDiv");
    }
    loadContent("../tool/adminFunctionalities.php?adminFunctionality=disconnectAll&element=Audit","resultDivMain","subscriptionConfigurationForm",true,'admin', null,null,callback);
  };
  if (toConfirm) {
    msg=i18n('confirmDisconnectAll');
    showConfirm(msg,actionOK);
  }
}

var alreadyStart=false;
function installAutoInstall(fileName,confirmed) {
  if (! confirmed) {
    actionOK=function() {
      installFile(fileName, true);
    };
    msg=i18n('installAutoConfirmInstall', new Array(fileName));
    showConfirm(msg,actionOK);
  } else {
    showWait();
    dojo.xhrGet({
      url : "../plugin/loadPlugin.php?pluginFile="
          + encodeURIComponent(fileName),
      load : function(data) {
        if (data=="OK") {
          loadContent("pluginManagement.php", "centerDiv");
        } else if (data=="RELOAD") {
          showWait();
          noDisconnect=true;
          quitConfirmed=true;        
          dojo.byId("directAccessPage").value="SubscriptionView.php";
          dojo.byId("menuActualStatus").value=menuActualStatus;
//          dojo.byId("p1name").value="type";
//          dojo.byId("p1value").value=forceRefreshMenu;
          dojo.byId("p1name").value=null;
          dojo.byId("p1value").value=null;
//          forceRefreshMenu="";
          dojo.byId("directAccessForm").submit();     
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
function installAutoDeleteFile(fileName,confirmed) {
  if (! confirmed) {
    actionOK=function() {
      installAutoDeleteFile(fileName, true);
    };
    msg=i18n('installAutoDeleteConfirm', new Array(fileName));
    showConfirm(msg,actionOK);
  } else {
    showWait();
    dojo.xhrGet({
      url : "../tool/installAutoDelete.php?file="
          + encodeURIComponent(fileName),
      load : function(data) {
        if (data=="OK") {
          loadContent("../view/SubscriptionView.php", "centerDiv");
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

function installAutoSetApplicationTo(newStatus, confirmed) {
  if (typeof confirmed=='undefined' || ! confirmed) {
    actionOK=function() {
      installAutoSetApplicationTo(newStatus, true);
    };
    msg=i18n('installAutoSetApplicationToConfirm');
    showConfirm(msg,actionOK);
  } else {
    var url="../tool/adminFunctionalities.php?adminFunctionality=setApplicationStatusTo&newStatus="+newStatus+"&fromSubscriptionUpdate=true";
    showWait();
    dojo.xhrPost({
      url : url,
      form : "adminForm",
      handleAs : "text",
      load : function(data, args) {
        loadContent('../view/SubscriptionView.php', "centerDiv");
      },
      error : function() {
      }
    });
  }
}

function installAutoDisconnectAll() {
  actionOK=function() {
    loadContent(
        "../tool/adminFunctionalities.php?adminFunctionality=disconnectAll&element=Audit",
        "resultDiv", "adminForm", true, 'admin',null,null,function(){loadContent('../view/SubscriptionView.php', "centerDiv");});
  };
  msg=i18n('confirmDisconnectAll');
  showConfirm(msg, actionOK);
}

function installAutoUpload() {
  if (!isHtml5()) {
    return true;
  }
  if (dojo.byId('installAutoFileName').innerHTML == "") {
    return false;
  }
  dojo.style(dojo.byId('downloadProgress'), {
    display : 'block'
  });
  showWait();
  return true;
}

function installAutoChangeFile(list) {
  if (list.length > 0) {
    dojo.byId("installAutoFileName").innerHTML=list[0]['name'];
    return true;
  }
}

function installAutoSaveAck(dataArray) {
  if (!isHtml5()) {
    resultFrame=document.getElementById("resultPost");
    resultText=resultPost.document.body.innerHTML;
    dijit.byId('resultDiv').set('content',resultText);
    installAutoSaveFinalize();
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
  contentNode = dojo.byId('resultDiv');
  contentNode.innerHTML=result.message;
  contentNode.style.display="block"; 
  installAutoSaveFinalize();
}

function installAutoSaveFinalize() {
  contentNode = dojo.byId('resultDiv');
  if (contentNode.innerHTML.indexOf('resultOK')>0) {
    setTimeout('loadContent("../view/SubscriptionView.php", "centerDiv");',1000);
  } else {
    hideWait();
  }
}

function installAutoInstall(fileName,confirmed) {
  if (! confirmed) {
    actionOK=function() {
      installAutoInstall(fileName, true);
    };
    msg=i18n('installAutoInstallConfirm', new Array(fileName));
    showConfirm(msg,actionOK);
  } else {
    showWait();
    dojo.xhrGet({
      url : "../tool/installAutoInstall.php?installAutoFile="
          + encodeURIComponent(fileName),
      load : function(data) {
        hideWait();
        if (data=="OK") {
          showWait();
          noDisconnect=true;
          quitConfirmed=true;        
          dojo.byId("directAccessPage").value="";
          dojo.byId("menuActualStatus").value=menuActualStatus;
          dojo.byId("p1name").value="type";
          dojo.byId("p1value").value=forceRefreshMenu;
          forceRefreshMenu="";
          dojo.byId("directAccessForm").submit();     
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

function installAutoSaveAttachmentProgress(data) {
  done=data.bytesLoaded;
  total=data.bytesTotal;
  if (total) {
    progress=done / total;
  }
  // dojo.style(dojo.byId('downloadProgress'), {display:'block'});
  dijit.byId('downloadProgress').set('value', progress);
}

var needRestart=true;
function installationDownloadRemote(version) {
  //loadContent("../view/SubscriptionView.php", "centerDiv");
  var id="projeqtor"+version+".zip";
  finalText='<table><tr><td><span style="font-weight:bold;">'+id+'</span></td><td width="20"></td><td><div id="progressContainer'+id+'" style="width:200px;height:18px;border:2px solid grey">'+
  '<div id="progressVal'+version+'" style="position: absolute; width:16px;position:relative; z-index:500; margin:0 auto; margin-top:2px;">0%</div>'+
  '<div id="progressBar'+version+'" style="width:'+(0/100)+'px;height:18px;background-color:#AAFFAA;margin-top:-18px;position:absolute;">'+
  '</div>'+
  '</div></td></tr></table>';
  dojo.byId('containerDownloader').innerHTML=finalText;
  setTimeout(function(){meetingDownload();},1000);
  dojo.xhrGet({
    url : "../tool/installAutoDownload.php?installAutoVersion="
        + version+addTokenIndexToUrl(),
    load : function() {
      if(dojo.byId('containerDownloader')!=null){
        needRestart=false;
        loadContent("../view/SubscriptionView.php", "centerDiv");
      }
    },
    error : function(data) {
      hideWait();
      needRestart=false;
      showError(data);
    }
  });
}

function meetingDownload(){
  if(dojo.byId('containerDownloader')!=null){
  alreadyStart=true;
  dojo.xhrGet({
    url : "../tool/installAutoDownloadProgress.php"+addTokenIndexToUrl('?'),
    load : function(data) {
      if(data!='empty' && dojo.byId('containerDownloader')!=null){
        finalText='';
        json=JSON.parse(data);
        for(var key in json){
          id=json[key]['name'];
          finalText+='<table><tr><td><span style="font-weight:bold;">'+json[key]['name']+'</span></td><td width="20"></td><td><div id="progressContainer'+id+'" style="width:200px;height:18px;border:2px solid grey">'+
          '<div id="progressVal'+id+'" style="position: absolute; width:16px;position:relative; z-index:500; margin:0 auto; margin-top:2px;">'+Math.round(json[key]['val'])+'%</div>'+
          '<div id="progressBar'+id+'" style="width:'+(200*Math.round(json[key]['val'])/100)+'px;height:18px;background-color:#AAFFAA;margin-top:-18px;position:absolute;">'+
          '</div>'+
          '</div></td></tr></table>';
        }
        dojo.byId('containerDownloader').innerHTML=finalText;
        setTimeout(function(){meetingDownload();},1000);
      }else{
        alreadyStart=false;
      }
    },
    error : function(data) {
      showError(data);
      return;
    }
  });
  };
}

function startDownload(){
  if(dojo.byId('containerDownloader')!=null){
    if(!alreadyStart)meetingDownload();
  }else{
    setTimeout(function(){startDownload();},1000);
  }
}

function installAutoSaveProxy() {
  var callBack=function() {
    setTimeout('loadContent("../view/SubscriptionView.php", "centerDiv");',1000);
  };
  loadContent("../tool/installAutoSaveProxy.php", "resultDiv","proxyForm",true,null,null,null, callBack);
}

function refreshRevisionUpdateCache(){
  loadContent("../view/SubscriptionView.php?needCacheRefresh=true", "centerDiv");
  showWait(i18n('refreshRevisionUpdateInProgress'));
}

function filterInstalledRevisionByDate(val, table){
  var dateStr = val || null;
  var tableName = table || 'current';
  ['Availables', 'Tickets', 'Files'].forEach(function(section){
    dojo.query('#' + tableName + 'RevisionUpdate' + section + ' tr[data-revdates]').forEach(function(tr){
      if (!dateStr) { tr.style.display = ''; return; }
      var dates = tr.getAttribute('data-revdates').split(' ');
      tr.style.display = (dates.indexOf(dateStr) !== -1) ? '' : 'none';
    });
  });
}