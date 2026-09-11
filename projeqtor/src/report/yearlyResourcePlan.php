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
$onlyRealWork = RequestHandler::getBoolean('onlyRealWork');
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
  $nbMonthCurrentYear = 13 - $paramStartMonth;
  $nbMonthNewYear = 12 - $nbMonthCurrentYear;
  $paramYear1 = $paramYear+1;
  include "header.php";
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
  $order="";
  $nbMonth = 13-$paramStartMonth;
  //VARIABLES
  $result=array();
  $projects=array();
  $projectsColor=array();
  $resources=array();
  $capacity=array();
  $workDayResource=array();
  $realDays=array();
  $startDate = $paramYear.'01';
  if(isset($monthWhere2)){
    $startDate2 = $paramYear1.'01';
  }
  
  if(!$onlyRealWork){
    //PLANNED WORK
    $planWork=new PlannedWork();
    $lstPlanWork=$planWork->getSqlElementsFromCriteria(null,false, $where, $order);
    foreach ($lstPlanWork as $work) {
      if (! pq_array_key_exists($work->idResource,$resources)) {
        $resources[$work->idResource]=SqlList::getNameFromId('Affectable', $work->idResource);
        $capacity[$work->idResource]=SqlList::getFieldFromId('Affectable', $work->idResource, 'capacity');
        $result[$work->idResource]=array();
        $realDays[$work->idResource]=array();
        $workDayResource[$work->idResource]=array();
      }
      if (! pq_array_key_exists($work->idProject,$projects)) {
        $projects[$work->idProject]=SqlList::getNameFromId('Project', $work->idProject);
        $projectsColor[$work->idProject]=SqlList::getFieldFromId('Project', $work->idProject, 'color');
      }
      if (! pq_array_key_exists($work->idProject,$result[$work->idResource])) {
        $result[$work->idResource][$work->idProject]=array();
      }
      if (! pq_array_key_exists($work->idProject,$realDays[$work->idResource])) {
        $realDays[$work->idResource][$work->idProject]=array();
      }
      if (! pq_array_key_exists($work->month,$result[$work->idResource][$work->idProject])) {
        $result[$work->idResource][$work->idProject][$work->month]=0;
      }
      if (! pq_array_key_exists($work->month,$workDayResource[$work->idResource])) {
        $workDayResource[$work->idResource][$work->month]=0;
      }
      if (! pq_array_key_exists($work->month,$realDays[$work->idResource][$work->idProject]) ) { // Do not add planned if real exists
        $result[$work->idResource][$work->idProject][$work->month]+=$work->work;
        $workDayResource[$work->idResource][$work->month]+=$work->work;
      } else if ($work->month>date('Ym')) {
        $result[$work->idResource][$work->idProject][$work->month]+=$work->work;
        $workDayResource[$work->idResource][$work->month]+=$work->work;
        if (isset($realDays[$work->idResource][$work->idProject][$work->month])) {
          unset($realDays[$work->idResource][$work->idProject][$work->month]);
        }
      }
    }
    
    $resultPlanned = $result;
  }
  //REAL WORK
  $work=new Work();
  $lstWork=$work->getSqlElementsFromCriteria(null,false, $where, $order);
  foreach ($lstWork as $work) {
    if (! pq_array_key_exists($work->idResource,$resources)) {
      $resources[$work->idResource]=SqlList::getNameFromId('Affectable', $work->idResource);
      $capacity[$work->idResource]=SqlList::getFieldFromId('Affectable', $work->idResource, 'capacity');
      $result[$work->idResource]=array();
      $realDays[$work->idResource]=array();
      $workDayResource[$work->idResource]=array();
    }
    if (! pq_array_key_exists($work->idProject,$projects)) {
      $projects[$work->idProject]=SqlList::getNameFromId('Project', $work->idProject);
      $projectsColor[$work->idProject]=SqlList::getFieldFromId('Project', $work->idProject, 'color');
    }
    if (! pq_array_key_exists($work->idProject,$result[$work->idResource])) {
      $result[$work->idResource][$work->idProject]=array();
    }
    if (! pq_array_key_exists($work->idProject,$realDays[$work->idResource])) {
      $realDays[$work->idResource][$work->idProject]=array();
    }
    if (! pq_array_key_exists($work->month,$result[$work->idResource][$work->idProject])) {
      $result[$work->idResource][$work->idProject][$work->month]=0;
      $realDays[$work->idResource][$work->idProject][$work->month]='real';
    } 
    if (! pq_array_key_exists($work->month,$workDayResource[$work->idResource])) {
      $workDayResource[$work->idResource][$work->month]=0;
    }
    $result[$work->idResource][$work->idProject][$work->month]+=$work->work;
    $workDayResource[$work->idResource][$work->month]+=$work->work;
  }
  
  if (!$paramYear ) {
    echo '<div style="background: #FFDDDD;font-size:150%;color:#808080;text-align:center;padding:20px">';
    echo i18n('messageNoData',array(i18n('year'))); // TODO i18n message
    echo '</div>';
  }
  
  $plannedStyle=' style="text-align:center;" ';
  
  echo "<table width='95%' align='center' ".excelName().">";
  if($outMode!='excel'){
    echo "<tr><td><table  width='100%' align='left'><tr>";
    echo "<td class='legend'>" . Work::displayWorkUnit() . "</td>";
    echo "</tr>";
    echo "</table>";
  }

  
  // title
  if($outMode!='excel')echo '<table width="100%" align="left" >';
  echo '<tr>';
  echo '<td class="reportTableHeader" rowspan="2" '.excelFormatCell('header',24).'>' . i18n('Resource') . '</td>';
  echo '<td class="reportTableHeader" rowspan="2" '.excelFormatCell('header',36).'>' . i18n('Project') . '</td>';
  if($onlyRealWork)echo '<td class="reportTableHeader" rowspan="2" '.excelFormatCell('header',12).'>' . i18n('colProjectCode') . '</td>';
  echo '<td colspan="'.$nbMonth.'" class="reportTableHeader" '.excelFormatCell('header',12).'>' . $paramYear  . '</td>';
  if($nbMonth < 12){
    echo '<td colspan="'.$nbMonthNewYear.'" class="reportTableHeader" '.excelFormatCell('header',12*$nbMonth).'>' . $paramYear1  . '</td>';
  }
  echo '<td class="reportTableHeader" rowspan="2" width=50px; '.excelFormatCell('header',12).'>' . i18n('sum'). '</td>';
  echo '<td  width="10%" rowspan="2"  class="reportTableHeader" '.excelFormatCell('header',12).'>' . i18n('colNotPlannedWork'). '</td>';
  echo '</tr>';
  echo '<tr>';
  $month=array();
  
   for($i=$paramStartMonth; $i<=12;$i++) {
     $style = "";
      echo '<td class="reportTableColumnHeader" ' . $style . ' '.excelFormatCell('subheader',12).'>' . $i . '</td>';
    }
    if($nbMonthNewYear>0){
     for($i=1; $i<=$nbMonthNewYear;$i++) {
       $style = "";
        echo '<td class="reportTableColumnHeader" ' . $style . ' '.excelFormatCell('subheader',12).'>' . $i . '</td>';
      }
    }
    
  echo '</tr>';
  $globalSum=array();
  for ($i=$paramStartMonth; $i<=12;$i++) {
    $globalSum[$startDate+$i-1]=0;
  }
  if($nbMonthNewYear>0){
    for ($i=1; $i<=$nbMonthNewYear;$i++) {
      $globalSum[$startDate2+$i-1]=0;
    }
  }
  asort($resources);
  if($idOrganization){
    $orga = new Organization($idOrganization);
    $listResOrg=$orga->getResourcesOfAllSubOrganizationsListAsArray();
    foreach ($resources as $idR=>$nameR){
      if(! in_array($idR, $listResOrg))unset($resources[$idR]);
    }
  }
  foreach ($resources as $idR=>$nameR) {
    $sumNpw=0;
      $res=new ResourceAll($idR);//florent ticket #5038
    if (!$paramTeam or $res->idTeam==$paramTeam) {
  	  $sum=array();
  	  for ($i=$paramStartMonth; $i<=12;$i++) {
  	    $sum[$startDate+$i-1]=0;
  	  }
  	  if($nbMonthNewYear>0){
    	  for ($i=1; $i<=$nbMonthNewYear;$i++) {
    	    $sum[$startDate2+$i-1]=0;
    	  }
  	  }
  	  echo '<tr height="20px">';
  	  echo '<td class="reportTableLineHeader" style="width:100px;" rowspan="'. (count($result[$idR])+1) . '" '.excelFormatCell('rowheader',24).'>' . htmlEncode($nameR) . '</td>';
  	  $sortProject=array();
  	  foreach ($result[$idR] as $id=>$name) {
  	    $sortProject[SqlList::getFieldFromId('Project', $id, 'sortOrder').'#'.$id]=$name;
  	  }
  	  ksort($sortProject);
  	  $tmpprojects=array();
  	  foreach ($sortProject as $sortId=>$name) {
  	    $split=pq_explode('#', $sortId);
  	    $tmpprojects[$split[1]]=$name;
  	  }
  	  foreach ($tmpprojects as $idP=>$proj) {
  	    if (pq_array_key_exists($idP, $projects)) {
  	      echo '<td class="reportTableData" style="width:150px;text-align: left;" '.excelFormatCell('data',36).'>' . htmlEncode($projects[$idP]) . '</td>';
  	      if($onlyRealWork){
  	        $codeProject = SqlList::getFieldFromId('Project', $idP, 'projectCode');
  	        echo '<td class="reportTableData" style="width:75px;text-align: center;" '.excelFormatCell('data',12).'>' . htmlEncode($codeProject) . '</td>';
  	      }
  	      $lineSum=0;
  	      for ($i=$paramStartMonth; $i<=12;$i++) {
  	        $day=$startDate+$i-1;
  	        $style="";
  	        $ital=false;
  	        echo '<td class="reportTableData" ' . $style . ' valign="top" '.excelFormatCell('data',12).'>';
  	        if (pq_array_key_exists($day,$result[$idR][$idP])) {
  	          echo ($ital)?'<i>':'';
  	          echo Work::displayWork($result[$idR][$idP][$day]);
  	          echo ($ital)?'</i>':'';
  	          $sum[$day]+=$result[$idR][$idP][$day];
  	          $globalSum[$day]+=$result[$idR][$idP][$day];
  	          $lineSum+=$result[$idR][$idP][$day];
  	        }
  	        echo '</td>';
  	      }
  	      if($nbMonthNewYear>0){
  	         for ($i=1; $i<=$nbMonthNewYear;$i++) {
  	          $day=$startDate2+$i-1;
  	          $style="";
  	          $ital=false;
  	          echo '<td class="reportTableData" ' . $style . ' valign="top" '.excelFormatCell('data',12).'>';
  	          if (pq_array_key_exists($day,$result[$idR][$idP])) {
  	            echo ($ital)?'<i>':'';
  	            echo Work::displayWork($result[$idR][$idP][$day]);
  	            echo ($ital)?'</i>':'';
  	            $sum[$day]+=$result[$idR][$idP][$day];
  	            $globalSum[$day]+=$result[$idR][$idP][$day];
  	            $lineSum+=$result[$idR][$idP][$day];
  	          }
  	          echo '</td>';
  	        }
  	      }
  	      echo '<td class="reportTableColumnHeader" '.excelFormatCell('subheader',12).'>' . Work::displayWork($lineSum) . '</td>';
  	      $ass= new Assignment();
  	      $crit=array('idResource'=>$idR, 'idProject'=>$idP);
  	      $npw=$ass->sumSqlElementsFromCriteria('notPlannedWork',$crit);
  	      $sumNpw+=$npw;
  	      echo '<td class="reportTableData" '.excelFormatCell('data',20).'>'.Work::displayWork($npw).'</td>';
  	      echo '</tr><tr>';
  	    }
  	  }
  	  $colspan = ($onlyRealWork)?'colspan="2" style="text-align:center"':'';
  	  $size = ($onlyRealWork)?2:1;
  	  echo '<td class="reportTableLineHeader" '.$colspan.' '.excelFormatCell('rowheader',null,null,null,null,'center').'>' . i18n('sum') . '</td>';
  	  $lineSum=0;
  	  for ($i=$paramStartMonth; $i<=12;$i++) {
  	    $style='';
  	    $day=$startDate+$i-1;
  	    $sumDay=$sum[$startDate+$i-1];
  	    $day=$startDate+$i-1;
  	    $day=pq_substr($day,0,4).'-'.pq_substr($day,4,2).'-'.pq_substr($day,6,2);
  	    echo '<td class="reportTableColumnHeader" ' . $style . ' '.excelFormatCell('subheader',12).'>' . Work::displayWork($sumDay) . '</td>';
  	    $lineSum+=$sum[$startDate+$i-1];
  	  	}
  	  	if($nbMonthNewYear > 0){
    	  	for ($i=1; $i<=$nbMonthNewYear;$i++) {
    	  	  $style='';
    	  	  $day=$startDate2+$i-1;
    	  	  $sumDay=$sum[$startDate2+$i-1];
    	  	  $day=$startDate2+$i-1;
    	  	  $day=pq_substr($day,0,4).'-'.pq_substr($day,4,2).'-'.pq_substr($day,6,2);
    	  	  echo '<td class="reportTableColumnHeader" ' . $style . ' '.excelFormatCell('data',12).'>' . Work::displayWork($sumDay) . '</td>';
    	  	  $lineSum+=$sum[$startDate2+$i-1];
    	  	}
  	  	}
  	  echo '<td class="reportTableHeader" '.excelFormatCell('header',12).'>' . Work::displayWork($lineSum) . '</td>';
  	  echo '<td class="reportTableHeader" '.excelFormatCell('header',12).'>' . Work::displayWork($sumNpw) . '</td>';
  	  echo '</tr>';
  	  
    }
  }
  
  echo '<tr><td colspan="' . ($nbMonth+3) . '">&nbsp;</td></tr>';
  $colspan = ($onlyRealWork)?'colspan="3"':'colspan="2"';
  echo '<tr><td class="reportTableHeader" '.$colspan.' '.excelFormatCell('header').'>' . i18n('sum') . '</td>';
  $lineSum=0;
  for ($i=$paramStartMonth; $i<=12;$i++) {
    $style='';
    echo '<td class="reportTableHeader" ' . $style . ' '.excelFormatCell('header',12).'>' . Work::displayWork($globalSum[$startDate+$i-1]) . '</td>';
    $lineSum+=$globalSum[$startDate+$i-1];
  }
  if($nbMonthNewYear > 0){
    for ($i=1; $i<=$nbMonthNewYear;$i++) {
      $style='';
      echo '<td class="reportTableHeader" ' . $style . ' '.excelFormatCell('header',12).'>' . Work::displayWork($globalSum[$startDate2+$i-1]) . '</td>';
      $lineSum+=$globalSum[$startDate2+$i-1];
    }
  }
  echo '<td class="reportTableHeader" '.excelFormatCell('header',12).'>' . Work::displayWork($lineSum) . '</td>';
  echo '</tr>';
  echo '</table>';
  if($outMode!='excel')echo '</td></tr></table>';

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

