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
scriptLog('   ->/view/abacusLineView.php');

$keyDownEventScript = NumberFormatter52::getKeyDownEvent();
$destinationHeight = RequestHandler::getValue('destinationHeight');
$heightTable = ($destinationHeight < 700) ? '82%' : '86%';

$selectedAbacusId = Parameter::getUserParameter('listAbacusDefinitionFilter');
$abacusIdleDisplay = Parameter::getUserParameter('abacusLinesIdleDisplay');
$abacusIdleDisplay = ($abacusIdleDisplay=='on')?true:false;

$structure = null;
$columns = array();
$lines = array();
$unitLabel = '';
$phases = array();
$phaseColumns = array();

if ($selectedAbacusId) {
  $abacusDef = new AbacusDefinition($selectedAbacusId);
  
  if ($abacusDef && $abacusDef->id) {
    // Build structure
    $structure = array(
        'id' => $abacusDef->id,
        'name' => $abacusDef->name,
        'unit' => $abacusDef->abacusunit ? $abacusDef->abacusunit : 'd',
        'idPhasing' => $abacusDef->idPhasing,
    );
    
    // Phases if phasing is defined
    if ($abacusDef->idPhasing) {
      $phase = new Phase();
      $phases = $phase->getSqlElementsFromCriteria(array('idPhasing' => $abacusDef->idPhasing, 'idle' => '0'), false, null, 'sortOrder ASC');
      
      foreach ($phases as $ph) {
        $phaseColumns[] = array(
            'idPhase' => $ph->id,
            'name' => $ph->name,
            'shortName' => $ph->shortName ? $ph->shortName : $ph->name,
        );
      }
    } else {
      $phaseColumns[] = array(
          'idPhase' => null,
          'name' => ucfirst(i18n('colValue')),
          'shortName' => ucfirst(i18n('colValue')),
      );
    }
    
    for ($i = 1; $i <= 5; $i++) {
      $className = $abacusDef->{'className' . $i};
      $idAbacusable = $abacusDef->{'idAbacusable' . $i};
      if ($className) {
        $structure['className'.$i] = $className;
        $structure['className'.$i.'Label'] = i18n($className);
        $structure['idAbacusable'.$i] = $idAbacusable;
        $abacusable = SqlElement::getFirstSqlElementFromCriteria('Abacusable', array('id' => $idAbacusable));
        $isValueColumn = ($abacusable && $abacusable->valueField == 1);
        $isInputColumn = ($abacusable && $abacusable->inputField == 1);
        $structure['valueClassName'.$i] = $isValueColumn ? 1 : 0;
        $structure['inputClassName' . $i] = $isInputColumn ? 1 : 0;
        
        $columns[] = array(
            'field' => 'className' . $i,
            'label' => i18n($className),
            'className' => $className,
            'isValueColumn' => $isValueColumn,
            'isInputColumn' => $isInputColumn,
            'idAbacusable' => $idAbacusable,
        );
      }
    }
    
    $unitLabel = ($structure['unit'] === '%') ? i18n('percent') : i18n('colDay');
    $abacusLine = new AbacusLine();
    $rawLines = $abacusLine->getSqlElementsFromCriteria(array('idAbacusDefinition' => $selectedAbacusId),false, null, 'id ASC');
    
    foreach ($rawLines as $line) {
      $lineData = array(
          'id' => $line->id,
          'assumption'=> $line->assumption,
          'example' => $line->example,
          'idle' => $line->idle,
      );
      for ($i = 1; $i <= 5; $i++) {
        if (isset($structure['className' . $i])) {
          $lineData['className' . $i] = $line->{'idClassName' . $i};
        }
      }
      
      $abacusValue = new AbacusValue();
      $lineValues = $abacusValue->getSqlElementsFromCriteria(array(
          'idAbacusDefinition' => $selectedAbacusId,
          'idAbacusLine' => $line->id
      ));
      $lineData['values'] = array();
      foreach ($lineValues as $val) {
        $phaseId = $val->idPhase ? $val->idPhase : 'default';
        $displayValue = $val->value;
        if ($structure['unit'] === '%') {
          $displayValue = $displayValue * 100; // Convert 0.25 to 25
        }
        $lineData['values'][$phaseId] = $displayValue;
      }
      
      $lines[] = $lineData;
    }
    
    $usedLines = array();
    
    if ($selectedAbacusId) {
      $abacusable = new Abacusable();
     
      foreach ($lines as $lineData) {
        $lineId = $lineData['id'];
        $idClassName1 = isset($lineData['className1']) ? $lineData['className1'] : null;
        $idClassName2 = isset($lineData['className2']) ? $lineData['className2'] : null;
        $idClassName3 = isset($lineData['className3']) ? $lineData['className3'] : null;
        $idClassName4 = isset($lineData['className4']) ? $lineData['className4'] : null;
        $idClassName5 = isset($lineData['className5']) ? $lineData['className5'] : null;
        $abacusProject = new AbacusProject();
        $where = $abacusDef->getAbacusLineWhere($idClassName1,$idClassName2,$idClassName3,$idClassName4,$idClassName5);
        
        $existing = $abacusProject->getSqlElementsFromCriteria(null, false, $where);
        if (count($existing) > 0) $usedLines[$lineId] = true;        
      }
    }
    
    // select values for non-value columns
    $fieldValuesCache = array();
    foreach ($columns as $col) {
      $needsSelection = !($col['isValueColumn'] && !$col['isInputColumn']);
      
      if ($needsSelection) {
        $cls = $col['className'];
        $idAbacusable = $col['idAbacusable'];
        
        if (!isset($fieldValuesCache[$cls]) && class_exists($cls)) {
          $obj  = new $cls();
          $sortCriteria='name ASC';
          if ($cls=='ResourceTeam' or $cls=='ResourceOrTeam' or $cls=='ResourceFromTeam') $sortCriteria='fullName ASC';
          else if (property_exists($cls, 'sortOrder')) $sortCriteria='sortOrder ASC';
          $list = $obj->getSqlElementsFromCriteria(array('idle' => '0'), false, null, $sortCriteria);
          
          $abacusable = null;
          $hasValue = false;
          $hasInput = false;
          if ($idAbacusable) {
            $abacusable = new Abacusable($idAbacusable);
            $hasValue = ($abacusable->valueField == 1);
            $hasInput = ($abacusable->inputField == 1);
          }
          
          $vals = array('' => '');
          $order=0;
          foreach ($list as $item) {
            $order++;
            $displayName = $item->name;
            if ($hasValue && $hasInput && property_exists($item, 'value') ) {
              $displayName .= ' (' . htmlDisplayNumeric($item->value) . ')';
            }
            
            $vals[$order.'-'.$item->id] = $displayName;
          }
          $fieldValuesCache[$cls] = $vals;
        }
      }
    }
  }
}
?>
  <?php if ($structure){ ?>
  <div style="display:flex;justify-content:space-between;align-items:center;padding:10px 20px;"> 
    <span id="abacusUnitDisplay" style="font-weight:bold;color:#666;font-size:13px;">
      <?php echo ucfirst(i18n('colUnit')) . ' = ' . $unitLabel; ?>
    </span>
  
    <div style="display:flex;align-items:center;gap:10px;">
      <label for="abacusIdleDisplay" style="font-weight:bold;color:#666;font-size:13px;width:300px">
        <?php echo i18n('showClosedAbacusLines'); ?>
      </label> 
      <div id="abacusIdleDisplay" class="colorSwitch" leftLabel="" rightLabel="" data-dojo-type="dojox/mobile/Switch" style="width:50px;"
           value="<?php echo ($abacusIdleDisplay) ? 'on' : 'off'; ?>">
        <script type="dojo/method" event="onStateChanged" args="newValue">
        toggleAbacusIdleLines(newValue);
      </script>
      </div>
    </div> 
  </div>
  <?php }?>
  
