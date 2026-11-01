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
require_once "../tool/projeqtor.php";
scriptLog('   ->/tool/saveAbacusProjectLine.php');

$action = RequestHandler::getValue('action');
$idProject = RequestHandler::getId('idProject');
$idAbacusDefinition = RequestHandler::getId('idAbacusDefinition');
$quantity = RequestHandler::getNumeric('quantity');
$comment = RequestHandler::getValue('comment');
$idle = RequestHandler::getNumeric('idle');

$id = RequestHandler::getId('id');

$idClassName1 = RequestHandler::getId('idClassName1');
$idClassName2 = RequestHandler::getId('idClassName2');
$idClassName3 = RequestHandler::getId('idClassName3');
$idClassName4 = RequestHandler::getId('idClassName4');
$idClassName5 = RequestHandler::getId('idClassName5');

$capacity = RequestHandler::getValue('capacity');

$idClassNameRef = null;
for ($i = 1; $i <= 5; $i++) {
  $val = RequestHandler::getId('idClassNameRef' . $i);
  if ($val) { $idClassNameRef = $val; break; }
}

Sql::beginTransaction();

if ($action == 'delete') {
  if (!$id) {
    echo '<div class="messageERROR">' . i18n('errorNoItemToDelete') . '</div>';
    return;
  }
  $abacusProject = new AbacusProject($id);
  $result = $abacusProject->delete();
  
} else if ($action == 'update') {
  if (!$id) {
    echo '<div class="messageERROR">' . i18n('errorNoItemToUpdate') . '</div>';
    return;
  }
  
  $abacusProject = new AbacusProject($id);
  $abacusProject->idAffectable = getCurrentUserId();
  $abacusProject->idClassName1 = $idClassName1;
  $abacusProject->idClassName2 = $idClassName2;
  $abacusProject->idClassName3 = $idClassName3;
  $abacusProject->idClassName4 = $idClassName4;
  $abacusProject->idClassName5 = $idClassName5;
  $abacusProject->quantity = $quantity;
  $abacusProject->comment = $comment;
  $abacusProject->idle = $idle;
  $abacusProject->idClassNameRef = $idClassNameRef;
  $abacusProject->capacity = $capacity;
  
  $result = $abacusProject->save();
  
} else {
  if (!$idAbacusDefinition) {
    $result = '<div class="messageINVALID">' . i18n('errorMandatoryField') . ' : ' . i18n('colAbacusDefinition') . '</div>';
    $result .= '<input type="hidden" id="lastOperation" name="lastOperation" value="save">';
    $result .= '<input type="hidden" id="lastOperationStatus" name="lastOperationStatus" value="INVALID">';
  }else if (!$quantity || $quantity <= 0) {
    $result = '<div class="messageINVALID">' . i18n('errorMandatoryField') . ' : ' . i18n('colQuantity') . '</div>';
    $result .= '<input type="hidden" id="lastOperation" name="lastOperation" value="save">';
    $result .= '<input type="hidden" id="lastOperationStatus" name="lastOperationStatus" value="INVALID">';
  }else{
    $abacusProject = new AbacusProject();
    $abacusProject->idProject = $idProject;
    $abacusProject->idAbacusDefinition = $idAbacusDefinition;
    $abacusProject->idAffectable = getCurrentUserId();
    $abacusProject->idClassName1 = $idClassName1;
    $abacusProject->idClassName2 = $idClassName2;
    $abacusProject->idClassName3 = $idClassName3;
    $abacusProject->idClassName4 = $idClassName4;
    $abacusProject->idClassName5 = $idClassName5;
    $abacusProject->quantity = $quantity;
    $abacusProject->comment = $comment;
    $abacusProject->idle = $idle;
    $abacusProject->idClassNameRef = $idClassNameRef;
    $abacusProject->capacity = $capacity;
    
    $result = $abacusProject->save();
  }
   
}

displayLastOperationStatus($result);
?>