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

//chdir('../');
include_once "../tool/projeqtor.php";
/*if ($_SERVER['REQUEST_METHOD'] != "POST" or securityGetAccessRightYesNo('menuPlgInstallAuto','read')!='YES') {
  traceHack ( "flpg installation tried without access right" );
  exit ();
}*/
header ('Content-Type: text/html; charset=UTF-8');
/** ===========================================================================
 * Save a document version (file) : call corresponding method in SqlElement Class
 * The new values are fetched in $_REQUEST
 */

// ATTENTION, this PHP script returns its result into an iframe (the only way to submit a file)
// then the iframe returns the result to resultDiv to reproduce expected behaviour
$isIE=false;
if (pq_array_key_exists('isIE',$_REQUEST)) {
  $isIE=$_REQUEST['isIE'];
} 
if ($isIE and $isIE<=9) {?>
<html>
<head>   
</head>
<body onload="parent.installAutoSaveAck();">
<?php } else { ob_start();}?>
<?php 
$error=false;
$uploadedFile=false;
projeqtor_set_time_limit(3600); // 60mn
$attachmentMaxSize=Parameter::getGlobalParameter('paramAttachmentMaxSize');
$uploadedFileArray=array();
if(intval(ini_get("upload_max_filesize")<50)){
  $error=htmlGetErrorMessage(i18n('installAutoErrorUpload'));
  echo $error;
  errorLog(pq_str_replace("\\","",i18n('installAutoErrorUpload')));
  $error=true;
  exit;
}
if (pq_array_key_exists('installAutoFile',$_FILES)) {
  $uploadedFileArray[]=$_FILES['installAutoFile'];
} else if (pq_array_key_exists('uploadedfile0',$_FILES)) {
  $cnt = 0;
  while(isset($_FILES['uploadedfile'.$cnt])){
  		$uploadedFileArray[]=$_FILES['uploadedfile'.$cnt];
  }
} else if (pq_array_key_exists('installAutoFile',$_FILES) and pq_array_key_exists('name',$_FILES['installAutoFile'])) {
  for ($i=0;$i<count($_FILES['installAutoFile']['name']);$i++) {
    $uf=array();
    $uf['name']=$_FILES['installAutoFile']['name'][$i];
    $uf['type']=$_FILES['installAutoFile']['type'][$i];
    $uf['tmp_name']=$_FILES['installAutoFile']['tmp_name'][$i];
    $uf['error']=$_FILES['installAutoFile']['error'][$i];
    $uf['size']=$_FILES['installAutoFile']['size'][$i];
    $uploadedFileArray[$i]=$uf;
  }
} else {
  $error=htmlGetErrorMessage(i18n('errorTooBigFile',array($attachmentMaxSize,'paramAttachmentMaxSize')));
  errorLog(i18n('errorTooBigFile',array($attachmentMaxSize,'paramAttachmentMaxSize')));
  //$error=true;
}

foreach ($uploadedFileArray as $uploadedFile) {
  if (! $error) {
    if ( $uploadedFile['error']!=0) {
      //$error="[".$uploadedFile['error']."] ";
      errorLog("[".$uploadedFile['error']."] installAutoUpload.php");
      //$error=true;
      switch ($uploadedFile['error']) {
      	case 1:
      	  $error.=htmlGetErrorMessage("[".$uploadedFile['error']."] ".i18n('errorTooBigFile',array(ini_get('upload_max_filesize'),'upload_max_filesize')));
      	  errorLog(i18n('errorTooBigFile',array(ini_get('upload_max_filesize'),'upload_max_filesize')));
      	  break;
      	case 2:
      	  $error.=htmlGetErrorMessage("[".$uploadedFile['error']."] ".i18n('errorTooBigFile',array($attachmentMaxSize,'paramAttachmentMaxSize')));
      	  errorLog(i18n('errorTooBigFile',array($attachmentMaxSize,'paramAttachmentMaxSize')));
      	  break;
      	case 4:
      	  $error.=htmlGetWarningMessage("[".$uploadedFile['error']."] ".i18n('errorNoFile'));
      	  errorLog(i18n('errorNoFile'));
      	  break;
      	case 3:
      	  $error.=htmlGetErrorMessage("[".$uploadedFile['error']."] ".i18n('errorUploadNotComplete'));
      	  errorLog(i18n('errorUploadNotComplete'));
      	  break;
      	default:
      	  $error.=htmlGetErrorMessage($error="[".$uploadedFile['error']."] ".i18n('errorUploadFile',array($uploadedFile['error'])));
      	  errorLog(i18n('errorUploadFile',array($uploadedFile['error'])));
      	  break;
      }
    }
  }
  if (! $error) {
    if (! $uploadedFile['name']) {
      $error=htmlGetWarningMessage(i18n('errorNoFile'));
      errorLog(i18n('errorNoFile'));
      //$error=true;
    }
  }
}
$pathSeparator=Parameter::getGlobalParameter('paramPathSeparator');
if (!$error) {
  foreach ($uploadedFileArray as $uploadedFile) {
    $fileName=$uploadedFile['name'];
	  $fileName=Security::checkValidFileName($fileName); // only allow [a-z, A-Z, 0-9, _, -] in file name
    $mimeType=$uploadedFile['type'];
    $mimeType=Security::checkValidMimeType($mimeType);
	  $fileSize=$uploadedFile['size'];   
    $uploaddir = "../files/version";
    /*if (! file_exists($uploaddir)) {
      mkdir($uploaddir,0777,true);
    }*/
    $paramFilenameCharset=Parameter::getGlobalParameter('filenameCharset');
    if ($paramFilenameCharset) {
      $uploadfile = $uploaddir . $pathSeparator . iconv("UTF-8", $paramFilenameCharset.'//TRANSLIT//IGNORE',$fileName);
    } else {
      $uploadfile = $uploaddir . $pathSeparator . $fileName;
    }
    if ( ! move_uploaded_file($uploadedFile['tmp_name'], $uploadfile)) {
      $error = htmlGetErrorMessage(i18n('errorUploadFile','hacking ?'));
      errorLog(i18n('errorUploadFile','hacking ?'));
      errorLog("Cannot move file to $uploadfile");
      errorLog("Check access rights to target folder");
    } 
    Security::checkEvilFile($uploadfile);
    $message="<div class='messageOK' >" . i18n('installAutoUploaded') . "</div>"
      	      ."<input type='hidden' value='resultOK' />";
  }
}
if (!$error) {
  $jsonReturn = json_encode(array('file' => $fileName, 'name' => $fileName, 'type' => $mimeType, 'size' => $fileSize, 'message' => $message));

  if ($isIE and $isIE<=9) {
    echo $message;
    echo '</body>';
    echo '</html>';
  } else {
    ob_end_clean();
    echo $jsonReturn;
  }
}?>