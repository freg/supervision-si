<?php
/* * * COPYRIGHT NOTICE *********************************************************
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
 * ** DO NOT REMOVE THIS NOTICE *********************************************** 
 * 
 * 
 * 
 * * ** instalation steps ****
 * reportAttachment
 * mkavurcic@gmail.com
 *
 * *** copy this file to ../report ****
 * 
 * *** sql - insert report data into database -- Miscellaneous report group ****
  INSERT INTO report (`id`, `name`, `idReportCategory`, `file`, `sortOrder`, `hasPdf`) VALUES
  (1000, 'reportAttachment', 9, 'attachment.php', 950, 1);
  INSERT INTO reportparameter (`idReport`, `name`, `paramType`, `sortOrder`, `defaultValue`) VALUES
  (1000, 'idUser', 'userList', 10, null);
  INSERT INTO projeqtor.reportparameter (idReport, `name`, paramType, sortOrder, idle, defaultValue, multiple) 
	VALUES (1000, 'Idle', 'boolean', 20, 0, true, 0);
 * 
 * *** Adjust report access rights to your needs ****
 * 
 * *** add new lines in ../tool/i18n/nls/en/lang.js - translate into other languages, if needed, and add to corresponding lang.js files ****
  sumOfAccessibleFiles: "Sum of accessible files",
  sumOfFiles: "Sum of attached files",
  reportAttachment: "Attachments",
 * 
 * ** */

include_once '../tool/projeqtor.php';

//header
$paramActive = '';
$paramUser = '';
$headerParameters = '';

if (pq_array_key_exists('idUser', $_REQUEST) and pq_trim($_REQUEST['idUser']) != "") {
    $paramUser = pq_trim($_REQUEST['idUser']);
    Security::checkValidId($paramUser);

    $headerParameters .= i18n("colIdUser") . ' : ' . htmlEncode(SqlList::getNameFromId('user', $paramUser)) . '<br/>';
} else {
    $headerParameters .= i18n("colIdUser") . ': ' . i18n("allUsers") . ' <br>';
}

if (pq_array_key_exists('Idle',$_REQUEST)) {
  $paramActive=true;
  $headerParameters .= i18n('labelShowIdle') . ' = ' . i18n('displayYes') . '<br>';
} else {
  $paramActive = FALSE;
    $headerParameters .= i18n('labelShowIdle') . ' = ' . i18n('displayNo') . '<br>';
}

$headerParameters .= i18n('colCreateDateTime') . ', ' . i18n("sortDesc");

//where 
$where = '';
if ($paramUser) {
    $where = 'idUser=' . $paramUser;
}

//attachment fetch
$att = new Attachment();
$res_att = $att->getSqlElementsFromCriteria(null, null, $where, 'creationDate desc');

include "header.php";

// Headers 
echo '<table id="att" style="width=750px;margin-left:auto; margin-right:auto" >';
echo '<TR>';
    echo '  <TD class="reportTableHeader" style="width:1%;">' . '</TD>';
    echo '  <TD class="reportTableHeader" style="width:9%;">' . i18n('colFileName') . '</TD>';
    echo '  <TD class="reportTableHeader" style="width:15%">' . i18n('colDescription') . '</TD>';
    echo '  <TD class="reportTableHeader" style="width:5%;">' . i18n('colFileSize') . '</TD>';
    echo '  <TD class="reportTableHeader" style="width:10%;">' . i18n('colIsPrivate') . '</TD>';
    echo '  <TD class="reportTableHeader" style="width:10%;">' . i18n('colIdProject') . '</TD>';
    echo '  <TD class="reportTableHeader" style="width:10%;">' . i18n('colRefType') . '</TD>';
    echo '  <TD class="reportTableHeader" style="width:10%;">' . i18n('colRefId') . '</TD>';
    echo '  <TD class="reportTableHeader" style="width:15%;">' . i18n('colDescription') . '</TD>';
    echo '  <TD class="reportTableHeader" style="width:10%;">' . i18n('colUserName') . '</TD>';
    echo '  <TD class="reportTableHeader" style="width:5%;">' . i18n('colCreateDateTime') . '</TD>';
