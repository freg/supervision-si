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
class RestrictType extends SqlElement {

  // extends SqlElement, so has $id
  public $id;    // redefine $id to specify its visible place 
  public $idProject;
  public $idProjectType;
  public $idProfile;
  public $idType;
  public $className;
  
  private static $arrayProfileRestrictions=null;
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
// MISCELLANOUS FUNCTIONS
// ============================================================================**********
  public static function isTypeVisible($class,$type,$profile) {
    if(! Parameter::getGlobalParameter('hideItemTypeRestrictionOnProject')=='YES') return true;
    if (self::$arrayProfileRestrictions===null) {
      self::getArrayProfileRestrictions(); 
    }
    if (self::$arrayProfileRestrictions===null or count(self::$arrayProfileRestrictions)==0) return true;
    if (!isset(self::$arrayProfileRestrictions[$profile])) return true;
    if (!isset(self::$arrayProfileRestrictions[$profile][$class])) return true;
    if (isset(self::$arrayProfileRestrictions[$profile][$class][$type])) return true;
    else return false;
  } 
  
  
  public static function isTypeVisibleForProject($class,$type,$project) {
    $user=getSessionUser();
    $profile=$user->getProfile($project);
    return self::isTypeVisible($class,$type,$profile);
  }
  
  private static function getArrayProfileRestrictions() {
    $res=array();
    $rt=new RestrictType();
    $rtList=$rt->getSqlElementsFromCriteria(null,false, "idProfile is not null and idProject is null and idProjectType is null");
    foreach ($rtList as $rt) {
      $prf=$rt->idProfile;
      $cls=pq_substr($rt->className, 0, -4);
      if (! isset($res[$prf])) $res[$prf]=array();
      if (! isset($res[$prf][$cls])) $res[$prf][$cls]=array();
      $res[$prf][$cls][$rt->idType]=$rt->idType;
    }
    self::$arrayProfileRestrictions=$res;
  }
  
}
?>