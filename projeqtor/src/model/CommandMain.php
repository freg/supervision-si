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

/** ============================================================================
 * CommandMain
 */  
require_once('_securityCheck.php');
 
class CommandMain extends SqlElement {

  // List of fields that will be exposed in general user interface
  public $_sec_description;
  public $id;    // redefine $id to specify its visible place 
  public $reference;
  public $name;
  public $idProject;
  public $idCommandType;
  public $idRecipient;
  public $idClient;
  public $idContact;
  public $externalReference;  
  public $receptionDate;
  public $idDeliveryMode;
  public $idUser;
  public $creationDate;
  public $Origin;
  public $description;
  public $additionalInfo;
  public $_sec_treatment;
  public $idStatus;
  public $idResource;  
  public $handled;
  public $handledDate;
  public $done;
  public $doneDate;
  public $idle;
  public $idleDate;
  public $cancelled;
  public $_lib_cancelled;
  public $idActivityType;
  public $idActivity;
  public $idPaymentDelay;
  public $_tab_5_6_smallLabel = array('untaxedAmountShort', 'tax', '', 'fullAmountShort','work', 'initial','initialLocal', 'add','addLocal', 'countTotal','countTotalLocal');
  public $untaxedAmount;
  public $taxPct;
  public $taxAmount;
  public $fullAmount;
  public $initialWork;
  public $untaxedAmountLocal;
  public $taxPctLocal;
  public $taxAmountLocal;
  public $fullAmountLocal;
  public $initialWorkLocal;
  public $addUntaxedAmount;
  public $_void_3_2;
  public $addTaxAmount;
  public $addFullAmount;
  public $addWork;
  public $addUntaxedAmountLocal;
  public $_void_4_2;
  public $addTaxAmountLocal;
  public $addFullAmountLocal;
  public $addWorkLocal;
  public $totalUntaxedAmount;
  public $_void_5_2;
  public $totalTaxAmount;
  public $totalFullAmount;
  public $validatedWork;
  public $totalUntaxedAmountLocal;
  public $_void_6_2;
  public $totalTaxAmountLocal;
  public $totalFullAmountLocal;
  public $validatedWorkLocal;
  public $initialPricePerDayAmount;
  public $addPricePerDayAmount;
  public $validatedPricePerDayAmount;
  public $_tab_2_2_smallLabel = array('initial', 'validated', 'startDate', 'endDate');
  public $initialStartDate;
  public $validatedStartDate;
  public $initialEndDate;
  public $validatedEndDate;
  public $comment;
  //public $_sec_BillLine;
  public $_BillLine=array();
  public $_BillLine_colSpan="2";
  public $_sec_WorkCommand;
  public $_spe_WorkCommand;
  public $_sec_situation;
  public $idSituation;
  public $_spe_situation;
  public $_sec_Link;
  public $_Link=array();
  public $_Attachment=array();
  public $_Note=array();
  public $_nbColMax=3;
  
  // Define the layout that will be used for lists
  private static $_layout='
    <th field="id" formatter="numericFormatter" width="5%" ># ${id}</th>
    <th field="nameProject" width="10%" >${idProject}</th>
    <th field="nameCommandType" width="10%" >${idCommandType}</th>
    <th field="name" width="15%" >${name}</th>
    <th field="colorNameStatus" width="10%" formatter="colorNameFormatter">${idStatus}</th>
    <th field="nameResource" formatter="thumbName22" width="10%" >${responsible}</th>
    <th field="validatedEndDate" width="10%" formatter="dateFormatter" >${validatedEndDate}</th>
  	<th field="untaxedAmount" formatter="costFormatter" width="10%" >${untaxedAmount}</th>
  	<th field="addUntaxedAmount" formatter="costFormatter" width="10%" >${addUntaxedAmount}</th>
  	<th field="totalUntaxedAmount" formatter="costFormatter" width="10%" >${totalUntaxedAmount}</th>
    ';

