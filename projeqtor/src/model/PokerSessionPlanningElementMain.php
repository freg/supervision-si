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
 * Planning element is an object included in all objects that can be planned.
 */ 
require_once('_securityCheck.php');

class PokerSessionPlanningElementMain extends PlanningElement {

  public $id;
  public $idProject;
  public $refType;
  public $refId;
  public $refName;
  public $_tab_4_2_smallLabel=array('validated','assigned', 'real', 'left', 'work','cost');
  public $validatedWork;
  public $assignedWork;
  public $realWork;
  public $leftWork;
  public $validatedCost;
  public $assignedCost;
  public $realCost;
  public $leftCost;
  //public $_tab_1_1=array('','priority');
  public $_tab_1_1_smallLabel_1 = array('', 'color');
  public $color;
  public $priority;
  public $idPokerSessionPlanningMode;
  
  private static $_fieldsAttributes=array(
      "initialStartDate"=>"hidden",
      "validatedStartDate"=>"hidden",
      "plannedStartDate"=>"hidden,noImport",
      "realStartDate"=>"hidden,noImport",
      "initialEndDate"=>"hidden",
      "validatedEndDate"=>"hidden",
      "plannedEndDate"=>"hidden,noImport",
      "realEndDate"=>"hidden,noImport",
      "initialDuration"=>"hidden",
      "validatedDuration"=>"hidden",
      "plannedDuration"=>"hidden,noImport",
      "realDuration"=>"hidden,noImport",
      "initialWork"=>"hidden",
      "validatedWork"=>"",
      "assignedWork"=>"readonly,noImport",
      "realWork"=>"readonly,noImport",
      "leftWork"=>"readonly,noImport",
      "plannedWork"=>"hidden,noImport",
      "notPlannedWork"=>"hidden",
      "initialCost"=>"hidden",
      "validatedCost"=>"",
      "assignedCost"=>"readonly,noImport",
      "realCost"=>"readonly,noImport",
      "leftCost"=>"readonly,noImport",
      "plannedCost"=>"hidden,noImport",
      "progress"=>"hidden,noImport",
      "expectedProgress"=>"hidden,noImport",
      "wbs"=>"hidden,noImport",
      "idPokerSessionPlanningMode"=>"hidden,required,noImport",
      "plannedStartFraction"=>"hidden",
      "plannedEndFraction"=>"hidden",
      "validatedStartFraction"=>"hidden",
      "validatedEndFraction"=>"hidden",
      "priority"=>"hidden"
  );   
  
  private static $_databaseTableName = 'planningelement';
  //private static $_databaseCriteria = array('refType'=>'Meeting'); // Cannot use auto filter as PeriodicMeeting is a Meeting (no PeriodicMeetingPlanningElement)
  
  private static $_databaseColumnName=array(
    "idPokerSessionPlanningMode"=>"idPlanningMode"
  );
  
  private static $_colCaptionTransposition = array('initialStartDate'=>'requestedStartDate',
      'initialEndDate'=> 'requestedEndDate',
      'initialDuration'=>'requestedDuration'
  );
  /** ==========================================================================
   * Constructor
   * @param $id Int the id of the object in the database (null if not stored yet)
   * @return void
   */ 
  function __construct($id = NULL, $withoutDependentObjects=false) {
    $this->idPokerSessionPlanningMode=16;
    parent::__construct($id,$withoutDependentObjects);
  }
  
