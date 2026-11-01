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
$onlyAction = RequestHandler::getValue('onlyAction');
$paramProject= pq_trim(RequestHandler::getId('idProject'));
$paramClosedItems=false;
if (pq_array_key_exists('showIdle',$_REQUEST)) {
  $paramClosedItems=true;
};
  // Header
$headerParameters="";
if ($paramProject!="") {
  $headerParameters.= i18n("colIdProject") . ' : ' . htmlEncode(SqlList::getNameFromId('Project', $paramProject)) . '<br/>';
}
if ($paramClosedItems!="") {
  $headerParameters.= i18n("colShowClosedItems") . ' : ' . i18n('displayYes') . '<br/>';
}  

include "header.php";

$queryWhereAction=getAccesRestrictionClause('Action',false);
if(!$onlyAction){
  $queryWhereRisk=getAccesRestrictionClause('Risk',false);
  $queryWhereIssue=getAccesRestrictionClause('Issue',false);
  $queryWhereOpportunity=getAccesRestrictionClause('Opportunity',false);
}
$queryWherePlus="";
if ($paramProject!="") {
  $queryWherePlus.=" and idProject in " . getVisibleProjectsList(true, $paramProject);
}
if(!$paramClosedItems){
  $queryWherePlus.=" and idle=0";
}

