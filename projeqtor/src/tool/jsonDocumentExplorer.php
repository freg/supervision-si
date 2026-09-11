<?php
/* * * COPYRIGHT NOTICE *********************************************************
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
 * ** DO NOT REMOVE THIS NOTICE *********************************************** */

require_once "../tool/projeqtor.php";
require_once "../tool/documentExplorerTreeData.php";
scriptLog('   ->/tool/jsonDocumentExplorer.php');

// --------------------------------------------------------------- columns ---
$defaultWidths = array('id' => 60, 'name' => 260);

$explorerColumns = array();
$order = 0;
foreach (ColumnSelector::getColumnsList('Document') as $col) {
  if (! SqlElement::isVisibleField($col->attribute)) continue;
  $formatter = $col->formatter;
  if ($formatter == 'numericFormatter' and $col->field == 'id') $formatter = 'idFormatter';
  if ($col->attribute == 'hatchPattern')                        $formatter = 'hatchPatternFormatter';

  $width = isset($defaultWidths[$col->field]) ? $defaultWidths[$col->field] : 120;
  $maxWidth = ($col->field == 'name') ? 300 : 600;

  $explorerColumns[] = array(
    'field'     => $col->field,
    'attribute' => $col->attribute,
    'label'     => $col->_displayName,
    'width'     => min($maxWidth, $width),
    'minWidth'  => 50,
    'maxWidth'  => $maxWidth,
    'order'     => $order,
    'formatter' => $formatter,
    'show'      => ($col->hidden) ? 0 : 1,
  );
  $order++;
}

$explorerCollapsed = array();
$collapsedPrefix   = 'Planning_DocumentDirectory_';
foreach (array_keys(Collapsed::getCollaspedList()) as $collapsedScope) {
  if (pq_strpos($collapsedScope, $collapsedPrefix) !== 0) continue;
  $c = intval(pq_substr($collapsedScope, pq_strlen($collapsedPrefix)));
  if ($c) $explorerCollapsed[$c] = true;
}

// ------------------------------------------------- repositories : items ---
$tree = getDocumentExplorerTree();

$counters   = array();   // per level
$pathByDir  = array();   // directory id => wbs path
$hiddenMap  = array();
$explorerItems = array();

foreach ($tree as $row) {
  $level  = $row['level'];
  $parent = $row['parent'];

  if (! isset($counters[$level])) $counters[$level] = 0;
  $counters[$level]++;
  // Deeper counters restart under a new parent.
  foreach (array_keys($counters) as $lvl) {
    if ($lvl > $level) unset($counters[$lvl]);
  }

  $prefix = ($parent and isset($pathByDir[$parent])) ? $pathByDir[$parent] . '-' : '';
  $wbs    = $prefix . str_pad($counters[$level], 5, '0', STR_PAD_LEFT);
  $pathByDir[$row['id']] = $wbs;

  $hiddenMap[$row['id']] = ($parent and (isset($explorerCollapsed[$parent]) or ! empty($hiddenMap[$parent])));

  $explorerItems[] = array(
    'id'          => (string) $row['id'],
    'refid'       => (string) $row['id'],
    'reftype'     => 'DocumentDirectory',
    'refname'     => $row['name'],
    'name'        => $row['name'],
    'wbs'         => $wbs,
    'wbssortable' => $wbs,
    'topid'       => ($parent) ? (string) $parent : '',
    'level'       => $row['level'],
    'hidden'      => $hiddenMap[$row['id']] ? '1' : '0',
    'haschild'    => $row['hasChild'] ? '1' : '0',
    'elementary'  => $row['hasChild'] ? '0' : '1',
    'collapsed'   => isset($explorerCollapsed[$row['id']]) ? '1' : '0',
    'canupdate'   => $row['canUpdate'] ? '1' : '0',
    'candelete'   => $row['canDelete'] ? '1' : '0',
    'location'    => isset($row['location'])  ? $row['location']  : '',
    'idproject'   => isset($row['idProject']) ? $row['idProject'] : '',
    'project'     => isset($row['project'])   ? $row['project']   : '',
    'idproduct'   => isset($row['idProduct']) ? $row['idProduct'] : '',
    'product'     => isset($row['product'])   ? $row['product']   : '',
    'idle'        => isset($row['idle'])      ? $row['idle']      : '0',
  );
}

$currentDirectory = sessionValueExists('Directory') ? getSessionValue('Directory') : null;

// ---------------------------------------------- documents : items ---
// The idle flag is set here and not in view/documentExplorerList.php, so that the
// two refreshes of view/js/docExplorerScreen.js - which call this script directly,
// bypassing the view - filter documents exactly like the first draw does.
// Explicitly removed when closed items are hidden : tool/jsonQuery.php l. 186 only
// tests whether the key is present.
$explorerShowClosed = documentExplorerShowClosed();
if ($explorerShowClosed) $_REQUEST['idle'] = true;
else                     unset($_REQUEST['idle']);

