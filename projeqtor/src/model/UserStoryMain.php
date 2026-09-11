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
require_once('_securityCheck.php');

class UserStoryMain extends SqlElement {

  public $_sec_description;
  public $id;
  public $reference;
  public $name;
  public $idUserStoryType;
  public $creationDate;
  public $lastUpdateDateTime;
  public $idUser;
  public $idProject;
  public $idEpic;
  public $idSprint;
  public $idPersonas;
  public $featureAction;
  public $featureGoal;
  public $featureOpposite;
  public $acceptationCriteria;
  public $description;
  public $_sec_treatment;
  public $idStatus;
  public $idResource;
  public $idScrumPriority;
  public $storyPoints;
  public $businessValue;
  public $WorkElement;
  public $handled;
  public $handledDate;
  public $done;
  public $doneDate;
  public $idle;
  public $idleDate;
  public $cancelled;
  public $_lib_cancelled;
  public $result;
  public $_sec_productComponent;
  public $idProduct;
  public $idComponent;
  public $idTargetProductVersion;
  public $idTargetComponentVersion;
  public $_sec_ToDoList;
  public $_SubTask;
  public $_sec_vote;
  public $VotingItem; //is an object
  public $_sec_Link;
  public $_Link = array();
  public $_Attachment = array();
  public $_Note = array();
  public $_nbColMax = 3;
  
  private static $_layout = '
    <th field="id" formatter="numericFormatter" width="5%" ># ${id}</th>
    <th field="nameProject" width="10%" >${idProject}</th>
    <th field="name" width="25%" >${name}</th>
    <th field="colorNameScrumPriority" width="10%" formatter="colorNameFormatter">${idScrumPriority}</th>
    <th field="namePersonas" width="10%" >${idPersonas}</th>
    <th field="colorNameStatus" width="15%" formatter="colorNameFormatter">${idStatus}</th>
    <th field="nameEpic" width="10%" >${idEpic}</th>
    <th field="nameSprint" width="10%" >${idSprint}</th>';
  
  private static $_fieldsAttributes = array(
      "id" => "nobr",
      "reference" => "readonly",
      "name" => "required",
      "idUserStoryType"=>"required",
      "description" => "readonly",
      "idProject" => "required",
      "idStatus" => "required",
      "creationDate" => "required",
      "handled" => "nobr",
      "done" => "nobr",
      "idle" => "nobr",
      "idleDate" => "nobr",
      "cancelled" => "nobr"
  );
  
  private static $_colCaptionTransposition = array(
      'idUser' => 'issuer',
      'idResource' => 'responsible'
  );
  
  private static $_databaseColumnName = array(
      'idTargetProductVersion' => 'idVersion',
      'idTargetComponentVersion' => 'idComponentVersion');

  function __construct($id = NULL, $withoutDependentObjects=false) {
    parent::__construct($id,$withoutDependentObjects);
    if ($this->idSprint and is_object($this->WorkElement) and $this->WorkElement->realWork>0) {
      self::$_fieldsAttributes['idSprint']='readonly';
    }
    if (Parameter::getGlobalParameter('realWorkOnlyForResponsible')=='YES') {
      if ($this->id and $this->idResource != getSessionUser()->id) {
        WorkElement::lockRealWork();
      }
    }
  }
  
  function __destruct() { 
    parent::__destruct(); 
  }
  
  /**
   * ==========================================================================
   * Return the specific layout
   *
   * @return String the layout
   */
  protected function getStaticLayout() {
    return self::$_layout;
  }
  
  /**
   * ==========================================================================
   * Return the specific fieldsAttributes
   *
   * @return Array the fieldsAttributes
   */
  protected function getStaticFieldsAttributes() {
    return self::$_fieldsAttributes;
  }
  
  /**
   * ============================================================================
   * Return the specific colCaptionTransposition
   *
   * @return String the colCaptionTransposition
   */
  protected function getStaticColCaptionTransposition($fld = null) {
    return self::$_colCaptionTransposition;
  }
  
  /**
   * ========================================================================
   * Return the specific databaseColumnName
   *
   * @return String the databaseTableName
   */
  protected function getStaticDatabaseColumnName() {
    return self::$_databaseColumnName;
  }
  
  // ============================================================================**********
  // GET VALIDATION SCRIPT
  // ============================================================================**********
  
  /**
   * ==========================================================================
   * Return the validation sript for some fields
   *
   * @return String the validation javascript (for dojo framework)
   */
  public function getValidationScript($colName) {
    $colScript = parent::getValidationScript ( $colName );
    if ($colName == "idProject") {
      $colScript .= '<script type="dojo/connect" event="onChange" >';
      $colScript .= '   refreshList("idEpic","idProject", this.value); ';
      $colScript .= '   refreshList("idSprint","idProject", this.value); ';
      $colScript .= '  formChanged();';
      $colScript .= '</script>';
    }
    if ($colName=="done") {
      $colScript .= '<script type="dojo/connect" event="onChange" >';
      $colScript .= '  var done=dijit.byId("done").get("checked");';
      $colScript .= '  var real=dijit.byId("WorkElement_realWork").get("value");';
      $colScript .= '  var planned=dijit.byId("WorkElement_plannedWork").get("value");';
      $colScript .= '  if (done) {';
      $colScript .= '    dijit.byId("WorkElement_leftWork").set("value", 0);';
      $colScript .= '  } else {';
      $colScript .= '    var left=planned-real;';
      $colScript .= '    if (left<0) left=0;';
      $colScript .= '    dijit.byId("WorkElement_leftWork").set("value", left);';
      $colScript .= '  } ';
      $colScript .= '  formChanged();';
      $colScript .= '</script>';
    }
    return $colScript;
  }
  
