<?php
use PhpOffice\PhpPresentation\Shape\Line;
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
include_once '../tool/projeqtor.php';
include_once '../tool/formatter.php';
?>
<script type="text/javascript" src="<?php echoStaticFileNameWithCacheMgt('js/projeqtor.js');?>"></script> <?php 
$id = RequestHandler::getId('id');
$obj = new Skill($id);
$currentLine = $id;

echo '<table id="skillStructure" width="100%"" style="min-width:400px">';
echo '<TR>';
echo '  <TD class="reportTableHeader" style="width:48%;text-align: center;">' . i18n('colName') . '</TD>';
echo '</TR>';
echo '</table>';

echo '<div id="skillStructureListDiv" style="position:relative;height:600px;width:100%;min-width:400px;">';
echo '<table id="dndskillStructure" align="left" width="100%" style="table-layout:fixed;">';
$parentSkill=array();
$subSkill=array();

$parentSkill=$obj->getParentSkill();
$subSkill=$obj->getRecursiveSubSkill();

$level=0;
foreach ($parentSkill as $parentId=>$parentName) {
  $level++;
  showSkill($parentId,$parentName,$level,'top');
}
$level++;
showSkill($obj->id,$obj->name,$level,'current');
showSubItems($subSkill,$level+1);


echo "</table>";
echo '</div>';

function showSubItems($subItems,$level){
  if (!$subItems) return;
  foreach ($subItems as $item) {
    showSkill($item['id'],$item['name'],$level,'sub');
    if (isset($item['subItems']) and is_array($item['subItems'])) {
      showSubItems($item['subItems'],$level+1);
    }
  }
}


function showSkill($id,$name,$level,$position) {
  global $currentLine;
  $rowType  = "row";
  $display='';
  $compStyle="";
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
  if($currentLine==$item->id){
    $style='background-color:#ffffaa;';
  }
  echo '<TR id="skillStructureRow_'.$item->id.'" height="40px" '.$display.'>';
  echo '  <TD class="ganttName reportTableData" style="'.$style.'width:48%;' . $compStyle . '">';
  echo '    <span>';
  echo '      <table><tr>';
  echo '<TD>';
  if(!$isElementary){
    echo '     <div id="group_'.$item->id.'" class="'.$class.'"';
    echo '      style="word-wrap: break-word; margin-left:'.(($level-1)*$padding+5).'px; position: relative; z-index: 100000;   width:16px; height:13px;"';
    echo '      onclick="expandSkillGroup(\''.$item->id.'\',\''.implode(',', $limitedSubSkill).'\',\''.implode(',', $subSkill).'\');">&nbsp;&nbsp;&nbsp;&nbsp;</div>';
  }else{
     echo '     <div id="group_'.$item->id.'" class="ganttSkill"';
     echo '      style="'.$style.'word-wrap: break-word; margin-left:'.(($level-1)*$padding+5).'px; position: relative; z-index: 100000;   width:16px; height:13px;"</div>';
  }
  echo '</TD>';
  $goto = "";
  if (securityCheckDisplayMenu(null,'Skill') and securityGetAccessRightYesNo('menu'.get_class($item), 'read', '')=="YES") {
    $goto=' onClick="top.gotoElement(\''.get_class($item).'\',\''.htmlEncode($item->id).'\');window.top.dijit.byId(\'dialogPrint\').hide();" style="cursor: pointer;" ';
  }
  echo '       <TD '.$goto.' style="'.$style.'padding-bottom:5px;" class="'.((isNewGui() and isset($goto) and $goto!='')?'classLinkName':'').'"><div class="amountTableDiv">#'.htmlEncode($item->id).'  '.htmlEncode($item->name). '</div></TD>' ;
  echo '      </tr></table>';
  echo '    </span>';
  echo '  </TD>';
}

