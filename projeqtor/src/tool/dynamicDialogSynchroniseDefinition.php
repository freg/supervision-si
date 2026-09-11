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


$idProject = RequestHandler::getId('idProject');
$project = new Project($idProject);

?>
  <table>
    <tr>
      <td>
       <form dojoType="dijit.form.Form" id='synchroniseDefinitionForm' name='synchroniseDefinitionForm' onSubmit="return false;">
       <input id="idProject" name="idProject" type="hidden" value="<?php echo $idProject;?>" />
         <table>
             <tr>
                <td class="dialogLabel"  >
                  <label for="synchroniseDefinitionTicket" style="text-align:right;width:100%;"><?php echo i18n("colSynchroniseDefinitionTicket") ?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
                </td>
                <td> 
                <select dojoType="dijit.form.FilteringSelect" class="input"  style="width: 200px;" id="synchroniseDefinitionTicket" name="synchroniseDefinitionTicket" readOnly>
                   <option value="tickets" <?php echo 'SELECTED';?> ><?php echo i18n('menuTicket'); ?> </option>
                   <option value="activities" ><?php echo i18n('Activity'); ?> </option>
                 </select>
                </td>
              </tr>
                 <tr>
                <td class="dialogLabel"  >
                  <label for="synchroniseDefinitionActivity" style="text-align:right;width:100%;" ><?php echo i18n("colSynchroniseDefinitionActivity") ?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
                </td>
                <td>
                <select dojoType="dijit.form.FilteringSelect" class="input"  style="width: 200px;" id="synchroniseDefinitionActivity" name="synchroniseDefinitionActivity" readOnly>
                   <option value="tickets"><?php echo i18n('menuTicket'); ?> </option>
                   <option value="activities" <?php echo 'SELECTED';?> ><?php echo i18n('Activity'); ?> </option>
                 </select>
                </td>
              </tr>
          <tr>
             <td class="dialogLabel"  >
               <label for="synchroniseDefinitionTicketType"  style="text-align:right;width:100%;"><?php echo i18n("colTypedeticketconcerne") ?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
             </td>
             <td> 
               <select dojoType="dijit.form.FilteringSelect"
              <?php echo autoOpenFilteringSelect();?>
                id="synchroniseDefinitionTicketType" name="synchroniseDefinitionTicketType" class="input" >
                 <?php htmlDrawOptionForReference('idTicketType',null,null, false); ?>
               </select> 
             </td>
          </tr>
          <tr>
             <td class="dialogLabel"  >
               <label for="synchroniseDefinitionStatus" style="text-align:right;width:100%;"><?php echo i18n("colSynchroniseState") ?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
             </td>
             <td>
               <select dojoType="dijit.form.FilteringSelect"
              <?php echo autoOpenFilteringSelect();?> style="border-left:3px solid red !important;"
                id="synchroniseDefinitionStatus" name="synchroniseDefinitionStatus" class="input" required="required"  >
                 <?php htmlDrawOptionForReference('idStatus',null,null, true); ?>
               </select> 
             </td>
          </tr>
           <tr>
             <td class="dialogLabel"> 
               <label for="synchroniseDefinitionActivityType" style="text-align:right;width:100%;"><?php echo i18n("colSynchroniseActivityType") ?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
             </td>
             <td>
               <select dojoType="dijit.form.FilteringSelect"
              <?php echo autoOpenFilteringSelect();?>
                id="synchroniseDefinitionActivityType" name="synchroniseDefinitionActivityType" class="input"  required="required"  style="border-left:3px solid red !important;">
                 <?php htmlDrawOptionForReference('idActivityType',null,$project, true); ?>
               </select> 
             </td>
          </tr>
          <tr>
            <td class="dialogLabel"> 
            <label style="text-align:right;width:100%;" for="synchroniseDefinitionPlanningActivity" ><?php echo i18n("SynchroniseActivityPlanning"); ?>&nbsp;&nbsp;</label>
              </td>
              <td>
              <?php if (isNewGui()) {?>
              <div  id="synchroniseDefinitionPlanningActivitySwitch" class="colorSwitch" data-dojo-type="dojox/mobile/Switch" 
            	   value="on" leftLabel="" rightLabel=""  style="width:10px;position:relative; left:0px;top:2px;z-index:99;" >
            	  <script type="dojo/method" event="onStateChanged" >
	             dijit.byId("synchroniseDefinitionPlanningActivity").set("checked",(this.value=="on")?true:false);
	            </script>
            	</div>
            	<?php }?>
               <input  dojoType="dijit.form.CheckBox" name="synchroniseDefinitionPlanningActivity" id="synchroniseDefinitionPlanningActivity" checked=true <?php if (isNewGui()) {?>style="display:none;"<?php }?>/>
              </td>
          </tr>
         <tr><td>&nbsp;</td><td>&nbsp;</td></tr>
         <tr><td>&nbsp;</td><td>&nbsp;</td></tr>
           <tr>
          <td class="filterHeader" colspan="2"><?php echo i18n("SynchroniseExistingTreatment"); ?></td>
          </tr>
          <tr><td>&nbsp;</td><td>&nbsp;</td></tr>
          <tr>
            <td class="dialogLabel"  > 
             <label style="text-align:right;width:100%;" for="synchroniseDefinitionTicketExisting" ><?php echo i18n("SynchroniseTicketExisting"); ?>&nbsp;&nbsp;</label>
              </td>
              <td>
              <?php if (isNewGui()) {?>
              <div  id="synchroniseDefinitionTicketExistingSwitch" class="colorSwitch" data-dojo-type="dojox/mobile/Switch" 
            	   value="off" leftLabel="" rightLabel=""  style="width:10px;position:relative; left:0px;top:2px;z-index:99;" >
            	  <script type="dojo/method" event="onStateChanged" >
	               dijit.byId("synchroniseDefinitionTicketExisting").set("checked",(this.value=="on")?true:false);
	            </script>
            	</div>
            	<?php }?>
               <input  dojoType="dijit.form.CheckBox" name="synchroniseDefinitionTicketExisting" id="synchroniseDefinitionTicketExisting" checked=false <?php if (isNewGui()) {?>style="display:none;"<?php }?>/>
            </td>
          </tr>
           <tr><td>&nbsp;</td><td>&nbsp;</td></tr>
         </table>
        </form>
      </td>
    </tr>
    <tr><td>&nbsp;</td><td>&nbsp;</td></tr>
    <tr><td>&nbsp;</td><td>&nbsp;</td></tr>
    <tr>
      <td align="center">
        <input type="hidden" id="synchroniseDefinitionAction">
        <button class="mediumTextButton" dojoType="dijit.form.Button" type="button" onclick="dijit.byId('dialogSynchroniseDefinition').hide();">
          <?php echo i18n("buttonCancel");?>
        </button>
        <button class="mediumTextButton" dojoType="dijit.form.Button" type="submit" id="dialogSynchroniseDefinitionSubmit" onclick="protectDblClick(this);saveSynchronizeDefinition();return false;">
          <?php echo i18n("buttonOK");?>
        </button>
      </td>
    </tr>
  </table>