  private function hideWorkCost() {
    unset($this->_tab_4_2_smallLabel);
  	self::$_fieldsAttributes['validatedWork']='hidden';
    self::$_fieldsAttributes['assignedWork']='hidden';
    self::$_fieldsAttributes['realWork']='hidden';
    self::$_fieldsAttributes['leftWork']='hidden';
    self::$_fieldsAttributes['validatedCost']='hidden';
    self::$_fieldsAttributes['assignedCost']='hidden';
    self::$_fieldsAttributes['realCost']='hidden';
    self::$_fieldsAttributes['leftCost']='hidden';
    //self::$_fieldsAttributes['priority']='hidden';
  }
  private function showWorkCost() {
  	$this->_tab_4_2_smallLabel = array('validated','assigned', 'real', 'left', 'work','cost');
  	//$this->_sec_progress=true;
    self::$_fieldsAttributes['validatedWork']='';
    self::$_fieldsAttributes['assignedWork']='readonly';
    self::$_fieldsAttributes['realWork']='readonly';
    self::$_fieldsAttributes['leftWork']='readonly';    
    self::$_fieldsAttributes['validatedCost']='';
    self::$_fieldsAttributes['assignedCost']='readonly';
    self::$_fieldsAttributes['realCost']='readonly';
    self::$_fieldsAttributes['leftCost']='readonly';
    //self::$_fieldsAttributes['priority']='';
  }
  
  // ADD BY Marc TABARY - 2017-02-16 - WORK AND COST VISIBILITY 
  private function showValidated() {
    $this->_tab_4_2_smallLabel = array('validated','assigned', 'real', 'left', 'work','cost');

    self::$_fieldsAttributes['validatedWork']='';
    self::$_fieldsAttributes['assignedWork']='hidden';
    self::$_fieldsAttributes['realWork']='hidden';
    self::$_fieldsAttributes['leftWork']='hidden';    
    self::$_fieldsAttributes['validatedCost']='';
    self::$_fieldsAttributes['assignedCost']='hidden';
    self::$_fieldsAttributes['realCost']='hidden';
    self::$_fieldsAttributes['leftCost']='hidden';
  }

  private function showOnlyWork() {
    $this->_tab_4_2_smallLabel = array('validated','assigned', 'real', 'left', 'work','cost');

    self::$_fieldsAttributes['validatedWork']='';
    self::$_fieldsAttributes['assignedWork']='readonly';
    self::$_fieldsAttributes['realWork']='readonly';
    self::$_fieldsAttributes['leftWork']='readonly';    
    self::$_fieldsAttributes['validatedCost']='hidden';
    self::$_fieldsAttributes['assignedCost']='hidden';
    self::$_fieldsAttributes['realCost']='hidden';
    self::$_fieldsAttributes['leftCost']='hidden';
  }
  
  private function showOnlyCost() {
    $this->_tab_4_2_smallLabel = array('validated','assigned', 'real', 'left', 'work','cost');

    self::$_fieldsAttributes['validatedWork']='hidden';
    self::$_fieldsAttributes['assignedWork']='hidden';
    self::$_fieldsAttributes['realWork']='hidden';
    self::$_fieldsAttributes['leftWork']='hidden';    
    self::$_fieldsAttributes['validatedCost']='';
    self::$_fieldsAttributes['assignedCost']='readonly';
    self::$_fieldsAttributes['realCost']='readonly';
    self::$_fieldsAttributes['leftCost']='readonly';
  }

  private function showOnlyValidatedWorkAndAllCost() {
    $this->_tab_4_2_smallLabel = array('validated','assigned', 'real', 'left', 'work','cost');

    self::$_fieldsAttributes['validatedWork']='';
    self::$_fieldsAttributes['assignedWork']='hidden';
    self::$_fieldsAttributes['realWork']='hidden';
    self::$_fieldsAttributes['leftWork']='hidden';    
    self::$_fieldsAttributes['validatedCost']='';
    self::$_fieldsAttributes['assignedCost']='readonly';
    self::$_fieldsAttributes['realCost']='readonly';
    self::$_fieldsAttributes['leftCost']='readonly';
  }

  private function hideWorkAndShowValidatedCost() {
    $this->_tab_4_2_smallLabel = array('validated','assigned', 'real', 'left', 'work','cost');

    self::$_fieldsAttributes['validatedWork']='hidden';
    self::$_fieldsAttributes['assignedWork']='hidden';
    self::$_fieldsAttributes['realWork']='hidden';
    self::$_fieldsAttributes['leftWork']='hidden';    
    self::$_fieldsAttributes['validatedCost']='';
    self::$_fieldsAttributes['assignedCost']='hidden';
    self::$_fieldsAttributes['realCost']='hidden';
    self::$_fieldsAttributes['leftCost']='hidden';
  }

