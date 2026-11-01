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
require_once "../tool/projeqtor_string.php";

function runScript($vers,$pluginSqlFile=null) {
  global $versionParameters, $parametersLocation;
  $paramDbName=Parameter::getGlobalParameter('paramDbName');
  $paramDbPrefix=Parameter::getGlobalParameter('paramDbPrefix');
  $dbType=Parameter::getGlobalParameter('paramDbType');
  projeqtor_set_time_limit(1500);
  traceLog("=====================================");
  traceLog("");
  if ($vers) {
    traceLog("VERSION " . $vers);
    traceLog("");
    $handle = @fopen("../db/projeqtor_" . $vers . ".sql", "r");
  } else {
    traceLog("PLUGIN SQL FILE : ".$pluginSqlFile);
    traceLog("");
    $handle = @fopen($pluginSqlFile, "r");
    $versionParameters=array();
  }
  $query="";
  $nbError=0;
  $comment=false;
  if ($handle) {
    while (!feof($handle)) {
      $buffer = fgets($handle);
      $buffer=pq_trim($buffer);
      $buffer=pq_str_replace('${database}', $paramDbName, $buffer);
      $buffer=pq_str_replace('${prefix}', $paramDbPrefix, $buffer);
      if ( pq_substr($buffer,0,2)=='--' ) {
        $buffer=''; // remove comments
      }
      if ( pq_substr($buffer,0,2)=='/*' ) {
          $comment=true; // identify start of long comments (to be removed)
      }
      if ( (pq_substr($buffer,-3)=='*/;' or pq_substr($buffer,-2)=='*/') and $comment) {
        $buffer=''; // identify end of long comments : remove long comments
        $comment=false;
      }
      if ($buffer!='') {
        $query.=$buffer . "\n";
      }
      if ( pq_substr($buffer,pq_strlen($buffer)-1,1)==';' ) {
        $query=pq_trim(formatForDbType($query));
        if ($query) {
          Sql::beginTransaction();
          $result=Sql::query($query);
          if ( ! $result or !$result->queryString ) {
            try {Sql::rollbackTransaction();} catch (Exception $e) { traceLog("Rollback cancelled (DDL command auto-committed)");}
            $nbError++;
            traceLog("");
            if ($vers) {
              traceLog( "Error # $nbError => SQL error while executing maintenance query for version $vers (see above message)");
            } else {
              traceLog( "Error # $nbError => SQL error while executing Plugin query in file $pluginSqlFile (see above message)");
            }
            traceLog("");
            traceLog("*************************************************");
            traceLog("");
            $query="";
          } else {              
            $action="";
            if (pq_substr($query,0,12)=='CREATE TABLE') {
              $action="CREATE TABLE";
            } else if (pq_substr($query,0,12)=='RENAME TABLE') {
              $action="RENAME TABLE";
            } else if (pq_substr($query,0,11)=='INSERT INTO') {
              $action="INSERT INTO";
            } else if (pq_substr($query,0,6)=='UPDATE') {
              $action="UPDATE";
            } else if (pq_substr($query,0,10)=='DROP INDEX' or (pq_substr($query,0,11)=='ALTER TABLE' and pq_stripos($query, 'DROP INDEX')>0)) {
              $action="DROP INDEX";
            } else if (pq_substr($query,0,11)=='ALTER TABLE') {
              $action="ALTER TABLE";
            } else if (pq_substr($query,0,10)=='DROP TABLE') {
              $action="DROP TABLE";
            } else if (pq_substr($query,0,11)=='DELETE FROM') {
              $action="DELETE FROM";
            } else if (pq_substr($query,0,14)=='TRUNCATE TABLE') {
              $action="TRUNCATE TABLE";
            } else if (pq_substr($query,0,12)=='CREATE INDEX') {
              $action="CREATE INDEX";
            } else if (pq_substr($query,0,19)=='CREATE UNIQUE INDEX') {
              $action="CREATE UNIQUE INDEX";
            } else if (pq_substr($query,0,22)=='CREATE OR REPLACE VIEW') {
              $action="CREATE OR REPLACE VIEW";
            }
            $deb=pq_strlen($action)+pq_stripos($query, $action);            
            $end=pq_strpos($query,' ', $deb+1);
            $len=$end-$deb;
            $tableName=pq_substr($query, $deb, $len );
            $pos=pq_strpos($tableName,"\n");
            if ($pos) {
              $tableName=pq_substr($tableName, 0,$pos);
            }            
            if ($action=="DROP TABLE") {            
              $q=pq_trim($query,"\n");
              $q=pq_trim($q,"\r");
              $q=pq_trim($q,' ;');
              $q=pq_trim($q,' ');
              $tableName=pq_substr($q,strrpos($q,' ',-2)+1);
            }
            $tableName=pq_trim($tableName);
            $tableName=pq_trim($tableName,'`');
            $tableName=pq_trim($tableName,'"');
            $tableName=pq_trim($tableName,';');
            if ( $action=="RENAME TABLE" or 
               ($action=="ALTER TABLE" and Sql::isPgsql() and pq_strpos($query,' RENAME TO ')>0 ) ) { // Must also rename sequence
              $pos=pq_strpos($query,' TO ');
              $toTableName=pq_substr($query,$pos+4);
              $toTableName=pq_trim($toTableName);
              $toTableName=pq_trim($toTableName,'`');
              $toTableName=pq_trim($toTableName,'"');
              $toTableName=pq_trim($toTableName,';');
              if (Sql::isPgsql()) {
                $action="RENAME TABLE";
                $querySeq="ALTER SEQUENCE ".$tableName."_id_seq RENAME TO ".$toTableName."_id_seq";
                $resultSeq=Sql::query($querySeq);
              }
            }
            try {Sql::commitTransaction();} catch (Exception $e) { /* traceLog("Commit already done (DDL command auto-committed)");*/ }
            switch ($action) {
              case "CREATE TABLE" :
                traceLog(" Table \"" . $tableName . "\" created."); 
                break;
              case "DROP TABLE" :
                traceLog(" Table \"" . $tableName . "\" dropped."); 
                break;
              case "ALTER TABLE" :
                traceLog(" Table \"" . $tableName . "\" altered."); 
                break;
              case "RENAME TABLE" :
                traceLog(" Table \"" . $tableName . "\" renamed to \"".$toTableName."\""); 
                break;
              case "TRUNCATE TABLE" :
                traceLog(" Table \"" . $tableName . "\" truncated.");
                if ($dbType=='pgsql') {Sql::updatePgSeq($tableName);} 
                break;                
              case "INSERT INTO":           
                traceLog(" " . Sql::$lastQueryNbRows . " lines inserted into table \"" . $tableName . "\".");
                if ($dbType=='pgsql') {Sql::updatePgSeq($tableName);} 
                break;
              case "UPDATE":
                traceLog(" " . Sql::$lastQueryNbRows . " lines updated into table \"" . $tableName . "\"."); 
                break;
              case "DELETE FROM":
                traceLog(" " . Sql::$lastQueryNbRows . " lines deleted from table \"" . $tableName . "\".");
                if ($dbType=='pgsql') {Sql::updatePgSeq($tableName);} 
                break;              
              case "CREATE INDEX" : case "CREATE UNIQUE INDEX" :
                traceLog(" Index \"" . $tableName . "\" created."); 
                break;
              case "DROP INDEX" :
                traceLog(" Index \"" . $tableName . "\" dropped."); 
                break;
              default:
                traceLog("ACTION '$action' NOT EXPECTED FOR QUERY : " . $query);
            }
          }
        }
        $query="";
      }
    }
    if ($vers and pq_array_key_exists($vers,$versionParameters)) {
      $nbParam=0;
      writeFile('// New parameters ' . $vers . "\n", $parametersLocation);
      foreach($versionParameters[$vers] as $id=>$val) {
        $param=Parameter::getGlobalParameter($id);
        if (! $param) {
          $nbParam++;
          writeFile('$' . $id . ' = \'' . addslashes($val) . '\';',$parametersLocation);
          writeFile("\n",$parametersLocation);
          traceLog('Parameter $' . $id . ' added');
        }
      }
      //echo i18n('newParameters', array($nbParam, $vers));
      echo '<br/>' . "\n";
    }
    fclose($handle);
    traceLog("");
    traceLog("DATABASE UPDATED");
    if ($nbError==0) {
      traceLog(" WITH NO ERROR");
    } else {
      traceLog(" WITH " . $nbError . " ERROR" . (($nbError>1)?"S":""));
    }
  }
  traceLog("");
  return $nbError;
}

