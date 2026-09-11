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
include_once '../tool/formatter.php';
include_once("../external/pChart2/class/pData.class.php");
include_once("../external/pChart2/class/pDraw.class.php");
include_once("../external/pChart2/class/pImage.class.php");

$idProject="";
if (pq_array_key_exists('idProject',$_REQUEST) and pq_trim($_REQUEST['idProject'])!="") {
  $idProject=pq_trim($_REQUEST['idProject']);
  $idProject = Security::checkValidId($idProject);
}
$scale="";
if (pq_array_key_exists('format',$_REQUEST)) {
	$scale=RequestHandler::getValue("format");
};
$startDateReport="";
if (pq_array_key_exists('startDate',$_REQUEST)) {
  $startDateReport=RequestHandler::getValue("startDate");
};
$endDateReport="";
if (pq_array_key_exists('endDate',$_REQUEST)) {
  $endDateReport=RequestHandler::getValue("endDate");
};
$showCompleted=false;
if (pq_array_key_exists('showBurndownActivities',$_REQUEST)) {
  $showCompleted=true;
}
$showToday=false;
if (pq_array_key_exists('showBurndownToday',$_REQUEST)) {
  $showToday=true;
}
$legend='included';
if (pq_array_key_exists('showBurndownLegendOnTop',$_REQUEST)) {
  $legend="top";
}
//filter id
$filterActivity="";
if (pq_array_key_exists('filterActivity',$_REQUEST)) {
  $filterActivity=RequestHandler::getValue("filterActivity");
};
$idFilterCriteria=$filterActivity;
$nameFilterCriteria=SqlList::getNameFromId("Filter", $filterActivity);
// FilterCriteria and DB name for join 
//planningElement
$pe = new PlanningElement();
$peTable=$pe->getDatabaseTableName();
//activity
$act = new Activity();
$actcrtTable=$act->getDatabaseTableName();
if($idFilterCriteria){
  //filter
  $ft = new Filter();
  $ftTable=$ft->getDatabaseTableName();
  //filterCriteria
  $idFilterCriteriaList = SqlList::getListWithCrit('FilterCriteria', array('idFilter'=>$idFilterCriteria), 'id');
  foreach ($idFilterCriteriaList as $idFlcrt){
    $arrayDisp=array();
    $arraySql=array();
    $ftcrt = new FilterCriteria($idFlcrt);
    $arraySqlFtcrt["attribute"]=$ftcrt->sqlAttribute;
    $arraySqlFtcrt["operator"]=$ftcrt->sqlOperator;
    $arraySqlFtcrt["value"]=$ftcrt->sqlValue;
    $orOperatorFtcrt=$ftcrt->orOperator;
    $arrayFtcrt[]=array("sql"=>$arraySqlFtcrt,"orOperator"=>$orOperatorFtcrt);
    
    $myFilters="";
    $nbFilters=0;
    foreach ($arrayFtcrt as $filter){
      if (!isset($filter['orOperator'])) $filter['orOperator']=0;
      if (!isset($filter['isDynamic'])) $filter['isDynamic']=0;
      if ($filter['orOperator']=='1') {
        $myFilters.= 'OR ';
      }
      elseif ($nbFilters==0) { //Nothing is displayed on the first criteria
        $nbFilters+=1;
      }
      else {
        $myFilters.='AND ';
      }
      $peCritOn=false;
      if(pq_strpos($filter['sql']['attribute'], 'PlanningElement')){
        $peCritOn=true;
        $critpe=explode('_', $filter['sql']['attribute'])[1];
        $ape = new ActivityPlanningElement();
        $critpe = $ape->getDatabaseColumnName($critpe);
        $myFilters.= "pe.".$critpe. " " .$filter['sql']['operator']. " " .$filter['sql']['value']." ";
      }else{
        $myFilters.= "a.".$filter['sql']['attribute'] . " " .$filter['sql']['operator']. " " .$filter['sql']['value']." ";
      }
    }
  }
  $ftcrtTable=$ftcrt->getDatabaseTableName();
}

$today=date('Y-m-d');
if($idFilterCriteria){ // TODO
//   if(!$startDateReport) $startDateReport=$today;
//   //case date early today with filter
//   if($startDateReport<$today){
//     echo '<div style="background: #FFDDDD;font-size:150%;color:#808080;text-align:center;padding:20px">';
//     echo i18n('incorrectDateToEarlyFilterActivity',array(i18n('colStartDate'))); 
//     echo '</div>';
//     if (!empty($cronnedScript)) goto end; else exit;
//   }
} else if (! $idProject) {
  echo '<div style="background: #FFDDDD;font-size:150%;color:#808080;text-align:center;padding:20px">';
  echo i18n('messageMandatory',array(i18n('colIdProject')));
  echo '</div>';
  if (!empty($cronnedScript)) goto end; else exit;
}


