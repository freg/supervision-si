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
 * Delete the current object : call corresponding method in SqlElement Class
 */

require_once "../tool/projeqtor.php";

$idWorkUnit = RequestHandler::getId('idWorkUnit');
Sql::beginTransaction();
$workUnit = new ActivityWorkUnit($idWorkUnit);
$idActivity = $workUnit->refId;
if($workUnit->idWorkCommand){
  $workCommandDone = SqlElement::getSingleSqlElementFromCriteria('WorkCommandDone', array('idActivityWorkUnit'=>$workUnit->id));
  $workCommandDone->delete();
  $newWorkCommandDone = new WorkCommandDone();
  $workCommand = new WorkCommand($workUnit->idWorkCommand);
  $lstWorkCommand = $newWorkCommandDone->getSqlElementsFromCriteria(array('idWorkCommand'=>$workUnit->idWorkCommand,'idCommand'=>$workCommand->idCommand));
  $quantity = 0;
  foreach ($lstWorkCommand as $comVal){
    $quantity += $comVal->doneQuantity;
  }
  $workCommand->doneQuantity = $quantity;
  $workCommand->doneAmount = $workCommand->unitAmount * $quantity;
  $workCommand->save();
}
$result=$workUnit->delete();


$act = new Activity($idActivity);
$CaReplaceValidCost= Parameter::getGlobalParameter('CaReplaceValidCost');
if($CaReplaceValidCost=='YES'){
  $act->ActivityPlanningElement->validatedCost = 0;
}
$activityWorkUnit = new ActivityWorkUnit();
$lstActWorkUnit = $activityWorkUnit->getSqlElementsFromCriteria(array('refType'=>'Activity','refId'=>$act->ActivityPlanningElement->refId));
$act->ActivityPlanningElement->validatedWork = 0;
$oldRevenue = $act->ActivityPlanningElement->revenue;
$act->ActivityPlanningElement->revenue = 0;
foreach ($lstActWorkUnit as $actWork){
  $complexityVal = SqlElement::getSingleSqlElementFromCriteria('ComplexityValues', array('idWorkUnit'=>$actWork->idWorkUnit,'idComplexity'=>$actWork->idComplexity));
  $act->ActivityPlanningElement->validatedWork += $complexityVal->charge*$actWork->quantity;
  $act->ActivityPlanningElement->revenue += $complexityVal->price*$actWork->quantity;
  $ass = new Assignment();
  $lstAss = $ass->getSqlElementsFromCriteria(array('refType'=>'Activity','refId'=>$act->ActivityPlanningElement->refId));
  $totalValidatedWork = 0;
  foreach ($lstAss as $asVal){
    if ($act->ActivityPlanningElement->idle) continue;
    $totalValidatedWork += $asVal->assignedWork;
  }
  if( $totalValidatedWork>0 ){
    $factor = $act->ActivityPlanningElement->validatedWork / $totalValidatedWork;
    $sumAssignedWork=0;
    $sumLeftWork=0;
    $sumAssignedCost=0;
    $sumLeftCost=0;
    foreach ($lstAss as $asVal){
      if (! $asVal->idle) {
        $asVal->_skipDispatch=true;
        $newLeftWork = ($asVal->assignedWork*$factor) - ($asVal->assignedWork) ;
        $asVal->assignedWork = round($asVal->assignedWork*$factor,2);
        $asVal->leftWork = $asVal->leftWork+$newLeftWork;
        if($asVal->leftWork < 0)$asVal->leftWork=0;
        $asVal->save();
      }
      $sumAssignedWork+=$asVal->assignedWork;
      $sumLeftWork+=$asVal->leftWork;
      $sumAssignedCost+=$asVal->assignedCost;
      $sumLeftCost+=$asVal->leftCost;
    }
    $act->ActivityPlanningElement->assignedWork=$sumAssignedWork;
    $act->ActivityPlanningElement->leftWork=$sumLeftWork;
    $act->ActivityPlanningElement->plannedWork=$act->ActivityPlanningElement->realWork+$act->ActivityPlanningElement->leftWork;
    $act->ActivityPlanningElement->assignedCost=$sumAssignedCost;
    $act->ActivityPlanningElement->leftCost=$sumLeftCost;
    $act->ActivityPlanningElement->plannedCost=$act->ActivityPlanningElement->realCost+$act->ActivityPlanningElement->leftCost;
    $act->ActivityPlanningElement->_workHistory=true; // Will force to update data (it's a hack)
  }
  if($CaReplaceValidCost=='YES'){
    $act->ActivityPlanningElement->validatedCost += $complexityVal->price*$actWork->quantity;
  }
}
$act->save();

$countActivity = $workUnit->countSqlElementsFromCriteria(array('refId'=>$idActivity,'refType'=>'Activity'));
if($countActivity==0){
  $act = new Activity($idActivity);
  $act->ActivityPlanningElement->hasWorkUnit = 0;
  $act->ActivityPlanningElement->revenue = $oldRevenue;
  $act->save();
}
displayLastOperationStatus($result);
?>