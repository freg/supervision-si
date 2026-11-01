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
scriptLog('   ->/tool/saveAbacusable.php');

$action = RequestHandler::getValue('action');
$id = RequestHandler::getId('id');
$className = RequestHandler::getValue('selectedName');

Sql::beginTransaction();

if ($action == 'update') {
  $valueFields = RequestHandler::getValue('valueFields');
  $inputFields = RequestHandler::getValue('inputFields');
  if (!$valueFields && !$inputFields) {
    $result = '<div class="NO_CHANGE">' . i18n('errorNoDataToSave') . '</div>';
    $result .= '<input type="hidden" id="lastOperationStatus" value="NO_CHANGE" />';
    $result .= '<input type="hidden" id="lastOperation" value="update" />';
    echo $result;
    exit;
  }
  
  $valueFieldsArray = array();
  $inputFieldsArray = array();
  
  if ($valueFields) {
    $items = explode(',', $valueFields);
    foreach ($items as $item) {
      if (empty($item)) continue;
      list($itemId, $itemValue) = explode(':', $item);
      $valueFieldsArray[intval($itemId)] = intval($itemValue);
    }
  }
  
  if ($inputFields) {
    $items = explode(',', $inputFields);
    foreach ($items as $item) {
      if (empty($item)) continue;
      list($itemId, $itemValue) = explode(':', $item);
      $inputFieldsArray[intval($itemId)] = intval($itemValue);
    }
  }
  
  $allIds = array_unique(array_merge(array_keys($valueFieldsArray), array_keys($inputFieldsArray)));
  
  $allSuccess = true;
  $allNoChange = true;
  $errorMessages = array();
  
  foreach ($allIds as $itemId) {
    try {
      $abacusable = new Abacusable($itemId);
      $oldValueField = isset($abacusable->valueField) ? $abacusable->valueField : 0;
      $oldInputField = isset($abacusable->inputField) ? $abacusable->inputField : 0;
      
      $newValueField = isset($valueFieldsArray[$itemId]) ? $valueFieldsArray[$itemId] : 0;
      $newInputField = isset($inputFieldsArray[$itemId]) ? $inputFieldsArray[$itemId] : 0;
      
      if ($newInputField == 1 && $newValueField == 0) {
        $newInputField = 0;
      }
      
      $hasChange = ($oldValueField != $newValueField) || ($oldInputField != $newInputField);
      
      if ($hasChange) {
        $abacusable->valueField = $newValueField;
        $abacusable->inputField = $newInputField;
        
        $res = $abacusable->save();
        
        $hasOK = (stripos($res, 'id="lastOperationStatus" value="OK"') !== false);
        $hasError = (stripos($res, 'id="lastOperationStatus" value="ERROR"') !== false);
        $hasInvalid = (stripos($res, 'id="lastOperationStatus" value="INVALID"') !== false);
        
        if ($hasError || $hasInvalid) {
          $allSuccess = false;
          if (preg_match('/<div class="(INVALID|ERROR)">(.*?)<\/div>/s', $res, $matches)) {
            $errorMessages[] = strip_tags($matches[2]);
          } else {
            $errorMessages[] = "Item ID $itemId: " . i18n('errorSaving');
          }
        } elseif ($hasOK) {
          $allNoChange = false;
        }
      }
      
    } catch (Exception $e) {
      $allSuccess = false;
      $errorMessages[] = "Item ID $itemId: " . $e->getMessage();
    }
  }
  
  if (!$allSuccess) {
    $result = '<div class="INVALID">';
    $result .= implode('<br/>', $errorMessages);
    $result .= '</div>';
    $result .= '<input type="hidden" id="lastOperationStatus" value="INVALID" />';
    $result .= '<input type="hidden" id="lastOperation" value="update" />';
  } elseif ($allNoChange) {
    $result = i18n('noAbacusChanged');
    $result .= '<input type="hidden" id="lastOperationStatus" value="NO_CHANGE" />';
    $result .= '<input type="hidden" id="lastOperation" value="update" />';
  } else {
    $result = i18n('updateAbacusable');
    $result .= '<input type="hidden" id="lastOperationStatus" value="OK" />';
    $result .= '<input type="hidden" id="lastOperation" value="update" />';
    $result .= '<input type="hidden" id="lastOperationId" value="0" />';
  }
}else if ($action == 'remove') {
  if ($id) {
    $abacusable = new Abacusable($id);
  }
  $result = $abacusable->delete();
} else if ($action == 'add') { 
  if (!$className) {
    $result = '<div class="messageERROR">' . i18n('errorClassNameRequired') . '</div> ';
    $result .= '<input type="hidden" id="lastOperationStatus" value="ERROR" />';
  } else {
    $abacusable = new Abacusable();
    $crit = array('className' => $className);
    $list = $abacusable->getSqlElementsFromCriteria($crit);
    if (count($list) > 2) {
      Sql::rollbackTransaction();
      $result = '<div class="INVALID">' . i18n('errorClassAlreadyExists') . '</div>';
      $result .= '<input type="hidden" id="lastOperationStatus" value="ERROR" />';
      exit;
    }
    $abacusable->className = $className;
    $abacusable->valueField = 0;
    
    $result = $abacusable->save();
  }

}

displayLastOperationStatus($result);

?>
