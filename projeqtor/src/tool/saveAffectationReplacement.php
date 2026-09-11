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
scriptLog('   ->/tool/saveAffectationReplacement.php');
// Get the info
if (! pq_array_key_exists('replaceAffectationIdAffectation',$_REQUEST)) {
  throwError('replaceAffectationIdAffectation parameter not found in REQUEST');
}
$id=($_REQUEST['replaceAffectationIdAffectation']); // validated to be numeric value in SqlElement base constructor.
$aff=new Affectation($id);

if (! pq_array_key_exists('replaceAffectationResource',$_REQUEST) ) {
  throwError('replaceAffectationResource parameter not found in REQUEST');
}
$resource=($_REQUEST['replaceAffectationResource']); // escaped before used in DB queries

if (! pq_array_key_exists('replaceAffectationProfile',$_REQUEST) ) {
  throwError('replaceAffectationProfile parameter not found in REQUEST');
}
$profile=($_REQUEST['replaceAffectationProfile']); // escaped before used in DB queries

if (! pq_array_key_exists('replaceAffectationRate',$_REQUEST)) {
  throwError('replaceAffectationRate parameter not found in REQUEST');
}
$rate=($_REQUEST['replaceAffectationRate']);
Security::checkValidNumeric($rate);

// $startDate="";
// if (pq_array_key_exists('replaceAffectationStartDate',$_REQUEST)) {
// 	$startDate=pq_trim($_REQUEST['replaceAffectationStartDate']);;
// }
// Security::checkValidDateTime($startDate);

// $endDate="";
// if (pq_array_key_exists('replaceAffectationEndDate',$_REQUEST)) {
// 	$endDate=pq_trim($_REQUEST['replaceAffectationEndDate']);;
// }
// Security::checkValidDateTime($endDate);

$startDate = RequestHandler::getDatetime('replaceAffectationStartDate');
$endDate = RequestHandler::getDatetime('replaceAffectationEndDate');

$paramAutoAff=Parameter::getGlobalParameter('autoAffectationPool');

$idle=0;

if($aff->idResource!=''){
  $oldRes=new ResourceAll($aff->idResource);
}else{
  $oldRes=new ResourceAll($aff->idResourceSelect);
}

$resObj=new ResourceAll($resource);

$rc=new ResourceCost();
$crit=array('idResource'=>$resource,'endDate'=>null);
$rcList=$rc->getSqlElementsFromCriteria($crit,null,null,'id asc');
$costArray=array();
$defaultRole=$resObj->idRole;
$defaultCost=0;
if (count($rcList)>0) {
  foreach ($rcList as $rc) {
    $costArray[$rc->idRole]=$rc->cost;
    if ($rc->idRole==$defaultRole) {
      $defaultCost=$rc->cost;
    }
    $last=$rc->idRole;
  }
  if (!$defaultCost) {
    $defaultRole=$last;
    $defaultCost=$costArray[$defaultRole];
  }
}

Sql::beginTransaction();

// Save new affectation
$newAff=new Affectation();
$newAff->idProject=$aff->idProject;
$newAff->idResource=$resource;
$newAff->idle=$idle;
$newAff->rate=$rate;
$newAff->startDate=$startDate;
$newAff->endDate=$endDate;
$newAff->idProfile=$profile;
$result=$newAff->save();


//gautier #5597
if($endDate){
  $newAffOld = new Affectation();
  if($aff->endDate){
    $newAffOld->endDate = $aff->endDate;
  }
  $endNew=addWorkDaysToDate($endDate, 2, $aff->idProject);
  $newAffOld->startDate = $endNew;
  $newAffOld->idResource = $aff->idResource;
  $newAffOld->idProject=$aff->idProject;
  $newAffOld->rate=$aff->rate;
  $newAffOld->idProfile=$aff->idProfile;
  $newAffOld->save();
}

// save old affectation
if ($startDate) {
  $endTst=addWorkDaysToDate($startDate, -1, $aff->idProject);
  if (($endTst>=$aff->startDate and !$aff->endDate)  or ($endTst>=$aff->startDate and $endTst<=$aff->endDate)) $aff->endDate=$endTst;
  if ($aff->endDate and $aff->endDate<date('Y-m-d')) {
    $aff->idle=1;
  }
} else {
  $aff->idle=1;
}

$aff->save();

if($paramAutoAff=='IMPLICIT' and $oldRes->isResourceTeam==1 and $aff->idle==1){
  $allAffImpl=$aff->getSqlElementsFromCriteria(array('idResourceTeam'=>$oldRes->id));
  foreach ($allAffImpl as $affImp){
    $affImp->idle=1;
    $affImp->save();
  }
}

$proj=new Project($newAff->idProject);
$listProj=getListToChange($proj,$aff->idResource);
$crit='idProject in '.transformListIntoInClause($listProj).' and idResource='.$aff->idResource;


// Change the assignments
$ass=new Assignment();
$assRec=new AssignmentRecurring();
$critRes='idAssignment in ( select id from '.$ass->getDatabaseTableName().' where '.$crit.')';
$resAss=array();

$assList=$ass->getSqlElementsFromCriteria(null,null,$crit);
$assRecLst=$assRec->getSqlElementsFromCriteria(null,null,$critRes,'idAssignment asc');


