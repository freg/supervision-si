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
scriptLog('   ->/view/refreshImputationValidation.php'); 

$idProject=0;
if(sessionValueExists('project') and getSessionValue('project')!="" and  getSessionValue('project')!="*" ){
    $idProject =  getSessionValue('project');
}
$idResource= (RequestHandler::isCodeSet('userNameSubTask'))?pq_trim(RequestHandler::getId('userNameSubTask')):0;
$idVersion = (RequestHandler::isCodeSet('targetProductVersionSubTask'))?pq_trim(RequestHandler::getId('targetProductVersionSubTask')):0;
$idPriority = (RequestHandler::isCodeSet('prioritySubTask'))?pq_trim(RequestHandler::getId('prioritySubTask')):0;
$orderBy = RequestHandler::getValue('toDoListOrderBy');
$element = (RequestHandler::isCodeSet('elementSubTask'))?pq_trim(RequestHandler::getValue('elementSubTask')):'';
$destinationHeight=RequestHandler::getValue('destinationHeight');
$destinationHeight=(isNewGui())?$destinationHeight-75:$destinationHeight-70;
if($idResource=='')$idResource=0;
if($idVersion=='')$idVersion=0;
if($idPriority=='')$idPriority=0;
if($orderBy =='')$orderBy=0;
?>
<form dojoType="dijit.form.Form" name="SubTaskForm" id="SubTaskForm"  method="Post" >
  <div  align="center" style="margin-bottom:5px;<?php if(isNewGui()){?>max-height:<?php echo $destinationHeight;?>px;height:<?php echo $destinationHeight;?>px;overflow-y: auto;<?php }else{?>height:95%;overflow-y:scroll;<?php }?>">
    <?php 
    SubTask::drawAllSubTask($idProject,$idResource,$element,$idVersion,$idPriority,$orderBy);
    ?>
  </div>
</form>