  private static $_fieldsAttributes=array("id"=>"nobr", "reference"=>"readonly",
                                  "name"=>"required", 
                                  "idCommandType"=>"required",
                                  "idStatus"=>"required",
                                  "handled"=>"nobr",
                                  "done"=>"nobr",
                                  "idle"=>"nobr",
                                  "idPaymentDelay"=>"hidden",
						  							      "taxAmount"=>"calculated,readonly",
                                  "addTaxAmount"=>"calculated,readonly",
                                  "totalTaxAmount"=>"calculated,readonly",
                                  "taxAmountLocal"=>"calculated,readonly",
                                  "addTaxAmountLocal"=>"calculated,readonly",
                                  "totalTaxAmountLocal"=>"calculated,readonly",
                                  "totalFullAmount"=>"readonly",
                                  "totalUntaxedAmount"=>"readonly",
						  							      "externalReference"=>"required",
                                  "idleDate"=>"nobr",
                                  "cancelled"=>"nobr", 
                                  "validatedWork"=>"readonly",
                                  "validatedWorkLocal"=>"readonly",
                                  "initialPricePerDayAmount"=>"hidden",
                                  "addPricePerDayAmount"=>"hidden",
                                  "validatedPricePerDayAmount"=>"hidden",
                                  "idProject"=>"required",
                                  "idSituation"=>"readonly",
                                   "taxPctLocal"=>"calculated","initialWorkLocal"=>"calculated","addWorkLocal"=>"calculated","validatedWorkLocal"=>"calculated,readonly"

  );  
  
  private static $_colCaptionTransposition = array('idUser'=>'issuer', 
                                                   'idResource'=> 'responsible',
  													                       'idActivity'=>'linkActivity',
                                                   'idDeliveryMode'=>'receiveMode', 
                                                   'idSituation'=>'actualSituation');
  private static $_databaseColumnName = array('taxPct'=>'tax'); 
    
   /** ==========================================================================
   * Constructor
   * @param $id Int the id of the object in the database (null if not stored yet)
   * @return void
   */ 
  function __construct($id = NULL, $withoutDependentObjects=false) {
    parent::__construct($id,$withoutDependentObjects);
    if ($withoutDependentObjects) return;
    if ($this->id) {
    	self::$_fieldsAttributes["creationDate"]='readonly';
    } else {
      $this->receptionDate=date('Y-m-d');
    }
    if ($this->hasCurrency()) {
      $this->taxPctLocal=$this->taxPct;
      $this->initialWorkLocal=$this->initialWork;
      $this->addWorkLocal=$this->addWork;
      $this->validatedWorkLocal=$this->validatedWork;
    }
    /*$status=new Status($this->idStatus);
    if ($status->isCopyStatus) {
    	self::$_fieldsAttributes["externalReference"]="";
    }*/
    if ($this->fullAmount) {
      $this->taxAmount=$this->fullAmount-$this->untaxedAmount;
      $this->addTaxAmount=$this->addFullAmount-$this->addUntaxedAmount;
      $this->totalTaxAmount=$this->totalFullAmount-$this->totalUntaxedAmount;
    }
    if ($this->fullAmountLocal) {
      $this->taxAmountLocal=$this->fullAmountLocal-$this->untaxedAmountLocal;
      $this->addTaxAmountLocal=$this->addFullAmountLocal-$this->addUntaxedAmountLocal;
      $this->totalTaxAmountLocal=$this->totalFullAmountLocal-$this->totalUntaxedAmountLocal;
    }
    if(pq_trim(Module::isModuleActive('moduleSituation')) != 1){
    	self::$_fieldsAttributes['_sec_situation']='hidden';
    	self::$_fieldsAttributes['idSituation']='hidden';
    }
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
  
  /** ==========================================================================
   * Return the specific layout
   * @return String the layout
   */
  protected function getStaticLayout() {
    return self::$_layout;
  }
  
  /** ==========================================================================
   * Return the specific fieldsAttributes
   * @return Array the fieldsAttributes  
   */
  protected function getStaticFieldsAttributes() {
    return self::$_fieldsAttributes;
  }
  
  /** ============================================================================
   * Return the specific colCaptionTransposition
   * @return String the colCaptionTransposition
   */
  protected function getStaticColCaptionTransposition($fld=null) {
    return self::$_colCaptionTransposition;
  }

  /** ========================================================================
   * Return the specific databaseTableName
   * @return String the databaseTableName
   */
  protected function getStaticDatabaseColumnName() {
    return self::$_databaseColumnName;
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
   	}
   	
   	if ($result=="") $result='OK';
	
    return $result;
  }

  
  /** =========================================================================
   * Overrides SqlElement::deleteControl() function to add specific treatments
   * @see persistence/SqlElement#deleteControl()
   * @return String the return message of persistence/SqlElement#deleteControl() method
   */  
  
