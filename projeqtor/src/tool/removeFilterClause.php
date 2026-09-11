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

$user=getSessionUser();

$comboDetail=false;
if (pq_array_key_exists('comboDetail',$_REQUEST)) {
  $comboDetail=true;
}

if (! $comboDetail and ! $user->_arrayFilters) {
  $user->_arrayFilters=array();
} else if ($comboDetail and ! $user->_arrayFiltersDetail) {
  $user->_arrayFiltersDetail=array();
}


// Get the filter info
if (! pq_array_key_exists('filterClauseId',$_REQUEST)) {
  throwError('filterClauseId parameter not found in REQUEST');
}
$filterClauseId=$_REQUEST['filterClauseId'];
if (! pq_array_key_exists('filterObjectClass',$_REQUEST)) {
  throwError('filterObjectClass parameter not found in REQUEST');
}
$filterObjectClass=$_REQUEST['filterObjectClass'];
$name="";
if (pq_array_key_exists('filterName',$_REQUEST)) {
  $name=$_REQUEST['filterName'];
}
pq_trim($name);
$idLayout="";
if (pq_array_key_exists('filterLayout',$_REQUEST)) {
  $idLayout=$_REQUEST['filterLayout'];
}
// Get existing filter info
if (!$comboDetail and pq_array_key_exists($filterObjectClass,$user->_arrayFilters)) {
  $filterArray=$user->_arrayFilters[$filterObjectClass];
} else if ($comboDetail and pq_array_key_exists($filterObjectClass,$user->_arrayFiltersDetail)) {
  $filterArray=$user->_arrayFiltersDetail[$filterObjectClass];
} else {
  $filterArray=array();
}

if ($filterClauseId=='all') {
  $filterArray=array();
} else {
  $filterCriteria = new FilterCriteria($filterClauseId);
  
  $deleted = $filterArray[$filterClauseId];
  $groupOnly=filterIsGroupOnly($deleted);
  unset($filterArray[$filterClauseId]);
  $deletedIndent = isset($deleted['indentLevel']) ? $deleted['indentLevel'] : 0;
  $filterArray = array_values($filterArray);
  $nextKey = $filterClauseId;
  if (!$groupOnly && isset($deleted['isGroup']) && $deleted['isGroup'] == 1) {
    $hasChildren = false;
    $countChildren = 0;
    for ($i = $nextKey; $i < count($filterArray); $i++) {
      if (pq_array_key_exists('indentLevel', $filterArray[$i]) 
          && ($filterArray[$i]['indentLevel'] == $deletedIndent
               || ($filterArray[$i]['indentLevel'] == $deletedIndent-1 && $filterArray[$i]['isGroup']== 2) )) {
        $hasChildren = true;
        $countChildren += 1;
      }
      if (pq_array_key_exists('isGroup', $filterArray[$i]) && $filterArray[$i]['isGroup'] == 2){
        break;
      }
    }      
    if (!$hasChildren) {
      foreach ($filterArray as &$crit) {
        if (isset($crit['isGroup'], $crit['indentLevel']) && $crit['isGroup'] == 2 && $crit['indentLevel'] == $deletedIndent - 1) {
          $crit['isGroup'] = 0;
          $crit['orOperator'] = $deleted['orOperator'];
          break;
        }
      }
      unset($crit);
    }
    if ($hasChildren) {
      for ($i = $nextKey; $i < count($filterArray); $i++) {
        if (pq_array_key_exists('indentLevel', $filterArray[$i]) && $filterArray[$i]['indentLevel'] == $deletedIndent || $filterArray[$i]['indentLevel'] == $deletedIndent + 1) {
          $filterArray[$i]['orOperator'] = $deleted['orOperator'];
          $filterArray[$i]['isGroup'] = 1;
          $filterArray[$i]['indentLevel'] = $deletedIndent;         
          break;
        }
        if (pq_array_key_exists('indentLevel', $filterArray[$i]) && $filterArray[$i]['indentLevel'] < $deletedIndent) {
          if ($countChildren=1){
            $filterArray[$i]['isGroup'] = 0;
            $filterArray[$i]['orOperator'] = $deleted['orOperator'];
          }
          break;
        }
      }
    }
  } 
  if (!$groupOnly && isset($deleted['isGroup']) && $deleted['isGroup'] == 2) {
    $deletedIndent = $deleted['indentLevel'];
    $groupStartIndex = -1;
    for ($i = $filterClauseId - 1; $i >= 0; $i--) {
      if (pq_array_key_exists('isGroup', $filterArray[$i]) && $filterArray[$i]['isGroup'] == 1 &&
        $filterArray[$i]['indentLevel'] == $deletedIndent + 1) {
        $groupStartIndex = $i;
        break;
      }
    }
    if ($groupStartIndex !== -1) {
      $hasOther = false;
      for ($j = $groupStartIndex + 1; $j < $filterClauseId; $j++) {
        if (pq_array_key_exists('indentLevel', $filterArray[$j]) && $filterArray[$j]['indentLevel'] >= $deletedIndent + 1) {
          $hasOther = true;
          break;
        }
      }
      if (!$hasOther) {
        $filterArray[$groupStartIndex]['isGroup'] = 0;
        $filterArray[$groupStartIndex]['indentLevel'] = $deletedIndent;
      } else {
        for ($j = $filterClauseId - 1; $j > $groupStartIndex; $j--) {
          if (pq_array_key_exists('indentLevel', $filterArray[$j]) && $filterArray[$j]['indentLevel'] >= $deletedIndent + 1) {
            $filterArray[$j]['isGroup'] = 2;
            $filterArray[$j]['indentLevel'] = $deletedIndent;
            break;
          }
        }
      }
    }
  } 
  
  if (isset($deleted['isGroup']) && ($deleted['isGroup'] != 2 || $deleted['isGroup'] != 1)){
    if ($filterClauseId == 0){
      $filterArray[0]['orOperator'] = 0;
    }
    if (!isset($filterArray[0]['disp'])) {
      unset($filterArray[0]);
    }
  }
  filterRecalculateGroupLevels($filterArray, 3);
  filterNormalizeFirstLogicalOperator($filterArray);
}

if (! $comboDetail) {
  $user->_arrayFilters[$filterObjectClass]=$filterArray;
  $user->_arrayFilters[$filterObjectClass . "FilterName"]="";
  $user->_arrayFilters[$filterObjectClass . "FilterLayout"]="";
} else {
	$user->_arrayFiltersDetail[$filterObjectClass]=$filterArray;
  $user->_arrayFiltersDetail[$filterObjectClass . "FilterName"]="";
}
htmlDisplayFilterCriteria($filterArray,$name,$idLayout,$filterObjectClass);

// save user (for filter saving)
setSessionUser($user);


?>
