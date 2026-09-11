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
 * Presents the list of objects of a given class.
 *
 */
require_once "../tool/projeqtor.php";
include_once('../tool/formatter.php');
scriptLog('   ->/view/resourceSkillView.php');

$ratioPertinence = 0.75;
$notResourceSkillSimple=RequestHandler::getBoolean('notResourceSkillSimple');

$idSkill=(RequestHandler::getValue('listSkillFilter'))?pq_trim(RequestHandler::getValue('listSkillFilter')):pq_trim(getSessionValue('listSkillFilter'));
$idSkillLevel=(RequestHandler::getValue('listSkillLevelFilter'))?pq_trim(RequestHandler::getValue('listSkillLevelFilter')):pq_trim(getSessionValue('listSkillLevelFilter'));
$strictLevelCheck=RequestHandler::getBoolean('strictLevelCheck');
$result=array();
$obj = new ResourceSkill();

if($idSkill){
    $querySelect = " * ";
    $queryFrom = $obj->getDatabaseTableName();
    $queryWhere='idle=0';
  
	$currentLine=$idSkill;
	$skl = new Skill($idSkill, true);
	$parentList = $skl->getTopParentSkillList();
	$subSkill = $skl->getSqlElementsFromCriteria(array('idSkill'=>$idSkill));
	$subList[]=$idSkill;
	Skill::getSubSkillList($subSkill, $subList);
	$limitedList = array();
	$limitedList = array_merge($subList, $parentList);
	$flatSubList = implode(',', $limitedList);
	$queryWhere .= " and idSkill in (0,".$flatSubList.")";
	if ($strictLevelCheck and $idSkillLevel) $queryWhere .= " and idSkillLevel = $idSkillLevel";
	else if (!$notResourceSkillSimple and $idSkillLevel) $queryWhere .= " and idSkillLevel >= $idSkillLevel";

	$queryOrderBy = "idSkillLevel ASC, useUntil ASC";	
	// constitute query and execute
	$query='select ' . $querySelect
	. ' from ' . $queryFrom
	.' where ' . $queryWhere
	. ' order by ' . $queryOrderBy;
	$result = Sql::query($query);
}

$recSkillList = array();
$listSkill = array();
$destinationHeight = RequestHandler::getValue('destinationHeight');
if ($notResourceSkillSimple){
  $heightTable = ($destinationHeight < 700) ? '80%' : '85%';
}else {
  $heightTable = ($destinationHeight < 700) ? '86%' : '90%';
}
$plannedBGColor='#FFFFDD';
$plannedFrontColor='#777777';
$plannedStyle=' style="text-align:center;background-color:' . $plannedBGColor . '; color: ' . $plannedFrontColor . ';" ';

