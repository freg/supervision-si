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
 * Habilitation defines right to the application for a menu and a profile.
 */ 
require_once('_securityCheck.php');
class Link extends SqlElement {

  // extends SqlElement, so has $id
  public $id;    // redefine $id to specify its visible place 
  public $ref1Type;
  public $ref1Id;
  public $ref2Type;
  public $ref2Id;
  public $comment;
  public $creationDate;
  public $idUser;
  public $idSynchronizationItem;
  
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
// MISCELLANOUS FUNCTIONS
// ============================================================================**********
  
  /**
   * Save object (permuts objects ref if needed)
   * @see persistence/SqlElement#save()
   */
  public function save() {

    if ($this->ref2Type=='TicketSimple') $this->ref2Type='Ticket';
    if ($this->ref1Type=='TicketSimple') $this->ref1Type='Ticket';
    if ($this->ref2Type < $this->ref1Type) {
      $type=$this->ref2Type;
      $id=$this->ref2Id;
      $this->ref2Type=$this->ref1Type;
      $this->ref2Id=$this->ref1Id;
      $this->ref1Type=$type;
      $this->ref1Id=$id;
    } 
    $result=parent::save();
    
    if ($this->ref1Type=='Requirement' and ($this->ref2Type=='TestCase' or $this->ref2Type=='Ticket')) {
    	$req=new Requirement($this->ref1Id);
      $req->updateDependencies();
    }
    if ($this->ref1Type=='TestSession' and $this->ref2Type=='Ticket') {
      $ts=new TestSession($this->ref1Id);
      $ts->updateDependencies();
    }
    if(SqlElement::class_exists($this->ref1Type)){
      // gautier add
      $class1 = $this->ref1Type;
      $id1 = $this->ref1Id;
      $obj = new $class1( $id1 );
      if (property_exists ( $class1, 'lastUpdateDateTime' ) and !SqlElement::$_doNotSaveLastUpdateDateTime) { 
        $resObj=$obj->saveForced();
      }
    }
    
    if(SqlElement::class_exists($this->ref2Type)){
      $class2 = $this->ref2Type;
      $id2 = $this->ref2Id;
      $obj = new $class2( $id2 );
      if (property_exists ( $class2, 'lastUpdateDateTime' )and !SqlElement::$_doNotSaveLastUpdateDateTime) {
        $obj->lastUpdateDateTime = date ( "Y-m-d H:i:s" );
        $resObj=$obj->saveForced();
      }
      // end gautier 
    }
    
    if($this->ref1Type == 'Acceptance' and $this->ref2Type == 'Activity'){
      $workCommandDone = new WorkCommandDone();
      $workCommandDoneList = $workCommandDone->sumSqlElementsFromCriteria('doneQuantity', array('refType'=>'Activity', 'refId'=>$this->ref2Id), null, 'idWorkCommand, idCommand');
      $workCommandDoneList = $workCommandDoneList ?: [];
      foreach ($workCommandDoneList as $workCommandDone){
        $workCommandAccepted = new WorkCommandAccepted();
        $workCommandAcceptedList = $workCommandAccepted->getSqlElementsFromCriteria(array('refType'=>'Activity', 'refId'=>$this->ref2Id, 'idWorkCommand'=>$workCommandDone['idworkcommand']));    
        $newWorkCommandAccepted = new WorkCommandAccepted();
        $newWorkCommandAccepted->idAcceptance = $this->ref1Id;
        $newWorkCommandAccepted->refType = $this->ref2Type;
        $newWorkCommandAccepted->refId = $this->ref2Id;
        $newWorkCommandAccepted->idWorkCommand = $workCommandDone['idworkcommand'];
        $newWorkCommandAccepted->idCommand = $workCommandDone['idcommand'];
        $acceptedQuantity = 0;
        foreach ($workCommandAcceptedList as $workCommandAccepted){
          $acceptedQuantity += $workCommandAccepted->acceptedQuantity;
        }
        $quantity = $workCommandDone['sumdonequantity'] - $acceptedQuantity;
        $newWorkCommandAccepted->acceptedQuantity = ($quantity > 0)?$quantity:0;
        $newWorkCommandAccepted->save();
      }
    }
    return $result;
  }
  
