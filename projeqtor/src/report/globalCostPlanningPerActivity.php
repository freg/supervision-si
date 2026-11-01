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

//echo "globalCostPlanning.php";
include_once '../tool/projeqtor.php';
$idProject="";
if (pq_array_key_exists('idProject',$_REQUEST) and pq_trim($_REQUEST['idProject'])!="") {
  $idProject=pq_trim($_REQUEST['idProject']);
  $idProject = Security::checkValidId($idProject);
}
$paramYear='';
if (pq_array_key_exists('yearSpinner',$_REQUEST)) {
	$paramYear=$_REQUEST['yearSpinner'];
	$paramYear=Security::checkValidYear($paramYear);
};
$paramMonth='';
if (pq_array_key_exists('monthSpinner',$_REQUEST)) {
	$paramMonth=$_REQUEST['monthSpinner'];
  $paramMonth=Security::checkValidMonth($paramMonth);
};
$paramWeek='';
if (pq_array_key_exists('weekSpinner',$_REQUEST)) {
	$paramWeek=$_REQUEST['weekSpinner'];
	$paramWeek=Security::checkValidWeek($paramWeek);
};
$idOrganization = pq_trim(RequestHandler::getId('idOrganization'));
$paramTeam='';
if (pq_array_key_exists('idTeam',$_REQUEST)) {
  $paramTeam=pq_trim($_REQUEST['idTeam']);
  Security::checkValidId($paramTeam);
}
$scale='month';
if (pq_array_key_exists('scale',$_REQUEST)) {
  $scale=$_REQUEST['scale'];
  $scale=Security::checkValidPeriodScale($scale);
}
$periodValue='';
if (pq_array_key_exists('periodValue',$_REQUEST))
{
	$periodValue=$_REQUEST['periodValue'];
	$periodValue=Security::checkValidPeriod($periodValue);
}

$headerParameters="";
if ($idProject!="") {
  $headerParameters.= i18n("colIdProject") . ' : ' . htmlEncode(SqlList::getNameFromId('Project',$idProject)) . '<br/>';
}
if ($idOrganization!="") {
  $headerParameters.= i18n("colIdOrganization") . ' : ' . htmlEncode(SqlList::getNameFromId('Organization',$idOrganization)) . '<br/>';
}
if ( $paramTeam) {
  $headerParameters.= i18n("team") . ' : ' . SqlList::getNameFromId('Team', $paramTeam) . '<br/>';
}
if ($paramYear) {
  $headerParameters.= i18n("year") . ' : ' . $paramYear . '<br/>';
}
if ($paramMonth) {
  $headerParameters.= i18n("month") . ' : ' . $paramMonth . '<br/>';
}
if ( $paramWeek) {
  $headerParameters.= i18n("week") . ' : ' . $paramWeek . '<br/>';
}

include "header.php";

$accessRightRead=securityGetAccessRight('menuProject', 'read');
  
$user=getSessionUser();
$queryWhere=getAccesRestrictionClause('Activity','w',false,true,true);

if ($idProject!='') {
  $queryWhere.=  " and w.idProject in " . getVisibleProjectsList(true, $idProject) ;
} else {
  //
}
// Remove Admin Projects : should not appear in Work Plan
$queryWhere.= " and w.idProject not in " . Project::getAdminitrativeProjectList() ;

if ($paramYear) {
  $queryWhere.=  " and year=".Sql::str($paramYear);
}
if ($paramMonth) {
  $queryWhere.=  " and month=".Sql::str($periodValue);
}
if ( $paramWeek) {
  $queryWhere.=  " and week=".Sql::str($periodValue);
}
if ($paramTeam) {
  $res=new ResourceAll();
  $lstRes=$res->getSqlElementsFromCriteria(array('idTeam'=>$paramTeam));
  $inClause='(0';
  foreach ($lstRes as $res) {
    $inClause.=','.$res->id;
  }
  $inClause.=')';
  $queryWhere.= " and w.idResource in ".$inClause;
}

if ($idOrganization ) {
  $orga = new Organization($idOrganization);
  $listResOrg=$orga->getResourcesOfAllSubOrganizationsListAsArray();
  $inClause='(0';
  foreach ($listResOrg as $res) {
    $inClause.=','.$res;
  }
  $inClause.=')';
  $queryWhere.= " and w.refType='Activity'   and w.idResource in ".$inClause;
}
$querySelect1= 'select sum(w.cost) as sumCost, w.' . $scale . ' as scale , w.idProject, w.refId as refId'; 
$queryGroupBy1 = 'w.'.$scale . ', w.idProject, w.refId, t2.sortOrder';
$queryWhere1 = $queryWhere;

