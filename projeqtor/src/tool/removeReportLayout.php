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
if (! pq_array_key_exists('reportLayoutObjectClass',$_REQUEST)) {
  throwError('reportLayoutObjectClass parameter not found in REQUEST');
}
$reportLayoutObjectClass=RequestHandler::getValue('reportLayoutObjectClass');

if (! pq_array_key_exists('idReportLayout',$_REQUEST)) {
  throwError('idReportLayout parameter not found in REQUEST');
}

if (!$comboDetail and pq_array_key_exists($reportLayoutObjectClass,$user->_arrayReportLayouts)) {
  $reportLayoutArray=$user->_arrayReportLayouts[$reportLayoutObjectClass];
} else {
  $reportLayoutArray=array();
}
$currentReportLayout="";
if (! $comboDetail and pq_array_key_exists($reportLayoutObjectClass,$user->_arrayReportLayouts)) {
  $currentReportLayout=$user->_arrayReportLayouts[$reportLayoutObjectClass]['id'];
}

$idReportLayout=$_REQUEST['idReportLayout']; // validated to be numeric value in SqlElement base constructor.
Sql::beginTransaction();
$reportLayout=new ReportLayout($idReportLayout);
$name=$reportLayout->scope;
$result=$reportLayout->delete();

$status=getLastOperationStatus($result);
if ($status=="OK"){
  $crit=array("idLayout"=>$idReportLayout ,"objectClass"=>$reportLayoutObjectClass, "idUser"=>$user->id, 'isReportList'=>'1');
  $layoutColumnSelector=new LayoutColumnSelector();
  $layoutColumnSelectorList = $layoutColumnSelector->getSqlElementsFromCriteria($crit);
  foreach ($layoutColumnSelectorList as $lColSelector){
    $lColSelector->delete();
  }
  $report = new Report();
  $reportLayoutList = $report->getSqlElementsFromCriteria(array('file'=>"reportObjectList.php?reportLayoutId=$idReportLayout"));
  foreach ($reportLayoutList as $report){
    $reportResult = $report->delete();
  }
}
$reportLayout=new ReportLayout();
$crit=array('idUser'=> $user->id, 'objectClass'=>$reportLayoutObjectClass);
$orderByReportLayout = "sortOrder ASC";
$reportLayoutList=$reportLayout->getSqlElementsFromCriteria($crit,false,null,$orderByReportLayout);
htmlDisplayStoredReportLayout($reportLayoutList,$reportLayoutObjectClass, $currentReportLayout);
echo "<div id='saveReportLayoutResult' align='center' style='z-index:9;position: absolute;left:50%;width:100%;margin-left:-50%;top:20px' >";
displayLastOperationStatus($result);
echo "</div>";
?>