  /**=========================================================================
   * Overrides SqlElement::save() function to add specific treatments
   * @see persistence/SqlElement#save()
   * @return String the return message of persistence/SqlElement#save() method
   */
  public function save() {
  	$result='';
  	
  	$oldIdProject=0;
  	$oldTotalUntaxedAmount=0;
  	$oldTotalUntaxedAmountLocal=0;
  	$oldValidatedWork=0;
  	$old=$this->getOld();
  	
  	//Check if we are in CREATION
    if (pq_trim($this->id)=='') {
    	// fill the creatin date if it's empty - creationDate is not empty for import ! 
    	if ($this->creationDate=='') $this->creationDate=date('Y-m-d H:i');
  	} else {
  		$oldIdProject=$old->idProject;
  		$oldTotalUntaxedAmount=$old->totalUntaxedAmount;
  		$oldTotalUntaxedAmountLocal=$old->totalUntaxedAmountLocal;
  		$oldValidatedWork=$old->validatedWork;
  	}
  
  	if (pq_trim($this->idClient)) {
  	  $client=new Client($this->idClient);
  	  if ($client->taxPct!='' and !$this->taxPct) {
  	    $this->taxPct=$client->taxPct;
  	  }
  	}
  	$paramImputOfBillLineClient = Parameter::getGlobalParameter('ImputOfBillLineClient');
  	$billLine=new BillLine();
  	$crit = array("refType"=> "Command", "refId"=>$this->id);
  	$billLineList = $billLine->getSqlElementsFromCriteria($crit,false);
  	if (count($billLineList)>0) {
  	  $amount=0;
  	  $amountLocal=0;
  	  $addAmount=0;
  	  $addAmountLocal=0;
  	  $work=0;
  	  $addWork=0;
  	  foreach ($billLineList as $line) {
  	    if ($line->extra) {
  	      $addAmount+=$line->amount;
  	      $addAmountLocal+=$line->amountLocal;
  	      if ($line->idMeasureUnit==3) $addWork+=$line->quantity; // Only if unit is Days
  	    } else {
  	      $amount+=$line->amount;
  	      $amountLocal+=$line->amountLocal;
  	      if ($line->numberDays) {
  	        $work += $line->numberDays;
  	      } else if ($line->idMeasureUnit==3) {
  	        $work+=$line->quantity;
  	      }
  	    }
  	  }
  	  if($paramImputOfBillLineClient == 'HT'){
    	  $this->untaxedAmount=$amount;
    	  $this->untaxedAmountLocal=$amountLocal;
    	  $this->addUntaxedAmount=$addAmount;
    	  $this->addUntaxedAmountLocal=$addAmountLocal;
  	  }else{
  	    $this->fullAmount=$amount;
  	    $this->fullAmountLocal=$amountLocal;
  	    $this->addFullAmount=$addAmount;
  	    $this->addFullAmountLocal=$addAmountLocal;
  	  }
  	  $this->initialWork=$work;
  	  $this->addWork=$addWork;
  	}
  	$this->initialWork=floatval($this->initialWork);
  	$this->addWork=floatval($this->addWork);
  	$this->taxPct=floatval($this->taxPct);
  	
  	$this->validatedWork=$this->initialWork+$this->addWork;
  	
  	if($paramImputOfBillLineClient == 'HT'){
  	  if (!$this->untaxedAmount) $this->untaxedAmount=0;
  	  if (!$this->addUntaxedAmount) $this->addUntaxedAmount=0;
  	  $this->totalUntaxedAmount=$this->untaxedAmount+$this->addUntaxedAmount;
    	$this->fullAmount=$this->untaxedAmount*(1+$this->taxPct/100);
    	$this->addFullAmount=$this->addUntaxedAmount*(1+$this->taxPct/100);
    	$this->totalFullAmount=$this->totalUntaxedAmount*(1+$this->taxPct/100);
    	if (!$this->untaxedAmountLocal) $this->untaxedAmountLocal=0;
    	if (!$this->addUntaxedAmountLocal) $this->addUntaxedAmountLocal=0;
    	$this->totalUntaxedAmountLocal=$this->untaxedAmountLocal+$this->addUntaxedAmountLocal;
    	$this->fullAmountLocal=$this->untaxedAmountLocal*(1+$this->taxPct/100);
    	$this->addFullAmountLocal=$this->addUntaxedAmountLocal*(1+$this->taxPct/100);
    	$this->totalFullAmountLocal=$this->totalUntaxedAmountLocal*(1+$this->taxPct/100);
  	}else{
  	  if (!$this->fullAmount) $this->fullAmount=0;
  	  if (!$this->addFullAmount) $this->addFullAmount=0;
  	  $this->totalFullAmount=$this->fullAmount+$this->addFullAmount;
  	  $this->untaxedAmount=$this->fullAmount/(1+$this->taxPct/100);
  	  $this->addUntaxedAmount=$this->addFullAmount/(1+$this->taxPct/100);
  	  $this->totalUntaxedAmount=$this->totalFullAmount/(1+$this->taxPct/100);
  	  if (!$this->fullAmountLocal) $this->fullAmountLocal=0;
  	  if (!$this->addFullAmountLocal) $this->addFullAmountLocal=0;
  	  $this->totalFullAmountLocal=$this->fullAmountLocal+$this->addFullAmountLocal;
  	  $this->untaxedAmountLocal=$this->fullAmountLocal/(1+$this->taxPct/100);
  	  $this->addUntaxedAmountLocal=$this->addFullAmountLocal/(1+$this->taxPct/100);
  	  $this->totalUntaxedAmountLocal=$this->totalFullAmountLocal/(1+$this->taxPct/100);
  	}
  	$this->validatedPricePerDayAmount=($this->validatedWork!=0)?($this->totalUntaxedAmount/$this->validatedWork):0;
  	$this->initialPricePerDayAmount=($this->initialWork!=0)?($this->untaxedAmount/$this->initialWork):0;
  	$this->validatedPricePerDayAmountLocal=($this->validatedWork!=0)?($this->totalUntaxedAmountLocal/$this->validatedWork):0;
  	$this->initialPricePerDayAmountLocal=($this->initialWork!=0)?($this->untaxedAmountLocal/$this->initialWork):0;
  	  	
  	$this->name=pq_trim($this->name);
      
    $resultClass = parent::save();
      
    if (! pq_strpos($resultClass,'id="lastOperationStatus" value="OK"')) {
    	return $resultClass;
    }
    
    /* dispatch of command to validated may be weird */
    if ($oldTotalUntaxedAmount!=$this->totalUntaxedAmount || 
    	$oldIdProject!=$this->idProject || $this->validatedWork!=$oldValidatedWork) {
    	if (pq_trim($oldIdProject)!='' and $oldIdProject!=$this->idProject) {
	    	$prj=new Project($oldIdProject);
	    	$prj->updateValidatedWork();
    	}
      if (pq_trim($this->idProject)!='') {
	    	$prj=new Project($this->idProject);
	    	$prj->updateValidatedWork();
    	}
    }
    if($this->idSituation){
    	$situation = new Situation($this->idSituation);
    	if($this->idProject != $situation->idProject){
    		$critWhere = array('refType'=>get_class($this),'refId'=>$this->id);
    		$situationList = $situation->getSqlElementsFromCriteria($critWhere,null,null);
    		foreach ($situationList as $sit){
    		  $sit->idProject = $this->idProject;
    		  $sit->save();
    		}
    		ProjectSituation::updateLastSituation($old, $this, $situation);
    	}
    }
    
    if(Module::isModuleActive('moduleGestionCA')){
    	$project = new Project($this->idProject);
    	$projectList = $project->getRecursiveSubProjectsFlatList(false, true);
    	$projectList = array_flip($projectList);
    	$projectList = '(0,'.implode(',',$projectList).')';
    	$where = 'idProject in '.$projectList.' and cancelled = 0';
    	$paramAmount = Parameter::getGlobalParameter('ImputOfAmountClient');
    	$cmdAmount = ($paramAmount == 'HT')?'totalUntaxedAmount':'totalFullAmount';
    	$cmdAmountLocal = ($paramAmount == 'HT')?'totalUntaxedAmountLocal':'totalFullAmountLocal';
    	$project->ProjectPlanningElement->commandSum = $this->sumSqlElementsFromCriteria($cmdAmount, null, $where);
    	$project->ProjectPlanningElement->commandSumLocal = $this->sumSqlElementsFromCriteria($cmdAmountLocal, null, $where);
    	$project->ProjectPlanningElement->updateCA(true);
    }
    
    if ($old->idProject!= $this->idProject){
      $listWorkCmd = sqlList::getListWithCrit('WorkCommand', array('idCommand'=>$this->id));
      if(count($listWorkCmd) > 0){
        foreach($listWorkCmd as $idWorkCommand =>$value){
          $workCommand = new WorkCommand($idWorkCommand);
          $workCommand->idProject = $this->idProject;
          $workCommand->save();
        }
      }
    }
    
    return $resultClass;
  }
  
