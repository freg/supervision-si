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
scriptLog('   ->/tool/displayFiletrList.php');
$user=getSessionUser();
$context="";

$comboDetail=false;
if (pq_array_key_exists('comboDetail',$_REQUEST)) {
  $comboDetail=true;
}

// Get the filter info
if (! pq_array_key_exists('filterObjectClass',$_REQUEST)) {
	if (isset($objectClass)) {
		$filterObjectClass=$objectClass;
		$context="directFilterList";
	} else {
    throwError('filterObjectClass parameter not found in REQUEST');
	}
} else {
  $filterObjectClass=$_REQUEST['filterObjectClass'];
}
if (pq_array_key_exists('context',$_REQUEST)) {
	$context=$_REQUEST['context'];
}

// Get existing filter info
if (! $comboDetail and pq_array_key_exists($filterObjectClass,$user->_arrayFilters)) {
  $filterArray=$user->_arrayFilters[$filterObjectClass];
} else if ( $comboDetail and pq_array_key_exists($filterObjectClass,$user->_arrayFiltersDetail)) {
  $filterArray=$user->_arrayFiltersDetail[$filterObjectClass];
} else {
  $filterArray=array();
}

$currentFilter="";
if (! $comboDetail and ! $user->_arrayFilters) {
  $user->_arrayFilters=array();
} else if ($comboDetail and ! $user->_arrayFiltersDetail) {
  $user->_arrayFiltersDetail=array();
}
if (! $comboDetail and pq_array_key_exists($filterObjectClass . "FilterName",$user->_arrayFilters)) {
  $currentFilter=$user->_arrayFilters[$filterObjectClass . "FilterName"];
} else if ($comboDetail and pq_array_key_exists($filterObjectClass . "FilterName",$user->_arrayFiltersDetail)) {
  $currentFilter=$user->_arrayFiltersDetail[$filterObjectClass . "FilterName"];
}

$idFilterFromFavoriteProject = RequestHandler::getValue('idFilterFromFavoriteProject');

$flt=new Filter();
$res= new Resource();
$resTable= $res->getDatabaseTableName();
// PBER #7060
$sharedFilterObjectClass=$filterObjectClass;
if ($sharedFilterObjectClass=='Planning' or $sharedFilterObjectClass=='PlanningWorkPlan') $sharedFilterObjectClass='PlanningElement';
else if (pq_strlen($sharedFilterObjectClass)>=8 and pq_substr($sharedFilterObjectClass, -8)=='Planning') $sharedFilterObjectClass='Activity';

$clauseWhere=" idUser in (Select id from $resTable where id!=$user->id and idle=0 ) AND refType='$sharedFilterObjectClass' AND isShared=1 ";
$orderByLayout = "sortOrder ASC";
$filterList=$flt->getSqlElementsFromCriteria(null, false,$clauseWhere,$orderByLayout);

if($idFilterFromFavoriteProject)$filterList=array();

htmlDisplaySharedFilter($filterList,$filterObjectClass,$currentFilter, $context);

?>
