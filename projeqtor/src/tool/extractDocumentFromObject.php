<?php 
use Doctrine\Common\Collections\Expr\Value;
use Gregwar\RST\References\Doc;
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
require_once "../tool/projeqtor.php";

$download = RequestHandler::getBoolean('download');
$objectClass=RequestHandler::getClass('objectClass');
$objectId = intval(RequestHandler::getId('objectId'));
$extractMode = RequestHandler::getValue('extractDocumentMode');
$extractSubDir = RequestHandler::getBoolean('extractSubDirectory');
$extractSubProj = RequestHandler::getBoolean('extractSubProjectDirectory');
$extractProjElement = RequestHandler::getBoolean('extractProjectElementDirectory');
$extractAttach = RequestHandler::getBoolean('extractAttachment');
$extractVersion = RequestHandler::getBoolean('extractVersion');
$preserveUploadedFileName = RequestHandler::getValue('preserveUploadedFileName');
$idVersion = RequestHandler::getValue('extractIdVersion');
$user = getSessionUser();
$ress=new Resource($user->id);

if($download){
    //after download delete userFiles
    if(is_Dir('../files/documents/userFiles_'.$user->id)){
      purgeFiles('../files/documents/userFiles_'.$user->id, null, true);
    }
    exit;
}

$object = new $objectClass($objectId);

$files = array();
$docFiles = array();
$attchFiles = array();

//Zip creation whith fileName userFile
if(!is_dir('../files/documents/userFiles_'.$user->id)){
  mkdir('../files/documents/userFiles_'.$user->id,0755,true);
}
$zipName='../files/documents/userFiles_'.$user->id.'/'.$objectClass.'_'.$objectId.'_user_'.$user->id.'.zip';

$zip=new ZipArchive();
$ret=$zip->open($zipName, ZIPARCHIVE::CREATE | ZIPARCHIVE::OVERWRITE);

$project = new Project();
$document = new Document();
$docDirectory = new DocumentDirectory();
$docVersion = new DocumentVersion();
$attachment = new Attachment();
$planElement = new PlanningElement();
$linkable = new Linkable();
$link = new Link();

$documentRoot = Parameter::getGlobalParameter('documentRoot');
if (substr($documentRoot,-1)!='/' and substr($documentRoot,-1)!='\\') $documentRoot.='/';
$docArray = array_filter(pq_explode('/', $documentRoot));
$docName = (isset($docArray[count($docArray)]))?$docArray[count($docArray)]:$docArray[(count($docArray)-1)];
$docRoot = ($documentRoot)?'~'.$docName.'/':'~documents/';
$attchDirectory = Parameter::getGlobalParameter('paramAttachmentDirectory');
if (substr($attchDirectory,-1)!='/' and substr($attchDirectory,-1)!='\\') $attchDirectory.='/';
$attchArray = array_filter(pq_explode('/', $attchDirectory));
$attachName = (isset($attchArray[count($attchArray)]))?$attchArray[count($attchArray)]:$attchArray[(count($attchArray)-1)];
$attchDir = ($attchDirectory)?'~'.$attachName.'/':'~attach/';
$DirName = ($objectClass=='DocumentDirectory')?$object->name:'';

$queryDoc = '';
$queryElmntDoc = '';
$queryAttch = '';
$queryElmntAttch = '';