  public function delete() {
  	$idP=$this->idProject;
  	$result =parent::delete();
  	if ($idP) {
  	  $prj=new Project($idP);
  	  $prj->updateValidatedWork();
  	}
  	if(Module::isModuleActive('moduleGestionCA')){
  	  $project = new Project($this->idProject);
  	  $project->ProjectPlanningElement->updateCA(true);
  	}
  	return $result;
  }
  
  
  public function copyTo($newClass, $newType, $newName, $newProject, $structure, $withNotes, $withAttachments, $withLinks, $withAssignments = false, $withAffectations = false, $toProject = NULL, $toActivity = NULL, $copyToWithResult = false, $copyToWithActivityPrice=false, $copyToWithStatus = false, $copyToWithSubTask=false, $moveAfterCreate=null) {
    $result=parent::copyTo($newClass, $newType, $newName, $newProject, $structure, $withNotes, $withAttachments, $withLinks, $withAssignments, $withAffectations, $toProject, $toActivity, $copyToWithResult, $copyToWithActivityPrice, $copyToWithStatus, false, $moveAfterCreate);
    if ($newClass=='Bill') {
      $paramEnableWorkUnit = Parameter::getGlobalParameter('enableWorkCommandManagement');
      if($paramEnableWorkUnit=='true'){
        $workCommand = new WorkCommand();
        $listWorkCommand = $workCommand->getSqlElementsFromCriteria(array('idCommand'=>$this->id));
        foreach ($listWorkCommand as $id=>$com){
          $workCommandBill = new WorkCommandBilled();
          $workCommandBill->idCommand = $this->id;
          $workCommandBill->idWorkCommand = $com->id;
          $workCommandBill->idBill = $result->id;
          $workCommandBill->billedQuantity = $com->commandQuantity - $com->billedQuantity;
          $workCommandBill->save();
          //$com->billedQuantity += $workCommandBill->billedQuantity;
          //$com->billedAmount = $com->unitAmount * $com->billedQuantity;
          //$com->save();
        }
      }
    }
    return $result;
  }
  
  
  
