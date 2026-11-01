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
 * Copy an object as a new one (of the same class) : call corresponding method in SqlElement Class
 */
require_once "../tool/projeqtor.php";
projeqtor_set_time_limit(300);


$fromContextMenu = RequestHandler::getBoolean('fromContextMenu');
$objectId = RequestHandler::getId('objectId');
$objectClass = RequestHandler::getClass('objectClass');

// Get the object from session(last status before change)
if($fromContextMenu){
  $proj=new $objectClass($objectId);
}else{
  $proj=SqlElement::getCurrentObject(null,null,true,false);
}
if (! is_object($proj)) {
  throwError('last saved object is not a real object');
}
// Get the object class from request

if (! pq_array_key_exists('copyProjectToName',$_REQUEST)) {
  throwError('copyProjectToName parameter not found in REQUEST');
}
$toName=$_REQUEST['copyProjectToName'];
if (! pq_array_key_exists('copyProjectToType',$_REQUEST)) {
  throwError('copyProjectToName parameter not found in REQUEST');
}
$toType=$_REQUEST['copyProjectToType'];

if (! pq_array_key_exists('copyProjectToSubProject',$_REQUEST)) {
  throwError('copyProjectToSubProject parameter not found in REQUEST');
}
$toSubProject=pq_trim($_REQUEST['copyProjectToSubProject']);

$copyStructure=false;
if (pq_array_key_exists('copyProjectStructure',$_REQUEST)) {
	$copyStructure=true;
}

$copyOtherStructure=false;
if (pq_array_key_exists('copyOtherProjectStructure',$_REQUEST)) {
  $copyOtherStructure=true;
}

$copyProjectRequirement=false;
if (pq_array_key_exists('copyProjectRequirement',$_REQUEST)) {
  $copyProjectRequirement=true;
}

$copyProjectRiskOpportunity = RequestHandler::getBoolean('copyProjectRiskOpportunity');
  
$copySubProjects=false;
if (pq_array_key_exists('copySubProjects',$_REQUEST)) {
  $copySubProjects=true;
}
$copyAffectations=false;
if (pq_array_key_exists('copyProjectAffectations',$_REQUEST)) {
  $copyAffectations=true;
}
$copyAssignments=false;
if (pq_array_key_exists('copyProjectAssignments',$_REQUEST)) {
	$copyAssignments=true;
}

$codeProject=null;
if (pq_array_key_exists('copyProjectToProjectCode',$_REQUEST)) {
  $codeProject=$_REQUEST['copyProjectToProjectCode'];
}

//gautier #1769
$copyToWithLinks=false;
if (pq_array_key_exists('copyToWithLinks',$_REQUEST)) {
  $copyToWithLinks=true;
}

//Krowry #2206
$copyToWithVersionProjects=false;
if (pq_array_key_exists('copyToWithVersionProjects',$_REQUEST)) {
  $copyToWithVersionProjects=true;
}

// ADD BY Marc TABARY - 2017-03-17 - COPY ACTIVITY PRICE WHEN COPY PROJECT
$copyToWithActivityPrice=false;
if (pq_array_key_exists('copyToWithActivityPrice',$_REQUEST)) {
  $copyToWithActivityPrice=true;
}

$copyToWithAttachments=RequestHandler::getBoolean('copyToWithAttachments');
// END ADD BY Marc TABARY - 2017-03-17 - COPY ACTIVITY PRICE WHEN COPY PROJECT

$copyToWithStatus = (RequestHandler::getBoolean('copyToWithStatus') == 1)?true:false;

$moveAfterCreate = RequestHandler::getId('moveAfterCreate');

// copy from existing object
Sql::beginTransaction();
$error=false;
PlanningElement::$_noDispatch=true;
SqlElement::$_doNotSaveLastUpdateDateTime=true;
//$newProj=copyProject($proj, $toName, $toType , $copyStructure, $copySubProjects, $copyAffectations, $copyAssignments, null);

Security::checkValidId($toType);

