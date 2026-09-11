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
class WorkCommandMain extends SqlElement {
    
    public $_sec_Description;
	public $id;
	public $idProject;
	public $idCommand;
	public $idWorkCommand;
	public $idWorkUnit;
	public $idComplexity;
	public $name;
	public $_spe_blank;
	public $unitAmount;
	public $unitAmountLocal;
	public $_tab_3_4 = array('ShortQuantity','amount', 'amountLocal', 'Ordered', 'Realised', 'Accepted', 'IsBilled');
	public $commandQuantity;
	public $commandAmount;
	public $commandAmountLocal;
	public $doneQuantity;
	public $doneAmount;
	public $doneAmountLocal;
	public $acceptedQuantity;
	public $acceptedAmount;
	public $acceptedAmountLocal;
	public $billedQuantity;
	public $billedAmount;
	public $billedAmountLocal;
	public $idle;
	public $elementary;
	public $_sec_phase;
	public $_spe_phase;
	public $_sec_Link;
	public $_Link = array();
	public $_Attachment = array();
	public $_Note = array();
	public $_nbColMax = 3;
	
	public static $_excludeConversion=array('commandAmount','doneAmount','acceptedAmount','billedAmount');
	
	private static $_fieldsAttributes=array(
	    "idProject"=>"required, doNotAutoFill",
	    "idWorkUnit"=>"required",
	    "idCommand"=>"required, doNotAutoFill",
	    "idComplexity"=>"required",
	    "commandAmount"=>"readonly",
	    "doneAmount"=>"readonly",
	    "acceptedAmount"=>"readonly",
	    "billedAmount"=>"readonly",
	    "unitAmount"=>"hidden",
	    "idle"=>"",
	    "elementary"=>"hidden",
	    "commandQuantity"=>"smallWidth,size1/2",
	    "doneQuantity"=>"readonly,smallWidth,size1/2",
	    "acceptedQuantity"=>"readonly,smallWidth,size1/2",
	    "billedQuantity"=>"readonly,smallWidth,size1/2"
	);
	
	private static $_layout='
    <th field="id" formatter="numericFormatter" width="5%"># ${id}</th>
	  <th field="nameCommand" width="17%" >${idCommand}</th>
	  <th field="name" width="30%" >${name}</th>
	  <th field="commandQuantity" formatter="numericFormatter" width="12%">${commandQuantity}</th>
	  <th field="commandAmount" formatter="costFormatter" width="12%">${commandAmount}</th> 
	  <th field="doneQuantity" formatter="numericFormatter" width="12%">${doneQuantity}</th>
	  <th field="doneAmount" formatter="costFormatter" width="12%">${doneAmount}</th>  
    ';
	
	private $isCreatingParent;
	
	private static $_colCaptionTransposition = array(
	    'idWorkCommand'=> 'isSubWorkCommand'
	);
	
	/** ==========================================================================
	 * Construct
	 * @return void
	 */
    function __construct($id = NULL, $withoutDependentObjects = false, $isCreatingParent = false) {
      parent::__construct($id, $withoutDependentObjects);
      $this->isCreatingParent = $isCreatingParent; 
    }
	
	public function control() {
	  $result = "";
	   
	  $defaultControl=parent::control();
	  if ($defaultControl!='OK') {
	    $result.=$defaultControl;
	  }
	  if ($this->idWorkCommand && $this->idWorkCommand == $this->id) {
	    $result .= '<br/>' . i18n('workCommandCannotBeItsOwnParent'); 
	  }
	  
	  if ($this->idWorkCommand){
	    $workCommand = new WorkCommand($this->idWorkCommand);
	    if ($workCommand->elementary == 1){
	      $result.='<br/>' . i18n('workCommandAlreadyHasAParent');
	    }
	  }
	   
	  if ($result == "") {
	    $result = 'OK';
	  }
	   
	  return $result;
	}
	
