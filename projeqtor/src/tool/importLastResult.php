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
require_once "../model/ImportProgress.php";
header('Content-Type: text/html; charset=UTF-8');
scriptLog('   ->/tool/importLastResult.php');

$idUser = getCurrentUserId();
if (is_object($idUser)) { $idUser = $idUser->id; }

$result = ImportProgress::getLastResult($idUser);
?>
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta http-equiv="content-type" content="text/html; charset=UTF-8" />
  <link rel="stylesheet" type="text/css" href="<?php echoStaticFileNameWithCacheMgt('../view/css/projeqtor.css');?>" />
  <link rel="stylesheet" type="text/css" href="<?php echoStaticFileNameWithCacheMgt('../view/css/projeqtorFlat.css');?>" />
  <?php if (isNewGui()) {?><link rel="stylesheet" type="text/css" href="<?php echoStaticFileNameWithCacheMgt('../view/css/projeqtorNew.css');?>" /> <?php }?>

</head>
<body id="importLastResult" class="white" style="display:block;overflow: auto;">
<?php if ($result) { ?>
  <div style="padding:8px 12px;margin:8px;display:inline-flex;align-items:center;gap:100px;">
    <div style="color:#555;line-height:1.6;">
      <?php echo i18n('importDoneOn').' : '.htmlFormatDateTime($result['dateTime'], false); ?><br/>
      <?php if (!empty($result['class'])) { ?>
        <?php echo ucfirst(i18n('colType')); ?> : <strong><?php echo i18n($result['class']); ?></strong><br/>
      <?php } ?>
      <?php if (!empty($result['fileName'])) { ?>
        <?php echo ucfirst(i18n('colFile')); ?> : <strong><?php echo htmlEncode($result['fileName']); ?></strong>
      <?php } ?>
    </div>
    <button id="purgeImportResultButton" onClick="window.top.purgeImportResult();"   style="cursor:pointer;padding:8px 18px;border:1px solid #d0d7de;border-radius:6px;background:#ffffff;font-size:14px;transition:all .2s ease;box-shadow:0 1px 3px rgba(0,0,0,.08);"
        onmouseover="this.style.background='#f5f7fa';this.style.borderColor='#b8c2cc';this.style.boxShadow='0 3px 8px rgba(0,0,0,.12)';"
        onmouseout="this.style.background='#fff';this.style.borderColor='#d0d7de';this.style.boxShadow='0 1px 3px rgba(0,0,0,.08)';">
     <?php echo i18n('buttonPurge'); ?>
    </button>
  </div>
  <?php echo $result['html']; ?>
<?php } else { ?>
<span style="color:#666;font-style:italic;padding-left: 20px;">
  <?php echo i18n('noImportResultAvailable'); ?>
  </span>
<?php } ?>
</body>