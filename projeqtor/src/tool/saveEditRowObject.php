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

/**
 * ===========================================================================
 * Save the current object : call corresponding method in SqlElement Class
 * The new values are fetched in $_REQUEST
 * The old values are fetched in $currentObject of SESSION
 * Only changed values are saved.
 * This way, 2 users updating the same object don't mess.
 */
require_once "../tool/projeqtor.php";

// Get the object class from request
$className = RequestHandler::getClass('objectClassName');
$objectId = RequestHandler::getId('objectIdRow');

$obj = new $className($objectId);
$needProjectListRefresh=false;
$idCalendarForCalendarRefresh=false;
$currentFormFields = array();
$currentFormFields['objectClassName']=$className;
$currentFormFields['objectId']=$objectId;

$editableFields = RequestHandler::getValue('editableFields');
$editableFields = explode(',', $editableFields);
$editableFields = array_flip($editableFields);

$extraRequiredFields=array();

if (pq_array_key_exists ( 'confirmed', $_REQUEST )) {
  if ($_REQUEST ['confirmed'] == 'true') {
    SqlElement::setSaveConfirmed ();
  }
}

$result ="";
$resultSave="";
$predstatus="";
$succstatus="";
$changePeValue=false;
$updatedNonePeField=array();
Sql::beginTransaction ();
SqlElement::unsetCurrentObject(); // PBER #11821
// get the modifications (from request)
foreach ($_REQUEST as $field=>$value){
  if(($field == 'name' and $obj->name!=$value) or ($field == 'idProject' and $obj->idProject!=$value))$needProjectListRefresh=true;
  if($field == 'idCalendarDefinition' and $obj->idCalendarDefinition!=$value)$idCalendarForCalendarRefresh=true;
  if(SqlElement::class_exists($className.'PlanningElement') and property_exists($className.'PlanningElement', 'id'.$className.pq_substr(ucfirst($field), 2))){
    $col = 'id'.$className.pq_substr(ucfirst($field), 2);
    $pe = $className.'PlanningElement';
    if(pq_trim($value) == ''){
      if($obj->$pe->getDataType($col) == 'int'){
        $value = intval($value);
      }else if($obj->$pe->getDataType($col) == 'decimal'){
        $value = floatval($value);
      }
    }
    if ($obj->$pe->$col!=$value and $col!='refName') $changePeValue=true;
    if($obj->$pe->$col!=$value)$updatedNonePeField[] = ucfirst($field);
    $obj->$pe->$col = $value;
    $currentFormFields[$col]=$value;
  }else if(SqlElement::class_exists($className.'PlanningElement') and property_exists($className.'PlanningElement', 'id'.$className.ucfirst($field))){
    $col = 'id'.$className.ucfirst($field);
    $pe = $className.'PlanningElement';
    if(pq_trim($value) == ''){
      if($obj->$pe->getDataType($col) == 'int'){
        $value = intval($value);
      }else if($obj->$pe->getDataType($col) == 'decimal'){
        $value = floatval($value);
      }
    }
    if ($obj->$pe->$col!=$value) $changePeValue=true;
    if($obj->$pe->$col!=$value)$updatedNonePeField[] = ucfirst($field);
    $obj->$pe->$col = $value;
    $currentFormFields[$col] = $value;
  }else if(SqlElement::class_exists($className.'PlanningElement') and property_exists($className.'PlanningElement', $field)){
    if ($className=='PeriodicMeeting') $pe='MeetingPlanningElement';
    else $pe = $className.'PlanningElement';
    if(pq_trim($value) == ''){
      if($obj->$pe->getDataType($field) == 'int'){
        $value = intval($value);
      }else if($obj->$pe->getDataType($field) == 'decimal'){
        $value = floatval($value);
      }
    }
    $objValue = $obj->$pe->$field;
    if($obj->$pe->getDataType($field) == 'int'){
      $objValue = ($obj->$pe->$field != '')?intval($obj->$pe->$field):0;
    }else if($obj->$pe->getDataType($field) == 'decimal'){
      $objValue = ($obj->$pe->$field != '')?floatval($obj->$pe->$field):0;
    }
    if ($field=='validatedWork') $value=Work::convertWork($value);
    if ($objValue!=$value) $changePeValue=true;
    if($objValue!=$value)$updatedNonePeField[] = ucfirst($field);
    $obj->$pe->$field = $value;
    $currentFormFields[$field]=$value;
  }else if(property_exists($className, 'id'.$className.ucfirst($field))){
    $col = 'id'.$className.ucfirst($field);
    if(pq_trim($value) == ''){
      if($obj->getDataType($col) == 'int'){
        $value = intval($value);
      }else if($obj->getDataType($col) == 'decimal'){
        $value = floatval($value);
      }
    }
    if($obj->$col != $value)$updatedNonePeField[] = ucfirst($field);
    $obj->$col = $value;
    $currentFormFields[$col] = $value;
  }else if(property_exists($className, 'id'.ucfirst($field))){
    $col = 'id'.ucfirst($field);
    if(pq_trim($value) == ''){
      if($obj->getDataType($col) == 'int'){
        $value = intval($value);
      }else if($obj->getDataType($col) == 'decimal'){
        $value = floatval($value);
      }
    }
    if($obj->$col != $value)$updatedNonePeField[] = ucfirst($field);
    $obj->$col = $value;
    $currentFormFields[$col] = $value;
  }else if(property_exists($className, $field)){
    if(pq_trim($value) == ''){
      if($obj->getDataType($field) == 'int'){
        $value = intval($value);
      }else if($obj->getDataType($field) == 'decimal'){
        $value = floatval($value);
      }
    }
    $objValue = $obj->$field;
    if($obj->getDataType($field) == 'int'){
      $objValue = ($obj->$field != '')?intval($obj->$field):0;
    }else if($obj->getDataType($field) == 'decimal'){
      $objValue = ($obj->$field != '')?floatval($obj->$field):0;
    }
    if ($objValue!=$value) $updatedNonePeField[] = ucfirst($field);
    if($field == 'idStatus' and $obj->idStatus!=$value){
      $changePeValue=true;
      $tab=SqlList::getList('Status','setIdleStatus');
      asort($tab);
      foreach ($tab as $idStatus=>$setIdleStatus) {
        if($idStatus == $value){
          $obj->idle = $setIdleStatus;
          if (property_exists($obj,'idleDate')) $obj->idleDate = ($setIdleStatus)?date('Y-m-d'):null;
        }
      }
      if (property_exists($obj,'done')) {
        $tab=SqlList::getList('Status','setDoneStatus');
        asort($tab);
        foreach ($tab as $idStatus=>$setDoneStatus) {
          if($idStatus == $value){
            $obj->done = $setDoneStatus;
            if (property_exists($obj,'doneDate') and ! $obj->doneDate) {
              $obj->doneDate = ($setDoneStatus)?date('Y-m-d'):null;
            }
          }
        }
      }
    }
    $obj->$field = $value;
    $currentFormFields[$field] = $value;
  }else if($field == 'predecessor'){
    $predstatus='';
    $valuePred=pq_trim($value," ;\n\r\t\v\x00");
    $valuePred=str_replace(',', ';', $valuePred);
    $arrayPred = explode(';', $valuePred);
    $arrayChanged=array();
    $existingDeps=array();
    foreach ($arrayPred as $val){
      $val=transformPredecessorValue($val);
      $pred = explode('#', $val);
      if($pred[0]==""){
        //$result = "";
        $predstatus='predescessorNull';
        continue;
      }
      if (count($pred)!=2 or !SqlElement::class_exists($pred[0])) {
        $control=i18n("incorectPredecessorsFormat");
        $result = '<b>' . i18n ( 'messageInvalidControls' ) . '</b><br/>' . $control;
        $result .= '<input type="hidden" id="lastOperationStatus" value="INVALID" />';
        break;
      }
    
      $refTypePred = $pred[0];
      $refIdPred = $pred[1];
      $crit=array('predecessorRefId'=>$refIdPred,'predecessorRefType'=>$refTypePred, 'successorRefId'=>$objectId, 'successorRefType'=>$className);
      $dep = Dependency::getSingleSqlElementFromCriteria('Dependency', $crit);
      if ($dep and $dep->id) {
        $existingDeps[$dep->id]=$dep;
        continue;
      }
      if($dep and $dep->predecessorRefType){
        $predRefType= $dep->predecessorRefType;
        $predRefId= $dep->predecessorRefId;
        $crit=array('id'=>$predRefId);
        $depReel= new $predRefType($predRefId);
        if($depReel->id == null){
          $control=i18n("incorectPredecessorsInput");
          $result = '<b>' . i18n ( 'messageInvalidControls' ) . '</b><br/>'. $control;
          $result .= '<input type="hidden" id="lastOperationStatus" value="INVALID" />';
          break;
        }
      }
      if($dep and $dep->predecessorRefType){
        $predRefType= $dep->predecessorRefType;
        $predRefId= $dep->predecessorRefId;
        $ElementIsAdmin = new $predRefType($predRefId);
        if(property_exists($ElementIsAdmin, "codeType")){
          if($ElementIsAdmin->codeType == 'ADM'){
            $control=i18n("incorectDependencyAdmin");
            $result = '<b>' . i18n ( 'messageInvalidControls' ) . '</b><br/>'. $control;
            $result .= '<input type="hidden" id="lastOperationStatus" value="INVALID" />';
            break;          }
        }else{
          $idElementIsAdmin = $ElementIsAdmin->idProject;
          $projectIsAdmin = new Project($idElementIsAdmin);
          if($projectIsAdmin->codeType == 'ADM'){
            $control=i18n("incorectDependencyAdmin");
            $result = '<b>' . i18n ( 'messageInvalidControls' ) . '</b><br/>'. $control;
            $result .= '<input type="hidden" id="lastOperationStatus" value="INVALID" />';
            break;
          }
        }
      }
      $dep->dependencyDelay=0;
      $dep->dependencyType='E-S';
      $result=$dep->save();
      $existingDeps[$dep->id]=$dep;
      $arrayChanged[$dep->predecessorId]=$dep->predecessorId;
      $arrayChanged[$dep->successorId]=$dep->successorId;
    }
    if($result==''){
      $predstatus='predescessorNoModif';
    }
    if(getLastOperationStatus($result)=='OK'){
      $changePeValue=true;
      $updatedNonePeField[] = ucfirst($field);
      $resultSave=$result;
      $crit=array('successorRefId'=>$objectId, 'successorRefType'=>$className);
      $dep=new Dependency();
      $depList = $dep->getSqlElementsFromCriteria($crit);
      foreach ($depList as $dep) {
        if (isset($existingDeps[$dep->id])){
          continue;
        }
        $predstatus='delete';
        $arrayChanged[$dep->predecessorId]=$dep->predecessorId;
        $arrayChanged[$dep->successorId]=$dep->successorId;
        $result=$dep->delete();
      }
    }
    if (count($arrayChanged)>0) {
//       $arrayDepend=array();
//       $dep=new Dependency();
//       foreach ($arrayChanged as $changed) {
//         $depList=$dep->getSqlElementsFromCriteria(null,false,"predecessorId=$changed or successorId=$changed");
//         $listPred="";
//         $listSucc="";
//         foreach ($depList as $dep) {
//           if ($dep->predecessorId==$changed) {
//             $listSucc.=($listSucc!="")?',':'';
//             $listSucc.="$dep->successorId#$dep->id#$dep->dependencyDelay#$dep->dependencyType";
//           } else {
//             $listPred.=($listPred!="")?',':'';
//             $listPred.="$dep->predecessorId#$dep->id#$dep->dependencyDelay#$dep->dependencyType";
//           }
//         }
//         $arrayDepend[$changed]=array("dependPred"=>$listPred, "dependSucc"=>$listSucc);
//       }
//       $jsonDep=json_encode($arrayDepend);
      $jsonDep=Dependency::getJsonDependenciesForItems($arrayChanged);
      echo "<input type='hidden' id='dependencyChanged' value='$jsonDep' />";
    }
  }else if($field == 'successor'){
    $succstatus='';
    $valueSucc=pq_trim($value," ;\n\r\t\v\x00");
    $valueSucc=str_replace(',', ';', $valueSucc);
    $arraySucc = explode(';', $valueSucc);
    $arrayChanged=array();
    $existingDeps=array();
    foreach ($arraySucc as $val){
      $val=transformPredecessorValue($val);
      $succ = explode('#', $val);
      if($succ[0]==""){
        //$result = "";
        $succstatus='successorNull';
        continue;
      }
      if (count($succ)!=2 or !SqlElement::class_exists($succ[0])) {
        $control=i18n("incorectSuccessorsFormat");
        $result = '<b>' . i18n ( 'messageInvalidControls' ) . '</b><br/>' . $control;
        $result .= '<input type="hidden" id="lastOperationStatus" value="INVALID" />';
        break;
      }
      
      $refTypeSucc = $succ[0];
      $refIdSucc = $succ[1];
      $crit=array('successorRefId'=>$refIdSucc,'successorRefType'=>$refTypeSucc, 'predecessorRefId'=>$objectId, 'predecessorRefType'=>$className);
      $dep = Dependency::getSingleSqlElementFromCriteria('Dependency', $crit);
      if ($dep and $dep->id) {
        $existingDeps[$dep->id]=$dep;
        continue;
      }
      if($dep and $dep->successorRefType){
        $succRefType= $dep->successorRefType;
        $succRefId= $dep->successorRefId;
        $crit=array('id'=>$succRefId);
        $depReel= new $succRefType($succRefId);
        if($depReel->id == null){
          $control=i18n("incorectSuccessorsInput");
          $result = '<b>' . i18n ( 'messageInvalidControls' ) . '</b><br/>'. $control;
          $result .= '<input type="hidden" id="lastOperationStatus" value="INVALID" />';
          break;
        }
      }
      if($dep and $dep->successorRefType){
        $succRefType= $dep->successorRefType;
        $succRefId= $dep->successorRefId;
        $ElementIsAdmin = new $succRefType($succRefId);
        if(property_exists($ElementIsAdmin, "codeType")){
          if($ElementIsAdmin->codeType == 'ADM'){
            $control=i18n("incorectDependencyAdmin");
            $result = '<b>' . i18n ( 'messageInvalidControls' ) . '</b><br/>'. $control;
            $result .= '<input type="hidden" id="lastOperationStatus" value="INVALID" />';
            break;          }
        }else{
          $idElementIsAdmin = $ElementIsAdmin->idProject;
          $projectIsAdmin = new Project($idElementIsAdmin);
          if($projectIsAdmin->codeType == 'ADM'){
            $control=i18n("incorectDependencyAdmin");
            $result = '<b>' . i18n ( 'messageInvalidControls' ) . '</b><br/>'. $control;
            $result .= '<input type="hidden" id="lastOperationStatus" value="INVALID" />';
            break;
          }
        }
      }
      $dep->dependencyDelay=0;
      $dep->dependencyType='E-S';
      $result=$dep->save();
      $existingDeps[$dep->id]=$dep;
      $arrayChanged[$dep->predecessorId]=$dep->predecessorId;
      $arrayChanged[$dep->successorId]=$dep->successorId;
    }
    if($result==''){
      $succstatus='successorNoModif';
    }
    if(getLastOperationStatus($result)=='OK'){
      $changePeValue=true;
      $updatedNonePeField[] = ucfirst($field);
      $resultSave=$result;
      $crit=array('predecessorRefId'=>$objectId, 'predecessorRefType'=>$className);
      $dep=new Dependency();
      $depList = $dep->getSqlElementsFromCriteria($crit);
      foreach ($depList as $dep) {
        if (isset($existingDeps[$dep->id])){
          continue;
        }
        $succstatus='delete';
        $arrayChanged[$dep->predecessorId]=$dep->predecessorId;
        $arrayChanged[$dep->successorId]=$dep->successorId;
        $result=$dep->delete();
      }
    }
    if (count($arrayChanged)>0) {
      $jsonDep=Dependency::getJsonDependenciesForItems($arrayChanged);
      echo "<input type='hidden' id='dependencyChanged' value='$jsonDep' />";
    }
  }
  
}
if ($result=="" or getLastOperationStatus($result)=='OK') {
  // save to database
  $previousResult=$result;
  if (SqlElement::class_exists($className.'PlanningElement') and isset($editableFields['validatedDuration']) and (! isset($editableFields['validatedEndDate']) or ! isset($editableFields['validatedStartDate']) ) ) {
    $pe=$className.'PlanningElement';
    $obj->$pe->_skipDurationCalculation=true;
  }
  $result = $obj->save();
  if ($resultSave!=''){$result=$resultSave;}
  if (($predstatus == "delete" || $succstatus == "delete") && $resultSave==""){$result=$previousResult;}
}
$status = getLastOperationStatus ( $result );
// Message of correct saving
if ($status == "OK") {
  Sql::commitTransaction ();
} else {
  Sql::rollbackTransaction ();
}
if ($status != "OK" && $status != "NO_CHANGE"){
  $peName=$className.'PlanningElement';
  $TypeName = SqlElement::getTypeName($className);
  if (property_exists($obj, $peName)) {
    $pe = $obj->$peName;
    $resultObj=$obj->getExtraRequiredFields($obj->$TypeName,$obj->idStatus,$obj->$peName->idPlanningMode,null);
    foreach ($resultObj as $key=>$val) {
      $extraRequiredFields[$key]=$val;
    }
    $resultPe=$pe->getExtraRequiredFields($obj->$TypeName,$obj->idStatus,$obj->$peName->idPlanningMode,null);
    foreach ($resultPe as $key=>$val) {
      $extraRequiredFields[$peName.'_'.$key]=$val;
    }
  }
  if (property_exists($obj, 'WorkElement') and $className!='TicketSimple') {
    $resultObj=$obj->getExtraRequiredFields($obj->$TypeName,$obj->idStatus,null,null);
    foreach ($resultObj as $key=>$val) {
      $extraRequiredFields[$key]=$val;
    }
    $we=$obj->WorkElement;
    $resultWe=$we->getExtraRequiredFields($obj->$TypeName,$obj->idStatus,null,null);
    foreach ($resultWe as $key=>$val) {
      $extraRequiredFields['WorkElement_'.$key]=$val;
    }
  }
  
  
  $arrayDefault=array('description'=>'optional', 'result'=>'optional', 'idResource'=>'optional', 'idResolution'=>'optional',
      $peName.'_validatedStartDate'=>'optional', $peName.'_validatedEndDate'=>'optional', $peName.'_validatedDuration'=>'optional');
  foreach ($arrayDefault as $key=>$val) {
    if (property_exists($obj,$key) and $obj->isAttributeSetToField($key,'required')) {
      $arrayDefault[$key]='required';
    }
  }
  $editable = Parameter::getPlanningColumnEditable();
  $extraRequiredFields=array_merge($arrayDefault,$extraRequiredFields);
  foreach ($extraRequiredFields as $col=>$option){
    $field = (pq_strpos($col, $peName) > -1)?pq_str_replace($peName.'_', '', $col):$col;
    if(ucfirst($field) == 'Result'){
      echo "<input type='hidden' id='needResult' name='needResult' value='true' />";
    }
    if(ucfirst($field) == 'Description'){
      echo "<input type='hidden' id='needDescription' name='needDescription' value='true' />";
    }
    if($option == 'required'){
      if(isset($editable[ucfirst($field)]) && isset($editableFields[$field])){
        unset($extraRequiredFields[$col]);
      } else if(isset($obj->$field) and $obj->$field){
        unset($extraRequiredFields[$col]);
      } 
    }else{
      unset($extraRequiredFields[$col]);
    }
  }
  if(count($extraRequiredFields) > 0){
    echo '<input type="hidden" id="lastSaveId" value="" /><input type="hidden" id="lastOperation" value="update" /><input type="hidden" id="lastOperationStatus" value="'.$status.'" />';
    echo "<input type='hidden' id='currentFormFields' name='currentFormFields' value='".json_encode($currentFormFields, JSON_HEX_APOS | JSON_HEX_QUOT, JSON_HEX_AMP)."' />";
    echo "<input type='hidden' id='extraRequiredFields' name='extraRequiredFields' value='".json_encode($extraRequiredFields, JSON_HEX_APOS | JSON_HEX_QUOT | JSON_HEX_AMP)."' />";
    echo "<input type='hidden' id='editRowObjectClass' name='editRowObjectClass' value='".$className."' />";
    echo "<input type='hidden' id='editRowObjectId' name='editRowObjectId' value='".$objectId."' />";
  }else{
    if($status == 'CONFIRM'){
      echo "<input type='hidden' id='editRowObjectConfirm' name='editRowObjectConfirm' value='1' />";
    }
    echo '<div class="message' . $status . '" >' . $result. '</div>';
  }
}else{
  $pe = $className.'PlanningElement';
  if ($status == "OK" and $className=='Project') {
    if ($needProjectListRefresh) {
      echo '<input type="hidden" id="needProjectListRefresh" value="true" />';
    }
    if($idCalendarForCalendarRefresh){
      echo '<input type="hidden" id="idProjectForCalendarRefresh" value="'.$obj->id.'" />';
      echo '<input type="hidden" id="idCalendarForCalendarRefresh" value="'.$obj->idCalendarDefinition.'" />';
    }
  }
  if ($status == "OK") {
    $updateRight=securityGetAccessRightYesNo('menu' . $className, 'update', $obj);
    $deleteRight=securityGetAccessRightYesNo('menu' . $className, 'delete', $obj);
    echo "<input type='hidden' id='updateRightAfterSave' value='$updateRight' />";
    echo "<input type='hidden' id='deleteRightAfterSave' value='$deleteRight' />";
    echo "<input type='hidden' id='editRowObjetSkipRefresh' value='".(! $changePeValue)."' />";
    if($updatedNonePeField)echo "<input type='hidden' id='editRowObjetFieldToRefresh' value='".implode(',', $updatedNonePeField)."' />";
  }
  $globalResult=$result;
  $globalStatus=$status;
  echo '<div class="message' . $status . '" >' . $result. '</div>';
}
function transformPredecessorValue($val) {
  $val=trim($val);
  $firstCar=pq_strtoupper(pq_substr($val,0,1));
  $firstCars2=pq_strtoupper(pq_substr($val,0,2));

  if ($firstCars2=='PS' or $firstCars2=='TS' or $firstCars2=='MG' or $firstCars2=='PM') {
    $num=pq_substr($val,2);
    if (! is_numeric($num) or ! intval($num)) return $val;
    $num=intval($num);
    if ($firstCars2=='PS') $val="PokerSession#$num";
    if ($firstCars2=='TS') $val="TestSession#$num";
    if ($firstCars2=='PM') $val="PeriodicMeeting#$num";
    if ($firstCars2=='MG') $val="Meeting#$num";
  }
  if ($firstCar=='A' or $firstCar=='P' or $firstCar=='M') {
    $num=pq_substr($val,1);
    if (! is_numeric($num) or ! intval($num)){
      return $val;
    }
    $num=intval($num);
    if ($firstCar=='A') $val="Activity#$num";
    if ($firstCar=='P') $val="Project#$num";
    if ($firstCar=='M') $val="Milestone#$num";
  }
  return $val;
}
?>