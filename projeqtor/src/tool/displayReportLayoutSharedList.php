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
scriptLog('   ->/tool/displayReportLayoutSharedList.php');
$user=getSessionUser();

$comboDetail=false;
if (pq_array_key_exists('comboDetail',$_REQUEST)) {
  $comboDetail=true;
}

// Get the layout info
$reportLayoutObjectClass=$_REQUEST['reportLayoutObjectClass'];

// Get existing layout info
if (! $comboDetail and pq_array_key_exists($reportLayoutObjectClass,$user->_arrayReportLayouts)) {
  $reportLayoutArray=$user->_arrayReportLayouts[$reportLayoutObjectClass];
} else {
  $reportLayoutArray=array();
}

$currentReportLayout="";
if (! $comboDetail and ! $user->_arrayReportLayouts) {
  $user->_arrayReportLayouts=array();
}
if (! $comboDetail and pq_array_key_exists($reportLayoutObjectClass,$user->_arrayReportLayouts)) {
  $currentReportLayout=$user->_arrayReportLayouts[$reportLayoutObjectClass]['id'];
}

$reportLayout=new ReportLayout();
$res= new Resource();
$resTable= $res->getDatabaseTableName();
$clauseWhere=" idUser in (Select id from $resTable where id!=$user->id and idle=0 ) AND objectClass='$reportLayoutObjectClass' AND isShared=1 ";
$reportLayoutList=$reportLayout->getSqlElementsFromCriteria(null, false,$clauseWhere);

htmlDisplaySharedReportLayout($reportLayoutList,$reportLayoutObjectClass,$currentReportLayout);
?>