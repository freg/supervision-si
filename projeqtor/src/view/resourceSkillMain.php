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
scriptLog('   ->/view/resourceSkillMain.php');
// florent
$currentScreen='ResourceSkill';
setSessionValue('currentScreen', $currentScreen);
$notResourceSkillSimple=RequestHandler::getBoolean('notResourceSkillSimple');
$skill=new Skill();
$idSkill=getSessionValue('listSkillFilter');
$idSkillLevel=getSessionValue('listSkillLevelFilter');
$showPeriodDisponibility=(getSessionValue('showPeriodDisponibility'))?getSessionValue('showPeriodDisponibility'):'showGlobalDisponibility';
$idProject=getSessionValue('listProjectFilter');
$strictLevelCheck = getSessionValue('strictLevelCheck');
if($idProject){
	$project = new Project($idProject);
	$useSince = $project->ProjectPlanningElement->validatedStartDate;
	if(!$useSince)$useSince = $project->ProjectPlanningElement->plannedStartDate;
	if(!$useSince)$useSince = date('Y-m-d');
	$useUntil= $project->ProjectPlanningElement->validatedEndDate;
	if(!$useUntil)$useUntil = $project->ProjectPlanningElement->plannedEndDate;
	if(!$useUntil)$useUntil = addMonthsToDate(date('Y-m-d'), 1);
}else{
  $useSince=(getSessionValue('skillUseSince'))?getSessionValue('skillUseSince'):date('Y-m-d');
  $useUntil=(getSessionValue('skillUseUntil'))?getSessionValue('skillUseUntil'):addMonthsToDate(date('Y-m-d'), 1);
}
$sortBy = (getSessionValue('sortByFilter'))?pq_trim(getSessionValue('sortByFilter')):'global';

