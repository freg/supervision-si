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

class AbacusDefinitionMain extends SqlElement {
  
  public $id;
  public $name;
  public $className1;
  public $className2;
  public $className3;
  public $className4;
  public $className5;
  public $idAbacusable1;
  public $idAbacusable2;
  public $idAbacusable3;
  public $idAbacusable4;
  public $idAbacusable5;
  public $idPhasing;
  public $abacusunit;
  public $assignmentWorkType;
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
    $wasIdle = false;
    if ($this->id) {
      $original = new AbacusDefinition($this->id);
      $wasIdle = ($original->idle == 1);
    }
    
    $result = parent::save();
    
    if (stripos($result, 'id="lastOperationStatus" value="OK"') === false) {
      return $result;
    }
    
    if ($this->abacusunit == 'd') {
      $this->assignmentWorkType = 'fixed';
    }
    
    if (!$wasIdle && $this->idle == 1 && $this->id) {
      $abacusLine = new AbacusLine();
      $lines = $abacusLine->getSqlElementsFromCriteria(array('idAbacusDefinition' => $this->id));
      foreach ($lines as $line) {
        if ($line->idle != 1) {
          $line->idle = 1;
          $lineResult = $line->save();
          if (stripos($lineResult, 'id="lastOperationStatus" value="OK"') === false &&
              stripos($lineResult, 'id="lastOperationStatus" value="NO_CHANGE"') === false) {
                $result  = '<div class="messageERROR">' . i18n('errorClosingAbacusLines') . '</div>';
                $result .= '<input type="hidden" id="lastOperationStatus" value="ERROR" />';
                $result .= '<input type="hidden" id="lastOperation" value="save" />';
                return $result;
              }
        }
      }
    }
    
