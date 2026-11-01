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
scriptLog('   ->/view/hierarchicalSkillView.php');

global $print;
if ( pq_array_key_exists('print',$_REQUEST) ) {
  $print=true;
}

// $table=$obj->getDatabaseTableName();
$hiddenRow = array();
$tableVisible = array();
$subRow=array();
$parentVisible=array();
$showClosed=(getSessionValue('listShowIdleSkill')=='on')?true:false;
$parentSkill=getSessionValue('listSkillParentFilter');
$maxwidht = 'margin-top:15px;';
if($print)$maxwidht='max-width:1350px;';
// Header
$where="1=1";
if(!$showClosed)$where.=" and idle=0";
if(pq_trim($parentSkill)!=''){
  $obj=new Skill($parentSkill);
  $objTable=$obj->getDatabaseTableName();
  $sbsSortableCol=$obj->getDatabaseColumnName('sbsSortable');
  $sbsSortable=$obj->sbsSortable;
  $where.=" and id in (Select s.id From $objTable as s Where s.$sbsSortableCol like '$sbsSortable%')";
}else{
  $obj=new Skill();
}
$lstSkill=$obj->getSqlElementsFromCriteria(null,false,$where,'sbsSortable asc');
$result="";

$minWidthTab=(isNewGui())?1363:1350;
if($print)$minWidthTab=900;
if (!$print) $result .= '<div id="hierarchicalSkillListHeaderDiv"" style="'.$maxwidht.'">';
$result .= '<table id="hierarchicalSkillListHeader" align="left" width="'.(($print)?'1000px':'100%').'" style="min-width:'.$minWidthTab.'px;">';
$result .= '<tr class="ganttHeight" style="height:32px">';

if(!$print)$result .= '  <td class="reportTableHeader" style="width:25px;min-width:25px;max-width:25px; border-right: 0px;"></td>';
$result .= '  <td class="reportTableHeader " ><div class="" style="width:80px;">' . i18n('colSbs') . '</div></td>' ;
$result .= '  <td class="reportTableHeader" style="border-left:0px; text-align: left;width:100%;">' . i18n('Skill') . '</td>';
$result .= '</tr>';
if(!$print)$result .= "</table>";

$style='style="width:98%;margin-left:5px;"';
if(!$print) $result .= '</div>';

$destHeight=RequestHandler::getValue('destinationHeight');
$height=($destHeight)?(intval($destHeight)).'px':'100%';

