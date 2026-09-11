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
$keyDownEventScript=NumberFormatter52::getKeyDownEvent();

$idAbacus = RequestHandler::getId('idAbacus');
$idAbacusProject = RequestHandler::getId('idAbacusProject');
$abacusProject = null;
$isEdit = false;

if ($idAbacusProject) {
  $abacusProject = new AbacusProject($idAbacusProject);
  $isEdit = true;
  $idAbacus = $abacusProject->idAbacusDefinition;
}

$abacus = new AbacusDefinition($idAbacus);

$abacusLine = new AbacusLine();
$allLines = $abacusLine->getSqlElementsFromCriteria(array('idAbacusDefinition' => $idAbacus));

$isBasedOnClosedLine = false;
if ($isEdit && $abacusProject) {
  foreach ($allLines as $line) {
    $matchesProject = true;    
    for ($i = 1; $i <= 5; $i++) {
      $idField = 'idClassName' . $i;     
      $projectValue = $abacusProject->$idField ?? null;
      $lineValue    = $line->$idField ?? null;      
      if ($projectValue != $lineValue) {
        $matchesProject = false;
        break;
      }
    }    
    if ($matchesProject) {
      if ($line->idle == 1) $isBasedOnClosedLine = true;      
      break;
    }
  }
}

if (!$isEdit || !$isBasedOnClosedLine) {
  $abacusLineList = $abacusLine->getSqlElementsFromCriteria(array('idAbacusDefinition' => $idAbacus,'idle' => '0'));
} else {
  $abacusLineList = $allLines;
}

// Lines
$classData = array();
$maxClassNum = 0;

for ($i = 1; $i <= 5; $i++) {
  $className = 'className' . $i;
  $idClassName = 'idClassName' . $i;
  $idAbacusable = 'idAbacusable' . $i;
  if (!empty($abacus->$className)) {
    $isResourceOrTeam = ($abacus->$className === 'ResourceOrTeam');
    $isResourceFromTeam = ($abacus->$className === 'ResourceFromTeam');
    
    $classData[$i] = array(
        'name'                => $abacus->$className,
        'lines'               => array(),
        'isResourceOrTeam'    => $isResourceOrTeam,
        'isResourceFromTeam'  => $isResourceFromTeam
    );
    
    if ($isResourceOrTeam || $isResourceFromTeam) {
      $poolIds = array();
      foreach ($abacusLineList as $line) {
        if (!empty($line->$idClassName)) {
          $poolIds[$line->$idClassName] = true;
        }
      }
      
      foreach (array_keys($poolIds) as $poolId) {
        $pool = new ResourceOrTeam($poolId);
        
        // For ResourceFromTeam: don't add the pool itself, only resources
        if (!$isResourceFromTeam) {
          $classData[$i]['lines'][$pool->id] = array(
              'id'     => $pool->id,
              'name'   => $pool->name,
              'indent' => true,
              'idPool' => $pool->id
          );
        }
        
        // Add resources for both ResourceOrTeam and ResourceFromTeam
        foreach ($pool->getActiveResources(false,true) as $resource) {
          $classData[$i]['lines'][$resource->id] = array(
              'id'     => $resource->id,
              'name'   => $resource->name,
              'indent' => false,
              'idPool' => $poolId
          );
        }
      }
    } else {
      $classObj = new $abacus->$className();
      
      if ($isEdit) {
        $classList = $classObj->getSqlElementsFromCriteria(null, false, null, 'name ASC');
      } else {
        $classList = $classObj->getSqlElementsFromCriteria(array('idle' => '0'), false, null, 'name ASC');
      }
      
      $abacusable = new Abacusable($abacus->$idAbacusable);
      $isValueField = !empty($abacusable) && $abacusable->valueField == 1;
      
      if ($isValueField) {
        foreach ($classList as $classItem) {
          $includeItem = !$classItem->idle || ($isEdit && $isBasedOnClosedLine);        
          if ($includeItem) {
            $displayName = $classItem->name;
            if (property_exists($classItem, 'value') && is_numeric($classItem->value)) {
              $displayName .= ' (' . htmlDisplayNumeric($classItem->value) . ')';
            }
            $classData[$i]['lines'][$classItem->id] = array(
                'id'     => $classItem->id,
                'name'   => $displayName,
                'indent' => true,
                'idPool' => $classItem->id,
                'isIdle' => ($classItem->idle == 1)
            );
          }
        }
      } else {
        foreach ($classList as $classItem) {
          $shouldInclude = false;
          
          foreach ($abacusLineList as $line) {
            if (!empty($line->$idClassName) && $line->$idClassName == $classItem->id) {
              if ($isEdit || $line->idle == 0) {
                $shouldInclude = true;
                break;
              }
            }
          }
          
          if ($shouldInclude) {
            $classData[$i]['lines'][$classItem->id] = array(
                'id'     => $classItem->id,
                'name'   => $classItem->name,
                'indent' => true,
                'idPool' => $classItem->id,
                'isIdle' => ($classItem->idle == 1)
            );
          }
        }
      }
    }
    $maxClassNum = $i;
  }
}

