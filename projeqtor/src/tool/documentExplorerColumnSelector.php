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

if (! isset($explorerType)) $explorerType = 'directory';
$documentExplorerDesc = Parameter::getDocumentExplorerColumnDescription($explorerType);

foreach ($documentExplorerDesc as $col => $desc) {
  if (! isset($desc['name'])) continue;
  $id       = $explorerType . $col;                 // suffixe unique par liste
  $show     = (! empty($desc['show'])) ? 1 : 0;
  // Name is the tree column : neither hideable nor movable.
  $isName   = ($col == 'Name');
  $minWidth = isset($desc['minWidth']) ? $desc['minWidth'] : 50;
  $label    = (isset($desc['label']) and $desc['label'] !== '') ? $desc['label'] : i18n('col' . $col);

  if ($isName) {
    echo '<div style="position:relative;padding:2px;width:100%;height:34px;cursor:default" id="documentExplorerColumnSelector' . $id . '">';
    echo '<span style="display:inline-block;width:15px;float:left;"><img style="width:6px" src="css/images/iconNoDrag.gif" />&nbsp;&nbsp;</span>';
  } else {
    echo '<div style="position:relative;padding:2px;width:100%;height:34px;cursor:default" class="dojoDndItem" id="documentExplorerColumnSelector' . $id . '" dndType="documentExplorerColumn' . $explorerType . '">';
    echo '<span style="float:left;" class="dojoDndHandle handleCursor"><img style="width:10px;position:relative;top:8px;left:5px" src="css/images/iconDrag.gif" />&nbsp;&nbsp;</span>';
  }

  $idLocked      = ($col == 'Id' and $explorerType == 'document');
  $disabledClass = ($isName or $idLocked) ? 'mblSwitchDisabled' : '';
  echo '<div id="documentExplorerCheckColumn' . $id . 'Sw" class="colorSwitch ' . $disabledClass . '" data-dojo-type="dojox/mobile/Switch"'
     . ' value="' . (($show == 1) ? 'on' : 'off') . '" leftLabel="" rightLabel=""'
     . ' style="position:relative;float:left;left:5px;top:11px;z-index:99;">';
  echo '<script type="dojo/method" event="onStateChanged">';
  echo '  dijit.byId("documentExplorerCheckColumn' . $id . '").set("checked",(this.value=="on")?true:false);';
  echo '</script>';
  echo '</div>';

  echo '<span dojoType="dijit.form.CheckBox" type="checkbox" id="documentExplorerCheckColumn' . $id . '" style="display:none"'
     . (($show == 1) ? ' checked="checked"' : '')
     . ($isName ? ' readonly' : '')
     . ' onChange="documentExplorerChangeColumn(\'' . $col . '\',this.checked,\'' . $explorerType . '\');"'
     . '></span>';
  echo '<label for="documentExplorerCheckColumn' . $id . '" class="checkLabel"'
     . ' style="position:relative;top:9px;float:none;left:15px;white-space:nowrap">&nbsp;' . $label . '</label>';

  echo '<div style="position:absolute;right:2px;top:0px;text-align:right">&nbsp;';
  echo '<div dojoType="dijit.form.NumberSpinner" id="documentExplorerColumnWidth' . $id . '"'
     . (($show == 0) ? ' disabled="disabled"' : '')
     . ' onChange="documentExplorerChangeColumnWidth(\'' . $col . '\',this.value,\'' . $explorerType . '\');"'
     . ' constraints="{ min:' . $minWidth . ', max:500, places:0 }"'
     . ' style="width:50px;text-align:center;" value="' . htmlEncode($desc['width']) . '">';
  echo '</div>';
  echo '&nbsp;</div>';
  echo '</div>';
}
?>
