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
require_once('_securityCheck.php');

class Security
{
  private static $continueOnError=false;
  // Must be disabled after each test to be forced before required test
  
  function __construct($name = NULL) {
    traceHack("Static Class Security must not be instanciated");
  }
  /* Security fonctions to check validity of input values
   *  =========
  *  ATTENTION : these functions concider that not allowed values are Hack attemps, disconnecting user and exiting script
  *  =========
  *  checkValidClass($className) : $className is a valid string corresponding to a valid class extending SqlElement
  *  checkValidId($id) : $id is a valid number or possibly '*' or empty string '' (may mean all in some cases)
  *  checkValidBoolean($boolean) : $boolean is a boolean, automatically replace similar values to 1 or 0, only allowed values
  *  checkValidDateTime($dateTime) : $date is either a date or a time or a datetime
  *  checkValidNumeric($numeric) : $numeric is a numeric value
  *  checkValidInteger($integer) : $integer is an integer value
  *  checkValidAlphanumeric($string) : $string is alphnumeric only containing a-z, A-Z, 0-9
  *  checkValidFilename($file) : $file is a valid file, avoiding cross directory hacks
  *  checkValidMimeType($mimeType) : $mimeType is a valid mime type corresponding to RFC1341
  *  checkValidYear($year) : $year is a valid year (4 digits)
  *  checkValidMonth($month) : $month is a valid month (1 or 2 digits, value between 1 and 12)
  *  checkValidWeek($week) : $week is a valid week (1 or 2 digits, value between 1 and 53)
  *  checkValidPeriod($period) : $period as a valid period (numeric)
  *  checkValidPeriodScale($periodScale) : $periodScale is a valid period scale (year, quarter, month, week, day)
  *  
  */
  public static function checkValidClass($className,$activeTraceHack=true) {
    if ($className=='') return ''; // Allow empty string
    //if ($className=='Planning') return $className; // Not a real class, but can be concidered as
    // not checking  existence using realpath() due to inconsistent behavior in different versions.
    if ($className=='Replan' or $className=='Construction' or $className=='Fixed') $className='Project';
    if ($className=='ProductVersionhasChild') $className = 'ProductVersion';
    if ($className=='ComponentVersionhasChild') $className = 'ComponentVersion';
    if (!file_exists('../model/'.$className.'.php') || 
    $className != basename(realpath('../model/'.$className.'.php'), '.php')) {
      if (!file_exists('../model/custom/'.$className.'.php') ||
      $className != basename(realpath('../model/custom/'.$className.'.php'), '.php')) {
        if ($activeTraceHack==true){
          traceHack("Invalid class name '$className'");
        }else{
          return false;
        }
      }
    }
    if (! SqlElement::is_subclass_of( $className, 'SqlElement')) {
      traceHack("Class '$className' does not extend SqlElement");
    }
    return $className;
  }
  public static function checkValidId($id,$activeTraceHack=true) {
    if (is_array($id)) {
      foreach ($id as $val);
      Security::checkValidId($val);
      return $id;
    }
    if ($id=='null' or $id=='undefined') $id=null;
    if (! is_numeric($id) and $id!='*' and pq_trim($id)!='') {
      if($activeTraceHack)traceHack("Id '$id' is not numeric");
      $id=null;
    }
    return $id;
  }
  public static function checkValidBoolean($boolean,$activeTraceHack=true) {
    if (! $boolean or $boolean==false or pq_trim($boolean)=='') return 0;
    if ($boolean==='0') return 0;
    if ($boolean==='1') return 1;
    if ($boolean==-1 or $boolean===true) return 1;
    if ($boolean=='on') return 1;
    if ($boolean=='true') return 1;
    if ($boolean=='off') return 0;
    if ($boolean=='false') return 0;
    if ($boolean!==0 and $boolean!==1) {
      if($activeTraceHack)traceHack("the value '$boolean' is not a boolean");
      $boolean=null;
    }
    return $boolean;
  }
  public static function checkValidDateTime($dateTime,$activeTraceHack=true) {
    if (! is_string($dateTime) and is_a($dateTime,'DateTime',true)) return Security::checkValidDateTime($dateTime->format('Y-m-d H:i:s'),$activeTraceHack);
    if (pq_trim($dateTime)=='') return '';
    $len=pq_strlen($dateTime);
    if ($len<5 or $len>19) {
      if($activeTraceHack)traceHack("Invalid dateTime format for '$dateTime' : only 5 to 19 characters length possible");
      return null;
    }
    $date=""; $time="";
    if ($len<10) {
      if (pq_substr($dateTime,0,1)=='T') {
        $time=pq_substr($dateTime,1);
      } else {
        $time=$dateTime;
      }
    } else if ($len==10) {
      $date=$dateTime;
    } else { // $len > 10
      $split=pq_explode(' ',$dateTime);
      if (count($split)!=2) {
        $split=pq_explode('T',$dateTime);
      }
      if (count($split)!=2) {
        if($activeTraceHack)traceHack("Invalid dateTime format for '$dateTime' : date / time not separated by space");
        return null;
      }
      $date=$split[0];
      $time=(count($split)>1)?$split[1]:null;
    }
    if ($date) {
      if (preg_match('/^\d{4}-\d{2}-\d{2}$/', pq_nvl(pq_trim($date))) != true) {
        if($activeTraceHack)traceHack("Invalid dateTime format for '$dateTime' : date expected format is YYYY-MM-DD");
        return null;
        //exit; // Not reached, traceHack exits script
      }
    }
    if ($time) {
      if (preg_match('/^\d{2}:\d{2}:\d{2}$/', pq_nvl(pq_trim($time))) != true 
      and preg_match('/^\d{2}:\d{2}$/', pq_nvl(pq_trim($time))) != true) {
        if($activeTraceHack)traceHack("Invalid dateTime format for '$dateTime' : time expected format is HH:MN or HH:MN:SS");
        return null;
        //exit; // Not reached, traceHack exits script
      }
    }
    return $dateTime;
  }
  public static function checkValidNumeric($numeric,$activeTraceHack=true) {
    if ($numeric===null or $numeric==='' or pq_trim($numeric)==='' or $numeric=='NaN') return null; //allow null or empty value
    if (! is_numeric($numeric)) {
      if($activeTraceHack) traceHack("Value '$numeric' is not numeric");
      $numeric=null;
    }
    return $numeric;
  }
  public static function checkValidInteger($integer,$activeTraceHack=true) {
    if ($integer===null or $integer==='' or pq_trim($integer)==='' or $integer=='NaN') return; //allow null or empty value
    if ($integer=='on') return 1;
    if ($integer=='off') return 0;
    if (! is_numeric($integer)) {
      if($activeTraceHack) traceHack("Value '$integer' is not a numeric integer");
      $interger=null;
    }
    return intval($integer);
  }
  public static function checkValidAlphanumeric($string,$activeTraceHack=true) {
    // TODO (SECURITY) : use ctype_alnum()
    if (preg_match('/[^0-9a-zA-Z]/', pq_nvl($string)) == true) {
      if($activeTraceHack) traceHack("invalid alpanumeric string value - $string");
      $string=null;
    }
    return $string;
  }
  public static function checkValidField($string,$activeTraceHack=true) {
    // TODO (SECURITY) : use ctype_alnum()
    if (preg_match('/[^0-9a-zA-Z\_]/', pq_nvl($string)) == true) {
      if($activeTraceHack) traceHack("invalid alpanumeric string value - $string");
      $string=null;
    }
    return $string;
  }
  public static function checkValidYear($year) {
    if (preg_match('/^[0-9]{4}$/', pq_nvl($year)) != 1) { // only allow 4 digit number as year. Note: may want to limit to range of valid year dates.
      $year='';
    }
    return $year;
  }
  public static function checkValidMonth($month) {
    // only allow from 1 to 2 digits as number as month. Must be between 1 and 12.
    if (is_numeric($month)) {
      $month = $month+0; // convert it to numeric variable
      if (is_int($month)) { // make sure its not a float
        if ($month < 1 or $month > 12) {// make sure it is not out of range
          $month='';
        }
      } else {
        $month='';
      }
    } else {
      $month='';
    }
    // here it is either an empty string or a number between 1-12
    $month=$month.''; // make sure it ends up as a string
    return $month;
  }
  public static function checkValidWeek($week) {
    // only allow from 1 to 2 digits as number as week. Must be between 1 and 52.
    if (is_numeric($week)) {
      $week = $week+0; // convert it to numeric variable
      if (is_int($week)) { // make sure its not a float
        if ($week < 1 or $week > 53) {// make sure it is not out of range
          $week='';
        }
      } else {
        $week='';
      }
    } else {
      $week='';
    }
    // here it is either an empty string or a number between 1-53
    $week=$week.''; // make sure it ends up as a string
    return $week;
  }
  public static function checkValidPeriod($period) {
    $period = preg_replace('/[^0-9]/', '', pq_nvl($period));
    return $period;
  }
  public static function checkValidPeriodScale($scale) {
    $scale=preg_replace('/[^a-z]/', '', pq_nvl($scale)); // only allow a-z.
    if ($scale!='week' and $scale!='month' and$scale!='day' and $scale!='quarter' and $scale!='year') {
      traceHack("period scale '$scale' is not an expected period scale");
      $scale=null; // Not reached as traceHack will exit script
    }
    return $scale;
  }
  public static function checkValidFileName($fileName,$activeTraceHack=true, $forAttachment=true) {
    //$fileName=preg_replace('/[^a-zA-Z0-9_-]/', '', $fileName); // only allow [a-z, A-Z, 0-9, _, -] in file name 
    // PBE : disabled : much too restrictive (accentuated characters can be used, need to allow . for extension a.ext or a.b.c.ext)
    //^[^/?*:;{}\\]*\.?[^/?*:;{}\\]+$ // => allows host and .htaccess as file name
    //
    // TODO (SECURITY) : use ctype_print()
    if (!$forAttachment and $activeTraceHack and basename($fileName)!=$fileName) {
      if($activeTraceHack)traceHack("filename $fileName containts path elements that are not accepted");
      $fileName=""; // Not reached as traceHack will exit script
    }
    if (! $forAttachment and ! ctype_print($fileName)) {
      $accents = array('À','Á','Â','Ã','Ä','Å','Ç','È','É','Ê','Ë','Ì','Í','Î','Ï','Ò','Ó','Ô','Õ','Ö','Ù','Ú','Û','Ü','Ý','à','á','â','ã','ä','å','ç','è','é','ê','ë','ì','í','î','ï','ð','ò','ó','ô','õ','ö','ù','ú','û','ü','ý','ÿ');
      $woaccts = array('A','p','A','A','A','A','C','E','E','E','E','I','I','I','I','O','O','O','O','O','U','U','U','U','Y','a','a','a','a','a','a','c','e','e','e','e','i','i','i','i','o','o','o','o','o','o','u','u','u','u','y','y');
      $fileName = pq_str_replace($accents, $woaccts, $fileName);
    }
    if (! preg_match('#^[^/?*:;{}\\<>|"]*\.?[^/?*:;{}\\<>|"]+$#', pq_nvl($fileName))) {
      if($activeTraceHack)traceHack("filename $fileName containts invalid characters \ / : * ? \" ; { } < >");
      //$fileName=pq_str_replace(array('/','\\'),array('',''), $fileName);
      if (! $forAttachment) $fileName=preg_replace('/[^a-zA-Z0-9_\-\.\ ]/', '', pq_nvl($fileName)); // reached only if $activeTraceHack==false
    }
    if ( preg_match('#[\x00\x08\x0B\x0C\x0E-\x1F]#',pq_nvl($fileName)) ) {
      if($activeTraceHack)traceHack("filename $fileName containts non printable characters");
      $fileName=""; // reached only if $activeTraceHack==false
    }
    if (! $forAttachment and ! ctype_print($fileName)) {
      if($activeTraceHack)traceHack("filename $fileName containts non printable characters");
      $fileName=""; // reached only if $activeTraceHack==false
    }
    if ( pq_substr($fileName,-1)=='.') {
      //if($activeTraceHack)traceHack("filename $fileName end with '.' which is not accepted and may be hacking attempt");
      $fileName=pq_substr($fileName,0,-1); 
    }
    
    if ($forAttachment) {
      $ext = pq_strtolower ( pathinfo ( $fileName, PATHINFO_EXTENSION ) );
      if (pq_substr($ext,0,3)=='php' or pq_substr($ext,0,3)=='pht' or pq_substr($ext,0,3)=='sht' or $ext=='phar' or $ext=='pgif'
          or $ext=='htm' or $ext=='html' ) {
        $fileName.='.projeqtor.txt';
      }
      if ($ext=='htaccess' or $ext=='htpasswd') {
        $fileName.='.projeqtor.txt';
      }
    }
    return $fileName;
  }
  public static function checkValidMimeType($mimeType) {
    $pattern = '/^a(pplication|udio)|image|m(essage|ultipart)|text|video|[xX]-([!-\x27*+\-0-9AZ^-~])+\/([!-\x27*+\-0-9AZ^-~])+(;([!-\x27*+\-0-9AZ^-~])+=(([!-\x27*+\-0-9AZ^-~])+|\"(([\x00-\x0c\x0e-\x21\x23-\x5b\x5d-\x7f]|((\r\n)?[ \t])+)|\\[\x00-\x7f])*\"))*$/'; // Content-Type according to rfc1341
    $mimeType=preg_match($pattern, pq_nvl($mimeType))?$mimeType:'text/html';
    return $mimeType;
  } 
  public static function checkEvilFile($file) {
    global $securityReturnJson;
    $securityReturnJson=true;
    if (pq_substr($file,-3)=='svg') {
      $image=file_get_contents($file);
      if (pq_strpos(pq_strtolower($image),'<script')!==false) {
        $msg="<div class='messageERROR' >Hack attempt detected : try to upload svg file with included script.<br/>The action and your IP has been traced.<input type='hidden' id='lastSaveId' value='' /><input type='hidden' id='lastOperation' value='insert' /><input type='hidden' id='lastOperationStatus' value='ERROR' /></div>";
        $jsonReturn='{"file":"'.htmlEncodeJson($file).'",'
            .'"name":"ERROR",'
            .'"type":"ERROR",'
            .'"size":"ERROR"  ,'
            .'"message":"'.$msg.'"}';
        $result=ob_get_clean();
        echo $jsonReturn;
        traceHack("try to upload svg file with included script ($file)");
        kill($file);
        exit;
        return false; // Not reached, trackHack exits scrips
      }
    }
  }
  public static function checkValidHtmlText($string) {
    // TODO (SECURITY) : use ctype_print()
    if (preg_match('/<script/', pq_nvl(pq_strtolower($string))) == true) {
      traceHack("invalid sequence in html text - $string");
    }
    if (preg_match('/onload|onshow|onclick|onchange|onmouseover|onmouseout|onkeydown|beforeunload|blur|oncontextmenu/', pq_nvl(pq_strtolower($string))) == true) {
      traceHack("invalid sequence in html text - $string");
    }
    return $string;
  }
  
