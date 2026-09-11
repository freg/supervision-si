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
$isLineMulti = RequestHandler::getValue('isLineMulti',false,null);
$idProviderOrderEdit=RequestHandler::getId('idProviderOrderEdit',false,null);
$idProviderOrder=RequestHandler::getValue('idProviderOrder',false,null);
$objectClass=RequestHandler::getValue('objectClass',false,null);
if($idProviderOrder==null){
  $idProviderOrder = $idProviderOrderEdit;
}
$idProviderTerm=RequestHandler::getValue('id',false,null);
$line="";

if($idProviderTerm){
  $line=new ProviderTerm($idProviderTerm);
}
if ($objectClass && $objectClass=='ProviderBill') {
  $providerOrder = new ProviderBill($idProviderOrder);
  $labelFrom="labelFromBill";
} else {
  $objectClass='ProviderOrder';
  $providerOrder = new ProviderOrder($idProviderOrder);
  $labelFrom="labelFromOrder";
}
$hasLocalCurrency=Project::hasProjectCurrency($providerOrder->idProject);
$currencyLocal=Project::getProjectCurrencyWithCss($providerOrder->idProject);
$currencyPositionLocal=Project::getProjectCurrencyPosition($providerOrder->idProject);
$showGlobalCurrency=$providerOrder->showGlobalCurrency();
$isLine = RequestHandler::getValue('isLine');
if(isset ($isLineMulti)){
  if($isLineMulti == false){
    $isLine = true;
  }else{
    $isLine = false;
  }
}
$conv=$providerOrder->getLocalToGlobalConversionRate();
$extraLocalClass=(! $showGlobalCurrency)?' localLabelClass ':'';
?>
  <table>
    <tr>
      <td>
       <form dojoType="dijit.form.Form" id='providerTermForm' name='providerTermForm' onSubmit="return false;">
        <input id="mode" name="mode" type="hidden" value="<?php echo $mode;?>" />
        <input id="conversionRate" name="conversionRate" type="hidden" value="<?php echo $conv;?>" />
        <input id="providerTermObjectClass" name="providerTermObjectClass" type="hidden" value="<?php echo $objectClass;?>" />
        <input id="providerOrderProject" name="providerOrderProject" type="hidden" value="<?php echo $providerOrder->idProject;?>" />
        <input id="providerOrderId" name="providerOrderId" type="hidden" value="<?php echo $providerOrder->id;?>" />
        <input id="providerOrderIsLine" name="providerOrderIsLine" type="hidden" value="<?php echo $isLine;?>" />
        <?php if($mode=='edit'){ ?>  <input id="idProviderTerm" name="idProviderTerm" type="hidden" value="<?php echo $idProviderTerm;?>" />  <?php } ?>
         <table>
           <tr>
             <td class="dialogLabel" >
              <label for="providerTermName" ><?php echo i18n("colName");?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
             </td>
             <td>
              <input dojoType="dijit.form.TextBox" 
	          id="providerTermName" name="providerTermName"
	          style="width: 400px;"
	          maxlength="100"
	          <?php $name=($line and $line->name)?$line->name:$providerOrder->name;?>
	          class="input required" value="<?php echo $name;?>" />
	         </td>
	        </tr>
	        
          <tr>
            <td class="dialogLabel" >
               <label for="providerTermDate" ><?php echo i18n("colDate");?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
            </td>
            <td>
               <div id="providerTermDate" name="providerTermDate"
                dojoType="dijit.form.DateTextBox" required="true" hasDownArrow="false"   
                constraints="{datePattern:browserLocaleDateFormatJs}"
                onChange="providerTermLineChangeNumber();"
                <?php if (isset($readOnly['startDate'])) echo " readonly ";?>
                type="text" maxlength="10"  style="width:100px; text-align: center;" class="input required"
                missingMessage="<?php echo i18n('messageMandatory',array('colDate'));?>" 
                invalidMessage="<?php echo i18n('messageMandatory',array('colDate'));?>" 
                value="">
               </div>
            </td>
          </tr>
          <tr>
            <td class="dialogLabel" >
              <label for="providerTermOrderUntaxedAmount" ><?php echo i18n("colUntaxedAmount");?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
            </td>
            <td>
            <?php if ($currencyPosition=='before' and $showGlobalCurrency) echo $currency;?>
              <input dojoType="dijit.form.NumberTextBox" 
                    id="providerTermOrderUntaxedAmountInit" name="providerTermOrderUntaxedAmountInit"
                    readonly constraints="{places:2}"
                    style="width:100px;<?php if (! $showGlobalCurrency) echo 'display:none;'?>"
                    value="<?php echo $providerOrder->untaxedAmount;?>"
                    class="input">
              </input> 
              <?php if ($currencyPosition=='after' and $showGlobalCurrency) echo $currency;?>
   
              <?php if ($hasLocalCurrency) {?>
              <?php if ($currencyPositionLocal=='before') echo $currencyLocal;?>
              <input dojoType="dijit.form.NumberTextBox" 
                    id="providerTermOrderUntaxedAmountInitLocal" name="providerTermOrderUntaxedAmountInitLocal"
                    readonly constraints="{places:2}"
                    style="width:100px;"
                    value="<?php echo $providerOrder->untaxedAmountLocal;?>"
                    class="input localFieldClass">
              </input> 
              <?php if ($currencyPositionLocal=='after') echo $currencyLocal;?>
               <?php }?>
              <?php  echo ' ('.i18n("colUntaxedAmount")." ".i18n($labelFrom).')';?>
            </td>
          </tr>
           <tr>
           <td class="dialogLabel" >
              <label for="providerTermDiscount" ><?php echo i18n("colDiscountRate");?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
           </td>
           <td>
               <input dojoType="dijit.form.NumberTextBox" 
                id="providerTermDiscount" name="providerTermDiscount"
                readonly 
                style="width:100px;"
                value="<?php echo $providerOrder->discountRate;?>"
                class="input">
               </input> 
               <?php  echo '%';?>
               <?php  echo ' ('.i18n("colDiscountRate")." ".i18n($labelFrom).')';?>
           </td>
          </tr>
          <tr>
            <td class="dialogLabel" >
              <label for="providerTermOrderUntaxedAmount" ><?php echo i18n("colTotalUntaxedAmount");?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
            </td>
            <td>
            <?php if ($currencyPosition=='before' and $showGlobalCurrency) echo $currency;?>
              <input dojoType="dijit.form.NumberTextBox" 
                    id="providerTermOrderUntaxedAmount" name="providerTermOrderUntaxedAmount"
                    readonly constraints="{places:2}"
                    style="width:100px;<?php if (! $showGlobalCurrency) echo 'display:none;'?>"
                    value="<?php echo $providerOrder->totalUntaxedAmount;?>"
                    class="input">
              </input> 
              <?php if ($currencyPosition=='after' and $showGlobalCurrency) echo $currency;?>
              
              <?php if ($hasLocalCurrency) {?>
              <?php if ($currencyPositionLocal=='before') echo $currencyLocal;?>
              <input dojoType="dijit.form.NumberTextBox" 
                    id="providerTermOrderUntaxedLocal" name="providerTermOrderUntaxedLocal"
                    readonly constraints="{places:2}"
                    style="width:100px;"
                    value="<?php echo $providerOrder->totalUntaxedAmountLocal;?>"
                    class="input localFieldClass">
              </input> 
              <?php if ($currencyPositionLocal=='after') echo $currencyLocal;?>
               <?php }?>
               
              <?php  echo ' ('.i18n("colTotalUntaxedAmount")." ".i18n($labelFrom).')';?>
            </td>
          </tr>
          <tr>
            <td class="dialogLabel" >
              <label for="providerTermTax" ><?php echo i18n("colTaxPct");?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
           </td>
           <td>
               <input dojoType="dijit.form.NumberTextBox" 
                id="providerTermTax" name="providerTermTax"
                readonly 
                style="width:100px;"
                value="<?php echo $providerOrder->taxPct;?>"
                class="input">
               </input> 
               <?php  echo '%';?>
               <?php  echo ' ('.i18n("colTaxPct")." ".i18n($labelFrom).')';?>
           </td>
         </tr>
          <tr>
            <td class="dialogLabel" >
              <label for="providerTermOrderFullAmount" ><?php echo i18n("colTotalFullAmount");?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
            </td>
            <td>
              <?php if ($currencyPosition=='before' and $showGlobalCurrency) echo $currency;?>
              <input dojoType="dijit.form.NumberTextBox" 
                    id="providerTermOrderFullAmount" name="providerTermOrderFullAmount"
                    readonly  constraints="{places:2}"
                    style="width:100px;<?php if (! $showGlobalCurrency) echo 'display:none;'?>"
                    value="<?php echo $providerOrder->totalFullAmount;?>"
                    class="input">
              </input> 
              <?php if ($currencyPosition=='after' and $showGlobalCurrency) echo $currency;?>
                   
              <?php if ($hasLocalCurrency) {?>
              <?php if ($currencyPositionLocal=='before') echo $currencyLocal;?>
              <input dojoType="dijit.form.NumberTextBox" 
                    id="providerTermOrderFullAmountLocal" name="providerTermOrderFullAmountLocal"
                    readonly constraints="{places:2}"
                    style="width:100px;"
                    value="<?php echo $providerOrder->totalFullAmountLocal;?>"
                    class="input localFieldClass">
              </input> 
              <?php if ($currencyPositionLocal=='after') echo $currencyLocal;?>
              <?php }?>
               
              <?php  echo ' ('.i18n("colTotalFullAmount")." ".i18n($labelFrom).')';?>
            </td>
          </tr>
          <?php 
          $maxValue = $providerOrder->totalUntaxedAmount;
          $alreadyOnTerms=0;
          $alreadyOnTermsHT=0;
          $maxValueLocal = $providerOrder->totalUntaxedAmountLocal;
          $alreadyOnTermsLocal=0;
          $alreadyOnTermsHTLocal=0;
          $providerTerm = new ProviderTerm();
          $termList=$providerTerm->getSqlElementsFromCriteria(array("id".$objectClass=>$providerOrder->id));
          foreach ($termList as $term) {
            $maxValue -= $term->untaxedAmount ;
            $alreadyOnTerms+=$term->fullAmount;
            $alreadyOnTermsHT+=$term->untaxedAmount;
            $maxValueLocal -= $term->untaxedAmountLocal ;
            $alreadyOnTermsLocal+=$term->fullAmountLocal;
            $alreadyOnTermsHTLocal+=$term->untaxedAmountLocal;
          }
          if($mode == 'edit'){
            $providerTermEdit = new ProviderTerm($idProviderTerm);    
            $NewMaxValue = $maxValue+$providerTermEdit->untaxedAmount;
            $NewMaxValueLocal = $maxValueLocal+$providerTermEdit->untaxedAmountLocal;
          }
          $percent = (floatval($providerOrder->totalUntaxedAmount))?(100*$maxValue/$providerOrder->totalUntaxedAmount):0;
          $taxAmount = ($maxValue*$providerOrder->taxPct)/100;
          $taxAmountLocal = ($maxValueLocal*$providerOrder->taxPct)/100;
          $totalFullAmount = $maxValue+$taxAmount;
          $totalFullAmountLocal = $maxValueLocal+$taxAmountLocal;
          if($mode == 'edit'){
            $MaxPercent = $percent;
            $percent = (floatval($providerOrder->totalUntaxedAmount))?(100*$providerTermEdit->untaxedAmount/$providerOrder->totalUntaxedAmount):0;
            $MaxPercent += $percent;
            $taxAmount = $providerTermEdit->taxAmount;
            $totalFullAmount = $providerTermEdit->untaxedAmount+$taxAmount;
            $taxAmountLocal = $providerTermEdit->taxAmountLocal;
            $totalFullAmountLocal = $providerTermEdit->untaxedAmountLocal+$taxAmountLocal;
          }?>
          <?php if ($mode!='edit') {?>
             <tr>
              <td class="dialogLabel" >
                <label for="providerTermSum" ><?php echo i18n("fullAmountOfTerms");?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
              </td>
              <td style="white-space:nowrap">
                <?php if ($currencyPosition=='before' and $showGlobalCurrency) echo $currency;?>
                <input dojoType="dijit.form.NumberTextBox" 
                      id="" name=""
                      readonly  constraints="{places:2}"
                      style="width:100px;<?php if (! $showGlobalCurrency) echo 'display:none;'?>"
                      value="<?php echo $alreadyOnTerms?>"
                      class="input">
                </input> 
                <?php if ($currencyPosition=='after' and $showGlobalCurrency) echo $currency;?>
                
              <?php if ($hasLocalCurrency) {?>
              <?php if ($currencyPositionLocal=='before') echo $currencyLocal;?>
              <input dojoType="dijit.form.NumberTextBox" 
                    id="" name=""
                    readonly constraints="{places:2}"
                    style="width:100px;"
                    value="<?php echo $alreadyOnTermsLocal;?>"
                    class="input localFieldClass">
              </input> 
              <?php if ($currencyPositionLocal=='after') echo $currencyLocal;?>
              <?php }?>
              
              <?php  echo ' ('.i18n("labelFullAmountOfTerms").')';?>
              </td>
            </tr>
          <?php }?>
          </table>
          <?php 
          if($isLine=='false'){
          ?> 
          <br/>
          
          <table style="margin:auto;<?php if ($mode!='edit' and ($alreadyOnTerms>=$providerOrder->totalFullAmount or $alreadyOnTermsHT>=$providerOrder->totalUntaxedAmount)) echo 'display:none;';?>">
          <tr>
            <td colspan="5" class="assignHeader"><?php echo i18n("colTermDetail");?></td>
          
          </tr>
          <tr>
            <td class="assignHeader" style="<?php if ($mode=='edit') echo 'display:none;';?>"><?php echo i18n("colNumberOfTerms");?></td>
            <td class="assignHeader"><?php echo i18n("colUntaxedAmount");?></td>
            <td class="assignHeader" ><?php echo i18n("colRate");?></td>
            <td class="assignHeader" ><?php echo i18n("colTaxAmount");?></td>
            <td class="assignHeader" ><?php echo i18n("colFullAmount");?></td>
          </tr>
          <tr>
           <td class="assignData" style="padding-top:0;padding-bottom:0;text-align:center;<?php if ($mode=='edit') echo 'display:none;';?>"> 
             <div dojoType="dijit.form.NumberTextBox" 
                id="providerTermNumberOfTerms" name="providerTermNumberOfTerms"
                constraints="{min:0,max:999,places:0}"
                style="width:50px;<?php if ($mode=='edit') echo 'display:none;';?>"
                value="1" 
                <?php if ($alreadyOnTerms>0) echo 'readonly';?>
                <?php if ($mode!='edit') echo 'onChange="providerTermLineChangeNumber();"';?>
                class="input">
             </div> 
           </td>
           <td class="assignData" style="padding-top:0;padding-bottom:0;">
            <?php if ($currencyPosition=='before' and $showGlobalCurrency) echo $currency;?>
            <div dojoType="dijit.form.NumberTextBox" 
              id="providerTermUntaxedAmount" name="providerTermUntaxedAmount"
              style="width: 100px;<?php if (! $showGlobalCurrency) echo 'display:none;'?>"
              <?php if ($hasLocalCurrency) echo ' readonly ';?>
              constraints="{max:<?php if($mode=='edit'){echo $NewMaxValue;}else{ echo $maxValue ;}?>,places:2}"
              onChange="providerTermLine(<?php echo $providerOrder->totalUntaxedAmount; ?>);"
              value="<?php if($mode=='edit'){echo $providerTermEdit->untaxedAmount ;}else { if($providerOrder->totalUntaxedAmount){echo $maxValue;}}?>" 
              class="input"
              <?php echo $keyDownEventScript;?>
            </div>
            <?php if ($currencyPosition=='after' and $showGlobalCurrency) echo $currency;?>
            <?php if ($showGlobalCurrency and $hasLocalCurrency) echo '<br/>'?>
            <?php if ($hasLocalCurrency) {?>
             <?php if ($currencyPositionLocal=='before') echo $currencyLocal;?>
            <div dojoType="dijit.form.NumberTextBox" 
              id="providerTermUntaxedAmountLocal" name="providerTermUntaxedAmountLocal"
              style="width: 100px;"
              constraints="{max:<?php if($mode=='edit'){echo $NewMaxValueLocal;}else{ echo $maxValueLocal ;}?>,places:2}"
              onChange="providerTermLineLocal(<?php echo $providerOrder->totalUntaxedAmountLocal; ?>);"
              value="<?php if($mode=='edit'){echo $providerTermEdit->untaxedAmountLocal ;}else { if($providerOrder->totalUntaxedAmountLocal){echo $maxValueLocal;}}?>" 
              class="input localFieldClass"
              <?php echo $keyDownEventScript;?>
            </div>
            <?php if ($currencyPositionLocal=='after') echo $currencyLocal;?>
            <?php }?> 
           </td>
           <td class="assignData" style="padding-top:0;padding-bottom:0;">
            <div dojoType="dijit.form.NumberTextBox" 
              id="providerTermPercent" name="providerTermPercent"
              style="width: 100px;"
              constraints="{max:<?php if($mode=='edit'){echo $MaxPercent+0.01;}else{echo $percent+0.01;}?>}"
              onChange="providerTermLinePercent(<?php echo $providerOrder->totalUntaxedAmount.",".(($providerOrder->totalUntaxedAmountLocal)??0); ?>);"
              value="<?php echo $percent;?>" 
              class="input"
              <?php echo $keyDownEventScript;?>
            </div>
            <?php echo '%';?>
           </td>
           <td class="assignData" style="padding-top:0;padding-bottom:0;">
               <?php if ($currencyPosition=='before' and $showGlobalCurrency) echo $currency;?>
               <input dojoType="dijit.form.NumberTextBox" 
                id="providerTermTaxAmount" name="providerTermTaxAmount"
                readonly  constraints="{places:2}"
                style="width:100px;<?php if (! $showGlobalCurrency) echo 'display:none;'?>"
                value="<?php echo $taxAmount;?>" 
                class="input"  >  
               </input> 
               <?php if ($currencyPosition=='after' and $showGlobalCurrency) echo $currency;?>
               
               <?php if ($showGlobalCurrency and $hasLocalCurrency) echo '<br/>'?>
               <?php if ($hasLocalCurrency) {?>
               <?php if ($currencyPositionLocal=='before') echo $currencyLocal;?>
               <input dojoType="dijit.form.NumberTextBox" 
                id="providerTermTaxAmountLocal" name="providerTermTaxAmountLocal"
                readonly  constraints="{places:2}"
                style="width:100px;"
                value="<?php echo $taxAmountLocal;?>" 
                class="input localFieldClass"  >  
               </input>
               <?php if ($currencyPositionLocal=='after') echo $currencyLocal;?>
               <?php }?> 
            </td>
            <td class="assignData" style="padding-top:0;padding-bottom:0;">
               <?php if ($currencyPosition=='before' and $showGlobalCurrency) echo $currency;?>
               <input dojoType="dijit.form.NumberTextBox" 
                id="providerTermFullAmount" name="providerTermFullAmount"
                readonly constraints="{places:2}"
                style="width:100px;<?php if (! $showGlobalCurrency) echo 'display:none;'?>"
                value="<?php echo $totalFullAmount; ?>" 
                class="input">  
               </input> 
               <?php if ($currencyPosition=='after' and $showGlobalCurrency) echo $currency;?>
               
               <?php if ($showGlobalCurrency and $hasLocalCurrency) echo '<br/>'?>
               <?php if ($hasLocalCurrency) {?>
               <?php if ($currencyPositionLocal=='before') echo $currencyLocal;?>
               <input dojoType="dijit.form.NumberTextBox" 
                id="providerTermFullAmountLocal" name="providerTermFullAmountLocal"
                readonly constraints="{places:2}"
                style="width:100px;"
                value="<?php echo $totalFullAmountLocal; ?>" 
                class="input localFieldClass">  
               </input> 
               <?php if ($currencyPositionLocal=='after') echo $currencyLocal;?>
               <?php }?> 
          </td>
	        </tr>
	        <tr><td colspan="5" style="text-align:center"><div id="labelRegularTerms"></div></td></tr>
	        
	         <?php 
           }else{ 
	           $billLine = new BillLine();
	           $billLineList=$billLine->getSqlElementsFromCriteria(array("refType"=>$objectClass,"refId"=>$providerOrder->id));
	           $i = 0;
	         ?> 
	          <br/>
	          <table>
	           <tr>
	             <td class="assignHeader" colspan="4"><?php echo i18n('labelBillLinesFromOrder');?></td>
	             <td class="assignHeader" colspan="5"><?php echo i18n('labelPartToTerm');?></td>
	           </tr >
	           <tr >
	            <td class="assignHeader"  style="width:50px;" >
                <?php echo i18n("colLineNumber");?>
              </td>
              <td class="assignHeader" style="width:180px;" >
                <?php echo i18n("colDescription");?>
              </td>
              <td class="linkHeader"   style="width:180px;">
                <?php echo i18n("colDetail");?>
              </td>
              <td class="assignHeader" style="width:115px;" >
                <?php echo i18n("colUntaxedAmount");?></label>
              </td>
              <td class="assignHeader" style="width:55px;">
                <?php echo i18n("colRate");?>
              </td>
              <td class="assignHeader" style="width:115px;">
                <?php echo i18n("colUntaxedAmount");?>
              </td>
              <td class="assignHeader" style="width:115px;">
               <?php echo i18n("colDiscount");?>
              </td>
              <td class="assignHeader" "style="width:115px;">
               <?php echo i18n("colTaxAmount");?>
              </td>
              <td class="assignHeader" style="width:115px;">
               <?php echo i18n("colFullAmount");?>
              </td>
             </tr>
	           <?php 
	           $style2 = 'border-left:1px solid black;border-bottom:1px solid black;white-space:nowrap;padding:0 2px;';
	           foreach ($billLineList as $bill) {  ?>
	             <?php $i++;?>
              <input id="providerOrderBillLineId<?php echo $i;?>" name="providerOrderBillLineId<?php echo $i;?>" type="hidden" value="<?php echo $bill->id;?>" />
              <?php 
                 
                $maxValue = $bill->amount;
                $maxValueLocal = $bill->amountLocal;
                $billLine2 = new BillLine();
                $critArray = array("refType"=>"ProviderTerm","idBillLine"=>$bill->id);
                $billLineList2=$billLine2->getSqlElementsFromCriteria($critArray);
                foreach ($billLineList2 as $bill2){
                  $maxValue -= $bill2->price;
                  $maxValueLocal -= $bill2->priceLocal;
                }
                if($mode != 'edit'){
                  if($maxValue==0){
                    continue;
                  }
                }
                $discount = 0;
                $discountLocal = 0;
                $percent = (floatval($bill->amount))?(100*$maxValue/$bill->amount):0;
                if($providerOrder->discountRate > 0){
                  $discount = ($maxValue*$providerOrder->discountRate/100);
                  $discountLocal = ($maxValueLocal*$providerOrder->discountRate/100);
                }
                $taxAmount = (($maxValue-$discount)*$providerOrder->taxPct)/100;
                $taxAmountLocal = (($maxValueLocal-$discountLocal)*$providerOrder->taxPct)/100;
                $totalFullAmount = $maxValue - $discount +$taxAmount;
                $totalFullAmountLocal = $maxValueLocal - $discountLocal +$taxAmountLocal;
                
                if($mode == 'edit'){
                  $discount = 0;
                  $billLine3 = new BillLine();
                  $critArray = array("refType"=>"ProviderTerm","idBillLine"=>$bill->id , "refId"=>$idProviderTerm);
                  $billLineList3=$billLine2->getSqlElementsFromCriteria($critArray);
                  $newPercent=0;
                  $newMaxValue=0;
                  $newMaxValueLocal=0;
                  foreach ($billLineList3 as $billLineTerm){
                    $newPercent = $percent;
                    $percent = $billLineTerm->rate;
                    $newPercent +=$percent; 
                    if($providerOrder->discountRate > 0){
                      $discount = ($billLineTerm->price*$providerOrder->discountRate/100);
                      $discountLocal = ($billLineTerm->priceLocal*$providerOrder->discountRate/100);
                    }
                    $taxAmount = (($billLineTerm->price-$discount)*$providerOrder->taxPct)/100;
                    $totalFullAmount = $billLineTerm->price - $discount +$taxAmount;
                    $newMaxValue = $billLineTerm->price+$maxValue;
                    $taxAmountLocal = (($billLineTerm->priceLocal-$discountLocal)*$providerOrder->taxPct)/100;
                    $totalFullAmountLocal = $billLineTerm->priceLocal - $discountLocal +$taxAmountLocal;
                    $newMaxValueLocal = $billLineTerm->priceLocal+$maxValueLocal;
                  }
                }
              ?>
               <tr>
                 <td style="width:50px; <?php echo $style2;?> ">
  		            <input dojoType="dijit.form.NumberTextBox" 
  			           id="providerTermBillLineLine<?php echo $i;?>" name="providerTermBillLineLine<?php echo $i;?>"
  			           style="width:40px;"
  			           class="display"
  			           value="<?php echo $bill->line;?>" />
  		           </td>
                 <td style="<?php echo $style2;?> ">
                  <textarea dojoType="dijit.form.Textarea" 
        	         id="billLineDescription<?php echo $i;?>" name="billLineDescription<?php echo $i;?>"
        	         style="width: 180px;"
        	         maxlength="200" class="display"
        	         ><?php echo $bill->description;?></textarea>
    	           </td>
                 <td style="<?php echo $style2;?> ">
                  <textarea dojoType="dijit.form.Textarea" 
      	           id="billLineDetail<?php echo $i;?>" name="billLineDetail<?php echo $i;?>"
      	           style="width: 180px;"
      	           maxlength="200" class="display"
      	           ><?php echo $bill->detail;?></textarea>  
      	         </td> 
                 <td style="<?php echo $style2;?> ">
                  <?php if ($currencyPosition=='before' and $showGlobalCurrency) echo $currency;?>
                  <div dojoType="dijit.form.NumberTextBox" 
                    id="providerTermBillLineUntaxed<?php echo $i;?>" name="providerTermBillLineUntaxed<?php echo $i;?>"
                    style="width: 100px;<?php if (! $showGlobalCurrency) echo 'display:none;'?>"
                    value="<?php echo $bill->amount ;?>" 
                    readonly
                    class="input readonly"
                    <?php echo $keyDownEventScript;?>
                  </div>
                  <?php if ($currencyPosition=='after' and $showGlobalCurrency) echo $currency;?>
                  
                  <?php if ($showGlobalCurrency and $hasLocalCurrency) echo '<br/>'?>
                 <?php if ($hasLocalCurrency) {?>
                 <?php if ($currencyPositionLocal=='before') echo $currencyLocal;?>
                 <div dojoType="dijit.form.NumberTextBox" 
                  id="providerTermBillLineUntaxedLocal<?php echo $i;?>" name="providerTermBillLineUntaxedLocal<?php echo $i;?>"
                  style="width:100px;"
                  value="<?php echo $bill->amountLocal ;?>" 
                  readonly
                  class="input localFieldClass">  
                  <?php echo $keyDownEventScript;?>
                 </div> 
                 <?php if ($currencyPositionLocal=='after') echo $currencyLocal;?>
                 <?php }?> 
                  
                 </td>
                 <td style="<?php echo $style2;?> ">
                  <div dojoType="dijit.form.NumberTextBox" 
                    id="providerTermPercent<?php echo $i;?>" name="providerTermPercent<?php echo $i;?>"
                    style="width:35px;"
                    constraints="{max:<?php if($mode=='edit'){
                                              echo $newPercent;
                                            }else{
                                              echo $percent;}?>}"
                    value="<?php echo $percent;?>" 
                     onChange="providerTermLinePercentBilleLine(<?php echo $i; ?>);"
                    class="input"
                    <?php echo $keyDownEventScript;?>
                  </div>
                  <?php echo '%';?>
                 </td>
                 <td style="<?php echo $style2;?> ">
                  <?php if ($currencyPosition=='before' and $showGlobalCurrency) echo $currency;?>
                  <div dojoType="dijit.form.NumberTextBox" 
                    id="providerTermUntaxedAmount<?php echo $i;?>" name="providerTermUntaxedAmount<?php echo $i;?>"
                    style="width: 100px;<?php if (! $showGlobalCurrency) echo 'display:none;'?>"
                    constraints="{max:<?php if($mode=='edit'){
                                              echo $newMaxValue;
                                            }else{
                                              echo $maxValue;}?>}"
                    <?php if ($hasLocalCurrency) echo "readonly";?>
                    value="<?php if($mode=='edit'){
                                  echo $billLineTerm->price;
                                 }else{
                                  echo $maxValue;}?>" 
                                                      
                    class="input"
                    onChange="providerTermLineBillLine(<?php echo $i; ?>);"
                    <?php echo $keyDownEventScript;?>
                  </div>
                  <?php if ($currencyPosition=='after' and $showGlobalCurrency) echo $currency;?>
                  
                  <?php if ($showGlobalCurrency and $hasLocalCurrency) echo '<br/>'?>
                  <?php if ($hasLocalCurrency) {?>
                  <?php if ($currencyPositionLocal=='before') echo $currencyLocal;?>
                  <div dojoType="dijit.form.NumberTextBox" 
                    id="providerTermUntaxedAmountLocal<?php echo $i;?>" name="providerTermUntaxedAmountLocal<?php echo $i;?>"
                    style="width: 100px;"
                    constraints="{max:<?php if($mode=='edit'){
                                              echo $newMaxValueLocal;
                                            }else{
                                              echo $maxValueLocal;}?>}"
                    value="<?php if($mode=='edit'){
                                  echo $billLineTerm->priceLocal;
                                 }else{
                                  echo $maxValueLocal;}?>" 
                                                      
                    class="input localFieldClass"
                    onChange="providerTermLineBillLine(<?php echo $i; ?>);"
                    <?php echo $keyDownEventScript;?>
                  </div>
                  <?php if ($currencyPositionLocal=='after') echo $currencyLocal;?>
                  <?php }?> 
                 </td>
              <td style="<?php echo $style2;?> ">
               <?php if ($currencyPosition=='before' and $showGlobalCurrency) echo $currency;?>
                 <input dojoType="dijit.form.NumberTextBox" 
                  id="providerTermDiscountAmount<?php echo $i;?>" name="providerTermDiscountAmount<?php echo $i;?>"
                  style="width:100px;<?php if (! $showGlobalCurrency) echo 'display:none;'?>"
                  value="<?php echo $discount;?>" 
                  readonly
                  class="input"  >  
                 </input> 
               <?php if ($currencyPosition=='after' and $showGlobalCurrency) echo $currency;?>
               <?php if ($showGlobalCurrency and $hasLocalCurrency) echo '<br/>'?>
               <?php if ($hasLocalCurrency) {?>
               <?php if ($currencyPositionLocal=='before') echo $currencyLocal;?>
                <input dojoType="dijit.form.NumberTextBox" 
                  id="providerTermDiscountAmountLocal<?php echo $i;?>" name="providerTermDiscountAmountLocal<?php echo $i;?>"
                  style="width:100px;"
                  value="<?php echo $discountLocal;?>" 
                  readonly
                  class="input localFieldClass"  >  
                 </input>   
               <?php if ($currencyPositionLocal=='after') echo $currencyLocal;?>
               <?php }?> 
              </td>         
             <td style="<?php echo $style2;?> ">
                 <?php if ($currencyPosition=='before' and $showGlobalCurrency) echo $currency;?>
                   <input dojoType="dijit.form.NumberTextBox" 
                    id="providerTermTaxAmount<?php echo $i;?>" name="providerTermTaxAmount<?php echo $i;?>"
                    class="input"
                    readonly
                    style="width:100px;<?php if (! $showGlobalCurrency) echo 'display:none;'?>"
                    value="<?php echo $taxAmount;?>" 
                     >  
                   </input> 
                   <?php if ($currencyPosition=='after' and $showGlobalCurrency) echo $currency;?>
                   
                  <?php if ($showGlobalCurrency and $hasLocalCurrency) echo '<br/>'?>
                  <?php if ($hasLocalCurrency) {?>
                  <?php if ($currencyPositionLocal=='before') echo $currencyLocal;?>
                    <input dojoType="dijit.form.NumberTextBox" 
                    id="providerTermTaxAmountLocal<?php echo $i;?>" name="providerTermTaxAmountLocal<?php echo $i;?>"
                    class="input localFieldClass"
                    readonly
                    style="width:100px;"
                    value="<?php echo $taxAmountLocal;?>" 
                     >  
                   </input>                  
                  <?php if ($currencyPositionLocal=='after') echo $currencyLocal;?>
                  <?php }?> 
              </td>
             <td style="<?php echo $style2;?>  border-right:1px solid black;">
             <?php if ($currencyPosition=='before' and $showGlobalCurrency) echo $currency;?>
               <input dojoType="dijit.form.NumberTextBox" 
                id="providerTermFullAmount<?php echo $i;?>" name="providerTermFullAmount<?php echo $i;?>"
                class="input"
                readonly
                style="width:100px;<?php if (! $showGlobalCurrency) echo 'display:none;'?>"
                value="<?php echo $totalFullAmount; ?>" 
                >  
               </input> 
               <?php if ($currencyPosition=='after' and $showGlobalCurrency) echo $currency;?>
               
               <?php if ($showGlobalCurrency and $hasLocalCurrency) echo '<br/>'?>
               <?php if ($hasLocalCurrency) {?>
               <?php if ($currencyPositionLocal=='before') echo $currencyLocal;?>
              <input dojoType="dijit.form.NumberTextBox" 
                id="providerTermFullAmountLocal<?php echo $i;?>" name="providerTermFullAmountLocal<?php echo $i;?>"
                class="input localFieldClass"
                readonly
                style="width:100px;"
                value="<?php echo $totalFullAmountLocal; ?>" 
                >  
               </input> 
               <?php if ($currencyPositionLocal=='after') echo $currencyLocal;?>
               <?php }?> 
          </td>
                 
                 </tr>
      	   <?php }
      	        } ?>
         </table>
        </form>
      </td>
    </tr>
    <tr><td>&nbsp;</td></tr>
    <tr>
      <td align="center">
        <input type="hidden" id="providerTermAction">
        <button class="mediumTextButton" dojoType="dijit.form.Button" type="button" onclick="dijit.byId('dialogProviderTerm').hide();">
          <?php echo i18n("buttonCancel");?>
        </button>
        <button class="mediumTextButton" dojoType="dijit.form.Button" type="submit" id="dialogProviderTermSubmit" onclick="protectDblClick(this);saveProviderTerm();return false;">
          <?php echo i18n("buttonOK");?>
        </button>
      </td>
    </tr>
  </table>
