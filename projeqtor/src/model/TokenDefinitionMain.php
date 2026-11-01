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
 * Client is the owner of a project.
 */  
require_once('_securityCheck.php'); 
class TokenDefinitionMain extends SqlElement {

  public $_sec_Description_tokenDef;
  public $id;
  public $name;
  public $idProject;
  public $idle;
  public $description;
  public $_sec_treatment_tokenDef;
  public $duration;
  public $_tab_2_1 = array('', '', 'paymentAmount');
  public $amount;
  public $amountLocal;
  public $splittable;
  public $_WorkTokenMarkup;
  public $_Attachment = array();
  public $_Note = array();
  public $_nbColMax = 3;

  
  private static $_layout='
    <th field="id" formatter="numericFormatter" width="5%"># ${id}</th>
    <th field="nameProject" width="20%">${idProject}</th>
    <th field="name" width="40%">${name}</th>
    <th field="idle" width="5%" formatter="booleanFormatter">${idle}</th>
    ';
  
  
  private static $_fieldsAttributes=array(
      'name'=>'required',
      'idProject'=>'required'
  );
  
  private static $_fieldsTooltip = array(
      "splittable"=>"tooltipSplittable"
  );
  
  private static $_databaseTableName = 'worktoken';
  private static $_databaseColumnName = array();
  

   /** ==========================================================================
   * Constructor
   * @param $id Int the id of the object in the database (null if not stored yet)
   * @return void
   */ 
  function __construct($id = NULL, $withoutDependentObjects=false) {
    parent::__construct($id,$withoutDependentObjects);
    if ($this->hasCurrency() and ! $this->showGlobalCurrency()) {
      $this->_tab_2_1 = array('', '', 'paymentAmountLocal');
    }
  }

  
   /** ==========================================================================
   * Destructor
   * @return void
   */ 
  function __destruct() {
    parent::__destruct();
  }

  public function save() {
    $old = $this->getOld();
    if (!$old->duration){
      $this->duration=Work::convertImputation($this->duration);
    }
    $result=parent::save();
    return $result;
  }
  
  public function control(){
    $result="";
    $defaultControl=parent::control();
    if ($defaultControl != 'OK') {
      $result .= $defaultControl;
    }
    $old = $this->getOld();
    if($this->id){
      if($this->idProject!=$old->idProject){
        $workTokenCC= new WorkTokenClientContract();
        $clientContract= new ClientContract();
        $tableWTCC=$workTokenCC->getDatabaseTableName();
        $where=" id in (SELECT wtcc.idClientContract FROM $tableWTCC as wtcc WHERE wtcc.idWorkToken=$this->id) and idle=0 ";
        $nbClientContract=$clientContract->countSqlElementsFromCriteria(null,$where);
        if($nbClientContract > 0){
          $result .= '<br/>' . i18n ( 'cantChangeProjectUsed' );
        }
      }
      // control if orders are fully consumed for this token
//       if($this->idle!=$old->idle and $this->idle=1){
//         $workTokenCC= new WorkTokenClientContract();
//         $where="idWorkToken=$this->id and fullyConsumed!=1";
//         $nbWTCC=$workTokenCC->countSqlElementsFromCriteria(null,$where);
//         if($nbWTCC > 0){
//           $result .= '<br/>' . i18n ( 'cantChangeTokenUsedUsed' );
//         }
//       }
      
      if($this->duration!=$old->duration){
        $this->duration=Work::convertImputation($this->duration);
      }
    }
    if ($result=="") {
      $result='OK';
    }
    return $result;
  }
  
  public function setAttributes() {
    if($this->id){
      $wTCC=new WorkTokenClientContract();
      $workTokenClientContratc=SqlElement::getFirstSqlElementFromCriteria(get_class($wTCC), array('idWorkToken'=>$this->id));
      if($workTokenClientContratc->id){
        self::$_fieldsAttributes ['amount'] = 'readonly';
        self::$_fieldsAttributes ['amountLocal'] = 'readonly';
        self::$_fieldsAttributes ['duration'] = 'readonly';
      }
    }
  }
  
  
  protected function getStaticFieldsTooltip() {
    return self::$_fieldsTooltip;
  }
  
  // ============================================================================**********
  // GET VALIDATION SCRIPT
  // ============================================================================**********
  
  /** ==========================================================================
   * Return the validation sript for some fields
   * @return String the validation javascript (for dojo frameword)
   */
  public function getValidationScript($colName) {
    $colScript = parent::getValidationScript($colName);
    return $colScript;
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

  
  /** ========================================================================
   * Return the specific databaseTableName
   * @return String the databaseTableName
   */
  protected function getStaticDatabaseTableName() {
    $paramDbPrefix=Parameter::getGlobalParameter('paramDbPrefix');
    return $paramDbPrefix . self::$_databaseTableName;
  }
  /**
   * ========================================================================
   * Return the specific databaseColumnName
   * 
   * @return String the databaseTableName
   */
  protected function getStaticDatabaseColumnName() {
    return self::$_databaseColumnName;
  }
  
  
}
?>