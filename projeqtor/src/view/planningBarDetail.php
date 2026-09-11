<?php
include_once "../tool/projeqtor.php";
$class=null;
if (isset($_REQUEST['class'])) {
  $class=$_REQUEST['class'];
}
Security::checkValidClass($class);
if ($class=='Replan' or $class=='Construction' or $class=='Fixed') {
  $class='Project';
}
$id=null;
if (isset($_REQUEST['id'])) {
  $id=$_REQUEST['id'];
}
if ($class!='PeriodicMeeting') Security::checkValidId($id);

echo '<input type="hidden" id="planningBarDetailObjectClass" name="planningBarDetailObjectClass" value="'.$class.'" />';
echo '<input type="hidden" id="planningBarDetailObjectId" name="planningBarDetailObjectId" value="'.$id.'" />';

$scale='day';
if (isset($_REQUEST['scale'])) {
  $scale=$_REQUEST['scale'];
}
if ($scale!='day' and $scale!='week' and $scale!='month' and $scale!='quarter') {
  echo '<div style="background-color:#FFF0F0;padding:3px;border:1px solid #E0E0E0;">'.i18n('ganttDetailScaleError');
  echo drawCloseButton(13, '#FFF0F0', '#E0E0E0');
  echo "</div>";
  return;
}
$objectClassManual=RequestHandler::getValue('objectClassManual');
if ($objectClassManual=='ResourcePlanning' and $class!='PeriodicMeeting') {
  $idAssignment=RequestHandler::getId('idAssignment');
}

$dates=array();
$work=array();
$weeks=array();
$maxCapacity=array();
$minCapacity=array();
$maxSurbooking=array();
$minSurbooking=array();
$ressAll=array();
$excludedAssKey=array();
$start=null;
$end=null;
$resourceList=array(0=>0);
$codeBlue = '#2e75bd';
$codeGreen= '#50bb50';
$codeRed='#bb5050';
$codeDarkGreen = '#114e11';
$gradientGreen = "repeating-linear-gradient(45deg, $codeGreen, $codeGreen 2.5%, transparent 5%, transparent 10%)";
$codeDarkRed ='#8B2525';
$gradientRed = "repeating-linear-gradient(45deg, $codeRed, $codeRed 2.5%, transparent 5%, transparent 10%)";
$surbookedColor='#dca83a'; // #f4bf42 #d4a430

if ($class=='Resource' or $class=='ResourceTeam' or $class=='PeriodicMeeting') {
  echo '<input type="hidden" id="noDataToDisplay" name="noDataToDisplay" value="true" />';
  echo '<div style="background-color:#FFF0F0;padding:3px;border:1px solid #E0E0E0;">'.i18n('noDataToDisplay');
  echo drawCloseButton(13, '#FFF0F0', '#E0E0E0');
  echo "</div>";
  return;
}
$crit=array('refType'=>$class, 'refId'=>$id);

if (!class_exists($class.'PlanningElement')) {
  echo "";
  return;
}
$pe=SqlElement::getSingleSqlElementFromCriteria($class.'PlanningElement', $crit);
if ($pe->assignedWork==0 and $pe->leftWork==0 and $pe->realWork==0) {
  echo '<input type="hidden" id="noDataToDisplay" name="noDataToDisplay" value="true" />';
  echo '<div style="background-color:#FFF0F0;padding:3px;border:1px solid #E0E0E0;">'.i18n('noDataToDisplay');
  echo drawCloseButton(13, '#FFF0F0', '#E0E0E0');
  echo "</div>";
  return;
}
// $modeName='id'pq_strtolower($class.'PlanningMode');
$mode=SqlList::getFieldFromId('PlanningMode', $pe->idPlanningMode, 'code');
if ($objectClassManual!='ResourcePlanning' and $mode=='REGUL' and $pe->realStartDate and !$pe->realEndDate and $pe->validatedEndDate>$pe->plannedEndDate) {
  $end=$pe->validatedEndDate;
} else if ($objectClassManual!='ResourcePlanning' and $mode=='REGUL' and !$pe->realEndDate and $pe->plannedEndDate>$pe->validatedEndDate) {
  $end=$pe->plannedEndDate;
}
if ($pe->realEndDate) $end=$pe->realEndDate;
if ($objectClassManual=='ResourcePlanning') {
  $crit=array('refType'=>$class, 'refId'=>$id, 'idAssignment'=>$idAssignment);
}

