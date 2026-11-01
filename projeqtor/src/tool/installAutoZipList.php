<?php 
/*** COPYRIGHT NOTICE *********************************************************
 *
******************************************************************************
*** WARNING *** T H I S    F I L E    I S    N O T    O P E N    S O U R C E *
******************************************************************************
*
* Copyright 2015 ProjeQtOr - Pascal BERNARD - support@projeqtor.org
*
* This file is an add-on to ProjeQtOr, packaged as a plug-in module.
* It is NOT distributed under an open source license.
* It is distributed in a proprietary mode, only to the customer who bought
* corresponding licence.
* The company ProjeQtOr remains owner of all add-ons it delivers.
* Any change to an add-ons without the explicit agreement of the company
* ProjeQtOr is prohibited.
* The diffusion (or any kind if distribution) of an add-on is prohibited.
* Violators will be prosecuted.
*
*** DO NOT REMOVE THIS NOTICE ************************************************/
function installAutoGetZipList($oneOnlyFile=null) {
  $error='';
  $dir="..".DIRECTORY_SEPARATOR."files".DIRECTORY_SEPARATOR."version";
  $mk=true;
  if (!file_exists($dir)) {
    $mk = mkdir($dir,0777,true);
  }
  if (!$mk or ! is_dir($dir)) {
    traceLog ("installAutoGetZipList() - directory '$dir' does not exist");
    $error="installAutoGetZipList() - directory '$dir' does not exist";
  }
  if (! $error) {
    $handle = opendir($dir);
    if (! is_resource($handle)) {
      traceLog ("installAutoGetZipList() - Unable to open directory '$dir' ");
      $error="installAutoGetZipList() - Unable to open directory '$dir' ";
    }
  }
  $files=array();
  while (!$error and ($file = readdir($handle)) !== false) {
    if ($file == '.' || $file == '..' || $file=='index.php') {
      continue;
    }
    $filepath = ($dir == '.') ? $file : $dir . DIRECTORY_SEPARATOR . $file;
    if (is_link($filepath)) {
      continue;
    }
    if ($oneOnlyFile and $oneOnlyFile!=$file) {
      continue;
    }
    if (is_file($filepath) and pq_strtolower(pq_substr($file,-4))=='.zip') {
      $fileDesc=array('name'=>$file,'path'=>$filepath);
      $dt=filemtime ($filepath);
      $date=date('Y-m-d H:i',$dt);
      $fileDesc['date']=$date;
      $fileDesc['size']=filesize($filepath);
      $files[]=$fileDesc;
    }
  }
  if (! $error) closedir($handle);
  return $files;
}

function installAutoGetZipListTmp($oneOnlyFile=null) {
  $error='';
  $dir="..".DIRECTORY_SEPARATOR."files".DIRECTORY_SEPARATOR."version".DIRECTORY_SEPARATOR."tmp";
  $mk=true;
  if (!file_exists($dir)) {
    $mk = mkdir($dir,0777,true);
  }
  if (!$mk or ! is_dir($dir)) {
    traceLog ("installAutoGetZipListTmp() - directory '$dir' does not exist");
    $error="installAutoGetZipListTmp() - directory '$dir' does not exist";
  }
  if (! $error) {
    $handle = opendir($dir);
    if (! is_resource($handle)) {
      traceLog ("installAutoGetZipListTmp() - Unable to open directory '$dir' ");
      $error="installAutoGetZipListTmp() - Unable to open directory '$dir' ";
    }
  }
  $files=array();
  while (!$error and ($file = readdir($handle)) !== false) {
    if ($file == '.' || $file == '..' || $file=='index.php') {
      continue;
    }
    $filepath = ($dir == '.') ? $file : $dir . DIRECTORY_SEPARATOR . $file;
    if (is_link($filepath)) {
      continue;
    }
    if ($oneOnlyFile and $oneOnlyFile!=$file) {
      continue;
    }
    if (is_file($filepath) and pq_strtolower(pq_substr($file,-4))=='.zip') {
      $fileDesc=array('name'=>$file,'path'=>$filepath);
      $dt=filemtime ($filepath);
      $date=date('Y-m-d H:i',$dt);
      $fileDesc['date']=$date;
      $fileDesc['size']=filesize($filepath);
      $files[]=$fileDesc;
    }
  }
  if (! $error) closedir($handle);
  return $files;
}

