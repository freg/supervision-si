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
 * ActionType defines the type of an issue.
 */ 
use Webklex\PHPIMAP\ClientManager;
use Webklex\PHPIMAP\Client;
require_once('_securityCheck.php');

class Cron {

  // Define the layout that will be used for lists
    
  private static $sleepTime;
  private static $checkDates;
// BEGIN - ADD BY TABARY - NOTIFICATION SYSTEM
  private static $checkNotifications;
// END - ADD BY TABARY - NOTIFICATION SYSTEM
// MTY - LEAVE SYSTEM
  private static $checkLeavesEarned;
// MTY - LEAVE SYSTEM
  private static $checkImport;
  private static $checkEmails;
  private static $checkMailGroup;
  private static $runningFile;
  private static $timesFile;
  private static $stopFile;
  private static $errorFile;
  private static $deployFile;
  private static $restartFile;
  private static $historyFile;
  private static $autoFile;
  private static $cronWorkDir;
  public static $listCronExecution;
  public static $lastCronTimeExecution;
  public static $lastCronExecution;
  public static $listCronAutoSendReport;
  public static $lastCronTimeAutoSendReport;
  public static $lastCronAutoSendReport;
  public static $cronUniqueId;
  public static $cronProcessId;
  public static $cronRequestedStop;
  public static $lastBankUpdate;
  public static $startCnxIssue;
  public static $waitDbTimer;
  
  const CRON_DATA_SEPARATOR='|';  
   /** ==========================================================================
   * Constructor
   * @param $id Int the id of the object in the database (null if not stored yet)
   * @return void
   */ 
  function __construct($id = NULL, $withoutDependentObjects=false) {

  }

  
   /** ==========================================================================
   * Destructor
   * @return void
   */ 
  function __destruct() {
    
  }

// ============================================================================**********
// GET STATIC DATA FUNCTIONS
// ============================================================================**********
  
  public static function init() {
  	if (self::$cronWorkDir) return;
  	self::$cronWorkDir=Parameter::getGlobalParameter('cronDirectory');
    self::$runningFile=self::$cronWorkDir.'/RUNNING';
    self::$timesFile=self::$cronWorkDir.'/DELAYS';
    self::$stopFile=self::$cronWorkDir.'/STOP';
    self::$errorFile=self::$cronWorkDir.'/ERROR';
    self::$deployFile=self::$cronWorkDir.'/DEPLOY';
    self::$restartFile=self::$cronWorkDir.'/RESTART';
    self::$historyFile=self::$cronWorkDir.'/HISTORY';
    self::$autoFile=self::$cronWorkDir.'/AUTO';
  }
  
  public static function getActualTimes() {
  	self::init();
  	if (! is_file(self::$timesFile)) {
  		return array();
  	}
  	$handle=fopen(self::$timesFile, 'r');
    $line=fgets($handle);
    fclose($handle);
    $result=array();
    $arr=pq_explode('|',$line);
    foreach ($arr as $val) {
    	$split=pq_explode('=',$val);
    	if (count($split)==2) {
    	  $result[$split[0]]=$split[1];
    	}
    }
  	return $result;
  }

  public static function setActualTimes() {
  	self::init();
    $handle=fopen(self::$timesFile, 'w');
    fwrite($handle,'SleepTime='.self::getSleepTime()
                 .'|CheckDates='.self::getCheckDates()
                 .'|CheckImport='.self::getCheckImport()
                 .'|CheckEmails='.self::getCheckEmails()
                 .( Mail::isMailGroupingActiv() ?'|CheckMailGroup='.self::getCheckMailGroup():'')
// BEGIN - ADD BY TABARY - NOTIFICATION SYSTEM            
                 .(isNotificationSystemActiv()?'|CheckNotifications='.self::getCheckNotifications():'')
// END - ADD BY TABARY - NOTIFICATION SYSTEM
// MTY - LEAVE SYSTEM            
                 .(isLeavesSystemActiv()?'|CheckLeavesEarned='.self::getCheckLeavesEarned():'')
// MTY - LEAVE SYSTEM
           );
    fclose($handle);
  }
  
  public static function storeHistory($msg) {
    self::init();
    $handle=fopen(self::$historyFile, 'a');
    fwrite($handle,date('Y-m-d H:i:s')." | ".getCurrentUserId()." | $msg \n");
    fclose($handle);
  }
  
  public static function getSleepTime() {
  	self::init();
    if (self::$sleepTime) {
    	return self::$sleepTime;
    }
  	$cronSleepTime=Parameter::getGlobalParameter('cronSleepTime');
    if (! $cronSleepTime) {$cronSleepTime=10;}
    self::$sleepTime=$cronSleepTime;
    return self::$sleepTime;
  }

  public static function getCheckDates() {
  	self::init();
    if (self::$checkDates) {
      return self::$checkDates;
    }
    $checkDates=Parameter::getGlobalParameter('cronCheckDates'); 
    if (! $checkDates) {$checkDates=30;}
    self::$checkDates=$checkDates;
    return self::$checkDates;
  }

// BEGIN - ADD BY TABARY - NOTIFICATION SYSTEM
  public static function getCheckNotifications() {
    self::init();
    if (!isNotificationSystemActiv()) {
        self::$checkNotifications=-1;
        return self::$checkNotifications;        
    }  
    if (self::$checkNotifications) {
      return self::$checkNotifications;
    }
    $checkNotifications=Parameter::getGlobalParameter('cronCheckNotifications'); 
    if (! $checkNotifications) {$checkNotifications=3600;}
    self::$checkNotifications=$checkNotifications;
    return self::$checkNotifications;
  }
// END - ADD BY TABARY - NOTIFICATION SYSTEM

// MTY - LEAVE SYSTEM
  public static function getCheckLeavesEarned() {
    self::init();
    if (!isLeavesSystemActiv()) {
        self::$checkLeavesEarned=-1;
        return self::$checkLeavesEarned;        
    }  
    if (self::$checkLeavesEarned) {
      return self::$checkLeavesEarned;
    }
    $checkLeavesEarned=3600*24; 
    self::$checkLeavesEarned=$checkLeavesEarned;
    return self::$checkLeavesEarned;
  }
// MTY - LEAVE SYSTEM
  
  
  public static function getCheckImport() {
  	self::init();
    if (self::$checkImport) {
      return self::$checkImport;
    }
    $checkImport=Parameter::getGlobalParameter('cronCheckImport'); 
    if (! $checkImport) {$checkImport=30;}
    self::$checkImport=$checkImport;
    return self::$checkImport;
  }  
  
