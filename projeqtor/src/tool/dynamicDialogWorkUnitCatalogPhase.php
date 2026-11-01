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
$id = RequestHandler::getId('id');
$idCatalog=RequestHandler::getValue('idCatalog',false,null);
$workUnits = new WorkUnit($id);
$wucp = new WorkUnitCatalogPhase($id);
$detailHeight=50;
$detailWidth=800;
?>
<div>
  <table style="width:100%;">
    <tr>
      <td>
       <form dojoType="dijit.form.Form" id='WorkUnitCatalogPhaseForm' name='WorkUnitCatalogPhaseForm' onSubmit="return false;">
        <input id="idCatalog" name="idCatalog" type="hidden" value="<?php echo $idCatalog;?>" />
        <input id="mode" name="mode" type="hidden" value="<?php echo $mode;?>" />
         <input id="idWorkUnit" name="idWorkUnit" type="hidden" value="<?php echo $id;?>" />
         <table style="width:1000px;">
         <tr><td>&nbsp;</td><td>&nbsp;</td></tr>
          <tr>
             <td style="width:100px;" class="dialogLabel" >
               <label for="WUCPReference" ><?php echo i18n("colWorkUnitCatalogPhases");?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
             </td>
             <td>
               <textarea dojoType="dijit.form.Textarea" 
                id="WUCPReferences" name="WUCPReferences"
                style="width:852px;border-left: 3px solid rgb(255, 0, 0);"
                maxlength="4000" 
                class="input"><?php echo pq_htmlspecialchars($wucp->name);?></textarea>   
             </td>
           </tr>
         <tr><td>&nbsp;</td><td>&nbsp;</td></tr>
           <tr>
             <td style="width:100px;vertical-align: top;" class="dialogLabel" >
               <label for="WUCPPercent" ><?php echo i18n("colPercent");?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
             </td>
             <td>
              <input id="WUCPPercent" name="WUCPPercent" type="hidden" value=""/>
                    <input  data-dojo-type="dijit.form.NumberTextBox" "
                    name="WUCPPercents" id="WUCPPercents" value="<?php echo pq_htmlspecialchars($wucp->ratioPct);?>" />
             <span><?php echo i18n('percent') ?></span>      
             </td>

          </tr>
         </table>
        </form>
      </td>
    </tr>
    <tr><td>&nbsp;</td><td>&nbsp;</td></tr>
    <tr>
      <td align="center">
        <input type="hidden" id="WorkUnitCatalogPhaseAction">
        <button class="mediumTextButton" dojoType="dijit.form.Button" type="button" onclick="dijit.byId('dialogWorkUnitCatalogPhase').hide();">
          <?php echo i18n("buttonCancel");?>
        </button>
        <button class="mediumTextButton" dojoType="dijit.form.Button" type="submit" id="dialogWorkUnitCatalogPhaseSubmit" onclick="protectDblClick(this);saveWorkUnitCatalogPhase();return false;">
          <?php echo i18n("buttonOK");?>
        </button>
      </td>
    </tr>
    <tr><td>&nbsp;</td><td>&nbsp;</td></tr>
  </table>
</div>