  public function delete() {
  	
  	$result=parent::delete();
  	
    if ($this->ref1Type=='Requirement' and ($this->ref2Type=='TestCase' or $this->ref2Type=='Ticket')) {
      $req=new Requirement($this->ref1Id);
      $req->updateDependencies();
    }
    if ($this->ref1Type=='TestSession' and $this->ref2Type=='Ticket') {
      $ts=new TestSession($this->ref1Id);
      $ts->updateDependencies();
    }
    
    // gautier add
    if(SqlElement::class_exists($this->ref1Type)){
      $class1 = $this->ref1Type;
      $id1 = $this->ref1Id;
      $obj = new $class1( $id1 );
      if (property_exists ( $class1, 'lastUpdateDateTime' ) and !SqlElement::$_doNotSaveLastUpdateDateTime) {
        $obj->lastUpdateDateTime = date ( "Y-m-d H:i:s" );
        $resObj=$obj->saveForced();
      }
    }
    
    if(SqlElement::class_exists($this->ref1Type)){
      $class2 = $this->ref2Type;
      $id2 = $this->ref2Id;
      $obj = new $class2( $id2 );
      if (property_exists ( $class2, 'lastUpdateDateTime' ) and !SqlElement::$_doNotSaveLastUpdateDateTime) {
        $obj->lastUpdateDateTime = date ( "Y-m-d H:i:s" );
        $resObj=$obj->saveForced();
      }
    }
    
    if($this->ref1Type == 'Acceptance' and $this->ref2Type=='Activity'){
      $workCommandAccepted = new WorkCommandAccepted();
      $workCommandAcceptedList = $workCommandAccepted->getSqlElementsFromCriteria(array('idAcceptance'=>$this->ref1Id, 'refType'=>$this->ref2Type, 'refId'=>$this->ref2Id));
      foreach ($workCommandAcceptedList as $workCommandAccepted){
        $workCommandAccepted->delete();
      }
    }
    
    // end gautier add
    return $result;
  }
  
  public function deleteControl(){
    global $deleteObjectInProgress; 
    $result="";
    if (! $deleteObjectInProgress) {
      $synchItem = new SynchronizedItems();
      $synch = $synchItem->countSqlElementsFromCriteria(array('ref1Type'=>$this->ref1Type,'ref2Type'=>$this->ref2Type,'ref1Id'=>$this->ref1Id,'ref2Id'=>$this->ref2Id));
      if($synch){
        $result.='<br/>' . i18n('errorDeleteSynchItems');
      }else{
        $synch2 = $synchItem->countSqlElementsFromCriteria(array('ref1Type'=>$this->ref2Type,'ref2Type'=>$this->ref1Type,'ref1Id'=>$this->ref2Id,'ref2Id'=>$this->ref1Id));
        if($synch2)$result.='<br/>' . i18n('errorDeleteSynchItems');
      }
    }
    if (! $result) {
      $result=parent::deleteControl();
    }
    return $result;
  }
  
