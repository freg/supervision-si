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

/** ===========================================================================
 * Save a note : call corresponding method in SqlElement Class
 * The new values are fetched in $_REQUEST
 */
require_once "../tool/projeqtor.php";

$mode=RequestHandler::getValue('mode');
if($mode !='edit'){
// Get the pokerItem info
if (! pq_array_key_exists('pokerItemRef1Type',$_REQUEST)) {
  throwError('pokerItemRef1Type parameter not found in REQUEST');
}
$ref1Type=$_REQUEST['pokerItemRef1Type'];
if (! pq_array_key_exists('pokerItemRef1Id',$_REQUEST)) {
  throwError('pokerItemRef1Id parameter not found in REQUEST');
}
$ref1Id=$_REQUEST['pokerItemRef1Id'];
if (! pq_array_key_exists('pokerItemRef2Type',$_REQUEST)) {
  throwError('pokerItemRef2Type parameter not found in REQUEST');
}

$ref2Type=$_REQUEST['pokerItemRef2Type'];

if (! pq_array_key_exists('pokerItemRef2Id',$_REQUEST)) {
  throwError('pokerItemRef2Id parameter not found in REQUEST');
}
$ref2Id=$_REQUEST['pokerItemRef2Id'];

$comment = RequestHandler::getValue('pokerItemComment');
$name = RequestHandler::getValue('pokerItemName');
$idPokerSession = RequestHandler::getId('idPokerSession');

$pokerItemId=null;

  $arrayId=array();
  if (is_array($ref2Id)) {
  	$arrayId=$ref2Id;
  } else {
  	$arrayId[]=$ref2Id;
  }
  Sql::beginTransaction();
  $result="";
  // get the modifications (from request)
  
  $item=new PokerItem();
  
  foreach ($arrayId as $ref2Id) { 
  	$pokerItem=new PokerItem();
  	$pokerItem->refId=$ref2Id;
  	$pokerItem->refType=$ref2Type;
    $pokerItem->comment = $comment;
    if(!pq_trim($name))$name=$ref2Type;
    $pokerItem->name = $name;
    $pokerItem->idPokerSession = $idPokerSession;
    $res=$pokerItem->save();
    if (!$result) {
      $result=$res;
    } else if (pq_stripos($res,'id="lastOperationStatus" value="OK"')>0 ) {
    	if (pq_stripos($result,'id="lastOperationStatus" value="OK"')>0 ) {
    		$deb=pq_stripos($res,'#');
    		$fin=pq_stripos($res,' ',$deb);
    		$resId=pq_substr($res,$deb, $fin-$deb);
    		$deb=pq_stripos($result,'#');
        $fin=pq_stripos($result,' ',$deb);
        $result=pq_substr($result, 0, $fin).','.$resId.pq_substr($result,$fin);
    	} else {
    	  $result=$res;
    	} 
    }
  }
}else{
  $result = "";
  $comment = RequestHandler::getValue('pokerItemComment');
  $idPokerItem = RequestHandler::getId('idPokerItem');
  Sql::beginTransaction();
  $pokerItem = new PokerItem($idPokerItem);
  $pokerItem->comment = $comment;
  $result=$pokerItem->save();
}
// Message of correct saving
displayLastOperationStatus($result);
?>