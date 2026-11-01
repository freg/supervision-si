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
 * You can get complete code of ProjeQtOr, other activity, help and information
 * about contributors at http://www.projeqtor.org 
 *     
 *** DO NOT REMOVE THIS NOTICE ************************************************/
include_once ("../tool/projeqtor.php");
$keyDownEventScript=NumberFormatter52::getKeyDownEvent();
$mode = RequestHandler::getValue('mode',false,null);
$idActivity=RequestHandler::getValue('idActivity',false,null);
$idActivitySkill=RequestHandler::getValue('idActivitySkill',false,null);

$act = new Activity($idActivity,true);
$actSkill = new ActivitySkill($idActivitySkill, true);
$skill = new Skill($actSkill->idSkill);

?>
  <table>
    <tr>
      <td>
       <form dojoType="dijit.form.Form" id='activitySkillForm' name='activitySkillForm' onSubmit="return false;">
        <input id="idActivity" name="idActivity" type="hidden" value="<?php echo $idActivity;?>" />
        <input id="mode" name="mode" type="hidden" value="<?php echo ($mode != '')?$mode:'add';?>" />
        <input id="idActivitySkill" name="idActivitySkill" type="hidden" value="<?php echo $idActivitySkill;?>" />
         <table>
           <tr>
             <td class="dialogLabel" >
               <label for="idSkill" style="white-space:nowrap;width:200px;"><?php echo i18n("colIdSkill");?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
             </td>
             <td>
                <select dojoType="dijit.form.FilteringSelect" 
								<?php echo autoOpenFilteringSelect();?>
								id="skillIdAct" name="skillIdAct" 
								<?php //if ($actSkill->idSkill) echo ' readonly="readonly" ';?>
								class="input required" value="<?php echo $actSkill->idSkill;?>" required="required">
                 <?php htmlDrawOptionForReference('idSkill', $actSkill->idSkill, $skill, true);?>
               </select>
             </td>
             <td style="vertical-align: top">
                 <button id="skillDetailButtonAct" dojoType="dijit.form.Button" showlabel="false"
                   title="<?php echo i18n('showDetail')?>"
                   iconClass="iconSearch22 iconSearch iconSize22 imageColorNewGui" class="notButton notButtonRounded">
                   <script type="dojo/connect" event="onClick" args="evt">
                    var canCreate=("<?php echo securityGetAccessRightYesNo('menuSkill','create');?>"=="YES")?1:0;
                    showDetail('skillIdAct', canCreate , 'Skill', false);
                   </script>
                 </button>
               </td>  
           </tr>
           <tr>
             <td class="dialogLabel" >
               <label for="skillLevelIdAct" style="white-space:nowrap;width:200px;"><?php echo i18n("colIdSkillLevel");?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
             </td>
             <td>
                <select dojoType="dijit.form.FilteringSelect"
								<?php echo autoOpenFilteringSelect();?>
								id="skillLevelIdAct" name="skillLevelIdAct"
								<?php //if ($actSkill->idSkillLevel) echo ' readonly="readonly" ';?>
								class="input required" value="<?php echo $actSkill->idSkillLevel;?>" required="required">
                 <?php htmlDrawOptionForReference('idSkillLevel', $actSkill->idSkillLevel, null, true);?>
               </select>
             </td>
           </tr>
           <tr><td>&nbsp;</td><td>&nbsp;</td></tr>
         </table>
        </form>
      </td>
    </tr>
    <tr>
      <td align="center">
        <input type="hidden" id="activitySkillAction">
        <button class="mediumTextButton" dojoType="dijit.form.Button" type="button" onclick="dijit.byId('dialogActivitySkill').hide();">
          <?php echo i18n("buttonCancel");?>
        </button>
        <button class="mediumTextButton" dojoType="dijit.form.Button" type="submit" id="dialogActivitySkillSubmit" onclick="protectDblClick(this);saveActivitySkill();return false;">
          <?php echo i18n("buttonOK");?>
        </button>
      </td>
    </tr>
  </table>