  public static function getCheckEmails() {
    self::init();
    if (self::$checkEmails) {
      return self::$checkEmails;
    }
    $checkEmails=Parameter::getGlobalParameter('cronCheckEmails'); 
    if (! $checkEmails) {$checkEmails=5*60;} // Default=every 5 mn
    self::$checkEmails=$checkEmails;
    return self::$checkEmails;
  }  
  
  public static function getCheckMailGroup() {
    self::init();
    if (self::$checkMailGroup) {
      return self::$checkMailGroup;
    }
    $checkMailGroup=Mail::getMailGroupPeriod(); 
    if (! $checkMailGroup or $checkMailGroup<0) {
      $checkMailGroup=-1;
    } else {
      $checkMailGroup=$checkMailGroup/2; // Check every half period
      if ($checkMailGroup<self::getSleepTime()) {
        $checkMailGroup=self::getSleepTime();
      } else if ($checkMailGroup>60) { // check at least every minute;
        $checkMailGroup=60;
      }
    }
    self::$checkMailGroup=$checkMailGroup;
    return self::$checkMailGroup;
  }  
  
  public static function check() {
  	self::init();
    if (file_exists(self::$runningFile)) {
      $handle=fopen(self::$runningFile, 'r');
      $lastData=fgets($handle);
      $lastSplit=pq_explode(self::CRON_DATA_SEPARATOR,$lastData);
      $last=$lastSplit[0];
      $now=time();
      fclose($handle);
      //$timeout=self::getSleepTime()*5; // Old Timeout is too small : long Cronned tasks lead to unexpected relaunch
      $timeout=30*60; // 30 minutes before considering CRON is dead
      if ( !$last or !is_numeric($last) or ($now-$last) > $timeout) {
        // not running for more than 5 cycles : dead process
        self::removeRunningFlag();
        return "stopped";
      } else {
        return "running";
      }
    } else {
      return "stopped";
    }
  }

  public static function checkDuplicateRunning() {
    // Will check if another CRON is already running (with other Process ID)
    self::init();
    if (file_exists(self::$runningFile)) {
      $handle=fopen(self::$runningFile, 'r');
      $lastData=fgets($handle);
      fclose($handle);
      $lastSplit=pq_explode(self::CRON_DATA_SEPARATOR,$lastData);
      $last=$lastSplit[0];
      //$timeout=30*60; // 30 minutes before concidering CRON is dead
      //$now=time();
      //$lastExecTimeout=false;
      //if ( !$last or !is_numeric($last) or ($now-$last) > $timeout) {
      //  $lastExecTimeout=true;
      //}
      if (count($lastSplit)>2) {
        $lastProcessId=$lastSplit[1];
        $lastUniqueId=$lastSplit[2];
      } else {
        // Another process is already running with no PID logged => this is old CRON running
        // => Set Stop flag : hoping next to execute will be the old one, and it will be stopped
        debugTraceLog("Cron possibly running twice : set stop flag to stop the older one");
        self::storeHistory("set stop flag to stop duplicate");
        self::setStopFlag();
        return;
      }
      if ($lastProcessId!=self::$cronProcessId or $lastUniqueId!=self::$cronUniqueId) {
        // Another process is already running with different PID
        // => Stop current one (exit)
        traceLog("Cron possibly running twice");
        debugTraceLog("    current process ID is ".self::$cronProcessId);
        debugTraceLog("    current unique ID is ".self::$cronUniqueId);
        debugTraceLog("    running process ID is ".$lastProcessId);
        debugTraceLog("    running unique ID is ".$lastUniqueId);
        traceLog("    => stopping current Cron");
        self::storeHistory("stop duplicate");
        exit;
      }
    } else {
      // No running flag : no issue, it should be presnet at least at next loop
    }      
  }  
  
 public static function abort() {
  	self::init();
    if (Cron::$cronRequestedStop==false) {
      if (! file_exists("../model/Mail.php") and getcwd()=='/') {
        chdir(__DIR__);
      }
      if (! file_exists("../model/Mail.php")) {
        debugTraceLog("../model/Mail.php not found, current directory is :'".getcwd()."' \nTry to move up with chdir('../')");
        chdir('../');
      }
      errorLog('CRON abnormally stopped');
      debugPrintTraceStack();
      // Try and alert Admin (send mail)
      $dest=pq_trim(Parameter::getGlobalParameter('paramAdminMail'));
      $instance=Parameter::getGlobalParameter('paramDbDisplayName');
      $title="[$instance] Cron abnormally stopped";
      $now=date('Y-m-d H:i:s');
      $msg="Cron was stopped for an undefined reason (abort).<br/>Please check log file at $now for more information.";
      $smtp=Parameter::getGlobalParameter('paramMailSmtpServer');
      self::storeHistory("abort");
      if ($smtp and $dest) {
        $result=sendMail($dest,$title,$msg);
      }
    }
    
    //if (file_exists(self::$runningFile)) {
  	//  unlink(self::$runningFile); // On Abort, preserve Running Flag so that Cron can restart
    //}
    
    //$errorFileName=self::$errorFile.'_'.date('Ymd_His');
    //$mode=(file_exists($errorFileName))?'w':'x';
    //$errorFile=fopen($errorFileName, 'w');
    //fclose($errorFile);  
  } 
  
