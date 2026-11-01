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

require_once "../tool/projeqtor.php";
Security::checkDisplayMenuForUser('Admin');
global $cronnedScript;
if ($cronnedScript!==true and securityGetAccessRightYesNo('menuAdmin','read')!='YES') {
  traceHack ( "admin functionality reached without access right" );
  exit ();
}
scriptLog("adminFunctionalities.php");
if (pq_array_key_exists('adminFunctionality', $_REQUEST)) {
	$adminFunctionality=$_REQUEST['adminFunctionality'];
}
if (! isset($adminFunctionality)) {
	echo "ERROR - functionality not defined";
	return;
}

Sql::beginTransaction();
$nbDays=(pq_array_key_exists('nbDays', $_REQUEST))?$_REQUEST['nbDays']:'';
$nbDays=Security::checkValidInteger(intval($nbDays));

if ($adminFunctionality=='sendAlert') {
	$result=sendAlert();
} else if ($adminFunctionality=='maintenance') {
	$result=maintenance();
} else if ($adminFunctionality=='updateReference') {
	$element=null;
	if (pq_array_key_exists('element', $_REQUEST)) {
	  $element=$_REQUEST['element'];
	}
	if ($element=='*') {
		$element=null;
	}
	else {
		if (intval($element)>0) {
			$elt=new Referencable($element);
			$element=$elt->name;
		}
		$element=Security::checkValidClass($element);
	}
	$result=updateReference($element);
} else if ($adminFunctionality=='disconnectAll') {
  $audit=new Audit();
  $list=$audit->getSqlElementsFromCriteria(array("idle"=>"0"));
  $result=i18n('colRequestDisconnection').'<input type="hidden" id="lastSaveId" value="" /><input type="hidden" id="lastOperation" value="update" /><input type="hidden" id="lastOperationStatus" value="NO_CHANGE" />';
  foreach($list as $audit) {
  	if ($audit->sessionId!=session_id()) {
      $audit->requestDisconnection=1;
      $res=$audit->save();
      $userAudit=new User($audit->idUser);
      if ($userAudit->id) {
        $userAudit->cleanCookieHash();
        $userAudit->stopAllWork();
      }
      $result=i18n('colRequestDisconnection').'<input type="hidden" id="lastSaveId" value="" /><input type="hidden" id="lastOperation" value="update" /><input type="hidden" id="lastOperationStatus" value="OK" />';      
  	}   	
  }
} else if ($adminFunctionality=='setApplicationStatusTo') { 
	$newStatus=$_REQUEST['newStatus'];
	$newStatus=Security::checkValidAlphanumeric($newStatus);
	$crit=array('idUser'=>null, 'idProject'=>null, 'parameterCode'=>'applicationStatus');
  $obj=SqlElement::getSingleSqlElementFromCriteria('Parameter', $crit);
  $obj->parameterValue=$newStatus;
  $result=$obj->save();
  $param=SqlElement::getSingleSqlElementFromCriteria('Parameter',array('idUser'=>null, 'idProject'=>null, 'parameterCode'=>'msgClosedApplication'));
  $fromSubscriptionUpdate = RequestHandler::getBoolean('fromSubscriptionUpdate');
  if(!$fromSubscriptionUpdate)
  {
    $msgClosedApplication=$_REQUEST['msgClosedApplication'];
    $msgClosedApplication=strip_tags($msgClosedApplication);
    $param->parameterValue=$msgClosedApplication;
    $param->save();
  }
  Parameter::clearGlobalParameters();
} else if ($adminFunctionality=='checkConsistency') {
  projeqtor_set_time_limit(900);
  $correct=RequestHandler::getBoolean('correct');
  IndicatorValue::$_doNotUpdate=true;
  if ($correct) SqlElement::$_skipAllControls=true;
  echo "<div class='consistencySection' style='background-color:#A0A0C0;'>".i18n('sectionCheckWbs')."</div>";
  Consistency::checkWbs($correct,false);
  echo "<div class='consistencySection' style='background-color:#A0A0C0;'>".i18n('sectionCheckBbs')."</div>";
  Consistency::checkBbs($correct,false);
  Sql::commitTransaction();
  Sql::beginTransaction();
  echo "<div class='consistencySection' style='background-color:#A0A0C0;'>".i18n('sectionCheckSbs')."</div>";
  Consistency::checkSbs($correct,false);
  Sql::commitTransaction();
  Sql::beginTransaction();
  echo "<div class='consistencySection' style=''>".i18n('sectionCheckWorkDuplicate')."</div>";
  Consistency::checkDuplicateWork($correct, false);
  Sql::commitTransaction();
  Sql::beginTransaction();
  echo "<div class='consistencySection' style=''>".i18n('sectionCheckWorkOnTicket')."</div>";
  Consistency::checkWorkOnTicket($correct, false);
  Sql::commitTransaction();
  Sql::beginTransaction();
  echo "<div class='consistencySection' style=''>".i18n('sectionCheckWorkOnAssignment')."</div>";
  Consistency::checkWorkOnAssignment($correct, false);
  Sql::commitTransaction();
  Sql::beginTransaction();
  echo "<div class='consistencySection' style=''>".i18n('sectionCheckIdlePropagation')."</div>";
  Consistency::checkIdlePropagation($correct, false);
  Sql::commitTransaction();
  Sql::beginTransaction();
  echo "<div class='consistencySection' style=''>".i18n('sectionCheckMissingPlanningElement')."</div>";
  Consistency::checkMissingPlanningElement($correct, false);
  Sql::commitTransaction();
  Sql::beginTransaction();
  echo "<div class='consistencySection' style=''>".i18n('sectionCheckWorkOnActivity')."</div>";
  Consistency::checkWorkOnActivity($correct, false);
  Sql::commitTransaction();
  Sql::beginTransaction();
  echo "<div class='consistencySection' style=''>".i18n('sectionCheckWorkOnMeeting')."</div>";
  Consistency::checkWorkOnMeeting($correct, false);
  Sql::commitTransaction();
  Sql::beginTransaction();
  echo "<div class='consistencySection' style=''>".i18n('sectionCheckAssignmentOnPeriodicMeeting')."</div>";
  Consistency::checkPeriodicMeetingAssign($correct, false);
  Sql::commitTransaction();
  Sql::beginTransaction();
  echo "<div class='consistencySection' style=''>".i18n('sectionCheckBudget')."</div>";
  Consistency::checkBudget($correct, false);
  Sql::commitTransaction();
  Sql::beginTransaction();
  echo "<div class='consistencySection' style=''>".i18n('sectionCheckTechnicalData')."</div>";
  Consistency::checkInvalidFilters($correct, false);
  Sql::commitTransaction();
  Sql::beginTransaction();
  echo "<div class='consistencySection' style=''>".i18n('sectionCheckPool')."</div>";
  Consistency::checkPools($correct, false);
  Sql::commitTransaction();
  Sql::beginTransaction();
  echo "<div class='consistencySection' style=''>".i18n('sectionCheckProject')."</div>";
  Consistency::checkProject($correct, false); 
  Sql::commitTransaction();
  Sql::beginTransaction();
  echo "<div class='consistencySection' style=''>".i18n('sectionCheckAssignmentSelection')."</div>";
  Consistency::checkAssignmentSelection($correct, false);
  Sql::commitTransaction();
  Sql::beginTransaction();
  echo "<div class='consistencySection'>" . i18n('sectionCheckSubTaskProject') . "</div>";
  Consistency::checkSubTaskProject($correct, false, true);
  Sql::commitTransaction(); 
  Sql::beginTransaction();
  IndicatorValue::$_doNotUpdate=false;
  if ($correct) SqlElement::$_skipAllControls=false;
  $result=false;
  Sql::commitTransaction();
} else if ($adminFunctionality == 'renumberWbs') {
    $planningElement = new PlanningElement();
    $result=$planningElement->renumberWbs(true, true);
    $fixOrder=$planningElement->renumberWbs(true, false);
    $result .= '<input type="hidden" id="lastOperation" value="insert" />';
    $result .= '<input type="hidden" id="lastOperationStatus" value="OK" />';
} else if ($adminFunctionality == 'executeWaitingUpdates') {
    // Manual, on-demand run of every pending deferred consolidation (WaitingUpdate),
    // same processing as the CRON task cronExecuteWaitingUpdates
    $nbProcessed = WaitingUpdate::executeWaiting(true);
    $result = i18n('treatmentEnded') . ' (' . $nbProcessed . ')';
    $result .= '<input type="hidden" id="lastOperation" value="insert" />';
    $result .= '<input type="hidden" id="lastOperationStatus" value="OK" />';
} else {
	traceHack("Functionality '$adminFunctionality' not defined");
	$result=false;
}

