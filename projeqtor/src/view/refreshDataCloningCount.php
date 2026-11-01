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
require_once "../tool/projeqtor.php";
require_once "../tool/formatter.php";
scriptLog('   ->/view/refreshDataCloningList.php'); 

$dataCloning = new DataCloning();
$date = date('Y-m-d');
$addDate =  addDaysToDate(date('Y-m-d'), 1);
$wherePerDay = "requestedDate > '$date' and requestedDate < '$addDate' ";
$dataCloningCountPerDay = $dataCloning->countSqlElementsFromCriteria(null, $wherePerDay);
$dataCloningPerDay = Parameter::getGlobalParameter('dataCloningPerDay');
$dataCloningCount = i18n('colDataCloningCount', array($dataCloningPerDay-$dataCloningCountPerDay, $dataCloningPerDay));
$dataCloningCountTitle="";
$width=RequestHandler::getValue("destinationWidth");
if ($width < 1500) {
  $dataCloningCountTitle=$dataCloningCount;
  $dataCloningCount = i18n('colLeft'). " : " . intval($dataCloningPerDay-$dataCloningCountPerDay) . "/" . $dataCloningPerDay;
}
?>
<div id="dataCloningRequestorCount" title="<?php echo $dataCloningCountTitle;?>">
  <?php echo $dataCloningCount;?>
</div>
