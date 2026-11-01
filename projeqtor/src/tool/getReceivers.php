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

/** ============================================================================
 * 
 */
require_once "../tool/projeqtor.php";

$checkContact = RequestHandler::getBoolean('dialogMailToContact');
$checkUser = RequestHandler::getBoolean('dialogMailToUser');
$checkAccountable = RequestHandler::getBoolean('dialogMailToAccountable');
$checkResource = RequestHandler::getBoolean('dialogMailToResource');
$checkFinancialResponsible = RequestHandler::getBoolean('dialogMailToFinancialResponsible');
$checkSponsor = RequestHandler::getBoolean('dialogMailToSponsor');
$checkProject = RequestHandler::getBoolean('dialogMailToProject');
$checkIncludingParentProject = RequestHandler::getBoolean('dialogMailToProjectIncludingParentProject');
$checkLeader = RequestHandler::getBoolean('dialogMailToLeader');
$checkManager = RequestHandler::getBoolean('dialogMailToManager');
$checkAssigned = RequestHandler::getBoolean('dialogMailToAssigned');
$checkSubscribers = RequestHandler::getBoolean('dialogMailToSubscribers');
$objectClass = RequestHandler::getClass('objectClass');
$objectId = RequestHandler::getId('objectId');

$listReceivers = array();
$obj = new $objectClass($objectId);

if ($checkContact == "true") {
  $code = 'CONT';
  if ($objectClass == 'Project'){
    $type = i18n('colBillContact');
  }else {
    $type = i18n('colRequestor');
  } 
  $contact = new Affectable( $obj->idContact, true );
  $listReceivers[] = [
      'id' => $contact->id,
      'email'=> $contact->email,
      'name'=> $contact->name,
      'type' => $type,
      'code'=> $code
  ];
}

if ($checkUser == "true") {
  $code = 'USER';
  $user = new User ( $obj->idUser, true );
  $listReceivers[] = [
      'id' => $user->id,
      'email'=> $user->email,
      'name'=> $user->name,
      'type' => i18n('colMailToUser'),
      'code'=> $code
  ];
}

if ($checkAccountable == "true" and property_exists($obj, 'idAccountable')) {
  $code = 'ACCO';
  $resource = new Resource ( $obj->idAccountable, true );
  $listReceivers[] = [
      'id' => $resource->id,
      'email'=> $resource->email,
      'name'=> $resource->name,
      'type' => i18n('colIdAccountable'),
      'code'=> $code
  ];
}

if ($checkResource == "true" and property_exists($obj, 'idResource')) {
  $code = 'RESO';
  if ($objectClass == 'Project') $type = i18n('colManager'); 
  else $type = i18n('colResponsible');
  $resource = new Resource ( $obj->idResource, true );
  $listReceivers[] = [
      'id' => $resource->id,
      'email'=> $resource->email,
      'name'=> $resource->name,
      'type' => $type,
      'code'=> $code
  ];
}

if ($checkFinancialResponsible == "true" and property_exists($obj, 'idResponsible')) {
  $code = 'FRES';
  $responsible = new Resource ( $obj->idResponsible );
  $listReceivers[] = [
    'id' => $responsible->id,
    'email'=> $responsible->email,
      'name'=> $responsible->name,
    'type' => i18n('colMailToFinancialResponsible'),
    'code'=> $code
  ];
}

if ($checkSponsor == "true" and property_exists($obj, 'idSponsor') ) {
  $code = 'SPON';
  $sponsor = new Sponsor ( $obj->idSponsor, true );
  $listReceivers[] = [
      'id' => $sponsor->id,
      'email'=>$sponsor->email,
      'name'=> $sponsor->name,
      'type' => i18n('colIdSponsor'),
      'code'=> $code
  ];
}

if ($checkProject == "true") {
  $code = 'PROJ';
  $aff = new Affectation ();
  $idProject = ($objectClass == 'Project') ? $obj->id : ((property_exists ( $obj, 'idProject' )) ? $obj->idProject : null);
  $crit = array('idProject' => $idProject, 'idle' => '0');
  $affList = $aff->getSqlElementsFromCriteria ( $crit, false );
  if ($affList and count ( $affList ) > 0) {
    $existingIds = [];
    foreach ( $affList as $aff ) {
      $resource = new Affectable ( $aff->idResource, true );
      if (in_array($resource->id, $existingIds)) {
        continue;
      }
      if (! $resource->idle and ! $resource->dontReceiveTeamMails) {
        $listReceivers[] = [
            'id' => $resource->id,
            'email'=> $resource->email,
            'name'=> $resource->name,
            'type' => i18n('colMailToProject'),
            'code'=>$code
        ];
        $existingIds[] = $resource->id;
      }
    }
  }
}

if ($checkIncludingParentProject == "true") {
  $code = 'PPRO';
  $idProject = ($objectClass == 'Project') ? $obj->id : ((property_exists ( $obj, 'idProject' )) ? $obj->idProject : null);
  $aff = new Affectation ();
  $proj = new Project($idProject,true);
  $critWhere="idle=0 and idProject in ".transformValueListIntoInClause($proj->getTopProjectList(true));
  $affList = $aff->getSqlElementsFromCriteria ( null, false, $critWhere);
  $existingIds = [];
  if ($affList and count ( $affList ) > 0) {
    foreach ( $affList as $aff ) {
    $resource = new Affectable ( $aff->idResource, true );
    if (in_array($resource->id, $existingIds)) {
      continue; 
    }
      if (! $resource->idle and ! $resource->dontReceiveTeamMails) {
       $listReceivers[] = [
           'id' => $resource->id,
           'email'=> $resource->email,
           'name'=> $resource->name,
           'type' => i18n('colMailToProjectIncludingParentProject'),
           'code'=> $code
        ];
       $existingIds[] = $resource->id;
      }
    }
  }
}

