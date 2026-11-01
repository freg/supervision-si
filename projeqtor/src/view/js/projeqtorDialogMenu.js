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
//= Menu Bars
//=============================================================================

function selectIconMenuBar(menuClass) {
  var icon=dojo.byId('iconMenuBar' + menuClass);
  dojo.query('.menuBarItem').removeClass('menuBarItemSelected',icon);
  if (icon && dojo.hasClass(icon,'menuBarItem')) {
    dojo.addClass(icon,'menuBarItemSelected');
  }
}

function loadMenuBarObject(menuClass,itemName,from,skipCheck,callback) {
  if (!skipCheck) {
    var actionYes = function () {
      loadMenuBarObject(menuClass,itemName,from,true,callback); // when recall skip checkFormChangeInProgress to avoid infinite while
    };   
    const actionSave = async function () {
      noRefreshAfterSave = true;
      if (dojo.byId('objectClassManual') && dojo.byId('objectClassManual').value=='Imputation') {
        try {
          await saveImputation();
          loadMenuBarObject(menuClass,itemName,from,true,callback);
        } catch (error) {
          console.warn("Imputation not saved:", error);
        }
      } else if (dojo.byId('objectClassManual') && dojo.byId('objectClassManual').value == 'AbacusLine') {
		 try {
		   await saveAbacusLine();
		   loadMenuBarObject(menuClass,itemName,from,true,callback);
		 } catch (error) {
		   console.warn("AbacusLine not saved:", error);
		    }
	  } else if (dojo.byId('objectClassManual') && dojo.byId('objectClassManual').value == 'AbacusDefinition') {
		 try {
		   await saveAbacusDefinitionList();
		   cleanupAbacusWidgets();
		   loadMenuBarObject(menuClass,itemName,from,true,callback);
		 } catch (error) {
		   console.warn("AbacusDefinition not saved:", error);
		 }
	  } else if (dojo.byId('objectClassManual') && dojo.byId('objectClassManual').value == 'AbacusPhase') {
	 	 try {
	 	   await saveAbacusPhase();
	 	   loadMenuBarObject(menuClass,itemName,from,true,callback);
	 	 } catch (error) {
	 	   console.warn("Phase not saved:", error);
	 	 }
	   }else {
        saveObject(actionYes);
      }
    };
    if (checkFormChangeInProgress(actionYes, null, actionSave)) {
      return false;
    }
  }
  setActionCoverListNonObj('CLOSE',false);
  currentPluginPage=null;
  if (from == 'bar' && !isNewGui) {
    selectTreeNodeById(dijit.byId('menuTree'),menuClass);
  }
  hideResultDivs();
  cleanContent("detailDiv");
  formChangeInProgress=false;
  var objectExist='true';
  var currentScreen=menuClass;
  var contentLoadedCallback=callback;
  if (callback) {
    contentLoadedCallback=function() {
      var executeCallback=function() {
        var grid=dijit.byId('objectGrid');
        if (grid && typeof grid._requestsPending==='function' && grid._requestsPending(0)) {
          var gridLoadConnection=dojo.connect(grid,'_onFetchComplete',function() {
            if (grid._requestsPending(0)) return;
            dojo.disconnect(gridLoadConnection);
            callback();
          });
        } else {
          callback();
        }
      };
      var centerDiv=dijit.byId('centerDiv');
      if (centerDiv && centerDiv.onLoadDeferred && typeof centerDiv.onLoadDeferred.then==='function') {
        centerDiv.onLoadDeferred.then(executeCallback);
      } else {
        executeCallback();
      }
    };
  }
  loadContent("objectMain.php?objectClass=" + currentScreen,"centerDiv",null,false,null,null,null,contentLoadedCallback);
  loadDiv("menuUserScreenOrganization.php?currentScreen=" + currentScreen + '&objectExist=' + objectExist,"mainDivMenu");
  stockHistory(currentScreen,null,"object");
  selectIconMenuBar(menuClass);
  if (isNewGui) {
    refreshSelectedItem(menuClass,defaultMenu);
    if (defaultMenu == 'menuBarRecent') {
      menuNewGuiFilter(defaultMenu,menuClass);
    }
    editFavoriteRow(true);
  }
  return true;
}

