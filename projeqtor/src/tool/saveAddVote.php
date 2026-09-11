<?PHP
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

/** ===========================================================================
 * Get the list of objects, in Json format, to display the grid list
 */
require_once "../tool/projeqtor.php"; 

$mode = RequestHandler::getValue('mode');
$idUser = getSessionUser()->id;
$refType = RequestHandler::getClass('classObj');
$refId = RequestHandler::getId('refId');
$voteSelf = RequestHandler::getValue('voteSelf');
$voteClient = RequestHandler::getValue('voteClient');
$voteNote = pq_trim(RequestHandler::getValue('voteNote'));
$notePrivacyVote = RequestHandler::getValue('notePrivacyVote');
$idVotingAttrUser= RequestHandler::getId('idVotingAttrUser');
$idVotingAttrClient= RequestHandler::getId('idVotingAttrClient');
$idClient = RequestHandler::getId('idClient');
$noteId = null;
$res="";
$result="";
Sql::beginTransaction();
if($mode=='add'){
  //CREATE NOTE
  if($voteNote){
    $note = new Note();
    $note->idUser=$idUser;
    $resource=new Resource($idUser);
    $note->idTeam=$resource->idTeam;
    $note->refId=$refId;
    $note->refType=$refType;
    $note->creationDate=date("Y-m-d H:i:s");
    $note->note=$voteNote;
    if ($notePrivacyVote) {
      $note->idPrivacy=$notePrivacyVote;
    } else if (! $note->idPrivacy) {
      $note->idPrivacy=1;
    }
    $note->save();
    $noteId = $note->id;
  }
  //VOTE CLIENT
  if($voteClient){
    $vote = new Voting();
    $vote->refId = $refId;
    $vote->refType = $refType;
    $vote->idVoter = $idUser;
    $vote->value = $voteClient;
    $vote->idClient = $idClient;
    $vote->idNote = $noteId;
    $res=$vote->save();
  }
  //VOTE USERS
  if($voteSelf){
    $idClient = null;
    $voteC = new Voting();
    $voteC->refId = $refId;
    $voteC->refType = $refType;
    $voteC->idVoter = $idUser;
    $voteC->idUser = $idUser;
    $voteC->value = $voteSelf;
    $voteC->idNote = $noteId;
    $res=$voteC->save();
  }

}else{
  //EDIT
  $voting = new Voting();
  $lstVoting = $voting->getSqlElementsFromCriteria(array('refType'=>$refType,'refId'=>$refId));
  $voteAttrNewValueClient = 0;
  $voteAttrNewValueUser = 0;
  $voteClientDone = false;
  $voteSelfDone = false;
  foreach ($lstVoting as $vote){
    $voteSelfChange = false;
    $voteClientChange = false;
    if(($vote->idUser==$idUser and $vote->idVoter==$idUser) or ($vote->idClient==$idClient and $idClient)){
      //USER
      if($vote->idUser == $idUser and !$vote->idClient){
        if($voteSelf != $vote->value and $voteSelf){
          $voteAttrNewValueUser = abs($voteSelf) - abs($vote->value);
          $vote->value = $voteSelf;
          $voteSelfChange = true;
        }
        $voteSelfDone = true;
        if($voteSelf==0 or !$voteSelf){
          $res=$vote->delete();
          $voteAttrNewValueUser = $voteAttrNewValueUser - abs($vote->value);
          continue;
        }
      }
      
      //CLIENT
      if($vote->idClient == $idClient and $idClient){
        if($voteClient != $vote->value and $voteClient and $voteClient != 0){
          $voteAttrNewValueClient =  abs($voteClient) - abs($vote->value);
          $vote->value=$voteClient;
          $voteClientChange = true;
        }
        $voteClientDone = true;
        if($voteClient==0 or !$voteClient){
          $res=$vote->delete();
          $voteAttrNewValueClient = $voteAttrNewValueClient - abs($vote->value);
          continue;
        }
      }
      //NOTE
      if($vote->idNote){
        $note = new Note($vote->idNote);
        if($voteNote != $note->note){
          $note->note=$voteNote;
          $res=$note->save();
        }
      }else{
        if($voteNote){
          $note = new Note();
          $note->idUser=$idUser;
          $resource=new Resource($idUser);
          $note->idTeam=$resource->idTeam;
          $note->refId=$refId;
          $note->refType=$refType;
          $note->creationDate=date("Y-m-d H:i:s");
          $note->note=$voteNote;
          if ($notePrivacyVote) {
            $note->idPrivacy=$notePrivacyVote;
          } else if (! $note->idPrivacy) {
            $note->idPrivacy=1;
          }
          $res=$note->save();
          $noteId = $note->id;
          $vote->idNote=$noteId;
        }
      }
      //SAVE
        if($voteSelfChange or $voteClientChange){
          $res=$vote->save();
        }
    }
  }
  //create vote USER
  if($voteSelf and !$voteSelfDone){
    $voteU = new Voting();
    $voteU->refId = $refId;
    $voteU->refType = $refType;
    $voteU->idVoter = $idUser;
    $voteU->idUser = $idUser;
    $voteU->value = $voteSelf;
    $voteU->idNote = $noteId;
    $res=$voteU->save();
    $voteAttrNewValueUser = $voteSelf;
  }
  //create vote Client
  if($voteClient and !$voteClientDone){
    $voteC = new Voting();
    $voteC->refId = $refId;
    $voteC->refType = $refType;
    $voteC->idVoter = $idUser;
    $voteC->value = $voteClient;
    $voteC->idUser = null;
    $voteC->idClient = $idClient;
    $voteC->idNote = $noteId;
    $res=$voteC->save();
    $voteAttrNewValueClient = $voteClient;
  }
  
}
if(!$res){
  if($mode=='add'){
    echo '<div class=\'messageNO_CHANGE\' >' .i18n('resultNoChange') . '</div>';
    exit;
  }else{
    $result = $vote->save();
  }
}
if (!$result) {
  $result=$res;
}