$clauseOrderBy=" actualEndDate asc";
$tabAction = array();
if(!$onlyAction){
  if($outMode != 'excel'){
    echo '<table  width="95%" align="center"><tr><td style="width: 100%" class="section">';
    echo i18n('Risk');
    echo '</td></tr>';
    echo '<tr><td>&nbsp;</td></tr>';
    echo '</table>';
  }
  
  $obj=new Risk();
  $lst=$obj->getSqlElementsFromCriteria(null, false, $queryWhereRisk . $queryWherePlus, $clauseOrderBy);
  echo '<table  width="95%" align="center" '.excelName(i18n('Risk')).'>';
  echo '<tr>';
  echo '<td class="largeReportHeader" style="width:3%" '.excelFormatCell('header',8).'>' . i18n('colId') . '</td>';
  echo '<td class="largeReportHeader" style="width:5%" '.excelFormatCell('header',15).'>' . i18n('colType') . '</td>';
  echo '<td class="largeReportHeader" style="width:5%" '.excelFormatCell('header',20).'>' . i18n('colIdProject') . '</td>';
  echo '<td class="largeReportHeader" style="width:7%" '.excelFormatCell('header',20).'>' . i18n('Risk') . '</td>';
  echo '<td class="largeReportHeader" style="width:10%" '.excelFormatCell('header',30).'>' . i18n('colCause') . '</td>';
  echo '<td class="largeReportHeader" style="width:10%" '.excelFormatCell('header',30).'>' . i18n('colImpact') . '</td>';
  echo '<td class="largeReportHeader" style="width:10%" '.excelFormatCell('header',30).'>' . i18n('colMitigationPlan') . '</td>';
  echo '<td class="largeReportHeader" style="width:4%" '.excelFormatCell('header',15).'>' . i18n('colSeverityShort') . '</td>';
  echo '<td class="largeReportHeader" style="width:4%" '.excelFormatCell('header',15).'>' . i18n('colLikelihoodShort') . '</td>';
  echo '<td class="largeReportHeader" style="width:4%" '.excelFormatCell('header',15).'>' . i18n('colCriticalityShort') . '</td>';
  echo '<td class="largeReportHeader" style="width:4%" '.excelFormatCell('header',15).'>' . i18n('colPriorityShort') . '</td>';
  echo '<td class="largeReportHeader" style="width:6%" '.excelFormatCell('header',20).'>' . i18n('colResponsible') . '</td>';
  echo '<td class="largeReportHeader" style="width:8%" '.excelFormatCell('header',20).'>';
  if($outMode != 'excel'){
    echo i18n('colDueDate');
    echo '<br/>';
  }else{
    $dueDate = i18n('colDueDate').'<br>';
    echo br2nl($dueDate);
  }
  echo '<span style="font-size:75%">' . i18n('commentDueDates') . '</span></td>';
  echo '<td class="largeReportHeader" style="width:5%" '.excelFormatCell('header',15).'>' . i18n('colIdStatus') . '</td>';
  echo '<td class="largeReportHeader" style="width:5%" '.excelFormatCell('header',10).'>' . i18n('colLink') . '</td>';
  echo '<td class="largeReportHeader" style="width:10%" '.excelFormatCell('header',30).'>' . i18n('colResult') . '</td>';
  echo '</tr>';
  foreach ($lst as $risk) {
    echo '<tr>';
    $done=($risk->done)?'Done':'';
    echo '<td class="largeReportData' . $done . '" '.excelFormatCell('data').' style="width:3%" >' . 'R' . htmlEncode($risk->id) . '</td>';
    echo '<td align="center" class="largeReportData' . $done . '" '.excelFormatCell('data').' style="width:5%">' . SqlList::getNameFromId('RiskType', $risk->idRiskType) . '</td>';
    echo '<td align="center" class="largeReportData' . $done . '" '.excelFormatCell('data').' style="width:5%">' . SqlList::getNameFromId('Project', $risk->idProject) . '</td>';
    echo '<td class="largeReportData' . $done . '" '.excelFormatCell('data').' style="width:7%">' . htmlEncode($risk->name); 
    if ($risk->description and $risk->name!=$risk->description) {
      if($outMode != 'excel')echo ':<br/>';
      echo ($risk->description); 
    }
    echo '</td>';
      echo '<td class="largeReportData' . $done . '" '.excelFormatCell('data').' style="width:10%">' . ($risk->cause) . '</td>';
      echo '<td class="largeReportData' . $done . '" '.excelFormatCell('data').' style="width:100px;">' . ($risk->impact) . '</td>';
      echo '<td class="largeReportData' . $done . '" '.excelFormatCell('data').' style="width:10%">' . ($risk->mitigationPlan) . '</td>';
    
    if($outMode == 'excel'){
      $severity = new Severity($risk->idSeverity);
      $color = $severity->color;
      $foreColor = excelForeColorFormatColor($color);
      echo' <td  align="" class="largeReportData' . $done . '" style="max-width:50px" '.excelFormatCell('data',15,$foreColor,$color).'>';
      echo $severity->name.'</td>';
      $likelihood = new Likelihood($risk->idLikelihood);
      $color = $likelihood->color;
      $foreColor = excelForeColorFormatColor($color);
      echo' <td  align="" class="largeReportData' . $done . '" style="max-width:50px" '.excelFormatCell('data',15,$foreColor,$color).'>';
      echo $likelihood->name.'</td>';
      $criticality = new Criticality($risk->idCriticality);
      $color = $criticality->color;
      $foreColor = excelForeColorFormatColor($color);
      echo' <td  align="" class="largeReportData' . $done . '" style="max-width:50px" '.excelFormatCell('data',15,$foreColor,$color).'>';
      echo $criticality->name.'</td>';
      $priority = new Priority($risk->idPriority);
      $color = $priority->color;
      $foreColor = excelForeColorFormatColor($color);
      echo' <td  align="" class="largeReportData' . $done . '" style="max-width:50px" '.excelFormatCell('data',15,$foreColor,$color).'>';
      echo $priority->name.'</td>';
    }else {
      echo '<td align="" class="largeReportData' . $done . '" style="width:4%" '.excelFormatCell('data').'><div>' . formatColor('Severity', $risk->idSeverity) . '</div></td>';
      echo '<td align="" class="largeReportData' . $done . '" style="width:4%" '.excelFormatCell('data').'><div>' . formatColor('Likelihood', $risk->idLikelihood) . '</div></td>';
      echo '<td align="" class="largeReportData' . $done . '" style="width:4%" '.excelFormatCell('data').'><div>' . formatColor('Criticality', $risk->idCriticality) . '</div></td>';
      echo '<td align="" class="largeReportData' . $done . '" style="width:4%" '.excelFormatCell('data').'><div>' . formatColor('Priority', $risk->idPriority) . '</div></td>';
    }
    echo '<td align="center" class="largeReportData' . $done . '" style="max-width:50px" '.excelFormatCell('data').'>' . SqlList::getNameFromId('Resource', $risk->idResource) . '</td>';
    echo '<td class="largeReportData' . $done . '" style="max-width:50px" '.excelFormatCell('data').'>';
    //table
    if($outMode != 'excel'){
      echo'<table width="100%">';
      if ($risk->initialEndDate!=$risk->actualEndDate) {
        echo '<tr><td align="center" style="width:6%;text-decoration: line-through;" '.excelFormatCell('data').'>' . htmlFormatDate($risk->initialEndDate) . '</td></tr>';
        echo '<tr><td align="center">' . htmlFormatDate($risk->actualEndDate) . '</td></tr>';
      } else {
        echo '<tr><td align="center" style="width:6%">'. htmlFormatDate($risk->initialEndDate) . '</td></tr>';
        echo '<tr><td align="center">&nbsp;</td></tr>'; 
      }
      echo   '<tr><td align="center" style="font-weight: bold">' . htmlFormatDate($risk->doneDate) . '</td></tr>';
      echo '</table></td>';
    }else{
      $date = '';
      if ($risk->initialEndDate!=$risk->actualEndDate) {
        $date.= htmlFormatDate($risk->actualEndDate);
      }else{
        $date.= htmlFormatDate($risk->initialEndDate);
      }
      $date .= '<br>';
      $date.= htmlFormatDate($risk->doneDate);
      echo br2nl($date);
      echo '</td>';
    }
    //end TABLE
    if($outMode=='excel'){
      $status = new Status($risk->idStatus);
      $color = $status->color;
      $foreColor = excelForeColorFormatColor($color);
      echo' <td  align="" class="largeReportData' . $done . '" style="width:5%" '.excelFormatCell('data',15,$foreColor,$color).'>';
      echo $status->name.'</td>';
    }else{
      echo '<td align="" class="largeReportData' . $done . '" style="width:5%" '.excelFormatCell('data').'><div>' . formatColor('Status', $risk->idStatus) . '</div></td>';
    }
    //table
    echo '<td  style="width:5%" class="largeReportData' . $done . '" '.excelFormatCell('data').'>' . br2nl(listLinks($risk)) . '</td>';
    echo '<td class="largeReportData' . $done . '" '.excelFormatCell('data').' style="width:10%;">' . ($risk->result) . '</td>';
    echo '</tr>';
  }
  
  unset($risk);
  echo '</table>';
  if($outMode !='excel'){
    echo'<br/><br/>';
    echo '</page><page>';
    
    
    echo '<table  width="95%" align="center"><tr><td style="width: 100%" class="section">';
    echo i18n('Opportunity');
    echo '</td></tr>';
    echo '<tr><td>&nbsp;</td></tr>';
    echo '</table>';
  }
  $obj=new Opportunity();
  $lst=$obj->getSqlElementsFromCriteria(null, false, $queryWhereOpportunity . $queryWherePlus, $clauseOrderBy);
  echo '<table  width="95%" align="center" '.excelName(i18n('Opportunity')).'>';
  echo '<tr>';
  echo '<td class="largeReportHeader" style="width:2%" '.excelFormatCell('header',8).'>' . i18n('colId') . '</td>';
  echo '<td class="largeReportHeader" style="width:5%" '.excelFormatCell('header',15).'>' . i18n('colType') . '</td>';
  echo '<td class="largeReportHeader" style="width:5%" '.excelFormatCell('header',20).'>' . i18n('colIdProject') . '</td>';
  echo '<td class="largeReportHeader" style="width:10%" '.excelFormatCell('header',30).'>' . i18n('Opportunity') . '</td>';
  echo '<td class="largeReportHeader" style="width:10%" '.excelFormatCell('header',30).'>' . i18n('colOpportunitySourceShort') . '</td>';
  echo '<td class="largeReportHeader" style="width:10%" '.excelFormatCell('header',30).'>' . i18n('colImpact') . '</td>';
  echo '<td class="largeReportHeader" style="width:5%;max-width:50px" '.excelFormatCell('header',30).'>' . i18n('colSeverityShort') . '</td>';
  echo '<td class="largeReportHeader" style="width:5%;max-width:50px" '.excelFormatCell('header',30).'>' . i18n('colOpportunityImprovementShort') . '</td>';
  echo '<td class="largeReportHeader" style="width:5%;max-width:50px" '.excelFormatCell('header',15).'>' . i18n('colCriticalityShort') . '</td>';
  echo '<td class="largeReportHeader" style="width:5%;max-width:50px" '.excelFormatCell('header',15).'>' . i18n('colPriorityShort') . '</td>';
  echo '<td class="largeReportHeader" style="width:7%;max-width:50px" '.excelFormatCell('header',20).'>' . i18n('colResponsible') . '</td>';
  echo '<td class="largeReportHeader" style="width:7%;max-width:50px" '.excelFormatCell('header',20).'>';
 if($outMode != 'excel'){
    echo i18n('colDueDate');
    echo '<br/>';
  }else{
    $dueDate = i18n('colDueDate').'<br>';
    echo br2nl($dueDate);
  }
  echo '<span style="font-size:75%">' . i18n('commentDueDates') . '</span></td>';
  echo '<td class="largeReportHeader" style="width:6%;max-width:50px" '.excelFormatCell('header',15).'>' . i18n('colIdStatus') . '</td>';
  echo '<td class="largeReportHeader" style="width:6%" '.excelFormatCell('header',10).'>' . i18n('colLink') . '</td>';
  echo '<td class="largeReportHeader" style="width:12%" '.excelFormatCell('header',30).'>' . i18n('colResult') . '</td>';
  echo '</tr>';
  foreach ($lst as $opportunity) {
    echo '<tr>';
    $done=($opportunity->done)?'Done':'';
    echo '<td class="largeReportData' . $done . '" '.excelFormatCell('data').' style="width:2%">' . 'O' . htmlEncode($opportunity->id) . '</td>';
    echo '<td align="center" class="largeReportData' . $done . '" '.excelFormatCell('data').' style="width:5%">' . SqlList::getNameFromId('OpportunityType', $opportunity->idOpportunityType) . '</td>';
    echo '<td align="center" class="largeReportData' . $done . '" '.excelFormatCell('data').' style="width:5%">' . SqlList::getNameFromId('Project', $opportunity->idProject) . '</td>';
    echo '<td class="largeReportData' . $done . '"  style="width:5%" '.excelFormatCell('data').'>' . ($opportunity->name); 
    if ($opportunity->description and $opportunity->name!=$opportunity->description) {
      if($outMode!='excel'){
        echo ':<br/>';
      }
      echo ($opportunity->description); 
    }
    echo '</td>';
    echo '<td style="width:10%" class="largeReportData' . $done . '" '.excelFormatCell('data').'>' . ($opportunity->cause) . '</td>';
    echo '<td style="width:10%" class="largeReportData' . $done . '" '.excelFormatCell('data').'>' . ($opportunity->impact) . '</td>';
    if($outMode == 'excel'){
      $severity = new Severity($opportunity->idSeverity);
      $color = $severity->color;
      $foreColor = excelForeColorFormatColor($color);
      echo  '<td  align="" class="largeReportData' . $done . '" style="max-width:50px" '.excelFormatCell('data',15,$foreColor,$color).'>';
      echo  $severity->name.'</td>';
      $likelihood = new Likelihood($opportunity->idLikelihood);
      $color = $likelihood->color;
      $foreColor = excelForeColorFormatColor($color);
      echo  '<td  align="" class="largeReportData' . $done . '" style="max-width:50px" '.excelFormatCell('data',15,$foreColor,$color).'>';
      echo $likelihood->name.'</td>';
      $criticality = new Criticality($opportunity->idCriticality);
      $color = $criticality->color;
      $foreColor = excelForeColorFormatColor($color);
      echo '<td  align="" class="largeReportData' . $done . '" style="max-width:50px" '.excelFormatCell('data',15,$foreColor,$color).'>';
      echo $criticality->name.'</td>';
      $priority = new Priority($opportunity->idPriority);
      $color = $priority->color;
      $foreColor = excelForeColorFormatColor($color);
      echo' <td  align="" class="largeReportData' . $done . '" style="max-width:50px" '.excelFormatCell('data',15,$foreColor,$color).'>';
      echo $priority->name.'</td>';
    }else{
      echo '<td align="" class="largeReportData' . $done . '" style="width:5%"><div>' . formatColor('Severity', $opportunity->idSeverity) . '</div></td>';
      echo '<td align="" class="largeReportData' . $done . '" style="width:5%"><div>' . formatColor('Likelihood', $opportunity->idLikelihood) . '</div></td>';
      echo '<td align="" class="largeReportData' . $done . '" style="width:5%"><div>' . formatColor('Criticality', $opportunity->idCriticality) . '</div></td>';
      echo '<td align="" class="largeReportData' . $done . '" style="width:5%"><div>' . formatColor('Priority', $opportunity->idPriority) . '</div></td>';
    }
    echo '<td align="center" class="largeReportData' . $done . '" '.excelFormatCell('data').'>' . SqlList::getNameFromId('Resource', $opportunity->idResource) . '</td>';
    echo '<td  style="width:7%" class="largeReportData' . $done . '" '.excelFormatCell('data').'>';
    //table
    if($outMode != 'excel'){
      echo '<table width="100%">';
      if ($opportunity->initialEndDate!=$opportunity->actualEndDate) {
        echo '<tr ><td align="center" style="text-decoration: line-through;">' . htmlFormatDate($opportunity->initialEndDate) . '</td></tr>';
        echo '<tr><td align="center">' . htmlFormatDate($opportunity->actualEndDate) . '</td></tr>';
      } else {
        echo '<tr><td align="center">'. htmlFormatDate($opportunity->initialEndDate) . '</td></tr>';
        echo '<tr><td align="center">&nbsp;</td></tr>'; 
      }
      echo   '<tr><td align="center" style="font-weight: bold">' . htmlFormatDate($opportunity->doneDate) . '</td></tr>';
      echo '</table>';
    }else{
      $date = '';
      if ($opportunity->initialEndDate!=$opportunity->actualEndDate) {
        $date .= htmlFormatDate($opportunity->initialEndDate);
        $date .= '<br>';
        $date .= htmlFormatDate($opportunity->actualEndDate);
      }else {
        $date .= htmlFormatDate($opportunity->initialEndDate);
      }
      $date .= '<br>';
      echo htmlFormatDate($opportunity->doneDate);
      echo br2nl($date);
    }
    echo'</td>';
    //end table
    if($outMode == 'excel'){
      $status = new Status($opportunity->idSeverity);
      $color = $status->color;
      $foreColor = excelForeColorFormatColor($color);
      echo' <td  align="" class="largeReportData' . $done . '" style="max-width:50px" '.excelFormatCell('data',20,$foreColor,$color).'>';
      echo $status->name.'</td>';
    }else{
      echo '<td align="" class="largeReportData' . $done . '" style="width:6%"><div>' . formatColor('Status', $opportunity->idStatus) . '</div></td>';
    }
    echo '<td style="width:6%" class="largeReportData' . $done . '" '.excelFormatCell('data').'>' . br2nl(listLinks($opportunity)) . '</td>';
    echo '<td style="width:12%" class="largeReportData' . $done . '" '.excelFormatCell('data').'>' . ($opportunity->result) . '</td>';
    echo '</tr>';
  }
  echo '</table>';
  unset($opportunity);
  if($outMode !='excel'){
    echo '<br/><br/>';
    echo '</page><page>';
    echo '<table  width="95%" align="center"><tr><td style="width: 100%" class="section">';
    echo i18n('Issue');
    echo '</td></tr>';
    echo '<tr><td>&nbsp;</td></tr>';
    echo '</table>';
  }
  $obj=new Issue();
  $lst=$obj->getSqlElementsFromCriteria(null, false, $queryWhereIssue . $queryWherePlus, $clauseOrderBy);
  echo '<table  width="95%" align="center" '.excelName(i18n('Issue')).'>';
  echo '<tr>';
  echo '<td class="largeReportHeader" style="width:2%" '.excelFormatCell('header',10).'>' . i18n('colId') . '</td>';
  echo '<td class="largeReportHeader" style="width:8%" '.excelFormatCell('header',15).'>' . i18n('colType') . '</td>';
  echo '<td class="largeReportHeader" style="width:10%" '.excelFormatCell('header',20).'>' . i18n('colIdProject') . '</td>';
  echo '<td class="largeReportHeader" style="width:8%" '.excelFormatCell('header',30).'>' . i18n('Action') . '</td>';
  echo '<td class="largeReportHeader" style="width:12%" '.excelFormatCell('header',30).'>' . i18n('colCause') . '</td>';
  echo '<td class="largeReportHeader" style="width:10%" '.excelFormatCell('header',30).'>' . i18n('colImpact') . '</td>';
  echo '<td class="largeReportHeader" style="width:10%" '.excelFormatCell('header',15).'>' . i18n('colPriority') . '</td>';
  echo '<td class="largeReportHeader" style="width:10%" '.excelFormatCell('header',20).'>' . i18n('colResponsible') . '</td>';
  echo '<td class="largeReportHeader" style="width:6%" '.excelFormatCell('header',20).'>';
 if($outMode != 'excel'){
    echo i18n('colDueDate');
    echo '<br/>';
  }else{
    $dueDate = i18n('colDueDate').'<br>';
    echo br2nl($dueDate);
  }
  echo '<span style="font-size:75%">' . i18n('commentDueDates') . '</span></td>';
  echo '<td class="largeReportHeader" style="width:6%" '.excelFormatCell('header',15).'>' . i18n('colIdStatus') . '</td>';
  echo '<td class="largeReportHeader" style="width:8%" '.excelFormatCell('header',10).'>' . i18n('colLink') . '</td>';
  echo '<td class="largeReportHeader" style="width:10%" '.excelFormatCell('header',30).'>' . i18n('colResult') . '</td>';
  echo '</tr>';
  foreach ($lst as $issue) {
    echo '<tr>';
    $done=($issue->done)?'Done':'';
    echo '<td class="largeReportData' . $done . '" '.excelFormatCell('data').' style="width:2%">' . 'I' . htmlEncode($issue->id) . '</td>';
    echo '<td align="center" class="largeReportData' . $done . '"'.excelFormatCell('data').' style="width:8%">' . SqlList::getNameFromId('IssueType', $issue->idIssueType) . '</td>';
    echo '<td align="center" class="largeReportData' . $done . '" '.excelFormatCell('data').' style="width:10%">' . SqlList::getNameFromId('Project', $issue->idProject) . '</td>';
    echo '<td class="largeReportData' . $done . '" '.excelFormatCell('data').' style="width:8%">' . htmlEncode($issue->name); 
    if ($issue->description and $issue->name!=$issue->description) {
      if($outMode!='excel'){
        echo ':<br/>';
      }
      echo ($issue->description); 
    }
    echo '</td>';
    echo '<td class="largeReportData' . $done . '" '.excelFormatCell('data').' style="width:12%">' . ($issue->cause) . '</td>';
    echo '<td class="largeReportData' . $done . '" '.excelFormatCell('data').' style="width:10%">' . ($issue->impact) . '</td>';
    if($outMode=='excel'){
      $priority = new Priority($issue->idPriority);
      $color = $priority->color;
      $foreColor = excelForeColorFormatColor($color);
      echo' <td  align="" class="largeReportData' . $done . '" style="max-width:50px" '.excelFormatCell('data',15,$foreColor,$color).'>';
      echo $priority->name.'</td>';
    }else{
      echo '<td align="" class="largeReportData' . $done . '" style="width:10%;max-width:50px"><div>' . formatColor('Priority', $issue->idPriority) . '</div></td>';
    }
    echo '<td align="center" class="largeReportData' . $done . '" '.excelFormatCell('data').'>' . SqlList::getNameFromId('Resource', $issue->idResource) . '</td>';
    echo '<td class="largeReportData' . $done . '" style="width:6%">';
    if($outMode!='excel'){
      echo '<table width="100%">';
      if ($issue->initialEndDate!=$issue->actualEndDate) {
        echo '<tr ><td align="center" style="text-decoration: line-through;">' . htmlFormatDate($issue->initialEndDate) . '</td></tr>';
        echo '<tr><td align="center">' . htmlFormatDate($issue->actualEndDate) . '</td></tr>';
      } else {
        echo '<tr><td align="center">'. htmlFormatDate($issue->initialEndDate) . '</td></tr>';
        echo '<tr><td align="center">&nbsp;</td></tr>'; 
      }
      echo   '<tr><td align="center" style="font-weight: bold">' . htmlFormatDate($issue->doneDate) . '</td></tr>';
      echo '</table>';
    }else{
      $date = '';
      if ($issue->initialEndDate!=$issue->actualEndDate) {
        $date .= htmlFormatDate($issue->initialEndDate);
        $date .= '<br>';
        $date .= htmlFormatDate($issue->actualEndDate);
      }else{
        $date .= htmlFormatDate($issue->initialEndDate);
      }
      $date .= '<br>';
      $date .= htmlFormatDate($issue->doneDate);
      echo br2nl($date);
    }
    echo'</td>';
    if($outMode=='excel'){
      $status = new Status($issue->idStatus);
      $color = $status->color;
      $foreColor = excelForeColorFormatColor($color);
      echo' <td  align="" class="largeReportData' . $done . '" style="max-width:50px" '.excelFormatCell('data',15,$foreColor,$color).'>';
      echo $status->name.'</td>';
    }else{
      echo '<td align="" class="largeReportData' . $done . '" style="width:6%;max-width:50px"><div>' . formatColor('Status', $issue->idStatus) . '</div></td>';
    }
    echo '<td class="largeReportData' . $done . '" '.excelFormatCell('data').' style="width:8%">' . br2nl(listLinks($issue)) . '</td>';
    echo '<td class="largeReportData' . $done . '" '.excelFormatCell('data').' style="width:10%">' . ($issue->result) . '</td>';
    echo '</tr>';
  }
  echo '</table>';
  unset ($issue);
}

