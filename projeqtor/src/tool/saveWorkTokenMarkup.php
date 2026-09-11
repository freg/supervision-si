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
 * Save a note : call corresponding method in SqlElement Class
 * The new values are fetched in $_REQUEST
 */
require_once "../tool/projeqtor.php";
scriptLog('   ->/tool/saveWorkUnit.php');

$mode = RequestHandler::isCodeSet('mode')? RequestHandler::getValue('mode'):null;
$idWorkToken=RequestHandler::isCodeSet('idWorkToken')? RequestHandler::getId('idWorkToken'):null;
$labelMarkup=RequestHandler::isCodeSet('LabelMarkup')? RequestHandler::getValue('LabelMarkup'):null;
$coefValue=RequestHandler::isCodeSet('LabelMarkup')? RequestHandler::getValue('coefValue'):null;
$idWorkTokenMarkup = RequestHandler::isCodeSet('idWorkTokenMarkup')? RequestHandler::getId('idWorkTokenMarkup'):null;

if(!$mode or (($mode == 'delete' or $mode == 'edit') and !$idWorkToken)){
  traceHack("saveSubTaskOrder.php called anormaly");
  exit() ;
}

Sql::beginTransaction();
$result = "";

if($mode == 'edit'){
  $workTokenMarkup = new WorkTokenMarkup($idWorkTokenMarkup);
  $workTokenMarkup->idWorkToken=$idWorkToken;
  $workTokenMarkup->name = $labelMarkup;
  $workTokenMarkup->coefficient= $coefValue;
  $res = $workTokenMarkup->save();
}else if($mode == 'delete'){
  $workTokenMarkup = new WorkTokenMarkup($idWorkTokenMarkup);
  $res=$workTokenMarkup->delete();
}else{
  $workTokenMarkup = new WorkTokenMarkup();
  $workTokenMarkup->idWorkToken=$idWorkToken;
  $workTokenMarkup->name = $labelMarkup;
  $workTokenMarkup->coefficient= $coefValue;
  $res = $workTokenMarkup->save();
}
// Message of correct saving
displayLastOperationStatus($res);

?>