$hideAssignationWithoutLeftWork=(Parameter::getUserParameter('hideAssignationWihtoutLeftWork')=='1')?true:false;
$wk=new Work();
$wkLst=$wk->getSqlElementsFromCriteria($crit);
foreach ($wkLst as $wk) {
  $dates[$wk->workDate]=$wk->workDate;
  if (!$start or $start>$wk->workDate) $start=$wk->workDate;
  if (!$end or $end<$wk->workDate) $end=$wk->workDate;
  $keyAss=$wk->idAssignment.'#'.$wk->idResource;
  $resourceList[$keyAss]=$wk->idResource;
  if (!isset($work[$keyAss])) $work[$keyAss]=array();
  if (!isset($work[$keyAss]['resource'])) {
    $ress=new ResourceAll($wk->idResource);
    $ressAll[$keyAss]=$ress;
    $work[$keyAss]['capacity']=($ress->capacity>1)?$ress->capacity:'1';
    $work[$keyAss]['idAssignment']=$wk->idAssignment;
    $ass=new Assignment($wk->idAssignment);
    $work[$keyAss]['function']=SqlList::getNameFromId('Role', $ass->idRole);
    $work[$keyAss]['resource']=$ress->name;
    $work[$keyAss]['idResource']=$ress->id;
    if ($ress->isResourceTeam) {
      $work[$keyAss]['capacity']=($ass->capacity>1)?$ass->capacity:'1';
    }
    if ($work[$keyAss]['capacity']>1) {
      $work[$keyAss]['resource'].='<span style="font-size:65%;color:grey;"> ('.i18n('max').' '.htmlDisplayNumericWithoutTrailingZeros($work[$keyAss]['capacity']).' '.i18n('shortDays').')</span>';
    }
  }
  $work[$keyAss][$wk->workDate]=array('work'=>$wk->work, 'type'=>'real');
  $maxCapacity[$keyAss]=$work[$keyAss]['capacity'];
  $minCapacity[$keyAss]=$work[$keyAss]['capacity'];
  $maxSurbooking[$keyAss]=0;
  $minSurbooking[$keyAss]=0;
  if ($hideAssignationWithoutLeftWork==1) {
    $ass=new Assignment($wk->idAssignment);
    if ($ass->leftWork==0) {
      unset($work[$keyAss]);
      $excludedAssKey[$keyAss]=$ass->idResource;
    }
  }
}
$wk=new PlannedWork();
$wkLst=$wk->getSqlElementsFromCriteria($crit);
foreach ($wkLst as $wk) {
  if ($pe->realEndDate and $wk->workDate>$pe->realEndDate) continue; // Do not take into account planned work over existing real end date - due to not replanned work
  $dates[$wk->workDate]=$wk->workDate;
  if (!$start or $start>$wk->workDate) $start=$wk->workDate;
  if (!$end or $end<$wk->workDate) $end=$wk->workDate;
  $keyAss=$wk->idAssignment.'#'.$wk->idResource;
  $resourceList[$keyAss]=$wk->idResource;
  if (!isset($work[$keyAss])) $work[$keyAss]=array();
  if (!isset($work[$keyAss]['resource'])) {
    $ress=new ResourceAll($wk->idResource);
    $ressAll[$keyAss]=$ress;
    $work[$keyAss]['capacity']=($ress->capacity>1)?$ress->capacity:'1';
    $work[$keyAss]['idAssignment']=$wk->idAssignment;
    $ass=new Assignment($wk->idAssignment);
    $work[$keyAss]['function']=SqlList::getNameFromId('Role', $ass->idRole);
    $work[$keyAss]['resource']=$ress->name;
    $work[$keyAss]['idResource']=$ress->id;
    if ($ress->isResourceTeam) {
      $work[$keyAss]['capacity']=($ass->capacity>1)?$ass->capacity:'1';
    }
    if ($work[$keyAss]['capacity']>1) {
      $work[$keyAss]['resource'].='<span style="font-size:65%;color:grey;"> ('.i18n('max').' '.htmlDisplayNumericWithoutTrailingZeros($work[$keyAss]['capacity']).' '.i18n('shortDay').')</span>';
    }
  }
  if (!isset($work[$keyAss][$wk->workDate])) {
    $work[$keyAss][$wk->workDate]=array(
        'work'=>$wk->work, 
        'type'=>'planned', 
        'surbooked'=>$wk->surbooked, 
        'surbookedWork'=>$wk->surbookedWork);
  }
  $maxCapacity[$keyAss]=$work[$keyAss]['capacity'];
  $minCapacity[$keyAss]=$work[$keyAss]['capacity'];
  $maxSurbooking[$keyAss]=0;
  $minSurbooking[$keyAss]=0;
  if ($hideAssignationWithoutLeftWork==1) {
    $ass=new Assignment($wk->idAssignment);
    if ($ass->leftWork==0) {
      unset($work[$keyAss]);
      $excludedAssKey[$keyAss]=$ass->idResource;
    }
  }
}
if (count($work)==0) {
  echo '<input type="hidden" id="noDataToDisplay" name="noDataToDisplay" value="true" />';
  echo '<div style="background-color:#FFF0F0;padding:3px;border:1px solid #E0E0E0;">'.i18n('noDataToDisplay');
  echo drawCloseButton(13, '#FFF0F0', '#E0E0E0');
  echo "</div>";
  return;
}
if ($pe->plannedEndDate>$end and !$pe->realEndDate and $objectClassManual!='ResourcePlanning') $end=$pe->plannedEndDate;
if ($pe->plannedStartDate<$start and !$pe->realStartDate and $objectClassManual!='ResourcePlanning')$start=$pe->plannedStartDate;
$where="idProject in ".Project::getAdminitrativeProjectList();
$act=new Activity();
$actList=$act->getSqlElementsFromCriteria(null, null, $where);
$actListId=array(0=>0);
foreach ($actList as $activity) {
  $actListId[$activity->id]=$activity->id;
}
$wk=new Work();
$where="refType='Activity' and refId in (".implode(',', $actListId).") and idResource in (".implode(',', $resourceList).")";
$actWorkList=$wk->getSqlElementsFromCriteria(null, null, $where);
$resourceList=array_flip($resourceList);
foreach ($actWorkList as $wk) {
  if ($start>$wk->workDate) continue;
  if ($end<$wk->workDate) continue;
  $dates[$wk->workDate]=$wk->workDate;
  $keyAss=$resourceList[$wk->idResource];
  if (!isset($work[$keyAss])) $work[$keyAss]=array();
  if (!isset($work[$keyAss]['resource'])) {
    $ress=new ResourceAll($wk->idResource);
    $ressAll[$keyAss]=$ress;
    $work[$keyAss]['capacity']=($ress->capacity>1)?$ress->capacity:'1';
    $work[$keyAss]['idAssignment']=$wk->idAssignment;
    $ass=new Assignment($wk->idAssignment);
    $work[$keyAss]['function']=SqlList::getNameFromId('Role', $ass->idRole);
    $work[$keyAss]['resource']=$ress->name;
    $work[$keyAss]['idResource']=$ress->id;
    if ($ress->isResourceTeam) {
      $ass=new Assignment($wk->idAssignment);
      $work[$keyAss]['capacity']=($ass->capacity>1)?$ass->capacity:'1';
    }
    if ($work[$keyAss]['capacity']>1) {
      $work[$keyAss]['resource'].='<span style="font-size:65%;color:grey;"> ('.i18n('max').' '.htmlDisplayNumericWithoutTrailingZeros($work[$keyAss]['capacity']).' '.i18n('shotDay').')</span>';
    }
  }
  
  if (isset($work[$keyAss][$wk->workDate])) {
    if ($work[$keyAss][$wk->workDate]['type']=='real' or $work[$keyAss][$wk->workDate]['type']=='real_administrative' or $work[$keyAss][$wk->workDate]['type']=='administrative') {
      $admWord=$wk->work;
      if (isset($work[$keyAss][$wk->workDate]['adm'])) $admWord+=$work[$keyAss][$wk->workDate]['adm'];
      $work[$keyAss][$wk->workDate]=array(
          'work'=>$work[$keyAss][$wk->workDate]['work'], 
          'type'=>'real_administrative', 
          'real'=>$work[$keyAss][$wk->workDate]['work'], 
          'adm'=>$admWord, 
          'planned'=>0);
    } else {
      // $suboked=(isset($work[$keyAss][$wk->workDate]['surbooked']) and $work[$keyAss][$wk->workDate]['surbooked'])?($work[$keyAss][$wk->workDate]['surbookedWork']-$wk->work ):'';
      $suboked=(isset($work[$keyAss][$wk->workDate]['surbooked']) and $work[$keyAss][$wk->workDate]['surbooked'])?($work[$keyAss][$wk->workDate]['surbookedWork']):0;
      $admWord=$wk->work;
      if (isset($work[$keyAss][$wk->workDate]['adm'])) $admWord+=$work[$keyAss][$wk->workDate]['adm'];
      $work[$keyAss][$wk->workDate]=array(
          'work'=>$work[$keyAss][$wk->workDate]['work'], 
          'type'=>'planned_administrative', 
          'real'=>0, 
          'adm'=>$admWord, 
          'planned'=>$work[$keyAss][$wk->workDate]['work'], 
          'surbooked'=>(isset($work[$keyAss][$wk->workDate]['surbooked']))?$work[$keyAss][$wk->workDate]['surbooked']:0, 
          'surbookedWork'=>$suboked);
    }
    $maxCapacity[$keyAss]=$work[$keyAss]['capacity'];
    $minCapacity[$keyAss]=$work[$keyAss]['capacity'];
    $maxSurbooking[$keyAss]=0;
    $minSurbooking[$keyAss]=0;
  } else {
    $work[$keyAss][$wk->workDate]=array('work'=>$wk->work, 'type'=>'administrative');
    $maxCapacity[$keyAss]=$work[$keyAss]['capacity'];
    $minCapacity[$keyAss]=$work[$keyAss]['capacity'];
    $maxSurbooking[$keyAss]=0;
    $minSurbooking[$keyAss]=0;
  }
  if ($hideAssignationWithoutLeftWork==1 and isset($excludedAssKey[$keyAss])) {
    unset($work[$keyAss]);
  }
}
if ($mode=='RECW') { // RECW
  $start=$pe->plannedStartDate;
  $end=$pe->plannedEndDate;
}
if (!$start or !$end) {
  echo '<input type="hidden" id="noDataToDisplay" name="noDataToDisplay" value="true" />';
  if ($pe->elementary) {
    if ($pe->paused) echo '<div style="background-color:#FFF0F0;padding:3px;border:1px solid #E0E0E0;">'.i18n('noDataToDisplay').'<br/>'.i18n('msgPausedActivity');
    else if ($hideAssignationWithoutLeftWork) echo '<div style="background-color:#FFF0F0;padding:3px;border:1px solid #E0E0E0;">'.i18n('noDataToDisplay');
    else echo '<div style="background-color:#FFF0F0;padding:3px;border:1px solid #E0E0E0;">'.i18n('noDataToDisplay').'<br/>'.i18n('planningCalculationRequired');
    echo drawCloseButton(13, '#FFF0F0', '#E0E0E0');
    echo "</div>";
  } else {
    echo '<div style="background-color:#FFF0F0;padding:3px;border:1px solid #E0E0E0;">'.i18n('noDataToDisplay');
    echo drawCloseButton(13, '#FFF0F0', '#E0E0E0');
    echo "</div>";
    return;
  }
}
if ($objectClassManual!='ResourcePlanning') {
  if ($pe->elementary==0 && $pe->plannedStartDate && $pe->plannedStartDate<$start) {
    $start=$pe->plannedStartDate; // PBER : Changed due to unconsistency with display
  }
}
$variableCapacity=array();
$surbooking=array();
$dt=$start;
while ($dt<=$end) {
  if (!isset($dates[$dt])) {
    $dates[$dt]=$dt;
  }
  foreach ($ressAll as $keyAss=>$ress) {
    if (!isset($variableCapacity[$keyAss])) $variableCapacity[$keyAss]=array();
    if (!isset($surbooking[$keyAss])) $surbooking[$keyAss]=array();
    $capa=$ress->getCapacityPeriod($dt);
    $surbook=$ress->getSurbookingCapacity($dt, true);
    if (!$ress->isResourceTeam) {
      if (!isset($maxCapacity[$keyAss])) $maxCapacity[$keyAss]=$capa;
      if (!isset($minCapacity[$keyAss])) $minCapacity[$keyAss]=$capa;
      if ($capa!=$ress->capacity) {
        $variableCapacity[$keyAss][$dt]=$capa;
      }
      if ($capa>$maxCapacity[$keyAss]) $maxCapacity[$keyAss]=$capa;
      if ($capa<$minCapacity[$keyAss]) $minCapacity[$keyAss]=$capa;
    }
    if (!isset($maxSurbooking[$keyAss])) $maxSurbooking[$keyAss]=0;
    if (!isset($minSurbooking[$keyAss])) $minSurbooking[$keyAss]=0;
    if ($surbook>$maxSurbooking[$keyAss]) $maxSurbooking[$keyAss]=$surbook;
    if ($surbook<$minSurbooking[$keyAss]) $minSurbooking[$keyAss]=$surbook;
  }
  $dt=addDaysToDate($dt, 1);
}
ksort($dates);

