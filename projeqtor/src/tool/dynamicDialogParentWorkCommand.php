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
$readOnly = false;
$keyDownEventScript=NumberFormatter52::getKeyDownEvent();
$currency=Parameter::getGlobalParameter('currency');
$currencyPosition=Parameter::getGlobalParameter('currencyPosition');
$mode = RequestHandler::getValue('mode',false,null);
$idCommand=RequestHandler::getValue('idCommand',false,null);
$workCommandParentName = RequestHandler::getValue('workCommandParentName')?: ' ';
$id = RequestHandler::getId('id');
$obj = new Command($idCommand);

?>
  <table>
    <tr>
      <td>
       <form dojoType="dijit.form.Form" id='workCommandParentForm' name='workCommandParentForm' onSubmit="return false;">
        <input id="mode" name="mode" type="hidden" value="<?php echo $mode;?>" />
        <input id="id" name="id" type="hidden" value="<?php echo $id;?>" />
        <input id="idCommand" name="idCommand" type="hidden" value="<?php echo $idCommand;?>" />
         <table>
           <tr>
             <td class="dialogLabel"  >
               <label for="workCommandParentName" ><?php echo i18n("colName") ?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
             </td>
             <td>
               <textarea dojoType="dijit.form.Textarea" 
                  id="workCommandParentName" name="workCommandParentName"
                  style="width: 500px;<?php if (isNewGui()) echo 'min-height:32px;max-height:153px';?>"
                  maxlength="200" class="required input"  value="<?php echo $workCommandParentName;?>"
                  missingMessage="<?php echo i18n('messageMandatory',array('colName'));?>"></textarea>
             </td>
           </tr>
           <tr><td>&nbsp;</td><td>&nbsp;</td></tr>
         </table>
        </form>
      </td>
    </tr>
    <tr>
      <td align="center">
        <input type="hidden" id="workCommandAction">
        <button class="mediumTextButton" dojoType="dijit.form.Button" type="button" onclick="dijit.byId('dialogParentWorkCommand').hide();">
          <?php echo i18n("buttonCancel");?>
        </button>
        <button class="mediumTextButton" dojoType="dijit.form.Button" type="submit" id="dialogParentWorkCommandSubmit" onclick="protectDblClick(this);saveParentWorkCommand();return false;">
          <?php echo i18n("buttonOK");?>
        </button>
      </td>
    </tr>
  </table>
