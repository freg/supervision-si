<?php // ==============================================================================================================
      // =========================================== FUNTIONS ==========================================================
      // ==============================================================================================================

// $planningType defined which planning is displayed
//   => 'planning'  => main planning
//   => 'portfolio' => project portfolio
//   => 'resource'  => resource planning
//   => 'global'    => global planning
//   => 'version'   => product version et component version planning
//   => 'contract'  => contract 

// ================================================== BUTTON PLAN 
function drawButtonPlan() {?>
  <button id="planButton" dojoType="dijit.form.Button" showlabel="false"
    title="<?php echo i18n('buttonPlan');?>" class="buttonIconNewGui detailButton"
    iconClass="dijitIcon iconPlanStopped" >
    <script type="dojo/connect" event="onClick" args="evt">
      showPlanParam();
      return false;
    </script>
  </button>
<?php 
}

// ================================================== CHECKBOX AUTOMATIC PLANNING 
function drawOptionAutomatic() {
  global $automaticRunPlanning,$displayWidthPlan;
  if ($automaticRunPlanning===null or $automaticRunPlanning==='') { // PBER #7145
    $automaticRunPlanning=1;
  }
  $disabled = (getSessionValue('lockPlanningSaveRefresh') and getSessionValue('lockPlanningSaveRefresh') == '1')?true:false;
  ?>
  <div style="white-space:nowrap;position:absolute; top:5px" title="<?php echo i18n('automaticRunPlan');?>">
  <?php if (isNewGui()) htmlDrawSwitch('automaticRunPlan',$automaticRunPlanning, true, true, $disabled);?>
    <span title="<?php echo i18n('automaticRunPlanHelp');?>" dojoType="dijit.form.CheckBox" 
      <?php if (isNewGui()) echo 'style="display:none"';?>
      type="checkbox" id="automaticRunPlan" name="automaticRunPlan" id="automaticRunPlan" class="whiteCheck"
      <?php if ( $automaticRunPlanning) {echo 'checked="checked"'; } ?>  >  
      <script type="dojo/connect" event="onChange" args="evt">
        saveUserParameter('automaticRunPlanning',((this.checked)?'1':'0'));
      </script>                    
    </span><div style="font-size:90%;margin:auto"><?php if (0 and $displayWidthPlan>1250) echo i18n('automaticRunPlan'); else echo i18n('automaticRunPlanShort');?></div>
  </div>
<?php 
}

//Gautier Param
function drawDisplayField($planning) {
  global $saveShowWbs, $saveShowClosed, $saveShowResource,$planningType, $showListFilter,$showClosedPlanningVersion,$showColorActivity,$showColorTypeActivity,$showHatchOnPlanningBar;?>
    <?php $tableWidth = ($planning=='workPlan')?'330px':'100%';?>
    <table style="width:100%;" class="planningDialogArea">
      <tr>
        <td colspan="2" style="padding-top:3px;padding-left:5px;padding-right:3px">
          <table style="width:<?php echo $tableWidth;?>;"><tr>
            <td style="width:40px;"><div class="iconChangeLayout iconSize32 imageColorNewGuiNoSelection" style="border:0"></div></td>
            <td class="dependencyHeader planningDialogTitle" style="text-align:left;"> &nbsp;&nbsp;<?php echo ($planning=='workPlan')?i18n('displayOnWorkPlan'):i18n('displayOnGantt');?></td>
          </tr></table>
        </td>
      </tr>
      
      <?php if($planning!='workPlan'){?>
      <tr>
        <td colspan="2">
          <table style="margin-left:5px;">
            <tr>
              <td style="text-align:right"><?php echo i18n('displayStartDate');?>&nbsp;</td><td><?php drawFieldStartDate();?></td><td style="padding:5px;padding-top:14px;"><?php drawOptionSaveDates();?>&nbsp;&nbsp;</td>
            </tr>
            <tr>
              <td style="text-align:right"><?php echo i18n('displayEndDate');?>&nbsp;</td><td><?php drawFieldEndDate();?></td><td style="padding-left:5px;padding-bottom:15px;"><?php drawOptionAllProject();?>&nbsp;&nbsp;</td>
            </tr>
          </table>
        </td>
      </tr>
      <?php } ?>
      
      <tr>
        <td class="title" style="display:none;width:40px;font-size:small;padding-left:5px;padding-top:5px;font-weight:normal"><?php echo i18n('tabDisplay');?></td>
        <td style="width:100%;padding-left:5px;padding-right:5px"><div style="height:4px;width:100%;border-bottom:1px solid var(--color-detail-header-text) !important;" ></div></td>
      </tr>
      
      <tr>
       <td colspan="2">
        <table>
            <tr>
              <td>
                <?php drawOptionsDisplaySwitch($planning);?>
              </td>
            </tr>
        </table>
       </td>
      </tr>
      
      <?php if($planning=='version'){?>
      <tr id="specificVersionFieldsSeparatorTR" style="display:<?php  echo ($showListFilter=='true')?'table-row':'none';?>;">
        <td class="title" style="display:none;width:40px;font-size:small;padding-left:5px;padding-top:5px;font-weight:normal"><?php echo i18n('option');?></td>
        <td style="width:100%;padding-left:5px;padding-right:5px"><div style="height:4px;width:100%;border-bottom:1px solid var(--color-detail-header-text) !important;" ></div></td>
      </tr>            
      
     <tr>
       <td colspan="2">
        <table>
            <tr>
              <td>
                <?php drawDisplayFieldVersion($planning);?>
              </td>
            </tr>
        </table>
       </td>
      </tr>
      <?php } ?>
    </table>
    <?php
}

function drawDisplayValidatedPlanning() {
  ?> 
  <table style="width:100%;" class="planningDialogArea">
    <tr>
      <td style="width:40px;padding-top:2px;padding-left:5px">
       <div class="iconPlanningValidation iconSize32 imageColorNewGuiNoSelection"></div>
      </td>  
      <td style="padding-top:3px;padding-bottom:3px;">
          <table style="width:100%;height:100%"><tr style="height:32px"><td class="dependencyHeader planningDialogTitle" style="text-align:left;"> &nbsp;&nbsp;<?php echo i18n('validatePlanning');?></td></tr></table>
      </td>
      <td style="width:44px;padding-left:5px">  
             <button title="<?php echo i18n('validateThePlanning');?>" dojoType="dijit.form.Button"
                id="savePlanningButton" name="savePlanningButton" class="iconButtonResetMargin roundedButton notButton" style="position:relative; top:-7px;"
                iconClass="iconButtonValidate iconSize32 imageColorNewGui " showLabel="false">
                 <script type="dojo/connect" event="onClick" args="evt">
		              showPlanSaveDates();
                  return false;  
                </script>
             </button>
      </td>
    </tr>
  </table>
  <?php
}

function drawDisplayExportProject() {
  ?>
  <table style="border:solid 1px lightgray;width:100%;">
    <tr>
      <td style="width:40px;padding-top:2px;">
          <button title="<?php echo i18n('reportExportMSProject')?>"
          dojoType="dijit.form.Button"
          id="listPrintMppButt" name="listPrintMppButt"
          iconClass="dijitButtonIcon dijitButtonIconMSProject" class="buttonIconNewGui detailButton" showLabel="false">
        </button>
        
      </td>
      <td class="messageHeader" style="text-align:left;">&nbsp;&nbsp;<?php echo i18n('exportPlanningMsProject');?></td>
      <td style="width:44px;">  
             <button title="<?php echo i18n('reportExportMSProject');?>" dojoType="dijit.form.Button"
                id="listPrintMpp" name="listPrintMpp" class="resetMargin roundedButton notButton" style="height:24px;width:32px;margin-top:-5px;"
                iconClass="iconButtonDownload iconSize22 imageColorNewGui" showLabel="false">
                 <script type="dojo/connect" event="onClick" args="evt">
		              showPrint("../tool/jsonPlanning.php", 'planning', null, 'mpp'); 
                </script>
             </button>
             <input type="hidden" id="outMode" name="outMode" value="" />
      </td>
    </tr>
  </table>
  <?php
}

function drawExports($print=true,$pdf=true,$ms=true) {
  ?>
  <table style="width:100%;min-width:300px" class="planningDialogArea">
     <tr>
      <td colspan="2" style="padding-top:3px;padding-left:5px;padding-right:3px">
        <table style="width:100%;"><tr><td style="width:35px;"><div style="position:relative;left:-2px;top:-2px" class="iconExport iconSize32 imageColorNewGuiNoSelection"></div></td><td class="dependencyHeader planningDialogTitle" style="text-align:left;"> &nbsp;&nbsp;<?php echo i18n('tabExport');?></td></tr></table>
      </td>
    </tr>
    <tr>
      <td colspan="2">
        <table style="width:100%;">
          <tr>
          <?php if($print){?>
            <td style="width:40px">&nbsp;</td>
            <td style="width:100px;text-align:center;padding:5px;padding-top:0;vertical-align:top">
                <button title="<?php echo i18n('printPlanning')?>"
                 dojoType="dijit.form.Button"
                 id="listPrint" name="listPrint"
                 iconClass="iconButton imageColorNewGui iconPrint iconSize32" class="detailButton" showLabel="false">
                  <script type="dojo/connect" event="onClick" args="evt">
                  <?php 
                    $ganttPlanningPrintOldStyle=Parameter::getGlobalParameter('ganttPlanningPrintOldStyle');
                    if (!$ganttPlanningPrintOldStyle) {$ganttPlanningPrintOldStyle="NO";}
                    if ($ganttPlanningPrintOldStyle=='YES') {?>
	                 showPrint("../tool/jsonPlanning.php"+addTokenIndexToUrl('?'), 'planning');
                  <?php } else { ?>
                     showPrint("planningPrint.php", 'planning');
                  <?php }?>                          
                  </script>
                </button>
                <div style="xfont-style:italic;font-size:80%;color:#a0a0a0"><?php echo i18n('planningPrint');?></div>
            </td>
            <?php } ?>
            <?php if($pdf){?>
            <td style="width:100px;text-left;text-align:center;padding:5px;padding-top:0;vertical-align:top">
                <button title="<?php echo i18n('reportPrintPdf')?>"
                  dojoType="dijit.form.Button"
                  id="listPrintPdf" name="listPrintPdf"
                  iconClass="iconButton imageColorNewGui iconButtonPdf iconSize32" class="detailButton" showLabel="false">
                  <script type="dojo/connect" event="onClick" args="evt">
                  var paramPdf='<?php echo Parameter::getGlobalParameter("pdfPlanningBeta");?>';
                  if(paramPdf!='false') planningPDFBox();
                  else showPrint("../tool/jsonPlanning_pdf.php"+addTokenIndexToUrl('?'), 'planning', null, 'pdf');
                  </script>
                </button>
                <div style="xfont-style:italic;font-size:80%;color:#a0a0a0"><?php echo i18n('planningPDF');?></div>
            </td>
            <?php } ?>
            <?php if($ms){?>
            <td style="width:100px;text-left;text-align:center;padding:5px;padding-top:0;vertical-align:top">
                 <button title="<?php echo i18n('reportExportMSProject')?>"
                  dojoType="dijit.form.Button"
                  id="listPrintMpp" name="listPrintMpp"
                  iconClass="iconButton imageColorNewGui iconButtonMsProject iconSize32" class="detailButton" showLabel="false">
                  <script type="dojo/connect" event="onClick" args="evt">
                    showPrint("../tool/jsonPlanning.php", 'planning', null, 'mpp');
                  </script>
                </button>
                <div style="xfont-style:italic;font-size:80%;color:#a0a0a0"><?php echo i18n('planningMSProject');?></div>
                <input type="hidden" id="outMode" name="outMode" value="" />
            </td>
            <?php } ?>
            <td>&nbsp;</td>
            <?php if($ms){?>
            <td style="width:100px;text-left;text-align:center;padding:5px;padding-top:0;vertical-align:top">
                 <button title="<?php echo i18n('PlanningHistory')?>"
                  dojoType="dijit.form.Button"
                  id="listPlanningHistory" name="listPlanningHistory"
                  iconClass="iconButton imageColorNewGui iconButtonHistory iconSize32" class="detailButton" showLabel="false">
                  <script type="dojo/connect" event="onClick" args="evt">
                    showPlanningHistory();
                  </script>
                </button>
                <div style="xfont-style:italic;font-size:80%;color:#a0a0a0"><?php echo i18n('PlanningHistory');?></div>
                <input type="hidden" id="outMode" name="outMode" value="" />
            </td>
            <?php } ?>
            <td>&nbsp;</td>
          </tr>
          <tr><td colspan="6" style="text-align:right;">
            <table style="float:right;"><tr>
              <?php
              global $planningType;
              $buttonType=($planningType=='planning')?'Planning':ucfirst($planningType).'Planning';
              $extraPlgButtons=Plugin::getButtons('extra', $buttonType);
              foreach ($extraPlgButtons as $bt) { ?>
                <td style="width:100px;text-align:center;padding:5px;padding-top:0;vertical-align:top">
                <button id="pluginButtonList<?php echo $bt->id;?>" dojoType="dijit.form.Button" showlabel="false"
                  title="<?php echo i18n($bt->buttonName);?>"
                  iconClass="<?php echo $bt->iconClass;?>" class="detailButton">
                  <script type="dojo/connect" event="onClick" args="evt">
                  <?php if ($bt->scriptJS) {
                          echo $bt->scriptJS;
                        } else { ?>
                        loadContent("<?php echo $bt->scriptPHP.'?objectClassManual='.$buttonType;?>", "resultDivMain", "listForm", true);
                  <?php }?>
                  </script>
                </button>
                <div style="xfont-style:italic;font-size:80%;color:#a0a0a0"><?php echo i18n($bt->buttonName);?></div>
                <td>
              <?php }?>
              
              </tr></table>
          </td></tr>  
        </table>
      </td>
    </tr>
  </table>
  <?php
}

function drawDisplayBaseline() {
?>
  <table style="width:100%;" class="planningDialogArea">
    <tr>
      <td colspan="2">    
        <table style="width:100%;">
          <tr>
             <td style="width:40px;padding-top:2px;padding-left:5px">
               <div title="<?php echo i18n('baselineSimple');?>" class="iconPlanningBaseline iconSize32 imageColorNewGuiNoSelection"></div>
            </td>      
            <td style="padding-top:3px;padding-bottom:3px;">
                <table style="width:100%;height:100%"><tr style="height:32px"><td class="dependencyHeader planningDialogTitle" style="text-align:left;"> &nbsp;&nbsp;<?php echo i18n('baselineSimple');?></td></tr></table>
            </td>
            <td style="width:44px;padding-left:5px">  
              <button title="<?php echo i18n('baselineSimple');?>" dojoType="dijit.form.Button"
                id="saveBaselineButton" name="saveBaselineButton" class="iconButtonResetMargin roundedButton notButton" style="position:relative;top:-7px;"
                iconClass="iconAdd  iconSize32 imageColorNewGui" showLabel="false">
                <script type="dojo/connect" event="onClick" args="evt">
		            showPlanningBaseline();
                return false;  
              </script>
              </button>
            </td>
          </tr>
        </table>
      </td>
    </tr>
    <tr style="display:none;">
      <td class="title" style="font-size:small;width:80px;padding-top:8px;padding-left:5px;"><?php echo i18n('tabDisplay');?></td><td style="padding-top:8px;padding-right:3px;"><div style="height:2px;width:100%;border-bottom:1px solid var(--color-detail-header-text) !important;" ></div></td>
    </tr>
    <tr>
      <td colspan="2"><?php drawOptionBaselineNew();?></td>
    </tr>
    
  </table>
<?php 
}

