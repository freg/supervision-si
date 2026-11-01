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
 * ProspectEstimate is a quotation issued to a prospect, before any client exists.
 */
require_once('_securityCheck.php');

class ProspectEstimateMain extends SqlElement {

  // List of fields that will be exposed in general user interface
  public $_sec_description;
  public $id;    // redefine $id to specify its visible place
  public $reference;
  public $name;
  public $idProject;
  public $idProspectEstimateType;
  public $idUser;
  public $creationDate;
  public $idProspect;
  public $Origin;
  public $description;
  public $additionalInfo;
  public $_sec_treatment;
  public $idStatus;
  public $idResource;
  public $idLikelihood;
  public $handled;
  public $handledDate;
  public $done;
  public $doneDate;
  public $idle;
  public $idleDate;
  public $cancelled;
  public $_lib_cancelled;
  public $initialEndDate;
  public $_tab_5_2_smallLabel = array('untaxedAmountShort', 'tax', '', 'fullAmountShort', 'estimatedWork', 'amount', 'amountLocal');
  public $untaxedAmount;
  public $taxPct;
  public $taxAmount;
  public $fullAmount;
  public $plannedWork;
  public $untaxedAmountLocal;
  public $taxPctLocal;
  public $taxAmountLocal;
  public $fullAmountLocal;
  public $plannedWorkLocal;
  public $comment;

  public $_BillLine=array();
  public $_BillLine_colSpan="2";
  public $_sec_Link;
  public $_Link=array();
  public $_Attachment=array();
  public $_Note=array();
  public $_nbColMax=3;

  // Define the layout that will be used for lists
  private static $_layout='
    <th field="id" formatter="numericFormatter" width="5%" ># ${id}</th>
    <th field="nameProject" width="10%" >${idProject}</th>
    <th field="nameProspect" width="15%" >${idProspect}</th>
    <th field="nameProspectEstimateType" width="10%" >${idProspectEstimateType}</th>
    <th field="name" width="20%" >${name}</th>
    <th field="colorNameStatus" width="10%" formatter="colorNameFormatter">${idStatus}</th>
    <th field="nameResource" formatter="thumbName22" width="10%" >${responsible}</th>
  	<th field="untaxedAmount" formatter="costFormatter" width="10%" >${untaxedAmount}</th>
  	<th field="fullAmount" formatter="costFormatter" width="10%" >${fullAmount}</th>
    ';

  private static $_fieldsAttributes=array("id"=>"nobr",
                                  "idProspectEstimateType"=>"required",
  		                            "idProject"=>"required",
  		                            "reference"=>"readonly",
                                  "name"=>"required",
                                  "idStatus"=>"required",
                                  "handled"=>"nobr",
                                  "done"=>"nobr",
                                  "idle"=>"nobr",
  								                "idleDate"=>"nobr",
                                  "cancelled"=>"nobr",
                                  "taxAmount"=>"calculated,readonly",
                                  "taxAmountLocal"=>"calculated,readonly",
                                  "taxPctLocal"=>"calculated","plannedWorkLocal"=>"calculated"
  );

  private static $_colCaptionTransposition = array('idUser'=>'issuer',
                                                   'idResource'=> 'responsible',
  													'idActivity'=>'linkActivity',
  		                      'initialEndDate'=>'actualEndDate',
                            'description'=>'request',
                            'plannedWork'=>'estimatedWork');
  private static $_databaseColumnName = array('taxPct'=>'tax');

