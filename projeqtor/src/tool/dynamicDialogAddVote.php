<?php
/*** COPYRIGHT NOTICE *********************************************************
 *
 * Copyright 2009-2016 ProjeQtOr - Pascal BERNARD - support@projeqtor.org
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
include_once ("../tool/projeqtor.php");
$keyDownEventScript=NumberFormatter52::getKeyDownEvent();
$isKanban = RequestHandler::getValue('isKanban');
$mode = RequestHandler::getValue('mode');
$objectId = RequestHandler::getId('idObj');
$objectClass = RequestHandler::getClass('class');
$noteId = RequestHandler::getId('noteId');
$idUseRule = RequestHandler::getId('idRule');
$idUser = getCurrentUserId();
$idVotingAttrUser = null;
$idVotingAttrClient = null;
$idNote = null;
$valueClient = null;
$valueUser = null;
$valueNote = "";
$idClient = null;
$maxPointPerClient = 0;
$maxPointPerUser = 0;
$minPointPerUser = 0;
$minPointPerClient = 0;
$detailHeight=300;
$detailWidth=1010;

if($mode == 'edit'){
 $voting = new Voting();
 $voteSelf = SqlElement::getSingleSqlElementFromCriteria('Voting', array('refType'=>$objectClass,'refId'=>$objectId,'idUser'=>$idUser,'idClient'=>null));
 if($voteSelf->id){
   if($voteSelf->idNote)$idNote =$voteSelf->idNote;
   if($voteSelf->idUser)$valueUser =$voteSelf->value;
 }
 if($idNote){
   $note = new Note($idNote);
   $valueNote = $note->note;
 }
}

if (sessionValueExists('screenWidth') and getSessionValue('screenWidth')) {
  $detailWidth = round(getSessionValue('screenWidth') * 0.60);
}
if (sessionValueExists('screenHeight')) {
  $detailHeight=round(getSessionValue('screenHeight')*0.60);
}
if(!$noteId){
  $note=new Note();
  $note->refType=$objectClass;
  $note->refId=$objectId;
}
$privacy=($note->id)?$note->idPrivacy:1;
$canChangeStatus = true;
$item= new $objectClass($objectId);

//USER
$voteUserId = VotingAttribution::getIdVotingAttribution($objectClass, $objectId,$idUser);
$voteUser = new VotingAttribution($voteUserId);
if($voteUser->id){
  $maxPointPerUser = $voteUser->leftValue;
  $idVotingAttrUser  = $voteUser->id;
}
//CLIENT
$canVoteForClient = false;
$affectable = new Affectable($idUser);
if($affectable->isContact){
  $contact = new Contact($idUser);
  if($contact->idClient){
    $voteClientId = VotingAttribution::getIdVotingAttribution($objectClass, $objectId,$idUser,$contact->idClient);
    $voteAtt = new VotingAttribution($voteClientId);
    if($voteAtt->id){
      if($mode=='edit'){
        $voteClient = SqlElement::getSingleSqlElementFromCriteria('Voting', array('refType'=>$objectClass,'refId'=>$objectId,'idClient'=>$contact->idClient));
        if($voteClient->id){
          if($voteClient->idNote)$idNote =$voteClient->idNote;
          if($voteClient->idClient)$valueClient =$voteClient->value;
        }
      }
      $canVoteForClient=true;
      $maxPointPerClient = $voteAtt->leftValue;
      $idClient = $contact->idClient;
      $idVotingAttrClient = $voteAtt->id;
    }
  }
}

// get maxPointPerUser in VotingUseRule
$maxPoint = null;
$lefPointUser = $maxPointPerUser;
$lefPointClient = $maxPointPerClient;
if($idUseRule){
  $votingUseRule = new VotingUseRule($idUseRule);
  if($votingUseRule->maxPointsPerUser){
    $maxPoint = $votingUseRule->maxPointsPerUser;
    if($maxPointPerUser > $maxPoint) $maxPointPerUser = $maxPoint;
    if($maxPointPerClient > $maxPoint) $maxPointPerClient = $maxPoint;
  }
}
?>
<div style="max-height:600px !important;">
  <table style="width:100%;">
    <tr>
      <td>
       <form dojoType="dijit.form.Form" id='addVoteForm' name='addVoteForm' onSubmit="return false;">
        <input id="mode" name="mode" type="hidden" value="<?php echo $mode;?>" />
        <input id="classObj" name="classObj" type="hidden" value="<?php echo $objectClass;?>" />
        <input id="refId" name="refId" type="hidden" value="<?php echo $objectId;?>" />
        <input id="idClient" name="idClient" type="hidden" value="<?php echo $idClient;?>" />
        <input id="idVotingAttrUser" name="idVotingAttrUser" type="hidden" value="<?php echo $idVotingAttrUser; ?>" />
        <input id="idVotingAttrClient" name="idVotingAttrClient" type="hidden" value="<?php echo $idVotingAttrClient; ?>" />
         <input id="noteEditorType" name="noteEditorType" type="hidden" value="<?php echo getEditorType();?>" />
        <table style="width:1000px;">
          <tr><td colspan="4">&nbsp;</td></tr>
      
      <?php if($isKanban=='true'){?>    
          <tr>
            <td class="label dialogLabel" style="float:right !important;white-space:nowrap;">
              <label for="targetValue" ><?php echo i18n("colTargetValue");?>&nbsp;&nbsp;</label>
            </td>
            <td>
              <div id="targetValue" name="targetValue" value="<?php echo $item->VotingItem->targetValue;?>" 
                 dojoType="dijit.form.NumberTextBox"  
                 style="width:50px" class="input" onChange="" readOnly
                 hasDownArrow="true"> 
               <?php echo $keyDownEventScript;?>
              </div>
            </td>
            <td class="label dialogLabel" style="float:right !important;white-space:nowrap;">
              <label for="pctRate" ><?php echo i18n("colPctRate");?>&nbsp;&nbsp;</label>
            </td>
            <td>
              <div id="pctRate" name="pctRate" value="<?php echo $item->VotingItem->pctRate;?>" 
                 dojoType="dijit.form.NumberTextBox"  
                 style="width:50px" class="input" onChange="" readOnly
                 hasDownArrow="true">
               <?php echo $keyDownEventScript;?>
              </div>
              %
            </td>
          </tr>
          <tr>
          <td class="label dialogLabel" style="float:right !important;white-space:nowrap;">
              <label for="actualValue" ><?php echo i18n("colActualValue");?>&nbsp;&nbsp;</label>
            </td>
            <td>
              <div id="actualValue" name="actualValue" value="<?php echo $item->VotingItem->actualValue;?>" 
                 dojoType="dijit.form.NumberTextBox"  
                 style="width:50px" class="input" onChange="" readOnly
                 hasDownArrow="true"> 
               <?php echo $keyDownEventScript;?>
              </div>
            </td>
             <td colspan="2">&nbsp;</td>
          </tr>
        <?php  } ?>  
          <tr>
            <td class="label dialogLabel" style="float:right !important;white-space:nowrap;">
              <label for="pointsRule" ><?php echo i18n("MaxpointsRule");?>&nbsp;&nbsp;</label>
            </td>
            <td>
              <div id="pointsRule" name="pointsRule" value="<?php echo $maxPoint;?>" 
                 dojoType="dijit.form.NumberTextBox"  
                 style="width:50px" class="input" onChange="" readOnly
                 hasDownArrow="true"> 
               <?php echo $keyDownEventScript;?>
              </div>
            </td>
            <td colspan="2">&nbsp;</td>
          </tr>
          <tr>
          <?php  if($idUseRule){
            if($votingUseRule->isDownVoting){
              $minPointPerUser = -$maxPointPerUser;
            }
          }?>
            <td class="label dialogLabel"  style="float:right !important;">
              <label for="voteSelf" ><?php echo i18n("voteSelf");?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
            </td>
            <td>
              <div id="voteSelf" name="voteSelf" value="<?php echo $valueUser;?>" 
                 dojoType="dijit.form.NumberTextBox"  constraints="{places:0,min:<?php echo $minPointPerUser;?>,max:<?php echo $maxPointPerUser;?>}"
                 style="width:50px;" class="input" onChange="changeVoteSelf(<?php echo $voteUserId;?>, <?php echo $valueUser;?>);"
                 hasDownArrow="true">
               <?php echo $keyDownEventScript;?>
              </div>
            </td>    
            <td class="label dialogLabel"  style="float:right !important;white-space:nowrap;">
              <label for="pointsVote" ><?php echo i18n("pointsLeft");?>&nbsp;&nbsp;</label>
            </td>
            <td style="width:70%">
              <div id="pointsVote" name="pointsVote" value="<?php echo $lefPointUser;?>" 
                 dojoType="dijit.form.NumberTextBox"  
                 style="width:50px" class="input" onChange="" readOnly
                 hasDownArrow="true"> 
               <?php echo $keyDownEventScript;?>
              </div>
            </td>
          </tr>
          <?php  if($canVoteForClient){?>   
          <tr>
            <td class="label dialogLabel"  style="float:right !important;">
              <label for="voteClient" ><?php echo i18n("voteClient");?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
            </td>
            <td>
             <?php  if($idUseRule){
            if($votingUseRule->isDownVoting){
              $minPointPerClient = -$maxPointPerClient;
            }
          }?>
              <div id="voteClient" name="voteClient" value="<?php echo $valueClient;?>" 
                 dojoType="dijit.form.NumberTextBox"  constraints="{places:0,min:<?php echo $minPointPerClient;?>,max:<?php echo $maxPointPerClient;?>}"
                 style="width:50px;" class="input" onChange=""
                 hasDownArrow="true">
               <?php echo $keyDownEventScript;?>
              </div>
            </td>
            <td class="dialogLabel"  style="float:right !important;white-space:nowrap;">
              <label for="pointsVote" ><?php echo i18n("pointsLeft");?>&nbsp;&nbsp;</label>
            </td>
            <td>
              <div id="pointsVoteClient" name="pointsVoteClient" value="<?php echo $lefPointClient;?>" 
                 dojoType="dijit.form.NumberTextBox"  
                 style="width:50px" class="input" onChange="" readOnly
                 hasDownArrow="true"> 
               <?php echo $keyDownEventScript;?>
              </div>
            </td>
                 
          </tr>
          <?php  } ?>   
          <tr ><td colspan="4">&nbsp;</td></tr>
          <tr>
            <td title="<?php echo i18n("hintVoteComment");?>" class="dialogLabel"  style="float:right !important;">
              <label for="voteNote" ><?php echo i18n("colComment");?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
              <div style="text-align:right;font-size:75%;color:#aaaaaa;font-style: italic;padding-right:10px"><?php echo i18n("hintVoteComment");?></div>
            </td>
            <td colspan="3">
              <?php if (getEditorType()=="CK" or getEditorType()=="CKInline") {?> 
              <textarea style="width:<?php echo $detailWidth/3;?>px; height:<?php echo $detailHeight/2;?>px" title="<?php echo i18n("hintVoteComment");?>"
                name="voteNote" id="voteNote"><?php
                  if (!isTextFieldHtmlFormatted($valueNote)) {
            	      echo formatPlainTextForHtmlEditing($valueNote);
                  } else {
            	      echo pq_htmlspecialchars($valueNote);
                  } ?></textarea>
              <?php } else if (getEditorType()=="text"){
          	  if (isTextFieldHtmlFormatted($valueNote)) {
            	  $text=new Html2Text($valueNote);
            	  $val=$text->getText();
              } else {
                $val=pq_str_replace(array("\n",'<br>','<br/>','<br />'),array("","\n","\n","\n"),$valueNote);
              }?>
              <textarea dojoType="dijit.form.Textarea" 
                id="voteNote" name="voteNote"
                style="max-width:<?php echo $detailWidth;?>px;height:<?php echo $detailHeight;?>px;max-height:<?php echo $detailHeight;?>px"
                maxlength="4000"
                class="input"
                onClick="dijit.byId('voteNote').setAttribute('class','');"><?php echo $val;?></textarea>
              <?php } else {?>
              <textarea dojoType="dijit.form.Textarea" type="hidden"
                id="voteNote" name="voteNote"
                style="display:none;"><?php echo pq_htmlspecialchars($valueNote);?></textarea>    
                <div data-dojo-type="dijit.Editor" id="voteNoteEditor"
                  data-dojo-props="onChange:function(){window.top.dojo.byId('voteNote').value=arguments[0];}
                    ,plugins:['removeFormat','bold','italic','underline','|', 'indent', 'outdent', 'justifyLeft', 'justifyCenter', 
                          'justifyRight', 'justifyFull','|','insertOrderedList','insertUnorderedList','|']
                    ,onKeyDown:function(event){window.top.onKeyDownFunction(event,'voteNoteEditor',this);}
                    ,onBlur:function(event){window.top.editorBlur('voteNoteEditor',this);}
                    ,extraPlugins:['dijit._editor.plugins.AlwaysShowToolbar','foreColor','hiliteColor']"
                  style="color:#606060 !important; background:none;padding:3px 0px 3px 3px;margin-right:2px;width:<?php echo $detailWidth;?>px;overflow:auto;"
                  class="input"><?php 
                  if (!isTextFieldHtmlFormatted($valueNote)) {
  			          	echo formatPlainTextForHtmlEditing($valueNote,'single');
  			          } else {
  			          	echo $note->note;
  			          }?>
  			        </div>
            <?php }?>
            <table width="100%" style="display:none"><tr height="25px">
            <td width="33%" class="smallTabLabel" >
              <label class="smallTabLabelRight" for="notePrivacyPublic"><?php echo i18n('public');?>&nbsp;</label>
              <input type="radio" data-dojo-type="dijit/form/RadioButton" name="notePrivacyVote" id="notePrivacyPublicVote" value="1" <?php if ($privacy==1) echo "checked"; if (!$canChangeStatus) echo ' disabled ';?> />
            </td>
            <td width="34%" class="smallTabLabel" >
            <?php $res=new Resource(getSessionUser()->id);
                  $hasTeam=($res->id and $res->idTeam)?true:false;?>
              <label class="smallTabLabelRight" for="notePrivacyTeam"><?php echo i18n('team');?>&nbsp;</label>
              <input type="radio" data-dojo-type="dijit/form/RadioButton" name="notePrivacyVote" id="notePrivacyTeamVote" value="2" <?php if ($privacy==2) echo "checked"; if (!$canChangeStatus or !$hasTeam or ($privacy==1 and isset($subNotePrivacy['1'])) ) echo ' disabled ';?> />
            </td>
            <td width="33%" class="smallTabLabel" >
              <label class="smallTabLabelRight" for="notePrivacyPrivate"><?php echo i18n('private');?>&nbsp;</label>
              <input type="radio" data-dojo-type="dijit/form/RadioButton" name="notePrivacyVote" id="notePrivacyPrivateVote" value="3" <?php if ($privacy==3) echo "checked";if (!$canChangeStatus  or ($privacy==1 and isset($subNotePrivacy['1'])) or ($privacy==2 and isset($subNotePrivacy['2']))) echo ' disabled ';?> />
            </td>
          </tr></table>
          </td>    
         </tr> 
           
           
            </td>
            </tr>
            </table>
        </form>
      </td>
    </tr>
    <tr><td>&nbsp;</td><td>&nbsp;</td></tr>
    <tr>
      <td align="center">
        <input type="hidden" id="attributionVoteAction">
        <button class="mediumTextButton" dojoType="dijit.form.Button" type="button" onclick="dijit.byId('dialogAddVote').hide();">
          <?php echo i18n("buttonCancel");?>
        </button>
        <button class="mediumTextButton" dojoType="dijit.form.Button" type="submit" id="dialogAddVoteSubmit" onclick="protectDblClick(this);saveAddVote(<?php echo $isKanban;?>);return false;">
          <?php echo i18n("buttonOK");?>
        </button>
      </td>
    </tr>
    <tr><td>&nbsp;</td><td>&nbsp;</td></tr>
  </table>
