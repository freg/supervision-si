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
$countNbElement = SynchronizedItems::getNumberSynchronizedItemByProject($idProject);
$countNbElementAll = SynchronizedItems::getNumberSynchronizedItemByProjectAll($idProject);
$countClose = $countNbElementAll - $countNbElement;
?>
  <table>
    <tr>
      <td>
       <form dojoType="dijit.form.Form" id='disableSynchronizeDefinitionForm' name='disableSynchronizeDefinitionForm' onSubmit="return false;">
       <input id="idProject" name="idProject" type="hidden" value="<?php echo $idProject;?>" />
         <table>
          <tr>
                <td class="dialogLabel"  >
                  <label style="width:370px;text-align:left;"><?php echo pq_ucfirst(i18n("numberOfSynchElement")); ?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
                </td>
                <td>
                <span style="text-align:left;"><?php echo $countNbElement;?></span>
                </td>
          </tr>
          <tr><td>&nbsp;</td><td>&nbsp;</td></tr>
          <tr>
                <td class="dialogLabel" > 
                <label style="width:370px;text-align:left;"><?php echo pq_ucfirst(i18n("numberOfSynchElementIdle")); ?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
                </td>
                <td>
                <span style="text-align:left;"><?php echo $countClose;?></span>
                </td>
          </tr>
          <tr><td>&nbsp;</td><td>&nbsp;</td></tr>
          <tr><td>&nbsp;</td><td>&nbsp;</td></tr>
          <tr>
          <td class="filterHeader" colspan="2"><?php echo i18n("SynchroniseExistingTreatment"); ?></td>
          </tr>
         <tr>
                  <td>
                    <div id="radioButtonDisableSynchDiv" name="radioButtonDisableSynchDiv" dojoType="dijit.layout.ContentPane" region="center">
                      <table>
                        <tr style="height:36px">
                          <td>
                            <input type="radio" data-dojo-type="dijit/form/RadioButton" class="marginLabel"
                              id="deleteLinkSynch" name="disableSynch" value="delete" <?php echo 'checked';?>/>
                          </td>
                          <td>
                            <label for="deleteLinkSynch" class="dialogLabel " style="text-align:left;margin-left:10px;width:350px;"><?php echo i18n('DeleteLinkSynch').Tool::getDoublePoint();?></label>
                          </td>
                        </tr>
                        <tr style="height:36px">
                          <td>
                            <input type="radio" data-dojo-type="dijit/form/RadioButton" 
                              id="keepLinkSynch" name="disableSynch" value="keep" class="marginLabel"/>
                           </td>
                           <td>
                            <label for="keepLinkSynch" class="dialogLabel " style="text-align:left;margin-left:10px;width:350px;"><?php echo i18n('KeepLinkSynch').Tool::getDoublePoint();?></label>
                           </td>
                        </tr>
                      </table>
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
        <input type="hidden" id="disableSynchronizeDefinitionAction">
        <button class="mediumTextButton" dojoType="dijit.form.Button" type="button" onclick="dijit.byId('dialogDisableSynchronizeDefinition').hide();">
          <?php echo i18n("buttonCancel");?>
        </button>
        <button class="mediumTextButton" dojoType="dijit.form.Button" type="submit" id="dialogdisableSynchronizeDefinitionSubmit" onclick="protectDblClick(this);saveDisableSynchronizeDefinition();return false;">
          <?php echo i18n("buttonOK");?>
        </button>
      </td>
    </tr>
  </table>
