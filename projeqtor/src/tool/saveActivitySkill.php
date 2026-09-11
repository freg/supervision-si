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
 * You can get complete code of ProjeQtOr, other activity, help and information
 * about contributors at http://www.projeqtor.org 
 *     
 *** DO NOT REMOVE THIS NOTICE ************************************************/

/** ===========================================================================
 * Save a note : call coractponding method in SqlElement Class
 * The new values are fetched in $_REQUEST
 */
require_once "../tool/projeqtor.php";
scriptLog('   ->/tool/saveActivitySkill.php');

$idActivity= RequestHandler::getId('idActivity');
$idActivitySkill = RequestHandler::getId('idActivitySkill');
$idSkill = RequestHandler::getId('skillIdAct');
$idSkillLevel = RequestHandler::getId('skillLevelIdAct');

$mode = RequestHandler::getValue('mode');
Sql::beginTransaction();
$result = "";

if($mode == 'edit'){
  $activitySkill = new ActivitySkill($idActivitySkill);
  $activitySkill->idActivity = $idActivity;
  $activitySkill->idSkill = $idSkill;
  $activitySkill->idSkillLevel = $idSkillLevel;
  $res=$activitySkill->save();
}else if($mode == 'delete'){
  $activitySkill = new ActivitySkill($idActivitySkill);
  $res=$activitySkill->delete();
}else{
  $activitySkill = new ActivitySkill();
  $activitySkill->idActivity = $idActivity;
  $activitySkill->idSkill = $idSkill;
  $activitySkill->idSkillLevel = $idSkillLevel;
  $res=$activitySkill->save();
}
if($result == ""){
  $result = getLastOperationStatus($res);
}

// Message of correct saving
displayLastOperationStatus($res);

?>