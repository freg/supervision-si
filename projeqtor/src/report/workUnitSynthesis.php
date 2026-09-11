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

include_once '../tool/projeqtor.php';
include_once "../tool/jsonFunctions.php";

$paramProject=pq_trim(RequestHandler::getId('idProject'));
if(!$paramProject)exit;
$paramActivityType=pq_trim(RequestHandler::getId('idActivityType'));
$paramProduct = pq_trim(RequestHandler::getId('idProduct'));
$paramVersion = pq_trim(RequestHandler::getId('idVersion'));

$user=getSessionUser();

// Header
$headerParameters = i18n("colIdProject") . ' : ' . htmlEncode(SqlList::getNameFromId('Project', $paramProject)) . '<br/>';
if ($paramActivityType!="") {
	$headerParameters.= i18n("colIdActivityType") . ' : ' . SqlList::getNameFromId('ActivityType', $paramActivityType) . '<br/>';
}
if ($paramProduct!="") {
	$headerParameters.= i18n("colIdActivityType") . ' : ' . SqlList::getNameFromId('Product', $paramProduct) . '<br/>';
}
if ($paramVersion!="") {
	$headerParameters.= i18n("colIdActivityType") . ' : ' . SqlList::getNameFromId('Version', $paramVersion) . '<br/>';
}
//END OF THAT
include "header.php";

$proj = new Project(Sql::fmtId($paramProject));
$projectList = $proj->getRecursiveSubProjectsFlatList(false, true);
$lstIdProject = array();
foreach ($projectList as $id=>$name){
  $prj = new Project($id, true);
  if($proj->idCatalogUO == $proj->idCatalogUO)$lstIdProject[$prj->id]=$prj->id;
}
$where ="idProject in (" .implode(',', $lstIdProject).")";
if ($paramActivityType!="") {
	$where.=" and idActivityType=" . Sql::fmtId($paramActivityType) ;
}
if ($paramProduct!="") {
	$where .= 'and idProduct='.Sql::fmtId($paramProduct);
}
if ($paramVersion!="") {
	$where .= 'and idVersion='.Sql::fmtId($paramVersion);
}

$order="idProject";
$activity=new Activity();
$lstActivity=$activity->getSqlElementsFromCriteria(null,false, $where, $order);
$lstIdActivity = array();
foreach ($lstActivity as $act){
  $lstIdActivity[$act->id]=$act->id;
}
$lstIdActivity = implode(',', $lstIdActivity);
$actWorkUnit = new ActivityWorkUnit();
$where = "refType='Activity' and refId in ($lstIdActivity)";
$lstActWorkUnit = $actWorkUnit->getSqlElementsFromCriteria(null,false, $where);

$workUnit = new WorkUnit();
$lstWorkUnit = $workUnit->getSqlElementsFromCriteria(array('idCatalogUO'=>$proj->idCatalogUO));

$complexity = new Complexity();
$lstComplexity = $complexity->getSqlElementsFromCriteria(array('idCatalogUO'=>$proj->idCatalogUO));

$complexityVal = new ComplexityValues();
$lstComplexityVal = $complexityVal->getSqlElementsFromCriteria(array('idCatalogUO'=>$proj->idCatalogUO));

$workUnitSynthesis = array();
foreach ($lstWorkUnit as $wU){
  foreach ($lstComplexity as $comp){
    foreach ($lstActWorkUnit as $actWU){
      if(isset($workUnitSynthesis[$wU->id][$comp->id]['quantity'])){
        if($actWU->idComplexity == $comp->id and $actWU->idWorkUnit == $wU->id){
          $workUnitSynthesis[$wU->id][$comp->id]['quantity'] += intval($actWU->quantity);
        }
      }else{
        if($actWU->idComplexity == $comp->id and $actWU->idWorkUnit == $wU->id){
        	$workUnitSynthesis[$wU->id][$comp->id]['quantity'] = intval($actWU->quantity);
        }else{
            $workUnitSynthesis[$wU->id][$comp->id]['quantity'] = 0;
        }
      }
    }
    foreach ($lstComplexityVal as $compVal){
      if($compVal->idComplexity == $comp->id and $compVal->idWorkUnit == $wU->id){
        $workUnitSynthesis[$wU->id][$comp->id]['revenue'] = floatval($compVal->price);
      }
    }
  }
}
if (checkNoData($workUnitSynthesis)) if (!empty($cronnedScript)) goto end; else exit;

