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
$idItem=RequestHandler::getId('idItem');
$idPokerSession=RequestHandler::getId('idPokerSession');
$list = RequestHandler::getValue('itemList');
$itemList=pq_explode(',',$list);
$user = getSessionUser();

$obj = new PokerSession($idPokerSession);
$canUpdate=securityGetAccessRightYesNo('menu'.get_class($obj), 'update', $obj)=="YES";
if ($obj->idle==1) {
	$canUpdate=false;
}

$pos = array_search($idItem, $itemList);
if($pos < 0)$pos=0;
$lenght = count($itemList)-1;
if($lenght < 0)$lenght=0;
$pos = array_search($idItem, $itemList);
if($pos < 0)$pos=0;
$previous = ($pos>0)?true:false;
$lenght = count($itemList)-1;
if($lenght < 0)$lenght=0;
$next = ($pos<$lenght)?true:false;
$pos +=1;

$pokerComplexity = new PokerComplexity();
$pokerComplexityList = $pokerComplexity->getSqlElementsFromCriteria(array('idle'=>'0'), null, null, "sortOrder ASC");
$pokerItem = new PokerItem($idItem);
$pokerMember = new PokerResource();
$pokerMember = $pokerMember->getSingleSqlElementFromCriteria('PokerResource', array('idPokerSession'=>$idPokerSession, 'idResource'=>$user->id));
$pokerMemberList = $pokerMember->getSqlElementsFromCriteria(array('idPokerSession'=>$idPokerSession));
$pokerVote = PokerVote::getSingleSqlElementFromCriteria('PokerVote', array('idPokerSession'=>$idPokerSession, 'idResource'=>$user->id, 'idPokerItem'=>$pokerItem->id));
$pokerVoteList = SqlList::getListWithCrit('pokerVote', array('idPokerSession'=>$idPokerSession, 'idPokerItem'=>$pokerItem->id), 'value');
sort($pokerVoteList);
$lowVote = 0;
$highVote = 0;
if(count($pokerVoteList) > 0){
  sort($pokerVoteList);
  if(isset($pokerVoteList[0])){
    $lowVote = $pokerVoteList[0];
    $lowCount = $pokerVote->countSqlElementsFromCriteria(array('idPokerSession'=>$obj->id,'idPokerItem'=>$pokerItem->id, 'value'=>$lowVote));
    if($lowCount > (count($pokerMemberList)/2))$lowVote=false;
    if(isset($pokerVoteList[count($pokerVoteList)-1])){
    	$highVote = $pokerVoteList[count($pokerVoteList)-1];
    	$highCount = $pokerVote->countSqlElementsFromCriteria(array('idPokerSession'=>$obj->id,'idPokerItem'=>$pokerItem->id, 'value'=>$highVote));
    	if($highCount > (count($pokerMemberList)/2))$highVote=false;
    }
  }else if (isset($pokerVoteList[1])){
    unset($pokerVoteList[0]);
    $lowVote = $pokerVoteList[1];
    $lowCount = $pokerVote->countSqlElementsFromCriteria(array('idPokerSession'=>$obj->id,'idPokerItem'=>$pokerItem->id, 'value'=>$lowVote));
    if($lowCount > (count($pokerMemberList)/2))$lowVote=false;
    if(isset($pokerVoteList[count($pokerVoteList)])){
    	$highVote = $pokerVoteList[count($pokerVoteList)];
    	$highCount = $pokerVote->countSqlElementsFromCriteria(array('idPokerSession'=>$obj->id,'idPokerItem'=>$pokerItem->id, 'value'=>$highVote));
    	if($highCount > (count($pokerMemberList)/2))$highVote=false;
    }
  }
}
echo '<div style="width: 95%;padding-bottom: 20px;" align="right">';
if($canUpdate and $obj->idResource == $user->id and !$pokerItem->value){
    if(count($pokerVoteList) > 0){
      $name = i18n('flipPokerVote');
      if($pokerItem->flipped){
      	$name = i18n('resetPokerVote');
      }
      echo ' <button id="flipPokerVote" dojoType="dijit.form.Button" style="vertical-align: middle;" class="roundedVisibleButton">';
      $icon = '&curarr;&nbsp;';
      if($pokerItem->flipped)$icon='&orarr;&nbsp;';
      echo '   <span style="padding: 0px 5px 0px 5px;">'.$icon . $name . '</span>';
      echo '   <script type="dojo/connect" event="onClick" args="evt">';
      if(!$pokerItem->flipped){
      	echo '     flipPokerVote('.$obj->id.','.$pokerItem->id.',\''.$list.'\');';
      }else{
      	echo '     resetPokerVote('.$obj->id.','.$pokerItem->id.',\''.$list.'\');';
      }
      echo '   </script>';
      echo ' </button>';
    }
    if($pokerItem->flipped){
    	echo ' <button id="closePokerVote" dojoType="dijit.form.Button" style="vertical-align: middle;margin-right: 10px;" class="roundedVisibleButton">';
    	echo '   <span style="padding: 0px 5px 0px 5px;">' . i18n('validatePokerVote') . '</span>';
    	echo '   <script type="dojo/connect" event="onClick" args="evt">';
    	echo '     closePokerItemVote('.$pokerItem->id.','.$obj->id.', false);';
    	echo '   </script>';
    	echo ' </button>';
    }
}
echo '</div>';

foreach ($pokerMemberList as $member){
  echo '<div style="float:left;padding: 0px 5px 10px 5px;"><table><tr>';
  echo '<td>';
  $pVote = PokerVote::getSingleSqlElementFromCriteria('PokerVote', array('idPokerItem'=>$pokerItem->id, 'idPokerSession'=>$obj->id, 'idResource'=>$member->idResource));
  $pComplex = PokerComplexity::getSingleSqlElementFromCriteria('PokerComplexity', array('value'=>$pVote->value));
  $style='';
  $color='white';
  if($lowVote == $pComplex->value and count($pokerVoteList) > 1){
  	$color='#84ea9b';
  }else if($highVote == $pComplex->value and count($pokerVoteList) > 1){
  	$color='#ff6565';
  }
  if($pVote->id and $pComplex->id and $pokerItem->flipped){
    $style='background-color:'.$pComplex->color.';color:'.$color;
  }else if($pVote->id and !$pokerItem->flipped){
    $style='background-color:var(--color-medium);';
  }
  echo '<div class="card-on-table">';
    echo '<div class="card-wrapper-mini">';
      echo '<div class="card-container-mini">';
        echo '<div class="card-mini card-face" style="'.$style.'" align="center">';
          if($pVote->id and $pokerItem->flipped){
            echo '<div class="text-center player-vote-mini"><span>'.$pComplex->name.'</span></div>';
          }else if($pVote->id and !$pokerItem->flipped){
            echo '<div style="position: absolute;top: 20px;left: 8px;"><img style="height:32px;width:32px;" src="img/logoSmallWhite.png"></div>';
          }
        echo '</div>';
      echo '</div>';
    echo '</div>';
  echo '</div>';
  echo '</td>';
  echo '<td><div style="padding-left: 10px;width: 55px;">'.SqlList::getNameFromId('Affectable', $member->idResource).'</div></td>';
  echo '</tr></table></div>';
}
?>