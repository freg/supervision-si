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
$auto=$_REQUEST['autorestartkey']??null;
$usrId=null;
$autoFileName='../files/cron/AUTO';
if ($auto and file_exists($autoFileName)) {
  $autoFile=file_get_contents($autoFileName);
  $split=explode("|",$autoFile);
  $autoCheck=$split[0];
  if ($autoCheck==$auto) {
    $usrId=$split[1];
    $batchMode=1;
  }
  unlink($autoFileName);
}
require_once "../tool/projeqtor.php";
if (isset($batchMode) and $batchMode==1) {
  if ($usrId) {
    $user=new User($usrId);
    setSessionUser($user);
  } else {
    // PBER Force Cron User
    $cronUser=new User();
    $cronUser->idCalendarDefinition=1;
    $cronUser->idProfile=1;
    $cronUser->resetAllVisibleProjects();
    setSessionUser($cronUser);
  }
}
if (! isset($batchMode) and ! Security::checkDisplayMenuForUser('Admin',false)) {
  if (! Security::checkDisplayMenuForUser('GlobalParameter',false)) {
    traceHack("cronRun() Reject for user withouit access to 'Admin' and 'GlobalParameter");
  }
}
function cronAbort() {Cron::abort();}
register_shutdown_function('cronAbort');
//Cron::init();
Cron::$cronRequestedStop=false;
Cron::run();