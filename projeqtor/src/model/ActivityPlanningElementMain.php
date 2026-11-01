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
class ActivityPlanningElementMain extends PlanningElement {

  public $id;
  public $idProject;
  public $refType;
  public $refId;
  public $refName;
  public $_separator_sectionDateAndDuration;
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
  public $_spe_isOnCriticalPath;
  public $_separator_sectionCostWork_marginTop;
  public $_tab_5_5_smallLabel_1 = array('validated', 'assigned', 'real', 'left', 'reassessed', 'work', 'cost','costLocal','expense','expenseLocal');
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
  public $expenseValidatedAmount;
  public $expenseAssignedAmount;
  public $expenseRealAmount;
  public $expenseLeftAmount;
  public $expensePlannedAmount;
  public $expenseValidatedAmountLocal;
  public $expenseAssignedAmountLocal;
  public $expenseRealAmountLocal;
  public $expenseLeftAmountLocal;
  public $expensePlannedAmountLocal;
  public $_separator_menuTechnicalProgress_marginTop;
  public $_tab_4_1_smallLabel_2 = array('toDeliver', 'toRealise', 'realised', 'left','workUnit');
  public $unitToDeliver;
  public $unitToRealise;
  public $unitRealised;
  public $unitLeft;
  public $_tab_5_1_smallLabel_8 = array('', '','','','','progress');
  public $unitProgress;
  public $idProgressMode;
  public $_label_weight;
  public $unitWeight;
  public $idWeightMode;
  public $_separator_sectionRevenue_marginTop;
  public $_tab_2_1_smallLabel = array('', '','CA');
  public $revenue;
  public $revenueLocal;
  public $_spe_idWorkUnits;
  public $_separator_menuReview_marginTop;
  public $_tab_5_2_smallLabel_3 = array('', '', '', '', '', 'progress','priority');
  public $progress;
  public $_label_expected;
  public $expectedProgress;
  public $_label_wbs;
  public $wbs;
  public $priority;
  public $_label_planning;
  public $idActivityPlanningMode;
  public $_tab_3_1_smallLabel_1 = array('', '', '','color');
  public $color;
  public $_label_hatchPattern;
  public $hatchPattern;
  public $_tab_3_1_3 = array('', '', '', 'minimumThreshold');
  public $minimumThreshold;
  public $_label_indivisibility;
  public $indivisibility;
  public $fixPlanning;
  public $_lib_helpFixPlanning;
  public $paused;
  public $_lib_helpPaused;
  public $_tab_5_1_smallLabel = array('workElementCount', 'estimated', 'real', 'left', '', 'ticket');
  public $workElementCount;
  public $workElementEstimatedWork;
  public $workElementRealWork;
  public $workElementLeftWork;
  public $_button_showTickets;
  //public $_label_wbs;
  //public $_label_progress;
  //public $_label_expected;
  public $wbsSortable;
  public $topId;
  public $topRefType;
  public $topRefId;
  public $idle;
  public $hasWorkUnit;
  
  private static $_fieldsAttributes=array(
    "plannedStartDate"=>"readonly,noImport",
    "realStartDate"=>"readonly,noImport",
    "plannedEndDate"=>"readonly,noImport",
    "realEndDate"=>"readonly,noImport",
    "plannedDuration"=>"readonly,noImport",
    "realDuration"=>"readonly,noImport",
    "initialWork"=>"hidden",
    "plannedWork"=>"readonly,noImport",
  	"notPlannedWork"=>"hidden",
    "realWork"=>"readonly,noImport",
    "leftWork"=>"readonly,noImport",
    "assignedWork"=>"readonly,noImport",
    "idActivityPlanningMode"=>"required,mediumWidth,colspan3",
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
    "_separator_menuTechnicalProgress_marginTop"=>"",
    "_separator_sectionRevenue_marginTop"=>"",
    "unitToDeliver"=>"",
    "unitToRealise"=>"",
    "unitRealised"=>"",
    "unitLeft"=>"",
    "unitProgress"=>"",
    "idProgressMode"=>"",
    "unitWeight"=>"",
    "hasWorkUnit"=>"hidden",
    "hatchPattern"=>""
  );

  private static $_fieldsTooltip = array(
  		"minimumThreshold"=> "tooltipMinimumThreshold",
  		"indivisibility"=> "tooltipIndivisibility",
      "fixPlanning"=> "tooltipFixPlanningActivity",
      "expectedProgress"=> "tooltipFixPlanningActivity",
      "paused"=>"tooltipPausedActivity"
  );
  
  private static $_databaseTableName = 'planningelement';
  //private static $_databaseCriteria = array('refType'=>'Activity'); // Bad idea : sets a mess when moving projets and possibly elsewhere.
  
  private static $_databaseColumnName=array(
    "idActivityPlanningMode"=>"idPlanningMode"
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
    parent::__construct($id,$withoutDependentObjects);
  }
  
