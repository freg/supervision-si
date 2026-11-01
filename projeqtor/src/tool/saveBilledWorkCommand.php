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
$idBill = RequestHandler::getId('idBill');
$idWorkCommand = RequestHandler::getId('billedWorkCommandWorkCommand');
$workCommand = new WorkCommand($idWorkCommand);
$billedQuantity = RequestHandler::getValue('billedWorkCommandQuantityBilled');
Sql::beginTransaction();
$result="";

if ($mode=='edit') {
  $billedWorkCommand = new WorkCommandBilled($id);
  $billedWorkCommand->billedQuantity = $billedQuantity;
  $res=$billedWorkCommand->save();
  $billedWorkCommand2 = new WorkCommandBilled();
  $listBilledWorkCommand2 = $billedWorkCommand2->getSqlElementsFromCriteria(array('idWorkCommand'=>$idWorkCommand));
  $totalBilled = 0;
  foreach ($listBilledWorkCommand2 as $billed){
    $ref=SqlList::getFieldFromId('Bill', $billed->idBill,'done');
    if ($ref=='1') $totalBilled += $billed->billedQuantity;
  }
  $workCommand->billedQuantity  = $totalBilled;
  $workCommand->billedAmount = $workCommand->unitAmount * $totalBilled;
  $workCommand->save();
}else{
  $billedWorkCommand = new WorkCommandBilled();
  $billedWorkCommand->idBill = $idBill;
  $billedWorkCommand->idCommand = $workCommand->idCommand;
  $billedWorkCommand->idWorkCommand = $idWorkCommand;
  $billedWorkCommand->billedQuantity = $billedQuantity;
  $res=$billedWorkCommand->save();
  $billedWorkCommand2 = new WorkCommandBilled();
  $listBilledWorkCommand2 = $billedWorkCommand2->getSqlElementsFromCriteria(array('idWorkCommand'=>$idWorkCommand));
  $totalBilled = 0;
  foreach ($listBilledWorkCommand2 as $billed){
    $ref=SqlList::getFieldFromId('Bill', $billed->idBill,'done');
    if ($ref=='1') $totalBilled += $billed->billedQuantity;
  }
  $workCommand->billedQuantity  = $totalBilled;
  $workCommand->billedAmount = $workCommand->unitAmount * $totalBilled;
  $workCommand->save();
}

if (!$result) {
  $result=$res;
}
// Message of correct saving
displayLastOperationStatus($result);

?>