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
 * Save a note : call corresponding method in SqlElement Class
 * The new values are fetched in $_REQUEST
 */
require_once "../tool/projeqtor.php";
scriptLog('   ->/tool/saveProviderTerm.php');

$mode=RequestHandler::getValue('mode');
$id = RequestHandler::getId('id');
$idActivityWorkUnit = RequestHandler::getId('idActivityWorkUnit');
$workCommandWorkUnit = RequestHandler::getId('ActivityWorkCommandWorkUnit');
$workCommandComplexity = RequestHandler::getId('ActivityWorkCommandComplexity');
$workCommandQuantity = RequestHandler::getValue('ActivityWorkCommandQuantity');
$workCommandAmount = RequestHandler::getValue('ActivityWorkCommandAmount');
$workCommandAmountLocal = RequestHandler::getValue('ActivityWorkCommandAmountLocal');
$idWorkCommand = RequestHandler::getId('ActivityBilledWorkCommandWorkCommand');
Sql::beginTransaction();
$result="";

if ($mode=='edit') {
  $newWorkCommand = false;
  $changeWorkCommand = false;
  $deleteWorkCommand = false;
  $activityWorkUnit = new ActivityWorkUnit($idActivityWorkUnit);
  $activityWorkUnit->refType = 'Activity';
  $activityWorkUnit->refId = $id;
  $activityWorkUnit->idWorkUnit = $workCommandWorkUnit;
  $activityWorkUnit->idComplexity = $workCommandComplexity;
  $activityWorkUnit->quantity = $workCommandQuantity;
  if($idWorkCommand == ' ')$idWorkCommand='';
  if(!$activityWorkUnit->idWorkCommand and $idWorkCommand)$newWorkCommand=true;
  if($activityWorkUnit->idWorkCommand and $idWorkCommand){
    $oldActWorkCommand = $activityWorkUnit->idWorkCommand;
    $changeWorkCommand=true;
  }
  if($activityWorkUnit->idWorkCommand and !$idWorkCommand){
    $oldActWorkCommand = $activityWorkUnit->idWorkCommand;
    $deleteWorkCommand = true;
  }
  $activityWorkUnit->idWorkCommand = $idWorkCommand;
  $res=$activityWorkUnit->save();
  $status=getLastOperationStatus($res);
  if ($status=="OK" ){
    $act = new Activity($id);
    $complex = new Complexity($workCommandComplexity);
    $complexValue = SqlElement::getSingleSqlElementFromCriteria('ComplexityValues', array('idComplexity'=>$workCommandComplexity,'idWorkUnit'=>$workCommandWorkUnit,'idCatalogUO'=>$complex->idCatalogUO));
    $act->save();
    if($newWorkCommand){
      $workCommand = new WorkCommand($idWorkCommand);
      $workCommandDone = new WorkCommandDone();
      $newWorkCommandDone = new WorkCommandDone();
      $workCommandDoneExist = $workCommandDone->getSingleSqlElementFromCriteria('WorkCommandDone', array('idActivityWorkUnit'=>$activityWorkUnit->id,'idWorkCommand'=>$idWorkCommand,'refId'=>$act->id,'refType'=>'Activity','idCommand'=>$workCommand->idCommand));
      if($workCommandDoneExist){
        $workCommandDone = new WorkCommandDone($workCommandDoneExist->id);
      }
      $workCommandDone->idCommand = $workCommand->idCommand;
      $workCommandDone->idWorkCommand = $idWorkCommand;
      $workCommandDone->refType = "Activity";
      $workCommandDone->refId = $act->id;
      $workCommandDone->doneQuantity = $workCommandQuantity;
      $workCommandDone->idActivityWorkUnit = $activityWorkUnit->id;
      $workCommandDone->save();
      $lstWorkCommand = $newWorkCommandDone->getSqlElementsFromCriteria(array('idWorkCommand'=>$idWorkCommand,'idCommand'=>$workCommand->idCommand));
      $quantity = 0;
      foreach ($lstWorkCommand as $comVal){
        $quantity += $comVal->doneQuantity;
      }
      $workCommand->doneQuantity = $quantity;
      $workCommand->doneAmount = $workCommand->unitAmount * $quantity;
      $workCommand->doneAmountLocal = $workCommand->unitAmountLocal * $quantity;
      $workCommand->save();
    }
    if($deleteWorkCommand){
      $workCommandDone = SqlElement::getSingleSqlElementFromCriteria('WorkCommandDone', array('idActivityWorkUnit'=>$activityWorkUnit->id));
      $workCommandDone->delete();
      $newWorkCommandDone = new WorkCommandDone();
      $workCommand = new WorkCommand($oldActWorkCommand);
      $lstWorkCommand = $newWorkCommandDone->getSqlElementsFromCriteria(array('idWorkCommand'=>$oldActWorkCommand,'idCommand'=>$workCommand->idCommand));
      $quantity = 0;
      foreach ($lstWorkCommand as $comVal){
        $quantity += $comVal->doneQuantity;
      }
      $workCommand->doneQuantity = $quantity;
      $workCommand->doneAmount = $workCommand->unitAmount * $quantity;
      $workCommand->doneAmountLocal = $workCommand->unitAmountLocal * $quantity;
      $workCommand->save();
    }
    if($changeWorkCommand){
      //delete
      $workCommandDone = SqlElement::getSingleSqlElementFromCriteria('WorkCommandDone', array('idActivityWorkUnit'=>$activityWorkUnit->id));
      $workCommandDone->delete();
      $newWorkCommandDone = new WorkCommandDone();
      $workCommand = new WorkCommand($oldActWorkCommand);
      $lstWorkCommand = $newWorkCommandDone->getSqlElementsFromCriteria(array('idWorkCommand'=>$idWorkCommand,'idCommand'=>$workCommand->idCommand));
      $quantity = 0;
      foreach ($lstWorkCommand as $comVal){
        $quantity += $comVal->doneQuantity;
      }
      $workCommand->doneQuantity = $quantity;
      $workCommand->doneAmount = $workCommand->unitAmount * $quantity;
      $workCommand->doneAmountLocal = $workCommand->unitAmountLocal * $quantity;
      $workCommand->save();
      //create
      $workCommand = new WorkCommand($idWorkCommand);
      $workCommandDone = new WorkCommandDone();
      $newWorkCommandDone = new WorkCommandDone();
      $workCommandDoneExist = $workCommandDone->getSingleSqlElementFromCriteria('WorkCommandDone', array('idActivityWorkUnit'=>$activityWorkUnit->id,'idWorkCommand'=>$idWorkCommand,'refId'=>$act->id,'refType'=>'Activity','idCommand'=>$workCommand->idCommand));
      if($workCommandDoneExist){
        $workCommandDone = new WorkCommandDone($workCommandDoneExist->id);
      }
      $workCommandDone->idCommand = $workCommand->idCommand;
      $workCommandDone->idWorkCommand = $idWorkCommand;
      $workCommandDone->refType = "Activity";
      $workCommandDone->refId = $act->id;
      $workCommandDone->doneQuantity = $workCommandQuantity;
      $workCommandDone->idActivityWorkUnit = $activityWorkUnit->id;
      $workCommandDone->save();
      $lstWorkCommand = $newWorkCommandDone->getSqlElementsFromCriteria(array('idWorkCommand'=>$idWorkCommand,'idCommand'=>$workCommand->idCommand));
      $quantity = 0;
      foreach ($lstWorkCommand as $comVal){
        $quantity += $comVal->doneQuantity;
      }
      $workCommand->doneQuantity = $quantity;
      $workCommand->doneAmount = $workCommand->unitAmount * $quantity;
      $workCommand->doneAmountLocal = $workCommand->unitAmountLocal * $quantity;
      $workCommand->save();
    }
  }
}else{
  $activityWorkUnit = new ActivityWorkUnit();
  $activityWorkUnit->refType = 'Activity';
  $activityWorkUnit->refId = $id;
  $activityWorkUnit->idWorkUnit = $workCommandWorkUnit;
  $activityWorkUnit->idComplexity = $workCommandComplexity;
  $activityWorkUnit->quantity = $workCommandQuantity;
  $activityWorkUnit->idWorkCommand=$idWorkCommand;
  $res=$activityWorkUnit->save();
  $status=getLastOperationStatus($res);
  if ($status=="OK" ){
    $act = new Activity($id);
    $complex = new Complexity($workCommandComplexity);
    $complexValue = SqlElement::getSingleSqlElementFromCriteria('ComplexityValues', array('idComplexity'=>$workCommandComplexity,'idWorkUnit'=>$workCommandWorkUnit,'idCatalogUO'=>$complex->idCatalogUO));
    if($act->ActivityPlanningElement->hasWorkUnit==0){
      $act->ActivityPlanningElement->hasWorkUnit=1;
      if($act->workOnRealTime==1)$act->workOnRealTime=0;
    }
    $act->save();
    if($idWorkCommand and $idWorkCommand!=' '){
      $workCommand = new WorkCommand($idWorkCommand);
      $workCommandDone = new WorkCommandDone();
      $newWorkCommandDone = new WorkCommandDone();
      $workCommandDoneExist = $workCommandDone->getSingleSqlElementFromCriteria('WorkCommandDone', array('idActivityWorkUnit'=>$activityWorkUnit->id,'idWorkCommand'=>$idWorkCommand,'refId'=>$act->id,'refType'=>'Activity','idCommand'=>$workCommand->idCommand));
      if($workCommandDoneExist){
        $workCommandDone = new WorkCommandDone($workCommandDoneExist->id);
      }
      $workCommandDone->idCommand = $workCommand->idCommand;
      $workCommandDone->idWorkCommand = $idWorkCommand;
      $workCommandDone->refType = "Activity";
      $workCommandDone->refId = $act->id;
      $workCommandDone->doneQuantity = $workCommandQuantity;
      $workCommandDone->idActivityWorkUnit = $activityWorkUnit->id;
      $workCommandDone->save();
      $lstWorkCommand = $newWorkCommandDone->getSqlElementsFromCriteria(array('idWorkCommand'=>$idWorkCommand,'idCommand'=>$workCommand->idCommand));
      $quantity = 0;
      foreach ($lstWorkCommand as $comVal){
        $quantity += $comVal->doneQuantity;
      }
      $workCommand->doneQuantity = $quantity;
      $workCommand->doneAmount = $workCommand->unitAmount * $quantity;
      $workCommand->doneAmountLocal = $workCommand->unitAmountLocal * $quantity;
      $workCommand->save();
    }
  }
}
if (!$result) {
  $result=$res;
}
// Message of correct saving
displayLastOperationStatus($result);

?>