echo drawCloseButton(13);

if ($scale=='day' or $scale=='week') {
  $width=20;
  echo '<table id="planningBarDetailTable" style="height:'.(count($work)*22).'px;background-color:#FFFFFF;border-collapse: collapse;marin:0;padding:0;width:100%">';
  $heightNormal=20;
  $heightCapacity=20;
  usort($work, 'sortByResourceName');
  
  if (PlanningMode::isFixedDuration($pe->idPlanningMode)) {
    if (intval($pe->validatedDuration)>0 and $pe->plannedDuration-$pe->validatedDuration>0) {
      $peEndDateOver=addWorkDaysToDate($pe->plannedStartDate, $pe->validatedDuration, $pe->idProject);
    }
  }
  
  $isColorBlind=Parameter::getUserParameter('colorBlindPlanning');
  foreach ($work as $resWork) {
    $keyAss=$resWork['idAssignment'].'#'.$resWork['idResource'];
    //if (!isset($ressAll[$keyAss])) continue;
    $resObj=$ressAll[$keyAss];
    echo '<tr style="height:20px;border:1px solid #505050;">';
    $overCapa=null;
    $underCapa=null;
    $surbooked=null;
    foreach ($dates as $dt) {
      $color="#ffffff";
      $tdColor="";
      $height=20;
      $w=0;
      $heightSurbooked=0;
      $capacityTop=$maxCapacity[$keyAss]; // $resWork['capacity'];
      if (!isset($variableCapacity[$keyAss][$dt])) {
        $heightNormal=20;
        $heightCapacity=20;
      } else {
        $tmp=$ressAll[$keyAss];
        if ($variableCapacity[$keyAss][$dt]>$tmp->capacity) {
          if (!$overCapa or $variableCapacity[$keyAss][$dt]>$overCapa) {
            $overCapa=$variableCapacity[$keyAss][$dt];
          }
        } else {
          if (!$underCapa or $variableCapacity[$keyAss][$dt]<$underCapa) {
            $underCapa=$variableCapacity[$keyAss][$dt];
          }
        }
        $heightNormal=round(20*$resWork['capacity']/$capacityTop, 0);
        $heightCapacity=round(20*$variableCapacity[$keyAss][$dt]/$capacityTop, 0);
      }
      if ($capacityTop==0) $capacityTop=1;
      if (isset($resWork[$dt])) {
        $overLimitedFixedDuration=false;
        if (isset($peEndDateOver) and $peEndDateOver<$dt) {
          $overLimitedFixedDuration=true;
        }
        $w=$resWork[$dt]['work'];
        if ((!$pe->validatedEndDate or $dt<=$pe->validatedEndDate) and !$overLimitedFixedDuration) {
          if ($resWork[$dt]['type']=='real_administrative' or $resWork[$dt]['type']=='planned_administrative') {
            $color=($resWork[$dt]['real']!=0)? $codeDarkGreen :"#50BB50";
            if ($isColorBlind=='YES') $color=($resWork[$dt]['real']!=0)?"#50BB50":"#67ff00";
          } else {
            $color=($resWork[$dt]['type']=='real')? $codeDarkGreen :"#50BB50";
            if ($isColorBlind=='YES') $color=($resWork[$dt]['type']=='real')?"#50BB50":"#67ff00";
          }
        } else {
          if ($resWork[$dt]['type']=='real_administrative' or $resWork[$dt]['type']=='planned_administrative') {
            $color=($resWork[$dt]['type']=='real_administrative')? $codeDarkRed :"#BB5050";
            if ($isColorBlind=='YES') $color=($resWork[$dt]['type']=='real_administrative')?"#63226b":"#9a3ec9";
          } else {
            $color=($resWork[$dt]['type']=='real')? $codeDarkRed :"#BB5050";
            if ($isColorBlind=='YES') $color=($resWork[$dt]['type']=='real')?"#63226b":"#9a3ec9";
          }
        }
        if ($resWork[$dt]['type']=='administrative') {
          $color=($isColorBlind=='YES')?"#5e8cba": $codeBlue;
        }
        if (isset($resWork[$dt]) and ($resWork[$dt]['type']=='planned_administrative' or $resWork[$dt]['type']=='real_administrative')) {
          $val=($resWork[$dt]['planned']>0 and $resWork[$dt]['real']==0)?$resWork[$dt]['planned']:$resWork[$dt]['real'];
          $valAmd=$resWork[$dt]['adm'];
          $heightAdm=round($valAmd*20/$capacityTop, 0);
          $heightRealPlanned=round($val*20/$capacityTop, 0);
        }
        if (isset($resWork[$dt]['surbooked']) and $resWork[$dt]['surbooked']==1) {
          $sb=$resWork[$dt]['surbookedWork'];
          // PBER #7059
          $height=($w-$sb>0)?round(($w-$sb)*20/$capacityTop, 0):0;
          // $height=round(($w)*20/$capacityTop,0);
          $heightSurbooked=round($sb*20/$capacityTop, 0);
        } else {
          $height=round($w*20/$capacityTop, 0);
        }
      }
      if (isOffDay($dt, SqlList::getFieldFromId('ResourceAll', $resWork['idResource'], 'idCalendarDefinition'))) {
        // Gautier #6103 Gantt bar does not show the real work
        $tdColor="background-color:#dddddd;";
        if ($color=='#ffffff') {
          $color="#dddddd";
        }
      }
      $showBorder=false;
      if ($scale=='day') $showBorder=true;
      if ($scale=='week' and date('w', strtotime($dt))==0) $showBorder=true;
      $backgroundImage = ($color == $codeDarkGreen) ? $gradientGreen : (($color == $codeDarkRed) ? $gradientRed : "none");
      echo '<td style="padding:0;width:'.$width.'px;'.(($showBorder)?'border-right:1px solid #eeeeee;':'').'position:relative;'.$tdColor.'">';
      if (isset($resWork[$dt]) and ($resWork[$dt]['type']=='planned_administrative' or $resWork[$dt]['type']=='real_administrative')) {
        $bottomAdmin=(isset($heightSurbooked) and $heightSurbooked>0)?$heightSurbooked:$heightRealPlanned;
        echo '<div style="display: block; background-color: ' . $codeBlue . '; position: absolute; bottom: ' . $bottomAdmin . 'px; left: 0px; width: 100%; height: ' . $heightAdm . 'px;"></div>';
        echo '<div style="display:block;background-color:'.$color.'; background-image: ' .$backgroundImage. ' ; position:absolute;bottom:0px;left:0px;width:100%;height:'.$heightRealPlanned.'px;"></div>';
      } else {
        echo '<div style="border-top:1px solid #555555;display:block;background-color:'.$color.'; background-image: '. $backgroundImage .' ;position:absolute;bottom:0px;left:0px;width:100%;height:'.$height.'px;"></div>';
      }
      if ($heightSurbooked>0) {
        echo '<div style="display:block;background-color:'.$surbookedColor.';position:absolute;bottom:'.$height.'px;left:0px;width:100%;height:'.$heightSurbooked.'px;border-top:1px solid grey"></div>';
      }
      if ($maxCapacity[$keyAss]!=$resWork['capacity'] or $minCapacity[$keyAss]!=$resWork['capacity']) {
        echo '<div style="display:block;background-color:transparent;position:absolute;bottom:0px;left:0px;width:100%;border-top:1px solid grey;height:'.$heightNormal.'px;"></div>';
      }
      if ($heightNormal!=$heightCapacity and isset($variableCapacity[$keyAss][$dt])) {
        $colorCapa='1px solid red';
        if ($variableCapacity[$keyAss][$dt]==0) $colorCapa='4px solid #9933CC';
        echo '<div style="display:block;background-color:transparent;position:absolute;bottom:0px;left:0px;width:100%;border-top:'.$colorCapa.';height:'.$heightCapacity.'px;"></div>';
      }
      echo '</td>';
    }
    echo '<td style="border-left:1px solid #505050;">';
    echo '<div style="width:200px; max-width:200px;overflow:hidden; text-align:left;max-height:20px;">&nbsp;';
    if ($overCapa) echo '<div style="float:right;padding-right:3px">&nbsp;<img style="width:10px" src="../view/img/arrowUp.png" />&nbsp;'.htmlDisplayNumericWithoutTrailingZeros($overCapa).'</div>';
    if ($underCapa) echo '<div style="float:right">&nbsp;<img style="width:10px" src="../view/img/arrowDown.png" />&nbsp;'.htmlDisplayNumericWithoutTrailingZeros($underCapa).'</div>';
    if ($maxSurbooking[$keyAss]!=0 or $minSurbooking[$keyAss]!=0) {
      if ($maxSurbooking[$keyAss]) echo '<div style="float:right;padding-right:3px;">&nbsp;<span style="color:'.$surbookedColor.';font-weight:bold">+</span>&nbsp;'.htmlDisplayNumericWithoutTrailingZeros($maxSurbooking[$keyAss]).'</div>';
      else if ($minSurbooking[$keyAss]) echo '<div style="float:right;padding-right:3px;">&nbsp;<span style="color:'.$surbookedColor.';font-weight:bold">-</span>&nbsp;'.htmlDisplayNumericWithoutTrailingZeros((-1)*$minSurbooking[$keyAss]).'</div>';
    }
    $function='<div style="text-shadow:0;position:absolute;top:-4px;overflow:show;z-index:9999;right:3px;font-size:65%;color:var(--color-medium)">'.$resWork['function'].'</div>';
    echo '</div><div style="width:200px;position:absolute;left:10px;margin-top:-15px;text-shadow: 1px 1px 2px white;white-space:nowrap;" class="planningBarDetailResName"><div style="padding-left:4px;overflow:hidden;width:200px">'.$resWork['resource'].'&nbsp;</div>'.$function.'</div></td>';
    echo '</tr>';
  }
  echo '</table>';
}