$headerParameters="";

if ($idProject!="") {
  $headerParameters.= i18n("colIdProject") . ' : ' . htmlEncode(SqlList::getNameFromId('Project',$idProject)) . '<br/>';
}
if ( $scale) {
  $headerParameters.= i18n("colFormat") . ' : ' . i18n($scale) . '<br/>';
}
if ($startDateReport!="") {
  $headerParameters.= i18n("colStartDate") . ' : ' . htmlFormatDate($startDateReport) . '<br/>';
}
if ($endDateReport!="") {
  $headerParameters.= i18n("colEndDate") . ' : ' . htmlFormatDate($endDateReport) . '<br/>';
}
if ($idFilterCriteria) {
  $headerParameters.= i18n("filterActivity") . ' : ' . htmlEncode($nameFilterCriteria) . '<br/>';
}
if ($showCompleted) {
  $headerParameters.= i18n("colShowBurndownActivities"). '<br/>';
}
if ($showToday) {
  $headerParameters.= i18n("colShowBurndownToday"). '<br/>';
}

include "header.php";
//OLD mondatoryProject
// if (!$idProject) {
//   echo '<div style="background: #FFDDDD;font-size:150%;color:#808080;text-align:center;padding:20px">';
//   echo i18n('messageNoData',array(i18n('Project'))); // TODO i18n message
//   echo '</div>';
//   if (!empty($cronnedScript)) goto end; else exit; 
// }

// Graph
if (! testGraphEnabled()) { return;}
$user=getSessionUser();
if($idProject){
  $proj=new Project($idProject);
}else{
  $proj=new Project();
}
$projcrtTablde=$proj->getDatabaseTableName();

// constitute query and execute for left work (history)=============================================
$ph=new ProjectHistory();
$phTable=$ph->getDatabaseTableName();
$pe=new PlanningElement();$peTable=$pe->getDatabaseTableName();
//select
  $querySelect= "select leftWork as leftwork, realWork as realwork, day ";
//form
  $queryFrom=   " from $phTable ph";
//where
if ($idFilterCriteria) {
  $todaySql=date('Ymd');
  $querySelect= "select sum(leftWork) as leftwork, sum(realWork) as realwork, '$todaySql' as day, min(coalesce(pe.realStartDate, pe.plannedStartDate, pe.validatedStartDate)) startact ";
  $queryFrom=   " from $actcrtTable a";
  $queryFrom.=  "   LEFT JOIN $peTable pe ON a.id = pe.refId AND pe.refType = 'Activity'";
  $queryWhere=  " where $myFilters";
  if ($idProject) $queryWhere.=" and a.idProject=$idProject";
} else if($idProject){
  $queryWhere=  " where ph.idProject=".Sql::fmtId($idProject);
  //$queryWhere.= " and ph.idProject in ".transformListIntoInClause($user->getVisibleProjects(false));
}else{
  $queryWhere= " where ph.idProject in ".transformListIntoInClause($user->getVisibleProjects(false));
}
//order
  $queryOrder= "  order by day asc";
//query
$query=$querySelect.$queryFrom.$queryWhere.$queryOrder;
$result=Sql::query($query);
$tabLeft=array();
$resLeft=array();
$start="";
if ($startDateReport) $start=$startDateReport;
$end="";
$hasReal=false;
$lastLeft=0;
$maxReal=0;
$startAct=null;
while ($line = Sql::fetchLine($result)) {
  $day=pq_substr($line['day'],0,4).'-'.pq_substr($line['day'],4,2).'-'.pq_substr($line['day'],6);
  $left=$line['leftwork']??0;
  $real=$line['realwork']??0;
  if ($real>0 or $idFilterCriteria) {
    $tabLeft[$day]=$left;
    //$left;
    if($idProject){
      $lastLeft=$left;
      $maxReal=$real;
    }else{
      $lastLeft+=$left;
      $maxReal+=$real;
    }
    if ( ($start=="" or $start>$day) and $day<=$today ) {$start=$day;}
    if ( ($end=="" or $end<$day) and $day<=$today ) { $end=$day;}
    if ($idFilterCriteria and isset($line['startact']) and ($startAct==null or $startAct>$line['startact'])) $startAct=$line['startact'];
  }
  if ($day>date('Y-m-d')) break;
}

