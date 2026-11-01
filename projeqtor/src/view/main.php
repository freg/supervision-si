<?php
/*** COPYRIGHT NOTICE *********************************************************
 *
 * Copyright 2009-2017 ProjeQtOr - Pascal BERNARD - support@projeqtor.org
 * Contributors : 
 *  2014 - Caccia : fix #1544
 *
 * This file is part of ProjeQtOr.
 * 
 * ProjeQtOr is free software: you can redistribute it and/or modify it under 
 * the terms of the GNU Affero General Public License as published by the Free 
 * Software Foundation, either version 3 of the License, or (at your option) 
 * any later version.
 * 
 * ProjeQtOr is distributed in the hope that it will be useful, but WITHOUT ANY
 * WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS 
 * FOR A PARTICULAR PURPOSE.  See the GNU Affero General Public License for 
 * more details.
 *
 * You should have received a copy of the GNU Affero General Public License along with
 * ProjeQtOr. If not, see <http://www.gnu.org/licenses/>.
 *
 * You can get complete code of ProjeQtOr, other resource, help and information
 * about contributors at http://www.projeqtor.org 
 *     
 *** DO NOT REMOVE THIS NOTICE ************************************************/

/* ============================================================================
 * Main page of application.
 * This page includes Frame definitions and framework requirements.
 * All the other pages are included into this one, in divs, using Ajax.
 * 
 *  Remarks for deployment :
 *    - set isDebug:false in djConfig
 */
$uniqueSessionId=md5(time());
$mobile=false;
require_once "../tool/projeqtor.php";
//include_once ("../tool/file.php"); included in projeqtor.php
if (isset($locked) and $locked) {
  include_once "../view/locked.php";
  exit;
}
header ('Content-Type: text/html; charset=UTF-8');
scriptLog('   ->/view/main.php');
if (Sql::getDbVersion()!=$version) {
	//Here difference of version is an important issue => disconnect and get back to login page.
	//session_destroy();
	Audit::finishSession();
	include_once 'login.php';
	exit;
}
unsetSessionTable('_tablesFormatList', 'User'); // Force refresh of User description (otherwise, after first install User screen is not correct)
$currency=Parameter::getGlobalParameter('currency');
$currencyPosition=Parameter::getGlobalParameter('currencyPosition');
checkVersion(); 
// Set Project & Planning element as cachable : will not change during operation
SqlElement::$_cachedQuery['Project']=array();
SqlElement::$_cachedQuery['ProjectPlanningElement']=array();
SqlElement::$_cachedQuery['PlanningElement']=array();
$keyDownEventScript=NumberFormatter52::getKeyDownEvent();
if(isNewGui())$firstColor=Parameter::getUserParameter('newGuiThemeColor');
$background=(isNewGui())?'#'.$firstColor.' !important':' #C3C3EB';

if(getSessionValue('Token')==''){
  $token=bin2hex(random_bytes(35));
  setSessionValue('Token', $token);
}else{
  $token=getSessionValue('Token');
}
// If this request opens the app in its own tab context (openInNewWindow()/the "New tab" button
// navigate here with directAccess=true), allocate this tab's private session slot right now,
// before session_write_close() below closes the session for writing. Doing it here (rather than
// further down, where this used to happen) is required so that the whole page below - menu,
// project selector, object detail - is rendered from the correctly cloned slot instead of the
// shared default one, and so the clone itself actually gets persisted for later requests.
if (pq_array_key_exists('directAccess', $_REQUEST)) {
  $earlyDirectAccessClass=RequestHandler::getValue('objectClass');
  $earlyDirectAccessId=intval(RequestHandler::getValue('objectId'));
  $index=allocateTabIndex(($earlyDirectAccessClass and $earlyDirectAccessId)?$earlyDirectAccessClass.'#'.$earlyDirectAccessId:null);
}
session_write_close();
if (isset($paramExtraHeaders) ) {
	if (! is_array($paramExtraHeaders)) $paramExtraHeaders=array($paramExtraHeaders);
	foreach ($paramExtraHeaders as $extraHeader) {
		header($extraHeader, true);
	}
}
?><!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta http-equiv="content-type" content="text/html; charset=UTF-8" />
  <meta name="keywork" content="projeqtor, project management" />
  <meta name="description" content="ProjeQtOr is Quality Based Project Organizer. Author: PROJEQTOR. Licensing: AGPL V3." />
  <meta name="author" content="projeqtor" />
  <meta name="Copyright" content="Pascal BERNARD" />
  <meta name=”viewport” content=”width=device-width, initial-scale=1.0″>
  <?php Security::writeMetaCSP();?>
<?php if (! isset($debugIEcompatibility) or $debugIEcompatibility==false) {?>  
  <meta http-equiv="X-UA-Compatible" content="IE=edge" />
<?php }?> 
  <title><?php echo (Parameter::getGlobalParameter('paramDbDisplayName'))?Parameter::getGlobalParameter('paramDbDisplayName'):i18n("applicationTitle");?></title>
  <link rel="stylesheet" type="text/css" href="<?php echoStaticFileNameWithCacheMgt('css/jsgantt.css');?>" />
  <link rel="stylesheet" type="text/css" href="<?php echoStaticFileNameWithCacheMgt('css/documentExplorer.css');?>" />
  <link rel="stylesheet" type="text/css" href="<?php echoStaticFileNameWithCacheMgt('css/prospectionView.css');?>" />
  <link rel="stylesheet" type="text/css" href="<?php echoStaticFileNameWithCacheMgt('css/projeqtor.css');?>" />
  <link rel="stylesheet" type="text/css" href="<?php echoStaticFileNameWithCacheMgt('css/projeqtorFlat.css');?>" />
  <link rel="stylesheet" type="text/css" href="<?php echoStaticFileNameWithCacheMgt('css/projeqtorHRFlat.css');?>" />
  <link rel="shortcut icon" href="img/logo.ico" type="image/x-icon" />
  <link rel="stylesheet" type="text/css" href="<?php echoStaticFileNameWithCacheMgt('../external/dojox/form/resources/CheckedMultiSelect.css');?>" />
  <link rel="stylesheet" type="text/css" href="<?php echoStaticFileNameWithCacheMgt('../external/dojox/layout/resources/ResizeHandle.css');?>" />
  <link rel="icon" href="img/logo.ico" type="image/x-icon" />
  <link rel="stylesheet" type="text/css" href="<?php echoStaticFileNameWithCacheMgt('css/projeqtorHr.css');?>" />
  <link rel="stylesheet" type="text/css" href="<?php echoStaticFileNameWithCacheMgt('../external/dojox/calendar/themes/tundra/Calendar.css');?>" />
  <?php if (isNewGui()) {?>
  <link rel="stylesheet" type="text/css" href="<?php echoStaticFileNameWithCacheMgt('css/projeqtorNew.css');?>" />
  <link rel="stylesheet" type="text/css" href="<?php echoStaticFileNameWithCacheMgt('../external/codrops/css/component.css');?>" />
  <script type="text/javascript" src="<?php echoStaticFileNameWithCacheMgt('../external/codrops/js/modernizr-custom.js');?>" ></script>
  <script type="text/javascript" src="<?php echoStaticFileNameWithCacheMgt('../external/codrops/js/classie.js');?>" ></script>
  <script type="text/javascript" src="<?php echoStaticFileNameWithCacheMgt('../external/codrops/js/mainLeftMenu.js');?>" ></script>
  <link rel="stylesheet" type="text/css" href="<?php echoStaticFileNameWithCacheMgt('../external/icomoon/css/style.css');?>" />
  <script type="text/javascript" src="<?php echoStaticFileNameWithCacheMgt('../external/icomoon/js/liga.js');?>" ></script>
  <script type="text/javascript" src="<?php echoStaticFileNameWithCacheMgt('js/projeqtorNewGui.js');?>" ></script>
  <script type="text/javascript" src="<?php echoStaticFileNameWithCacheMgt('js/projeqtorSelector.js');?>" ></script>
  <script type="text/javascript" src="<?php echoStaticFileNameWithCacheMgt('../external/dojox/mobile/deviceTheme.js');?>" data-dojo-config="mblUserAgent: 'Custom'"></script>
  <?php }?>
  <?php if (isModernUi()) {?>
  <link rel="stylesheet" type="text/css" href="<?php echoStaticFileNameWithCacheMgt('css/projeqtorModern.css');?>" />
  <?php }?>
  <script type="text/javascript" src="<?php echoStaticFileNameWithCacheMgt('js/dynamicCss.js');?>" ></script>
  <script type="text/javascript" src="<?php echoStaticFileNameWithCacheMgt('../external/html2canvas/html2canvas.js');?>"></script>
  <?php if (isHtml5()) {?>
  <script type="text/javascript" src="<?php echoStaticFileNameWithCacheMgt('../external/pdfmake/pdfmake.min.js');?>"></script>
  <?php }?>
  <script type="text/javascript" src="<?php echoStaticFileNameWithCacheMgt('../external/pdfmake/vfs_fonts.js');?>"></script>
  <script type="text/javascript" src="<?php echoStaticFileNameWithCacheMgt('../external/CryptoJS/rollups/md5.js');?>" ></script>
  <script type="text/javascript" src="<?php echoStaticFileNameWithCacheMgt('../external/CryptoJS/rollups/sha256.js');?>" ></script>
  <script type="text/javascript" src="<?php echoStaticFileNameWithCacheMgt('../external/phpAES/aes.js');?>" ></script>
  <script type="text/javascript" src="<?php echoStaticFileNameWithCacheMgt('../external/phpAES/aes-ctr.js');?>" ></script>
  <script type="text/javascript" src="<?php echoStaticFileNameWithCacheMgt('js/projeqtor.js');?>" ></script>
<?php if ($indexRequest) { ?>
  <script type="text/javascript">
    // This request already carried a private tab index : make it the tab's current one,
    // overriding projeqtor.js's default null.
    directAccessIndex=<?php echo intval($indexRequest); ?>;
  </script>
<?php } ?>
  <script type="text/javascript" src="<?php echoStaticFileNameWithCacheMgt('js/projeqtorDataTools.js');?>" ></script>
  <script type="text/javascript" src="<?php echoStaticFileNameWithCacheMgt('js/jsgantt.js');?>"></script>
  <script type="text/javascript" src="<?php echoStaticFileNameWithCacheMgt('js/projeqtorWork.js');?>" ></script>
  <script type="text/javascript" src="<?php echoStaticFileNameWithCacheMgt('js/projeqtorDialog.js');?>" ></script>
  <script type="text/javascript" src="<?php echoStaticFileNameWithCacheMgt('js/projeqtorDialogAlertNotification.js');?>"></script>
  <script type="text/javascript" src="<?php echoStaticFileNameWithCacheMgt('js/projeqtorDialogAdminTool.js');?>" ></script>
  <script type="text/javascript" src="<?php echoStaticFileNameWithCacheMgt('js/projeqtorDialogAttachNoteLink.js');?>" ></script>
  <script type="text/javascript" src="<?php echoStaticFileNameWithCacheMgt('js/projeqtorDialogColumnsLayout.js');?>" ></script>
  <script type="text/javascript" src="<?php echoStaticFileNameWithCacheMgt('js/projeqtorDialogConfiguration.js');?>" ></script>
  <script type="text/javascript" src="<?php echoStaticFileNameWithCacheMgt('js/projeqtorDialogDocument.js');?>" ></script>
  <script type="text/javascript" src="<?php echoStaticFileNameWithCacheMgt('js/projeqtorDialogFinancial.js');?>" ></script>
  <script type="text/javascript" src="<?php echoStaticFileNameWithCacheMgt('js/projeqtorDialogFilter.js');?>" ></script>
  <script type="text/javascript" src="<?php echoStaticFileNameWithCacheMgt('js/projeqtorDialogMail.js');?>" ></script>
  <script type="text/javascript" src="<?php echoStaticFileNameWithCacheMgt('js/projeqtorDialogMenu.js');?>" ></script>
  <script type="text/javascript" src="<?php echoStaticFileNameWithCacheMgt('js/projeqtorDialogObjects.js');?>" ></script>
  <script type="text/javascript" src="<?php echoStaticFileNameWithCacheMgt('js/projeqtorDialogPlanning.js');?>" ></script>
  <script type="text/javascript" src="<?php echoStaticFileNameWithCacheMgt('js/projeqtorDialogPoker.js');?>" ></script>
  <script type="text/javascript" src="<?php echoStaticFileNameWithCacheMgt('js/projeqtorPlanning.js');?>" ></script>
  <script type="text/javascript" src="<?php echoStaticFileNameWithCacheMgt('js/projeqtorPlanSelect.js');?>" ></script>
  <script type="text/javascript" src="<?php echoStaticFileNameWithCacheMgt('js/jsDocExplorer.js');?>" ></script>
  <script type="text/javascript" src="<?php echoStaticFileNameWithCacheMgt('js/docExplorerScreen.js');?>" ></script>
  <script type="text/javascript" src="<?php echoStaticFileNameWithCacheMgt('js/jsProspectionView.js');?>" ></script>
  <script type="text/javascript" src="<?php echoStaticFileNameWithCacheMgt('js/projeqtorRevisionUpdate.js');?>" ></script>
  <script type="text/javascript" src="<?php echoStaticFileNameWithCacheMgt('js/liveMeeting.js');?>" ></script>
  <script type="text/javascript" src="<?php echoStaticFileNameWithCacheMgt('js/kanban.js');?>" ></script>
  <script type="text/javascript" src="<?php echoStaticFileNameWithCacheMgt('js/jsKanban.js');?>"></script>
  <script type="text/javascript" src="<?php echoStaticFileNameWithCacheMgt('js/projectDashboard.js');?>" ></script>
  <script type="text/javascript" src="<?php echoStaticFileNameWithCacheMgt('js/jsBacklog.js');?>"></script>
  <script type="text/javascript" src="<?php echoStaticFileNameWithCacheMgt('js/projeqtorFormatter.js');?>" ></script>
  <script type="text/javascript" src="<?php echoStaticFileNameWithCacheMgt('js/projeqtorDialogLayout.js');?>" ></script>
  <script type="text/javascript" src="<?php echoStaticFileNameWithCacheMgt('../external/ckeditor/ckeditor.js');?>"></script>
  <script type="text/javascript" src="<?php echoStaticFileNameWithCacheMgt('../external/chartJS/dist/chart.min.js"');?> ></script>
  <script type="text/javascript" src="<?php echoStaticFileNameWithCacheMgt('../external/chartJS/plugins/datalabels/chartjs-plugin-datalabels.min.js');?>" ></script>
  <script type="text/javascript" src="<?php echoStaticFileNameWithCacheMgt('js/projeqtorHR.js');?>" ></script>
   
 <script type="text/javascript" src="<?php echoStaticFileNameWithCacheMgt('../external/promise/es6-promise.min.js');?>"></script>
 <script type="text/javascript" src="<?php echoStaticFileNameWithCacheMgt('../external/promise/es6-promise.auto.min.js');?>"></script>
 
  <script type="text/javascript">
        var dojoConfig = {
            modulePaths: {"i18n":"../../tool/i18n",
                          "i18nCustom":"../../plugin"},
            parseOnLoad: true,
            isDebug: <?php echo getBooleanValueAsString(Parameter::getGlobalParameter('paramDebugMode'));?>
        };
  </script>
  <script type="text/javascript" src="<?php echoStaticFileNameWithCacheMgt('../external/dojo/dojo.js');?>"></script>
  <script type="text/javascript" src="<?php echoStaticFileNameWithCacheMgt('../external/dojo/projeqtorDojo.js');?>"></script>
  <?php Plugin::includeAllFiles();?>
  <script type="text/javascript"> 
    <?php if (getSessionValue('mobile',false,true)==true) {?> window.location.replace("../mobile/index.php?csrfToken=<?php echo $token; ?>"); <?php }?>
    var csrfToken='<?php echo $token?>';
    var isNewGui=<?php echo (isNewGui())?'true':'false';?>;
    var isModernUi=<?php echo (isModernUi())?'true':'false';?>;
    var customMessageExists=<?php echo(file_exists(Plugin::getDir()."/nls/$currentLocale/lang.js"))?'true':'false';?>; 
    var isMenuBarSource = false; 
    dojo.require("dojo.data.ItemFileWriteStore");
    dojo.require("dojo.date");
    dojo.require("dojo.date.locale");
    dojo.require("dojo.dnd.Container");
    dojo.require("dojo.dnd.Manager");
    dojo.require("dojo.dnd.Source");
    dojo.require("dojo.dom-construct");
    dojo.require("dojo.dom-geometry");
    dojo.require("dojo.i18n");
    dojo.require("dojo.fx.easing");
    dojo.require("dojo.NodeList-fx");
    dojo.require("dojo.parser");
    dojo.require("dojo.query");
    dojo.require("dojo.store.DataStore");
    dojo.require("dijit.ColorPalette");
    dojo.require("dijit.Dialog"); 
    //dojo.require("dijit.Editor");
    //dojo.require("dijit._editor.plugins.AlwaysShowToolbar");
    //dojo.require("dijit._editor.plugins.FullScreen");
    //dojo.require("dijit._editor.plugins.FontChoice");
    //dojo.require("dijit._editor.plugins.Print");
    //dojo.require("dijit._editor.plugins.TextColor");
    dojo.require("dijit.Fieldset");
    dojo.require("dijit.form.Button");
    dojo.require("dijit.form.CheckBox");
    dojo.require("dojox.form.CheckedMultiSelect");
    dojo.require("dojox.layout.ResizeHandle");
    dojo.require("dijit.form.ComboBox");
    dojo.require("dijit.form.DateTextBox");
    dojo.require("dijit.form.FilteringSelect");
    dojo.require("dijit.form.Form");
    dojo.require("dijit.form.HorizontalSlider");
    dojo.require("dijit.form.HorizontalRuleLabels");
    dojo.require("dijit.form.MultiSelect");
    dojo.require("dijit.form.NumberSpinner");
    dojo.require("dijit.form.NumberTextBox");
    dojo.require("dijit.form.RadioButton");
    dojo.require("dijit.form.Select");
    dojo.require("dijit.form.Textarea");
    dojo.require("dijit.form.TextBox");
    dojo.require("dijit.form.TimeTextBox");
    dojo.require("dijit.form.ValidationTextBox");
    dojo.require("dijit.InlineEditBox");
    dojo.require("dijit.layout.AccordionContainer");
    dojo.require("dijit.layout.BorderContainer");
    dojo.require("dijit.layout.ContentPane");
    dojo.require("dijit.layout.TabContainer");
    dojo.require("dijit.Menu"); 
    dojo.require("dijit.MenuBar"); 
    dojo.require("dijit.MenuBarItem");
    dojo.require("dijit.PopupMenuBarItem");
    dojo.require("dijit.ProgressBar");
    dojo.require("dijit.TitlePane");
    dojo.require("dijit.Toolbar");
    dojo.require("dijit.Tooltip");
    dojo.require("dijit.Tree"); 
    dojo.require("dojox.calendar.Calendar");
    dojo.require("dojox.form.FileInput");
    dojo.require("dojox.form.Uploader");
    dojo.require("dojox.form.uploader.FileList");
    dojo.require("dojox.fx.scroll");
    dojo.require("dojox.fx");
    dojo.require("dojox.grid.DataGrid");
