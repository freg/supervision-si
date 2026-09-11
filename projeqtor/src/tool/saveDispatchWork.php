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
// Get the note info
if (! pq_array_key_exists('dispatchWorkObjectClass',$_REQUEST)) {
  throwError('dispatchWorkObjectClass parameter not found in REQUEST');
}
$refType=$_REQUEST['dispatchWorkObjectClass'];
Security::checkValidClass($refType);

if (! pq_array_key_exists('dispatchWorkObjectId',$_REQUEST)) {
  throwError('dispatchWorkObjectId parameter not found in REQUEST');
}
$refId=$_REQUEST['dispatchWorkObjectId'];

if (! pq_array_key_exists("dispatchWorkTotal",$_REQUEST) ) {
  throwError('dispatchWorkTotal parameter not found in REQUEST');
}
$total=Work::convertImputation($_REQUEST['dispatchWorkTotal']);

if (! pq_array_key_exists('dispatchWorkDate',$_REQUEST)) {
  throwError('dispatchWorkDate parameter not found in REQUEST');
}
$dateList=$_REQUEST['dispatchWorkDate'];

if (! pq_array_key_exists('dispatchWorkResource',$_REQUEST)) {
  throwError('dispatchWorkResource parameter not found in REQUEST');
}
$resourceList=$_REQUEST['dispatchWorkResource'];

if (! pq_array_key_exists('dispatchWorkValue',$_REQUEST)) {
  throwError('dispatchWorkValue parameter not found in REQUEST');
}
$valueList=$_REQUEST['dispatchWorkValue'];

if (! pq_array_key_exists('dispatchWorkId',$_REQUEST)) {
  throwError('dispatchWorkId parameter not found in REQUEST');
}
$workIdList=$_REQUEST['dispatchWorkId'];

if (! pq_array_key_exists('dispatchWorkElementId',$_REQUEST)) {
  throwError('dispatchWorkElementId parameter not found in REQUEST');
}
$weId=$_REQUEST['dispatchWorkElementId'];
$we=new WorkElement($weId);
$obj=new $refType($refId);
$moduleTokenManagementActive=false;
if(Module::isModuleActive('moduleTokenManagement') and RequestHandler::isCodeSet('tokenType')){
  $moduleTokenManagementActive=true;
  $tokenTime=RequestHandler::getValue('tokenTime');
  $tokenType=RequestHandler::getValue('tokenType');
  $tokenQuantityValue=RequestHandler::getValue('tokenQuantityValue');
  $tokenMarkupType=RequestHandler::getValue('tokenMarkupType');
  $tokenQuantityMarkupValue=RequestHandler::getValue('tokenQuantityMarkupValue');
  $billableToken=RequestHandler::getValue('billableTokenInput');
}

