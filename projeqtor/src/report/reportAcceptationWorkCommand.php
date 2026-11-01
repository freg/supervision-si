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

// Header
include_once '../tool/projeqtor.php';
include_once('../tool/formatter.php');

//param recovery
$paramProject=pq_trim(RequestHandler::getId('idProject',false));
$paramShowIdle = RequestHandler::getBoolean('showClosedItems');
$year=RequestHandler::getYear('yearSpinner');
$month=RequestHandler::getMonth('monthSpinner');
if (!$month or $month == '')$month="1";

// param Header
$headerParameters="";
if ($paramProject!="") {
  $headerParameters.= i18n("colIdProject") . ' : ' . htmlEncode(SqlList::getNameFromId('Project', $paramProject)) . '<br/>';
}
if ($year!="") {
  $headerParameters.= i18n("year") . ' : ' . $year . '<br/>';
}
if ($month!="") {
  $headerParameters.= i18n("month") . ' : ' . $month  . '<br/>';
}
include "header.php";

//Query for workCommand
$where=getAccesRestrictionClause('WorkCommand',false,false,true,true);
if ($paramProject!='') {
  $where.=  " and idProject in " . getVisibleProjectsList(true, $paramProject) ;
}
$where .=' and elementary=1';
$order="idProject asc, name asc";

$wCmd = new WorkCommand();
$lstWCmd = $wCmd->getSqlElementsFromCriteria(null,false, $where, $order);

//Month/Year System
if ($month and $month<10) $month='0'.intval($month);
if ($month=="01") {
  $endMonth = "12";
} else {
  $endMonth = intval($month) - 1;
  if ($endMonth<10) $endMonth='0'.intval($endMonth);
}
$endYear = ($month=="1") ? $year : $year + 1;

//Query for WorkCommandAccept
$lastDayOfMonth=lastDayOfMonth($endMonth,$endYear);
$where="where acceptedDate>= '$year-$month-01'";
$where.=" and acceptedDate<='$endYear-$endMonth-$lastDayOfMonth'";
if ($paramProject!='') {
  $where.=  " and idProject in " . getVisibleProjectsList(true, $paramProject) ;
}
$where.= " and wca.acceptedQuantity>0 ";
$order=" order by acceptedDate asc";

$wCmdAcpt = new WorkCommandAccepted();
$query = "SELECT wca.idWorkCommand, wca.acceptedDate, wca.acceptedQuantity, wc.unitAmount FROM ".$wCmdAcpt->getDatabaseTableName()." wca JOIN ".$wCmd->getDatabaseTableName()." wc ON wca.idWorkCommand = wc.id " . $where . $order;
// Execute the Query
$result = Sql::query($query);
$lstWCmdAcpt = array();

//column size
$col1="3";
$col2="10";
$col3="15";

$tabWCmd = array();

