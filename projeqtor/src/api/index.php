<?php
/*** COPYRIGHT NOTICE *********************************************************
 *
 * Copyright 2009-2017 ProjeQtOr - Pascal BERNARD - support@projeqtor.org
 * Contributors : 
 *   => mamath : fix #1510
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

// For security reasons, this code can be disabled to avoid API access
// To disable API, just add $paramDisableAPI=true; in your parameters.php file
if (isset($paramDisableAPI) and $paramDisableAPI) {
  die();
}
$querySyntax='Possible values are :  
GET    ../api/{objectClass}/{objectId}
       ../api/{objectClass}/all
       ../api/{objectClass}/filter/{filterId}
       ../api/{objectClass}/search/criteria1/criteria2/... (criteria as sql where clause)
       ../api/{objectClass}/updated/{YYYYMMDDHHMNSS}/{YYYYMMDDHHMNSS}
       ../api/Cron/{cmd} with cmd = "start", "stop", restart", "check"
       ../api/{objectClass}/{objectId}/select={colum_name}
       ../api/{objectClass}/all/select={colum_name}
PUT    ../api/{objectClass} with data containing json description of items
POST   ../api/{objectClass} with data containing json description of items
DELETE ../api/{objectClass} with data containing json id of items';
$invalidQuery="invalid API query";

// $cronnedScript=true;
$batchMode=true;
$apiMode=true;
$contextForAttributes='global';
require_once "../tool/projeqtor.php";
require_once "../external/phpAES/aes.class.php";
require_once "../external/phpAES/aesctr.class.php";
require_once '../tool/jsonFunctions.php';

$batchMode=false;
// Look for user : can be found in
// $_SERVER['PHP_AUTH_USER']
// $_SERVER['REMOTE_USER']
// $_SERVER['REDIRECT_REMOTE_USER']
// http_digest_parse($_SERVER['PHP_AUTH_DIGEST'])['username']
$username="";
if (isset($_SERVER['PHP_AUTH_USER'])) {
  $username=$_SERVER['PHP_AUTH_USER'];
} else if (isset($_SERVER['REMOTE_USER'])) {
  $username=$_SERVER['REMOTE_USER'];
} else if (isset($_SERVER['REDIRECT_REMOTE_USER'])) {
  $username=$_SERVER['REDIRECT_REMOTE_USER'];
} else if (isset($_SERVER['PHP_AUTH_DIGEST'])) {
  $digest=http_digest_parse($_SERVER['PHP_AUTH_DIGEST']);
  if ($digest and isset($digest['username'])) {
    $username=$digest['username'];
  }
}
if ($username) {
  $user=SqlElement::getSingleSqlElementFromCriteria('User', array('name'=>$username));
  $user->_API=true;
} else {
  $user=new User();
  $cronnedScript=true;
}
if (!$user->id) {
  returnError($invalidQuery, "user '$username' unknown in database");
}
if ($user->idle or $user->locked) {
  returnError($invalidQuery, "user '$username' disabled");
}
traceLog("API : mode=" . $_SERVER['REQUEST_METHOD'] . " user=$user->name, id=$user->id, profile=$user->idProfile");
setSessionUser($user);

header('Content-Type: application/json; charset=UTF-8');
if ($_SERVER['REQUEST_METHOD']=='GET') {
  set_time_limit(0); // Remove all possibilities for Timeout
                     // GET method : security => class is checked, id is numerically filtered, access right is applied
  if (isset($_REQUEST['uri'])) {
    // $uri=htmlEncode($_REQUEST['uri']);
    $uri=$_REQUEST['uri'];
    if (isset($_SERVER['QUERY_STRING']) and pq_substr($_SERVER['QUERY_STRING'], 0, 4)=='uri=') {
      $uri=pq_str_replace('+', ' ', pq_substr($_SERVER['QUERY_STRING'], 4));
    } else if (isset($_SERVER['REQUEST_URI'])) {
      $pos=pq_strpos($_SERVER['REQUEST_URI'], '/api/');
      if ($pos>-1) $uri=urldecode((pq_substr($_SERVER['REQUEST_URI'], $pos+5)));
    }
    $split=explode('/', $uri);
    $hasSelectClause=(pq_substr($split[count($split)-1], 0, 7)=='select=')?true:false;
    $nbSplit=count($split);
    $selectedFields=null;
    if ($hasSelectClause) {
      $nbSplit--;
      $lastValue=$split[count($split)-1];
      $fields=pq_substr($lastValue,7);
      unset($split[count($split)-1]);
      $selectedFields=explode(',',$fields);
    }
    if ($nbSplit>1) {
      $selectMode=false;
      $class=pq_ucfirst($split[0]);
      $where="1=0";
      // $where="";
      if (SqlElement::class_exists($class)) {
        if ($class!='Cron') {
          Security::checkValidClass($class);
          $obj=new $class();
          $table=$obj->getDatabaseTableName();
//           $columnMap=array();
//           $sqlCols="
//             SELECT COLUMN_NAME
//             FROM INFORMATION_SCHEMA.COLUMNS
//             WHERE TABLE_SCHEMA = DATABASE()
//               AND TABLE_NAME = '$table'
//           ";
//           $resCols=Sql::query($sqlCols);
//           while ($col=Sql::fetchLine($resCols)) {
//             $lc=strtolower($col['COLUMN_NAME']);
//             $columnMap[$lc]=$col['COLUMN_NAME'];
//           }
        }
        if ($class=='Cron') {
          $cmd=$split[1];
          if ($cmd=='start') {
            if (Cron::check()=='running') {
              echo '{"cronStatus":"running"}';
              exit();
            } else {
              // if ( isset( $_COOKIE[session_name()] ) )
              // setcookie( session_name(), “”, time()-3600, “/” );
              // $_SESSION = array();
              // session_destroy();
              // session_start();
              // echo '{"cronStatus":"started"}';
              // ignore_user_abort(1);
              // function cronAbort() {Cron::abort();}
              // register_shutdown_function('cronAbort');
              // error_reporting(0);
              // session_write_close();
              Cron::run();
              exit();
            }
          } else if ($cmd=='stop') {
            if (Cron::check()=='running') {
              echo '{"cronStatus":"stopping"}';
              Cron::setStopFlag();
              exit();
            } else {
              echo '{"cronStatus":"stopped"}';
            }
          } else if ($cmd=='restart') {
            if (Cron::check()=='running') {
              echo '{"cronStatus":"running"}';
              exit();
            } else {
              Cron::run();
              echo '{"cronStatus":"started"}';
              exit();
            }
          } else if ($cmd=='check') {
            echo '{"cronStatus":"' . Cron::check() . '"}';
            exit();
          } else {
            returnError($invalidQuery, $querySyntax);
          }
        } else if ($nbSplit==2 and is_numeric($split[1])) { // =============== uri = {OblectClass}/{ObjectId}
          $id=$split[1];
          $where="id=" . Sql::fmtId($id);
        } else if ($nbSplit==2 and $split[1]=='all') { // =============== uri = {OblectClass}/all
          $where="1=1";
        } else if ($nbSplit==4 and $split[1]=='updated') { // =============== uri = {OblectClass}/update/{YYYYMMDDHHMNSS}/{YYYYMMDDHHMNSS}
          $beg=$split[2];
          $end=$split[3];
          if ($class=='Work') {
            $begDate=pq_substr($beg, 0, 8);
            $endDate=pq_substr($end, 0, 8);
            $where="day>=" . Sql::str($begDate) . " and day<=" . Sql::str($endDate);
          } else {
            $begDate=pq_substr($beg, 0, 4) . '-' . pq_substr($beg, 4, 2) . '-' . pq_substr($beg, 6, 2) . ' ' . pq_substr($beg, 8, 2) . ':' . pq_substr($beg, 10, 2) . ':' . pq_substr($beg, 12, 2);
            $endDate=pq_substr($end, 0, 4) . '-' . pq_substr($end, 4, 2) . '-' . pq_substr($end, 6, 2) . ' ' . pq_substr($end, 8, 2) . ':' . pq_substr($end, 10, 2) . ':' . pq_substr($end, 12, 2);
            if (0 and property_exists($class, 'lastUpdateDateTime')) { //
                                                                       // PBER : try that is desactivated : will trigger change on activity but not cvonsolidation on its parent activity
              $where="lastUpdateDateTime>='$begDate' and lastUpdateDateTime<'$endDate'";
            } else {
              $hist=new History();
              $crit="refType='$class' and operationDate>='$begDate' and operationDate<'$endDate'";
              $peName=$class . 'PlanningElement';
              if (property_exists($class, $peName)) {
                $crit="(refType='$class' or refType='$peName') and operationDate>='$begDate' and operationDate<'$endDate'";
              }
              $histList=$hist->getSqlElementsFromCriteria(null, null, $crit);
              $hAr=array();
              foreach ($histList as $hist) {
                if ($hist->refType==$class) $histRefId=$hist->refId;
                else $histRefId=SqlList::getFieldFromId($peName, $hist->refId, 'refId');
                $hAr[$histRefId]=$histRefId;
              }
              if (count($hAr)==0) {
                $where="id=0";
              } else {
                $where="id in (" . implode(',', $hAr) . ")";
              }
            }
          }
        } else if ($nbSplit==3 and $split[1]=='filter') { // =============== uri = {OblectClass}/filter/{filterId}
          $filterId=$split[2];
          $crit=new FilterCriteria();
          $critList=$crit->getSqlElementsFromCriteria(array('idFilter'=>$filterId, 'isReportList'=>'0'));
          $where=(count($critList)>0)?"1=1":"1=0";
          $idTab=0;
          foreach ($critList as $crit) {
            if ($crit->sqlOperator!='SORT' and !$crit->isDynamic) {
              $split=explode('_', $crit->sqlAttribute);
              $critSqlValue=$crit->sqlValue;
              if ($crit->sqlOperator=='IN' and ($crit->sqlAttribute=='idProduct' or $crit->sqlAttribute=='idProductOrComponent' or $crit->sqlAttribute=='idComponent')) {
                $critSqlValue=pq_str_replace(array(' ', '(', ')'), '', $critSqlValue);
                $splitVal=explode(',', $critSqlValue);
                $critSqlValue='(0';
                foreach ($splitVal as $idP) {
                  $prod=new Product($idP);
                  $critSqlValue.=', ' . $idP;
                  $list=$prod->getRecursiveSubProductsFlatList(false, false);
                  foreach ($list as $idPrd=>$namePrd) {
                    $critSqlValue.=', ' . $idPrd;
                  }
                }
                $critSqlValue.=')';
              }
              if ($nbSplit>1) {
                $externalClass=$split[0];
                $externalObj=new $externalClass();
                $externalTable=$externalObj->getDatabaseTableName();
                $idTab+=1;
                // $externalTableAlias = 'T' . $idTab;
                // $queryFrom .= ' left join ' . $externalTable . ' as ' . $externalTableAlias .
                // ' on ( ' . $externalTableAlias . ".refType='" . get_class($obj) . "' and " . $externalTableAlias . '.refId = ' . $table . '.id )';
                // $queryWhere.=($queryWhere=='')?'':' and ';
                // $queryWhere.=$externalTableAlias . "." . $split[1] . ' ' //// !!! Sql Injection
                // . $crit['sql']['operator'] . ' '
                // . $critSqlValue;
              } else {
                $where.=($where=='')?'':' and ';
                $where.="(" . $table . "." . $crit->sqlAttribute . ' ' . $crit->sqlOperator . $critSqlValue;
                if (pq_strlen($crit->sqlAttribute)>=9 and pq_substr($crit->sqlAttribute, 0, 2)=='id' and (pq_substr($crit->sqlAttribute, -7)=='Version' and SqlElement::is_a(pq_substr($crit->sqlAttribute, 2), 'Version')) and $crit->sqlOperator=='IN') {
                  $scope=pq_substr($crit->sqlAttribute, 2);
                  $vers=new OtherVersion();
                  $where.=" or exists (select 'x' from " . $vers->getDatabaseTableName() . " VERS " . " where VERS.refType=" . Sql::str($class) . " and VERS.refId=" . $table . ".id and scope=" . Sql::str($scope) . " and VERS.idVersion IN " . $critSqlValue . ")";
                }
                $where.=")";
              }
            }
          }
        } else if ($nbSplit>=2 and $split[1]=='search') { // =============== uri = {OblectClass}/search
          $cpt=2;
          $where="";
          while (isset($split[$cpt])) {
            $where.=($where)?" and ":'';
            $where.='(';
            $addWhere=$split[$cpt];
            // if ( pq_strpos(pq_strtolower($addWhere), 'like')>-1) $addWhere=pq_str_replace('*','%',$addWhere);
            $addWhere=pq_str_replace('id IN ()', 'id IN (0)', $addWhere);
            $where.=$addWhere;
            $where.=')';
            $cpt++;
          }
          //
          $where=$obj->replaceDatabaseColumnNameInWhereClause($where);
        } else {
          returnError($invalidQuery, $querySyntax);
        }
        // Add access restrictions
        if ($class!='Affectation' and $class!='Assignment' and property_exists($class, 'refType') and property_exists($class, 'refId')) {
          // No control : will be applied later
        } else if ($class=='ProjectHistory') {
          // No control : will be applied later
        } else {
          $getAccesRestrictionClause=getAccesRestrictionClause($class, null, true);
          $where.=' and ' . $getAccesRestrictionClause; // GOOD : access limit is applied !!!
        }
        echo '{"identifier":"id",';
        echo ' "items":[';
        $where=pq_str_replace('id IN  and ', 'id IN (0) and ', $where);
        $list=$obj->getSqlElementsFromCriteria(null, null, $where);
        debugTraceLog("API Call  => found " . count($list) . " items");
        $cpt=0;
        foreach ($list as $obj) {
          if ($class!='Affectation' and $class!='Assignment' and property_exists($class, 'refType') and property_exists($class, 'refId')) {
            $objRefClass=$obj->refType;
            $objRef=new $objRefClass($obj->refId, true);
            if (securityGetAccessRightYesNo('menu' . $objRefClass, 'read', $objRef)!="YES") continue;
          } else if ($class=='ProjectHistory') {
            $proj=new Project($obj->idProject);
            if (securityGetAccessRightYesNo('menuProject', 'read', $proj)!="YES") continue;
          }
          if ($cpt) echo ",";
          $cpt++;
          echo '{' . jsonDumpObj($obj,null,null,$selectedFields) . '}';
        }
        debugTraceLog("          => finished");
        echo ']';
        echo ' }';
      } else {
        returnError($invalidQuery, i18n("invalidClassName", array($class)));
      }
    } else {
      returnError($invalidQuery, $querySyntax);
    }
  } else {
    returnError($invalidQuery, $querySyntax);
  }
} else IF ($_SERVER['REQUEST_METHOD']=='PUT' or $_SERVER['REQUEST_METHOD']=='POST' or $_SERVER['REQUEST_METHOD']=='DELETE') {
  // PUT, POST or DELETE : security => data is encoded with API Key (AES 128, 192 or 256 depending on $aesKeyLength)
  // So caller needs correct User/Password and API Key.
  // We can trust data.
  // NB : access rights will be controlled on insert/update/delete (!)
  $multipart = false;
  if (isset($_REQUEST['data'])) {
    $dataEncoded=$_REQUEST['data'];
    $data=AesCtr::decrypt($dataEncoded, $user->apiKey, Parameter::getGlobalParameter('aesKeyLength'));
    
  } else {
    $raw=file_get_contents("php://input");
    $ct  = $_SERVER['CONTENT_TYPE'] ?? '';
    $extracted = extractMultipartDataAndFile($raw, $ct);
    $dataEncoded = $extracted['data'];
    $data=AesCtr::decrypt($dataEncoded, $user->apiKey, Parameter::getGlobalParameter('aesKeyLength'));
  }
  if (!$data) {
    returnError($invalidQuery, "'data' missing for method " . $_SERVER['REQUEST_METHOD']);
  }
  $file=null;
  if (isset($_REQUEST['file'])) {
    $file=$_REQUEST['file'];
  }else if(isset($_FILES['file'])){
    $file = $_FILES['file'];
    $multipart=true;
  }else if(isset($extracted)){
    $file = $extracted['file'];
    //$multipart=true;
  }
  
  $class="";
  $uri=htmlEncode($_REQUEST['uri']);
  $split=explode('/', $uri);
  $nbSplit=count($split);
  if ($nbSplit>0) {
    $class=pq_ucfirst($split[0]);
  }
  
  if (!SqlElement::class_exists($class)) {
    returnError($invalidQuery, "'$class' is not a known object class");
  }
  $dataArray=@json_decode($data, true);
  if (!$dataArray) {
    returnError($invalidQuery, "'data' is not correctly encoded for method " . $_SERVER['REQUEST_METHOD'] . ". Request for correct API KEY");
  }
  if (isset($dataArray['items'])) {
    $arrayData=$dataArray['items'];
  } else {
    $arrayData=array($dataArray);
  }
  $cpt=0;
  echo '{"identifier":"id", "items":[';
  foreach ($arrayData as $objArray) {
    Sql::beginTransaction();
    $id=null;
    if (isset($objArray['id'])) $id=$objArray['id'];
    $obj=new $class($id);
    if ($_SERVER['REQUEST_METHOD']=='PUT' or $_SERVER['REQUEST_METHOD']=='POST') {
      jsonFillObj($obj, $objArray);
      if (get_class($obj)=="Work") {
        $result=$obj->saveWork(); // Specific save method for import and API
      } else {
        $result=$obj->save();
      }
      if($class == 'Attachment'){
        $refType = Security::checkValidClass($obj->refType);
        $refId = Security::checkValidId($obj->refId);
        $refObj = new $refType($refId);
        if($refObj->name and property_exists($refObj, '_Attachment')){
          $pathSeparator=Parameter::getGlobalParameter('paramPathSeparator');
          $attachmentDirectory=Parameter::getGlobalParameter('paramAttachmentDirectory');
          
          if($multipart){
            $fileName = Security::checkValidFileName($file['name'],true, true);
            $fileSize = $file['size'];
            $fileType = $file['type'];
          }else{
            $fileName = Security::checkValidFileName($obj->fileName,true, true);
            $fileType = getMimeTypeFromFileName($fileName);
          }
          
          $uploaddir = $attachmentDirectory . $pathSeparator . "attachment_" . $obj->id . $pathSeparator;
          if (! file_exists($uploaddir)) {
            mkdir($uploaddir,0777,true);
          }
          $paramFilenameCharset=Parameter::getGlobalParameter('filenameCharset');
          if ($paramFilenameCharset) {
            $uploadfile = $uploaddir . iconv("UTF-8", $paramFilenameCharset.'//TRANSLIT//IGNORE',$fileName);
          } else {
            $uploadfile = $uploaddir . $fileName;
          }
          
          if($multipart){
            $tmpPath  = $file['tmp_name'];
            if ( ! move_uploaded_file($tmpPath, $uploadfile)) {
              $subResult = htmlGetErrorMessage(i18n('errorUploadFile',array('missing file on multipart')));
              errorLog(i18n('errorUploadFile',array('missing file')));
              $obj->delete();
            } else {
              Security::checkEvilFile($uploadfile);
              $obj->subDirectory=pq_str_replace(Parameter::getGlobalParameter('paramAttachmentDirectory'),'${attachmentDirectory}',$uploaddir);
              $obj->fileSize = $fileSize;
              $obj->mimeType = $fileType;
              $obj->type='file';
              $obj->creationDate = date('Y-m-d H:i:s');
              $subResult=$obj->save();
            }
          }else{
            $tmpPath = $uploadfile;
            if ( ! file_put_contents($uploadfile, $file) and $obj->type=='file') {
              $subResult = htmlGetErrorMessage(i18n('errorUploadFile',array('missing file on fields array')));
              errorLog(i18n('errorUploadFile',array('missing file on fields array')));
              $obj->delete();
            } else {
              Security::checkEvilFile($uploadfile);
              $obj->subDirectory=pq_str_replace(Parameter::getGlobalParameter('paramAttachmentDirectory'),'${attachmentDirectory}',$uploaddir);
              $obj->fileSize = filesize($uploadfile);
              $obj->mimeType = $fileType;
              if (!$obj->type) $obj->type='file';
              $obj->creationDate = date('Y-m-d H:i:s');
              $subResult=$obj->save();
            }
          }
          if($subResult)$result=$subResult;
        }else{
          $subResult = htmlGetErrorMessage(i18n('noAccessToThisElement'));
          errorLog(i18n('noAccessToThisElement'));
          $obj->delete();
        }
      }
    } else if ($_SERVER['REQUEST_METHOD']=='DELETE') {
      if (get_class($obj)=="Work") {
        $result=$obj->deleteWork(); // Specific delete method for import and API
      } else {
        SqlElement::setDeleteConfirmed();
        $result=$obj->delete();
      }
    }
    $resultStatus="KO";
    $search='id="lastOperationStatus" value="';
    $pos=pq_strpos($result, $search);
    if ($pos) {
      $posDeb=$pos+pq_strlen($search);
      $posFin=pq_strpos($result, '"', $posDeb);
      $resultStatus=pq_substr($result, $posDeb, $posFin-$posDeb);
    }
    $pos=pq_strpos($result, '<input type="hidden"'); // Search first tag
    if ($pos) {
      $result=pq_substr($result, 0, $pos);
    }
    if ($resultStatus=="OK") {
      Sql::commitTransaction();
    } else {
      Sql::rollbackTransaction();
    }
    $result=str_ireplace(array('<b>', '</b>', '<br/>', '<br>'), array('', '', ' ', ' '), $result);
    $obj=new $class($obj->id); // refresh object to display calculated values in return
    if ($cpt) echo ",";
    $cpt++;
    echo '{"apiResult":"' . $resultStatus . '", "apiResultMessage":"' . htmlEncodeJson($result) . '", ' . jsonDumpObj($obj,null,null,null) . '}';
  }
  // print_r($arrayData);
  echo '] }';
} else {
  returnError($invalidQuery, 'method ' . $_SERVER['REQUEST_METHOD'] . ' not taken into acocunt in this API');
}

function returnError($error, $message) {
  echo '{"error":"' . $error . '", "message":"' . json_encode($message) . '"}';
  exit();
}

function jsonFillObj(&$obj, $arrayObj, $included=false) {
  $res="";
  if (method_exists($obj, 'setAttributes')) {
    $obj->setAttributes();
  }
  foreach ($obj as $fld=>$val) {
    if (is_object($val)) {
      jsonFillObj($val, $arrayObj, true);
    } else if (pq_substr($fld, 0, 1)=='_' or $obj->isAttributeSetToField($fld, 'hidden') or $fld=='apiKey' or $fld=='password' or ($included and ($fld=='id' or $fld=='refType' or $fld=='refId' or $fld=='refName' or $fld=='handled' or $fld=='done' or $fld=='idle' or $fld=='cancelled'))) {
      // Nothing
    } else {
      if (isset($arrayObj[$fld])) {
        $obj->$fld=$arrayObj[$fld];
      }
    }
  }
}

function http_digest_parse($txt) {
  // protect against missing data
  $needed_parts=array('nonce'=>1, 'nc'=>1, 'cnonce'=>1, 'qop'=>1, 'username'=>1, 'uri'=>1, 'response'=>1);
  $data=array();
  $keys=implode('|', array_keys($needed_parts));
  preg_match_all('@(' . $keys . ')=(?:([\'"])([^\2]+?)\2|([^\s,]+))@', pq_nvl($txt), $matches, PREG_SET_ORDER);

  foreach ($matches as $m) {
    $data[$m[1]]=$m[3]?$m[3]:$m[4];
    unset($needed_parts[$m[1]]);
  }

  return $needed_parts?false:$data;
}

function extractMultipartDataAndFile(string $rawBody, string $contentTypeHeader): array {
  $out = ['data' => $rawBody, 'file' => null];
  
  if (!preg_match('/boundary=(?:"([^"]+)"|([^;]+))/i', $contentTypeHeader, $m)) {
    return $out;
  }
  $boundary = $m[1] !== '' ? $m[1] : $m[2];
  $boundary = trim($boundary);
  
  $delimiter = "--" . $boundary;
  
  // 2) Split parts (binary-safe)
  $parts = explode($delimiter, $rawBody);
  
  foreach ($parts as $part) {
    $part = ltrim($part, "\r\n");
    $part = rtrim($part, "\r\n");
    
    if ($part === '' || $part === '--') {
      continue;
    }
    
    // 3) split headers / body
    $pos = strpos($part, "\r\n\r\n");
    if ($pos === false) {
      continue;
    }
    
    $headersText = substr($part, 0, $pos);
    $body = substr($part, $pos + 4); // after \r\n\r\n
    
    // With multipart, body often end with \r\n
    if (substr($body, -2) === "\r\n") {
      $body = substr($body, 0, -2);
    }
    
    if (!preg_match('/\bContent-Disposition:\s*form-data;\s*name="([^"]+)"/i', $headersText, $hm)) {
      continue;
    }
    $name = $hm[1];
    
    if ($name === 'data') {
      $out['data'] = $body;
    } elseif ($name === 'file') {
      $out['file'] = $body;
    }
  }
  
  return $out;
}

?>