/*
 * Delete duplicate if new version has been installed twice :
 *  - habilitation
 * 
 */
function deleteDuplicate() {
  // HABILITATION
  $hab=new Habilitation();
  $habList=$hab->getSqlElementsFromCriteria(null, false, null, 'idMenu, idProfile, id ');
  $idMenu='';
  $idProfile='';
  foreach ($habList as $hab) {
    if ($hab->idMenu==$idMenu and $hab->idProfile==$idProfile) {
      $hab->delete();
    } else {
      $idMenu=$hab->idMenu;
      $idProfile=$hab->idProfile;
    }
  }
  // HABILITATIONREPORT
  $hab=new HabilitationReport();
  $habList=$hab->getSqlElementsFromCriteria(array(), false, null, 'idReport, idProfile, id ');
  $idReport='';
  $idProfile='';
  foreach ($habList as $hab) {
    if ($hab->idReport==$idReport and $hab->idProfile==$idProfile) {
      $hab->delete();
    } else {
      $idReport=$hab->idReport;
      $idProfile=$hab->idProfile;
    }
  }
  // HABILITATIONOTHER
  $hab=new HabilitationOther();
  $habList=$hab->getSqlElementsFromCriteria(array(), false, null, 'scope, idProfile, id ');
  $scope='';
  $idProfile='';
  foreach ($habList as $hab) {
    if ($hab->scope==$scope and $hab->idProfile==$idProfile) {
      $hab->delete();
    } else {
      $scope=$hab->scope;
      $idProfile=$hab->idProfile;
    }
  }
  // ACCESSRIGHT
  $acc=new AccessRight();
  $accList=$acc->getSqlElementsFromCriteria(array(), false, null, 'idProfile, idMenu, id ');
  $idMenu='';
  $idProfile='';
  foreach ($accList as $acc) {
    if ($acc->idMenu==$idMenu and $acc->idProfile==$idProfile) {
      $acc->delete();
    } else {
      $idMenu=$acc->idMenu;
      $idProfile=$acc->idProfile;
    }
  }
  // PARAMETER
  $par=new Parameter();
  $parList=$par->getSqlElementsFromCriteria(array(), false, null, 'idUser, idProject, parameterCode, id');
  $idUser='';
  $idProject='';
  $parameterCode='';
  foreach ($parList as $par) {
    if ($par->idUser==$idUser and $par->idProject==$idProject and $par->parameterCode==$parameterCode) {
      $par->delete();
    } else {
      $idUser=$par->idUser;
      $idProject=$par->idProject;
      $parameterCode=$par->parameterCode;
    }
  }
  // REPORT PARAMETER
  $par=new ReportParameter();
  $parList=$par->getSqlElementsFromCriteria(array(), false, null, 'idReport, name');
  $idReport='';
  $name='';
  foreach ($parList as $par) {
    if ($par->idReport==$idReport and $par->name==$name) {
      $par->delete();
    } else {
      $idReport=$par->idReport;
      $name=$par->name;
    }
  }
  // CRONEXECUTION
  $cronexec=new CronExecution();
  $cronexecList=$cronexec->getSqlElementsFromCriteria(array(), false, null, 'fileExecuted, fonctionName, id');
  $fileExecuted='';
  $fonctionName='';
  foreach ($cronexecList as $cronexec) {
    if ( ($cronexec->fileExecuted==$fileExecuted and $cronexec->fonctionName==$fonctionName) or ! $cronexec->fileExecuted or ! $cronexec->fonctionName ) {
      $cronexec->delete();
    } else {
      $fileExecuted=$cronexec->fileExecuted;
      $fonctionName=$cronexec->fonctionName;
    }
  }
}