    return $result;
  }
  
  
  public function control() {
    $result = '';
    $defaultControl = parent::control();
    if ($defaultControl != 'OK') {
      $result .= $defaultControl;
    }
    if (!$this->className1 && !$this->className2 && !$this->className3&& !$this->className4 && !$this->className5) {
      $result .= '<br/>' . i18n('errorAtLeastOneColumnRequired');
    }
    
    $poolOrResourceCount = 0;
    $classes = array($this->className1, $this->className2, $this->className3,$this->className4, $this->className5);
    foreach($classes as $className) {
      if ($className == 'ResourceOrTeam' or $className == 'ResourceFromTeam') $poolOrResourceCount++;
    }
    if ($poolOrResourceCount > 1){
      $result  = '<div class="INVALID">';
      $result .= i18n('errorOnlyOnePoolOrResourceAllowed');
      $result .= '</div>';
      $result .= '<input type="hidden" id="lastOperationStatus" value="INVALID" />';
      $result .= '<input type="hidden" id="lastOperation" value="delete" />';
    }
    

    $currentUnit = $this->abacusunit ? $this->abacusunit : 'd';
    $currentWorkType = $this->assignmentWorkType ? $this->assignmentWorkType : 'fixed';
    
    if ($currentUnit == 'd' && $currentWorkType != 'fixed') {
      $result  = '<div class="INVALID">';
      $result .= i18n('errorWorkTypeMustBeFixedForDays');
      $result .= '</div>';
      $result .= '<input type="hidden" id="lastOperationStatus" value="INVALID" />';
      $result .= '<input type="hidden" id="lastOperation" value="save" />';
    }
    
    if ($currentUnit == '%' && $currentWorkType == 'fixed') {
      $hasValueColumn = false;
      $ids = [];
      for ($i = 1; $i <= 5; $i++) {
        $field = "idAbacusable$i";
        if (!empty($this->$field)) {
          $ids[] = (int)$this->$field;
        }
      }
      
      if (!empty($ids)) {
        $crit = "id IN (" . implode(',', $ids) . ")";
        $ab = new Abacusable();
        $list = $ab->getSqlElementsFromCriteria(null, false, $crit);
        
        foreach ($list as $a) {
          if ($a->valueField == 1 && $a->className != 'Resource') {
            $hasValueColumn = true;
            break;
          }
        }
      }
      
      if (!$hasValueColumn) {
        $result  = '<div class="INVALID">';
        $result .= i18n('errorWorkTypeFixedRequiresValueColumn');
        $result .= '</div>';
        $result .= '<input type="hidden" id="lastOperationStatus" value="INVALID" />';
        $result .= '<input type="hidden" id="lastOperation" value="save" />';
      }
    }
    
    $line = new AbacusLine();
    $lines = $line->getSqlElementsFromCriteria(array('idAbacusDefinition' => $this->id));
    if (count($lines) > 0) {
      $original = new AbacusDefinition($this->id);
      $hasStructureChange = (
          $original->className1 != $this->className1 ||
          $original->className2 != $this->className2 ||
          $original->className3 != $this->className3 ||
          $original->className4 != $this->className4 ||
          $original->className5 != $this->className5
          );
      if ($hasStructureChange) {
        $result  = '<div class="INVALID">';
        $result .= i18n('errorCannotEditAbacusWithLines');
        $result .= '</div>';
        $result .= '<input type="hidden" id="lastOperationStatus" value="INVALID" />';
        $result .= '<input type="hidden" id="lastOperation" value="delete" />';
      }
    }
    
    $classes = array($this->className1, $this->className2, $this->className3, $this->className4, $this->className5);
    foreach($classes as $className) {
      if ($className) {
        $abacusable = new Abacusable();
        $abacusables = $abacusable->getSqlElementsFromCriteria(array('className' => $className));
        if (count($abacusables) == 0) {
          $result  = '<div class="INVALID">';
          $result .= i18n('errorClassNameNotFoundInAbacusable') . ' : ' . $className;
          $result .= '</div>';
          $result .= '<input type="hidden" id="lastOperationStatus" value="INVALID" />';
          $result .= '<input type="hidden" id="lastOperation" value="delete" />';
          break;
        }
      }
    }
    
    // Check if changing phasing when lines exist
    if ($this->id) {
      $original = new AbacusDefinition($this->id);
      
      if ($original->idPhasing != $this->idPhasing) {
        $line = new AbacusLine();
        $lines = $line->getSqlElementsFromCriteria(array('idAbacusDefinition' => $this->id));
        
        if (count($lines) > 0) {
          $result  = '<div class="INVALID">';
          $result .= i18n('errorCannotChangeAbacusPhasingWithLines');
          $result .= '</div>';
          $result .= '<input type="hidden" id="lastOperationStatus" value="INVALID" />';
          $result .= '<input type="hidden" id="lastOperation" value="save" />';
        }
      }
    }
    
    if ($result == "") {
      $result = 'OK';
    }
    return $result;
  }
  
  public function delete() {
    $result=parent::delete();
    if (! pq_strpos($result,'id="lastOperationStatus" value="OK"')) {
      return $result;
    }
    $line = new AbacusLine();
    $lines = $line->getSqlElementsFromCriteria(array('idAbacusDefinition' => $this->id));
    if (count($lines) > 0) {
      $result  = '<div class="INVALID">';
      $result .= i18n('errorCannotDeleteAbacusWithLines');
      $result .= '</div>';
      $result .= '<input type="hidden" id="lastOperationStatus" value="INVALID" />';
      $result .= '<input type="hidden" id="lastOperation" value="delete" />';
    }
    
    $project = new AbacusProject();
    $projects = $project->getSqlElementsFromCriteria(array('idAbacusDefinition' => $this->id));
    if (count($projects) > 0) {
      $result  = '<div class="INVALID">';
      $result .= i18n('errorCannotDeleteAbacusUsedInProject');
      $result .= '</div>';
      $result .= '<input type="hidden" id="lastOperationStatus" value="INVALID" />';
      $result .= '<input type="hidden" id="lastOperation" value="delete" />';
    }
    if ($result == "") {
      $result = 'OK';
    }
    return $result;
  }
  
  public function getStaticLayout() {
    return self::$_layout;
  }
  
  public function getAbacusLineWhere($idClassName1=null, $idClassName2=null, $idClassName3=null, $idClassName4=null, $idClassName5=null) {
    $abacusable = new Abacusable();
    $abacusables = $abacusable->getSqlElementsFromCriteria(array('valueField' => 1));
    $valueFieldClasses = array();
    foreach ($abacusables as $ab) {
      $valueFieldClasses[] = $ab->className;
    }
    
    $where = 'idAbacusDefinition=' . $this->id;
    $ids = array($idClassName1, $idClassName2, $idClassName3, $idClassName4, $idClassName5);
    
    for ($i = 1; $i <= 5; $i++) {
      $className = $this->{'className' . $i};
      if ($className && !in_array($className, $valueFieldClasses)) {
        $where .= ' AND idClassName' . $i . ' ' . (is_null($ids[$i-1]) ? 'IS NULL' : '= ' . (int)$ids[$i-1]);
      }
    }
    
    return $where;
  }
  
  
  public function copyAbacusDefinition($newName, $newIdPhasing) {
    if (!$this->id) {
      $result  = '<div class="messageERROR">' . i18n('errorAbacusDefinitionDoesNotExist') . '</div>';
      $result .= '<input type="hidden" id="lastOperationStatus" value="ERROR" />';
      $result .= '<input type="hidden" id="lastOperation" value="copy" />';
      return $result;
    }
    
    $newName = trim($newName);
    if ($newName === '') {
      $result  = '<div class="messageERROR">' . i18n('errorAbacusDefinitionEmpty') . '</div>';
      $result .= '<input type="hidden" id="lastOperationStatus" value="ERROR" />';
      $result .= '<input type="hidden" id="lastOperation" value="copy" />';
      return $result;
    }
    
    $newIdPhasing = $newIdPhasing ? $newIdPhasing : null;
    $samePhasing  = ((string)$newIdPhasing === (string)$this->idPhasing);
    
    // Copy abacus Definition
    $newDef = new AbacusDefinition();
    $newDef->name = $newName;
    $newDef->className1 = $this->className1;
    $newDef->className2 = $this->className2;
    $newDef->className3 = $this->className3;
    $newDef->className4 = $this->className4;
    $newDef->className5 = $this->className5;
    $newDef->idAbacusable1 = $this->idAbacusable1;
    $newDef->idAbacusable2 = $this->idAbacusable2;
    $newDef->idAbacusable3 = $this->idAbacusable3;
    $newDef->idAbacusable4 = $this->idAbacusable4;
    $newDef->idAbacusable5 = $this->idAbacusable5;
    $newDef->idPhasing = $newIdPhasing;
    $newDef->abacusunit = $this->abacusunit;
    $newDef->assignmentWorkType = $this->assignmentWorkType;
    $newDef->idle= 0;
    
    $allDefs = $this->getSqlElementsFromCriteria(null);
    $maxSortOrder = 0;
    foreach ($allDefs as $d) {
      if ($d->sortOrder > $maxSortOrder) $maxSortOrder = $d->sortOrder;
    }
    $newDef->sortOrder = $maxSortOrder + 1;
    
    $result = $newDef->save();
    if (stripos($result, 'id="lastOperationStatus" value="OK"') === false) {
      return $result;
    }
    
    // Copy abacus lines
    $abacusLine = new AbacusLine();
    $originalLines = $abacusLine->getSqlElementsFromCriteria(array('idAbacusDefinition' => $this->id));
    
    $lineIdMap = array();
    foreach ($originalLines as $line) {
      $newLine = new AbacusLine();
      $newLine->idAbacusDefinition = $newDef->id;
      $newLine->idClassName1 = $line->idClassName1;
      $newLine->idClassName2 = $line->idClassName2;
      $newLine->idClassName3 = $line->idClassName3;
      $newLine->idClassName4 = $line->idClassName4;
      $newLine->idClassName5 = $line->idClassName5;
      $newLine->assumption = $line->assumption;
      $newLine->example = $line->example;
      $newLine->idle = $line->idle;
      
      $lineResult = $newLine->save();
      if (stripos($lineResult, 'id="lastOperationStatus" value="OK"') === false) {
        $result  = '<div class="messageERROR">' . i18n('errorCopyingAbacusLines') . '</div>';
        $result .= '<input type="hidden" id="lastOperationStatus" value="ERROR" />';
        $result .= '<input type="hidden" id="lastOperation" value="copy" />';
        return $result;
      }
      $lineIdMap[$line->id] = $newLine->id;
    }
    
    // -- Copy the values, only if the phase has not changed
    if ($samePhasing && count($lineIdMap) > 0) {
      $abacusValue = new AbacusValue();
      $originalValues = $abacusValue->getSqlElementsFromCriteria(array('idAbacusDefinition' => $this->id));
      
      foreach ($originalValues as $val) {
        if (!isset($lineIdMap[$val->idAbacusLine])) continue;
        $newValue = new AbacusValue();
        $newValue->idAbacusDefinition = $newDef->id;
        $newValue->idAbacusLine = $lineIdMap[$val->idAbacusLine];
        $newValue->idPhase = $val->idPhase;
        $newValue->value = $val->value;
        $newValue->save();
      }
    }
    
    return $result;
  }
}
?>