  public static function checkValidUrl($string,$activeTraceHack=true) {
    if ($string=='') return false;
    if (! ctype_print($string) ) {
      if ($activeTraceHack) traceHack("invalid url (contains non printable characters) url='$string'");
      return false; // Not reached, trackHack exits scrips
    }
    //$string=filter_var($string, FILTER_VALIDATE_URL); // Not filtered yet : direct file acces
    if (preg_match('/\.\.\/|[<>]/',pq_nvl(urldecode($string))) == True) {
      //traceHack("invalid url value - [$string]"); // Maybe just an erroneous input, not always an hack attempt
      return false;
    }
    
    return $string;
  }
  public static function checkValidRequestValue($string) {
    if ($string===null) return null;
    if ($string=='') return '';
    if (is_array($string)) {
      foreach ($string as $id => $arr) {
        $string[$id]=self::checkValidRequestValue($arr);
      }
      return $string;
    } 
    //$string = preg_replace('/[\x00-\x1F\x7F\xA0]/u', '', $string);
    $string = preg_replace('/[\x00-\x09\x0B-\x1F\x7F\xA0]/u', '', $string); // keep line break	
//     if ( ctype_cntrl($string) ) { // Cannot be so easy : %E2%80%AF is valid and non printable
//       traceHack("invalid request value (contains non printable characters) value='$string'");
//       return false; // Not reached, trackHack exits scripts
//     }
    //$string=filter_var($string, FILTER_VALIDATE_URL); // Not filtered yet : direct file acces
    if (preg_match('/<script/', pq_nvl(pq_strtolower($string))) == true) {
      traceHack("invalid sequence in html request value - $string");
      return false; // Not reached, trackHack exits scripts
    }
    return $string;
  }
  
