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
$idAcceptance = RequestHandler::getValue('idAcceptance',false,null);
$mode = RequestHandler::getValue('mode',false,null);
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
  $workCommandAcceptance = new WorkCommandAccepted($id);
  $workCom = new WorkCommand($workCommandAcceptance->idWorkCommand);
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
$obj = new Acceptance($idAcceptance);
$currencyLocal=Project::getProjectCurrencyWithCss($obj->idProject);
$currencyPositionLocal=Project::getProjectCurrencyPosition($obj->idProject);
$hasLocalCurrency=Project::hasProjectCurrency($obj->idProject);
$showGlobalCurrency=$obj->showGlobalCurrency();
?>
  <table>
    <tr>
      <td>
       <form dojoType="dijit.form.Form" id='acceptedWorkCommandForm' name='acceptedWorkCommandForm' onSubmit="return false;">
        <input id="mode" name="mode" type="hidden" value="<?php echo $mode;?>" />
        <input id="id" name="id" type="hidden" value="<?php echo $id;?>" />
        <input id="idAcceptance" name="idAcceptance" type="hidden" value="<?php echo $idAcceptance;?>" />
         <table>
          <tr>
             <td class="dialogLabel"  >
               <label for="acceptedWorkCommandWorkCommand" ><?php echo pq_strtolower (i18n("colWorkCommand")); ?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
             </td>
             <td>
               <select dojoType="dijit.form.FilteringSelect"
                id="acceptedWorkCommandWorkCommand" name="acceptedWorkCommandWorkCommand"
                <?php echo autoOpenFilteringSelect();?>
                class="input"  style="border-left:3px solid red !important;" requiered="requiered"
                onChange="changeAcceptedWorkCommand();"  <?php if($mode=='edit'){?>readOnly<?php }?>>
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
               <label for="acceptedWorkCommandWorkUnit" ><?php echo i18n("colIdWorkUnit") ?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
             </td>
             <td>
               <input dojoType="dijit.form.ValidationTextBox"
              <?php echo autoOpenFilteringSelect();?>
                id="acceptedWorkCommandWorkUnit" name="acceptedWorkCommandWorkUnit"
                class="input" <?php if($mode=='edit'){?>value="<?php echo $workUnitName;?>"<?php }?> readOnly> 
             </td>
           </tr>
           <tr>
             <td class="dialogLabel"  >
               <label for="acceptedWorkCommandComplexity" ><?php echo i18n("colIdComplexity") ?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
             </td>
             <td>
             <input dojoType="dijit.form.ValidationTextBox"
              <?php echo autoOpenFilteringSelect();?> <?php if($mode=='edit'){?>value="<?php echo $complexityName;?>"<?php }?>
                id="acceptedWorkCommandComplexity" name="acceptedWorkCommandComplexity"
                class="input" readOnly>
             </td>
           </tr>
           <tr>
             <td class="dialogLabel" >
               <label for="acceptedWorkCommandUnitAmount" ><?php echo i18n("colUnitAmount");?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
             </td>
             <td>
             <?php if ($currencyPosition=='before') echo $currency;?>
               <input dojoType="dijit.form.NumberTextBox" 
                id="acceptedWorkCommandUnitAmount" name="acceptedWorkCommandUnitAmount"
                readonly 
                style="width:100px;<?php if (! $showGlobalCurrency) echo 'display:none;'?>"
                class="input"  value="<?php echo $unitAmount;?>">  
               </input> 
               <?php if ($currencyPosition=='after') echo $currency;?>
               <?php if ($hasLocalCurrency) {?>
               <?php if ($currencyPositionLocal=='before') echo $currencyLocal;?>
                 <input dojoType="dijit.form.NumberTextBox" 
                  id="acceptedWorkCommandUnitAmountLocal" name="acceptedWorkCommandUnitAmountLocal"
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
               <label for="acceptedWorkCommandQuantity" ><?php echo i18n("colQuantity");?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
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
                    id="acceptedWorkCommandCommand" name="acceptedWorkCommandCommand"
                    style="width:100px;"  readOnly
                    class="input"  value="<?php echo $qt1;?>">
                    <?php echo $keyDownEventScript;?>  
                 </div>
               </td>
                <td>
                 <div dojoType="dijit.form.NumberTextBox" 
                    id="acceptedWorkCommandDone" name="acceptedWorkCommandDone"
                    style="width:100px;"  readOnly
                    class="input"  value="<?php echo $qt2;?>">
                    <?php echo $keyDownEventScript;?>  
                 </div>
               </td>
               <td>
                 <div dojoType="dijit.form.NumberTextBox" 
                    id="acceptedWorkCommandAccepted" name="acceptedWorkCommandAccepted"
                    style="width:100px;"  readOnly
                    class="input"  value="<?php echo $qt4;?>">
                    <?php echo $keyDownEventScript;?>  
                 </div>
               </td>
               <td>
                 <div dojoType="dijit.form.NumberTextBox" 
                    id="acceptedWorkCommandBilled" name="acceptedWorkCommandBilled"
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
               <label for="acceptedWorkCommandQuantityAccepted" ><?php echo i18n("colAcceptedQuantity");?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
             </td>
             <td>
               <div dojoType="dijit.form.NumberTextBox" 
                  id="acceptedWorkCommandQuantityAccepted" name="acceptedWorkCommandQuantityAccepted"
                  style="width:100px;border-left:3px solid red !important;" required="required"  constraints="{min:0.01}"
                  onChange="acceptedWorkCommandChangeQuantity('<?php echo $mode;?>','<?php echo $id;?>');"  <?php if($mode!='edit'){?>readOnly<?php }?>
                  class="input"  value="<?php echo $quantity;?>">
                  <?php echo $keyDownEventScript;?>  
               </div>
             </td>
            </tr>
            <tr>
             <td class="dialogLabel" >
               <label for="acceptedWorkCommandAmount" ><?php echo i18n("colAmount");?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
             </td>
             <td>
             <?php if ($currencyPosition=='before') echo $currency;?>
               <input dojoType="dijit.form.NumberTextBox" 
                id="acceptedWorkCommandAmount" name="acceptedWorkCommandAmount"
                readonly 
                style="width:100px;<?php if (! $showGlobalCurrency) echo 'display:none;'?>"
                class="input"  value="<?php echo $totalAmount;?>">  
               </input> 
               <?php if ($currencyPosition=='after') echo $currency;?>
               <?php if ($hasLocalCurrency) {?>
               <?php if ($currencyPositionLocal=='before') echo $currencyLocal;?>
                 <input dojoType="dijit.form.NumberTextBox" 
                  id="acceptedWorkCommandAmountLocal" name="acceptedWorkCommandAmountLocal"
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
        <input type="hidden" id="AcceptedWorkCommandAction">
        <button class="mediumTextButton" dojoType="dijit.form.Button" type="button" onclick="dijit.byId('dialogAcceptedWorkCommand').hide();">
          <?php echo i18n("buttonCancel");?>
        </button>
        <button class="mediumTextButton" dojoType="dijit.form.Button" type="submit" id="dialogAcceptedWorkCommandSubmit" onclick="protectDblClick(this);saveAcceptedWorkCommand();return false;">
          <?php echo i18n("buttonOK");?>
        </button>
      </td>
    </tr>
  </table>
