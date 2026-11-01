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
$currency=Parameter::getGlobalParameter('currency');
$currencyPosition=Parameter::getGlobalParameter('currencyPosition');

$refId=RequestHandler::getId('refId');
$refType=RequestHandler::getValue('refType');

?>
  <table>
    <tr>
      <td>
       <form dojoType="dijit.form.Form" id='workImputationForm' name='workImputationForm' onSubmit="return false;">
        <input id="refId" name="refId" type="hidden" value="<?php echo $refId;?>" />
        <input id="refType" name="refType" type="hidden" value="<?php echo $refType;?>" />
         <table>
           <tr>
             <td class="dialogLabel"  >
               <label for="workImputationName"  style="width: 70px;" ><?php echo i18n("colName") ?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
             </td>
             <td>
               <textarea dojoType="dijit.form.Textarea" 
                  id="workImputationName" name="workImputationName"
                  style="width: 300px;<?php if (isNewGui()) echo 'min-height:32px;max-height:153px';?>"
                  maxlength="100" class="required input" value=""
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
        <input type="hidden" id="workImputationAction">
        <button class="mediumTextButton" dojoType="dijit.form.Button" type="button" onclick="dijit.byId('dialogWorkImputationLine').hide();">
          <?php echo i18n("buttonCancel");?>
        </button>
        <button class="mediumTextButton" dojoType="dijit.form.Button" type="submit" id="dialogWorkImputationSubmit" onclick="protectDblClick(this);saveWorkCategory();return false;">
          <?php echo i18n("buttonOK");?>
        </button>
      </td>
    </tr>
  </table>
