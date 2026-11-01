<?php
/*
 *	@author: qCazelles 
 */

require_once('_securityCheck.php');
class ActivityWorkUnit extends SqlElement {
	public $id;   
  public $refType;
  public $refId;
  public $idWorkUnit;
  public $idComplexity;
  public $quantity;
  public $idWorkCommand;
  	
	private static $_databaseCriteria = array();
	/** ========================================================================
	 * Return the specific database criteria
	 * @return String the databaseTableName
	 */
	protected function getStaticDatabaseCriteria() {
	  return self::$_databaseCriteria;
	}
	
	/** ==========================================================================
	 * Construct
	 * @return void
	 */
	function __construct($id = NULL, $withoutDependentObjects=false) {
		parent::__construct($id,$withoutDependentObjects);
	}
	
	
	public function control() {
	  $result = "";
	  $old = $this->getOld(false);
	  
	  $defaultControl=parent::control();
    if ($defaultControl!='OK') {
      $result.=$defaultControl;
    }
	  
	  if($this->idWorkCommand and $this->idWorkCommand != " " and $this->idWorkCommand != ''){
	    $workCommand = new WorkCommand($this->idWorkCommand);
	    $newWorkCommandDone = new WorkCommandDone();
	    $lstWorkCommand = $newWorkCommandDone->getSqlElementsFromCriteria(array('idWorkCommand'=>$this->idWorkCommand,'idCommand'=>$workCommand->idCommand));
	    $quantity = $this->quantity;
	    foreach ($lstWorkCommand as $comVal){
	      if($comVal->refType == 'Activity' and $comVal->idActivityWorkUnit == $this->id){
	        continue;
	      }else{
	        $quantity += $comVal->doneQuantity;
	      }
	    }
	    if($quantity > $workCommand->commandQuantity){
	      $result.='<br/>' . i18n('errorQuantityCantBeSuperiorThanCommand');
	    }
	  }
	  
	  if ($result == "") {
	    $result = 'OK';
	  }
	  
	  return $result;
	}
	
	public function saveActivityWorkUnit() {
	  $result = '';
	  if(!$this->refType)$this->refType='Activity';
	  if($this->refType !='Activity' and $this->refType){
	    $result .='<br/>' . i18n('refTypeMustBeActivity');
	  }
    if($this->quantity < 1){
      $result .='<br/>' . i18n('quantity0');
    }
    if(!$this->idComplexity){
      $result .='<br/>' . i18n('noIdComplexity');
    }
    if(!$this->idWorkUnit){
      $result .='<br/>' . i18n('noIdWorkUnit');
    }
    if($this->refId){
      $act=new Activity($this->refId,true);
      if(!$act->id)$result .='<br/>' . i18n('noMatchActivity');
      if($act->workOnRealTime)$result .='<br/>' . i18n('ActivityIsWorkOnRealTime');
      $workUnit = new WorkUnit($this->idWorkUnit,true);
      //$catalog = new CatalogUO($workUnit->idCatalogUO,true);
      $proj=new Project($act->idProject,true);
      if($act->id and $proj->idCatalogUO != $workUnit->idCatalogUO) $result .='<br/>' . i18n('CatalogProjectIsNotTheSame');
      if($this->idWorkCommand){
        $workCommand = new WorkCommand($this->idWorkCommand,true);
        $command = new Command($workCommand->idCommand,true);
        if($act->idProject != $command->idProject)$result .='<br/>' . i18n('CommandIsNotOnTheSameProject');
        if($workCommand->idComplexity != $this->idComplexity )$result .='<br/>' . i18n('idComplexityNoMatch');
        if($workCommand->idWorkUnit != $this->idWorkUnit )$result .='<br/>' . i18n('idWorkUnitNoMatch');
        if(!$result){
          $workCommand = new WorkCommand($this->idWorkCommand);
          $workCommandDone = new WorkCommandDone();
          $newWorkCommandDone = new WorkCommandDone();
          $workCommandDoneExist = $workCommandDone->getSingleSqlElementFromCriteria('WorkCommandDone', array('idActivityWorkUnit'=>$this->idWorkUnit,'idWorkCommand'=>$this->idWorkCommand,'refId'=>$this->refId,'refType'=>'Activity','idCommand'=>$command->id));
          if($workCommandDoneExist){
            $workCommandDone = new WorkCommandDone($workCommandDoneExist->id);
          }
          $workCommandDone->idCommand = $command->id;
          $workCommandDone->idWorkCommand = $this->idWorkCommand;
          $workCommandDone->refType = "Activity";
          $workCommandDone->refId = $this->refId;
          $workCommandDone->doneQuantity = $this->quantity;
          $workCommandDone->idActivityWorkUnit = $this->idWorkUnit;
          $workCommandDone->save();
          $lstWorkCommand = $newWorkCommandDone->getSqlElementsFromCriteria(array('idWorkCommand'=>$this->idWorkCommand,'idCommand'=>$command->id));
          $quantity = 0;
          foreach ($lstWorkCommand as $comVal){
            $quantity += $comVal->doneQuantity;
          }
          $workCommand->doneQuantity = $quantity;
          $workCommand->doneAmount = $workCommand->unitAmount * $quantity;
          $workCommand->doneAmountLocal = $workCommand->unitAmountLocal * $quantity;
          $workCommand->save();
        }
      }
    }
    if($result==''){
	   $result .= $this->save();
    }
	  return $result;
	}
	
