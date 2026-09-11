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
 * Line defines right to the application for a menu and a profile.
 */  
require_once('_securityCheck.php'); 
class KpiValueRequest extends SqlElement {

  // extends SqlElement, so has $id
  public $id;    // redefine $id to specify its visible place 
  //public $name;
  public $refType;
  public $refId;
  public $requestDate;
  public $requestDateTime;
  public $_noHistory=true; // Will never save history for this object
  public Static $_noKpiHistory=false;
  
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
// GET VALIDATION SCRIPT
// ============================================================================**********
 
  public function save() {
    //$this->id=null; // Temp will alwyas store new line, to avoid Locks
    $this->requestDateTime=date("Y-m-d H:i:s");
    $this->requestDate=date("Y-m-d");
    $result=parent::save();
    self::triggerCalculation(); // Required if Cron is not running...
    return $result;
  }
  public static function triggerCalculation($time=null) {
    $kvr=new KpiValueRequest();
    if (!$time) $time=date("Y-m-d 00:00:00");
    $crit="requestDateTime<'$time'";
    $cpt=$kvr->countGroupedSqlElementsFromCriteria(null, array('refType','refId','requestDate'),$crit);
    if (count($cpt)>0) {
      foreach($cpt as $key=>$cptVal) {
        $split=pq_explode('|',$key);
        $refType=$split[0];
        $refId=$split[1];
        $requestDate=$split[2];
        if (!SqlElement::class_exists($refType)) continue;
        $obj=new $refType($refId);
        KpiValue::calculateKpiExecute($obj,null,$requestDate);
      }
      $resPurge=$kvr->purge($crit);
    }
  }
  
}
?>
