<?php


class VotingAttribution extends SqlElement
{
    public $id;    // redefine $id to specify its visible place
    public $idVotingAttributionRule;
    public $idUser;
    public $idClient;
    public $refType;
    public $idProject;
    public $totalValue;
    public $usedValue;
    public $leftValue;
    public $lastAttributionDate;
    public $endAttributionDate;
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
      $result = parent::save();
      return $result;
    }
    
    public function control() {
      $result="";
      //control UNICITY
      $array= array('idUser'=>$this->idUser);
      if($this->idClient)$array= array('idClient'=>$this->idClient);
      $lstVotAttr = $this->getSqlElementsFromCriteria($array);
      $exist = false;
      foreach ($lstVotAttr as $votAttr){
        if($votAttr->id == $this->id)continue;
        if($this->refType == $votAttr->refType){
          if(($this->idProject and !$votAttr->idProject) or (!$this->idProject and $votAttr->idProject) or ($this->idProject == $votAttr->idProject)){
            $exist = true;
            break;
          }
        }
      }
      if($this->idProject){
        if($exist) $result.='<br/>' . i18n('msgCannotAddRuleOnAProjectIfRuleWithAllProject');
      }else{
        if($exist) $result.='<br/>' . i18n('msgCannotAddRuleOnAllProjectIfRuleWithOneProject');
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
    
    public static function getIdVotingAttribution($refType,$refId,$idUser,$idClient = null){
      $result = null;
      $item = new $refType($refId);
      $voteAttr = new VotingAttribution();
      if(!$idClient){
        $array = array('refType'=>$refType,'idUser'=>$idUser);
      }else{
        $array = array('refType'=>$refType,'idClient'=>$idClient);
      }
      $lstVoteAttr = $voteAttr->getSqlElementsFromCriteria($array);
      foreach ($lstVoteAttr as $vote){
        if(!$vote->idProject or $vote->idProject==$item->idProject){
          $result=$vote->id;
          break;
        }
      }
      if(!$result){
        if(!$idClient){
          $array = array('idUser'=>$idUser,'refType'=>null);
        }else{
          $array = array('idClient'=>$idClient,'refType'=>null);
        }
        $lstVoteAttr = $voteAttr->getSqlElementsFromCriteria($array);
        foreach ($lstVoteAttr as $vote){
          if(!$vote->idProject or $vote->idProject==$item->idProject){
            if(!$vote->refType){
              $result=$vote->id;
              break;
            }
          }
        }
      }
      return $result;
    }
    
    public static function canVote($refType, $refId, $idType, $idUser=null){
      $result = false;
      $item = new $refType($refId);
      //if idUser not set, take id of current user
      if(!$idUser)$idUser=getSessionUser()->id;
      $voteAttr = new VotingAttribution();
      $lstVoteAttr = $voteAttr->getSqlElementsFromCriteria(array('idUser'=>$idUser));
      foreach ($lstVoteAttr as $voteAtt){
        if(!$voteAtt->refType or ($voteAtt->refType==$refType)){
          if(!$voteAtt->idProject or ($voteAtt->idProject == $item->idProject))$result=true;
        }
      }
      if(!$result){
        $affectable = new Affectable($idUser);
        if($affectable->isContact){
          $contact = new Contact($idUser);
          if($contact->idClient){
            $lstVoteAttrClient = $voteAttr->getSqlElementsFromCriteria(array('idClient'=>$contact->idClient));
            foreach ($lstVoteAttrClient as $voteAttClient){
              if(!$voteAttClient->refType or ($voteAttClient->refType==$refType)){
                if(!$voteAttClient->idProject or ($voteAttClient->idProject == $item->idProject))$result=true;
              }
            }
          }
        }
      }
      return $result;
    }
    
    public static function votingAttributionPoints($idVotingAttr,$today){
      $vote = new VotingAttribution($idVotingAttr);
      //$lastDate = $vote->lastAttributionDate;
      if(!$vote->lastAttributionDate)$vote->lastAttributionDate=date('Y-m-d');
      $total = $vote->totalValue;
      $voteRule = new VotingAttributionRule($vote->idVotingAttributionRule);
      if($voteRule->fixValue)return;
      $lastAttr = new DateTime($vote->lastAttributionDate);
      $today = new DateTime(date('Y-m-d'));
      $interval = $lastAttr->diff($today);
      if($voteRule->weeklyValue){
//         $origin = new DateTime($lastDate);
//         $target = new DateTime($today);
//         $interval = $origin->diff($target);
//         $nbDay =floatval($interval->format('%a days'));
//         if($nbDay >= 1){
//           $total += floor($nbDay/7)*$voteRule->weeklyValue;
//         }
        $nbWeeks=floor($interval->format('%d')/7);
        $total += $nbWeeks*$voteRule->weeklyValue;
        if(addDaysToDate($vote->lastAttributionDate,$nbWeeks*7) > $vote->endAttributionDate)return;
        $vote->lastAttributionDate=addDaysToDate($vote->lastAttributionDate,$nbWeeks*7);
      }elseif ($voteRule->monthlyValue){
//         $lastAttr = new DateTime($vote->lastAttributionDate);
//         $lastMonth = $lastAttr->format('m');
//         $lastYear = $lastAttr->format('y');
//         if($lastYear != date('y')){
//           $nbYear = floatval(date('y')-$lastYear);
//           $nbMonth =floatval( abs($lastMonth-12)+date('m'));
//           if($nbYear>1)$nbMonth+= ($nbYear-1)*12;
//         }else{
//           $nbMonth = floatval(date('m'))- $lastMonth;
//         }
//         if($nbMonth >= 1){
//           $total += $nbMonth*$voteRule->monthlyValue;
//         }
        $nbMonths= $interval->format('%m');
        $total += $nbMonths*$voteRule->monthlyValue;
        if(addMonthsToDate($vote->lastAttributionDate,$nbMonths) > $vote->endAttributionDate)return;
        $vote->lastAttributionDate=addMonthsToDate($vote->lastAttributionDate,$nbMonths);
      }elseif ($voteRule->yearlyValue){
//         $origin = new DateTime($lastDate);
//         $target = new DateTime($today);
//         $interval = $origin->diff($target);
//         $nbYear = $interval->format('%y years');
//         if($nbYear > 0){
//           $total = $nbYear*$voteRule->yearlyValue;
//         }
        $nbYears= $interval->format('%y');
        $total += $nbYears*$voteRule->yearlyValue;
        if(addMonthsToDate(addMonthsToDate($vote->lastAttributionDate,$nbYears*12)) > $vote->endAttributionDate)return;
        $vote->lastAttributionDate=addMonthsToDate($vote->lastAttributionDate,$nbYears*12);
      }elseif ($voteRule->dailyValue){
//         $origin = new DateTime($lastDate);
//         $target = new DateTime($today);
//         $interval = $origin->diff($target);
//         $nbDay = floatval($interval->format('%a days'));
//         if($nbDay >= 1){
//           $total += $nbDay*($voteRule->dailyValue);
//         }
        $nbDays=$interval->format('%d');
        $total += $nbDays*$voteRule->dailyValue;
        if(addDaysToDate($vote->lastAttributionDate,$nbDays) > $vote->endAttributionDate)return;
        $vote->lastAttributionDate=addDaysToDate($vote->lastAttributionDate,$nbDays);
      }
//       if($total != $vote->totalValue){
//         $vote->lastAttributionDate = $today;
//       }
      if($voteRule->limitValue){
        $totalAndUse = $total -  $vote->usedValue;
        if($totalAndUse > $voteRule->limitValue) $total = $voteRule->limitValue + $vote->usedValue;
      }
      $vote->totalValue = $total;
      $vote->leftValue = $total - $vote->usedValue;
      $vote->save();
    }
    
    
    static function drawVotingFollowUpAttributionRules($idUser){
      //CLIENT
      $lstClient = array();
      $voteAttrClient = new VotingAttribution();
      $affectable = new Affectable($idUser);
      if($affectable->isContact){
        $contact = new Contact($idUser);
        if($contact->idClient){
          $lstClient = $voteAttrClient->getSqlElementsFromCriteria(array('idClient'=>$contact->idClient));
        }      
      }
      //USER
      $voteAttrUser = new VotingAttribution();
      $lstUser = $voteAttrUser->getSqlElementsFromCriteria(array('idClient'=>null,'idUser'=>$idUser));
      
      $result = "";
      //Header
      $result .='<div id="votingAttributionDiv" align="center" style="margin-top:20px;margin-bottom:20px;overflow-y:auto; width:97%;">';
      $result .='<table width="90%" style="margin-left:20px;margin-right:20px;border: 1px solid grey;">';
      $result .='   <tr class="reportHeader">';
      $result .='     <td style="border: 1px solid grey;border-right: 1px solid white;height:40px;width:30%;text-align:center;vertical-align:center;">'.ucfirst(i18n('VotingAttributionRule')).'</td>';
      $result .='     <td style="border: 1px solid grey;border-right: 1px solid white;height:40px;width:20%;text-align:center;vertical-align:center;">'.ucfirst(i18n('colElement')).'</td>';
      $result .='     <td style="border: 1px solid grey;border-right: 1px solid white;height:40px;width:20%;text-align:center;vertical-align:center;">'.ucfirst(i18n('Project')).'</td>';
      $result .='     <td style="border: 1px solid grey;border-right: 1px solid white;height:40px;width:10%;text-align:center;vertical-align:center;">'.ucfirst(i18n('colCountTotal')).'</td>';
      $result .='     <td style="border: 1px solid grey;border-right: 1px solid white;height:40px;width:10%;text-align:center;vertical-align:center;">'.ucfirst(i18n('used')).'</td>';
      $result .='     <td style="border: 1px solid grey;height:40px;width:10%;text-align:center;vertical-align:center;">'.ucfirst(i18n('colLeft')).'</td>';
      $result .='   </tr>';
      //USER
      foreach ($lstUser as $voteUser){
        $usedValue = (!$voteUser->usedValue)?0:$voteUser->usedValue;
        $result .='   <tr class="" style="height:25px;"><td style="border:1px solid grey;" align="center">';
        $result .='<table><tr><td align="left">'.formatIcon('User', 22).'</td>';
        $result .='    <td align="right">&nbsp;'.SqlList::getNameFromId('VotingAttributionRule', $voteUser->idVotingAttributionRule).'</td>';
        $result .='</tr></table></td>';
        $result .='    <td align="center" style="border:1px solid grey;">&nbsp;'.$voteUser->refType.'</td>';
        $result .='    <td align="center" style="border:1px solid grey;">&nbsp;'.SqlList::getNameFromId('Project', $voteUser->idProject).'</td>';
        $result .='    <td align="center" style="border:1px solid grey;">&nbsp;'.$voteUser->totalValue.'</td>';
        $result .='    <td align="center" style="border:1px solid grey;">&nbsp;'.$usedValue.'</td>';
        $result .='    <td align="center" style="border:1px solid grey;">&nbsp;'.$voteUser->leftValue.'</td>';
        $result .='   </tr>';
      }
      //CLIENT
      foreach ($lstClient as $voteClient){
        $usedValue = (!$voteClient->usedValue)?0:$voteClient->usedValue;
        $result .='   <tr class="" style="height:25px;"><td style="border:1px solid grey;" align="center">';
        $result .='     <table><tr><td align="left">'.formatIcon('Client', 22).'</td>';
        $result .='       <td align="right">&nbsp;'.SqlList::getNameFromId('VotingAttributionRule', $voteClient->idVotingAttributionRule).'</td>';
        $result .='     </tr></table></td>';
        $result .='    <td align="center" style="border:1px solid grey;">&nbsp;'.$voteClient->refType.'</td>';
        $result .='    <td align="center" style="border:1px solid grey;">&nbsp;'.SqlList::getNameFromId('Project', $voteClient->idProject).'</td>';
        $result .='    <td align="center" style="border:1px solid grey;">&nbsp;'.$voteClient->totalValue.'</td>';
        $result .='    <td align="center" style="border:1px solid grey;">&nbsp;'.$usedValue.'</td>';
        $result .='    <td align="center" style="border:1px solid grey;">&nbsp;'.$voteClient->leftValue.'</td>';
        $result .='   </tr>';
      }
      $result .='</table>';
      $result .='</div>';
    	echo $result;
    }
    
    static function drawVotingFollowUpItems($idUser,$element,$status,$sorting,$showIdle, $limit){
      $i=1;
      $canSeeVotes=SqlElement::getSingleSqlElementFromCriteria('HabilitationOther', array('idProfile'=>getSessionUser()->idProfile, 'scope'=>'canManageVotes'));
      //$visibleProjectArray = getVisibleProjectsList();
      $votingItem = new VotingItem();
      $orderBy ='';
      $listAll = false;
      if($sorting=='class'){
        $orderBy=" refType DESC, refId ASC";
      }elseif($sorting=='pct'){
        $orderBy=" pctRate DESC";
      }elseif($sorting=='value'){
        $orderBy=" actualValue DESC";
      }
      $lock = false;
      if ($status=='notLock'){
        $lock = 'notLock';
      }elseif ($status=='lock'){
        $lock = 1;
      }
      $whereClause=" 1=1 ";
      $element=pq_trim($element);
      if($element){
        $whereClause.=" and refType=".Sql::str($element);
      }
      if($lock){
        if($lock=='notLock')$lock='0';
        $whereClause.=" and locked=".(($lock)?1:0); 
      }
      $tkt=new Ticket(); $tktTable=$tkt->getDatabaseTableName();
      $act=new Activity(); $actTable=$act->getDatabaseTableName();
      $req=new Requirement(); $reqTable=$req->getDatabaseTableName();
      $chr=new ChangeRequest(); $chrTable=$chr->getDatabaseTableName();
      $ust=new UserStory(); $ustTable=$ust->getDatabaseTableName();
      $idleClause=$showIdle?"":" and idle=0";
      $whereClause.= " and ( (refType='Ticket' and refId in (select id from $tktTable where idProject in " . getVisibleProjectsList(true) . " $idleClause) )" ;
      $whereClause.= "   or (refType='Activity' and refId in (select id from $actTable where idProject in " . getVisibleProjectsList(true) . " $idleClause) )" ;
      $whereClause.= "   or (refType='ChangeRequest' and refId in (select id from $chrTable where idProject in " . getVisibleProjectsList(true) . " $idleClause) )" ;
      $whereClause.= "   or (refType='Requirement' and refId in (select id from $reqTable where idProject in " . getVisibleProjectsList(true) . " $idleClause) ) )" ;
      $whereClause.= "   or (refType='UserStory' and refId in (select id from $ustTable where idProject in " . getVisibleProjectsList(true) . " $idleClause) )" ;
      $lstVoting=$votingItem->getSqlElementsFromCriteria(null,false,$whereClause,$orderBy,false, true, $limit);
      
      $result = "";
      $result .='<div id="drawVotingAttributionFollowUp2" align="center" style="border-top:solid 3px grey;margin-top:40px;margin-bottom:20px;overflow-y:auto; width:97%;">';
      $result .=' <table width="95%" style="margin-top:30px;margin-left:20px;margin-right:20px;border: 1px solid grey;">';
      $result .='   <tr class="reportHeader">';
      $result .='     <td style="border: 1px solid grey;border-right: 1px solid white;height:40px;width:15%;text-align:center;vertical-align:center;" colspan="2">'.ucfirst(i18n('colElement')).'</td>';
      //$result .='     <td style="border: 1px solid grey;border-right: 1px solid white;height:40px;width:5%;text-align:center;vertical-align:center;">'.ucfirst(i18n('colId')).'</td>';
      $result .='     <td style="border: 1px solid grey;border-right: 1px solid white;height:40px;width:37%;text-align:center;vertical-align:center;">'.ucfirst(i18n('colName')).'</td>';
      $result .='     <td style="border: 1px solid grey;border-right: 1px solid white;height:40px;width:7%;text-align:center;vertical-align:center;">'.ucfirst(i18n('Status')).'</td>';
      $result .='     <td style="border: 1px solid grey;border-right: 1px solid white;height:40px;width:11%;text-align:center;vertical-align:center;">'.ucfirst(i18n('colTargetVersion')).'</td>';
      $result .='     <td style="border: 1px solid grey;border-right: 1px solid white;height:40px;width:5%;text-align:center;vertical-align:center;">'.ucfirst(i18n('colDescription')).'</td>';
      $result .='     <td style="border: 1px solid grey;border-right: 1px solid white;height:40px;width:5%;text-align:center;vertical-align:center;">'.ucfirst(i18n('colNote')).'</td>';
      $result .='     <td style="border: 1px solid grey;border-right: 1px solid white;height:40px;width:5%;text-align:center;vertical-align:center;">'.ucfirst(i18n('colTargetValue')).'</td>';
      $result .='     <td style="border: 1px solid grey;border-right: 1px solid white;height:40px;width:5%;text-align:center;vertical-align:center;">'.ucfirst(i18n('colActualValue')).'</td>';
      $result .='     <td style="border: 1px solid grey;height:40px;width:5%;text-align:center;vertical-align:center;">'.ucfirst(i18n('colPct')).'</td>';
      if($canSeeVotes->rightAccess==1){
        $result .='     <td style="border: 1px solid grey;height:40px;width:5%;text-align:center;vertical-align:center;">'.ucfirst(i18n('colAllVote')).'</td>';
      }
      $result .='   </tr>';
      $note=new Note();
      $cptNotes=$note->countGroupedSqlElementsFromCriteria(null, array("refType","refId"), "refType in ('Ticket', 'Activity', 'Requirement', 'UserStory')");
      foreach ($lstVoting as $vote){
        $i++;
        //$object = new $vote->refType($vote->refId);
        //if (securityGetAccessRightYesNo('menu'.$vote->refType, 'read', $object, getSessionUser()) != "YES") continue;
        $nbNotes=(isset($cptNotes[$vote->refType.'|'.$vote->refId]))?$cptNotes[$vote->refType.'|'.$vote->refId]:0;
        $badge= '<div id="VoteBadge_'.$vote->refType.$vote->refId.'" class="kanbanBadge" style="">'.$nbNotes.'</div>';
        $type = 'status';
        $divNote = '<div id="badges" style="position:relative;top:-8px;left:0px">
                      <div id="addComent" onclick="voteAddNote(' . $vote->refId . ', \'' . $vote->refType . '\');" style="position:relative;width:15px;margin-bottom:2px;margin-right:8px;margin-top:2px;" title=" ' . i18n ( 'addNote' ) . ' ">
                        ' . formatSmallButton ( 'AddComment' ) . '
                        <div  style="pointer-events: none;position:absolute;left:-5px;top:3px">
                         '.(($nbNotes!=0)?$badge:'').'
                        </div>
                      </div>
                     </div> ';
        $divDescription = '<div style="position:relative">';
        $divDescription .='<button id="'.$i.'showDetailDiv" dojoType="dijit.form.Button" showlabel="false"
                                   title="'.i18n('showDetail').'" 
                                   iconClass="iconSearch22 iconSearch iconSize22 imageColorNewGui" class="notButton notButtonRounded">';
        $divDescription .='<script type="dojo/connect" event="onClick" args="evt">
                            showDetail( \'description\',0,\''.htmlEncode($vote->refType).'\',false,'.htmlEncode($vote->refId).',true);
                          </script>';
        $divDescription .='</button>';
        $divDescription .='</div>';
        if($canSeeVotes){
          $divCanSeeVote = '<div style="position:relative">';
          $divCanSeeVote .='<button id="'.$i.'seeVote" dojoType="dijit.form.Button" showlabel="false"
                                   title="'.i18n('seeVote').'"
                                   iconClass="iconVoting22  iconVoting  iconSize22 imageColorNewGui" class="notButton notButtonRounded">';
          $divCanSeeVote .='<script type="dojo/connect" event="onClick" args="evt">';
          $page="../view/seeAllVote.php?id=".$vote->refId."&refType=".$vote->refType; 
          $divCanSeeVote.="var url='$page';";
          $divCanSeeVote.='showPrint(url, "asset", null, "html", "P");
                            </script>';
          $divCanSeeVote .='</button>';
          $divCanSeeVote .='</div>';
          
          
        }
        $goto='';
        if (securityCheckDisplayMenu(null, $vote->refType)) {
          $goto=' onClick="gotoElement(\''.$vote->refType.'\',\''.htmlEncode($vote->refId).'\');" ';
        }
        $idStatus = SqlList::getFieldFromId($vote->refType, $vote->refId, 'idStatus');
        $idTargetProductVersion = SqlList::getFieldFromId($vote->refType, $vote->refId, 'idTargetProductVersion');
        $colorStatus = SqlList::getFieldFromId('Status', $idStatus, 'color');
        $pctRate = (!$vote->pctRate)?0:$vote->pctRate;
        $actualValue = (!$vote->actualValue)?0:$vote->actualValue;
        $targetValue = (!$vote->targetValue)?0:$vote->targetValue;
        // if (! $vote->actualValue and $vote->targetValue and ! $pctRate) $pctRate=100; // If done here, sort will be incorrect, must be done when calculating rate
        $result .='   <tr class="">';
        $result .='    <td '.$goto.' class="assignData hyperlink '.((isNewGui() and isset($goto) and $goto!='')?'classLinkName':'').'" align="center" style="width:9%;vertical-align:inherit !important;border:1px solid grey;">&nbsp;'.$vote->refType.'</td>';
        $result .='    <td '.$goto.' class="assignData hyperlink '.((isNewGui() and isset($goto) and $goto!='')?'classLinkName':'').'" align="center" style="width:6%;vertical-align:inherit !important;border:1px solid grey;">&nbsp;#'.$vote->refId.'</td>';
        $result .='    <td class="assignData" align="center" style="vertical-align:middle; text-align:left;border:1px solid grey;">&nbsp;'.SqlList::getNameFromId($vote->refType, $vote->refId).'</td>';
        $result .='    <td class="assignData" align="center" style="vertical-align:middle; text-align:center;border:1px solid grey;color: ' . getForeColor($colorStatus) . ';background-color: ' . $colorStatus . '">&nbsp;'.SqlList::getNameFromId('Status', $idStatus).'</td>';
        $result .='    <td class="assignData" align="center" style="vertical-align:middle; text-align:left;border:1px solid grey;">&nbsp;'.SqlList::getNameFromId('Version', $idTargetProductVersion).'</td>';
        $result .='    <td align="center" style="border:1px solid grey;">'.$divDescription.'</td>';
        $result .='    <td align="center" style="border:1px solid grey;">&nbsp;'.$divNote.'</td>';
        $result .='    <td align="center" style="border:1px solid grey;">&nbsp;'.$targetValue.'</td>';
        $result .='    <td align="center" style="border:1px solid grey;">&nbsp;'.$actualValue.'</td>';
        $result .='    <td align="center" style="border:1px solid grey;">&nbsp;'.$pctRate.'%</td>';
        if($canSeeVotes->rightAccess==1){
          $result .='    <td align="center" style="border:1px solid grey;">'.$divCanSeeVote.'</td>';
        }
        $result .='   </tr>';
      }
      $result .=' </table>';
      $result .='</div>';
      echo $result;
    }
    
    public static  function drawVotingAttributionFollowUpGlobal($idRes,$idClient,$element=false,$left=false){
      
      $lst = array();
      $voteAttr = new VotingAttribution();
      $idClient=($idClient==0)?false:$idClient;
      if($idRes){ //========================= if User is Select
        $affectable = new Affectable($idRes);
        $where="idUser = $idRes";
        if($affectable->isContact){
          $contact=new Contact($idRes);
          if($contact->idClient!=""){
            $lstContatc[$idRes]=$contact->idClient;
            $where=" (idUser = $idRes or idClient=$contact->idClient)";
          }
        }
        if($element)$where.=" and refType='$element'";
        if(!$left)$where .=" and leftValue > 0";
        $lst=$voteAttr->getSqlElementsFromCriteria(null,false,$where,' -idClient desc,idUser asc, idVotingAttributionRule asc, idProject asc,refType asc ');

      }else if(!$idClient) { //========================= if no User and no Client are Select
        $where='1=1';
        $whereContact=' idClient is not null';
        if($element){
          $where.=" and refType='$element'";
          $whereContact.=" and refType='$element'";
        }
        if(!$left){
          $where .=" and leftValue > 0";
           $whereContact .=" and leftValue > 0";
        }
        $lst=$voteAttr->getSqlElementsFromCriteria(null,false,$where,' -idClient desc,idUser asc, idVotingAttributionRule asc, idProject asc,refType asc ');
        $allClient=$voteAttr->getSqlElementsFromCriteria(null,false,$where,'idClient asc');
        $contact= new Contact();
        foreach ($allClient as $attrClient){
          $idC=$attrClient->idClient;
          $lstContactClien=$contact->getSqlElementsFromCriteria(array('idClient'=>$idC,'isUser'=>1),false,null,'isUser asc');
          foreach ($lstContactClien as $c){
             $lstContatc[$c->id]=$idC;
          }
        }
        
      }else{ //========================= if Client is Select
        $lsIdC="";
        $client=new Client();
        $where="idClient = $idClient";
        $contact= new Contact();
        $lstContactClien=$contact->getSqlElementsFromCriteria(array('idClient'=>$idClient,'isUser'=>1),false,null,'isUser asc');
        foreach ($lstContactClien as $c){
          $lsIdC.=($lsIdC=="")?$c->id:",".$c->id;
          $lstContatc[$c->id]=$idClient;
        }
        if($lsIdC!="")$where="(idClient = $idClient or idUser in ($lsIdC) )";
        if($element)$where.=" and refType='$element'";
        if($left)$where .=" and leftValue > 0";
        $lst = $voteAttr->getSqlElementsFromCriteria(null,false,$where,'-idClient desc ,idUser asc, idVotingAttributionRule asc, idProject asc,refType asc ');
      }
      
      

      $result = "";
      $result .='<div id="drawVotingAttributionFollowUp2" align="center" style="margin-top:40px;margin-bottom:20px;overflow-y:auto; width:97%;">';
      $result .=' <table width="95%" style="margin-top:30px;margin-left:20px;margin-right:20px;">';
      $result .='   <tr class="reportHeader">';
      $result .='     <td style="border: 1px solid grey;border-right: 1px solid white;height:40px;width:15%;text-align:center;vertical-align:center;">'.ucfirst(i18n('colIdUser')).'</td>';
      $result .='     <td style="border: 1px solid grey;border-right: 1px solid white;height:40px;width:15%;text-align:center;vertical-align:center;">'.ucfirst(i18n('colIdClient')).'</td>';
      $result .='     <td style="border: 1px solid grey;border-right: 1px solid white;height:40px;width:15%;text-align:center;vertical-align:center;">'.ucfirst(i18n('VotingAttributionRule')).'</td>';
      $result .='     <td style="border: 1px solid grey;border-right: 1px solid white;height:40px;width:4%;text-align:center;vertical-align:center;">'.ucfirst(i18n('colElement')).'</td>';
      $result .='     <td style="border: 1px solid grey;border-right: 1px solid white;height:40px;width:15%;text-align:center;vertical-align:center;">'.ucfirst(i18n('colIdProject')).'</td>';
      $result .='     <td style="border: 1px solid grey;border-right: 1px solid white;height:40px;width:5%;text-align:center;vertical-align:center;">'.ucfirst(i18n('colCountTotal')).'</td>';
      $result .='     <td style="border: 1px solid grey;border-right: 1px solid white;height:40px;width:5%;text-align:center;vertical-align:center;">'.ucfirst(i18n('used')).'</td>';
      $result .='     <td style="border: 1px solid grey;border-right: 1px solid white;height:40px;width:5%;text-align:center;vertical-align:center;">'.ucfirst(i18n('colLeft')).'</td>';
      $result .='   </tr>';
      
      //================================initialization val=============================//
      $firstUser=false;
      $firstClient=false;
      $lastidUser="";
      $lastidClient="";
      $idRule="";
      $idProj="0";
      $nameUser="";
      $nameRule="";
      $el="";
      $proj="";
      $userchange=false;
      $ruleChange=false;
      $elChange=false;
      $cpUser=1;
      $cpRule=1;
      $cpEl=1;
      $cpProj=1;
      $cpClient=1;
      $onclickUser="";
      $onclickRule="";
      $onclickProj="";
      $classUser="";
      $classClient="";
      $classRule="";
      $classProj="";
      $rightReadUser=securityGetAccessRightYesNo('menuUser','read');
      $rightReadRule=securityGetAccessRightYesNo('menuVotingAttributionRule','read');
      $rightReadProject=securityGetAccessRightYesNo('menuProject','read');
      $rightReadClient=securityGetAccessRight('menuClient', 'read');
      //=============================================================//
      if(!empty($lst)){
        foreach ($lst as $attr){
          $isClient=($attr->idClient)?true:false;
          $changeUser=false;
          $changeClient=false;
          $clientName='';
          //=============================================Info Client=================================================//
          if(($lastidClient!=$attr->idClient and $idClient=="" ) or ($idClient!="" and $lastidClient!=$idClient ) and $isClient){
            if(!$firstClient){
              $firstClient=true;
              $changeClient=true;
            }
            
            if($lastidClient!=""){
              $result=pq_str_replace('rawspanClient', $cpClient, $result);
              $result=pq_str_replace('rawspanClient', $cpClient, $result);
            }
            
            if ( securityCheckDisplayMenu(null, 'Client') and $rightReadUser=="YES") {
              $onclickClient=' onClick="gotoElement(\'Client\',\''.htmlEncode($lastidClient).'\');" ';
              $styleClient='cursor: pointer;';
              $classClient='classLinkName';
            }else{
              $onclickClient="";
            }
            $lastidClient=$attr->idClient;
            
            $nameUser="";
            $clientName=SqlList::getNameFromId('Client', $attr->idClient);
            $cpClient=1;
            $clientChange=true;
          }else{
            $clientChange=false;
            $cpClient++;
          }
          //=============================================================================================//
          //================================================info User==============================================//
          
          if(($lastidUser!=$attr->idUser and $idRes=="") or ($idRes!="" and $lastidUser!=$idRes ) and !$isClient ) {
            if(!$firstUser){
              $firstUser=true;
              $changeUser=true;
            }
            if($lastidUser!=""){
              $result=pq_str_replace('rawspanUser', $cpUser, $result);
            }
            if ( securityCheckDisplayMenu(null, 'User') and $rightReadUser=="YES") {
              $onclickUser=' onClick="gotoElement(\'User\',\''.htmlEncode($lastidUser).'\');" ';
              $styleUser='cursor: pointer;';
              $classUser='classLinkName';
            }else{
              $onclickUser="";
            }
          
            $lastidUser=$attr->idUser;
            if(isset($lstContatc) and isset($lstContatc[$lastidUser])){
              $clientName=SqlList::getNameFromId('Client', $lstContatc[$lastidUser]);
            }
          
            $nameUser=SqlList::getNameFromId('Affectable', $attr->idUser);
            $cpUser=1;
            $userchange=true;
          }else{
            $userchange=false;
            $cpUser++;
          }
          
          if($changeClient or $changeUser){
            $result .='   <tr style="border:unset;" ><td colspan="8" style="border:unset;height:20px;"></td></tr>';
            $result.='    <tr class="linkHeader" ><td colspan="8" style="border:unset;height:20px;text-align:center;">'.(($changeClient)?i18n('colIdClient'):i18n('colIdUser')).'</td></tr>';
          }
          //=============================================================================================//
          
          //===================================================info Rule==========================================//
          if($idRule!=$attr->idVotingAttributionRule or $userchange or $clientChange){
            $idRule=$attr->idVotingAttributionRule;
            if ( securityCheckDisplayMenu(null, 'VotingAttributionRule') and $rightReadRule=="YES") {
              $onclickRule=' onClick="gotoElement(\'VotingAttributionRule\',\''.htmlEncode($idRule).'\');" ';
              $styleRule='cursor: pointer;';
              $classRule='classLinkName';
            }else{
              $onclickRule="";
            }
            $nameRule=SqlList::getNameFromId('VotingAttributionRule', $attr->idVotingAttributionRule);
            $result=pq_str_replace('rawspanRule', $cpRule, $result);
            $cpRule=1;
            $ruleChange=true;
          }else{
            $ruleChange=false;
            $cpRule++;
          }
          //=============================================================================================//
          //======================================================info Element=======================================//
          
          if($el!=$attr->refType or $ruleChange){
            $el=$attr->refType;
            $result=pq_str_replace('rawspanEl', $cpEl, $result);
            $cpEl=1;
            $elChange=true;
          }else{
            $elChange=false;
            $cpEl++;
          }
          //===================================================info Project==========================================//
          //=============================================================================================//
          if($idProj!=$attr->idProject or $elChange){
            $idProj=$attr->idProject;
            if ( securityCheckDisplayMenu(null, 'Project') and $rightReadProject=="YES") {
              $onclickProj=' onClick="gotoElement(\'Project\',\''.htmlEncode($idProj).'\');" ';
              $styleProj='cursor: pointer;';
              $classProj='classLinkName';
            }else{
              $onclickProj="";
            }
            $proj=SqlList::getNameFromId('Project', $attr->idProject);
            $result=pq_str_replace('rawspanProj', $cpProj, $result);
            $cpProj=1;
          }else{
            $cpProj++;
          }
          
          $totalVal=($attr->totalValue!='')?$attr->totalValue:0;
          $usedVal=($attr->usedValue!='')?$attr->usedValue:0;
          $leftVal=($attr->leftValue!='')?$attr->leftValue:0;
          
          //=============================================================================================//
          
          $result .='   <tr class="">';
          if($cpClient==1 and $isClient){
            $result .='<td style="border:1px solid grey;height:40px;text-align:center;vertical-align:center;" id="us" rowspan="rawspanClient" >'.$nameUser.'</td>';
            $result .='<td style="border:1px solid grey;height:40px;text-align:center;vertical-align:center;"  rowspan="rawspanClient" '.$onclickClient.'>';
            $result .='<div class="'.$classClient.'" style="'.(($onclickClient!="")?$styleClient:'').'"> '.$clientName.'</div></td>';
          }
          if($cpUser==1 and !$isClient){
            $result .='<td style="border:1px solid grey;height:40px;text-align:center;vertical-align:center;" id="us" rowspan="rawspanUser" '.$onclickUser.'>';
            $result.='<div class="'.$classUser.'" style="'.(($onclickUser!="")?$styleUser:'').'">'.$nameUser.'</div></td>';
            $result .='<td style="border:1px solid grey;height:40px;text-align:center;vertical-align:center;font-style: italic;color:grey;"  rowspan="rawspanUser" >'.$clientName.'</td>';
          }
          if($cpRule==1){
            $result .=' <td style="border:1px solid grey;height:40px;text-align:center;vertical-align:center;" id="ru" rowspan="rawspanRule" '.$onclickRule.'>';
            $result.='<div class="'.$classRule.'" style="'.(($onclickRule!="")?$styleRule:'').'">'.$nameRule.'</div></td>';
          }
          if($cpEl==1)$result .=' <td style="border:1px solid grey;height:40px;text-align:center;vertical-align:center;" id="el" rowspan="rawspanEl">'.$el.'</td>';
          if($cpProj==1){
            $result .=' <td style="border:1px solid grey;height:40px;text-align:center;vertical-align:center;" id="pr"  rowspan="rawspanProj" '.$onclickProj.'>';
            $result.='<div class="'.$classProj.'" style="'.(($onclickProj!="")?$styleProj:'').'">'.$proj.'</div></td>';
          }
          $result .='     <td style="border:1px solid grey;height:40px;text-align:center;vertical-align:center;">'.$totalVal.'</td>';
          $result .='     <td style="border:1px solid grey;height:40px;text-align:center;vertical-align:center;">'.$usedVal.'</td>';
          $result .='     <td style="border:1px solid grey;height:40px;text-align:center;vertical-align:center;">'.$leftVal.'</td>';
          $result .='   </tr>';
        }
      }else{
        $result .='   <tr>';
        $result .='   <tr style="border:unset;" ><td colspan="8" style="border:unset;height:20px;"></td></tr>';
        $result .= '    <td colspan="8">';
        $result .= '    <div style="background:#FFDDDD;font-size:150%;color:#808080;text-align:center;padding:15px 0px;width:100%;height:45px;">'.i18n('noDataFound').'</div>';
        $result .= '    </td>';
        $result .='   </tr>';
      }

      
      $result=pq_str_replace('rawspanUser', $cpUser, $result);
      $result=pq_str_replace('rawspanRule', $cpRule, $result);
      $result=pq_str_replace('rawspanEl', $cpEl, $result);
      $result=pq_str_replace('rawspanProj', $cpProj, $result);

      $result .=' </table>';
      $result .='</div>';
      echo $result;
    }
}