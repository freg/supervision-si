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

/* ============================================================================
 * Presents the list of objects of a given class.
 *
 */
require_once "../tool/projeqtor.php";
require_once "../tool/formatter.php";
scriptLog('   ->/view/criticalResourcesList.php');

$calcuteStartDate = date('Y-m-d');
if(sessionValueExists('startDateCalculPlanning')){
  $calcuteStartDate = getSessionValue('startDateCalculPlanning');
}

$firstDay = date('Y-m-d');
if(sessionValueExists('startDateCriticalResources')){
  $firstDay = getSessionValue('startDateCriticalResources');
}

$lastDay = date('Y-m-d', strtotime(date('Y-m-d') . ' + 1 year'));
if(sessionValueExists('endDateCriticalResources')){
  $lastDay = getSessionValue('endDateCriticalResources');
}

$proj=null;
if (sessionValueExists('project')) {
  $proj=getSessionValue('project');
} else {
  $defaultProject=Parameter::getUserParameter('defaultProject');
  if (is_numeric($defaultProject)) $proj=$defaultProject;
}
if ($proj=="*" or ! $proj) { 
	//$proj=' , ';
	$proj=null;
} else {
	//$proj = ",".$proj;
}
if (getSessionValue('idProjectCriticalResources')) {
  $proj.= (($proj)?",":"").getSessionValue('idProjectCriticalResources');
}
if (getSessionValue('scaleCriticalResources')) {
  $scale = getSessionValue('scaleCriticalResources');
  if ($scale == 'false') {
    $scale = 'month';
  }
} else {
  $scale = 'month';
}

if (getSessionValue('nbCriticalResourcesValue') && getSessionValue('nbCriticalResourcesValue') != 'null') {
  $maxResources = getSessionValue('nbCriticalResourcesValue');
} else {
  $maxResources = null;
}


$indicatorValueRed = (getSessionValue('CriticalResourceIndicatorRed'))?getSessionValue('CriticalResourceIndicatorRed'):Parameter::getGlobalParameter('CriticalResourceIndicatorRed');
$indicatorValueOrange = (getSessionValue('CriticalResourceIndicatorOrange'))?getSessionValue('CriticalResourceIndicatorOrange'):Parameter::getGlobalParameter('CriticalResourceIndicatorOrange');

$isColorBlind = (Parameter::getUserParameter('colorBlindPlanning') == 'YES')?true:false;
$redColorA = 'linear-gradient(45deg, #63226b 6.25%, #9a3ec9 6.25%, #9a3ec9 43.75%, #63226b 43.75%, #63226b 56.25%, #9a3ec9 56.25%, #9a3ec9 93.75%, #63226b 93.75%);background-size: 8px 8px;';

$param = "?scale=$scale&start=$firstDay&end=$lastDay&idProject=$proj&limitedRow=$maxResources";
?>
<script type="dojo/method">
oldValueProjectCriticalResources = <?php echo(json_encode($proj));?>
</script>

