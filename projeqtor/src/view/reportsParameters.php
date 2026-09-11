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
scriptLog('   ->/view/reportsList.php');
?>
<div style="height:100%;width:100%;overflow-x:hidden; overflow-y:auto" >
<form dojoType="dijit.form.Form" id='reportForm' name='reportForm' onSubmit="return false;">
<table><tr><td>
<table style="width:100%;min-width:292px;">
  <tr>
    <td>&nbsp;</td>
    <td>&nbsp;</td>
  </tr>
<?php 
$user=getSessionUser();
$autoSendReportAccess = securityCheckDisplayMenu(null, 'AutoSendReport');
$currentWeek=weekNumber(date('Y-m-d'));
if (pq_strlen($currentWeek)==1) {
  $currentWeek='0' . $currentWeek;
}
$currentYear=pq_strftime("%Y") ;
$currentMonth=pq_strftime("%m") ;
if (isset($rep)) {
  $idReport = $rep->id;
}
if (isset($_REQUEST['idReport'])) {
  $idReport=$_REQUEST['idReport'];
}
if (!$idReport) {
  exit;
}
$idRow = Parameter::getUserParameter('idFavoriteRow');
$limitToActiveProjects=true;
$showIdle=false;
if (sessionValueExists('projectSelectorShowIdle') and getSessionValue('projectSelectorShowIdle')==1) {
  $limitToActiveProjects=false;
  $showIdle=true;
}
$report=new Report($idReport);
$projectSelected=null;
$idReportCategory=$report->idReportCategory;

if (isset($debugReport) and $debugReport) {
  echo "<div style='position:absolute;top:10px;right:10px' >id : " . htmlEncode($report->id) . "</div>";
  echo "<div style='position:absolute;top:25px;right:10px' >name : " . htmlEncode($report->name) . "</div>";
  echo "<div style='position:absolute;top:40px;right:10px' >file : " . htmlEncode($report->file) . "</div>";
  
}
echo "<input type='hidden' id='reportFile' name='reportFile' value='" . htmlEncode($report->file) . "' />";
echo "<input type='hidden' id='reportId' name='reportId' value='" . htmlEncode($report->id) . "' />";

