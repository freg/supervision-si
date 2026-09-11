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

function showDetailPokerItem() {
  var pokerItemType=dijit.byId('pokerItemRef2Type').get("value");
  if (pokerItemType) {
    var canCreate=0;
    if (canCreateArray[pokerItemType] == "YES") {
      canCreate=1;
    }
    showDetail('pokerItemRef2Id',canCreate,pokerItemType,true);
  } else {
    showInfo(i18n('messageMandatory',new Array(i18n('pokerItemType'))));
  }
}

// =============================================================================
// = Poker Item
// =============================================================================

var noRefreshPokerItem=false;
function addPokerItem(classPokerItem,defaultPokerItem,idPokerSession) {
  var params="&objectClass=PokerSession&objectId=" + idPokerSession;
  loadDialog('dialogPokerItem',function() {
    noRefreshPokerItem=true;
    var objectClass=dojo.byId('objectClass').value;
    var objectId=dojo.byId("objectId").value;
    var message=i18n("dialogPokerItem");
    dojo.byId("pokerItemId").value="";
    dojo.byId("pokerItemRef1Type").value=objectClass;
    dojo.byId("pokerItemRef1Id").value=objectId;
    if (classPokerItem) {
      dojo.byId("pokerItemFixedClass").value=classPokerItem;
      message=i18n("dialogPokerItemRestricted",new Array(i18n(objectClass),objectId,i18n(classPokerItem)));
      dijit.byId("pokerItemRef2Type").setDisplayedValue(i18n(classLink));
      lockWidget("pokerItemRef2Type");
      noRefreshPokerItem=false;
      refreshPokerItemList();
    } else {
      dojo.byId("pokerItemFixedClass").value="";
      if (defaultPokerItem) {
        dijit.byId("pokerItemRef2Type").set('value',defaultPokerItem);
      } else {
        dijit.byId("pokerItemRef2Type").reset();
      }
      message=i18n("dialogPokerItemExtended",new Array(i18n(objectClass),objectId));
      unlockWidget("pokerItemRef2Type");
      noRefreshPokerItem=false;
      refreshPokerItemList();
    }

    dijit.byId("dialogPokerItem").set('title',message);
    dijit.byId("pokerItemComment").set('value','');
    dijit.byId("dialogPokerItem").show();
    disableWidget('dialogPokerItemSubmit');
  },true,params,true);
}

function selectPokerItemItem() {
  var nbSelected=0;
  list=dojo.byId('pokerItemRef2Id');
  if (list.options) {
    for (var i=0;i < list.options.length;i++) {
      if (list.options[i].selected) {
        nbSelected++;
      }
    }
  }
  if (nbSelected > 0) {
    enableWidget('dialogPokerItemSubmit');
  } else {
    disableWidget('dialogPokerItemSubmit');
  }
}

/**
 * Refresh the pokerItem list (after update)
 */
function refreshPokerItemList(selected) {
  if (noRefreshPokerItem) return;
  disableWidget('dialogPokerItemSubmit');
  var url='../tool/dynamicListPokerItem.php';
  if (selected) {
    url+='?selected=' + selected;
  }
  if (!selected) {
    selectPokerItemItem();
  }
  loadContent(url,'dialogPokerItemList','pokerItemForm',false);
}

/**
 * save a pokerItem (after addPokerItem)
 * 
 */
function savePokerItem() {
  if (dojo.byId("pokerItemRef2Id").value == "") return;
  var fixedClass=(dojo.byId('pokerItemFixedClass')) ? dojo.byId('pokerItemFixedClass').value : '';
  loadContent("../tool/savePokerItem.php","resultDivMain","pokerItemForm",true,'pokerItem' + fixedClass);
  dijit.byId('dialogPokerItem').hide();
}

/**
 * Display a delete PokerItem Box
 * 
 */
function removePokerItem(pokerItemId) {
  actionOK=function() {
    loadContent("../tool/removePokerItem.php?pokerItemId=" + pokerItemId,"resultDivMain",null,true,'pokerItem');
  };
  msg=i18n('confirmDeletePokerItem',new Array('PokerItem',pokerItemId));
  showConfirm(msg,actionOK);
}

function editPokerItem(pokerItemId) {
  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
  var callBack=function() {
    dojo.xhrGet({
      url:'../tool/getSingleData.php?dataType=editPokerItem&idPokerItem=' + pokerItemId + ''+addTokenIndexToUrl(),
      handleAs:"text",
      load:function(data) {
        dijit.byId('pokerItemComment').set('value',data);
      }
    });
    dijit.byId("dialogPokerItem").show();
  };
  var params="&pokerItemId=" + pokerItemId;
  params+="&mode=edit";
  loadDialog('dialogPokerItem',callBack,false,params);
}

function startPokerSession(idPokerSession) {
  dojo.xhrPost({
    url:'../tool/startPokerSession.php?idPokerSession=' + idPokerSession + '&quickStart=true'+addTokenIndexToUrl() + ''+addTokenIndexToUrl(),
    handleAs:"text",
    load:function(data) {
      globalOpenPokerItemVote(idPokerSession);
    }
  });
}

function stopPokerSession(idPokerSession) {
  dojo.xhrPost({
    url:'../tool/startPokerSession.php?idPokerSession=' + idPokerSession + '&quickStart=false'+addTokenIndexToUrl(),
    handleAs:"text",
    load:function(data) {
      refreshGrid();
      loadContent("objectDetail.php","detailDiv","listForm",null,null,null,null,null,true);
    }
  });
}

