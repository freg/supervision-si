<?php
/*** COPYRIGHT NOTICE *********************************************************
 *
 ******************************************************************************
 *** WARNING *** T H I S    F I L E    I S    N O T    O P E N    S O U R C E *
 ******************************************************************************
 *
 * Copyright 2015 ProjeQtOr - Pascal BERNARD - support@projeqtor.org
 *
 * This file is an add-on to ProjeQtOr, packaged as a plug-in module.
 * It is NOT distributed under an open source license.
 * It is distributed in a proprietary mode, only to the customer who bought
 * corresponding licence.
 * The company ProjeQtOr remains owner of all add-ons it delivers.
 * Any change to an add-ons without the explicit agreement of the company
 * ProjeQtOr is prohibited.
 * The diffusion (or any kind if distribution) of an add-on is prohibited.
 * Violators will be prosecuted.
 *
 *** DO NOT REMOVE THIS NOTICE ************************************************/

/* ============================================================================
 * Habilitation defines right to the application for a menu and a profile.
 */
require_once "../tool/projeqtor.php";
require_once "../tool/formatter.php";

$columnType = RequestHandler::getValue('columnType');
$itemID = RequestHandler::getValue('itemID');
$oldColumn = RequestHandler::getValue('oldColumn');
$newColumn = RequestHandler::getValue('newColumn');
$forceWorkflow = RequestHandler::getValue('forceWorkflow');

$objectClass = RequestHandler::getClass('objectClass');
$objectId = RequestHandler::getId('objectId');

$object=new $objectClass($objectId);
$nameVar='id'.$objectClass.'Type';
$nameVar2=$objectClass.'Type';
$objectType=new $nameVar2($object->$nameVar);

$reponse="";
$user=getSessionUser();
$prof=$user->getProfile($object);

if (pq_array_key_exists('backlogResourceList',$_REQUEST)) {
  $object->idResource=$_REQUEST['backlogResourceList'];
}
if (pq_array_key_exists('backlogResult',$_REQUEST)) {
  $object->result=$_REQUEST['backlogResult'];
}
if (pq_array_key_exists('backlogDescription',$_REQUEST)) {
  $object->description=$_REQUEST['backlogDescription'];
}

if($columnType == 'Status'){
  $extraRequiredFields = $object->getExtraRequiredFields($objectType->id, $newColumn, null, null, $prof);
}else{
  $extraRequiredFields = $object->getExtraRequiredFields($objectType->id, null, null, null, $prof);
}
foreach ($extraRequiredFields as $field){
  $fld = pq_trim($field);
  if(isset($_REQUEST[$fld])){
    $elementName = '';
    if(property_exists($object,$objectClass.'PlanningElement')){
      $elementName = $objectClass.'PlanningElement';
    }elseif (property_exists($object,'WorkElement')){
      $elementName = 'WorkElement';
    }
    $val = RequestHandler::getValue($fld);
    if(pq_strpos($fld, 'Work'))$val = Work::convertWork($val);
    if(property_exists($object, $fld)){
      $object->$fld = $val;
    }else if(property_exists($object->$elementName, $fld)){
      $object->$elementName->$fld = $val;
    }
  }
}

if($columnType=="Status"){
  $status=new Status($newColumn);
  $requiredList = $object->getExtraRequiredFields(null, $newColumn);
  $fieldArray = $object->getFieldsArray();
  foreach ($fieldArray as $fieldName){
    if($object->getFieldAttributes($fieldName) == 'required'){
      $requiredList[$fieldName] = 'required';
    }
  }
  $elementName = '';
  if(property_exists($object,get_class($object).'PlanningElement')){
    $planningElement = $objectClass.'PlanningElement';
    $elementName = $planningElement;
    $plgElmt = new $planningElement();
    $elmtRequired = $plgElmt->getExtraRequiredFields(null, $newColumn);
    $requiredList = array_merge($requiredList, $elmtRequired);
  }elseif (property_exists($object,'WorkElement')){
    $elementName = 'WorkElement';
    $wrkElmt = new WorkElement();
    $elmtRequired = $wrkElmt->getExtraRequiredFields(null, $newColumn);
    $requiredList = array_merge($requiredList, $elmtRequired);
  }
  if($objectType->mandatoryResourceOnHandled && $status->setHandledStatus && !$object->idResource){
    $reponse.="&needRessource=true";
  }
  if($objectType->mandatoryResultOnDone && $status->setDoneStatus && !$object->result){
    $reponse.="&needResult=true";
  }
  if($objectType->mandatoryDescription && !$object->description){
    $reponse.="&needDescription=true";
  }
  if(count($requiredList) > 0){
    $requiredFields = array();
    foreach ($requiredList as $field=>$att){
      $item = pq_trim($field);
      if(($item != 'result' or $item != 'idResource')){
        $hasOnObject = property_exists($object, $item);
        $hasOnElement = ($elementName and property_exists($object->$elementName, $item));
        $filledOnObject = $hasOnObject and (pq_trim($object->$item) !== '' and $object->$item !== 0 and $object->$item !== null);
        $filledOnElement = $hasOnElement and ($object->$elementName->$item and $object->$elementName->$item != 0);
        if($filledOnObject or $filledOnElement){
          continue;
        }
        if($hasOnObject or $hasOnElement){
          $requiredFields[$item] = $item;
        }else{
          continue;
        }
      }
    }
    if(isset($requiredFields['idResource']))unset($requiredFields['idResource']);
    if(isset($requiredFields['result']))unset($requiredFields['result']);
    if(isset($requiredFields['description']))unset($requiredFields['description']);
    if(count($requiredFields)>0){
      $requiredFields = implode(',', $requiredFields);
      $reponse.="&extraRequiredFields=".$requiredFields;
    }
  }
}

