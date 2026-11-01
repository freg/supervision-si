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
$idResource=RequestHandler::getValue('idResource',false,null);
$idResourceSkill=RequestHandler::getValue('idResourceSkill',false,null);

$res = new Resource($idResource,true);
$resSkill = new ResourceSkill($idResourceSkill, true);
$useUntil = $resSkill->useUntil;
$useSince = ($resSkill->useSince)?$resSkill->useSince:'';
$skill = new Skill($resSkill->idSkill);

?>
  <table>
    <tr>
      <td>
       <form dojoType="dijit.form.Form" id='resourceSkillForm' name='resourceSkillForm' onSubmit="return false;">
        <input id="idResource" name="idResource" type="hidden" value="<?php echo $idResource;?>" />
        <input id="mode" name="mode" type="hidden" value="<?php echo ($mode != '')?$mode:'add';?>" />
        <input id="idResourceSkill" name="idResourceSkill" type="hidden" value="<?php echo $idResourceSkill;?>" />
         <table>
           <tr>
             <td class="dialogLabel" >
               <label for="skillId" style="white-space:nowrap;width:200px;"><?php echo i18n("colIdSkill");?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
             </td>
             <td>
               <table><tr><td>
               <div id="dialogSkillList" dojoType="dijit.layout.ContentPane" region="center">
                <?php if($mode!='edit'){?>
                 <input id="skillId" name="skillId" type="hidden" value=""/>
                 <?php }else{?>
                 	<select dojoType="dijit.form.FilteringSelect" id="skillId" name="skillId"
										class="input" value="<?php echo $resSkill->idSkill;?>" readOnly>
                 		<option value="<?php echo $resSkill->idSkill;?>"><?php echo '#'.$resSkill->idSkill.' '.htmlspecialchars(SqlList::getNameFromId('Skill', $resSkill->idSkill), ENT_QUOTES, 'UTF-8')?></option>
               		</select>  
                 <?php }?>
               </div>
               </td><td style="vertical-align: top;<?php if($mode=='edit'){?>display:none;<?php }?>">
               <div style="width: 100%;">
                 <button id="skillDetailButton" dojoType="dijit.form.Button" showlabel="false"
                   title="<?php echo i18n('showDetail')?>" class="notButton notButtonRounded"
                   iconClass="iconSearch22 iconSearch iconSize22 imageColorNewGui">
                   <script type="dojo/connect" event="onClick" args="evt">
                    var canCreate=("<?php echo securityGetAccessRightYesNo('menuSkill','create');?>"=="YES")?1:0;
                    showDetail('skillId', canCreate , 'Skill', true);
                   </script>
                 </button>
               </div>
               </td></tr></table>
             </td>
           </tr>
           <tr>
             <td class="dialogLabel" >
               <label for="skillLevelId" style="white-space:nowrap;width:200px;"><?php echo i18n("colIdSkillLevel");?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
             </td>
             <td>
                <select dojoType="dijit.form.FilteringSelect"
								<?php echo autoOpenFilteringSelect();?>
								id="skillLevelId" name="skillLevelId"
								<?php //if ($resSkill->idSkillLevel) echo ' readonly="readonly" ';?>
								class="input required" value="<?php echo $resSkill->idSkillLevel;?>" required="required" onChange="getLastResourceSkill()">
                 <?php htmlDrawOptionForReference('idSkillLevel', $resSkill->idSkillLevel, null, true);?>
               </select>
             </td>
           </tr>
           <tr>
             <td colspan="2">
               <table>
                 <tr>
                   <td class="dialogLabel" >
                     <label for="skillResourceUseSince" style="white-space:nowrap;width:200px;"><?php echo i18n("useSince");?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
                   </td>
                   <td>
                     <input id="skillResourceUseSince" name="skillResourceUseSince" value="<?php if(isset($useSince)){ echo $useSince;} ?>"  
			                 dojoType="dijit.form.DateTextBox" class="input"
			                 constraints="{datePattern:browserLocaleDateFormatJs}"
                             style="width:100px" />
                   </td>
                   <td class="dialogLabel" >
                     <label for="skillResourceUseUntil" ><?php echo i18n("useUntil");?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
                   </td>
                   <td>
                   <input id="skillResourceUseUntil" name="skillResourceUseUntil" value="<?php if(isset($useUntil)){ echo $useUntil;} ?>"  
		                 dojoType="dijit.form.DateTextBox" 
		                 constraints="{datePattern:browserLocaleDateFormatJs}"
		                 style="width:100px" />
                   </td>
                 </tr>
               </table>
             </td>
           </tr>
           <tr>
             <td class="dialogLabel" >
               <label for="resourceSkillComment" style="white-space:nowrap;width:200px;"><?php echo i18n("colComment");?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
             </td>
             <td> 
               <textarea dojoType="dijit.form.Textarea" 
                id="resourceSkillComment" name="resourceSkillComment"
                style="width:408px;"
                maxlength="4000"
                class="input"><?php if(isset($resSkill->comment)){ echo br2nl($resSkill->comment);}?></textarea>   
             </td>
           </tr>
           <tr>
             <td class="dialogLabel" >
               <label for="idle" style="white-space:nowrap;width:200px;"><?php echo i18n("colIdle");?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
             </td>
             <td>
               <div id="resourceSkillIdle" name="resourceSkillIdle"
                 dojoType="dijit.form.CheckBox" type="checkbox" <?php if($resSkill->idle){ echo "checked='checked'";}?>>
               </div>
             </td>    
           </tr>
           <tr><td>&nbsp;</td><td>&nbsp;</td></tr>
         </table>
        </form>
      </td>
    </tr>
    <tr>
      <td align="center">
        <input type="hidden" id="resourceSkillAction">
        <button class="mediumTextButton" dojoType="dijit.form.Button" type="button" onclick="dijit.byId('dialogResourceSkill').hide();">
          <?php echo i18n("buttonCancel");?>
        </button>
        <button class="mediumTextButton" dojoType="dijit.form.Button" type="submit" id="dialogResourceSkillSubmit" onclick="protectDblClick(this);saveResourceSkill();return false;">
          <?php echo i18n("buttonOK");?>
        </button>
      </td>
    </tr>
  </table>