function drawTimeLine() {
  ?>
  <table style="width:100%;" class="planningDialogArea">
    <tr>
      <td style="width:40px;padding-top:2px;"><div class="iconTimeline iconSize32 imageColorNewGuiNoSelection" style="position:relative;left:3px;top:-3px"></div></td>
      <td style="padding-top:3px;padding-bottom:3px;padding-right:3px">
          <table style="width:100%;height:100%"><tr style="height:32px"><td class="dependencyHeader planningDialogTitle" style="text-align:left;"> &nbsp;&nbsp;<?php echo i18n('Timeline');?></td></tr></table>
      </td>
    </tr>
    <tr>
      <td colspan="2"><?php drawOptionHideTimelineNew();?></td>
    </tr>
  </table>
<?php 
}

// ================================================== FIELD START DATE FOR DISPLAY
function drawFieldStartDate($planning="planning") {
  global $projectDate,$startDate; ?>         
  <div dojoType="dijit.form.DateTextBox"
  	<?php if (sessionValueExists('browserLocaleDateFormatJs')) {
			echo ' constraints="{datePattern:\''.getSessionValue('browserLocaleDateFormatJs').'\'}" ';
		}?>
    id="startDatePlanView" name="startDatePlanView"
    invalidMessage="<?php echo i18n('messageInvalidDate')?>"
    type="text" maxlength="10" 
    <?php if ($projectDate) {echo 'disabled'; } ?> 
    style="width:100px; text-align: center;" class="input roundedLeft"
    hasDownArrow="true"
    <?php echo autoClearDateTextbox(); ?>
    value="<?php if(sessionValueExists('startDatePlanView') and !$projectDate){ echo getSessionValue('startDatePlanView'); }else{ echo $startDate; } ?>" >
    <script type="dojo/method" event="onChange" >
      saveDataToSession('startDatePlanView',formatDate(dijit.byId('startDatePlanView').get("value")), true);
      saveDataToSession('startDateWorkPlanView',formatDate(dijit.byId('startDatePlanView').get("value")), true);
      <?php if($planning == 'workPlan'){?>
      refreshJsonWorkPlan();
      <?php }else{ ?>
      refreshJsonPlanning();
      <?php } ?>
    </script>
  </div>
<?php 
}

function drawWorkPlanFieldStartDate() {
  global $projectDate,$startDate,$currentLocale;
  $workPlanDatePattern=(pq_substr($currentLocale, 0, 2)=='fr')?'dd/MM/yyyy':getSessionValue('browserLocaleDateFormatJs'); ?>
  <div dojoType="dijit.form.DateTextBox"
	<?php if ($workPlanDatePattern) {
			echo ' constraints="{datePattern:\''.$workPlanDatePattern.'\'}" ';
		}?>
    id="startDatePlanView" name="startDatePlanView"
    invalidMessage="<?php echo i18n('messageInvalidDate')?>"
    type="text" maxlength="10" 
    <?php if ($projectDate) {echo 'disabled'; } ?> 
    style="width:100px; text-align: center;" class="input roundedLeft"
    hasDownArrow="true"
    <?php echo autoClearDateTextbox(); ?>
    value="<?php if(sessionValueExists('startDateWorkPlanView') and !$projectDate){ echo getSessionValue('startDateWorkPlanView'); }else{ echo $startDate; } ?>" >
    <script type="dojo/method" event="onChange" >
      saveDataToSession('startDateWorkPlanView',formatDate(dijit.byId('startDatePlanView').get("value")), true);
      var workPlanDurationMode=dijit.byId('workPlanDurationMode');
      if (workPlanDurationMode && workPlanDurationMode.get('value')!=='') {
        changeParamWorkPlanDurationMode(workPlanDurationMode.get('value'));
      } else {
        refreshJsonWorkPlan();
      }
    </script>
  </div>
<?php 
}

// ================================================== FIELD END DATE FOR DISPLAY
function drawFieldEndDate($planning="planning") {
  global $projectDate,$endDate; ?>                           
    <div dojoType="dijit.form.DateTextBox"
      <?php if (sessionValueExists('browserLocaleDateFormatJs')) {
				echo ' constraints="{datePattern:\''.getSessionValue('browserLocaleDateFormatJs').'\'}" ';
			}?>
      id="endDatePlanView" name="endDatePlanView"
      invalidMessage="<?php echo i18n('messageInvalidDate')?>"
      type="text" maxlength="10"
      <?php if ($projectDate) {echo 'disabled'; } ?> 
      style="width:100px; text-align: center;" class="input roundedLeft"
      hasDownArrow="true"
      <?php echo autoClearDateTextbox(); ?>
      value="<?php if(sessionValueExists('endDatePlanView') and !$projectDate){ echo getSessionValue('endDatePlanView'); }else{ echo $endDate; } ?>" >
      <script type="dojo/method" event="onChange" >
        saveDataToSession('endDatePlanView',formatDate(dijit.byId('endDatePlanView').get("value")), false);
        saveDataToSession('endDateWorkPlanView',formatDate(dijit.byId('endDatePlanView').get("value")), true);
        <?php if($planning == 'workPlan'){?>
        refreshJsonWorkPlan();
        <?php }else{ ?>
        refreshJsonPlanning();
        <?php } ?>
      </script>
    </div>
<?php 
}

function drawWorkPlanFieldEndDate() {
  global $projectDate,$endDate,$currentLocale;
  $workPlanDatePattern=(pq_substr($currentLocale, 0, 2)=='fr')?'dd/MM/yyyy':getSessionValue('browserLocaleDateFormatJs'); ?>
    <div dojoType="dijit.form.DateTextBox"
      <?php if ($workPlanDatePattern) {
				echo ' constraints="{datePattern:\''.$workPlanDatePattern.'\'}" ';
			}?>
      id="endDatePlanView" name="endDatePlanView"
      invalidMessage="<?php echo i18n('messageInvalidDate')?>"
      type="text" maxlength="10"
      <?php if ($projectDate) {echo 'disabled'; } ?> 
      style="width:100px; text-align: center;" class="input roundedLeft"
      hasDownArrow="true"
      <?php echo autoClearDateTextbox(); ?>
      value="<?php if(sessionValueExists('endDateWorkPlanView') and !$projectDate){ echo getSessionValue('endDateWorkPlanView'); }else{ echo $endDate; } ?>" >
      <script type="dojo/method" event="onChange" >
        saveDataToSession('endDateWorkPlanView',formatDate(dijit.byId('endDatePlanView').get("value")), true);
        if (typeof workPlanDurationChangeInProgress==='undefined' || !workPlanDurationChangeInProgress) {
          refreshJsonWorkPlan();
        }
      </script>
    </div>
<?php 
}

// ================================================== CHECKBOX SAVE DATES
function drawOptionSaveDates() {
  global $projectDate, $saveDates; ?>
  <span title="<?php echo i18n('saveDates')?>" dojoType="dijit.form.CheckBox"
    type="checkbox" id="listSaveDates" name="listSaveDates" class="whiteCheck"
    <?php if ($projectDate) {echo 'disabled'; } ?> 
    <?php if ( $saveDates) {echo 'checked="checked"'; } ?>  >
    <script type="dojo/method" event="onChange" >
      refreshJsonPlanning();
    </script>
  </span>
  <span for="listSaveDates"><?php echo i18n("saveDates");?></span>
<?php 
}

// ================================================== CHECKBOX SHOW ALL THE PROJECT
function drawOptionAllProject($planning="planning") {  
  global $projectDate;?>                      
  <span title="<?php echo i18n("projectDate")?>" dojoType="dijit.form.CheckBox"
    type="checkbox" id="projectDate" name="projectDate" class="whiteCheck"
    <?php if ($projectDate) {echo 'checked="checked"'; } ?>  >
    <script type="dojo/method" event="onChange" >
      <?php if($planning == "workPlan"){?>
      saveUserParameter('workPlanProjectDate',((this.checked)?'1':'0'));
      <?php }else{ ?>
      saveUserParameter('workPlanProjectDate',((this.checked)?'1':'0'));
      saveUserParameter('projectDate',((this.checked)?'1':'0'));
      <?php } ?>
      var now = formatDate(new Date());
      if (this.checked == false) {
        //dojo.setAttr('startDatePlanView', 'value', date.toLocaleDateString());
        if (endDatePlanViewSaved) dijit.byId('endDatePlanView').set("value",endDatePlanViewSaved);
        if (startDatePlanViewSaved) dijit.byId('startDatePlanView').set("value",startDatePlanViewSaved);
        else dijit.byId('startDatePlanView').set("value",now);
        enableWidget("startDatePlanView");
        enableWidget("endDatePlanView");
        enableWidget("listSaveDates");
        <?php if($planning == 'workPlan'){?>
        enableWidget("workPlanDurationMode");
        <?php }?>
        if(dojo.byId('planningJsonData')){
          g.setPlanningMinDate(dijit.byId('startDatePlanView').get('value'));
          g.setPlanningMaxDate(dijit.byId('endDatePlanView').get('value'));
        }
        if(dojo.byId('workPlanJsonData')){
          gwp.setPlanningMinDate(dijit.byId('startDatePlanView').get('value'));
          gwp.setPlanningMaxDate(dijit.byId('endDatePlanView').get('value'));
        }
      } else {
        startDatePlanViewSaved=dijit.byId('startDatePlanView').get('value');
        endDatePlanViewSaved=dijit.byId('endDatePlanView').get('value');
        dijit.byId('startDatePlanView').reset();
        dijit.byId('endDatePlanView').reset();
        if(dijit.byId('listSaveDates'))dijit.byId('listSaveDates').set('checked', false);
        disableWidget("startDatePlanView");
        disableWidget("endDatePlanView");
        disableWidget("listSaveDates");
        <?php if($planning == 'workPlan'){?>
        disableWidget("workPlanDurationMode");
        <?php }?>
        if(dojo.byId('planningJsonData')){
          g.setPlanningMinDate(null);
          g.setPlanningMaxDate(null);
        }
        if(dojo.byId('workPlanJsonData')){
          gwp.setPlanningMinDate(null);
          gwp.setPlanningMaxDate(null);
        }
      }
      <?php if($planning == 'workPlan'){?>
      refreshJsonWorkPlan();
      <?php }else{ ?>
      refreshJsonPlanning();
      <?php } ?>
    </script>
  </span>
  <span for="projectDate"><?php echo i18n("projectDate");?></span>
<?php 
}

// ================================================== BUTTONS FOR PLANNING FUNCTIONS (save validated dates, baselines, print, pdf export)
function drawButtonsPlanning() { 
  global $canPlan,$showValidationButton, $planningType;?>
  <table>
    <tr>
      <?php 
      if ($canPlan and ($planningType=='planning' or $planningType=='global') ) { 
        if($showValidationButton){
      ?>
      <td colspan="1" width="32px">
        <button id="savePlanningButton" dojoType="dijit.form.Button" showlabel="false"
         title="<?php echo i18n('validatePlanning');?>" 
         iconClass="dijitButtonIcon dijitButtonIconValidPlan" class="buttonIconNewGui detailButton">
         <script type="dojo/connect" event="onClick" args="evt">
		       showPlanSaveDates();
           return false;  
         </script>
        </button>
      </td>
      <?php 
        }
      ?>
      <td colspan="1" width="32px">
        <button id="saveBaselineButton" dojoType="dijit.form.Button" showlabel="false"
          title="<?php echo i18n('savePlanningBaseline');?>"
          iconClass="dijitButtonIcon dijitButtonIconSavePlan" class="buttonIconNewGui detailButton">
          <script type="dojo/connect" event="onClick" args="evt">
		        showPlanningBaseline();
            return false;  
          </script>
        </button>
      </td>
      <?php 
      }
      ?>  
      <td colspan="1" width="32px">
        <button title="<?php echo i18n('printPlanning')?>"
         dojoType="dijit.form.Button"
         id="listPrint" name="listPrint"
         iconClass="dijitButtonIcon dijitButtonIconPrint" class="buttonIconNewGui detailButton" showLabel="false">
          <script type="dojo/connect" event="onClick" args="evt">
            <?php 
            $ganttPlanningPrintOldStyle=Parameter::getGlobalParameter('ganttPlanningPrintOldStyle');
            if (!$ganttPlanningPrintOldStyle) {$ganttPlanningPrintOldStyle="NO";}
            if ($ganttPlanningPrintOldStyle=='YES') {?>
	            showPrint("../tool/jsonPlanning.php"+addTokenIndexToUrl('?'), 'planning');
            <?php } else { ?>
              showPrint("planningPrint.php", 'planning');
            <?php }?>                          
          </script>
        </button>
      </td>
      <td colspan="1" width="32px">
        <button title="<?php echo i18n('reportPrintPdf')?>"
          dojoType="dijit.form.Button"
          id="listPrintPdf" name="listPrintPdf"
          iconClass="dijitButtonIcon dijitButtonIconPdf" class="buttonIconNewGui detailButton" showLabel="false">
          <script type="dojo/connect" event="onClick" args="evt">
            var paramPdf='<?php echo Parameter::getGlobalParameter("pdfPlanningBeta");?>';
            if(paramPdf!='false') planningPDFBox();
            else showPrint("../tool/jsonPlanning_pdf.php"+addTokenIndexToUrl('?'), 'planning', null, 'pdf');
          </script>
        </button>
      </td>
      <?php if ($planningType=='planning' or $planningType=='global') {?>
      <td width="32px" style="padding-right:10px;">
        <button title="<?php echo i18n('reportExportMSProject')?>"
          dojoType="dijit.form.Button"
          id="listPrintMpp" name="listPrintMpp"
          iconClass="dijitButtonIcon dijitButtonIconMSProject" class="buttonIconNewGui detailButton" showLabel="false">
          <script type="dojo/connect" event="onClick" args="evt">
            showPrint("../tool/jsonPlanning.php", 'planning', null, 'mpp');
          </script>
        </button>
        <input type="hidden" id="outMode" name="outMode" value="" />
      </td>
      <?php }?>
    </tr>
  </table>
<?php 
}