if ($notResourceSkillSimple){
echo '<table align="center" width="98%">';
echo '<tr><td style="width:50%">&nbsp;</td><td style="text-align:right" align="right">';
  echo '<table width="100%" style="margin-bottom: 10px;transform: scale(0.80);" align="right">';
  echo '<tr>';
  echo '<td class="reportTableDataFull" style="width:20px;text-align:center;">1</td>';
  echo '<td width="60px" class="legend" style="white-space:nowrap;text-align:left">' . i18n('colRealWork') . '</td>';
  echo '<td width="5px">&nbsp;&nbsp;&nbsp;</td>';
  echo '<td class="reportTableDataFull" ' . $plannedStyle . '><i>1</i></td>';
  echo '<td width="50px" class="legend" style="white-space:nowrap;text-align:left">' . i18n('colPlanned') . '</td>';
  echo '<td width="5px">&nbsp;&nbsp;&nbsp;</td>';
  echo '<td class="reportTableDataFull" style="width:20px;text-align:center;color: #00AA00;background-color:#FAFAFA">1</td>';
  echo '<td width="60px" class="legend" style="white-space:nowrap;text-align:left">' . i18n('colNoWork') . '</td>';
  echo '<td width="5px">&nbsp;&nbsp;&nbsp;</td>';
  echo '<td width="200px" class="legend" style="white-space:nowrap;padding-right:5pxtext-align:right">' . Work::displayWorkUnit() . '</td>';
  echo '</tr>';
echo '</table></td></tr>';
echo '</table>';
}
echo '<div style="max-height: '.$heightTable.'; overflow-y: auto; overflow-x: auto;">';
echo '<TABLE id="resourceSkillList" align="center" width="'.($notResourceSkillSimple ? '98%' : '80%').'" style="margin: 0 auto;table-layout:fixed;border: 1px solid #AAAAAA;">';
echo '<TR class="ganttHeight" style="height:32px">';
echo '<TD class="reportTableHeader" style="border-left:0px; text-align: center;width:20%;padding: 5px" rowspan="'.($notResourceSkillSimple ? 2 : 1).'">'.i18n('colIdSkill').'</TD>';
echo '<TD class="reportTableHeader amountTableHeaderTD" style="width:11%;padding: 5px" rowspan="'.($notResourceSkillSimple ? 2 : 1).'">'.i18n('colIdSkillLevel').'</TD>';
echo '<TD class="reportTableHeader amountTableHeaderTD" style="width:7%;padding: 5px" rowspan="'.($notResourceSkillSimple ? 2 : 1).'">'.i18n('since').'</TD>';
echo '<TD class="reportTableHeader amountTableHeaderTD" style="width:7%;padding: 5px" rowspan="'.($notResourceSkillSimple ? 2 : 1).'">'.i18n('until').'</TD>';
echo '<TD class="reportTableHeader amountTableHeaderTD" style="width:12%;padding: 5px" rowspan="'.($notResourceSkillSimple ? 2 : 1).'">'.i18n('colIdResource').'</TD>';
if ($notResourceSkillSimple){
echo '<TD class="reportTableHeader amountTableHeaderTD" style="width:4%;padding: 5px" rowspan="2">'.i18n('colCapacity').'</TD>';
echo '<TD class="reportTableHeader amountTableHeaderTD" style="width:32%;padding: 5px" rowspan="2">'.i18n('Dispo').'</TD>';
echo '<TD class="reportTableHeader amountTableHeaderTD" style="width:10%;padding: 5px" colspan="3" >'.i18n('colPertinence').'</TD>';
}
echo '</TR>';
if ($notResourceSkillSimple){
echo '<TR class="ganttHeight" style="height:32px">';
echo '<TD class="reportTableHeader amountTableHeaderTD" title="'.i18n('Dispo').'">'.i18n('smallDisponibility').'</TD>';
echo '<TD class="reportTableHeader amountTableHeaderTD" title="'.i18n('Skill').'">'.i18n('smallSkill').'</TD>';
echo '<TD class="reportTableHeader amountTableHeaderTD"  title="'.i18n('Global').'">'.i18n('smallGlobal').'</TD>';
echo '</TR>';
}
// Treat each line
if($result && Sql::$lastQueryNbRows > 0){
  $resultRow = array();
  $resultLine = '';
  if (Sql::$lastQueryNbRows > 0) {
  	while ($line = Sql::fetchLine($result)) {
  		$line=array_change_key_case($line,CASE_LOWER);
  		$obj=new Skill($line['idskill'],true);
  		if(($obj->isElementary() and !$obj->idSkill) or (!$obj->isElementary() and !$obj->idSkill)){
  			$listSkill[$line['idskill']]=$line['idskill'];
  		}
  		$recSkillList[$line['idskill']][$line['idresource']]=$line;
  	}
  	if($idSkill){
  		unset($listSkill);
  		$listSkill[] = $idSkill;
  	}
  	foreach ($listSkill as $idSkill){
  		$obj=new Skill($idSkill,true);
  		$parentSkill=$obj->getParentSkill();
  		$subSkill=$obj->getRecursiveSubSkill();
  		$level=0;
  		//$pertinence = pow($ratioPertinence,count($parentSkill));
  		foreach ($parentSkill as $parentId=>$parentName) {
  			$level++;
  			$pertinence = pow($ratioPertinence,count($parentSkill)-$level+1);
  			showSkill($parentId,$parentName,$level,'top', $recSkillList, $pertinence, $resultRow,$notResourceSkillSimple);
  			$pertinence= sqrt($pertinence);
  		}
  		$level++;
  		showSkill($obj->id,$obj->name,$level,'current', $recSkillList, 1, $resultRow,$notResourceSkillSimple);
  		showSubItems($subSkill,$level+1, $recSkillList, $resultRow,$notResourceSkillSimple);
  	}
  	foreach ($resultRow as $row){
  	  echo $row;
  	}
  }
}else{
  echo '<TR>';
  echo '<TD colspan="'.($notResourceSkillSimple ? 10 : 5).'" style="background:#FFDDDD;font-size:150%;color:#808080;text-align:center;padding:15px 0;">'
      . i18n('noDataFound') . '</TD>';
  echo '</TR>';     
}
echo '</TABLE>';
echo '</div>';
//echo '</div>';

