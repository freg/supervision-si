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
require_once('_securityCheck.php');

class SprintPlanningElementMain extends PlanningElement {
  public $id;
  public $idProject;
  public $refType;
  public $refId;
  public $refName;
  public $_tab_5_3_smallLabel = array('validated', 'planned', 'real', '', 'requested', 'startDate', 'endDate', 'duration');
  public $validatedStartDate;
  public $plannedStartDate;
  public $realStartDate;
  public $latestStartDate;
  public $initialStartDate;
  public $validatedEndDate;
  public $plannedEndDate;
  public $realEndDate;
  public $latestEndDate;
  public $initialEndDate;
  public $validatedDuration;
  public $plannedDuration;
  public $realDuration;
  public $_void_4;
  public $initialDuration;
  public $_separator_sectionCostWork_marginTop;
  public $_tab_5_3_smallLabel_1 = array('validated', 'assigned', 'real', 'left', 'reassessed', 'work', 'cost','costLocal');
  public $validatedWork;
  public $assignedWork;
  public $realWork;
  public $leftWork;
  public $plannedWork;
  public $validatedCost;
  public $assignedCost;
  public $realCost;
  public $leftCost;
  public $plannedCost;
  public $validatedCostLocal;
  public $assignedCostLocal;
  public $realCostLocal;
  public $leftCostLocal;
  public $plannedCostLocal;
  public $_separator_menuReview_marginTop;
  public $_tab_5_2_smallLabel_3 = array('', '', '', '', '', 'progress','priority');
  public $progress;
  public $_label_expected;
  public $expectedProgress;
  public $_label_wbs;
  public $wbs;
  public $priority;
  public $_label_planning;
  public $idSprintPlanningMode;
  public $fixPlanning;
  public $_lib_helpFixPlanning;
  public $paused;
  public $_lib_helpPaused;
  public $_tab_5_1_smallLabel = array('workElementCount', 'estimated', 'real', 'left', '', 'IdUserStory');
  public $workElementCount;
  public $workElementEstimatedWork;
  public $workElementRealWork;
  public $workElementLeftWork;
  public $_button_showUserSotry;
  public $_tab_1_1_smallLabel_1 = array('', 'color');
  public $color;
  
  private static $_fieldsAttributes=array(
      "plannedStartDate"=>"readonly,noImport",
      "realStartDate"=>"readonly,noImport",
      "plannedEndDate"=>"readonly,noImport",
      "realEndDate"=>"readonly,noImport",
      "plannedDuration"=>"readonly,noImport",
      "validatedDuration"=>"required",
      "realDuration"=>"readonly,noImport",
      "initialWork"=>"hidden",
      "plannedWork"=>"readonly,noImport",
      "notPlannedWork"=>"hidden",
      "realWork"=>"readonly,noImport",
      "leftWork"=>"readonly,noImport",
      "assignedWork"=>"readonly,noImport",
      "idSprintPlanningMode"=>"required,mediumWidth,colspan3",
      "expenseAssignedAmount"=>"readonly",
      "expenseRealAmount"=>"readonly",
      "expenseLeftAmount"=>"readonly",
      "expensePlannedAmount"=>"readonly",
      "idPlanningMode"=>"hidden,noImport",
      "indivisibility"=>"colspan3",
      "workElementEstimatedWork"=>"readonly,noImport",
      "workElementRealWork"=>"readonly,noImport",
      "workElementLeftWork"=>"readonly,noImport",
      "workElementCount"=>"display,noImport",
      "plannedStartFraction"=>"hidden",
      "plannedEndFraction"=>"hidden",
      "validatedStartFraction"=>"hidden",
      "validatedEndFraction"=>"hidden",
      "latestStartDate"=>"hidden",
      "latestEndDate"=>"hidden",
      "isOnCriticalPath"=>"hidden",
      "isManualProgress"=>"hidden",
      "_tab_5_1_smallLabel_4"=>"hidden",
      "_spe_isOnCriticalPath"=>"",
      "_label_indivisibility"=>"",
      "indivisibility"=>"",
      "minimumThreshold"=>"",
      "fixPlanning"=>"nobr",
      "paused"=>"nobr",
      "_separator_menuTechnicalProgress_marginTop"=>"hidden",
      "_separator_sectionRevenue_marginTop"=>"hidden",
      "unitToDeliver"=>"",
      "unitToRealise"=>"",
      "unitRealised"=>"",
      "unitLeft"=>"",
      "unitProgress"=>"",
      "idProgressMode"=>"",
      "unitWeight"=>"",
      "hasWorkUnit"=>"hidden",
      "minimumThreshold"=>"hidden",
      "indivisibility"=>"hidden",
      "unitToDeliver"=>"hidden",
      "unitToRealise"=>"hidden",
      "unitToRealise"=>"hidden",
      "unitRealised"=>"hidden",
      "unitLeft"=>"hidden",
      "unitProgress"=>"hidden",
      "idProgressMode"=>"hidden",
      "unitWeight"=>"hidden"
  );
  