// ================================================== BUTTONS DEFAULT (NEW, FILTER, COLUMNS)
function drawButtonsDefault() {
  global $objectClass, $planningType, $showListFilter;
  $planningClass = array('planning'=>'Planning','portfolio'=>'PortfolioPlanning','resource'=>'ResourcePlanning','global'=>'GlobalPlanning','version'=>'VersionPlanning','contract'=>'ContractGantt');
  ?>
  <table style="width:10px">
    <tr>
    <?php
      global $planningType;
      $buttonType=($planningType=='planning')?'Planning':ucfirst($planningType).'Planning';
      $extraPlgButtons=Plugin::getButtons('list', $buttonType);     
      foreach ($extraPlgButtons as $bt) { ?>
        <td colspan="1">
        <button id="pluginButtonList<?php echo $bt->id;?>" dojoType="dijit.form.Button" showlabel="false"
          title="<?php echo i18n($bt->buttonName);?>"
          iconClass="<?php echo $bt->iconClass;?>" class="detailButton">
          <script type="dojo/connect" event="onClick" args="evt">
                  <?php if ($bt->scriptJS) {
                  echo $bt->scriptJS;
                } else { ?>
                        loadContent("<?php echo $bt->scriptPHP.'?objectClassManual='.$buttonType;?>", "resultDivMain", "listForm", true);
                  <?php }?>
                  </script>
        </button>
        </td>
    <?php }?>   
    <?php 
      if ($planningType=='planning'){?>
         <td colspan="1">
      <button id="saveBaselineButtonMenu" dojoType="dijit.form.Button" showlabel="false"
          title="<?php echo i18n('savePlanningBaseline');?>"
              iconClass="dijitButtonIcon dijitButtonIconSavePlan" class="buttonIconNewGui detailButton">
              <script type="dojo/connect" event="onClick" args="evt">
              showPlanningBaseline();
      return false;
      </script>
      </button>
      </td>
      <?php }
      if ($planningType=='planning' or $planningType=='resource' or $planningType=='global' or $planningType=='version') {?>
        <td colspan="1" width="51px" style="<?php if (isNewGui()) echo 'padding-right: 5px;';?>">
          <?php // ================================================================= NEW ?>
          <?php if ($planningType=='version') {?><div id ="addNewActivity" style="visibility:<?php echo ($showListFilter=='true')?'visible':'hidden';?>;"><?php } ?>
          <div dojoType="dijit.form.DropDownButton"
            class="comboButton"   
            id="planningNewItem" jsId="planningNewItem" name="planningNewItem" 
            showlabel="false" class="" iconClass="dijitButtonIcon dijitButtonIconNew"
            title="<?php echo i18n('comboNewButton');?>">
            <span>title</span>
            <div dojoType="dijit.TooltipDialog" class="white" style="width:200px;">   
              <div style="font-weight:bold; height:25px;text-align:center"><?php echo i18n('comboNewButton');?>      </div>
              <?php 
              $arrayItems=array('Project','Activity','Milestone','Meeting','PeriodicMeeting','TestSession');
              if ($planningType=='resource' or $planningType=='version') $arrayItems=array('Activity');
              if ($planningType=='global') $arrayItems=array_merge($arrayItems,array('Ticket','Action','Decision','Delivery','Deliverable','Incoming','Risk','Issue','Opportunity','Question'));
              foreach($arrayItems as $item) {
                $canCreate=securityGetAccessRightYesNo('menu' . $item,'create');
                if ($canCreate=='YES') {
                  if (! securityCheckDisplayMenu(null,$item) ) {
                    $canCreate='NO';
                  }
                }
                if ($canCreate=='YES') {?>
                  <div style="vertical-align:top;cursor:pointer;" class="newGuiIconText"
                    onClick="addNewItem('<?php echo $item;?>');" >
                    <table width:"100%"><tr style="height:22px" >
                      <td style="vertical-align:top; width: 30px;padding-left:5px"><?php echo formatIcon($item, 22, null, false);;?></td>    
                      <td style="vertical-align:top;padding-top:2px"><?php echo i18n($item)?></td>
                    </tr></table>   
                  </div>
                  <div style="height:5px;"></div>
                <?php 
                } 
              }?>
            </div>
          </div>
          <?php if ($planningType=='version') {?></div><?php } ?>        
        </td>   
      <?php
      } 
      if ($planningType=='global') {?>
        <td colspan="1" width="51px" style="<?php if (isNewGui()) echo 'padding-right: 5px;';?>">
          <?php drawGlobalItemsSelector();?>
        </td>  
      <?php 
      } 
      $activeFilter=false;
      if (is_array(getSessionUser()->_arrayFilters)) {
        if (pq_array_key_exists('Planning', getSessionUser()->_arrayFilters)) {
          if (count(getSessionUser()->_arrayFilters['Planning'])>0) {
         	  foreach (getSessionUser()->_arrayFilters['Planning'] as $filter) {
         		  if (!isset($filter['isDynamic']) or $filter['isDynamic']=="0") {
         			  $activeFilter=true;
         		  }
         	  }
          }
        }
      }
      ?>
      <?php 
      if ($planningType=='planning' or $planningType=='resource' or $planningType=='version') {?>
        <td colspan="1" width="55px" style="padding-left:1px";>
          <?php // ================================================================= FILTER ?>
          <?php if ($planningType=='version') {?><div id="listFilterAdvanced" style="visibility:<?php echo ($showListFilter=='true')?'visible':'hidden';?>;"><?php }?>
          <button title="<?php echo i18n('advancedFilter')?>"  
            class="comboButton"
            dojoType="dijit.form.DropDownButton" 
            id="listFilterFilter" name="listFilterFilter"
            iconClass="dijitButtonIcon icon<?php echo($activeFilter)?'Active':'';?>Filter" showLabel="false">
            <?php 
            if(!isNewGui()){?>
              <script type="dojo/connect" event="onClick" args="evt">
                showFilterDialog();
              </script>
              <script type="dojo/method" event="onMouseEnter" args="evt">
                clearTimeout(closeFilterListTimeout);
                clearTimeout(openFilterListTimeout);
                openFilterListTimeout=setTimeout("dijit.byId('listFilterFilter').openDropDown();",popupOpenDelay);
              </script>
              <script type="dojo/method" event="onMouseLeave" args="evt">
                clearTimeout(openFilterListTimeout);
                closeFilterListTimeout=setTimeout("dijit.byId('listFilterFilter').closeDropDown();",2000);
              </script>
              <?php 
            }?>
            <div dojoType="dijit.TooltipDialog" id="directFilterList" style="z-index: 999999;<!-- display:none; --> position: absolute;">
              <?php 
              $objectClass='Planning';
              $dontDisplay=true;
              if(isNewGui())include "../tool/displayQuickFilterList.php";
              include "../tool/displayFilterList.php";
              if(!isNewGui()){?>
                <script type="dojo/method" event="onMouseEnter" args="evt">
                  clearTimeout(closeFilterListTimeout);
                  clearTimeout(openFilterListTimeout);
                </script>
                <script type="dojo/method" event="onMouseLeave" args="evt">
                  dijit.byId('listFilterFilter').closeDropDown();
                </script>
              <?php  
              }?>
            </div> 
          </button>
          <?php if ($planningType=='version') {?></div><?php }?>
        </td>
       <?php 
      }?>  
      <td colspan="1">
        <?php // ================================================================= COLUMNS SELECTOR ?> 
        <div dojoType="dijit.form.DropDownButton"
          id="planningColumnSelector" jsId="planningColumnSelector" name="planningColumnSelector"  
          showlabel="false" class="comboButton" iconClass="dijitButtonIcon dijitButtonIconColumn" 
          title="<?php echo i18n('columnSelector');?>">
          <span>title</span>
          <?php 
          $screenHeight=getSessionValue('screenHeight','1080');
          $columnSelectHeight=intval($screenHeight*0.6);?>
          <div dojoType="dijit.TooltipDialog" id="planningColumnSelectorDialog" class="white" style="width:350px;">   
            <script type="dojo/connect" event="onHide" data-dojo-args="evt">
              if (dndMoveInProgress) {  setTimeout('dijit.byId("planningColumnSelector").openDropDown();',1); }
            </script>
            <div style="text-align: center;">
                <button dojoType="dijit.form.Button" title="<?php echo i18n('titleResetList');?>"
                  class="mediumTextButton" id="" name="" showLabel="true"><?php echo i18n('buttonReset');?>
                  <script type="dojo/connect" event="onClick" args="evt">
                        resetPlanningListColumn();
                      </script>
                </button>
               <button title="" dojoType="dijit.form.Button" 
                  class="mediumTextButton" id="" name="" showLabel="true"><?php echo i18n('buttonManageLayout');?>
                  <script type="dojo/connect" event="onClick" args="evt">
                     showLayoutDialog('<?php echo $planningClass[$planningType];?>');
                  </script>
                </button> 
              <button title="" dojoType="dijit.form.Button" 
                class="mediumTextButton" id="" name="" showLabel="true"><?php echo i18n('buttonOK');?>
                <script type="dojo/connect" event="onClick" args="evt">
                  validatePlanningColumn('<?php echo $planningType;?>');
                </script>
              </button>
            </div>
            <div style="height:5px;"></div>
            <div id="divPlanningColumnSelector" dojoType="dijit.layout.ContentPane" region="top">
              <div id="dndPlanningColumnSelector" jsId="dndPlanningColumnSelector" dojotype="dojo.dnd.Source"  
                dndType="column" style="overflow-y:auto; max-height:<?php echo $columnSelectHeight;?>px; position:relative"
                withhandles="true" class="container">    
                <?php 
                if ($planningType=='portfolio') $portfolioPlanning=true;
                if ($planningType=='contract') $contractGantt=true;
                if ($planningType=='version') $versionPlanning=true;
                if ($planningType=='resource') $resourcePlanning=true;
                include('../tool/planningColumnSelector.php');?>
              </div>
            </div>
            <div style="height:5px;"></div>    
            <div style="text-align: center;">
                <button dojoType="dijit.form.Button" title="<?php echo i18n('titleResetList');?>"
                  class="mediumTextButton" id="" name="" showLabel="true"><?php echo i18n('buttonReset');?>
                  <script type="dojo/connect" event="onClick" args="evt">
                        resetPlanningListColumn();
                      </script>
                </button>
               <button title="" dojoType="dijit.form.Button" 
                  class="mediumTextButton" id="" name="" showLabel="true"><?php echo i18n('buttonManageLayout');?>
                  <script type="dojo/connect" event="onClick" args="evt">
                     showLayoutDialog('<?php echo $planningClass[$planningType];?>');
                  </script>
                </button> 
              <button title="" dojoType="dijit.form.Button" 
                class="mediumTextButton" id="" name="" showLabel="true"><?php echo i18n('buttonOK');?>
                <script type="dojo/connect" event="onClick" args="evt">
                  validatePlanningColumn('<?php echo $planningType;?>');
                </script>
              </button>
            </div>          
          </div>
        </div>
      </td>
    </tr>
  </table>
<?php 
}

// ================================================== BASELINE
function drawOptionBaselineNew() {
  global $displayWidthPlan,$proj;?>
  <table style="margin-bottom:3px;">
    <tr>
      <td style="text-align:right;white-space:nowrap;padding-left:8px;padding-right:8px;">
      <table>
        <td>
        <?php 
        if (isNewGui()) echo pq_ucfirst(i18n('baselineTop')) .'&nbsp;';
        else echo (($displayWidthPlan>1230)?i18n('baselineTop'):i18n('baselineTopShort')).'&nbsp;:&nbsp;';?>
        <select dojoType="dijit.form.FilteringSelect" class="input roundedLeft" 
          style="width:<?php echo ($displayWidthPlan>930)?'300':'80';?>px;"
          data-dojo-props="queryExpr: '*${0}*', autoComplete:false"
          name="selectBaselineTop" id="selectBaselineTop"
          <?php echo autoOpenFilteringSelect();?> >
          <script type="dojo/method" event="onChange" >
            saveDataToSession("planningBaselineTop",this.value,false);
            refreshJsonPlanning();
          </script>
          <?php htmlDrawOptionForReference('idBaselineSelect', getSessionValue("planningBaselineTop"), null,false,null,null);?>
        </select>
        </td>
        
        <?php 
        $colorBaselineUpper = Parameter::getUserParameter('colorBaselineUpper') !== '' ? '#' . Parameter::getUserParameter('colorBaselineUpper') : '#BBDDDD';
        ?>
        <td>
          <div id="colorBaselineUpper" style="position:relative; height:29px;width:35px;float:left;top:0px;float:left;border:solid grey 0.5px;border-radius:5px;background-color:<?php echo $colorBaselineUpper; ?>">
          </div>
          <input id="colorBaselineUpperValue" type="hidden" value="<?php echo $colorBaselineUpper; ?>">
          <div dojoType="dijit.form.DropDownButton" showlabel="false" iconClass="colorSelector" style="position:relative; height:24px;width:50px;top:-3px;">
          <span><?php echo i18n('selectColor'); ?></span>
          <div dojoType="dijit.ColorPalette" id="colorPickerBaselineUpper" >
            <script type="dojo/method" event="onChange" >
              var fld=dojo.byId("colorBaselineUpper");
              var valueToSave = this.value.replace('#','');
              saveDataToSession('colorBaselineUpper',valueToSave,true);
              fld.style.backgroundColor=this.value;
              var inputValue=dojo.byId("colorBaselineUpperValue");
              inputValue.value=this.value;
              refreshJsonPlanning();
            </script>
          </div>
        </div>
        <button id="resetColorBaselineUpper" dojoType="dijit.form.Button" showlabel="true" style="display:none"
          title="<?php echo i18n('helpResetColor');?>" >
          <span><?php echo i18n('resetColor');?></span>
          <script type="dojo/connect" event="onClick" args="evt">
            var fld=dojo.byId("colorBaselineUpper");
            fld.style.backgroundColor="#BBDDDD";
            saveDataToSession('colorBaselineUpper','BBDDDD',true);
            var inputValue=dojo.byId("colorBaselineUpperValue");
            inputValue.value="#BBDDDD";
            refreshJsonPlanning();
          </script>
        </button>
      </td>
      </table>
    </tr>
    <tr>
      <td style="text-align:right;white-space:nowrap;padding-left:8px;">
      <table>
        <td>
        <?php 
        if (isNewGui()) echo pq_ucfirst(i18n('baselineBottom')) .'&nbsp;';
        else echo (($displayWidthPlan>1230)?i18n('baselineBottom'):i18n('baselineBottomShort')).'&nbsp;:&nbsp';?>
        <select dojoType="dijit.form.FilteringSelect" class="input roundedLeft" 
          style="width:<?php echo ($displayWidthPlan>930)?'300':'80';?>px;"
          data-dojo-props="queryExpr: '*${0}*', autoComplete:false"
          name="selectBaselineBottom" id="selectBaselineBottom"
          <?php echo autoOpenFilteringSelect();?> >
          <script type="dojo/method" event="onChange" >
            saveDataToSession("planningBaselineBottom",this.value);
            refreshJsonPlanning();
          </script>
          <?php htmlDrawOptionForReference('idBaselineSelect', getSessionValue("planningBaselineBottom"), null,false,null,null);?>
        </select>
        </td>
        <td>
        <?php 
        $colorBaselineBottom = Parameter::getUserParameter('colorBaselineBottom') !== '' ? '#'.Parameter::getUserParameter('colorBaselineBottom') : '#BBBBFF';
        ?>
        <div id="colorBaselinebottom" style="position:relative; height:29px;width:35px;float:left;top:0px;border:solid grey 0.5px;border-radius:5px;background-color:<?php echo $colorBaselineBottom; ?>">
        </div>
        <input id="colorBaselineBottomValue" type="hidden" value="<?php echo $colorBaselineBottom; ?>">
        <div dojoType="dijit.form.DropDownButton"  showlabel="false" iconClass="colorSelector" style="position:relative; height:24px;width:50px;top:-3px">
          <div dojoType="dijit.ColorPalette" id="colorPickerBaselineBottom" >
            <script type="dojo/method" event="onChange" >
              var fld=dojo.byId("colorBaselinebottom");
              fld.style.backgroundColor=this.value;
              var valueToSave = this.value.replace('#','');
              saveDataToSession('colorBaselineBottom',valueToSave,true);
              var inputValue=dojo.byId("colorBaselineBottomValue");
              inputValue.value=this.value;
              refreshJsonPlanning();
            </script>
          </div>
          </div>
        <button id="resetColorBaselinebottom" dojoType="dijit.form.Button" showlabel="true" style="display:none"
          title="<?php echo i18n('helpResetColor');?>" >
          <span><?php echo i18n('resetColor');?></span>
          <script type="dojo/connect" event="onClick" args="evt">
            var fld=dojo.byId("colorBaselinebottom");
            fld.style.backgroundColor="#BBBBFF";
            saveDataToSession('colorBaselineBottom','BBBBFF',true);
            var inputValue=dojo.byId("colorBaselineBottomValue");
            inputValue.value="#BBBBFF";
            refreshJsonPlanning();
          </script>
        </button>
      </td>
      </table>
    </tr>
  </table>
<?php 
}


