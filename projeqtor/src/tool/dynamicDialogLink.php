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
$objId = RequestHandler::getId('objId');
if ($class and $id) {
	$obj=new $class($id);
} else {
  $obj=null;
}
$link = new Link();
$storedLinkType = '';
if ($class) {
  $storedLinkType = Parameter::getUserParameter('linkLastClass' . $class);
}
if($mode =='edit'){
  $linlinkId = RequestHandler::getId('linkId');
  $link = new Link($linlinkId);
  $refLinkId="";
  $refLinkType="";
  if($objId==$link->ref1Id){
    $refLinkId=$link->ref2Id;
    $refLinkType=$link->ref2Type;
  }else if($objId == $link->ref2Id){
    $refLinkId = $link->ref1Id;
    $refLinkType=$link->ref1Type;
  }
}

?>
<table>
    <tr>
      <td>
       <form id='linkForm' name='linkForm' onSubmit="return false;">
         <input id="linkFixedClass" name="linkFixedClass" type="hidden" value="" />
         <input id="linkId" name="linkId" type="hidden" value="" />
         <input id="linkRef1Type" name="linkRef1Type" type="hidden" value="" />
         <input id="linkRef1Id" name="linkRef1Id" type="hidden" value="" />
         <input id="mode" name="mode" type="hidden" value="<?php echo $mode;?>" />
         <input id="linkStoredType" name="linkStoredType" type="hidden" value="<?php echo htmlEncode($storedLinkType); ?>" />
         <?php if($mode =='edit'){ ?>
         <input id="idLink" name="idLink" type="hidden" value="<?php echo $linlinkId;?>" />
         <?php } ?>
         <table>
           <tr>
             <td class="dialogLabel"  >
               <label for="linkRef2Type" ><?php echo i18n("linkType") ?>&nbsp;<?php echo (isNewGui())?'':':';?>&nbsp;</label>
             </td>
             <td>
             <?php if($mode!='edit'){?>
							<select dojoType="dijit.form.FilteringSelect" id="linkRef2Type" name="linkRef2Type"
  						 onchange="saveUserParameter('linkLastClass'+dojo.byId('objectClass').value, this.value);refreshLinkList();"
               <?php if (isNewGui()) {?>  style="width:388px" <?php }?> 
               <?php echo autoOpenFilteringSelect();?>
                class="input" value="">
                 <?php htmlDrawOptionForReference('idLinkable',null , $obj, true);?>
               </select>
               <?php }else{?>
               <textarea dojoType="dijit.form.Textarea"
                             id="linkRef2Type" name="linkRef2Type" readOnly
                             style="width: 400px;" value="<?php echo i18n($refLinkType);?>"
                             maxlength="4000"
                             class="input"></textarea>
               <?php }?>
             </td>
           </tr>
           <tr><td>&nbsp;</td><td>&nbsp;</td></tr>
           <tr>
             <td class="dialogLabel" >
               <label for="linkRef2Id" ><?php echo i18n("linkElement") ?>&nbsp;<?php echo (isNewGui())?'':':';?>&nbsp;</label>
             </td>
             <td>
             
               <table><tr><td>
               <div id="dialogLinkList" dojoType="dijit.layout.ContentPane" region="center">
                <?php if($mode!='edit'){?>
                 <input id="linkRef2Id" name="linkRef2Id" type="hidden" value="" />
                 <?php }else{?>
                 <textarea dojoType="dijit.form.Textarea"
                             id="linkRef2Id" name="linkRef2Id" readOnly
                             style="width: 400px;" value="<?php echo '#'.$refLinkId.' '.htmlspecialchars(SqlList::getNameFromId($refLinkType, $refLinkId), ENT_QUOTES, 'UTF-8')?>"
                             maxlength="4000"
                             class="input"></textarea>
                   <?php }?>
               </div>
               </td><td style="vertical-align: top;<?php if($mode=='edit'){?>display:none;<?php }?>">
               <div style="width: 100%;">
                 <button id="linkDetailButton" dojoType="dijit.form.Button" showlabel="false"
                   title="<?php echo i18n('showDetail')?>" class="notButton notButtonRounded"
                   iconClass="iconSearch22 iconSearch iconSize22 imageColorNewGui">
                   <script type="dojo/connect" event="onClick" args="evt">
                    showDetailLink();
                 </script>
                 </button>
               </div>
               <div>
                 <button id="linkNewButton" dojoType="dijit.form.Button" showlabel="false"
                  title="<?php echo i18n('comboNewButton');?>" 
                  iconClass="dijitButtonIcon dijitButtonIconNew" class="notButton notButtonRounded">
                  <script type="dojo/connect" event="onClick" args="evt">
                    newDetailItemLink();
                  </script>
                </button>
               </div>

               </td></tr></table>
             </td>
           </tr>
            <tr><td>&nbsp;</td><td>&nbsp;</td></tr>
           </table>
           <div id="linkDocumentVersionDiv" style="display:none">
           <table>
           <tr>
               <td class="dialogLabel" >
                   <label for="linkRef2Type" ><?php echo i18n("colIdVersion") ?>&nbsp;<?php echo (isNewGui())?'':':';?>&nbsp;</label>
               </td>
               <td>
                  <select dojoType="dijit.form.FilteringSelect" 
                  <?php echo autoOpenFilteringSelect();?>
                    id="linkDocumentVersion" name="linkDocumentVersion" 
                    onchange=""
                    class="input" value="" >
                  </select>
                  <?php if (0) { //Desactivated?>                
                  <img src="css/images/smallButtonAdd.png" onClick="addDocumentVersion();" title="<?php echo i18n('addDocumentVersion');?>" class="smallButton"/>
                  <?php }?>
               </td>
           </tr>
           <tr><td>&nbsp;</td><td>&nbsp;</td></tr>
         </table>
         </div>
         <table>  
           <tr>
               <td class="dialogLabel" >
                   <label for="linkRef2Type" ><?php echo i18n("colComment") ?>&nbsp;<?php echo (isNewGui())?'':':';?>&nbsp;</label>
               </td>
               <td>
                   <textarea dojoType="dijit.form.Textarea"
                             id="linkComment" name="linkComment"
                             style="width: 400px;"
                             maxlength="4000"
                             class="input"></textarea>
               </td>
           </tr>
           <tr><td>&nbsp;</td><td>&nbsp;</td></tr>
   
            <td class="dialogLabel"  >
               
             </td>     
          <td>
            <?php if (isNewGui()) {?>
            <div  id="copyLinksofLinkedSwitch" class="colorSwitch <?php if($mode=='edit'){?> mblSwitchDisabled <?php }?> " data-dojo-type="dojox/mobile/Switch" 
          	   value="off" leftLabel="" rightLabel=""  style="width:10px;position:relative; left:0px;top:2px;z-index:99;" >
          	  <script type="dojo/method" event="onStateChanged" >
	             dijit.byId("copyLinksofLinked").set("checked",(this.value=="on")?true:false);
	            </script>
          	</div>
          	<?php }?>
             <input  dojoType="dijit.form.CheckBox" name="copyLinksofLinked" id="copyLinksofLinked" checked=false <?php if (isNewGui()) {?>style="display:none;"<?php }?>/>
             <label style="float:none" for="copyLinksofLinked" ><?php echo i18n("copyLinkFromOriginalElement") ?></label>
          </td>
          <tr><td>&nbsp;</td><td>&nbsp;</td></tr>
          
          <td class="dialogLabel"  >
               
             </td> 
          <td>
            <?php if (isNewGui()) {?>
            <div  id="synchronizationLinkSwitch" class="colorSwitch" data-dojo-type="dojox/mobile/Switch" 
          	   value="<?php echo ($link->idSynchronizationItem != null) ? 'on' : 'off'; ?>"
          	   leftLabel="" rightLabel=""  style="width:10px;position:relative; left:0px;top:2px;z-index:99;" >
          	  <script type="dojo/method" event="onStateChanged" >
	             dijit.byId("synchronizationLink").set("checked",(this.value=="on")?true:false);
	            </script>
          	</div>
          	<?php }?>
             <input  dojoType="dijit.form.CheckBox" name="synchronizationLink" id="synchronizationLink" checked=false <?php if (isNewGui()) {?>style="display:none;"<?php }?>/>
             <label style="float:none" for="synchronizationLink" ><?php echo i18n("synchronizationLink") ?></label>
          </td>
          <tr><td>&nbsp;</td><td>&nbsp;</td></tr>
         </table>         
        </form>
      </td>
    </tr>
    <tr>
      <td align="center">
        <input type="hidden" id="dialogLinkAction">
        <button class="mediumTextButton" dojoType="dijit.form.Button" type="button" onclick="dijit.byId('dialogLink').hide();">
          <?php echo i18n("buttonCancel");?>
        </button>
        <button class="mediumTextButton" dojoType="dijit.form.Button" type="submit" id="dialogLinkSubmit" onclick="protectDblClick(this);saveLink();return false;">
          <?php echo i18n("buttonOK");?>
        </button>
      </td>
    </tr>
  </table>