//    dojo.require("dojox.grid.ColumnFilter");
    dojo.require("dojox.mobile.parser");
    dojo.require("dojox.mobile.Switch");
    dojo.require("dojox.mobile.SwapView");
    dojo.require("dojox.mobile.TabBar");
    dojo.require("dojox.mobile.PageIndicator");
    dojo.require("dojox.image.Lightbox");
//    dojo.declare("dojox.grid.DataGrid", [dojox.grid.DataGrid, dojox.grid.ColumnFilter], {});
    dojo.subscribe("/dnd/drop", function(source, nodes, copy, target){
      if(target.id == null){
      //gautier #translationApplication
        //if (target.id == null) we are in dgrid DROP , nothing to do.
  	    if(target.parent.id=='menuBarDndSource1' || target.parent.id=='menuBarDndSource2' || target.parent.id=='menuBarDndSource3' || target.parent.id=='menuBarDndSource4' || target.parent.id=='menuBarDndSource5'){
  	    	var selection = getSourceSelectedItem(nodes);
        	setTimeout('moveMenuBarItem("'+ source.id +'", "'+ target.parent.id +'", "'+selection+'", "'+copy+'")',100); 
  	    }
      }else if(target.id=='columnManagmentDndTarget' || target.id=='columnManagmentDndSource'){
      	updateKanbanColumnManagment(source, target, nodes);
      }else if (target.id=='dndListToday'){
        var selection = getSourceSelectedItem(nodes);
      	setTimeout('moveTodayDiv("'+ source.id +'", "'+ target.parent.id +'", "'+selection+'")',100); 
        
      } else if (target.id=='subscriptionAvailable' || target.id=='subscriptionSubscribed') {
        if (source.id==target.id) return;
        for (var i=0;i<nodes.length;i++) {
          var item=nodes[i];
          var mode=(target.id=='subscriptionAvailable')?'off':'on';
          changeSubscriptionFromDialog(mode,'other',item.getAttribute('objectclass'),item.getAttribute('objectid'),item.getAttribute('userid'),null,item.getAttribute('currentuserid'))
        }
      }else if (dojo.byId('objectClassManual')
             && dojo.byId('objectClassManual').value == 'DocumentExplorer'
             && typeof documentExplorerHandleDrop == 'function'
             && documentExplorerHandleDrop(source, nodes, target)) {
        return;
      }else if (source.id!=target.id) {
    	  if( target.id=='menuBarDndSource' || target.id=='menuBarDndSource1' || target.id=='menuBarDndSource2' || target.id=='menuBarDndSource3' || target.id=='menuBarDndSource4' || target.id=='menuBarDndSource5'){
    		  var selection = getSourceSelectedItem(nodes);
    	      setTimeout('moveMenuBarItem("'+source.id+'", "'+ target.id +'", "'+selection+'", "'+copy+'")',100); 
          }else if(target.id=='removeMenuDiv'){
        	  setTimeout('removeMenuBarItem("'+ target.id +'")',100);
    	  }else{
        	  return;
          }
      }else if(source.id.substring(0,11) =='dndSubTask_'){
  	    setTimeout('reorderSubTask('+source.node.id+')',100);  
      } else if (nodes.length>0 && nodes[0] && target && target.current) {
        var moveTasks=false;
        var arrayTasks=new Array();
        dojo.forEach(nodes, function(selectedItem) {
           var idFrom = selectedItem.id;
           var idTo = target.current.id;
           if (target.id=='dndSourceTable') {
             if(checkFormChangeInProgress())return;
             moveTasks=idTo;
             arrayTasks.push(idFrom);
           } else  if (target.id=='dndPlanningColumnSelector') {
          	 setTimeout('movePlanningColumn("' + idFrom + '", "' + idTo + '")',100);
           } else  if (target.id=='dndPlanningHeaderColumn') {
          	 setTimeout('movePlanningHeaderColumn("' + idFrom + '", "' + idTo + '")',100);
           } else  if (target.id=='dndListColumnSelector') {
             setTimeout('moveListColumn("' + idFrom + '", "' + idTo + '")',100);
           } else if (target.id=='dndTodayParameters') {
             setTimeout('reorderTodayItems()',100);  
           } else if (target.id=='dndFavoriteReports') {
          	 setTimeout('reorderFavoriteReportItems()',100);  
           } else if (target.id=='dndListFilterSelector') {
             setTimeout('moveFilterListColumn()',100); 
           } else if( target.id=='dndListFilterSelector2') {
             setTimeout('moveFilterListColumn2()',100); 
           } else if( target.id=='dndHierarchicalBudgetList') {
             setTimeout('moveBudgetFromHierarchicalView("' + idFrom + '", "' + idTo + '")',100); 
           } else if( target.id=='dndHierarchicalSkillList') {
             setTimeout('moveSkillFromHierarchicalView("' + idFrom + '", "' + idTo + '")',100); 
           } else if( target.id=='menuBarDndSource' || target.id=='menuBarDndSource1' || target.id=='menuBarDndSource2' || target.id=='menuBarDndSource3' || target.id=='menuBarDndSource4' || target.id=='menuBarDndSource5') {
        	   var selection = getSourceSelectedItem(nodes);
               setTimeout('moveMenuBarItem("'+ source.id +'", "'+ target.id +'", "'+selection+'", "'+copy+'")',100); 
           } else if (target.id=='dndListLayoutSelector') {
             setTimeout('moveLayoutListColumn()',100); 
           } else if (target.id=='dndListReportLayoutSelector') {
             setTimeout('moveReportLayoutListColumn()',100); 
           }else if(target.id=='today'){
             //
           }
        });
        if (moveTasks) {
        //setTimeout('moveTask("' + idFrom + '", "' + idTo + '")',100);
          var execMove=setTimeout(function() { moveTask(arrayTasks, moveTasks); },20);
        }
      }else if(source.id == target.id){
    	  if(source.id == 'menuBarDndSource'){
    		  dojo.byId('anotherBarContainer').style.display = 'none';
    		  dojo.byId('menuBarListDiv').setAttribute('style', 'overflow:hidden;width: 100%;height: 43px;border-left: 1px solid var(--color-dark);');
    	  }
    	  dojo.byId('removeMenuDiv').style.visibility = 'hidden';
      }
    });
    dojo.subscribe("/dnd/start", function(source, nodes, copy, target){
      source.sync();
      if (!source || !source.id) return;
      if(source.id.indexOf('menuBarDndSource') != -1){
   	   dojo.extend( dojo.dnd.Source, { copyState: function( keyPressed, self ){
  	          return keyPressed; }}
 	       );
      }
       if(source.id == 'menuBarDndSource'){
           dojo.byId('anotherBarContainer').style.display = 'block';
           dojo.byId('menuBarListDiv').setAttribute('style', 'overflow:hidden;width: 100%;height: 43px;border-radius: 5px;border-left: 1px solid var(--color-dark);');
           dojo.byId('removeMenuDiv').style.visibility = 'visible';
       } else if (source.id.substr(0,16)=='menuBarDndSource') {
    	   dojo.byId('removeMenuDiv').style.visibility = 'visible';
       }
       if(source.id == 'dndSourceTable')
       {
         document.activeElement.blur();
         if(checkFormChangeInProgress())return;
       }
       if(source.id == 'dndPlanningHeaderColumn')
       {
         document.activeElement.blur();
         if(checkFormChangeInProgress())return;
       }
    });
    dojo.subscribe("/dnd/cancel", function(){
      if (isNewGui) {
      	if(dojo.byId('isEditFavorite').value == 'true'){
      		dojo.byId('isEditFavorite').value = 'false';
      	}else{
      		dojo.byId('isEditFavorite').value = 'true';
      	}
  	    dojo.byId('anotherBarContainer').style.display = 'none';
  	    dojo.byId('menuBarListDiv').setAttribute('style', 'overflow:hidden;width: 100%;height: 43px;border-left: 1px solid var(--color-dark);');
  	    dojo.byId('removeMenuDiv').style.visibility = 'hidden';
      }
    });


    dndMoveInProgress=false;
    dojo.subscribe("/dnd/drop/before", function(source, nodes, copy, target){
        dndMoveInProgress=true;
        setTimeout("dndMoveInProgress=false;",50);
        if (target && target.id && target.id.indexOf('backlogColumn')!=-1 && source.id!=target.id){
            sendChangeBacklog(nodes[0], source, target);
        }else if (target && target.id && target.id.indexOf('kanbanColumn')!=-1 && source.id!=target.id){
            sendChangeKanban(nodes[0], source, target);
        }else if (target && target.id && target.id.indexOf('raciRoleColumn_')==0 && source.id!=target.id){
            if (typeof raciStoreAvailableState == 'function') raciStoreAvailableState();
            sendChangeRaci(nodes, source, target);
        }
        if (source && source.selectNone) {
            source.selectNone();
        }
    });
    <?php $audit=New Audit();
  	$cpt=$audit->countSqlElementsFromCriteria(array('auditDay'=>date('Ymd')));
  	if($cpt < 1){?>
    checkSubscribeCode('login');
    <?php }?>
    var extraLastNewParam='<?php echo RequestHandler::getNewsInfo();?>';
    var isHosted=<?php echo (isset($hosted) and $hosted===true)?'true':'false';?>;
    // Management of history
    var historyTable=new Array();
    var historyPosition=-1;    
    var fadeLoading=<?php echo getBooleanValueAsString(Parameter::getGlobalParameter('paramFadeLoadingMode'));?>;
    var refreshUpdates="YES";
    var aesLoginHash="<?php echo md5(session_id());?>";
    var printInNewWindow=<?php echo (getPrintInNewWindow())?'true':'false';?>;
    var pdfInNewWindow=<?php echo (getPrintInNewWindow('pdf'))?'true':'false';?>;
    var alertCheckTime='<?php echo Parameter::getGlobalParameter('alertCheckTime');?>';
    //var scaytAutoStartup=<?php echo (Parameter::getUserParameter('scaytAutoStartup')=='NO')?'false':'true';?>;
    var scaytAutoStartup=false; // New in V9.3.0, always disable Scayt, let default browser correction
    var offDayList='<?php echo Calendar::getOffDayList();?>';
    var workDayList='<?php echo Calendar::getWorkDayList();?>';
    var applicationName='<?php echo htmlEncode(((Parameter::getGlobalParameter('paramDbDisplayName'))?Parameter::getGlobalParameter('paramDbDisplayName'):i18n("applicationTitle")),'protectQuotes');?>';
		var autoHideMenuLeftDashboard="<?php echo Parameter::getUserParameter("autoHideMenuLeftDashboard");?>";
    var oldMenuLeftPos=false;
// MTY - MULTI CALENDAR    
    var uOffDayList='<?php echo Calendar::getOffDayList(getSessionUser()->idCalendarDefinition);?>';
    var uWorkDayList='<?php echo Calendar::getWorkDayList(getSessionUser()->idCalendarDefinition);?>';
    var globalOffDayList= new Array();
    var globalWorkDayList= new Array();
    var globalDefaultOffDays = new Array();
    <?php foreach (SqlList::getList('CalendarDefinition', 'id') as $idCalendarDefinition){
     echo "globalOffDayList[$idCalendarDefinition]='".Calendar::getOffDayList($idCalendarDefinition)."';";
     echo "globalWorkDayList[$idCalendarDefinition]='".Calendar::getWorkDayList($idCalendarDefinition)."';";
    } ?>
    //var pOffDayList= new Array();
    //var pWorkDayList= new Array();
    var projectCalendar=new Array();
// MTY - MULTI CALENDAR    
    var defaultOffDays=new Array();
    //var projectOffDays=new Array();
    var defaultMenu="<?php echo Parameter::getUserParameter('defaultMenu'); ?>";
    <?php 
// MTY - GENERIC DAY OFF
    $defaultOffDays = array();
    $globalDefaultOffDays = array();
    //$projectOffDays = array();
    if (Parameter::getGlobalParameter('OpenDaySunday')=='offDays') {
        echo "defaultOffDays[0]=0;";
        $defaultOffDays[0] = 1;
    }    
    if (Parameter::getGlobalParameter('OpenDayMonday')=='offDays') {
        echo "defaultOffDays[1]=1;"; 
        $defaultOffDays[1] = 1;
    }    
    if (Parameter::getGlobalParameter('OpenDayTuesday')=='offDays') {
        echo "defaultOffDays[2]=2;"; 
        $defaultOffDays[2] = 1;
    }    
    if (Parameter::getGlobalParameter('OpenDayWednesday')=='offDays') {
        echo "defaultOffDays[3]=3;"; 
        $defaultOffDays[3] = 1;
    }    
    if (Parameter::getGlobalParameter('OpenDayThursday')=='offDays') {
        echo "defaultOffDays[4]=4;";
        $defaultOffDays[4] = 1;
    }    
    if (Parameter::getGlobalParameter('OpenDayFriday')=='offDays') {
        echo "defaultOffDays[5]=5;"; 
        $defaultOffDays[5] = 1;
    }    
    if (Parameter::getGlobalParameter('OpenDaySaturday')=='offDays') {
        echo "defaultOffDays[6]=6;";
        $defaultOffDays[6] = 1;        
    } 
    $calDef = new CalendarDefinition(getSessionUser()->idCalendarDefinition);
    for ($i=0;$i<=6;$i++) {
        $dayOfWeek = "dayOfWeek".$i;
        if ($calDef->$dayOfWeek==1 and !pq_array_key_exists($i, $defaultOffDays)) {
            echo "defaultOffDays[$i]=$i;";
        }
    }
    foreach (SqlList::getList('CalendarDefinition', 'id') as $idCalendarDefinition){
      $calDef = new CalendarDefinition($idCalendarDefinition);
      $globalDefaultOffDays[$idCalendarDefinition] = array();
      echo "globalDefaultOffDays[$idCalendarDefinition] = new Array();";
      for ($i=0;$i<=6;$i++) {
          $dayOfWeek = "dayOfWeek".$i;
          if ($calDef->$dayOfWeek==1 and !pq_array_key_exists($i, $globalDefaultOffDays[$idCalendarDefinition])) {
              echo "globalDefaultOffDays[$idCalendarDefinition][$i]=$i;";
              $globalDefaultOffDays[$idCalendarDefinition][$i]=$i;
          }
      }
    }
    $projectCalendar = new Project();
    $where = "idle = 0 and idCalendarDefinition is not null";
    $projectCalendarList = $projectCalendar->getSqlElementsFromCriteria(null,null,$where,null, null,true);
    foreach ($projectCalendarList as $project){
      //$calDef = new CalendarDefinition($project->idCalendarDefinition);
      echo "projectCalendar[$project->id]=$project->idCalendarDefinition;";
      //$projectOffDays[$project->id] = array();
      //echo "projectOffDays[$project->id] = new Array();";
      //echo "pOffDayList[$project->id]='".Calendar::getOffDayList($project->idCalendarDefinition)."';";
      //echo "pWorkDayList[$project->id]='".Calendar::getWorkDayList($project->idCalendarDefinition)."';";
      //for ($i=0;$i<=6;$i++) {
      //  $dayOfWeek = "dayOfWeek".$i;
      //  if ($calDef->$dayOfWeek==1 and !pq_array_key_exists($i, $projectOffDays[$project->id])) {
      //    echo "projectOffDays[$project->id][$i]=$i;";
      //    $projectOffDays[$project->id][$i]=1;
      //  }
      //}
    }
// MTY - GENERIC DAY OFF
    ?>
// BEGIN - ADD BY TABARY - NOTIFICATION SYSTEM
    var paramNotificationSystemActiv=<?php echo (Module::isModuleActive('moduleNotification'))?'true':'false'; ?>;
    var totalUnreadNotificationsCount=0;
// END - ADD BY TABARY - NOTIFICATION SYSTEM
// MTY - LEAVE SYSTEM
    var isLeaveSystemActiv = <?php echo (isLeavesSystemActiv()?1:0); ?>;
// MTY - LEAVE SYSTEM
    var draftSeparator='<?php echo Parameter::getGlobalParameter('draftSeparator');?>';
    var paramCurrency='<?php echo $currency;?>';
    var paramCurrencyPosition='<?php echo $currencyPosition;?>';
    var paramWorkUnit='<?php echo Parameter::getGlobalParameter('workUnit');?>';
    if (! paramWorkUnit) paramWorkUnit='days';
    var paramImputationUnit='<?php echo Parameter::getGlobalParameter('imputationUnit');?>';
    if (! paramImputationUnit) paramImputationUnit='days';
    var paramHoursPerDay='<?php echo Parameter::getGlobalParameter('dayTime');?>';
    if (! paramHoursPerDay) paramHoursPerDay=8;
    var paramConfirmQuit="<?php echo Parameter::getUserParameter("paramConfirmQuit")?>";
    var browserLocaleDateFormat="<?php echo Parameter::getUserParameter('browserLocaleDateFormat');?>";
    var browserLocaleDateFormatJs=browserLocaleDateFormat.replace(/D/g,'d').replace(/Y/g,'y');
    var browserLocaleTimeFormat="<?php echo Parameter::getUserParameter('browserLocaleTimeFormat');?>";
    <?php $fmt=getNumberFormatter52( $browserLocale, NumberFormatter52::DECIMAL );?>
    var browserLocaleDecimalSeparator="<?php echo $fmt->decimalSeparator?>";
    var aesKeyLength=<?php echo Parameter::getGlobalParameter('aesKeyLength');?>;
    var refreshAuto="<?php echo (Parameter::getUserParameter('refreshAuto')!='')?Parameter::getUserParameter('refreshAuto'):0;?>";
    var refreshAutoTimer="<?php echo (Parameter::getUserParameter('refreshAutoTimer')!='')?Parameter::getUserParameter('refreshAutoTimer'):30;?>";
    var noRefresh=false;
    var arraySelectedProject = new Array();
    <?php foreach (Project::getSelectedProjectList() as $key=>$idP){
      echo "arraySelectedProject[$key]='$idP';";
    }?>
    var selectedFavoriteProject = "<?php echo Parameter::getUserParameter('idFavoriteProjectList');?>";
    var favoriteProjectsArray = '';
    var isColorBlind = "<?php echo Parameter::getUserParameter('colorBlindPlanning');?>";
    var fromContextMenu = false;
    var lockPlanningSaveRefresh = 0;
    var lockPlanningBarDetail = "<?php echo (Parameter::getUserParameter('lockPlanningBarDetail') == '1' or Parameter::getUserParameter('lockPlanningBarDetail') == '')?1:0;?>";
    var planningClickAction = "<?php echo (Parameter::getUserParameter('planningClickAction') == '1')?1:0;?>";
    var documentExplorerClickAction = "<?php echo (Parameter::getUserParameter('documentExplorerClickAction') == '1')?1:0;?>";
    var documentExplorerPreviewOnClick = "<?php echo (Parameter::getUserParameter('documentExplorerPreviewOnClick') == '1')?1:0;?>";
    var displayUnitProgress = "<?php echo (Parameter::getUserParameter('displayUnitProgress') == '1')?1:0;?>";
    var showTaskNameOnPlanningBar = "<?php echo (Parameter::getUserParameter('showTaskNameOnPlanningBar') == '1')?1:0;?>";
    var showHatchOnPlanningBar = "<?php echo (Parameter::getUserParameter('showHatchOnPlanningBar') == '1')?1:0;?>";
    var showTaskNameOnPlanningBarResources = "<?php echo (Parameter::getUserParameter('showTaskNameOnPlanningBarResources') == '1')?1:0;?>";
    var planningShowResource = "<?php echo (Parameter::getUserParameter('planningShowResource') == '1')?1:0;?>";
    var autoUpdateLeftWorkOnPool = "<?php echo (Parameter::getGlobalParameter('autoUpdateLeftWorkOnPool') != 'NO')?1:0;?>";
    var autoScrollPlanningBar = "<?php echo (Parameter::getUserParameter('autoScrollPlanningBar') == '1')?1:0;?>";
    var removeQuickPlanningFeature = "<?php echo (Parameter::getGlobalParameter('removeQuickPlanningFeature') == 'YES')?1:0;?>";
    var showHiddenLevelCondensed = "<?php echo (Parameter::getUserParameter('showHiddenLevelCondensed') == '1')?1:0;?>";
    var directFilterArray = new Array();
    var lastKawaMsg="<?php echo Parameter::getUserParameter("lastKawaMsg")?>";
    var globalPageLinesCount=<?php echo Parameter::getPlanningPageLineCount();?>;
    var statusColorArray = new Array();
    <?php $statusTab=SqlList::getList('Status','color');
    foreach ($statusTab as $idStatus=>$color){
      echo "statusColorArray[$idStatus]='$color';";
    }?>
    var wpShowProject = "<?php echo (Parameter::getUserParameter("planningShowProject") != "0" and Parameter::getUserParameter("planningShowProject") != "")?1:0;?>";
    var wpShowProjectColor = "<?php echo (Parameter::getUserParameter("planningShowProjectColor") == "1")?1:0;?>";
    var wpShowLateColor = "<?php echo (Parameter::getUserParameter("planningShowLateColor") == "1")?1:0;?>";
    var wpShowLateColorPriority = "<?php echo (Parameter::getUserParameter("planningShowLateColorPriority") == "1")?1:0;?>";
    var wpShowPoolForResource = "<?php echo (Parameter::getUserParameter("workPlanShowPoolForResource") == "1")?1:0;?>";
    var wpShowResourceWithoutWork = "<?php echo (Parameter::getUserParameter("workPlanShowResourceWithoutWork") == "1")?1:0;?>";
    var wpShowWorkDecimals = "<?php echo (Parameter::getUserParameter("workPlanShowWorkDecimals") != "0" and Parameter::getUserParameter("workPlanShowWorkDecimals") != "")?1:0;?>";
    var multiSelectionInputPressed = false;
    var focusEditRowLine = false;
    window.onresize=function() {
      if (dojo.byId('objectClassManual') && dojo.byId('objectClassManual').value=='Planning') {
        if (g) {g.DrawDependencies();}
      } 
    };
