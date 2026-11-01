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

$idFilter=RequestHandler::getId('idFilter');
$mode = RequestHandler::getValue('mode');
$filter = new Filter($idFilter);
$displayResult = '';

Sql::beginTransaction();
if($mode == 'add'){
  $filter->isFavoriteProject = 1;
  $displayResult = i18n('addedFilterToFavoriteProjectList', array(htmlEncode($filter->name)));
}else if ($mode == 'remove'){
  $filter->isFavoriteProject = 0;
  $displayResult = i18n('removedFilterFromFavoriteProjectList', array(htmlEncode($filter->name)));
}
$result = $filter->save();
$status = getLastOperationStatus($result);
if($status == 'OK'){
  $result = $displayResult;
  if($mode == 'add'){
    $favoriteProject = new FavoriteProjectList();
    $favoriteProject->idUser = $user->id;
    $favoriteProject->name = $filter->name;
    $favoriteProject->idFilter = $filter->id;
    $favoriteProject->save();
  }else if ($mode == 'remove'){
    $favoriteProject = FavoriteProjectList::getSingleSqlElementFromCriteria('FavoriteProjectList', array('idFilter'=>$filter->id));
    $idFavoriteProjectList = getSessionValue('idFavoriteProjectList');
    if($favoriteProject->id == $idFavoriteProjectList){
      Parameter::storeUserParameter('idFavoriteProjectList', '');
      setSessionValue('idFavoriteProjectList', '');
    }
    
    $favoriteProject->delete();
  }
}

echo "<div id='saveFilterResult' style='z-index:9;position: absolute;left:50%;width:100%;margin-left:-50%;top:20px' >";
echo '<table width="100%"><tr><td align="center" >';
echo '<span class="message'.$status.'" style="z-index:999;position:relative;top:7px;padding:10px 20px;white-space:nowrap" >' . $result .'</span>';
echo '</td></tr></table>';
echo "</div>";

$flt=new Filter();
$crit=array('idUser'=> $user->id, 'refType'=>$filter->refType );
$orderByFilter = "sortOrder ASC";
$filterList=$flt->getSqlElementsFromCriteria($crit,false,null,$orderByFilter);

htmlDisplayStoredFilter($filterList,$filter->refType,"","",null);
Sql::commitTransaction();
?>