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
scriptLog('   ->/tool/documentExplorerMove.php');

$items  = RequestHandler::getValue('items');
$target = RequestHandler::getValue('target');

$moved   = 0;
$refused = array();
// Charges utiles brutes de save(), pour le bandeau de resultat standard : un refus
// l'emporte sur un succes, l'ecran devant montrer ce qui a bloque.
$firstInvalidResult = null;
$lastOkResult       = null;

/** Whole request failure : the target itself cannot be used. */
function documentExplorerMoveAbort($reason) {
  echo json_encode(array('moved'=>0, 'refused'=>array(
      array('label'=>'', 'reason'=>$reason))));
}

$idTarget = null;
if ($target != 'root') {
  if (pq_substr($target, 0, 10) != 'directory:') {
    documentExplorerMoveAbort('invalid target');
    return;
  }
  $idTarget = intval(pq_substr($target, 10));
  if (! $idTarget) {
    documentExplorerMoveAbort('invalid target');
    return;
  }
  $targetDir = new DocumentDirectory($idTarget);
  if (! $targetDir->id) {
    documentExplorerMoveAbort('unknown target');
    return;
  }
}

foreach (pq_explode(',', $items) as $item) {
  $parts = pq_explode(':', $item);
  if (count($parts) != 2) continue;
  $refType = $parts[0];
  $refId   = intval($parts[1]);
  if (! $refId) continue;
  if ($refType != 'Document' and $refType != 'DocumentDirectory') continue;

  $obj = new $refType($refId);
  if (! $obj->id) continue;
  $label = $obj->name;

  if ($refType == 'Document' and ! $idTarget) {
    $refused[] = array('label'=>$label,
        'reason'=>i18n('messageMandatory', array(i18n('colIdDocumentDirectory'))));
    continue;
  }

  if ($refType == 'DocumentDirectory' and $idTarget) {
    $parentId = $idTarget;
    $depth = 0;
    $cycle = false;
    while ($parentId and $depth < 100) {
      if ($parentId == $obj->id) { $cycle = true; break; }
      $parent = new DocumentDirectory($parentId);
      $parentId = $parent->idDocumentDirectory;
      $depth++;
    }
    if ($cycle) {
      $refused[] = array('label'=>$label, 'reason'=>i18n('errorHierarchicLoop'));
      continue;
    }
  }

  $currentParent = ($obj->idDocumentDirectory) ? intval($obj->idDocumentDirectory) : null;
  if ($currentParent === $idTarget) continue;

  $obj->idDocumentDirectory = ($idTarget) ? $idTarget : null;

  if (! $idTarget and $refType == 'DocumentDirectory') {
    $obj->location = '';
  }

  $result = $obj->save();
  if (pq_strpos($result, 'id="lastOperationStatus" value="OK"')) {
    $moved++;
    $lastOkResult = $result;
  } else {
    $refused[] = array('label'=>$label, 'reason'=>pq_trim(strip_tags($result)));
    if ($firstInvalidResult === null) $firstInvalidResult = $result;
  }
}

echo json_encode(array('moved'=>$moved, 'refused'=>$refused,
    'message'=>($firstInvalidResult !== null) ? $firstInvalidResult : $lastOkResult));
?>
