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

// Pour documentExplorerShowClosed(), qui donne l'etat de l'interrupteur ci-dessous.
// Cette barre d'outils est dessinee avant l'inclusion de tool/jsonDocumentExplorer.php,
// qui charge le meme fichier : sans ce require, la fonction n'existe pas encore.
require_once "../tool/documentExplorerTreeData.php";

function documentExplorerDrawNewItem() { ?>
  <div dojoType="dijit.form.DropDownButton" class="comboButton"
       id="explorerNewItem" jsId="explorerNewItem" name="explorerNewItem"
       showlabel="false" iconClass="dijitButtonIcon dijitButtonIconNew"
       title="<?php echo i18n('comboNewButton');?>">
    <span>title</span>
    <div dojoType="dijit.TooltipDialog" class="white" style="width:200px;">
      <div style="font-weight:bold;height:25px;text-align:center"><?php echo i18n('comboNewButton');?></div>
      <?php foreach (array('DocumentDirectory','Document') as $item) {
        $canCreate=securityGetAccessRightYesNo('menu'.$item,'create');
        if ($canCreate=='YES' and ! securityCheckDisplayMenu(null,$item)) $canCreate='NO';
        if ($canCreate=='YES') { ?>
          <div style="vertical-align:top;cursor:pointer;" class="newGuiIconText"
               onClick="addNewItem('<?php echo $item;?>');">
            <table style="width:100%"><tr style="height:22px">
              <td style="vertical-align:top;width:30px;padding-left:5px"><?php echo formatIcon($item, 22, null, false);?></td>
              <td style="vertical-align:top;padding-top:2px"><?php echo i18n($item);?></td>
            </tr></table>
          </div>
          <div style="height:5px;"></div>
        <?php }
      } ?>
    </div>
  </div>
<?php }

function documentExplorerDrawFilter() {
  $activeFilter=false;
  if (is_array(getSessionUser()->_arrayFilters)
      and pq_array_key_exists('Document', getSessionUser()->_arrayFilters)) {
    foreach (getSessionUser()->_arrayFilters['Document'] as $filter) {
      if (! isset($filter['isDynamic']) or $filter['isDynamic']=="0") $activeFilter=true;
    }
  } ?>
  <button title="<?php echo i18n('advancedFilter');?>"
    class="comboButton" dojoType="dijit.form.DropDownButton"
    id="listFilterFilter" name="listFilterFilter"
    iconClass="dijitButtonIcon icon<?php echo ($activeFilter)?'Active':'';?>Filter" showLabel="false">
    <?php if (! isNewGui()) { ?>
      <script type="dojo/connect" event="onClick" args="evt">
        showFilterDialog();
      </script>
    <?php } ?>
    <div dojoType="dijit.TooltipDialog" id="directFilterList" style="z-index:999999;position:absolute;">
      <?php
      $objectClass='Document';
      $dontDisplay=true;
      include "../tool/displayFilterList.php";
      ?>
    </div>
  </button>
<?php }

