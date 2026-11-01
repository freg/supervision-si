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
 * Presents an object. 
 */
  require_once "../tool/projeqtor.php";
  scriptLog('   ->/view/planningWorkPlanMain.php');
  

  //florent
  $currentScreen='PlanningWorkPlan';
  $notGlobal=RequestHandler::getBoolean('notGlobal');
  $paramScreen='';
  if(RequestHandler::isCodeSet('paramScreen_'.$currentScreen)){
    $paramScreen=RequestHandler::getValue('paramScreen_'.$currentScreen);
  }else if(RequestHandler::isCodeSet('paramScreen')){
    $paramScreen=RequestHandler::getValue('paramScreen');
  }
  $paramLayoutObjectDetail=RequestHandler::getValue('paramLayoutObjectDetail');
  if(RequestHandler::isCodeSet('paramRightDiv_'.$currentScreen)){
    $paramRightDiv=RequestHandler::getValue('paramRightDiv_'.$currentScreen);
  }else{
    $paramRightDiv=RequestHandler::getValue('paramRightDiv');
  }
  if((!$notGlobal and $paramScreen!='')){
    if($paramScreen=='top')$paramRightDiv='trailing';
    else $paramRightDiv='bottom';
  }
  setSessionValue('currentScreen', $currentScreen);
  $positionListDiv=changeLayoutObjectDetail($paramScreen,$paramLayoutObjectDetail,'paramScreen_'.$currentScreen,$notGlobal);
  $positonRightDiv=changeLayoutActivityStream($paramRightDiv,'paramRightDiv_'.$currentScreen,$notGlobal);
  if(Parameter::getUserParameter('paramScreen_'.$currentScreen)){
    $codeModeLayout=Parameter::getUserParameter('paramScreen_'.$currentScreen);
  }else{
    $codeModeLayout=Parameter::getUserParameter('paramScreen');
  }
  $listHeight='';
  if ($positionListDiv=='top'){
    $listHeight=HeightLayoutListDiv($currentScreen);
  }
  if($positonRightDiv=="bottom"){
    $rightHeightPlanning=getHeightLayoutActivityStream($currentScreen);
  }else{
  	$rightWidthPlanning=getWidthLayoutActivityStream($currentScreen);
  }
  $tableWidth=WidthDivContentDetail($positionListDiv,$currentScreen);
  //
?>
<input type="hidden" name="objectClassManual" id="objectClassManual" value="PlanningWorkPlan" />
<input type="hidden" name="planning" id="planning" value="true" />
<input type="hidden" id="projectNotStartBeforeValidatedDate" value="<?php echo (Parameter::getGlobalParameter("notStartBeforeValidatedStartDate")=='YES')?1:0;?>" />
<div id="mainDivContainer" class="container" dojoType="dijit.layout.BorderContainer" onclick="hideDependencyRightClick();">
 <div dojoType="dijit.layout.ContentPane" region="center" splitter="true">
    <div class="container" dojoType="dijit.layout.BorderContainer" liveSplitters="false">
    <div id="listBarShow" class="dijitAccordionTitle"  onMouseover="showList('mouse')" onClick="showList('click');">
		  <div id="listBarIcon" align="center"></div>
		</div>
      <div id="listDiv" dojoType="dijit.layout.ContentPane" region="left" 
      style="width:100%">
// <?php $clickAction=Parameter::getUserParameter('planningClickAction');
//       if ($clickAction=='') {
//         $msg=i18n("planningClickActionMessage");
//         echo '<script type="dojo/connect" event="onShow" args="evt">';
//         echo 'var showInfoMsg=function(){';
//         echo '   showInfo("'.$msg.'");';
//         echo '};';
//         echo ' setTimeout(showInfoMsg,1500);';
//         echo '</script>';
//         Parameter::storeUserParameter('planningClickAction', '0');
//       }
      include 'planningWorkPlanList.php'?>
      </div>
 </div>
</div> 