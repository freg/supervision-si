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
$disableOption = RequestHandler::getValue('disableSynch');

Sql::beginTransaction();
$result="";
$synch = Synchronization::getProjectSynchronizationDefinition($idProject);
$synchId = $synch->id;
$res=$synch->delete();
if($disableOption=='delete' and $idProject){
  $synchItem = new SynchronizedItems();
  //$lstSynchItem = $synchItem->getSqlElementsFromCriteria(array('idSynchronization'=>$synchId));
  $tkt=new Ticket();$tktTable=$tkt->getDatabaseTableName();
  $lstSynchItem=$synchItem->getSqlElementsFromCriteria(null,false,"ref2Type='Ticket' and exists (select 'x' from $tktTable t where t.id=ref2id and idle=0 and t.idProject=$idProject)");
  foreach ($lstSynchItem as $item){
    $item->delete();
  }
}
if (!$result) {
  $result=$res;
}
// Message of correct saving
displayLastOperationStatus($result);

?>