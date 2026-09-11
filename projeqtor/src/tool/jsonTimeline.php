<?PHP
use Mpdf\Tag\Table;
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

/** ===========================================================================
 * Get the list of objects, in Json format, to display the grid list
 */
  require_once "../tool/projeqtor.php";
  session_write_close();
  
  $user = getSessionUser();
  $startDate=date('Y-m-d');
  $endDate=date('Y-m-d');
  
  $maxRow = Parameter::getUserParameter('maxTimelineRow');
  $idProject = explode(',', pq_str_replace(array(' ','(',')'),'',getVisibleProjectsList()));
  
  $tlItem = new TimelineItem();
  $timeline = $tlItem->getSqlElementsFromCriteria(array('idUser'=>$user->id));
  $itemList = array();
  $itemListSortDate = array();
  foreach ($timeline as $item){
    $itemRef = $item->getSingleSqlElementFromCriteria('PlanningElement',  array('refType'=>$item->refType, 'refId'=>$item->refId));
    if($itemRef->id and (in_array($itemRef->idProject, $idProject) or $idProject[0]=='*')){
      if($itemRef->realStartDate and $itemRef->realStartDate < $startDate){
        $startDate = $itemRef->realStartDate;
      }else if(!$itemRef->realStartDate and $itemRef->plannedStartDate and $itemRef->plannedStartDate < $startDate){
        $startDate = $itemRef->plannedStartDate;
      }else if(!$itemRef->plannedStartDate and $itemRef->validatedStartDate and $itemRef->validatedStartDate < $startDate){
        $startDate = $itemRef->validatedStartDate;
      }
      if($itemRef->realEndDate and $itemRef->realEndDate > $startDate){
        $endDate = $itemRef->realEndDate;
      }else if(!$itemRef->realEndDate and $itemRef->plannedEndDate and $itemRef->plannedEndDate > $endDate){
        $endDate = $itemRef->plannedEndDate;
      }else if(!$itemRef->plannedEndDate and $itemRef->validatedEndDate and $itemRef->validatedEndDate > $endDate){
        $endDate = $itemRef->validatedEndDate;
      }
      
      $itemList[$itemRef->id]['name']=$item->name;
      $itemList[$itemRef->id]['startDate']=null;
      if($itemRef->realStartDate){
        $itemList[$itemRef->id]['startDate']=$itemRef->realStartDate;
      }else if(!$itemRef->realStartDate and $itemRef->plannedStartDate){
        $itemList[$itemRef->id]['startDate']=$itemRef->plannedStartDate;
      }else if(!$itemRef->plannedStartDate and $itemRef->validatedStartDate){
        $itemList[$itemRef->id]['startDate']=$itemRef->validatedStartDate;
      }
      $itemList[$itemRef->id]['endDate']=null;
      if($itemRef->realEndDate){
        $itemList[$itemRef->id]['endDate']=$itemRef->realEndDate;
      }else if(!$itemRef->realEndDate and $itemRef->plannedStartDate){
        $itemList[$itemRef->id]['endDate']=$itemRef->plannedEndDate;
      }else if(!$itemRef->plannedStartDate and $itemRef->validatedEndDate){
        $itemList[$itemRef->id]['endDate']=$itemRef->validatedEndDate;
      }
      $itemList[$itemRef->id]['refType']=$item->refType;
      $itemList[$itemRef->id]['refId']=$item->refId;
      $itemStartdate = $itemList[$itemRef->id]['startDate'];
      $itemEndDate = $itemList[$itemRef->id]['endDate'];
      $itemDateInterval = $itemStartdate.'_'.$itemEndDate;
      if(!isset($itemListSortDate[$itemRef->wbs][$itemDateInterval][$itemRef->id]))$itemListSortDate[$itemRef->wbs][$itemDateInterval][$itemRef->id]=$item->name;
    }
  }
  
  $totWidth=RequestHandler::getValue('destinationWidth');
  // calculations Date
  $format='month';
  $todayLeft = 0;
  $maxDate = addMonthsToDate($endDate, 1);
  $minDate = date('Y-m-01', pq_strtotime($startDate));
  $startDate = $minDate;
  $numDays = (dayDiffDates($minDate, $maxDate) +1);
  $ratio=27.8;
  if($format == 'day') {
    $colWidth = 18;
    $colUnit = 1;
    $topUnit=7;
    $ratio=($totWidth/round($numDays / $topUnit))*(1/$topUnit);
    $todayLeft = round(dayDiffDates($startDate, date('Y-m-d')));
    $todayLeft = ($ratio*$todayLeft);
    $todayHeight=52;
  } else if($format == 'week') {
    $colWidth = 50;
    $colUnit = 7;
    $topUnit=7;
    $ratio=($totWidth/round($numDays / $topUnit))*(1/$topUnit);
    $todayLeft = round(dayDiffDates($startDate, date('Y-m-d')));
    $todayLeft = ($ratio*$todayLeft);
    $todayHeight=24;
  } else if($format == 'month') {
    $colWidth = 60;
    $colUnit = 30;
    $topUnit=30;
    $ratio=($totWidth/round($numDays / $topUnit))*(1/$topUnit);
    $todayLeft = round(dayDiffDates($startDate, date('Y-m-d')));
    $todayLeft = (($topUnit*$ratio)*$todayLeft)/$topUnit;
    $todayHeight=24;
  } else if($format == 'quarter') {
    $colWidth = 30;
    $colUnit = 30;
    $topUnit=90;
    $ratio=($totWidth/round($numDays / $topUnit))*(1/$topUnit);
    $todayLeft = round(dayDiffDates($startDate, date('Y-m-d')));
    $todayLeft = (($topUnit*$ratio)*$todayLeft)/$topUnit;
    $todayHeight=24;
  }
  $numUnits = round($numDays / $colUnit);
  $topUnits = round($numDays / $topUnit);
  
  $displayTimeline = (count($timeline)>0)?'':'display:none;';
  
  echo '<div style="position:relative;width:100%;overflow-y:hidden;padding-top: 23px;'.$displayTimeline.'">';
  echo '<div style="position:relative;width:'.(($topUnit*$ratio)*$topUnits).'px;overflow:hidden;min-height:21px;">';
  echo '<table style="width:100%;margin: 0px; padding: 0px;">';
  echo '<tr style="height: 20px;border-bottom: 1px solid #AAAAAA; ">';
  $day=$minDate;
  for ($i=0;$i<$topUnits;$i++) {
    $span=$topUnit;
    $title="";
    $today = false;
    if ($format=='month') {
      $title=date('M y', pq_strtotime($day));
      if(date('Y-m') == date('Y-m', pq_strtotime($day)))$today=true;
      $span=($day==$minDate)?$topUnit:'';
    } else if($format=='week') {
      $title=pq_substr($day,2,2) . " #" . weekNumber($day);
      if(date('Y-W') == date('Y-W', pq_strtotime($day)))$today=true;
      if($today){
        $todayLeft += $topUnit*(dayDiffDates(date('Y-m-d', firstDayofWeek(date('W', pq_strtotime($day)), date('Y', pq_strtotime($day)))), date('Y-m-d'))+1);
      }
    } else if ($format=='day') {
      $tDate = pq_explode("-", $day);
      $date= mktime(0, 0, 0, $tDate[1], $tDate[2]+1, $tDate[0]);
      $title=pq_substr($day,0,4) . " #" . weekNumber($day);
      $title.=' (' . pq_substr(i18n(date('F', $date)),0,4) . ')';
      if(date('Y-m-d') == $day)$today=true;
      if($today){
        $todayLeft += $topUnit*(dayDiffDates(date('Y-m-d', firstDayofWeek(date('W', pq_strtotime($day)), date('Y', pq_strtotime($day)))), date('Y-m-d'))+1);
      }
    } else if ($format=='quarter') {
      $arrayQuarter=array("01"=>"1","02"=>"1","03"=>"1",
          "04"=>"2","05"=>"2","06"=>"2",
          "07"=>"3","08"=>"3","09"=>"3",
          "10"=>"4","11"=>"4","12"=>"4");
  
      $title="Q";
      $title.=$arrayQuarter[pq_substr($day,5,2)];
      $title.=" ".pq_substr($day,0,4);
      if($arrayQuarter[pq_substr(date('Y-m-d'),5,2)] == $arrayQuarter[pq_substr($day,5,2)])$today=true;
      $span=numberOfDaysOfMonth($day)+numberOfDaysOfMonth(addMonthsToDate($day,1))+numberOfDaysOfMonth(addMonthsToDate($day,2));
      $span=3*30/5;
    }
    if(isset($displayIsLimited) and $displayIsLimited)$totalspan+=$span;
    $style='';
    if($day!=$minDate){
      $style='border-left: 1px solid #AAAAAA;';
    }
    $bold = ($today)?'font-weight:bold':'';
    echo '<td class="" style="'.$bold.';width:'.($topUnit*$ratio).'px !important;'.$style.'">';
    echo '&nbsp'.$title;
    echo '</td>';
    if ($format=='month') {
      $day=addMonthsToDate($day,1);
    } else if ($format=='quarter') {
      $day=addMonthsToDate($day,3);
    } else {
      $day=addDaysToDate($day,$topUnit);
    }
  }
  echo '</tr>';
  echo '</table>';
  echo '</div>';
  $left = round(dayDiffDates($startDate, date('Y-m-d')));
  $left = ((($topUnit*$ratio)*$left)/numberOfDaysOfMonth(date('Y-m-d')));
  echo '<div style="position:absolute;top:0px;left:'.$todayLeft.'px;height: 18px;background:green;color:white;padding:0px 5px;z-index:999;border-radius: 5px 0px 5px 0px;" title="'.htmlFormatDate(date('Y-m-d')).'">'.ucfirst(i18n('today')).'</div>';
  echo '<div style="position:absolute;top:18px;left:'.$todayLeft.'px;height: 25px;width:2px;background:green;z-index: -1;" title="'.htmlFormatDate(date('Y-m-d')).'"></div>';
  echo '<div style="position:absolute;top:43px;left:'.$todayLeft.'px;height: 100%;width:2px;background:green;z-index:999;" title="'.htmlFormatDate(date('Y-m-d')).'"></div>';
  echo '<div style="position:relative;width:'.(($topUnit*$ratio)*$topUnits).'px;min-height:64px;margin: 3px 0px;overflow-y:scroll;overflow-x:hidden;">';
  $left = round(dayDiffDates($startDate, date('Y-m-d')));
  $left = ((($topUnit*$ratio)*$left)/numberOfDaysOfMonth(date('Y-m-d')));
  $itemToDraw = array();
  $milestoneToDraw = array();
  ksort($itemListSortDate);
  foreach ($itemListSortDate as $wbs=>$dateList){
    foreach ($dateList as $date=>$idItemList){
      foreach ($idItemList as $idItem=>$itemName){
        $nbRow = 0;
        $currentStartDate = explode('_', $date)[0];
        $currentEndDate = explode('_', $date)[1];
        $pe = new PlanningElement($idItem,true);
        if(count($itemToDraw)>0 and isset($itemToDraw[$nbRow])){
          foreach ($itemToDraw as $row=>$dateList){
            foreach ($dateList as $itemDate=>$wbsList){
              foreach ($wbsList as $wbs=>$item){
                $itemStartdate = explode('_', $itemDate)[0];
                $itemEndDate = explode('_', $itemDate)[1];
                if(($currentStartDate <= $itemStartdate and $currentEndDate >= $itemStartdate) or
                   ($currentStartDate <= $itemEndDate and $currentEndDate >= $itemEndDate) or
                   ($currentStartDate >= $itemStartdate and $currentEndDate <= $itemEndDate))$nbRow++;
              }
            }
          }
        }
        $item = $itemList[$idItem];
        if($nbRow-count($itemToDraw) > 0)$nbRow-=($nbRow-count($itemToDraw));
        $left = round(dayDiffDates($startDate, $item['startDate']));
        $left = ((($topUnit*$ratio)*$left)/$topUnit)+1;
        if($item['refType'] != 'Milestone'){
          $top = 'top:'.((20*$nbRow)+$nbRow).'px;';
          $width = round(dayDiffDates($item['startDate'], $item['endDate']))+1;
          $width = ((($topUnit*$ratio)*$width)/$topUnit)-1;
          $color = ($pe->color)?$pe->color:'var(--color-light)';
          $fontColor = '#3a3a3a';
          $itemToDraw[$nbRow][$date][$wbs] = '<div style="border-left:1px solid white;border-radius:3px;position:absolute;left:'.$left.'px;'.$top.'width:'.$width.'px;height:20px;background:'.$color.';overflow:hidden;cursor:pointer;" title="'.$itemName.' ( '.htmlFormatDate($item['startDate']).' - '.htmlFormatDate($item['endDate']).' )"
          oncontextmenu="event.preventDefault();openTimelineContextMenu('.$idItem.','.$item['refId'].',\''.$item['refType'].'\');" onclick="runScript(\''.$item['refType'].'\','.$item['refId'].','.$idItem.');">';
          $itemToDraw[$nbRow][$date][$wbs] .= '  <div style="float:left;overflow:hidden;white-space:nowrap;font-weight: bold;margin: 5px 0px 0px 7px;font-size: 7pt;color:'.$fontColor.'">'.$itemName.'</div>';
          $itemToDraw[$nbRow][$date][$wbs] .= '  <div style="float:left;overflow:hidden;white-space:nowrap;margin: 5px 0px 0px 10px;font-size: 7pt;color:'.$fontColor.';">'.htmlFormatDate($item['startDate']).' - '.htmlFormatDate($item['endDate']).'</div>';
          $itemToDraw[$nbRow][$date][$wbs] .= '  <input class="hiddenTimelineTask" type="hidden" id="TimelineItemTask_'.$idItem.'" name="TimelineItemTask_'.$item['refType'].'"/>';
          $itemToDraw[$nbRow][$date][$wbs] .= '</div>';
        }else{
          $top = '29px';
          $milestoneToDraw[$nbRow][$date][$wbs] = '<div style="position:absolute;left:'.$left.'px;top:'.$top.';cursor:pointer;z-index:99;" title="'.$itemName.' ( '.htmlFormatDate($item['startDate']).' )"
          oncontextmenu="event.preventDefault();openTimelineContextMenu('.$idItem.','.$item['refId'].',\''.$item['refType'].'\');" onclick="runScript(\''.$item['refType'].'\','.$item['refId'].','.$idItem.');">';
          $milestoneToDraw[$nbRow][$date][$wbs] .= '  <div style="top: -20px;left: 7px;font-weight: bold;font-size: 9px;position: absolute;white-space:nowrap;transform: translateX(-50%);">'.$itemName.'</div>';
          $milestoneToDraw[$nbRow][$date][$wbs] .= '  <div style="top: -10px;left: 7px;width: 2px;height:20px;background: black;position: absolute;"></div>';
          $milestoneToDraw[$nbRow][$date][$wbs] .= '  <div style="font-size: 15pt;color: black;">◊</div>';
          $milestoneToDraw[$nbRow][$date][$wbs] .= '  <input class="hiddenTimelineTask" type="hidden" id="TimelineItemTask_'.$idItem.'" name="TimelineItemTask_'.$item['refType'].'"/>';
          $milestoneToDraw[$nbRow][$date][$wbs] .= '</div>';
        }
      }
    }
  }
  ksort($itemToDraw);
  foreach ($itemToDraw as $row=>$dateList){
    foreach ($dateList as $date=>$wbsList){
      foreach ($wbsList as $wbs=>$item){
        if($maxRow){
          if($row < $maxRow){
            echo $item;
          }else{
            continue;
          }
        }else{
          echo $item;
        }
      }
    }
  }
  echo '</div>';
  foreach ($milestoneToDraw as $row=>$dateList){
    foreach ($dateList as $date=>$wbsList){
      foreach ($wbsList as $wbs=>$item){
        if($maxRow){
          if($row < $maxRow){
            echo $item;
          }else{
            continue;
          }
        }else{
          echo $item;
        }
      }
    }
  }
  echo '</div>';
?>