   /** ==========================================================================
   * Constructor
   * @param $id Int the id of the object in the database (null if not stored yet)
   * @return void
   */
  function __construct($id = NULL, $withoutDependentObjects=false) {
    self::$_fieldsAttributes['taxAmountLocal']='calculated,readonly';
    parent::__construct($id,$withoutDependentObjects);
    if ($withoutDependentObjects) return;
    if (count($this->_BillLine)) {
      self::$_fieldsAttributes['untaxedAmount']='readonly';
      self::$_fieldsAttributes['plannedWork']='readonly';
      self::$_fieldsAttributes['plannedWorkLocal']='readonly,calculated';
    }
    if ($this->hasCurrency()) {
      $this->taxPctLocal=$this->taxPct;
      $this->plannedWorkLocal=$this->plannedWork;
    }
    if ($this->fullAmount) {
      $this->taxAmount=$this->fullAmount-$this->untaxedAmount;
    }
    if ($this->fullAmountLocal) {
      $this->taxAmountLocal=$this->fullAmountLocal-$this->untaxedAmountLocal;
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

  /**=========================================================================
   * Overrides SqlElement::save() function to add specific treatments
   * @see persistence/SqlElement#save()
   * @return String the return message of persistence/SqlElement#save() method
   */
  public function save() {
    if (pq_trim($this->id)=='') {
    	// fill the creation date if it's empty - creationDate is not empty for import !
    	if ($this->creationDate=='') $this->creationDate=date('Y-m-d');
	  }
    $this->name=pq_trim($this->name);
    $paramImputOfBillLineClient = Parameter::getGlobalParameter('ImputOfBillLineClient');
	  $billLine=new BillLine();
	  $crit = array("refType"=> "ProspectEstimate", "refId"=>$this->id);
	  $billLineList = $billLine->getSqlElementsFromCriteria($crit,false);
	  if (count($billLineList)>0) {
  	  $amount=0;
  	  $numberDays=0;
  	  foreach ($billLineList as $line) {
  	    $amount+=$line->amount;
  	    $numberDays+=$line->numberDays;
  	  }
  	  if($paramImputOfBillLineClient == 'HT'){
    	  $this->untaxedAmount=$amount;
  	  }else{
  	    $this->fullAmount=$amount;
  	  }
  	  $this->plannedWork=$numberDays;
	  }
	  if($paramImputOfBillLineClient == 'HT'){
      $this->fullAmount=$this->untaxedAmount*(1+$this->taxPct/100);
	  }else{
	    $this->untaxedAmount=$this->fullAmount/(1+$this->taxPct/100);
	  }
    return parent::save();
  }

  // Save without extra save() feature and without controls
  public function simpleSave($withoutDependencies=false) {
    return parent::saveForced($withoutDependencies);
  }

   /** ==========================================================================
   * Return the validation sript for some fields
   * @return String the validation javascript (for dojo frameword)
   */
  public function getValidationScript($colName) {

    $colScript = parent::getValidationScript($colName);
    if ($colName=="untaxedAmount" || $colName=="untaxedAmountLocal" || $colName=="taxPct" || $colName=="taxPctLocal" || $colName=="fullAmount" || $colName=="fullAmountLocal" ) {
      $colScript .= '<script type="dojo/connect" event="onChange" >';
      $paramImputOfAmountClient = Parameter::getGlobalParameter('ImputOfAmountClient');
      if (count($this->_BillLine)) {
        $paramImputOfAmountClient = Parameter::getGlobalParameter('ImputOfBillLineClient');
      }
      if($paramImputOfAmountClient == 'HT'){
        $colScript .= '  updateBillTotal();';
      }else{
        $colScript .= '  updateBillTotalTTC();';
      }
      $colScript .= '  formChanged();';
      $colScript .= '</script>';
    }
    return $colScript;
  }

  public function setAttributes() {
    if (count($this->_BillLine)) {
      self::$_fieldsAttributes['untaxedAmount']='readonly';
      self::$_fieldsAttributes['fullAmount']='readonly';
    }
    $paramImputOfAmountClient = Parameter::getGlobalParameter('ImputOfAmountClient');
    if($paramImputOfAmountClient == 'HT'){
      self::$_fieldsAttributes['fullAmount']="readonly";
    }else{
      self::$_fieldsAttributes['untaxedAmount']="readonly";
    }
    if ($this->hasCurrency() ) {
      self::$_fieldsAttributes['taxPct']='hidden';
      self::$_fieldsAttributes['plannedWork']='hidden';
    } else {
      self::$_fieldsAttributes['taxPctLocal']='hidden,calculated';
      self::$_fieldsAttributes['plannedWorkLocal']='hidden,calculated';
    }
  }


  /** =========================================================================
   * Overrides SqlElement::copyTo() to fill client and contact from the prospect
   * @see persistence/SqlElement#copyTo()
   * @return SqlElement the newly created object
   */
  public function copyTo($newClass, $newType, $newName, $newProject, $setOrigin, $withNotes, $withAttachments, $withLinks, $withAssignments=false, $withAffectations=false, $toProject=null, $toActivity=null, $copyToWithResult=false, $copyToWithActivityPrice=false, $copyToWithStatus=false, $copyToWithSubTask=false, $moveAfterCreate=null) {
    $newObj=parent::copyTo($newClass, $newType, $newName, $newProject, $setOrigin, $withNotes, $withAttachments, $withLinks, $withAssignments, $withAffectations, $toProject, $toActivity, $copyToWithResult, $copyToWithActivityPrice, $copyToWithStatus, $copyToWithSubTask, $moveAfterCreate);
    if ($newClass!='Quotation' or !$newObj or !$newObj->id or !$this->idProspect) {
      return $newObj;
    }
    $idClient=$this->getSingleProspectLink('Client');
    $idContact=$this->getSingleProspectLink('Contact');
    if (!$idClient and !$idContact) {
      return $newObj;
    }
    if ($idClient) $newObj->idClient=$idClient;
    if ($idContact) $newObj->idContact=$idContact;
    $res=$newObj->save();
    if (getLastOperationStatus($res)!='OK') {
      errorLog("ProspectEstimate #" . $this->id . " : cannot fill client and contact on Quotation #" . $newObj->id);
    }
    return $newObj;
  }

  /** =========================================================================
   * Return the id of the only object of given class linked to the prospect
   * Returns null when the prospect has no such link, or more than one
   * @param $class String the linked class, 'Client' or 'Contact'
   * @return Int the id, or null
   */
  private function getSingleProspectLink($class) {
    $id=Sql::fmtId($this->idProspect);
    $cls=Sql::str($class);
    $where="(ref1Type='Prospect' and ref1Id=$id and ref2Type=$cls)"
          . " or (ref2Type='Prospect' and ref2Id=$id and ref1Type=$cls)";
    $link=new Link();
    $list=$link->getSqlElementsFromCriteria(null, false, $where);
    if (count($list)!=1) {
      return null;
    }
    $found=reset($list);
    return ($found->ref1Type=='Prospect')?$found->ref2Id:$found->ref1Id;
  }
}
