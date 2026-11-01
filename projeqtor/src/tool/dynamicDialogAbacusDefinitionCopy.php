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

$idAbacusDefinition = RequestHandler::getId('idAbacusDefinition');
$abacus = new AbacusDefinition($idAbacusDefinition);

$phasing = new Phasing();
$phasingList = $phasing->getSqlElementsFromCriteria(array('idle' => '0'), false, null, 'name ASC');
$phasingArray = array('' => '');
foreach ($phasingList as $ph) {
  $phasingArray[$ph->id] = $ph->name;
}

$defaultName = i18n('copyOfPrefix') . ' ' . $abacus->name;
?>

<div style="padding:10px;">
  <form dojoType="dijit.form.Form" id="abacusDefinitionCopyForm" name="abacusDefinitionCopyForm" onSubmit="return false;">
    <table style="width:100%;">
      <tr>
        <td class="dialogLabel" style="width:25%;">
          <label><?php echo ucfirst(i18n('colName')); ?> &nbsp;&nbsp;</label>
        </td>
        <td>
          <input id="copyAbacusName" name="copyAbacusName" dojoType="dijit.form.TextBox" type="text" class="input" style="width:100%;" required="required" value="<?php echo htmlEncode($defaultName); ?>" />
        </td>
      </tr>
      <tr>
        <td class="dialogLabel" style="width:25%;padding-top:8px;">
          <label><?php echo i18n('colIdPhasing'); ?> &nbsp;&nbsp;</label>
        </td>
        <td style="padding-top:8px;">
          <select id="copyAbacusIdPhasing" name="copyAbacusIdPhasing" dojoType="dijit.form.FilteringSelect" class="input" <?php echo autoOpenFilteringSelect();?> style="width:100%;" data-dojo-props="queryExpr: '*${0}*', autoComplete: true">
            <?php foreach ($phasingArray as $key => $val) {
              $selected = ($abacus->idPhasing == $key) ? 'selected="selected"' : '';
              echo '<option value="' . htmlEncode($key) . '" ' . $selected . '>' . htmlEncode($val) . '</option>';
            } ?>
          </select>
        </td>
      </tr>
      <tr>
        <td colspan="2" style="padding-top:10px;">
          <div id="copyPhasingWarning" style="display:none;background-color:#fff3cd;border:1px solid #ffc107;padding:8px;border-radius:4px;color:#856404;font-size:12px;">
            <?php echo i18n('warningCopyAbacusPhasingChanged'); ?>
          </div>
        </td>
      </tr>
    </table>

    <div style="text-align:center;margin-top:20px;">
      <input type="hidden" id="copyAbacusSourceId" value="<?php echo $abacus->id; ?>">
      <input type="hidden" id="copyAbacusOriginalPhasing" value="<?php echo $abacus->idPhasing; ?>">

      <button class="mediumTextButton" dojoType="dijit.form.Button" type="button" onclick="dijit.byId('dialogAbacusDefinitionCopy').hide();">
        <?php echo i18n("buttonCancel"); ?>
      </button>
      <button class="mediumTextButton" dojoType="dijit.form.Button" type="submit" id="dialogAbacusDefinitionCopySubmit"
              onclick="protectDblClick(this);saveCopyAbacusDefinition();return false;" style="margin-left:10px;">
        <?php echo i18n("buttonOK"); ?>
      </button>
    </div>
  </form>
</div>