function documentExplorerDrawColumnSelector() {
  $screenHeight=getSessionValue('screenHeight','1080');
  $columnSelectHeight=intval($screenHeight*0.5); ?>
  <div dojoType="dijit.form.DropDownButton"
       id="documentExplorerColumnSelector" jsId="documentExplorerColumnSelector" name="documentExplorerColumnSelector"
       showlabel="false" class="comboButton" iconClass="dijitButtonIcon dijitButtonIconColumn"
       title="<?php echo i18n('columnSelector');?>">
    <span>title</span>
    <div dojoType="dijit.TooltipDialog" id="documentExplorerColumnSelectorDialog" class="white" style="width:350px;">
      <?php /* Les sources de glisser-deposer n'existent qu'une fois le menu
               analyse : l'abonnement a onDndDrop se pose donc a l'ouverture. */ ?>
      <script type="dojo/connect" event="onShow" data-dojo-args="evt">
        documentExplorerBindColumnDnd();
      </script>
      <script type="dojo/connect" event="onHide" data-dojo-args="evt">
        if (dndMoveInProgress) { setTimeout('dijit.byId("documentExplorerColumnSelector").openDropDown();',1); }
      </script>
      <div style="text-align:center;">
        <button dojoType="dijit.form.Button" title="<?php echo i18n('titleResetList');?>"
          class="mediumTextButton" showLabel="true"><?php echo i18n('buttonReset');?>
          <script type="dojo/connect" event="onClick" args="evt">documentExplorerResetColumns();</script>
        </button>
        <button dojoType="dijit.form.Button" class="mediumTextButton" showLabel="true"><?php echo i18n('buttonOK');?>
          <script type="dojo/connect" event="onClick" args="evt">documentExplorerValidateColumns();</script>
        </button>
      </div>
      <div style="height:5px;"></div>
      <div id="divDocumentExplorerColumnSelector" dojoType="dijit.layout.ContentPane" region="top"
           style="overflow-y:auto; max-height:<?php echo $columnSelectHeight;?>px;">
        <?php foreach (array('directory'=>'DocumentDirectory','document'=>'Document') as $explorerType=>$documentExplorerClass) { ?>
          <div class="listTitle" style="font-weight:bold;padding:4px 0 2px 4px;">
            <?php echo i18n($documentExplorerClass);?>
          </div>
          <div id="dndDocumentExplorerColumnSelector<?php echo $explorerType;?>"
               jsId="dndDocumentExplorerColumnSelector<?php echo $explorerType;?>"
               dojotype="dojo.dnd.Source" dndType="documentExplorerColumn<?php echo $explorerType;?>"
               withhandles="true" class="container" style="position:relative;">
            <?php include '../tool/documentExplorerColumnSelector.php'; ?>
          </div>
          <div style="height:8px;"></div>
        <?php } ?>
      </div>
      <div style="height:5px;"></div>
      <div style="text-align:center;">
        <button dojoType="dijit.form.Button" title="<?php echo i18n('titleResetList');?>"
          class="mediumTextButton" showLabel="true"><?php echo i18n('buttonReset');?>
          <script type="dojo/connect" event="onClick" args="evt">documentExplorerResetColumns();</script>
        </button>
        <button dojoType="dijit.form.Button" class="mediumTextButton" showLabel="true"><?php echo i18n('buttonOK');?>
          <script type="dojo/connect" event="onClick" args="evt">documentExplorerValidateColumns();</script>
        </button>
      </div>
    </div>
  </div>
<?php }

function documentExplorerDrawButtonsDefault() { ?>
  <table style="width:10px">
    <tr>
      <td colspan="1"><?php documentExplorerDrawFilter();?></td>
      <td colspan="1"><?php documentExplorerDrawColumnSelector();?></td>
    </tr>
  </table>
<?php }

function documentExplorerDrawClickActionSwitch() { ?>
  <table style="margin-left:5px;">
    <tr title="<?php echo pq_ucfirst(i18n('planningClickActionSwitch'));?>">
      <td style="width:40px;">
        <div id="documentExplorerClickActionSwitch" name="documentExplorerClickActionSwitch"
             class="colorSwitch" data-dojo-type="dojox/mobile/Switch"
             <?php if (Parameter::getUserParameter('documentExplorerClickAction')=='1') {echo 'value="on"'; }else{echo 'value="off"';} ?>   
             leftLabel="" rightLabel="" style="width:25px;">
          <script type="dojo/connect" event="onStateChanged" args="newState">
            saveUserParameter('documentExplorerClickAction',((this.value=='on')?'1':'0'));
            documentExplorerClickAction = (this.value=='on')?'1':'0';
          </script>
        </div>
      </td>
      <td class="checkboxLabel">
        <span onclick="invertSwitchValue('documentExplorerClickActionSwitch');"><?php echo pq_ucfirst(i18n("planningClickAction"));?></span>
      </td>
    </tr>
  </table>
<?php }

