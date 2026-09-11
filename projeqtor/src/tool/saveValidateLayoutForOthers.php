<?php
/*** COPYRIGHT NOTICE *********************************************************
 *
 * Copyright 2009-2017 ProjeQtOr - Pascal BERNARD - support@projeqtor.org
 * Contributors : 
 *  => g.miraillet : Fix #1502
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
 * Save some information about subscription so item.
 */
require_once "../tool/projeqtor.php";
$user=getSessionUser();
$tab = RequestHandler::getValue('test');
$classTab = RequestHandler::getValue('layoutObjectClass');
//if(pq_strpos($classTab, 'Planning') !== false)$classTab='Planning'; // PBER #10872
$tabIdUser = explode('-',$tab);
$layoutId = $user->_arrayLayouts[$classTab]['id'];
$layoutRef = new Layout($layoutId);
$class=$layoutRef->objectClass;
$scope = $layoutRef->scope;
$newUser = RequestHandler::getValue('layoutForNewUser');
$newCo = RequestHandler::getValue('layoutForNewConnexion');

Sql::beginTransaction();

if(pq_trim($newUser)=='on'){
//ONLY ONE DEFAULT BY CLASS
  $OldLayoutDefault = SqlElement::getSingleSqlElementFromCriteria('Layout',array('ObjectClass'=>$class,'isDefault'=>1,'idUser'=>'0'));
  if($OldLayoutDefault->id){
    $OldLayoutDefault->delete();
  }
  $layoutDefault = new Layout();
  $layoutDefault->idUser ='0';
  $layoutDefault->objectClass = $class;
  $layoutDefault->scope = $scope;
  $layoutDefault->isShared = 0;
  $layoutDefault->isDefault= 1;
  $layoutDefault->save();
}else{
  $OldLayoutDefault = SqlElement::getSingleSqlElementFromCriteria('Layout',array('ObjectClass'=>$class,'isDefault'=>1,'idUser'=>'0','scope'=>$scope));
  if($OldLayoutDefault->id){
    $OldLayoutDefault->delete();
  }
}
//NO FORCE
if(pq_trim($newCo)!='on'){
  foreach ($tabIdUser as $idUser){
    if(!$idUser)continue;
    //PURGE COLUMN SELECTOR USER
    $columnSelector=new ColumnSelector();
    $crit=array("objectClass"=>$class , "idUser"=>$idUser);
    $columnSelectorList = $columnSelector->getSqlElementsFromCriteria($crit);
    foreach ($columnSelectorList as $column){
      $column->delete();
    }
    //APPLY COLUMN SELECTOR
    $crit=array("idLayout"=>$layoutRef->id,"objectClass"=>$class, "idUser"=>$user->id, 'isReportList'=>'0');
    $layoutColumnSelector=new LayoutColumnSelector();
    $layoutColumnSelectorList = $layoutColumnSelector->getSqlElementsFromCriteria($crit);
    foreach ($layoutColumnSelectorList as $cls){
      $crit=array("objectClass"=>$class , "idUser"=>$idUser, "field"=>$cls->field);
      $cs=ColumnSelector::getSingleSqlElementFromCriteria('ColumnSelector', $crit);
      $colArray[]="$cls->field,$cls->hidden,$cls->sortOrder";
      $cs->scope = $cls->scope;
      $cs->objectClass = $cls->objectClass;
      $cs->idUser = $idUser;
      $cs->field = $cls->field;
      $cs->attribute = $cls->attribute;
      $cs->sortOrder = $cls->sortOrder;
      $cs->widthPct = $cls->widthPct;
      $cs->name = $cls->name;
      $cs->subItem = $cls->subItem;
      $cs->formatter = $cls->formatter;
      $cs->hidden=$cls->hidden;
      $cs->save();
    }
  }
//FORCE LAYOUT
}else{
  foreach ($tabIdUser as $idUser){
    if(!$idUser)continue;
    //CREATE LAYOUT FORCE
    $layoutForce = SqlElement::getSingleSqlElementFromCriteria('LayoutForced', array('idUser'=>$idUser,'objectClass'=>$class));
    if($layoutForce->id and $layoutForce->idLayout == $layoutId){
      continue;
    }
    $layoutForce->idUser = $idUser;
    $layoutForce->idLayout = $layoutId;
    $layoutForce->objectClass = $class;
    $layoutForce->idCreator = $user->id;
    $layoutForce->save();
    //CREATE LAYOUT
//     $layout = new Layout();
//     $layout->idUser=$idUser;
//     $layout->objectClass=$class;
//     $layout->scope = $scope;
//     $layout->isShared = 0;
//     $layout->save();
    //PURGE COLUMN SELECTOR USER
    $columnSelector=new ColumnSelector();
    $crit=array("objectClass"=>$class , "idUser"=>$idUser);
    $columnSelectorList = $columnSelector->getSqlElementsFromCriteria($crit);
    foreach ($columnSelectorList as $column){
      $column->delete();
    }
    //APPLY COLUMN SELECTOR
    $crit=array("idLayout"=>$layoutRef->id,"objectClass"=>$class, "idUser"=>$user->id, 'isReportList'=>'0');
    $layoutColumnSelector=new LayoutColumnSelector();
    $layoutColumnSelectorList = $layoutColumnSelector->getSqlElementsFromCriteria($crit);
    foreach ($layoutColumnSelectorList as $cls){
      $crit=array("objectClass"=>$class , "idUser"=>$idUser, "field"=>$cls->field);
      $cs=ColumnSelector::getSingleSqlElementFromCriteria('ColumnSelector', $crit);
      $colArray[]="$cls->field,$cls->hidden,$cls->sortOrder";
      $cs->scope = $cls->scope;
      $cs->objectClass = $cls->objectClass;
      $cs->idUser = $idUser;
      $cs->field = $cls->field;
      $cs->attribute = $cls->attribute;
      $cs->sortOrder = $cls->sortOrder;
      $cs->widthPct = $cls->widthPct;
      $cs->name = $cls->name;
      $cs->subItem = $cls->subItem;
      $cs->formatter = $cls->formatter;
      $cs->hidden=$cls->hidden;
      $cs->save();
    }
    //APPLY LAYOUT
    $userOther = new User($idUser);
    $layoutName='stockLayout' . $layoutRef->objectClass;
    $layoutArray=array("id"=>$layoutRef->id,"comment"=>$layoutRef->comment,"name"=>$layoutRef->scope);
    $userOther->_arrayLayouts[$layoutRef->objectClass]=$layoutArray;
    $userOther->_arrayLayouts[$layoutRef->objectClass . "LayoutName"]=$layoutRef->scope;
  }
  //DELETE LAYOUT AND FORCE LAYOUT
  $forcedLayout = new LayoutForced();
  $lstForceLayout = $forcedLayout->getSqlElementsFromCriteria(array('objectClass'=>$class,'idLayout'=>$layoutId));
  foreach ($lstForceLayout as $fl){
    if(!in_array($fl->idUser,$tabIdUser)){
//       $layoutDelete =  SqlElement::getSingleSqlElementFromCriteria('Layout',array('objectClass'=>$class,'idUser'=>$fl->idUser,'scope'=>$layoutRef->scope));
//       $layoutDelete->delete();
      $fl->delete();
    }
  }
}
Sql::commitTransaction();

