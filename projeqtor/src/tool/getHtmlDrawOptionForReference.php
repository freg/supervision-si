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
 * Save some information to session (remotely).
 */
require_once "../tool/projeqtor.php";
$col=RequestHandler::getValue('col');
$selection= (is_numeric(RequestHandler::getValue('selection')))?RequestHandler::getValue('selection'):null;
$refType = RequestHandler::getClass('refType');
if ($refType=='Replan' or $refType=='Construction' or $refType=='Fixed') {
  $refType='Project';
}
$refId = RequestHandler::getId('refId');
$critField = RequestHandler::getValue('critField');
$critVal = RequestHandler::getValue('critVal');

$obj = new $refType($refId);
$required = false;
if(pq_strpos($col, 'id') !== false and !property_exists($refType, $col)){
  if(SqlElement::class_exists($refType.'PlanningElement') and property_exists($refType.'PlanningElement', 'id'.$refType.pq_substr($col, 2))){
    $col = 'id'.$refType.pq_substr($col, 2);
    $pe = $refType.'PlanningElement';
    $selection = (is_numeric($selection))?$selection:$obj->$pe->$col;
    $required =(pq_strpos($obj->$pe->getFieldAttributes($col), 'required')!==false)?true:false;
  }else if(property_exists($refType, 'id'.$refType.$col)){
    $col = 'id'.$refType.$col;
    $selection = (is_numeric($selection))?$selection:$obj->$col;
    $required =(pq_strpos($obj->getFieldAttributes($col), 'required')!==false)?true:false;
  } 
}else if(pq_strpos($col, 'id') === false and property_exists($refType, 'id'.$refType.$col)){
    $col = 'id'.$refType.$col;
    $selection = (is_numeric($selection))?$selection:$obj->$col;
    $required =(pq_strpos($obj->getFieldAttributes($col), 'required')!==false)?true:false;
}else if(pq_strpos($col, 'id') !== false and property_exists($refType, $col)){
  $selection = (is_numeric($selection))?$selection:$obj->$col;
  $required =(pq_strpos($obj->getFieldAttributes($col), 'required')!==false)?true:false;
}else if(pq_strpos($col, 'id') === false and property_exists($refType, 'id'.$col)){
  $col = 'id'.$col;
  $selection = (is_numeric($selection))?$selection:$obj->$col;
  $required =(pq_strpos($obj->getFieldAttributes($col), 'required')!==false)?true:false;
}else if(pq_strpos($col, 'id') === false and property_exists($obj, 'WorkElement')){
    if(property_exists($obj->WorkElement, 'id'.$refType.$col)){
      $col = 'id'.$refType.$col;
      $selection = (is_numeric($selection))?$selection:$obj->WorkElement->$col;
      $required =(pq_strpos($obj->WorkElement->getFieldAttributes($col), 'required')!==false)?true:false;
    }
}else if(pq_strpos($col, 'id') === false and property_exists($obj, 'PlanningElement')){
    $pe = $refType.'PlanningElement';
    if(property_exists($obj->$pe, 'id'.$refType.$col)){
      $col = 'id'.$refType.$col;
      $selection = (is_numeric($selection))?$selection:$obj->$pe->$col;
      $required =(pq_strpos($obj->$pe->getFieldAttributes($col), 'required')!==false)?true:false;
    }
}
htmlDrawOptionForReference($col, $selection, $obj, $required, $critField, $critVal);
?>