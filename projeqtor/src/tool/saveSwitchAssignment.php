<?php 
/*** COPYRIGHT NOTICE *********************************************************
 *
 * Copyright 2009-2015 ProjeQtOr - Pascal BERNARD - support@projeqtor.org
 * Contributors : -
 *
 * This file is part of ProjeQtOr.
 * 
 * ProjeQtOr is free software: you can redistribute it and/or modify it under 
 * the terms of the GNU General Public License as published by the Free 
 * Software Foundation, either version 3 of the License, or (at your option) 
 * any later version.
 * 
 * ProjeQtOr is distributed in the hope that it will be useful, but WITHOUT ANY
 * WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS 
 * FOR A PARTICULAR PURPOSE.  See the GNU General Public License for 
 * more details.
 *
 * You should have received a copy of the GNU General Public License along with
 * ProjeQtOr. If not, see <http://www.gnu.org/licenses/>.
 *
 * You can get complete code of ProjeQtOr, other resource, help and information
 * about contributors at http://www.projeqtor.org 
 *     
 *** DO NOT REMOVE THIS NOTICE ************************************************/

/* ============================================================================
 * Habilitation defines right to the application for a menu and a profile.
 */ 
require_once "../tool/projeqtor.php";
scriptLog('saveSwitchAssignment.php');

$idResource = RequestHandler::getValue('idResource');
$affectation = new Affectation();
$critArray= array('idResource'=>$idResource);
$allAffectations = $affectation->getSqlElementsFromCriteria($critArray);
$resultArray = array();
$startDate = RequestHandler::getValue('newAffectationStartDate');

$newAffectations = array();

$oldRes=new ResourceAll($idResource);

Sql::beginTransaction();

