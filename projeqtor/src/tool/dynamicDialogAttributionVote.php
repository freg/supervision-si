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
$mode = RequestHandler::getValue('mode',false,null);
$id = RequestHandler::getId('idAttributionVote');
$class = RequestHandler::getClass('class');
$idResource = RequestHandler::getId('idResource');
if($mode == 'edit'){
  $attrVote = new VotingAttribution($id);
}
$proj = null;
$detailHeight=50;
$detailWidth=800;
?>
<div>
  <table style="width:100%;">
    <tr>
      <td>
       <form dojoType="dijit.form.Form" id='attributionVoteForm' name='attributionVoteForm' onSubmit="return false;">
        <input id="mode" name="mode" type="hidden" value="<?php echo $mode;?>" />
        <input id="classObj" name="classObj" type="hidden" value="<?php echo $class;?>" />
        <input id="idResource" name="idResource" type="hidden" value="<?php echo $idResource;?>" />
        <input id="idAttributionVote" name="idAttributionVote" type="hidden" value="<?php echo $id;?>" />
         <table style="width:1000px;">
         <tr><td>&nbsp;</td><td>&nbsp;</td></tr>
          <tr>
             <td class="dialogLabel" style="float:right !important;white-space:nowrap;width:205px;" >
               <label for="attributionVoteRule" ><?php echo i18n("VotingAttributionRule") ?> &nbsp;</label>
             </td>
             <td>
               <select dojoType="dijit.form.FilteringSelect" 
               <?php echo autoOpenFilteringSelect();?>
                id="attributionVoteRule" name="attributionVoteRule"  style="border-left:3px solid red !important;" data-dojo-props="queryExpr: '*${0}*',autoComplete:false"
                value="<?php if($mode=='edit') echo $attrVote->idVotingAttributionRule; ?>" class="input"  onChange="setAttributionVoteElement();">
                 <?php  htmlDrawOptionForReference('idVotingAttributionRule',null,null,true);?>
               </select>
             </td>
           </tr>
          <tr>
             <td class="dialogLabel" style="float:right !important;" >
               <label for="attributionVoteElement" ><?php echo i18n("colElement"); ?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
             </td>
             <td>
               <select dojoType="dijit.form.FilteringSelect" 
               <?php echo autoOpenFilteringSelect();?>
                id="attributionVoteElement" name="attributionVoteElement"  data-dojo-props="queryExpr: '*${0}*',autoComplete:false"
                value="<?php if($mode=='edit') echo $attrVote->refType; ?>" class="input"  <?php echo 'readonly';?>>
                <option value=" " ></option>
                <?php $vote = new VotingItem();
                       $lstClass = $vote->getVotableClassList();
                       foreach ($lstClass as $value){?>
                <option value="<?php echo $value; ?>"
                  <span ><?php echo htmlEncode(i18n($value));?></span>
                </option>
                <?php } ?>
               </select>
             </td>
           </tr>
         
          <tr>
             <td class="dialogLabel" style="float:right !important;">
               <label for="attributionVoteProject" ><?php echo i18n("colIdProject") ?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
             </td>
             <td>
               <select dojoType="dijit.form.FilteringSelect" 
               <?php echo autoOpenFilteringSelect();?>
                id="attributionVoteProject" name="attributionVoteProject"  data-dojo-props="queryExpr: '*${0}*',autoComplete:false"
                value="<?php if($mode=='edit' and $attrVote->idProject){ echo $attrVote->idProject;}else{ echo " ";} ?>" class="input" >
                 <?php  htmlDrawOptionForReference('idProject', null,null,false);?>
               </select>
             </td>
           </tr>
           
           <tr>
             <td class="dialogLabel"  style="float:right !important;">
               <label for="attributionVoteTotal" ><?php echo i18n("colCountTotal");?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
             </td>
             <td>
               <div id="attributionVoteTotal" name="attributionVoteTotal" value="<?php if($mode=='edit')echo $attrVote->totalValue; ?>" 
                 dojoType="dijit.form.NumberTextBox"  constraints="{min:0,max:99999,places:0}"
                 style="width:100px" class="input" onChange=""
                 hasDownArrow="true">
               <?php echo $keyDownEventScript;?>
               </div>
             </td>    
           </tr>
     <?php // if($id){?>
           <tr>
             <td class="dialogLabel"  style="float:right !important;">
               <label for="attributionVoteUsed" ><?php echo i18n("used");?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
             </td>
             <td>
               <div id="attributionVoteUsed" name="attributionVoteUsed" value="<?php if($mode=='edit')echo $attrVote->usedValue; ?>" 
                 dojoType="dijit.form.NumberTextBox"  constraints="{min:0,max:99999,places:0}"
                 style="width:100px" class="input" <?php echo 'readonly';?>
                 hasDownArrow="true"> 
               <?php echo $keyDownEventScript;?>
               </div>
             </td>    
            </tr>
            <tr>
             <td class="dialogLabel" style="float:right !important;" >
               <label for="attributionVoteLeft" ><?php echo i18n("colLeft");?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
             </td>
             <td>
               <div id="attributionVoteLeft" name="attributionVoteLeft" value="<?php if($mode=='edit')echo $attrVote->leftValue; ?>" 
                 dojoType="dijit.form.NumberTextBox"  constraints="{min:0,max:99999,places:0}"
                 style="width:100px" class="input" <?php echo 'readonly';?>
                 hasDownArrow="true">
               <?php echo $keyDownEventScript;?>
               </div>
             </td>    
           </tr>
           <tr>
             <td class="dialogLabel" style="float:right !important;white-space:nowrap;width:190px;" >
               <label for="attributionVoteDate" ><?php echo i18n("lastAttributionDate");?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
             </td>
             <td>
             <input id="attributionVoteDate" name="attributionVoteDate" value="<?php if($mode=='edit')echo $attrVote->lastAttributionDate; ?>"  
               dojoType="dijit.form.DateTextBox"  <?php echo 'readonly';?> hasDownArrow="false"
               constraints="{datePattern:browserLocaleDateFormatJs}"
               style="width:100px" />
             </td>
           </tr>
           <?php // } ?>
            </td>
            </tr>
            <tr>
             <td class="dialogLabel" style="float:right !important;white-space:nowrap;width:190px;" >
               <label for="endAttributionDate" ><?php echo i18n("endDate");?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
             </td>
             <td>
             <input id="endAttributionDate" name="endAttributionDate" value="<?php if($mode=='edit')echo $attrVote->endAttributionDate; ?>"  
               dojoType="dijit.form.DateTextBox"  hasDownArrow="false"
               constraints="{datePattern:browserLocaleDateFormatJs}"
               style="width:100px" />
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
        <button class="mediumTextButton" dojoType="dijit.form.Button" type="button" onclick="dijit.byId('dialogAttributionVote').hide();">
          <?php echo i18n("buttonCancel");?>
        </button>
        <button class="mediumTextButton" dojoType="dijit.form.Button" type="submit" id="dialogAttributionVoteSubmit" onclick="protectDblClick(this);saveAttributionVote();return false;">
          <?php echo i18n("buttonOK");?>
        </button>
      </td>
    </tr>
    <tr><td>&nbsp;</td><td>&nbsp;</td></tr>
  </table>
