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
 * History reflects all changes to any object.
 */ 
require_once('_securityCheck.php');
class History extends SqlElement {

  // extends SqlElement, so has $id
  public $id;    // redefine $id to specify its visible place 
  public $refType;
  public $refId;
  public $operation;
  public $colName; 
  public $oldValue;
  public $newValue;
  public $operationDate;
  public $idUser;
  public $isWorkHistory;
  public $idProject;
  
  public static $_storeDate;
  public static $_storeItem;
  public $_noHistory=true; // Will never save history for this object
  public static $_avoidLoop=false;
  
  //public static $_noHistoryColumns=array("validatedCalculated","needReplan","marginWork","marginWorkPct","plannedStartDate","plannedEndDate","plannedDuration","expectedProgress");
  public static $_noHistoryColumns=array("validatedCalculated","needReplan","marginWork","marginWorkPct","expectedProgress"
                                        ,"quickplanStartDate","quickplanEndDate","quickplanUpdated","assignedDuration"); // PBER #9699 and #9697 
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

  /** ===========================================================================
   * Store a new History trace (will call ->save)
   * @param String $refType type of object updated
   * @param Int $refId id of object updated
   * @param String $operation 
   * @param String $colName name of column updated
   * @param String $oldValue old value of column (before update)
   * @param String $newValue new value of column (after update)
   * @return boolean true if save is OK, false either
   */
  public static function store ($obj, $refType, $refId, $operation, $colName=null, $oldValue=null, $newValue=null) {
    if ($operation!='insert' and SqlElement::isCopyInProgress()) return true; // On copy, only save history for inserts, not for all following updates during same operation
    if (!$refType or !$refId) {
      if ($obj and $obj->id) {
        $refType=get_class($obj);
        $refId=$obj->id;
      } else {
        return true;
      }
    }
    if (property_exists($refType, '_noHistory')) return true;
    if ($operation=="update" and in_array($colName,self::$_noHistoryColumns)) return true;
    $user=getSessionUser();
    $hist=new History();
    $histArch= new HistoryArchive();
    $canArchiveIdle=Parameter::getGlobalParameter('cronArchiveCloseItems');
    // Attention : History fields are not to be escaped by Sql::str because $olValue and $newValue have already been escaped
    // So other fiels (names) must be manually "quoted"
    if ($refType=='PlanningElement' and $obj and isset($obj->refType)) {
    	$refType=$obj->refType.'PlanningElement';
    }
    if(property_exists($obj, 'idProject') or get_class($obj)=='Project'){
      $hist->idProject=(get_class($obj)=='Project')?$obj->id:$obj->idProject ;
    }
    //florent
    if(($colName=='idle' or $colName=='cancelled') and $newValue=='1' and $canArchiveIdle=='YES'){
      $tableHist=$hist->getDatabaseTableName();
      $tableHistArch=$histArch->getDatabaseTableName();
      $hist->refType=$refType;
      if ($refType=='TicketSimple') {
        $hist->refType='Ticket';
      }
      $hist->refId=$refId;
      $hist->operation=$operation;
      $hist->colName=$colName;
      if ($colName and pq_strtolower(pq_substr($obj->getDataType($colName),-4))=='text') {
        $hist->oldValue=pq_mb_substr($oldValue,0,$histArch->getDataLength('oldValue'),'UTF-8');
        $hist->newValue=pq_mb_substr($newValue,0,$histArch->getDataLength('newValue'),'UTF-8');
      } else {
        $hist->oldValue=$oldValue;
        $hist->newValue=$newValue;
      }
      if ($obj and property_exists($obj, '_workHistory')) {
        $hist->isWorkHistory=1;
      }
      $hist->idUser=$user->id;
      $hist->operationDate=self::getOperationDate($obj);
      $returnValue=$hist->save();
      
      $colList="";
      foreach ($hist as $fld=>$val) {
        if (pq_substr($fld,0,1)=='_' or $fld=='id') continue;
        $col=$hist->getDatabaseColumnName($fld);
        if ($col) {
          $colList.="$col, ";
        }
      }
      $colList=pq_substr($colList,0,-2);
      $requestIns="INSERT INTO $tableHistArch ($colList)
                   SELECT $colList FROM $tableHist WHERE refType='$refType' and refId=$refId and operationDate <> '$hist->operationDate';"; 
      SqlDirectElement::execute($requestIns);
      $res=Sql::$lastQueryNbRows;
      $clauseDel="refType='$refType' and refId=$refId and operationDate <> '$hist->operationDate'";
      if($res > 0){
        $hist->purge($clauseDel);
      }
      // PBER Moved here From SqlElement
      // Move Assignment History
      if (property_exists($obj, '_Assignment')) {
        $ass=new Assignment();
        $assList=$ass->getSqlElementsFromCriteria(array('refType'=>get_class($obj),'refId'=>$obj->id));
        $assListId='0';
        foreach($assList as $ass) $assListId.=','.$ass->id;
        $requestIns="INSERT INTO $tableHistArch ($colList)
                   SELECT $colList FROM $tableHist WHERE refType='Assignment' and refId in ($assListId);";
        SqlDirectElement::execute($requestIns);
        $res=Sql::$lastQueryNbRows;
        $clauseDel="refType='Assignment' and refId in ($assListId)";
        if($res > 0){
          $hist->purge($clauseDel);
        }
      }
      // Move Notes History
      if (property_exists($obj, '_Note')) {
        $note = new Note ();
        $noteList=$note->getSqlElementsFromCriteria(array('refType'=>get_class($obj),'refId'=>$obj->id));
        $noteListId='0';
        foreach($noteList as $note) $noteListId.=','.$note->id;
        $requestIns="INSERT INTO $tableHistArch ($colList)
                   SELECT $colList FROM $tableHist WHERE refType='Note' and refId in ($noteListId);";
        SqlDirectElement::execute($requestIns);
        $res=Sql::$lastQueryNbRows;
        $clauseDel="refType='Note' and refId in ($noteListId)";
        if($res > 0){
          $hist->purge($clauseDel);
        }
      }
    }else{
      $hist->refType=$refType;
      if ($refType=='TicketSimple') {
        $hist->refType='Ticket';
      }
      $hist->refId=$refId;
      $hist->operation=$operation;
      $hist->colName=$colName;
      if ($colName and pq_strtolower(pq_substr($obj->getDataType($colName),-4))=='text') {
      	$hist->oldValue=pq_mb_substr($oldValue,0,$hist->getDataLength('oldValue'),'UTF-8');
      	$hist->newValue=pq_mb_substr($newValue,0,$hist->getDataLength('newValue'),'UTF-8');
      } else {
      	$hist->oldValue=$oldValue;
      	$hist->newValue=$newValue;
      }
      if ($obj and property_exists($obj, '_workHistory')) {
        $hist->isWorkHistory=1;
      }
      $hist->idUser=$user->id;
      $hist->operationDate=self::getOperationDate($obj);
      $returnValue=$hist->save();
    }
    // For TestCaseRun : store history for TestSession 
    if ($refType=='TestCaseRun' and !self::$_avoidLoop) {
      self::$_avoidLoop=true;
    	self::store ($obj, 'TestSession', $obj->idTestSession, $operation , $colName. '|' . 'TestCase' . '|' .$obj->idTestCase, $oldValue, $newValue);
    	self::$_avoidLoop=false;
    } else if ($refType=='Link') {       
    // For link : store History for both referenced items
      self::store ($obj, $obj->ref1Type, $obj->ref1Id, $operation , 'Link' . '|' . $colName. '|' . $obj->ref2Type . '|' . $obj->ref2Id, $oldValue, $newValue);
      if ($obj->ref1Type!=$obj->ref2Type or $obj->ref1Id!=$obj->ref2Id) {
        self::store ($obj, $obj->ref2Type, $obj->ref2Id, $operation , 'Link' . '|' . $colName. '|' . $obj->ref1Type . '|' . $obj->ref1Id, $oldValue, $newValue);
      }
    } else if ($refType=='Assignment' and $operation != 'update') {
      $value=SqlList::getNameFromId('ResourceAll', $obj->idResource);
      $oldValue = ($operation=='delete')?$value:'';
      $newValue = ($operation=='insert')?$value:'';
      self::store ($obj, $obj->refType, $obj->refId, $operation , '|' . $colName. '|' . $refType . '|' . $obj->id, $oldValue, $newValue);
    } else if ($refType=='Affectation' and $operation != 'update') {
      $value=SqlList::getNameFromId('ResourceAll', $obj->idResource);
      $oldValue = ($operation=='delete')?$value:'';
      $newValue = ($operation=='insert')?$value:'';
      self::store ($obj, 'Project', $obj->idProject, $operation , '|' . $colName. '|' . $refType . '|' . $obj->id, $oldValue, $newValue);
    } else if ($refType=='Note') {
    	if ($operation=='insert') {
    		$newValue=$obj->note;
    	} else if ($operation=='delete') {
        $oldValue=$obj->note;
      }
    	if ($colName!="updateDate") {    
        self::store ($obj, $obj->refType, $obj->refId, $operation , $colName. '|' . $refType . '|' . $obj->id, $oldValue, $newValue);
    	}
    } else if ($refType=='Attachment') {
      if ($operation=='insert') {
        $newValue=$obj->fileName;
      } else if ($operation=='delete') {
        $oldValue=$obj->fileName;
      }
      if ($colName!="updateDate") {    
        self::store ($obj, $obj->refType, $obj->refId, $operation , $colName. '|' . $refType . '|' . $obj->id, $oldValue, $newValue);
      }
    } else if ($refType=='Approver' ){
      $aff= new Affectable($obj->idAffectable);
      if($operation=='insert'){
        self::store ($obj, $obj->refType, $obj->refId, $operation , 'Approver', '', $aff->name);
      }else if ($operation=='delete'){
        self::store ($obj, $obj->refType, $obj->refId, $operation , 'Approver', $aff->name,'');
      }
      
    }else if($refType=='ProductStructure'){
      $prodOrComp = new ProductOrComponent($obj->idProduct);
      $objType = null;
      if($prodOrComp->idProductType){
        $objType = 'Product';
      }else if($prodOrComp->idComponentType){
        $objType = 'Component';
      }
      if($operation=='insert'){
        self::store ($obj, $objType, $obj->idProduct, 'update' , 'addComponentLink', '', intval($obj->idComponent));
        self::store ($obj, 'Component', $obj->idComponent, 'update' , 'add'.$objType.'Link', '', $prodOrComp->id);
      }else if($operation=='delete'){
      	self::store ($obj, $objType, $obj->idProduct, 'update' , 'deleteComponentLink', intval($obj->idComponent), '');
      	self::store ($obj, 'Component', $obj->idComponent, 'update' , 'delete'.$objType.'Link', $prodOrComp->id, '');
      }
    }else if($refType=='ProductVersionStructure'){
      $prod = new ProductVersion($obj->idProductVersion);
      $comp = new ComponentVersion($obj->idProductVersion);
      $prodOrComp = null;
      $objType = null;
      if($prod->id){
        $objType = 'ProductVersion';
        $prodOrComp = $prod;
      }else if($comp->id){
        $objType = 'ComponentVersion';
        $prodOrComp = $comp;
      }
      if($operation=='insert'){
        self::store ($obj, $objType, $obj->idProductVersion, 'update' , 'addComponentVersionLink', '', intval($obj->idComponentVersion));
        self::store ($obj, 'ComponentVersion', $obj->idComponentVersion, 'update' , 'add'.$objType.'Link', '', (($prodOrComp)?$prodOrComp->id:null));
      }else if($operation=='delete'){
      	self::store ($obj, $objType, $obj->idProductVersion, 'update' , 'deleteComponentVersionLink', intval($obj->idComponentVersion), '');
      	self::store ($obj, 'ComponentVersion', $obj->idComponentVersion, 'update' , 'delete'.$objType.'Link', (($prodOrComp)?$prodOrComp->id:null), '');
      }
    } else if ($refType=='Dependency') {
     	if ($operation=='insert' or $operation=='delete') {
     	  self::store($obj, $obj->predecessorRefType, $obj->predecessorRefId, $operation , 'Dependency|DependencySuccessor|'. $obj->successorRefType . '|' . $obj->successorRefId, $oldValue, $newValue);
    	  self::store($obj, $obj->successorRefType, $obj->successorRefId, $operation , 'Dependency|DependencyPredecessor|'.$obj->predecessorRefType . '|' . $obj->predecessorRefId, $oldValue, $newValue);
     	} else {
     	  self::store($obj, $obj->predecessorRefType, $obj->predecessorRefId, $operation , 'Dependency|'.$colName.'|'. $obj->successorRefType . '|' . $obj->successorRefId, $oldValue, $newValue);
     	  self::store($obj, $obj->successorRefType, $obj->successorRefId, $operation , 'Dependency|'.$colName.'|'.$obj->predecessorRefType . '|' . $obj->predecessorRefId, $oldValue, $newValue);
     	}
    	
    }
    // PBER - ADD TRACE FOR WBS CHANGE
    if ( Parameter::getGlobalParameter('debugWbsChange')===true and ( ($refType=='Project' and $colName=='sortOrder') or ($refType=='ProjectPlanningElement' and $colName=='wbsSortable') )) {
      $msg=" => Change WBS for Project #$hist->idProject | $refType #$refId | field=$colName | oldValue=$oldValue | newValue=$newValue | user=$user->id";
      debugTraceLog($msg);
      $msg="    ".$_SERVER["SCRIPT_NAME"];
      $lastFn="";
      foreach (debug_backtrace(!DEBUG_BACKTRACE_PROVIDE_OBJECT|DEBUG_BACKTRACE_IGNORE_ARGS) as $dbg) {
        $lastFn.=' => ';
        $lastFn.=$dbg['class']??'';
        $lastFn.=$dbg['type']??'';
        $lastFn.=$dbg['function']??'';
      }
      $msg.=$lastFn;
      debugTraceLog($msg);
    }
    // PBER - END
    if (pq_strpos($returnValue,'<input type="hidden" id="lastOperationStatus" value="OK"')) {
      return true;
    } else {
      return false;
    }
  }
  private static function getOperationDate($obj) {
    $objRef=get_class($obj).'#'.$obj->id;
    if (! self::$_storeDate) {
      self::$_storeDate=date('Y-m-d H:i:s');
      self::$_storeItem=$objRef;
    }
    if ($objRef!=self::$_storeItem and property_exists($obj, 'refType') and property_exists($obj, 'refId')) {
      $objRef=$obj->refType.'#'.$obj->refId;
    }
    if ($objRef!=self::$_storeItem) {
      self::$_storeDate=date('Y-m-d H:i:s');
      self::$_storeItem=$objRef;
    }
    return self::$_storeDate;
  } 
}
?>