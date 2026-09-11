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

$assignId=$modelId=$projectId=null;
if (pq_array_key_exists('assignId',$_REQUEST))  $assignId=$_REQUEST['assignId'];
if (pq_array_key_exists('modelId',$_REQUEST))   $modelId=$_REQUEST['modelId'];
if (pq_array_key_exists('projectId',$_REQUEST)) $projectId=$_REQUEST['projectId'];
Security::checkValidId($assignId);
Security::checkValidId($modelId);
Security::checkValidId($projectId);

$project=new Project($projectId);
if (securityGetAccessRightYesNo('menuProject', 'update', $project)!="YES") {
  throwError('No access');
}

Sql::beginTransaction();
$result='';
$assign=new RaciAssignment($assignId);
if ($assign->id and $assign->idProject==$projectId) {
  $result=$assign->delete();
}

$status=getLastOperationStatus($result);
if ($status=="OK" or $status=="NO_CHANGE" or $status=="INCOMPLETE") {
  Sql::commitTransaction();
} else {
  Sql::rollbackTransaction();
}
?>
