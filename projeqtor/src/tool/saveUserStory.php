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

$objectClass = RequestHandler::getClass('objectClass');
$objectId = RequestHandler::getId('objectId');
$idTypeClass = 'id'.$objectClass;
$idUserStory = RequestHandler::getId('userStoryId');
$mode = RequestHandler::getValue('mode');
Sql::beginTransaction();
$result = "";
$res = "";
if($mode == 'delete'){
  $userStory = new UserStory($idUserStory);
  $userStory->$idTypeClass = '';
  $res=$userStory->save();
  if(getLastOperationStatus($res) != 'OK'){
    $result = $res;
  }
}else{
  if(is_array($idUserStory)){
    foreach ($idUserStory as $userStoryId){
      $userStory = new UserStory($userStoryId);
      $userStory->$idTypeClass = $objectId;
      $res=$userStory->save();
      if(getLastOperationStatus($res) != 'OK'){
        $result = $res;
      }
    }
  }else{
    $userStory = new UserStory($idUserStory);
    $userStory->$idTypeClass = $objectId;
    $res=$userStory->save();
    if(getLastOperationStatus($res) != 'OK'){
      $result = $res;
    }
  }
}

if($result == ""){
  // Message of incorrect saving
  Sql::commitTransaction();
  $status = 'OK';
  echo '<input type="hidden" id="lastSaveId" value="' . htmlEncode ( $objectId ) . '" />';
  echo '<input type="hidden" id="needForceRefreshCreationInfo" value="true" />';
  $msg = i18n ( $objectClass ). ' #' . htmlEncode ( $objectId ) . ' ' . i18n ( 'resultUpdated' );
  displayOKKOStatus($status, $msg);
}else{
  // Message of incorrect saving
  displayLastOperationStatus($result);
}

?>