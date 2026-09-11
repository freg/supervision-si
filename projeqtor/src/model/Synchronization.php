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
 * Synchronization defined who to start a synchronization with items
 */ 
require_once('_securityCheck.php');
class Synchronization extends SqlElement {

  // extends SqlElement, so has $id
  public $id;    // redefine $id to specify its visiblez place
  public $idProject;
  public $originType="Ticket";    // First version only from Ticket to Activity
  public $targetType="Activity";  // First version only from Ticket to Activity
  public $idStatus;
  public $idOrigineType;
  public $idTargetType;
  public $setActivity;
  private static $_lastErrorMessage='';
  static $_createSyncItemInProgress=false;
  static $_synchInProgress=false;
 
  private static $_fieldsAttributes=array(
      "idProject"=>"required,unique",
      "idStatus"=>"required",
      "idTargetType"=>"required"
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
  
  public function save() {
    unsetSessionValue('synchronizationTable',true); // on change, clean cache for synchronization to refresh it
    return parent::save();
  }
  
  public function delete() {
    unsetSessionValue('synchronizationTable',true); // on change, clean cache for synchronization to refresh it
    return parent::delete();
  }
     
  /** ==========================================================================
   * Return list of fields synchronized for a given project
   *   ! list is static on first version of feature
   * @return array of field names  
   */
  public static function getSynchronizedFields($idProject) {
    // idProject not required as not needed on this version (returns a static list
    return array(
      "name",
      "idProject",
      "idStatus",
      "idResource",
      "idProduct",
      "idTargetProductVersion",
      "idComponent",  
      "idTargetComponentVersion");
  }
  
  /** ==========================================================================
   * Internal function to get synchronization data using cache
   * @return array of Synchronization objects (all) 
   */
  private static function getAllSynchronizationDefinitions() {
    if ( sessionValueExists('synchronizationTable',true)) {
      return getSessionValue('synchronizationTable',null,true);
    }
    $sync=new Synchronization();
    $syncList=$sync->getSqlElementsFromCriteria(null);
    $result=array();
    foreach($syncList as $sync) {
      $result[$sync->idProject]=$sync;
    }
    setSessionValue('synchronizationTable', $result,true);
    return $result;
  }
  
  /** ==========================================================================
   * Checks if defined project is synchronized (synchronization definition exists)
   * @return boolean True or False
   */
  public static function isProjectSynchronized($idProject) {
    if ($idProject===null or $idProject==='') return false;
    $syncTable=self::getAllSynchronizationDefinitions();
    if (isset($syncTable[$idProject])) {
      return true;
    } else {
      return false;
    }
  }
   
  /** ==========================================================================
   * Returns synchronization definition for given project (if it exists)
   * @return object Synchronization
   */
  public static function getProjectSynchronizationDefinition($idProject) {
    if ($idProject===null or $idProject==='') return null;
    $syncTable=self::getAllSynchronizationDefinitions();
    if (isset($syncTable[$idProject])) {
      return $syncTable[$idProject];
    } else {
      return null;
    }
  }
  
  /** ==========================================================================
   * Initialize the synchronization between 2 items
   * Created the sychonized item (destination) if required
   * @return Object an object (the synchronised object) or null if synchronization failed
   */
  public static function startSynchronization($obj){
    self::$_lastErrorMessage='';
    if ($obj==null) {
      debugTraceLog("Synchronization::startSynchronization() call with null object");
      self::$_lastErrorMessage="TECHNICAL ERROR - Synchronization::startSynchronization() call with null object";
      return null;
    }
    $objectClass=get_class($obj);
    if (!property_exists($obj,'idProject')) {
      debugTraceLog("Synchronization::startSynchronization() object $objectClass has no idProject");
      self::$_lastErrorMessage="TECHNICAL ERROR - Synchronization::startSynchronization() object $objectClass has no idProject";
      return null; // No idProject on item => quit
    }
    if (! self::isProjectSynchronized($obj->idProject)) {
      debugTraceLog("Synchronization::startSynchronization() Project #$obj->idProject for object $objectClass has no Synchronization definition");
      self::$_lastErrorMessage="TECHNICAL ERROR - Synchronization::startSynchronization() Project #$obj->idProject for object $objectClass has no Synchronization definition";
      return null; // No synchronization for the Project => quit
    }
    $sync=self::getProjectSynchronizationDefinition($obj->idProject);
    if ($objectClass=='TicketSimple') $objectClass='Ticket';
    if ($sync->originType!=$objectClass) {
      debugTraceLog("Synchronization::startSynchronization() Item $objectClass #$obj->id in not of Synchronized class $sync->originType");
      self::$_lastErrorMessage="TECHNICAL ERROR - Synchronization::startSynchronization() Item $objectClass #$obj->id in not of Synchronized class $sync->originType";
      return null; // Item is not of the origin class that is synchronized => quit
    }
    $synchedItem=SynchronizedItems::getSynchronizedItemObj($objectClass, $obj->id);
    if ($synchedItem!=null) { // object already synchronized
      return $synchedItem;  // return the object already qsynchronized (first idea to retrun null was not accurate)
    }
    if ($objectClass=='Ticket' and $sync->targetType=='Activity') {
      if ($obj->idActivity) { // Ticket has planning activity
        $act=new Activity($obj->idActivity);
        if (!$act->id) {
          errorLog("[1] Synchronization::startSynchronization - Ticket #$obj->id refers to unexisting Activity #$obj->idActivity");
          self::$_lastErrorMessage="TECHNICAL ERROR - Synchronization::startSynchronization - Ticket #$obj->id refers to unexisting Activity #$obj->idActivity";
          return null;
        }
        // Count tickets also attached to the Planning Activity 
        $tkt=new Ticket();
        $crit="idActivity=$obj->idActivity and id<>$obj->id";
        $cptTicketsAlsoLinkedToActivity=$tkt->countSqlElementsFromCriteria(null,$crit);
        // Get item already synchronized with this activitiy
        $itemAlreadySynchonizedWithActivity=SynchronizedItems::getSynchronizedItemKey('Activity',$act->id);
        // Look for origin of activity
        $origin=SqlElement::getSingleSqlElementFromCriteria('Origin', array('refType'=>'Activity','refId'=>$act->id));
        $hasDifferentOrigin=false;
        if ($origin and $origin->id and ($origin->originType!=$objectClass or $origin->originId!=$obj->id)) $hasDifferentOrigin=true;
        if ($act->idle==0 and $cptTicketsAlsoLinkedToActivity==0 and $itemAlreadySynchonizedWithActivity==null and $hasDifferentOrigin==false) { // Activity not linked to other ticket, can be synchronized 
          $result=$sync->storeSynchronizedItems($obj,$act);
          if ($result=='OK') {
            return $act;
          } else {
            return null; // Failed to synchronise
          }          
        } else { // Ticket is already linked to activity that cannot be synchronized with it (linked to several tickets or closed or already synchronized) 
          debugTraceLog("[4] Synchronization::startSynchronization - $objectClass #$obj->id is already linked to activity that cannot be synchronized with it (linked to several tickets or closed or already synchronized)");
          self::$_lastErrorMessage=i18n("synchronizationFailedActivityNotSynchronizable");
          return null;  
        }
      } else { // Ticket does not have planning Activity
        $origin=new Origin();
        $originList=$origin->getSqlElementsFromCriteria(array('refType'=>'Activity','originType'=>$objectClass,'originId'=>$obj->id));
        if (count($originList)==1) { // Ticket is origin of one single Activity
          $orig=reset($originList);
          $act=new Activity($orig->refId);
          // Get item already synchronized with this activitiy
          $itemAlreadySynchonizedWithActivity=SynchronizedItems::getSynchronizedItemKey('Activity',$act->id);
          // Count tickets also attached to the Origin Activity
          $tkt=new Ticket();
          $crit="idActivity=$act->id and id<>$obj->id";
          $cptTicketsAlsoLinkedToActivity=$tkt->countSqlElementsFromCriteria(null,$crit);
          if ( $act->idle==0 and $cptTicketsAlsoLinkedToActivity==0 and $itemAlreadySynchonizedWithActivity==null) { // The activity that has ticket as Origin can be linked to it 
            $result=$sync->storeSynchronizedItems($obj,$act);
            if ($result=='OK') {
              return $act;
            } else {
              return null; // Failed to synchronise
            }
          } else { // The activity that has ticket as Origin cannot be linked to it
            $act=$sync->createSynchronizedItem($obj);
            if ($act and $act->id) {
              $result=$sync->storeSynchronizedItems($obj, $act);
              if ($result=='OK') {
                return $act;
              } else {
                return null; // Failed to synchronise
              }
            } else {  
              return null;
            }
          }       
        } else { // Ticket is origin of no or more than one Activity
          $act=$sync->createSynchronizedItem($obj);
          if ($act and $act->id) {
            $result=$sync->storeSynchronizedItems($obj,$act);
            if ($result=='OK') {
              return $act;
            } else {
              return null; // Failed to synchronise
            }
          } else {
            return null;
          }  
        }
      }
    }
  }
  
  private function createSynchronizedItem($obj){    
    self::$_createSyncItemInProgress=true; // To force creation of assigned resource on activity
    $result=$obj->copyTo(
        $this->targetType,     // class 
        $this->idTargetType,   // type
        $obj->name,            // name
        $obj->idProject,       // project
        true,                  // setOrigin 
        true,                  // withNotes 
        true,                  // withAttachments 
        true,                  // withLinks
        false,                 // withAssignments
        false,                 // withAffectations
        null,                  // toProject (for move)
        null,                  // toActivity (for move)
        false,                 // copyToWithResult
        false,                  // copyToWithVersionProjects
        false                  // copyToWithStatus
    );
    self::$_createSyncItemInProgress=false;
    if (getLastOperationStatus($result->_copyResult)=='OK') {
      return $result; // REturn the copied object (synchronized item)
    } else {
      debugTraceLog("TECHNICAL ERROR - Synchronization::createSynchronizedItem() - Error copying ".get_class($obj)."#$obj->id to $this->targetType");
      debugTraceLog($result->_copyResult);
      self::$_lastErrorMessage=i18n("synchronizationError",array(i18n($this->targetType))) ."<br/><br/>$result->_copyResult";
      return null;
    }
  }
  
  private function storeSynchronizedItems($source,$target) {
    self::$_lastErrorMessage='';
    $ref1Type=get_class($source);
    $ref1Id=$source->id;
    $ref2Type=get_class($target);
    $ref2Id=$target->id;
    // TODO : verify unicity 
    $syncItems=new SynchronizedItems();
    $syncItems->idSynchronization=$this->id;
    if ($ref1Type<$ref2Type or ($ref1Type==$ref2Type and $ref1Id<$ref2Id)) {
      $syncItems->ref1Type=$ref1Type;
      $syncItems->ref1Id=$ref1Id;
      $syncItems->ref2Type=$ref2Type;
      $syncItems->ref2Id=$ref2Id;
    } else {
      $syncItems->ref1Type=$ref2Type;
      $syncItems->ref1Id=$ref2Id;
      $syncItems->ref2Type=$ref1Type;
      $syncItems->ref2Id=$ref1Id;
    }
    $crit= "(ref1Type='$ref1Type' and ref1Id=$ref1Id) or (ref1Type='$ref2Type' and ref1Id=$ref2Id)";
    $crit.=" or (ref2Type='$ref1Type' and ref2Id=$ref1Id) or (ref2Type='$ref2Type' and ref2Id=$ref2Id)";
    $existsSynchItems=$syncItems->getSqlElementsFromCriteria(null,null,$crit);
    if (count($existsSynchItems)>0) {
      errorLog("Synchronization::storeSynchronizedItems($ref1Type,$ref1Id,$ref2Type,$ref2Id)");
      errorLog("  Already existing synchronized items");
      foreach ($existsSynchItems as $si) {
        errorLog("    => $si->ref1Type #$si->ref1Id | $si->ref2Type #$si->ref2Id");
      }
      self::$_lastErrorMessage="TECHNICAL ERROR - Synchronization::storeSynchronizedItems($ref1Type #$ref1Id, $ref2Type #$ref2Id) - Already existing synchronized items";
      return 'KO';
    }
    $result=$syncItems->save();
    if (getLastOperationStatus($result)=='OK') {
      $resultOrigin=$this->storeOrigin(get_class($source), $source->id, get_class($target), $target->id);
      if ($resultOrigin!='OK') {return 'KO';}
      $resultLink=$this->storeLink($syncItems->ref1Type,$syncItems->ref1Id,$syncItems->ref2Type,$syncItems->ref2Id,$syncItems->id);
      if ($resultLink!='OK') {return 'KO';}
      $resultStatus=$this->synchronizeStatus($source, $target);
      if ($resultStatus!='OK' ) {return 'KO';}
      if ($this->setActivity==1) {
        $tkt=new Ticket($syncItems->ref2Id);
        if ($tkt->id and !$tkt->idActivity) {
          $tkt->idActivity=$syncItems->ref1Id;
          $resultTkt=$tkt->save();
          if (getLastOperationStatus($resultTkt)!='OK') {
            debugTraceLog("FUNCTINAL ERROR - Synchronization::storeSynchronizedItems($ref1Type #$ref1Id, $ref2Type #$ref2Id) - Could not set idActivity on ticket");
            debugTraceLog($resultStatus);
            self::$_lastErrorMessage=i18n("synchronizationFailed")."<br/> $resultStatus";
            return 'KO';
          }
        }
      }
      return 'OK';
    } else {
      self::$_lastErrorMessage=$result;
      return 'KO';
    }
  }
  private function storeOrigin($originType,$originId,$refType,$refId) {
    $orig=SqlElement::getSingleSqlElementFromCriteria('Origin', array('originType'=>$originType,'originId'=>$originId,'refType'=>$refType,'refId'=>$refId));
    if (!$orig->id) {
      $resultOrigin=$orig->save();
      if (getLastOperationStatus($resultOrigin)!='OK') {
        debugTraceLog("TECHNICAL ERROR - Synchronization::storeOrigin($originType, $originId, $refType, $refId, ) - Could not save Origin");
        debugTraceLog($resultOrigin);
        self::$_lastErrorMessage=i18n("synchronizationFailedSaveOrigin")."<br/>$resultOrigin";
        return "KO";
      } else {
        return "OK";
      }
    } else {
      // Origine already exist : OK
      return "OK";
    }
  }
  private function storeLink($ref1Type,$ref1Id,$ref2Type,$ref2Id, $idSynchronizeditems) {
    if ($ref1Type<$ref2Type or ($ref1Type==$ref2Type and $ref1Id<$ref2Id)) {
     // OK Correct Order
    } else {
      $tempRef=$ref1Type;
      $tempId=$ref1Id;
      $sref1Type=$ref2Type;
      $ref1Id=$ref2Id;
      $ref2Type=$tempRef;
      $ref2Id=$tempId;
    }
    $link=SqlElement::getSingleSqlElementFromCriteria('Link',array('ref1Type'=>$ref1Type, 'ref1Id'=>$ref1Id, 'ref2Type'=>$ref2Type, 'ref2Id'=>$ref2Id));
    if (!$link->id) {
      $link->idSynchronizationItem = $idSynchronizeditems;
      $resultLink=$link->save();
      if (getLastOperationStatus($resultLink)!='OK') {
        debugTraceLog("TECHNICAL ERROR - Synchronization::storeLink($ref1Type #$ref1Id, $ref2Type #$ref2Id) - Could not save Link");
        debugTraceLog($resultLink);
        self::$_lastErrorMessage=i18n("synchronizationFailedSaveLink")."<br/>$resultLink";
        return 'KO';
      } else {
        return 'OK';
      }
    }
    else return "OK";
  }
  
  private function synchronizeStatus($source, $target) {
    global $createSynchronizationDefiniton;
    if (! property_exists($source, 'idStatus') or ! property_exists($target, 'idStatus')) return 'OK';
    SqlElement::$_skipWorkflowControl=true;
    $statT=new Status($target->idStatus);
    $statS=new Status($source->idStatus);
    if (isset($createSynchronizationDefiniton) and $createSynchronizationDefiniton===true 
    and  $statT->idle==0 and $statT->isCopyStatus==0 and $statT->sortOrder>$statS->sortOrder) { // When creating sync definition, set both items to highest status (not to 
      $source->idStatus=$target->idStatus;
      self::setRequiredValues($target,$source);
      $resultStatus=$source->save();
    } else {
      $target->idStatus=$source->idStatus;
      self::setRequiredValues($source,$target);
      $resultStatus=$target->save();
    }
    SqlElement::$_skipWorkflowControl=false;
    if (getLastOperationStatus($resultStatus)=='OK' or getLastOperationStatus($resultStatus)=='NO_CHANGE') {
      return 'OK';
    } else {
      debugTraceLog("FUNCTIONAL ERROR - Synchronization::synchronizeStatus() - Could not move ".get_class($target)." #$target->id to status '".SqlList::getNameFromId('Status',$target->idStatus)."'");
      debugTraceLog($resultStatus);
      self::$_lastErrorMessage=i18n("synchronizationFailedSyncStatus")."<br/>$resultStatus";
      return 'KO';
    }
  }
  public static function setRequiredValues($source,$target) {
    $target->setAttributes();
    $fldType=$target->getObjectTypeName();
    $extraRequiredFields=$target->getExtraRequiredFields(null,$source->idStatus,$target->$fldType);
    foreach ($target as $fld=>$val) {
      if (! $val and ($target->isAttributeSetToField($fld,'required') or isset($extraRequiredFields[$fld]) ) ) {
        if (property_exists($source, $fld)) {
          $target->$fld=$source->$fld;
        }
        if ($fld=='description' and ! $target->$fld) {
          $target->$fld=$source->name;
        }
      }
    }
  } 
  
  public static function synchronizeFields($source, $oldSource) {
    if (self::$_synchInProgress==true) return;
    self::$_synchInProgress=true;
    $fields=self::getSynchronizedFields($oldSource->idProject); // In initial version idProject does not matter, list is fix
    $syncItem=SynchronizedItems::getSynchronizedItemObj(get_class($source),$source->id);
    if (! $syncItem or ! $syncItem->id) {
      //errorLog("synchronizeFields::synchronizeFields - Cannot retreive synchronized item for ".get_class($source)." #".$source->id);
      // Item not synchronized... 
      self::$_synchInProgress=false;
      return null;
    }
    if (method_exists($syncItem, 'setAttributes')) $syncItem->setAttributes();
    $fldType=$syncItem->getObjectTypeName();
    $extraRequiredFields=$syncItem->getExtraRequiredFields(null,$source->idStatus,$syncItem->$fldType);
    $changed=false;
    foreach ($syncItem as $fld=>$val) {
      if (pq_substr($fld,0,1)=='_') continue;
      if (property_exists($source, $fld) and property_exists($syncItem, $fld)) {
        if (in_array($fld,$fields) and $source->$fld!=$oldSource->$fld) {
          // Value has changed in source
          $syncItem->$fld=$source->$fld;
          $changed=true;
        } else if (! $syncItem->$fld and $source->$fld and ($syncItem->isAttributeSetToField($fld,'required') or isset($extraRequiredFields[$fld]) ) ) {
          // Value has not changed in source but is set and not set in target and required in target
          $syncItem->$fld=$source->$fld;
          $changed=true;
        }
      }  
    }
    if ($changed) {
      SqlElement::$_skipWorkflowControl=true;
      SqlElement::$_skipProjectControl=true;
      $result=$syncItem->save();
      //SqlElement::$_skipWorkflowControl=false;
      //SqlElement::$_skipProjectControl=false;
      if (getLastOperationStatus($result)!='OK' and getLastOperationStatus($result)!='NO_CHANGE') {
        $result=i18n("synchronizationError",array(i18n(get_class($syncItem)).' #'.$syncItem->id)) ."<br/><br/>".$result;
      }
      self::$_synchInProgress=false;
      return $result;
    } else {
      self::$_synchInProgress=false;
      return '<input type="hidden" id="lastOperationStatus" value="NO_CHANGE" />';
    }
    self::$_synchInProgress=false;
  }

  public static function getLastErrorMessage() {
    return self::$_lastErrorMessage;
  }
  public static function getLastResult() {
    if (self::getLastErrorMessage()=='') return 'OK';
    else return 'ERROR';
  }
}
?>