function drawOptionBaseline() {
  global $displayWidthPlan,$proj;?>
  <table>
    <tr>
      <td style="font-weight:bold;text-align:center;"><?php echo pq_ucfirst(i18n('displayBaseline'));?></td>
    </tr>
    <tr>
      <td style="text-align:right;white-space:nowrap;">
      <table>
        <td>
        <?php 
        if (isNewGui()) echo pq_ucfirst(i18n('baselineTop')) .'&nbsp;';
        else echo (($displayWidthPlan>1230)?i18n('baselineTop'):i18n('baselineTopShort')).'&nbsp;:&nbsp;';?>
        <select dojoType="dijit.form.FilteringSelect" class="input roundedLeft" 
          style="width:<?php echo ($displayWidthPlan>930)?'150':'80';?>px;"
          name="selectBaselineTop" id="selectBaselineTop"
          <?php echo autoOpenFilteringSelect();?> >
          <script type="dojo/method" event="onChange" >
            saveDataToSession("planningBaselineTop",this.value,false);
            refreshJsonPlanning();
          </script>
          <?php htmlDrawOptionForReference('idBaselineSelect', getSessionValue("planningBaselineTop"), null,false,null,null);?>
        </select>
        </td>
        
        <?php 
        $colorBaselineUpper = Parameter::getUserParameter('colorBaselineUpper') !== '' ? '#' . Parameter::getUserParameter('colorBaselineUpper') : '#BBDDDD';
        ?>
        <td>
          <div id="colorBaselineUpper" style="position:relative; height:29px;width:40px;float:left;top:2px;float:left;border:solid grey 0.5px;border-radius:5px;background-color:<?php echo $colorBaselineUpper; ?>">
          </div>
          <input id="colorBaselineUpperValue" type="hidden" value="<?php echo $colorBaselineUpper; ?>">
          <div dojoType="dijit.form.DropDownButton" showlabel="false" iconClass="colorSelector" style="position:relative; height:24px;width:40px;top:-3px;">
          <span><?php echo i18n('selectColor'); ?></span>
          <div dojoType="dijit.ColorPalette" id="colorPickerBaselineUpper" >
            <script type="dojo/method" event="onChange" >
              var fld=dojo.byId("colorBaselineUpper");
              var valueToSave = this.value.replace('#','');
              saveDataToSession('colorBaselineUpper',valueToSave,true);
              fld.style.backgroundColor=this.value;
              var inputValue=dojo.byId("colorBaselineUpperValue");
              inputValue.value=this.value;
              refreshJsonPlanning();
            </script>
          </div>
        </div>
        <button id="resetColorBaselineUpper" dojoType="dijit.form.Button" showlabel="true"
          title="<?php echo i18n('helpResetColor');?>" >
          <span><?php echo i18n('resetColor');?></span>
          <script type="dojo/connect" event="onClick" args="evt">
            var fld=dojo.byId("colorBaselineUpper");
            fld.style.backgroundColor="#BBDDDD";
            saveDataToSession('colorBaselineUpper','BBDDDD',true);
            var inputValue=dojo.byId("colorBaselineUpperValue");
            inputValue.value="#BBDDDD";
            refreshJsonPlanning();
          </script>
        </button>
      </td>
      </table>
    </tr>
    <tr>
      <td style="text-align:right;white-space:nowrap;">
      <table>
        <td>
        <?php 
        if (isNewGui()) echo pq_ucfirst(i18n('baselineBottom')) .'&nbsp;';
        else echo (($displayWidthPlan>1230)?i18n('baselineBottom'):i18n('baselineBottomShort')).'&nbsp;:&nbsp';?>
        <select dojoType="dijit.form.FilteringSelect" class="input roundedLeft" 
          style="width:<?php echo ($displayWidthPlan>930)?'150':'80';?>px;"
          name="selectBaselineBottom" id="selectBaselineBottom"
          <?php echo autoOpenFilteringSelect();?> >
          <script type="dojo/method" event="onChange" >
            saveDataToSession("planningBaselineBottom",this.value);
            refreshJsonPlanning();
          </script>
          <?php htmlDrawOptionForReference('idBaselineSelect', getSessionValue("planningBaselineBottom"), null,false,($proj)?'idProject':null,($proj)?$proj:null);?>
        </select>
        </td>
        <td>
        <?php 
        $colorBaselineBottom = Parameter::getUserParameter('colorBaselineBottom') !== '' ? '#'.Parameter::getUserParameter('colorBaselineBottom') : '#BBBBFF';
        ?>
        <div id="colorBaselinebottom" style="position:relative; height:29px;width:40px;float:left;top:2px;border:solid grey 0.5px;border-radius:5px;background-color:<?php echo $colorBaselineBottom; ?>">
        </div>
        <input id="colorBaselineBottomValue" type="hidden" value="<?php echo $colorBaselineBottom; ?>">
        <div dojoType="dijit.form.DropDownButton"  showlabel="false" iconClass="colorSelector" style="position:relative; height:24px;width:40px;top:-3px">
          <div dojoType="dijit.ColorPalette" id="colorPickerBaselineBottom" >
            <script type="dojo/method" event="onChange" >
              var fld=dojo.byId("colorBaselinebottom");
              fld.style.backgroundColor=this.value;
              var valueToSave = this.value.replace('#','');
              saveDataToSession('colorBaselineBottom',valueToSave,true);
              var inputValue=dojo.byId("colorBaselineBottomValue");
              inputValue.value=this.value;
              refreshJsonPlanning();
            </script>
          </div>
          </div>
        <button id="resetColorBaselinebottom" dojoType="dijit.form.Button" showlabel="true"
          title="<?php echo i18n('helpResetColor');?>" >
          <span><?php echo i18n('resetColor');?></span>
          <script type="dojo/connect" event="onClick" args="evt">
            var fld=dojo.byId("colorBaselinebottom");
            fld.style.backgroundColor="#BBBBFF";
            saveDataToSession('colorBaselineBottom','BBBBFF',true);
            var inputValue=dojo.byId("colorBaselineBottomValue");
            inputValue.value="#BBBBFF";
            refreshJsonPlanning();
          </script>
        </button>
      </td>
      </table>
    </tr>
  </table>
<?php 
}

// ================================================== CHECKBOXES FOR DISPLAY OPTIONS 
function drawOptionsDisplay() {
  global $saveShowWbs, $saveShowClosed, $saveShowResource,$planningType, $showListFilter,$showClosedPlanningVersion,$showColorActivity,$showColorTypeActivity,$showHatchOnPlanningBar;?>
  <table width="100%">
    <?php if ($planningType!='contract' and $planningType!='version') {?>
    <tr class="checkboxLabel">
      <td><?php echo pq_ucfirst(i18n("labelShowWbs".((isNewGui())?'':'Short')));?></td>
      <td width="35px">
        <div title="<?php echo pq_ucfirst(i18n('showWbs'));?>" dojoType="dijit.form.CheckBox" 
          class="whiteCheck" type="checkbox" id="showWBS" name="showWBS"
          <?php if ($saveShowWbs=='1') { echo ' checked="checked" '; }?> >
          <script type="dojo/method" event="onChange" >
            saveUserParameter('planningShowWbs',((this.checked)?'1':'0'));
            refreshJsonPlanning();
          </script>
        </div>&nbsp;
      </td>
    </tr>
    <?php }?>
    <tr class="checkboxLabel" <?php echo ($planningType=='version')?'style="height:25px"':''?>>
      <td><?php echo pq_ucfirst(i18n("labelShowIdle".((isNewGui() or $planningType=='version')?'':'Short')));?></td>
      <td style="width: 30px;">
        <?php if ($planningType=='version') {?>
        <div title="<?php echo i18n('labelShowIdle')?>" dojoType="dijit.form.CheckBox" 
         class="whiteCheck" type="checkbox" id="showClosedPlanningVersion" name="showClosedPlanningVersion"
         <?php if ($showClosedPlanningVersion=='1') { echo ' checked="checked" '; }?> >
          <script type="dojo/method" event="onChange" >
            saveUserParameter('planningVersionShowClosed',((this.checked)?'1':'0'));
            refreshJsonPlanning();
          </script>
        </div>&nbsp;
        <?php } else {?>
        <div title="<?php echo pq_ucfirst(i18n('showIdleElements'));?>" dojoType="dijit.form.CheckBox" 
          class="whiteCheck" type="checkbox" id="listShowIdle" name="listShowIdle"
          <?php if ($saveShowClosed=='1') { echo ' checked="checked" '; }?> >
          <script type="dojo/method" event="onChange" >
            saveUserParameter('planningShowClosed',((this.checked)?'1':'0'));
            refreshJsonPlanning();
          </script>
        </div>&nbsp;
        <?php }?>
      </td>
    </tr>
    <?php 
    if (pq_strtoupper(Parameter::getUserParameter('displayResourcePlan'))!='NO' and ($planningType=='planning' or  $planningType=='global' or $planningType=='contract' or $planningType=='version') ) {?>
      <tr class="checkboxLabel" <?php echo ($planningType=='version')?'style="height:25px"':''?>>
        <td>
          <?php if ($planningType=='version') {?><div id="displayRessource" style="visibility:<?php echo ($showListFilter=='true')?'visible':'hidden';?>;"><?php }?>
          <?php echo pq_ucfirst(i18n("labelShowResource".((isNewGui() or $planningType=='version')?'':'Short')));?>
          <?php if ($planningType=='version') {?></div><?php }?>
        </td>
        <td style="width: 30px;">
          <?php if ($planningType=='version') {?><div id="displayRessourceCheck" style="visibility:<?php echo ($showListFilter=='true')?'visible':'hidden';?>!important;"><?php }?>
          <div title="<?php echo pq_ucfirst(i18n('showResources'));?>" dojoType="dijit.form.CheckBox" 
            class="whiteCheck" type="checkbox" 
            <?php if ($planningType=='version') {?>id="showRessourceComponentVersion" name="showRessourceComponentVersion"<?php } else { ?>id="listShowResource" name="listShowResource"<?php }?> 
            <?php if ($saveShowResource=='1') { echo ' checked="checked" '; }?> >
            <script type="dojo/method" event="onChange" >
              saveUserParameter('planningShowResource',((this.checked)?'1':'0'));
              refreshJsonPlanning();
            </script>
          </div>&nbsp;
          <?php if ($planningType=='version') {?></div><?php }?>
        </td>
      </tr>
    <?php 
    }?>
    <tr class="checkboxLabel">
      <td><?php echo i18n('showColorActivity'); ?></td>
      <td style="width: 30px;">
        <div id="displayRessourceCheck">
          <div title="<?php echo i18n('showColorActivity'); ?>" dojoType="dijit.form.CheckBox" class="whiteCheck" type="checkbox" id="showColorActivity" name="showColorActivity" 
          <?php if ($showColorActivity=='1') { echo ' checked="checked" '; }?> >
            <script type="dojo/method" event="onChange" >
              saveUserParameter('showColorActivity',((this.checked)?'1':'0'));
              refreshJsonPlanning();
            </script>
          </div>&nbsp;
        </div>
      </td>
    </tr><tr class="checkboxLabel">
      <td><?php echo i18n('showColorTypeActivity'); ?></td>
      <td style="width: 30px;">
        <div id="displayRessourceCheck">
          <div title="<?php echo i18n('showColorTypeActivity'); ?>" dojoType="dijit.form.CheckBox" class="whiteCheck" type="checkbox" id="showColorTypeActivity" name="showColorTypeActivity" 
          <?php if ($showColorTypeActivity=='YES') { echo ' checked="checked" '; }?> >
            <script type="dojo/method" event="onChange" >
              saveUserParameter('showColorTypeActivity',((this.checked)?'YES':'NO'));
              refreshJsonPlanning();
            </script>
          </div>&nbsp;
        </div>
      </td>
    </tr>
  </table>
<?php 
}