if ($idFilterCriteria and ! $startDateReport and $startAct) {
  $startDateReport=addDaysToDate($startAct,-1);
  $start=$startDateReport;
}
//if lastLeft = 0, no data.
if($lastLeft == 0 ){
  echo '<div style="background: #FFDDDD;font-size:150%;color:#808080;text-align:center;padding:20px">';
  echo i18n('noDataFound'); // TODO i18n message
  echo '</div>';
  if (!empty($cronnedScript)) goto end; else exit;
}
//if (!$end)$end=(intval(date('Y')+10)).'1231';
if (!$end) $end=$today;
if (!$start) $start=$today;
$endReal=$end;
// constitute query and execute for planned post $end (last real work day)=============================
$pw=new PlannedWork();
$pwTable=$pw->getDatabaseTableName();
//select
$querySelect= "select sum(pw.work) as work, pw.workDate as day ";
//from
$queryFrom=   " from $pwTable pw";
if($idFilterCriteria){
//join
  $queryJoin=  " LEFT JOIN $actcrtTable a ON pw.refId = a.id  AND pw.refType = 'Activity'";
  if($peCritOn){
    //join for planningElement
   $queryJoin .= "LEFT JOIN $peTable pe ON pw.refId = pe.refId AND pe.refType = 'Activity'";
  }
}
//where
//$queryWhere=  " where pw.workDate>'$end'";
if (0 and $startDateReport) $queryWhere= "  where pw.workDate>'$startDateReport'";
else $queryWhere=  " where 1=1";
if($idProject){
  $proj=new Project($idProject);
  $queryWhere.= " and pw.idProject in " . transformListIntoInClause($proj->getRecursiveSubProjectsFlatList(false, true));
} else {
  $queryWhere.= " and pw.idProject in ".transformListIntoInClause($user->getVisibleProjects(false));
}
if($idFilterCriteria){
  $queryWhere .= " AND $myFilters";
}
//order
$queryOrder= "  group by pw.workDate order by pw.workDate";
//query
if($idFilterCriteria){
  $query=$querySelect.$queryFrom.$queryJoin.$queryWhere.$queryOrder;
}else{
  $query=$querySelect.$queryFrom.$queryWhere.$queryOrder;
}
$resultPlanned=Sql::query($query);
if(Sql::$lastQueryNbRows == 0){
  echo '<div style="background: #FFDDDD;font-size:150%;color:#808080;text-align:center;padding:20px">';
  echo i18n('noDataFound'); // TODO i18n message
  echo '</div>';
  if (!empty($cronnedScript)) goto end; else exit;
}
$tabLeftPlanned=array();
$resLeftPlanned=array();
$resBest=array();
if (! $idFilterCriteria) $tabLeftPlanned[$end]=$lastLeft;
$newLastLeft=$lastLeft;
while ($line = Sql::fetchLine($resultPlanned)) {
  $day=$line['day'];
  $planned=$line['work']??0;
  $newLastLeft-=$planned;
  if ($startDateReport and $idFilterCriteria and $day<$startDateReport) continue;
  if ($newLastLeft<0) $newLastLeft=0;
  $tabLeftPlanned[$day]=$newLastLeft;
  if ($start=="" or $start>$day) {$start=$day;}
  if ($end=="" or $end<$day) { $end=$day;}
  if ($newLastLeft==0) break;
  if($idFilterCriteria){ // TODO
    $dateDay=pq_substr($day,0,4).'-'.pq_substr($day,4,2).'-'.pq_substr($day,6,2);
    if (!$startDateReport or $startDateReport>$day) $startDateReport=$day;
  }
}
ksort($tabLeftPlanned);
if (count($tabLeftPlanned)<=0) if (!empty($cronnedScript)) goto end; else exit;
// constitute query and execute for completed tasks===========================================================
//select
$querySelect= "select plannedEndDate as plannedend, realEndDate as realend ";
//from
$queryFrom=   " from $peTable pe";
//join
$queryJoin=  " JOIN $actcrtTable a ON pe.refId = a.id  AND pe.refType = 'Activity' ";
//where
$queryWhere=  " where pe.idProject in " . transformListIntoInClause($proj->getRecursiveSubProjectsFlatList(false, true));
$queryWhere.= " and pe.idProject in ".transformListIntoInClause($user->getVisibleProjects(false));
if($idFilterCriteria){
  $queryWhere .= " AND $myFilters";
}
$queryWhere.= "  and pe.elementary=1";
$queryWhere.= " and COALESCE(pe.realEndDate, pe.plannedEndDate) >='$start'";
//   $queryWhere=  " where pe.idProject in " . transformListIntoInClause($proj->getRecursiveSubProjectsFlatList(false, true));
//   $queryWhere.= " and pe.idProject in ".transformListIntoInClause($user->getVisibleProjects(false));
//order
$queryOrder= "  order by COALESCE(pe.realEndDate, pe.plannedEndDate)";
//query
if($idFilterCriteria){
  $query=$querySelect.$queryFrom.$queryJoin.$queryWhere.$queryOrder;
}else{
  $query=$querySelect.$queryFrom.$queryWhere.$queryOrder;
}
$tabCompletedTasks=array();
$tabCompletedTasksPlanned=array();
$resCompletedTasks=array();
$resCompletedTasksPlanned=array();
$resLeftTasks=array();
$resLeftTasksPlanned=array();
$nbTasks=0;
if ($showCompleted) {
  $resultTasks=Sql::query($query);
  if(Sql::$lastQueryNbRows == 0){
    echo '<div style="background: #FFDDDD;font-size:150%;color:#808080;text-align:center;padding:20px">';
    echo i18n('noDataFound'); // TODO i18n message
    echo '</div>';
    if (!empty($cronnedScript)) goto end; else exit;
  }
  while ($line = Sql::fetchLine($resultTasks)) {
    if ($line['realend']) {
      $day=$line['realend'];
      if (isset($tabCompletedTasks[$day])){ $tabCompletedTasks[$day]++;}
      else {$tabCompletedTasks[$day]=1;}
      $nbTasks++;
    } else if ($line['plannedend']){
      $day=$line['plannedend'];
      if (isset($tabCompletedTasksPlanned[$day])) {$tabCompletedTasksPlanned[$day]++;}
      else {$tabCompletedTasksPlanned[$day]=1;}
      $nbTasks++;
    } else {
      // No real, no planned => not taken into account
    }
  }
}
if (checkNoData(array_merge($tabLeft,$tabLeftPlanned))) if (!empty($cronnedScript)) goto end; else exit;
//gautier #4369
if(count($tabLeftPlanned)==1 and isset($tabLeftPlanned[$today])){
  if(pq_trim($tabLeftPlanned[$today])==0){
    echo '<div style="background: #FFDDDD;font-size:150%;color:#808080;text-align:center;padding:20px">';
    echo i18n('reportNoData');
    echo '</div>';
    if (!empty($cronnedScript)) goto end; else exit;
  }
}
if($idProject){
  $pe=SqlElement::getSingleSqlElementFromCriteria('PlanningElement',array('refType'=>'Project', 'refId'=>$idProject));
  if (pq_trim($pe->realStartDate) and $pe->realStartDate<$start) $start=$pe->realStartDate;
  if (pq_trim($pe->realEndDate) and $pe->realEndDate>$end) $end=$pe->realEndDate;
  if (pq_trim($pe->validatedEndDate) and $pe->validatedEndDate>$end) $end=$pe->validatedEndDate;
  if (pq_trim($pe->validatedStartDate)) {
    $valStart=$pe->realStartDate;
  } else {
    $valStart=$start;
  }
} else {
  $valStart=$start;
}
$arrDates=array();
$date=$start;
if (!$date) $date=$today;
if (!$start or !$end) {
  echo '<div style="background: #FFDDDD;font-size:150%;color:#808080;text-align:center;padding:20px">';
  echo i18n('reportNoData'); 
  echo '</div>';
  if (!empty($cronnedScript)) goto end; else exit;
}
while ($date<=$end) {
  if ($scale=='week') { 
    //$arrDates[$date]=date('Y-W',pq_strtotime($date)); 
    $arrDates[$date]=weekFormat($date);
  } else if ($scale=='month') { 
    $arrDates[$date]=date('Y-m',pq_strtotime($date));  
  } else if ($scale=='quarter') { 
    $year=date('Y',pq_strtotime($date));
    $month=date('m',pq_strtotime($date));
    $quarter=1+intval(($month-1)/3);
    $arrDates[$date]=$year.'-Q'.$quarter;  
  } else { 
    $arrDates[$date]=$date;
  }
  $date=addDaysToDate($date, 1);
}

