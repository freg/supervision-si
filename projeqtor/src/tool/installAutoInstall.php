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

//chdir ( '../' );
$maintenance = true;
require_once '../tool/projeqtor.php';
require_once "../db/maintenanceFunctions.php";
require_once "installAutoZipList.php";

/*
 * if (securityGetAccessRightYesNo('menuPlgInstallAuto','read')!='YES') {
 * traceHack ( "InstallAuto tried without access right" );
 * exit ();
 * }
 */
$oneFile = null;
if (isset ( $_REQUEST ['installAutoFile'] )) {
	$oneFile = urldecode ( $_REQUEST ['installAutoFile'] );
	$oneFile = Security::checkValidFileName ( $oneFile );
}
$user = getSessionUser ();
$profile = new Profile ( $user->idProfile );
if ($profile->profileCode != 'ADM') {
	echo 'Call to installAutoInstall.php for non Admin user.<br/>This action and your IP has been traced.';
	traceHack ( 'Call to installAutoInstall.php for non Admin user' );
	exit ();
}

Sql::$maintenanceMode = true;
$files = installAutoGetZipList ( $oneFile );
$result = "";
foreach ( $files as $file ) {
	$result = load ( $file );
	echo $result;
}
$i18nSessionValue = 'i18nMessages' . ((isset ( $currentLocale )) ? $currentLocale : '');
unsetSessionValue ( $i18nSessionValue, false );

if (! $oneFile) {
	echo "InstallAutoInstall.php executed at " . date ( 'Y-m-d H:i:s' );
}
function load($file) {
	global $globalCatchErrors;
	traceLog ( "New installation found : " . $file ['name'] );
	$zipFile = $file ['path'];
	$versionFile = getVersionFile ( $zipFile );
	if ($versionFile == - 1)
		return i18n ( 'installAutoFindVersionError' );
	$V1 = ltrim ( Parameter::getGlobalParameter ( "dbVersion" ), 'V' );
	$V2 = ltrim ( $versionFile, 'V' );
	$versionCompare = version_compare ( $V1, $V2 );
	if ($versionCompare > 0)
		return i18n ( 'installAutoCompareVersionError' );
	$result = "OK";
	// unzip plugIn files
	$zip = new ZipArchive ();
	$globalCatchErrors = true;
	$res = $zip->open ( $zipFile );
	if ($res === TRUE) {
		$res = $zip->extractTo ( "..".DIRECTORY_SEPARATOR );
		if ($res !== TRUE) {
			return i18n ( 'installAutoRightAcess', Array (
					i18n ( 'installAutoRightZip' ) 
			) );
		}
		$zip->close ();
		$returnCopy = recurseCopy ( "..".DIRECTORY_SEPARATOR."projeqtor".DIRECTORY_SEPARATOR."", "..".DIRECTORY_SEPARATOR );
		if (is_string ( $returnCopy )) {
			return i18n ( 'installAutoRightAcess', Array (
					$returnCopy 
			) );
		}
		$delTree1 = delTree ( "..".DIRECTORY_SEPARATOR."files".DIRECTORY_SEPARATOR."version", false );
		if (is_string ( $delTree1 )) {
			return i18n ( 'installAutoRightAcess', Array (
					$delTree1 
			) );
		}
		$delTree2 = delTree ( "..".DIRECTORY_SEPARATOR."projeqtor".DIRECTORY_SEPARATOR );
		if (is_string ( $delTree2 )) {
			return i18n ( 'installAutoRightAcess', Array (
					$delTree2 
			) );
		}
		traceLog ( "Installation unzipped succefully" );
		return $result;
	}
	if ($res !== TRUE) {
		$result = i18n ( 'pluginUnzipFail', array (
				$zipFile,
				$zipFile 
		) );
		errorLog ( "Plugin::load() : $result" );
		return $result;
	}
}
function getVersionFile($file) {
	$zip = new ZipArchive ();
	$globalCatchErrors = true;
	$res = $zip->open ( $file );
	$fileInZip = "";
	if ($res === TRUE) {
		$idx = $zip->locateName ( 'projeqtor.php', ZIPARCHIVE::FL_NODIR );
		$fileInZip = $zip->getFromIndex ( $idx );
	}
	if (pq_strpos ( $fileInZip, '$version = "' ) !== false) {
		$size = 0;
		while ( pq_substr ( $fileInZip, pq_strpos ( $fileInZip, '$version = "' ) + 12 + $size, 1 ) != '"' ) {
			$size ++;
		}
		return pq_substr ( $fileInZip, pq_strpos ( $fileInZip, '$version = "' ) + 12, $size );
	} else 	if (pq_strpos ( $fileInZip, '$version="' ) !== false) {
		$size = 0;
		while ( pq_substr ( $fileInZip, pq_strpos ( $fileInZip, '$version="' ) + 10 + $size, 1 ) != '"' ) {
			$size ++;
		}
		return pq_substr ( $fileInZip, pq_strpos ( $fileInZip, '$version="' ) + 10, $size );
	} else {
		return - 1;
	}
}
function recurseCopy($source, $dest) {
	if (is_dir ( $source )) {
		$dir_handle = opendir ( $source );
		while ( $file = readdir ( $dir_handle ) ) {
			if ($file != "." && $file != "..") {
				if (is_dir ( $source . DIRECTORY_SEPARATOR . $file )) {
					if (! is_dir ( $dest . DIRECTORY_SEPARATOR . $file )) {
						mkdir ( $dest . DIRECTORY_SEPARATOR . $file );
					}
					recurseCopy ( $source . DIRECTORY_SEPARATOR . $file, $dest . DIRECTORY_SEPARATOR . $file );
				} else {
					copy ( $source . DIRECTORY_SEPARATOR . $file, $dest . DIRECTORY_SEPARATOR . $file );
				}
			}
		}
		closedir ( $dir_handle );
	} else {
		copy ( $source, $dest );
	}
}
function delTree($dir, $delFolder = true) {
	$files = array_diff ( scandir ( $dir ), array (
			'.',
			'..' 
	) );
	foreach ( $files as $file ) {
		$test = true;
		(is_dir ( $dir.DIRECTORY_SEPARATOR.$file )) ? delTree ( $dir.DIRECTORY_SEPARATOR.$file ) : $test = unlink ( $dir.DIRECTORY_SEPARATOR.$file );
		if (! $test) {
			return i18n ( 'installAutoRightDel', Array (
					$dir.DIRECTORY_SEPARATOR.$file
			) );
		}
	}
	if ($delFolder)
		return rmdir ( $dir ) ? true : i18n ( 'installAutoRightDel', Array (
				$dir 
		) );
}