//date recovery for workCommand
foreach ( $lstWCmd as $wCmd){
  if(!isset($tabWCmd[$wCmd->id])){
    $tabWCmd[$wCmd->id]=array();
  }

  if(!isset($tabWCmd[$wCmd->id]['commandQuantity'])){
    $tabWCmd[$wCmd->id]['commandQuantity']=0;
  }
  $tabWCmd[$wCmd->id]['commandQuantity']+=$wCmd->commandQuantity;

  if(!isset($tabWCmd[$wCmd->id]['commandAmount'])){
    $tabWCmd[$wCmd->id]['commandAmount']=0;
  }
  $tabWCmd[$wCmd->id]['commandAmount']+=$wCmd->commandAmount;
  
  if(!isset($tabWCmd[$wCmd->id]['TotalAmountAccepted'])){
    $tabWCmd[$wCmd->id]['TotalAmountAccepted']=0;
  }
  $tabWCmd[$wCmd->id]['TotalAmountAccepted']+=$wCmd->acceptedAmount;
  
  if(!isset($tabWCmd[$wCmd->id]['TotalLeftAmountAccepted'])){
    $tabWCmd[$wCmd->id]['TotalLeftAmountAccepted']=0;
  }
  $tabWCmd[$wCmd->id]['TotalLeftAmountAccepted']=$tabWCmd[$wCmd->id]['commandAmount']-$tabWCmd[$wCmd->id]['TotalAmountAccepted'];
  
  if(!isset($tabWCmd[$wCmd->id]['TotalLeftAccepted'])){
    $tabWCmd[$wCmd->id]['TotalLeftAccepted']=0;
  }
  if(!isset($tabWCmd[$wCmd->id]['Acceptation'])){
    $tabWCmd[$wCmd->id]['Acceptation']=array();
  }
}
//No data print
if(!isset($tabWCmd[$wCmd->id]['commandQuantity'])){
  echo '<div style="background: #FFDDDD;font-size:150%;color:#808080;text-align:center;padding:20px">';
  echo i18n('reportNoData');
  echo '</div>';
  return;
}
//data recovery for workCommandAccept 
while ( $line = Sql::fetchLine($result)) {
  $acceptedMonth = date('Y-m', strtotime($line['acceptedDate']));
  if(!isset($tabWCmd[$line['idWorkCommand']]['Acceptation'][$acceptedMonth])){
    $tabWCmd[$line['idWorkCommand']]['Acceptation'][$acceptedMonth]=0;
  }
  if(!isset($tabWCmd[$line['idWorkCommand']]['TotalAccepted'])){
    $tabWCmd[$line['idWorkCommand']]['TotalAccepted']=0;
  }
  if(!isset($tabWCmd[$line['idWorkCommand']]['TotalAmoutAccept'])){
    $tabWCmd[$line['idWorkCommand']]['TotalAmoutAccept']=0;
  }
  $tabWCmd[$line['idWorkCommand']]['Acceptation'][$acceptedMonth]+=$line['acceptedQuantity'];
  
  $tabWCmd[$line['idWorkCommand']]['TotalAccepted']+=$line['acceptedQuantity'];;
  
  $tabWCmd[$line['idWorkCommand']]['TotalAmoutAccept']+=($line['acceptedQuantity'] * $line['unitAmount']);
}
//data recovery for TotalLeftAccepted 
$tabWCmdTotalLeftAccept=array();
foreach ( $lstWCmd as $wCmd){
  $tabWCmdTotalLeftAccept[$wCmd->id]['TotalLeftAccepted']= $tabWCmd[$wCmd->id]['commandQuantity']-$wCmd->acceptedQuantity;
}

//start Table
echo '<table  width="95%" align="center">';

//Header
echo'<tr>';
echo' <td class="reportTableHeader"  style="vertical-align: bottom; width:'.$col2.'%" '.excelFormatCell('header',20).'>'.pq_ucfirst(i18n('WorkCommand')).'</td>';
echo' <td class="reportTableHeader"  style="vertical-align: bottom; width:'.$col1.'%" '.excelFormatCell('header',20).'>'.pq_ucfirst(i18n('numberWorkUnit')).'</td>';
//month argument print
$yearTemp=$year;
$monthTemp=$month;
for($i=$monthTemp; $i<=12; $i++){
  $date=date('m/Y', strtotime($yearTemp."-".$i));
  echo' <td class="reportHeader"  style="width:'.$col1.'%; writing-mode: vertical-lr; text-orientation: mixed; transform: rotate(180deg);" '.excelFormatCell('header',20).'>'.$date."</br>".pq_ucfirst(i18n('quantityReceived')).'</td>';
}
//month argument print
$yearTemp++;
for($i=1; $i<=$month-1; $i++){
  $date=date('m/Y', strtotime($yearTemp."-".$i));
  echo' <td class="reportTableHeader"  style="width:'.$col1.'%; writing-mode: vertical-lr; text-orientation: mixed; transform: rotate(180deg);" '.excelFormatCell('header',20).'>'.$date."</br>".pq_ucfirst(i18n('quantityReceived')).'</td>';
}

