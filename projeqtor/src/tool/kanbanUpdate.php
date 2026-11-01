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
require_once "../tool//kanbanConstructPrinc.php";

$columnType = RequestHandler::getValue('columnType');
$itemID = RequestHandler::getValue('itemID');
$oldColumn = RequestHandler::getValue('oldColumn');
$newColumn = RequestHandler::getValue('newColumn');
$idKanban = RequestHandler::getId('idKanban');
$objectClass = RequestHandler::getClass('objectClass');
$objectId = RequestHandler::getId('objectId');
$forceWorkflow = RequestHandler::getValue('forceWorkflow');

$object=new $objectClass($objectId);
$nameVar='id'.$objectClass.'Type';
$nameVar2=$objectClass.'Type';
$objectType=new $nameVar2($object->$nameVar);
$kanban = new Kanban($idKanban);
$json = json_decode($kanban->param,true);
$user=getSessionUser();
$prof=$user->getProfile($object);

$reponse="";

if (pq_array_key_exists('kanbanResourceList',$_REQUEST)) {
  $object->idResource=$_REQUEST['kanbanResourceList'];
}
if (pq_array_key_exists('kanbanResult',$_REQUEST)) {
  $object->result=$_REQUEST['kanbanResult'];
}
if (pq_array_key_exists('kanbanDescription',$_REQUEST)) {
  $object->description=$_REQUEST['kanbanDescription'];
}
if (pq_array_key_exists('kanbanResolutionList',$_REQUEST)) {
  $object->idResolution=$_REQUEST['kanbanResolutionList'];
}
// if($columnType == 'Status'){
//   $extraRequiredFields = $object->getExtraRequiredFields($objectType->id, $newColumn, null, null, $prof);
// }else{
//   $extraRequiredFields = $object->getExtraRequiredFields($objectType->id, null, null, null, $prof);
// }

$extraRequiredFields = RequestHandler::getValue('extraRequiredFields');
$extraRequiredFields = pq_explode(',', pq_nvl($extraRequiredFields));

foreach ($extraRequiredFields as $field){
  $fld = pq_trim($field);
  if(isset($_REQUEST[$fld])){
    $elementName = '';
	  if(property_exists($object,get_class($object).'PlanningElement')){
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
	if(!$forceWorkflow){
		// PBE : status is not always the first of column, but can be one avalable in the column
		$statusList=SqlList::getList('Status');
		$targetStatus=array();
		$json['column']=array_merge($json['column'],array()); // will "fill holes" in keys : 0, 1, 3, 5 will become 0, 1, 2, 3
		for ($i=0;$i<count($json['column']);$i++) {
		  $itemKanban=$json['column'][$i];
		  $idFrom=$itemKanban['from'];
		  if ($idFrom==$newColumn) {
	  	  $targetStatus[$idFrom]=$idFrom;
	  	  $found=false;
	  	  foreach ($statusList as $idS=>$nameS) {
	  	    if ($found) {
	  	      if ($i<count($json['column'])-1 and $idS==$json['column'][$i+1]['from']) {
	  	        break;
	  	      } else {
	  	        $targetStatus[$idS]=$idS;
	  	      }
	  	    } else if ($idS==$idFrom) {
	  	      $found=true;
	  	    }
	  	  }
		  }
		}
		$workflowId=$objectType->idWorkflow;
		$wf=new Workflow($workflowId);
		$mapWorkflow=$wf->getWorkflowstatusArray();
		$user=getSessionUser();
		$prof=$user->getProfile($object);
		foreach ($targetStatus as $testStatus) {
		  if (isset($mapWorkflow[$object->idStatus][$testStatus])
		  and isset($mapWorkflow[$object->idStatus][$testStatus][$prof])
		  and $mapWorkflow[$object->idStatus][$testStatus][$prof]==1) {
		    $newColumn=$testStatus;
		    break;
		  }
		}
		// PBE - End
	}
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
  if($objectType->mandatoryResolutionOnDone && $status->setDoneStatus && !$object->idResolution){
    $reponse.="&needResolution=true";
  }
  if(count($requiredList) > 0){
    $requiredFields = array();
    foreach ($requiredList as $field=>$att){
      $item = pq_trim($field);
      if(($item != 'result' or $item != 'idResource')){
        if(property_exists($object, $item) and (pq_trim($object->$item) == '' or $object->$item === 0)){
        	$requiredFields[$item] = $item;
        }else if($elementName and property_exists($object->$elementName, $item) and (!$object->$elementName->$item or $object->$elementName->$item == 0)){
            $requiredFields[$item] = $item;
        }else{
          continue;
        }
      }
    }
    if(isset($requiredFields['idResource']))unset($requiredFields['idResource']);
    if(isset($requiredFields['result']))unset($requiredFields['result']);
    if(count($requiredFields)>0){
      $requiredFields = implode(',', $requiredFields);
      $reponse.="&extraRequiredFields=".$requiredFields;
    }
  }
}

if($reponse==""){
  $newV='id'.$columnType;
  if($newColumn!='n' and $newColumn!='0'){
    $object->$newV=$newColumn;
  }else{
    $object->$newV=null;
  }
  if($forceWorkflow){
    // Bypass all controls (required fields, workflow, etc.) when forcing column assignment
    $previousSkipAllControls = SqlElement::$_skipAllControls;
    SqlElement::$_skipAllControls = true;
    $result=$object->save();
    SqlElement::$_skipAllControls = $previousSkipAllControls;
  }else{
    $result=$object->save();
  }
  $resultOk=getLastOperationStatus($result);
  if($resultOk != "OK"){
    echo 'messageError/split/'.getLastOperationMessage($result);
  }
}else{
  echo $reponse.'&objectClass='.$objectClass.'&objectId='.$objectId.'&itemID='.$itemID.'&newColumn='.$newColumn.'&oldColumn='.$oldColumn.'&columnType='.$columnType.($forceWorkflow?'&forceWorkflow=1':'');
}
?>