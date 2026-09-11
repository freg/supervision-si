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
scriptLog('   ->/view/refreshSubTaskAttachmentDiv.php'); 


$idSubTask=(RequestHandler::isCodeSet('idSubTask'))?RequestHandler::getId('idSubTask'):null;

if(!$idSubTask){
    //traceHack("refreshSubTaskAttachmentDiv.php called illegally ");
    exit;
}
$attach= new Attachment();
$subTask= new SubTask($idSubTask);

$allAttach=$attach->getSqlElementsFromCriteria(array("refType"=>get_class($subTask),"refId"=>$subTask->id),null);
if(!empty($allAttach)){
  foreach ($allAttach as $attachment){
    if ($attachment->isThumbable()) {
      echo '<div style="float:left;" oncontextmenu="event.preventDefault();removeAttachment('.$attachment->id.');dojo.byId(\'refreshSTDivValues\').value=\''.$idSubTask.'\';">';
      echo '<img src="'.getImageThumb($attachment->getFullPathFileName(), 32).'" '.' title="'.htmlEncode($attachment->fileName).'" 
          style="min-height:18px;max-width:50px;float:left;cursor:pointer;margin-left: 5px;margin-right: 5px;border:'.((isNewGui())?'1px solid var(--color-button-background-selected)':'1px solid black').'" '
          .' onClick="showImage(\'Attachment\',\''.htmlEncode($attachment->id).'\',\''.htmlEncode($attachment->fileName, 'protectQuotes').'\');" />';
      echo '</div>';
    }else{
      echo '<div style="float:left;" oncontextmenu="event.preventDefault();removeAttachment('.$attachment->id.');dojo.byId(\'refreshSTDivValues\').value=\''.$idSubTask.'\';">';
      echo htmlGetMimeType($attachment->mimeType, $attachment->fileName, $attachment->id,'Attachment',null,28);
      echo '</div>';
    }
  }
}
?>