//     dojo.ready(function() {
//     	var FilteredGrid = dojo.declare([dojox.grid.DataGrid, dojox.grid.ColumnFilter], {});
// 		});
    dojo.addOnLoad(function(){
      currentLocale="<?php echo $currentLocale;?>";
      // Set color depending on theme for New Gui
      if (isNewGui) {
        changeTheme('<?php echo getTheme();?>');
        setColorTheming('<?php echo '#'.Parameter::getUserParameter('newGuiThemeColor');?>','<?php echo '#'.Parameter::getUserParameter('newGuiThemeColorBis');?>');
        if (dojo.byId('ml-menu')) {
         (function() {
            var menuEl = dojo.byId('ml-menu'),
                         mlmenu = new MLMenu(menuEl, {
                           initialBreadcrumb : i18n('homePage'), // initial breadcrumb text
                           backCtrl : false, // show back button
                         });
          })();
          menuLeftObject=new menuLeft( dojo.byId( 'mainDiv' ) );
        } else {
          return;
        }
      }
      
      //setColorTheming('blue');
      // FIX IE11 not recognized as IE
      if( !dojo.isIE ) {
        var userAgent = navigator.userAgent.toLowerCase();
        var IEReg = /(msie\s|trident.*rv:)([\w.]+)/;
        var match = IEReg.exec(userAgent);
        if( match )
          dojo.isIE = match[2] - 0;
        else
          dojo.isIE = undefined;
      }

      //Disable the key events Ctrl and Shift
      dojo.extend( dojo.dnd.Source, { copyState: function( keyPressed, self ){
          return false; }}
      );
      <?php 
      if (sessionValueExists('project')) {
        $proj=getSessionValue('project');
        if(strpos($proj, ",") != null){
        	$proj="*";
        }
      } else {
        $proj="*";
      }
      echo "currentSelectedProject='$proj';";
      if (sessionValueExists('hideMenu')) {
        if (getSessionValue('hideMenu')!='NO') {
          echo "menuHidden=true;";
          echo "menuShowMode='" . getSessionValue('hideMenu') . "';";
        }
      }
      if (Parameter::getUserParameter('paramScreen')=='switch') {
        echo "switchedMode=true;";
        echo "switchListMode='CLICK';";
      }    
      ?>
      dijit.Tooltip.defaultPosition=["below", "right"];
      addMessage("<?php echo htmlEncode(i18n('welcomeMessage').' '.((getSessionUser()->resourceName)?getSessionUser()->resourceName:getSessionUser()->name),'qotes');?>");
      //dojo.byId('body').className='<?php echo getTheme();?>';
      saveResolutionToSession();
      saveBrowserLocaleToSession();
      aboutMessage="<?php echo $aboutMessage;?>";
      aboutMessage+='<br/><b>PHP <?php echo phpversion();?></b><br/>';
      aboutMessage+='<br/><b>'+i18n('externalLibrary')+'</b><br/>';
      aboutMessage+='&nbsp;&nbsp;.&nbsp;CK Editor : '+CKEDITOR.version+'<br/>';
      aboutMessage+='&nbsp;&nbsp;.&nbsp;Dojo : '+dojo.version.major+"."+dojo.version.minor+"."+dojo.version.patch+'<br/>';
      aboutMessage+='&nbsp;&nbsp;.&nbsp;html2canvas : <?php include_once('../external/html2canvas/getVersion.php');echo html2canvasGetVersion();?>'+'<br/>';
      aboutMessage+='&nbsp;&nbsp;.&nbsp;html2pdf : <?php use Spipu\Html2Pdf\Html2Pdf;require_once '../external/html2pdf/vendor/autoload.php';$html2pdf = new Html2Pdf();echo $html2pdf->getVersion();?>'+'<br/>';
      aboutMessage+='&nbsp;&nbsp;.&nbsp;HtmlPhpExcel : <?php include_once('../external/HtmlPhpExcel/version.txt');?>'+'<br/>';
      aboutMessage+='&nbsp;&nbsp;.&nbsp;pChart2 : <?php include_once('../external/pChart2/getVersion.php');echo pChartGetVersion();?>'+'<br/>';
      aboutMessage+='&nbsp;&nbsp;.&nbsp;pdfMake : <?php include_once('../external/pdfmake/getVersion.php');echo pdfmakeGetVersion();?>'+'<br/>';
      aboutMessage+='&nbsp;&nbsp;.&nbsp;phpMailer : <?php $vers=file_get_contents('../external/PHPMailer/VERSION');echo $vers;?>'+'<br/>';
      aboutMessage+='&nbsp;&nbsp;.&nbsp;TinyButStrong :<?php include_once('../external/tbs/getVersion.php');echo tbsGetVersion();?>'+'<br/>';    
      aboutMessage+='&nbsp;&nbsp;&nbsp;CryptoJS 3.1.2 '+'<br/>';      
      aboutMessage+='&nbsp;&nbsp;&nbsp;phpAES '+'<br/>';
      aboutMessage+='&nbsp;&nbsp;&nbsp;XLSReader'+'<br/>';
      aboutMessage+='<br/>';
      // Relaunch Cron (if stopped, any connexion will restart it)
      adminCronRelaunch();
      if (dojo.isIE) {
        document.onhelp = function() { return (false); };
        window.onhelp = function() { return (false); };
      }
      var onKeyDownFunc = function(event) {
        if (event.keyCode == 83 && (navigator.platform.match("Mac") ? event.metaKey : event.ctrlKey) && ! event.altKey && event.target.id!="noteNoteStream") { // CTRL + S (save)
          event.preventDefault();
          if (dojo.isFF) stopDef();
          globalSave();
        } else if (event.keyCode == 112) { // F1 (show help)
          event.preventDefault();
          if (dojo.isFF) stopDef();
          showHelp();
        }else if(event.keyCode==27){ // ESCAPE (to exit full screen mode of CK Editor)
          if(editorInFullScreen() && whichFullScreen!=-1){
            editorArray[whichFullScreen].execCommand('maximize');
          }
          if(focusEditRowLine){
            if(currentRowToEdit && dojo.byId('objectIdRow') && dojo.byId('objectClassName') && dojo.byId('idProjectRow') ){
              var refId = dojo.byId('objectIdRow').value;
              var refType = dojo.byId('objectClassName').value;
              var idProject = dojo.byId('idProjectRow').value;
              JSGantt.closeAndSelectEditRow(currentRowToEdit, refId, refType, idProject);
            }else{
              JSGantt.closeEditRowObjectPlanning();
            }
          }
        }else if(event.keyCode==122){
          setTimeout("resizeAfterFullScreen();",150);
        }else if(event.keyCode==13){
          if(currentRowToEdit && !isEditRowFinishDisplay && focusEditRowLine){
            var refId = dojo.byId('objectIdRow').value;
            var refClass = dojo.byId('objectClassName').value;
            var idProject = dojo.byId('idProjectRow').value;
            if (refClass=='Replan' || refClass=='Construction' || refClass=='Fixed') refClass='Project';
            JSGantt.planningRowClickAction(currentRowToEdit, refId, refClass, idProject, false);
          }else if(currentRowToEdit && focusEditRowLine){
            inlineSave();
          }
        }else if((event.keyCode==38 || event.keyCode==40) && focusEditRowLine){
          switchEditRowLine(event);
        }else if(event.ctrlKey || event.shiftKey){
          multiSelectionInputPressed=true;
          if(event.keyCode != 16 && event.keyCode != 17){
            //Case for crtl+f
            //if crtl or shift down AND another key down (not again crtl(17) or shift(16)) don't multiSelectionInputPressed
            multiSelectionInputPressed=false;
          }
        }
        if (event.target.id=="noteNoteStream") {
          saveNoteStream(event);
        } if (event.target.id=="noteStreamKanban") {
          saveNoteStreamKanban(event);
        } if (event.target.id=="noteStreamVote") {
          saveNoteStreamVote(event);
        }
        if(event.target.id=="noteStreamBacklog"){
        	saveNoteStreamBacklog(event);
        }
      };
      var onKeyUpFunc = function(event) {
        if(!event.ctrlKey || !event.shiftKey){
          multiSelectionInputPressed=false;
        }
      };
      //if (dojo.isIE && dojo.isIE<=8) { // compatibility with IE8 removed in V6.0
      //  dojo.connect(document, "onkeypress", this, onKeyPressFunc);
      //} else {
        dojo.connect(document, "onkeydown", this, onKeyDownFunc);
        dojo.connect(document, "onkeyup", this, onKeyUpFunc);
      //} 
        var fullScr=function(evt){
          var fullscreenElement = document.fullscreenElement || document.mozFullScreenElement ||
          document.webkitFullscreenElement || document.msFullscreenElement;
          if(!fullscreenElement){
            setTimeout('cancelBothFullScreen();',10);
          }
          setTimeout("resizeAfterFullScreen();",150);
        };
        document.addEventListener("fullscreenchange",fullScr);
        document.addEventListener("webkitfullscreenchange",fullScr);
        document.addEventListener("mozfullscreenchange",fullScr);
        document.addEventListener("msfullscreenchange",fullScr);
 //remi -> Ctrl+Wheel for CkEditor, can't use when CkEditor is in full screen 
        //document.addEventListener("wheel", function(event){
        //  if(event.ctrlKey){
        //    if(displayFullScreenCKfield){
        //        // event.cancel();
        //      event.preventDefault();
        //    }
        //  }
        //});
      <?php 
      $firstPage="welcome.php";
      $firstPageDirectAccess=null;
      if (securityCheckDisplayMenu(1) ) {
      	$firstPage="today.php";
      }
      if (Parameter::getGlobalParameter('startPageLocked')=='YES') {
        $paramFirstPage=Parameter::getGlobalParameter('startPage');
      } else {
        $paramFirstPage=Parameter::getUserParameter('startPage');
      }
      if ($paramFirstPage) {
        $menuName=Menu::getMenuNameFromPage($paramFirstPage);
        if (securityCheckDisplayMenu(null,$menuName) or $paramFirstPage=='welcome.php' or $paramFirstPage=='startGuide.php') {
          $firstPage=$paramFirstPage;
        }
      }
      if (pq_array_key_exists("directAccessPage",$_REQUEST)) {
        $uniqueSessionId=getSessionValue('uniqueSessionId');
        if ($_REQUEST["directAccessPage"]=== "objectMain.php") {
            if (pq_array_key_exists("p1name", $_REQUEST)) {
                if ($_REQUEST['p1name']=='Resource' and RequestHandler::getValue('changeCurrentLocale')!="changeCurrentLocale") {
                    $class='Resource';
                    $id=$_REQUEST['p1value'];
                    $directObj=new $class($id);
                    $rights=$user->getAccessControlRights();
                    echo "dojo.byId('directAccessPage').value='';";
                    echo "dojo.byId('menuActualStatus').value='';";
                    echo 'gotoElement("' . $class . '","' . $id . '");';
                    $firstPage="";
                }else{
                  //gautier #3287
                  if(RequestHandler::getValue('changeCurrentLocale')=="changeCurrentLocale"){
                    $class=RequestHandler::getClass('p1name');
                    $id=RequestHandler::getId('p1value');
                    if ($id) {
                      $directObj=new $class($id);
                      $rights=$user->getAccessControlRights();
                      echo "dojo.byId('directAccessPage').value='';";
                      echo "dojo.byId('menuActualStatus').value='';";
                      echo "waitingForReply=false;";
                      $firstPageDirectAccess=$id;
                    }
                    $firstPage='objectMain.php?objectClass='.$class;
                  }
                }
            }
        } else {
// MTY - LEAVE SYSTEM          
        securityCheckRequest();
        $firstPage=$_REQUEST['directAccessPage'];     
        for ($i=1;$i<=9;$i++) {
          $pName='p'.$i.'name';
          $pValue='p'.$i.'value';
          if (pq_array_key_exists($pName,$_REQUEST) and pq_array_key_exists($pValue,$_REQUEST) ) {
            $firstPage.=($i==1)?'?':'&';
            $firstPage.=pq_htmlentities($_REQUEST[$pName])."=".pq_htmlentities($_REQUEST[$pValue]);
          } else {
            break;
          }
        }
        echo "dojo.byId('directAccessPage').value='';";
        echo "dojo.byId('menuActualStatus').value='';";
        }        
      } else if (RequestHandler::isCodeSet('directAccess') or (RequestHandler::isCodeSet('objectClass') and RequestHandler::isCodeSet('objectId')) ) {
        $class=RequestHandler::getValue('objectClass');
        if ($class and class_exists($class)) {
		      Security::checkValidClass($class);
		      $id=RequestHandler::getValue('objectId');
		      // PBER #10527 - Remove ... %E2%80%A6
		      $id=intval($id);
          Security::checkValidId($id);
          $directObj=new $class($id);
        } else {
          $directObj=null;
          $id=null;
          $class="Today";
        }
        $rights=$user->getAccessControlRights();
        //if ($class=='Ticket' and (securityGetAccessRightYesNo('menuTicket', 'read', $directObj)=='NO' or securityCheckDisplayMenu(null,'Ticket')==false ) )  {
        if ($class=='Ticket' and securityCheckDisplayMenu(null,'Ticket')==false and securityCheckDisplayMenu(null,'TicketSimple')==true)  {
          $class='TicketSimple';
        } else if ($class=='Ticket' and securityGetAccessRightYesNo('menuTicket', 'read', $directObj)=='NO' and securityGetAccessRightYesNo('menuTicketSimple', 'read', $directObj)=='YES') {
          $class='TicketSimple';
        } else if ($class=='TicketSimple' and securityGetAccessRightYesNo('menuTicket', 'read', $directObj)=='YES' and securityCheckDisplayMenu(null,'Ticket')==true) {
          $class='Ticket';
        }
        if (pq_array_key_exists('directAccess', $_REQUEST)) {
          $uniqueSessionId=getSessionValue('uniqueSessionId');
        	echo "noDisconnect=true;";
          // $index was already allocated earlier above, before session_write_close(), so the
          // whole page is rendered from the right slot. Note: like before, this particular
          // setSessionValue can't persist (session is already closed by now and can't be
          // reopened here - headers are already sent), but directAccessClass isn't read back
          // anywhere else, so this is harmless.
          setSessionValue('directAccessClass',$class);
        	echo "directAccessIndex=$index;";
        }
        if ($class=="Today") {
          //$firstPage="welcome.php";
          
        } else { 
          //echo 'var delay=(dojo.isFF)?1000:10;';
          echo 'var delay=1000;';
          echo 'setTimeout(\'gotoElement("' . $class . '","' . $id . '");\',delay);';
          $firstPage="";
        }
      }
      if(!isNewGui()){
        $hideMenu=false;
        if (Parameter::getUserParameter('hideMenu') and Parameter::getUserParameter('hideMenu')!='NO' and ! getSessionValue('showModule')){
          echo 'hideShowMenu(true,true);';
          $hideMenu=true;
        }
      }
      echo "menuDivSize='".getContentPaneSize('contentPaneLeftDivWidth')."';";
      // Module
      if (getSessionValue('showModule')) {
        setSessionValue('showModule', $firstPage); 
        $firstPage=null;
      } else if ($firstPage) {
      ?>
      <?php 
      if ($firstPage) {
        $root=explode('.php',$firstPage)[0];
        if (pq_substr($root,-4)=='Main') $root=pq_substr($root,0,-4);
        if ($root!='object') {
          $root=pq_ucfirst($root);
          echo "stockHistory('$root',null,'$root');";
        } else {
          $class=explode('objectClass=',$firstPage)[1];
          echo "stockHistory('$class',null,'$root');";
        }
      }
      ?>
      <?php 
      if ($firstPage=='planningMain.php' or $firstPage=='portfolioPlanningMain.php' or $firstPage=='resourcePlanningMain.php') echo 'coverListAction="CLOSE";';
      ?>
      setTimeout('loadContent("<?php echo $firstPage;?>","centerDiv",null,null,null,<?php echo ($firstPageDirectAccess)?intval($firstPageDirectAccess):'null';?>);',200);
      <?php 
      }
      ?>
      dojo.byId("loadingDiv").style.visibility="hidden";
      dojo.byId("loadingDiv").style.display="none";
      dojo.byId("mainDiv").style.visibility="visible"; 
      setTimeout('checkAlert();',5000); //first check at 5 seco 

// MTY - LEAVE SYSTEM
      <?php
        if (isLeavesSystemActiv() and (getSessionUser()->isEmployee or isLeavesAdmin(getSessionUser()->id))) {
          $audit=new Audit();
          $cpt=$audit->countSqlElementsFromCriteria(array('idUser'=>getSessionUser()->id, 'auditDay'=>date('Ymd')));
          if ($cpt<=1) { // Massive check only for first connection of day
      ?>
            checkLeavesEarned(<?php echo getSessionUser()->id?>);
      <?php
          }
        }
      ?>
// MTY - LEAVE SYSTEM
      <?php if ($firstPage=="welcome.php") {?>
          //setTimeout("runWelcomeAnimation();",2000);
      <?php } ?>
      <?php // check for ongoing work on Ticket 
      if (getSessionUser()->id) {
	      $crit=array('ongoing'=>'1','idUser'=>getSessionUser()->id);
	      $we=SqlElement::getSingleSqlElementFromCriteria('WorkElement', $crit);
	      if ($we and $we->id) {
	      	$start=$we->ongoingStartDateTime;
	      	//echo "startStopWork('start', '$we->refType', $we->refRefId, $start);";
	      }
      }
      ?>
      showHideMoveButtons();
      <?php  $lastHighLight = SqlElement::getSingleSqlElementFromCriteria('Highlight', array('idUser'=>$user->id,'scope'=>'news'));
              $refLastHighLight = $lastHighLight->reference;
              if(!$refLastHighLight)$refLastHighLight=1;?>
      getLastNews(<?php echo  $refLastHighLight;?>);
    }); // End of dojo.addOnload 
    var canAccessPlanning='<?php echo securityCheckDisplayMenu(null, 'Planning', null); ?>';
    var noRefreshAfterSave = false;
    var ganttPlanningScale="<?php echo Parameter::getUserParameter('planningScale');?>";
    if (! ganttPlanningScale) ganttPlanningScale='day';
    var ganttPlanningZoom="<?php $planningZoomMain=Parameter::getUserParameter('planningZoom'); echo (($planningZoomMain=='75' or $planningZoomMain=='125')?$planningZoomMain:'100');?>";
    var cronSleepTime=<?php echo Cron::getSleepTime();?>;
    var canCreateArray=new Array();
    var dependableArray=new Array();
    var linkableArray=new Array();
    var originableArray=new Array();
    var copyableArray=new Array();
    var indicatorableArray=new Array();
    var mailableArray=new Array();
    var textableArray=new Array();
    var situationableArray=new Array();
    var checklistableArray=new Array();
    var planningColumnOrder=new Array();
    var contentPaneResized = new Array();
    var planningModeCode = new Array();
    <?php
      echo "\n";
      $list=SqlList::getListNotTranslated('Dependable');
      foreach ($list as $id=>$name) {
      	$right=securityGetAccessRightYesNo('menu' . $name,'create');
      	echo "canCreateArray['" . $name . "']='" . $right . "';";
      	echo "dependableArray['" . $id . "']='" . $name . "';";
      }
      echo "\n";
      $list=SqlList::getListNotTranslated('Linkable');
      foreach ($list as $id=>$name) {
        $right=securityGetAccessRightYesNo('menu' . $name,'create');
        echo "canCreateArray['" . $name . "']='" . $right . "';";
        echo "linkableArray['" . $id . "']='" . $name . "';";
      }
      echo "\n";
      $list=SqlList::getListNotTranslated('Originable');
      foreach ($list as $id=>$name) {
        $right=securityGetAccessRightYesNo('menu' . $name,'create');
        echo "canCreateArray['" . $name . "']='" . $right . "';";
        echo "originableArray['" . $id . "']='" . $name . "';";
      }
      echo "\n";
      $list=SqlList::getListNotTranslated('Copyable');
      foreach ($list as $id=>$name) {
        echo "copyableArray['" . $id . "']='" . $name . "';";
      }
      echo "\n";
      $list=SqlList::getListNotTranslated('Indicatorable');
      foreach ($list as $id=>$name) {
        echo "indicatorableArray['" . $id . "']='" . $name . "';";
      }
      echo "\n";
      $list=SqlList::getListNotTranslated('Mailable');
      foreach ($list as $id=>$name) {
        echo "mailableArray['" . $id . "']='" . $name . "';";
      }
      echo "\n";
      $list=SqlList::getListNotTranslated('Textable');
      foreach ($list as $id=>$name) {
        echo "textableArray['" . $id . "']='" . $name . "';";
      }
      echo "\n";
      $list=SqlList::getListNotTranslated('Checklistable');
      foreach ($list as $id=>$name) {
      	echo "checklistableArray['" . $id . "']='" . $name . "';";
      }
      echo "\n";
      $list=SqlList::getListNotTranslated('Situationable');
      foreach ($list as $id=>$name) {
      	echo "situationableArray['" . $id . "']='" . $name . "';";
      }
      echo "\n";
      $list=SqlList::getListNotTranslated('PlanningMode','code',null,true);
      foreach ($list as $id=>$code) {
        echo "planningModeCode['" . $id . "']='" . $code . "';";
      }
      echo "\n";
      // Retrieve order and visibility info for Planning Columns
      $planningTypeList = array('contract','global','planning','portfolio','resource','version','workPlan');
      //$planningTypeList = array('planning');
      foreach ($planningTypeList as $planningType){
        echo "idx=getIndiceForPlanningType('".$planningType."');";
        if($planningType == 'portfolio'){
          $list=Parameter::getPlanningColumnDescription($planningType);
          $proj = new Project();
          foreach ($list as $name=>$desc) {
            if(!isset($desc['name']))continue;
            $type = $proj->getDataType($name);
            $length = $proj->getDataLength($name);
            if($name == 'Color')$type='color';
            if($type == 'int' and $length == 1)$type='boolean';
            $show = $desc['show'];
            $width = $desc['width'];
            $minWidth = $desc['minWidth'];
            $order = $desc['order'];
            $custom='false';
            $customName=null;
            if(property_exists('Project','_customFields')){
              $colName = pq_strtolower(pq_substr($name, 0, 1)).pq_substr($name, 1);
              if(in_array($colName, Project::$_customFields)){
                $custom='true';
                $customName = $proj->getColCaption($colName);
              }
            }
            echo "if(!planningFieldsDescription[idx].find(({ name }) => name === '$name')){";
            echo '  planningFieldsDescription[idx].push({name:"'.$name.'", show:'.$show.', order:'.$order.',  width:'.$width.', minWidth:'.$minWidth.', showSpecif:1, type:"'.$type.'", inputType:null,rawValue:new Array(), showValue:new Array(), editable:false, custom:'.$custom.', customName:"'.$customName.'"});';
            echo "}";
          }
        }else if($planningType == 'planning'){
          $list=Parameter::getPlanningColumnDescription($planningType);
          $act = new Activity();
          foreach ($list as $name=>$desc) {
            if(!isset($desc['name']))continue;
            $type = $act->getDataType($name);
            $length = $act->getDataLength($name);
            if($name == 'Color')$type='color';
            if($type == 'int' and $length == 1)$type='boolean';
            $show = $desc['show'];
            $width = $desc['width'];
            $minWidth = $desc['minWidth'];
            $order = $desc['order'];
            $custom='false';
            $customName=null;
            if(property_exists('Activity','_customFields')){
              $colName = pq_strtolower(pq_substr($name, 0, 1)).pq_substr($name, 1);
              if(in_array($colName, Activity::$_customFields)){
                $custom='true';
                $customName = $act->getColCaption($colName);
              }
            }
            echo "if(!planningFieldsDescription[idx].find(({ name }) => name === '$name')){";
            echo '  planningFieldsDescription[idx].push({name:"'.$name.'", show:'.$show.', order:'.$order.',  width:'.$width.', minWidth:'.$minWidth.', showSpecif:1, type:"'.$type.'", inputType:null,rawValue:new Array(), showValue:new Array(), editable:false, custom:'.$custom.', customName:"'.$customName.'"});';
            echo "}";
          }
        }
        
        $list=Parameter::getPlanningColumnDescription($planningType);
        foreach ($list as $name=>$desc) {
          if(!isset($desc['name']))continue;
          echo "setPlanningFieldShow('$name',".(($desc['show'])?'true':'false').",'$planningType');";
          if (isset($desc['width'])) echo "setPlanningFieldWidth('$name',".$desc['width'].",'$planningType');";
          else echo "setPlanningFieldWidth('$name',80,'$planningType');";
          if (isset($desc['minWidth'])) echo "setPlanningFieldMinWidth('$name',".$desc['minWidth'].",'$planningType');";
        }
        
        echo "planningColumnOrder[idx]=new Array();";
        $list=Parameter::getPlanningColumnOrder($planningType);
        foreach ($list as $order=>$name) {
          echo "planningColumnOrder[idx][" . ($order) . "]='" . $name . "';";
          echo "setPlanningFieldOrder('$name',$order,'$planningType');";
        } 
      }
      echo "\n";
      foreach (array('directory','document') as $explorerType) {
        echo "idx=getIndiceForPlanningType('".$explorerType."');";
        $list=Parameter::getDocumentExplorerColumnDescription($explorerType);
        foreach ($list as $name=>$desc) {
          if (! isset($desc['name'])) continue;
          echo "setPlanningFieldShow('$name',".(($desc['show'])?'true':'false').",'$explorerType');";
          echo "setPlanningFieldWidth('$name',".$desc['width'].",'$explorerType');";
          echo "setPlanningFieldMinWidth('$name',".$desc['minWidth'].",'$explorerType');";
          if (isset($desc['label']) and $desc['label']!=='') {
            echo "documentExplorerSetFieldLabel('$name',".json_encode($desc['label']).",'$explorerType');";
          }
        }
        echo "documentExplorerColumnOrder[idx]=new Array();";
        $list=Parameter::getDocumentExplorerColumnOrder($explorerType);
        foreach ($list as $order=>$name) {
          echo "documentExplorerColumnOrder[idx][".$order."]='".$name."';";
          echo "setPlanningFieldOrder('$name',$order,'$explorerType');";
        }
      }
      echo "\n";
      $param = new Parameter();
      $user = getSessionUser();
      $where = "parameterCode Like '%contentPane%' and idUser=$user->id";
      $contentPaneParamList = $param->getSqlElementsFromCriteria(null,null,$where);
      foreach ($contentPaneParamList as $contentPane){
        echo "contentPaneResized['".$contentPane->parameterCode."']=".$contentPane->parameterValue.";";
      }
      echo "\n";
      // Retrieve translation files for each installed plugin
      Plugin::getTranslationJsArrayForPlugins('i18nPluginArray');
      ?>
      window.onfocus= function(){
        // PBER : when D&D comes from other screen, onFocus is triggered on drop, before setting file name
        //        this auto-closes pop-up unexpectedly
        //        But the closure must be preserved if Drop was done onut of the Drop area : so delayed the test to wait the drop to happen
        var funcOnFocus=function() {
          if(dropFilesDocument && dijit.byId('dialogDocumentVersion').open){
            dojo.byId('dropFilesDocInfoDiv').style.opacity='0%';
            dojo.byId('dropFilesDocInfoDiv').style.display='none';
            dijit.byId('dialogDocumentVersion').hide();
            dropFilesDocument=false;
          }
        };
        setTimeout(funcOnFocus,100);
      }
// PBER : Fix D&D from outlook
//        The window.onmouseover was placed to hide dialog box when item is droped out of browser page, as soon as mouve is moved over it again
//        This set the mess with D&D from outlook (and not from other, don't knwo why
//        The onfocus above is enough to get the correct behavior as dialog will be hoden as soon as page gets the focus back (click into it)
//       window.onmouseover= function(e){ 
//         if( dropFilesDocument && dijit.byId('dialogDocumentVersion').open){
//           dojo.byId('dropFilesDocInfoDiv').style.opacity='0%';
//           dojo.byId('dropFilesDocInfoDiv').style.display='none';
//           dijit.byId('dialogDocumentVersion').hide();
//           dropFilesDocument=false;
//         }
//       }
    //window.onbeforeunload = function (evt){ return beforequit();};
  </script>
</head>
    <?php
    if (getSessionValue('passwordChangeInProgress')=='true') {
      setSessionValue('uniqueSessionId',$uniqueSessionId);
    }
    unsetSessionValue('passwordChangeInProgress');
    $currentUniqueSessionId=pq_trim(getSessionValue('uniqueSessionId'));
    if ($currentUniqueSessionId and $currentUniqueSessionId!=$uniqueSessionId and ! isset($simuIndex)) {
      // 
      echo "<body id='body' class='nonMobile tundra ".getTheme()."' onload=\"window.location='main.php?directAccess=true';\">";
      debugTraceLog("Double connection on same browser for user #".getSessionUser()->id);
      include_once '../view/welcome.php';
      echo "<div style='display:none;position:absolute;top:40%;width:100%;text-align:center;color:var(--color-detail-header-text);font-size:18pt;font-weight:bold'>".i18n("connectionAlreadyExists")."</div>";
      $style="border-radius: 5px;background: #f0eff5;color: #4d4d80;";
      echo "<div id='buttonReconnectContainer' class='nonMobile tundra ".getTheme()."' align='center' style='display:none;position:absolute;top:56%;width:100%;left:-10px;'><button dojoType='dijit.form.Button' class='dynamicTextButton' style='' onClick='var callBack=function() {window.location = \"../index.php\";};saveDataToSession(\"disconnect\", null, null, callBack);'>".i18n("EnforceConnection")."</button></div>";
      //echo "<div onDblClick='var callBack=function() {window.location = \"../index.php\";};saveDataToSession(\"disconnect\", null, null, callBack);' style='position:absolute;top:0;left:0;width:100%;height:100%;background:transparent'></div>";
      echo "</body>";
      echo "</html>";
      exit;
    }    
    if ($uniqueSessionId) {
      setSessionValue('uniqueSessionId',$uniqueSessionId);
    }
    ?>
<body id="body" class="nonMobile tundra <?php echo getTheme();?>" <?php if(isNewGui()) echo 'style="background-color:'.$background.';"'; ?> onBeforeUnload="return beforequit();" onUnload="quit();" >
<div id="centerThumb80" style="display:none;z-index:999999;position:absolute;top:10px;left:10px;height:80px;width:80px;"></div>
<div id="loadingDiv" class="<?php echo getTheme();  echo (isNewGui())?'loginFrameNewGui':'loginFrame' ;?>" 
 style="position:absolute; visibility: visible; display:block; width:100%; height:100%; margin:0; padding:0; border:0">
   <?php if (!isFF() and isNewGui()) echo '<div style="position:absolute;margin-top:-50%;margin-left:-0%;width:250%;height:250%;opacity:0.1 !important;z-index:-2;" class="loginBackgroundNewGui"></div>';?>
   <?php if (isFF() and isNewGui()) echo '<div style="position:absolute;margin-top:-40%;margin-left:-10%;width:250%;height:250%;z-index:-2;"><img style="width:100%;height:100%;opacity:0.1 !important" src="css/images/Engrenages.svg" /></div>';?>
   <?php if (isNewGui()) echo '<div style="position:absolute;width:100%;height:100%;opacity:0.6 !important;z-index:-1;" class="loginBackgroundNewGui"></div>';?>
   <table align="center" width="100%" height="100%" class="<?php echo (isNewGui())?'':'loginBackground';?>">
    <tr height="100%">
      <td width="100%" align="center">
        <div class="background  <?php  echo (isNewGui())?'loginFrameNewGui':'loginFrame' ;?>" <?php echo (isNewGui())?'style="background-color:white;"':'';?>>
        <table align="center" >
		    <?php if(isNewGui()){?>
			    <tr style="height:42px;" >
			     <td align="center" style="position:relative;height: 1%;" valign="center">
			       <div style="position:relative;height:75px;">
			         <div class="divLoginIconDrawing" style="position:absolute;background-color:#<?php echo $firstColor;?>";>
			           	<div class="divLoginIconBig"></div>		         
			         </div>
			       </div>
			     </td>
			    </tr>
	    <?php }?>
          <tr style="height:10px;">
            <td align="left" style="position:relative;height: 100%;" valign="top">
              <div style="position:relative; width: 400px; height: 54px;">
    	          <div style="overflow:visible;position:absolute;width: 480px; height: 250px;top:15px;text-align: center">
    	           <div id="waitLogin" style="position:absolute;top:50%"></div>  
	    		        <img style="max-height:60px" src="<?php 
	    		          if (file_exists("../logo.gif")) echo '../logo.gif';
	    		          else if (file_exists("../logo.jpg")) echo '../logo.jpg';
	    		          else if (file_exists("../logo.png")) echo '../logo.png';
	    		          else echo 'img/titleSmall.png';?>" />
    	          </div>
  	            <div style="width: 470px; height:130px;position:absolute;top:160px;overflow:hidden;text-align:center;">
                  Loading ...    
                </div>
              </div>
            </td>
          </tr>
          <tr style="height:100%" height="100%">
            <td style="height:99%" align="left" valign="middle">
              <div  id="" style="width: 470px; height:210px;overflow:hidden">
              </div>
            </td>
          </tr>
        </table>
        </div>
      </td>
    </tr>
  </table>
</div>
<div id="mainDiv" style="visibility: hidden;" class="mainDiv">
  <div id="wait" >
  	<div id="waitMessage" class="waitMessage"></div>
  </div>
  <div id="errorPopup" data-dojo-type="dijit.Dialog" title=<?php echo pq_strtoupper(i18n("ERROR")) ?>></div>
  <div dojoType="dijit.layout.ContentPane" id="resultPopup" style ="pointer-events: none;vertical-align:middle;min-height:20px;max-height:500px;height:auto" onclick="dojo.byId('resultPopup').style.display='none';dojo.byId('resultPopup').style.pointerEvents='none';"></div>
  <div id="temporaryMessage" style="display:none;z-index:999;text-align:center;position:fixed;width:500px;left:50%;top:10px;margin-left:-250px">
    <div id="temporaryMessageText" style="text-align:center;cursor:pointer;" onClick="dojo.byId('temporaryMessage').style.display='none';"></div>
  </div>
  <div id="detailRightDivAlt" style="display:none"></div>
  <div dojoType="dijit/ProgressBar" id="downloadProgress" data-dojo-props="maximum:1">
  </div>
  <?php
  // Module
  if (getSessionValue('showModule')) {
    $showModuleScreen=true;
    include "../view/moduleView.php";
  }
  ?>
  	<?php   
  //Gautier RGPD
  $crit = array ('idUser'=>$user->id,'accepted'=>'0');
  $listMessageLegalFollowup=SqlList::getListWithCrit ('MessageLegalFollowup',$crit,'idMessageLegal');
  if($listMessageLegalFollowup){
    $cptMess = 0;
    foreach ($listMessageLegalFollowup as $idFollowup=>$idMessage){
      $messLegal = new MessageLegal($idMessage);
      $where="idle=0";
      $arrayWhere = array();
      if($messLegal->idAffectable){
        array_push($arrayWhere, "idAffectable='".Sql::fmtId($user->id)."'");
      }else{
        array_push($arrayWhere, "idAffectable is null");
      }
      if($messLegal->idProfile){
        array_push($arrayWhere, "idProfile = '".$user->idProfile."'");
      }else{
        array_push($arrayWhere, "idProfile is null");
      }
      if($messLegal->idProject){
        $projectList = array_flip($user->getAffectedProjects());
        array_push($arrayWhere, "idProject in (".implode(',', $projectList).")");
      }else{
          array_push($arrayWhere, "idProject is null");
      }
      if($messLegal->idTeam){
        array_push($arrayWhere, "idTeam = '". $user->idTeam ."'");
      }else{
        array_push($arrayWhere, "idTeam is null");
      }
      if($messLegal->idOrganization){
      	array_push($arrayWhere, "idOrganization = '".$user->idOrganization."'");
      }else{
        array_push($arrayWhere, "idOrganization is null");
      }
      if(count($arrayWhere)>0){
        $where .= ' and (';
        $arrayWhere = implode(' and ', $arrayWhere);
        $where .= $arrayWhere;
        $where.=" )";
      }
      $listMsg=$messLegal->getSqlElementsFromCriteria(null, false, $where);
      if($listMsg){
        foreach ($listMsg as $msgL){
        	$listMsgFlat[$msgL->id]=$msgL->id;
        }
        if(!in_array($idMessage, $listMsgFlat)){
          unset($listMessageLegalFollowup[$idFollowup]);
        }
      }else{
        unset($listMessageLegalFollowup[$idFollowup]);
      }
      if((date('Y-m-d H:i:s') > $messLegal->endDate AND $messLegal->endDate )  OR (date('Y-m-d H:i:s') < $messLegal->startDate AND $messLegal->startDate ) OR $messLegal->idle){
        unset($listMessageLegalFollowup[$idFollowup]);
      }
    }
    $nbListMess = count($listMessageLegalFollowup);
   }
   if($listMessageLegalFollowup){
    ?>
  <div id="dialogMessageLegal" style="width:100%; visibility:visible; display:inline-block;height:30%;"> 
    <div id="messageLegallArrow" style="display:block; float:right; margin-top:15px; width:5%; height:100%; margin-top:5px;">
      <div class="iconArrowMessageLegal" ><span style="color:white; width:18px; height:90%;writing-mode:vertical-rl;"><?php echo i18n("readToHide");?></span></div>
    </div>
     <?php 
     Sql::beginTransaction();
     foreach ($listMessageLegalFollowup as $idFollowup=>$idMessage){
       $messFollow = new MessageLegalFollowup($idFollowup);
       $messLegal = new MessageLegal($idMessage);
       $cptMess++;
       if(!$messFollow->firstViewDate){
         $messFollow->firstViewDate = date('Y-m-d H:i:s');
       }
       $messFollow->lastViewDate = date('Y-m-d H:i:s');
       $messFollow->save();
       $val=$messLegal->description; 
       ?>
    <div id="messageLegall<?php echo $messFollow->id;?>" style="display:<?php echo ($cptMess < $nbListMess)?'none':'block';?>;  width:95%; height:100%; overflow-y:auto;"> 
      <div id="messageLegal<?php echo $messFollow->id;?>" style="font-size:12pt; margin-top:15px; min-height:200px; margin:15px 40px 5px 40px;">  
         <?php echo $val;?>
      </div>
      <div style="width:97%;  bottom:5px; text-align:right;">
       <?php if($cptMess != 1){?>
         <span style="font-size:12pt;cursor:pointer; text-decoration:underline;" id="plusTard<?php echo $messFollow->id;?>" onclick="dojo.byId('messageLegall<?php echo $oldValue;?>').style.display='block';dojo.byId('messageLegall<?php echo $messFollow->id;?>').style.display='none'";>
       <?php }else{?>   
         <span style="font-size:12pt;cursor:pointer; text-decoration:underline;" id="buttonLater<?php echo $messFollow->id;?>" onclick="dojo.byId('dialogMessageLegal').style.visibility='hidden'";>
       <?php } 
       echo i18n("buttonLater");?></span>
       &nbsp;&nbsp;&nbsp;
       <?php 
       if($messLegal->name != 'newGui'){
         if($cptMess != 1){?>
      	 <button style="font-size:12pt;position:relative;top:-5px;" dojoType="dijit.form.Button" id="markOK<?php echo $messFollow->id;?>" onclick="setReadMessageLegalFollowup(<?php echo $messFollow->id;?>);dojo.byId('messageLegall<?php echo $oldValue;?>').style.display='block';dojo.byId('messageLegall<?php echo $messFollow->id;?>').style.display='none'";>
         <?php }else{?>
         <button style="font-size:12pt;position:relative;top:-5px;" dojoType="dijit.form.Button" id="markOK<?php echo $messFollow->id;?>" onclick="setReadMessageLegalFollowup(<?php echo $messFollow->id;?>);dojo.byId('dialogMessageLegal').style.visibility='hidden'";>
         <?php } 
         echo i18n("buttonAgree");?>
         </button>
       <?php } else {?>
         <button style="font-size:12pt;position:relative;top:-5px;" dojoType="dijit.form.Button" id="activateNewgui<?php echo $messFollow->id;?>" onclick="setNewGui(<?php echo $messFollow->id;?>, 1);dojo.byId('dialogMessageLegal').style.visibility='hidden'";>
           <?php echo i18n("cronExecutionActivate");?>
         </button>
         <button style="font-size:12pt;position:relative;top:-5px;" dojoType="dijit.form.Button" id="desactiveNewgui<?php echo $messFollow->id;?>" onclick="setNewGui(<?php echo $messFollow->id;?>, 0);dojo.byId('dialogMessageLegal').style.visibility='hidden'";>
           <?php echo i18n("cronExecutionDesactivate");?>
         </button>
       <?php }?>
      </div>  
    </div>
     <?php 
       $oldValue = $messFollow->id;
     }
     Sql::commitTransaction(); ?>
  </div>
   <?php  } ?>
 
  <?php 
  if(!isNewGui()){
     $leftWidth=getContentPaneSize('contentPaneLeftDivWidth');
     $leftWidth=($leftWidth and $leftWidth>35)?$leftWidth.'px':'20%';
     if ($hideMenu){
       $leftWidth="32px";
     }
     
     //$IconSizeMenuHide = 16;
    $IconSizeMenuHide=Parameter::getUserParameter('paramIconSize');
    if (!$IconSizeMenuHide) $IconSizeMenuHide=22;
    $IconSizeMenuHide2 = $IconSizeMenuHide+5;
   ?>
  <div id="menuBarShow" class="dijitAccordionTitle2 reportTableColumnHeader2 largeReportHeader2"  style="position:absolute;left:0px; top:81px; bottom:0px; width:<?php echo $IconSizeMenuHide2;?>px;">
    <?php include "menuHideMenu.php"; ?> 
    <div id="hideMenuBarShowButton" style="cursor:pointer;position:absolute; right:-22px; bottom:2px;z-index:949;display:<?php echo (isset($showModuleScreen))?"none":"block";?>;">
		  <a onClick="hideMenuBarShowMode();" id="buttonSwitchedMenuBarShow" title="" >
		    <span style='top:0px;display:inline-block;width:22px;height:22px;'>
		      <div class='iconHideStream22 iconHideStream iconSize22' style='' >&nbsp;</div>
		    </span>
		  </a>
		</div>
  </div> 
  
  <div id="hideMenuBarShowButton2" style="cursor:pointer;position:absolute;display:<?php echo (isset($showModuleScreen))?"none":"block";?>;left:<?php echo $IconSizeMenuHide2 ?>; bottom:2px;z-index:949">
	<?php if (! isset($showModuleScreen)) {?>
	  <a onClick="hideMenuBarShowMode();" id="buttonSwitchedMenuBarShow" title="" >
	    <span style='top:0px;display:inline-block;width:22px;height:22px;'>
	      <div class='iconHideStream22 iconHideStream iconSize22' style='' >&nbsp;</div>
	    </span>
	  </a>
	<?php }?>  
	</div>
<?php }?>
  <div id="globalContainer" class="container" dojoType="dijit.layout.BorderContainer" liveSplitters="false"> 
    <?php 
    //$iconSize=Parameter::getUserParameter('paramTopIconSize');
    //$showMenuBar=Parameter::getUserParameter('paramShowMenuBar');
    //$showMenuBar='NO';
    $iconSize=(isNewGui())?22:32;
    $showMenuBar='YES';
    //if (! $iconSize or $showMenuBar=='NO') $iconSize=16;
    $iconSize+=9;?>
    
    <div id="toolBarDiv" style="height:30px" dojoType="dijit.layout.ContentPane" region="top"  >
      <?php include "menuBar.php";?>
    </div>
<?php if(isNewGui()){
      $isMenuLeftOpen=Parameter::getUserParameter('isMenuLeftOpen');
      if($isMenuLeftOpen=='' or $isMenuLeftOpen==null) $isMenuLeftOpen='true';
      $pinMode=Parameter::getUserParameter('pinMode');
      if ($pinMode=='' or $pinMode==null) $pinMode='false';
      if ($pinMode=='true') {
        $isMenuLeftOpen='false';
        Parameter::storeUserParameter('isMenuLeftOpen', 'false');
      }
      ?>
    <div id="menuTop" class="menuTop">
      <div id="globalTopCenterDiv" class="container" region="center" dojoType="dijit.layout.BorderContainer" liveSplitters="false">
        <input id="selectedScreen" value="" hidden >
        <input id="isMenuLeftOpen" value="<?php echo $isMenuLeftOpen?>" hidden >
        <div id="right-pane" class="right-pane">
<?php } if (!isNewGui()) {?>
     <div id="statusBarDiv" dojoType="dijit.layout.ContentPane" region="top" style="height:48px;position:absolute; top:30px;">
      <table width="100%"><tr>
      
       <td width="220px" id="menuBarLeft" >
      
        <div style="overflow:hidden;position: absolute; left:2px; top: 8px;width:205px; background: transparent; color: #FFFFFF !important; border:<?php echo (isNewGui())?'0':'1';?>px solid #FFF;vertical-align:middle;" 
        onChange="menuFilter(this.value);" id="menuSelector" id="menuSelector"
        onMouseEnter="showMenuList();" onMouseLeave="hideMenuList(300);"
        dojoType="dijit.form.Select" class="input filterField rounded menuSelect" 
        ><?php foreach ($allMenuClass as $cl=>$clVal) {
          $selected=($defaultMenu==$cl)?' selected=selected ':'';
          echo '<option value="'.$cl.'" '.$selected.' style="color:#fff !important;">';
          echo '<div style="z-index:9999;height:25px;vertical-align:middle;top:2px;width:190px;" value="'.$cl.'" '.$selected.' class="menuSelectList" onMouseOver="clearTimeout(closeMenuListTimeout);" onMouseLeave="hideMenuList(200,\''.$cl.'\');">';
          echo '  <div style="z-index:9;position:absolute;height:23px;width:25px;left:1px;background-color:#ffffff;border-radius:5px;opacity: 0.5;">&nbsp;</div>';
          echo '  <span style="z-index:10;position:absolute;height:22px;left:2px;" class="icon'.pq_ucfirst($cl).'22 icon'.pq_ucfirst($cl).' iconSize22">&nbsp;</span>';
          echo '  <span style="z-index:11;position:absolute;left:30px;top:9px;">'. i18n('menu'.pq_ucfirst($clVal)).'</span>';
          echo '</div>';
          echo '</option>';
      }?></div>
      
      <?php if ($showMenuBar!='NO') {?>    
      
        <button id="menuBarMoveLeft" dojoType="dijit.form.Button" showlabel="false"
         title="<?php echo i18n('menuBarMoveLeft');?>" class="buttonMove"
         iconClass="leftBarIcon" style="position:relative; left:232px; width: 14px;top:-2px;height:48px;margin:0;vertical-align:middle">
           <script type="dojo/method" event="onMouseDown">         
           menuBarMove=true;
           moveMenuBar('left');
         </script>
           <script type="dojo/method" event="onMouseUp">
           moveMenuBarStop();
         </script>
           <script type="dojo/method" event="onClick">
           moveMenuBarStop();
         </script>
        </button>    
      </td>
     
     <td width="85%">       
          <div id="menuBarVisibleDiv" style="height:<?php echo $iconSize+9;?>px;width:<?php echo ($cptAllMenu*56);?>px; position: absolute; top: 0px; left:248px; z-index:0">
          <div style="width: 100%; height:48px; position: absolute; left: 0px; top:1px; overflow:hidden; z-index:0">
    	    <div name="menubarContainer" id="menubarContainer" style="width:<?php echo ($cptAllMenu*56);?>px; position: relative; left:0px; overflow:hidden;z-index:0">
    	      <table><tr>
    	       <?php drawAllMenus($menuList);?>
    	     </tr></table>
    	    </div>
          </div>
          </div>
      </td>
<?php } else {?>
    <td style="width:80%"><div id="menuBarVisibleDiv"></div></td>
<?php }?>
    <td width="25px" align="center" id="menuBarRight" class="statusBar" style="right:0;position:absolute;z-index:30;">
      <table><tr><td rowspan="2">
<?php if ($showMenuBar!='NO') {?>   
           <button id="menuBarMoveRight" dojoType="dijit.form.Button" showlabel="false"
         title="<?php echo i18n('menuBarMoveRight');?>" class="buttonMove"
         iconClass="rightBarIcon" style="position:relative; left:-3px; top:-2px;width: 14px;height:48px;margin:0;vertical-align:middle">
             <script type="dojo/method" event="onMouseDown">         
           menuBarMove=true;
           moveMenuBar('right');
         </script>
             <script type="dojo/method" event="onMouseUp">
           moveMenuBarStop();

         </script>
             <script type="dojo/method" event="onClick">
           moveMenuBarStop();
         </script>
          </button>
          <?php }?>
      </td><tr>
      </table>
    </td></tr>
    </table>
    </div>
    <?php 
          $hideMenuLeftParam = Parameter::getGlobalParameter ( 'MenuBarLeft' ); 
      if (sessionValueExists('MenuBarLeft') and getSessionValue('MenuBarLeft')=='false'){
          $hideMenuLeftParam = 'true';
      }
        if($hideMenuLeftParam == 'false' and ! isset($showModuleScreen)) { ?>
        <script type="text/javascript">
           hideShowMenu(true);
        </script>
     <?php } ?>
    <?php }else{
      include 'menuNewGuiTop.php'; 
      $nbFavoriteRow = 5;
      ?>
      <div dojoType="dijit.layout.ContentPane" id="anotherBarContainer" name="anotherBarContainer" region="center" style="width: 100%;z-index: 999;top:46px;background-color: rgb(181 181 181 / 50%);display:none"
      onClick="dojo.byId('anotherBarContainer').style.display = 'none';dojo.byId('isEditFavorite').value = 'false';">
        <table style="width:100%;"><tr>
          <td id="hideMenuLeftMargin" style="width:37px;<?php echo ($isMenuLeftOpen=='false')?'display:block;':'display:none;'?>"></td>
          <td style="width:120px;">
            <div style="margin: 5px 5px 5px 5px;height: 43px;width: auto;border: 1px solid var(--color-dark);border-radius: 5px;background: white;overflow:hidden;">
            <?php $menuBarTopMode = Parameter::getUserParameter('menuBarTopMode');?>
              <table style="width:100%;height:100%;">
                     <tr>
                       <td class="<?php if($menuBarTopMode=='ICON'){echo 'imageColorNewGuiSelected';}else{ echo 'imageColorNewGui';}?>" style="padding-left:8px;" onclick="saveUserParameter('menuBarTopMode', 'ICON');menuNewGuiFilter('menuBarCustom', null);" title="<?php echo i18n('setToIcon');?>"><?php echo formatNewGuiButton('FavorisIcon', 22, true);?></td>
                       <td class="<?php if($menuBarTopMode=='ICONTXT'){echo 'imageColorNewGuiSelected';}else{ echo 'imageColorNewGui';}?>" onclick="saveUserParameter('menuBarTopMode', 'ICONTXT');menuNewGuiFilter('menuBarCustom', null);" title="<?php echo i18n('setToIconTxt');?>"><?php echo formatNewGuiButton('FavorisIconTxt', 22, true);?></td>
                       <td class="<?php if($menuBarTopMode=='TXT'){echo 'imageColorNewGuiSelected';}else{ echo 'imageColorNewGui';}?>" onclick="saveUserParameter('menuBarTopMode', 'TXT');menuNewGuiFilter('menuBarCustom', null);" title="<?php echo i18n('setToTxt');?>"><?php echo formatNewGuiButton('FavorisTxt', 22, true);?></td>
                     </tr>
              </table>
            </div>
            <div title="<?php echo i18n('removeMenu');?>" id="removeMenuDiv" dojoType="dojo.dnd.Source" data-dojo-props="accept: ['menuBar'], singular:true" style="margin: 0px 5px 0px 5px;height: 141px;width: auto;border: 1px solid var(--color-dark);border-radius: 5px;background: white;overflow:hidden;visibility: hidden;">
              <table style="width:100%;height:100%;">
               <tr>
                 <td align="center" style="font-style: italic;font-size: 11px;color: #9c9c9c;"><?php echo i18n('removeMenu');?></td>
               </tr>
               <tr>
                 <td class="imageColorNewGui" align="center" title="<?php echo i18n('removeMenu');?>" style="padding-bottom: 20px;"><?php echo formatNewGuiButton('Remove', 32, false);?></td>
               </tr>
              </table>
            </div>
          </td>
          <td>
            <div id="anotherMenubarList" name="anotherMenubarList" style="width:100%;z-index:9999999;">
             <?php
             if($defaultMenu == 'menuBarCustom'){
             	$startRow = $idRow+1;
             }else{
             	$idRow = 1;
             	$startRow = $idRow;
             } 
              for($i=$startRow; $i<=($idRow+4); $i++){
                  if($i > 5){
                    $idAnotherRow = $i-5;
                  }else{
                    $idAnotherRow = $i;
                  }
                 $idDiv = "menuBarDndSource$idAnotherRow";
                 $idInput = "idFavoriteRow$idAnotherRow";
                 ?>
              <div id="<?php echo 'anotherBar'.$idAnotherRow;?>" class="anotherBar" style="margin-top: 5px;height: 43px;width:100%;border: 1px solid var(--color-dark);border-radius: 5px;background: white;overflow:hidden;">
                <input type="hidden" id="<?php echo $idInput;?>" name="<?php echo $idInput;?>" value="<?php echo $idAnotherRow;?>"> 
                <table style="width:100%;height:100%;" onWheel="wheelFavoriteRow(<?php echo $idRow;?>, event, <?php echo $nbFavoriteRow;?>);" oncontextmenu="event.preventDefault();editFavoriteRow(false);">
                     <tr>
                     <td style="font-weight: bold;font-size: 13pt;text-align: center;color: var(--color-dark);width: 50px;border-right: 1px solid var(--color-dark);cursor:pointer;" onclick="saveUserParameter('idFavoriteRow', <?php echo $idAnotherRow;?>);gotoFavoriteRow(<?php echo $idRow;?>,<?php echo $idAnotherRow;?>);">
                       <?php echo $idAnotherRow; ?>
                     </td>
                      <td style="height:100%;">
                        <div dojoType="dojo.dnd.Source" class="anotherBarDiv" id="<?php echo $idDiv;?>" jsId="<?php echo $idDiv;?>" name="<?php echo $idDiv;?>" data-dojo-props="accept: ['menuBar'], horizontal: true, singular:true" style="width: 1000%;height: 43px;vertical-align:middle;">
      	                  <?php Menu::drawAllNewGuiMenus('menuBarCustom', null, $idAnotherRow,true);?>
  	                    </div>
                      </td>
                     </tr>
                </table>
              </div>
              <?php 
              }?>
            </div>
          </td>
          <td style="width:70px;"></td>
        </tr></table>
      </div>
      <?php }

      $hideMenuTopParam = (Parameter::getGlobalParameter ( 'MenuBarTop' )=='NO')?'YES':'NO';
      if (sessionValueExists('hideMenuTop') and getSessionValue('hideMenuTop')=='YES'){
        $hideMenuTopParam = 'YES';
      }
      if ( $hideMenuTopParam=='YES' and !isNewGui() ) {?>
      <script>
        dojo.byId('statusBarDiv').style.height="0px";
        dojo.byId('statusBarDiv').style.padding="0px";
        dojo.byId('leftDiv').style.top='30px';
        dojo.byId('centerDiv').style.top='30px';
        dojo.byId('menuBarShow').style.top='30px';
        var height=parseInt(dojo.byId('mainDiv').offsetHeight)-30;
      </script>
    <?php }?>
        <div id="centerDiv" dojoType="dijit.layout.ContentPane" region="center">
    </div>
    <div id="statusBarDivBottom" dojoType="dijit.layout.ContentPane" region="bottom" style="overflow:visible;display:block;height:0px; position:absolute; bottom:0px;">
      <div id="dialogReminder">
          <div id="reminderDiv" style="width:100%;height: 142px"></div>
            <div style="width:100%;text-align:right">
              <table>
                <tr id="trMarkAs" style="display:flex;gap:5px;">
                  <td style="padding-top:2px">
                    <button dojoType="dijit.form.Button" class="roundedVisibleButtonInfo" onclick="setAlertReadMessage();">
                      <span class="markAsReadIcon"></span>
                        <?php echo i18n("markAsRead");?>
                      </button>
                  </td>
                  <td width="80%" style="padding-top:2px">
                   <span id="markAllAsReadButtonDiv" >
                	 		<button  dojoType="dijit.form.Button" class="roundedVisibleButtonInfo" id="markAllAsReadButton" onclick="setAllAlertReadMessage();">
                	      <?php echo i18n("markAllAsRead");?>
                	 		</button>
                	 </span>
                  </td>
                </tr>
              </table>
          </div>
          <div style="width:100%; height:15%; text-align:right">
              <span class="iconClock"></span>
              <?php echo ucfirst(i18n("remindMeIn"));?>
              <input type="input" dojoType="dijit.form.TextBox" id="remindAlertTime" name="remindAletTime" value="15" style="width:25px" />
              <?php echo i18n("shortMinute");?>
              <button dojoType="dijit.form.Button" class="roundedVisibleButtonInfo" onclick="setAlertRemindMessage();">
                  <span class="iconNotification22 iconNotification iconSize22"></span>
                  <?php echo i18n("remind");?>
              </button>
          </div>
      </div>
       
    </div>
    
    <!--the left div must be created after the central div for the dynamism of the left menu on the new interface -->
 <?php if(isNewGui()){?> </div></div></div>
    <div id="leftMenu" class="menu-left"> 
    <?php 
      }
    ?>
    <div id="leftDiv" dojoType="dijit.layout.ContentPane" region="left"  splitter="<?php echo (isNewGui())?'false':'true';?>" style="width:<?php echo ((!isNewGui())?$IconSizeMenuHide2:(($isMenuLeftOpen=='false')?'0px':'250px'));?><?php echo (isNewGui())?';dispaly:none;':'';?>" >
      <?php if(!isNewGui()){?>
      <script type="dojo/connect" event="resize" args="evt">
         if (hideShowMenuInProgress) return;
         if (dojo.byId("leftDiv").offsetWidth>52) 
         saveContentPaneResizing("contentPaneLeftDivWidth", dojo.byId("leftDiv").offsetWidth, true);
         dojo.byId("hideMenuBarShowButton2").style.left=dojo.byId("leftDiv").offsetWidth+3+"px";
      </script>
      
      <div id="menuBarShow" class="dijitAccordionTitle " onMouseover="tempShowMenu('mouse');" onClick="tempShowMenu('click');">
        <div id="menuBarIcon" valign="middle"></div>
      </div>       
      <div class="container" dojoType="dijit.layout.BorderContainer" liveSplitters="false">

        <div id="logoDiv" dojoType="dijit.layout.ContentPane" region="top">
          <?php 
            $width=300;
            if (sessionValueExists('screenWidth')){
              $width = getSessionValue('screenWidth') * 0.2;
            }
            $zoom=round($width/300*100, 0);  
          ?>
          <div id="logoTitleDiv" 
               style="background-image: url(<?php 
               if (file_exists("../logo.gif")) echo '../logo.gif';
	    		          else if (file_exists("../logo.jpg")) echo '../logo.jpg';
	    		          else if (file_exists("../logo.png")) echo '../logo.png';
	    		          else echo 'img/titleWhiteSmall.png';?>); background-repeat: no-repeat; height: 50px; width:100%;background-position:center" 
               onclick="showAbout(aboutMessage);" title="<?php echo i18n('aboutMessage');?>" > 
          </div>
          <div style="position:absolute; right:0px; bottom:0px" id="helpbutton" style="text-align:right;" onclick="showHelp();">
            <div width="32px" height="32px" class="iconHelpTitle" title="<?php echo i18n('help');?>" onclick="showHelp();">&nbsp;</div>
          </div>
        </div>
        <div id="mapDiv" dojoType="dijit.layout.ContentPane" region="center" style="padding: 0px; margin:0px">
          <div dojoType="dijit.layout.AccordionContainer" style="height: 300px;" >
          <?php $selectedAccordionTop=Parameter::getUserParameter('accordionPaneTop');
                if (! $selectedAccordionTop) $selectedAccordionTop='menuTree';?>
            <div dojoType="dijit.layout.ContentPane" title="<?php echo i18n('menu');?>" 
              style="overflow: hidden !important;" <?php if ($selectedAccordionTop=='menuTree') echo 'selected="true"';?>>
              <?php include "menuTree.php"; ?>
              <script type="dojo/connect" event="onShow" args="evt">
                saveDataToSession("accordionPaneTop","messageDiv",true);
              </script>
            </div>
            <?php if (securityCheckDisplayMenu(null,'Document')) {?>
            <div dojoType="dijit.layout.ContentPane" title="<?php echo i18n('document');?>" <?php if ($selectedAccordionTop=='document') echo 'selected="true"';?>>
              <div dojoType="dojo.data.ItemFileReadStore" id="directoryStore" jsId="directoryStore" url="../tool/jsonDirectory.php<?php echo Security::addTokenIndexToUrl('?');?>"></div>
              <?php if (securityCheckDisplayMenu(null,'DocumentDirectory')) {?>
              <div style="position: absolute; float:right; right: 5px; cursor:pointer;"
                title="<?php echo i18n("menuDocumentDirectory");?>"
                onclick="if (checkFormChangeInProgress()){return false;};loadContent('objectMain.php?objectClass=DocumentDirectory','centerDiv');"
                class="iconDocumentDirectory22">
              </div>
              <?php }?>
              <div dojoType="dijit.tree.ForestStoreModel" id="directoryModel" jsId="directoryModel" store="directoryStore"
               query="{id:'*'}" rootId="directoryRoot" rootLabel="Documents"
               childrenAttrs="children">
              </div>             
              <div dojoType="dijit.Tree" id="documentDirectoryTree" model="directoryModel" openOnClick="false" showRoot='false'>
                <script type="dojo/method" event="onClick" args="item">;
                  if (checkFormChangeInProgress()){return false;}
                  loadContent("objectMain.php?objectClass=Document&Directory="+directoryStore.getValue(item, "id"),"centerDiv");
                </script>
                <script type="dojo/method" event="onOpen" args="item">;
                  dojo.query('.dijitTreeNode .dijitTreeContent', this.id).forEach(function(node){
                    dojo.query('.dijitTreeLabel', node).forEach(function(label){
                      var spanId = label.id+'Zip';
                      var parentId = label.id.slice(0, -6);
                      if(!dojo.byId(spanId) && parentId != 'dijit__TreeNode_0'){
                        node.innerHTML += '<span id="'+spanId+'" role="presentation" class="dijitInline" style="display:none">'+
                        '<div class="iconButtonZipFile iconButtonZipFile16 iconSize16"></div></span>';

                      }
                      if(parentId != 'dijit__TreeNode_0'){
                        var span = document.getElementById(spanId);
                        span.addEventListener("click", stopEventDocumentDirectoryLeftMenu, false);
                        node.parentNode.insertBefore(span, node.previousSibling);
                        if(!dojo.hasClass(node.parentNode , 'isAlreadyCreated')){
                          dojo.connect(node.parentNode , 'mouseenter' ,function(){showZipButton(span, node.firstElementChild);});
                          dojo.connect(node.parentNode , 'mouseleave' ,function(){showZipButton(span, node.firstElementChild);});
                          dojo.addClass(node.parentNode , 'isAlreadyCreated');
                        }
                      }
                    });
                  });
                </script>
              </div>
              <script type="dojo/connect" event="onShow" args="evt">
                saveDataToSession("accordionPaneTop", "document", true);
              </script>
            </div>
            <?php }?>
          </div>
        </div>
        <?php
           $leftBottomHeight=getContentPaneSize('contentPaneLeftBottomDivHeight');
           $leftBottomHeight=($leftBottomHeight)?$leftBottomHeight.'px':'300px';?>
        <div dojoType="dijit.layout.ContentPane" id="leftBottomDiv" region="bottom" splitter="true" style="height:<?php echo $leftBottomHeight;?>;">
          <script type="dojo/connect" event="resize" args="evt">
             saveContentPaneResizing("contentPaneLeftBottomDivHeight", dojo.byId("leftBottomDiv").offsetHeight, true);
          </script>
          <div id="accordionLeftBottomDiv" dojoType="dijit.layout.AccordionContainer" persists="true">
            <?php $selectedAccordionBottom=Parameter::getUserParameter('accordionPaneBottom');
                if (! $selectedAccordionBottom) $selectedAccordionBottom='projectLinkDiv';?>
<!-- BEGIN - ADD BY TABARY - NOTIFICATION SYSTEM -->                
            <?php if (securityCheckDisplayMenu(null,'Notification') and isNotificationSystemActiv()) {?>
            <div id="notificationAccordion"
                 dojoType="dijit.layout.ContentPane" 
                 class="background" 
                 title="<?php echo i18n('accordionNotification');?>" 
                 <?php if ($selectedAccordionBottom=='notification') echo 'selected="true"';?>>
                <div dojoType="dojo.data.ItemFileReadStore" 
                     id="notificationStore" 
                    jsId="notificationStore" url="../tool/jsonNotification.php<?php echo Security::addTokenIndexToUrl('?');?>">
                </div>
                <div style="position: absolute; float:right; right: 5px; cursor:pointer;"
                     title="<?php echo i18n("notificationAccess");?>"
                     onclick="if (checkFormChangeInProgress()){return false;};loadContent('objectMain.php?objectClass=Notification','centerDiv');"
                     class="iconNotification22">
                </div>
                <div style="position: absolute; float:right; right: 45px; cursor:pointer;"
                     title="<?php echo i18n("notificationRefresh");?>"
                     onclick="if (checkFormChangeInProgress()){return false;};refreshNotificationTree(true);"
                     class="iconNotificationRefresh22">
                </div>
                <div dojoType="dijit.tree.ForestStoreModel" id="notificationModel" jsId="notificationModel" store="notificationStore"
                     query="{id:'*'}" rootId="notificationRoot" rootLabel="Notifications"
                     childrenAttrs="children">
                </div>             
                <div dojoType="dijit.Tree" id="notificationTree" model="notificationModel" openOnClick="false" showRoot='false'>
                    <script type="dojo/method" event="onLoad" args="evt">
                        var cronCheckNotification = <?php echo Parameter::getGlobalParameter('cronCheckNotifications'); ?>;
                        var intervalNotificationTreeDelay = cronCheckNotification*1000;
                        var intervalNotificationTree = setInterval(function() {
                                                                                refreshNotificationTree(true);
                                                                              },
                                                                   intervalNotificationTreeDelay);
                    </script>
                    <script type="dojo/method" event="onClick" args="item">;
                        if (notificationStore.getValue(item, "objClass")==="") {return false;}
                        if (checkFormChangeInProgress()){return false;}
                        var objectId = "";
                        var objClass = notificationStore.getValue(item, "objClass");
                        if (objClass=="NotificationManual") {
                                objClass="Notification";                            
                        }
                        if (notificationStore.getValue(item, "objId")!=="") {
                            objectId = notificationStore.getValue(item, "objId");
                            gotoElement(objClass, objectId, true);
                        } else {
                            loadContent("objectMain.php?objectClass="+objClass,"centerDiv");
                        }                            
                    </script>
                    <script type="dojo/method" event="getIconClass" args="item">
                        if (item == this.model.root) {
                          return "checkBox";
                        } else {
                            var isTotal = notificationStore.getValue(item,"isTotal");
                            if (isTotal==="YES") {
                                var totalCount = notificationStore.getValue(item,"count");
                                totalUnreadNotificationsCount = totalCount;
                                var ac = dijit.byId('accordionLeftBottomDiv');
                                if (totalCount>0) {
                                    ac.selectChild(dijit.byId('notificationAccordion'));
                                } else {
//                                    ac.selectChild(dijit.byId('messageDiv'));                                    
                                }
                                // Update the Title Panel
                                var titlePane = totalCount + ' ';
                                titlePane += i18n('accordionNotification');
                                var pane = dijit.byId('notificationAccordion');
                                pane.set("title",titlePane);
                                
                                // Hide menuBarNotificationCount if totalCount=0
                                if (totalCount==0) {
                                    document.getElementById("notificationTree").style.visibility = "hidden";
                                    document.getElementById("menuBarNotificationCount").style.visibility = "hidden";
                                    document.getElementById("drawNotificationUnread").style.visibility = "hidden";
                                    document.getElementById("countNotifications").style.visibility="hidden";
                                } else {
                                    // Show and Update the Notification count in menuBar
                                    document.getElementById("notificationTree").style.visibility = "visible";
                                    document.getElementById("countNotifications").style.visibility="visible";
                                    document.getElementById("menuBarNotificationCount").style.visibility = "visible";
                                    document.getElementById("countNotifications").innerHTML = totalCount;
                                }
                                loadContent("../view/menuNotificationRead.php", "drawNotificationUnread");  
                            }
                            
                            return notificationStore.getValue(item, "iconClass");
                        }
                    </script>
                </div>
                <script type="dojo/connect" event="onShow" args="evt">
                    saveDataToSession("accordionPaneBottom", "notification", true);
                </script>
            </div>
            <?php }?>
<!-- END - ADD BY TABARY - NOTIFICATION SYSTEM -->
            <div id="projectLinkDiv" class="background" dojoType="dijit.layout.ContentPane" <?php if ($selectedAccordionBottom=='projectLinkDiv') echo 'selected="true"';?> title="<?php echo i18n('ExternalShortcuts');?>">
              <?php include "../view/shortcut.php"?>
              <script type="dojo/connect" event="onShow" args="evt">
                
                saveDataToSession("accordionPaneBottom", "projectLinkDiv", true);
              </script>
            </div>
            <div id="messageDiv" dojoType="dijit.layout.ContentPane" title="<?php echo i18n('Console');?>" <?php if ($selectedAccordionBottom=='messageDiv') echo 'selected="true"';?>>
              <script type="dojo/connect" event="onShow" args="evt">
                saveDataToSession("accordionPaneBottom", "messageDiv", true);
              </script>
            </div>
          </div>
        </div>
      </div> 
      <?php
      }else{
         include 'menuNewGuiLeft.php'; 
      } 
      ?>
    </div>
     <?php if(isNewGui()){?></div><?php }?>
    <div id="dialogAlert" dojoType="dijit.Dialog" title="<?php echo i18n("dialogAlert");?>">
      <table>
        <tr>
          <td width="50px" id="dialogAlertIcon">
               <?php echo formatIcon('Alert', 32);?>
          </td>
          <td>
            <div id="dialogAlertMessage">
            </div>
          </td>
        </tr>
        <tr><td colspan="2" align="center">&nbsp;</td></tr>
        <tr>
          <td colspan="2" align="center">
            <button class="smallTextButton" dojoType="dijit.form.Button" type="submit" onclick="dijit.byId('dialogAlert').acceptCallback();dijit.byId('dialogAlert').hide();">
              <?php echo i18n("buttonOK");?>
            </button>
          </td>
        </tr>
      </table>
    </div>