if(!$print)$result .= '<div id="hierarchicalSkillListDiv" style="position:relative;height:'. $height .';width:100%;min-width:'.((isNewGui())?1363:1350).'px;'.$maxwidht.'overflow-x:hidden;">';
if(!$print)$result .= '<table id="dndHierarchicalSkillList" dojoType="dojo.dnd.Source" jsId="dndSourceTableSkill" id="dndSourceTableSkill" align="left" width="100%" style="min-width:'.((isNewGui())?1363:1350).'px;">';
foreach ($lstSkill as $skill){
  $id=$skill->id;
  $onclcik='onClick="dojo.byId('."'objectId'".').value=\''.$id.'\';listClick();loadContent('."'objectDetail.php'".', '."'detailDiv'".','."'listForm'".');"';
  if($skill->isElementary()){
    $compStyle="";
    $pEl=false;
    $rowType  = "row";
    if(!$skill->idSkill and pq_strpos($skill->sbsSortable, '.')!=false){
       $hiddenRow[$id]=$id;
    }
    
    if($skill->idSkill and isset($parentVisible[$skill->idSkill])){
      $tableVisible[]=$id.'=>'.$parentVisible[$skill->idSkill];
    }else{
      $tableVisible[$id]=$id.'=>visible';
    }
  }else{
    $compStyle="font-weight: normal; background: #E8E8E8";
    $pEl=true;
    $rowType = "group";
    $subList = $skill->getSqlElementsFromCriteria(array('idSkill'=>$id));
    $subRowList=array();
    foreach ($subList as $sub){
      $subRowList[]=$sub->id;
    }
    
    $subSkill=array();
    Skill::getSubSkillList($subList, $subSkill);
    $subRow[]=$id."=>".implode("/", $subRowList);
    $crit=array('scope'=>'hierarchicalSkillRow_'.$id, 'idUser'=>getCurrentUserId());
    $col=SqlElement::getSingleSqlElementFromCriteria('Collapsed', $crit);
    if(pq_trim($col->id)!=''){
      $class = 'ganttExpandClosed';
      $hiddenRow = array_merge($hiddenRow, $subSkill);
    }else{
      $class = 'ganttExpandOpened';
    }
    $visible = ($class=='ganttExpandOpened')?'visible':'hidden';
    if($skill->idSkill and isset($parentVisible[$skill->idSkill]) and $parentVisible[$skill->idSkill])$tableVisible[$id]=$id.'=>'.$parentVisible[$skill->idSkill];
    else $tableVisible[$id]=$id.'=>visible';
    $parentVisible[$id]=$visible;
  }
  $wbs=$skill->sbsSortable;
  $level=(pq_strlen($wbs)+1)/6;
  $tab="";
  for ($i=1;$i<$level;$i++) {
  	$tab.='<span class="ganttSep">&nbsp;&nbsp;&nbsp;&nbsp;</span>';
  }
  
  $display='';
  if(in_array($id, $hiddenRow) and $id!=$parentSkill){
    $display='visibility:collapse';
  }

  $result .= '<tr id="hierarchicalSkillRow_'.$id.'" dndType="skillHierachical" class="dojoDndItem ganttTask hierarchicalSkillRow" height="30px" style="cursor:default;'.$display.'">';
  if(!$print){
    $result .= '  <td class="ganttName reportTableData" style="width:25px;min-width:25px;max-width:25px;padding: 3px 5px 3px 5px;' . $compStyle . ';text-align:center;">';
    $result .= '    <span class="dojoDndHandle handleCursor">';
    $result .= '     <img style="margin-right:2px;width:8px" src="css/images/iconDrag.gif" />';
    $result .= '    </span>';
    $result .= '  </td>' ;
  }
  $result .= '  <td class="ganttName reportTableData amountTabletd" style="width:80px;' . $compStyle . ';text-align:left;" '.$onclcik.'>';
  $result .=                  '<div style="width:80px;padding-left:8px;">' .htmlEncode($skill->sbs). '</div>';
  $result .= '   </td>' ;
  $result .= '  <td class="ganttName reportTableData " style="' . $compStyle . ';text-align:left;padding-left:15px;">';
  $result .= '    <table style="width:100%;height:100%;vertical-align:middle;"><tr style="height:100%">';
  $result .= '     <td style="width:1px;font-size:180%">'.$tab.'</td>';
  $result .= '     <td style="position:relative;width:16px;">';
  if($pEl and !$print){
    $result .='     <div id="group_'.$id.'" class="'.$class.'"';
    $result .='      style="position: relative; z-index: 100000; width:16px; height:13px;float:left;"';
    $result .='      onclick="event.preventDefault();expandHierarchicalSkillGroup(\''.$id.'\',\''.implode(',', $subSkill).'\');">&nbsp;&nbsp;&nbsp;&nbsp;</div>';
  }
  $result .= '      </td>';
  
  $result .= '      <td style="vertical-align:middle;margin-left:0"><div '.$style.' '.$onclcik.'>' .htmlEncode($skill->name). '</div></td>';
  $result .= '     </tr></table>';
  $result .= '   </td>' ;
  $result .= '</tr>';
}

$result .= "</table>";
if(count($tableVisible)>0)asort($tableVisible);
$tableVisible=implode(",", $tableVisible) ;
$subRow=implode(",", $subRow);
$result .='<input type="hidden" id="visibleRows" name="visibleRows" value="'.$tableVisible.'" />';
$result .='<input type="hidden" id="subRowsForParents" name="subRowsForParents" value="'.$subRow.'" />';
$result .= '<div id="hierarchicalSkillListDivEnd" style="min-height:20px;">&nbsp;</div>';
$result .= "</div>";

echo $result;


?>