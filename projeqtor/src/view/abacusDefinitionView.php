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

/* ============================================================================
 * Presents the list of Abacus Definitions
 */
require_once "../tool/projeqtor.php";
include_once('../tool/formatter.php');
scriptLog('   ->/view/abacusDefinitionView.php');

$abacusDefinitionIdleDisplay = (Parameter::getUserParameter('abacusIdleDisplay')=='on')?true:false;
$critWhere="1=1";

$abacusDef = new AbacusDefinition();
$listAbacusDef = $abacusDef->getSqlElementsFromCriteria(null, false, $critWhere, 'sortOrder ASC');

$abacusLine = new AbacusLine();
$allLines = $abacusLine->getSqlElementsFromCriteria(null, false, $critWhere, null);

$usedDefinitions = array();
foreach ($allLines as $line) {
  if ($line->idAbacusDefinition) {
    $usedDefinitions[$line->idAbacusDefinition] = true;
  }
}

$abacusable = new Abacusable();
$listAbacusable = $abacusable->getSqlElementsFromCriteria(null, false, $critWhere, 'className ASC, valueField ASC, inputField ASC');
$classList = array('' => '');
$abacusableMap = array();
$abacusableById = [];
$classListDetailed = array();
foreach ($listAbacusable as $ab) {
  $abacusableById[$ab->id] = $ab;
  $suffix = '';
  $key = $ab->className;
  if ($ab->className != 'Resource' && $ab->valueField == 1 && $ab->inputField == 1) {
    $suffix = ' (' . i18n('colValue') . ', ' . i18n('input') . ')';
    $key .= '_value_input';
  } else if ($ab->className != 'Resource' && $ab->valueField == 1 && $ab->inputField == 0) {
    $suffix = ' (' . i18n('colValue') . ')';
    $key .= '_value';
  }
  $displayName = i18n($ab->className) . $suffix;
  $classList[$key] = $displayName;
  $abacusableMap[$key] = $ab->id;
  if (!isset($classListDetailed[$ab->className])) {
    $classListDetailed[$ab->className] = array();
  }
  $classListDetailed[$ab->className][] = array(
      'id' => $ab->id,
      'key' => $key,
      'valueField' => $ab->valueField,
      'inputField' => $ab->inputField,
      'displayName' => $displayName
  );
}
$abacusableKeyById = array_flip($abacusableMap);

$phasing = new Phasing();
$phasingList = $phasing->getSqlElementsFromCriteria(array('idle' => '0'), false, null, 'name ASC');
$phasingArray = array('' => '');
foreach ($phasingList as $ph) {
  $phasingArray[$ph->id] = $ph->name;
}

$unitArray = array(
    'd' => i18n('colDay'),
    '%' => i18n('percent')
);

$destinationHeight = RequestHandler::getValue('destinationHeight');
$heightTable = ($destinationHeight < 700) ? '86%' : '90%';

?>

