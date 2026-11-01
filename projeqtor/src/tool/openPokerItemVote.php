<?PHP
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
 * Get the list of objects, in Json format, to display the grid list
 */
require_once "../tool/projeqtor.php"; 
$id=RequestHandler::getId('idPokerItem');
$idPokerSession = RequestHandler::getId('idPokerSession');
$mode = RequestHandler::getValue('mode');
$pokerItem = new PokerItem($id,true);
if($mode=='open'){
  $pokerItem->isOpen = 1;
  $pokerItem->save();
}else if($mode=='pause'){
  $pokerItem->isOpen = 0;
  $pokerItem->save();
}else if($mode=='close' and $pokerItem->flipped){
  $idComplexity = RequestHandler::getValue('idComplexity');
  $comp = new PokerComplexity($idComplexity);
  $pokerItem->value = $comp->value;
  $pokerItem->isOpen = 0;
  $pokerItem->save();
  $obj = new $pokerItem->refType($pokerItem->refId);
  if($pokerItem->refType == "Ticket"){
    $obj->WorkElement->plannedWork = $comp->itemWork;
  }else if($pokerItem->refType == "Activity"){
    $obj->ActivityPlanningElement->validatedWork = $comp->itemWork;
  }else if($pokerItem->refType == "Requirement"){
    $obj->plannedWork = $comp->itemWork;
  }else if($pokerItem->refType == "UserStory"){
    $obj->storyPoints = $comp->value;
  }
  $obj->save();
}else if($mode=='global'){
  $itemList = SqlList::getListWithCrit('PokerItem', array('idPokerSession'=>$idPokerSession), 'id');
  foreach ($itemList as $idItem){
    $pokerItem = new PokerItem($idItem,true);
    if(!$pokerItem->isOpen and $pokerItem->flipped and $pokerItem->value)continue;
    $pokerItem->isOpen = 1;
    $pokerItem->save();
  }
}
?>