function showSubItems($subItems,$level, $arraySkill, &$resultRow,$notResourceSkillSimple){
  if (!$subItems) return;
  foreach ($subItems as $item) {
    if (hasValidResources($item, $arraySkill)) {
      showSkill($item['id'],$item['name'],$level,'sub', $arraySkill, 1, $resultRow,$notResourceSkillSimple);
    }
    if (isset($item['subItems']) and is_array($item['subItems'])) {
      showSubItems($item['subItems'],$level+1,$arraySkill, $resultRow,$notResourceSkillSimple);
    }
  }
}

function hasValidResources($item, $arraySkill) {
  if (isset($arraySkill[$item['id']]) && count($arraySkill[$item['id']]) > 0) {
    return true;
  }
  if (!empty($item['subItems'])) {
    foreach ($item['subItems'] as $subItem) {
      if (hasValidResources($subItem, $arraySkill)) {
        return true;
      }
    }
  }
  return false;
  
}
function showSkill($id,$name,$level,$position, $arraySkill, $pertinence, &$resultRow,$notResourceSkillSimple) {
  $resourceSkill = (isset($arraySkill[$id]))?$arraySkill[$id]:array(0=>array(0));
  $result = '';
  $rowType  = "row";
  $display='';
  $padding=16;
  if($level==1)$padding=5;
  $name="#$id - $name";
  $style="";
  $current=($position=='current');
  $item=new Skill($id);
  $isElementary = $item->isElementary();
  $limitedSubSkill = array();
  if( !$isElementary) {
    $rowType = "group";
    $skill = new Skill();
    $subList = $skill->getSqlElementsFromCriteria(array('idSkill'=>$id));
    foreach ($subList as $id=>$obj){
      $limitedSubSkill[]=$obj->id;
    }
    $subSkill=array();
    Skill::getSubSkillList($subList, $subSkill);
    $class = 'ganttExpandOpened';
  }
  $idProject=(RequestHandler::getValue('listProjectFilter'))?pq_trim(RequestHandler::getValue('listProjectFilter')):pq_trim(getSessionValue('listProjectFilter'));
  $idSkillLevel=(RequestHandler::getValue('listSkillLevelFilter'))?pq_trim(RequestHandler::getValue('listSkillLevelFilter')):pq_trim(getSessionValue('listSkillLevelFilter'));
  $currentLine=(RequestHandler::getValue('listSkillFilter'))?pq_trim(RequestHandler::getValue('listSkillFilter')):pq_trim(getSessionValue('listSkillFilter'));
  $sortBy = (RequestHandler::getValue('sortByFilter'))?pq_trim(RequestHandler::getValue('sortByFilter')):pq_trim(getSessionValue('sortByFilter'));
  if(!$sortBy)$sortBy='global';
  $backGround='';
  if($currentLine==$item->id){
    $backGround='background-color:var(--color-light-secondary);';
  }
  $firstRow = true;
  $topId=$item->getTopParentSkill();
  
  $resSortArray = array();
  
  $skillLevel = new SkillLevel();
  $minWeight = $skillLevel->getMinValueFromCriteria('weight', null, "1=1");
  foreach ($resourceSkill as $skill){
    $idResSkill=(isset($skill['id']))?$skill['id']:0;
    if($idResSkill == 0)continue;
    $txDispo = 0;
    $skillLevel = new SkillLevel();
    $weight = 0;
    $maxWeight=1;
    if($idResSkill != 0){
    	$skillLevel = new SkillLevel($skill['idskilllevel']);
    	$weight = $skillLevel->weight;
    	$where = ($idSkillLevel)?"id=$idSkillLevel":'1=1';
    	$maxWeight = $skillLevel->getMaxValueFromCriteria('weight', null, $where);
    }
    $resourceName = ($idResSkill != 0)?SqlList::getNameFromId('Resource', $skill['idresource']):'';
    $resourceId = ($idResSkill != 0)?$skill['idresource']:'';
    $txWeight=($weight/$maxWeight > 1)?1:($weight/$maxWeight);
    $txPerti = $pertinence*$txWeight;
    drawResourceDisponibility($resourceId, $resourceName, $txDispo);
    $txGlobal = round(($txPerti*$txDispo)*100);
    if($sortBy == 'dispo')$resSortArray[$resourceId]=(($txDispo*100)*$txGlobal)/100;
    if($sortBy == 'perti')$resSortArray[$resourceId]=(($txPerti*100)*$txGlobal)/100;
    if($sortBy == 'global')$resSortArray[$resourceId]=$txGlobal;
  }
  
  arsort($resSortArray);
  $resourceSkill = array_merge_preserve_keys($resSortArray, $resourceSkill);
  
  foreach ($resourceSkill as $skill){
    $idResSkill=(isset($skill['id']))?$skill['id']:0;
    $idRow = 'id="skillStructureRow_'.$item->id.'_'.$idResSkill.'"';
    $result .='<TR '.$idRow.' style="height:40px !important;'.$style.'">';
    $rowspan = (count($resourceSkill)>1)?'rowspan="'.count($resourceSkill).'"':'';
    $hiddenClass = '';
    if(count($resourceSkill)>1){
      $hiddenClass = ($firstRow)?'resourceSkillFirstRow':'resourceSkillHiddenRow';
    }
    $result .='  <TD class="ganttName reportTableData '.$hiddenClass.'" style="width:20%;'.$backGround.'">';
    $result .='    <span>';
    $result .='      <table><tr>';
    $result .='<TD>';
    if(!$isElementary and $firstRow){
    	$result .='     <div id="group_'.$item->id.'" class="'.$class.'"';
    	$result .='      style="word-wrap: break-word; margin-left:'.(($level-1)*$padding+5).'px; position: relative; z-index: 100000;   width:16px; height:13px;"';
    	$result .='      onclick="expandSkillGroup(\''.$item->id.'\',\''.implode(',', $limitedSubSkill).'\',\''.implode(',', $subSkill).'\');">&nbsp;&nbsp;&nbsp;&nbsp;</div>';
    }else{
    	$result .='     <div id="group_'.$item->id.'" class="ganttSkill"';
    	$result .='      style="word-wrap: break-word; margin-left:'.(($level-1)*$padding+5).'px; position: relative; z-index: 100000;   width:16px; height:13px;"></div>';
    }
    $result .='</TD>';
    if($firstRow){
      $goto = "";
      if (securityCheckDisplayMenu(null,'Skill') and securityGetAccessRightYesNo('menu'.get_class($item), 'read', '')=="YES") {
      	$goto=' onClick="top.gotoElement(\''.get_class($item).'\',\''.htmlEncode($item->id).'\');window.top.dijit.byId(\'dialogPrint\').hide();" style="cursor: pointer;" ';
      }
      $result .='       <TD '.$goto.' style="'.$style.'padding-bottom:5px;" class="'.((isNewGui() and isset($goto) and $goto!='')?'classLinkName':'').'"><div style="margin:10px; text-align:left;">#'.htmlEncode($item->id).'  '.htmlEncode($item->name). '</div></TD>' ;
    }
    $result .='      </tr></table>';
    $result .='    </span>';
    $result .='  </TD>';
    $skillLevel = new SkillLevel();
    $weight = 0;
    $maxWeight=1;
    if($idResSkill != 0){
      $skillLevel = new SkillLevel($skill['idskilllevel']);
      $weight = $skillLevel->weight;
      $where = ($idSkillLevel)?"id=$idSkillLevel":'1=1';
      $maxWeight = $skillLevel->getMaxValueFromCriteria('weight', null, $where);
    }
    if (isset($skill['comment']) and $skill['comment'] != "") {
      $result .='  <TD class="ganttName reportTableData" title="'.$skillLevel->name.'" style="position:relative!important;'.$backGround.';height=\"20px\";"><img src="icons/'.$skillLevel->icon.'" alt="'.$skillLevel->name.'" style="height: 36px;"><div class="iconButtonComment16 iconButtonComment iconSize16" style="position:absolute;top:10px;right:15px" title="'.br2nl($skill["comment"]).'"></div></TD>';
    } else {
      $result .='  <TD class="ganttName reportTableData" title="'.$skillLevel->name.'" style="'.$backGround.'"><img src="icons/'.$skillLevel->icon.'" alt="'.$skillLevel->name.'" style="height: 36px;"></TD>';
    }
    
    $useSinceSkill = ($idResSkill != 0)?htmlFormatDate($skill['usesince']):'';
    $result .='  <TD class="ganttName reportTableData" style="'.$backGround.'">'.$useSinceSkill.'</TD>';
    $useUntilSkill = ($idResSkill != 0)?htmlFormatDate($skill['useuntil']):'';
    $result .='  <TD class="ganttName reportTableData" style="'.$backGround.'">'.$useUntilSkill.'</TD>';
    $resourceName = ($idResSkill != 0)?SqlList::getNameFromId('Resource', $skill['idresource']):'';
    $resourceId = ($idResSkill != 0)?$skill['idresource']:'';
    $result .='  <TD class="ganttName reportTableData" style="'.$backGround.'">';
    if($idResSkill != 0){
      $result .='<TABLE style="width:100%;height:100%"><TR>';
      $result .='<TD align="right" style="width:20%;padding-right:5px;">'.formatUserThumb($resourceId, $resourceName, $resourceName).'</TD>';
      $goto = "";
      if (securityCheckDisplayMenu(null,'Resource') and securityGetAccessRightYesNo('menuResource', 'read', '')=="YES") {
      	$goto=' onClick="top.gotoElement(\'Resource\',\''.htmlEncode($resourceId).'\');window.top.dijit.byId(\'dialogPrint\').hide();" style="cursor: pointer;" ';
      }
      $result .='<TD align="left" style="width:60%;" '.$goto.' class="'.((isNewGui() and isset($goto) and $goto!='')?'classLinkName':'').'">'.$resourceName.'</TD>';
      $aff=new Affectation();
      $affLst=$aff->getSqlElementsFromCriteria(array('idProject'=>$idProject, 'idResource'=>$resourceId));
      $buttonClass = (count($affLst)>0)?formatSmallButton('Edit'):formatSmallButton('Add');
      $funcAdd = 'addAffectation(\'Resource\',\'ResourceSkill\',\''.$resourceId.'\', \''.$idProject.'\',false,false);';
      $func = (count($affLst)>0)?'editAffectation(\''.$affLst[0]->id.'\',\'Resource\',\'ResourceSkill\',\''.$affLst[0]->idResource.'\', \''.$affLst[0]->idProject.'\',\''.htmlEncode($affLst[0]->rate).'\',\''.htmlEncode($affLst[0]->idle).'\',\''.$affLst[0]->startDate.'\',\''.htmlEncode($affLst[0]->endDate).'\',\''.htmlEncode($affLst[0]->idProfile).'\');':$funcAdd;
      $title = (count($affLst)>0)?i18n('editAffectation'):i18n('addAffectation');
      if ($notResourceSkillSimple) $result .='<TD><a onClick="'.$func.'" title="'.$title.'">'.$buttonClass.'</a></TD>';
      $result .='</TR></TABLE>';
    }
    $result .='</TD>';
    $cap = '';
    if($idResSkill != 0){
      $res=new Resource($resourceId);
      $cap = round($res->capacity);
    }
    if($notResourceSkillSimple) $result .='  <TD class="ganttName reportTableData" style="'.$backGround.'">'.$cap.'</TD>';
    $txDispo = 0;
    $maxWeight = ($idSkillLevel != "")?$maxWeight:$minWeight;
    $txWeight=($weight/$maxWeight > 1)?1:($weight/$maxWeight);
    $txPerti = $pertinence*$txWeight;
    $perti = ($idResSkill != 0)?round($txPerti*100).'%':'';
    $dispoRsult = ($idResSkill != 0)?drawResourceDisponibility($resourceId, $resourceName, $txDispo):'';
    $dispo = ($idResSkill != 0)?round($txDispo*100).'%':'';
    if($notResourceSkillSimple){
      $result .='  <TD class="ganttName reportTableData" style="padding:unset !important;'.$backGround.'">'.$dispoRsult.'</TD>';
      $result .='  <TD class="ganttName reportTableData" style="'.$backGround.'">' . $dispo . '</TD>';
      $result .='  <TD class="ganttName reportTableData" style="'.$backGround.'">' . $perti . '</TD>';
    }
    $txGlobal = ($idResSkill != 0)?round(($txPerti*$txDispo)*100):'';
    $color="";
    if($txGlobal == 0)$color="background-color:#ebebeb";
    if($txGlobal > 0 and $txGlobal <=50)$color="background-color:orange";
    if($txGlobal > 50 and $txGlobal <=75)$color="background-color:gold";
    if($txGlobal > 75 and $txGlobal <=100)$color="background-color:#45d545";
    if($idResSkill == 0){
      $color="";
    }else{
      $txGlobal .= '%';
    }
    if($notResourceSkillSimple) $result .='  <TD class="ganttName reportTableData" style="'.$backGround.$color.'">' . $txGlobal . '</TD>';
    $result .='  </TR>';
    $firstRow=false;
  }
  $resultRow[] = $result;
}