<div id="abacusLineTableContainer"  class="<?php echo !$structure ? 'emptyAbacus' : ''; ?>" style="max-height: <?php echo $heightTable; ?>; overflow-y: auto; overflow-x: auto; margin: 0 20px;">

  <?php if (!$structure){ ?>
  <!-- No abacus selected -->
  <div id="noAbacusSelected" style="text-align:center;padding:50px;color:#999;font-size:14px;">
    <?php echo i18n('pleaseSelectAbacusDefinition'); ?>
  </div>
  <div id="abacusLineTableDiv" style="display:none;"></div>
  <?php }else{ ?>
  <div id="noAbacusSelected" style="display:none;"></div>
  <div id="abacusLineTableDiv">

    <table id="abacusLineTable"  style="margin:0 auto;table-layout:fixed;border:1px solid #AAAAAA;min-width:max-content;width:auto;white-space:nowrap;">

      <thead id="abacusLineTableHead" style="">
        <tr class="ganttHeight" style="height:40px;border-bottom:1px solid #AAAAAA;position: sticky;top: 0;z-index: 101;">
          <!-- ID -->
          <th class="assignHeader" style="width:30px;text-align:center;padding:5px;">
            <?php echo i18n('colId'); ?>
          </th>
          <!-- Dynamic columns -->
          <?php foreach ($columns as $col){ ?>
          <th class="assignHeader" style="max-width:200px;width:200px;text-align:center;padding:5px;overflow:hidden;text-overflow:ellipsis;">
            <?php echo htmlEncode($col['label']); ?>
          </th>
          <?php } ?>
          <!-- Assumption -->
          <th class="assignHeader" style="max-width:300px;width:300px;text-align:center;padding:5px;">
            <?php echo i18n('menuAssumption'); ?>
          </th>
          <!-- Examples -->
          <th class="assignHeader" style="max-width:300px;width:300px;text-align:center;padding:5px;">
            <?php echo i18n('colExamples'); ?>
          </th>
          <!-- Phase columns -->
          <?php foreach ($phaseColumns as $phCol){ ?>
          <th class="assignHeader" style="max-width:120px;width:100px;text-align:center;padding:5px;border-right:none !important;background-color:#f8f9fa;overflow:hidden;text-overflow:ellipsis;">
            <?php echo htmlEncode($phCol['shortName']); ?>
          </th>
          <?php } ?>
          <!-- Add buttons -->
          <th style="position: sticky;width:0.5px; background-color:#AAAAAA;right: 80px;z-index: 9999999;"></th>
          <th class="assignHeader" style="width:80px;text-align:center;padding:2px;position: sticky;right: 0;z-index: 101;border:none;">
            <a title="<?php echo i18n('addAbacusLine'); ?>" onclick="addAbacusLine();" style="display:inline-block;margin-bottom:2px;margin-right:8px;">
              <?php echo formatSmallButton('Add'); ?>
            </a>
            <a title="<?php echo i18n('addTenAbacusLines'); ?>" onclick="addTenAbacusLines();" style="display:inline-block;">
              <?php echo formatSmallButton('NewMultiple'); ?>
            </a>
          </th>
        </tr>
      </thead>

      <tbody id="abacusLineTableBody">
        <?php if (count($lines) === 0){ ?>
        <tr class="noDataRow">
          <td colspan="<?php echo (3 + count($columns) + 2 + count($phaseColumns) + 2); ?>"
              style="text-align:center;padding:15px;color:#999;">
            <?php echo i18n('noDataFound'); ?>
          </td>
        </tr>
        <?php } else{ ?>
        <?php foreach ($lines as $lineData){
          $lineId = $lineData['id']; 
          $isIdle = $lineData['idle'];
          $isUsed = isset($usedLines[$lineId]) ? 1 : 0;
          
          $rowClass = $isIdle ? 'abacusLineRow isIdle-line' : 'abacusLineRow';
          $rowStyle = ($isIdle && !$abacusIdleDisplay) ? 'display:none;' : '';
          ?>

        <tr class=" <?php echo $rowClass; ?>" data-id="<?php echo $lineId; ?>" style="border-bottom:1px solid #AAAAAA;vertical-align:top;padding-top:6px;<?php echo $rowStyle; ?>">
          <input type="hidden" id="lineUsed_<?php echo $lineId; ?>" name="lineUsed[<?php echo $lineId; ?>]" value="<?php echo $isUsed; ?>" />
          <!-- ID cell -->        
          <td  style="text-align:center; font-weight: normal;color: #555555;padding:17px 2px 2px 2px; background-color:#f5f5f5; border-right:1px solid #AAAAAA; position:relative;">              
            <?php if ($isUsed && !$isIdle){ ?>
                <span title="<?php echo i18n('abacusLineUsed');?>" style="position:absolute;left:0;top:0;bottom:0;width:6px;background-color:#ec9c29"></span>
            <?php } ?>            
            <?php echo htmlEncode($lineId); ?>           
          </td>
          
          
          <!-- Dynamic columns -->
          <?php foreach ($columns as $col){
            $field   = $col['field'];
            $isValue = $col['isValueColumn'];
            $isInput = $col['isInputColumn'];
            $current = isset($lineData[$field]) ? $lineData[$field] : '';
            $isDisabled = ($isIdle || $isUsed);
            $isReadonly = ($isValue && !$isInput);
          ?>
          <td style="padding:8px 2px 2px 2px;border-right:1px solid #AAAAAA;<?php echo $isReadonly || $isUsed ? 'background-color:#f0f0f0;' : '';?>" onchange="formChanged();">
            <?php if ($isReadonly){ ?>
            <!-- Value column : read-only numeric input -->
            <input name="<?php echo $field; ?>[<?php echo $lineId; ?>]" id="<?php echo $field; ?>_<?php echo $lineId; ?>" class="input"style="width:97%;border:none;text-align:right;background-color:#f0f0f0;"
                   value="<?php echo htmlEncode($current); ?>" <?php echo $isDisabled ? 'disabled' : ''; ?> readonly />
            <?php } else { ?>
            <select dojoType="dijit.form.FilteringSelect" name="<?php echo $field; ?>[<?php echo $lineId; ?>]" id="<?php echo $field; ?>_<?php echo $lineId; ?>" class="input" 
                    style="width:97%;border:none;padding:3px;" data-dojo-props="queryExpr: '*${0}*', autoComplete: true" onchange="formChanged();" <?php echo $isDisabled ? 'disabled' : ''; ?>>>
              <?php $cls  = $col['className'];
              $vals = isset($fieldValuesCache[$cls]) ? $fieldValuesCache[$cls] : array('' => '');
              foreach ($vals as $key => $label){
                $exp=explode('-',$key);
                if (count($exp)==2) $key=$exp[1];
                else $key=$exp[0];
                $selected = ((string)$current === (string)$key) ? 'selected="selected"' : ''; ?>
              <option value="<?php echo htmlEncode($key); ?>" <?php echo $selected; ?>>
                <?php echo htmlEncode($label); ?>
              </option>
              <?php } ?>
            </select>
            <?php } ?>
          </td>
          <?php } ?>

          <!-- Assumption -->
          <td style="padding:10px 2px 2px 2px;border-right:1px solid #AAAAAA;" onchange="formChanged();">
            <textarea name="assumption[<?php echo $lineId; ?>]" id="assumption_<?php echo $lineId; ?>" class="input dijitTextBox syncedTextarea" 
                      style="width:97%;border:none;padding:3px;resize:vertical;font-family:Arial;min-height:25px;"
                      <?php echo $isIdle ? 'disabled' : ''; ?>><?php echo htmlEncode($lineData['assumption']); ?></textarea>
          </td>
          
          <!-- Example -->
          <td style="padding:10px 2px 2px 2px;border-right:1px solid #AAAAAA;" onchange="formChanged();">
            <textarea name="example[<?php echo $lineId; ?>]" id="example_<?php echo $lineId; ?>" class="input dijitTextBox syncedTextarea" 
                      style="width:97%;border:none;padding:3px;resize:vertical;font-family:Arial;min-height:25px;"
                      <?php echo $isIdle ? 'disabled' : ''; ?>><?php echo htmlEncode($lineData['example']); ?></textarea>
          </td>

          <!-- Phase columns -->
          <?php
          $total = count($phaseColumns);
          $i = 0;
          foreach ($phaseColumns as $phCol){
            $i++;
            $phaseId = $phCol['idPhase'] ? $phCol['idPhase'] : 'default';
            $currentValue = isset($lineData['values'][$phaseId]) ? $lineData['values'][$phaseId] : '0';
            
            // Format the value for display
            if ($currentValue !== '' && is_numeric($currentValue)) {
              if ($structure['unit'] === '%') {
                $currentValue = number_format($currentValue, 2, '.', '');
              } else {
                $currentValue = number_format($currentValue, 2, '.', '');
              }
            }
            $displayUnit = ($structure['unit'] === '%') ? '%' : i18n('shortDay');
            $style ="padding:8px 2px 2px 2px;" . ($i < $total ? "border-right:1px solid #AAAAAA;" : "") . ($isIdle ? "background-color:#f0f0f0;" : "");
          ?>
          <td style="<?php echo $style ?>" onchange="formChanged();">
          <div style="display:flex;align-items:center;gap:2px;">
            <div dojoType="dijit.form.NumberTextBox" type="text"
                   name="phaseValue[<?php echo $lineId; ?>][<?php echo $phaseId; ?>]" 
                   id="phaseValue_<?php echo $lineId; ?>_<?php echo $phaseId; ?>" 
                   class="input phaseValueInput dijitTextBox" 
                   data-unit="<?php echo htmlEncode($structure['unit']); ?>"
                   style="width:97%;border:none;text-align:right;padding:3px;<?php echo $isIdle ? 'background-color:#f0f0f0;' : ''; ?>""
                   value="<?php echo htmlEncode($currentValue); ?>"
                   <?php echo $isIdle ? 'disabled' : ''; ?> />
            <?php echo $keyDownEventScript;?> 
            </div>
            <span style="color:#666;font-size:11px;min-width:20px;"><?php echo htmlEncode($displayUnit); ?></span>
          </div>
          </td>
          <?php } ?>

          <!-- Delete -->
          <td class="delete-cell" style="position: sticky;width:0.5px; background-color:#AAAAAA;right: 80px;z-index: 9999999;"></td>
          <td class="delete-cell" style="padding:17px 10px 2px 2px;position: sticky;right: 0;z-index: 20;background: <?php echo $isIdle || $isUsed ? '#F0F0F0' : 'white' ?>;">
            <div style="display:flex;align-items:center;justify-content:center;gap:15px;">
          
              <?php if ($isIdle) { ?>
                <div class="iconClose16 imageColorNewGui iconClose iconSize16" title="<?php echo i18n('reopenAbacusLine'); ?>" style="cursor:pointer;" onclick="reopenAbacusLine('<?php echo $lineId; ?>');"></div>
              <?php } else if ($isUsed) { ?>
                <div class="iconLock16 imageColorNewGui iconLock iconSize16" title="<?php echo i18n('closeAbacusLine'); ?>" style="cursor:pointer;" onclick="closeAbacusLine('<?php echo $lineId; ?>');"></div>
              <?php } else { ?>
                <div class="iconRemove16 imageColorNewGui iconRemove iconSize16" style="cursor:pointer;" onclick="deleteAbacusLine('<?php echo $lineId; ?>');"></div>
              <?php } ?>
          
              <div class="iconCopy16 imageColorNewGui iconCopy iconSize16" title="<?php echo i18n('copyAbacusLine'); ?>" style="cursor:pointer;" onclick="copyAbacusLine('<?php echo $lineId; ?>');"></div>
          
            </div>
          </td>

        </tr>
        <?php }} ?>
      </tbody>
    </table>
  </div>
  <?php } ?>

</div>


<input type="hidden" id="currentAbacusDefinitionId" value="<?php echo $selectedAbacusId ? htmlEncode($selectedAbacusId) : ''; ?>" />
<input type="hidden" id="currentAbacusStructure" value="<?php echo $structure ? htmlspecialchars(json_encode($structure), ENT_QUOTES, 'UTF-8') : ''; ?>" />
<input type="hidden" id="abacusFieldValuesCache" value='<?php echo $structure ? htmlspecialchars(json_encode($fieldValuesCache), ENT_QUOTES, 'UTF-8') : '{}'; ?>' />
<input type="hidden" id="abacusPhaseColumns" value='<?php echo $structure ? htmlspecialchars(json_encode($phaseColumns), ENT_QUOTES, 'UTF-8') : '[]'; ?>' />