  private function showAllWorkAndValidatedCost() {
    $this->_tab_4_2_smallLabel = array('validated','assigned', 'real', 'left', 'work','cost');

    self::$_fieldsAttributes['validatedWork']='';
    self::$_fieldsAttributes['assignedWork']='readonly';
    self::$_fieldsAttributes['realWork']='readonly';
    self::$_fieldsAttributes['leftWork']='readonly';    
    self::$_fieldsAttributes['validatedCost']='';
    self::$_fieldsAttributes['assignedCost']='hidden';
    self::$_fieldsAttributes['realCost']='hidden';
    self::$_fieldsAttributes['leftCost']='hidden';
  }
  
  private function showOnlyValidatedWorkAndHideCost() {
    $this->_tab_4_2_smallLabel = array('validated','assigned', 'real', 'left', 'work','cost');

    self::$_fieldsAttributes['validatedWork']='';
    self::$_fieldsAttributes['assignedWork']='hidden';
    self::$_fieldsAttributes['realWork']='hidden';
    self::$_fieldsAttributes['leftWork']='hidden';    
    self::$_fieldsAttributes['validatedCost']='hidden';
    self::$_fieldsAttributes['assignedCost']='hidden';
    self::$_fieldsAttributes['realCost']='hidden';
    self::$_fieldsAttributes['leftCost']='hidden';
  }
// END - ADD BY Marc TABARY - 2017-02-16 - WORK AND COST VISIBILITY 

  public function setAttributes() {
// MODIFY BY Marc TABARY - 2017-02-16 - WORK AND COST VISIBILITY
    if (!$this->_workVisibility or !$this->_costVisibility) $this->setVisibility();
    $workVisibility=$this->_workVisibility;
    $costVisibility=$this->_costVisibility;
    $wcVisibility = $workVisibility.$costVisibility;
    switch ($wcVisibility) {
        case "NONO" :
        $this->hideWorkCost();
            break;
        case "NOALL" :
            $this->showOnlyCost();
            break;
        case "NOVAL" :
            $this->hideWorkAndShowValidatedCost();
            break;
        case "ALLALL" :
          $this->showWorkCost();
            break;
        case "ALLNO" :
            $this->showOnlyWork();
            break;
        case "ALLVAL" :
            $this->showAllWorkAndValidatedCost();
            break;
        case "VALVAL" :
            $this->showValidated();
            break;
        case "VALALL" :
            $this->showOnlyValidatedWorkAndAllCost();
            break;
        case "VALNO" :
            $this->showOnlyValidatedWorkAndHideCost();
            break;
        default:
          $this->hideWorkCost();
            break;
      }
// END MODIFY BY Marc TABARY - 2017-02-16 - WORK AND COST VISIBILITY
  	//global $workVisibility,$costVisibility;
// COMMENT BY Marc TABARY - 2017-02-16 - WORK AND COST VISIBILITY
//    if (! $this->id) {
//      //$this->hideWorkCost();
//    } else {
//      if ($workVisibility!='ALL' or $costVisibility!='ALL') {
//        $this->hideWorkCost();
//      } else {
//        /*$ass=new Assignment();
//        $cptAss=$ass->countSqlElementsFromCriteria(array('refType'=>$this->refType, 'refId'=>$this->refId));
//        if ($cptAss>0) {*/
//          $this->showWorkCost();
//        /*} else {
//          $this->hideWorkCost();
//        } */
//      }
//    }
// END COMMENT BY Marc TABARY - 2017-02-16 - WORK AND COST VISIBILITY
    }
    /** ==========================================================================
   * Destructor
   * @return void
   */ 
  function __destruct() {
    parent::__destruct();
  }

