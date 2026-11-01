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
 * Scenario for Critial Resources : specific project types
 */ 
require_once('_securityCheck.php');
class CriticalResourceScenarioProject extends SqlElement {

  // extends SqlElement, so has $id
  public $_sec_Description;
  public $id;    // redefine $id to specify its visible place 
  public $idProject;
  public $idUser;
  public $idScenario;
  public $proposale;
  public $monthDelay;
  //public $_sec_void;
  

  
   /** ==========================================================================
   * Constructor
   * @param $id Int the id of the object in the database (null if not stored yet)
   * @return void
   */ 
  function __construct($id = NULL, $withoutDependentObjects=false) {
    parent::__construct($id,$withoutDependentObjects);
  }

  
   /** ==========================================================================
   * Destructor
   * @return void
   */ 
  function __destruct() {
    parent::__destruct();
  }

// ============================================================================**********
// GET STATIC DATA FUNCTIONS
// ============================================================================**********

  public static function getScenarioProjectInfo(&$listProjectsType, &$listProjectsDelay, $idScenario=null) {
    $crsp=new CriticalResourceScenarioProject();
    $list=$crsp->getSqlElementsFromCriteria(array('idScenario'=>$idScenario, 'idUser'=>getCurrentUserId()));
    foreach ($list as $crsp) {
      if ($crsp->proposale==2) $listProjectsType[$crsp->idProject]='OPE';
      else if ($crsp->proposale==1) $listProjectsType[$crsp->idProject]='PRP'; 
      if ($crsp->monthDelay) $listProjectsDelay[$crsp->idProject]=$crsp->monthDelay;
    }
  }
  
