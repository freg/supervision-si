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

/** ============================================================================
 * Save real work allocation.
 */

require_once "../tool/projeqtor.php";
$status="NO_CHANGE";
$errors="";
$finalResult="";
Assignment::$_skipRightControl=true;
debugTraceLog('   saveImputation for user #'.$_REQUEST['userId'].' | range '.$_REQUEST['rangeType'].' '.$_REQUEST['rangeValue'].' | nb fields='.count($_POST, COUNT_RECURSIVE).' | nb lines='.count($_POST['idAssignment']));
if (!isset($_REQUEST['nbLines'])) {
  traceLog('WARNING - all lines are not retrieved from screen');
  traceLog('        - Maybe max_input_vars is too small in php.ini (actual value is '.ini_get('max_input_vars').')');
  traceLog('        - current number of Post Fields retreived = '.count($_POST, COUNT_RECURSIVE));
  traceLog('        - user #'.$_REQUEST['userId'].' | range '.$_REQUEST['rangeType'].' '.$_REQUEST['rangeValue']);
  traceLog('        - number of lines on timesheet = '.count($_POST['idAssignment']));
  trigger_error('Error - too many fields to save for '.count($_POST['idAssignment']).' lines',E_USER_ERROR);
  exit;
}
$rangeType=$_REQUEST['rangeType'];
$rangeValue=$_REQUEST['rangeValue'];
$userId=$_REQUEST['userId'];
$nbLines=$_REQUEST['nbLines'];
if ($rangeType=='week') {
  $nbDays=7;
} else if ($rangeType=='day') {
  $nbDays=1;
} else if ($rangeType=='month') {
  $nbDays=lastDayOfMonth(intval(pq_substr($rangeValue,4)),intval(pq_substr($rangeValue,0,4)));
}
// Save main comment
if (isset($_REQUEST['imputationComment'])) {
	$comment=$_REQUEST['imputationComment'];
	$period=new WorkPeriod();
  $crit=array('idResource'=>$userId, 'periodRange'=>$rangeType,'periodValue'=>$rangeValue);
  $period=SqlElement::getSingleSqlElementFromCriteria('WorkPeriod', $crit);
  $period->comment=$comment;
  $result=$period->save();
  if (pq_stripos($result,'id="lastOperationStatus" value="ERROR"')>0 ) {
    $status='ERROR';
    $finalResult=$result;
  } else if (pq_stripos($result,'id="lastOperationStatus" value="OK"')>0 ) {
    $status='OK';
  } else { 
    if ($finalResult=="") {
      $finalResult=$result;
    }
  }
}
PlanningElement::$_noDispatch='needReplan'; // FOR TESTS ONLY
$arrayPeToRefresh=array();
$arrayAssToSave=array();
$tooSoon=false;
$assignmentObj=null;
// Control maxPerDay and maxPerWeek =================================

