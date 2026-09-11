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
 * Save some information to session (remotely).
 */

require_once "../tool/projeqtor.php";
scriptLog('   ->/tool/dynamicListPokerItem.php');

$ref1Type=RequestHandler::getClass('pokerItemRef1Type');
$ref1Id=RequestHandler::getId('pokerItemRef1Id');
$ref2Type=RequestHandler::getClass('pokerItemRef2Type');

$selected=null;
if (pq_array_key_exists('selected',$_REQUEST)) {
  $selected=$_REQUEST['selected'];
}
$selectedArray=pq_explode('_',$selected);

$obj=new $ref1Type($ref1Id);
if ($ref2Type) {
  $objList=new $ref2Type();
  if (property_exists($objList, "idProject") and property_exists($obj, "idProject")) {
    $crit = array ( 'idle'=>'0', 'idProject'=>($ref1Type=='Project')?$obj->id:$obj->idProject);
    $list=$objList->getSqlElementsFromCriteria($crit,false,null);
  } else {
  	$crit = array ( 'idle'=>'0');
  	$list=$objList->getSqlElementsFromCriteria($crit,false,null, 'id desc');
  }
} else {
  $list=array();
}
?>
<select id="pokerItemRef2Id" size="14" name="pokerItemRef2Id[]" multiple
onchange="selectPokerItemItem();"  ondblclick="savePokerItem();"
class="selectList" >
 <?php
 $found=array();
 foreach ($list as $lstObj) {
   $sel="";
   if (in_array($lstObj->id,$selectedArray)) {
    $sel=" selected='selected' ";
    $found[$lstObj->id]=true;
   }
   $val=$lstObj->name;
   echo "<option value='$lstObj->id'" . $sel . ">#".htmlEncode($lstObj->id)." - ".htmlEncode($val)."</option>";
 }
 foreach ($selectedArray as $selected) {
	 if ($selected and ! isset($found[$selected]) ) {
	   $lstObj=new $ref2Type($selected);
	   echo "<option value='$lstObj->id' selected='selected' >#".htmlEncode($lstObj->id)." - ".htmlEncode($lstObj->name)."</option>";
	 }
 }
 ?>
</select>