// Message for result
if ($result) displayLastOperationStatus($result);

function sendAlert(){
  $alertSendTo=(pq_array_key_exists('alertSendTo', $_REQUEST))?$_REQUEST['alertSendTo']:'';
  if ($alertSendTo!='*') {
    $alertSendTo=Security::checkValidAlphanumeric($alertSendTo);
  }
  $alertSendDate=(pq_array_key_exists('alertSendDate', $_REQUEST))?$_REQUEST['alertSendDate']:'';
  $alertSendDate=Security::checkValidDateTime($alertSendDate);
  $alertSendTime=(pq_array_key_exists('alertSendTime', $_REQUEST))?$_REQUEST['alertSendTime']:'';
  $alertSendTime=Security::checkValidDateTime($alertSendTime);
  $alertSendType=(pq_array_key_exists('alertSendType', $_REQUEST))?$_REQUEST['alertSendType']:''; // Note: escaped before use using htmlspecialchars().
  $alertSendTitle=(pq_array_key_exists('alertSendTitle', $_REQUEST))?$_REQUEST['alertSendTitle']:''; // Note: escaped before use using htmlspecialchars().
  $alertSendMessage=(pq_array_key_exists('alertSendMessage', $_REQUEST))?$_REQUEST['alertSendMessage']:''; // Note: escaped before use using htmlspecialchars().
  $ctrl="";
  if (! pq_trim($alertSendTitle)) {
    $ctrl.= i18n("messageMandatory", array(i18n('colTitle'))).'<br/>';
  }
  if (! pq_trim($alertSendMessage)) {
   $ctrl.=i18n("messageMandatory", array(i18n('colMessage'))).'<br/>';
  }
  if ($ctrl) {
  	$returnValue= $ctrl;
    $returnValue .= '<input type="hidden" id="lastOperation" value="control" />';
    $returnValue .= '<input type="hidden" id="lastOperationStatus" value="ERROR" />';
    return $returnValue;
  }
  $lstUser=array();
  if ($alertSendTo=='*') {
    $lstUser=SqlList::getList('User');
  } else if ($alertSendTo=='connect'){
    $audit=new Audit();
    $lst=$audit->getSqlElementsFromCriteria(array('idle'=>'0'));
    foreach($lst as $audit) {
      $lstUser[$audit->idUser]='';
    }
  } else {
 	  $lstUser[$alertSendTo]='';
  }
  //Sql::beginTransaction();
  foreach ($lstUser as $id=>$name) {
 	  $alert=new Alert();
 	  $alert->idUser=$id;
    $alert->alertType=pq_htmlspecialchars($alertSendType,ENT_QUOTES,'UTF-8');
    $alert->alertInitialDateTime=$alertSendDate . " " . pq_substr($alertSendTime,1);
    $alert->alertDateTime=$alertSendDate . " " . pq_substr($alertSendTime,1);
    $alert->title=pq_htmlspecialchars($alertSendTitle,ENT_QUOTES,'UTF-8');
    $alert->message=pq_htmlspecialchars($alertSendMessage,ENT_QUOTES,'UTF-8');
    $alert->save();
  }
  $returnValue= i18n('sentAlertTo',array(count($lstUser)));
  $returnValue .= '<input type="hidden" id="lastOperation" value="insert" />';
  $returnValue .= '<input type="hidden" id="lastOperationStatus" value="OK" />';
  //Sql::commitTransaction();
  return $returnValue;
}