$resource=new Resource($userId);
$workDayArray=array();
for ($j=1; $j<=$nbDays; $j++) {$workDayArray[$j]=0;}
$workWeek=0;
$w=new Work;
$firstDay=$_REQUEST['day_1'];
$lastDay=$_REQUEST['day_' .$nbDays];
$msg="";
if ($resource->maxDailyWork or $resource->maxWeeklyWork) {
  for ($i=0; $i<$nbLines; $i++) {
    for ($j=1; $j<=$nbDays; $j++) {
      $workValue=Work::convertImputation($_REQUEST['workValue_'.$j][$i]);
      $workWeek+=$workValue;
      $workDayArray[$j]+=$workValue;
    }
  }
}
if ($resource->maxDailyWork>0) {
  for ($j=1; $j<=$nbDays; $j++) {
    if (round($workDayArray[$j],2)>round($resource->maxDailyWork,2)) {
      $status='INVALID';
      $msg.=i18n('maxDailyWorkError',array(Work::displayImputationWithUnit($resource->maxDailyWork))).'<br/>';
      break;
    }
  }
}
$year=pq_substr($rangeValue,0,4);
$week=pq_substr($rangeValue,4);
if (! is_numeric($year) or ! is_numeric($week)) {
  $status='INVALID';
  $msg.=i18n('invalidDate'). " '$rangeValue' <br/>";
}
if ($resource->maxWeeklyWork>0) {
  if ($rangeType=='week'){
    if (round($workWeek,2)>round($resource->maxWeeklyWork,2)) {
      $status='INVALID';
      $msg.=i18n('maxWeeklyWorkError',array(Work::displayImputationWithUnit($resource->maxWeeklyWork))).'<br/>';
    } 
  }
  else if ($rangeType=='month'){
    $workMonth=array();
    
    for ($i=0; $i<$nbLines; $i++) {
      for ($j=1; $j<=$nbDays; $j++) {
        $workVal=Work::convertImputation($_REQUEST['workValue_'.$j][$i]);
        $dayDate=RequestHandler::getDatetime('day_'.$j);
        if (!isset($workMonth[$dayDate])) {
            $workMonth[$dayDate] = 0;
        }
        $workMonth[$dayDate] += $workVal;
      }
    }
   
    $firstWeekday = date('N', strtotime($firstDay));
    if ($firstWeekday != 1){
      $previousWeek = date('oW', strtotime($firstDay));
      $work = new Work();
      $existingDays = array_keys($workMonth);
      $where = "idResource=" . $resource->id . " AND week='$previousWeek' AND workDate NOT IN ('" . implode("','", $existingDays) . "')";
      $listWork = $work->getSqlElementsFromCriteria(null, null, $where);
      foreach ($listWork as $wk){
        $workDate = $wk->workDate;
        $workValue = $wk->work;
        if (!isset($workMonth[$workDate])) {
          $workMonth[$workDate] = 0;
        }
        $workMonth[$workDate] += Work::convertImputation($workValue);
      }
    }
    $lastWeekDay = date('N', strtotime($lastDay));
    if ($lastWeekDay != 7){
      $finalWeek = date('oW', strtotime($lastDay));
      $work = new Work();
      $existingDays = array_keys($workMonth);
      $where = "idResource=" . $resource->id . " AND week='$finalWeek' AND workDate NOT IN ('" . implode("','", $existingDays) . "')";
      $listWork = $work->getSqlElementsFromCriteria(null, null, $where);
      foreach ($listWork as $wk){
        $workDate = $wk->workDate;
        $workValue = $wk->work;
        if (!isset($workMonth[$workDate])) {
          $workMonth[$workDate] = 0;
        }
        $workMonth[$workDate] += Work::convertImputation($workValue);
      }
    }
    $weeks = [];
    $weekMondays = [];
    foreach ($workMonth as $date => $work) {
      $weekNumber = date('o-W', strtotime($date));
      $mondayDate = date('Y-m-d', strtotime($date));
      if (!isset($weeks[$weekNumber])) {
        $weeks[$weekNumber] = 0;
        $weekMondays[$weekNumber] = $mondayDate;
      }
      $weeks[$weekNumber] += $work;
    }

    $problemWeeks = [];
    foreach ($weeks as $week => $totalWork) {
      if (round($totalWork,2) > round($resource->maxWeeklyWork,2)) {
        $problemWeeks[$week] = $totalWork;
      }
    }

    if (!empty($problemWeeks)) {
      $status='INVALID';
      $msg.=i18n('maxWeeklyWorkError', [Work::displayImputationWithUnit($resource->maxWeeklyWork)]) . '<br/>';
      foreach ($problemWeeks as $week => $workSum) {
        $mondayDate = dateFormatter($weekMondays[$week]);
        $msg.= i18n("weekExceedsLimit",array($mondayDate,Work::displayImputationWithUnit($workSum))) . '<br/>';
      }
    }
   }
  
}
if ($status=='INVALID') {
  echo '<div class="message'.$status.'" >' . $msg . '</div>';
  echo '<input type="hidden" id="lastOperation" value="save" name="lastOperation">';
  echo '<input type="hidden" id="lastOperationStatus" value="' . $status .'" name="lastOperationStatus">';
  exit;
}
// ========================================================
$manualPlanned=getManualPlanned($firstDay,$lastDay,$userId);
$savedReal=array();
$wk=new Work();
$firstDayAsDay=pq_str_replace('-','',$firstDay);
$lastDayAsDay=pq_str_replace('-','',$lastDay);
$wkList=$wk->getSqlElementsFromCriteria(null,null,"idResource=$userId and day>='$firstDayAsDay' and day<='$lastDayAsDay'");
$arrayWorkItem=array();
foreach ($wkList as $wk){
  $key="$wk->idAssignment|$wk->workDate|$wk->idWorkElement|$wk->idResource";
  $arrayWorkItem[$key]=$wk;
}
Sql::beginTransaction();
for ($i=0; $i<$nbLines; $i++) {
	$imputable=$_REQUEST['imputable'][$i];
  $locked=$_REQUEST['locked'][$i];
  $planAct=$_REQUEST['planAct'][$i];
  $leftChanged=$_REQUEST['leftChanged'][$i];
  $changed=false;
  if ( ($imputable and ! $locked) or $planAct) {
    $line=new ImputationLine();
    $line->idAssignment=$_REQUEST['idAssignment'][$i];
    if (isset($_REQUEST['idWorkElement_'.($i+1)])) {
      $line->idWorkElement=$_REQUEST['idWorkElement_'.($i+1)];
    }
    $ass=new Assignment($line->idAssignment);
    $line->idResource=$userId;
    if ($ass->id) {
      $line->refType=$ass->refType;
      $line->refId=$ass->refId;    
      $line->idProject=$ass->idProject;
    } else if ($line->idWorkElement) {
      $we=new WorkElement($line->idWorkElement);
      $line->refType=$we->refType;
      $line->refId=$we->refId;
      $line->idProject=$we->idProject;
    }
    if (isset($_REQUEST['leftWork'][$i])) {
      $line->leftWork=Work::convertImputation($_REQUEST['leftWork'][$i]);
    } else {
    	traceLog('WARNING - Left work not retrieved from screen');
    	traceLog('        - Maybe max_input_vars is too small in php.ini (actual value is '.ini_get('max_input_vars').')');
    	traceLog('        - Assignment #'.$ass->id.' on '.$ass->refType.' #'.$ass->refId.' for resource #'.$ass->idResource. ' - '.SqlList::getNameFromId('Resource',$ass->idResource));
    	trigger_error('Error - Maybe max_input_vars is too small in php.ini',E_USER_ERROR);
    }
    if ($locked and $planAct and $ass->id) {
      $ass->leftWork=$line->leftWork;
      $arrayAssToSave[]=$ass;
      continue;
    }
    $line->imputable=$imputable;
    $line->isPlanningActivity=$planAct;
    $realWorkDiffTot=0;
    $arrayWork=array();
    for ($j=1; $j<=$nbDays; $j++) {
      $realWorkDiff=0;
    	$workId=null;
    	if (pq_array_key_exists('workId_' . $j, $_REQUEST)) {
        $workId=$_REQUEST['workId_' . $j][$i];
    	}
      $workValue=Work::convertImputation($_REQUEST['workValue_'.$j][$i]);
      $workDate=$_REQUEST['day_' . $j];
      if ($workId and $workId!='x') {
        $work=new Work($workId);
      } else {
//         $crit=array('idAssignment'=>$line->idAssignment,
//                     'workDate'=>$workDate, 'idWorkElement'=>null , 'idResource'=>$line->idResource);
//         if ($line->idWorkElement) {
//           $crit['idWorkElement']=$line->idWorkElement;
//         }
        $key="$line->idAssignment|$workDate|$line->idWorkElement|$line->idResource";
//
//        $work=SqlElement::getSingleSqlElementFromCriteria('Work', $crit);
        $work=$arrayWorkItem[$key]??(new Work()); 
      }
      if (!isset($savedReal[$workDate])) $savedReal[$workDate]=0;
      $savedReal[$workDate]+=$workValue;
      if($workValue != 0){
        if((!$ass->realWork or $ass->realWork == 0) and $workDate < $ass->plannedStartDate){
          $tooSoon=true;
          $assignmentObj=$ass;
          $objWorkDate=$workDate;
          $objWorkValue=$workValue;
        }
      } 
      $realWorkDiff=$workValue-$work->work;
      $realWorkDiffTot+=$realWorkDiff;
      if ($workId=='x') {
        $crit=array('idAssignment'=>$line->idAssignment,
            'workDate'=>$workDate, 'idResource'=>$line->idResource);
        $key="$line->idAssignment|$workDate|$line->idResource";
        $plannedWork=SqlElement::getSingleSqlElementFromCriteria('PlannedWork', $crit);
        if ($plannedWork and $plannedWork->id) {
          $resPlan=$plannedWork->delete();
          $statPlan=getLastOperationStatus($resPlan);
          if ($statPlan=='OK') $changed=true;
        }
      }
      $arrayWork[$j]=$work;
      $arrayWork[$j]->work=$workValue;
      $arrayWork[$j]->idResource=$userId;
      $arrayWork[$j]->idProject=$line->idProject;
      $arrayWork[$j]->refType=$line->refType;
      $arrayWork[$j]->refId=$line->refId;
      $arrayWork[$j]->idAssignment=$line->idAssignment;   
      if ($line->idWorkElement) $arrayWork[$j]->idWorkElement=$line->idWorkElement;
      $arrayWork[$j]->setDates($workDate);
    }
    $line->arrayWork=$arrayWork;
    $result=$line->save();
    $stat=($result)?getLastOperationStatus($result):'NO_CHANGE';
    if ($stat=="ERROR" or $stat=="INVALID") {
      $status='ERROR';
      $finalResult=$result;
      break;
    } else if ($stat=="OK") {
      $status='OK';
      $changed=true;
    } else { 
      if ($finalResult=="") {
        $finalResult=$result;
      }
    }
    $pe=SqlElement::getSingleSqlElementFromCriteria('PlanningElement', array("refType"=>$ass->refType,"refId"=>$ass->refId));
    if($pe->idPlanningMode=="23"){
      $crit=array('refType'=>$line->refType, 'refId'=>$line->refId, 'idResource'=>$line->idResource);
      $pw= new PlannedWork();
      $w=new Work();
      $realwork=$w->sumSqlElementsFromCriteria('work', $crit);
      $plannedwork=$pw->sumSqlElementsFromCriteria('work', $crit);
      if ($plannedwork!=$ass->leftWork) $changed=true;
      $ass->leftWork=$plannedwork;
      $ass->assignedWork=$plannedwork+$realwork;
    }
    if (! $line->idWorkElement) {
      if ($ass->leftWork!=$line->leftWork and $leftChanged) {
      	$changed=true;
      	$ass->leftWork=$line->leftWork;
      }
    } else {
      if ($realWorkDiffTot!=0) {
        $changed=true;
        $ass->leftWork-=$realWorkDiffTot;
        if ($ass->leftWork<0) $ass->leftWork=0; 
      }
    }
    if ($changed) {
       if ($ass->id) {
//          if(Parameter::getGlobalParameter('displayPoolsOnImputation') == 'NO' and Parameter::getGlobalParameter('autoUpdateLeftWorkOnPool') == 'YES'){
//            $assignWork = $ass->assignedWork;
//            $realWork = $ass->realWork;
//            if(($assignWork <= $realWork) || ($assignWork <= $realWork+$realWorkDiffTot) && $line->leftWork <= 0){
//              $rta = ResourceTeamAffectation::getSingleSqlElementFromCriteria('ResourceTeamAffectation', array('idResource'=>$ass->idResource, 'idle'=>'0'));
//              if($rta->id){
//                $poolAss = Assignment::getSingleSqlElementFromCriteria('Assignment', array('refType'=>$ass->refType, 'refId'=>$ass->refId, 'idResource'=>$rta->idResourceTeam));
//                if($poolAss->id){
//                  if($assignWork <= $realWork){
//                    $poolAss->leftWork -= $realWorkDiffTot;
//                  }else if($assignWork < ($realWork+$realWorkDiffTot)){
//                    $poolAss->leftWork -= abs(($assignWork-$realWork) - $realWorkDiffTot);
//                  }
//                  $arrayAssToSave[] = $poolAss;
//                }
//              }
//            }
//          }
         $resultAss=$ass->saveWithRefresh();
         $statAss=($resultAss)?getLastOperationStatus($resultAss):'';
       } else {
         $statAss="";
         $resultAss="";
       }
       if ($statAss=="OK") $arrayPeToRefresh[$ass->refType.'#'.$ass->refId]=array('refType'=>$ass->refType, 'refId'=>$ass->refId);
       if ($statAss=="OK" or $statAss=='NO_CHANGE') { // NO_CHANGE means work was changed, but not assignment (Ex : -1 day 1, +1 day 2)
       	$status='OK';
       } else if ($statAss=="INVALID"){
       	$status='INVALID';
       	$finalResult=$resultAss;
       	break;
       } else if ($statAss=="ERROR"){
       	$status='ERROR';
       	$finalResult=$resultAss;
       	break;
       }
       // PBER - V9.2 : will slightly increase time to save, but will unlock items to avoid deadlocks
       Sql::commitTransaction();
       Sql::beginTransaction();
    }
  }
}
foreach ($arrayAssToSave as $ass) {
    $resultAss=$ass->saveWithRefresh();
    $statAss=($resultAss)?getLastOperationStatus($resultAss):'';
    if ($statAss=="OK") {
      $arrayPeToRefresh[$ass->refType.'#'.$ass->refId]=array('refType'=>$ass->refType, 'refId'=>$ass->refId);
      $changed=true;
      if ($status=='NO_CHANGE') $status='OK'; // Just saved Left for Planning Activity. Must to treat as OK to commit;
    }
    Sql::commitTransaction();
    Sql::beginTransaction();
}
purgeManualPlanned($savedReal,$manualPlanned,$resource);

