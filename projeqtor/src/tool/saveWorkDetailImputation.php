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
require_once "../tool/projeqtor.php";
scriptLog('   ->/tool/saveWorkDetailImputation.php');

$idWork = RequestHandler::getId('idWorkForWorkDetail');
$workValue = RequestHandler::getValue('dispatchWorkImputationValue');

$idWorkCategory = RequestHandler::getValue('dispatchWorkImputation');
$uncertainties = RequestHandler::getValue('uncertaintiesDispatchWorkImputation');
$progress = RequestHandler::getValue('progressDispatchWorkImputation');

$idWorkDetail = RequestHandler::getValue('idWorkDetail');
$idWorkDetail = explode(',', $idWorkDetail);

$idAssignment = RequestHandler::getId('idAssignment');
$idResource = RequestHandler::getId('idResource');
$idProject = RequestHandler::getId('idProject');
$curDate=RequestHandler::getDatetime('curDate');
$refType = RequestHandler::getValue('refType');
$refId = RequestHandler::getValue('refId');
$countLine = count($workValue);

$assignment = new Assignment($idAssignment);
$status="";
$msg="";
$week = date('oW', strtotime($curDate));
$day = date('Ymd', strtotime($curDate));

// Control maxPerDay and maxPerWeek =================================
$resource=new Resource($idResource);
$workDayArray=array();
$workTime= 0;
foreach ($workValue as $value) {
  $valueConvert = Work::convertImputation(floatval($value));
  $workTime += $valueConvert;
}

if ($resource->maxDailyWork>0) {
  if (round($workTime,2)>round($resource->maxDailyWork,2)) {
    $status='INVALID';
    $msg.=i18n('maxDailyWorkError',array(Work::displayImputationWithUnit($resource->maxDailyWork))).'<br/>';
  }
}

if ($resource->maxWeeklyWork>0) {
  $work = new Work();
  $where = "idResource=" . $resource->id . " AND week='$week'";
  $listWork = $work->getSqlElementsFromCriteria(null,null,$where);
  $workWeek = $workTime;
  foreach ($listWork as $wk){
    if ($wk->day != $day){
      $workWeek += Work::convertImputation($wk->work);
    }
  }
  if (round($workWeek,2)>round($resource->maxWeeklyWork,2)) {
    $status='INVALID';
    $msg.=i18n('maxWeeklyWorkError',array(Work::displayImputationWithUnit($resource->maxWeeklyWork))).'<br/>';
  }
}
if ($status=='INVALID') {
  echo '<div class="message'.$status.'" >' . $msg . '</div>';
  echo '<input type="hidden" id="lastOperation" value="save" name="lastOperation">';
  echo '<input type="hidden" id="lastOperationStatus" value="' . $status .'" name="lastOperationStatus">';
  exit;
}
// ========================================================

Sql::beginTransaction();
$result="";
$res = "";

$existingWork = 0;
if ($idWork != null) {
  $existingWorkObj = new Work($idWork);
  $existingWork = $existingWorkObj->work;
}

$work = new Work();
if ($idWork != null) $work = new Work($idWork);
$work->idResource = $idResource;
$work->idProject = $idProject;
$work->refType = $refType;
$work->refId = $refId;
$work->idAssignment = $idAssignment;
$workTime= 0;
foreach ($workValue as $value) {
    $valueConvert = Work::convertImputation(floatval($value));
    $workTime += $valueConvert;
}
$work->work = $workTime;
$work->workDate = $curDate;
$work->day = $day;
$work->week = $week;
$work->month = date('Ym', strtotime($curDate));
$work->year = date('o', strtotime($curDate));
$res=$work->save(). '</br>';

$realWorkDiff = $workTime - $existingWork;

if ($workTime == 0) {
  $res = $work->delete() . '</br>';
  $realWorkDiff = -$existingWork;
}

if ($workTime == 0) $res = $work->delete() . '</br>';

for ($i = 0; $i < $countLine; $i++) { 
  if (isset($idWorkDetail[$i]) && !empty($idWorkDetail[$i])){
    $workDetail = new WorkDetail($idWorkDetail[$i]);
    if ($workValue[$i] == 0){
      $res .= $workDetail->delete(). '</br>';
    }else{
      $workDetail->work = Work::convertImputation($workValue[$i]);
      $workDetail->idwork = $work->id;
      $workDetail->idWorkCategory = $idWorkCategory[$i];
      $workDetail->uncertainties = $uncertainties[$i];
      $workDetail->progress = $progress[$i];
      $res .= $workDetail->save(). '</br>';
    }
  } else if ($workValue[$i] != 0) {
    $workDetail = new WorkDetail();
    $workDetail->work = Work::convertImputation($workValue[$i]);
    $workDetail->idwork = $work->id;
    $workDetail->idWorkCategory = $idWorkCategory[$i];
    $workDetail->uncertainties = $uncertainties[$i];
    $workDetail->progress = $progress[$i];
    $res .= $workDetail->save(). '</br>';
  }
}

$changed = false;
if ($realWorkDiff != 0) {
  $changed = true;
  $crit = array('refType' => $assignment->refType, 'refId' => $assignment->refId, 'idResource' => $assignment->idResource);
  $w = new Work();
  $totalRealWork = $w->sumSqlElementsFromCriteria('work', $crit);
  
  $assignment->leftWork = $assignment->assignedWork - $totalRealWork;
  if ($assignment->leftWork < 0) $assignment->leftWork = 0;
}

if ($changed && $assignment->id) {
  $resultAss = $assignment->saveWithRefresh();
  $statAss = ($resultAss) ? getLastOperationStatus($resultAss) : '';
  
  if ($statAss == "OK" || $statAss == 'NO_CHANGE') {
    $pe = SqlElement::getSingleSqlElementFromCriteria('PlanningElement',
        array("refType" => $assignment->refType, "refId" => $assignment->refId));
    if ($pe && $pe->id) {
      $resPe = PlanningElement::updateSynthesis($assignment->refType, $assignment->refId);
    }
  } else if ($statAss == "INVALID" || $statAss == "ERROR") {
    Sql::rollbackTransaction();
    echo '<div class="message' . $statAss . '" >' . $resultAss . '</div>';
    echo '<input type="hidden" id="lastOperation" value="save" name="lastOperation">';
    echo '<input type="hidden" id="lastOperationStatus" value="' . $statAss . '" name="lastOperationStatus">';
    exit;
  }
}

if (!$result) {
  $result=$res;
}

// Message of correct saving
displayLastOperationStatus($result);

?>
