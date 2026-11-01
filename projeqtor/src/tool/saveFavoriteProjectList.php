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
 * Save a filter : call corresponding method in SqlElement Class
 * The new values are fetched in $_REQUEST
 */

require_once "../tool/projeqtor.php";

$user=getSessionUser();
$name=pq_trim(RequestHandler::getValue('favoriteProjectListName'));
$mode = RequestHandler::getValue('mode');
$idFavoriteList = RequestHandler::getId('idFavoriteList');
$idFavoriteProjectList = getSessionValue('idFavoriteProjectList');
$favoriteProjectsArray = Parameter::getUserParameter('favoriteProjectsArray');

Sql::beginTransaction();
$favoritePl = new FavoriteProjectList();
if($idFavoriteList){
  $favoritePl = new FavoriteProjectList($idFavoriteList);
  $favItem = new FavoriteProjectItem();
  $favoriteProjectItemList = $favItem->getSqlElementsFromCriteria(array('idFavoriteProjectList'=>$idFavoriteList));
  foreach ($favoriteProjectItemList as $favoriteItem){
    $favoriteItem->delete();
  }
  $favoritePl->delete();
  $idFavoriteProjectList = '';
}else{
  if ($name) {
	$favoriteProjectsList = pq_explode(',', $favoriteProjectsArray);
  	$favoritePl = FavoriteProjectList::getSingleSqlElementFromCriteria('FavoriteProjectList', array('name'=>$name, 'idUser'=>$user->id));
  	$favoritePl->name = $name;
  	$favoritePl->idUser = $user->id;
  	$sortOrder = ($favoritePl->getMaxValueFromCriteria('sortOrder', array('idUser'=>$user->id)))+10;
  	$favoritePl->sortOrder = $sortOrder;
  	$favoritePl->save();
  	$idFavoriteProjectList = $favoritePl->id;
  	$favItem = new FavoriteProjectItem();
  	$favoriteProjectItemList = $favItem->getSqlElementsFromCriteria(array('idFavoriteProjectList'=>$favoritePl->id));
    foreach ($favoriteProjectItemList as $favoriteItem){
      $favoriteItem->delete();
    }
  	foreach ($favoriteProjectsList as $idProject){
  		$favProjItem = new FavoriteProjectItem();
  		$favProjItem->idProject = $idProject;
  		$favProjItem->idFavoriteProjectList = $favoritePl->id;
  		$favProjItem->save();
  	}
  }
  if(!$mode){
    echo "<div id='saveFavoriteProjectResult' style='z-index:999;position: absolute;left:50%;width:100%;margin-left:-50%;top:20px' >";
    echo '<table width="100%"><tr><td align="center" >';
    echo '<span class="messageOK" style="z-index:999;position:relative;top:7px;padding:10px 20px;white-space:nowrap" >' . i18n('colFavoriteProjectList') . " '" . htmlEncode($name) . "' " . i18n('resultUpdated') . ' (#'.htmlEncode($favoritePl->id).')</span>';
    echo '</td></tr></table>';
    echo "</div>";
  }
}

Sql::commitTransaction();

if(!$mode){
  $fav=new FavoriteProjectList();
  $crit=array('idUser'=> $user->id);
  $orderByFilter = "name ASC";
  $favoriteList=$fav->getSqlElementsFromCriteria($crit,false,null,$orderByFilter);
  $favoriteProjFlatList = implode(',', SqlList::getListWithCrit('FavoriteProjectList', array('idUser'=>$user->id), 'id'));
  $fontSize = (!isNewGui())?'font-size:8pt;':'';
  $width = (isNewGui())?'10px;float:left':'6px;';
  echo '<input type="hidden" id="idSelectedFavoriteProject" name="idSelectedFavoriteProject" value="'.$idFavoriteProjectList.'" />';
  echo '<table width="100%" id="dndListFavoriteSelector" jsId="dndListFavoriteSelector" dojotype="dojo.dnd.Source" withhandles="true" data-dojo-props="accept: [\'tableauFavoriteList\']">';
  if(count($favoriteList)>0){
    echo '<tr style="height:22px;">';
    echo ' <td colspan="3" style="cursor:pointer;'.$fontSize.'font-style:italic;padding:5px;height: 22px;"';
    echo ' class="filterData ganttTaskrow" onClick="selectFavoriteProjectList(\''.$favoriteProjectsArray.'\', \'\');" title="'.i18n("resetFavoriteList").'">'.i18n('noFavorite').'</td>';
    echo '</tr>';
    foreach ($favoriteList as $favoriteProject){
      $favoriteProjectItemList = SqlList::getListWithCrit('FavoriteProjectItem', array('idFavoriteProjectList'=>$favoriteProject->id), 'idProject');
      $favoriteProjectItemList = implode(',', $favoriteProjectItemList);
      $selectedListClass = ($favoriteProject->id == $idFavoriteProjectList)?'dojoDndItemAnchor':'';
      $selectedBackgroundColor = ($favoriteProject->id == $idFavoriteProjectList)?'favoriteProjectListSelected':'';
      echo '<tr class="dojoDndItem '.$selectedListClass.' ganttTaskrow" dndType="tableauFavoriteList" id="favoriteList'.$favoriteProject->id.'">';
      echo '<input type="hidden" id="favoriteProjectList_'.$favoriteProject->id.'" name="favoriteProjectList_'.$favoriteProject->id.'" value="'.$favoriteProjectItemList.'" />';
      echo '  <td style="cursor:pointer;'.$fontSize.'font-style:italic;padding:5px;height: 22px;"';
      echo '    class="filterData '.$selectedBackgroundColor.'" onClick="selectFavoriteProjectList(\''.$favoriteProjectItemList.'\', \''.$favoriteProject->id.'\');" title="'.i18n("selectStoredFavorite").'">';
      //echo '     <span class="dojoDndHandle handleCursor"><img style="width:'.$width.'" src="css/images/iconDrag.gif" />&nbsp;&nbsp;</span>';
      echo '     <span id="favoriteProjectName_'.$favoriteProject->id.'" style="position:relative;top:2px;margin:3px">'.htmlEncode($favoriteProject->name).'</span></td>';
      echo '  </td>';
      echo '  <td class="filterData dndHidden" width="16px" align="center" style="height: 22px;">';
      echo '     <a onClick="selectFavoriteProjectList(\''.$favoriteProjectItemList.'\', \''.$favoriteProject->id.'\', true)" title="'.i18n('editStoredFavorite').'">';
      echo         formatSmallButton('Edit');
      echo '     </a>';
      echo '  </td>';
      echo '  <td class="filterData dndHidden" width="16px" align="center" style="height: 22px;">';
      echo '    <a src="css/images/smallButtonRemove.png" onClick="removeFavoriteProjectList(\''.$favoriteProjFlatList.'\', \''.htmlEncode($favoriteProject->id).'\')" title="'.i18n('removeStoredFavorite').'">';
      echo formatSmallButton('Remove');
      echo '    </a>';
      echo '  </td>';
      echo '</tr>';
    }
  }else{
    echo '<tr style="height:22px;">';
    echo ' <td colspan="3" style="cursor:pointer;'.$fontSize.'font-style:italic;padding:5px;height: 22px;"';
    echo ' class="filterData ganttTaskrow" onClick="selectFavoriteProjectList(\''.$favoriteProjectsArray.'\',\'\');" title="'.i18n("resetFavoriteList").'">'.i18n('noFavorite').'</td>';
    echo '</tr>';
  }
  echo '</table>';
}else{
  echo $idFavoriteProjectList;
}
?>