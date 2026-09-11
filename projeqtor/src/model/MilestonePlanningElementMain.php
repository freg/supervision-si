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
class MilestonePlanningElementMain extends PlanningElement {

  public $id;
  public $idProject;
  public $refType;
  public $refId;
  public $refName;
  public $_tab_5_1_smallLabel = array('validated', 'planned', 'real','latest','requested', 'dueDate');
  public $validatedEndDate;
  public $plannedEndDate;
  public $realEndDate;
  public $latestEndDate;
  public $initialEndDate;
  public $_tab_3_1_smallLabel = array('', '', '','planning');
  public $idMilestonePlanningMode;
  public $_label_wbs;
  public $wbs;
  public $_tab_1_1_smallLabel_1 = array('', 'color');
  public $color;
  public $wbsSortable;
  public $topId;
  public $topRefType;
  public $topRefId;
  public $priority;
  public $idle;
  private static $_fieldsAttributes=array(
    "priority"=>"hidden,noImport",
    "initialStartDate"=>"hidden,noImport",
    "validatedStartDate"=>"hidden,noImport",
    "plannedStartDate"=>"hidden,noImport",
    "realStartDate"=>"hidden,noImport",
    "initialDuration"=>"hidden,noImport",
    "validatedDuration"=>"hidden,noImport",
    "plannedDuration"=>"hidden,noImport",
    "realDuration"=>"hidden,noImport",
    "initialWork"=>"hidden,noImport",
    "validatedWork"=>"hidden,noImport",
    "plannedWork"=>"hidden,noImport",
  	"notPlannedWork"=>"hidden",
    "realWork"=>"hidden,noImport",
    "assignedWork"=>"hidden,noImport",
    "leftWork"=>"hidden,noImport",
    "validatedCost"=>"hidden,noImport",
    "plannedCost"=>"hidden,noImport",
    "realCost"=>"hidden,noImport",
    "assignedCost"=>"hidden,noImport",
    "leftCost"=>"hidden,noImport",
    "realEndDate"=>"readonly,noImport",
    "idMilestonePlanningMode"=>"required,mediumWidth",
    "progress"=>"hidden,noImport",
    "expectedProgress"=>"hidden,noImport",
    "plannedStartFraction"=>"hidden",
    "plannedEndFraction"=>"hidden",
    "validatedStartFraction"=>"hidden",
    "validatedEndFraction"=>"hidden",
    "latestEndDate"=>"hidden"
  );   
  
  private static $_databaseTableName = 'planningelement';
  //private static $_databaseCriteria = array('refType'=>'Milestone'); // Bad idea : sets a mess when moving projets and possibly elsewhere.
  
  private static $_databaseColumnName=array(
    "idMilestonePlanningMode"=>"idPlanningMode"
  );
  
  private static $_colCaptionTransposition = array('initialStartDate'=>'requestedStartDate',
      'initialEndDate'=> 'requestedEndDate',
      'initialDuration'=>'requestedDuration',
      'validatedEndDate'=>'validatedDueDate',
      'plannedEndDate'=>'plannedDueDate',
      'requestedEndDate'=>'requestedDueDate'
  );
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
    $old=$this->getOld();
    $this->initialStartDate=$this->initialEndDate;
    $this->validatedStartDate=$this->validatedEndDate;
    if (! $this->plannedEndDate and $this->validatedEndDate) $this->plannedEndDate=$this->validatedEndDate;
    if ($this->idPlanningMode==6 and $this->validatedEndDate and $this->validatedEndDate!=$old->validatedEndDate) $this->plannedEndDate=$this->validatedEndDate;
    $this->plannedStartDate=$this->plannedEndDate;
    $this->realStartDate=$this->realEndDate;
    $this->initialDuration=null;
    $this->validatedDuration=null;
    $this->plannedDuration=null;
    $this->realDuration=null;
    #florent ticket 4039
    $this->initialWork=null;
    $this->validatedWork=null;
    $this->plannedWork=null;
  	$this->notPlannedWork=null;
    $this->realWork=null;
    $this->assignedWork=null;
    $this->leftWork=null;
    $this->validatedCost=null;
    $this->plannedCost=null;
    $this->realCost=null;
    $this->assignedCost=null;
    $this->leftCost=null;
    $this->elementary=1;
    $this->plannedEndFraction=$this->plannedStartFraction;
    $this->validatedEndFraction=$this->validatedStartFraction;
    $this->realDuration=0;
    $result = parent::save();
    if ($this->realStartDate!=$this->realEndDate) {
      $this->realStartDate=$this->realEndDate;
      $this->simpleSave();
    }
    if ($this->plannedStartDate!=$old->plannedStartDate) {
      $this->updateMilestonableItems();
    }
    
    return $result;
  }
  public function setAttributes() {
    $showLatest=Parameter::getGlobalParameter('showLatestDates');
    if ($showLatest) {
      self::$_fieldsAttributes['latestStartDate']="readonly";
      self::$_fieldsAttributes['latestEndDate']="readonly";
    }
    if ($this->idMilestonePlanningMode==6 and Parameter::getGlobalParameter('manuallyChangePlannedDate')!='NO') {
      self::$_fieldsAttributes['plannedEndDate']="";
    } else {
      self::$_fieldsAttributes['plannedEndDate']="readonly";
    }
  }
  
  public function getValidationScript($colName) {
    $colScript = parent::getValidationScript($colName);
    
    if ($colName=="validatedEndDate") {
      $colScript .= '<script type="dojo/connect" event="onChange" >';
      $colScript .= '  var pm=dijit.byId("MilestonePlanningElement_idMilestonePlanningMode").get("value");';
      $colScript .= '  if (pm==6) {';
      $colScript .= '  var endDate=this.value;';
      $colScript .= '  if (endDate<new Date()) endDate=new Date();';
      $colScript .= '    dijit.byId("MilestonePlanningElement_plannedEndDate").set("value",endDate); ';
      $colScript .= '  }';
      $colScript .= '  formChanged();';
      $colScript .= '</script>';
    } else if ($colName=="idMilestonePlanningMode") {
      $colScript .= '<script type="dojo/connect" event="onChange" >';
      $colScript .= '  dijit.byId("MilestonePlanningElement_plannedEndDate").set("readOnly",(this.value==6)?false:true); ';
      $colScript .= '  formChanged();';
      $colScript .= '</script>';
    }
    return $colScript;
  }
}
?>