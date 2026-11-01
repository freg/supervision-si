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
$idToken=RequestHandler::getValue('idToken',false,null);
$id=RequestHandler::getValue('idWorkTokenMarkup',false,null);
$used =(RequestHandler::isCodeSet('used') and RequestHandler::getValue('used')!=0)? RequestHandler::getValue('used'):null;
$detailHeight=50;
$detailWidth=800;
if($id){
  $workTokenMarkup = new WorkTokenMarkup($id);
  if(!$idToken)$idToken=$workTokenMarkup->idWorkToken;
}
?>
<div>
<form dojoType="dijit.form.Form" id='workTokenMarkupForm' name='workTokenMarkupForm' onSubmit="return false;" action="">
  <input id=idWorkToken name="idWorkToken" type="hidden" value="<?php echo $idToken;?>" />
  <input id="mode" name="mode" type="hidden" value="<?php echo $mode;?>" />
  <?php 
    if(isset($workTokenMarkup)) echo '<input id="idWorkTokenMarkup" name="idWorkTokenMarkup" type="hidden" value="'.$id.'" />';
  ?>
    <table style="width:100%;padding:5%;">
      <tr><td>&nbsp;</td></tr>
      <tr>
        <td style="width:100px;" class="dialogLabel" >
          <label for="LabelMarkup" ><?php echo i18n("colLabelMarkup");?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
        </td>
        <td>
          <div dojoType="dijit.form.Textarea" id="LabelMarkup" name="LabelMarkup"
          style="width:200px;border-left: 3px solid rgb(255, 0, 0);"
          class="input"><?php echo (isset($workTokenMarkup))?pq_htmlspecialchars($workTokenMarkup->name):'';?></div>   
        </td>
      </tr>
      <tr>
        <td class="dialogLabel" >
          <label for="coefValue" ><?php echo i18n("colCoefValue");?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
        </td>
        <td>
            <div id="coefValue" name="coefValue" 
                 dojoType="dijit.form.NumberTextBox" 
                 constraints="{min:-1}" 
                 title="<?php echo i18n("explainHowEnterCoef")?>"
                 style="width:50px; text-align: right;border-left: 3px solid rgb(255, 0, 0);" 
                 value="<?php echo (isset($workTokenMarkup))? $workTokenMarkup->coefficient:'';?>"
                 required="true" <?php if($used) echo "readonly";?>>
                 <?php echo $keyDownEventScript;?>
            </div>
          <div dojoType="dijit.Tooltip" connectId="coefValue"><?php echo i18n("explainHowEnterCoef")?></div>
        </td>
      </tr>
      <tr><td>&nbsp;</td></tr>
      <tr><td>&nbsp;</td></tr>
      <tr>
        <td align="center" colspan="2">
          <input type="hidden" id="workTokenMarkupAction">
          <button class="mediumTextButton" dojoType="dijit.form.Button" type="button" onclick="dijit.byId('dialogWorkTokenMarkup').hide();">
            <?php echo i18n("buttonCancel");?>
          </button>
          <button class="mediumTextButton" dojoType="dijit.form.Button" type="submit" id="dialogworkTokenMarkupSubmit" onclick="protectDblClick(this);saveWorkTokenMarkup();return false;">
            <?php echo i18n("buttonOK");?>
          </button>
        </td>
      </tr>
    </table>
  </form>
</div>