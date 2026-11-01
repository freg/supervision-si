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
scriptLog('   ->/tool/displayFiletrList.php');
$user=getSessionUser();

$comboDetail=false;
if (pq_array_key_exists('comboDetail',$_REQUEST)) {
  $comboDetail=true;
}

// Get the layout info
$layoutObjectClass=$_REQUEST['layoutObjectClass'];

// Get existing layout info
if (! $comboDetail and pq_array_key_exists($layoutObjectClass,$user->_arrayLayouts)) {
  $layoutArray=$user->_arrayLayouts[$layoutObjectClass];
} else {
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
$res= new Resource();
$resTable= $res->getDatabaseTableName();
$clauseWhere=" idUser in (Select id from $resTable where id!=$user->id and idle=0 ) AND objectClass='$layoutObjectClass' AND isShared=1 ";
$layoutList=$lyt->getSqlElementsFromCriteria(null, false,$clauseWhere);

htmlDisplaySharedLayout($layoutList,$layoutObjectClass,$currentLayout);
?>