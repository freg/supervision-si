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
scriptLog('   ->/view/documentExplorerList.php');
$planningType='planning';
require_once '../tool/documentExplorerListFunction.php';
$startDate=date('Y-m-d');
$endDate=null;
$user=getSessionUser();
$projectDate=Parameter::getUserParameter('projectDate');
$paramStart=SqlElement::getSingleSqlElementFromCriteria('Parameter',array('idUser'=>$user->id,'idProject'=>null,'parameterCode'=>'planningStartDate'));
if ($paramStart->id) {
  $startDate=$paramStart->parameterValue;
}
$paramEnd=SqlElement::getSingleSqlElementFromCriteria('Parameter',array('idUser'=>$user->id,'idProject'=>null,'parameterCode'=>'planningEndDate'));
if ($paramEnd->id) {
  $endDate=$paramEnd->parameterValue;
}
if($projectDate){
  $startDate=null;
  $endDate=null;
}else{
  $startDate=date('Y-m-d');
}
$saveShowResource=Parameter::getUserParameter('planningShowResource');
$saveShowProjectModel=Parameter::getUserParameter('showProjectModel');
// Closed (idle) items are not dealt with here : documentExplorerShowClosed(), in
// tool/documentExplorerTreeData.php, owns that decision and tool/jsonDocumentExplorer.php
// applies it - the two refreshes of the screen call it without passing through this view.

$hideTimeline = Parameter::getUserParameter('hideTimeline');
$displayTimeline=($hideTimeline)?'none':'block';
$tlItem = new TimelineItem();
$timeline = $tlItem->getSqlElementsFromCriteria(array('idUser'=>$user->id));
$displayTimeline = (count($timeline)>0 and $displayTimeline != 'none')?'block':'none;';
$paramHistoryVisible=Parameter::getUserParameter('displayHistory');
$displayHistory = ($paramHistoryVisible == 'NO')?false:true;
?>

