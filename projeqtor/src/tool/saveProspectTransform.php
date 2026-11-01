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
 * You can get complete code of ProjeQtOr, other activity, help and information
 * about contributors at http://www.projeqtor.org 
 *     
 *** DO NOT REMOVE THIS NOTICE ************************************************/

/** ===========================================================================
 * Save a note : call coractponding method in SqlElement Class
 * The new values are fetched in $_REQUEST
 */
require_once "../tool/projeqtor.php";
scriptLog('   ->/tool/saveProspectTransform.php');
$id = RequestHandler::getId('idProspect');
$prospect = new Prospect($id);

Sql::beginTransaction();

if ($prospect->prospectNameCompany != null) {
  $client = new Client();
  $client->name=$prospect->prospectNameCompany;
  $type=new ClientType();
  // The class adds its own scope='Client' criterion with AND, which binds tighter
  // than OR : without these brackets the query returns any scope, and the sort on
  // sortOrder puts the ProspectType first.
  $typeList=$type->getSqlElementsFromCriteria(null,null,"(name like '%Prospect%' or name like '%".i18n('Prospect')."%')");
  if (count($typeList)>0) {
    $typeOjb=reset($typeList);
    $typeCli=$typeOjb->id;
  } else {
    $typeList=$type->getSqlElementsFromCriteria(null,null,"idle=0");
    $typeOjb=reset($typeList);
    $typeCli=$typeOjb->id;
  }
  $client->idClientType=$typeCli;
  //_sec_adresse
  $client->designation=$prospect->designation??null;
  $client->street=$prospect->street??null;
  $client->complement=$prospect->complement??null;
  $client->zip=$prospect->zip??null;
  $client->city=$prospect->city??null;
  $client->state=$prospect->state??null;
  $client->country=$prospect->country??null;
  $client->fillRequiredFields();
  //save
  $resCli=$client->save();
  if (getLastOperationStatus($resCli)!='OK') traceLog($resCli);
  if (getLastOperationStatus($resCli)=='OK') {
    $lnk=new Link();
    $lnk->ref1Type='Client';
    $lnk->ref1Id=$client->id;
    $lnk->ref2Type='Prospect';
    $lnk->ref2Id=$prospect->id;
    $lnk->save();
  }
}

if ($prospect->prospectNameContact != null) {
  $contact = new Contact();
  $contact->name=$prospect->prospectNameContact;
  $contact->email=$prospect->email??null;
  $contact->contactFunction=$prospect->prospectFunction??null;
  $contact->phone=$prospect->phone??null;
  $contact->mobile=$prospect->mobile??null;
  $contact->fax=$prospect->fax??null;
  if (isset($client) and $client and $client->id) $contact->idClient=$client->id;
  //_sec_adresse
  $contact->designation=$prospect->designation??null;
  $contact->street=$prospect->street??null;
  $contact->complement=$prospect->complement??null;
  $contact->zip=$prospect->zip??null;
  $contact->city=$prospect->city??null;
  $contact->state=$prospect->state??null;
  $contact->country=$prospect->country??null;
  $contact->fillRequiredFields();
  //save
  $resCont=$contact->save();
  if (getLastOperationStatus($resCont)!='OK') traceLog($resCont);
  if (getLastOperationStatus($resCont)=='OK') {
    $lnk=new Link();
    $lnk->ref1Type='Contact';
    $lnk->ref1Id=$contact->id;
    $lnk->ref2Type='Prospect';
    $lnk->ref2Id=$prospect->id;
    $lnk->save();
  }
}

$prospect->lastEventDatetime=date('Y-m-d H:i:s');
$res=$prospect->save();
displayLastOperationStatus($res);  


?>