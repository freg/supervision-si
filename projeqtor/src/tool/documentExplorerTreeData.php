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

/* ============================================================================
 * Build the flat, depth-first ordered list of DocumentDirectory visible to the
 * current user, for the document explorer tree.
 */
require_once "../tool/projeqtor.php";
scriptLog('   ->/tool/documentExplorerTreeData.php');

/**
 * Should closed (idle) directories and documents be listed ?
 *
 * Single source of truth for the two consumers of this file : the tree built
 * below, and tool/jsonQuery.php, which asks it whether the selected directory may
 * be seen before listing its documents. Same three forcings as the planning screen - the
 * user parameter, archive mode, an explicit "idle >= 0" filter - but the filter
 * is read on Document, the class the explorer filters on, where planningList.php
 * reads Planning.
 *
 * @return bool
 */
function documentExplorerShowClosed() {
  if (Parameter::getUserParameter('documentExplorerShowClosed') == '1') return true;
  if (sessionValueExists('projectSelectorShowIdle') and getSessionValue('projectSelectorShowIdle') == 1) return true;
  $filters = getSessionUser()->_arrayFilters;
  if (is_array($filters) and pq_array_key_exists('Document', $filters)) {
    foreach ($filters['Document'] as $filter) {
      if (! isset($filter['sql'])) continue;
      if ($filter['sql']['attribute'] == 'idle'
      and $filter['sql']['operator']  == '>='
      and $filter['sql']['value']     == '0') return true;
    }
  }
  return false;
}

/**
 * Flat depth-first list of visible directories.
 * A directory is kept when the user can read it, OR when one of its
 * descendants is readable : otherwise a visible branch would be unreachable.
 *
 * Closed directories are dropped before anything else when documentExplorerShowClosed()
 * says so : their children are then left without a walked parent, hence the whole
 * branch disappears. Dropping them here rather than at walk time also keeps the
 * ancestor promotion below from bringing them back for a readable descendant.
 *
 * @return array of array('id','name','parent','level','hasChild','canUpdate','canDelete')
 */
function getDocumentExplorerTree() {
  $dir = new DocumentDirectory();
  $all = $dir->getSqlElementsFromCriteria(null, false, null, 'name asc');
  $showClosed = documentExplorerShowClosed();

  $byParent = array();
  $rows     = array();
  foreach ($all as $d) {
    if (! $showClosed and $d->idle) continue;
    $parent = ($d->idDocumentDirectory) ? intval($d->idDocumentDirectory) : 0;
    if (! isset($byParent[$parent])) $byParent[$parent] = array();
    $byParent[$parent][] = $d;
    $rows[$d->id] = $d;
  }

  $visible = array();
  foreach ($rows as $id => $d) {
    $visible[$id] = DocumentDirectory::canSeeDirectory($id, $d->idProject, 'read');
  }

  $changed = true;
  $guard   = 0;
  while ($changed and $guard < 100) {
    $changed = false;
    $guard++;
    foreach ($rows as $id => $d) {
      $parent = ($d->idDocumentDirectory) ? intval($d->idDocumentDirectory) : 0;
      if ($visible[$id] and $parent and isset($visible[$parent]) and ! $visible[$parent]) {
        $visible[$parent] = true;
        $changed = true;
      }
    }
  }

  $result = array();
  documentExplorerWalk(0, 0, $byParent, $visible, $result);
  return $result;
}

/**
 * Is this directory one the user may see, in the current "show closed" mode ?
 *
 * The tree is the only place that knows it : per-directory read rights, ancestors
 * kept for a readable descendant, and the closed directories dropped by
 * documentExplorerShowClosed() all apply there.
 *
 * SINGLE CALLER, AND OUTSIDE THIS FOLDER : tool/jsonQuery.php, which uses it to
 * decide whether the document list may show the content of the selected
 * directory. A search limited to the documentExplorer* files makes it look dead.
 *
 * Replaces getDocumentExplorerBranchIds(), dropped on 2026-08-18 with the
 * recursive browsing it served : the document list now shows the documents of the
 * selected directory only, never those of its sub-directories.
 *
 * @return bool
 */
function documentExplorerDirectoryIsVisible($idDirectory) {
  $idDirectory = intval($idDirectory);
  if (! $idDirectory) return false;
  foreach (getDocumentExplorerTree() as $row) {
    if ($row['id'] == $idDirectory) return true;
  }
  return false;
}

/**
 * Depth-first walk. Not using DocumentDirectory::getAllSubdirectories(), which
 * only returns direct children : its recursion is computed then discarded.
 * Do not fix it here, that would change project propagation in save().
 */
function documentExplorerWalk($parent, $level, $byParent, $visible, &$result) {
  if ($level > 50) return; // guard against a cycle already present in database
  if (! isset($byParent[$parent])) return;
  foreach ($byParent[$parent] as $d) {
    if (empty($visible[$d->id])) continue;
    $hasChild = false;
    if (isset($byParent[$d->id])) {
      foreach ($byParent[$d->id] as $child) {
        if (! empty($visible[$child->id])) { $hasChild = true; break; }
      }
    }
    $result[] = array(
      'id'        => intval($d->id),
      'name'      => $d->name,
      'parent'    => intval($parent),
      'level'     => $level,
      'hasChild'  => $hasChild,
      'canUpdate' => DocumentDirectory::canSeeDirectory($d->id, $d->idProject, 'update'),
      'canDelete' => DocumentDirectory::canSeeDirectory($d->id, $d->idProject, 'delete'),
      'location'    => $d->location,
      'idProject'   => $d->idProject,
      'project'     => ($d->idProject) ? SqlList::getNameFromId('Project', $d->idProject) : '',
      'idProduct'   => $d->idProduct,
      'product'     => ($d->idProduct) ? SqlList::getNameFromId('Product', $d->idProduct) : '',
      'idle'        => $d->idle,
    );
    documentExplorerWalk($d->id, $level + 1, $byParent, $visible, $result);
  }
}
?>
