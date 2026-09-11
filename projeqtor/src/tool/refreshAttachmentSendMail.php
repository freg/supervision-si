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

require_once "../tool/projeqtor.php";
require_once "../tool/formatter.php";
scriptLog('   ->/tool/refreshAttachmentSendMail.php');
$isIE=false;
if (pq_array_key_exists('isIE',$_REQUEST)) {
  $isIE=$_REQUEST['isIE'];
}
$objectClass=RequestHandler::getClass('objectClass');
if($objectClass == 'TicketSimple'){
  $objectClass = 'Ticket';
}

$objectId = RequestHandler::getValue('objectId');
$objectId = intval($objectId);

$paramMailerType=pq_strtolower(Parameter::getGlobalParameter('paramMailerType'));
$lstAttach= array();
$lstDoc= array();
$obj=new $objectClass($objectId);
if (method_exists($obj, 'setAttributes')) $obj->setAttributes();
$emTp = new EmailTemplate();
$idObjectType = 'id'.$objectClass.'Type';
$idMailable = SqlList::getIdFromTranslatableName('Mailable', $objectClass);
$where = "(idMailable = ".Sql::fmtId($idMailable)." or idMailable IS NULL) ";
if (property_exists($obj, $idObjectType)) $where.=" and (idType = '".$obj->$idObjectType."' or idType IS NULL)";
$listEmailTemplate = $emTp->getSqlElementsFromCriteria(null,false,$where);
$displayComboButton=false;
$user=getSessionUser();
$profile=$user->getProfile($obj);
$habil=SqlElement::getSingleSqlElementFromCriteria('habilitationOther', array('idProfile'=>$profile, 'scope'=>'combo'));
if ($habil) {
  $list=new ListYesNo($habil->rightAccess);
  if ($list->code=='YES') {
    $displayComboButton=true;
  }
}

if($paramMailerType=='phpmailer'){
  $lstAllAttach=searchAllAttachmentMailable($objectClass,$obj->id);
  $currentUser=new Resource(getCurrentUserId());
  $lstAttach=$lstAllAttach[0];
  $lstDoc=$lstAllAttach[1];
}
$maxSizeAttachment=Parameter::getGlobalParameter('paramAttachmentMaxSizeMail');
if($maxSizeAttachment==''){
  $maxSizeAttachment=0;
}
$maxSize=$maxSizeAttachment;
$maxSizeAttachment=octectConvertSize($maxSize);

//add attachment
$attachmentDirectory = Parameter::getGlobalParameter('paramAttachmentDirectory');
$pathSeparator=Parameter::getGlobalParameter('paramPathSeparator');
$folderPath = $attachmentDirectory . $pathSeparator . "attachment_" . $objectClass ."_".$objectId.$pathSeparator;
?>
  <table id="scrollAddTableMail" style='font-size:12px;width:685px;max-width:685px;'>
  <?php 
    //header of addAttachment
    if ( is_dir($folderPath) ) {
      $files = scandir($folderPath);

      $filesDot=array_search('..', $files);
      if($filesDot !== false)unset($files[$filesDot]);
      
      $filesDot=array_search('.', $files);
      if($filesDot !== false)unset($files[$filesDot]);
      
      if(count($files)>0){
        echo " <tr>";
        echo " <td class='assignHeader' ><div style='width:280px'>";
        if ( isNewGui() ) { echo " <div style='padding-top:7px'>"; }
        echo i18n('sectionAttachmentAdd')."&nbsp;";
        if ( isNewGui() ) { echo " </div>"; }
        echo " </div>";
        echo " </td>";
        echo " <td class='assignHeader' ><div style='width:120px'>".i18n('dashboardTicketMainTitleType')."</div></td>";
        echo " <td class='assignHeader' ><div style='width:110px'>".i18n('FileSize')."</div></td>";
        if( 1 or !empty($lstDoc) ){
          echo " <td class='assignHeader'><div style='width:175px'>".i18n('addTempAttachLib')."</div></td>";
        }
        echo " <td class=''>";
        echo " <div style='width:15px'></div>";
        echo " </td>";
        echo " </tr>";
        //data of AddAttachment
        foreach ( $files as $file ) {
          if ( $file !== '.' && $file !== '..' && is_file($folderPath . '/' . $file) ) {
            $fileSizeAdd = filesize( $folderPath . '/' . $file );
            $fileExtAdd = pathinfo( $file, PATHINFO_EXTENSION );
            if ( file_exists("../view/img/mime/$fileExtAdd.png") ) {
              $imgAdd="../view/img/mime/$fileExtAdd.png";
            } else {
              $imgAdd="../view/img/mime/unknown.png";
            }
            $fileName=pq_str_replace("'","",$file);
            $extAdd="file";
            echo "<tr>";
            echo "<td class='assignData verticalCenterData' >
                  <input type='hidden' id='name_dialogMail".$fileName."' name='name_dialogMail".$fileName."' value='".$fileName."'/>
                  <input type='hidden' id='size_dialogMail".$fileName."' name='size_dialogMail".$fileName."' value='".$fileSizeAdd."'/>
                  <div style='width:270px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;'>";
                   echo "<a style='margin-left: 5px,' onClick='removeAttachmentSendMail(\"$objectClass\",\"$objectId\"," . json_encode(htmlEncode($file)) .")'; title='" . i18n('removeAttachment') . "'>" . formatSmallButton('Remove') . "</a>";
                   echo "<div id='dialogMail".$fileName."' name='dialogMail".$fileName."' class='checkBoxAddAttachmentMail' style='display:none' checked dojoType='dijit.form.CheckBox' type='checkbox' onChange='showAttachedSize(".json_encode($fileSizeAdd).",".json_encode($fileName).",".json_encode($objectId).",".json_encode($extAdd).",".json_encode("DialogMail").");'>
                    </div>&nbsp;".$file."";
            echo "</div>
                </td>";
            echo " <td class='assignData verticalCenterData' style='text-align:center;'>";
            echo "<div style='width:110px'>";
            echo '<img src="'.$imgAdd.'" '.' title="'.htmlEncode($fileName).'" style="float:center;cursor:pointer"'.' onClick="showImage(\''.$objectClass.'\',\''.htmlEncode($objectId).'\',\''.htmlEncode($file, 'protectQuotes').'\',\'dialogMail\',\''.$fileSizeAdd.'\');" />';
            echo "</div>";
            echo "</td>";
            //
            echo " <td class='assignData verticalCenterData' style='width:105px;text-align:center;'><div style='width:100px'>".octectConvertSize($fileSizeAdd)."</div></td>";
            if( 1 or !empty($lstDoc) ){
              
              echo " <td class='assignData verticalCenterData' style='text-align:center;'><div style='width:165px'><input dojotype='dijit.form.CheckBox' class='keepAttachmentMail' id='keepAttachmentMail_".$fileName."' name='keepAttachmentMail[]' title='". i18n('addTempAttach')."' value='".htmlEncode($file)."' /></div></td>";
            }
            echo " </tr>";
          }
        }
      }
    } ?>
  </table>