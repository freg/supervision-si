<?php
/*** COPYRIGHT NOTICE *********************************************************
 *
 * Copyright 2009-2017 ProjeQtOr - Pascal BERNARD - support@projeqtor.org
 * Contributors : -
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
 * Presents the list of objects of a given class.
 *
 */
require_once "../tool/projeqtor.php";
scriptLog('   ->/view/planningList.php');
$planningType='planning';
require_once '../tool/planningListFunction.php';
$startDate=date('Y-m-d');
$endDate=null;
$user=getSessionUser();
$saveDates=false;
$projectDate=Parameter::getUserParameter('projectDate');
$paramStart=SqlElement::getSingleSqlElementFromCriteria('Parameter',array('idUser'=>$user->id,'idProject'=>null,'parameterCode'=>'planningStartDate'));
if ($paramStart->id) {
  $startDate=$paramStart->parameterValue;
  $saveDates=true;
}
$paramEnd=SqlElement::getSingleSqlElementFromCriteria('Parameter',array('idUser'=>$user->id,'idProject'=>null,'parameterCode'=>'planningEndDate'));
if ($paramEnd->id) {
  $endDate=$paramEnd->parameterValue;
  $saveDates=true;
}
if($projectDate){
  $saveDates=false;
  $startDate=null;
  $endDate=null;
}else{
  $startDate=date('Y-m-d');
}
//$saveShowWbsObj=SqlElement::getSingleSqlElementFromCriteria('Parameter',array('idUser'=>$user->id,'idProject'=>null,'parameterCode'=>'planningShowWbs'));
//$saveShowWbs=$saveShowWbsObj->parameterValue;
$saveShowWbs=Parameter::getUserParameter('planningShowWbs');
//$saveShowResourceObj=SqlElement::getSingleSqlElementFromCriteria('Parameter',array('idUser'=>$user->id,'idProject'=>null,'parameterCode'=>'planningShowResource'));
//$saveShowResource=$saveShowResourceObj->parameterValue;
$saveShowResource=Parameter::getUserParameter('planningShowResource');
//$saveShowWorkObj=SqlElement::getSingleSqlElementFromCriteria('Parameter',array('idUser'=>$user->id,'idProject'=>null,'parameterCode'=>'planningShowWork'));
//$saveShowWork=$saveShowWorkObj->parameterValue;
$saveShowWork=Parameter::getUserParameter('planningShowWork');
$showColorActivity=Parameter::getUserParameter('showColorActivity');
$showColorTypeActivity=Parameter::getUserParameter('showColorTypeActivity');
$showHatchOnPlanningBar=Parameter::getUserParameter('showHatchOnPlanningBar');
//$saveShowClosedObj=SqlElement::getSingleSqlElementFromCriteria('Parameter',array('idUser'=>$user->id,'idProject'=>null,'parameterCode'=>'planningShowClosed'));
//$saveShowClosed=$saveShowClosedObj->parameterValue;
$saveShowClosed=Parameter::getUserParameter('planningShowClosed');
$archiveMode=(sessionValueExists('projectSelectorShowIdle') and getSessionValue('projectSelectorShowIdle')==1)?1:0;
if ($archiveMode) {
  $saveShowClosed=1;
}
$saveShowProjectModel=Parameter::getUserParameter('showProjectModel');
$showTaskNamePlanning=Parameter::getUserParameter('showTaskNameOnPlanningBar');
if (is_array( getSessionUser()->_arrayFilters)) {
  if (pq_array_key_exists('Planning', getSessionUser()->_arrayFilters)) {
    $arrayFilter=getSessionUser()->_arrayFilters['Planning'];
    foreach ($arrayFilter as $filter) {
      if ($filter['sql']['attribute']=='idle' and $filter['sql']['operator']=='>=' and $filter['sql']['value']=='0') {
        $saveShowClosed=1;
      }
    }
  }
}
if ($saveShowClosed==1) {
  $_REQUEST['idle']=true;
}
$automaticRunPlanning=Parameter::getUserParameter('automaticRunPlanning');

