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

scriptLog('dynamicDialogMail.php');
$isIE=false;
if (pq_array_key_exists('isIE',$_REQUEST)) {
	$isIE=$_REQUEST['isIE'];
} 
$objectClass=RequestHandler::getClass('objectClass');
if($objectClass == 'TicketSimple'){
    $objectClass = 'Ticket';
}

$objectId = RequestHandler::getId('objectId');

$paramMailerType=pq_strtolower(Parameter::getGlobalParameter('paramMailerType'));
$lstAttach= array();
$lstDoc= array();
$obj=new $objectClass($objectId);
if (method_exists($obj, 'setAttributes')) $obj->setAttributes();
$emTp = new EmailTemplate();
$idObjectType = 'id'.$objectClass.'Type';
$idMailable = SqlList::getIdFromTranslatableName('Mailable', $objectClass);
$where = "(idMailable = ".Sql::fmtId($idMailable)." or idMailable IS NULL) ";
if (property_exists($obj, $idObjectType)) $where.=" and (idType = '".$obj->$idObjectType."' or idType IS NULL)";
$listEmailTemplate = $emTp->getSqlElementsFromCriteria(null,false,$where);
$displayComboButton=false;
$user=getSessionUser();
$profile=$user->getProfile($obj);
$habil=SqlElement::getSingleSqlElementFromCriteria('habilitationOther', array('idProfile'=>$profile, 'scope'=>'combo'));
if ($habil) {
  $list=new ListYesNo($habil->rightAccess);
  if ($list->code=='YES') {
    $displayComboButton=true;
  }
}

//florent #4442
$maxSize=0;
if($paramMailerType=='phpmailer'){
  $lstAllAttach=searchAllAttachmentMailable($objectClass,$obj->id);
  $currentUser=new Resource(getCurrentUserId());
  $lstAttach=$lstAllAttach[0];
  $lstDoc=$lstAllAttach[1];
}
$maxSizeAttachment=Parameter::getGlobalParameter('paramAttachmentMaxSizeMail');
if($maxSizeAttachment==''){
  $maxSizeAttachment=0;
}

$maxSize=$maxSizeAttachment;
$maxSizeAttachment=octectConvertSize($maxSize);
//
$listReceivers = array();
$detailHeight=150;
$detailWidth=510;

