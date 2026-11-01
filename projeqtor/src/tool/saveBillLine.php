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

// Get the bill line info
$lineId=null;
$lineId=RequestHandler::getId('billLineId'); // validated to be numeric value in SqlElement base constructor.
$refType=RequestHandler::getClass('billLineRefType',true);
$refId=RequestHandler::getId('billLineRefId',true);
$lineNum=RequestHandler::getNumeric('billLineLine',true);
$quantity=RequestHandler::getNumeric('billLineQuantity');
$numberDays=RequestHandler::getNumeric('billLineNumberDays');
$idTerm=RequestHandler::getId('billLineIdTerm');
$idResource=RequestHandler::getId('billLineIdResource');
$idActivityPrice=RequestHandler::getId('billLineIdActivityPrice');
$startDate=RequestHandler::getDatetime('billLineStartDate');
$endDate=RequestHandler::getDatetime('billLineEndDate');
$description=RequestHandler::getValue('billLineDescription');
$detail=RequestHandler::getValue('billLineDetail');
$price=RequestHandler::getNumeric('billLinePrice');
$priceLocal=RequestHandler::getNumeric('billLinePriceLocal');
$unit=RequestHandler::getValue('billLineUnit');
$extra=RequestHandler::isCodeSet('billLineExtra')?1:0;
$billingType=RequestHandler::isCodeSet('billLineBillingType')?RequestHandler::getAlphanumeric('billLineBillingType'):'M';

$lineId=pq_trim($lineId);
if ($lineId=='') $lineId=null;

//gautier
$catalogSpecification = "";
$boolCatalog = false;
if (RequestHandler::isCodeSet('billLineIdCatalog') and RequestHandler::getId('billLineIdCatalog')) {
  $boolCatalog = true;
  $catalog=new Catalog(RequestHandler::getId('billLineIdCatalog'));
  $catalogSpecification = ($catalog->specification)?$catalog->specification:"";
}//end 

Sql::beginTransaction();
$line=new BillLine($lineId);
$line->refType=$refType;
$line->refId=$refId;
$line->line=$lineNum;
$line->quantity=$quantity;
$line->numberDays=$numberDays;
$line->idTerm=$idTerm;
$line->idResource=$idResource;
$line->idActivityPrice=$idActivityPrice;
$line->startDate=$startDate;
$line->endDate=$endDate;
$line->description=$description;
$line->detail=$detail;
$line->price=$price;
$line->priceLocal=$priceLocal;
$line->idMeasureUnit=$unit;
$line->extra=$extra;
$line->billingType=$billingType;
//gautier #2516
if($boolCatalog){
  $line->idCatalog=$catalog->id;
  if(!$lineId and $line->refType=="Bill" and $catalogSpecification){
    $bill=new Bill($line->refId);
    if(!$bill->description or pq_strpos($bill->description,$catalogSpecification )=== FALSE){ 
      $bill->description .= $catalogSpecification;
    }
    $bill->save();
  }
  if(!$lineId and $line->refType=="Quotation" and $catalogSpecification){
    $quot=new Quotation($line->refId);
    if(!$quot->comment or pq_strpos($quot->comment,$catalogSpecification )=== FALSE){ 
      $quot->comment .= $catalogSpecification;
    }
    $quot->save();
  }
  if(!$lineId and $line->refType=="ProspectEstimate" and $catalogSpecification){
    $estimate=new ProspectEstimate($line->refId);
    if(!$estimate->comment or pq_strpos($estimate->comment,$catalogSpecification )=== FALSE){ 
      $estimate->comment .= $catalogSpecification;
    }
    $estimate->save();
  }
  if(!$lineId and $line->refType=="Command" and $catalogSpecification){
    $order=new Command($line->refId);
    if(!$order->comment or pq_strpos($order->comment,$catalogSpecification )=== FALSE){ 
      $order->comment .= $catalogSpecification;
    }
    $order->save();
  }
}//end
$result=$line->save();

// Message of correct saving
displayLastOperationStatus($result);
?>