$isValueFieldMap = array();
$isInputFieldMap = array();
for ($i = 1; $i <= 5; $i++) {
  $className = 'className' . $i;
  $idAbacusable = 'idAbacusable' . $i;
  if (!empty($abacus->$className)) {
    $abacusable = new Abacusable($abacus->$idAbacusable);
    $isValueFieldMap[$i] = !empty($abacusable) && $abacusable->valueField == 1 && $abacusable->inputField == 0;
    $isInputFieldMap[$i] = ($abacusable->inputField==1);
  } else {
    $isValueFieldMap[$i] = false;
    $isInputFieldMap[$i] = false;
  }
}

$hasPoolField = false;
$poolClassNums = array();
for ($i = 1; $i <= 5; $i++) {
  $className = 'className' . $i;
  if (!empty($abacus->$className)) {
    $cn = $abacus->$className;
    if ($cn === 'ResourceTeam' || $cn === 'Team' || $cn === 'ResourceOrTeam' || $cn === 'ResourceFromTeam') {
      $hasPoolField = true;
      $poolClassNums[] = $i;
    }
  }
}
$initialCapacityVisible = false;
if ($isEdit && $abacusProject && $hasPoolField) {
  foreach ($poolClassNums as $pNum) {
    $cn = 'className' . $pNum;
    $idField = 'idClassName' . $pNum;
    $classType = $abacus->$cn;
    if ($classType === 'ResourceTeam' || $classType === 'Team') {
      if ($abacusProject->$idField) { $initialCapacityVisible = true; break; }
    } else if ($classType === 'ResourceOrTeam') {
      // Only if pool sélectionné (not ref)
      if ($abacusProject->$idField && !$abacusProject->idClassNameRef) {
        $initialCapacityVisible = true; break;
      }
    }
  }
}

// Dependencies : AbacusLines
$dependencies = array();
foreach ($abacusLineList as $line) {
  if (!$isEdit && $line->idle == 1) continue;  
  
  for ($i = 1; $i <= 5; $i++) {
    $idClassName = 'idClassName' . $i;
    
    if (!empty($line->$idClassName) || $isValueFieldMap[$i]) {
      $key = '';
      
      for ($j = 1; $j < $i; $j++) {
        $prevIdClassName = 'idClassName' . $j;
        // Ignore level with valueField
        if (!empty($line->$prevIdClassName) && !$isValueFieldMap[$j]) {
          $key .= ($key ? '_' : '') . $line->$prevIdClassName;
        }
      }
      
      if (!isset($dependencies[$i])) $dependencies[$i] = array();
      if (!isset($dependencies[$i][$key])) $dependencies[$i][$key] = array();
      
      // If valueField = all values
      $entryId = $isValueFieldMap[$i] ? null : $line->$idClassName;
      $alreadyAdded = false;
      if ($isValueFieldMap[$i]) {
        foreach ($dependencies[$i][$key] as $existing) {
          if ($existing['id'] === null) {
            $alreadyAdded = true;
            break;
          }
        }
      }
      
      if (!$alreadyAdded) {
        $dependencies[$i][$key][] = array(
            'id'         => $entryId,
            'assumption' => $line->assumption,
            'example'    => $line->example,
            'valueField' => $isValueFieldMap[$i],
            'inputField' => $isInputFieldMap[$i]
        );
      }
    }
  }
}