<div style="max-height: <?php echo $heightTable; ?>; overflow-y: auto; overflow-x: auto;">

  <div style="display:flex;align-items:center;justify-content:flex-end;gap:10px;padding:0px 20px 10px 10px;">   
    <label for="abacusDefinitionIdleDisplay" style="font-weight:bold;color:#666;font-size:13px;width:300px">
      <?php echo i18n('showClosedAbacusLines'); ?>
    </label> 
    <div id="abacusDefinitionIdleDisplay" class="colorSwitch" leftLabel="" rightLabel="" data-dojo-type="dojox/mobile/Switch" style="width:50px;"
         value="<?php echo ($abacusDefinitionIdleDisplay) ? 'on' : 'off'; ?>">
      <script type="dojo/method" event="onStateChanged" args="newValue">
        toggleAbacusDefinitionIdle(newValue);
      </script>
    </div>
  </div>

  <table id="abacusDefinitionTable" align="center" width="98%" style="margin: 0 auto;table-layout:auto;border: 1px solid #AAAAAA;">
		<input type="hidden" id="abacusClassListJson" value='<?php echo htmlspecialchars(json_encode($classList), ENT_QUOTES, 'UTF-8'); ?>' />
		<input type="hidden" id="abacusPhasingListJson" value='<?php echo htmlspecialchars(json_encode($phasingArray), ENT_QUOTES, 'UTF-8'); ?>' />
		<input type="hidden" id="abacusUnitListJson" value='<?php echo htmlspecialchars(json_encode($unitArray), ENT_QUOTES, 'UTF-8'); ?>' />
		<input type="hidden" id="abacusableMapJson" value='<?php echo htmlspecialchars(json_encode($abacusableMap), ENT_QUOTES, 'UTF-8'); ?>' />
		<?php $option = array(
        'fixed' => i18n('fixed'),
		    'proportional' => ucfirst(i18n('proportionalOption'))
    );?>
    <input type="hidden" id="abacusWorkTypeListJson" value='<?php echo htmlspecialchars(json_encode($option), ENT_QUOTES, 'UTF-8'); ?>' />
		<input type="hidden" id="classListDetailedJson" value='<?php echo htmlspecialchars(json_encode($classListDetailed), ENT_QUOTES, 'UTF-8'); ?>' />

    <thead>
      <tr class="ganttHeight" style="height:40px">
        <th class="assignHeader" style="width:3%;text-align:center;padding:5px"><?php echo ucfirst(i18n('colId')); ?></th>
        <th class="assignHeader" style="width:15%;text-align:center;padding:5px"><?php echo ucfirst(i18n('colName')); ?></th>
         <?php for ($i=1;$i<=5;$i++) { ?>
          <th class="assignHeader" style="width:10%;text-align:center;padding:5px"><?php echo i18n('colClassName') . " $i" ?></th>
        <?php }?>
        <th class="assignHeader" style="width:10%;text-align:center;padding:5px"><?php echo i18n('colIdPhasing'); ?></th>
        
        <th class="assignHeader" style="width:5%;text-align:center;padding:5px;;position: relative;" title="<?php echo i18n('tooltipUnit'); ?>">
        	<?php echo ucfirst(i18n('colUnit')); ?>
        	 <span id="infoIconUnit" class="iconInfo12 iconInfo iconSize12 imageColorNewGui" style="cursor:help;top:3px;position:absolute;right:3px;" data-info-text="<?php echo i18n('tooltipUnit'); ?>"></span>
        </th>
        
        <th class="assignHeader" style="width:10%;text-align:center;padding:5px;position: relative;" title="<?php echo str_replace('<br/>', '&#10;', i18n('tooltipAssignmentWorkType')); ?>">
          <?php echo ucfirst(i18n('colAsignmentWork')); ?>
          <span id="infoIconAssignmentWork" class="iconInfo12 iconInfo iconSize12 imageColorNewGui" style="cursor:help;top:3px;position:absolute;right:3px;" data-info-text="<?php echo i18n('tooltipAssignmentWorkType'); ?>"></span>
        </th>
        
        <th class="assignHeader" style="width:2%;text-align:center;padding:2px" title="<?php echo i18n('moveUp'); ?>"></th>
        <th class="assignHeader" style="width:2%;text-align:center;padding:2px" title="<?php echo i18n('moveDown'); ?>"></th>
        <th class="assignHeader" style="width:5%;text-align:center;padding:2px" title="<?php echo i18n('addAbacusDefinition'); ?>">
          <a title="<?php echo i18n('addAbacusDefinition'); ?>"onclick="addLineAbacusDefinition();">
            <?php echo formatSmallButton('Add'); ?>
          </a>
            <a title="<?php echo i18n('addTenAbacusDefinition'); ?>" onclick="addTenAbacusDefinition();" style="display:inline-block;">
              <?php echo formatSmallButton('NewMultiple'); ?>
            </a>
        </th>
      </tr>
    </thead>

    <tbody>
      <?php
      if (count($listAbacusDef) > 0) {
        foreach ($listAbacusDef as $def) {         
          $isUsed = isset($usedDefinitions[$def->id]);
          $isIdle = ($def->idle == 1);
          $rowClass = $isIdle ? 'abacusDefRow isIdle-line' : 'abacusDefRow';
          $rowStyle = ($isIdle && !$abacusDefinitionIdleDisplay) ? 'display:none;' : '';

          $disabledAttr = ($isUsed || $isIdle) ? 'disabled' : '';
          $readonlyAttr = ($isUsed || $isIdle) ? 'readonly' : '';
          $disabledStyle = ($isUsed || $isIdle) ? 'background-color:#f0f0f0;cursor:not-allowed;' : '';
          
          $readonlyAttrName = $isIdle ? 'readonly' : '';
          $disabledStyleName =  $isIdle ? 'background-color:#f0f0f0;cursor:not-allowed;' : '';

          ?>
          <tr class="<?php echo $rowClass ?>" data-id="<?php echo $def->id; ?>" data-used="<?php echo $isUsed ? '1' : '0'; ?>" style="height:40px;border-bottom: 1px solid #AAAAAA;<?php echo $rowStyle?>">
            <input type="hidden" id="defUsed_<?php echo $def->id; ?>" name="defUsed[<?php echo $def->id; ?>]" value="<?php echo $isUsed ? '1' : '0'; ?>" />
            <input type="hidden" id="defIdle_<?php echo $def->id; ?>" name="defIdle[<?php echo $def->id; ?>]" value="<?php echo $isIdle ? '1' : '0'; ?>" />
            <?php for ($i=1;$i<=5;$i++){
              $idField = "idAbacusable$i";
              $abId = $def->$idField;?>
            <input type="hidden" id="idAbacusable<?php echo $i?>_<?php echo $def->id; ?>" name="idAbacusable<?php echo $i?>[<?php echo $def->id; ?>]" value="<?php echo $abId ?: ''; ?>" />
						<?php }?>
            <!-- ID  -->
             <td style="text-align:center; font-weight: normal;color: #555555; background-color:#f0f0f0; border-right:1px solid #AAAAAA; position:relative;">              
              <?php if ($isUsed && !$isIdle){ ?>
                <span title="<?php echo i18n('abacusDefinitionUsedInLines');?>" style="position:absolute;left:0;top:0;bottom:0;width:6px;background-color:#ec9c29;"></span>
              <?php } ?>            
              <?php echo $def->id; ?>           
            </td>

            <!-- Name -->
            <td class="<?php echo $rowClass ?>" style="padding:2px;border-right:1px solid #AAAAAA;<?php echo $isIdle ? 'background-color:#f0f0f0;' : '';?>">
              <input type="text" name="name[<?php echo $def->id; ?>]" id="name_<?php echo $def->id; ?>" class="input dijitTextBox" onchange="formChanged()" oninput="formChanged()"style="width:97%;border:1px solid transparent;padding:3px !important;outline:none;border-radius:2px;<?php echo $disabledStyleName; ?>"
                value="<?php echo htmlEncode($def->name); ?>" 
                <?php echo $readonlyAttrName; ?>/>
            </td>

            <!-- Class 1 to Class 5 -->
            <?php for ($i=1;$i<=5;$i++){
                    $idField = "idAbacusable$i";
                    $abId = $def->$idField;
                    $currentKey = $abacusableKeyById[$abId] ?? '';?>
            
            <td class="" style="padding:2px;border-right:1px solid #AAAAAA;<?php echo $isUsed ? 'background-color:#f0f0f0;' : '';?>">
              <select dojoType="dijit.form.FilteringSelect"
                      name="className<?php echo $i?>[<?php echo $def->id; ?>]" 
                      id="className<?php echo $i?>_<?php echo $def->id; ?>"
                      class="input" 
                      onchange="formChanged()" 
                      style="width:93%;border:none;padding:3px;<?php echo $disabledStyle; ?>"
                      data-dojo-props="queryExpr: '*${0}*', autoComplete: true"
                      <?php echo $disabledAttr; ?>>
                <?php               
                foreach ($classList as $key => $val) {
                  $selected = ($currentKey === $key) ? 'selected="selected"' : '';
                  echo '<option value="' . htmlEncode($key) . '" ' . $selected . '>' . htmlEncode($val) . '</option>';
                }
                ?>
  						</select>
            </td>
 						<?php }?>
                        
 
            <!-- Phasing -->
            <td class="<?php echo $rowClass ?>" style="padding:2px;border-right:1px solid #AAAAAA;<?php echo $isUsed ? 'background-color:#f0f0f0;' : '';?>">
              <select dojoType="dijit.form.FilteringSelect"
                      name="idPhasing[<?php echo $def->id; ?>]" 
                      id="idPhasing_<?php echo $def->id; ?>"
                      class="input" 
                      onchange="formChanged()" 
                      style="width:93%;border:none;padding:3px;<?php echo $disabledStyle; ?>"
                      data-dojo-props="queryExpr: '*${0}*', autoComplete: true"
                      <?php echo $disabledAttr; ?>>
                <?php
                foreach ($phasingArray as $key => $val) {
                  $selected = ($def->idPhasing == $key) ? 'selected="selected"' : '';
                  echo '<option value="' . htmlEncode($key) . '" ' . $selected . '>' . htmlEncode($val) . '</option>';
                }
                ?>
              </select>
            </td>

            <!-- Unit -->
            <td class="<?php echo $rowClass ?>" style="padding:2px;border-right:1px solid #AAAAAA;<?php echo $isUsed ? 'background-color:#f0f0f0;' : '';?>">
              <select dojoType="dijit.form.FilteringSelect"
                      name="abacusunit[<?php echo $def->id; ?>]" 
                      id="abacusunit_<?php echo $def->id; ?>"
                      class="input" 
                      onchange="formChanged()" 
                      style="width:86%;border:none;padding:3px;<?php echo $disabledStyle; ?>"
                      data-dojo-props="queryExpr: '*${0}*', autoComplete: true"
                      <?php echo $disabledAttr; ?>>
                <?php
                foreach ($unitArray as $key => $val) {
                  $selected = (($def->abacusunit ? $def->abacusunit : 'd') == $key) ? 'selected="selected"' : '';
                  echo '<option value="' . htmlEncode($key) . '" ' . $selected . '>' . htmlEncode($val) . '</option>';
                }
                ?>
              </select>
            </td>
            
            <!-- Assignment Work Type -->
            <td class="<?php echo $rowClass ?>" style="padding:2px;border-right:1px solid #AAAAAA;<?php echo $isUsed ? 'background-color:#f0f0f0;' : '';?>">
              <?php
              // Check if at least one column is a value column
              $hasValueColumn = false;
              for ($i=1;$i<=5;$i++) {
                $id = $def->{"idAbacusable$i"};
                if ($id && isset($abacusableById[$id]) && $abacusableById[$id]->valueField) {
                  $hasValueColumn = true;
                  break;
                }
              }
              
              $currentUnit = $def->abacusunit ? $def->abacusunit : 'd';
              
              $options = [
                  'fixed' => i18n('fixed'),
                  'proportional' => ucfirst(i18n('proportionalOption'))
              ];
              ?>
              <select dojoType="dijit.form.FilteringSelect"
                      name="assignmentWorkType[<?php echo $def->id; ?>]" 
                      id="assignmentWorkType_<?php echo $def->id; ?>"
                      class="input workTypeSelect"
                      data-unit="<?php echo $currentUnit; ?>"
                      data-has-value="<?php echo $hasValueColumn ? '1' : '0'; ?>"
                      onchange="formChanged();" 
                      style="width:93%;border:none;padding:3px;<?php echo $disabledStyle; ?>"
                      data-dojo-props="queryExpr: '*${0}*', autoComplete: true"
                      <?php echo $disabledAttr; ?>>
                <?php
                foreach ($options  as $key => $val) {
                  $selected = (($def->assignmentWorkType ? $def->assignmentWorkType : 'fixed') == $key) ? 'selected="selected"' : '';
                  echo '<option value="' . htmlEncode($key) . '" ' . $selected . '>' . htmlEncode($val) . '</option>';
                }
                ?>
              </select>
            </td>

            <td class="" style="text-align:center;padding:2px;border-right:1px solid #AAAAAA;">
              <div class="iconDown16 iconDown imageColorNewGui iconSize16" style="cursor:pointer;transform: rotate(180deg);margin:0 auto;" title="<?php echo i18n('moveUp'); ?>"
                onclick="moveAbacusDefinitionUp('<?php echo $def->id; ?>');">
              </div>
            </td>

            <td class="" style="text-align:center;padding:2px;border-right:1px solid #AAAAAA;">
              <div class="iconDown16 iconDown imageColorNewGui iconSize16" style="cursor:pointer;margin:0 auto;" title="<?php echo i18n('moveDown'); ?>"
                onclick="moveAbacusDefinitionDown('<?php echo $def->id; ?>');">
              </div>
            </td>

            <td class="" style="text-align:center;padding:2px;">
              <div style="display:flex;align-items:center;justify-content:center;gap:6px;">
                                    
  				<?php if ($isIdle){ ?>
                  <div class="iconClose16 imageColorNewGui iconClose iconSize16" title="<?php echo i18n('abacusDefinitionIdle'); ?>" style="cursor:default;margin:0 auto;"></div>
                <?php } elseif ($isUsed){ ?>
                  <div class="iconLock16 imageColorNewGui iconLock iconSize16" style="cursor:pointer;margin:0 auto;" title="<?php echo i18n('closeAbacusDefinition'); ?>"
                    onclick="closeAbacusDefinition('<?php echo $def->id; ?>');">
                  </div>
                <?php }else{ ?>
                  <div class="iconRemove16 imageColorNewGui iconRemove iconSize16" style="cursor:pointer;margin:0 auto;" title="<?php echo i18n('delete'); ?>"
                    onclick="deleteAbacusDefinitionLine('<?php echo $def->id; ?>');">
                  </div>
                <?php }?>
                
                <a onclick="copyAbacusDefinition(this);" style="cursor:pointer;"data-id="<?php echo $def->id; ?>"data-name="<?php echo htmlEncode($def->name); ?>"title="<?php echo i18n('abacusDefinitionCopy'); ?>">
                  <?php echo formatSmallButton('Copy'); ?>
                </a>
              
              </div>
            </td>
          </tr>
          <?php
        }
      } else {
        ?>
        <tr>
          <td colspan="13" style="text-align:center;padding:15px;color:#999;">
            <?php echo i18n('noDataFound'); ?>
          </td>
        </tr>
        <?php
      }
      ?>
    </tbody>
  </table>
</div>