<div id="mainDocumentExplorerDivContainer" dojoType="dijit.layout.BorderContainer">
	<div dojoType="dijit.layout.ContentPane" region="top" id="listHeaderDiv"
	 style="z-index: 3; position: relative; overflow: visible !important;padding-bottom:5px;min-height: 34px;">
	  <script type="dojo/method" event="onUnload" >
      if (! documentExplorerDrawInProgress) documentExplorerResetFieldsDescription();
      return true;
    </script>
		<table width="100%" class="listTitle" style="height:auto">
		  <tr height="27px" >
		    <td style="vertical-align:top; min-width:100px; width:15%">
		      <table >
    		    <tr height="32px">
      		    <td width="50px" style="min-width:50px;<?php if (isNewGui()) echo 'position:relative;top:2px';?>" align="center">
                <?php echo formatIcon('DocumentDirectory', 32, null, true);?>
              </td>
              <td style="min-width:100px" ><span class="title" style="max-width:250px;white-space:normal"><?php echo i18n('menuDocumentExplorer');?></span></td>
      		  </tr>
    		  </table>
		    </td>
		    <td>
		      <form dojoType="dijit.form.Form" id="listForm" action="" method="" style="">
		      	<?php
		        $objectClass=(RequestHandler::isCodeSet('objectClass'))?RequestHandler::getClass('objectClass'):'';
		        $objectId=(RequestHandler::isCodeSet('objectId'))?RequestHandler::getId('objectId'):'';?>
		        <input type="hidden" id="planningType" name="planningType" value="<?php echo $planningType;?>" />
		        <?php  ?>
		        <input type="hidden" id="objectClassList" name="objectClassList" value="Document" />
		        <input type="hidden" id="objectClass" name="objectClass" value="<?php echo $objectClass;?>" />
		        <input type="hidden" id="objectId" name="objectId" value="<?php echo $objectId;?>" />
		        <input type="hidden" id="idProjectForCalendar" name="idProjectForCalendar" value="<?php echo Project::getIdProjectForIdCalendarDefinition();?>" />
		        <?php if (isNewGui()) { // ========================================================= NEW GUI?>
		        <table style="width: 100%;">
		          <tr>
		            <td style="width:90%;text-align:right;white-space:nowrap;vertical-align:middle;">
                  <?php  ?>
                  &nbsp;
                </td>
		            <?php  ?>
                <td style="width:150px;text-aliogn:right;">
                       <?php  ?>
                       <?php documentExplorerDrawButtonsDefault();?>
                </td>
                <td style="width:50px;padding-right:10px;">
                  <?php documentExplorerDrawNewItem(); ?>
                </td>
                <td style="width:50px;padding-right:10px;">
                  <?php  ?>
                  <?php documentExplorerDrawExtraButton(); ?>
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
		<div dojoType="dijit.layout.ContentPane" id="documentExplorerJsonData" jsId="documentExplorerJsonData"
     style="display: none">

		  <?php
		       if ($saveShowResource) $_REQUEST['showResource']='on';
		       if ($saveShowProjectModel) $_REQUEST['showProjectModel']='on';
		       $length=Parameter::getPlanningPageLineCount();
		       setSessionValue('showAllGanttLines', 'false');
		       $_REQUEST['jsonQueryStartLine']=0;
		       $_REQUEST['jsonQueryNbLines']=$length;
		       $_REQUEST['jsonQueryHiddenLines']=0;
            include '../tool/jsonDocumentExplorer.php';
          ?>
		</div>
	</div>
	<div dojoType="dijit.layout.ContentPane" region="center" id="gridContainerDiv" >
   <div id="submainDocumentExplorerDivContainer" dojoType="dijit.layout.BorderContainer"
    style="border-top:1px solid #ffffff;">
    <?php $leftPartSize=Parameter::getUserParameter('documentExplorerLeftSize');
          if (! $leftPartSize or intval($leftPartSize) < 325) {$leftPartSize='325px';} ?>
	   <div dojoType="dijit.layout.ContentPane" region="left" splitter="true"
      style="width:<?php echo $leftPartSize;?>; height:100%; overflow-x:auto; overflow-y:auto;" class="ganttDiv"
      id="leftGanttChartDIV" name="leftGanttChartDIV"
      onScroll="documentExplorerShowVisibleLines();">
      <script type="dojo/method" event="onUnload" >
         setTimeout("documentExplorerSaveLeftSize();",1);
         return true;
      </script>
     </div>
     <div dojoType="dijit.layout.ContentPane" region="center"
      style="height:100%; overflow:hidden;" class="ganttDiv"
      id="GanttChartDIV" name="GanttChartDIV" >
       <div id="mainRightPlanningDivContainer" dojoType="dijit.layout.BorderContainer" style="z-index:-4;">
         <?php  ?>
         <div dojoType="dijit.layout.ContentPane" region="center"
          style="width:100%; overflow-x:auto; overflow-y:auto; position:relative;" class="ganttDiv"
          id="rightGanttChartDIV" name="rightGanttChartDIV">
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
          <!-- #11179 -->

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
          <tr id="cm_addFromPlanning" class="contextMenuRow" onClick="">
            <td style="padding-top:5px;padding-bottom:5px;"><?php echo formatSmallButton('Add', false , false);?></td>
            <td style="padding-left:10px;padding-top:5px;padding-bottom:5px;" id="cm_addFromPlanning_label"><?php echo i18n('contextMenuButtonNew');?></td>
          </tr>
          <tr id="cm_copyFromPlanning" class="contextMenuRow" onClick="">
            <td style="padding-top:5px;padding-bottom:5px;"><?php echo formatSmallButton('Copy', false , false);?></td>
            <td style="padding-left:10px;padding-top:5px;padding-bottom:5px;" id="cm_copyFromPlanning_label"><?php echo i18n('contextMenuButtonCopy');?></td>
          </tr>
          <tr id="cm_removeFromPlanning" class="contextMenuRow" onClick="">
            <td style="padding-top:5px;padding-bottom:5px;"><?php echo formatSmallButton('Remove', false , false);?></td>
            <td style="padding-left:10px;padding-top:5px;padding-bottom:5px;" id="cm_removeFromPlanning_label"><?php echo i18n('contextMenuButtonDelete');?></td>
            <script type="dojo/connect" event="onClick" args="evt">
            </script>
          </tr>
          <tr id="cm_emailFromPlanning" class="contextMenuRow" onClick="" >
            <td style="padding-top:5px;padding-bottom:5px;"><?php echo formatSmallButton('Email', false, false);?></td>
            <td style="padding-left:10px;padding-top:5px;padding-bottom:5px;" id="cm_emailFromPlanning_label"><?php echo i18n('contextMenuButtonMail');?></td>
          </tr>
          <?php if($displayHistory){?>
          <tr id="cm_historyFromPlanning" class="contextMenuRow" onClick="" >
            <td style="padding-top:5px;padding-bottom:5px;"><?php echo formatSmallButton('History', false, false);?></td>
            <td style="padding-left:10px;padding-top:5px;padding-bottom:5px;"><?php echo i18n('dialogHistory');?></td>
          </tr>
          <?php }?>
          <tr id="cm_explorerExtract" class="contextMenuRow" onClick="" style="display:none;">
            <td style="padding-top:5px;padding-bottom:5px;"><?php echo formatSmallButton('Download', false , false);?></td>
            <td style="padding-left:10px;padding-top:5px;padding-bottom:5px;"><?php echo i18n('buttonDocumentExtraction');?></td>
          </tr>
        </table>
      </div>
    </div>
  </div>
</div>