?>
 
<div style="padding:10px;overflow:auto;">
  <form dojoType="dijit.form.Form" id="abacusProjectLineForm" name="abacusProjectLineForm" onSubmit="return false;">
    
    <table style="width:100%;">
      <tr>
        <td colspan="2">
          <table style="width:100%;">
            <?php if ($isEdit && $isBasedOnClosedLine){ ?>
            <tr>
              <td colspan="2" style="padding:10px;">
                <div style="background-color:#fff3cd;border:1px solid #ffc107;padding:10px;border-radius:4px;color:#856404;max-width: 800px;">
                  <?php echo i18n('warningAbacusLineIsClosed'); ?>
                </div>
              </td>
            </tr>
            <?php } ?>
            <tr>
              <td class="dialogLabel" style="width:20%;">
                <label><?php echo i18n('colAbacusUsed');?> &nbsp;&nbsp;</label>
              </td>
              <td>
                <div class="dijitInline" style="width:100%;">
                  <?php echo htmlEncode($abacus->name); ?>
                </div>
              </td>
            </tr>
          </table>
        </td>
      </tr>
      
      <tr>
        <td style="width:50%; vertical-align:top; padding-right:10px;">
          <table style="width:100%;">
            <?php foreach ($classData as $classNum => $data){ ?>
            <tr>
            <div>
 
              <td class="dialogLabel"  style="width:20%;padding-top:<?= $classNum == 1 ? '17px;' : '5px;' ?>">
              
                <label><?php echo i18n(htmlEncode($data['name'])); ?> &nbsp;&nbsp;</label>
              </td>
								<td style="padding-top:<?= $classNum == 1 ? '17px;' : '5px;' ?>">
                <?php if ($classNum == 1) { ?>
                  <select id="idClassName<?php echo $classNum; ?>" name="idClassName<?php echo $classNum; ?>" <?php echo autoOpenFilteringSelect();?>
                          dojoType="dijit.form.FilteringSelect" class="input" required="required" 
                          style="width:100%;border-left:3px solid red !important;<?php echo ($isEdit && $isBasedOnClosedLine) ? 'pointer-events:none;opacity:0.6;background-color:#f5f5f5;' : ''; ?>" 
                          onChange="refreshAbacusLists(<?php echo $classNum; ?>);"
                          <?php echo ($isEdit && $isBasedOnClosedLine) ? 'data-readonly="true"' : ''; ?>>
                    <option value=""></option>
                    <?php foreach ($data['lines'] as $line) { 
                      $idField = 'idClassName' . $classNum;
                      
                      // For ResourceFromTeam: only allow resource selection, not pool
                      if ($data['isResourceFromTeam'] && $line['indent']) {
                        continue; // Skip pools for ResourceFromTeam
                      }
                      
                      // En mode création, ne pas afficher les éléments issus de lignes closes
                      if (!$isEdit && isset($line['isIdle']) && $line['isIdle']) {
                        continue;
                      }
                      
                      $selected = ($isEdit && $abacusProject->$idField == $line['idPool'] && 
                                   ((!$isEdit) || ($abacusProject->idClassNameRef == $line['id'] || ($line['indent'] && !$abacusProject->idClassNameRef)))) 
                                  ? 'selected="selected"' : '';
                     if ($data['isResourceFromTeam']) $displayName = htmlEncode($line['name']);
                     else $displayName = $line['indent'] ? htmlEncode($line['name']) : '_ ' . htmlEncode($line['name']);                                  
                    ?>
                      <option value="<?php echo $line['id']; ?>" <?php echo $selected; ?>>
                        <?php echo $displayName; ?>
                      </option>
                    <?php } ?>
                  </select>
                <?php } else { ?>
                  <div id="idClassName<?php echo $classNum; ?>" name="idClassName<?php echo $classNum; ?>" <?php echo autoOpenFilteringSelect();?> dojoType="dijit.form.FilteringSelect" searchAttr="name" class="input" 
                       style="width:100%;border-left:3px solid red !important;<?php echo ($isEdit && $isBasedOnClosedLine) ? 'pointer-events:none;opacity:0.6;background-color:#f5f5f5;' : ''; ?>" 
                       required="required" 
                       disabled="disabled"
                       <?php echo ($isEdit && $isBasedOnClosedLine) ? 'data-readonly="true"' : ''; ?>
                       onChange="refreshAbacusLists(<?php echo $classNum; ?>);"></div>
                <?php } ?>
              </td>
              <?php if ($data['name'] == 'Resource') {?>
              <td style="padding-left:16px;padding-top:<?= $classNum == 1 ? '17px;' : '5px;' ?>">
                 <button id="abacusResourceDetailButton<?php echo $classNum; ?>" dojoType="dijit.form.Button" showlabel="false"
                   title="<?php echo i18n('showDetail')?>"
                   iconClass="iconSearch22 iconSearch iconSize22 imageColorNewGui" class="notButton notButtonRounded">
                   <script type="dojo/connect" event="onClick" args="evt">
                    var canCreate=("<?php echo securityGetAccessRightYesNo('menuProject','create');?>"=="YES")?1:0;
                    showDetail('abacusResource<?php echo $classNum; ?>', canCreate , 'Resource', false);
                   </script>
                 </button>
               </td> 
               <?php } ?>
            </tr>
            </div>
            <?php }?>
          </table>
          
         <table style="width:100%;">
            <tr>
              <td class="dialogLabel" style="width:20%;padding-top:5px;">
                <label><?php echo ucfirst(i18n('quantity')); ?> &nbsp;&nbsp;</label>
              </td>
              <td style="padding-top:5px;">
								<div id="abacusQuantity" name="abacusQuantity" dojoType="dijit.form.NumberTextBox" type="text" class="input" style="width:150px;" constraints="{min:0}"
       				 			 value="<?php echo $isEdit ? htmlEncode($abacusProject->quantity) : '1'; ?>" /> 
       			 		<?php echo $keyDownEventScript;?>
       					</div>
              </td>
            </tr>
            
            <tr id="abacusCapacityRow" style="display:<?php echo ($hasPoolField && $initialCapacityVisible) ? 'table-row' : 'none'; ?>;">
              <td class="dialogLabel" style="width:20%;padding-top:5px;">
                <label><?php echo ucfirst(i18n('colCapacity')); ?> &nbsp;&nbsp;</label>
              </td>
              <td style="padding-top:5px;">
                <div id="abacusCapacity" name="abacusCapacity" dojoType="dijit.form.NumberTextBox" type="text" class="input" style="width:150px;" constraints="{min:0}"
                     value="<?php echo $isEdit ? htmlEncode($abacusProject->capacity ?? '') : '1'; ?>" />
                <?php echo $keyDownEventScript; ?>
                </div>
              </td>
            </tr>
            <tr>
              <td class="dialogLabel" style="width:20%;padding-top:5px;">
                <label><?php echo ucfirst(i18n('idle')); ?> &nbsp;&nbsp;</label>
              </td>
              <td style="padding-top:5px;">
                <div id="abacusIdle" name="abacusIdle" dojoType="dijit.form.CheckBox" type="checkbox" 
                     <?php echo ($isEdit && $abacusProject->idle == 1) ? 'checked' : ''; ?> />
              </td>
            </tr>
          </table>
          
        </td>
        
        <td style="width:50%; vertical-align:top; padding-left:20px;">
          <table style="width:100%;">
            <tr>
              <td class="dialogLabel" style="vertical-align:top;">
                <label style="display:inline-block; text-align:left;"><?php echo i18n('menuAssumption'); ?></label>
              </td>
            </tr>
            <tr>
              <td>
                <div id="globalAssumption" style="font-style:italic; min-height:80px; max-height:80px; overflow-y:auto; padding:5px; background-color:#f9f9f9; border:1px solid #ddd; border-radius: 4px;">
                  
                </div>
              </td>
            </tr>
            <tr>
              <td class="dialogLabel" style="vertical-align:top; padding-top:10px;">
                <label style="display:inline-block; text-align:left;"><?php echo i18n('colExamples'); ?></label>
              </td>
            </tr>
            <tr>
              <td>
                <div id="globalExample" style="font-style:italic; min-height:80px; max-height:80px; overflow-y:auto; padding:5px; background-color:#f9f9f9; border:1px solid #ddd; border-radius: 4px;">
                  
                </div>
              </td>
            </tr>
          </table>
        </td>
      </tr>
      
      
      <tr>
        <td colspan="2">
          <table style="width:100%;">
            <tr>
              <td class="dialogLabel" style="width:15%; vertical-align:top;padding-top:15px;">
                <label><?php echo ucfirst(i18n('colComment'));?> &nbsp;&nbsp;</label>
              </td>
              <td style="padding-top:15px;">
                <textarea id="abacusProjectcomment" name="abacusProjectcomment" dojoType="dijit.form.Textarea" class="input" style="width:100%;min-height:50px;max-height:85px;" maxlength="4000"></textarea>
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
 
    <div style="text-align:center;margin-top:20px;">
      <input type="hidden" id="dialogAbacusProjectLineAction" value="<?php echo $isEdit ? 'update' : 'add'; ?>">
      <input type="hidden" id="idAbacusDefinition" name="idAbacusDefinition" value="<?php echo $idAbacus; ?>">
      <input type="hidden" id="isBasedOnClosedLine" value="<?php echo $isBasedOnClosedLine ? '1' : '0'; ?>">
      <?php if ($isEdit) { ?>
 			  <input type="hidden" id="idAbacusProject" name="idAbacusProject" value="<?php echo $idAbacusProject; ?>">
        <input type="hidden" id="abacusInitialValues" value='<?php 
          $initVals = array();
          for ($i = 1; $i <= 5; $i++) {
            $idField = 'idClassName' . $i;
            $initVals[$i] = $abacusProject->$idField ?? '';
          }
          $initVals['ref'] = $abacusProject->idClassNameRef ?? '';
          echo htmlspecialchars(json_encode($initVals), ENT_QUOTES, 'UTF-8'); ?>'>
			<?php } ?>
      <input type="hidden" id="abacusDependencies" name="abacusDependencies" value='<?php echo htmlspecialchars(json_encode($dependencies), ENT_QUOTES, 'UTF-8'); ?>'>
      <input type="hidden" id="abacusClassData" name="abacusClassData" value='<?php echo htmlspecialchars(json_encode($classData), ENT_QUOTES, 'UTF-8'); ?>'>
      <input type="hidden" id="abacusLineList" name="abacusLineList" value='<?php echo htmlspecialchars(json_encode($abacusLineList), ENT_QUOTES, 'UTF-8'); ?>'>
      <input type="hidden" id="abacusMaxClassNum" name="abacusMaxClassNum" value="<?php echo $maxClassNum; ?>">
      <input type="hidden" id="abacusPoolClassNums" value='<?php echo htmlspecialchars(json_encode($poolClassNums), ENT_QUOTES, "UTF-8"); ?>'>
			<input type="hidden" id="abacusHasPoolField" value="<?php echo $hasPoolField ? '1' : '0'; ?>">
       
      <button class="mediumTextButton" dojoType="dijit.form.Button" type="button" onclick="dijit.byId('dialogAbacusProjectLine').hide();">
        <?php echo i18n("buttonCancel");?>
      </button>
      <button class="mediumTextButton" dojoType="dijit.form.Button" type="submit" id="dialogAbacusProjectSubmit" onclick="protectDblClick(this);saveAbacusProject();return false;" style="margin-left:10px;">
        <?php echo i18n("buttonOK");?>
      </button>
    </div>
  </form>
</div>