function maintenance() {
	$operation=(pq_array_key_exists('operation', $_REQUEST))?$_REQUEST['operation']:'';
	$item=(pq_array_key_exists('item', $_REQUEST))?$_REQUEST['item']:'';
	$nbDays=(pq_array_key_exists('nbDays', $_REQUEST))?$_REQUEST['nbDays']:'0'; // Note: already filtered at top of file.
	$ctrl="";
  if (! pq_trim($operation) or ($operation!='delete' and $operation!='close' and $operation!='read')) {
    $ctrl.='ERROR<br/>';
	  traceHack("invalid operation value - $operation");
	  Sql::rollbackTransaction();
	  exit;
  }
  if (! pq_trim($item) or ($item!='Alert' and 
                        $item!='Mail' and 
                        $item!='Audit' and
// BEGIN - ADD BY TABARY -NOTIFICATION SYSTEM
                        $item!='Notification' and
// END - ADD BY TABARY -NOTIFICATION SYSTEM          
                        $item!="Logfile")) {
    $ctrl.='ERROR<br/>';
	  traceHack("invalid item value - $item");
	  Sql::rollbackTransaction();
	exit;
  }
  if ( pq_trim($nbDays)=='' or (intval($nbDays)=='0' and $nbDays!='0')) {
    $ctrl.= i18n("messageMandatory", array(i18n('days'))) .'<br/>';
  }
  //echo '|'.$operation.'|'.$item.'|'.intval($nbDays).'|';
  if ($ctrl) {
    $returnValue= $ctrl;
    $returnValue .= '<input type="hidden" id="lastOperation" value="control" />';
    $returnValue .= '<input type="hidden" id="lastOperationStatus" value="ERROR" />';
    return $returnValue;
  }
  $targetDate=addDaysToDate(date('Y-m-d'), (-1)*$nbDays ) . ' ' . date('H:i');
  $obj=new $item();
  $clauseWhere="1=0";
  if ($item=="Alert") {
  	$clauseWhere="alertInitialDateTime<'" . $targetDate . "'"; 
  } else if ($item=="Mail") {
  	$clauseWhere="mailDateTime<'" . $targetDate . "'";
  } else if ($item=="Audit") {
    $clauseWhere="disconnectionDateTime<'" . $targetDate . "'";
  } else if ($item=="Logfile") {
    $clauseWhere=$targetDate;
// BEGIN - ADD BY TABARY -NOTIFICATION SYSTEM
  } else if ($item=="Notification") {
    $targetDate=addDaysToDate(date('Y-m-d'), (-1)*$nbDays );
    $clauseWhere="notificationDate<'" . $targetDate . "'";      
// END - ADD BY TABARY -NOTIFICATION SYSTEM  
  }
  if ($operation=="close") {
  	if ($item=="Alert") {
  	  $obj->read($clauseWhere);
  	}
    return $obj->close($clauseWhere);
  } else if ($operation=="delete") {
    return $obj->purge($clauseWhere);
  } else if ($operation=="read" and $item=="Alert") {
    $clauseWhere="readFlag=0 and idUser=".getSessionUser()->id;
    return $obj->read($clauseWhere);
  }
}