  private static $_fieldsTooltip = array(
      "minimumThreshold"=> "tooltipMinimumThreshold",
      "indivisibility"=> "tooltipIndivisibility",
      "fixPlanning"=> "tooltipFixPlanningSprint",
      "expectedProgress"=> "tooltipFixPlanningSprint",
      "paused"=>"tooltipPausedSprint"
  );
  
  private static $_databaseTableName = 'planningelement';
  //private static $_databaseCriteria = array('refType'=>'Sprint'); // Bad idea : sets a mess when moving projets and possibly elsewhere.
  
  private static $_databaseColumnName=array(
      "idSprintPlanningMode"=>"idPlanningMode"
  );
  
  private static $_colCaptionTransposition = array('initialStartDate'=>'requestedStartDate',
      'initialEndDate'=> 'requestedEndDate',
      'initialDuration'=>'requestedDuration'
  );
  
  /* Return the specific databaseTableName
  * @return String the databaseTableName
  */
  protected function getStaticDatabaseTableName() {
    $paramDbPrefix=Parameter::getGlobalParameter('paramDbPrefix');
    return $paramDbPrefix . self::$_databaseTableName;
  }
  
  /** ==========================================================================
   * Return the specific fieldsAttributes
   * @return Array the fieldsAttributes
   */
  protected function getStaticFieldsAttributes() {
    return array_merge(parent::getStaticFieldsAttributes(),self::$_fieldsAttributes);
  }
  
  /** ========================================================================
   * Return the generic databaseTableName
   * @return String the databaseTableName
   */
  protected function getStaticDatabaseColumnName() {
    return self::$_databaseColumnName;
  }
  
  /** ============================================================================
   * Return the specific colCaptionTransposition
   * @return String the colCaptionTransposition
   */
  protected function getStaticColCaptionTransposition($fld=null) {
    return self::$_colCaptionTransposition;
  }
  
  protected function getStaticFieldsTooltip() {
    return self::$_fieldsTooltip;
  }
  
  /**=========================================================================
   * Overrides SqlElement::save() function to add specific treatments
   * @see persistence/SqlElement#save()
   * @return String the return message of persistence/SqlElement#save() method
   */
  public function save() {
    if (! PlanningElement::$_noDispatch) $this->updateWorkElementSummary(true);
    if(!$this->id){
      $this->automaticAssignment = 1;
    }
    if($this->idSprintPlanningMode){
      $this->idPlanningMode = $this->idSprintPlanningMode;
    }
    $old = $this->getOld();
    $result= parent::save();
    return $result;
  }
  
  /** =========================================================================
   * control data corresponding to Model constraints
   * @param void
   * @return "OK" if controls are good or an error message
   *  must be redefined in the inherited class
   */
  public function control(){
    $result="";
    $defaultControl=parent::control();
    if ($defaultControl!='OK') {
      $result.=$defaultControl;
    }if ($result=="") {
      $result='OK';
    }
    return $result;
  }
  