<div id="dialogInfo" dojoType="dijit.Dialog" title="<?php echo i18n("dialogInformation");?>">
  <table>
    <tr>
      <td width="50px" id="dialogInfoIcon">
        <?php echo formatIcon('Info', 32);?>
      </td>
      <td>
        <div id="dialogInfoMessage">
        </div>
      </td>
    </tr>
    <tr>
      <td colspan="2" align="center">
        <br/>
        <button class="smallTextButton" dojoType="dijit.form.Button" type="submit" onclick="dijit.byId('dialogInfo').acceptCallback();dijit.byId('dialogInfo').hide();">
          <?php echo i18n("buttonOK");?>
        </button>
      </td>
    </tr>
  </table>
</div>

<div id="dialogError" dojoType="dijit.Dialog" title="<?php echo i18n("dialogError");?>">
  <table>
    <tr>
      <td width="50px" id="dialogErrorIcon">
        <?php echo formatIcon('Error',32);?>
      </td>
      <td>
        <div id="dialogErrorMessage">
        </div>
      </td>
    </tr>
    <tr height="50px">
      <td colspan="2" align="center">
        <?php echo i18n("contactAdministrator");?>
      </td>
    </tr>
    <tr><td colspan="2" align="center">&nbsp;</td></tr>
    <tr>
      <td colspan="2" align="center">
        <button class="smallTextButton" dojoType="dijit.form.Button" type="submit" onclick="dijit.byId('dialogError').hide();">
          <?php echo i18n("buttonOK");?>
        </button>
      </td>
    </tr>
  </table>
