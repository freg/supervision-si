<?php
/*** COPYRIGHT NOTICE *********************************************************
 *
******************************************************************************
*** WARNING *** T H I S    F I L E    I S    N O T    O P E N    S O U R C E *
******************************************************************************
*
* Copyright 2017 ProjeQtOr - Pascal BERNARD - support@projeqtor.org
*
* This file is an add-on to ProjeQtOr, packaged as a plug-in module.
* It is NOT distributed under an open source license.
* It is distributed in a proprietary mode, only to the customer who bought
* corresponding licence.
* The company ProjeQtOr remains owner of all add-ons it delivers.
* Any change to an add-ons without the explicit agreement of the company
* ProjeQtOr is prohibited.
* The diffusion (or any kind if distribution) of an add-on is prohibited.
* Violators will be prosecuted.
*
*** DO NOT REMOVE THIS NOTICE ************************************************/

require_once "../tool/projeqtor.php";
require_once "../tool/formatter.php";
require_once 'kanbanFunction.php';

$idItem = RequestHandler::getId ( 'id' );
$idKanban = RequestHandler::getValue ( 'idKanban' );
$type = RequestHandler::getValue ( 'type' );
$from = RequestHandler::getValue ( 'from' );

$kanB = new Kanban ( $idKanban, true );
$json = $kanB->param;
$type = $kanB->type;

$jsonDecode = json_decode ( $json, true );
$itemClass = $jsonDecode ['typeData'];
$hasVersion=(property_exists($itemClass,'idTargetProductVersion'))?true:false;
$hasMilestone=(property_exists($itemClass,'idMilestone'))?true:false;
$item = new $itemClass ( $idItem );
$line = array ();
$item->targetProductVersion = $kanB->type;
$item->milestone = $kanB->type;
/*
 * foreach($item as $fld=>$val) { $line[pq_strtolower($fld)]=$val; }
 */
$line = ( array ) $item;
$typeName = 'id' . get_class ( $item ) . 'Type';
$line ['name'] = $item->name;
$line ['idtickettype'] = $item->$typeName;
$line ['idstatus'] = $item->idStatus;
$line ['idproject'] = $item->idProject;
// Not for Activity
if (get_class ( $item ) != 'Activity' && get_class ( $item ) != 'Requirement') {
	$line ['idpriority'] = $item->idPriority;
}

$line ['idtargetproductversion'] = ($hasVersion)?$item->idTargetProductVersion:null;
$line ['idmilestone'] = ($hasMilestone)?$item->idMilestone:null;

if (property_exists ( $item, 'idActivity' )) {
	$line ['idactivity'] = $item->idActivity;
} else {
	$line ['idactivity'] = null;
}

// if(get_class($item)!= 'Requirement'){}

$line ['description'] = $item->description;
$line ['iduser'] = $item->idUser;

// sortOrder => 300 Status->sortOrder
// Resource->idUser
$line ['targetproductversion'] = $item->targetProductVersion;
// TargetProductVersion -> $type
// var_dump($line['targetproductversion']);
$line ['milestone'] = $item->milestone;

if (property_exists ( $item, 'WorkElement' )) {
	$we = $item->WorkElement;
	$line ['plannedwork'] = $we->plannedWork;
	$line ['realwork'] = $we->realWork;
	$line ['leftwork'] = $we->leftWork;
} else {
	$peName = get_class ( $item ) . 'PlanningElement';
	if (property_exists ( $item, $peName )) {
		$pe = $item->$peName;
		$line ['plannedwork'] = $pe->plannedWork;
		$line ['realwork'] = $pe->realWork;
		$line ['leftwork'] = $pe->leftWork;
		$isColorBlind=(Parameter::getUserParameter('colorBlindPlanning') == 'YES')?true:false;
		if ($pe->refType == 'Activity'){
		  $pColor='#50BB50';
		  $pColorBlindColor = $pColor;
		  if ($pe->notPlannedWork > 0) { // Some left work not planned
		    $pColor = '#9933CC';
		    $pColorBlindColor = '#BB5050';
		  } else if (pq_trim($pe->validatedEndDate) != "" and $pe->validatedEndDate < $pe->plannedEndDate) { 
		    if ($pe->refType!='Milestone' and ( ! $pe->assignedWork or $pe->assignedWork==0 ) and ( ! $pe->leftWork or $pe->leftWork==0 ) and ( ! $pe->realWork or $pe->realWork==0 )) {
		      $pColor = '#BB9099';
		      $pColorBlindColor = 'linear-gradient(45deg, #63226b 5%, #9a3ec9 5%, #9a3ec9 45%, #63226b 45%, #63226b 55%, #9a3ec9 55%, #9a3ec9 95%, #63226b 95%);';
		    } else {
		      $pColor = '#BB5050';
		      $pColorBlindColor = 'linear-gradient(45deg, #63226b 5%, #9a3ec9 5%, #9a3ec9 45%, #63226b 45%, #63226b 55%, #9a3ec9 55%, #9a3ec9 95%, #63226b 95%);';
		    }
		  } else if ( ( ($pe->idPlanningMode==8 or $pe->idPlanningMode==14) and intval($pe->validatedDuration) < intval($pe->plannedDuration) )
		      or ( ($pe->idPlanningMode==25 or $pe->idPlanningMode==26) and $pe->plannedStartDate != $pe->validatedStartDate )
		      or ( ($pe->idPlanningMode==19 or $pe->idPlanningMode==21) and $pe->plannedStartDate < $pe->validatedStartDate )  ) {
		        $pColor = '#BB5050';
		        $pColorBlindColor = 'linear-gradient(45deg, #63226b 5%, #9a3ec9 5%, #9a3ec9 45%, #63226b 45%, #63226b 55%, #9a3ec9 55%, #9a3ec9 95%, #63226b 95%);';
		      } else if ($pe->refType!='Milestone' and ( ! $pe->assignedWork or $pe->assignedWork==0 ) and ( ! $pe->leftWork or $pe->leftWork==0 ) and ( ! $pe->realWork or $pe->realWork==0 ) ) { // No workassigned : greyed
		        $pColor = '#AEC5AE';
		      }
		      if ($pe->surbooked==1) {
		        $pColor='#f4bf42';
		        $pColorBlindColor='#bfbfbf';
		      }
		      // Color for late from inheritedEndDate
		      if (pq_trim($pe->validatedEndDate)=="" and pq_trim($pe->inheritedEndDate)!="" and $pe->inheritedEndDate < $pe->plannedEndDate) {
		        if ($pe->assignedWork>0) $pColor = '#DA70D6';
		        else $pColor = '#DDA0DD';
		      }
		      $pe->plannedcolor = ($isColorBlind)?$pColorBlindColor:$pColor;
		} else {
		  $pColor='#F1F1F1';
		  $pColorBlindColor = $pColor;
		  $pe->plannedcolor = ($isColorBlind)?$pColorBlindColor:$pColor;
		}
		$line ['plannedcolor'] = $pe->plannedcolor;
	}
}

// $line =
// sortOrder => 300
// name4 => admin
// name5 =>

$add = "";

$from = "";
$mode = "refresh";
kanbanDisplayTicket ( $idItem, $type, $idKanban, $from, $line, $add, $mode);
?>