foreach ($allAffectations as $aff) {
  if (RequestHandler::isCodeSet('assignmentProject_'.$aff->idProject)) {
    if ($aff->idle==1) continue; // PBER #7315
    $proj=new Project($aff->idProject);
    if ($proj->idle==1) continue; // PBER #7315
    $newResource = RequestHandler::getValue('assignmentProject_'.$aff->idProject);
    if ($newResource !== null && $newResource !== " ") {
      $resObj=new ResourceAll($newResource);
      $newAff=new Affectation();
      $newAffList = $newAff->getSqlElementsFromCriteria(array('idResource'=>$newResource,'idProject'=>$aff->idProject,'idle'=>'0'));
      
      if(count($newAffList) <= 0){
        $newAff->idProject=$aff->idProject;
        $newAff->idResource=$newResource;
        if ($startDate !== ''){
          $newAff->startDate=$startDate;
        }
        $resultArray[]=$newAff->save();
      }
      if ($startDate !== '') {
        $endTst=addWorkDaysToDate($startDate, -1);
        if (($endTst>=$aff->startDate and !$aff->endDate)  or ($endTst>=$aff->startDate and $endTst<=$aff->endDate)) $aff->endDate=$endTst;
        if ($aff->endDate and $aff->endDate<date('Y-m-d')) {
          $aff->idle=1;
        }
      } else {
        $aff->idle=1;
      }

      if (securityGetAccessRightYesNo('menuAffectation', 'update',$aff)=='YES') $resultArray[]=$aff->save();
            
      if ($proj->idResource == $oldRes->id) {
        $proj->idResource = $newResource;
        $resultArray[]=$proj->save();
      }
      
      $listProj=getListToChange($proj,$aff->idResource);
      $crit='idProject in '.transformListIntoInClause($listProj).' and idResource='.$aff->idResource;
      
      $ass=new Assignment();
      $assRec=new AssignmentRecurring();
      //$critRes='idAssignment in ( select id from '.$ass->getDatabaseTableName().' where '.$crit.')';
      //$critRes.=" and idle=0"; // PBER #7315
      $critRes='idAssignment in ( select id from '.$ass->getDatabaseTableName().' where '.$crit.' and idle=0)';
      $resAss=array();
      
      $assList=$ass->getSqlElementsFromCriteria(null,null,$crit);
      $assRecLst=$assRec->getSqlElementsFromCriteria(null,null,$critRes,'idAssignment asc');

      $pw=new PlannedWork();
      $pwM=new PlannedWorkManual();
      foreach ($assList as $ass) {
        if ($ass->idle==1) continue; // PBER #7315
        $refType=$ass->refType;
        $refObj=new $refType($ass->refId, true);
        if ($refObj->idle==1) continue; // PBER #7315
        $needNew=true;
        $needChangePM=false;
        $where='idAssignment='.$ass->id;
        $left=0;
        $assigned=0;
        $leftM=$pwM->sumSqlElementsFromCriteria('work', null, $where);

        if (! $startDate) {
          $left=$ass->leftWork;
          $assigned=$ass->assignedWork;
          if ($ass->realWork==0) {
            $needNew=false;
          }
        } else {
          if ($startDate){
            $where.=" and workDate>='$startDate'";
          }
          $left=$pw->sumSqlElementsFromCriteria('work', null, $where);
          if ($ass->realWork==0 and ($left==$ass->leftWork or $leftM==$ass->leftWork )) {
            $needNew=false;
          }
        }

        if($leftM!=0){
          $needChangePM=true;
        }
        
        if ($left>0 or $assigned>=0) {
          if ($needNew) {
            $newAss = Assignment::getSingleSqlElementFromCriteria('Assignment', array('idProject'=>$ass->idProject,'refType'=>$ass->refType,'refId'=>$ass->refId,'idResource'=>$newResource));
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
          if ($needNew) $resultArray[]=$ass->save();
          if($startDate !== '') $newAss->plannedStartDate = $startDate; 
          $newAss->idResource=$newResource;;
          $newAss->plannedWork=$newAss->realWork+$newAss->leftWork;
          $newAss->notPlannedWork=0;
          if ($resObj->isResourceTeam and !$oldRes->isResourceTeam) { // deduct capacity from rate
            $newAss->capacity=round($oldRes->capacity*$ass->rate/100,2);
          }
          $newAss->isResourceTeam=$resObj->isResourceTeam;
          $newAss->idRole=(isset($costArray[$ass->idRole]))?$ass->idRole:$resObj->idRole;
          $newAss->dailyCost=(isset($costArray[$ass->idRole]))?$costArray[$ass->idRole]:0;
          $newAss->newDailyCost=$newAss->dailyCost;
          $newAss->assignedCost=$newAss->assignedWork*$newAss->dailyCost;
          $newAss->leftCost=$newAss->leftWork*$newAss->dailyCost;
          $newAss->plannedCost=$newAss->plannedWork*$newAss->dailyCost;
          $resultArray[]=$newAss->save();
          $resAss[$ass->id]=$newAss->id;
          if($needChangePM){
            $purgePw=false;
            $dbTableName=array($pwM->getDatabaseTableName(),$pw->getDatabaseTableName());
            foreach ($dbTableName as $name){
              $query="UPDATE ".$name." SET  ".$name.".idResource = ".$newAss->idResource." WHERE ".$name.".idAssignment = ".$ass->id." and ".$name.".idResource = ".$oldRes->id;
              if($startDate!=''){
                $query.=" and ".$name.".workDate >= '$startDate' ";
                $purgePw=true;
              }
              SqlDirectElement::execute($query);
            }
          }else{
            $pw->purge($where);
          }
        }
        $listType = array('Action', 'Activity', 'Issue', 'Milestone', 'Risk', 'Ticket', 'Decision', 'Meeting', 'Question', 'Requirement', 'TestCase', 'TestSession');
        foreach($listType as $type) {
          $item = new $type();
          $items = $item->getSqlElementsFromCriteria(array('idProject'=>$ass->idProject,'idResource'=>$idResource, 'idle'=>'0')); // PBER #7315
          foreach($items as $item) {
            if ($item->idle==1) continue; // PBER #7315
            $item->idResource = $newResource;
            $resultArray[]=$item->save();
          }
        }
      }
      foreach ($assRecLst as $assReToChange){
        if(pq_array_key_exists($assReToChange->idAssignment, $resAss) and $assReToChange->idAssignment!=$resAss[$assReToChange->idAssignment]){
          $newRec=new AssignmentRecurring();
          $newRec->day=$assReToChange->day;
          $newRec->idAssignment=$resAss[$assReToChange->idAssignment];
          $newRec->idResource=$newResource;
          $newRec->refId=$assReToChange->refId;
          $newRec->refType=$assReToChange->refType;
          $newRec->value=$assReToChange->value;
          $newRec->type=$assReToChange->type;
          $newRec->save();
        }else{
          $assReToChange->idResource=$newResource;
          $assReToChange->save();
        }
      }
    }    
  }
}

if (isset($resultArray)) {
  $KOArray = array();
  $KOmsg='OK';
  foreach ($resultArray as $result){
    $status=getLastOperationStatus($result);
    $msg=getLastOperationMessage($result);
    if ($status!='OK') {
      if ($status=='ERROR') {
        $KOmsg='ERROR';
      } if ($status=='INVALID' and $KOmsg!='ERROR') {
        $KOmsg='INVALID';
      } else {
        $KOmsg=$status;
      }
      $KOArray[]='<div>'.pq_substr($result,pq_strpos($result,'<br/><br/>')+10).'</div>';
    }
  }
  sql::commitTransaction();
  if(count($KOArray)>0){
    echo '<div class="message'.$KOmsg.'" >';
    foreach ($KOArray as $KO){
      echo $KO;
      echo '<br/>';
    }
    echo '</div>';
  }else{
    echo '<div class="messageOK" >'.i18n('dialogSwitchAssignment').' '.i18n("done").'</div>';
    echo '<input type="hidden" id="lastOperation" name="lastOperation" value="save">';
    echo '<input type="hidden" id="lastOperationStatus" name="lastOperationStatus" value="OK">';
  }
}

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