$pw=new PlannedWork();
$pwM=new PlannedWorkManual();
foreach ($assList as $ass) {
  $needNew=true;
  $needChangePM=false;
  $where='idAssignment='.$ass->id;
  $left=0;
  $assigned=0;
  $leftM=$pwM->sumSqlElementsFromCriteria('work', null, $where);
  if($leftM!=0){
    $needChangePM=true;
  }
  if (! $startDate and !$endDate) {
    $left=$ass->leftWork;
    $assigned=$ass->assignedWork;
    if ($ass->realWork==0) {
      $needNew=false;
    }
  } else {
    if ($startDate){
      $where.=" and workDate>='$startDate'";
    }
    if($endDate){
      $where.=" and workDate<='$endDate'";
    }
    $left=$pw->sumSqlElementsFromCriteria('work', null, $where);
    if ($ass->realWork==0 and ($left==$ass->leftWork or $leftM==$ass->leftWork )) {
      $needNew=false;
    }
  }
  if ($left>0 or $assigned>=0) {
    if ($needNew) {
        $newAss = Assignment::getSingleSqlElementFromCriteria('Assignment', array('idProject'=>$ass->idProject,'refType'=>$ass->refType,'refId'=>$ass->refId,'idResource'=>$resource));     
        if($newAss->id){
          $newAss->assignedWork+=$left;
          $newAss->leftWork+=$left;
          $ass->assignedWork-=$left;
          if ($ass->assignedWork<0) $ass->assignedWork=0;
          $ass->leftWork-=$left;
          if ($ass->leftWork<0) $ass->leftWork=0;
        }else{
          $newAss=new Assignment();
          $newAss->idProject=$ass->idProject;
          $newAss->refType=$ass->refType;
          $newAss->refId=$ass->refId;
          $newAss->assignedWork=$left;
          $newAss->leftWork=$left;
          $ass->assignedWork-=$left;
          if ($ass->assignedWork<0) $ass->assignedWork=0;
          $ass->leftWork-=$left;
          if ($ass->leftWork<0) $ass->leftWork=0;
        }
    } else {
      if($ass->isResourceTeam and $ass->uniqueResource){
         if(!$resObj->isResourceTeam){
           $ass->isResourceTeam=0;
         }
         $ass->uniqueResource=0;
      }
      $newAss=$ass;
    } 
    $newAss->idResource=$resource;;
    $newAss->plannedWork=$newAss->realWork+$newAss->leftWork;
    $newAss->notPlannedWork=0;
    $newAss->rate=$rate;
    if ($resObj->isResourceTeam and !$oldRes->isResourceTeam) { // deduct capacity from rate
      $newAss->capacity=round($oldRes->capacity*$ass->rate/100,2);
    }
    $newAss->isResourceTeam=$resObj->isResourceTeam;
    $newAss->idRole=(isset($costArray[$ass->idRole]))?$ass->idRole:$defaultRole;
    $newAss->dailyCost=(isset($costArray[$ass->idRole]))?$costArray[$ass->idRole]:$defaultCost;
    $newAss->newDailyCost=$newAss->dailyCost;
    $newAss->assignedCost=$newAss->assignedWork*$newAss->dailyCost;
    $newAss->leftCost=$newAss->leftWork*$newAss->dailyCost;
    $newAss->plannedCost=$newAss->plannedWork*$newAss->dailyCost;
    $newAss->save();
    $resAss[$ass->id]=$newAss->id;
    if ($needNew) $ass->save();
   if($needChangePM){
      $purgePw=false;
      $dbTableName=array($pwM->getDatabaseTableName(),$pw->getDatabaseTableName());
      foreach ($dbTableName as $name){
        $query="UPDATE ".$name." SET  ".$name.".idResource = ".$newAss->idResource." WHERE ".$name.".idAssignment = ".$ass->id." and ".$name.".idResource = ".$oldRes->id;
        if($startDate!='' and $endDate==''){
          $query.=" and ".$name.".workDate >= '$startDate' ";
          $purgePw=true;
        }else if($startDate!='' and $endDate!=''){
          $query.=" and ".$name.".workDate between '$startDate' and '$endDate' ";
          $purgePw=true;
        }
        SqlDirectElement::execute($query);
      }
    }else{
      $pw->purge($where);
    }
  }
}

foreach ($assRecLst as $assReToChange){
  if(pq_array_key_exists($assReToChange->idAssignment, $resAss) and $assReToChange->idAssignment!=$resAss[$assReToChange->idAssignment]){
    $newRec=new AssignmentRecurring();
    $newRec->day=$assReToChange->day;
    $newRec->idAssignment=$resAss[$assReToChange->idAssignment];
    $newRec->idResource=$resource;
    $newRec->refId=$assReToChange->refId;
    $newRec->refType=$assReToChange->refType;
    $newRec->value=$assReToChange->value;
    $newRec->type=$assReToChange->type;
    $newRec->save();
  }else{
    $assReToChange->idResource=$resource;
    $assReToChange->save();
  }
}

// Message of correct saving
displayLastOperationStatus($result);

function getListTochange($proj,$idRes) {
  $result=array();
  $result[$proj->id]=$proj->name;
  $subProjList=$proj->getSubProjects(true,true);
  foreach ($subProjList as $subProj) {
    $aff=new Affectation();
    $countAff=$aff->countSqlElementsFromCriteria(array('idProject'=>$subProj->id,'idResource'=>$idRes));
    if ($countAff==0) {
      $result=array_merge_preserve_keys($result,getListTochange($subProj,$idRes));
    }
  }
  return $result;
}

?>