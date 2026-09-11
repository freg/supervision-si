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
$user=getSessionUser();
$layoutObjectClass=RequestHandler::getValue('objectClass');
$canAttributeLayoutParam = SqlElement::getSingleSqlElementFromCriteria('HabilitationOther', array('idProfile'=>$user->idProfile, 'scope'=>'canAttributeLayout'));
$canAttributeLayout = ($canAttributeLayoutParam->id)?$canAttributeLayoutParam->rightAccess:2;
$forcedLayout = LayoutForced::getSingleSqlElementFromCriteria('LayoutForced', array('idUser'=>$user->id, 'objectClass'=>$layoutObjectClass));
$planningClass = array('Planning'=>'planning','PortfolioPlanning'=>'portfolio','ResourcePlanning'=>'resource','GlobalPlanning'=>'global','VersionPlanning'=>'version','ContractGantt'=>'contract');
$planningType = (isset($planningClass[$layoutObjectClass]))?$planningClass[$layoutObjectClass]:null;
?>
<table style="<?php if (isNewGui()) echo 'width:780px';?>">
    <tr>
     <td class="section"><?php echo i18n("sectionStoredLayout");?></td>
    </tr>
    <?php if (isNewGui()) {?><tr><td><div style="height:6px"></div></td></tr><?php }?>
    <tr>
      <td>
        <div id='listStoredLayouts' dojoType="dijit.layout.ContentPane" region="center" ><div style="height:250px">loading...</div></div>
      </td>
    </tr>
    <tr><td>&nbsp;</td></tr>
    <tr>
      <td>
        <div id='listSharedLayouts' dojoType="dijit.layout.ContentPane" region="center"></div>
      </td>
    </tr>
    <tr><td>&nbsp;</td></tr>
</table>
<table style="<?php if (isNewGui()) echo 'width:780px';?>">
    <tr>
     <td class="section"><?php echo i18n("sectionActiveLayout");?></td>
    </tr>
    <tr>
      <td style="margin: 2px;"> 
        <form id='dialogLayoutForm' name='dialogLayoutForm' onSubmit="return false;">
         <input type="hidden" id="layoutObjectClass" name="layoutObjectClass" value="<?php echo $layoutObjectClass;?>"/>
         <input type="hidden" id="layoutName" name="layoutName" />
         <div id='listSelectedLayout' dojoType="dijit.layout.ContentPane" region="center" style="overflow:hidden;max-height:127px;overflow-y:auto"></div>
        </form>
      </td>
    </tr>
    <?php if (isNewGui()) {?><tr><td><div style="height:6px"></div></td></tr><?php }?>
    <tr style="height:32px">
      <td align="center">
        <table><tr>
        <td>
        <button class="mediumTextButton" dojoType="dijit.form.Button" type="button" onclick="dijit.byId('dialogLayout').hide();">
          <?php echo i18n("buttonCancel");?>
        </button>
        </td>
        <?php if($canAttributeLayout == 1){?>
        <td>
        <input type="hidden" id="canAttributeLayout" name="canAttributeLayout" value="<?php echo $canAttributeLayout; ?>">
        <input type="hidden" id="idForcedLayout" name="idForcedLayout" value="<?php echo $forcedLayout->idLayout; ?>">
        <?php $name="";$idLayout="";$disabled="";
              if (pq_array_key_exists($layoutObjectClass . "LayoutName", $user->_arrayLayouts)) {
                $name=$user->_arrayLayouts[$layoutObjectClass . "LayoutName"];
              }
              if (pq_array_key_exists($layoutObjectClass, $user->_arrayLayouts)) {
                $idLayout=$user->_arrayLayouts[$layoutObjectClass]['id'];
              }
              if(!$name or ($idLayout != "" and $idLayout == $forcedLayout->idLayout))$disabled = 'disabled';
              ?>
        
        <button  id="layoutAttribute" name="layoutAttribute" class="mediumTextButton" <?php echo $disabled;?> dojoType="dijit.form.Button" onclick="loadDialog('dialogLayoutForOthers',null,true,'&layoutObjectClass='+ dojo.byId('layoutObjectClass').value,true);">
          <?php echo i18n("buttonAttributeLayout");?>
        </button>
        </td>
        <?php }?>
        <td>
        <button class="mediumTextButton" dojoType="dijit.form.Button" type="submit" id="dialogLayoutSubmit" onclick="protectDblClick(this);validateLayoutListColumn('<?php echo $planningType?>');return false;">
          <?php echo i18n("buttonOK");?>
        </button>
        </td></tr></table>
      </td>
    </tr>
  </table>