if($outMode !='excel'){
  echo '<br/><br/>';
  echo '</page><page>';
  echo '<table  width="95%" align="center"><tr><td style="width: 100%" class="section">';
  echo i18n('Action');
  echo '</td></tr>';
  echo '<tr><td>&nbsp;</td></tr>';
  echo '</table>';
}
$obj=new Action();
$clauseOrderBy=" actualDueDate asc";
$lst=$obj->getSqlElementsFromCriteria(null, false, $queryWhereAction . $queryWherePlus, $clauseOrderBy);
echo '<table  width="95%" align="center" '.excelName(i18n('Action')).'>';
echo '<tr>';
echo '<td class="largeReportHeader" style="width:2%" '.excelFormatCell('header',10).'>' . i18n('colId') . '</td>';
if($onlyAction){
  echo '<td class="largeReportHeader" style="width:10%" '.excelFormatCell('header',25).'>' . i18n('colName') . '</td>';
}
echo '<td class="largeReportHeader" style="width:10%" '.excelFormatCell('header',15).'>' . i18n('colType') . '</td>';
echo '<td class="largeReportHeader" style="width:10%" '.excelFormatCell('header',20).'>' . i18n('colIdProject') . '</td>';
//==22
if(!$onlyAction){
  echo '<td class="largeReportHeader" style="width:12%" '.excelFormatCell('header',30).'>' . i18n('Action') . '</td>';
}
echo '<td class="largeReportHeader" style="width:15%" '.excelFormatCell('header',40).'>' . i18n('colDescription') . '</td>';
//==60
echo '<td class="largeReportHeader" style="width:6%" '.excelFormatCell('header',15).'>' . i18n('colPriority') . '</td>';
if($onlyAction){
  echo '<td class="largeReportHeader" style="width:6%" '.excelFormatCell('header',20).'>' . i18n('colRequestor') . '</td>';
}
echo '<td class="largeReportHeader" style="width:6%" '.excelFormatCell('header',20).'>' . i18n('colResponsible') . '</td>';
//echo '<td class="largeReportHeader" style="width:8%" '.excelFormatCell('header',20).'>';
// if($outMode != 'excel'){
//   echo i18n('colDueDate');
//   echo '<br/>';
// }else{
//   $dueDate = i18n('colDueDate').'<br>';
//   echo br2nl($dueDate);
// }
//echo '<span style="font-size:75%">' . i18n('commentDueDates') . '</span></td>';
//==80
echo '<td class="largeReportHeader" style="width:6%" '.excelFormatCell('header',20).'>' . i18n('colInitialDueDate') . '</td>';
echo '<td class="largeReportHeader" style="width:6%" '.excelFormatCell('header',20).'>' . i18n('colActualDueDate') . '</td>';
echo '<td class="largeReportHeader" style="width:6%" '.excelFormatCell('header',20).'>' . i18n('colDoneDate') . '</td>';
echo '<td class="largeReportHeader" style="width:5%" '.excelFormatCell('header',15).'>' . i18n('colIdStatus') . '</td>';
if(!$onlyAction){
  echo '<td class="largeReportHeader" style="width:5%" '.excelFormatCell('header',10).'>' . i18n('colLink') . '</td>';
}
echo '<td class="largeReportHeader" style="width:10%" '.excelFormatCell('header',30).'>' . i18n('colResult') . '</td>';
echo '</tr>';

