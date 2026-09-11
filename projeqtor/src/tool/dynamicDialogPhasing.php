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
include_once('../tool/formatter.php');

$phasing = new Phasing();
$critWhere="1=1";
$listPhasing = $phasing->getSqlElementsFromCriteria(null, false, $critWhere,'name ASC');

?>

<div style="padding:10px;overflow:auto;max-height:550px;">
  <form id="phasingForm" name="phasingForm"> 
    <div style="padding:10px 10px 10px 0px;margin-bottom:15px;">    
      <div style="display:flex;align-items:center;gap:10px;">    
        <span style="white-space:nowrap;">
          <?php echo i18n('colName'); ?> :
        </span>        
        <div style="position: relative; display: flex; align-items: center;">
          <input type="text" id="newPhasingInput"  maxlength="100" placeholder="<?php echo ucfirst(i18n('addPhasing'));?>" onkeydown="validatePhasing()" onkeyup="inputNamePhasing()" style="width: 100%; border: 1px solid var(--color-medium); border-radius: 5px; padding: 5px;" />
          <div class="iconCancel iconSize16 imageColorNewGui" onclick="cancelPhasingInput();" id="clearPhasingInput" style="padding-top: 0; position: absolute; right: 7px; cursor: pointer;display:none;"></div>
        </div>
        <button id="buttonAddPhasing" dojoType="dijit.form.Button" showlabel="false" title="<?php echo i18n('addPhasing');?>" iconClass="imageColorNewGui iconAdd22 iconAdd iconSize22" class="notButton"
         onclick="addPhasing()";>
       </button>        
      </div>    
    </div>
    
    <table width="100%" style="margin-bottom:15px;">
     <?php if (count($listPhasing) > 0) { ?>
      <thead>
        <tr class="" style="height:32px">
          <th class="assignHeader" style="width:12%;text-align:center;padding:5px"></th>
          <th class="assignHeader" style="width:5%;text-align:center;padding:5px"><?php echo ucfirst(i18n('colId')); ?></th>
          <th class="assignHeader" style="width:65%;text-align:center;padding:5px"><?php echo i18n('colName'); ?></th>
        </tr>
      </thead>
     <?php } ?>
      <tbody id="phasingTableBody">
        <?php
        if (count($listPhasing) > 0) {
          foreach ($listPhasing as $item) {
            ?>
            <tr id="phasingRow_<?php echo $item->id; ?>" style="height:32px;">
              <td class="assignData" style="text-align:center;padding:2px; vertical-align: middle;">
                <a title="<?php echo ucfirst(i18n('deleteButton')); ?>" onclick="removePhasing(<?php echo $item->id; ?>);">
                  <?php echo formatSmallButton('Remove') ?>
                </a>
                <a title="<?php echo ucfirst(i18n('edit')); ?>" onclick="editPhasing(<?php echo $item->id; ?>);"  style="margin-left:5px;">
                  <?php echo formatSmallButton('Edit') ?>
                </a>
              </td>
              
              <td class="assignData" style="text-align:center; vertical-align: middle;">
                <?php echo $item->id; ?>
              </td>
              
              <td id="phasingNameCell_<?php echo $item->id; ?>" class="assignData" style="padding:2px;vertical-align: middle;max-width:500px ! important;">
                <div id="phasingName_<?php echo $item->id; ?>" name="phasingName_<?php echo $item->id; ?>" value="<?php echo htmlEncode($item->name); ?>" 
                  style="width:auto;word-wrap: break-word;white-space: normal;padding:3px;" title="<?php echo htmlEncode($item->name); ?>"><?php echo htmlEncode($item->name); ?></div>
              </td>             
              
            </tr>
            <?php
          }
        } else {
          ?>
          <tr>
            <td colspan="3" style="text-align:center;padding:15px;color:#999;">
              <?php echo i18n('noDataFound'); ?>
            </td>
          </tr>
          <?php
        }
        ?>
      </tbody>
    </table>
  
      <div style="text-align:center;margin-top:20px;">
        <input type="hidden" id="dialogAbacusPhaseAction">
        <button class="mediumTextButton" dojoType="dijit.form.Button" type="button" onclick="dijit.byId('dialogPhasing').hide();">
          <?php echo i18n("buttonCancel");?>
        </button>
        <button class="mediumTextButton" dojoType="dijit.form.Button" type="submit" id="dialogAbacusPhasingSubmit" onclick="protectDblClick(this);addPhasing(true);return false;" style="margin-left:10px;">
          <?php echo i18n("buttonOK");?>
        </button>
      </div>
   </form> 
</div>