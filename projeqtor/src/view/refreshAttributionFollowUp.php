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

/* ============================================================================
 * Presents the list of objects of a given class.
 *
 */
require_once "../tool/projeqtor.php";
require_once "../tool/formatter.php";
scriptLog('   ->/view/refreshImputationValidation.php'); 


$idResource= (RequestHandler::isCodeSet('userAttributionName'))?pq_trim(RequestHandler::getId('userAttributionName')):0;
$idClient = (RequestHandler::isCodeSet('idClientAttributionFollowUp'))?pq_trim(RequestHandler::getId('idClientAttributionFollowUp')):0;
$element = (RequestHandler::isCodeSet('votingAttributionFollowUpElement'))?pq_trim(RequestHandler::getValue('votingAttributionFollowUpElement')):'';
$left=RequestHandler::isCodeSet('showAttributionWithoutLeft')?RequestHandler::getBoolean('showAttributionWithoutLeft'):0;

if($idResource=='')$idResource=0;
if($idClient=='')$idClient=0;
?>
    <form dojoType="dijit.form.Form" name="formVotingAttributionFollowUp" id="formVotingAttributionFollowUp"  method="Post" >
      <div style="height:100%;width:100%;overflow-y:auto;">
      <?php VotingAttribution::drawVotingAttributionFollowUpGlobal($idResource,$idClient, $element, $left);?>
      </div>
    </form>