function drawOptionsDisplaySwitch($planning) {
  global $showActivityHierarchy,$saveShowProject,$showProjectLevel,$saveShowProjectColor,$saveShowLateColor,$saveShowLateColorPriority,$showPoolForResource,$showResourceWithoutWork,$showWorkDecimals,$displayComponentVersionActivity,$displayProductVersionActivity,$showOneTimeActivities,$showOnlyActivesVersions,$saveShowWbs,$saveShowWork ,$saveShowClosed, $saveShowResource,$planningType, $showListFilter,$showClosedPlanningVersion,$showColorActivity, $showColorTypeActivity,$showTaskNamePlanning,$showHatchOnPlanningBar;?>
  <table style="margin-left:20px;margin-top:5px;margin-bottom:5px;" width="100%">
  
   <?php if($planning=='version'){?>
    
<?php // === show only current versions ================================================================================================================================= ?>    
    <tr title="<?php echo pq_ucfirst(i18n('showOnlyActivesVersions'));?>">
      <td style="padding-top:6px;">
        <div id="hideVersionsWithoutActivityCheck" name="hideVersionsWithoutActivityCheck" class="colorSwitch" data-dojo-type="dojox/mobile/Switch"
                <?php if ($showOnlyActivesVersions=='1') {echo 'value="on"'; }else{echo 'value="off"';} ?>   
                 leftLabel="" rightLabel="" style="width:25px;" >
            <script type="dojo/method" event="onStateChanged" >
              saveUserParameter('showOnlyActivesVersions',((this.value=='on')?'1':'0'));
              refreshJsonPlanning();
  		    </script>
  	    </div>&nbsp;
      </td>
      <td class="checkboxLabel"><span onclick="invertSwitchValue('hideVersionsWithoutActivityCheck');"><?php echo pq_ucfirst(i18n("showOnlyActivesVersions"));?></span></td>
    </tr>
    
<?php // === show activities from product version ======================================================================================================================= ?>
    <tr title="<?php echo pq_ucfirst(i18n('displayProductVersionActivity'));?>">
      <td style="padding-top:6px;">
        <div id="listDisplayProductVersionActivity" name="listDisplayProductVersionActivity" class="colorSwitch" data-dojo-type="dojox/mobile/Switch"
                <?php if ($displayProductVersionActivity=='1') {echo 'value="on"'; }else{echo 'value="off"';} ?>   
                 leftLabel="" rightLabel="" style="width:25px;" >
            <script type="dojo/method" event="onStateChanged" >
              saveUserParameter('planningVersionDisplayProductVersionActivity',((this.value=='on')?'1':'0'));
              showListFilter('planningVersionDisplayProductVersionActivity',((this.value=='on')?'1':'0'));
              refreshJsonPlanning();
  		    </script>
  	    </div>&nbsp;
      </td>
      <td class="checkboxLabel"><span onclick="invertSwitchValue('listDisplayProductVersionActivity');"><?php echo pq_ucfirst(i18n("displayProductVersionActivity"));?></span></td>
    </tr>

<?php // === show activities from component version ===================================================================================================================== ?>
    <tr  title="<?php echo pq_ucfirst(i18n('displayComponentVersionActivity'));?>">
      <td style="padding-top:6px;">
        <div id="listDisplayComponentVersionActivity" name="listDisplayComponentVersionActivity" class="colorSwitch" data-dojo-type="dojox/mobile/Switch"
                <?php if ($displayComponentVersionActivity=='1') {echo 'value="on"'; }else{echo 'value="off"';} ?>   
                 leftLabel="" rightLabel="" style="width:25px;" >
            <script type="dojo/method" event="onStateChanged" >
              saveUserParameter('planningVersionDisplayComponentVersionActivity',((this.value=='on')?'1':'0'));
              showListFilter('planningVersionDisplayComponentVersionActivity',((this.value=='on')?'1':'0'));
              refreshJsonPlanning();
  		    </script>
  	    </div>&nbsp;
      </td>
      <td class="checkboxLabel"><span onclick="invertSwitchValue('listDisplayComponentVersionActivity');"><?php echo pq_ucfirst(i18n("displayComponentVersionActivity"));?></span></td>
    </tr>     
    <?php }?>
  
  
   <?php if($planning != 'version' and $planning != 'contract' and $planning != 'workPlan'){ ?>
<?php // === show WBS =================================================================================================================================================== ?>
    <tr title="<?php echo pq_ucfirst(i18n('wbsSwitch'));?>">
      <td style="padding-top:6px;">
         <div   id="showWBS" class="colorSwitch" data-dojo-type="dojox/mobile/Switch"
                <?php if ($saveShowWbs=='1') {echo 'value="on"'; }else{echo 'value="off"';} ?>   
                 leftLabel="" rightLabel="" style="width:25px;" >
            <script type="dojo/method" event="onStateChanged" >
              saveUserParameter('planningShowWbs',((this.value=='on')?'1':'0'));
              refreshJsonPlanning();
  		      </script>
  		    </div>&nbsp;
      </td>
      <td style="padding-right:10px;" class="checkboxLabel"><span onclick="invertSwitchValue('showWBS');"><?php echo i18n('labelShowWbsShort');?></span></td>
    </tr>
    <?php } ?>

<?php // === Color on left part ===================================================================================================================== ?>
<?php if($planning != 'workPlan'){?>
     <tr  <?php if($planning=='version' or $planning=='contract'){?>style="display:none;" <?php }?> title="<?php echo pq_ucfirst(i18n('showColorActivitySwitch'));?>" >
            <td style="padding-top:6px;">
              <div  id="showColorActivity" class="colorSwitch" data-dojo-type="dojox/mobile/Switch"
                  <?php if ($showColorActivity=='1') {echo 'value="on"'; }else{echo 'value="off"';} ?>   
                   leftLabel="" rightLabel="" style="width:25px;" >
               <script type="dojo/method" event="onStateChanged" >
                saveUserParameter('showColorActivity',((this.value=='on')?'1':'0'));
                refreshJsonPlanning();
  		       </script>
    		  </div>&nbsp;
            </td>
        <td class="checkboxLabel"><span onclick="invertSwitchValue('showColorActivity');"><?php echo i18n("showColorActivity");?></span></td>
     </tr>
      <tr  <?php if($planning=='version' or $planning=='contract' or $planning=='portfolio'){?>style="display:none;" <?php }?> title="<?php echo pq_ucfirst(i18n('showColorTypeActivitySwitch'));?>" >
            <td style="padding-top:6px;">
              <div  id="showColorTypeActivity" class="colorSwitch" data-dojo-type="dojox/mobile/Switch"
                  <?php if ($showColorTypeActivity=='YES') {echo 'value="on"'; }else{echo 'value="off"';} ?>   
                   leftLabel="" rightLabel="" style="width:25px;" >
               <script type="dojo/method" event="onStateChanged" >
                saveUserParameter('showColorTypeActivity',((this.value=='on')?'YES':'NO'));
                refreshJsonPlanning();
  		       </script>
    		  </div>&nbsp;
            </td>
        <td class="checkboxLabel"><span onclick="invertSwitchValue('showColorTypeActivity');"><?php echo i18n("showColorTypeActivity");?></span></td>
     </tr>
     
     
     <!-- showHatchOnPlanningBar -->
     <tr <?php if($planning=='version' or $planning=='contract' or $planning=='portfolio'){?>style="display:none;" <?php }?>
       title="<?php echo pq_ucfirst(i18n('showHatchOnPlanningBarSwitch'));?>">
       <td style="padding-top:6px;">
         <div id="showHatchOnPlanningBarSwitch"
           class="colorSwitch"
           data-dojo-type="dojox/mobile/Switch"
           <?php if ($showHatchOnPlanningBar=='1') { echo 'value="on"'; } else { echo 'value="off"'; } ?>
           leftLabel="" rightLabel="" style="width:25px;">
        	<script type="dojo/method" event="onStateChanged">
            showHatchOnPlanningBar = (this.value=='on')?1:0;
            saveUserParameter('showHatchOnPlanningBar',((this.value=='on')?'1':'0'));
            refreshJsonPlanning();
          </script>
      	</div>&nbsp;
      </td>
      <td class="checkboxLabel">
        <span onclick="invertSwitchValue('showHatchOnPlanningBarSwitch');"><?php echo i18n("showHatchOnPlanningBar");?></span>
      </td>
		</tr>
     
    <?php if($planning == 'resources' and $planning != 'contract'){ ?>
        <tr title="<?php echo pq_ucfirst(i18n('labelShowLeftWork'));?>">
           <td style="padding-top:6px;">
          <div  id="listShowLeftWork" class="colorSwitch" data-dojo-type="dojox/mobile/Switch"
             <?php if ($saveShowWork=='1') {echo 'value="on"'; }else{echo 'value="off"';} ?>   
             leftLabel="" rightLabel="" style="width:25px;" >
          <script type="dojo/method" event="onStateChanged" >
        saveUserParameter('planningShowWork',((this.value=='on')?'1':'0'));
        refreshJsonPlanning();
      </script>
        </div>&nbsp;
       </td>
     <td class="checkboxLabel"><span onclick="invertSwitchValue('listShowLeftWork');"><?php echo i18n("labelShowLeftWork");?></span></td>
     </tr>
    <?php } ?>
    
   <?php if($planning != 'portfolio' and $planning != 'version' ){?>
     <?php if (pq_strtoupper(Parameter::getUserParameter('displayResourcePlan'))!='NO' and ($planningType=='planning' or  $planningType=='global' or $planningType=='contract' or $planningType=='version') ) {?>
        <tr title="<?php echo pq_ucfirst(i18n('displayRessourceCheckSwitch'));?>">
          <td style="padding-top:6px;">
            <div id="displayRessourceCheck" class="colorSwitch" data-dojo-type="dojox/mobile/Switch"
                  <?php if ($saveShowResource=='1') {echo 'value="on"'; }else{echo 'value="off"';} ?>   
                   leftLabel="" rightLabel="" style="width:25px;" >
              <script type="dojo/method" event="onStateChanged" >
              saveUserParameter('planningShowResource',((this.value=='on')?'1':'0'));
              planningShowResource = (this.value=='on')?'1':'0';
              refreshJsonPlanning();
  		      </script>
    		    </div>&nbsp;
          </td>
          <td class="checkboxLabel"><span onclick="invertSwitchValue('displayRessourceCheck');"><?php echo i18n("resources");?></span></td>
        </tr>
      <?php }?>
    <?php } ?>
       <?php if($planning != 'version' and $planning != 'contract'){?>
      <tr title="<?php echo pq_ucfirst(i18n('showTaskNameOnPlanningBarSwitch'));?>">
        <td style="padding-top:6px;">
        
          <?php if($planning == 'resources'){?> 
           <div id="showTaskNameOnPlanningBarResources" name="showTaskNameOnPlanningBarResources" class="colorSwitch" data-dojo-type="dojox/mobile/Switch"
          <?php }else{ ?> 
           <div id="showTaskNameOnPlanningBar" name="showTaskNameOnPlanningBar" class="colorSwitch" data-dojo-type="dojox/mobile/Switch"
          <?php } ?>
          
       <?php if ($showTaskNamePlanning=='1') {echo 'value="on"'; }else{echo 'value="off"';}    
              ?>   
              leftLabel="" rightLabel="" style="width:25px;" >
              
              <?php if($planning == 'resources'){?> 
               <script type="dojo/method" event="onStateChanged" >
                  saveUserParameter('showTaskNameOnPlanningBarResources',((this.value=='on')?'1':'0'));
                  showTaskNameOnPlanningBarResources = (this.value=='on')?'1':'0';
                  refreshJsonPlanning();
  		        </script>
              <?php }else{ ?>  
                <script type="dojo/method" event="onStateChanged" >
                  saveUserParameter('showTaskNameOnPlanningBar',((this.value=='on')?'1':'0'));
                  showTaskNameOnPlanningBar = (this.value=='on')?'1':'0';
                  refreshJsonPlanning();
  		        </script>
  		      <?php } ?>
  		      
    	    </div>&nbsp;
        </td>
        
        <?php if($planning == 'resources'){?> 
        <td class="checkboxLabel"><span onclick="invertSwitchValue('showTaskNameOnPlanningBarResources');"><?php echo pq_ucfirst(i18n("showTaskNameOnPlanningBar"));?></span></td>
        <?php }else{ ?> 
        <td class="checkboxLabel"><span onclick="invertSwitchValue('showTaskNameOnPlanningBar');"><?php echo pq_ucfirst(i18n("showTaskNameOnPlanningBar"));?></span></td>
        <?php } ?>
        
      </tr>
      <?php } ?>

    
    <?php if(Parameter::getGlobalParameter('paramWithCriticalPath')!="NO"){?>
       <?php if($planning != 'portfolio' and $planning !='resources' and $planning != 'version' and $planning != 'contract'){?>
    <tr title="<?php echo pq_ucfirst(i18n('criticalPathPlanningSwitch'));?>">
      <td style="padding-top:6px;">
          <div   id="criticalPathPlanning" class="colorSwitch" data-dojo-type="dojox/mobile/Switch"
                 <?php if ( Parameter::getUserParameter('criticalPathPlanning')=='1') {echo 'value="on"'; }else{echo 'value="off"';} ?>
                 leftLabel="" rightLabel="" style="width:25px;" >
            <script type="dojo/method" event="onStateChanged" >
              saveUserParameter('criticalPathPlanning',((this.value=='on')?'1':'0'));
              if (! (dijit.byId("dialogPlan") && dijit.byId("dialogPlan").open) ) refreshJsonPlanning();
  		    </script>
  		    </div>&nbsp;
      </td>
      <td class="checkboxLabel"><span onclick="invertSwitchValue('criticalPathPlanning');"><?php echo i18n("criticalPathSimple");?></span></td>
    </tr>
    <?php }} ?>
    
    <?php if($planning == 'planning'){?>
     <tr title="<?php echo pq_ucfirst(i18n('planningDisplayUnitProgress'));?>">
      <td style="padding-top:6px;">
        <div   id="displayUnitProgress" name="displayUnitProgress" class="colorSwitch" data-dojo-type="dojox/mobile/Switch"
                <?php if (Parameter::getUserParameter('displayUnitProgress')=='1') {echo 'value="on"'; }else{echo 'value="off"';} ?>   
                 leftLabel="" rightLabel="" style="width:25px;" >
            <script type="dojo/method" event="onStateChanged" >
              saveUserParameter('displayUnitProgress',((this.value=='on')?'1':'0'));
              displayUnitProgress = (this.value=='on')?'1':'0';
              refreshJsonPlanning();
  		      </script>
  		    </div>&nbsp;
      </td>
      <td class="checkboxLabel"><span onclick="invertSwitchValue('displayUnitProgress');"><?php echo pq_ucfirst(i18n("colUnitProgress"));?></span></td>
    </tr>
    <?php } ?>
    <?php }?>
    <?php if($planning == 'resources' or $planning == 'workPlan'){?>
     <tr title="<?php echo pq_ucfirst(i18n('showProjectLevel'));?>">
      <td style="padding-top:6px;">
        <div   id="listShowProject" class="colorSwitch" data-dojo-type="dojox/mobile/Switch"
                <?php if ($saveShowProject==1) {echo 'value="on"'; }else{echo 'value="off"';} ?>   
                 leftLabel="" rightLabel="" style="width:25px;" >
            <script type="dojo/method" event="onStateChanged" >
              saveUserParameter('planningShowProject',((this.value=='on')?'1':'0'));
              <?php if($planning == 'workPlan'){?>
              wpShowProject = (this.value=='on')?'1':'0';
              refreshJsonWorkPlan();
              <?php }else{ ?>
              refreshJsonPlanning();
              <?php } ?>
  		      </script>
  		    </div>&nbsp;
      </td>
      <td class="checkboxLabel"><span onclick="invertSwitchValue('listShowProject');"><?php echo i18n("labelShowProjectLevel");?></span></td>
    </tr> 
    <?php } ?>
    <?php if($planning == 'workPlan'){?>
    <tr title="<?php echo pq_ucfirst(i18n('labelShowProjectColor'));?>">
      <td style="padding-top:6px;">
        <div   id="listShowProjectColor" class="colorSwitch" data-dojo-type="dojox/mobile/Switch"
                <?php if ($saveShowProjectColor==1) {echo 'value="on"'; }else{echo 'value="off"';} ?>   
                 leftLabel="" rightLabel="" style="width:25px;" >
            <script type="dojo/method" event="onStateChanged" >
              if(this.value=='on'){
                dijit.byId('listShowLateColor').set('value', 'off');
                dijit.byId('listShowLateColorPriority').set('value', 'off');
              }
              wpShowProjectColor = (this.value=='on')?'1':'0';
              saveUserParameter('planningShowProjectColor',((this.value=='on')?'1':'0'));
              refreshJsonWorkPlan();
  		      </script>
  		    </div>&nbsp;
      </td>
      <td class="checkboxLabel"><span onclick="invertSwitchValue('listShowProjectColor');"><?php echo i18n("labelShowProjectColor");?></span></td>
    </tr>
    <tr title="<?php echo pq_ucfirst(i18n('labelShowLateColor'));?>">
      <td style="padding-top:6px;">
        <div   id="listShowLateColor" class="colorSwitch" data-dojo-type="dojox/mobile/Switch"
                <?php if ($saveShowLateColor==1) {echo 'value="on"'; }else{echo 'value="off"';} ?>   
                 leftLabel="" rightLabel="" style="width:25px;" >
            <script type="dojo/method" event="onStateChanged" >
              if(this.value=='on'){
                dijit.byId('listShowProjectColor').set('value', 'off');
              }
              wpShowLateColor = (this.value=='on')?'1':'0';
              saveUserParameter('planningShowLateColor',((this.value=='on')?'1':'0'));
              refreshJsonWorkPlan();
  		      </script>
  		    </div>&nbsp;
      </td>
      <td class="checkboxLabel"><span onclick="invertSwitchValue('listShowLateColor');"><?php echo i18n("labelShowLateColor");?></span></td>
    </tr>
    <tr title="<?php echo pq_ucfirst(i18n('labelShowLateColorPriority'));?>">
      <td style="padding-top:6px;">
        <div   id="listShowLateColorPriority" class="colorSwitch" data-dojo-type="dojox/mobile/Switch"
                <?php if ($saveShowLateColorPriority==1) {echo 'value="on"'; }else{echo 'value="off"';} ?>   
                 leftLabel="" rightLabel="" style="width:25px;" >
            <script type="dojo/method" event="onStateChanged" >
              wpShowLateColorPriority = (this.value=='on')?'1':'0';
              saveUserParameter('planningShowLateColorPriority',((this.value=='on')?'1':'0'));
              if(this.value=='on'){
                dijit.byId('listShowProjectColor').set('value', 'off');
                dijit.byId('listShowLateColor').set('value', 'on');
              }
              refreshJsonWorkPlan();
  		      </script>
  		    </div>&nbsp;
      </td>
      <td class="checkboxLabel"><span onclick="invertSwitchValue('listShowLateColorPriority');"><?php echo i18n("labelShowLateColorPriority");?></span></td>
    </tr> 
     <tr title="<?php echo pq_ucfirst(i18n('labelShowPoolForResource'));?>">
      <td style="padding-top:6px;">
        <div   id="listShowPoolForResource" class="colorSwitch" data-dojo-type="dojox/mobile/Switch"
                <?php if ($showPoolForResource==1) {echo 'value="on"'; }else{echo 'value="off"';} ?>   
                 leftLabel="" rightLabel="" style="width:25px;" >
            <script type="dojo/method" event="onStateChanged" >
              wpShowPoolForResource = (this.value=='on')?'1':'0';
              saveUserParameter('workPlanShowPoolForResource',((this.value=='on')?'1':'0'));
              refreshJsonWorkPlan();
  		      </script>
  		    </div>&nbsp;
      </td>
      <td class="checkboxLabel"><span onclick="invertSwitchValue('listShowPoolForResource');"><?php echo i18n("labelShowPoolForResource");?></span></td>
    </tr>
    <tr title="<?php echo pq_ucfirst(i18n('labelShowResourceWithoutWork'));?>">
      <td style="padding-top:6px;">
        <div   id="listShowResourceWithoutWork" class="colorSwitch" data-dojo-type="dojox/mobile/Switch"
                <?php if ($showResourceWithoutWork==1) {echo 'value="on"'; }else{echo 'value="off"';} ?>   
                 leftLabel="" rightLabel="" style="width:25px;" >
            <script type="dojo/method" event="onStateChanged" >
              wpShowResourceWithoutWork = (this.value=='on')?'1':'0';
              saveUserParameter('workPlanShowResourceWithoutWork',((this.value=='on')?'1':'0'));
              refreshJsonWorkPlan();
  		      </script>
  		    </div>&nbsp;
      </td>
      <td class="checkboxLabel"><span onclick="invertSwitchValue('listShowResourceWithoutWork');"><?php echo i18n("labelShowResourceWithoutWork");?></span></td>
    </tr>
    <tr title="<?php echo pq_ucfirst(i18n('labelShowWorkDecimals'));?>">
      <td style="padding-top:6px;">
        <div   id="listShowWorkDecimals" class="colorSwitch" data-dojo-type="dojox/mobile/Switch"
                <?php if ($showWorkDecimals==1) {echo 'value="on"'; }else{echo 'value="off"';} ?>   
                 leftLabel="" rightLabel="" style="width:25px;" >
            <script type="dojo/method" event="onStateChanged" >
              wpShowWorkDecimals = (this.value=='on')?'1':'0';
              saveUserParameter('workPlanShowWorkDecimals',((this.value=='on')?'1':'0'));
              refreshJsonWorkPlan();
  		      </script>
  		    </div>&nbsp;
      </td>
      <td class="checkboxLabel"><span onclick="invertSwitchValue('listShowWorkDecimals');"><?php echo i18n("labelShowWorkDecimals");?></span></td>
    </tr>
    <?php } ?>
    <?php if($planning != 'version' and $planning != 'contract' and $planning != 'workPlan'){?>
     <tr title="<?php echo pq_ucfirst(i18n('showProjectModelSwitch'));?>">
      <td style="padding-top:6px;">
        <div   id="showProjectModel" class="colorSwitch" data-dojo-type="dojox/mobile/Switch"
                <?php if (Parameter::getUserParameter('showProjectModel')!='1') {echo 'value="off"'; }else{echo 'value="on"';} ?>   
                 leftLabel="" rightLabel="" style="width:25px;" >
            <script type="dojo/method" event="onStateChanged" >
              saveUserParameter('showProjectModel',((this.value=='off')?'0':'1'));
              refreshJsonPlanning();
  		      </script>
  		    </div>&nbsp;
      </td>
      <td class="checkboxLabel"><span onclick="invertSwitchValue('showProjectModel');"><?php echo i18n("projectModel");?></span></td>
    </tr>   
    <?php } ?>
    <?php if($planning != 'workPlan'){?>
       <tr title="<?php echo pq_ucfirst(i18n('listShowIdleSwitch'));?>">
      <td style="padding-top:6px;">
        <div   id="listShowIdleSwitch" class="colorSwitch" data-dojo-type="dojox/mobile/Switch"
                <?php if ($saveShowClosed=='1'){echo 'value="on"'; }else{echo 'value="off"';} ?>   
                 leftLabel="" rightLabel="" style="width:25px;" >
            <script type="dojo/method" event="onStateChanged" >
              saveUserParameter('planningShowClosed',((this.value=='on')?'1':'0'));
              refreshJsonPlanning();
  		      </script>
  		    </div>&nbsp;
      </td>
      <td class="checkboxLabel"><span onclick="invertSwitchValue('listShowIdleSwitch');"><?php echo i18n("IdleElements");?></span></td>
    </tr>
    <?php } ?>
     <?php if($planning != 'portfolio' and $planning != 'version' and $planning != 'contract' and $planning != 'workPlan'){?>
     <tr title="<?php echo pq_ucfirst(i18n('hideAssignationWihtoutLeftWorkSwitch'));?>">
      <td style="padding-top:6px;">
        <div    id="hideAssignationWihtoutLeftWork" class="colorSwitch" data-dojo-type="dojox/mobile/Switch"
                <?php if (Parameter::getUserParameter('hideAssignationWihtoutLeftWork')=='1') {echo 'value="off"'; }else{echo 'value="on"';} ?>   
                 leftLabel="" rightLabel="" style="width:25px;" >
            <script type="dojo/method" event="onStateChanged" >
              saveUserParameter('hideAssignationWihtoutLeftWork',((this.value=='off')?'1':'0'));
              refreshJsonPlanning();
  		      </script>
  		    </div>&nbsp;
      </td>
      <td class="checkboxLabel"><span onclick="invertSwitchValue('hideAssignationWihtoutLeftWork');"><?php echo i18n("AssignationWihtoutLeftWork");?></span></td>
    </tr>
    <?php } ?>
    
    <?php  if($planning != 'portfolio' and $planning != 'version' and $planning != 'contract' and $planning != 'workPlan'){?>
     <tr title="<?php echo pq_ucfirst(i18n('lockPlanningBarDetailSwitch'));?>" >
      <td style="padding-top:6px;">
        <div  id="lockPlanningBarDetail" class="colorSwitch" data-dojo-type="dojox/mobile/Switch"
                <?php if (Parameter::getUserParameter('lockPlanningBarDetail')=='1' or Parameter::getUserParameter('lockPlanningBarDetail')=='') {echo 'value="on"'; }else{echo 'value="off"';} ?>   
                 leftLabel="" rightLabel="" style="width:25px;" >
            <script type="dojo/method" event="onStateChanged" >
              lockPlanningBarDetail=(this.value=='on')?'1':'0';
              saveUserParameter('lockPlanningBarDetail',((this.value=='on')?'1':'0'));
              refreshJsonPlanning();
  		      </script>
  		    </div>&nbsp;
      </td>
      <td class="checkboxLabel"><span onclick="invertSwitchValue('lockPlanningBarDetail');"><?php echo i18n("lockBarDetail");?></span></td>
    </tr>
    <?php } ?>
     <?php if($planning != 'portfolio' and $planning != 'contract' and $planning != 'workPlan'){?>
     <tr title="<?php echo pq_ucfirst(i18n('planningClickActionSwitch'));?>">
      <td style="padding-top:6px;">
        <div   id="planningClickAction" name="planningClickAction" class="colorSwitch" data-dojo-type="dojox/mobile/Switch"
                <?php if (Parameter::getUserParameter('planningClickAction')=='1') {echo 'value="on"'; }else{echo 'value="off"';} ?>   
                 leftLabel="" rightLabel="" style="width:25px;" >
            <script type="dojo/method" event="onStateChanged" >
              saveUserParameter('planningClickAction',((this.value=='on')?'1':'0'));
              planningClickAction = (this.value=='on')?'1':'0';
  		      </script>
  		    </div>&nbsp;
      </td>
      <td class="checkboxLabel"><span onclick="invertSwitchValue('planningClickAction');"><?php echo pq_ucfirst(i18n("planningClickAction"));?></span></td>
    </tr>
    <?php } ?>
    <?php  if($planning != 'portfolio' and $planning != 'version' and $planning != 'contract' and $planning != 'workPlan'){?>
     <tr title="<?php echo pq_ucfirst(i18n('autoScrollPlanningBar'));?>" >
      <td style="padding-top:6px;">
        <div  id="autoScrollPlanningBar" class="colorSwitch" data-dojo-type="dojox/mobile/Switch"
                <?php if (Parameter::getUserParameter('autoScrollPlanningBar')=='1') {echo 'value="on"'; }else{echo 'value="off"';} ?>   
                 leftLabel="" rightLabel="" style="width:25px;" >
            <script type="dojo/method" event="onStateChanged" >
              autoScrollPlanningBar=(this.value=='on')?'1':'0';
              saveUserParameter('autoScrollPlanningBar',((this.value=='on')?'1':'0'));
              //refreshJsonPlanning();
  		      </script>
  		    </div>&nbsp;
      </td>
      <td class="checkboxLabel"><span onclick="invertSwitchValue('lockPlanningBarDetail');"><?php echo i18n("autoScrollPlanningBar");?></span></td>
    </tr>
        <?php } ?>
    <?php  if($planning == 'planning'){?>
     <tr title="<?php echo pq_ucfirst(i18n('showHiddenLevelCondensed'));?>" >
      <td style="padding-top:6px;">
        <div  id="showHiddenLevelCondensed" class="colorSwitch" data-dojo-type="dojox/mobile/Switch"
                <?php if (Parameter::getUserParameter('showHiddenLevelCondensed')=='1') {echo 'value="on"'; }else{echo 'value="off"';} ?>   
                 leftLabel="" rightLabel="" style="width:25px;" >
            <script type="dojo/method" event="onStateChanged" >
              showHiddenLevelCondensed=(this.value=='on')?'1':'0';
              saveUserParameter('showHiddenLevelCondensed',((this.value=='on')?'1':'0'));
              refreshJsonPlanning();
  		      </script>
  		    </div>&nbsp;
      </td>
      <td class="checkboxLabel"><span onclick="invertSwitchValue('showHiddenLevelCondensed');"><?php echo i18n("showHiddenLevelCondensed");?></span></td>
    </tr>
        <?php } ?>
  </table>
<?php 
}