foreach ($lst as $action) {
  //gautier #2576
   $bool = false;
   if(!$onlyAction){
     listLinks($action);
     foreach ($tabAction as $actiones){
       if($actiones == 'A' . htmlEncode($action->id) ){
         $bool = true;
       }
     }
   }
  if($action->isPrivate == false){
    if ($bool == true or $onlyAction){
      echo '<tr>';
      $done=($action->done)?'Done':'';
      echo '<td class="largeReportData' . $done . '" '.excelFormatCell('data').' style="width:2%">';
      if($onlyAction){
        echo '#' . htmlEncode($action->id) . '</td>';
      }else{
        echo 'A' . htmlEncode($action->id) . '</td>';
      }
      if($onlyAction){
        echo '<td align="center" class="largeReportData' . $done . '" '.excelFormatCell('data').' style="width:10%">' . $action->name . '</td>';
      }
      echo '<td align="center" class="largeReportData' . $done . '" '.excelFormatCell('data').' style="width:10%;">' . SqlList::getNameFromId('ActionType', $action->idActionType) . '</td>';
      echo '<td align="center" class="largeReportData' . $done . '" '.excelFormatCell('data').' style="width:10%;">' . SqlList::getNameFromId('Project', $action->idProject) . '</td>';
      if(!$onlyAction){
        echo '<td class="largeReportData' . $done . '" '.excelFormatCell('data').' style="width:12%;">' . htmlEncode($action->name) . '</td>';
      }
      echo '<td class="largeReportData' . $done . '" '.excelFormatCell('data').' style="width:15%;">' . ($action->description) . '</td>';
      if($outMode=='excel'){
        $priority = new Priority($action->idPriority);
        $color = $priority->color;
        $foreColor = excelForeColorFormatColor($color);
        echo' <td  align="" class="largeReportData' . $done . '" style="max-width:50px" '.excelFormatCell('data',15,$foreColor,$color).'>';
        echo $priority->name.'</td>';
      }else{
        echo '<td align="" class="largeReportData' . $done . '" style="width:6%;max-width:50px"><div>' . formatColor('Priority', $action->idPriority) . '</div></td>';
      }
      if($onlyAction){
        echo '<td align="center" class="largeReportData' . $done . '" '.excelFormatCell('data').' style="width:6%">' . SqlList::getNameFromId('Resource', $action->idContact) . '</td>';
      }
      echo '<td align="center" class="largeReportData' . $done . '" '.excelFormatCell('data').' style="width:6%">' . SqlList::getNameFromId('Resource', $action->idResource) . '</td>';
      echo '<td align="center" class="largeReportData' . $done . '" '.excelFormatCell('data').' style="width:6%">'.htmlFormatDate($action->initialDueDate).'</td>';
      echo '<td align="center" class="largeReportData' . $done . '" '.excelFormatCell('data').' style="width:6%">'.htmlFormatDate($action->actualDueDate).'</td>';
      echo '<td align="center" class="largeReportData' . $done . '" '.excelFormatCell('data').' style="width:6%">'.htmlFormatDate($action->doneDate).'</td>';
//      echo '<td class="largeReportData' . $done . '" '.excelFormatCell('data').'>';
//       if($outMode=='excel'){
//         $date = '';
//         if ($action->initialDueDate!=$action->actualDueDate) {
//           $date.= htmlFormatDate($action->initialDueDate);
//           $date .= '<br>';
//           $date .=htmlFormatDate($action->actualDueDate);
//         } else {
//           $date.=htmlFormatDate($action->initialDueDate);
//         }
//         $date .= '<br>';
//         $date .= ($action->doneDate);
//         echo br2nl($date);
//       }else{
//         if ($action->initialDueDate!=$action->actualDueDate) {
//           echo htmlFormatDate($action->initialDueDate);
//           echo htmlFormatDate($action->actualDueDate);
//         } else {
//           echo htmlFormatDate($action->initialDueDate);
//         }
//         echo'<table width="100%">';
//         if ($action->initialDueDate!=$action->actualDueDate) {
//           echo '<tr ><td align="center" style="text-decoration: line-through;">' . htmlFormatDate($action->initialDueDate) . '</td></tr>';
//           echo '<tr><td align="center">' . htmlFormatDate($action->actualDueDate) . '</td></tr>';
//         } else {
//           echo '<tr><td align="center">'. htmlFormatDate($action->initialDueDate) . '</td></tr>';
//           echo '<tr><td align="center">&nbsp;</td></tr>'; 
//         }
//         echo   '<tr><td align="center" style="font-weight: bold">' . htmlFormatDate($action->doneDate) . '</td></tr>';
//         echo '</table>';
//       }
//      echo'</td>';
      if($outMode=='excel'){
        $status = new Status($action->idStatus);
        $color = $status->color;
        $foreColor = excelForeColorFormatColor($color);
        echo' <td  align="" class="largeReportData' . $done . '" style="max-width:50px" '.excelFormatCell('data',15,$foreColor,$color).'>';
        echo $status->name.'</td>';
        
      }else{
        echo '<td align="" class="largeReportData' . $done . '" style="width:6%;max-width:50px"><div>' . formatColor('Status', $action->idStatus) . '</div></td>';
      }
      if(!$onlyAction){
        echo '<td class="largeReportData' . $done . '" '.excelFormatCell('data').' style="width:5%">' . br2nl(listLinks($action)) . '</td>';
      }
      echo '<td class="largeReportData' . $done . '" '.excelFormatCell('data').' style="width:10%">' . ($action->result) . '</td>';
      echo '</tr>';  
    }       
  }
}
echo '</table>';
if($outMode!='excel')echo '<br/>';