if ($scale=='month' or $scale=='quarter') {
  $weeks=array();
  $width=20;
  $maxDaysPerWeek=0;
  echo '<table id="planningBarDetailTable" style="height:'.(count($work)*22).'px;background-color:#FFFFFF;border-collapse: collapse;margin:0;padding:0;width:100%">';
  $heightNormal=20;
  $heightCapacity=20;
  usort($work, 'sortByResourceName');
  if (PlanningMode::isFixedDuration($pe->idPlanningMode)) {
    if ($pe->plannedDuration-$pe->validatedDuration>0) {
      $peEndDateOver=addWorkDaysToDate($pe->plannedStartDate, $pe->validatedDuration, $pe->idProject);
    }
  }
  $isColorBlind=Parameter::getUserParameter('colorBlindPlanning');
  foreach ($work as $resWork) {
    $keyAss=$resWork['idAssignment'].'#'.$resWork['idResource'];
    if (!isset($ressAll[$keyAss])) continue;
    $resObj=$ressAll[$keyAss];
    echo '<tr style="height:20px;border:1px solid #505050;">';
    $overCapa=null;
    $underCapa=null;
    $surbooked=null;
    $resourceCapacity=0;
    $weekData=array('color'=>array(), 'tdColor'=>array(), 'height'=>array(), 'heightSurbooked'=>array(), 'capacityTop'=>array());
    $currentWeek=null;
    $nbDaysInWeek=0;
    $weekHasOpenDay=false;
    foreach ($dates as $dt) {
      $color="#ffffff";
      $tdColor="";
      $height=20;
      $w=0;
      $heightSurbooked=0;
      $capacityTop=$maxCapacity[$keyAss];
      if (!isset($variableCapacity[$keyAss][$dt])) {
        $heightNormal=20;
        $heightCapacity=20;
      } else {
        $tmp=$ressAll[$keyAss];
        if ($variableCapacity[$keyAss][$dt]>$tmp->capacity) {
          if (!$overCapa or $variableCapacity[$keyAss][$dt]>$overCapa) {
            $overCapa=$variableCapacity[$keyAss][$dt];
          }
        } else {
          if (!$underCapa or $variableCapacity[$keyAss][$dt]<$underCapa) {
            $underCapa=$variableCapacity[$keyAss][$dt];
          }
        }
        $heightNormal=round(20*$resWork['capacity']/$capacityTop, 0);
        $heightCapacity=round(20*$variableCapacity[$keyAss][$dt]/$capacityTop, 0);
      }
      if ($capacityTop==0) $capacityTop=1;
      $dayToCount=false;
      if (isset($resWork[$dt])) {
        $overLimitedFixedDuration=false;
        if (isset($peEndDateOver) and $peEndDateOver<$dt) {
          $overLimitedFixedDuration=true;
        }
        $w=$resWork[$dt]['work'];
        if ((!$pe->validatedEndDate or $dt<=$pe->validatedEndDate) and !$overLimitedFixedDuration) {
          if ($resWork[$dt]['type']=='real_administrative' or $resWork[$dt]['type']=='planned_administrative') {
            $color=($resWork[$dt]['real']!=0)? $codeDarkGreen :"#50BB50";
            if ($isColorBlind=='YES') $color=($resWork[$dt]['real']!=0)?"#50BB50":"#67ff00";
            $dayToCount=true;
          } else {
            $color=($resWork[$dt]['type']=='real')? $codeDarkGreen :"#50BB50";
            if ($isColorBlind=='YES') $color=($resWork[$dt]['type']=='real')?"#50BB50":"#67ff00";
            $dayToCount=true;
          }
        } else {
          if ($resWork[$dt]['type']=='real_administrative' or $resWork[$dt]['type']=='planned_administrative') {
            $color=($resWork[$dt]['type']=='real_administrative')? $codeDarkRed :"#BB5050";
            if ($isColorBlind=='YES') $color=($resWork[$dt]['type']=='real_administrative')?"#63226b":"#9a3ec9";
            $dayToCount=true;
          } else {
            $color=($resWork[$dt]['type']=='real')? $codeDarkRed :"#BB5050";
            if ($isColorBlind=='YES') $color=($resWork[$dt]['type']=='real')?"#63226b":"#9a3ec9";
            $dayToCount=true;
          }
        }
        if ($resWork[$dt]['type']=='administrative') {
          $color=($isColorBlind=='YES')?"#5e8cba":$codeBlue;
          //$dayToCount=true;
        }
        if (isset($resWork[$dt]) and ($resWork[$dt]['type']=='planned_administrative' or $resWork[$dt]['type']=='real_administrative')) {
          $val=($resWork[$dt]['planned']>0 and $resWork[$dt]['real']==0)?$resWork[$dt]['planned']:$resWork[$dt]['real'];
          $valAmd=$resWork[$dt]['adm'];
          $heightAdm=round($valAmd*20/$capacityTop, 0);
          $heightRealPlanned=round($val*20/$capacityTop, 0);
          //$dayToCount=true;
        }
        if (isset($resWork[$dt]['surbooked']) and $resWork[$dt]['surbooked']==1) {
          $sb=$resWork[$dt]['surbookedWork'];
          // PBER #7059
          $height=($w-$sb>0)?round(($w-$sb)*20/$capacityTop, 0):0;
          // $height=round(($w)*20/$capacityTop,0);
          $heightSurbooked=round($sb*20/$capacityTop, 0);
        } else {
          $height=round($w*20/$capacityTop, 0);
        }
        if ($w==0) $height=0;
      } else {
        $height=0;
      }

      $weekNumber=pq_substr($dt, 0, 4).getWeekNumber($dt);
      if ($weekNumber!=$currentWeek) {
        $weekHasOpenDay=false;
        if ($currentWeek!==null) {
          //echo '</div>';
          $weeks[$currentWeek][]=$weekData;
        }       
        //echo '<div class="week-container" style="display:flex;">';
        $weekData=array();
        $currentWeek=$weekNumber;
        $nbDaysInWeek=0;
      }
      if ($dayToCount==true or ! isOffDay($dt, SqlList::getFieldFromId('ResourceAll', $resWork['idResource'], 'idCalendarDefinition')) ) {
        $nbDaysInWeek++;
      }
      $weekData['nbDays']=$nbDaysInWeek;
      if (isOpenDay($dt, SqlList::getFieldFromId('ResourceAll', $resWork['idResource'], 'idCalendarDefinition') ) ) $weekHasOpenDay=true;
      //$weekData['nbDays']=$nbDaysInWeek;
      $weekData['color'][]=$color;
      $weekData['tdColor'][]=$tdColor;
      $weekData['height'][]=$height;
      $weekData['heightSurbooked'][]=$heightSurbooked;
      $weekData['capacityTop'][]=$capacityTop;
      $weekData['hasOpenDay']=$weekHasOpenDay;
    }
    $nbDaysInWeek++;
    $weekData['nbDays']=$nbDaysInWeek;
    $weeks[$currentWeek][]=$weekData;
    foreach ($weeks as $weekNumber=>$weekData) {
      $totalHeight=0;
      $chosenColor=null;
      $totalHeightSurbooked=0;
      $totalCapacityTop=0;
      $totalHeightAdmin=0;
      $nbDaysInWeek=5;
      $hasBB5050=false;
      $tdColor="";
      foreach ($weekData as $dayData) {
        // $dayData=$weekData;
        $nbDaysInWeek=$dayData['nbDays'];
        $totalHeightSurbooked+=array_sum($dayData['heightSurbooked']);
        $totalCapacityTop+=array_sum($dayData['capacityTop']);
        $totalHeight+=array_sum($dayData['height']);
        if ($dayData['hasOpenDay']==false) { $tdColor="background-color:#dddddd"; }
        foreach ($dayData['color'] as $idC=>$color) {
          if ($color==='#BB5050') {
            $chosenColor=$color;
            $hasBB5050=true;
            //break 2;
          } else if ($color===$codeBlue) {
            $totalHeightAdmin+=$dayData['height'][$idC];
          }
        }
      }
      $nbWorkDaysInWeek=count($weekData[0]['color']);
      if (!$hasBB5050) {
        $colorCounts=array_count_values(array_merge(...array_column($weekData, 'color')));
        arsort($colorCounts);
        foreach ($colorCounts as $color=>$count) {
          if ($color!=='#ffffff') {
            $chosenColor=$color;
            break;
          }
        }
        if ($chosenColor===null) {
          $chosenColor='#fffffff';
        }
      }
      $averageHeight=($nbDaysInWeek)?($totalHeight-$totalHeightAdmin)/$nbDaysInWeek:0;
      $averageHeightAdmin=($nbDaysInWeek)?$totalHeightAdmin/$nbDaysInWeek:0;
      $finalColorForWeek=$chosenColor;
      $averageHeightSurbooked=($totalHeightSurbooked==0 or ! $nbDaysInWeek)?0:$totalHeightSurbooked/$nbDaysInWeek;
      $averageCapacityTop=($nbDaysInWeek)?$totalCapacityTop/$nbDaysInWeek:0;
      $curWidth=$width*2*$nbWorkDaysInWeek/7;
      //$curWidth=$width;
      $backgroundImage = ($finalColorForWeek == $codeDarkGreen) ? $gradientGreen : (($finalColorForWeek == $codeDarkRed) ? $gradientRed : "none");
      echo '<td style="padding:0;width:'.$curWidth.'px;'.((0 and $scale=='day')?'border-right:1px solid #eeeeee;':'border-right:0;').'position:relative;'.$tdColor.'">';
      if (0 and isset($resWork[$dt]) and ($resWork[$dt]['type']=='planned_administrative' or $resWork[$dt]['type']=='real_administrative')) {
        $bottomAdmin=(isset($averageHeightSurbooked) and $averageHeightSurbooked>0)?$averageHeightSurbooked:$heightRealPlanned;
        echo '<div style="display:block;background-color:' . $codeBlue . ';position:absolute;bottom:' . $bottomAdmin . 'px;left:0px;width:100%;height:' . $heightAdm . 'px;"></div>';
        echo '<div style="display:block;background-color:'.$finalColorForWeek.'; background-image: ' .$backgroundImage. ';position:absolute;bottom:0px;left:0px;width:100%;height:'.$heightRealPlanned.'px;"></div>';
      } else if ($finalColorForWeek!='#fffffff') {
        if ($averageHeightAdmin>0) echo '<div style="display: block; background-color: ' . $codeBlue . ';position: absolute; bottom: 0; left: 0; width: 100%; height: ' . $averageHeightAdmin . 'px;"></div>';
        echo '<div style="border-top:1px solid #555555;display:block;background-color:'.$finalColorForWeek.'; background-image: ' .$backgroundImage. '; position:absolute;bottom:'.$averageHeightAdmin.'px;left:0px;width:100%;height:'.$averageHeight.'px;"></div>';
      } else {       
        echo '<div style="display:block;background-color:'.$finalColorForWeek.'; background-image: ' .$backgroundImage. ';position:absolute;bottom:0px;left:0px;width:100%;height:'.$averageHeight.'px;"></div>';
      }
      if ($averageHeightSurbooked>0) {
        echo '<div style="display:block;background-color:'.$surbookedColor.';position:absolute;bottom:'.$averageHeight.'px;left:0px;width:100%;height:'.$averageHeightSurbooked.'px;"></div>';
      }
      if ($maxCapacity[$keyAss]!=$resWork['capacity'] or $minCapacity[$keyAss]!=$resWork['capacity']) {
        echo '<div style="display:block;background-color:transparent;position:absolute;bottom:0px;left:0px;width:100%;border-top:1px solid grey;height:'.$heightNormal.'px;"></div>';
      }
      if ($heightNormal!=$heightCapacity and isset($variableCapacity[$keyAss][date('Y-m-d',firstDayofWeek(pq_substr($weekNumber,4),pq_substr($weekNumber,0,4)))]) ) {
        $colorCapa='1px solid red';
        if ($variableCapacity[$keyAss][$dt]==0) $colorCapa='4px solid #9933CC';
        echo '<div style="display:block;background-color:transparent;position:absolute;bottom:0px;left:0px;width:100%;border-top:'.$colorCapa.';height:'.$heightCapacity.'px;"></div>';
      }
      echo '</td>';
    }
    echo '<td style="border-left:1px solid #505050;">';
    echo '<div style="width:200px; max-width:200px;overflow:hidden; text-align:left;max-height:20px;">&nbsp;';
    if ($overCapa) echo '<div style="float:right;padding-right:3px">&nbsp;<img style="width:10px" src="../view/img/arrowUp.png" />&nbsp;'.htmlDisplayNumericWithoutTrailingZeros($overCapa).'</div>';
    if ($underCapa) echo '<div style="float:right">&nbsp;<img style="width:10px" src="../view/img/arrowDown.png" />&nbsp;'.htmlDisplayNumericWithoutTrailingZeros($underCapa).'</div>';
    if ($maxSurbooking[$keyAss]!=0 or $minSurbooking[$keyAss]!=0) {
      if ($maxSurbooking[$keyAss]) echo '<div style="float:right;padding-right:3px;">&nbsp;<span style="color:'.$surbookedColor.';font-weight:bold">+</span>&nbsp;'.htmlDisplayNumericWithoutTrailingZeros($maxSurbooking[$keyAss]).'</div>';
      else if ($minSurbooking[$keyAss]) echo '<div style="float:right;padding-right:3px;">&nbsp;<span style="color:'.$surbookedColor.';font-weight:bold">-</span>&nbsp;'.htmlDisplayNumericWithoutTrailingZeros((-1)*$minSurbooking[$keyAss]).'</div>';
    }
    echo '</div><div style="width:200px;position:absolute;left:10px;margin-top:-15px;text-shadow: 1px 1px 2px white;white-space:nowrap;overflow:hidden;" class="planningBarDetailResName">'.$resWork['resource'].'&nbsp;</div></td>';
    
    $weeks=array();
    echo '</div>';
    echo '</tr>';
  }
  
  echo '</table>';
}

