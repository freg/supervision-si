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
 * Client is the owner of a project.
 */  
require_once('_securityCheck.php'); 
class WorkTokenClientContractWork extends SqlElement {

  public $id;
  public $idWork;
  public $time;
  public $idWorkTokenClientContract;
  public $workTokenQuantity;
  public $idWorkTokenMarkup;
  public $workTokenMarkupQuantity;
  public $billable;
  public $_isNameTranslatable = true;
  
  private static $_databaseTableName = 'worktokenclientcontractwork';
  private static $_databaseCriteria = array();
  /** ==========================================================================
   * Constructor
   * @param $id Int the id of the object in the database (null if not stored yet)
   * @return void
  */
  /** ========================================================================
   * Return the specific databaseTableName
   * @return String the databaseTableName
  */
  protected function getStaticDatabaseTableName() {
    $paramDbPrefix=Parameter::getGlobalParameter('paramDbPrefix');
    return $paramDbPrefix . self::$_databaseTableName;
  }
  
  /** ========================================================================
   * Return the specific database criteria
   * @return String the databaseTableName
   */
  protected function getStaticDatabaseCriteria() {
    return self::$_databaseCriteria;
  }
  
  /** ==========================================================================
   * Construct
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
  
  public function save() {
    $old=$this->getOld();
    
    $result=parent::save();
    
    // Update Current Contract
    self::updateContract($this->idWorkTokenClientContract);
    // Update Old contract
    if ($old->idWorkTokenClientContract and $old->idWorkTokenClientContract!=$this->idWorkTokenClientContract) {
      self::updateContract($old->idWorkTokenClientContract);
    }
    return $result;
  }
  
  public static function updateContract($idWorkTokenClientContract) {
    $idClientContract = SqlList::getFieldFromId('WorkTokenClientContract', $idWorkTokenClientContract, 'idClientContract');
    $idWorkTokenClientContractList = SqlList::getListWithCrit('WorkTokenClientContract', array('idClientContract'=>$idClientContract,'idleToken'=>'0'), 'id');
    $idWorkTokenClientContractListCrit = (count($idWorkTokenClientContractList)>0)?implode(',', $idWorkTokenClientContractList):'0';
    if (pq_trim($idWorkTokenClientContractListCrit)=='') $idWorkTokenClientContractListCrit='0';
    $where = "idWorkTokenClientContract in ($idWorkTokenClientContractListCrit) and billable=1";
    $wtccw=new WorkTokenClientContractWork();
    $clientContract = new ClientContract($idClientContract, true);
    $clientContract->tokenUsed = $wtccw->sumSqlElementsFromCriteria('workTokenMarkupQuantity', null, $where);
    $clientContract->tokenLeft = $clientContract->tokenOrdered - $clientContract->tokenUsed;
    $clientContract->save();
  }
  
  public function control(){
    $result="";
    $defaultControl=parent::control();
    if ($defaultControl != 'OK') {
      $result .= $defaultControl;
    }
    $old = $this->getOld();
    if($this->id){
      if( $this->idWorkTokenClientContract!='' and $this->workTokenQuantity!=$old->workTokenQuantity){
        self::calculIfOrderFullyConsumed('save',$old);
      }elseif ($this->idWorkTokenClientContract!=$old->idWorkTokenClientContract){
        self::calculIfOrderFullyConsumed('save',$old);
      }
    }else{
      self::calculIfOrderFullyConsumed('save');
    }
       
    if ($result=="") {
      $result='OK';
    }
    return $result;
  }
  
  public function delete(){
    $result = parent::delete();
    if (! pq_strpos($result,'id="lastOperationStatus" value="OK"')) {
      return $result;
    }
    self::calculIfOrderFullyConsumed('delete');
    
    self::updateContract($this->idWorkTokenClientContract);
    
    return $result;
  }
  
public function calculIfOrderFullyConsumed($mode,$old=false){

    if ($this->billable==0) {
    	return;
    }
    if($mode!='delete' and $old and $this->idWorkTokenClientContract!=$old->idWorkTokenClientContract){
      $oldWorkTokenCC= new WorkTokenClientContract($old->idWorkTokenClientContract);
      if($oldWorkTokenCC->fullyConsumed==1){
        $where="id<>$this->id and idWorkTokenClientContract=$old->idWorkTokenClientContract";
        $oldSum=$this->sumSqlElementsFromCriteria('workTokenMarkupQuantity', null,$where);
        $oldTotal=$oldSum-$this->workTokenMarkupQuantity;
        if($oldWorkTokenCC->quantity > $oldTotal){
          $oldWorkTokenCC->fullyConsumed=0;
          $oldWorkTokenCC->save();
        }
      }
    }
    $workTokenCC= new WorkTokenClientContract($this->idWorkTokenClientContract);
    $where="";
    if($this->id)$where.="id<>".Sql::fmtId($this->id)." and";
    $idWorkTokenClientContract = ($this->idWorkTokenClientContract)?$this->idWorkTokenClientContract:'0';
    $where.=" idWorkTokenClientContract=$idWorkTokenClientContract and billable=1";
    $sumQuantityW=$this->sumSqlElementsFromCriteria('workTokenMarkupQuantity', null,$where);
    $total=$sumQuantityW;
    if ($this->billable and $mode!='delete') $total+=floatval($this->workTokenMarkupQuantity);
    if($workTokenCC->quantity <=$total and $workTokenCC->fullyConsumed==0){
      $workTokenCC->fullyConsumed=1;
      $res=$workTokenCC->save();
    }else if($workTokenCC->fullyConsumed==1){
      $workTokenCC->fullyConsumed=0;
      $res=$workTokenCC->save();
    }
  }
}
?>