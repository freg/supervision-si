<?php
/*** COPYRIGHT NOTICE *********************************************************
 *
 ******************************************************************************
 *** WARNING *** T H I S    F I L E    I S    N O T    O P E N    S O U R C E *
 ******************************************************************************
 *
 * Copyright 2015 ProjeQtOr - Pascal BERNARD - support@projeqtor.org
 *
 * This file is an add-on to ProjeQtOr, packaged as a plug-in module.
 * It is NOT distributed under an open source license.
 * It is distributed in a proprietary mode, only to the customer who bought
 * corresponding licence.
 * The company ProjeQtOr remains owner of all add-ons it delivers.
 * Any change to an add-ons without the explicit agreement of the company
 * ProjeQtOr is prohibited.
 * The diffusion (or any kind if distribution) of an add-on is prohibited.
 * Violators will be prosecuted.
 *
 *** DO NOT REMOVE THIS NOTICE ************************************************/

require_once "../tool/projeqtor.php";
require_once "../tool/formatter.php";

$orderBy = sessionValueExists('dashboardOrderBy') ? getSessionValue('dashboardOrderBy') : ""  ;
$searchByLayout = sessionValueExists('searchByLayout') ? getSessionValue('searchByLayout') : "" ;

$typeObject = "Project";
$filterByStatus = Parameter::getGlobalParameter('filterByStatus');
$displayByStatusList = Parameter::getUserParameter("displayByStatusList_projectDashboard");

$linearViewDashboard = Parameter::getUserParameter("linearViewDashboard");
$linearViewDashboard = ($linearViewDashboard=='on')?true:false;

?>
<link rel="stylesheet" type="text/css" href="../view/css/projectDashboard.css">