// Message of correct saving
displayLastOperationStatus($result);

$status=getLastOperationStatus($result);
if ($status=="OK"){
  //CALCULATE VOTING ITEM
//  $voting = new Voting();
//  $lstVoting = $voting->getSqlElementsFromCriteria(array('refType'=>$refType,'refId'=>$refId));
//   $votingItem->actualValue = 0;
//   foreach ($lstVoting as $voteV){
//     $votingItem->actualValue += $voteV->value;
//   }
//   $targetValue = $votingItem->targetValue;
//   if($targetValue){
//     $votingItem->pctRate = $votingItem->actualValue * 100 / $targetValue;
//   }else{
//     $votingItem->pctRate = 0;
//   }
  $votingItem = SqlElement::getSingleSqlElementFromCriteria('VotingItem', array('refType'=>$refType,'refId'=>$refId));
  $votingItem->save();
  

  //CALCULATE ATTRIBUTION
  //ON USERS
  if($idVotingAttrUser){
    $votingAttrUser = new VotingAttribution($idVotingAttrUser);
    if($mode=='add'){
      if($voteSelf){
        if($votingAttrUser->usedValue){
          $votingAttrUser->usedValue += abs($voteSelf);
        }else{
          $votingAttrUser->usedValue = abs($voteSelf);
        }
      }
    }else{
      if(!$votingAttrUser->usedValue)$votingAttrUser->usedValue=0;
      if($voteSelf==0){
        $votingAttrUser->usedValue -= abs($voteAttrNewValueUser);
      }else{
        $votingAttrUser->usedValue += $voteAttrNewValueUser;
      }
    }
    $votingAttrUser->leftValue = $votingAttrUser->totalValue - $votingAttrUser->usedValue;
    $votingAttrUser->save();
  }
  //ON CLIENTS
  if($idVotingAttrClient){
    $votingAttrClient = new VotingAttribution($idVotingAttrClient);
    if($mode=='add'){
      if($voteClient){
        if($votingAttrClient->usedValue){
          $votingAttrClient->usedValue += abs($voteClient);
        }else{
          $votingAttrClient->usedValue = abs($voteClient);
        }
      }
    }else{
      if(!$votingAttrClient->usedValue)$votingAttrClient->usedValue=0;
      if($voteClient==0){
        $votingAttrClient->usedValue -= abs($voteAttrNewValueClient);
      }else{
        $votingAttrClient->usedValue += $voteAttrNewValueClient;
      }
    }
    $votingAttrClient->leftValue = $votingAttrClient->totalValue - $votingAttrClient->usedValue;
    $votingAttrClient->save();
  }
  
}

?>