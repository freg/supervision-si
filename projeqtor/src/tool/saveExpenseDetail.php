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

$expenseDetailId=RequestHandler::getId('expenseDetailId');
$idExpense=RequestHandler::getId('idExpense', true);
$expenseDetailName=RequestHandler::getValue('expenseDetailName');
$expenseDetailReference=RequestHandler::getValue('expenseDetailReference');
$expenseDetailDate=RequestHandler::getDatetime('expenseDetailDate');
$expenseDetailType=RequestHandler::getValue('expenseDetailType');
$expenseDetailAmount=RequestHandler::getNumeric('expenseDetailAmount');
$expenseDetailAmountLocal=RequestHandler::getNumeric('expenseDetailAmountLocal');

$expenseDetailValue01=null;
$expenseDetailValue02=null;
$expenseDetailValue03=null;
$expenseDetailUnit01=null;
$expenseDetailUnit02=null;
$expenseDetailUnit03=null;
$expenseDetailValue01=RequestHandler::getValue('expenseDetailValue01');
$expenseDetailValue02=RequestHandler::getValue('expenseDetailValue02');
$expenseDetailValue03=RequestHandler::getValue('expenseDetailValue03');
$expenseDetailUnit01=RequestHandler::getValue('expenseDetailUnit01');
$expenseDetailUnit02=RequestHandler::getValue('expenseDetailUnit02');
$expenseDetailUnit03=RequestHandler::getValue('expenseDetailUnit03');

Sql::beginTransaction();
// get the modifications (from request)
$expenseDetail=new ExpenseDetail($expenseDetailId);

$expenseDetail->idExpense=$idExpense; 
$expenseDetail->idExpenseDetailType=$expenseDetailType; 
$expenseDetail->name=$expenseDetailName;
$expenseDetail->externalReference=$expenseDetailReference;
//$expenseDetail->description;
$expenseDetail->expenseDate=$expenseDetailDate; 
$expenseDetail->amount=$expenseDetailAmount;
$expenseDetail->amountLocal=$expenseDetailAmountLocal;
$expenseDetail->value01=$expenseDetailValue01;
$expenseDetail->value02=$expenseDetailValue02;
$expenseDetail->value03=$expenseDetailValue03;
$expenseDetail->unit01=$expenseDetailUnit01;
$expenseDetail->unit02=$expenseDetailUnit02;
$expenseDetail->unit03=$expenseDetailUnit03;

$expense=new Expense($idExpense);
$expenseDetail->idProject=$expense->idProject; 
if ($expense->idActivity !== null) $expenseDetail->idActivity=$expense->idActivity; 
$expenseDetail->idle=$expense->idle;

$result=$expenseDetail->save();

// Message of correct saving
displayLastOperationStatus($result);
?>