<input type="hidden" id="objectClassManual" value="ProjectDashboard" />
<div class="container" dojoType="dijit.layout.BorderContainer" id="divProjectDashboardContainer" design="headline" gutters="false">
  <!-- ================= HEADER (region top) ================= -->
  <div id="titleProjectDashboard" class="listTitle" dojoType="dijit.layout.ContentPane" 
     region="top" style="z-index:5;overflow:visible;min-height:65px;">
    <table width="100%">
      <tr style="vertical-align: middle;">
        <td style="width:50px;">
          <div style="position:absolute;top:2px">
            <?php echo formatIcon('ProjectDashboard', 32, null, true); ?>
          </div>
        </td>
        <td class="title" style="height:35px;">
          <div id="dashboardTitle" style="float:left;position:relative;top:0px;left:20px;text-overflow:ellipsis;overflow:hidden;">
            <span id="classNameSpan"><?php echo i18n('projectDashboard'); ?></span>
          </div>
          
          <!-- ================= FILTER BAR BY STATUS ================= -->
          <?php if ($filterByStatus == 'YES') { 
            if (!$displayByStatusList) $displayByStatusList = 'none';
            
            $project = new Project();
            $listStatus = $project->getExistingStatus();
            $countListStatus = count($listStatus);
          ?>
          <div class="no-title-style">
            <div id="barFilterByStatus" style="display: <?php echo $displayByStatusList;?>; float:left; margin-left: 30px; margin-top: 5px;">
              <div style="display:flex; align-items:center; gap: 10px;">
                <span style="font-weight:bold; white-space:nowrap;font-size: 13px;"><?php echo i18n("colIdStatus");?> :</span>
                <div style="display:flex; gap: 5px; flex-wrap: wrap; max-width: 800px;font-size: 13px;">
                  <?php
                  $cptStatus = 0;
                  foreach ($listStatus as $status) {
                    $cptStatus += 1;
                    $docLineclass = 'docLineTag';
                    $statusStyle = '';
                    if (sessionValueExists('showStatus'.$status->id.'ProjectDashboard') 
                        and getSessionValue('showStatus'.$status->id.'ProjectDashboard') == 'true') {
                      $docLineclass = 'docLineTagNew';
                      $statusStyle = 'background-color:'.$status->color.';color:'.getForeColor($status->color).';';
                    }
                  ?>		
                  <div class="status-tag-container" data-status-id="<?php echo $status->id; ?>" style="display:inline-block;">
                    <span class="<?php echo $docLineclass;?>" 
                          style="cursor:pointer;<?php echo $statusStyle;?>" 
                          onClick="updateShowStatusStateProjectDashboard(this, <?php echo $cptStatus; ?>, '<?php echo $status->color;?>');"
                          title="<?php echo i18n('selectStatus', array($status->name));?>">
                      <div style="padding: 0px 5px 0px 5px;">
                        <?php echo $status->name; ?>
                        <div class="docLineTagPin"></div>
                      </div>
                    </span>
                    <div style="position:relative;float:left;display:none;" 
                         id="showStatusProjectDashboard<?php echo $cptStatus; ?>"
                         dojoType="dijit.form.CheckBox" type="checkbox" value="<?php echo $status->id; ?>"
                         <?php if (sessionValueExists('showStatus'.$status->id.'ProjectDashboard')) {
                           if (getSessionValue('showStatus'.$status->id.'ProjectDashboard') == 'true') { 
                             echo 'checked="checked"';
                           }
                         }?> 
                         onChange="refreshProjectDashboardList()">
                    </div>
                  </div>
                  <?php } ?>
                </div>
              </div>
              <input type="hidden" id="countStatusProjectDashboard" value="<?php echo $cptStatus; ?>" />
            </div>
          </div>
          <?php } ?>
        </td>
      </tr>
      
      <tr><td colspan="2" style="height: 10px;"></td></tr>
      <tr>
        <td colspan="2">
          <!-- ================= FILTER BAR ================= -->
          <div style="width:100%; display:flex; align-items:center; flex-wrap:wrap; gap:10px;padding: 0px 0px 0px 10px;">
            
            <!-- Sort by -->
            <?php echo ucfirst(i18n("sortedBy"));?> :</span>
            <select name="dashboardOrderBy" id="dashboardOrderBy" class="input roundedLeft" style="width:150px;margin-right:15px;"
                    dojoType="dijit.form.FilteringSelect" <?php echo autoOpenFilteringSelect();?>>   
              <option <?php if($orderBy == "wbs") echo "selected";?> value="wbs"><?php echo i18n("colWbs");?></option>
              <option <?php if($orderBy == "name") echo "selected";?> value="name"><?php echo i18n("colName");?></option>
              <option <?php if($orderBy == "work") echo "selected";?> value="work"><?php echo i18n("colWork");?></option>
              <option <?php if($orderBy == "priority") echo "selected";?> value="priority"><?php echo i18n("colPriority");?></option>
              <option <?php if($orderBy == "EndDate") echo "selected";?> value="EndDate"><?php echo i18n("colEndDate");?></option>
							<option <?php if($orderBy == "recents") echo "selected";?> value="recents"><?php echo i18n("mostRecent");?></option>
              <script type="dojo/method" event="onChange">
                changeDashboardOrderBy();
                if (this.value=='priority') enhancedSwitchHandler('priorityDashboard', true, true);
                saveDataToSession('dashboardOrderBy', this.value, true);
              </script>
            </select>

            <!-- Manager -->
            <?php echo ucfirst(i18n("colManager"));?> : 
            <select name="searchByResponsible" id="searchByResponsible" class="filterField roundedLeft" style="width:150px;" 
                    dojoType="dijit.form.FilteringSelect" <?php echo autoOpenFilteringSelect();?>
                    value="<?php if(sessionValueExists('searchByResponsible')){ echo getSessionValue('searchByResponsible');}?>">
              <?php htmlDrawOptionForReference('idResponsible', null, null, false); ?>
              <script type="dojo/method" event="onChange">
                filterDashboard();
                saveDataToSession('searchByResponsible', this.value, true);
              </script>
            </select>

            <!-- Client -->
            <?php echo ucfirst(i18n("colClient"));?> : 
            <select name="searchByClient" id="searchByClient" class="filterField roundedLeft" style="width:150px;" 
                    dojoType="dijit.form.FilteringSelect" <?php echo autoOpenFilteringSelect();?>
                    value="<?php if(sessionValueExists('searchByClient')){ echo getSessionValue('searchByClient');}?>">
              <?php htmlDrawOptionForReference('idClient', null, null, false); ?>
              <script type="dojo/method" event="onChange">
                filterDashboard();
                saveDataToSession('searchByClient', this.value, true);
              </script>
            </select>

            <!-- Organization -->
            <?php echo ucfirst(i18n("colOrganization"));?> : 
            <select name="searchByOrganization" id="searchByOrganization" class="filterField roundedLeft" style="width:150px;"
                    dojoType="dijit.form.FilteringSelect" <?php echo autoOpenFilteringSelect();?>
                    value="<?php if(sessionValueExists('searchByOrganization')){ echo getSessionValue('searchByOrganization');}?>">
              <?php htmlDrawOptionForReference('idOrganization', null, null, false); ?>
              <script type="dojo/method" event="onChange">
                filterDashboard();
                saveDataToSession('searchByOrganization', this.value, true);
              </script>
            </select>

            <!-- Layout -->
            <?php echo ucfirst(i18n("colLayout"));?> : 
            <select name="searchByLayout" id="searchByLayout" class="input roundedLeft" style="width:150px;" required="false"
                    dojoType="dijit.form.FilteringSelect" <?php echo autoOpenFilteringSelect();?>>
              <option <?php if($searchByLayout == " ") echo "selected";?> value=""></option>
              <option <?php if($searchByLayout == "viewOne") echo "selected";?> value="viewOne"><?php echo i18n("viewOne");?></option>
              <option <?php if($searchByLayout == "viewTwo") echo "selected";?> value="viewTwo"><?php echo i18n("viewTwo");?></option>
              <option <?php if($searchByLayout == "viewThree") echo "selected";?> value="viewThree"><?php echo i18n("viewThree");?></option>
              <script type="dojo/method" event="onChange">
                onSearchByLayoutChange(this.value);
              </script>
            </select>
            

              <span style="margin-left:10px;"><?php echo ucfirst(i18n("colViewLinear"));?> : </span>
              <div style="">
   							<div id="linearViewDashboard" class="colorSwitch"  data-dojo-type="dojox/mobile/Switch" value="<?php echo $linearViewDashboard ? 'on' : 'off' ?>" leftLabel="" rightLabel="" style="">
  								<script type="dojo/method" event="onStateChanged">
                    enhancedSwitchHandler("linearViewDashboard", this.value, true);
                  </script>
  							</div>
  						</div>


            <div style="margin-left:auto;padding-right:15px;">
              <!-- Parameters -->
              <div name="extraButtonProjectDashboard" id="extraButtonProjectDashboard" jsId="extraButtonProjectDashboard" title="<?php echo i18n('extraButtons');?>" class="comboButton" iconClass="dijitButtonIcon dijitButtonIconExtraButtons"
                   dojoType="dijit.form.DropDownButton" showlabel="false">
                <div id="extraButtonProjectDashboardDialog" class="white" 
                     dojoType="dijit.TooltipDialog">
                  <table style="margin:5px">
                    <tr><td><?php projectDashboardParameterList();?></td></tr>
                  </table>
                </div>
              </div>
            </div>
          </div>
        </td>
      </tr>
      
      <!-- =============== JSON DATA (hidden) ================= -->
      <div dojoType="dijit.layout.ContentPane"
           id="projectDashboardJsonData"
           jsId="projectDashboardJsonData"
           style="display:none;">
        <?php include '../tool/jsonProjectDashboard.php'; ?>
      </div>
    </table>
  </div>

  <!-- =============== MAIN DASHBOARD AREA (center) ================= -->
  <div dojoType="dijit.layout.ContentPane"
       id="divProjectDashboardContent"
       region="center"
       style="overflow:auto;position:relative;">
  </div>

