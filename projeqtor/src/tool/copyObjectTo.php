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
 * Copy an object as a new one (of the same class) : call corresponding method in SqlElement Class
 */

require_once "../tool/projeqtor.php";
$copyPasteMode=RequestHandler::getBoolean("copyPasteFromContextMenu");
$resultArray=array();
$parentArray=array();
$copyPasteSourcePlanningElements=array();
if($copyPasteMode){
  $fromContextMenu=true;
  $copyObjectArray = RequestHandler::getValue("copyObjectArray");
  $copyTargetClass = RequestHandler::getClass("copyTargetClass");
  $copyTargetId = RequestHandler::getId("copyTargetId");
  $copyObjectArray = explode(',', $copyObjectArray);
  foreach ($copyObjectArray as $copyObject) {
    $copyObjectSplit=explode('_', $copyObject);
    $copyObjectClass=$copyObjectSplit[0];
    if($copyObjectClass=='Replan' || $copyObjectClass=='Construction' || $copyObjectClass=='Fixed'){
      $copyObjectClass = "Project";
    }
    $copyObjectId=$copyObjectSplit[1];
    $sourcePe=SqlElement::getSingleSqlElementFromCriteria('PlanningElement', array('refType'=>$copyObjectClass, 'refId'=>$copyObjectId));
    if ($sourcePe and $sourcePe->id) {
      $copyPasteSourcePlanningElements["$copyObjectClass#$copyObjectId"]=(object)array(
          'id'=>$sourcePe->id,
          'refType'=>$sourcePe->refType,
          'refId'=>$sourcePe->refId,
          'wbs'=>$sourcePe->wbs,
          'wbsSortable'=>$sourcePe->wbsSortable
      );
    }
  }
  $lstObject = array_reverse($copyObjectArray);
}else{
  $fromContextMenu = RequestHandler::getBoolean('fromContextMenu');
  $objectId = RequestHandler::getId('objectId');
  $objectClass = RequestHandler::getClass('objectClass');
  $lstObject[] = $objectId;
  $obj = new $objectClass($objectId);
  // Get the object class from request
  if (! pq_array_key_exists('copyClass',$_REQUEST)) {
    throwError('copyClass parameter not found in REQUEST');
  }
  $className=$_REQUEST['copyClass'];
  // compare expected class with object class
  if ($className!=get_class($obj) ) {
    if($className=='SubTask'and RequestHandler::isCodeSet('copyId')){
      $obj= new SubTask (RequestHandler::getId('copyId'));
    }else{
      throwError('last save object (' . get_class($obj) . ') is not of the expected class (' . $className . ').');
    }
    
  }
  if (! pq_array_key_exists('copyToClass',$_REQUEST)) {
    throwError('copyToClass parameter not found in REQUEST');
  }
  if (is_numeric($_REQUEST['copyToClass'])) {
    $toClassNameObj=new Copyable($_REQUEST['copyToClass']); // validates copyToClass is numeric inside SqlElement constructor
    $toClassName=$toClassNameObj->name;
  } else {
    $toClassName=$_REQUEST['copyToClass'];
  }
  //!copyPasteMode because name set after
  if (!$copyPasteMode and ! pq_array_key_exists('copyToName',$_REQUEST)) {
    throwError('copyToName parameter not found in REQUEST');
  }
  $toName=RequestHandler::getValue('copyToName');
  if($className=='SubTask'){
    if (isTextFieldHtmlFormatted($toName)) {
      $text=new Html2Text($toName);
      $toName=$text->getText();
    } else {
      $toName=br2nl($toName);
    }
    $toName=pq_str_replace('"','""',$toName);
    $toName=pq_substr($toName,0,100);
  }
  
  if($className != "CatalogUO"){
    if (! pq_array_key_exists('copyToType',$_REQUEST)) {
      throwError('copyToType parameter not found in REQUEST');
    }
    $toType=$_REQUEST['copyToType'];
  }else{
    $toType = null;
  }
}
foreach($lstObject as $objectCopy){
  // Get the object from session(last status before change)
  if($copyPasteMode){
    $objectCopy = explode('_', $objectCopy);
    $objectClass = $objectCopy[0];
    if($objectClass=='Replan' || $objectClass=='Construction' || $objectClass=='Fixed'){
      $objectClass = "Project";
    }
    $objectId = $objectCopy[1];
    $className = $objectClass;
    $toClassName=$objectClass;
  }else{
    $objectId = $objectCopy;
  }
  if($fromContextMenu){
    if($objectClass=='Replan' || $objectClass=='Construction' || $objectClass=='Fixed'){
      $objectClass = "Project";
    }
    $obj=new $objectClass($objectId);
  }else{
    $obj=SqlElement::getCurrentObject(null,null,true,false);
  }
  if($copyPasteMode){
    $objTypeName = $obj->getTypeName($objectClass);
    $toType=$obj->$objTypeName;
    $toName=$obj->name;
    $toProject=$obj->idProject;
  }
   if(! is_object($obj)) {
     if(RequestHandler::isCodeSet('copyClass') and RequestHandler::isCodeSet('copyId') and RequestHandler::getClass('copyClass')=='SubTask'){
       $obj= new SubTask (RequestHandler::getId('copyId'));
     }else{
       throwError('last saved object is not a real object');
     }
  }
  
  $copyToOrigin=false;
  if (pq_array_key_exists('copyToOrigin',$_REQUEST)) {
    $copyToOrigin=true;
  }
  $copyToLinkOrigin=false;
  if (pq_array_key_exists('copyToLinkOrigin',$_REQUEST)) {
    $copyToLinkOrigin=true;
  }
  $synchronizationLink=false;
  if (pq_array_key_exists('synchronizationLinkCopy',$_REQUEST)) {
    $synchronizationLink=true;
  }
  $copyToWithNotes=false;
  if (pq_array_key_exists('copyToWithNotes',$_REQUEST)) {
    $copyToWithNotes=true;
  }
  $copyToWithAttachments=false;
  if (pq_array_key_exists('copyToWithAttachments',$_REQUEST)) {
    $copyToWithAttachments=true;
  }
  $copyToWithLinks=false;
  if (pq_array_key_exists('copyToWithLinks',$_REQUEST)) {
    $copyToWithLinks=true;
  }
  
  $copyToWithSubTask=false;
  if (pq_array_key_exists('copyToWithSubTask',$_REQUEST)) {
    $copyToWithSubTask=true;
  }
  
  $copyToWithResult=false;
  if (pq_array_key_exists('copyToWithResult',$_REQUEST)) {
    $copyToWithResult=true;
  }
  
  $copyWithStructure=false;
  if (pq_array_key_exists('copyWithStructure',$_REQUEST)) {
  	if ($className=='Activity' && $toClassName=='Activity') {
      $copyWithStructure=true; 
  	}
  }
  $copyAssignments=false;
  if (pq_array_key_exists('copyWithAssignments',$_REQUEST) || pq_array_key_exists('copyWithAssignmentsPaste',$_REQUEST)) {
  	$copyAssignments=true;
  }
  if (pq_array_key_exists('copyToCopyVersionStructure',$_REQUEST)) {
  	$copyVersionStructure=$_REQUEST['copyToCopyVersionStructure'];
  	$obj->_copyVersionStructure=$copyVersionStructure;
  }
  if (pq_array_key_exists('copyToVersionNumber',$_REQUEST)) {
  	$copyToVersionNumber=$_REQUEST['copyToVersionNumber'];
  	$obj->versionNumber=$copyToVersionNumber;
  }
  
  $toProject=(property_exists($obj, 'idProject'))?$obj->idProject:null;
  if (RequestHandler::isCodeSet('copyToProject')) {
    $toProject=RequestHandler::getId('copyToProject',false,null);
  }
  
  $copyStructure = RequestHandler::getValue('copyStructure');
  $duplicateLinkedTestsCases = RequestHandler::getValue('duplicateLinkedTestsCases');
  if($copyToWithLinks and $duplicateLinkedTestsCases){
    $copyToWithLinks = false;
  }
  $copyToWithStatus = (RequestHandler::getBoolean('copyToWithStatus') == 1)?true:false;
  
  $copyToWithDetail = (RequestHandler::getBoolean('copyToWithDetail') == 1)?true:false;
  
  $moveAfterCreate = ($toProject and $obj->idProject!=$toProject and !$copyPasteMode)?null:RequestHandler::getId('moveAfterCreate');
  
  $copyToWithDependency=RequestHandler::getBoolean('copyToWithDependency');
  $copyToWithPredecessor=RequestHandler::getBoolean('copyToWithPredecessor');
  $copyToWithSuccessor=RequestHandler::getBoolean('copyToWithSuccessor');

  Sql::beginTransaction();
  PlanningElement::$_noDispatch=true;
  SqlElement::$_doNotSaveLastUpdateDateTime=true;
  $error=false;
  if ($moveAfterCreate and $toProject) {
    $peTo=new PlanningElement($moveAfterCreate);
    $toProject=$peTo->idProject;
  }
  // copy from existing object
  Security::checkValidId($toType); // $toType is an id !
  if ($className=='ComponentVersion') {
  	$obj->name=$toName;
  	$obj->idComponentVersionType=$toType;
  	$newObj=$obj->copy();
  	if ($copyToWithStatus) {
  	  $allowedStatusList = Workflow::getAllowedStatusListForObject(new ComponentVersion());
  	  if(isset($allowedStatusList) and count($allowedStatusList) > 0){
  	    $st = reset($allowedStatusList);
  	    $newObj->idStatus = $st->id;
  	    $resultSaveStatus=$newObj->save();
  	  }
  	}
  }elseif($className=='Asset' or $className=='SubTask'){
    $newObj=$obj->copyTo($toClassName,$toType, $toName, $toProject,$copyStructure,$copyToWithNotes, $copyToWithAttachments,$copyToWithLinks, false, false, null, null, false, false, $copyToWithStatus, false, $moveAfterCreate);
  }else if ($className=="ProjectExpense" or $className=="IndividualExpense") {
    $newObj=$obj->copyTo($toClassName,$toType, $toName, $toProject, $copyToOrigin, $copyToWithNotes, $copyToWithAttachments,$copyToWithLinks, $copyAssignments,false,null,null,$copyToWithResult, false, $copyToWithStatus, false, $copyToWithDetail);
  }else if($className == 'Activity' or $className =='Milestone'){
    $newObj=$obj->copyTo($toClassName,$toType, $toName, $toProject, $copyToOrigin, $copyToWithNotes, $copyToWithAttachments,$copyToWithLinks, $copyAssignments,false,null,null,$copyToWithResult, false, $copyToWithStatus, $copyToWithSubTask, $moveAfterCreate, $copyToWithDependency, $copyToWithPredecessor, $copyToWithSuccessor);
  }else {
    if(property_exists(get_class($obj), '_SubTask')){
      $newObj=$obj->copyTo($toClassName,$toType, $toName, $toProject, $copyToOrigin, $copyToWithNotes, $copyToWithAttachments,$copyToWithLinks, $copyAssignments,false,null,null,$copyToWithResult, false, $copyToWithStatus,$copyToWithSubTask,$moveAfterCreate);
    }else{
      $newObj=$obj->copyTo($toClassName,$toType, $toName, $toProject, $copyToOrigin, $copyToWithNotes, $copyToWithAttachments,$copyToWithLinks, $copyAssignments,false,null,null,$copyToWithResult, false, $copyToWithStatus, false, $moveAfterCreate);
    }
  }
  $result=$newObj->_copyResult;
  if (! pq_stripos($result,'id="lastOperationStatus" value="OK"')>0 ) {
    $error=true;
  } else {
    $resultArray["$objectClass#$objectId"]=get_class($newObj).'#'.$newObj->id;
  }
  unset($newObj->_copyResult);
  
  if (!$error and RequestHandler::isCodeSet('copyToDescription') and property_exists($newObj, 'description')) {
    $newObj->description = RequestHandler::getValue('copyToDescription');
    $resDescription = $newObj->saveForced();
    $lastOp = getLastOperationStatus($resDescription);
    if ($lastOp != "OK" and $lastOp!="NO_CHANGE") {
      errorLog("Copy description update failed for " . get_class($newObj) . " #$newObj->id : $resDescription");
    }
  }
  if (!$error and $copyWithStructure and get_class($obj)=='Activity' and get_class($newObj)=='Activity') {
  	//$res=copyStructure($obj, $newObj, $copyToOrigin, $copyToWithNotes, $copyToWithAttachments,$copyToWithLinks, $copyAssignments);
  	$res=PlanningElement::copyStructure($obj, $newObj, $copyToOrigin, $copyToWithNotes, $copyToWithAttachments,$copyToWithLinks, $copyAssignments, null, $toProject, false, $copyWithStructure, false, $copyToWithStatus);
  	if ($res!='OK') {
  	  $error=true;
  	  $result=$res;
  	} else {
  	  //PlanningElement::copyStructureFinalize(); // PBER #9515 - With this line, dependencies are dupplicated
  	                                              //              copyStructureFinalize() is done just below
  	}
  }
  if (!$error and ($copyWithStructure or $copyAssignments)) {
    PlanningElement::copyStructureFinalize($copyToWithPredecessor, $copyToWithSuccessor);
  }
  if (!$error and $copyToLinkOrigin) {
  	$link=new Link();
    $link->ref1Id=$obj->id;
    $link->ref1Type=get_class($obj);
    $link->ref2Id=$newObj->id;
    $link->ref2Type=get_class($newObj);
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
      $synchronizedItems = new SynchronizedItems();
      $synchronizedItems->ref1Id = $link->ref1Id;
      $synchronizedItems->ref1Type = $link->ref1Type;
      $synchronizedItems->ref2Id = $link->ref2Id;
      $synchronizedItems->ref2Type = $link->ref2Type;
      $synchronizedItems->save();
      $link->idSynchronizationItem = $synchronizedItems->id;
    }else{
      $link->idSynchronizationItem = null;
    }
    $link->comment=null;
    $user=getSessionUser();
    $link->idUser=$user->id;
    $link->creationDate=date("Y-m-d H:i:s"); 
    $resLink=$link->save();
  }
  
  if(!$error and $copyStructure and get_class($obj)=='Requirement') {
    $res=Requirement::copyStructure($obj, $newObj, $copyToOrigin, $copyToWithNotes, $copyToWithAttachments,$copyToWithLinks, $copyAssignments, null, $toProject, false, $duplicateLinkedTestsCases, $copyToWithStatus);
  }
  if(!$error and $duplicateLinkedTestsCases and get_class($obj)=='Requirement'){
    $link = new Link();
    $listLink = $link->getSqlElementsFromCriteria(array('ref1Type'=>'Requirement','ref1Id'=>$obj->id,'ref2Type'=>'TestCase'));
    foreach ($listLink as $lk){
      $tc = new TestCase($lk->ref2Id);
      $newTc = $tc->copy();
      $newTc->save();
      $newLink = $lk->copy();
      $newLink->ref1Id = $newObj->id;
      $newLink->ref2Id = $newTc->id;
      $newLink->save();
    }
  }
  // Message of correct saving
  $status = displayLastOperationStatus($result);
  if ($copyPasteMode) { 
    echo "<input type='hidden' id='isCopyPastResult' name='isCopyPastResult' value='true' />";
  }
  if ($status == "OK") {
    if (! pq_array_key_exists('comboDetail', $_REQUEST)) {
      SqlElement::setCurrentObject ($newObj);
    }
  }
}

