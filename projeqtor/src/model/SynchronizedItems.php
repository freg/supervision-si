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
 * Synchronized items is list of all items that are synchronized.
 */ 
require_once('_securityCheck.php');
class SynchronizedItems extends SqlElement {

  // extends SqlElement, so has $id
  public $id;    // redefine $id to specify its visiblez place
  public $idSynchronization;
  public $ref1Type;
  public $ref1Id;
  public $ref2Type;
  public $ref2Id;
  
  private static $_fieldsAttributes=array(
  );
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
  /** ==========================================================================
   * Return the specific fieldsAttributes
   * @return Array the fieldsAttributes  
   */
  protected function getStaticFieldsAttributes() {
  	return self::$_fieldsAttributes;
  }
    
  /** ==========================================================================
   * Return the key of item synchronized with given item
   * @return Array the fieldsAttributes  
   */
  public static function getSynchronizedItemKey($refType,$refId) {
    if (!$refType or !$refId) return null;
    $si=new SynchronizedItems();
    $crit="(ref1Type='$refType' and ref1Id=$refId) or ((ref2Type='$refType' and ref2Id=$refId) )";
    $siList=$si->getSqlElementsFromCriteria(null,null,$crit);
    if (count($siList)==0) return null; // Not synchronized
    if (count($siList)>1) {
      traceLog("Synchronization::getSynchronizedItemKey($refType,$refId) : multisynchronization detected, return only first");
    }
    $si=reset($siList);
    if ($si->ref1Type==$refType and $si->ref1Id==$refId) return $si->ref2Type.'#'.$si->ref2Id;
    else return $si->ref1Type.'#'.$si->ref1Id;
  }
  /** ==========================================================================
   * Return the item synchronized with given item
   * @return Array the fieldsAttributes  
   */
  public static function getSynchronizedItemObj($refType,$refId) {
    $key= self::getSynchronizedItemKey($refType,$refId);
    if ($key==null) return null;
    $split=pq_explode('#',$key);
    $class=$split[0];
    $id=$split[1];
    if (! class_exists($class)) {
      traceLog("Synchronization::getSynchronizedItemObj($refType, $refId) : $class is not an existing class");
      return null;
    }
    $obj=new $class($id);
    return $obj;
  }
  public static function deletedSynchronizedItem($refType,$refId) {
    if (!$refType or !$refId) return null;
    $si=new SynchronizedItems();
    $crit="(ref1Type='$refType' and ref1Id=$refId) or ((ref2Type='$refType' and ref2Id=$refId) )";
    $siList=$si->getSqlElementsFromCriteria(null,null,$crit);
    if (count($siList)==0) return null; // Not synchronized
    if (count($siList)>1) {
      traceLog("Synchronization::getSynchronizedItemKey($refType,$refId) : multisynchronization detected, return only first");
    }
    $si=reset($siList);
    if ($si->ref1Type=='Activity' and $si->ref2Type=='Ticket') {
      $tkt=new Ticket($si->ref2Id);
      if ($tkt->id) {
        $tkt->idActivity=null;
        $resSaveTkt=$tkt->saveForced();
      }
    }
    return $si->delete();

  }
  
  public static function getNumberSynchronizedItemByProject($idProject) {
//     $cpt = 0;
//     $synch = SqlElement::getSingleSqlElementFromCriteria('Synchronization', array('idProject'=>$idProject));
//     $obj = new SynchronizedItems();
//     $list =  $obj->getSqlElementsFromCriteria(array('idSynchronization'=>$synch->id));
//     foreach ($list as $synchItem){
//       $ticket = new Ticket($synchItem->ref2Id);
//       if(!$ticket->idle)$cpt++;
//     }
//     return $cpt;
    // Previous way only counted items synchronised with current rule on project
    // This did not count items if rule was deleted the recreated, and also items than were moved from pther project (but synchronized
    if (! $idProject) return 0;
    $tkt=new Ticket();$tktTable=$tkt->getDatabaseTableName();
    $si=new SynchronizedItems();
    $cpt=$si->countSqlElementsFromCriteria(null,"ref2Type='Ticket' and exists (select 'x' from $tktTable t where t.id=ref2id and idle=0 and t.idProject=$idProject)");
    return $cpt; 
  }
  
  public static function getNumberSynchronizedItemByProjectAll($idProject) {
//     $cpt = 0;
//     $synch = SqlElement::getSingleSqlElementFromCriteria('Synchronization', array('idProject'=>$idProject));
//     $obj = new SynchronizedItems();
//     $cpt =  $obj->countSqlElementsFromCriteria(array('idSynchronization'=>$synch->id));
    if (! $idProject) return 0;
    $tkt=new Ticket();$tktTable=$tkt->getDatabaseTableName();
    $si=new SynchronizedItems();
    $cpt=$si->countSqlElementsFromCriteria(null,"ref2Type='Ticket' and exists (select 'x' from $tktTable t where t.id=ref2id and t.idProject=$idProject)");
    return $cpt;
  }
}
?>