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
scriptLog('   ->/tool/saveAbacusLine.php');

$action = RequestHandler::getValue('action');
$idAbacusDefinition = RequestHandler::getId('idAbacusDefinition');

Sql::beginTransaction();
$result = '';
$res = '';

if ($action == 'close'){
  $id = RequestHandler::getId('id');
  $abacusLine = new AbacusLine($id);
  $abacusLine->idle = 1;
  $result = $abacusLine->save();
  
} else if ($action == 'reopen'){
  $id = RequestHandler::getId('id');
  $abacusLine = new AbacusLine($id);
  $abacusLine->idle = 0;
  $result = $abacusLine->save();
  
}else if ($action == 'save') {
  $hasValueChange = false;
  $ids = RequestHandler::getValue('ids');
  $assumption = RequestHandler::getValue('assumption');
  $example = RequestHandler::getValue('example');
  $className1 = RequestHandler::getValue('className1');
  $className2 = RequestHandler::getValue('className2');
  $className3 = RequestHandler::getValue('className3');
  $className4 = RequestHandler::getValue('className4');
  $className5 = RequestHandler::getValue('className5');
  
  if (!$ids || !$idAbacusDefinition) {
    Sql::rollbackTransaction();
    $result = '<div class="messageERROR">' . i18n('errorNoDataToSave') . '</div>';
    $result .= '<input type="hidden" id="lastOperationStatus" value="ERROR" />';
    $result .= '<input type="hidden" id="lastOperation" value="save" />';
    displayLastOperationStatus($result);
    exit;
  }
  
  $idsArray = explode(',', $ids);
  $assumptionArray = explode('|~|', $assumption);
  $exampleArray = explode('|~|', $example);
  
  $className1Array = $className1 ? explode('|', $className1) : array();
  $className2Array = $className2 ? explode('|', $className2) : array();
  $className3Array = $className3 ? explode('|', $className3) : array();
  $className4Array = $className4 ? explode('|', $className4) : array();
  $className5Array = $className5 ? explode('|', $className5) : array();
  
  $allSuccess = true;
  $allNoChange = true;
  $newIds = array();
  
  // Load phase values from request
  $phaseValues = array();
  $abacusDef = new AbacusDefinition($idAbacusDefinition);
  
  if ($abacusDef->idPhasing) {
    $phase = new Phase();
    $phases = $phase->getSqlElementsFromCriteria(array('idPhasing' => $abacusDef->idPhasing, 'idle' => '0'), false, null, 'sortOrder ASC');
    
    foreach ($phases as $ph) {
      $phaseId = $ph->id;
      $phaseValueStr = RequestHandler::getValue('phaseValue_' . $phaseId);
      if ($phaseValueStr !== null) {
        $phaseValues[$phaseId] = explode('|', $phaseValueStr);
      }
    }
  } else {
    // No phasing - single value column
    $phaseValueStr = RequestHandler::getValue('phaseValue_default');
    if ($phaseValueStr !== null) {
      $phaseValues['default'] = explode('|', $phaseValueStr);
    }
  }
  
  
  foreach ($idsArray as $index => $id) {
    $isNew = (strpos($id, 'new_') === 0);
    
    if ($isNew) $abacusLine = new AbacusLine();
    else $abacusLine = new AbacusLine($id);
    
    $abacusLine->idAbacusDefinition = $idAbacusDefinition;
    $abacusLine->assumption = isset($assumptionArray[$index]) ? $assumptionArray[$index] : '';
    $abacusLine->example = isset($exampleArray[$index]) ? $exampleArray[$index] : '';
    
    $abacusLine->idClassName1 = (count($className1Array) > 0 && isset($className1Array[$index]) && $className1Array[$index] !== '')
    ? extractClassNameId($className1Array[$index]) : null;
    
    $abacusLine->idClassName2 = (count($className2Array) > 0 && isset($className2Array[$index]) && $className2Array[$index] !== '')
    ? extractClassNameId($className2Array[$index]) : null;
    
    $abacusLine->idClassName3 = (count($className3Array) > 0 && isset($className3Array[$index]) && $className3Array[$index] !== '')
    ? extractClassNameId($className3Array[$index]) : null;
    
    $abacusLine->idClassName4 = (count($className4Array) > 0 && isset($className4Array[$index]) && $className4Array[$index] !== '')
    ? extractClassNameId($className4Array[$index]) : null;
    
    $abacusLine->idClassName5 = (count($className5Array) > 0 && isset($className5Array[$index]) && $className5Array[$index] !== '')
    ? extractClassNameId($className5Array[$index]) : null;
    
    $res = $abacusLine->save();
    
    $hasOK = (stripos($res, 'id="lastOperationStatus" value="OK"') !== false);
    $hasNoChange = (stripos($res, 'id="lastOperationStatus" value="NO_CHANGE"') !== false);
    
    if (!$hasOK && !$hasNoChange) {
      $allSuccess = false;
      break;
    }
    
    if ($hasOK) $allNoChange = false;
    
    $savedLineId = $abacusLine->id;
    
    if ($isNew && $savedLineId) {
      $newIds[$id] = $savedLineId;
    }
    
    // Save phase values for this line
    if ($savedLineId && count($phaseValues) > 0) {
      foreach ($phaseValues as $phaseId => $valuesArray) {
        if (isset($valuesArray[$index])) {
          $valueToSave = trim($valuesArray[$index]);
          
          $abacusValue = new AbacusValue();
          $criteria = array('idAbacusDefinition' => $idAbacusDefinition,'idAbacusLine' => $savedLineId);
          
          // Add idPhase to criteria
          if ($phaseId === 'default') {
            $criteria['idPhase'] = null;
          } else {
            $criteria['idPhase'] = $phaseId;
          }
          
          $existingValues = $abacusValue->getSqlElementsFromCriteria($criteria);
          
          if (count($existingValues) > 0) {
            $abacusValue = $existingValues[0];
          } else {
            // Create new value
            $abacusValue = new AbacusValue();
            $abacusValue->idAbacusDefinition = $idAbacusDefinition;
            $abacusValue->idAbacusLine = $savedLineId;
            $abacusValue->idPhase = ($phaseId === 'default') ? null : $phaseId;
          }
          
          if ($valueToSave !== '' && $valueToSave !== null) {
            $abacusValue->value = $valueToSave;
            $saveResult = $abacusValue->save();
            
            // Check if save was successful
            $valueHasOK = (stripos($saveResult, 'id="lastOperationStatus" value="OK"') !== false);
            
            if ($valueHasOK) {
              $allNoChange = false;
              $hasValueChange = true;
            }
            
          } else {
            // Delete if value is empty and record exists
            if ($abacusValue->id) {
              $abacusValue->delete();
              $allNoChange = false;
              $hasValueChange = true;
            }
          }
        }
      }
    }
  }
  
  if (!$allSuccess) {
    $result = $res;
    $result .= '<input type="hidden" id="lastOperationStatus" value="ERROR" />';
    $result .= '<input type="hidden" id="lastOperation" value="save" />';
  } else if ($allNoChange && !$hasValueChange) {
    $result = i18n('noAbacusChanged');
    $result .= '<input type="hidden" id="lastOperationStatus" value="NO_CHANGE" />';
    $result .= '<input type="hidden" id="lastOperation" value="save" />';
  } else {
    $result = i18n('saveAbacusLine');
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
    $result .= '<div class="messageERROR">' . i18n('errorOnDelete') . '</div>';
  } else {
    $abacusLine = new AbacusLine($id);
    
    // Delete associated AbacusValue records first
    $abacusValue = new AbacusValue();
    $valuesToDelete = $abacusValue->getSqlElementsFromCriteria(array(
        'idAbacusDefinition' => $abacusLine->idAbacusDefinition,
        'idAbacusLine' => $abacusLine->id
    ));
    
    foreach ($valuesToDelete as $val) {
      $val->delete();
    }
    
    // Then delete the line
    $result = $abacusLine->delete();
  }
}

displayLastOperationStatus($result);

function extractClassNameId($value) {
  if (!$value || $value === '') return null;
  if (strpos($value, 'pool_') === 0) return (int) substr($value, 5);
  if (strpos($value, 'res_') === 0) return (int) substr($value, 4);
  return (int) $value;
}
?>