  public static function drawProjectList(){
    $user=getSessionUser();
    $prjVisLst=$user->getVisibleProjects();
    $prjLst=$user->getHierarchicalViewOfVisibleProjects(true);
    $width=RequestHandler::getValue('destinationWidth',1500);
    $widthTab=($width*0.6)-100;
    $widthType=180;
    $widthDate=300;
    $widthWbs=100;
    $widthProj=$widthTab-$widthType-$widthDate-$widthWbs;
    $projType=array();
    $projDelay=array();
    $showAllProject='false';
    self::getScenarioProjectInfo($projType,$projDelay,null);
    echo '<table align="center" style="margin:10px 20px" class="dijitTitlePane">';
    echo '<thead><tr>';
    echo '  <td class="messageHeader sortable" style="width:'.$widthWbs.'px;border-right:0" onclick="onColumnHeaderClickedSort(event)">'.i18n('colWbs').'</td>';
    echo '  <td class="messageHeader sortable" style="position:relative;width:'.$widthProj.'px;border-right:0" onclick="onColumnHeaderClickedSort(event)">'.i18n('colIdProject').'</td>';
    echo '  <td class="messageHeader sortable" style="width:'.$widthType.'px;border-right:0" onclick="onColumnHeaderClickedSort(event)">'.i18n('colType').'</td>';
    echo '  <td class="messageHeader sortable" style="width:'.intval($widthDate*0.30).'px;border-right:0" onclick="onColumnHeaderClickedSort(event)">'.i18n('colStart').'</td>';
    echo '  <td class="messageHeader sortable" style="width:'.intval($widthDate*0.30).'px;border-right:0;border-left:0" onclick="onColumnHeaderClickedSort(event)">'.i18n('colEnd').'</td>';
    echo '  <td class="messageHeader sortable" style="width:'.intval($widthDate*0.40).'px;border-right:0;border-left:0" onclick="onColumnHeaderClickedSort(event)">'.i18n('colLate').' ('.i18n('colMonth').')&nbsp;</td>';
    echo '</tr></thead>';
    $parmSizeProject=null;
    $countPro=0;
    $adminProject=Project::getAdminitrativeProjectList(true);
    foreach ($prjLst as $sharpid=>$sharpName) {
      if (isset($adminProject[pq_trim($sharpid,'#')])) continue;
      $countPro++;
      if($parmSizeProject!='' and $parmSizeProject==$countPro and $showAllProject=='false'){
        echo '<tr style="text-align: center;font-weight:bold;">';
        echo '<td colspan="3"  class="messageData"><div >'.i18n('limitedDisplay', array($parmSizeProject)).'</div></td>';
        echo'</tr>';
        break;
      }
      $split=pq_explode('#', $sharpName);
      //$wbs=$split[0];
      //$wbsSortable=formatSortableWbs($wbs);
      $name=pq_str_replace('&sharp;', '#', $split[1]);
      $id=pq_substr($sharpid, 1);
      $wbsSortable=SqlList::getFieldFromId('Project',$id,'sortOrder');
      $wbs=formatWbs($wbsSortable);
      $project=new Project($id,false);
      $typ=SqlList::getFieldFromId('ProjectType', $project->idProjectType, 'code');
      echo '<tr style="height:25px;position:relative;">';
      // PBER : important, leave the ! after formatSortableWbs($wbs), this ensures correct sorting (so that 00001!< is before 00001.000001!<
      echo '<td class="reportTableData" style="width:'.$widthWbs.'px;text-align:left"><div class="dataContent" style="width:'.$widthWbs.'px;"><div style="display:none">'.$wbsSortable.'!</div><div class="dataExtend" style="min-width:'.($widthWbs-5).'px">'.$wbs.'</div></div></td>';
      echo '<td class="reportTableData classLinkName" style="width:'.$widthProj.'px;text-align:left" onclick="gotoElement(\'Project\','.$project->id.');"><div class="dataContent" style="width:'.$widthProj.'px;"><div class="dataExtend" style="min-width:'.($widthProj-5).'px">'.$name.'&nbsp;&nbsp;&nbsp;</div></div></td>';
      $alteredType=false;
      if (isset($projType[$project->id])) {
        $alteredType=$projType[$project->id];
      }
      echo '<td id="scenarioProjectTD_'.$project->id.'" class="reportTableData'.(($alteredType)?' alteredScenario':'').'" style="width:'.$widthType.'px;padding:2px 5px">';
      echo '  <table style="width:100%"><tr>';
      echo '    <td style="text-align:left">'.SqlList::getNameFromId('ProjectType', $project->idProjectType).'</td>';
      echo '    <td style="width:20px">';
      if ( ($typ=='PRP' and $alteredType!='OPE') or $alteredType=='PRP') $lockedClass="Locked";
      else  $lockedClass="UnLocked";  
      echo '      <div id="scenarioProjectIcon_'.$project->id.'" onClick="scenarioProjectSwitchType('.$project->id.')" class="roundedIconButton icon'.$lockedClass.' iconSize22">&nbsp;</div>';
      echo '    </td>';
      echo '  </tr></table>';
      echo '</td>';
      $alteredDelay=0;
      if (isset($projDelay[$project->id])) {
        $alteredDelay=$projDelay[$project->id];
      }
      echo '<td id="scenarioProjectDelayTD1_'.$project->id.'" class="reportTableData'.(($alteredDelay)?' alteredScenario':'').'" style="padding:2px 5px; border-right:0">';
      echo ' <div style="display:none">'.$project->ProjectPlanningElement->plannedStartDate.'</div>'.htmlFormatDate($project->ProjectPlanningElement->plannedStartDate);
      echo '</td>';
      echo '<td id="scenarioProjectDelayTD2_'.$project->id.'" class="reportTableData'.(($alteredDelay)?' alteredScenario':'').'" style="padding:2px 5px;border-right:0; border-left:0">';
      echo ' <div style="display:none">'.$project->ProjectPlanningElement->plannedEndDate.'</div>'.htmlFormatDate($project->ProjectPlanningElement->plannedEndDate);
      echo '</td>';
      echo '<td id="scenarioProjectDelayTD3_'.$project->id.'" class="reportTableData'.(($alteredDelay)?' alteredScenario':'').'" style="padding:2px 5px; border-left:0">';
      echo ' <div id="scenarioProjectDelayValue_'.$project->id.'" style="display:none">'.htmlSortFixLengthNumeric($alteredDelay,3).'</div>';            
      echo ' <div style="width:70px; text-align: center; color: #000000; display:inline-block;" ';
      echo '   dojoType="dijit.form.NumberSpinner" constraints="{min:-100,max:100,places:0,pattern:\'###0\'}"';
      echo '   intermediateChanges="true" maxlength="3"  class="input  generalColClass "  value="'.$alteredDelay.'"';
      echo '   smallDelta="1" id="scenarioProjectDelay_'.$project->id.'">';
      echo '   <script type="dojo/connect" event="onChange" >  scenarioProjectSwitchDelay('.$project->id.')</script>';
      echo ' </div>';
      echo '</td>';
      echo '</tr>';
    }  
    echo "</table>";
  }
}
?>