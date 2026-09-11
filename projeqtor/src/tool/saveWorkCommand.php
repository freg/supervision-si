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
$idCommand = RequestHandler::getId('idCommand');
$workCommandWorkUnit = RequestHandler::getId('workCommandWorkUnit');
$workCommandComplexity = RequestHandler::getId('workCommandComplexity');
$workCommandUnitAmount = RequestHandler::getValue('workCommandUnitAmount');
$workCommandQuantity = RequestHandler::getValue('workCommandQuantity');
$workCommandAmount = RequestHandler::getValue('workCommandAmount');
$workCommandParent = RequestHandler::getValue('workCommandParent');
$nameWorkCommand = RequestHandler::getValue('nameWorkCommand');
Sql::beginTransaction();
$result="";

$workCommand = ($mode=='edit') ? new WorkCommand($id) : new WorkCommand();

if ($mode!='edit') $workCommand->idCommand = $idCommand;
$nameWorkUnit = SqlList::getFieldFromId('WorkUnit',$workCommandWorkUnit,'reference');
$nameComplexity = SqlList::getNameFromId('Complexity',$workCommandComplexity);
$nameWorkCommandParent = SqlList::getNameFromId('WorkCommand',$workCommandParent);
if (!$nameWorkCommand){
  $workCommand->name =  ($nameWorkCommandParent != null) ? $nameWorkCommandParent. ' - ' .$nameWorkUnit.' - '.$nameComplexity : $nameWorkUnit.' - '.$nameComplexity;
}else{
  $workCommand->name = $nameWorkCommand;
}
$workCommand->idWorkUnit = $workCommandWorkUnit;
$workCommand->idComplexity = $workCommandComplexity;
$workCommand->idWorkCommand = $workCommandParent;
$workCommand->commandQuantity = $workCommandQuantity;

$workCommand->elementary = ($workCommandParent) ? '1' : '0';
if ($mode=='edit'){
  $workCommand->commandAmount = $workCommandQuantity * $workCommand->unitAmount;
}else {
  $workCommand->unitAmount = $workCommandUnitAmount;
  $workCommand->commandAmount = $workCommandAmount;
}

$res = ($workCommandParent) ? $workCommand->save() : $workCommand->save(false);

if (!$result) {
  $result=$res;
}
// Message of correct saving
displayLastOperationStatus($result);

?>