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

$lockConfirm = RequestHandler::getBoolean('lockConfirm');
if($lockConfirm)RevisionUpdate::deleteLockFile();
$lockFile = RevisionUpdate::getLockFile();
if(!$lockFile){
  $newRevisionUpdate = array();
  if(isset($user->_arrayRevisionUpdate) and count($user->_arrayRevisionUpdate) > 0){
    $newRevisionUpdate = $user->_arrayRevisionUpdate;
  }else{
    $jsonRevisionUpdate=RevisionUpdate::getRemoteFile("https://subscription.projeqtor.org/getRevisionUpdates.php");
    $newRevisionUpdate=json_decode($jsonRevisionUpdate,true);
    if (! is_array($newRevisionUpdate)) {
      $newRevisionUpdate=array();
    }
    if(count($newRevisionUpdate) > 0){
      ksort($newRevisionUpdate);
      $user->_arrayRevisionUpdate = $newRevisionUpdate;
    }
  }
  $filesRevisionUpdate = array();
  if($newRevisionUpdate){
    foreach ($newRevisionUpdate as $revision=>$update){
      foreach ($update['files'] as $files){
        if(isset($filesRevisionUpdate[$files['path']])){
          $filesInfo = $filesRevisionUpdate[$files['path']];
        }else{
          $filesInfo = array();
        }
        if(!isset($filesInfo['revision'])){
          $filesInfo['revision']=array();
        }
        if(!isset($filesInfo['name'])){
          $filesInfo['name']=$files['name'];
        }
        if(!in_array($revision, $filesInfo['revision'])){
          array_push($filesInfo['revision'], $revision);
        }
        $filesRevisionUpdate[$files['path']] = $filesInfo;
      }
    }
    if($filesRevisionUpdate and count($filesRevisionUpdate) > 0){
      echo RevisionUpdate::downloadRevisionFiles($newRevisionUpdate, $filesRevisionUpdate);
    }
  }
}else{
  $user = ($lockFile['idUser'] != 0)?SqlList::getNameFromId('Affectable', $lockFile['idUser']):'CRON';
  $date = htmlFormatDateTime($lockFile['startDateTime']);
  echo i18n("confirmLockRevisionUpdate", array($user, $date));
}
