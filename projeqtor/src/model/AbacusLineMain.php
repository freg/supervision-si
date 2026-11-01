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

class AbacusLineMain extends SqlElement {
  public $id;
  public $idAbacusDefinition;
  public $idClassName1;
  public $idClassName2;
  public $idClassName3;
  public $idClassName4;
  public $idClassName5;
  public $assumption;
  public $example;
  public $idle;
  
  public $_AbacusDefinition = null;
  
  
  /** @var array Field definitions */
  private static $_fieldsAttributes=array("id"=>"nobr", 
      "idAbacusDefinition"=>"nobr", 
  ); 
  
  /**
   * Constructor
   * @param int $id ID of the object
   * @param bool $withoutDependentObjects Flag to not load dependent objects
   */
  public function __construct($id = NULL, $withoutDependentObjects = false) {
    parent::__construct($id, $withoutDependentObjects);
  }
  
  
  /** ==========================================================================
   * Destructor
   * @return void
   */
  function __destruct() {
    parent::__destruct();
  }
  
  public function control() {
    $result ='';
    if (!$this->idAbacusDefinition) {
      $result  = '<div class="INVALID">';
      $result .= i18n('errorAbacusDefinitionRequired');
      $result .= '</div>';
      $result .= '<input type="hidden" id="lastOperationStatus" value="INVALID" />';
      $result .= '<input type="hidden" id="lastOperation" value="delete" />';
      return $result;
    }
    
    $existing = $this->getSqlElementsFromCriteria(array(
        'idAbacusDefinition' => $this->idAbacusDefinition,
        'idClassName1'       => $this->idClassName1,
        'idClassName2'       => $this->idClassName2,
        'idClassName3'       => $this->idClassName3,
        'idClassName4'       => $this->idClassName4,
        'idClassName5'       => $this->idClassName5,
    ));
    
    foreach ($existing as $line) {
      if ($line->id == $this->id) continue;
      $result  = '<div class="INVALID">';
      $result .= i18n('errorDuplicateAbacusLine');
      $result .= '</div>';
      $result .= '<input type="hidden" id="lastOperationStatus" value="INVALID" />';
      $result .= '<input type="hidden" id="lastOperation" value="delete" />';
    }
    
    $abacusDef = new AbacusDefinition($this->idAbacusDefinition);
    
    if (!$abacusDef || !$abacusDef->id) {
      $result  = '<div class="INVALID">';
      $result .= i18n('errorAbacusDefinitionDoesNotExist');
      $result .= '</div>';
      $result .= '<input type="hidden" id="lastOperationStatus" value="INVALID" />';
      $result .= '<input type="hidden" id="lastOperation" value="delete" />';
      return $result;
    }
    
    if ($abacusDef && $abacusDef->id) {     
      $classNameMap = array(
          1 => array('id' => 'idClassName1', 'class' => 'className1', 'abacusable' => 'idAbacusable1'),
          2 => array('id' => 'idClassName2', 'class' => 'className2', 'abacusable' => 'idAbacusable2'),
          3 => array('id' => 'idClassName3', 'class' => 'className3', 'abacusable' => 'idAbacusable3'),
          4 => array('id' => 'idClassName4', 'class' => 'className4', 'abacusable' => 'idAbacusable4'),
          5 => array('id' => 'idClassName5', 'class' => 'className5', 'abacusable' => 'idAbacusable5'),
      );    
  
      foreach ($classNameMap as $num => $mapping) {
        $idField = $mapping['id'];
        $classField = $mapping['class'];
        $abacusableField = $mapping['abacusable'];
        $expectedId = $abacusDef->$abacusableField;
        $idValueInLine = $this->$idField;     
        // Case 1 : Column filled in the row but NOT defined in the abacusDefinition 
        if (!$expectedId) {
          if ($idValueInLine) {
            $result  = '<div class="INVALID">';
            $result .= i18n('errorAbacusColumnNotDefined', array($idField, $classField));
            $result .= '</div>';
            $result .= '<input type="hidden" id="lastOperationStatus" value="INVALID" />';
            $result .= '<input type="hidden" id="lastOperation" value="delete" />';
            return $result;
          }
          break;
        }
            
        // Case 2 : Column filled but it is a valueField
        $abacusable = new Abacusable($expectedId);
        if ($abacusable->valueField && !$abacusable->inputField) {
          if ($idValueInLine) {
            $result  = '<div class="INVALID">';
            $result .= i18n('errorAbacusValueFieldCannotBeFilled', array($idField, $classField));
            $result .= '</div>';
            $result .= '<input type="hidden" id="lastOperationStatus" value="INVALID" />';
            $result .= '<input type="hidden" id="lastOperation" value="delete" />';
            return $result;
          }
          continue;
        }

        // Case 3 : Column not filled and it isnot a valueField
        if (!$idValueInLine) {
          $result  = '<div class="INVALID">';
          $result .= i18n('errorAbacusColumnMustBeFilled', array($idField, $classField));
          $result .= '</div>';
          $result .= '<input type="hidden" id="lastOperationStatus" value="INVALID" />';
          $result .= '<input type="hidden" id="lastOperation" value="delete" />';
          return $result;
        }
            
      }
    } else {
      $result  = '<div class="INVALID">';
      $result .= i18n('errorAbacusDefinitionNoExist', array($idField, $classField));
      $result .= '</div>';
      $result .= '<input type="hidden" id="lastOperationStatus" value="INVALID" />';
      $result .= '<input type="hidden" id="lastOperation" value="delete" />';
      return $result;
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
    $abacusDef = new AbacusDefinition($this->idAbacusDefinition);
    $abacusable = new Abacusable();
    $abacusables = $abacusable->getSqlElementsFromCriteria(array('valueField' => 1));
    $valueFieldClasses = array();
    foreach ($abacusables as $ab) {
      $valueFieldClasses[] = $ab->className;
    }
    
    $abacusProject = new AbacusProject();
    $where = $abacusDef->getAbacusLineWhere($this->idClassName1, $this->idClassName2, $this->idClassName3,$this->idClassName4, $this->idClassName5);
    
    $existing = $abacusProject->getSqlElementsFromCriteria(null, false, $where);
    foreach ($existing as $line) {
      if ($line->id == $this->id) continue;
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
    
  
}
?>