  public function setAttributes() {
    global $contextForAttributes;
    $paramEnableWorkUnit = Parameter::getGlobalParameter('enableWorkCommandManagement');
    //if (Parameter::getGlobalParameter('PlanningActivity')=='YES') {
      $act=new Activity($this->refId,true);
      if ( ! $act->isPlanningActivity) {
        self::$_fieldsAttributes['workElementCount']='hidden';
        self::$_fieldsAttributes['workElementEstimatedWork']='hidden';
        self::$_fieldsAttributes['workElementRealWork']='hidden';
        self::$_fieldsAttributes['workElementLeftWork']='hidden';
        self::$_fieldsAttributes['_button_showTickets']='hidden';
      }
    //}
    if ($this->isAttributeSetToField('workElementCount', 'hidden')
    and $this->isAttributeSetToField('workElementEstimatedWork', 'hidden')
    and $this->isAttributeSetToField('workElementRealWork', 'hidden')
    and $this->isAttributeSetToField('workElementLeftWork', 'hidden')) {
      self::$_fieldsAttributes['_button_showTickets']='hidden';
    }
    $showLatest=Parameter::getGlobalParameter('showLatestDates');
    if ($showLatest) {
      self::$_fieldsAttributes['latestStartDate']="readonly";
      self::$_fieldsAttributes['latestEndDate']="readonly";
    }
    $user=getSessionUser();
    $priority=SqlElement::getSingleSqlElementFromCriteria('HabilitationOther',array('idProfile'=>$user->getProfile($this->idProject),'scope'=>'changeManualProgress'));
    if(!$this->isManualProgress or $priority and ($priority->rightAccess == 2 or ! $priority->id ) ){
      self::$_fieldsAttributes["progress"]='display';
    }else{
      self::$_fieldsAttributes["progress"]='';
    }
    $planningMode=new PlanningMode($this->idPlanningMode);
    $mode=$planningMode->code;
    if ($contextForAttributes!='multipleUpdate' and $mode!='ASAP' and $mode!='ALAP' and $mode!='START' and $mode!='STARR' and $mode!='GROUP') {
      $this->indivisibility=0;
      $this->minimumThreshold=0;
      self::$_fieldsAttributes["indivisibility"]='readonly';
      self::$_fieldsAttributes["minimumThreshold"]='readonly';
    } else {
      self::$_fieldsAttributes["indivisibility"]='';
      self::$_fieldsAttributes["minimumThreshold"]='';
    }
    if ($this->indivisibility){
      self::$_fieldsAttributes["minimumThreshold"]='required';
    }
    if($this->refId){
      $element=new $this->refType ($this->refId);
      if(property_exists($element, 'workOnRealTime') and $element->workOnRealTime==1){
        self::$_fieldsAttributes["validatedWork"]="readonly";
        self::$_fieldsAttributes["validatedCost"]="readonly";
        self::$_fieldsAttributes["_spe_idWorkUnits"]="hidden";
      }
    }
    if(Module::isModuleActive('moduleTechnicalProgress')){//Parameter::getGlobalParameter('technicalProgress')=='YES'
      self::$_fieldsAttributes['_separator_menuTechnicalProgress_marginTop']='';
      $asSon=$this->getSonItemsArray(true);
      if($asSon and count($asSon)>0){
        foreach ($asSon as $id=>$son ){
          if($son->refType!='Activity'){
            unset($asSon[$id]);
          }
        }
      }
      if(!$asSon or (!$this->id) or count($asSon)==0){
        if(!$this->id or $this->idProgressMode=='' or $this->idWeightMode=='' ){
          $this->idProgressMode=1;
          $this->idWeightMode=1;
          $this->unitToDeliver=0;
          $this->unitToRealise=0;
          $this->unitRealised=0;
          $this->unitLeft=0;
          $this->unitWeight=0;
          $this->unitProgress=0;
        }
        self::$_fieldsAttributes['unitToDeliver']='';
        self::$_fieldsAttributes['unitToRealise']='';
        self::$_fieldsAttributes['unitRealised']='';
        self::$_fieldsAttributes['unitLeft']='readonly';
        self::$_fieldsAttributes['unitProgress']='';
        self::$_fieldsAttributes['unitWeight']='';
        self::$_fieldsAttributes["_label_weight"]='';
        self::$_fieldsAttributes['idProgressMode']='size1/3,';
        self::$_fieldsAttributes['idWeightMode']='size1/3,';
      }else{
        if( $this->idProgressMode=='' or $this->idWeightMode=='' ){
          $this->idProgressMode=1;
          $this->idWeightMode=2;
        }
        if($this->unitProgress=='' or $this->unitWeight==''){
          $this->unitProgress=0;
          $this->unitWeight=0;
        }
        //unset($this->_tab_4_1_smallLabel_2);
        self::$_fieldsAttributes['unitProgress']='';
        self::$_fieldsAttributes['unitWeight']='';
        self::$_fieldsAttributes['idProgressMode']='readonly,size1/3';
        self::$_fieldsAttributes['idWeightMode']='size1/3';
      }
      if($this->idProgressMode==1){
        self::$_fieldsAttributes['unitProgress']='readonly';
      }
      if($this->idWeightMode!=1){
        self::$_fieldsAttributes['unitWeight']='readonly';
      }
       self::$_fieldsAttributes['_tab_2_1_smallLabel_8']='nobr';
    }else{
      unset($this->_separator_menuTechnicalProgress_marginTop);
      unset($this->_tab_5_1_smallLabel_8);
      unset($this->_tab_4_1_smallLabel_2);
      self::$_fieldsAttributes['unitToDeliver']='hidden,noimport';
      self::$_fieldsAttributes['unitToRealise']='hidden,noimport';
      self::$_fieldsAttributes['unitRealised']='hidden,noimport';
      self::$_fieldsAttributes['unitLeft']='hidden,noimport';
      self::$_fieldsAttributes['unitProgress']='hidden,noimport';
      self::$_fieldsAttributes['unitWeight']='hidden,noimport';
      self::$_fieldsAttributes["_label_weight"]='hidden, noimport';
      self::$_fieldsAttributes['idProgressMode']='hidden, noimport';
      self::$_fieldsAttributes['idWeightMode']='hidden, noimport';
    }
    $project = new Project($this->idProject);
    if(Module::isModuleActive('moduleGestionCA')){
      $user=getSessionUser();
      $profile=$user->getProfile($this->idProject);
      $visibility1=PlanningElement::getCostVisibility($profile);
      $visibility2=PlanningElement::getWorkVisibility($profile);
      if($visibility1!='NO' and $visibility2 != 'NO'){
        self::$_fieldsAttributes['_separator_sectionRevenue_marginTop']='';
      }
      if (isset($contextForAttributes) and $contextForAttributes=='global'){
        self::$_fieldsAttributes['revenue']='';
      }
      if($project->ProjectPlanningElement->idRevenueMode == 2){
      	if($this->elementary){
      	  self::$_fieldsAttributes['revenue']='';
        	if($this->hasWorkUnit){
        	  if($this->validatedDuration){
        	   self::$_fieldsAttributes['validatedDuration']='readonly';
        	  }
        	  self::$_fieldsAttributes['revenue']='readonly';
        	  self::$_fieldsAttributes['validatedWork']='readonly';
        	  $CaReplaceValidCost= Parameter::getGlobalParameter('CaReplaceValidCost');
        	  if($CaReplaceValidCost=='YES'){
        	    self::$_fieldsAttributes['validatedCost']='readonly';
        	  }
        	}else{
        	  $CaReplaceValidCost= Parameter::getGlobalParameter('CaReplaceValidCost');
        	  if($CaReplaceValidCost=='YES' and $this->revenue > 0){
        	    self::$_fieldsAttributes['validatedCost']='readonly';
        	  }
        	}
      	}else{
      	  if ($this->refType=='Activity') {
      	    // Non elementary Activity : Revenue Readonly only if it has children activities (activity main contain only Meeting on Milestone) 
      	    $cpt=$this->countSqlElementsFromCriteria(array('refType'=>'Activity','topRefType'=>'Activity','topRefId'=>$this->refId)); 
      	    if ($cpt>0) {
      	      self::$_fieldsAttributes['revenue']='readonly';
      	    } else {
      	      self::$_fieldsAttributes['revenue']='';
      	    }
      	  }
      	}
      }else{
      	//unset($this->_separator_sectionRevenue_marginTop);
        self::$_fieldsAttributes['_separator_sectionRevenue_marginTop']='hidden';
      	unset($this->_tab_5_1_smallLabel_3);
      }
    }
    if($this->paused==1){
      self::$_fieldsAttributes["fixPlanning"]='readonly,nobr';
    }
    
    if($this->topRefId!=''){
      $parent=new $this->topRefType($this->topRefId);
      
    }
    if (isset($element) and SqlList::getFieldFromId("Status", $element->idStatus, "setPausedStatus")!=0 or (isset($parent) and $parent->paused==1) ){
      self::$_fieldsAttributes["paused"]="readonly,nobr";
    }
    if(!Module::isModuleActive('moduleExpenses')){
      self::$_fieldsAttributes["expenseValidatedAmount"]="hidden";
      self::$_fieldsAttributes["expenseAssignedAmount"]="hidden";
      self::$_fieldsAttributes["expenseRealAmount"]="hidden";
      self::$_fieldsAttributes["expenseLeftAmount"]="hidden";
      self::$_fieldsAttributes["expensePlannedAmount"]="hidden";
      self::$_fieldsAttributes["expenseValidatedAmountLocal"]="hidden";
      self::$_fieldsAttributes["expenseAssignedAmountLocal"]="hidden";
      self::$_fieldsAttributes["expenseRealAmountLocal"]="hidden";
      self::$_fieldsAttributes["expenseLeftAmountLocal"]="hidden";
      self::$_fieldsAttributes["expensePlannedAmountLocal"]="hidden";
    }
    if($this->id){
      $proj= new Project();
      $count=$proj->countSqlElementsFromCriteria(array("id"=>$this->idProject,'codeType'=>'ADM'));
      if($count!=0){
        if(self::$_fieldsAttributes["fixPlanning"]!="hidden")self::$_fieldsAttributes["fixPlanning"]="hidden";
        if(self::$_fieldsAttributes["paused"]!="hidden")self::$_fieldsAttributes["paused"]="hidden";
        if(isset(self::$_fieldsAttributes["revenue"])){
          if(self::$_fieldsAttributes["revenue"]!="hidden")self::$_fieldsAttributes["revenue"]="hidden";
        }
        self::$_fieldsAttributes["priority"]="hidden";
        self::$_fieldsAttributes["idActivityPlanningMode"]="hidden,mediumWidth,colspan3";
        self::$_fieldsAttributes["minimumThreshold"]="hidden";
        self::$_fieldsAttributes["indivisibility"]="hidden";
        unset($this->_tab_5_2_smallLabel_3);
        unset($this->_separator_sectionRevenue_marginTop);
        unset($this->_spe_idWorkUnits);
        self::$_fieldsAttributes["_label_expected"]="hidden";
        self::$_fieldsAttributes["expectedProgress"]="hidden";
        self::$_fieldsAttributes["_label_wbs"]="hidden";
        self::$_fieldsAttributes["progress"]="hidden";
        if(! Module::isModuleActive('moduleTechnicalProgress')){
          unset($this->_separator_menuTechnicalProgress_marginTop);
          unset($this->_tab_5_1_smallLabel_8);
          unset($this->_tab_4_1_smallLabel_2);
          self::$_fieldsAttributes['unitToDeliver']="hidden";
          self::$_fieldsAttributes['unitToRealise']="hidden";
          self::$_fieldsAttributes['unitRealised']="hidden";
          self::$_fieldsAttributes['unitLeft']="hidden";
          self::$_fieldsAttributes['unitProgress']="hidden";
          self::$_fieldsAttributes['unitWeight']="hidden";
          self::$_fieldsAttributes["_label_weight"]="hidden";
          self::$_fieldsAttributes['idProgressMode']="hidden";
          self::$_fieldsAttributes['idWeightMode']="hidden";
        }
      }else{
        unset($this->_tab_5_1_smallLabel_4);
      }
    }else{
        unset($this->_tab_5_1_smallLabel_4);
    }
    if ($this->isAttributeSetToField("unitWeight", "hidden") and ! $this->isAttributeSetToField("_label_weight", "hidden")) {
      self::$_fieldsAttributes["_label_weight"]="hidden";
    }
    if ($this->id and $this->elementary==0) {
      self::$_fieldsAttributes['idActivityPlanningMode']="hidden,mediumWidth,colspan3";
    }
    if(Module::isModuleActive('moduleTechnicalProgress')){
      if (Parameter::getGlobalParameter('automaticChangeTechnicalProgress') == 'YES') {
        if ($this->refType == 'Activity' && $this->refId) {
          $act = new Activity($this->refId, true);
          $status = new Status($act->idStatus);
          if ($status->setDoneStatus) {
            if($this->elementary == 1){
              $idModeTechnicalPogressManual = SqlList::getIdFromTranslatableName('ProgressMode', 'manual');
              $idModeTechnicalPogressCalc   = SqlList::getIdFromTranslatableName('ProgressMode', 'calculated');
              if ($this->idProgressMode == $idModeTechnicalPogressManual) {
                self::$_fieldsAttributes['unitProgress'] = 'readonly';
              }
              if ($this->idProgressMode == $idModeTechnicalPogressCalc) {
                self::$_fieldsAttributes['unitToRealise'] = 'readonly';
                self::$_fieldsAttributes['unitRealised']  = 'readonly';
                self::$_fieldsAttributes['unitLeft']      = 'readonly';
                self::$_fieldsAttributes['unitProgress']  = 'readonly';
              }
            }
          }
        }
      }
    }
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
    if($this->idActivityPlanningMode){
      $this->idPlanningMode = $this->idActivityPlanningMode;
    }
    $old = $this->getOld();
    if($this->minimumThreshold){
      if($old->minimumThreshold != $this->minimumThreshold){
        $this->minimumThreshold = Work::convertWork($this->minimumThreshold);
      }
    }
    
    if($this->paused==1){
      if($this->fixPlanning!=1)$this->fixPlanning=1;
// PBER #10578
//       $this->plannedStartDate=null;
//       $this->plannedEndDate=null;
    }

    //florent
    if(($this->idPlanningMode=='23' and $old->idPlanningMode!='23')or($this->idPlanningMode!='23' and $old->idPlanningMode=='23') ){
      $pw= new PlannedWork();
      $ass=new Assignment();
      if($old->idPlanningMode=='23'){
        $pw= new PlannedWorkManual();
      }
      $clause= "idProject=".$this->idProject." and refType='".$this->refType."' and refId=".$this->refId;
      $pw->purge($clause);
      if($old->idPlanningMode!='23'){
        //$ass->plannedWork;
        $lstAss=$ass->getSqlElementsFromCriteria(null, null,$clause);
        if($lstAss){
          foreach ( $lstAss as $assign){
            if($assign->isResourceTeam==1){
              $assign->delete();
            }
            //$newLeft=$assign->leftWork-$assign->plannedWork;
            $assign->assignedWork=0;
            $assign->leftWork=0;
            $assign->plannedWork=$assign->realWork;
            $assign->assignedCost=0;
            $assign->leftCost=0;
            $assign->plannedCost=$assign->realCost;
            $assign->notPlannedWork=0;
            $assign->save();
          }
        }
      }
       //$this->updateSynthesis($this->refType, $this->refId);
    }
    if($this->plannedWork!=$old->plannedWork and $this->validatedWork!=$this->plannedWork){
      $act= new Activity($this->refId,true);
      if($act->workOnRealTime==1 ){
        $this->validatedWork=$this->plannedWork;
        $this->validatedCost=$this->plannedCost;
        $this->assignedCost=$this->plannedCost;
      }
    }
    if($this->elementary and $this->revenue > 0){
      $paramCA = Parameter::getGlobalParameter('CaReplaceValidCost');
      if($paramCA == 'YES' ) {
        // PBER - #10688
        $projectPE = SqlElement::getSingleSqlElementFromCriteria('PlanningElement', array('refType'=>'Project','refId'=>$this->idProject));
        //$project = new Project($this->idProject);
        //if (is_object($project->ProjectPlanningElement) and $project->ProjectPlanningElement->idRevenueMode == 2){
        if ($projectPE and $projectPE->id and $projectPE->idRevenueMode == 2){
          $this->validatedCost = $this->revenue;
        }
      }
    }
    
    if ($this->idActivityPlanningMode != $old->idActivityPlanningMode
        and PlanningMode::isProportionable($old->idActivityPlanningMode)
        and !PlanningMode::isProportionable($this->idActivityPlanningMode)) {
          
          $ass = new Assignment();
          $clause = "idProject=".$this->idProject
          . " and refType='".$this->refType."'"
              . " and refId=".$this->refId
              . " and proportional=1";
              
              $lstAss = $ass->getSqlElementsFromCriteria(null, null, $clause);
              
              if ($lstAss) {
                foreach ($lstAss as $assign) {
                  $assign->proportional = 0;
                  $assign->save();
                }
              }
        }
    
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
    $mode=null;
    if ($this->idActivityPlanningMode) {
      $mode=new ActivityPlanningMode($this->idActivityPlanningMode);
    }   
//     if ($mode) {
//       if ($mode->mandatoryStartDate and ! $this->validatedStartDate) {
//         $result.='<br/>' . i18n('errorMandatoryValidatedStartDate');
//       }
//       if ($mode->mandatoryEndDate and ! $this->validatedEndDate) {
//         $result.='<br/>' . i18n('errorMandatoryValidatedEndDate');
//       }
//       if ($mode->mandatoryDuration and ! $this->validatedDuration) {
//         $result.='<br/>' . i18n('errorMandatoryValidatedDuration');
//       }
   
//     }

    $old = $this->getOld();
    if($this->idActivityPlanningMode!='23' and $old->idPlanningMode=='23' and $this->plannedWork!='' and !SqlElement::isSaveConfirmed()){
      if(Parameter::getGlobalParameter('plannedWorkManualType')=="real" ){
        $result.='<br/>' . i18n('errorPlannedWorkManualType');
      }else{
        $result.='<br/>' . i18n('changePlanMan');
        $result.='<input type="hidden" name="confirmControl" id="confirmControl" value="save" />';
      }
    }else if($this->idActivityPlanningMode=='23' and $old->idPlanningMode!='23'){
      //gautier #4719
      $isPlannedWork = Parameter::getGlobalParameter('plannedWorkManualType');
      if($isPlannedWork =='planned'){
        $listAdmProj = Project::getAdminitrativeProjectList(true);
        if(in_array($this->idProject, $listAdmProj)){
          $result.='<br/>' . i18n('noPlannedWorkOnAdmProject');
        }
      }
      $ass=new Assignment();
      $critArray=array("idProject"=>$this->idProject,"refType"=>$this->refType,"refId"=>$this->refId);
      $assLst=$ass->getSqlElementsFromCriteria($critArray);
      $lstRes=array();
      foreach ($assLst as $ass){
         if(in_array($ass->idResource, $lstRes)){
           $result.='<br/>' . i18n('errorPlanWorkManDuplicate');
           break;
         }
         if($ass->isResourceTeam==1 and !SqlElement::isSaveConfirmed()){
           $result.='<br/>' . i18n('removePoolIntervention');
           $result.='<input type="hidden" name="confirmControl" id="confirmControl" value="save" />';
         }
        $lstRes["Assignement".$ass->id]=$ass->idResource;
      }
    }
    $defaultControl=parent::control();
    if ($defaultControl!='OK') {
      $result.=$defaultControl;
    }if ($result=="") {
      $result='OK';
    }
    return $result;
    
  }
  