Sql::beginTransaction();
$saveDispatchMode=true;
$error=false;
$result=i18n("messageNoChange").' '.i18n("colRealWork").'<input type="hidden" id="lastSaveId" value="" /><input type="hidden" id="lastOperation" value="update" /><input type="hidden" id="lastOperationStatus" value="NO_CHANGE" />';
if ($we->realWork!=$total) {
  $we->realWork=$total;
  $resultWe=$we->save(true);
  $status = getLastOperationStatus ( $resultWe );
  if ($status=='OK') {
    $result=cleanResult($resultWe);
  } else if ($status=='ERROR') {
    $result=$resultWe;
    $error=true;
  }
  $result=cleanResult($resultWe);
}
$arrayResourceDate=array();
$arrayChanged=array();
foreach ($dateList as $idx=>$date) {
  if ($error) break;
  if ( (pq_trim($date) and isset($resourceList[$idx]) and pq_trim($resourceList[$idx])) or (isset($workIdList[$idx]) and $workIdList[$idx]) ) {
    $id=(isset($workIdList[$idx]))?$workIdList[$idx]:null;
    $work=new Work($id);
    $oldWork=new Work($id);
    if (pq_trim($date)) $work->setDates($date);
    if (isset($resourceList[$idx]) and pq_trim($resourceList[$idx])) $work->idResource=$resourceList[$idx];
    $work->idProject=$obj->idProject;
    if (! $work->refType) {
      if (property_exists($refType, 'idActivity') and $obj->idActivity) {
        $work->refType='Activity';
        $work->refId=$obj->idActivity;
      }else if (property_exists($refType, 'idSprint') and $obj->idSprint) {
        $work->refType='Sprint';
        $work->refId=$obj->idSprint;
      }else {
        $work->refType=$refType;
        $work->refId=$refId;
      }
    }
    $newWork=Work::convertImputation($valueList[$idx]);
    $diff=$newWork-$work->work;
    if ($diff>0) { 
      if (!isset($arrayChanged[$resourceList[$idx]])) $arrayChanged[$resourceList[$idx]]=array();
      if (!isset($arrayChanged[$resourceList[$idx]][$date])) $arrayChanged[$resourceList[$idx]][$date]=0;
      $arrayChanged[$resourceList[$idx]][$date]+=$diff;
    }
    $work->work=$newWork;
    $work->idWorkElement=$weId;
    $work->dailyCost=null; // set to null to force refresh 
    $work->cost=null;
//     $resWork=$work->save();
//     $status = getLastOperationStatus ( $resWork );
//     if ($status=='ERROR' or $status=='INVALID') {
//       $result=$resWork;
//       $error=true;
//       break;
//     }
    if ($work->idResource != $oldWork->idResource) {
      $oldAss=WorkElement::updateAssignment($oldWork, $oldWork->work*(-1));
      $diff=$newWork;
    }
    $ass=WorkElement::updateAssignment($work, $diff);
    $work->idAssignment=($ass)?$ass->id:null;
    $resWork="";
    if($oldWork->work!=$work->work or $work->idResource!=$oldWork->idResource or $oldWork->day!=$work->day 
    or $oldWork->refType!=$work->refType or $oldWork->refId!=$work->refId) {
      if ($work->work==0) {
        if ($work->id) {
          $resWork=$work->delete();
        }
//         if($moduleTokenManagementActive){
//           $workToken=SqlElement::getSingleSqlElementFromCriteria('WorkTokenClientContractWork', array('idWork'=>$work->id));
//           if($workToken->id)$workTokenRes=$workToken->delete();
//         }
      } else {
        $resWork=$work->save();
        $arrayResourceDate[$work->idResource.'#'.$work->workDate]=$work->id;
      }
    }
    if($moduleTokenManagementActive and $work->id  ){
      $workToken=SqlElement::getSingleSqlElementFromCriteria('WorkTokenClientContractWork', array('idWork'=>$work->id));
      $tokenOrdered=$tokenType[$idx];
      if($tokenOrdered!=""){
        if($tokenQuantityValue[$idx]==0 or $tokenQuantityValue[$idx]==""){
          $workTokenRes=$workToken->delete();
        }else{
          $date=new DateTime();
          $date->setTimestamp(pq_strtotime($tokenTime[$idx]));
          $pos=pq_strpos($tokenMarkupType[$idx], '_');
          $idWorkTokenMakup=pq_substr($tokenMarkupType[$idx],0,$pos);
          
          $workToken->time=$date->getTimestamp();
          $workToken->idWorkTokenClientContract=$tokenOrdered;
          $workToken->workTokenQuantity=$tokenQuantityValue[$idx];
          $workToken->workTokenMarkupQuantity=$tokenQuantityMarkupValue[$idx];
          $workToken->idWorkTokenMarkup=$idWorkTokenMakup;
          $workToken->billable=$billableToken[$idx];
          
          $workTokenRes=$workToken->save();
        }
      }else if($workToken->id){
        $workTokenRes=$workToken->delete();
      }
      $we->save(true);
    }
    if ($resWork) {
      $status = getLastOperationStatus ( $resWork );
      if ($status=='OK') {
        $result=cleanResult($resWork);
        
      } else if ($status=='ERROR' or $status=='INVALID') {
        $result=$resWork;
        $error=true;
        break;
      }
    }
    if($moduleTokenManagementActive and isset($workTokenRes)){
      $statusWt = getLastOperationStatus ( $workTokenRes );
      if ($statusWt=='OK') {
        $result=cleanResult($workTokenRes);
      
      } else if ($statusWt=='ERROR' or $statusWt=='INVALID') {
        $result=$workTokenRes;
        $error=true;
        break;
      }
    }
    if ($ass) $ass->saveWithRefresh(); // required to update cost
  }
}

// Check maxDailyWork and maxWeeklyWork
$w=new Work();
$msg='';
foreach ($arrayChanged as $idRes=>$dates) {
  $res=new Resource($idRes);
  if (!$res->maxDailyWork and ! $res->maxWeeklyWork) continue;
  if ($res->maxDailyWork) {
    foreach ($dates as $date=>$diff) {
      $sumDay=$w->sumSqlElementsFromCriteria('work', null, "idResource=$idRes and workDate='$date'");
      if ($sumDay>$res->maxDailyWork) {
        $msg.=$res->name." : ".i18n('maxDailyWorkError',array(Work::displayImputationWithUnit($res->maxDailyWork))).'<br/>';
      }
    }
  }
  if ($res->maxWeeklyWork) {
    $week=getWeekNumberFromDate($date);
    $sumDay=$w->sumSqlElementsFromCriteria('work', null, "idResource=$idRes and week='$week'");
    if ($sumDay>$res->maxWeeklyWork) {
      $msg.=$res->name." : ".i18n('maxWeeklyWorkError',array(Work::displayImputationWithUnit($res->maxWeeklyWork))).'<br/>';
    }
  }
  if ($msg!='') {
    $result='<div class="messageINVALID" >' . $msg . '</div>';
    $result.='<input type="hidden" id="lastOperation" name="lastOperation" value="save">';
    $result.='<input type="hidden" id="lastOperationStatus" name="lastOperationStatus" value="INVALID">';
  }
}
if (getLastOperationStatus($result)=='OK') ProjectPlanningElement::updateSynthesis('Project',$we->idProject);
// Message of correct saving
displayLastOperationStatus($result);
if (getLastOperationStatus($result)=='OK') {
  WaitingUpdate::flushAndExecuteWaiting();
}

function cleanResult($result) {
  return i18n('messageImputationSaved').pq_substr($result,pq_strpos($result,'<input'));
}
?>