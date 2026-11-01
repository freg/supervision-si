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
require_once "../tool/projeqtor.php";
scriptLog('dynamicDialogExpenseDetail.php');

$id=RequestHandler::getId('id');
$refType=RequestHandler::getClass("refType");
$refId=RequestHandler::getId("refId");
$expenseType=RequestHandler::getAlphanumeric('expenseType');

if (!$refType or !$refId) {
  traceLog("call dynamicDialogExpenseDetail.php without refType and refId");
  exit;
}

$obj=new $refType($refId);    
$line=new ExpenseDetail($id); 

$currency=Parameter::getGlobalParameter('currency');
$currencyPosition=Parameter::getGlobalParameter('currencyPosition');
$hasLocalCurrency=Project::hasProjectCurrency($obj->idProject);
$currencyLocal=Project::getProjectCurrencyWithCss($obj->idProject);
$currencyPositionLocal=Project::getProjectCurrencyPosition($obj->idProject);
$showGlobalCurrency=$obj->showGlobalCurrency();
$keyDownEventScript=NumberFormatter52::getKeyDownEvent();
$readOnly=array();
?>

<table>
<tr>
<td>
<form dojoType="dijit.form.Form" id='expenseDetailForm' jsid='expenseDetailForm' name='expenseDetailForm' onSubmit="return false;">
<input id="expenseDetailId" name="expenseDetailId" type="hidden" value="<?php echo $id;?>" />
<input id="idExpense" name="idExpense" type="hidden" value="<?php echo $refId;?>" />
<table>
<tr>
<td class="dialogLabel" >
<label for="expenseDetailDate" ><?php echo i18n("colDate");?>&nbsp;:&nbsp;</label>
             </td>
             <td>
             
               <div id="expenseDetailDate" name="expenseDetailDate"
                 dojoType="dijit.form.DateTextBox" 
                 constraints="{datePattern:browserLocaleDateFormatJs}"
                 invalidMessage="<?php echo i18n('messageInvalidDate');?> " 
                 type="text" maxlength="10" 
                 style="width:100px; text-align: center;" class="input"
                 required="false"
                 hasDownArrow="true"
                 value="<?php echo $line->expenseDate;?>"
                 missingMessage="<?php echo i18n('messageMandatory',array('colDate'));?>" 
                 invalidMessage="<?php echo i18n('messageMandatory',array('colDate'));?>" 
                 >
             </div>
             </td>
           </tr>
           <tr>
             <td class="dialogLabel" >
               <label for="expenseDetailReference" ><?php echo i18n("colReference");?>&nbsp;:&nbsp;</label>
             </td>
             <td>
               <div id="expenseDetailReference" name="expenseDetailReference" value="<?php echo $line->externalReference;?>" 
                 dojoType="dijit.form.TextBox" class="input"
                 style="width:200px" 
                 required="false"             
               ></div>
             </td>
           </tr>
           <tr>
             <td class="dialogLabel" >
               <label for="expenseDetailName" ><?php echo i18n("colName");?>&nbsp;:&nbsp;</label>
             </td>
             <td>
               <input id="expenseDetailName" name="expenseDetailName"
                 dojoType="dijit.form.TextBox" class="input required"
                 style="width:400px" 
                 required="true" 
                 value="<?php echo $line->name;?>"
                 missingMessage="<?php echo i18n('messageMandatory',array('colName'));?>" 
                 invalidMessage="<?php echo i18n('messageMandatory',array('colName'));?>"              
               />
             </td>
           </tr>
 
           <tr>
             <td class="dialogLabel" >
               <label for="expenseDetailType" ><?php echo i18n("colType");?>&nbsp;:&nbsp;</label>
             </td>
             <td>
              <select dojoType="dijit.form.FilteringSelect" 
              <?php echo autoOpenFilteringSelect();?>
                id="expenseDetailType" name="expenseDetailType"
                style="width:200px" 
                class="input" 
                value="<?php echo ($line->idExpenseDetailType)?$line->idExpenseDetailType:' ';?>" 
                onChange="expenseDetailTypeChange();" >                
                 <?php htmlDrawOptionForReference('idExpenseDetailType', null, null, false);?>            
               </select>  
             </td>
           </tr>
           <tr>
            <td colspan="2">
              <div id="expenseDetailDiv" dojoType="dijit.layout.ContentPane" region="center" >    
              </div>
            </td> 
           </tr>
           
           <?php $extraLocalClass=(! $showGlobalCurrency)?' localLabelClass ':'';?>
           <tr>
             <td class="dialogLabel" >
               <label for="expenseDetailAmount" class="<?php echo $extraLocalClass;?>"><?php echo i18n("colAmount");?>&nbsp;:&nbsp;</label>
             </td>
             <td>
               <?php echo ($currencyPosition=='before'  and $showGlobalCurrency)?$currency:''; ?>
               <div id="expenseDetailAmount" name="expenseDetailAmount"
                 dojoType="dijit.form.NumberTextBox" class="input <?php if (!$hasLocalCurrency) echo 'required';?>"
                 constraints="{places:2}"
                 style="width:97px;<?php if (! $showGlobalCurrency) echo 'display:none;'?>"
                 <?php if ($hasLocalCurrency) echo ' readonly ';?>
                 value="<?php echo $line->amount;?>" 
                 onChange="var localValue=calculateAmountFromConvertion(this.value,<?php echo $obj->getGlobalToLocalConversionRate();?>,'expenseDetailAmountLocal');"	          
                  >
                 <?php echo $keyDownEventScript;?>
                 </div>
               <?php echo ($currencyPosition=='after'  and $showGlobalCurrency)?$currency:'';?>
               
               <?php if ($hasLocalCurrency) {?>
               &nbsp;&nbsp;
               <?php if ($currencyPositionLocal=='before') echo $currencyLocal;?>
               <div id="expenseDetailAmountLocal" name="expenseDetailAmountLocal"
                 dojoType="dijit.form.NumberTextBox" class="input required localFieldClass"
                 constraints="{places:2}"
                 style="width:97px"
                 value="<?php echo $line->amountLocal;?>" 
                  >
                 <?php echo $keyDownEventScript;?>
                 <?php if ($hasLocalCurrency) echo $obj->getLocalToGlobalUpdateScript('expenseDetailAmountLocal');?>
                 </div>
               <?php if ($currencyPositionLocal=='after') echo $currencyLocal;?>
               <?php }?>
             </td>
           </tr> 
         </table>
        </form>
      </td>
    </tr>
    <tr>
      <td align="center">
        <input type="hidden" id="dialogExpenseDetailAction">
        <button class="mediumTextButton" dojoType="dijit.form.Button" type="button" onclick="dijit.byId('dialogExpenseDetail').hide();">
          <?php echo i18n("buttonCancel");?>
        </button>
        <button class="mediumTextButton" dojoType="dijit.form.Button" type="submit" id="dialogExpenseDetailSubmit" onclick="protectDblClick(this);saveExpenseDetail();return false;">
          <?php echo i18n("buttonOK");?>
        </button>
      </td>
    </tr>
  </table>