echo' <td class="reportTableHeader"  style="vertical-align: bottom; width:'.$col1.'%" '.excelFormatCell('header',20).'>'.pq_ucfirst(i18n('totalItemReceived')).'</td>';
echo' <td class="reportTableHeader"  style="vertical-align: bottom; width:'.$col2.'%" '.excelFormatCell('header',20).'>'.pq_ucfirst(i18n('amountStillReceived')).'</td>';
echo' <td class="reportTableHeader"  style="vertical-align: bottom; width:'.$col2.'%" '.excelFormatCell('header',20).'>'.pq_ucfirst(i18n('amountTotalReceived')).'</td>';
echo' <td class="reportTableHeader"  style="vertical-align: bottom; width:'.$col2.'%" '.excelFormatCell('header',20).'>'.pq_ucfirst(i18n('restItemReceived')).'</td>';
echo'</tr>';

//data print
foreach ($tabWCmd as $idWorkCommand=>$workCommand){
  echo'<tr>';
    echo '<td class="reportTableColumnHeader" style="text-align:center; border:1px solid #6f6f6f; width:'.$col2.'%" '.excelFormatCell('data',20,null,null,null,'right').'>'.SqlList::getNameFromId('WorkCommand', $idWorkCommand).'</td>';
    echo '<td class="reportTableColumnHeader" style="text-align:center; border:1px solid #6f6f6f; width:'.$col1.'%" '.excelFormatCell('data',20,null,null,null,'right').'>'.$workCommand['commandQuantity'].'</td>';
    //month argument data
    $yearTemp=$year;
    $monthTemp=$month;
    for($i=$monthTemp; $i<=12; $i++){
      $date=date('Y-m', strtotime($yearTemp."-".$i));
      $amountByDate = 0;
      foreach ($workCommand['Acceptation'] as $dateAcceptation => $amount) {
        if($date == date('Y-m', strtotime($dateAcceptation))){
         $amountByDate = intval($amount);
        }
      }
      echo '<td class="reportTableLineHeader" style="text-align:center; width:'.$col1.'%" '.excelFormatCell('data',20,null,null,null,'right').'>'.$amountByDate.'</td>';
    }
    //month argument data 
    $yearTemp++;
    for($i=1; $i<=$month-1; $i++){
      $date=date('Y-m', strtotime($yearTemp."-".$i));
      $amountByDate = 0;
      foreach ($workCommand['Acceptation'] as $dateAcceptation => $amount) {
        if($date == date('Y-m', strtotime($dateAcceptation))){
          $amountByDate = intval($amount);
        }
      }
      echo '<td class="reportTableLineHeader" style="text-align:center; width:'.$col1.'%" '.excelFormatCell('data',20,null,null,null,'right').'>'.$amountByDate.'</td>';
    }
    //recovery of totalLeftAccept
    $totalLeftAccept=$tabWCmdTotalLeftAccept[$idWorkCommand]['TotalLeftAccepted'];
    if(!isset($workCommand['TotalAccepted'])){
      $workCommand['TotalAccepted']=0;
    }
    if(!isset($workCommand['TotalAmoutAccept'])){
      $workCommand['TotalAmoutAccept']=0;
    }
    echo '<td class="reportTableData" style="text-align:center; width:'.$col1.'%" '.excelFormatCell('data',20,null,null,null,'right').'>'.$workCommand['TotalAccepted'].'</td>';
    echo '<td class="reportTableData" style="text-align:center; background-color: #FFFFDD; width:'.$col2.'%" '.excelFormatCell('data',20,null,null,null,'right').'>'.htmlDisplayCurrency($workCommand['TotalLeftAmountAccepted']).'</td>';
    echo '<td class="reportTableData" style="text-align:center; background-color: #FFFFDD; width:'.$col2.'%" '.excelFormatCell('data',20,null,null,null,'right').'>'.htmlDisplayCurrency($workCommand['TotalAmoutAccept']).'</td>';
    echo '<td class="reportTableData" style="text-align:center; background-color: #FFFFDD; width:'.$col2.'%" '.excelFormatCell('data',20,null,null,null,'right').'>'.$totalLeftAccept.'</td>';
echo'</tr>';
}

echo '</table>';
?>
