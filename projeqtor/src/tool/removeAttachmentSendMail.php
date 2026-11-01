<?php
use http\Client\Request;

require_once "../tool/projeqtor.php";
require_once "../tool/formatter.php";
scriptLog('   ->/tool/removeAttachmentSendMail.php');

$objectClass=RequestHandler::getClass('objectClass');
if($objectClass == 'TicketSimple'){
  $objectClass = 'Ticket';
}

$objectId = RequestHandler::getValue('objectId');
$objectId = intval($objectId);

$name = RequestHandler::getValue('name');

$attachmentDirectory = Parameter::getGlobalParameter('paramAttachmentDirectory');
$pathSeparator=Parameter::getGlobalParameter('paramPathSeparator');
$folderPath = $attachmentDirectory . $pathSeparator . "attachment_" . $objectClass ."_".$objectId.$pathSeparator;

if ( is_dir($folderPath) ) {
  if($name!='false'){
    deleteFileAttachment($folderPath,$name);
  }else{
    deleteFolderAttah($folderPath);
  }

}


function deleteFileAttachment($folderPath, $fileName) {
  if (!is_dir($folderPath)) {
    debugTraceLog("Folder does not exist: $folderPath");
    return false;
  }
  $filePath = $folderPath . $fileName;
  if (!file_exists($filePath)) {
    debugTraceLog("File does not exist: $filePath");
    return false;
  }
  if (!is_file($filePath)) {
    debugTraceLog("Path is not a file: $filePath");
    return false;
  }
  if (unlink($filePath)) {
    debugTraceLog("File successfully deleted: $filePath");
    return true;
  } else {
    debugTraceLog("Failed to delete file: $filePath");
    return false;
  }
}

function deleteFolderAttah($folderPath) {
  if (!is_dir($folderPath)) return false;
  
  $files = array_diff(scandir($folderPath), ['.', '..']);
  foreach ($files as $file) {
    $filePath = $folderPath . '/' . $file;
    if (is_dir($filePath)) {
      deleteFolderRecursively($filePath); 
    } else {
      unlink($filePath); 
    }
  }
  
  return rmdir($folderPath); 
}


?>