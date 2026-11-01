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

/** ============================================================================
 * Activity is main planned element
 */  
require_once('_securityCheck.php');

class CronExecution extends SqlElement {
  
  public $id;    // redefine $id to specify its visible place
  public $cron;
  public $fileExecuted;
  public $idle;
  public $fonctionName;
  public $nextTime;
  public $_noHistory;
  
   /** ==========================================================================
   * Constructor
   * @param $id Int the id of the object in the database (null if not stored yet)
   * @return void
   */ 
  function __construct($id = NULL, $withoutDependentObjects=false) {
    parent::__construct($id,$withoutDependentObjects);
  }

   /** ==========================================================================
   * Destructor
   * @return void
   */ 
  function __destruct() {
    parent::__destruct();
  }

  public function save($withRelaunch=true) {
    return parent::save();
  }
  
  public function calculNextTime(){
    $UTC=new DateTimeZone(Parameter::getGlobalParameter ( 'paramDefaultTimezone' ));
    $date=new DateTime('now');
    $splitCron=pq_explode(" ",$this->cron);
    $minute=1;
		$splitMinuteCron=pq_explode("/",$splitCron[0]);
		if(count($splitMinuteCron)==2){
		  $splitCron[0]=$splitMinuteCron[0];
		  $mod = $date->format('i')%$splitMinuteCron[1];
		  if($mod > 0){
		    $minute = $splitMinuteCron[1] - $mod;
		  }else{
		    $minute = $splitMinuteCron[1];
		  }
		}
		$splitHourCron=pq_explode("/",$splitCron[1]);
		if(count($splitHourCron)==2){
			$splitCron[1]=$splitHourCron[0];
			$mod = $date->format('H')%$splitHourCron[1];
			if($mod > 0){
			  if($splitCron[0] != '*'){
			    $minute = ($splitHourCron[1]-$mod)*60-$date->format('i')+$splitCron[0];
			  }else{
			    $minute = ($splitHourCron[1]-$mod)*60-$date->format('i');
			  }
			}else{
			  if($splitCron[0] != '*'){
			    $minute = abs($date->format('i') - $splitCron[0]);
			  }else{
			  	$minute = abs(60-$date->format('i'));
			  }
			}
		}
		$date->modify('+'.$minute.' minute');
    $count=0;
    if(count($splitCron)==5){
      $find=false;
      while(!$find){ //cron minute/hour/dayOfMonth/month/dayOfWeek
        if(($splitCron[0]=='*' || $date->format("i")==$splitCron[0])
        && ($splitCron[1]=='*' || $date->format("H")==$splitCron[1])
        && ($splitCron[2]=='*' || $date->format("d")==$splitCron[2])
        && ($splitCron[3]=='*' || $date->format("m")==$splitCron[3])
        && ($splitCron[4]=='*' || $date->format("N")==$splitCron[4])){
          $find=true;
          $date->setTime($date->format("H"), $date->format("i"), 0);
          $this->nextTime=$date->format("U");
          $this->save(false);
        }else{
          $date->modify('+1 minute');
        }
        $count++;
        if($count>=2150000){
          $this->idle=1;
          $this->save(false);
          $find=true;
          errorLog("Can't find next time for cronexecution because too many execution #".$this->id);
        }
      }
    }else{
      errorLog("Can't find next time for cronexecution because too many execution #".$this->id);
    }
  }
  