function loadMenuBarItem(item,itemName,from,skipCheck) {
  if (!skipCheck) {
    var actionYes = function () {
      loadMenuBarItem(item, itemName, from, true); // when recall skip checkFormChangeInProgress to avoid infinite while
    };   
    const actionSave = async function () {
      noRefreshAfterSave = true;
      if (dojo.byId('objectClassManual') && dojo.byId('objectClassManual').value=='Imputation') {
        try {
          await saveImputation();
          loadMenuBarItem(item, itemName, from, true);
        } catch (error) {
          console.warn("Imputation not saved:", error);
        }
      } else if (dojo.byId('objectClassManual') && dojo.byId('objectClassManual').value == 'AbacusLine') {
		try {
		  await saveAbacusLine();
		  loadMenuBarItem(item, itemName, from, true);
		} catch (error) {
		  console.warn("AbacusLine not saved:", error);
		}
	  } else if (dojo.byId('objectClassManual') && dojo.byId('objectClassManual').value == 'AbacusDefinition') {
		try {
		  await saveAbacusDefinitionList();
		  cleanupAbacusWidgets();
		  loadMenuBarItem(item, itemName, from, true);
		} catch (error) {
		  console.warn("AbacusDefinition not saved:", error);
		}
	  } else if (dojo.byId('objectClassManual') && dojo.byId('objectClassManual').value == 'AbacusPhase') {
		try {
		  await saveAbacusPhase();
		  loadMenuBarItem(item, itemName, from, true);
		} catch (error) {
		  console.warn("Pahse not saved:", error);
		}
	  } else {
        saveObject(actionYes);
      }
    };
    if (checkFormChangeInProgress(actionYes, null, actionSave)) {
      return false;
    }
  }
  
  setActionCoverListNonObj('CLOSE',false);
  currentPluginPage=null;
  if (from == 'bar' && !isNewGui) {
    selectTreeNodeById(dijit.byId('menuTree'),item);
  }
  cleanContent("detailDiv");
  hideResultDivs();
  formChangeInProgress=false;
  var currentScreen=item;
  var objectExist='false';
  if (item == 'Today') {
    loadContent("today.php","centerDiv");
  } else if (item == 'StartGuide') {
    loadContent("startGuide.php","centerDiv");
  } else if (item == 'DocumentExplorer') {
    objectExist='true';
    cleanContent("centerDiv");
    loadContent("documentExplorerMain.php","centerDiv",null,false,null,null,null,explorerInit);
  } else if (item == 'ProspectionView') {
    objectExist='true';
    cleanContent("centerDiv");
    loadContent("prospectionViewMain.php","centerDiv",null,false,null,null,null,prospectionViewInit);
  } else if (item == 'Planning') {
    objectExist='true';
    vGanttCurrentLine=-1;
    cleanContent("centerDiv");
    loadContent("planningMain.php","centerDiv");
  } else if (item == 'PlanningWorkPlan') {
    objectExist='true';
    vGanttCurrentLine=-1;
    cleanContent("centerDiv");
    loadContent("planningWorkPlanMain.php","centerDiv");
  } else if (item == 'PortfolioPlanning') {
    objectExist='true';
    vGanttCurrentLine=-1;
    cleanContent("centerDiv");
    loadContent("portfolioPlanningMain.php","centerDiv");
  } else if (item == 'ResourcePlanning') {
    objectExist='true';
    vGanttCurrentLine=-1;
    cleanContent("centerDiv");
    loadContent("resourcePlanningMain.php","centerDiv");
  }else if (item == 'WorkPlan') {
    objectExist='false';
    vGanttCurrentLine=-1;
    cleanContent("centerDiv");
    loadContent("workPlanMain.php","centerDiv");
  } else if (item == 'GlobalPlanning') {
    objectExist='true';
    vGanttCurrentLine=-1;
    cleanContent("centerDiv");
    loadContent("globalPlanningMain.php","centerDiv");
  } else if (item == 'HierarchicalBudget') {
    objectExist='true';
    vGanttCurrentLine=-1;
    cleanContent("centerDiv");
    loadContent("hierarchicalBudgetMain.php","centerDiv");
  } else if (item == 'ResourceSkill') {
    objectExist='true';
    vGanttCurrentLine=-1;
    cleanContent("centerDiv");
    loadContent("resourceSkillMain.php?notResourceSkillSimple="+true,"centerDiv");
  } else if (item == 'ResourceSkillSimple') {
	objectExist='true';
	vGanttCurrentLine=-1;
	cleanContent("centerDiv");
	loadContent("resourceSkillMain.php?notResourceSkillSimple="+false,"centerDiv");
  }else if (item == 'HierarchicalSkill') {
    objectExist='true';
    vGanttCurrentLine=-1;
    cleanContent("centerDiv");
    loadContent("hierarchicalSkillMain.php","centerDiv");
  } else if (item == 'GanttClientContract' || item == 'GanttSupplierContract') {
    var object="SupplierContract";
    if (item == 'GanttClientContract') {
      object="ClientContract";
    }
    objectExist='true';
    vGanttCurrentLine=-1;
    cleanContent("centerDiv");
    loadContent("contractGanttMain.php?objectClass=" + object,"centerDiv");
  } else if (item == 'Imputation') {
    loadContent("imputationMain.php","centerDiv");
  } else if (item == 'Diary') {
    loadContent("diaryMain.php","centerDiv");
  } else if (item == 'ActivityStream') {
    loadContent("activityStreamMain.php","centerDiv");
  } else if (item == 'ImportData') {
	loadContent("importData.php","centerDiv",null,false,null,null,null,checkImportDataScreen);
  } else if (item == 'Reports') {
    loadContent("reportsMain.php","centerDiv");
  } else if (item == 'Absence') {
    loadContent("absenceMain.php","centerDiv");
  } else if (item == 'PlannedWorkManual' || item == 'ConsultationPlannedWorkManual') {
    var param='false';
    if (item == 'ConsultationPlannedWorkManual') param='true';
    loadContent("plannedWorkManualMain.php?readonly=" + param,"centerDiv");
  } else if (item == 'ImputationValidation') {
    loadContent("imputationValidationMain.php","centerDiv");
  } else if (item == 'VotingFollowUp') {
    loadContent("votingFollowUpMain.php","centerDiv");
  } else if (item == 'VotingAttributionFollowUp') {
    loadContent("votingAttributionFollowUpMain.php","centerDiv");
  } else if (item == 'ConsultationValidation') {
    loadContent("consolidationValidationMain.php","centerDiv");
  } else if (item == 'ViewAllSubTask') {
    loadContent("viewAllSubTaskMain.php","centerDiv");
  } else if (item == 'AutoSendReport') {
    loadContent("autoSendReportMain.php","centerDiv");
  } else if (item == 'DataCloning') {
    loadContent("dataCloningMain.php","centerDiv");
  } else if (item == 'DataCloningParameter') {
    loadContent("dataCloningParameterMain.php","centerDiv");
  } else if (item == 'VersionsPlanning') {
    objectExist='true';
    showDetail('versionsPlanningDetail',false,'ProductVersion',true);
  } else if (item == 'VersionsComponentPlanning') {
    showDetail('versionsComponentPlanningDetail',false,'ComponentVersion',true);
  } else if (item == 'UserParameter') {
    loadContent("parameter.php?type=userParameter","centerDiv");
  } else if (item == 'ProjectParameter') {
    loadContent("parameter.php?type=projectParameter","centerDiv");
  } else if (item == 'GlobalParameter') {
    loadContent("parameter.php?type=globalParameter","centerDiv");
  } else if (item == 'Habilitation') {
    loadContent("parameter.php?type=habilitation","centerDiv");
  } else if (item == 'HabilitationReport') {
    loadContent("parameter.php?type=habilitationReport","centerDiv");
  } else if (item == 'HabilitationOther') {
    loadContent("parameter.php?type=habilitationOther","centerDiv");
  } else if (item == 'AccessRight') {
    loadContent("parameter.php?type=accessRight","centerDiv");
  } else if (item == 'AccessRightNoProject') {
    loadContent("parameter.php?type=accessRightNoProject","centerDiv");
  } else if (item == 'Admin') {
    loadContent("admin.php","centerDiv");
  } else if (item == 'Plugin' || item == 'PluginManagement') {
    loadContent("pluginManagement.php","centerDiv");
  } else if (item == 'Subscription') {
    loadSubscriptionView();
  } else if (item == 'Calendar') {
    loadContent("objectMain.php?objectClass=CalendarDefinition","centerDiv");
  } else if (item == 'Gallery') {
    loadContent("galleryMain.php","centerDiv");
  } else if (item == 'DashboardTicket') {
    loadContent("dashboardTicketMain.php","centerDiv");
  } else if (item == 'DashboardRequirement') { // ADD qCazelles - Requirements
    // dashboard - Ticket 90
    loadContent("dashboardRequirementMain.php","centerDiv");
  } else if (pluginMenuPage && pluginMenuPage['menu' + item]) {
    loadMenuBarPlugin(item,itemName,from);
  } else if (item == "LeaveCalendar") {
    loadContent("leaveCalendar.php","centerDiv");
  } else if (item == "LeavesSystemHabilitation") {
    loadContent("leavesSystemHabilitation.php","centerDiv");
  } else if (item == "DashboardEmployeeManager") {
    loadContent("dashboardEmployeeManager.php","centerDiv");
  } else if (item == "Module") {
    loadContent("moduleView.php","centerDiv");
  } else if (item == "Kanban") {
    loadContent("kanbanViewMain.php","centerDiv");
  } else if (item == "DocumentRight") {
    loadContent("documentsRight.php","centerDiv");
  } else if (item == "CriticalResources") {
    loadContent("criticalResourcesMain.php","centerDiv");
  }	else if (item == 'SprintBacklog') {
	loadContent("sprintBacklogMain.php","centerDiv");
  } else if (item == 'ProductBacklog') {
    loadContent("productBacklogMain.php","centerDiv");
  } else if (item == 'ProjectDashboard') {
	loadContent("projectDashboardMain.php","centerDiv");
  } else if (item == 'ProjectDashboardDetail') {
	loadContent("projectDashboardDetailMain.php","centerDiv");
  } else if (item == 'AbacusDefinition') {
	cleanContent("centerDiv");
	cleanupAbacusWidgets();
	var callback = function () {
	  initAbacusTableNavigation();
	}
	loadContent("abacusDefinitionMain.php","centerDiv",null,false,null,null,null,callback);
  } else if (item == 'AbacusLine') {
	cleanContent("centerDiv");
	loadContent("abacusLineMain.php","centerDiv");
   }else if (item == 'AbacusPhase') {
	cleanContent("centerDiv");
	loadContent("abacusPhaseMain.php","centerDiv");
  } else {
    showInfo(i18n("messageSelectedNotAvailable",new Array(itemName)));
  }
  loadDiv("menuUserScreenOrganization.php?currentScreen=" + currentScreen + '&objectExist=' + objectExist,"mainDivMenu");
  stockHistory(item,null,currentScreen);
  selectIconMenuBar(item);
  if (isNewGui) {
    refreshSelectedItem(item,defaultMenu);
    if (defaultMenu == 'menuBarRecent') {
      menuNewGuiFilter(defaultMenu,item);
    }
    editFavoriteRow(true);
  }
  return true;
}

