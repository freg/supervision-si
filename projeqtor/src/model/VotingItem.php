<?php


class VotingItem extends SqlElement
{
    public $id;    // redefine $id to specify its visible place
    public $refType;
    public $refId;
    public $targetValue;
    public $actualValue;
    public $nbVoted;
    public $pctRate;
    public $locked;
    public $_button_vote;
    
    
    private static $_fieldsAttributes=array(
        "id"=>"hidden",
        "name"=>"hidden",
        "targetValue"=>"readonly",
        "actualValue"=>"readonly",
        "pctRate"=>"readonly",
        "nbVoted"=>"readonly",
        "refType"=>"hidden",
        "refId"=>"hidden",
        "locked"=>"hidden",
    );
    
    
    /** ==========================================================================
     * Constructor
     * @param $id Int the id of the object in the database (null if not stored yet)
     * @return void
     */ 
    function __construct($id = NULL, $withoutDependentObjects=false) {
      parent::__construct($id,$withoutDependentObjects);
    }
    
    public function __destruct() {
      parent::__destruct();
    }
    
    public function save() {
      //calculate TargetValue
      if ($this->refType=='TicketSimple') $this->refType='Ticket';
      $old = $this->getOld(true);
      $idUseRule=self::getIdUseRule($this->refType,$this->refId);
      $votingUseRule = new VotingUseRule($idUseRule);
      $itemOrigin = new $this->refType($this->refId);
      $locked = self::isBlockingStatus($votingUseRule->blocking__idStatus, $itemOrigin->idStatus);
      $this->locked = $locked;
      if($votingUseRule->fixValue and $votingUseRule->fixValue != 0){
        $this->targetValue = $votingUseRule->fixValue;
      }else{
        if($this->refType=='Ticket'){
          $item = SqlElement::getSingleSqlElementFromCriteria('WorkElement', array('refType'=>'Ticket','refId'=>$this->refId));
          $this->targetValue =  ceil($item->plannedWork * $votingUseRule->workPointConvertion);
        }elseif($this->refType=='Activity'){
          $activity = new Activity($this->refId);
          $this->targetValue = ceil($activity->ActivityPlanningElement->validatedWork * $votingUseRule->workPointConvertion);
        }elseif($this->refType=='Requirement'){
          $requ = new Requirement($this->refId);
          $this->targetValue = ceil($requ->plannedWork * $votingUseRule->workPointConvertion);
        }elseif($this->refType=='ChangeRequest'){
          $requ = new ChangeRequest($this->refId);
          $this->targetValue = ceil($requ->plannedWork * $votingUseRule->workPointConvertion);
        }
      }
      if($this->id){
        $this->actualValue = 0;
        $this->nbVoted = 0;
        $this->pctRate = 0;
        $voting = new Voting();
        $lstVoting = $voting->getSqlElementsFromCriteria(array('refType'=>$this->refType,'refId'=>$this->refId));
        foreach ($lstVoting as $voteV){
          $this->actualValue += $voteV->value;
          $this->nbVoted +=1;
        }
        if(!$this->targetValue){
          if($this->actualValue and $this->actualValue >0){
            $this->pctRate = 100;
          }
        }else{
          if($this->actualValue and $this->actualValue >0){
            if($this->targetValue){
              $this->pctRate = $this->actualValue * 100 / $this->targetValue;
            }
          }
        }
      }
      $result = parent::save();
      return $result;
    }
    
    
    