  /** =========================================================================
   * Update the synthesis Data (work) from workElement (tipically Tickets)
   * Called by workElement
   * @return void
   */
  public function updateWorkElementSummary($noSave=false) {
    $we=new WorkElement();  	
  	$weList=$we->getSqlElementsFromCriteria(array('idActivity'=>$this->refId));
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
  	$top=new Activity($this->refId);
  	$param=Parameter::getGlobalParameter('limitPlanningActivity');
  	if($param != "YES"){
  	  if ($this->workElementCount==0 and $top->isPlanningActivity) {
  	    $top->isPlanningActivity=0;
  	    $top->saveForced();
  	  } else if ($this->workElementCount>0 and !$top->isPlanningActivity) {
  	     $top->isPlanningActivity=1;
  	     $top->saveForced();
  	  }
  	}
  }
  public function getValidationScript($colName) {
    $colScript = parent::getValidationScript ( $colName );
    if ($colName == "fixPlanning") {
      if(Parameter::getUserParameter('paramLayoutObjectDetail')=="tab"){
        $colScript .= '<script type="dojo/connect" event="onChange" >';
        $colScript .= ' dijit.byId("fixPlanning").set("value",dijit.byId("ActivityPlanningElement_fixPlanning").get("value"));';
        $colScript .= '  formChanged();';
        $colScript .= '</script>';
      }
    }else if($colName=="paused"){
      $colScript .= '<script type="dojo/connect" event="onChange" >';
      $colScript .= '  if(this.checked){';
      $colScript .= '   dijit.byId("ActivityPlanningElement_fixPlanning").set("readOnly",true);';
      $colScript .= '   dijit.byId("ActivityPlanningElement_fixPlanning").set("checked",true);';
      $colScript .= '   dijit.byId("ActivityPlanningElement_fixPlanning").set("value",1);';
      $colScript .= '   dijit.byId("fixPlanning").set("readOnly",true);';
      $colScript .= '  }else{';
      $colScript .= '   dijit.byId("ActivityPlanningElement_fixPlanning").set("readOnly",false);';
      $colScript .= '   dijit.byId("ActivityPlanningElement_fixPlanning").set("checked",false);';
      $colScript .= '   dijit.byId("ActivityPlanningElement_fixPlanning").set("value",0);';
      $colScript .= '   dijit.byId("fixPlanning").set("readOnly",false);';
      $colScript .= '  }';
      if(Parameter::getUserParameter('paramLayoutObjectDetail')=="tab"){
      $colScript .= ' dijit.byId("paused").set("value",dijit.byId("ActivityPlanningElement_fixPlanning").get("value"));';
      $colScript .= '  formChanged();';
      }
      $colScript .= '</script>';
    }else if ($colName=='validatedCost' or $colName=='expenseValidatedAmount') {
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
    if ($item=='showTickets') {
      echo '<div id="' . $item . 'Button" ';
      echo ' title="' . i18n('showTickets') . '" style="float:right;margin-right:3px;"';
      echo ' class="roundedButton">';
      echo '<div class="iconView iconSize16 imageColorNewGui" ';
      $jsFunction="showTickets('Activity',$this->refId);";
      echo ' onclick="' . $jsFunction . '"';
      echo '></div>';
      echo '</div>';
    } else if ($item=='isOnCriticalPath') {
      if ($this->id and $this->isOnCriticalPath and RequestHandler::getValue('criticalPathPlanning')) {
        echo '<div style="position:relative;"><div style="color:#AA0000;margin:0px 10px;text-align:center;position:absolute;top:-55px;height:60px;">'.i18n('colIsOnCriticalPath').'</div></div>';
      }
    }elseif ($item=='idWorkUnits'){
      $user=getSessionUser();
      $profile=$user->getProfile($this->idProject);
      $visibility1=PlanningElement::getCostVisibility($profile);
      $visibility2=PlanningElement::getWorkVisibility($profile);
      if( $visibility2 != 'NO'){
        if(Module::isModuleActive('moduleGestionCA') and $this->id){
          $project = new Project($this->idProject);
          if($project->ProjectPlanningElement->idRevenueMode == 2){
            $act = new Activity();
            $isParent = $act->countSqlElementsFromCriteria(array('idActivity'=>$this->refId));
            if(!$isParent){
              $activityWU = new ActivityWorkUnit();
              $listActWU = $activityWU->getSqlElementsFromCriteria(array('refId'=>$this->refId,'refType'=>'Activity'));
              $obj = new Activity($this->refId);
              drawActivityWorkUnit($listActWU,$obj,false,$visibility1);
            }
          }
        }
      }
    }
  }
  public function updateTotal() {
    $this->totalAssignedCost=$this->assignedCost+$this->expenseAssignedAmount;
    $this->totalLeftCost=$this->leftCost+$this->expenseLeftAmount;
    $this->totalPlannedCost=$this->plannedCost+$this->expensePlannedAmount;
    $this->totalRealCost=$this->realCost+$this->expenseRealAmount;
    $this->totalValidatedCost=$this->validatedCost+$this->expenseValidatedAmount;
    if ($this->plannedWork!=0 and $this->validatedWork!=0) {
      $this->marginWork=$this->validatedWork-$this->plannedWork;
      $this->marginWorkPct=round($this->marginWork/$this->validatedWork*100,0);
    } else {
      $this->marginWork=null;
      $this->marginWorkPct=null;
    }
    if ($this->totalPlannedCost and $this->totalValidatedCost) {
      $this->marginCost=$this->totalValidatedCost-$this->totalPlannedCost;
      $this->marginCostPct=round($this->marginCost/$this->totalValidatedCost*100,0);
    } else {
      $this->marginCost=null;
      $this->marginCostPct=null;
    }
    $this->plannedWork=$this->realWork+$this->leftWork; // Need to be done here to refrehed
    $this->plannedCost=$this->realCost+$this->leftCost;
  }
  
  protected function updateSynthesisActivity ($doNotSave=false) {
    parent::updateSynthesisObj(($doNotSave)?1:2); // Will update work and resource cost, but not save yet ;)
    $this->updateExpense(true); // Will retrieve expense directly on the project
    $this->addTicketWork(true); // Will add ticket work that is not linked to Activity
    $consolidateValidated=Parameter::getGlobalParameter('consolidateValidated');
    $hasSubActivity=false;
    //$this->_noHistory=true; // PBER #8671 - Removed here and added on PlanningElement::updateSynthesis - must save history on item but not consolidation
    // Add expense data from other planningElements
    $validatedExpense=0;
    $assignedExpense=0;
    $plannedExpense=0;
    $realExpense=0;
    $leftExpense=0;
    $validatedExpenseLocal=0;
    $assignedExpenseLocal=0;
    $plannedExpenseLocal=0;
    $realExpenseLocal=0;
    $leftExpenseLocal=0;
    if (! $this->elementary) {
        $hasSubActivity=true;
    		$critPla=array("refType"=>'Activity',"topId"=>$this->id);
    		$planningElement=new ActivityPlanningElement();
    		$plaList=$planningElement->getSqlElementsFromCriteria($critPla, false);
    		// Add data from other planningElements dependant from this one
    		foreach ($plaList as $pla) {
    		  if ($pla->refType=='Activity') $hasSubProjects=true;
    		  if (!$pla->cancelled and $pla->expenseValidatedAmount) $validatedExpense+=$pla->expenseValidatedAmount;
    		  if (!$pla->cancelled and $pla->expenseValidatedAmountLocal) $validatedExpenseLocal+=$pla->expenseValidatedAmountLocal;
    		  if (!$pla->cancelled and $pla->expenseAssignedAmount) $assignedExpense+=$pla->expenseAssignedAmount;
    		  if (!$pla->cancelled and $pla->expenseAssignedAmountLocal) $assignedExpenseLocal+=$pla->expenseAssignedAmountLocal;
    		  if (!$pla->cancelled and $pla->expensePlannedAmount) $plannedExpense+=$pla->expensePlannedAmount;
    		  if (!$pla->cancelled and $pla->expensePlannedAmountLocal) $plannedExpenseLocal+=$pla->expensePlannedAmountLocal;
    		  $realExpense+=$pla->expenseRealAmount;
    		  $realExpenseLocal+=$pla->expenseRealAmountLocal;
    		  if (!$pla->cancelled and $pla->expenseLeftAmount) $leftExpense+=$pla->expenseLeftAmount;
    		  if (!$pla->cancelled and $pla->expenseLeftAmountLocal) $leftExpenseLocal+=$pla->expenseLeftAmountLocal;
    		  if ( !$pla->cancelled and $pla->realEndDate and $this->realEndDate and $pla->realEndDate>$this->realEndDate ) {
    		    $this->realEndDate=$pla->realEndDate;
    		  } 
    		}
    }
    if($hasSubActivity){
      $this->idRevenueMode = 2;
    }
    // save cumulated data
    $this->expenseAssignedAmount+=$assignedExpense;
    $this->expensePlannedAmount+=$plannedExpense;
    $this->expenseRealAmount+=$realExpense;
    $this->expenseLeftAmount+=$leftExpense;
    if ($this->hasCurrency()) {
      $this->expenseAssignedAmountLocal+=$assignedExpenseLocal;
      $this->expensePlannedAmountLocal+=$plannedExpenseLocal;
      $this->expenseRealAmountLocal+=$realExpenseLocal;
      $this->expenseLeftAmountLocal+=$leftExpenseLocal;
    } else {
      $this->expenseAssignedAmountLocal=0;
      $this->expensePlannedAmountLocal=0;
      $this->expenseRealAmountLocal=0;
      $this->expenseLeftAmountLocal=0;
      $this->expenseValidatedAmountLocal=0;
    }
    if ($consolidateValidated=="ALWAYS") {
    		$this->expenseValidatedAmount=$validatedExpense;
    		if ($this->hasCurrency()) { $this->expenseValidatedAmountLocal=$validatedExpenseLocal;}
    		else { $this->expenseValidatedAmountLocal=0;}
    		if ($hasSubActivity) $this->validatedExpenseCalculated=1;
    } else if ($consolidateValidated=="IFSET") {
    		if ($validatedExpense or $validatedExpenseLocal) {
    		  $this->expenseValidatedAmount=$validatedExpense;
    		  if ($this->hasCurrency()) { $this->expenseValidatedAmountLocal=$validatedExpenseLocal; }
    		  else { $this->expenseValidatedAmountLocal=0; }
    		  if ($hasSubActivity) $this->validatedExpenseCalculated=1;
    		}
    }
    if (!$doNotSave) $resultSaveAct=$this->save();
  }
  
  public function updateExpense($doNotSave=false) {
    $exp=new Expense();
    $paramInputExpense = Parameter::getGlobalParameter('ImputOfAmountProvider');
    $lstExp=$exp->getSqlElementsFromCriteria(array('idActivity'=>$this->refId,'cancelled'=>'0'));
    $assigned=0;
    $real=0;
    $planned=0;
    $left=0;
    $assignedLocal=0;
    $realLocal=0;
    $plannedLocal=0;
    $leftLocal=0;
    foreach ($lstExp as $exp) {
  		if ($exp->plannedAmount) {
  		  if ($paramInputExpense=='TTC') {$assigned+=$exp->plannedFullAmount; $assignedLocal+=$exp->plannedFullAmountLocal;}
  		  else {$assigned+=$exp->plannedAmount; $assignedLocal+=$exp->plannedAmountLocal;}
  		}
  		if ($exp->realAmount) {
  		  if ($paramInputExpense=='TTC') {$real+=$exp->realFullAmount; $realLocal+=$exp->realFullAmountLocal;}
  		  else { $real+=$exp->realAmount; $realLocal+=$exp->realAmountLocal;}
  		} else {
  		  if ($exp->plannedAmount) {
  		    if ($paramInputExpense=='TTC') {$left+=$exp->plannedFullAmount; $leftLocal+=$exp->plannedFullAmountLocal;}
  		    else {$left+=$exp->plannedAmount; $leftLocal+=$exp->plannedAmountLocal;}
  		  }
  		}
    }
    $planned=$real+$left;
    $plannedLocal=$realLocal+$leftLocal;
    $this->expenseAssignedAmount=$assigned;
    $this->expenseLeftAmount=$left;
    $this->expensePlannedAmount=$planned;
    $this->expenseRealAmount=$real;
    if ($this->hasCurrency()) {
      $this->expenseAssignedAmountLocal=$assignedLocal;
      $this->expenseLeftAmountLocal=$leftLocal;
      $this->expensePlannedAmountLocal=$plannedLocal;
      $this->expenseRealAmountLocal=$realLocal;
    } else {
      $this->expenseAssignedAmountLocal=0;
      $this->expenseLeftAmountLocal=0;
      $this->expensePlannedAmountLocal=0;
      $this->expenseRealAmountLocal=0;
    }
    if (!$doNotSave and !$this->elementary) {
      $critPla=array("refType"=>'Activity',"topId"=>$this->id);
      $plaList=$this->getSqlElementsFromCriteria($critPla, false);
      // Add data from other planningElements dependant from this one
      foreach ($plaList as $pla) {
        // if (!$pla->cancelled and $pla->expenseValidatedAmount) $this->expenseValidatedAmount+=$pla->expenseValidatedAmount;
        if (!$pla->cancelled and $pla->expenseAssignedAmount) $this->expenseAssignedAmount+=$pla->expenseAssignedAmount;
        if (!$pla->cancelled and $pla->expensePlannedAmount) $this->expensePlannedAmount+=$pla->expensePlannedAmount;
        if (!$pla->cancelled and $pla->expenseLeftAmount) $this->expenseLeftAmount+=$pla->expenseLeftAmount;
        if ($pla->expenseRealAmount) $this->expenseRealAmount+=$pla->expenseRealAmount;
        if ($this->hasCurrency()) {
          if (!$pla->cancelled and $pla->expenseAssignedAmountLocal) $this->expenseAssignedAmountLocal+=$pla->expenseAssignedAmountLocal;
          if (!$pla->cancelled and $pla->expensePlannedAmountLocal) $this->expensePlannedAmountLocal+=$pla->expensePlannedAmountLocal;
          if (!$pla->cancelled and $pla->expenseLeftAmountLocal) $this->expenseLeftAmountLocal+=$pla->expenseLeftAmountLocal;
          if ($pla->expenseRealAmount) $this->expenseRealAmountLocal+=$pla->expenseRealAmountLocal;
        }
      }
    }
    $this->updateTotal();
    if (! $doNotSave) {
    		$this->simpleSave();
    		if ($this->topId) {
    		  self::updateSynthesis($this->topRefType, $this->topRefId);
    		}
    		// ADD BY Marc TABARY - 2017-02-17 - EXPENSE CONSOLIDATION ON ORGANIZATION
    		// Update BudgetElement of the project's organization (if necessary)
    		if(isset($this->idOrganization) and $this->idOrganization and pq_trim($this->idOrganization)!='') {
    		  $orga = new Organization($this->idOrganization);
    		  $orga->updateSynthesis();
    		}
    		// END ADD BY Marc TABARY - 2017-02-17 - EXPENSE CONSOLIDATION ON ORGANIZATION
    }
  }
  public function addTicketWork($doNotSave=false) {
    //$crit=array('idProject'=>$this->refId,'idActivity'=>null);
    $where='idActivity='.$this->refId; $crit=null;
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
?>