function listLinks($objIn) {
  global $tabAction,$outMode;
  $linkExcel = '';
  $lst=Link::getLinksAsListForObject($objIn);
  $res='<table style="width:100%; margin:0 ; spacing:0 ; padding: 0">';
  foreach ($lst as $link) {
    $obj=new $link['type']($link['id']);
    $style=(isset($obj->done) and $obj->done)?'style="text-decoration: line-through;"':'';
    if ($link['type']=='Action' or $link['type']=='Issue' or $link['type']=='Risk' or $link['type']=='Opportunity') {
      $type=pq_substr($link['type'],0,1);
    } else {
      //$type=pq_substr(i18n($link['type']),0,10);
      $type=pq_substr($link['type'],0,10);
    }
    //gautier #2576
    if($link['type']=='Action'){
     $act = new Action($link['id']);
     if($act->isPrivate == false){
       $res.='<tr><td '. $style . '>' . $type . $link['id'] . '</td></tr>'; 
       $linkExcel .= $type . $link['id'];
       $linkExcel .= '<br>';
       $tabAction[$type . $link['id']] =  $type . $link['id'];
     } 
    }else{
      $res.='<tr><td '. $style . '>' . $type . $link['id'] . '</td></tr>';
      $linkExcel .= $type . $link['id'];
      $linkExcel .= '<br>';
    }  
  }
  $res.='</table>';
  if($outMode=='excel'){
    $res = $linkExcel;
  }
  return $res;
}

?>
