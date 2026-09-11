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

$comboDetail=false;
if (RequestHandler::isCodeSet('comboDetail')) {
  $comboDetail=true;
}

// Get the layout info
$reportLayoutObjectClass=RequestHandler::getValue('reportLayoutObjectClass');

if (!$comboDetail and pq_array_key_exists($reportLayoutObjectClass,$user->_arrayReportLayouts)) {
  $reportLayoutArray=$user->_arrayReportLayouts[$reportLayoutObjectClass];
} else {
  $reportLayoutArray=array();
}
$currentReportLayout="";
if (! $comboDetail and pq_array_key_exists($reportLayoutObjectClass,$user->_arrayReportLayouts)) {
  $currentReportLayout=$user->_arrayReportLayouts[$reportLayoutObjectClass]['id'];
}

$idReportLayout=RequestHandler::getId('idReportLayout',true); // validated to be numeric value in SqlElement base constructor.
Sql::beginTransaction();
$reportLayout=new ReportLayout($idReportLayout);
$name=$reportLayout->scope;
$message=i18n("resultShared");
if($reportLayout->isShared==1){
  $message=i18n("resultNoShared");
  $reportLayout->isShared=0;
}else{
  $reportLayout->isShared=1;
}
$result = $reportLayout->save();

$reportLayout=new ReportLayout();
$crit=array('idUser'=> $user->id, 'objectClass'=>$reportLayoutObjectClass);
$orderByReportLayout = "sortOrder ASC";
$reportLayoutList=$reportLayout->getSqlElementsFromCriteria($crit,false,null,$orderByReportLayout);
htmlDisplayStoredReportLayout($reportLayoutList,$reportLayoutObjectClass, $currentReportLayout);
echo "<div id='saveLayoutResult' align='center' style='z-index:9;position: absolute;left:50%;width:100%;margin-left:-50%;top:20px' >";
displayLastOperationStatus($result);
echo "</div>";
?>