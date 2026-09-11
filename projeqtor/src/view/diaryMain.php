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
 * Presents an object. 
 */
  require_once "../tool/projeqtor.php";
  scriptLog('   ->/view/diaryMain.php');  
  $user=getSessionUser();
  
  $currentWeek=weekNumber(date('Y-m-d')) ;
  $currentYear=pq_strftime("%Y") ;
  $currentDay=date('Y-m-d',firstDayofWeek($currentWeek,$currentYear));
  $diaryDate = date('Y-m-d');
  if(sessionValueExists('dateSelectorDiary')){
    $diaryDate = getSessionValue('dateSelectorDiary');
    $currentWeek=weekNumber($diaryDate) ;
    $currentYear=pq_strftime("%Y") ;
    $currentDay=date('Y-m-d',firstDayofWeek($currentWeek,$currentYear));
  }
  
  $period=Parameter::getUserParameter("diaryPeriod");
  if (!$period) {$period="month";}
  $year=date('Y', pq_strtotime($diaryDate));
  $month=date('m', pq_strtotime($diaryDate));
  $week=date('W', pq_strtotime($diaryDate));
  $day=$diaryDate;
  $filterByStatus=Parameter::getGlobalParameter('filterByStatus');
  $displayByStatusList=Parameter::getUserParameter("displayByStatusList_Diary");
  
?>
<input type="hidden" name="objectClassManual" id="objectClassManual"
	value="Diary" />