if (! $currentDirectory) {
  $explorerDocumentsRaw = '{"identifier":"id","items":[]}';
} else {
  $_REQUEST['objectClass'] = 'Document';
  ob_start();
  include '../tool/jsonQuery.php';
  $explorerDocumentsRaw = pq_trim(ob_get_clean());
  if ($explorerDocumentsRaw === '') {
    $explorerDocumentsRaw = '{"identifier":"id","items":[]}';
  }
}

$decoded = json_decode($explorerDocumentsRaw, true);
$rawDocuments = (is_array($decoded) and isset($decoded['items'])) ? $decoded['items'] : array();

$docObjects = array();
$docIds = array();
foreach ($rawDocuments as $doc) {
  if (isset($doc['id']) and intval($doc['id'])) $docIds[] = intval($doc['id']);
}
if (count($docIds)) {
  $docObj = new Document();
  foreach ($docObj->getSqlElementsFromCriteria(null, false, 'id in ('.implode(',', $docIds).')') as $o) {
    $docObjects[$o->id] = $o;
  }
}

$explorerDocumentItems = array();
$docOrder = 0;
foreach ($rawDocuments as $doc) {
  $o = isset($docObjects[intval($doc['id'])]) ? $docObjects[intval($doc['id'])] : null;
  // Safety net : jsonQuery also shows idle documents when session listShowIdleDocument
  // is on (l. 185), whatever this screen asked for. Read on the object and not on
  // $doc : idle is only in there when it is one of the selected columns.
  if (! $explorerShowClosed and $o and $o->idle) continue;
  $docOrder++;
  $item = $doc;

  $plainName = isset($doc['name']) ? $doc['name'] : '';
  if (pq_strpos($plainName, '#!#!#!#!#!#') !== false) {
    $split     = pq_explode('#!#!#!#!#!#', $plainName);
    $plainName = (count($split) > 1) ? $split[1] : $split[0];
  }

  $item['id']          = 'd' . intval($doc['id']);
  $item['refid']       = isset($doc['id']) ? (string) intval($doc['id']) : '';
  $item['reftype']     = 'Document';
  $item['refname']     = $plainName;
  $item['elementary']  = '1';
  $item['wbssortable'] = str_pad($docOrder, 5, '0', STR_PAD_LEFT);
  $item['topid']       = '';
  $item['level']       = 0;
  $item['hidden']      = '0';
  $item['collapsed']   = '0';

  foreach ($explorerColumns as $column) {
    $field = $column['field'];
    if ($field == 'id') continue;
    if (isset($doc[$field])) $item[pq_strtolower($field)] = $doc[$field];
  }
  $item['iddisplay'] = (string) intval($doc['id']);

  $item['idproject']         = ($o) ? $o->idProject         : '';
  $item['project']           = isset($doc['nameProject'])        ? $doc['nameProject']        : '';
  $item['idproduct']         = ($o) ? $o->idProduct         : '';
  $item['product']           = isset($doc['nameProduct'])        ? $doc['nameProduct']        : '';
  $item['iddocumenttype']    = ($o) ? $o->idDocumentType    : '';
  $item['documenttype']      = isset($doc['nameDocumentType'])   ? $doc['nameDocumentType']   : '';
  $item['idstatus']          = ($o) ? $o->idStatus          : '';
  $item['status']            = isset($doc['colorNameStatus'])    ? $doc['colorNameStatus']    : '';
  $item['iddocumentversion'] = ($o) ? $o->idDocumentVersion : '';
  $item['documentversion']   = isset($doc['nameDocumentVersion'])? $doc['nameDocumentVersion']: '';
  $item['documentreference'] = isset($doc['documentReference'])  ? $doc['documentReference']  : '';
  $item['locked']            = isset($doc['locked'])             ? $doc['locked']             : '0';
  $item['idle']              = isset($doc['idle'])               ? $doc['idle']               : '0';

  $explorerDocumentItems[] = $item;
}

$explorerDocumentsJson = json_encode(array(
  'identifier' => 'id',
  'items'      => $explorerDocumentItems,
  'totalRows'  => (string) count($explorerDocumentItems),
));

echo '{"identifier":"id"'
   . ',"items":'            . json_encode($explorerItems)
   . ',"totalRows":"'       . count($explorerItems) . '"'
   . ',"fullLines":"'       . count($explorerItems) . '"'
   . ',"firstFullLine":"1"'
   . ',"lastFullLine":"'    . count($explorerItems) . '"'
   . ',"hiddenLines":"0"'
   . ',"partialLines":"0"'
   . ',"needRefresh":"0"'
   . ',"immediateRefresh":"0"'
   . ',"columns":'          . json_encode($explorerColumns)
   . ',"collapsed":'        . json_encode(array_keys($explorerCollapsed))
   . ',"currentDirectory":' . intval($currentDirectory)
   . ',"documents":'        . $explorerDocumentsJson
   . '}';
?>
