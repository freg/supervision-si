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
 * Move task (from before to)
 */
require_once "../tool/projeqtor.php";
scriptLog('   ->/tool/moveSkillFromHierarchicalView.php');
$idFrom = RequestHandler::getValue('idFrom');
$idTo = RequestHandler::getValue('idTo');

$mode=RequestHandler::getValue('mode');
if ($mode!='before' and $mode!='after') {
  $mode='before ?';
}

$idSource = pq_explode('_',$idFrom)[1];
$idTarget = pq_explode('_',$idTo)[1];
$source = new Skill($idSource);
$target = new Skill($idTarget);


// UPDATE PARENTS (recursively)
if ($idTarget) {
  if ($source->idSkill != $target->idSkill) {
    $oldParent=$source->idSkill;
  }
  $source->idSkill = $target->idSkill;
  if ($mode=='after') {
    $source->sbsSortable =  $target->sbsSortable.'.1';
    $source->sbs =  $target->sbs.'.1';
  } else {
    $split=pq_explode('.',$target->sbs);
    $last=$split[count($split)-1];
    $new=intval($last)-1;
    if (count($split)==1) {
      $source->sbs =  $new.'.1';
    } else {
      $newSbsRoot=pq_substr($target->sbs,0,strrpos($target->sbs, '.'));
      $source->sbs =  $newSbsRoot.'.'.$new.'.1';
    }
    $source->sbsSortable =  formatSortableWbs($source->sbs);;
  }
  $source->save();
  $parent=new Skill($target->idSkill);
  $parent->regenerateSbsLevel();
  if (isset($oldParent) and $oldParent) {
    $parent=new Skill($oldParent);
    $parent->regenerateSbsLevel();
  }
}
?>