function drawResourceDisponibility($resourceId, $resourceName, &$txDispo){
  $showPeriodDisponibility=(RequestHandler::getValue('showPeriodDisponibility'))?RequestHandler::getValue('showPeriodDisponibility'):getSessionValue('showPeriodDisponibility');
  $useSince=(RequestHandler::getValue('skillUseSince'))?RequestHandler::getValue('skillUseSince'):getSessionValue('skillUseSince');
  $useUntil=(RequestHandler::getValue('skillUseUntil'))?RequestHandler::getValue('skillUseUntil'):getSessionValue('skillUseUntil');

  if((!$useSince and !$useUntil) or ($useSince > $useUntil))return;
  $resources[$resourceId]=$resourceName;
  $resourceCalendar[$resourceId]=SqlList::getFieldFromId('ResourceAll', $resourceId, 'idCalendarDefinition');
  $paramPeriodScale='day';
  $resultTable = '';
  $where="1=1";
  if($resourceId)$where .= " and idResource=$resourceId";
  if ($showPeriodDisponibility=="showMonthlyDisponibility") {
  	$start=$useSince;
  	$startYear=pq_substr($start,0,4);
  	$startMonth=pq_substr($start,5,2);
  	$startValue=$startYear.$startMonth;
  	if($startValue)$where.= " and month >= '$startValue'";
  	$end=$useUntil;
  	$endYear=pq_substr($end,0,4);
  	$endMonth=pq_substr($end,5,2);
  	$endValue=$endYear.$endMonth;
  	if($endValue)$where.= " and month <= '$endValue'";
  	$paramPeriodScale='month';
  } else if ($showPeriodDisponibility=="showWeeklyDisponibility") {
  	$start=$useSince;
  	$startValue=pq_substr($start,0,4).pq_substr($start,5,2).pq_substr($start,8,2);
  	if($startValue)$where.= " and day >= '$startValue'";
  	$end=$useUntil;
  	$endValue=pq_substr($end,0,4).pq_substr($end,5,2).pq_substr($end,8,2);
  	if($endValue)$where.= " and day <= '$endValue'";
  	$paramPeriodScale='week';
  } else {
    $start=$useSince;
    if($start)$where.= " and workDate >= '$start'";
    $end=$useUntil;
    if($end)$where.= " and workDate <= '$end'";
    $paramPeriodScale='day';
  }
  $header=i18n($paramPeriodScale);

  $work=new Work();
  $lstWork=$work->getSqlElementsFromCriteria(null,false, $where);
  $result=array();
  
  $capacity=array();
  foreach ($resources as $id=>$name) {
  	$capacity[$id]=SqlList::getFieldFromId('ResourceAll', $id, 'capacity');
  	$result[$id]=array();
  }
  
  $real=array();
  foreach ($lstWork as $work) {
  	if (! pq_array_key_exists($work->idResource,$resources)) {
  		continue;
  	}
  	if (! pq_array_key_exists($work->idResource,$real)) {
  		$real[$work->idResource]=array();
  	}
  	if (! pq_array_key_exists($work->day,$result[$work->idResource])) {
  		$result[$work->idResource][$work->day]=0;
  		$real[$work->idResource][$work->day]=true;
  	}
  	$result[$work->idResource][$work->day]+=$work->work;
  }
  $planWork=new PlannedWork();
  $lstPlanWork=$planWork->getSqlElementsFromCriteria(null,false, $where);
  foreach ($lstPlanWork as $work) {
  	if (! pq_array_key_exists($work->idResource,$resources)) {
  		continue;
  	}
  	if (! pq_array_key_exists($work->idResource,$real)) {
  		$real[$work->idResource]=array();
  	}
  	if (! pq_array_key_exists($work->day,$result[$work->idResource])) {
  		$result[$work->idResource][$work->day]=0;
  	}
  	$result[$work->idResource][$work->day]+=$work->work;
  }
  
  $weekendBGColor='#cfcfcf';
  $weekendFrontColor='#555555';
  $weekendStyle=' style="text-align: center;background-color:' . $weekendBGColor . '; color:' . $weekendFrontColor . '" ';
  $plannedBGColor='#FFFFDD';
  $plannedFrontColor='#777777';
  $plannedStyle=' style="text-align:center;background-color:' . $plannedBGColor . '; color: ' . $plannedFrontColor . ';" ';
  
  // Group data corresponding to periodscale
  $resultPeriod=array();
  $resultPeriodFmt=array();
  $totalPeriod=array();
  $sumDay = 0;
  for($day=$start;$day<=$end;$day=addDaysToDate($day, 1)) {
  	if ($paramPeriodScale=="month") {
  		$period=pq_substr($day,0,7);
  	} else if ($paramPeriodScale=="week") {
  		$period=weekFormat($day);
  	} else {
  		$period=htmlformatDate($start)." - ".htmlFormatDate($end);
  	}
  	if (! isset($resultPeriod[$period])) {
  		$resultPeriod[$period]=array();
  		$resultPeriodFmt[$period]=array();
  	}
  	foreach ($resources as $idR=>$nameR) {
  		$res = new ResourceAll($idR, true);//florent ticket #5038
  		$capaDay=0;
  		if (! isOffDay($day, $resourceCalendar[$idR])) {
  			$capaDay=$res->getCapacityPeriod($day);
  			$sumDay += $capaDay;
  		}
  		if (! isset($resultPeriod[$period][$idR])) {
  			$resultPeriod[$period][$idR]=0;
  			$resultPeriodFmt[$period][$idR]='none';
  		}
  		if ($res->isResourceTeam != '') {
  			$resultPeriod[$period][$idR]+=$capaDay;
  		}
  		$dayFmt=pq_str_replace('-', '', $day);
  		if (isset($result[$idR][$dayFmt])) {
  			$resultPeriod[$period][$idR]-=$result[$idR][$dayFmt];
  			if (isset($real[$idR][$dayFmt]) and $real[$idR][$dayFmt]==true) {
  				$resultPeriodFmt[$period][$idR]='real';
  			} else if ($resultPeriodFmt[$period][$idR]=='none') {
  				$resultPeriodFmt[$period][$idR]='plan';
  			}
  		}
  	}
  }
  
  $resultTable .= '<div style="width:100%;overflow-x:auto;overflow-y: hidden;">';
  $resultTable .= '<table style="width:100%;height:100%;"><tr>';
  foreach($resultPeriod as $idP=>$period) {
  	$resultTable .= '<td class="reportTableColumnHeader" style="white-space:nowrap;border:none;">' . $idP . '</td>';
  }
  $resultTable .= '</tr>';
  foreach ($resources as $idR=>$nameR) {
  	$res=new ResourceAll($idR);
  	if ($res->isResourceTeam) {
  		$maxCapa=$capacity[$idR];
  	} else {
  		$maxCapa = 0;
  		for($day=$start;$day<=$end;$day=addDaysToDate($day, 1)) {
  			if($res->getCapacityPeriod($day) > $maxCapa){
  				$maxCapa = round($res->getCapacityPeriod($day), 2);
  			}
  		}
  	}
	$sum=0;
	$resultTable .= '<tr style="height:20px">';
	foreach($resultPeriod as $idP=>$period) {
		$style="";
		$italic=false;
		$style=' style="text-align:center;';
		$val=$period[$idR];
		if ($resultPeriodFmt[$idP][$idR]=='plan') {
			$style.='background-color:' . $plannedBGColor . ';';
			if ($val<0) $style.="color:#d05050;font-weight:bold;";
			$italic=true;
		} else if ($resultPeriodFmt[$idP][$idR]=='real') {
			if ($val<0) $style.='color: #d05050;font-weight:bold;';
			else $style.='color: #000000;';
		} else {
			$style.='color: #00AA00;color: #00AA00;background-color:#FAFAFA;';
		}
		$style.='border-bottom:unset;border-left:unset;border-right:unset;"';
		$resultTable .= '<td class="reportTableDataFull" ' . $style . ' valign="middle">';
		if ($italic) {
			$resultTable .= '<i>' . round(Work::displayWork($val), 2) . '</i>';
		} else {
			$resultTable .= round(Work::displayWork($val), 1);
		}
		$resultTable .= '</td>';
		if ($val>0) {
			$sum+=$val;
		}
		if($res->isResourceTeam and $val<0){
			$sum+=$val;
		}
	}
	$txDispo = ($sumDay)?round($sum/$sumDay, 2):'0';
	$resultTable .= '</tr>';
  }
  $resultTable .= '</table>';
  $resultTable .= '</div>';
  return $resultTable;
}
?>