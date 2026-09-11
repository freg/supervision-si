<?php 
use PhpOffice\PhpPresentation\Slide\AbstractBackground;

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
 * Presents an object. 
 */
  require_once "../tool/projeqtor.php";
  require_once "../tool/formatter.php";
  scriptLog('   ->/view/diary.php');   

  if (! isset($destinationHeight)) {
    $destinationHeight=$_REQUEST['destinationHeight'];
  }
  if (! isset($destinationWidth)) {
    $destinationWidth=$_REQUEST['destinationWidth'];
  }
  
  $cpt=0;
  $arrayActivities=array(); // Array of activities to display
  $idRessource=getSessionUser()->id;
  $showDone=false;
  $showIdle=false;
  $selectedTypes=Parameter::getUserParameter('diarySelectedItems');
  if (! isset($period)) {
  	$period=pq_htmlentities($_REQUEST['diaryPeriod']);
    $year=pq_htmlentities($_REQUEST['diaryYear']);
    $month=pq_htmlentities($_REQUEST['diaryMonth']);
    $week=pq_htmlentities($_REQUEST['diaryWeek']);
    $day=pq_htmlentities($_REQUEST['diaryDay']);
    Parameter::storeUserParameter("diaryPeriod",$period);
    $idRessource=$_REQUEST['diaryResource'];
    $selectedTypes=$_REQUEST['diarySelectItems'];
    $showIdle=(isset($_REQUEST['showIdle']))?true:false;
    $showDone=(isset($_REQUEST['showDone']))?true:false;
  }
  
  if ($selectedTypes=='' or $selectedTypes=='none') $selectedTypes='All';
  
  if(sessionValueExists('diaryResource')) {
    $idRessource = getSessionValue('diaryResource');
  }
  if(sessionValueExists('showIdleDiary')) {
    if(getSessionValue('showIdleDiary')=='on'){
      $showIdle = true;
    }else{
      $showIdle = false;
    }
  }
  if(sessionValueExists('showDoneDiary')) {
    if(getSessionValue('showDoneDiary')=='on'){
      $showDone = true;
    }else{
      $showDone = false;
    }
  }