    /** ========================================================================
   * Return the specific databaseTableName
   * @return String the databaseTableName
   */
  protected function getStaticDatabaseTableName() {
    $paramDbPrefix=Parameter::getGlobalParameter('paramDbPrefix');
    return $paramDbPrefix . self::$_databaseTableName;
  }
//   /** ========================================================================
//    * Return the specific database criteria
//    * @return String the databaseTableName
//    */
//   protected function getStaticDatabaseCriteria() {
//     return self::$_databaseCriteria;
//   }  
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
  /**=========================================================================
   * Overrides SqlElement::save() function to add specific treatments
   * @see persistence/SqlElement#save()
   * @return String the return message of persistence/SqlElement#save() method
   */
  public function save() {
  	$pokerSession=new $this->refType($this->refId);
  	$old=new PokerSessionPlanningElement($this->id);
  	if (!$this->id) {
  	  if (!$this->priority) {
  		  $this->priority=1; // very high priority
  	  }
  	}
  	$this->topRefType='Project';
  	$this->topRefId=$pokerSession->idProject;
  	if ($this->refType=='PokerSession') {
  	  $this->validatedStartDate=$pokerSession->pokerSessionDate;
  	  $this->plannedStartDate=$pokerSession->pokerSessionDate;
  	  if ($this->realStartDate) $this->realStartDate=$pokerSession->pokerSessionDate;
  	  $this->validatedEndDate=$pokerSession->pokerSessionDate;
  	  $this->plannedEndDate=$pokerSession->pokerSessionDate;
  	  if ($this->realStartDate) $this->realEndDate=$pokerSession->pokerSessionDate;    
  	}
  	
  	$this->validatedStartFraction=calculateFractionFromTime($pokerSession->pokerSessionStartTime);
  	$this->validatedDuration=calculateFractionBeetweenTimes($pokerSession->pokerSessionStartTime,$pokerSession->pokerSessionEndTime);
  	$this->validatedEndFraction=$this->validatedStartFraction+$this->validatedDuration;
  	
  	//$this->validatedWork=0;
    $this->idProject=$pokerSession->idProject;
    $this->refName=$pokerSession->name;
    $this->idle=$pokerSession->idle;
    if (isset($pokerSession->done)) {
      $this->done=$pokerSession->done;
    }
    if (! $this->assignedCost) $this->assignedCost=0;
    if (! $this->realCost) $this->realCost=0;
    if (! $this->leftCost) $this->leftCost=0;
    if (pq_trim($old->idProject)!=pq_trim($this->idProject) or pq_trim($old->topId)!=pq_trim($this->topId) 
    or pq_trim($old->topRefType)!=pq_trim($this->topRefType) or pq_trim($old->topRefId)!=pq_trim($this->topRefId)) {
    	$this->wbs=null; // Force recalculation
    	$this->topId=null;
    }
    return parent::save();
  }
  
/** =========================================================================
   * control data corresponding to Model constraints
   * @param void
   * @return "OK" if controls are good or an error message 
   *  must be redefined in the inherited class
   */
  public function control(){
    $result="";
    $mode=null;
    $pokerSession=new $this->refType($this->refId,true);
    if (! $this->idPokerSessionPlanningMode) {
    	$this->idPokerSessionPlanningMode=16;
    }
    if (!$this->priority) {
      $this->priority=1; // very high priority
    }
    if ($this->refType=='PokerSession') {
      if (! $pokerSession->pokerSessionDate) $pokerSession->pokerSessionDate=date('Y-m-d');
      $this->validatedStartDate=$pokerSession->pokerSessionDate;
      $this->validatedEndDate=$pokerSession->pokerSessionDate;
    }
    $defaultControl=parent::control();
    if ($defaultControl!='OK') {
      $result.=$defaultControl;
    }if ($result=="") {
      $result='OK';
    }
    return $result;
    
  }
}
?>