function formatForDbType($query,$dbType=null) {
  if (!$dbType) $dbType=Parameter::getGlobalParameter('paramDbType');
  if (pq_substr($query,0,4)=='SET ') {
	 return ''; // Remove SET instructions 
  }
  if ($dbType=='mysql') {
    return $query;
  }
  $from=array();
  $to=array();
  if (pq_stripos($query,'ADD INDEX')) {
    errorLog("'ADD INDEX' on an 'ALTER TABLE' instruction should not be used as it is non ANSI standard. Use 'CREATE INDEX' instead");
    return '';
  }
  if ($dbType=='pgsql') {
    if (pq_stripos($query,'DROP INDEX')) {
      return pq_substr($query,pq_stripos($query,'DROP INDEX'));
    }
    $from[]='  ';                                         $to[]=' ';
    $from[]='`';                                          $to[]='';
    $from[]=' int(12) unsigned NOT NULL AUTO_INCREMENT';  $to[]=' serial';
    $from[]=' int(12) UNSIGNED NOT NULL AUTO_INCREMENT';  $to[]=' serial';
    $from[]=' int(12) unsigned AUTO_INCREMENT';           $to[]=' serial';
    $from[]=' int(12) UNSIGNED AUTO_INCREMENT';           $to[]=' serial';
    $from[]=' int(12) AUTO_INCREMENT';                    $to[]=' serial';
    $from[]=' BIGINT(';                                   $to[]=' numeric(';
    $from[]=' int(';                                      $to[]=' numeric(';
    $from[]=' datetime';                                  $to[]=' timestamp';
    $from[]=' double';                                    $to[]=' double precision';
    $from[]=' mediumtext';                                $to[]=' text';
    $from[]=' longtext';                                  $to[]=' text';
    $from[]=' unsigned';                                  $to[]='';
    $from[]='\\\'';                                       $to[]='\'\'';
    $from[]='ENGINE=InnoDB';                              $to[]='';
    $from[]='DEFAULT CHARSET=utf8mb4 COLLATE utf8mb4_general_ci';                    $to[]='';
    $from[]='DEFAULT CHARSET=utf8mb4';                    $to[]='';
    $from[]='COLLATE utf8mb4_general_ci';                 $to[]='';
    $from[]='DEFAULT CHARSET=utf8';                       $to[]='';
    $from[]='COLLATE utf8_general_ci';                    $to[]='';
    $from[]='STR_TO_DATE';                                $to[]='to_timestamp';
    $from[]='str_to_date';                                $to[]='to_timestamp';
    $from[]='%Y-%m-%d %H:%i:%s';                          $to[]='YYYY-MM-DD HH24:MI:SS';
    $from[]='CHARACTER SET ascii';                        $to[]='';
    $from[]='COLLATE ascii_general_ci';                   $to[]='';
    $res=str_ireplace($from, $to, $query);
    // ALTER TABLE : very different from MySql !!!
    if (pq_substr($res,0,11)=='ALTER TABLE') {
      $posChange=pq_strpos($res,'CHANGE');
      while ($posChange) {
        $colPos1=pq_strpos($res,' ',$posChange+1);
        $colPos2=pq_strpos($res,' ',$colPos1+1);
        $colPos3=pq_strpos($res,' ',$colPos2+1);
        if (!$colPos3) {$colPos3=pq_strlen($res)-1;}
        $col1=pq_substr($res,$colPos1+1,$colPos2-$colPos1-1);
        $col2=pq_substr($res,$colPos2+1,$colPos3-$colPos2-1);
        if ($col1==$col2) {
          $res=pq_substr($res,0,$posChange-1). ' ALTER '.$col2.' TYPE '.pq_substr($res,$colPos3+1);
        } else {
          $res=pq_substr($res,0,$posChange-1). ' RENAME '.$col1.' TO '.$col2.';';
        }
        $res=pq_str_replace(' DEFAULT NULL', ' ', $res);
        $posChange=pq_strpos($res,'CHANGE', $posChange+5);
      }
    } else if (pq_substr($res,0,12)=='RENAME TABLE') {
       $res=pq_str_replace('RENAME TABLE','ALTER TABLE',$res);
       $res=pq_str_replace(' TO ',' RENAME TO ',$res);
    } else if (pq_substr($res,0,12)=='CREATE INDEX') {
      $res=pq_str_replace('(180)','',$res);
    }
    $posComment=pq_strpos($res," COMMENT '");
    while ($posComment) {
      $posCommentEnd=pq_strpos($res,"'",$posComment+10);
      $res=pq_substr($res,0,$posComment).pq_substr($res,$posCommentEnd+1);
      $posComment=pq_strpos($res," COMMENT '");
    }
  } else {
    // not mysql, not pgsql, so WHAT ?
    echo "unknown database type '$dbType'";
    return '';
  }
  
  return $res;
}