  public static function drawCronExecutionDefintion($scope,$adminView=false) {
    $cronExecution=null;
    $cronExecution=SqlElement::getSingleSqlElementFromCriteria('CronExecution', array('fonctionName'=>'cron'.pq_ucfirst($scope)));
    if (!$cronExecution->id) {
      $cronExecution->idle=1;
    }
    if($scope!='disconnectAll' and $scope!='runConsistencyFix' and $scope!='SubscriptionUpdateRevision' and $scope!='SubscriptionUpdateVersion' and $scope!='reorderWBS')echo "<br/>";
    if($scope!='disconnectAll' and $scope!='runConsistencyCheck' and $scope!='SubscriptionUpdateRevision' and $scope!='SubscriptionUpdateVersion' and $scope!='reorderWBS')echo "<br/>";
    $splitCron=($cronExecution->cron)?pq_explode(" ",$cronExecution->cron):array('0','*','*','*','*');
    foreach ($splitCron as $key=>$line){
      if($line=="*")$splitCron[$key]=i18n("all");
    }
    if(!$adminView and $scope!='skillsAlertCron'){
      if($scope=='disconnectAll' or $scope=='runConsistencyFix' or $scope=='runConsistencyCheck' or $scope=='reorderWBS') $adminView=true;
      $minutes=$splitCron[0];
      $hours=$splitCron[1];
      $dayOfMonth=$splitCron[2];
      $month=$splitCron[3];
      $dayOfWeek=$splitCron[4];
      if (substr($minutes,0,2)=='*/') $minutes = i18n('everyXMinutes',array(substr($minutes,2)));
      if (substr($hours,0,2)=='*/') $hours = i18n('everyXHours',array(substr($hours,2)));
      echo "<table style='float:left;'>";
      echo "  <tr><td class='linkHeader' style='width:100px;padding:0px 5px'>".i18n('colFrequency')."</td><td class='linkHeader' style='width:80px;padding:0px 5px'>".i18n('colValue')."</td></tr>";
      echo "  <tr><td class='linkData'>".i18n('minute')."</td><td class='linkData'>$minutes</td></tr>";
      echo "  <tr><td class='linkData'>".i18n('hour')."</td><td class='linkData'>$hours</td></tr>";
      echo "  <tr><td class='linkData'>".i18n('colFixedDay')."</td><td class='linkData'>$dayOfMonth</td></tr>";
      echo "  <tr><td class='linkData'>".i18n('month')."</td><td class='linkData'>".self::getMonthName($month)."</td></tr>";
      echo "  <tr><td class='linkData'>".i18n('colFixedDayOfWeek')."</td><td class='linkData'>".self::getWeekDayName($dayOfWeek)."</td></tr>";
      if($scope=='runConsistencyCheck'){
        echo "  <tr><td class='linkData'>".i18n('cronConsistencyCheckMail')."</td><td style='width:200px;' class='linkData'>".Parameter::getGlobalParameter('cronConsistencyCheckMail')."</td></tr>";
      }
      echo " </table>";
      echo "&nbsp;";
      echo "<button id='cronExecution$scope' dojoType='dijit.form.Button' class='roundedVisibleButton' showlabel='true' style='position:relative;top:-2px'>";
      echo i18n("cronDefineParameters");
      echo "  <script type='dojo/connect' event='onClick' args='evt'>";
      echo "    loadDialog('dialogCronDefinition', null, true, '&cronScope=$scope&adminView=$adminView', true);";
      echo "  </script>";
      echo "</button><br/>";
      echo "&nbsp;";
    }
    if ($cronExecution->id!='') {
      $title = ($adminView)?i18n('helpCronExecutionActivateAdmin'):'';
      if($scope=='disconnectAll'){
        $adminView=true;
        $title = i18n('helpCronExecutionDisconnectAll');
      }
      if($scope=='runConsistencyFix'){
        $adminView=true;
        $title = i18n('helpCronExecutionRunConsistencyFix');
      }
      if($scope=='runConsistencyCheck'){
        $adminView=true;
        $title = i18n('helpCronExecutionRunConsistencyCheck');
      }
      if($scope=='reorderWBS'){
        $adminView=true;
        $title = i18n('helpReorderWBS');
      }
      if($scope=='skillsAlertCron'){
        $adminView=false;
        $title = i18n('helpSkillsAlertCron');
      }
      echo '<button id="cronExecutionActivate'.$scope.'" class="roundedVisibleButton" dojoType="dijit.form.Button" showlabel="true" style="position:relative;'.(($adminView)?'':'top:2px;').'"
              title="'.$title.'" >';
      echo    $cronExecution->idle ? i18n("cronExecutionActivate") : i18n("cronExecutionDesactivate");
      echo "  <script type='dojo/connect' event='onClick' args='evt'>";
      echo "    cronActivation('$scope','$adminView');";
      echo "  </script>";
      echo "</button>";
      if ($cronExecution->idle==1) {
        echo "<div style='white-space:nowrapo;height:30px; width:400px;color:#A00000;position:relative;left:12px;".(($adminView)?'display:inline;':'')."'>".i18n(($adminView)?'cronExecutionNotRunningAdmin':'cronExecutionNotRunning')."</div>";
      } else {
        echo "<div style='white-space:nowrapo;height:30px; width:400px;color:#00A000;position:relative;left:12px;".(($adminView)?'display:inline;':'')."'>".i18n(($adminView)?'cronExecutionRunningAdmin':'cronExecutionRunning')."</div>";
      }
    }

  }
  
  public static function getObjectFromScope($scope) {
    $obj=SqlElement::getSingleSqlElementFromCriteria('CronExecution', array('fonctionName'=>'cron'.pq_ucfirst($scope)));
    if (! pq_trim($obj->cron)) $obj->cron='0 * * * *';
    return $obj;
  }
  public static function getWeekDayName($day) {
    if ($day=='*' or $day=='all' or $day==i18n('all')) return i18n('all');
    $dayName=array(0=>'Sunday',   1=>'Monday', 2=>'Tuesday',  3=>'Wednesday',
                   4=>'Thursday', 5=>'Friday', 6=>'Saturday', 7=>'Sunday');
    if (isset($dayName[$day])) return i18n($dayName[$day]);
    else return $day;
  }
  public static function getMonthName($month) {
    if ($month=='*' or $month=='all' or $month==i18n('all')) return i18n('all');
    return getMonth(0,$month-1);
  }
}
?>