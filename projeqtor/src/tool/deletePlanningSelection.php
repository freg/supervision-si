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
 * Delete several items from Planning view.
 */

require_once "../tool/projeqtor.php";

function normalizePlanningDeleteClass($className) {
  if ($className=='Replan' or $className=='Construction' or $className=='Fixed') return 'Project';
  if ($className=='ProductVersionhasChild') return 'ProductVersion';
  if ($className=='ComponentVersionhasChild') return 'ComponentVersion';
  return $className;
}

if (! pq_array_key_exists('selection', $_REQUEST)) {
  throwError('selection parameter not found in REQUEST');
}
$selection=pq_trim($_REQUEST['selection']);
$selectList=pq_explode(';', $selection);

if (!$selection or count($selectList)==0) {
  $summary='<div class=\'messageWARNING\' >'.i18n('messageNoData', array(i18n('Planning')), ENT_QUOTES, 'UTF-8').'</div >';
  echo '<input type="hidden" id="summaryResult" value="'.$summary.'" />';
  exit;
}

$items=array();
foreach ($selectList as $selectedItem) {
  if (!pq_trim($selectedItem)) continue;
  $parts=pq_explode(':', $selectedItem);
  if (count($parts)!=2) continue;
  $className=normalizePlanningDeleteClass(pq_trim($parts[0]));
  $id=pq_trim($parts[1]);
  Security::checkValidClass($className);
  Security::checkValidId($id);
  $pe=SqlElement::getSingleSqlElementFromCriteria('PlanningElement', array('refType'=>$className, 'refId'=>$id));
  $items[]=array(
    'className'=>$className,
    'id'=>$id,
    'wbsSortable'=>($pe->id)?$pe->wbsSortable:'',
    'topRefType'=>($pe->id)?$pe->topRefType:'',
    'topRefId'=>($pe->id)?$pe->topRefId:'',
    'topId'=>($pe->id)?$pe->topId:''
  );
}

if (count($items)==0) {
  $summary='<div class=\'messageWARNING\' >'.i18n('messageNoData', array(i18n('Planning')), ENT_QUOTES, 'UTF-8').'</div >';
  echo '<input type="hidden" id="summaryResult" value="'.$summary.'" />';
  exit;
}

usort($items, function($a, $b) {
  if ($a['wbsSortable']==$b['wbsSortable']) return 0;
  if (!$a['wbsSortable']) return 1;
  if (!$b['wbsSortable']) return -1;
  return ($a['wbsSortable']>$b['wbsSortable'])?-1:1;
});

$cptOk=0;
$cptError=0;
$cptWarning=0;
$cptNoChange=0;
$needProjectListRefresh=false;
$renumberTargets=array();

echo "<table>";
SqlElement::setDeleteConfirmed();
$deleteObjectInProgress=true;
// Defer costly planning synthesis and revenue updates until every item has been processed.
PlanningElement::$_noDispatch=true;
PlanningElement::$_noDispatchArray=array();
PlanningElement::$_skipUpdateRevenue=true;
foreach ($items as $selectedItem) {
  $className=$selectedItem['className'];
  $id=$selectedItem['id'];
  if ($className=='Project') {
    Project::$_deleteProjectInProgress=true;
  }
  Sql::beginTransaction();
  echo '<tr>';
  echo '<td valign="top"><b>'.i18n($className).' #'.htmlEncode($id).'&nbsp;:&nbsp;</b></td>';

  $item=new $className($id);
  if (! $item->id) {
    Sql::rollbackTransaction();
    $cptWarning++;
    echo '<td><span class="messageWARNING" >'.i18n('messageItemDelete', array(i18n($className), $id)).'</span></td>';
    echo '</tr>';
    continue;
  }
  if (property_exists($item, 'locked') and $item->locked) {
    Sql::rollbackTransaction();
    $cptWarning++;
    echo '<td><span class="messageWARNING" >'.i18n($className).' #'.htmlEncode($item->id).' '.i18n('colLocked').'</span></td>';
    echo '</tr>';
    continue;
  }
  projeqtor_set_time_limit(600);
  $resultSave=$item->delete();
  $resultSave=pq_str_replace('<br/><br/>', '<br/>', $resultSave);
  $statusSave=getLastOperationStatus($resultSave);
  if ($statusSave=="ERROR") {
    Sql::rollbackTransaction();
    $cptError++;
  } else if ($statusSave=="OK") {
    Sql::commitTransaction();
    $cptOk++;
    if ($className=='Project') $needProjectListRefresh=true;
    if ($selectedItem['topRefType'] and $selectedItem['topRefId']) {
      PlanningElement::updateSynthesisNoDispatch($selectedItem['topRefType'], $selectedItem['topRefId']);
    }
    if ($selectedItem['topId']) {
      $renumberTargets[$selectedItem['topId']]=$selectedItem['topId'];
    }
  } else if ($statusSave=="NO_CHANGE") {
    Sql::commitTransaction();
    $cptNoChange++;
  } else {
    Sql::rollbackTransaction();
    $cptWarning++;
  }
  $displayStatus=($statusSave=='ERROR' or $statusSave=='OK' or $statusSave=='NO_CHANGE')?$statusSave:'WARNING';
  echo '<td><div style="padding: 0px 5px;" class="message'.$displayStatus.'" >'.$resultSave.'</div></td>';
  echo '</tr>';
}
echo "</table>";

PlanningElement::$_skipUpdateRevenue=false;
if ($cptOk) {
  // Reuse the planning move finalizer, then renumber each surviving parent only once.
  Sql::beginTransaction();
  PlanningElement::moveTaskFinalize();
  PlanningElement::$_noDispatch=false;
  foreach ($renumberTargets as $planningElementId) {
    $planningElement=new PlanningElement($planningElementId);
    if ($planningElement->id) {
      $planningElement->renumberWbs();
    }
  }
  Sql::commitTransaction();
} else {
  PlanningElement::$_noDispatch=false;
}

$summary="";
if ($cptError) {
  $summary.='<div class=\'messageERROR\' >'.$cptError." ".i18n('resultError').'</div>';
}
if ($cptOk) {
  $summary.='<div class=\'messageOK\' >'.$cptOk." ".i18n('resultOk').'</div>';
}
if ($cptWarning) {
  $summary.='<div class=\'messageWARNING\' >'.$cptWarning." ".i18n('resultWarning').'</div>';
}
if ($cptNoChange) {
  $summary.='<div class=\'messageNO_CHANGE\' >'.$cptNoChange." ".i18n('resultNoChange').'</div>';
}
echo '<input type="hidden" id="summaryResult" value="'.$summary.'" />';
if ($needProjectListRefresh) {
  echo '<input type="hidden" id="needProjectListRefresh" value="true" />';
}
?>