  public function setAttributes() {
    if(Parameter::getUserParameter('paramLayoutObjectDetail')=="col"){
      self::$_fieldsAttributes["fixPlanning"]='hidden';
    }
    if($this->id){
      $displayVote = VotingItem::isVotable('UserStory', $this->id,$this->idUserStoryType);
      if($displayVote or RequestHandler::isCodeSet('customization')){
        self::$_fieldsAttributes ['_sec_vote'] = '';
        self::$_fieldsAttributes ['VotingItem'] = '';
      }else{
        self::$_fieldsAttributes ['_sec_vote'] = 'hidden';
        self::$_fieldsAttributes ['VotingItem'] = 'hidden';
      }
    }else if (! RequestHandler::isCodeSet('customization')) {
      self::$_fieldsAttributes ['_sec_vote'] = 'hidden';
      self::$_fieldsAttributes ['VotingItem'] = 'hidden';
    }
    if (!Module::isModuleActive('moduleTodoList') or Parameter::getUserParameter('displaySubTask')!="YES"
        or (! $this->id and ! RequestHandler::isCodeSet('customization')) ){//Parameter::getGlobalParameter('activateSubtasksManagement')!='YES'
          self::$_fieldsAttributes ['_SubTask'] = 'hidden';
          self::$_fieldsAttributes ['_sec_ToDoList'] = 'hidden';
          unset($this->_sec_ToDoList);
    } else if ($this->id) {
      $user=getSessionUser();
      $habilSub=SqlElement::getSingleSqlElementFromCriteria('HabilitationOther', array('idProfile'=>$user->getProfile($this),'scope'=>'subtask'));
      $listYesNo=new ListYesNo($habilSub->rightAccess);
      if ($listYesNo->code!='YES') {
        self::$_fieldsAttributes ['_SubTask'] = 'hidden';
        self::$_fieldsAttributes ['_sec_ToDoList'] = 'hidden';
        unset($this->_sec_ToDoList);
      }
    }
  }
  
  /**
   * =========================================================================
   * control data corresponding to Model constraints
   *
   * @param
   *          void
   * @return "OK" if controls are good or an error message
   *         must be redefined in the inherited class
   */
  public function control() {
    $result = "";
    $old = $this->getOld(false);
    
    if ($this->id and pq_trim($old->idSprint) and pq_trim($this->idSprint)!=pq_trim($old->idSprint) and $this->WorkElement->realWork>0)  {
      $result .='<br/>' . i18n ( 'msgPlanningSprintWithWork' );
    }
    
    $proj = new Project($this->idProject,true);
    $projType = new ProjectType($proj->idProjectType);
    if($projType->isLeadProject){
      if (!$this->id) {
        $result .= '<br/>' . i18n ( 'cantCreateAnActivityFromLeadProject' );
      }
      if ($this->id && $old->idProject != $this->idProject) {
        //      ==> Can't associated the activity with the project dedicated to the leave
        $result .= '<br/>' . i18n ( 'cantAssociateAnActivityWithLeadProject' );
      }
    }
    
    if ($this->id && $old->idProject != $this->idProject) {
      $ass = new Assignment();
      $lstAss = $ass->getSqlElementsFromCriteria(array('refType'=>'UserStory','refId'=>$this->id,'idle'=>'0'));
      $proj = new Project($this->idProject,true);
      $topProject = $proj->getTopProjectList(true);
      foreach ( $lstAss as $as){
        if($as->isMaterial)continue;
        $aff = new Affectation();
        $where = " idResource = ".$as->idResource." and idProject in " . transformValueListIntoInClause($topProject);
        $affExist = $aff->countSqlElementsFromCriteria(null,$where);
        if($affExist==0){
          $result .= '<br/>' . i18n ( 'cantMoveActivityWithoutAffectedResource', array($as->idResource,SqlList::getNameFromId('Affectable',$as->idResource)) );
          break;
        }
      }
    }
    
    $defaultControl = parent::control ();
    if ($defaultControl != 'OK') {
      $result .= $defaultControl;
    }
    if ($result == "") {
      $result = 'OK';
    }
    return $result;
  }
  
  public function deleteControl() {
    $result='';
    $canDeleteRealWork = false;
    $crit = array('idProfile' => getSessionUser()->getProfile ( $this ), 'scope' => 'canDeleteRealWork');
    $habil = SqlElement::getSingleSqlElementFromCriteria ( 'HabilitationOther', $crit );
    if ($habil and $habil->id and $habil->rightAccess == '1') {
      $canDeleteRealWork = true;
    }
    if ($this->WorkElement and $this->WorkElement->realWork>0 and !$canDeleteRealWork) {
      $result.='<br/>' . i18n('msgUnableToDeleteRealWork');
    }
    if ($result=='') {
      $result .= parent::deleteControl();
    }
    return $result;
  }