if ($idFilterCriteria and (! isset($resLeft[$start]) or $resLeft[$start]==VOID)) {
  $tabLeft[$start]=$lastLeft+$maxReal;
}
if ($idFilterCriteria) { // RETRIEVE WORK TO DECREASE VALUE
  $w=new Work();
  $currentLeft=$lastLeft+$maxReal;
  $wTable=$w->getDatabaseTableName();
  //select
  $querySelect= "select sum(w.work) as work, w.workDate as day ";
  $queryFrom=   " from $wTable w";
  $queryJoin=  " LEFT JOIN $actcrtTable a ON w.refId = a.id  AND w.refType = 'Activity'";
  if($peCritOn){
    $queryJoin .= "LEFT JOIN $peTable pe ON w.refId = pe.refId AND pe.refType = 'Activity'";
  }
  if ($startDateReport) $queryWhere= "  where w.workDate>='$startDateReport'";
  else $queryWhere=  " where 1=1";
  $queryWhere .= " AND $myFilters";
  $queryOrder= "  group by w.workDate order by w.workDate";
  $query=$querySelect.$queryFrom.$queryJoin.$queryWhere.$queryOrder;
  $resultReal=Sql::query($query);
  while ($line = Sql::fetchLine($resultReal)) {
    $day=$line['day'];
    $work=$line['work']??0;
    $currentLeft-=$work;
    $tabLeft[$day]=$currentLeft;
  }
}