if ($checkLeader == "true") {
  $code = 'LEAD';
  $aff = new Affectation ();
  $idProject = ($objectClass == 'Project') ? $obj->id : ((property_exists ( $obj, 'idProject' )) ? $obj->idProject : null);
  $crit = array('idProject' => $idProject, 'idle' => '0');
  $affList = $aff->getSqlElementsFromCriteria ( $crit, false );
  $existingIds = [];
  if ($affList and count ( $affList ) > 0) {
    foreach ( $affList as $aff ) {
      $resource = new Affectable ( $aff->idResource, true );
      if (in_array($resource->id, $existingIds)) {
        continue;
      }
      if ($aff->idProfile or $resource->idProfile) {
        $profile = ($aff->idProfile) ? $aff->idProfile : $resource->idProfile;
        $prf = new Profile ( $profile );
        if ($prf->profileCode == 'PL') {
          $listReceivers[] = [
              'id' => $resource->id,
              'email'=> $resource->email,
              'name'=> $resource->name,
              'type' => i18n('colMailToLeader'),
              'code'=> $code
          ];
        $existingIds[] = $resource->id;
        }
      }
    }
  }
}

if ($checkManager == "true") {
  $code = 'MANA';
  if ($objectClass != 'Project'){
    $project = new Project ($obj->idProject);
    $resource = new Affectable ( $project->idResource, true );
    $listReceivers[] = [
        'id' => $resource->id,
        'email'=> $resource->email,
        'name'=> $resource->name,
        'type' => i18n('colMailToManager'),
        'code'=> $code
    ];
  } else {
    $resource = new Affectable ( $obj->idResource, true );
    $listReceivers[] = [
        'id' => $resource->id,
        'email'=> $resource->email,
        'name'=> $resource->name,
        'type' => i18n('colManager'),
        'code'=> $code
    ];
  }
}

if ($checkAssigned == "true") {
  $code = 'ASSI';
  $ass = new Assignment ();
  $crit = array('refType' => $objectClass, 'refId' => $obj->id);
  $assList = $ass->getSqlElementsFromCriteria ( $crit );
  $existingIds = [];
  foreach ( $assList as $ass ) {
    $res = new ResourceAll ( $ass->idResource, true );
    if (in_array($res->id, $existingIds)) {
      continue;
    }
    $listReceivers[] = [
        'id' => $res->id,
        'email'=> $res->email,
        'name'=> $res->name,
        'type' => i18n('colMailToAssigned'),
        'code'=> $code
    ];
    $existingIds[] = $res->id;
  }
  
}

if ($checkSubscribers == "true") {
  $code = 'SUBS';
  $subscription = new Subscription();
  $crit = array('refType' => $objectClass, 'refId' => $objectId);
  $listSubscribers = $subscription->getSqlElementsFromCriteria($crit, false, null);
  $existingIds = [];
  foreach ($listSubscribers as $subs) {
    $resource = new Affectable ( $subs->idAffectable, true );
    if (in_array($resource->id, $existingIds)) {
      continue;
    }
    if ($subs->inCopy) $type = i18n('Incopy');
    else $type = i18n('colMailToSubscribers');
    $listReceivers[] = [
        'id' => $subs->idAffectable,
        'email' => $resource->email,
        'name'=> $resource->name,
        'type' => $type,
        'code'=> $code
    ];
    $existingIds[] = $resource->id;
  }
}

foreach ($listReceivers as $receiver) { 
  if ($receiver['id']){?>
  <tr>
    <td style="text-align: center;">
        <div id="dialogMailCheckReceiver_<?php echo $receiver['code'] . '#' . $receiver['id'] ?>"
             name="dialogMailCheckReceiver_<?php echo $receiver['code'] . '#' . $receiver['id'] ?>"
             dojoType="dijit.form.CheckBox"
             type="checkbox" checked="true"></div>
    </td>
  
  <?php if ($receiver['email']) { ?>
    <td style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 11px; padding: 0 10px 0px 5px;" title=" <?php echo htmlspecialchars($receiver['email'], ENT_QUOTES, 'UTF-8') ?>"> <?php echo $receiver['email'] ?></td>
  <?php } else {
    $noEmailText = i18n('noEmail') . ' - ' . $receiver['name']; ?>
    <td style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-style: italic; font-size: 11px;padding: 0 10px 0px 5px;" title=" <?php echo htmlspecialchars($noEmailText, ENT_QUOTES, 'UTF-8')?>"> <?php echo $noEmailText ?></td>
  <?php } ?>
  <td style="font-size: 11px; width: 100px; max-width: 100px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title=" <?php echo htmlspecialchars($receiver['type'], ENT_QUOTES, 'UTF-8') ?>"> <?php echo $receiver['type'] ?></td>
    </tr>
<?php }} ?>

