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

$idProject = RequestHandler::getId('idProject');

if (!$idProject) {
  echo '<div style="padding:20px;color:red;">ERROR: No project ID provided</div>';
  return;
}
$searchByLayout = sessionValueExists('searchByLayoutDetail') ? getSessionValue('searchByLayoutDetail') : "" ;
?>

<link rel="stylesheet" type="text/css" href="../view/css/projectDashboard.css">

<input type="hidden" id="objectClassManual" value="ProjectDetail" />
<input type="hidden" id="currentProjectId" value="<?php echo $idProject; ?>" />

<div class="container" dojoType="dijit.layout.BorderContainer" id="divProjectDashboardContainer" design="headline" gutters="false">
  
  <!-- ================= HEADER (region top) ================= -->
  <div id="titleProjectDashboard" class="listTitle" dojoType="dijit.layout.ContentPane" 
       region="top" style="z-index:5;overflow:visible;min-height:65px;">
    <table width="100%">
      <tr style="vertical-align: middle;">
        <td style="width:50px;">
          <div style="position:absolute;top:2px">
            <?php echo formatIcon('Project', 32, null, true); ?>
          </div>
        </td>
        <td class="title" style="height:35px;">
          <div id="dashboardTitle" style="float:left;position:relative;top:8px;text-overflow:ellipsis;overflow:hidden;">
            <span id="classNameSpan"><?php echo i18n('menuProjectDashboardDetail'); ?></span>
          </div>
        </td>
      </tr>
      
      <tr><td colspan="2" style="height: 10px;"></td></tr>
      <tr>
        <td colspan="2">
          <div style="width:100%;padding:0px 0px 0px 10px;">            
            <!-- Layout -->
            <?php echo ucfirst(i18n("colLayout"));?> : 
            <select name="searchByLayoutDetail" id="searchByLayoutDetail" class="input roundedLeft" style="width:150px;" required="false"
              dojoType="dijit.form.FilteringSelect" <?php echo autoOpenFilteringSelect();?>>
              <option <?php if($searchByLayout == " ") echo "selected";?> value=""></option>
              <option <?php if($searchByLayout == "viewOne") echo "selected";?> value="viewOne"><?php echo i18n("viewOne");?></option>
              <option <?php if($searchByLayout == "viewTwo") echo "selected";?> value="viewTwo"><?php echo i18n("viewTwo");?></option>
              <option <?php if($searchByLayout == "viewThree") echo "selected";?> value="viewThree"><?php echo i18n("viewThree");?></option>
              <script type="dojo/method" event="onChange">
                onSearchByLayoutChangeDetail(this.value);
              </script>
            </select>
            
            <div style="float:right;padding-right:15px;">
            
            <!-- Bouton retour -->
            <button dojoType="dijit.form.Button" onclick="returnToProjectDashboard();" iconClass="dijitButtonIcon dijitButtonIconPrevious" title="<?php echo i18n('buttonBackToDashBoard'); ?>" class="detailButton" showLabel="true">
            </button>
              <!-- Parameters -->
              <div name="extraButtonProjectDashboardDetail" id="extraButtonProjectDashboardDetail" jsId="extraButtonProjectDashboardDetail" 
                   title="<?php echo i18n('extraButtons');?>" class="comboButton" iconClass="dijitButtonIcon dijitButtonIconExtraButtons"dojoType="dijit.form.DropDownButton" howlabel="false">
                <div id="extraButtonProjectDashboardDetailDialog" class="white" dojoType="dijit.TooltipDialog">
                  <table style="margin:5px">
                    <tr><td><?php projectDetailParameterList();?></td></tr>
                  </table>
                </div>
              </div>
            </div>
          </div>
        </td>
      </tr>

      <!-- =============== JSON DATA (hidden) ================= -->
      <div dojoType="dijit.layout.ContentPane" id="projectDashboardDetailJsonData" jsId="projectDashboardDetailJsonData" style="display:none;">
        <?php include '../tool/jsonProjectDashboardDetail.php'; ?>
      </div>
    </table>
  </div>

  <!-- =============== MAIN CONTENT AREA (center) ================= -->
  <div dojoType="dijit.layout.ContentPane" id="divProjectDashboardDetailContent" region="center" style="overflow:auto;position:relative;"></div>

</div>

