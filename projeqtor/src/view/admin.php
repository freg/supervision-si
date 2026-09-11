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
 * List of parameter specific to a user.
 * Every user may change these parameters (for his own user only !).
 */
  require_once "../tool/projeqtor.php";
  scriptLog('   ->/view/admin.php');
  
  $user=getSessionUser();
  $collapsedList=Collapsed::getCollaspedList();      
  Security::checkDisplayMenuForUser('Admin');

?>
<input type="hidden" name="objectClassManual" id="objectClassManual" value="Administration" />
<div class="container" dojoType="dijit.layout.BorderContainer">
  <div id="adminButtonDiv" class="listTitle" dojoType="dijit.layout.ContentPane" region="top" style="z-index:3;overflow:visible">
    <script type="dojo/connect" event="onShow" args="evt"><?php Parameter::setDisplaySM();?></script>
    <table width="100%" class="admin projeqtorReference">
      <tr height="32px" style="vertical-align: middle;">
        <td width="50px" align="center">
         <?php echo formatIcon('Admin',32,null,true);?>
        </td>
        <td><span class="title">
          <?php echo i18n("menuAdmin");?>&nbsp;</span>      
        </td>
        <td width="10px" >&nbsp;
        </td>
        <td width="50px"> 
        </td>
        <td>      
        </td>
      </tr>
    </table>
  </div>
  <div id="formAdminDiv" dojoType="dijit.layout.ContentPane" region="center" style="overflow-y:auto;"> 
    <form dojoType="dijit.form.Form" id="adminForm" jsId="adminForm" name="adminForm" encType="multipart/form-data" action="" method="" >
      <table style="width:97%;margin:10px;padding: 10px;vertical-align:top;">
        <tr style="">
          <td style="width:49%;vertical-align:top;">
            <?php $titlePane="Admin_cronTasks"; ?> 
            <div dojoType="dijit.TitlePane" 
             open="<?php echo ( pq_array_key_exists($titlePane, $collapsedList)?'false':'true');?>"
             id="<?php echo $titlePane;?>" 
             onHide="saveCollapsed('<?php echo $titlePane;?>');"
             onShow="saveExpanded('<?php echo $titlePane;?>');"       
             title="<?php echo i18n('cronTasks');?>">
            <table style="width:100%;">            
              <tr>
                <td class="label" style="<?php echo (isNewGui())?'margin-top:-3px;':'';?>"><?php echo i18n("cronStatus").Tool::getDoublePoint();?></td>
                <td class="display">
                  <?php 
                    $cronStatus=Cron::check();
                    echo i18n($cronStatus);
                    if ($cronStatus=='running') {
                    	$arrayTimes=Cron::getActualTimes();
                    	$arrayDisabled=array();
                    	if (isset($arrayTimes['SleepTime']) and $arrayTimes['SleepTime']!=-1 ) {
                    	  echo "<i><br/>&nbsp;&nbsp;&nbsp;" . i18n('adminCronSleepTime', array($arrayTimes['SleepTime'])) . '</i>';
                    	} 
                    	if (isset($arrayTimes['CheckDates']) and $arrayTimes['CheckDates']!=-1) {
                    	  echo "<i><br/>&nbsp;&nbsp;&nbsp;" . i18n('adminCronCheckDates', array($arrayTimes['CheckDates'])) . '</i>';
                    	} else {
                    	  $arrayDisabled[]="CheckDates";
                    	}
                    	if (isset($arrayTimes['CheckImport']) and $arrayTimes['CheckImport']!=-1) {
                    	  echo "<i><br/>&nbsp;&nbsp;&nbsp;" . i18n('adminCronCheckImport', array($arrayTimes['CheckImport'])) . '</i>';
                    	} else {
                    	  $arrayDisabled[]="CheckImport";
                    	}
// BEGIN - ADD BY TABARY - NOTIFICATION SYSTEM
                      if (isset($arrayTimes['CheckNotifications']) and isNotificationSystemActiv() and $arrayTimes['CheckNotifications']!=-1) {
                        echo "<i><br/>&nbsp;&nbsp;&nbsp;" . i18n('adminCronCheckNotifications', array($arrayTimes['CheckNotifications'])) . '</i>';
                      } else {
                    	  $arrayDisabled[]="CheckNotifications";
                    	}
// END - ADD BY TABARY - NOTIFICATION SYSTEM     
// MTY - LEAVE SYSTEM
                      if (isset($arrayTimes['CheckLeavesEarned']) and isLeavesSystemActiv() and $arrayTimes['CheckLeavesEarned']!=-1) {
                        echo "<i><br/>&nbsp;&nbsp;&nbsp;" . i18n('adminCronCheckLeavesEarned', array($arrayTimes['CheckLeavesEarned'])) . '</i>';
                      } else {
                    	  $arrayDisabled[]="CheckLeavesEarned";
                    	}
// MTY - LEAVE SYSTEM                    	
                      if (isset($arrayTimes['CheckMailGroup']) and Mail::isMailGroupingActiv() and $arrayTimes['CheckMailGroup']!=-1) {
                    	  echo "<i><br/>&nbsp;&nbsp;&nbsp;" . i18n('adminCronCheckMailGroup', array($arrayTimes['CheckMailGroup'],Mail::getMailGroupPeriod())) . '</i>';
                    	}else {
                    	  $arrayDisabled[]="CheckMailGroup";
                    	}
                      if (isset($arrayTimes['CheckEmails']) and $arrayTimes['CheckEmails']!=-1) {
                        echo "<i><br/>&nbsp;&nbsp;&nbsp;" . i18n('adminCronCheckEmails', array($arrayTimes['CheckEmails'])) . '</i>';
                      }else {
                    	  $arrayDisabled[]="CheckEmails";
                    	}
                    	if (count($arrayDisabled)>0) {
                    	  echo '<br/>'.i18n("disabled");
                    	  foreach ($arrayDisabled as $disabled) {
                    	    echo "<i><br/>&nbsp;&nbsp;&nbsp;" . i18n($disabled) . '</i>';
                    	  }
                    	}
                    }
                  ?>
                </td>
              </tr>
              <tr>
                <td></td>
                <td>
                  <button id="alertRunStop" dojoType="dijit.form.Button" showlabel="true" class="roundedVisibleButton">
                    <?php echo ($cronStatus=='stopped')?i18n('run'):i18n('stop'); ?>
                   <script type="dojo/connect" event="onClick" args="evt">                 
                  <?php if ($cronStatus=='stopped') {
                  	echo 'showWait();adminLaunchScript("cronRun");';
                  	echo 'disableWidget("alertRunStop");';
                  	echo 'refreshCronIconStatus("running");';
                  } else {
                  	echo 'showWait();adminLaunchScript("cronStop");';
                  	echo 'disableWidget("alertRunStop");';  
                  	echo 'refreshCronIconStatus("stopped");';
                  }
                    echo 'return false;';
                  ?> 
                   </script>
                 </button>
                </td>
              </tr>
            </table>
            </div><br/>
            <?php $titlePane="Admin_sendAlert"; ?> 
            <div dojoType="dijit.TitlePane"
             open="<?php echo ( pq_array_key_exists($titlePane, $collapsedList)?'false':'true');?>"
             id="<?php echo $titlePane;?>" 
             onHide="saveCollapsed('<?php echo $titlePane;?>');"
             onShow="saveExpanded('<?php echo $titlePane;?>');"
             title="<?php echo i18n('sendAlert');?>">
            <table style="width:100%;">
              <tr>
                <td width="200px;" style="<?php echo (isNewGui())?'margin-top:5px;':'';?>" class="label"><?php echo i18n("colMailTo"). Tool::getDoublePoint();?></td>
                <td width="90%">
                  <select dojoType="dijit.form.FilteringSelect" class="input" required="true"
                    <?php echo autoOpenFilteringSelect();?>
                    style="width: 95%;" name="alertSendTo" id="alertSendTo">
                    <option value="*"><?php echo i18n('allUsers')?></option>
                    <option value="connect"><?php echo i18n('allConnectedUsers')?></option>
                    <?php htmlDrawOptionForReference('idUser', null, null, true);?>
                  </select>
                </td>
              </tr>
              <tr>
                <td class="label" style="<?php echo (isNewGui())?'margin-top:5px;':'';?>"><?php echo i18n("colSendDate"). Tool::getDoublePoint();?></td>
                <td>
                  <div dojoType="dijit.form.DateTextBox" name="alertSendDate" id="alertSendDate"
	                  <?php if (sessionValueExists('browserLocaleDateFormatJs')) {
											echo ' constraints="{datePattern:\''.getSessionValue('browserLocaleDateFormatJs').'\'}" ';
										}?>
                    invalidMessage="<?php echo i18n('messageInvalidDate')?>" 
                    type="text" maxlength="10"
                    style="width:75px; text-align: center;" class="input" required="true"
                    value="<?php echo date('Y-m-d');?>"
                    hasDownArrow="false">
                  </div>
                  <div dojoType="dijit.form.TimeTextBox" name="alertSendTime" id="alertSendTime"
                    invalidMessage="<?php echo i18n('messageInvalidTime')?>" 
                    type="text" maxlength="5" required="true"
                    style="width:50px; text-align: center;" class="input"
                    value="T<?php echo date('H:i');?>" 
                    hasDownArrow="false">
                  </div>      
                </td>
              </tr>
              <tr>
                <td class="label" style="<?php echo (isNewGui())?'margin-top:5px;':'';?>"><?php echo i18n("colType"). Tool::getDoublePoint();?></td>
                <td>
                  <select dojoType="dijit.form.FilteringSelect" class="input" 
                    <?php echo autoOpenFilteringSelect();?>
                    style="width: 95%;" name="alertSendType" id="alertSendType" required="true">
                    <option value="INFO"><?php echo i18n('INFO')?></option>
                    <option value="WARNING"><?php echo i18n('WARNING')?></option>
                    <option value="ALERT"><?php echo i18n('ALERT')?></option>
                  </select>
                </td>
              </tr>
              <tr>
                <td class="label" style="<?php echo (isNewGui())?'margin-top:5px;':'';?>"><?php echo i18n("colTitle"). Tool::getDoublePoint();?></td>
                <td>
                  <div dojoType="dijit.form.TextBox"
                    style="width:95%;" required="true"
                    name="alertSendTitle" id="alertSendTitle">
                  </div>
                </td>
              </tr>
              <tr>
                <td class="label" style="<?php echo (isNewGui())?'margin-top:5px;':'';?>"><?php echo i18n("colMessage"). Tool::getDoublePoint();?></td>
                <td>
                  <textarea dojoType="dijit.form.Textarea"
                    name="alertSendMessage" id="alertSendMessage"
                    style="width:97%;"
                    maxlength="4000"
                    class="input"></textarea>
                </td>
              </tr>
              <tr>
                <td class="label"></td>
                <td>
                  <button id="alertSend" dojoType="dijit.form.Button" showlabel="true" class="roundedVisibleButton">
                    <?php echo i18n('send'); ?>
                   <script type="dojo/connect" event="onClick" args="evt">                 
                     adminSendAlert();
                     return false;
                   </script>
                 </button>
                </td>
              </tr>
            </table></div><br/>
            
            <?php $titlePane="Admin_manageConnections"; ?> 
            <div dojoType="dijit.TitlePane"
             open="<?php echo ( pq_array_key_exists($titlePane, $collapsedList)?'false':'true');?>"
             id="<?php echo $titlePane;?>" 
             onHide="saveCollapsed('<?php echo $titlePane;?>');"
             onShow="saveExpanded('<?php echo $titlePane;?>');"
             title="<?php echo i18n('manageConnections');?>">
            <table style="width:100%;">
              <tr>
                <td width="200px;" style="<?php echo (isNewGui())?'margin-top:-3px;':'';?>" class="label"><?php echo i18n("activeConnections"). Tool::getDoublePoint();?></td>
                <td width="90%">
                  <?php $audit=New Audit();
                  $cpt=$audit->countSqlElementsFromCriteria(array('idle'=>'0'));
                  echo $cpt;?>
                </td>
              </tr>
              <tr>
                <td class="label"></td>
                <td>
                  <button id="disconnectAll" dojoType="dijit.form.Button" showlabel="true" class="roundedVisibleButton">
                    <?php echo i18n('disconnectAll'); ?>
                   <script type="dojo/connect" event="onClick" args="evt">                 
                     adminDisconnectAll(true);
                     return false;
                   </script>
                 </button>
                </td>
              </tr>
              <tr><td colspan="2">&nbsp;</td></tr>
              <tr>
                <td width="200px;" style="<?php echo (isNewGui())?'margin-top:-3px;':'';?>" class="label"><?php echo i18n("cronDisconnectAll"). Tool::getDoublePoint();?></td>
                <td>
                 <div>
                  <?php echo CronExecution::drawCronExecutionDefintion('disconnectAll',false);?>
                 </div>
                </td>
              </tr>
              <tr><td colspan="2">&nbsp;</td></tr>
              <tr>
                <td width="200px;" style="<?php echo (isNewGui())?'margin-top:-3px;':'';?>" class="label"><?php echo i18n("applicationStatus"). Tool::getDoublePoint();?></td>
                <td width="90%">
                  <?php $statusApp=Parameter::getGlobalParameter('applicationStatus');
                  if (!pq_trim($statusApp)) {$statusApp='Open';}
                  echo i18n('applicationStatus'.$statusApp);
                  ?>
                </td>
              </tr>
              <tr>
                <td class="label"></td>
                <td>
                  <button id="openCloseApp" dojoType="dijit.form.Button" showlabel="true" class="roundedVisibleButton">
                    <?php $operation="Closed";
                    if ($statusApp!='Open') {$operation='Open';}
                    echo i18n('setApplicationTo'.$operation); ?>
                   <script type="dojo/connect" event="onClick" args="evt">                 
                     adminSetApplicationTo('<?php echo $operation;?>');
                     return false;
                   </script>
                 </button>
                </td>
              </tr>
              <tr>
                <td class="label" style="<?php echo (isNewGui())?'margin-top:5px;':'';?>"><?php echo i18n("closedMessage"). Tool::getDoublePoint();?></td>
                <td>
                  <textarea dojoType="dijit.form.Textarea"
                    name="msgClosedApplication" id="msgClosedApplication"
                    style="width:99%;"
                    maxlength="4000"
                    class="input"><?php echo Parameter::getGlobalParameter('msgClosedApplication');?></textarea>
                </td>
              </tr>  
              
            </table></div><br/>
            
            <?php $titlePane="Admin_manageConsistency"; ?> 
            <div dojoType="dijit.TitlePane"
             open="<?php echo ( pq_array_key_exists($titlePane, $collapsedList)?'false':'true');?>"
             id="<?php echo $titlePane;?>" 
             onHide="saveCollapsed('<?php echo $titlePane;?>');"
             onShow="saveExpanded('<?php echo $titlePane;?>');"
             title="<?php echo i18n('consistencyCheckSection');?>">
            <table style="width:100%;">
              <tr>
                <td width="200px" class="label"><?php echo i18n("runConsistencyCheck"). Tool::getDoublePoint();?></td>
                <td style="width:99%;text-align:left;">
                  <button id="runConsistencyCheck" dojoType="dijit.form.Button" showlabel="true" class="roundedVisibleButton">
                    <?php echo i18n('consistencyCheck'); ?>
                   <script type="dojo/connect" event="onClick" args="evt">   
                     page="../tool/adminFunctionalities.php?adminFunctionality=checkConsistency&correct=0";           
                     showPrint(page, "admin", null, "html", "P");
                   </script>
                 </button><br/>
                 <button id="runConsistencyFix" dojoType="dijit.form.Button" showlabel="true" class="roundedVisibleButton">
                    <?php echo i18n('consistencyFix'); ?>
                   <script type="dojo/connect" event="onClick" args="evt">                 
                     page="../tool/adminFunctionalities.php?adminFunctionality=checkConsistency&correct=1";           
                     showPrint(page, "admin", null, "html", "P");
                   </script>
                 </button>
                </td>
              </tr>
              <tr><td colspan="2">&nbsp;</td></tr>
              <tr>
                <td  width="200px;" style="<?php echo (isNewGui())?'margin-top:-3px;':'';?>" class="label"><?php echo i18n("cronRunConsistencyFix"). Tool::getDoublePoint();?></td>
                <td style="width:99%;text-align:left;">
                 <div>
                  <?php echo CronExecution::drawCronExecutionDefintion('runConsistencyFix');?>
                 </div>
                </td>
              </tr>
              <tr><td colspan="2">&nbsp;</td></tr>
              <tr>
                <td  width="200px;" style="<?php echo (isNewGui())?'margin-top:15px;':'';?>" class="label"><?php echo i18n("cronRunConsistencyCheck"). Tool::getDoublePoint();?></td>
                <td style="width:99%;text-align:left;">
                 <div>
                  <?php echo CronExecution::drawCronExecutionDefintion('runConsistencyCheck');?>
                 </div>
                </td>
              </tr>
            </table></div><br/>    
          </td>
          <td style="width:10px">&nbsp;</td>
          <td style="width:49%;vertical-align:top;">
            <?php $titlePane="Admin_dbMaintenance"; ?> 
            <div dojoType="dijit.TitlePane"
             open="<?php echo ( pq_array_key_exists($titlePane, $collapsedList)?'false':'true');?>"
             id="<?php echo $titlePane;?>" 
             onHide="saveCollapsed('<?php echo $titlePane;?>');"
             onShow="saveExpanded('<?php echo $titlePane;?>');"
             title="<?php echo i18n('dbMaintenance');?>">
            <table style="width:100%;">
              <tr>
                <td class="label" style="width:200px;<?php echo (isNewGui())?'margin-top:5px;':'';?>">
                  <?php echo i18n("closeEmails"). Tool::getDoublePoint();?>
                </td>
                      <?php $maintenanceCloseMail=SqlElement::getSingleSqlElementFromCriteria('Parameter', array('parameterCode'=>'maintenanceCloseMail'));
                      if($maintenanceCloseMail->id=='')$maintenanceCloseMail=7;
                      else $maintenanceCloseMail=$maintenanceCloseMail->parameterValue;
                  ?>
                <td class="display" width="90%">
                  <?php echo i18n('sentSinceMore');?>&nbsp;
                  <div dojoType="dijit.form.NumberTextBox" constraints="{min:0,max:999}" 
                    style="width:30px;"
                    value="<?php echo $maintenanceCloseMail;?>" onchange="saveMaintenanceAdmin('maintenanceCloseMail')" id="maintenanceCloseMail">
                  </div>
                  &nbsp;<?php echo i18n('days');?>
                </td>
              </tr>
              <tr>
                <td></td>
                <td>
                  <button id="closeEmails" dojoType="dijit.form.Button" showlabel="true" class="roundedVisibleButton">
                    <?php echo i18n('close'); ?>
                     <script type="dojo/connect" event="onClick" args="evt">
                       maintenance('close','Mail');
                       return false;
                     </script>
                 </button>
                 <div style="display: inline-block;">
                  <?php echo CronExecution::drawCronExecutionDefintion('closeMails',true);?>
                 </div>
                </td>
              </tr>
              <tr><td colspan="2">&nbsp;</td></tr>
              <tr>
                <td class="label" style="width:200px;<?php echo (isNewGui())?'margin-top:5px;':'';?>">
                  <?php echo i18n("deleteEmails"). Tool::getDoublePoint();?>
                </td>
                <?php 
                      $maintenanceDeleteMail=SqlElement::getSingleSqlElementFromCriteria('Parameter', array('parameterCode'=>'maintenanceDeleteMail'));
                      if($maintenanceDeleteMail->id=='')$maintenanceDeleteMail=30;
                      else $maintenanceDeleteMail=$maintenanceDeleteMail->parameterValue;
                  ?>
                <td class="display">
                  <?php echo i18n('sentSinceMore');?>&nbsp;
                   <div dojoType="dijit.form.NumberTextBox" constraints="{min:0,max:999}"
                    style="width:30px;"
                    value="<?php echo $maintenanceDeleteMail;?>" onchange="saveMaintenanceAdmin('maintenanceDeleteMail')" id="maintenanceDeleteMail">
                  </div>
                  &nbsp;<?php echo i18n('days');?>
                </td>
              </tr>
              <tr>
                <td></td>
                <td>
                  <button id="deleteEmails" dojoType="dijit.form.Button" showlabel="true" class="roundedVisibleButton">
                    <?php echo i18n('deleteButton'); ?>
                     <script type="dojo/connect" event="onClick" args="evt">
                       maintenance('delete','Mail');
                       return false;
                     </script>
                 </button>
                 <div style="display: inline-block;">
                  <?php echo CronExecution::drawCronExecutionDefintion('deleteMails',true);?>
                  </div>
                </td>
              </tr>
                       <tr><td colspan="2">&nbsp;</td></tr>
              <tr>
                <td class="label" style="width:200px;<?php echo (isNewGui())?'margin-top:5px;':'';?>">
                  <?php echo i18n("closeAlerts"). Tool::getDoublePoint();?>
                </td>
                  <?php 
                      $maintenanceCloseAlert=SqlElement::getSingleSqlElementFromCriteria('Parameter', array('parameterCode'=>'maintenanceCloseAlert'));
                      if($maintenanceCloseAlert->id=='')$maintenanceCloseAlert=7;
                      else $maintenanceCloseAlert=$maintenanceCloseAlert->parameterValue;
                  ?>
                <td class="display">
                  <?php echo i18n('sentSinceMore');?>&nbsp;
                   <div dojoType="dijit.form.NumberTextBox" constraints="{min:0,max:999}"
                    style="width:30px;"
                    value="<?php echo $maintenanceCloseAlert;?>" onchange="saveMaintenanceAdmin('maintenanceCloseAlert')" id="maintenanceCloseAlert">
                  </div>
                  &nbsp;<?php echo i18n('days');?>
                </td>
              </tr>
              <tr>
                <td></td>
                <td>
                  <button id="closeAlerts" dojoType="dijit.form.Button" showlabel="true" class="roundedVisibleButton">
                    <?php echo i18n('close'); ?>
                     <script type="dojo/connect" event="onClick" args="evt">
                       maintenance('close','Alert');
                       return false;
                     </script>
                 </button>
                 <div style="display: inline-block;">
                  <?php echo CronExecution::drawCronExecutionDefintion('closeAlerts',true);?>
                 </div>
                </td>
              </tr>
              <tr><td colspan="2">&nbsp;</td></tr>
              <tr>
                <td class="label" style="width:200px;<?php echo (isNewGui())?'margin-top:5px;':'';?>">
                  <?php echo i18n("deleteAlerts"). Tool::getDoublePoint();?>
                </td>
                  <?php 
                      $maintenanceDeleteAlert=SqlElement::getSingleSqlElementFromCriteria('Parameter', array('parameterCode'=>'maintenanceDeleteAlert'));
                      if($maintenanceDeleteAlert->id=='')$maintenanceDeleteAlert=30;
                      else $maintenanceDeleteAlert=$maintenanceDeleteAlert->parameterValue;
                  ?>
                <td class="display">
                  <?php echo i18n('sentSinceMore');?>&nbsp;
                   <div dojoType="dijit.form.NumberTextBox" constraints="{min:0,max:999}"
                    style="width:30px;"
                    value="<?php echo $maintenanceDeleteAlert;?>" onchange="saveMaintenanceAdmin('maintenanceDeleteAlert')" id="maintenanceDeleteAlert">
                  </div>
                  &nbsp;<?php echo i18n('days');?>
                </td>
              </tr>
              <tr>
                <td></td>
                <td>
                  <button id="deleteAlerts" dojoType="dijit.form.Button" showlabel="true" class="roundedVisibleButton">
                    <?php echo i18n('deleteButton'); ?>
                     <script type="dojo/connect" event="onClick" args="evt">
                       maintenance('delete','Alert');
                       return false;
                     </script>
                 </button>
                 <div style="display: inline-block;">
                    <?php echo CronExecution::drawCronExecutionDefintion('deleteAlerts',true);?>
                 </div>
                </td>
              </tr>
              <tr><td colspan="2">&nbsp;</td></tr>
              <tr>
