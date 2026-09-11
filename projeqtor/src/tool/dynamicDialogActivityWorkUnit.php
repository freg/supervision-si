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
$visibility=(RequestHandler::isCodeSet('visibility'))?RequestHandler::getValue('visibility'):null;
$mode = RequestHandler::getValue('mode',false,null);
$id = RequestHandler::getId('id');
$obj = new Activity($id);
$idWorkUnit =(RequestHandler::isCodeSet('idWorkUnit'))? RequestHandler::getId('idWorkUnit'):null;
$idActivityWorkUnit = RequestHandler::getId('idActivityWorkUnit');
$idComplexity = RequestHandler::getId('idComplexity');
$idWorkCommand = RequestHandler::getId('idWorkCommand');
$quantity = RequestHandler::getNumeric('quantity');
$minQuantity = 0.01;
$commandAmount = RequestHandler::getNumeric('commandAmount');
$commandAmountLocal = RequestHandler::getNumeric('commandAmountLocal');
$paramEnableWorkUnit = Parameter::getGlobalParameter('enableWorkCommandManagement');

if($mode=='edit'){
  $actWorkUnit = new ActivityWorkUnit($idActivityWorkUnit);
  $idWorkUnit = $actWorkUnit->idWorkUnit;
  $idComplexity = $actWorkUnit->idComplexity;
  $quantity = $actWorkUnit->quantity;
  $idWorkCommand = $actWorkUnit->idWorkCommand;
  $complexityVal = SqlElement::getSingleSqlElementFromCriteria('ComplexityValues', array('idWorkUnit'=>$idWorkUnit,'idComplexity'=>$idComplexity));
  $commandAmount = $complexityVal->price*$quantity;
  $commandAmountLocal = $complexityVal->priceLocal*$quantity;
}