  // Save without extra save() feature and without controls
  public function simpleSave($withoutDependencies=false) {
    return $this->saveForced($withoutDependencies);
  }
    /** ==========================================================================
   * Return the validation sript for some fields
   * @return String the validation javascript (for dojo frameword)
   */
  public function getValidationScript($colName) {
    
    $colScript = parent::getValidationScript($colName);
    if ($colName=="untaxedAmount" || $colName=="taxPct"  || $colName=="initialWork" 
  	 || $colName=="addUntaxedAmount" || $colName=="addWork" || $colName=="addFullAmount" || $colName=="fullAmount"
     || $colName=="untaxedAmountLocal" || $colName=="taxPctLocal" || $colName=="initialWorkLocal"
     || $colName=="addUntaxedAmountLocal" || $colName=="addWorkLocal" || $colName=="addFullAmountLocal" || $colName=="fullAmountLocal") {
      $colScript .= '<script type="dojo/connect" event="onChange" >';
      $paramImputOfAmountClient = Parameter::getGlobalParameter('ImputOfAmountClient');
      if (count($this->_BillLine)) {
        $paramImputOfAmountClient = Parameter::getGlobalParameter('ImputOfBillLineClient');
      }
      if($paramImputOfAmountClient == 'HT'){
        $colScript .= '  updateCommandTotal();';
      }else{
        $colScript .= '  updateCommandTotalTTC();';
      }
      $colScript .= '  formChanged();';
      $colScript .= '</script>';
    } else if ($colName=="idProject") {
    	$colScript .= '<script type="dojo/connect" event="onChange" >';
    	$colScript .= '  setClientValueFromProject("idClient",this.value);';
    	$colScript .= '  formChanged();';
    	$colScript .= '</script>';
    } else if ($colName=="idClient") {
    	$colScript .= '<script type="dojo/connect" event="onChange" >';
    	$colScript .= '  refreshList("idContact", "idClient", this.value, null, null, false);';
    	$colScript .= '  formChanged();';
    	$colScript .= '</script>';
    }    
    return $colScript;
  }
    
