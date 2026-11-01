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

$list=RequestHandler::getClass("list");
$idProject=RequestHandler::getId("idProject");
$vals=SqlList::getList($list);
$hidden=ListHideValue::getValuesArray($idProject, $list);
?>
<table style="width:100%;user-select:none">
<?php foreach ($vals as $valId=>$valName) {
  $value=(isset($hidden[$valId]))?'YES':'NO';
  ?>
 <tr class="dojoxGridRow">
   <td style="width:11%; text-align:center" class="dojoxGridCell "><?php echo $valId;?></td>
   <td style="width:80%; padding-left:10px" class="dojoxGridCell "><?php echo $valName;?></td>
   <td style="width:10%; text-align:center" class="dojoxGridCell "><div style="display:<?php echo ($value=='YES')?'none':'block'; ?>" id="hiddenNo_<?php echo $valId;?>" class="iconHiddenNo" onClick="storeValueHidden('<?php echo $list;?>',<?php echo $valId;?>,true);"></div><div style="display:<?php echo ($value!='YES')?'none':'block'; ?>" id="hidden_<?php echo $valId;?>" class="iconHidden" onClick="storeValueHidden('<?php echo $list;?>',<?php echo $valId;?>,false);"></div></td>
 </tr>
<?php }?>
</table>