	/** ==========================================================================
	 * Destructor
	 * @return void
	 */
	function __destruct() {
	  parent::__destruct();
	}
	
	/** ==========================================================================
	 * Return the specific fieldsAttributes
	 * @return Array the fieldsAttributes
	 */
	protected function getStaticFieldsAttributes() {
	  return self::$_fieldsAttributes;
	}
	
	/** ==========================================================================
	 * Return the specific layout
	 * @return String the layout
	 */
	protected function getStaticLayout() {
	  return self::$_layout;
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
	public function save($updateElementary = true) {
	  //if (!$this->idProject) {
	if (1) {
	  $cmd = new Command($this->idCommand,true);
	  $this->idProject=$cmd->idProject;
	}
	$valComplexity = new ComplexityValues();
	$price=0;
	$priceLocal=0;
    $listValComplexity = $valComplexity->getSqlElementsFromCriteria(array('idComplexity'=>$this->idComplexity,'idWorkUnit'=>$this->idWorkUnit));
    
    foreach ($listValComplexity as $item){
      $price = $item->price;
      $priceLocal = $item->priceLocal;
    }
  
    $this->unitAmount = $price;
    $this->unitAmountLocal = ($this->hasCurrency())?$priceLocal:null;
    $this->commandAmount = $this->unitAmount * $this->commandQuantity;
    $this->commandAmountLocal = ($this->hasCurrency())?$this->unitAmountLocal * $this->commandQuantity:null;

    
    $this->doneAmount = $this->unitAmount * $this->doneQuantity;
    $this->doneAmountLocal = ($this->hasCurrency())?$this->unitAmountLocal * $this->doneQuantity:null;
    $this->acceptedAmount = $this->unitAmount * $this->acceptedQuantity;
    $this->acceptedAmountLocal = ($this->hasCurrency())?$this->unitAmountLocal * $this->acceptedQuantity:null;
    $this->billedAmount = $this->unitAmount * $this->billedQuantity;
    $this->billedAmountLocal = ($this->hasCurrency())?$this->unitAmountLocal * $this->billedQuantity:null;

	if ($updateElementary && !$this->id) {
      $this->elementary = 1;
    }
    
    if ($this->elementary == 0) {
      $children=array();
      if (isset($this->id)){
        $children = $this->getSqlElementsFromCriteria(array('idWorkCommand' => $this->id));
      }
      $totalDoneQuantity = 0;
      $totalDoneAmount = 0;
      $totalDoneAmountLocal = 0;
      $totalAcceptedQuantity = 0;
      $totalAcceptedAmount = 0;
      $totalAcceptedAmountLocal = 0;
      $totalBilledQuantity = 0;
      $totalBilledAmount = 0;
      $totalBilledAmountLocal = 0;
      foreach ($children as $child) {
        $totalDoneQuantity += $child->doneQuantity;
        $totalDoneAmount += $child->doneAmount;
        $totalDoneAmountLocal += $child->doneAmountLocal;
        $totalAcceptedQuantity += $child->acceptedQuantity;
        $totalAcceptedAmount += $child->acceptedAmount;
        $totalAcceptedAmountLocal += $child->acceptedAmountLocal;
        $totalBilledQuantity += $child->billedQuantity;
        $totalBilledAmount += $child->billedAmount;
        $totalBilledAmountLocal += $child->billedAmountLocal;
      }
      $this->doneQuantity = $totalDoneQuantity;
      $this->doneAmount = $totalDoneAmount;
      $this->doneAmountLocal = $totalDoneAmountLocal;
      $this->acceptedQuantity = $totalAcceptedQuantity;
      $this->acceptedAmount = $totalAcceptedAmount;
      $this->acceptedAmountLocal = $totalAcceptedAmountLocal;
      $this->billedQuantity = $totalBilledQuantity;
      $this->billedAmount = $totalBilledAmount;
      $this->billedAmountLocal = $totalBilledAmountLocal;
    }
      
    $old=$this->getOld();
    $workCommand = new WorkCommand();
    if ($this->name != $old->name && $this->id){
      $workCommandList = $workCommand->getSqlElementsFromCriteria(array('idWorkCommand'=>$this->id));
      foreach ($workCommandList as $item){
        $item->name = preg_replace('/^[^-]+/', $this->name, $item->name);
        $item->save();
      }    
    }
     
    $result = parent::save();

    if ($this->idWorkCommand != $old->idWorkCommand) {
      $parentWorkCommand = new WorkCommand($old->idWorkCommand);
      $parentWorkCommand->save();
    }
      
	if ($this->idWorkCommand) {
	  $parentWorkCommand = new WorkCommandMain($this->idWorkCommand,false, true);
	  $parentWorkCommand->elementary = 0;
	  $parentWorkCommand->save(false);
	  $this->idCommand = $parentWorkCommand->idCommand;
	}
	  
	  return $result;
	}
	
	public function hasChildren() {
	  $children = $this->getSqlElementsFromCriteria(array('idWorkCommand' => $this->id));
	  return !empty($children);
	}
	
	public function updateAcceptedCommand(){
	  $wca = new WorkCommandAccepted();
	  $where = "idWorkCommand = $this->id and acceptedDate is not null";
	  $acceptedQuantity = $wca->sumSqlElementsFromCriteria('acceptedQuantity', null, $where);
	  $this->acceptedQuantity = $acceptedQuantity;
	  $this->save();
	}
	
	public function setAttributes(){
	  if($this->idProject) self::$_fieldsAttributes ['idProject'] = 'readonly';
	  if ($this->elementary == '0') {
	    self::$_fieldsAttributes['idWorkCommand'] = 'hidden';
	  }	  
	}
	
	public function simpleSave($withoutDependencies=false) {
	  return parent::saveForced($withoutDependencies);
	}
	
	public function deleteControl(){
	  $result="";
	   
	  // Cannot delete done WorkCommand
	  if ($this->doneQuantity and $this->doneQuantity > 0 )	{
	    $result .= "<br/>" . i18n("errorDeleteDoneWorkCommand");
	  }
	  
	  // Cannot delete accepted WorkCommand
	  if ($this->acceptedQuantity and $this->acceptedQuantity > 0 )	{
	    $result .= "<br/>" . i18n("errorDeleteAcceptedWorkCommand");
	  }
	  
	  // Cannot delete billed WorkCommand
	  if ($this->billedQuantity and $this->billedQuantity > 0 )	{
	    $result .= "<br/>" . i18n("errorDeleteBilledWorkCommand");
	  }
	  
	  if ($this->hasChildren()) {
	    $result .= "<br/>" . i18n("errorDeleteParentWorkCommand");
	  }
	
	  if (! $result) {
	    $result=parent::deleteControl();
	  }
	  return $result;
	}
	
	public function delete() {
	  $result = parent::delete();
	
	  $parentWorkCommand = new WorkCommand($this->idWorkCommand);
	  if (!$parentWorkCommand->hasChildren()) {
	    $parentWorkCommand->elementary = 1;
	    $parentWorkCommand->save(false);
	  }
	  return $result;
	}
	
	private static $_databaseCriteria = array();   
	
	/** ========================================================================
	 * Return the specific database criteria
	 * @return String the databaseTableName
	 */
	protected function getStaticDatabaseCriteria() {
	  return self::$_databaseCriteria;
	}
			
    public function getValidationScript($colName) {
      $colScript = parent::getValidationScript ( $colName );
      if ($colName=="idProject") {
        $colScript .= '<script type="dojo/connect" event="onChange" >';
        $colScript .= '  if (this.value) {';
        $colScript .= '    dijit.byId("idWorkUnit").set("value",null);';
        $colScript .= '    dijit.byId("idCommand").set("value",null);';
        $colScript .= '    refreshList("idWorkUnit","idProject", this.value, null, null, true);';
        $colScript .= '    refreshList("idCommand","idProject", this.value, null, null, true);';
        $colScript .= '  } else {';
        $colScript .= '    refreshList("idWorkUnit","idProject", null, null, null, true);';
        $colScript .= '    refreshList("idCommand","idProject", null, null, null, true);';
        $colScript .= '  }';
		$colScript .= '</script>';
      }else if ($colName=="idWorkUnit") {
        $colScript .= '<script type="dojo/connect" event="onChange" >';
        $colScript .= '  if (this.value) {';
        $colScript .= '    dijit.byId("idComplexity").set("value",null);';
        $colScript .= '    var idWorkUnit = dijit.byId("idWorkUnit").get("value");';
        $colScript .= '    refreshList("idComplexity","idWorkUnit", idWorkUnit, null, null, true);';
        $colScript .= '  }';
        $colScript .= '</script>';         
      }
//       if ($colName=="idWorkUnit" || $colName=="idComplexity" || $colName=="idWorkCommand" ) {
//         $colScript .= '<script type="dojo/connect" event="onChange" >';
//         $colScript .= '  var idWorkUnit = dojo.byId("idWorkUnit").value;';
//         $colScript .= '  var idComplexity = dojo.byId("idComplexity").value;';
//         $colScript .= '  var idWorkCommand = dojo.byId("idWorkCommand").value;';
//         $colScript .= '  if (idWorkCommand){';
//         $colScript .= '     var extractedNameWorkCommand = idWorkCommand.match(/[^-]+$/)[0];';
//         $colScript .= '     if (extractedNameWorkCommand) idWorkCommand = extractedNameWorkCommand;';
//         $colScript .= '     var nameConcatenated = idWorkCommand + " - " + idWorkUnit + " - " + idComplexity;';
//         $colScript .= '     dojo.byId("name").value = nameConcatenated;';
//         $colScript .= '  } else {';
//         $colScript .= '     var nameConcatenated = idWorkUnit + " - " + idComplexity;';
//         $colScript .= '     dojo.byId("name").value = nameConcatenated;';
//         $colScript .= '  }';
//         $colScript .= '  terminateChange();';
//         $colScript .= '  formChanged();';
//         $colScript .= '</script>';
//       }
      if ($colName=="idWorkCommand" ) {
        $colScript .= '<script type="dojo/connect" event="onChange" >';
        $colScript .= '  if (this.value) {';
        $colScript .= '    dijit.byId("idCommand").set("value",null);';
        $colScript .= '    var idWorkCommand = dijit.byId("idWorkCommand").get("value");';
        $colScript .= '    refreshList("idCommand","idWorkCommand", idWorkCommand, null, null, true);';
        $colScript .= '  }';
        $colScript .= '</script>';
      }
      
      return $colScript;
    }
    
    /** =========================================================================
     * Draw a specific item for the current class.
     * @param String $item the item. Correct values are :
     *    - subprojects => presents sub-projects as a tree
     * @return String an html string able to display a specific item
     *  must be redefined in the inherited class
     */
    public function drawSpecificItem($item){
      global $print;
      $result = "";
      if($item== "phase"){
        if($this->id){
          $workUnit = new WorkUnit($this->idWorkUnit);
          $WorkUnitCatalogPhase = new WorkUnitCatalogPhase();
          $listWorkUnitCatalogPhase = $WorkUnitCatalogPhase->getSqlElementsFromCriteria(array('idCatalogUO'=>$workUnit->idCatalogUO));
          $catalogUO = new CatalogUO($workUnit->idCatalogUO);
          drawWorkUnitCatalogPhase($catalogUO,$listWorkUnitCatalogPhase,$this);
        }
      }
      if ($item== "blank"){
        $result .="<div>&nbsp;</div>";
      }
      return $result;
    }
    public function getStaticExcludeConversion() {
      return self::$_excludeConversion;
    }
}