  public static function removeStopFlag() {
  	self::init();
    if (file_exists(self::$stopFile)) {
      unlink(self::$stopFile);
    }
  }
  
  public static function removeRunningFlag() {
  	self::init();
    if (file_exists(self::$runningFile)) {
      unlink(self::$runningFile);
    }
  }
  public static function removeDeployFlag() {
    if (file_exists(self::$deployFile)) {
      unlink(self::$deployFile);
    }
  }
  public static function removeRestartFlag() {
    if (file_exists(self::$restartFile)) {
      unlink(self::$restartFile);
    }
  }
  public static function setRunningFlag() {
  	self::init();
  	$handle=fopen(self::$runningFile, 'w');
    fwrite($handle,time().self::CRON_DATA_SEPARATOR.self::$cronProcessId.self::CRON_DATA_SEPARATOR.self::$cronUniqueId);
    fclose($handle);
  }
  
  public static function setRestartFlag() {
    self::init();
    self::removeRunningFlag();
    self::removeStopFlag();
    $handle=fopen(self::$restartFile, 'w');
    fwrite($handle,time());
    fclose($handle);
    self::storeHistory("set restart flag");
  }
  
  public static function setStopFlag() {
  	self::init();
    $handle=fopen(self::$stopFile, 'w');
    fclose($handle);
    self::storeHistory("set stop flag");
  }
  public static function removeAutoFlag() {
    if (file_exists(self::$autoFile)) {
      unlink(self::$autoFile);
    }
  }
  public static function setAutoFlag() {
    if (file_exists(self::$autoFile)) {
      unlink(self::$autoFile);
      errorLog("Cron::setAutoFlag() Already existing AUTO flag");
      return;
    }
    $key=md5(date('H:i:s').rand());
    $handle=fopen(self::$autoFile, 'w');
    fwrite($handle,$key.'|'.getCurrentUserId());
    fclose($handle);
    return $key;
  }
  
  public static function checkStopFlag() {
  	self::init();
    if (file_exists(self::$stopFile) or file_exists(self::$deployFile)) { 
      traceLog('Cron normally stopped at '.date('d/m/Y H:i:s'));
      Cron::$cronRequestedStop=true;
      self::removeRunningFlag();
      self::removeStopFlag();
      if (file_exists(self::$deployFile)) {
      	traceLog('Cron stopped for deployment. Will be restarted');
      	self::setRestartFlag();
        self::removeDeployFlag();
      }
      return true; 
    } else {
    	return false;
    }
  }
  
  // Restrart already running CRON  !!! NOT WORKING WITHOUT A RELAUNCH !!!
  public static function restart() {
    error_reporting(0);
    //session_write_close();
    if (self::check()=='running') {
//       self::setStopFlag();
//       sleep(self::getSleepTime());
    }
    self::storeHistory("request restart");
    self::setRestartFlag();
    //self::relaunch(); // FREEZES CURRENT USER
  }
  
	// If running flag exists and cron is not really running, relaunch
	public static function relaunch() {
		self::init();
		Cron::$cronRequestedStop=true; // Mandatory to avoid Abort message if Cron is already running
		if (file_exists(self::$restartFile)) {
			self::removeRestartFlag();
			Cron::$cronRequestedStop=false;
			self::run();
			self::storeHistory("restart (relaunch)");
		} else if (file_exists(self::$runningFile)) {
      $handle=fopen(self::$runningFile, 'r');
      //$last=fgets($handle);
      $lastData=fgets($handle);
      $lastSplit=pq_explode(self::CRON_DATA_SEPARATOR,$lastData);
      $last=$lastSplit[0];
      $now=time();
      fclose($handle);
      if (!$last or !is_numeric($last)) $last=0;
      if ( !$last or ($now-$last) > (60*30)) {
        // not running for more than 30 mn (before we used 5 cycles : dead process)
        self::removeRunningFlag();
        Cron::$cronRequestedStop=false;
        self::storeHistory("start (relaunch)");
        self::run();
      }
		}
	}
	// Restart new Cron with new php files and stop current one
	public static function autoRestart() {
	  if (! function_exists('curl_init')) {
	    debugTraceLog("CURL functions not available on Cron. Autorestart cannot be executed. Set restart flag to restart on next connection");
	    self::setRestartFlag();
	    Cron::$cronRequestedStop=true;
	    exit;
	  }
	  $url=SqlElement::getBaseUrl().'/tool/cronRun.php';
	  $key=Cron::setAutoFlag();
	  $url.='?autorestartkey='.$key;
	  $ch=curl_init();
	  $proxy=Parameter::getGlobalParameter("paramProxy");
	  $proxyUser=Parameter::getGlobalParameter("paramProxyUser");
	  $proxyPassword=Parameter::getGlobalParameter("paramProxyPassword");
	  if (preg_match('`^https://`i', pq_nvl($url))) {
	    curl_setopt($ch, CURLOPT_SSL_VERIFYPEER, false);
	    curl_setopt($ch, CURLOPT_SSL_VERIFYHOST, 0);
	  }
	  curl_setopt( $ch, CURLOPT_RETURNTRANSFER, false );
	  curl_setopt( $ch, CURLOPT_URL, $url );
	  if (isset($proxy) and $proxy) {
	    $split=explode("://",$proxy);
	    if (count($split)>1) $proxy=$split[1];
	    curl_setopt($ch, CURLOPT_FRESH_CONNECT, true);
	    curl_setopt($ch, CURLOPT_TIMEOUT_MS, 1000);
	    curl_setopt($ch, CURLOPT_CONNECTTIMEOUT, 10);
	    curl_setopt($ch, CURLOPT_PROXY, $proxy);
	    curl_setopt($ch, CURLOPT_FOLLOWLOCATION, true);
	    curl_setopt($ch, CURLOPT_RETURNTRANSFER, false);
	    //curl_setopt($ch, CURLOPT_HTTPPROXYTUNNEL, true);
	    if (isset($proxyUser) and $proxyUser and isset($proxyPassword) and $proxyPassword) {
	      $proxyauth="$proxyUser:$proxyPassword";
	      curl_setopt($ch, CURLOPT_PROXYUSERPWD, $proxyauth);
	    }
	  } else {
	    curl_setopt($ch, CURLOPT_NOBODY, true );
	    curl_setopt($ch, CURLOPT_HEADER, false );
	    curl_setopt($ch, CURLOPT_TIMEOUT_MS, 1000);
	    curl_setopt($ch, CURLOPT_RETURNTRANSFER, false );
	    curl_setopt($ch, CURLOPT_FOLLOWLOCATION, true );
	    curl_setopt($ch, CURLOPT_MAXREDIRS, 3 );
	  }
	  traceLog('Cron stopped at '.date('d/m/Y H:i:s').' for automatic restart'); 
	  self::removeRunningFlag();
	  self::storeHistory("autoRestart");
	  $error=null;
	  try {
	    $curl_response = curl_exec( $ch );
	    if ($curl_response == false) {
	      $error=curl_error($ch);
	    }
	    //curl_close($curl);
	  } catch (Exception $ex) {
	    $error=$e->getMessage;
	  }
	  if ($error and strPos($error,'timed out')===false) {
	    traceLog("Error when trying to start new Cron, calling url '$url'");
	    traceLog($error);
	    traceLog("Could not start new Cron, so current one continues (possibly with old code)");
	    return;
	  }
	  sleep(2);
	  curl_close( $ch );
	  Cron::$cronRequestedStop=true;
	  exit;
	}
	
