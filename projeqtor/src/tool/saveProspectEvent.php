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

/** ===========================================================================
 * Save a situation : call corresponding method in SqlElement Class
 * The new values are fetched in $_REQUEST
 */

require_once "../tool/projeqtor.php";

// Get the situation info
$prospectId=RequestHandler::getValue('refId');
$refType=RequestHandler::getClass('refType');
$eventId=RequestHandler::getId('eventId');
$name=RequestHandler::getValue('eventName');
$prospectEventType=RequestHandler::getId('prospectEventType');
$description=RequestHandler::getValue('eventDescription');
// The contact concerned. The blank entry of a reference list carries a space,
// which would pass for a value : it is trimmed before it reaches the record.
$eventContact=pq_trim(RequestHandler::getValue('eventContact'));
if ($eventContact==='') $eventContact=null;
$date = RequestHandler::getValue('eventDate');
$time = RequestHandler::getValue('eventTime');
$dateTime = $date.' '.pq_substr($time, 1);
$eventId=pq_trim($eventId);
$action=RequestHandler::getValue('action');
if ($eventId=='') {
  $eventId=null;
}
if($action != 'remove'){
  $prospectId = pq_trim($prospectId, ',');
  $prospects = explode(",", $prospectId);
  foreach ($prospects as $prospectId){
    if ($eventId) {
      $event=new ProspectEvent($eventId);
    } else {
      $event=new ProspectEvent();
    }
    Sql::beginTransaction();
    if($action == 'remove'){
      $result=$event->delete();
    }else{
      $event->refType = $refType;
      $event->refId = $prospectId;
      // Opened from a contact, the contact is the record itself : the form is not
      // trusted on where the action belongs.
      $event->idContact = ($refType=='Contact') ? $prospectId : $eventContact;
      if (!$event->idUser) $event->idUser=getCurrentUserId();
      $event->eventDateTime = $dateTime;
      $event->name=$name;
      $event->idProspectEventType=$prospectEventType;
      $event->description=$description;
      $event->idle=0;
      $result=$event->save();
    }
    // Message of correct saving
    displayLastOperationStatus($result);
    
    // Update last date
    if ($refType=='Prospect') {
      $max=$event->getMaxValueFromCriteria('eventDateTime', array('refType'=>'Prospect', 'refId'=>$prospectId));
      $p=new Prospect($prospectId);
      $p->lastEventDatetime=$max;
      $p->save();
    }
  }
}else{
  if ($eventId) {
    $event=new ProspectEvent($eventId);
  } else {
    $event=new ProspectEvent();
  }
  Sql::beginTransaction();
  if($action == 'remove'){
    $result=$event->delete();
  }
  displayLastOperationStatus($result);
  
  // Update last date
  if ($refType=='Prospect') {
    $max=$event->getMaxValueFromCriteria('eventDateTime', array('refType'=>'Prospect', 'refId'=>$prospectId));
    $p=new Prospect($prospectId);
    $p->lastEventDatetime=$max;
    $p->save();
  }
}
?>