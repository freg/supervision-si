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

/* ============================================================================
 * Presents the list of objects of a given class.
 *
 */
require_once "projeqtor.php";
require_once "formatter.php";
scriptLog('   ->/view/refreshCriticalResources.php'); 

$proj = RequestHandler::getValue('idProjectCriticalResources');
$scale = RequestHandler::getValue('scaleCriticalResources');
$calculDate = RequestHandler::getValue('startDateCalculPlanning');
$firstDay = RequestHandler::getValue('startDateCriticalResources');
$lastDay = RequestHandler::getValue('endDateCriticalResources');
$maxResources = RequestHandler::getValue('nbCriticalResourcesValue');
//$idResourceSelected = RequestHandler::getValue('criticalResourceGraph');

$refreshData = RequestHandler::getValue('refreshData');

if ($refreshData) {
  Affectable::unsetCriticalResourcePlanningResult();
}

$lastDayStored=Affectable::getCriticalResourcePlanningResult();
if (! $lastDayStored or $lastDayStored!=$calculDate) {
  PlannedWork::plan('*',$calculDate,false,true,true);
  Affectable::storeCriticalResourcePlanningResult($calculDate);
}

$displayData = true;
if ($lastDay < $firstDay) {
  $displayData = false;
}

 if ($lastDay != null && $firstDay !=null && $scale !=null && $displayData) { 
   $hide=true;
   $selectedTab = getSessionValue('criticalSelectedTab');
   include '../view/criticalResourcesTabs.php';
 } else { 
  echo '<div style="background:#FFDDDD;font-size:150%;color:#808080;text-align:center;padding:15px 0px;width:100%;">'.i18n('noDataFound').'</div>';
  }?>