<?php
use PhpOffice\PhpSpreadsheet\Shared\Date;
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
 * Acknowledge an operation
 */
 require_once ('../tool/projeqtor.php');

$displayHighlight = false;
$notif = new Notification();
$lstNotif = $notif->getSqlElementsFromCriteria(array('idResource'=>$user->id,'idStatusNotification'=>'1','idle'=>'0'));
$highlight = new Highlight();
$lastHighLight = SqlElement::getSingleSqlElementFromCriteria('Highlight', array('idUser'=>$user->id,'scope'=>'notification'));
$lastNotif = new Notification($lastHighLight->reference);
foreach ($lstNotif as $notifs){
  if( $lastNotif->id != $notifs->id){
    if($lastNotif->notificationDate < $notifs->notificationDate ){
      $displayHighlight = 'yes';
    }
    if($lastNotif->notificationDate == $notifs->notificationDate and $lastNotif->id < $notifs->id){
      $displayHighlight = 'yes';
    }
  }
}
echo $displayHighlight;

?>
