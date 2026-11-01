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

//echo "colorPlan.php";
include_once '../tool/projeqtor.php';

$paramProject='';
if (pq_array_key_exists('idProject',$_REQUEST)) {
  $paramProject=pq_trim($_REQUEST['idProject']);
  Security::checkValidId($paramProject);
}
$idOrganization = pq_trim(RequestHandler::getId('idOrganization'));
$paramTeam='';
if (pq_array_key_exists('idTeam',$_REQUEST)) {
  $paramTeam=pq_trim($_REQUEST['idTeam']);
  Security::checkValidId($paramTeam);
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
$scale='proportional';
if (pq_array_key_exists('scale',$_REQUEST) and $_REQUEST['scale']=='same') {
	$scale='same';
}

$paramShowAdminProj=RequestHandler::getBoolean('showAdminProj');
$paramShowNextElevenMonths=RequestHandler::getBoolean('includeNextElevenMonths');

$user=getSessionUser();
$printPreview = (RequestHandler::getValue('outMode') == 'html');
$printMode = RequestHandler::getValue('outMode');

$periodType=$_REQUEST['periodType']; // not filtering as data as data is only compared against fixed strings
$periodValue='';
if (pq_array_key_exists('periodValue',$_REQUEST))
{
	$periodValue=$_REQUEST['periodValue'];
	$periodValue=Security::checkValidPeriod($periodValue);
}
$displayByWeek=($periodType=='year');

function colorPlanBuildIsoWeekColumns($isoYear) {
  $columns=array();
  $lastWeek=intval(date('W', pq_strtotime($isoYear.'-12-28')));
  for ($week=1; $week<=$lastWeek; $week++) {
    $weekStart=new DateTime();
    $weekStart->setISODate($isoYear, $week, 1);
    $weekEnd=clone $weekStart;
    $weekEnd->modify('+6 days');
    $key=sprintf('%04d%02d', $isoYear, $week);
    $columns[$key]=array(
      'label'=>$week,
      'dateStart'=>$weekStart->format('Y-m-d'),
      'dateEnd'=>$weekEnd->format('Y-m-d')
    );
  }
  return $columns;
}

function colorPlanBuildPeriodColumns($periodType, $periodValue, $paramYear, $paramMonth, $displayByWeek) {
  $columns=array();
  if ($displayByWeek) {
    return colorPlanBuildIsoWeekColumns(intval($paramYear));
  } else if ($periodType=='month') {
    $nbDays=date("t", mktime(0, 0, 0, $paramMonth, 1, $paramYear));
    for ($i=1; $i<=$nbDays; $i++) {
      $day=(($i<10)?'0':'') . $i;
      $date=$paramYear.'-'.$paramMonth.'-'.$day;
      $columns[$periodValue . $day]=array('label'=>$day, 'dateStart'=>$date, 'dateEnd'=>$date);
    }
  }
  return $columns;
}

function colorPlanGetPeriodBounds($periodColumns) {
  if (!$periodColumns) return array('dateStart'=>null, 'dateEnd'=>null);
  $first=reset($periodColumns);
  $last=end($periodColumns);
  return array('dateStart'=>$first['dateStart'], 'dateEnd'=>$last['dateEnd']);
}

function colorPlanBuildRecurringOffWeekdays($globalOffWeekdays, $calendarOffWeekdays) {
  $offWeekdays=array();
  for ($weekday=0; $weekday<=6; $weekday++) {
    if (!empty($globalOffWeekdays[$weekday]) or !empty($calendarOffWeekdays[$weekday])) {
      $offWeekdays[$weekday]=true;
    }
  }
  return $offWeekdays;
}

function colorPlanCalculateEffectiveWeeklyCapacity($days, $isPool=false) {
  $capacity=0;
  foreach ($days as $day) {
    if (!empty($day['recurringOff']) or !empty($day['holiday'])) continue;
    $dayCapacity=max(0, floatval($day['capacity']));
    if (!$isPool) {
      $leaveWork=max(0, floatval($day['leaveWork']));
      $dayCapacity-=min($dayCapacity, $leaveWork);
    }
    $capacity+=$dayCapacity;
  }
  return round(max(0, $capacity), 2);
}

function colorPlanIsLeaveWorkData($idLeave, $idProject, $leaveProjectId) {
  return !empty($idLeave) or ($leaveProjectId and $idProject==$leaveProjectId);
}

function colorPlanMergeDailyLeave(&$leaveResult, $idResource, $day, $work, $isReal, $workDate, $today) {
  if (!isset($leaveResult[$idResource])) $leaveResult[$idResource]=array();
  if (!isset($leaveResult[$idResource][$day])) {
    $leaveResult[$idResource][$day]=array('work'=>0);
  }
  if ($isReal) {
    $leaveResult[$idResource][$day]['real']=true;
    $leaveResult[$idResource][$day]['work']+=$work;
  } else if (!isset($leaveResult[$idResource][$day]['real']) or $workDate>=$today) {
    $leaveResult[$idResource][$day]['work']+=$work;
  }
}

function colorPlanAggregateResultByWeek($result, $periodColumns) {
  $weekResult=array();
  foreach ($result as $idResource=>$periods) {
    $weekResult[$idResource]=array();
    foreach ($periods as $day=>$dayData) {
      $date=pq_substr($day,0,4).'-'.pq_substr($day,4,2).'-'.pq_substr($day,6,2);
      $weekKey=date('oW', strtotime($date));
      if (!isset($periodColumns[$weekKey])) continue;
      if (!isset($weekResult[$idResource][$weekKey])) {
        $weekResult[$idResource][$weekKey]=array();
      }
      foreach ($dayData as $key=>$value) {
        if ($key=='real') {
          $weekResult[$idResource][$weekKey]['real']=true;
        } else if ($key=='refType' or $key=='refId') {
          if (!pq_array_key_exists($key, $weekResult[$idResource][$weekKey])) {
            $weekResult[$idResource][$weekKey][$key]=$value;
          } else if ($weekResult[$idResource][$weekKey][$key]!=$value) {
            $weekResult[$idResource][$weekKey][$key]='';
          }
        } else {
          if (!isset($weekResult[$idResource][$weekKey][$key])) {
            $weekResult[$idResource][$weekKey][$key]=0;
          }
          $weekResult[$idResource][$weekKey][$key]+=$value;
        }
      }
    }
  }
  return $weekResult;
}

function colorPlanBuildWeeklySegments($values, $weeklyCapacity, $projectColors, $cellHeight=20, $heightReferenceCapacity=null) {
  $layout=array('segments'=>array(), 'remainingHeight'=>$cellHeight);
  if ($weeklyCapacity<=0) return $layout;
  $threshold=$weeklyCapacity*0.20;
  $heightCapacity=($heightReferenceCapacity and $heightReferenceCapacity>0)?$heightReferenceCapacity:$weeklyCapacity;
  $groupedWork=0;
  foreach ($values as $idProject=>$work) {
    if (!is_numeric($idProject) or $work<=0) continue;
    if ($work<$threshold) {
      $groupedWork+=$work;
      continue;
    }
    $layout['segments'][]=array(
      'idProject'=>$idProject,
      'work'=>$work,
      'height'=>intval(floor($cellHeight*$work/$heightCapacity)),
      'color'=>(isset($projectColors[$idProject]))?$projectColors[$idProject]:'#777777',
      'grouped'=>false
    );
  }
  if ($groupedWork>0) {
    $groupedWork=round($groupedWork, 10);
    $layout['segments'][]=array(
      'idProject'=>'colorPlanGroupedProjects',
      'work'=>$groupedWork,
      'height'=>intval(floor($cellHeight*$groupedWork/$heightCapacity)),
      'color'=>'#b5b5b5',
      'grouped'=>true
    );
  }
  $usedHeight=0;
  foreach ($layout['segments'] as $segment) $usedHeight+=$segment['height'];
  $layout['remainingHeight']=max(0, $cellHeight-$usedHeight);
  return $layout;
}

function colorPlanResourceCapacityForPeriod($resource, $period, $displayByWeek, $idCalendarDefinition=null, $leaveByDay=array()) {
  if (!$displayByWeek) {
    return round($resource->getCapacityPeriod($period['dateStart']), 2);
  }
  if (!$idCalendarDefinition) $idCalendarDefinition=1;
  $calendarDefinition=new CalendarDefinition($idCalendarDefinition);
  $parameterCodes=array(
    0=>'OpenDaySunday',
    1=>'OpenDayMonday',
    2=>'OpenDayTuesday',
    3=>'OpenDayWednesday',
    4=>'OpenDayThursday',
    5=>'OpenDayFriday',
    6=>'OpenDaySaturday'
  );
  $globalOffWeekdays=array();
  $calendarOffWeekdays=array();
  foreach ($parameterCodes as $weekday=>$parameterCode) {
    $globalOffWeekdays[$weekday]=(Parameter::getGlobalParameter($parameterCode)=='offDays');
    $field='dayOfWeek'.$weekday;
    $calendarOffWeekdays[$weekday]=(!empty($calendarDefinition->$field));
  }
  $recurringOffWeekdays=colorPlanBuildRecurringOffWeekdays($globalOffWeekdays, $calendarOffWeekdays);
  $days=array();
  $date=new DateTime($period['dateStart']);
  $end=new DateTime($period['dateEnd']);
  while ($date<=$end) {
    $day=$date->format('Y-m-d');
    $dayKey=$date->format('Ymd');
    $weekday=intval($date->format('w'));
    $recurringOff=!empty($recurringOffWeekdays[$weekday]);
    $days[]=array(
      'capacity'=>$resource->getCapacityPeriod($day),
      'recurringOff'=>$recurringOff,
      'holiday'=>(!$recurringOff and isOffDay($day, $idCalendarDefinition)),
      'leaveWork'=>(isset($leaveByDay[$dayKey]))?$leaveByDay[$dayKey]:0
    );
    $date->modify('+1 day');
  }
  return colorPlanCalculateEffectiveWeeklyCapacity($days, !empty($resource->isResourceTeam));
}

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
if ($periodType=='year' or $periodType=='month' or $periodType=='week') {
  $headerParameters.= i18n("year") . ' : ' . $paramYear . '<br/>';
  
}
if ($periodType=='month') {
  $headerParameters.= i18n("month") . ' : ' . $paramMonth . '<br/>';
}
if ( $periodType=='week') {
  $headerParameters.= i18n("week") . ' : ' . $paramWeek . '<br/>';
}
$nbMonths=1;
if ($periodType=='month' and isset($_REQUEST['includeNextMonth'])) {
  $nbMonths=2;
  $headerParameters.= i18n("colIncludeNextMonth").'<br/>';
}
if ($periodType=='month' and $paramShowNextElevenMonths){
  $nbMonths=13;
  $headerParameters.= i18n("colIncludeNextElevenMonths").'<br/>';
}
if ($paramShowAdminProj) {
  $headerParameters.= i18n("colShowAdminProj").'<br/>';
}

$headerParameters.=i18n("colFormat"). ' : ' . i18n('scale'.pq_ucfirst($scale)).'<br/>';

include "header.php";

$initParamMonth=$paramMonth;
// LOOP FOR SEVERAL MONTHS
$initParamYear = $paramYear;
for ($cptMonth=0;$cptMonth<$nbMonths;$cptMonth++) {
  if ($periodType=='month') {
//     $paramMonth=intval($initParamMonth)+$cptMonth;
//   if ($paramMonth>12) {$paramYear+=1;$paramMonth=1;}
//     if ($paramMonth<10) $paramMonth='0'.$paramMonth;
//     $periodValue=$paramYear.$paramMonth;
    $baseDate = "$initParamYear-$initParamMonth-01";
    $newDate = date('Y-m', strtotime("+$cptMonth months", strtotime($baseDate)));
    $paramYear = substr($newDate, 0, 4);
    $paramMonth = substr($newDate, 5, 2);
    $periodValue = $paramYear.$paramMonth;
  }
  if ($displayByWeek and !$paramYear) {
    echo '<div style="background: #FFDDDD;font-size:150%;color:#808080;text-align:center;padding:20px">';
    echo i18n('messageNoData',array(i18n('year')));
    echo '</div>';
    if (!empty($cronnedScript)) goto end; else exit;
  }
  if ($displayByWeek) {
    $periodColumns=colorPlanBuildPeriodColumns($periodType, $periodValue, $paramYear, $paramMonth, true);
    $periodBounds=colorPlanGetPeriodBounds($periodColumns);
    $yearlyStartDate=$periodBounds['dateStart'];
    $yearlyEndDate=$periodBounds['dateEnd'];
  }
  
$where=getAccesRestrictionClause('Resource',false,false,true,true);
//$where="1=1";
$where='('.$where.' or idProject in '.Project::getAdminitrativeProjectList().')';

$where.=($periodType=='week')?" and week='" . $periodValue . "'":'';
$where.=($periodType=='month')?" and month='" . $periodValue . "'":'';
if ($displayByWeek) {
  $where.=" and workDate>='$yearlyStartDate' and workDate<='$yearlyEndDate'";
} else {
  $where.=($periodType=='year')?" and year='" . $periodValue . "'":'';
}
if ($paramProject!='') {
//   $where.=  "and ( idProject in " . getVisibleProjectsList(true, $paramProject) ;
//   if ($paramShowAdminProj) {
//     $where.= "or idProject in ".Project::getAdminitrativeProjectList();
//   }
//   $where.= ")";
}
$order="";
$work=new Work();
$lstWork=$work->getSqlElementsFromCriteria(null,false, $where, $order);
$result=array();
$projects=array(); 
$projectsColor=array();
$resources=array();
$resourcesTeam=array();
$resourceCapacity=array();
//gautier #2441
$idRessource=getSessionUser()->id;
$resss=new ResourceAll($idRessource);
$resourcesFull = array();
$resourcesAffect= array();
$resourcesToShow = array();
$leaveResult=array();
$leaveProjectId=($displayByWeek)?Project::getLeaveProjectId():null;
$specific='imputation';
$commonElement = getListForSpecificRights($specific,true);
$resourcesToShow=$commonElement;
$refIdCell = '';
$refTypeCell = '';
//$commonElement = $table;
//no parameters
//project

if($paramProject){
  $proj=new Project($paramProject);
  $listProj=$proj->getRecursiveSubProjectsFlatList(false,true);
  if ($paramShowAdminProj) {
    foreach (Project::getAdminitrativeProjectList(true) as $idP=>$nameP) {
      $listProj[$idP]=$nameP;
    }
  }
  $resourcesAffect = SqlList::getListWithCrit('Affectation', array('idProject'=>array_keys($listProj)),'idResource');
  $resourcesProject = SqlList::getListWithCrit('ResourceAll', array('id'=>$resourcesAffect));
  $resourcesToShow = array_intersect($resourcesToShow,$resourcesProject);
} else {
  $resourcesNotClose = SqlList::getListWithCrit('ResourceAll', array('idle'=>'0'));
  $resourcesToShow = array_intersect($resourcesToShow,$resourcesNotClose);
}

if ($displayByWeek) {
  $selectedDateStart=$yearlyEndDate;
  $selectedDateEnd=$yearlyStartDate;
} else {
  $selectedDateStart="$paramYear-$paramMonth-".lastDayOfMonth($paramMonth,$paramYear);
  $selectedDateEnd="$paramYear-$paramMonth-01";
}
$resourcesNotHereBeforeStart = SqlList::getListWithCrit('ResourceAll',"idle=0 and startdate>'$selectedDateStart'");
foreach ($resourcesNotHereBeforeStart as $res) {
  foreach($resourcesToShow as $key=>$value) {
    if ($res == $value) {
      unset($resourcesToShow["$key"]);
    }
  }
}
$resourcesNotHereAfterEnd = SqlList::getListWithCrit('ResourceAll',"idle=0 and enddate<'$selectedDateEnd'");
foreach ($resourcesNotHereAfterEnd as $res) {
  foreach($resourcesToShow as $key=>$value) {
    if ($res == $value) {
      unset($resourcesToShow["$key"]);
    }
  }
}
//team
if($paramTeam){
  $resourcesTeam =SqlList::getListWithCrit('ResourceAll', array('idTeam'=>$paramTeam));
  $resourcesToShow = array_intersect($resourcesToShow,$resourcesTeam);
}

// organization
if($idOrganization){
  $orga = new Organization($idOrganization);
  $listResOrg=$orga->getResourcesOfAllSubOrganizationsListAsArray();
  foreach ($resourcesToShow as $idR=>$nameR){
    if(! in_array($idR, $listResOrg)) unset($resourcesToShow[$idR]);
  }
}
foreach ($lstWork as $work) {
  //if (! isset($resourcesToShow[$work->idResource])) continue;
  if ($displayByWeek and colorPlanIsLeaveWorkData($work->idLeave, $work->idProject, $leaveProjectId)) {
    colorPlanMergeDailyLeave($leaveResult, $work->idResource, $work->day, $work->work, true, $work->workDate, date('Y-m-d'));
    continue;
  }
  if ($paramProject and isset($listProj) and !isset($listProj[$work->idProject]) ) continue;
  if (! pq_array_key_exists($work->idResource,$resources)) {
    if ($paramTeam) {
      $team=SqlList::getFieldFromId('ResourceAll', $work->idResource,'idTeam');
      if ($team!=$paramTeam) continue;
    }
    if ($idOrganization) {
      $orga=SqlList::getFieldFromId('ResourceAll', $work->idResource,'idOrganization');
      if ($orga!=$idOrganization) continue;
    }
	$nameResToAdd=SqlList::getNameFromId('ResourceAll', $work->idResource);
    if ($nameResToAdd==$work->idResource) continue;
    $resources[$work->idResource]=$nameResToAdd;
  	$resourceCapacity[$work->idResource]=SqlList::getFieldFromId('ResourceAll', $work->idResource, 'capacity');
    $result[$work->idResource]=array();
  }
  if (! pq_array_key_exists($work->idProject,$projects)) {
    $projects[$work->idProject]=SqlList::getNameFromId('Project', $work->idProject);
    $proj=new Project($work->idProject);
    $projectsColor[$work->idProject]=$proj->getColor();
  }
  if (! pq_array_key_exists($work->day,$result[$work->idResource])) {
    $result[$work->idResource][$work->day]=array();
  }
  if (! pq_array_key_exists($work->idProject,$result[$work->idResource][$work->day])) {
    $result[$work->idResource][$work->day][$work->idProject]=0;
    $result[$work->idResource][$work->day]['real']=true;
  }
  if (!pq_array_key_exists('refType', $result[$work->idResource][$work->day])) {
      $result[$work->idResource][$work->day]['refType'] = $work->refType;
  }else {
    $result[$work->idResource][$work->day]['refType'] = '';
  }
  if (!pq_array_key_exists('refId', $result[$work->idResource][$work->day])) {
      $result[$work->idResource][$work->day]['refId'] = $work->refId;
  }else {
    $result[$work->idResource][$work->day]['refId'] = '';
  }
  $result[$work->idResource][$work->day][$work->idProject]+=$work->work;
  //echo "work : " . htmlEncode($work->day) . " / " . htmlEncode($work->idProject) . " / " . htmlEncode($work->idResource) . " / " . htmlEncode($work->work) . "<br/>";
}
$planWork=new PlannedWork();
$lstPlanWork=$planWork->getSqlElementsFromCriteria(null,false, $where, $order);
foreach ($lstPlanWork as $work) {  
  //if (! isset($resourcesToShow[$work->idResource])) continue;
  if ($displayByWeek and colorPlanIsLeaveWorkData($work->idLeave, $work->idProject, $leaveProjectId)) {
    colorPlanMergeDailyLeave($leaveResult, $work->idResource, $work->day, $work->work, false, $work->workDate, date('Y-m-d'));
    continue;
  }
  if ($paramProject and isset($listProj) and !isset($listProj[$work->idProject]) ) continue;
  if (! pq_array_key_exists($work->idResource,$resources)) {
    if ($paramTeam) {
      $team=SqlList::getFieldFromId('ResourceAll', $work->idResource,'idTeam');
      if ($team!=$paramTeam) continue;
    }
    if ($idOrganization) {
      $orga=SqlList::getFieldFromId('ResourceAll', $work->idResource,'idOrganization');
      if ($orga!=$idOrganization) continue;
    }
    
    $nameResToAdd=SqlList::getNameFromId('ResourceAll', $work->idResource);
    if ($nameResToAdd==$work->idResource) continue;
    $resources[$work->idResource]=$nameResToAdd;
    $resourceCapacity[$work->idResource]=SqlList::getFieldFromId('ResourceAll', $work->idResource, 'capacity');
    $result[$work->idResource]=array();
  }
  if (! pq_array_key_exists($work->idProject,$projects)) {
    $projects[$work->idProject]=SqlList::getNameFromId('Project', $work->idProject);
    $proj=new Project($work->idProject);
    $projectsColor[$work->idProject]=$proj->getColor();
  }
  if (! pq_array_key_exists($work->day,$result[$work->idResource])) {
    $result[$work->idResource][$work->day]=array();
  }
  if (! pq_array_key_exists($work->idProject,$result[$work->idResource][$work->day])) {
    $result[$work->idResource][$work->day][$work->idProject]=0;
  }
  if (! pq_array_key_exists('real',$result[$work->idResource][$work->day]) or $work->workDate>=date('Y-m-d')) { // Do not add planned if real exists 
    // PBER : show planned in the future event if real exists (may be admin project, or planned intervention of booked in advance)
    $result[$work->idResource][$work->day][$work->idProject]+=$work->work;
  }
  if (!pq_array_key_exists('refType', $result[$work->idResource][$work->day])) {
      $result[$work->idResource][$work->day]['refType'] = $work->refType;
  }else {
    $result[$work->idResource][$work->day]['refType'] = '';
  }
  if (!pq_array_key_exists('refId', $result[$work->idResource][$work->day])) {
      $result[$work->idResource][$work->day]['refId'] = $work->refId;
  }else {
    $result[$work->idResource][$work->day]['refId'] = '';
  }
}

if ($periodType=='month') {
  $startDate=$periodValue. "01";
  if (!$paramYear) {
    echo '<div style="background: #FFDDDD;font-size:150%;color:#808080;text-align:center;padding:20px">';
    echo i18n('messageNoData',array(i18n('year'))); // TODO i18n message
    echo '</div>';
    if (!empty($cronnedScript)) goto end; else exit;
  } 
  $time=mktime(0, 0, 0, $paramMonth, 1, $paramYear);
  $header=i18n(pq_strftime("%B", $time))." ".pq_strftime("%Y", $time);
} else if ($displayByWeek) {
  $header=$paramYear;
}
if (!$displayByWeek) {
  $periodColumns=colorPlanBuildPeriodColumns($periodType, $periodValue, $paramYear, $paramMonth, false);
}
if ($displayByWeek) {
  $result=colorPlanAggregateResultByWeek($result, $periodColumns);
}
$nbDays=count($periodColumns);
$weekendBGColor='#cfcfcf';
$weekendFrontColor='#555555';
$weekendStyle=' style="background-color:' . $weekendBGColor . '; color:' . $weekendFrontColor . '" ';

$resourcesToShow=array_merge_preserve_keys($resourcesToShow,$resources);
$month=($displayByWeek)?null:$paramYear.'-'.$paramMonth;
if (count($resourcesToShow)==0 and checkNoData($result,$month)) continue;
echo '<table style="width:95%;" align="center" id="areaColorPlanDetail" >';
echo '<tr><td>';
echo '<table width="100%" align="left">';
echo '<tr>';
echo '<td class="reportTableDataFull" style="border:0">';
echo '<div style="height:20px;width:20px;position:relative;background-color:#DDDDDD;">&nbsp;';
echo '<div style="width:20px;position:absolute;top:3px;left:5px;color:#000000;">R</div>';
echo '<div style="width:20px;position:absolute;top:2px;left:6px;color:#FFFFFF;">R</div>';
echo '</div>';
echo '</td><td style="width:100px; padding-left:5px;" class="legend">' . i18n('colRealWork') . '</td>';
echo '<td style="width:5px;">&nbsp;&nbsp;&nbsp;</td>';
echo '<td class="reportTableDataFull" style="border:0">';
echo '<div style="height:20px;width:20px;position:relative;background-color:#DDDDDD;">&nbsp;';
echo '</div>';
echo '</td><td style="width:100px; padding-left:5px;" class="legend">' . i18n('colPlanned') . '</td>';
if ($displayByWeek) {
  echo '<td style="width:5px;">&nbsp;&nbsp;&nbsp;</td>';
  echo '<td class="reportTableDataFull" style="border:0">';
  echo '<div style="height:20px;width:20px;position:relative;background-color:#b5b5b5;">&nbsp;</div>';
  echo '</td><td style="width:300px;padding-left:5px;" class="legend" title="'.i18n('helpOtherProjects').'">'.i18n('otherProjects').'</td>';
}
echo '<td>&nbsp;</td>';
echo "</tr></table>";
//echo "<br/>";

echo '<table width="100%" align="left"><tr>';
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
$cptProj=0;
foreach($projects as $idP=>$nameP) {
	if ((($cptProj) % 8)==0) { echo '</tr><tr>';}
	$cptProj++;
  echo '<td width="20px">';
  echo '<div style="border:1px solid #AAAAAA ;height:20px;width:20px;position:relative;background-color:' . (($projectsColor[$idP])?$projectsColor[$idP]:"#FFFFFF") . ';">&nbsp;';
  echo '</div>';
  echo '</td><td style="width:100px; padding-left:5px;" class="legend">' . htmlEncode($nameP) . '</td>';
  echo '<td width="5px">&nbsp;&nbsp;&nbsp;</td>';
}
echo '<td>&nbsp;</td></tr></table>';
//echo '<br/>';
// title
$planningTableAttributes=($displayByWeek)?'align="center" style="width:100%;"':'align="center"';
$resourceCellStyle=($displayByWeek)?' style="width:90px;max-width:90px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;"':'';
$weekCellStyle=($displayByWeek)?' style="padding-left:0;padding-right:0;text-align:center;font-size:8pt;white-space:nowrap;overflow:hidden;"':'';
echo '<table '.$planningTableAttributes.'><tr><td class="reportTableHeader" rowspan="2"'.$resourceCellStyle.'>' . i18n('Resource') . '</td>';
echo '<td colspan="' . $nbDays . '" class="reportTableHeader">' . $header . '</td>';
echo '</tr><tr>';
$days=array();
$daysCal=array();
$lstCal=SqlList::getList('CalendarDefinition');
foreach($lstCal as $idCal=>$nameCal) {$daysCal[$idCal]=array();}
foreach($periodColumns as $periodKey=>$periodInfo) {
  $style='';
  if (!$displayByWeek and isOffDay($periodInfo['dateStart'])) {
    $days[$periodKey]="off";
    $style=$weekendStyle;
  } else {
    $days[$periodKey]="open";
  }
  foreach($lstCal as $idCal=>$nameCal) {
    if (!$displayByWeek and isOffDay($periodInfo['dateStart'],$idCal)) {
      $daysCal[$idCal][$periodKey]="off";
    } else {
      $daysCal[$idCal][$periodKey]="open";
    }
  }
  $columnLabel=$periodInfo['label'];
  echo '<td class="reportTableColumnHeader" ' . $style . $weekCellStyle . '>' . $columnLabel . '</td>';
}

echo '</tr>';

asort($resourcesToShow);

foreach ($resourcesToShow as $idR=>$nameR) {
  $idCal=SqlList::getFieldFromId('Affectable', $idR, 'idCalendarDefinition');
	//if ($paramTeam) {
    $res=new ResourceAll($idR);//florent ticket #5038
  //}
  if (!$paramTeam or $res->idTeam==$paramTeam) {
    //gautier
    if(pq_array_key_exists($idR,$resourceCapacity)){
  	  $capacity=$resourceCapacity[$idR];
    }else{
      $capacity=SqlList::getFieldFromId('ResourceAll', $idR, 'capacity');
    }
    $maxCapa = 0;
    $resourceLeaveByDay=array();
    if ($displayByWeek and isset($leaveResult[$idR])) {
      foreach ($leaveResult[$idR] as $leaveDay=>$leaveData) {
        $resourceLeaveByDay[$leaveDay]=$leaveData['work'];
      }
    }
    $periodCapacities=array();
    foreach($periodColumns as $periodKey=>$periodInfo) {
      $periodCapacity=colorPlanResourceCapacityForPeriod($res, $periodInfo, $displayByWeek, $idCal, $resourceLeaveByDay);
      $periodCapacities[$periodKey]=$periodCapacity;
     	if($periodCapacity > $maxCapa){
    		$maxCapa = $periodCapacity;
    	}
    }
	  //echo '<tr height="20px"><td class="reportTableLineHeader" style="width:200px">' . $nameR;
    $trHeight =($scale=='same')?(20 * $maxCapa):20;
    $resourceLineStyle=($displayByWeek)?'width:90px;max-width:90px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;':'width:200px';
    echo '<tr height="' . $trHeight . 'px"><td class="reportTableLineHeader" style="'.$resourceLineStyle.'">' . $nameR;
    
	  echo '<div style="float:right;font-size:80%;color:#A0A0A0;">';
	  if($displayByWeek){
	    echo htmlDisplayNumericWithoutTrailingZeros($maxCapa);
	  }else if($capacity != $maxCapa){
	  	echo '<table width="100%"><tr><td style="width:50%;text-align:right;padding-right:10px;">'.htmlDisplayNumericWithoutTrailingZeros($capacity).'</td>';
	  	echo '<td style="width:50%;text-align:left;font-style:italic;">max('.$maxCapa.')</td></tr></table>';
	  }else{
	  	echo htmlDisplayNumericWithoutTrailingZeros($capacity);
	  }
	  echo '</div>';
	  echo '</td>';
	  foreach($periodColumns as $day=>$periodInfo) {
	    $cellCapacity=($displayByWeek)?$periodCapacities[$day]:$capacity;
	    $style="";
	    //if ($days[$day]=="off") {
	    if ($idCal and $daysCal[$idCal][$day]=="off") {
	      $style=$weekendStyle;
	    }
	    echo '<td class="reportTableDataFull" ' . $style . $weekCellStyle . ' valign="top" oncontextmenu="return false;">';
	    // test day and result
	    //if (pq_array_key_exists($resources[$idR],$result) and pq_array_key_exists($resources[$idR],$days )){
  	  if(isset($result[$idR])){
  	    if (pq_array_key_exists($day,$result[$idR])) {
  	      echo "<div style='position:relative;'>";
  	      $real=false;
  	      $refTypeCell='';
  	      $refIdCell='';
  	      foreach ($result[$idR][$day] as $idP=>$val) {
  	        if ($idP=='real') {
  	          $real=true;
  	        }else if ($idP == 'refType'){ 
        	      $refTypeCell = $val;
  	        }else if ($idP == 'refId'){ 
        	      $refIdCell = $val; 
  	        }
  	      }
          if ($displayByWeek) {
            $dateCell=$periodInfo['dateStart'];
            $dateEndCell=$periodInfo['dateEnd'];
            $idcolorPlanDetailDiv="colorPlanDetailDiv-".$idR."-".$dateCell;
            $heightReferenceCapacity=($scale=='same')?$maxCapa:$cellCapacity;
            $weeklyLayout=colorPlanBuildWeeklySegments($result[$idR][$day], $cellCapacity, $projectsColor, $trHeight, $heightReferenceCapacity);
            foreach ($weeklyLayout['segments'] as $segment) {
              if ($segment['height']<=0) continue;
              $idP=$segment['idProject'];
              if ($segment['grouped']) {
                $handlers=!$printPreview ? " onclick=\"reportExtraInformations('$idR', '$dateCell', event, '$dateEndCell');\" oncontextmenu=\"reportExtraInformations('$idR', '$dateCell', event, '$dateEndCell'); return false;\"" : '';
              } else {
                $projectName=htmlEncode($projects[$idP], 'parameter');
                $handlers=!$printPreview ? " onclick='reportGotoElement(\"$idR\", \"$dateCell\", \"$refTypeCell\", \"$refIdCell\", \"$idP\", event, \"$projectName\", \"$dateEndCell\");' oncontextmenu=\"reportExtraInformations('$idR', '$dateCell', event, '$dateEndCell'); return false;\"" : '';
              }
              echo "<div class='$idcolorPlanDetailDiv' id='colorPlanDetail' $handlers style='cursor:pointer;position:relative;height:".$segment['height']."px;background-color:".$segment['color'].";'></div>";
            }
            if ($weeklyLayout['remainingHeight']>0) {
              $handlers=!$printPreview ? " onclick=\"reportExtraInformations('$idR', '$dateCell', event, '$dateEndCell');\" oncontextmenu=\"reportExtraInformations('$idR', '$dateCell', event, '$dateEndCell'); return false;\"" : '';
              echo "<div class='$idcolorPlanDetailDiv' id='colorPlanDetail' $handlers style='cursor:pointer;position:relative;height:".$weeklyLayout['remainingHeight']."px;'></div>";
            }
          } else {
            foreach ($result[$idR][$day] as $idP=>$val) {
              if (!in_array($idP, ['real', 'refType', 'refId'])) {
                if($capacity != 0){
                  if (!$maxCapa) $maxCapa=1;
                  if (!$capacity) $capacit=1;
                  if ($scale=='same') $height=floor($trHeight*$val/$maxCapa);
                  else $height=floor($trHeight*$val/$capacity);
                  $dateCell=pq_substr($day,0,4).'-'.pq_substr($day,4,2).'-'.pq_substr($day,6,2);
                  $idcolorPlanDetailDiv = "colorPlanDetailDiv-" . $idR . "-" . $dateCell;
                  $varOnclickOnContextMenu = !$printPreview ? " onclick='reportGotoElement(\"$idR\", \"$dateCell\", \"$refTypeCell\", \"$refIdCell\", \"$idP\", event, \"" . htmlEncode($projects[$idP],'parameter') . "\");' oncontextmenu=\"reportExtraInformations('$idR', '$dateCell', event); return false;\"" : '';
                  echo "<div  class='$idcolorPlanDetailDiv' id='colorPlanDetail' $varOnclickOnContextMenu style='cursor:pointer;position:relative;height:" . $height . "px; background-color:" . $projectsColor[$idP] . ";'></div>";
                  $adjustedHeight = $trHeight - $height;
                  if ($adjustedHeight  != 0 and !$real and $refTypeCell!=''){
                    echo "<div  class='$idcolorPlanDetailDiv' id='colorPlanDetail' $varOnclickOnContextMenu style='cursor:pointer;position:relative;height:" . $adjustedHeight . "px;'></div>";
                  }
                }
              }
            }
          }
  	      
  	      if ($real) {
  	        echo "<div style='user-select:none;pointer-events:none;position:absolute;top:3px;left:5px;color:#000000;'>R</div>";
  	        echo "<div style='user-select:none;pointer-events:none;position:absolute;top:2px;left:6px;color:#FFFFFF;'>R</div>";
  	      }
  	      
  	      echo "</div>";
  	    }
  	  }
	    echo '</td>';
	  }
	  echo '</tr>';
  }
}
echo '</table>';
echo '</td></tr></table>';
echo '<br/><br/>';
if($outMode !="pdf"){
  echo "<div id='colorPlanDetailDiv' style='z-index:998;display:none; position:fixed; background-color:#FFFFFF; padding:7px; xpadding-top:10px; border:1px solid var(--color-medium); border-radius: 5px 0px 5px 5px; width:600px; max-height:140px; overflow-x:hidden; overflow-y:auto;'></div>";
  echo "<div id='colorPlanClose' onclick='closeColorPlanDetails();' style='z-index:999;display:none; position:fixed; background-color:#FFFFFF; border:1px solid var(--color-medium); border-bottom:0;width:25px; height:20px; border-radius:5px 5px 0px 0px; justify-content: center; align-items: center;'> <div class='iconClose iconSize16 pointer'></div></div>";
}
// END OF LOOP ON MONTH
}
end:
