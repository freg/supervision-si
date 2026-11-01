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
 * Action is establised during meeting, to define an action to be followed.
 */ 
require_once('_securityCheck.php');

class AcceptanceMain extends SqlElement {

  // List of fields that will be exposed in general user interface
  public $_sec_description;
  public $id;    // redefine $id to specify its visible place
  public $reference;
  public $name;
  public $idProject;
  public $idAcceptanceType;
  public $externalReference;
  public $description;
  public $_sec_validation;
  public $idStatus;
  public $idResource;
  public $acceptanceDate;
  public $handled;
  public $handledDateTime;
  public $done;
  public $doneDateTime;
  public $idle;
  public $idleDateTime;
  public $result;
  public $_sec_AcceptedWorkCommand;
  public $_spe_AcceptedWorkCommand;
  public $_sec_Link_Activity;
  public $_Link_Activity=array();
  public $_sec_Link;
  public $_Link=array();
  public $_Attachment=array();
  public $_Note=array();

  public $_nbColMax=3;
  
  // Define the layout that will be used for lists
  private static $_layout='
    <th field="id" formatter="numericFormatter" width="5%" ># ${id}</th>
    <th field="nameProject" width="10%" >${idProject}</th>
    <th field="nameAcceptanceType" width="10%" >${idAcceptanceType}</th>
    <th field="name" width="30%" >${name}</th>
    <th field="acceptanceDate" formatter="dateFormatter" width="8%" >${acceptanceDate}</th>
    <th field="idle" width="5%" formatter="booleanFormatter" >${idle}</th>
    ';

