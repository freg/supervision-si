<?php 
/*** COPYRIGHT NOTICE *********************************************************
 *
 * Copyright 2009-2015 ProjeQtOr - Pascal BERNARD - support@projeqtor.org
 * Contributors : -
 *
 * This file is part of ProjeQtOr.
 * 
 * ProjeQtOr is free software: you can redistribute it and/or modify it under 
 * the terms of the GNU General Public License as published by the Free 
 * Software Foundation, either version 3 of the License, or (at your option) 
 * any later version.
 * 
 * ProjeQtOr is distributed in the hope that it will be useful, but WITHOUT ANY
 * WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS 
 * FOR A PARTICULAR PURPOSE.  See the GNU General Public License for 
 * more details.
 *
 * You should have received a copy of the GNU General Public License along with
 * ProjeQtOr. If not, see <http://www.gnu.org/licenses/>.
 *
 * You can get complete code of ProjeQtOr, other resource, help and information
 * about contributors at http://www.projeqtor.org 
 *     
 *** DO NOT REMOVE THIS NOTICE ************************************************/

/* ============================================================================
 * Habilitation defines right to the application for a menu and a profile.
 */ 
require_once "../tool/projeqtor.php";
//cron minute/hour/day of month/month/day of week
$minutes='*';
$hours='*';
$dayOfMonth='*';
$month='*';
$dayOfWeek='*';
$scope=RequestHandler::getValue('cronScope');
$adminView=RequestHandler::getValue('adminView');
if (!$scope) return;
$cronExecution=CronExecution::getObjectFromScope($scope);
$cron=pq_explode(" ",$cronExecution->cron);
$minutes=$cron[0];
$hours=$cron[1];
$dayOfMonth=$cron[2];
$month=$cron[3];
$dayOfWeek=$cron[4];
?>
<form dojoType="dijit.form.Form" id='cronDefiniton' name='cronDefiniton' onSubmit="return false;" >
<input type="hidden" name="cronExecutionScope" value="<?php echo $scope;?>" />
<table style="width:100%;">
<tr>
  <td colspan="2" style="font-weight:normal;text-align:center"><?php echo i18n("cronDefineParametersHelp");?></td>
</tr>
<tr>
  <td colspan="2" style="font-weight:bold;text-align:center">&nbsp;</td>
</tr>
<tr>
  <td class="dialogLabel"><label><?php echo i18n("minute");?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label></td>
  <td style="padding-right:20px">
    <select dojoType="dijit.form.FilteringSelect" class="input required" required="true"
    <?php echo autoOpenFilteringSelect();?>
    style="width: 98%;" name="cronDefinitonMinutes" id="cronDefinitonMinutes">
    <?php 
      echo htmlReturnOptionForMinutesHoursCron($minutes);
    ?>
    </select>
  </td>
</tr>
<tr>
  <td class="dialogLabel"><label><?php echo i18n("hour");?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label></td>
  <td style="padding-right:20px">
    <select dojoType="dijit.form.FilteringSelect" class="input required" required="true"
    <?php echo autoOpenFilteringSelect();?>
    style="width: 98%;" name="cronDefinitonHours" id="cronDefinitonHours">
    <?php 
      if ($scope == 'Baseline') {
        echo htmlReturnOptionForMinutesHoursCron($hours,true, false, true);
      } else {
        echo htmlReturnOptionForMinutesHoursCron($hours,true);
      }
    ?>
    </select>
  </td>
</tr>
<tr>
  <td class="dialogLabel"><label><?php echo i18n("colFixedDay");?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label></td>
  <td style="padding-right:20px">
    <select dojoType="dijit.form.FilteringSelect" class="input required" required="true"
    <?php echo autoOpenFilteringSelect();?>
    style="width: 98%;" name="cronDefinitonDayOfMonth" id="cronDefinitonDayOfMonth">
    <?php 
      echo htmlReturnOptionForMinutesHoursCron($dayOfMonth,false,true);
    ?>
    </select>
  </td>