// CHANGE BY Marc TABARY - 2017-03-17 - COPY ACTIVITY PRICE WHEN COPY PROJECT
$proj->projectCode=$codeProject;
if($proj->idProject != $toSubProject){
  $moveAfterCreate=null;
}
$newProj=$proj->copyTo('Project',
                        $toType,
                        $toName,
                        null, 
                        false, false,
                        $copyToWithAttachments,
                        $copyToWithLinks,
                        $copyAssignments,
                        false, $toSubProject, null, false,
                        $copyToWithActivityPrice,
                        $copyToWithStatus,
                        $copyToWithVersionProjects, false, $moveAfterCreate);
  // Old
//$newProj=$proj->copyTo('Project',$toType,$toName,false,false, false,$copyToWithLinks,$copyAssignments,false, $toSubProject, null, false, $copyToWithVersionProjects ); // toProject
// END CHANGE BY Marc TABARY - 2017-03-17 - COPY ACTIVITY PRICE WHEN COPY PROJECT

$result=$newProj->_copyResult;
if (getLastOperationStatus($result)!='OK') {
  $error=true;
  $result .= '<input type="hidden" id="lastSaveId" value="" />';
  $result .= '<input type="hidden" id="lastOperation" value="copy" />';
  $result .= '<input type="hidden" id="lastOperationStatus" value="INVALID" />';
}

// copy affectations
if (!$error and $copyAffectations) {
	$aff=new Affectation();
	$crit=array('idProject'=>$proj->id);
	$lstAff=$aff->getSqlElementsFromCriteria($crit);
	foreach ($lstAff as $aff) {
	  $res = new ResourceAll($aff->idResource);
	  if ($res->idle) continue;
		$critExists=array('idProject'=>$newProj->id, 'idResource'=>$aff->idResource);
		$affExists=SqlElement::getSingleSqlElementFromCriteria('Affectation', $critExists);
		if (!$affExists or !$affExists->id) {
			$aff->id=null;
			$aff->idProject=$newProj->id;
			$aff->save();
		}
	}
}
if(!$error and $copyProjectRequirement){
	$req=new Requirement();
	$crit=array('idProject'=>$proj->id);
	$lstReq=$req->getSqlElementsFromCriteria($crit);
	foreach ($lstReq as $req) {
		$critExists=array('idProject'=>$newProj->id, 'id'=>$req->id);
		$reqExists=SqlElement::getSingleSqlElementFromCriteria('Requirement', $critExists);
		if ($reqExists) {
			$copyReq=$req->copyTo('Requirement', $req->idRequirementType, $req->name, $newProj->id, false, true, true, true, $copyAssignments,$copyAffectations,false, false, false, $copyToWithActivityPrice, $copyToWithStatus, false, $moveAfterCreate);
			$res=$copyReq->_copyResult;
			if (! pq_stripos($res,'id="lastOperationStatus" value="OK"')>0 ) {
				$error=true;
				$result = $res;
				$result .= '<input type="hidden" id="lastSaveId" value="" />';
				$result .= '<input type="hidden" id="lastOperation" value="copy" />';
				$result .= '<input type="hidden" id="lastOperationStatus" value="INVALID" />';
			}
			unset($copyReq->_copyResult);
		}
	}
}
if(!$error and $copyProjectRiskOpportunity){
	$crit=array('idProject'=>$proj->id);
	$risk=new Risk();
	$lstRisk=$risk->getSqlElementsFromCriteria($crit);
	foreach ($lstRisk as $risk) {
		$critExists=array('idProject'=>$newProj->id, 'id'=>$risk->id);
		$rskExists=SqlElement::getSingleSqlElementFromCriteria('Risk', $critExists);
		if ($rskExists) {
			$copyRisk=$risk->copyTo('Risk', $risk->idRiskType, $risk->name, $newProj->id, false, true, true, true, $copyAssignments,$copyAffectations,false, false, false, $copyToWithActivityPrice, $copyToWithStatus, false, $moveAfterCreate);
			$res=$copyRisk->_copyResult;
			if (! pq_stripos($res,'id="lastOperationStatus" value="OK"')>0 ) {
				$error=true;
				$result = $res;
				$result .= '<input type="hidden" id="lastSaveId" value="" />';
				$result .= '<input type="hidden" id="lastOperation" value="copy" />';
				$result .= '<input type="hidden" id="lastOperationStatus" value="INVALID" />';
			}
			unset($copyRisk->_copyResult);
		}
	}
	$opp = new Opportunity();
	$lstOpp=$opp->getSqlElementsFromCriteria($crit);
	foreach ($lstOpp as $opp) {
		$critExists=array('idProject'=>$newProj->id, 'id'=>$opp->id);
		$oppExists=SqlElement::getSingleSqlElementFromCriteria('Opportunity', $critExists);
		if ($oppExists) {
			$copyOpp=$opp->copyTo('Opportunity', $opp->idOpportunityType, $opp->name, $newProj->id, false, true, true, true, $copyAssignments,$copyAffectations,false, false, false, $copyToWithActivityPrice, $copyToWithStatus, false, $moveAfterCreate);
			$res=$copyOpp->_copyResult;
			if (! pq_stripos($res,'id="lastOperationStatus" value="OK"')>0 ) {
				$error=true;
				$result=$res;
				$result .= '<input type="hidden" id="lastSaveId" value="" />';
				$result .= '<input type="hidden" id="lastOperation" value="copy" />';
				$result .= '<input type="hidden" id="lastOperationStatus" value="INVALID" />';
			}
			unset($copyOpp->_copyResult);
		}
	}
}

