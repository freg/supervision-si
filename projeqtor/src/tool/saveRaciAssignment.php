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

require_once "../tool/projeqtor.php";

$projectId=$modelId=$roleId=null;
$assignIds=$affectableIds='';
if (pq_array_key_exists('projectId',$_REQUEST))    $projectId=$_REQUEST['projectId'];
if (pq_array_key_exists('modelId',$_REQUEST))      $modelId=$_REQUEST['modelId'];
if (pq_array_key_exists('roleId',$_REQUEST))       $roleId=$_REQUEST['roleId'];
if (pq_array_key_exists('assignId',$_REQUEST))     $assignIds=$_REQUEST['assignId'];
if (pq_array_key_exists('idAffectable',$_REQUEST)) $affectableIds=$_REQUEST['idAffectable'];
Security::checkValidId($projectId);
Security::checkValidId($modelId);
Security::checkValidId($roleId);

$project=new Project($projectId);
if (securityGetAccessRightYesNo('menuProject', 'update', $project)!="YES") {
  throwError('No access');
}

Sql::beginTransaction();
// Default result (valid OK status) so the matrix always refreshes, even when
// every dropped item is a duplicate (nothing actually saved).
$result=htmlSetResultMessage(null, '', false, '', 'update', 'OK');
// Move existing assignments to this role (several allowed)
foreach (explode(',', $assignIds) as $assignId) {
  if (! pq_trim($assignId)) continue;
  Security::checkValidId($assignId);
  $assign=new RaciAssignment($assignId);
  if ($assign->id and $assign->idProject==$projectId) {
    $assign->idRaciRole=$roleId;
    $result=$assign->save();
  }
}
// Create assignments from dropped affectables (several allowed)
foreach (explode(',', $affectableIds) as $idAffectable) {
  if (! pq_trim($idAffectable)) continue;
  Security::checkValidId($idAffectable);
  // Skip if already present for this role
  $existing=SqlElement::getSingleSqlElementFromCriteria('RaciAssignment',
              array('idProject'=>$projectId,'idRaciModel'=>$modelId,'idRaciRole'=>$roleId,
                    'resourceType'=>'Affectable','resourceId'=>$idAffectable));
  if (! ($existing and $existing->id)) {
    $assign=new RaciAssignment();
    $assign->idProject=$projectId;
    $assign->idRaciModel=$modelId;
    $assign->idRaciRole=$roleId;
    $assign->resourceType='Affectable';
    $assign->resourceId=$idAffectable;
    $result=$assign->save();
  }
}
$status=getLastOperationStatus($result);
if ($status=="OK" or $status=="NO_CHANGE" or $status=="INCOMPLETE") {
  Sql::commitTransaction();
} else {
  Sql::rollbackTransaction();
}
?>
