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

scriptLog('dynamicDialogAttachment.php');
$isIE=false;
if (pq_array_key_exists('isIE',$_REQUEST)) {
	$isIE=$_REQUEST['isIE'];
} 
$mode = RequestHandler::getValue('mode');
$id = RequestHandler::getId('id');
$att = new Attachment($id);
$privacy = $att->idPrivacy;
$type = $att->type;
?>

<table>
    <tr>
      <td>
      <form id='attachmentFormEdit' name='attachmentFormEdit' onSubmit="return false;">
        <input id="mode" name="mode" type="hidden" value="<?php echo $mode;?>" />
        <input id="idAttachment" name="idAttachment" type="hidden" value="<?php echo $id;?>" />
    <?php  if($type=='file'){ ?>
          <table>
            <tr>
              <td class="dialogLabel" style="vertical:align:top">
                <label for="attachmentFileEdit" ><?php echo i18n("colFile");?>&nbsp;<?php if (! isNewGui()) echo ':';?>&nbsp;</label>
              </td>
              <td>
                <textarea dojoType="dijit.form.Textarea"
                             id="attachmentFileEdit" name="attachmentFileEdit" readOnly
                             style="width: 350px;" value="<?php echo $att->fileName;?>"
                             maxlength="4000"
                             class="input"></textarea> 
              </td>
            </tr>
          </table>
    <?php   } ?>
    <?php if($type=='link'){?>
      <table>
        <tr height="30px">
          <td class="dialogLabel" >
            <label for="attachmentLinkEdit" ><?php echo i18n("colHyperlink");?>&nbsp;<?php if (!isNewGui()) echo ':';?>&nbsp;</label>
          </td>
          <td>
            <div id="attachmentLinkEdit" name="attachmentLinkEdit" dojoType="dijit.form.ValidationTextBox"
               style="width: <?php echo (isNewGui())?'338':'350';?>px;"
               trim="true" maxlength="400" class="input"
               value="<?php if($mode=='edit')echo $att->link;?>">
            </div>
          </td>
        </tr>
      </table>
    <?php } ?>
    <table>
      <tr>
        <td class="dialogLabel" >
         <label for="attachmentDescriptionEdit" ><?php echo i18n("colDescription");  if (!isNewGui()) echo ':';?>&nbsp;</label>
        </td>
        <td> 
         <textarea dojoType="dijit.form.Textarea" 
          id="attachmentDescriptionEdit" name="attachmentDescriptionEdit"
          style="width: 350px;"
          maxlength="4000"
          class="input"></textarea>   
        </td>
      </tr>
     </table>
      <tr><td colspan="2">
       <table width="100%"><tr height="25px">
            <td width="33%" class="smallTabLabel" >
              <label class="smallTabLabelRight" for="attachmentPrivacyPublicEdit"><?php echo i18n('public');?>&nbsp;</label>
              <input <?php if($mode=='edit' and $privacy==1){?> checked <?php }?> type="radio" data-dojo-type="dijit/form/RadioButton" name="attachmentPrivacyEdit" id="attachmentPrivacyPublicEdit" value="1" />
            </td>
            <td width="34%" class="smallTabLabel" >
             <?php $res=new Resource(getSessionUser()->id);
                    $hasTeam=($res->id and $res->idTeam)?true:false;
              ?>
              <label class="smallTabLabelRight" for="attachmentPrivacyTeamEdit"><?php echo i18n('team');?>&nbsp;</label>
              <input <?php if($mode=='edit' and $privacy==2){?> checked <?php }?>  type="radio" data-dojo-type="dijit/form/RadioButton" name="attachmentPrivacyEdit" id="attachmentPrivacyTeamEdit" <?php if (!$hasTeam) echo ' disabled ';?>value="2" />
            </td>
            <td width="33%" class="smallTabLabel" >
              <label class="smallTabLabelRight" for="attachmentPrivacyPrivateEdit"><?php echo i18n('private');?>&nbsp;</label>
              <input <?php if($mode=='edit' and $privacy==3){?> checked <?php }?>  type="radio" data-dojo-type="dijit/form/RadioButton" name="attachmentPrivacyEdit" id="attachmentPrivacyPrivateEdit" value="3" />
            </td>
          </tr>
      </table>
      </td></tr>
      </form>
      <tr>
      <td align="center">
        <input type="hidden" id="dialogAttachmentEditAction">
        <button class="mediumTextButton" dojoType="dijit.form.Button" type="button" onclick="dijit.byId('dialogAttachmentEdit').hide();">
          <?php echo i18n("buttonCancel");?>
        </button>
        <button class="mediumTextButton" dojoType="dijit.form.Button" type="submit" id="dialogAttachmentEditSubmit" onclick="protectDblClick(this);saveAttachmentEdit();return false;">
          <?php echo i18n("buttonOK");?>
        </button>
      </td>
    </tr>
    </table>
    </td>
    </tr>
  </table>    