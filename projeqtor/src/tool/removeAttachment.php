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

/** ===========================================================================
 * Delete the current attachment : call corresponding method in SqlElement Class
 */

require_once "../tool/projeqtor.php";

$attachmentId=null;
if (pq_array_key_exists('attachmentId',$_REQUEST)) {
  $attachmentId=$_REQUEST['attachmentId']; // validated to be numeric value in SqlElement base constructor.
}
$attachmentId=pq_trim($attachmentId);
if ($attachmentId=='') {
  $attachmentId=null;
} 
if ($attachmentId==null) {
  throwError('attachmentId parameter not found in REQUEST');
}
$obj=new Attachment($attachmentId);
$subDirectory=pq_str_replace('${attachmentDirectory}', Parameter::getGlobalParameter('paramAttachmentDirectory'), $obj->subDirectory);
if (file_exists($subDirectory . $obj->fileName)) {
  unlink($subDirectory . $obj->fileName);
  purgeFiles($subDirectory, null);
  rmdir($subDirectory);
}
$subDirectory_thumb=pq_str_replace('${attachmentDirectory}', '../files/thumbs', $obj->subDirectory);
if ( $subDirectory_thumb and file_exists( $subDirectory_thumb ) ) {
   purgeFiles($subDirectory_thumb, null,true);
   //rmdir($subDirectory_thumb);
}
Sql::beginTransaction();
$result=$obj->delete();
$refType=$obj->refType;
$refId=$obj->refId;
if ($refType=='User' or $refType=='Contact') {
	$refType='Resource';
}
if ($refType=='Resource' && $obj->isProfilePic==1) { 
	Affectable::deleteThumbs($refType, intval($refId), $obj->subDirectory.$obj->fileName);
}

if ($refType=='Project' && $obj->isProfilePic==1) {
//Todo
}
// Message of correct saving
$result.='<input type="hidden" id="lastSaveRefType" value="'.$refType.'" />';
$result.='<input type="hidden" id="lastSaveRefId" value="'.$refId.'" />';
displayLastOperationStatus($result);
?>