<?php 
function projectDetailParameterList(){
  $objective = Parameter::getUserParameter("objectivesDetail");
  $objective = ($objective=='off')?false:true;
  
  $weather = Parameter::getUserParameter("weatherDetail");
  $weather = ($weather=='off' )?false:true;
  
  $resource = Parameter::getUserParameter("resourceDetail");
  $resource = ($resource=='off')?false:true;
  
  $milestone = Parameter::getUserParameter("milestoneDetail");
  $milestone = ($milestone=='off')?false:true;
  
  $financial = Parameter::getUserParameter("financialDetail");
  $financial = ($financial=='off' )?false:true;
  
  $budget = Parameter::getUserParameter("budgetDetail");
  $budget = ($budget=='off' )?false:true;
  
  $revenue = Parameter::getUserParameter("revenueDetail");
  $revenue = ($revenue=='off' )?false:true;
  
  $risk = Parameter::getUserParameter("riskDetail");
  $risk = ($risk=='off')?false:true;
  
  $opportunity = Parameter::getUserParameter("opportunityDetail");
  $opportunity = ($opportunity=='off')?false:true;
  
  $tornado = Parameter::getUserParameter("tornadoDetail");
  $tornado = ($tornado=='off')?false:true;
  
  $raci = Parameter::getUserParameter("raciDetail");
  $raci = ($tornado=='off')?false:true;
 
  $burndown = Parameter::getUserParameter("burndownDetail");
  $burndown = ($burndown=='off')?false:true;
  
  $fortyFiveDegree = Parameter::getUserParameter("fortyFiveDegreeDetail");
  $fortyFiveDegree = ($fortyFiveDegree=='off')?false:true;
  
  $sCurve = Parameter::getUserParameter("sCurveDetail");
  $sCurve = ($sCurve=='off')?false:true;
  
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
  echo '        <tr>';
  // LEFT COLUMN
  echo '          <td style="width:50%;vertical-align:top;">';
  echo '            <table style="width:100%;">';
  $leftItems = [
      ['objectivesDetail',$objective,'colObjectives', false],
      ['weatherDetail',$weather,'weather',false],
      ['resourceDetail',$resource,'resources',false],
      ['milestoneDetail',$milestone,'Milestone',false],
      ['financialDetail',$financial,'moduleFinancial',false],
//       ['budgetDetail',$budget,'colIdBudget',false],
      ['revenueDetail',$revenue,'sectionRevenue',false],
      ['riskDetail',$risk,'menuRiskManagement',false],
      ['opportunityDetail',$opportunity,'menuOpportunity',false],
      ['tornadoDetail',$tornado,'tornado',false],
      ['raciDetail',$raci,'raci',false],
      ['burndownDetail',$burndown,'reportBurndownChart',false],
      ['fortyFiveDegreeDetail',$fortyFiveDegree,'report45DegreeChart',false],
      ['sCurveDetail',$sCurve,'reportSCurveChart',false]
  ];
  foreach ($leftItems as $item) {
      echo '              <tr>';
      echo '                <td style="padding-top:2px;width:30px;">';
      echo '                  <div id="'.$item[0].'" class="colorSwitch" data-dojo-type="dojox/mobile/Switch" '.(($item[1]) ? 'value="on"' : 'value="off"').' leftLabel="" rightLabel="" style="width:25px;">';
      echo '                    <script type="dojo/method" event="onStateChanged">';
      echo '                      enhancedSwitchHandlerDetail("'.$item[0].'", this.value, '.($item[3] ? 'true' : 'false').');';
      echo '                    </script>';
      echo '                  </div>';
      echo '                </td>';
      echo '                <td class="checkboxLabel" style="padding-left:5px;">';
      echo '                  <span onclick="toggleDashboardParameterDetail(\''.$item[0].'\');">'.pq_ucfirst(i18n($item[2])).'</span>';
      echo '                </td>';
      echo '              </tr>';
  }
  echo '            </table>';
  echo '          </td>';
  echo '        </tr>';
    
  // =================================== Option + RECORDING ===================================
  echo '  <tr style="display:flex;gap:10px;">';
  // RIGHT: RECORDING
  echo '    <td style="width:100%;vertical-align:top;padding: 10px 0px 0px 5px;">';
  echo '      <table style="width:100%;margin:5px 0;">';
  echo '        <tr>';
  echo '          <td style="width:40px;"><div class="iconPlanningBaseline iconSize32 imageColorNewGuiNoSelection" style="border:0;margin-right:10px;"></div></td>';
  echo '          <td class="dependencyHeader planningDialogTitle" style="text-align:left;padding-left:5px;width:100%;">'.i18n('recording').'</td>';
  echo '          <td style="width:40px;text-align:right;padding-right:0;">';
  echo '            <div id="addRecordingDashboardDetail" title="'.i18n('addRecording').'" style="margin:0 0 0 10px;" onClick="saveLayoutRecordingDetail()">'.formatMediumButton('Save').'</div>';
  echo '          </td>';
  echo '        </tr>';
  echo '        <tr>';
  echo '          <td colspan="3">'.ucfirst(i18n("colLayout")).' <select dojoType="dijit.form.FilteringSelect" class="input roundedLeft" style="max-width:120px;" name="layoutRecordingDetail" id="layoutRecordingDetail">';
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