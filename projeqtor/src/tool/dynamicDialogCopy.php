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
if (!pq_array_key_exists('objectClass', $_REQUEST)) {
  throwError('Parameter objectClass not found in REQUEST');
}
$objectClass=$_REQUEST['objectClass'];
Security::checkValidClass($objectClass);
if (!pq_array_key_exists('objectId', $_REQUEST)) {
  throwError('Parameter objectId not found in REQUEST');
}
$objectId=$_REQUEST['objectId'];
Security::checkValidId($objectId);
if (!pq_array_key_exists('copyType', $_REQUEST)) {
  throwError('Parameter copyType not found in REQUEST');
}
$copyType=$_REQUEST['copyType'];
if ($copyType!='copyObjectTo'&&$copyType!='copyProject'&&$copyType!='copyVersion') {
  traceHack('dynamicDialogCopy: $copyType contains an unexpected valid value');
}
$fromContextMenu=RequestHandler::getBoolean('fromContextMenu');

$idClass=SqlList::getIdFromTranslatableName('Copyable', $objectClass);
$toCopy=new $objectClass($objectId);
$pe=$objectClass . 'PlanningElement';
$moveAfterCreate=null;
if (property_exists($toCopy, $pe)) {
  $moveAfterCreateObj=PlanningElement::getSingleSqlElementFromCriteria('PlanningElement', array(
      'refType'=>$objectClass,
      'refId'=>$objectId));
  if (isset($moveAfterCreateObj->id) and $moveAfterCreateObj->id) {
    $moveAfterCreate=$moveAfterCreateObj->id;
  }
}

