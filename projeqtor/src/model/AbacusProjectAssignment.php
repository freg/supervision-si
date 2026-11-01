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
class AbacusProjectAssignment extends SqlElement {

  public $id;
  public $idAbacusProject;
  public $idAssignment;
  public $idAbacusDefinition;
  public $idAffectable;
  public $idProject;
  public $refType;
  public $refId;
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

  /**
   * Control data before saving
   * @return string Error message or empty string if valid
   */
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
    
  /** =========================================================================
   * Overrides SqlElement::deleteControl() function to add specific treatments
   * @see persistence/SqlElement#deleteControl()
   * @return String the return message of persistence/SqlElement#deleteControl() method
   */
 
  public function deleteControl() {
    $result = "";    
    if (! $result) {
      $result = parent::deleteControl();
    }    
    return $result;
  } 
  
}
?>