<?PHP
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

/** ===========================================================================
 * Markup of the plannable project list : a hidden native select holding the
 * state, and the container the visible list is drawn into by projeqtorPlanSelect.js
 */

/** Opening tag of the hidden select. Options are echoed by the caller, which
 * marks the selected ones itself : no value attribute is emitted, because the
 * widget would then deselect every option missing from it. */
function planProjectSelectOpen() {
  $s ='<div id="pqPlanSelectHolder" style="position:absolute;width:0;height:0;overflow:hidden;">';
  $s.='<select dojoType="dijit.form.MultiSelect" class="selectPlan" multiple="true"';
  $s.=' id="idProjectPlan" name="idProjectPlan[]" onChange="changedIdProjectPlan(this.value);">';
  return $s;
}

/** Closing tag of the hidden select, followed by the visible list container.
 * The inner wrapper keeps the class the stylesheet sizes, so the list holds the
 * width the dialog is built around. */
function planProjectSelectClose() {
  $s ='</select></div>';
  $s.='<div class="selectPlan">';
  $s.='<div id="pqPlanList" class="dojoxCheckedMultiSelectWrapper"';
  $s.=' style="border:1px solid #A0A0A0;height:218px;max-height:218px;';
  $s.='overflow-y:auto;overflow-x:hidden;background:#FFFFFF;"></div>';
  $s.='</div>';
  return $s;
}