//   if(sessionValueExists('dateSelectorDiary')) {
//     $day = getSessionValue('dateSelectorDiary');
//     $year= date('Y',pq_strtotime($day));
//     $month= date('m',pq_strtotime($day));
//     $week= date('W',pq_strtotime($day));
//     if ($period=='week') {
//       if ($week>50 and $month==1) {
//         $year--;
//       } else if ($week==1 and $month==12) {
//         $year++;
//       }
//     }
//   }

  
  $ress=new Resource($idRessource);
  $calendar=$ress->idCalendarDefinition;
  $weekDaysCaption=array(
  		1=>i18n("Monday"),
  		2=>i18n("Tuesday"),
  		3=>i18n("Wednesday"),
  		4=>i18n("Thursday"),
  		5=>i18n("Friday"),
  		6=>i18n("Saturday"),
  		7=>i18n("Sunday"),
  );
  
  $holyday = new CalendarBankOffDays();
  $holydayList = $holyday->getSqlElementsFromCriteria(array('idCalendarDefinition'=>$calendar));
  $holydays = array();
  foreach ($holydayList as $holyday){
    $hDay = ($holyday->day <= 9)?'0'.$holyday->day:$holyday->day;
    $hMonth = ($holyday->month <= 9)?'0'.$holyday->month:$holyday->month;
    $hDate = $year.'-'.$hMonth.'-'.$hDay;
    $holydays[$hDate]=$holyday->name;
  }
  
  $projectColorArray=array();
  $projectNameArray=array();
  $totalHeight=$destinationHeight;
  $trHeight=$totalHeight;
  if ($period=="month") {
  	$firstDay=$year.'-'.$month.'-01';
  	$lastDayOfMonth=date('t',pq_strtotime($year.'-'.$month.'-01'));
    $week=weekNumber($firstDay);
  	$lastWeek=weekNumber($year.'-'.$month.'-'.$lastDayOfMonth);
  	//$lastWeek=weekNumber('2017-04-30');
  	if ($lastWeek==1) {
  	  while ($lastWeek==1) {
    	  $lastDayOfMonth--;
    	  $lastWeek=weekNumber($year.'-'.$month.'-'.$lastDayOfMonth);
  	  }
  	  $lastWeek+=1;
  	}
	  if ($lastWeek>$week) {
		  $trHeight=floor(($totalHeight-20)/($lastWeek-$week+1));
	  } else {
		  $trHeight=floor(($totalHeight-20)/($lastWeek+1));
	  }
  } else if ($period=="week") {
    $trHeight=$totalHeight-10;
  } else if ($period=="day") {
    $trHeight=$totalHeight;
  }
  if ($period=="month") {
    if ($month=='01' and $week>50) {
      $currentDay=date('Y-m-d',firstDayofWeek($week,$year-1));
    } else {
  	  $currentDay=date('Y-m-d',firstDayofWeek($week,$year));
    }
  	$lastDayOfMonth=date('t',pq_strtotime($year.'-'.$month.'-01'));
	  //$weekOfLastDayOfMonth=date('W',pq_strtotime($year.'-'.$month.'-'.$lastDayOfMonth));
  	$weekOfLastDayOfMonth=$lastWeek;
  	$firstDayOfLastWeek=date('Y-m-d',firstDayofWeek($weekOfLastDayOfMonth, $year ));
  	$endDay=addDaysToDate($firstDayOfLastWeek, 6);
  	$inScopeDay=false;	
  } else if ($period=="week") {
  	$currentDay=date('Y-m-d',firstDayofWeek($week,$year));
  	$endDay=addDaysToDate($currentDay, 6);
  	$inScopeDay=true;
  } else if ($period=="day") {
  	$currentDay=$day;
  	$endDay=$currentDay;
  	$inScopeDay=true;
  }

  echo '<TABLE style="width:100%;height:100%">';
  
  $showDayOff = Parameter::getUserParameter("showDayOffDiary");
  $showDayOff = ($showDayOff=='on' or $showDayOff=='1' or $showDayOff=="")?true:false;
    
  $cal = new CalendarDefinition($ress->idCalendarDefinition);
  $nbOffDays = 7;
  $offDays = array();
  if (Parameter::getGlobalParameter('OpenDayMonday')=='offDays' or $cal->dayOfWeek1){
    $offDays[0]=1;
    if(!$showDayOff)$nbOffDays--;
  }else{
    $offDays[0]=0;
  }
  if (Parameter::getGlobalParameter('OpenDayTuesday')=='offDays' or $cal->dayOfWeek2){
    $offDays[1]=1;
    if(!$showDayOff)$nbOffDays--;
  }else{
    $offDays[1]=0;
  }
  if (Parameter::getGlobalParameter('OpenDayWednesday')=='offDays' or $cal->dayOfWeek3){
    $offDays[2]=1;
    if(!$showDayOff)$nbOffDays--;
  }else{
    $offDays[2]=0;
  }
  if (Parameter::getGlobalParameter('OpenDayThursday')=='offDays' or $cal->dayOfWeek4){
    $offDays[3]=1;
    if(!$showDayOff)$nbOffDays--;
  }else{
    $offDays[3]=0;
  }
  if (Parameter::getGlobalParameter('OpenDayFriday')=='offDays' or $cal->dayOfWeek5){
    $offDays[4]=1;
    if(!$showDayOff)$nbOffDays--;
  }else{
    $offDays[4]=0;
  }
  if (Parameter::getGlobalParameter('OpenDaySaturday')=='offDays' or $cal->dayOfWeek6){
    $offDays[5]=1;
    if(!$showDayOff)$nbOffDays--;
  }else{
    $offDays[5]=0;
  }
  if (Parameter::getGlobalParameter('OpenDaySunday')=='offDays' or $cal->dayOfWeek0){
    $offDays[6]=1;
    if(!$showDayOff)$nbOffDays--;
  }else{
    $offDays[6]=0;
  }
  $colTDWidth = ($period == 'month')?1:3;
  $colHeaderWidth = ($period != 'day')?(100-$colTDWidth)/$nbOffDays:(100-$colTDWidth)/2;
  $colHeaderWidth = $destinationWidth * ($colHeaderWidth/100);
  
  if ($period!='day') {
    echo '<tr height="16px">';
    echo '<td style="width:'.$colTDWidth.'%"></td>';
    for ($i=0; $i<7;$i++) {
      if(!$showDayOff and $offDays[$i])continue;
      $day = date('Y-m-d', firstDayofWeek($week, $year));
      $date = pq_strtotime(addDaysToDate($day, $i));
  	  echo '<td class="diaryWeekHeader" style="width: '.$colHeaderWidth.'px;height:15px;padding:5px 0px;">'.i18n(date('D', $date)).'</td>';
    }
  } else {
  	echo '<tr height="16px">';
  	echo '<td style="width:'.$colTDWidth.'%"></td>';
//   	$trHeight=$totalHeight;
  }
  $arrayActivities=getAllActivities($currentDay, $endDay, $idRessource, $selectedTypes, $showDone,$showIdle, $nbOffDays);
  drawDiaryLineHeader($currentDay, $trHeight,$period);
  $countDay = 0; 
  while ($currentDay<=$endDay) {
    $day = date('N', pq_strtotime($currentDay))-1;
    if(!$showDayOff and $offDays[$day]){
      //skip to next day
    }else{
      if ($period=="month") {
        if (pq_substr($currentDay,5,2)==$month) {
          $inScopeDay=true;
        } else {
          $inScopeDay=false;
        }
      }
      $bgColor="#FFFFFF";
      if (isOffDay($currentDay,$calendar)) {
        $bgColor="#dfdfdf";
      }
      $border = "border: 1px solid #AAAAAA;";
      if($period == 'week')$border = "border-left: 1px solid #AAAAAA;border-right: 1px solid #AAAAAA;border-top: 1px solid #AAAAAA;";
      //   	if (date('Y-m-d')==$currentDay) {
      //   	  $border="border: 3px solid var(--color-medium-secondary);";
      //   	}
      if($period=='month'){
        echo '<td class="diaryDayTD" style="width: '.(($period=='day')?'100%;':$colHeaderWidth.'px;').$border.'background-color:white">';
        echo '<table style="width:100%; height:100%;">';
        if ($period!='day') {
          echo '<tr style="height:16px">';
          echo '<td class="'.(($currentDay==date('Y-m-d'))?'diaryTodayHeader':'diaryDayHeader').'" style="padding:0;cursor: pointer;background-color:'.$bgColor.';"';
          $year = date('Y', pq_strtotime($currentDay));
          $month = date('m', pq_strtotime($currentDay));
          echo ' onClick="diaryDay(\''.$currentDay.'\');" ><div class="" oncontextmenu="if(event.target === this) { openDiaryContextMenu(null, null, '.$idRessource.', \''.$currentDay.'\', null, null); return false; }">';
          echo pq_substr($currentDay,8,2);
          echo '</div></td>';
          echo '</tr>';
        }
        $height='';
        if(isFF()){
          $trHeight = ($period=='month')?($destinationHeight/6)-5:$destinationHeight-65;
          $height = 'style="height:'.$trHeight.'px"';
        }else if($period=='month'){
          $trHeight = 98;
          $height = 'style="height:'.$trHeight.'%"';
        }
        echo '<tr '.$height.'>';
        echo ' <td style="'.((isFF())?'':'padding: 3px 0px;').'background-color:'.$bgColor.';">';
        drawDiaryItem($currentDay,$idRessource,$inScopeDay,$period,$colHeaderWidth,$calendar);
        if($period=='month')echo ' </td>';
        echo '</tr>';
        echo '</table>';
      }else{
        echo '<td style="width: '.(($period=='day')?'100%;':$colHeaderWidth.'px;').$border.'background-color:'.$bgColor.'">';
        drawDiaryItem($currentDay,$idRessource,$inScopeDay,$period,$colHeaderWidth,$calendar);
      }
    }
    $currentDay=addDaysToDate($currentDay, 1);
    if ($currentDay<=$endDay and date('N', pq_strtotime($currentDay))==1) {
      drawDiaryLineHeader($currentDay, $trHeight,$period);
    }
  }
  echo '</tr></TABLE>';
  
  function drawDiaryItem($date,$ress,$inScopeDay,$period,$itemRawWidth,$calendar=1) {
    global $cpt, $trHeight, $currentDay, $destinationWidth, $destinationHeight, $holydays;
    
    $seeWork=Parameter::getUserParameter("diarySeeWork".Parameter::getUserParameter("diaryIdKanban"));
    $seeWork=($seeWork=='on' or $seeWork=='1')?true:false;
    if($seeWork && PlanningElement::getWorkVisibiliy(getSessionUser()->idProfile)=="ALL")$seeWork=true; else $seeWork=false;
    
    // Récupération des paramètres d'affichage
    $hideStatus = Parameter::getUserParameter("diaryHideStatus");
    $hideStatus = ($hideStatus=='on' or $hideStatus=='')?true:false;
//     $hideProduct = Parameter::getUserParameter("diaryHideProduct");
//     $hideProduct = ($hideProduct=='on' or $hideProduct=='')?true:false;
//     $hideActivityPlanning = Parameter::getUserParameter("diaryHideActivityPlanning");
//     $hideActivityPlanning = ($hideActivityPlanning=='on' or $hideActivityPlanning=='')?true:false;
    $hideResponsible = Parameter::getUserParameter("diaryHideResponsible");
    $hideResponsible = ($hideResponsible=='on' or $hideResponsible=='')?true:false;
    $hidePriority = Parameter::getUserParameter("diaryHidePriority");
    $hidePriority = ($hidePriority=='on' or $hidePriority=='')?true:false;
    $hideCriticality = Parameter::getUserParameter("diaryHideCriticality");
    $hideCriticality = ($hideCriticality=='on' or $hideCriticality=='')?true:false;
    $hidePlannedDate = Parameter::getUserParameter("diaryHidePlannedDate");
    $hidePlannedDate = ($hidePlannedDate=='on' or $hidePlannedDate=='')?true:false;
    $hidedeType = Parameter::getUserParameter("diaryHideType");
    $hidedeType = ($hidedeType=='on' or $hidedeType=='')?true:false;
//     $hideProjectName = Parameter::getUserParameter("diaryHideProjectName");
//     $hideProjectName = ($hideProjectName=='on' or $hideProjectName=='')?true:false;
    $modeColorTitle = Parameter::getUserParameter( "diaryModeColorTitle");
    $modeColorTitle = (!$modeColorTitle)? 'noColor' : $modeColorTitle;
    $hideColorTitle = Parameter::getUserParameter("diaryHideColorTitle");
    $hideColorTitle = ($hideColorTitle=='on')?true:false;
    
    $showDayOff = Parameter::getUserParameter("showDayOffDiary");
    $showDayOff = ($showDayOff=='on' or $showDayOff=='1' or $showDayOff=="")?true:false;
    
    $showPlannedWorkPool = Parameter::getUserParameter("showPlannedWorkPoolDiary");
    $showPlannedWorkPool = ($showPlannedWorkPool=='on' or $showPlannedWorkPool=='1' or $showPlannedWorkPool=="")?true:false;
    
    $showActivitiesPlannedEndDate = Parameter::getUserParameter("showActivitiesPlannedEndDateDiary");
    $showActivitiesPlannedEndDate = ($showActivitiesPlannedEndDate=='on' or $showActivitiesPlannedEndDate=='1' or $showActivitiesPlannedEndDate=="")?true:false;
    
    $resource = new Resource($ress, true);
    $cal = new CalendarDefinition($resource->idCalendarDefinition);
    $nbDays = 7;
    if(!$showDayOff){
      if (Parameter::getGlobalParameter('OpenDaySunday')=='offDays' or $cal->dayOfWeek0)$nbDays--;
      if (Parameter::getGlobalParameter('OpenDayMonday')=='offDays' or $cal->dayOfWeek1)$nbDays--;
      if (Parameter::getGlobalParameter('OpenDayTuesday')=='offDays' or $cal->dayOfWeek2)$nbDays--;
      if (Parameter::getGlobalParameter('OpenDayWednesday')=='offDays' or $cal->dayOfWeek3)$nbDays--;
      if (Parameter::getGlobalParameter('OpenDayThursday')=='offDays' or $cal->dayOfWeek4)$nbDays--;
      if (Parameter::getGlobalParameter('OpenDayFriday')=='offDays' or $cal->dayOfWeek5)$nbDays--;
      if (Parameter::getGlobalParameter('OpenDaySaturday')=='offDays' or $cal->dayOfWeek6)$nbDays--;
    }
    
    $noneAssignableItems=array('Action','Delivery','Milestone');
    
    $startAM = intval(Parameter::getGlobalParameter('startAM'));
    $endPM = intval(Parameter::getGlobalParameter('endPM'));
    $totalHours = ($endPM - $startAM) + 1;
    
    $height='';
//     if(isFF()){
//       $trHeight = ($period=='month')?($destinationHeight/6)-2:$destinationHeight-65;
//       $height = 'style="height:'.$trHeight.'px;margin-bottom: -3px;"';
//     }
    $dayDivClass = (date('Y-m-d')==$currentDay)?'diaryCurrentDayDiv':'diaryItemDiv';
    $tableDayClass = ($period != 'day' and date('Y-m-d')==$currentDay)?'diaryCurrentDayTable':'';
    if($period == 'day')$dayDivClass="diaryDayDiv";
    
    $currentHolyday=(isset($holydays[$date]))?$holydays[$date]:'';
    
    // Récupération des tâches pour cette date
    $lst = getActivity($date);
    if (!$showPlannedWorkPool) {
      $lst = array_filter($lst, function($item) {
        return !(!$item['real'] && isset($item['idResourceTeam']) && $item['idResourceTeam']);
      });
    }
    
    $lst = array_filter($lst, function($item) use ($ress, $date) {
      if ($item['class'] != 'Activity') return true;
      $project = new Project($item['projectId']);
      $type = new Type($project->idProjectType);
      if ($type->code != 'ADM') return true;
      $work = new Work();
      $workList = $work->getSqlElementsFromCriteria(array('idResource' => $ress,'refId' => $item['id'],'refType'=>'Activity','workDate' => $date));
      if (count($workList) > 0) {
        foreach ($workList as $w) {
          if ($w->work > 0) return true; 
        }
      }
      return false;
    });
    
//     if (!$showActivitiesPlannedEndDate) {
//       $lst = array_filter($lst, function($item) use ($ress){
//         return !empty($item['real']) || empty($item['idAssignment']) || (!empty($item['responsibleId']) && $item['responsibleId'] == $ress);
//       });
//     }
    
    // Organiser les tâches par type
    $timedItems = array(); // Tâches avec heure précise
    $globalItems = array(); // Tâches sans heure (toute la journée)
    $numberTimedItems = array(); // Nombre de Tâches par heure
    for ($h = $startAM; $h < $endPM+1; $h++) {
      if(!isset($numberTimedItems[$h])){
        $numberTimedItems[$h]=0;
      }
    }
    
    // startAM Parser l'heure de debut de journée (param global)
    $startAMTimeStr = str_replace(['h', '.'], ':', Parameter::getGlobalParameter('startAM'));
    $startAMTimeParts = explode(':', $startAMTimeStr);
    $startAMHour = intval($startAMTimeParts[0]);
    $startAMMinute = isset($startAMTimeParts[1]) ? intval($startAMTimeParts[1]) : 0;
    $startAMHourFloat = $startAMHour + ($startAMMinute / 60);
    
    // endPM Parser l'heure de fin de journée (param global)
    $endPMTimeStr = str_replace(['h', '.'], ':', Parameter::getGlobalParameter('endPM'));
    $endPMTimeParts = explode(':', $endPMTimeStr);
    $endPMHour = intval($endPMTimeParts[0]);
    $endPMMinute = isset($endPMTimeParts[1]) ? intval($endPMTimeParts[1]) : 0;
    $endPMHourFloat = $endPMHour + ($endPMMinute / 60);
    
    // Analyser chaque tâche
    foreach ($lst as $item) {
      if (isset($item['meetingStartTime']) && $item['meetingStartTime'] != '') {
        
        // Parser l'heure de début (formats supportés: "10:30", "10h30", "10.30")
        $startTimeStr = str_replace(['h', '.'], ':', $item['meetingStartTime']);
        $startTimeParts = explode(':', $startTimeStr);
        $startHour = intval($startTimeParts[0]);
        $startMinute = isset($startTimeParts[1]) ? intval($startTimeParts[1]) : 0;
        $startHourFloat = $startHour + ($startMinute / 60);
        
        // Calculer l'heure de fin
        $endHour = $startHour + 1; // Durée par défaut 1h
        $endMinute = $startMinute;
        
        // Si on a une heure de fin spécifiée
        if (isset($item['meetingEndTime']) && $item['meetingEndTime'] != '') {
          $endTimeStr = str_replace(['h', '.'], ':', $item['meetingEndTime']);
          $endTimeParts = explode(':', $endTimeStr);
          $endHour = intval($endTimeParts[0]);
          $endMinute = isset($endTimeParts[1]) ? intval($endTimeParts[1]) : 0;
        }
        
        $endHourFloat = $endHour + ($endMinute / 60);
        
        // Limiter aux heures de travail
        $startHourFloat = max($startHourFloat, $startAMHourFloat);
        $endHourFloat = min($endHourFloat, $endPMHourFloat + 1);
        $startHour = max($startHour, $startAMHour);
        $endHour = min($endHour, $endPMHour + 1);
        $isOutOfDaytime = ((isset($item['meetingStartTime']) and $startHour != intval($item['meetingStartTime'])) or (isset($item['meetingEndTime']) and $endHour != intval($item['meetingEndTime'])))?true:false;
        
        $duration = $endHourFloat - $startHourFloat;
        if ($duration > 0) {
          $timedItems[] = array(
              'item' => $item,
              'startHour' => $startHourFloat,
              'endHour' => $endHourFloat,
              'duration' => $duration,
              'startHourInt' => $startHour,
              'endHourInt' => $endHour,
              'isOutOfDaytime'=>$isOutOfDaytime
          );
          if( $duration < 1){
            $numberTimedItems[$startHour]+=1;
          }else{
            for ($h = $startHour; $h < $endHour; $h++) {
              $numberTimedItems[$h]+=1;
            }
          }
        }
      } else {
        $globalItems[] = $item;
      }
    }
    
    // Détecter les conflits et calculer les positions en colonnes
    $columnAssignments = array(); // itemIndex => column
    $usedColumns = array(); // [startHour-endHour] => [column1, column2, ...]
    
    foreach ($timedItems as $index => $timedItem) {
      $column = 0;
      $placed = false;
      
      while (!$placed) {
        $canPlace = true;
        $startHour = $timedItem['startHourInt'];
        $endHour = ($timedItem['endHourInt'] <= $startHour)?$startHour+1:$timedItem['endHourInt'];
        // Vérifier si cette colonne est libre pour toute la durée
        for ($h = $startHour; $h < $endHour; $h++) {
          $key = $h . '-' . ($h + 1);
          if (isset($usedColumns[$key]) && in_array($column, $usedColumns[$key])) {
            $canPlace = false;
            break;
          }
        }
        
        if ($canPlace) {
          // Réserver cette colonne pour toute la durée
          for ($h = $startHour; $h < $endHour; $h++) {
            $key = $h . '-' . ($h + 1);
            if (!isset($usedColumns[$key])) {
              $usedColumns[$key] = array();
            }
            $usedColumns[$key][] = $column;
          }
          $columnAssignments[$index] = $column;
          $placed = true;
        } else {
          $column++;
        }
      }
    }
    
    // Calculer le nombre maximum de colonnes nécessaires
    $maxColumns = 0;
    foreach ($columnAssignments as $col) {
      $maxColumns = max($maxColumns, $col + 1);
    }
    $maxColumns = max(1, $maxColumns);
    
    // ===== RENDU HTML =====
    
    if($period == 'month'){
      echo '<div class="'.$dayDivClass.'" align="center" '.$height.' oncontextmenu="if(event.target === this) { openDiaryContextMenu(null, null, '.$ress.', \''.$currentDay.'\', null, null); return false; }">';
      if($currentHolyday) echo '<div class="diaryHolydayDiv"><div class="diaryHolyday">'.$currentHolyday.'</div></div>';
      
      // Pour le mois, afficher normalement
      foreach ($lst as $item) {
        echo renderDiaryItemHTML($item, $cpt++, $itemRawWidth, $period, $hideColorTitle, $hidedeType, $hideStatus,
            $hideResponsible, $hidePriority, null, null,
            $seeWork, $ress, $currentDay, $noneAssignableItems);
      }
      if(count($lst) <= 0)echo renderAddButtonDiaryItemHTML($currentDay, $date, $ress);
      
      echo '</div>';
      
    } else {
      // Pour la semaine et le jour - créer un conteneur avec position relative
      echo '<div style="position: relative; width: 100%; height: 100%;">';
      
      if($period != 'month') echo '<table class="'.$tableDayClass.'" style="width:100%;height:100%;">';
      
      $currentDayClass = (date('Y-m-d') == $currentDay)?'diaryCurrentDayTD':'diaryDayTD';
      
      // Ligne globale (tâches sans heure)
      if($period != 'day'){
        $globalRowHeight = (count($timedItems) == 0 and $period == 'week' and count($globalItems) != 0) ? '100%' : '16.5%';
        echo '<tr class="global'.ucfirst($dayDivClass).'" style="height:'.$globalRowHeight.';">';
        //echo '<tr class="global'.ucfirst($dayDivClass).'" style="height:16.5%;">';
        echo '<td class="'.$currentDayClass.'" >';
        if ($period!='day') {
          echo '<table style="height:100%;width:100%"><tr style="height:16px">';
          echo '<td class="'.(($currentDay==date('Y-m-d'))?'diaryTodayHeader':'diaryDayHeader').'" style="padding:0;cursor: pointer;"';
          echo ' onClick="diaryDay(\''.$currentDay.'\');" ><div class="" oncontextmenu="if(event.target === this) { openDiaryContextMenu(null, null, '.$ress.', \''.$currentDay.'\', null, null); return false; }">';
          echo pq_substr($currentDay,8,2);
          echo '</div></td>';
          echo '</tr>';
          echo '<tr><td style="'.((isFF())?'':'padding: 3px 0px;').'border-bottom:1px solid #AAAAAA;">';
        }
        echo '<div class="'.$dayDivClass.'" align="center" '.$height.' oncontextmenu="if(event.target === this) { openDiaryContextMenu(null, null, '.$ress.', \''.$currentDay.'\', null, null); return false; }">';
        if($currentHolyday) echo '<div class="diaryHolydayDiv"><div class="diaryHolyday">'.$currentHolyday.'</div></div>';
        
        // Afficher les tâches globales normalement
        foreach ($globalItems as $item) {
          echo renderDiaryItemHTML($item, $cpt++, $itemRawWidth, $period, $hideColorTitle, $hidedeType, $hideStatus,
              $hideResponsible, $hidePriority, null, null,
              $seeWork, $ress, $currentDay, $noneAssignableItems);
        }
        if(count($globalItems) <= 0)echo renderAddButtonDiaryItemHTML($currentDay, $date, $ress, 'X');
        
        echo '</div>';
        if($period!='day') echo '</td></tr></table>';
        echo '</td></tr>';
      }
      
      // Lignes horaires - VIDES pour préserver la grille
      $heightHour = ($period == 'week')?83.5/$totalHours:100/$totalHours;
      if (count($timedItems) > 0 or $period != 'week' or count($globalItems) == 0) {
        for ($h = $startAM; $h <= $endPM; $h++){
          echo '<tr class="timed'.ucfirst($dayDivClass).'" style="height:'.$heightHour.'%">';
          echo '<td class="'.$currentDayClass.' '.(($period == 'day')?'timedItem':'').'" style="'.(($period == 'day' and $h == $startAM)?'width:50%;':'').'padding: 3px 0px;'.(($h == $endPM)?'':'border-bottom:1px solid #AAAAAA;').'">';
          
          // Contenu vide pour préserver la grille
          $id = ($h < $startAM)?'X':$h;
          $time = ($h < $startAM)?$startAM:$h;
          if(isset($numberTimedItems[$h]) and $numberTimedItems[$h] <= 0){
            echo '<div class="'.$dayDivClass.'" align="center" oncontextmenu="if(event.target === this) { openDiaryContextMenu(null, null, '.$ress.', \''.$currentDay.'\', \''.$time.'\', null); return false; }">';
            echo renderAddButtonDiaryItemHTML($currentDay, $date, $ress, $id, $time);
          }else{
            echo '<div class="'.$dayDivClass.'" align="center"';
            echo ' oncontextmenu="openDiaryContextMenu(null, null, '.$ress.', \''.$currentDay.'\', \''.$time.'\', null)">';
          }
          echo '</div>';
          
          // Gestion du jour avec colonne globale
          if($period == 'day' and $h == $startAM){
            echo '</td><td class="'.$currentDayClass.' globalItem" rowspan="'.$totalHours.'" style="width:50%;padding: 3px 0px;border-left: 1px solid #AAAAAA;">';
            echo '<div class="'.$dayDivClass.'" align="center" '.$height.' oncontextmenu="if(event.target === this) { openDiaryContextMenu(null, null, '.$ress.', \''.$currentDay.'\', null, null); return false; }">';
            if($currentHolyday) echo '<div class="diaryHolydayDiv"><div class="diaryHolyday">'.$currentHolyday.'</div></div>';
            
            // Afficher les tâches globales pour le jour
            foreach ($globalItems as $item) {
              echo renderDiaryItemHTML($item, $cpt++, $itemRawWidth, $period, $hideColorTitle, $hidedeType, $hideStatus,
                  $hideResponsible, $hidePriority, null, null,
                  $seeWork, $ress, $currentDay, $noneAssignableItems);
            }
            if(count($globalItems) <= 0)echo renderAddButtonDiaryItemHTML($currentDay, $date, $ress, 'X');
            echo '</div>';
          }
          echo '</td></tr>';
        }
      }
      
      if($period != 'month') echo '</table>';
      
      
      // ===== AFFICHAGE DES TÂCHES TEMPORELLES EN OVERLAY =====
      
      // Calculer les positions absolues pour les tâches temporelles
      $tableTopOffset = ($period != 'day') ? 16.5 : 0; // Offset pour la ligne globale
      
      foreach ($timedItems as $index => $timedItem) {
        $item = $timedItem['item'];
        $column = $columnAssignments[$index];
        $isOutOfDaytime = $timedItem['isOutOfDaytime'];
        $duration = $timedItem['duration'];
        
        // Calculer la position verticale
        $startRowIndex = $timedItem['startHourInt'] - $startAM;
        $endRowIndex = $timedItem['endHourInt'] - $startAM;
        
        // Position et taille
        $topPercent = $tableTopOffset + ($startRowIndex * $heightHour);
        $heightPercent = ($endRowIndex - $startRowIndex) * $heightHour;
        
        // Ajustement fin pour les minutes
        $startMinuteOffset = (($timedItem['startHour'] - $timedItem['startHourInt']) * $heightHour);
        $endMinuteOffset = (($timedItem['endHour'] - $timedItem['endHourInt']) * $heightHour);
        
        // Trouver toutes les tâches qui se chevauchent avec celle-ci
        $overlappingTasks = array();
        foreach ($timedItems as $otherIndex => $otherTimedItem) {
          // Vérifier s'il y a chevauchement
          if ($timedItem['startHour'] < $otherTimedItem['endHour'] &&
              $timedItem['endHour'] > $otherTimedItem['startHour']) {
                $overlappingTasks[] = $otherIndex;
              }
        }
        
        // Le nombre de colonnes nécessaires = nombre de tâches qui se chevauchent
        $columnsUsedForThisSlot = count($overlappingTasks);
        
        // Top et height des items en fonction de la tranche horraire
        $topPercent += $startMinuteOffset;
        $topPercent += 0.3;
        $heightPercent = $heightPercent - $startMinuteOffset + $endMinuteOffset;
        $heightPercent -= 0.6;
        
        // Position horizontale basée sur les colonnes réellement utilisées pour cette période
        $leftPercent = ($columnsUsedForThisSlot <= 1)?3:2;
        $leftPercent += ($column / $columnsUsedForThisSlot) * 98;
        $widthPercent = ($columnsUsedForThisSlot <= 1)?100:(90 / $columnsUsedForThisSlot); // Petit espacement
        
        // Ajustement pour la vue jour (colonne de gauche plus étroite)
        if ($period == 'day') {
          $leftPercent = ($leftPercent * 0.5); // 50% de la largeur totale
          $widthPercent = $widthPercent * 0.5;
        }
        
        echo '<div style="position: absolute; left: '.$leftPercent.'%; width: '.$widthPercent.'%; top: '.$topPercent.'%; height: '.$heightPercent.'%; z-index: 100; pointer-events: none;">';
        echo '  <div style="height: 100%; pointer-events: auto;">';
        
        // Déterminer si on doit utiliser le mode compact
        $useCompactMode = ($columnsUsedForThisSlot > 1);
        echo renderTimedDiaryItemHTML($item, $cpt++, $period, $hideColorTitle, $hidedeType, $hideStatus,
            $hideResponsible, $hidePriority, null, null,
            $seeWork, $ress, $currentDay, $noneAssignableItems, $duration, $useCompactMode, $isOutOfDaytime);
        echo '  </div>';
        echo '</div>';
      }
      
      echo '</div>'; // Ferme le conteneur relatif
    }
  }
  
  // Fonction pour rendre les tâches normales (sans heure)
  function renderDiaryItemHTML($item, $idItem, $itemRawWidth, $period, $hideColorTitle, $hidedeType, $hideStatus,
      $hideResponsible, $hidePriority, $hideProduct, $hideActivityPlanning,
      $seeWork, $ress, $currentDay, $noneAssignableItems) {
        
        $fullWidthElement = Parameter::getUserParameter("diaryFullWidthElement");
        $fullWidthElement = ($fullWidthElement=='on' or $fullWidthElement=='1')?true:false;
        
        $itemHeight = '';
        if($fullWidthElement){
          $h = 110;
          if($period == 'day'){
            $h = 105;
            $h = ($hideActivityPlanning)?$h+24:$h;
            $h = ($hideProduct)?$h+24:$h;
          }else if($period == 'week'){
            $h = 92;
          }
          $itemHeight = 'height:'.$h.'px;';
        }
        
        $result = '';
        $color = ($item['color'])?$item['color']:'#eeeeee';
        
        $itemWidth = $itemRawWidth * 0.90;
        $result .= '<div id="item_'.$idItem.'" class="diaryItemSmall" style="width:'.$itemWidth.'px;'.$itemHeight.'border-left: 4px solid '.$color.'"';
        $result .= ' oncontextmenu="openDiaryContextMenu(' . $item['id'] . ', \''.$item['class'].'\', '.$ress.', \''.$currentDay.'\', null, '.$item['idAssignment'].')">';
        
        if($hideColorTitle or $hidedeType or $hideStatus){
          $result .= '<div class="diaryTopItemDiv">';
          $result .= '<table style="width:100%">';
          $result .= '  <tr>';
          $result .= '    <td style="font-size:10px;font-family:arial;width:'.((($item['meetingStartTime']))?'30':'50').'%">';
          if($hideColorTitle){
            $result .= '      <div style="float:left;margin: 2px 5px 0px 2px;">'.formatColorRounded ($item['color'], 12, 3, 'left', null).'</div>';
            $result .= '      <div style="float:left;margin: 3px 4px 0px 0px;">#' . $item['id'] . '</div>';
          }
          if($hidedeType){
            $typeCode=SqlList::getFieldFromId('Type', $item['typeId'],'code');
            if (!$typeCode) $typeCode=pq_substr($item['typeName'],0,3);
            $result .= '      <div style="margin: 3px 0px 0px 5px;overflow: hidden;text-overflow: ellipsis;">'.$typeCode.'</div>';
          }
          $result .= '    </td>';
          if (($hideColorTitle or $hidedeType or $hideStatus) and $item['meetingStartTime']){
            $result .= '<td style="width:20%"><div style="text-align: center;"><b>'.$item['meetingStartTime'].'</b></div></td>';
          }
          $result .= '    <td style="width:50%">';
          if($hideStatus){
            $statusColor = SqlList::getFieldFromId('Status', $item['statusId'], 'color');
            $result .= '      <div style="margin:0px 2px 0px 5px;text-align: center;">'.formatColorRounded ($statusColor, 12  , 8, 'left', null, $item['statusName'], 7).'</div>';
          }
          $result .= '    </td>';
          $result .= '   </tr>';
          $result .= '  </table>';
          $result .= '</div>';
        }
        $result .= '<div class="diaryCenterItemDiv" style="'.(($fullWidthElement)?'height:100%;':'').'">';
        $result .= '  <div style="position:relative;margin-left:5px;">'.formatIcon($item['class'], 22,null,false).'</div>';
        $itemName = ($item['real'])?$item['name']:'<i>'.$item['name'].'</i>';
        $nameWidth  = 65;
        if(!$fullWidthElement){
          if($hideResponsible and $item['responsibleId'] and $item['responsibleName']){
            $nameWidth -= 10;
          }
          if($hidePriority and $item ['priorityId'] and $item ['priorityName']){
            $nameWidth -= 10;
          }
          if(!in_array($item['class'], $noneAssignableItems)){
            $nameWidth -= 10;
          }
        }
        if($period == 'day')$nameWidth=100;
        if($fullWidthElement)$nameWidth=100;
        $wrap=($fullWidthElement)?'style="white-space:normal;max-height:46px"':'';
        $result .= '  <div style="position:relative;margin-left:5px;width: '.$nameWidth.'%;" title="'.$item['name'].'"><div class="diaryItemNameDiv" '.$wrap.'>'.$itemName.'</div></div>';
        if ((!$hideColorTitle and !$hidedeType and !$hideStatus) and $item['meetingStartTime']){
          $result .= '<div style="position:relative;margin:0px 5px;text-align: center;font-size: 11px;"><b>'.$item['meetingStartTime'].'</b></div>';
        }
        if(!$fullWidthElement){
          $result .= '<div style="position:relative;margin:0px 5px;display:flex;align-items:center;justify-content:end;">';
          if($hideResponsible and $item['responsibleId'] and $item['responsibleName']){
            $result .= '  <div style="position:relative;margin-right:5px;" id="userThumbTicket' . $idItem . '">';
            $result .=    formatUserThumb ( $item['responsibleId'],$item['responsibleName'].'<br/><span style="font-size:80%"><i>('.i18n('colResponsible').')</i></span>', "", 20, 'left', false, $idItem, true );
            $result .= '  </div>';
          }
          if($hidePriority and $item ['priorityId'] and $item ['priorityName']){
            $result .= '<div style="position:relative;margin-right:5px;">';
            $result .= formatColorThumb ( "idPriority", $item ['priorityId'], 20, 'left', $item ['priorityName'], $idItem, true );
            $result .= '</div>';
          }
          $canCreate=(securityGetAccessRightYesNo('menu'.$item['class'],'create')=="YES")?1:0;
          $week = date('W', strtotime($currentDay));
          $year = date('Y', pq_strtotime($currentDay));
          $result .=  ' <div class="roundedButtonSmall" onclick="showDetail(null, '.$canCreate.' , \''. $item['class'] .'\', false, '. $item['id'] .');"';
          $result .=  '   title="'.i18n('kanbanEditItem', array($item['id'])).'" style="position:relative;width:18px;" >'.formatSmallButton( 'Edit').'</div>';
          if(!in_array($item['class'], $noneAssignableItems)){
            if (!$item['idAssignment'] and $item['idResourceTeam']){
              $crit = array('refType'=> $item['class'], 'refId'=>$item['id'], 'idResource'=>$item['idResourceTeam']);
              $ass = SqlElement::getFirstSqlElementFromCriteria("Assignment", $crit);
              $item['idAssignment'] = $ass->id;
            }else if (!$item['idAssignment'] and !$item['idResourceTeam']){
              $crit = array('refType'=> $item['class'], 'refId'=>$item['id']);
              $ass = SqlElement::getFirstSqlElementFromCriteria("Assignment", $crit);
              $item['idAssignment'] = $ass->id;
            }
            $result .=  ' <div class="roundedButtonSmall" onclick="diaryGotoTimesheet('.$ress.','.$year.','.$week.',\''.$currentDay.'\','.$item['idAssignment'].');"
        	                   title="'.i18n('diaryGotoTimesheet', array(i18n($item['class']), $item['id'])).'" style="position:relative;width:18px;" >' . formatSmallButton ( 'Imputation',true ) . '</div>';
          }
          $result .=  ' <div class="roundedButtonSmall" onclick="gotoElement(\''.$item['class'].'\','.$item['id'].');"
        	                 title="'.i18n('diaryGotoItem', array(i18n($item['class']), $item['id'])).'" style="position:relative;width:18px;" >' . formatSmallButton ( 'Goto',true ) . '</div>';
          $result .= '</div>';
        }
        $result .= '</div>';
        if($fullWidthElement){
          if(!in_array($item['class'], $noneAssignableItems) and $seeWork){
            $result .= '<div id="diaryWorkItemDiv" style="position: relative;">'.displayAllWork($currentDay, $item['class'], $item['id'], $ress). '</div>';
          }
          $result .= '<div class="diaryBottomItemDiv">';
          $result .= '  <div style="position:relative;display:flex;align-items: center;">';
          if($hideResponsible and $item['responsibleId'] and $item['responsibleName']){
            $result .= '  <div style="position:relative;margin-right:5px;" id="userThumbTicket' . $idItem . '">';
            $result .=      formatUserThumb ( $item['responsibleId'],$item['responsibleName'].'<br/><span style="font-size:80%"><i>('.i18n('colResponsible').')</i></span>', "", 20, 'left', false, $idItem, true );
            $result .= '  </div>';
          }
          if($hidePriority and $item ['priorityId'] and $item ['priorityName']){
            $result .= '  <div style="position:relative;margin-right:5px;">';
            $result .=      formatColorThumb ( "idPriority", $item ['priorityId'], 20, 'left', $item ['priorityName'], $idItem, true );
            $result .= '  </div>';
          }
          $result .= '</div>';
          $result .= '<div style="position:relative;display:flex;align-items: center;">';
          $canCreate=(securityGetAccessRightYesNo('menu'.$item['class'],'create')=="YES")?1:0;
          $week = date('W', strtotime($currentDay));
          $year = date('Y', pq_strtotime($currentDay));
          $result .=  ' <div class="roundedButtonSmall" onclick="showDetail(null, '.$canCreate.' , \''. $item['class'] .'\', false, '. $item['id'] .');"	title="" style="position:relative;width:18px;" >'.formatSmallButton( 'Edit').'</div>';
          if(!in_array($item['class'], $noneAssignableItems)){
            $result .=  ' <div style="position:relative;padding-left: 5px;" class="roundedButtonSmall" onclick="diaryGotoTimesheet('.$ress.','.$year.','.$week.',\''.$currentDay.'\','.$item['idAssignment'].');"
        	                  title="'.i18n('diaryGotoTimesheet', array(i18n($item['class']), $item['id'])).'" style="width:18px;" >' . formatSmallButton ( 'Imputation',true ) . '</div>';
          }
          $result .=  ' <div style="position:relative;padding-left: 5px;" class="roundedButtonSmall" onclick="gotoElement(\''.$item['class'].'\','.$item['id'].');"
        	                 title="'.i18n('diaryGotoItem', array(i18n($item['class']), $item['id'])).'" style="width:18px;" >' . formatSmallButton ( 'Goto',true ) . '</div>';
          $result .= ' </div>';
          $result .= '</div>';
        }
        
        // Tooltip pour toutes les tâches temporelles
        $hintHtml=i18n($item['class']).' #'.$item['id']."<br/>"
        .'<b>'.htmlspecialchars($item['name'])."</b><br/>"
        .i18n('colIdProject').": <i>".htmlspecialchars($item['projectName']).'</i><br/>';
        if (isset($item['meetingStartTime']) and $item['meetingStartTime']) {
          $hintHtml.=i18n('colStartTime').": <i>".$item['meetingStartTime']."</i><br/>";
        }
        if (isset($item['meetingEndTime']) and $item['meetingEndTime']) {
          $hintHtml.=i18n('colEndTime').": <i>".$item['meetingEndTime']."</i><br/>";
        }
        if ($item['date']) {
          $hintHtml.=$item['date'].": <i>".htmlFormatDate($currentDay)."</i><br/>";
        }
        if ($item['work'] and $item['real']) {
          $hintHtml.=i18n('colRealWork').": ".Work::displayWorkWithUnit($item['work'])."<br/>";
        }
        if ($item['work'] and ! $item['real']) {
          $plannedText = Work::displayWorkWithUnit($item['work']);
          if (isset($item['idResourceTeam']) && $item['idResourceTeam']) {
            $poolName = SqlList::getFieldFromId('ResourceTeam', $item['idResourceTeam'], 'name');
            if ($poolName) {
              $plannedText .= ' - '.i18n('forPool').' ' . htmlspecialchars($poolName);
            }
          }
          $hintHtml.=i18n('planned').": <i>".$plannedText."</i><br/>";
        }
        if ($item['productName']) {
          $hintHtml.=i18n('colIdVersion').": <i>".htmlspecialchars($item['productName']).'</i><br/>';
        }
        if ($item['activityPlanningName']) {
          $hintHtml.=i18n('labelKanbanHideActivityPlanning').": <i>".htmlspecialchars($item['activityPlanningName']).'</i><br/>';
        }
        
        $result .= '<div dojoType="dijit.Tooltip" connectId="item_'.$idItem.'" position="above">';
        $result .= $hintHtml;
        $result .= '</div>';
        
        $result .= '</div>';
        
        return $result;
  }
  
  // Fonction spécialisée pour rendre les tâches temporelles
  function renderTimedDiaryItemHTML($item, $idItem, $period, $hideColorTitle, $hidedeType, $hideStatus,
      $hideResponsible, $hidePriority, $hideProduct, $hideActivityPlanning,
      $seeWork, $ress, $currentDay, $noneAssignableItems, $duration, $compactMode = false, $isOutOfDaytime = false) {
        $result = '';
        $color = ($item['color'])?$item['color']:'#eeeeee';
        $startHour = (isset($item['meetingStartTime']))?intval($item['meetingStartTime']):0;
        $endHour = (isset($item['meetingEndTime']))?intval($item['meetingEndTime']):0;
        $ismultipleRow = ($endHour - $startHour > 1)?true:false;
        if($isOutOfDaytime and $duration <= 1)$ismultipleRow=false;
        if($isOutOfDaytime and $duration < 1)$compactMode=true;
        
        // Style adapté pour les tâches temporelles
        $itemStyle = 'border-left: 4px solid '.$color.'; height: 100%; overflow: hidden;margin:unset;';
        if ($compactMode) {
          $itemStyle .= ' font-size: 11px;';
        }
        $result .= '<div id="item_timed_'.$idItem.'" class="diaryItemSmall" style="'.$itemStyle.'"';//width:'.$itemWidth.'px;
        $result .= ' oncontextmenu="openDiaryContextMenu(' . $item['id'] . ', \''.$item['class'].'\', '.$ress.', \''.$currentDay.'\', \''.$startHour.'\', '.$item['idAssignment'].')">';
        
        if ($compactMode) {
          // Mode compact pour les tâches qui se chevauchent
          $result .= '<div style="padding: 2px; height: 100%; display: flex; flex-direction: column;">';
          $result .= '<div style="font-weight: bold; font-size: 10px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">';
          $result .= htmlspecialchars($item['name']);
          $result .= '</div>';
          if ($item['meetingStartTime']) {
            $result .= '<div style="font-size: 9px; color: #666; margin-top: 1px;">'.$item['meetingStartTime'].'</div>';
          }
          $result .= '</div>';
        } else {
          if($hideColorTitle or $hidedeType or $hideStatus){
            $result .= '<div class="diaryTopItemDiv">';
            $result .= '<table style="width:100%">';
            $result .= '  <tr>';
            $result .= '    <td style="font-size:10px;font-family:arial;width:'.((($item['meetingStartTime']))?'30':'50').'%">';
            if($hideColorTitle){
              $result .= '      <div style="float:left;margin: 2px 5px 0px 2px;">'.formatColorRounded ($item['color'], 12, 3, 'left', null).'</div>';
              $result .= '      <div style="float:left;margin: 3px 4px 0px 0px;">#' . $item['id'] . '</div>';
            }
            if($hidedeType){
              $typeCode=SqlList::getFieldFromId('Type', $item['typeId'],'code');
              if (!$typeCode) $typeCode=pq_substr($item['typeName'],0,3);
              $result .= '      <div style="margin: 3px 0px 0px 5px;overflow: hidden;text-overflow: ellipsis;">'.$typeCode.'</div>';
            }
            $result .= '    </td>';
            if (($hideColorTitle or $hidedeType or $hideStatus) and $item['meetingStartTime']){
              $result .= '<td style="width:20%"><div style="text-align: center;"><b>'.$item['meetingStartTime'].'</b></div></td>';
            }
            $result .= '    <td style="width:50%">';
            if($hideStatus){
              $statusColor = SqlList::getFieldFromId('Status', $item['statusId'], 'color');
              $result .= '      <div style="margin:0px 2px 0px 5px;text-align: center;">'.formatColorRounded ($statusColor, 12  , 8, 'left', null, $item['statusName'], 7).'</div>';
            }
            $result .= '    </td>';
            $result .= '   </tr>';
            $result .= '  </table>';
            $result .= '</div>';
          }
          $result .= '<div class="diaryCenterItemDiv" style="height: 100%;">';
          $result .= '  <div style="position:relative;margin-left:5px;">'.formatIcon($item['class'], 22,null,false).'</div>';
          $itemName = ($item['real'])?$item['name']:'<i>'.$item['name'].'</i>';
          $nameWidth  = 65;
          if(!$ismultipleRow){
            if($hideResponsible and $item['responsibleId'] and $item['responsibleName']){
              $nameWidth -= 10;
            }
            if($hidePriority and $item ['priorityId'] and $item ['priorityName']){
              $nameWidth -= 10;
            }
            if(!in_array($item['class'], $noneAssignableItems)){
              $nameWidth -= 10;
            }
          }
          if($period == 'day')$nameWidth=100;
          $result .= '  <div style="position:relative;margin-left:5px;width: '.$nameWidth.'%;" title="'.$item['name'].'"><div class="diaryItemNameDiv">'.$itemName.'</div></div>';
          if ((!$hideColorTitle and !$hidedeType and !$hideStatus) and $item['meetingStartTime']){
            $result .= '<div style="position:relative;margin:0px 5px;text-align: center;font-size: 11px;"><b>'.$item['meetingStartTime'].'</b></div>';
          }
          if(!$ismultipleRow){
            $result .= '<div style="position:relative;margin:0px 5px;display:flex;align-items:center;justify-content:end;">';
            if($hideResponsible and $item['responsibleId'] and $item['responsibleName']){
              $result .= '  <div style="position:relative;margin-right:5px;" id="userThumbTicket' . $idItem . '">';
              $result .=    formatUserThumb ( $item['responsibleId'],$item['responsibleName'].'<br/><span style="font-size:80%"><i>('.i18n('colResponsible').')</i></span>', "", 20, 'left', false, $idItem, true );
              $result .= '  </div>';
            }
            if($hidePriority and $item ['priorityId'] and $item ['priorityName']){
              $result .= '<div style="position:relative;margin-right:5px;">';
              $result .= formatColorThumb ( "idPriority", $item ['priorityId'], 20, 'left', $item ['priorityName'], $idItem, true );
              $result .= '</div>';
            }
            $canCreate=(securityGetAccessRightYesNo('menu'.$item['class'],'create')=="YES")?1:0;
            $week = date('W', strtotime($currentDay));
            $year = date('Y', pq_strtotime($currentDay));
            $result .=  ' <div class="roundedButtonSmall" onclick="showDetail(null, '.$canCreate.' , \''. $item['class'] .'\', false, '. $item['id'] .');"';
            $result .=  '   title="'.i18n('kanbanEditItem', array($item['id'])).'" style="position:relative;width:18px;" >'.formatSmallButton( 'Edit').'</div>';
            if(!in_array($item['class'], $noneAssignableItems)){
              $result .=  ' <div class="roundedButtonSmall" onclick="diaryGotoTimesheet('.$ress.','.$year.','.$week.',\''.$currentDay.'\','.$item['idAssignment'].');"
      	         title="'.i18n('diaryGotoTimesheet', array(i18n($item['class']), $item['id'])).'" style="position:relative;width:18px;" >' . formatSmallButton ( 'Imputation',true ) . '</div>';
            }
            $result .=  ' <div class="roundedButtonSmall" onclick="gotoElement(\''.$item['class'].'\','.$item['id'].');"
      	         title="'.i18n('diaryGotoItem', array(i18n($item['class']), $item['id'])).'" style="position:relative;width:18px;" >' . formatSmallButton ( 'Goto',true ) . '</div>';
            $result .=  ' </div>';
          }
          $result .= '</div>';
          if($ismultipleRow){
            if(!in_array($item['class'], $noneAssignableItems) and $seeWork){
              $result .= '<div id="diaryWorkItemDiv" style="position: relative;">'.displayAllWork($currentDay, $item['class'], $item['id'], $ress). '</div>';
            }
            $result .= '<div class="diaryBottomItemDiv">';
            $result .= '  <div style="position:relative;display:flex;align-items: center;">';
            if($hideResponsible and $item['responsibleId'] and $item['responsibleName']){
              $result .= '  <div style="position:relative;margin-right:5px;" id="userThumbTicket' . $idItem . '">';
              $result .=      formatUserThumb ( $item['responsibleId'],$item['responsibleName'].'<br/><span style="font-size:80%"><i>('.i18n('colResponsible').')</i></span>', "", 20, 'left', false, $idItem, true );
              $result .= '  </div>';
            }
            if($hidePriority and $item ['priorityId'] and $item ['priorityName']){
              $result .= '  <div style="position:relative;margin-right:5px;">';
              $result .=      formatColorThumb ( "idPriority", $item ['priorityId'], 20, 'left', $item ['priorityName'], $idItem, true );
              $result .= '  </div>';
            }
            $result .= '  </div>';
            $result .= '  <div style="position:relative;display:flex;align-items: center;">';
            $canCreate=(securityGetAccessRightYesNo('menu'.$item['class'],'create')=="YES")?1:0;
            $week = date('W', strtotime($currentDay));
            $year = date('Y', pq_strtotime($currentDay));
            $result .=  '  <div class="roundedButtonSmall" onclick="showDetail(null, '.$canCreate.' , \''. $item['class'] .'\', false, '. $item['id'] .');"	title="" style="position:relative;width:18px;" >'.formatSmallButton( 'Edit').'</div>';
            if(!in_array($item['class'], $noneAssignableItems)){
              $result .=  '   <div style="position:relative;padding-left: 5px;" class="roundedButtonSmall" onclick="diaryGotoTimesheet('.$ress.','.$year.','.$week.',\''.$currentDay.'\','.$item['idAssignment'].');"
        	       title="'.i18n('diaryGotoTimesheet', array(i18n($item['class']), $item['id'])).'" style="width:18px;" >' . formatSmallButton ( 'Imputation',true ) . '</div>';
            }
            $result .=  '   <div style="position:relative;padding-left: 5px;" class="roundedButtonSmall" onclick="gotoElement(\''.$item['class'].'\','.$item['id'].');"
        	         title="'.i18n('diaryGotoItem', array(i18n($item['class']), $item['id'])).'" style="width:18px;" >' . formatSmallButton ( 'Goto',true ) . '</div>';
            $result .= '  </div>';
            $result .= '</div>';
          }
        }

        // Tooltip pour toutes les tâches temporelles
        $hintHtml=i18n($item['class']).' #'.$item['id']."<br/>"
        .'<b>'.htmlspecialchars($item['name'])."</b><br/>"
        .i18n('colIdProject').": <i>".htmlspecialchars($item['projectName']).'</i><br/>';
        if (isset($item['meetingStartTime']) and $item['meetingStartTime']) {
          $hintHtml.=i18n('colStartTime').": <i>".$item['meetingStartTime']."</i><br/>";
        }
        if (isset($item['meetingEndTime']) and $item['meetingEndTime']) {
          $hintHtml.=i18n('colEndTime').": <i>".$item['meetingEndTime']."</i><br/>";
        }
        if ($item['date']) {
          $hintHtml.=$item['date'].": <i>".htmlFormatDate($currentDay)."</i><br/>";
        }
        if ($item['work'] and $item['real']) {
          $hintHtml.=i18n('colRealWork').": ".Work::displayWorkWithUnit($item['work'])."<br/>";
        }
        if ($item['work'] and ! $item['real']) {
          $plannedText = Work::displayWorkWithUnit($item['work']);
          if (isset($item['idResourceTeam']) && $item['idResourceTeam']) {
            $poolName = SqlList::getFieldFromId('ResourceTeam', $item['idResourceTeam'], 'name');
            if ($poolName) {
              $plannedText .= ' - '.i18n('forPool').' ' . htmlspecialchars($poolName);
            }
          }
          $hintHtml.=i18n('planned').": <i>".$plannedText."</i><br/>";
        }
        if ($item['productName']) {
          $hintHtml.=i18n('colIdVersion').": <i>".htmlspecialchars($item['productName']).'</i><br/>';
        }
        if ($item['activityPlanningName']) {
          $hintHtml.=i18n('labelKanbanHideActivityPlanning').": <i>".htmlspecialchars($item['activityPlanningName']).'</i><br/>';
        }
        
        $result .= '<div dojoType="dijit.Tooltip" connectId="item_timed_'.$idItem.'" position="above">';
        $result .= $hintHtml;
        $result .= '</div>';
        
        $result .= '</div>';
        
        return $result;
  }
  
  function getAmPmTimes($idProject) {
    $pro = new Project($idProject); 
    $startAM = ($pro->startAM !== null && $pro->startAM !== '') ? $pro->startAM : Parameter::getGlobalParameter('startAM');
    $endAM   = ($pro->endAM !== null && $pro->endAM !== '') ? $pro->endAM : Parameter::getGlobalParameter('endAM');
    $startPM = ($pro->startPM !== null && $pro->startPM !== '') ? $pro->startPM : Parameter::getGlobalParameter('startPM');
    $endPM   = ($pro->endPM !== null && $pro->endPM !== '')? $pro->endPM : Parameter::getGlobalParameter('endPM');
    
    return array(
      'startAM' => $startAM,'endAM' => $endAM,
       'startPM' => $startPM,'endPM' => $endPM,
    );
  }
  
    
  function renderAddButtonDiaryItemHTML($currentDay, $date, $ress, $idItemDiv='X', $time=''){
    $result = '';
    $dayAddClass = (date('Y-m-d') == $currentDay)?'diaryCurrentDayAdd':'diaryDayAdd';
    $id = ($time)?'_'.$idItemDiv:'';
    $result .= '<div id="itemAddDiv_'.$date.$id.'" class="'.$dayAddClass.'" style="" onclick="dijit.byId(\'itemAddButton_'.$date.$id.'\').openDropDown();" onmouseleave="dojo.removeClass(\'itemAddDiv_'.$date.$id.'\', \'forceDisplay\');dijit.byId(\'itemAddButton_'.$date.$id.'\').closeDropDown();"';
    $result .= 'oncontextmenu="event.preventDefault();dijit.byId(\'itemAddButton_'.$date.$id.'\').openDropDown();">';
    $result .= '  <div id="itemAddButton_'.$date.$id.'" dojoType="dijit.form.DropDownButton" showlabel="false" iconClass="iconAdd iconSize22 imageColorWhite" title="'.i18n('comboNewButton').'">';
    $result .= '    <div dojoType="dijit.TooltipDialog" class="white diaryDayAddDialog" style="width:200px;height:100%;" ';
    $result .= '      onmouseenter="dojo.addClass(\'itemAddDiv_'.$date.$id.'\', \'forceDisplay\');dijit.byId(\'itemAddButton_'.$date.$id.'\').openDropDown();" onmouseleave="dojo.removeClass(\'itemAddDiv_'.$date.$id.'\', \'forceDisplay\');dijit.byId(\'itemAddButton_'.$date.$id.'\').closeDropDown();">';
    $result .= '      <input type="hidden" id="objectClass" name="objectClass" value="" />';
    $result .= '      <input type="hidden" id="objectId" name="objectId" />';
    $result .= '      <div style="font-weight:bold; height:25px;text-align:center">'.i18n('comboNewButton').'</div>';
    $arrayItems=($idItemDiv=='X')?array('Action','Delivery','Meeting'):array('Meeting');
    foreach($arrayItems as $item) {
      $canCreate=securityGetAccessRightYesNo('menu' . $item,'create');
      if ($canCreate=='YES') {
        if (! securityCheckDisplayMenu(null,$item) ) {
          $canCreate='NO';
        }
      }
      if ($canCreate=='YES') {
        $result .= '    <div class="newGuiIconText" style="vertical-align:top;cursor:pointer;margin-top:5px;height:22px;" onClick="dijit.byId(\'itemAddButton_'.$date.$id.'\').closeDropDown();addDiaryItem(\''.$item.'\',\''.$ress.'\',\''.$date.'\', \''.$time.'\');">';
        $result .= '      <table width:"100%" >';
        $result .= '        <tr style="height:22px">';
        $result .= '          <td style="vertical-align:top; width: 30px;padding-left:5px">'.formatIconNewGui($item, 22, null, false).'</td>';
        $result .= '          <td style="vertical-align:top;padding-top:2px;">'.i18n($item).'</td>';
        $result .= '       </tr>';
        $result .= '     </table>';
        $result .= '    </div>';
      }
    }
    $result .= '    </div>';
    $result .= '  </div>';
    $result .= '</div>';
    return $result;
  }
  
  // Fonction pour obtenir les activités
  function getActivity($date) {
    global $arrayActivities;
    if (pq_array_key_exists($date, $arrayActivities)) {
      return $arrayActivities[$date];
    } else {
      return array();
    }
  }
  
  function displayAllWork($date, $class, $id, $ress) {
    $seeWork = Parameter::getUserParameter ( "diarySeeWork");
    $seeWork=($seeWork=='on' or $seeWork=='1')?true:false;
    if ($seeWork && PlanningElement::getWorkVisibility ( getSessionUser ()->idProfile ) == "ALL") {
      $seeWork = true;
    } else {
      $seeWork = false;
    }
    if (! $seeWork) {
      return '';
    }
    
    $object = new $class($id, true);
    $arrayWork = array();
    if (! isset ( $arrayWork['plannedwork'] )) {
      $arrayWork['plannedwork'] = 0;
    }
    if (! isset ( $arrayWork['realwork'] )) {
      $arrayWork['realwork'] = 0;
    }
    if (! isset ( $arrayWork['leftwork'] )) {
      $arrayWork['leftwork'] = 0;
    }
    
    $pw = new PlannedWork();
    $pwl = $pw->getSqlElementsFromCriteria(array('refType'=>$class, 'refId'=>$id, 'idResource'=>$ress, 'workDate'=>$date));
    foreach ($pwl as $wk){
      if(!isset($arrayWork['plannedwork'])){
        $arrayWork['plannedwork']=$wk->work;
      }else{
        $arrayWork['plannedwork']+=$wk->work;
      }
      if(!isset($arrayWork['leftwork'])){
        $arrayWork['leftwork']=$wk->work;
      }else{
        $arrayWork['leftwork']+=$wk->work;
      }
    }
    
    $w = new Work();
    $wl = $w->getSqlElementsFromCriteria(array('refType'=>$class, 'refId'=>$id, 'idResource'=>$ress, 'workDate'=>$date));
    foreach ($wl as $wk){
      if(!isset($arrayWork['realwork'])){
        $arrayWork['realwork']=$wk->work;
      }else{
        $arrayWork['realwork']+=$wk->work;
      }
      if(isset($arrayWork['leftwork']) and $arrayWork['leftwork'] > 0){
        $arrayWork['leftwork']-=$wk->work;
      }
    }
    $formatter = 'workFormatter';
    return '
       <table style="background-color:#dfdfdf;cursor:move;width:100%;">
         <tr>
           <td valueWork="' . pq_str_replace ( ',', '.', $arrayWork['plannedwork'] != null ? $arrayWork['plannedwork'] : 0 ) . '"
               class="" title="' . i18n ( 'colEstimated' ) . '" style="width:33%;text-align:center;padding:0px 3px 3px 3px;font-size:80%;">
               <span style="font-size:90%;color:var(--color-medium);">'.i18n ( 'colEstimated' ).'</span><br/>' . $formatter ( $arrayWork['plannedwork'] ) . '</td>
           <td valueWork="' . pq_str_replace ( ',', '.', $arrayWork['realwork'] != null ? $arrayWork['realwork'] : 0 ) . '"
               class="" title="' . i18n ( 'colReal' ) . '" style="width:33%;text-align:center;padding:0px 3px 3px 3px;font-size:80%;">
               <span style="font-size:90%;color:var(--color-medium);">'.i18n ( 'colReal' ).'</span><br/>' . $formatter ( $arrayWork['realwork'] ) . '</td>
           <td valueWork="' . pq_str_replace ( ',', '.', $arrayWork['leftwork'] != null ? $arrayWork['leftwork'] : 0 ) . '"
               class="" title="' . i18n ( 'colLeft' ) . '" style="width:33%;text-align:center;padding:0px 3px 3px 3px;font-size:80%;">
               <span style="font-size:90%;color:var(--color-medium);">'.i18n ( 'colLeft' ).'</span><br/>' . $formatter ( $arrayWork['leftwork'] ) . '</td>
         </tr>
       </table>';
  }
  
  // Fonction pour dessiner l'en-tête des lignes
  function drawDiaryLineHeader($currentDay, $trHeight, $period) {
    global $destinationHeight;
    echo '</tr>';
    $height = '';
    if (isFF()) {
      $trHeight = ($period=='month')?($destinationHeight/6)-2:$destinationHeight-65;
      $height = 'style="height:'.$trHeight.'px;"';
    } else {
      $trHeight = ($period=='month')?99/6:99;
      $height = 'style="height:'.$trHeight.'%;"';
    }
    
    echo '<tr '.$height.'>';
    if ($period=="month") {
      $week = weekNumber($currentDay);
      $weekYear = pq_substr($currentDay,0,4);
      if (intval($week)==1 and pq_substr($currentDay,5,2)==12) $weekYear+=1;
      echo '<td class="buttonDiary" onClick="diaryWeek('.$week.',\''.$currentDay.'\');" style="width:1%">';
      echo ' <div >'.weekNumber($currentDay).'</div>';
      echo ' <div class="diaryWeekSelector">'.formatIcon('Goto', 16).'</div></td>';
    } else {
      echo '<td style="width:3%;border-top:1px solid #AAAAAA;">';
      echo '  <table style="width:100%;height:100%;margin-bottom: 2px;">';
      if ($period == 'week') echo '    <tr style="height:16.5%"><td style="display: flex;height:100%;border-bottom:1px solid #AAAAAA;"></td></tr>';
      $startAM = intval(Parameter::getGlobalParameter('startAM'));
      $endPM = intval(Parameter::getGlobalParameter('endPM'));
      $heightHour = ($period == 'week')?83.5/(($endPM-$startAM)+1):100/(($endPM-$startAM)+1);
      for ($i = $startAM; $i <= $endPM; $i++){
        echo '    <tr style="height:'.$heightHour.'%"><td style="display: flex;border-bottom:1px solid #AAAAAA;text-align:center;font-size:13px;width:100%;height:100%"><div style="width:100%;">'.$i.':00</div></td></tr>';
      }
      echo '  </table>';
      echo '</td>';
    }
  }

  function getAllActivities($startDate, $endDate, $ress, $selectedTypes, $showDone=false, $showIdle=false, $nbOffDays=7) {
    global $projectColorArray, $projectNameArray, $allActi, $destinationWidth, $countListStatus;
  	$result=array();
  	$typesList=pq_explode(',', $selectedTypes);
  	
  	$hideColorTitle = Parameter::getUserParameter("diaryHideColorTitle");
  	$hideColorTitle = ($hideColorTitle=='on')?true:false;
  	$modeColorTitle = Parameter::getUserParameter( "diaryModeColorTitle");
  	$modeColorTitle = (!$hideColorTitle or !$modeColorTitle)? 'noColor' : $modeColorTitle;
  	
  	// Administrative Project
  	$adminProject = Project::getAdminitrativeProjectList();
  	// Proposale Project
  	$proposaleProject = Project::getProposaleInClauseList();
  	// Templqte Project
  	$templateProject = Project::getTemplateInClauseList();
  	// Under Construction Project
  	$underConstructionProject = Project::getUnderConstructionInClauseList();
  	
    foreach ($typesList as $typeFilter) {
      if ($typeFilter=='All') $arrObj=array(new Action(), new Ticket(), new MilestonePlanningElement(), new MeetingPlanningElement(), new Delivery());
      else if ($typeFilter=="Meeting") $arrObj=array(new MeetingPlanningElement());
      else $arrObj=array(new $typeFilter());
      if (isset($_REQUEST['countStatus']) or $countListStatus) {
        $statusWhere="IN (";
        $listStatusFilter=array();
        $countStatus=($countListStatus)?$countListStatus:$_REQUEST['countStatus'];
        for ($i=1; $i<=$countStatus; $i++) {
          if($countListStatus){
            if (sessionValueExists("objectStatusDiary$i") and pq_trim(getSessionValue("objectStatusDiary$i"))!='') {
              $statusWhere.=((pq_strlen($statusWhere)==4)?"":", ").getSessionValue("objectStatusDiary$i");
              $listStatusFilter[]=getSessionValue("objectStatusDiary$i");
            }
          }else{
            if (pq_array_key_exists("objectStatus$i", $_REQUEST) and pq_trim($_REQUEST["objectStatus$i"])!='') {
              $statusWhere.=((pq_strlen($statusWhere)==4)?"":", ").$_REQUEST["objectStatus$i"];
              $listStatusFilter[]=$_REQUEST["objectStatus$i"];
            }
          }
        }
        $statusWhere.=")";
      }
      foreach ($arrObj as $obj) {
        $ass=new Assignment();
        $assTable=$ass->getDatabaseTableName();
        if (get_class($obj)=='MeetingPlanningElement') {
          $meet=new Meeting();
          $meetTable=$meet->getDatabaseTableName();
          $mpeTable=$obj->getDatabaseTableName();
          $critWhere=" ( exists (select 'x' from $assTable ass where ass.refType='Meeting' and ass.refId = pe.refId and ass.idResource=".Sql::fmtId($ress);
          $critWhere.=((isset($countStatus))?" AND  exists ( select 'x' from $meetTable meet where id = ass.refId AND meet.idStatus $statusWhere)":"").")";
          $critWhere.="  or exists (select 'x' from $meetTable meet where id=pe.refId and meet.idResource=".Sql::fmtId($ress);
          $critWhere.=((isset($countStatus))?" AND meet.idStatus $statusWhere":"").") )";
        } else if (get_class($obj)=='MilestonePlanningElement' ) {
          if (!isset($countStatus)) $critWhere="1=1";
          else {
            $mlst=new Milestone();
            $mlstTable=$mlst->getDatabaseTableName();
            $mlstpeTable=$obj->getDatabaseTableName();
            $critWhere="exists (select 'x' from $mlstTable mlst where id=$mlstpeTable.refId AND mlst.idStatus $statusWhere)";
          }
        }else if (get_class($obj)=='Delivery'){
          if (!isset($countStatus)){ 
            $critWhere="1=1";
          }else{ 
            $critWhere="idStatus $statusWhere";
          }
        } else {
          $critWhere="idResource=".Sql::fmtId($ress);
          if (isset($countStatus)) $critWhere.=" AND idStatus $statusWhere";
        }
        if (!$showDone and !$showIdle and get_class($obj)!=='MeetingPlanningElement') {
          $critWhere.=" and done=0 ";
        } else if (!$showDone and !$showIdle and get_class($obj)=='MeetingPlanningElement') {
          $critWhere.=" and pe.done=0 ";
        }
        if (!$showIdle  and get_class($obj)!=='MeetingPlanningElement') {
          $critWhere.=" and idle=0 ";
        } else if (!$showIdle  and get_class($obj)=='MeetingPlanningElement') {
          $critWhere.=" and pe.idle=0 ";
        }
        if (property_exists($obj, 'actualDueDate') and property_exists($obj, 'initialDueDate')) {
          $critWhere.=" and ( "." (actualDueDate>='$startDate' and actualDueDate<='$endDate') "." or ( actualDueDate is null and (initialDueDate>='$startDate' and initialDueDate<='$endDate') )"." )";
        } else if (property_exists($obj, 'actualDueDateTime') and property_exists($obj, 'initialDueDateTime')) {
          $critWhere.=" and ( "." (actualDueDateTime>='$startDate 00:00:00' and actualDueDateTime<='$endDate 23:59:59') "." or ( actualDueDateTime is null and (initialDueDateTime>='$startDate 00:00:00' and initialDueDateTime<='$endDate 23:59:59') )"." )";
        } else if (property_exists($obj, 'validatedEndDate')) {
          $refType=pq_str_replace('PlanningElement', '', get_class($obj));
          $critWhere.=" and refType='$refType' and validatedEndDate>='$startDate' and validatedEndDate<='$endDate' ";
          if (get_class($obj)=='MeetingPlanningElement') {
            $critWhere.=" and pe.idProject in ".transformListIntoInClause(getSessionUser()->getVisibleProjects(true));
          } else {
            $critWhere.=" and idProject in ".transformListIntoInClause(getSessionUser()->getVisibleProjects(true));
          }
          if ($refType=='Milestone' and $ress!=getSessionUser()->id) {
            $lstMile=SqlList::getListWithCrit('Milestone', array('idResource'=>$ress));
            $critWhere.=" and refId in ".transformListIntoInClause($lstMile);
          }
        }else if(property_exists($obj, 'initialDate') and property_exists($obj, 'plannedDate') and property_exists($obj, 'realDate')){
          $critWhere.=" and ( "." ( realDate is null and  plannedDate is null and initialDate>='$startDate' and initialDate<='$endDate'  ) "." or ( realDate is null and (plannedDate>='$startDate' and plannedDate<='$endDate') )";
          $critWhere.=" or (  (realDate>='$startDate' and realDate<='$endDate') )"." )";
          $critWhere.=" and idProject in ".transformListIntoInClause(getSessionUser()->getVisibleProjects(true));
          if ( $ress!=getSessionUser()->id  and get_class($obj)=="Delivery") {
            $lstDelivery=SqlList::getListWithCrit('Delivery', array('idResource'=>$ress));
            $critWhere.=" and id in ".transformListIntoInClause($lstDelivery);
          }
        }else {
          $critWhere.=" and 1=0";
        }
        if(get_class($obj)=='MeetingPlanningElement'){
          $critWhere .= " and pe.idProject not in $templateProject and pe.idProject not in $underConstructionProject";
        }else{
          $critWhere .= " and idProject not in $templateProject and idProject not in $underConstructionProject";
        }
        
        $pe = new PlanningElement();
        $peTable = $pe->getDatabaseTableName();
       if (get_class($obj)=='MeetingPlanningElement') {
          $query="select pe.id from $peTable as pe join $meetTable as m on pe.refId=m.id where ".$critWhere." order by m.meetingStartTime";
          $resQuery=Sql::query($query);
          $lst =array();
          while ($res = Sql::fetchLine($resQuery)) {
            $pe = new MeetingPlanningElement($res['id']);
            array_push($lst, $pe);
          }
        } else {
          $lst=$obj->getSqlElementsFromCriteria(null, false, $critWhere);
        }
        if ($typeFilter=='Activity') {
          $activity = new Activity();
          $actTable = $activity->getDatabaseTableName();
          $respQuery="select pe.id from $peTable as pe join $actTable as act on pe.refId=act.id where act.idResource in (". $ress .") ";
          $resRespQuery=Sql::query($respQuery);
          while ($res = Sql::fetchLine($resRespQuery)) {
            $pe = new PlanningElement($res['id']);
            array_push($lst, $pe);
          }
        }
        foreach ($lst as $o) {
          if (get_class($o)=='MilestonePlanningElement' or get_class($o)=='MeetingPlanningElement') {
            $refType=$o->refType;
            $item=new $refType($o->refId);
          } else {
            $item=$o;
          }
          $isWorkElement = (property_exists($item, 'WorkElement'))?true:false;
          $productName = (property_exists($item, 'idProductVersion'))?SqlList::getNameFromId('ProductVersion', $item->idProductVersion):'';
          $productName = (!$productName and property_exists($item, 'idTargetProductVersion'))?SqlList::getNameFromId('TargetProductVersion', $item->idTargetProductVersion):'';
          $activityPlanningName = (property_exists($item, 'idActivity'))?SqlList::getNameFromId('Activity', $item->idActivity):'';
          if (pq_array_key_exists($o->idProject, $projectColorArray)) {
            $color=$projectColorArray[$o->idProject];
            $projectId=$o->idProject;
            $projectName=$projectNameArray[$o->idProject];
          } else {
            $pro=new Project($item->idProject);
            $color=$pro->getColor();
            $projectId=$pro->id;
            $projectName=$pro->name;
            $projectColorArray[$o->idProject]=$color;
            $projectNameArray[$o->idProject]=$projectName;
          }
          $typeName=null;
          $typeId=null;
          $typeClass = get_class($item).'Type';
          $type='id'.get_class($item).'Type';
          if (property_exists($item, $type)) {
            $typeId=$item->$type;
            $typeName=SqlList::getNameFromId('Type', $item->$type);
          }
          $priorityName=null;
          $priorityId=null;
          if (property_exists($item, 'idPriority')) {
            $priorityId=$item->idPriority;
            $priorityName=SqlList::getNameFromId('Priority', $item->idPriority);
          }
          $responsibleName=null;
          $responsibleId=null;
          if (property_exists($item, 'idResource')) {
            $responsibleId=$item->idResource;
            $responsibleName=SqlList::getNameFromId('Affectable', $item->idResource);
          }
          $statusName=null;
          $statusId=null;
          if (property_exists($item, 'idStatus')) {
            $statusId=$item->idStatus;
            $statusName=SqlList::getNameFromId('Status', $item->idStatus);
          }
          $description=null;
          if (property_exists($item, 'description')) {
            if ($item->description) {
              $description=$item->description;
              $minChar = 200;
              if(pq_strpos($description, '<img ') != ''){
                $minChar = 400;
                $itemWidth = ($destinationWidth/$nbOffDays)-30;
                $description=pq_str_replace('<img ','<img style="max-width:'.($itemWidth-15).'px;" onClick="showImage(\'Note\',this.src,\' \');"',$description);
                $img = pq_substr($description, pq_strpos($description, '<img '), (pq_strpos($description, '/>')-pq_strpos($description, '<img '))+2);
                $description = pq_substr($description, 0, pq_strpos($description, '<img ')).'<div>#IMGREPLACED#</div>'.pq_substr($description, pq_strpos($description, '<img '));
                $text = new Html2Text ($description);
                $descr = $text->getText ();
                $descr=pq_htmlspecialchars($descr);
                $descr=pq_str_replace('#IMGREPLACED#',$img,$descr);
              }else{
                $text = new Html2Text ($description);
                $descr = $text->getText ();
                $descr=pq_htmlspecialchars($descr);
              }
              if (pq_strlen ($description) > 4000) {
  //               $descr1 = pq_substr ( $descr, 0, 4000);
  //               $description1 = nl2brForPlainText ( $descr1 );
                $descr2 = pq_substr ( $descr, 0, $minChar );
                $description = nl2brForPlainText ( $descr2 );
              } else {
  //               $description1=$description;
                $descr2 = pq_substr ( $descr, 0, $minChar);
                $description = nl2brForPlainText ( $descr2 );
              }
            } else {
  //             $description1 = '<div style="font-style:italic; color:#CDCADB; ">' . i18n ( "kanbanNoDescription" ) . '</div>';
              $description = '<div style="font-style:italic; color:#CDCADB; ">' . i18n ( "kanbanNoDescription" ) . '</div>';
            }
          }
          //Ticket #438 F.KARA
          $meetingStartTime=null;
          if(property_exists($item,'meetingStartTime')) {
              $meetingStartTime=pq_substr($item->meetingStartTime,0,5);
          }
          $meetingEndTime=null;
          if(property_exists($item,'meetingEndTime')) {
            $meetingEndTime=pq_substr($item->meetingEndTime,0,5);
          }
          $date=null;
          $dateField="";
          $name="";
          $id=$o->id;
          $class=get_class($o);
          if (property_exists($obj, 'actualDueDate') and property_exists($obj, 'initialDueDate') and property_exists($o, 'actualDueDate') and property_exists($o, 'initialDueDate')) {
            if ($o->actualDueDate) {
              $date=$o->actualDueDate;
              $dateField=i18n('colActualDueDate');
            } else {
              $date=$o->initialDueDate;
              $dateField=i18n('colInitialDueDate');
            }
            $name=$o->name;
          } else if (property_exists($obj, 'actualDueDateTime') and property_exists($obj, 'initialDueDateTime') and property_exists($o, 'initialDueDateTime') and property_exists($o, 'actualDueDateTime')) {
            if ($o->actualDueDateTime) {
              $date=pq_substr($o->actualDueDateTime, 0, 10);
              $dateField=i18n('colActualDueDate');
            } else {
              $date=pq_substr($o->initialDueDateTime, 0, 10);
              $dateField=i18n('colInitialDueDate');
            }
            $name=$o->name;
           } else if (property_exists($obj, 'validatedEndDate') and property_exists($o, 'validatedEndDate') and $o->validatedEndDate) {
            $name=$o->refName;
            $id=$o->refId;
            $class=$o->refType;
            $date=$o->validatedEndDate;
            $dateField=($class=='Meeting')?i18n('colMeetingDate'):i18n('colValidatedEndDate');
          } else if ( property_exists($obj, 'initialDate') and property_exists($obj, 'plannedDate') and property_exists($obj, 'realDate') and property_exists($o, 'initialDate') and property_exists($o, 'plannedDate') and property_exists($o, 'realDate')){
            $name=$o->name;
            if($o->realDate!=''){
              $date=$o->realDate;
              $dateField=i18n('colRealDate');
            }elseif ($o->realDate=='' and $o->plannedDate!=''){
              $date=$o->plannedDate;
              $dateField=i18n('colPlannedDate');
            }else{
              $date=$o->initialDate;
              $dateField=i18n('colInitialDate');
            }
          } else if (property_exists($obj, 'plannedEndDate') and property_exists($o, 'plannedEndDate') and ! isset($result[$date]["$o->refType#$o->refId"])) {
            $name=$o->refName;
            $id=$o->refId;
            $class=$o->refType;
            $date=$o->plannedEndDate;
            $dateField=i18n('colPlannedEndDate');
            $item=new $class($id,true);
            $statusId=$item->idStatus;
            $statusName=SqlList::getNameFromId('Status', $item->idStatus);
            $tn=SqlElement::getTypeName($class);
            if (property_exists($class, $tn)) {
              $typeId=$item->$tn;
              $typeName=SqlList::getNameFromId('Type', $item->$tn);
            }
            if (property_exists($class, 'description')) {
              $description=$item->description;
            }
            if (property_exists($class, 'idResource')) {
              $responsibleId=$item->idResource;
              $responsibleName=SqlList::getNameFromId('Affectable', $item->idResource);
            }
            if (property_exists($class, 'idPriority')) {
              $priorityId=$item->idPriority;
              $priorityName=SqlList::getNameFromId('Priority', $item->idPriority);
            }
          }
          if ($date) {
            if (!pq_array_key_exists($date, $result)) {
              $result[$date]=array();
            }
            
            $isResourceTeam=false;
            $idResourceTeam=null;
            $ass = new Assignment();
            $assList = $ass->getSqlElementsFromCriteria(array('refType'=>get_class($item), 'refId'=>$item->id, 'isResourceTeam'=>1));
            foreach ($assList as $asgn){
            	$resTeam = ResourceTeamAffectation::getSingleSqlElementFromCriteria('ResourceTeamAffectation', array('idResourceTeam'=>$asgn->idResource, 'idResource'=>$ress));
            	if($resTeam->id){
            		$idResourceTeam = $resTeam->idResourceTeam;
            		$isResourceTeam=true;
            	}
            }
            $ass=new Assignment();
            $assigment = $ass->getSingleSqlElementFromCriteria('Assignment', array('refType'=>get_class($item), 'refId'=>$item->id, 'idResource'=>$ress));
            if(pq_strpos(get_class($obj), 'PlanningElement')){
              if($modeColorTitle == 'colorItem'){
                $color = $item->getColor();
              }
            }else{
              if($modeColorTitle == 'colorItem' and property_exists($class, 'color')){
                $color = $item->color;
              }
            }
            if($modeColorTitle == 'colorType'){
              $itemType = new $typeClass($typeId);
              $color = $itemType->color;
            }else if($modeColorTitle == 'colorPriority'){
              $itemPriority = new Priority($priorityId);
              $color = $itemPriority->color;
            }else if($modeColorTitle == 'noColor'){
              $color='';
            }
  
            $result[$date]["$class#$id"]=array(
                'class'=>$class,
                'id'=>$id,
                'work'=>0,
                'real'=>false,
                'name'=>$name,
                'color'=>$color,
                'date'=>$dateField,
                'projectId'=>$projectId,
                'projectName'=>$projectName,
                'typeId'=>$typeId,
                'typeName'=>$typeName,
                'priorityId'=>$priorityId,
                'priorityName'=>$priorityName,
                'responsibleId'=>$responsibleId,
                'responsibleName'=>$responsibleName,
                'statusId'=>$statusId,
                'statusName'=>$statusName,
                'description'=>$description,
                'meetingStartTime'=> $meetingStartTime, //Ticket #438 F.KARA - Get the start time of a meeting
                'meetingEndTime'=> $meetingEndTime,
                'isResourceTeam'=> $isResourceTeam,
                'idResourceTeam'=> $idResourceTeam,
                'idAssignment'=>$assigment->id,
                'isWorkElement'=>$isWorkElement,
                'productName'=>$productName,
                'activityPlanningName'=>$activityPlanningName
            );
          }
        }
      }
  	}
  	// Planned Activities and real work
  	$ressList = array(Sql::fmtId($ress));
  	$resourceTeamAff = SqlList::getListWithCrit('ResourceTeamAffectation', array('idResource'=>$ress));
  	foreach ($resourceTeamAff as $id){
  	  $resTeamaff = new ResourceTeamAffectation($id);
  	  array_push($ressList, Sql::fmtId($resTeamaff->idResourceTeam));
  	}
  	$ressList = '('.implode(',', $ressList).')';
  	$critWhere="idResource in ".$ressList;
  	$critWhere.=" and workDate>='$startDate' and workDate<='$endDate'";
  	$critWhereAss="idResource in ".$ressList." and assignedWork is null";
  	if ($selectedTypes != 'All') {
  	  $selectedTypes = pq_str_replace(",", "','", $selectedTypes);
  	  $critWhereAss.=" AND refType IN ('$selectedTypes')";
  	  $critWhere.=" AND refType IN ('$selectedTypes')";
  	}
  	$pw=new PlannedWork();
  	$w=new Work();
  	$ass=new Assignment();
  	$pwList=$pw->getSqlElementsFromCriteria(null,false,$critWhere." and idProject not in $proposaleProject and idProject not in $templateProject and idProject not in $underConstructionProject");
  	$wList=$w->getSqlElementsFromCriteria(null,false,$critWhere);
  	$assList=$ass->getSqlElementsFromCriteria(null,false,$critWhereAss);
  	$workList=array_merge($pwList,$wList);
  	//$workList=array_merge($workList, $assList);
  	//KEVIN
  	foreach ($workList as $pw) {
  	  if (!$pw->refType) continue;
  	  $ass=new Assignment();
  	  $assTable=$ass->getDatabaseTableName();
  	  $assignment = $ass->getSingleSqlElementFromCriteria('Assignment', array('refType'=>$pw->refType, 'refId'=>$pw->refId, 'idResource'=>$ress));
  	  $item=new $pw->refType($pw->refId);
  	  $isWorkElement = (property_exists($item, 'WorkElement'))?true:false;
  	  $productName = (property_exists($item, 'idProductVersion'))?SqlList::getNameFromId('ProductVersion', $item->idProductVersion):'';
  	  $productName = (!$productName and property_exists($item, 'idTargetProductVersion'))?SqlList::getNameFromId('TargetProductVersion', $item->idTargetProductVersion):'';
  	  $activityPlanningName = (property_exists($item, 'idActivity'))?SqlList::getNameFromId('Activity', $item->idActivity):'';
  	  $class = $pw->refType;
  	  if (! property_exists($item,'done') or ! property_exists($item,'idle')  or ! property_exists($item,'idStatus')) continue;
  	  if (($item->done and !$showDone and !$showIdle) or ($item->idle and !$showIdle) or  (isset($countStatus) and !in_array($item->idStatus, $listStatusFilter)))
  	    continue;
  		if ($pw->refType=='Meeting') {
  		    if(isset($item->meetingStartTime)) {
                  $display=htmlFormatTime($item->meetingStartTime);
              }
  		} else if (get_class($pw)=='Work') {
  				$display='['.Work::displayWorkWithUnit($pw->work).'] ';
  		} else if (get_class($pw)=='Assignment') {
  		  $display='[0]';
  		} else {
  		  $display='<i>('.Work::displayWorkWithUnit($pw->work).')</i> ';
  		}
  		$adminProject = Project::getAdminitrativeProjectList(true);
  		$isAdmin = in_array($pw->idProject, $adminProject);
  		if (pq_array_key_exists($item->idProject,$projectColorArray)) {
  			$color=$projectColorArray[$item->idProject];
  			$projectId=$item->idProject;
  			$projectName=$projectNameArray[$item->idProject];
  		} else {
  			$pro=new Project($item->idProject);
  			$color=$pro->getColor();
  			$projectId=$item->idProject;
  			$projectName=$pro->name;
  			$projectColorArray[$item->idProject]=$color;
  			$projectNameArray[$item->idProject]=$projectName;
  		}
  		if (get_class($pw)=='Assignment'){
  		  $pe = new PlanningElement();
  		  $critWherePe = "refType = '" .$pw->refType ."' and refId=".$pw->refId;
  		  $pe = $pe->getSqlElementsFromCriteria(null,false,$critWherePe);
  		  if(isset($pe[0])){
  		    $date = ($isAdmin)?$pe[0]->realEndDate:$pe[0]->plannedEndDate;
  		  }else{
  		    $date='';
  		  }
  		} else {
  		  $date=$pw->workDate;
  		}
  		if (!pq_array_key_exists($date, $result)) {
  			$result[$date]=array();
  		}
  		$typeId=null;
  		$typeName=null;
  		$typeClass = get_class($item).'Type';
  		$type='id'.get_class($item).'Type';
  		if (property_exists($item,$type)) {
  		  $typeId=$item->$type;
  		  $typeName=SqlList::getNameFromId('Type', $item->$type);
  		}
  		$priorityId=null;
  		$priorityName=null;
  		if (property_exists($item,'idPriority')) {
  		  $priorityId=$item->idPriority;
  		  $priorityName=SqlList::getNameFromId('Priority', $item->idPriority);
  		}
  		$responsibleId=null;
  		$responsibleName=null;
  		if (property_exists($item,'idResource')) {
  		  $responsibleId=$item->idResource;
  		  $responsibleName=SqlList::getNameFromId('Affectable', $item->idResource);
  		}
  		$statusName=null;
  		$statusId=null;
  		if (property_exists($item,'idStatus')) {
  		  $statusId=$item->idStatus;
  		  $statusName=SqlList::getNameFromId('Status', $item->idStatus);
  		}
  		$description=null;
  	    if (property_exists($item, 'description')) {
            if ($item->description) {
              $description=$item->description;
              $minChar = 200;
              if(pq_strpos($description, '<img ') != ''){
                $minChar = 400;
                $itemWidth = ($destinationWidth/$nbOffDays)-30;
                $description=pq_str_replace('<img ','<img style="max-width:'.($itemWidth-15).'px;" onClick="showImage(\'Note\',this.src,\' \');"',$description);
                $img = pq_substr($description, pq_strpos($description, '<img '), (pq_strpos($description, '/>')-pq_strpos($description, '<img '))+2);
                $description = pq_substr($description, 0, pq_strpos($description, '<img ')).'<div>#IMGREPLACED#</div>'.pq_substr($description, pq_strpos($description, '<img '));
                $text = new Html2Text ($description);
                $descr = $text->getText ();
                $descr=pq_htmlspecialchars($descr);
                $descr=pq_str_replace('#IMGREPLACED#',$img,$descr);
              }else{
                $text = new Html2Text ($description);
                $descr = $text->getText ();
                $descr=pq_htmlspecialchars($descr);
              }
              if (pq_strlen ($description) > 4000) {
  //               $descr1 = pq_substr ( $descr, 0, 4000);
  //               $description = nl2brForPlainText ( $descr1 );
                $descr2 = pq_substr ( $descr, 0, $minChar );
                $description = nl2brForPlainText ( $descr2 );
              } else {
  //               $description=$description;
                $descr2 = pq_substr ( $descr, 0, $minChar);
                $description = nl2brForPlainText ( $descr2 );
              }
            } else {
  //             $description = '<div style="font-style:italic; color:#CDCADB; ">' . i18n ( "kanbanNoDescription" ) . '</div>';
              $description = '<div style="font-style:italic; color:#CDCADB; ">' . i18n ( "kanbanNoDescription" ) . '</div>';
            }
          }
          //Ticket #438 F.KARA
  		$meetingStartTime=null;
  		if(property_exists($item,'meetingStartTime')) {
  		  $meetingStartTime=pq_substr($item->meetingStartTime,0,5);;
      }
  //     $isResourceTeam=false;
  //     $idResourceTeam=null;
  //     $ass = new Assignment();
  //     $assList = $ass->getSqlElementsFromCriteria(array('refType'=>get_class($item), 'refId'=>$item->id, 'isResourceTeam'=>1));
  //     foreach ($assList as $asgn){
  //       $resTeam = ResourceTeamAffectation::getSingleSqlElementFromCriteria('ResourceTeamAffectation', array('idResourceTeam'=>$asgn->idResource, 'idResource'=>$ress));
  //       if($resTeam->id){
  //         $idResourceTeam = $resTeam->idResourceTeam;
  //         $isResourceTeam=true;
  //       }
  //     }
      $meetingEndTime = null;
      if (get_class($pw) == 'PlannedWork' && $pw->isManual == 1 && !$meetingStartTime) {
        $pwManual = PlannedWorkManual::getSingleSqlElementFromCriteria('PlannedWorkManual',array('idPlannedWork' => $pw->id));
        if ($pwManual && $pwManual->id) {
          $times = getAmPmTimes($pw->idProject);
          if ($pwManual->period == 'PM') {
            $meetingStartTime = $times['startPM'];
            $meetingEndTime = $times['endPM'];
          } else {
            $meetingStartTime = $times['startAM'];
            $meetingEndTime = $times['endAM'];
          }
        }
      }
      
      if($modeColorTitle == 'colorItem'){
        $color = $item->getColor();
      }else if($modeColorTitle == 'colorType'){
        $itemType = new $typeClass($typeId);
        $color = $itemType->color;
      }else if($modeColorTitle == 'colorPriority'){
        $itemPriority = new Priority($priorityId);
        $color = $itemPriority->color;
      }else if($modeColorTitle == 'noColor'){
        $color='';
      }
      
      $team=new ResourceTeam($pw->idResource);
      $isResourceTeam=($team->id)?1:0;
      $idResourceTeam=($team->id)?$team->id:null;
        if (isset($result[$date][$pw->refType.'#'.$pw->refId])) {
          $result[$date][$pw->refType.'#'.$pw->refId]['work']=(get_class($pw)=='Assignment') ? 0 : $pw->work;
          $result[$date][$pw->refType.'#'.$pw->refId]['real']=((get_class($pw)=='Work')?true:false);
          
          if (get_class($pw) == 'PlannedWork' && $pw->isManual == 1 && empty($result[$date][$pw->refType.'#'.$pw->refId]['meetingStartTime'])) {
            $result[$date][$pw->refType.'#'.$pw->refId]['meetingStartTime'] = $meetingStartTime;
            $result[$date][$pw->refType.'#'.$pw->refId]['meetingEndTime']   = $meetingEndTime;
          }
        } else {
          $result[$date][$pw->refType.'#'.$pw->refId."|".$pw->idResource]=array(
    				'class'=>$pw->refType,
    		    'id'=>$pw->refId,
    				'work'=>(get_class($pw)=='Assignment') ? 0 : $pw->work,
    		    'real'=>((get_class($pw)=='Work')?true:false),
    				'name'=>$item->name,
    				'color'=>$color,
    		    'date'=>"",
    				'projectId'=>$projectId,
    				'projectName'=>$projectName,
    				'typeId'=>$typeId,
    				'typeName'=>$typeName,
    				'priorityId'=>$priorityId,
    				'priorityName'=>$priorityName,
    				'responsibleId'=>$responsibleId,
    				'responsibleName'=>$responsibleName,
    		    'statusId'=>$statusId,
    		    'statusName'=>$statusName,
    		    'description'=>$description,
            'meetingStartTime'=> $meetingStartTime,//Ticket #438 F.KARA - Get the start time of a meeting
              'meetingEndTime'   => $meetingEndTime,
    		    'isResourceTeam'=> $isResourceTeam,
    		    'idResourceTeam'=> $idResourceTeam,
              'idAssignment'=>$assignment->id,
              'isWorkElement'=>$isWorkElement,
              'productName'=>$productName,
              'activityPlanningName'=>$activityPlanningName
    		  );
        }
  	}
  	// PBER : assigned items at planned end date - Source = #11894 (in fact was not working as expected)
  	$showActivitiesPlannedEndDate = Parameter::getUserParameter("showActivitiesPlannedEndDateDiary");
  	$showActivitiesPlannedEndDate = ($showActivitiesPlannedEndDate=='on' or $showActivitiesPlannedEndDate=='1' or $showActivitiesPlannedEndDate=="")?true:false;
  	if ($showActivitiesPlannedEndDate) {
  	  $pe=new PlanningElement();
  	  $peTable=$pe->getDatabaseTableName();
  	  $ass=new Assignment();
  	  $assTable=$ass->getDatabaseTableName();
  	  $critAssigned="plannedEndDate>='$startDate' and plannedEndDate<='$endDate' ";
  	  $critAssigned.=" and exists (select 'x' from $assTable where $assTable.idResource=$ress and $assTable.refType=$peTable.refType and $assTable.refId=$peTable.refId and $assTable.idle=0)";
  	  if ($selectedTypes != 'All') $critAssigned.=" and $peTable.refType IN ('$selectedTypes')";
  	  if (! $showDone) $critAssigned.=" and $peTable.done=0";
  	  if (! $showIdle) $critAssigned.=" and $peTable.idle=0";
  	  
  	  $peList=$pe->getSqlElementsFromCriteria(null,null,$critAssigned);
  	  foreach ($peList as $pe) {	    
  	    if (isset($result[$pe->plannedEndDate][$pe->refType.'#'.$pe->refId."|".$ress])) continue;
  	    if (isset($result[$pe->plannedEndDate][$pe->refType.'#'.$pe->refId])) continue;
  	    $item=new $pe->refType($pe->refId, true);
  	    if (array_key_exists($pe->idProject,$projectColorArray)) {
  	      $color=$projectColorArray[$pe->idProject];
  	      $projectId=$pe->idProject;
  	      $projectName=$projectNameArray[$pe->idProject];
	      } else {
	        $pro=new Project($pe->idProject);
	        $color=$pro->getColor();
	        $projectId=$pe->idProject;
	        $projectName=$pro->name;
	        $projectColorArray[$pe->idProject]=$color;
	        $projectNameArray[$pe->idProject]=$projectName;
	      }
	      $typeName=null;
	      $typeId=null;
	      $typeClass = get_class($item).'Type';
	      $type='id'.get_class($item).'Type';
	      if (property_exists($item, $type)) {
	        $typeId=$item->$type;
	        $typeName=SqlList::getNameFromId('Type', $item->$type);
	      }
	      $priorityName=null;
	      $priorityId=null;
	      if (property_exists($item, 'idPriority')) {
	        $priorityId=$item->idPriority;
	        $priorityName=SqlList::getNameFromId('Priority', $item->idPriority);
	      }
	      $responsibleName=null;
	      $responsibleId=null;
	      if (property_exists($item, 'idResource')) {
	        $responsibleId=$item->idResource;
	        $responsibleName=SqlList::getNameFromId('Affectable', $item->idResource);
	      }
	      $statusName=null;
	      $statusId=null;
	      if (property_exists($item, 'idStatus')) {
	        $statusId=$item->idStatus;
	        $statusName=SqlList::getNameFromId('Status', $item->idStatus);
	      }
	      $description=null;
	      $description=null;
	      if (property_exists($item, 'description')) {
	        if ($item->description) {
	          $description=$item->description;
	          $minChar = 200;
	          if(pq_strpos($description, '<img ') != ''){
	            $minChar = 400;
	            $itemWidth = ($destinationWidth/$nbOffDays)-30;
	            $description=pq_str_replace('<img ','<img style="max-width:'.($itemWidth-15).'px;" onClick="showImage(\'Note\',this.src,\' \');"',$description);
	            $img = pq_substr($description, pq_strpos($description, '<img '), (pq_strpos($description, '/>')-pq_strpos($description, '<img '))+2);
	            $description = pq_substr($description, 0, pq_strpos($description, '<img ')).'<div>#IMGREPLACED#</div>'.pq_substr($description, pq_strpos($description, '<img '));
	            $text = new Html2Text ($description);
	            $descr = $text->getText ();
	            $descr=pq_htmlspecialchars($descr);
	            $descr=pq_str_replace('#IMGREPLACED#',$img,$descr);
	          }else{
	            $text = new Html2Text ($description);
	            $descr = $text->getText ();
	            $descr=pq_htmlspecialchars($descr);
	          }
	          if (pq_strlen ($description) > 4000) {
	            //               $descr1 = pq_substr ( $descr, 0, 4000);
	            //               $description1 = nl2brForPlainText ( $descr1 );
	            $descr2 = pq_substr ( $descr, 0, $minChar );
	            $description = nl2brForPlainText ( $descr2 );
	          } else {
	            //               $description1=$description;
	            $descr2 = pq_substr ( $descr, 0, $minChar);
	            $description = nl2brForPlainText ( $descr2 );
	          }
	        } else {
	          //             $description1 = '<div style="font-style:italic; color:#CDCADB; ">' . i18n ( "kanbanNoDescription" ) . '</div>';
	          $description = '<div style="font-style:italic; color:#CDCADB; ">' . i18n ( "kanbanNoDescription" ) . '</div>';
	        }
	      }
	      if($modeColorTitle == 'colorItem'){
	        $color = $item->getColor();
	      }else if($modeColorTitle == 'colorType'){
	        $itemType = new $typeClass($typeId);
	        $color = $itemType->color;
	      }else if($modeColorTitle == 'colorPriority'){
	        $itemPriority = new Priority($priorityId);
	        $color = $itemPriority->color;
	      }else if($modeColorTitle == 'noColor'){
	        $color='';
	      }
	      $productName = (property_exists($item, 'idProductVersion'))?SqlList::getNameFromId('ProductVersion', $item->idProductVersion):'';
	      $productName = (!$productName and property_exists($item, 'idTargetProductVersion'))?SqlList::getNameFromId('TargetProductVersion', $item->idTargetProductVersion):'';
	      $activityPlanningName = (property_exists($item, 'idActivity'))?SqlList::getNameFromId('Activity', $item->idActivity):'';
	      $result[$pe->plannedEndDate][$pe->refType.'#'.$pe->refId."|".$ress]=array(
  	        'class'=>$pe->refType,
  	        'id'=>$pe->refId,
    	      'work'=>0,
    	      'real'=>0,
  	        'name'=>$pe->refName,
  	        'color'=>$color,
    	      'date'=>"",
    	      'projectId'=>$projectId,
    	      'projectName'=>$projectName,
    	      'typeId'=>$typeId,
    	      'typeName'=>$typeName,
    	      'priorityId'=>$priorityId,
    	      'priorityName'=>$priorityName,
    	      'responsibleId'=>$responsibleId,
    	      'responsibleName'=>$responsibleName,
    	      'statusId'=>$statusId,
    	      'statusName'=>$statusName,
    	      'description'=>$description,
    	      'meetingStartTime'=> null,
  	        'meetingEndTime'   => null,
  	        'isResourceTeam'=> null,
  	        'idResourceTeam'=> null,
    	      'idAssignment'=> null,
  	        'isWorkElement'=> null,
    	      'productName'=>$productName,
    	      'activityPlanningName'=>$activityPlanningName
  	    );
  	  }
  	}
  	
  	return $result;
  }
?>

