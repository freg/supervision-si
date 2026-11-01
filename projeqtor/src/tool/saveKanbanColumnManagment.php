<?php
/*** COPYRIGHT NOTICE *********************************************************
 *
 ******************************************************************************
 *** WARNING *** T H I S    F I L E    I S    N O T    O P E N    S O U R C E *
 ******************************************************************************
 *
 * Copyright 2015 ProjeQtOr - Pascal BERNARD - support@projeqtor.org
 *
 * This file is an add-on to ProjeQtOr, packaged as a plug-in module.
 * It is NOT distributed under an open source license.
 * It is distributed in a proprietary mode, only to the customer who bought
 * corresponding licence.
 * The company ProjeQtOr remains owner of all add-ons it delivers.
 * Any change to an add-ons without the explicit agreement of the company
 * ProjeQtOr is prohibited.
 * The diffusion (or any kind if distribution) of an add-on is prohibited.
 * Violators will be prosecuted.
 *
 *** DO NOT REMOVE THIS NOTICE ************************************************/

require_once "../tool/projeqtor.php";
require_once "../tool/formatter.php";

$idKanban = RequestHandler::getId('idKanban');
$idColumn = RequestHandler::getValue('idColumn');
$columnName = RequestHandler::getValue('nameColumn');
$jsonColumn = RequestHandler::getValue('jsonColumn');

$kanban = new Kanban($idKanban);

Sql::beginTransaction();

if($idColumn != ''){
  $json = json_decode ( $kanban->param, true );
  if (isset ( $json ['column'] )){
    foreach ($json['column'] as &$col) {
      if($col['from'] == 'n')$col['from']='0';
      if ($col['from'] == $idColumn) {
        $col['name'] = $columnName;
        break;
      }
    }
    unset($col);
  }
  $jsonColumn = json_encode($json);
}

$kanban->param = $jsonColumn;
$result=$kanban->save();

// Message of correct saving
displayLastOperationStatus($result);
?>