var currentPluginPage=null;
function loadMenuBarPlugin(item,itemName,from,skipCheck) {
  if (!skipCheck) {
    var actionYes = function () {
      loadMenuBarPlugin(item, itemName, from, true); // when recall skip checkFormChangeInProgress to avoid infinite while
    };   
    const actionSave = async function () {
      noRefreshAfterSave = true;
      if (dojo.byId('objectClassManual') && dojo.byId('objectClassManual').value=='Imputation') {
        try {
          await saveImputation();
          loadMenuBarPlugin(item, itemName, from, true);
        } catch (error) {
          console.warn("Imputation not saved:", error);
        }
      } else {
        saveObject(actionYes);
      }
    };
    if (checkFormChangeInProgress(actionYes, null, actionSave)) {
      return false;
    }
  }
  setActionCoverListNonObj('CLOSE',false);
  if (!pluginMenuPage || !pluginMenuPage['menu' + item]) {
    showInfo(i18n("messageSelectedNotAvailable",new Array(item.name)));
    return;
  }
  hideResultDivs();
  currentPluginPage=pluginMenuPage['menu' + item];
  loadContent(pluginMenuPage['menu' + item],"centerDiv");
  if (isNewGui) {
    refreshSelectedItem(item,itemName);
    if (defaultMenu == 'menuBarRecent') {
      menuNewGuiFilter(defaultMenu,item);
    }
    editFavoriteRow(true);
  }
  return currentPluginPage;
}

