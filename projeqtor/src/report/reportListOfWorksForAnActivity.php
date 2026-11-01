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

$paramProject = RequestHandler::getId('idProject');
$paramActivity = RequestHandler::getId('idActivity');

// Header
$headerParameters="";
if ($paramProject!="") {
  $headerParameters.= i18n("colIdProject") . ' : ' . htmlEncode(SqlList::getNameFromId('Project', $paramProject)) . '<br/>';
  if ($paramActivity != null) $headerParameters.= i18n("colIdActivity") . ' : ' . htmlEncode(SqlList::getNameFromId('Activity', $paramActivity)) . '<br/>';
}  
include "header.php";

if ($paramActivity != null){
  $activity = new Activity($paramActivity);
}else{
  $activity = new Activity();
  $listActivities = $activity->getSqlElementsFromCriteria(array('idProject'=>$paramProject));
}


$allProjectIds = getAllProjectIds($paramProject);

$work = new Work();
$where = "idProject IN (" . implode(',', $allProjectIds) . ") and refType='Activity'";
if ($paramActivity != null) $where .= " and refId=$paramActivity";
$listWork = $work->getSqlElementsFromCriteria(null, false ,$where);

if (!empty($listWork)) {
  $workIds = array_map(function($work) {
    return $work->id;
  }, $listWork);
  $workDetail = new WorkDetail();
  $whereDetail = "idWork IN (" . implode(',', $workIds) . ")";
  $listWorkDetail = $workDetail->getSqlElementsFromCriteria(null, false, $whereDetail);
}else{
  $listWorkDetail =[];
}
$result = $listWorkDetail;
if (checkNoData($result)) exit;


$activities = [];

foreach ($listWorkDetail as $workDetail) {
    $workCategory = new WorkCategory($workDetail->idWorkCategory);
    $workName = $workCategory->name;
    $activityName = '';
    foreach ($listWork as $work) {
        if ($work->id == $workDetail->idWork) {
            $activity = new Activity($work->refId);
            $activityName = $activity->name;
            break;
        }
    }
    if (!isset($activities[$activityName])) {
        $activities[$activityName] = [
            'activity' => $activityName,
            'works' => []
        ];
    }
    if (!isset($activities[$activityName]['works'][$workName])) {
        $activities[$activityName]['works'][$workName] = [
            'name' => $workName,
            'uncertainties' => [],
            'progress' => [],
            'totalWork' => 0
        ];
    }
    $activities[$activityName]['works'][$workName]['totalWork'] += $workDetail->work;
    if (!empty($workDetail->uncertainties)) {
        $activities[$activityName]['works'][$workName]['uncertainties'] = array_merge(
            $activities[$activityName]['works'][$workName]['uncertainties'],
            explode(", ", $workDetail->uncertainties)
        );
    }
    if (!empty($workDetail->progress)) {
        $activities[$activityName]['works'][$workName]['progress'] = array_merge(
            $activities[$activityName]['works'][$workName]['progress'],
            explode(", ", $workDetail->progress)
        );
    }
}

echo '<table  width="75%" align="center">';
echo '<tr>';
echo ' <td class="reportTableHeader" style="width:15%;">' . i18n('sectionActivity') . '</td>';
echo ' <td class="reportTableHeader" style="width:15%;">' . i18n('colWorks') . '</td>';
echo ' <td class="reportTableHeader" style="width:10%;">' . ucfirst(i18n('colWork')) . '</td>';
echo ' <td class="reportTableHeader" style="width:20%;">' . i18n('colUncertainties') . '</td>';
echo ' <td class="reportTableHeader" style="width:20%;">' . i18n('colProgressImputation') . '</td>';
echo '</tr>';

$style = "padding:4px;padding-left:10px;text-align:left;vertical-align:top;";

foreach ($activities as $activityName => $activity) {
  $activityRowCount = 0;
  foreach ($activity['works'] as $work) {
    $activityRowCount += 1; 
  }    
  $firstActivityRow = true; 

  foreach ($activity['works'] as $work) {
  echo '<tr>';      
  
  if ($firstActivityRow) {
    echo ' <td style="text-align:center;vertical-align:center;" rowspan='. $activityRowCount .' class="reportTableData" >'. $activity['activity']. '</td>';
    $firstActivityRow = false; 
  }
  
  echo ' <td style='.$style.' class="reportTableData" >'. $work['name'] .'</td>';
  echo ' <td style="text-align:center;vertical-align:center;" class="reportTableData" >'. Work::displayImputationWithUnit($work['totalWork']). ' </td>';
  echo ' <td style='.$style.' class="reportTableData" >'. (!empty($work['uncertainties']) ? implode('<br>', $work['uncertainties']) : '') .'</td>';
  echo ' <td style='.$style.' class="reportTableData" >'. (!empty($work['progress']) ? implode('<br>', $work['progress']) : '') .'</td>';
  echo '</tr>';
  }
}
echo "</table>";



function getAllProjectIds($parentId) {
  $ids = array($parentId);
  $project = new Project();
  $subProjects = $project->getSqlElementsFromCriteria(null, false, "idProject=$parentId");

  foreach ($subProjects as $subProject) {
    $ids = array_merge($ids, getAllProjectIds($subProject->id));
  }
  return $ids;
}

?>
