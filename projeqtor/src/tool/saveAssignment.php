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
 * The new values are fetched in the Request with RequestHandler that controls format and security
 */

require_once "../tool/projeqtor.php";

if (RequestHandler::getBoolean('getLastSaveResult')) {
  if (!sessionValueExists('lastSaveResult')) {
    http_response_code(404);
    exit;
  }
  echo getSessionValue('lastSaveResult');
  exit;
}

ob_start();
$assignedChangeStatus=(Parameter::getGlobalParameter("statusChangeAssignment")=="YES")?true:false;
$refreshObj='false';

$assignmentId=RequestHandler::getId('assignmentId');
$assignmentId=pq_trim($assignmentId);
if ($assignmentId=='') $assignmentId=null;

// Get the assignment info
$refType=RequestHandler::getClass('assignmentRefType',true);
//Security::checkValidClass($refType);

$refId=RequestHandler::getId('assignmentRefId',true);
//Security::checkValidId($refId);
$refId=intval($refId);

$idResource=RequestHandler::getId('assignmentIdResource');
//Security::checkValidId($idResource);

$unique=RequestHandler::getBoolean('assignmentUnique');

$definitive=RequestHandler::getId('definitive');
if ($definitive>0) {
  $idResource=$definitive;
  $unique=false;
}

$idRole=RequestHandler::getId('assignmentIdRole');
//Security::checkValidId($idRole);

$cost=RequestHandler::getNumeric('assignmentDailyCost');
//Security::checkValidNumeric($cost);

$rate=RequestHandler::getNumeric('assignmentRate',true);
//Security::checkValidNumeric($rate);

$proportional=RequestHandler::getBoolean('assignmentProportional');

$assignedWork=RequestHandler::getNumeric('assignmentAssignedWork',true);
//Security::checkValidNumeric($assignedWork);

$realWork=RequestHandler::getNumeric('assignmentRealWork',true);
//Security::checkValidNumeric($realWork);

$leftWork=RequestHandler::getNumeric('assignmentLeftWork',true);
//Security::checkValidNumeric($leftWork);

$plannedWork=RequestHandler::getNumeric('assignmentPlannedWork',true);
//Security::checkValidNumeric($plannedWork);

$comment=RequestHandler::getValue('assignmentComment',true); 
//$comment=htmlEncode($comment);// Must not escape : will be done on display

$idOrigin=RequestHandler::getNumeric('assignedIdOrigin',false,null);

$optional = RequestHandler::getBoolean('attendantIsOptional');

$isTeam = RequestHandler::getBoolean('isTeam');
$isOrganization = RequestHandler::getBoolean('isOrganization');
$isResourceTeam = RequestHandler::getBoolean('isResourceTeam');

$mode = RequestHandler::getValue('mode');

//gautier #resourceTeam
$etp = RequestHandler::getNumeric('assignmentCapacity');

$planningMode=null;
$obj=new $refType($refId);
$peName=$refType.'PlanningElement';
if (property_exists($obj, $peName)) {
  $idPm=$obj->$peName->idPlanningMode;
  $pmObj=new PlanningMode($idPm);
  $planningMode=$pmObj->code;
}
$assRec=array();
if ($planningMode=='RECW') {
  for ($i=1;$i<=7;$i++) $assRec[$i]=RequestHandler::getValue('recurringAssignmentW'.$i);
}
$idle=RequestHandler::getBoolean('assignmentIdle');

$assignment=new Assignment();
$result=null;

$resourceList=array($idResource=>$idResource);
if($isTeam){
  $crit = array('idTeam'=>$idResource);
  $resourceList = SqlList::getListWithCrit('Resource', $crit);
}
if($isOrganization){
  $crit = array('idOrganization'=>$idResource);
  $resourceList = SqlList::getListWithCrit('Resource', $crit);
}
$res = new ResourceAll($idResource);

if ($isResourceTeam){

    $crit = array('idResourceTeam'=>$idResource);
    $rta=new ResourceTeamAffectation();
    if($refType=='Meeting' or $refType=='PeriodicMeeting' or $refType=='PokerSession'){
      if($refType=='Meeting'){
        $date=$obj->meetingDate;
      }else if($refType=='PeriodicMeeting'){
        $date=$obj->periodicityStartDate;
      }else{
        $date=$obj->pokerSessionDate;
      }
      $where="idResourceTeam = $idResource and (startDate <= '$date' or startDate IS NULL) and (endDate >= '$date'  or endDate IS NULL ) ";
       $list=$rta->getSqlElementsFromCriteria(null,null,$where);
    }else{
      $list=$rta->getSqlElementsFromCriteria($crit);
    }
    $resourceList = array();
    foreach ($list as $l){
        $resource = new ResourceAll($l->idResource);
        $resourceList[$resource->id] = $resource->name;
    }
}
Sql::beginTransaction();
if($planningMode == 'MAN' and $mode =='edit'){
  $assignment=new Assignment($assignmentId);
  $oldCost=$assignment->dailyCost;
  $assignment->idRole=$idRole;
  $assignment->comment=$comment;
  $assignment->dailyCost=$cost;
  $assignment->idle=intval(pq_trim($idle));
  if (! $oldCost or $assignment->dailyCost!=$oldCost) {
    $assignment->newDailyCost=$cost;
  }
  $result=$assignment->save();
  $result = i18n('Assignment').' #'.$assignmentId.' '.i18n("resultUpdated").'<input type="hidden" id="lastSaveId" value="'.$assignmentId.'" /><input type="hidden" id="lastOperation" value="update" /><input type="hidden" id="lastOperationStatus" value="OK" />';
}else{
  foreach ($resourceList as $idResource=>$name){
    // get the modifications (from request)
    $assignment=new Assignment($assignmentId);
    $res = new ResourceAll($idResource);
    $oldCost=$assignment->dailyCost;
    
    $assignment->refId=$refId;
    $assignment->refType=$refType;
    if (! $realWork && $idResource) {
      $assignment->idResource=$idResource;
    }
    // if it's a pool, affect role of resource in pool
    if(!pq_trim($idRole)){
      $assignment->idRole = $res->idRole;
    }else{
      $assignment->idRole=$idRole;
    }
    $assignment->dailyCost=$cost;
    if (! $oldCost or $assignment->dailyCost!=$oldCost) {
      $assignment->newDailyCost=$cost;
    }
    $resource = new ResourceAll($assignment->idResource);
    if($resource->isResourceTeam and !$unique){
      $assignment->capacity=$etp;
      $periods = ResourceTeamAffectation::buildResourcePeriods($idResource);
      $today=date('Y-m-d');
      $maxCapacity = 1;
      foreach ($periods as $p) {
        if($p['end']>$today and $maxCapacity < $p['rate']){
          $maxCapacity = $p['rate'];
        }
      }
      if (! $proportional) {
        $rate = ($etp/$maxCapacity)*100;
        if($rate > 100) $rate = 100;
      }
      $assignment->rate = $rate;
    }else{
      $assignment->rate=$rate;
    }

    $assignment->proportional=intval($proportional);
    $assignment->uniqueResource=($unique)?1:0;;
    $assignment->assignedWork=Work::convertWork($assignedWork);
    //$assignment->realWork=Work::convertWork($realWork); // Should not be changed here
    $assignment->leftWork=Work::convertWork($leftWork);
    $assignment->plannedWork=Work::convertWork($plannedWork);
    $assignment->idle=intval(pq_trim($idle));
    $assignment->comment=$comment;
    
    if (! $assignment->idProject) {
      $refObj=new $refType($refId);
      $assignment->idProject=$refObj->idProject;
    }
    
    if (! $oldCost and $cost and $assignment->realWork) {
    	$wk=new Work();
    	$where="idResource=" . Sql::fmtId($assignment->idResource);
    	$where.=" and idAssignment=" . $assignment->id ;
    	$where.=" and (cost=0 or cost is null) and work>0";
    	$wkList=$wk->getSqlElementsFromCriteria(null, false, $where);
    	foreach ($wkList as $wk) {
    		$wk->dailyCost=$cost;
    		$wk->cost=$cost*$wk->work;
    		$wk->save();
    	}
    	$assignment->realCost=$assignment->realWork*$assignment->dailyCost;
    }
    if(isset($optional)){
      $assignment->optional=$optional;
    }
    if ($idOrigin) {
      $assignment->_origin=$idOrigin;
    }
    $resultTmp=$assignment->save();
    if (!isset($result) or !$result) $result=$resultTmp;
    if($assignedChangeStatus and $refreshObj=='false' and pq_strpos($result, "_refreshStatusObject")!==false){
      $refreshObj='true';
      $result=pq_substr($result,0,pq_strpos($result, "_refreshStatusObject"));
    }
    
    // 
    //$ar=new AssignmentRecurring();
    if ($planningMode=='RECW') {
      for ($i=1;$i<=7;$i++) {
        $res='';
        $ar=SqlElement::getSingleSqlElementFromCriteria('AssignmentRecurring', array('idAssignment'=>$assignment->id, 'day'=>$i));
        if (!$assRec[$i]) {
          if ($ar->id) $res=$ar->delete();
        } else {
          $ar->idAssignment=$assignment->id;
          $ar->type=pq_substr($planningMode,-1);
          $ar->day=$i;
          $ar->value=Work::convertWork($assRec[$i]);
          $ar->refType=$refType;
          $ar->refId=$refId;
          $ar->idResource=$idResource;
          $res=$ar->save();
        }
        if (getLastOperationStatus($result)=='NO_CHANGE' and getLastOperationStatus($res)=='OK') {
          $result=pq_str_replace('NO_CHANGE', 'OK', $result);
          $result=i18n("Assignment").' #'.htmlEncode($assignment->id).' '.i18n('resultUpdated').pq_substr($result,pq_strpos($result,'<input'));
        }
      }
    } else {
      $ar=new AssignmentRecurring();
      if ($assignment->id) $ar->purge("idAssignment=$assignment->id");
    }
    
    $elt=new $assignment->refType($assignment->refId);
    $mailResult=null;
    if ($assignmentId) {
      $mailResult=$elt->sendMailIfMailable(false,false,false,false,false,false,false,false,false,false,true,false);
    } else {
      $mailResult=$elt->sendMailIfMailable(false,false,false,false,false,false,false,false,false,true,false,false);
    }
    if ($mailResult) {
      $pos=pq_strpos($result,'<input type="hidden"');
      if ($pos) {
        $result=pq_substr($result, 0,$pos).' - ' . Mail::getResultMessage($mailResult).pq_substr($result, $pos);
      }
    }
    if ($refType=='Meeting' or $refType=='PeriodicMeeting') {
      Meeting::removeDupplicateAttendees($refType, $refId);
    }
    if ($refType=='Meeting') {
      $meeting = new Meeting($refId);
      $meetTable=$meeting->getDatabaseTableName();
      $critWhere = "refType = 'Meeting'";
      $critWhere .= " and idResource=$idResource ";
      $critWhere .= " and refId <> $refId";
      $critWhere .= " and refId in (Select id From $meetTable meet where ";
      $critWhere .= " ( meet.meetingStartDateTime between '".  $meeting->meetingStartDateTime . "' and '" . $meeting->meetingEndDateTime ."'";
      $critWhere .= " or meet.meetingEndDateTime between '" . $meeting->meetingStartDateTime . "' and '" . $meeting->meetingEndDateTime ."' ) )";
      $tmpAss=new Assignment();
      $countSame = $tmpAss->countSqlElementsFromCriteria(null,$critWhere);
      if ($countSame > 0) {
        $result .= '</br>'. i18n('resourceAlreadyTaken', array(SqlList::getNameFromId('Affectable', $idResource)));
        $result=pq_str_replace('id="lastOperationStatus" value="OK"','id="lastOperationStatus" value="INCOMPLETE"',$result);
      }
    }
    
    if ($idOrigin){
      $assignmentOrigin = new Assignment($idOrigin);
        $assignmentOrigin->assignedWork=$assignmentOrigin->assignedWork-Work::convertWork($assignedWork);
        if ($assignmentOrigin->assignedWork<0) $assignmentOrigin->assignedWork=0;
        $assignmentOrigin->leftWork=$assignmentOrigin->leftWork-Work::convertWork($leftWork);
        if ($assignmentOrigin->leftWork<0) $assignmentOrigin->leftWork=0;
        $assignmentOrigin->save();
    }
      
    // If uniquerResource, store list of resources
    if ($assignment->isResourceTeam and $assignment->uniqueResource) {
      $userSelected=RequestHandler::getValue("dialogAssignmentManualSelect");
      $res=AssignmentSelection::addResourcesFromPool($assignment->id,$assignment->idResource,$userSelected);
      if (getLastOperationStatus($result)=='NO_CHANGE' and $res and getLastOperationStatus($res)=='OK') {
        $result=$res;
      } 
    }
    if ($definitive) {
      $assSel=new AssignmentSelection();
      $assSel->purge("idAssignment=$assignment->id");
    }
  }
  echo '<input id="idAssignment" name="idAssignment" type="hidden" value="'.$assignment->id.'"/>';
}
$status = getLastOperationStatus($result);
if ($result==null) {
  echo '<div class="messageNO_CHANGE" >'.i18n("messageNoChange").' '.i18n("Assignment").'</div>';
  echo '<input id="lastOperationStatus" name="lastOperationStatus" type="hidden" value="NO_CHANGE"/>';
} else {
  if($assignedChangeStatus){
    echo '<input id="refreshObjectAfterAssigned" name="refreshObjectAfterAssigned" type="hidden" value="'.$refreshObj.'"/>';
  }
   echo '<input id="lastOperationStatus" name="lastOperationStatus" type="hidden" value="'.$status.'"/>';
   echo '<input id="savedAssignment" name="savedAssignment" type="hidden" value="1"/>';
   displayLastOperationStatus($result);
}
$saveResponse=ob_get_clean();
setSessionValue('lastSavedObject',array(
  'objectClass'=>'Assignment',
  'objectId'=>$assignment->id
));
setSessionValue('lastSaveResult',$saveResponse);
session_write_close();
echo $saveResponse;
?>