//OLD CODE//////

//GET EXIST
// $lstLayout = $layoutRef->getSqlElementsFromCriteria(array('objectClass'=>$class,'scope'=>$scope));
// foreach ($lstLayout as $lay){
//   $tabExist[$lay->idUser]=$lay->idUser;
// }
// //New
// foreach ($tabIdUser as $idUser){
//   if(!$idUser)continue;
//   //EXIST
//   if(in_array($idUser,$tabExist)){
//     //FORCE LAYOUT
//     if(pq_trim($newCo)=='on'){
//         $layoutForce = SqlElement::getSingleSqlElementFromCriteria('LayoutForced', array('idUser'=>$idUser,'objectClass'=>$class));
//         $layoutForce->idUser = $idUser;
//         $layoutForce->idLayout = $layoutId;
//         $layoutForce->objectClass = $class;
//         $layoutForce->idCreator = $user->id;
//         $layoutForce->save();
//     }
//   //NEW
//   }else{
    
//     $layout = new Layout();
//     $layout->idUser=$idUser;
//     $layout->objectClass=$class;
//     $layout->scope = $scope;
//     $layout->isShared = 0;
//     $layout->save();
    
    
//   //APPLY LAYOUT
//   $userOther = new User($idUser);
//   $layoutName='stockLayout' . $layoutRef->objectClass;
//   $layoutArray=array("id"=>$layoutRef->id,"comment"=>$layoutRef->comment,"name"=>$layoutRef->scope);
//   $userOther->_arrayLayouts[$lay->objectClass]=$layoutArray;
//   $userOther->_arrayLayouts[$lay->objectClass . "LayoutName"]=$layoutRef->scope;
    