var customMenuAddRemoveTimeout=null;
var customMenuAddRemoveTimeoutDelay=3000;
var customMenuAddRemoveClass=null;
function customMenuManagement(menuClass) {
  var button=dojo.byId('iconMenuBar' + menuClass);
  offsetbutton=button.offsetLeft + dojo.byId('menuBarVisibleDiv').offsetLeft + dojo.byId('menubarContainer').offsetLeft;
  if (dojo.hasClass(button,'menuBarCustom')) {
    clearTimeout(customMenuAddRemoveTimeout);
    dojo.byId('customMenuAdd').style.display='none';
    customMenuAddRemoveClass=menuClass;
    dojo.byId('customMenuRemove').style.left=offsetbutton + 'px';
    dojo.byId('customMenuRemove').style.display='block';
    customMenuAddRemoveTimeout=setTimeout("dojo.byId('customMenuRemove').style.display='none';",customMenuAddRemoveTimeoutDelay);
  } else {
    clearTimeout(customMenuAddRemoveTimeout);
    dojo.byId('customMenuRemove').style.display='none';
    customMenuAddRemoveClass=menuClass;
    dojo.byId('customMenuAdd').style.left=offsetbutton + 'px';
    dojo.byId('customMenuAdd').style.display='block';
    customMenuAddRemoveTimeout=setTimeout("dojo.byId('customMenuAdd').style.display='none';",customMenuAddRemoveTimeoutDelay);
  }
}

