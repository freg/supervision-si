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
 * Stauts defines list stauts an activity or action can get in (lifecylce).
 */ 
require_once('_securityCheck.php');
class Role extends SqlElement {

  // extends SqlElement, so has $id
  public $_sec_Description;
  public $id;    // redefine $id to specify its visible place 
  public $name;
  public $sortOrder=0;
  public $defaultCost;
  public $defaultExternalCost;
  public $_spe_updateResourceCost;
  public $idle;
  public $description;
  //public $_sec_void;
  
  // Define the layout that will be used for lists
  private static $_layout='
    <th field="id" formatter="numericFormatter" width="10%"># ${id}</th>
    <th field="name" width="75%">${name}</th>
    <th field="sortOrder"  formatter="numericFormatter" width="10%">${sortOrderShort}</th>    
    <th field="idle" width="5%" formatter="booleanFormatter">${idle}</th>
    ';

  
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
  
  // ============================================================================**********
  // GET VALIDATION SCRIPT
  // ============================================================================**********
  
  /** ==========================================================================
   * Return the validation sript for some fields
   * @return String the validation javascript (for dojo framework)
   */
  public function getValidationScript($colName) {
    $colScript = parent::getValidationScript($colName);
    if ($colName=="defaultCost") {
      $colScript .= '<script type="dojo/connect" event="onChange" >';
      $colScript .= '  var defaultExternalCost=dijit.byId("defaultExternalCost");';
      $colScript .= '  if(!defaultExternalCost.value){';
      $colScript .= '   defaultExternalCost.set("value", this.value);';
      $colScript .= '  }';
      $colScript .= '  formChanged();';
      $colScript .= '</script>';
    }
    return $colScript;
  }
  
  /**
   * =========================================================================
   * Draw a specific item for the current class.
   *
   * @param String $item the
   *        	item. Correct values are :
   *        	- subprojects => presents sub-projects as a tree
   * @return String an html string able to display a specific item
   *         must be redefined in the inherited class
   */
  public function drawSpecificItem($item, $readOnly=false, $included=false, $hasToken=false) {
    global $print, $comboDetail, $nbColMax;
    $result = "";
    if($item=="updateResourceCost"){
      $result .= '<div style="position:absolute; right:2px;';
      if (isNewGui()) $result .= ' text-align: center; text-align: right;">';
      else $result .= ' border: 0px solid #FFFFFF; -moz-border-radius: 15px; border-radius: 15px; text-align: right;">';
      if (isNewGui()) $result .= '<div style="position:absolute;top:-34px;right:0px;text-align:right;">';
      else $result .= '<div style="position:absolute;right:0px;width:80px !important;top:-24px;text-align:right;">';
      $result .= '<button id="updateResourceCost" dojoType="dijit.form.Button" showlabel="true"';
      if (isNewGui()) $result .= ' title="'.i18n('updateResourceCostTitle').'" style="vertical-align: middle;" class="roundedVisibleButton">';
      else $result .= ' title="'.i18n('updateResourceCostTitle').'" style="vertical-align: middle;">';
      $result .= '<span>' . i18n('updateResourceCost') . '</span>';
      $result .= '<script type="dojo/connect" event="onClick" args="evt">';
      $result .= '  showUpdateResourceCost("' . htmlEncode($this->id) . '");';
      $result .= '</script>';
      $result .= '</button>';
      $result.='</div>';
      $result.='</div>';
    }
    return $result;
  }
}
?>