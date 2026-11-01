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
scriptLog('   ->/tool/dynamicListUserStory.php');

$idProject = RequestHandler::getId('idProject');

$selected=null;
if (pq_array_key_exists('selected',$_REQUEST)) {
	$selected=$_REQUEST['selected'];
}
$selectedArray=pq_explode('_',$selected);

$crit = array ('idProject'=>$idProject, 'idle'=>'0');
$list = SqlList::getListWithCrit('UserStory', $crit, 'name', false);
?>
<select id="userStoryId" size="14" name="userStoryId[]" multiple
onchange="enableWidget('dialogUserStorySubmit');" <?php if (isNewGui()) echo ' style="width:410px;" ';?> class="selectList" ondblclick="saveUserStory();">
 <?php
 foreach ($list as $id=>$name) {
   $selected = (in_array($id, $selectedArray))?'SELECTED':'';
   echo "<option value='$id' $selected>$name</option>";
 }
 ?>
</select>