</div>


 
<div id="dialogQuestion" dojoType="dijit.Dialog" title="<?php echo i18n("dialogQuestion");?>">
  <table>
    <tr>
      <td width="50px" id="dialogQuestionIcon">
        <img src="img/confirm.png" />
      </td>
      <td>
        <div id="dialogQuestionMessage"></div>
      </td>
    </tr>
    <tr><td colspan="2" align="center">&nbsp;</td></tr>
    <tr>
      <td colspan="2" align="center">
        <button class="smallTextButton" dojoType="dijit.form.Button" type="button" onclick="dijit.byId('dialogQuestion').acceptCallbackNo();dijit.byId('dialogQuestion').hide();">
          <?php echo i18n("buttonNo");?>
        </button>
        <button class="smallTextButton" id="dialogQuestionSubmitButton" dojoType="dijit.form.Button" type="submit" onclick="protectDblClick(this);dijit.byId('dialogQuestion').acceptCallbackYes();dijit.byId('dialogQuestion').hide();">
          <?php echo i18n("buttonYes");?>
        </button>
      </td>
    </tr>
  </table>
</div>

<!-- remi 7823-->
<div id="dialogQuestionNoSave" dojoType="dijit.Dialog" title="<?php echo i18n("dialogQuestion");?>" onCancel="dijit.byId('dialogQuestionNoSave').acceptCallbackNo();dijit.byId('dialogQuestionNoSave').hide()">
  <table>
    <tr>
      <td width="50px" id="dialogQuestionNoSaveIcon">
        <img src="img/confirm.png" />
      </td>
      <td>
        <div id="dialogQuestionNoSaveMessage"></div>
      </td>
    </tr>
    <tr><td colspan="2" align="center">&nbsp;</td></tr>
    <tr>
      <td colspan="3" align="center">
        <button class="mediumTextButton" dojoType="dijit.form.Button" type="button" onclick="dijit.byId('dialogQuestionNoSave').acceptCallbackNo();dijit.byId('dialogQuestionNoSave').hide();">
          <?php echo i18n("buttonNoForQuestionNoSave");?>
        </button>
        <button class="mediumTextButton" id="dialogQuestionNoSaveSubmitButton" dojoType="dijit.form.Button" type="submit" onclick="protectDblClick(this);dijit.byId('dialogQuestionNoSave').acceptCallbackYes();dijit.byId('dialogQuestionNoSave').hide();">
          <?php echo i18n("buttonYesForQuestionNoSave");?>
        </button>
        <button class="longTextButton" id="dialogQuestionNoSaveSaveButton" dojoType="dijit.form.Button" type="submit" onclick="protectDblClick(this);dijit.byId('dialogQuestionNoSave').acceptCallbackSave();dijit.byId('dialogQuestionNoSave').hide();">
          <?php echo i18n("buttonSaveForQuestionNoSave");?>
        </button>
      </td>
    </tr>
  </table>
 <script type="dojo/method" event="onKeyUp" >
  if(event.keyCode==13){
    dijit.byId('dialogQuestionNoSave').acceptCallbackSave();
    dijit.byId('dialogQuestionNoSave').acceptCallbackYes();
    dijit.byId('dialogQuestionNoSave').hide();
  }
 </script>
