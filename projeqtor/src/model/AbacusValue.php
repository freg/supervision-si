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
class AbacusValue extends SqlElement {

  // extends SqlElement, so has $id
  public $id;
  public $idAbacusDefinition;
  public $idAbacusLine;
  public $idPhase;
  public $value;
  
  
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

  public function control() {
    $result = '';
    
    // Validate that phase belongs to the phasing of the abacus definition
    if ($this->idPhase && $this->idAbacusDefinition) {
      $abacusDef = new AbacusDefinition($this->idAbacusDefinition);
      
      if ($abacusDef && $abacusDef->id && $abacusDef->idPhasing) {
        $phase = new Phase($this->idPhase);
        
        if (!$phase || !$phase->id) {
          $result  = '<div class="INVALID">';
          $result .= i18n('errorPhaseDoesNotExist');
          $result .= '</div>';
          $result .= '<input type="hidden" id="lastOperationStatus" value="INVALID" />';
          $result .= '<input type="hidden" id="lastOperation" value="save" />';
          return $result;
        }
        
        if ($phase->idPhasing != $abacusDef->idPhasing) {
          $result  = '<div class="INVALID">';
          $result .= i18n('errorPhaseDoesNotBelongToPhasing');
          $result .= '</div>';
          $result .= '<input type="hidden" id="lastOperationStatus" value="INVALID" />';
          $result .= '<input type="hidden" id="lastOperation" value="save" />';
          return $result;
        }
        
        // Check if phase is closed
        if ($phase->idle == 1) {
          $result  = '<div class="INVALID">';
          $result .= i18n('errorCannotUseClosedPhase');
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
  
}
?>