<div class="container" dojoType="dijit.layout.BorderContainer">
	<div id="listDiv" dojoType="dijit.layout.ContentPane" region="top"
		class="listTitle" splitter="false"
		style="max-height: <?php echo ($filterByStatus=='YES' and $displayByStatusList == 'flex')?'57':'37';?>px !important; padding-top:3px !important;">
		<table width="100%" class="listTitle">
			<tr height="17px" style="max-height: 17px;">
				<td style="width: 50px; text-align: center"><div style="position: relative;top: -17px;">
                  <?php echo formatIcon('Diary',32,null,true);?>
                </div></td>
				<td style="width: 50px; text-align: left"><span class="title"><?php echo i18n('menuDiary');?></span></td>
				<td style="text-align: center;"> 
		   <?php 
		   echo '<div style="min-width:200px;font-size:20px;font-weight:bold;display: flex;flex-direction: column;align-items: center;padding-left:10px;" id="diaryCaption">';
		   if ($period=='month') {
		      echo i18n(date("F",mktime(0,0,0,$month,1,$year))).' '.$year;
		   } else if ($period=='week') {
              $firstday=date('Y-m-d',firstDayofWeek($week, $year));
              $lastday=addDaysToDate($firstday, 6);
              echo $year.' #'.$week."<span style='font-size:12px'> (".htmlFormatDate($firstday)." - ".htmlFormatDate($lastday).")</span>";
           } else if ($period=='day') {
              $vDayArr = array('', i18n("Monday"),i18n("Tuesday"),i18n("Wednesday"),
		                i18n("Thursday"), i18n("Friday"),i18n("Saturday"),i18n("Sunday"));
              echo $vDayArr[date("N",mktime(0,0,0,$month,date('d'),$year))]." ".htmlFormatDate($day);
           }
           echo "</div>";
		   ?>
		   </td>
				<td nowrap="nowrap">
				<form id="diaryForm" name="diaryForm">
						<input type="hidden" name="diaryYear" id="diaryYear" value="<?php echo $year;?>" />
						<input type="hidden" name="diaryMonth" id="diaryMonth" value="<?php echo $month;?>" />
						<input type="hidden" name="diaryWeek" id="diaryWeek" value="<?php echo $week;?>" />
						<input type="hidden" name="diaryDay" id="diaryDay" value="<?php echo $day;?>" />
						<table style="width: 100%">
							<tr>
							 <td>
							 <?php
                              if ($filterByStatus=='YES') {
                                if (!$displayByStatusList) $displayByStatusList='none';
                                $arrObj=array(new Action(), new Ticket(), new Milestone(), new Meeting(), new Activity(), new Delivery());
                                $listStatus=array();
                                foreach ($arrObj as $obj) {
                                  $listObjStatus=$obj->getExistingStatus();
                                  foreach ($listObjStatus as $status) {
                                    if (!in_array($status, $listStatus)) $listStatus[]=$status;
                                  }
                                }
                                $countListStatus = (sessionValueExists('countStatusDiary') and getSessionValue('countStatusDiary') != '')?getSessionValue('countStatusDiary'):'';
                              ?>
                              <div class="listTitle" id="barFilterByStatus" dojoType="dijit.layout.ContentPane" region="top" style="display: <?php echo $displayByStatusList;?>; width: 100%;">
                              	<div style="display:flex;font-weight:bold;padding-left:10px;align-items:center;"><?php echo i18n("colIdStatus");?>&nbsp;:&nbsp;</div>
                              	<table style="display: flex; width: 100%;height: auto;overflow-y: auto;">
                              		<tr style="display: inlineblock; width: 100%">
                                          <?php
                                            $cptStatus=0;
                                          	foreach ($listStatus as $status) {
                                          		$cptStatus += 1;
                                          		$docLineclass = 'docLineTag';
                                          		$statusStyle = '';
                                          		if(sessionValueExists('showStatus'.$status->id.'Diary') and getSessionValue('showStatus'.$status->id.'Diary') == 'true'){
                                              		$docLineclass = 'docLineTagNew';
                                              		$statusStyle = 'background-color:'.$status->color.';color:'.getForeColor($status->color).';';
                                          		}
                                          ?>		
                                          <td style="float: left; height: 100%; white-space: nowrap" title="<?php echo i18n('selectStatus', array($status->name));?>">
                          			     <span class="<?php echo $docLineclass;?>" style="cursor:pointer;<?php echo $statusStyle;?>" onClick="updateShowStatusState(this, <?php echo $cptStatus; ?>, '<?php echo $status->color;?>');">
                          				    <div style="padding: 0px 5px 0px 5px;"><?php echo $status->name; ?><div class="docLineTagPin"></div></div>
                          	             </span>
                          				  <div style="position:relative;float:left;display:none;" id="showStatus<?php echo $cptStatus; ?>"
                          				    dojoType="dijit.form.CheckBox" type="checkbox" value="<?php echo $status->id; ?>"
                          				    <?php if(sessionValueExists('showStatus'.$status->id.'Diary')){if(getSessionValue('showStatus'.$status->id.'Diary') == 'true'){ ?> checked=" checked "<?php } }?> 
                          				    onChange="refreshDiaryList()">
                          				  </div>
                          			     </td>
                                          <?php
                                          	 } ?>
                              		      </tr>
                              	       </table>
                              	     <input type="hidden" id="countStatus" value="<?php echo $cptStatus; ?>" />
                              		</div>
                              <?php } ?>
							 </td>
							 <td style="width: 175px;text-align: right;padding: 0px 10px;">
                              <?php echo i18n("colFirstDay");?> 
                                <div dojoType="dijit.form.DateTextBox"
                						<?php if (sessionValueExists('browserLocaleDateFormatJs')) {
                										echo ' constraints="{datePattern:\''.getSessionValue('browserLocaleDateFormatJs').'\'}" ';
                									}?>
                						id="dateSelectorDiary" name="dateSelectorDiary"
                                        invalidMessage="<?php echo i18n('messageInvalidDate')?>"
                						type="text" maxlength="10"
                						style="width: 100px; text-align: center;"
                						class="input roundedLeft" hasDownArrow="true"
                						value="<?php echo $currentDay;?>">
                						<script type="dojo/method" event="onChange">
                                          diarySelectDate();
                						</script>
                					</div>
                				</td>
                				<td style="width: 80px;padding-right: 10px;">
                				  <button dojoType="dijit.form.Button" type="button" style="" class="roundedVisibleButton">
                                    <?php echo ucfirst(i18n('today'));?>
                                    <script type="dojo/method" event="onClick">
                                      dijit.byId('dateSelectorDiary').set('value','<?php echo date('Y-m-d');?>');
                                    </script>
                                  </button>
                				</td>
                				<td style="width: 170px;text-align: right;padding-right: 10px;">
                				  <table>
                				    <tr>
                				      <td>
                				        <div id="previousOnDateMode">
                				          <button id="previousOnDateModeButton" dojoType="dijit.form.Button" showlabel="false" style="position:relative;height:18px"
                                           iconClass="dijitButtonIcon dijitButtonIconPrevious" class="detailButton" >
                                            <script type="dojo/connect" event="onClick" args="evt">
                                                diaryPrevious();
                                            </script>
                                          </button>
                				        </div>
                				      </td>
                				      <td>
                				        <select dojoType="dijit.form.FilteringSelect" class="input roundedLeft" style="width: 100px;" name="diaryPeriod" id="diaryPeriod"
      									<?php echo autoOpenFilteringSelect();?>
      									value="<?php echo $period;?>">
									     <script type="dojo/method" event="onChange">
                                            diaryChangePeriod();
                                         </script>
          							     <option value="month"><?php echo i18n('colMonth');?></option>
          							     <option value="week"><?php echo i18n('colWeekPeriod');?></option>
          							     <option value="day"><?php echo i18n('colDay');?></option>
       						           </select>
                				      </td>
                				      <td>
                				        <div id="nextOnDateMode">
                      				      <button id="nextOnDateModeButton" dojoType="dijit.form.Button" showlabel="false" style="position:relative;height:18px"
                                             iconClass="dijitButtonIcon dijitButtonIconNext" class="detailButton" >
                                            <script type="dojo/connect" event="onClick" args="evt">
                                               diaryNext();
                                            </script>
                                          </button>
                				        </div>
                				      </td>
                				    </tr>
                				  </table>
                				</td>
								<td style="width: 200px;text-align: right;padding-right: 10px;">
									<table>
										<tr>
											<td>
		   					                  <?php echo i18n("colIdResource");?> 
		   					                  <select dojoType="dijit.form.FilteringSelect"
												class="input roundedLeft" style="width: 150px;"
												name="diaryResource" id="diaryResource"
												<?php echo autoOpenFilteringSelect();?>
												value="<?php if(sessionValueExists('diaryResource')){ echo getSessionValue('diaryResource');}else{ echo ($user->isResource)?$user->id:'0';}?>">
													<script type="dojo/method" event="onChange">
                                                      saveDataToSession('diaryResource',dijit.byId('diaryResource').get("value"), false);
                                                      loadContent("../view/diary.php","detailDiv","diaryForm");
                                                    </script>
    							                <?php
                                                $specific='diary';
                                                include '../tool/drawResourceListForSpecificAccess.php'?>  
       						                   </select>
											</td>
										</tr>
									</table>
								</td>
								<td style="width:32px;padding-right: 5px;">
								  <div dojoType="dijit.form.DropDownButton"							    
                                   id="extraButtonDiary" jsId="extraButtonDiary" name="extraButtonDiary" 
                                   showlabel="false" class="comboButton" iconClass="dijitButtonIcon dijitButtonIconExtraButtons" class="detailButton" 
                                   title="<?php echo i18n('extraButtons');?>">
                                     <div dojoType="dijit.TooltipDialog" class="white" id="extraButtonDiaryDialog" tyle="position: absolute; top: 50px; right: 40%">        
                                       <table style="margin:5px">
                                         <tr style="width:100%;">
                                          <td><?php diaryParameterList();?></td>
                                         </tr>
                                       </table>
                                     </div>
                                  </div>
								</td>
							</tr>
						</table>
					</form></td>
			</tr>
		</table>
	</div>
  
  <?php
  $destinationHeight=intval($_REQUEST['destinationHeight'])-54;
  if (isset($displayStatus) and $displayStatus!='none') $destinationHeight-=16;
  ?>
  <div id="detailDiv" dojoType="dijit.layout.ContentPane" region="center" style="overflow:auto;height: <?php echo $destinationHeight?>px;">
   <?php include 'diary.php'; ?>
  </div>
	</div>
	
	<div class="contextMenuClass comboButtonInvisible" dojoType="dijit.form.DropDownButton" id="diaryContextMenu" name="diaryContextMenu" style="position:absolute;top:0px;left:0px;width:0px;height:0px;overflow:hidden;">
      <div dojoType="dijit.TooltipDialog" id="dialogDiaryContextMenu" tabindex="0" onMouseEnter="clearTimeout(hideDiaryContextMenu);" onMouseLeave="hideDiaryContextMenu(200)" onfocusout="hideElementOnFocusOut(null, hideDiaryContextMenu(200))">
        <input type="hidden" id="contextMenuRefId" name="contextMenuRefId" value="" />
        <input type="hidden" id="contextMenuRefType" name="contextMenuRefType" value="" />
        <table style="width:100%;height:100%">
          <tr id="addFromDiaryAction" class="contextMenuRow" onClick="">
            <td style="padding-top:5px;padding-bottom:5px;"><?php echo formatSmallButton('Action', true);?></td>
            <td style="padding-left:10px;padding-top:5px;padding-bottom:5px;" id="addFromDiaryAction_label"><?php echo i18n('buttonNew', array(i18n('Action')));?></td>
          </tr>
          <tr id="addFromDiaryDelivery" class="contextMenuRow" onClick="">
            <td style="padding-top:5px;padding-bottom:5px;"><?php echo formatSmallButton('Delivery', true);?></td>
            <td style="padding-left:10px;padding-top:5px;padding-bottom:5px;" id="addFromDiaryDelivery_label"><?php echo i18n('buttonNew', array(i18n('Delivery')));?></td>
          </tr>
          <tr id="addFromDiaryMeeting" class="contextMenuRow" onClick="">
            <td style="padding-top:5px;padding-bottom:5px;"><?php echo formatSmallButton('Meeting', true);?></td>
            <td style="padding-left:10px;padding-top:5px;padding-bottom:5px;" id="addFromDiaryMeeting_label"><?php echo i18n('buttonNew', array(i18n('Meeting')));?></td>
          </tr>
          <tr id="editFromDiary" class="contextMenuRow" onClick="">
            <td style="padding-top:5px;padding-bottom:5px;"><?php echo formatSmallButton('Edit');?></td>
            <td style="padding-left:10px;padding-top:5px;padding-bottom:5px;" id="editFromDiary_label"><?php echo i18n('contextMenuButtonEdit');?></td>
          </tr>
          <tr id="gotoTimesheetFromDiary" class="contextMenuRow" onClick="">
            <td style="padding-top:5px;padding-bottom:5px;"><?php echo formatSmallButton('Imputation', true);?></td>
            <td style="padding-left:10px;padding-top:5px;padding-bottom:5px;" id="gotoTimesheetFromDiary_label"><?php echo i18n('gotoTimesheet');?></td>
          </tr>
          <tr id="gotoItemFromDiary" class="contextMenuRow" onClick="">
            <td style="padding-top:5px;padding-bottom:5px;"><?php echo formatSmallButton('Goto', true);?></td>
            <td style="padding-left:10px;padding-top:5px;padding-bottom:5px;" id="gotoItemFromDiary_label"></td>
          </tr>
          <tr id="searchInPlanningFromDiary" class="contextMenuRow" onClick="">
        		<td style="padding-top:5px;padding-bottom:5px;"><?php echo formatSmallButton('Planning', true);?></td>
        		<td style="padding-left:10px;padding-top:5px;padding-bottom:5px;" id="searchInPlanningFromDiary_label"><?php echo i18n('buttonSearch')?></td>
      		</tr>
        </table>
      </div>
    </div>
	
