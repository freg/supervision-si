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
 * Scenario for Critial Resources : specific pool capacity
 */ 
require_once('_securityCheck.php');
class CriticalResourceScenarioPool extends SqlElement {

  // extends SqlElement, so has $id
  public $_sec_Description;
  public $id;    // redefine $id to specify its visible place 
  public $idResource;
  public $idUser;
  public $idScenario;
  public $extracapacity;
  public $givenDate;
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
  public static function getScenarioPoolInfo(&$listPoolExtraCapa,&$listPoolGivenDate=null, $idScenario=null) {
    $crsp=new CriticalResourceScenarioPool();
    $list=$crsp->getSqlElementsFromCriteria(array('idScenario'=>$idScenario));
    foreach ($list as $crsp) {
      $listPoolExtraCapa[$crsp->idResource]=$crsp->extracapacity;
      $listPoolGivenDate[$crsp->idResource]=$crsp->givenDate;
    }
  }
  
  public static function drawPoolList(){
    $user=getSessionUser();
    $width=RequestHandler::getValue('destinationWidth',1500);
    $widthTab=$width/2-100;
    $widthCapa=400;
    $widthPool=$widthTab-$widthCapa;
    $poolExtraCapa=array();
    $poolGivenDate=array();
    self::getScenarioPoolInfo($poolExtraCapa,$poolGivenDate,null);
    $pool=new ResourceTeam();
    $poolList=$pool->getSqlElementsFromCriteria(array("idle"=>"0"),null,null,'fullName asc',true);
    
    echo '<table align="center" style="margin:10px 20px" class="dijitTitlePane">';
    echo '<thead><tr>';
    echo '  <td class="messageHeader sortable" style="width:'.$widthPool.'px;border-right:0" onclick="onColumnHeaderClickedSort(event)">'.lcfirst(i18n('ResourceTeam')).'</td>';
    echo '  <td class="messageHeader sortable" style="text-align:center;width:'.intval($widthCapa*0.5).'px;border-right:0" onclick="onColumnHeaderClickedSort(event)">'.i18n('colCapacity').'</td>';
    echo '  <td class="messageHeader sortable" style="text-align:center;width:'.intval($widthCapa*0.5).'px;border-left:0;px;border-right:0" onclick="onColumnHeaderClickedSort(event)">'.i18n('colSurbooking').'</td>';
    echo '  <td class="messageHeader sortable" style="text-align:center;width:'.intval($widthCapa*0.5).'px;border-left:0" onclick="onColumnHeaderClickedSort(event)">'.i18n('colGivenDate').'</td>';
    
    echo '</tr></thead>';
    $countPool=0;
    foreach ($poolList as $poolId=>$pool) {
      $countPool++;
      $name=$pool->name;
      $id=$pool->id;
      echo '<tr style="height:25px;position:relative;">';
      echo '<td class="reportTableData classLinkName" style="width:'.$widthPool.'px;text-align:left" onclick="gotoElement(\'ResourceTeam\','.$id.');"><div class="dataContent" style="width:'.$widthPool.'px;"><div class="dataExtend" style="min-width:'.($widthPool-5).'px">'.$name.'&nbsp;&nbsp;&nbsp;</div></div></td>';
      $alteredCapa=0;
      if (isset($poolExtraCapa[$pool->id])) {
        $alteredCapa=$poolExtraCapa[$pool->id];
      }
      $givenDate=null;
      if (isset($poolGivenDate[$pool->id])) {
        $givenDate=$poolGivenDate[$pool->id];
      }
      $capa=$pool->getCapacityPeriod(date('Y-m-d'));
      echo ' <td id="scenarioPoolTD1_'.$pool->id.'" class="reportTableData'.(($alteredCapa)?' alteredScenario':'').'" style="padding:2px 5px;border-right:0">';
      echo '  <div style="display:none">'.htmlSortFixLengthNumeric($capa*10,4).'</div>'.htmlDisplayNumericWithoutTrailingZeros($capa);
      echo ' </td>';
      echo ' <td id="scenarioPoolTD2_'.$pool->id.'" class="reportTableData'.(($alteredCapa)?' alteredScenario':'').'" style="padding:2px 5px;border-left:0;border-right:0">';
      echo '  <div id="scenarioPoolExtraCapa_'.$pool->id.'" style="display:none">'.htmlSortFixLengthNumeric($alteredCapa*10,4).'</div>';     
      echo '   <div style="width:70px; text-align: center; color: #000000; display:inline-block;" ';
      echo '     id="scenarioPoolExtraCapa_'.$pool->id.'" dojoType="dijit.form.NumberSpinner" constraints="{min:0,max:100,places:1,pattern:\'###0.0\'}"';
      echo '     intermediateChanges="true" maxlength="3"  class="input  generalColClass " value="'.$alteredCapa.'"';
      echo '     smallDelta="0.5" id="scenarioPoolExtraCapa_'.$pool->id.'">';
      echo '     <script type="dojo/connect" event="onChange" >  scenarioPoolSwitchCapacity('.$pool->id.')</script>';
      echo '   </div>';
      echo ' </td>';
      echo ' <td id="scenarioPoolTD3_'.$pool->id.'" class="reportTableData'.(($alteredCapa)?' alteredScenario':'').'" style="padding:2px 5px;border-left:0">';
      echo '  <div dojoType="dijit.form.DateTextBox" id="givenDate_'.$pool->id.'" name="givenDate" style="width:105px; text-align: center; color: #000000; display:inline-block;" value="'.$givenDate.'">';
      echo '     <script type="dojo/connect" event="onChange" >  scenarioPoolSaveDate('.$pool->id.')</script>';
      echo '  </div>';
      echo ' </td>';
      echo '</tr>';
    }
    echo "</table>";
  }
  
}
?>