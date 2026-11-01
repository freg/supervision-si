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
 * Action is establised during meeting, to define an action to be followed.
 */ 
require_once('_securityCheck.php');

class RequirementMain extends SqlElement {

  // List of fields that will be exposed in general user interface
  public $_sec_description;
  public $id;    // redefine $id to specify its visible place 
  public $reference;
  public $name;
  public $idProject;
  public $idRequirementType;
  public $idProduct;
  public $idComponent;  //ADD qCazelles - Add Component to Requirement - Ticket 171
  public $externalReference;
  public $creationDateTime;
  public $idUser;
  public $idContact;
  public $Origin;
  // Added by babynus
  public $idBusinessFeature;
  public $idUrgency;
  public $initialDueDate;
  public $actualDueDate;
  public $description;
  public $_sec_treatment;
  public $idRequirement;
  public $idStatus;
  public $idResource;
  public $idCriticality;
  public $idFeasibility;
  public $idRiskLevel;
  public $idPriority; //ADDED BY atrancoso ticket #84
  public $plannedWork;
  public $idTargetProductVersion;
  public $idTargetComponentVersion;  //ADD qCazelles - Add Component to Requirement - Ticket 171
  public $idMilestone;
  public $handled;
  public $handledDate;
  public $done;
  public $doneDate;
  public $idle;
  public $idleDate;
  public $cancelled;
  public $_lib_cancelled;
  public $result;
  public $_sec_Lock;
  public $_spe_lockButton;
  public $locked;
  public $idLocker;
  public $lockedDate;
  public $_sec_testCaseSummary;
  public $_tab_5_2_smallLabel = array('countTotal','countPlanned', 'countPassed', 'countBlocked', 'countFailed', 'workElementCount','');
  public $countTotal;
  public $countPlanned;
  public $countPassed;
  public $countBlocked;
  public $countFailed;
  public $_void_1;
  public $pctPlanned;
  public $pctPassed;
  public $pctBlocked;
  public $pctFailed;
  public $idRunStatus;
  public $_tab_5_1_smallLabel = array('testSummary','', '','','countIssues','');
  public $runStatusIcon;
  public $runStatusName;
  public $_void_5;
  public $_void_6;
  public $countIssues;
  public $countLinked;
  public $_sec_vote;
  public $VotingItem; //is an object
  public $_sec_predecessor;
  public $_Dependency_Predecessor=array();
  public $_sec_successor;
  public $_Dependency_Successor=array();
  public $_sec_Link_TestCase;
  public $_Link_TestCase=array();
  public $_sec_Link;
  public $_Link=array();
  public $_Attachment=array();
  public $_Note=array();
  public $_nbColMax=3;
  // Define the layout that will be used for lists
  private static $_layout='
    <th field="id" formatter="numericFormatter" width="5%" ># ${id}</th>
    <th field="nameProject" width="8%" >${idProject}</th>
    <th field="nameProduct" width="8%" >${idProduct}</th>
    <th field="nameRequirementType" width="8%" >${type}</th>
    <th field="name" width="20%" >${name}</th>
    <th field="colorNameRunStatus" width="6%" formatter="colorNameFormatter">${testSummary}</th>
    <th field="colorNameStatus" width="10%" formatter="colorNameFormatter">${idStatus}</th>
    <th field="nameResource" formatter="thumbName22" width="10%" >${responsible}</th>
    <th field="nameTargetProductVersion" width="10%" >${idTargetProductVersion}</th>
    <th field="handled" width="5%" formatter="booleanFormatter" >${handled}</th>
    <th field="done" width="5%" formatter="booleanFormatter" >${done}</th>
    <th field="idle" width="5%" formatter="booleanFormatter" >${idle}</th>
    ';

  private static $_fieldsAttributes=array("id"=>"nobr", "reference"=>"readonly",
                                  "name"=>"required", 
                                  "idRequirementType"=>"required",
                                  "idStatus"=>"required",
                                  "creationDateTime"=>"required",
                                  "handled"=>"nobr",
                                  "done"=>"nobr",
                                  "idle"=>"nobr",
                                  "idUser"=>"hidden",
                                  "countLinked"=>"hidden",
                                  "countTotal"=>"display",
                                  "countPlanned"=>"display",
                                  "countPassed"=>"display",
                                  "countFailed"=>"display",
                                  "countBlocked"=>"display",
                                  "countIssues"=>"display",
                                  "noDisplay1"=>"calculated,hidden",
                                  "noDisplay2"=>"calculated,hidden",
                                  "pctPlanned"=>"calculated,display,html",
                                  "pctPassed"=>"calculated,display,html",
                                  "pctBlocked"=>"calculated,display,html",
                                  "pctFailed"=>"calculated,display,html",
                                  "noDisplay3"=>"calculated,hidden",
                                  "noDisplay4"=>"calculated,hidden",
                                  "idRunStatus"=>"display,html,hidden,forceExport",
                                  "runStatusIcon"=>"calculated,display,html",
                                  "runStatusName"=>"calculated,display,html",
                                  "locked"=>"readonly",
                                  "idLocker"=>"readonly",
                                  "lockedDate"=>"readonly",
                                  "idleDate"=>"nobr",
                                  "cancelled"=>"nobr"
  );  
  
