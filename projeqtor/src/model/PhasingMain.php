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

class PhasingMain extends SqlElement {
  
  public $id;
  public $name;
  public $idle;
  
  private static $_layout = '
    <th field="id" formatter="numericFormatter" width="5%" ># ${id}</th>
    <th field="name" width="80%">${name}</th>
    <th field="idle" width="5%" formatter="booleanFormatter" >${idle}</th>
  ';
  
  private static $_fieldsAttributes = array(
      "id"=>"nobr",
      "name"=>"required",
      "idle"=>"nobr",
  ); 
  
  /**
   * ==========================================================================
   * Constructor
   *
   * @param $id Int the
   *          id of the object in the database (null if not stored yet)
   * @return void
   */
  public function __construct($id = NULL, $withoutDependentObjects=false) {
    parent::__construct($id, $withoutDependentObjects);
  }
  
  /**
   * ==========================================================================
   * Destructor
   *
   * @return void
   */
  function __destruct() {
    parent::__destruct ();
  }
  
  
  public function delete() {
    $result = parent::delete();
    
    if (stripos($result, 'id="lastOperationStatus" value="OK"') === false) {
      return $result;
    }
    
    if (!$this->id) {
      return $result;
    }
    
    // Check if phasing is used in AbacusValue (via AbacusLine)
    $abacusValue = new AbacusValue();
    $phase = new Phase();
    $phases = $phase->getSqlElementsFromCriteria(array('idPhasing' => $this->id));
    
    $phaseIds = array();
    foreach ($phases as $ph) {
      $phaseIds[] = $ph->id;
    }
    
    if (!empty($phaseIds)) {
      $wherePhases = 'idPhase IN (' . implode(',', $phaseIds) . ')';
      $usedInValues = $abacusValue->getSqlElementsFromCriteria(null, false, $wherePhases);
      
      if (count($usedInValues) > 0) {
        $result  = '<div class="INVALID">';
        $result .= i18n('errorCannotDeletePhasingUsedInAbacusLines');
        $result .= '</div>';
        $result .= '<input type="hidden" id="lastOperationStatus" value="INVALID" />';
        $result .= '<input type="hidden" id="lastOperation" value="delete" />';
        return $result;
      }
    }
    
    // Check if phasing is used in AbacusDefinition
    $abacusDef = new AbacusDefinition();
    $defsUsingPhasing = $abacusDef->getSqlElementsFromCriteria(array('idPhasing' => $this->id));
    
    if (count($defsUsingPhasing) > 0) {
      foreach ($phases as $ph) {
        if ($ph->idle != 1) {
          $ph->idle = 1;
          $ph->save();
        }
      }
      
      // Set idPhasing to null in all AbacusDefinition
      foreach ($defsUsingPhasing as $def) {
        $def->idPhasing = null;
        $def->save();
      }
      
      // Close the phasing
      $this->idle = 1;
      
      $result  = '<div class="OK">';
      $result .= i18n('phasingClosedDueToUsage');
      $result .= '</div>';
      $result .= '<input type="hidden" id="lastOperationStatus" value="OK" />';
      $result .= '<input type="hidden" id="lastOperation" value="save" />';
      return $result;
    }
    
    // If phasing has phases but is not used, warn and delete all
    if (count($phases) > 0) {
      foreach ($phases as $ph) {
        $ph->delete();
      }
    }
    
    // Clean up references in Projects and Activities (existing code)
    $proj = new Project();
    $projList = $proj->getSqlElementsFromCriteria(array('idPhasing' => $this->id));
    foreach ($projList as $p) {
      $p->idPhasing = null;
      $p->save();
    }
    
    $act = new Activity();
    $actList = $act->getSqlElementsFromCriteria(array('idPhasing' => $this->id));
    foreach ($actList as $a) {
      $a->idPhasing = null;
      $a->save();
    }
    
    return $result;
  }
  /**
   * ==========================================================================
   * Return the specific layout
   *
   * @return String the layout
   */
   public function getStaticLayout() {
    return self::$_layout;
  }
}
?>