if ($copyPasteMode) {
  // After copy grouped items, copy dependencies between them
  $critAr='';
  foreach ($copyObjectArray as $ar) {
    $arSplit = explode('_', $ar);
    $arClass = $arSplit[0];
    $arId = $arSplit[1];
    $critAr.=(($critAr)?',':'');
    $critAr.="('$arClass',$arId)";
  }
  $critDep="(predecessorRefType, predecessorRefId) IN ($critAr) and (successorRefType, successorRefId) IN ($critAr)";
  $dep=new Dependency();
  $depList=$dep->getSqlElementsFromCriteria(null,false,$critDep);
  foreach ($depList as $dep) {
    $pred="$dep->predecessorRefType#$dep->predecessorRefId";
    $succ="$dep->successorRefType#$dep->successorRefId";
    if (! isset($resultArray[$pred]) or ! isset($resultArray[$succ])) continue;
    $dep->id=null; // Wil create new with same info
    $newPred=explode('#',$resultArray[$pred]);
    $dep->predecessorRefType=$newPred[0];
    $dep->predecessorRefId=$newPred[1];
    $dep->predecessorId=null;
    $newSucc=explode('#',$resultArray[$succ]);
    $dep->successorRefType=$newSucc[0];
    $dep->successorRefId=$newSucc[1];
    $dep->successorId=null;
    $resultDep=$dep->save();
  }
  //$resultArray["$objectClass#$objectId"]=get_class($newObj).'#'.$newObj->id;
  // After copy grouped items : preserve the structure of the copied items
  $parentsToRenumber=array();
  $copiedParentPlanningElementIds=array();
  $sourcePlanningElements=array();
  foreach ($resultArray as $key=>$keyNew) {
    if (isset($copyPasteSourcePlanningElements[$key])) {
      $sourcePlanningElements[$key]=$copyPasteSourcePlanningElements[$key];
    } else {
      $keySplit=explode('#',$key);
      $oldPe=SqlElement::getSingleSqlElementFromCriteria('PlanningElement', array('refType'=>$keySplit[0], 'refId'=>$keySplit[1]));
      if ($oldPe and $oldPe->id) $sourcePlanningElements[$key]=$oldPe;
    }
  }
  uasort($sourcePlanningElements, function($a,$b) {
    if ($a->wbsSortable==$b->wbsSortable) return 0;
    return ($a->wbsSortable>$b->wbsSortable)?1:-1;
  });
  foreach ($sourcePlanningElements as $key=>$pe) {
    $topKey=null;
    $topWbs='';
    foreach ($sourcePlanningElements as $testKey=>$testPe) {
      if ($testKey==$key) continue;
      if (!$testPe->wbs or !$pe->wbs) continue;
      if (pq_substr($pe->wbs, 0, pq_strlen($testPe->wbs) + 1)==$testPe->wbs . '.' and pq_strlen($testPe->wbs)>pq_strlen($topWbs)) {
        $topKey=$testKey;
        $topWbs=$testPe->wbs;
      }
    }
    if ($topKey and isset($resultArray[$topKey])) {
      $keyNewSplit=explode('#',$resultArray[$key]);
      $newClass=$keyNewSplit[0];
      $newId=$keyNewSplit[1];
      $newItem=new $newClass($newId);
      $topKeyNewSplit=explode('#',$resultArray[$topKey]);
      $newTopClass=$topKeyNewSplit[0];
      $newTopId=$topKeyNewSplit[1];
      $topFld='id'.$newTopClass;
      if (property_exists($newItem,$topFld)) {
        if ($newTopClass=='Project' and property_exists($newItem, 'idProject')) {
          $newItem->idProject=$newTopId;
          if (property_exists($newItem, 'idActivity')) {
            $newItem->idActivity=null;
          }
        } else if ($newTopClass=='Activity' and property_exists($newItem, 'idActivity')) {
          $newTopItem=new Activity($newTopId);
          $newItem->idActivity=$newTopId;
          if (property_exists($newItem, 'idProject')) {
            $newItem->idProject=$newTopItem->idProject;
          }
        } else {
          $newItem->$topFld=$newTopId;
        }
        $resNewItem=$newItem->saveForced();
        if (getLastOperationStatus($resNewItem)!="OK") {
          errorLog("Copy paste selection parent restoration failed for $newClass #$newId : $resNewItem");
        } else {
          $peNew=SqlElement::getSingleSqlElementFromCriteria('PlanningElement', array('refType'=>$newClass,'refId'=>$newId));
          if ($peNew and $peNew->id) {
            $topPeNew=SqlElement::getSingleSqlElementFromCriteria('PlanningElement', array('refType'=>$newTopClass,'refId'=>$newTopId));
            $peNew->topId=($topPeNew and $topPeNew->id)?$topPeNew->id:null;
            if ($topPeNew and $topPeNew->id) $copiedParentPlanningElementIds[$topPeNew->id]=$topPeNew->id;
            $peNew->topRefType=$newTopClass;
            $peNew->topRefId=$newTopId;
            if ($newTopClass=='Activity') {
              $newTopItem=new Activity($newTopId);
              $peNew->idProject=$newTopItem->idProject;
            } else if ($newTopClass=='Project') {
              $peNew->idProject=$newTopId;
            }
            $peNew->wbs=null;
            $peNew->wbsSortable=null;
            $resPeNew=$peNew->saveForced();
            if (getLastOperationStatus($resPeNew)!="OK") {
              errorLog("Copy paste selection planning parent restoration failed for $newClass #$newId : $resPeNew");
            }
            if ($peNew->topId) $parentsToRenumber[$peNew->topId]=$peNew->topId;
          }
        }
      } else {
        $peNew=SqlElement::getSingleSqlElementFromCriteria('PlanningElement', array('refType'=>$newClass,'refId'=>$newId));
        if ($peNew and $peNew->id) {
          $topKeyNewSplit=explode('#',$resultArray[$topKey]);
          $topPeNew=SqlElement::getSingleSqlElementFromCriteria('PlanningElement', array('refType'=>$topKeyNewSplit[0],'refId'=>$topKeyNewSplit[1]));
          $peNew->topId=($topPeNew and $topPeNew->id)?$topPeNew->id:null;
          if ($topPeNew and $topPeNew->id) $copiedParentPlanningElementIds[$topPeNew->id]=$topPeNew->id;
          $peNew->topRefType=$topKeyNewSplit[0];
          $peNew->topRefId=$topKeyNewSplit[1];
          $resPeNew=$peNew->saveForced();
          if (getLastOperationStatus($resPeNew)=="OK" and $peNew->topId) $parentsToRenumber[$peNew->topId]=$peNew->topId;
        }
      }
    }
  }
  if ($copyAssignments) {
    foreach ($resultArray as $key=>$keyNew) {
      $keyNewSplit=explode('#',$keyNew);
      $newClass=$keyNewSplit[0];
      $newId=$keyNewSplit[1];
      $newItem=new $newClass($newId);
      if (! property_exists($newItem, 'idProject') or ! $newItem->idProject) continue;
      $ass=new Assignment();
      $lstAss=$ass->getSqlElementsFromCriteria(array('refType'=>$newClass, 'refId'=>$newId));
      foreach ($lstAss as $ass) {
        if ($ass->idProject==$newItem->idProject) continue;
        $ass->idProject=$newItem->idProject;
        $resAss=$ass->saveForced();
        if (getLastOperationStatus($resAss)!="OK") {
          errorLog("Copy paste selection assignment project restoration failed for Assignment #$ass->id : $resAss");
        }
      }
    }
  }
  $rootCopiedPlanningElements=array();
  foreach ($sourcePlanningElements as $key=>$oldPe) {
    $hasCopiedParent=false;
    foreach ($sourcePlanningElements as $testKey=>$testPe) {
      if ($testKey==$key) continue;
      if (!$testPe->wbs or !$oldPe->wbs) continue;
      if (pq_substr($oldPe->wbs, 0, pq_strlen($testPe->wbs) + 1)==$testPe->wbs . '.') {
        $hasCopiedParent=true;
        break;
      }
    }
    if ($hasCopiedParent) continue;
    $keyNewSplit=explode('#',$resultArray[$key]);
    $newPe=SqlElement::getSingleSqlElementFromCriteria('PlanningElement', array('refType'=>$keyNewSplit[0], 'refId'=>$keyNewSplit[1]));
    if (! $newPe or ! $newPe->id) continue;
    $rootCopiedPlanningElements[]=array('wbsSortable'=>$oldPe->wbsSortable, 'newPeId'=>$newPe->id);
    if ($newPe->topId) $parentsToRenumber[$newPe->topId]=$newPe->topId;
  }
  usort($rootCopiedPlanningElements, function($a,$b) {
    if ($a['wbsSortable']==$b['wbsSortable']) return 0;
    return ($a['wbsSortable']>$b['wbsSortable'])?1:-1;
  });
  if (count($rootCopiedPlanningElements)>0 and $copyTargetClass and $copyTargetId) {
    $rootIds=array();
    foreach ($rootCopiedPlanningElements as $rootCopiedPlanningElement) {
      $rootIds['#'.$rootCopiedPlanningElement['newPeId']]=$rootCopiedPlanningElement['newPeId'];
    }
    $targetChild=new PlanningElement();
    $targetChildren=$targetChild->getSqlElementsFromCriteria(array('topRefType'=>$copyTargetClass, 'topRefId'=>$copyTargetId), false, null, 'wbsSortable asc');
    $anchorId=null;
    foreach ($targetChildren as $targetChild) {
      if (! isset($rootIds['#'.$targetChild->id])) {
        $anchorId=$targetChild->id;
        break;
      }
    }
    if ($anchorId) {
      foreach ($rootCopiedPlanningElements as $rootCopiedPlanningElement) {
        $rootPe=new PlanningElement($rootCopiedPlanningElement['newPeId']);
        $moveResult=$rootPe->moveTo($anchorId, 'before');
        if (getLastOperationStatus($moveResult)!="OK") {
          errorLog("Copy paste selection root reorder failed for PlanningElement #$rootPe->id : $moveResult");
        }
      }
    }
  }
  $copiedPlanningElements=array();
  foreach ($resultArray as $key=>$keyNew) {
    if (! isset($sourcePlanningElements[$key])) continue;
    $oldPe=$sourcePlanningElements[$key];
    $keyNewSplit=explode('#',$keyNew);
    $newPe=SqlElement::getSingleSqlElementFromCriteria('PlanningElement', array('refType'=>$keyNewSplit[0], 'refId'=>$keyNewSplit[1]));
    if (! $newPe or ! $newPe->id) continue;
    $rootKey=$key;
    $rootWbs=$oldPe->wbs;
    foreach ($sourcePlanningElements as $testRootKey=>$testRootPe) {
      if ($testRootKey==$key) continue;
      if (!$testRootPe->wbs or !$oldPe->wbs) continue;
      if (pq_substr($oldPe->wbs, 0, pq_strlen($testRootPe->wbs) + 1)==$testRootPe->wbs . '.' and pq_strlen($testRootPe->wbs)<pq_strlen($rootWbs)) {
        $rootKey=$testRootKey;
        $rootWbs=$testRootPe->wbs;
      }
    }
    $copiedPlanningElements[]=array(
        'key'=>$key,
        'rootKey'=>$rootKey,
        'oldWbs'=>$oldPe->wbs,
        'newPeId'=>$newPe->id
    );
  }
  usort($copiedPlanningElements, function($a,$b) {
    if ($a['oldWbs']==$b['oldWbs']) return 0;
    return (formatSortableWbs($a['oldWbs'])>formatSortableWbs($b['oldWbs']))?1:-1;
  });
  foreach ($copiedPlanningElements as $copiedPlanningElement) {
    if (! isset($resultArray[$copiedPlanningElement['rootKey']])) continue;
    if (! isset($sourcePlanningElements[$copiedPlanningElement['rootKey']])) continue;
    $rootOldPe=$sourcePlanningElements[$copiedPlanningElement['rootKey']];
    $rootNewKeySplit=explode('#',$resultArray[$copiedPlanningElement['rootKey']]);
    $rootNewPe=SqlElement::getSingleSqlElementFromCriteria('PlanningElement', array('refType'=>$rootNewKeySplit[0], 'refId'=>$rootNewKeySplit[1]));
    if (! $rootOldPe or ! $rootOldPe->id or ! $rootNewPe or ! $rootNewPe->id) continue;
    $newPe=new PlanningElement($copiedPlanningElement['newPeId']);
    if (! $newPe or ! $newPe->id) continue;
    if ($copiedPlanningElement['key']==$copiedPlanningElement['rootKey']) {
      $newWbs=$rootNewPe->wbs;
    } else {
      $suffix=pq_substr($copiedPlanningElement['oldWbs'], pq_strlen($rootOldPe->wbs)+1);
      $newWbs=$rootNewPe->wbs . '.' . $suffix;
    }
    if ($newWbs and $newPe->wbs!=$newWbs) {
      $newPe->wbs=$newWbs;
      $newPe->wbsSortable=formatSortableWbs($newWbs);
      $resWbs=$newPe->saveForced();
      if (getLastOperationStatus($resWbs)!="OK") {
        errorLog("Copy paste selection WBS restoration failed for PlanningElement #$newPe->id : $resWbs");
      }
    }
  }
  foreach ($copiedParentPlanningElementIds as $parentPeId) {
    $parentPe=new PlanningElement($parentPeId);
    if ($parentPe and $parentPe->id and $parentPe->elementary!=0) {
      $parentPe->elementary=0;
      $resParentPe=$parentPe->saveForced();
      if (getLastOperationStatus($resParentPe)!="OK") {
        errorLog("Copy paste selection parent group restoration failed for PlanningElement #$parentPe->id : $resParentPe");
      }
    }
  }
}

