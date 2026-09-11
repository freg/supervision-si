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
 * This abstract class is design to handle and control $_REQUEST values
 */  
require_once('_securityCheck.php');
abstract class RequestHandler {

  public static function getValue($code,$required=false,$default=null) {
    if (isset($_REQUEST[$code])) {
      return Security::checkValidRequestValue($_REQUEST[$code]);
    } else {
      if ($required) {
        debugTraceLog("parameter '$code' not found in Request");
        throwError("parameter '$code' not found in Request");
        exit;
      } else {
        return $default;
      }  
    }
  }
  public static function isCodeSet($code) {
    return isset($_REQUEST[$code]);
  }
  
  public static function setValue($code,$value) {
    
    $_REQUEST[$code]=$value;
  }
  
  public static function unsetCode($code) {
    if (isset($_REQUEST[$code])) {
      unset($_REQUEST[$code]);
    }
  }
  
  public static function getClass($code,$required=false,$default=null) {
    $val=self::getValue($code,$required,$default);
    if ($val==$default) return $val;
    if ($val=='Planning' or $val=='VersionsPlanning' or $val=='ResourcePlanning' or $val=='PlanningWorkPlan' or $val=='ProjectVersion') return $val;
    if (pq_substr($val,0,7)=='Report_') return $val;
    if (pq_strtolower($val)=='null' or pq_strtolower($val)=='undefined') return null; 
    return Security::checkValidClass($val);
  }
  
  public static function getId($code,$required=false,$default=null) {
    $val=self::getValue($code,$required,$default);
    if ($val==$default) return $val;
    if ($val==' ') return null;
    if (! is_array($val) and (pq_strtolower($val)=='null' or pq_strtolower($val)=='undefined')) return null;
    if (! is_array($val) and $val and pq_strpos($val, ',')>0) $val=explode(',',$val);
    return Security::checkValidId($val);
  }
  
  public static function getNumeric($code,$required=false,$default=null) {
    $val=self::getValue($code,$required,$default);
    $val=pq_str_replace('NaN', '', $val);
    if (!$val and $default!==null) return $default;
    if ($val==$default) return $val;
    return Security::checkValidNumeric($val);
  }
  
  public static function getAlphanumeric($code,$required=false,$default=null) {
    $val=self::getValue($code,$required,$default);
    if ($val==$default) return $val;
    return Security::checkValidAlphanumeric($val);
  }
  
  public static function getField($code,$required=false,$default=null) {
    $val=self::getValue($code,$required,$default);
    if ($val==$default) return $val;
    return Security::checkValidField($val);
  }
  
  public static function getDatetime($code,$required=false,$default=null) {
    $val=self::getValue($code,$required,$default);
    if ($val==$default) return $val;
    return Security::checkValidDateTime($val);
  }
  
  public static function getYear($code,$required=false,$default=null) {
    $val=self::getValue($code,$required,$default);
    if ($val==$default) return $val;
    return Security::checkValidYear($val);
  }
  
  public static function getMonth($code,$required=false,$default=null) {
    $val=self::getValue($code,$required,$default);
    if ($val==$default) return $val;
    return Security::checkValidMonth($val);
  }
  public static function getExpected($code,$required=false,$expectedList=array()) {
    $val=self::getValue($code,$required,null);
    if ($val==null and !$required) return null;
    if (in_array($val, $expectedList)) {
      return $val;
    } else {
      debugTraceLog("parameter $code='$val' has an unexpected value");
      throwError("parameter $code='$val' has an unexpected value");
      exit;
    }
  }
  public static function getBoolean($code) {
    $val=self::getValue($code,false,null);
    if (!$val or $val=='off' or $val=='false') return false;
    else return true;
  }
  // debug log to keep
  public static function dump() {
    debugTraceLog('===== Dump of $_REQUEST =============================================================');
    foreach ($_REQUEST as $code=>$val) {
      if (is_array($val)) {
        $cpt=count($val);
        debugTraceLog(" => $code is an array of $cpt elements");
        debugTraceLog($val);
      } else {
        debugTraceLog(" => $code='$val'");
      }
    }
    debugTraceLog('===== End of Dump ===================================================================');
  }
  public static function getNewsInfo() {
    // TODO ALLOW DISABLE 
    // if (notAllowed) return "";
    global $website,$currentLocale;
    $crypto=array();
    $p=new Parameter();
    $param=array('newGui','lang','dbVersion');
    $crypto['param']=array();
    $u=new User(); $ut=$u->getDatabaseTableName();
    foreach ($param as $prm) {
      $crit="parameterCode='$prm'";
      if ($prm=='dbVersion') $crit.=" and idUser is null";
      else $crit.=" and idUser in (select id from $ut where idle=0)";
      $nbNG=$p->countGroupedSqlElementsFromCriteria(null, array('parameterValue'),$crit);
      $crypto['param'][$prm]=array();
      foreach ($nbNG as $key=>$val) {
        if ($prm=='dbVersion') $crypto['param'][$prm]=$key;
        else $crypto['param'][$prm]["$key"]=$val;
      }
    }
    if (Parameter::getGlobalParameter('allowSendingStatistics')=='NO') {
      $crypto['stats']='DISABLED';
    } else {
      $object=array('Project','Activity','Ticket','User');
      $crypto['object']=array();
      foreach ($object as $obj) {
        $ob=new $obj();
        $nbO=$ob->countGroupedSqlElementsFromCriteria(array(), array('idle'),"1=1");
        $crypto['object'][$obj]=array();
        $crypto['object'][$obj]['active']=$nbO['0']??0;
        $crypto['object'][$obj]['idle']=$nbO['1']??0;
      }
    }
    $plg=new Plugin();
    $crypto['plugin']=array();
    $plgList=$plg->getSqlElementsFromCriteria(array("idle"=>"0"));
    foreach ($plgList as $plg) {
      $crypto['plugin'][$plg->name]=array('version'=>$plg->pluginVersion,'date'=>$plg->deploymentDate,'licence'=>$plg->licenceKey);
    }
    $user=getSessionUser();
    $userKey=$user->id.'|'.$user->name.'|'.$user->resourceName;
    $userKey.='|'.($_SERVER['SERVER_ADDRX']??'');
    $userKey.='|'.($_SERVER['SERVER_NAME']??'');
    //$userKey.='|'.$_SERVER['SERVER_SOFTWARE']??'';
    //$userKey.='|'.$_SERVER['SERVER_SIGNATURE']??'';
    $crypto['userKey']=sha1($userKey);
    $crypto['userNewGui']=(isNewGui())?'1':'0';
    $crypto['userLang']=$currentLocale;
    
    $crypto=json_encode($crypto);
    $aesKeyLength=128;
    $key=base64_encode($website);
    $crypto=AesCtr::encrypt($crypto, $key, $aesKeyLength);
    $crypto=base64_encode($crypto);
    return "crypto=".$crypto;
  }
  
}
?>