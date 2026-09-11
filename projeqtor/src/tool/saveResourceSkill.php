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
 * Save a note : call corresponding method in SqlElement Class
 * The new values are fetched in $_REQUEST
 */
require_once "../tool/projeqtor.php";
scriptLog('   ->/tool/saveResourceSkill.php');

$idResource= RequestHandler::getId('idResource');
$idResourceSkill = RequestHandler::getId('idResourceSkill');
$idSkill = RequestHandler::getId('skillId');
$idSkillLevel = RequestHandler::getId('skillLevelId');
$useSince = RequestHandler::getValue('skillResourceUseSince');
$useUntil = RequestHandler::getValue('skillResourceUseUntil');
$comment = RequestHandler::getValue('resourceSkillComment');
$idle = RequestHandler::getBoolean('resourceSkillIdle');
if($idle){
  $idle = 1;
}else{
  $idle = 0;
}
$mode = RequestHandler::getValue('mode');
Sql::beginTransaction();
$result = "";

if($mode == 'edit'){
  $resourceSkill = new ResourceSkill($idResourceSkill);
  $resourceSkill->idResource = $idResource;
  $resourceSkill->idSkill = $idSkill;
  $resourceSkill->idSkillLevel = $idSkillLevel;
  $resourceSkill->comment = nl2brForPlainText($comment);
  $resourceSkill->idle = $idle;
  $resourceSkill->useSince = $useSince;
  if ($resourceSkill->useUntil != $useUntil) $resourceSkill->lastAlertDate = null;
  $resourceSkill->useUntil = $useUntil;
  $res=$resourceSkill->save();
}else if($mode == 'delete'){
  $resourceSkill = new ResourceSkill($idResourceSkill);
  $res=$resourceSkill->delete();
}else{
  if(is_array($idSkill)){
    foreach ($idSkill as $skillId){
      $resourceSkill = new ResourceSkill();
      $resourceSkill->idResource = $idResource;
      $resourceSkill->idSkill = $skillId;
      $resourceSkill->idSkillLevel = $idSkillLevel;
      $resourceSkill->comment = nl2brForPlainText($comment);
      $resourceSkill->idle = $idle;
      $resourceSkill->useSince = $useSince;
      $resourceSkill->useUntil = $useUntil;
      $res=$resourceSkill->save();
    }
  }else{
    $resourceSkill = new ResourceSkill();
    $resourceSkill->idResource = $idResource;
    $resourceSkill->idSkill = $idSkill;
    $resourceSkill->idSkillLevel = $idSkillLevel;
    $resourceSkill->comment = nl2brForPlainText($comment);
    $resourceSkill->idle = $idle;
    $resourceSkill->useSince = $useSince;
    $resourceSkill->useUntil = $useUntil;
    $res=$resourceSkill->save();
  }
}
if($result == ""){
  $result = getLastOperationStatus($res);
}

// Message of correct saving
displayLastOperationStatus($res);

?>