if ($status=='ERROR') {
	Sql::rollbackTransaction();
  echo '<div class="messageERROR" >' . $finalResult . '</div>';
}else if ($status=='INVALID') {
	Sql::rollbackTransaction();
  echo '<div class="messageINVALID" >' . $finalResult . '</div>';
} else if ($status=='OK'){ 
	Sql::commitTransaction();
  echo '<div class="messageOK" >' . i18n('messageImputationSaved') . '</div>';
  checkSendAlert($userId,$rangeValue, 'imputationAlertInputByOther');
  if($tooSoon){
    checkSendAlert($userId,$rangeValue, 'imputationAlertWorkTooSoon', $assignmentObj, $objWorkDate, $objWorkValue);
  }
} else {
  Sql::rollbackTransaction(); // IMORTANT NOTICE : DUE TO INTERMEDIATE COMMITS, THIS ROLLBACK MAY ONLY ROLLBACK LAST TRANSACTION 
  echo '<div class="messageNO_CHANGE" >' . i18n('messageNoImputationChange') . '</div>';
}
echo '<input type="hidden" id="lastOperation" value="save" name="lastOperation">';
echo '<input type="hidden" id="lastOperationStatus" value="' . $status .'" name="lastOperationStatus">';
flush(); // PBER #8054 #11874 - give response to user before consolidation

