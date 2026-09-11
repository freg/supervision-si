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

$paramProject=pq_trim(RequestHandler::getId('idProject'));
$idOrganization = pq_trim(RequestHandler::getId('idOrganization'));
$paramTeam=pq_trim(RequestHandler::getId('idTeam'));
$paramYear=RequestHandler::getYear('yearSpinner');
$paramStartMonth = RequestHandler::getValue('monthSpinner');
$user=getSessionUser();

// Header
$headerParameters="";

if ($paramProject!="") {
  $headerParameters.= i18n("colIdProject") . ' : ' . htmlEncode(SqlList::getNameFromId('Project', $paramProject)) . '<br/>';
}
if ($idOrganization!="") {
  $headerParameters.= i18n("colIdOrganization") . ' : ' . htmlEncode(SqlList::getNameFromId('Organization',$idOrganization)) . '<br/>';
}
if ($paramTeam!="") {
  $headerParameters.= i18n("colIdTeam") . ' : ' . htmlEncode(SqlList::getNameFromId('Team', $paramTeam)) . '<br/>';
}
if ($paramYear!="") {
  $headerParameters.= i18n("year") . ' : ' . $paramYear . '<br/>';
}
$headerParameters.= i18n("startMonth") . ' : ' . $paramStartMonth . '<br/>';