  private static $_colCaptionTransposition = array('idResource'=> 'responsible',
                                                   //'idTargetProductVersion'=>'targetVersion', //REMOVE qCazelles - Add Component to Requirement - Ticket 171
                                                   'idRiskLevel'=>'technicalRisk',
                                                   'plannedWork'=>'estimatedEffort',
                                                   'idContact' => 'requestor',
                                                   'idRunStatus'=>'testSummary'
                                                   );
  
  //private static $_databaseColumnName = array('idResource'=>'idUser');
  private static $_databaseColumnName = array();
  //private static $_databaseColumnName = array('idTargetProductVersion'=>'idTargetVersion'); //REMOVE qCazelles - Add Component to Requirement - Ticket 171
    
   /** ==========================================================================
   * Constructor
   * @param $id Int the id of the object in the database (null if not stored yet)
   * @return void
   */ 
  function __construct($id = NULL, $withoutDependentObjects=false) {
    parent::__construct($id,$withoutDependentObjects);
    if ($withoutDependentObjects) return; 
    $this->getCalculatedItem();
  }

   /** ==========================================================================
   * Destructor
   * @return void
   */ 
  function __destruct() {
    parent::__destruct();
  }
  
  //ADD qCazelles - Add Component to Requirement - Ticket 171
  public function setAttributes() {
    $manageComponentOnRequirement=Parameter::getGlobalParameter('manageComponentOnRequirement');
    if ($manageComponentOnRequirement!='YES') {
      self::$_fieldsAttributes['idComponent']='hidden';
      self::$_fieldsAttributes['idTargetComponentVersion']='hidden';
    }
    if (!Module::isModuleActive('moduleTargetMilestone')) {
      self::$_fieldsAttributes["idMilestone"]='hidden';
    }
    if($this->id){
      $displayVote = VotingItem::isVotable('Requirement', $this->id,$this->idRequirementType);
      if($displayVote or RequestHandler::isCodeSet('customization')){
        self::$_fieldsAttributes ['_sec_vote'] = '';
        self::$_fieldsAttributes ['VotingItem'] = '';
      }else{
        self::$_fieldsAttributes ['_sec_vote'] = 'hidden';
        self::$_fieldsAttributes ['VotingItem'] = 'hidden';
//        unset($this->_sec_vote);
//        unset($this->VotingItem);
      }
    }else if (! RequestHandler::isCodeSet('customization')){
      self::$_fieldsAttributes ['_sec_vote'] = 'hidden';
      self::$_fieldsAttributes ['VotingItem'] = 'hidden';
    }
  }
  //END ADD qCazelles - Add Component to Requirement - Ticket 171

// ============================================================================**********
// GET STATIC DATA FUNCTIONS
// ============================================================================**********
  
  /** ==========================================================================
   * Return the specific layout
   * @return String the layout
   */
  protected function getStaticLayout() {
    return self::$_layout;
  }
  
  /** ==========================================================================
   * Return the specific fieldsAttributes
   * @return Array the fieldsAttributes  
   */
  protected function getStaticFieldsAttributes() {
    return self::$_fieldsAttributes;
  }
  
  /** ============================================================================
   * Return the specific colCaptionTransposition
   * @return String the colCaptionTransposition
   */
  protected function getStaticColCaptionTransposition($fld=null) {
    return self::$_colCaptionTransposition;
  }

  /** ========================================================================
   * Return the specific databaseColumnName
   * @return String the databaseTableName
   */
  protected function getStaticDatabaseColumnName() {
    return self::$_databaseColumnName;
  }
  
  
// ============================================================================**********
// GET VALIDATION SCRIPT
// ============================================================================**********
  
