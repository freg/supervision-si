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
 * Save some information about planning columns status.
 */
require_once "../tool/projeqtor.php";
Sql::beginTransaction();
$user=getSessionUser();
global $hideScope;
$hideScope=='column';
if (! pq_array_key_exists('action',$_REQUEST)) {
  throwError('action parameter not found in REQUEST');
}
$action=$_REQUEST['action'];
if ($action=='status') {
  if (! pq_array_key_exists('status',$_REQUEST)) {
	throwError('status parameter not found in REQUEST');
  }
  $status=$_REQUEST['status'];
  if (! pq_array_key_exists('item',$_REQUEST)) {
	throwError('item parameter not found in REQUEST');
  }
  $item=$_REQUEST['item'];
  $cs=new ColumnSelector($item);
  $objectClass=$cs->objectClass;
  if (! $cs->id) {
  	errorLog("ERROR in saveSelectedColumn, impossible to retrieve ColumnSelector($item)");
  } else {
  	$cs->hidden=($status=='hidden')?1:0;
    $cs->save();
    //Gautier #re-order column sortOrder
    $columnSelector = new ColumnSelector();
    $order = " sortOrder ASC ";
    $csListNotHidden = $columnSelector->getSqlElementsFromCriteria(array('idUser'=>$user->id,'objectClass'=>$cs->objectClass),null,null,$order);
    $tabHidden = array();
    $tabNotHidden = array();
    $tabById = array();
    $finalTab = array();
    foreach ($csListNotHidden as $obj){
      $tabById[$obj->id]=true;
      if($obj->hidden){
        $tabHidden[]= $obj->id;
      }else{
        $tabNotHidden[]= $obj->id;
      }
    }
    if (pq_array_key_exists('orderedList',$_REQUEST)) {
      $orderedList=pq_explode('|',$_REQUEST['orderedList']);
      foreach ($orderedList as $id) {
        if (pq_array_key_exists($id,$tabById)) {
          $finalTab[]=$id;
          unset($tabById[$id]);
        }
      }
      foreach (array_merge($tabNotHidden,$tabHidden) as $id) {
        if (pq_array_key_exists($id,$tabById)) {
          $finalTab[]=$id;
        }
      }
    } else {
      $finalTab = array_merge($tabNotHidden, $tabHidden);
    }
    foreach ($finalTab as $id=>$value){
       $cs = new ColumnSelector($value);
       if($cs->sortOrder != $id+1){
         $cs->sortOrder = $id+1;
         $cs->save(); 
       }
    }
  }
} else if ($action=='reset') {
  if (! pq_array_key_exists('objectClass',$_REQUEST)) {
	throwError('objectClass parameter not found in REQUEST');
  }
  $objectClass=$_REQUEST['objectClass'];
  Security::checkValidClass($objectClass);
  $clause="scope='list' and objectClass='$objectClass' and idUser=$user->id ";
  $cs=new ColumnSelector();
  $resPurge=$cs->purge($clause); 
} else if ($action=='width') {
  if (! pq_array_key_exists('width',$_REQUEST)) {
    throwError('width parameter not found in REQUEST');
  }
  $width=$_REQUEST['width'];
  if (! pq_array_key_exists('item',$_REQUEST)) {
    throwError('item parameter not found in REQUEST');
  }
  $item=$_REQUEST['item'];
  $cs=new ColumnSelector($item);
  $objectClass=$cs->objectClass;
  if (! $cs->id) {
    errorLog("ERROR in saveSelectedColumn, impossible to retrieve ColumnSelector($item)");
  } else {
    $cs->widthPct=$width;
    $cs->save();
  }
}
Sql::commitTransaction();
unsetSessionValue('list#'.$objectClass);
?>
