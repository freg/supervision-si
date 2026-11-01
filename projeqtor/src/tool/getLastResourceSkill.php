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
scriptLog('   ->/tool/getLastResourceSkill.php');

$idResource= RequestHandler::getId('idResource');
$idSkill = RequestHandler::getId('skillId');
if(is_array($idSkill)){
  echo false;
}else{
  $idSkillLevel = RequestHandler::getId('skillLevelId');
  
  $resourceSkill = new ResourceSkill();
  $lastResourceSkillList = $resourceSkill->getSqlElementsFromCriteria(array('idResource'=>$idResource, 'idSkill'=>$idSkill),false,null,'idSkillLevel DESC, useUntil DESC');
  $lastResourceSkill = (count($lastResourceSkillList)> 0)?$lastResourceSkillList[0]:null;
  if($lastResourceSkill){
    $thisSkillLevelWeight = SqlList::getFieldFromId('SkillLevel', $idSkillLevel, 'weight');
    $lastSkillLevelWeight = SqlList::getFieldFromId('SkillLevel', $lastResourceSkill->idSkillLevel, 'weight');
    if($thisSkillLevelWeight > $lastSkillLevelWeight){
      echo true;
    }
  }
}
?>