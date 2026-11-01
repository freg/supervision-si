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

include_once '../tool/formatter.php';

if (! isset ($print)) {
	$print=false;
}
if (! pq_array_key_exists('objectClass',$_REQUEST)) {
	throwError('Parameter objectClass not found in REQUEST');
}
$objectClass=$_REQUEST['objectClass'];

if (! pq_array_key_exists('objectId',$_REQUEST)) {
	throwError('Parameter objectId not found in REQUEST');
}
$objectId=$_REQUEST['objectId'];

$obj = new $objectClass($objectId);
$pe = $objectClass.'PlanningElement';

$dynamicDialogEditAssignment=true;
$_REQUEST['comboDetailAssignment']=true;

$user = getSessionUser();
$assignmentView=SqlElement::getSingleSqlElementFromCriteria('HabilitationOther', array('idProfile'=>$user->getProfile($obj->idProject), 'scope'=>'assignmentView'));
$assignmentEdit=SqlElement::getSingleSqlElementFromCriteria('HabilitationOther', array('idProfile'=>$user->getProfile($obj->idProject), 'scope'=>'assignmentEdit'));
$ass=new Assignment();
$ass->id=1;$ass->idProject=$obj->idProject;
$canUpdate=true;
$showPurgeButton = true;
if (securityGetAccessRightYesNo('menuAssignment', 'update', $ass)!="YES") $canUpdate=false;
if (!$obj->id or ! $canUpdate or ($assignmentView and $assignmentView->rightAccess!=1) or ($assignmentEdit and $assignmentEdit->rightAccess!=1)) {
  $showPurgeButton = false;
}

?>
<div style="position:relative;">
  <div style="">
    <input type="hidden" id="assignmentDialogObjectClass" name="assignmentDialogObjectClass" value="<?php echo $objectClass;?>"/>
    <input type="hidden" id="assignmentDialogObjectId" name="assignmentDialogObjectId" value="<?php echo $objectId;?>"/>
    <input type="hidden" id="assignmentDialogIdProject" name="assignmentDialogIdProject" value="<?php echo $obj->idProject;?>"/>
    <input type="hidden" id="assignmentDialogValidatedWork" name="assignmentDialogValidatedWork" value="<?php echo $obj->$pe->validatedWork;?>"/>
    <input type="hidden" id="assignmentDialogAssignedWork" name="assignmentDialogAssignedWork" value="<?php echo $obj->$pe->assignedWork;?>"/>
    <input type="hidden" id="assignmentDialogWorkOnRealTime" name="assignmentDialogWorkOnRealTime" value="<?php if(property_exists($objectClass, 'workOnRealTime')){echo $obj->workOnRealTime;}?>"/>
    <?php if($objectClass == 'Activity' and $showPurgeButton){?>
      <div style="position:absolute;right:20px;">
        <a id="assignmentDialogPurgeAssignment" onClick="purgeAssignmentTable()" title="<?php echo i18n('helpPurgeAssignment', array(i18n('colActivity'), $objectId));?>" class="imageColorNewGui" ><?php echo formatMediumButton('Purge');?></a>
      </div>
    <?php }?>
    <table>
      <?php include '../view/objectDetail.php';?>
    </table>
  </div>
</div>

<?php // Centralise button, to be displayed on top and bottom 
function showCloseButton() {
  global $objectClass,$objectId,$showWorkHistory,$showArchive;
  ?> 
  <table style="width: 100%;">
   <tr>
     <td style="padding-top:10px;" align="center">
       <button dojoType="dijit.form.Button" type="button" onclick="dijit.byId('dialogEditAssignmentPlanning').hide();">
         <?php echo i18n("close");?>
       </button>
     </td>
   </tr>      
  </table>
<?php 
} 
?>