function getWeekNumber($date) {
  return date('W', strtotime($date));
}

function sortByResourceName($a, $b) {
  return $a['resource'] <=> $b['resource'];
}

function drawCloseButton($size, $bgColor='white', $borderColor='black') {
  $tabSize=($size*2)-4;
  $tabHeight=$size+4;
  $marge=($size/2)-2;
  $margeHeight=($tabHeight-$size)/2;
  $display=(Parameter::getUserParameter('lockPlanningBarDetail')=='1' or Parameter::getUserParameter('lockPlanningBarDetail')=='')?'':'display:none;';
  $closeButton="<div id='planningBarDetailCloseButton' style='".$display."cursor:pointer;position: absolute;right: 0px;top: -".($tabHeight+1)."px;width:".$tabSize."px;height: ".$tabHeight."px;background-color:".$bgColor.";border-top: 1px solid ".$borderColor.";border-left: 1px solid ".$borderColor.";border-right: 1px solid ".$borderColor.";border-radius: 5px 5px 0px 0px;' onClick='JSGantt.exitBarLink(null, true)'>";
  $closeButton.="<div style='position: absolute;right:".$marge."px;top:".$margeHeight."px;'><span style='width:".$size."px;height:".$size."px;' class='imageColorNewGui'><img style='width:".$size."px;height:".$size."px;' src='images/tabClose.svg' /></span></div>";
  $closeButton.="</div>";
  return $closeButton;
}