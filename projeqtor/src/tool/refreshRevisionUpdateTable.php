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

$user=getSessionUser();
$revisionId = RequestHandler::getValue('revisionId');
$table = RequestHandler::getValue('table');
$arrayRevisionUpdate = array();
if($table == 'current'){
  $arrayRevisionUpdate=array();
  $revisionUpdate = new RevisionUpdate();
  $arrayRevisionUpdateList = $revisionUpdate->getSqlElementsFromCriteria(array('version'=>Sql::getDbVersion()));
  foreach ($arrayRevisionUpdateList as $revisionUpdate){
    $arrayRevisionUpdate["$revisionUpdate->revisionId"]=array("version"=>"$revisionUpdate->version", "channel"=>"$revisionUpdate->channel", "date"=>"$revisionUpdate->date","files"=>array(),"tickets"=>array());
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

RevisionUpdate::drawRevisionUpdateTable($arrayRevisionUpdate, $revisionId, $table);