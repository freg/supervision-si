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
 * List of orginable items
 */ 
require_once('_securityCheck.php');
class Abacusable extends SqlElement {

  // extends SqlElement, so has $id
  public $id;
  public $className;
  public $valueField;
  public $inputField;
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

  /**
   * Control data before saving
   * @return string Error message or empty string if valid
   */
  public function control() {
    $result = '';
    $defaultControl = parent::control();
    if ($this->className=='Resource') $this->valueField=1;
    if ($defaultControl != 'OK') {
      $result .= $defaultControl;
    }
    if (!$this->className) {
      $result .= '<br/>' . i18n('errorClassNameRequired');
    }
    if ($this->className && !class_exists($this->className)) {
      $result .= '<br/>' . i18n('errorClassDoesNotExist');
    }
    if ($this->valueField == 1 && $this->className) {
      if (class_exists($this->className) && $this->className!=='Resource') {
        $obj = new $this->className();
        if (!property_exists($obj, 'value')) {
          $result .= '<br/>' . i18n('errorClassHasNoValueField');
        }
      }
    }
    if (!$this->valueField && $this->inputField == 1){
      $result .= '<br/>' . i18n('errorClassHasNoValue');
    }
    
    if ($this->id) {
      $original = new Abacusable($this->id);
      if ($original->valueField != $this->valueField || $original->inputField != $this->inputField) {
        // Check if this Abacusable is referenced in any AbacusDefinition
        $abacusDefinition = new AbacusDefinition();
        $where = "idAbacusable1 = " . $this->id .
        " OR idAbacusable2 = " . $this->id .
        " OR idAbacusable3 = " . $this->id .
        " OR idAbacusable4 = " . $this->id .
        " OR idAbacusable5 = " . $this->id;
        
        $definitions = $abacusDefinition->getSqlElementsFromCriteria(null, false, $where);
        if (count($definitions) > 0) {
          $result  = '<div class="INVALID">';
          $result .= i18n('errorCannotModifyAbacusableUsedInDefinition');
          $result .= '</div>';
          $result .= '<input type="hidden" id="lastOperationStatus" value="INVALID" />';
          $result .= '<input type="hidden" id="lastOperation" value="save" />';
          return $result;
        }
      }
    }
    
    if ($result == "") {
      $result = 'OK';
    }
    return $result;
  }
    
  /** =========================================================================
   * Overrides SqlElement::deleteControl() function to add specific treatments
   * @see persistence/SqlElement#deleteControl()
   * @return String the return message of persistence/SqlElement#deleteControl() method
   */
 
  public function deleteControl() {
    $result = "";
    $definition = new AbacusDefinitionMain();
    $definitions = $definition->getSqlElementsFromCriteria(array(), false);
    
    foreach ($definitions as $def) {
      $ids = array(
          $def->idAbacusable1,
          $def->idAbacusable2,
          $def->idAbacusable3,
          $def->idAbacusable4,
          $def->idAbacusable5
      );
      
      if (in_array($this->id, $ids)) {
        $result  = '<div class="INVALID">';
        $result .= i18n('errorCannotDeleteAbacusableUsedInDefinition');
        $result .= '</div>';
        $result .= '<input type="hidden" id="lastOperationStatus" value="INVALID" />';
        $result .= '<input type="hidden" id="lastOperation" value="delete" />';
        break;
      }
    }
    
    if (! $result) {
      $result = parent::deleteControl();
    }
    
    return $result;
  }
  
  function save() {
    if ($this->className=='Resource') $this->valueField=1;
    return parent::save();
  }
  
  
}
?>