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

/* ============================================================================
 * Presents the list of objects of a given class.
 *
 */
require_once "../tool/projeqtor.php";
require_once "../tool/formatter.php";
scriptLog('   ->/view/updateRevisionTickets.php'); 

$user=getSessionUser();

$table = RequestHandler::getValue('table');
$revisionId = RequestHandler::getValue('revisionId');
$ticketId = RequestHandler::getValue('ticketId');
$filePath = RequestHandler::getValue('filePath');

$arrayRevision=array();
if($revisionId)$arrayRevision[$revisionId]=$revisionId;

$arrayRevisionUpdate = array();
if($table == 'current'){
$arrayRevisionUpdate=array();
  $revisionUpdate = new RevisionUpdate();
  $arrayRevisionUpdateList = $revisionUpdate->getSqlElementsFromCriteria(array('version'=>Sql::getDbVersion()));
  foreach ($arrayRevisionUpdateList as $revisionUpdate){
    $arrayRevisionUpdate["$revisionUpdate->revisionId"]=array("version"=>"$revisionUpdate->version", "date"=>"$revisionUpdate->date","files"=>array(),"tickets"=>array());
    $jonFiles = json_decode($revisionUpdate->files);
    $files = $jonFiles->files;
    if(is_array($files)){
      foreach ($files as $key=>$file){
        array_push($arrayRevisionUpdate["$revisionUpdate->revisionId"]["files"], array("name"=>$file->name, "path"=>$file->path));
      }
    }else{
      $arrayRevisionUpdate["$revisionUpdate->revisionId"]["files"] = array("name"=>$files->name, "path"=>$files->path);
    }
    $jonTickets = json_decode($revisionUpdate->tickets);
    $tickets = $jonTickets->tickets;
    if(is_array($tickets)){
      foreach ($tickets as $ticket){
        array_push($arrayRevisionUpdate["$revisionUpdate->revisionId"]["tickets"], array("id"=>$ticket->id, "name"=>$ticket->name, "url"=>$ticket->url));
      }
    }else{
      $arrayRevisionUpdate["$revisionUpdate->revisionId"]["tickets"] = array("id"=>$tickets->id, "name"=>$tickets->name, "url"=>$tickets->url);
    }
  }
}else{
  if(isset($user->_arrayRevisionUpdate) and count($user->_arrayRevisionUpdate) > 0){
    $arrayRevisionUpdate = $user->_arrayRevisionUpdate;
  }
}

$langFiles = array();
if($arrayRevisionUpdate and !isset($arrayRevisionUpdate['ERROR'])){
  foreach ($arrayRevisionUpdate as $revision=>$update){
    if ($revisionId and $revision != $revisionId)continue;
    foreach ($update['files'] as $files){
      if($files['name'] == 'lang.js' and $files['path'] != "tool/i18n/nls/lang.js"){
        if(pq_strpos($files['path'], "tool/i18n/nls/el/") !== false and $files['path'] != "tool/i18n/nls/el/lang.js"){
          $cutFilePath = pq_str_replace("tool/i18n/nls/el/", "", $files['path']);
        }else{
          $cutFilePath = pq_str_replace("tool/i18n/nls/", "", $files['path']);
        }
        $cutFilePath = pq_str_replace("/".$files['name'], "", $cutFilePath);
        if(!in_array($cutFilePath, $langFiles)){
          array_push($langFiles, $cutFilePath);
        }
      }
    }
  }
  $langTitle = i18n('revisionLangTitle')."\n";
  foreach ($langFiles as $lang){
    $langTitle .= "$lang\n";
  }
}

if($arrayRevisionUpdate and !isset($arrayRevisionUpdate['ERROR'])){
  foreach ($arrayRevisionUpdate as $revision=>$update){
    if($filePath != ''){
      foreach ($update['files'] as $files){
        $isShortLang = ($files['name'] == "lang.js" and $files['path'] != "tool/i18n/nls/lang.js");
        $filePathName = ($isShortLang)?"tool/i18n/nls/*/lang.js":$files['path'];
        if($filePathName == $filePath){
          $arrayRevision[$revision]=$revision;
        }
      }
    }
    if($ticketId != ''){
      foreach ($update['tickets'] as $tickets){
        $idTicket = (isset($tickets['id']) and $tickets['id'] != '')?$tickets['id']:'0000';
        if($idTicket == $ticketId){
          $arrayRevision[$revision]=$revision;
        }
      }
    }
  }
}

$arrayFiles = array();
if($arrayRevisionUpdate and !isset($arrayRevisionUpdate['ERROR'])){
  $fileDates = RevisionUpdate::buildRevisionDateMaps($arrayRevisionUpdate)['file'];
  echo '      <table style="width:100%">';
  foreach ($arrayRevisionUpdate as $revision=>$update){
    if ($arrayRevision and !isset($arrayRevision[$revision]))continue;
    foreach ($update['files'] as $files){
      $isShortLang = ($files['name'] == "lang.js" and $files['path'] != "tool/i18n/nls/lang.js");
      $filePathName = ($isShortLang)?"tool/i18n/nls/*/lang.js":$files['path'];
      if(!isset($arrayFiles[$filePathName])){
        $arrayFiles[$filePathName]=$files;
        $lineClass = ($filePath and $filePathName == $filePath)?'subsUpdateVersionLineSelected':'subsUpdateVersionLine';
        $title = ($isShortLang)?$langTitle:'';
        $fileRevDates = isset($fileDates[$filePathName]) ? $fileDates[$filePathName] : '';
        echo '     <tr id="'.$table.'FileLine_('.$filePathName.')" data-revdates="'.$fileRevDates.'" class="'.$lineClass.'" onclick="updateRevisionSelectedLine(null, null, \''.$filePathName.'\', \''.$table.'\')">';
        echo '       <td title="'.$title.'" class="updateSubData '.$table.'Files" value="'.$filePathName.'">'.$filePathName.'</td>';
        echo '     </tr>';
      }
    }
  }
  echo '      </table>';
}
?>