  public function getValidationScript($colName) {
    $colScript = parent::getValidationScript ( $colName );
    if ($colName == "fixPlanning") {
      if(Parameter::getUserParameter('paramLayoutObjectDetail')=="tab"){
        $colScript .= '<script type="dojo/connect" event="onChange" >';
        $colScript .= ' dijit.byId("fixPlanning").set("value",dijit.byId("SprintPlanningElement_fixPlanning").get("value"));';
        $colScript .= '  formChanged();';
        $colScript .= '</script>';
      }
    }else if($colName=="paused"){
      $colScript .= '<script type="dojo/connect" event="onChange" >';
      $colScript .= '  if(this.checked){';
      $colScript .= '   dijit.byId("SprintPlanningElement_fixPlanning").set("readOnly",true);';
      $colScript .= '   dijit.byId("SprintPlanningElement_fixPlanning").set("checked",true);';
      $colScript .= '   dijit.byId("SprintPlanningElement_fixPlanning").set("value",1);';
      $colScript .= '   dijit.byId("fixPlanning").set("readOnly",true);';
      $colScript .= '  }else{';
      $colScript .= '   dijit.byId("SprintPlanningElement_fixPlanning").set("readOnly",false);';
      $colScript .= '   dijit.byId("SprintPlanningElement_fixPlanning").set("checked",false);';
      $colScript .= '   dijit.byId("SprintPlanningElement_fixPlanning").set("value",0);';
      $colScript .= '   dijit.byId("fixPlanning").set("readOnly",false);';
      $colScript .= '  }';
      if(Parameter::getUserParameter('paramLayoutObjectDetail')=="tab"){
        $colScript .= ' dijit.byId("paused").set("value",dijit.byId("SprintPlanningElement_fixPlanning").get("value"));';
        $colScript .= '  formChanged();';
      }
      $colScript .= '</script>';
    }else if ($colName=='validatedCost') {
      $colScript .= '<script type="dojo/connect" event="onChange" >';
      $colScript .= '  if (dijit.byId("' . get_class($this) . '_totalValidatedCost")) {';
      $colScript .= '    var cost=dijit.byId("' . get_class($this) . '_validatedCost").get("value");';
      $colScript .= '    var expense=dijit.byId("' . get_class($this) . '_expenseValidatedAmount").get("value");';
      $colScript .= '    if (!cost) cost=0;';
      $colScript .= '    if (!expense) expense=0;';
      $colScript .= '    var total = cost+expense;';
      $colScript .= '    dijit.byId("' . get_class($this) . '_totalValidatedCost").set("value",total);';
      $colScript .= '    formChanged();';
      $colScript .= '  }';
      $colScript .= '</script>';
    }
    return $colScript;
  }
  
  public function drawSpecificItem($item) {
    if ($item=='showUserSotry') {
      echo '<div id="' . $item . 'Button" ';
      echo ' title="' . i18n('showUserStory') . '" style="float:right;margin-right:3px;"';
      $jsFunction="showUserStories('Sprint',$this->refId);";
      echo ' onclick="' . $jsFunction . '" >';
      echo formatMediumButton('View');
      echo '</div>';
    }
  }
  
  protected function updateSynthesisSprint ($doNotSave=false) {
    parent::updateSynthesisObj(($doNotSave)?1:2); // Will update work and resource cost, but not save yet ;)
    $this->addUserStoryWork(true); // Will add ticket work that is not linked to Activity
    if (!$doNotSave) $resultSaveAct=$this->save();
  }
  
  /** =========================================================================
   * Update the synthesis Data (work) from workElement
   * Called by workElement
   * @return void
   */
  public function updateWorkElementSummary($noSave=false) {
    $we=new WorkElement();
    $weList=$we->getSqlElementsFromCriteria(array('idSprint'=>$this->refId));
    $this->workElementEstimatedWork=0;
    $this->workElementRealWork=0;
    $this->workElementLeftWork=0;
    $this->workElementCount=0;
    foreach ($weList as $we) {
      $this->workElementEstimatedWork+=$we->plannedWork;
      $this->workElementRealWork+=$we->realWork;
      $this->workElementLeftWork+=$we->leftWork;
      $this->workElementCount+=1;
    }
    if (! $noSave) {
      $this->simpleSave();
    }
  }
  
  public function addUserStoryWork($doNotSave=false) {
    $where='idSprint='.$this->refId; $crit=null;
    $tkt=new WorkElement();
    $sum=$tkt->sumSqlElementsFromCriteria(array('realWork', 'leftWork','realCost','leftCost'), $crit, $where);
    $this->realWork+=$sum['sumrealwork'];
    $this->leftWork+=$sum['sumleftwork'];
    $this->realCost+=$sum['sumrealcost'];
    $this->leftCost+=$sum['sumleftcost'];
    $this->plannedWork=$this->realWork+$this->leftWork; // Need to be done here to refrehed
    $this->plannedCost=$this->realCost+$this->leftCost;
    //$this->realCost+=$sumCost;
    if (! $doNotSave) {
      $this->simpleSave();
      if ($this->topId) {
        self::updateSynthesis($this->topRefType, $this->topRefId);
      }
    }
  }
}