/*function copyStructure($from, $to, $copyToOrigin, $copyToWithNotes, $copyToWithAttachments,$copyToWithLinks, $copyAssignments) {
  	$nbErrors=0;
  	$errorFullMessage="";
  	$milArray=array();
    $milArrayObj=array();
    $actArray=array();
    $actArrayObj=array();
    $crit=array('idActivity'=>$from->id);
    $items=array();
    // Activities to be copied
    $activity=New Activity();
    $activities=$activity->getSqlElementsFromCriteria($crit, false, null, null, true);
    foreach ($activities as $activity) {
      $act=new Activity($activity->id);
      $items['Activity_'.$activity->id]=$act;
    }
    $mile=New Milestone();
    $miles=$mile->getSqlElementsFromCriteria($crit, false, null, null, true);
    foreach ($miles as $mile) {
      $mil=new Milestone($mile->id);
      $items['Milestone_'.$mile->id]=$mil;
    }
    // Sort by wbsSortable
    uasort($items, "customSortByWbsSortable");
    $itemArrayObj=array();
    $itemArray=array();
    $itemArrayAssignment=array();
    foreach ($items as $id=>$item) {
      //$new=$item->copy();
      //$toTypeFld='id'.get_class($item).'Type';
      $new=$new=$item->copy();
      $tmpRes=$new->_copyResult;
      if (! pq_stripos($tmpRes,'id="lastOperationStatus" value="OK"')>0 ) {
        errorLog($tmpRes);
        $errorFullMessage.='<br/>'.i18n(get_class($item)).' #'.htmlEncode($item->id)." : ".$tmpRes;
        $nbErrors++;
      } else {
        $itemArrayObj[get_class($new) . '_' . $new->id]=$new;
        $itemArray[$id]=get_class($new) . '_' . $new->id;
        if ($copyAssignments and property_exists($item, '_Assignment')) {
  	      $itemArrayAssignment[]=array('class'=>get_class($item),'oldId'=>$item->id,'newId'=>$new->id);
  	    }
      }
    }
    foreach ($itemArrayObj as $new) {
      $new->idProject=$from->idProject;
      $new->idActivity=$to->id;
      $pe=get_class($new).'PlanningElement';
      $new->$pe->wbs=null;
      $tmpRes=$new->save();
      if (! pq_stripos($tmpRes,'id="lastOperationStatus" value="OK"')>0 ) {
        errorLog($tmpRes);
        $errorFullMessage.='<br/>'.i18n(get_class($new)).' #'.htmlEncode($new->id)." : ".$tmpRes;
        $nbErrors++;
      } 
    }
    if ($copyAssignments) {
      foreach ($itemArrayAssignment as $item) {
        $ass=new Assignment();
        $crit=array('refType'=>$item['class'], 'refId'=>$item['oldId']);
        $lstAss=$ass->getSqlElementsFromCriteria($crit);
        foreach ($lstAss as $ass) {
          $ass->id=null;
          $ass->idProject=$from->idProject;
          $ass->refId=$item['newId'];
          $ass->comment=null;
          $ass->realWork=0;
          $ass->leftWork=$ass->assignedWork;
          $ass->plannedWork=$ass->assignedWork;
          $ass->realStartDate=null;
          $ass->realEndDate=null;
          $ass->plannedStartDate=null;
          $ass->plannedEndDate=null;
          $ass->realCost=0;
          $ass->leftCost=$ass->assignedCost;
          $ass->plannedCost=$ass->assignedCost;
          $ass->billedWork=null;
          $ass->idle=0;
          $ass->save();
        }
      }
    }
    // Copy dependencies 
    $critWhere="";
    foreach ($itemArray as $id=>$new) {
      $split=pq_explode('_',$id);
      $critWhere.=($critWhere)?', ':'';
      $critWhere.="('" . $split[0] . "','" . Sql::fmtId($split[1]) . "')";
    }
    if ($critWhere) {
      $clauseWhere="(predecessorRefType,predecessorRefId) in (" . $critWhere . ")"
           . " or (successorRefType,successorRefId) in (" . $critWhere . ")";
    } else {
      $clauseWhere=" 1=0 ";
    }
    $dep=New dependency();
    $deps=$dep->getSqlElementsFromCriteria(null, false, $clauseWhere);
    foreach ($deps as $dep) {
      if (pq_array_key_exists($dep->predecessorRefType . "_" . $dep->predecessorRefId, $itemArray) ) {
        $split=pq_explode('_',$itemArray[$dep->predecessorRefType . "_" . $dep->predecessorRefId]);
        $dep->predecessorRefType=$split[0];
        $dep->predecessorRefId=$split[1];
        $crit=array('refType'=>$split[0], 'refId'=>$split[1]);
        $pe=SqlElement::getSingleSqlElementFromCriteria('PlanningElement', $crit);
        $dep->predecessorId=$pe->id;
      }
      if (pq_array_key_exists($dep->successorRefType . "_" . $dep->successorRefId, $itemArray) ) {
        $split=pq_explode('_',$itemArray[$dep->successorRefType . "_" . $dep->successorRefId]);
        $dep->successorRefType=$split[0];
        $dep->successorRefId=$split[1];
        $crit=array('refType'=>$split[0], 'refId'=>$split[1]);
        $pe=SqlElement::getSingleSqlElementFromCriteria('PlanningElement', $crit);
        $dep->successorId=$pe->id;
      }
      $dep->id=null;
      $tmpRes=$dep->save();
      if (! pq_stripos($tmpRes,'id="lastOperationStatus" value="OK"')>0 ) {
        errorLog($tmpRes);
        $errorFullMessage.='<br/>'.i18n(get_class($dep)).' #'.htmlEncode($dep->id)." : ".$tmpRes;
        $nbErrors++;
      } 
    }
    $result="OK";
    if ($nbErrors>0) {
      $result='<div class="messageERROR" >' 
             . i18n('errorMessageCopy',array($nbErrors))
             . '</div><br/>'
             . pq_str_replace('<br/><br/>','<br/>',$errorFullMessage);
    }
    return $result;
}
function customSortByWbsSortable($a,$b) {
  $pe=get_class($a).'PlanningElement';
  $wbsA=$a->$pe->wbsSortable;
  $pe=get_class($b).'PlanningElement';
  $wbsB=$b->$pe->wbsSortable;
  return ($wbsA > $wbsB)?1:-1;
}*/
?>
