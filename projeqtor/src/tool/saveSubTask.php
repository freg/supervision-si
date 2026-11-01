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
 * Delete the current object : call corresponding method in SqlElement Class
 */

require_once "../tool/projeqtor.php";

$element= (RequestHandler::isCodeSet('element'))?RequestHandler::getValue('element'):"";
if($element=='')return;
$refType = (RequestHandler::isCodeSet('refType'))?RequestHandler::getValue('refType'):"";
$refId = (RequestHandler::isCodeSet('refId'))?RequestHandler::getValue('refId'):null;
$obj=new $refType ($refId);
if(!securityGetAccessRightYesNo('menu'.$refType,'update',$obj) or securityGetAccessRightYesNo('menu'.$refType,'update',$obj)!='YES') {
  traceHack("saveSubTask.php called for $refType #$refId but user has not write access to this item");
  exit;
}
if($element=='SubTask'){
  $operation = (RequestHandler::isCodeSet('operation'))?RequestHandler::getValue('operation'):"";
  $sortOrder = (RequestHandler::isCodeSet('sortOrder'))?RequestHandler::getValue('sortOrder'):null;
  
  if($operation!='save')$idSubTask = (RequestHandler::isCodeSet('idSubTask'))?RequestHandler::getId('idSubTask'):"";
  if($operation!='delete'){
    //$name=(RequestHandler::isCodeSet('name'))?urldecode(RequestHandler::getValue('name')):null;
    $name=(RequestHandler::isCodeSet('name'))?RequestHandler::getValue('name'):null;
    $priority = (RequestHandler::isCodeSet('priority'))?RequestHandler::getValue('priority'):null;
    $status = (RequestHandler::isCodeSet('status'))?RequestHandler::getValue('status'):"";
    $resource = (RequestHandler::isCodeSet('resource'))?RequestHandler::getValue('resource'):null;
    $dueDate = RequestHandler::getValue('dueDate');
  }
  Sql::beginTransaction();
  if($operation=='save' or $operation=='update'){
    $subTask =($operation=='save')?new SubTask():new SubTask($idSubTask);
    if($operation=='update')$old=$subTask->getOld();
    //if($name!=null)$subTask->name=nl2br($name);
    if($name!=null)$subTask->name=(htmlentities($name));
    if($priority!=null)$subTask->idPriority=(intval($priority)!=0)?intval($priority):null;
    if($resource!=null)$subTask->idResource=(intval($resource)!=0)?intval($resource):null;
    if (RequestHandler::getValue('dueDate')) $subTask->dueDate=($dueDate !='null')?$dueDate:' ';
    if($sortOrder!=null)$subTask->sortOrder=intval($sortOrder);
    if($operation=='update' and $status!=null){
      switch ($status){
       	case '1':
	      $subTask->paused=1;
	      $subTask->handled=0;
	      $subTask->done=0;
	      $subTask->idle=0;
	      break;
	    case '2':
	      $subTask->paused=0;
      	  $subTask->handled=1;
      	  $subTask->done=0;
      	  $subTask->idle=0;
      	  break;
	    case '3':
	      $subTask->paused=0;
      	  $subTask->handled=0;
      	  $subTask->done=1;
      	  $subTask->idle=0;
      	  break;
	    case '4':
	      $subTask->paused=0;
      	  $subTask->handled=0;
      	  $subTask->done=0;
      	  $subTask->idle=1;
      	  break;
      	  default:
	      	if($old->paused!=0 or $old->handled!=0 or $old->done!=0 or $old->idle!=0){
	      	  $subTask->paused=0;
      	      $subTask->handled=0;
      	      $subTask->done=0;
      	      $subTask->idle=0;
      	    }
      }
    }else{
      $subTask->refId=$refId;
      $subTask->refType=$refType;
      $subTask->idProject=$obj->idProject;
      if(property_exists($refType,'idTargetProductVersion'))$subTask->idTargetProductVersion=$obj->idTargetProductVersion;
    }
    $subTask->creationDateTime = date('Y-m-d H:i:s');
    $result=$subTask->save();
  }else{
    $subTask = new SubTask($idSubTask);
    $result=$subTask->delete();
  }
  $creatorName = '';
  $creationDate = '';
  
  if ($subTask->idUser) {
    $creatorName = SqlList::getNameFromId('User', $subTask->idUser);
  }
  if ($subTask->creationDateTime) {
    $creationDate = htmlFormatDateTime($subTask->creationDateTime, false);
  }
  echo '<input type="hidden" id="lastCreateNameUser" value="'.htmlEncode($creatorName).'" />';
  echo '<input type="hidden" id="lastCreateDate" value="'.htmlEncode($creationDate).'" />';
  displayLastOperationStatus ( $result );
}else{
  $field = (RequestHandler::isCodeSet('field'))?RequestHandler::getValue('field'):null;
  $val = (RequestHandler::isCodeSet('value'))?RequestHandler::getValue('value'):null;
  
  Sql::beginTransaction();
  if($field=='Status'){
    $obj->idStatus=$val;
  }else if($field=='Version'){
    $obj->idTargetProductVersion=$val;
  }else {
    $obj->idResource=$val;
  }
  $result=$obj->save();
  displayLastOperationStatus ( $result );
}

?>