function drawDisplayFieldVersion() {
  global $showActivityHierarchy,$showProjectLevel,$displayComponentVersionActivity,$displayProductVersionActivity,$showOneTimeActivities,$showOnlyActivesVersions,$saveShowWbs,$saveShowWork ,$saveShowClosed, $saveShowResource,$planningType, $showListFilter,$showClosedPlanningVersion,$showColorActivity,$showColorTypeActivity,$showHatchOnPlanningBar;?>
 
  <table style="margin-left:20px;margin-top:10px;" width="100%">
   <tr id="versionsWithoutActivityCheckTr" style="display:<?php  echo ($showListFilter=='true')?'table-row':'none';?>;" title="<?php echo pq_ucfirst(i18n('versionsWithoutActivity'));?>">
      <td style="padding-top:6px;">
        <div id="versionsWithoutActivityCheck" name="versionsWithoutActivityCheck" class="colorSwitch" data-dojo-type="dojox/mobile/Switch"
                <?php if (Parameter::getUserParameter('versionsWithoutActivity')=='1') {echo 'value="on"'; }else{echo 'value="off"';} ?>   
                 leftLabel="" rightLabel="" style="width:25px;" >
            <script type="dojo/method" event="onStateChanged" >
              saveUserParameter('versionsWithoutActivity',((this.value=='on')?'1':'0'));
              refreshJsonPlanning();
  		    </script>
  	    </div>&nbsp;
      </td>
      <td class="checkboxLabel"><span onclick="invertSwitchValue('versionsWithoutActivityCheck');"><?php echo pq_ucfirst(i18n("versionsWithoutActivity"));?></span></td>
    </tr>             
         <tr  id="showOneTimeActivitiesTr" style="display:<?php  echo ($showListFilter=='true')?'table-row':'none';?>;" title="<?php echo pq_ucfirst(i18n('versionPlanningShowOneTimeActivities'));?>">
      <td style="padding-top:6px;">
        <div id="showOneTimeActivities" name="showOneTimeActivities" class="colorSwitch" data-dojo-type="dojox/mobile/Switch"
                <?php if ($showOneTimeActivities) {echo 'value="on"'; }else{echo 'value="off"';} ?>   
                 leftLabel="" rightLabel="" style="width:25px;" >
            <script type="dojo/method" event="onStateChanged" >
              saveUserParameter('showOneTimeActivities',((this.value=='on')?'1':'0'));
              refreshJsonPlanning();
  		    </script>
  	    </div>&nbsp;
      </td>
      <td class="checkboxLabel"><span onclick="invertSwitchValue('showOneTimeActivities');"><?php echo pq_ucfirst(i18n("versionPlanningShowOneTimeActivities"));?></span></td>
    </tr>               
           
     <tr  id="showProjectLevelTr" style="display:<?php  echo ($showListFilter=='true')?'table-row':'none';?>;" title="<?php echo pq_ucfirst(i18n('labelShowProjectLevel'));?>">
      <td style="padding-top:6px;">
        <div id="showProjectLevel" name="showProjectLevel" class="colorSwitch" data-dojo-type="dojox/mobile/Switch"
                <?php if ($showProjectLevel) {echo 'value="on"'; }else{echo 'value="off"';} ?>   
                 leftLabel="" rightLabel="" style="width:25px;" >
            <script type="dojo/method" event="onStateChanged" >
              saveUserParameter('planningVersionShowProjectLevel',((this.value=='on')?'1':'0'));
              refreshJsonPlanning();
  		    </script>
  	    </div>&nbsp;
      </td>
      <td class="checkboxLabel"><span onclick="invertSwitchValue('showProjectLevel');"><?php echo pq_ucfirst(i18n("labelShowProjectLevel"));?></span></td>
    </tr>     
    
    
    <tr  id="showOnlyActivesVersionsTr" style="display:<?php  echo ($showListFilter=='true')?'table-row':'none';?>;" title="<?php echo pq_ucfirst(i18n('labelShowActivityHierarchy'));?>">
      <td style="padding-top:6px;">
        <div id="showOnlyActivesVersions" name="showOnlyActivesVersions" class="colorSwitch" data-dojo-type="dojox/mobile/Switch"
                <?php if ($showActivityHierarchy) {echo 'value="on"'; }else{echo 'value="off"';} ?>   
                 leftLabel="" rightLabel="" style="width:25px;" >
            <script type="dojo/method" event="onStateChanged" >
              saveUserParameter('planningVersionDisplayActivityHierarchy',((this.value=='on')?'1':'0'));
              refreshJsonPlanning();
  		    </script>
  	    </div>&nbsp;
      </td>
      <td class="checkboxLabel"><span onclick="invertSwitchValue('showOnlyActivesVersions');"><?php echo pq_ucfirst(i18n("labelShowActivityHierarchy"));?></span></td>
    </tr>   
     <tr id="showRessourceComponentVersionTr" style="display:<?php  echo ($showListFilter=='true')?'table-row':'none';?>;" title="<?php echo pq_ucfirst(i18n('displayRessourceCheckSwitch'));?>">
        <td style="padding-top:6px;">
          <div   id="showRessourceComponentVersion" name="showRessourceComponentVersion" class="colorSwitch" data-dojo-type="dojox/mobile/Switch"
                <?php if ($saveShowResource=='1') {echo 'value="on"'; }else{echo 'value="off"';} ?>   
                 leftLabel="" rightLabel="" style="width:25px;" >
            <script type="dojo/method" event="onStateChanged" >
              saveUserParameter('planningShowResource',((this.value=='on')?'1':'0'));
              planningShowResource = (this.value=='on')?'1':'0';
              refreshJsonPlanning();
  		      </script>
  		    </div>&nbsp;
        </td>
        <td class="checkboxLabel"><span onclick="invertSwitchValue('showRessourceComponentVersion');"><?php echo i18n("resources");?></span></td>
      </tr> 
       </table>        
    <?php 
    
}