<div dojoType="dijit.layout.BorderContainer" id="criticalResourcesParamDiv" name="criticalResourcesParamDiv">
  <div dojoType="dijit.layout.ContentPane" region="top" id="criticalResourcesButtonDiv" class="listTitle" >
    <div style="vertical-align:top; min-width:350px; width:20%; height:32px;">
      <table>
        <tr height="32px">
          <td width="50px" align="center">
            <?php echo formatIcon('CriticalResources', 32, null, true);?>
          </td>
          <td width="250px"><span class="title"><?php echo i18n('menuCriticalResources');?></span></td>
          <td>
            <span class="dijitReset dijitStretch dijitButtonContents" data-dojo-attach-point="titleNode,focusNode" role="button" aria-labelledby="planButton_label" tabindex="0" id="planButton" title="Calculer le planning des projets" style="user-select: none;margin-left:15px;">
              <div title ="<?php echo i18n('calculCriticalResource');?>" class="dijitReset dijitInline dijitIcon iconPlanStopped imageColorNewGui"  onclick="refreshDataCriticalResources()"  data-dojo-attach-point="iconNode"></div>
            </span>
          </td>
        </tr>
      </table>
    </div>
    <form dojoType="dijit.form.Form" name="criticalResourcesForm" id="criticalResourcesForm" onSubmit="return false;" style="padding-bottom:20px;">
      <input type="hidden" id="outMode" name="outMode" value="excel">
      <input type="hidden" id="print" name="print" value="true">
      <input type="hidden" id="page" name="page" value="../view/criticalResourceExport.php">
      <input type="hidden" id="reportName" name="reportName" value="CriticalResource" />
      <table width="100%" height="64px" class="listTitle">
        <tr height="32px">
      		<td>
            <table>
              <tr>
                <td>
                  <table>
                    <tr>
                      <td nowrap="nowrap" style="text-align: right;padding-left:20px; padding-right:10px;"><?php echo i18n("calculateStartDate");?></td>
                      <td>
                        <div dojoType="dijit.form.DateTextBox"
                          <?php if (sessionValueExists('browserLocaleDateFormatJs')) {
              						echo ' constraints="{datePattern:\''.getSessionValue('browserLocaleDateFormatJs').'\'}" ';
              						}?>
                          id="startDateCalculPlanning" name="startDateCalculPlanning"
                          invalidMessage="<?php echo i18n('messageInvalidDate')?>"
                          type="text" maxlength="10"
                          style="width:110px; text-align: center;" class="input roundedLeft"
                          hasDownArrow="true"
                          value="<?php echo $calcuteStartDate;?>" >
                          <script type="dojo/method" event="onChange" >
                            var start=dijit.byId('startDateCalculPlanning').get("value");
                            saveDataToSession('startDateCalculPlanning',formatDate(start), true);
                            refreshDataCriticalResources();
                          </script>
                        </div>
                      </td>
                    </tr>
                    <tr>
                      <td nowrap="nowrap" style="text-align: right;padding-left:20px; padding-right:10px;"><?php echo i18n("displayStartDate");?></td>
                      <td>
                        <div dojoType="dijit.form.DateTextBox"
                          <?php if (sessionValueExists('browserLocaleDateFormatJs')) {
              						  echo ' constraints="{max:\''.$lastDay.'\', datePattern:\''.getSessionValue('browserLocaleDateFormatJs').'\'}" ';
              						} else {
              						  echo 'constraints="{max:\''.$lastDay.'\'}"';
              						}
              						?>
                          id="startDateCriticalResources" name="startDateCriticalResources"
                          invalidMessage="<?php echo i18n('messageInvalidDate')?>"
                          type="text" maxlength="10"
                          style="width:110px; text-align: center;" class="input roundedLeft"
                          hasDownArrow="true"
                          value="<?php echo $firstDay;?>" >
                          <script type="dojo/method" event="onChange" >
                            var start=dijit.byId('startDateCriticalResources').get("value");
                            var end=dijit.byId('endDateCriticalResources').get('value');
                            saveDataToSession('startDateCriticalResources',formatDate(start), true);
                            dijit.byId('endDateCriticalResources').constraints.min = start;
                            refreshCriticalResources();
                          </script>
                        </div>
                      </td>
                    </tr>
                    <tr>
                      <td nowrap="nowrap" style="text-align: right;padding-left:20px; padding-right:10px;"><?php echo i18n("displayEndDate");?></td>
                      <td>
                        <div dojoType="dijit.form.DateTextBox"
                          <?php if (sessionValueExists('browserLocaleDateFormatJs')) {
              						  echo ' constraints="{min:\''.$firstDay.'\', datePattern:\''.getSessionValue('browserLocaleDateFormatJs').'\'}" ';
              						} else {
              						  echo 'constraints="{min:\''.$firstDay.'\'}"';
              						}
              						?>
                          id="endDateCriticalResources" name="endDateCriticalResources"
                          type="text" maxlength="10" hasDownArrow="true"
                          style="width:110px; text-align:center;" class="input roundedLeft"
                          value="<?php echo $lastDay;?>" >
                          <script type="dojo/method" event="onChange" >
                            var start=dijit.byId('startDateCriticalResources').get("value");
                            var end = dijit.byId('endDateCriticalResources').get('value');
                            saveDataToSession('endDateCriticalResources',formatDate(end), true);
                            dijit.byId('startDateCriticalResources').constraints.max = end;
                            refreshCriticalResources();
                          </script>
                        </div>
                      </td>
                    </tr>
                    <tr>
                      <td nowrap="nowrap" style="text-align: right;padding-left:20px; padding-right:10px;"><?php echo i18n("nbMaxCriticalResources");?></td>
                      <td>
                        <div dojoType="dijit.form.NumberTextBox" constraints="{min:1,max:999}" id="nbCriticalResourcesValue" name="nbCriticalResourcesValue"
                          style="width:50px; text-align: left; color: #000000;" 
                          value="<?php if (getSessionValue('nbCriticalResourcesValue')!= null) echo getSessionValue('nbCriticalResourcesValue');?>">
                  	      <script type="dojo/method" event="onChange" >
                            
                            if (isNaN(this.get("value"))) {
                              var nbCriticalResourcesValue = null;
                            } else {
                              var nbCriticalResourcesValue=this.get("value");
                            }
                            saveDataToSession('nbCriticalResourcesValue',nbCriticalResourcesValue, true);
                            refreshCriticalResources();
                          </script>
                  	    </div>
                  	  </td>
                    </tr>
                  </table>
                </td>
                <td style="display:block; margin-top:30px;">
                  <table>
                   <tr>
                      <td nowrap="nowrap" style="text-align: right;padding-left:20px; padding-right:10px;"><?php echo lcfirst(i18n("periodScale"));?></td>
                  	  <td>
                        <table>
                          <tr>
                            <td style="text-align:right;  width:5%" class="tabLabel" >
                              <input  onClick="saveDataToSession('scaleCriticalResources', 'week', false);refreshCriticalResources();" type="radio" dojoType="dijit.form.RadioButton"  name="scaleCriticalResources" id="scaleCriticalResourcesWeek" value="week" 
                              <?php if (getSessionValue('scaleCriticalResources')=='week') echo 'checked' ?>/>
                            </td>
                            <td style="text-align:left;" >
                              <?php echo i18n('week');?>
                            </td>
                          </tr>
                          <tr>
                            <td style="text-align:right; width:5%" class="tabLabel">
                              <input  onClick="saveDataToSession('scaleCriticalResources', 'month', false);refreshCriticalResources();"   type="radio" dojoType="dijit.form.RadioButton"  name="scaleCriticalResources" id="scaleCriticalResourcesMonth" value="month" 
                              <?php if (getSessionValue('scaleCriticalResources')=='month' or ! getSessionValue('scaleCriticalResources') or getSessionValue('scaleCriticalResources')=='false') echo 'checked' ?> />
                            </td>
                            <td style="text-align:left;">
                              <?php echo i18n('month');?>
                            </td>
                          </tr>
                          <tr>
                            <td style="text-align:right; width:5%" class="tabLabel">
                              <input  onClick="saveDataToSession('scaleCriticalResources', 'quarter', false);refreshCriticalResources();"  type="radio" dojoType="dijit.form.RadioButton"  name="scaleCriticalResources" id="scaleCriticalResourcesTrimester" value="quarter"
                              <?php if (getSessionValue('scaleCriticalResources')=='quarter') echo 'checked' ?>/>
                              </div>
                            </td>
                            <td style="text-align:left;">
                              <?php echo i18n('quarter');?>
                            </td>
                          </tr>
                        </table>
                      </td>
                    </tr>
                    
                  </table>
                </td>
                <td style="padding-left:20px;">
                  <?php
                    $styleColor = isNewGui() ? '' : '#000000';
                    $style = "width:initial;color:$styleColor;height:150px;max-height:150px;"; 
                  ?>
                <select dojoType="dojox.form.CheckedMultiSelect" class="selectPlan" multiple="true" 
                  style="<?php echo htmlspecialchars($style, ENT_QUOTES, 'UTF-8'); ?>"
                  id="idProjectCriticalResources" name="idProjectCriticalResources[]" 
                  onChange="saveProjectCriticalResources(this.value);refreshCriticalResources();"
                  value="<?php echo htmlspecialchars(($proj) ? $proj : ' ', ENT_QUOTES, 'UTF-8'); ?>">
                  <option value=" " ><?php echo i18n("allProjects");?></option>
                   <?php
                      $user=getSessionUser();
                      $wbsList=SqlList::getList('Project','sortOrder',$proj, true );
                      $sepChar=Parameter::getUserParameter('projectIndentChar');
                      if (!$sepChar) $sepChar='__';
                      else if ($sepChar=='no') $sepChar='';
                      $wbsLevelArray=array();
                      $projectClause = transformListIntoInClause(getSessionUser()->getListOfPlannableProjects());
                      $inClause=" idProject in ". $projectClause;
                      $inClause.=" and idProject not in " . Project::getAdminitrativeProjectList();
                      $inClause.=" and idProject not in " . Project::getTemplateInClauseList();
                      $inClause.=" and idProject not in " . Project::getProposaleInClauseList();
                      $inClause.=" and refType= 'Project'";
                      $inClause.=" and idle=0";
                      $order="wbsSortable asc";
                      $pe=new PlanningElement();
                      $list=$pe->getSqlElementsFromCriteria(null,false,$inClause,$order,null,true);
                      foreach ($list as $projOb){
                        if (isset($wbsList[$projOb->idProject])) {
                          $wbs=$wbsList[$projOb->idProject];
                        } else {
                          $wbs='';
                        }
                        $wbsTest=$wbs;
                        $level=1;
                        while (pq_strlen($wbsTest)>3) {
                          $wbsTest=pq_substr($wbsTest,0,pq_strlen($wbsTest)-6);

                          if (pq_array_key_exists($wbsTest, $wbsLevelArray)) {
                            $level=$wbsLevelArray[$wbsTest]+1;
                            $wbsTest="";
                          }
                        }
                        $wbsLevelArray[$wbs]=$level;
                        $sep='';
                        for ($i=1; $i<$level;$i++) {$sep.=$sepChar;}
                        $val = $sep.$projOb->refName;
                        ?>
                        <option value="<?php echo $projOb->idProject; ?>"><?php echo $val; ?></option>      
                       <?php
                     }
                   ?>
                 </select>
                </td>
                <td>
                  <div id="criticalLegend" name="criticalLegend" style="display:none;position:absolute;right:20px;padding:5px 10px;bottom:0px;border:1px solid #cccccc;background:#ffffffE0;" >
                    <table>
                      <tr style="height:20px">
                        <td colspan="2" style="text-align:center;color:#707070"><?php echo i18n("legend");?></td>
                      </tr>
                      <tr style="height:20px" title="<?php echo i18n("criticalResourceNormalHint");?>">
                        <td><div style="height:15px;width:30px;background:<?php echo (($isColorBlind)?'#67ff00':'#50BB50');?>"></div></td>
                        <td style="padding-left:10px;color:#707070"><?php echo i18n("criticalResourceNormal");?></td>
                      </tr>
                      <tr style="height:20px" title="<?php echo i18n("criticalResourceSurbookedHint");?>">
                        <td><div style="height:15px;width:30px;background:<?php echo (($isColorBlind)?'#bfbfbf':'#FFC000');?>"></div></td>
                        <td style="padding-left:10px;color:#707070"><?php echo i18n("criticalResourceSurbooked");?></td>
                      </tr>
                      <tr style="height:20px" title="<?php echo i18n("criticalResourceLateHint");?>">
                        <td><div style="height:15px;width:30px;background:<?php echo (($isColorBlind)?$redColorA:'#BB5050');?>"></div></td>
                        <td style="padding-left:10px;color:#707070"><?php echo i18n("criticalResourceLate");?></td>
                      </tr>
                    </table>
                  </div>
                      <div id="criticalLegend2" name="criticalLegend2" style="display:none;position:absolute;right:20px;padding:5px 10px;bottom:0px;border:1px solid #cccccc;background:#ffffffE0;" >
                        <table>
                          <tr style="height:22px">
                            <td colspan="2" style="text-align:center;color:#707070"><?php echo i18n("indicatorValueDefinition");?></td>
                          </tr>
                          <tr style="height:20px;">
                            <td><div style="height:15px;width:30px;background:<?php echo (($isColorBlind)?'#bfbfbf':'#FFC000');?>"></div></td>
                            <td style="padding-left:10px;color:#707070"><?php echo i18n("criticalResourceIndicatorValueColor");?></td>
                            <td style="padding-left:10px;color:#707070">
                              <div dojoType="dijit.form.NumberTextBox" constraints="{min:-999,max:999}" id="indicatorValueOrange" name="indicatorValueOrange"
                                style="width:40px;height:15px;text-align: left; color: #000000;" 
                                value="<?php echo $indicatorValueOrange;?>">
                      	        <script type="dojo/method" event="onChange">
                                  saveDataToSession('CriticalResourceIndicatorOrange', this.value);
                                  saveGlobaleParameter('CriticalResourceIndicatorOrange', this.value, refreshCriticalResources());
                                </script>
                      	      </div>
                      	      %
                            </td>
                          </tr>
                          <tr style="height:20px">
                            <td><div style="height:15px;width:30px;background:<?php echo (($isColorBlind)?$redColorA:'#BB5050');?>"></div></td>
                            <td style="padding-left:10px;color:#707070"><?php echo i18n("criticalResourceIndicatorValueColor");?></td>
                            <td style="padding-left:10px;color:#707070">
                              <div dojoType="dijit.form.NumberTextBox" constraints="{min:-999,max:999}" id="indicatorValueRed" name="indicatorValueRed"
                                style="width:40px;height:15px;text-align: left; color: #000000;" 
                                value="<?php echo $indicatorValueRed;?>">
                      	        <script type="dojo/method" event="onChange">
                                  saveDataToSession('CriticalResourceIndicatorRed', this.value);
                                  saveGlobaleParameter('CriticalResourceIndicatorRed', this.value, refreshCriticalResources());
                                </script>
                      	      </div>
                      	      %
                            </td>
                          </tr>
                        </table>
                     </div>
      
      
      
      
      
                 </td>
              </tr>
            </table>
          </td>
        </tr>
      </table>
    </form>
  </div>
<?php
  if ($proj == " , ") {
    $proj =null;
  }
  $proj = explode (",", pq_nvl($proj));   
  $lastDayStored=Affectable::getCriticalResourcePlanningResult();
  if (! $lastDayStored or $lastDayStored!=$calcuteStartDate) {
    PlannedWork::plan('*',$calcuteStartDate,false,true,true);
    Affectable::storeCriticalResourcePlanningResult($calcuteStartDate);
  }
  $hide=true;
  $selectedTab = getSessionValue('criticalSelectedTab');
?>

<div style="position:relative;" dojoType="dijit.layout.ContentPane" region="center" id="criticalResourcesWorkDiv" name="criticalResourcesWorkDiv">
<?php include 'criticalResourcesTabs.php';?>
</div>
     
</div>