</div>




<?php 
function projectDashboardParameterList(){
  $datesStart = Parameter::getUserParameter("datesStartDashboard");
  $datesStart = ($datesStart=='off')?false:true;
  
  $datesEnd = Parameter::getUserParameter("datesEndDashboard");
  $datesEnd = ($datesEnd=='off' )?false:true;
  
  if ($datesStart && $datesEnd) $datesEnd=false;
  
  $status = Parameter::getUserParameter("statusDashboard");
  $status = ($status=='off')?false:true;
  
  $nextMilestone = Parameter::getUserParameter("nextMilestoneDashboard");
  $nextMilestone = ($nextMilestone=='off')?false:true;
  
  $weather = Parameter::getUserParameter("weatherDashboard");
  $weather = ($weather=='off' )?false:true;
  
  $trend = Parameter::getUserParameter("trendDashboard");
  $trend = ($trend=='off' )?false:true;
  
  $quality = Parameter::getUserParameter("qualityDashboard");
  $quality = ($quality=='off' )?false:true;
  
  $priority = Parameter::getUserParameter("priorityDashboard");
  $priority = ($priority=='off' )?false:true;
  
  $resources = Parameter::getUserParameter("resourcesDashboard");
  $resources = ($resources=='off')?false:true;
  
  $timeline = Parameter::getUserParameter("timelineDashboard");
  $timeline = ($timeline=='off')?false:true;
  
  $showMilestone = Parameter::getUserParameter("listShowMilestone");
  if ($showMilestone==' ') $showMilestone=null;
  
  $colorMilestone = Parameter::getUserParameter("colorMilestone");
  $colorMilestone = ($colorMilestone=='off')?false:true;
  
  $workProgress = Parameter::getUserParameter("workProgressDashboard");
  $workProgress = ($workProgress=='off')?false:true;
  
  $budgetProgress = Parameter::getUserParameter("budgetProgressDashboard");
  $budgetProgress = ($budgetProgress=='off')?false:true;
  
  $risksProgress = Parameter::getUserParameter("risksProgressDashboard");
  $risksProgress = ($risksProgress=='off')?false:true;
  
  $financialProgress = Parameter::getUserParameter("financialProgressDashboard");
  $financialProgress = ($financialProgress=='on')?true:false;
  
  $technicalProgress = Parameter::getUserParameter("technicalProgressDashboard");
  $technicalProgress = ($technicalProgress=='on')?true:false;
  
  $ticketsProgress = Parameter::getUserParameter("ticketsProgressDashboard");
  $ticketsProgress = ($ticketsProgress=='on')?true:false;
  
  $requirementsProgress = Parameter::getUserParameter("requirementsProgressDashboard");
  $requirementsProgress = ($requirementsProgress=='on')?true:false;
  
  $userStoriesProgress = Parameter::getUserParameter("userStoriesProgressDashboard");
  $userStoriesProgress = ($userStoriesProgress=='on')?true:false;
  
  $closedProject = Parameter::getUserParameter("closedProjectDashboard");
  $closedProject = ($closedProject=='on')?true:false;
  
  $pausedProjects = Parameter::getUserParameter("pausedProjectsDashboard");
  $pausedProjects = ($pausedProjects=='on')?true:false;
  
  $notStartedProjects = Parameter::getUserParameter("notStartedProjects");
  $notStartedProjects = ($notStartedProjects=='off')?false:true;
   
  
  echo '<table style="width:100%;">';
  
  // =================================== DISPLAY OF INFORMATION ===================================
  echo '  <tr>';
  echo '    <td colspan="2" style="vertical-align:top;">';
  echo '      <table style="width:100%;margin:5px;">';
  echo '        <tr>';
  echo '          <td style="width:40px;"><div class="iconChangeLayout iconSize32 imageColorNewGuiNoSelection" style="border:0"></div></td>';
  echo '          <td class="dependencyHeader planningDialogTitle" style="text-align:left;padding-left:5px;">'.i18n('displayOfInformation').'</td>';
  echo '        </tr>';
  echo '      </table>';
  echo '    </td>';
  echo '  </tr>';
  
  // =================================== 2-COLUMN PARAMETERS ===================================
  echo '  <tr>';
  echo '    <td colspan="2" style="vertical-align:top;">';
  echo '      <table style="width:100%;margin:0 5px;">';
  echo '        <tr>';
  // LEFT COLUMN
  echo '          <td style="width:50%;vertical-align:top;">';
  echo '            <table style="width:100%;">';
  $leftItems = [
      ['datesStartDashboard',$datesStart,'datesStartDashboard', false],
      ['datesEndDashboard',$datesEnd,'datesEndDashboard',false],
      ['statusDashboard',$status,'statusForFilter',false],
      ['priorityDashboard',$priority,'Priority',false],
      ['nextMilestoneDashboard',$nextMilestone,'nextMilestoneDashboard',false],
      ['weatherDashboard',$weather,'weather',false],
      ['trendDashboard',$trend,'Trend',false],
      ['qualityDashboard',$quality,'Quality',false],
      ['timelineDashboard',$timeline,'timelineDashboard',false],
      ['colorMilestone',$colorMilestone,'colorMilestone',false],
      ['listShowMilestone',$showMilestone,'showMilestoneShort',true]
  ];
  foreach ($leftItems as $item) {
    if ($item[0] == 'listShowMilestone') {
      echo '              <tr>';
      echo '                <td style="padding:2px 12px 0 0;width:30px;">'.pq_ucfirst(i18n($item[2])).'</td>';
      echo '                <td><select dojoType="dijit.form.FilteringSelect" class="input roundedLeft" style="width:150px;" name="'.$item[0].'" id="'.$item[0].'">';
      echo                    autoOpenFilteringSelect();
      echo '                  <script type="dojo/method" event="onChange">saveDataToSession("'.$item[0].'", this.value,'.($item[3] ? 'true' : 'false').');onMilestoneFilterChange(this.value);</script>';
      echo '                    <option value=" " '.(!$item[1] ? 'SELECTED' : '').'>'.i18n("paramNone").'</option>';
      echo                       htmlDrawOptionForReference("idMilestoneType", (($item[1] && $item[1] != 'all') ? $item[1] : null), null, true);
      echo '                    <option value="all" '.($item[1] == 'all' ? 'SELECTED' : '').'>'.i18n("all").'</option>';
      echo '                </select></td>';
      echo '              </tr>';
    } else {
      echo '              <tr>';
      echo '                <td style="padding-top:2px;width:30px;">';
      echo '                  <div id="'.$item[0].'" class="colorSwitch" data-dojo-type="dojox/mobile/Switch" '.(($item[1]) ? 'value="on"' : 'value="off"').' leftLabel="" rightLabel="" style="width:25px;">';
      echo '                    <script type="dojo/method" event="onStateChanged">';
      echo '                      enhancedSwitchHandler("'.$item[0].'", this.value, '.($item[3] ? 'true' : 'false').');';
      echo '                    </script>';
      echo '                  </div>';
      echo '                </td>';
      echo '                <td class="checkboxLabel" style="padding-left:5px;">';
      echo '                  <span onclick="toggleDashboardParameter(\''.$item[0].'\');">'.pq_ucfirst(i18n($item[2])).'</span>';
      echo '                </td>';
      echo '              </tr>';
    }
  }
  echo '            </table>';
  echo '          </td>';
  // RIGHT COLUMN
  echo '          <td style="width:50%;vertical-align:top;">';
  echo '            <table style="width:100%;">';
  
  echo '              <tr>';
  echo '                <td colspan="2" style="padding-bottom:8px;">';
  echo '                  <div style="display:flex;align-items:center;gap:8px;">';
  echo '                    <span style="font-weight:bold;color:#666;">'.i18n('progressGraphs').'</span>';
  echo '                    <div class="progress-info-bubble" style="display:inline-block;">';
  echo '                      <div id="progress-info-icon" class="iconInfo16 iconInfo iconSize16 imageColorNewGui" style="cursor:help;" data-info-text="'.htmlspecialchars(i18n('maxThreeProgressGraphsInfo')).'">&nbsp;</div>';
  echo '                    </div>';
  echo '                  </div>';
  echo '                </td>';
  echo '              </tr>';
  
  $rightItems = [
      ['workProgressDashboard',$workProgress,'workProgressDashboard',false],
      ['budgetProgressDashboard',$budgetProgress,'budgetProgressDashboard',false],
      ['risksProgressDashboard',$risksProgress,'risksProgressDashboard',false],
      ['technicalProgressDashboard',$technicalProgress,'menuTechnicalProgress',false],
      ['financialProgressDashboard',$financialProgress,'financialProgressDashboard',false],
      ['ticketsProgressDashboard',$ticketsProgress,'ticketsProgressDashboard',false],
      ['requirementsProgressDashboard',$requirementsProgress,'requirementsProgressDashboard',false],
      ['userStoriesProgressDashboard',$userStoriesProgress,'userStoriesProgressDashboard',false],
  ];
  foreach ($rightItems as $item) {
    echo '              <tr>';
    echo '                <td style="padding-top:2px;width:30px;">';
    echo '                  <div id="'.$item[0].'" class="colorSwitch progress-chart-switch" data-dojo-type="dojox/mobile/Switch" '.(($item[1])?'value="on"':'value="off"').' leftLabel="" rightLabel="" style="width:25px;">';
    echo '                    <script type="dojo/method" event="onStateChanged">';
    echo '                      enhancedSwitchHandler("'.$item[0].'", this.value, '.($item[3] ? 'true' : 'false').');';
    echo '                    </script>';
    echo '                  </div>';
    echo '                </td>';
    echo '                <td class="checkboxLabel" style="padding-left:5px;">';
    echo '                  <span onclick="toggleDashboardParameter(\''.$item[0].'\');">'.pq_ucfirst(i18n($item[2])).'</span>';
    echo '                </td>';
    echo '              </tr>';
  }
  
  echo '              <tr><td colspan="2" style="height:10px;border-top:1px solid #e0e0e0;"></td></tr>';
  
  $otherItems = [
      ['closedProjectDashboard',$closedProject,'closedProjectDashboard',false],
      ['pausedProjectsDashboard',$pausedProjects,'pausedProjectsDashboard',false],
      ['notStartedProjects',$notStartedProjects,'notStartedProjects',false]
  ];
  foreach ($otherItems as $item) {
    echo '              <tr>';
    echo '                <td style="padding-top:2px;width:30px;">';
    echo '                  <div id="'.$item[0].'" class="colorSwitch" data-dojo-type="dojox/mobile/Switch" '.(($item[1])?'value="on"':'value="off"').' leftLabel="" rightLabel="" style="width:25px;">';
    echo '                    <script type="dojo/method" event="onStateChanged">';
    echo '                      enhancedSwitchHandler("'.$item[0].'", this.value, '.($item[3] ? 'true' : 'false').');';
    echo '                    </script>';
    echo '                  </div>';
    echo '                </td>';
    echo '                <td class="checkboxLabel" style="padding-left:5px;">';
    echo '                  <span onclick="toggleDashboardParameter(\''.$item[0].'\');">'.pq_ucfirst(i18n($item[2])).'</span>';
    echo '                </td>';
    echo '              </tr>';
  }
  echo '            </table>';
  echo '          </td>';
  echo '        </tr>';
  echo '      </table>';
  echo '    </td>';
  echo '  </tr>';
  
  // =================================== Option + RECORDING ===================================
  echo '  <tr style="display:flex;gap:10px;">';
  if (Parameter::getGlobalParameter('filterByStatus') == 'YES') {
    // LEFT: MANAGEMENT
    echo '    <td style="width:45%;vertical-align:top;">';
    echo '      <table style="width:100%;margin:5px;">';
    echo '        <tr>';
    echo '          <td style="width:40px;"><div class="iconDisplayOnKanbanManagement iconSize32 imageColorNewGuiNoSelection" style="border:0"></div></td>';
    echo '          <td class="dependencyHeader planningDialogTitle" style="text-align:left;padding-left:5px;">'.i18n('dialogManage').'</td>';
    echo '        </tr>';
    echo '        <tr>';
    echo '          <td style="padding-left:5px;">';
    echo '            <button title="'.i18n('filterByStatus').'" dojoType="dijit.form.Button" id="iconStatusButtonParam" name="iconStatusButtonParam" iconClass="dijitButtonIcon dijitButtonIconStatusChange imageColorNewGui" class="detailButton" showLabel="false">';
    echo '              <script type="dojo/connect" event="onClick" args="evt">';
    echo '                protectDblClick(this);';
    echo '                var barFilter = dojo.byId("barFilterByStatus");';
    echo '                if (barFilter) {';
    echo '                  if (barFilter.style.display == "none") {';
    echo '                    barFilter.style.display = "flex";';
    echo '                    saveDataToSession("displayByStatusList_projectDashboard", "flex", true);';
    echo '                    applyCurrentFilters();';
    echo '                  } else {';
    echo '                    barFilter.style.display = "none";';
    echo '                    saveDataToSession("displayByStatusList_projectDashboard", "none", true);';
    echo '                    applyStatusFilter([]);';
    echo '                  }';
    echo '                }';
    echo '              </script>';
    echo '            </button>';
    echo '          </td>';
    echo '        </tr>';
    echo '        <tr>';
    echo '          <td colspan="2" style="font-size:80%;color:#a0a0a0;vertical-align: top;">'.i18n('filterByStatus').'</td>';
    echo '        </tr>';
    echo '      </table>';
    echo '    </td>';
  } else {
    echo '    <td style="width:45%;vertical-align:top;"></td>';
  }
  
  // RIGHT: RECORDING
  echo '    <td style="width:55%;vertical-align:top;padding-left:5px;padding-right:0;">';
  echo '      <table style="width:100%;margin:5px 0;">';
  echo '        <tr>';
  echo '          <td style="width:40px;"><div class="iconPlanningBaseline iconSize32 imageColorNewGuiNoSelection" style="border:0;margin-right:10px;"></div></td>';
  echo '          <td class="dependencyHeader planningDialogTitle" style="text-align:left;padding-left:5px;width:100%;">'.i18n('recording').'</td>';
  echo '          <td style="width:40px;text-align:right;padding-right:0;">';
  echo '            <div id="addRecordingDashboard" title="'.i18n('addRecording').'" style="margin:0 0 0 10px;" onClick="saveLayoutRecording()">'.formatMediumButton('Save').'</div>';
  echo '          </td>';
  echo '        </tr>';
  echo '        <tr>';
  echo '          <td colspan="3">'.ucfirst(i18n("colLayout")).' <select dojoType="dijit.form.FilteringSelect" class="input roundedLeft" style="max-width:120px;" name="layoutRecording" id="layoutRecording">';
  echo '            <script type="dojo/method" event="onChange"></script>';
  echo '              <option value="viewOne">'.i18n("viewOne").'</option>';
  echo '              <option value="viewTwo">'.i18n("viewTwo").'</option>';
  echo '              <option value="viewThree">'.i18n("viewThree").'</option>';
  echo '          </select></td>';
  echo '        </tr>';
  echo '      </table>';
  echo '    </td>'; 
  echo '  </tr>';
  
  echo '</table>';
    
}


?>

<script type="text/javascript">
  dojo.ready(function() {
    initializeLayoutRecording(); 
    var currentLayout = dijit.byId('searchByLayout');
    if (currentLayout) {
      var layoutValue = currentLayout.get('value');
      if (layoutValue && layoutValue !== '' && layoutValue !== ' ') {
        restoreLayoutRecording(layoutValue);
      }
    }
  });
</script>