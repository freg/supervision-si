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

scriptLog('dynamicDialogUpdateResourceCost.php');

$user = getSessionUser();
$resourceProfile = new Profile($user->idProfile);
$currentDay = date('Y-m-d');

$idRole = RequestHandler::getId('idRole');

$updateResourceCostOption = 'updateOptionCostFromDate';
$role = new Role($idRole);
?>
  <table width="100%">
    <tr>
      <td>
        <form dojoType="dijit.form.Form" id='updateResourceCostForm' name='updateResourceCostForm' onSubmit="return false;">
          <table width="925px;" style="white-space:nowrap">
            <input type="hidden" id="idRole" name="idRole" value="<?php echo $idRole;?>"/>
            <tr>
              <td class="assignHeader"><?php echo pq_ucfirst(i18n('UpdateResourceCostChoices'));?></td>
            </tr>
            <tr>
              <td></br></td>
            </tr>
            <tr><td>
              <table width="100%">
                <tr>
                  <td>
                    <div id="resourceCostRadioButtonDiv" name="resourceCostRadioButtonDiv" dojoType="dijit.layout.ContentPane" region="center">
                      <table width="100%">
                        <tr style="height:22px">
                          <td style="padding-left:15px;width: 22px;">
                            <input type="radio" data-dojo-type="dijit/form/RadioButton" class="marginLabel" onchange="if(this.checked){dijit.byId('updateResourceCostStartDate').set('class', 'input required');dijit.byId('updateResourceCostStartDate').set('required', true);}"
                              id="updateOptionCostFromDate" name="updateResourceCostOption" value="updateOptionCostFromDate" <?php if($updateResourceCostOption == 'updateOptionCostFromDate'){echo 'checked';}?>/>
                            
                          </td>
                          <td>
                            <label for="updateOptionCostFromDate" class="dialogLabel" style="text-align:left;font-weight: bold;"><?php echo i18n('updateOptionCostFromDate').Tool::getDoublePoint();?></label>
                          </td>
                          <td>
                            <input id="updateResourceCostStartDate" name="updateResourceCostStartDate" value="" dojoType="dijit.form.DateTextBox" constraints="{datePattern:browserLocaleDateFormatJs}" style="width:100px" 
                            class="<?php if($updateResourceCostOption == 'updateOptionCostFromDate'){echo 'input required';}?>" required="<?php if($updateResourceCostOption == 'updateOptionCostFromDate'){echo 'true';}?>"/>
                          </td>
                        </tr>
                        <tr>
                          <td colspan="3">
                            <label for="updateOptionCostFromDate" class="dialogLabel" style="padding-left:40px;text-align:left;font-size: 90%;"><?php echo i18n('OptionCostFromDate'); ?></label>
                          </td>
                        </tr>
                        <tr>
                          <td colspan="3">
                            <label for="updateOptionCostFromDate" class="dialogLabel" style="padding-left:40px;text-align:left;font-size: 90%;"><?php echo i18n('OptionCostFromDateDescription'); ?></label>
                          </td>
                        </tr>
                        <tr>
                          <td></br></td>
                        </tr>
                        <tr style="height:22px">
                          <td style="padding-left:15px;width: 22px;">
                            <input type="radio" data-dojo-type="dijit/form/RadioButton" onchange="if(this.checked){dijit.byId('updateResourceCostStartDate').set('class', '');dijit.byId('updateResourceCostStartDate').set('required', false);}"
                              id="updateOptionReplaceActualCost" name="updateResourceCostOption" value="updateOptionReplaceActualCost" class="marginLabel"/>
                          </td>
                          <td colspan="2">
                            <label for="updateOptionReplaceActualCost" class="dialogLabel" style="text-align:left;font-weight: bold;"><?php echo i18n('updateOptionReplaceActualCost').Tool::getDoublePoint();?></label>
                          </td>
                        </tr>
                        <tr>
                          <td colspan="3">
                            <label for="updateOptionReplaceActualCost" class="dialogLabel" style="padding-left:40px;text-align:left;font-size: 90%;"><?php echo i18n('OptionReplaceActualCost'); ?></label>
                          </td>
                        </tr>
                        <tr>
                          <td colspan="3">
                            <label for="updateOptionReplaceActualCost" class="dialogLabel" style="padding-left:40px;text-align:left;font-size: 90%;"><?php echo i18n('OptionReplaceActualCostDescription'); ?></label>
                          </td>
                        </tr>
                        <tr>
                          <td></br></td>
                        </tr>
                        <tr style="height:22px">
                          <td style="padding-left:15px;width: 22px;">
                            <input type="radio" data-dojo-type="dijit/form/RadioButton" onchange="if(this.checked){dijit.byId('updateResourceCostStartDate').set('class', '');dijit.byId('updateResourceCostStartDate').set('required', false);}"
                              id="updateOptionFullReplaceCost" name="updateResourceCostOption" value="updateOptionFullReplaceCost"/>&nbsp;&nbsp;
                          </td>
                          <td colspan="2">
                            <label for="updateOptionFullReplaceCost" class="dialogLabel" style="text-align:left;font-weight: bold;"><?php echo i18n('updateOptionFullReplaceCost').Tool::getDoublePoint();?></label>
                          </td>
                        </tr>
                        <tr>
                          <td colspan="3">
                            <label for="updateOptionFullReplaceCost" class="dialogLabel" style="padding-left:40px;text-align:left;font-size: 90%;"><?php echo i18n('OptionFullReplaceCost'); ?></label>
                          </td>
                        </tr>
                        <tr>
                          <td colspan="3">
                            <label for="updateOptionFullReplaceCost" class="dialogLabel" style="padding-left:40px;text-align:left;font-size: 90%;"><?php echo i18n('OptionFullReplaceCostDescription'); ?></label>
                          </td>
                        </tr>
                      </table>
                    </div>
                  </td>
                </tr>
              </table></td>
            </tr>
            <tr>
              <td></br></td>
            </tr>
          </table>
        </form>
     </td>
   </tr>
   <tr>
     <td></br></td>
   </tr>
   <table width="100%">
    <tr>
      <td align="center">
        <button dojoType="dijit.form.Button" type="button" onclick="dijit.byId('dialogUpdateResourceCost').hide();">
          <?php echo i18n("buttonCancel");?>
        </button>
        <button dojoType="dijit.form.Button" type="button" id="dialogUpdateResourceCostSubmit" type="submit" onclick="updateResourceCost();">
          <?php echo i18n("buttonOK");?>
        </button>
      </td>
    </tr>
  </table>
  </table>