//   $crit=array("objectClass"=>$class, "idUser"=>$user->id);
//   $columnSelector=new ColumnSelector();
//   $columnSelectorList = $columnSelector->getSqlElementsFromCriteria($crit);
//   $arrayColumn = array();
//   foreach ($columnSelectorList as $column){
//     $layoutColumnSelector= new LayoutColumnSelector();
//     $arrayColumn[$column->field]=$column->hidden;
//     $layoutColumnSelector->idLayout = $layoutId;
//     $layoutColumnSelector->scope = $column->scope;
//     $layoutColumnSelector->objectClass = $column->objectClass;
//     $layoutColumnSelector->idUser = $idUser;
//     $layoutColumnSelector->field = $column->field;
//     $layoutColumnSelector->attribute = $column->attribute;
//     $layoutColumnSelector->hidden = $column->hidden;
//     $layoutColumnSelector->sortOrder = $column->sortOrder;
//     $layoutColumnSelector->widthPct = $column->widthPct;
//     $layoutColumnSelector->name = $column->name;
//     $layoutColumnSelector->subItem = $column->subItem;
//     $layoutColumnSelector->formatter = $column->formatter;
//     $layoutColumnSelector->save();
//   }
//   $columnSelector=new ColumnSelector();
//   $crit=array("objectClass"=>$class , "idUser"=>$user->id);
//   $columnSelectorList = $columnSelector->getSqlElementsFromCriteria($crit);
//   foreach ($columnSelectorList as $column){
//     $column->delete();
//   }
//   $crit=array("idLayout"=>$layoutRef->id ,"objectClass"=>$class, "idUser"=>$user->id, 'isReportList'=>'0');
//   $layoutColumnSelector=new LayoutColumnSelector();
//   $layoutColumnSelectorList = $layoutColumnSelector->getSqlElementsFromCriteria($crit);
//   foreach ($layoutColumnSelectorList as $cls){  
//     $crit=array("objectClass"=>$class , "idUser"=>$userOther->id, "field"=>$cls->field);
//     $cs=ColumnSelector::getSingleSqlElementFromCriteria('ColumnSelector', $crit);
//     $colArray[]="$cls->field,$cls->hidden,$cls->sortOrder";
//     $cs->scope = $cls->scope;
//     $cs->objectClass = $cls->objectClass;
//     $cs->idUser = $cls->idUser;
//     $cs->field = $cls->field;
//     $cs->attribute = $cls->attribute;
//     $cs->sortOrder = $cls->sortOrder;
//     $cs->widthPct = $cls->widthPct;
//     $cs->name = $cls->name;
//     $cs->subItem = $cls->subItem;
//     $cs->formatter = $cls->formatter;
//     $cs->hidden=$cls->hidden;
//     $cs->save();
//   }
//     //FORCE LAYOUT
//     if(trim($newCo)=='on'){
//       $layoutForce = SqlElement::getSingleSqlElementFromCriteria('LayoutForced', array('idUser'=>$idUser,'objectClass'=>$class));
//       $layoutForce->idUser = $idUser;
//       $layoutForce->idLayout = $layoutId;
//       $layoutForce->objectClass = $class;
//       $layoutForce->idCreator = $user->id;
//       $layoutForce->save();
//     }
//   }
// }

// //DELETE
// foreach ($lstLayout as $lay){
//   if(!in_array($lay->idUser, $tabIdUser) and $lay->idUser != $user->id and $lay->idUser != 0){
//     $lay->delete();
//     //DELETE LAYOUT COLUMN SELECTOR
//   }
// }
?>