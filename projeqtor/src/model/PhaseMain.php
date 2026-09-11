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

class PhaseMain extends SqlElement {
  
  public $id;
  public $idPhasing;
  public $name;
  public $duration;
  public $shortName;
  public $sortOrder;
  public $idle;
   
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
  
  public function save() {
    $result = parent::save();
    if (stripos($result, 'id="lastOperationStatus" value="OK"') === false) {
      return $result;
    }

    return $result;
  }
  
  
  public function control() {
    $result = '';
    $defaultControl = parent::control();
    if ($defaultControl != 'OK') {
      $result .= $defaultControl;
    }
    if ($result == "") {
      $result = 'OK';
    }
    return $result;
  }
  
  public function delete() {
    $result = parent::delete();
    
    if (stripos($result, 'id="lastOperationStatus" value="OK"') === false) {
      return $result;
    }
    
    if (!$this->id) {
      return $result;
    }
    
    // Check if phase is used in AbacusValue
    $abacusValue = new AbacusValue();
    $usedInValues = $abacusValue->getSqlElementsFromCriteria(array('idPhase' => $this->id));
    
    if (count($usedInValues) > 0) {
      $result  = '<div class="INVALID">';
      $result .= i18n('errorCannotDeletePhaseUsedInAbacusLines');
      $result .= '</div>';
      $result .= '<input type="hidden" id="lastOperationStatus" value="INVALID" />';
      $result .= '<input type="hidden" id="lastOperation" value="delete" />';
      return $result;
    }
    
    // Check if phase is used in Activity
    $act = new Activity();
    $actList = $act->getSqlElementsFromCriteria(array('idPhase' => $this->id));
    
    if (count($actList) > 0) {
      $result  = '<div class="INVALID">';
      $result .= i18n('errorCannotDeletePhaseUsedInActivities');
      $result .= '</div>';
      $result .= '<input type="hidden" id="lastOperationStatus" value="INVALID" />';
      $result .= '<input type="hidden" id="lastOperation" value="delete" />';
      return $result;
    }
    
    // Clean up references in Activities
    $act = new Activity();
    $actList = $act->getSqlElementsFromCriteria(array('idPhase' => $this->id));
    foreach ($actList as $a) {
      $a->idPhase = null;
      $a->save();
    }
    
    return $result;
  }
  
  public function getStaticLayout() {
    return self::$_layout;
  }
   
}
?>