  private function zeroIfNull($value) {
  	$val = $value;
  	if (!$val || $val=='' || !is_numeric($val)) {
  		$val=0;
  	} else { 
  		$val=$val*1;
  	}
  	
  	return $val;
  	
  }
  
  public function setAttributes() {
    self::$_fieldsAttributes['_sec_WorkCommand']='hidden';
    self::$_fieldsAttributes['_spe_WorkCommand']='hidden';
    if (count($this->_BillLine)) {
      self::$_fieldsAttributes['untaxedAmount']='readonly';
      self::$_fieldsAttributes['fullAmount']='readonly';
      //self::$_fieldsAttributes['addUntaxedAmount']='readonly';
      //self::$_fieldsAttributes['addFullAmount']='readonly';
      self::$_fieldsAttributes['totalUntaxedAmount']='readonly';
      self::$_fieldsAttributes['initialWork']='readonly';
      //self::$_fieldsAttributes['addWork']='readonly';
    }
    $paramImputOfAmountClient = Parameter::getGlobalParameter('ImputOfAmountClient');
    if($paramImputOfAmountClient == 'HT'){
      self::$_fieldsAttributes['fullAmount']="readonly";
      self::$_fieldsAttributes['addFullAmount']="readonly";
    }else{
      self::$_fieldsAttributes['untaxedAmount']="readonly";
      self::$_fieldsAttributes['addUntaxedAmount']="readonly";
    }
    $paramEnableWorkUnit = Parameter::getGlobalParameter('enableWorkCommandManagement');
    if($paramEnableWorkUnit=='true'){
      self::$_fieldsAttributes['_sec_WorkCommand']='';
      self::$_fieldsAttributes['_spe_WorkCommand']='';
    }
     if ($this->hasCurrency() ) {
       self::$_fieldsAttributes['taxPct']='hidden';
       self::$_fieldsAttributes['initialWork']='hidden';
       self::$_fieldsAttributes['addWork']='hidden';
       self::$_fieldsAttributes['validatedWork']='hidden';
     } else {
       self::$_fieldsAttributes['taxPctLocal']='hidden,calculated';
       self::$_fieldsAttributes['initialWorkLocal']='hidden,calculated';
       self::$_fieldsAttributes['addWorkLocal']='hidden,calculated';
       self::$_fieldsAttributes['validatedWorkLocal']='hidden,calculated';
     }
  }
  
  public function drawSpecificItem($item){
  	global $comboDetail, $print, $outMode, $largeWidth;
  	$result="";
  	if($item=='situation'){
  		$situation = new Situation();
  		$situation->drawSituationHistory($this);
  	}elseif($item=="WorkCommand"){
  	  $workCommand = new WorkCommand();
  	  $listCommand = $workCommand->getSqlElementsFromCriteria(array('idCommand'=>$this->id));
  	  drawWorkCommand($listCommand,$this);
  	}
  	return $result;
  }
  
}
?>