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

$kanban=new Kanban();
$mineList=$kanban->getSqlElementsFromCriteria(null, false," idUser=$user->id ");
$res= new Resource();
$reTable= $res->getDatabaseTableName();
$clauseWhere=" idUser in (Select id from $reTable where id!=$user->id and idle=0 ) AND isShared=1 ";
$sharedList=$kanban->getSqlElementsFromCriteria(null, false,$clauseWhere, "idUser ASC");

if(count($mineList) == 0 and count($sharedList) == 0){
  echo 'noKanban';
}else if(count($mineList) == 1 and count($sharedList) == 0){
  echo 'mineKanban_'.$mineList[0]->id;
}else if(count($mineList) == 0 and count($sharedList) == 1){
  echo 'sharedKanban_'.$sharedList[0]->id;
}else if(count($mineList) > 1 or count($sharedList) > 1 or (count($mineList) > 0 and count($sharedList) > 0)){
  echo 'allKanban';
}
?>