if(SqlList::getNameFromId('ReportCategory', $idReportCategory, false) == 'reportCategoryObjectList'){
  $idReportLayout = pq_substr($report->file, (pq_strpos($report->file, 'reportLayoutId')+15));
  $reportLayoutObjectClass=SqlList::getFieldFromId('ReportLayout', $idReportLayout, 'objectClass');
  if($reportLayoutObjectClass){
    if(property_exists($reportLayoutObjectClass, 'idProject')){
      $reportParam = new ReportParameter();
      $reportParam->idReport = $idReport;
      $reportParam->name = 'idProject';
      $reportParam->paramType = 'projectList';
      $reportParam->sortOrder = 10;
      $reportParam->defaultValue = 'currentProject';
      $listParam[]=$reportParam;
    }
    if(property_exists($reportLayoutObjectClass, 'idResource')){
      $reportParam = new ReportParameter();
      $reportParam->idReport = $idReport;
      $reportParam->name = 'responsible';
      $reportParam->paramType = 'resourceList';
      $reportParam->sortOrder = 10;
      $reportParam->defaultValue = 'currentResource';
      $listParam[]=$reportParam;
    }
    if(property_exists($reportLayoutObjectClass, 'idOrganization')){
      $reportParam = new ReportParameter();
      $reportParam->idReport = $idReport;
      $reportParam->name = 'idOrganization';
      $reportParam->paramType = 'organizationList';
      $reportParam->sortOrder = 10;
      $reportParam->defaultValue = 'currentOrganization';
      $listParam[]=$reportParam;
    }
    if(property_exists($reportLayoutObjectClass, 'idTeam')){
      $reportParam = new ReportParameter();
      $reportParam->idReport = $idReport;
      $reportParam->name = 'idTeam';
      $reportParam->paramType = 'teamList';
      $reportParam->sortOrder = 10;
      $listParam[]=$reportParam;
    }
    if(property_exists($reportLayoutObjectClass, SqlElement::getTypeName($reportLayoutObjectClass))){
      $reportParam = new ReportParameter();
      $reportParam->idReport = $idReport;
      $reportParam->name = SqlElement::getTypeName($reportLayoutObjectClass);
      $reportParam->paramType = SqlElement::getTypeClassName($reportLayoutObjectClass).'List';
      $reportParam->sortOrder = 10;
      $listParam[]=$reportParam;
    }
  }
}else{
  $param=new ReportParameter();
  $crit=array('idReport'=>$idReport);
  $listParam=$param->getSqlElementsFromCriteria($crit,false,null,'sortOrder');
}
if (count($listParam)==0) echo '<tr><td class="label"><label>&nbsp;</label></td><td><div style="width:70px;">&nbsp;</div></td></tr>';
$isPeriodTypeDate=false;
foreach ($listParam as $param) {
  $required=$param->required;
  if ($param->paramType=='week') {
    $defaultWeek='';
    $defaultYear='';
    if ($param->defaultValue=='currentWeek') {
      $defaultWeek=$currentWeek;
      $defaultYear=$currentYear;
    } else if ($param->defaultValue=='currentYear') {
      $defaultYear=$currentYear;
    }
    ?>
    <input type="hidden" id='periodValue' name='periodValue' value='<?php echo $currentYear . $currentWeek;?>' />
    <input type="hidden" id='periodType' name='periodType' value='week'/>
    <tr>
    <td class="label"><label><?php echo i18n("year");?>&nbsp;<?php if (!isNewGui()) echo ':&nbsp;';?></label></td>
    <td><div style="width:70px; text-align: center; color: #000000;<?php if($required)echo "border-left:3px solid red;" ;?>" 
      dojoType="dijit.form.NumberSpinner" 
      constraints="{min:2000,max:2100,places:0,pattern:'###0'}"
      intermediateChanges="true"
      maxlength="4"
      <?php if($required)echo 'required' ;?>
      value="<?php echo $defaultYear;?>" smallDelta="1"
      id="yearSpinner" name="yearSpinner" >
      <script type="dojo/method" event="onChange">
        var year=dijit.byId('yearSpinner').get('value');
        var week=dijit.byId('weekSpinner').get('value') + '';
        week=(week.length==1)?'0'+week:week;
        dojo.byId('periodValue').value='' + year + week;
      </script>
    </div></td>
    </tr>
    <tr>
    <td class="label"><label><?php echo i18n("week");?>&nbsp;<?php if (!isNewGui()) echo ':&nbsp;';?></label></td>
    <td><div style="width:55px; text-align: center; color: #000000;<?php if($required)echo "border-left:3px solid red;" ;?>" 
       dojoType="dijit.form.NumberSpinner" 
       <?php if($required)echo "required" ;?>
       constraints="{min:0,max:55,places:0,pattern:'00'}"
       intermediateChanges="true"
       maxlength="2"
       value="<?php echo $defaultWeek;?>" smallDelta="1"
       id="weekSpinner" name="weekSpinner" >
       <script type="dojo/method" event="onChange" >
         var year=dijit.byId('yearSpinner').get('value');
         if (this.value>getWeek(31, 12, year) && this.value>getWeek(28, 12, year)) {
          dijit.byId('weekSpinner').set('value',1);
          year=parseInt(year)+1;
          dijit.byId('yearSpinner').set('value',year);
         } else if (this.value==0) {
          year=parseInt(year)-1;          
          dijit.byId('weekSpinner').set('value',Math.max(getWeek(31, 12, year),getWeek(28, 12, year)));
          dijit.byId('yearSpinner').set('value',year);
         }
         var week=dijit.byId('weekSpinner').get('value') + '';
         week=(week.length==1)?'0'+week:week;
         dojo.byId('periodValue').value='' + year + week;
       </script>
     </div></td>
     </tr>
<?php 
  } else if ($param->paramType=='month') {
    $defaultMonth='';
    $defaultYear='';
    if ($param->defaultValue=='currentMonth') {
      $defaultMonth=$currentMonth;
      $defaultYear=$currentYear;
    } else if ($param->defaultValue=='currentYear') {
    	$defaultYear=$currentYear;
    }
?>
    <input type="hidden" id='periodValue' name='periodValue' value='<?php echo $currentYear . $currentMonth;?>' />
    <input type="hidden" id='periodType' name='periodType' value='month'/>
    <tr>
    <td class="label"><label><?php echo i18n("year");?>&nbsp;<?php if (!isNewGui()) echo ':&nbsp;';?></label></td>
    <td><div style="width:70px; text-align: center; color: #000000;<?php if($required)echo "border-left:3px solid red;" ;?>" 
      dojoType="dijit.form.NumberSpinner" 
      <?php  if($required)echo "required" ; ?>
      constraints="{min:2000,max:2100,places:0,pattern:'###0'}"
      intermediateChanges="true"
      maxlength="4"
      value="<?php echo $defaultYear;?>" smallDelta="1"
      id="yearSpinner" name="yearSpinner" >
      <script type="dojo/method" event="onChange">
        var year=dijit.byId('yearSpinner').get('value');
        var month=dijit.byId('monthSpinner').get('value') + '';
        month=(month.length==1)?'0'+month:month;
        dojo.byId('periodValue').value='' + year + month;
      </script>
    </div>
    <?php if (!$defaultYear) {?>
    <div class="roundedVisibleButton roundedButton generalColClass" 
      style="text-align:center;float:right;margin-right:0px; width:50%;<?php echo (isNewGui())?'padding:3px 5px;position:relative;top:4px;':'padding:0px 5px;height:16px;';?>"
      onclick="dijit.byId('yearSpinner').set('value','<?php echo date('Y');?>');">
      <?php echo i18n('setToCurrentYear');?>
    </div>
    <?php }?>
    </td>
    </tr>
    <tr>
    <td class="label"><label><?php echo i18n("month");?>&nbsp;<?php if (!isNewGui()) echo ':&nbsp;';?></label></td>
    <td><div style="width:55px; text-align: center; color: #000000;<?php if($required)echo "border-left:3px solid red;" ;?>" 
       dojoType="dijit.form.NumberSpinner" 
       constraints="{min:0,max:13,places:0,pattern:'00'}"
       intermediateChanges="true"
       <?php if($required)echo "required" ;?>
       maxlength="2"
       value="<?php echo $defaultMonth;?>" smallDelta="1"
       id="monthSpinner" name="monthSpinner" >
       <script type="dojo/method" event="onChange" >
        var year=dijit.byId('yearSpinner').get('value');
        if (this.value==13) {
          dijit.byId('monthSpinner').set('value','01');
          year=parseInt(year)+1;
          dijit.byId('yearSpinner').set('value',year);
        } else if (this.value==0) {
          dijit.byId('monthSpinner').set('value','12');
          year=parseInt(year)-1;
          dijit.byId('yearSpinner').set('value',year);
        }
        var month=dijit.byId('monthSpinner').get('value')+'';
        month=(month.length==1)?'0'+month:month;
        //dijit.byId('monthSpinner').set('value',month);
        dojo.byId('periodValue').value='' + year + month;
       </script>
     </div>
     <?php if (!$defaultMonth) {?>
    <div class="roundedVisibleButton roundedButton generalColClass" 
      style="text-align:center;float:right;margin-right:0px; width:50%;<?php echo (isNewGui())?'padding:3px 5px;position:relative;top:4px;':'padding:0px 5px;height:16px;';?>" 
      onclick="dijit.byId('yearSpinner').set('value','<?php echo date('Y');?>');dijit.byId('monthSpinner').set('value','<?php echo date('m');?>');">
      <?php echo i18n('setToCurrentMonth');?>
    </div>
    <?php }?>
     </td>
     </tr> 
<?php    
  } else if ($param->paramType=='year') {
    $defaultYear='';
    if ($param->defaultValue=='currentYear') {
      $defaultYear=$currentYear;
    }
?>
    <input type="hidden" id='periodValue' name='periodValue' value='<?php echo $currentYear;?>' />
    <input type="hidden" id='periodType' name='periodType' value='year'/>
    <tr>
    <td class="label"><label><?php echo i18n("year");?>&nbsp;<?php if (!isNewGui()) echo ':&nbsp;';?></label></td>
    <td><div style="width:70px; text-align: center; color: #000000;<?php if($required)echo "border-left:3px solid red;" ;?>" 
      dojoType="dijit.form.NumberSpinner" 
      <?php if($required)echo "required" ;?>
      constraints="{min:2000,max:2100,places:0,pattern:'###0'}"
      intermediateChanges="true"
      maxlength="4"
      value="<?php echo $defaultYear;?>" smallDelta="1"
      id="yearSpinner" name="yearSpinner" >
      <script type="dojo/method" event="onChange">
        var year=dijit.byId('yearSpinner').get('value');
        dojo.byId('periodValue').value='' + year;
      </script>
    </div></td>
    </tr>
    <?php //ADD qCazelles - Report fiscal year - Ticket #128 
    if (Parameter::getGlobalParameter("reportStartMonth")!='NO' and $param->name!='yearNoMonthStart') {
    ?>
    <tr>
    <td class="label"><label><?php echo i18n("startMonth");?>&nbsp;<?php if (!isNewGui()) echo ':&nbsp;';?></label></td>
    <td><div style="width:55px; text-align: center; color: #000000;<?php if($required)echo "border-left:3px solid red;" ;?>" 
       dojoType="dijit.form.NumberSpinner" 
       constraints="{min:1,max:12,places:0,pattern:'00'}"
       intermediateChanges="true"
       <?php if($required)echo "required" ;?>
       maxlength="2"
       value="01" smallDelta="1"
       id="monthSpinner" name="monthSpinner" >
       <script type="dojo/method" event="onChange" >
            if(dojo.byId('NbMonthSpinner')){
              var spinnerNbMonth = dijit.byId('NbMonthSpinner');
                for (var i = 1; i < 12; i++) {
                  if (this.value == i) {
                    var putValue = 13 - i;
                    spinnerNbMonth.set('value', putValue);
                    spinnerNbMonth.constraints.max = putValue;
                  } else if (this.value == 12) {
                    spinnerNbMonth.set('value', 1);
                    spinnerNbMonth.constraints.max = 1;
                  }
                }
            }
       </script>
     </div>
     </td>
     </tr>
     <?php } 
     else {
       echo '<input type="hidden" name="monthSpinner" id="monthSpinner" value="01" />'; 
     }
     //END ADD qCazelles - Report fiscal year - Ticket #128 ?>
<?php    
  } else if ($param->paramType=="nbMonth"){
    ?>
        <!-- START TICKET #383 - F.KARA : Add a number of months -->
      <tr>
          <td class="label"><label><?php echo i18n("NbMonth");?>&nbsp;<?php if (!isNewGui()) echo ':&nbsp;';?></label></td>
          <td><div style="width:55px; text-align: center; color: #000000;<?php if($required)echo "border-left:3px solid red;" ;?>"
                   dojoType="dijit.form.NumberSpinner"
                   constraints="{min:1,max:12,places:0,pattern:'00'}"
                  <?php if($required)echo "required" ;?>
                   intermediateChanges="true"
                   maxlength="2"
                   value="12" smallDelta="1"
                   id="NbMonthSpinner" name="NbMonthSpinner" >
                  <script type="dojo/method" event="onChange" >
                    </script>
              </div>
          </td>
      </tr>
        <!-- END TICKET #383 - F.KARA : Add a number of months -->
 <?php 
  }else if ($param->paramType=='date') {
    $defaultDate='';
    if ($param->defaultValue=='today') {
      $defaultDate=date('Y-m-d');
    }else if($param->defaultValue=='lastMonth'){
      //$defaultDate=date('Y-m-d',strtotime('-1 month'));
      //$defaultDate=date('Y-m-d',strtotime('-1 month +1 day'));
      $defaultDate=date('Y-m-01');
    }else if($param->defaultValue=='nextMonth'){
        //$defaultDate=date('Y-m-d',strtotime('-1 month'));
        //$defaultDate=date('Y-m-d',strtotime('-1 month +1 day'));
        $defaultDate=date('Y-m-01').lastDayOfMonth(intval(date('m')),intval(date('Y')));
    }else if($param->defaultValue=='nextElevenMonths'){
      $defaultDate=date('Y-m-01', strtotime('+11 months'));
    } else if ($param->defaultValue=='firstOpenDayOfYear') {
      $year=intval(date('Y'));
      $day=firstDayofWeek(01,$year);
      $defaultDate=date('Y-m-d',$day);
      while (! isOpenDay($defaultDate)) {$defaultDate=addDaysToDate($defaultDate, 1);}
    } else if ($param->defaultValue=='lastDayOfPreviousWeek') {
      $week=intval(weekNumber(date('Y-m-d')))-1;
      $year=intval(date('Y'));
      $day=lastDayofWeek($week,$year);
      $defaultDate=$day;
    } else if ($param->defaultValue) {
      $defaultDate=$param->defaultValue; 
    }
?>
    <tr>
    <td class="label"><label><?php echo i18n('col' . pq_ucfirst($param->name));?>&nbsp;<?php if (!isNewGui()) echo ':&nbsp;';?></label></td>
    <td>
     <?php if(!$isPeriodTypeDate){?>
       <input type="hidden" id='periodType' name='periodType' value='date'/>
    <?php }?>
    <div style="width:100px; text-align: center; color: #000000;<?php if($required)echo "border-left:3px solid red;" ;?>" 
      dojoType="dijit.form.DateTextBox" 
     <?php if($required) echo "required" ;?>
      <?php if (sessionValueExists('browserLocaleDateFormatJs')) {
				echo ' constraints="{datePattern:\''.getSessionValue('browserLocaleDateFormatJs').'\'}" ';
      }?>
      invalidMessage="<?php echo i18n('messageInvalidDate');?>" 
      value="<?php echo $defaultDate;?>"
      hasDownArrow="true"
      id="<?php echo $param->name;?>" name="<?php echo $param->name;?>" >
    </div></td>
    </tr>
<?php    
  } else if ($param->paramType=='periodScale') {
    $defaultValue=$param->defaultValue;
?>
    <tr>
    <td class="label"><label><?php echo i18n('col' . pq_ucfirst($param->name));?>&nbsp;<?php if (!isNewGui()) echo ':&nbsp;';?></label></td>
    <td>
    <select dojoType="dijit.form.FilteringSelect" class="input <?php if($required)echo "required" ;?>" 
     <?php if($required)echo "required" ;?>
    <?php echo autoOpenFilteringSelect();?>
       style="width: 200px;"
       id="<?php echo $param->name;?>" name="<?php echo $param->name;?>"
     >
       <option value="day" <?php echo ($defaultValue=='day')?'SELECTED':'';?> ><?php echo i18n('day'); ?> </option>
       <option value="week" <?php echo ($defaultValue=='week')?'SELECTED':'';?> ><?php echo i18n('week'); ?> </option>
       <option value="month" <?php echo ($defaultValue=='month')?'SELECTED':'';?> ><?php echo i18n('month'); ?> </option>
       <option value="quarter" <?php echo ($defaultValue=='quarter')?'SELECTED':'';?> ><?php echo i18n('quarter'); ?> </option>
     </select>
    </td>
    </tr>
<?php  
  //gautier #2977  
  } else if ($param->paramType=='element') {
    $defaultValue=$param->defaultValue;
?>
    <tr>
    <td class="label"><label><?php echo i18n('col' . pq_ucfirst($param->name));?>&nbsp;<?php if (!isNewGui()) echo ':&nbsp;';?></label></td>
    <td>
    <select dojoType="dijit.form.FilteringSelect" class="input  <?php if($required)echo "required" ;?>" 
    <?php if($required)echo "required" ;?>
    <?php echo autoOpenFilteringSelect();?>
       style="width: 200px;"
       id="<?php echo $param->name;?>" name="<?php echo $param->name;?>"
     >
       <option value="tickets" <?php echo ($defaultValue=='tickets')?'SELECTED':'';?> ><?php echo i18n('menuTicket'); ?> </option>
       <option value="activities" <?php echo ($defaultValue=='activities')?'SELECTED':'';?> ><?php echo i18n('Activity'); ?> </option>
     </select>
    </td>
    </tr>
<?php    
  } else if ($param->paramType=='periodScaleYear') {
    $defaultValue=$param->defaultValue;
?>
    <tr>
    <td class="label"><label><?php echo i18n('col' . pq_ucfirst($param->name));?>&nbsp;<?php if (!isNewGui()) echo ':&nbsp;';?></label></td>
    <td>
    <select dojoType="dijit.form.FilteringSelect" class="input  <?php if($required)echo "required" ;?>"  
     <?php if($required)echo "required" ;?>
    <?php echo autoOpenFilteringSelect();?>
       style="width: 200px;"
       id="<?php echo $param->name;?>" name="<?php echo $param->name;?>"
     >
       <option value="year" <?php echo ($defaultValue=='quarter')?'SELECTED':'';?> ><?php echo i18n('year'); ?> </option>
       <option value="month" <?php echo ($defaultValue=='month')?'SELECTED':'';?> ><?php echo i18n('month'); ?> </option>
       <option value="week" <?php echo ($defaultValue=='month')?'SELECTED':'';?> ><?php echo i18n('week'); ?> </option>
       
     </select>
    </td>
    </tr>
<?php    
  } else if ($param->paramType=='boolean') {
    $defaultValue=($param->defaultValue=='true' or $param->defaultValue=='1')?true:false;
    $projectVal='';
    if ($param->name=='showVAT' and Parameter::getGlobalParameter('ImputOfAmountProvider') == 'TTC') {
      $defaultValue = true;
    }
     if (sessionValueExists('project')) {
      if (getSessionValue('project')!='*') {
        $projectVal=getSessionValue('project');
        if(pq_strpos($defaultValue, ",") !== false){
          $projectVal="*";
        }
      }
    }
?>
    <tr id="tr_<?php echo $param->name;?>" style="visibility:<?php echo ($param->name=='showAdminProj' and $report->id=='4' and ($projectVal=='*' or $projectVal==''))?'hidden;':'visible;';?>">
    <td class="label" ><label style="white-space:nowrap"><?php echo i18n('col'.pq_ucfirst($param->name));?>&nbsp;<?php if (!isNewGui()) echo ':&nbsp;';?></label></td>
    <td>
      <div dojoType="dijit.form.CheckBox" type="checkbox" 
         <?php 
           if($required){
                  echo "required" ;
                  echo 'class="required";';
          }
        ?>
        id="<?php echo $param->name;?>" name="<?php echo $param->name;?>"
        style="<?php if (isNewGui()) echo 'position:relative;top:4px';?>"
        <?php echo ($defaultValue)?' checked ':'';?> >
      </div>
    </td>
    </tr><?php 
  } else if ($param->paramType=='projectList') {
    $defaultValue='';
    if ($param->defaultValue=='currentProject') {
      if (sessionValueExists('project')) {
        
        if (getSessionValue('project')!='*') {
          $defaultValue=getSessionValue('project');
          if(pq_strpos($defaultValue, ",") !== false){
            $defaultValue="*";
          }
        }
      }
    } else if ($param->defaultValue) {
      $defaultValue=$param->defaultValue; 
    }
?>
    <tr>
    <td class="label"><label><?php echo i18n('col' . pq_ucfirst($param->name));?>&nbsp;<?php if (!isNewGui()) echo ':&nbsp;';?></label></td>
    <td>
      <select data-dojo-type="<?php echo (($param->multiple == 1) ? 'dojox.form.CheckedMultiSelect' : 'dijit.form.FilteringSelect') ?>" class="input <?php if($required)echo "required" ;if ($param->multiple == 1) echo "multiSelect" ;?> " 
       <?php echo ($param->multiple == 1) ? '' : 'data-dojo-props="queryExpr: \'*${0}*\', autoComplete:false"'; ?>
       <?php echo ($param->multiple == 1) ? '' : autoOpenFilteringSelect(); ?>
       <?php echo (($param->multiple == 1) ? ' style="border:0px;border-bottom:1px solid #eeeeee;width: 200px !important; height: 127px;" multiple="true"' : ' style="width:200px;"') ?>
       id="<?php echo $param->name;?>" name="<?php echo $param->name . (($param->multiple == 1) ? '[]' : '');?>"
     >    
       <?php $projObj = new Project();
             htmlDrawOptionForReference('idProject', $defaultValue,$projObj, $required,null,null,$limitToActiveProjects,false,$showIdle,false); 
             $projectSelected=$defaultValue;?>
       <script type="dojo/connect" event="onChange" args="evt">
          if(dojo.byId('reportId').value=='4'){
             if(dojo.byId('idProject').value!=''){
               dojo.byId('tr_showAdminProj').style.visibility='visible';
             }else{
               dojo.byId('tr_showAdminProj').style.visibility='hidden';
             }
          }
          if (dijit.byId('idVersion')) {
            if (dijit.byId('idProduct')) {
              var idProduct=trim(dijit.byId('idProduct').get('value'));
              if (idProduct) {
                refreshList("idVersion","idProduct", idPoduct);
              } else {
                if (trim(this.value)) {
                  refreshList("idVersion","idProject", this.value);
                } else {
                  refreshList("idVersion");
                }
              }
            } else {
              if (trim(this.value)) {
                refreshList("idVersion","idProject", this.value);
              } else {
                refreshList("idVersion");
              }
            }
          } 
          if (dijit.byId('idActivity')) {
            if (trim(this.value)) {
              refreshList("idActivity", "idProject", this.value);
            } else {
              refreshList("idActivity");
            }
          }
          if (dijit.byId('idTicket')) {
            if (trim(this.value)) {
              refreshList("idTicket", "idProject", this.value);
            } else {
              refreshList("idTicket");
            }
          }
          if (dijit.byId('idProduct')) {
            refreshList("idProduct","idProject", this.value);
          }
          if (dijit.byId('idBaselineSelect')) {
            dijit.byId('idBaselineSelect').set("value",null);
            refreshList("idBaselineSelect","idProject", this.value, null, null, true);
          }

       </script>
     </select>  
    </td>
    </tr>
<?php    
  } else if ($param->paramType=='productList') {
    $defaultValue='';
    if ($param->defaultValue) {
      $defaultValue=$param->defaultValue; 
    }
?>
    <tr>
    <td class="label"><label><?php echo i18n('col' . pq_ucfirst($param->name));?>&nbsp;<?php if (!isNewGui()) echo ':&nbsp;';?></label></td>
    <td>
    <select dojoType="dijit.form.FilteringSelect" class="input <?php if($required)echo "required" ;?>" 
    <?php if($required)echo "required" ;?>
    <?php echo autoOpenFilteringSelect();?>
       style="width: 200px;"
       id="<?php echo $param->name;?>" name="<?php echo $param->name;?>"
     >
       <?php htmlDrawOptionForReference('idProduct', $defaultValue, null, false); ?>
       <script type="dojo/connect" event="onChange" args="evt">
          var version=null;
          if (dijit.byId('idVersion')) version='idVersion';
          else if (dijit.byId('idProductVersion')) version='idProductVersion';     
          if (version) {
            if (dijit.byId('idProject')) {
              if (trim(this.value)) {
                refreshList(version,"idProduct", this.value);
              } else {
                if (trim( dijit.byId("idProject").get("value")) ) {
                  refreshList("idVersion","idProject", dijit.byId("idProject").get("value"));
                } else {
                  refreshList("idVersion");
                }
              }
            } else {
              if (trim(this.value)) {
                refreshList(version,"idProduct", this.value);
              } else {
                refreshList(version);
              }
            }
          } 
       </script>
     </select>    
    </td>
    </tr>
<?php 
  } else if ($param->paramType=='userList') {
    $defaultValue='';
    if ($param->defaultValue=='currentUser') {
      if (sessionUserExists()) {
        $defaultValue=$user->id;
      }
    } else if ($param->defaultValue) {
      $defaultValue=$param->defaultValue; 
    }
?>
    <tr>
    <td class="label"><label><?php echo i18n('col' . pq_ucfirst($param->name));?>&nbsp;<?php if (!isNewGui()) echo ':&nbsp;';?></label></td>
    <td>
    <select dojoType="dijit.form.FilteringSelect" class="input <?php if($required)echo "required" ;?>" 
    <?php if($required)echo "required" ;?>
    <?php echo autoOpenFilteringSelect();?>
       style="width: 200px;"
       id="<?php echo $param->name;?>" name="<?php echo $param->name;?>"
     >
       <?php htmlDrawOptionForReference('idUser', $defaultValue, null, false); ?>
     </select>    
    </td>
    </tr>
<?php
  } else if ($param->paramType=='versionList') {
    $defaultValue=$param->defaultValue;
    ?>
  <tr>
    <td class="label"><label><?php echo i18n('col' . pq_ucfirst($param->name));?>&nbsp;<?php if (!isNewGui()) echo ':&nbsp;';?></label></td>
    <td>
      <select dojoType="dijit.form.FilteringSelect" class="input <?php if($required)echo "required" ;?>"
      <?php if($required)echo "required" ;?>
      <?php echo autoOpenFilteringSelect();?>
              style="width: 200px;"
              id="<?php echo $param->name;?>" name="<?php echo $param->name;?>"
        >
        <?php htmlDrawOptionForReference('idVersion', $defaultValue, null, false); ?>
      </select>
    </td>
  </tr>
<?php
  } else if ($param->paramType=='testSessionList') {
    $defaultValue=$param->defaultValue;
    ?>
  <tr>
    <td class="label"><label><?php echo i18n('col' . pq_ucfirst($param->name));?>&nbsp;<?php if (!isNewGui()) echo ':&nbsp;';?></label></td>
    <td>
      <select dojoType="dijit.form.FilteringSelect" class="input <?php if($required)echo "required" ;?>"
      <?php if($required)echo "required" ;?>
      <?php echo autoOpenFilteringSelect();?>
              style="width: 200px;"
              id="<?php echo $param->name;?>" name="<?php echo $param->name;?>"
        >
        <?php htmlDrawOptionForReference('idTestSession', $defaultValue, null, false); ?>
      </select>
    </td>
  </tr>  
<?php
  } else if ($param->paramType=='resourceList') {
    $canChangeResource=false;
    if ($param->name=='resource' or $param->name=='idResource' or $param->name=='idResourceAll') {
      $crit=array('idProfile'=>$user->idProfile, 'scope'=>'reportResourceAll');
      $habil=SqlElement::getSingleSqlElementFromCriteria('HabilitationOther', $crit);
      if ($habil and $habil->id and $habil->rightAccess=='1') {
        $canChangeResource=true;
      }
    } else {
      $canChangeResource=true;
    }
    $defaultValue=null;
    if ($param->defaultValue=='currentResource' or (!$param->defaultValue and !$canChangeResource) ) {
      if ($user->isResource) {
        $defaultValue=$user->id;
      }
    } else if ($param->defaultValue) {
      $defaultValue=$param->defaultValue; 
    }
?>
    <tr>
    <td class="label"><label><?php echo i18n('col' . pq_ucfirst($param->name));?>&nbsp;<?php if (!isNewGui()) echo ':&nbsp;';?></label></td>
    <td>
    <?php if (! $canChangeResource) $param->multiple=0;?>
    <select dojoType="<?php echo (($param->multiple == 1) ? 'dojox.form.CheckedMultiSelect' : 'dijit.form.FilteringSelect') ?>" class="input <?php if($required)echo "required" ;?>" 
    <?php if($required)echo "required" ;?>
    <?php echo ($param->multiple == 1) ? '' : autoOpenFilteringSelect(); ?>
    <?php echo (($param->multiple == 1) ? ' style="border:0px;border-bottom:1px solid #eeeeee;width: 200px !important; height: 127px;" multiple="true"' : ' style="width:200px;"') ?>
       style="width: 200px;"
       <?php if (! $canChangeResource) echo ' readonly ';?>
       id="<?php echo $param->name;?>" name="<?php echo $param->name . (($param->multiple == 1) ? '[]' : '');?>"
     >
     <?php if ($param->multiple == 1) { ?>
     <option value="SA"><?php echo i18n('buttonSelectAll');?></option>
     
     <script type="dojo/method" event="onClick" args="evt">
      var widget=dojo.byId('widget_<?php echo $param->name;?>');
      selected=evt.srcElement;
      selectedId=selected.id;
      firstItem=widget.children[1].children[1].firstChild.firstChild.firstChild;
      firstItemId=firstItem.id;
      var optionsMultiSelect = this.options;
      if (selectedId==firstItemId) {
        for (var i = 1; i< optionsMultiSelect.length; i++) {
          if (optionsMultiSelect[0].selected) {
            optionsMultiSelect[i].selected = true;
          } else {
            optionsMultiSelect[i].selected = false;
          }
        }
      }
     </script>
     <?php } ?>
       <?php 
       $projectSelectorShowIdle = (getSessionValue('projectSelectorShowIdle') == '1')?true:false;
       $specific='imputation';
       if ($param->name=='idResourceAll' and $canChangeResource) $includePool=true;
       if ($param->multiple!=1 and $canChangeResource) $drawBlankOption=true;
       if($param->name=='resourceTeam')$onlyResourceTeam=true;
       include '../tool/drawResourceListForSpecificAccess.php';
       /*htmlDrawOptionForReference('idResourceAll', $defaultValue, null, false, null,null,true, true, $projectSelectorShowIdle);*/?> 
     </select>   
    </td>
    </tr>
<?php 
  } else if ($param->paramType=='requestorList') {
    $defaultValue='';
?>
    <tr>
    <td class="label"><label><?php echo i18n('col' . pq_ucfirst($param->name));?>&nbsp;<?php if (!isNewGui()) echo ':&nbsp;';?></label></td>
    <td>
    <select dojoType="dijit.form.FilteringSelect" class="input <?php if($required)echo "required" ;?>" 
    <?php if($required)echo "required" ;?>
    <?php echo autoOpenFilteringSelect();?>
       style="width: 200px;"
       id="<?php echo $param->name;?>" name="<?php echo $param->name;?>"
     >
       <?php $report= new Report($param->idReport);
       $reportCategory= new ReportCategory($report->idReportCategory);
       if ($reportCategory->name=='reportCategoryTicket') htmlDrawOptionForReference('idAffectable', $defaultValue, null, false);
       else htmlDrawOptionForReference('idContact', $defaultValue, null, false); ?>
     </select>    
    </td>
    </tr>    
<?php 
  } else if ($param->paramType=='milestoneTypeList') {
    $defaultValue='';
    $saveShowMilestoneObj=SqlElement::getSingleSqlElementFromCriteria('Parameter',array('idUser'=>$user->id,'idProject'=>null,'parameterCode'=>'planningShowMilestone'));
    $defaultValue=$saveShowMilestoneObj->parameterValue;
    if (! is_numeric($defaultValue)) $defaultValue=null;
?>
    <tr>
    <td class="label"><label><?php echo i18n('col' . pq_ucfirst($param->name));?>&nbsp;<?php if (!isNewGui()) echo ':&nbsp;';?></label></td>
    <td>
    <select dojoType="dijit.form.FilteringSelect" class="input <?php if($required)echo "required" ;?>" 
    <?php if($required)echo "required" ;?>
    <?php echo autoOpenFilteringSelect();?>
      style="width: 150px;"
      name="<?php echo $param->name;?>" id="<?php echo $param->name;?>">
      <?php if ($param->name=='listShowMilestone') {?>
      <option value=" " <?php echo (! $defaultValue)?'SELECTED':'';?>><?php echo i18n("paramNone");?></option>                            
      <?php htmlDrawOptionForReference('idMilestoneType', $defaultValue,null, true);?>
      <option value="all" <?php echo ($defaultValue=='all')?'SELECTED':'';?>><?php echo i18n("all");?></option>
      <?php } else {
            htmlDrawOptionForReference('idMilestoneType', $defaultValue,null, false);
       }?>
    </select>
    </td></tr>
<?php 
  } else if ($param->paramType=='showDetail') {
    $defaultValue='';
?>
    <tr >
    <td class="label"><label><?php echo i18n('col' . pq_ucfirst($param->name));?>&nbsp;<?php if (!isNewGui()) echo ':&nbsp;';?></label></td>
    <td ">
      <input dojoType="dijit.form.CheckBox" id="<?php echo $param->name;?>" name="<?php echo $param->name;?>" />
    </td>
    </tr>       
<?php 
  } else if ($param->paramType=='isEmployee') {
    $defaultValue='';
    ?>
  <tr>
  <td class="label"><label><?php echo i18n('col' . pq_ucfirst($param->name));?>&nbsp;<?php if (!isNewGui()) echo ':&nbsp;';?></label></td>
  <td>
    <input dojoType="dijit.form.CheckBox" id="<?php echo $param->name;?>" name="<?php echo $param->name;?>" />
  </td>
  </tr>       
<?php 
  } else if ($param->paramType=='ticketType') {
    $defaultValue='';
    if ($param->defaultValue) {
      $defaultValue=$param->defaultValue; 
    }
?>
    <tr>
    <td class="label"><label><?php echo i18n('col' . pq_ucfirst($param->name));?>&nbsp;<?php if (!isNewGui()) echo ':&nbsp;';?></label></td>
    <td>
    <select dojoType="dijit.form.FilteringSelect" class="input <?php if($required)echo "required" ;?>" 
    <?php if($required)echo "required" ;?>
    <?php echo autoOpenFilteringSelect();?>
       style="width: 200px;"
       id="<?php echo $param->name;?>" name="<?php echo $param->name;?>"
     >
       <?php htmlDrawOptionForReference('idTicketType', $defaultValue, null, false); ?>
     </select>    
    </td>
    </tr>
<?php 
  } else if ($param->paramType=='objectList') {
    $defaultValue='';
    if ($param->defaultValue) {
      $defaultValue=$param->defaultValue; 
    }
    $arr=SqlList::getListNotTranslated('Importable');
?>
    <tr>
    <td class="label"><label><?php echo i18n('col' . pq_ucfirst($param->name));?>&nbsp;<?php if (!isNewGui()) echo ':&nbsp;';?></label></td>
    <td>
    <select dojoType="dijit.form.FilteringSelect" class="input <?php if($required)echo "required" ;?>" 
    <?php if($required)echo "required" ;?>
    <?php echo autoOpenFilteringSelect();?>
       style="width: 200px;"
       id="<?php echo $param->name;?>" name="<?php echo $param->name;?>"
     >
     <?php
       if ($defaultValue===' ')   echo '<option value=" "></option>';
       foreach ($arr as $val) {
         echo '<option value="' . $val . '" ';
         if ($val==$defaultValue) {
           echo ' SELECTED '; 
         }  
         echo '>' . i18n($val) . '</option>';
       }
     ?>    
     </select>    
    </td>
    </tr>
<?php 
  } else if ($param->paramType=='id') {
    $defaultValue='';
    if ($param->defaultValue) {
      $defaultValue=$param->defaultValue; 
    }
?>
    <tr>
    <td class="label"><label><?php echo i18n('col' . pq_ucfirst($param->name));?>&nbsp;<?php if (!isNewGui()) echo ':&nbsp;';?></label></td>
    <td>#
    <div style="width:60px; text-align: left; color: #000000;" 
      dojoType="dijit.form.TextBox"  class="<?php if($required)echo "required" ;?>"
      <?php if($required)echo "required" ;?>
      value="<?php echo $defaultValue;?>"
      id="<?php echo $param->name;?>" name="<?php echo $param->name;?>" >
    </div> 
    </td>
    </tr>
<?php 
  } else if ($param->paramType=='nextPeriod') {
    $defaultValue='10/month';
    if ($param->defaultValue) {
      $defaultValue=$param->defaultValue; 
    }
    $defList=pq_explode('/',$defaultValue);
    $defaultPeriodValue=$defList[0];
    $defaultPeriodScale=$defList[1];
?>
    <tr style="height:10px;">
    <td class="label"><label><?php echo i18n('col' . pq_ucfirst($param->name));?>&nbsp;<?php if (!isNewGui()) echo ':&nbsp;';?></label></td>
    <td >
	    <div style="width:20px; text-align: left; color: #000000;" 
	      dojoType="dijit.form.NumberTextBox"
	      class="<?php if($required)echo "required" ;?>"
	      <?php if($required)echo "required" ;?>
	      constraints="{min:1,max:99}"  
	      value="<?php echo $defaultPeriodValue;?>"
	      id="<?php echo $param->name;?>Value" name="<?php echo $param->name;?>Value" >
	    </div>
	    <div style="<?php echo (isNewGui())?'border:0;position:relative;top:0px;float:right':'border: 1px solid #eeeeee; position: relative; top: -18px; left: 35px;'?>">
		    &nbsp;<input type="radio" data-dojo-type="dijit/form/RadioButton"
		      <?php if ($defaultPeriodScale=="month") { echo 'checked';} ?>
		      name="<?php echo $param->name;?>Scale" id="scaleMonth" value="month"/> 
		    <label for="scaleMonth" class="notLabel" style="<?php echo (isNewGui())?'float:right;text-align:left;position:relative;top:0px;left:5px;padding:0':'';?>"><?php echo i18n('month');?></label> <br />
		    &nbsp;<input type="radio" data-dojo-type="dijit/form/RadioButton"
		      <?php if ($defaultPeriodScale=="week") { echo 'checked';} ?>
		      name="<?php echo $param->name;?>Scale" id="scaleWeek" value="week"/> 
		    <label for="scaleWeek" class="notLabel" style="<?php echo (isNewGui())?'float:right;text-align:left;position:absolute;top:17px;left:25px;;padding:0':'';?>"><?php echo i18n('week');?></label>
	    </div>
    </td>
    </tr>
<?php 
	//ADD qCazelles - graphTickets
  } else if ($param->paramType=='priorityList') { 
  	if (Parameter::getGlobalParameter('filterTicketReportPriority') != 'YES') {
  		continue;
  	}
?>
  	<tr>
  	<td class="label"><label><?php echo i18n('col' . pq_ucfirst($param->name));?>&nbsp;<?php if (!isNewGui()) echo ':&nbsp;';?></label></td>
  	<td>
  		<table>
  			<tr>
    <?php 
    $listPriorities = SqlList::getList('Priority');
    foreach ($listPriorities as $idPriority => $priorityName) {
    	?>
		    	<td>
		    		<table>
		    			<tr>
		    				<td>&nbsp;<?php echo $priorityName; ?>&nbsp;</td>
		    			</tr>
		    			<tr>
		    				<td style="text-align:center">
		    				<!-- 
					    		<select name="priorities[<?php echo $idPriority; ?>]">
					    			<option value="YES"><?php echo i18n('displayYes'); ?></option>
					    			<option value="NO"><?php echo i18n('displayNo'); ?></option>
					    		</select>
					    	-->
    							<div dojoType="dijit.form.CheckBox" type="checkbox" 
    								name="priorities[<?php echo $idPriority;?>]" style="">
    							</div>
					    	</td>
					    </tr>
					</table>
				</td>	
    	<?php	
    }
    ?>
    	<td>
    		<table>
    			<tr>
    				<td>&nbsp;<?php echo i18n('undefinedPriority');?>&nbsp;</td>
    			</tr>
    			<tr>
    				<td style="text-align:center">
    				<!-- 
    					<select name="priorities[undefined]"">
					    	<option value="YES"><?php echo i18n('displayYes');?></option>
					    	<option value="NO"><?php echo i18n('displayNo'); ?></option>
					    </select>
					-->
					<div dojoType="dijit.form.CheckBox" type="checkbox" 
						name="priorities[undefined]" style="">
					</div>
					</td>
    			</tr>
    		</table>
    	</td>
    
    		</tr>
    	</table>
    </td>
    </tr>
<?php  

  } else if ($param->paramType=='urgencyList') {
    ?>
  	<tr>
  	<td class="label"><label><?php echo i18n('col' . pq_ucfirst($param->name));?>&nbsp;<?php if (!isNewGui()) echo ':&nbsp;';?></label></td>
  	<td>
  		<table>
  			<tr>
    <?php 
    $listUrgency = SqlList::getList('Urgency');
    
    foreach ($listUrgency as $idUrgency => $urgencyName) {
    	?>
		    	<td>
		    		<table>
		    			<tr>
		    				<td>&nbsp;<?php echo $urgencyName; ?>&nbsp;</td>
		    			</tr>
		    			<tr>
		    				<td style="text-align:center">
		    				<!-- 
					    		<select name="priorities[<?php echo $idUrgency; ?>]">
					    			<option value="YES"><?php echo i18n('displayYes'); ?></option>
					    			<option value="NO"><?php echo i18n('displayNo'); ?></option>
					    		</select>
					    	-->
    							<div dojoType="dijit.form.CheckBox" type="checkbox" 
    								name="urgency[<?php echo $idUrgency;?>]" style="">
    							</div>
					    	</td>
					    </tr>
					</table>
				</td>	
    	<?php	
    }
    ?>
    	<td>
    		<table>
    			<tr>
    				<td>&nbsp;<?php echo i18n('undefinedUrgency');?>&nbsp;</td>
    			</tr>
    			<tr>
    				<td style="text-align:center">
    				<!-- 
    					<select name="urgency[undefined]"">
					    	<option value="YES"><?php echo i18n('displayYes');?></option>
					    	<option value="NO"><?php echo i18n('displayNo'); ?></option>
					    </select>
					-->
					<div dojoType="dijit.form.CheckBox" type="checkbox" 
						name="urgency[undefined]" style="">
					</div>
					</td>
    			</tr>
    		</table>
    	</td>
    
    		</tr>
    	</table>
    </td>
    </tr>
<?php  

  } else if ($param->paramType=='intInput') {
  	$defaultValue='';
  	if ($param->defaultValue) {
  		$defaultValue=$param->defaultValue;	
  	}
?>
	<tr>
	<td class="label"><label><?php echo i18n(($param->name!='nbOfDays')?$param->name:'numberOfDays');?>&nbsp;<?php if (!isNewGui()) echo ':&nbsp;';?></label></td>
	<td>
	<div dojoType="dijit.form.TextBox" <?php if($required)echo "required" ;?> type="text" class="input <?php if($required)echo "required" ;?>" style="width: 150px" id="<?php echo $param->name;?>" name="<?php echo $param->name;?>" value="<?php echo $defaultValue;?>" />
	</td>
	</tr>
<?php
  } else if ($param->paramType=='intMonthInput') {
  	$defaultValue='';
  	if ($param->defaultValue) {
  		$defaultValue=$param->defaultValue;	
  	}
?>
	<tr>
	<td class="label"><label><?php echo i18n(($param->name!='nbOfMonths')?$param->name:'numberOfMonths');?>&nbsp;<?php if (!isNewGui()) echo ':&nbsp;';?></label></td>
	<td>
	<div dojoType="dijit.form.NumberSpinner" <?php if($required)echo "required" ;?> type="text" class="input <?php if($required)echo "required" ;?>" style="width: 55px" id="<?php echo $param->name;?>" name="<?php echo $param->name;?>" value="<?php echo $defaultValue;?>" />
	</td>
	</tr>
<?php
  	//END ADD atrancoso
  //add atrancoso
} else if ($param->paramType=='criticalityList') {
  ?>
  	<tr>
  	<td class="label"><label><?php echo i18n('col' . pq_ucfirst($param->name));?>&nbsp;<?php if (!isNewGui()) echo ':&nbsp;';?></label></td>
  	<td>
  		<table>
  			<tr>
    <?php 
    $listCriticality = SqlList::getList('Criticality');
    
    foreach ($listCriticality as $idCriticality => $criticalityName) {
    	?>
		    	<td>
		    		<table>
		    			<tr>
		    				<td>&nbsp;<?php echo $criticalityName; ?>&nbsp;</td>
		    			</tr>
		    			<tr>
		    				<td style="text-align:center">
		    				<!-- 
					    		<select name="criticality[<?php echo $idCriticality; ?>]">
					    			<option value="YES"><?php echo i18n('displayYes'); ?></option>
					    			<option value="NO"><?php echo i18n('displayNo'); ?></option>
					    		</select>
					    	-->
    							<div dojoType="dijit.form.CheckBox" type="checkbox" 
    								name="criticality[<?php echo $idCriticality;?>]" style="">
    							</div>
					    	</td>
					    </tr>
					</table>
				</td>	
    	<?php	
    }
    ?>
    	<td>
    		<table>
    			<tr>
    				<td>&nbsp;<?php echo i18n('undefinedCriticality');?>&nbsp;</td>
    			</tr>
    			<tr>
    				<td style="text-align:center">
    				<!-- 
    					<select name="criticality[undefined]"">
					    	<option value="YES"><?php echo i18n('displayYes');?></option>
					    	<option value="NO"><?php echo i18n('displayNo'); ?></option>
					    </select>
					-->
					<div dojoType="dijit.form.CheckBox" type="checkbox" 
						name="criticality[undefined]" style="">
					</div>
					</td>
    			</tr>
    		</table>
    	</td>
    
    		</tr>
    	</table>
    </td>
    </tr>
<?php
  
} else if ($param->paramType=="filterActivityInput"){
  $flt = new Filter();
  $crit=array('idUser'=> $user->id, 'refType'=>"Activity", 'isDynamic'=>"0" );;
  $orderByFilter = "sortOrder ASC";
  $filterList=$flt->getSqlElementsFromCriteria($crit,false,null,$orderByFilter);
  ?>
        <!-- param filtre, Activity here -->
      <tr>
          <td class="label"><label><?php echo i18n("filterActivity");?>&nbsp;<?php if (!isNewGui()) echo ':&nbsp;';?></label></td>
          <td>
            <select data-dojo-type="dijit.form.FilteringSelect" class="input<?php if($required)echo "required" ;?>"
              <?php if($required)echo "required" ;?>
              <?php echo autoOpenFilteringSelect();?> 
              style="width:200px;" 
              id="<?php echo $param->name;?>" name="<?php echo $param->name;?>"
            >
            <option><?php echo '&nbsp;';?></option>
            <?php foreach ($filterList as $filter){
              ?>
              <option value="<?php echo($filter->id);?>"><?php echo($filter->name)?></option>
           <?php    
            }
            ?>
            
            </select>      
          </td>
      </tr>
        <!-- param filtre, Activity here -->
 <?php 
 
  } else {
    $defaultValue='';
    if ($param->defaultValue) {
      if ($param->defaultValue=='currentOrganization') {
        $res=new Resource($user->id);
        if ($res->id and $res->idOrganization and Module::isModuleActive('moduleOrganization')) {
          $defaultValue=$res->idOrganization;
        }
      } else {
        $defaultValue=$param->defaultValue;
      } 
    }
    $class=(pq_substr($param->paramType,-4,4)=='List')?pq_substr($param->paramType,0,pq_strlen($param->paramType)-4):$param->paramType;
    $class=pq_ucfirst($class);
    if (! class_exists($class)) continue;
    $critField=null; $critVal=null;
    if ($projectSelected and property_exists($class, 'idProject')) {
    	$critField='idProject';
    	$critVal=$projectSelected;
    }
?>
    <tr style="<?php if ($class=='Organization' and ! Module::isModuleActive('moduleOrganization')) echo 'display:none;' ?>">
    <td class="label"><label><?php echo i18n('col' . pq_ucfirst($param->name));?>&nbsp;<?php if (!isNewGui()) echo ':&nbsp;';?></label></td>
    <td style="position: relative">
    <select data-dojo-type="<?php echo (($param->multiple == 1) ? 'dojox.form.CheckedMultiSelect' : 'dijit.form.FilteringSelect') ?>" class="input <?php if($required)echo "required" ;if ($param->multiple == 1) echo "multiSelect" ;?> " 
    <?php if($required)echo "required" ;?>
    <?php echo ($param->multiple == 1) ? '' : autoOpenFilteringSelect(); ?>
       <?php echo (($param->multiple == 1) ? ' style="border:0px;border-bottom:1px solid #eeeeee;width: 200px !important; height: 127px;" multiple="true"' : ' style="width:200px;"') ?>
       id="<?php echo $param->name;?>" name="<?php echo $param->name . (($param->multiple == 1) ? '[]' : '');?>"
     >
     <?php if ($class=='Baseline') $class='BaselineSelect';?>
     <?php htmlDrawOptionForReference('id'.$class, $defaultValue, null, ($class=='BaselineSelect' || $param->multiple),$critField,$critVal); ?>     
    </select>
    <?php if ($param->multiple == 1 ) {?>
      <div style="position: absolute; top:0; left: 235px">
      <button id="selectAllButton" dojoType="dijit.form.Button" showlabel="false" 
        title="<?php echo i18n('buttonSelectAll');?>"
        iconClass="iconSelectAll" class="detailButton" >
        <script type="dojo/connect" event="onClick" args="evt">
          select = dijit.byId('<?php echo $param->name;?>');
          options=select.getOptions();
          select.set("value",options);
        </script>
      </button>
      <button id="unselectAllButton" dojoType="dijit.form.Button" showlabel="false" 
      title="<?php echo i18n('buttonUnselectAll');?>"
      iconClass="iconUnselectAll" class="detailButton" >
        <script type="dojo/connect" event="onClick" args="evt">
          select = dijit.byId('<?php echo $param->name;?>');
          options=select.getOptions();
          select.options=[];
          for (var i=0;i<options.length; i++) {            
            var opt=options[i];
            opt.selected=false;
            select.addOption(opt); 
          }
      </script>
      </button>    
      </div>
    <?php }?>
    </td>
    </tr>
<?php 
  }
}
?>
  <tr>
    <td></td>
    <td><div style="position:absolute;top:5px" class="nobr">
      <input type="hidden" name="orientation" value="<?php echo $report->orientation;?>" />
      <?php 
      $reportName=$report->name;
      $reportName=pq_str_replace(array('report','Macro'),array('',''),$reportName);
      ?>
      <input type="hidden" id="objectClass" name="objectClass" value="" />
      <input type="hidden" id="reportCodeName" name="reportCodeName" value="<?php echo base64_encode($reportName);?>" />
      <?php if($report->hasView) { ?>
      <button title="<?php echo i18n('reportShow')?>"   
         dojoType="dijit.form.Button" type="submit" 
         id="reportSubmit" name="reportSubmit" 
         iconClass="dijitButtonIcon dijitButtonIconDisplay" class="detailButton whiteBackground" showLabel="false"
         onclick="dojo.byId('outMode').value='';runReport();return false;">
      </button>
      <?php }?>
      <?php if($report->hasPrint) { ?>
      <button title="<?php echo i18n('reportPrint')?>"  
         dojoType="dijit.form.Button" type="button"
         id="reportPrint" name="reportPrint"
         iconClass="dijitButtonIcon dijitButtonIconPrint" class="detailButton whiteBackground" showLabel="false">
          <script type="dojo/connect" event="onClick" args="evt">
            dojo.byId('outMode').value='';            
            var fileName=dojo.byId('reportFile').value;
            showPrint("../report/"+ fileName, 'report',null,null,'<?php echo $report->orientation;?>');
          </script>
      </button>
      <?php }?>
      <?php if($report->hasPdf) { ?>
      <button title="<?php echo i18n('reportPrintPdf')?>"  
         dojoType="dijit.form.Button" 
         id="reportPrintPdf" name="reportPrintPdf"
         iconClass="dijitButtonIcon dijitButtonIconPdf" class="detailButton whiteBackground" showLabel="false">
          <script type="dojo/connect" event="onClick" args="evt">
            dojo.byId('outMode').value='pdf';
            var fileName=dojo.byId('reportFile').value;
            //showPrint("../report/"+ fileName, 'report', null, 'pdf');
            if(fileName.lastIndexOf("jsonPlanning.php") != -1){
              showPrint("../report/"+ fileName.substring(0,fileName.indexOf("php")-1) +"_pdf" + fileName.substring(fileName.indexOf("php")-1,fileName.length), 'report', null, 'pdf','<?php echo $report->orientation;?>');
            }else if(fileName.lastIndexOf("jsonResourcePlanning.php") != -1){
              showPrint("../report/"+ fileName.substring(0,fileName.indexOf("php")-1) +"_pdf"+ fileName.substring(fileName.indexOf("php")-1,fileName.length), 'report', null, 'pdf','<?php echo $report->orientation;?>');
            }else{
              showPrint("../report/"+ fileName, 'report', null, 'pdf','<?php echo $report->orientation;?>');
            }
          </script>
      </button>
      <?php }?>
      <?php if($report->hasToday) { ?>
      <button title="<?php echo i18n('showInToday')?>"   
         dojoType="dijit.form.Button" type="button" 
         id="reportShowInToday" name="reportShowInToday" 
         iconClass="dijitButtonIcon dijitButtonIconToday" class="detailButton whiteBackground" showLabel="false"
         onclick="saveReportInToday();">
      </button>
      <?php }?>
      <?php if (isHtml5() and $report->hasFavorite) {?>
      <button title="<?php echo i18n('defineAsFavorite')?>"   
         dojoType="dijit.form.Button" type="button" 
         id="reportDefineAsFavorite" name="reportDefineAsFavorite" 
         iconClass="imageColorNewGui iconReportsFavorite iconSize22" class="detailButton whiteBackground" showLabel="false"
         onclick="saveReportAsFavorite(<?php echo $idRow;?>);">
      </button>
      <?php }?>
      <?php if($report->hasCsv) { ?>
      <button title="<?php echo i18n('reportPrintCsv')?>"
         dojoType="dijit.form.Button" type="button"
         id="reportPrintCsv" name="reportPrintCsv"
         iconClass="dijitButtonIcon dijitButtonIconCsv" class="detailButton whiteBackground" showLabel="false">
         <script type="dojo/connect" event="onClick" args="evt">
             dojo.byId('outMode').value='csv';
             var fileName=dojo.byId('reportFile').value;
             showPrint("../report/"+ fileName, 'report',null,'csv','<?php echo $report->orientation;?>');
           </script>
      </button>
		  <?php }?>
		  <?php if ($report->hasWord) { ?>
      <button title="<?php echo i18n('reportPrintWord')?>"
         dojoType="dijit.form.Button" type="button"
         id="reportPrintWord" name="reportPrintWord"
         iconClass="dijitButtonIcon dijitButtonIconWord" class="detailButton whiteBackground" showLabel="false">
         <script type="dojo/connect" event="onClick" args="evt">
             dojo.byId('outMode').value='word';
             var fileName=dojo.byId('reportFile').value;
             showPrint("../report/"+ fileName, 'report',null,'word','X');
           </script>
      </button>
		  <?php }?>
		  <?php if($report->hasExcel and version_compare(phpversion(), '7.1.0', '>=')) { ?>
      <button title="<?php echo i18n('reportPrintExcel')?>"
         dojoType="dijit.form.Button" type="button"
         id="reportPrintExcel" name="reportPrintExcel"
         iconClass="dijitButtonIcon dijitButtonIconExcel" class="detailButton whiteBackground" showLabel="false">
         <script type="dojo/connect" event="onClick" args="evt">
             dojo.byId('outMode').value='word';
             var fileName=dojo.byId('reportFile').value;
             showPrint("../report/"+ fileName, 'report',null,'excel','X');
           </script>
      </button>
		  <?php }?>
		   <?php if($report->filterClass) { 
		     $activeFilter=false;
		     if (is_array(getSessionUser()->_arrayFilters)) {
		       if (pq_array_key_exists('Report_'.$report->filterClass, getSessionUser()->_arrayFilters)) {
		         if (count(getSessionUser()->_arrayFilters['Report_'.$report->filterClass])>0) {
		           foreach (getSessionUser()->_arrayFilters['Report_'.$report->filterClass] as $filter) {
		             if (!isset($filter['isDynamic']) or $filter['isDynamic']=="0") {
		               $activeFilter=true;
		             }
		           }
		         }
		       }
		     }
		     ?>
		   <input type="hidden" id="objectClassList" name="objectClassList" value="Report_<?php echo $report->filterClass;?>"/>
       <button 
         title="<?php echo i18n('advancedFilter')?>"  
         class="comboButton detailButton <?php echo (isNewGui())?'':'whiteBackground';?>"
         dojoType="dijit.form.DropDownButton" 
         id="listFilterFilter" name="listFilterFilter"
         iconClass="dijitButtonIcon icon<?php echo($activeFilter)?'Active':'';?>Filter" showLabel="false">
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
          <div dojoType="dijit.TooltipDialog" id="directFilterList" style="z-index: 999999;<!-- display:none; --> position: absolute;">
          <?php 
          //RequestHandler::setValue('filterObjectClass','Planning');
          $objectClass='Report_'.$report->filterClass;
          include "../tool/displayFilterList.php";?>
            <script type="dojo/method" event="onMouseEnter" args="evt">
                                clearTimeout(closeFilterListTimeout);
                                clearTimeout(openFilterListTimeout);
                              </script>
            <script type="dojo/method" event="onMouseLeave" args="evt">
                                dijit.byId('listFilterFilter').closeDropDown();
                              </script>
          </div> 
        </button>
		  <?php }
		  if($autoSendReportAccess and $report->hasPdf) {?>
  		  <button title="<?php echo i18n('reportAutoSendReport')?>"   
           dojoType="dijit.form.Button" type="submit" 
           id="reportAutoSendReport" name="reportAutoSendReport" 
           iconClass="dijitButtonIcon dijitButtonIconEmail" class="detailButton whiteBackground" showLabel="false"
           onclick="saveReportParametersForDialog();">
        </button>
        <?php }?>
        <input type="hidden" id="page" name="page" value="<?php echo ((pq_substr($report->file,0,3)=='../')?'':'../report/') . $report->file;?>"/>
        <input type="hidden" id="print" name="print" value=true />
        <input type="hidden" id="report" name="report" value=true />
        <input type="hidden" id="outMode" name="outMode" value='' />
        <input type="hidden" id="reportName" name="reportName" value="<?php echo i18n($report->name);?>" />
        <input type="hidden" id="csrfToken" name="csrfToken" value="<?php echo getSessionValue('Token');?>" />
        <input type="hidden" id="directAccessIndex" name="directAccessIndex" value="<?php echo RequestHandler::getValue('directAccessIndex');?>" />
      </div></td>
  </tr>
</table>
</td><td>&nbsp;
</td></tr></table>
</form>
</div>
