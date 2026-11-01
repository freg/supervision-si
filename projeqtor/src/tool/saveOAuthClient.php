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
 * Save real work allocation.
 */

require_once "../tool/projeqtor.php";
$id=RequestHandler::getValue('idOAuthClient');
$name=RequestHandler::getValue('dialogOAuthName');
$source=RequestHandler::getValue('dialogOAuthSourceId');
$tenant=RequestHandler::getValue('dialogOAuthTenantId');
$client=RequestHandler::getValue('dialogOAuthClientId');
$secret=RequestHandler::getValue('dialogOAuthClientSecret');
$action=RequestHandler::getValue('action');

$oauth=new OAuthClient($id);
$oauth->idUser=getCurrentUserId();
$oauth->name=$name;
$oauth->oauthSource=$source;
$oauth->tenantId=$tenant;
$oauth->clientId=$client;
$oauth->setSecret($secret);
$oauth->scope=$oauth->getScope();

$result=$oauth->save();
$url=$oauth->getAccesUrl();
setSessionValue("OAUTH2", $oauth);

if ($action=='getToken') echo $oauth->id.'|'.$url;
//else displayLastOperationStatus($result);
?>