$canPlan=false;
$right=SqlElement::getSingleSqlElementFromCriteria('habilitationOther', array('idProfile'=>$user->idProfile, 'scope'=>'planning'));
if ($right) {
  $list=new ListYesNo($right->rightAccess);
  if ($list->code=='YES') {
    $canPlan=true;
  }
}
$canAutomaticCal=false;
$rightAutomaticCal=SqlElement::getSingleSqlElementFromCriteria('habilitationOther', array('idProfile'=>$user->idProfile, 'scope'=>'enableAutomaticCal'));
if ($rightAutomaticCal) {
  $listAutomaticCal=new ListYesNo($rightAutomaticCal->rightAccess);
  if ($listAutomaticCal->code=='YES') {
    $canAutomaticCal=true;
  }
}
$plannableProjectsList=getSessionUser()->getListOfPlannableProjects();
// $plannedElement = new PlanningElement();
// $plannedProjectList = $plannedElement->getSqlElementsFromCriteria(array("refType"=>"Project"));

// foreach ($plannedProjectList as $plannedProject){
//   if($plannedProject->validatedStartDate < $startDate and $plannedProject->validatedStartDate != ''){
//     $startDate = $plannedProject->validatedStartDate;
//   }
//   if($plannedProject->validatedEndDate > $endDate and $plannedProject->validatedEndDate != ''){
//   	$endDate = $plannedProject->validatedEndDate;
//   }
// }

if (! $canPlan) {
  $canPlan=(count($plannableProjectsList)>0)?true:false;
}

$proj=null;
if (sessionValueExists('project')) {
  $proj=getSessionValue('project');
  if(pq_strpos($proj, ",")){
  	$proj="*";
  }
}
if ($proj=='*' or !$proj) {
  $proj=null;
}

$displayWidthPlan="9999";
if (RequestHandler::isCodeSet('destinationWidth')) {
  $displayWidthPlan=RequestHandler::getNumeric('destinationWidth');
}
//florent
$showValidationButton=false;
$accessValidatePlanning=false;
$lstUserP=$user->getAllProfiles();
foreach ($lstUserP as $prof){
  $priority=SqlElement::getSingleSqlElementFromCriteria('HabilitationOther',array('idProfile'=>$prof,'scope'=>'validatePlanning'));
  if($priority->rightAccess!=1){
     continue;
  }else{
    $accessValidatePlanning=true;
  }
  $showValidationButton=true;
  break;
}

$hideTimeline = Parameter::getUserParameter('hideTimeline');
$displayTimeline=($hideTimeline)?'none':'block';
$tlItem = new TimelineItem();
$timeline = $tlItem->getSqlElementsFromCriteria(array('idUser'=>$user->id));
$displayTimeline = (count($timeline)>0 and $displayTimeline != 'none')?'block':'none;';
//$objectClass='Task';
//$obj=new $objectClass;
$lockSaveRefresh = (getSessionValue('lockPlanningSaveRefresh') and getSessionValue('lockPlanningSaveRefresh') == '1')?1:0;
$paramHistoryVisible=Parameter::getUserParameter('displayHistory');
$displayHistory = ($paramHistoryVisible == 'NO')?false:true;
$planningZoom=Parameter::getUserParameter('planningZoom');
if ($planningZoom!='75' and $planningZoom!='125') {
  $planningZoom='100';
}
$planningZoomRatio=((int)$planningZoom)/100;
$planningTopHeight=round(45*$planningZoomRatio);
$planningRightTopOffset=round(-10*$planningZoomRatio);
?>
  
