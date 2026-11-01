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

require_once "../tool/projeqtor.php";
$data = false;
$class = RequestHandler::getClass('class');
$jsonValue = RequestHandler::getValue('jsonValue');
$userId = getCurrentUserId();
$columnSelector = new ColumnSelector();
$mode = RequestHandler::getValue('mode');
$totalDiv = RequestHandler::getValue('totalDiv');
$list = pq_explode("__", $jsonValue);
$delete = array_pop($list);
$order = " sortOrder ASC ";
if($mode=='size'){
  $currentList = $columnSelector->getSqlElementsFromCriteria(array('idUser'=>$userId,'objectClass'=>$class),null,null,$order);
}else{
  $currentList = $columnSelector->getSqlElementsFromCriteria(array('idUser'=>$userId,'objectClass'=>$class),null,null,$order,null,null,count($list));
}
if($mode=='size'){
  foreach ($list as $id=>$val){
    $list[$id]= intval(pq_substr($val, 0 , -2));
    $list[$id] = ceil(round($list[$id]/intval($totalDiv) * 100,1));
  }
  $total = 0;
  foreach ($list as $idList=>$percent){
    if($total>=100){
      $list[$idList]='hidden';
    }
    if($total+$percent > 100 and $total < 100){
      $percent = 100-$total;
      $list[$idList] = $percent;
    }
    $total += $percent;
  }
  if($total < 100){
    $list[sizeof($list)-1] += (100 - $total) ;
    $data = sizeof($list)-1;
    $data .= "#!#!#!#!#!#";
    $data .= round(($list[sizeof($list)-1]*$totalDiv/100))."px";
  }
}
Sql::beginTransaction();
foreach ($currentList as $id=>$obj){
  if($mode=='move'){
    if(isset($list[$id]) and in_array($obj->field, $list) ){
      if($list[$id] != $obj->field){
        $key = array_search($obj->field, $list);
        $obj->sortOrder = $key+1;
        $obj->save();
      }
    }
  }else{
    if(!$obj->hidden){
      if(isset($list[$id])){
        if($list[$id] != $obj->widthPct){
          if($list[$id]=='hidden'){
            $obj->hidden= 1;
          }else{
            $obj->widthPct = $list[$id];
          }
        }
        $obj->saveForced();
      }
    }else{
      if(isset($list[$id])){
        $obj->hidden= 0;
        if ($list[$id]!='hidden') $obj->widthPct = $list[$id];
        $obj->saveForced();
      }
    }
  }
  
}
Sql::commitTransaction();
if($data){
  echo $data;
}
 ?>