RequestHandler::setValue('showPeriodDisponibility', $showPeriodDisponibility);
RequestHandler::setValue('listProjectFilter', $idProject);
RequestHandler::setValue('listSkillFilter', $idSkill);
RequestHandler::setValue('listSkillLevelFilter', $idSkillLevel);
RequestHandler::setValue('skillUseSince', $useSince);
RequestHandler::setValue('skillUseUntil', $useUntil);
RequestHandler::setValue('sortBy', $sortBy);
$width=RequestHandler::getValue('destinationWidth');
?>
<input type="hidden" name="objectClassManual" id="objectClassManual"value="ResourceSkill" />
<input type="hidden" name="ResourceSkill" id="ResourceSkill"value="true" />
<div id="mainDivContainer" class="container"
  dojoType="dijit.layout.BorderContainer"
  onclick="hideDependencyRightClick();">
  <div id="listDiv" dojoType="dijit.layout.ContentPane" region="center" splitter="true" 
   style=";overflow-y: none;">
    <div dojoType="dijit.layout.ContentPane"
      region="center" id="listHeaderDiv"
      style="width: 100%;">
      <form dojoType="dijit.form.Form" name="resourceSkillListForm" id="resourceSkillListForm" action="" method="post" >
        <div style="<?php echo ($width)?'max-width:'.$width.'px; overflow-x:auto':'';?>">
        <table width="100%" class="listTitle">
          <tr>
            <td width="5px" style="padding-left:5px;vertical-align:top" align="center">
              <div style="position: absolute; left: 5px; width: 32px; top: 36px; height: 32px;" class="iconHighlight">&nbsp;</div>
              <div style="position:relative; top:2px;left:3px" class="icon<?php echo $currentScreen;?>32 icon<?php echo $currentScreen;?> iconSize32" ></div>
            </td>
            <td width="5px" style="vertical-align:top" class="title">
              <div style="width: 100%; height: 100%;position: relative;">
                <div id="menuName" style="width: 100%;text-overflow: ellipsis; overflow: hidden;position:relative; top:7px;left:5px">
                  <span id="classNameSpan" style="padding-left: 5px;"><?php echo i18n("menuResourceSkillSimple");?></span>
                </div>
              </div>
              <?php if ($notResourceSkillSimple){ ?>
              <div style="position:absolute;top:47px;left:40px;font-size:10pt;font-weight:normal" class="listDiv">
                <table style="width:100%;heigth:100%;">
                  <tr>
                    <td width="5px" style="vertical-align: middle; text-align: right;">
                      <span class="nobr">&nbsp;&nbsp;&nbsp;
                          <?php echo i18n("colSortOrder");?>
                          &nbsp;</span>
                    </td>
                    <td width="5px">
                      <select title="<?php echo i18n('hintSortOrderRelevance')?>" type="text" class="filterField roundedLeft" dojoType="dijit.form.FilteringSelect"
                          <?php echo autoOpenFilteringSelect();?> 
                          data-dojo-props="queryExpr: '*${0}*',autoComplete:false"
                          id="sortByFilter" name="sortByFilter" style="width:150px" value="<?php echo $sortBy; ?>" >
                            <option value="dispo"><?php echo i18n('Dispo')?></option>
                            <option value="perti"><?php echo i18n('Skill')?></option>
                            <option value="global"><?php echo i18n('Global')?></option>
                            <script type="dojo/method" event="onChange">
                    var callBack=function() {refreshResourceSkillList(<?php echo $notResourceSkillSimple; ?>)};
                    saveDataToSession('sortByFilter', this.value, false,callBack);
                  </script>
                      </select>
                    </td>
                  </tr>
                </table>
              </div>
              <?php }?>
              <?php if (!$notResourceSkillSimple) { ?>
  							<td width="5px">&nbsp;</td>
							<?php } ?>
            </td>
            <td  width="5px" style="padding-top: 10px;">
              <table width="100%">
                <tr>
                  <td style="vertical-align: middle; text-align: right;"
                    width="5px">
                    <span class="nobr">&nbsp;&nbsp;&nbsp;
                        <?php echo i18n("colIdSkill");?>
                        &nbsp;</span>
                  </td>
                  <td width="5px">
                    <select title="<?php echo i18n('colIdSkill')?>" type="text" class="filterField roundedLeft" dojoType="dijit.form.FilteringSelect"
                        <?php echo autoOpenFilteringSelect();?> 
                        data-dojo-props="queryExpr: '*${0}*',autoComplete:false"
                        id="listSkillFilter" name="listSkillFilter" style="width:150px" value="<?php if(sessionValueExists('listSkillFilter')){ echo getSessionValue('listSkillFilter'); }?>" >
                          <?php
                          // gautier #indentSkill
                          htmlDrawOptionForReference('idSkill', $idSkill, $skill, false);
                          ?>
                          <script type="dojo/method" event="onChange">
                            var callBack=function() {refreshResourceSkillList(<?php echo $notResourceSkillSimple; ?>);};
                            saveDataToSession('listSkillFilter', this.value, false,callBack);
                          </script>
                    </select>
                  </td>
                </tr>
                <tr>
                  <td style="vertical-align: middle; text-align: right;"
                    width="5px">
                    <span class="nobr">&nbsp;&nbsp;&nbsp;
                        <?php echo i18n("colLevel");?>
                        &nbsp;</span>
                  </td>
                  <td width="5px">
                    <select title="<?php echo i18n('colIdSkillLevel')?>" type="text" class="filterField roundedLeft" dojoType="dijit.form.FilteringSelect"
                        <?php echo autoOpenFilteringSelect();?> 
                        data-dojo-props="queryExpr: '*${0}*',autoComplete:false"
                        id="listSkillLevelFilter" name="listSkillLevelFilter" style="width:150px" value="<?php if(sessionValueExists('listSkillLevelFilter')){ echo getSessionValue('listSkillLevelFilter'); }?>" >
                          <?php
                          // gautier #indentSkill
                          htmlDrawOptionForReference('idSkillLevel', $idSkillLevel, null, false);
                          ?>
                          <script type="dojo/method" event="onChange">
                            var callBack=function() {refreshResourceSkillList(<?php echo $notResourceSkillSimple; ?>);};
                            saveDataToSession('listSkillLevelFilter', this.value, false,callBack);
                          </script>
                    </select>
            			</td>
            			
            			<td id="strictLevelCheckStructureDiv" style="position: absolute; margin: 2px 0px 0px 10px;margin-left: 10px;">
                    <div style="display: inline-flex; align-items: center; gap: 4px;">
                      <div id="strictLevelCheck" name="strictLevelCheck" dojoType="dijit.form.CheckBox" <?php if ($strictLevelCheck=='true') echo " checked ";?> type="checkbox">
                        <script type="dojo/method" event="onChange">
                          var callBack = function() {
                            refreshResourceSkillList(<?php echo $notResourceSkillSimple; ?>);
                          };
                          saveDataToSession('strictLevelCheck', ((this.checked) ? true : false), false, callBack);
                        </script>
                      </div>
                      <label for="strictLevelCheck" style="text-align: left;"> <?php echo i18n("strictLevel") ?>&nbsp;<?php if(!isNewGui()){ ?>:<?php } ?>&nbsp; </label>
                    </div>
                  </td>	
                </tr>
              </table>
            </td>
            <?php if ($notResourceSkillSimple){ ?>
            <td width="5px" style="padding-top: 10px;vertical-align:top;">
                <table style="width:100%;heigth:100%;">
                  <tr>
                    <td width="5px" style="vertical-align: middle; text-align: right;">
                      <span class="nobr">&nbsp;&nbsp;&nbsp;
                          <?php echo i18n("colIdProject");?>
                          &nbsp;</span>
                    </td>
                    <td width="5px">
                      <select title="<?php echo i18n('colIdProject')?>" type="text" class="filterField roundedLeft" dojoType="dijit.form.FilteringSelect"
                        <?php echo autoOpenFilteringSelect();?> 
                        data-dojo-props="queryExpr: '*${0}*',autoComplete:false"
                        id="listProjectFilter" name="listProjectFilter" style="width:150px" value="<?php if(sessionValueExists('listProjectFilter')){ echo getSessionValue('listProjectFilter'); }?>" >
                          <?php
                          // gautier #indentSkill
                          htmlDrawOptionForReference('idProject', $idProject, null, false);
                          ?>
                          <script type="dojo/method" event="onChange">
                            var callBack=function() {setResourceSkillProjectDate(<?php echo $notResourceSkillSimple; ?>)};
                            saveDataToSession('listProjectFilter', this.value, false,callBack);
                          </script>
                      </select>
                    </td>
                  </tr>
                </table>
            </td>
            <td width="5px" style="padding-left: 20px;padding-top: 10px;vertical-align:top;">
              <div id="resourceSkillProjectDate" class="container" region="top" dojoType="dijit.layout.ContentPane">
              <table>
                <tr>
                  <td ><?php echo i18n('disponibility')?></td>
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
                 refreshResourceSkillList(<?php echo $notResourceSkillSimple; ?>);
               </script>
                     </div>
                   </td>
                </tr>
                <tr>
                    <td ></td>
                   <td width="5px"style="vertical-align: middle; text-align: right;">
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
                          refreshResourceSkillList(<?php echo $notResourceSkillSimple; ?>);
                       </script>  
                     </div>
                   </td>
                </tr>
              </table>
              </div>
            </td>
            <td width="5px" style="padding-top: 10px;vertical-align:top;">

              </td>
             <td width="5px" style="width:21%;padding-right: 10px;">
              <div style="position:relative;float:left;width: 100%;">
                <label for="showGlobalDisponibility" class="notLabel" style="color:var(--color-list-header-text) !important;margin-top:-5px;text-shadow: 0px 0px;width: 90%;"><?php echo i18n('showGlobalDisponibility');?></label>
                  <input type="radio" data-dojo-type="dijit/form/RadioButton" style="float:right"
                  <?php if ($showPeriodDisponibility=='showGlobalDisponibility') { echo "checked='checked'"; }?>
                    id="showGlobalDisponibility" name="showPeriodDisponibility" value="showGlobalDisponibility" 
                    onclick="var callBack=function() {refreshResourceSkillList(<?php echo $notResourceSkillSimple; ?>);};
                         saveDataToSession('showPeriodDisponibility', this.value, false,callBack);"/>
              </div>
              <div style="position:relative;float:left;width: 100%;">
                <label for="showWeeklyDisponibility" class="notLabel" style="color:var(--color-list-header-text) !important;margin-top:-5px;text-shadow: 0px 0px;width: 90%;"><?php echo i18n('showWeeklyDisponibility');?></label>
                  <input type="radio" data-dojo-type="dijit/form/RadioButton" style="float:right"
                  <?php if ($showPeriodDisponibility=='showWeeklyDisponibility') { echo "checked='checked'"; }?>
                    id="showWeeklyDisponibility" name="showPeriodDisponibility" value="showWeeklyDisponibility"
                    onclick="var callBack=function() {refreshResourceSkillList(<?php echo $notResourceSkillSimple; ?>);};
                         saveDataToSession('showPeriodDisponibility', this.value, false,callBack);"/>
              </div>
              <div style="position:relative;float:left;width: 100%;">
                <label for="showMonthlyDisponibility" class="notLabel" style="color:var(--color-list-header-text) !important;margin-top:-5px;text-shadow: 0px 0px;width: 90%;"><?php echo i18n('showMonthlyDisponibility');?></label>
                  <input type="radio" data-dojo-type="dijit/form/RadioButton" style="float:right"
                  <?php if ($showPeriodDisponibility=='showMonthlyDisponibility') { echo "checked='checked'"; }?>
                    id="showMonthlyDisponibility" name="showPeriodDisponibility" value="showMonthlyDisponibility"
                    onclick="var callBack=function() {refreshResourceSkillList(<?php echo $notResourceSkillSimple; ?>);};
                         saveDataToSession('showPeriodDisponibility', this.value, false,callBack);"/>
              </div>
            </td>
            <?php }else { ?>
        			<td width="800px">&nbsp;</td>
    				<?php } ?>
          </tr>
        </table>
        </div>
      </form>
    </div>
    <div id="hierarchicalSkillDivView" dojoType="dijit.layout.BorderContainer" name="hierarchicalSkillDivView" style="height: 100%">
      <div id="resourceSkillListDiv" class="container" region="center" dojoType="dijit.layout.ContentPane" style="height:95%;width:100%;padding-top:10px;overflow:auto !important;">
          <?php include 'resourceSkillView.php'?>
      </div>
    </div>
  </div>