if ($paramYear >= '2000'  && ($paramStartMonth <= '12' && $paramStartMonth > '0')) {
  include "header.php";
  $nbMonthCurrentYear = 13 - $paramStartMonth;
  $nbMonthNewYear = 12 - $nbMonthCurrentYear;
  $paramYear1 = $paramYear+1;
  $where=getAccesRestrictionClause('Activity',false,false,true,true);
  $where='('.$where.' or idProject in '.Project::getAdminitrativeProjectList().')';
  if ($paramProject!='') {
    $where.=  "and idProject in " . getVisibleProjectsList(true, $paramProject) ;
  }
  if($nbMonthNewYear >= 1 ){
    $where.= " and ( year= '$paramYear' or  year = '$paramYear1')";
  }else{
    $where.= " and year='" . $paramYear."'";
  }
  $monthWhere = null;
  $monthWhere .=(pq_strlen($paramStartMonth)==1)?0:'';
  $monthWhere .= $paramStartMonth;
  $monthWhere = $paramYear.$monthWhere;
  $where .= " and month >= '". $monthWhere."'"; 
  if($nbMonthNewYear >= 1 ){
    $monthWhere2 = $paramYear1;
    $monthWhere2 .=(pq_strlen($nbMonthNewYear)==1)?0:'';
    $monthWhere2.=$nbMonthNewYear;
    $where .= " and month <= '$monthWhere2'";
  }
  $where .= " and refType='Activity'";
  $order="";
  //VARIABLES
  $nbMonth = 13 - $paramStartMonth;
  $work=new Work();
  $lstWork=$work->getSqlElementsFromCriteria(null,false, $where, $order);
  $result=array();
  $projects=array();
  $projectsColor=array();
  $activities=array();
  $resources=array();
  $realDays=array();
  $startDate = $paramYear.'01';
  if(isset($monthWhere2)){
    $startDate2 = $paramYear1.'01';
  }
  $planWork=new PlannedWork();
  $lstPlanWork=$planWork->getSqlElementsFromCriteria(null,false, $where, $order);
  foreach ($lstPlanWork as $work) {
  	if (! pq_array_key_exists($work->idResource,$resources)) {
  		$resources[$work->idResource]=SqlList::getNameFromId('Affectable', $work->idResource);
  	}
  	if (! pq_array_key_exists($work->idProject,$projects)) {
  		$projects[$work->idProject]=SqlList::getNameFromId('Project', $work->idProject);
  		$projectsColor[$work->idProject]=SqlList::getFieldFromId('Project', $work->idProject, 'color');
  		$realDays[$work->idProject]=array();
  		$result[$work->idProject]=array();
  	}

  	if (! pq_array_key_exists($work->refId, $activities)) {
  	  $activities[$work->refId]=SqlList::getNameFromId('Activity', $work->refId);
  	  $realDays[$work->idProject][$work->refId]=array();
  	  $result[$work->idProject][$work->refId]=array();
  	}
  	if (! pq_array_key_exists($work->idResource,$result[$work->idProject][$work->refId])) {
  		$result[$work->idProject][$work->refId][$work->idResource]=array();
  		$realDays[$work->idProject][$work->refId][$work->idResource]=array();
  	}
  	if (! pq_array_key_exists($work->month,$result[$work->idProject][$work->refId][$work->idResource])) {
  		$result[$work->idProject][$work->refId][$work->idResource][$work->month]=0;
  	}
  	if (! pq_array_key_exists($work->month,$realDays[$work->idProject][$work->refId][$work->idResource])) { // Do not add planned if real exists
  		$result[$work->idProject][$work->refId][$work->idResource][$work->month]+=$work->work;
  	} else if ($work->month>date('Ym')) {
  		$result[$work->idProject][$work->refId][$work->idResource][$work->month]+=$work->work;
  		if (isset($realDays[$work->idProject][$work->refId][$work->idResource][$work->month])) {
  			unset($realDays[$work->idProject][$work->refId][$work->idResource][$work->month]);
  		}
  	}
  }
  foreach ($lstWork as $work) {
    if (! pq_array_key_exists($work->idResource,$resources)) {
      $resources[$work->idResource]=SqlList::getNameFromId('Affectable', $work->idResource);
    }
    if (! pq_array_key_exists($work->idProject,$projects)) {
      $projects[$work->idProject]=SqlList::getNameFromId('Project', $work->idProject);
      $projectsColor[$work->idProject]=SqlList::getFieldFromId('Project', $work->idProject, 'color');
      $realDays[$work->idProject]=array();
      $result[$work->idProject]=array();
    }
    if (! pq_array_key_exists($work->refId, $activities) and !pq_array_key_exists($work->refId, $result[$work->idProject])) {
      $activities[$work->refId]=SqlList::getNameFromId('Activity', $work->refId);
  	  $realDays[$work->idProject][$work->refId]=array();
  	  $result[$work->idProject][$work->refId]=array();
    }
    if (! pq_array_key_exists($work->idResource,$result[$work->idProject][$work->refId])) {
      $result[$work->idProject][$work->refId][$work->idResource]=array();
      $realDays[$work->idProject][$work->refId][$work->idResource]=array();
    }
    if (! pq_array_key_exists($work->month,$result[$work->idProject][$work->refId][$work->idResource])) {
      $result[$work->idProject][$work->refId][$work->idResource][$work->month]= 0;
      $realDays[$work->idProject][$work->refId][$work->idResource][$work->month]='real';
    } 
    $result[$work->idProject][$work->refId][$work->idResource][$work->month]+=$work->work;
  }
  $weekendBGColor='';
  $weekendFrontColor='';
  $weekendStyle=' style="background-color:' . $weekendBGColor . '; color:' . $weekendFrontColor . '" ';
  $plannedStyle=' style="text-align:center;" ';
  
  if ($outMode !== 'excel') {
    echo "<table width='95%' align='center'><tr>";
    echo '<td><table width="100%" align="left"><tr>';
    echo "<td class='reportTableDataFull' width='20px' style='text-align:center;'>";
    echo "1";
    echo "</td><td width='100px' class='legend'>" . i18n('colRealWork') . " test</td>";
    echo "<td width='5px'>&nbsp;&nbsp;&nbsp;</td>";
    echo '<td class="reportTableDataFull" ' . $plannedStyle . '>';
    echo "<i>1</i>";
    echo "</td><td width='100px' class='legend'>" . i18n('colPlanned') . "</td>";
    echo "<td>&nbsp;</td>";
    echo "<td class='legend'>" . Work::displayWorkUnit() . "</td>";
    echo "<td>&nbsp;</td>";
    echo "</tr></table>";
  }
  // title
  echo '<table width="100%" align="left" '.excelName().'><tr>';
  echo '<td class="reportTableHeader" rowspan="2" '.excelFormatCell('header',20).'>' . i18n('Project') . '</td>';
  echo '<td class="reportTableHeader" rowspan="2"'.excelFormatCell('header',20).'>' . i18n('Activity') . '</td>';
  echo '<td class="reportTableHeader" rowspan="2"'.excelFormatCell('header',20).'>' . i18n('Resource') . '</td>';
  echo '<td colspan="'.$nbMonth.'" class="reportTableHeader" '.excelFormatCell('header',120).'>' . $paramYear  . '</td>';
  if($nbMonth < 12){
    echo '<td colspan="'.$nbMonthNewYear.'" class="reportTableHeader" '.excelFormatCell('header',10).'>' . $paramYear1  . '</td>';
  }
  echo '<td class="reportTableHeader" rowspan="2" width=50px; '.excelFormatCell('header',10).'>' . i18n('sum'). '</td>';
  echo '<td  width="10%" rowspan="2"  class="reportTableHeader" '.excelFormatCell('header',10).'>' . i18n('colNotPlannedWork'). '</td>';
  echo '</tr>';
  echo '<tr>';
  $month=array();
  for($i=$paramStartMonth; $i<=12;$i++) {
    $style = "";
    echo '<td class="reportTableColumnHeader" ' . $style . ' '.excelFormatCell('subheader',10).'>' . $i . '</td>';
  }
  if($nbMonthNewYear>0){
    for($i=1; $i<=$nbMonthNewYear;$i++) {
      $style = "";
      echo '<td class="reportTableColumnHeader" ' . $style . ''.excelFormatCell('subheader',10).'>' . $i . '</td>';
    }
  }
  echo '</tr>';
  
  asort($resources);
  if($idOrganization){
    $orga = new Organization($idOrganization);
    $listResOrg=$orga->getResourcesOfAllSubOrganizationsListAsArray();
    foreach ($resources as $idR=>$nameR){
      if(! in_array($idR, $listResOrg))unset($resources[$idR]);
    }
  }
  if ($paramTeam) {
  	foreach ($resources as $idR=>$ress) {
  		$res=new ResourceAll($idR);//florent ticket #5038
  		if ($res->idTeam!=$paramTeam) {
  			unset($resources[$idR]);
  		}
  	}
  }
  foreach ($projects as $idP=>$nameP) {
    foreach ($activities as $idA=>$nameA) {
      if (pq_array_key_exists($idA, $result[$idP])){
        foreach ($result[$idP][$idA] as $idR=>$ress) {
          if (! isset($resources[$idR]) ) {
            unset  ($result[$idP][$idR]);
            if (count($result[$idP])==0 ) {
              unset ($result[$idP]);
              unset($projects[$idP]);
            }
          }
        }
      }
    }
  }
  $globalSum=array();
  for ($i=$paramStartMonth; $i<=12;$i++) {
    $globalSum[$startDate+$i-1]=0;
  }
  if($nbMonthNewYear>0){
    for ($i=1; $i<=$nbMonthNewYear;$i++) {
      $globalSum[$startDate2+$i-1]=0;
    }
  }
  $sortProject=array();
  foreach ($projects as $id=>$name) {
    $sortProject[SqlList::getFieldFromId('Project', $id, 'sortOrder').'#'.$id]=$name;
  }
  ksort($sortProject);
  $projects=array();
  foreach ($sortProject as $sortId=>$name) {
    $split=pq_explode('#', $sortId);
    $projects[$split[1]]=$name;
  }
  
  $countResourcesByProject=array();  
  
  foreach ($projects as $idP=>$nameP) {
    $sum=array();
    $sumNpw=0;
    for ($i=$paramStartMonth; $i<=12;$i++) {
      $sum[$startDate+$i-1]=0;
    }
    if($nbMonthNewYear>0){
      for ($i=1; $i<=$nbMonthNewYear;$i++) {
        $sum[$startDate2+$i-1]=0;
      }
    }
    foreach($activities as $idA=>$nameA) {
      if (isset($result[$idP]) and pq_array_key_exists($idA, $result[$idP])){
        foreach ($result[$idP][$idA] as $idR=>$ress) {
          if (! pq_array_key_exists($idR, $resources)) {
            unset($result[$idP][$idA][$idR]);
            if (count($result[$idP][$idA])==0) {
              unset($result[$idP][$idA]);
              if (count($result[$idP])==0) {
                unset($result[$idP]);
              }
            }
          }
        }
      }
    }
    $countResourcesByProject=0;
    foreach($activities as $idA=>$nameA) {
      if (isset($result[$idP][$idA]) and is_array($result[$idP][$idA])){
        $countResourcesByProject+=count($result[$idP][$idA]);
      }
    }
    if (!isset($result[$idP])) continue;
    echo '<tr height="20px"><td class="reportTableLineHeader" style="width:150px;" rowspan="'. ($countResourcesByProject+1) . '" '.excelFormatCell('rowheader',20).'>' . htmlEncode($nameP) . '</td>';
    foreach($activities as $idA=>$nameA) {
      if (pq_array_key_exists($idA, $result[$idP])){
        echo '<td class="reportTableLineHeader" style="width:150px;" rowspan="'. (count($result[$idP][$idA])) . '" '.excelFormatCell('rowheader',20).'>' . htmlEncode($nameA) . '</td>';
        foreach ($result[$idP][$idA] as $idR=>$ress) {
          if (pq_array_key_exists($idR, $resources)) {
            echo '<td class="reportTableData" style="width:100px; text-align: left;" '.excelFormatCell('data',20).'>' . htmlEncode($resources[$idR]) . '</td>';
            $lineSum=0;
            $sumNpw=0;
            for ($i=$paramStartMonth; $i<=12;$i++) {
              $day=$startDate+$i-1;
              $style="";
              $ital=false;
                if (! pq_array_key_exists($day, $realDays[$idP][$idA][$idR]) 
                and pq_array_key_exists($day,$result[$idP][$idA][$idR])) {
                  $style=$plannedStyle;
                  $ital=true;
                }
              echo '<td class="reportTableData" ' . $style . ' valign="top" '.excelFormatCell('data',10).'>';
              if (pq_array_key_exists($day,$result[$idP][$idA][$idR])) {
                echo ($ital)?'<i>':'';
                echo Work::displayWork($result[$idP][$idA][$idR][$day]);
                echo ($ital)?'</i>':'';
                $sum[$day]+=$result[$idP][$idA][$idR][$day];
                $globalSum[$day]+=$result[$idP][$idA][$idR][$day];
                $lineSum+=$result[$idP][$idA][$idR][$day];
              }
              echo '</td>';
            }
            if($nbMonthNewYear>0){
              for ($i=1; $i<=$nbMonthNewYear;$i++) {
                $day=$startDate2+$i-1;
                $style="";
                $ital=false;
                if (! pq_array_key_exists($day, $realDays[$idP][$idA][$idR])
                and pq_array_key_exists($day,$result[$idP][$idA][$idR])) {
                  $style=$plannedStyle;
                  $ital=true;
                }
                echo '<td class="reportTableData" ' . $style . ' valign="top" '.excelFormatCell('data',10).'>';
                if (pq_array_key_exists($day,$result[$idP][$idA][$idR])) {
                  echo ($ital)?'<i>':'';
                  echo Work::displayWork($result[$idP][$idA][$idR][$day]);
                  echo ($ital)?'</i>':'';
                  $sum[$day]+=$result[$idP][$idA][$idR][$day];
                  $globalSum[$day]+=$result[$idP][$idA][$idR][$day];
                  $lineSum+=$result[$idP][$idA][$idR][$day];
                }
                echo '</td>';
              }
            }
            echo '<td class="reportTableColumnHeader" '.excelFormatCell('subheader',10).'>' . Work::displayWork($lineSum) . '</td>';
            $ass= new Assignment();
            $crit=array('idResource'=>$idR, 'idProject'=>$idP);
            $npw=$ass->sumSqlElementsFromCriteria('notPlannedWork',$crit);
            $sumNpw+=$npw;
            echo '<td class="reportTableData" '.excelFormatCell('data',12).'>'.Work::displayWork($npw).'</td>';
            echo '</tr><tr>';
          }
        }
      }
    }
    echo '<td class="reportTableLineHeader" colspan="2" style="text-align: center" '.excelFormatCell('rowheader',40,null,null,null,'center').'>' . i18n('sum') . '</td>';
    $lineSum=0;
    for ($i=$paramStartMonth; $i<=12;$i++) {
      $style='';
      $day=$startDate+$i-1;
      echo '<td class="reportTableColumnHeader" ' . $style . ' '.excelFormatCell('subheader',10).'>' . Work::displayWork($sum[$startDate+$i-1]) . '</td>';
      $lineSum+=$sum[$startDate+$i-1];
    }
    if($nbMonthNewYear>0){
      for ($i=1; $i<=$nbMonthNewYear;$i++) {
        $style='';
        $day=$startDate2+$i-1;
        echo '<td class="reportTableColumnHeader" ' . $style . ' '.excelFormatCell('data',10).'>' . Work::displayWork($sum[$startDate2+$i-1]) . '</td>';
        $lineSum+=$sum[$startDate2+$i-1];
      }
    }
    echo '<td class="reportTableHeader" '.excelFormatCell('header',10).'>' . Work::displayWork($lineSum) . '</td>';
    echo '<td class="reportTableHeader" '.excelFormatCell('header',10).'>' . Work::displayWork($sumNpw) . '</td>';
    echo '</tr>';
    
  }
  echo "<tr><td>&nbsp;</td></tr>";
  echo '<tr><td class="reportTableHeader" colspan="3" '.excelFormatCell('header',60).'>' . i18n('sum') . '</td>';
  $lineSum=0;
  for ($i=$paramStartMonth; $i<=12;$i++) {
    $style='';
    $day=$startDate+$i-1;
    echo '<td class="reportTableHeader" ' . $style . ' '.excelFormatCell('header',10).'>' . Work::displayWork($globalSum[$startDate+$i-1]) . '</td>';
    $lineSum+=$globalSum[$startDate+$i-1];
  }
  if($nbMonthNewYear>0){
    for ($i=1; $i<=$nbMonthNewYear;$i++) {
      $style='';
      $day=$startDate2+$i-1;
      echo '<td class="reportTableHeader" ' . $style . ' '.excelFormatCell('header',10).'>' . Work::displayWork($globalSum[$startDate2+$i-1]) . '</td>';
      $lineSum+=$globalSum[$startDate2+$i-1];
    }
  }
  echo '<td class="reportTableHeader" '.excelFormatCell('header',10).'>' . Work::displayWork($lineSum) . '</td>';
  echo '</tr>';
  echo '</table>';
  if ($outMode !== 'excel') {
    echo '</td></tr></table>';
  }
} else {
  echo '
  <table width="95%" align="center">
    <tbody>
      <tr height="50px">
        <td width="100%" align="center">
          <div style="background: #FFDDDD;font-size:150%;color:#808080;text-align:center;padding:20px">';
  
  if (!($paramYear > '2000')) echo i18n('messageNoData',array(i18n('year')))." <br>";
  if (!($paramStartMonth <= '12' && $paramStartMonth > '0')) echo i18n('messageNoData',array(i18n('month')))." \n";
  
  echo '
          </div>
        </td>
      </tr>
    </tbody>
  </table>';
}

echo '<br/><br/>';

