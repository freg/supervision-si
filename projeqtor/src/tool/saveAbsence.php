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

/** ============================================================================
 * Save real work allocation.
 */

require_once "../tool/projeqtor.php";

//parameter
$isCurrent=(RequestHandler::isCodeSet('isCurrent'))?true:false;
$isBetweenToDate=(RequestHandler::isCodeSet('isBetweenToDate'))?true:false;
$userId = RequestHandler::getId('userId');
$workVal = RequestHandler::getNumeric('workVal');
$idProject = RequestHandler::getId('idProject');
$actId = RequestHandler::getId('actId');
$assId = RequestHandler::getId('assId');


$res= new ResourceAll($userId,true);
$etp= round($res->capacity,2);

$unitAbs = Parameter::getGlobalParameter('imputationUnit');
$plannedWorkM= new PlannedWorkManual();
$editWork = false;

if($isCurrent){ // <==================== add current absences
  $workEl = new Work();
  $act= new Activity();
  $lstDayFlatList=RequestHandler::getValue("lstDaysFlatList");
  $lstDay=array_flip(pq_explode(",", RequestHandler::getValue("lstDays")));
  $lstOtherWork=array();
  $lstWorkMan=array();
  $updateWorkForAct=array();
  $lastWorDay="";
  
  //========================================Get Planned work Manual===================================================//
  $where="workDate in ($lstDayFlatList) and idResource=$userId ";
  $asWork=$plannedWorkM->getSqlElementsFromCriteria(null,false,$where,"workDate asc");

  if(!empty($asWork)){
    foreach ($asWork as $id=>$work){
      if($lastWorDay!=$work->workDate){
        $lastWorDay=$work->workDate;
        $lstWorkMan[$work->workDate]=$work->work;
      }else{
        $lstWorkMan[$work->workDate]+=$work->work;
      }
    }
  }
  foreach ($lstWorkMan as $date=>$work){
    if($work+$workVal>$etp){
      $time=pq_strtotime($date);
      $formatedDate=date('Ymd',$time);
      
      if(strpos($lstDayFlatList, ','.$formatedDate)!==false){
        $lstDayFlatList=pq_str_replace(','.$formatedDate, "", $lstDayFlatList);
      }else if(strpos($lstDayFlatList, $formatedDate.',')!==false){
        $lstDayFlatList=pq_str_replace($formatedDate.',', "", $lstDayFlatList);
      }else if(strpos($lstDayFlatList, $formatedDate)!==false){
        $lstDayFlatList=pq_str_replace($formatedDate, "", $lstDayFlatList);
      }
      unset($lstDay[$date]);
    }else{
      $lstOtherWork[$date]=$work;
    }
  }
  //===========================//
  //=========get work==========//
  $where="idResource =$userId and day in ($lstDayFlatList) and refType = 'Activity' ";
  if($workVal == 0)$where .=" and  idProject=$idProject and  refId =$actId and idAssignment =$assId";
  $listWork = $workEl->getSqlElementsFromCriteria(null,false,$where);
  
  Sql::beginTransaction();
  
  // delete work =====
  PlanningElement::$_noDispatch=true;
  if ($workVal == 0){
    foreach ($listWork as $isWork){
      $isWork->deleteWork();
    }
    PlanningElement::updateSynthesis(get_class($act), $actId);
    PlanningElement::$_noDispatch=false;
  }else{ // add or replace work =====
    
    //=====checkup for work to  add for know is taller than resource capacity =====//
    if($unitAbs != 'days'){
      $maxHour = Parameter::getGlobalParameter('dayTime');
      $sumWork = $workVal/$maxHour;
    }else{
      $sumWork = $workVal;
    }
    //==================================//
    if ($sumWork<=$etp){
      $countEdit=0;
      $countOtherAct=0;
      $alreadyRegistered=array();
      $nochange=true;
      
      //=================existing work================//
      if(!empty($listWork)){
        foreach ($listWork as $isWork){
          unset($lstDay[$isWork->workDate]);
          if($isWork->idAssignment!=$assId ){
            $countOtherAct++;
            if(isset($lstOtherWork[$isWork->workDate]))$lstOtherWork[$isWork->workDate]+=$isWork->work;
            else $lstOtherWork[$isWork->workDate]=$isWork->work;
            continue;
          }else{
            if($isWork->work==$sumWork){
              $alreadyRegistered[$isWork->workDate]=true;
              continue;
            }else{
              $updateWorkForAct[$isWork->workDate]=$isWork;
            }
          }
        }
        //=================existing work for this absence and update this=================//
        if(!empty($updateWorkForAct)){
          foreach ($updateWorkForAct as $dateW=>$w){
            if(pq_array_key_exists($dateW,$lstOtherWork) and ($lstOtherWork[$dateW]+$sumWork)>$etp){//existing work for this date and this work+ absence work > capcity resource
              unset($lstOtherWork[$dateW]);
              continue;
            }
            $nochange=($nochange)?false:$nochange;
            $w->work =$sumWork;
            $res=$w->saveWork();
            $countEdit++;
          }
        }
        //==========================================//
      }

      
      if($countOtherAct>0){
        foreach ($lstOtherWork as $date=>$workValue){
          if(pq_array_key_exists($date, $alreadyRegistered))continue;
          if(pq_array_key_exists($date, $updateWorkForAct))continue;
          if($workValue+$sumWork <=$etp ){
            $nochange=($nochange)?false:$nochange;
            $newWork= new Work();
            $newWork->refType = 'Activity';
            $newWork->refId = $actId;
            $newWork->setDates($date);
            $newWork->idResource = $userId;
            $newWork->work = $sumWork;
            $newWork->idProject = $idProject;
            $newWork->idAssignment = $assId;
            $res=$newWork->saveWork();
          }
        }
      }
      
      $lstDay=array_flip($lstDay);
      if((($countEdit!=count($listWork) and count($listWork)!=0) or count($listWork)==0) and count($lstDay)!=0 ) {
        foreach ($lstDay as $absDay){
          $newWork= new Work();
          $newWork->refType = 'Activity';
          $newWork->refId = $actId;
          $newWork->setDates($absDay);
          $newWork->idResource = $userId;
          $newWork->work = $sumWork;
          $newWork->idProject = $idProject;
          $newWork->idAssignment = $assId;
          $res=$newWork->saveWork();
        }
      }else{
        if($nochange){
          $result = 'warning';
          echo $result;
        }
        
      }
      PlanningElement::updateSynthesis(get_class($act), $actId);
      PlanningElement::$_noDispatch=false;
    }else{
      $result = 'warning';
      echo $result;
    }
  }
  Sql::commitTransaction();
  
}else if($isBetweenToDate){ // <==================== add absence beetwen to dates
  $workEl = new Work();
  $act= new Activity();
  $startDate=new DateTime(RequestHandler::getValue("startDate"));
  $startDate=$startDate->format("Y-m-d");
  $enDate=new DateTime(RequestHandler::getValue("endDate"));
  $enDate=$enDate->format("Y-m-d");
  $lastWorDay="";
  $lstWorkMan=array();
  $lstOtherWork=array();
  $dayFull=array();
  $updateWorkForAct=array();
  
  //========================================Get Planned work Manual===================================================//
  $where="workDate>='$startDate' and workDate<='$enDate' and idResource=$userId ";
  $asWork=$plannedWorkM->getSqlElementsFromCriteria(null,false,$where,"workDate asc");
  if(!empty($asWork)){
    foreach ($asWork as $id=>$work){
      if($lastWorDay!=$work->workDate){
        $lastWorDay=$work->workDate;
        $lstWorkMan[$work->workDate]=$work->work;
      }else{
        $lstWorkMan[$work->workDate]+=$work->work;
      }
    }
  }
  foreach ($lstWorkMan as $date=>$work){
    if($work+$workVal<=$etp)$lstOtherWork[$date]=$work; //has workManual but can have work additional
    else $dayFull[$date]=true; //has workManual and is full for this day 
  }
  //===========================//
  //=========get work==========//
  $where="idResource =$userId and workDate >='$startDate' and workDate <='$enDate' ";
  if($workVal == 0)$where .=" and  idProject=$idProject and  refId =$actId and idAssignment =$assId";
  $listWork = $workEl->getSqlElementsFromCriteria(null,false,$where);
  $idCalendar=strval($res->idCalendarDefinition);
  //===========================//
  Sql::beginTransaction();
  
  // delete work =====
  PlanningElement::$_noDispatch=true;
  if ($workVal == 0){
    foreach ($listWork as $isWork){
      $isWork->deleteWork();
    }
    PlanningElement::updateSynthesis(get_class($act), $actId);
    PlanningElement::$_noDispatch=false;
  }else{
    //=====checkup for work to  add for know is taller than resource capacity =====//
    if($unitAbs != 'days'){
      $maxHour = Parameter::getGlobalParameter('dayTime');
      $sumWork = $workVal/$maxHour;
    }else{
      $sumWork = $workVal;
    }
    //============================================================================//
    if ($sumWork<=$etp){
      $countEdit=0;
      $countOtherAct=0;
      $nochange=true;
      //=================existing work=================//
      if(!empty($listWork)){
        foreach ($listWork as $isWork){
          if($isWork->idAssignment!=$assId ){
            $countOtherAct++;
            if(isset($lstOtherWork[$isWork->workDate]))$lstOtherWork[$isWork->workDate]+=$isWork->work;
            else $lstOtherWork[$isWork->workDate]=$isWork->work;
            continue;
          }else{
            if($isWork->work==$sumWork){
              $dayFull[$isWork->workDate]=true;
              continue;
            }else{
              $updateWorkForAct[$isWork->workDate]=$isWork;
            }
          }
        }
        //==========================================//
        //=================existing work for this absence and update this=================//
        if(!empty($updateWorkForAct)){
          foreach ($updateWorkForAct as $dateW=>$w){
            if(pq_array_key_exists($dateW,$lstOtherWork) and ($lstOtherWork[$dateW]+$sumWork)>$etp){//existing work for this date and this work+ absence work > capcity resource
              unset($lstOtherWork[$dateW]);
              continue;
            }
            $nochange=($nochange)?false:$nochange;
            $w->work =$sumWork;
            $res=$w->saveWork();
            $countEdit++;
          }
        }
      }
      //==========================================//
      //===================existing work on other element =======================//
      if($countOtherAct>0){
        foreach ($lstOtherWork as $date=>$workValue){
          if(pq_array_key_exists($date, $dayFull))continue; 
          if(pq_array_key_exists($date,$updateWorkForAct))continue; 
          if($workValue+$sumWork <=$etp ){
            $nochange=($nochange)?false:$nochange;
            $newWork= new Work();
            $newWork->refType = 'Activity';
            $newWork->refId = $actId;
            $newWork->setDates($date);
            $newWork->idResource = $userId;
            $newWork->work = $sumWork;
            $newWork->idProject = $idProject;
            $newWork->idAssignment = $assId;
            $res=$newWork->saveWork();
          }
          $dayFull[$date]=true;
        }
      }
      //==========================================//
      //===================for each date add work of absence not already exists for this date or work exist but is < to capacity resource   =======================//
      for($i=pq_strtotime($startDate);$i<=pq_strtotime($enDate);$i=pq_strtotime('+1 day', $i)){
        $date=date("Y-m-d",$i);
        if(isOffDay($date,$idCalendar))continue;
        if(pq_array_key_exists($date, $dayFull))continue;
        if(pq_array_key_exists($date,$updateWorkForAct))continue;
        $nochange=($nochange)?false:$nochange;
        $newWork= new Work();
        $newWork->refType = 'Activity';
        $newWork->refId = $actId;
        $newWork->setDates($date);
        $newWork->idResource = $userId;
        $newWork->work = $sumWork;
        $newWork->idProject = $idProject;
        $newWork->idAssignment = $assId;
        $res=$newWork->saveWork();
      }
      //==========================================//
      if($nochange){
        $result = 'warning';
        echo $result;
      }
  
      
      PlanningElement::updateSynthesis(get_class($act), $actId);
      PlanningElement::$_noDispatch=false;
    }else{
      $result = 'warningEtp';
      echo $result;
    }
  }
  Sql::commitTransaction();
  

  //===============================================================================================================//
}else{ // add absence
  
  $day = RequestHandler::getValue('day');
  $workDay = RequestHandler::getValue('workDay');
  $sumVal=0;
  
  $where=array("workDate"=>$workDay, 'idResource'=>$userId);
  $asWork=$plannedWorkM->getSqlElementsFromCriteria($where);
  if(!empty($asWork)){
    foreach ($asWork as $id=>$work){
      $sumVal+=$work->work;
    }
  }

  Sql::beginTransaction();
  $result = "";
  if($sumVal!=0 and $sumVal+$workVal>$res->capacity){
    $result = 'warningPlanned';
    echo $result;
  }else{
    if ($workVal == 0){
        $work = new Work();
        $where = "refType = 'Activity' and refId =".$actId." and idResource =".$userId." and idProject=".$idProject." and idAssignment =".$assId." and day='".$day."'";
        $listWork = $work->getSqlElementsFromCriteria(null,false,$where);
        
        //delete work
        foreach ($listWork as $isWork){
          $isWork->deleteWork();
        }
    }else {
      $work = new Work();
      //$where = " idProject in " . Project::getAdminitrativeProjectList()."  and " ;
      $where = "refType = 'Activity' and idResource =".$userId." and day='".$day."'";
      $listWork = $work->getSqlElementsFromCriteria(null,false,$where);
      
      if($unitAbs != 'days'){
      	$maxHour = Parameter::getGlobalParameter('dayTime');
      	$somWork = $workVal/$maxHour;
      }else{
        $somWork = $workVal;
      }
      foreach ($listWork as $isWork){
        if($isWork->refId == $actId and $somWork <= $etp){
          $editWork = true;
          $isWork->work =($unitAbs != 'days')?$somWork:$workVal;

          
          $isWork->saveWork();
          $somWork += $workVal;
        } else {
          $somWork += $isWork->work;
        }
      }
      if(!$editWork){
        if($somWork <= $etp){
          //put parameter in work object
          $work->refType = 'Activity';
          $work->refId = $actId;
          $work->setDates($workDay);
          $work->idResource = $userId;
          if($unitAbs != 'days'){
          	$workVal = $workVal/$maxHour;
          }
          $work->work = $workVal;
          $work->idProject = $idProject;
          $work->idAssignment = $assId;
          //save work
          $work->saveWork();
        }else {
          $result = 'warning';
          echo $result;
          //dojo.byId('warningDiv').style.display = 'block';
        }
      }
    }
  }
  // commit work
  Sql::commitTransaction();
}  
?>