function migrateParameters($arrayParamsToMigrate) {
  global $parametersLocation;
  include $parametersLocation;
  foreach ($arrayParamsToMigrate as $param) {
    //$crit=array('idUser'=>null, 'idProject'=>null, 'parameterCode'=>$param);
    //$parameter=SqlElement::getSingleSqlElementFromCriteria('Parameter', $crit);
    //if (!$parameter or !$parameter->id) { 
    $parameter=new Parameter();
    //}
    $parameter->idUser=null;
    $parameter->idProject=null;
    $parameter->parameterCode=$param;  
    $parameter->parameterValue=Parameter::getGlobalParameter($param);
    if ($param=='paramMailEol') {
      if ($parameter->parameterValue=='\n') {
        $parameter->parameterValue='LF';
      } else  {
        $parameter->parameterValue='CRLF';
      }
    }
    $parameter->save();
  }
  Parameter::regenerateParamFile();
}

function kanbanPostInstall() {

  Habilitation::correctUpdates();

  if (SqlElement::class_exists('HabilitationSuperAdmin')) {
    $hab=SqlElement::getSingleSqlElementFromCriteria('HabilitationSuperAdmin',array('idMenu'=>'100006001'));
    $hab->idMenu='100006001';
    $hab->save();
  }

  $objStatus = new Status();
  $listStatus=$objStatus->getSqlElementsFromCriteria(null,false);
  $listStatusWithOrder=array();
  foreach ($listStatus as $line){
    $listStatusWithOrder[$line->sortOrder.'-'.$line->id]=$line;
  }
  ksort($listStatusWithOrder);
  $kanban=new Kanban();
  $listColumn=array();
  $stat=0;
  foreach ($listStatusWithOrder as $line){
    if($stat==0 && !$line->setHandledStatus && !$line->setDoneStatus && !$line->setIdleStatus){
      $listColumn['column'][$stat]['from']=$line->id;
      $listColumn['column'][$stat]['name']=pq_ucfirst ("backlog");
      $listColumn['column'][$stat]['cantDelete']=true;
      $stat++;
    }else
      if($stat==1 && $line->setHandledStatus){
      $listColumn['column'][$stat]['from']=$line->id;
      $listColumn['column'][$stat]['name']=pq_ucfirst (i18n("colHandled"));
      $stat++;
    }else
      if($stat==2 && $line->setDoneStatus){
      $listColumn['column'][$stat]['from']=$line->id;
      $listColumn['column'][$stat]['name']=pq_ucfirst (i18n("colDone"));
      $stat++;
    }else
      if($stat==3 && $line->setIdleStatus){
      $listColumn['column'][$stat]['from']=$line->id;
      $listColumn['column'][$stat]['name']=pq_ucfirst (i18n("colIdle"));
      $stat++;
    }
  }
  $listColumn["typeData"]="Ticket";
  $kanban->idUser=getSessionUser()->id;
  $kanban->param=json_encode($listColumn);
  $kanban->name="Kanban";
  $kanban->type="Status";
  $kanban->isShared=0;
  $kanban->save();
}