    public function drawSpecificItem($item) {
      global $print, $displayWidth,  $printWidth ,$outMode, $preseveHtmlFormatingForPDF;
      $widthPct=setWidthPct($displayWidth, $print, $printWidth, $this);
      $widthPctNote=((intval($widthPct)-2)*0.4)-40;
      if ($item=='vote' and $this->id) {
        $obj = new $this->refType($this->refId);
        if(!$this->locked){
          $voteAttr = new VotingAttribution();
          $typeName=SqlElement::getTypeName($this->refType);
          $idType = $obj->$typeName;
          $canVote = $voteAttr->canVote($this->refType, $this->refId, $idType);
          $voteExist = false;
          $vote = SqlElement::getSingleSqlElementFromCriteria('Voting', array('refType'=>$this->refType,'refId'=>$this->refId,'idUser'=>getCurrentUserId()));
          if($vote->id)$voteExist=true;
          if(!$voteExist){
            $idUser = getCurrentUserId();
            $affectable = new Affectable($idUser);
            if($affectable->isContact){
              $contact = new Contact($idUser);
              if($contact->idClient){
                $vote = SqlElement::getSingleSqlElementFromCriteria('Voting', array('refType'=>$this->refType,'refId'=>$this->refId,'idClient'=>$contact->idClient));
                if($vote->id)$voteExist=true;
              }
            }
          }
          $idRule=self::getIdUseRule($this->refType, $this->refId);
          if($canVote and !$voteExist){
        		echo '<div id="'.$item.'Add" title="' . i18n('addVote') . '" style="padding:2px 2px 0px 0px;" >';
        		echo '<button id="' . $item . 'AddButton" dojoType="dijit.form.Button" style="width:200px;vertical-align: middle;" class="roundedVisibleButton">';
        		echo '<span>' . i18n('addVote') . '</span>';
        		echo '<script type="dojo/connect" event="onClick" args="evt">';
        		echo 'addVote(\''.$this->refType.'\','.$this->refId.',\''.getEditorType().'\',\'add\','.$idRule.',null);';
        		echo '</script>';
        		echo '</button>';
        		echo '</div>';
          }
          if($voteExist){
            echo '<div id="'.$item.'Edit" title="' . i18n('editVote') . '" style="padding:2px 2px 0px 0px;" >';
            echo '<button id="' . $item . 'EditButton" dojoType="dijit.form.Button" style="width:300px;vertical-align: middle;" class="roundedVisibleButton">';
            echo '<span>'. i18n('editVote') .' ('.i18n('colActualValue').' '.htmlDisplayNumericWithoutTrailingZeros($vote->value).')</span>';
            echo '<script type="dojo/connect" event="onClick" args="evt">';
            echo 'addVote(\''.$this->refType.'\','.$this->refId.',\''.getEditorType().'\',\'edit\','.$idRule.',null);';
            echo '</script>';
            echo '</button>';
            echo '</div>';
          }
        }
        $voting = new Voting();
        $voteItemExist = $voting->countSqlElementsFromCriteria(array('refType'=>$this->refType,'refId'=>$this->refId));
      //$canSeeVotes=SqlElement::getSingleSqlElementFromCriteria('HabilitationOther', array('idProfile'=>getSessionUser ()->getProfile ( $obj->idProject ), 'scope'=>'canManageVotes'));
        $viewTable=SqlElement::getSingleSqlElementFromCriteria('HabilitationOther', array('idProfile'=>getSessionUser ()->getProfile ( $obj->idProject ), 'scope'=>'votingPanelDetail'));
        $viewNameInTable=SqlElement::getSingleSqlElementFromCriteria('HabilitationOther', array('idProfile'=>getSessionUser ()->getProfile ( $obj->idProject ), 'scope'=>'nameVoterDetail'));
       
      //if($canSeeVotes->rightAccess==1 and $voteItemExist){
        if($viewTable->rightAccess==1 and $voteItemExist) {
          echo '<table style="margin-top:20px;width:100%;">';
          echo '  <tr>';
          echo '    <td class="linkHeader" style="width:20%">'.i18n('colIdVoter').'</td>';
          echo '    <td class="linkHeader" style="width:20%">'.i18n('colValue').'</td>';
          echo '    <td class="linkHeader" style="width:20%">'.i18n('colIdUser').'</td>';
          echo '    <td class="linkHeader" style="width:20%">'.i18n('colIdClient').'</td>';
          echo '    <td class="linkHeader" style="width:20%">'.i18n('colComment').'</td>';
          echo '  </tr>';
          $lstVote =  $voting->getSqlElementsFromCriteria(array('refType'=>$this->refType,'refId'=>$this->refId));
          foreach ($lstVote as $vote){
            echo '<tr>';
            $idVoter=SqlList::getNameFromId('Affectable', $vote->idVoter);
            $idUser = SqlList::getNameFromId('Affectable', $vote->idUser);
            $idClient = SqlList::getNameFromId('Client', $vote->idClient);

            echo '<td align="center" class="assignData">'.htmlEncode($idVoter).'</td>';
            echo '<td align="center" class="assignData">'.htmlDisplayNumericWithoutTrailingZeros($vote->value).'</td>';
            echo '<td align="center" class="assignData">'.htmlEncode($idUser).'</td>';
            echo '<td align="center" class="assignData">'.htmlEncode($idClient).'</td>';
            echo '<td align="center" class="assignData">';
            
            if ($vote->idNote){
              $strDataHTML = SqlElement::getRefField('Note',$vote->idNote, 'note');
            } else {
              $strDataHTML = "";
            }
            $strDataHTML = pq_str_replace(array('<style','/style>'),array('<nostyle','/nostyle>'),$strDataHTML);            
            if ($print and $outMode=="pdf") {
              if ($strDataHTML) {
                $strDataHTML=preg_replace("/\<([a-zA-Z0-9-]*@[a-zA-Z0-9-]*\.[a-zA-Z0-9-]*)\>/", "&lt;$1&gt;", $strDataHTML);
              }
              if (!$preseveHtmlFormatingForPDF) {
                $strDataHTML=htmlEncode($strDataHTML, 'pdf');
              }
            } else {
              $strDataHTML=preg_replace('@(https?://([-\w\.]<+[-\w])+(:\d+)?(/([\w/_\.#-]*(\?\S+)?[^\.\s])?)?)@','<a href="$1" target="_blank">$1</a>',pq_nvl($strDataHTML));
              if (!$print) {
                $strDataHTML=htmlSetClickableImages($strDataHTML,(intval($widthPctNote)-32).'px');
              }
            }
            if (!$print) echo '<div style="min-height:23px;max-width:'.$widthPctNote.';overflow-x:auto;" >';
            echo $strDataHTML;
            if (!$print) echo '</div>';
            
            echo '</td>';
            echo '</tr>';
          }
          echo '</table>';
        }
          if($viewTable->rightAccess==2) {
            if($viewNameInTable->rightAccess==1 and $voteItemExist){
            echo '</br>';              
            echo '<div class="" style="display: flex; align-items: center;">';
              echo '<div class="">'.i18n('colIdAllVoter').'&nbsp; : &nbsp;</div>';
              $lstVote =  $voting->getSqlElementsFromCriteria(array('refType'=>$this->refType,'refId'=>$this->refId));
             foreach ($lstVote as $vote){
              $idVoter=SqlList::getNameFromId('Affectable', $vote->idVoter);
              echo '<div align="center" class="">'.htmlEncode($idVoter).',&nbsp;</div>';
             }
            echo '<div>';
            
         }
        }
      }
    }
    