$lastTabLeft=$lastLeft+$maxReal;
foreach ($arrDates as $date => $period) {
  if (isset($tabLeft[$date])) $lastTabLeft=$tabLeft[$date];
  else $tabLeft[$date]=$lastTabLeft;
}


$old=null;
$old=reset($tabLeft);
$oldPlanned=$lastLeft;
$nbSteps=0;
$leftTasks=$nbTasks;
$completedFound=0;
$plannedCompletedNotDone=0;
foreach ($arrDates as $date => $period) {
  if ($date>$endReal) {
    if (!isset($resLeft[$period])) $resLeft[$period]=VOID;
  } else if (isset($tabLeft[$date])) {
    if (isset($tabLeftPlanned[$date])) {
      $resLeft[$period]=Work::displayWork($tabLeftPlanned[$date]);
      $old=$tabLeftPlanned[$date];
    } else {
      $resLeft[$period]=Work::displayWork($tabLeft[$date]);
      $old=$tabLeft[$date];
    }
    
  } else {
    if ($idFilterCriteria and $date<$today) $resLeft[$period]=VOID;
    else $resLeft[$period]=($old===null)?VOID:Work::displayWork($old);
  }
  if (isset($tabLeftPlanned[$date])) {
    $resLeftPlanned[$period]=Work::displayWork($tabLeftPlanned[$date]);
    $oldPlanned=$tabLeftPlanned[$date];
  } else {
    if ($date>=$endReal) {
      $resLeftPlanned[$period]=Work::displayWork($oldPlanned);
    } else  {
      $resLeftPlanned[$period]=VOID;
    }
  }
  if ($showCompleted) {
    if (isset($tabCompletedTasks[$date])) {
      if (isset($resCompletedTasks[$period])) { $resCompletedTasks[$period]+=$tabCompletedTasks[$date];}
      else {$resCompletedTasks[$period]=$tabCompletedTasks[$date];}
      $leftTasks-=$tabCompletedTasks[$date];
    } else if (! isset($resCompletedTasks[$period]) ){
      $resCompletedTasks[$period]=VOID;
    }  
    if (isset($tabCompletedTasksPlanned[$date])) {
      if (isset($resCompletedTasksPlanned[$period])) { $resCompletedTasksPlanned[$period]+=$tabCompletedTasksPlanned[$date];}
      else {$resCompletedTasksPlanned[$period]=$tabCompletedTasksPlanned[$date];}
      if (count($tabCompletedTasks)>0) {
        $plannedCompletedNotDone+=$tabCompletedTasksPlanned[$date];
      } else {
        $leftTasks-=$tabCompletedTasksPlanned[$date];
      }
    } else if (! isset($resCompletedTasksPlanned[$period]) ){
      $resCompletedTasksPlanned[$period]=VOID;
    }  
    if (count($tabCompletedTasks)>0) { 
      $resLeftTasks[$period]=$leftTasks; 
      $resLeftTasksPlanned[$period]=VOID;
    } else {
      if (! isset($resLeftTasks[$period])) {
        $resLeftTasks[$period]=VOID;
      }
      $resLeftTasksPlanned[$period]=$leftTasks;
    }
    if (isset($tabCompletedTasks[$date])) {
      unset($tabCompletedTasks[$date]);
      if (count($tabCompletedTasks)==0) {
        $resLeftTasks[$period]=$leftTasks;
        $leftTasks-=$plannedCompletedNotDone;
        $resLeftTasksPlanned[$period]=$leftTasks;
      }
    }
    
  }
  if ($date>=$valStart and $date<=$pe->validatedEndDate) $nbSteps++;
}