<div id="mainPlanningDivContainer" dojoType="dijit.layout.BorderContainer">
	<div dojoType="dijit.layout.ContentPane" region="top" id="listHeaderDiv" 
	 style="z-index: 3; position: relative; overflow: visible !important;padding-bottom:5px;min-height: 34px;">
	  <script type="dojo/method" event="onUnload" >
      if (! drawGanttInProgress) resetPlanningFieldDescription();  
      return true;
    </script>
		<table width="100%" class="listTitle" style="height:auto">
		  <tr height="27px" >
		    <td style="vertical-align:top; min-width:100px; width:15%">
		      <table >
    		    <tr height="32px">
      		    <td width="50px" style="min-width:50px;<?php if (isNewGui()) echo 'position:relative;top:2px';?>" align="center">
                <?php echo formatIcon('Planning', 32, null, true);?>
              </td>
              <td style="min-width:100px" ><span class="title" style="max-width:250px;white-space:normal"><?php echo i18n('menuPlanning');?></span></td>
      		  </tr>
      		  <?php if (!isNewGui()) {?>
      		  <tr><td>
  		        <?php drawOptionCriticalPath();?>
            </td></tr>
            <?php }?>       		  
    		  </table>
		    </td>
		    <td>   
		      <form dojoType="dijit.form.Form" id="listForm" action="" method="" style="">
		      	<?php 
		        $objectClass=(RequestHandler::isCodeSet('objectClass'))?RequestHandler::getClass('objectClass'):'';
		        $objectId=(RequestHandler::isCodeSet('objectId'))?RequestHandler::getId('objectId'):'';?>
		        <input type="hidden" id="planningType" name="planningType" value="<?php echo $planningType;?>" /> 
		        <input type="hidden" id="objectClass" name="objectClass" value="<?php echo $objectClass;?>" /> 
		        <input type="hidden" id="objectId" name="objectId" value="<?php echo $objectId;?>" />
		        <input type="hidden" id="idProjectForCalendar" name="idProjectForCalendar" value="<?php echo Project::getIdProjectForIdCalendarDefinition();?>" />
		        <?php if (!isNewGui()) { // =========================================================== NOT NEW GUI?>
		        <table style="width: 100%;">
		          <tr>
		            <td style="width:70px; position:relative;">

		              &nbsp;&nbsp;&nbsp;
                  <?php if ($canPlan) { ?>
                  <?php drawButtonPlan(); ?>
                    <?php if ($canAutomaticCal) { ?>
                      <?php drawOptionAutomatic();?>
                    <?php }?>
                  <?php }?>
		            </td>
		            <td style="white-space:nowrap;width:<?php echo ($displayWidthPlan>1030)?240:150;?>px">
		              <table align="right" style="margin:7px">
                    <tr>
                      <td align="right" style="white-space:nowrap">&nbsp;&nbsp;&nbsp;<?php echo ($displayWidthPlan>1030)?i18n("displayStartDate"):i18n("from");?>&nbsp;&nbsp;</td><td>
                        <?php drawFieldStartDate();?>
                      </td>
                    </tr>
                    <tr>
                      <td align="right" style="white-space:nowrap">&nbsp;&nbsp;&nbsp;<?php echo ($displayWidthPlan>1030)?i18n("displayEndDate"):i18n("to");?>&nbsp;&nbsp;</td>
                      <td>
                      <?php drawFieldEndDate();?>

                      </td>
                    </tr>
                  </table>
		            </td>
                <td style="width:250px;">
                  <table >
                    <tr>
                    <td style="white-space:nowrap;padding-right:10px;position:relative;top:4px">
                    <?php drawOptionAllProject();?>
                            
                     </td>
                      <td colsan="3">
                        <?php drawButtonsPlanning();?>
                      </td>
                    </tr>
                    <tr>
                    <td style="white-space:nowrap;padding-right:10px;position:relative;top:-4px">
                       <?php drawOptionSaveDates();?>
                          </td>
                      <td colspan="3">
                       <?php drawButtonsDefault();?>
                      </td>
                    </tr>
                  </table>
                </td>
		            <td style="">
                  <?php drawOptionBaseline();?>
                </td>
                
		            <td style="text-align: right; align: right;">
                  <?php drawOptionsDisplay();?>
		            </td>
		          </tr>
		        </table>
		        <?php }?>    
		        <?php if (isNewGui()) { // ========================================================= NEW GUI?>
		        <table style="width: 100%;">
		          <tr>
		            <td style="width:90%;text-align:right;white-space:nowrap;vertical-align:middle;">
                  <?php
                  $planningSearchIdDisplay=(sessionValueExists('planningSearchIdQuickSwPlanning') and getSessionValue('planningSearchIdQuickSwPlanning')=='on')?'inline-flex':'none';
                  $planningSearchNameDisplay=(sessionValueExists('planningSearchNameQuickSwPlanning') and getSessionValue('planningSearchNameQuickSwPlanning')=='on')?'inline-flex':'none';
                  ?>
                  <span id="planningSearchIdBarSpan" style="display:<?php echo $planningSearchIdDisplay;?>;align-items:center;gap:5px;vertical-align:middle;margin-right:8px;">
                    <span style="font-size:90%;text-transform:uppercase;"><?php echo i18n("colId");?></span>
                    <div title="<?php echo i18n('filterOnId')?>" style="width:95px;" class="filterField rounded" dojoType="dijit.form.TextBox"
                      type="text" id="planningSearchIdBar" name="planningSearchIdBar">
                      <script type="dojo/method" event="onKeyUp" >
                        planningSearchInputKeyUp(event, 'id', 'bar');
                      </script>
                      <script type="dojo/method" event="onKeyDown" >
                        return planningSearchInputKeyDown(event, 'id', 'bar');
                      </script>
                    </div>
                    <span id="planningSearchIdBarCount" style="font-size:85%;min-width:28px;">0/0</span>
                    <div class="iconDown16 iconDown imageColorNewGui iconSize16" style="cursor:pointer;transform: rotate(180deg);" title="<?php echo i18n('previous'); ?>" onclick="planningSearchMove('id', -1);"></div>
                    <div class="iconDown16 iconDown imageColorNewGui iconSize16" style="cursor:pointer;" title="<?php echo i18n('next'); ?>" onclick="planningSearchMove('id', 1);"></div>
                  </span>
                  <span id="planningSearchNameBarSpan" style="display:<?php echo $planningSearchNameDisplay;?>;align-items:center;gap:5px;vertical-align:middle;margin-right:8px;">
                    <span style="font-size:90%;"><?php echo ucfirst(i18n("colName"));?></span>
                    <div title="<?php echo i18n('filterOnName')?>" style="width:170px;" class="filterField rounded" dojoType="dijit.form.TextBox"
                      type="text" id="planningSearchNameBar" name="planningSearchNameBar">
                      <script type="dojo/method" event="onKeyUp" >
                        planningSearchInputKeyUp(event, 'name', 'bar');
                      </script>
                      <script type="dojo/method" event="onKeyDown" >
                        return planningSearchInputKeyDown(event, 'name', 'bar');
                      </script>
                    </div>
                    <span id="planningSearchNameBarCount" style="font-size:85%;min-width:28px;">0/0</span>
                    <div class="iconDown16 iconDown imageColorNewGui iconSize16" style="cursor:pointer;transform: rotate(180deg);" title="<?php echo i18n('previous'); ?>" onclick="planningSearchMove('name', -1);"></div>
                    <div class="iconDown16 iconDown imageColorNewGui iconSize16" style="cursor:pointer;" title="<?php echo i18n('next'); ?>" onclick="planningSearchMove('name', 1);"></div>
                  </span>
                </td>
		            <td style="position:relative; min-width:118px;">
		              <div style="position:absolute; top:1.5px; right:6px; display:flex; align-items:center; gap:5px;">
                    <span style="font-size:90%;"><?php echo i18n('printZoom')?></span>
                    <select id="planningZoomSelect" name="planningZoomSelect" class="comboButton" dojoType="dijit.form.FilteringSelect" style="width:75px;">
                      <script type="dojo/method" event="onChange" >
                        JSGantt.changePlanningZoom(this.value);
                      </script>
                      <option value="75" <?php echo ($planningZoom=='75')?'selected="selected"':'';?>>75%</option>
                      <option value="100" <?php echo ($planningZoom=='100')?'selected="selected"':'';?>>100%</option>
                      <option value="125" <?php echo ($planningZoom=='125')?'selected="selected"':'';?>>125%</option>
                    </select>
                  </div>
                </td>
		            <td style="position:relative; min-width:30px">
		              <div style="position:absolute; top:4px"> 
		                <button id="todayPlanningScroll" dojoType="dijit.form.Button" 
                          title="<?php echo i18n('gotoPlanningScroll');?>" class="buttonIconNewGui detailButton"
                          iconClass="dijitIcon iconToday iconSize22 " >
                          <script type="dojo/connect" event="onClick" args="evt">
                            GotoPlanningToday();
                          </script>
		                </button>
		              </div>
		            </td>
                <?php if ($canPlan) { ?>
		            <td style="width:auto;position:relative;min-width:108px;">
		              <div id="predecessorSequence" class="dependencySequence" style="left:0px;"></div>
		              <div class="iconSucessorPredecessor iconSize60 imageColorNewGuiNoSelection">
		                <div title="<?php echo i18n('helpPredecessorButton');?>" id="predecessor" class="dependencyPredecessor" onclick="drawButtonPredecessorElement();" style="left: -4px;"></div>
                    <div title="<?php echo i18n('helpSuccessorButton');?>" id="successor" class="dependencySuccessor" onclick="drawButtonSuccessorElement();" style="right: -4px;"></div>
		              </div>
		              <div id="successorSequence" class="dependencySequence" style="left:84px;"></div>
		              <div id="predecessorSuccessorReset" class="predecessorSuccessorReset" onClick="predecessorSuccessorReset()">
		                <img src="css/images/tabClose.gif" />
		              </div>
		            </td>
		            
                <td style="width:auto;position:relative;min-width:41px;top:3px;">
                  <div title="<?php echo i18n('helpCriticalPathFilterButton');?>" id="criticalPathFilterButton" class="iconCriticalPathFilter iconSize24 imageColorNewGui"style="cursor:pointer;" onclick="toggleCriticalPathFilter();">
                  </div>
                </td>
		            
		            <td id="lockSaveRefreshButtonTd" style="min-width: 25px;position:relative;">
		              <div style="position:absolute;top:2px;right:0px">
                        <button id="lockSaveRefreshButton" dojoType="dijit.form.Button" showlabel="false"
                          title="<?php echo i18n('lockSaveRefreshButton');?>" class="buttonIconNewGui detailButton"
                          iconClass="dijitIcon <?php echo ($lockSaveRefresh != 1)?'iconDeLock':'iconLock';?> iconSize22" >
                          <script type="dojo/connect" event="onClick" args="evt">
                            lockSaveRefresh();
                            return false;
                          </script>
                        </button>
                      </div> 
                    </td>		            
		            <td style="width:70px; min-width: 50px;position:relative;">
		              &nbsp;&nbsp;&nbsp;
		                <div style="position:absolute;top:-2px;right:10px">
                    <?php drawButtonPlan(); ?>
                    </div>    
		            </td>
		            <?php if ($canAutomaticCal){?>
		              <td style="width:70px; min-width:22px; position:relative;padding-right:20px;">
                        <?php drawOptionAutomatic();?>
                	  </td>
                  	<?php } ?>
                <?php } ?>
                <td style="width:150px;text-aliogn:right;">
                       <?php drawButtonsDefault();?>
                </td>
                <td style="width:50px;padding-right:10px;">
                        <div dojoType="dijit.form.DropDownButton"							    
							             id="extraButtonPlanning" jsId="extraButtonPlanning" name="extraButtonPlanning" 
							             showlabel="false" class="comboButton" iconClass="dijitButtonIcon dijitButtonIconExtraButtons" class="detailButton" 
							             title="<?php echo i18n('extraButtons');?>">
                           <div dojoType="dijit.TooltipDialog" class="white" id="extraButtonImputationDialog"
							              style="position: absolute; top: 50px; right: 40%">        
                               <table>
                                 <tr style="width:100%;">
                                  <td style="padding-right:10px;"><?php drawDisplayField('planning');?></td>
                                  <td style="vertical-align:top;">
                                    <table>
                                    <?php
                                    if ($accessValidatePlanning==true){ ?>
                                      <tr><td style="width:100%;"><?php drawDisplayValidatedPlanning();?></td></tr>
                                    <?php } ?>
                                      <tr><td style="padding-top:10px;width:100%;"><?php drawDisplayBaseline();?></td></tr>
                                      <tr><td style="padding-top:10px;width:100%;"><?php drawTimeLine();?></td></tr>
                                      <tr><td style="padding-top:10px;width:100%;"><?php drawExports();?></td></tr>
                                    </table>
                                  </td>
		                             </tr>
		                           </table>
                           </div>
                        </div>
                </td>
                <td style="width:50px;padding-right:10px">
                  <div dojoType="dijit.layout.ContentPane"  id="menuLayoutScreen" class="pseudoButton" style="position:relative;overflow:hidden;width:50px;min-width:55px;">
                    <div dojoType="dijit.form.DropDownButton" id="menuLayoutScreenButton" title="<?php echo i18n("changeScreenLayout");?>"  style="display: table-cell;<?php if (!isNewGui()) {?>background-color: #D3D3D3;<?php }?>vertical-align: middle;position:relative;min-width:50px;top:-3px" >
            			    <table style="width:100%">
                			  <tr>
                  				<td style="width:24px;padding-top:2px;">
                  				  <div class="<?php if (!isNewGui()) echo 'iconChangeLayout22' ;?> iconChangeLayout iconSize22 <?php if(isNewGui()) echo 'imageColorNewGui';?>">&nbsp;</div> 
                  				</td>
                  			  <td style="vertical-align:middle;">&nbsp;</td>
                			  </tr>
            			    </table>
            			    <div id="drawMenuLayoutScreen" dojoType="dijit.TooltipDialog"
                         style="max-width:90px; overflow-x:hidden;width:90px; ">
                         <?php include "menuLayoutScreen.php" ?>           
                        </div> 
            		</div>
                  </div>
                </td>
              </tr>

	        </table>
		        <?php }?>    
		      </form>
		    </td>
		  </tr>
		</table>
		<div dojotype="dijit.layout.ContentPane" region="top" style="width:100%;height: 100%;overflow: hidden;display:<?php echo $displayTimeline;?>;"
          class="ganttDiv" id="timelineGanttDiv" name="timelineGanttDiv" jsId="timelineGanttDiv">
                  <?php
                      include '../tool/jsonTimeline.php';
                  ?>
        </div>
		<div dojoType="dijit.layout.ContentPane" id="planningJsonData" jsId="planningJsonData" 
     style="display: none">
          
		  <?php
		       if ($saveShowResource) $_REQUEST['showResource']='on';
		       if ($saveShowProjectModel) $_REQUEST['showProjectModel']='on';
		       $length=Parameter::getPlanningPageLineCount();
		       setSessionValue('showAllGanttLines', 'false');
		       $_REQUEST['jsonQueryStartLine']=0;
		       $_REQUEST['jsonQueryNbLines']=$length;
		       $_REQUEST['jsonQueryHiddenLines']=0;
            include '../tool/jsonPlanning.php';
          ?>
		</div>
	</div>
	<div dojoType="dijit.layout.ContentPane" region="center" id="gridContainerDiv" >
   <div id="submainPlanningDivContainer" dojoType="dijit.layout.BorderContainer"
    style="border-top:1px solid #ffffff;">
    <?php $leftPartSizeReference=Parameter::getUserParameter('planningLeftSizeUnzoomed');
          if ($leftPartSizeReference) {
            $leftPartSize=round(((float)$leftPartSizeReference)*$planningZoomRatio).'px';
          } else {
            $leftPartSize=Parameter::getUserParameter('planningLeftSize');
            if (! $leftPartSize) {$leftPartSize='325px';}
          } ?>
	   <div dojoType="dijit.layout.ContentPane" region="left" splitter="true" 
      style="width:<?php echo $leftPartSize;?>; height:100%; overflow-x:scroll; overflow-y:hidden;" class="ganttDiv" 
      id="leftGanttChartDIV" name="leftGanttChartDIV"
      onScroll="showGanttLinesVisible();this.scrollTop=0;JSGantt.syncPlanningScroll();" 
      onWheel="leftMouseWheel(event);">
      <script type="dojo/method" event="onUnload" >
         if (! JSGantt.planningZoomChangeInProgress) {
           setTimeout("JSGantt.savePlanningLeftSize();",1);
         }
         return true;
      </script>
     </div>
     <div dojoType="dijit.layout.ContentPane" region="center" 
      style="height:100%; overflow:hidden;" class="ganttDiv" 
      id="GanttChartDIV" name="GanttChartDIV" >
       <div id="mainRightPlanningDivContainer" dojoType="dijit.layout.BorderContainer" style="z-index:-4;">
         <div dojoType="dijit.layout.ContentPane" region="top" 
          style="width:100%; height:<?php echo $planningTopHeight;?>px; overflow:hidden;" class="ganttDiv"
          id="topGanttChartDIV" name="topGanttChartDIV">
         </div>
         <div dojoType="dijit.layout.ContentPane" region="center" 
          style="z-index:-4; width:100%; overflow-x:scroll; overflow-y:scroll; position: relative; top:<?php echo $planningRightTopOffset;?>px;" class="ganttDiv"
          id="rightGanttChartDIV" name="rightGanttChartDIV"
          onScroll="showGanttLinesVisible();JSGantt.syncPlanningScroll();"
         >
         </div>
       </div>
     </div>
   </div>
     <div class="contextMenuClass comboButtonInvisible" dojoType="dijit.form.DropDownButton" id="planningContextMenu" name="planningContextMenu" style="position:absolute;top:0px;left:0px;width:0px;height:0px;overflow:hidden;">
      <div dojoType="dijit.TooltipDialog" id="dialogPlanningContextMenu" tabindex="0" onMouseEnter="clearTimeout(hidePlanningContextMenu);" onMouseLeave="JSGantt.hideMenu(200)" onfocusout="hideElementOnFocusOut(null, JSGantt.hideMenu(200))">
        <input type="hidden" id="contextMenuRefId" name="contextMenuRefId" value="" />
        <input type="hidden" id="contextMenuRefType" name="contextMenuRefType" value="" />
        <table style="width:100%;height:100%">
          <tr id="cm_openFromPlanning" class="contextMenuRow" onClick="">
            <td style="padding-top:5px;padding-bottom:5px;"><?php echo formatSmallButton('View', false , false);?></td>
            <td style="padding-left:10px;padding-top:5px;padding-bottom:5px;" id="cm_openFromPlanning_label"><?php echo i18n('contextMenuButtonOpen');?></td>
          </tr>
          
         <!-- #11177 -->
          <tr id="cm_gotoListFromPlanning" class="contextMenuRow" onClick="">
            <td style="padding-top:5px;padding-bottom:5px;"><?php echo formatSmallButton('Goto', true , false);?></td>
            <td style="padding-left:10px;padding-top:5px;padding-bottom:5px;" id="cm_gotoListFromPlanning_label"><?php echo i18n('contextMenuButtonGotoList');?></td>
          </tr>
          <!-- #11179 -->
          <tr id="cm_filterListFromPlanning" class="contextMenuRow" onClick="">
            <td style="padding-top:5px;padding-bottom:5px;"><?php echo formatSmallButton('Goto', true , false);?></td>
            <td style="padding-left:10px;padding-top:5px;padding-bottom:5px;" id="cm_filterListFromPlanning_label"><?php echo i18n('contextMenuButtonFilterInList');?></td>
          </tr>
          
          <tr id="cm_closeFromPlanning" class="contextMenuRow" onClick="">
            <td style="padding-top:5px;padding-bottom:5px;"><?php echo formatSmallButton('Cancel', false , false);?></td>
            <td style="padding-left:10px;padding-top:5px;padding-bottom:5px;" id="cm_closeFromPlanning_label"><?php echo i18n('contextMenuButtonClose');?></td>
          </tr>
          <tr id="cm_editOnlineFromPlanning" class="contextMenuRow" onClick="">
            <td style="padding-top:5px;padding-bottom:5px;"><?php echo formatSmallButton('Edit', false , false);?></td>
            <td style="padding-left:10px;padding-top:5px;padding-bottom:5px;" id="cm_editOnlineFromPlanning_label"><?php echo i18n('contextMenuButtonEditOnline');?></td>
          </tr>
          <tr id="cm_editFromPlanning" class="contextMenuRow" onClick="">
            <td style="padding-top:5px;padding-bottom:5px;"><?php echo formatSmallButton('Edit', false , false);?></td>
            <td style="padding-left:10px;padding-top:5px;padding-bottom:5px;" id="cm_editFromPlanning_label"><?php echo i18n('contextMenuButtonEdit');?></td>
          </tr>
          <tr id="cm_editAssignmentFromPlanning" class="contextMenuRow" onClick="">
            <td style="padding-top:5px;padding-bottom:5px;"><?php echo formatSmallButton('Assignment', false , false);?></td>
            <td style="padding-left:10px;padding-top:5px;padding-bottom:5px;" id="cm_editAssignmentFromPlanning_label"><?php echo i18n('contextMenuButtonAssignment');?></td>
            <script type="dojo/connect" event="onClick" args="evt">
            </script>
          </tr>
          <tr id="cm_editAffectationFromPlanning" class="contextMenuRow" onClick="">
            <td style="padding-top:5px;padding-bottom:5px;"><?php echo formatSmallButton('Affectation', false , false);?></td>
            <td style="padding-left:10px;padding-top:5px;padding-bottom:5px;" id="cm_editAffectationFromPlanning_label"><?php echo i18n('contextMenuButtonAllocation');?></td>
            <script type="dojo/connect" event="onClick" args="evt">
            </script>
          </tr>
          <tr id="cm_addFromPlanning" class="contextMenuRow" onClick="">
            <td style="padding-top:5px;padding-bottom:5px;"><?php echo formatSmallButton('Add', false , false);?></td>
            <td style="padding-left:10px;padding-top:5px;padding-bottom:5px;" id="cm_addFromPlanning_label"><?php echo i18n('contextMenuButtonNew');?></td>
          </tr>
          <tr id="cm_copyFromPlanning" class="contextMenuRow" onClick="">
            <td style="padding-top:5px;padding-bottom:5px;"><?php echo formatSmallButton('Copy', false , false);?></td>
            <td style="padding-left:10px;padding-top:5px;padding-bottom:5px;" id="cm_copyFromPlanning_label"><?php echo i18n('contextMenuButtonCopy');?></td>
          </tr>
          
          <tr id="cm_copyPasteFromPlanning" class="contextMenuRow" onClick="">
            <td style="padding-top:5px;padding-bottom:5px;"><?php echo formatSmallButton('Copy', false , false);?></td>
            <td style="padding-left:10px;padding-top:5px;padding-bottom:5px;" id="cm_copyPasteFromPlanning_label"><?php echo i18n('contextMenuButtonCopyPaste');?></td>
          </tr>
          
          <tr id="cm_splitFromPlanning" class="contextMenuRow" onClick="">
            <td style="padding-top:5px;padding-bottom:5px;"><?php echo formatSmallButton('Split', false , false);?></td>
            <td style="padding-left:10px;padding-top:5px;padding-bottom:5px;" id="cm_splitFromPlanning_label"><?php echo i18n('contextMenuButtonSplit');?></td>
          </tr>
          <tr id="cm_removeFromPlanning" class="contextMenuRow" onClick="">
            <td style="padding-top:5px;padding-bottom:5px;"><?php echo formatSmallButton('Remove', false , false);?></td>
            <td style="padding-left:10px;padding-top:5px;padding-bottom:5px;" id="cm_removeFromPlanning_label"><?php echo i18n('contextMenuButtonDelete');?></td>
            <script type="dojo/connect" event="onClick" args="evt">
            </script>
          </tr>
          <tr id="cm_printFromPlanning" class="contextMenuRow" onClick="">
            <td style="padding-top:5px;padding-bottom:5px;"><?php echo formatSmallButton('Print', true , false);?></td>
            <td style="padding-left:10px;padding-top:5px;padding-bottom:5px;" id="cm_printFromPlanning_label"><?php echo i18n('contextMenuButtonPrint');?></td>
          </tr>
          <tr id="cm_pdfFromPlanning" class="contextMenuRow" onClick="">
            <td style="padding-top:5px;padding-bottom:5px;"><?php echo formatSmallButton('Pdf', false , false);?></td>
            <td style="padding-left:10px;padding-top:5px;padding-bottom:5px;"><?php echo ucfirst(i18n('reportPrintPdf'));?></td>
          </tr>
          <tr id="cm_emailFromPlanning" class="contextMenuRow" onClick="" >
            <td style="padding-top:5px;padding-bottom:5px;"><?php echo formatSmallButton('Email', false, false);?></td>
            <td style="padding-left:10px;padding-top:5px;padding-bottom:5px;" id="cm_emailFromPlanning_label"><?php echo i18n('contextMenuButtonMail');?></td>
          </tr>
          <tr id="cm_successorFromPlanning" class="contextMenuRow" onClick="" >
            <td style="padding-top:5px;padding-bottom:5px;"><?php echo formatSmallButton('Successor', false, false);?></td>
            <td style="padding-left:10px;padding-top:5px;padding-bottom:5px;"><?php echo i18n('contextMenuIndentButton');?></td>
          </tr>
          <tr id="cm_predecessorFromPlanning" class="contextMenuRow" onClick="" >
            <td style="padding-top:5px;padding-bottom:5px;"><?php echo formatSmallButton('Predecessor', false, false);?></td>
            <td style="padding-left:10px;padding-top:5px;padding-bottom:5px;"><?php echo i18n('contextMenuOutdentButton');?></td>
          </tr>
          <?php if($displayHistory){?>
          <tr id="cm_historyFromPlanning" class="contextMenuRow" onClick="" >
            <td style="padding-top:5px;padding-bottom:5px;"><?php echo formatSmallButton('History', false, false);?></td>
            <td style="padding-left:10px;padding-top:5px;padding-bottom:5px;"><?php echo i18n('dialogHistory');?></td>
          </tr>
          <?php }?>
          <tr id="cm_sectionTimeline"><td colspan="2"><hr></td></tr>
          <tr id="cm_addToTimeline" class="contextMenuRow" onClick="">
            <td style="padding-top:5px;padding-bottom:5px;"><?php echo formatSmallButton('Add', false , false);?></td>
            <td style="padding-left:10px;padding-top:5px;padding-bottom:5px;"><?php echo i18n('addItemToTimeline');?></td>
          </tr>
          <tr id="cm_removeFromTimeline" class="contextMenuRow" onClick="">
            <td style="padding-top:5px;padding-bottom:5px;"><?php echo formatSmallButton('Remove', false , false);?></td>
            <td style="padding-left:10px;padding-top:5px;padding-bottom:5px;"><?php echo i18n('removeItemFromTimeline');?></td>
          </tr>
        </table>
      </div>
    </div>
  </div>
</div>