// ================================================== CHECKBOX FOR CRITICAL PATH
function drawOptionCriticalPath() {
?>
  <div style="white-space:nowrap; <?php echo (isNewGui())?'margin-right:6px;margin-top:5px;':'position:absolute; bottom:5px;left:10px;'; ?>" class="checkboxLabel">
    <?php if (isNewGui()) {?><?php echo pq_ucfirst(i18n('criticalPath'));?>&nbsp;<?php }?>
    <span title="<?php echo pq_ucfirst(i18n('criticalPath'));?>" dojoType="dijit.form.CheckBox"
      type="checkbox" id="criticalPathPlanning" name="criticalPathPlanning" class="whiteCheck"
      <?php if ( Parameter::getUserParameter('criticalPathPlanning')=='1') {echo 'checked="checked"'; } ?>  >  
      <script type="dojo/connect" event="onChange" args="evt">
        saveUserParameter('criticalPathPlanning',((this.checked)?'1':'0'));
        refreshJsonPlanning();
      </script>                    
    </span>
    <?php if (!isNewGui()) {?>&nbsp;<?php echo i18n('criticalPath');?><?php }?>
  </div>
<?php 
}

function drawOptionProjectModel() {
  ?>
  <div style="white-space:nowrap; <?php echo (isNewGui())?'margin-right:6px;margin-top:5px;':'position:absolute; bottom:5px;left:10px;'; ?>" class="checkboxLabel">
    <?php if (isNewGui()) {?><?php echo pq_ucfirst(i18n('showProjectModel'));?>&nbsp;<?php }?>
    <span title="<?php echo pq_ucfirst(i18n('showProjectModel'));?>" dojoType="dijit.form.CheckBox"
      type="checkbox" id="showProjectModel" name="showProjectModel" class="whiteCheck"
      <?php if ( Parameter::getUserParameter('showProjectModel')=='1') {echo 'checked="checked"'; } ?>  >  
      <script type="dojo/connect" event="onChange" args="evt">
        saveUserParameter('showProjectModel',((this.checked)?'1':'0'));
        refreshJsonPlanning();
      </script>                    
    </span>
    <?php if (!isNewGui()) {?>&nbsp;<?php echo i18n('showProjectModel');?><?php }?>
  </div>
<?php 
}

// ================================================== FIELD MILESTONES
function drawMilestones() {
  global $saveShowMilestone;
  if ($saveShowMilestone==' ') $saveShowMilestone=null;
  ?>
  <?php echo i18n("showMilestoneShort");?>
  <select dojoType="dijit.form.FilteringSelect" class="input roundedLeft" 
    style="width: 150px;"
    <?php echo autoOpenFilteringSelect();?>
    name="listShowMilestone" id="listShowMilestone">
    <script type="dojo/method" event="onChange" >
      saveUserParameter('planningShowMilestone',this.value);
      refreshJsonPlanning();
    </script>
    <option value=" " <?php echo (! $saveShowMilestone)?'SELECTED':'';?>><?php echo i18n("paramNone");?></option>                            
      <?php htmlDrawOptionForReference('idMilestoneType', (($saveShowMilestone and $saveShowMilestone!='all')?$saveShowMilestone:null) ,null, true);?>
    <option value="all" <?php echo ($saveShowMilestone=='all')?'SELECTED':'';?>><?php echo i18n("all");?></option>                            
  </select>
<?php                         
}

// ================================================== CHECKBOX SHOW LEFT WORK
function drawOptionLeftWork() {
  global $saveShowWork;?>
  <table width="100%">
    <tr class="checkboxLabel">
      <td >
        <?php echo pq_ucfirst(i18n("labelShowLeftWork".((isNewGui()?'':'Short'))));?>
      </td>
      <td style="width:36px">
        <div title="<?php echo i18n('showLeftWork')?>" dojoType="dijit.form.CheckBox" 
          type="checkbox" id="listShowLeftWork" name="listShowLeftWork" class="whiteCheck"
          <?php if ($saveShowWork=='1') { echo ' checked="checked" '; }?> >
          <script type="dojo/method" event="onChange" >
        saveUserParameter('planningShowWork',((this.checked)?'1':'0'));
        refreshJsonPlanning();
      </script>
        </div>&nbsp;
      </td>
    </tr>
  </table>
<?php 
}

// ================================================== CHECKBOX FOR RESOURCE 
function drawOptionResource() {
  global $saveShowNullAssignment, $saveShowProject;?>
  <table width="100%">
    <tr class="checkboxLabel">
      <td style="min-width:80px;<?php if (!isNewGui()) echo 'text-align:right;padding-right:10px;';?>"><?php echo pq_ucfirst(i18n("labelShowAssignmentWithoutWork".((isNewGui())?'':'Short')));?></td>
      <td style="width:36px">
        <div title="<?php echo i18n('titleShowAssignmentWithoutWork')?>" dojoType="dijit.form.CheckBox" 
          type="checkbox" id="listShowNullAssignment" name="listShowNullAssignment" class="whiteCheck" 
          <?php if ($saveShowNullAssignment=='1') { echo ' checked="checked" '; }?> >
          <script type="dojo/method" event="onChange" >
          saveUserParameter('listShowNullAssignment',((this.checked)?'1':'0'));
          refreshJsonPlanning();
        </script>
        </div>&nbsp;
      </td>
    </tr>
    <tr class="checkboxLabel">
      <td style="min-width:80px;<?php if (!isNewGui()) echo 'text-align:right;padding-right:10px;';?>"><?php echo pq_ucfirst(i18n("labelShowProjectLevel".((isNewGui())?'':'Short')));?></td>
      <td tyle="width:36px">
        <div title="<?php echo i18n('showProjectLevel')?>" dojoType="dijit.form.CheckBox" 
          type="checkbox" id="listShowProject" name="listShowProject" class="whiteCheck"
          <?php if ($saveShowProject=='1') { echo ' checked="checked" '; }?> >
          <script type="dojo/method" event="onChange" >
            saveUserParameter('planningShowProject',((this.checked)?'1':'0'));
            refreshJsonPlanning();
          </script>
        </div>&nbsp;
      </td>
      </tr>
  </table>
<?php 
}

// ==================
function drawResourceTeamOrga($planningType='resource', $withPool=true) {
  global $displayWidthPlan, $displayListDiv;
  $sizeSelect=($displayListDiv>1400)?150:100;
  $showOrga=($displayWidthPlan>1180)?true:false;
  $showTeam=($displayWidthPlan>980)?true:false;
  $showPool=($displayWidthPlan>780)?true:false;
  $showRes=($displayWidthPlan>780)?true:false;
  $selectResourceName='';
  if(sessionValueExists('selectResourceName')){ $selectResourceName=getSessionValue('selectResourceName'); }
  else if ($planningType=='resource') {
    $selectResourceName=getCurrentUserId();
    setSessionValue('selectResourceName', $selectResourceName);
  }
  ?>
  <table>
    <tr>
      <td style="text-align:right;padding-left:15px;<?php if (! $showRes) echo 'display:none;'?>"><?php echo i18n('colIdResource');?>&nbsp;&nbsp;</td>
      <td style="<?php if (! $showRes) echo 'display:none;'?>">
        <select dojoType="dijit.form.FilteringSelect" class="input roundedLeft" 
          style="width: <?php echo $sizeSelect;?>px;"
          <?php echo autoOpenFilteringSelect();?>
          name="selectResourceName" id="selectResourceName" value="<?php echo $selectResourceName;?>" >
          <script type="dojo/method" event="onChange" >
            <?php if($planningType == "workPlan"){ ?>
              workPlanChangeSelection('selectResourceName');
              saveDataToSession('selectResourceName', dijit.byId('selectResourceName').get("value"), true);
              refreshJsonWorkPlan();
            <?php }else{?>
            saveDataToSession('selectResourceName', dijit.byId('selectResourceName').get("value"), false);
            refreshJsonPlanning();
            <?php }?>
          </script>
          <option value=""></option>
          <?php 
          //$specific='resourcePlanning';
          $specific='imputation';
          $includePool=$withPool;
          $specificDoNotInitialize=true;                       
          include '../tool/drawResourceListForSpecificAccess.php'; ?>
        </select>
      </td>
    <?php if (! isNewGui()) {?>
    </tr>
    <tr>
    <?php }
      
      if($planningType=='workPlan'){ ?>
      <td style="text-align:right;padding-left:15px;<?php if (! $showPool) echo 'display:none;'?>"><?php echo i18n('ResourceTeam');?>&nbsp;&nbsp;</td>
      <td style="<?php if (! $showPool) echo 'display:none;'?>">
        <select dojoType="dijit.form.FilteringSelect" class="input roundedLeft" 
          style="width: <?php echo $sizeSelect;?>px;"
          <?php echo autoOpenFilteringSelect();?>
          name="selectPoolName" id="selectPoolName" value="<?php if(sessionValueExists('selectPoolName')){ echo getSessionValue('selectPoolName'); }?>" >
          <script type="dojo/method" event="onChange" >
            saveDataToSession('selectPoolName', dijit.byId('selectPoolName').get("value"), true);
            workPlanChangeSelection('selectPoolName');
            refreshJsonWorkPlan();
          </script>
          <?php htmlDrawOptionForReference('idResourceTeam', null);?>
        </select>
      </td>
    <?php } ?>
      <td style="text-align:right;padding-left:15px;<?php if (! $showTeam) echo 'display:none;'?>"><?php echo i18n('colIdTeam');?>&nbsp;&nbsp;</td>
      <td style="<?php if (! $showTeam) echo 'display:none;'?>">
        <select dojoType="dijit.form.FilteringSelect" class="input roundedLeft" 
          style="width:<?php echo $sizeSelect;?>px;"
          name="teamName" id="teamName" value="<?php if(sessionValueExists('teamName')){ echo getSessionValue('teamName'); }?>"
          <?php echo autoOpenFilteringSelect();?>
          >
          <script type="dojo/method" event="onChange" > 
            <?php if($planningType == "workPlan"){ ?>
              workPlanChangeSelection('teamName');
              saveDataToSession('teamName', dijit.byId('teamName').get("value"), true);
              refreshJsonWorkPlan();
            <?php }else{?>
            saveDataToSession('teamName', dijit.byId('teamName').get("value"), false);
            refreshJsonPlanning();
            <?php }?>
          </script>
          <?php 
          htmlDrawOptionForReference('idTeam', null)?>  
        </select>
      </td>
    <?php if (! isNewGui()) {?>  
    </tr>
    <tr>
    <?php }?>
      <td style="text-align:right;padding-left:15px;<?php if (! $showOrga) echo 'display:none;'?>"><?php echo i18n('colIdOrganization');?>&nbsp;&nbsp;</td>
        <td style="<?php if (! $showOrga) echo 'display:none;'?>">
        <select dojoType="dijit.form.FilteringSelect" class="input roundedLeft" 
          data-dojo-props="queryExpr: '*${0}*', autoComplete:false"
          style="width:<?php echo $sizeSelect;?>px;"
          name="organizationName" id="organizationName" value="<?php if(sessionValueExists('organizationName')){ echo getSessionValue('organizationName'); }?>"
          <?php echo autoOpenFilteringSelect();?>
          >
          <script type="dojo/method" event="onChange" > 
            <?php if($planningType == "workPlan"){ ?>
              workPlanChangeSelection('organizationName');
              saveDataToSession('organizationName', dijit.byId('organizationName').get("value"), true);
              refreshJsonWorkPlan(); 
            <?php }else{?>
            saveDataToSession('organizationName', dijit.byId('organizationName').get("value"), false);
            refreshJsonPlanning();
            <?php }?> 
          </script>
          <?php 
          global $showHierarchy;
          $showHierarchy=true;
          htmlDrawOptionForReference('idOrganization', null)?>  
        </select>
      </td>
    </tr>
  </table>
<?php   
}