  private static $_fieldsAttributes=array("id"=>"nobr", "reference"=>"readonly",
                                  "name"=>"required", 
                                  "idProject"=>"required", 
                                  "idAcceptanceType"=>"required",
                                  "idStatus"=>"required",
                                  "handled"=>"nobr",
                                  "done"=>"nobr",
                                  "idle"=>"nobr",
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

// ============================================================================**********
// GET VALIDATION SCRIPT
// ============================================================================**********
  
  /** ==========================================================================
   * Return the validation sript for some fields
   * @return String the validation javascript (for dojo framework)
   */
  public function getValidationScript($colName) {
    $colScript = parent::getValidationScript($colName);
    if ($colName=="idle") {   
      $colScript .= '<script type="dojo/connect" event="onChange" >';
      $colScript .= '  if (this.checked) { ';
      $colScript .= '    if (dijit.byId("idleDate").get("value")==null) {';
      $colScript .= '      var curDate = new Date();';
      $colScript .= '      dijit.byId("idleDate").set("value", curDate); ';
      $colScript .= '    }';
      $colScript .= '  } else {';
      $colScript .= '    dijit.byId("idleDate").set("value", null); ';
      $colScript .= '  } '; 
      $colScript .= '  formChanged();';
      $colScript .= '</script>';
    } else if ($colName=="done") {   
      $colScript .= '<script type="dojo/connect" event="onChange" >';
      $colScript .= '  if (this.checked) { ';
      $colScript .= '    if (dijit.byId("doneDateTime").get("value")==null) {';
      $colScript .= '      var curDate = new Date();';
      $colScript .= '      dijit.byId("doneDateTime").set("value", curDate); ';
      $colScript .= '    }';
      $colScript .= '  } else {';
      $colScript .= '    dijit.byId("doneDateTime").set("value", null); ';
      $colScript .= '  } '; 
      $colScript .= '  formChanged();';
      $colScript .= '</script>';
    } else if ($colName=="doneDateTime") {   
      $colScript .= '<script type="dojo/connect" event="onChange" >';
      $colScript .= '  if (dijit.byId("doneDateTime").get("value")!=null && dijit.byId("acceptanceDate").get("value") == null) {';
      $colScript .= '    dijit.byId("acceptanceDate").set("value", dijit.byId("doneDateTime").get("value")); ';
      $colScript .= '  }';
      $colScript .= '  formChanged();';
      $colScript .= '</script>';
    }
    return $colScript;
  }
    
  public function save() {
    $old=$this->getOld();
    
    if($this->id and $old->acceptanceDate and $this->acceptanceDate == ''){
      $acceptedWorkCommand = new WorkCommandAccepted();
      $listAcceptedWorkCommand = $acceptedWorkCommand->getSqlElementsFromCriteria(array('idAcceptance'=>$this->id));
      foreach ($listAcceptedWorkCommand as $acceptedWorkCommand){
        if($acceptedWorkCommand->acceptedDate != null){
          $acceptedWorkCommand->acceptedDate = null;
          $acceptedWorkCommand->save();
        }
      }
    }
    if($this->id and $this->acceptanceDate != null){
      $acceptedWorkCommand = new WorkCommandAccepted();
      $listAcceptedWorkCommand = $acceptedWorkCommand->getSqlElementsFromCriteria(array('idAcceptance'=>$this->id));
      foreach ($listAcceptedWorkCommand as $acceptedWorkCommand){
        $acceptedWorkCommand->acceptedDate = $this->acceptanceDate;
        $acceptedWorkCommand->save();
      }
    }
    
    $result=parent::save();
    return $result;
  }
  
  public function delete() {
    $result=parent::delete();
    return $result;
  }
  
  public function copyTo($newClass, $newType, $newName, $newProject, $structure,$withNotes, $withAttachments, $withLinks,$withAssignments = false, $withAffectations = false,$toProject = NULL, $toActivity = NULL,$copyToWithResult = false, $copyToWithActivityPrice = false,$copyToWithStatus = false, $copyToWithSubTask = false,$moveAfterCreate = null) {
    $result = parent::copyTo($newClass, $newType, $newName, $newProject,$structure, $withNotes, $withAttachments, $withLinks,$withAssignments, $withAffectations, $toProject,$toActivity, $copyToWithResult, $copyToWithActivityPrice,$copyToWithStatus, false, $moveAfterCreate);  
    if ($newClass == 'Bill') {
      $paramEnableWorkUnit = Parameter::getGlobalParameter('enableWorkCommandManagement');
      if($paramEnableWorkUnit == 'true'){
        $workCommandBilledAuto = new WorkCommandBilled();
        $autoCreatedList = $workCommandBilledAuto->getSqlElementsFromCriteria(array('idBill' => $result->id)); 
        foreach ($autoCreatedList as $autoCreated) {
          $autoCreated->delete();
        }
        $workCommandAccepted = new WorkCommandAccepted();
        $listAcceptedCommand = $workCommandAccepted->getSqlElementsFromCriteria(array('idAcceptance' => $this->id));
        foreach ($listAcceptedCommand as $acceptedCmd) {
          $workCommand = new WorkCommand($acceptedCmd->idWorkCommand);
          $workCommandBill = new WorkCommandBilled();
          $workCommandBill->idCommand = $workCommand->idCommand;
          $workCommandBill->idWorkCommand = $acceptedCmd->idWorkCommand;
          $workCommandBill->idBill = $result->id;
          $workCommandBill->billedQuantity = $acceptedCmd->acceptedQuantity;
          $workCommandBill->save();
        }
      }
    }
    return $result;
  }
  
  //ADD qCazelles
  public function control() {
    $result="";
  	$defaultControl=parent::control();
    if ($defaultControl!='OK') {
      $result.=$defaultControl;
    }
    if ($result=="") {
      $result='OK';
    }
    return $result;
  }
  
  public function drawSpecificItem($item){
    $result="";
    if($item=="AcceptedWorkCommand"){
      $workCommandAccepted = new WorkCommandAccepted();
      $listAcceptedCommand = $workCommandAccepted->getSqlElementsFromCriteria(array('idAcceptance'=>$this->id));
      drawAcceptedWorkCommand($listAcceptedCommand,$this);
    }
    return $result;
  }
}
?>