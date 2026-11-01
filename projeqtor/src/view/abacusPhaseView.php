<?php
/*** COPYRIGHT NOTICE *********************************************************
 *
 * Copyright 2009-2026 ProjeQtOr - Pascal BERNARD - support@projeqtor.org
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
scriptLog('   ->/view/abacusPhaseView.php');

$abacusPhaseIdleDisplay = Parameter::getUserParameter('abacusPhaseIdleDisplay');
$abacusPhaseIdleDisplay = ($abacusPhaseIdleDisplay=='on')?true:false;

$selectedPhasingId = getSessionValue('listAbacusPhaseFilter');
$critWhere = "1=1";
if ($selectedPhasingId) {
  $critWhere = "idPhasing = " . Sql::fmtId($selectedPhasingId);
}

$abacusPhase = new Phase();
$listAbacusPhase = $abacusPhase->getSqlElementsFromCriteria(null, false, $critWhere, 'sortOrder ASC');

$usedPhases = array();
if ($selectedPhasingId) {
  foreach ($listAbacusPhase as $phase) {
    $abacusValue = new AbacusValue();
    $values = $abacusValue->getSqlElementsFromCriteria(array('idPhase' => $phase->id));
    if (count($values) > 0) {
      $usedPhases[$phase->id] = true;
    }
  }
}

$destinationHeight = RequestHandler::getValue('destinationHeight');
$heightTable = ($destinationHeight < 700) ? '86%' : '90%';
?>

<div style="max-height: <?php echo $heightTable; ?>; overflow-y: auto; overflow-x: auto;">
  <?php if (!$selectedPhasingId || $selectedPhasingId == ''){?>
  <!-- No phasing selected -->
  <div id="noAbacusSelected" style="text-align:center;padding:50px;color:#999;font-size:14px;">
    <?php echo i18n('pleaseSelectAbacusPhase'); ?>
  </div>
  <div id="abacusLineTableDiv" style="display:none;"></div>
  <?php }else{ ?>
  <div style="display:flex;align-items:center;justify-content:flex-end;gap:10px;padding:0px 20px 10px 10px;">   
    <label for="abacusPhaseIdleDisplay" style="font-weight:bold;color:#666;font-size:13px;width:300px">
      <?php echo i18n('showClosedAbacusLines'); ?>
    </label> 
    <div id="abacusPhaseIdleDisplay" class="colorSwitch" leftLabel="" rightLabel="" data-dojo-type="dojox/mobile/Switch" style="width:50px;"
         value="<?php echo ($abacusPhaseIdleDisplay) ? 'on' : 'off'; ?>">
      <script type="dojo/method" event="onStateChanged" args="newValue">
        toggleAbacusPhaseIdle(newValue);
      </script>
    </div>
  </div>

  <table id="abacusPhaseTable" align="center" width="98%" style="margin: 0 auto;table-layout:auto;border: 1px solid #AAAAAA;">

    <thead>
      <tr class="ganttHeight" style="height:40px">
        <th class="assignHeader" style="width:3%;text-align:center;padding:5px"><?php echo ucfirst(i18n('colId')); ?></th>
        <th class="assignHeader" style="width:25%;text-align:center;padding:5px"><?php echo ucfirst(i18n('colShortName')); ?></th>
        <th class="assignHeader" style="width:45%;text-align:center;padding:5px"><?php echo ucfirst(i18n('colFullName')); ?></th>
        <th class="assignHeader" style="width:15%;text-align:center;padding:5px"><?php echo ucfirst(i18n('colDuration')) . ' (' .i18n('shortDay') . ')' ?></th>
        <th class="assignHeader" style="width:2%;text-align:center;padding:2px" title="<?php echo i18n('moveUp'); ?>"></th>
        <th class="assignHeader" style="width:2%;text-align:center;padding:2px" title="<?php echo i18n('moveDown'); ?>"></th>
        <th class="assignHeader" style="width:3%;text-align:center;padding:2px" title="<?php echo i18n('addAbacusPhase'); ?>">
          <a title="<?php echo i18n('addAbacusPhase'); ?>"onclick="addLineAbacusPhase();">
            <?php echo formatSmallButton('Add'); ?>
          </a>
            <a title="<?php echo i18n('addTenAbacusPhase'); ?>" onclick="addTenAbacusPhase();" style="display:inline-block;">
              <?php echo formatSmallButton('NewMultiple'); ?>
            </a>
        </th>
      </tr>
    </thead>

    <tbody>
      <?php
      if (count($listAbacusPhase) > 0) {
        foreach ($listAbacusPhase as $phase) {         
          $isUsed = isset($usedPhases[$phase->id]);
          $isIdle = ($phase->idle == 1);
          $rowClass = $isIdle ? 'abacusPhaseRow isIdle-line' : 'abacusPhaseRow';
          $rowStyle = ($isIdle && !$abacusPhaseIdleDisplay) ? 'display:none;' : '';

          $readonlyAttr = ($isUsed || $isIdle) ? 'readonly' : '';
          $disabledStyle = ($isUsed || $isIdle) ? 'background-color:#f0f0f0;cursor:not-allowed;' : '';
          
          $readonlyAttrDuration = $isIdle ? 'readonly' : '';
          $disabledStyleDuration =  $isIdle ? 'background-color:#f0f0f0;cursor:not-allowed;' : '';

          ?>
          <tr class="<?php echo $rowClass ?>" data-id="<?php echo $phase->id; ?>" data-used="<?php echo $isUsed ? '1' : '0'; ?>" style="height:40px;border-bottom: 1px solid #AAAAAA;<?php echo $rowStyle?>">
            <input type="hidden" id="phaseUsed_<?php echo $phase->id; ?>" name="phaseUsed[<?php echo $phase->id; ?>]" value="<?php echo $isUsed ? '1' : '0'; ?>" />
            <input type="hidden" id="phaseIdle_<?php echo $phase->id; ?>" name="phaseIdle[<?php echo $phase->id; ?>]" value="<?php echo $isIdle ? '1' : '0'; ?>" />

            <!-- ID  -->
             <td  style="text-align:center; font-weight: normal;color: #555555; background-color:#f0f0f0; border-right:1px solid #AAAAAA; position:relative;">              
              <?php if ($isUsed && !$isIdle){ ?>
                <span title="<?php echo i18n('abacusPhaseUsedInLines');?>" style="position:absolute;left:0;top:0;bottom:0;width:6px;background-color:#ec9c29;"></span>
              <?php } ?>            
              <?php echo $phase->id; ?>           
            </td>

            <!-- Short Name -->
            <td class="<?php echo $rowClass ?>" style="padding:2px;border-right:1px solid #AAAAAA;<?php echo $isUsed ? 'background-color:#f0f0f0;' : '';?>">
              <input type="text" name="shortName[<?php echo $phase->id; ?>]" id="shortName_<?php echo $phase->id; ?>" class="input dijitTextBox" maxlength="15" onchange="formChanged()" oninput="formChanged()"
                style="width:97%;border:1px solid transparent;padding:3px;outline:none;border-radius:2px;<?php echo $disabledStyle; ?>" value="<?php echo htmlEncode($phase->shortName); ?>" 
                <?php echo $readonlyAttr; ?>/>
            </td>
            
            <!-- Full Name -->
            <td class="<?php echo $rowClass ?>" style="padding:2px;border-right:1px solid #AAAAAA;<?php echo $isUsed ? 'background-color:#f0f0f0;' : '';?>">
              <input type="text" name="fullName[<?php echo $phase->id; ?>]" id="fullName_<?php echo $phase->id; ?>" class="input dijitTextBox" maxlength="100" onchange="formChanged()" oninput="formChanged()"
                style="width:97%;border:1px solid transparent;padding:3px;outline:none;border-radius:2px;<?php echo $disabledStyle; ?>" value="<?php echo htmlEncode($phase->name); ?>" 
                <?php echo $readonlyAttr; ?>/>
            </td>
            
            <!-- Duration -->
            <td class="<?php echo $rowClass ?>" style="padding:2px;border-right:1px solid #AAAAAA;<?php echo $isIdle ? 'background-color:#f0f0f0;' : '';?>">
              <input type="text" name="duration[<?php echo $phase->id; ?>]" id="duration_<?php echo $phase->id; ?>" class="input dijitTextBox" maxlength="5" onchange="formChanged()" oninput="formChanged()"
                style="width:97%;border:1px solid transparent;padding:3px;outline:none;border-radius:2px;<?php echo $disabledStyleDuration; ?>" value="<?php echo htmlEncode($phase->duration); ?>" 
                <?php echo $readonlyAttrDuration; ?>/>
            </td>

            <td class="" style="text-align:center;padding:2px;border-right:1px solid #AAAAAA;">
              <div class="iconDown16 iconDown imageColorNewGui iconSize16" style="cursor:pointer;transform: rotate(180deg);margin:0 auto;" title="<?php echo i18n('moveUp'); ?>"
                onclick="moveAbacusPhaseUp('<?php echo $phase->id; ?>');">
              </div>
            </td>

            <td class="" style="text-align:center;padding:2px;border-right:1px solid #AAAAAA;">
              <div class="iconDown16 iconDown imageColorNewGui iconSize16" style="cursor:pointer;margin:0 auto;" title="<?php echo i18n('moveDown'); ?>"
                onclick="moveAbacusPhaseDown('<?php echo $phase->id; ?>');">
              </div>
            </td>

            <td class="" style="text-align:center;padding:2px;">
							<?php if ($isIdle){ ?>
                <div class="iconClose16 imageColorNewGui iconClose iconSize16" title="<?php echo i18n('abacusPhaseIdle'); ?>" style="cursor:default;margin:0 auto;"></div>
              <?php } elseif ($isUsed){ ?>
                <div class="iconLock16 imageColorNewGui iconLock iconSize16" style="cursor:pointer;margin:0 auto;" title="<?php echo i18n('closeAbacusPhase'); ?>"
                  onclick="closeAbacusPhase('<?php echo $phase->id; ?>');">
                </div>
              <?php }else{ ?>
                <div class="iconRemove16 imageColorNewGui iconRemove iconSize16" style="cursor:pointer;margin:0 auto;" title="<?php echo i18n('delete'); ?>"
                  onclick="deleteAbacusPhaseLine('<?php echo $phase->id; ?>');">
                </div>
              <?php }?>
            </td>
          </tr>
          <?php
        }
      } else {
        ?>
        <tr>
          <td colspan="12" style="text-align:center;padding:15px;color:#999;">
            <?php echo i18n('noDataFound'); ?>
          </td>
        </tr>
        <?php
      }
      ?>
    </tbody>
  </table>
    <?php } ?>
</div>