function customMenuAddItem() {
  var param="?operation=add&class=" + customMenuAddRemoveClass;
  dojo.xhrGet({
    url:"../tool/saveCustomMenu.php" + param +addTokenIndexToUrl(),
    handleAs:"text",
    load:function(data,args) {
    },
  });
  dojo.addClass('iconMenuBar' + customMenuAddRemoveClass,'menuBarCustom');
  if (!isNewGui) {
    dojo.byId('customMenuAdd').style.display='none';
  } else {
    hideFavoriteTooltip(0,customMenuAddRemoveClass);
  }
}

function customMenuRemoveItem() {
  var param="?operation=remove&class=" + customMenuAddRemoveClass;
  dojo.xhrGet({
    url:"../tool/saveCustomMenu.php" + param +addTokenIndexToUrl(),
    handleAs:"text",
    load:function(data,args) {
      if (data == 'menuBarCustom') {
        dojo.byId('iconMenuBar' + customMenuAddRemoveClass).style.display="none";
      }
    },
  });
  dojo.removeClass('iconMenuBar' + customMenuAddRemoveClass,'menuBarCustom');
  if (!isNewGui) {
    dojo.byId('customMenuRemove').style.display='none';
  } else {
    hideFavoriteTooltip(0,customMenuAddRemoveClass);
  }
}

function showIconViewSubMenu(comboName) {
  var name=comboName + 'IconViewSubMenu';
  var offsetLeft=dojo.byId(comboName + 'ButtonDetail').offsetLeft;
  if (dojo.byId(name).style.display == 'none') {
    dojo.byId(name).style.left=offsetLeft + 'px';
    dojo.byId(name).style.display='block';
  } else {
    dojo.byId(name).style.display='none';
  }
  var val=null;
  if (dijit.byId(comboName)) {
    val=dijit.byId(comboName).get('value');
  }
  if (!val || val == "" || val == " " || val == "*") {
    dojo.byId(comboName + 'SubViewItem').style.display='none';
  }
}

var hideIconViewSubMenuTimeOut;
function hideIconViewSubMenu(col) {
  var name=col + 'IconViewSubMenu';
  if (hideIconViewSubMenuTimeOut) {
    clearTimeout(hideIconViewSubMenuTimeOut);
  }
  hideIconViewSubMenuTimeOut=setTimeout("dojo.byId(" + name + ").style.display='none';",300);
}

function moveMenuBar(way,duration) {
  if (!duration) duration=150;
  if (!menuBarMove) return;
  var bar=dojo.byId('menubarContainer');
  left=parseInt(bar.style.left.substr(0,bar.style.left.length - 2),10);
  width=parseInt(bar.style.width.substr(0,bar.style.width.length - 2),10);
  var step=56 * 1;
  if (way == 'left') {
    pos=left + step;
  }
  if (way == 'right') {
    pos=left - step;
  }
  if (pos > 0) pos=0;
  if (way == 'right') {
    var visibleWidthRight=dojo.byId('menuBarRight').getBoundingClientRect().left;
    var visibleWidthLeft=dojo.byId('menuBarLeft').getBoundingClientRect().right;
    var visibleWidth=visibleWidthRight - visibleWidthLeft;
    if (visibleWidth - left > width) {
      moveMenuBarStop();
      return;
    }
  }
  dojo.fx.slideTo({
    duration:duration,
    node:bar,
    left:pos,
    easing:function(n) {
      return n;
    },
    onEnd:function() {
      duration-=10;
      if (duration < 50) duration=50;
      if (menuBarMove) {
        moveMenuBar(way,duration);
      }
      showHideMoveButtons();
    }
  }).play();
}
menuBarMove=false;
function moveMenuBarStop() {
  showHideMoveButtons();
  menuBarMove=false;
}

function hideResultDivs(name) {
  name=name || 'resultDivMain';
  if (dojo.byId(name)) {
      dojo.byId(name).style.display='none';
  }
}

function favoriteReportsTooltipReposition(toolTipId) {
  if (! dijit.byId(toolTipId)) return;
  var toolTip=dijit.byId(toolTipId);
  var node = toolTip.dropDown.domNode;
  if (node.className.substr(-5)=='Right') {
    node.parentNode.style.left=(node.parentNode.offsetLeft+100)+'px';
  }
}
