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

$idProject = RequestHandler::getId('idProject');
$ticketType = RequestHandler::getId('synchroniseDefinitionTicketType');
$ticketState = RequestHandler::getId('synchroniseDefinitionStatus');
$activityType = RequestHandler::getId('synchroniseDefinitionActivityType');
$asPlaningActivity = RequestHandler::getBoolean('synchroniseDefinitionPlanningActivity');
$doTicketExisting = RequestHandler::getBoolean('synchroniseDefinitionTicketExisting');
$createSynchronizationDefiniton=true;

Sql::beginTransaction();
$result="";
//Create Synch
$synch = new Synchronization();
$synch->idProject = $idProject;
$synch->originType = 'Ticket';
$synch->targetType = 'Activity';
$synch->idStatus = $ticketState;
$synch->idOrigineType = $ticketType;
$synch->idTargetType = $activityType;
if(!$asPlaningActivity)$asPlaningActivity = 0;
if($asPlaningActivity)$asPlaningActivity = 1;
$synch->setActivity = $asPlaningActivity;
$res=$synch->save();

if (!$result) {
  $result=$res;
}
// Message of correct saving
displayLastOperationStatus($result);

// Create activities with existing Tickets
if($doTicketExisting){
  $where = " idProject=".$idProject. " and idle = 0 ";
if($ticketType and $ticketType != ' '){
   $where .= " and idTicketType=".$ticketType;
 }
  if($ticketState){
    //sortOrder >= 
    $status = new Status($ticketState);
    $whereLst = ' idle = 0 and sortOrder >= '.$status->sortOrder;
    $statusNew = new Status();
    $lstStatus = $statusNew->getSqlElementsFromCriteria(null,null,$whereLst);
    $statArray= array();
    foreach ($lstStatus as $stat){
      $statArray[]= $stat->id;
    }
    $where .= " and idStatus in ".transformValueListIntoInClause($statArray);
  }
  $tick = new Ticket();
  $ticketArray = $tick->getSqlElementsFromCriteria(null,false,$where);
  foreach ($ticketArray as $obj){
    Synchronization::startSynchronization($obj);
  }
  
}
?>