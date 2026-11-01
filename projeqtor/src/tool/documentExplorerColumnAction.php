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
scriptLog('   ->/tool/documentExplorerColumnAction.php');

$user = getSessionUser();

$explorerType = RequestHandler::getValue('explorerType');
if ($explorerType != 'document') $explorerType = 'directory';
$objectClass = ($explorerType == 'document') ? 'DocumentExplorerDocument' : 'DocumentExplorerDirectory';

$action = RequestHandler::getValue('action');

// Known fields : nothing else may reach the database.
$known = array_keys(Parameter::getDocumentExplorerColumnDescription($explorerType));

function documentExplorerColumnRow($objectClass, $field, $position=null) {
  $user = getSessionUser();
  $col = SqlElement::getSingleSqlElementFromCriteria('ColumnSelector',
      array('idUser'=>$user->id, 'objectClass'=>$objectClass, 'field'=>$field));
  if (! $col or ! $col->id) {
    $col = new ColumnSelector();
    $col->idUser     = $user->id;
    $col->objectClass= $objectClass;
    $col->field      = $field;
    if ($position !== null) $col->sortOrder = intval($position);
  }
  $col->attribute = $col->field;
  $col->name      = $col->field;
  $col->scope     = 'list';
  return $col;
}

Sql::beginTransaction();

/* Rank of each field in the descriptor, used as the initial order of the
 * ColumnSelector rows created on the fly. */
$positions = array_flip(array_keys(Parameter::getDocumentExplorerColumnDescription($explorerType)));

if ($action == 'status') {
  $item = RequestHandler::getField('item');
  if (in_array($item, $known)) {
    $col = documentExplorerColumnRow($objectClass, $item,
        isset($positions[$item]) ? $positions[$item] : null);
    $col->hidden = (RequestHandler::getValue('status') == 'hidden') ? '1' : '0';
    $col->save();
  }

} else if ($action == 'width') {
  $item = RequestHandler::getField('item');
  if (in_array($item, $known)) {
    $col = documentExplorerColumnRow($objectClass, $item,
        isset($positions[$item]) ? $positions[$item] : null);
    $col->widthPct = intval(RequestHandler::getNumeric('width'));
    $col->save();
  }

} else if ($action == 'order') {
  $order = 0;
  foreach (pq_explode('|', RequestHandler::getValue('orderedList')) as $entry) {
    $field  = pq_trim($entry);
    if ($field === '') continue;
    $hidden = false;
    if (pq_strpos($field, 'hidden') === 0) {
      $hidden = true;
      $field  = pq_substr($field, 6);
    }
    if (! in_array($field, $known)) continue;
    $col = documentExplorerColumnRow($objectClass, $field);
    $col->sortOrder = $order;
    $col->hidden    = ($hidden) ? '1' : '0';
    $col->save();
    $order++;
  }

} else if ($action == 'reset') {
  $columnSelector = new ColumnSelector();
  $columnSelector->purge("objectClass='" . $objectClass . "' and idUser=" . $user->id);
}

Sql::commitTransaction();

// Descriptor recomputed : the static cache of Parameter still holds the values
// from before the write.
Parameter::resetDocumentExplorerColumnDescription($explorerType);
$desc = Parameter::getDocumentExplorerColumnDescription($explorerType);

$out = array();
foreach ($desc as $name => $d) {
  if (! isset($d['name'])) continue;
  $out[] = array(
    'name'     => $name,
    'show'     => (! empty($d['show'])) ? 1 : 0,
    'width'    => intval($d['width']),
    'minWidth' => intval($d['minWidth']),
    'order'    => intval($d['order']),
    'label'    => isset($d['label']) ? $d['label'] : '',
  );
}
echo json_encode(array('type'=>$explorerType, 'columns'=>$out));
?>