function pausePokerSession(idPokerSession) {
  dojo.xhrPost({
    url:'../tool/startPausePokerSession.php?idPokerSession=' + idPokerSession + ''+addTokenIndexToUrl(),
    handleAs:"text",
    load:function(data) {
      loadContent("objectDetail.php","detailDiv","listForm",null,null,null,null,null,true);
    }
  });
}

function flipPokerVote(idPokerSession,idItem,itemList) {
  dojo.xhrPost({
    url:'../tool/flipPokerVote.php?idPokerItem=' + idItem + '&idPokerSession=' + idPokerSession + '&mode=flip'+addTokenIndexToUrl(),
    handleAs:"text",
    load:function(data) {
      refreshPokerItemResult(idPokerSession,idItem,itemList);
    }
  });
}

function resetPokerVote(idPokerSession,idItem,itemList) {
  dojo.xhrPost({
    url:'../tool/flipPokerVote.php?idPokerItem=' + idItem + '&idPokerSession=' + idPokerSession + '&mode=reset'+addTokenIndexToUrl(),
    handleAs:"text",
    load:function(data) {
      refreshPokerItemResult(idPokerSession,idItem,itemList);
    }
  });
}

function openPokerItemVote(idItem,idPokerSession) {
  dojo.xhrPost({
    url:'../tool/startPokerSession.php?idPokerSession=' + idPokerSession + '&quickStart=true'+addTokenIndexToUrl(),
    handleAs:"text",
    load:function(data) {
      dojo.xhrPost({
        url:'../tool/openPokerItemVote.php?idPokerItem=' + idItem + '&mode=open'+addTokenIndexToUrl(),
        handleAs:"text",
        load:function(data) {
          loadContent("objectDetail.php","detailDiv","listForm",null,null,null,null,null,true);
        }
      });
    }
  });
}

function globalOpenPokerItemVote(idPokerSession) {
  dojo.xhrPost({
    url:'../tool/openPokerItemVote.php?idPokerSession=' + idPokerSession + '&mode=global'+addTokenIndexToUrl(),
    handleAs:"text",
    load:function(data) {
      loadContent("objectDetail.php","detailDiv","listForm",null,null,null,null,null,true);
    }
  });
}

function commitPokerItemVote(idPokerItem) {
  var idComplexity=dijit.byId('pokerComplexity').get('value');
  dojo.xhrPost({
    url:'../tool/openPokerItemVote.php?idPokerItem=' + idPokerItem + '&mode=close' + '&idComplexity=' + idComplexity + ''+addTokenIndexToUrl(),
    handleAs:"text",
    load:function(data) {
      dijit.byId("dialogPokerCloseVote").hide();
      loadContent("objectDetail.php","detailDiv","listForm");
    }
  });
}

function pausePokerItemVote(idPokerItem) {
  dojo.xhrPost({
    url:'../tool/openPokerItemVote.php?idPokerItem=' + idPokerItem + '&mode=pause'+addTokenIndexToUrl(),
    handleAs:"text",
    load:function(data) {
      dijit.byId("dialogPokerCloseVote").hide();
      loadContent("objectDetail.php","detailDiv","listForm");
    }
  });
}

function closePokerItemVote(idPokerItem,idPokerSession,global) {
  if (checkFormChangeInProgress()) {
    showAlert(i18n('alertOngoingChange'));
    return;
  }
  var callBack=function() {
    dijit.byId("dialogPokerCloseVote").show();
  };
  var params="&idPokerItem=" + idPokerItem + "&idPokerSession=" + idPokerSession + "&globalClose=" + global;
  loadDialog('dialogPokerCloseVote',callBack,false,params);
}

function gotoPokerItem(idPokerSession,idItem,itemList) {
  tabToSelect=dijit.byId('tabDetailContainer_tablist_Treatment');
  tabContainer=dijit.byId('tabDetailContainer');
  if (tabContainer != undefined) {
    tabContainer.selectChild(tabToSelect.page);
  }
  pokerItemNav(idPokerSession,idItem,itemList,null);
}

function pokerItemNav(idPokerSession,idItem,itemList,nav) {
  var url='../tool/pokerItemNavigation.php?idPokerSession=' + idPokerSession + '&idItem=' + idItem + '&itemList=' + itemList + '&nav=' + nav;
  loadContent(url,'pokerVoteDiv',null,false);
}

function refreshPokerItemResult(idPokerSession,idItem,itemList) {
  var url='../tool/refreshPokerItemResult.php?idPokerSession=' + idPokerSession + '&idItem=' + idItem + '&itemList=' + itemList;
  var callBack=function() {
    refreshPokerVoteList(idPokerSession,idItem,itemList);
  };
  loadContent(url,'pokerVoteResult',null,false,null,null,null,callBack,true);
}

function refreshPokerVoteList(idPokerSession,idItem,itemList) {
  var url='../tool/refreshPokerVoteList.php?idPokerSession=' + idPokerSession + '&idItem=' + idItem + '&itemList=' + itemList;
  loadContent(url,'pokerVoteList',null,false);
}

function voteToPokerItem(idPokerSession,idItem,itemList,vote) {
  if (!vote) vote='';
  dojo.xhrPost({
    url:'../tool/voteToPokerItem.php?idPokerSession=' + idPokerSession + '&idItem=' + idItem + '&vote=' + vote + ''+addTokenIndexToUrl(),
    handleAs:"text",
    load:function(data) {
      pokerItemNav(idPokerSession,idItem,itemList,null);
    }
  });
}