if($reponse==""){
  $newV='id'.$columnType;
  if($newColumn!='0'){
      $object->$newV=$newColumn;
      if($columnType == 'Status'){
        $st = new Status($newColumn);
        if ($st->setHandledStatus and property_exists($object,'handled') and property_exists($object,'handledDate')) {
          $object->handled=1;
          $object->handledDate=date('Y-m-d');
        }else if(!$st->setHandledStatus and property_exists($object,'handled') and property_exists($object,'handledDate')){
          $object->handled=0;
          $object->handledDate=null;
        }
        if ($st->setDoneStatus and property_exists($object,'done') and property_exists($object,'doneDate')) {
          $object->done=1;
          $object->doneDate=date('Y-m-d');
        }else if (!$st->setDoneStatus and property_exists($object,'done') and property_exists($object,'doneDate')){
          $object->done=0;
          $object->doneDate=null;
        }
        if ($st->setIdleStatus and property_exists($object,'idle') and property_exists($object,'idleDate')) {
          $object->idle=1;
          $object->idleDate=date('Y-m-d');
        }else if (!$st->setIdleStatus and property_exists($object,'idle') and property_exists($object,'idleDate')) {
          $object->idle=0;
          $object->idleDate=null;
        }
        if ($st->setCancelledStatus and property_exists($object,'cancelled') ) {
          $object->cancelled=1;
        }else if (!$st->setCancelledStatus and property_exists($object,'cancelled') ) {
          $object->cancelled=0;
        }
      }
    }else{
      $object->$newV=null;
    }
    $needGlobalRefresh = false;
    $beforeOldSprintIdStatus = $oldColumn;
    $beforeNewSprintIdStatus = $newColumn;
    $afterOldSprintIdStatus = $oldColumn;
    $afterNewSprintIdStatus = $newColumn;
    if($columnType == 'Sprint'){
      if($oldColumn!='0'){
        $oldSprint = new Sprint($oldColumn);
        $beforeOldSprintIdStatus = $oldSprint->idStatus;
      }
      if($newColumn!='0'){
        $newSprint = new Sprint($newColumn);
        $beforeNewSprintIdStatus = $newSprint->idStatus;
      }
    }
    if($forceWorkflow){
      $previousSkipAllControls = SqlElement::$_skipAllControls;
      SqlElement::$_skipAllControls = true;
      $result=$object->save();
      SqlElement::$_skipAllControls = $previousSkipAllControls;
    }else{
      $result=$object->save();
    }
    if($columnType == 'Sprint'){
      if($oldColumn!='0'){
        $oldSprint = new Sprint($oldColumn);
        $afterOldSprintIdStatus = $oldSprint->idStatus;
      }
      if($newColumn!='0'){
        $newSprint = new Sprint($newColumn);
        $afterNewSprintIdStatus = $newSprint->idStatus;
      }
      if(($beforeOldSprintIdStatus != $afterOldSprintIdStatus) or ($beforeNewSprintIdStatus != $afterNewSprintIdStatus))$needGlobalRefresh=true;
    }
    $resultOk=getLastOperationStatus($result);
    if($resultOk!="OK"){
      echo 'messageError/split/'.getLastOperationMessage($result);
    }else if($needGlobalRefresh){
      echo 'needGlobalRefresh';
    }
}else{
  echo $reponse.'&objectClass='.$objectClass.'&objectId='.$objectId.'&itemID='.$itemID.'&newColumn='.$newColumn.'&oldColumn='.$oldColumn.'&columnType='.$columnType.($forceWorkflow?'&forceWorkflow=1':'');
}
?>