<!-- BEGIN - ADD BY TABARY - NOTIFICATION SYSTEM -->
              <td class="label" style="width:200px;<?php echo (isNewGui())?'margin-top:5px;':'';?>">
                  <?php echo lcfirst(i18n("deleteNotifications")). Tool::getDoublePoint();?>
                </td>
                <?php 
                      $maintenanceDeleteNotification=SqlElement::getSingleSqlElementFromCriteria('Parameter', array('parameterCode'=>'maintenanceDeleteNotification'));
                      if($maintenanceDeleteNotification->id=='')$maintenanceDeleteNotification=30;
                      else $maintenanceDeleteNotification=$maintenanceDeleteNotification->parameterValue;
                ?>
                <td class="display">
                  <?php echo i18n('sentSinceMore');?>&nbsp;
                   <div dojoType="dijit.form.NumberTextBox" constraints="{min:0,max:999}"
                    style="width:30px;"
                    value="<?php echo $maintenanceDeleteNotification;?>" onchange="saveMaintenanceAdmin('maintenanceDeleteNotification')" id="maintenanceDeleteNotification">
                  </div>
                  &nbsp;<?php echo i18n('days');?>
                </td>
              </tr>
              <tr>
                <td></td>
                <td>
                  <button id="deleteNotifications" dojoType="dijit.form.Button" showlabel="true" class="roundedVisibleButton">
                    <?php echo i18n('deleteButton'); ?>
                     <script type="dojo/connect" event="onClick" args="evt">
                       maintenance('delete','Notification');
                       return false;
                     </script>
                 </button>
                 <div style="display: inline-block;">
                    <?php echo CronExecution::drawCronExecutionDefintion('deleteNotifications',true);?>
                 </div>
                </td>
              </tr>
              <tr><td colspan="2">&nbsp;</td></tr>
              <tr>
