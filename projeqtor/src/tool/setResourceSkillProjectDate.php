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
require_once "../tool/formatter.php";
scriptLog('   ->/tool/refreshButtonAutoSendReport.php');

$idProject = RequestHandler::getId('listProjectFilter');
$useSinceSkill = RequestHandler::getValue('skillUseSince');
$useUntilSkill = RequestHandler::getValue('skillUseUntil');
$project = new Project($idProject);

$useSince = $project->ProjectPlanningElement->validatedStartDate;
if(!$useSince)$useSince = $project->ProjectPlanningElement->plannedStartDate;
if(!$useSince)$useSince = date('Y-m-d');
$useUntil= $project->ProjectPlanningElement->validatedEndDate;
if(!$useUntil)$useUntil = $project->ProjectPlanningElement->plannedEndDate;
if(!$useUntil)$useUntil = addMonthsToDate(date('Y-m-d'), 1);
?>
<table>
  <tr>
    <td rowspan="2" ><?php echo i18n('disponibility')?></td>
    <td style="vertical-align: middle; text-align: right;"
      width="5px">
      <span class="nobr">&nbsp;&nbsp;&nbsp;
          <?php echo i18n("colStart");?>
          &nbsp;</span>
    </td>
     <td width="5px">
       <div dojoType="dijit.form.DateTextBox"
        <?php if (sessionValueExists('browserLocaleDateFormatJs')) {
					echo ' constraints="{datePattern:\''.getSessionValue('browserLocaleDateFormatJs').'\'}" ';
				 }?>
         id="skillUseSince" name="skillUseSince"
         invalidMessage="<?php echo i18n('messageInvalidDate')?>"
         type="text" maxlength="10"
         style="width:100px; text-align: center;" class="input roundedLeft"
         hasDownArrow="true"
         value="<?php echo $useSince;?>" >
         <script type="dojo/method" event="onChange" >
                 var start=dijit.byId('skillUseSince').get("value");
                 var end=dijit.byId('skillUseUntil').get('value');
                 saveDataToSession('skillUseSince',formatDate(start), false);
                 refreshResourceSkillList();
               </script>
       </div>
     </td>
  </tr>
  <tr>
     <td style="vertical-align: middle; text-align: right;"
      width="5px">
      <span class="nobr">&nbsp;&nbsp;&nbsp;
          <?php echo i18n("colEnd");?>
          &nbsp;</span>
    </td>
     <td width="5px">
     <div dojoType="dijit.form.DateTextBox"
         <?php if (sessionValueExists('browserLocaleDateFormatJs')) {
					echo ' constraints="{datePattern:\''.getSessionValue('browserLocaleDateFormatJs').'\'}" ';
				 }?>
         id="skillUseUntil" name="skillUseUntil"
         type="text" maxlength="10" hasDownArrow="true"
         style="width:100px; text-align:center;" class="input roundedLeft"
         value="<?php echo $useUntil;?>" >
         <script type="dojo/method" event="onChange" >
                          var start=dijit.byId('skillUseSince').get("value");
                          var end = dijit.byId('skillUseUntil').get('value');
                          saveDataToSession('skillUseUntil',formatDate(end), false);
                          refreshResourceSkillList();
                       </script>  
       </div>
     </td>
  </tr>
</table>