$startLabel=reset($arrDates);
$maxLeft=0;
//if ($idProject) $maxLeft=Work::displayWork($pe->validatedWork);
if (!$maxLeft and isset($resLeft[$startLabel])) $maxLeft=$resLeft[$startLabel];
if (!$maxLeft and isset($resLeftPlanned[$startLabel])) $maxLeft=$resLeftPlanned[$startLabel];
$minLeft=0;
//$nbSteps=count($arrDates)-1;
if (!$nbSteps) $nbSteps=count($arrDates);
$stepValue=($nbSteps>1)?(($maxLeft-$minLeft)/($nbSteps-1)):0;
$val=$maxLeft;

$graphWidth=1200;
$graphHeight=720;
$indexToday=0;
$today=null;
foreach ($arrDates as $date => $period) {
  if ($date==date('Y-m-d')) {$today=$period;}
  if ($date<$valStart) {
    $resBest[$period]=VOID;
    continue;
  }
  if ($val!==VOID or ! isset($resBest[$period])) $resBest[$period]=$val;
  if ($val) {
    $val-=$stepValue;
    if ($val<0) $val=VOID;
    else if ($val<0.1 and $scale!='day') $val=VOID;
  } else {
    $val=VOID;
  }
}
if ($scale!='day') $resBest[$period]=VOID;
$startDatePeriod=null;
$endDatePeriod=null;
if ($startDateReport and isset($arrDates[$startDateReport])) $startDatePeriod=$arrDates[$startDateReport];
if ($endDateReport and isset($arrDates[$endDateReport])) $endDatePeriod=$arrDates[$endDateReport];
if ($startDatePeriod or $endDatePeriod) {
  foreach ($arrDates as $date => $period) {
    if ( ($startDatePeriod and $period<$startDatePeriod) or ($endDatePeriod and $period>$endDatePeriod) ) {
      unset($arrDates[$date]);
      unset($resBest[$period]);
      unset($resLeft[$period]);
      unset($resLeftPlanned[$period]);
      if ($showCompleted){
        unset($resLeftTasks[$period]);
        unset($resLeftTasksPlanned[$period]);
        unset($resCompletedTasks[$period]);
        unset($resCompletedTasksPlanned[$period]);
      }
    }
    //if ($idFilterCriteria and $date!=$startDatePeriod) unset($resLeft[$period]);
  }
}


$arrDates=array_flip($arrDates);
$cpt=0;
$modulo=intVal(50*count($arrDates)/$graphWidth);
if ($modulo<0.5) $modulo=0;
foreach ($arrDates as $date => $period) {
  if ($period<date('Y-m-d')) $indexToday++;
  if (0 and $cpt % $modulo !=0 ) {
    $arrDates[$date]=VOID;
  } else {
    if ($scale=='day') {
      $arrDates[$date]=htmlFormatDate($date);
    } else if ($scale=='month') {
      $arrDates[$date]=getMonthName(pq_substr($date,5)).' '.pq_substr($date,0,4);
    } else {
      $arrDates[$date]=$date;
    }
  }
  $cpt++;
}
$arrLabel=array();
$arrVoidLabel=array();


foreach($arrDates as $date){
  $arrLabel[]=$date;
  $arrVoidLabel[]=VOID;
}

$resLeftTasksScale=$resLeftTasks;
if ($nbTasks<150) {
  $maxVal=$nbTasks;
  if ($nbTasks<20) {
    if (intval($nbTasks/2)!=($nbTasks/2)) $maxVal+=1;
  } else {
    if (intval($nbTasks/20)!=($nbTasks/20)) $maxVal=intval(($nbTasks+20)/20)*20;
    else $maxVal=intval(($nbTasks)/20)*20;
  }
  array_splice($resLeftTasksScale, count($resLeftTasksScale)-1);
  $resLeftTasksScale[]=$maxVal;
}

$maxPlotted=30; // max number of point to get plotted lines. If over lines are not plotted/

//if the end date is earlier than the start date
if ($endDateReport<=$startDateReport && $endDateReport) {
  echo '<div style="background: #FFDDDD;font-size:150%;color:#808080;text-align:center;padding:20px">';
  echo i18n('messageNoData',array(i18n('date'))); // TODO i18n message
  echo '</div>';
  if (!empty($cronnedScript)) goto end; else exit;
}