  /** ==========================================================================
   * Return the validation sript for some fields
   * @return String the validation javascript (for dojo framework)
   */
  public function getValidationScript($colName) {
    $colScript = parent::getValidationScript($colName);

    if ($colName=="initialDueDate") {
      $colScript .= '<script type="dojo/connect" event="onChange" >';
      $colScript .= '  if (dijit.byId("actualDueDate").get("value")==null) { ';
      $colScript .= '    dijit.byId("actualDueDate").set("value", this.value); ';
      $colScript .= '  } ';
      $colScript .= '  formChanged();';
      $colScript .= '</script>';     
    } else if ($colName=="actualDueDate") {
      $colScript .= '<script type="dojo/connect" event="onChange" >';
      $colScript .= '  if (dijit.byId("initialDueDate").get("value")==null) { ';
      $colScript .= '    dijit.byId("initialDueDate").set("value", this.value); ';
      $colScript .= '  } ';
      $colScript .= '  formChanged();';
      $colScript .= '</script>';           
    }
    return $colScript;
  }

/** =========================================================================
   * control data corresponding to Model constraints
   * @param void
   * @return "OK" if controls are good or an error message 
   *  must be redefined in the inherited class
   */
  public function control(){
    $result="";
    
    if (!pq_trim($this->idProject) and !pq_trim($this->idProduct)) {
      $result.="<br/>" . i18n('messageMandatory',array(i18n('colIdProject') . " " . i18n('colOrProduct')));
    }
    
    if ($this->id and $this->id==$this->idRequirement) {
      $result.='<br/>' . i18n('errorHierarchicLoop');
    } else if (pq_trim($this->idRequirement)){
      $parentList=array();
    	$parent=new Requirement($this->idRequirement);
    	while ($parent->idRequirement) {
    		$parentList[$parent->idRequirement]=$parent->idRequirement;
    		$parent=new Requirement($parent->idRequirement);
    	}
      if (pq_array_key_exists($this->id,$parentList)) {
        $result.='<br/>' . i18n('errorHierarchicLoop');
      }
    }
    if (pq_trim($this->idRequirement)) {
      $parentRequirement=new Requirement($this->idRequirement);
      if ( pq_trim($this->idProduct)) {
        if (pq_trim($parentRequirement->idProduct)!=pq_trim($this->idProduct)) {
          $result.='<br/>' . i18n('msgParentRequirementInSameProjectProduct');
        }
      } else {
        if (pq_trim($parentRequirement->idProject)!=pq_trim($this->idProject)) {
          $result.='<br/>' . i18n('msgParentRequirementInSameProjectProduct');
        }
      }
    }
    
    $defaultControl=parent::control();
    if ($defaultControl!='OK') {
      $result.=$defaultControl;
    }
    if ($result=="") {
      $result='OK';
    }
    return $result;
  }
  
  public function save() {

  	if (! pq_trim($this->idRunStatus)) $this->idRunStatus=5;
  	$result=parent::save();
    return $result;
  }

  static function copyStructure($obj, $newObj, $copyToOrigin=false, 
      $copyToWithNotes=false, $copyToWithAttachments=false, $copyToWithLinks=false, 
      $copyAssignments=false, $copyAffectations=false, $toProject=null, $copySubProjects=false ,$duplicateLinkedTestsCases=false, $copyToWithStatus=false){
    if (  get_class($newObj)=='Requirement') {
      $req = new Requirement();
      $reqList=$req->getSqlElementsFromCriteria(array('idRequirement'=>$obj->id));
      foreach ($reqList as $val){
        $val->idRequirement = $newObj->id;
        $newItem=$val->copyTo(get_class($val), $val->idRequirementType, $val->name, ($toProject)?$toProject:$val->idProject, $copyToOrigin, $copyToWithNotes, $copyToWithAttachments, $copyToWithLinks);
        $resultItem=$newItem->_copyResult;
        
        $link = new Link();
        $listLink = $link->getSqlElementsFromCriteria(array('ref1Type'=>'Requirement','ref1Id'=>$val->id,'ref2Type'=>'TestCase'));
        foreach ($listLink as $lk){
          $tc = new TestCase($lk->ref2Id);
          $newTc = $tc->copy();
          $newTc->save();
          $newLink = $lk->copy();
          $newLink->ref1Id = $newItem->id;
          $newLink->ref2Id = $newTc->id;
          $newLink->save();
        }
        
        unset($newItem->_copyResult);
        if (! pq_stripos($resultItem,'id="lastOperationStatus" value="OK"')>0 ) {
          return $resultItem;
        }
        // recursively call copy structure
        $res=self::copyStructure($val, $newItem, $copyToOrigin,
            $copyToWithNotes, $copyToWithAttachments, $copyToWithLinks,
            $copyAssignments, $copyAffectations,$toProject,$copySubProjects,$duplicateLinkedTestsCases,$copyToWithStatus);
        if ($res!='OK') {
          return $res;
        }
      }
      return "OK"; // No error ;)
    }
  }
  
