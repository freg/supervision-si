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
class IncomingMailMain extends SqlElement {

public $_sec_description;
  public $id;    // redefine $id to specify its visible place 
  public $name;
  public $idProject;
  public $idIncomingMailType;
  public $receptionDate;
  public $idDeliveryMode;
  public $idResponsible;
  public $idStatus;
  public $idle;
  public $description;
  public $_sec_descriptionTransmitter;
  public $idProvider;
  public $idClient;
  public $idAffectable;
  public $descriptionTransmitter;
  public $_sec_ApproverMail;
  public $idApprovalStatus;
  public $_Approver=Array();
  public $_sec_Link;
  public $_Link = array();
  public $_Attachment=array();
  public $_Note=array();
  public $_nbColMax=3;
  
  // Define the layout that will be used for lists
  private static $_layout='
    <th field="id" formatter="numericFormatter" width="5%" ># ${id}</th>
    <th field="nameProject" width="20%" >${idProject}</th>
    <th field="name" width="50" >${name}</th>
    <th field="nameIncomingMailType" width="20%">${idIncomingMailType}</th> 
    <th field="idle" width="5%" formatter="booleanFormatter">${idle}</th>
    ';

  private static $_fieldsAttributes=array( 
                                          "name"=>"required", 
                                          "idProject"=>"required",
                                          "idIncomingMailType"=>"required",                     
                                          "idStatus"=>"required",
                                          "idApprovalStatus"=>"readonly",
  );  
  
  private static $_colCaptionTransposition = array('idResponsible'=> 'responsible','idDeliveryMode'=>'ReceiveMode','idAffectable' =>'Sender');
  
  private static $_databaseColumnName = array( 'idAffectable' =>'idContact');
    
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
  
// ============================================================================**********
// GET VALIDATION SCRIPT
// ============================================================================**********
  
  /** ==========================================================================
   * Return the validation sript for some fields
   * @return String the validation javascript (for dojo framework)
   */
  public function getValidationScript($colName) {
    $colScript = parent::getValidationScript($colName);
//     if ($colName=="initialDueDate") {
//       $colScript .= '<script type="dojo/connect" event="onChange" >';
//       $colScript .= '  if (dijit.byId("actualDueDate").get("value")==null) { ';
//       $colScript .= '    dijit.byId("actualDueDate").set("value", this.value); ';
//       $colScript .= '  } ';
//       $colScript .= '  formChanged();';
//       $colScript .= '</script>';     
//     }
    return $colScript;
  }
  

  /**=========================================================================
   * Overrides SqlElement::save() function to add specific treatments
   * @see persistence/SqlElement#save()
   * @return String the return message of persistence/SqlElement#save() method
   */
  public function save() {
    
    if(!$this->id){
      $this->idApprovalStatus = 1;
    }
    
    $result = parent::save();
    return $result;
  }
 
  public function setAttributes(){
  }
  
  public function getApprovalStatus() {
    $approver = new Approver();
    $lstApprover = $approver->getSqlElementsFromCriteria(array('refType'=>'IncomingMail','refId'=>$this->id));
    if(!$lstApprover){
      $result = 1;
    }else{
      $reject = false;
      $approved = true;
      $notReject = false;
      foreach ($lstApprover as $app){
        if($app->approved != 1)$approved = false;
        if($app->disapproved == 1) $reject = true;
        if($app->approved==0 and $app->disapproved==0)$notReject = true;
      }
      if($approved)$result = 4;
      if($reject)$result=2;
      if($notReject and !$reject)$result=3;
    }
    return $result;
  }
  
}
?>