    private static $_colCaptionTransposition = array(
    );
    
    
    public function setAttributes() {
//       $voteAttr = new VotingAttribution();
//       $obj = new $this->refType($this->refId);
//       $idType= "id".$this->refType."Type";
//       $idType = $obj->$idType;
//       $canVote = $voteAttr->canVote($this->refType, $this->refId, $idType);
//       if($canVote){
//         self::$_fieldsAttributes['_button_vote']='';
//       }
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
    
    public static function isVotable($refType,$refId,$idType=null) {
      $result = false;
      if(Module::isModuleActive('moduleVoting') and $refId and $refId!=-1){
        $voting = new VotingItem();
        if($refType=='TicketSimple')$refType='Ticket';
        $exist = $voting->countSqlElementsFromCriteria(array('refType'=>$refType,'refId'=>$refId));
        if(!$exist){
          $voting->refId = $refId;
          $voting->refType = $refType;
          $voting->save();
        }
        $idRule = self::getIdUseRule($refType,$refId);
        if($idRule)$result = true;
      }
      return $result;
    }
    
    public static function getIdUseRule($refType,$refId) {
      $result = null;
      $item = new $refType($refId);
      $useRule = new VotingUseRule();
      if (pq_substr($refType,-4)=='Main') {
        $refType=pq_substr($refType,0,-4);
      }
      if($refType=='TicketSimple')$refType='Ticket';
      $typeName=SqlElement::getTypeName($refType);
      //Filter on project + refType + idType
      $useRulePerfect = $item->getSingleSqlElementFromCriteria('VotingUseRule', array('idType'=>$item->$typeName,'idProject'=>$item->idProject));
      if($useRulePerfect->id)$result=$useRulePerfect->id;
      //Filter project + refType
      if(!$result){
        $useRuleNoIdType = $useRule->getSqlElementsFromCriteria(array('idProject'=>$item->idProject,'refType'=>$refType,'idType'=>null));
        foreach ($useRuleNoIdType as $vote){
          if(!$vote->idType){
            $result=$vote->id;
            break;
          }
        }
      }
      //Filter on refType + idType
      if(!$result){
        $useRuleNoProject = $useRule->getSqlElementsFromCriteria(array('idProject'=>null,'idType'=>$item->$typeName,'refType'=>$refType));
        foreach ($useRuleNoProject as $vote){
          if(!$vote->idProject){
            $result=$vote->id;
            break;
          }
        }
      }
      //Filter on refType
      if(!$result){
        $useRuleNoProjectNoIdType = $useRule->getSqlElementsFromCriteria(array('refType'=>$refType,'idProject'=>null,'idType'=>null));
        foreach ($useRuleNoProjectNoIdType as $vote){
          if(!$vote->idType){
            $result=$vote->id;
            break;
          }
        }
      }
      return $result;
    }
    
    public static function getVotableClassList(){
      return array('Ticket', 'Activity', 'Requirement', 'ChangeRequest', 'UserStory');
    }
    
    public static function isVotableClass($itemClass){
      $array= self::getVotableClassList();
      $result = false;
      if(in_array($itemClass,$array)){
        $result = true;
      }
      return $result;
    }
    
    public static function workField($itemClass){
      $result = '';
      if($itemClass=='TicketSimple')$itemClass='Ticket';
      if($itemClass=='Ticket'){
        $result = 'plannedWork';
      }elseif($itemClass=='Activity'){
        $result = 'validatedWork';
      }elseif($itemClass=='Requirement'){
        $result='plannedWork';
      }
      return $result;
    }
    
    public static function isBlockingStatus($idStatusUseRule, $idStatusItem){
      if(!$idStatusUseRule)return 0;
      $result = 0;
      $statusUseRule = new Status($idStatusUseRule);
      $statusItem = new Status($idStatusItem);
      if($statusItem->sortOrder >= $statusUseRule->sortOrder)$result=1;
      return $result;
    }

}