  public static function checkValidRequestField($string) {
    if ( preg_match('/^[a-zA-Z_\-\x7f-\xff][a-zA-Z0-9_\x7f-\xff]*$/',$string) ) {
      return $string;
    } else {
      traceHack("invalid name for request field name - $string");
      return false; // Not reached, trackHack exits scripts
    }
  }
  
  public static function checkValidLocale($string) {
    if (!$string) return;
    if (preg_match('/[^a-zA-Z]\-[^a-zA-Z]/', pq_nvl($string)) == true) {
      traceHack("invalid locale string value - $string");
    }
    return $string;
  }
  
  public static function checkValidAccessForUser($obj, $mode='read', $refType=null, $refId=null, $traceHack=true) {
    if (!$obj) {
      if ($refType and $refId) {
        if ($refType=='ResourceAllNoMaterial' or $refType=='ResourceAll') $refType='Resource';
        $obj=new $refType($refId);
      } else if ($refType and ! $refId) { // Here is dedicated check for jsonQuery
        $user=getSessionUser();
        $menuName='menu'.$refType;
        if ($menuName=='menuCalendarDefinition') $menuName='menuCalendar';
        if ($menuName=='menuBudgetItem') $menuName='menuBudget';
        if ($menuName=='menuBusinessFeature') $menuName='menuProduct';
        if ($menuName=='menuWork') $menuName='menuImputation';
        if ($menuName=='menuResourceAll') $menuName='menuResource';
        if ($menuName=='menuResourceAllNoMaterial') $menuName='menuResource';
        if ($menuName=='menuAccountable') $menuName='menuResource';
        if (SqlElement::is_subclass_of($refType, 'PlgCustomList')) $menuName='menuScreenCustomization';
        if (isLeavesSystemMenuByMenuName("menu".$refType)) {
          $showLeaveMenu=showLeavesSystemMenu("menu".$refType);
          if ( ! $showLeaveMenu) {
            if ($traceHack) traceHack("checkValidAccessForUser() Reject for $refType - no access to HR screen '$refType'");
            else return false;
          }
        } else {
          $check=Security::checkDisplayMenuForUser(pq_substr($menuName,4),false);
          if (!$check and $menuName=='menuTicketSimple') $check=Security::checkDisplayMenuForUser('Ticket',false);
          //if (!$check and $menuName=='menuAffectable') $check=Security::checkDisplayMenuForUser('User',false);
          if (!$check and $menuName=='menuAffectable') $check=Security::checkDisplayMenuForUser('Resource',false);
          //if (!$check and $menuName=='menuAffectable') $check=Security::checkDisplayMenuForUser('Contact',false);
          if (!$check and $menuName=='menuProductVersion' and RequestHandler::getBoolean('comboDetail')) $check=Security::checkDisplayMenuForUser('VersionsPlanning',false);
          if (!$check and $menuName=='menuComponentVersion' and RequestHandler::getBoolean('comboDetail')) $check=Security::checkDisplayMenuForUser('VersionsComponentPlanning',false);
          if ( ! $check ) {
            if ($traceHack) traceHack("checkValidAccessForUser() Reject for $refType - no access to screen '$refType'");
            else return false;
          } else {
            return true; // OK
          }
        }
      }
    }
    if (!$obj) return true;
    if (get_class($obj)=='Logfile') {
      $user=getSessionUser();
      $accessRightList = $user->getAccessControlRights ();
      if ( !isset($accessRightList['menuAdmin']) or !isset($accessRightList['menuAdmin']['read']) or $accessRightList['menuAdmin']['read']!='ALL' ) {
        if ($traceHack) traceHack("checkValidAccessForUser() Reject for ".get_class($obj)." - no access to administration screen");
        else return false;
      } else {
        return true; // OK
      }
    } else if (get_class($obj)=='Attachment') {
      // Access an attachment : must crontrol acess on item containing the attachment
      $refType=$obj->refType;
      $refId=$obj->refId;
      $obj=new $refType($refId);
      if (! property_exists($refType, '_Attachment')) {
        // referenced object does not have _Attachmen,t : so is image of user, no control
        return true;
      }
    } else if (get_class($obj)=='DocumentVersion') {  
      // Access on document version : must crontrol acess on document containing the version
      $obj=new Document($obj->idDocument);
    }
    if (!$obj->id and $mode!='create') {
      if ($traceHack) traceHack("checkValidAccessForUser() Reject for ".get_class($obj)." #".$obj->id." - no id for object on mode different from create");
      else return false;
    }
    $right = securityGetAccessRightYesNo( 'menu'.get_class($obj), $mode,$obj );
    #7466 - PBER : users with only access to TicketSimple should be able to see attachments to tickets through ticketsimple screen
    if ($right!='YES' and get_class($obj)=='Ticket') {
      $obj=new TicketSimple($obj->id);
      $right = securityGetAccessRightYesNo( 'menu'.get_class($obj), $mode,$obj );
    }
    if ($right!='YES') {
      if ($traceHack) traceHack("checkValidAccessForUser() Reject for ".get_class($obj)." #".$obj->id." - no '$mode' right to this item");
      else return false;
    }
    return true;
  }
  /**
   * 
   * @param string $menu : name of menu without the 'menu' prefix
   * @param boolean $traceHack
   */
  public static function checkDisplayMenuForUser($menu, $traceHack=true) {
    global $cronnedScript;
    if ($cronnedScript==true) return true;
    $user=getSessionUser();
    $check=securityCheckDisplayMenu(null, $menu, $user);
    if ($check==false and $traceHack==true) traceHack("checkDisplayMenuForUser() Reject for menu '$menu'");
    return $check;
  }
  public static function writeMetaCSP() {
    echo "<meta http-equiv=\"Content-Security-Policy\" content=\"script-src 'self' 'unsafe-inline' 'unsafe-eval'\">";
  }
  
