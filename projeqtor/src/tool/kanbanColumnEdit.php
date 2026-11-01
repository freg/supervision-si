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

/* ============================================================================
 * Habilitation defines right to the application for a menu and a profile.
*/
require_once "../tool/projeqtor.php";

if (! pq_array_key_exists('name',$_REQUEST)) {
  throwError('Parameter name not found in REQUEST');
}
$name=$_REQUEST['name'];

if (! pq_array_key_exists('types',$_REQUEST)) {
  throwError('Parameter types not found in REQUEST');
}
$types=$_REQUEST['types'];

if (! pq_array_key_exists('idKanban',$_REQUEST)) {
  throwError('Parameter idKanban not found in REQUEST');
}
$idKanban=$_REQUEST['idKanban'];

if (! pq_array_key_exists('idFrom',$_REQUEST)) {
  throwError('Parameter idFrom not found in REQUEST');
}
$idFrom=$_REQUEST['idFrom'];

// Colonne renseignÃ© dans le formulaire
$columnKanbanForm = explode(',', $types);

$newColumns = array();
foreach($columnKanbanForm as $idColumn) {
  if ($idColumn == 'n') {
    $idColumn = '0';
  }
  $newColumns[$idColumn] = RequestHandler::getValue("nameColumn_".$idColumn);
}
/*
 * RÃ©cupÃ©ration du kanban
 */
$kanban=new Kanban($idKanban);
$json=json_decode($kanban->param,true);

/*
 * RÃ©cupÃ©ration des colunnes du formulaire
*/
$columnKanbanForm = explode(',', $types);
$newColumns = array();
foreach($columnKanbanForm as $idColumn) {
  if ($idColumn == 'n') {
  	$newColumns[$idColumn] = RequestHandler::getValue("nameColumn_0");
  } else {
    $newColumns[$idColumn] = RequestHandler::getValue("nameColumn_".$idColumn);
  }
}


/*
 * Construction du nouveau JSON
*/
$newJsonColumn = array();
foreach($newColumns as $from => $name) {
  if ($from == 0 or $from =='n' or $name == 'Backlog') {
    $arrayNewColumn = ["from" => $from, "name" => $name, "cantDelete" => 1];
  } else {
    $arrayNewColumn = ["from" => $from, "name" => $name];
  }
  array_push($newJsonColumn, $arrayNewColumn);
}
$json['column'] = $newJsonColumn;

/*
 * RÃ©cupÃ©ration du kanban + save
*/
$kanban->param=json_encode($json);
$kanban->save();



