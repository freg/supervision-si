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
scriptLog('   ->/tool/saveAbacusPhase.php');

$action = RequestHandler::getValue('action');

Sql::beginTransaction();
$result = '';
$res = '';

if ($action == 'save') {
  $idPhasing = RequestHandler::getId('idPhasing');
  $ids = RequestHandler::getValue('ids');
  $shortNames = RequestHandler::getValue('shortNames');
  $fullNames = RequestHandler::getValue('fullNames');
  $durations = RequestHandler::getValue('durations');
  $sortOrders = RequestHandler::getValue('sortOrders');
  
  if (!$ids || !$idPhasing) {
    Sql::rollbackTransaction();
    echo '<div class="messageERROR">' . i18n('errorNoDataToSave') . '</div>';
    echo '<input type="hidden" id="lastOperationStatus" value="ERROR" />';
    echo '<input type="hidden" id="lastOperation" value="save" />';
    exit;
  }
  
  $idsArray = explode(',', $ids);
  $shortNamesArray = explode('|', $shortNames);
  $fullNamesArray = explode('|', $fullNames);
  $durationsArray = explode('|', $durations);
  $sortOrdersArray = explode('|', $sortOrders);
  
  $allSuccess = true;
  $allNoChange = true;
  $newIds = array();
  
  foreach ($idsArray as $index => $id) {
    $isNew = (strpos($id, 'new_') === 0);
    
    if ($isNew) {
      $phase = new Phase();
    } else {
      $phase = new Phase($id);
    }
    
    $phase->idPhasing = $idPhasing;
    $phase->shortName = isset($shortNamesArray[$index]) ? $shortNamesArray[$index] : '';
    $phase->name = isset($fullNamesArray[$index]) ? $fullNamesArray[$index] : '';
    
    // Duration must be an integer
    $durationValue = isset($durationsArray[$index]) ? trim($durationsArray[$index]) : '';
    if ($durationValue !== '') {
      // Convert to integer, remove any non-numeric characters
      $durationValue = preg_replace('/[^0-9-]/', '', $durationValue);
      $phase->duration = intval($durationValue);
    } else {
      $phase->duration = null;
    }
    
    $phase->sortOrder = isset($sortOrdersArray[$index]) ? intval($sortOrdersArray[$index]) : ($index + 1);
    $phase->idle = 0;
    
    $res = $phase->save();
    
    $hasOK = (stripos($res, 'id="lastOperationStatus" value="OK"') !== false);
    $hasNoChange = (stripos($res, 'id="lastOperationStatus" value="NO_CHANGE"') !== false);
    
    if (!$hasOK && !$hasNoChange) {
      $allSuccess = false;
      break;
    }
    
    if ($hasOK) $allNoChange = false;
    if ($isNew && $phase->id) $newIds[$id] = $phase->id;
  }
  
  if (!$allSuccess) {
    $result = $res;
    $result .= '<input type="hidden" id="lastOperationStatus" value="ERROR" />';
    $result .= '<input type="hidden" id="lastOperation" value="save" />';
  } else if ($allNoChange) {
    $result = i18n('noAbacusChanged');
    $result .= '<input type="hidden" id="lastOperationStatus" value="NO_CHANGE" />';
    $result .= '<input type="hidden" id="lastOperation" value="save" />';
  } else {
    $result = i18n('saveAbacusPhase');
    $result .= '<input type="hidden" id="lastOperationStatus" value="OK" />';
    $result .= '<input type="hidden" id="lastOperation" value="save" />';
    if (count($newIds) > 0) {
      $result .= '<input type="hidden" id="newIds" value="' . htmlEncode(json_encode($newIds)) . '" />';
    }
  }
  
} else if ($action == 'delete') {
  $id = RequestHandler::getId('id');
  if (!$id) {
    Sql::rollbackTransaction();
    $result = '<input type="hidden" id="lastOperationStatus" value="ERROR" />';
  } else {
    $phase = new Phase($id);
    $result = $phase->delete();
  }
} else if ($action == 'close') {
  $id = RequestHandler::getId('id');
  if (!$id) {
    Sql::rollbackTransaction();
    $result = '<input type="hidden" id="lastOperationStatus" value="ERROR" />';
  } else {
    $phase = new Phase($id);
    $phase->idle = 1;
    $result = $phase->save();
  }
}

displayLastOperationStatus($result);
?>