function getFileInfo($url){
  if (!$url) {
    errorLog("file transfer issue : cannot get correct url");
    echo i18n('installAutoErrorDownload').'<br/>(incorrect url = \''.$url.'\')';
  }
  $ch = curl_init($url);
  $proxy=Parameter::getGlobalParameter("paramProxy");
  $proxyUser=Parameter::getGlobalParameter("paramProxyUser");
  $proxyPassword=Parameter::getGlobalParameter("paramProxyPassword"); 
  if (preg_match('`^https://`i', $url)) {
    curl_setopt($ch, CURLOPT_SSL_VERIFYPEER, false);
    curl_setopt($ch, CURLOPT_SSL_VERIFYHOST, 0);
  }
  if (isset($proxy) and $proxy) {
    $split=explode("://",$proxy);
    if (count($split)>1) $proxy=$split[1];
    curl_setopt($ch, CURLOPT_FRESH_CONNECT, true);
    curl_setopt($ch, CURLOPT_TIMEOUT, 10);
    curl_setopt($ch, CURLOPT_CONNECTTIMEOUT, 10);
    curl_setopt($ch, CURLOPT_PROXY, $proxy); 
    curl_setopt($ch, CURLOPT_FOLLOWLOCATION, true);
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, false);
    //curl_setopt($ch, CURLOPT_HTTPPROXYTUNNEL, true);
    if (isset($proxyUser) and $proxyUser and isset($proxyPassword) and $proxyPassword) {
      $proxyauth="$proxyUser:$proxyPassword";
      curl_setopt($ch, CURLOPT_PROXYUSERPWD, $proxyauth);
    }
  } else {
    curl_setopt( $ch, CURLOPT_NOBODY, true );
    curl_setopt( $ch, CURLOPT_HEADER, false );
    curl_setopt( $ch, CURLOPT_RETURNTRANSFER, false );
    curl_setopt( $ch, CURLOPT_FOLLOWLOCATION, true );
    curl_setopt( $ch, CURLOPT_MAXREDIRS, 3 );
  }
  curl_exec( $ch );
  $headerInfo = curl_getinfo( $ch );
  curl_close( $ch );
  return $headerInfo;
}
function getRemoteFile($fileName) {
  ini_set('default_socket_timeout', 10); // Very short timeout
  $proxy=Parameter::getGlobalParameter("paramProxy");
  $proxyUser=Parameter::getGlobalParameter("paramProxyUser");
  $proxyPassword=Parameter::getGlobalParameter("paramProxyPassword");
  if (isset($proxy)) {
    if (isset($proxyUser) and $proxyUser and isset($proxyPassword) and $proxyPassword) {
      $auth = base64_encode("$proxyUser:$proxyPassword");
      $aContext = array(
          'http' => array(
              'proxy' => $proxy,
              'timeout' => 10,
              'request_fulluri' => true,
              'header' => "Proxy-Authorization: Basic $auth",
          ),
      );
    } else {
      $aContext = array(
          'http' => array(
              'proxy' => $proxy,
              'timeout' => 10,
              'request_fulluri' => true,
          ),
      );
    }
    $cxContext = stream_context_create($aContext);
  } else {
  	//     $aContext = array(
  	//         'http' => array(
  	//             'timeout' => 10,
  	//         ),
  	//     );
  	$cxContext=null;
  }
  enableCatchErrors();
  return file_get_contents($fileName,false,$cxContext);
  disableCatchErrors();
}
function fileDownload($url, $destination){
  $dir="..".DIRECTORY_SEPARATOR."files".DIRECTORY_SEPARATOR."version".DIRECTORY_SEPARATOR."tmp";
  $mk = true;
  if (!file_exists($dir)) {
    $mk = mkdir($dir,0777,true);
  }
  if($mk){
    $fp = fopen ($destination, 'w+');
    $ch = curl_init();
    $proxy=Parameter::getGlobalParameter("paramProxy");
    $proxyUser=Parameter::getGlobalParameter("paramProxyUser");
    $proxyPassword=Parameter::getGlobalParameter("paramProxyPassword");
    if (preg_match('`^https://`i', $url)) {
      curl_setopt($ch, CURLOPT_SSL_VERIFYPEER, false);
      curl_setopt($ch, CURLOPT_SSL_VERIFYHOST, 0);
    }
    curl_setopt( $ch, CURLOPT_RETURNTRANSFER, false );
    curl_setopt( $ch, CURLOPT_URL, $url );
    curl_setopt( $ch, CURLOPT_BINARYTRANSFER, true );
    curl_setopt($ch, CURLOPT_TIMEOUT, 1000);
    curl_setopt( $ch, CURLOPT_CONNECTTIMEOUT, 1000);
    if (isset($proxy) and $proxy) {
      $split=explode("://",$proxy);
      if (count($split)>1) $proxy=$split[1];
      //curl_setopt($ch, CURLOPT_FRESH_CONNECT, true);
      curl_setopt($ch, CURLOPT_PROXY, $proxy);
      curl_setopt($ch, CURLOPT_FOLLOWLOCATION, true);
      curl_setopt($ch, CURLOPT_RETURNTRANSFER, false);
      //curl_setopt($ch, CURLOPT_HTTPPROXYTUNNEL, true);
      if (isset($proxyUser) and $proxyUser and isset($proxyPassword) and $proxyPassword) {
        $proxyauth="$proxyUser:$proxyPassword";
        curl_setopt($ch, CURLOPT_PROXYUSERPWD, $proxyauth);
      }
    } else {
      curl_setopt( $ch, CURLOPT_RETURNTRANSFER, false );
    }
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, false);
    curl_setopt( $ch, CURLOPT_FILE, $fp );
    curl_exec( $ch );
    curl_close( $ch );
    fclose( $fp );
    if (filesize($destination) > 0) return true;
  }else{
    errorLog("file download issue : can't create $dir");
    return "file download issue : can't create $dir";
  }
}
?>