	public static function run() {
//scriptLog('Cron::run()');	
    self::$cronProcessId=getmypid();
    self::$cronUniqueId=uniqid('',true);
    global $cronnedScript, $i18nMessages, $currentLocale ,$paramCronWaitDb, $browserLocaleDateFormat, $browserLocale, $browserLocaleTimeFormat ;
    $cronnedScript=true; // Defined and set to be able to force rights on Control() : Cron has all rights.
    self::init();  
    $i18nMessages=null;
    $currentLocale=Parameter::getGlobalParameter ( 'paramDefaultLocale' );
    $browserLocale=Parameter::getGlobalParameter ( 'paramDefaultLocale' );
    $browserLocaleTimeFormat=Parameter::getGlobalParameter('cronTimeFormat');
    $browserLocaleDateFormat=Parameter::getGlobalParameter('cronDateFormat');
    if (!$browserLocaleDateFormat) $browserLocaleDateFormat=Parameter::getUserParameter("browserLocaleDateFormat");
    if (!$browserLocaleTimeFormat) $browserLocaleDateFormat=Parameter::getUserParameter("browserLocaleTimeFormat");
		if (self::check()=='running') {
      errorLog('Try to run cron already running - Exit');
      session_write_close();
      exit;
    }
    $inCronBlockFonctionCustom=true;
    self::removeDeployFlag();
    self::removeRestartFlag();
    projeqtor_set_time_limit(0);
    ignore_user_abort(1);
    error_reporting(0);
    session_write_close();
    error_reporting(E_ERROR);
// BEGIN - ADD BY TABARY - NOTIFICATION SYSTEM
    $cronCheckNotifications=-1;
    if (isNotificationSystemActiv()) {
        $cronCheckNotifications=self::getCheckNotifications();
    }
// END - ADD BY TABARY - NOTIFICATION SYSTEM
// MTY - LEAVE SYSTEM
    $cronCheckLeavesEarned=-1;
    if (isLeavesSystemActiv()) {
        $cronCheckLeavesEarned=self::getCheckLeavesEarned();
    }
// MTY - LEAVE SYSTEM
    $cronCheckDates=self::getCheckDates();
    $cronCheckImport=self::getCheckImport();
    $cronCheckEmails=self::getCheckEmails();
    $cronCheckMailGroup=self::getCheckMailGroup();
    $cronSleepTime=self::getSleepTime();
    self::setActualTimes();
    self::removeStopFlag();
    self::setRunningFlag();
    self::storeHistory("run");
    // PBER Force Cron User
    $cronUser=new User();
    $cronUser->idCalendarDefinition=1;
    $cronUser->idProfile=1;
    $cronUser->resetAllVisibleProjects();
    setSessionUser($cronUser);
    traceLog('Cron started at '.date('d/m/Y H:i:s')); 
    self::$startCnxIssue=null;
    $timer=null;
    while(1) {
      if (file_exists(self::$restartFile)) {
        self::removeRestartFlag();
        self::removeStopFlag();
        self::autoRestart();
      }
      if (self::checkStopFlag()) {
        self::removeRestartFlag();
        self::removeStopFlag();
        self::storeHistory("stop");
        return; 
      }
      self::checkDuplicateRunning();
      $cnxResult=Sql::reconnect(); // Force reconnection to avoid "mysql has gone away"
      self::setRunningFlag();
      if (! $cnxResult) {
        if (self::$startCnxIssue==null) {
          self::$startCnxIssue=date("Y-m-d H:i:s");
        } else {
          self::$waitDbTimer =pq_strtotime('+30 minutes', pq_strtotime(self::$startCnxIssue));
          if(isset($paramCronWaitDb)){
            self::$waitDbTimer=$paramCronWaitDb+pq_strtotime(self::$startCnxIssue);
          }
          if(self::$waitDbTimer<= pq_strtotime(date("Y-m-d H:i:s"))){
            errorLog("SQL ERROR : Connection to Database failed");
            errorLog("   the waiting time has expired. ");
            errorLog("   Cron was stopped. ");
            self::$startCnxIssue=null;
            self::storeHistory("set stop flag for db error connexion failed waiting time for connect db has expired");
            self::removeRunningFlag();
            self::setStopFlag();
            break;
          }else{
            $cronnedScript=true;
          }
        }
        sleep($cronSleepTime);
        continue;
      } else {
        self::$startCnxIssue=null;
      }
      // CheckDates : automatically raise alerts based on dates
      if ($cronCheckDates>0) {
	      $cronCheckDates-=$cronSleepTime;
	      if ($cronCheckDates<=0) {
	      	try { 
	          self::checkDates();
	      	} catch (Exception $e) {
	      		traceLog("Cron::run() - Error on checkDates()");
	      	}
	        $cronCheckDates=Cron::getCheckDates();
	      }
      }
      // CheckImport : automatically import some files in import directory
      if ($cronCheckImport>0) {
	      $cronCheckImport-=$cronSleepTime;
	      if ($cronCheckImport<=0) {
	      	try { 
	          self::checkImport();
	      	} catch (Exception $e) {
	          traceLog("Cron::run() - Error on checkImport()");
	        }
	        $cronCheckImport=Cron::getCheckImport();
	      }
      }
      // CheckEmails : automatically import notes from Reply to mails
//       try {
//         self::checkEmails();
//       } catch (Exception $e) {
//         traceLog("Cron::run() - Error on checkEmails()");
//       }
      if ($cronCheckEmails>0) {
	      $cronCheckEmails-=$cronSleepTime;
	      if ($cronCheckEmails<=0) {
	        try {
	          self::checkEmails();
	        } catch (Exception $e) {
	          traceLog("Cron::run() - Error on checkEmails()");
	        }
	        $cronCheckEmails=Cron::getCheckEmails();
	      }
      }
      // CheckEmails : automatically import notes from Reply to mails
      if ($cronCheckMailGroup>0) {
        $cronCheckMailGroup-=$cronSleepTime;
        if ($cronCheckMailGroup<=0) {
          try {
            self::checkMailGroup();
          } catch (Exception $e) {
            traceLog("Cron::run() - Error on checkMailGroup()");
          }
          $cronCheckMailGroup=Cron::getCheckMailGroup();
        }
      }
      
      // Check Database Execution
      foreach (self::$listCronExecution as $key=>$cronExecution){
        if($cronExecution->nextTime===null){
          $cronExecution->calculNextTime();
        }
        $UTC=new DateTimeZone(Parameter::getGlobalParameter ( 'paramDefaultTimezone' ));
        $date=new DateTime('now');
        if($cronExecution->fileExecuted and file_exists($cronExecution->fileExecuted) and $cronExecution->nextTime!=null and $cronExecution->nextTime<=$date->format("U")){
          self::$lastCronTimeExecution = $cronExecution->nextTime;
          self::$lastCronExecution = $cronExecution->cron;
          $cronExecution->calculNextTime();
          call_user_func($cronExecution->fonctionName);
        }
      }
      
      // Check Database Execution for auto send report damian
      foreach (getlistCronAutoSendReport() as $key=>$cronAutoSendReport){
      	if($cronAutoSendReport->nextTime===null){
      		$cronAutoSendReport->calculNextTime();
      	}
      	$UTC=new DateTimeZone(Parameter::getGlobalParameter ( 'paramDefaultTimezone' ));
      	$date=new DateTime('now');
      	$resource = new Resource($cronAutoSendReport->idResource);
      	if($cronAutoSendReport->nextTime!=null && $cronAutoSendReport->nextTime<=$date->format("U")){
      		self::$lastCronTimeAutoSendReport = $cronAutoSendReport->nextTime;
      		self::$lastCronAutoSendReport = $cronAutoSendReport->cron;
      		if($cronAutoSendReport->sendFrequency != 'everyOpenDays'){
      		  $cronAutoSendReport->sendReport($cronAutoSendReport->idReport, $cronAutoSendReport->reportParameter);
      		}else{
      		  if(isOpenDay(date('Y-m-d'), $resource->idCalendarDefinition)){
      		    $cronAutoSendReport->sendReport($cronAutoSendReport->idReport, $cronAutoSendReport->reportParameter);
      		  }
      		}
      		$cronAutoSendReport->calculNextTime();
      	}
      }
      
// BEGIN - ADD BY TABARY - NOTIFICATION SYSTEM
      // CheckNotifications : automatically generate notifications
      if (isNotificationSystemActiv() and $cronCheckNotifications>0 ) {
        $cronCheckNotifications-=$cronSleepTime;
        if ($cronCheckNotifications<=0) {
          try { 
            self::checkNotifications();
          } catch (Exception $e) {
            traceLog("Cron::run() - Error on checkNotifications()");
          }
          $cronCheckNotifications=Cron::getCheckNotifications();
        }
      }
// END - ADD BY TABARY - NOTIFICATION SYSTEM
		
// MTY - LEAVE SYSTEM
      // CheckLeavesEarned : automatically calculed quantity and left for leaves earned
      if (isLeavesSystemActiv() and $cronCheckLeavesEarned>0 ) {
        $cronCheckLeavesEarned-=$cronSleepTime;
        if ($cronCheckLeavesEarned<=0) {
          try { 
            self::checkLeavesEarned();
          } catch (Exception $e) {
            traceLog("Cron::run() - Error on checkLeavesEarned()");
          }
          $cronCheckLeavesEarned=Cron::getCheckLeavesEarned();
        }
      }
// MTY - LEAVE SYSTEM
      
      // Sleep to next check
      sleep($cronSleepTime);
    } // While 1
  }
  
// BEGIN - ADD BY TABARY - NOTIFICATION SYSTEM
  public static function checkNotifications() {      
//scriptLog('Cron::checkNotifications()');
    global $globalCronMode;
    if (!isNotificationSystemActiv()) {return;}
    self::init();
    $globalCronMode=true;  
    // Generates notification from notification Definition
    $notifDef = new NotificationDefinition();
    $crit = array("idle" => '0');
    $lstNotifDef=$notifDef->getSqlElementsFromCriteria($crit);    
    foreach($lstNotifDef as $notifDef) {
        $notifDef->generateNotifications();
    }
  
    // Generates email notification
    $currentDate = date('Y-m-d');
    $currentTime = date('H:i:s');
    $crit = "idle=0 and sendEmail=1 and emailSent=0 and ( notificationDate<'$currentDate' or (notificationDate='$currentDate' and notificationTime<'$currentTime') )";
    $notif = new Notification();
    $lstNotif = $notif->getSqlElementsFromCriteria(null,false,$crit);
    foreach($lstNotif as $notif) {
      $notif->sendEmail();
    }
  }// END - ADD BY TABARY - NOTIFICATION SYSTEM
    
// MTY - LEAVE SYSTEM
  public static function checkLeavesEarned() {      
//scriptLog('Cron::checkLeavesEarned()');
    global $globalCronMode;
    if (!isLeavesSystemActiv()) {return;}
    self::init();
    $globalCronMode=true;  
    
    // Check for all employees
    $employee = new Employee();
    $crit = array("idle" => '0');
    $employeesList = $employee->getSqlElementsFromCriteria($crit);
    foreach($employeesList as $emp) {
        $employees[$emp->id] = $emp->name;
    }
    if (!empty($employees)) {        
        foreach ($employees as $key=>$emp) {
            $res = checkLeaveEarnedEnd($key);
            if ($res=='OK') { 
                $res = checkValidity($key);
                if ($res=='OK') { 
                    $res = checkEarnedPeriod($key);
                    if ($res!='OK') {
                        $msg = "ERROR - Cron - $res";                        
                    }
                } else {
                $msg = "ERROR - Cron - $res";                    
                }
            } else {
                $msg = "ERROR - Cron - $res";
            }
        }
    }
  }
// MTY - LEAVE SYSTEM
  
