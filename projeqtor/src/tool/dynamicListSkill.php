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

/** ============================================================================
 * 
 */

require_once "../tool/projeqtor.php";
scriptLog('   ->/tool/dynamicListSkill.php');

$selected=null;
if (pq_array_key_exists('selected',$_REQUEST)) {
	$selected=$_REQUEST['selected'];
}
$selectedArray=pq_explode('_',$selected);

$crit = array ( 'idle'=>'0');
$list = SqlList::getListWithCrit('Skill', $crit, 'name', false);
$skillList=SqlList::getList('Skill','sbsSortable',null,false);

$sepChar=Parameter::getUserParameter('projectIndentChar');
if (!$sepChar) $sepChar='__';
else if ($sepChar=='no') $sepChar='';
$sbsLevelArray=array();

?>
<select id="skillId" size="14" name="skillId[]" multiple
onchange="enableWidget('dialogResourceSkillSubmit');" <?php if (isNewGui()) echo ' style="width:410px;" ';?> class="selectList" >
 <?php
 foreach ($list as $id=>$name) {
   if(isset($skillList[$id])){
     $val = $name;
     $skillOrder = $skillList[$id];
     $skillTest=$skillOrder;
     $level=1;
     while (pq_strlen($skillTest)>4) {
       $skillTest=pq_substr($skillTest,0,pq_strlen($skillTest)-6);
       if (pq_array_key_exists($skillTest, $sbsLevelArray)) {
         $level=$sbsLevelArray[$skillTest]+1;
         $skillTest="";
       }
     }
     $sbsLevelArray[$skillOrder]=$level;
     $sep='';
     for ($i=1; $i<$level;$i++) {
       if (pq_strpos($sepChar,'|')!==FALSE and $i<$level-1 and pq_strlen($sepChar)>1) {
         $sepCharW = str_repeat('..', 2);
       } else {$sepCharW = $sepChar;}
       $sep.=$sepCharW;
     }
     $val =$sep.$val;
     $selected = (in_array($id, $selectedArray))?'SELECTED':'';
     echo "<option value='$id' $selected>$val</option>";
   }
 }
 ?>
</select>