$querySelect2= 'select sum(w.work * a.newDailyCost) as sumCost, w.' . $scale . ' as scale , w.idProject , w.refId'; 
$queryGroupBy2 = $scale . ', w.idProject, w.refId ,t2.sortOrder';
$queryWhere2 = $queryWhere . ' and w.idAssignment=a.id ';
// constitute query and execute


$tab=array();
$start="";
$end="";
for ($i=1;$i<=2;$i++) {
  $obj=($i==1)?new Work():new PlannedWork();
  $proj= new Project();
  $ass=new Assignment();
  $var=($i==1)?'real':'plan';
  $querySelect=($i==1)?$querySelect1:$querySelect2;
  $queryGroupBy=($i==1)?$queryGroupBy1:$queryGroupBy2;
  $queryWhere=($i==1)?$queryWhere1:$queryWhere2;
  //$queryFrom=($i==1)?$queryFrom1:$queryFrom2;
  $queryWhere=($queryWhere=='')?' 1=1':$queryWhere;
  $query=$querySelect 
     . ' from ' . $obj->getDatabaseTableName().' w '.(($i==2)?', '.$ass->getDatabaseTableName() . ' a':'') .', '.$proj->getDatabaseTableName().' t2 ' 
     . ' where ' . $queryWhere.' AND t2.id=w.idProject ' 
     . ' group by ' . $queryGroupBy
     . ' order by t2.sortOrder asc ';
  $result=Sql::query($query);
  while ($line = Sql::fetchLine($result)) {
  	$line=array_change_key_case($line,CASE_LOWER);
    $date=$line['scale'];
    $proj=$line['idproject'];
    $refId=$line['refid'];
    $cost=round(pq_nvl($line['sumcost'],0),2);
    
    if (! pq_array_key_exists($proj, $tab) ) {
    $tab[$proj]=array("name"=>SqlList::getNameFromId('Project', $proj));
    }
    if (! pq_array_key_exists($refId, $tab[$proj]) ) {
      $tab[$proj][$refId]=array("id"=>$refId, "real"=>array(),"plan"=>array());
    }
    $tab[$proj][$refId][$var][$date]=$cost;
    if ($start=="" or ($start>$date and $date)) {
      $start=$date;
    }
    if ($end=="" or $end<$date) {
      $end=$date;
    }
  }
}
if (checkNoData($tab)) exit;

$arrDates=array();
$arrYear=array();
$date=$start;
while ($date<=$end) {
  $arrDates[]=$date;
  $year=pq_substr($date,0,4);
  if (! pq_array_key_exists($year,$arrYear)) {
    $arrYear[$year]=0;
  }
  $arrYear[$year]+=1;
  if ($scale=='week') {
    $day=date('Y-m-d',firstDayofWeek(pq_substr($date,4,2),pq_substr($date,0,4)));
    $next=addWeeksToDate($day,1);
    $date=pq_str_replace('-','', weekFormat($next));
  } else {
    $day=pq_substr($date,0,4) . '-' . pq_substr($date,4,2) . '-01';
    $next=addMonthsToDate($day,1);
    $date=pq_substr($next,0,4) . pq_substr($next,5,2);
  }
}
// Header
$plannedBGColor='#FFFFDD';
$plannedFrontColor='#777777';
$plannedStyle=' style="width:20px;text-align:right;background-color:' . $plannedBGColor . '; color: ' . $plannedFrontColor . ';" ';
if ($outMode!='excel') {
echo "<table width='95%' align='center'><tr><td>";
  echo'<table width="100%" align="left"><tr>';
  echo "<td class='reportTableDataFull' style='width:20px; text-align:center;'>";
  echo "1";
  echo "</td><td width='100px' class='legend'>" . i18n('colRealCost') . "</td>";
  echo "<td width='5px'>&nbsp;&nbsp;&nbsp;</td>";
  echo '<td class="reportTableDataFull" ' . $plannedStyle . '>';
  echo "<i>1</i>";
  echo "</td><td width='100px' class='legend'>" . i18n('colPlanned') . "</td>";
  echo "<td>&nbsp;</td>";
  echo "</tr></table>";
  echo "<br/>";
}

