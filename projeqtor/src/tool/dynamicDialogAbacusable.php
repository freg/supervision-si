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

  $abacusable = new Abacusable();
  $critWhere="1=1";
  $listAbacusable = $abacusable->getSqlElementsFromCriteria(null, false, $critWhere);
  $lineList=SqlList::getListNotTranslated('menuReadWriteList');
  $lineList = array_map(function($value) {
    return pq_substr($value, 4);
  }, $lineList);
    
  $lineList = array_merge($lineList, [
    'Resource' => 'Resource',
    'ResourceTeam' => 'ResourceTeam',
    'ResourceOrTeam' => 'ResourceOrTeam',
    'ResourceFromTeam' => 'ResourceFromTeam',
  ]);
    
  $translatedList = [];
  foreach($lineList as $key => $value) {
    $translatedList[$value] = i18n($value);
  }
  $lstCustom=getCustomClassList();
  $translatedList = array_merge($translatedList, $lstCustom);
  asort($translatedList);
  usort($listAbacusable, function($a, $b) {
    return strcmp(i18n($a->className), i18n($b->className));
  });

  // Check which Abacusables are used in AbacusDefinitions
  $usedAbacusables = array();
  $abacusDefinition = new AbacusDefinition();
  $allDefinitions = $abacusDefinition->getSqlElementsFromCriteria(null, false, "1=1");
  foreach ($allDefinitions as $def) {
    for ($i = 1; $i <= 5; $i++) {
      $field = "idAbacusable$i";
      if (!empty($def->$field)) {
        $usedAbacusables[$def->$field] = true;
      }
    }
  }
?>

