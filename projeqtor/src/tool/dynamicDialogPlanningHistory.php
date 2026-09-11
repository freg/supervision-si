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

include_once '../tool/formatter.php';
  $user=getSessionUser();
  $order="date DESC";
  $PlHist = new PlanningHistory();
  $prjVisLst=$user->getVisibleProjects();
  $likeConditions = [];
  if (!empty($prjVisLst)){
    foreach ($prjVisLst as $idProject=>$name) {
      $likeConditions[] = "CONCAT('#', projects, '#') LIKE '%#" . intval($idProject) . "#%'";
    }
    $crit = implode(' OR ', $likeConditions);
    $crit .=' OR projects is null';
    $plHistoryList = $PlHist->getSqlElementsFromCriteria(null,false, $crit, $order,null, null, 15);
  }else {
    $plHistoryList = [];
  }
  echo '<div style="width: 1100px;">';
    echo '<table style="width:100%;margin-right:10px;position:relative;">';
      echo '<tr>';
        echo '<td class="historyHeader" style="width:15%">'.i18n('colName').'</td>';
        echo '<td class="historyHeader" style="width:10%">'.i18n('colDate').'</td>';
        echo '<td class="historyHeader" style="width:15%">'.i18n('Project').'</td>';
        echo '<td class="historyHeader" style="width:10%">'.i18n('colDuration').'</td>';
        echo '<td class="historyHeader" style="width:15%">'.i18n('colOperation').'</td>';
     echo '</tr>';
     $i=1;
     foreach ($plHistoryList as $PlHist ){
       $duration = round(($PlHist->endTime - $PlHist->startTime)*1000)/1000;
       $plHistProjId=explode('#',pq_nvl($PlHist->projects));
       $plHistProjName=array();
       foreach ($plHistProjId as $idProj){
         if (in_array($idProj, array_keys($prjVisLst))) {
           $plHistProjName[$idProj] = SqlList::getNameFromId('Project', $idProj);
         }
       }
       if (count($plHistProjName)==0 and ! $PlHist->idUser) $plHistProjName[]=i18n('allProjects');
       $plHistProjName=implode(', ',$plHistProjName);
       //$plHistProjName = pq_substr($plHistProjName,0,-1);
       $plHistProjName = rtrim($plHistProjName, ', ');
       $plHistProjDescription=$PlHist->resultDescription;
       $plHistProjResult=$PlHist->result;
       if ($PlHist->idUser==null and $PlHist->projects==null) {
         $accessRightRead=securityGetAccessRight('menuProject', 'read');
         if ($accessRightRead!="ALL") $plHistProjDescription='';
       }
     echo '<tr>';
     echo '<td class="historyData" style="width:15%">'.(($PlHist->idUser)?SqlList::getNameFromId("Affectable", $PlHist->idUser):i18n('automaticRunPlan')).'</td>';
        echo '<td class="historyData" style="width:10%">'.htmlFormatDateTime($PlHist->date).'</td>';
        echo '<td class="historyData" style="width:15%" onmouseenter="showDetailPlanningHistory(this, '. htmlEncode(json_encode($plHistProjName)) .',\''.$plHistProjResult.'\','.$i.')" onwheel="scrollDetailPlanningHistory('.$i.',this);"  onmouseleave="hideTooltip(this)"><div style=" width:650px; position:relative; text-overflow: ellipsis; overflow:hidden; white-space: nowrap;">'.$plHistProjName.'</div></td>';
        echo '<td class="historyData" style="width:10%">'.$duration.'&nbsp'.i18n('second').'</td>';
        echo '<td class="historyData" style="width:15%" onmouseenter="showDetailPlanningHistory(this, '. htmlEncode(json_encode($plHistProjDescription)).', \''.$plHistProjResult.'\','.$i.')" onwheel="scrollDetailPlanningHistory('.$i.',this);" onmouseleave="hideTooltip(this)">'.i18n('planningShortResult'.$PlHist->result).'</td>';
     echo '</tr>';
     $i++;
     }
     $i=1;
    echo '</table>';
  echo '</div>'; 
?>