$dataSet = new pData();
// Definition of series
$dataSet->addPoints($resBest,"best");
$dataSet->addPoints($resLeft,"left");
$dataSet->addPoints($resLeftPlanned,"leftPlanned");
$dataSet->setSerieOnAxis("best",0);
$dataSet->setSerieOnAxis("left",0);
$dataSet->setSerieOnAxis("leftPlanned",0);
if ($showCompleted){
  $dataSet->addPoints($resLeftTasks,"leftTasks");
  $dataSet->addPoints($resLeftTasksPlanned,"leftTasksPlanned");
  $dataSet->addPoints($resCompletedTasks,"completedTasks");
  $dataSet->addPoints($resCompletedTasksPlanned,"completedTasksPlanned");
  $dataSet->setSerieOnAxis("leftTasks",1);
  $dataSet->setSerieOnAxis("leftTasksPlanned",1);
  $dataSet->setSerieOnAxis("completedTasks",1);
  $dataSet->setSerieOnAxis("completedTasksPlanned",1);
  $dataSet->setSerieDescription("leftTasks",i18n("legendRemainingTasks")."  ");
  $dataSet->setSerieDescription("leftTasksPlanned",i18n("legendRemainingTasks").' ('.i18n('planned').')  ',"leftPlanned");
  $dataSet->setSerieDescription("completedTasks",i18n("legendCompletedTasks")."  ");
  $dataSet->setSerieDescription("completedTasksPlanned",i18n("legendCompletedTasks").' ('.i18n('planned').')  ',"leftPlanned");
}

$dataSet->setAxisPosition(1,AXIS_POSITION_RIGHT);
$dataSet->setAxisName(0,i18n("legendRemainingEffort"). ' ('.i18n(Work::getWorkUnit()).')');
$dataSet->setAxisName(1,i18n("legendNumberOfTasks"));
$dataSet->setAxisUnit(0,' '.Work::displayShortWorkUnit().' ');
$dataSet->setAxisUnit(1,' ');
/* Create the abscissa serie */
$dataSet->addPoints($arrLabel,"dates");
//$dataSet->setSerieDescription("dates","My labels");
$dataSet->setSerieDescription("best",i18n("legendBestBurndown")."  ");
$dataSet->setSerieDescription("left",i18n("legendRemainingEffort")."  ");
$dataSet->setSerieDescription("leftPlanned",i18n("legendRemainingEffort").' ('.i18n('planned').')  ',"leftPlanned");

$dataSet->setAbscissa("dates");

/* Create the pChart object */
$graph = new pImage($graphWidth,$graphHeight,$dataSet);

/* Draw the background */
$graph->Antialias = FALSE;
$Settings = array("R"=>240, "G"=>240, "B"=>240, "Dash"=>0, "DashR"=>0, "DashG"=>0, "DashB"=>0);
$graph->drawFilledRectangle(0,0,$graphWidth,$graphHeight,$Settings);

/* Add a border to the picture */
$graph->drawRectangle(0,0,$graphWidth-1,$graphHeight-1,array("R"=>150,"G"=>150,"B"=>150));

/* Set the default font */
$graph->setFontProperties(array("FontName"=>getFontLocation("verdana"),"FontSize"=>9,"R"=>100,"G"=>100,"B"=>100));

/* Draw the scale */
$graph->setGraphArea(60,30,$graphWidth-55,$graphHeight-(($scale=='month')?100:75));
$graph->drawFilledRectangle(60,30,$graphWidth-55,$graphHeight-(($scale=='month')?100:75),array("R"=>255,"G"=>255,"B"=>255,"Surrounding"=>-200,"Alpha"=>230));
$formatGrid=array("LabelSkip"=>$modulo, "SkippedAxisAlpha"=>(($modulo>9)?0:20), "SkippedGridTicks"=>0,
    "Mode"=>SCALE_MODE_START0, "GridTicks"=>0,
    "DrawYLines"=>array(0), "DrawXLines"=>true,"Pos"=>SCALE_POS_LEFTRIGHT, 
    "LabelRotation"=>60, "GridR"=>200,"GridG"=>200,"GridB"=>200);
$graph->drawScale($formatGrid);

