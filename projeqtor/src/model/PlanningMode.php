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
 * RiskType defines the type of a risk.
 */ 
require_once('_securityCheck.php');
class PlanningMode extends SqlElement {

  // extends SqlElement, so has $id
  public $_sec_description;
  public $id;
  public $name;
  public $code;
  public $sortOrder=0;
  public $mandatoryStartDate;
  public $mandatoryEndDate;
  public $mandatoryDuration;
  public $defaultDuration;
  public $proportional;
  public $_lib_proportional;
  public $applyTo;
  public $idle ;
  //public $_sec_void;
  
  public $_isNameTranslatable = true;
  public $_isApplyToTranslatable = true;
  public $_noDelete=true;
  public $_noCreate=true;
  
  // Define the layout that will be used for lists
  private static $_layout='
    <th field="id" formatter="numericFormatter" width="10%"># ${id}</th>
    <th field="name" width="55%" formatter="translateFormatter">${name}</th>  
    <th field="applyTo" width="20%" formatter="translateFormatter">${applyTo}</th>
    <th field="sortOrder" formatter="numericFormatter" width="10%"># ${sortOrder}</th>
    <th field="idle" width="5%" formatter="booleanFormatter">${idle}</th>
    ';

  private static $_fieldsAttributes=array(
      "name"=>"readonly",
      "code"=>"readonly",
      "sortOrder"=>"readonly",
      "mandatoryStartDate"=>"readonly",
      "mandatoryEndDate"=>"readonly",
      "mandatoryDuration"=>"readonly",
      "applyTo"=>"readonly",
      "defaultDuration"=>"hidden"
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
  
  public static function isProportional($idPlanningMode) {
    if (! $idPlanningMode) return false;
   $proportional=SqlList::getFieldFromId('PlanningMode',$idPlanningMode,'proportional');
   if ($proportional==1 ) return true;
    else return false;
  }
  public static function isProportionable($idPlanningMode) {
    if (! $idPlanningMode) return false;
    $code=SqlList::getFieldFromId('PlanningMode',$idPlanningMode,'code');
    if ($code=='REGUL' or $code=='FULL' or $code=='HALF' or $code=='QUART' or $code=='FDUR' or $code=='DDUR' or $code=='CDUR') return true;
    else return false;
  }
  public static function isRegularDuration($idPlanningMode) {
    if (! $idPlanningMode) return false;
    $code=SqlList::getFieldFromId('PlanningMode',$idPlanningMode,'code');
    if ($code=='REGUL' or $code=='FULL' or $code=='HALF' or $code=='QUART') return true;
    else return false;
  }
  public static function isFixedDuration($idPlanningMode) {
    if (! $idPlanningMode) return false;
    //     if ($idPlanningMode==8 or $idPlanningMode==14 or $idPlanningMode==27 or $idPlanningMode==28 or $idPlanningMode==29 or $idPlanningMode==30) return true;
//     else return false;
    $code=SqlList::getFieldFromId('PlanningMode',$idPlanningMode,'code');
    if ($code=='FDUR' or $code=='DDUR' or $code=='CDUR' ) return true;
    else return false;
  }
  public static function isFixed($idPlanningMode) {
    if (! $idPlanningMode) return false;
    $code=SqlList::getFieldFromId('PlanningMode',$idPlanningMode,'code');
    if ($code=='FIXED' or $code=='MAN') return true;
    else return false;
  }
  public static function isManual($idPlanningMode) {
    if (! $idPlanningMode) return false;
    $code=SqlList::getFieldFromId('PlanningMode',$idPlanningMode,'code');
    if ($code=='MAN') return true;
    else return false;
  }
  
  public function setAttributes(){
    if ($this->id and self::isFixedDuration($this->id)) {
      self::$_fieldsAttributes ['defaultDuration'] = '';
    }
    if ($this->id and (self::isFixedDuration($this->id) or self::isRegularDuration($this->id))) {
      self::$_fieldsAttributes ['proportional'] = 'nobr';
    } else {
      self::$_fieldsAttributes ['proportional'] = 'hidden';
    }
  }
}
?>