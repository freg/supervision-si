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
 * Run planning
 */
require_once "../tool/projeqtor.php";
scriptLog('   ->/tool/plan.php');
if (! pq_array_key_exists('idProjectPlan',$_REQUEST)) {
  //throwError('idProjectPlan parameter not found in REQUEST');
  $idProjectPlan=array(" ");
} else {
  $idProjectPlan=$_REQUEST['idProjectPlan']; // validated to be numeric in SqlElement base constructor
  if (! is_array($idProjectPlan)) $idProjectPlan=explode(',', $idProjectPlan);
  Security::checkValidId($idProjectPlan);
}

if (! pq_array_key_exists('startDatePlan',$_REQUEST)) {
  throwError('startDatePlan parameter not found in REQUEST');
}
$startDatePlan=pq_trim($_REQUEST['startDatePlan']);
Security::checkValidDateTime($startDatePlan);

if (! Parameter::getUserParameter('modeSurbooking')) {
  Parameter::storeUserParameter('modeSurbooking', Parameter::getGlobalParameter('checkedSurbookingDefault'));
}
$infinitecapacity=(Parameter::getUserParameter('modeSurbooking')=='YES')?true:false;

$criticalMode=(getSessionValue('modeSurbookingCritical')=='YES')?true:false;

// Moved transaction at end of procedure (out of script plan.php) to minimize lock possibilities
// Sql::beginTransaction();

if ($startDatePlan) {
  setSessionValue('startDateCalculPlanning', $startDatePlan);
}
$planRefType=null;
$planRefId=null;
if (RequestHandler::getValue('planLastSavedClass',false,null) and RequestHandler::getValue('planLastSavedId',false,null)) {
  $planRefType=RequestHandler::getClass('planLastSavedClass');
  $planRefId=RequestHandler::getId('planLastSavedId');
  // Automatic planning after project copy must include the new project, even when it is not in current selection.
  $allProjects=(count($idProjectPlan)==1 and !pq_trim($idProjectPlan[0]));
  if ($planRefType=='Project' and !$allProjects and !in_array($planRefId, $idProjectPlan)) {
    // Only a real project widens the scope : the class comes from the screen and
    // the id from the saved object, so the pair can name another class
    $refProj=new Project($planRefId, true);
    if ($refProj->id) { $idProjectPlan[]=$planRefId; }
  }
  $pe=SqlElement::getSingleSqlElementFromCriteria('PlanningElement', array('refType'=>$planRefType, 'refId'=>$planRefId));
  $pm=new PlanningMode($pe->idPlanningMode);
  if ($pm->code!='DDUR') {
    $planRefType=null;
    $planRefId=null;
  }
}

$CalculateWithCriticalPathParam=1;
$CalculateWithCriticalPath=Parameter::getUserParameter('planWithCriticalPath');
if($CalculateWithCriticalPath==0 or $CalculateWithCriticalPath==''){
  $CalculateWithCriticalPathParam=0;
}
projeqtor_set_time_limit(600);
$result=PlannedWork::plan($idProjectPlan, $startDatePlan,$CalculateWithCriticalPathParam,$infinitecapacity,false,$criticalMode, $planRefType, 0);

// Message of correct saving

// Moved transaction at end of procedure (out of script plan.php) to minimize lock possibilities
//displayLastOperationStatus($result);
?>
