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
 * Save a note : call corresponding method in SqlElement Class
 * The new values are fetched in $_REQUEST
 */

require_once "../tool/projeqtor.php";
scriptLog('   ->/tool/selectStoredFilter.php');
$user=getSessionUser();
$comboDetail=false;
if (pq_array_key_exists('comboDetail',$_REQUEST)) {
  $comboDetail=true;
}
$idFilterFromFavoriteProject = RequestHandler::getValue('idFilterFromFavoriteProject');
$filterObjectClass=RequestHandler::getValue('filterObjectClass',true);
if (!isset($objectClass) or !$objectClass) $objectClass=$filterObjectClass;
if ($objectClass=='Planning' or $objectClass=='PlanningWorkPlan') $objectClass='PlanningElement';
else if ($objectClass=='GlobalPlanning' or $objectClass=='VersionsPlanning' or $objectClass=='ResourcePlanning') $objectClass='Activity';
else if (pq_substr($objectClass,0,7)=='Report_') $objectClass=pq_substr($objectClass,7);
else if ($objectClass=='ProjectDashboard') $objectClass='Project';
Security::checkValidClass($objectClass);


$name="";
$idLayout = null;

if (!$comboDetail) {
  if (pq_array_key_exists($filterObjectClass . "FilterName", $user->_arrayFilters)) $name = $user->_arrayFilters[$filterObjectClass . "FilterName"];
  if (pq_array_key_exists($filterObjectClass . "FilterLayout", $user->_arrayFilters))  $idLayout = $user->_arrayFilters[$filterObjectClass . "FilterLayout"];
} else {
  if (pq_array_key_exists($filterObjectClass . "FilterName", $user->_arrayFiltersDetail))  $name = $user->_arrayFiltersDetail[$filterObjectClass . "FilterName"];
  if (pq_array_key_exists($filterObjectClass . "FilterLayout", $user->_arrayFiltersDetail)) $idLayout = $user->_arrayFiltersDetail[$filterObjectClass . "FilterLayout"]; 
}

if (!$idLayout) $idLayout = RequestHandler::getId('idLayout');

htmldisplayFilterNameLayout($name,$idLayout,$filterObjectClass, $idFilterFromFavoriteProject);

?>
