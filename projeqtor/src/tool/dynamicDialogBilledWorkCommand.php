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
$mode = RequestHandler::getValue('mode',false,null);
$idBill = RequestHandler::getValue('idBill',false,null);
$id = RequestHandler::getId('id');
$idWorkCommand = RequestHandler::getId('idWorkCommand');
$quantity = RequestHandler::getNumeric('quantity');
$unitAmount = null;
$totalAmount = null;
$unitAmountLocal = null;
$totalAmountLocal = null;
$qt1 = null;
$qt2 = null;
$qt3 = null;
$qt4 = null;
if($id){
  $workCommandBill = new WorkCommandBilled($id);
  $workCom = new WorkCommand($workCommandBill->idWorkCommand);
  $idWorkUnit = $workCom->idWorkUnit;
  $workUnitName = SqlList::getNameFromId('WorkUnit', $idWorkUnit);
  $idComplexity = $workCom->idComplexity;
  $complexityName = SqlList::getNameFromId('Complexity', $idComplexity);
  $unitAmount = $workCom->unitAmount;
  $totalAmount = $unitAmount*$quantity;
  $unitAmountLocal = $workCom->unitAmountLocal;
  $totalAmountLocal = $unitAmountLocal*$quantity;
  $qt1 = $workCom->commandQuantity;
  $qt2 = $workCom->doneQuantity;
  $qt3 = $workCom->billedQuantity;
  $qt4 = $workCom->acceptedQuantity;
}
$obj = new Bill($idBill);
$currencyLocal=Project::getProjectCurrencyWithCss($obj->idProject);
$currencyPositionLocal=Project::getProjectCurrencyPosition($obj->idProject);
$hasLocalCurrency=Project::hasProjectCurrency($obj->idProject);
$showGlobalCurrency=$obj->showGlobalCurrency();
?>
  <table>
    <tr>
      <td>
       <form dojoType="dijit.form.Form" id='billedWorkCommandForm' name='billedWorkCommandForm' onSubmit="return false;">
        <input id="mode" name="mode" type="hidden" value="<?php echo $mode;?>" />
        <input id="id" name="id" type="hidden" value="<?php echo $id;?>" />
        <input id="idBill" name="idBill" type="hidden" value="<?php echo $idBill;?>" />
        <input id="statusBill" name="statusBill" type="hidden" value="<?php echo $obj->done;?>" />
         <table>
         
          <tr>
             <td class="dialogLabel"  >
               <label for="billedWorkCommandWorkCommand" ><?php echo pq_strtolower (i18n("colWorkCommand")); ?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
             </td>
             <td>
               <select dojoType="dijit.form.FilteringSelect"
              <?php echo autoOpenFilteringSelect();?>
                id="billedWorkCommandWorkCommand" name="billedWorkCommandWorkCommand"
                class="input"  style="border-left:3px solid red !important;" requiered="requiered"
                onChange="changeBilledWorkCommand();"  <?php if($mode=='edit'){?>readOnly<?php }?>
                missingMessage="<?php echo i18n('messageMandatory',array(i18n('colIdWorkCommand')));?>" >
                 <?php 
                 if($mode=='edit'){
                  htmlDrawOptionForReference('idWorkCommand',$idWorkCommand, $obj, false,array('elementary', 'idProject'), array('1', $obj->idProject));
                 }else{
                  htmlDrawOptionForReference('idWorkCommand',null, $obj, false, array('elementary', 'idProject'), array('1', $obj->idProject)); 
                 }?>
               </select> 
             </td>
           </tr>
           <tr>
             <td class="dialogLabel"  >
               <label for="billedWorkCommandWorkUnit" ><?php echo i18n("colIdWorkUnit") ?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
             </td>
             <td>
               <input dojoType="dijit.form.ValidationTextBox"
              <?php echo autoOpenFilteringSelect();?>
                id="billedWorkCommandWorkUnit" name="billedWorkCommandWorkUnit"
                class="input" <?php if($mode=='edit'){?>value="<?php echo $workUnitName;?>"<?php }?> readOnly> 
             </td>
           </tr>
           <tr>
             <td class="dialogLabel"  >
               <label for="billedWorkCommandComplexity" ><?php echo i18n("colIdComplexity") ?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
             </td>
             <td>
             <input dojoType="dijit.form.ValidationTextBox"
              <?php echo autoOpenFilteringSelect();?> <?php if($mode=='edit'){?>value="<?php echo $complexityName;?>"<?php }?>
                id="billedWorkCommandComplexity" name="billedWorkCommandComplexity"
                class="input" readOnly>
             </td>
           </tr>
           <tr>
             <td class="dialogLabel" >
               <label for="billedWorkCommandUnitAmount" ><?php echo i18n("colUnitAmount");?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
             </td>
             <td>
             <?php if ($currencyPosition=='before') echo $currency;?>
               <input dojoType="dijit.form.NumberTextBox" 
                id="billedWorkCommandUnitAmount" name="billedWorkCommandUnitAmount"
                readonly 
                style="width:100px;<?php if (! $showGlobalCurrency) echo 'display:none;'?>"
                class="input"  value="<?php echo $unitAmount;?>">  
               </input> 
               <?php if ($currencyPosition=='after') echo $currency;?>
             
             <?php if ($hasLocalCurrency) {?>
             <?php if ($currencyPositionLocal=='before') echo $currencyLocal;?>
               <input dojoType="dijit.form.NumberTextBox" 
                id="billedWorkCommandUnitAmountLocal" name="billedWorkCommandUnitAmountLocal"
                readonly 
                style="width:100px;"
                class="input localFieldClass"  value="<?php echo $unitAmountLocal;?>">  
               </input> 
               <?php if ($currencyPositionLocal=='after') echo $currencyLocal;?>
             <?php }?>
             </td>
             
           </tr>
            <tr>
             <td class="dialogLabel" >
               <label for="billedWorkCommandQuantity" ><?php echo i18n("colQuantity");?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
             </td>
             <td>
             <table>
             <tr>
              <td style="text-align:center;"><?php echo pq_ucfirst(i18n("ordered"));?></td>
              <td style="text-align:center;"><?php echo pq_ucfirst(i18n("used"));?></td>
              <td style="text-align:center;"><?php echo pq_ucfirst(i18n("colAccepted"));?></td>
              <td style="text-align:center;"><?php echo pq_ucfirst(i18n("colBilled"));?></td>
             </tr>
             <tr>
               <td>
                 <div dojoType="dijit.form.NumberTextBox" 
                    id="billedWorkCommandCommand" name="billedWorkCommandCommand"
                    style="width:100px;"  readOnly
                    class="input"  value="<?php echo $qt1;?>">
                    <?php echo $keyDownEventScript;?>  
                 </div>
               </td>
                <td>
                 <div dojoType="dijit.form.NumberTextBox" 
                    id="billedWorkCommandDone" name="billedWorkCommandDone"
                    style="width:100px;"  readOnly
                    class="input"  value="<?php echo $qt2;?>">
                    <?php echo $keyDownEventScript;?>  
                 </div>
               </td>
               <td>
                 <div dojoType="dijit.form.NumberTextBox" 
                    id="billedWorkCommandAccepted" name="billedWorkCommandAccepted"
                    style="width:100px;"  readOnly
                    class="input"  value="<?php echo $qt4;?>">
                    <?php echo $keyDownEventScript;?>  
                 </div>
               </td>
               <td>
                 <div dojoType="dijit.form.NumberTextBox" 
                    id="billedWorkCommandBilled" name="billedWorkCommandBilled"
                    style="width:100px;"  readOnly
                    class="input"  value="<?php echo $qt3;?>">
                    <?php echo $keyDownEventScript;?>  
                 </div>
               </td>
             </tr>
            </table></td>
            </tr>
            <tr>
             <td class="dialogLabel" >
               <label for="billedWorkCommandQuantityBilled" ><?php echo i18n("colBilledQuantity");?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
             </td>
             <td>
               <div dojoType="dijit.form.NumberTextBox" 
                  id="billedWorkCommandQuantityBilled" name="billedWorkCommandQuantityBilled"
                  style="width:100px;border-left:3px solid red !important;" required="required"  constraints="{min:0.01}"
                  onChange="billedWorkCommandChangeQuantity('<?php echo $mode;?>','<?php echo $id;?>');"  <?php if($mode!='edit'){?>readOnly<?php }?>
                  class="input"  value="<?php echo $quantity;?>">
                  <?php echo $keyDownEventScript;?>  
               </div>
             </td>
            </tr>
            <tr>
             <td class="dialogLabel" >
               <label for="billedWorkCommandAmount" ><?php echo i18n("colAmount");?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
             </td>
             <td>
             <?php if ($currencyPosition=='before') echo $currency;?>
               <input dojoType="dijit.form.NumberTextBox" 
                id="billedWorkCommandAmount" name="billedWorkCommandAmount"
                readonly 
                style="width:100px;<?php if (! $showGlobalCurrency) echo 'display:none;'?>"
                class="input"  value="<?php echo $totalAmount;?>">  
               </input> 
               <?php if ($currencyPosition=='after') echo $currency;?>
               <?php if ($hasLocalCurrency) {?>
               <?php if ($currencyPositionLocal=='before') echo $currencyLocal;?>
                 <input dojoType="dijit.form.NumberTextBox" 
                  id="billedWorkCommandAmountLocal" name="billedWorkCommandAmountLocal"
                  readonly 
                  style="width:100px;"
                  class="input localFieldClass"  value="<?php echo $totalAmountLocal;?>">  
                 </input> 
                 <?php if ($currencyPositionLocal=='after') echo $currencyLocal;?>
               <?php }?>
             </td>
           </tr>
           <tr><td>&nbsp;</td><td>&nbsp;</td></tr>
         </table>
        </form>
      </td>
    </tr>
    <tr>
      <td align="center">
        <input type="hidden" id="BilledWorkCommandAction">
        <button class="mediumTextButton" dojoType="dijit.form.Button" type="button" onclick="dijit.byId('dialogBilledWorkCommand').hide();">
          <?php echo i18n("buttonCancel");?>
        </button>
        <button class="mediumTextButton" dojoType="dijit.form.Button" type="submit" id="dialogBilledWorkCommandSubmit" onclick="protectDblClick(this);saveBilledWorkCommand();return false;">
          <?php echo i18n("buttonOK");?>
        </button>
      </td>
    </tr>
  </table>