  function save() {
    $old = $this->getOld (false);
    if (! $this->name) {
      $this->name = Sql::fmtStr(_('UserStory')) . " #" . date('Y-m-d_H:i');
    } 
    if($this->id and $old->idSprint and $this->idSprint == ""){
      SqlElement::$_skipWorkflowControl=true;
      $statusList = SqlList::getStatusList(get_class($this));
      $lowestStatus = array_key_first($statusList);
      $this->idStatus = $lowestStatus;
    }
    
    if (isset($this->WorkElement)) {
      $this->WorkElement->done=$this->done;
      $this->WorkElement->idle=$this->idle;
    }
    if ($old->idSprint!=$this->idSprint and $this->idSprint) {
      $spt=new Sprint($this->idSprint);
      if ($spt->idTargetProductVersion) {
        $this->idTargetProductVersion=$spt->idTargetProductVersion;
        $vers=new Version($$spt->idTargetProductVersion);
        if ($vers->idProduct) {
          $this->idProduct=$vers->idProduct;
        }
      }
    }
    
    if ($this->idPersonas || $this->featureAction || $this->featureGoal || $this->featureOpposite) {
      $blocks = array();
      
      if ($this->idPersonas) {
        $label = ucfirst(i18n('colIdPersonas'));
        $label .= ' : ';
        $value = SqlList::getNameFromId('Personas', $this->idPersonas);
        $blocks[] = '<b>'.$label.'</b>'.$value;
      }
      
      if ($this->featureAction) {
        $label = i18n('colFeatureAction');
        $label = preg_replace('/\s*\.\.\.$/', ' : ', $label);
        $value = strip_tags($this->featureAction);
        $blocks[] = '<b>'.$label.'</b>'.$value;
      }
      
      if ($this->featureGoal) {
        $label = i18n('colFeatureGoal');
        $label = preg_replace('/\s*\.\.\.$/', ' : ', $label);
        $value = strip_tags($this->featureGoal);
        $blocks[] = '<b>'.$label.'</b>'.$value;
      }
      
      if($this->featureOpposite){
        $label = i18n('colFeatureOpposite');
        $label = preg_replace('/\s*\.\.\.$/', ' : ', $label);
        $value = strip_tags($this->featureOpposite);
        $blocks[] = '<b>'.$label.'</b>'.$value;
      }
      
      $this->description = implode('<br/><br/>', $blocks);
    }
    
    $result = parent::save ();
    
    if ($old->idSprint and $old->idSprint!=$this->idSprint) {
      // if top sprint changed, must update corresponding Planning element for userStory work summary
      $spe = SqlElement::getSingleSqlElementFromCriteria ( 'SprintPlanningElement', array (
          'refType' => 'Sprint',
          'refId' => $old->idSprint
      ) );
      if ($spe and $spe->id) {
        $spe->updateWorkElementSummary ();
      }
    }
    
    if($this->idEpic != $old->idEpic){
      if($this->idEpic){
        $newEpic = new Epic($this->idEpic);
        $newEpic->updateStoryPointAndBusinessValue();
        $newEpic->updateStatusFromUserStory();
      }
      if($old->idEpic){
        $oldEpic = new Epic($old->idEpic);
        $oldEpic->updateStoryPointAndBusinessValue();
        $oldEpic->updateStatusFromUserStory();
      }
    }
    
    if($this->idSprint != $old->idSprint){
      if($this->idSprint){
        $newSprint = new Sprint($this->idSprint);
        $newSprint->updateStatusFromUserStory();
      }
      if($old->idSprint){
        $oldSprint = new Sprint($old->idSprint);
        $oldSprint->updateStatusFromUserStory();
      }
    }
    
    if($this->idStatus != $old->idStatus){
      if($this->idSprint){
        $newSprint = new Sprint($this->idSprint);
        $newSprint->updateStatusFromUserStory();
      }
      if($this->idEpic){
        $newEpic = new Epic($this->idEpic);
        $newEpic->updateStatusFromUserStory();
      }
    }
    
    if(($this->storyPoints != $old->storyPoints) or ($this->businessValue != $old->businessValue)){
      $epic = new Epic($this->idEpic);
      $epic->updateStoryPointAndBusinessValue();
    }
    
    if ($this->id and $old->idProject != $this->idProject) {
      $sub = new SubTask();
      $subList = $sub->getSqlElementsFromCriteria(array('refType' => 'UserStory', 'refId' => $this->id),false);
      foreach ($subList as $sub) {
        $sub->idProject = $this->idProject;
        $sub->saveForced();
      }
    }
    
    SqlElement::$_skipWorkflowControl=false;
    if (! pq_strpos ( $result, 'id="lastOperationStatus" value="OK"' )) {
      return $result;
    }
    return $result;
  }
}
