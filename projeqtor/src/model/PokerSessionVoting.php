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
class PokerSessionVoting extends SqlElement {
   
   public $_sec_description;
   public $_spe_pokerVote;
   public $_sec_detail;
   public $id;
   public $idUser;
   public $idProject;
   public $idResource;
   public $name;
   public $description;
  
   private static $_databaseTableName = 'pokersession';
  
   private static $_fieldsAttributes=array(
       'id'=>'hidden', 
       'name'=>'readonly',
       'idProject'=>'readonly', 
       'idResource'=>'readonly');
   
   private static $_colCaptionTransposition = array(
       'idUser'=>'issuer',
       'idResource'=> 'responsible');
   
   private static $_databaseCriteria = array('handled'=>'1');
   
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
  
  /** ========================================================================
   * Return the specific database criteria
   * @return String the databaseTableName
   */
  protected function getStaticDatabaseCriteria() {
  	return self::$_databaseCriteria;
  }
  /** ============================================================================
   * Return the specific colCaptionTransposition
   * @return String the colCaptionTransposition
   */
  protected function getStaticColCaptionTransposition($fld=null) {
    return self::$_colCaptionTransposition;
  }
  
  public function drawSpecificItem($item) {
    global $print;
    $canUpdate=securityGetAccessRightYesNo('menuPokerSessionVoting', 'update', $this) == "YES";
    $result = "";
    if($item=="pokerVote"){
        $pokerSession = new PokerSession($this->id, true);
    	drawPokerVote($pokerSession);
    }
//     return $result;
  }
}?>