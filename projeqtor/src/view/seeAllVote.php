<?php
use PhpOffice\PhpPresentation\Shape\Line;
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
 * Presents the list of objects of a given class.
 *
 */
include_once '../tool/projeqtor.php';
include_once '../tool/formatter.php';
?>
<script type="text/javascript" src="<?php echoStaticFileNameWithCacheMgt('js/projeqtor.js');?>"></script> <?php 
$id = RequestHandler::getId('id');
$refType = RequestHandler::getValue('refType');
echo '<table id="seeAllVotesDiv" width="95%"" style="min-width:400px">';
echo '  <tr>';
echo '    <td class="linkHeader" style="width:28%">'.i18n('colIdVoter').'</td>';
echo '    <td class="linkHeader" style="width:16%">'.i18n('colValue').'</td>';
echo '    <td class="linkHeader" style="width:28%">'.i18n('colIdUser').'</td>';
echo '    <td class="linkHeader" style="width:28%">'.i18n('colIdClient').'</td>';
echo '  </tr>';
$voting = new Voting();
$lstVote =  $voting->getSqlElementsFromCriteria(array('refType'=>$refType,'refId'=>$id));
foreach ($lstVote as $vote){
  echo '<tr>';
  $idVoter=SqlList::getNameFromId('Affectable', $vote->idVoter);
  $idUser = SqlList::getNameFromId('Affectable', $vote->idUser);
  $idClient = SqlList::getNameFromId('Client', $vote->idClient);
  echo '<td align="center" class="assignData">'.htmlEncode($idVoter).'</td>';
  echo '<td align="center" class="assignData">'.htmlDisplayNumericWithoutTrailingZeros($vote->value).'</td>';
  echo '<td align="center" class="assignData">'.htmlEncode($idUser).'</td>';
  echo '<td align="center" class="assignData">'.htmlEncode($idClient).'</td>';
  echo '</tr>';
}
echo '</table>';
echo '</div>';


