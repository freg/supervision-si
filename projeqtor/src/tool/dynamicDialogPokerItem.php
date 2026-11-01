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
$class=RequestHandler::getClass('objectClass');
$id=RequestHandler::getId('objectId');
$mode = RequestHandler::getValue('mode');

if ($class and $id) {
	$obj=new $class($id);
} else {
  $obj=null;
}
if($mode =='edit'){
  $idPokerItem = RequestHandler::getId('pokerItemId');
  $item = new PokerItem($idPokerItem);
}
?>
<table>
    <tr>
      <td>
       <form id='pokerItemForm' name='pokerItemForm' onSubmit="return false;">
         <input id="pokerItemFixedClass" name="pokerItemFixedClass" type="hidden" value="" />
         <input id="pokerItemId" name="pokerItemId" type="hidden" value="" />
         <input id="pokerItemRef1Type" name="pokerItemRef1Type" type="hidden" value="" />
         <input id="pokerItemRef1Id" name="pokerItemRef1Id" type="hidden" value="" />
         <input id="mode" name="mode" type="hidden" value="<?php echo $mode;?>" />
         <input id="idPokerSession" name="idPokerSession" type="hidden" value="<?php echo $id;?>" />
         <?php if($mode =='edit'){ ?>
         <input id="idPokerItem" name="idPokerItem" type="hidden" value="<?php echo $idPokerItem;?>" />
         <?php } ?>
         <table>
           <tr>
             <td class="dialogLabel"  >
               <label for="pokerItemRef2Type" ><?php echo i18n("pokerItemType") ?>&nbsp;<?php echo (isNewGui())?'':':';?>&nbsp;</label>
             </td>
             <td>
             <?php if($mode!='edit'){?>
               <select dojoType="dijit.form.FilteringSelect" id="pokerItemRef2Type" name="pokerItemRef2Type" onchange="refreshPokerItemList();" 
               <?php if (isNewGui()) {?>  style="width:388px" <?php }?> 
               <?php echo autoOpenFilteringSelect();?>
                class="input" value="Ticket">
                <option value='Ticket'><?php echo htmlEncode(i18n('Ticket'));?></option>
                <option value='Activity'><?php echo htmlEncode(i18n('Activity'));?></option>
                <option value='Requirement'><?php echo htmlEncode(i18n('Requirement'));?></option>
                <option value='UserStory'><?php echo htmlEncode(i18n('UserStory'));?></option>
               </select>
               <?php }else{?>
               <textarea dojoType="dijit.form.Textarea"
                             id="pokerItemRef2Type" name="pokerItemRef2Type" readOnly
                             style="width: 400px;" value="<?php echo $item->refType;?>"
                             maxlength="4000"
                             class="input"></textarea>
               <?php }?>
             </td>
           </tr>
           <tr><td>&nbsp;</td><td>&nbsp;</td></tr>
           <tr>
             <td class="dialogLabel" >
               <label for="pokerItemRef2Id" ><?php echo i18n("pokerItemElement") ?>&nbsp;<?php echo (isNewGui())?'':':';?>&nbsp;</label>
             </td>
             <td>
             
               <table><tr><td>
               <div id="dialogPokerItemList" dojoType="dijit.layout.ContentPane" region="center">
                <?php if($mode!='edit'){?>
                 <input id="pokerItemRef2Id" name="pokerItemRef2Id" type="hidden" value="" />
                 <?php }else{?>
                 <textarea dojoType="dijit.form.Textarea"
                             id="pokerItemRef2Id" name="pokerItemRef2Id" readOnly
                             style="width: 400px;" value="<?php echo '#'.$item->refId.' '.SqlList::getNameFromId($item->refType, $item->refId);?>"
                             maxlength="4000"
                             class="input"></textarea>
                   <?php }?>
               </div>
               </td><td style="vertical-align: top;<?php if($mode=='edit'){?>display:none;<?php }?>">
               <button id="pokerItemDetailButton" dojoType="dijit.form.Button" showlabel="false"
                 title="<?php echo i18n('showDetail')?>" class="notButton notButtonRounded"
                 iconClass="iconSearch22 iconSearch iconSize22 imageColorNewGui">
                 <script type="dojo/connect" event="onClick" args="evt">
                    showDetailPokerItem();
                 </script>
               </button>
               </td></tr></table>
             </td>
           </tr>
            <tr><td>&nbsp;</td><td>&nbsp;</td></tr>
           </table>
         <table>
         <?php if($mode!='edit'){?>
            <tr>
               <td class="dialogLabel" >
                   <label for="pokerItemName" ><?php echo i18n("colName") ?>&nbsp;<?php echo (isNewGui())?'':':';?>&nbsp;</label>
               </td>
               <td>
                   <textarea dojoType="dijit.form.Textarea"
                             id="pokerItemName" name="pokerItemName"
                             style="width: 400px;"
                             maxlength="4000"
                             class="input"></textarea>
               </td>
           </tr> 
           <?php }?> 
           <tr>
               <td class="dialogLabel" >
                   <label for="pokerItemRef2Type" ><?php echo i18n("colComment") ?>&nbsp;<?php echo (isNewGui())?'':':';?>&nbsp;</label>
               </td>
               <td>
                   <textarea dojoType="dijit.form.Textarea"
                             id="pokerItemComment" name="pokerItemComment"
                             style="width: 400px;"
                             maxlength="4000"
                             class="input"></textarea>
               </td>
           </tr>
           <tr><td>&nbsp;</td><td>&nbsp;</td></tr>
   
            <td class="dialogLabel"  >
               
             </td>     
          <tr><td>&nbsp;</td><td>&nbsp;</td></tr>
         </table>         
        </form>
      </td>
    </tr>
    <tr>
      <td align="center">
        <input type="hidden" id="dialogPokerItemAction">
        <button class="mediumTextButton" dojoType="dijit.form.Button" type="button" onclick="dijit.byId('dialogPokerItem').hide();">
          <?php echo i18n("buttonCancel");?>
        </button>
        <button class="mediumTextButton" dojoType="dijit.form.Button" type="submit" id="dialogPokerItemSubmit" onclick="protectDblClick(this);savePokerItem();return false;">
          <?php echo i18n("buttonOK");?>
        </button>
      </td>
    </tr>
  </table>
