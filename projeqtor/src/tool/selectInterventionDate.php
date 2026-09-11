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

$date=RequestHandler::getDatetime('date');
$resource=RequestHandler::getId('resource');
$period=RequestHandler::getValue('period');

$firstClickedDate=RequestHandler::getValue('firstClickedDate');
//$firstClickedDateAddOne=RequestHandler::getValue('firstClickedDateAddOne');
$shiftClickedDate=RequestHandler::getValue('shiftClickedDate');
//$shiftClickedDateMinusOne=RequestHandler::getValue('shiftClickedDateMinusOne');
$myfirstPeriod=RequestHandler::getValue('myfirstPeriod');

if ($period!='AM' and $period!='PM' and $period!='AMX' and $period!='PMX' and $period!='AMW' and $period!='PMW') {
  traceLog("saveInterventionDate.php incorrect period '$period'");
  exit;
}
$idMode=RequestHandler::getValue('idMode');
if ($idMode and ! is_numeric($idMode)) {
  traceLog("saveInterventionDate.php incorrect idMode '$idMode'");
  exit;
}
$letterMode=RequestHandler::getValue('letterMode');
if ($letterMode!='' and pq_strlen($letterMode)>3) {
  traceLog("saveInterventionDate.php incorrect letterMode '$letterMode'");
  exit;
}
$refType=RequestHandler::getClass('refType');
$refId=RequestHandler::getId('refId');
$resObj=new Resource($resource);
$manageCapacity=PlannedWorkManual::getManageCapacity($resObj);
$halfDayDuration=0.5;
if ($manageCapacity=='DURATION') {
  $capacity=$resObj->getCapacityPeriod($date);
  $halfDayDuration=$capacity/2;
}
$allDay=false;
if (pq_substr($period,-1)=="X") {
  $allDay=true;
  $period=pq_substr($period,0,2);
  $periodx=($period=='AM')?'PM':'AM';
}
$multiSelect=false;
if (pq_substr($period,-1)=="W") {
  $multiSelect=true;
  $periodMulti=pq_substr($period,0,2);
  //$periodx=($period=='AM')?'PM':'AM';
}
$resourceIncompatible = new ResourceIncompatible();
$critArray=array('idResource'=>$resource);
$incompatibleResourceList=$resourceIncompatible->getSqlElementsFromCriteria($critArray, false);
$lstIncompatible=array();
foreach ($incompatibleResourceList as $inc) {
  $lstIncompatible[$inc->idIncompatible]=$inc->idIncompatible;
}
$critIncompatible="idResource in ".transformListIntoInClause($lstIncompatible)." and workDate='$date'";
$critIncompatible.=" and refType is not null and refId is not null";

if($firstClickedDate and $firstClickedDate != "undefined"){
  $startDate = $firstClickedDate;
}else{
  $startDate = null;
}
if($shiftClickedDate and $shiftClickedDate != "undefined"){
 $endDate = $shiftClickedDate;
}else{
 $endDate = null;
}


if ($startDate && $endDate) {
  $dates = getDatesInRange($startDate, $endDate);
} else {
  $dates = array($date); 
}
//$periodTemp=$myfirstPeriod;