  /** ==========================================================================
   * Return a list of Link objects involving one given object
   * @param Object $obj the object we are looking links for
   * @param String $classLink optional reference to a class to restrict links of this class
   * @return Array array of Link objects
   */
  static function getLinksForObject($obj, $classLink=null) {
    $where=null;
    $orderBy=null;
    $link=new Link();
    $class=get_class($obj);
    if ($class=='TicketSimple') $class='Ticket';
    if ($classLink) {
      if ($class<$classLink) {
        $where=" ref1Type='" . $class . "' and ref1Id=" . Sql::fmtId($obj->id) . " and ref2Type='" . $classLink . "' ";
      } else if ($class>$classLink) {
        $where=" ref2Type='" . $class . "' and ref2Id=" . Sql::fmtId($obj->id) . " and ref1Type='" . $classLink . "' ";
      } else {
        $where=" ref1Type='" . $class . "' and ref2Type='" . $class . "' and (ref1Id=" . Sql::fmtId($obj->id) . " or ref2Id=" . Sql::fmtId($obj->id) . "  ) ";
      }
    } else {
      $where=" ( ref1Type='" . $class . "' and ref1Id=" . Sql::fmtId($obj->id) . ") ";
      $where.=" or ( ref2Type='" . $class . "' and ref2Id=" . Sql::fmtId($obj->id) . " ) ";
    }
    //echo $where . "\n";
    $list=$link->getSqlElementsFromCriteria(null,false,$where,$orderBy);
    return $list;
  }
  /** ==========================================================================
   * Return a list of links as "type" and "id" array involving one given object
   * @param Object $obj the object we are looking links for
   * @param String $classLink optional reference to a class to restrict links of this class
   * @return Array array of "type" and "id" sur array
   */
  static function getLinksAsListForObject($obj, $classLink=null) {
    $list = self::getLinksForObject($obj, $classLink);
    $class=get_class($obj);
    $result=array();
    foreach($list as $listObj) {
      $type="";
      $id="";
      if ($listObj->ref1Type==$class and $listObj->ref1Id==$obj->id ) {
         $type=$listObj->ref2Type;
         $id=$listObj->ref2Id;
      } else {
         $type=$listObj->ref1Type;
         $id=$listObj->ref1Id;
      }
      $res=array("type"=>$type, "id"=>$id);
      $result[$listObj->id]=$res;
    }
    return $result;
  }
  
  static function getLinksAsObjectsForObject($obj, $classLink=null) {
    $list = getLinksForObject($obj, $classLink);
    $class=get_class($obj);
    foreach($list as $lstObj) {
      $type="";
      $id="";
      if ($lstObj->ref1Type=$class and $lstObj->ref1Id=$obj->id ) {
         $type=$lstObj->ref2Type;
         $id=$lstObj->ref2Id;
      } else {
         $type=$lstObj->ref1Type;
         $id=$lstObj->ref1Id;
      }
      $resObj=new $type($id);
      $result[$lstObj->id]=$resObj;
    }
    return $result;
  }

/** =========================================================================
   * control data corresponding to Model constraints
   * @param void
   * @return "OK" if controls are good or an error message 
   *  must be redefined in the inherited class
   */
  public function control(){
    $result="";
    $checkCrit=array('ref1Type'=>$this->ref1Type,
                     'ref1Id'=>$this->ref1Id,
                     'ref2Type'=>$this->ref2Type,
                     'ref2Id'=>$this->ref2Id);
    $lnk=new Link();
    $check=$lnk->getSqlElementsFromCriteria($checkCrit);
    if($this->ref1Id==$this->ref2Id and $this->ref2Type==$this->ref1Type){
      $result.='<br/>' . i18n('errorLinkItemToItself');
    }    
    if (count($check)>0) {
      $result.='<br/>' . i18n('errorDuplicateLink');
    }
    if( Module::isModuleActive('moduleGestionCA') and $this->ref1Type == 'Bill' and $this->ref2Type == 'Command'){
      $checkUniqueBill=$lnk->getSqlElementsFromCriteria(array('ref1Type'=>$this->ref1Type, 'ref1Id'=>$this->ref1Id, 'ref2Type'=>'Command'));
      if (count($checkUniqueBill)>0) {
        $result.='<br/>' . i18n('errorUniqueBillLink');
      }
    }
    $defaultControl=parent::control();
    if ($defaultControl!='OK') {
      $result.=$defaultControl;
    }if ($result=="") {
      $result='OK';
    }
    return $result;
  }
}
?>