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
 * The new values are fetched in REQUEST
 */

require_once "../tool/projeqtor.php";
scriptLog('   ->/tool/displayLayoutList.php');
$user=getSessionUser();
$comboDetail=false;
if (RequestHandler::isCodeSet('comboDetail')) {
  $comboDetail=true;
}

// Get the layout info
$layoutObjectClass=RequestHandler::getValue('layoutObjectClass');
if (!isset($objectClass) or !$objectClass) $objectClass=$layoutObjectClass;

// Get existing layout info
if (! $comboDetail and pq_array_key_exists($layoutObjectClass,$user->_arrayLayouts)) {
  $layoutArray=$user->_arrayLayouts[$layoutObjectClass];
}else {
  $layoutArray=array();
}
$currentLayout="";
if (! $comboDetail and ! $user->_arrayLayouts) {
  $user->_arrayLayouts=array();
}
if (! $comboDetail and pq_array_key_exists($layoutObjectClass,$user->_arrayLayouts)) {
  $currentLayout=$user->_arrayLayouts[$layoutObjectClass]['id'];
}

$lyt=new Layout();
$crit=array('idUser'=> $user->id, 'objectClass'=>$objectClass);
$orderByLayout = "sortOrder ASC";
$layoutList=$lyt->getSqlElementsFromCriteria($crit,false,null,$orderByLayout);

htmlDisplayStoredLayout($layoutList,$layoutObjectClass,$currentLayout, $comboDetail);

?>