unset($newProj->_copyResult);
if(!$error) {
  $newProj->sortOrder=$newProj->ProjectPlanningElement->wbsSortable; // update sortOrder
  $newProj->save();
}

if (!$error and RequestHandler::isCodeSet('copyToDescription') and property_exists($newProj, 'description')) {
  $newProj->description = RequestHandler::getValue('copyToDescription');
  $resDescription = $newProj->saveForced();
  $lastOp = getLastOperationStatus($resDescription);
  if ($lastOp != "OK" and $lastOp!="NO_CHANGE") {
    errorLog("Copy description update failed for " . get_class($newObj) . " #$newObj->id : $resDescription");
  }
}
if (!$error and ($copyStructure or $copyOtherStructure)) {
  $res=PlanningElement::copyStructure($proj, $newProj, false, false, $copyToWithAttachments,$copyToWithLinks,$copyAssignments, $copyAffectations,$newProj->id,$copySubProjects,$copyStructure,$copyOtherStructure, $copyToWithStatus, $copyToWithActivityPrice, $copyProjectRequirement, $copyProjectRiskOpportunity);
  if ($res!='OK') {
    $result=$res;
    $error=true;
  }
}
// if (!$error and $copyOtherStructure) {
//   $res=PlanningElement::copyOtherStructure($proj, $newProj, false, false, $copyToWithAttachments,$copyToWithLinks,$copyAssignments, $copyAffectations,$newProj->id,$copySubProjects,$copyToWithVersionProjects,$copyStructure);
//   if ($res!='OK') {
//     $result=$res;
//     $error=true;
//   }
// }

if(!$error and !$copyStructure and !$copyOtherStructure and $copySubProjects){
  $res=PlanningElement::copyStructureProject($proj, $newProj, false, false, $copyToWithAttachments,$copyToWithLinks,$copyAssignments, $copyAffectations,$newProj->id,$copySubProjects, $copyToWithStatus, $copyToWithActivityPrice, $copyProjectRequirement, $copyProjectRiskOpportunity);
  if ($res!='OK') {
    $result=$res;
    $error=true;
  }
}

if (!$error and ($copyStructure or $copyOtherStructure or $copySubProjects)) {
  PlanningElement::copyStructureFinalize();
}
// Message of correct saving
$status = displayLastOperationStatus($result);
if ($status == "OK") {
  if (! pq_array_key_exists ( 'comboDetail', $_REQUEST )) {
    SqlElement::setCurrentObject (new Project( $newProj->id ));
  }
  User::resetAllVisibleProjects(null,getSessionUser()->id); // Will reteive visibiity for new project and sub-projects
}else {
  if ($newProj && $newProj->id) {
    $selectedProj = pq_explode(',', getSessionValue('project'));
    $key = array_search($newProj->id, $selectedProj);
    if ($key !== false) {
      unset($selectedProj[$key]);
      setSessionValue('project', implode(',', $selectedProj));
    }
  }
}

?>