echo '<table width="100%" align="center">';
echo '<tr rowspan="2">';
echo '<td class="reportTableHeader" rowspan="2" '.excelFormatCell('header',30).'>' . i18n('Project') . '</td>';
echo '<td class="reportTableHeader" colspan="2" rowspan="2" '.excelFormatCell('header',20).'>' . i18n('Activity') . '</td>';
foreach ($arrYear as $year=>$nb) {
  echo '<td  '.excelFormatCell('header',40).' class="reportTableHeader" colspan="' . $nb . '">' . $year . '</td>';
}
echo '<td  width="10%" class="reportTableHeader" rowspan="2" '.excelFormatCell('header',10).'>' . i18n('sum') . '</td>';
echo '</tr>';
echo '<tr>';
$arrSum=array();
foreach ($arrDates as $date) {
  echo '<td class="reportTableColumnHeader" '.excelFormatCell('subheader',10).'>';
  echo pq_substr($date,4,2); 
  echo '</td>';
  $arrSum[$date]=0;
} 
echo '</tr>';
$sumProj=array();
foreach($tab as $proj=>$tabValue){
  $count=count($tabValue);
  $count=$count*2;
  $count= $count-2;
  $x=0;
  foreach($tabValue as $refId=>$lists) {
    if($refId=='name')continue;
    $x++;
  $sumProj[$proj]=array();
  for ($i=1; $i<=2; $i++) {
    if ($i==1) {
      echo '<tr>';
      if($x==1){
        echo'   <td '.excelFormatCell('data',30,null,null,null,'left').' class="reportTableLineHeader" rowspan="'.$count.'">&nbsp;&nbsp;' . htmlEncode(SqlList::getNameFromId('Project',$proj)) . '</td>';
      }
      $style='style="text-align:right;"';
      $mode='real';
      $ital=false;
    } else {
      echo '<tr>';
      $style=$plannedStyle;
      $mode='plan';
      $ital=true;
    }
    if($i==1){
    echo '<td '.excelFormatCell('data',5,null,null,null,'center').' class="reportTableData" rowspan="2">#' . $refId . '</td>';
    echo '<td '.excelFormatCell('data',15,null,null,null,'left').' class="reportTableData" style="text-align:left;" rowspan="2">&nbsp;&nbsp;&nbsp;' . htmlEncode(SqlList::getNameFromId('Activity',$refId)) . '</td>';
    }
    
    
    $sum=0;
    foreach($arrDates as $date) {
      if ($i==1) {
        $sumProj[$proj][$refId][$date]=0;
      }
      $val=null;
      if (pq_array_key_exists($mode, $lists) and pq_array_key_exists($date,$lists[$mode])) {
        $val=$lists[$mode][$date];
      }
      echo '<td  '.excelFormatCell('data',10,null,null,null,'right',null,null,'cost').' class="reportTableData" ' . $style . '>';
      echo ($ital)?'<i>':'';
      echo (($outMode=='excel')?$val:costFormatter($val));
      echo ($ital)?'</i>':'';
      $sum+=$val;
      $arrSum[$date]+=$val;
      echo '</td>';
      $sumProj[$proj][$refId][$date]+=$val;
    }
    echo '<td '.excelFormatCell('subheader',10,null,null,null,'right',null,null,'cost').' class="reportTableColumnHeader" style="text-align:right;">';
    echo ($ital)?'<i>':'' ;
    echo (($outMode=='excel')?$sum:costFormatter($sum));
    echo ($ital)?'</i>':'';
    echo '</td>';
    echo '</tr>';
    
  }
  }
}
echo "<tr><td>&nbsp;</td></tr>";
echo '<tr><td class="reportTableHeader" colspan="3" '.excelFormatCell('header',50).'>' . i18n('sum') . '</td>';
$sum=0;
$cumul=array();
foreach ($arrSum as $date=>$val) {
  echo '<td class="reportTableHeader" '.excelFormatCell('header',10,null,null,null,null,null,null,'cost').' >'.(($outMode=='excel')?$val:costFormatter($val)).'</td>';
  $sum+=$val;
  $cumul[$date]=$sum;
}
echo '<td class="reportTableHeader" '.excelFormatCell('header',20,null,null,null,'right',null,null,'cost').' >'.(($outMode=='excel')?$sum:costFormatter($sum)).'</td>';
echo '</tr>';
echo '</table>';
if($outMode !='excel'){
echo '</td></tr></table>';
}

?>