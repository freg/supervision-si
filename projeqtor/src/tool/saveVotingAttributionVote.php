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
$votingRule=RequestHandler::getId('attributionVoteRule');
$element=pq_ltrim(RequestHandler::getValue('attributionVoteElement'));
$idProject=pq_ltrim(RequestHandler::getId('attributionVoteProject'));
$total=RequestHandler::getValue('attributionVoteTotal');
$used=RequestHandler::getValue('attributionVoteUsed');
$left=RequestHandler::getValue('attributionVoteLeft');
$date=RequestHandler::getValue('attributionVoteDate');
$endDate=RequestHandler::getValue('endAttributionDate');
$class = RequestHandler::getClass('classObj');
$idResource = RequestHandler::getId('idResource');
$idAttributionVote = RequestHandler::getId('idAttributionVote');

Sql::beginTransaction();
$result="";
if(!$mode){
  $voteAttr = new VotingAttribution();
  $voteAttr->idVotingAttributionRule = $votingRule;
  $voteAttr->refType=$element;
  $voteAttr->idProject=$idProject;
  $voteRule = new VotingAttributionRule($votingRule);
  if($voteRule->limitValue){
    if($voteRule->limitValue < $total) $total = $voteRule->limitValue;
  }
  //if($voteRule->fixValue){
    $voteAttr->totalValue = $total;
    $voteAttr->leftValue = $total;
    $voteAttr->usedValue = 0;
    $voteAttr->lastAttributionDate = date('Y-m-d');
    $voteAttr->endAttributionDate = $endDate;
  //}
  if($class=='User')$voteAttr->idUser= $idResource;
  if($class=='Client')$voteAttr->idClient = $idResource;
  $res=$voteAttr->save();
}elseif($mode=='delete'){
  $voteAttr = new VotingAttribution($idAttributionVote);
  $res=$voteAttr->delete();
}elseif($mode=='edit'){
  $voteAttrEdit = new VotingAttribution($idAttributionVote);
  $voteAttrEdit->idVotingAttributionRule = $votingRule;
  $voteAttrEdit->refType=$element;
  $voteAttrEdit->idProject=$idProject;
  $voteRule = new VotingAttributionRule($votingRule);
  //if($voteRule->fixValue){
    if($voteRule->limitValue){
      if($voteRule->limitValue < $total) $total = $voteRule->limitValue;
    }
    $voteAttrEdit->totalValue = $total;
    if($voteRule->fixValue){
      $voteAttrEdit->usedValue = 0;
    }
    $voteAttrEdit->leftValue = $total - $voteAttrEdit->usedValue;
    if (! $voteAttrEdit->lastAttributionDate) $voteAttrEdit->lastAttributionDate = date('Y-m-d');
    $voteAttrEdit->endAttributionDate = $endDate;
  //}
  if($class=='User')$voteAttrEdit->idUser= $idResource;
  if($class=='Client')$voteAttrEdit->idClient = $idResource;
  $res=$voteAttrEdit->save();
}

if (!$result) {
  $result=$res;
}

// Message of correct saving
displayLastOperationStatus($result);
?>