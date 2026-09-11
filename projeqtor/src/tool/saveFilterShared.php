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
$filterShared = new Filter($idFilter);
$userFilterShared = new User($filterShared->idUser);

$flt=new Filter();
$crit=array('idUser'=> $user->id, 'refType'=>$filterShared->refType );
$orderByFilter = "sortOrder ASC";
$filterList=$flt->getSqlElementsFromCriteria($crit,false,null,$orderByFilter);

$maxSortOrder = 0;
foreach ($filterList as $filter) {
  if (isset($filter->sortOrder) && $filter->sortOrder > $maxSortOrder) {
    $maxSortOrder = $filter->sortOrder;
  }
}
Sql::beginTransaction();

$filter = new Filter();
$filter->name = $filterShared->name . ' (' . $userFilterShared->name .')';
$filter->refType = $filterShared->refType;
$filter->idUser = $user->id;
$filter->isShared = 0;
$filter->isDynamic = $filterShared->isDynamic;
$filter->sortOrder = $maxSortOrder + 1;
$filter->idLayout = $filterShared->idLayout;
$filter->save();

$filterCrit = new FilterCriteria();
$listFilterCriteria = $filterCrit->getSqlElementsFromCriteria(array('idFilter'=>$filterShared->id));
foreach ($listFilterCriteria as $filCrit){
  $filterCriteria = new FilterCriteria();
  $props = get_object_vars($filCrit);
  $excluded = ['id', 'idFilter'];
  foreach ($props as $key => $value) {
    if (!in_array($key, $excluded)) {
      $filterCriteria->$key = $value;
    }
  }
  $filterCriteria->idFilter = $filter->id;
  $filterCriteria->save();
}

echo "<div id='saveFilterResult' style='z-index:9;position: absolute;left:50%;width:100%;margin-left:-50%;top:20px' >";
echo '<table width="100%"><tr><td align="center" >';
echo '<span class="messageOK" style="z-index:999;position:relative;top:7px;padding:10px 20px;white-space:nowrap" >' . i18n('colFilter') . " '" . htmlEncode($filter->name) . "' " . i18n('resultSave') . ' (#'.htmlEncode($filter->id).')</span>';
echo '</td></tr></table>';
echo "</div>";

$filterList[] = $filter;
htmlDisplayStoredFilter($filterList,$filterShared->refType,"","",null);
Sql::commitTransaction();
?>