    public static function checkDates() {
//scriptLog('Cron::checkDates()');
  	global $globalCronMode;
    self::init();
    $globalCronMode=true;  
    $indVal=new IndicatorValue();
    $where="type='delay' and idle=0 and (";
	  // If YEARLY, even if warning and alert have been sent, check if we need to update targetDateTime
    $where.=" ( warningTargetDateTime<='" . date('Y-m-d H:i:s') . "' and (warningSent=0 or code = 'YEARLY'))" ;
    $where.=" or ( alertTargetDateTime<='" . date('Y-m-d H:i:s') . "' and (alertSent=0 or code = 'YEARLY'))" ;
    $where.=")";
    $lst=$indVal->getSqlElementsFromCriteria(null, null, $where);

    foreach ($lst as $indVal) {
      $indVal->checkDates();
    }
  }
  
//---------checkImport----------
  public static function checkImport() {
    //scriptLog('Cron::checkImport()');
    cron::init();
    global $globalCronMode, $globalCatchErrors;
    $globalCronMode=true;
    $globalCatchErrors=true;
    $importDir=Parameter::getGlobalParameter('cronImportDirectory');
    $eol=Parameter::getGlobalParameter('mailEol');
    $cpt=0;
    $pathSeparator=Parameter::getGlobalParameter('paramPathSeparator');
    $importSummary="";
    $importFullLog="";
    $attachmentArray=array();
    $boundary = null;
    $importFileArray=array();
    if (is_dir($importDir)) {
      if ($dirHandler = opendir($importDir)) {
        while (($file = readdir($dirHandler)) !== false) {
          if ($file!="." and $file!=".." and filetype($importDir . $pathSeparator . $file)=="file") {
            $globalCronMode=true; // Cron should not be stopped on error or exception
            $importFile=$importDir . $pathSeparator . $file;
            $pos=pq_strpos($file,'_');
            if ($pos>0) {
              $timestamp=pq_substr($file,$pos+1).'_'.$cpt;
            } else {
              $timestamp=date('Ymd_his').'_'.$cpt;
            }
            $importFileArray[$timestamp]=$importFile;
          }
        }
        ksort($importFileArray);
        foreach ($importFileArray as $importFile) {
          $file=basename($importFile);
          $split=pq_explode('_',$file);
          $class=$split[0];
          $result="";
          try {
            $result=Importable::import($importFile, $class);
          } catch (Exception $e) {
            $msg="CRON : Exception on import of file '$importFile'";
            $result="ERROR";
          }
          $globalCronMode=false; // VOLOUNTARILY STOP THE CRON. Actions are requested !
          try {
            if ($result=="OK") {
              $msg="Import OK : file $file imported with no error [ Number of '$class' imported : " . Importable::$cptDone . " ]";
              traceLog($msg);
              $importSummary.="<span style='color:green;'>$msg</span><br/>";
              if (! is_dir($importDir . $pathSeparator . "done")) {
                mkdir($importDir . $pathSeparator . "done",0777,true);
                 
              }
              rename($importFile,$importDir . $pathSeparator . "done" . $pathSeparator . $file);
            } else {
              if ($result=="INVALID") {
                $msg="Import INVALID : file $file imported with " . Importable::$cptInvalid . " control errors [ Number of '$class' imported : " . Importable::$cptOK . " ]";
                traceLog($msg);
                $importSummary.="<span style='color:orange;'>$msg</span><br/>";
              } else {
                $msg="Import ERROR : file $file imported with " . Importable::$cptRejected . " errors [ Number of '$class' imported : " . Importable::$cptOK . " ]";
                traceLog($msg);
                $importSummary.="<span style='color:red;'>$msg</span><br/>";
              }
              if (! is_dir($importDir . $pathSeparator . "error")) {
                mkdir($importDir . $pathSeparator . "error",0777,true);
              }
              rename($importFile,$importDir . $pathSeparator . "error" . $pathSeparator . $file);
            }
          } catch (Exception $e) {
            $msg="CRON : Impossible to move file '$importFile'";
            traceLog($msg);
            $importSummary.="<span style='color:red;'>$msg</span><br/>";
            $msg="CRON IS STOPPED TO AVOID MULTIPLE-TREATMENT OF SAME FILES";
            traceLog($msg);
            $importSummary.="<span style='color:red;'>$msg</span><br/>";
            $msg="Check access rights to folder '$importDir', subfolders 'done' and 'error' and file '$importFile'";
            traceLog($msg);
            $importSummary.="<span style='color:red;'>$msg</span><br/>";
            exit; // VOLOUNTARILY STOP THE CRON. Actions are requested !
          }
          $globalCronMode=true; // If cannot write log file, do not exit CRON (not blocking)
          $logFile=$importDir . $pathSeparator . 'logs' . $pathSeparator . pq_substr($file, 0, pq_strlen($file)-4) . ".log.htm";
          if (! is_dir($importDir . $pathSeparator . "logs")) {
            mkdir($importDir . $pathSeparator . "logs",0777,true);
          }
          if (file_exists($logFile)) {
            kill($logFile);
          }
          // Write log file
          $fileHandler = fopen($logFile, 'w');
          fwrite($fileHandler, Importable::getLogHeader());
          fwrite($fileHandler, Importable::$importResult);
          fwrite($fileHandler, Importable::getLogFooter());
          fclose($fileHandler);
          // Prepare joined file on email
          if (Parameter::getGlobalParameter('cronImportLogDestination')=='mail+log') {
            if (! isset($paramMailerType) or $paramMailerType=='phpmailer') {
              $attachmentArray[]=$logFile;
            } else { // old way to send attachments
              if (! $boundary) {
                $boundary = md5(uniqid(microtime(), TRUE));
              }
              $file_type = 'text/html';
              $content = Importable::getLogHeader();
              $content .= Importable::$importResult;
              $content .= Importable::getLogFooter();
              $content = chunk_split(base64_encode($content));
              $importFullLog .= $eol.'--'.$boundary.$eol;
              $importFullLog .= 'Content-type:'.$file_type.';name="'.basename($logFile).'"'.$eol;
              $importFullLog .= 'Content-Length: ' . pq_strlen($content).$eol;
              $importFullLog .= 'Content-transfer-encoding:base64'.$eol;
              $importFullLog .= 'Content-disposition: attachment; filename="'.basename($logFile).'"'.$eol;
              $importFullLog .= $eol.$content.$eol;
              $importFullLog .= '--'.$boundary.$eol;
            }
          }
          $cpt+=1;
        }
        closedir($dirHandler);
      }
    } else {
      $msg="ERROR - check Cron::Import() - ". $importDir . " is not a directory";
      traceLog($msg);
      $importSummary.="<span style='color:red;'>$msg</span><br/>";
    }
    if ($importSummary) {
      $logDest=Parameter::getGlobalParameter('cronImportLogDestination');
      if (pq_stripos($logDest,'mail')!==false) {
        $baseName=Parameter::getGlobalParameter('paramDbDisplayName');
        $to=Parameter::getGlobalParameter('cronImportMailList');
        if (! $to) {
          traceLog("Cron : email requested, but no email address defined");
        } else {
          $message=$importSummary;
          if (pq_stripos($logDest,'log')!==false) {
            $message=Importable::getLogHeader().$message;
            if($importFullLog) $message.=$eol.$importFullLog;
            Importable::getLogFooter();
          }
          $title="[$baseName] Import summary ". date('Y-m-d H:i:s');
          $resultMail=sendMail($to, $title, $message, null, null, null, $attachmentArray, $boundary);
        }
      }
    }
  }
  
