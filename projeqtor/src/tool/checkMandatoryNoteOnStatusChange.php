<?php
/*** COPYRIGHT NOTICE *********************************************************
 *
 * Copyright 2009-2017 ProjeQtOr - Pascal BERNARD - support@projeqtor.org
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
 * You should have received a copy of the GNU Affero General Public License
 * along with ProjeQtOr. If not, see <http://www.gnu.org/licenses/>.
 *
 *** DO NOT REMOVE THIS NOTICE ************************************************/

/**
 * Returns 1 when the requested transition must be preceded by a note.
 * Actual enforcement is also performed by SqlElement::control().
 */
require_once '../tool/projeqtor.php';

$objectClass=RequestHandler::getClass('objectClass');
$objectId=RequestHandler::getId('objectId');
$newStatusId=RequestHandler::getId('newStatusId');

if (!$objectClass or !$objectId or !$newStatusId) {
  echo '0';
  exit;
}
$object=new $objectClass($objectId);
echo SqlElement::mustAddNoteOnStatusChange($object, $newStatusId)?'1':'0';
?>