//$critIncompatible.=" and refType='$refType' and refId=$refId";
ob_start();
$someNotSet=false;
$firtOperation=null;
foreach ($dates as $date) {
  $skip=array();
  if ($multiSelect and isOffDay($date, $resObj->idCalendarDefinition)) { continue; }
  
  if ($multiSelect) {
    if ($date===$firstClickedDate) {
      if ($myfirstPeriod=='PM') { 
        continue;
      } else {
        $allDay=false;
        $period='PM';
        $pwm=SqlElement::getSingleSqlElementFromCriteria('PlannedWorkManual', array('workDate'=>$date,'idResource'=>$resource,'period'=>$period));
        $pwmx=null;
      }
    } else if ($date===$shiftClickedDate) {
      if ($periodMulti=='AM') {
        $allDay=false;
        $period='AM';
        $periodx=null;
        $pwm=SqlElement::getSingleSqlElementFromCriteria('PlannedWorkManual', array('workDate'=>$date,'idResource'=>$resource,'period'=>$period));
        $pwmx=null;
      } else {
        $allDay=true;
        $period='AM';
        $periodx='PM';
        $pwm=SqlElement::getSingleSqlElementFromCriteria('PlannedWorkManual', array('workDate'=>$date,'idResource'=>$resource,'period'=>$period));
        $pwmx=SqlElement::getSingleSqlElementFromCriteria('PlannedWorkManual', array('workDate'=>$date,'idResource'=>$resource,'period'=>$periodx));
      }
    } else {
      $allDay=true;
      $period='AM';
      $periodx='PM';
      $pwm=SqlElement::getSingleSqlElementFromCriteria('PlannedWorkManual', array('workDate'=>$date,'idResource'=>$resource,'period'=>$period));
      $pwmx=SqlElement::getSingleSqlElementFromCriteria('PlannedWorkManual', array('workDate'=>$date,'idResource'=>$resource,'period'=>$periodx));
    }

  } else {
    $pwm=SqlElement::getSingleSqlElementFromCriteria('PlannedWorkManual', array('workDate'=>$date,'idResource'=>$resource,'period'=>$period));
    if ($allDay) $pwmx=SqlElement::getSingleSqlElementFromCriteria('PlannedWorkManual', array('workDate'=>$date,'idResource'=>$resource,'period'=>$periodx));
  }
  if($pwm->id and $pwm->refType and $pwm->refId){
    $lstProjectVisible = $user->getVisibleProjects();
    $project =new Project($pwm->idProject,true);
    $profile=getSessionUser()->getProfile($project);
    $habil=SqlElement::getSingleSqlElementFromCriteria('HabilitationOther', array('idProfile'=>$profile, 'scope'=>'assignmentEdit'));
    if($habil->rightAccess!=1 or !pq_array_key_exists($pwm->idProject, $lstProjectVisible)){
      if ($multiSelect) {
        $someNotSet=true;
        $skip[$period]=true;
      } else {
        echo '{"error":"'.i18n('errorUpdateRights').'"}';
        exit;
      }
    }
  }
  if( $allDay and $pwmx and $pwmx->id and $pwmx->refType and $pwmx->refId){
    $lstProjectVisible = $user->getVisibleProjects();
    $project =new Project($pwmx->idProject,true);
    $profile=getSessionUser()->getProfile($project);
    $habil=SqlElement::getSingleSqlElementFromCriteria('HabilitationOther', array('idProfile'=>$profile, 'scope'=>'assignmentEdit'));
    if($habil->rightAccess!=1 or !pq_array_key_exists($pwmx->idProject, $lstProjectVisible)){
      if ($multiSelect) {
        $someNotSet=true;
        $skip[$periodx]=true;
      } else {
        echo '{"error":"'.i18n('errorUpdateRights').'"}';
        exit;
      }
    } 
  }

  if ($refType and $refId and (!$pwm->id or $pwm->refType!=$refType or $pwm->refId!=$refId) and count($lstIncompatible)>0) {
    $nb=$pwm->countSqlElementsFromCriteria(null,"$critIncompatible and period='$period'");
    if ($nb>0) {
      if ($multiSelect) {
        $someNotSet=true;
        $skip[$period]=true;
      } else {
        echo '{"error":"'.i18n('errorIncompatibleAlreadyPlanned').'"}';
        exit;
      }
    }
  }
  if ( $allDay and $refType and $refId and $pwmx and (!$pwmx->id or $pwmx->refType!=$refType or $pwmx->refId!=$refId) and count($lstIncompatible)>0) {
    $nb=$pwm->countSqlElementsFromCriteria(null,"$critIncompatible and period='$periodx'");
    if ($nb>0) {
      if ($multiSelect) {
        $someNotSet=true;
        $skip[$periodx]=true;
      } else {
        echo '{"error":"'.i18n('errorIncompatibleAlreadyPlanned').'"}';
        exit;
      }
    }
  }
  Sql::beginTransaction();
  //gautier habilation
  
  if (!$pwm->id) {
    $pwm->setDates($date);
    $pwm->idResource=$resource;
    $pwm->period=$period;
  }
  if ($allDay and !$pwmx->id) {
    $pwmx->setDates($date);
    $pwmx->idResource=$resource;
    $pwmx->period=$periodx;
  }
  
  if ($refType and $refId and $idMode) {
    if ($pwm->refType==$refType and $pwm->refId==$refId and $pwm->idInterventionMode==$idMode) {
      $pwm->refType=null;
      $pwm->refId=null;
      $pwm->work=null;
      $pwm->idInterventionMode=null;
      if ($allDay) {
        $pwmx->refType=null;
        $pwmx->refId=null;
        $pwmx->work=null;
        $pwmx->idInterventionMode=null;
      }
    } else {
      $pwm->refType=$refType;
      $pwm->refId=$refId;
      $pwm->work=$halfDayDuration;
      $pwm->idInterventionMode=$idMode;
      if ($allDay) {
        $pwmx->refType=$refType;
        $pwmx->refId=$refId;
        $pwmx->work=$halfDayDuration;
        $pwmx->idInterventionMode=$idMode;
      }
    }
  } else if ($idMode) {
    if ($pwm->idInterventionMode==$idMode) {
      $pwm->idInterventionMode=null;
      if ($allDay) {
        $pwmx->idInterventionMode=null;
      }
    } else {
      $pwm->idInterventionMode=$idMode;
      if ($allDay) {
        $pwmx->idInterventionMode=$idMode;
      }     
    }
  } else if ($refType and $refId) {
    if ($pwm->refType==$refType and $pwm->refId==$refId) {
      $pwm->refType=null;
      $pwm->refId=null;
      $pwm->work=null;
      if ($allDay) {
        $pwmx->refType=null;
        $pwmx->refId=null;
        $pwmx->work=null;
      }
    } else {
      $pwm->refType=$refType;
      $pwm->refId=$refId;
      $pwm->work=$halfDayDuration;
      if ($allDay) {
        $pwmx->refType=$refType;
        $pwmx->refId=$refId;
        $pwmx->work=$halfDayDuration;
      }
    }
  }
  $pwm->inputUser=getCurrentUserId();
  $pwm->inputDateTime=date('Y-m-d H:i:s');
  if ($allDay) {
    $pwmx->inputUser=getCurrentUserId();
    $pwmx->inputDateTime=date('Y-m-d H:i:s');
  }
  $result='';$resultx='';
  if (!$pwm->idInterventionMode and !$pwm->refType and !$pwm->refId) {
    if (! isset($skip[$period]) and $firtOperation!='insert') $result=$pwm->delete();
    if ($allDay) {
      if (! isset($skip[$periodx])  and $firtOperation!='insert') $resultx=$pwmx->delete();
    }
    if (! $firtOperation) $firtOperation="delete";
  } else {
    if (! isset($skip[$period]) and $firtOperation!='delete') $result=$pwm->save();
    if ($allDay) {
      if (! isset($skip[$periodx]) and $firtOperation!='delete') $resultx=$pwmx->save();
    }
    if (! $firtOperation) $firtOperation="insert";
  }
  // Message of correct saving
  displayLastOperationStatus($result??$resultx);

  $ass = SqlElement::getSingleSqlElementFromCriteria('Assignment', array('refType'=>$refType,'refId'=>$refId,'idResource'=>$resource,'idle'=>'0'));
  $assigned = ($ass->assignedWork) ? Work::displayWork($ass->assignedWork): 0;
  $real = ($ass->realWork) ? Work::displayWork($ass->realWork) : 0;
  $left = ($ass->leftWork) ? Work::displayWork($ass->leftWork) : 0;
  ob_clean();
  echo '{"assigned":'.$assigned.',"real":'.$real.',"left":'.$left.'}';
}
// Idea to display message is not good idea as is removes the refresh
// if ($someNotSet) { 
//   ob_clean();
//   echo '{"error":"'.i18n('plannedIntervnetionSomeNotSet').'"}';
// }

function getDatesInRange($startDate, $endDate) {
  $periodInR= new DatePeriod(
      new DateTime($startDate),
      new DateInterval('P1D'),
      (new DateTime($endDate))->modify('+1 day')
  );
  $dateArray = array();
  foreach ($periodInR as $date) {
    $dateArray[] = $date->format('Y-m-d');
  }
  return $dateArray;
}
?>
