<?php
/*
 *	@author: qCazelles
 */

include_once '../tool/projeqtor.php';

include_once("../external/pChart2/class/pData.class.php");
include_once("../external/pChart2/class/pDraw.class.php");
include_once("../external/pChart2/class/pImage.class.php");

$paramProduct='';
if (pq_array_key_exists('idProduct',$_REQUEST)) {
	$paramProduct=pq_trim($_REQUEST['idProduct']);
	$paramProduct = Security::checkValidId($paramProduct); // only allow digits
};

$paramVersion='';
if (pq_array_key_exists('idVersion',$_REQUEST)) {
	$paramVersion=pq_trim($_REQUEST['idVersion']);
	$paramVersion = Security::checkValidId($paramVersion); // only allow digits
};

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

$paramPriorities=array();
if (pq_array_key_exists('priorities',$_REQUEST)) {
	foreach ($_REQUEST['priorities'] as $idPriority => $boolean) {
		$paramPriorities[] = $idPriority;
	}
}

$periodType='year';
//$periodValue=$_REQUEST['periodValue'];
$periodValue=$paramYear;

// Header
$headerParameters="";
if ($paramProduct!="") {
	$headerParameters.= i18n("colIdProduct") . ' : ' . htmlEncode(SqlList::getNameFromId('Product', $paramProduct)) . '<br/>';
}
if ($paramVersion!="") {
	$headerParameters.= i18n("colVersion") . ' : ' . htmlEncode(SqlList::getNameFromId('Version', $paramVersion)) . '<br/>';
}
if ($periodType=='year' or $periodType=='month' or $periodType=='week') {
	$headerParameters.= i18n("year") . ' : ' . $paramYear . '<br/>';
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
if (!empty($paramPriorities)) {
	$priority = new Priority();
	$priorities = $priority->getSqlElementsFromCriteria(null, false, null, 'id asc');
	
	$prioritiesDisplayed = array();
	for ($i = 0; $i < count($priorities); $i++) {
		if ( in_array($i+1, $paramPriorities)) {
			$prioritiesDisplayed[] = $priorities[$i];
		}
	}
	
	$headerParameters.= i18n("colPriority") .' : ';
	foreach ($prioritiesDisplayed as $priority) {
		$headerParameters.=$priority->name . ', ';
	}
	$headerParameters=pq_substr($headerParameters, 0, -2);
	
	if ( in_array('undefined', $paramPriorities)) {
		$headerParameters.=', '.i18n('undefinedPriority');
	}
}
include "header.php";

$paramProject="";
$includedReport=true;

include "ticketYearlyReport.php";
	