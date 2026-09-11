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
scriptLog('   ->/tool/saveAbacusDefinition.php');

$action = RequestHandler::getValue('action');

Sql::beginTransaction();
$result= '';
$res ='';
if ($action == 'save') {
  $ids = RequestHandler::getValue('ids');
  $names = RequestHandler::getValue('names');
  $className1 = RequestHandler::getValue('className1');
  $className2 = RequestHandler::getValue('className2');
  $className3 = RequestHandler::getValue('className3');
  $className4 = RequestHandler::getValue('className4');
  $className5 = RequestHandler::getValue('className5');
  $idAbacusable1 = RequestHandler::getValue('idAbacusable1');
  $idAbacusable2 = RequestHandler::getValue('idAbacusable2');
  $idAbacusable3 = RequestHandler::getValue('idAbacusable3');
  $idAbacusable4 = RequestHandler::getValue('idAbacusable4');
  $idAbacusable5 = RequestHandler::getValue('idAbacusable5');
  $idPhasing = RequestHandler::getValue('idPhasing');
  $abacusunit = RequestHandler::getValue('abacusunit');
  $sortOrders = RequestHandler::getValue('sortOrders');
  
  if (!$ids) {
    Sql::rollbackTransaction();
    echo '<div class="messageERROR">' . i18n('errorNoDataToSave') . '</div>';
    echo '<input type="hidden" id="lastOperationStatus" value="ERROR" />';
    echo '<input type="hidden" id="lastOperation" value="save" />';
    exit;
  }
  
  $idsArray = explode(',', $ids);
  $namesArray = explode('|', $names);
  $className1Array = explode('|', $className1);
  $className2Array = explode('|', $className2);
  $className3Array = explode('|', $className3);
  $className4Array = explode('|', $className4);
  $className5Array = explode('|', $className5);
  $idAbacusable1Array = explode('|', $idAbacusable1);
  $idAbacusable2Array = explode('|', $idAbacusable2);
  $idAbacusable3Array = explode('|', $idAbacusable3);
  $idAbacusable4Array = explode('|', $idAbacusable4);
  $idAbacusable5Array = explode('|', $idAbacusable5);
  $idPhasingArray = explode('|', $idPhasing);
  $abacusunitArray = explode('|', $abacusunit);
  $assignmentWorkType = RequestHandler::getValue('assignmentWorkType');
  $assignmentWorkTypeArray = explode('|', $assignmentWorkType);
  $sortOrdersArray = explode('|', $sortOrders);
  
  $allSuccess = true;
  $allNoChange = true;
  $newIds = array();
  
  foreach ($idsArray as $index => $id) {
    $isNew = (strpos($id, 'new_') === 0);
    
    if ($isNew) {
      $abacusDef = new AbacusDefinition();
    } else {
      $abacusDef = new AbacusDefinition($id);
    }
    
    $abacusDef->name = isset($namesArray[$index]) ? $namesArray[$index] : '';
    $abacusDef->className1 = isset($className1Array[$index]) ? $className1Array[$index] : '';
    $abacusDef->className2 = isset($className2Array[$index]) ? $className2Array[$index] : '';
    $abacusDef->className3 = isset($className3Array[$index]) ? $className3Array[$index] : '';
    $abacusDef->className4 = isset($className4Array[$index]) ? $className4Array[$index] : '';
    $abacusDef->className5 = isset($className5Array[$index]) ? $className5Array[$index] : '';
    $abacusDef->idAbacusable1 = isset($idAbacusable1Array[$index]) && $idAbacusable1Array[$index] !== '' ? $idAbacusable1Array[$index] : null;
    $abacusDef->idAbacusable2 = isset($idAbacusable2Array[$index]) && $idAbacusable2Array[$index] !== '' ? $idAbacusable2Array[$index] : null;
    $abacusDef->idAbacusable3 = isset($idAbacusable3Array[$index]) && $idAbacusable3Array[$index] !== '' ? $idAbacusable3Array[$index] : null;
    $abacusDef->idAbacusable4 = isset($idAbacusable4Array[$index]) && $idAbacusable4Array[$index] !== '' ? $idAbacusable4Array[$index] : null;
    $abacusDef->idAbacusable5 = isset($idAbacusable5Array[$index]) && $idAbacusable5Array[$index] !== '' ? $idAbacusable5Array[$index] : null;
    $abacusDef->idPhasing = isset($idPhasingArray[$index]) ? $idPhasingArray[$index] : null;
    $abacusDef->abacusunit = isset($abacusunitArray[$index]) ? $abacusunitArray[$index] : '%';
    $abacusDef->assignmentWorkType = isset($assignmentWorkTypeArray[$index]) ? $assignmentWorkTypeArray[$index] : 'fixed';
    $abacusDef->sortOrder = isset($sortOrdersArray[$index]) ? intval($sortOrdersArray[$index]) : ($index + 1);
    if ($isNew) {
      $abacusDef->idle = 0;
    }
    
    $res = $abacusDef->save();
    
    $hasOK = (stripos($res, 'id="lastOperationStatus" value="OK"') !== false);
    $hasNoChange = (stripos($res, 'id="lastOperationStatus" value="NO_CHANGE"') !== false);
    
    if (!$hasOK && !$hasNoChange) {
      $allSuccess = false;
      break;
    }
    
    if ($hasOK) $allNoChange = false;
    if ($isNew && $abacusDef->id) $newIds[$id] = $abacusDef->id;
  }
  
  if (!$allSuccess) {
    $result = $res;
    $result .= '<input type="hidden" id="lastOperationStatus" value="ERROR" />';
    $result .= '<input type="hidden" id="lastOperation" value="save" />';
  } else if ($allNoChange) {
    $result = i18n('noAbacusChanged').
    $result .= '<input type="hidden" id="lastOperationStatus" value="NO_CHANGE" />';
    $result .= '<input type="hidden" id="lastOperation" value="save" />';
  } else {
    $result = i18n('saveAbacusDefinition').
    $result .= '<input type="hidden" id="lastOperationStatus" value="OK" />';
    $result .= '<input type="hidden" id="lastOperation" value="save" />';
    if (count($newIds) > 0) {
      $result .= '<input type="hidden" id="newIds" value="' . htmlEncode(json_encode($newIds)) . '" />';
    }
  }
  
} else if ($action == 'delete') {
  $id = RequestHandler::getId('id');
  if (!$id) {
    $result = '<input type="hidden" id="lastOperationStatus" value="ERROR" />';
  }else {
    $abacusDef = new AbacusDefinition($id);
    $result = $abacusDef->delete();
  }
} else if ($action == 'copy') {
  $idAbacusDefinition = RequestHandler::getId('idAbacusDefinition');
  $name = RequestHandler::getValue('name');
  $idPhasing = RequestHandler::getValue('idPhasing');
  
  if (!$idAbacusDefinition) {
    $result = '<input type="hidden" id="lastOperationStatus" value="ERROR" />';
  } else {
    $abacusDef = new AbacusDefinition($idAbacusDefinition);
    $result = $abacusDef->copyAbacusDefinition($name, $idPhasing);
  }
} else if ($action == 'close') {
  $id = RequestHandler::getId('id');
  if (!$id) {
    $result = '<input type="hidden" id="lastOperationStatus" value="ERROR" />';
  } else {
    $abacusDef = new AbacusDefinition($id);
    $abacusDef->idle = 1;
    $result = $abacusDef->save();
  }
}


displayLastOperationStatus($result);
?>
