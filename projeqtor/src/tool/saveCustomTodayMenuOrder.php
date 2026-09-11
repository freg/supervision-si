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

/**
 * ============================================================================
 * Save Today displayed info list
 */
require_once "../tool/projeqtor.php";
$reset = RequestHandler::getValue('reset');
if(!$reset){
$customArray=RequestHandler::getValue('customArray');
$customArray=pq_explode(',', $customArray);
unset($customArray[0]);
$customArrayOrder=array_flip($customArray);
$customArray=implode("','", $customArray);
Sql::beginTransaction();
 $where="idUser=".getSessionUser()->id." and scope='newGui'";
 $today = new Today();
 $todayList = $today->getSqlElementsFromCriteria(null, false, $where, 'sortOrder');
 $i = 20;
  foreach ($todayList as $menu) {
    if(!isset($customArrayOrder[$menu->staticSection])){
      $i++;
      $menu->sortOrder=$i;
    }else{
    $menu->sortOrder=$customArrayOrder[$menu->staticSection];
    }
    $menu->save();
    unset($customArrayOrder[$menu->staticSection]);
  }
}else{
  Sql::beginTransaction();
  $arrayToday = array('Projects'=>1,'Message'=>2,'Documents'=>3,'Todo'=>4,'ResponsibleTodoList'=>5,'News'=>6);
  $where="idUser=".getSessionUser()->id." and  ( scope='newGui' OR scope='report') ";
  $today = new Today();
  $todayList = $today->getSqlElementsFromCriteria(null, false, $where, 'sortOrder');
  foreach ($todayList as $menu) {
    if($menu->idReport){
      $menu->delete();
      continue;
    }
    $menu->sortOrder=$arrayToday[$menu->staticSection];
    $menu->idle = 0;
    $menu->save();
  }
}

Sql::commitTransaction();
?>