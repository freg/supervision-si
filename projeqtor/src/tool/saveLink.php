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
$synchronizationLink=false;
if (pq_array_key_exists('synchronizationLink', $_REQUEST)){
  if ($_REQUEST['synchronizationLink']!='0') {
    $synchronizationLink=true;
  }
}
if($mode !='edit'){
// Get the link info
if (! pq_array_key_exists('linkRef1Type',$_REQUEST)) {
  throwError('linkRef1Type parameter not found in REQUEST');
}
$ref1Type=$_REQUEST['linkRef1Type'];
if (! pq_array_key_exists('linkRef1Id',$_REQUEST)) {
  throwError('linkRef1Id parameter not found in REQUEST');
}
$ref1Id=$_REQUEST['linkRef1Id'];
if (! pq_array_key_exists('linkRef2Type',$_REQUEST)) {
  throwError('linkRef2Type parameter not found in REQUEST');
}
//$ref2Type=SqlList::getNameFromId('Linkable', $_REQUEST['linkRef2Type']);
$ref2TypeObj=New Linkable($_REQUEST['linkRef2Type']);
$ref2Type=$ref2TypeObj->name;

if (! pq_array_key_exists('linkRef2Id',$_REQUEST)) {
  throwError('linkRef2Id parameter not found in REQUEST');
}
$ref2Id=$_REQUEST['linkRef2Id'];

$copyLinksofLinked=false;
if (pq_array_key_exists('copyLinksofLinked', $_REQUEST)){
  if ($_REQUEST['copyLinksofLinked']!='0') {
    $copyLinksofLinked=true;
  }
}

if ($ref2Type=='Document') {
  if (pq_array_key_exists('linkDocumentVersion',$_REQUEST)) {
    $version=$_REQUEST['linkDocumentVersion'];
    if (pq_trim($version)) {
    	$ref2Type='DocumentVersion';
    	$ref2Id=$version;
    }
  }
}

$comment="";
if (pq_array_key_exists('linkComment',$_REQUEST)) {
    $comment=$_REQUEST['linkComment'];
}

$linkId=null;

  $arrayId=array();
  if (is_array($ref2Id)) {
  	$arrayId=$ref2Id;
  } else {
  	$arrayId[]=$ref2Id;
  }
  Sql::beginTransaction();
  $result="";
  // get the modifications (from request) 
  
  $Lnk=new Link();
  
  foreach ($arrayId as $ref2Id) { 
    if ($synchronizationLink=='on'){
      $ref1Id = intval($ref1Id);
      $ref2Id = intval($ref2Id);
      $where1 = "(ref1Type='$ref1Type' AND ref1Id='$ref1Id' AND idSynchronizationItem IS NOT NULL) OR (ref1Type='$ref2Type' AND ref1Id='$ref2Id' AND idSynchronizationItem IS NOT NULL)";
      $where2 = "(ref2Type='$ref2Type' AND ref2Id='$ref2Id' AND idSynchronizationItem IS NOT NULL) OR (ref2Type='$ref1Type' AND ref2Id='$ref1Id' AND idSynchronizationItem IS NOT NULL)";
      $syncCheck1 = $Lnk->getSqlElementsFromCriteria(null, false, $where1);
      $syncCheck2 = $Lnk->getSqlElementsFromCriteria(null, false, $where2);
      if ($syncCheck1 || $syncCheck2) {
        $result = '<b>' . i18n('errorElementAlreadySynchronized') . '</b>';
        $result .= '<input type="hidden" id="lastOperation" value="control" />';
        $result .= '<input type="hidden" id="lastOperationStatus" value="INVALID" />';
        displayLastOperationStatus($result);
        return; 
      }
    }
    
    $crit1=array('ref1Type'=>$ref2Type,'ref1Id'=>intval($ref2Id));
    $list1=$Lnk->getSqlElementsFromCriteria($crit1);    
    $crit2=array('ref2Type'=>$ref2Type,'ref2Id'=>intval($ref2Id));
    $list2=$Lnk->getSqlElementsFromCriteria($crit2);
    
  	$link=new Link();
  	$link->ref1Id=$ref1Id;
  	$link->ref1Type=$ref1Type;
  	$link->ref2Id=$ref2Id;
  	$link->ref2Type=$ref2Type;
    $link->comment=$comment;
    $link->idUser=$user->id;
    $link->creationDate=date("Y-m-d H:i:s");
    
    if ($synchronizationLink=='on'){
      $synchronizedItems = new SynchronizedItems();
      $synchronizedItems->ref1Id = $ref1Id;
      $synchronizedItems->ref1Type = $ref1Type;
      $synchronizedItems->ref2Id = $ref2Id;
      $synchronizedItems->ref2Type = $ref2Type;
      $synchronizedItems->save();
      $link->idSynchronizationItem = $synchronizedItems->id;
    }else {
      $link->idSynchronizationItem = null;
    }
    
    $res=$link->save();
    if ($copyLinksofLinked=='on'){
      foreach ($list1 as $link){
        $link->id=null;
        $link->ref1Type=$ref1Type;
        $link->ref1Id=$ref1Id;
        $link->save();  
      }
      foreach($list2 as $link){
        $link->id=null;
        $link->ref2Type=$ref1Type;
        $link->ref2Id=$ref1Id;
        $link->save();
      }
    }

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
  
  //$mailResult=null;
  $mailResult1=null;
  $mailResult2=null;
  if (getLastOperationStatus($result)=='OK') {
    $elt1=new $link->ref1Type($link->ref1Id);
    $mailResult1=$elt1->sendMailIfMailable(false,false,false,false,false,false,false,false,false,false,false,false,false,false,true,false);
    $elt2=new $link->ref2Type($link->ref2Id);
    $mailResult2=$elt2->sendMailIfMailable(false,false,false,false,false,false,false,false,false,false,false,false,false,false,true,false);
  }
  if ($mailResult1 or $mailResult2) {
    $pos=pq_strpos($result,'<input type="hidden"');
    if ($pos) {
      $result=pq_substr($result, 0,$pos).' - ' . Mail::getResultMessage(($mailResult1=='TEMP')?$mailResult1:$mailResult2).pq_substr($result, $pos);
    }
  }
}else{
  $result = "";
  $comment = RequestHandler::getValue('linkComment');
  $idLink = RequestHandler::getId('idLink');
  Sql::beginTransaction();
  $link = new Link($idLink);
  if ($synchronizationLink=='on'){
    $Lnk=new Link();
    $where1 = "(ref1Type='$link->ref1Type' AND ref1Id='$link->ref1Id' AND idSynchronizationItem IS NOT NULL) OR (ref1Type='$link->ref2Type' AND ref1Id='$link->ref2Id' AND idSynchronizationItem IS NOT NULL)";
    $where2 = "(ref2Type='$link->ref2Type' AND ref2Id='$link->ref2Id' AND idSynchronizationItem IS NOT NULL) OR (ref2Type='$link->ref1Type' AND ref2Id='$link->ref1Id' AND idSynchronizationItem IS NOT NULL)";
    $syncCheck1 = $Lnk->getSqlElementsFromCriteria(null, false, $where1);
    $syncCheck2 = $Lnk->getSqlElementsFromCriteria(null, false, $where2);
    if ($syncCheck1 || $syncCheck2) {
      $result = '<b>' . i18n('errorElementAlreadySynchronized') . '</b>';
      $result .= '<input type="hidden" id="lastOperation" value="control" />';
      $result .= '<input type="hidden" id="lastOperationStatus" value="INVALID" />';
      displayLastOperationStatus($result);
      return;
    }
  }
  if ($synchronizationLink=='on'){
    $synchronizedItems = new SynchronizedItems();
    $synchronizedItems->ref1Id = $link->ref1Id;
    $synchronizedItems->ref1Type = $link->ref1Type;
    $synchronizedItems->ref2Id = $link->ref2Id;
    $synchronizedItems->ref2Type = $link->ref2Type;
    $synchronizedItems->save();
    $link->idSynchronizationItem = $synchronizedItems->id;
  }else {
    if ($link->idSynchronizationItem){
      $synchronizedItems = new SynchronizedItems($link->idSynchronizationItem);
      $synchronizedItems->delete();
    }
    $link->idSynchronizationItem = null;
  }
  $link->comment = $comment;
  $result=$link->saveForced();
}
// Message of correct saving
displayLastOperationStatus($result);
?>