  /**
   * Check that received URL does not have malicious syntax
   * Called on projeqtor.php (so for each call
   * @param string $menu : name of menu without the 'menu' prefix
   * @param boolean $traceHack
   */
  public static function checkValidAccess() {
    // Avoid non printable characters and '<script' in URL
    if (isset($_SERVER['QUERY_STRING'])) Security::checkValidRequestValue($_SERVER['QUERY_STRING']);
    if (isset($_SERVER['REQUEST_URI'])) Security::checkValidRequestValue($_SERVER['REQUEST_URI']);
    // Add other tests here
  }
  
  public static function checkValidEmail($email, $traceHack=false) {
    $check=preg_match('/^[a-zA-Z0-9._-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,4}$/', $email);
    if ($check==false and $traceHack==true) traceHack("invalid email format for '$email'");
    return $check;
  }
  
  public static function addTokenIndexToUrl($urlParam='') {
    global $tokenRequest, $indexRequest;
    if (!$tokenRequest) $tokenRequest=getSessionValue('Token');
    if (!$urlParam) $urlParam='';
    $paramAddStart='check';
    if ($urlParam=='') {
      $paramAddStart='no';
    } else if ($urlParam=='?') {
      $urlParam='';
      $paramAddStart='yes';
    } else if (pq_strpos($urlParam, "?") !==false) {
      $paramAddStart='no';
    } else {
      $paramAddStart='yes';
    }
    
    $urlParamExt='';
    
    if (pq_strpos($urlParam, "csrfToken=")===false) {
      $urlParamExt.=(($paramAddStart=='no')?'&':'?')."csrfToken=".$tokenRequest;
      $paramAddStart='no';
    }
    
    if (pq_strpos($urlParam, "directAccessIndex=")===false) {
      $urlParamExt.=(($paramAddStart=='no')?'&':'?')."directAccessIndex=".$indexRequest;
      $paramAddStart='no';
    }
    
    return $urlParamExt;
  }
}
 