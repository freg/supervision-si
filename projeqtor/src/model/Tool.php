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
 * Parameter is a global kind of object for parametring.
 * It may be on user level, on project level or on global level.
 */ 
require_once('_securityCheck.php');
class Tool {
  
  /** ==========================================================================
   * Constructor
   * @param $id Int the id of the object in the database (null if not stored yet)
   * @return void
   */ 
  function __construct($id = NULL, $withoutDependentObjects=false) {
    //traceHack("Class Tool should not be instanciate, ony use Static calls");   
  }

  
  /** ==========================================================================
   * Destructor
   * @return void
   */ 
  function __destruct() {
    //traceHack("Class Tool should not be instanciate, ony use Static calls");
  }
  
// ============================================================================**********
// Tool methods
// ============================================================================**********

  /** ==========================================================================
   * Return the validation sript for some fields
   * @return String the validation javascript (for dojo frameword)
   */
  public static function beforeVersion($V1,$V2) {
  $V1=pq_ltrim($V1,'V');
  $V2=pq_ltrim($V2,'V');
  return(version_compare($V1, $V2,"<"));
  }
  
  public static function afterVersion($V1,$V2) {
  $V1=pq_ltrim($V1,'V');
  $V2=pq_ltrim($V2,'V');
  return(version_compare($V1, $V2,">="));
  }
  
  public static function getDoublePoint() {
    if (isNewGui()) return "&nbsp;&nbsp;";
    else return "&nbsp;:&nbsp;";
  }
  
  public static function getMigrationWarning() {
    global $version;
    $currVersion=Sql::getDbVersion();
    $result="";
    if (Sql::getDbVersion()==$version) return "";
    if (Sql::getDbVersion()=='0.0.0' or ! Sql::getDbVersion()) return "";
    $backupRequired=false;
    $longLasting=false;
    $veryLongLasting=false;
    if (Tool::beforeVersion($currVersion,"V10.0.0") and Sql::isMysql()) {
      $backupRequired=true;
      $longLasting=true;
      $veryLongLasting=false;
    }
    if ($backupRequired) {
      $result.=	'<div class="messageWARNING" style="margin-top:5px">';
			$result.=	i18n('migrationBackupRequired');
			$result.='</div>';
    }
    if ($veryLongLasting) {
      $result.=	'<div class="messageWARNING" style="margin-top:5px">';
      $result.=	i18n('migrationVeryLongLasting');
      $result.='</div>';
    } else if ($longLasting) {
      $result.=	'<div class="messageWARNING" style="margin-top:5px">';
      $result.=	i18n('migrationLongLasting');
      $result.='</div>';
    }
    return $result;
  }
}
?>