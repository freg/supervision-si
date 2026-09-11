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

/** ===========================================================================
 * Save a layout : call corresponding method in SqlElement Class
 * The new values are fetched in $_REQUEST
 */

require_once "../tool/projeqtor.php";

$user=getSessionUser();
$name = RequestHandler::getValue('saveGroup');
$tab = RequestHandler::getValue('tab');
$tabIdUser = explode('-',$tab);

echo "<div id='saveGroupResult' style='z-index:9;position: absolute;left:50%;width:100%;margin-left:-50%;top:20px' >";
echo '<table width="100%"><tr><td align="center" >';
echo '<span class="messageOK" style="z-index:999;position:relative;top:7px;padding:10px 20px;white-space:nowrap" >' . i18n('colGroup') . " '" . htmlEncode($name) . "' " . i18n('resultUpdated').'</span>';
echo '</td></tr></table>';
echo "</div>";

Sql::beginTransaction();

$layGroup=new LayoutGroup();

$layGroup = LayoutGroup::getSingleSqlElementFromCriteria('LayoutGroup', array('idUser'=>$user->id, 'name'=>$name));
if(!$layGroup->id){
  $layGroup->idUser = $user->id;
  $layGroup->name = $name;
  $layGroup->save();
  
  foreach ($tabIdUser as $idUser){
    if(!$idUser)continue;
    $layoutUser = new LayoutGroupUser();
    $layoutUser->idLayoutGroup = $layGroup->id;
    $layoutUser->idUser = $idUser;
    $layoutUser->save();
  } 
}else{
  $layoutUser = new LayoutGroupUser();
  $layoutUserList = $layoutUser->getSqlElementsFromCriteria(array('idLayoutGroup'=>$layGroup->id));
  if($layoutUserList){
    foreach ($layoutUserList as $oldLayoutUser){
      $oldLayoutUser->delete();
    }
  }
  foreach ($tabIdUser as $idUser){
    if(!$idUser)continue;
    $layoutUser = new LayoutGroupUser();
    $layoutUser->idLayoutGroup = $layGroup->id;
    $layoutUser->idUser = $idUser;
    $layoutUser->save();
  }
}

echo "<input type='hidden' id='newIdLayoutGroup' name='newIdLayoutGroup' value='$layGroup->id'>";
Sql::commitTransaction();
?>