<?php 
function diaryParameterList(){
  $seeWork=Parameter::getUserParameter("diarySeeWork");
  $seeWork=($seeWork=='on' or $seeWork=='1')?true:false;
  if($seeWork && PlanningElement::getWorkVisibiliy(getSessionUser()->idProfile)=="ALL")$seeWork=true; else $seeWork=false;

  $showIdle = Parameter::getUserParameter("showIdleDiary");
  $showIdle = ($showIdle=='on' or $showIdle=='1')?true:false;

  $fullWidthElement = Parameter::getUserParameter("diaryFullWidthElement");
  $fullWidthElement = ($fullWidthElement=='on' or $fullWidthElement=='1')?true:false;

  $showDone = Parameter::getUserParameter("showDoneDiary");
  $showDone = ($showDone=='on' or $showDone=='1')?true:false;
  
  $showDayOff = Parameter::getUserParameter("showDayOffDiary");
  $showDayOff = ($showDayOff=='on' or $showDayOff=='1' or $showDayOff=="")?true:false;
  
  $showPlannedWorkPool = Parameter::getUserParameter("showPlannedWorkPoolDiary");
  $showPlannedWorkPool = ($showPlannedWorkPool=='on' or $showPlannedWorkPool=='1' or $showPlannedWorkPool=="")?true:false;

  $showActivitiesPlannedEndDate = Parameter::getUserParameter("showActivitiesPlannedEndDateDiary");
  $showActivitiesPlannedEndDate = ($showActivitiesPlannedEndDate=='on' or $showActivitiesPlannedEndDate=='1' or $showActivitiesPlannedEndDate=="")?true:false;

  $hideStatus = Parameter::getUserParameter("diaryHideStatus");
  $hideStatus = ($hideStatus=='on' or $hideStatus=='')?true:false;

//   $hideProduct = Parameter::getUserParameter("diaryHideProduct");
//   $hideProduct = ($hideProduct=='on' or $hideProduct=='')?true:false;

//   $hideActivityPlanning = Parameter::getUserParameter("diaryHideActivityPlanning");
//   $hideActivityPlanning = ($hideActivityPlanning=='on' or $hideActivityPlanning=='')?true:false;

  $hideResponsible = Parameter::getUserParameter("diaryHideResponsible");
  $hideResponsible = ($hideResponsible=='on' or $hideResponsible=='')?true:false;

  $hidePriority = Parameter::getUserParameter("diaryHidePriority");
  $hidePriority = ($hidePriority=='on' or $hidePriority=='')?true:false;

  $hideCriticality = Parameter::getUserParameter("diaryHideCriticality");
  $hideCriticality = ($hideCriticality=='on' or $hideCriticality=='')?true:false;

  $hidePlannedDate = Parameter::getUserParameter("diaryHidePlannedDate");
  $hidePlannedDate = ($hidePlannedDate=='on' or $hidePlannedDate=='')?true:false;

  $hidedeType = Parameter::getUserParameter("diaryHideType");
  $hidedeType = ($hidedeType=='on' or $hidedeType=='')?true:false;

//   $hideProjectName = Parameter::getUserParameter("diaryHideProjectName");
//   $hideProjectName = ($hideProjectName=='on' or $hideProjectName=='')?true:false;

  $modeColorTitle = Parameter::getUserParameter( "diaryModeColorTitle");
  $modeColorTitle = (!$modeColorTitle)? 'noColor' : $modeColorTitle;

  $hideColorTitle = Parameter::getUserParameter("diaryHideColorTitle");
  $hideColorTitle = ($hideColorTitle=='on')?true:false;

  echo '<table style="width:100%;">';
  echo '  <tr>';
  echo '    <td style="vertical-align:top;">';
  echo '<table style="width:440px;margin:5px 15px 5px 5px;display:inline-block;">';
  echo '  <tr>';
  echo '    <td style="width:40px;"><div class="iconDisplayOnKanban iconSize32 imageColorNewGuiNoSelection" style="border:0"></div></td>';
  echo '    <td class="dependencyHeader planningDialogTitle" style="width:400px;text-align:left;padding-left: 5px;">'.i18n('displayOnDiary').'</td>';
  echo '  </tr>';
  echo '  <tr>';
  echo '    <td style="padding-top:2px;">';
  echo '      <div id="diaryFullWidthElement" name="diaryFullWidthElement" class="colorSwitch" data-dojo-type="dojox/mobile/Switch" '.(($fullWidthElement)?'value="on"':'value="off"').' leftLabel="" rightLabel="" style="width:25px;">';
  echo '        <script type="dojo/method" event="onStateChanged" >';
  echo '          diaryShowFullWidthElement(this.value);';
  echo '        </script>';
  echo '      </div>';
  echo '    </td>';
  echo '    <td style="padding-left:5px;" class="checkboxLabel"><span onclick="invertSwitchValue(\'diaryFullWidthElement\');">'.pq_ucfirst(i18n("labelKanbanFullWidthElement")).'</span></td>';
  echo '  </tr>';
  echo '  <tr>';
  echo '    <td style="padding-top:2px;">';
  echo '      <div id="diaryShowIdle" name="diaryShowIdle" class="colorSwitch" data-dojo-type="dojox/mobile/Switch" '.(($showIdle)?'value="on"':'value="off"').' leftLabel="" rightLabel="" style="width:25px;">';
  echo '        <script type="dojo/method" event="onStateChanged" >';
  echo '          var callBack=function(){loadContent("../view/diary.php","detailDiv","diaryForm");};';
  echo '          saveDataToSession("showIdleDiary",this.value,true,callBack);';
  echo '        </script>';
  echo '      </div>';
  echo '    </td>';
  echo '    <td style="padding-left:5px;" class="checkboxLabel"><span onclick="invertSwitchValue(\'listShowIdle\');">'.pq_ucfirst(i18n("labelKanbanShowIdle")).'</span></td>';
  echo '  </tr>';
  echo '  <tr>';
  echo '    <td style="padding-top:2px;">';
  echo '      <div id="diaryShowDone" name="diaryShowDone" class="colorSwitch" data-dojo-type="dojox/mobile/Switch" '.(($showDone)?'value="on"':'value="off"').' leftLabel="" rightLabel="" style="width:25px;">';
  echo '        <script type="dojo/method" event="onStateChanged" >';
  echo '          var callBack=function(){loadContent("../view/diary.php","detailDiv","diaryForm");};';
  echo '          saveDataToSession("showDoneDiary",this.value,true,callBack);';
  echo '        </script>';
  echo '      </div>';
  echo '    </td>';
  echo '    <td style="padding-left:5px;" class="checkboxLabel"><span onclick="invertSwitchValue(\'diaryShowDone\');">'.pq_ucfirst(i18n("labelShowDone")).'</span></td>';
  echo '  </tr>';
  echo '  <tr>';
  echo '    <td style="padding-top:2px;">';
  echo '      <div id="diaryShowDayoff" name="diaryShowDayoff" class="colorSwitch" data-dojo-type="dojox/mobile/Switch" '.(($showDayOff)?'value="on"':'value="off"').' leftLabel="" rightLabel="" style="width:25px;">';
  echo '        <script type="dojo/method" event="onStateChanged" >';
  echo '          var callBack=function(){loadContent("../view/diary.php","detailDiv","diaryForm");};';
  echo '          saveDataToSession("showDayOffDiary",this.value,true,callBack);';
  echo '        </script>';
  echo '      </div>';
  echo '    </td>';
  echo '    <td style="padding-left:5px;" class="checkboxLabel"><span onclick="invertSwitchValue(\'diaryShowDayoff\');">'.pq_ucfirst(i18n("labelHideDayOff")).'</span></td>';
  echo '  </tr>';
  
  // Activity is displayed on planned end date if resource assigned to the activity
  echo '  <tr>';
  echo '    <td style="padding-top:2px;">';
  echo '      <div id="diaryShowActivitiesPlannedEndDate" name="diaryShowActivitiesPlannedEndDate" class="colorSwitch" data-dojo-type="dojox/mobile/Switch" '.(($showActivitiesPlannedEndDate)?'value="on"':'value="off"').' leftLabel="" rightLabel="" style="width:25px;">';
  echo '        <script type="dojo/method" event="onStateChanged" >';
  echo '          var callBack=function(){loadContent("../view/diary.php","detailDiv","diaryForm");};';
  echo '          saveDataToSession("showActivitiesPlannedEndDateDiary",this.value,true,callBack);';
  echo '        </script>';
  echo '      </div>';
  echo '    </td>';
  echo '    <td style="padding-left:5px;" class="checkboxLabel"><span onclick="invertSwitchValue(\'diaryShowActivitiesPlannedEndDate\');">'.pq_ucfirst(i18n("showActivitiesPlannedEndDate")).'</span></td>';
  echo '  </tr>';
  
  // Planned Pool
  echo '  <tr>';
  echo '    <td style="padding-top:2px;">';
  echo '      <div id="diaryShowPlannedWorkPool" name="diaryShowPlannedWorkPool" class="colorSwitch" data-dojo-type="dojox/mobile/Switch" '.(($showPlannedWorkPool)?'value="on"':'value="off"').' leftLabel="" rightLabel="" style="width:25px;">';
  echo '        <script type="dojo/method" event="onStateChanged" >';
  echo '          var callBack=function(){loadContent("../view/diary.php","detailDiv","diaryForm");};';
  echo '          saveDataToSession("showPlannedWorkPoolDiary",this.value,true, callBack);';
  echo '        </script>';
  echo '      </div>';
  echo '    </td>';
  echo '    <td style="padding-left:5px;" class="checkboxLabel"><span onclick="invertSwitchValue(\'diaryShowPlannedWorkPool\');">'.pq_ucfirst(i18n("showPlannedWorkPool")).'</span></td>';
  echo '  </tr>';
  
  echo '  <tr id="diarySeeWorkTR" style="'.((!$fullWidthElement)?'display:none;':'').'">';
  echo '    <td style="padding-top:10px;">';
  echo '      <div id="diarySeeWork" name="diarySeeWork" class="colorSwitch" data-dojo-type="dojox/mobile/Switch" '.(($seeWork)?'value="on"':'value="off"').' leftLabel="" rightLabel="" style="width:25px;">';
  echo '        <script type="dojo/method" event="onStateChanged" >';
  echo '          var callBack=function(){loadContent("../view/diary.php","detailDiv","diaryForm");};';
  echo '          saveDataToSession("diarySeeWork",this.value,true, callBack);';
  echo '        </script>';
  echo '      </div>';
  echo '    </td>';
  echo '    <td style="padding-left:5px;" class="checkboxLabel"><span onclick="invertSwitchValue(\'diarySeeWork\');">'.pq_ucfirst(i18n("kanbanSeeWork")).'</span></td>';
  echo '  </tr>';
  echo '</table>';
  echo '    </td>';
  echo '    <td rowspan="2" style="vertical-align:top;">';
  echo '<table style="width:240px;margin:5px 5px 0px 5pxpx;display:inline-block;">';
  echo '  <tr style="padding:5px;">';
  echo '    <td style="width:40px;"><div class="iconDisplayOnKanbanTiles iconSize32 imageColorNewGuiNoSelection" style="border:0"></div></td>';
  echo '    <td class="dependencyHeader planningDialogTitle" style="width:200px;text-align:left;padding-left: 5px;">'.i18n('displayOnKanbanTiles').'</td>';
  echo '  </tr>';
  echo '  <tr>';
  echo '    <td style="padding-top:2px;">';
  echo '      <div id="diaryHideStatus" name="diaryHideStatus" class="colorSwitch" data-dojo-type="dojox/mobile/Switch" '.(($hideStatus)?'value="on"':'value="off"').' leftLabel="" rightLabel="" style="width:25px;">';
  echo '        <script type="dojo/method" event="onStateChanged" >';
  echo '          var callBack=function(){loadContent("../view/diary.php","detailDiv","diaryForm");};';
  echo '          saveDataToSession("diaryHideStatus",this.value,true,callBack);';
  echo '        </script>';
  echo '      </div>';
  echo '    </td>';
  echo '    <td style="padding-left:5px;" class="checkboxLabel"><span onclick="invertSwitchValue(\'diaryHideStatus\');">'.pq_ucfirst(i18n("labelKanbanHideStatus")).'</span></td>';
  echo '  </tr>';
  echo '  <tr>';
  echo '    <td style="padding-top:2px;">';
  echo '      <div id="diaryHideResponsible" name="diaryHideResponsible" class="colorSwitch" data-dojo-type="dojox/mobile/Switch" '.(($hideResponsible)?'value="on"':'value="off"').' leftLabel="" rightLabel="" style="width:25px;">';
  echo '        <script type="dojo/method" event="onStateChanged" >';
  echo '          var callBack=function(){loadContent("../view/diary.php","detailDiv","diaryForm");};';
  echo '          saveDataToSession("diaryHideResponsible",this.value,true,callBack);';
  echo '        </script>';
  echo '      </div>';
  echo '    </td>';
  echo '    <td style="padding-left:5px;" class="checkboxLabel"><span onclick="invertSwitchValue(\'diaryHideResponsible\');">'.pq_ucfirst(i18n("labelKanbanHideResponsible")).'</span></td>';
  echo '  </tr>';
  echo '  <tr>';
  echo '    <td style="padding-top:2px;">';
  echo '      <div id="diaryHidePriority" name="diaryHidePriority" class="colorSwitch" data-dojo-type="dojox/mobile/Switch" '.(($hidePriority)?'value="on"':'value="off"').' leftLabel="" rightLabel="" style="width:25px;">';
  echo '        <script type="dojo/method" event="onStateChanged" >';
  echo '          var callBack=function(){loadContent("../view/diary.php","detailDiv","diaryForm");};';
  echo '          saveDataToSession("diaryHidePriority",this.value,true,callBack);';
  echo '        </script>';
  echo '      </div>';
  echo '    </td>';
  echo '    <td style="padding-left:5px;" class="checkboxLabel"><span onclick="invertSwitchValue(\'diaryHidePriority\');">'.pq_ucfirst(i18n("labelKanbanHidePriority")).'</span></td>';
  echo '  </tr>';
  echo '  <tr>';
  echo '    <td style="padding-top:2px;">';
  echo '      <div id="diaryHideType" name="diaryHideType" class="colorSwitch" data-dojo-type="dojox/mobile/Switch" '.(($hidedeType)?'value="on"':'value="off"').' leftLabel="" rightLabel="" style="width:25px;">';
  echo '        <script type="dojo/method" event="onStateChanged" >';
  echo '          var callBack=function(){loadContent("../view/diary.php","detailDiv","diaryForm");};';
  echo '          saveDataToSession("diaryHideType",this.value,true,callBack);';
  echo '        </script>';
  echo '      </div>';
  echo '    </td>';
  echo '    <td style="padding-left:5px;" class="checkboxLabel"><span onclick="invertSwitchValue(\'diaryHideType\');">'.pq_ucfirst(i18n("labelKanbanHideType")).'</span></td>';
  echo '  </tr>';
  echo '  <tr>';
  echo '    <td style="padding-top:2px;">';
  echo '      <div id="diaryHideColorTitle" name="diaryHideColorTitle" class="colorSwitch" data-dojo-type="dojox/mobile/Switch" '.(($hideColorTitle)?'value="on"':'value="off"').' leftLabel="" rightLabel="" style="width:25px;">';
  echo '        <script type="dojo/method" event="onStateChanged" >';
  echo '          var callBack=function(){loadContent("../view/diary.php","detailDiv","diaryForm");};';
  echo '          saveDataToSession("diaryHideColorTitle",this.value,true,callBack);';
  echo '        </script>';
  echo '      </div>';
  echo '    </td>';
  echo '      <td colspan="2" style="padding-left:5px;"><span class="checkboxLabel" onclick="invertSwitchValue(\'diaryHideColorTitle\');">'.pq_ucfirst(i18n("labelKanbanHideColorTitle")).'</span>';
  echo '        <select id="diaryModeColorTitle" name="diaryModeColorTitle" class="comboButton" dojoType="dijit.form.FilteringSelect" style="width:75px;" value="'.$modeColorTitle.'">';
  $arrOpt=array(
      "noColor"=>" ",
      "colorProject"=>'Replan',
      "colorItem"=>'colElement',
      "colorType"=>'colType',
      "colorPriority"=>'colPriority');
  foreach ($arrOpt as $key=>$val){
    if ($key == 'noColor') {
      $label = '&nbsp;';
    } else {
      $label = ucfirst(i18n($val));
    }
    echo '        <option value="'.$key.'">'.$label.'</option>';
  }
  echo '        <script type="dojo/method" event="onChange" >';
  echo '          var callBack=function(){loadContent("../view/diary.php","detailDiv","diaryForm");};';
  echo '          saveDataToSession("diaryModeColorTitle",this.value,true,callBack);';
  echo '          if (this.value == "noColor") {';
  echo '            dijit.byId("diaryHideColorTitle").set("value", "off");';
  echo '          } else {';
  echo '            dijit.byId("diaryHideColorTitle").set("value", "on");';
  echo '          }';
  echo '        </script>';
  echo '        </select>';
  echo '      </td>';
  echo '  </tr>';
  echo '</table>';
  echo '    </td>';
  echo '  </tr>';
  echo '  <tr>';
  echo '    <td style="vertical-align:top;">';
  echo '<table style="width:440px;margin:5px 15px 0px 5px;display:inline-block;">';
  echo '  <tr>';
  echo '    <td style="width:40px;"><div class="iconDisplayOnKanbanManagement iconSize32 imageColorNewGuiNoSelection" style="border:0"></div></td>';
  echo '    <td class="dependencyHeader planningDialogTitle" style="width:400px;text-align:left;padding-left: 5px;">'.i18n('displayOnDiaryManagement').'</td>';
  echo '  </tr>';
  echo '  <tr>';
  echo '    <td colspan="2">';
  echo '      <table style="width:100%;text-align:center;margin-top: 5px;">';
  echo '        <tr>';
  echo '          <td style="width:80px;text-align:center;vertical-align:top;">';
  echo '          <div dojoType="dijit.form.DropDownButton" id="addDiaryItemButton" jsId="addDiaryItemButton" name="addDiaryItemButton" class="noBorder"
                            showlabel="false" iconClass="iconAdd iconSize22 imageColorNewGui" title="'.i18n('comboNewButton').'">';
  echo '            <div dojoType="dijit.TooltipDialog" class="white" style="width:200px;height:100%;">';
  echo '              <input type="hidden" id="objectClass" name="objectClass" value="" />'; 
  echo '              <input type="hidden" id="objectId" name="objectId" value="" />';
  echo '              <div style="font-weight:bold; height:25px;text-align:center">'.i18n('comboNewButton').'</div>';
  $arrayItems=array('Action','Delivery','Meeting');
  foreach($arrayItems as $item) {
    $canCreate=securityGetAccessRightYesNo('menu' . $item,'create');
    if ($canCreate=='YES') {
      if (! securityCheckDisplayMenu(null,$item) ) {
        $canCreate='NO';
      }
    }
  if ($canCreate=='YES') {
  echo '                <div class="newGuiIconText" style="vertical-align:top;cursor:pointer;margin-top:5px;height:22px;" onClick="addDiaryItem(\''.$item.'\');">';
  echo '                  <table width:"100%" >';
  echo '                    <tr style="height:22px">';
  echo '                      <td style="vertical-align:top; width: 30px;padding-left:5px">'.formatIconNewGui($item, 22, null, false).'</td>';    
  echo '                      <td style="vertical-align:top;padding-top:2px;">'.i18n($item).'</td>';
  echo '                    </tr>';
  echo '                  </table>';   
  echo '                </div>';
    } 
  }
  echo '              </div>';
  echo '          </div>';
  echo '          </td>';
  if (Parameter::getGlobalParameter('filterByStatus') == 'YES') {
  echo '          <td style="width:75px;text-align:center;vertical-align:top;">';
  echo '            <button title="'.i18n('filterByStatus').'" dojoType="dijit.form.Button" id="iconStatusButton" name="iconStatusButton"';
  echo '              iconClass="dijitButtonIcon dijitButtonIconStatusChange imageColorNewGui" class="detailButton" showLabel="false">';
  echo '                <script type="dojo/connect" event="onClick" args="evt">';
  echo '                  protectDblClick(this);';
  echo '                  if (dijit.byId("barFilterByStatus").domNode.style.display == "none") {';
  echo '                    dijit.byId("barFilterByStatus").domNode.style.display = "flex";';
  echo '                  } else {';
  echo '                    dijit.byId("barFilterByStatus").domNode.style.display = "none";';
  echo '                  }';
  echo '                  var callBack=function(){loadContent("../view/diary.php","detailDiv","diaryForm");};';
  echo '                  saveDataToSession("displayByStatusList_Diary", dijit.byId("barFilterByStatus").domNode.style.display, true,callBack);';
  echo '                </script>';
  echo '            </button>';
  echo '          </td>';
  }
  echo '          <td style="width:80px;text-align:center;vertical-align:top;">';
  echo '            <div dojoType="dijit.form.DropDownButton" id="listItemsSelector" jsId="listItemsSelector" name="listItemsSelector" showlabel="false"';
  echo '              class="noBorder comboButton" iconClass="iconGlobalView iconSize22 imageColorNewGui" title="'.i18n('itemSelector').'">';
  echo '                <div dojoType="dijit.TooltipDialog" class="white" id="listItemsSelectorDialog" style="position: absolute; top: 50px; right: 40%">';
  echo '                  <script type="dojo/connect" event="onShow" args="evt">';
  echo '                    oldSelectedItems=dijit.byId("diarySelectItems").get("value");';
  echo '                  </script>';
  echo '                  <div style="text-align: center; position: relative;">';
  echo '                    <div style="position: absolute; top: 34px; right: 42px;"></div>';
  echo '                  </div>';
  echo '                  <div style="height: 5px; border-bottom: 1px solid #AAAAAA"></div>';
  $itemsToDisplay=Parameter::getUserParameter('diarySelectedItems');
  echo '                  <div><select dojoType="dojox.form.CheckedMultiSelect" multiple="true" style="border: 1px solid #A0A0A0; width: initial; height: 120px;"';
  echo '                          id="diarySelectItems" name="diarySelectItems" onChange="diarySelectItems(this.value);" value="'.$itemsToDisplay.'">';
  $arrOpt=array("All"=>"activityStreamAllItems",
                "Action"=>'Action',
                "Ticket"=>'Ticket',
                "MilestonePlanningElement"=>'Milestone',
                "Meeting"=>'Meeting',
                "Activity"=>"Activity",
                "Delivery"=>"Delivery");
  foreach ($arrOpt as $key=>$val){
    echo '                        <option value="'.$key.'">'.htmlencode(i18n($val)).'</option>';
  }
  echo '                  </select></div>';
  echo '                  <div style="height: 5px; border-top: 1px solid #AAAAAA"></div>';
  echo '                  <div style="text-align: center; position: relative;">';
  echo '                    <button title="" dojoType="dijit.form.Button" class="mediumTextButton" id="" name="" showLabel="true">'.i18n('buttonOK');
  echo '                      <script type="dojo/connect" event="onClick" args="evt">';
  echo '                        dijit.byId("listItemsSelector").closeDropDown();';
  echo '                      </script>';
  echo '                    </button>';
  echo '                    <div style="position: absolute; bottom: 33px; right: 42px;"></div>';
  echo '                  </div>';
  echo '                </div>';
  echo '              </div>';
  echo '            </td>';
  echo '        </tr>';
  echo '        <tr>';
  if ($canCreate=='YES') {
  echo '          <td style="font-size:80%;color:#a0a0a0;vertical-align: top;">'.i18n('contextMenuButtonNew').'</td>';
  }
  if (Parameter::getGlobalParameter('filterByStatus') == 'YES') {
  echo '          <td style="font-size:80%;color:#a0a0a0;vertical-align: top;">'.i18n('filterByStatus').'</td>';
  }
  echo '          <td style="font-size:80%;color:#a0a0a0;vertical-align: top;">'.i18n('listTodayItems').'</td>';
  echo '        </tr>';
  echo '      </table>';
  echo '    </td>';
  echo '  </tr>';
  echo '</table>';
  echo '    </td>';
  echo '  </tr>';
  echo '</table>';
}
?>