function drawGlobalItemsSelector() {
?>
  <div dojoType="dijit.form.DropDownButton"
    id="listItemsSelector" jsId="listItemsSelector" name="listItemsSelector"
    showlabel="false" class="comboButton" iconClass="iconGlobalView iconSize22 imageColorNewGui"
    title="<?php echo i18n('itemSelector');?>">
    <span>title</span>
    <div dojoType="dijit.TooltipDialog" class="white" id="listItemsSelectorDialog"
      style="position: absolute; top: 50px; right: 40%">
      <script type="dojo/connect" event="onShow" args="evt">
        oldSelectedItems=dijit.byId('globalPlanningSelectItems').get('value');
      </script>
      <div style="text-align: center;position: relative;">
        <button title="" dojoType="dijit.form.Button"
          class="mediumTextButton" id="" name="" showLabel="true"><?php echo i18n('buttonOK');?>
          <script type="dojo/connect" event="onClick" args="evt">
            dijit.byId('listItemsSelector').closeDropDown();
          </script>
        </button>
        <div style="position: absolute;top: 34px; right:42px;"></div>
      </div>   
      <div style="height:5px;border-bottom:1px solid #AAAAAA"></div>    
      <div>                       
        <?php GlobalPlanningElement::drawGlobalizableList();?>
      </div>
      <div style="height:5px;border-top:1px solid #AAAAAA"></div>    
      <div style="text-align: center;position: relative;">
        <button title="" dojoType="dijit.form.Button" 
          class="mediumTextButton" id="" name="" showLabel="true"><?php echo i18n('buttonOK');?>
          <script type="dojo/connect" event="onClick" args="evt">
            dijit.byId('listItemsSelector').closeDropDown();
          </script>
        </button>
        <div style="position: absolute;bottom: 33px; right:42px;" ></div>
      </div>   
	  </div>
	</div>       
<?php             
}
function drawVersionOptionsComponentVersionActivity() {
  global $displayComponentVersionActivity;
  ?>
  <td style="padding-right:5px;padding-left:20px;text-align: right;">
    <?php echo pq_ucfirst(i18n('displayComponentVersionActivity'));?>
  </td>
  <td>
    <div title="<?php echo pq_ucfirst(i18n('displayComponentVersionActivity'));?>" dojoType="dijit.form.CheckBox" 
     class="whiteCheck" type="checkbox" id="listDisplayComponentVersionActivity" name="listDisplayComponentVersionActivity"
     <?php if ($displayComponentVersionActivity=='1') { echo ' checked="checked" '; }?> >
      <script type="dojo/method" event="onChange" >
        saveUserParameter('planningVersionDisplayComponentVersionActivity',((this.checked)?'1':'0'));
        showListFilter('planningVersionDisplayComponentVersionActivity',((this.checked)?'1':'0'));
        refreshJsonPlanning();
      </script>
    </div>
  </td>
<?php 
}
function drawVersionOptionsVersionsWithoutActivity() {
  global $showListFilter;
  ?>
  <td style="padding-right:5px;padding-left:20px;text-align: right;" >
	  <div id="versionsWithoutActivity" style="visibility:<?php  echo ($showListFilter=='true')?'visible':'hidden';?>;">
      <?php echo pq_ucfirst(i18n('versionsWithoutActivity'));?>
    </div>
  </td>
  <td>
	  <div id="hideVersionsWithoutActivityCheck" style="visibility:<?php  echo ($showListFilter=='true')?'visible':'hidden';?>!important;">
      <div title="<?php echo pq_ucfirst(i18n('versionsWithoutActivityCheck'));?>" dojoType="dijit.form.CheckBox" 
       class="whiteCheck" type="checkbox" id="versionsWithoutActivityCheck" name="versionsWithoutActivityCheck"
       <?php if ($hideversionsWithoutActivity=Parameter::getUserParameter('versionsWithoutActivity')=='1') { echo ' checked="checked" '; }?> >
        <script type="dojo/method" event="onChange" >
          saveUserParameter('versionsWithoutActivity',((this.checked)?'1':'0'));
          refreshJsonPlanning();
        </script>
      </div>
    </div>
  </td>
<?php
} 
function drawVersionOptionsProductVersionActivity() {
  global $showListFilter, $displayProductVersionActivity;
  ?>
  <td style="padding-right:5px;padding-left:20px;text-align: right;">
    <?php echo pq_ucfirst(i18n('displayProductVersionActivity'));?>
  </td>
  <td>
    <div title="<?php echo pq_ucfirst(i18n('displayProductVersionActivity'));?>" dojoType="dijit.form.CheckBox" 
     class="whiteCheck" type="checkbox" id="listDisplayProductVersionActivity" name="listDisplayProductVersionActivity"
     <?php if ($displayProductVersionActivity=='1') { echo ' checked="checked" '; }?> >
      <script type="dojo/method" event="onChange" >
        saveUserParameter('planningVersionDisplayProductVersionActivity',((this.checked)?'1':'0'));
        showListFilter('planningVersionDisplayProductVersionActivity',((this.checked)?'1':'0'));
        refreshJsonPlanning();
      </script>
    </div>
  </td>
<?php
} 

function drawVersionOptionsOnlyActivesVersions() {
  global $showOnlyActivesVersions,$showListFilter;?>
  <td  style="padding-right:5px;padding-left:20px;text-align: right;" > 
    <?php echo pq_ucfirst(i18n('showOnlyActivesVersions'));?>
  </td>
  <td>  
    <div title="<?php echo pq_ucfirst(i18n('showOnlyActivesVersions'));?>" dojoType="dijit.form.CheckBox" 
     class="whiteCheck" type="checkbox" id="showOnlyActivesVersions" name="showOnlyActivesVersions"
     <?php if ($showOnlyActivesVersions=='1') { echo ' checked="checked" '; }?> >
      <script type="dojo/method" event="onChange" >
        saveUserParameter('showOnlyActivesVersions',((this.checked)?'1':'0'));
        refreshJsonPlanning();
      </script>
    </div>
  </td>
<?php 
}
function drawVersionOptionsOneTimeActivities() {
  global $showOneTimeActivities,$showListFilter;?>
  <td  style="padding-right:5px;padding-left:20px;text-align: right;" >
    <div id="hideOneTimeActivitiesLabel" style="visibility:<?php  echo ($showListFilter=='true')?'visible':'hidden';?>;">
      <span for="showOneTimeActivities"><?php echo pq_ucfirst(i18n("versionPlanningShowOneTimeActivities"));?></span>
    </div>
  </td>
  <td>
    <div id="hideOneTimeActivitiesCheck" style="visibility:<?php  echo ($showListFilter=='true')?'visible':'hidden';?>!important;">  
    <span title="<?php echo pq_ucfirst(i18n('versionPlanningShowOneTimeActivities'));?>" dojoType="dijit.form.CheckBox"
     type="checkbox" id="showOneTimeActivities" name="showOneTimeActivities" class="whiteCheck"
     <?php if ( $showOneTimeActivities) {echo 'checked="checked"'; } ?>  >
      <script type="dojo/method" event="onChange" >
        saveUserParameter('showOneTimeActivities',((this.checked)?'1':'0'));
        refreshJsonPlanning();
      </script>
    </span>
    </div>
  </td>
<?php 
}                            
function drawVersionOptionsProjectLevels() {
  global $showProjectLevel,$showListFilter;?>
  <td style="padding-right:5px;padding-left:20px;text-align: right;">
    <div id="hideProjectLevelLabel" style="visibility:<?php  echo ($showListFilter=='true')?'visible':'hidden';?>;">
    <?php echo pq_ucfirst(i18n('labelShowProjectLevel'));?>
    </div>
  </td>
  <td>
      <div id="hideProjectLevelCheck" style="visibility:<?php  echo ($showListFilter=='true')?'visible':'hidden';?>;">
    <div title="<?php echo pq_ucfirst(i18n('labelShowProjectLevel'));?>" dojoType="dijit.form.CheckBox"
     class="whiteCheck" type="checkbox" id="showProjectLevel" name="showProjectLevel"
     <?php if ($showProjectLevel) { echo ' checked="checked" '; }?> >
      <script type="dojo/method" event="onChange" >
        saveUserParameter('planningVersionShowProjectLevel',((this.checked)?'1':'0'));
        refreshJsonPlanning();
      </script>
    </div>
  </td>
<?php 
}                            
function drawVersionOptionsActivityHierarchy() {
  global $showActivityHierarchy,$showListFilter;?>  
  <td style="padding-right:5px;padding-left:20px;text-align: right;">
    <div id="hideActivityHierarchyLabel" style="visibility:<?php  echo ($showListFilter=='true')?'visible':'hidden';?>;">
    <?php echo pq_ucfirst(i18n('labelShowActivityHierarchy'));?>
    </div>
  </td>
  <td>
    <div id="hideActivityHierarchyCheck" style="visibility:<?php  echo ($showListFilter=='true')?'visible':'hidden';?>;">
    <div title="<?php echo pq_ucfirst(i18n('labelShowActivityHierarchy'));?>" dojoType="dijit.form.CheckBox"
     class="whiteCheck" type="checkbox" id="showActivityHierarchy" name="showActivityHierarchy"
     <?php if ($showActivityHierarchy) { echo ' checked="checked" '; }?> >
      <script type="dojo/method" event="onChange" >
        saveUserParameter('planningVersionDisplayActivityHierarchy',((this.checked)?'1':'0'));
        refreshJsonPlanning();
      </script>
    </div>
    </div>
  </td>
<?php 
} 

function drawOptionHideTimelineNew() {
  $hideTimeline = Parameter::getUserParameter('hideTimeline');
  $maxTimelineRow = Parameter::getUserParameter('maxTimelineRow');
  ?>
  <table style="margin-top:7px;margin-left:32px;">
  <tr>
    <td title="<?php echo i18n('helpDisplayTimeline');?>">
          <div  id="hideTimeline" class="colorSwitch" data-dojo-type="dojox/mobile/Switch"
                <?php if ($hideTimeline=='0') {echo 'value="on"'; }else{echo 'value="off"';} ?>   
                 leftLabel="" rightLabel="" style="width:10px;position:relative; left:10px;top:2px;z-index:99;" >
            <script type="dojo/method" event="onStateChanged" >
              saveUserParameter('hideTimeline',((this.value=='off')?'1':'0'));
              if(dojo.byId('workPlanJsonData')){
                loadMenuBarItem('PlanningWorkPlan','PlanningWorkPlan','bar');
              }else{
                loadMenuBarItem('Planning','Planning','bar');
              }
  		      </script>
  		    </div>
  		    <span onclick="invertSwitchValue('hideTimeline');">&nbsp;&nbsp;<?php echo i18n('tabDisplay');?></span>
    </td>
 </tr><tr>  
    <td title="<?php echo i18n('helpLineTimeline');?>" style="padding-left:10px;padding-right:5px;padding-top:2px;">
    <?php echo pq_ucfirst(i18n('maxTimelineRow'));?>&nbsp;
      <div title="" style="max-width:30px;" class="input rounded" dojoType="dijit.form.TextBox" type="text" value="<?php echo $maxTimelineRow;?>">
          <script type="dojo/method" event="onChange" >
          saveUserParameter('maxTimelineRow',this.value);
          refreshTimeline();
        </script>
        </div>
     </td>
  </tr>
 </table>
<?php 
}

function drawOptionHideTimeline() {
  $hideTimeline = Parameter::getUserParameter('hideTimeline');
  $maxTimelineRow = Parameter::getUserParameter('maxTimelineRow');
  ?>
  <div style="white-space:nowrap; <?php echo (isNewGui())?'margin-right:6px;margin-top:5px;':'position:absolute; bottom:5px;left:10px;'; ?>" class="checkboxLabel">
  <?php echo pq_ucfirst(i18n('maxTimelineRow'));?>&nbsp;
    <div title="" style="max-width:30px;" class="input rounded" dojoType="dijit.form.TextBox" type="text" value="<?php echo $maxTimelineRow;?>">
      <script type="dojo/method" event="onChange" >
        saveUserParameter('maxTimelineRow',this.value);
        refreshTimeline();
      </script>
    </div>
    <?php if (isNewGui()) {?><?php echo pq_ucfirst(i18n('hideTimeline'));?>&nbsp;<?php }?>
    <span title="<?php echo pq_ucfirst(i18n('hideTimeline'));?>" dojoType="dijit.form.CheckBox"
      type="checkbox" id="hideTimeline" name="hideTimeline" class="whiteCheck"
      <?php if ( $hideTimeline=='1') {echo 'checked="checked"'; } ?>  >  
      <script type="dojo/connect" event="onChange" args="evt">
        saveUserParameter('hideTimeline',((this.checked)?'1':'0'));
        if(dojo.byId('workPlanJsonData')){
          loadMenuBarItem('PlanningWorkPlan','PlanningWorkPlan','bar');
        }else{
          loadMenuBarItem('Planning','Planning','bar');
        }
      </script>                    
    </span>
    <?php if (!isNewGui()) {?>&nbsp;<?php echo i18n('hideTimeline');?><?php }?>
  </div>
<?php 
}

?>
