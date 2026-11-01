<?php
/*** COPYRIGHT NOTICE *********************************************************
 *
 * Copyright 2009-2017 ProjeQtOr - Pascal BERNARD - support@projeqtor.org
 * Contributors : Eliott LEGRAND (from Salto Consulting - 2018) 
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

// ELIOTT - LEAVE SYSTEM

/** ============================================================================
 * return the fields necessary to update the summary tab in view/leaveCalendar.php
 */
require_once "../tool/projeqtor.php";
if(!isset($_REQUEST['idEmployee'])){
    $result= htmlSetResultMessage(null, 
                                  i18n("errorWrongRequest")." ".i18n("missing")." : idEmployee", 
                                  false,
                                  "", 
                                  "GET EMPLOYEE LEAVE EARNED SUMMARY",
                                  "INVALID");

    echo json_encode($result);
    exit;
}

$res=[];

$idEmployee = $_REQUEST['idEmployee'];
$lvsEarned = EmployeeLeaveEarned::getList(null, $idEmployee);
$showClosedPeriods=(isset($paramShowClosedLeavePeriods) and $paramShowClosedLeavePeriods==true)?true:false;
$critArrayEmpContract=array("idEmployee"=>(string)$idEmployee, "idle"=>'0');
$userEmpContract = SqlElement::getFirstSqlElementFromCriteria("EmploymentContract", $critArrayEmpContract);
if ($userEmpContract->id<=0) {
    $res = [];
    echo json_encode($res);    
} else {
    $alreadySummed=0;
    foreach($lvsEarned as $lvEarned){
        $resLine = [];
        $lvType = new LeaveType($lvEarned->idLeaveType);
        $resLine["lvTColor"] = $lvType->color;
        $resLine["lvTOppositeColor"] = oppositeColor($lvType->color);
        $resLine["lvTName"] = $lvType->name;
        if ($lvEarned->startDate==null) {
            $theStartDate = " ";
        } else {
            $theStartDate = (new DateTime($lvEarned->startDate))->format("Y/m/d");
        }
        if ($lvEarned->endDate!=null and $userEmpContract->endDate!=null and $userEmpContract->endDate<$lvEarned->endDate) {
            $theEndDate = (new DateTime($userEmpContract->endDate))->format("Y/m/d");                
        } else {
            if ($lvEarned->endDate==null) {
                $theEndDate=" ";
            } else {
                $theEndDate = (new DateTime($lvEarned->endDate))->format("Y/m/d");
            }
        }
        $critArrayLvTypeOf = array("idLeaveType"=>(string)$lvType->id,"idEmploymentContractType"=>(string)$userEmpContract->idEmploymentContractType);
        $lvTypeOfEmpContractType = SqlElement::getFirstSqlElementFromCriteria("LeaveTypeOfEmploymentContractType", $critArrayLvTypeOf);

        if($lvTypeOfEmpContractType->periodDuration){
            $resLine["periodDuration"] = $lvTypeOfEmpContractType->periodDuration.' '.i18n( ($lvTypeOfEmpContractType->periodDuration<=1 ? 'colMonth':'colMonths') );
        }else{
            $resLine["periodDuration"] = " - ";
        }
        $resLine["startDateEndDate"] = htmlFormatDate($theStartDate).'<br/>'.htmlFormatDate($theEndDate);
        if($lvEarned->quantity){
            $leave=new Leave();
            $resLine["quantity"] = htmlDisplayNumericWithoutTrailingZeros($lvEarned->quantity);
            $where="idEmployee=$idEmployee and idLeaveType=$lvEarned->idLeaveType and accepted=1 and startDate <='".date("Y-m-d")."'";
            $sumLeave= $leave->sumSqlElementsFromCriteria('nbDays',null,$where);
            $recorded=$lvEarned->quantity - $lvEarned->leftQuantity- $lvEarned->leftQuantityBeforeClose;
            if($recorded==0 or $sumLeave=='')$sumLeave=0;
            $resLine["recorded"] = htmlDisplayNumericWithoutTrailingZeros($recorded);
            $tmpTaken=$sumLeave-$alreadySummed;
            if ($tmpTaken>$lvEarned->quantity) {
              $tmpTaken=$lvEarned->quantity;
            }
            if ($tmpTaken>$recorded) {
              $tmpTaken=$recorded;
            }
            $alreadySummed+=$tmpTaken;
            $resLine["taken"] = htmlDisplayNumericWithoutTrailingZeros($tmpTaken);
            $resLine["left"] = htmlDisplayNumericWithoutTrailingZeros($lvEarned->leftQuantity);
        }else{
            $recorded=0;
            $taken=0;
            if($lvEarned->poseWithoutRights==1){
              $leave=new Leave();
              $where="idEmployee=$idEmployee and idLeaveType=$lvEarned->idLeaveType and accepted=1 and startDate <='".date("Y-m-d")."'";
              $whereRecorded="idEmployee=$idEmployee and idLeaveType=$lvEarned->idLeaveType and rejected<>1";
              $recorded=$leave->sumSqlElementsFromCriteria('nbDays',null,$whereRecorded);
              $taken=$leave->sumSqlElementsFromCriteria('nbDays',null,$where);
            }
            $resLine["quantity"] = " - ";
            $resLine["recorded"] =($recorded==0)?" - ":htmlDisplayNumericWithoutTrailingZeros($recorded);
            $resLine["taken"] =($taken==0)?" - ":htmlDisplayNumericWithoutTrailingZeros($taken);
            $resLine["left"] = " - ";
        }

        $right = $lvEarned->getLeavesRight(true,false);
        if ($right['quantity']) {
            if ($lvEarned->leftQuantity<0) {
                $theQuantity = max(0,$right["quantity"]+$lvEarned->leftQuantity);
            } else {
                $theQuantity = $right["quantity"];
            }
            $resLine["earnedPeriodPlusOne"] = htmlDisplayNumericWithoutTrailingZeros($theQuantity);
        } else {
            $resLine["earnedPeriodPlusOne"] = 0;
        }
        $resLine['idle']=$lvEarned->idle;
        if ($showClosedPeriods or $lvEarned->idle==0) $res[]=$resLine;
    }
    echo json_encode($res);
}