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
 * Save the current object : call corresponding method in SqlElement Class
 * The new values are fetched in $_REQUEST
 * The old values are fetched in $currentObject of SESSION
 * Only changed values are saved. 
 * This way, 2 users updating the same object don't mess.
 */

require_once "../tool/projeqtor.php";


// Get the object class from request
if (! pq_array_key_exists('objectClass',$_REQUEST)) {
  throwError('objectClass parameter not found in REQUEST');
}
$className=$_REQUEST['objectClass'];
Security::checkValidClass($className);

if (! pq_array_key_exists('selection',$_REQUEST)) {
  throwError('selection parameter not found in REQUEST');
}else {
  $selection=pq_trim($_REQUEST['selection']);
  $selectList=pq_explode(';',$selection);
}

if(RequestHandler::isCodeSet('idMultipleUpdateAttribute')){
  $field=RequestHandler::getValue('idMultipleUpdateAttribute');
}else{
  throwError('field  not found in REQUEST');
}

if ($field == ''){
  echo '<div class="messageINVALID">' . i18n('errorNoFieldSelected') . '</div>';
  echo '<input type="hidden" id="lastOperation" name="lastOperation" value="save">';
  echo '<input type="hidden" id="lastOperationStatus" name="lastOperationStatus" value="INVALID">';
  exit;
}

if (!$selection or count($selectList)==0) {
	 $summary='<div class=\'messageWARNING\' >'.i18n('messageNoData',array(i18n($className))).'</div >';
	 echo '<input type="hidden" id="summaryResult" value="'.$summary.'" />';
	 exit;
}
$isLongText=RequestHandler::getValue("isLongText");
$newValue='';
$fieldSearch=$field;
$obj= new $className();
$lst=RequestHandler::getValue('multipleUpdateValueList');
if(pq_strpos($field, 'Element_'))$fieldSearch=pq_substr($field,pq_strpos($field, 't_')+2);

$objForCheck = $obj;
if (pq_strpos($field, 'Element_') !== false) {
  $subElementClass = pq_substr($field, 0, pq_strpos($field, 't_')+1);
  if (property_exists($obj, $subElementClass)) $objForCheck = new $subElementClass();
}
$lst=RequestHandler::getValue('multipleUpdateValueList');
if(pq_trim(RequestHandler::getValue('newMultipleUpdateValue'))!=''){
  $newValue=RequestHandler::getValue('newMultipleUpdateValue');
}elseif (pq_trim(RequestHandler::getValue('newMultipleUpdateValueNum'))!=''){
  $newValue=RequestHandler::getValue('newMultipleUpdateValueNum');
}elseif (pq_trim(RequestHandler::getValue('multipleUpdateTextArea'))!=''){
  $newValue=RequestHandler::getValue('multipleUpdateTextArea');
}elseif (!empty($lst) and isForeignKey($fieldSearch, $objForCheck)){
  foreach ($lst as $idL=>$valList){
    $newValue=$valList;
  }
}elseif (pq_trim(RequestHandler::getValue('multipleUpdateValueDate')) and !pq_trim(RequestHandler::getValue('multipleUpdateValueTime'))){
  $newValue=RequestHandler::getValue('multipleUpdateValueDate');
}elseif (pq_trim(RequestHandler::getValue('multipleUpdateValueDate')) and pq_trim(RequestHandler::getValue('multipleUpdateValueTime'))){
  $newValue=RequestHandler::getValue('multipleUpdateValueDate').' '.pq_substr(RequestHandler::getValue('multipleUpdateValueTime'),1);
  $newValue=convertUserTimeToServerTimezone($newValue);
}elseif (pq_trim(RequestHandler::getValue('multipleUpdateValueTime'))){
  $newValue=pq_substr(RequestHandler::getValue('multipleUpdateValueTime'),1);
  $newValue=convertUserTimeToServerTimezone($newValue);
}elseif ($objForCheck->getDataType($fieldSearch)=='int' and $objForCheck->getDataLength($fieldSearch)==1){
  if(RequestHandler::getValue('multipleUpdateValueCheckbox') and RequestHandler::getValue('multipleUpdateValueCheckbox')=='on') $newValue=1;
  else $newValue=0;
}else if (pq_trim(RequestHandler::getValue('multipleUpdateColorButtonInput'))!=''){
  $newValue=RequestHandler::getValue('multipleUpdateColorButtonInput');
}
if (pq_substr($field, -12) == 'hatchPattern' and  pq_trim(RequestHandler::getValue('multipleUpdateValueHatch'))!='') {
  $newValue = RequestHandler::getValue('multipleUpdateValueHatch'); 
}

