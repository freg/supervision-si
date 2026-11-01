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
 * Re-render the RACI matrix for a project (read-only, used when the selected
 * RACI model changes on the project screen or after assignment updates).
 */
require_once "../tool/projeqtor.php";

$modelId=$projectId=null;
if (pq_array_key_exists('modelId',$_REQUEST))   $modelId=$_REQUEST['modelId'];
if (pq_array_key_exists('projectId',$_REQUEST)) $projectId=$_REQUEST['projectId'];
Security::checkValidId($projectId);

if (! $modelId) {
  echo '<i>'.i18n('raciSelectModel').'</i>';
  return;
}
Security::checkValidId($modelId);

$project=new Project($projectId);
if (securityGetAccessRightYesNo('menuProject', 'read', $project)!="YES") {
  throwError('No access');
}
$model=new RaciModel($modelId);
if (! $model->id) {
  echo '<i>'.i18n('raciSelectModel').'</i>';
  return;
}
echo $model->drawMatrix(false, $projectId);
?>