$currencyLocal=Project::getProjectCurrencyWithCss($obj->idProject);
$currencyPositionLocal=Project::getProjectCurrencyPosition($obj->idProject);
$hasLocalCurrency=Project::hasProjectCurrency($obj->idProject);
$showGlobalCurrency=$obj->showGlobalCurrency();
?>
  <table>
    <tr>
      <td>
       <form dojoType="dijit.form.Form" id='activityWorkUnitForm' name='activityWorkUnitForm' onSubmit="return false;">
        <input id="mode" name="mode" type="hidden" value="<?php echo $mode;?>" />
        <input id="id" name="id" type="hidden" value="<?php echo $id;?>" />
        <input id="idActivityWorkUnit" name="idActivityWorkUnit" type="hidden" value="<?php echo $idActivityWorkUnit;?>" />
         <table>
          <tr>
             <td class="dialogLabel"  >
               <label for="ActivityWorkCommandWorkUnit" ><?php echo i18n("colIdWorkUnit") ?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
             </td>
             <td>
               <select dojoType="dijit.form.FilteringSelect"
              <?php echo autoOpenFilteringSelect();?>
                id="ActivityWorkCommandWorkUnit" name="ActivityWorkCommandWorkUnit" <?php if($readOnly==true){?>readOnly<?php }?>
                class="input" required="required" style="border-left:3px solid red !important;"
                onChange="activityWorkUnitChangeIdWorkUnit();" 
                missingMessage="<?php echo i18n('messageMandatory',array(i18n('colIdWorkUnit')));?>" >
                 <?php htmlDrawOptionForReference('idWorkUnit',$idWorkUnit, $obj, false); ?>
               </select> 
             </td>
           </tr>
           <tr>
             <td class="dialogLabel"  >
               <label for="ActivityWorkCommandComplexity" ><?php echo i18n("colIdComplexity") ?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
             </td>
             <td>
               <select dojoType="dijit.form.FilteringSelect"
              <?php echo autoOpenFilteringSelect();?>
                id="ActivityWorkCommandComplexity" name="ActivityWorkCommandComplexity"
                class="input" required="required" style="border-left:3px solid red !important;"
                onChange="activityWorkUnitChangeIdComplexity();"  <?php if($mode!="edit"){?>readOnly<?php }?>  <?php if($mode=="edit" and $readOnly==true){?>readOnly<?php }?> 
                missingMessage="<?php echo i18n('messageMandatory',array(i18n('idComplexity')));?>" >
                 <?php 
                 if($mode!='edit'){
                    htmlDrawOptionForReference('idComplexity',$idComplexity, $obj, false,'idProject',$obj->idProject); 
                  }else{
                    htmlDrawOptionForReference('idComplexity',$idComplexity, $actWorkUnit, false,'idProject',$obj->idProject);
                  }?>
               </select> 
             </td>
           </tr>
            <tr>
             <td class="dialogLabel" >
               <label for="ActivityWorkCommandQuantity" ><?php echo i18n("colQuantity");?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
             </td>
             <td>
               <div dojoType="dijit.form.NumberTextBox" 
                  id="ActivityWorkCommandQuantity" name="ActivityWorkCommandQuantity"
                  style="width:100px;border-left:3px solid red !important;" required="required" 
                  invalidMessage="<?php echo i18n('quantityCanBeInferiorThan',$minQuantity);?>" 
                  onChange="activityWorkUnitChangeQuantity();" <?php if($mode!="edit"){?>readOnly<?php }?> constraints="{min:<?php echo $minQuantity;?>}"
                  class="input"  value="<?php echo $quantity; ?>">
                  <?php echo $keyDownEventScript;?>  
               </div>
             </td>
            </tr>
            <?php if($paramEnableWorkUnit=='true'){ ?>
      <tr>
          <td class="dialogLabel"  >
               <label for="ActivityBilledWorkCommandWorkCommand" ><?php echo pq_strtolower(i18n("colWorkCommand")); ?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
             </td>
             <td>
               <select dojoType="dijit.form.FilteringSelect"
              <?php echo autoOpenFilteringSelect();?>
                id="ActivityBilledWorkCommandWorkCommand" name="ActivityBilledWorkCommandWorkCommand"
                class="input"  <?php if($mode!="edit"){?>readOnly<?php }?>>
                 <?php 
                 if($mode=='edit'){
                  htmlDrawOptionForReference('idWorkCommand',$idWorkCommand, $obj, false,array('idWorkUnit','idComplexity'), array($actWorkUnit->idWorkUnit,$actWorkUnit->idComplexity));
                 }else{
                  htmlDrawOptionForReference('idWorkCommand',null, $obj, false, 'elementary', '1'); 
                 }?>
               </select> 
               
             </td>
           </tr>
    <?php }
      if(!$visibility or ($visibility and $visibility!='NO' )){
    ?>
            <tr>
             <td class="dialogLabel" >
               <label for="ActivityWorkCommandAmount" ><?php echo i18n("colAmount");?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
             </td>
             <td>
             <?php if ($currencyPosition=='before') echo $currency;?>
               <input dojoType="dijit.form.NumberTextBox" 
                id="ActivityWorkCommandAmount" name="ActivityWorkCommandAmount"
                readonly 
                style="width:100px;<?php if (! $showGlobalCurrency) echo 'display:none;'?>"
                class="input"  value="<?php echo $commandAmount;?>">  
               </input> 
               <?php if ($currencyPosition=='after') echo $currency;?>
               
             <?php if ($hasLocalCurrency) {?>
             <?php if ($currencyPositionLocal=='before') echo $currencyLocal;?>
               <input dojoType="dijit.form.NumberTextBox" 
                id="ActivityWorkCommandAmountLocal" name="ActivityWorkCommandAmountLocal"
                readonly 
                style="width:100px;"
                class="input localFieldClass"  value="<?php echo $commandAmountLocal;?>">  
               </input> 
               <?php if ($currencyPositionLocal=='after') echo $currencyLocal;?>
             <?php }?>
             </td>
           </tr>
      <?php }else{?>
        <input dojoType="dijit.form.NumberTextBox" hidden
                id="ActivityWorkCommandAmount" name="ActivityWorkCommandAmount"
                type="hidden" value="<?php echo $commandAmount;?>">  
               </input> 
      <?php    } ?>
           <tr><td>&nbsp;</td><td>&nbsp;</td></tr>
         </table>
        </form>
      </td>
    </tr>
    <tr>
      <td align="center">
        <input type="hidden" id="workUnitAction">
        <button class="mediumTextButton" dojoType="dijit.form.Button" type="button" onclick="dijit.byId('dialogActivityWorkUnit').hide();">
          <?php echo i18n("buttonCancel");?>
        </button>
        <button class="mediumTextButton" dojoType="dijit.form.Button" type="submit" id="dialogActivityWorkUnitSubmit" onclick="protectDblClick(this);saveActivityWorkUnit();return false;">
          <?php echo i18n("buttonOK");?>
        </button>
      </td>
    </tr>
  </table>