</tr>
<tr>
  <td class="dialogLabel"><label><?php echo i18n("month");?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label></td>
  <td style="padding-right:20px">
    <select dojoType="dijit.form.FilteringSelect" class="input required" required="true"
    <?php echo autoOpenFilteringSelect();?>
    style="width: 98%;" name="cronDefinitonMonth" id="cronDefinitonMonth">
    <?php 
    echo '<option value="*" >'.i18n('all').'</option>';
      //echo htmlReturnOptionForMonthsCron($month);
      echo htmlReturnOptionForMonths($month,true);
    ?>
    </select>
  </td>
</tr>
<tr>
  <td class="dialogLabel"><label><?php echo i18n("colFixedDayOfWeek");?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label></td>
  <td style="padding-right:20px">
    <select dojoType="dijit.form.FilteringSelect" class="input required" required="true"
    <?php echo autoOpenFilteringSelect();?>
    style="width: 98%;" name="cronDefinitonDayOfWeek" id="cronDefinitonDayOfWeek">
    <?php 
      echo '<option value="*" >'.i18n('all').'</option>';
      //echo htmlReturnOptionForWeekdaysCron($dayOfWeek);
      echo htmlReturnOptionForWeekdays($dayOfWeek,true);
    ?>
    </select>
  </td>
</tr>
<?php if ($scope=='runConsistencyCheck'){?> 
<tr>
  <td><label for='cronConsistencyCheckMail'><?php echo i18n("cronConsistencyCheckMail");?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label></td>
  <td style="padding-right:20px;">
    <input dojoType="dijit.form.TextBox" class="input required"  style="width: 100%;height: 15px;border-radius: 5px;" name="cronConsistencyCheckMail" id="cronConsistencyCheckMail" value="<?php echo Parameter::getGlobalParameter('cronConsistencyCheckMail')?>"/>
  </td>
</tr>
<?php }?>
<tr>
  <td colspan="2" style="font-weight:bold;text-align:center">&nbsp;</td>
</tr>
<tr>
  <td align="center" colspan="2">
    <input type="hidden" id="dialogCronDefinitonAction">
    <button class="mediumTextButton"  dojoType="dijit.form.Button" type="button" onclick="dijit.byId('dialogCronDefinition').hide();formChangeInProgress=false;">
      <?php echo i18n("buttonCancel");?>
    </button>
    <button class="mediumTextButton"  id="dialogCronDefinitonSubmit" dojoType="dijit.form.Button" data-scope="<?php echo $scope; ?>" type="submit" onclick="protectDblClick(this);cronExecutionDefinitionSave('<?php echo $adminView;?>');return false;">
      <?php echo i18n("buttonOK");?>
    </button>
  </td>
</tr>
</table>
</form>
<?php 
function htmlReturnOptionForMinutesHoursCron($selection, $isHours=false, $isDayOfMonth=false, $required=false) {
  $arrayWeekDay=array();
  $max=59;
  $start=0;
  $modulo=5;
  if($isHours){
    $max=23;
    $start=0;
    $modulo=1;
  }
  if($isDayOfMonth){
    $max=31;
    $start=1;
    $modulo=1;
  }
  for($i=$start;$i<=$max;$i++){
    $key=$i;
    //if($key<10)$key='0'.$key;
    if ( $i % $modulo==0) $arrayWeekDay[$key]=$key;
  }
  $result="";
  if (! $required) {
    $result.='<option value="*" '.(($selection=='*')?'selected':'').'>'.i18n('all').'</option>';
  }
  
  // "*/N" options, only relevant for minutes and hours columns
  if (! $isDayOfMonth) {
    $intervals=array();
    if ($isHours) {
      $intervals=array(2,3,4,6,8,12);
    } else {
      $intervals=array(5,10,15,30);
    }
    foreach($intervals as $n) {
      $value='*/'.$n;
      $label= $isHours ? i18n('everyXHours',array($n)): i18n('everyXMinutes',array($n));
      $result.='<option value="'.$value.'"';
      if ($selection!==null and $selection===$value) { $result.=' SELECTED '; }
      $result.='>'.$label.'</option>';
    }
  }
  
  foreach($arrayWeekDay as $key=>$line) {
    $result.= '<option value="' . $key . '"';
    if ($selection!==null and $key==$selection ) { $result.= ' SELECTED '; }
    $result.= '>'.$line.'</option>';
  }
  return $result;
}
?>