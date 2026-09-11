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

/* ============================================================================
 * List of parameter specific to a user.
 * Every user may change these parameters (for his own user only !).
 */
  require_once "../tool/projeqtor.php";
  require_once "../tool/formatter.php";
  scriptLog('   ->/view/dynamicDialogShowTickets.php');
  
  $refType=RequestHandler::getClass('refType');
  $refId=RequestHandler::getId('refId');
  $obj = new $refType($refId);
  $startAMDate = date('Y-m-d').' '.getDailyHours($obj->idProject, 'startAM', false);
  $endAMDate = date('Y-m-d').' '.getDailyHours($obj->idProject, 'endAM', false);
  $startPMDate = date('Y-m-d').' '.getDailyHours($obj->idProject, 'startPM', false);
  $endPMDate = date('Y-m-d').' '.getDailyHours($obj->idProject, 'endPM', false);
  $hourPerDay = abs(pq_strtotime($startAMDate)-pq_strtotime($endAMDate))+abs(pq_strtotime($startPMDate)-pq_strtotime($endPMDate));
  $list=array();
  $stPeriod = new StatusPeriod();
  $list=$stPeriod->getSqlElementsFromCriteria(array('refType'=>$refType, 'refId'=>$refId));
  echo '<div style="height:90%;max-height:90%;overflow:auto;">';
  echo '<table style="width:100%;text-align:center">';
  echo '<tr>';
  echo '<td class="linkHeader" style="width:10%" rowspan="2">' . i18n('colMacroStatus') . '</td>';
  echo '<td class="linkHeader" style="width:30%" colspan="3">'.i18n('startPeriod').'</td>';
  echo '<td class="linkHeader" style="width:30%" colspan="3">'.i18n('endPeriod').'</td>';
  echo '<td class="linkHeader" style="width:30%" colspan="2">'.i18n('colDuration').'</td>';
  echo '</tr><tr>';
  echo '<td class="linkHeader">' . i18n('colDate') . '</td>';
  echo '<td class="linkHeader">' . i18n('colIdStatus') . '</td>';
  echo '<td class="linkHeader">' . i18n('colIdUser') . '</td>';
  echo '<td class="linkHeader">' . i18n('colDate') . '</td>';
  echo '<td class="linkHeader">' . i18n('colIdStatus') . '</td>';
  echo '<td class="linkHeader" >' . i18n('colIdUser') . '</td>';
  echo '<td class="linkHeader">' . i18n('colCalendar') . '</td>';
  echo '<td class="linkHeader">' . i18n('openDays') . '</td>';
  echo '</tr>';
  foreach ( $list as $statusPeriod ) {
    echo '<tr>';
    echo '<td class="linkData" style="white-space:nowrap;width:10%">';
    $class = ($statusPeriod->active)?'Submitted':'Unsubmitted';
    echo '<table><tr><td style="float:left">'.formatIcon($class, 16, null, false, true).'</td><td style="padding-left:10px">'.i18n('col'.pq_ucfirst($statusPeriod->type)).'</td></tr></table></td>';
    echo '<td class="linkData" style="white-space:nowrap;width:15%">'.htmlFormatDateTime($statusPeriod->startDate).'</td>';
    $objStatus=new Status($statusPeriod->idStatusStart);
    echo '<td class="dependencyData colorNameData"  style="width:10%">' . colorNameFormatter($objStatus->name . "#split#" . $objStatus->color) . '</td>';
    $objStatus=new Status($statusPeriod->idStatusEnd);
    $userName = SqlList::getNameFromId('User', $statusPeriod->idUserStart);
    echo '<td class="linkData" style="white-space:nowrap;width:10%">';
    echo '<table><tr><td style="float:left">'.formatUserThumb($statusPeriod->idUserStart, $userName, 'Creator').'</td><td style="width:50px">'.$userName.'</td></tr></table></td>';
    echo '<td class="linkData" style="white-space:nowrap;width:15%">'.htmlFormatDateTime($statusPeriod->endDate).'</td>';
    echo '<td class="dependencyData colorNameData"  style="width:10%">' . colorNameFormatter($objStatus->name . "#split#" . $objStatus->color) . '</td>';
    $userName = SqlList::getNameFromId('User', $statusPeriod->idUserEnd);
    echo '<td class="linkData" style="white-space:nowrap;width:10%">';
    echo '<table><tr><td style="float:left">'.formatUserThumb($statusPeriod->idUserEnd, $userName, 'Creator').'</td><td style="width:50px">'.$userName.'</td></tr></table></td>';
    $duration = $statusPeriod->duration;
    $durationDisplay = "";
    if($duration){
    	$startDate = new DateTime(date("Y-m-d H:i:s"));
    	$endDate = new DateTime(date("Y-m-d H:i:s", pq_strtotime("+$duration seconds")));
    	$durationDiff = date_diff($startDate, $endDate, true);
    	if($durationDiff->y){
    		$durationDisplay .= $durationDiff->format('%y').i18n('shortYear').' ';
    	}
    	if($durationDiff->m){
    		$durationDisplay .= $durationDiff->format('%m').i18n('shortMonth').' ';
    	}
    	if($duration >=86400){
    		$durationDisplay .= $durationDiff->format('%d').i18n('shortDay').' ';
    	}
    	if($duration >=3600){
    		$durationDisplay .= $durationDiff->format('%h').i18n('shortHour').' ';
    	}
    	if($duration >=60){
    		$durationDisplay .= $durationDiff->format('%i').i18n('shortMinute').' ';
    	}
    }
    if(!$durationDisplay and $statusPeriod->duration)$durationDisplay='0'.i18n('shortMinute');
    echo '<td class="linkData" style="white-space:nowrap;width:10%">'.$durationDisplay.'</td>';
    $duration = $statusPeriod->durationOpenTime;
    if($duration>=$hourPerDay){
      $duration = $duration/3600;
      $durationDay = (($duration - fmod($duration,1))/($hourPerDay/3600))*86400;
      $durationHour = fmod($duration,1)*3600;
      if(fmod(($durationDay/86400), 1) > 0){
        $hoursDay = fmod(($durationDay/86400), 1)*86400;
      	$durationDay = $durationDay - $hoursDay;
      	$durationHour = $durationHour + $hoursDay;
      }
      $duration = $durationDay+$durationHour;
    }
    $durationDisplay = "";
    if($duration){
    	$startDate = new DateTime(date("Y-m-d H:i:s"));
    	$endDate = new DateTime(date("Y-m-d H:i:s", pq_strtotime("+$duration seconds")));
    	$durationDiff = date_diff($startDate, $endDate, true);
    	
    	if($durationDiff->y){
    		$durationDisplay .= $durationDiff->format('%y').i18n('shortYear').' ';
    	}
    	if($durationDiff->m){
    		$durationDisplay .= $durationDiff->format('%m').i18n('shortMonth').' ';
    	}
        if($duration >=86400){
    		$durationDisplay .= $durationDiff->format('%d').i18n('shortDay').' ';
    	}
    	if($duration >=3600){
    	    if($durationDiff->format('%h')>($hourPerDay/3600)){
    	      $hour = round(($durationDiff->format('%h')*($hourPerDay/3600))/24);
    	    }else{
    	      $hour = $durationDiff->format('%h');
    	    }
    		$durationDisplay .= $hour.i18n('shortHour').' ';
    	}
    	if($duration >=60){
    		$durationDisplay .= $durationDiff->format('%i').i18n('shortMinute').' ';
    	}
    }
    if(!$durationDisplay and $statusPeriod->duration)$durationDisplay='0'.i18n('shortMinute');
    echo '<td class="linkData" style="white-space:nowrap;width:10%">'.$durationDisplay.'</td>';
    echo '</tr>';
  }
  echo '</table>';
  echo '</div>';
  echo '<br/>';
  echo '<div align="center"><button dojoType="dijit.form.Button" type="button" onclick="dijit.byId(\'dialogStatusPeriod\').hide();">'.i18n("close").'</button></div>';
  echo '<div align="right" style="position: absolute;right: 12px;bottom: 10px;width: 199px;text-align: right;font-size: 11px;color: #BABABA;">';
  echo '<table style="width:100%"><tr><td></td><td>'.i18n('colStart').'</td><td>'.i18n('colEnd').'</td></tr>';
  echo '<tr><td>'.i18n('colMorning').'</td><td>'.getDailyHours($obj->idProject, 'startAM', false).'</td>';
  echo '<td>'.getDailyHours($obj->idProject, 'endAM', false).'</td><tr>';
  echo '<tr><td>'.i18n('colAfternoon').'</td><td>'.getDailyHours($obj->idProject, 'startPM', false).'</td>';
  echo '<td>'.getDailyHours($obj->idProject, 'endPM', false).'</td><tr>';
  echo '</table></div>';
  ?>