function documentExplorerDrawPreviewSwitch() { ?>
  <table style="margin-left:5px;">
    <tr title="<?php echo pq_ucfirst(i18n('documentExplorerPreviewOnClick'));?>">
      <td style="width:40px;">
        <div id="documentExplorerPreviewSwitch" name="documentExplorerPreviewSwitch"
             class="colorSwitch" data-dojo-type="dojox/mobile/Switch"
             <?php if (Parameter::getUserParameter('documentExplorerPreviewOnClick')=='1') {echo 'value="on"'; }else{echo 'value="off"';} ?>
             leftLabel="" rightLabel="" style="width:25px;">
          <script type="dojo/connect" event="onStateChanged" args="newState">
            documentExplorerSavePreviewOnClick((this.value=='on')?'1':'0');
          </script>
        </div>
      </td>
      <td class="checkboxLabel">
        <span onclick="invertSwitchValue('documentExplorerPreviewSwitch');"><?php echo pq_ucfirst(i18n("documentExplorerPreviewOnClick"));?></span>
      </td>
    </tr>
  </table>
<?php }

function documentExplorerDrawShowClosedSwitch() { ?>
  <table style="margin-left:5px;">
    <tr title="<?php echo pq_ucfirst(i18n('showIdleElements'));?>">
      <td style="width:40px;">
        <?php /* Etat effectif et non valeur brute du parametre : le mode archive et un
                 filtre "idle >= 0" forcent l'affichage, comme sur le planning. */ ?>
        <div id="documentExplorerShowClosedSwitch" name="documentExplorerShowClosedSwitch"
             class="colorSwitch" data-dojo-type="dojox/mobile/Switch"
             <?php if (documentExplorerShowClosed()) {echo 'value="on"'; }else{echo 'value="off"';} ?>
             leftLabel="" rightLabel="" style="width:25px;">
          <script type="dojo/connect" event="onStateChanged" args="newState">
            documentExplorerSaveShowClosed((this.value=='on')?'1':'0');
          </script>
        </div>
      </td>
      <td class="checkboxLabel">
        <span onclick="invertSwitchValue('documentExplorerShowClosedSwitch');"><?php echo pq_ucfirst(i18n("labelShowIdle"));?></span>
      </td>
    </tr>
  </table>
<?php }

function documentExplorerDrawDisplayField() { ?>
  <table style="width:100%;" class="planningDialogArea">
    <tr>
      <td colspan="2" style="padding-top:3px;padding-left:5px;padding-right:3px">
        <table style="width:330px;"><tr>
          <td style="width:40px;">
            <div class="iconChangeLayout iconSize32 imageColorNewGuiNoSelection" style="border:0"></div>
          </td>
          <td class="dependencyHeader planningDialogTitle" style="text-align:left;">
            &nbsp;&nbsp;<?php echo i18n('displayOnDocumentExplorer');?>
          </td>
        </tr></table>
      </td>
    </tr>
    <tr>
      <td class="title" style="display:none;width:40px;"></td>
      <td style="width:100%;padding-left:5px;padding-right:5px">
        <div style="height:4px;width:100%;border-bottom:1px solid var(--color-detail-header-text) !important;"></div>
      </td>
    </tr>
    <tr>
      <td colspan="2" style="padding-top:6px;padding-bottom:4px;">
        <?php documentExplorerDrawClickActionSwitch();?>
      </td>
    </tr>
    <tr>
      <td colspan="2" style="padding-bottom:4px;">
        <?php documentExplorerDrawShowClosedSwitch();?>
      </td>
    </tr>
    <tr>
      <td colspan="2" style="padding-bottom:6px;">
        <?php documentExplorerDrawPreviewSwitch();?>
      </td>
    </tr>
  </table>
<?php }

function documentExplorerDrawExtraButton() { ?>
  <div dojoType="dijit.form.DropDownButton"
       id="extraButtonExplorer" jsId="extraButtonExplorer" name="extraButtonExplorer"
       showlabel="false" class="comboButton" iconClass="dijitButtonIcon dijitButtonIconExtraButtons"
       title="<?php echo i18n('extraButtons');?>">
    <div dojoType="dijit.TooltipDialog" class="white" id="extraButtonExplorerDialog"
         style="position:absolute;top:50px;right:40%">
      <?php documentExplorerDrawDisplayField();?>
    </div>
  </div>
<?php }
?>