<!-- END - ADD BY TABARY - NOTIFICATION SYSTEM -->
              <td class="label" style="width:200px;<?php echo (isNewGui())?'margin-top:5px;':'';?>">                <?php echo i18n("deleteAudit"). Tool::getDoublePoint();?>
                </td>
                <?php 
                      $maintenanceDeleteAudit=SqlElement::getSingleSqlElementFromCriteria('Parameter', array('parameterCode'=>'maintenanceDeleteAudit'));
                      if($maintenanceDeleteAudit->id=='')$maintenanceDeleteAudit=30;
                      else $maintenanceDeleteAudit=$maintenanceDeleteAudit->parameterValue;
                ?>
                <td class="display">
                  <?php echo i18n('closedSinceMore');?>&nbsp;
                   <div dojoType="dijit.form.NumberTextBox" constraints="{min:0,max:999}"
                    style="width:30px;"
                    value="<?php echo $maintenanceDeleteAudit;?>" 
                    onchange="saveMaintenanceAdmin('maintenanceDeleteAudit')" id="maintenanceDeleteAudit">
                  </div>
                  &nbsp;<?php echo i18n('days');?>
                </td>
              </tr>
              <tr>
                <td></td>
                <td>
                  <button id="deleteAudit" dojoType="dijit.form.Button" showlabel="true" class="roundedVisibleButton">
                    <?php echo i18n('deleteButton'); ?>
                     <script type="dojo/connect" event="onClick" args="evt">
                       maintenance('delete','Audit');
                       return false;
                     </script>
                 </button>
                 <div style="display: inline-block;">
                  <?php echo CronExecution::drawCronExecutionDefintion('deleteAudit',true);?>
                 </div>
                </td>
              </tr>
              <tr><td colspan="2">&nbsp;</td></tr>
              <tr>
                <td class="label" style="width:200px;<?php echo (isNewGui())?'margin-top:5px;':'';?>">
                  <?php echo i18n("updateReference"). Tool::getDoublePoint();?>
                </td>
                <td class="display">
                  <select dojoType="dijit.form.FilteringSelect" class="input" style="width:200px;"
                    <?php echo autoOpenFilteringSelect();?>
                    name="updateReferenceItem" id="updateReferenceItem" required="true">
                      <option value="*"><?php echo i18n('all')?></option>
                      <?php htmlDrawOptionForReference('idReferencable', null, null, true,null,null,null,null,false);?> 
                  </select>
                </td>
              </tr>
              <tr>
                <td></td>
                <td>
                  <button id="updateReference" dojoType="dijit.form.Button" showlabel="true" class="roundedVisibleButton">
                    <?php echo i18n('operationUpdate'); ?>
                     <script type="dojo/connect" event="onClick" args="evt">
                       item=dijit.byId('updateReferenceItem').get('value');
                       maintenance('updateReference',item);
                       return false;
                     </script>
                 </button>
                </td>
              </tr>
            </table></div>
            <br/>
            <?php $titlePane="Admin_logfileMaintenance"; ?> 
            <div dojoType="dijit.TitlePane"
             open="<?php echo ( pq_array_key_exists($titlePane, $collapsedList)?'false':'true');?>"
             id="<?php echo $titlePane;?>" 
             onHide="saveCollapsed('<?php echo $titlePane;?>');"
             onShow="saveExpanded('<?php echo $titlePane;?>');"
             title="<?php echo i18n('logfileMaintenance');?>">
             <table style="width:100%;">
              <tr>
                <td class="label" style="width:200px;<?php echo (isNewGui())?'margin-top:5px;':'';?>">
                  <?php echo i18n("paramLogLevel"). Tool::getDoublePoint();?>
                </td>
                <td class="display">
                  <select dojoType="dijit.form.FilteringSelect" class="input" style="width:200px;"
                      <?php echo autoOpenFilteringSelect();?>
                            name="logLevelAdm" id="logLevelAdm" required="true">
                            <?php $logLevelAdm = Parameter::getGlobalParameter('logLevel');?>
                      <option value="1" <?php if($logLevelAdm==1){?> selected <?php }?>><?php echo i18n('dialogError')?></option>
                      <option value="2" <?php if($logLevelAdm==2){?> selected <?php }?>><?php echo i18n('trace')?></option>
                      <option value="3" <?php if($logLevelAdm==3){?> selected <?php }?>><?php echo i18n('Debug')?></option>
                      <option value="4" <?php if($logLevelAdm==4){?> selected <?php }?>><?php echo i18n('script')?></option>
                       <script type="dojo/connect" event="onChange" args="evt">
                       logLevel(this.value);
                     </script>
                  </select>
                </td>
              </tr>
              <tr>
                <td class="label" style="width:200px;<?php echo (isNewGui())?'margin-top:5px;':'';?>">
                  <?php echo i18n("deleteLogfile"). Tool::getDoublePoint();?>
                </td>
               <?php 
                      $maintenanceDeletedLogfile=SqlElement::getSingleSqlElementFromCriteria('Parameter', array('parameterCode'=>'deleteLogfileDays'));
                      if($maintenanceDeletedLogfile->id=='')$maintenanceDeletedLogfile=30;
                      else $maintenanceDeletedLogfile=$maintenanceDeletedLogfile->parameterValue;
                ?>
                  
                <td class="display" width="90%">
                  <?php echo i18n('olderThan');?>&nbsp;
                  <div dojoType="dijit.form.NumberTextBox" constraints="{min:0,max:999}"
                    style="width:30px;"
                    value="<?php echo $maintenanceDeletedLogfile;?>" 
                    onchange="saveMaintenanceAdmin('deleteLogfileDays');" name="deleteLogfileDays" id="deleteLogfileDays">
                  </div>
                  &nbsp;<?php echo i18n('days');?>
                </td>
              </tr>
              <tr>
                <td></td>
                <td>
                  <button id="deleteLogfile" dojoType="dijit.form.Button" showlabel="true" class="roundedVisibleButton">
                    <?php echo i18n('deleteButton'); ?>
                     <script type="dojo/connect" event="onClick" args="evt">
                       maintenance('delete','Logfile');
                       return false;
                     </script>
                 </button>
                 <div style="display: inline-block;">
                  <?php echo CronExecution::drawCronExecutionDefintion('deleteLogfile',true);?>
                 </div>
                </td>
              </tr>
              <tr><td colspan="2">&nbsp;</td></tr>
              <tr>
                <td class="label" style="width:200px"><?php echo lcfirst(i18n('dialogLogfiles')). Tool::getDoublePoint();?></td>
                <td>
                 <button id="showLogfile" dojoType="dijit.form.Button" showlabel="true" class="roundedVisibleButton">
                    <?php echo i18n('showLogfiles'); ?>
                     <script type="dojo/connect" event="onClick" args="evt">
                       loadDialog('dialogLogfiles',null,true);
                       //loadContent("../view/logfiles.php","centerDiv");
                     </script>
                 </button>
                 <br/>
                 <button id="showLastLogfile" dojoType="dijit.form.Button" showlabel="true" class="roundedVisibleButton">
                    <?php echo i18n('showLastLogfile'); ?>
                     <script type="dojo/connect" event="onClick" args="evt">
                       showLogfile('last');
                     </script>
                 </button>
                </td>
              </tr>
              <tr><td colspan="2">&nbsp;</td></tr>
            </table>
            </div>
            <?php $titlePane="Admin_reorderWBS"; ?> 
            <div dojoType="dijit.TitlePane"
             open="<?php echo ( pq_array_key_exists($titlePane, $collapsedList)?'false':'true');?>"
             id="<?php echo $titlePane;?>" 
             onHide="saveCollapsed('<?php echo $titlePane;?>');"
             onShow="saveExpanded('<?php echo $titlePane;?>');"
             title="<?php echo i18n('reorderWBS');?>">
            <table style="width:100%;">
              <tr>
                <td width="200px;" style="<?php echo (isNewGui())?'margin-top:-3px;':'';?>" class="label"><?php echo i18n("startReorderingWBS"). Tool::getDoublePoint();?></td>
                <td>
                  <button id="startReorderingWBS" dojoType="dijit.form.Button" showlabel="true" class="roundedVisibleButton">
                    <?php echo i18n('run'); ?>
                   <script type="dojo/connect" event="onClick" args="evt">                 
                     reorderWbs();
                   </script>
                 </button>
                </td>
              </tr>
              <tr><td colspan="2">&nbsp;</td></tr>
              <tr>
                <td width="200px;" style="<?php echo (isNewGui())?'margin-top:-3px;':'';?>" class="label"><?php echo i18n("automaticallyReorderWBS"). Tool::getDoublePoint();?></td>
                <td>
                 <div>
                  <?php echo CronExecution::drawCronExecutionDefintion('reorderWBS');?>
                 </div>
                </td>
              </tr>
            </table></div><br/>
            <?php $titlePane="Admin_executeWaitingUpdates"; ?>
            <div dojoType="dijit.TitlePane"
             open="<?php echo ( pq_array_key_exists($titlePane, $collapsedList)?'false':'true');?>"
             id="<?php echo $titlePane;?>"
             onHide="saveCollapsed('<?php echo $titlePane;?>');"
             onShow="saveExpanded('<?php echo $titlePane;?>');"
             title="<?php echo i18n('sectionWaitingUpdates');?>">
            <table style="width:100%;">
              <tr>
                <td width="200px;" style="<?php echo (isNewGui())?'margin-top:-3px;':'';?>" class="label"><?php echo i18n("startExecuteWaitingUpdates"). Tool::getDoublePoint();?></td>
                <td>
                  <button id="startExecuteWaitingUpdates" dojoType="dijit.form.Button" showlabel="true" class="roundedVisibleButton">
                    <?php echo i18n('run'); ?>
                   <script type="dojo/connect" event="onClick" args="evt">
                     executeWaitingUpdates();
                   </script>
                 </button>
                </td>
              </tr>
              <tr><td colspan="2">&nbsp;</td></tr>
              <tr>
                <td width="200px;" style="<?php echo (isNewGui())?'margin-top:-3px;':'';?>" class="label"><?php echo i18n("automaticallyExecuteWaitingUpdates"). Tool::getDoublePoint();?></td>
                <td>
                 <div>
                  <?php echo CronExecution::drawCronExecutionDefintion('executeWaitingUpdates');?>
                 </div>
                </td>
              </tr>
            </table></div><br/>
          </td>
        </tr>
      </table>
    </form>
  </div>
</div>