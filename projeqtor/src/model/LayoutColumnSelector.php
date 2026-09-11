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

/* ============================================================================
 * RiskType defines the type of a risk.
 */  
require_once('_securityCheck.php'); 
class LayoutColumnSelector extends SqlElement {

  // Define the layout that will be used for lists
   public $id;
   public $idLayout;
   public $scope;
   public $objectClass;
   public $idUser;
   public $field;
   public $attribute;
   public $hidden;
   public $sortOrder;
   public $widthPct;
   public $name;
   public $subItem;
   public $formatter;
   public $isReportList;
   public $_from;
   public $_displayName;
   /** ==========================================================================
   * Constructor
   * @param $id Int the id of the object in the database (null if not stored yet)
   * @return void
   */ 
  function __construct($id = NULL, $withoutDependentObjects=false) {
    parent::__construct($id,$withoutDependentObjects);
  }

  
   /** ==========================================================================
   * Destructor
   * @return void
   */ 
  function __destruct() {
    parent::__destruct();
  }

// ============================================================================**********
// GET STATIC DATA FUNCTIONS
// ============================================================================**********
  public static function getColumnsList($classObj, $idLayout=null, $isReport=false) {
    // retrieve from database, in correct order
    $user=getSessionUser();
    $obj=new $classObj();
    $lcs=new LayoutColumnSelector();
    
    $extraHiddenFields=$obj->getExtraHiddenFields('*','*');
    if (isset($extraHiddenFields['id'])) unset($extraHiddenFields['id']);
    if (isset($extraHiddenFields['name'])) unset($extraHiddenFields['name']);
    if (method_exists($obj, 'setAttributes')) $obj->setAttributes();
    
    $isReportList = ($isReport)?'1':'0';
    $crit=array('scope'=>'list', 'objectClass'=>$classObj, 'idUser'=>$user->id, 'isReportList'=>$isReportList);
    if($idLayout){
      $reportLayout = new ReportLayout($idLayout, true);
      if(!$reportLayout->isShared){
        $crit=array('scope'=>'list', 'objectClass'=>$classObj, 'idUser'=>$user->id, 'idLayout'=>$idLayout,'isReportList'=>$isReportList);
      }else{
        $crit=array('scope'=>'list', 'objectClass'=>$classObj, 'idLayout'=>$idLayout,'isReportList'=>$isReportList);
      }
    }
    $lcsList=$lcs->getSqlElementsFromCriteria($crit, false, null, 'sortOrder asc');
  
    $result=array();
    foreach ($lcsList as $lcs) {
      if (! SqlElement::isVisibleField($lcs->attribute)) {
        continue;
      }
      if ($obj->isAttributeSetToField($lcs->attribute, 'notInList')) {
        continue;
      }
      if (( $obj->isAttributeSetToField($lcs->attribute, 'hidden') or in_array($lcs->attribute,$extraHiddenFields) ) and $lcs->attribute!='id' and $lcs->attribute!='name') {
        continue;
      }
      $lcs->_name=$lcs->attribute;
      $dispObj=$obj;
      $hidden=$extraHiddenFields;
      if ($lcs->subItem) {
        $fromObj='obj'.$lcs->subItem;
        if (! isset($$fromObj)) {
        		$$fromObj=new $lcs->subItem();
        }
        $dispObj=$$fromObj;
        $hiddenObj='hidden'.$lcs->subItem;
        if (! isset($$hiddenObj)) {
          $$hiddenObj=$dispObj->getExtraHiddenFields();
        }
        $hidden=$$hiddenObj;
      }
      if (in_array($lcs->attribute,$hidden) and $lcs->attribute!='id' and $lcs->attribute!='name') {
        continue;
      }
      $lcs->_displayName=$dispObj->getColCaption($lcs->_name);
      if (pq_substr($lcs->attribute,0,9)=='idContext' and pq_strlen($lcs->attribute)==10) {
        $ctx=new ContextType(pq_substr($lcs->attribute,-1));
        $lcs->_displayName=$ctx->name;
      }
      $lcs->_from=$lcs->subItem;
      $result[$lcs->attribute]=$lcs;
    }
    return $result;
  }

}  
?>