  public static function checkEmails() {	
  	self::init();
    global $globalCronMode, $globalCatchErrors;
    $globalCronMode=true;     
    $globalCatchErrors=true;
    $checkEmails=Parameter::getGlobalParameter('cronCheckEmails');
    if (!$checkEmails or intval($checkEmails)<=0) {
      return; // disabled
    }
    // TODO ImpaMailbox2 only for PHP >= 8.2
    //require_once("../model/ImapMailbox.php"); // Imap management Class
    require_once("../model/ImapMailbox2.php"); // Imap management Class - New version Compliant with oAuth2
    if (! ImapMailbox::checkImapEnabled()) {
      traceLog("ERROR - Cron::checkEmails() - IMAP extension not enabled in your PHP config. Cannot connect to IMAP Mailbox.");
      return;
    }
//     $afterMailTreatment = Parameter::getGlobalParameter('afterMailTreatment');
    //gautier #inputMailbox
    //remi
//     $inputMbT = new InputMailboxTicket(); 
//     $inputMbI = new InputMailboxImport();
    InputMailboxTicket::checkEmailsTicket();
    InputMailboxImport::checkEmailsImport();
    
    
  }
  
  public static function checkMailGroup() {
    self::init();
    global $globalCronMode, $globalCatchErrors, $cronnedMailSender;
    $globalCronMode=true;
    $globalCatchErrors=true;
    $period=Mail::getMailGroupPeriod();
    if ($period<=0) return;
    // Direct SQL : allowed here because very technical query, requiring high performance
    //              attention, in postgresql, fields are always returned in lowercase
    $mts=new MailToSend();
    $mtsTable=$mts->getDatabaseTableName();
    $dateToCheck=date("Y-m-d H:i:s", pq_strtotime(date("Y-m-d H:i:s")) - $period);
    // Get list of items with last stored email (in MailToSend) older than period : must send the emails 
    $query="select refType as reftype, refId as refid, max(recordDateTime) as lastdate from $mtsTable group by refType, refId having max(recordDateTime)<'$dateToCheck'";
    $result = Sql::query($query);
    $arrayMailToSend=array();
    if (Sql::$lastQueryNbRows > 0) {
      $line = Sql::fetchLine($result);
      while ($line) {
        $arrayMailToSend[]=array('refType'=>$line['reftype'], 'refId'=>$line['refid'],'date'=>$line['lastdate']);
        $line = Sql::fetchLine($result);
      }
    } else {
      return;
    }
    // Here, $arrayMailToSend contains 1 line per element for wich mails have to be sent 
    $error=false;
    Sql::beginTransaction();
    $groupRule=Parameter::getGlobalParameter('mailGroupDifferent');
    if (!$groupRule) $groupRule='LAST';
    $idToPurge=array();
    $sepLine="<table style='width:95%'><tr><td style='border-bottom:3px solid #545381'>&nbsp;</td></tr><tr><td>&nbsp;</td></tr></table>";
    foreach ($arrayMailToSend as $toSendItem) { // For each item in $arrayMailToSend
      // List all emails stored in MailToSend for the item
      $refType=$toSendItem['refType'];
      $refId=$toSendItem['refId'];
      $crit=array('refType'=>$refType, 'refId'=>$refId);
      $list=$mts->getSqlElementsFromCriteria($crit,false,null,'recordDateTime desc');
      $item=new $refType($refId);
      $arrayMail=array();
      $last=end($list);
      $lastDate=$last->recordDateTime;
      foreach ($list as $toSend) { // For each email to send
        if ($toSend->recordDateTime>$toSendItem['date']) continue; // Found a brand new email, do not take it into account, will be included in next period loop 
        $idToPurge[]=$toSend->id; // Store ids of MailToSend that need to be purge after sending email
        $key=0; // For $groupRule=='ALL' or $groupRule=='MERGE'
        if ($groupRule=='ALL') $key=$toSend->idEmailTemplate;
        if ( !isset($arrayMail[$key])) {
          if ($toSend->template=='basic') {
            $template=$item->getMailDetail();
          } else {
            $templateObj=new EmailTemplate($toSend->idEmailTemplate);
            $template=$item->getMailDetailFromTemplate($templateObj->template,$lastDate);
          }
          $arrayMail[$key]=array(
            'newerDate'=>$toSend->recordDateTime,
            'olderdate'=>$toSend->recordDateTime,
            'idEmailTemplate'=>$toSend->idEmailTemplate,
            'nameTemplate'=>$toSend->template,
            'template'=>$template,
            'title'=>$toSend->title,
            'allTitles'=>array($toSend->title),
            'allDates'=>array($toSend->recordDateTime),
            'allTemplates'=>array($toSend->template),
            'dest'=>$toSend->dest      
          );
        } else {
          // Merge dest
          $arr1=pq_explode(',',$arrayMail[$key]['dest']);
          $arr2=pq_explode(',',$toSend->dest);
          $arrMerged=array_unique(array_merge($arr1, $arr2));
          $arrayMail[$key]['dest']=implode(',', $arrMerged);
          // Merge titles
          $arrayMail[$key]['allTitles'][]=$toSend->title;
          $arrayMail[$key]['allDates'][]=$toSend->recordDateTime;
          // Merge template (if option is to merge templates)
          if ($groupRule=='MERGE' and ! in_array($toSend->template, $arrayMail[$key]['allTemplates'])) {
            $arrayMail[$key]['allTemplates'][]=$toSend->template;
            $body=$arrayMail[$key]['template'];
            if ($toSend->template=='basic') {
              $template=$item->getMailDetail();
            } else {
              $templateObj=new EmailTemplate($toSend->idEmailTemplate);
              $template=$item->getMailDetailFromTemplate($templateObj->template,$lastDate);
            }
            $body.=$sepLine.$template;
            $arrayMail[$key]['template']=$body;
          }
        }
      }
      foreach ($arrayMail as $mail) {
        $dest=$mail['dest'];
        $title=$mail['title'];
        $body='<html>';
        $body.='<head><title>' . $title .'</title></head>';
        $body.='<body style="font-family: Verdana, Arial, Helvetica, sans-serif;">';
        if (count($mail['allTitles'])>1) {
          $body.="<table style='width:95%'>";
          $body.="<tr><td colspan='2' style='text-align:center;background-color: #E0E0E0;font-weight:bold'>".i18n("mailGroupTitles")."</td></tr>";
          foreach ($mail['allTitles'] as $idx=>$title) {
            $body.="<tr><td style='width:10%;padding:3px 10px'>".htmlFormatDateTime($mail['allDates'][$idx])."</td><td style='padding:3px 10px'>$title</td></tr>";
          }
          $body.="";
          $body.="";
          $body.="</table>";
          $body.=$sepLine;
        }
        $body.=$mail['template'];
        $body.='</body>';
        $body.='</html>';
        $cronnedMailSender=$toSend->idUser;
        $resultMail[] = sendMail($dest, $title, $body, $item, null, null, null, null, null );
      }
    }
    
    // Puge sent emails from MailToSend
    $listId=implode(',',$idToPurge);
    $resPurge=$mts->purge("id in ($listId)");
    
    // Finalize
    if ($error) {
      Sql::rollbackTransaction();
    } else {
      Sql::commitTransaction();
    }
  }
  
}

function getListCronAutoSendReport(){
  //Look if CronAutoSendReport exist in database //damian
  $listCronAutoSendReport=SqlList::getListWithCrit("AutoSendReport", array("idle"=>"0"), 'id');
  $inCronBlockFonctionCustom=true;
  foreach ($listCronAutoSendReport as $key=>$cronAutoSendReport){
  	if(is_numeric($cronAutoSendReport)){
  		$listCronAutoSendReport[$key]=new AutoSendReport($cronAutoSendReport);
  		$cronAutoSendReport=$listCronAutoSendReport[$key];
  	}
  }
  return $listCronAutoSendReport;
}

//Look if CronExecution exist in database
Cron::$listCronExecution=SqlList::getListWithCrit("CronExecution", array("idle"=>"0"), 'id');
$inCronBlockFonctionCustom=true;
foreach (Cron::$listCronExecution as $key=>$cronExecution){
  if(is_numeric($cronExecution)){
    Cron::$listCronExecution[$key]=new CronExecution($cronExecution);
    $cronExecution=Cron::$listCronExecution[$key];
  }
  if ($cronExecution->fileExecuted) require_once $cronExecution->fileExecuted;
}

?>