$dataSet->setSerieWeight("best",1);
$dataSet->setSerieWeight("left",1);
$dataSet->setSerieWeight("leftPlanned",1);
$dataSet->setSerieWeight("leftTasks",1);
$dataSet->setSerieWeight("leftTasksPlanned",1);
$dataSet->setPalette("best",array("R"=>250,"G"=>180,"B"=>210,"Alpha"=>255));
$dataSet->setPalette("left",array("R"=>120,"G"=>140,"B"=>250,"Alpha"=>255));
$dataSet->setPalette("leftPlanned",array("R"=>180,"G"=>180,"B"=>250,"Alpha"=>50));
$dataSet->setPalette("leftTasks",array("R"=>50,"G"=>150,"B"=>50,"Alpha"=>100));
$dataSet->setPalette("leftTasksPlanned",array("R"=>100,"G"=>200,"B"=>100,"Alpha"=>50));
$dataSet->setPalette("completedTasks",array("R"=>200,"G"=>200,"B"=>100,"Alpha"=>80));
$dataSet->setPalette("completedTasksPlanned",array("R"=>240,"G"=>240,"B"=>150,"Alpha"=>80));
$dataSet->setSerieTicks("leftTasksPlanned",3);
$dataSet->setSerieTicks("leftPlanned",3);

$dataSet->setSerieDrawable("completedTasks",true);
$dataSet->setSerieDrawable("completedTasksPlanned",true);
$dataSet->setSerieDrawable("best",FALSE);
$dataSet->setSerieDrawable("left",FALSE);
$dataSet->setSerieDrawable("leftPlanned",FALSE);
$dataSet->setSerieDrawable("leftTasks",FALSE);
$dataSet->setSerieDrawable("leftTasksPlanned",FALSE);
$graph->drawStackedBarChart();

$dataSet->setSerieDrawable("completedTasks",FALSE);
$dataSet->setSerieDrawable("completedTasksPlanned",FALSE);

$graph->Antialias = TRUE;
/* Write the chart title */
$dataSet->setSerieDrawable("best",true);
$dataSet->setSerieDrawable("left",true);
$dataSet->setSerieDrawable("leftPlanned",true);
$dataSet->setSerieDrawable("leftTasks",true);
$dataSet->setSerieDrawable("leftTasksPlanned",true);
//$graph->setShadow(TRUE,array("X"=>1,"Y"=>1,"R"=>0,"G"=>0,"B"=>0,"Alpha"=>10));
$graph->drawLineChart();
//$graph->drawSplineChart();

$dataSet->setSerieDrawable("best",false);
if (count($resLeft)<$maxPlotted) {
  $graph->drawPlotChart();
}

//gautier #today should not be visible if date of today is not display
$today = date('Y-m-d');
if ($showToday and $today >= $start and $today <= $end and $indexToday){
  $graph->drawXThreshold(array($indexToday),array("Alpha"=>70,"Ticks"=>0));
}

$dataSet->setSerieDrawable("best",true);
$dataSet->setSerieDrawable("left",true);
$dataSet->setSerieDrawable("leftPlanned",true);
$dataSet->setSerieDrawable("leftTasks",true);
$dataSet->setSerieDrawable("leftTasksPlanned",true);
$dataSet->setSerieDrawable("completedTasks",true);
$dataSet->setSerieDrawable("completedTasksPlanned",true);

if ($legend=="top") {
  $graph->setFontProperties(array("FontName"=>getFontLocation("verdana"),"FontSize"=>10.8,"R"=>100,"G"=>100,"B"=>100));
  $graph->drawLegend(10,10,array("Mode"=>LEGEND_HORIZONTAL, "Family"=>LEGEND_FAMILY_BOX ,
      "R"=>255,"G"=>255,"B"=>255,"Alpha"=>0,
      "FontR"=>55,"FontG"=>55,"FontB"=>55,
      "Margin"=>0));
  $graph->drawText($graphWidth/2,50,i18n("reportBurndownChart"),array("FontSize"=>14,"Align"=>TEXT_ALIGN_BOTTOMMIDDLE));
} else {
  $graph->setFontProperties(array("FontName"=>getFontLocation("verdana"),"FontSize"=>11,"R"=>100,"G"=>100,"B"=>100));
  $graph->drawLegend($graphWidth-350,50,array("Mode"=>LEGEND_VERTICAL, "Family"=>LEGEND_FAMILY_BOX ,
      "R"=>255,"G"=>255,"B"=>255,"Alpha"=>100,
      "FontR"=>55,"FontG"=>55,"FontB"=>55,
      "Margin"=>5));
  $graph->drawText($graphWidth/2,20,i18n("reportBurndownChart"),array("FontSize"=>14,"Align"=>TEXT_ALIGN_BOTTOMMIDDLE));
}
/* Render the picture (choose the best way) */
$imgName=getGraphImgName("burndownChart");
$graph->Render($imgName);

//$graph->autoOutput($imgName);
echo '<table width="95%" align="center"><tr><td align="center">';
echo '<img style="width:1000px;height:600px" src="' . $imgName . '" />'; 
echo '</td></tr></table>';
echo '<br/>';

end:

?>