</div>


<div id="dialogConfirm" dojoType="dijit.Dialog" title="<?php echo i18n("dialogConfirm");?>">
  <table>
    <tr>
      <td width="50px" id="dialogConfirmIcon">
           <?php echo formatIcon('Confirm',32);?>
      </td>
      <td>
        <div id="dialogConfirmMessage"></div>
      </td>
    </tr>
    <tr><td colspan="2" align="center">&nbsp;</td></tr>
    <tr>
      <td colspan="2" align="center">
        <input type="hidden" id="dialogConfirmAction">
        <button class="mediumTextButton" dojoType="dijit.form.Button" type="button" onclick="dijit.byId('dialogConfirm').hide();">
          <?php echo i18n("buttonCancel");?>
        </button>
        <button class="mediumTextButton" id="dialogConfirmSubmitButton" dojoType="dijit.form.Button" type="submit" onclick="protectDblClick(this);dijit.byId('dialogConfirm').acceptCallback();dijit.byId('dialogConfirm').hide();">
          <?php echo i18n("buttonOK");?>
        </button>
      </td>
    </tr>
  </table>
</div>

<div id="dialogPrint" dojoType="dijit.Dialog" title="<?php echo i18n("dialogPrint");?>" onHide="window.document.title=applicationName;dojo.byId('printFrame').src='../view/preparePreview.php?csrfToken=<?php echo $token;?>';removeFullScreenDialog('dialogPrint');" >
  <?php 
    $printHeight=600;
    $printWidth=1010;
    if (sessionValueExists('screenHeight')) {
      $printHeight=round(getSessionValue('screenHeight')*0.65);
    }
    if (sessionValueExists('screenWidth') and getSessionValue('screenWidth')<1160) {
      $printWidth=round(getSessionValue('screenWidth')*0.87);
    }
  ?> 
  <div id="dialogPrintFullScreenIcon" title="<?php echo i18n("fullScreen");?>" class="fullScreenIcon" tabindex="-1" onClick="toggleFullScreenDialog('dialogPrint');"></div>
  <div style="widht:100%" id="printPreview" dojoType="dijit.layout.ContentPane" region="center">
    <table style="widht:100%">
      <tr>
        <td id="printDialogFrameContainer" style="width:<?php echo $printWidth;?>px" align="right">
          <div id="sentToPrinterDiv">
            <table width="100%"><tr><td width="300px" align="right">
              <button  id="sendToPrinter" dojoType="dijit.form.Button" showlabel="false" class="notButton"
                title="<?php echo i18n('sendToPrinter');?>" 
                iconClass="dijitButtonIcon dijitButtonIconPrint imageColorNewGui" >
                <script type="dojo/connect" event="onClick" args="evt">
                  sendFrameToPrinter();
                </script>
              </button>
            </td>
            <td align="left" width="<?php echo $printWidth - 300;?>px" class="textColorNewGui">
              &nbsp;<?php echo i18n('sendToPrinter')?>
            </td></tr></table>
          </div>
        </td>
      </tr>
      <tr>
        <td>   
          <iframe width="100%" height="<?php echo $printHeight;?>px"
            scrolling="auto" frameborder="0px" name="printFrame" id="printFrame" src="" onload="hideWait();" onreadystatechange="hideWait();">
          </iframe>
          <iframe width="100%" height="10px" style="display:none"
            scrolling="auto" frameborder="0px" name="generateAttachPDFFrame" id="generateAttachPDFFrame" src="" onload="if (top.dojo.byId('detailDiv')) {redirectOnTab('', '', 'fichier');loadContent('objectDetail.php?refreshAttachments=true',dojo.byId('objectClass').value + '_Attachment','listForm');}">
          </iframe>
        </td>
      </tr>
    </table>
  </div>
