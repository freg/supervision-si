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
require_once "../tool/projeqtor.php";
$id=RequestHandler::getId('idPokerSession');
$idPokerItem=RequestHandler::getId('idPokerItem');
$globalClose = RequestHandler::getBoolean('globalClose');

$obj=new PokerSession($id);
$item = new PokerItem($idPokerItem);
$lowComplexity=0;
$highComplexity=0;
$value='';
$pokerMember = new PokerResource();
$pokerMember = $pokerMember->getSingleSqlElementFromCriteria('PokerResource', array('idPokerSession'=>$id, 'idResource'=>$user->id));
$pokerMemberList = $pokerMember->getSqlElementsFromCriteria(array('idPokerSession'=>$id));
$pokerVote = PokerVote::getSingleSqlElementFromCriteria('PokerVote', array('idPokerSession'=>$id, 'idResource'=>$user->id, 'idPokerItem'=>$item->id));
$pokerVoteList = SqlList::getListWithCrit('pokerVote', array('idPokerSession'=>$id, 'idPokerItem'=>$item->id), 'value');
$lowVote = 0;
$highVote = 0;
if(count($pokerVoteList) > 0){
	sort($pokerVoteList);
	$complexity = new PokerComplexity();
	if(isset($pokerVoteList[0])){
		$lowVote = $pokerVoteList[0];
		$lowCount = $pokerVote->countSqlElementsFromCriteria(array('idPokerSession'=>$obj->id,'idPokerItem'=>$item->id, 'value'=>$lowVote));
		if($lowCount > (count($pokerMemberList)/2) and count($pokerMemberList) > 2)$lowVote=false;
		$lowComplexity = $complexity->getSingleSqlElementFromCriteria('PokerComplexity', array('value'=>$lowVote));
		if(isset($pokerVoteList[count($pokerVoteList)-1])){
			$highVote = $pokerVoteList[count($pokerVoteList)-1];
			$highCount = $pokerVote->countSqlElementsFromCriteria(array('idPokerSession'=>$obj->id,'idPokerItem'=>$item->id, 'value'=>$highVote));
			if($highCount > (count($pokerMemberList)/2) and count($pokerMemberList) > 2)$highVote=false;
			$highComplexity = $complexity->getSingleSqlElementFromCriteria('PokerComplexity', array('value'=>$highVote));
		}
	}else if (isset($pokerVoteList[1])){
		unset($pokerVoteList[0]);
		$lowVote = $pokerVoteList[1];
		$lowCount = $pokerVote->countSqlElementsFromCriteria(array('idPokerSession'=>$obj->id,'idPokerItem'=>$item->id, 'value'=>$lowVote));
		if($lowCount > (count($pokerMemberList)/2) and count($pokerMemberList) > 2)$lowVote=false;
		$lowComplexity = $complexity->getSingleSqlElementFromCriteria('PokerComplexity', array('value'=>$lowVote));
		if(isset($pokerVoteList[count($pokerVoteList)])){
			$highVote = $pokerVoteList[count($pokerVoteList)];
			$highCount = $pokerVote->countSqlElementsFromCriteria(array('idPokerSession'=>$obj->id,'idPokerItem'=>$item->id, 'value'=>$highVote));
			if($highCount > (count($pokerMemberList)/2) and count($pokerMemberList) > 2)$highVote=false;
			$highComplexity = $complexity->getSingleSqlElementFromCriteria('PokerComplexity', array('value'=>$highVote));
		}
	}
}
if($item->value){
	$complexity = new PokerComplexity();
	$value = $complexity->getSingleSqlElementFromCriteria('PokerComplexity', array('value'=>$item->value));
}else{
	$value = $lowComplexity;
}
?>
<table>
    <tr>
      <td>
       <form id='pokerCloseVoteForm' name='pokerCloseVoteForm' onSubmit="return false;">
         <input id="idPokerSession" name="idPokerSession" type="hidden" value="<?php echo $id;?>" />
         <input id="idPokerItem" name="idPokerItem" type="hidden" value="<?php echo $idPokerItem;?>" />
         <table>
           <tr>
             <td class="dialogLabel" >
               <label for="pokerItemRefType" ><?php echo i18n("pokerItemType") ?>&nbsp;<?php echo (isNewGui())?'':':';?>&nbsp;</label>
             </td>
             <td>
               <textarea dojoType="dijit.form.Textarea"
                             id="pokerItemRefType" name="pokerItemRefType" readOnly
                             style="width: 400px;" value="<?php echo $item->refType;?>"
                             maxlength="4000"
                             class="input"></textarea>
             </td>
           </tr>
           <tr>
             <td class="dialogLabel" >
               <label for="pokerItemRefId" ><?php echo i18n("pokerItemElement") ?>&nbsp;<?php echo (isNewGui())?'':':';?>&nbsp;</label>
             </td>
             <td>
               <table><tr><td>
                 <textarea dojoType="dijit.form.Textarea"
                             id="pokerItemRefId" name="pokerItemRefId" readOnly
                             style="width: 400px;" value="<?php echo '#'.$item->refId.' '.SqlList::getNameFromId($item->refType, $item->refId);?>"
                             maxlength="4000"
                             class="input"></textarea>
               </td></tr></table>
             </td>
           </tr>
           <tr>
           <td class="dialogLabel" >
               <label for="pokerComplexity" ><?php echo i18n("PokerComplexity") ?>&nbsp;<?php echo (isNewGui())?'':':';?>&nbsp;</label>
             </td>
            <td>
              <select dojoType="dijit.form.FilteringSelect" id="pokerComplexity" name="pokerComplexity" style="width:200px" 
                <?php echo autoOpenFilteringSelect();?> class="input" value="<?php echo $value->id;?>">
                <?php echo htmlDrawOptionForReference('idPokerComplexity',$value->id,$value,true);?>
               </select>
               <?php if($lowComplexity->id and $highComplexity->id and ($lowComplexity->value != $highComplexity->value)){?>
               <button class="mediumTextButton" dojoType="dijit.form.Button" type="button" style="width:82px" id="pokerMinVoteValue" onclick="dijit.byId('pokerComplexity').set('value', <?php echo $lowComplexity->id;?>);">
                <?php echo ($lowComplexity->id)?$lowComplexity->name:'';?>&nbsp;&darr;
              </button>
              <button class="mediumTextButton" dojoType="dijit.form.Button" type="button" style="width:82px" id="pokerMaxVoteValue" onclick="dijit.byId('pokerComplexity').set('value', <?php echo $highComplexity->id;?>);">
                <?php echo 	($highComplexity->id)?$highComplexity->name:'';?>&nbsp;&uarr;
              </button>
              <?php }?>
             </td>
           </tr>
            <tr><td>&nbsp;</td><td>&nbsp;</td></tr>
           </table>
        </form>
      </td>
    </tr>
    <tr>
      <td align="center">
        <input type="hidden" id="dialogPokerItemAction">
        <button class="mediumTextButton" dojoType="dijit.form.Button" type="button" onclick="dijit.byId('dialogPokerCloseVote').hide();">
          <?php echo i18n("buttonCancel");?>
        </button>
        <button class="mediumTextButton" dojoType="dijit.form.Button" type="submit" style="width:150px" onclick="protectDblClick(this);pausePokerItemVote(<?php echo $idPokerItem;?>);return false;">
          <?php echo i18n("pausePokerVote");?>
        </button>
        <button class="mediumTextButton" dojoType="dijit.form.Button" type="submit" style="width:150px" onclick="protectDblClick(this);commitPokerItemVote(<?php echo $idPokerItem;?>);return false;">
          <?php if($globalClose){echo i18n("closePokerVote");}else{echo i18n("validatePokerVote");}?>
        </button>
      </td>
    </tr>
  </table>
