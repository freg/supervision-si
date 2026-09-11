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
$objectClass=RequestHandler::getClass('objectClass');
if($objectClass == 'TicketSimple'){
	$objectClass = 'Ticket';
}
$objectId = intval(RequestHandler::getId('objectId'));
$extractMode = 'Element';
if($objectClass == 'Project')$extractMode='Project';
if($objectClass == 'DocumentDirectory')$extractMode='Directory';

$extractSubDir = getSessionValue('extractSubDirectory');
$extractSubProj = getSessionValue('extractSubProjectDirectory');
$extractProjElement = getSessionValue('extractProjectElementDirectory');
$extractAttach = getSessionValue('extractAttachment');
$extractVersion = getSessionValue('extractVersion');
$extractIdVersion = (getSessionValue('extractIdVersion'))?getSessionValue('extractIdVersion'):'idDocumentVersion';

$preserveUploadedFileName = (getSessionValue('preserveUploadedFileName'))?getSessionValue('preserveUploadedFileName'):Parameter::getGlobalParameter('preserveUploadedFileName');

$obj = new $objectClass($objectId);

?>
<form dojoType="dijit.form.Form" id='documentExtractionForm' name='documentExtractionForm' onSubmit="return false;">
  <input type="hidden" id="objectClass" name="objectClass" value="<?php echo $objectClass;?>"/>
  <input type="hidden" id="objectId" name="objectId" value="<?php echo $objectId;?>"/>
  <input type="hidden" id="extractDocumentMode" name="extractDocumentMode" value="<?php echo $extractMode;?>"/>
  <table style="width:100%">
    <tr>
      <td align="center">
        <div class="icon<?php echo $objectClass;?> iconSize22 imageColorNewGui"></div>
        <div><?php echo i18n($objectClass).' #'.$objectId.' '.$obj->name;?></div>
      </td>
    </tr>
    <tr><td><br></td></tr>
    <tr>
      <td style="text-align: left; vertical-align: middle;width:485px; word-wrap: none;white-space:nowrap">
        <table>
        <?php if($extractMode == 'Directory'){?>
          <tr>
            <td style="vertical-align:top;">
              <label style="width:300px;text-align:right;margin-top:-2px"for="preserveUploadedFileName"><?php echo i18n('extractDocumentName')?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
            </td>
            <td>
              <table>
                  <tr>
                    <td>
            	       <input type="radio" data-dojo-type="dijit/form/RadioButton" name="preserveUploadedFileName" <?php if($preserveUploadedFileName=='YES'){echo 'checked';}?>
                      id="extractRealName" value="YES" onClick="saveDataToSession('preserveUploadedFileName',this.value,false);" />
                    </td>
                    <td>
                    <label class="display" style="text-align:left;padding:0px 0px 2px 5px;" for="extractRealName"><?php echo i18n("extractRealName")?></label>
                    </td>
                  </tr>
                  <tr>
                    <td>
          	       <input type="radio" data-dojo-type="dijit/form/RadioButton" name="preserveUploadedFileName" <?php if($preserveUploadedFileName=='NO'){echo 'checked';}?>
                      id="extractFormattedName" value="NO" onClick="saveDataToSession('preserveUploadedFileName',this.value,false);" />
                    </td>
                    <td>
                    <label class="display" style="text-align:left;padding:0px 0px 2px 5px;" for="extractFormattedName"><?php echo i18n("extractFormattedName")?></label>
                    </td>
                  </tr>
                </table>
              </td>
          </tr>
          <tr><td><br></td></tr>
          <tr>
            <td style="vertical-align:top;">
              <label style="width:300px;text-align:right;margin-top:-2px"for="extractVersion"><?php echo i18n('extractVersion')?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
            </td>
            <td>
              <table>
                <tr>
                  <td>
          	       <input type="radio" data-dojo-type="dijit/form/RadioButton" name="extractIdVersion" <?php if($extractIdVersion=='idDocumentVersion'){echo 'checked';}?>
                    id="extractVersionLast" value="idDocumentVersion" onClick="saveDataToSession('extractIdVersion',this.value,false);" />
                  </td>
                  <td>
                  <label class="display" style="text-align:left;padding:0px 0px 2px 5px;" for="extractVersionLast"><?php echo i18n("extractVersionLast")?></label>
                  </td>
                </tr>
                <tr>
                  <td>
        	       <input type="radio" data-dojo-type="dijit/form/RadioButton" name="extractIdVersion" <?php if($extractIdVersion=='idDocumentVersionRef'){echo 'checked';}?>
                    id="extractVersionRef" value="idDocumentVersionRef" onClick="saveDataToSession('extractIdVersion',this.value,false);"  />
                  </td>
                  <td>
                  <label class="display" style="text-align:left;padding:0px 0px 2px 5px;" for="extractVersionRef"><?php echo i18n("extractVersionRef")?></label>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
          <tr>
            <td>
              <label style="width:300px;text-align:right;" for="extractSubDirectory"><?php echo i18n('extractSubDirectory')?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
            </td>
            <td>
              <div id="extractSubDirectory" name="extractSubDirectory" dojoType="dijit.form.CheckBox" type="checkbox"
                <?php if ($extractSubDir) echo ' checked ';?>
                onChange="saveDataToSession('extractSubDirectory',this.checked,false);" 
                ></div>
            </td>
          </tr>
        <?php }else if($extractMode == 'Project'){?>     
          <tr>
            <td style="vertical-align:top;">
              <label style="width:300px;text-align:right;" for="extractVersion"><?php echo i18n('extractProjectDocuments')?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
            </td>
            <td>
              <div id="extractVersion" name="extractVersion" dojoType="dijit.form.CheckBox" type="checkbox" checked
               onChange="saveDataToSession('extractVersion',this.checked,false);" ></div>
            </td>
          <tr>                        
          <tr>
            <td style="vertical-align:top;">
              <label style="width:300px;text-align:right;margin-top:-2px" ><?php echo i18n('extractDocumentName')?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
            </td>
            <td>
              <table>
                <tr>
                  <td>
            	       <input type="radio" data-dojo-type="dijit/form/RadioButton" name="preserveUploadedFileName" <?php if($preserveUploadedFileName=='YES'){echo 'checked';}?>
                      id="extractRealName" value="YES" onClick="saveDataToSession('preserveUploadedFileName',this.value,false);" />
                  </td>
                  <td>
                    <label class="display" style="text-align:left;padding:0px 0px 2px 5px;" for="extractRealName"><?php echo i18n("extractRealName")?></label>
                  </td>
                </tr>
                <tr>
                  <td>
          	       <input type="radio" data-dojo-type="dijit/form/RadioButton" name="preserveUploadedFileName" <?php if($preserveUploadedFileName=='NO'){echo 'checked';}?>
                      id="extractFormattedName" value="NO" onClick="saveDataToSession('preserveUploadedFileName',this.value,false);" />
                  </td>
                  <td>
                    <label class="display" style="text-align:left;padding:0px 0px 2px 5px;" for="extractFormattedName"><?php echo i18n("extractFormattedName")?></label>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
          <tr>
            <td style="vertical-align:top;">
              <label style="width:300px;text-align:right;margin-top:-2px" ><?php echo i18n('extractVersion')?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
            </td>
            <td>
              <table>
                <tr>
                  <td>
                    <table>
                      <tr>
                        <td>
                	       <input type="radio" data-dojo-type="dijit/form/RadioButton" name="extractIdVersion" <?php if($extractIdVersion=='idDocumentVersion'){echo 'checked';}?>
                          id="extractVersionLast" value="idDocumentVersion" onClick="saveDataToSession('extractIdVersion',this.value,false);" />
                        </td>
                        <td>
                        <label class="display" style="text-align:left;padding:0px 0px 2px 5px;" for="extractVersionLast"><?php echo i18n("extractVersionLast")?></label>
                        </td>
                      </tr>
                      <tr>
                        <td>
              	       <input type="radio" data-dojo-type="dijit/form/RadioButton" name="extractIdVersion" <?php if($extractIdVersion=='idDocumentVersionRef'){echo 'checked';}?>
                          id="extractVersionRef" value="idDocumentVersionRef" onClick="saveDataToSession('extractIdVersion',this.value,false);" />
                        </td>
                        <td>
                        <label class="display" style="text-align:left;padding:0px 0px 2px 5px;" for="extractVersionRef"><?php echo i18n("extractVersionRef")?></label>
                        </td>
                      </tr>
                    </table>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
          <tr><td><br></td></tr>
          <tr>
            <td>
              <label style="width:300px;text-align:right;" for="extractSubProjectDirectory"><?php echo i18n('extractSubProjectDirectory')?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
            </td>
            <td>
              <div id="extractSubProjectDirectory" name="extractSubProjectDirectory" dojoType="dijit.form.CheckBox" type="checkbox"
              <?php if ($extractSubProj) echo ' checked ';?> 
                onChange="saveDataToSession('extractSubProjectDirectory',this.checked,false);" 
                ></div>
            </td>
          </tr>
          <tr><td><br></td></tr>
          <tr>
            <td>
              <label style="width:300px;text-align:right;" for="extractProjectElementDirectory"><?php echo i18n('extractProjectElementDirectory')?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
            </td>
            <td>
              <div id="extractProjectElementDirectory" name="extractProjectElementDirectory" dojoType="dijit.form.CheckBox" type="checkbox"
              <?php if ($extractProjElement) echo ' checked ';?> 
                onChange="saveDataToSession('extractProjectElementDirectory',this.checked,false);" 
                ></div>
            </td>
          </tr>
          <?php if(property_exists($objectClass, '_Attachment')){?>
          <tr><td><br></td></tr>
          <tr>
            <td>
              <label style="width:300px;text-align:right;" for="extractAttachment"><?php echo i18n('extractAttachments')?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
            </td>
            <td>
              <div id="extractAttachment" name="extractAttachment" dojoType="dijit.form.CheckBox" type="checkbox"
              <?php if ($extractAttach) echo ' checked ';?> 
                onChange="saveDataToSession('extractAttachment',this.checked,false);" 
                ></div>
            </td>
          </tr>
          <?php }?>
        <?php }else{?>
          <tr>
            <td style="vertical-align:top;">
              <label style="width:300px;text-align:right;" for="extractVersion"><?php echo i18n('extractLinkedDocuments')?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
            </td>
            <td>
              <div id="extractVersion" name="extractVersion" dojoType="dijit.form.CheckBox" type="checkbox" checked
               onChange="saveDataToSession('extractVersion',this.checked,false);" ></div>
            </td>
          <tr>  
          <tr>
            <td style="vertical-align:top;">
              <label style="width:300px;text-align:right;margin-top:-2px"for="preserveUploadedFileName"><?php echo i18n('extractDocumentName')?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
            </td>
            <td>
              <table>
                  <tr>
                    <td>
            	       <input type="radio" data-dojo-type="dijit/form/RadioButton" name="preserveUploadedFileName" <?php if($preserveUploadedFileName=='YES'){echo 'checked';}?>
                      id="extractRealName" value="YES" onClick="saveDataToSession('preserveUploadedFileName',this.value,false);" />
                    </td>
                    <td>
                    <label class="display" style="text-align:left;padding:0px 0px 2px 5px;" for="extractRealName"><?php echo i18n("extractRealName")?></label>
                    </td>
                  </tr>
                  <tr>
                    <td>
          	       <input type="radio" data-dojo-type="dijit/form/RadioButton" name="preserveUploadedFileName" <?php if($preserveUploadedFileName=='NO'){echo 'checked';}?>
                      id="extractFormattedName" value="NO" onClick="saveDataToSession('preserveUploadedFileName',this.value,false);" />
                    </td>
                    <td>
                    <label class="display" style="text-align:left;padding:0px 0px 2px 5px;" for="extractFormattedName"><?php echo i18n("extractFormattedName")?></label>
                    </td>
                  </tr>
                </table>
              </td>
          </tr>
          <tr>
            <td style="vertical-align:top;">
              <label style="width:300px;text-align:right;margin-top:-2px" ><?php echo i18n('extractVersion')?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
            </td>
            <td>
                    <table>
                      <tr>
                        <td>
                	       <input type="radio" data-dojo-type="dijit/form/RadioButton" name="extractIdVersion" <?php if($extractIdVersion=='idDocumentVersion'){echo 'checked';}?>
                          id="extractVersionLast" value="idDocumentVersion" onClick="saveDataToSession('extractIdVersion',this.value,false);" />
                        </td>
                        <td>
                        <label class="display" style="text-align:left;padding:0px 0px 2px 5px;" for="extractVersionLast"><?php echo i18n("extractVersionLast")?></label>
                        </td>
                      </tr>
                      <tr>
                        <td>
              	       <input type="radio" data-dojo-type="dijit/form/RadioButton" name="extractIdVersion" <?php if($extractIdVersion=='idDocumentVersionRef'){echo 'checked';}?>
                          id="extractVersionRef" value="idDocumentVersionRef" onClick="saveDataToSession('extractIdVersion',this.value,false);" />
                        </td>
                        <td>
                        <label class="display" style="text-align:left;padding:0px 0px 2px 5px;" for="extractVersionRef"><?php echo i18n("extractVersionRef")?></label>
                        </td>
                      </tr>
                    </table>
            </td>
          </tr>
          <?php if(property_exists($objectClass, '_Attachment')){?>
          <tr><td><br></td></tr>
          <tr>
            <td>
              <label style="width:300px;text-align:right;" for="extractAttachment"><?php echo i18n('extractAttachments')?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
            </td>
            <td>
              <div id="extractAttachment" name="extractAttachment" dojoType="dijit.form.CheckBox" type="checkbox" 
              <?php if ($extractAttach) echo ' checked ';?>
                onChange="saveDataToSession('extractAttachment',this.checked,false);" 
                ></div>
            </td>
          </tr>
          <?php }?>
        <?php }?>
        </table>
      </td>
    </tr>
    <tr style="border-bottom:2px solid #F0F0F0;"><td></td><td>&nbsp;</td></tr>
    <tr style="height:10px;"><td></td><td>&nbsp;</td></tr>
  </table>
  <table style="width:100%">
    <tr>
      <td align="center">
        <button dojoType="dijit.form.Button" type="button" onclick="dijit.byId('dialogDocumentExtraction').hide();">
          <?php echo i18n("buttonCancel");?>
        </button>
        <button dojoType="dijit.form.Button" type="submit" id="dialogDocumentExtractionSubmit" onclick="protectDblClick(this);submitDocumentExtraction();return false;">
          <?php echo i18n("buttonOK");?>
        </button>
      </td>
    </tr>
  </table>
</form>