</div>

<div class="dijitDialog dijitDialogFocused dijitFocused" id="dialogShowHtml" dojoType="dijit.Dialog" onHide="if (window.frames['showHtmlFrame']) window.frames['showHtmlFrame'].location.href='../view/preparePreview.php?csrfToken=<?php echo $token;?>';removeFullScreenDialog('dialogShowHtml');" title="">
  <?php 
    $printHeight=600;
    $printWidth=1010;
    if (sessionValueExists('screenHeight')) {
      $printHeight=round(getSessionValue('screenHeight')*0.50);
    }
  ?> 
  <div id="dialogShowHtmlFullScreenIcon" title="<?php echo i18n("fullScreen");?>" class="fullScreenIcon" tabindex="-1" onClick="toggleFullScreenDialog('dialogShowHtml');"></div>
  <div style="widht:100%" id="showHtmlLink" dojoType="dijit.layout.ContentPane" region="center">
    <table style="width:100%">
      <tr>
        <td id="showHtmlContainer" width="<?php echo $printWidth;?>px">   
          <iframe width="100%" height="<?php echo $printHeight;?>px"
            scrolling="auto" frameborder="0px" name="showHtmlFrame" id="showHtmlFrame" src="">
          </iframe>
        </td>
      </tr>
    </table>
  </div>
</div>

<div id="showHtmlLink8" dojoType="dijit.Dialog"  id="divPrintFullScreenShowHtml2" style="top:0;z-index:99999;display:none;position:absolute;width:99%;height:99%;">test
<iframe scrolling="auto" frameborder="0px" name="showHtmlFrame3" id="showHtmlFrame3" src="">
</iframe>
</div>

<div id="dialogDetail" dojoType="dijit.Dialog" title="<?php echo i18n("dialogDetailCombo");?>" class="background" onHide="window.document.title=applicationName;">
  <?php 
    $detailHeight=600;
    $detailWidth=1010;
    if ( sessionValueExists('screenWidth') and getSessionValue('screenWidth')<1160) {
       $detailWidth = getSessionValue('screenWidth') * 0.87;
    }
    if ( sessionValueExists('screenHeight')) {
      $detailHeight=round(getSessionValue('screenHeight')*0.70);
    }
  ?> 
  <div id="detailView" dojoType="dijit.layout.ContentPane" region="center" style="overflow:hidden" class="background">
    <table style="width:100%;height:100%">
      <?php if (!isNewGui()) {?><tr style="height:10px;"><td></td></tr><?php }?>
      <tr>
        <?php if (isNewGui()) {?>
        <td></td>
        <td align="left" style="width:<?php echo ($detailWidth - 400);?>px; position:relative;">
          <div style="width:100%;font-size:8pt" dojoType="dijit.layout.ContentPane" region="center" name="comboDetailResult" id="comboDetailResult"></div>
        </td>
        
        <?php }?>
        <td width="32px" align="left" style="white-space:nowrap;<?php if (isNewGui()) echo "position:relative;top:-5px;right:12px;"?>">
          <input type="hidden" name="canCreateDetail" id="canCreateDetail" />
          <input type="hidden" id='comboName' name='comboName' value='' />
          <input type="hidden" id='comboClass' name='comboClass' value='' />
          <input type="hidden" id='comboMultipleSelect' name='comboMultipleSelect' value='' />
          <button id="comboSearchButton" dojoType="dijit.form.Button" showlabel="false"
            title="<?php echo i18n('comboSearchButton');?>" 
            iconClass="dijitButtonIcon dijitButtonIconSearch" class="dialogDetailButton">
            <script type="dojo/connect" event="onClick" args="evt">
              displaySearch();
            </script>
          </button>
          <button id="comboSelectButton" dojoType="dijit.form.Button" showlabel="false"
            title="<?php echo i18n('comboSelectButton');?>" 
            iconClass="dijitButtonIcon dijitButtonIconSelect" class="dialogDetailButton">
            <script type="dojo/connect" event="onClick" args="evt">
              selectDetailItem();
            </script>
          </button>
          <button id="comboNewButton" dojoType="dijit.form.Button" showlabel="false"
            title="<?php echo i18n('comboNewButton');?>" 
            iconClass="dijitButtonIcon dijitButtonIconNew" class="dialogDetailButton">
            <script type="dojo/connect" event="onClick" args="evt">
              newDetailItem();
            </script>
          </button>
          <button id="comboSaveButton" dojoType="dijit.form.Button" showlabel="false"
            title="<?php echo i18n('comboSaveButton');?>" 
            iconClass="dijitButtonIcon dijitButtonIconSave" class="dialogDetailButton">
            <script type="dojo/connect" event="onClick" args="evt">
              saveDetailItem();
            </script>
          </button>
         <button id="comboCloseButton" dojoType="dijit.form.Button" showlabel="false"
            title="<?php echo i18n('comboCloseButton');?>" 
            iconClass="dijitButtonIcon dijitButtonIconUndo" class="dialogDetailButton">
            <script type="dojo/connect" event="onClick" args="evt">
              hideDetail();
            </script>
          </button>
        </td>
        <?php if (!isNewGui()) {?>
        <td align="left" style="width:<?php echo ($detailWidth - 400);?>px; position:relative;">
          <div style="width:100%;font-size:8pt" dojoType="dijit.layout.ContentPane" region="center" name="comboDetailResult" id="comboDetailResult"></div>
        </td>
        <td></td><?php }?>
      </tr>
      <?php if (!isNewGui()) {?><tr><td colspan="3">&nbsp;</td></tr><?php }?>
      <tr>
        <td width="<?php echo $detailWidth;?>px" colspan="3">   
          <iframe width="100%" height="<?php echo $detailHeight;?>px"
            scrolling="auto" frameborder="0px" name="comboDetailFrame" id="comboDetailFrame" src="" >
          </iframe>
        </td>
      </tr>
    </table>
  </div>
  <div id="someNodeHandle"  style="bottom:10px;right:10px;" data-dojo-type="dojox.layout.ResizeHandle" data-dojo-props="targetId:'detailView'"></div>
</div>

<input type="hidden" id="noFilterSelected" name="noFilterSelected" value="true" />

<div id="dialogOtherVersion" dojoType="dijit.Dialog" title="<?php echo i18n("dialogOtherVersion");?>">
  <table>
    <tr>
      <td>
       <form id='otherVersionForm' name='otherVersionForm' onSubmit="return false;">
         <input id="otherVersionRefType" name="otherVersionRefType" type="hidden" value="" />
         <input id="otherVersionRefId" name="otherVersionRefId" type="hidden" value="" />
         <input id="otherVersionType" name="otherVersionType" type="hidden" value="" />
         <input id="otherVersionId" name="otherVersionId" type="hidden" value="" />
         <table>
           <tr><td>&nbsp;</td><td>&nbsp;</td></tr>
           <tr>
             <td class="dialogLabel" >
               <label for="otherVersionId" ><?php echo i18n("colOtherVersions") ?>&nbsp;:&nbsp;</label>
             </td>
             <td>
               <table><tr><td>
               <div id="dialogOtherVersionList" dojoType="dijit.layout.ContentPane" region="center">
                 <input id="otherVersionIdVersion" name="otherVersionIdVersion" type="hidden" value="" />
               </div>
               </td><td style="vertical-align: top">
               <button id="otherVersionDetailButton" dojoType="dijit.form.Button" showlabel="false"
                 title="<?php echo i18n('showDetail')?>"
                 iconClass="iconSearch22 iconSearch iconSize22 imageColorNewGui" class="notButton notButtonRounded">
                 <script type="dojo/connect" event="onClick" args="evt">
                   showDetailOtherVersion();
                 </script>
               </button>
               </td></tr></table>
             </td>
           </tr>
           <tr><td>&nbsp;</td><td>&nbsp;</td></tr>
         </table>
        </form>
      </td>
    </tr>
    <tr>
      <td align="center">
        <input type="hidden" id="dialogOtherVersionAction">
        <button class="mediumTextButton" dojoType="dijit.form.Button" type="button" onclick="dijit.byId('dialogOtherVersion').hide();">
          <?php echo i18n("buttonCancel");?>
        </button>
        <button class="mediumTextButton" dojoType="dijit.form.Button" type="submit" id="dialogOtherVersionSubmit" onclick="protectDblClick(this);saveOtherVersion();return false;">
          <?php echo i18n("buttonOK");?>
        </button>
      </td>
    </tr>
  </table>
</div>

<div id="dialogOtherClient" dojoType="dijit.Dialog" title="<?php echo i18n("dialogOtherClient");?>">
  <table>
    <tr>
      <td>
       <form id='otherClientForm' name='otherClientForm' onSubmit="return false;">
         <input id="otherClientRefType" name="otherClientRefType" type="hidden" value="" />
         <input id="otherClientRefId" name="otherClientRefId" type="hidden" value="" />
         <input id="otherClientId" name="otherClientId" type="hidden" value="" />
         <table>
           <tr><td>&nbsp;</td><td>&nbsp;</td></tr>
           <tr>
             <td class="dialogLabel" >
               <label for="otherClientId" ><?php echo i18n("colOtherClients") ?>&nbsp;:&nbsp;</label>
             </td>
             <td>
               <table><tr><td>
               <div id="dialogOtherClientList" dojoType="dijit.layout.ContentPane" region="center">
                 
                 <select id="otherClientIdClient" size="14" name="otherClientIdClient[]" multiple
                  onchange="selectOtherClientItem();"  ondblclick="saveOtherClient();"
                  class="selectList" >
                 </select>
               </div>
               </td><td style="vertical-align: top">
               <?php $canSeeClient=securityCheckDisplayMenu(null, 'Client');
               if ($canSeeClient) {?>
               <button id="otherClientDetailButton" dojoType="dijit.form.Button" showlabel="false"
                 title="<?php echo i18n('showDetail')?>"
                 iconClass="iconSearch22 iconSearch iconSize22 imageColorNewGui" class="notButton notButtonRounded">
                 <script type="dojo/connect" event="onClick" args="evt">
                   showDetailOtherClient();
                 </script>
               </button>
               <?php }?>
               </td></tr></table>
             </td>
           </tr>
           <tr><td>&nbsp;</td><td>&nbsp;</td></tr>
         </table>
        </form>
      </td>
    </tr>
    <tr>
      <td align="center">
        <input type="hidden" id="dialogOtherClientAction">
        <button class="mediumTextButton" dojoType="dijit.form.Button" type="button" onclick="dijit.byId('dialogOtherClient').hide();">
          <?php echo i18n("buttonCancel");?>
        </button>
        <button class="mediumTextButton" dojoType="dijit.form.Button" type="submit" id="dialogOtherClientSubmit" onclick="protectDblClick(this);saveOtherClient();return false;">
          <?php echo i18n("buttonOK");?>
        </button>
      </td>
    </tr>
  </table>
</div>

<!-- ADD BY Marc TABARY - 2017-02-23 - CHOICE OBJECTS LINKED BY ID TO MAIN OBJECT -->
<!-- DIALOG - What is show on Add submit -->
<div id="dialogObject" dojoType="dijit.Dialog" title="<?php echo i18n("dialogObject");?>">
  <table>
    <tr>
      <td>
        <!-- FORM -->
        <form id='objectFormDialog' name='objectFormDialog' onSubmit="return false;">
          <!-- Store the class name of the main object -->  
          <input id="mainObjectClass" name="mainObjectClass" type="hidden" value="" />
          <!-- Store the id of the instance of the main object -->            
          <input id="idInstanceOfMainClass" name="idInstanceOfMainClass" type="hidden" value="" />
          <!-- Store the linked object class Name -->  
          <input id="linkObjectClassName" name="linkObjectClassName" type="hidden" value="" />
         <table>
            <tr>
              <td class="dialogLabel" >
                <label for="dialogObjectList" ><?php echo i18n("item") ?>&nbsp;:&nbsp;</label>
              </td>
              <td>
                <table><tr><td>
                  <div id="dialogObjectList" dojoType="dijit.layout.ContentPane" region="center">
                    <!-- Place of select construct dynamicaly by (dymanicListObject) -->  
                    <input id="linkedObjectId" name="linkedObjectId" type="hidden" value="" />
                  </div>
                </td></tr></table>
              </td>
              <td style="vertical-align: top;">
               <div style="width: 100%;">
                 <button id="linkedObjectButton" dojoType="dijit.form.Button" showlabel="false"
                   title="<?php echo i18n('showDetail')?>" class="notButton notButtonRounded"
                   iconClass="iconSearch22 iconSearch iconSize22 imageColorNewGui">
                   <script type="dojo/connect" event="onClick" args="evt">
                    showDetailLinkedObject();
                 </script>
                 </button>
               </div>
             </td>
            </tr>
            <tr><td>&nbsp;</td><td>&nbsp;</td></tr>
          </table>
         </form>
      </td>
    </tr>
    <tr>
      <td align="center">
        <input type="hidden" id="objectAction">
        <button class="mediumTextButton" dojoType="dijit.form.Button" type="button" onclick="dijit.byId('dialogObject').hide();">
          <?php echo i18n("buttonCancel");?>
        </button>
        <button class="mediumTextButton" dojoType="dijit.form.Button" type="submit" id="dialogObjectSubmit" onclick="protectDblClick(this);saveLinkObject();return false;">
          <?php echo i18n("buttonOK");?>
        </button>
      </td>
    </tr>
  </table>
