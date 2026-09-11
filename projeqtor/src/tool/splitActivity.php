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

/** ===========================================================================
 * Save a note : call corresponding method in SqlElement Class
 * The new values are fetched in $_REQUEST
 */
require_once "../tool/projeqtor.php";

$objectId = RequestHandler::getId('objectId');
$objectClass = RequestHandler::getClass('objectClass');
$toClassName=$objectClass;

$obj=new $objectClass($objectId);
$type = "id".SqlElement::getTypeClassName($objectClass);
$toType = $obj->$type;
$toName = $obj->name;
$toProject = $obj->idProject;

$idPlanningElementOrigin = null;
$planningElementClass = get_class($obj).'PlanningElement';
if (property_exists(get_class($obj), $planningElementClass)) {
  $idPlanningElementOrigin = $obj->$planningElementClass->id;
}
$copyToOrigin=false;
$copyToWithNotes=true;
$copyToWithAttachments=true;
$copyToWithLinks=true;
$copyAssignments=true;
$copyToWithResult=true;
$copyToWithStatus=true;
$moveAfterCreate=$idPlanningElementOrigin;
$copyToWithDependency=true;
$copyWithStructure=true;
$copyToWithSubTask=true;

Sql::beginTransaction();
PlanningElement::$_noDispatch=true;
SqlElement::$_doNotSaveLastUpdateDateTime=true;
$error=false;
$activityWorkUnit = new ActivityWorkUnit();
$actWorkUnitList = $activityWorkUnit->getSqlElementsFromCriteria(array('refType'=>$objectClass, 'refId'=>$objectId));
if(count($actWorkUnitList) > 0){
  $resultValue = '<b>' . i18n ( 'cantSplitActivityWorkUnit' ) . '</b><br/>';
  $resultValue .= '<input type="hidden" id="lastOperationStatus" value="INVALID" />';
  $resultValue .= '<input type="hidden" id="lastSaveId" value="' . htmlEncode ( $objectId ) . '" />';
  $resultValue .= '<input type="hidden" id="lastOperation" value="control" />';
  $result = '<div class="messageINVALID" >'.$resultValue.'</div>';
  echo $result;
  return;
}

$newObj=$obj->copyTo($toClassName,$toType, $toName, $toProject, $copyToOrigin, $copyToWithNotes, $copyToWithAttachments,$copyToWithLinks, $copyAssignments,false,null,null,$copyToWithResult, false, $copyToWithStatus, $copyToWithSubTask, $moveAfterCreate, $copyToWithDependency, false, true);

$result=$newObj->_copyResult;
if (! pq_stripos($result,'id="lastOperationStatus" value="OK"')>0 ) {
  $error=true;
}
unset($newObj->_copyResult);
if (!$error and $copyWithStructure) {
  $res=PlanningElement::copyStructure($obj, $newObj, false, $copyToWithNotes, $copyToWithAttachments,$copyToWithLinks, $copyAssignments, null, $toProject, false, $copyWithStructure, false, $copyToWithStatus);
  if ($res!='OK') {
    $error=true;
    $result=$res;
  } else {
    PlanningElement::copyStructureFinalize();
  }
}
if (!$error and ($copyWithStructure or $copyAssignments)) {
  PlanningElement::copyStructureFinalize();
}

// Message of correct saving
$status = displayLastOperationStatus($result);

if ($status == "OK") {
  //Delete current dependency replace by copy
  $dep = new Dependency();
  $where = "predecessorRefType = '$objectClass' and predecessorRefId = $obj->id and successorRefId != $newObj->id";
  $depList = $dep->getSqlElementsFromCriteria(null, null, $where);
  foreach ($depList as $dependency){
    $dependency->delete();
  }
  
  // Divide Duration
  $pe = $objectClass.'PlanningElement';
  $firstValidatedDuration = intdiv(pq_nvl($obj->$pe->validatedDuration, 1), 2) + fmod(pq_nvl($obj->$pe->validatedDuration, 1), 2);
  $secondValidatedDuration = intdiv(pq_nvl($obj->$pe->validatedDuration, 1), 2);
  $obj->$pe->validatedDuration = $firstValidatedDuration;
  $obj->save();
  $newObj->$pe->validatedDuration = $secondValidatedDuration;
  $newObj->save();
  
  // Divide Work
  $firstValidatedWork = intdiv(pq_nvl($obj->$pe->validatedWork, 1), 2) + fmod(pq_nvl($obj->$pe->validatedWork, 1), 2);
  $secondValidatedWork = intdiv(pq_nvl($obj->$pe->validatedWork, 1), 2);
  $obj->$pe->validatedWork = $firstValidatedWork;
  $obj->save();
  $newObj->$pe->validatedWork = $secondValidatedWork;
  $newObj->save();
  
  // Divide Assignment
  $ass = new Assignment();
  $crit = array('refType' => $objectClass, 'refId' => $obj->id);
  $lstAss = $ass->getSqlElementsFromCriteria ( $crit );
  foreach ( $lstAss as $ass ) {
    $divAssignedWork = intdiv(pq_nvl($ass->assignedWork, 1), 2) + fmod(pq_nvl($ass->assignedWork, 1), 2);
    $ass->assignedWork = $divAssignedWork;
    $ass->save();
    $divLeftWork = intdiv(pq_nvl($ass->leftWork, 1), 2) + fmod(pq_nvl($ass->leftWork, 1), 2);
    $ass->leftWork = $divLeftWork;
    $ass->save();
  }
  $ass = new Assignment();
  $crit = array('refType' => $objectClass, 'refId' => $newObj->id);
  $lstAss = $ass->getSqlElementsFromCriteria ( $crit );
  foreach ( $lstAss as $ass ) {
    $divAssignedWork = intdiv(pq_nvl($ass->assignedWork, 1), 2);
    $ass->assignedWork = $divAssignedWork;
    $ass->save();
    $divLeftWork = intdiv(pq_nvl($ass->leftWork, 1), 2);
    $ass->leftWork = $divLeftWork;
    $ass->save();
  }
}

?>