echo '<table style="width:95%;text-align:center" '.excelName().' align="center">';
echo '<tr>';
echo '<td style="width:15%"'.excelFormatCell('header',30).'></td>';
$colspan = count($lstComplexity);
$width = 75/(($colspan*2)+1);
echo '<td colspan="'.$colspan.'" class="reportTableHeader" style=""'.excelFormatCell('header',(20*$colspan)).'>'.i18n('quantity').'</td>';
$colspan = count($lstComplexity)+1;

echo '<td colspan="'.$colspan.'" class="reportTableHeader" style=""'.excelFormatCell('header',(20*$colspan)).'>'.i18n('sectionRevenue').'</td>';
echo '</tr>';
echo '<tr>';
echo '<td class="reportTableHeader" style="width:15%"'.excelFormatCell('header',30).'>' . i18n('ActivityWorkUnit') . '</td>';
foreach ($workUnitSynthesis as $idWorkUnit=>$compList){
  foreach ($compList as $idComlexity=>$actWorkUList){
    echo '<td class="reportTableHeader" style="width:'.$width.'%"'.excelFormatCell('header',20).'>'.SqlList::getNameFromId('Complexity', $idComlexity).'</td>';
  }
  break;
}
foreach ($workUnitSynthesis as $idWorkUnit=>$compList){
	foreach ($compList as $idComlexity=>$actWorkUList){
		echo '<td class="reportTableHeader" style="width:'.$width.'%"'.excelFormatCell('header',20).'>'.SqlList::getNameFromId('Complexity', $idComlexity).'</td>';
	}
  break;
}
echo '<td class="reportTableHeader" style="width:'.$width.'%"'.excelFormatCell('header',20).'>'.i18n('sum').'</td>';
echo '</tr>';
foreach ($lstWorkUnit as $workUnit){
  echo '<tr>';
  echo '<td class="reportTableData" style="width:15%"'.excelFormatCell('data',30).'>'.$workUnit->name.'</td>';
  foreach ($lstComplexity as $complexity){
    $quantity = 0;
    if(isset($workUnitSynthesis[$workUnit->id][$complexity->id]['quantity'])){
    	$quantity = $workUnitSynthesis[$workUnit->id][$complexity->id]['quantity'];
    }
    echo '<td class="reportTableData" '.excelFormatCell('data',20).'>'.$quantity.'</td>';
  }
  $revenueSum = 0;
  foreach ($lstComplexity as $complexity){
    $revenue = 0;
    if(isset($workUnitSynthesis[$workUnit->id][$complexity->id]['revenue']) and isset($workUnitSynthesis[$workUnit->id][$complexity->id]['quantity'])){
      $revenue = $workUnitSynthesis[$workUnit->id][$complexity->id]['quantity']*$workUnitSynthesis[$workUnit->id][$complexity->id]['revenue'];
    }
    $revenueSum += $revenue;
  	echo '<td class="reportTableData" style="text-align:right;" '.excelFormatCell('data',20,null,null,null,'right').'>'.(($outMode=='excel')?$revenue:htmlDisplayCurrency($revenue, true)).'</td>';
  }
  echo '<td class="reportTableData" style="text-align:right;" '.excelFormatCell('data',20,null,null,null,'right').'>'.(($outMode=='excel')?$revenueSum:htmlDisplayCurrency($revenueSum, true)).'</td>';
  echo '</tr>';
}
echo '</table>';

end: