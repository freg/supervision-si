<?php
/*** COPYRIGHT NOTICE *********************************************************
 *
 * Copyright 2009-2017 ProjeQtOr - Pascal BERNARD - support@projeqtor.org
 * Contributors : BRW
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

/**
 * ===========================================================================
 */
function writeFile($msg, $file) {
  if (function_exists('error_log')) {
    return error_log($msg, 3, $file);
  } else {
    $handle=fopen($file, "a");
    if (!$handle) return false;
    if (!fwrite($handle, $msg)) return false;
    if (!fclose($handle)) return false;
    return true;
  }
}

/**
 * Delete a file
 * 
 * @param
 *          $file
 * @throws Exception
 */
function kill($file) {
  if (file_exists($file)) {
    return unlink($file);
  }
  return false;
}

/**
 * Purge some files
 * 
 * @param string $dir
 *          directory
 * @param string $pattern
 *          pattern for file selection
 */
function purgeFiles($dir, $pattern, $removeDirs=false, $patternExt=null) {
  if (!is_dir($dir)) {
    traceLog("purgeFiles('$dir', '$pattern') - directory '$dir' does not exist");
    return;
  }
  $handle=opendir($dir);
  if (!is_resource($handle)) {
    traceLog("purgeFiles('$dir', '$pattern') - Unable to open directory '$dir' ");
    return;
  }
  while (($file=readdir($handle))!==false) {
    if ($file=='.'||$file=='..'||$file=='.svn') {
      continue;
    }
    $filepath=$dir=='.'?$file:$dir.'/'.$file;
    if (is_link($filepath)) {
      continue;
    }
    if (is_file($filepath)) {
      if ( (!$pattern or substr($file, 0, strlen($pattern))==$pattern) and (!$patternExt or substr($file, (-1)*strlen($patternExt))==$patternExt )) {
        unlink($filepath);
      }
    } else if (is_dir($filepath)) {
      purgeFiles($filepath, $pattern, $removeDirs);
    }
  }
  if ($removeDirs) {
    rmdir($dir);
  }
  closedir($handle);
}

/**
 * Create of thumb image of given size, with same name suffixed with "_thumb$size" or with name definied in $thumb
 * 
 * @param string $image
 *          source image to generate thumb from
 * @param integer $size
 *          size of thumb
 * @param string $thumb
 *          name of target thumb (to avoid defaut naming)
 *          $param boolean $square if thumb target to be rendered as a square (crop borders)
 */
function createThumb($imageFile, $size, $thumb=null, $square=false) {
  $paramFilenameCharset=Parameter::getGlobalParameter('filenameCharset');
  if ($paramFilenameCharset) {
    $thumb=iconv("UTF-8", $paramFilenameCharset.'//TRANSLIT//IGNORE', $thumb);
  }
  if (!$size) {
    copy($imageFile, $thumb);
    return;
  }
  $paramFilenameCharset=Parameter::getGlobalParameter('filenameCharset');
  if ($paramFilenameCharset) {
    $imageFile=iconv("UTF-8", $paramFilenameCharset.'//TRANSLIT//IGNORE', $imageFile);
  }
  if (!$imageFile or !is_file($imageFile) or @filesize($imageFile)<1) {
    return false;
  }
  $ext=pq_strtolower(pathinfo($imageFile, PATHINFO_EXTENSION));
  $imgFmt="";
  $imageInfo = false;
  // EDIT START BRW 2013-07-31
  $bSupported=true;
  
  set_error_handler(function($severity, $message, $file, $line) {
  });
  try {
   $imageInfo = @getimagesize($imageFile); 
  } catch (Exception $e) {
    restore_error_handler();
    return false;
  } catch (Error $e) {
    restore_error_handler();
    return false;
  }
    restore_error_handler();
  if (!$imageInfo || !is_array($imageInfo)) {
    return 'invalid';
  }    
//   if (@is_array(getimagesize($imageFile))) {
//     $arr=getimagesize($imageFile);
    switch ($imageInfo['mime']) {
      case 'image/tiff' :
        $bSupported=false;
        break;
      case 'image/jpeg' :
      case 'image/jpg' :
        $imgFmt='jpeg';
        break;
      case 'image/gif' :
        $imgFmt='gif';
        $blending=true;
        break;
      case 'image/png' :
        $imgFmt='png';
        $blending=false;
        break;
      default :
        $bSupported=false;
        break;
    }
//   } else {
//     $bSupported=false;
//     switch ($ext) {
//       case 'jpg' :
//       case 'jpeg' :
//         $imgFmt='jpeg';
//         break;
//       case 'gif' :
//         $imgFmt='gif';
//         $blending=true;
//         break;
//       case 'png' :
//         $imgFmt='png';
//         $blending=false;
//         break;
//     }
//   }

  if ($bSupported) {
    $imagecreate="imagecreatefrom$imgFmt";
    $imagesave="image$imgFmt";
    
    $img=$imagecreate($imageFile);
    $x=imagesx($img);
    $y=imagesy($img);
    $px=0;
    $py=0;
    if ($square) {
      $nx=$size;
      $ny=$size;
      if ($x>$y) {
        $px=round(($x-$y)/2, 0);
        $x=$y;
      } else if ($x<$y) {
        $py=round(($y-$y)/2, 0);
        $y=$x;
      }
    } else if ($x>$size or $y>$size) {
      if ($x>$y) {
        $nx=$size;
        $ny=floor($y/($x/$size));
      } else {
        $nx=floor($x/($y/$size));
        $ny=$size;
      }
    } else {
      $nx=$x;
      $ny=$y;
    }
    if ($nx<1) $nx=1;
    if ($ny<1) $ny=1;
    $nimg=imagecreatetruecolor($nx, $ny);
    // preserve transparency for PNG and GIF images
    if ($imgFmt=='png' or $imgFmt=='gif') {
      $background=imagecolorallocate($nimg, 0, 0, 0);
      imagecolortransparent($nimg, $background);
      imagealphablending($nimg, $blending);
      imagesavealpha($nimg, true);
    }
    imagecopyresampled($nimg, $img, 0, 0, $px, $py, $nx, $ny, $x, $y);
    if (!$thumb) {
      $thumb=getThumbFileName($imageFile, $size);
    }
    enableCatchErrors();
    $dir=pathinfo($thumb, PATHINFO_DIRNAME);
    if (!file_exists($dir)) {
      mkdir($dir, 0777, true);
    }
    try {
      $res=@$imagesave($nimg, $thumb);
    } catch (Exception $e) {
      errorLog("create thumb error : ".$e->getMessage());
      $res=false;
    }
    if (!$res) {
      errorLog("Cannot write thumb file : '$thumb' (check write access to folder)");
    }
    disableCatchErrors();
    return true;
  }
  return false;
  // EDIT END BRW 2013-07-31
}

function getThumbFileName($imageFile,$size) {
	$thumbLocation='../files/thumbs';
	$attLoc=Parameter::getGlobalParameter('paramAttachmentDirectory');
	$docLoc=Parameter::getGlobalParameter('documentRoot');
	$root='../files';
	if (pq_substr($imageFile,0,pq_strlen($attLoc))==$attLoc) {
		$root=$attLoc;
	} else if (pq_substr($imageFile,0,pq_strlen($attLoc))==$docLoc)  {
		$root=$docLoc;
	}
	$relativePath = pq_substr($imageFile, pq_strlen($root));
    $filename = basename($relativePath);
    $directory = dirname($relativePath);
    $filename = preg_replace('/[^\w.]/', '_', $filename);
    $thumbFile = $thumbLocation . $directory . '/' . $filename;
	if (!$size) return $imageFile;
	$ext=pq_strtolower(pathinfo($imageFile, PATHINFO_EXTENSION));
	return $thumbFile . '_thumb' . $size . '.' . $ext;
}
function urlencodepath($string) {
  if (!$string) return '';
  return implode("/", array_map("rawurlencode", explode("/", $string)));
}

function getImageThumb($imageFile, $size) {
  if (pq_substr($imageFile,-4)=='.svg') return $imageFile;
  $thumb=getThumbFileName(rawurldecode($imageFile), $size);
  if (!file_exists($thumb)) {
    $createResult = createThumb($imageFile, $size, $thumb);
    if ($createResult === 'invalid') {
      return "../view/img/mime/unknown.png";
    } else if (!$createResult) {
      errorLog("Cannot create image thumb of size $size for $imageFile (uploaded file with image extension is not an image, try and delete it)");
      return "";
    }
  }
  return $thumb;
}

function isThumbable($fileName) {
  $ext = (!empty($fileName)) ? strtolower(pathinfo($fileName, PATHINFO_EXTENSION)) : null;
  if ($ext=='jpg' or $ext=='jpeg' or $ext=='gif' or $ext=='png' or $ext=='svg') {
    return true;
  } else {
    return false;
  }
}
function getStaticFileNameWithCacheMgt($file) {
  global $version,$svnRevision;
  $defaultAccessFileName="$file?version=$version.$svnRevision"; // if something is wrong with cache management return this
  
  if (substr($file,0,12)=='../external/') return $file;
  if (substr($file,0,9)=='external/') return $file;
  if (strpos($file,'/external/')!==false) return $file;
  if (substr($file,0,7)=='../css/') return $file;
  if (substr($file,0,4)=='css/') return $file;
  if (strpos($file,'/css/')!==false) return $file;
  if (strpos($file,'/plugin/')!==false) return $file;
  //if (substr($file,0,9)=='view/css/') return $defaultAccessFileName;
  //if (substr($file,0,12)=='../view/css/') return $defaultAccessFileName;
  
  $extension=strtolower(pathinfo($file, PATHINFO_EXTENSION));
  $filename=basename($file,".$extension");
  $extraDir='';
  if (substr($file,0,5)=='view/' and substr(getcwd(),-4)=='view') {
    $file=substr($file,5);
    $extraDir='cache/';
  }
  enableCatchErrors();
  
  $directory=dirname($file);
  $time=filemtime($file);
  if (! $time) {
    errorLog("Cannot get last modification time for $file");
    errorLog(" => ".$_SERVER['SCRIPT_FILENAME']);
    debugPrintTraceStack();
    return $file;
  }
  
  $targetDir='../cache/'.$directory;
  if (substr($directory,0,8)=='../view/') $targetDir='../cache/'.substr($directory,8);
  if (! file_exists($targetDir)) {
	try {
      if (! @mkdir($targetDir, 0755, true)) return $defaultAccessFileName;;
	} catch (Exception $e) {
      errorLog("create directory $targetDir : ".$e->getMessage());
      return $defaultAccessFileName;
    }
  }
  
  $targetFile="$targetDir/$filename.$time.$extension";
  if (! file_exists($targetFile)) {
    purgeFiles($targetDir, "$filename.", false, ".$extension");
    if (! @copy($file,$targetFile)) return $defaultAccessFileName;
  }
  disableCatchErrors();
  if ($extraDir) return "$extraDir$directory/$filename.$time.$extension";
  else return $targetFile;
}

function echoStaticFileNameWithCacheMgt($file) {
  echo getStaticFileNameWithCacheMgt($file);
}

function getStreamContext($timeout=10) {
  if (!$timeout) $timeout=10;
  $http_options=array('timeout' => $timeout);
  $proxy=Parameter::getGlobalParameter('paramProxy');
  if (pq_trim($proxy)) {
    $http_options['proxy']='tcp://'.$proxy;
    $http_options['request_fulluri']=true;
    $proxyUser=Parameter::getGlobalParameter("paramProxyUser");
    $proxyPassword=Parameter::getGlobalParameter("paramProxyPassword");
    if (pq_trim($proxyUser) and pq_trim($proxyPassword)) {
      $auth = base64_encode("$proxyUser:$proxyPassword");
      $http_options['header']="Proxy-Authorization: Basic $auth";
    }
  }
  $ctx=stream_context_create(array('http'=>$http_options));
  return $ctx;
}