function updateReference($element) {
	$arrayElements=array();
	if ($element) {
		$arrayElements[]=pq_ucfirst($element);
	} else {
		$list=SqlList::getListNotTranslated('Referencable');
		foreach ($list as $ref) {		
			$arrayElements[]=$ref;
		}
	}
	$cptCommit=100;
	// Sql::beginTransaction(); already done
	foreach ($arrayElements as $elt) {
		$obj=new $elt();
		if(!property_exists($obj,'reference')) continue;
		$request="update " . $obj->getDatabaseTableName() . " set reference=null";
		SqlDirectElement::execute($request); 
		$lst=$obj->getSqlElementsFromCriteria(null, false);
		if (count($lst)<100) {
		  projeqtor_set_time_limit(1500);
		} else {
		  traceLog("   => setting unlimited execution time for script (more than 100 $elt to update)");
		  projeqtor_set_time_limit(0);
		}
		$cpt=0;
		traceLog("   => ".count($lst)." $elt to update");
	  foreach ($lst as $object) {
		  $object->setReference(true);
		  $cpt++;
		  if ( ($cpt % $cptCommit) == 0) {
		    Sql::commitTransaction();
		    traceLog("   => $cpt $elt done...");
		    Sql::beginTransaction();
		  }
		}
	}
	// Sql::commitTransaction(); done afterwards
	$element=(!$element)?'all':$element;
	$returnValue=i18n('updatedReference',array(i18n($element)));	
	$returnValue .= '<input type="hidden" id="lastOperation" value="update" />';
  $returnValue .= '<input type="hidden" id="lastOperationStatus" value="OK" />';
  return $returnValue;
}
function displayError($msg,$indent=false){
  if ($indent) echo "<span style='display:inline-block;padding-left:50px'>&nbsp;</span>";
  echo "<span class='messageERROR' style='position:relative;top:4px;left:20px;'>$msg</span><br/><br/>";
}
function displayOK($msg,$indent=false){
  if ($indent) echo "<span style='display:inline-block;padding-left:50px'>&nbsp;</span>";
  echo "<span class='messageOK' style='position:relative;top:4px;left:20px;'>$msg</span><br/><br/>";
}
function displayMsg($msg,$indent=false){
  if ($indent) echo "<span style='display:inline-block;padding-left:50px'>&nbsp;</span>";
  echo "<span class='messageNO_CHANGE' style='position:relative;top:4px;left:20px;'>$msg</span><br/><br/>";
}