if($extractMode == 'Directory'){//Query for extract document from Directory
  $subDirList = array();
  if($extractSubDir){
    $docDir = new DocumentDirectory($objectId);
  	$subDir = $docDir->getRecursiveSubDirectoriesFlatList(true);
  	foreach ($subDir as $id=>$name){
  	  $subDirList[$id]=$id;
  	}
  }else{
    $subDirList[$objectId]=$objectId;
  }
  $subDirList = implode(',', $subDirList);
  
  $queryDoc = 'Select dv.id, dv.fileName as filename, dv.fullName as fullname, dd.location, d.idDocumentDirectory as iddocumentdirectory, dv.idDocument as iddocument FROM '.$document->getDatabaseTableName().' d 
      left join '.$docVersion->getDatabaseTableName().' dv on dv.id = d.'.$idVersion.'
          left join '.$docDirectory->getDatabaseTableName().' dd on dd.id = d.idDocumentDirectory
      WHERE d.'.$idVersion.' is not null and dd.id in (0,'.$subDirList.')';
}else if($extractMode == 'Project'){//Query for extract document and attachment from Project and project elements
  if($extractSubProj){
    $proj = new Project($objectId);
  	$subProjList = $proj->getRecursiveSubProjectsFlatList(null, true);
  	$subProjList = array_flip($subProjList);
  }else{
    $subProjList[$objectId] = $objectId;
  }
  $subProjList = implode(',', $subProjList);
  
  if($extractVersion){//Extract document query
    $queryDoc = 'Select dv.id, dv.fileName, dv.fullName, dd.location, d.idDocumentDirectory, dv.idDocument FROM '.$document->getDatabaseTableName().' d
      left join '.$docVersion->getDatabaseTableName().' dv on dv.id = d.'.$idVersion.'
          left join '.$docDirectory->getDatabaseTableName().' dd on dd.id = d.idDocumentDirectory
      WHERE d.'.$idVersion.' is not null and d.idProject in (0,'.$subProjList.')';
  }
  
  if($extractAttach){//Extract attachment query
    $queryAttch = 'Select a.id, a.refType, a.refId, a.fileName, a.subDirectory FROM '.$attachment->getDatabaseTableName().' a
      left join '.$planElement->getDatabaseTableName().' pl on pl.refId = a.refId and pl.refType = a.refType
      WHERE a.subDirectory is not null and ( pl.refType = \'Project\' and pl.refId in (0,'.$subProjList.'))';
  }
  
  if($extractProjElement){//Extract project elements query (document and attchment) 
    $linkableList = $linkable->getSqlElementsFromCriteria(null, null, "1=1");
    $cp=0;
    foreach ($linkableList as $linkable){
      $obj = new $linkable->name();
      if(property_exists(get_class($obj), 'idProject')){
        $name = $linkable->name;
        if($cp!=0)$queryElmntAttch .=' UNION ALL ';
        $queryElmntAttch .= 'Select att.id, att.refType, att.refId, att.fileName, att.subDirectory FROM '.$attachment->getDatabaseTableName().' att ';
        $queryElmntAttch .= 'WHERE att.refType = "'.$linkable->name.'" and refId in ( ';
        $queryElmntAttch .= 'SELECT id FROM '.$obj->getDatabaseTableName().'  WHERE idProject in (0,'.$subProjList.') ) ';
        $queryElmntAttch .= 'and att.subDirectory is not null ';
        
        if($cp!=0)$queryElmntDoc .=' UNION ALL ';
        $queryElmntDoc .= 'Select dv.id, dv.fileName, dv.fullName, dd.location, d.idDocumentDirectory, dv.idDocument, lk.ref1Type, lk.ref2Type, lk.ref1Id, lk.ref2Id FROM '.$docVersion->getDatabaseTableName().' dv
                left join '.$document->getDatabaseTableName().' d  on dv.idDocument = d.id
                    left join '.$link->getDatabaseTableName().' lk on ( lk.ref1Type = \'DocumentVersion\'  or lk.ref2Type = \'DocumentVersion\' or lk.ref1Type = \'Document\' or lk.ref2Type = \'Document\' )
                     left join '.$docDirectory->getDatabaseTableName().' dd on dd.id = d.idDocumentDirectory';
        
        $queryElmntDoc .= ' WHERE ((lk.ref2Type = "'.$linkable->name.'" 
                                      and lk.ref2Id in (SELECT id FROM '.$obj->getDatabaseTableName().'  WHERE idProject in (0,'.$subProjList.') )) 
                                    or ( lk.ref1Type = "'.$linkable->name.'" 
                                      and lk.ref1Id in ( SELECT id FROM '.$obj->getDatabaseTableName().'  WHERE idProject in (0,'.$subProjList.') )))
                                  and (((lk.ref1Type = \'Document\' and lk.ref1Id = dv.idDocument ) or (lk.ref2Type = \'Document\' and lk.ref2Id = dv.idDocument) and d.'.$idVersion.'=dv.id and d.'.$idVersion.' is not null ) 
                                      or ((lk.ref1Type = \'DocumentVersion\' and lk.ref1Id = dv.id ) or (lk.ref2Type = \'DocumentVersion\' and lk.ref2Id = dv.id)))';
        $cp++;
      }
    }
  }
}else if($extractMode == 'Element'){//Query for extract document and attachment from Elements
    if($extractVersion){//Extract document query
      $queryDoc .= 'Select dv.id, dv.fileName, dv.fullName, dd.location, d.idDocumentDirectory, dv.idDocument FROM '.$docVersion->getDatabaseTableName().' dv
                left join '.$document->getDatabaseTableName().' d on dv.idDocument = d.id
                    left join '.$link->getDatabaseTableName().' lk on (lk.ref1Type = \'DocumentVersion\'  or lk.ref2Type = \'DocumentVersion\' )
                                                                    or (lk.ref1Type = \'Document\' or lk.ref2Type = \'Document\')
                      left join '.$docDirectory->getDatabaseTableName().' dd on dd.id = d.idDocumentDirectory';
      $queryDoc .= ' WHERE (lk.ref2Type = "'.$objectClass.'" and lk.ref2Id = '.$objectId.') or (lk.ref1Type = "'.$objectClass.'" and lk.ref1Id = '.$objectId.') 
          and ( ( (lk.ref1Type = \'Document\' and lk.ref1Id = dv.idDocument ) or (lk.ref2Type = \'Document\' and lk.ref2Id = dv.idDocument) and d.'.$idVersion.'=dv.id and d.'.$idVersion.' is not null ) 
              or ( (lk.ref1Type = \'DocumentVersion\' and lk.ref1Id = dv.id ) or (lk.ref2Type = \'DocumentVersion\' and lk.ref2Id = dv.id)) );';
    }
    
    if($extractAttach){//Extract attachment query
      $queryAttch = 'Select a.id, a.refType, a.refId, a.fileName, a.subDirectory FROM '.$attachment->getDatabaseTableName().' a
      WHERE a.subDirectory is not null and a.refType = \''.$objectClass.'\' and a.refId = '.$objectId;
    }
}

//==================================================================================================//
//                                         Documents                                                //
//==================================================================================================//
if($queryDoc){//Initialization of array for current object documents
  $docLists = Sql::query($queryDoc);
  if($docLists){
    $nameDir="";
    if($extractMode == 'Element' or $extractMode == 'Project'){
      $nameDir=$extractMode;
    }
  	foreach ($docLists as $key=>$files) {
  	    $file = array_change_key_case($files);
  		$docDirectory = new DocumentDirectory($file['iddocumentdirectory']);
  		$ext = (pq_substr($file['filename'], -4)== '.php')?'.projeqtor.txt':'';
  		if($docDirectory->canSeeDirectory($docDirectory->id, $docDirectory->idProject)){
  		  $doc = new Document($file['iddocument']);
  			if(securityGetAccessRightYesNo('menuDocument', 'read', $doc, $user) == 'YES'){
  				if(is_dir($documentRoot.pq_substr($file['location'], 1)) and is_file($documentRoot.pq_substr($file['location'], 1).'/'.$file['filename'].$ext.'.'.$file['id'])){
  				  $docFiles[$key.$nameDir]['nameDir']=$nameDir;
  				  $docFiles[$key.$nameDir]['idDocument']=$file['iddocument'];
  				  $docFiles[$key.$nameDir]['idVersion']=$file['id'];
  				  $docFiles[$key.$nameDir]['idDocumentDirectory']=$file['iddocumentdirectory'];
  				  $docFiles[$key.$nameDir]['location']=pq_substr($file['location'], 1);
  				  $docFiles[$key.$nameDir]['locationDir']=($extractMode == 'Directory')?pq_substr($file['location'], 1).'/':$docRoot;
  				  $docFiles[$key.$nameDir]['fileName']=$file['filename'];
  				  $docFiles[$key.$nameDir]['fullName']=$file['fullname'];
  				  if($extractMode != 'Directory'){//creation of zip folder for non-directory elements
  				  	if($DirName != ''){
  				  		$zip->addEmptyDir($docRoot.pq_substr($file['location'], pq_strpos($file['location'], $DirName)));
  				  	}else{
  				  		$zip->addEmptyDir($docRoot);
  				  	}
  				  }
  				}
  			}
  		}
  	}
  }
}
if($queryElmntDoc){//Initialization of array for documents of object linked elements
	$docLists = Sql::query($queryElmntDoc);
	if($docLists){
	  foreach ($docLists as $key=>$files) {
	    $file = array_change_key_case($files);
	  	$docDirectory = new DocumentDirectory($file['iddocumentdirectory']);
	  	$ext = (pq_substr($file['filename'], -4)== '.php')?'.projeqtor.txt':'';
	  	if($docDirectory->canSeeDirectory($docDirectory->id, $docDirectory->idProject)){
	  	  $doc = new Document($file['iddocument']);
	  		if(securityGetAccessRightYesNo('menuDocument', 'read', $doc, $user) == 'YES'){
    		  if(is_dir($documentRoot.pq_substr($file['location'], 1)) and is_file($documentRoot.pq_substr($file['location'], 1).'/'.$file['filename'].$ext.'.'.$file['id'])){
    		    $obj = null;
    		    if($file['ref1type'] != 'Document' and $file['ref1type'] != 'DocumentVersion'){
    		    	$obj = new $file['ref1type']($file['ref1id']);
    		    }else{
    		    	$obj = new $file['ref2type']($file['ref2id']);
    		    }
    		    $nameDir = ($obj->id)?get_class($obj).'_'.$obj->id.'_'.$obj->name.'/':'';
    		    $docFiles[$key.$nameDir]['nameDir']=$nameDir;
    		    $docFiles[$key.$nameDir]['idDocument']=$file['iddocument'];
    		    $docFiles[$key.$nameDir]['idVersion']=$file['id'];
    		    $docFiles[$key.$nameDir]['idDocumentDirectory']=$file['iddocumentdirectory'];
    		    $docFiles[$key.$nameDir]['location']=pq_substr($file['location'], 1);
    		    $docFiles[$key.$nameDir]['locationDir']=$docRoot;
    		    $docFiles[$key.$nameDir]['fileName']=$file['filename'];
    		    $docFiles[$key.$nameDir]['fullName']=$file['fullname'];
    		    $zip->addEmptyDir($nameDir.$docRoot);
  			  }
	  		}
	  	}
	}
  }
}
if(count($docFiles) > 0){//Adding documents files to zip with their location and document rights
  foreach ($docFiles as $files) {
  	$docVers = $files['idVersion'];
  	$docDirectory = new DocumentDirectory($files['idDocumentDirectory']);
  	$location = $files['location'];
  	$locationDir = $files['locationDir'];
  	$nameDir = ($files['nameDir'] != $extractMode)?$files['nameDir']:'';
  	$fileName = $files['fileName'];
  	$fullName = ($preserveUploadedFileName=='NO')?$files['fullName']:$fileName;
  	$ext = (pq_substr($files['fileName'], -4)== '.php')?'.projeqtor.txt':'';
  	if($docDirectory->canSeeDirectory($docDirectory->id, $docDirectory->idProject)){
  	  $doc = new Document($files['idDocument']);
  		if(securityGetAccessRightYesNo('menuDocument', 'read', $doc, $user) == 'YES'){
  			if(is_dir($documentRoot.$location) and is_file($documentRoot.$location.'/'.$fileName.$ext.'.'.$docVers)){
    		    if($DirName){
    		      $locationDir = ($locationDir == $docRoot)?$docRoot:pq_substr($locationDir, pq_strpos($locationDir, $DirName));
    		      $zip->addFile($documentRoot.$location.'/'.$fileName.$ext.'.'.$docVers, $nameDir.$locationDir.$fullName);
    		    }else{
    		      $zip->addFile($documentRoot.$location.'/'.$fileName.$ext.'.'.$docVers, $nameDir.$locationDir.$fullName);
    		    }
  			}
  		}
  	}
  }
}

//==================================================================================================//
//                                         Attachments                                              //
//==================================================================================================//
if($queryAttch){//Initialization of array for current object attachments
  $attchLists = Sql::query($queryAttch);
  if($attchLists){
  	foreach ($attchLists as $files) {
  	  $file = array_change_key_case($files);
  	  $attachment = new Attachment($file['id']);
  	  if ($user->id==$attachment->idUser or $attachment->idPrivacy==1 or ($attachment->idPrivacy==2 and $ress->idTeam==$attachment->idTeam) ) {
        $location = $file['subdirectory'];
        $fileName = $file['filename'];
        $class = $file['reftype'];
        $id = $file['refid'];
        $obj = new $class($id);
        $nameDir = $class.'_'.$id.'_'.$obj->name;
        $location = pq_str_replace('${attachmentDirectory}', $attchDirectory, $location);
        $location = pq_str_replace('\\', '/', $location);
        $location = pq_str_replace('//', '/', $location);
        if(is_dir($location) and is_file($location.$fileName)){
          $attchFiles[$file['id']]['id']=$file['id'];
          $attchFiles[$file['id']]['location']=$location;
          $attchFiles[$file['id']]['nameDir']=$attchDir;
          $attchFiles[$file['id']]['fileName']=$file['filename'];
          $zip->addEmptyDir($attchDir);
        }
      }
  	}
  }
}
if($queryElmntAttch){//Initialization of array for attachments of object linked elements
	$attchLists = Sql::query($queryElmntAttch);
	if($attchLists){
    	foreach ($attchLists as $files) {
    	  $file = array_change_key_case($files);
    	  $attachment = new Attachment($file['id']);
    	  if ($user->id==$attachment->idUser or $attachment->idPrivacy==1 or ($attachment->idPrivacy==2 and $ress->idTeam==$attachment->idTeam) ) {
      	     $location = $file['subdirectory'];
      	     $class = $file['reftype'];
      	     $id = $file['refid'];
    		 $obj = new $class($id);
    		 $nameDir = $class.'_'.$id.'_'.$obj->name.'/'.$attchDir;
    		 $location = pq_str_replace('${attachmentDirectory}', $attchDirectory, $location);
    		 $location = pq_str_replace('\\', '/', $location);
    		 $location = pq_str_replace('//', '/', $location);
    		 if(is_dir($location) and is_file($location.$file['filename'])){
    		   $attchFiles[$file['id']]['id']=$file['id'];
    		   $attchFiles[$file['id']]['location']=$location;
    		   $attchFiles[$file['id']]['nameDir']=$nameDir;
    		   $attchFiles[$file['id']]['fileName']=$file['filename'];
    		   $zip->addEmptyDir($nameDir);
    		 }
    	  }
    	}
	}
}
if(count($attchFiles)>0){//Adding attachments files to zip with their location
  foreach ($attchFiles as $files) {
  	$location = $files['location'];
  	$fileName = $files['fileName'];
  	$nameDir = $files['nameDir'];
  	$fullName = (pq_substr($fileName, -14)=='.projeqtor.txt')?pq_substr($fileName, 0, -14):$fileName;
	if(is_file($location.$fileName)){
		$zip->addFile($location.$fileName, $nameDir.$fullName);
	}
  }
}

//=========================================== Fin ==================================================//

if(!$docFiles and !$attchFiles){
  $zip->close();
  echo "noFilesFound";//if no files found on documents and attachment return no files found message
  exit;
}else{
  $zip->close();
  echo $zipName;//if files found on documents and attachment return zipName for download
}