$newObj=new $objectClass();
$allowedStatusList=Workflow::getAllowedStatusListForObject($newObj);
$status=new Status();
if (isset($allowedStatusList) and count($allowedStatusList)>0) {
  $status=reset($allowedStatusList);
}
$copyToClassId=0;
if ($copyType=="copyObjectTo") {
  $copyToClassId=SqlList::getFieldFromId('Copyable', $idClass, 'idDefaultCopyable', false);
  if ($copyToClassId) {
    $copyToClass=SqlList::getNameFromId('Copyable', $copyToClassId, false);
  } else {
    $copyToClassId=$idClass;
    $copyToClass=$objectClass;
  }
  $userCopyToClassId=Parameter::getUserParameter('copyObjectToLastClass' . $objectClass);
  if ($userCopyToClassId&&is_numeric($userCopyToClassId)) {
    $copyableTest=new Copyable($userCopyToClassId);
    if ($copyableTest->id) {
      $copyToClassId=$userCopyToClassId;
      $copyToClass=$copyableTest->name;
    }
  }

  ?>
<table>
	<tr>
		<td>
			<form dojoType="dijit.form.Form" id='copyForm' name='copyForm'
				onSubmit="return false;">
				<input id="copyClass" name="copyClass" type="hidden" value="" /> 
				<input id="copyId" name="copyId" type="hidden" value="" /> 
				<input id="copyFromContextMenu" name="copyFromContextMenu" type="hidden" value="<?php echo $fromContextMenu;?>" /> 
				<input id="moveAfterCreate" name="moveAfterCreate" type="hidden" value="<?php echo $moveAfterCreate?>" />
				<input id="copyEditorType" name="copyEditorType" type="hidden" value="<?php echo getEditorType();?>" />
				<table>
					<tr>
						<td valign="top" style="width: 50%; padding: 15px 15px 0px 10px;">
							<table>
								<tr>
									<td class="dialogLabel"><label for="copyToName"><?php echo i18n("copyToName") ?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label></td>
									<td>
                   <?php
                    if ($objectClass=='SubTask') {
                        if (isTextFieldHtmlFormatted($toCopy->name)) {
                          $text=new Html2Text($toCopy->name);
                          $val=$text->getText();
                        } else {
                          $val=br2nl($toCopy->name);
                        }
                        $val=pq_str_replace('"', '""', $val);
                        $name=pq_substr($val, 0, 100);
                      } else {
                        $name=pq_str_replace('"', '&quot;', $toCopy->name);
                      }
                    ?>
                     <select id="copyToName" name="copyToName"
      										dojoType="dijit.form.ValidationTextBox" required="required"
      										style="width: 400px;" trim="true" maxlength="100"
      										class="input required" value="<?php echo $name;?>">
      							</select>
									</td>
								</tr>
								<tr>
									<td>&nbsp;</td>
									<td>&nbsp;</td>
								</tr>
           			<?php if ($copyType=='copyObjectTo' and property_exists($toCopy, 'idProject')) {?>
           			<tr>
									<td class="dialogLabel"><label for="copyToProject"><?php echo i18n("copyToProject") ?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label></td>
									<td>
										<div id="copyToProject" name="copyToProject"
											dojoType="dijit.form.FilteringSelect" required="required"
											class="input required" style="width: 400px;"
											data-dojo-props="queryExpr: '*${0}*',autoComplete:false"
											<?php echo autoOpenFilteringSelect();?> class="input">
                			<?php htmlDrawOptionForReference('idProject', $toCopy->idProject, null, true);?>
                      <script type="dojo/connect" event="onChange" args="evt">
                        var copyType=dijit.byId('copyToType');
                        if (copyType) {
                           var objclass=copyableArray[dijit.byId('copyToClass').get('value')];
                           refreshList("id"+objclass+"Type","idProject", this.value, null,'copyToType',true);
                        }
                      </script>
										</div>
									</td>
								</tr>
								<tr>
									<td>&nbsp;</td>
									<td>&nbsp;</td>
								</tr>
           <?php }?>
           			<tr>
									<td class="dialogLabel"><label for="copyToClass"><?php echo i18n("copyToClass") ?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
									</td>
									<td><select dojoType="dijit.form.FilteringSelect"
										<?php echo autoOpenFilteringSelect(); if($objectClass == 'CatalogUO'){ ?>
										readOnly <?php }?> id="copyToClass" name="copyToClass"
										required="required" class="input required">
                 <?php htmlDrawOptionForReference('idCopyable', $copyToClassId, $toCopy, ($copyToClass=="SubTask")?false:true,'idle','0');?>
                 <script type="dojo/connect" event="onChange" args="evt">
                   saveUserParameter('copyObjectToLastClass' + dojo.byId('copyClass').value, this.value);
                   var objclass=copyableArray[this.value];
                   dijit.byId('copyToType').set('value',null);
                   //dijit.byId('copyToType').reset();
                   var idProjectRow = (dojo.byId('idProjectRow'))?dojo.byId('idProjectRow').value:null;
                  <?php if($objectClass!='SubTask'){?>
                   var idProject=(dijit.byId('idProject'))?dijit.byId('idProject').get('value'):idProjectRow;
                  <?php }else{?>
                   var idProject=(dijit.byId('copyToProject'))?dijit.byId('copyToProject').get('value'):idProjectRow;
                  <?php }?>
                   refreshList("id"+objclass+"Type","idProject", idProject, null,'copyToType',true);
                   /*if (dojo.byId('copyClass').value==objclass) {
                     var runModif="dijit.byId('copyToType').set('value',dijit.byId('id"+objclass+"Type').get('value'))";
                     setTimeout(runModif,1);
                   }*/
                   copyObjectToShowStructure();
                   setValueCheckBoxForUser();
 
                 </script>
									</select></td>
								</tr>
								<tr>
									<td>&nbsp;</td>
									<td>&nbsp;</td>
								</tr>
           <?php if($objectClass != 'CatalogUO'){?>
           			<tr>
									<td class="dialogLabel"><label for="copyToType"><?php echo i18n("copyToType") ?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
									</td>
									<td><select dojoType="dijit.form.FilteringSelect"
										<?php echo autoOpenFilteringSelect();?> id="copyToType"
										name="copyToType" required class="input required">
                <?php
                ($copyToClass=="PeriodicMeeting")?$colName='idMeetingType':$colName='id' . $copyToClass . 'Type';
                    if ($copyToClass!="ProviderTerm" and $copyToClass!="SubTask") {
                      htmlDrawOptionForReference($colName, (($copyToClass==$objectClass)?$toCopy->$colName:null), null, true);
                    }
                    ?>
               </select></td>
								</tr>
								<tr>
									<td>&nbsp;</td>
									<td>&nbsp;</td>
								</tr>
           <?php }?>
           <?php if (property_exists($toCopy, 'description')) {?>
          			 <tr>
									<td class="dialogLabel" colspan="2" style="text-align: left;">
										<label style="text-align: left;padding-bottom: 10px;" for="copyToDescription"><?php echo ucfirst(i18n("colDescription")). ' :' ?><?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
									</td>
								</tr>
								<tr>
									<td colspan="2">
               <?php
                $descriptionValue=pq_str_replace('"', '&quot;', $toCopy->description);
                $descriptionWidth=590;
                $descriptionHeight=120;
                if (getEditorType()=="CK" or getEditorType()=="CKInline") {
              ?>
                 <textarea style="width:<?php echo $descriptionWidth; ?>px; height:<?php echo $descriptionHeight; ?>px" tabindex="1"
                   name="copyToDescription" id="copyToDescription" ><?php echo $descriptionValue;?></textarea>
               <?php } else if (getEditorType() == "text") {?>
                 <textarea dojoType="dijit.form.Textarea"
                   id="copyToDescription" name="copyToDescription"
                   style="max-width:<?php echo $descriptionWidth;?>px;height:<?php echo $descriptionHeight;?>px;max-height:<?php echo $descriptionHeight;?>px"
                   maxlength="4000"
                   class="input" ><?php echo $descriptionValue;?></textarea>
               <?php } else { ?>
                 <textarea dojoType="dijit.form.Textarea" type="hidden"
											id="copyToDescription" name="copyToDescription"
											style="display: none;"><?php echo $descriptionValue;?></textarea>
										<div data-dojo-type="dijit.Editor" id="copyDescriptionEditor"
                   data-dojo-props="onChange:function(){window.top.dojo.byId('copyToDescription').value=arguments[0];}
                     ,plugins:['removeFormat','bold','italic','underline','|', 'indent', 'outdent', 'justifyLeft', 'justifyCenter', 
                               'justifyRight', 'justifyFull','|','insertOrderedList','insertUnorderedList','|']
                     ,extraPlugins:['dijit._editor.plugins.AlwaysShowToolbar','foreColor','hiliteColor']"
                   style="color:#606060 !important; background:none;padding:3px 0px 3px 3px;margin-right:2px;width:<?php echo $descriptionWidth;?>px;overflow:auto;"
                   class="input" >
                   <?php echo $descriptionValue;?>
                 </div>
               <?php } ?>
             </td>
								</tr>

           <?php }?>
             </table>
						</td>
						<td valign="top"
							style="width: 50%; border-left: 1px solid #d0d0d0; padding: 0px 0px 25px 15px;">
							<table>
								<tr>
									<td>&nbsp;</td>
									<td>&nbsp;</td>
								</tr>
                 <?php  if($objectClass=='Requirement'){?>
            		<tr>
									<td class="dialogLabel" colspan="2"
										style="width: 100%; text-align: left;"><label
										for="copyStructure" style="width: 90%; text-align: right;"><?php echo i18n("copyStructure") ?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
               <?php
                $isCheckedSructure=true;
                $isCheckedSructure=(Parameter::getUserParameter('isCheckedSructure' . $objectClass . $copyToClassId))?Parameter::getUserParameter('isCheckedSructure' . $objectClass . $copyToClassId):Parameter::getUserParameter('isCheckedSructure' . $objectClass);
                ?>
               <div id="copyStructureRequirement" name="copyStructure"
											dojoType="dijit.form.CheckBox"
											<?php if ($isCheckedSructure=='true') echo " checked ";?>
											type="checkbox">
											<script type="dojo/method" event="onChange">
                  var type=dijit.byId('copyToClass').get('value');
                  saveDataToSession('isCheckedSructure<?php echo $objectClass;?>'+type,((this.checked)?true:false),true);
                  saveDataToSession('isCheckedSructure<?php echo $objectClass;?>',((this.checked)?true:false),true);
               </script>
										</div></td>
								</tr>
								<tr>
									<td class="dialogLabel" colspan="2"
										style="width: 100%; text-align: left;"><label
										for="duplicateLinkedTestsCases"
										style="width: 90%; text-align: right;"><?php echo i18n("DuplicateLinkedTestsCases") ?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
               <?php
                $isCheckedDuplicateLink=true;
                $isCheckedDuplicateLink=(Parameter::getUserParameter('isCheckedDuplicateLink' . $objectClass . $copyToClassId))?Parameter::getUserParameter('isCheckedDuplicateLink' . $objectClass . $copyToClassId):Parameter::getUserParameter('isCheckedDuplicateLink' . $objectClass);
                ?>
               <div id="duplicateLinkedTestsCases"
											name="duplicateLinkedTestsCases"
											dojoType="dijit.form.CheckBox"
											<?php if ($isCheckedDuplicateLink=='true') echo " checked ";?>
											type="checkbox">
											<script type="dojo/method" event="onChange">
                  var type=dijit.byId('copyToClass').get('value');
                  saveDataToSession('isCheckedDuplicateLink<?php echo $objectClass;?>'+type,((this.checked)?true:false),true);
                  saveDataToSession('isCheckedDuplicateLink<?php echo $objectClass;?>',((this.checked)?true:false),true);
               </script>
										</div></td>
								</tr>
           
            <?php }
            if ($objectClass!="SubTask") {
              ?>
           			<tr>
									<td class="dialogLabel" colspan="2"
										style="width: 100%; text-align: left;">
										<div id="copyWithStructureDiv" style="display: none;">
											<label for="copyWithStructure" class="copyWithStructureClass"
												style="width: 90%; text-align: right;"><?php echo i18n("copyWithStructure") ?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
	               <?php
                $isCheckedStructure=true;
                $isCheckedStructure=(Parameter::getUserParameter('isCheckedStructure' . $objectClass . $copyToClassId))?Parameter::getUserParameter('isCheckedStructure' . $objectClass . $copyToClassId):Parameter::getUserParameter('isCheckedStructure' . $objectClass);
                ?>
	               <div id="copyWithStructure" name="copyWithStructure"
												class="copyWithStructureClass"
												dojoType="dijit.form.CheckBox"
												<?php if ($isCheckedStructure=='true') echo " checked ";?>
												type="checkbox">
												<script type="dojo/method" event="onChange">
                  var type=dijit.byId('copyToClass').get('value');
                    saveDataToSession('isCheckedStructure<?php echo $objectClass;?>'+type,((this.checked)?true:false),true);
                    saveDataToSession('isCheckedStructure<?php echo $objectClass;?>',((this.checked)?true:false),true);
                 </script>
											</div>
											<br /> <label for="copyWithAssignments"
												style="width: 90%; text-align: right;"><?php echo i18n("copyAssignments") ?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
                 <?php
                  $isCheckedWithAsignments=true;
                  $isCheckedWithAsignments=(Parameter::getUserParameter('isCheckedWithAsignments' . $objectClass . $copyToClassId))?Parameter::getUserParameter('isCheckedWithAsignments' . $objectClass . $copyToClassId):Parameter::getUserParameter('isCheckedWithAsignments' . $objectClass);
                  ?>
                 <div id="copyWithAssignments"
												name="copyWithAssignments" dojoType="dijit.form.CheckBox"
												<?php if ($isCheckedWithAsignments=='true') echo " checked ";?>
												type="checkbox">
												<script type="dojo/method" event="onChange">
                    var type=dijit.byId('copyToClass').get('value');
                    saveDataToSession('isCheckedWithAsignments<?php echo $objectClass;?>'+type,((this.checked)?true:false),true);
                    saveDataToSession('isCheckedWithAsignments<?php echo $objectClass;?>',((this.checked)?true:false),true);
                 </script>
											</div>
										</div>
									</td>
								</tr>
           <?php
          }
          if ($objectClass!="CatalogUO" and $objectClass!='SubTask') {
          if ($copyToClass!="Asset") {
          ?> 
           <tr>
									<td class="dialogLabel" colspan="2"
										style="width: 100%; text-align: left;"><label
										for="copyToOrigin" style="width: 90%; text-align: right;"><?php echo i18n("copyToOrigin") ?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
               <?php
                $isCheckedOrigin=true;
                $isCheckedOrigin=(Parameter::getUserParameter('isCheckedOrigin' . $objectClass . $copyToClassId))?Parameter::getUserParameter('isCheckedOrigin' . $objectClass . $copyToClassId):Parameter::getUserParameter('isCheckedOrigin' . $objectClass);
                ?>
               <div id="copyToOrigin" name="copyToOrigin"
											dojoType="dijit.form.CheckBox"
											<?php if ($isCheckedOrigin=='true') echo " checked ";?>
											type="checkbox">
											<script type="dojo/method" event="onChange">
                  var type=dijit.byId('copyToClass').get('value');
                  saveDataToSession('isCheckedOrigin<?php echo $objectClass;?>'+type,((this.checked)?true:false),true);
                  saveDataToSession('isCheckedOrigin<?php echo $objectClass;?>',((this.checked)?true:false),true);
               </script>
										</div></td>
								</tr>
								<tr>
									<td class="dialogLabel" colspan="2"
										style="width: 100%; text-align: left;"><label
										for="copyToLinkOrigin" style="width: 90%; text-align: right;"><?php echo i18n("copyToLinkOrigin") ?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
               <?php
                $isCheckedLinkOrigin=true;
                $isCheckedLinkOrigin=(Parameter::getUserParameter('isCheckedLinkOrigin' . $objectClass . $copyToClassId))?Parameter::getUserParameter('isCheckedLinkOrigin' . $objectClass . $copyToClassId):Parameter::getUserParameter('isCheckedLinkOrigin' . $objectClass);
                ?>
               <div id="copyToLinkOrigin" name="copyToLinkOrigin"
											dojoType="dijit.form.CheckBox"
											<?php if ($isCheckedLinkOrigin=='true') echo " checked ";?>
											type="checkbox">
											<script type="dojo/method" event="onChange">
                  var type=dijit.byId('copyToClass').get('value');
                  saveDataToSession('isCheckedLinkOrigin<?php echo $objectClass;?>'+type,((this.checked)?true:false),true);
                  saveDataToSession('isCheckedLinkOrigin<?php echo $objectClass;?>',((this.checked)?true:false),true);
                  var synchronizationLink = document.getElementById('synchronizationLinkCopy');
                  var synchronizationLinkDiv = document.querySelector('div[widgetid="synchronizationLinkCopy"]');
                  var synchronizationLinkInput = document.querySelector('input[name="synchronizationLinkCopy"]');
                  if (this.checked) {
                    synchronizationLink.style.display = 'block';
                  } else {
                    synchronizationLink.style.display = 'none';
                    synchronizationLinkDiv.classList.remove("dijitCheckBoxChecked", "dijitChecked");
                    synchronizationLinkInput.setAttribute("aria-checked", "false");
                  }
               </script>
										</div>

										<div id="synchronizationLinkCopy" style="display: <?php echo ($isCheckedLinkOrigin == 'true') ? 'block' : 'none'; ?>;">
											<label for="synchronizationLinkCopyField"
												style="width: 90%; text-align: right;">
                    <?php echo i18n("synchronizationLink"); ?>&nbsp;
                    <?php if(!isNewGui()){?>:<?php }?>
                    &nbsp;
                </label>
                <?php
                $isCheckedSynchronizationLink=true;
                $isCheckedSynchronizationLink=(Parameter::getUserParameter('isCheckedSynchronizationLink' . $objectClass . $copyToClassId))?Parameter::getUserParameter('isCheckedSynchronizationLink' . $objectClass . $copyToClassId):Parameter::getUserParameter('isCheckedSynchronizationLink' . $objectClass);
                ?>
                <div id="synchronizationLinkCopy"
												name="synchronizationLinkCopy"
												dojoType="dijit.form.CheckBox"
												<?php if ($isCheckedSynchronizationLink=='true') echo " checked ";?>
												type="checkbox">
												<script type="dojo/method" event="onChange">
                    var type=dijit.byId('copyToClass').get('value');
                    saveDataToSession('isCheckedSynchronizationLink<?php echo $objectClass;?>'+type,((this.checked)?true:false),true);
                    saveDataToSession('isCheckedSynchronizationLink<?php echo $objectClass;?>',((this.checked)?true:false),true);
                  </script>
											</div>
										</div></td>
								</tr>
								<tr>
           <?php }else{ ?> 						
								<tr>
									<td class="dialogLabel" colspan="2"
										style="width: 100%; text-align: left;"><label
										for="copyStructure" style="width: 90%; text-align: right;"><?php echo i18n("copyStructure") ?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
               <?php
                $isCheckedSructure=true;
                $isCheckedSructure=(Parameter::getUserParameter('isCheckedSructure' . $objectClass . $copyToClassId))?Parameter::getUserParameter('isCheckedSructure' . $objectClass . $copyToClassId):Parameter::getUserParameter('isCheckedSructure' . $objectClass);
                ?>
               <div id="copyStructure" name="copyStructure"
											dojoType="dijit.form.CheckBox"
											<?php if ($isCheckedSructure=='true') echo " checked ";?>
											type="checkbox">
											<script type="dojo/method" event="onChange">
                  var type=dijit.byId('copyToClass').get('value');
                  saveDataToSession('isCheckedSructure<?php echo $objectClass;?>'+type,((this.checked)?true:false),true);
                  saveDataToSession('isCheckedSructure<?php echo $objectClass;?>',((this.checked)?true:false),true);
               </script>
										</div></td>
								</tr>
           <?php
          }
            }
            if ($objectClass!='SubTask') {
              ?>
           <tr>
									<td class="dialogLabel" colspan="2"
										style="width: 100%; text-align: left;"><label
										for="copyToWithLinks" style="width: 90%; text-align: right;"><?php echo i18n("copyToWithLinks") ?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
               <?php
                $isCheckedWithLink=true;
                $isCheckedWithLink=(Parameter::getUserParameter('isCheckedWithLink' . $objectClass . $copyToClassId))?Parameter::getUserParameter('isCheckedWithLink' . $objectClass . $copyToClassId):Parameter::getUserParameter('isCheckedWithLink' . $objectClass);
                ?>
               <div id="copyToWithLinks" name="copyToWithLinks"
											dojoType="dijit.form.CheckBox"
											<?php if ($isCheckedWithLink=='true') echo " checked ";?>
											type="checkbox">
											<script type="dojo/method" event="onChange">
                  var type=dijit.byId('copyToClass').get('value');
                  saveDataToSession('isCheckedWithLink<?php echo $objectClass;?>'+type,((this.checked)?true:false),true);
                  saveDataToSession('isCheckedWithLink<?php echo $objectClass;?>',((this.checked)?true:false),true);
               </script>
										</div></td>
								</tr>
           <?php if(property_exists($objectClass, '_SubTask')){?>
           <tr>
									<td class="dialogLabel" colspan="2"
										style="width: 100%; text-align: left;"><label
										for="copyToWithSubTask" style="width: 90%; text-align: right;"><?php echo i18n("copyToWithSubTask") ?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
               <?php
                $isCheckSubTask=false;
                $isCheckSubTask=(Parameter::getUserParameter('isCheckedSubTask' . $objectClass . $copyToClassId))?Parameter::getUserParameter('isCheckedSubTask' . $objectClass . $copyToClassId):Parameter::getUserParameter('isCheckedSubTask' . $objectClass);
                ?>
               <div id="copyToWithSubTask" name="copyToWithSubTask"
											dojoType="dijit.form.CheckBox"
											<?php if ($isCheckSubTask=='true') echo " checked ";?>
											type="checkbox">
											<script type="dojo/method" event="onChange">
                  var type=dijit.byId('copyToClass').get('value');
                  saveDataToSession('isCheckedSubTask<?php echo $objectClass;?>'+type,((this.checked)?true:false),true);
                  saveDataToSession('isCheckedSubTask<?php echo $objectClass;?>',((this.checked)?true:false),true);
                </script>
										</div></td>
								</tr>
           <?php }}?>
           <tr>
									<td class="dialogLabel" colspan="2"
										style="width: 100%; text-align: left;"><label
										for="copyToWithAttachments"
										style="width: 90%; text-align: right;"><?php echo i18n("copyToWithAttachments") ?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
               <?php
              $isCheckedWithAttachments=true;
              $isCheckedWithAttachments=(Parameter::getUserParameter('isCheckedWithAttachments' . $objectClass . $copyToClassId))?Parameter::getUserParameter('isCheckedWithAttachments' . $objectClass . $copyToClassId):Parameter::getUserParameter('isCheckedWithAttachments' . $objectClass);
              ?>
               <div id="copyToWithAttachments"
											name="copyToWithAttachments" dojoType="dijit.form.CheckBox"
											<?php if ($isCheckedWithAttachments=='true') echo " checked ";?>
											type="checkbox">
											<script type="dojo/method" event="onChange">
                  var type=dijit.byId('copyToClass').get('value');
                  saveDataToSession('isCheckedWithAttachments<?php echo $objectClass;?>'+type,((this.checked)?true:false),true);
                  saveDataToSession('isCheckedWithAttachments<?php echo $objectClass;?>',((this.checked)?true:false),true);
               </script>
										</div></td>
								</tr>
           <?php if($objectClass!='SubTask'){?>
           <tr>
									<td class="dialogLabel" colspan="2"
										style="width: 100%; text-align: left;"><label
										for="copyToWithNotes" style="width: 90%; text-align: right;"><?php echo i18n("copyToWithNotes") ?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
               <?php
              $isCheckedWithNotes=true;
              $isCheckedWithNotes=(Parameter::getUserParameter('isCheckedWithNotes' . $objectClass . $copyToClassId))?Parameter::getUserParameter('isCheckedWithNotes' . $objectClass . $copyToClassId):Parameter::getUserParameter('isCheckedWithNotes' . $objectClass);
              ?>
               <div id="copyToWithNotes" name="copyToWithNotes"
											dojoType="dijit.form.CheckBox"
											<?php if ($isCheckedWithNotes=='true') echo " checked ";?>
											type="checkbox">
											<script type="dojo/method" event="onChange">
                  var type=dijit.byId('copyToClass').get('value');
                  saveDataToSession('isCheckedWithNotes<?php echo $objectClass;?>'+type,((this.checked)?true:false),true);
                  saveDataToSession('isCheckedWithNotes<?php echo $objectClass;?>',((this.checked)?true:false),true);
               </script>
										</div></td>
								</tr>   
           <?php } if($copyToClass!="Asset" and $objectClass!= 'CatalogUO' and $objectClass!='SubTask'){ ?> 
           <tr>
									<td class="dialogLabel" colspan="2"
										style="width: 100%; text-align: left;"><label
										for="copyToWithResult" style="width: 90%; text-align: right;"><?php echo i18n("copyToWithResult") ?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
                <?php
                $isCheckedWithResult=true;
                $isCheckedWithResult=(Parameter::getUserParameter('isCheckedWithResult' . $objectClass . $copyToClassId))?Parameter::getUserParameter('isCheckedWithResult' . $objectClass . $copyToClassId):Parameter::getUserParameter('isCheckedWithResult' . $objectClass);
                ?>
               <div id="copyToWithResult" name="copyToWithResult"
											dojoType="dijit.form.CheckBox"
											<?php if ($isCheckedWithResult=='true') echo " checked ";?>
											type="checkbox">
											<script type="dojo/method" event="onChange">
                  var type=dijit.byId('copyToClass').get('value');
                  saveDataToSession('isCheckedWithResult<?php echo $objectClass;?>'+type,((this.checked)?true:false),true);
                  saveDataToSession('isCheckedWithResult<?php echo $objectClass;?>',((this.checked)?true:false),true);
               </script>
										</div></td>
								</tr>   
         <?php } if(property_exists($objectClass, 'idStatus')){ ?> 
           <tr>
									<td class="dialogLabel" colspan="2"
										style="width: 100%; text-align: left;"><label
										for="copyToWithStatus" style="width: 90%; text-align: right;"><?php echo i18n("CopyWithStatus", array($status->name));?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
                <?php
                $isCheckedWithStatus=true;
                $isCheckedWithStatus=(Parameter::getUserParameter('isCheckedWithStatus' . $objectClass . $copyToClassId))?Parameter::getUserParameter('isCheckedWithStatus' . $objectClass . $copyToClassId):Parameter::getUserParameter('isCheckedWithStatus' . $objectClass);
                if ($isCheckedWithStatus!='false' or Parameter::getGlobalParameter('defaultSkipCopyStatus')=="YES") $isCheckedWithStatus=true;
                else if ($isCheckedWithStatus=='false' or Parameter::getGlobalParameter('defaultSkipCopyStatus')=="NO") $isCheckedWithStatus=false;
                ?>
               <div id="copyToWithStatus" name="copyToWithStatus"
											dojoType="dijit.form.CheckBox"
											<?php if ($isCheckedWithStatus=='true') echo " checked ";?>
											type="checkbox">
											<script type="dojo/method" event="onChange">
                  var type=dijit.byId('copyToClass').get('value');
                  saveDataToSession('isCheckedWithStatus<?php echo $objectClass;?>'+type,((this.checked)?true:false),true);
                  saveDataToSession('isCheckedWithStatus<?php echo $objectClass;?>',((this.checked)?true:false),true);
               </script>
										</div></td>
								</tr>   
         <?php } if($objectClass=='ProjectExpense' || $objectClass=='IndividualExpense'){ ?> 
          <tr>
									<td class="dialogLabel" colspan="2"
										style="width: 100%; text-align: left;"><label
										for="copyToWithDetail" style="width: 90%; text-align: right;"><?php echo i18n("copyToWithDetail") ?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
                <?php
                $isCheckedWithDetail=true;
                $isCheckedWithDetail=(Parameter::getUserParameter('$isCheckedWithDetail' . $objectClass . $copyToClassId))?Parameter::getUserParameter('$isCheckedWithDetail' . $objectClass . $copyToClassId):Parameter::getUserParameter('$isCheckedWithDetail' . $objectClass);
                ?>
               <div id="copyToWithDetail" name="copyToWithDetail"
											dojoType="dijit.form.CheckBox"
											<?php if ($isCheckedWithDetail=='true') echo " checked ";?>
											type="checkbox">
											<script type="dojo/method" event="onChange">
                  var type=dijit.byId('copyToClass').get('value');
                  saveDataToSession('$isCheckedWithDetail<?php echo $objectClass;?>'+type,((this.checked)?true:false),true);
                  saveDataToSession('$isCheckedWithDetail<?php echo $objectClass;?>',((this.checked)?true:false),true);
               </script>
										</div></td>
								</tr>   
         <?php } ?>
         <?php
      if ($objectClass=='Activity' or $objectClass=='Milestone' or $objectClass=='Sprint') {
          $isCheckedWithDependency=true;
          $isCheckedWithDependency=(Parameter::getUserParameter('isCheckedWithDependency' . $objectClass . $copyToClassId))?Parameter::getUserParameter('isCheckedWithDependency' . $objectClass . $copyToClassId):Parameter::getUserParameter('isCheckedWithDependency' . $objectClass);
          $isCheckedWithPredecessor=true;
          $isCheckedWithPredecessor=(Parameter::getUserParameter('isCheckedWithPredecessor' . $objectClass . $copyToClassId))?Parameter::getUserParameter('isCheckedWithPredecessor' . $objectClass . $copyToClassId):Parameter::getUserParameter('isCheckedWithPredecessor' . $objectClass);
          $isCheckedWithSuccessor=true;
          $isCheckedWithSuccessor=(Parameter::getUserParameter('isCheckedWithSuccessor' . $objectClass . $copyToClassId))?Parameter::getUserParameter('isCheckedWithSuccessor' . $objectClass . $copyToClassId):Parameter::getUserParameter('isCheckedWithSuccessor' . $objectClass);
          ?>
           <tr>
									<td class="dialogLabel" colspan="2"
										style="width: 100%; text-align: left;"><label
										for="copyToWithPredecessor"
										style="width: 90%; text-align: right;"><?php echo i18n("copyToWithPredecessor");?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
										<div id="copyToWithPredecessor" name="copyToWithPredecessor"
											dojoType="dijit.form.CheckBox"
											<?php if ($isCheckedWithPredecessor=='true') echo " checked ";?>
											<?php if($isCheckedWithDependency == 'true') echo " disabled ";?>
											type="checkbox">
											<script type="dojo/method" event="onChange">
                  if(this.checked || dijit.byId('copyToWithSuccessor').get('checked') == true){
                    if(dijit.byId('copyToWithDependency').get('disabled') == false){
                      dijit.byId('copyToWithDependency').set('disabled', true);
                    }
                    dijit.byId('copyToWithDependency').set('checked', false);
                  }else{
                    dijit.byId('copyToWithDependency').set('disabled', false);
                  }
                  var type=dijit.byId('copyToClass').get('value');
                  saveDataToSession('isCheckedWithPredecessor<?php echo $objectClass;?>'+type,((this.checked)?true:false),true);
                  saveDataToSession('isCheckedWithPredecessor<?php echo $objectClass;?>',((this.checked)?true:false),true);
               </script>
										</div></td>
								</tr>
								<tr>
									<td class="dialogLabel" colspan="2"
										style="width: 100%; text-align: left;"><label
										for="copyToWithSuccessor"
										style="width: 90%; text-align: right;"><?php echo i18n("copyToWithSuccessor");?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
										<div id="copyToWithSuccessor" name="copyToWithSuccessor"
											dojoType="dijit.form.CheckBox"
											<?php if ($isCheckedWithSuccessor=='true') echo " checked ";?>
											<?php if($isCheckedWithDependency == 'true') echo " disabled ";?>
											type="checkbox">
											<script type="dojo/method" event="onChange">
                  if(this.checked || dijit.byId('copyToWithPredecessor').get('checked') == true){
                    if(dijit.byId('copyToWithDependency').get('disabled') == false){
                      dijit.byId('copyToWithDependency').set('disabled', true);
                    }
                    dijit.byId('copyToWithDependency').set('checked', false);
                  }else{
                    dijit.byId('copyToWithDependency').set('disabled', false);
                  }
                  var type=dijit.byId('copyToClass').get('value');
                  saveDataToSession('isCheckedWithSuccessor<?php echo $objectClass;?>'+type,((this.checked)?true:false),true);
                  saveDataToSession('isCheckedWithSuccessor<?php echo $objectClass;?>',((this.checked)?true:false),true);
               </script>
										</div></td>
								</tr>
								<tr>
									<td class="dialogLabel" colspan="2"
										style="width: 100%; text-align: left;"><label
										for="copyToWithDependency"
										style="width: 90%; text-align: right;"><?php echo i18n("copyToWithDependency");?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
										<div id="copyToWithDependency" name="copyToWithDependency"
											dojoType="dijit.form.CheckBox"
											<?php if ($isCheckedWithDependency=='true') echo " checked ";?>
											<?php if($isCheckedWithPredecessor == 'true' or $isCheckedWithSuccessor == 'true') echo " disabled ";?>
											type="checkbox">
											<script type="dojo/method" event="onChange">
                  if(this.checked){
                    dijit.byId('copyToWithPredecessor').set('disabled', true);
                    dijit.byId('copyToWithPredecessor').set('checked', false);
                    dijit.byId('copyToWithSuccessor').set('disabled', true);
                    dijit.byId('copyToWithSuccessor').set('checked', false);
                  }else{
                    dijit.byId('copyToWithPredecessor').set('disabled', false);
                    dijit.byId('copyToWithSuccessor').set('disabled', false);
                  }
                  var type=dijit.byId('copyToClass').get('value');
                  saveDataToSession('isCheckedWithDependency<?php echo $objectClass;?>'+type,((this.checked)?true:false),true);
                  saveDataToSession('isCheckedWithDependency<?php echo $objectClass;?>',((this.checked)?true:false),true);
               </script>
										</div></td>
								</tr>   
         <?php }?>
             </table>
						</td>
					</tr>
					<tr>
						<td colspan="2">&nbsp;</td>
					</tr>
				</table>
			</form>
		</td>
	</tr>
	<tr>
		<td align="center"><input type="hidden" id="copyAction">
			<button class="mediumTextButton" dojoType="dijit.form.Button"
				type="button" onclick="dijit.byId('dialogCopy').hide();">
          <?php echo i18n("buttonCancel");?>
        </button>
			<button class="mediumTextButton" dojoType="dijit.form.Button"
				type="submit" id="dialogCopySubmit"
				onclick="protectDblClick(this);copyObjectToSubmit();return false;">
          <?php echo i18n("buttonOK");?>
        </button></td>
	</tr>
</table>
<?php
} else if ($copyType=="copyProject") {
  ?>
<table>
	<tr>
		<td>
			<form dojoType="dijit.form.Form" id='copyProjectForm' name='copyProjectForm' onSubmit="return false;">
				<input id="copyProjectId" name="copyProjectId" type="hidden" value="" /> <input id="moveAfterCreate" name="moveAfterCreate" type="hidden" value="<?php echo $moveAfterCreate?>" />
				<input id="copyEditorType" name="copyEditorType" type="hidden" value="<?php echo getEditorType();?>" />
				<table>
					<tr>
						<td valign="top" style="width: 50%; padding: 15px 15px 0px 10px;">
							<table>
								<tr>
									<td class="dialogLabel"><label for="copyProjectToName"><?php echo i18n("copyToName") ?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
									</td>
									<td>
										<div id="copyProjectToName" name="copyProjectToName"
											dojoType="dijit.form.ValidationTextBox" required="required"
											style="width: 400px;" trim="true" maxlength="100"
											class="input required"
											value="<?php echo ($fromContextMenu)?$toCopy->name:'';?>"></div>
									</td>
								</tr>
								<tr>
									<td>&nbsp;</td>
									<td>&nbsp;</td>
								</tr>
								<tr>
									<td class="dialogLabel"><label for="copyProjectToSubProject"><?php echo i18n("colIsSubProject") ?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
									</td>
									<td><select dojoType="dijit.form.FilteringSelect"
										data-dojo-props="queryExpr: '*${0}*',autoComplete:false"
										<?php echo autoOpenFilteringSelect();?>
										id="copyProjectToSubProject" name="copyProjectToSubProject"
										class="input">
                <?php htmlDrawOptionForReference('idProject', $toCopy->idProject,null,false);?> 
               </select></td>
								</tr>
								<tr>
									<td>&nbsp;</td>
									<td>&nbsp;</td>
								</tr>
								<tr>
									<td class="dialogLabel"><label for="copyProjectToType"><?php echo i18n("colProjectType") ?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
									</td>
									<td><select dojoType="dijit.form.FilteringSelect"
										<?php echo autoOpenFilteringSelect();?> required="required"
										id="copyProjectToType" name="copyProjectToType" required
										class="input required"
										value="<?php echo ($fromContextMenu and $toCopy->codeType != 'TMP')?$toCopy->idProjectType:'';?>">
                <?php htmlDrawOptionForReference('idProjectType', null, $toCopy, true);?>
               </select></td>
								</tr>
								<tr>
									<td>&nbsp;</td>
									<td>&nbsp;</td>
								</tr>
								<tr>
									<td class="dialogLabel"><label for="copyProjectToProjectCode"><?php echo i18n("colProjectCode") ?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
									</td>
									<td>
               <?php $required=(pq_strpos($toCopy->getFieldAttributes('projectCode'),'required')!==false)?true:false;?>
               <div id="copyProjectToProjectCode"
										name="copyProjectToProjectCode"
										dojoType="dijit.form.ValidationTextBox" style="width: 400px;"
										<?php if ($required) echo ' required="required" ';?> trim="true"
										maxlength="100"
										class="input<?php if ($required) echo ' required';?>" value="">
									</div>
									</td>
								</tr>
								<tr>
									<td>&nbsp;</td>
									<td>&nbsp;</td>
								</tr>
           <?php if (property_exists($toCopy, 'description')) {?>
          			 <tr>
									<td class="dialogLabel" colspan="2" style="text-align: left;">
										<label style="text-align: left;padding-bottom: 10px;" for="copyToDescription"><?php echo ucfirst(i18n("colDescription")). ' :' ?><?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
									</td>
								</tr>
								<tr>
									<td colspan="2">
               <?php
                $descriptionValue=pq_str_replace('"', '&quot;', $toCopy->description);
                $descriptionWidth=590;
                $descriptionHeight=120;
                if (getEditorType()=="CK" or getEditorType()=="CKInline") {
              ?>
                 <textarea style="width:<?php echo $descriptionWidth; ?>px; height:<?php echo $descriptionHeight; ?>px" tabindex="1"
                   name="copyToDescription" id="copyToDescription" ><?php echo $descriptionValue;?></textarea>
               <?php } else if (getEditorType() == "text") {?>
                 <textarea dojoType="dijit.form.Textarea"
                   id="copyToDescription" name="copyToDescription"
                   style="max-width:<?php echo $descriptionWidth;?>px;height:<?php echo $descriptionHeight;?>px;max-height:<?php echo $descriptionHeight;?>px"
                   maxlength="4000"
                   class="input" ><?php echo $descriptionValue;?></textarea>
               <?php } else { ?>
                 <textarea dojoType="dijit.form.Textarea" type="hidden"
											id="copyToDescription" name="copyToDescription"
											style="display: none;"><?php echo $descriptionValue;?></textarea>
										<div data-dojo-type="dijit.Editor" id="copyDescriptionEditor"
                   data-dojo-props="onChange:function(){window.top.dojo.byId('copyToDescription').value=arguments[0];}
                     ,plugins:['removeFormat','bold','italic','underline','|', 'indent', 'outdent', 'justifyLeft', 'justifyCenter', 
                               'justifyRight', 'justifyFull','|','insertOrderedList','insertUnorderedList','|']
                     ,extraPlugins:['dijit._editor.plugins.AlwaysShowToolbar','foreColor','hiliteColor']"
                   style="color:#606060 !important; background:none;padding:3px 0px 3px 3px;margin-right:2px;width:<?php echo $descriptionWidth;?>px;overflow:auto;"
                   class="input" >
                   <?php echo $descriptionValue;?>
                 </div>
               <?php } ?>
             </td>
								</tr>
           <?php }?>
							</table>
						</td>
						<td valign="top"
							style="width: 50%; border-left: 1px solid #d0d0d0; padding: 0px 0px 25px 15px;">
							<table>
								<tr>
									<td>&nbsp;</td>
									<td>&nbsp;</td>
								</tr>
								<tr>
									<td class="dialogLabel" colspan="2"
										style="width: 100%; text-align: left;"><label
										for="copyProjectStructure" style="width: 90%; text-align: right;"><?php echo i18n("copyProjectStructure") ?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
               <?php
                $isCheckedProjectStructure=true;
                $isCheckedProjectStructure=Parameter::getUserParameter('isCheckedProjectStructure' . $objectClass);
                ?>
               <div id="copyProjectStructure"
										name="copyProjectStructure" dojoType="dijit.form.CheckBox"
										<?php if ($isCheckedProjectStructure=='true') echo " checked ";?>
										type="checkbox" onChange="copyProjectStructureChange()">
										<script type="dojo/method" event="onChange">
                  saveDataToSession('isCheckedProjectStructure<?php echo $objectClass;?>',((this.checked)?true:false),true);
               </script>
									</div></td>
								</tr>
								<tr>
									<td class="dialogLabel" colspan="2"
										style="width: 100%; text-align: left;"><label
										for="copyOtherProjectStructure"
										style="width: 90%; text-align: right;"><?php echo i18n("copyOtherProjectStructure") ?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
               <?php
                $isCheckedOtherProjectStructure=true;
                $isCheckedOtherProjectStructure=Parameter::getUserParameter('isCheckedOtherProjectStructure' . $objectClass);
                ?>
               <div id="copyOtherProjectStructure"
										name="copyOtherProjectStructure" dojoType="dijit.form.CheckBox"
										<?php if ($isCheckedOtherProjectStructure=='true') echo " checked ";?>
										type="checkbox" onChange="copyProjectStructureChange()">
										<script type="dojo/method" event="onChange">
                  saveDataToSession('isCheckedOtherProjectStructure<?php echo $objectClass;?>',((this.checked)?true:false),true);
               </script>
									</div></td>
								</tr>
								<tr>
									<td class="dialogLabel" colspan="2"
										style="width: 100%; text-align: left;"><label
										for="copySubProjects" style="width: 90%; text-align: right;"><?php echo i18n("copySubProjects") ?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
               <?php
                $isCheckedSubProject=true;
                $isCheckedSubProject=Parameter::getUserParameter('isCheckedSubProject' . $objectClass);
                ?>
               <div id="copySubProjects" name="copySubProjects"
										dojoType="dijit.form.CheckBox"
										<?php if ($isCheckedSubProject=='true') echo " checked ";?>
										type="checkbox">
										<script type="dojo/method" event="onChange">
                  saveDataToSession('isCheckedSubProject<?php echo $objectClass;?>',((this.checked)?true:false),true);
               </script>
									</div></td>
								</tr>
								<tr>
									<td class="dialogLabel" colspan="2"
										style="width: 100%; text-align: left;"><label
										for="copyProjectAffectations"
										style="width: 90%; text-align: right;"><?php echo i18n("copyProjectAffectations") ?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>              
               <?php
              $isCheckedProjectAffectation=Parameter::getUserParameter('isCheckedProjectAffectation' . $objectClass);
              ?>
               <div id="copyProjectAffectations"
										name="copyProjectAffectations" dojoType="dijit.form.CheckBox"
										<?php if ($isCheckedProjectAffectation=='true') echo " checked ";?>
										type="checkbox">
										<script type="dojo/method" event="onChange">
                  saveDataToSession('isCheckedProjectAffectation<?php echo $objectClass;?>',((this.checked)?true:false),true);
                </script>
									</div></td>
								</tr>
								<tr>
									<td class="dialogLabel" colspan="2"
										style="width: 100%; text-align: left;"><label
										for="copyProjectAssignments"
										style="width: 90%; text-align: right;"><?php echo i18n("copyAssignments") ?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
               <?php
              $isCheckedProjectAssignment=Parameter::getUserParameter('isCheckedProjectAssignment' . $objectClass);
              ?>
               <div id="copyProjectAssignments"
										name="copyProjectAssignments" dojoType="dijit.form.CheckBox"
										<?php if ($isCheckedProjectAssignment=='true') echo " checked ";?>
										type="checkbox">
										<script type="dojo/method" event="onChange">
                  saveDataToSession('isCheckedProjectAssignment<?php
                  echo $objectClass;
                    ?>',((this.checked)?true:false),true);
                </script>
									</div></td>
								</tr>
								<!--  Krowry #2206 -->
								<tr>
									<td class="dialogLabel" colspan="2"
										style="width: 100%; text-align: left;"><label
										for="copyToWithVersionProjects"
										style="width: 90%; text-align: right;"><?php echo i18n("copyToWithVersionProjects") ?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
               <?php
              $isCheckedVersionProjects=true;
              $isCheckedVersionProjects=Parameter::getUserParameter('isCheckedVersionProjects' . $objectClass);
              ?>
               <div id="copyToWithVersionProjects"
										name="copyToWithVersionProjects" dojoType="dijit.form.CheckBox"
										<?php if ($isCheckedVersionProjects=='true') echo " checked ";?>
										type="checkbox">
										<script type="dojo/method" event="onChange">
                  saveDataToSession('isCheckedVersionProjects<?php echo $objectClass;?>',((this.checked)?true:false),true);
                </script>
									</div></td>
								</tr>
								<tr>
									<td class="dialogLabel" colspan="2"
										style="width: 100%; text-align: left;"><label
										for="copyProjectRequirement"
										style="width: 90%; text-align: right;"><?php echo i18n("copyProjectRequirement") ?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
               <?php
                $isCheckedProjectRequirement=true;
                $isCheckedProjectRequirement=Parameter::getUserParameter('isCheckedProjectRequirement' . $objectClass);
                ?>
               <div id="copyProjectRequirement"
										name="copyProjectRequirement" dojoType="dijit.form.CheckBox"
										<?php if ($isCheckedProjectRequirement=='true') echo " checked ";?>
										type="checkbox">
										<script type="dojo/method" event="onChange">
                  saveDataToSession('isCheckedProjectRequirement<?php echo $objectClass;?>',((this.checked)?true:false),true);
               </script>
									</div></td>
								</tr>
								<tr>
									<td class="dialogLabel" colspan="2"
										style="width: 100%; text-align: left;"><label
										for="copyProjectRiskOpportunity"
										style="width: 90%; text-align: right;"><?php echo i18n("copyProjectRiskOpportunity") ?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
               <?php
                $isCheckedProjectRiskOpportunity=Parameter::getUserParameter('isCheckedProjectRiskOpportunity' . $objectClass);
                ?>
               <div id="copyProjectRiskOpportunity"
										name="copyProjectRiskOpportunity" dojoType="dijit.form.CheckBox"
										<?php if ($isCheckedProjectRiskOpportunity=='true') echo " checked ";?>
										type="checkbox">
										<script type="dojo/method" event="onChange">
                  saveDataToSession('isCheckedProjectRiskOpportunity<?php echo $objectClass;?>',((this.checked)?true:false),true);
               </script>
									</div></td>
								</tr>
								<!-- ADD BY Marc TABARY - 2017-03-17 - COPY ACTIVITY PRICE WHEN COPY PROJECT -->
								<tr>
									<td class="dialogLabel" colspan="2"
										style="width: 100%; text-align: left;"><label
										for="copyToWithActivityPrice"
										style="width: 90%; text-align: right;"><?php echo i18n("copyToWithActivityPrice") ?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
                <?php
                $isCheckedActivityPrice=Parameter::getUserParameter('isCheckedActivityPrice' . $objectClass);
                ?>
               <div id="copyToWithActivityPrice"
										name="copyToWithActivityPrice" dojoType="dijit.form.CheckBox"
										<?php if ($isCheckedActivityPrice=='true') echo " checked ";?>
										type="checkbox">
										<script type="dojo/method" event="onChange">
                  saveDataToSession('isCheckedActivityPrice<?php echo $objectClass;?>',((this.checked)?true:false),true);
                </script>
									</div></td>
								</tr>
								<!-- END ADD BY Marc TABARY - 2017-03-17 - COPY ACTIVITY PRICE WHEN COPY PROJECT -->
								<!-- Gautier #1769 -->
								<tr>
									<td class="dialogLabel" colspan="2"
										style="width: 100%; text-align: left;"><label
										for="copyToWithLinks" style="width: 90%; text-align: right;"><?php echo i18n("copyToWithLinks") ?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
               <?php
                $isCheckedLink=true;
                $isCheckedLink=Parameter::getUserParameter('isCheckedLink' . $objectClass);
                ?>
               <div id="copyToWithLinks" name="copyToWithLinks"
										dojoType="dijit.form.CheckBox"
										<?php if ($isCheckedLink=='true') echo " checked ";?>
										type="checkbox">
										<script type="dojo/method" event="onChange">
                  saveDataToSession('isCheckedLink<?php echo $objectClass;?>',((this.checked)?true:false),true);
                </script>
									</div></td>
								</tr>
           <?php if(property_exists($objectClass, '_SubTask')){?>
           <tr>
									<td class="dialogLabel" colspan="2"
										style="width: 100%; text-align: left;"><label
										for="copyToWithSubTask" style="width: 90%; text-align: right;"><?php echo i18n("copyToWithSubTask") ?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
               <?php
              $isCheckSubTask=false;
                $isCheckSubTask=Parameter::getUserParameter('isCheckedSubTask' . $objectClass);
                ?>
               <div id="copyToWithSubTask" name="copyToWithSubTask"
										dojoType="dijit.form.CheckBox"
										<?php if ($isCheckSubTask=='true') echo " checked ";?>
										type="checkbox">
										<script type="dojo/method" event="onChange">
                  saveDataToSession('isCheckedSubTask<?php echo $objectClass;?>',((this.checked)?true:false),true);
                </script>
									</div></td>
								</tr>
           <?php }?>
          <!-- Gautier #copyAttachments Project -->
								<tr>
									<td class="dialogLabel" colspan="2"
										style="width: 100%; text-align: left;"><label
										for="copyToWithAttachments"
										style="width: 90%; text-align: right;"><?php echo i18n("copyToWithAttachments") ?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
               <?php
                $isCheckedWithAttachments=true;
                $isCheckedWithAttachments=Parameter::getUserParameter('isCheckedWithAttachments' . $objectClass);
                ?>
               <div id="copyToWithAttachments"
										name="copyToWithAttachments" dojoType="dijit.form.CheckBox"
										<?php if ($isCheckedWithAttachments=='true') echo " checked ";?>
										type="checkbox">
										<script type="dojo/method" event="onChange">
                  saveDataToSession('isCheckedWithAttachments<?php echo $objectClass;?>',((this.checked)?true:false),true);
               </script>
									</div></td>
								</tr>
           <?php if(property_exists($objectClass, 'idStatus')){ ?> 
           <tr>
									<td class="dialogLabel" colspan="2"
										style="width: 100%; text-align: left;"><label
										for="copyToWithStatus" style="width: 90%; text-align: right;"><?php echo i18n("CopyWithStatus", array($status->name));?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
                <?php
                $isCheckedWithStatus=true;
                $isCheckedWithStatus=(Parameter::getUserParameter('isCheckedWithStatus' . $objectClass . $copyToClassId))?Parameter::getUserParameter('isCheckedWithStatus' . $objectClass . $copyToClassId):Parameter::getUserParameter('isCheckedWithStatus' . $objectClass);
                if ($isCheckedWithStatus!='false' or Parameter::getGlobalParameter('defaultSkipCopyStatus')=="YES") $isCheckedWithStatus=true;
                else if ($isCheckedWithStatus=='false' or Parameter::getGlobalParameter('defaultSkipCopyStatus')=="NO") $isCheckedWithStatus=false;
                ?>
               <div id="copyToWithStatus" name="copyToWithStatus"
										dojoType="dijit.form.CheckBox"
										<?php if ($isCheckedWithStatus=='true') echo " checked ";?>
										type="checkbox">
										<script type="dojo/method" event="onChange">
                  saveDataToSession('isCheckedWithStatus<?php echo $objectClass;?>',((this.checked)?true:false),true);
               </script>
									</div></td>
								</tr>   
         <?php }?> 
							</table>
						</td>
					</tr>
					<tr>
						<td colspan="2">&nbsp;</td>
					</tr>
				</table>
			</form>
		</td>
	</tr>
	<tr>
		<td align="center"><input type="hidden" id="copyProjectAction">
			<button class="mediumTextButton" dojoType="dijit.form.Button"
				type="button" onclick="dijit.byId('dialogCopy').hide();">
          <?php echo i18n("buttonCancel");?>
        </button>
			<button class="mediumTextButton" dojoType="dijit.form.Button"
				type="submit" id="dialogCopySubmit"
				onclick="protectDblClick(this);copyProjectToSubmit();return false;">
          <?php echo i18n("buttonOK");?>
        </button></td>
	</tr>
</table>
<?php

}else if ($copyType=="copyVersion") {
  if ($objectClass=='ComponentVersion') {
    $source=new Component($toCopy->idComponent);
    $type=$toCopy->idComponentVersionType;
  } else if ($objectClass=='ProductVersion') {
    $source=new Product($toCopy->idProduct);
    $type=$toCopy->idProductVersionType;
  } else {
    errorLog("object class $objectClass not taken into account for copy type 'copyVersion'");
    exit();
  }
  $paramNameAutoformat=Parameter::getGlobalParameter('versionNameAutoformat');
  $paramNameAutoformatSeparator=Parameter::getGlobalParameter('versionNameAutoformatSeparator');
  ?>
<table>
	<tr>
		<td>
			<form dojoType="dijit.form.Form" id='copyForm' name='copyForm'
				onSubmit="return false;">
				<input id="copyClass" name="copyClass" type="hidden" value="<?php echo $objectClass;?>" /> <input id="copyToClass" name="copyToClass" type="hidden" value="<?php echo $objectClass;?>" />
				<input id="copyId" name="copyId" type="hidden" value="<?php echo $objectId;?>" /> <input id="copySourceName" name="copySourceName" type="hidden" value="<?php echo $source->name;?>" /> <input id="copySourceNameSeparator" name="copySourceNameSeparator"type="hidden" value="<?php echo $paramNameAutoformatSeparator;?>" />
				<input id="moveAfterCreate" name="moveAfterCreate" type="hidden" value="<?php echo $moveAfterCreate?>" />
				<input id="copyEditorType" name="copyEditorType" type="hidden" value="<?php echo getEditorType();?>" />
				<table>
					<tr>
						<td valign="top" style="width: 50%; padding: 15px 15px 0px 10px;">
							<table>
           <?php if ($paramNameAutoformat=='YES') {?>
           <tr>
									<td class="dialogLabel"><label for="copyToVersionNumber"><?php echo i18n("colVersionNumber") ?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
									</td>
									<td>
										<div id="copyToVersionNumber" name="copyToVersionNumber"
											dojoType="dijit.form.ValidationTextBox" required="required"
											style="width: 400px;" trim="true" maxlength="100" class="input"
											value="<?php echo pq_str_replace('"', '&quot;', $toCopy->versionNumber);?>">
											<script type="dojo/connect" event="onChange">
                    dijit.byId("copyToName").set("value", dojo.byId('copySourceName').value+dojo.byId('copySourceNameSeparator').value+this.value);
                  </script>
										</div>
									</td>
								</tr>
								<tr>
									<td>&nbsp;</td>
									<td>&nbsp;</td>
								</tr>
           <?php }?>
           <tr>
									<td class="dialogLabel"><label for="copyToName"><?php echo i18n("copyToName") ?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
									</td>
									<td>
										<div id="copyToName" name="copyToName"
											dojoType="dijit.form.ValidationTextBox"
											<?php if ($paramNameAutoformat=='YES') { echo "readonly";} else { echo 'required="required"';}?>
											style="width: 400px;" trim="true" maxlength="100" class="input"
											value="<?php echo pq_str_replace('"', '&quot;', $toCopy->name);?>">
										</div>
									</td>
								</tr>
								<tr>
									<td>&nbsp;</td>
									<td>&nbsp;</td>
								</tr>
           <?php  if($objectClass != "CatalogUO"){?>
           <tr>
									<td class="dialogLabel"><label for="copyToType"><?php echo i18n("copyToType") ?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
									</td>
									<td><select dojoType="dijit.form.FilteringSelect"
										<?php echo autoOpenFilteringSelect();?> id="copyToType"
										name="copyToType" required class="input">
                <?php
                $colName='id' . $objectClass . 'Type';
                htmlDrawOptionForReference($colName, $toCopy->$colName, null, true);
                ?>
               </select></td>
								</tr>
								<tr>
									<td>&nbsp;</td>
									<td>&nbsp;</td>
								</tr>
           <?php } ?>
           <?php if (property_exists($toCopy, 'description')) {?>
          			 <tr>
									<td class="dialogLabel" colspan="2" style="text-align: left;">
										<label style="text-align: left;padding-bottom: 10px;" for="copyToDescription"><?php echo ucfirst(i18n("colDescription")). ' :' ?><?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
									</td>
								</tr>
								<tr>
									<td colspan="2">
               <?php
                $descriptionValue=pq_str_replace('"', '&quot;', $toCopy->description);
                $descriptionWidth=590;
                $descriptionHeight=120;
                if (getEditorType()=="CK" or getEditorType()=="CKInline") {
              ?>
                 <textarea style="width:<?php echo $descriptionWidth; ?>px; height:<?php echo $descriptionHeight; ?>px" tabindex="1"
                   name="copyToDescription" id="copyToDescription" ><?php echo $descriptionValue;?></textarea>
               <?php } else if (getEditorType() == "text") {?>
                 <textarea dojoType="dijit.form.Textarea"
                   id="copyToDescription" name="copyToDescription"
                   style="max-width:<?php echo $descriptionWidth;?>px;height:<?php echo $descriptionHeight;?>px;max-height:<?php echo $descriptionHeight;?>px"
                   maxlength="4000"
                   class="input" ><?php echo $descriptionValue;?></textarea>
               <?php } else { ?>
                 <textarea dojoType="dijit.form.Textarea" type="hidden"
											id="copyToDescription" name="copyToDescription"
											style="display: none;"><?php echo $descriptionValue;?></textarea>
										<div data-dojo-type="dijit.Editor" id="copyDescriptionEditor"
                   data-dojo-props="onChange:function(){window.top.dojo.byId('copyToDescription').value=arguments[0];}
                     ,plugins:['removeFormat','bold','italic','underline','|', 'indent', 'outdent', 'justifyLeft', 'justifyCenter', 
                               'justifyRight', 'justifyFull','|','insertOrderedList','insertUnorderedList','|']
                     ,extraPlugins:['dijit._editor.plugins.AlwaysShowToolbar','foreColor','hiliteColor']"
                   style="color:#606060 !important; background:none;padding:3px 0px 3px 3px;margin-right:2px;width:<?php echo $descriptionWidth;?>px;overflow:auto;"
                   class="input" >
                   <?php echo $descriptionValue;?>
                 </div>
               <?php } ?>
             </td>
								</tr>
           <?php }?>
							</table>
						</td>
						<td valign="top"
							style="width: 50%; border-left: 1px solid #d0d0d0; padding: 0px 0px 25px 15px;">
							<table>
								<tr>
									<td>&nbsp;</td>
									<td>&nbsp;</td>
								</tr>
           <?php $paramTypeOfCopyComponentVersion=Parameter::getGlobalParameter('typeOfCopyComponentVersion');
            if (!$paramTypeOfCopyComponentVersion) {
              $paramTypeOfCopyComponentVersion='free';
            }
            ?>
								<tr>
									<td style="vertical-align: top; padding-bottom: 20px;">
										<div class="dialogLabel" style="margin-bottom: 10px;">
                        <?php echo i18n("copyToCopyVersionStructure"); ?>
                    </div>
										<table>
											<tr>
												<td><input type="radio" data-dojo-type="dijit/form/RadioButton"
													<?php if($paramTypeOfCopyComponentVersion == 'A'){ echo 'checked'; } if($paramTypeOfCopyComponentVersion != 'free' and $paramTypeOfCopyComponentVersion != 'A'){ echo' disabled'; }?>
													name="copyToCopyVersionStructure"
													id="copyToCopyVersionStructureCopy" value="Copy" />&nbsp; </td>
												<td><?php echo i18n("copyToCopyVersionStructureCopy"); ?></td>
											</tr>

											<tr>
												<td><input type="radio" data-dojo-type="dijit/form/RadioButton"
													<?php if($paramTypeOfCopyComponentVersion == 'B' or $paramTypeOfCopyComponentVersion == 'free') { echo 'checked'; } if($paramTypeOfCopyComponentVersion != 'free' and $paramTypeOfCopyComponentVersion != 'B'){ echo' disabled'; }?>
													name="copyToCopyVersionStructure"
													id="copyToCopyVersionStructureNoCopy" value="NoCopy" />&nbsp;</td>
												<td><?php echo i18n("copyToCopyVersionStructureNoCopy"); ?></td>
											</tr>

											<tr>
												<td><input type="radio" data-dojo-type="dijit/form/RadioButton"
													<?php if($paramTypeOfCopyComponentVersion == 'C'){ echo 'checked'; } if($paramTypeOfCopyComponentVersion != 'free' and $paramTypeOfCopyComponentVersion != 'C'){ echo' disabled'; }?>
													name="copyToCopyVersionStructure"
													id="copyToCopyVersionStructureReplace" value="Replace" />&nbsp;</td>
												<td><?php echo i18n("copyToCopyVersionStructureReplace"); ?></td>
											</tr>
										</table>
									</td>
									<td style="text-align: center; vertical-align: top;">
									<img src="../view/img/helpCopyVersion.png" style="width:60px; transition:0.2s ease; cursor:pointer;"onmouseenter="this.style.width='300px';" onmouseout="this.style.width='120px';"  />
									</td>
								</tr>

								<?php if(property_exists($objectClass, 'idStatus')){ ?> 
           <tr>
									<td class="dialogLabel" colspan="2"
										style="width: 100%; text-align: left;"><label
										for="copyToWithStatus" style="width: 90%; text-align: right;"><?php echo i18n("CopyWithStatus", array($status->name));?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
                <?php
                $isCheckedWithStatus=true;
                $isCheckedWithStatus=(Parameter::getUserParameter('isCheckedWithStatus' . $objectClass . $copyToClassId))?Parameter::getUserParameter('isCheckedWithStatus' . $objectClass . $copyToClassId):Parameter::getUserParameter('isCheckedWithStatus' . $objectClass);
                if ($isCheckedWithStatus!='false') $isCheckedWithStatus=true;
                ?>
               <div id="copyToWithStatus" name="copyToWithStatus"
										dojoType="dijit.form.CheckBox"
										<?php if ($isCheckedWithStatus=='true') echo " checked ";?>
										type="checkbox">
										<script type="dojo/method" event="onChange">
                  var type=dijit.byId('copyToClass').get('value');
                  saveDataToSession('isCheckedWithStatus<?php echo $objectClass;?>'+type,((this.checked)?true:false),true);
                  saveDataToSession('isCheckedWithStatus<?php echo $objectClass;?>',((this.checked)?true:false),true);
               </script>
									</div></td>
								</tr>   
         <?php }?> 
							</table>
						</td>
					</tr>
					<tr>
						<td colspan="2">&nbsp;</td>
					</tr>
				</table>
			</form>
		</td>
	</tr>
	<tr>
		<td align="center"><input type="hidden" id="copyAction">
			<button class="mediumTextButton" dojoType="dijit.form.Button"
				type="button" onclick="dijit.byId('dialogCopy').hide();">
          <?php echo i18n("buttonCancel");?>
        </button>
			<button class="mediumTextButton" dojoType="dijit.form.Button"
				type="submit" id="dialogCopySubmit"
				onclick="protectDblClick(this);copyObjectToSubmit();return false;">
          <?php echo i18n("buttonOK");?>
        </button></td>
	</tr>
</table>
<?php
}
?>