echo '</TR>';
//rows
$paramPathSeparator = Parameter::getGlobalParameter ( 'paramPathSeparator' );
$paramAttachmentDirectory = Parameter::getGlobalParameter ( 'paramAttachmentDirectory' );
$nr = 0;
$nr1 = 0;
$fs = 0;
$notFound=0;
foreach ($res_att as $att) {
    if (! class_exists($att->refType)) continue;
    $nr += 1;
    $paramId = 'idProject';
    if ($att->refType == 'Project') {
        $paramId = 'id';
    }
//access rights check - "project is in active user's visible projects list" and ("file is not private" or "file idUser equals active user" or "active user is admin")
    if (in_array(
                    SqlList::getNameFromId(
                            'Project'
                            , implode(
                                    '',  SqlList::getListWithCrit(
                                            $att->refType, array('id' => $att->refId), $paramId, NULL, $paramActive)
                            )
                    )
                    , getUserVisibleObjectsList('Project')
            )
            and ( $att->idPrivacy != SqlList::getIdFromTranslatableName('privacy', 'private')
            or $user->id == $att->idUser
            )
    ) {
        $nr1 += 1;
        $fs += $att->fileSize;
        $exists=true;
        $subDirectory = pq_str_replace ( '${attachmentDirectory}', $paramAttachmentDirectory, $att->subDirectory );
        if ($att->fileName and $att->subDirectory and ! file_exists($subDirectory.$paramPathSeparator.$att->fileName)) {
          $notFound++;
          $exists=false;
        }
        
        echo '<TR>';
            echo '  <TD class="attachmentData smallButtonsGroup" style="width:5px">';
            if ($att->fileName and $att->subDirectory and $outMode!='pdf') {
              if ($exists) {
                echo'<a href="../tool/download.php?class=Attachment&id=' . htmlEncode($att->id) . Security::addTokenIndexToUrl().'" target="printFrame" title="' . i18n('helpDownload') . '">'
                . formatSmallButton('Download');
                echo '</a>';
              } else {
                echo '<div title="' . i18n('errorNotFoundAttachment').'" class="iconButtonFailed16 iconButtonFailed iconSize16" ></div>';
              }
            }
            if ($att->link) {
                echo '<div style="float:center;cursor:pointer" title="' . htmlEncode($att->link) . '" onClick="window.open(\'' . htmlEncode(urldecode($att->link)) . '\')" target="_blank">'
                //. '<img src="../view/img/mime/html.png" />';
                .formatSmallButton('Link');
                echo '</div>';
            }
            echo '</TD>';
            echo '  <TD class="reportTableData" style="white-space:nowrap">' . $att->fileName . '</TD>';
            if ($outMode=='pdf') echo '  <TD class="reportTableData">' . insertLineBreaksForPdf($att->description,35) . '</TD>';
            else echo '  <TD class="reportTableData">' . $att->description . '</TD>';
            echo '  <TD class="reportTableData" style="text-align:right;white-space:nowrap">' . htmlGetFileSize($att->fileSize) . '</TD>';
            echo '  <TD class="reportTableData" style="white-space:nowrap">';
            switch ($att->idPrivacy) {
                case SqlList::getIdFromTranslatableName('privacy', 'private') :
                    echo '<span style="display:inline-block" >'.formatIcon('Locked',16,null, false, false).'</span>&nbsp;';
                    // echo '<img style="width:14px; vertical-align:top" src="../view/css/images/iconLock32.png" /> ';
                    echo SqlList::getNameFromId('privacy', $att->idPrivacy);
                    break;
                default: echo SqlList::getNameFromId('privacy', $att->idPrivacy);
            }
            echo '</TD>';
            echo '  <TD class="reportTableData">'
            . SqlList::getNameFromId('Project', array_values(SqlList::getListWithCrit($att->refType, array('id' => $att->refId), $paramId, NULL, $paramActive))[0]) . '</TD>';
            echo '  <TD class="reportTableData" style="text-align:left;white-space:nowrap">&nbsp;'
                .'<span style="display:inline-block">'.formatIcon($att->refType,16,null, false, false).'</span>&nbsp;' . i18n($att->refType) . '</TD>';
            echo '  <TD class="reportTableData" style="white-space:nowrap">' . $att->refId . '</TD>';
            if ($outMode=='pdf') echo '  <TD class="reportTableData">' . insertLineBreaksForPdf(SqlList::getNameFromId($att->refType, $att->refId),35) . '</TD>';
            else echo '  <TD class="reportTableData">' . SqlList::getNameFromId($att->refType, $att->refId) . '</TD>';
            echo '  <TD class="reportTableData" style="white-space:nowrap">' . SqlList::getNameFromId('user', $att->idUser) . '</TD>';
            echo '  <TD class="reportTableData" style="white-space:nowrap">' . htmlFormatDateTime($att->creationDate) . '</TD>';
        echo '</TR>';
    }
}
//summary row
echo '<TR>';
    echo '<TD class="reportTableLineHeader" colspan="2" style="text-align:left; white-space:nowrap">' . i18n('sumOfFiles') . ': <b>' . intval($nr-$nr1) . '</b></TD>';
    echo '<TD class="reportTableLineHeader" colspan="1" style="text-align:left; white-space:nowrap">' . i18n('sumOfAccessibleFiles') . ': <b>' . $nr1 . '</b></TD>';
    echo '<TD class="reportTableLineHeader" colspan="1" style="text-align:right; white-space:nowrap"><b>' . htmlGetFileSize($fs) . '</b></TD>';
    echo '<TD class="reportTableLineHeader" colspan="7" style="background-color:yellow;">' . (($notFound)?i18n('sumOfNotExistingFiles') . ': <b>' . $notFound. '</b>':'').'</TD>';
echo '</TR>';
echo '</table>';
echo "<br>";
echo "<br>";
