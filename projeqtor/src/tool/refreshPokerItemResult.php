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
$result="";
$id=RequestHandler::getId('idItem');
$idPokerSession=RequestHandler::getId('idPokerSession');
$list = RequestHandler::getValue('itemList');
$itemList=pq_explode(',',$list);
$user = getSessionUser();

$obj = new PokerSession($idPokerSession);
$pos = array_search($id, $itemList);
if($pos < 0)$pos=0;
$previous = ($pos>0)?true:false;
$lenght = count($itemList)-1;
if($lenght < 0)$lenght=0;
$next = ($pos<$lenght)?true:false;

$pokerComplexity = new PokerComplexity();
$pokerComplexityList = $pokerComplexity->getSqlElementsFromCriteria(array('idle'=>'0'), null, null, "sortOrder ASC");
$pokerItem = new PokerItem($id);
$pokerMember = new PokerResource();
$pokerMember = $pokerMember->getSingleSqlElementFromCriteria('PokerResource', array('idPokerSession'=>$idPokerSession, 'idResource'=>$user->id));
$pokerMemberList = $pokerMember->getSqlElementsFromCriteria(array('idPokerSession'=>$idPokerSession));
$pokerVote = PokerVote::getSingleSqlElementFromCriteria('PokerVote', array('idPokerSession'=>$idPokerSession, 'idResource'=>$user->id, 'idPokerItem'=>$pokerItem->id));
$pokerVoteList = SqlList::getListWithCrit('pokerVote', array('idPokerSession'=>$idPokerSession, 'idPokerItem'=>$pokerItem->id), 'value');
$lowVote = 0;
$highVote = 0;
if(count($pokerVoteList) > 0){
  sort($pokerVoteList);
  if(isset($pokerVoteList[0])){
    $lowVote = $pokerVoteList[0];
    $lowCount = $pokerVote->countSqlElementsFromCriteria(array('idPokerSession'=>$obj->id,'idPokerItem'=>$pokerItem->id, 'value'=>$lowVote));
    if($lowCount > (count($pokerMemberList)/2) and count($pokerMemberList) > 2)$lowVote=false;
    if(isset($pokerVoteList[count($pokerVoteList)-1])){
    	$highVote = $pokerVoteList[count($pokerVoteList)-1];
    	$highCount = $pokerVote->countSqlElementsFromCriteria(array('idPokerSession'=>$obj->id,'idPokerItem'=>$pokerItem->id, 'value'=>$highVote));
    	if($highCount > (count($pokerMemberList)/2) and count($pokerMemberList) > 2)$highVote=false;
    }
  }else if (isset($pokerVoteList[1])){
    unset($pokerVoteList[0]);
    $lowVote = $pokerVoteList[1];
    $lowCount = $pokerVote->countSqlElementsFromCriteria(array('idPokerSession'=>$obj->id,'idPokerItem'=>$pokerItem->id, 'value'=>$lowVote));
    if($lowCount > (count($pokerMemberList)/2) and count($pokerMemberList) > 2)$lowVote=false;
    if(isset($pokerVoteList[count($pokerVoteList)])){
    	$highVote = $pokerVoteList[count($pokerVoteList)];
    	$highCount = $pokerVote->countSqlElementsFromCriteria(array('idPokerSession'=>$obj->id,'idPokerItem'=>$pokerItem->id, 'value'=>$highVote));
    	if($highCount > (count($pokerMemberList)/2) and count($pokerMemberList) > 2)$highVote=false;
    }
  }
}

if($pokerMember->id and !$obj->done){
  foreach ($pokerComplexityList as $pokerComplexity){
      $selected = ($pokerVote->id and $pokerVote->value == $pokerComplexity->value)?'selected':'';
      $onclick=(!$pokerItem->flipped)?'voteToPokerItem('.$obj->id.','.$pokerItem->id.',\''.$list.'\', '.$pokerComplexity->value.');':'';
      if($selected)$onclick='';
      $style='background-color:'.$pokerComplexity->color.';';
      if($selected)$style='background-color:white;color:'.$pokerComplexity->color.';';
      echo '<div class="card-rig card-in-hand '.$selected.'" onclick="'.$onclick.'">';
        echo '<div class="card-wrapper perspective-wrapper">';
          echo '<div class="card-container">
                  <div class="card card-face" style="'.$style.'">
                      <div class="small-card-id"><span>'.$pokerComplexity->value.'</span></div>
                      <div class="text-center player-vote"><span>'.$pokerComplexity->name.'</span></div>
                  </div>
                </div>';
        echo '</div>';
      echo '</div>';
  }
}
echo '</table>';
?>