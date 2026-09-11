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

include_once '../tool/projeqtor.php';
include_once "../tool/jsonFunctions.php";
//echo 'ticketReport.php';

if (! isset($includedReport)) {

	$paramYear='';
	if (pq_array_key_exists('yearSpinner',$_REQUEST)) {
		$paramYear=$_REQUEST['yearSpinner'];
		$paramYear=Security::checkValidYear($paramYear);
	};

	$paramMonth='';
	if (pq_array_key_exists('monthSpinner',$_REQUEST)) {
		$paramMonth=$_REQUEST['monthSpinner'];
		$paramMonth=Security::checkValidMonth($paramMonth);
	};

	$paramProject='';
	if (pq_array_key_exists('idProject',$_REQUEST)) {
		$paramProject=pq_trim($_REQUEST['idProject']);
		Security::checkValidId($paramProject);
	}

	$paramTicketType='';
	if (pq_array_key_exists('idTicketType',$_REQUEST)) {
		$paramTicketType=pq_trim($_REQUEST['idTicketType']);
		$paramTicketType = Security::checkValidId($paramTicketType); // only allow digits
	};

	$paramRequestor='';
	if (pq_array_key_exists('requestor',$_REQUEST)) {
		$paramRequestor=pq_trim($_REQUEST['requestor']);
		$paramRequestor = Security::checkValidId($paramRequestor); // only allow digits
	}

	$paramIssuer='';
	if (pq_array_key_exists('issuer',$_REQUEST)) {
		$paramIssuer=pq_trim($_REQUEST['issuer']);
		$paramIssuer = Security::checkValidId($paramIssuer); // only allow digits
	};

	$paramResponsible='';
	if (pq_array_key_exists('responsible',$_REQUEST)) {
		$paramResponsible=pq_trim($_REQUEST['responsible']);
		$paramResponsible = Security::checkValidId($paramResponsible); // only allow digits
	};
	
	$ticketWithoutDelay=RequestHandler::getBoolean('ticketWithoutDelay');

	$user=getSessionUser();

	$periodType="";
	$periodValue="";
	if (pq_array_key_exists('periodType',$_REQUEST)) {
		$periodType=$_REQUEST['periodType']; // not filtering as data as data is only compared against fixed strings
		if (pq_array_key_exists('periodValue',$_REQUEST))
		{
			$periodValue=$_REQUEST['periodValue'];
			$periodValue=Security::checkValidPeriod($periodValue);
		}
	}
	// Header
	$headerParameters="";
	if ($paramProject!="") {
		$headerParameters.= i18n("colIdProject") . ' : ' . htmlEncode(SqlList::getNameFromId('Project', $paramProject)) . '<br/>';
	}
	if ($periodType=='year' or $periodType=='month' or $periodType=='week') {
		$headerParameters.= i18n("year") . ' : ' . $paramYear . '<br/>';
	}
	//ADD qCazelles - Report fiscal year - Ticket #128
	if ($periodType=='year' and $paramMonth!="01") {
		if(!$paramMonth){
			$paramMonth="01";
		}
		$headerParameters.= i18n("startMonth") . ' : ' . i18n(date('F', mktime(0,0,0,$paramMonth,10))) . '<br/>';
	}
	//END ADD qCazelles - Report fiscal year - Ticket #128
	if ($periodType=='month') {
		$headerParameters.= i18n("month") . ' : ' . $paramMonth . '<br/>';
	}
	if ($paramTicketType!="") {
		$headerParameters.= i18n("colIdTicketType") . ' : ' . SqlList::getNameFromId('TicketType', $paramTicketType) . '<br/>';
	}
	if ($paramRequestor!="") {
		$headerParameters.= i18n("colRequestor") . ' : ' . SqlList::getNameFromId('Contact', $paramRequestor) . '<br/>';
	}
	if ($paramIssuer!="") {
		$headerParameters.= i18n("colIssuer") . ' : ' . SqlList::getNameFromId('User', $paramIssuer) . '<br/>';
	}
	if ($paramResponsible!="") {
		$headerParameters.= i18n("colResponsible") . ' : ' . SqlList::getNameFromId('Resource', $paramResponsible) . '<br/>';
	}
	if ($ticketWithoutDelay!="") {
		$headerParameters.= i18n("colTicketWithoutDelay") . ' : On' . '<br/>';
	}
	//END OF THAT
	include "header.php";
}
$where=getAccesRestrictionClause('Ticket',false);
// Adapt clause on filter
$arrayFilter=jsonGetFilterArray('Report_Ticket', false);
if (count($arrayFilter)>0) {
	$obj=new Ticket();
	$querySelect="";
	$queryFrom="";
	$queryOrderBy="";
	$idTab=0;
	jsonBuildWhereCriteria($querySelect,$queryFrom,$where,$queryOrderBy,$idTab,$arrayFilter,$obj);
}
if ($paramMonth and $paramYear) {
    $firstDay = $paramYear.'-'.$paramMonth.'-01 00:00:00';
	$lastDay = $paramYear.'-'.$paramMonth.'-'.numberOfDaysOfMonth($firstDay).' 00:00:00';
	$where.=" and ( handledDateTime>= '" . $firstDay . "' and handledDateTime<='" . $lastDay . "' )";
}
if ($paramProject!="") {
	$where.=" and idProject in " .  getVisibleProjectsList(false, $paramProject);
}
if ($paramTicketType!="") {
	$where.=" and idTicketType=" . Sql::fmtId($paramTicketType) ;
}
if ($paramRequestor!="") {
	$where.=" and idContact=" . Sql::fmtId($paramRequestor) ;
}
if ($paramIssuer!="") {
	$where.=" and idUser=" . Sql::fmtId($paramIssuer);
}
if ($paramResponsible!="") {
	$where.=" and idResource=" . Sql::fmtId($paramResponsible) ;
}
//$delay = openHourDiffTime('2021-04-09 11:30:00', '2021-04-22 16:30:00', $paramProject)/3600;
//END ADD qCazelles - graphTickets