  public function drawSpecificItem($item){
    global $print;
    $result="";
    if ($item=='lockButton' and !$print) {
      if ($this->locked) {
        $canUnlock=false;
        $user=getSessionUser();
        if ($user->id==$this->idLocker) {
          $canUnlock=true;
        } else {
          $right=SqlElement::getSingleSqlElementFromCriteria('habilitationOther', array('idProfile'=>$user->getProfile($this), 'scope'=>'requirement'));        
          if ($right) {
            $list=new ListYesNo($right->rightAccess);
            if ($list->code=='YES') {
              $canUnlock=true;
            }
          }  
        }
        if ($canUnlock) {
          $result .= '<tr><td></td><td>';
          $result .= '<button id="unlockRequirement" dojoType="dijit.form.Button" showlabel="true"'; 
          $result .= ' title="' . i18n('unlockRequirement') . '" >';
          $result .= '<span>' . i18n('unlockRequirement') . '</span>';
          $result .=  '<script type="dojo/connect" event="onClick" args="evt">';
          $result .=  '  unlockRequirement();';
          $result .= '</script>';
          $result .= '</button>';
          $result .= '</td></tr>';
        }
      } else {
        $result .= '<tr><td></td><td>';
        $result .= '<button id="lockRequirement" dojoType="dijit.form.Button" showlabel="true"'; 
        $result .= ' title="' . i18n('lockRequirement') . '" >';
        $result .= '<span>' . i18n('lockRequirement') . '</span>';
        $result .=  '<script type="dojo/connect" event="onClick" args="evt">';
        $result .=  '  lockRequirement();';
        $result .= '</script>';
        $result .= '</button>';
        $result .= '</td></tr>';
      }
      $result .= '<input type="hidden" id="idCurrentUser" name="idCurrentUser" value="' . getSessionUser()->id . '" />';
      return $result;
    }
  }
  
   
  public function getCalculatedItem(){
     if ($this->countTotal!=0) {
     	$this->pctPlanned='<i>('.htmlDisplayPct(round($this->countPlanned/$this->countTotal*100)).')</i>';
     	$this->pctPassed='<i>('.htmlDisplayPct(round($this->countPassed/$this->countTotal*100)).')</i>';
      $this->pctFailed='<i>('.htmlDisplayPct(round($this->countFailed/$this->countTotal*100)).')</i>';
      $this->pctBlocked='<i>('.htmlDisplayPct(round($this->countBlocked/$this->countTotal*100)).')</i>';
     }
     if ($this->id) {
       $name=SqlList::getNameFromId('RunStatus', $this->idRunStatus,false);
       $this->runStatusName=i18n($name);
       $this->runStatusIcon='<img src="../view/css/images/icon'.pq_ucfirst($name).'22.png" />';
     }
  }
  
  public function updateDependencies() {
  	$this->_noHistory=true;
  	$listCrit='idTestCase in (0';
  	$this->countLinked=0;
  	$this->countIssues=0;
    foreach ($this->_Link as $link) {
      if ($link->ref2Type=='TestCase') {
        $listCrit.=','.Sql::fmtId($link->ref2Id);
        $this->countLinked+=1;
      }
      if ($link->ref2Type=='Ticket') {
        $this->countIssues+=1;
      }
    }
    $listCrit.=")";
    $tcr=new TestCaseRun();
    $listTcr=$tcr->getSqlElementsFromCriteria(null, false, $listCrit,  "statusDateTime asc");
    $this->countBlocked=0;
    $this->countFailed=0;
    $this->countPassed=0;
    $this->countPlanned=0;
    $this->countTotal=0;
    $countTotal=0;
    $lstStatus=array();
    // Fixing : take into account only last test cas run for a test case
    foreach($listTcr as $tcr) {
    	$countTotal+=1;
    	$lstStatus[$tcr->idTestCase]=$tcr;
    }
    // adding taking into account sub-requirements for top requirement
    $lstReq=$this->getSqlElementsFromCriteria(array('idRequirement'=>$this->id));
    $lstStatus=array_merge($lstStatus,$lstReq);
    foreach ($lstStatus as $tcr) { // thanks to previous treatment, this list includes only last status of test case
    	$this->countTotal+=1;
      if ($tcr->idRunStatus==1) {
        $this->countPlanned+=1;
      }
      if ($tcr->idRunStatus==2) {
        $this->countPassed+=1;
      }
      if ($tcr->idRunStatus==3) {
        $this->countFailed+=1;
      }
      if ($tcr->idRunStatus==4) {
        $this->countBlocked+=1;
      }
    }
    if ($this->countFailed>0) {
      $this->idRunStatus=3; // failed
    } else if ($this->countBlocked>0) {
      $this->idRunStatus=4; // blocked
    } else if ($this->countPlanned>0) {
      $this->idRunStatus=1; // planned
    } else if ($this->countTotal==0) {
      $this->idRunStatus=5; // empty
    } else {
      $this->idRunStatus=2; // passed
    }  
    $this->save();
    if ($this->idRequirement) {
    	$top=new Requirement($this->idRequirement);
    	$top->updateDependencies();
    }
  }
}
?>