</div>
<!-- END ADD BY Marc TABARY - 2017-02-23 - CHOICE OBJECTS LINKED BY ID TO MAIN OBJECT -->

<!-- BEGIN - ADD BY TABARY - NOTIFICATION SYSTEM -->
<!-- DIALOG - What is show on Change Status submit -->
<div id="dialogChangeStatus" dojoType="dijit.Dialog" title="<?php echo i18n("dialogChangeStatus");?>">
  <table>
    <tr>
      <td>
        <!-- FORM -->
        <form id="changeStatusForm" name="changeStatusForm" onSubmit="return false;">
          <!-- Store the class name of the object -->  
          <input id="objectClassChangeStatus" name="objectClassChangeStatus" type="hidden" value="" />
          <!-- Store the id of the instance of the object -->            
          <input id="idInstanceOfClassChangeStatus" name="idInstanceOfClassChangeStatus" type="hidden" value="" />
          <!-- Store the idStatus of the instance of the object -->  
          <input id="idStatusOfInstanceOfClassChangeStatus" name="idStatusOfInstanceOfClassChangeStatus" type="hidden" value="" />
          <!-- Store the idType of the instance of the object -->  
          <input id="idTypeOfInstanceOfClassChangeStatus" name="idTypeOfInstanceOfClassChangeStatus" type="hidden" value="" />
         <table>
            <tr>
              <td class="dialogLabel" >
                <label for="dialogChangeStatusList" ><?php echo i18n("colChangeStatus") ?>&nbsp;:&nbsp;</label>
              </td>
              <td>
                <table><tr><td>
                  <div id="dialogChangeStatusList" dojoType="dijit.layout.ContentPane" region="center">
                    <!-- Place of select construct dynamicaly by (dymanicListObject) -->  
                    <input id="changeStatusId" name="changeStatusId" type="hidden" value="" />
                  </div>
                </td></tr></table>
              </td>
            </tr>
            <tr><td>&nbsp;</td><td>&nbsp;</td></tr>
          </table>
         </form>
      </td>
    </tr>
    <tr>
      <td align="center">
        <input type="hidden" id="changeStatusAction">
        <button class="mediumTextButton" dojoType="dijit.form.Button" type="button" onclick="dijit.byId('dialogChangeStatus').hide();">
          <?php echo i18n("buttonCancel");?>
        </button>
        <button class="mediumTextButton" dojoType="dijit.form.Button" type="submit" id="dialogChangeStatusSubmit" onclick="protectDblClick(this);saveChangedStatusObject();return false;">
          <?php echo i18n("buttonOK");?>
        </button>
      </td>
    </tr>
  </table>
</div>
<!-- END - ADD BY TABARY - NOTIFICATION SYSTEM -->

<div id="dialogApprover" dojoType="dijit.Dialog" title="<?php echo i18n("dialogApprover");?>">
  <table>
    <tr>
      <td>
        <form id='approverForm' name='approverForm' onSubmit="return false;">
          <input id="approverRefType" name="approverRefType" type="hidden" value="" />
          <input id="approverRefId" name="approverRefId" type="hidden" value="" />
          <input id="approverItemId" name="approverItemId" type="hidden" value="" />
          <table>
            <tr>
              <td class="dialogLabel" >
                <label for="approverId" ><?php echo i18n("approver") ?>&nbsp;:&nbsp;</label>
              </td>
              <td>
                <table><tr><td>
                  <div id="dialogApproverList" dojoType="dijit.layout.ContentPane" region="center">
                    <input id="approverId" name="approverId" type="hidden" value="" />
                  </div>
                </td><td style="vertical-align: top">
                  <button id="approverIdDetailButton" dojoType="dijit.form.Button" showlabel="false"
                          title="<?php echo i18n('showDetail')?>"
                          iconClass="iconSearch22 iconSearch iconSize22 imageColorNewGui" class="notButton notButtonRounded">
                    <script type="dojo/connect" event="onClick" args="evt">
                      showDetailApprover();
                    </script>
                  </button>
                </td></tr></table>
              </td>
            </tr>
            <tr><td>&nbsp;</td><td>&nbsp;</td></tr>
          </table>
         </form>
      </td>
    </tr>
    <tr>
      <td align="center">
        <input type="hidden" id="approverAction">
        <button class="mediumTextButton" dojoType="dijit.form.Button" type="button" onclick="dijit.byId('dialogApprover').hide();">
          <?php echo i18n("buttonCancel");?>
        </button>
        <button class="mediumTextButton" dojoType="dijit.form.Button" type="submit" id="dialogApproverSubmit" onclick="protectDblClick(this);saveApprover();return false;">
          <?php echo i18n("buttonOK");?>
        </button>
      </td>
    </tr>
  </table>
</div>

<div id="dialogOrigin" dojoType="dijit.Dialog" title="<?php echo i18n("dialogOrigin");?>">
  <table>
    <tr>
      <td>
       <form id='originForm' name='originForm' onSubmit="return false;">
         <input id="originId" name="originId" type="hidden" value="" />
         <input id="originRefId" name="originRefId" type="hidden" value="" />
         <input id="originRefType" name="originRefType" type="hidden" value="" />
         <table>
           <tr>
             <td class="dialogLabel"  >
               <label for="originOriginType" ><?php echo i18n("originType") ?>&nbsp;<?php if (!isNewGui()) echo ':&nbsp;';?></label>
             </td>
             <td>
               <select dojoType="dijit.form.FilteringSelect" 
               <?php echo autoOpenFilteringSelect();?>
                id="originOriginType" name="originOriginType" 
                onchange="refreshOriginList();"
                class="input" value="" >
                 <?php htmlDrawOptionForReference('idOriginable', null, null, true);?>
               </select>
             </td>
           </tr>
           <tr><td>&nbsp;</td><td>&nbsp;</td></tr>
           <tr>
             <td class="dialogLabel" >
               <label for="OriginOriginId" ><?php echo i18n("originElement") ?>&nbsp;<?php if (!isNewGui()) echo ':&nbsp;';?></label>
             </td>
             <td>
               <table><tr><td>
               <div id="dialogOriginList" dojoType="dijit.layout.ContentPane" region="center">
                 <input id="originOriginId" name="originOriginId" type="hidden" value="" />
               </div>
               </td><td style="vertical-align: top;max-width:25px">
               <button id="originDetailButton" dojoType="dijit.form.Button" showlabel="false"
                 title="<?php echo i18n('showDetail')?>" class="notButton notButtonRounded"
                 iconClass="iconSearch22 iconSearch iconSize22 imageColorNewGui">
                 <script type="dojo/connect" event="onClick" args="evt">
                    showDetailOrigin();
                 </script>
               </button>
               </td></tr></table>
             </td>
           </tr>
           <tr><td>&nbsp;</td><td>&nbsp;</td></tr>
         </table>
        </form>
      </td>
    </tr>
    <tr>
      <td align="center">
        <input type="hidden" id="dialogOriginAction">
        <button class="mediumTextButton" dojoType="dijit.form.Button" type="button" onclick="dijit.byId('dialogOrigin').hide();">
          <?php echo i18n("buttonCancel");?>
        </button>
        <button class="mediumTextButton" dojoType="dijit.form.Button" type="submit" id="dialogOriginSubmit" onclick="protectDblClick(this);saveOrigin();return false;">
          <?php echo i18n("buttonOK");?>
        </button>
      </td>
    </tr>
  </table>
</div>

<div id="dialogCreationInfo" dojoType="dijit.Dialog" title="<?php echo i18n("dialogCreationInfo");?>">
  <table>
    <tr>
      <td>
        <table >
          <tr id="dialogCreationInfoCreatorLine">
            <td class="dialogLabel"  >
              <label for="dialogCreationInfoCreator" ><?php echo i18n("colIssuer") ?>&nbsp;:&nbsp;</label>
            </td>
            <td>
              <select dojoType="dijit.form.FilteringSelect" id="dialogCreationInfoCreator" 
              <?php echo autoOpenFilteringSelect();?>
              class="input" value="" >
                <?php htmlDrawOptionForReference('idUser', null, null, true);?>
              </select>
            </td>
          </tr>
          <tr><td>&nbsp;</td><td>&nbsp;</td></tr>
          <tr id="dialogCreationInfoDateLine">
            <td class="dialogLabel" >
              <label for="dialogCreationInfoDate" ><?php echo i18n("colCreationDate") ?>&nbsp;:&nbsp;</label>
            </td>
            <td>
              <div id="dialogCreationInfoDate" dojoType="dijit.form.DateTextBox" 
                 constraints="{datePattern:browserLocaleDateFormatJs}"
                 invalidMessage="<?php echo i18n('messageInvalidDate');?> " 
                 type="text" maxlength="10" 
                 style="width:100px; text-align: center;" class="input"
                 required="true" hasDownArrow="true" 
                 missingMessage="<?php echo i18n('messageMandatory',array('colDate'));?>" 
                 invalidMessage="<?php echo i18n('messageMandatory',array('colDate'));?>" 
                 >
              </div>
              <span id="dialogCreationInfoTimeLine">
              <div id="dialogCreationInfoTime" dojoType="dijit.form.TimeTextBox" 
                 invalidMessage="<?php echo i18n('messageInvalidTime');?>"
                 type="text" maxlength="8"
                 style="width:65px; text-align: center;" class="input"
                 required="true" 
                 >
              </div>
              </span>
            </td>
          </tr>
          <tr><td>&nbsp;</td><td>&nbsp;</td></tr>
        </table>
      </td>
    </tr>
    <tr>
      <td align="center">
        <button class="mediumTextButton" dojoType="dijit.form.Button" type="button" onclick="dijit.byId('dialogCreationInfo').hide();">
          <?php echo i18n("buttonCancel");?>
        </button>
        <button class="mediumTextButton" dojoType="dijit.form.Button" type="submit" id="dialogCreationInfoSubmit" onclick="protectDblClick(this);saveCreationInfo();return false;">
          <?php echo i18n("buttonOK");?>
        </button>
      </td>
    </tr>
  </table>
</div>

<div id="dialogAttachment" dojoType="dijit.Dialog" title="<?php echo i18n("dialogAttachment");?>"></div>
<form id='attachmentAckForm' name='attachmentAckForm'> 
   <input type='hidden' id="resultAck" name="resultAck" />
</form>

<form id='activityIdListForm' name='activityIdListForm'> 
   <input type='hidden' id="activityIdList" name="activityIdList" />
</form>
	   
<div id="dialogDocumentVersion" dojoType="dijit.Dialog" title="<?php echo i18n("dialogDocumentVersion");?>"></div>

<div id="dialogDependency" dojoType="dijit.Dialog" title="<?php echo i18n("dialogDependency");?>">
  <table>
    <tr>
      <td>
       <form dojoType="dijit.form.Form" id='dependencyForm' name='dependencyForm' onSubmit="return false;">
         <input id="dependencyId" name="dependencyId" type="hidden" value="" />
         <input id="dependencyRefType" name="dependencyRefType" type="hidden" value="" />
         <input id="dependencyRefId" name="dependencyRefId" type="hidden" value="" />
         <input id="dependencyType" name="dependencyType" type="hidden" value="" />
         <table>
           <tr>
             <td class="dialogLabel"  >
               <label for="dependencyRefTypeDep" ><?php echo i18n("linkType") ?>&nbsp;:&nbsp;</label>
             </td>
             <td>
               <select dojoType="dijit.form.FilteringSelect" 
               <?php echo autoOpenFilteringSelect();?>
                id="dependencyRefTypeDep" name="dependencyRefTypeDep" 
                onchange="refreshDependencyList();"
                missingMessage="<?php echo i18n('messageMandatory',array(i18n('linkType')));?>"
                class="input" value="" >
                 <?php htmlDrawOptionForReference('idDependable', null, null, true);?>
               </select>
             </td>
           </tr>
           <tr><td>&nbsp;</td><td>&nbsp;</td></tr>
         </table>
         <div id="dependencyAddDiv" >
         <table>
           <tr>
             <td class="dialogLabel" >
               <label for="dependencyRefIdDep" ><?php echo i18n("linkElement") ?>&nbsp;:&nbsp;</label>
             </td>
             <td><table><tr><td>
               <div id="dialogDependencyList" dojoType="dijit.layout.ContentPane" region="center" >
                 <input id="dependencyRefIdDep" name="dependencyRefIdDep" type="hidden" value="" />
               </div>
               </td><td style="vertical-align: top">
               <button id="dependencyDetailButton" dojoType="dijit.form.Button" showlabel="false"
                 title="<?php echo i18n('showDetail')?>"
                 iconClass="iconSearch22 iconSearch iconSize22 imageColorNewGui" class="notButton notButtonRounded">
                 <script type="dojo/connect" event="onClick" args="evt">
                    showDetailDependency();
                 </script>
               </button>
               </td></tr></table>
             </td>
           </tr>
           <tr><td>&nbsp;</td><td>&nbsp;</td></tr>
         </table>
         </div>
         <div id="dependencyEditDiv">
           <table>
             <tr>
               <td class="dialogLabel"  >
                 <label for="dependencyRefIdDepEdit" ><?php echo i18n("linkElement") ?>&nbsp;:&nbsp;</label>
               </td>
               <td>
                 <select dojoType="dijit.form.FilteringSelect" 
                 <?php echo autoOpenFilteringSelect();?>
                  id="dependencyRefIdDepEdit" name="dependencyRefIdDepEdit" 
                  class="input" value="" size="10">
                 </select>
               </td>
             </tr>
              <tr><td>&nbsp;</td><td>&nbsp;</td></tr>
           </table>  
         </div>
         <div id="dependencyDelayDiv">
	         <table>
	           <tr>
	             <td class="dialogLabel" >
	               <label for="dependencyDelay" ><?php echo i18n("colDependencyDelay");?>&nbsp;:&nbsp;</label>
	             </td>
	             <td><span class="nobr">
	               <input id="dependencyDelay" name="dependencyDelay" value="0" 
	                 dojoType="dijit.form.NumberTextBox" 
                   constraints="{min:-999, max:999}" 
	                 style="width:50px; text-align: center;" 
	                 missingMessage="<?php echo i18n('messageMandatory',array(i18n('colDependencyDelay')));?>" 
	                 required="true" />&nbsp;
	               <?php echo i18n('colDependencyDelayComment'); ?>
	               </span>
	             </td>
	           </tr>
	           <tr><td>&nbsp;</td><td>&nbsp;</td></tr>
	         </table>
          </div>
          <div id="dependencyTypeDiv">
	         <table>
	           <tr>
	             <td class="dialogLabel" >
	               <label for="dependencyType" ><?php echo i18n("colType");?>&nbsp;:&nbsp;</label>
	             </td>
	             <td><span class="nobr">
                <select dojoType="dijit.form.FilteringSelect" class="input" name="typeOfDependency" id="typeOfDependency"
                  <?php echo autoOpenFilteringSelect();?> style="width:115px;height:20px">
                  <?php $depType=array('E-S','E-E','S-S');
                  foreach ($depType as $type) {
                    $lib=( (pq_substr($type,0,1)=='E')?i18n('colEnd'):i18n('colStart') ).' - '.( (pq_substr($type,-1)=='E' )?i18n('colEnd'):i18n('colStart') );
                    echo "<option value='$type'>$lib</option>";
                  }?>
                </select>
                 </td>
	           </tr>
	           <tr><td>&nbsp;</td><td>&nbsp;</td></tr>
	         </table>
          </div>
          <!--KEVIN TICKET #2038 -->
          	<table>
							<tr>
								<td><label for="dependencyComment"><?php echo i18n("colComment");?>&nbsp;:&nbsp;</label></td>															
								<td><input id="dependencyComment" name="dependencyComment" value="" dojoType="dijit.form.Textarea" class="input"/></td>
							</tr>
							<tr><td>&nbsp;</td><td>&nbsp;</td></tr>
						</table>
					</form>
				</td>
			</tr>         
        </form>
      </td>
    </tr>
    <tr>
      <td align="center">
        <input type="hidden" id="dialogDependencyAction">
        <button class="mediumTextButton" dojoType="dijit.form.Button" type="button" onclick="dijit.byId('dialogDependency').hide();">
          <?php echo i18n("buttonCancel");?>
        </button>
        <button class="mediumTextButton" dojoType="dijit.form.Button" type="submit" id="dialogDependencySubmit" onclick="protectDblClick(this);saveDependency();return false;">
          <?php echo i18n("buttonOK");?>
        </button>
      </td>
    </tr>
  </table>
</div>

<div id="xdialogShowImage" dojoType="dojox.image.LightboxDialog" >
</div>
<form  method="POST" style="display:none" id="directAccessForm" action="../view/main.php">
  <input type="hidden" name="directAccessPage" id="directAccessPage" value="" />
  <input type="hidden" name="menuActualStatus" id="menuActualStatus" value="" />
  <input type="hidden" name="p1name" id="p1name" value="" />
  <input type="hidden" name="changeCurrentLocale" id="changeCurrentLocale" value="" />
  <input type="hidden" name="p1value" id="p1value" value="" />
</form>
<form id='favoriteForm' name='favoriteForm' onSubmit="return false;">
  <input type="hidden" id="page" name="page" value=""/>
  <input type="hidden" id="print" name="print" value=true />
  <input type="hidden" id="report" name="report" value=true />
  <input type="hidden" id="outMode" name="outMode" value='html' />
  <input type="hidden" id="reportName" name="reportName" value="test" />
</form>
<div id="deleteMultipleResultDiv" dojoType="dijit.layout.ContentPane" region="none" style="display:none"></div>
<div id="resultDivMain"           dojoType="dijit.layout.ContentPane" region="none" style="display:none"></div>
<div id="disconnectionMessage" dojoType="dijit.layout.ContentPane" region="none" class="resultDiv" style="display:none;opacity:1">
  <div id="disconnectionMessageText" style="text-align:center;cursor:pointer;" onClick="quitConfirmed=true;window.location = '../index.php';"></div>
</div>
<div id="textFullScreenCKdiv" style="width:300px;height:200px;position:absolute;display:none;" class="">
  <textarea style="width:100%; height:100%" name="textFullScreenCK" id="textFullScreenCK"></textarea>
</div>
<?php 
$proj=null;
if (sessionValueExists('project')) {
  $proj=getSessionValue('project');
} else {
  $defaultProject=Parameter::getUserParameter('defaultProject');
  if (is_numeric($defaultProject)) $proj=$defaultProject;
}
$idFavoriteProjectList = pq_trim(getSessionValue('idFavoriteProjectList'));
if($proj=="*" and $idFavoriteProjectList){
  $favoriteProjectArray = SqlList::getListWithCrit('FavoriteProjectItem', array('idFavoriteProjectList'=>$idFavoriteProjectList), 'idProject');
  $proj = implode(',', $favoriteProjectArray);
}
if ($proj=="*" or ! $proj) $proj=null;
?>
<input type="hidden" id="planLastSavedClass" name="planLastSavedClass" value="" />
<input type="hidden" id="planLastSavedId" name="planLastSavedId" value="" />    
<input type="hidden" id="planSelectedProjects" name="planSelectedProjects" value="<?php echo ($proj)?$proj:' ';?>" />
<input type="hidden" id="planStartDate" name="planStartDate" value="<?php echo date('Y-m-d');?>" />
</body>
</html>