$arrayTodo=fillWithParent($arrayPeToRefresh);
if ($status=='OK'){
  //PlanningElement::$_noDispatch=false;
  foreach ($arrayTodo as $ref) {
    Sql::beginTransaction();
    $res=PlanningElement::updateSynthesis($ref['refType'], $ref['refId']);
    if (getLastOperationStatus($res)=='OK') {
      // PBER - V9.2 : will slightly increase time to save, and may bring slight unconsistency, but will unlock items to avoid deadlocks
      Sql::commitTransaction();
    } else {
      Sql::rollbackTransaction();
    }
  }
}


function checkSendAlert($userId,$periodValue,$paramCode,$assignmentObj=null, $objWorkDate=null, $objWorkValue=null) {
  $param=Parameter::getGlobalParameter($paramCode);  
  $currentUser=getSessionUser();
  if ($paramCode == 'imputationAlertInputByOther' and $userId==$currentUser->id) return;
  if (!pq_trim($param) or $param=='NO' or $param=='NONE') return;
  $name=($currentUser->resourceName)?$currentUser->resourceName:$currentUser->name;
  $name='"'.$name.'"';
  $periodValue=pq_substr($periodValue,0,4).'-'.pq_substr($periodValue,4);
  $obj = null;
  if($paramCode == 'imputationAlertInputByOther'){
    $alertSendTitle=i18n('messageAlertImputationByOtherTitle');
    $alertSendMessage=i18n('messageAlertImputationByOtherBody',array($name,$periodValue));
  }else{
    $obj = new $assignmentObj->refType($assignmentObj->refId,true);
    $alertSendTitle=i18n('messageAlertImputationWorkTooSoonTitle', array($name, $assignmentObj->refType, $assignmentObj->refId));
    $alertSendMessage=i18n('messageAlertImputationWorkTooSoonBody',array($name, Work::displayWorkWithUnit($objWorkValue), htmlFormatDate($objWorkDate))).
    "<br/>&nbsp;&nbsp;&nbsp;<a href='". $obj->getReferenceUrl() ."' target='#' >". i18n ( $assignmentObj->refType ) ." #". htmlEncode ( $assignmentObj->refId ) ."</a><br/>&nbsp;&nbsp;&nbsp;".$obj->name;
  }
  $idResourceTab = array();
  if($paramCode == 'imputationAlertWorkTooSoon'){
    $profile=new Profile();
    $listIdProfile = array();
    $listProfile=$profile->getSqlElementsFromCriteria(array('profileCode'=>'PL'));
    foreach ($listProfile as $profile) {
    	$listIdProfile[$profile->id]=$profile->id;
    }
    $aff=new Affectation();
    $where=' idProject ='.$assignmentObj->idProject.' and idProfile in '.transformListIntoInClause($listIdProfile);
    $affListIdResource=$aff->getSqlElementsFromCriteria(null, false, $where);
    foreach ($affListIdResource as $affRes) {
    	$idResourceTab[$affRes->idResource]=$affRes->idResource;
    }
  }else{
    $idResourceTab[$userId]=$userId;
  }
  foreach ($idResourceTab as $idResource){
    if($idResource==$currentUser->id)continue;
    if ($param=='ALERT' or $param=='ALERT&MAIL') {
    	$alertSendType='WARNING';
    	$alert=new Alert();
    	$alert->idUser=$idResource;
    	$alert->alertType=$alertSendType;
    	if($paramCode == 'imputationAlertWorkTooSoon')$alert->idProject=$assignmentObj->idProject;
    	if($paramCode == 'imputationAlertWorkTooSoon')$alert->refId=$assignmentObj->refId;
    	if($paramCode == 'imputationAlertWorkTooSoon')$alert->refType=$assignmentObj->refType;
    	$alert->alertInitialDateTime=date('Y-m-d H:i:s');
    	$alert->alertDateTime=date('Y-m-d H:i:s');
    	$alert->title=pq_mb_substr($alertSendTitle,0,100);
    	$alert->message=$alertSendMessage;
    	$result=$alert->save();
    }
    if ($param=='MAIL' or $param=='ALERT&MAIL') {
    	$to=SqlList::getFieldFromId('User', $idResource, 'email');
    	if (pq_trim($to)) {
    		$result=sendMail($to, '['.Parameter::getGlobalParameter('paramDbDisplayName').'] '.$alertSendTitle, $alertSendMessage, $obj);
    	}
    }
  }
}
function fillWithParent($arrayPeToRefresh) {
  $result=array();
  foreach ($arrayPeToRefresh as $ref) {
    $pe=SqlElement::getSingleSqlElementFromCriteria('PlanningElement',array('refType'=>$ref['refType'], 'refId'=>$ref['refId']),true);
    $result[$pe->wbsSortable]=$ref;
    while ($pe->topRefType and $pe->topRefId) {
      $pe=SqlElement::getSingleSqlElementFromCriteria('PlanningElement',array('refType'=>$pe->topRefType, 'refId'=>$pe->topRefId),true);
      $result[$pe->wbsSortable]=array('refType'=>$pe->refType, 'refId'=>$pe->refId);
    }
  }
  krsort($result);
  return $result;
}
function getManualPlanned($start,$end,$userId) {
  $crit="workDate>='$start' and workDate<='$end' and idResource=$userId and isManual=1";
  $pw=new PlannedWork();
  $lst=$pw->getSqlElementsFromCriteria(null,null,$crit);
  $result=array();
  foreach($lst as $pw) {
    if (! isset($result[$pw->workDate]) ) $result[$pw->workDate]=array('total'=>0);
    $result[$pw->workDate][]=$pw;
    $result[$pw->workDate]['total']+=$pw->work;
  }
  return $result;
}
function purgeManualPlanned($realArray,$manualArray,$resource) {
  foreach ($manualArray as $date=>$manual) {
    if (isset($realArray[$date])) {
      $capacity=$resource->getCapacityPeriod($date);
      $real=$realArray[$date];
      $toremove=$real+$manual['total']-$capacity;
      if ($toremove>0) {
        foreach($manual as $man) {
          if (! is_object($man)) continue;
          if ($man->work>$toremove) {
            $man->work-=$toremove;
            $resSav=$man->save();
            $toremove=0;
          } else {
            $toremove-=$man->work;
            $resDel=$man->delete();
          }
          if ($toremove<=0) break;
        }
      }
    }
  }
}
?>
