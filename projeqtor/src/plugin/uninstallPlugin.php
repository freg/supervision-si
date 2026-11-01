<?php
/*** COPYRIGHT NOTICE *********************************************************
 *
 * Copyright 2014 ProjeQtOr - Pascal BERNARD - support@projeqtor.org
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

$maintenance=true;
require_once '../tool/projeqtor.php';
require_once "../db/maintenanceFunctions.php";

$user=getSessionUser();

if (securityGetAccessRightYesNo('menuPlugin','read')!='YES') {
  traceHack ( "plugin management tried without access right" );
  exit ();
}
$idMenu = SqlList::getIdFromName('menu', i18n('menuPluginManagement'));
$habilitation = Habilitation::getSingleSqlElementFromCriteria('Habilitation', array('idMenu'=>$idMenu, 'idProfile'=>$user->idProfile));
if ($habilitation->allowAccess != 1) {
  echo 'Call to uninstallPlugin.php for non allowed user.<br/>This action and your IP has been traced.';
  traceHack('Call to uninstallPlugin.php for non allowed user');
	exit;
}

$uniqueCode = RequestHandler::getValue('uniqueCode');
$pluginName = RequestHandler::getValue('pluginName');
$plugin = new Plugin();
$pluginList = $plugin->getSqlElementsFromCriteria(array('uniqueCode'=>$uniqueCode));
$idPluginList = SqlList::getListWithCrit('Plugin', array('uniqueCode'=>$uniqueCode), 'id',null,true);
$idPluginFlatList = '(0,'.implode(',', $idPluginList).')';

$pluginButton = new PluginButton();
$pluginTriggerEvent = new PluginTriggeredEvent();
$menu = new Menu();
$navigation = new Navigation();
$cron = new CronExecution();

try {
  $xml = new XMLReader();
  $pluginDescriptor = $pluginName.'/pluginDescriptor.xml';
  $xml->open($pluginDescriptor);
  $fileName = '';
  $fileTarget = '';
  
  while( $xml->read() ) {
  	try {
  		if($xml->nodeType == XMLReader::ELEMENT && $xml->name=='files'){
  			$node = new SimpleXMLElement($xml->readOuterXML());
  			$file = $node->children();
  			foreach ($file as $val){
  				$fileAttr = $val->attributes();
  				foreach ($fileAttr as $attr=>$obj){
  					if($attr == 'name'){
  						$fileName = (string)$obj;
  					}
  					if($attr == 'target'){
  						$fileTarget = (string)$obj;
  					}
  				}
				if($fileName != 'PlgCustomList.php'){
			       traceLog("remove file $fileTarget/$fileName");	
  			       unlink($fileTarget.'/'.$fileName);
  			    }
  			}
  		}
  	} catch (Exception $e) {
  		$xml->close();
		errorLog("Error while reading $pluginDescriptor");
  		errorLog($e->getMessage());
  	}
  }
  $xml->close();
} catch (Exception $e) {
  $xml->close();
  errorLog("Unable to open $pluginDescriptor");
  errorLog($e->getMessage());
}

purgeFiles($pluginName, null, true);

$query = 'DELETE FROM '.$pluginButton->getDatabaseTableName().' WHERE idPlugin in '.$idPluginFlatList.';';
Sql::query($query);
$query = 'DELETE FROM '.$pluginTriggerEvent->getDatabaseTableName().' WHERE idPlugin in '.$idPluginFlatList.';';
Sql::query($query);
$query = 'DELETE FROM '.$plugin->getDatabaseTableName().' WHERE id in '.$idPluginFlatList.';';
Sql::query($query);
$query = 'DELETE FROM '.$menu->getDatabaseTableName().' WHERE id >= '.$uniqueCode.'000 and id <= '.$uniqueCode.'999;';
Sql::query($query);
$query = 'DELETE FROM '.$navigation->getDatabaseTableName().' WHERE idMenu >= '.$uniqueCode.'000 and idMenu <= '.$uniqueCode.'999;';
Sql::query($query);
if($pluginName == 'backupDatabase'){
  $query .= 'DELETE FROM '.$cron->getDatabaseTableName().' WHERE fileExecuted LIKE \'../tool/plgBackupCron.php%\';';
  Sql::query($query);
}