	public function save() {
	  $result = parent::save();
	  
	  $act = new Activity($this->refId);
	  $oldValidatedWork=$act->ActivityPlanningElement->validatedWork;
	  $CaReplaceValidCost= Parameter::getGlobalParameter('CaReplaceValidCost');
	  if($CaReplaceValidCost=='YES'){
	    $act->ActivityPlanningElement->validatedCost = 0;
	  }
	  $activityWorkUnit = new ActivityWorkUnit();
	  $lstActWorkUnit = $activityWorkUnit->getSqlElementsFromCriteria(array('refType'=>'Activity','refId'=>$this->refId));
	  $act->ActivityPlanningElement->validatedWork = 0;
	  $act->ActivityPlanningElement->revenue = 0;
	  $act->ActivityPlanningElement->revenueLocal = 0;
	  foreach ($lstActWorkUnit as $actWork){
	    $complexityVal = SqlElement::getSingleSqlElementFromCriteria('ComplexityValues', array('idWorkUnit'=>$actWork->idWorkUnit,'idComplexity'=>$actWork->idComplexity));
	    $act->ActivityPlanningElement->validatedWork += $complexityVal->charge*$actWork->quantity;
	    $act->ActivityPlanningElement->revenue += $complexityVal->price*$actWork->quantity;
	    $act->ActivityPlanningElement->revenueLocal += $complexityVal->priceLocal*$actWork->quantity;
	  }
	  $ass = new Assignment();
	  $lstAss = $ass->getSqlElementsFromCriteria(array('refType'=>'Activity','refId'=>$act->ActivityPlanningElement->refId));
	  $totalValidatedWork = 0;
	  foreach ($lstAss as $asVal){
	    if ($act->ActivityPlanningElement->idle) continue;
	    $totalValidatedWork += $asVal->assignedWork;
	  }
    //if($totalValidatedWork < $act->ActivityPlanningElement->validatedWork and $totalValidatedWork>0 ){
    if( $totalValidatedWork>0){
      $factor = ($oldValidatedWork!=0)?$act->ActivityPlanningElement->validatedWork / $oldValidatedWork:$act->ActivityPlanningElement->validatedWork/$totalValidatedWork;
      $sumAssignedWork=0;
      $sumLeftWork=0;
      $sumAssignedCost=0;
      $sumLeftCost=0;
      foreach ($lstAss as $asVal){
        if (! $asVal->idle) {
          $asVal->_skipDispatch=true;
          $newLeftWork = ($asVal->assignedWork*$factor) - ($asVal->assignedWork) ;
          $asVal->assignedWork = round($asVal->assignedWork*$factor,3);
          $asVal->leftWork = round($asVal->leftWork+$newLeftWork,3);
          if($asVal->leftWork < 0)$asVal->leftWork=0;
          $asVal->save();
        }
        $sumAssignedWork+=$asVal->assignedWork;
        $sumLeftWork+=$asVal->leftWork;
        $sumAssignedCost+=$asVal->assignedCost;
        $sumLeftCost+=$asVal->leftCost;
      }
      $act->ActivityPlanningElement->assignedWork=$sumAssignedWork;
      $act->ActivityPlanningElement->leftWork=$sumLeftWork;
      $act->ActivityPlanningElement->plannedWork=$act->ActivityPlanningElement->realWork+$act->ActivityPlanningElement->leftWork;
      $act->ActivityPlanningElement->assignedCost=$sumAssignedCost;
      $act->ActivityPlanningElement->leftCost=$sumLeftCost;
      $act->ActivityPlanningElement->plannedCost=$act->ActivityPlanningElement->realCost+$act->ActivityPlanningElement->leftCost;
      $act->ActivityPlanningElement->_workHistory=true; // Will force to update data (it's a hack)
    }
    // TODO : PBER check validity $actWork is in a loop...
    if($CaReplaceValidCost=='YES' and $act->ActivityPlanningElement->revenue>0){
      //$act->ActivityPlanningElement->validatedCost += $complexityVal->price*$actWork->quantity;
      $act->ActivityPlanningElement->validatedCost=$act->ActivityPlanningElement->revenue;
    }
    if($CaReplaceValidCost=='YES' and $act->ActivityPlanningElement->revenueLocal>0){
      //$act->ActivityPlanningElement->validatedCost += $complexityVal->price*$actWork->quantity;
      $act->ActivityPlanningElement->validatedCostLocal=$act->ActivityPlanningElement->revenueLocal;
    }
	  $act->save();
	  
	  return $result;
	}
	

	/** ==========================================================================
	 * Destructor
	 * @return void
	 */
	function __destruct() {
		parent::__destruct();
	}
	/**
	 * ========================================================================
	 * Return the specific databaseColumnName
	 *
	 * @return String the databaseTableName
	 */
	
	
}