$order="idUrgency";
$where .= ' and handled=1';
$ticket=new Ticket();
$lstTicket=$ticket->getSqlElementsFromCriteria(null,false, $where, $order);
$ticketType=new TicketType();
$whereTicketType=($paramTicketType!='')?'id='.Sql::fmtId($paramTicketType):'1=1';
$lstTicketType = $ticketType->getSqlElementsFromCriteria(null, null, $whereTicketType);
$urgency=new Urgency();
$lstUrgency = $urgency->getSqlElementsFromCriteria(null, null, "1=1");


echo '<table style="width:95%;text-align:center"'.excelName().' align="center">';
echo '<tr>';
echo '<td class="reportTableHeader" style="width:20%"'.excelFormatCell('header',40).'>' . i18n('colIdTicketType') . '</td>';
echo '<td class="reportTableHeader" style="width:15%"'.excelFormatCell('header',30).'>'.i18n('colUrgency').'</td>';
echo '<td class="reportTableHeader" style="width:10%"'.excelFormatCell('header',20).'>'.i18n('nbHandled').'</td>';
echo '<td class="reportTableHeader" style="width:15%"'.excelFormatCell('header',20).'>'.i18n('delayHandled').'</td>';
echo '<td class="reportTableHeader" style="width:10%"'.excelFormatCell('header',20).'>'.i18n('nbNotHandled').'</td>';
echo '<td class="reportTableHeader" style="width:15%"'.excelFormatCell('header',20).'>'.i18n('delayNotHandled').'</td>';
echo '<td class="reportTableHeader" style="width:10%"'.excelFormatCell('header',20).'>'.i18n('punctualityRate').'</td>';
echo '</tr>';
$result = array();
foreach ($lstTicket as $ticket){
	$delay = SqlElement::getSingleSqlElementFromCriteria('TicketDelay', array('idTicketType'=>$ticket->idTicketType, 'idUrgency'=>$ticket->idUrgency, 'idProject'=>$ticket->idProject, 'idMacroTicketStatus'=>1));
	if(!$delay->id){
		$delay = SqlElement::getSingleSqlElementFromCriteria('TicketDelay', array('idTicketType'=>$ticket->idTicketType, 'idUrgency'=>$ticket->idUrgency, 'idMacroTicketStatus'=>1));
	}
	$delayValue = 0;
    if(!isset($result[$ticket->idTicketType][$ticket->idUrgency]['OK'])){
	    $result[$ticket->idTicketType][$ticket->idUrgency]['OK'] = 0;
    }
    if(!isset($result[$ticket->idTicketType][$ticket->idUrgency]['KO'])){
    	$result[$ticket->idTicketType][$ticket->idUrgency]['KO'] = 0;
    }
    if(!isset($result[$ticket->idTicketType][$ticket->idUrgency]['Nb'])){
    	$result[$ticket->idTicketType][$ticket->idUrgency]['Nb'] = 0;
    }
	if($delay->id){
    	$delayUnit = new DelayUnit($delay->idDelayUnit);
    	$duration = 0;
    	$startAMDate = date('Y-m-d').' '.getDailyHours($ticket->idProject, 'startAM', false);
    	$endAMDate = date('Y-m-d').' '.getDailyHours($ticket->idProject, 'endAM', false);
    	$startPMDate = date('Y-m-d').' '.getDailyHours($ticket->idProject, 'startPM', false);
    	$endPMDate = date('Y-m-d').' '.getDailyHours($ticket->idProject, 'endPM', false);
    	$hourPerDay = abs(pq_strtotime($startAMDate)-pq_strtotime($endAMDate))+abs(pq_strtotime($startPMDate)-pq_strtotime($endPMDate));
    	switch ($delayUnit->code){
    		case 'HH' :
    			$duration = abs(pq_strtotime($ticket->creationDateTime)-pq_strtotime($ticket->handledDateTime));
    			$delayValue = $duration/3600;
    			break;
    		case 'OH' :
    			$duration = openHourDiffTime($ticket->creationDateTime, $ticket->handledDateTime, $ticket->idProject);
    			$delayValue = $duration/3600;
            	if($duration>$hourPerDay){
            	  $duration = $duration/$hourPerDay;
            	  $duration = $duration*86400;
//                   $durationDay = (($duration - fmod($duration,1))/($hourPerDay/3600))*86400;
//                   $durationHour = fmod($duration,1)*3600;
//                   $duration = $durationDay+$durationHour;
                }
    			break;
    		case 'DD' :
    			$duration = abs(pq_strtotime($ticket->creationDateTime)-pq_strtotime($ticket->handledDateTime));
    			$delayValue = $duration/86400;
    			break;
    		case 'OD' :
    			$duration = openHourDiffTime($ticket->creationDateTime, $ticket->handledDateTime, $ticket->idProject);
    			$delayValue = $duration/86400;
            	if($duration>$hourPerDay){
            	  $duration = $duration/$hourPerDay;
            	  $duration = $duration*86400;
//                   $durationDay = (($duration - fmod($duration,1))/($hourPerDay/3600))*86400;
//                   $durationHour = fmod($duration,1)*3600;
//                   $duration = $durationDay+$durationHour;
                }
    			break;
    	}
    	$result[$ticket->idTicketType][$ticket->idUrgency]['Nb']++;
    	$duration = round($duration);
    	$delayValue = round($delayValue, 2);
    	if(isset($result[$ticket->idTicketType][$ticket->idUrgency]['durationTotal'])){
    		$result[$ticket->idTicketType][$ticket->idUrgency]['durationTotal'] += $duration;
    	}else{
    		$result[$ticket->idTicketType][$ticket->idUrgency]['durationTotal'] = $duration;
    	}
  		if(isset($result[$ticket->idTicketType][$ticket->idUrgency]['durationOK'])){
  		  $result[$ticket->idTicketType][$ticket->idUrgency]['durationOK'] += $duration;
  		}else{
  		  $result[$ticket->idTicketType][$ticket->idUrgency]['durationOK'] = $duration;
  		}
  		$result[$ticket->idTicketType][$ticket->idUrgency]['OK']++;
  		if($delayValue > $delay->value){
  	        if(isset($result[$ticket->idTicketType][$ticket->idUrgency]['durationKO'])){
    		  $result[$ticket->idTicketType][$ticket->idUrgency]['durationKO'] += $duration;
    		}else{
    		  $result[$ticket->idTicketType][$ticket->idUrgency]['durationKO'] = $duration;
    		}
    		$result[$ticket->idTicketType][$ticket->idUrgency]['KO']++;
    	}
	}else if($ticketWithoutDelay and !$delay->id){
	  if(isset($result[$ticket->idTicketType][$ticket->idUrgency]['OK'])){
	    $result[$ticket->idTicketType][$ticket->idUrgency]['OK']++;
	  }
	  $duration = abs(pq_strtotime($ticket->creationDateTime)-pq_strtotime($ticket->handledDateTime));
	  if(isset($result[$ticket->idTicketType][$ticket->idUrgency]['durationTotal'])){
	  	$result[$ticket->idTicketType][$ticket->idUrgency]['durationTotal'] += $duration;
	  }else{
	  	$result[$ticket->idTicketType][$ticket->idUrgency]['durationTotal'] = $duration;
	  }
	  if(isset($result[$ticket->idTicketType][$ticket->idUrgency]['durationOK'])){
	  	$result[$ticket->idTicketType][$ticket->idUrgency]['durationOK'] += $duration;
	  }else{
	  	$result[$ticket->idTicketType][$ticket->idUrgency]['durationOK'] = $duration;
	  }	  
	  $result[$ticket->idTicketType][$ticket->idUrgency]['Nb']++;
	}else{
	  continue;
	}
}
$startAMDate = date('Y-m-d').' '.getDailyHours(null, 'startAM', false);
$endAMDate = date('Y-m-d').' '.getDailyHours(null, 'endAM', false);
$startPMDate = date('Y-m-d').' '.getDailyHours(null, 'startPM', false);
$endPMDate = date('Y-m-d').' '.getDailyHours(null, 'endPM', false);
$hourPerDay = abs(pq_strtotime($startAMDate)-pq_strtotime($endAMDate))+abs(pq_strtotime($startPMDate)-pq_strtotime($endPMDate));
foreach ($lstUrgency as $urgency){
  foreach ($lstTicketType as $type){
    echo '<tr>';
    echo '<td class="reportTableData" style="width:20%"'.excelFormatCell('data',40).'>'.$type->name.'</td>';
    echo '<td class="reportTableData" style="width:15%"'.excelFormatCell('data',30).'>'.$urgency->name.'</td>';
    $OK = (isset($result[$type->id][$urgency->id]['OK']))?$result[$type->id][$urgency->id]['OK']:0;
    echo '<td class="reportTableData" style="width:10%"'.excelFormatCell('data',20).'>'.$OK.'</td>';
    $durationOK = (isset($result[$type->id][$urgency->id]['durationOK']))?$result[$type->id][$urgency->id]['durationOK']:0;
    if($durationOK)$durationOK = $durationOK/$OK;
    if($durationOK>$hourPerDay){
    	$durationOK = $durationOK/3600;
    	$durationDay = (($durationOK - fmod($durationOK,1))/($hourPerDay/3600))*86400;
    	$durationHour = fmod($durationOK,1)*3600;
    	if(fmod(($durationDay/86400), 1) > 0){
    		$hoursDay = fmod(($durationDay/86400), 1)*86400;
    		$durationDay = $durationDay - $hoursDay;
    		$durationHour = $durationHour + $hoursDay;
    	}
    	$durationOK = $durationDay+$durationHour;
    }
    $durationOK = round($durationOK);
    $durationDisplay = '';
  	$startDate = new DateTime(date("Y-m-d H:i:s"));
  	$endDate = new DateTime(date("Y-m-d H:i:s", pq_strtotime("+$durationOK seconds")));
  	$durationDiff = date_diff($startDate, $endDate, true);
  	if($durationDiff->y){
  		$durationDisplay .= $durationDiff->format('%y').i18n('shortYear').' ';
  	}
  	if($durationDiff->m){
  		$durationDisplay .= $durationDiff->format('%m').i18n('shortMonth').' ';
  	}
    if($durationOK >=86400){
  		$durationDisplay .= $durationDiff->format('%d').i18n('shortDay').' ';
  	}
  	if($durationOK >=3600){
  	    if($durationDiff->format('%h')>($hourPerDay/3600)){
  	      $hour = round(($durationDiff->format('%h')*($hourPerDay/3600))/24);
  	    }else{
  	      $hour = $durationDiff->format('%h');
  	    }
  		$durationDisplay .= $hour.i18n('shortHour').' ';
  	}
  	if($durationOK >=60){
  		$durationDisplay .= $durationDiff->format('%i').i18n('shortMinute').' ';
  	}
    if(!$durationDisplay and $OK)$durationDisplay='0'.i18n('shortMinute');
    echo '<td class="reportTableData" style="width:15%"'.excelFormatCell('data',20).'>'.$durationDisplay.'</td>';
    $KO = (isset($result[$type->id][$urgency->id]['KO']))?$result[$type->id][$urgency->id]['KO']:0;
    echo '<td class="reportTableData" style="width:10%"'.excelFormatCell('data',20).'>'.$KO.'</td>';
    $durationKO = (isset($result[$type->id][$urgency->id]['durationKO']))?$result[$type->id][$urgency->id]['durationKO']:0;
    if($durationKO)$durationKO = $durationKO/$KO;
    if($durationKO>$hourPerDay){
    	$durationKO = $durationOK/3600;
    	$durationDay = (($durationKO - fmod($durationKO,1))/($hourPerDay/3600))*86400;
    	$durationHour = fmod($durationKO,1)*3600;
    	if(fmod(($durationDay/86400), 1) > 0){
    		$hoursDay = fmod(($durationDay/86400), 1)*86400;
    		$durationDay = $durationDay - $hoursDay;
    		$durationHour = $durationHour + $hoursDay;
    	}
    	$durationKO = $durationDay+$durationHour;
    }
    $durationKO = round($durationKO);
    $startDate = new DateTime(date("Y-m-d H:i:s"));
    $endDate = new DateTime(date("Y-m-d H:i:s", pq_strtotime("+$durationKO seconds")));
    $durationDiff = date_diff($startDate, $endDate, true);
    $durationDisplay = '';
  	if($durationDiff->y){
  		$durationDisplay .= $durationDiff->format('%y').i18n('shortYear').' ';
  	}
  	if($durationDiff->m){
  		$durationDisplay .= $durationDiff->format('%m').i18n('shortMonth').' ';
  	}
    if($durationKO >=86400){
  		$durationDisplay .= $durationDiff->format('%d').i18n('shortDay').' ';
  	}
  	if($durationKO >=3600){
  	    if($durationDiff->format('%h')>($hourPerDay/3600)){
  	      $hour = round(($durationDiff->format('%h')*($hourPerDay/3600))/24);
  	    }else{
  	      $hour = $durationDiff->format('%h');
  	    }
  		$durationDisplay .= $hour.i18n('shortHour').' ';
  	}
  	if($durationKO >=60){
  		$durationDisplay .= $durationDiff->format('%i').i18n('shortMinute').' ';
  	}
    if(!$durationDisplay and $KO)$durationDisplay='0'.i18n('shortMinute');
    echo '<td class="reportTableData" style="width:15%"'.excelFormatCell('data',20).'>'.$durationDisplay.'</td>';
    $NB = (isset($result[$type->id][$urgency->id]['Nb']))?$result[$type->id][$urgency->id]['Nb']:0;
    $ponctuality='';
    if($OK)$ponctuality = (($OK-$KO)/$NB)*100;
    $ponctuality = (!pq_trim($ponctuality))?'':round($ponctuality).'%';
    echo '<td class="reportTableData" style="width:10%"'.excelFormatCell('data',20).'>'.$ponctuality.'</td>';
    echo '</tr>';
  }
}
echo '</table>';