$isIndivisibilityField = ($fieldSearch == 'indivisibility' || $fieldSearch == 'minimumThreshold');
if($field=="idActivity"){
  $act=new Activity($newValue);
  $idProjAct=$act->idProject;
}
if($field=="maxDailyWork" or $field=="maxWeeklyWork"){
  $coef= Work::getImputationCoef();
  $newValue=$newValue/$coef;
}

SqlElement::unsetCurrentObject();
SqlElement::setSaveConfirmed(); // PBER #10335
$cptOk=0;
$cptError=0;
$cptWarning=0;
$cptNoChange=0;
$note=false;
$idProjectForCalendarRefresh=array();
echo "<table style='margin-top:5px;'>";
foreach ($selectList as $id) {
	if (!pq_trim($id)) { continue;}
	projeqtor_set_time_limit(300);
	Sql::beginTransaction();
	echo '<tr class="trSaveObjectMultiple">';
	echo '<td valign="top">&nbsp;<b>#'.$id.'&nbsp:&nbsp;</b></td>';
	$item=new $className($id);
	if (property_exists($item, 'locked') and $item->locked) {
		Sql::rollbackTransaction();
    $cptWarning++;
        echo '<td><span class="messageWARNING" >' . i18n($className) . " #" . htmlEncode($item->id) . ' '.i18n('colLocked'). '</span></td>';
		continue;
	}
	if ($isIndivisibilityField && $className == 'Activity') {
	  $pmName = 'idActivityPlanningMode';
	  $idPlanningMode = null;
	  if (property_exists($item, $pmName) && $item->$pmName) $idPlanningMode = $item->$pmName;
	  elseif (property_exists($item->ActivityPlanningElement, 'idPlanningMode')) $idPlanningMode = $item->ActivityPlanningElement->idPlanningMode;
	  if ($idPlanningMode) {
	    $mode = SqlList::getFieldFromId('PlanningMode', $idPlanningMode, 'code');
	    if ($mode != 'ASAP' && $mode != 'ALAP' && $mode != 'START' && $mode != 'STARR' && $mode != 'GROUP') {
	      Sql::rollbackTransaction();
	      $cptWarning++;
	      echo '<td class="tdSaveObjectMultiple"><div style="margin-bottom:5px;width:100%;"><span style="width:100%;" class="messageINVALID" >' . i18n($className) . " #" . htmlEncode($item->id) . ' : ' . i18n('PlanningMode') . ' = ' . SqlList::getNameFromId('PlanningMode', $idPlanningMode) . '</span></div></td>';
	      continue;
	    }
	  }
	}
	if(property_exists($item, $field) and pq_trim(pq_strpos($field, 'Element_'))==""){
	  if($isLongText!="true"){
	    if($field=="idActivity" and property_exists($className, "idProject") and $item->idProject!=$idProjAct){
	      if($className!="Ticket" or ($className=="Ticket" and  $item->WorkElement->realWork==0)){
	        if ($idProjAct) $item->idProject=$idProjAct;
	      }
	    }
	    $item->$field=$newValue;
	  }else if($field=='tags') {
	    $statusSaveTag='';
	    $newValue= replaceAccentuatedCharacters($newValue);
	    $cleaned = preg_replace("/[^a-z0-9]/i", '', $newValue);    
	    if ($newValue != $cleaned || empty(trim($newValue))){
	      echo '<div id="divSaveObjectMultiple" style="width: auto;height: 15%;display: grid;align-items: center;text-align: center;" class=\'messageWARNING\' >' .ucfirst(i18n("tagFormatError")). '</div>';
	      return;
	    }
	    if ($item->$field != null){
	      if (strpos($item->$field, '#'.$newValue.'#') !== false){
	        $statusSaveTag = 'NO_CHANGE';
	      }
	      $newValue = $newValue."#";
	    }else{
	      $newValue="#".$newValue."#";
	    }
	    if ($statusSaveTag != 'NO_CHANGE'){
	      $item->$field=$item->$field.$newValue;
	      $statusSaveTag = 'OK'; 
	    }
	    $newValue = trim($newValue, '#');
	  }else{
	    if (!empty($item->$field)) $item->$field=$item->$field."<br>".$newValue;
	    else $item->$field=$newValue;
	  }
	  
	}else if (pq_trim(pq_strpos($field, 'Element_'))!="" and property_exists(pq_substr($field,0, pq_strpos($field, 't_')+1),pq_substr($field,pq_strpos($field, 't_')+2))){
	   $subElement=pq_substr($field,0, pq_strpos($field, 't_')+1);
	   $fieldElment=pq_substr($field, pq_strpos($field, 't_')+2);
	   if($fieldElment!="fixPlanning" and $fieldElment!="paused"){
	     $item->$subElement->$fieldElment=$newValue;
	   }else{
	     $item->$fieldElment=$newValue;
	     if ($fieldElment=='paused' and $newValue==0 and property_exists($item, 'fixPlanning')) {
	       $item->fixPlanning=$newValue;
	     }
	     
	   }
	}elseif ($field=="Note" and property_exists($item,'_Note')){
	   $note=true;
	      $noteObj=new Note();
	      $noteObj->refType=$className;
	      $noteObj->refId=$id;
	      $noteObj->creationDate=date('Y-m-d H:i:s');
	      $noteObj->note=nl2br($newValue);
	      $noteObj->idPrivacy=1;
	      $res=new Resource(getSessionUser()->id);
	      $noteObj->idTeam=$res->idTeam;
	      $resultSave=$noteObj->save();
	} else{
	  echo '<td><span class="messageWARNING" >' . i18n($className) . " #" . htmlEncode($item->id) . ' '.i18n('nonExistentFields'). ' '.$field.'</span></td>';
	  continue;
	}
	if($field=="idStatus" and property_exists($item,'idStatus')){
	  $item->recalculateCheckboxes(true);
	}
	if(!$note) $resultSave=$item->save();
	$resultSave = pq_str_replace('<br/><br/>','<br/>',$resultSave);
	if ($field!='tags'){
	  $statusSave = getLastOperationStatus ( $resultSave );
	}else{
	  $statusSave = $statusSaveTag;
	}
	if ($statusSave=="ERROR" ) {
	  Sql::rollbackTransaction();
	  $cptError++;
	} else if ($statusSave=="OK") {
	  Sql::commitTransaction();
	  $cptOk++;
	} else if ($statusSave=="NO_CHANGE") {
	  Sql::commitTransaction();
	  $cptNoChange++;
	} else { 
	  Sql::rollbackTransaction();
	  $cptWarning++;
  }
  echo '<td><div style="width:100%;margin-bottom:5px" class="message'.$statusSave.'" >' . $resultSave . '</div></td>';
  echo '</tr>';
  if($field=="idCalendarDefinition" and $statusSave == "OK" and $className=='Project'){
    $idProjectForCalendarRefresh["$item->id,$item->idCalendarDefinition"]="$item->id,$item->idCalendarDefinition";
  }
}
if ($idProjectForCalendarRefresh) {
  echo '<input type="hidden" id="idProjectForCalendarRefresh" value="'.implode('#', $idProjectForCalendarRefresh).'" />';
}
echo "</table>";
$summary="";
if ($cptError) {
  $summary.='<div class=\'messageERROR\' >' . $cptError." ".i18n('resultError') . '</div>';
}
if ($cptOk) {
  $summary.='<div class=\'messageOK\' >' . $cptOk." ".i18n('resultOk') . '</div>';
}
if ($cptWarning) {
  $summary.='<div class=\'messageWARNING\' >' . $cptWarning." ".i18n('resultWarning') . '</div>';
}
if ($cptNoChange) {
  $summary.='<div class=\'messageNO_CHANGE\' >' . $cptNoChange." ".i18n('resultNoChange') . '</div>';
}
echo '<input type="hidden" id="summaryResult" value="'.$summary.'" />';
?>