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
 * You should have received a copy of the GNU Affero General Public License along with
 * ProjeQtOr. If not, see <http://www.gnu.org/licenses/>.
 *
 *** DO NOT REMOVE THIS NOTICE ************************************************/

require_once "../tool/projeqtor.php";

$user=getSessionUser();
$comboDetail=pq_array_key_exists('comboDetail', $_REQUEST);

if (!$comboDetail and !$user->_arrayFilters) {
  $user->_arrayFilters=array();
} else if ($comboDetail and !$user->_arrayFiltersDetail) {
  $user->_arrayFiltersDetail=array();
}

if (!pq_array_key_exists('filterObjectClass', $_REQUEST)) {
  throwError('filterObjectClass parameter not found in REQUEST');
}
$filterObjectClass=RequestHandler::getValue('filterObjectClass');
$conditionPosition=RequestHandler::getNumeric('filterGroupConditionPosition');
$conditionOrder=RequestHandler::getNumeric('filterGroupConditionOrder');
$action=RequestHandler::getValue('filterGroupAction');
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
$nextConditionOrder=$conditionOrder;
if (($action!='open' and $action!='close') or $conditionPosition===null or $conditionOrder===null) {
  $error='noLine';
} else {
  $filterArray=array_values($filterArray);
  $oldFilterArray=$filterArray;
  $visiblePosition=0;
  $selectedIndex=null;
  foreach ($filterArray as $id=>$filter) {
    if (isset($filter['hidden']) and $filter['hidden']=='1') {
      continue;
    }
    if ($visiblePosition==$conditionPosition and !filterIsGroupOnly($filter)) {
      $selectedIndex=$id;
      break;
    }
    $visiblePosition++;
  }
  if ($selectedIndex===null) {
    $error='noLine';
  } else {
    $insertIndex=$selectedIndex;
    if ($action=='open') {
      $hasOpen=(isset($filterArray[$selectedIndex]['isGroup']) and intval($filterArray[$selectedIndex]['isGroup'])==1);
      if ($selectedIndex>0 and filterIsGroupOnly($filterArray[$selectedIndex-1])
          and isset($filterArray[$selectedIndex-1]['isGroup'])
          and intval($filterArray[$selectedIndex-1]['isGroup'])==1) {
        $hasOpen=true;
      }
      if ($hasOpen) {
        $error='alreadyOpen';
      }
    } else {
      $insertIndex=$selectedIndex+1;
      while ($insertIndex<count($filterArray)
          and filterIsGroupOnly($filterArray[$insertIndex])
          and isset($filterArray[$insertIndex]['isGroup'])
          and intval($filterArray[$insertIndex]['isGroup'])==2) {
        $insertIndex++;
      }
    }
    if ($error=='') {
      $groupMarker=array(
          'disp'=>array('attribute'=>'', 'operator'=>'', 'value'=>''),
          'sql'=>array('attribute'=>'', 'operator'=>'GROUP', 'value'=>$action),
          'isDynamic'=>'0',
          'orOperator'=>'0',
          'isGroup'=>($action=='open') ? 1 : 2,
          'indentLevel'=>0,
          'groupOnly'=>'1'
      );
      array_splice($filterArray, $insertIndex, 0, array($groupMarker));
      $error=filterRecalculateGroupLevels($filterArray, 3);
      if ($action=='close' and $error=='notEnoughGroupContent') {
        $filterArray=$oldFilterArray;
        $openingRemoved=false;
        if (isset($filterArray[$selectedIndex]['isGroup'])
            and intval($filterArray[$selectedIndex]['isGroup'])==1) {
          $filterArray[$selectedIndex]['isGroup']=0;
          $openingRemoved=true;
        } else if ($selectedIndex>0
            and filterIsGroupOnly($filterArray[$selectedIndex-1])
            and isset($filterArray[$selectedIndex-1]['isGroup'])
            and intval($filterArray[$selectedIndex-1]['isGroup'])==1) {
          array_splice($filterArray, $selectedIndex-1, 1);
          $selectedIndex--;
          $openingRemoved=true;
        }
        if ($openingRemoved) {
          $insertIndex=$selectedIndex+1;
          while ($insertIndex<count($filterArray)
              and filterIsGroupOnly($filterArray[$insertIndex])
              and isset($filterArray[$insertIndex]['isGroup'])
              and intval($filterArray[$insertIndex]['isGroup'])==2) {
            $insertIndex++;
          }
          $groupMarker['sql']['value']='close';
          $groupMarker['isGroup']=2;
          array_splice($filterArray, $insertIndex, 0, array($groupMarker));
          $error=filterRecalculateGroupLevels($filterArray, 3);
        }
      }
      if ($error!='') {
        $filterArray=$oldFilterArray;
      } else {
        filterNormalizeFirstLogicalOperator($filterArray);
      }
    }
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
echo '<input type="hidden" id="filterGroupUpdateError" value="' . htmlEncode($error) . '" />';
echo '<input type="hidden" id="filterGroupNextConditionOrder" value="' . htmlEncode($nextConditionOrder) . '" />';
setSessionUser($user);

?>
