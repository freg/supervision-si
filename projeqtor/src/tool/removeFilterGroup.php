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
 * FOR A PARTICULAR PURPOSE. See the GNU Affero General Public License for more
 * details.
 *
 *** DO NOT REMOVE THIS NOTICE ************************************************/

require_once "../tool/projeqtor.php";

$user=getSessionUser();
$comboDetail=pq_array_key_exists('comboDetail', $_REQUEST);

if (!pq_array_key_exists('filterObjectClass', $_REQUEST)) {
  throwError('filterObjectClass parameter not found in REQUEST');
}
$filterObjectClass=RequestHandler::getValue('filterObjectClass');
$markerReference=RequestHandler::getValue('filterGroupMarkerReference');
$name=RequestHandler::getValue('filterName');
$idLayout=RequestHandler::getValue('filterLayout');

if (!$comboDetail and pq_array_key_exists($filterObjectClass, $user->_arrayFilters)) {
  $filterArray=$user->_arrayFilters[$filterObjectClass];
} else if ($comboDetail and pq_array_key_exists($filterObjectClass, $user->_arrayFiltersDetail)) {
  $filterArray=$user->_arrayFiltersDetail[$filterObjectClass];
} else {
  $filterArray=array();
}

$error='';
$oldFilterArray=$filterArray;
$pairs=filterBuildGroupMarkerPairs($filterArray);
if (!$markerReference or !pq_array_key_exists($markerReference, $pairs)) {
  $error='groupMarkerNotFound';
} else {
  $references=array($markerReference);
  if ($pairs[$markerReference]!==null) {
    $references[]=$pairs[$markerReference];
  }
  foreach ($references as $reference) {
    if (preg_match('/^group-([0-9]+)$/', $reference, $matches)) {
      $id=intval($matches[1]);
      if (isset($filterArray[$id]) and filterIsGroupOnly($filterArray[$id])) {
        unset($filterArray[$id]);
      }
    } else if (preg_match('/^condition-([0-9]+)-(open|close)$/', $reference, $matches)) {
      $id=intval($matches[1]);
      $expectedGroup=($matches[2]=='open') ? 1 : 2;
      if (isset($filterArray[$id]['isGroup']) and intval($filterArray[$id]['isGroup'])==$expectedGroup) {
        $filterArray[$id]['isGroup']=0;
        $filterArray[$id]['indentLevel']=0;
      }
    }
  }
  $filterArray=array_values($filterArray);
  $error=filterRecalculateGroupLevels($filterArray, 3);
  if ($error!='') {
    $filterArray=$oldFilterArray;
  } else {
    filterNormalizeFirstLogicalOperator($filterArray);
  }
}

if (!$comboDetail) {
  $user->_arrayFilters[$filterObjectClass]=$filterArray;
  $user->_arrayFilters[$filterObjectClass . "FilterName"]=$name;
  $user->_arrayFilters[$filterObjectClass . "FilterLayout"]=$idLayout;
} else {
  $user->_arrayFiltersDetail[$filterObjectClass]=$filterArray;
  $user->_arrayFiltersDetail[$filterObjectClass . "FilterName"]=$name;
}

htmlDisplayFilterCriteria($filterArray, $name, $idLayout, $filterObjectClass);
echo '<input type="hidden" id="filterGroupRemoveError" value="' . htmlEncode($error) . '" />';
setSessionUser($user);

?>