<div style="padding:10px;overflow:auto;max-height:550px;">
  <form id="abacusableForm" name="abacusableForm">
  
    <div style="padding:10px;margin-bottom:15px;">
      <div style="display:flex;align-items:center;gap:10px;">
    
        <label style="white-space:nowrap;">
          <?php echo i18n('CLASS'); ?> :
        </label>
    
				<select dojoType="dijit.form.FilteringSelect" id="newClassNameAbacusable" name="newClassNameAbacusable" class="input" style="flex:1;padding:3px;"
          <?php echo autoOpenFilteringSelect();?>>
          <option value=" "></option>
          <?php foreach ($translatedList as $name=>$translated) { 
            $count = 0;
            $hasValue = class_exists($name) && property_exists($name, 'value');            
            foreach ($listAbacusable as $item) {
              if ($item->className == $name) {
                $count++;
              }
            }           
            $max = $hasValue ? 3 : 1;            
            if ($count < $max) { ?>
            <option value="<?php echo htmlEncode($name); ?>">
              <?php echo htmlEncode($translated); ?>
            </option>
          <?php } 
          } ?>
        </select>
    
        <div id="addAbacusable" title="<?php echo i18n('addAbacusable'); ?>" onclick="addAbacusableItem();" style="cursor:pointer;padding:5px;">
          <div class="iconAdd22 imageColorNewGui iconAdd iconSize22"></div>
        </div>
    
      </div>
    </div>

    
    <table width="100%" style="margin-bottom:15px;">
      <thead>
        <tr class="" style="height:42px">
          <th class="assignHeader" style="width:7%;text-align:center;padding:5px"></th>
          <th class="assignHeader" style="width:5%;text-align:center;padding:5px"><?php echo ucfirst(i18n('colId')); ?></th>
          <th class="assignHeader" style="width:62%;text-align:center;padding:5px"><?php echo i18n('CLASS'); ?></th>
          <th class="assignHeader" style="width:13%;text-align:center;padding:5px;position: relative;" title="<?php echo i18n('tooltipValueField'); ?>" > <?php echo ucfirst(i18n('colValue')); ?>
           <span id="infoIconValueAbacusable" class="iconInfo12 iconInfo iconSize12 imageColorNewGui" style="cursor:help;top:3px;position: absolute;right: 3px;" data-info-text="<?php echo i18n('tooltipValueField'); ?>"></span>
          </th>
          <th class="assignHeader" style="width:13%;text-align:center;padding:5px;position: relative" title="<?php echo i18n('tooltipInputField'); ?>" > <?php echo ucfirst(i18n('input')); ?>
          	<span id="infoIconInputAbacusable" class="iconInfo12 iconInfo iconSize12 imageColorNewGui" style="cursor:help;top:3px;position: absolute;right: 3px;" data-info-text="<?php echo i18n('tooltipInputField'); ?>"></span>
          </th>
        </tr>
      </thead>
      <tbody id="abacusableTableBody">
        <?php
        if (count($listAbacusable) > 0) {
          foreach ($listAbacusable as $item) {            
            $hasValueProperty = false;
            if (class_exists($item->className)) {
              $hasValueProperty = property_exists($item->className, 'value');
            }
            $isUsed = isset($usedAbacusables[$item->id]);
            
            ?>
            <tr id="abacusableRow_<?php echo $item->id; ?>" style="height:32px;">
            
            <td class="assignData" style="text-align:center;padding:2px; vertical-align: middle; position:relative;">            
              <?php if ($isUsed) { ?>
                <div title="<?php echo i18n('abacusableUsed');?>" style="position:absolute;left:0;top:0;bottom:0;width:6px;background-color:#ec9c29;"></div>
              <?php } ?>            
              <a title="<?php echo ucfirst(i18n('deleteButton')); ?>" onclick="deleteAbacusable(<?php echo $item->id; ?>);">
                <?php echo formatSmallButton('Remove') ?>
              </a>            
            </td>
              
              <td class="assignData" style="text-align:center; vertical-align: middle;">
                <?php echo $item->id; ?>
              </td>
              
              <td class="assignData" style="padding:2px;vertical-align: middle;">
                <div name="className_<?php echo $item->id; ?>" value="<?php echo htmlEncode($item->className); ?>" 
                  style="width:98%;padding:3px;"readonly title="<?php echo i18n(htmlEncode($item->className)); ?>">
                  <?php echo i18n(htmlEncode($item->className)); ?></div>
              </td>
              
              <td class="assignData" style="text-align:center;padding:2px;vertical-align: middle;">
              <?php if ($hasValueProperty){?>
                <div id="valueField_<?php echo $item->id; ?>" name="valueField_<?php echo $item->id; ?>" dojoType="dijit.form.CheckBox" type="checkbox"
                  value="<?php echo $item->valueField; ?>"
                  <?php echo ($item->valueField == 1) ? 'checked="checked"' : ''; ?>>
                  <script type="dojo/connect" event="onChange" args="checked">
                    toggleInputFieldAbacusable(<?php echo $item->id; ?>, checked);
                  </script>                 
                </div>
              <?php }?>
              </td>
              
              <td class="assignData" style="text-align:center;padding:2px;vertical-align: middle;">
              <?php if ($hasValueProperty){?>
                <div id="inputField_<?php echo $item->id; ?>" name="inputField_<?php echo $item->id; ?>" dojoType="dijit.form.CheckBox" type="checkbox"
                value="<?php echo $item->inputField; ?>"
                  <?php echo $item->valueField != 1 ? 'disabled="disabled"' : '' ?>
                  <?php echo $item->inputField ? 'checked="checked"' : ''; ?>">
                </div>
              <?php }?>
              </td>
              
            </tr>
            <?php
          }
        } else {
          ?>
          <tr>
            <td colspan="4" style="text-align:center;padding:15px;color:#999;">
              <?php echo i18n('noDataFound'); ?>
            </td>
          </tr>
          <?php
        }
        ?>
      </tbody>
    </table>
  
      <div style="text-align:center;margin-top:20px;">
        <input type="hidden" id="dialogAbacusableAction">
        <button class="mediumTextButton" dojoType="dijit.form.Button" type="button" onclick="dijit.byId('dialogAbacusable').hide();">
          <?php echo i18n("buttonCancel");?>
        </button>
        <button class="mediumTextButton" dojoType="dijit.form.Button" type="submit" id="dialogAbacusableSubmit" onclick="protectDblClick(this);saveAbacusable();return false;" style="margin-left:10px;">
          <?php echo i18n("buttonOK");?>
        </button>
      </div>
   </form> 
</div>