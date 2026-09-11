<?php
use PhpOffice\PhpSpreadsheet\Shared\Date;
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

/** ============================================================================
 * Save some information about planning columns status.
 */
require_once "../tool/projeqtor.php";

$id=pq_trim((RequestHandler::isCodeSet('id'))?RequestHandler::getValue('id'):'');
$obj=pq_trim((RequestHandler::isCodeSet('object'))?RequestHandler::getValue('object'):'');
$idObj=pq_trim((RequestHandler::isCodeSet('idObj'))?RequestHandler::getValue('idObj'):'');
$startDate=pq_trim((RequestHandler::isCodeSet('startDate'))?pq_strtotime(RequestHandler::getValue('startDate')):'');
$endDate=pq_trim((RequestHandler::isCodeSet('endDate'))?pq_strtotime(RequestHandler::getValue('endDate')):'');
$resizer=RequestHandler::getValue('resizer',false,null);
$user=getSessionUser();

$newStartDate = date('Y-m-d',$startDate);
$newEndDate = date('Y-m-d',$endDate);

if ($obj and SqlElement::class_exists($obj)) {
  $referenced=new $obj($idObj);
  $canUpdate=(securityGetAccessRightYesNo('menu' . $obj, 'update', $referenced)=='YES');
  if (! $canUpdate) {
    echo i18n('errorUpdateRights');
    exit;
  }
}

$object=SqlElement::getSingleSqlElementFromCriteria('PlanningElement', array("id"=>$id ,"refType"=>$obj, "refId"=>$idObj));
Sql::beginTransaction();

$pm=SqlList::getFieldFromId('PlanningMode', $object->idPlanningMode, "code");
if ($pm=='START' || $pm=='STARR') {
  $object->validatedStartDate=$newStartDate;
  if ($object->validatedEndDate) $object->validatedEndDate=$newEndDate;
}
if ($pm=='ALAP') {
  $object->validatedEndDate=$newEndDate;
  if ($object->validatedStartDate) $object->validatedStartDate=$newStartDate;
}
if ($pm=='FDUR' ) {
  $object->validatedDuration=workDayDiffDates($newStartDate, $newEndDate, $object->idProject);
  if ($object->validatedStartDate) $object->validatedStartDate=$newStartDate;
  if ($object->validatedEndDate) $object->validatedEndDate=$newEndDate;
}
if ($pm=='DDUR' or $pm=='CDUR') {
  if ($resizer != 'start')$object->validatedDuration=workDayDiffDates($newStartDate, $newEndDate, $object->idProject);
  if ($newStartDate and ($resizer=='start' or $object->validatedStartDate)) $object->validatedStartDate=$newStartDate;
  if ($newEndDate and $object->validatedEndDate) $object->validatedEndDate=$newEndDate;
}

if ($pm=='REGUL' or $pm=='QUART' or $pm=='HALF' or $pm=='FULL') {
  $object->validatedStartDate=$newStartDate;
  $object->validatedEndDate=$newEndDate;
}
$object->plannedStartDate=$newStartDate;
$object->plannedEndDate=$newEndDate;
$object->plannedDuration=workDayDiffDates($newStartDate, $newEndDate, $object->idProject);

$result=$object->save();
echo 'OK';

Sql::commitTransaction();
?>