?>
<form dojoType="dijit.form.Form" id='mailForm'   style="max-height:800px;overflow-y:auto;overflow-x:hidden;float:none; name='mailForm' onSubmit="return false;">
  <table id="dialogMailGeneralTable">
  	<tr>
  		<td name="dialogMailLeftPartOptionEmailTemplateMessage" style="vertical-align:top; padding-right:20px; max-width:600px;">
  			<input type="hidden" name="dialogMailObjectClass" id="dialogMailObjectClass" value="<?php echo htmlEncode($objectClass);?>" />		
      		<table id="dialogMailGlobalTop">
      			<tr>
      				<td>
          			<div id="mailInfoDiv" class="mailInfoDiv" style="display:none;"><span style="font-weight: bold;"><?php echo i18n('dialogMailIn'); ?></span> <?php echo ' ' . $objectClass . ' #' . ltrim($objectId, '0'); ?></div>
      				</td>
      		  </tr>
        		<tr>
          		<td>
                <input id="mailRefType" name="mailRefType" type="hidden" value="<?php echo $objectClass;?>" />
                <input id="mailRefId" name="mailRefId" type="hidden" value="<?php echo $objectId;?>" />
                <input id="idEmailTemplate" name="idEmailTemplate" type="hidden" value="" />
                <input id="previousEmail" name="previousEmail" type="hidden" value="" />
                <input id="dialogMailSelectedReceivers" name="selectedReceivers" type="hidden" value="" />
                <input id="mailEditorType" name="mailEditorType" type="hidden" value="<?php echo getEditorType();?>" />
                
              	<table id="dialogMailCheckboxOptionAndReceiver" style="white-space:nowrap">
            			<tr>
              			<td>
              				<table id="dialogMailCheckbox"> 
            						<?php if (property_exists($objectClass, 'idContact')) { ?>
                				<tr>
                  				<td class="dialogLabel">
                   				 <label for="dialogMailToContact"><?php echo htmlEncode($obj->getColCaption("idContact"));?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
                  				</td>
                  				<td>
                  				<?php  
                            $checkContact="false";
                            if(sessionValueExists('dialogMailToContact')){ 
                                $dialogMailToContact = getSessionValue('dialogMailToContact');
                                if($dialogMailToContact=="true"){
                                  $checkContact=$dialogMailToContact;
                                }
                             }
                           ?>
                    			<div id="dialogMailToContact" name="dialogMailToContact" dojoType="dijit.form.CheckBox" type="checkbox" onChange="saveDataToSession('dialogMailToContact',this.checked,false);updateReceivers();" <?php echo ($checkContact=="true")?"checked":"";?>></div>
                  			</td>
                			</tr>
          						<?php } ?>
          						<?php if (property_exists($objectClass, 'idUser') and $objectClass!='Project') {?>   
                			<tr>
                  			<td class="dialogLabel">
                    			<label for="dialogMailToUser"><?php echo htmlEncode($obj->getColCaption("idUser")); ?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
                  			</td>
                  			<td>
                          <?php  
                              $checkUser="false";
                              if(sessionValueExists('dialogMailToUser')){ 
                                  $dialogMailToUser = getSessionValue('dialogMailToUser');
                                  if($dialogMailToUser=="true"){
                                    $checkUser=$dialogMailToUser;
                                  }
                                  
                               }
                          ?>
                    			<div id="dialogMailToUser" name="dialogMailToUser" dojoType="dijit.form.CheckBox" type="checkbox" onChange="saveDataToSession('dialogMailToUser',this.checked,false);updateReceivers();"<?php echo ($checkUser=="true")?"checked":"";?>></div>             
                				</td>
                			</tr>
              				<?php } ?>
              				<?php if (property_exists($objectClass, 'idAccountable') and !$obj->isAttributeSetToField('idAccountable','hidden') ) {?>   
                			<tr>
                  			<td class="dialogLabel">
                   			 <label for="dialogMailToAccountable"><?php echo htmlEncode($obj->getColCaption("idAccountable")); ?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
                  			</td>
                    		<td>
                        	<?php  
                            $checkAccount="false";
                            if(sessionValueExists('dialogMailToAccountable')){ 
                                $dialogMailToAccountable = getSessionValue('dialogMailToAccountable');
                                if($dialogMailToAccountable=="true"){
                                  $checkAccount=$dialogMailToAccountable;
                                }
                                
                             }
                          ?>
                        	<div id="dialogMailToAccountable" name="dialogMailToAccountable" dojoType="dijit.form.CheckBox" type="checkbox" onChange="saveDataToSession('dialogMailToAccountable',this.checked,false);updateReceivers();"<?php echo ($checkAccount=="true")?"checked":"";?> ></div>
                    		</td>
                  		</tr>
                      <?php } ?>
                      <?php if (property_exists($objectClass, 'idResource') ) {?>   
                  		<tr>
                    		<td class="dialogLabel">
                      		<label for="dialogMailToResource"><?php echo htmlEncode($obj->getColCaption("idResource")); ?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
                    		</td>
                    		<td>
                        	<?php  
                            $checkRes="false";
                            if(sessionValueExists('dialogMailToResource')){ 
                                $dialogMailToResource = getSessionValue('dialogMailToResource');
                                if($dialogMailToResource=="true"){
                                  $checkRes=$dialogMailToResource;
                                }
                                
                             }
                          ?>
                        	<div id="dialogMailToResource" name="dialogMailToResource" dojoType="dijit.form.CheckBox" type="checkbox" onChange="saveDataToSession('dialogMailToResource',this.checked,false);updateReceivers();"<?php echo ($checkRes=="true")?"checked":"";?>></div>
                    		</td>
                  		</tr>
                      <?php } ?>
                      <?php if (property_exists($objectClass, 'idResponsible') ) {?>   
                      <tr>
                        <td class="dialogLabel">
                          <label for="dialogMailToFinancialResponsible"><?php echo htmlEncode($obj->getColCaption("idResponsible")); ?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
                        </td>
                        <td>
                          <?php  
                              $checkResp="false";
                              if(sessionValueExists('dialogMailToFinancialResponsible')){ 
                                  $dialogMailToFinancialResponsible = getSessionValue('dialogMailToFinancialResponsible');
                                  if($dialogMailToFinancialResponsible=="true"){
                                    $checkResp=$dialogMailToFinancialResponsible;
                                  }
                                  
                               }
                          ?>
                          <div id="dialogMailToFinancialResponsible" name="dialogMailToFinancialResponsible" dojoType="dijit.form.CheckBox" type="checkbox" onChange="saveDataToSession('dialogMailToFinancialResponsible',this.checked,false);updateReceivers();"<?php echo ($checkResp=="true")?"checked":"";?>></div>
                        </td>
                      </tr>
                      <?php } ?>
                      <?php if (property_exists($objectClass, 'idSponsor')) { ?>
                      <tr>
                        <td class="dialogLabel">
                          <label for="dialogMailToSponsor"><?php echo htmlEncode($obj->getColCaption("idSponsor"));?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
                        </td>
                        <td>
                          <?php  
                              $checkSponsor="false";
                              if(sessionValueExists('dialogMailToSponsor')){ 
                                  $dialogMailToSponsor = getSessionValue('dialogMailToSponsor');
                                  if($dialogMailToSponsor=="true"){
                                    $checkSponsor=$dialogMailToSponsor;
                                  }
                                  
                               }
                           ?>
                          <div id="dialogMailToSponsor" name="dialogMailToSponsor" dojoType="dijit.form.CheckBox" type="checkbox" onChange="saveDataToSession('dialogMailToSponsor',this.checked,false);updateReceivers();"<?php echo ($checkSponsor=="true")?"checked":"";?> ></div>
                        </td>
                      </tr>
                      <?php } ?>
                      <?php if (property_exists($objectClass, 'idProject')) { ?>
                      <tr>
                        <td class="dialogLabel">
                          <label for="dialogMailToProject"><?php echo i18n("colMailToProject") ?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
                        </td>
                        <td>
                          <?php  
                              $checkProjr="false";
                              if(sessionValueExists('dialogMailToProject')){ 
                                  $dialogMailToProject = getSessionValue('dialogMailToProject');
                                  if($dialogMailToProject=="true"){
                                    $checkProjr=$dialogMailToProject;
                                  }
                                  
                               }
                          ?>
                          <div id="dialogMailToProject" name="dialogMailToProject" dojoType="dijit.form.CheckBox" type="checkbox" onChange="saveDataToSession('dialogMailToProject',this.checked,false);updateReceivers();"<?php echo ($checkProjr=="true")?"checked":"";?> ></div>
                        </td>
                      </tr>
                      <tr>
                        <td class="dialogLabel">
                          <label for="dialogMailToProjectIncludingParentProject"><?php echo i18n("colMailToProjectIncludingParentProject") ?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
                        </td>
                        <td>
                          <?php  
                              $checkParentProjr="false";
                              if(sessionValueExists('dialogMailToProjectIncludingParentProject')){ 
                                  $dialogMailToParentProject = getSessionValue('dialogMailToProjectIncludingParentProject');
                                  if($dialogMailToParentProject=="true"){
                                    $checkParentProjr=$dialogMailToParentProject;
                                  }
                                  
                               }
                          ?>
                          <div id="dialogMailToProjectIncludingParentProject" name="dialogMailToProjectIncludingParentProject" title="<?php echo i18n('globalProjectTeam');?>"  dojoType="dijit.form.CheckBox" type="checkbox" onChange="saveDataToSession('dialogMailToProjectIncludingParentProject',this.checked,false);updateReceivers();"<?php echo ($checkParentProjr=="true")?"checked":"";?> ></div>
                        </td>
                      </tr>
                      <tr>
                        <td class="dialogLabel">
                          <label for="dialogMailToLeader"><?php echo i18n("colMailToLeader") ?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
                        </td>
                        <td>
                          <?php  
                              $checkLeader="false";
                              if(sessionValueExists('dialogMailToLeader')){ 
                                  $dialogMailToLeader = getSessionValue('dialogMailToLeader');
                                  if($dialogMailToLeader=="true"){
                                    $checkLeader=$dialogMailToLeader;
                                  }
                                  
                               }
                          ?>
                          <div id="dialogMailToLeader" name="dialogMailToLeader" dojoType="dijit.form.CheckBox" type="checkbox" onChange="saveDataToSession('dialogMailToLeader',this.checked,false);updateReceivers();"<?php echo ($checkLeader=="true")?"checked":"";?> ></div>              
                        </td>
                      </tr>
                      <?php if ($objectClass!='Project' and property_exists($objectClass, 'idProject') ) {?>
                      <tr>
                        <td class="dialogLabel">
                          <label for="dialogMailToManager"><?php echo i18n("colMailToManager") ?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
                        </td>
                        <td>
                          <?php  
                              $checkManager="false";
                              if(sessionValueExists('dialogMailToManager')){ 
                                  $dialogMailToManager = getSessionValue('dialogMailToManager');
                                  if($dialogMailToManager=="true"){
                                    $checkManager=$dialogMailToManager;
                                  }
                                  
                               }
                          ?>
                          <div id="dialogMailToManager" name="dialogMailToManager" dojoType="dijit.form.CheckBox" type="checkbox" onChange="saveDataToSession('dialogMailToManager',this.checked,false);updateReceivers();"<?php echo ($checkManager=="true")?"checked":"";?> ></div>
                        </td>
                      </tr>
                      <?php }?>
                  		<?php } ?>
                      <?php if (property_exists($objectClass, '_Assignment') ) {
                        $assigedLabel = i18n("colMailToAssigned");
                        if($objectClass == 'Meeting'){
                          $assigedLabel = i18n("colAttendees");
                        }?>  
                      <tr>
                        <td class="dialogLabel">
                          <label for="dialogMailToAssigned"><?php echo $assigedLabel; ?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
                        </td>
                        <td>
                          <?php  
                              $checkAssigned="false";
                              if(sessionValueExists('dialogMailToAssigned')){ 
                                  $dialogMailToAssigned = getSessionValue('dialogMailToAssigned');
                                  if($dialogMailToAssigned=="true"){
                                    $checkAssigned=$dialogMailToAssigned;
                                  }
                                  
                               }
                          ?>
                          <div id="dialogMailToAssigned" name="dialogMailToAssigned" dojoType="dijit.form.CheckBox" type="checkbox" onChange="saveDataToSession('dialogMailToAssigned',this.checked,false);updateReceivers();"<?php echo ($checkAssigned=="true")?"checked":"";?> ></div>
                        </td>
                      </tr>
                      <?php }?>
                      <tr>
                        <td class="dialogLabel">
                          <label for="dialogMailToSubscribers"><?php echo i18n("colMailToSubscribers") ?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
                        </td>
                        <td>
                          <?php  
                              $checkSubscribers="false";
                              if(sessionValueExists('dialogMailToSubscribers')){ 
                                  $dialogMailToSubscribers = getSessionValue('dialogMailToSubscribers');
                                  if($dialogMailToSubscribers=="true"){
                                    $checkSubscribers=$dialogMailToSubscribers;
                                  }
                                  
                               }
                          ?>
                          <div id="dialogMailToSubscribers" name="dialogMailToSubscribers" title="<?php echo i18n('colMailToSubscribersDetail');?>" dojoType="dijit.form.CheckBox" type="checkbox" onChange="saveDataToSession('dialogMailToSubscribers',this.checked,false);updateReceivers();"<?php echo ($checkSubscribers=="true")?"checked":"";?> ></div>
                        </td>
                      </tr>    
              			</table>
              			</td>
                    <!-- Receiver -->
                    <td style="vertical-align: top; padding:5px 0px 0px 50px;">
                    <div id="receiverTableContainer" >
                      <div style="width: 350px; overflow-y: auto; overflow-x: hidden; height: 235px; border: 1px solid var(--color-medium);">
                        <table id="dialogMailReceiver" style="width: 100%; table-layout: fixed; border-collapse: collapse;">
                          <thead>
                            <tr style="background-color: var(--color-medium); height: 20px;">
                              <th style="width: 30px;"></th>
                              <th style="width: 200px; font-size: 12px; color: white;"><?php echo ucfirst(i18n("colReceiver")); ?></th>
                              <th style="width: 100px; font-size: 12px; color: white;"><?php echo ucfirst(i18n("colType")); ?></th>
                            </tr>
                          </thead>
                          <tbody id="receiversTableBody">
                            <tr><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td></tr>
                            <tr><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td></tr>
                            <tr><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td></tr>
                          </tbody>
                        </table>
                			</div>
                		</div>
              			</td>
            			</tr>
            		</table>
          	    <!-- Other receivers -->
              	<table id="dialogMailOtherOption">
                  <td class="dialogLabel">
                    <label for="dialogMailToOther"><?php echo i18n("colMailToOther") ?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
                  </td>
                  <td>
                    <?php $checOther="false";
                      if(sessionValueExists('dialogMailToOther')){ 
                        $dialogMailToOther = getSessionValue('dialogMailToOther');
                        if($dialogMailToOther=="true"){
                           $checOther=$dialogMailToOther;
                        }
                      }
                    ?>
                    <div id="dialogMailToOther" name="dialogMailToOther" title="" dojoType="dijit.form.CheckBox" type="checkbox" onChange="dialogMailToOtherChange();saveDataToSession('dialogMailToOther',this.checked,false);"<?php echo ($checOther=="true")?"checked":"";?> ></div>
                    <?php echo i18n('helpOtherEmail');?>
                  </td>
                </table>
                <!-- other option text -->
                <table id ="dialogMailOtherText">
                  <td class="dialogLabel">
                  	<label>&nbsp;&nbsp;</label>
                  </td>
                  <?php if(sessionValueExists('dialogMailToOther')){ 
                    $dialogOtherMail = getSessionValue('dialogOtherMail');
                  }?>
                  <td style="width: 390px;">
                 		<textarea dojoType="dijit.form.Textarea" 
        				      id="dialogOtherMail" name="dialogOtherMail"
        				      style="width: 390px; min-height:30px;display:<?php echo ($checOther=='true')?'block':'none';?>"
        				      maxlength="4000"
        				      class="input" onblur="findAutoEmail();hideEmailHistorical();" oninput="compareEmailCurrent();" onclick="compareEmailCurrent();" onchange="saveDataToSession('dialogOtherMail',this.value,false);"><?php echo ($checOther=='true')?$dialogOtherMail:'';?></textarea>
        				    <textarea dojoType="dijit.form.Textarea" 
            					id="dialogMailObjectIdEmail" name="dialogMailObjectIdEmail"
            					style="width: 200px;display:none"
            					class="input" onchange="dialogMailIdEmailChange();">
            				</textarea>
            			</td>
        					<td style="position: relative; top:-1px;">
        					<?php if ($displayComboButton and Security::checkValidAccessForUser(null, 'read', 'Affectable',null,false)) {?>
                  	<button id="otherMailDetailButton" dojoType="dijit.form.Button" showlabel="false"style="display:<?php echo ($checOther=='true')?'block':'none';?>" title="<?php echo i18n('showDetail')?>" iconClass="iconSearch22 iconSearch iconSize22 imageColorNewGui" class="notButton notButtonRounded">
                    		<script type="dojo/connect" event="onClick" args="evt">
                      		dijit.byId('dialogMailObjectIdEmail').set('value',null);
                      		showDetail('dialogMailObjectIdEmail', 0, 'Affectable', true);
                    	</script>
                  	</button>
                  <?php }?>
                  </td>
                </table>
                <table>
                 <tr name="dialogOtherMailHistoricalTR">
                    <td class="dialogLabel">
                      <label for="dialogOtherMailHistorical"></label>
                    </td>
                    <td>
                      <?php  
                          $checkHist="false";
                          if(sessionValueExists('dialogOtherMailHistorical')){ 
                              $dialogOtherMailHistorical = getSessionValue('dialogOtherMailHistorical');
                              if($dialogOtherMailHistorical=="true"){
                                $checkHist=$dialogOtherMailHistorical;
                              }
                              
                           }
                      ?>
                      <div id="dialogOtherMailHistorical" name="dialogOtherMailHistorical" style="height:auto; margin-top:-1.9px; margin-left:0.5px; overflow-y:auto; position:relative; z-index: 999999999; display:none; width: 498px;  background-color:white; border:1px solid grey;" onChange="saveDataToSession('dialogOtherMailHistorical',this.checked,false);"<?php echo ($checkHist=="true")?"checked":"";?> ></div>
                    </td>
                  </tr>
                </table>
                <table id="dialogMailEmailTemplate">
                  <?php if (property_exists($objectClass, '_Note') ) {?>    
                  <tr name="dialogMailOptionSaveAsNote">
                    <td class="dialogLabel">
                      <label for="dialogMailSaveAsNote"><?php echo i18n("colSaveAsNote") ?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
                    </td>
                  	<td>
                    <?php 
                      $checkNote = "false";
                      $dialogMailSaveAsNote = Parameter::getUserParameter('dialogMailSaveAsNote');
                      
                      if ($dialogMailSaveAsNote == "true") {
                        $checkNote = "true";
                      }
                    ?>
                      <div id="dialogMailSaveAsNote" name="dialogMailSaveAsNote" dojoType="dijit.form.CheckBox" type="checkbox" onChange="saveUserParameter('dialogMailSaveAsNote', this.checked ? 'true' : 'false');"
                        <?php echo ($checkNote=="true")?"checked":"";?> >
                      </div>
                  	</td>
                	</tr>
                	<?php }?>
                	<tr name="dialogMailOptionEmailTemplate">
                    <td class="dialogLabel">
                      <label for="dialogMailEmailTemplate" class="generalColClass idEmailTemplateClass"><?php echo htmlEncode($obj->getColCaption("idEmailTemplate")); ?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
                    </td>
                    <td>
                      <?php 
                      $showVal=false;
                          if(sessionValueExists('dialogMailEmailTemplate')){ 
                              $dialogMailEmailTemplate = getSessionValue('dialogMailEmailTemplate');
                              foreach ($listEmailTemplate as $key => $value){
                                  if($value->id ==$dialogMailEmailTemplate ){
                                    $showVal=true;
                                    $dialogName=$value->name;
                                  }
                              }
                          }
                          
    
                      ?>
                      <select dojoType="dijit.form.FilteringSelect" 
                        id="selectEmailTemplate" name="selectEmailTemplate" class="input" onChange="saveDataToSession('dialogMailEmailTemplate',this.value,false);"
                        <?php echo autoOpenFilteringSelect();?>>
                        <option value="<?php echo ($showVal==true)?$dialogMailEmailTemplate:''; ?>"><?php  echo ($showVal==true)?$dialogName:''; ?></option>
                        <?php 
                          foreach ($listEmailTemplate as $key => $value){
                            if ($value->idle) continue;
                            if(sessionValueExists('dialogMailEmailTemplate')){
                              if($value->id==$dialogMailEmailTemplate){
                                continue;
                              }
                            }
                            ?>
                            <option value="<?php echo $value->id;?>"><?php echo htmlEncode($value->name);?></option>
                        <?php 
                          }?>
                          <script type="dojo/connect" event="onChange" args="evt">
                          dojo.byId('idEmailTemplate').value = this.value;
                        </script>
                          <script type="dojo/connect" event="" args="evt">
                         dojo.byId('idEmailTemplate').value = this.value;
                        </script>
                       </select>
                        <!-- message -->
                  	</td>
                  </tr>

                	<tr>
                    <td class="dialogLabel" colspan="2">
                      <label for="dialogMailMessage" style="text-align: left;padding-bottom: 10px;"><?php echo i18n("colMailMessage") .' :'; ?></label>
                    </td>
                	</tr>
                  <tr>
                    <td colspan="2">
                      <?php if (getEditorType() == "CK" or getEditorType() == "CKInline") { ?> 
                        <textarea style="width:<?php echo $detailWidth; ?>px; height:<?php echo $detailHeight; ?>px" tabindex="1"
                          name="dialogMailMessage" id="dialogMailMessage" onChange="saveDataToSession('dialogMailMessage',this.value,false);"></textarea>
                      <?php } else if (getEditorType() == "text") {?>
                          <textarea dojoType="dijit.form.Textarea"
                            id="dialogMailMessage" name="dialogMailMessage"
                            style="max-width:<?php echo $detailWidth;?>px;height:<?php echo $detailHeight;?>px;max-height:<?php echo $detailHeight;?>px"
                            maxlength="4000"
                            class="input" onChange="saveDataToSession('dialogMailMessage',this.value,false);">
                          </textarea>
                      <?php } else { ?>
                          <textarea dojoType="dijit.form.Textarea" type="hidden"
                            id="dialogMailMessage" name="dialogMailMessage"
                            style="display:none;" onChange="saveDataToSession('dialogMailMessage',this.value,false);"></textarea>    
                          <div data-dojo-type="dijit.Editor" id="mailMailEditor"
                            data-dojo-props="onChange:function(){window.top.dojo.byId('dialogMailMessage').value=arguments[0];}
                              ,plugins:['removeFormat','bold','italic','underline','|', 'indent', 'outdent', 'justifyLeft', 'justifyCenter', 
                                        'justifyRight', 'justifyFull','|','insertOrderedList','insertUnorderedList','|']
                              ,onKeyDown:function(event){window.top.onKeyDownFunction(event,'mailMailEditor',this);}
                              ,onBlur:function(event){window.top.editorBlur('mailMailEditor',this);}
                              ,extraPlugins:['dijit._editor.plugins.AlwaysShowToolbar','foreColor','hiliteColor']"
                            style="color:#606060 !important; background:none;padding:3px 0px 3px 3px;margin-right:2px;width:<?php echo $detailWidth;?>px;overflow:auto;"
                            class="input" >
                          </div>
                      <?php } ?>
                    </td>
                  </tr>
               	</table>
               </td>
              </tr>
             </table>
            </td>
            <td name="dialogMailRightPartAttachment" style="vertical-align:top; width:720px;">
              	<!-- Table for label Files to attach to email -->
                <table id="dialogMailLabelBeforeTable" style="width:90%;margin-bottom:5px;width:700px;" align="center">
                  <tr>
                    <td class="dialogLabel" style="float:left; margin-left:5px;margin-top:3px;width:310px" >
                        <div id='titleAttachmentTab' style="font-size:14px;font-weight:bold;float:left;"><?php echo i18n('titleAttachmentTabMail');?></div>
                    </td style="width:30%">
                    <td class="dialogLabel" width:80% style="width:210px;position:relative;top:5px;">
                        <label for="totalSize" style="font-size:12px;float:right;"><?php echo  i18n("totalSize")." :";?></label>
                    </td>
                    <td class="dialogLabel" style="width:150px;position:relative;top:5px;">
                        <input  name="attachments" id="attachments"  class="input"  type="hidden" value="<?php echo getSessionValue("dialogMailAttachments");?>"/>
                        <input  name="totalSizeNoConvert" id="totalSizeNoConvert"  class="input"  type="hidden" value="" />
                        <input  name="maxSizeNoconvert" id="maxSizeNoconvert" class="input"  type="hidden" value="<?php echo $maxSize;?>" />
                        <div id="infoSize"  style="position:relative;font-size:12px;border:none;right:0px;text-align:right;padding-right:20px;white-space:nowrap"><input  name="totalSize" id="totalSize"  class="input "  style="border:none;width:70px;text-align:right;" value="" readonly /><?php echo "&nbsp;/&nbsp;".$maxSizeAttachment;?></div>
                    </td>
                  </tr>
              	</table>
             		<!-- table for button Add attached file -->
           	    <table id="dialogMailAddAttachmentButton" style="margin: 10px auto;">
              		<tr height="30px ">
              			<td style="padding-right: 10px"><?php echo i18n("addAttachment")?></td>
              			<td style="position:relative">
                    	<div>
                      	<input type="hidden" name="MAX_FILE_SIZE" value="<?php echo Parameter::getGlobalParameter('paramAttachmentMaxSize');?>" />
                       	<span id="attachmentFileDropAreaEmail" >  
                          <div MAX_FILE_SIZE="<?php echo Parameter::getGlobalParameter('paramAttachmentMaxSize');?>"
                          dojoType="dojox.form.Uploader" type="file" 
                          name="attachmentFile" id="attachmentFileEmail" 
                          url="../tool/saveAttachment.php?attachmentRefType=<?php echo get_class($obj);?>&SendMail=true&attachmentRefId=<?php echo $obj->id;?><?php echo Security::addTokenIndexToUrl(); ?>"
                          multiple="true" 
                          uploadOnSelect="true"
                          cancelText="<?php echo i18n("buttonReset");?>"
                          onComplete="refreshAttachmentSendMail('<?php echo $isIE?>','<?php echo $objectClass?>','<?php echo $objectId?>');"
                          onBegin="hideResultDivs();saveAttachment(true,'attachmentFileDirect');"
                          onError="dojo.style(dojo.byId('downloadProgress'), {display:'none'});"
                          <?php if (! $isIE) {?>
                          style="text-align:left;padding:0px;margin:0px;<?php echo (isNewGui())?'width:350px':'z-index: 50;width:340px; border: 3px dotted #EEEEEE;';?>"
                          <?php } else {?>
                          style="overflow: hidden; border: 0px"
                          <?php }?>
                          label="<?php echo i18n("buttonBrowse");?>"
                          title="<?php echo i18n("helpSelectFile");?>"  />
                    			<script type="dojo/connect" event="onComplete" args="dataArray">
                            saveAttachmentAck(dataArray);
	                        </script>
                    		  <script type="dojo/connect" event="onProgress" args="data">
                            saveAttachmentProgress(data);
	                        </script>
                    	    <script type="dojo/connect" event="onError" args="data">
                            hideWait();
                            showError(i18n("uploadUncomplete"));
	                        </script>
                     		</span>
                      </div> 
                      <span id="dialogMailSpanForButtonAddAttachment" style="font-style:italic;position: absolute; z-index: 49; top: 8px; left: 120px; color: #AAAAAA; width:230px;pointer-events: none;"><?php echo i18n("dragAndDrop");?></span>
                 		</td>
                 	</tr>
                </table>
             		 <?php 
             		   //old condition if no part right
             		   //$styleTableOkCancelButton ="margin-top:10px; margin-left:300px; transform: translateX(-50%); background-color: #fff; padding: 5px;";
             		   $styleTableOkCancelButton ="margin-top:10px;position: absolute;bottom: 20px; left:1000px; transform: translateX(-50%); background-color: #fff; padding: 5px;";
                  //florent #4442
                  if((!empty($lstAttach) or !empty($lstDoc)) and  $maxSize!=0  ){
  
                 ?>
                <table id="dialogMailTableAttachment" style="width:100%;bottom:5px;width:700px;" align="center">
                  <td>
                    <table id ="dialogMailTableHeader" style='width:100%;font-size:12px;width:700px;'>
                  		<tr>
                      	<td class='assignHeader' >
                      		<div style="width:280px">
                        		<div style="float:left;margin-left:5px;" id='dialogMailAll' name='dialogMailAll'  dojoType='dijit.form.CheckBox' type='checkbox' onclick='selectAllCheckBox(".checkBoxAttachmentMail");'></div>
                            <?php if (isNewGui()) {?><div style="padding-top:7px"><?php }?>
                            <?php echo i18n('sectionAttachment')."&nbsp;";?>
                            <?php if (isNewGui()) {?></div><?php }?>
                      		</div>
                    		</td>
                      	<td class='assignHeader' >
                      		<div style="width:120px"><?php echo i18n('dashboardTicketMainTitleType');?></div>
                      	</td>
                      	<td class='assignHeader' >
                      		<div style="width:110px"><?php echo i18n('FileSize');?></div>
                    		</td>
                        <?php 
                        if(1 or !empty($lstDoc)){
                          echo " <td class='assignHeader'><div style='width:175px'></div></td>";
                        }
                        ?>
                        <td class=''>
                          <div style="width:15px"></div>
                        </td>
                    </tr>
                  </table>
                  <div id='showAttachment' style="max-height:386px;overflow-y:auto;overflow-x:hidden;float:none;width:700px;">
                  <div id='showattachmentPJ' style="max-height:154px;overflow: hidden auto; float: none; width: 700px; display: block; opacity: 1;">
                    <table id="scrollTableMail" name="dialogMailTableAttachmentContent" style='font-size:12px; width:685px; max-width:685px;'>
                      <?php 
                        foreach($lstAttach as $attached){
                          if(($attached->idPrivacy==3 and $attached->idUser!=$currentUser->id) or ($attached->idPrivacy==2 and $attached->idTeam!=$currentUser->idTeam)){
                             continue;
                          }
                          $attachName=pq_str_replace("'","",$attached->fileName).''.$attached->id;
                          $checkAttachementCurrent="false";
                          if(sessionValueExists('dialogMail'.$attachName.'')){
                            $checkAttachementCurrentSession = getSessionValue('dialogMail'.$attachName.'');
                            if($checkAttachementCurrentSession=="true"){
                              $checkAttachementCurrent=$checkAttachementCurrentSession;
                            }
                            
                          }
                          echo "<tr>";
                          echo "<td class='assignData verticalCenterData' >
                                  <div style='width:270px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;'>
                                    <div id='dialogMail".$attachName."' name='dialogMail".$attachName."' "; echo ($checkAttachementCurrent=='true')?'checked':''; echo" class='checkBoxAttachmentMail' dojoType='dijit.form.CheckBox' type='checkbox' onChange='saveDataToSession(\"dialogMail$attachName\",this.checked,false);  showAttachedSize(".json_encode($attached->fileSize).",".json_encode($attachName).",".json_encode($attached->id).",".json_encode($attached->type).");'></div>
                                    &nbsp;".$attached->fileName."
                                  </div>
                                </td>";
                          //mime and img of the attachemnt
                          echo " <td class='assignData verticalCenterData' style='text-align:center;'><div style='width:110px'>";
                          if ($attached->isThumbable()) {
                            $ext=pathinfo($attached->fileName, PATHINFO_EXTENSION);
                            if (file_exists("../view/img/mime/$ext.png")) {
                              $img="../view/img/mime/$ext.png";
                            } else {
                              $img="../view/img/mime/unknown.png";
                            }
                            echo '<img src="'.$img.'" '.' title="'.htmlEncode($attachName).'" style="float:center;cursor:pointer"'.' onClick="showImage(\'Attachment\',\''.htmlEncode($attached->id).'\',\''.htmlEncode($attached->fileName, 'protectQuotes').'\');" />';
                          } else {
                            echo htmlGetMimeType($attached->mimeType, $attached->fileName, $attached->id,'Attachment',"float:center");
                          }
                          echo "</div></td>";
                          //
                          echo " <td class='assignData verticalCenterData' style='width:105px;text-align:center;'><div style='width:100px'>".octectConvertSize($attached->fileSize)."</div></td>";
                          if(1 or !empty($lstDoc)){
                           echo " <td class='assignData verticalCenterData' style='text-align:center;'><div style='width:165px'></div></td>";
                          }
                          echo " </tr>";
                        }
                        if(!empty($lstDoc)){
                          echo "<tr>";
                          echo "<td class='assignHeader'><div style='width:280px'>".i18n('Document')."&nbsp;</div></td>";
                          echo "<td class='assignHeader'><div style='width:120px'>".i18n('dashboardTicketMainTitleType')."</div></td>";
                          echo "<td class='assignHeader'><div style='width:110px'>".i18n('FileSize')."</div></td>";
                          echo "<td class='assignHeader'><div style='width:175px'>".i18n('DocumentVersion')."</div></td>";
                          echo "</tr>";
                          echo "<tr>";
                          foreach($lstDoc as $document){
                             $filsize=0;
                             if($document->ref1Type=='DocumentVersion'){
                                $docV= new DocumentVersion($document->ref1Id);
                                $docIm=$docV;
                                $name=$docV->fullName;
                                $filsizeRef=$docV->fileSize;
                                $docId=$docV->id;
                                $type='DocumentVersion';
                             }else{
                               $doc= new Document($document->ref1Id);
                               if($doc->idDocumentVersionRef=="" and $doc->idDocumentVersion==""){
                                  continue;
                               }
                               $vers='';
                               $name=$doc->name;
                               $docId=(($doc->idDocumentVersionRef!='')?$doc->idDocumentVersionRef:$doc->idDocumentVersion);
                               $docVersRf=new DocumentVersion($docId);
                               $docIm=$docVersRf;
                               $filsizeRef=(($docVersRf->fileSize=='')?'-':$docVersRf->fileSize);
                               if($doc->idDocumentVersion!=''){
                                $docVers=new DocumentVersion($doc->idDocumentVersion);
                                $docIdV=$docVers->id;
                                $filsize=(($docVers->fileSize=='')?'-':$docVers->fileSize);
                                $vers=$docVers->name;
                               }
                               $versRef=$docVersRf->name;
                               if($versRef=="" and $vers!=""){
                                 $versRef=$vers;
                                 $filsizeRef=$filsize;
                               }
                               $type='DocumentVersion';
                            }
                            echo "<td class='assignData verticalCenterData'><div style='width:270px'><input   id='addVersion".$name."' hidden value='$docId' />";
                            echo "<input   id='filesizeNoConvert".$name."' hidden value='".$filsizeRef."' />";
                            echo "<div id='dialogMail".$name."' name='dialogMail".$name."'  dojoType='dijit.form.CheckBox' type='checkbox' class='checkBoxAttachmentMail'  onChange='showAttachedSize(dojo.byId(\"filesizeNoConvert".$name."\").value,".json_encode($name).",dojo.byId(\"addVersion".$name."\").value,".json_encode($type).");' ></div>&nbsp;".$name."</div></td>";
                            //mime and img of the doc
                            echo " <td class='assignData verticalCenterData' style='text-align:center;'><div style='width:110px'>";
                            if ($docIm->isThumbable()) {
                              $ext=pathinfo($docIm->fileName, PATHINFO_EXTENSION);
                              if (file_exists("../view/img/mime/$ext.png")) {
                                $img="../view/img/mime/$ext.png";
                              } else {
                                $img="../view/img/mime/unknown.png";
                              }
                              echo '<img src="'.$img.'" '.' title="'.htmlEncode($docIm->fileName).'" style="float:center;cursor:pointer"'.' onClick="showImage(\'DocumentVersion\',\''.htmlEncode($docIm->id).'\',\''.htmlEncode($docIm->fileName, 'protectQuotes').'\');" />';
                            } else {
                              echo htmlGetMimeType($docIm->mimeType, $docIm->fileName, $docIm->id,'DocumentVersion',"float:center");
                            }
                            echo "</div></td>";
                            //
                            echo " <td class='assignData verticalCenterData' style='text-align:center;'><div style='width:100px'>";
                            echo "     <input readonly class='assignData verticalCenterData'  id='filesize".$name."' style='border:none;position:relative;text-align: center;width:95px' value='".octectConvertSize($filsizeRef)."' /></div></td>";
                            if($document->ref1Type!='DocumentVersion' and $versRef!==$vers ){
                              echo "<td class='assignData verticalCenterData'><div style='width:165px'>";
                              echo " <input name='v1_".$name."' id='v1_".$name."'  class='input'  hidden value='$filsizeRef' />";
                              echo " <input name='idDocRef".$name."' id='idDocRef".$name."'  class='input'  hidden value='$docId' />";
                              echo " <input name='v2_".$name."' id='v2_".$name."'  class='input'  hidden value='$filsize' />";
                              echo " <input name='idDoc".$name."' id='idDoc".$name."'  class='input'  hidden value='$docIdV' />";
                              echo "<table style='width:100%;'><tr><td style='width:50%;'><label title=".i18n('colReferenceDocumentVersion')."  style='width:30%;' for='versionRef".$name."'>".$versRef."</label>";
                              echo "&nbsp;&nbsp;<input title=".i18n('colReferenceDocumentVersion')." type='radio' data-dojo-type='dijit/form/RadioButton'  name='vers".$name."' id='versionRef".$name."' checked onChange='changeFileSizeMail(".json_encode($name).");'/></td>";
                              echo "<td><label title=".i18n('lastVersion')."  style='width:30%;' for='version".$name."'>".$vers."</label>";
                              echo "&nbsp;&nbsp;<input title=".i18n('lastVersion')." type='radio' data-dojo-type='dijit/form/RadioButton'  name='vers".$name."' id='version".$name."'/></td></tr></table></div></td>";
                            }else{
                              echo " <td class='assignData verticalCenterData' style='text-align:center' ><div style='width:165px' >".((isset($docV))?$docV->name:$versRef)."</div></td>";
                            }
                            echo " </tr>";
                          }
                          ///<div dojoType='dijit.Tooltip' connectId='version".$name."' position='above'>".i18n('lastVersion')."</div><div dojoType='dijit.Tooltip' connectId='versionRef".$name."' position='above'>".i18n('colReferenceDocumentVersion')."</div>
                        }?>
                    </table>
										</div>
      							<div id='showAddAttachment' style="max-height:232px;overflow-y:auto;overflow-x:hidden;float:none;width:700px; display:block;" dojoType="dijit.layout.ContentPane" region="center"></div>
                  </div>
              	</td>
            	</tr>
        		</table>	
      <?php }
      if((empty($lstAttach) && empty($lstDoc))){ ?>
      <div id='showAddAttachment' style="max-height:435px;overflow-y:auto;overflow-x:hidden;float:none;width:700px; display:block;" dojoType="dijit.layout.ContentPane" region="center"></div>
      <?php } ?>
      <br/>
     	 <table id="dialogMailButtonOkCancel" align="center" colspan="3" style="<?php echo $styleTableOkCancelButton ?>">
    			<tr>
    				<td>
            <button dojoType="dijit.form.Button" type="button"
              onclick="dijit.byId('dialogMail').hide(); var minimizedMailIcon=dojo.query('[id^=mailEditorMinimizedIcon_]').shift(); if (minimizedMailIcon) minimizedMailIcon.parentNode.removeChild(minimizedMailIcon);repositionMinimizedIcons();">
              <?php echo i18n("buttonCancel");?>
            </button>
             <button dojoType="dijit.form.Button" type="submit" id="dialogMailSubmit" onclick="
                if (typeof CKEDITOR !== 'undefined') {
                  for (var instance in CKEDITOR.instances) {
                    if (instance === 'dialogMailMessage' || instance.indexOf('mailMailEditor') !== -1) {
                      CKEDITOR.instances[instance].updateElement();
                      var content = CKEDITOR.instances[instance].getData();
                      dojo.byId('dialogMailMessage').value = content;
                      break;
                    }
                  }
                }
                stockEmailCurrent();
                protectDblClick(this);
                getAddedAttachment(true,true);
                sendMail('DialogMail');
                return false;">
      				<?php echo i18n("buttonOK");?>
      	  	</button>
      	  	</td>
      	  </tr>
       </table>
      </td>
  	</tr>
  </table>
</form>   
