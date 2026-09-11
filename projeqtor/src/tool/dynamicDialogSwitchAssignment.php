<?php 
/*** COPYRIGHT NOTICE *********************************************************
 *
 * Copyright 2009-2015 ProjeQtOr - Pascal BERNARD - support@projeqtor.org
 * Contributors : -
 *
 * This file is part of ProjeQtOr.
 * 
 * ProjeQtOr is free software: you can redistribute it and/or modify it under 
 * the terms of the GNU General Public License as published by the Free 
 * Software Foundation, either version 3 of the License, or (at your option) 
 * any later version.
 * 
 * ProjeQtOr is distributed in the hope that it will be useful, but WITHOUT ANY
 * WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS 
 * FOR A PARTICULAR PURPOSE.  See the GNU General Public License for 
 * more details.
 *
 * You should have received a copy of the GNU General Public License along with
 * ProjeQtOr. If not, see <http://www.gnu.org/licenses/>.
 *
 * You can get complete code of ProjeQtOr, other resource, help and information
 * about contributors at http://www.projeqtor.org 
 *     
 *** DO NOT REMOVE THIS NOTICE ************************************************/

/* ============================================================================
 * Habilitation defines right to the application for a menu and a profile.
 */ 
require_once "../tool/projeqtor.php";
scriptLog('dynamicDialogSwitchAttachment.php');
$idResource=RequestHandler::getId('idResource');
$affectation = new Affectation();
$user=getSessionUser();

$project= new Project();
$query = 'SELECT aff.* FROM '.$affectation->getDatabaseTableName().' as aff JOIN '.$project->getDatabaseTableName().' as proj on aff.idProject=proj.id WHERE aff.idResource = '.$idResource.' and aff.idle = 0 order by proj.sortOrder';
$result = Sql::query($query);
$allAffectations = array();
foreach ($result as $res) {
  $aff = new Affectation($res['id']);
  array_push($allAffectations, $aff);
}
$allProject = array();
?>
<div>
<form dojoType="dijit.form.Form" id='saveSwitchAssignmentForm' name='saveSwitchAssignmentForm'>
  <input id="idResource" name="idResource" value="<?php echo $idResource; ?>" type="hidden"/>
  <input id="idProject" name="idProject" value="" type="hidden"/>
  
  <?php if (empty($allAffectations)) { ?>
  <div style="text-align:center; padding: 20px; font-style: italic;">
    <?php echo i18n('noReplacementNeeded'); ?>
  </div>
<?php } else { ?>
  <table>
      <tr>
      <td class="dialogLabel"><label><?php echo i18n('colStartDate');?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label></td>
      
      <td><div value="" dojoType="dijit.form.DateTextBox" class="input"
                 id="newAffectationStartDate" name="newAffectationStartDate" 
			           constraints="{datePattern:browserLocaleDateFormatJs}" style="width:100px" >
			       <script type="dojo/connect" event="onChange" args="evt">
                var today=new Date();
                if (dijit.byId('endDate') && (! dijit.byId('endDate').get('value') || formatDate(dijit.byId('endDate').get('value'))==formatDate(today) ) ) {
                  dijit.byId('endDate').set('value',dijit.byId('newAffectationStartDate').get('value'));
                }              
            </script>  
			    </div>
			</td>
    </tr>
  </table>
  <div style="xheight:500px;max-height:500px;overflow:auto;border-bottom: 0.5px grey solid;">
  <table style="width:100%;text-align:center">
    <tr>
      <td class="linkHeader" style="width:50%" colspan="2"><?php echo i18n('colIdProject') ?></td>
      <td class="linkHeader" style="width:50%"><?php echo i18n('colReplaceAffectation') ?></td>
    </tr>
 <?php  foreach ($allAffectations as $aff) {
 
   $project = new Project($aff->idProject);
   if (in_array($project, $allProject)) continue;
   array_push($allProject, $project);
   ?>
    <tr>
      <td class="linkData" style="width:5%; vertical-align: middle;"><?php echo ' #'.$project->id; ?></td>
      <td class="linkData" style="width:45%; text-align:left; vertical-align: middle; padding-left:10px"><?php echo $project->name; ?></td>
      <td class="linkData"  style="padding:0 10px; margin:0">
        <div dojoType="dijit.form.FilteringSelect" style="float:left"
               <?php echo autoOpenFilteringSelect();?> 
                id="assignmentProject_<?php echo $aff->idProject; ?>" name="assignmentProject_<?php echo $aff->idProject;?>"
                class="input" 
                missingMessage="<?php echo i18n('messageMandatory',array(i18n('colIdResource')));?>">
               <?php  htmlDrawOptionForReference('idResourceAll', null, null, false, 'idProject', $project->id);?>
        </div>
        <?php $canCreateAffectation=(securityGetAccessRightYesNo('menuAffectation', 'create', $aff, $user)=='YES')?true:false;
        $habil=SqlElement::getSingleSqlElementFromCriteria('HabilitationOther', array('idProfile'=>$user->getProfile($project->id), 'scope'=>'assignmentEdit'));
        if ($canCreateAffectation) {?>
        <button id="showDetailForSwitchAssignment_<?php echo $aff->idProject; ?>" dojoType="dijit.form.Button" showlabel="false"
                title="<?php echo i18n('showDetail')?>" class="notButton notButtonRounded"
                iconClass="iconSearch22 iconSearch iconSize22 imageColorNewGui">
          <script type="dojo/connect" event="onClick" args="evt">
            dojo.byId('idProject').value = <?php echo $aff->idProject;?>;
            showDetail('assignmentProject_<?php echo $aff->idProject; ?>',0,'ResourceAllNoMaterial');
          </script>
        </button>
        <?php }
        $act = new Activity();
        $act->idProject=$aff->idProject;
        $canUpdateActivity=(securityGetAccessRightYesNo('menuActivity', 'update', $act)=='YES')?true:false;
        $canUpdateAssignment=($habil->rightAccess==1)?true:false;
        if ($canUpdateAssignment) {
          $assTmp = new Assignment();
          $assTmp->idProject=$aff->idProject;
          $canUpdateAssignment=(securityGetAccessRightYesNo('menuAssignment', 'create', $assTmp)=='YES' and securityGetAccessRightYesNo('menuAssignment', 'update', $assTmp)=='YES')?true:false;
        }
        if(! $canUpdateActivity or ! $canUpdateAssignment){?>
          <div class="imageColorNewGui" style="float:left;top: 8px;left: 5px;position: relative;" title="<?php echo i18n('errorUpdateRights'); ?> ( <?php if (!$canUpdateActivity) echo i18n('Activity');?> <?php if (!$canUpdateAssignment) echo i18n('Assignment');?> )">
            <?php echo formatMediumButton('Alert', true, false);?>
          </div>
        <?php }?>
      </td>
    </tr>
<?php   }?>
</table>
</div>
  	<div style="text-align:justify;margin:10px;"><?php echo i18n('warningChangeAffectation');?></div>
  	
<?php } ?>
<table style="width: 100%;">
		  <tr>
			  <td align="center"><input type="hidden" id="dialogSwitchAssignmentResultAction">
				  <button class="mediumTextButton" dojoType="dijit.form.Button" type="button"  onclick="dijit.byId('dialogSwitchAssignment').hide();">
                    <?php echo i18n("buttonCancel");?>
                  </button>
				<button class="mediumTextButton" id="dialogSwitchAssignmentSubmit" dojoType="dijit.form.Button" type="submit" onclick="protectDblClick(this);saveSwitchAssignment();">
                  <?php echo i18n("buttonOK");?>
                </button></td>
		  </tr>
	  </table>
</form>
</div>